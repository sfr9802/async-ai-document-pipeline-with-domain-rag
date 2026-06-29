from __future__ import annotations

import csv
import hashlib
import json
import inspect
import os
import sqlite3
import subprocess
import sys
import types
from pathlib import Path

import pytest

from ai.eval import actual_rag_eval
from ai.eval.actual_rag_eval import (
    DatasetSchemaError,
    ExpectedEvidenceResolver,
    EvidenceResolutionConfig,
    FakeDeterministicEmbeddingProvider,
    FakeVectorAdapter,
    RepoCurrentBm25Adapter,
    SourceNativeCorpusLoader,
    SourceNativeHybridAdapter,
    append_actual_rag_status_event,
    build_backend_comparison_metrics,
    build_parser,
    build_corpus_coverage_audit_report,
    build_legacy_real_rag_quality_gate_report,
    build_evidence_gate_summary,
    build_source_native_legacy_cleanup_report,
    apply_selected_evidence_composer_to_outputs,
    apply_evidence_gate_to_outputs,
    build_source_native_bge_m3_index_artifact,
    build_run_comparison,
    answer_correct,
    abstains,
    heuristic_judge_answer,
    load_eval_dataset,
    make_actual_rag_run_id,
    normalize_answer_text,
    _public_report_row,
    _report_path_value,
    resolve_quality_gate_baseline_report,
    run_eval_from_paths,
    score_rag_eval_items,
    select_composer_evidence,
    validate_evidence_package_for_gate,
    validate_actual_rag_guardrails,
    write_source_native_legacy_cleanup_report,
    write_latest_pointers,
)
from ai.eval.weaviate_source_atom import (
    BgeM3EmbeddingBuilder,
    WEAVIATE_SOURCE_ATOM_REQUIRED_PROPERTIES,
    WEAVIATE_SOURCE_ATOM_V2_EXTRA_PROPERTIES,
    FakeWeaviateSourceAtomClient,
    WeaviateSourceAtomAdapter,
    WeaviateSourceAtomClient,
    WeaviateSourceAtomConfig,
    WeaviateSourceAtomIndexer,
    WeaviateUnavailableError,
    _write_json_atomic,
    build_default_weaviate_adapter,
    build_weaviate_source_atom_schema,
    derive_weaviate_route_taxonomy,
    plan_weaviate_query_variants,
    plan_weaviate_retrieval_route,
    source_atom_record_from_mapping,
)
import ai.scripts.rag_weaviate_source_atom_index as weaviate_index_script
from ai.scripts.rag_weaviate_source_atom_index import build_parser as build_weaviate_index_parser

from ai.tests.actual_rag_eval_helpers import (
    FakeBgeM3EmbeddingProvider,
    FakeWeaviateBgeM3EmbeddingProvider,
    output_file_names,
    weaviate_source_atom_record,
    write_jsonl,
)

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
    assert "prompt" not in summary["judge_config"]
    assert summary["judge_config"]["prompt_sha256"]


def test_public_report_row_strips_raw_prompt_response_payloads_recursively() -> None:
    public = _public_report_row(
        {
            "id": "row-1",
            "generated_answer": "answer",
            "raw_prompt_payload": {"messages": ["secret prompt"]},
            "raw_response_payload": {"choices": ["secret response"]},
            "rawPromptPayload": {"messages": ["secret camel prompt"]},
            "raw_response_sha256": "abc123",
            "diagnostics": {
                "raw_prompt": "secret prompt",
                "rawPromptText": "secret camel raw prompt",
                "rawResponseText": "secret camel raw response",
                "llmPrompt": "secret llm prompt",
                "llmResponse": "secret llm response",
                "model_response_payload": {"text": "secret response"},
                "responseText": "secret bare response",
                "raw_response_sha256": "def456",
                "safe": [{"prompt_payload": "secret prompt"}, {"kept": True}],
            },
            "_generated_answer_before_evidence_gate": "internal answer",
        }
    )

    encoded = json.dumps(public, ensure_ascii=False)
    assert "raw_prompt_payload" not in encoded
    assert "raw_response_payload" not in encoded
    assert "secret prompt" not in encoded
    assert "secret response" not in encoded
    assert "secret camel" not in encoded
    assert "secret llm" not in encoded
    assert "secret bare response" not in encoded
    assert "_generated_answer_before_evidence_gate" not in public
    assert public["raw_response_sha256"] == "abc123"
    assert public["diagnostics"]["raw_response_sha256"] == "def456"
    assert public["diagnostics"]["safe"] == [{}, {"kept": True}]


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
            "citations": [{"doc_id": "doc-a", "chunk_id": "c1", "text": "Seoul is the capital."}],
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
    assert summary["strict_metrics"]["citation_precision"]["denominator"] == 0
    assert summary["strict_metrics"]["citation_recall"]["denominator"] == 0
    assert summary["strict_metrics"]["citation_precision"]["exclusion_reasons"] == {
        "answerability_unknown_not_in_citation_denominator": 1
    }
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


def test_full_corpus_expected_evidence_resolution_finds_source_native_candidate_without_retrieval_leakage(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "full_corpus_resolution"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-full-corpus",
                "query": "Project Orion status dashboard",
                "answerability": "unknown",
                "expected_answer": "2026-04-12",
                "expected_evidence": [
                    {
                        "text": "Mercury launch window opens on 2026-04-12",
                        "required": True,
                    }
                ],
            }
        ],
    )
    source_units = [
        {
            "unit_id": "src-distractor",
            "source_atom_id": "srcatom-distractor",
            "doc_id": "doc-distractor",
            "chunk_id": "chunk-distractor",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Dashboard",
            "text": "Project Orion status dashboard has no launch-window answer.",
            "surface": "source_atom",
            "text_sha256": "src-distractor-sha",
            "metadata": {},
        },
        {
            "unit_id": "src-target",
            "source_atom_id": "srcatom-target",
            "evidence_bundle_id": "bundle-target",
            "doc_id": "doc-target",
            "chunk_id": "chunk-target",
            "source_family": "XLSX",
            "title": "Mercury Launch",
            "section": "Schedule",
            "text": (
                "sheet=Schedule | display_value=Mercury launch window opens on 2026-04-12. | "
                "normalized_value=SECRET_NORMALIZED_VALUE | formula=SECRET_FORMULA"
            ),
            "surface": "evidence_bundle",
            "text_sha256": "src-target-sha",
            "metadata": {},
        },
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=1,
        run_id="full_corpus_resolution",
        retrieval_surface="auto",
        retrieval_backend="bm25",
        source_native_units=source_units,
        evidence_resolution_scope="full-corpus",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    assert report["retrieval_surface"]["selected"] == "source_native"
    assert report["items"][0]["retrieved_contexts"][0]["doc_id"] == "doc-distractor"
    assert "gold_missing_answerability" in report["items"][0]["canonical_failure_labels"]
    assert "metric_not_applicable" in report["items"][0]["canonical_failure_labels"]
    diagnostics = report["diagnostic_metrics"]
    assert "gold_missing_answerability" in diagnostics["canonical_failure_labels"]
    assert diagnostics["canonical_failure_category_counts"]["gold_missing_answerability"] == 1
    assert diagnostics["expected_evidence_resolution_scope"] == "full-corpus"
    assert diagnostics["expected_evidence_full_corpus_candidate_count"] >= 1
    assert diagnostics["expected_evidence_full_corpus_high_confidence_count"] == 1
    assert diagnostics["expected_evidence_full_corpus_resolved_candidate_count"] == 1
    assert diagnostics["expected_evidence_full_corpus_unresolved_count"] == 0
    assert diagnostics["gold_or_qrels_mutation"] is False
    assert diagnostics["human_decision_fields_filled_by_codex"] is False
    assert report["gold_or_qrels_mutation"] is False
    assert report["human_decision_fields_filled_by_codex"] is False
    assert report["expected_evidence_resolution"]["scope"] == "full-corpus"
    assert report["expected_evidence_resolution"]["full_corpus_candidate_count"] >= 1

    candidate = report["evidence_resolution_candidates"][0]["candidates"][0]
    assert candidate["source"] == "full_corpus_source_native"
    assert candidate["doc_id"] == "doc-target"
    assert candidate["chunk_id"] == "chunk-target"
    assert candidate["source_atom_id"] == "srcatom-target"
    assert candidate["evidence_bundle_id"] == "bundle-target"
    assert candidate["candidate_text_hash"]
    assert candidate["candidate_full_text_hash"] == candidate["candidate_text_hash"]
    encoded_candidates = json.dumps(report["evidence_resolution_candidates"], ensure_ascii=False)
    assert "normalized_value=" not in encoded_candidates
    assert "SECRET_NORMALIZED_VALUE" not in encoded_candidates
    assert "formula=" not in encoded_candidates
    assert "SECRET_FORMULA" not in encoded_candidates
    assert candidate["normalized_match_info"]["normalized_expected_in_candidate"] is True
    assert candidate["match_type"] in {"exact_match", "normalized_match"}
    assert candidate["collision_warning"] == ""
    assert candidate["missing_numeric_or_date_anchors"] == []
    assert report["guardrails"]["expected_fields_used_for_candidate_generation"] is False
    assert report["guardrails"]["qrels_used_for_candidate_generation"] is False
    assert report["guardrails"]["gold_fields_used_for_candidate_generation"] is False
    assert set(report["strict_metrics"]).issubset(set(report["metric_tiers"]["strict"]))
    assert set(report["provisional_metrics"]).issubset(set(report["metric_tiers"]["provisional"]))
    assert set(report["inferred_answerable_metrics"]).issubset(set(report["metric_tiers"]["inferred_answerable"]))
    assert set(report["diagnostic_metrics"]).issubset(set(report["metric_tiers"]["diagnostic"]))
    assert set(report["diagnostic_metric_details"]).issubset(set(report["metric_tiers"]["diagnostic"]))


def test_full_corpus_review_only_scope_ignores_retrieved_context_candidates(tmp_path: Path) -> None:
    dataset = tmp_path / "resolver_scope_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "scope",
                "query": "Mercury launch window",
                "answerability": "unknown",
                "expected_answer": "2026-04-12",
                "expected_evidence": [{"text": "Mercury launch window opens on 2026-04-12", "required": True}],
            }
        ],
    )
    item = load_eval_dataset(dataset)[0]
    resolver = ExpectedEvidenceResolver(EvidenceResolutionConfig(scope="full-corpus-review-only", max_candidates=3))

    result = resolver.resolve_item(
        item,
        retrieved_contexts=[
            {
                "rank": 1,
                "doc_id": "doc-retrieved",
                "chunk_id": "chunk-retrieved",
                "score": 0.99,
                "text": "Mercury launch window opens on 2026-04-12.",
            }
        ],
        index_candidates=[
            {
                "rank": 99,
                "doc_id": "doc-full-corpus",
                "chunk_id": "chunk-full-corpus",
                "score": 0.91,
                "text": "Mercury launch window opens on 2026-04-12.",
                "_resolution_source": "full_corpus_source_native",
            }
        ],
    )

    selected = result["rows"][0]["selected_candidate"]
    assert selected["doc_id"] == "doc-full-corpus"
    assert selected["source"] == "full_corpus_source_native"
    assert all(
        candidate["doc_id"] != "doc-retrieved"
        for candidate in result["rows"][0]["candidates"]
    )


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
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert rows
    required_columns = {
        "query_id",
        "query",
        "expected_answer",
        "expected_evidence_text",
        "candidate_doc_id",
        "candidate_chunk_id",
        "candidate_source_atom_id",
        "candidate_evidence_bundle_id",
        "candidate_text_preview",
        "candidate_text_hash",
        "candidate_score",
        "candidate_confidence",
        "match_type",
        "match_reasons",
        "anchor_hits",
        "missing_numeric_or_date_anchors",
        "collision_warning",
        "machine_recommendation",
        "human_accept",
        "human_reject_reason",
        "human_expected_answer_override",
        "human_expected_evidence_override",
        "human_answerability_label",
        "human_notes",
    }
    assert required_columns.issubset(set(reader.fieldnames or []))
    assert all(row["human_mapping_decision"] == "" for row in rows)
    for row in rows:
        for field in (
            "human_accept",
            "human_reject_reason",
            "human_expected_answer_override",
            "human_expected_evidence_override",
            "human_answerability_label",
            "human_notes",
        ):
            assert row[field] == ""


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
    source_native_loader = report["index_retrieval_config"]["source_native"]["source_native_loader"]
    assert "searchunit_searchview_fallback" not in source_native_loader["preferred_surface_order"]
    assert report["surface_migration"]["selected_surface"] == "source_native"
    assert report["surface_migration"]["searchunit_searchview_candidate_surface_enabled"] is False
    assert report["surface_migration"]["auto_fallback_to_searchunit_searchview"] is False
    assert report["surface_migration"]["deprecation_decision"] == "demote_from_routine_actual_rag_candidate_surface"
    assert report["surface_migration"]["remaining_failure_target"] == "source_native_ranking_query_formulation"
    assert report["legacy_cleanup"] == {
        "enabled": True,
        "searchunit_searchview_routine_candidate_surface_enabled": False,
        "searchunit_searchview_role": "explicit_legacy_comparison_debug_only",
        "auto_fallback_to_searchunit_searchview": False,
        "source_native_hard_switch_preserved": True,
    }
    assert report["artifact_cleanup"]["output_mode_single_report_json_only"] is True
    assert report["artifact_cleanup"]["legacy_sidecars_routine_disabled"] is True
    assert report["artifact_cleanup"]["human_review_packet_exception_preserved"] is True
    assert report["artifact_cleanup"]["raw_prompt_payload_written"] is False
    assert report["artifact_cleanup"]["raw_response_payload_written"] is False
    assert report["runner_alias_cleanup"]["current_moved"] is False
    assert "--legacy-surface-comparison" in report["runner_alias_cleanup"]["aliases_kept_check_only"]
    assert report["diagnostic_metrics"]["source_native_expected_evidence_text_presence_rate"] == 1.0
    assert report["diagnostic_metrics"]["searchunit_expected_evidence_text_presence_rate"] is None
    row = report["items"][0]
    assert row["retrieval_surface_comparison"]["selected"]["surface"] == "source_native"
    assert row["retrieval_surface_comparison"]["source_native"]["expected_evidence_retrieved"] is True
    assert row["retrieval_surface_comparison"]["searchunit_searchview"]["comparison_enabled"] is False
    assert row["retrieval_surface_comparison"]["searchunit_searchview"]["candidate_count"] is None
    assert report["guardrails"]["gold_fields_used_for_candidate_generation"] is False


def test_source_native_legacy_cleanup_report_records_inventory_guardrails_and_debt(tmp_path: Path) -> None:
    routine_summary = {
        "run_id": "routine_source_native",
        "retrieval_surface": {
            "requested": "auto",
            "selected": "source_native",
            "source_native_available": True,
            "source_native_selected": True,
            "searchunit_searchview_candidate_surface_enabled": False,
            "auto_fallback_to_searchunit_searchview": False,
        },
        "artifact_contract": {
            "output_mode": "single",
            "single_artifact_default": True,
            "legacy_sidecars_written": False,
            "human_review_packet_exception": False,
        },
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
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
    report_path = (
        tmp_path
        / "ai"
        / "eval"
        / "reports"
        / "rag-ingestion"
        / "runs"
        / "actual_rag_eval_source_native_legacy_cleanup_nonprod"
        / "report.json"
    )

    report = write_source_native_legacy_cleanup_report(
        report_path,
        routine_summary=routine_summary,
        changed_files=[
            "ai/eval/actual_rag_eval.py",
            "ai/tests/test_actual_rag_eval_metric_generation.py",
            "docs/rag-ingestion-progress.md",
        ],
        deleted_files=[],
        generated_at="2026-06-11T00:00:00+00:00",
    )

    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted == report
    assert output_file_names(report_path.parent) == ["report.json"]
    assert report["run_id"] == "actual_rag_eval_source_native_legacy_cleanup_nonprod"
    assert report["cleanup_decisions"]["deletions"] == []
    assert report["legacy_cleanup"]["source_native_hard_switch_preserved"] is True
    assert report["artifact_cleanup"]["output_mode_single_report_json_only"] is True
    assert report["artifact_cleanup"]["legacy_sidecars_routine_disabled"] is True
    assert report["runner_alias_cleanup"]["current_moved"] is False
    assert report["runner_alias_cleanup"]["aliases_removed"] == []
    assert report["protected_namespaces_touched"] == []
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["answerability_label_mutation"] is False
    assert report["guardrails"]["expected_answer_mutation"] is False
    assert report["guardrails"]["expected_evidence_mutation"] is False
    assert report["guardrails"]["denominator_mutation"] is False
    assert report["guardrails"]["current_moved"] is False
    assert report["classification_counts"]["EXPLICIT_LEGACY_DEBUG_KEEP"] >= 1
    assert report["classification_counts"]["EXPLICIT_LEGACY_COMPARISON_KEEP"] >= 1
    assert report["classification_counts"]["PROTECTED_HOLD"] >= 1
    assert report["classification_counts"]["DOCS_ONLY_UPDATE"] >= 1
    assert report["classification_counts"]["DEPRECATE_FAIL_CLOSED"] >= 1
    inventory_categories = {entry["category"] for entry in report["inventory"]}
    assert {
        "searchunit_searchview_runtime_reference",
        "searchunit_searchview_test_reference",
        "searchunit_searchview_docs_reference",
        "actual_rag_sidecar_writer",
        "legacy_report_writer",
        "legacy_cli_alias",
        "stale_generated_ignored_artifact",
        "protected_namespace_reference",
    }.issubset(inventory_categories)
    assert report["remaining_debt"] == [
        "source_native_ranking_query_formulation",
        "bge_m3_artifacts_held_read_only_future_remeasurement_when_explicitly_opened_or_not_current",
        "extractive_v1_answer_generation_replacement",
    ]


def test_source_native_legacy_cleanup_report_builder_validates_guardrails() -> None:
    unsafe_summary = {
        "run_id": "unsafe",
        "retrieval_surface": {"selected": "source_native"},
        "artifact_contract": {"output_mode": "single"},
        "official_metric_input_rows": 1,
        "guardrails": {"gold_mutation": False},
    }

    with pytest.raises(DatasetSchemaError, match="official_metric_input_rows"):
        build_source_native_legacy_cleanup_report(routine_summary=unsafe_summary)


def test_legacy_searchunit_comparison_requires_explicit_debug_flag(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native_legacy_comparison"
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
            "bm25_text": "needle answer appears in legacy searchunit evidence",
            "embedding_text": "needle answer appears in legacy searchunit evidence",
            "metadata": {"source_safe_id": "legacy-doc", "source_text_sha256": "legacy-sha"},
        }
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=1,
        run_id="source_native_legacy_comparison",
        retrieval_surface="auto",
        retrieval_backend="bm25",
        source_native_units=source_units,
        searchunit_units=searchunit_units,
        legacy_surface_comparison=True,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    assert report["surface_migration"]["searchunit_searchview_candidate_surface_enabled"] is False
    assert report["surface_migration"]["legacy_comparison_enabled"] is True
    row = report["items"][0]
    assert row["retrieval_surface_comparison"]["searchunit_searchview"]["comparison_enabled"] is True
    assert row["retrieval_surface_comparison"]["searchunit_searchview"]["candidate_count"] == 1
    assert report["diagnostic_metrics"]["searchunit_retrieval_empty_rate"] == 0.0


def test_searchunit_candidate_surface_requires_legacy_debug_flag(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    write_jsonl(dataset, [{"id": "q1", "query": "legacy debug", "answerability": "unknown"}])
    searchunit_units = [
        {
            "payload_id": "legacy-1",
            "search_unit_id": "legacy-chunk",
            "search_view_id": "legacy-view",
            "source_family": "TEXT",
            "bm25_text": "legacy debug candidate",
            "embedding_text": "legacy debug candidate",
            "metadata": {"source_safe_id": "legacy-doc", "source_text_sha256": "legacy-sha"},
        }
    ]

    with pytest.raises(DatasetSchemaError, match="legacy/debug only"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=tmp_path / "reports" / "rag_eval" / "searchunit_blocked",
            top_k=1,
            run_id="searchunit_blocked",
            retrieval_surface="searchunit-searchview",
            retrieval_backend="bm25",
            searchunit_units=searchunit_units,
        )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "reports" / "rag_eval" / "searchunit_debug",
        top_k=1,
        run_id="searchunit_debug",
        retrieval_surface="searchunit-searchview",
        retrieval_backend="bm25",
        searchunit_units=searchunit_units,
        legacy_surface_comparison=True,
    )
    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(tmp_path / "reports" / "rag_eval" / "searchunit_debug") == ["report.json"]
    assert report["retrieval_surface"]["selected"] == "searchunit_searchview"
    assert report["retrieval_surface"]["searchunit_searchview_role"] == "legacy_comparison_debug_only"
    assert report["retrieval_surface"]["searchunit_searchview_candidate_surface_enabled"] is True
    assert report["source_native_layered_retrieval"]["enabled"] is False
    assert report["source_native_layered_retrieval"]["legacy_searchunit_comparison_enabled"] is True


def test_source_native_units_reject_forbidden_candidate_generation_fields(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    write_jsonl(dataset, [{"id": "q1", "query": "source-native safe", "answerability": "unknown"}])

    with pytest.raises(DatasetSchemaError, match="forbidden source-native candidate fields"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=tmp_path / "reports" / "rag_eval" / "source_native_forbidden",
            top_k=1,
            run_id="source_native_forbidden",
            retrieval_surface="auto",
            retrieval_backend="bm25",
            source_native_units=[
                {
                    "unit_id": "src-unit-bad",
                    "source_atom_id": "srcatom-bad",
                    "doc_id": "source-doc",
                    "chunk_id": "source-bad",
                    "source_family": "TEXT",
                    "text": "source-native safe text",
                    "surface": "source_atom",
                    "text_sha256": "src-bad-sha",
                    "expected_answer": "oracle token",
                }
            ],
        )


def test_source_native_vector_index_audit_records_invocation_hydration_and_nonoracle(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native_vector_audit"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-vector",
                "query": "Project Orion Atlas launch April 2026",
                "answerability": "answerable",
                "expected_answer": "April 2026",
                "expected_evidence": [{"text": "Project Orion Atlas launch is scheduled for April 2026", "required": True}],
            }
        ],
    )
    source_units = [
        {
            "unit_id": "src-vector-1",
            "source_atom_id": "srcatom-vector-1",
            "doc_id": "source-doc",
            "chunk_id": "source-vector-1",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Launch",
            "text": "Project Orion Atlas launch is scheduled for April 2026.",
            "surface": "source_atom",
            "text_sha256": "src-vector-1-sha",
            "metadata": {},
        },
        {
            "unit_id": "src-vector-2",
            "source_atom_id": "srcatom-vector-2",
            "doc_id": "source-doc",
            "chunk_id": "source-vector-2",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Background",
            "text": "Project Orion background context for semantic vector retrieval.",
            "surface": "source_atom",
            "text_sha256": "src-vector-2-sha",
            "metadata": {},
        },
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=2,
        run_id="source_native_vector_audit",
        retrieval_surface="auto",
        retrieval_backend="hybrid",
        source_native_units=source_units,
        source_native_embedding_provider=FakeDeterministicEmbeddingProvider(),
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    audit = report["vector_index_audit"]
    assert audit["enabled"] is True
    assert audit["status"] == "connected_semantic_quality_unproven"
    assert audit["vector_surface"] == "source_native"
    assert audit["vector_backend"] == "python_deterministic_test"
    assert audit["external_vector_db_configured"] is False
    assert audit["external_vector_db_invoked"] is False
    assert audit["embedding_model"] == "deterministic-test-source-native-vector"
    assert audit["embedding_dim"] == 16
    assert audit["gpu_used_for_embedding"] is False
    assert audit["bge_m3_replacement_needed"] is True
    assert audit["index_integrity_passed"] is True
    assert audit["query_invocation_passed"] is True
    assert audit["hydration_passed"] is True
    assert audit["hybrid_comparison_available"] is True
    assert audit["semantic_quality_claim_allowed"] is False
    assert audit["id_map_count"] == audit["source_native_unit_count"] == 2
    assert audit["id_map_matches_source_native_units"] is True
    assert audit["faiss_index_ntotal"] == audit["id_map_count"]
    assert audit["faiss_ntotal_matches_id_map"] is True
    assert audit["faiss_row_id_mismatch_count"] == 0
    assert audit["raw_local_paths_exposed"] is False
    assert audit["target_presence_diagnostics"]["expected_fields_used_for_candidate_generation"] is False
    assert audit["target_presence_diagnostics"]["gold_fields_used_for_candidate_generation"] is False
    assert audit["target_presence_diagnostics"]["qrels_used_for_candidate_generation"] is False
    assert audit["target_presence_diagnostics"]["ids_used_for_candidate_generation"] is False
    assert audit["target_presence_diagnostics"]["baseline_topk_used_for_candidate_generation"] is False
    assert audit["target_presence_diagnostics"]["expected_fields_used_for_post_retrieval_diagnostics"] is True
    assert audit["target_presence_diagnostics"]["vector_expected_anchor_recall@k_diagnostic"] >= 0.0
    assert report["final_rag_target"]["retrieval_surface"] == "source_native"
    assert report["final_rag_target"]["evidence_truth"] == "SourceAtom/EvidenceBundle"
    assert report["final_rag_target"]["searchunit_searchview_role"] == "legacy_comparison_debug_only"
    row_comparison = report["items"][0]["retrieval_backend_comparison"]
    assert row_comparison["bm25_top_k_count"] >= 1
    assert row_comparison["vector_top_k_count"] >= 1
    assert row_comparison["hybrid_top_k_count"] >= 1
    assert row_comparison["bm25_vector_topk_overlap_count"] >= 0
    assert row_comparison["hybrid_contains_vector_only_candidate_count"] >= 0
    assert row_comparison["hybrid_contains_bm25_only_candidate_count"] >= 0
    assert row_comparison["vector_contribution_to_selected_topk_count"] >= 0
    assert row_comparison["bm25_contribution_to_selected_topk_count"] >= 0
    assert isinstance(row_comparison["selected_topk_layer_provenance_counts"], dict)
    vector_invocation = row_comparison["source_native_vector_invocation"]
    assert vector_invocation["vector_backend_invoked"] is True
    assert vector_invocation["query_embedding_created_or_loaded"] is True
    assert vector_invocation["query_embedding_dim"] == 16
    assert vector_invocation["vector_top_k_count"] >= 1
    assert vector_invocation["vector_hydration_failure_count"] == 0
    assert vector_invocation["vector_hydration_success_count"] == vector_invocation["vector_top_k_count"]
    assert vector_invocation["vector_candidate_generation_input_policy"] == "query_text_only_no_gold_qrels_labels_ids_or_baseline_topk"
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False


def test_current_diagnostic_hash_faiss_source_native_audit_marks_semantic_quality_unproven() -> None:
    source_units = [
        {
            "unit_id": "src-audit-1",
            "source_atom_id": "srcatom-audit-1",
            "doc_id": "source-doc",
            "chunk_id": "source-audit-1",
            "source_family": "TEXT",
            "title": "Audit",
            "section": "Vector",
            "text": "diagnostic hash vector audit source-native text",
            "surface": "source_atom",
            "text_sha256": "src-audit-1-sha",
            "metadata": {},
        }
    ]
    adapter = SourceNativeHybridAdapter(units=source_units, requested_backend="auto")
    payloads = adapter._load_payloads()
    adapter._vector_attempted = True
    adapter._vector_ready = True
    adapter._existing_vector_mode = True
    adapter._existing_vector_index = type("FakeFaissIndex", (), {"ntotal": len(payloads)})()
    adapter._vector_id_map = payloads
    adapter._embedding_model = "codex-diagnostic-hashing-vector-v1"
    adapter._embedding_device = "cpu_existing_nonprod_index"
    adapter._gpu_used_for_embedding = False
    adapter._vector_dim = 128

    audit = adapter.vector_index_audit_report

    assert audit["status"] == "connected_semantic_quality_unproven"
    assert audit["vector_backend"] == "faiss"
    assert audit["embedding_model"] == "codex-diagnostic-hashing-vector-v1"
    assert audit["embedding_dim"] == 128
    assert audit["embedding_device"] == "cpu_existing_nonprod_index"
    assert audit["gpu_used_for_embedding"] is False
    assert audit["bge_m3_replacement_needed"] is True
    assert audit["semantic_quality_claim_allowed"] is False
    assert audit["index_integrity_passed"] is True
    assert audit["faiss_index_ntotal"] == 1
    assert audit["faiss_ntotal_matches_id_map"] is True


def test_source_native_bge_m3_persisted_index_supersedes_diagnostic_hash(tmp_path: Path) -> None:
    source_index = tmp_path / "source_index"
    source_index.mkdir(parents=True)
    manifest = source_index / "search_view_manifest.jsonl"
    rows = [
        {
            "source_atom_id": "srcatom-bge-1",
            "search_view_id": "view-bge-1",
            "source_family": "TEXT",
            "document_id": "doc-bge-1",
            "faiss_row_id": 0,
            "bm25_text": "Project Orion Atlas launch is scheduled for April 2026.",
            "embedding_text": "Project Orion Atlas launch is scheduled for April 2026.",
        },
        {
            "source_atom_id": "srcatom-bge-2",
            "search_view_id": "view-bge-2",
            "source_family": "TEXT",
            "document_id": "doc-bge-2",
            "faiss_row_id": 1,
            "bm25_text": "Unrelated archive note about a different project.",
            "embedding_text": "Unrelated archive note about a different project.",
        },
    ]
    write_jsonl(manifest, rows)
    loader = SourceNativeCorpusLoader(search_view_manifest_path=manifest)
    bge_index_dir = tmp_path / "bge_index"

    build = build_source_native_bge_m3_index_artifact(
        index_dir=bge_index_dir,
        loader=loader,
        embedding_provider=FakeBgeM3EmbeddingProvider(),
        force=True,
        gpu_preflight={"torch_cuda_available": True},
    )

    assert build["embedding_model"] == "BAAI/bge-m3-test"
    assert build["dimension"] == 4
    assert build["chunk_count"] == 2
    assert build["gpu_used_for_embedding"] is True
    assert (bge_index_dir / "faiss.index").exists()
    assert (bge_index_dir / "build.json").exists()
    assert (bge_index_dir / "search_view_manifest.jsonl").exists()

    adapter = SourceNativeHybridAdapter(
        requested_backend="vector",
        loader=SourceNativeCorpusLoader(search_view_manifest_path=bge_index_dir / "search_view_manifest.jsonl"),
        embedding_provider=FakeBgeM3EmbeddingProvider(),
        gpu_preflight={"torch_cuda_available": True},
    )

    contexts, _latency = adapter._vector_contexts("Project Orion Atlas April 2026", top_k=1)
    audit = adapter.vector_index_audit_report

    assert contexts[0]["chunk_id"] == "srcatom-bge-1"
    assert audit["status"] == "connected_bge_m3_candidate"
    assert audit["vector_backend"] == "faiss"
    assert audit["embedding_model"] == "BAAI/bge-m3-test"
    assert audit["embedding_dim"] == 4
    assert audit["embedding_device"] == "cuda:0"
    assert audit["gpu_used_for_embedding"] is True
    assert audit["bge_m3_replacement_needed"] is False
    assert audit["semantic_quality_claim_allowed"] is False
    assert audit["index_integrity_passed"] is True
    assert audit["faiss_index_ntotal"] == 2
    assert audit["faiss_ntotal_matches_id_map"] is True
    assert audit["faiss_row_id_mismatch_count"] == 0
    assert "diagnostic_hash" not in " ".join(audit["limitations"])


def test_sentence_transformer_embedder_local_files_only_forces_offline_model_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.capabilities.rag.embeddings import SentenceTransformerEmbedder

    captured: dict[str, object] = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            captured["model_name"] = model_name
            captured["kwargs"] = dict(kwargs)
            captured["hf_hub_offline"] = os.environ.get("HF_HUB_OFFLINE")
            captured["transformers_offline"] = os.environ.get("TRANSFORMERS_OFFLINE")
            self.max_seq_length = 8192
            self.device = "cuda:0"

        def get_sentence_embedding_dimension(self) -> int:
            return 4

        def encode(self, texts: list[str], **_kwargs: object) -> object:
            import numpy as np

            return np.ones((len(texts), 4), dtype=np.float32)

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)

    embedder = SentenceTransformerEmbedder(
        model_name="BAAI/bge-m3",
        local_files_only=True,
        show_progress_bar=False,
    )
    vectors = embedder.embed_queries(["local bge-m3 only"])

    assert vectors.shape == (1, 4)
    assert captured["model_name"] == "BAAI/bge-m3"
    assert captured["kwargs"]["local_files_only"] is True
    assert captured["hf_hub_offline"] == "1"
    assert captured["transformers_offline"] == "1"


def test_sentence_transformer_embedder_local_files_only_overrides_false_offline_envs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.capabilities.rag.embeddings import SentenceTransformerEmbedder

    captured: dict[str, object] = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            captured["model_name"] = model_name
            captured["kwargs"] = dict(kwargs)
            captured["hf_hub_offline"] = os.environ.get("HF_HUB_OFFLINE")
            captured["transformers_offline"] = os.environ.get("TRANSFORMERS_OFFLINE")
            captured["hf_datasets_offline"] = os.environ.get("HF_DATASETS_OFFLINE")
            self.max_seq_length = 8192
            self.device = "cuda:0"

        def get_sentence_embedding_dimension(self) -> int:
            return 4

        def encode(self, texts: list[str], **_kwargs: object) -> object:
            import numpy as np

            return np.ones((len(texts), 4), dtype=np.float32)

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    monkeypatch.setenv("HF_DATASETS_OFFLINE", "0")

    embedder = SentenceTransformerEmbedder(
        model_name="BAAI/bge-m3",
        local_files_only=True,
        show_progress_bar=False,
    )
    vectors = embedder.embed_queries(["local bge-m3 only"])

    assert vectors.shape == (1, 4)
    assert captured["model_name"] == "BAAI/bge-m3"
    assert captured["kwargs"]["local_files_only"] is True
    assert captured["hf_hub_offline"] == "1"
    assert captured["transformers_offline"] == "1"
    assert captured["hf_datasets_offline"] == "1"


def test_sentence_transformer_embedder_local_files_only_unsupported_kwarg_fallback_stays_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.capabilities.rag.embeddings import SentenceTransformerEmbedder

    calls: list[dict[str, object]] = []
    captured: dict[str, object] = {}

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            calls.append(dict(kwargs))
            if "local_files_only" in kwargs:
                raise TypeError("__init__() got an unexpected keyword argument 'local_files_only'")
            captured["model_name"] = model_name
            captured["hf_hub_offline"] = os.environ.get("HF_HUB_OFFLINE")
            captured["transformers_offline"] = os.environ.get("TRANSFORMERS_OFFLINE")
            captured["hf_datasets_offline"] = os.environ.get("HF_DATASETS_OFFLINE")
            self.max_seq_length = 8192
            self.device = "cuda:0"

        def get_sentence_embedding_dimension(self) -> int:
            return 4

        def encode(self, texts: list[str], **_kwargs: object) -> object:
            import numpy as np

            return np.ones((len(texts), 4), dtype=np.float32)

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    monkeypatch.setenv("HF_DATASETS_OFFLINE", "0")

    embedder = SentenceTransformerEmbedder(
        model_name="BAAI/bge-m3",
        local_files_only=True,
        show_progress_bar=False,
    )
    vectors = embedder.embed_queries(["local bge-m3 only"])

    assert vectors.shape == (1, 4)
    assert calls == [{"local_files_only": True}, {}]
    assert captured["model_name"] == "BAAI/bge-m3"
    assert captured["hf_hub_offline"] == "1"
    assert captured["transformers_offline"] == "1"
    assert captured["hf_datasets_offline"] == "1"


def test_sentence_transformer_embedder_local_files_only_restores_offline_env_for_later_loads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.capabilities.rag.embeddings import SentenceTransformerEmbedder

    loads: list[dict[str, object]] = []

    class FakeSentenceTransformer:
        def __init__(self, model_name: str, **kwargs: object) -> None:
            loads.append(
                {
                    "model_name": model_name,
                    "kwargs": dict(kwargs),
                    "hf_hub_offline": os.environ.get("HF_HUB_OFFLINE"),
                    "transformers_offline": os.environ.get("TRANSFORMERS_OFFLINE"),
                    "hf_datasets_offline": os.environ.get("HF_DATASETS_OFFLINE"),
                }
            )
            self.max_seq_length = 8192
            self.device = "cuda:0"

        def get_sentence_embedding_dimension(self) -> int:
            return 4

        def encode(self, texts: list[str], **_kwargs: object) -> object:
            import numpy as np

            return np.ones((len(texts), 4), dtype=np.float32)

    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = FakeSentenceTransformer
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    monkeypatch.setenv("HF_DATASETS_OFFLINE", "0")

    local_embedder = SentenceTransformerEmbedder(
        model_name="BAAI/bge-m3",
        local_files_only=True,
        show_progress_bar=False,
    )
    nonlocal_embedder = SentenceTransformerEmbedder(
        model_name="BAAI/bge-m3",
        local_files_only=False,
        show_progress_bar=False,
    )

    assert local_embedder.embed_queries(["local bge-m3 only"]).shape == (1, 4)
    assert os.environ["HF_HUB_OFFLINE"] == "0"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "0"
    assert os.environ["HF_DATASETS_OFFLINE"] == "0"
    assert nonlocal_embedder.embed_queries(["non-local policy"]).shape == (1, 4)

    assert loads[0]["kwargs"] == {"local_files_only": True}
    assert loads[0]["hf_hub_offline"] == "1"
    assert loads[0]["transformers_offline"] == "1"
    assert loads[0]["hf_datasets_offline"] == "1"
    assert loads[1]["kwargs"] == {}
    assert loads[1]["hf_hub_offline"] == "0"
    assert loads[1]["transformers_offline"] == "0"
    assert loads[1]["hf_datasets_offline"] == "0"


def test_diagnostic_hit_mmr_ndcg_metrics_and_semantic_samples_are_reported_without_leakage(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native_quality_metrics"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-quality",
                "query": "Project Orion Atlas launch April 2026",
                "answerability": "answerable",
                "expected_answer": "April 2026",
                "expected_evidence": [
                    {
                        "text": "Project Orion Atlas launch is scheduled for April 2026",
                        "required": True,
                    }
                ],
            }
        ],
    )
    source_units = [
        {
            "unit_id": "src-quality-1",
            "source_atom_id": "srcatom-quality-1",
            "doc_id": "source-doc-quality-1",
            "chunk_id": "source-quality-1",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Launch",
            "text": "Project Orion Atlas launch is scheduled for April 2026.",
            "surface": "source_atom",
            "text_sha256": "src-quality-1-sha",
            "metadata": {},
        },
        {
            "unit_id": "src-quality-2",
            "source_atom_id": "srcatom-quality-2",
            "doc_id": "source-doc-quality-2",
            "chunk_id": "source-quality-2",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Archive",
            "text": "Project Orion archive contains background material unrelated to the April launch.",
            "surface": "source_atom",
            "text_sha256": "src-quality-2-sha",
            "metadata": {},
        },
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=2,
        run_id="source_native_quality_metrics",
        retrieval_surface="auto",
        retrieval_backend="hybrid",
        source_native_units=source_units,
        source_native_embedding_provider=FakeDeterministicEmbeddingProvider(),
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    metrics = report["diagnostic_retrieval_metrics"]
    assert metrics["enabled"] is True
    assert metrics["metric_policy"] == "diagnostic_only_not_official"
    assert metrics["denominator_policy"] == "rows_with_expected_evidence_for_post_retrieval_diagnostics_only"
    assert metrics["candidate_generation_input_policy"] == "query_text_only_no_gold_qrels_labels_ids_or_baseline_topk"
    assert metrics["gold_fields_used_for_candidate_generation"] is False
    assert metrics["expected_fields_used_for_candidate_generation"] is False
    assert metrics["qrels_used_for_candidate_generation"] is False
    assert metrics["ids_used_for_candidate_generation"] is False
    assert metrics["baseline_topk_used_for_candidate_generation"] is False
    assert metrics["rankings"]["selected"]["hit@1"] == 1.0
    assert metrics["rankings"]["selected"]["hit@2"] == 1.0
    assert metrics["rankings"]["selected"]["ndcg@2"] == 1.0
    assert metrics["rankings"]["mmr_selected"]["mmr_enabled"] is True
    assert metrics["rankings"]["mmr_selected"]["mmr_lambda"] == 0.65
    assert metrics["rankings"]["mmr_selected"]["hit@2"] == 1.0
    assert metrics["rankings"]["mmr_selected"]["ndcg@2"] >= 0.0

    row_metrics = report["items"][0]["diagnostic_retrieval_metrics"]
    assert row_metrics["selected"]["first_relevant_rank"] == 1
    assert row_metrics["mmr_selected"]["mmr_enabled"] is True
    assert row_metrics["mmr_selected"]["candidate_count"] >= 1
    assert row_metrics["mmr_selected"]["selected_chunk_ids"][0]

    samples = report["semantic_quality_samples"]
    assert samples["enabled"] is True
    assert samples["sample_policy"] == "bounded_query_response_context_examples_no_raw_prompt_or_full_raw_response"
    assert samples["semantic_quality_claim_allowed"] is False
    assert samples["samples"][0]["id"] == "q-quality"
    assert samples["samples"][0]["query"] == "Project Orion Atlas launch April 2026"
    assert "Project Orion" in samples["samples"][0]["generated_answer_excerpt"]
    assert samples["samples"][0]["retrieved_contexts"][0]["text_sha256"]
    assert len(samples["samples"][0]["retrieved_contexts"][0]["text_preview"]) <= 240
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False


def test_source_native_layered_retrieval_is_bounded_source_native_only_and_no_leakage(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native_layered"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-layered",
                "query": "Project Orion April 2026 Atlas launch status",
                "answerability": "answerable",
                "expected_answer": "FORBIDDEN_EXPECTED_ANSWER_TOKEN",
                "expected_evidence": [
                    {
                        "doc_id": "forbidden-expected-doc",
                        "chunk_id": "forbidden-expected-chunk",
                        "text": "FORBIDDEN_EXPECTED_EVIDENCE_TOKEN",
                        "required": True,
                    }
                ],
            }
        ],
    )
    source_units = [
        {
            "unit_id": "src-unit-target",
            "source_atom_id": "srcatom-target",
            "doc_id": "source-doc",
            "chunk_id": "source-target",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Launch",
            "text": "Source owned Project Orion status: Atlas launch milestone is scheduled for April 2026.",
            "surface": "source_atom",
            "text_sha256": "src-target-sha",
            "metadata": {"structure_kind": "paragraph"},
        },
        {
            "unit_id": "src-unit-neighbor",
            "source_atom_id": "srcatom-neighbor",
            "doc_id": "source-doc",
            "chunk_id": "source-neighbor",
            "source_family": "TEXT",
            "title": "Project Orion",
            "section": "Launch",
            "text": "Neighbor source-native context for the same Project Orion launch section.",
            "surface": "source_atom",
            "text_sha256": "src-neighbor-sha",
            "metadata": {"structure_kind": "paragraph"},
        },
    ]
    searchunit_units = [
        {
            "payload_id": "legacy-tempting",
            "search_unit_id": "legacy-winning-search-unit",
            "search_view_id": "legacy-winning-search-view",
            "source_family": "TEXT",
            "bm25_text": "Project Orion April 2026 Atlas legacy SearchUnit projection should not be routine.",
            "embedding_text": "Project Orion April 2026 Atlas legacy SearchUnit projection should not be routine.",
            "metadata": {"source_safe_id": "legacy-doc", "source_text_sha256": "legacy-sha"},
        }
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=2,
        run_id="source_native_layered",
        retrieval_surface="auto",
        retrieval_backend="hybrid",
        source_native_units=source_units,
        searchunit_units=searchunit_units,
        source_native_embedding_provider=FakeDeterministicEmbeddingProvider(),
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert output_file_names(output_dir) == ["report.json"]
    layered = report["source_native_layered_retrieval"]
    assert layered["enabled"] is True
    assert layered["planner"] == "bounded_deterministic_source_native_layered_retrieval_v1"
    assert layered["selected_surface"] == "source_native"
    assert layered["selected_backend"] == "hybrid"
    assert layered["query_variant_count"] <= 8
    assert layered["backend_call_count"] <= 16
    assert layered["final_candidate_count"] <= 2
    assert layered["bounds"]["max_candidates_per_layer"] <= 50
    assert layered["bounds"]["max_merged_candidates"] <= 100
    assert layered["bounds"]["max_neighbor_expansion_windows"] <= 2
    assert {
        "L0_query_normalization",
        "L1_lexical_anchor_search",
        "L2_semantic_vector_search",
        "L3_query_variant_search",
        "L4_structure_aware_source_native_search",
        "L5_merge_dedupe",
        "L6_source_neighbor_expansion",
        "L7_anchor_aware_reranking_diagnostics",
    }.issubset(set(layered["layers"]))
    assert layered["per_layer_candidate_counts"]["L1_lexical_anchor_search"] >= 1
    assert layered["per_layer_candidate_counts"]["L5_merge_dedupe"] >= 1
    assert set(layered["per_layer_latency_ms"]) >= set(layered["layers"])
    assert layered["gold_fields_used_for_candidate_generation"] is False
    assert layered["expected_fields_used_for_candidate_generation"] is False
    assert layered["qrels_used_for_candidate_generation"] is False
    assert layered["answerability_labels_used_for_candidate_generation"] is False
    assert layered["ids_used_for_candidate_generation"] is False
    assert layered["baseline_topk_used_for_candidate_generation"] is False
    assert layered["searchunit_searchview_used_as_candidate_surface"] is False
    assert layered["legacy_searchunit_comparison_enabled"] is False
    assert all(
        forbidden.casefold() not in " ".join(layered["query_variants"]).casefold()
        for forbidden in [
            "FORBIDDEN_EXPECTED_ANSWER_TOKEN",
            "FORBIDDEN_EXPECTED_EVIDENCE_TOKEN",
            "q-layered",
            "forbidden-expected-doc",
            "forbidden-expected-chunk",
            "legacy-winning-search-unit",
            "legacy-winning-search-view",
        ]
    )
    row = report["items"][0]
    row_layered = row["source_native_layered_retrieval"]
    assert row_layered["enabled"] is True
    assert row_layered["query_variants"] == layered["query_variants"]
    assert row["retrieval_surface_comparison"]["searchunit_searchview"]["comparison_enabled"] is False
    assert row["retrieval_surface_comparison"]["selected"]["surface"] == "source_native"
    assert row["retrieved_contexts"]
    assert all(context["retrieval_surface"] == "source_native" for context in row["retrieved_contexts"])
    assert all(context.get("layer_provenance") for context in row["retrieved_contexts"])
    assert "legacy-winning-search-unit" not in json.dumps(row["retrieved_contexts"], ensure_ascii=False)


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
    assert diagnostics["searchunit_target_span_absent_count"] == 0
    assert diagnostics["both_surfaces_fail_count"] == 0
    assert report["items"][0]["retrieval_surface_comparison"]["searchunit_searchview"]["comparison_enabled"] is False


def test_source_native_unavailable_auto_does_not_use_searchunit_for_evidence_resolution(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "source_native_unavailable_no_legacy_resolution"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "legacy-only evidence",
                "answerability": "answerable",
                "expected_answer": "legacy answer",
                "expected_evidence": [{"text": "legacy-only SearchUnit evidence", "required": True}],
            }
        ],
    )
    searchunit_units = [
        {
            "payload_id": "legacy-1",
            "search_unit_id": "legacy-search-unit",
            "search_view_id": "legacy-search-view",
            "source_family": "TEXT",
            "bm25_text": "legacy-only SearchUnit evidence",
            "embedding_text": "legacy-only SearchUnit evidence",
            "metadata": {"source_safe_id": "legacy-doc", "source_text_sha256": "legacy-sha"},
        }
    ]

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        top_k=1,
        run_id="source_native_unavailable_no_legacy_resolution",
        retrieval_surface="auto",
        retrieval_backend="bm25",
        source_native_units=[],
        searchunit_units=searchunit_units,
        resolve_expected_evidence=True,
        evidence_resolution_scope="both",
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert report["retrieval_surface"]["selected"] == "unavailable"
    assert report["retrieval_surface"]["auto_fallback_to_searchunit_searchview"] is False
    assert report["diagnostic_metrics"]["expected_evidence_resolution_candidate_count"] == 0
    assert report["diagnostic_metrics"]["expected_evidence_id_unresolved_count"] == 1
    assert report["evidence_resolution_candidates"]
    assert all(row["candidates"] == [] for row in report["evidence_resolution_candidates"])
    candidate_payload_json = json.dumps(
        [candidate for row in report["evidence_resolution_candidates"] for candidate in row["candidates"]],
        ensure_ascii=False,
    )
    assert "legacy-search-unit" not in candidate_payload_json
    assert "legacy-only SearchUnit evidence" not in candidate_payload_json


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
    assert report["surface_migration"]["searchunit_searchview_candidate_surface_enabled"] is False
    assert report["items"][0]["retrieval_surface_comparison"]["source_native"]["expected_evidence_retrieved"] is True


def test_legacy_real_rag_quality_gate_report_scores_answer_evidence_and_critic(tmp_path: Path) -> None:
    dataset = tmp_path / "existing_gold.csv"
    dataset.write_text(
        "\n".join(
            [
                "query_id,question,expected_answer,supporting_evidence,human_review_status,human_approved_gold",
                "q1,Where is HQ?,Seoul,Seoul headquarters,USER_REVIEWED_APPROVED,TRUE",
                "q2,Which port?,Busan,Busan port,USER_REVIEWED_APPROVED,TRUE",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    items = load_eval_dataset(dataset)
    legacy_report = {
        "run_id": "legacy_searchunit_snapshot",
        "dataset_path": dataset.as_posix(),
        "total_item_count": 2,
        "index_retrieval_config": {"adapter": "repo_current_searchunit_vector_hybrid"},
        "items": [
            {
                "id": "q1",
                "query": "Where is HQ?",
                "generated_answer": "Seoul",
                "citations": [{"doc_id": "doc-hq", "chunk_id": "su-hq", "text": "Seoul headquarters"}],
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "su-hq",
                        "search_unit_id": "su-hq",
                        "source_atom_id": "src-hq",
                        "text": "Seoul headquarters",
                    }
                ],
                "failure_labels": [],
            },
            {
                "id": "q2",
                "query": "Which port?",
                "generated_answer": "Busan",
                "citations": [{"doc_id": "doc-port", "chunk_id": "su-port", "text": "Busan port"}],
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-port",
                        "chunk_id": "su-port",
                        "search_unit_id": "su-port",
                        "source_atom_id": "src-port",
                        "text": "Busan port",
                    }
                ],
                "failure_labels": [],
            },
        ],
    }
    real_report = {
        "run_id": "real_source_native_snapshot",
        "dataset_path": dataset.as_posix(),
        "output_dir": (tmp_path / "real").as_posix(),
        "total_item_count": 2,
        "retrieval_surface": {
            "selected": "source_native",
            "source_native_selected": True,
            "searchunit_searchview_candidate_surface_enabled": False,
            "auto_fallback_to_searchunit_searchview": False,
        },
        "source_native_layered_retrieval": {
            "selected_surface": "source_native",
            "source_native_units_only": True,
            "gold_fields_used_for_candidate_generation": False,
            "expected_fields_used_for_candidate_generation": False,
            "qrels_used_for_candidate_generation": False,
            "answerability_labels_used_for_candidate_generation": False,
            "ids_used_for_candidate_generation": False,
            "baseline_topk_used_for_candidate_generation": False,
        },
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "expected_fields_used_for_candidate_generation": False,
            "gold_fields_used_for_candidate_generation": False,
            "qrels_used_for_candidate_generation": False,
            "answerability_labels_used_for_candidate_generation": False,
            "baseline_topk_used_for_candidate_generation": False,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
            "official_metric": False,
            "protected_namespaces_touched": [],
        },
        "items": [
            {
                "id": "q1",
                "query": "Where is HQ?",
                "expected_answer": "Seoul",
                "expected_answer_aliases": [],
                "expected_evidence": [{"doc_id": "doc-hq", "chunk_id": "src-hq", "text": "Seoul headquarters"}],
                "answerability": "unknown",
                "generated_answer": "Seoul",
                "citations": [{"doc_id": "doc-hq", "source_atom_id": "src-hq", "text": "Seoul headquarters"}],
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "retrieval_surface": "source_native",
                        "text": "Seoul headquarters",
                    }
                ],
                "failure_labels": [],
            },
            {
                "id": "q2",
                "query": "Which port?",
                "expected_answer": "Busan",
                "expected_answer_aliases": [],
                "expected_evidence": [{"doc_id": "doc-port", "chunk_id": "src-port", "text": "Busan port"}],
                "answerability": "unknown",
                "generated_answer": "Seoul",
                "citations": [{"doc_id": "doc-other", "source_atom_id": "src-other", "text": "Seoul office"}],
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-other",
                        "source_atom_id": "src-other",
                        "evidence_bundle_id": "bundle-other",
                        "retrieval_surface": "source_native",
                        "text": "Seoul office",
                    }
                ],
                "failure_labels": ["answer_judge_fail"],
            },
        ],
    }

    report, rows = build_legacy_real_rag_quality_gate_report(
        gold_items=items,
        existing_gold_set_path=dataset,
        legacy_baseline_report=legacy_report,
        legacy_baseline_path=tmp_path / "legacy_report.json",
        real_rag_report=real_report,
        real_rag_report_path=tmp_path / "real" / "report.json",
    )

    assert report["existing_gold_set_path"] == dataset.as_posix()
    assert report["gold_set_item_count"] == 2
    assert report["gold_mutation"] is False
    assert report["legacy_baseline_run_id"] == "legacy_searchunit_snapshot"
    assert report["legacy_baseline_replayed_not_executed"] is True
    assert report["real_rag_selected_surface"] == "source_native"
    assert report["guardrail_status"]["valid"] is True
    assert report["guardrail_status"]["source_native_selected"] is True
    assert report["guardrail_status"]["searchunit_searchview_not_used_in_real_rag_lane"] is True
    assert rows[0]["query_id"] == "q1"
    assert rows[0]["answer_delta_category"] == "same_answer_same_support"
    assert rows[0]["evidence_package_status"] == "sufficient"
    assert rows[0]["diagnostic_critic"]["critic_result_tier"] == "diagnostic"
    assert rows[0]["diagnostic_critic"]["answer_supported_by_evidence"] is True
    assert rows[1]["answer_delta_category"] == "legacy_correct_real_wrong"
    assert rows[1]["evidence_package_status"] == "insufficient"
    assert rows[1]["citation_points_to_expected_or_resolved_evidence"] is False
    assert rows[1]["citation_points_to_retrieved_context_diagnostic_only"] is True
    assert rows[1]["diagnostic_critic"]["citation_supported_by_evidence"] is False
    assert rows[1]["diagnostic_critic"]["citation_points_to_retrieved_context_diagnostic_only"] is True
    assert rows[1]["diagnostic_critic"]["should_abstain"] is True
    assert report["same_answer_same_support_count"] == 1
    assert report["legacy_correct_real_wrong_count"] == 1
    assert report["real_rag_supported_count"] == 1
    assert report["unsupported_same_answer_count"] == 0
    assert report["diagnostic_critic_summary"]["citation_supported_by_evidence_count"] == 1
    assert report["diagnostic_critic_summary"]["citation_points_to_expected_or_resolved_evidence_count"] == 1
    assert report["diagnostic_critic_summary"]["citation_points_to_retrieved_context_diagnostic_only_count"] == 2

    unsafe_real_report = dict(real_report)
    unsafe_real_report["guardrails"] = {
        **real_report["guardrails"],
        "expected_fields_used_for_candidate_generation": True,
    }
    unsafe_report, _unsafe_rows = build_legacy_real_rag_quality_gate_report(
        gold_items=items,
        existing_gold_set_path=dataset,
        legacy_baseline_report=legacy_report,
        legacy_baseline_path=tmp_path / "legacy_report.json",
        real_rag_report=unsafe_real_report,
        real_rag_report_path=tmp_path / "real" / "report.json",
    )
    assert unsafe_report["guardrail_status"]["valid"] is False
    assert "expected_fields_not_used_for_candidate_generation" in unsafe_report["guardrail_status"]["violations"]

    gate_unsafe_real_report = {
        **real_report,
        "evidence_gate": {
            "evidence_gate_mode": "enforce",
            "validator_version": "bounded_evidence_gate_v1",
            "guardrail_status": {
                "gate_uses_expected_fields": True,
                "gate_uses_gold_fields": False,
                "gate_uses_legacy_fields": False,
                "retrieval_loop_triggered": False,
            },
        },
    }
    gate_unsafe_report, _gate_unsafe_rows = build_legacy_real_rag_quality_gate_report(
        gold_items=items,
        existing_gold_set_path=dataset,
        legacy_baseline_report=legacy_report,
        legacy_baseline_path=tmp_path / "legacy_report.json",
        real_rag_report=gate_unsafe_real_report,
        real_rag_report_path=tmp_path / "real" / "report.json",
    )
    assert gate_unsafe_report["guardrail_status"]["valid"] is False
    assert "expected_gold_legacy_not_used_for_evidence_gate_enforcement" in gate_unsafe_report["guardrail_status"]["violations"]

    legacy_comparison_real_report = {
        **real_report,
        "retrieval_surface": {
            **real_report["retrieval_surface"],
            "legacy_surface_comparison_enabled": True,
        },
    }
    legacy_comparison_report, _legacy_comparison_rows = build_legacy_real_rag_quality_gate_report(
        gold_items=items,
        existing_gold_set_path=dataset,
        legacy_baseline_report=legacy_report,
        legacy_baseline_path=tmp_path / "legacy_report.json",
        real_rag_report=legacy_comparison_real_report,
        real_rag_report_path=tmp_path / "real" / "report.json",
    )
    assert legacy_comparison_report["guardrail_status"]["valid"] is False
    assert "searchunit_searchview_not_used_in_real_rag_lane" in legacy_comparison_report["guardrail_status"]["violations"]


def test_quality_gate_baseline_auto_selects_exact_query_id_coverage(tmp_path: Path) -> None:
    dataset = tmp_path / "existing_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {"id": "q1", "query": "Q1?", "expected_answer": "A1", "expected_evidence": [{"text": "A1 evidence"}]},
            {"id": "q2", "query": "Q2?", "expected_answer": "A2", "expected_evidence": [{"text": "A2 evidence"}]},
        ],
    )
    items = load_eval_dataset(dataset)
    report_root = tmp_path / "reports" / "rag_eval"
    dataset_report_path = _report_path_value(dataset)

    def _write_candidate(run_dir: str, run_id: str, item_ids: list[str]) -> Path:
        output = report_root / run_dir
        output.mkdir(parents=True, exist_ok=True)
        path = output / "report.json"
        path.write_text(
            json.dumps(
                    {
                        "run_id": run_id,
                        "dataset_path": dataset_report_path,
                        "total_item_count": len(item_ids),
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
                            "official_metric_input_rows": 0,
                            "official_metric_input_rows_created": 0,
                            "official_metric_input_rows_consumed": 0,
                            "promotion_evidence": False,
                            "product_success_evidence_allowed": False,
                            "live_readiness_claim": False,
                            "protected_namespaces_touched": [],
                            "raw_prompt_payload_written": False,
                            "raw_response_payload_written": False,
                            "expected_fields_used_for_candidate_generation": False,
                            "gold_fields_used_for_candidate_generation": False,
                            "qrels_used_for_candidate_generation": False,
                            "answerability_labels_used_for_candidate_generation": False,
                            "baseline_topk_used_for_candidate_generation": False,
                            "ids_used_for_candidate_generation": False,
                        },
                        "index_retrieval_config": {"adapter": "repo_current_searchunit_vector_hybrid"},
                        "items": [{"id": item_id, "generated_answer": "answer"} for item_id in item_ids],
                    },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    _write_candidate("zzz_partial_single_vector_final", "zzz_partial_single_vector_final", ["q1"])
    expected = _write_candidate("aaa_exact_legacy", "aaa_exact_legacy", ["q1", "q2"])

    baseline, selected = resolve_quality_gate_baseline_report(
        "auto",
        dataset_path=dataset,
        gold_items=items,
        report_root=report_root,
    )

    assert selected == expected
    assert baseline["run_id"] == "aaa_exact_legacy"




def test_citation_validator_rejects_same_doc_chunk_with_different_source_identity() -> None:
    raw_outputs = [
        {
            "id": "q-identity",
            "query": "Where is Apollo HQ?",
            "generated_answer": "Apollo HQ is in Seoul.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_atom_id": "src-selected",
                    "evidence_bundle_id": "bundle-selected",
                    "text": "Apollo HQ is in Seoul.",
                    "text_sha256": "hash-selected",
                }
            ],
            "citations": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_atom_id": "src-other",
                    "evidence_bundle_id": "bundle-other",
                    "text": "Apollo HQ is in Seoul.",
                    "text_sha256": "hash-other",
                }
            ],
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="diagnostic")

    citation = gated_outputs[0]["evidence_gate"]["citation_validations"][0]
    assert citation["citation_target_exists"] is False
    assert citation["citation_target_in_selected_evidence"] is False
    assert citation["citation_support_status"] == "missing_target"
    assert gated_outputs[0]["answer_gate_decision"] == "block_unsupported_answer"
    assert gated_outputs[0]["unsupported_answer_blocked"] is False
    assert gated_outputs[0]["would_block_unsupported_answer"] is True
    assert summary["citation_supported_count"] == 0
    assert summary["citation_missing_target_count"] == 1
    assert summary["unsupported_answer_blocked_count"] == 0


def test_run_eval_preserves_citation_source_identity_for_evidence_gate(tmp_path: Path) -> None:
    dataset = tmp_path / "citation_identity_gold.jsonl"
    context = tmp_path / "citation_identity_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "citation_identity"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-identity",
                "query": "Where is Apollo HQ?",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-hq", "chunk_id": "chunk-hq", "text": "Apollo HQ is in Seoul."}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-identity",
                "generated_answer": "Apollo HQ is in Seoul.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "chunk-hq",
                        "source_atom_id": "src-other",
                        "evidence_bundle_id": "bundle-other",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        context_jsonl_path=context,
        output_dir=output_dir,
        top_k=1,
        run_id="citation_identity",
        output_mode="single",
        evidence_gate_mode="diagnostic",
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    row = report["items"][0]
    citation = row["evidence_gate"]["citation_validations"][0]
    assert row["citations"][0]["source_atom_id"] == "src-other"
    assert row["citations"][0]["evidence_bundle_id"] == "bundle-other"
    assert citation["cited_source_atom_id"] == "src-other"
    assert citation["cited_evidence_bundle_id"] == "bundle-other"
    assert citation["citation_target_exists"] is False
    assert citation["citation_target_in_selected_evidence"] is False
    assert citation["citation_support_status"] == "missing_target"


def test_evidence_gate_handles_empty_rows_and_invalid_mode() -> None:
    raw_outputs = [{"id": "empty", "query": "", "generated_answer": "", "retrieved_contexts": [], "citations": []}]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="diagnostic")
    off_outputs, off_summary = apply_evidence_gate_to_outputs(raw_outputs, mode="off")

    assert gated_outputs[0]["answer_gate_decision"] == "not_comparable"
    assert gated_outputs[0]["evidence_gate"]["evidence_package_status"] == "insufficient"
    assert summary["item_count"] == 1
    assert summary["unsupported_answer_rate_before_gate"] == 0.0
    assert summary["unsupported_answer_rate_after_gate"] == 0.0
    assert off_outputs[0]["evidence_gate_mode"] == "off"
    assert off_summary["gate_policy_not_applicable_count"] == 1
    with pytest.raises(DatasetSchemaError):
        apply_evidence_gate_to_outputs(raw_outputs, mode="agent-loop")


def test_evidence_gate_ignores_expected_evidence_resolution_for_enforcement() -> None:
    raw_outputs = [
        {
            "id": "q-resolution-leak",
            "query": "Where is Apollo HQ?",
            "generated_answer": "Apollo HQ is in Seoul.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-wrong",
                    "chunk_id": "chunk-wrong",
                    "source_atom_id": "src-wrong",
                    "evidence_bundle_id": "bundle-wrong",
                    "text": "Apollo HQ moved from Busan.",
                }
            ],
            "citations": [],
            "expected_evidence_resolution": {
                "rows": [
                    {
                        "resolved": True,
                        "selected_candidate": {
                            "doc_id": "doc-gold",
                            "source_atom_id": "src-gold",
                            "text": "Apollo HQ is in Seoul.",
                        },
                    }
                ]
            },
            "expected_answer": "Seoul",
            "expected_evidence": [{"text": "Apollo HQ is in Seoul."}],
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="enforce")

    row = gated_outputs[0]
    assert row["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert row["evidence_gate"]["selected_evidence_count"] == 0
    assert row["evidence_gate"]["gate_uses_expected_fields"] is False
    assert row["evidence_gate"]["gate_uses_gold_fields"] is False
    assert summary["insufficient_evidence_abstained_count"] == 1
    assert summary["unsupported_answer_rate_after_gate"] == 0.0


def test_evidence_gate_does_not_use_title_or_workbook_metadata_as_support() -> None:
    raw_outputs = [
        {
            "id": "q-title-only",
            "query": "Where is Apollo HQ?",
            "generated_answer": "Apollo HQ is in Seoul.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-hq",
                    "chunk_id": "chunk-hq",
                    "source_atom_id": "src-hq",
                    "evidence_bundle_id": "bundle-hq",
                    "title": "Apollo HQ Seoul workbook",
                    "section": "Seoul locator",
                    "text": "Workbook metadata only; no answer sentence here.",
                }
            ],
            "citations": [],
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="enforce")

    assert gated_outputs[0]["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert gated_outputs[0]["evidence_gate"]["selected_evidence_count"] == 0
    assert summary["insufficient_evidence_abstained_count"] == 1


def test_evidence_gate_does_not_use_xlsx_cell_axis_as_answer_value_support() -> None:
    raw_outputs = [
        {
            "id": "q-xlsx-cell-axis-only",
            "query": "2019년 2월 5호선 승차총승객수는 얼마야?",
            "generated_answer": "F7입니다.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-xlsx",
                    "chunk_id": "chunk-xlsx",
                    "source_atom_id": "src-xlsx",
                    "evidence_bundle_id": "bundle-xlsx",
                    "source_family": "XLSX",
                    "text": "2019년 2월 5호선 승차총승객수 항목입니다.",
                    "sheet": "2019년 2월",
                    "cell": "F7",
                    "row_label": "5호선",
                    "column_label": "승차총승객수",
                }
            ],
            "citations": [
                {
                    "doc_id": "doc-xlsx",
                    "chunk_id": "chunk-xlsx",
                    "source_atom_id": "src-xlsx",
                    "evidence_bundle_id": "bundle-xlsx",
                    "source_family": "XLSX",
                    "text": "2019년 2월 5호선 승차총승객수 항목입니다.",
                    "sheet": "2019년 2월",
                    "cell": "F7",
                    "row_label": "5호선",
                    "column_label": "승차총승객수",
                }
            ],
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="enforce")

    assert gated_outputs[0]["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert gated_outputs[0]["answer_gate_decision"] == "block_unsupported_answer"
    assert gated_outputs[0]["evidence_gate"]["evidence_package_status"] == "insufficient"
    assert summary["allowed_answer_count"] == 0
    assert summary["insufficient_evidence_abstained_count"] == 1


def test_evidence_gate_does_not_use_pdf_page_axis_as_answer_value_support() -> None:
    raw_outputs = [
        {
            "id": "q-pdf-page-axis-only",
            "query": "2024년 영업이익 표의 값은 얼마야?",
            "generated_answer": "7입니다.",
            "retrieved_contexts": [
                {
                    "doc_id": "doc-pdf",
                    "chunk_id": "chunk-pdf",
                    "source_atom_id": "src-pdf",
                    "evidence_bundle_id": "bundle-pdf",
                    "source_family": "PDF",
                    "text": "2024년 영업이익 표 항목입니다.",
                    "page_number": "7",
                    "table_caption": "영업실적 표",
                    "bbox": "[10,20,30,40]",
                }
            ],
            "citations": [
                {
                    "doc_id": "doc-pdf",
                    "chunk_id": "chunk-pdf",
                    "source_atom_id": "src-pdf",
                    "evidence_bundle_id": "bundle-pdf",
                    "source_family": "PDF",
                    "text": "2024년 영업이익 표 항목입니다.",
                    "page_number": "7",
                    "table_caption": "영업실적 표",
                    "bbox": "[10,20,30,40]",
                }
            ],
        }
    ]

    gated_outputs, summary = apply_evidence_gate_to_outputs(raw_outputs, mode="enforce")

    assert gated_outputs[0]["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    assert gated_outputs[0]["answer_gate_decision"] == "block_unsupported_answer"
    assert gated_outputs[0]["evidence_gate"]["evidence_package_status"] == "insufficient"
    assert summary["allowed_answer_count"] == 0
    assert summary["insufficient_evidence_abstained_count"] == 1


def test_validate_actual_rag_guardrails_rejects_semantic_raw_response_without_evidence_gate() -> None:
    summary = {
        "run_id": "raw-response-guard",
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
        "semantic_quality_samples": {
            "enabled": True,
            "semantic_quality_claim_allowed": False,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": True,
        },
    }

    with pytest.raises(DatasetSchemaError, match="semantic_quality_samples.raw_response_payload_written"):
        validate_actual_rag_guardrails(summary)


def test_validate_actual_rag_guardrails_accepts_evidence_gate_without_semantic_samples() -> None:
    summary = {
        "run_id": "gate_only_guardrail",
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
        "evidence_gate": {
            "evidence_gate_mode": "diagnostic",
            "validator_version": "bounded_evidence_gate_v1",
            "guardrail_status": {
                "gate_uses_expected_fields": False,
                "gate_uses_gold_fields": False,
                "gate_uses_legacy_fields": False,
                "retrieval_loop_triggered": False,
            },
        },
    }

    validate_actual_rag_guardrails(summary)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("uses_query_id_or_row_id_or_target_id", True, "query_id_or_row_id_or_target_id"),
        ("uses_expected_answer_or_evidence", True, "expected_answer_or_evidence"),
        ("uses_qrels_or_labels", True, "qrels_or_labels"),
        ("per_row_alias_table", True, "per_row_alias_table"),
        ("composer_or_gate_loosening_for_single_residual", True, "single_residual"),
        ("classification", "forbidden_eval_row_shortcut", "forbidden_eval_row_shortcut"),
    ],
)
def test_validate_actual_rag_guardrails_rejects_forbidden_heuristic_risk_ledger_entries(
    field: str,
    value: object,
    match: str,
) -> None:
    entry = {
        "rule_id": "unsafe_shortcut",
        "classification": "query_text_only_reformulation",
        "status": "active",
        "uses_query_id_or_row_id_or_target_id": False,
        "uses_expected_answer_or_evidence": False,
        "uses_qrels_or_labels": False,
        "per_row_alias_table": False,
        "composer_or_gate_loosening_for_single_residual": False,
    }
    entry[field] = value
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
        "heuristic_risk_ledger": {
            "schema_version": "actual_rag_eval.heuristic_risk_ledger.v1",
            "official_metric": False,
            "official_metric_input_rows": 0,
            "entries": [entry],
            "forbidden_eval_row_shortcut_active": False,
        },
    }

    with pytest.raises(DatasetSchemaError, match=match):
        validate_actual_rag_guardrails(summary)


def test_evidence_gate_summary_is_embedded_in_quality_gate_report() -> None:
    real_report = {
        "run_id": "real_gate",
        "retrieval_surface": {
            "selected": "source_native",
            "source_native_selected": True,
            "searchunit_searchview_candidate_surface_enabled": False,
            "auto_fallback_to_searchunit_searchview": False,
        },
        "source_native_layered_retrieval": {
            "selected_surface": "source_native",
            "source_native_units_only": True,
            "gold_fields_used_for_candidate_generation": False,
            "expected_fields_used_for_candidate_generation": False,
            "qrels_used_for_candidate_generation": False,
            "answerability_labels_used_for_candidate_generation": False,
            "ids_used_for_candidate_generation": False,
            "baseline_topk_used_for_candidate_generation": False,
        },
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "expected_fields_used_for_candidate_generation": False,
            "gold_fields_used_for_candidate_generation": False,
            "qrels_used_for_candidate_generation": False,
            "answerability_labels_used_for_candidate_generation": False,
            "baseline_topk_used_for_candidate_generation": False,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
            "official_metric": False,
            "protected_namespaces_touched": [],
        },
        "evidence_gate": {
            "evidence_gate_mode": "enforce",
            "validator_version": "bounded_evidence_gate_v1",
            "item_count": 1,
            "sufficient_evidence_package_count": 0,
            "insufficient_evidence_package_count": 1,
            "allowed_answer_count": 0,
            "abstained_count": 1,
            "unsupported_answer_blocked_count": 1,
            "would_abstain_count": 1,
            "would_block_unsupported_answer_count": 1,
            "citation_supported_count": 0,
            "citation_retrieved_context_only_diagnostic_count": 1,
            "unsupported_answer_rate_before_gate": 1.0,
            "unsupported_answer_rate_after_gate": 0.0,
            "insufficient_evidence_abstained_count": 1,
            "sufficient_evidence_allowed_count": 0,
            "guardrail_status": {
                "gate_uses_expected_fields": False,
                "gate_uses_gold_fields": False,
                "gate_uses_legacy_fields": False,
                "retrieval_loop_triggered": False,
            },
        },
        "items": [
            {
                "id": "q1",
                "query": "Where?",
                "generated_answer": "제공된 근거만으로는 답할 수 없습니다.",
                "original_generated_answer_hash": "original-hash",
                "gated_answer_hash": "gated-hash",
                "retrieved_contexts": [{"doc_id": "doc-a", "source_atom_id": "src-a", "text": "Only Busan evidence"}],
                "citations": [{"doc_id": "doc-a", "source_atom_id": "src-a", "text": "Only Busan evidence"}],
                "evidence_gate": {
                    "evidence_package_status": "insufficient",
                    "answer_gate_decision": "block_unsupported_answer",
                    "answer_modified_by_gate": True,
                    "abstention_reason": "missing_entity_anchor",
                    "unsupported_answer_blocked": True,
                    "retrieval_loop_triggered": False,
                    "gate_uses_expected_fields": False,
                    "gate_uses_gold_fields": False,
                    "gate_uses_legacy_fields": False,
                },
            }
        ],
    }
    legacy_report = {"run_id": "legacy", "items": [{"id": "q1", "generated_answer": "Busan"}]}
    dataset = Path("unused.jsonl")
    items = [
        type(
            "EvalItemLike",
            (),
            {
                "id": "q1",
                "query": "Where?",
                "expected_answer": "Seoul",
                "expected_answer_aliases": [],
                "expected_evidence": [],
                "answerability": "unknown",
                "has_answerability_label": False,
                "has_expected_evidence": False,
            },
        )()
    ]

    report, rows = build_legacy_real_rag_quality_gate_report(
        gold_items=items,
        existing_gold_set_path=dataset,
        legacy_baseline_report=legacy_report,
        legacy_baseline_path=Path("legacy.json"),
        real_rag_report=real_report,
        real_rag_report_path=Path("real.json"),
    )

    assert report["evidence_gate_mode"] == "enforce"
    assert report["validator_version"] == "bounded_evidence_gate_v1"
    assert report["abstained_count"] == 1
    assert rows[0]["answer_gate_decision"] == "block_unsupported_answer"
    assert rows[0]["answer_modified_by_gate"] is True
    assert rows[0]["real_rag_supported_before_gate"] is False
    assert rows[0]["real_rag_supported_after_gate"] is False
    assert rows[0]["expected_answer_match_after_gate"] is False


def test_run_eval_writes_legacy_real_rag_quality_gate_artifacts_without_using_baseline_for_candidates(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "tiny_gold.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "Where is the needle answer?",
                "expected_answer": "needle answer",
                "expected_evidence": [{"doc_id": "doc-a", "chunk_id": "src-a", "text": "needle answer appears"}],
            }
        ],
    )
    baseline = tmp_path / "legacy_report.json"
    baseline.write_text(
        json.dumps(
                {
                    "run_id": "legacy_searchunit_snapshot",
                    "dataset_path": dataset.as_posix(),
                    "total_item_count": 1,
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
                        "official_metric_input_rows": 0,
                        "official_metric_input_rows_created": 0,
                        "official_metric_input_rows_consumed": 0,
                        "promotion_evidence": False,
                        "product_success_evidence_allowed": False,
                        "live_readiness_claim": False,
                        "protected_namespaces_touched": [],
                        "raw_prompt_payload_written": False,
                        "raw_response_payload_written": False,
                        "gold_fields_used_for_candidate_generation": False,
                        "query_id_used_for_candidate_generation": False,
                        "row_id_used_for_candidate_generation": False,
                        "target_id_used_for_candidate_generation": False,
                        "baseline_topk_used_for_candidate_generation": False,
                        "expected_fields_used_for_candidate_generation": False,
                        "qrels_used_for_candidate_generation": False,
                        "answerability_labels_used_for_candidate_generation": False,
                        "ids_used_for_candidate_generation": False,
                        "retriever_oracle_shortcut_used": False,
                    },
                    "index_retrieval_config": {"adapter": "repo_current_searchunit_vector_hybrid"},
                    "items": [
                    {
                        "id": "q1",
                        "query": "Where is the needle answer?",
                        "generated_answer": "needle answer",
                        "citations": [{"doc_id": "doc-a", "chunk_id": "su-a", "text": "needle answer appears"}],
                        "retrieved_contexts": [
                            {
                                "doc_id": "doc-a",
                                "chunk_id": "su-a",
                                "search_unit_id": "su-a",
                                "source_atom_id": "src-a",
                                "text": "needle answer appears",
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=tmp_path / "quality_gate_run",
        top_k=3,
        run_id="quality_gate_run",
        command="unit-test",
        retrieval_surface="source-native",
        source_native_units=[
            {
                "unit_id": "src-a",
                "source_atom_id": "src-a",
                "doc_id": "doc-a",
                "source_family": "TEXT",
                "text": "needle answer appears",
                "surface": "source_atom",
            }
        ],
        source_native_embedding_provider=FakeDeterministicEmbeddingProvider(),
        quality_gate_baseline_path=baseline,
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    gate_report_path = Path(report["artifact_paths"]["legacy_real_rag_quality_gate_report_json"])
    gate_items_path = Path(report["artifact_paths"]["legacy_real_rag_quality_gate_items_jsonl"])
    assert report["artifact_contract"]["legacy_sidecars_written"] is False
    assert report["artifact_contract"]["quality_gate_sidecars_written"] is True
    assert report["artifact_contract"]["quality_gate_sidecar_exception"] is True
    assert gate_report_path.exists()
    assert gate_items_path.exists()
    gate_report = json.loads(gate_report_path.read_text(encoding="utf-8"))
    gate_rows = [json.loads(line) for line in gate_items_path.read_text(encoding="utf-8").splitlines()]
    assert gate_report["legacy_baseline_replayed_not_executed"] is True
    assert gate_report["guardrail_status"]["legacy_outputs_not_used_for_candidate_generation"] is True
    assert gate_report["guardrail_status"]["expected_fields_not_used_for_candidate_generation"] is True
    assert gate_report["guardrail_status"]["source_native_units_only"] is True
    assert gate_rows[0]["legacy_retrieved_context_ids"] == ["su-a"]
    assert gate_rows[0]["real_rag_source_atom_ids"] == ["src-a"]
    assert gate_rows[0]["candidate_generation_input_policy"] == "query_text_only"
    assert gate_rows[0]["diagnostic_critic"]["retrieval_loop_triggered"] is False


def test_run_eval_enforce_evidence_gate_before_quality_gate_artifacts_and_preserves_single_output_policy(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "gate_gold.jsonl"
    context = tmp_path / "gate_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "gate_enforce"
    write_jsonl(
        dataset,
        [
            {
                "id": "supported",
                "query": "Where is Apollo HQ?",
                "expected_answer": "Seoul",
                "expected_evidence": [{"doc_id": "doc-hq", "chunk_id": "src-hq", "text": "Apollo HQ is in Seoul."}],
            },
            {
                "id": "blocked",
                "query": "When did Project Mercury launch?",
                "expected_answer": "2026-04-12",
                "expected_evidence": [{"doc_id": "doc-date", "chunk_id": "src-date", "text": "Project Mercury launched on 2026-04-12."}],
            },
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "supported",
                "generated_answer": "Apollo HQ is in Seoul.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "src-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-hq",
                        "chunk_id": "src-hq",
                        "source_atom_id": "src-hq",
                        "evidence_bundle_id": "bundle-hq",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
            },
            {
                "id": "blocked",
                "generated_answer": "Project Mercury launched on 2027-05-01.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-date",
                        "chunk_id": "src-date",
                        "source_atom_id": "src-date",
                        "evidence_bundle_id": "bundle-date",
                        "text": "Project Mercury launched on 2026-04-12.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-date",
                        "chunk_id": "src-date",
                        "source_atom_id": "src-date",
                        "evidence_bundle_id": "bundle-date",
                        "text": "Project Mercury launched on 2026-04-12.",
                    }
                ],
            },
        ],
    )
    baseline = tmp_path / "legacy_report.json"
    baseline.write_text(
        json.dumps(
            {
                "run_id": "legacy_snapshot",
                "dataset_path": dataset.as_posix(),
                "total_item_count": 2,
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
                    "official_metric_input_rows": 0,
                    "official_metric_input_rows_created": 0,
                    "official_metric_input_rows_consumed": 0,
                    "promotion_evidence": False,
                    "product_success_evidence_allowed": False,
                    "live_readiness_claim": False,
                    "protected_namespaces_touched": [],
                    "raw_prompt_payload_written": False,
                    "raw_response_payload_written": False,
                    "expected_fields_used_for_candidate_generation": False,
                    "gold_fields_used_for_candidate_generation": False,
                    "qrels_used_for_candidate_generation": False,
                    "answerability_labels_used_for_candidate_generation": False,
                    "baseline_topk_used_for_candidate_generation": False,
                    "ids_used_for_candidate_generation": False,
                },
                "index_retrieval_config": {"adapter": "repo_current_searchunit_vector_hybrid"},
                "items": [
                    {"id": "supported", "generated_answer": "Seoul"},
                    {"id": "blocked", "generated_answer": "2026-04-12"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        context_jsonl_path=context,
        output_dir=output_dir,
        top_k=2,
        run_id="gate_enforce",
        output_mode="single",
        quality_gate_baseline_path=baseline,
        evidence_gate_mode="enforce",
    )

    report = json.loads(bundle.report_path.read_text(encoding="utf-8"))
    assert sorted(output_file_names(output_dir)) == [
        "legacy_real_rag_quality_gate_items.jsonl",
        "legacy_real_rag_quality_gate_report.json",
        "report.json",
    ]
    assert report["artifact_contract"]["legacy_sidecars_written"] is False
    assert report["artifact_contract"]["quality_gate_sidecars_written"] is True
    assert report["evidence_gate"]["evidence_gate_mode"] == "enforce"
    assert report["evidence_gate"]["sufficient_evidence_allowed_count"] == 1
    assert report["evidence_gate"]["insufficient_evidence_abstained_count"] == 1
    supported, blocked = report["items"]
    assert supported["answer_gate_decision"] == "allow_answer"
    assert supported["generated_answer"] == "Apollo HQ is in Seoul."
    assert blocked["answer_gate_decision"] == "block_unsupported_answer"
    assert blocked["generated_answer"] == "제공된 근거만으로는 답할 수 없습니다."
    gate_report = json.loads((output_dir / "legacy_real_rag_quality_gate_report.json").read_text(encoding="utf-8"))
    gate_rows = [
        json.loads(line)
        for line in (output_dir / "legacy_real_rag_quality_gate_items.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert gate_report["evidence_gate_mode"] == "enforce"
    assert gate_report["insufficient_evidence_abstained_count"] == 1
    assert {row["answer_gate_decision"] for row in gate_rows} == {"allow_answer", "block_unsupported_answer"}
    assert {row["expected_answer_match_before_gate"] for row in gate_rows} == {False, True}
    assert {row["expected_evidence_match_before_gate"] for row in gate_rows} == {True}
    assert {row["expected_evidence_match_after_gate"] for row in gate_rows} == {True}
    blocked_gate_row = next(row for row in gate_rows if row["query_id"] == "blocked")
    assert blocked_gate_row["legacy_real_answer_delta_before_gate"] == "legacy_correct_real_wrong"
    assert blocked_gate_row["expected_answer_match_after_gate"] is False
    assert blocked_gate_row["unsupported_answer_blocked"] is True
    assert blocked_gate_row["would_block_unsupported_answer"] is False


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


def test_report_separates_selected_evidence_supported_and_gold_correct_citations(tmp_path: Path) -> None:
    dataset = tmp_path / "citation_terms_gold.jsonl"
    context = tmp_path / "citation_terms_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "citation_terms"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-citation-terms",
                "query": "Where is Apollo HQ?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"text": "Apollo headquarters is in Seoul.", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-citation-terms",
                "generated_answer": "Apollo HQ is in Seoul.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-selected",
                        "chunk_id": "chunk-selected",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-selected",
                        "chunk_id": "chunk-selected",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="citation_terms",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        resolve_expected_evidence=False,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    gate = report["evidence_gate"]
    diagnostics = report["diagnostic_metrics"]
    assert gate["citation_supported_count"] == 1
    assert gate["citation_selected_evidence_supported_count"] == 1
    assert gate["citation_supported_definition"] == "citation_target_selected_and_text_supported_by_selected_evidence"
    assert diagnostics["citation_gold_correct_checked_count_diagnostic"] == 1
    assert diagnostics["citation_gold_correct_pass_count_diagnostic"] == 0
    assert diagnostics["citation_gold_correct_rate_diagnostic"] == 0.0
    assert diagnostics["citation_gold_correct_definition"] == (
        "citation_matches_expected_evidence_when_gold_fields_available_diagnostic_only"
    )


def test_citation_gold_correct_diagnostic_passes_when_expected_evidence_matches(tmp_path: Path) -> None:
    dataset = tmp_path / "citation_gold_correct_pass_gold.jsonl"
    context = tmp_path / "citation_gold_correct_pass_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "citation_gold_correct_pass"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-citation-pass",
                "query": "Where is Apollo HQ?",
                "answerability": "answerable",
                "expected_answer": "Seoul",
                "expected_evidence": [{"text": "Apollo HQ is in Seoul.", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-citation-pass",
                "generated_answer": "Apollo HQ is in Seoul.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-selected",
                        "chunk_id": "chunk-selected",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-selected",
                        "chunk_id": "chunk-selected",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="citation_gold_correct_pass",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        resolve_expected_evidence=False,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    diagnostics = report["diagnostic_metrics"]
    assert report["evidence_gate"]["citation_selected_evidence_supported_count"] == 1
    assert diagnostics["citation_gold_correct_checked_count_diagnostic"] == 1
    assert diagnostics["citation_gold_correct_pass_count_diagnostic"] == 1
    assert diagnostics["citation_gold_correct_rate_diagnostic"] == 1.0


def test_citation_gold_correct_diagnostic_rate_is_none_without_gold_fields(tmp_path: Path) -> None:
    dataset = tmp_path / "citation_no_gold.jsonl"
    context = tmp_path / "citation_no_gold_context.jsonl"
    output_dir = tmp_path / "reports" / "rag_eval" / "citation_no_gold"
    write_jsonl(
        dataset,
        [{"id": "q-citation-no-gold", "query": "Where is Apollo HQ?", "answerability": "answerable"}],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-citation-no-gold",
                "generated_answer": "Apollo HQ is in Seoul.",
                "retrieved_contexts": [
                    {
                        "doc_id": "doc-selected",
                        "chunk_id": "chunk-selected",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-selected",
                        "chunk_id": "chunk-selected",
                        "source_atom_id": "src-selected",
                        "evidence_bundle_id": "bundle-selected",
                        "text": "Apollo HQ is in Seoul.",
                    }
                ],
            }
        ],
    )

    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="citation_no_gold",
        output_mode="single",
        evidence_gate_mode="diagnostic",
        resolve_expected_evidence=False,
    )

    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    diagnostics = report["diagnostic_metrics"]
    assert report["evidence_gate"]["citation_selected_evidence_supported_count"] == 1
    assert diagnostics["citation_gold_correct_checked_count_diagnostic"] == 0
    assert diagnostics["citation_gold_correct_pass_count_diagnostic"] == 0
    assert diagnostics["citation_gold_correct_rate_diagnostic"] is None


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
                        "text": "PDF source text 다른 만화 TV 애니메이션 방영 시기는 2006년 10월입니다.",
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


def test_reviewed_evidence_mapping_csv_ingest_applies_run_local_overlay_and_opens_strict_denominators(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    reviewed_csv = tmp_path / "reviewed_mapping.csv"
    output_dir = tmp_path / "reports" / "rag_eval" / "reviewed_ingest"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-reviewed",
                "query": "Mercury launch date?",
                "answerability": "unknown",
                "expected_answer": "2026-04-12",
                "expected_evidence": [
                    {
                        "text": "Mercury launch window opens on 2026-04-12",
                        "required": True,
                    }
                ],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-reviewed",
                "generated_answer": "2026-04-12",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-reviewed",
                        "chunk_id": "chunk-reviewed",
                        "score": 0.97,
                        "text": "Mercury launch window opens on 2026-04-12.",
                    }
                ],
                "citations": [
                    {
                        "doc_id": "doc-reviewed",
                        "chunk_id": "chunk-reviewed",
                        "text": "Mercury launch window opens on 2026-04-12.",
                    }
                ],
            }
        ],
    )
    with reviewed_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "query_id",
                "expected_evidence_index",
                "candidate_doc_id",
                "candidate_chunk_id",
                "candidate_text_hash",
                "machine_recommendation",
                "human_accept",
                "human_answerability_label",
                "human_notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "query_id": "q-reviewed",
                "expected_evidence_index": "0",
                "candidate_doc_id": "doc-reviewed",
                "candidate_chunk_id": "chunk-reviewed",
                "candidate_text_hash": "sha256:test-reviewed",
                "machine_recommendation": "likely_accept",
                "human_accept": "yes",
                "human_answerability_label": "answerable",
                "human_notes": "reviewer accepted source-native evidence mapping",
            }
        )

    original_dataset = dataset.read_bytes()
    bundle = run_eval_from_paths(
        dataset_path=dataset,
        output_dir=output_dir,
        context_jsonl_path=context,
        top_k=1,
        run_id="reviewed_ingest",
        reviewed_evidence_mapping_csv=reviewed_csv,
    )

    assert dataset.read_bytes() == original_dataset
    assert output_file_names(output_dir) == ["report.json", "reviewed_evidence_mapping_patch.json"]
    report = json.loads(bundle.summary_path.read_text(encoding="utf-8"))
    assert report["reviewed_mapping_input_path"] == reviewed_csv.as_posix()
    assert report["reviewed_mapping_applied"] is True
    assert report["reviewed_mapping_row_count"] == 1
    assert report["reviewed_mapping"]["accepted_mapping_count"] == 1
    assert report["reviewed_mapping"]["answerability_label_applied_count"] == 1
    assert report["reviewed_mapping"]["gold_or_qrels_mutation"] is False
    assert report["reviewed_mapping"]["machine_recommendation_treated_as_gold"] is False
    assert report["diagnostic_metrics"]["reviewed_mapping_row_count"] == 1
    assert report["diagnostic_metrics"]["reviewed_mapping_applied"] is True
    assert report["strict_metrics"]["exact_or_alias_answer_correctness"]["denominator"] == 1
    assert report["strict_metrics"]["evidence_recall@1"]["denominator"] == 1
    assert report["strict_metrics"]["evidence_recall@1"]["numerator"] == 1
    assert report["answerability_distribution"]["answerable"] == 1
    assert report["answerability_distribution"]["unknown"] == 0
    assert report["denominator_changes"]["strict_answer_denominator"]["before"] == 0
    assert report["denominator_changes"]["strict_answer_denominator"]["after"] == 1
    assert report["denominator_changes"]["strict_evidence_denominator"]["before"] == 0
    assert report["denominator_changes"]["strict_evidence_denominator"]["after"] == 1
    assert report["items"][0]["reviewed_mapping_applied"] is True
    assert report["items"][0]["expected_evidence"][0]["doc_id"] == "doc-reviewed"
    assert report["items"][0]["expected_evidence"][0]["chunk_id"] == "chunk-reviewed"
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["qrels_mutation"] is False
    assert report["guardrails"]["label_mutation"] is False
    assert report["guardrails"]["expected_fields_used_for_candidate_generation"] is False
    assert report["human_decision_fields_filled_by_codex"] is False
    patch = json.loads((output_dir / "reviewed_evidence_mapping_patch.json").read_text(encoding="utf-8"))
    assert patch["row_count"] == 1
    assert patch["changes"][0]["query_id"] == "q-reviewed"
    assert "answerability_label_applied" in patch["changes"][0]["change_types"]
    assert "expected_evidence_id_mapping_applied" in patch["changes"][0]["change_types"]


def test_reviewed_evidence_mapping_csv_rejects_machine_recommendation_as_human_decision(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    reviewed_csv = tmp_path / "reviewed_mapping.csv"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "Mercury launch date?",
                "answerability": "unknown",
                "expected_answer": "2026-04-12",
                "expected_evidence": [{"text": "Mercury launch window opens on 2026-04-12"}],
            }
        ],
    )
    write_jsonl(context, [{"id": "q1", "generated_answer": "", "retrieved_contexts": [], "citations": []}])
    with reviewed_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["query_id", "candidate_doc_id", "candidate_chunk_id", "machine_recommendation", "human_accept"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "query_id": "q1",
                "candidate_doc_id": "doc1",
                "candidate_chunk_id": "chunk1",
                "machine_recommendation": "likely_accept",
                "human_accept": "likely_accept",
            }
        )

    with pytest.raises(DatasetSchemaError, match="machine recommendation"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=tmp_path / "reports" / "rag_eval" / "reject_machine",
            context_jsonl_path=context,
            reviewed_evidence_mapping_csv=reviewed_csv,
        )


def test_reviewed_evidence_mapping_csv_rejects_unreviewed_blank_human_fields(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    reviewed_csv = tmp_path / "reviewed_mapping.csv"
    write_jsonl(
        dataset,
        [
            {
                "id": "q1",
                "query": "Mercury launch date?",
                "answerability": "unknown",
                "expected_answer": "2026-04-12",
                "expected_evidence": [{"text": "Mercury launch window opens on 2026-04-12"}],
            }
        ],
    )
    write_jsonl(context, [{"id": "q1", "generated_answer": "", "retrieved_contexts": [], "citations": []}])
    with reviewed_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["query_id", "candidate_doc_id", "candidate_chunk_id", "machine_recommendation", "human_accept"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "query_id": "q1",
                "candidate_doc_id": "doc1",
                "candidate_chunk_id": "chunk1",
                "machine_recommendation": "likely_accept",
                "human_accept": "",
            }
        )

    with pytest.raises(DatasetSchemaError, match="explicit human"):
        run_eval_from_paths(
            dataset_path=dataset,
            output_dir=tmp_path / "reports" / "rag_eval" / "reject_blank",
            context_jsonl_path=context,
            reviewed_evidence_mapping_csv=reviewed_csv,
        )


def test_cli_smoke_with_reviewed_evidence_mapping_csv_ingest(tmp_path: Path) -> None:
    dataset = tmp_path / "fixture_gold.jsonl"
    context = tmp_path / "fixture_context.jsonl"
    reviewed_csv = tmp_path / "reviewed_mapping.csv"
    output_dir = tmp_path / "reports" / "rag_eval" / "cli_reviewed_ingest"
    write_jsonl(
        dataset,
        [
            {
                "id": "q-cli-reviewed",
                "query": "Mercury launch date?",
                "answerability": "unknown",
                "expected_answer": "2026-04-12",
                "expected_evidence": [{"text": "Mercury launch window opens on 2026-04-12", "required": True}],
            }
        ],
    )
    write_jsonl(
        context,
        [
            {
                "id": "q-cli-reviewed",
                "generated_answer": "2026-04-12",
                "retrieved_contexts": [
                    {
                        "rank": 1,
                        "doc_id": "doc-cli",
                        "chunk_id": "chunk-cli",
                        "score": 0.99,
                        "text": "Mercury launch window opens on 2026-04-12.",
                    }
                ],
                "citations": [{"doc_id": "doc-cli", "chunk_id": "chunk-cli", "text": "Mercury launch window opens on 2026-04-12."}],
            }
        ],
    )
    with reviewed_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "query_id",
                "expected_evidence_index",
                "candidate_doc_id",
                "candidate_chunk_id",
                "machine_recommendation",
                "human_accept",
                "human_answerability_label",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "query_id": "q-cli-reviewed",
                "expected_evidence_index": "0",
                "candidate_doc_id": "doc-cli",
                "candidate_chunk_id": "chunk-cli",
                "machine_recommendation": "likely_accept",
                "human_accept": "yes",
                "human_answerability_label": "answerable",
            }
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
            "--output-dir",
            str(output_dir),
            "--run-id",
            "cli_reviewed_ingest",
            "--top-k",
            "1",
            "--reviewed-evidence-mapping-csv",
            str(reviewed_csv),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert output_file_names(output_dir) == ["report.json", "reviewed_evidence_mapping_patch.json"]
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["reviewed_mapping_applied"] is True
    assert report["reviewed_mapping_input_path"] == reviewed_csv.as_posix()
    assert report["strict_metrics"]["exact_or_alias_answer_correctness"]["denominator"] == 1
    assert report["strict_metrics"]["evidence_recall@1"]["denominator"] == 1
    assert report["guardrails"]["gold_mutation"] is False
    assert report["guardrails"]["expected_fields_used_for_candidate_generation"] is False


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
