from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "ai" / "eval" / "reports" / "rag-ingestion"
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
REPAIRED_PDF_QUERY_IDS = ("gq_auto_010", "gq_auto_030", "gq_pdf_section_question_001")
CURRENT_REPORT_FILENAMES = {
    "official_answer_citation_metric_first_run_v1.json",
    "official_answer_citation_metric_first_run_v1.md",
    "official_answer_citation_scorer_results_v1.jsonl",
    "official_metric_input_config_v1.json",
    "official_metric_pre_execution_smoke_report_v1.json",
    "xlsx_answer_citation_runtime_precision_candidate_results_v1.jsonl",
    "pdf_answer_citation_table_value_candidate_results_v1.jsonl",
    "rag_current_eval_status.jsonl",
}


def test_source_of_truth_audit_reports_current_scored_baseline() -> None:
    first_run = read_json(REPORT_DIR / "official_answer_citation_metric_first_run_v1.json")
    first_run_md = (REPORT_DIR / "official_answer_citation_metric_first_run_v1.md").read_text(encoding="utf-8")
    scorer_rows = read_jsonl(REPORT_DIR / "official_answer_citation_scorer_results_v1.jsonl")
    xlsx_rows = read_jsonl(REPORT_DIR / "xlsx_answer_citation_runtime_precision_candidate_results_v1.jsonl")
    pdf_rows = read_jsonl(REPORT_DIR / "pdf_answer_citation_table_value_candidate_results_v1.jsonl")
    smoke = read_json(REPORT_DIR / "official_metric_pre_execution_smoke_report_v1.json")

    assert first_run["official_scoring_attempt_count"] == 29
    assert first_run["scored_count"] == 29
    assert first_run["official_metric_execution_started"] is True
    assert first_run["execution_blocker_category"] is None
    assert first_run["primary_failure_category"] == "CITATION_UNSUPPORTED"
    assert first_run["status_detail"] == "SCORED_BASELINE_PARTIAL"
    assert first_run["failure_category_counts"] == {
        "CITATION_UNSUPPORTED": 11,
        "PARTIAL_OR_UNSUPPORTED": 10,
        "PASS": 8,
    }
    assert "SCORER_BACKEND_UNAVAILABLE" not in json.dumps(first_run, ensure_ascii=False)
    assert "SCORER_BACKEND_UNAVAILABLE" not in first_run_md

    assert len(scorer_rows) == 29
    assert len({row["query_id"] for row in scorer_rows}) == 29
    first_run_rows_by_id = {row["query_id"]: row for row in first_run["row_results"]}
    mismatches = [
        row["query_id"]
        for row in scorer_rows
        if first_run_rows_by_id[row["query_id"]]["failure_category"] != row["failure_category"]
    ]
    assert mismatches == []

    assert len(xlsx_rows) == 29
    assert len({row["query_id"] for row in xlsx_rows}) == 29
    assert Counter(row["failure_category"] for row in xlsx_rows) == Counter({"PASS": 26, "PARTIAL_OR_UNSUPPORTED": 3})
    assert sum(
        1
        for row in xlsx_rows
        if row["track"] == "xlsx_business_structured" and row["failure_category"] == "PASS"
    ) == 19
    assert [
        row["query_id"]
        for row in xlsx_rows
        if row["track"] == "pdf_business_ocr_mm" and row["failure_category"] != "PASS"
    ] == ["gq_auto_010", "gq_auto_030", "gq_pdf_section_question_001"]

    assert len(pdf_rows) == 29
    assert len({row["query_id"] for row in pdf_rows}) == 29
    assert Counter(row["failure_category"] for row in pdf_rows) == Counter({"PASS": 29})
    for query_id in REPAIRED_PDF_QUERY_IDS:
        row = next(row for row in pdf_rows if row["query_id"] == query_id)
        score_details = row.get("score_details", {})
        locator = row["generated_citations"][0]["citation_locator"]
        assert score_details["deterministic_verification_passed"] is True
        assert score_details["expected_answer_used_for_generation"] is False
        assert score_details["supporting_evidence_used_for_generation"] is False
        assert score_details["gold_fields_used_for_generation"] is False
        assert score_details["source_text_contains_answer_value"] is True
        assert score_details["source_row_contains_target_value"] is True
        assert score_details["source_bound_identity_verified"] is True
        assert score_details["locator_compatibility"] == ["OFFICIAL_COMPATIBLE_LOCATOR"]
        assert locator["file"]
        assert locator["page"]
        assert locator["physical_page_index"] >= 0
        assert locator["bbox"] and len(locator["bbox"]) == 4
        assert locator["search_unit_id"]
        assert locator["document_version_id"]
        assert locator["source_basis"]
        assert locator["source_pdf_path"]
        assert locator["row_label"]
        assert locator["target_column"]
        assert locator["region_type"] in {"paragraph", "table_body"}
        assert locator["region_type"] != "table_row"
        if locator["region_type"] == "table_body":
            assert locator["bbox_granularity"] == "row_only"

    assert smoke["official_metric_execution_started"] is False
    assert smoke["status"] == "OFFICIAL_METRIC_PRE_EXECUTION_SMOKE_PASS_WITH_DIAGNOSTIC_WARNINGS"

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_progress = progress.split("## Short History", 1)[0]
    assert "SCORER_BACKEND_UNAVAILABLE" not in current_progress
    assert "official_answer_citation_pdf_table_value_candidate_report_only_pass" in current_progress
    assert "PDF candidate now has official-compatible source-bound locators" in current_progress
    assert "promotion_evidence=false" in current_progress


def test_pdf_candidate_locator_repair_artifacts_are_locked_to_current_report_only_state() -> None:
    first_run = read_json(REPORT_DIR / "official_answer_citation_metric_first_run_v1.json")
    input_config = read_json(REPORT_DIR / "official_metric_input_config_v1.json")
    xlsx_rows = read_jsonl(REPORT_DIR / "xlsx_answer_citation_runtime_precision_candidate_results_v1.jsonl")
    pdf_rows = read_jsonl(REPORT_DIR / "pdf_answer_citation_table_value_candidate_results_v1.jsonl")
    status_events = read_jsonl(REPORT_DIR / "rag_current_eval_status.jsonl")
    smoke = read_json(REPORT_DIR / "official_metric_pre_execution_smoke_report_v1.json")

    assert {path.name for path in REPORT_DIR.iterdir() if path.is_file()} == CURRENT_REPORT_FILENAMES
    assert not (REPORT_DIR / "rag_current_eval_status.md").exists()

    assert first_run["scored_count"] == 29
    assert first_run["failure_category_counts"] == {
        "CITATION_UNSUPPORTED": 11,
        "PARTIAL_OR_UNSUPPORTED": 10,
        "PASS": 8,
    }
    assert Counter(row["failure_category"] for row in first_run["row_results"]) == Counter(
        {"CITATION_UNSUPPORTED": 11, "PARTIAL_OR_UNSUPPORTED": 10, "PASS": 8}
    )
    first_run_by_id = {row["query_id"]: row for row in first_run["row_results"]}
    scorer_by_id = {
        row["query_id"]: row
        for row in read_jsonl(REPORT_DIR / "official_answer_citation_scorer_results_v1.jsonl")
    }
    config_query_ids = {row["query_id"] for row in input_config["candidate_manifest"]}
    assert set(first_run_by_id) == set(scorer_by_id) == config_query_ids
    assert {
        query_id: row["failure_category"]
        for query_id, row in first_run_by_id.items()
    } == {
        query_id: row["failure_category"]
        for query_id, row in scorer_by_id.items()
    }
    assert [first_run_by_id[query_id]["failure_category"] for query_id in REPAIRED_PDF_QUERY_IDS] == [
        "PARTIAL_OR_UNSUPPORTED",
        "PARTIAL_OR_UNSUPPORTED",
        "PARTIAL_OR_UNSUPPORTED",
    ]

    assert len(xlsx_rows) == 29
    assert len({row["query_id"] for row in xlsx_rows}) == 29
    assert Counter(row["failure_category"] for row in xlsx_rows) == Counter({"PASS": 26, "PARTIAL_OR_UNSUPPORTED": 3})
    assert all(row.get("promotion_evidence") is False for row in xlsx_rows)
    xlsx_by_id = {row["query_id"]: row for row in xlsx_rows}
    for query_id in REPAIRED_PDF_QUERY_IDS:
        row = xlsx_by_id[query_id]
        assert row["failure_category"] == "PARTIAL_OR_UNSUPPORTED"
        serialized_row = json.dumps(row, ensure_ascii=False)
        assert "table_value_candidate" not in serialized_row
        assert "OFFICIAL_COMPATIBLE_LOCATOR" not in serialized_row

    assert len(pdf_rows) == 29
    assert len({row["query_id"] for row in pdf_rows}) == 29
    assert Counter(row["failure_category"] for row in pdf_rows) == Counter({"PASS": 29})
    assert all(row.get("promotion_evidence") is False for row in pdf_rows)

    pdf_by_id = {row["query_id"]: row for row in pdf_rows}
    assert all(sum(1 for row in pdf_rows if row["query_id"] == query_id) == 1 for query_id in REPAIRED_PDF_QUERY_IDS)
    for query_id in REPAIRED_PDF_QUERY_IDS:
        row = pdf_by_id[query_id]
        score_details = row["score_details"]
        locator = row["generated_citations"][0]["citation_locator"]
        assert score_details["locator_compatibility"] == ["OFFICIAL_COMPATIBLE_LOCATOR"]
        assert score_details["expected_answer_used_for_generation"] is False
        assert score_details["supporting_evidence_used_for_generation"] is False
        assert score_details["gold_fields_used_for_generation"] is False
        assert locator["search_unit_id"].strip()
        assert locator["document_version_id"].strip()
        assert locator["source_pdf_path"].strip()
        assert locator["row_label"].strip()
        assert locator["target_column"].strip()
        assert locator["source_basis"].strip()
        assert numeric_bbox(locator["bbox"])
        if query_id == "gq_auto_010":
            assert locator["region_type"] == "paragraph"
            assert "bbox_granularity" not in locator
        else:
            assert locator["region_type"] == "table_body"
            assert locator["bbox_granularity"] == "row_only"

    status = status_events[-1]
    assert status["event_type"] == "pdf_candidate_locator_hardening"
    assert status["current_focused_result"] == "68 passed, 0 skipped, 0 failed"
    assert status["pdf_candidate_result_count"] == {
        "failure_category_counts": {"PASS": 29},
        "rows": 29,
        "unique_query_ids": 29,
    }
    assert status["pdf_repaired_rows"] == 3
    assert set(status["locator_compatibility_after"]) == set(REPAIRED_PDF_QUERY_IDS)
    assert all(value == ["OFFICIAL_COMPATIBLE_LOCATOR"] for value in status["locator_compatibility_after"].values())
    assert status["guardrails"]["promotion_evidence"] is False
    assert status["guardrails"]["denominator_mutation"] is False
    assert status["guardrails"]["production_mutation"] is False

    assert smoke["official_metric_execution_started"] is False
    assert first_run["official_metric_execution_started"] is True


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def numeric_bbox(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    try:
        return all(isinstance(float(item), float) for item in value)
    except (TypeError, ValueError):
        return False
