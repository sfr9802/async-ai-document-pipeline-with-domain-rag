from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "ai" / "eval" / "reports" / "rag-ingestion"
README = ROOT / "README.md"
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
REPAIRED_PDF_QUERY_IDS = ("gq_auto_010", "gq_auto_030", "gq_pdf_section_question_001")
AGENTIC_RUN_ID = "official_answer_citation_agentic_loop_run_v1"
AGENTIC_V2_RUN_ID = "official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic"
AGENTIC_V2_1_RUN_ID = "official_answer_citation_agentic_loop_run_v2_1_citation_contract_repair"
AGENTIC_DIAGNOSTIC_CLASSIFICATION = (
    "diagnostic_live_generation_fixture_all_index_not_official_denominator_representative"
)
AGENTIC_DIAGNOSTIC_PERFORMANCE_INTERPRETATION = (
    "diagnostic_retrieval_agent_loop_not_final_answer_generation_quality"
)
SOURCE_BOUND_INDEX_BLOCKER = "SOURCE_BOUND_OFFICIAL_DENOMINATOR_SOURCE_FIELDS_MISSING"
READINESS_JSON = REPORT_DIR / "official_answer_citation_source_bound_index_build_readiness_v1.json"
AGENTIC_RESULTS = REPORT_DIR / f"{AGENTIC_RUN_ID}_results.jsonl"
AGENTIC_SUMMARY_JSON = REPORT_DIR / f"{AGENTIC_RUN_ID}_summary.json"
AGENTIC_SUMMARY_MD = REPORT_DIR / f"{AGENTIC_RUN_ID}_summary.md"
AGENTIC_ATTRIBUTION_JSON = REPORT_DIR / f"{AGENTIC_RUN_ID}_failure_attribution.json"
AGENTIC_V2_RESULTS = REPORT_DIR / f"{AGENTIC_V2_RUN_ID}_results.jsonl"
AGENTIC_V2_SUMMARY_JSON = REPORT_DIR / f"{AGENTIC_V2_RUN_ID}_summary.json"
AGENTIC_V2_ATTRIBUTION_JSON = REPORT_DIR / f"{AGENTIC_V2_RUN_ID}_failure_attribution.json"
AGENTIC_V2_1_RESULTS = REPORT_DIR / f"{AGENTIC_V2_1_RUN_ID}_results.jsonl"
AGENTIC_V2_1_SUMMARY_JSON = REPORT_DIR / f"{AGENTIC_V2_1_RUN_ID}_summary.json"
AGENTIC_V2_1_ATTRIBUTION_JSON = REPORT_DIR / f"{AGENTIC_V2_1_RUN_ID}_failure_attribution.json"
AGENTIC_INDEX_DIR = ROOT / "ai" / "eval" / "indexes" / "rag-data"
ALLOWED_AGENTIC_ATTRIBUTION_CATEGORIES = {
    "CORPUS_COVERAGE_MISS",
    "RETRIEVAL_MISS",
    "CITATION_PAYLOAD_MISSING",
    "CITATION_LOCATOR_INCOMPATIBLE",
    "ANSWER_GENERATION_NOOP_LIMITATION",
    "STRUCTURED_ADAPTER_NOT_WIRED",
    "SCORER_COMPATIBILITY_MISMATCH",
    "REAL_MODEL_OR_RETRIEVAL_QUALITY_FAILURE",
    "UNKNOWN_NEEDS_INSPECTION",
}
ALLOWED_V2_ATTRIBUTION_CATEGORIES = {
    "PASS",
    "RETRIEVAL_MISS",
    "CITATION_PAYLOAD_SCHEMA_MISMATCH",
    "ADAPTER_FAILURE",
    "ANSWER_SYNTHESIS_LIMITATION",
    "SCORER_COMPATIBILITY_MISMATCH",
    "SOURCE_BOUND_MANIFEST_MISMATCH",
}
CURRENT_REPORT_FILENAMES = {
    "official_answer_citation_metric_first_run_v1.json",
    "official_answer_citation_metric_first_run_v1.md",
    "official_answer_citation_scorer_results_v1.jsonl",
    "official_metric_input_config_v1.json",
    "official_metric_pre_execution_smoke_report_v1.json",
    "xlsx_answer_citation_runtime_precision_candidate_results_v1.jsonl",
    "pdf_answer_citation_table_value_candidate_results_v1.jsonl",
    "rag_current_eval_status.jsonl",
    f"{AGENTIC_RUN_ID}_results.jsonl",
    f"{AGENTIC_RUN_ID}_summary.json",
    f"{AGENTIC_RUN_ID}_summary.md",
    f"{AGENTIC_RUN_ID}_failure_attribution.json",
    f"{AGENTIC_V2_RUN_ID}_results.jsonl",
    f"{AGENTIC_V2_RUN_ID}_summary.json",
    f"{AGENTIC_V2_RUN_ID}_summary.md",
    f"{AGENTIC_V2_RUN_ID}_failure_attribution.json",
    f"{AGENTIC_V2_1_RUN_ID}_results.jsonl",
    f"{AGENTIC_V2_1_RUN_ID}_summary.json",
    f"{AGENTIC_V2_1_RUN_ID}_summary.md",
    f"{AGENTIC_V2_1_RUN_ID}_failure_attribution.json",
    "official_answer_citation_source_bound_index_build_readiness_v1.json",
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
    assert "official_denominator_source_bound_index_build_ready_load_checked" in current_progress
    assert "PDF table/value candidate now has official-compatible source-bound locators" in current_progress
    assert "official_answer_citation_agentic_loop_run_v1" in current_progress
    assert "promotion_evidence=false" in current_progress
    assert "faiss_gpu_used=true" in current_progress
    assert "baseline_comparison_is_model_quality_comparable=false" in current_progress
    assert "4 current run artifacts" in current_progress
    assert "BUILD_READY_LOAD_CHECK_PASSED" in current_progress
    assert "rerun_allowed=true" in current_progress


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

    status = next(event for event in reversed(status_events) if event.get("event_type") == "pdf_candidate_locator_hardening")
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


def test_readme_baseline_section_matches_immutable_first_run_and_separates_candidates() -> None:
    first_run = read_json(REPORT_DIR / "official_answer_citation_metric_first_run_v1.json")
    readme = README.read_text(encoding="utf-8")

    assert "## RAG Answer/Citation Metric Baseline" in readme
    assert "official_answer_citation_metric_first_run_v1" in readme
    assert "`SCORED_BASELINE_PARTIAL`" in readme
    assert f"`scored_count={first_run['scored_count']}`" in readme
    assert "`PASS=8`" in readme
    assert "`CITATION_UNSUPPORTED=11`" in readme
    assert "`PARTIAL_OR_UNSUPPORTED=10`" in readme
    assert "immutable baseline" in readme
    assert "XLSX runtime candidate" in readme
    assert "PASS=26/29" in readme
    assert "XLSX=19/19" in readme
    assert "PDF table/value candidate" in readme
    assert "PASS=29/29" in readme
    assert "must not be presented as the official first-run baseline" in readme
    assert "expected answers/supporting evidence are for scoring/audit only" in readme
    assert AGENTIC_RUN_ID in readme
    assert str(AGENTIC_RESULTS.relative_to(ROOT)).replace("\\", "/") in readme


def test_agentic_loop_measurement_artifacts_are_separate_fail_closed_current_run() -> None:
    first_run = read_json(REPORT_DIR / "official_answer_citation_metric_first_run_v1.json")
    input_config = read_json(REPORT_DIR / "official_metric_input_config_v1.json")
    summary = read_json(AGENTIC_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_RESULTS)
    summary_md = AGENTIC_SUMMARY_MD.read_text(encoding="utf-8")
    status_events = read_jsonl(REPORT_DIR / "rag_current_eval_status.jsonl")

    assert summary["run_id"] == AGENTIC_RUN_ID
    assert not any(
        event.get("run_id") == AGENTIC_RUN_ID
        and event.get("measurement_classification") == "official_next_run_measurement"
        for event in status_events
    )
    assert summary["baseline_reference"]["run_id"] == "official_answer_citation_metric_first_run_v1"
    assert summary["baseline_reference"]["status_detail"] == "SCORED_BASELINE_PARTIAL"
    assert summary["artifact_provenance"]["immutable_first_run_baseline_overwritten"] is False
    assert summary["artifact_provenance"]["report_only_candidates_promoted"] is False
    assert summary["denominator_count"] == 29
    assert summary["result_count"] == 29
    assert summary["unique_query_id_count"] == 29
    assert summary["validation"]["ok"] is True
    assert summary["pipeline_decision"]["registry_application_report_required"] is False
    assert summary["pipeline_decision"]["registry_application_fallback_used"] is True
    assert summary["artifact_paths"]["failure_attribution_json"] == (
        "ai/eval/reports/rag-ingestion/"
        "official_answer_citation_agentic_loop_run_v1_failure_attribution.json"
    )
    assert summary["agentic_loop"]["implemented"] is True
    assert summary["agentic_loop"]["enabled"] is True
    assert summary["agentic_loop"]["backend"] in {"legacy", "graph"}
    assert summary["non_production_rag_index_dependency"]["canonical_path"] == "ai/eval/indexes/rag-data"
    assert summary["non_production_rag_index_dependency"]["worker_relative_path"] == "eval/indexes/rag-data"
    assert summary["non_production_rag_index_dependency"]["production_index_path_used"] is False
    assert summary["non_production_rag_index_dependency"]["build_command"] == (
        "cd ai && AIPIPELINE_WORKER_RAG_FAISS_BUILD_DEVICE=cuda "
        "python -m scripts.build_rag_index --fixture all "
        "--index-version official-answer-citation-agentic-loop-v1-nonprod-fixture-all"
    )
    assert summary["non_production_rag_index_dependency"]["build_metadata"] == {
        "faiss_build_device_requested": "cuda",
        "faiss_gpu_count": 1,
        "faiss_gpu_device": 0,
        "faiss_gpu_used": True,
    }
    assert summary["infrastructure_blocker"]["model_quality_regression"] is False
    if summary["failure_counts"] == {"GENERATION_PIPELINE_UNAVAILABLE": 29}:
        assert summary["status"] == "BLOCKED_ACTUAL_GENERATION_PIPELINE_UNAVAILABLE"
        assert summary["measurement_classification"] == "diagnostic_actual_generation_blocked_pipeline_unavailable"
        assert summary["scored_count"] == 0
        assert summary["pass_count"] == 0
        assert summary["agentic_loop"]["executed"] is False
        assert summary["infrastructure_blocker"]["category"] == "NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING"
    else:
        assert summary["status"] in {"PASS", "BLOCKED_OR_PARTIAL"}
        assert summary["measurement_classification"] == AGENTIC_DIAGNOSTIC_CLASSIFICATION
        assert summary["performance_interpretation"] == AGENTIC_DIAGNOSTIC_PERFORMANCE_INTERPRETATION
        assert summary["infrastructure_blocker"]["baseline_comparison_is_model_quality_comparable"] is False
        assert summary["corpus_coverage_verdict"]["verdict"] == (
            "fixture_all_index_not_official_denominator_representative"
        )
        assert summary["corpus_coverage_verdict"]["fixture_all_represents_official_mixed_denominator"] is False
        assert summary["corpus_coverage_verdict"]["official_denominator_source_bound_index"] is False
        assert summary["live_runner_verdict"]["current_run_uses_noop_llm"] is True
        assert summary["live_runner_verdict"]["generator"] == "ExtractiveGenerator"
        assert summary["live_runner_verdict"]["citation_locators_normalized_to_official_schema"] is False
        assert summary["diagnostic_limitations"]["chunk_only_citations_not_canonical_search_unit_payloads"] is True
        assert summary["diagnostic_limitations"]["current_pass_is_final_model_quality_regression"] is False
        assert summary["diagnostic_limitations"]["current_pass_is_promotion_evidence"] is False
        assert summary["source_bound_official_denominator_index_design"]["entrypoint_implemented"] is True
        assert summary["source_bound_official_denominator_index_design"]["blocker_category"] == SOURCE_BOUND_INDEX_BLOCKER
        assert summary["source_bound_official_denominator_index_design"]["build_ready"] is False
        assert summary["source_bound_official_denominator_index_design"]["target_index_built"] is False
        assert summary["source_bound_official_denominator_index_design"]["load_check_passed"] is False
        assert summary["source_bound_official_denominator_index_design"]["rerun_allowed"] is False
        assert summary["source_bound_official_denominator_index_design"]["production_index_path_used"] is False
        assert summary["source_bound_official_denominator_index_design"]["candidate_artifacts_as_generation_source"] is False
        assert summary["agentic_loop"]["actual_generation_pipeline_available"] is True
        assert summary["agentic_loop"]["executed"] is True
        assert "GENERATION_PIPELINE_UNAVAILABLE" not in summary["failure_counts"]
        assert all(
            row["generated_answer"] or row["generated_citations"] or row["failure_category"] != "GENERATION_PIPELINE_UNAVAILABLE"
            for row in results
        )
    assert summary["local_llm_used"] is False
    assert summary["local_gpu_used"] is True
    assert summary["guardrails"]["promotion_evidence"] is False
    assert summary["guardrails"]["generation_used_expected_answer"] is False
    assert summary["guardrails"]["generation_used_supporting_evidence"] is False
    assert summary["guardrails"]["denominator_mutation"] is False
    assert summary["guardrails"]["gold_mutation"] is False
    assert summary["guardrails"]["production_mutation"] is False
    assert summary["comparison_to_baseline"]["pass_delta"] == -7
    assert summary["comparison_to_baseline"]["per_track_pass_delta"] == {
        "pdf_business_ocr_mm": 0,
        "text_namu_v2_1": -6,
        "xlsx_business_structured": -1,
    }

    official_query_ids = {row["query_id"] for row in input_config["candidate_manifest"]}
    assert len(results) == 29
    assert {row["query_id"] for row in results} == official_query_ids
    assert all(row["run_id"] == AGENTIC_RUN_ID for row in results)
    assert all(row["promotion_evidence"] is False for row in results)
    assert all(row["generation_used_expected_answer"] is False for row in results)
    assert all(row["generation_used_supporting_evidence"] is False for row in results)
    assert all(row["generation_used_gold_fields"] is False for row in results)
    assert all(row["agentic_loop_enabled"] is True for row in results)
    assert all(row["local_llm_used"] is False for row in results)
    assert all(row["local_gpu_used"] is True for row in results)
    assert all("expected_answer" not in row for row in results)
    assert all("supporting_evidence" not in row for row in results)
    if summary["failure_counts"] == {"GENERATION_PIPELINE_UNAVAILABLE": 29}:
        assert all(row["agentic_loop_executed"] is False for row in results)
        assert all(row["failure_category"] == "GENERATION_PIPELINE_UNAVAILABLE" for row in results)
        assert all(row["infrastructure_blocker_category"] == "NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING" for row in results)
    else:
        assert any(row["agentic_loop_executed"] is True for row in results)
        assert all(row["failure_category"] != "GENERATION_PIPELINE_UNAVAILABLE" for row in results)

    assert "official_answer_citation_agentic_loop_run_v1" in summary_md
    assert AGENTIC_DIAGNOSTIC_CLASSIFICATION in summary_md
    assert "baseline comparable as model quality: `false`" in summary_md
    assert "model quality regression: `false`" in summary_md
    assert "chunk-only citation locators are not canonical SearchUnit payloads" in summary_md
    assert "FAISS GPU used for build: `true`" in summary_md
    assert "official first-run baseline was not overwritten" in summary_md
    latest = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_RUN_ID
    )
    assert latest["event_type"] == "official_answer_citation_agentic_loop_measurement"
    assert latest["run_id"] == AGENTIC_RUN_ID
    assert latest["result_count"] == 29
    assert latest["unique_query_id_count"] == 29
    assert latest["pass_count"] == summary["pass_count"]
    assert latest["measurement_classification"] == AGENTIC_DIAGNOSTIC_CLASSIFICATION
    assert latest["performance_interpretation"] == AGENTIC_DIAGNOSTIC_PERFORMANCE_INTERPRETATION
    assert latest["infrastructure_blocker"]["baseline_comparison_is_model_quality_comparable"] is False
    assert latest["source_bound_official_denominator_index_design"]["blocker_category"] == SOURCE_BOUND_INDEX_BLOCKER
    assert latest["non_production_rag_index_dependency"]["build_metadata"]["faiss_gpu_used"] is True
    assert latest["promotion_evidence"] is False
    assert first_run["failure_category_counts"] == {
        "CITATION_UNSUPPORTED": 11,
        "PARTIAL_OR_UNSUPPORTED": 10,
        "PASS": 8,
    }


def test_agentic_loop_failure_attribution_locks_diagnostic_interpretation() -> None:
    summary = read_json(AGENTIC_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_RESULTS)
    attribution = read_json(AGENTIC_ATTRIBUTION_JSON)
    status_events = read_jsonl(REPORT_DIR / "rag_current_eval_status.jsonl")

    assert attribution["run_id"] == AGENTIC_RUN_ID
    assert attribution["measurement_result"] == {
        "rows": 29,
        "unique_query_ids": 29,
        "scored_count": 29,
        "PASS": 1,
        "CITATION_UNSUPPORTED": 25,
        "PARTIAL_OR_UNSUPPORTED": 3,
    }
    assert attribution["performance_interpretation"] == (
        "diagnostic_retrieval_agent_loop_not_final_answer_generation_quality"
    )
    assert attribution["measurement_classification"] == (
        "diagnostic_live_generation_fixture_all_index_not_official_denominator_representative"
    )
    assert attribution["corpus_coverage_verdict"]["fixture_all_represents_official_mixed_denominator"] is False
    assert attribution["corpus_coverage_verdict"]["official_denominator_source_bound_index"] is False
    assert attribution["corpus_coverage_verdict"]["index_path"] == "ai/eval/indexes/rag-data"
    assert attribution["corpus_coverage_verdict"]["production_index_path_used"] is False
    assert attribution["corpus_coverage_verdict"]["candidate_index_path_used"] is False
    assert attribution["live_runner_verdict"]["canonical_live_generation_runner_available"] is False
    assert attribution["live_runner_verdict"]["current_run_uses_noop_llm"] is True
    assert attribution["live_runner_verdict"]["local_llm_backend_available"] is False
    assert attribution["live_runner_verdict"]["generator"] == "ExtractiveGenerator"
    assert attribution["structured_adapter_wiring_verdict"]["xlsx_candidate_adapter_wired_into_live_path"] is False
    assert attribution["structured_adapter_wiring_verdict"]["pdf_candidate_adapter_wired_into_live_path"] is False
    assert attribution["guardrails"]["promotion_evidence"] is False
    assert attribution["guardrails"]["generation_used_expected_answer"] is False
    assert attribution["guardrails"]["generation_used_supporting_evidence"] is False
    assert attribution["baseline_comparison_is_model_quality_comparable"] is False
    assert summary["measurement_classification"] == attribution["measurement_classification"]
    assert summary["performance_interpretation"] == attribution["performance_interpretation"]
    assert summary["infrastructure_blocker"]["baseline_comparison_is_model_quality_comparable"] is False

    design = attribution["source_bound_official_denominator_index_design"]
    assert design["status"] == "implemented_fail_closed_source_metadata_missing_or_unchecked"
    assert design["blocker_category"] == SOURCE_BOUND_INDEX_BLOCKER
    assert design["target_index_path"] == "ai/eval/indexes/rag-data-official-denominator-v1"
    assert design["entrypoint_implemented"] is True
    assert design["build_ready"] is False
    assert design["target_index_built"] is False
    assert design["load_check_passed"] is False
    assert design["rerun_allowed"] is False
    assert design["production_index_path_used"] is False
    assert design["candidate_index_path_used"] is False
    assert design["candidate_artifacts_as_generation_source"] is False
    assert design["required_fields_by_track"]["text_namu_v2_1"] == [
        "document_id",
        "document_version_id",
        "search_unit_id",
        "text_locator",
    ]
    assert "workbook" in design["required_fields_by_track"]["xlsx_business_structured"]
    assert "bbox" in design["required_fields_by_track"]["pdf_business_ocr_mm"]

    rows = attribution["row_level_attribution"]
    assert len(rows) == 29
    assert {row["query_id"] for row in rows} == {row["query_id"] for row in results}
    assert all(row["primary_attribution"] in ALLOWED_AGENTIC_ATTRIBUTION_CATEGORIES for row in rows)
    assert all(
        set(row["secondary_attributions"]).issubset(ALLOWED_AGENTIC_ATTRIBUTION_CATEGORIES)
        for row in rows
    )
    assert all(row["generation_used_expected_answer"] is False for row in rows)
    assert all(row["generation_used_supporting_evidence"] is False for row in rows)
    assert all(row["generated_answer_present"] is True for row in rows)
    assert all(row["generated_citations_present"] is True for row in rows)
    assert all(row["citation_payload_points_to_retrieved_evidence"] is True for row in rows)
    assert all(row["citation_locator_scorer_compatible"] is False for row in rows)
    assert all(row["retrieved_source_matches_expected_official_source_family"] is False for row in rows)
    assert all(row["llm_backend_noop_limitation"] is True for row in rows)

    assert attribution["primary_attribution_counts"] == {
        "CORPUS_COVERAGE_MISS": 6,
        "SCORER_COMPATIBILITY_MISMATCH": 1,
        "STRUCTURED_ADAPTER_NOT_WIRED": 22,
    }
    assert attribution["per_track_primary_attribution_counts"] == {
        "pdf_business_ocr_mm": {
            "SCORER_COMPATIBILITY_MISMATCH": 1,
            "STRUCTURED_ADAPTER_NOT_WIRED": 3,
        },
        "text_namu_v2_1": {"CORPUS_COVERAGE_MISS": 6},
        "xlsx_business_structured": {"STRUCTURED_ADAPTER_NOT_WIRED": 19},
    }

    latest = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_failure_attribution"
        and event.get("run_id") == AGENTIC_RUN_ID
    )
    assert latest["run_id"] == AGENTIC_RUN_ID
    assert latest["measurement_classification"] == attribution["measurement_classification"]
    assert latest["performance_interpretation"] == attribution["performance_interpretation"]
    assert latest["primary_attribution_counts"] == attribution["primary_attribution_counts"]
    assert latest["baseline_comparison_is_model_quality_comparable"] is False
    assert latest["source_bound_official_denominator_index_design"]["blocker_category"] == SOURCE_BOUND_INDEX_BLOCKER
    assert latest["guardrails"]["promotion_evidence"] is False
    assert summary["artifact_provenance"]["report_only_candidates_promoted"] is False


def test_source_bound_readiness_artifact_records_build_and_load_check_passed() -> None:
    readiness = read_json(READINESS_JSON)
    status_events = read_jsonl(REPORT_DIR / "rag_current_eval_status.jsonl")

    assert readiness["entrypoint_implemented"] is True
    assert readiness["status"] == "BUILD_READY_LOAD_CHECK_PASSED"
    assert readiness["blocker_category"] is None
    assert readiness["target_index_path"] == "ai/eval/indexes/rag-data-official-denominator-v1"
    assert readiness["index_version"] == (
        "official-answer-citation-agentic-loop-v1-nonprod-official-denominator-source-bound"
    )
    assert readiness["official_denominator_rows"] == 29
    assert readiness["official_rows_by_track"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 6,
            "xlsx_business_structured": 19,
    }
    assert readiness["blocked_query_ids"] == []
    assert readiness["missing_fields_by_query_id"] == {}
    assert readiness["missing_source_files_by_query_id"] == {}
    assert readiness["source_bound_locators_by_query_id"]["text_namu_v2_0005"][
        "text_locator"
    ]["source_corpus_path"] == "ai/eval/corpora/namu-v4-structured-combined/rag_chunks.jsonl"
    assert readiness["source_bound_locators_by_query_id"]["gq_auto_012"]["row_label"] == (
        "대중교통구분=지하철 | 노선명=5호선 | 년월=201902"
    )
    assert readiness["source_bound_locators_by_query_id"]["gq_auto_012"][
        "target_column"
    ] == "승차총승객수"
    assert readiness["source_bound_locators_by_query_id"]["gq_auto_012"][
        "normalized_value"
    ] == "15446522"
    assert readiness["source_file_inventory_by_query_id"]["gq_auto_012"][0]["exists"] is True
    pdf_inventory = readiness["source_file_inventory_by_query_id"]["gq_auto_010"][0]
    assert pdf_inventory["exists"] is True
    assert pdf_inventory["kind"] == "pdf_locator_manifest"
    assert pdf_inventory["reference"] == "2847f7af-cfe4-41de-8393-58912df2dba9"
    assert pdf_inventory["document_version_id"] == "docv_fe2470815512a395"
    assert pdf_inventory["search_unit_id"] == "7bf516bf-2a17-4303-86d8-3cffaa04846e"
    assert pdf_inventory["source_pdf_path_resolved"] is True
    assert "D:/_external_runtime_artifacts/" in pdf_inventory["source_path"]
    pdf_locator = readiness["source_bound_locators_by_query_id"]["gq_auto_010"]
    assert pdf_locator["source_pdf_path"].endswith("2021_03_recent_economic_trends.pdf")
    assert pdf_locator["document_version_id"] == "docv_fe2470815512a395"
    assert pdf_locator["row_label"] == "▪ 실업률은 모든 연령계층에서 상승"
    assert pdf_locator["target_column"] == "paragraph_text"
    assert pdf_locator["pdf_source_text_locator"]["method"] == "pymupdf_source_pdf_text"
    assert "D:/_external_runtime_artifacts/" in pdf_locator["source_locator_manifest_path"]
    assert "D:/_external_runtime_artifacts/" in "\n".join(readiness["source_roots_checked"])
    assert "D:/_external_workspace_archive/" in "\n".join(readiness["source_roots_checked"])
    assert readiness["build_ready"] is True
    assert readiness["target_index_built"] is True
    assert readiness["load_check_passed"] is True
    assert readiness["rerun_allowed"] is True
    assert readiness["index_build_result"]["official_denominator_rows"] == 29
    assert readiness["index_load_check"]["passed"] is True
    assert readiness["index_load_check"]["track_counts"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 6,
        "xlsx_business_structured": 19,
    }
    assert readiness["candidate_artifacts_as_generation_source"] is False
    assert readiness["generation_used_expected_answer"] is False
    assert readiness["generation_used_supporting_evidence"] is False
    assert readiness["production_index_path_used"] is False
    assert readiness["candidate_index_path_used"] is False
    assert readiness["promotion_evidence"] is False

    assert set(readiness["required_fields_by_track"]["text_namu_v2_1"]) == {
        "document_id",
        "document_version_id",
        "search_unit_id",
        "text_locator",
    }
    assert readiness["required_fields_by_track"]["xlsx_business_structured"] == [
        "workbook",
        "sheet",
        "range",
        "cell",
        "row_label",
        "target_column",
        "normalized_value",
        "search_unit_id",
        "document_version_id",
    ]
    assert readiness["required_fields_by_track"]["pdf_business_ocr_mm"] == [
        "source_pdf_path",
        "page",
        "physical_page_index",
        "bbox",
        "region_type",
        "row_label",
        "target_column",
        "search_unit_id",
        "document_version_id",
    ]

    latest = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_source_bound_index_preparation"
    )
    assert latest["source_bound_official_denominator_index_design"]["entrypoint_implemented"] is True
    assert latest["source_bound_official_denominator_index_design"]["blocker_category"] is None
    assert latest["source_bound_official_denominator_index_design"]["blocked_query_count"] == 0
    assert latest["source_bound_official_denominator_index_design"]["required_field_complete_counts"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 6,
        "xlsx_business_structured": 19,
    }
    assert latest["source_bound_official_denominator_index_design"]["source_identity_resolved_counts"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 6,
        "xlsx_business_structured": 19,
    }
    assert latest["source_bound_official_denominator_index_design"]["missing_fields_by_query_id"] == {}
    assert latest["source_bound_official_denominator_index_design"]["missing_source_files_by_query_id"] == {}
    assert latest["source_bound_official_denominator_index_design"]["target_index_built"] is True
    assert latest["source_bound_official_denominator_index_design"]["load_check_passed"] is True
    assert latest["source_bound_official_denominator_index_design"]["rerun_allowed"] is True
    assert latest["search_unit_citation_payload_wired"] is True
    assert latest["xlsx_source_bound_adapter_opt_in_wired"] is True
    assert latest["pdf_source_bound_adapter_opt_in_wired"] is True
    assert latest["guardrails"]["gold_mutation"] is False
    assert latest["guardrails"]["denominator_mutation"] is False
    assert latest["guardrails"]["production_mutation"] is False


def test_v2_source_bound_diagnostic_artifacts_are_separate_and_guarded() -> None:
    summary = read_json(AGENTIC_V2_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V2_RESULTS)
    attribution = read_json(AGENTIC_V2_ATTRIBUTION_JSON)
    status_events = read_jsonl(REPORT_DIR / "rag_current_eval_status.jsonl")

    assert summary["run_id"] == AGENTIC_V2_RUN_ID
    assert summary["status"] == "BLOCKED_OR_PARTIAL"
    assert summary["diagnostic_only"] is True
    assert summary["llm_backend"] == "noop"
    assert "noop/extractive" in summary["llm_backend_limitation"]
    assert summary["artifact_provenance"]["immutable_first_run_baseline_overwritten"] is False
    assert summary["artifact_provenance"]["report_only_candidates_promoted"] is False
    assert summary["artifact_provenance"]["run_id_separate_from_first_run"] is True
    assert summary["result_count"] == 29
    assert summary["unique_query_id_count"] == 29
    assert summary["scored_count"] == 20
    assert summary["pass_count"] == 20
    assert summary["failure_counts"] == {
        "PASS": 20,
        "SEARCH_UNIT_LOCATOR_INCOMPLETE": 5,
        "STRUCTURED_LOCATOR_DROPPED": 4,
    }
    assert summary["measurement_classification"] == AGENTIC_V2_RUN_ID
    assert summary["performance_interpretation"] == "source_bound_official_denominator_backend_limited_diagnostic"
    assert summary["source_bound_index_used"] is True
    assert summary["non_production_rag_index_dependency"]["canonical_path"] == (
        "ai/eval/indexes/rag-data-official-denominator-v1"
    )
    assert summary["non_production_rag_index_dependency"]["worker_relative_path"] == (
        "eval/indexes/rag-data-official-denominator-v1"
    )
    assert summary["non_production_rag_index_dependency"]["preflight_errors"] == []
    assert summary["non_production_rag_index_dependency"]["source_bound_artifact_contract_ok"] is True
    assert summary["non_production_rag_index_dependency"]["source_bound_index_load_checked"] is True
    assert summary["non_production_rag_index_dependency"]["satisfied"] is True
    assert summary["non_production_rag_index_dependency"]["rerun_allowed"] is True
    assert summary["non_production_rag_index_dependency"]["candidate_index_path_used"] is False
    assert summary["non_production_rag_index_dependency"]["production_index_path_used"] is False
    assert summary["non_production_rag_index_dependency"]["search_unit_manifest_metadata"] == {
        "all_source_bound": True,
        "row_count": 29,
        "track_counts": {
            "pdf_business_ocr_mm": 4,
            "text_namu_v2_1": 6,
            "xlsx_business_structured": 19,
        },
        "unique_query_id_count": 29,
        "unique_search_unit_id_count": 29,
    }
    assert summary["non_production_rag_index_dependency"]["readiness_artifact"] == {
        "blocked_query_ids": [],
        "load_check_passed": True,
        "missing_fields_by_query_id": {},
        "missing_source_files_by_query_id": {},
        "official_denominator_rows": 29,
        "official_rows_by_track": {
            "pdf_business_ocr_mm": 4,
            "text_namu_v2_1": 6,
            "xlsx_business_structured": 19,
        },
        "path": "ai/eval/reports/rag-ingestion/official_answer_citation_source_bound_index_build_readiness_v1.json",
        "rerun_allowed": True,
        "status": "BUILD_READY_LOAD_CHECK_PASSED",
        "target_index_built": True,
        "target_index_path": "ai/eval/indexes/rag-data-official-denominator-v1",
    }
    assert summary["canonical_search_unit_payload_used"] is True
    assert summary["search_unit_citation_payloads_used"] is True
    assert summary["xlsx_pdf_structured_adapters_enabled"] is True
    assert summary["adapter_output_from_source_bound_search_units"] is False
    assert summary["candidate_artifacts_as_generation_source"] is False
    assert summary["generation_used_expected_answer"] is False
    assert summary["generation_used_supporting_evidence"] is False
    assert summary["generation_used_gold_fields"] is False
    assert summary["promotion_evidence"] is False
    assert summary["baseline_comparison_is_model_quality_comparable"] is False
    assert summary["official_score_category_counts"]["PASS"] == summary["pass_count"]
    assert summary["official_score_category_counts"] == {
        "PASS": 20,
        "CITATION_UNSUPPORTED": 0,
        "PARTIAL_OR_UNSUPPORTED": 0,
    }
    assert summary["per_track_counts"] == {
        "pdf_business_ocr_mm": {
            "failure_counts": {"STRUCTURED_LOCATOR_DROPPED": 4},
            "pass_count": 0,
            "row_count": 4,
            "scored_count": 0,
        },
        "text_namu_v2_1": {
            "failure_counts": {"PASS": 1, "SEARCH_UNIT_LOCATOR_INCOMPLETE": 5},
            "pass_count": 1,
            "row_count": 6,
            "scored_count": 1,
        },
        "xlsx_business_structured": {
            "failure_counts": {"PASS": 19},
            "pass_count": 19,
            "row_count": 19,
            "scored_count": 19,
        },
    }

    assert len(results) == 29
    assert len({row["query_id"] for row in results}) == 29
    assert Counter(row["track"] for row in results) == Counter(
        {"xlsx_business_structured": 19, "text_namu_v2_1": 6, "pdf_business_ocr_mm": 4}
    )
    assert Counter(row["failure_category"] for row in results) == Counter(
        {"PASS": 20, "SEARCH_UNIT_LOCATOR_INCOMPLETE": 5, "STRUCTURED_LOCATOR_DROPPED": 4}
    )
    assert Counter(row["score_status"] for row in results) == Counter({"PASS": 20, "FAIL_CLOSED": 9})
    assert all(row["run_id"] == AGENTIC_V2_RUN_ID for row in results)
    assert all("expected_answer" not in row for row in results)
    assert all("supporting_evidence" not in row for row in results)
    assert all(row["generation_used_expected_answer"] is False for row in results)
    assert all(row["generation_used_supporting_evidence"] is False for row in results)
    assert all(row["generation_used_gold_fields"] is False for row in results)
    assert all(row["promotion_evidence"] is False for row in results)
    assert all(row["search_unit_citation_payloads_used"] is True for row in results)
    assert all(row["structured_source_bound_adapters_enabled"] is True for row in results)
    assert any(
        citation.get("structured_adapter_output_from_source_bound_search_unit") is True
        for row in results
        for citation in row["generated_citations"]
    )
    assert not all(
        any(citation.get("structured_adapter_output_from_source_bound_search_unit") is True for citation in row["generated_citations"])
        for row in results
    )

    assert attribution["run_id"] == AGENTIC_V2_RUN_ID
    assert attribution["source_bound_index_used"] is True
    assert attribution["canonical_search_unit_payload_used"] is True
    assert attribution["adapter_output_from_source_bound_search_units"] is False
    assert attribution["baseline_comparison_is_model_quality_comparable"] is False
    assert attribution["primary_attribution_counts"] == {"CITATION_PAYLOAD_SCHEMA_MISMATCH": 9, "PASS": 20}
    assert attribution["per_track_primary_attribution_counts"] == {
        "pdf_business_ocr_mm": {"CITATION_PAYLOAD_SCHEMA_MISMATCH": 4},
        "text_namu_v2_1": {"CITATION_PAYLOAD_SCHEMA_MISMATCH": 5, "PASS": 1},
        "xlsx_business_structured": {"PASS": 19},
    }
    assert set(attribution["primary_attribution_counts"]).issubset(ALLOWED_V2_ATTRIBUTION_CATEGORIES)
    assert all(
        row["primary_attribution"] in ALLOWED_V2_ATTRIBUTION_CATEGORIES
        for row in attribution["row_level_attribution"]
    )
    assert all(
        row["generation_used_expected_answer"] is False
        and row["generation_used_supporting_evidence"] is False
        and row["generation_used_gold_fields"] is False
        and row["promotion_evidence"] is False
        for row in attribution["row_level_attribution"]
    )

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V2_RUN_ID
    )
    assert measurement["source_bound_index_used"] is True
    assert measurement["candidate_artifacts_as_generation_source"] is False
    assert measurement["generation_used_expected_answer"] is False
    assert measurement["generation_used_supporting_evidence"] is False
    assert measurement["generation_used_gold_fields"] is False
    assert measurement["promotion_evidence"] is False
    assert measurement["baseline_comparison_is_model_quality_comparable"] is False
    assert measurement["result_count"] == 29
    assert measurement["unique_query_id_count"] == 29
    assert measurement["scored_count"] == 20
    assert measurement["pass_count"] == 20
    assert measurement["adapter_output_from_source_bound_search_units"] is False

    failure_attribution = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_failure_attribution"
        and event.get("run_id") == AGENTIC_V2_RUN_ID
    )
    assert failure_attribution["primary_attribution_counts"] == {
        "CITATION_PAYLOAD_SCHEMA_MISMATCH": 9,
        "PASS": 20,
    }
    assert failure_attribution["source_bound_index_used"] is True
    assert failure_attribution["canonical_search_unit_payload_used"] is True
    assert failure_attribution["adapter_output_from_source_bound_search_units"] is False
    assert failure_attribution["baseline_comparison_is_model_quality_comparable"] is False
    assert failure_attribution["guardrails"]["promotion_evidence"] is False


def test_v2_1_citation_contract_repair_artifacts_discard_off_track_citations() -> None:
    summary = read_json(AGENTIC_V2_1_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V2_1_RESULTS)
    attribution = read_json(AGENTIC_V2_1_ATTRIBUTION_JSON)
    status_events = read_jsonl(REPORT_DIR / "rag_current_eval_status.jsonl")

    assert summary["run_id"] == AGENTIC_V2_1_RUN_ID
    assert summary["measurement_classification"] == AGENTIC_V2_1_RUN_ID
    assert summary["status"] == "BLOCKED_OR_PARTIAL"
    assert summary["diagnostic_only"] is True
    assert summary["llm_backend"] == "noop"
    assert summary["source_bound_index_used"] is True
    assert summary["result_count"] == 29
    assert summary["unique_query_id_count"] == 29
    assert summary["scored_count"] == 29
    assert summary["pass_count"] == 26
    assert summary["failure_counts"] == {
        "CITATION_UNSUPPORTED": 1,
        "PARTIAL_OR_UNSUPPORTED": 2,
        "PASS": 26,
    }
    assert summary["discarded_off_track_citation_count"] == 22
    assert summary["same_track_valid_citation_count"] == 123
    assert summary["query_bound_scored_citation_count"] == 29
    assert summary["non_query_bound_same_track_scored_citation_count"] == 94
    assert summary["schema_mismatch_residual_count"] == 0
    assert summary["all_generated_citations_source_bound"] is True
    assert summary["same_track_generated_citations_source_bound"] is True
    assert summary["scored_citations_source_bound"] is True
    assert summary["adapter_output_for_same_track_citations"] is True
    assert summary["adapter_output_from_source_bound_search_units"] is True
    assert summary["candidate_artifacts_as_generation_source"] is False
    assert summary["generation_used_expected_answer"] is False
    assert summary["generation_used_supporting_evidence"] is False
    assert summary["generation_used_gold_fields"] is False
    assert summary["promotion_evidence"] is False
    assert summary["baseline_comparison_is_model_quality_comparable"] is False
    assert summary["per_track_counts"] == {
        "pdf_business_ocr_mm": {
            "failure_counts": {"CITATION_UNSUPPORTED": 1, "PARTIAL_OR_UNSUPPORTED": 1, "PASS": 2},
            "pass_count": 2,
            "row_count": 4,
            "scored_count": 4,
        },
        "text_namu_v2_1": {
            "failure_counts": {"PARTIAL_OR_UNSUPPORTED": 1, "PASS": 5},
            "pass_count": 5,
            "row_count": 6,
            "scored_count": 6,
        },
        "xlsx_business_structured": {
            "failure_counts": {"PASS": 19},
            "pass_count": 19,
            "row_count": 19,
            "scored_count": 19,
        },
    }

    assert len(results) == 29
    assert all(row["run_id"] == AGENTIC_V2_1_RUN_ID for row in results)
    assert all("expected_answer" not in row for row in results)
    assert all("supporting_evidence" not in row for row in results)
    assert all(row["generation_used_expected_answer"] is False for row in results)
    assert all(row["generation_used_supporting_evidence"] is False for row in results)
    assert all(row["generation_used_gold_fields"] is False for row in results)
    assert all(row["promotion_evidence"] is False for row in results)
    assert all(row["same_track_valid_citation_count"] > 0 for row in results)
    assert all(row["schema_mismatch_residual_count"] == 0 for row in results)
    assert not any(
        "#xlsx_business_structured" in row["generated_answer"]
        for row in results
        if row["track"] != "xlsx_business_structured"
    )
    assert all(
        citation["citation_payload_validation"]["manifest_track"] == row["track"]
        for row in results
        for citation in row["scored_citations"]
    )
    assert all(
        citation["citation_payload_validation"]["category"] == "OFF_TRACK_CITATION_FOR_QUERY_TRACK"
        for row in results
        for citation in row["discarded_off_track_citations"]
    )
    assert sum(row["discarded_off_track_citation_count"] for row in results) == 22
    assert any(row["discarded_off_track_citation_count"] > 0 for row in results if row["track"] == "pdf_business_ocr_mm")
    assert any(row["discarded_off_track_citation_count"] > 0 for row in results if row["track"] == "text_namu_v2_1")
    assert not any(
        citation["search_unit_citation_payload"]["track"] != row["track"]
        for row in results
        for citation in row["scored_citations"]
    )
    assert all(
        citation["search_unit_citation_payload"]["manifest_query_id"]
        == citation["citation_payload_validation"]["manifest_query_id"]
        for row in results
        for citation in row["generated_citations"]
    )
    assert all(
        citation["citation_payload_validation"]["row_query_id"] == row["query_id"]
        for row in results
        for citation in row["generated_citations"]
    )

    assert attribution["run_id"] == AGENTIC_V2_1_RUN_ID
    assert attribution["source_bound_index_used"] is True
    assert attribution["canonical_search_unit_payload_used"] is True
    assert attribution["discarded_off_track_citation_count"] == 22
    assert attribution["same_track_valid_citation_count"] == 123
    assert attribution["query_bound_scored_citation_count"] == 29
    assert attribution["non_query_bound_same_track_scored_citation_count"] == 94
    assert attribution["schema_mismatch_residual_count"] == 0
    assert attribution["primary_attribution_counts"] == {"ANSWER_SYNTHESIS_LIMITATION": 3, "PASS": 26}
    assert attribution["per_track_primary_attribution_counts"] == {
        "pdf_business_ocr_mm": {"ANSWER_SYNTHESIS_LIMITATION": 2, "PASS": 2},
        "text_namu_v2_1": {"ANSWER_SYNTHESIS_LIMITATION": 1, "PASS": 5},
        "xlsx_business_structured": {"PASS": 19},
    }
    assert attribution["baseline_comparison_is_model_quality_comparable"] is False
    assert attribution["guardrails"]["promotion_evidence"] is False

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V2_1_RUN_ID
    )
    assert measurement["discarded_off_track_citation_count"] == 22
    assert measurement["same_track_valid_citation_count"] == 123
    assert measurement["query_bound_scored_citation_count"] == 29
    assert measurement["non_query_bound_same_track_scored_citation_count"] == 94
    assert measurement["schema_mismatch_residual_count"] == 0
    assert measurement["candidate_artifacts_as_generation_source"] is False
    assert measurement["generation_used_expected_answer"] is False
    assert measurement["generation_used_supporting_evidence"] is False
    assert measurement["generation_used_gold_fields"] is False
    assert measurement["promotion_evidence"] is False
    assert "source-bound denominator index" in summary["pipeline_decision"]["rationale"]
    assert "registry-backed RAG pipeline" not in summary["pipeline_decision"]["rationale"]


def test_agentic_available_pipeline_row_exception_is_specific_not_pipeline_unavailable() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    class BoomRetriever:
        def retrieve(self, _query: str) -> object:
            raise RuntimeError("synthetic retriever failure after index availability")

    args = SimpleNamespace(
        agent_loop_backend="legacy",
        agent_max_iter=1,
        agent_max_total_ms=1000,
        agent_max_llm_tokens=1000,
        agent_min_stop_confidence=0.0,
    )
    rows = [
        {
            "query_id": "q-row-failure",
            "track": "text_namu_v2_1",
            "question": "실패 분기 확인용 질문",
            "expected_answer": "sentinel answer",
            "supporting_evidence": "sentinel evidence",
        }
    ]

    out = runner.execute_agentic_generation_rows(rows, args, {"_retriever": BoomRetriever()})

    assert len(out) == 1
    row = out[0]
    assert row["failure_category"] == runner.AGENTIC_GENERATION_ROW_FAILED
    assert row["failure_category"] != runner.GENERATION_PIPELINE_UNAVAILABLE
    assert row["agentic_loop_enabled"] is True
    assert row["agentic_loop_executed"] is True
    assert row["scoring_attempted"] is False
    assert row["generated_answer"] == ""
    assert row["generated_citations"] == []
    assert row["retrieved_evidence"] == []
    assert row["infrastructure_blocker_category"] is None


def test_faiss_cuda_build_fails_closed_when_gpu_api_unavailable(
    tmp_path, monkeypatch
) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from app.capabilities.rag import faiss_index as faiss_index_module
    from app.capabilities.rag.faiss_index import FaissIndex

    monkeypatch.setattr(faiss_index_module, "_faiss_gpu_ready", lambda: False)
    monkeypatch.setattr(faiss_index_module, "_faiss_gpu_count", lambda: 0)
    index = FaissIndex(tmp_path / "idx", build_device="cuda")

    with pytest.raises(RuntimeError, match="FAISS GPU build requested"):
        index.build(
            np.ones((2, 4), dtype=np.float32),
            index_version="gpu-required",
            embedding_model="hashing",
        )


def test_faiss_cuda_build_records_gpu_metadata(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from app.capabilities.rag import faiss_index as faiss_index_module
    from app.capabilities.rag.faiss_index import FaissIndex

    calls: list[tuple[str, int | None]] = []

    class _FakeGpuIndex:
        def __init__(self, cpu_index):
            self.cpu_index = cpu_index

        def add(self, vectors):
            calls.append(("add", int(vectors.shape[0])))
            self.cpu_index.add(vectors)

    def _to_gpu(_resources, device, cpu_index):
        calls.append(("to_gpu", int(device)))
        return _FakeGpuIndex(cpu_index)

    def _to_cpu(gpu_index):
        calls.append(("to_cpu", None))
        return gpu_index.cpu_index

    monkeypatch.setattr(faiss_index_module, "_faiss_gpu_ready", lambda: True)
    monkeypatch.setattr(faiss_index_module, "_faiss_gpu_count", lambda: 1)
    monkeypatch.setattr(
        faiss_index_module.faiss,
        "StandardGpuResources",
        lambda: object(),
        raising=False,
    )
    monkeypatch.setattr(
        faiss_index_module.faiss,
        "index_cpu_to_gpu",
        _to_gpu,
        raising=False,
    )
    monkeypatch.setattr(
        faiss_index_module.faiss,
        "index_gpu_to_cpu",
        _to_cpu,
        raising=False,
    )

    index = FaissIndex(tmp_path / "idx", build_device="cuda")
    index.build(
        np.ones((2, 4), dtype=np.float32),
        index_version="gpu-used",
        embedding_model="hashing",
    )

    payload = json.loads((tmp_path / "idx" / "build.json").read_text())
    assert payload["faiss_build_device_requested"] == "cuda"
    assert payload["faiss_gpu_used"] is True
    assert payload["faiss_gpu_count"] == 1
    assert payload["faiss_gpu_device"] == 0
    assert calls == [("to_gpu", 0), ("add", 2), ("to_cpu", None)]


def test_sentence_transformer_embedder_exposes_configured_max_seq_length_for_ingest_manifest() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from app.capabilities.rag.embeddings import SentenceTransformerEmbedder

    embedder = SentenceTransformerEmbedder("BAAI/bge-m3", max_seq_length=1024)

    assert embedder.max_seq_length == 1024


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
