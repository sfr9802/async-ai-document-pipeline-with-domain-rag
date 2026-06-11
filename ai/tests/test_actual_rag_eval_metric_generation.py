from __future__ import annotations

import csv
import json
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

from ai.eval.actual_rag_eval import (
    DatasetSchemaError,
    ExpectedEvidenceResolver,
    EvidenceResolutionConfig,
    FakeDeterministicEmbeddingProvider,
    FakeVectorAdapter,
    RepoCurrentBm25Adapter,
    SourceNativeCorpusLoader,
    append_actual_rag_status_event,
    build_backend_comparison_metrics,
    build_run_comparison,
    answer_correct,
    abstains,
    heuristic_judge_answer,
    load_eval_dataset,
    make_actual_rag_run_id,
    normalize_answer_text,
    run_eval_from_paths,
    score_rag_eval_items,
    validate_actual_rag_guardrails,
    write_latest_pointers,
)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def output_file_names(path: Path) -> list[str]:
    return sorted(item.name for item in path.iterdir() if item.is_file())


def test_schema_validation_preserves_partial_gold_without_promoting_to_headline(tmp_path: Path) -> None:
    dataset = tmp_path / "partial_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "Where did Mitsuha go?",
                "answerability": "answerable",
                "expected_answer": "Tokyo",
                "expected_answer_aliases": ["도쿄"],
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Tokyo", "required": True}],
            },
            {"id": "q2", "query": "Missing label is allowed as diagnostic partial gold."},
        ],
    )

    items = load_eval_dataset(dataset)

    assert [item.id for item in items] == ["q1", "q2"]
    assert items[1].answerability == "unknown"
    assert "missing_answerability_label" in items[1].validation_warnings
    assert "missing_expected_answer" in items[1].validation_warnings
    assert "missing_expected_evidence" in items[1].validation_warnings
    assert items[1].expected_evidence == ()


def test_schema_validation_fails_clearly_for_invalid_evidence_shape(tmp_path: Path) -> None:
    dataset = tmp_path / "bad_gold.jsonl"
    write_jsonl(
        dataset,
        [{"id": "q1", "query": "bad", "answerability": "answerable", "expected_evidence": "not-a-list"}],
    )

    with pytest.raises(DatasetSchemaError, match=r"q1.*expected_evidence must be a list"):
        load_eval_dataset(dataset)


def test_existing_csv_golden_shape_loads_with_warnings_not_conversion_work(tmp_path: Path) -> None:
    dataset = tmp_path / "gold.csv"
    dataset.write_text(
        "\n".join(
            [
                "query_id,question,expected_answer,supporting_evidence,citation_locator,user_answerability_label",
                'csv_1,Where?,Seoul,Seoul is the capital.,"{""file"": ""doc-a"", ""search_unit_id"": ""c1""}",ANSWERABLE_CONFIRMED',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    items = load_eval_dataset(dataset)

    assert items[0].id == "csv_1"
    assert items[0].query == "Where?"
    assert items[0].answerability == "answerable"
    assert items[0].expected_answer == "Seoul"
    assert items[0].expected_evidence[0].doc_id == "doc-a"
    assert items[0].expected_evidence[0].chunk_id == "c1"
    assert items[0].expected_evidence[0].text == "Seoul is the capital."
    assert "missing_expected_answer_aliases" in items[0].validation_warnings


def test_answer_normalization_aliases_and_abstention_detector() -> None:
    assert normalize_answer_text("  Seoul, Korea!  ") == "seoul korea"
    assert answer_correct("서울입니다.", expected_answer="Seoul", aliases=["서울입니다"])
    assert not answer_correct("Busan", expected_answer="Seoul", aliases=["서울"])
    assert abstains("문서에서 찾을 수 없습니다. 제공된 context에 답이 없습니다.")
    assert abstains("The answer is not available from the provided context.")
    assert not abstains("The answer is Seoul.")


def test_provisional_heuristic_judge_marks_semantic_contains_without_replacing_strict() -> None:
    result = heuristic_judge_answer(
        generated_answer="The answer is Seoul, based on the provided context.",
        expected_answer="Seoul",
        aliases=[],
        expected_evidence_texts=[],
        retrieved_context_texts=["Seoul is the capital city."],
        notes="",
    )

    assert result["judge_version"] == "heuristic_overlap_v1"
    assert result["provisional"] is True
    assert result["passed"] is True
    assert result["reason"] == "expected_answer_contained_in_generated_answer"
    assert answer_correct(
        "The answer is Seoul, based on the provided context.",
        expected_answer="Seoul",
        aliases=[],
    ) is False


def test_score_accepts_deterministic_fake_judge_adapter_without_model_calls(tmp_path: Path) -> None:
    class DeterministicFakeJudge:
        config = {
            "enabled": True,
            "tier": "provisional",
            "judge_kind": "deterministic_test_fake",
            "judge_version": "test_fake_v1",
            "threshold": 1.0,
            "prompt": "test fixture only",
            "external_api_calls": False,
        }

        def evaluate(self, *, item, generated_answer, retrieved_context_texts, expected_evidence_texts):
            return {
                "passed": item.id == "semantic",
                "available": True,
                "provisional": True,
                "judge_kind": "deterministic_test_fake",
                "judge_version": "test_fake_v1",
                "reason": "fixture",
            }

    dataset = tmp_path / "semantic_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "semantic",
                "query": "semantic answer?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital.", "required": True}],
            }
        ],
    )
    items = load_eval_dataset(dataset)
    outputs = [
        {
            "id": "semantic",
            "query": "semantic answer?",
            "answerability": "answerable",
            "generated_answer": "The capital city is Seoul.",
            "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul is the capital."}],
            "citations": [],
            "expected_answer": "Seoul",
            "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital.", "required": True}],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {},
        }
    ]

    summary, _rows = score_rag_eval_items(
        items,
        outputs,
        top_k_values=[1],
        judge_adapter=DeterministicFakeJudge(),
    )

    assert summary["judge_config"]["judge_kind"] == "deterministic_test_fake"
    assert summary["provisional_metrics"]["judged_answer_correctness_provisional"]["denominator"] == 1
    assert summary["provisional_metrics"]["judged_answer_correctness_provisional"]["numerator"] == 1
    assert summary["judge_config"]["external_api_calls"] is False


def test_e2e_provisional_fails_when_judge_fails_despite_generic_overlap(tmp_path: Path) -> None:
    dataset = tmp_path / "generic_overlap_false_positive.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "anime_wrong_entity",
                "query": "자동판매기 미궁 방랑 애니 3기 감독과 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "야마모토 타카시, 2026년 4월",
                "expected_evidence": [
                    {
                        "doc_id": "doc-expected",
                        "chunk_id": "chunk-expected",
                        "text": "일본 라이트 노벨 자동판매기로 다시 태어난 나는 미궁을 방랑한다 원작 TV 애니메이션 제3기 감독 야마모토 타카시 방영 시기는 2026년 4월",
                        "required": True,
                    }
                ],
            }
        ],
    )
    outputs = [
        {
            "id": "anime_wrong_entity",
            "query": "자동판매기 미궁 방랑 애니 3기 감독과 방영 시기는?",
            "answerability": "answerable",
            "generated_answer": "감독은 나베시마 오사무, 방영 시기는 2006년 10월입니다.",
            "retrieved_contexts": [
                {
                    "rank": 1,
                    "doc_id": "doc-other",
                    "chunk_id": "chunk-other",
                    "score": 0.9,
                    "text": "일본 만화 D.Gray-man 원작 TV 애니메이션 제3기 감독 나베시마 오사무 방영 시기는 2006년 10월",
                }
            ],
            "citations": [],
            "expected_answer": "야마모토 타카시, 2026년 4월",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {},
        }
    ]

    items = load_eval_dataset(dataset)
    summary, rows = score_rag_eval_items(items, outputs, top_k_values=[1])
    row = rows[0]

    assert row["metric_results"]["judged_answer_correctness_provisional"]["passed"] is False
    assert row["metric_results"]["weak_evidence_match_recall@1"] is False
    assert row["metric_results"]["e2e_rag_success_provisional"] is False
    assert summary["provisional_metrics"]["e2e_rag_success_provisional"]["numerator"] == 0


def test_anchor_based_weak_evidence_positive_case_without_id_match(tmp_path: Path) -> None:
    dataset = tmp_path / "anchor_positive.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "anchor_positive",
                "query": "자동판매기 3기 감독은?",
                "answerability": "answerable",
                "expected_answer": "야마모토 타카시",
                "expected_evidence": [
                    {
                        "doc_id": "doc-expected",
                        "chunk_id": "chunk-expected",
                        "text": "자동판매기 미궁 방랑 애니메이션 제3기 감독 야마모토 타카시",
                        "required": True,
                    }
                ],
            }
        ],
    )
    outputs = [
        {
            "id": "anchor_positive",
            "query": "자동판매기 3기 감독은?",
            "answerability": "answerable",
            "generated_answer": "야마모토 타카시",
            "retrieved_contexts": [
                {
                    "rank": 1,
                    "doc_id": "doc-other",
                    "chunk_id": "chunk-other",
                    "score": 0.8,
                    "text": "자동판매기 미궁 방랑 애니메이션 제3기 감독 야마모토 타카시",
                }
            ],
            "citations": [],
            "expected_answer": "야마모토 타카시",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {},
        }
    ]

    items = load_eval_dataset(dataset)
    _summary, rows = score_rag_eval_items(items, outputs, top_k_values=[1])

    assert rows[0]["metric_results"]["weak_evidence_match_recall@1"] is True
    assert rows[0]["metric_results"]["e2e_rag_success_provisional"] is True


def test_weak_evidence_rejects_same_entity_wrong_date_anchor(tmp_path: Path) -> None:
    dataset = tmp_path / "wrong_date_anchor.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "wrong_date",
                "query": "자동판매기 3기 감독과 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "야마모토 타카시, 2026년 4월",
                "expected_evidence": [
                    {
                        "doc_id": "doc-expected",
                        "chunk_id": "chunk-expected",
                        "text": "자동판매기 미궁 방랑 애니메이션 제3기 감독 야마모토 타카시 방영 시기는 2026년 4월",
                        "required": True,
                    }
                ],
            }
        ],
    )
    outputs = [
        {
            "id": "wrong_date",
            "query": "자동판매기 3기 감독과 방영 시기는?",
            "answerability": "answerable",
            "generated_answer": "야마모토 타카시, 2025년 4월",
            "retrieved_contexts": [
                {
                    "rank": 1,
                    "doc_id": "doc-other",
                    "chunk_id": "chunk-other",
                    "score": 0.8,
                    "text": "자동판매기 미궁 방랑 애니메이션 제3기 감독 야마모토 타카시 방영 시기는 2025년 4월",
                }
            ],
            "citations": [],
            "expected_answer": "야마모토 타카시, 2026년 4월",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {},
        }
    ]

    items = load_eval_dataset(dataset)
    _summary, rows = score_rag_eval_items(items, outputs, top_k_values=[1])

    assert rows[0]["metric_results"]["judged_answer_correctness_provisional"]["passed"] is False
    assert rows[0]["metric_results"]["weak_evidence_match_recall@1"] is False
    assert rows[0]["metric_results"]["e2e_rag_success_provisional"] is False


def test_inferred_answerable_metrics_do_not_mutate_unknown_gold_label(tmp_path: Path) -> None:
    dataset = tmp_path / "unknown_with_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "unknown_gold",
                "query": "What is the capital?",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital.", "required": True}],
            }
        ],
    )
    outputs = [
        {
            "id": "unknown_gold",
            "query": "What is the capital?",
            "answerability": "answerable",
            "generated_answer": "Seoul",
            "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul is the capital."}],
            "citations": [],
            "expected_answer": "Seoul",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": False,
                "has_citations": False,
            },
            "diagnostics": {},
        }
    ]

    items = load_eval_dataset(dataset)
    summary, rows = score_rag_eval_items(items, outputs, top_k_values=[1])

    assert items[0].answerability == "unknown"
    assert rows[0]["answerability"] == "unknown"
    assert summary["strict_metrics"]["exact_or_alias_answer_correctness"]["denominator"] == 0
    assert summary["inferred_answerable_metrics"]["exact_or_alias_answer_correctness_inferred_answerable"]["denominator"] == 1
    assert summary["inferred_answerable_metrics"]["exact_or_alias_answer_correctness_inferred_answerable"]["numerator"] == 1
    assert summary["inferred_answerable_metrics"]["e2e_rag_success_inferred_answerable"]["numerator"] == 1
    assert rows[0]["metric_results"]["answerability_inferred_for_metrics_only"] is True


def test_score_rag_eval_items_separates_headline_denominators_from_diagnostics(tmp_path: Path) -> None:
    dataset = tmp_path / "gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "good",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_answer_aliases": ["서울"],
                "expected_evidence": [
                    {"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital.", "required": True}
                ],
            },
            {
                "id": "rank3",
                "query": "rank three evidence?",
                "answerability": "answerable",
                "expected_answer": "evidence three",
                "expected_evidence": [{"doc_id": "doc-c", "chunk_id": "c3", "text": "evidence three", "required": True}],
            },
            {"id": "partial", "query": "partial gold", "answerability": "answerable"},
            {"id": "empty", "query": "unknown label"},
            {"id": "unanswerable", "query": "not in corpus", "answerability": "unanswerable"},
            {
                "id": "provisional",
                "query": "partial answer support?",
                "answerability": "answerable",
                "expected_evidence": [
                    {"doc_id": "doc-p", "chunk_id": "cp", "text": "Seoul is the capital city.", "required": True}
                ],
                "notes": "Expected answer is missing, but evidence text can support provisional scoring.",
            },
        ],
    )
    items = load_eval_dataset(dataset)
    outputs = [
        {
            "id": "good",
            "query": "capital?",
            "answerability": "answerable",
            "generated_answer": "Seoul",
            "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul"}],
            "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul"}],
            "expected_answer": "Seoul",
            "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": True,
            },
            "diagnostics": {},
        },
        {
            "id": "rank3",
            "query": "rank three evidence?",
            "answerability": "answerable",
            "generated_answer": "evidence three",
            "retrieved_contexts": [
                {"rank": 1, "doc_id": "doc-x", "chunk_id": "cx", "score": 0.9, "text": "wrong"},
                {"rank": 2, "doc_id": "doc-y", "chunk_id": "cy", "score": 0.8, "text": "wrong"},
                {"rank": 3, "doc_id": "doc-c", "chunk_id": "c3", "score": 0.7, "text": "evidence three"},
            ],
            "citations": [
                {"doc_id": "doc-c", "chunk_id": "c3", "text": "evidence three"},
                {"doc_id": "doc-x", "chunk_id": "cx", "text": "wrong"},
            ],
            "expected_answer": "evidence three",
            "expected_evidence": [{"doc_id": "doc-c", "chunk_id": "c3", "text": "evidence three", "required": True}],
            "metric_inputs_available": {
                "has_expected_answer": True,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": True,
            },
            "diagnostics": {},
        },
        {
            "id": "partial",
            "query": "partial gold",
            "answerability": "answerable",
            "generated_answer": "some answer",
            "retrieved_contexts": [],
            "citations": [],
            "expected_answer": "",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": False,
                "has_expected_evidence": False,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {"gold_incomplete": True},
        },
        {
            "id": "empty",
            "query": "unknown label",
            "answerability": "unknown",
            "generated_answer": "",
            "retrieved_contexts": [],
            "citations": [],
            "expected_answer": "",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": False,
                "has_expected_evidence": False,
                "has_answerability_label": False,
                "has_citations": False,
            },
            "diagnostics": {"retrieval_empty": True, "generation_empty": True, "gold_incomplete": True},
        },
        {
            "id": "unanswerable",
            "query": "not in corpus",
            "answerability": "unanswerable",
            "generated_answer": "문서에서 찾을 수 없습니다.",
            "retrieved_contexts": [],
            "citations": [],
            "expected_answer": "",
            "expected_evidence": [],
            "metric_inputs_available": {
                "has_expected_answer": False,
                "has_expected_evidence": False,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {"retrieval_empty": True, "citation_empty": True},
        },
        {
            "id": "provisional",
            "query": "partial answer support?",
            "answerability": "answerable",
            "generated_answer": "Seoul is the capital city.",
            "retrieved_contexts": [
                {"rank": 1, "doc_id": "doc-p", "chunk_id": "cp", "score": 0.9, "text": "Seoul is the capital city."}
            ],
            "citations": [],
            "expected_answer": "",
            "expected_evidence": [
                {"doc_id": "doc-p", "chunk_id": "cp", "text": "Seoul is the capital city.", "required": True}
            ],
            "metric_inputs_available": {
                "has_expected_answer": False,
                "has_expected_evidence": True,
                "has_answerability_label": True,
                "has_citations": False,
            },
            "diagnostics": {"citation_empty": True, "gold_incomplete": True},
        },
    ]

    summary, scored_rows = score_rag_eval_items(items, outputs, top_k_values=[1, 3])

    strict = summary["strict_metrics"]
    provisional = summary["provisional_metrics"]
    assert strict["exact_or_alias_answer_correctness"]["numerator"] == 2
    assert strict["exact_or_alias_answer_correctness"]["denominator"] == 2
    assert strict["evidence_recall@1"]["numerator"] == 2
    assert strict["evidence_recall@1"]["denominator"] == 3
    assert strict["evidence_recall@3"]["numerator"] == 3
    assert strict["citation_precision"]["numerator"] == 2
    assert strict["citation_precision"]["denominator"] == 3
    assert strict["citation_recall"]["numerator"] == 2
    assert strict["citation_recall"]["denominator"] == 2
    assert strict["abstention_accuracy"]["numerator"] == 1
    assert strict["abstention_accuracy"]["denominator"] == 1
    assert strict["e2e_rag_success_strict"]["denominator"] == 2
    assert strict["e2e_rag_success_strict"]["numerator"] == 1
    assert provisional["judged_answer_correctness_provisional"]["denominator"] == 3
    assert provisional["judged_answer_correctness_provisional"]["numerator"] == 3
    assert provisional["weak_evidence_match_recall@1"]["numerator"] == 2
    assert provisional["e2e_rag_success_provisional"]["numerator"] == 3
    assert "answer_supported_by_retrieved_context_provisional" not in provisional
    assert summary["diagnostic_metric_details"]["answer_extracted_from_retrieved_context_rate"]["denominator"] == 3
    assert summary["diagnostic_metric_details"]["citation_points_to_retrieved_context_rate"]["denominator"] == 3
    assert "citation_overlap_provisional" not in provisional
    assert summary["diagnostic_metrics"]["missing_expected_answer_count"] == 4
    assert summary["diagnostic_metrics"]["missing_answerability_label_count"] == 1
    assert summary["diagnostic_metrics"]["gold_missing_count"] == 3
    assert summary["diagnostic_metrics"]["expected_evidence_id_missing_count"] == 0
    assert summary["diagnostic_metrics"]["expected_evidence_id_unresolved_count"] == 0
    assert "gold_missing_expected_answer" in {label for row in scored_rows for label in row["failure_labels"]}
    assert "provisional_metric_used" in next(row for row in scored_rows if row["id"] == "provisional")["failure_labels"]
    assert "strict_metric_not_applicable" in next(row for row in scored_rows if row["id"] == "provisional")["failure_labels"]
    assert "citation_wrong" in next(row for row in scored_rows if row["id"] == "rank3")["failure_labels"]


def test_expected_evidence_resolver_exact_id_and_high_confidence_text_candidate(tmp_path: Path) -> None:
    dataset = tmp_path / "resolver_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "exact",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [
                    {"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital.", "required": True}
                ],
            },
            {
                "id": "candidate",
                "query": "자동판매기 3기 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [
                    {
                        "text": "자동판매기 미궁 방랑 애니메이션 제3기 방영 시기는 2026년 4월",
                        "required": True,
                    }
                ],
            },
        ],
    )
    items = {item.id: item for item in load_eval_dataset(dataset)}
    resolver = ExpectedEvidenceResolver(EvidenceResolutionConfig(scope="both", max_candidates=3))

    exact = resolver.resolve_item(
        items["exact"],
        retrieved_contexts=[{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul"}],
        index_candidates=[],
    )
    candidate = resolver.resolve_item(
        items["candidate"],
        retrieved_contexts=[],
        index_candidates=[
            {
                "rank": 1,
                "doc_id": "doc-auto",
                "chunk_id": "chunk-2026",
                "score": 0.88,
                "text": "자동판매기 미궁 방랑 애니메이션 제3기 방영 시기는 2026년 4월입니다.",
            }
        ],
    )

    assert exact["rows"][0]["id_status"] == "resolved_exact"
    assert exact["rows"][0]["selected_candidate"]["confidence"] == "high"
    assert exact["rows"][0]["selected_candidate"]["source"] == "retrieved_contexts"
    assert candidate["rows"][0]["id_status"] == "resolved_candidate"
    assert candidate["rows"][0]["selected_candidate"]["doc_id"] == "doc-auto"
    assert candidate["rows"][0]["selected_candidate"]["confidence"] == "high"
    assert "numeric_or_date_anchors_satisfied" in candidate["rows"][0]["candidates"][0]["match_reasons"]


def test_expected_evidence_resolver_rejects_generic_overlap_and_numeric_mismatch(tmp_path: Path) -> None:
    dataset = tmp_path / "resolver_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "generic",
                "query": "source text?",
                "answerability": "answerable",
                "expected_answer": "document answer",
                "expected_evidence": [{"text": "document source answer text", "required": True}],
            },
            {
                "id": "date",
                "query": "방영 시기?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [{"text": "방영 시기는 2026년 4월", "required": True}],
            },
        ],
    )
    items = {item.id: item for item in load_eval_dataset(dataset)}
    resolver = ExpectedEvidenceResolver(EvidenceResolutionConfig(scope="both", max_candidates=3))

    generic = resolver.resolve_item(
        items["generic"],
        retrieved_contexts=[
            {"rank": 1, "doc_id": "doc-generic", "chunk_id": "c1", "score": 0.7, "text": "document source text answer"}
        ],
        index_candidates=[],
    )
    date_mismatch = resolver.resolve_item(
        items["date"],
        retrieved_contexts=[],
        index_candidates=[
            {"rank": 1, "doc_id": "doc-date", "chunk_id": "c2", "score": 0.7, "text": "방영 시기는 2025년 4월"}
        ],
    )

    assert generic["resolved_count"] == 0
    assert generic["rows"][0]["resolved"] is False
    assert "no_non_generic_anchor_overlap" in generic["rows"][0]["resolution_warnings"]
    assert date_mismatch["resolved_count"] == 0
    assert date_mismatch["rows"][0]["candidates"][0]["confidence"] == "low"
    assert "numeric_or_date_anchor_missing" in date_mismatch["rows"][0]["candidates"][0]["match_reasons"]


def test_medium_confidence_resolution_counts_only_when_configured(tmp_path: Path) -> None:
    dataset = tmp_path / "medium_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "medium",
                "query": "capital city?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"text": "Seoul is the capital city of Korea", "required": True}],
            }
        ],
    )
    item = load_eval_dataset(dataset)[0]
    contexts = [
        {"rank": 1, "doc_id": "doc-medium", "chunk_id": "c1", "score": 0.7, "text": "Seoul is the capital city of Korea"}
    ]

    default_resolution = ExpectedEvidenceResolver(EvidenceResolutionConfig(scope="retrieved-only")).resolve_item(
        item,
        retrieved_contexts=contexts,
        index_candidates=[],
    )
    medium_counted = ExpectedEvidenceResolver(
        EvidenceResolutionConfig(scope="retrieved-only", count_medium=True)
    ).resolve_item(item, retrieved_contexts=contexts, index_candidates=[])

    assert default_resolution["rows"][0]["selected_candidate"]["confidence"] == "medium"
    assert default_resolution["resolved_count"] == 0
    assert default_resolution["rows"][0]["resolved"] is False
    assert medium_counted["resolved_count"] == 1
    assert medium_counted["rows"][0]["resolved"] is True


def test_default_run_writes_single_report_json_with_embedded_sections(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "single"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul"}],
                "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul"}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="single",
        command="unit-test single",
    )

    assert output_file_names(output_dir) == ["report.json"]
    assert bundle.summary_path == output_dir / "report.json"
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["artifact_contract"]["output_mode"] == "single"
    assert report["artifact_contract"]["primary_report_json"] == (output_dir / "report.json").as_posix()
    assert report["artifact_contract"]["legacy_sidecars_written"] is False
    assert report["items"][0]["id"] == "q1"
    assert report["evidence_resolution"]["enabled"] is True
    assert report["backend_comparison"]["vector_index_available"] is False
    assert report["gpu_preflight"]["checked"] is True
    assert report["retrieval_backend"]["requested"] == "auto"
    assert report["generator_config"]["provider"] == "extractive-v1"
    assert report["human_review_packet"]["enabled"] is False


def test_legacy_output_mode_writes_old_artifacts_only_when_requested(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "legacy"
    write_jsonl(dataset, [{"id": "q1", "query": "capital?", "answerability": "answerable", "expected_answer": "Seoul"}])
    write_jsonl(context, [{"id": "q1", "generated_answer": "Seoul", "retrieved_contexts": [], "citations": []}])

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="legacy",
        output_mode="legacy",
    )

    assert bundle.summary_path == output_dir / "rag_eval_summary.json"
    assert "report.json" not in output_file_names(output_dir)
    assert {"rag_eval_items.jsonl", "rag_eval_summary.json", "rag_eval_report.md"}.issubset(output_file_names(output_dir))


def test_human_review_packet_mode_writes_exactly_one_additional_csv(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "review"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "자동판매기 3기 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [{"text": "자동판매기 제3기 방영 시기는 2026년 4월", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "2026년 4월",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-auto",
                        "chunk_id": "chunk-2026",
                        "score": 0.95,
                        "text": "TEXT source text 자동판매기 제3기 방영 시기는 2026년 4월입니다.",
                        "source_family": "TEXT",
                    }
                ],
                "citations": [{"doc_id": "doc-auto", "chunk_id": "chunk-2026", "text": "자동판매기 2026년 4월"}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="review",
        write_human_review_packet=True,
    )

    assert output_file_names(output_dir) == ["human_review_packet.csv", "report.json"]
    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    packet = report["human_review_packet"]
    assert packet["enabled"] is True
    assert packet["path"].endswith("human_review_packet.csv")
    assert packet["row_count"] >= 1
    assert packet["format"] == "csv"
    assert packet["human_decision_fields_blank"] is True
    assert packet["gold_qrels_labels_mutated"] is False
    with (output_dir / "human_review_packet.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all(row["human_mapping_decision"] == "" for row in rows)


def test_fake_vector_adapter_selects_hybrid_and_records_backend_comparison(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "hybrid"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "서울 수도",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital.", "required": True}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=2,
        run_id="hybrid",
        retrieval_backend="auto",
        retrieval_adapter=FakeVectorAdapter(),
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert report["retrieval_backend"]["requested"] == "auto"
    assert report["retrieval_backend"]["selected"] == "hybrid"
    assert report["retrieval_backend"]["vector_enabled"] is True
    assert report["backend_comparison"]["vector_index_available"] is True
    assert report["backend_comparison"]["bm25_candidate_count_avg"] > 0
    assert report["backend_comparison"]["vector_candidate_count_avg"] > 0
    assert report["backend_comparison"]["hybrid_candidate_count_avg"] > 0
    row = report["items"][0]["retrieval_backend_comparison"]
    assert row["selected_backend"] == "hybrid"
    assert row["bm25_top_k"]
    assert row["vector_top_k"]
    assert row["hybrid_top_k"]
    adapter_source = inspect.getsource(FakeVectorAdapter)
    for forbidden in ["expected_answer", "expected_evidence", "qrels", "query_id", "row_id", "target_id", "baseline_top"]:
        assert forbidden not in adapter_source


def test_auto_backend_falls_back_to_bm25_when_faiss_unavailable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    payloads = RepoCurrentBm25Adapter()._load_payloads()
    assert payloads
    query = " ".join(_clean_token for _clean_token in str(payloads[0]["bm25_text"]).split()[:8])
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "no_faiss"
    write_jsonl(dataset, [{"id": "q1", "query": query, "answerability": "unknown"}])

    monkeypatch.setitem(sys.modules, "faiss", None)

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=3,
        run_id="no_faiss",
        retrieval_backend="auto",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    assert report["retrieval_backend"]["requested"] == "auto"
    assert report["retrieval_backend"]["selected"] == "bm25"
    assert report["retrieval_backend"]["vector_enabled"] is False
    assert report["retrieval_backend"]["fallback_reason"].startswith("faiss_or_numpy_unavailable:")
    assert report["diagnostic_metrics"]["pipeline_error_count"] == 0
    assert report["backend_comparison"]["comparison_available"] is True
    assert report["backend_comparison"]["bm25_candidate_count_avg"] > 0
    assert report["items"][0]["retrieval_backend_comparison"]["selected_backend"] == "bm25"
    assert report["guardrails"]["gold_fields_used_for_candidate_generation"] is False


def test_backend_comparison_metrics_missing_rows_are_unavailable() -> None:
    class NoComparisonAdapter:
        backend_diagnostics = {
            "vector_index_available": False,
            "gpu_used_for_embedding": False,
            "fallback_reason": "unit_test_missing_comparison",
        }

    metrics = build_backend_comparison_metrics([{"id": "q1", "diagnostics": {}}], NoComparisonAdapter())

    assert metrics["comparison_available"] is False
    assert metrics["comparison_row_count"] == 0
    assert metrics["comparison_missing_row_count"] == 1
    assert metrics["bm25_retrieval_empty_rate"] is None
    assert metrics["vector_retrieval_empty_rate"] is None
    assert metrics["hybrid_retrieval_empty_rate"] is None
    assert metrics["bm25_candidate_count_avg"] is None
    assert metrics["fallback_reason"] == "unit_test_missing_comparison"


def test_source_native_corpus_loader_prefers_source_atom_rows_and_redacts_paths(tmp_path: Path) -> None:
    manifest = tmp_path / "search_view_manifest.jsonl"
    write_jsonl(
        manifest,
        [
            {
                "source_atom_id": "srcatom-1",
                "source_family": "TEXT",
                "search_view_id": "sv-1",
                "bm25_text": "needle evidence text from source atom",
                "embedding_text": "needle evidence text from source atom",
                "source_identity": "D:/secret/raw/path/source.txt",
                "workbook_id": "",
                "document_version_id": "doc-1",
                "faiss_row_id": 0,
            }
        ],
    )

    loader = SourceNativeCorpusLoader(search_view_manifest_path=manifest, source_atom_registry_path=tmp_path / "atoms.jsonl")
    units = loader.load_units()

    assert [unit["surface"] for unit in units] == ["source_atom"]
    assert units[0]["source_atom_id"] == "srcatom-1"
    assert units[0]["text"] == "needle evidence text from source atom"
    assert "D:/secret" not in json.dumps(units[0], ensure_ascii=False)
    assert units[0]["metadata"]["source_identity_hash"].startswith("sha256:")


def test_source_native_surface_auto_demotes_searchunit_when_source_native_wins(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "needle source-native answer",
                "answerability": "answerable",
                "expected_answer": "needle answer",
                "expected_evidence": [{"text": "needle answer appears in source native evidence", "required": True}],
            }
        ],
    )
    source_units = [
        {
            "unit_id": "src-unit-1",
            "source_atom_id": "srcatom-1",
            "doc_id": "source-doc",
            "chunk_id": "source-chunk",
            "source_family": "TEXT",
            "title": "Source Doc",
            "section": "Evidence",
            "text": "needle answer appears in source native evidence",
            "surface": "source_atom",
            "text_sha256": "src-sha",
            "metadata": {},
        }
    ]
    searchunit_units = [
        {
            "payload_id": "legacy-1",
            "search_unit_id": "legacy-chunk",
            "search_view_id": "legacy-view",
            "source_family": "TEXT",
            "bm25_text": "irrelevant legacy projection filler",
            "embedding_text": "irrelevant legacy projection filler",
            "metadata": {"source_safe_id": "legacy-doc", "source_text_sha256": "legacy-sha"},
        }
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=1,
        run_id="source_native",
        retrieval_surface="auto",
        retrieval_backend="hybrid",
        source_native_units=source_units,
        searchunit_units=searchunit_units,
        source_native_embedding_provider=FakeDeterministicEmbeddingProvider(),
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    assert report["retrieval_surface"]["requested"] == "auto"
    assert report["retrieval_surface"]["selected"] == "source_native"
    assert report["retrieval_surface_decision"]["searchunit_searchview_demoted"] is True
    assert report["diagnostic_metrics"]["source_native_expected_evidence_text_presence_rate"] == 1.0
    assert report["diagnostic_metrics"]["searchunit_expected_evidence_text_presence_rate"] == 0.0
    row = report["items"][0]
    assert row["retrieval_surface_comparison"]["selected"]["surface"] == "source_native"
    assert row["retrieval_surface_comparison"]["source_native"]["expected_evidence_retrieved"] is True
    assert row["retrieval_surface_comparison"]["searchunit_searchview"]["expected_evidence_retrieved"] is False
    assert report["guardrails"]["gold_fields_used_for_candidate_generation"] is False


def test_source_native_surface_classifies_absent_and_present_not_retrieved(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native_absence"
    write_jsonl(
        dataset,
        [
            {
                "id": "present_missed",
                "query": "generic query",
                "answerability": "answerable",
                "expected_answer": "hidden target",
                "expected_evidence": [{"text": "hidden target span", "required": True}],
            },
            {
                "id": "absent",
                "query": "absent query",
                "answerability": "answerable",
                "expected_answer": "missing target",
                "expected_evidence": [{"text": "missing target span", "required": True}],
            },
        ],
    )
    source_units = [
        {
            "unit_id": "src-hidden",
            "source_atom_id": "srcatom-hidden",
            "doc_id": "source-doc",
            "chunk_id": "hidden",
            "source_family": "TEXT",
            "title": "Hidden",
            "section": "Evidence",
            "text": "hidden target span",
            "surface": "source_atom",
            "text_sha256": "hidden-sha",
            "metadata": {},
        }
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=1,
        run_id="source_native_absence",
        retrieval_surface="source-native",
        retrieval_backend="bm25",
        source_native_units=source_units,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    diagnostics = report["diagnostic_metrics"]
    assert diagnostics["source_native_target_span_present_but_not_retrieved_count"] == 1
    assert diagnostics["source_native_target_span_absent_count"] == 1
    assert diagnostics["both_surfaces_fail_count"] == 2


def test_cli_smoke_with_fake_vector_adapter_hybrid_backend(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    output_dir = report_root / "cli_fake_hybrid"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.scripts.rag_actual_eval",
            "--dataset",
            str(dataset),
            "--top-k",
            "2",
            "--run-id",
            "cli_fake_hybrid",
            "--output-dir",
            str(output_dir),
            "--report-root",
            str(report_root),
            "--retrieval-backend",
            "hybrid",
            "--output-mode",
            "single",
            "--use-fake-vector-adapter",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_file_names(output_dir) == ["report.json"]
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["retrieval_backend"]["requested"] == "hybrid"
    assert report["retrieval_backend"]["selected"] == "hybrid"
    assert report["backend_comparison"]["vector_index_available"] is True
    assert report["items"][0]["retrieval_backend_comparison"]["vector_top_k"]
    assert report["guardrails"]["gold_fields_used_for_candidate_generation"] is False
    assert report["gold_fields_used_for_candidate_generation"] is False


def test_cli_smoke_with_fake_source_native_fixture_beats_searchunit(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    output_dir = report_root / "cli_source_native"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "needle source-native answer",
                "answerability": "answerable",
                "expected_answer": "needle answer",
                "expected_evidence": [{"text": "needle answer appears in source native evidence", "required": True}],
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.scripts.rag_actual_eval",
            "--dataset",
            str(dataset),
            "--top-k",
            "1",
            "--run-id",
            "cli_source_native",
            "--output-dir",
            str(output_dir),
            "--report-root",
            str(report_root),
            "--retrieval-surface",
            "auto",
            "--retrieval-backend",
            "auto",
            "--output-mode",
            "single",
            "--use-fake-source-native-fixture",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert output_file_names(output_dir) == ["report.json"]
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["retrieval_surface"]["selected"] == "source_native"
    assert report["retrieval_surface_decision"]["searchunit_searchview_demoted"] is True
    assert report["items"][0]["retrieval_surface_comparison"]["source_native"]["expected_evidence_retrieved"] is True


def test_evidence_resolution_artifacts_summary_registry_status_and_markdown(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    status_path = tmp_path / "status.jsonl"
    original_dataset_bytes = dataset.read_bytes() if dataset.exists() else b""
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "자동판매기 3기 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [
                    {
                        "text": "자동판매기 미궁 방랑 애니메이션 제3기 방영 시기는 2026년 4월",
                        "required": True,
                    }
                ],
            }
        ],
    )
    original_dataset_bytes = dataset.read_bytes()
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "2026년 4월",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-auto",
                        "chunk_id": "chunk-2026",
                        "score": 0.9,
                        "text": "자동판매기 미궁 방랑 애니메이션 제3기 방영 시기는 2026년 4월입니다.",
                    }
                ],
                "citations": [{"doc_id": "doc-auto", "chunk_id": "chunk-2026", "text": "자동판매기 2026년 4월"}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=report_root / "resolved",
        context_jsonl_path=context,
        top_k=3,
        run_id="resolved",
        report_root=report_root,
        status_jsonl_path=status_path,
        append_registry=True,
        write_latest=True,
        resolve_expected_evidence=True,
        evidence_resolution_scope="both",
    )

    assert dataset.read_bytes() == original_dataset_bytes
    summary = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    item_row = summary["items"][0]
    artifact_paths = summary["artifact_paths"]
    assert output_file_names(report_root / "resolved") == ["report.json"]
    assert artifact_paths["evidence_resolution_candidates_jsonl"] == ""
    assert summary["evidence_resolution_candidates"]
    assert summary["diagnostic_metrics"]["expected_evidence_resolution_enabled"] is True
    assert summary["diagnostic_metrics"]["expected_evidence_resolution_scope"] == "both"
    assert summary["diagnostic_metrics"]["expected_evidence_row_count"] == 1
    assert summary["diagnostic_metrics"]["expected_evidence_id_missing_count"] == 1
    assert summary["diagnostic_metrics"]["expected_evidence_id_resolved_candidate_count"] == 1
    assert summary["diagnostic_metrics"]["expected_evidence_id_unresolved_count"] == 0
    assert summary["provisional_metrics"]["resolved_evidence_available_rate"]["numerator"] == 1
    assert summary["provisional_metrics"]["resolved_evidence_recall@3_provisional"]["numerator"] == 1
    assert summary["provisional_metrics"]["citation_matches_resolved_evidence_precision_provisional"]["numerator"] == 1
    assert item_row["expected_evidence_resolution"]["resolved_count"] == 1
    assert item_row["expected_evidence_resolution"]["selected_candidates"][0]["doc_id"] == "doc-auto"
    assert summary["artifact_contract"]["output_mode"] == "single"
    assert summary["guardrails"]["gold_fields_used_for_candidate_generation"] is False

    registry_row = json.loads((report_root / "runs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    latest = json.loads((report_root / "latest_fixture.json").read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8").splitlines()[0])
    assert registry_row["evidence_resolution"]["enabled"] is True
    assert registry_row["evidence_resolution"]["expected_evidence_id_resolved_candidate_count"] == 1
    assert latest["evidence_resolution"]["expected_evidence_id_resolved_candidate_count"] == 1
    assert status["evidence_id_resolved_candidate_count"] == 1


def test_evidence_mapping_packet_files_human_fields_and_summary_counts(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    status_path = tmp_path / "status.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q_accept",
                "query": "자동판매기 3기 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [{"text": "자동판매기 제3기 방영 시기는 2026년 4월", "required": True}],
            },
            {
                "id": "q_reject",
                "query": "다른 작품 3기 방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [{"text": "자동판매기 제3기 방영 시기는 2026년 4월", "required": True}],
            },
            {
                "id": "q_review",
                "query": "미츠하는 어디로 향했어?",
                "answerability": "answerable",
                "expected_answer": "도쿄",
                "expected_evidence": [{"text": "미츠하가 타키를 만나러 도쿄로 향했다", "required": True}],
            },
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q_accept",
                "generated_answer": "2026년 4월",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-auto",
                        "chunk_id": "chunk-2026",
                        "score": 0.95,
                        "text": "TEXT source text 자동판매기 제3기 방영 시기는 2026년 4월입니다.",
                        "source_family": "TEXT",
                        "source_kind": "source_derived_semantic_snippet",
                        "source_title": "safe text source",
                    }
                ],
                "citations": [{"doc_id": "doc-auto", "chunk_id": "chunk-2026", "text": "자동판매기 2026년 4월"}],
            },
            {
                "id": "q_reject",
                "generated_answer": "2006년 10월",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-wrong",
                        "chunk_id": "chunk-2006",
                        "score": 0.8,
                        "text": "PDF source text 다른 만화 TV 애니메이션 제3기 방영 시기는 2006년 10월입니다.",
                        "source_family": "PDF",
                        "source_kind": "source_derived_semantic_snippet",
                    }
                ],
                "citations": [{"doc_id": "doc-wrong", "chunk_id": "chunk-2006", "text": "2006년 10월"}],
            },
            {
                "id": "q_review",
                "generated_answer": "도쿄",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-mitsuha",
                        "chunk_id": "chunk-tokyo",
                        "score": 0.7,
                        "text": "TEXT source text 미츠하는 도쿄로 향했다.",
                        "source_family": "TEXT",
                        "source_path": "C:\\Users\\sfr99\\raw\\mitsuha.txt",
                    }
                ],
                "citations": [{"doc_id": "doc-mitsuha", "chunk_id": "chunk-tokyo", "text": "미츠하 도쿄"}],
            },
        ],
    )

    original_dataset = dataset.read_bytes()
    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=report_root / "mapping_packet",
        context_jsonl_path=context,
        top_k=3,
        run_id="mapping_packet",
        report_root=report_root,
        status_jsonl_path=status_path,
        append_registry=True,
        write_latest=True,
        resolve_expected_evidence=True,
        evidence_resolution_scope="both",
        write_evidence_mapping_packet=True,
    )

    assert dataset.read_bytes() == original_dataset
    summary = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    artifact_paths = summary["artifact_paths"]
    csv_path = Path(artifact_paths["human_review_packet_csv"])
    jsonl_path = artifact_paths["evidence_mapping_review_packet_jsonl"]
    md_path = artifact_paths["evidence_mapping_review_packet_md"]
    packet_summary_path = artifact_paths["evidence_mapping_packet_summary_json"]
    assert csv_path.exists()
    assert jsonl_path == ""
    assert md_path == ""
    assert packet_summary_path == ""
    assert output_file_names(report_root / "mapping_packet") == ["human_review_packet.csv", "report.json"]

    with csv_path.open(encoding="utf-8", newline="") as handle:
        packet_rows = list(csv.DictReader(handle))
    assert packet_rows
    for row in packet_rows:
        assert row["human_mapping_decision"] == ""
        assert row["human_accepted_doc_id"] == ""
        assert row["human_accepted_chunk_id"] == ""
        assert row["human_answerability_label"] == ""
        assert row["human_relevance_label"] == ""
        assert row["human_decision_fields_filled_by_codex"] in {"False", False}
        assert "C:\\Users" not in json.dumps(row, ensure_ascii=False)

    by_item = {row["item_id"]: row for row in packet_rows}
    assert by_item["q_accept"]["machine_recommendation"] == "likely_accept"
    assert by_item["q_reject"]["machine_recommendation"] == "likely_reject"
    assert by_item["q_review"]["machine_recommendation"] in {"review_needed", "possible_match"}
    assert "raw_path_redacted" in by_item["q_review"]["risk_flags"]

    diagnostics = summary["diagnostic_metrics"]
    assert diagnostics["evidence_mapping_packet_enabled"] is True
    assert diagnostics["evidence_mapping_packet_item_count"] == 3
    assert diagnostics["evidence_mapping_packet_likely_accept_count"] == 1
    assert diagnostics["evidence_mapping_packet_likely_reject_count"] >= 1
    assert diagnostics["source_metadata_redacted_path_count"] >= 1
    assert diagnostics["human_decision_fields_filled_by_codex"] is False
    assert summary["human_review_packet"]["row_count"] == len(packet_rows)

    registry_row = json.loads((report_root / "runs.jsonl").read_text(encoding="utf-8").splitlines()[0])
    latest = json.loads((report_root / "latest_fixture.json").read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8").splitlines()[0])
    assert registry_row["evidence_mapping_packet"]["enabled"] is True
    assert latest["evidence_mapping_packet"]["human_decision_fields_filled_by_codex"] is False
    assert status["evidence_mapping_packet"]["evidence_mapping_packet_likely_accept_count"] == 1


def test_evidence_mapping_packet_comparison_metrics_are_new_or_unavailable() -> None:
    previous = {
        "run_id": "previous",
        "top_k": 3,
        "strict_metrics": {},
        "provisional_metrics": {},
        "diagnostic_metrics": {},
    }
    current = {
        "run_id": "current",
        "top_k": 3,
        "strict_metrics": {},
        "provisional_metrics": {},
        "diagnostic_metrics": {
            "evidence_mapping_packet_candidate_count": 3,
            "evidence_mapping_packet_likely_accept_count": 1,
            "evidence_mapping_packet_possible_match_count": 1,
            "evidence_mapping_packet_review_needed_count": 0,
            "evidence_mapping_packet_likely_reject_count": 1,
            "source_metadata_resolved_candidate_count": 2,
            "source_metadata_unresolved_candidate_count": 1,
        },
    }

    comparison = build_run_comparison(previous, current, target_label="previous")
    by_metric = {row["metric"]: row for row in comparison["rows"]}

    assert by_metric["evidence_mapping_packet_candidate_count"]["current"] == "3"
    assert by_metric["evidence_mapping_packet_likely_accept_count"]["interpretation"] == "unavailable"
    assert by_metric["source_metadata_resolved_candidate_count"]["current"] == "2"


def test_cli_smoke_with_evidence_mapping_packet_and_previous_comparison(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    status_path = tmp_path / "status.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"text": "Seoul is the capital city of Korea", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [
                    {"rank": 1, "doc_id": "doc-seoul", "chunk_id": "c1", "score": 0.9, "text": "Seoul is the capital city of Korea"}
                ],
                "citations": [{"doc_id": "doc-seoul", "chunk_id": "c1", "text": "Seoul is the capital city of Korea"}],
            }
        ],
    )

    first = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.scripts.rag_actual_eval",
            "--dataset",
            str(dataset),
            "--context-jsonl",
            str(context),
            "--top-k",
            "3",
            "--run-id",
            "cli_mapping_before",
            "--output-dir",
            str(report_root / "cli_mapping_before"),
            "--report-root",
            str(report_root),
            "--status-jsonl",
            str(status_path),
            "--append-registry",
            "--write-latest",
            "--resolve-expected-evidence",
            "--evidence-resolution-scope",
            "both",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr

    second = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.scripts.rag_actual_eval",
            "--dataset",
            str(dataset),
            "--context-jsonl",
            str(context),
            "--top-k",
            "3",
            "--run-id",
            "cli_mapping_after",
            "--output-dir",
            str(report_root / "cli_mapping_after"),
            "--report-root",
            str(report_root),
            "--status-jsonl",
            str(status_path),
            "--append-registry",
            "--write-latest",
            "--compare-to",
            "previous",
            "--resolve-expected-evidence",
            "--evidence-resolution-scope",
            "both",
            "--write-human-review-packet",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert second.returncode == 0, second.stderr
    summary = json.loads((report_root / "cli_mapping_after" / "report.json").read_text(encoding="utf-8"))
    assert summary["diagnostic_metrics"]["evidence_mapping_packet_enabled"] is True
    assert summary["comparison"]["target_run_id"] == "cli_mapping_before"
    assert output_file_names(report_root / "cli_mapping_after") == ["human_review_packet.csv", "report.json"]


def test_resolved_evidence_e2e_variant_still_requires_answer_judge_pass(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "방영 시기는?",
                "answerability": "answerable",
                "expected_answer": "2026년 4월",
                "expected_evidence": [{"text": "방영 시기는 2026년 4월", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "2025년 4월",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-date", "chunk_id": "c1", "score": 0.9, "text": "방영 시기는 2026년 4월"}],
                "citations": [{"doc_id": "doc-date", "chunk_id": "c1", "text": "방영 시기는 2026년 4월"}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "judge_fail",
        context_jsonl_path=context,
        top_k=1,
        run_id="judge_fail",
        resolve_expected_evidence=True,
        evidence_resolution_scope="both",
    )
    summary = json.loads(bundle.summary_path.read_text(encoding="utf-8"))

    assert summary["provisional_metrics"]["resolved_evidence_recall@1_provisional"]["numerator"] == 1
    assert summary["provisional_metrics"]["judged_answer_correctness_provisional"]["numerator"] == 0
    assert summary["provisional_metrics"]["e2e_rag_success_resolved_evidence_provisional"]["numerator"] == 0


def test_comparison_includes_new_evidence_resolution_metrics() -> None:
    def metric(name: str, numerator: int, denominator: int, tier: str = "provisional") -> dict:
        return {
            "name": name,
            "tier": tier,
            "numerator": numerator,
            "denominator": denominator,
            "score": None if denominator == 0 else round(numerator / denominator, 6),
        }

    previous = {
        "run_id": "previous",
        "top_k": 3,
        "strict_metrics": {},
        "provisional_metrics": {},
        "diagnostic_metrics": {},
    }
    current = {
        "run_id": "current",
        "top_k": 3,
        "strict_metrics": {},
        "provisional_metrics": {
            "resolved_evidence_available_rate": metric("resolved_evidence_available_rate", 1, 2),
            "resolved_evidence_recall@3_provisional": metric("resolved_evidence_recall@3_provisional", 1, 1),
            "citation_matches_resolved_evidence_precision_provisional": metric(
                "citation_matches_resolved_evidence_precision_provisional",
                1,
                1,
            ),
            "citation_matches_resolved_evidence_recall_provisional": metric(
                "citation_matches_resolved_evidence_recall_provisional",
                1,
                1,
            ),
            "e2e_rag_success_resolved_evidence_provisional": metric(
                "e2e_rag_success_resolved_evidence_provisional",
                0,
                1,
            ),
        },
        "diagnostic_metrics": {
            "expected_evidence_id_unresolved_count": 0,
            "expected_evidence_id_resolved_candidate_count": 1,
            "expected_evidence_resolution_candidate_count": 2,
        },
    }

    comparison = build_run_comparison(previous, current, target_label="previous")
    by_metric = {row["metric"]: row for row in comparison["rows"]}

    assert by_metric["resolved_evidence_available_rate"]["interpretation"] == "new metric"
    assert by_metric["resolved_evidence_available_rate"]["current"] == "1/2 (0.500000)"
    assert by_metric["expected_evidence_id_resolved_candidate_count"]["interpretation"] == "unavailable"


def test_cli_smoke_with_expected_evidence_resolution_both_scope(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    status_path = tmp_path / "status.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"text": "Seoul is the capital city of Korea", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-seoul", "chunk_id": "c1", "score": 0.9, "text": "Seoul is the capital city of Korea"}],
                "citations": [{"doc_id": "doc-seoul", "chunk_id": "c1", "text": "Seoul is the capital city of Korea"}],
            }
        ],
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.scripts.rag_actual_eval",
            "--dataset",
            str(dataset),
            "--context-jsonl",
            str(context),
            "--top-k",
            "3",
            "--run-id",
            "cli_resolution",
            "--output-dir",
            str(report_root / "cli_resolution"),
            "--report-root",
            str(report_root),
            "--status-jsonl",
            str(status_path),
            "--append-registry",
            "--write-latest",
            "--resolve-expected-evidence",
            "--evidence-resolution-scope",
            "both",
            "--count-medium-evidence-resolution",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads((report_root / "cli_resolution" / "report.json").read_text(encoding="utf-8"))
    assert summary["diagnostic_metrics"]["expected_evidence_resolution_enabled"] is True
    assert summary["artifact_paths"]["evidence_resolution_candidates_jsonl"] == ""
    assert summary["evidence_resolution_candidates"]
    assert output_file_names(report_root / "cli_resolution") == ["report.json"]


def test_report_generation_and_cli_smoke_with_tiny_fixture_dataset(tmp_path: Path) -> None:
    dataset = tmp_path / "tiny_gold.jsonl"
    context = tmp_path / "tiny_context.jsonl"
    output_dir = tmp_path / "rag_eval_output"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "What is the capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_answer_aliases": ["서울"],
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
                "tags": ["smoke"],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul 서울"}],
                "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul 서울"}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=3,
        run_id="unit_smoke",
        command="unit-test",
    )

    assert bundle.summary_path.exists()
    assert bundle.items_path.exists()
    assert bundle.markdown_path.exists()
    summary = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert summary["strict_metrics"]["e2e_rag_success_strict"]["score"] == 1.0
    assert summary["provisional_metrics"]["e2e_rag_success_provisional"]["score"] == 1.0
    assert summary["diagnostic_metric_details"]["answer_extracted_from_retrieved_context_rate"]["score"] == 1.0
    assert summary["diagnostic_metric_details"]["citation_points_to_retrieved_context_rate"]["score"] == 1.0
    assert summary["official_metric_input_rows"] == 0
    assert summary["official_metric_input_rows_created"] == 0
    assert summary["official_metric_input_rows_consumed"] == 0
    assert summary["protected_namespaces_touched"] == []
    assert summary["raw_prompt_payload_written"] is False
    assert summary["raw_response_payload_written"] is False
    assert summary["guardrails"]["official_metric"] is False
    assert summary["guardrails"]["promotion_evidence"] is False
    assert summary["guardrails"]["product_success_evidence_allowed"] is False
    assert summary["guardrails"]["live_readiness_claim"] is False
    assert summary["artifact_contract"]["output_mode"] == "single"
    assert "strict denominators" in summary["denominator_policy"].lower()
    assert "e2e_rag_success_provisional" in summary["provisional_metrics"]
    assert "answer_extracted_from_retrieved_context_rate" in summary["diagnostic_metric_details"]
    assert "not answer correctness" in summary["denominator_policy"]

    cli_output = tmp_path / "cli_output"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai.scripts.rag_actual_eval",
            "--dataset",
            str(dataset),
            "--context-jsonl",
            str(context),
            "--output-dir",
            str(cli_output),
            "--top-k",
            "3",
            "--run-id",
            "cli_smoke",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert output_file_names(cli_output) == ["report.json"]


def test_registry_latest_status_and_index_accumulate_without_promoting_metrics(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    status_path = tmp_path / "status.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul"}],
                "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul"}],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=report_root / "fixture_run",
        context_jsonl_path=context,
        top_k=3,
        run_id="fixture_run",
        command="unit-test accumulation",
        report_root=report_root,
        status_jsonl_path=status_path,
        append_registry=True,
        write_latest=True,
    )

    registry_path = report_root / "runs.jsonl"
    registry_rows = [json.loads(line) for line in registry_path.read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in registry_rows] == ["fixture_run"]
    assert registry_rows[0]["summary_json"] == bundle.summary_path.as_posix()
    assert registry_rows[0]["strict_metrics_summary"]["e2e_rag_success_strict"]["score"] == 1.0
    assert registry_rows[0]["guardrails"]["gold_mutation"] is False
    assert registry_rows[0]["guardrails"]["official_metric"] is False
    assert (report_root / "latest.json").exists()
    assert (report_root / "latest_fixture.json").exists()
    latest_fixture = json.loads((report_root / "latest_fixture.json").read_text(encoding="utf-8"))
    assert latest_fixture["run_id"] == "fixture_run"
    assert latest_fixture["summary_json"] == bundle.summary_path.as_posix()
    assert (report_root / "README.md").read_text(encoding="utf-8").startswith("# Actual RAG Eval Runs")

    status_rows = [json.loads(line) for line in status_path.read_text(encoding="utf-8").splitlines()]
    assert status_rows[0]["event_type"] == "actual_rag_eval_run"
    assert status_rows[0]["run_id"] == "fixture_run"
    assert status_rows[0]["guardrails"]["qrels_mutation"] is False
    assert status_rows[0]["short_result_interpretation"] == "baseline recorded; no comparison target supplied"


def test_repeated_run_id_does_not_overwrite_historical_artifacts(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "same_run"
    write_jsonl(
        dataset,
        [{"id": "q1", "query": "capital?", "answerability": "answerable", "expected_answer": "Seoul"}],
    )
    write_jsonl(context, [{"id": "q1", "generated_answer": "Seoul", "retrieved_contexts": [], "citations": []}])

    run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="same_run",
    )

    with pytest.raises(DatasetSchemaError, match="already contains actual RAG eval artifacts"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=output_dir,
            context_jsonl_path=context,
            top_k=1,
            run_id="same_run",
        )


def test_actual_rag_guardrail_validation_rejects_ambiguous_registry_inputs() -> None:
    valid = {
        "run_id": "guarded",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
    }
    validate_actual_rag_guardrails(valid)

    missing = dict(valid)
    missing.pop("official_metric_input_rows")
    with pytest.raises(DatasetSchemaError, match="official_metric_input_rows"):
        validate_actual_rag_guardrails(missing)

    nonzero = dict(valid, official_metric_input_rows_consumed=1)
    with pytest.raises(DatasetSchemaError, match="official_metric_input_rows_consumed"):
        validate_actual_rag_guardrails(nonzero)

    touched = dict(valid, protected_namespaces_touched=["ai/eval/eval_queries"])
    with pytest.raises(DatasetSchemaError, match="protected_namespaces_touched"):
        validate_actual_rag_guardrails(touched)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("official_metric_input_rows", 1),
        ("official_metric_input_rows_created", 1),
        ("official_metric_input_rows_consumed", 1),
        ("raw_prompt_payload_written", True),
        ("raw_response_payload_written", True),
    ],
)
def test_actual_rag_guardrail_validation_rejects_forbidden_top_level_flags(field: str, value) -> None:
    summary = {
        "run_id": "guarded",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
    }
    summary[field] = value

    with pytest.raises(DatasetSchemaError, match=field):
        validate_actual_rag_guardrails(summary)


@pytest.mark.parametrize(
    "field",
    [
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "answerability_label_mutation",
        "expected_answer_mutation",
        "expected_evidence_mutation",
        "denominator_mutation",
        "retriever_ranking_improvement",
        "official_metric",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_readiness_claim",
    ],
)
def test_actual_rag_guardrail_validation_rejects_forbidden_guardrail_flags(field: str) -> None:
    summary = {
        "run_id": "guarded",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
    }
    summary["guardrails"][field] = True

    with pytest.raises(DatasetSchemaError, match=field):
        validate_actual_rag_guardrails(summary)


def test_run_comparison_handles_deltas_missing_metrics_and_denominator_changes() -> None:
    def metric(name: str, numerator: int, denominator: int, tier: str = "provisional") -> dict:
        return {
            "name": name,
            "tier": tier,
            "numerator": numerator,
            "denominator": denominator,
            "score": None if denominator == 0 else round(numerator / denominator, 6),
        }

    previous = {
        "run_id": "previous",
        "top_k": 10,
        "strict_metrics": {
            "exact_or_alias_answer_correctness": metric("exact_or_alias_answer_correctness", 1, 2, "strict"),
            "evidence_recall@10": metric("evidence_recall@10", 1, 2, "strict"),
            "citation_precision": metric("citation_precision", 1, 1, "strict"),
        },
        "provisional_metrics": {
            "judged_answer_correctness_provisional": metric("judged_answer_correctness_provisional", 1, 2),
            "weak_evidence_match_recall@10": metric("weak_evidence_match_recall@10", 1, 2),
        },
        "diagnostic_metric_details": {
            "answer_extracted_from_retrieved_context_rate": metric(
                "answer_extracted_from_retrieved_context_rate",
                1,
                2,
                "diagnostic",
            )
        },
        "diagnostic_metrics": {"retrieval_empty_rate": 0.5, "pipeline_error_count": 2},
    }
    current = {
        "run_id": "current",
        "top_k": 10,
        "strict_metrics": {
            "exact_or_alias_answer_correctness": metric("exact_or_alias_answer_correctness", 2, 4, "strict"),
            "evidence_recall@10": metric("evidence_recall@10", 2, 2, "strict"),
            "citation_precision": metric("citation_precision", 1, 1, "strict"),
            "citation_recall": metric("citation_recall", 0, 0, "strict"),
        },
        "provisional_metrics": {
            "judged_answer_correctness_provisional": metric("judged_answer_correctness_provisional", 2, 2),
            "weak_evidence_match_recall@10": metric("weak_evidence_match_recall@10", 1, 2),
            "e2e_rag_success_provisional": metric("e2e_rag_success_provisional", 1, 2),
        },
        "diagnostic_metric_details": {
            "answer_extracted_from_retrieved_context_rate": metric(
                "answer_extracted_from_retrieved_context_rate",
                2,
                2,
                "diagnostic",
            )
        },
        "diagnostic_metrics": {
            "retrieval_empty_rate": 0.25,
            "pipeline_error_count": 1,
            "expected_evidence_id_unresolved_count": 3,
        },
    }

    comparison = build_run_comparison(previous, current, target_label="previous")
    by_metric = {row["metric"]: row for row in comparison["rows"]}

    assert comparison["guardrails"]["official_metric"] is False
    assert comparison["guardrails"]["promotion_evidence"] is False
    assert comparison["interpretation_policy"] == "nonprod_diagnostic_comparison_only"
    assert by_metric["judged_answer_correctness_provisional"]["delta"] == 0.5
    assert by_metric["judged_answer_correctness_provisional"]["interpretation"] == "improved"
    assert by_metric["weak_evidence_match_recall@10"]["interpretation"] == "unchanged"
    assert by_metric["exact_or_alias_answer_correctness"]["interpretation"] == "denominator changed"
    assert by_metric["citation_recall"]["interpretation"] == "unavailable"
    assert by_metric["retrieval_empty_rate"]["interpretation"] == "improved"
    assert by_metric["pipeline_error_count"]["interpretation"] == "improved"
    assert by_metric["expected_evidence_id_unresolved_count"]["interpretation"] == "unavailable"
    assert by_metric["answer_extracted_from_retrieved_context_rate"]["interpretation"] == "diagnostic only"


def test_repo_current_bm25_adapter_does_not_use_raw_gold_or_xlsx_shortcuts() -> None:
    source = inspect.getsource(RepoCurrentBm25Adapter)
    forbidden_fragments = [
        "openpyxl",
        "load_workbook",
        "formula",
        "normalized_value",
        "target_locator",
        "gold_locator",
        "query_id",
        "case_id",
        "expected_answer",
        "expected_evidence",
    ]

    for fragment in forbidden_fragments:
        assert fragment not in source


def test_expected_evidence_resolver_does_not_use_raw_xlsx_or_gold_locator_shortcuts() -> None:
    source = inspect.getsource(ExpectedEvidenceResolver)
    forbidden_fragments = [
        "openpyxl",
        "load_workbook",
        "formula",
        "normalized_value",
        "target_locator",
        "gold_locator",
        "query_id",
        "case_id",
    ]

    for fragment in forbidden_fragments:
        assert fragment not in source


def test_markdown_report_includes_previous_run_comparison_section(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context_before = tmp_path / "context_before.jsonl"
    context_after = tmp_path / "context_after.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
            }
        ],
    )
    write_jsonl(context_before, [{"id": "q1", "generated_answer": "", "retrieved_contexts": [], "citations": []}])
    write_jsonl(
        context_after,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul"}],
                "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul"}],
            }
        ],
    )

    previous = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "before",
        context_jsonl_path=context_before,
        top_k=1,
        run_id="before",
        output_mode="legacy",
    )
    current = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "after",
        context_jsonl_path=context_after,
        top_k=1,
        run_id="after",
        comparison_summary=previous.summary,
        comparison_target="previous",
        output_mode="legacy",
    )

    report = current.markdown_path.read_text(encoding="utf-8")
    summary = json.loads(current.summary_path.read_text(encoding="utf-8"))
    assert "## Previous Run Comparison" in report
    assert "| Metric | Tier | Previous | Current | Delta | Interpretation |" in report
    assert summary["comparison"]["target_run_id"] == "before"
    assert summary["comparison"]["rows"]


def test_run_id_helper_is_filesystem_safe_and_collision_safe(tmp_path: Path) -> None:
    report_root = tmp_path / "reports" / "rag_eval"
    dataset = tmp_path / "gold_queries_text_namu_v2_1_question_gold_v2.csv"
    dataset.write_text("id,query\n", encoding="utf-8")

    explicit = make_actual_rag_run_id(dataset, explicit_run_id="manual_run_01", report_root=report_root)
    assert explicit == "manual_run_01"
    with pytest.raises(DatasetSchemaError, match="filesystem-safe"):
        make_actual_rag_run_id(dataset, explicit_run_id="../bad", report_root=report_root)

    first = make_actual_rag_run_id(dataset, generated_at="2026-06-10T01:02:03Z", report_root=report_root)
    (report_root / first).mkdir(parents=True)
    (report_root / first / "rag_eval_summary.json").write_text("{}", encoding="utf-8")
    second = make_actual_rag_run_id(dataset, generated_at="2026-06-10T01:02:03Z", report_root=report_root)
    assert first == "actual_rag_eval_text_gold_20260610_010203"
    assert second == "actual_rag_eval_text_gold_20260610_010203_02"


def test_latest_pointer_can_be_written_without_registry_append(tmp_path: Path) -> None:
    report_root = tmp_path / "reports" / "rag_eval"
    summary = {
        "run_id": "manual",
        "generated_at": "2026-06-10T01:02:03Z",
        "dataset_path": "ai/eval/eval_queries/gold_queries_text_namu_v2_1_question_gold_v2.csv",
        "output_dir": "reports/rag_eval/manual",
        "artifact_paths": {
            "summary_json": "reports/rag_eval/manual/rag_eval_summary.json",
            "markdown_report": "reports/rag_eval/manual/rag_eval_report.md",
            "items_jsonl": "reports/rag_eval/manual/rag_eval_items.jsonl",
        },
        "schema_version": "actual_rag_eval.v1",
        "run_kind": "actual_rag_eval_metric_generation_nonprod",
        "total_item_count": 6,
        "top_k": 10,
        "judge_mode": "heuristic",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
    }

    pointers = write_latest_pointers(summary, report_root=report_root)

    assert (report_root / "latest.json") in pointers
    assert (report_root / "latest_text_gold.json") in pointers
    assert json.loads((report_root / "latest_text_gold.json").read_text(encoding="utf-8"))["run_id"] == "manual"


def test_status_event_append_is_compact_and_guardrailed(tmp_path: Path) -> None:
    status_path = tmp_path / "status.jsonl"
    summary = {
        "run_id": "run",
        "generated_at": "2026-06-10T01:02:03Z",
        "dataset_path": "fixture_gold.jsonl",
        "output_dir": "reports/rag_eval/run",
        "total_item_count": 1,
        "strict_metrics": {},
        "provisional_metrics": {},
        "diagnostic_metrics": {"pipeline_error_count": 0, "retrieval_empty_rate": 0.0},
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
    }

    event = append_actual_rag_status_event(summary, status_jsonl_path=status_path)

    assert event["event_type"] == "actual_rag_eval_run"
    assert event["next_suggested_repair_target"] == "monitor_accumulated_actual_rag_eval_runs"
    assert json.loads(status_path.read_text(encoding="utf-8"))["run_id"] == "run"


def test_cli_appends_registry_latest_status_and_compares_to_previous(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context_before = tmp_path / "context_before.jsonl"
    context_after = tmp_path / "context_after.jsonl"
    report_root = tmp_path / "reports" / "rag_eval"
    status_path = tmp_path / "status.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "capital?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul", "required": True}],
            }
        ],
    )
    write_jsonl(context_before, [{"id": "q1", "generated_answer": "", "retrieved_contexts": [], "citations": []}])
    write_jsonl(
        context_after,
        [
            {
                "id": "q1",
                "generated_answer": "Seoul",
                "retrieved_contexts": [{"rank": 1, "doc_id": "doc-a", "chunk_id": "c1", "score": 1.0, "text": "Seoul"}],
                "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul"}],
            }
        ],
    )

    base_cmd = [
        sys.executable,
        "-m",
        "ai.scripts.rag_actual_eval",
        "--dataset",
        str(dataset),
        "--top-k",
        "1",
        "--append-registry",
        "--write-latest",
        "--report-root",
        str(report_root),
        "--status-jsonl",
        str(status_path),
    ]
    first = subprocess.run(
        [
            *base_cmd,
            "--context-jsonl",
            str(context_before),
            "--run-id",
            "cli_previous",
            "--output-dir",
            str(report_root / "cli_previous"),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )
    second = subprocess.run(
        [
            *base_cmd,
            "--context-jsonl",
            str(context_after),
            "--run-id",
            "cli_current",
            "--output-dir",
            str(report_root / "cli_current"),
            "--compare-to",
            "previous",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        check=False,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    registry_rows = [json.loads(line) for line in (report_root / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in registry_rows] == ["cli_previous", "cli_current"]
    assert json.loads((report_root / "latest_fixture.json").read_text(encoding="utf-8"))["run_id"] == "cli_current"
    status_rows = [json.loads(line) for line in status_path.read_text(encoding="utf-8").splitlines()]
    assert [row["run_id"] for row in status_rows] == ["cli_previous", "cli_current"]
    current_summary = json.loads((report_root / "cli_current" / "report.json").read_text(encoding="utf-8"))
    assert current_summary["comparison"]["target_run_id"] == "cli_previous"
    assert current_summary["comparison"]["rows"]
    assert output_file_names(report_root / "cli_current") == ["report.json"]
