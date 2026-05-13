from __future__ import annotations

import csv
import importlib.util
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_text_namu_v2_gold_review_workflow.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


workflow = load_module(SCRIPT_PATH, "rag_text_namu_v2_gold_review_workflow_for_tests")


def test_v2_review_pack_has_simplified_human_columns_without_denominator_policy():
    assert workflow.HUMAN_REVIEW_COLUMNS == [
        "user_final_gold_policy",
        "user_answerability_label",
        "user_relevance_label",
        "user_expected_answer_override",
        "user_expected_evidence_override",
        "user_review_notes",
    ]
    assert "user_denominator_policy" not in workflow.REVIEW_PACK_FIELDNAMES
    assert workflow.REVIEW_PACK_FIELDNAMES[-6:] == workflow.HUMAN_REVIEW_COLUMNS


def test_manual_candidate_pool_matches_target_bucket_mix():
    assert len(workflow.MANUAL_CANDIDATES) == 100
    assert sum(workflow.TARGET_BUCKET_COUNTS.values()) == 100
    assert Counter(row["bucket"] for row in workflow.MANUAL_CANDIDATES) == workflow.TARGET_BUCKET_COUNTS
    assert {row["allowed_abstain"] for row in workflow.MANUAL_CANDIDATES} == {"false", "true"}


def test_v1_audit_detects_column_corruption_and_preserves_audit_only_status(tmp_path: Path):
    original_path = tmp_path / "gold_queries_text_namu_v4_v0.csv"
    reviewed_path = tmp_path / "text_gold_review_pack.csv"
    original_rows = [
        {
            **{column: "" for column in workflow.V1_ORIGINAL_REQUIRED_COLUMNS},
            "query_id": "gold_seed_0001",
            "query": "문서 찾아줘",
        },
        {
            **{column: "" for column in workflow.V1_ORIGINAL_REQUIRED_COLUMNS},
            "query_id": "gold_seed_0002",
            "query": "정상 질문",
        },
    ]
    reviewed_rows = [
        {
            **{column: "" for column in workflow.V1_REVIEW_REQUIRED_COLUMNS},
            "track": "TEXT",
            "query_id": "gold_seed_0001",
            "user_gold_decision": "KEEP_POSITIVE",
            "user_answerability_label": "REVISE_EXPECTED_EVIDENCE",
            "user_relevance_label": "RELEVANT",
        },
        {
            **{column: "" for column in workflow.V1_REVIEW_REQUIRED_COLUMNS},
            "track": "TEXT",
            "query_id": "gold_seed_0002",
            "user_gold_decision": "REVISE_EXPECTED_ANSWER",
            "user_answerability_label": "PARTIALLY_ANSWERABLE",
            "user_relevance_label": "",
        },
    ]
    write_csv(original_path, workflow.V1_ORIGINAL_REQUIRED_COLUMNS, original_rows)
    write_csv(reviewed_path, workflow.V1_REVIEW_REQUIRED_COLUMNS, reviewed_rows)

    report = workflow.audit_v1_review_pack(
        reviewed_rows=reviewed_rows,
        reviewed_columns=workflow.V1_REVIEW_REQUIRED_COLUMNS,
        original_rows=original_rows,
        original_columns=workflow.V1_ORIGINAL_REQUIRED_COLUMNS,
        reviewed_path=reviewed_path,
        original_path=original_path,
    )

    assert report["status"] == "AUDIT_ONLY_NOT_FINAL_GOLD"
    assert report["row_counts"]["equal"] is True
    assert report["query_id_checks"]["set_equal"] is True
    assert report["invalid_label_placements"]["action_label_in_user_answerability_label_count"] == 1
    assert report["empty_required_human_fields"]["user_denominator_policy_empty_count"] == 2
    assert report["classification"]["primary_suspected_issue"] == "human-review-column issue"


def test_derive_denominator_policy_conservative_defaults():
    assert (
        workflow.derive_denominator_policy(
            final_policy="KEEP_OFFICIAL",
            answerability="ANSWERABLE",
            relevance="RELEVANT",
            allowed_abstain="false",
        )
        == "STRICT_OFFICIAL_POSITIVE_DENOMINATOR"
    )
    assert (
        workflow.derive_denominator_policy(
            final_policy="KEEP_OFFICIAL",
            answerability="PARTIALLY_ANSWERABLE",
            relevance="RELEVANT",
            allowed_abstain="false",
        )
        == "DIAGNOSTIC_ONLY_PARTIAL_UNSUPPORTED"
    )
    assert (
        workflow.derive_denominator_policy(
            final_policy="KEEP_OFFICIAL",
            answerability="NOT_ANSWERABLE",
            relevance="RELEVANT",
            allowed_abstain="true",
        )
        == "DIAGNOSTIC_ONLY_NOT_ANSWERABLE_NO_ABSTAIN_DENOMINATOR"
    )
    assert (
        workflow.derive_denominator_policy(
            final_policy="NEEDS_REVIEW",
            answerability="",
            relevance="",
            allowed_abstain="false",
        )
        == "PENDING_REVIEW_EXCLUDED"
    )


def test_validate_review_pack_allows_initial_pending_rows():
    row = valid_review_row("text_namu_v2_0001")

    result = workflow.validate_v2_review_pack(
        [row],
        columns=workflow.REVIEW_PACK_FIELDNAMES,
        pages=fixture_pages(),
        chunks=fixture_chunks(),
    )

    assert result["ok"], result["row_errors"]
    assert result["final_policy_counts"] == {"NEEDS_REVIEW": 1}
    assert result["derived_policy_counts"] == {"PENDING_REVIEW_EXCLUDED": 1}


def test_validate_review_pack_rejects_cross_column_label_placements():
    rows = [
        {
            **valid_review_row("text_namu_v2_0001"),
            "user_final_gold_policy": "KEEP_OFFICIAL",
            "user_answerability_label": "REVISE_EXPECTED_EVIDENCE",
            "user_relevance_label": "RELEVANT",
        },
        {
            **valid_review_row("text_namu_v2_0002"),
            "user_final_gold_policy": "ANSWERABLE",
            "user_answerability_label": "ANSWERABLE",
            "user_relevance_label": "RELEVANT",
        },
    ]

    result = workflow.validate_v2_review_pack(
        rows,
        columns=workflow.REVIEW_PACK_FIELDNAMES,
        pages=fixture_pages(),
        chunks=fixture_chunks(),
    )

    assert not result["ok"]
    assert "action/final-policy label is inside answerability column" in result["row_errors"]["text_namu_v2_0001"]
    assert "answerability label is inside final-gold-policy column" in result["row_errors"]["text_namu_v2_0002"]


def test_validate_candidates_rejects_must_contain_terms_missing_from_expected_answer_text():
    row = valid_review_row("text_namu_v2_0001")
    row["expected_answer_text"] = "대형 뱅가드 대회가 열린다."
    row["must_contain_terms"] = "대형 대회"

    result = workflow.validate_v2_candidates(
        [row],
        pages=fixture_pages(),
        chunks=fixture_chunks(),
        expected_row_count=None,
    )

    assert not result["status"] == "PASSED"
    assert any(
        "must_contain_terms item is not literal" in error
        for error in result["row_errors"]["text_namu_v2_0001"]
    )


def test_validate_candidates_decodes_source_url_page_title():
    row = valid_review_row("text_namu_v2_0001")
    row["expected_page_title"] = "문서"

    result = workflow.validate_v2_candidates(
        [row],
        pages=fixture_pages(),
        chunks=fixture_chunks(),
        expected_row_count=None,
    )

    assert result["status"] == "PASSED", result["row_errors"]

    row["expected_page_title"] = "짧은제목"
    result = workflow.validate_v2_candidates(
        [row],
        pages=fixture_pages(),
        chunks=fixture_chunks(),
        expected_row_count=None,
    )

    assert result["status"] == "FAILED"
    assert any("decoded source_url title" in error for error in result["row_errors"]["text_namu_v2_0001"])


def test_validate_candidates_rejects_source_locator_mismatch():
    row = valid_review_row("text_namu_v2_0001")
    row["source_locator"] = row["source_locator"].replace("page_id=page-1", "page_id=page-2")

    result = workflow.validate_v2_candidates(
        [row],
        pages=fixture_pages(),
        chunks=fixture_chunks(),
        expected_row_count=None,
    )

    assert result["status"] == "FAILED"
    assert any("source_locator page_id mismatch" in error for error in result["row_errors"]["text_namu_v2_0001"])


def test_validate_candidates_warns_on_time_sensitive_source_bound_wording():
    row = valid_review_row("text_namu_v2_0001")
    row["query"] = "상영일은 문서에 언제로 적혀 있어"
    row["expected_answer_text"] = "문서에는 2025년 12월 27일 상영 예정이라고 적혀 있다."
    row["must_contain_terms"] = "2025년 12월 27일;상영 예정"

    result = workflow.validate_v2_candidates(
        [row],
        pages=fixture_pages(),
        chunks=fixture_chunks(),
        expected_row_count=None,
    )

    assert result["status"] == "PASSED", result["row_errors"]
    assert "time-sensitive wording present: 예정" in result["row_warnings"]["text_namu_v2_0001"]


def valid_review_row(query_id: str) -> dict[str, str]:
    chunk_text = "정답 근거"
    chunk_hash = workflow.sha256_text(chunk_text)
    return {
        "query_id": query_id,
        "track": "TEXT",
        "bucket": "direct_fact_lookup",
        "query": "질문",
        "expected_answer_text": "정답",
        "must_contain_terms": "정답",
        "expected_document_ids": "page-1",
        "expected_page_ids": "page-1",
        "expected_section_ids": "section-1",
        "expected_chunk_ids": "chunk-1",
        "expected_page_title": "문서",
        "expected_section_path": "개요",
        "source_url": "https://namu.wiki/w/%EB%AC%B8%EC%84%9C",
        "chunk_text_sha256": chunk_hash,
        "source_evidence_quote": chunk_text,
        "answer_type": "short_fact",
        "allowed_abstain": "false",
        "source_dataset": workflow.SOURCE_DATASET,
        "source_original_gold": workflow.SOURCE_ORIGINAL_GOLD,
        "source_query_id": "gold_seed_fixture",
        "source_label_status": "bound",
        "source_locator": (
            "source_query_id=gold_seed_fixture; "
            f"source_artifact={workflow.SOURCE_ORIGINAL_GOLD}; "
            "source_namespace=TEXT_NAMU_V4; page_id=page-1; section_id=section-1; "
            f"chunk_id=chunk-1; section_path=개요; source_url=https://namu.wiki/w/%EB%AC%B8%EC%84%9C; "
            f"chunk_text_sha256={chunk_hash}"
        ),
        "candidate_default_policy": "OFFICIAL_REVIEW_CANDIDATE",
        "generation_notes": "fixture",
        "user_final_gold_policy": "NEEDS_REVIEW",
        "user_answerability_label": "",
        "user_relevance_label": "",
        "user_expected_answer_override": "",
        "user_expected_evidence_override": "",
        "user_review_notes": "",
    }


def fixture_pages():
    return {
        "page-1": {
            "page_id": "page-1",
            "page_title": "문서",
            "sections": [{"section_id": "section-1", "heading_path": ["개요"]}],
        }
    }


def fixture_chunks():
    return {
        "chunk-1": {
            "chunk_id": "chunk-1",
            "doc_id": "page-1",
            "section_id": "section-1",
            "section_path": ["개요"],
            "chunk_text": "정답 근거",
            "metadata": {"source_url": "https://namu.wiki/w/%EB%AC%B8%EC%84%9C"},
        }
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
