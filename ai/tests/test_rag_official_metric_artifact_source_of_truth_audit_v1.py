from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "ai" / "eval" / "reports" / "rag-ingestion"
REPORT_ARCHIVE_DIR = REPORT_DIR / "_archive" / "legacy"
EXTERNAL_REPORT_ARCHIVE_DIR = Path(
    "D:/_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/"
    "rag-ingestion/repo-wide-cleanup-20260519/reports/rag-ingestion-legacy"
)
README = ROOT / "README.md"
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
MEASUREMENTS_DOC = ROOT / "docs" / "rag-ingestion-measurements.md"
TRIAGE_DOC = ROOT / "docs" / "rag-ingestion-triage.md"
REPAIRED_PDF_QUERY_IDS = ("gq_auto_010", "gq_auto_030", "gq_pdf_section_question_001")
RESIDUAL_AUDIT_QUERY_IDS = {
    "gq_auto_030",
    "gq_pdf_section_question_001",
    "text_namu_v2_0017",
}
AGENTIC_RUN_ID = "official_answer_citation_agentic_loop_run_v1"
AGENTIC_V2_RUN_ID = "official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic"
AGENTIC_V2_1_RUN_ID = "official_answer_citation_agentic_loop_run_v2_1_citation_contract_repair"
AGENTIC_V2_2_RUN_ID = "official_answer_citation_agentic_loop_run_v2_2_llm_backend_validation"
AGENTIC_V3_RUN_ID = "official_answer_citation_agentic_loop_run_v3_comparable_live_measurement"
AGENTIC_V3_1_RUN_ID = "official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement"
AGENTIC_V3_1_PRIORITY_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage"
)
AGENTIC_V3_1_PRIORITY_STRICT_JSON_DIAGNOSTICS_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_priority_1_5_triage_strict_json_diagnostics"
)
AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage"
)
AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage"
)
AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage"
)
AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_3_remaining_queue_answer_span_renderer_triage"
)
AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_4_pdf_residual_answer_span_renderer_triage"
)
AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic"
)
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic"
)
AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit"
)
AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation"
)
AGENTIC_V3_1_PRIORITY_QUERY_IDS = (
    "gq_pdf_section_question_001",
    "text_namu_v2_0012",
    "gq_auto_010",
    "gq_auto_023",
    "gq_xlsx_lookup_008",
)
AGENTIC_DIAGNOSTIC_CLASSIFICATION = (
    "diagnostic_live_generation_fixture_all_index_not_official_denominator_representative"
)
AGENTIC_DIAGNOSTIC_PERFORMANCE_INTERPRETATION = (
    "diagnostic_retrieval_agent_loop_not_final_answer_generation_quality"
)
SOURCE_BOUND_INDEX_BLOCKER = "SOURCE_BOUND_OFFICIAL_DENOMINATOR_SOURCE_FIELDS_MISSING"
REPORT_ARTIFACT_SLUGS = {
    AGENTIC_RUN_ID: "agentic_v1",
    AGENTIC_V2_RUN_ID: "v2_source_bound",
    AGENTIC_V2_1_RUN_ID: "v2_1_citation",
    AGENTIC_V2_2_RUN_ID: "v2_2_backend",
    AGENTIC_V3_RUN_ID: "v3_comparable",
    AGENTIC_V3_1_RUN_ID: "v3_1_foundation",
    AGENTIC_V3_1_PRIORITY_RUN_ID: "v3_1_priority",
    AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID: "v3_1_textloc",
    AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID: "v3_1_1_post_locator",
    AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID: "v3_1_2_span",
    AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID: "v3_1_3_remaining",
    AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID: "v3_1_4_pdf_residual",
    AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID: "v3_1_5_gq010_coverage",
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID: "v3_1_6_gq010_pdfwin",
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID: AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID: AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
}
ARCHIVED_REPORT_RUN_IDS = set(REPORT_ARTIFACT_SLUGS) - {
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID,
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
}


def report_artifact_dir(run_id: str) -> Path:
    if run_id not in ARCHIVED_REPORT_RUN_IDS:
        return REPORT_DIR
    return REPORT_ARCHIVE_DIR if REPORT_ARCHIVE_DIR.exists() else EXTERNAL_REPORT_ARCHIVE_DIR


def archived_report_dir() -> Path:
    return REPORT_ARCHIVE_DIR if REPORT_ARCHIVE_DIR.exists() else EXTERNAL_REPORT_ARCHIVE_DIR


def report_artifact_path(run_id: str, suffix: str) -> Path:
    return report_artifact_dir(run_id) / f"{REPORT_ARTIFACT_SLUGS[run_id]}_{suffix}"


def report_artifact_repo_relative(run_id: str, suffix: str) -> str:
    logical_dir = REPORT_ARCHIVE_DIR if run_id in ARCHIVED_REPORT_RUN_IDS else REPORT_DIR
    return (logical_dir / f"{REPORT_ARTIFACT_SLUGS[run_id]}_{suffix}").relative_to(ROOT).as_posix()


READINESS_JSON = REPORT_DIR / "source_bound_readiness_v1.json"
AGENTIC_RESULTS = report_artifact_path(AGENTIC_RUN_ID, "results.jsonl")
AGENTIC_SUMMARY_JSON = report_artifact_path(AGENTIC_RUN_ID, "summary.json")
AGENTIC_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_RUN_ID, "failure.json")
AGENTIC_V2_RESULTS = report_artifact_path(AGENTIC_V2_RUN_ID, "results.jsonl")
AGENTIC_V2_SUMMARY_JSON = report_artifact_path(AGENTIC_V2_RUN_ID, "summary.json")
AGENTIC_V2_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V2_RUN_ID, "failure.json")
AGENTIC_V2_1_RESULTS = report_artifact_path(AGENTIC_V2_1_RUN_ID, "results.jsonl")
AGENTIC_V2_1_SUMMARY_JSON = report_artifact_path(AGENTIC_V2_1_RUN_ID, "summary.json")
AGENTIC_V2_1_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V2_1_RUN_ID, "failure.json")
AGENTIC_V2_2_RESULTS = report_artifact_path(AGENTIC_V2_2_RUN_ID, "results.jsonl")
AGENTIC_V2_2_SUMMARY_JSON = report_artifact_path(AGENTIC_V2_2_RUN_ID, "summary.json")
AGENTIC_V2_2_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V2_2_RUN_ID, "failure.json")
AGENTIC_V3_RESULTS = report_artifact_path(AGENTIC_V3_RUN_ID, "results.jsonl")
AGENTIC_V3_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_RUN_ID, "summary.json")
AGENTIC_V3_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_RUN_ID, "failure.json")
AGENTIC_V3_1_RESULTS = report_artifact_path(AGENTIC_V3_1_RUN_ID, "results.jsonl")
AGENTIC_V3_1_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_RUN_ID, "summary.json")
AGENTIC_V3_1_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_RUN_ID, "failure.json")
AGENTIC_V3_1_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_TRIAGE_JSON = report_artifact_path(AGENTIC_V3_1_RUN_ID, "queue.json")
AGENTIC_V3_1_PRIORITY_RESULTS = report_artifact_path(AGENTIC_V3_1_PRIORITY_RUN_ID, "results.jsonl")
AGENTIC_V3_1_PRIORITY_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_PRIORITY_RUN_ID, "summary.json")
AGENTIC_V3_1_PRIORITY_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_PRIORITY_RUN_ID, "failure.json")
AGENTIC_V3_1_PRIORITY_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_PRIORITY_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_PRIORITY_STRICT_JSON_DIAGNOSTICS_JSON = REPORT_ARCHIVE_DIR / "v3_1_priority_strict_json.json"
AGENTIC_V3_1_PRIORITY_TRIAGE_DELTA_JSON = report_artifact_path(AGENTIC_V3_1_PRIORITY_RUN_ID, "delta.json")
AGENTIC_V3_1_TEXT_LOCATOR_RESULTS = report_artifact_path(AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "results.jsonl")
AGENTIC_V3_1_TEXT_LOCATOR_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "summary.json")
AGENTIC_V3_1_TEXT_LOCATOR_SUMMARY_MD = report_artifact_path(AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "summary.md")
AGENTIC_V3_1_TEXT_LOCATOR_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "failure.json")
AGENTIC_V3_1_TEXT_LOCATOR_TRIAGE_DELTA_JSON = report_artifact_path(AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "delta.json")
AGENTIC_V3_1_TEXT_LOCATOR_TRIAGE_DELTA_MD = report_artifact_path(AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "delta.md")
AGENTIC_V3_1_1_POST_RESULTS = report_artifact_path(AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID, "results.jsonl")
AGENTIC_V3_1_1_POST_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID, "summary.json")
AGENTIC_V3_1_1_POST_SUMMARY_MD = report_artifact_path(AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID, "summary.md")
AGENTIC_V3_1_1_POST_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID, "failure.json")
AGENTIC_V3_1_1_POST_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_1_POST_TRIAGE_QUEUE_JSON = report_artifact_path(AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID, "queue.json")
AGENTIC_V3_1_2_ANSWER_SPAN_RESULTS = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "results.jsonl")
AGENTIC_V3_1_2_ANSWER_SPAN_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "summary.json")
AGENTIC_V3_1_2_ANSWER_SPAN_SUMMARY_MD = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "summary.md")
AGENTIC_V3_1_2_ANSWER_SPAN_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "failure.json")
AGENTIC_V3_1_2_ANSWER_SPAN_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_2_ANSWER_SPAN_DIAGNOSTICS_JSONL = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "spans.jsonl")
AGENTIC_V3_1_2_ANSWER_SPAN_REMAINING_TRIAGE_JSON = report_artifact_path(AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "queue.json")
AGENTIC_V3_1_3_REMAINING_QUEUE_RESULTS = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "results.jsonl")
AGENTIC_V3_1_3_REMAINING_QUEUE_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "summary.json")
AGENTIC_V3_1_3_REMAINING_QUEUE_SUMMARY_MD = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "summary.md")
AGENTIC_V3_1_3_REMAINING_QUEUE_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "failure.json")
AGENTIC_V3_1_3_REMAINING_QUEUE_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_3_REMAINING_QUEUE_DIAGNOSTICS_JSONL = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "spans.jsonl")
AGENTIC_V3_1_3_REMAINING_QUEUE_REMAINING_TRIAGE_JSON = report_artifact_path(AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "queue.json")
AGENTIC_V3_1_4_PDF_RESIDUAL_RESULTS = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "results.jsonl")
AGENTIC_V3_1_4_PDF_RESIDUAL_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "summary.json")
AGENTIC_V3_1_4_PDF_RESIDUAL_SUMMARY_MD = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "summary.md")
AGENTIC_V3_1_4_PDF_RESIDUAL_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "failure.json")
AGENTIC_V3_1_4_PDF_RESIDUAL_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_4_PDF_RESIDUAL_DIAGNOSTICS_JSONL = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "spans.jsonl")
AGENTIC_V3_1_4_PDF_RESIDUAL_REMAINING_TRIAGE_JSON = report_artifact_path(AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "queue.json")
AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID, "summary.json")
AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_DIAGNOSTICS_JSONL = report_artifact_path(AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID, "context.jsonl")
AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_TRIAGE_JSON = report_artifact_path(AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID, "queue.json")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RESULTS = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "results.jsonl")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_SUMMARY_JSON = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "summary.json")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_ATTRIBUTION_JSON = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "failure.json")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_AUDIT_JSONL = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "audit.jsonl")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_ANSWER_SPAN_DIAGNOSTICS_JSONL = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "spans.jsonl")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_CONTEXT_DIAGNOSTICS_JSONL = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "context.jsonl")
AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_REMAINING_TRIAGE_JSON = report_artifact_path(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID, "queue.json")
AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    "summary.json",
)
AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_INVENTORY_JSONL = report_artifact_path(
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    "all_track_residual_inventory.jsonl",
)
AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_REMAINING_JSON = report_artifact_path(
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    "remaining_triage_queue.json",
)
AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_DECISION_PACKET_JSON = report_artifact_path(
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    "user_decision_packet.json",
)
AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SILVER_AUDIT_JSON = report_artifact_path(
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID,
    "silver_readiness_audit.json",
)
AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_SUMMARY_JSON = report_artifact_path(
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
    "summary.json",
)
AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_HUMAN_REVIEW_JSON = report_artifact_path(
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
    "human_review_packet.json",
)
AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_DECISION_MATRIX_JSONL = report_artifact_path(
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
    "decision_matrix.jsonl",
)
AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_REMAINING_JSON = report_artifact_path(
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
    "remaining_triage_queue.json",
)
AGENTIC_INDEX_DIR = ROOT / "ai" / "eval" / "indexes" / "rag-data"
EXPLICIT_GENERATED_REPORT_MARKDOWN_FILENAMES: set[str] = set()
CURRENT_REPORT_PATHS = {
    REPORT_DIR / "baseline_v1.json",
    REPORT_DIR / "scorer_v1.jsonl",
    REPORT_DIR / "metric_input_v1.json",
    REPORT_DIR / "smoke_v1.json",
    REPORT_DIR / "xlsx_candidate_v1.jsonl",
    REPORT_DIR / "pdf_candidate_v1.jsonl",
    REPORT_DIR / "source_bound_readiness_v1.json",
    REPORT_DIR / "status.jsonl",
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RESULTS,
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_SUMMARY_JSON,
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_ATTRIBUTION_JSON,
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_AUDIT_JSONL,
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_ANSWER_SPAN_DIAGNOSTICS_JSONL,
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_CONTEXT_DIAGNOSTICS_JSONL,
    AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_REMAINING_TRIAGE_JSON,
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SUMMARY_JSON,
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_INVENTORY_JSONL,
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_REMAINING_JSON,
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_DECISION_PACKET_JSON,
    AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SILVER_AUDIT_JSON,
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_SUMMARY_JSON,
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_HUMAN_REVIEW_JSON,
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_DECISION_MATRIX_JSONL,
    AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_REMAINING_JSON,
}
ARCHIVED_REPORT_PATHS = {
    AGENTIC_RESULTS,
    AGENTIC_SUMMARY_JSON,
    AGENTIC_ATTRIBUTION_JSON,
    AGENTIC_V2_RESULTS,
    AGENTIC_V2_SUMMARY_JSON,
    AGENTIC_V2_ATTRIBUTION_JSON,
    AGENTIC_V2_1_RESULTS,
    AGENTIC_V2_1_SUMMARY_JSON,
    AGENTIC_V2_1_ATTRIBUTION_JSON,
    AGENTIC_V2_2_RESULTS,
    AGENTIC_V2_2_SUMMARY_JSON,
    AGENTIC_V2_2_ATTRIBUTION_JSON,
    AGENTIC_V3_RESULTS,
    AGENTIC_V3_SUMMARY_JSON,
    AGENTIC_V3_ATTRIBUTION_JSON,
    AGENTIC_V3_1_RESULTS,
    AGENTIC_V3_1_SUMMARY_JSON,
    AGENTIC_V3_1_ATTRIBUTION_JSON,
    AGENTIC_V3_1_AUDIT_JSONL,
    AGENTIC_V3_1_TRIAGE_JSON,
    AGENTIC_V3_1_PRIORITY_RESULTS,
    AGENTIC_V3_1_PRIORITY_SUMMARY_JSON,
    AGENTIC_V3_1_PRIORITY_ATTRIBUTION_JSON,
    AGENTIC_V3_1_PRIORITY_AUDIT_JSONL,
    AGENTIC_V3_1_PRIORITY_TRIAGE_DELTA_JSON,
    AGENTIC_V3_1_PRIORITY_STRICT_JSON_DIAGNOSTICS_JSON,
    AGENTIC_V3_1_TEXT_LOCATOR_RESULTS,
    AGENTIC_V3_1_TEXT_LOCATOR_SUMMARY_JSON,
    AGENTIC_V3_1_TEXT_LOCATOR_SUMMARY_MD,
    AGENTIC_V3_1_TEXT_LOCATOR_ATTRIBUTION_JSON,
    AGENTIC_V3_1_TEXT_LOCATOR_TRIAGE_DELTA_JSON,
    AGENTIC_V3_1_TEXT_LOCATOR_TRIAGE_DELTA_MD,
    AGENTIC_V3_1_1_POST_RESULTS,
    AGENTIC_V3_1_1_POST_SUMMARY_JSON,
    AGENTIC_V3_1_1_POST_SUMMARY_MD,
    AGENTIC_V3_1_1_POST_ATTRIBUTION_JSON,
    AGENTIC_V3_1_1_POST_AUDIT_JSONL,
    AGENTIC_V3_1_1_POST_TRIAGE_QUEUE_JSON,
    AGENTIC_V3_1_2_ANSWER_SPAN_RESULTS,
    AGENTIC_V3_1_2_ANSWER_SPAN_SUMMARY_JSON,
    AGENTIC_V3_1_2_ANSWER_SPAN_ATTRIBUTION_JSON,
    AGENTIC_V3_1_2_ANSWER_SPAN_AUDIT_JSONL,
    AGENTIC_V3_1_2_ANSWER_SPAN_DIAGNOSTICS_JSONL,
    AGENTIC_V3_1_2_ANSWER_SPAN_REMAINING_TRIAGE_JSON,
    AGENTIC_V3_1_3_REMAINING_QUEUE_RESULTS,
    AGENTIC_V3_1_3_REMAINING_QUEUE_SUMMARY_JSON,
    AGENTIC_V3_1_3_REMAINING_QUEUE_ATTRIBUTION_JSON,
    AGENTIC_V3_1_3_REMAINING_QUEUE_AUDIT_JSONL,
    AGENTIC_V3_1_3_REMAINING_QUEUE_DIAGNOSTICS_JSONL,
    AGENTIC_V3_1_3_REMAINING_QUEUE_REMAINING_TRIAGE_JSON,
    AGENTIC_V3_1_4_PDF_RESIDUAL_RESULTS,
    AGENTIC_V3_1_4_PDF_RESIDUAL_SUMMARY_JSON,
    AGENTIC_V3_1_4_PDF_RESIDUAL_ATTRIBUTION_JSON,
    AGENTIC_V3_1_4_PDF_RESIDUAL_AUDIT_JSONL,
    AGENTIC_V3_1_4_PDF_RESIDUAL_DIAGNOSTICS_JSONL,
    AGENTIC_V3_1_4_PDF_RESIDUAL_REMAINING_TRIAGE_JSON,
    AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_SUMMARY_JSON,
    AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_DIAGNOSTICS_JSONL,
    AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_TRIAGE_JSON,
}
CURRENT_REPORT_FILENAMES = {path.name for path in CURRENT_REPORT_PATHS}
ARCHIVED_REPORT_FILENAMES = {path.name for path in ARCHIVED_REPORT_PATHS}
ALL_REPORT_FILENAMES = CURRENT_REPORT_FILENAMES | ARCHIVED_REPORT_FILENAMES


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
def test_source_of_truth_audit_reports_current_scored_baseline() -> None:
    first_run = read_json(REPORT_DIR / "baseline_v1.json")
    measurement_doc = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    scorer_rows = read_jsonl(REPORT_DIR / "scorer_v1.jsonl")
    xlsx_rows = read_jsonl(REPORT_DIR / "xlsx_candidate_v1.jsonl")
    pdf_rows = read_jsonl(REPORT_DIR / "pdf_candidate_v1.jsonl")
    smoke = read_json(REPORT_DIR / "smoke_v1.json")

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
    assert "SCORER_BACKEND_UNAVAILABLE" not in measurement_doc
    assert "official_answer_citation_metric_first_run_v1" in measurement_doc
    assert "PASS `8/29`" in measurement_doc

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
    assert "Human-facing rolling docs" in current_progress
    assert "Per-run Markdown" in current_progress
    assert "BUILD_READY_LOAD_CHECK_PASSED" in current_progress
    assert "rerun_allowed=true" in current_progress


def test_pdf_candidate_locator_repair_artifacts_are_locked_to_current_report_only_state() -> None:
    first_run = read_json(REPORT_DIR / "baseline_v1.json")
    input_config = read_json(REPORT_DIR / "metric_input_v1.json")
    xlsx_rows = read_jsonl(REPORT_DIR / "xlsx_candidate_v1.jsonl")
    pdf_rows = read_jsonl(REPORT_DIR / "pdf_candidate_v1.jsonl")
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    smoke = read_json(REPORT_DIR / "smoke_v1.json")

    assert {path.name for path in REPORT_DIR.iterdir() if path.is_file()} == CURRENT_REPORT_FILENAMES
    assert {path.name for path in archived_report_dir().iterdir() if path.is_file()} == ARCHIVED_REPORT_FILENAMES
    assert CURRENT_REPORT_FILENAMES | ARCHIVED_REPORT_FILENAMES == ALL_REPORT_FILENAMES
    assert not (REPORT_DIR / "status.md").exists()
    assert {path.name for path in REPORT_DIR.glob("*.md")} == EXPLICIT_GENERATED_REPORT_MARKDOWN_FILENAMES
    assert PROGRESS_DOC.exists()
    assert MEASUREMENTS_DOC.exists()
    assert TRIAGE_DOC.exists()

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
        for row in read_jsonl(REPORT_DIR / "scorer_v1.jsonl")
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
    first_run = read_json(REPORT_DIR / "baseline_v1.json")
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
    assert (
        report_artifact_repo_relative(AGENTIC_RUN_ID, "results.jsonl") in readme
        or "D:\\_external_runtime_artifacts\\async-ocr-rag-multimodal-pipeline\\rag-ingestion\\" in readme
    )


def test_agentic_loop_measurement_artifacts_are_separate_fail_closed_current_run() -> None:
    first_run = read_json(REPORT_DIR / "baseline_v1.json")
    input_config = read_json(REPORT_DIR / "metric_input_v1.json")
    summary = read_json(AGENTIC_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_RESULTS)
    measurement_doc = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

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
    assert summary["artifact_paths"]["failure_attribution_json"] == report_artifact_repo_relative(
        AGENTIC_RUN_ID, "failure.json"
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
    assert all(
        "pdf_answer_citation_table_value_candidate" not in json.dumps(row, ensure_ascii=False)
        for row in results
    )
    assert all("table_value_candidate" not in json.dumps(row, ensure_ascii=False) for row in results)
    assert all("pdf_candidate" not in json.dumps(row, ensure_ascii=False) for row in results)
    if summary["failure_counts"] == {"GENERATION_PIPELINE_UNAVAILABLE": 29}:
        assert all(row["agentic_loop_executed"] is False for row in results)
        assert all(row["failure_category"] == "GENERATION_PIPELINE_UNAVAILABLE" for row in results)
        assert all(row["infrastructure_blocker_category"] == "NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING" for row in results)
    else:
        assert any(row["agentic_loop_executed"] is True for row in results)
        assert all(row["failure_category"] != "GENERATION_PIPELINE_UNAVAILABLE" for row in results)

    assert "official_answer_citation_agentic_loop_run_v1" in measurement_doc
    assert "diagnostic live-generation" in measurement_doc
    assert "fixture-all/noop/chunk-only" in measurement_doc
    assert "promotion_evidence=false" in measurement_doc
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
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

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
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

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
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

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
        "path": "ai/eval/reports/rag-ingestion/source_bound_readiness_v1.json",
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
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    assert summary["run_id"] == AGENTIC_V2_1_RUN_ID
    assert summary["measurement_classification"] == AGENTIC_V2_1_RUN_ID
    assert summary["status"] == "BLOCKED_OR_PARTIAL"
    assert summary["diagnostic_only"] is True
    assert summary["llm_backend"] == "noop"
    assert summary["source_bound_index_used"] is True
    assert summary["result_count"] == 29
    assert summary["unique_query_id_count"] == 29
    assert summary["scored_count"] == 29
    assert summary["pass_count"] == 28
    assert summary["failure_counts"] == {
        "PARTIAL_OR_UNSUPPORTED": 1,
        "PASS": 28,
    }
    assert summary["discarded_off_track_citation_count"] == 20
    assert summary["same_track_valid_citation_count"] == 125
    assert summary["query_bound_scored_citation_count"] == 29
    assert summary["non_query_bound_same_track_scored_citation_count"] == 96
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
            "failure_counts": {"PASS": 4},
            "pass_count": 4,
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
    assert sum(row["discarded_off_track_citation_count"] for row in results) == 20
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
    assert attribution["discarded_off_track_citation_count"] == 20
    assert attribution["same_track_valid_citation_count"] == 125
    assert attribution["query_bound_scored_citation_count"] == 29
    assert attribution["non_query_bound_same_track_scored_citation_count"] == 96
    assert attribution["schema_mismatch_residual_count"] == 0
    assert attribution["primary_attribution_counts"] == {"ANSWER_SYNTHESIS_LIMITATION": 1, "PASS": 28}
    assert attribution["per_track_primary_attribution_counts"] == {
        "pdf_business_ocr_mm": {"PASS": 4},
        "text_namu_v2_1": {"ANSWER_SYNTHESIS_LIMITATION": 1, "PASS": 5},
        "xlsx_business_structured": {"PASS": 19},
    }
    residual_audit = attribution["residual_failure_audit"]
    assert residual_audit["scope"] == "v2_1_residual_failures_only"
    assert set(residual_audit["target_query_ids"]) == RESIDUAL_AUDIT_QUERY_IDS
    assert set(residual_audit["audited_query_ids"]) == RESIDUAL_AUDIT_QUERY_IDS
    assert residual_audit["non_target_audited_query_ids"] == []
    assert residual_audit["llm_backend_validation_started"] is False
    assert residual_audit["llm_backend_validation_readiness"] == (
        "READY_FOR_LLM_BACKEND_VALIDATION_RESIDUALS_CONFIRMED_AS_SYNTHESIS"
    )
    assert residual_audit["schema_mismatch_residual_count"] == 0
    assert residual_audit["schema_mismatch_residual_count"] == summary["schema_mismatch_residual_count"]
    assert residual_audit["candidate_artifacts_as_generation_source"] is False
    assert residual_audit["expected_supporting_gold_used_for_audit_only"] is True
    assert residual_audit["generation_used_expected_answer"] is False
    assert residual_audit["generation_used_supporting_evidence"] is False
    assert residual_audit["generation_used_gold_fields"] is False
    assert residual_audit["promotion_evidence"] is False
    assert residual_audit["refined_primary_attribution_counts"] == {
        "ANSWER_SYNTHESIS_LIMITATION": 1,
        "PASS": 2,
    }
    assert residual_audit["counts"] == {
        "answer_synthesis_limitation_confirmed": 1,
        "deterministic_extractive_answer_missing_value": 3,
        "query_bound_evidence_contains_answer": 3,
        "query_bound_evidence_contains_citation_support": 3,
        "query_bound_evidence_gap": 0,
        "same_track_non_query_bound_distracted": 1,
        "same_track_non_query_bound_helped": 0,
        "scorer_normalization_issue_possible": 0,
    }
    assert "gq_auto_010" not in residual_audit["audited_query_ids"]
    assert "gq_auto_024" not in residual_audit["audited_query_ids"]

    audit_rows = {row["query_id"]: row for row in residual_audit["rows"]}
    expected_counts = {
        "gq_auto_030": (1, 1, 2, "PASS"),
        "gq_pdf_section_question_001": (1, 1, 2, "PASS"),
        "text_namu_v2_0017": (1, 2, 3, "ANSWER_SYNTHESIS_LIMITATION"),
    }
    results_by_id = {row["query_id"]: row for row in results}
    failed_ids = {row["query_id"] for row in results if row["failure_category"] != "PASS"}
    assert failed_ids == {"text_namu_v2_0017"}
    for query_id, (query_bound, non_query_bound, same_track, refined) in expected_counts.items():
        row = results_by_id[query_id]
        audit_row = audit_rows[query_id]
        assert row["query_bound_scored_citation_count"] == query_bound
        assert row["non_query_bound_same_track_scored_citation_count"] == non_query_bound
        assert row["same_track_valid_citation_count"] == same_track
        assert row["schema_mismatch_residual_count"] == 0
        assert audit_row["query_bound_scored_citation_count"] == query_bound
        assert audit_row["non_query_bound_same_track_scored_citation_count"] == non_query_bound
        assert audit_row["same_track_valid_citation_count"] == same_track
        assert audit_row["refined_primary_attribution"] == refined
        assert audit_row["generation_used_expected_answer"] is False
        assert audit_row["generation_used_supporting_evidence"] is False
        assert audit_row["generation_used_gold_fields"] is False
        assert audit_row["candidate_artifacts_as_generation_source"] is False
        assert audit_row["audit_comparison_only"] is True

    auto_query_bound_text = " ".join(
        citation["citation_text"]
        for citation in results_by_id["gq_auto_030"]["scored_citations"]
        if citation["citation_payload_validation"]["manifest_query_id"] == "gq_auto_030"
    )
    assert "2020" in auto_query_bound_text
    assert "1,088.0" in auto_query_bound_text
    assert audit_rows["gq_auto_030"]["query_bound_evidence_contains_answer"] is True
    assert audit_rows["gq_auto_030"]["query_bound_evidence_contains_citation_support"] is True
    assert audit_rows["gq_auto_030"]["same_track_non_query_bound_evidence_helped_or_distracted"] == "neutral"
    assert audit_rows["gq_auto_030"]["answer_synthesis_limitation_confirmed"] is False
    table_query_bound_text = " ".join(
        citation["citation_text"]
        for citation in results_by_id["gq_pdf_section_question_001"]["scored_citations"]
        if citation["citation_payload_validation"]["manifest_query_id"] == "gq_pdf_section_question_001"
    )
    assert "2024" in table_query_bound_text
    assert "518.4" in table_query_bound_text
    assert audit_rows["gq_pdf_section_question_001"]["query_bound_evidence_contains_answer"] is True
    assert audit_rows["gq_pdf_section_question_001"]["query_bound_evidence_contains_citation_support"] is True
    assert audit_rows["gq_pdf_section_question_001"]["same_track_non_query_bound_evidence_helped_or_distracted"] == "neutral"
    assert audit_rows["gq_pdf_section_question_001"]["scorer_normalization_issue_possible"] is False
    assert audit_rows["text_namu_v2_0017"]["query_bound_evidence_contains_answer"] is True
    assert audit_rows["text_namu_v2_0017"]["query_bound_evidence_contains_citation_support"] is True
    assert audit_rows["text_namu_v2_0017"]["same_track_non_query_bound_evidence_helped_or_distracted"] == "distracted"
    assert audit_rows["text_namu_v2_0017"]["answer_synthesis_limitation_confirmed"] is True
    assert attribution["baseline_comparison_is_model_quality_comparable"] is False
    assert attribution["guardrails"]["promotion_evidence"] is False

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V2_1_RUN_ID
    )
    assert measurement["discarded_off_track_citation_count"] == 20
    assert measurement["same_track_valid_citation_count"] == 125
    assert measurement["query_bound_scored_citation_count"] == 29
    assert measurement["non_query_bound_same_track_scored_citation_count"] == 96
    assert measurement["schema_mismatch_residual_count"] == 0
    assert measurement["candidate_artifacts_as_generation_source"] is False
    assert measurement["generation_used_expected_answer"] is False
    assert measurement["generation_used_supporting_evidence"] is False
    assert measurement["generation_used_gold_fields"] is False
    assert measurement["promotion_evidence"] is False
    assert measurement["residual_failure_audit"]["audited_row_count"] == 3
    assert measurement["residual_failure_audit"]["promotion_evidence"] is False
    failure_attribution_event = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_failure_attribution"
        and event.get("run_id") == AGENTIC_V2_1_RUN_ID
    )
    assert failure_attribution_event["residual_failure_audit"]["audited_row_count"] == 3
    preflight = runner.v2_1_artifact_consistency_preflight(
        summary=summary,
        attribution=attribution,
        rows=results,
        status_events=status_events,
    )
    assert preflight["ok"] is True
    assert preflight["failure_bucket"] is None
    assert preflight["pass_count"] == 28
    assert preflight["per_track_pass_count"] == {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 5,
        "xlsx_business_structured": 19,
    }
    assert preflight["remaining_failure_query_ids"] == ["text_namu_v2_0017"]
    assert preflight["answer_synthesis_limitation_query_ids"] == ["text_namu_v2_0017"]
    assert preflight["query_bound_evidence_gap_count"] == 0
    assert preflight["schema_mismatch_residual_count"] == 0
    assert preflight["promotion_evidence"] is False
    assert preflight["readiness"] == "READY_FOR_LLM_BACKEND_VALIDATION_RESIDUALS_CONFIRMED_AS_SYNTHESIS"
    unexpected_residual_reports = [
        path.name
            for path in REPORT_DIR.iterdir()
            if "residual" in path.name and path.suffix in {".json", ".md"}
            and not path.name.startswith(f"{AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID}_")
            and not path.name.startswith(f"{AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID}_")
            and not path.name.startswith(f"{AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID}_")
        ]
    assert unexpected_residual_reports == []
    assert "source-bound denominator index" in summary["pipeline_decision"]["rationale"]
    assert "registry-backed RAG pipeline" not in summary["pipeline_decision"]["rationale"]


def test_v2_2_llm_backend_validation_artifact_is_diagnostic_only() -> None:
    summary = read_json(AGENTIC_V2_2_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V2_2_RESULTS)
    attribution = read_json(AGENTIC_V2_2_ATTRIBUTION_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V2_2_RUN_ID
    assert summary["measurement_classification"] == AGENTIC_V2_2_RUN_ID
    assert summary["diagnostic_only"] is True
    assert summary["promotion_evidence"] is False
    assert summary["baseline_comparison_is_model_quality_comparable"] is False
    assert summary["source_bound_index_used"] is True
    assert summary["canonical_search_unit_payload_used"] is True
    assert summary["prompt_context_source_bound_only"] is True
    assert summary["candidate_artifacts_as_generation_source"] is False
    assert summary["generation_used_expected_answer"] is False
    assert summary["generation_used_supporting_evidence"] is False
    assert summary["generation_used_gold_fields"] is False
    assert summary["v2_1_artifact_consistency_preflight"]["ok"] is True
    assert summary["v2_1_artifact_consistency_preflight"]["pass_count"] == 28
    assert summary["v2_1_artifact_consistency_preflight"]["query_bound_evidence_gap_count"] == 0
    assert summary["v2_1_artifact_consistency_preflight"]["schema_mismatch_residual_count"] == 0
    assert summary["result_count"] == 29
    assert len(results) == 29
    assert all(row["run_id"] == AGENTIC_V2_2_RUN_ID for row in results)
    assert all(row["diagnostic_only"] is True for row in results)
    assert all(row["promotion_evidence"] is False for row in results)
    assert all(row["prompt_context_source_bound_only"] is True for row in results)
    assert all(row["candidate_artifacts_as_generation_source"] is False for row in results)
    assert all(row["generation_used_expected_answer"] is False for row in results)
    assert all(row["generation_used_supporting_evidence"] is False for row in results)
    assert all(row["generation_used_gold_fields"] is False for row in results)
    assert all(
        "pdf_answer_citation_table_value_candidate" not in json.dumps(row, ensure_ascii=False)
        for row in results
    )
    assert all("expected_answer" not in row for row in results)
    assert all("supporting_evidence" not in row for row in results)
    assert attribution["run_id"] == AGENTIC_V2_2_RUN_ID
    assert attribution["promotion_evidence"] is False
    assert attribution["v2_1_artifact_consistency_preflight"]["ok"] is True

    bucket_counts = summary["validation_bucket_counts"]
    if summary["llm_backend_validation_status"] == "LLM_BACKEND_UNAVAILABLE_FAIL_CLOSED":
        assert summary["real_llm_backend_used"] is False
        assert summary["local_llm_used"] is False
        assert summary["llm_backend"] != "noop"
        assert bucket_counts == {"LLM_BACKEND_UNAVAILABLE": 29}
        assert all(row["validation_bucket"] == "LLM_BACKEND_UNAVAILABLE" for row in results)
    else:
        assert summary["llm_backend_validation_status"] == "LLM_BACKEND_VALIDATION_COMPLETED"
        assert summary["real_llm_backend_used"] is True
        assert summary["llm_backend"] in {"llamacpp", "openai-compatible", "ollama"}
        assert summary["llm_invoked_row_count"] == 1
        assert summary["retained_without_llm_count"] == 28
        assert bucket_counts["PASS_RETAINED"] >= 28
        assert summary["existing_pass_regression_count"] == 0
        assert summary["schema_mismatch_residual_count"] == 0
        assert summary["query_bound_evidence_gap_count"] == 0
        assert summary["text_namu_v2_0017"]["validation_bucket"] in {
            "LLM_SYNTHESIS_IMPROVED",
            "LLM_SYNTHESIS_REGRESSED",
            "LLM_TIMEOUT_OR_FAIL_CLOSED",
            "CITATION_SUPPORT_REGRESSED",
        }
        structured_rows = [
            row for row in results if row["track"] in {"pdf_business_ocr_mm", "xlsx_business_structured"}
        ]
        assert len(structured_rows) == 23
        assert all(row["structured_adapter_output_retained"] is True for row in structured_rows)
        assert all(row["structured_adapter_overwritten_by_llm"] is False for row in structured_rows)
        retained_rows = [row for row in results if row["validation_bucket"] == "PASS_RETAINED"]
        assert all(row["real_llm_backend_available"] is True for row in retained_rows)
        assert all(row["real_llm_backend_used"] is False for row in retained_rows)
        assert all(row["real_llm_backend_used_for_row"] is False for row in retained_rows)
        target_row = next(row for row in results if row["query_id"] == "text_namu_v2_0017")
        assert target_row["llm_invoked_for_row"] is True
        assert target_row["real_llm_backend_used"] is True
        assert target_row["real_llm_backend_used_for_row"] is True

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V2_2_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["llm_backend_validation_status"] == summary["llm_backend_validation_status"]


def test_v3_comparable_live_measurement_artifacts_are_separate_and_guarded() -> None:
    summary = read_json(AGENTIC_V3_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_RESULTS)
    attribution = read_json(AGENTIC_V3_ATTRIBUTION_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    input_config = read_json(REPORT_DIR / "metric_input_v1.json")
    first_run = read_json(REPORT_DIR / "baseline_v1.json")

    assert summary["run_id"] == AGENTIC_V3_RUN_ID
    assert summary["measurement_classification"] == "comparable_live_measurement_v3_not_promotion_evidence"
    assert summary["run_id"] not in {
        AGENTIC_RUN_ID,
        AGENTIC_V2_RUN_ID,
        AGENTIC_V2_1_RUN_ID,
        AGENTIC_V2_2_RUN_ID,
    }
    assert summary["diagnostic_only"] is True
    assert summary["comparable_live_measurement"] is True
    assert summary["promotion_evidence"] is False
    assert summary["threshold_tuning"] is False
    assert summary["winner_selection"] is False
    assert summary["promotion_gate_auto_run"] is False
    assert summary["v2_2_completed_preflight"]["ok"] is True
    assert summary["source_bound_official_denominator_index_only"] is True
    assert summary["source_bound_index_used"] is True
    assert summary["canonical_search_unit_payload_used"] is True
    assert summary["real_llm_backend_required_for_text_rows"] is True
    assert summary["same_scorer_as_v2_2"] is True
    assert summary["same_denominator_as_v2_2"] is True
    assert summary["baseline_comparison_is_model_quality_comparable"] is True
    assert summary["comparison_scope"] == "mixed_structured_adapter_retained_and_text_llm_synthesis_rows"
    assert summary["structured_rows_policy"]["xlsx_primary_answer_policy"] == "deterministic_source_bound_adapter_retained"
    assert summary["structured_rows_policy"]["llm_overwrites_structured_adapter_output"] is False
    assert summary["text_rows_policy"]["text_rows_use_real_llm_synthesis"] is True
    assert summary["text_rows_policy"]["prompt_context_mode"] in {
        "query-bound-only",
        "same-track-scored-context",
    }
    assert summary["guardrails"] == {
        "promotion_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "production_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
        "baseline_mutation": False,
        "threshold_tuning": False,
        "winner_selection": False,
    }

    assert len(results) == 29
    assert len({row["query_id"] for row in results}) == 29
    config_query_ids = {row["query_id"] for row in input_config["candidate_manifest"]}
    assert {row["query_id"] for row in results} == config_query_ids
    assert Counter(row["track"] for row in results) == Counter(
        {
            "pdf_business_ocr_mm": 4,
            "text_namu_v2_1": 6,
            "xlsx_business_structured": 19,
        }
    )
    assert summary["result_count"] == 29
    assert sum(summary["result_bucket_counts"].values()) == 29
    assert set(summary["result_bucket_counts"]).issubset(
        {
            "PASS",
            "PARTIAL_OR_UNSUPPORTED",
            "CITATION_UNSUPPORTED",
            "PASS_RETAINED_BY_STRUCTURED_ADAPTER",
            "LLM_SYNTHESIS_PASS",
            "LLM_SYNTHESIS_REGRESSED",
            "STRUCTURED_ADAPTER_REGRESSED",
            "CITATION_SUPPORT_REGRESSED",
            "PROMPT_CONTEXT_POLICY_VIOLATION",
            "SCORER_NORMALIZATION_ISSUE_POSSIBLE",
        }
    )
    assert summary["per_track_counts_by_source_family"]["PDF"]["row_count"] == 4
    assert summary["per_track_counts_by_source_family"]["TEXT"]["row_count"] == 6
    assert summary["per_track_counts_by_source_family"]["XLSX"]["row_count"] == 19

    assert all(row["run_id"] == AGENTIC_V3_RUN_ID for row in results)
    assert all(row["promotion_evidence"] is False for row in results)
    assert all(row["candidate_artifacts_as_generation_source"] is False for row in results)
    assert all(row["generation_used_expected_answer"] is False for row in results)
    assert all(row["generation_used_supporting_evidence"] is False for row in results)
    assert all(row["generation_used_gold_fields"] is False for row in results)
    assert all("expected_answer" not in row for row in results)
    assert all("supporting_evidence" not in row for row in results)
    assert all("human_label" not in row for row in results)

    structured_rows = [
        row for row in results if row["track"] in {"pdf_business_ocr_mm", "xlsx_business_structured"}
    ]
    text_rows = [row for row in results if row["track"] == "text_namu_v2_1"]
    assert len(structured_rows) == 23
    assert all(row["result_bucket"] == "PASS_RETAINED_BY_STRUCTURED_ADAPTER" for row in structured_rows)
    assert all(row["structured_adapter_output_retained"] is True for row in structured_rows)
    assert all(row["structured_adapter_overwritten_by_llm"] is False for row in structured_rows)
    assert all(row["llm_invoked_for_row"] is False for row in structured_rows)
    assert len(text_rows) == 6
    assert all(row["llm_invoked_for_row"] is True for row in text_rows)
    assert all(row["real_llm_backend_used_for_row"] is True for row in text_rows)

    pdf_table_rows = [
        row
        for row in structured_rows
        if any(
            (citation.get("search_unit_citation_payload") or {}).get("region_type") == "table_body"
            for citation in row["scored_citations"]
        )
    ]
    assert pdf_table_rows
    for row in pdf_table_rows:
        locator = row["scored_citations"][0]["search_unit_citation_payload"]
        assert locator["page"]
        assert locator["bbox"] and len(locator["bbox"]) == 4
        assert locator["source_pdf_path"]
        assert locator["row_label"]
        assert locator["target_column"]

    target_row = next(row for row in results if row["query_id"] == "text_namu_v2_0017")
    for key in (
        "llm_output_contains_expected_answer_span_for_scoring",
        "citation_support_present",
        "answer_citation_support_jointly_satisfied",
        "non_query_bound_same_track_context_used",
        "non_query_bound_same_track_context_distracted",
        "scorer_normalization_issue_possible",
        "prompt_context_policy",
    ):
        assert key in target_row["text_namu_v2_0017_diagnostics"]
    if target_row["failure_category"] != "PASS":
        assert summary["next_step_recommendation"] == "failure_tuning_for_text_namu_v2_0017"

    assert first_run["schema_version"] == summary["baseline_reference"]["run_id"]
    baseline_identity = official_file_identity(REPORT_DIR / "baseline_v1.json")
    assert summary["baseline_reference"]["artifact_identity"]["path"] == baseline_identity["path"]
    assert summary["baseline_reference"]["artifact_identity"]["exists"] is True
    assert baseline_identity["exists"] is True
    assert attribution["run_id"] == AGENTIC_V3_RUN_ID
    assert attribution["promotion_evidence"] is False
    assert attribution["guardrails"] == summary["guardrails"]
    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["comparable_live_measurement"] is True
    assert measurement["promotion_gate_auto_run"] is False
    assert measurement["result_bucket_counts"] == summary["result_bucket_counts"]


def test_v3_1_all_track_foundation_measurement_artifacts_are_separate_and_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_RESULTS)
    attribution = read_json(AGENTIC_V3_1_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_AUDIT_JSONL)
    triage = read_json(AGENTIC_V3_1_TRIAGE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")
    input_config = read_json(REPORT_DIR / "metric_input_v1.json")

    lane_names = {
        "v3_primary_replay",
        "live_llm_retrieval_topk",
        "live_llm_query_bound_oracle",
    }
    required_guardrails = {
        "diagnostic_only": True,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_gate_auto_run": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
    }
    locator_fields = {
        "PDF": {
            "source_pdf_path",
            "page",
            "physical_page_index",
            "bbox",
            "region_type",
            "search_unit_id",
            "document_version_id",
        },
        "XLSX": {
            "workbook",
            "sheet",
            "range",
            "cell",
            "row_label",
            "target_column",
            "normalized_value",
            "search_unit_id",
            "document_version_id",
        },
        "TEXT": {"document_id", "document_version_id", "search_unit_id", "text_locator"},
    }

    assert summary["run_id"] == AGENTIC_V3_1_RUN_ID
    assert summary["measurement_classification"] == "all_track_foundation_measurement_v3_1_diagnostic_only"
    assert summary["run_id"] not in {
        AGENTIC_RUN_ID,
        AGENTIC_V2_RUN_ID,
        AGENTIC_V2_1_RUN_ID,
        AGENTIC_V2_2_RUN_ID,
        AGENTIC_V3_RUN_ID,
    }
    assert summary["total_denominator_rows"] == 29
    assert summary["rows_by_source_family"] == {"PDF": 4, "TEXT": 6, "XLSX": 19}
    assert summary["diagnostic_only"] is True
    for key, expected in required_guardrails.items():
        assert summary["guardrails"][key] is expected
    assert summary["next_step_recommendation"] == "row_level_failure_triage_after_all_track_foundation_measurement"

    assert set(summary["lane_counts"]) == lane_names
    assert summary["lane_counts"]["live_llm_retrieval_topk"]["llm_invoked_count"] == 29
    assert summary["lane_counts"]["live_llm_query_bound_oracle"]["llm_invoked_count"] == 29
    assert summary["lane_counts"]["v3_primary_replay"]["adapter_retained_count"] == 23
    assert summary["lane_counts"]["v3_primary_replay"]["llm_invoked_count"] == 6
    assert summary["source_family_lane_counts"]["PDF"]["v3_primary_replay"]["pass_count"] == 4
    assert summary["source_family_lane_counts"]["XLSX"]["v3_primary_replay"]["pass_count"] == 19

    assert len(results) == 29
    assert len(audit_rows) == 29
    config_query_ids = {row["query_id"] for row in input_config["candidate_manifest"]}
    assert {row["query_id"] for row in results} == config_query_ids
    assert Counter(row["source_family"] for row in results) == Counter({"PDF": 4, "TEXT": 6, "XLSX": 19})
    assert all(row["run_id"] == AGENTIC_V3_1_RUN_ID for row in results)
    assert all(set(row["lane_results"]) == lane_names for row in results)
    assert all("expected_answer" not in row for row in results)
    assert all("supporting_evidence" not in row for row in results)
    assert all("human_label" not in row for row in results)

    for row in results:
        family = row["source_family"]
        assert locator_fields[family].issubset(set(row["denominator_locator"]))
        assert row["denominator_search_unit_id"] == row["denominator_locator"]["search_unit_id"]
        assert row["query_bound_search_unit_present"] is True

        lane_a = row["lane_results"]["v3_primary_replay"]
        lane_b = row["lane_results"]["live_llm_retrieval_topk"]
        lane_c = row["lane_results"]["live_llm_query_bound_oracle"]
        assert lane_b["llm_invoked"] is True
        assert lane_c["llm_invoked"] is True
        assert lane_b["answer_origin"] == "LLM_SYNTHESIS"
        assert lane_c["answer_origin"] == "LLM_SYNTHESIS"
        assert lane_b["prompt_context_mode"] == "retrieval_topk_source_bound"
        assert lane_c["prompt_context_mode"] == "query_bound_only_source_bound"
        assert lane_b["generation_used_expected_answer"] is False
        assert lane_c["generation_used_expected_answer"] is False
        assert lane_b["generation_used_gold_fields"] is False
        assert lane_c["generation_used_gold_fields"] is False
        assert lane_b["generation_used_supporting_evidence"] is False
        assert lane_c["generation_used_supporting_evidence"] is False
        assert set(lane_c["cited_search_unit_ids"]).issubset({row["denominator_search_unit_id"]})
        for live_lane in (lane_b, lane_c):
            assert live_lane["llm_generated_locator_validation"]["generated_by_llm"] is True
            assert set(live_lane["llm_generated_locator_validation"]["required_fields"]) == locator_fields[family]
            assert live_lane["llm_generated_locator_validation"]["cited_search_unit_ids"] == live_lane["cited_search_unit_ids"]
            assert isinstance(live_lane["llm_generated_citation_locators"], list)
            for generated_locator in live_lane["llm_generated_citation_locators"]:
                assert "search_unit_id" in generated_locator
            if live_lane["failure_category"] == "PASS":
                assert live_lane["llm_generated_locator_validation"]["ok"] is True
                assert len(live_lane["llm_generated_citation_locators"]) == len(live_lane["cited_search_unit_ids"])
                for generated_locator in live_lane["llm_generated_citation_locators"]:
                    assert locator_fields[family].issubset(set(generated_locator))

        if family in {"PDF", "XLSX"}:
            assert lane_a["answer_origin"] == "STRUCTURED_ADAPTER"
            assert lane_a["llm_invoked"] is False
            assert lane_a["prompt_context_mode"] == "structured_adapter_retained"
        else:
            assert lane_a["answer_origin"] == "LLM_SYNTHESIS"
            assert lane_a["llm_invoked"] is True

    failing_query_ids = {
        row["query_id"]
        for row in results
        if any(lane["failure_category"] != "PASS" for lane in row["lane_results"].values())
    }
    assert {item["query_id"] for item in triage["items"]} == failing_query_ids
    assert all(item["failing_lane_names"] for item in triage["items"])
    assert all(item["query_id"] in failing_query_ids for item in triage["items"])
    assert all(item["safe_to_fix_without_user_gold_decision"] in {True, False} for item in triage["items"])
    assert all(item["requires_user_gold_policy_decision"] in {True, False} for item in triage["items"])

    assert attribution["run_id"] == AGENTIC_V3_1_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]
    assert set(attribution["failure_taxonomy"]) >= {
        "PASS",
        "RETRIEVAL_QUERY_BOUND_MISS",
        "CITATION_PAYLOAD_SCHEMA_MISMATCH",
        "LLM_STRICT_JSON_PARSE_FAILURE",
        "PDF_BBOX_LOCATOR_LOSS",
        "XLSX_CELL_LOCATOR_LOSS",
        "SCORER_NORMALIZATION_REVIEW",
        "GOLD_POLICY_REVIEW_CANDIDATE",
    }

    assert all("expected_answer" not in row for row in audit_rows)
    assert all("supporting_evidence" not in row for row in audit_rows)
    assert all(row["query_id"] in config_query_ids for row in audit_rows)
    measurement_doc = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage_doc = TRIAGE_DOC.read_text(encoding="utf-8")
    assert AGENTIC_V3_1_RUN_ID in measurement_doc
    assert AGENTIC_V3_1_RUN_ID in triage_doc
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_RUN_ID}*promotion*"))
    forbidden_status = subprocess.run(
        [
            "git",
            "status",
            "--short",
            "--untracked-files=all",
            "--",
            "ai/eval/silver",
            "ai/eval/review",
            "ai/eval/eval_queries",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert forbidden_status.returncode == 0
    assert forbidden_status.stdout.strip() == ""

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["result_count"] == 29
    assert measurement["lane_counts"] == summary["lane_counts"]


def test_v3_1_priority_1_5_strict_json_locator_triage_artifacts_are_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_PRIORITY_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_PRIORITY_RESULTS)
    attribution = read_json(AGENTIC_V3_1_PRIORITY_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_PRIORITY_AUDIT_JSONL)
    strict_json_diagnostics = read_json(AGENTIC_V3_1_PRIORITY_STRICT_JSON_DIAGNOSTICS_JSON)
    triage_delta = read_json(AGENTIC_V3_1_PRIORITY_TRIAGE_DELTA_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    required_guardrails = {
        "diagnostic_only": True,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_gate_auto_run": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
    }

    assert summary["run_id"] == AGENTIC_V3_1_PRIORITY_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_RUN_ID
    assert summary["measurement_classification"] == "priority_1_5_strict_json_locator_triage_diagnostic_only"
    assert summary["target_row_count"] == 5
    assert summary["result_count"] == 5
    assert tuple(summary["target_query_ids"]) == AGENTIC_V3_1_PRIORITY_QUERY_IDS
    assert [row["query_id"] for row in results] == list(AGENTIC_V3_1_PRIORITY_QUERY_IDS)
    assert [row["query_id"] for row in audit_rows] == list(AGENTIC_V3_1_PRIORITY_QUERY_IDS)
    for key, expected in required_guardrails.items():
        assert summary["guardrails"][key] is expected
        assert summary[key] is expected

    assert summary["strict_json_parse_failure_before"] == 2
    assert summary["strict_json_parse_failure_after"] == 0
    assert summary["strict_json_schema_repair_applied_count_before"] == 0
    assert summary["strict_json_schema_repair_applied_count_after"] == 2
    assert summary["llm_generated_locator_copy_failure_before"] == 5
    assert summary["llm_generated_locator_copy_failure_after"] == 1
    assert summary["llm_generated_locator_field_mismatch_failure_before"] == 3
    assert summary["llm_generated_locator_field_mismatch_failure_after"] == 0
    assert summary["llm_generated_locator_missing_failure_before"] == 0
    assert summary["llm_generated_locator_missing_failure_after"] == 1
    assert summary["pdf_source_pdf_path_mismatch_before"] == 1
    assert summary["pdf_source_pdf_path_mismatch_after"] == 0
    assert summary["xlsx_row_label_mismatch_before"] == 2
    assert summary["xlsx_row_label_mismatch_after"] == 0
    assert "posthoc_payload_locator_preservation_failure_count" in summary
    assert "llm_generated_locator_copy_failure_count" in summary
    assert "posthoc_payload_locator_preservation_failure_count" in summary["locator_metric_split"]
    assert "llm_generated_locator_copy_failure_count" in summary["locator_metric_split"]
    assert "llm_generated_locator_missing_failure_count" in summary["locator_metric_split"]
    assert summary["v3_1_artifact_consistency_preflight"]["ok"] is True
    assert summary["score_interpretation"] == "answer_and_citation_scores_are_reference_only_not_promotion_evidence"

    assert attribution["run_id"] == AGENTIC_V3_1_PRIORITY_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]
    assert strict_json_diagnostics["run_id"] == AGENTIC_V3_1_PRIORITY_STRICT_JSON_DIAGNOSTICS_ID
    assert strict_json_diagnostics["target_run_id"] == AGENTIC_V3_1_PRIORITY_RUN_ID
    assert strict_json_diagnostics["diagnostic_only"] is True
    assert tuple(strict_json_diagnostics["target_query_ids"]) == AGENTIC_V3_1_PRIORITY_QUERY_IDS[:2]
    measurement_doc = MEASUREMENTS_DOC.read_text(encoding="utf-8")
    triage_doc = TRIAGE_DOC.read_text(encoding="utf-8")
    assert AGENTIC_V3_1_PRIORITY_RUN_ID in measurement_doc
    assert AGENTIC_V3_1_PRIORITY_RUN_ID in triage_doc
    assert "LLM-generated locator copy failure: `5 -> 1`" in triage_doc

    diagnostic_rows = {row["query_id"]: row for row in strict_json_diagnostics["rows"]}
    for query_id in AGENTIC_V3_1_PRIORITY_QUERY_IDS[:2]:
        after = diagnostic_rows[query_id]["after"]
        assert after["prompt_context_mode"] == "retrieval_topk_source_bound"
        assert after["raw_response_sha256"]
        assert after.get("sanitized_raw_response_excerpt") or after.get("raw_response_excerpt")
        assert after["attempted_schema_keys"] == ["answer", "cited_search_unit_ids", "citation_locators"]
        assert "strict_json_error" in after
        assert "missing_required_keys" in after
        assert "schema_repair_applied" in after
        assert "missing_required_keys_before_repair" in after
        assert after["cited_search_unit_ids_before_parse"]

    rows_by_id = {row["query_id"]: row for row in results}
    pdf_validation = rows_by_id["gq_auto_010"]["lane_results"]["live_llm_retrieval_topk"][
        "llm_generated_locator_validation"
    ]
    pdf_unit_id = rows_by_id["gq_auto_010"]["denominator_search_unit_id"]
    pdf_source_path_check = pdf_validation["field_comparisons_by_search_unit_id"][pdf_unit_id]["source_pdf_path"]
    assert pdf_source_path_check["byte_equal"] is True
    assert pdf_source_path_check["normalized_equal"] is True

    for query_id in ("gq_auto_023", "gq_xlsx_lookup_008"):
        row = rows_by_id[query_id]
        validation = row["lane_results"]["live_llm_retrieval_topk"]["llm_generated_locator_validation"]
        unit_id = row["denominator_search_unit_id"]
        row_label_check = validation["field_comparisons_by_search_unit_id"][unit_id]["row_label"]
        assert row_label_check["byte_equal"] is True
        assert row_label_check["normalized_equal"] is True

    before_by_id = {row["query_id"]: row for row in triage_delta["rows"]}
    assert before_by_id["gq_auto_010"]["before"]["pdf_source_pdf_path_byte_equal"] is False
    assert before_by_id["gq_auto_010"]["after"]["pdf_source_pdf_path_byte_equal"] is True
    for query_id in ("gq_auto_023", "gq_xlsx_lookup_008"):
        assert before_by_id[query_id]["before"]["xlsx_row_label_byte_equal"] is False
        assert before_by_id[query_id]["after"]["xlsx_row_label_byte_equal"] is True
        assert before_by_id[query_id]["after"]["xlsx_row_label_normalized_equal"] is True

    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(strict_json_diagnostics)
    assert_no_gold_generation_source_fields(triage_delta)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_PRIORITY_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_PRIORITY_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_PRIORITY_RUN_ID}*promotion*"))

    forbidden_status = subprocess.run(
        [
            "git",
            "status",
            "--short",
            "--untracked-files=all",
            "--",
            "ai/eval/silver",
            "ai/eval/review",
            "ai/eval/eval_queries",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert forbidden_status.returncode == 0
    assert forbidden_status.stdout.strip() == ""

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_PRIORITY_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["result_count"] == 5
    assert measurement["strict_json_parse_failure_after"] == summary["strict_json_parse_failure_after"]


def test_priority_strict_json_schema_repair_is_counted_separately() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    rows = [
        {
            "lane_results": {
                "live_llm_retrieval_topk": {
                    "failure_category": "PASS",
                    "strict_json_parse_ok": True,
                    "strict_json_diagnostics": {
                        "parse_ok": True,
                        "schema_repair_applied": True,
                        "missing_required_keys_before_repair": ["cited_search_unit_ids"],
                        "missing_required_keys": [],
                    },
                }
            }
        }
    ]

    assert runner.strict_json_parse_failure_count(rows) == 0
    assert runner.strict_json_schema_repair_applied_count(rows) == 1


def test_priority_locator_copy_failure_counts_missing_fields() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    rows = [
        {
            "lane_results": {
                "live_llm_retrieval_topk": {
                    "llm_generated_locator_validation": {
                        "generated_by_llm": True,
                        "ok": False,
                        "missing_fields_by_search_unit_id": {"su_text": ["text_locator"]},
                        "missing_locator_for_search_unit_ids": [],
                        "mismatched_fields_by_search_unit_id": {},
                    }
                }
            }
        }
    ]

    assert runner.llm_generated_locator_copy_failure_count(rows) == 1
    assert runner.llm_generated_locator_field_mismatch_failure_count(rows) == 0
    assert runner.llm_generated_locator_missing_failure_count(rows) == 1


def test_v3_1_text_locator_residual_triage_copies_canonical_text_locator() -> None:
    summary = read_json(AGENTIC_V3_1_TEXT_LOCATOR_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_TEXT_LOCATOR_RESULTS)
    attribution = read_json(AGENTIC_V3_1_TEXT_LOCATOR_ATTRIBUTION_JSON)
    triage_delta = read_json(AGENTIC_V3_1_TEXT_LOCATOR_TRIAGE_DELTA_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_PRIORITY_RUN_ID
    assert summary["measurement_classification"] == "text_locator_residual_triage_diagnostic_only"
    assert summary["target_row_count"] == 1
    assert summary["result_count"] == 1
    assert summary["target_query_ids"] == ["text_namu_v2_0012"]
    assert summary["text_locator_missing_count_before"] == 1
    assert summary["text_locator_missing_count_after"] == 0
    assert summary["llm_generated_locator_missing_failure_before"] == 1
    assert summary["llm_generated_locator_missing_failure_after"] == 0
    assert summary["llm_generated_locator_field_mismatch_failure_after"] == 0
    assert summary["text_locator_byte_equal_after"] is True
    assert summary["text_locator_normalized_equal_after"] is True
    assert summary["promotion_evidence"] is False
    assert summary["generation_used_expected_answer"] is False
    assert summary["generation_used_gold_fields"] is False
    assert summary["generation_used_supporting_evidence"] is False
    assert summary["guardrails"]["promotion_gate_auto_run"] is False
    assert attribution["run_id"] == AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]

    assert [row["query_id"] for row in results] == ["text_namu_v2_0012"]
    row = results[0]
    assert row["source_family"] == "TEXT"
    assert row["denominator_locator"]["text_locator"]
    for lane_name in ("live_llm_retrieval_topk", "live_llm_query_bound_oracle"):
        lane = row["lane_results"][lane_name]
        validation = lane["llm_generated_locator_validation"]
        unit_id = row["denominator_search_unit_id"]
        generated_locator = next(
            locator for locator in lane["llm_generated_citation_locators"] if locator["search_unit_id"] == unit_id
        )
        text_locator_check = validation["field_comparisons_by_search_unit_id"][unit_id]["text_locator"]
        assert generated_locator["text_locator"]
        assert validation["ok"] is True
        assert validation["missing_fields_by_search_unit_id"] == {}
        assert validation["mismatched_fields_by_search_unit_id"] == {}
        assert text_locator_check["byte_equal"] is True
        assert text_locator_check["normalized_equal"] is True
        assert lane["failure_category"] != "CITATION_PAYLOAD_SCHEMA_MISMATCH"

    delta_row = triage_delta["rows"][0]
    assert delta_row["query_id"] == "text_namu_v2_0012"
    assert delta_row["before"]["text_locator_present"] is False
    assert delta_row["after"]["text_locator_present"] is True
    assert delta_row["after"]["text_locator_byte_equal"] is True
    assert delta_row["after"]["text_locator_normalized_equal"] is True
    assert delta_row["after"]["llm_generated_locator_missing_failure"] is False
    assert delta_row["after"]["llm_generated_locator_field_mismatch_failure"] is False

    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(triage_delta)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["result_count"] == 1


def test_v3_1_1_post_strict_json_locator_triage_all_track_measurement_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_1_POST_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_1_POST_RESULTS)
    attribution = read_json(AGENTIC_V3_1_1_POST_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_1_POST_AUDIT_JSONL)
    triage_queue = read_json(AGENTIC_V3_1_1_POST_TRIAGE_QUEUE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID
    assert summary["measurement_classification"] == "all_track_foundation_measurement_v3_1_1_post_strict_json_locator_triage_diagnostic_only"
    assert summary["total_denominator_rows"] == 29
    assert summary["result_count"] == 29
    assert len(results) == 29
    assert len(audit_rows) == 29
    assert summary["rows_by_source_family"] == {"PDF": 4, "TEXT": 6, "XLSX": 19}
    assert set(summary["lane_counts"]) == {"v3_primary_replay", "live_llm_retrieval_topk", "live_llm_query_bound_oracle"}
    assert all(set(row["lane_results"]) == set(summary["lane_counts"]) for row in results)
    assert summary["strict_json_parse_failure_count_by_lane"]["live_llm_retrieval_topk"] == 0
    assert summary["strict_json_parse_failure_count_by_lane"]["live_llm_query_bound_oracle"] == 0
    assert summary["llm_generated_locator_copy_failure_count_by_lane"]["live_llm_retrieval_topk"] == 0
    assert summary["llm_generated_locator_copy_failure_count_by_lane"]["live_llm_query_bound_oracle"] == 0
    assert summary["llm_generated_locator_missing_failure_count_by_lane"]["live_llm_retrieval_topk"] == 0
    assert summary["llm_generated_locator_field_mismatch_failure_count_by_lane"]["live_llm_retrieval_topk"] == 0
    assert summary["pdf_source_pdf_path_mismatch_count"] == 0
    assert summary["xlsx_row_label_mismatch_count"] == 0
    assert summary["text_text_locator_missing_count"] == 0
    assert "answer_span_mismatch_count_by_lane" in summary
    assert "existing_pass_regression_count" in summary["regression_from_v3_1_foundation"]
    assert isinstance(summary["regression_from_v3_1_foundation"]["regressions"], list)
    assert summary["promotion_evidence"] is False
    assert summary["generation_used_expected_answer"] is False
    assert summary["generation_used_gold_fields"] is False
    assert summary["generation_used_supporting_evidence"] is False
    assert summary["guardrails"]["promotion_gate_auto_run"] is False
    assert attribution["run_id"] == AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]
    assert triage_queue["run_id"] == AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID
    assert triage_queue["strict_json_or_locator_residual_count"] == 0
    assert all(
        item["primary_failure_category"]
        not in {"LLM_STRICT_JSON_PARSE_FAILURE", "PDF_BBOX_LOCATOR_LOSS", "XLSX_CELL_LOCATOR_LOSS", "CITATION_PAYLOAD_SCHEMA_MISMATCH"}
        for item in triage_queue["items"]
    )

    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(triage_queue)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["result_count"] == 29
    assert measurement["lane_counts"] == summary["lane_counts"]


def test_v3_1_2_answer_span_renderer_triage_batch_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_2_ANSWER_SPAN_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_2_ANSWER_SPAN_RESULTS)
    attribution = read_json(AGENTIC_V3_1_2_ANSWER_SPAN_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_2_ANSWER_SPAN_AUDIT_JSONL)
    diagnostics = read_jsonl(AGENTIC_V3_1_2_ANSWER_SPAN_DIAGNOSTICS_JSONL)
    remaining = read_json(AGENTIC_V3_1_2_ANSWER_SPAN_REMAINING_TRIAGE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    first_batch = [
        "text_namu_v2_0012",
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0077",
        "text_namu_v2_0084",
    ]
    target_ids = [*first_batch, "text_namu_v2_0005"]

    assert summary["run_id"] == AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID
    assert summary["measurement_classification"] == "answer_span_renderer_triage_v3_1_2_diagnostic_only"
    assert summary["write_summary_markdown"] is False
    assert not AGENTIC_V3_1_2_ANSWER_SPAN_SUMMARY_MD.exists()
    assert summary["target_query_ids"] == target_ids
    assert summary["first_batch_query_ids"] == first_batch
    assert summary["secondary_text_watchlist_query_ids"] == ["text_namu_v2_0005"]
    assert summary["queue_source_of_truth_decision"]["selected_source_type"] == "machine_triage_queue_artifact"
    assert summary["queue_source_of_truth_decision"]["doc_drift_observed"] is True

    assert len(results) == 6
    assert len(audit_rows) == 6
    assert len(diagnostics) == 6
    assert [row["query_id"] for row in results] == target_ids
    assert [row["query_id"] for row in diagnostics] == target_ids
    assert all(row["first_batch_selected"] is True for row in results[:5])
    assert results[-1]["query_id"] == "text_namu_v2_0005"
    assert results[-1]["first_batch_selected"] is False
    assert results[-1]["include_decision"] == "included_as_secondary_text_watchlist_only_queue_rank_12"

    assert summary["lane_counts"]["v3_primary_replay"]["pass_count"] == 1
    assert summary["lane_counts"]["live_llm_retrieval_topk"]["pass_count"] == 1
    assert summary["lane_counts"]["live_llm_query_bound_oracle"]["pass_count"] == 0
    assert summary["answer_span_mismatch_count_by_lane"] == {
        "live_llm_query_bound_oracle": 12,
        "live_llm_retrieval_topk": 9,
        "v3_primary_replay": 0,
    }
    assert all(value == 0 for value in summary["strict_json_parse_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_copy_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_missing_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_field_mismatch_failure_count_by_lane"].values())
    assert summary["pdf_source_pdf_path_mismatch_count"] == 0
    assert summary["xlsx_row_label_mismatch_count"] == 0
    assert summary["text_text_locator_missing_count"] == 0

    diagnostic_counts = summary["answer_span_renderer_diagnostic_counts"]
    assert diagnostic_counts["diagnostic_only_expected_span_mismatch"] >= 11
    assert diagnostic_counts["answer_too_narrow"] >= 10
    assert diagnostic_counts["renderer_formatting_mismatch"] >= 2
    assert diagnostic_counts["scorer_normalization_gap"] >= 2
    assert "retrieval_context_insufficiency" not in diagnostic_counts

    for row in diagnostics:
        assert row["diagnostic_only"] is True
        assert row["promotion_evidence"] is False
        assert row["reference_span_audit_only"] is True
        assert row["reference_span_text_embedded"] is False
        for lane_diag in row["answer_span_renderer_diagnostics"].values():
            assert "scoring_reference_span_sha256" in lane_diag
            assert lane_diag["reference_span_text_embedded"] is False
            assert lane_diag["generation_used_expected_answer"] is False
            assert lane_diag["generation_used_supporting_evidence"] is False
            assert lane_diag["generation_used_gold_fields"] is False

    assert remaining["run_id"] == AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID
    assert remaining["source_run_id"] == AGENTIC_V3_1_1_POST_TRIAGE_RUN_ID
    assert remaining["strict_json_or_locator_residual_count"] == 0
    remaining_ids = [item["query_id"] for item in remaining["items"]]
    assert not set(first_batch).intersection(remaining_ids)
    assert "text_namu_v2_0005" in remaining_ids
    assert remaining_ids[0] == "gq_auto_010"

    assert attribution["run_id"] == AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]
    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(results)
    assert_generation_guardrail_flags_false(attribution)
    assert_generation_guardrail_flags_false(audit_rows)
    assert_generation_guardrail_flags_false(diagnostics)
    assert_generation_guardrail_flags_false(remaining)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(attribution)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(diagnostics)
    assert_no_gold_generation_source_fields(remaining)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["guardrails"] == summary["guardrails"]
    assert measurement["strict_json_parse_failure_count_by_lane"] == summary["strict_json_parse_failure_count_by_lane"]
    assert "strict_json_parse_failure_after" not in measurement
    assert measurement["answer_span_renderer_diagnostic_counts"] == diagnostic_counts

    failure_event = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_failure_attribution"
        and event.get("run_id") == AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID
    )
    assert failure_event["promotion_evidence"] is False
    assert failure_event["diagnostic_only"] is True
    assert failure_event["generation_used_expected_answer"] is False
    assert failure_event["generation_used_supporting_evidence"] is False
    assert failure_event["generation_used_gold_fields"] is False
    assert failure_event["guardrails"] == summary["guardrails"]


def test_v3_1_3_remaining_queue_answer_span_renderer_triage_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_3_REMAINING_QUEUE_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_3_REMAINING_QUEUE_RESULTS)
    attribution = read_json(AGENTIC_V3_1_3_REMAINING_QUEUE_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_3_REMAINING_QUEUE_AUDIT_JSONL)
    diagnostics = read_jsonl(AGENTIC_V3_1_3_REMAINING_QUEUE_DIAGNOSTICS_JSONL)
    remaining = read_json(AGENTIC_V3_1_3_REMAINING_QUEUE_REMAINING_TRIAGE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    target_ids = [
        "gq_auto_010",
        "gq_auto_024",
        "gq_auto_030",
        "gq_auto_043",
        "gq_pdf_section_question_001",
        "gq_xlsx_date_number_format_001",
        "text_namu_v2_0005",
    ]

    assert summary["run_id"] == AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID
    assert summary["measurement_classification"] == "remaining_queue_answer_span_renderer_triage_v3_1_3_diagnostic_only"
    assert summary["write_summary_markdown"] is False
    assert not AGENTIC_V3_1_3_REMAINING_QUEUE_SUMMARY_MD.exists()
    assert summary["target_query_ids"] == target_ids
    assert summary["queue_source_of_truth_decision"]["selected_source"] == report_artifact_repo_relative(
        AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "queue.json"
    )
    assert summary["queue_source_of_truth_decision"]["selected_source_type"] == "machine_remaining_queue_artifact"

    assert len(results) == 7
    assert len(audit_rows) == 7
    assert len(diagnostics) == 7
    assert [row["query_id"] for row in results] == target_ids
    assert [row["query_id"] for row in diagnostics] == target_ids
    assert summary["rows_by_source_family"] == {"PDF": 4, "TEXT": 1, "XLSX": 2}
    assert "gq_auto_037" not in summary["target_query_ids"]
    assert "gq_auto_037" not in json.dumps(remaining, ensure_ascii=False)

    assert summary["target_queue_pass_count_before_by_lane"] == {
        "live_llm_query_bound_oracle": 0,
        "live_llm_retrieval_topk": 3,
        "v3_primary_replay": 7,
    }
    assert summary["target_queue_pass_count_after_by_lane"] == {
        "live_llm_query_bound_oracle": 5,
        "live_llm_retrieval_topk": 5,
        "v3_primary_replay": 7,
    }
    assert summary["all_track_remeasurement_performed"] is True
    assert summary["all_track_result_count_before"] == 29
    assert summary["all_track_result_count_after"] == 29
    assert summary["all_track_pass_count_before_by_lane"] == {
        "live_llm_query_bound_oracle": 17,
        "live_llm_retrieval_topk": 20,
        "v3_primary_replay": 24,
    }
    assert summary["all_track_pass_count_after_by_lane"] == {
        "live_llm_query_bound_oracle": 22,
        "live_llm_retrieval_topk": 22,
        "v3_primary_replay": 24,
    }
    assert summary["target_queue_answer_span_mismatch_before_by_lane"] == {
        "live_llm_query_bound_oracle": 7,
        "live_llm_retrieval_topk": 4,
        "v3_primary_replay": 0,
    }
    assert summary["target_queue_answer_span_mismatch_after_by_lane"] == {
        "live_llm_query_bound_oracle": 2,
        "live_llm_retrieval_topk": 2,
        "v3_primary_replay": 0,
    }
    assert summary["all_track_answer_span_mismatch_before_by_lane"] == {
        "live_llm_query_bound_oracle": 12,
        "live_llm_retrieval_topk": 9,
        "v3_primary_replay": 0,
    }
    assert summary["all_track_answer_span_mismatch_after_by_lane"] == {
        "live_llm_query_bound_oracle": 7,
        "live_llm_retrieval_topk": 7,
        "v3_primary_replay": 0,
    }
    assert all(value == 0 for value in summary["strict_json_parse_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_copy_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_missing_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_field_mismatch_failure_count_by_lane"].values())
    assert summary["pdf_source_pdf_path_mismatch_count"] == 0
    assert summary["xlsx_row_label_mismatch_count"] == 0
    assert summary["text_text_locator_missing_count"] == 0
    assert all(
        all(value == 0 for value in item.values()) if isinstance(item, dict) else item == 0
        for item in summary["all_track_residuals_after"].values()
    )
    assert summary["text_namu_v2_0005_lane_a_b_not_degraded"] is True
    assert summary["text_namu_v2_0005_lane_c_improved"] is True

    remaining_ids = [item["query_id"] for item in remaining["items"]]
    assert remaining_ids == ["gq_auto_010", "gq_pdf_section_question_001"]
    assert remaining["strict_json_or_locator_residual_count"] == 0
    assert remaining["source_queue_artifact"] == report_artifact_repo_relative(
        AGENTIC_V3_1_2_ANSWER_SPAN_RUN_ID, "queue.json"
    )

    for row in diagnostics:
        assert row["diagnostic_only"] is True
        assert row["promotion_evidence"] is False
        assert row["reference_span_audit_only"] is True
        assert row["reference_span_text_embedded"] is False
        for lane_diag in row["answer_span_renderer_diagnostics"].values():
            assert lane_diag["reference_span_text_embedded"] is False
            assert lane_diag["generation_used_expected_answer"] is False
            assert lane_diag["generation_used_supporting_evidence"] is False
            assert lane_diag["generation_used_gold_fields"] is False

    assert attribution["run_id"] == AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]
    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(results)
    assert_generation_guardrail_flags_false(attribution)
    assert_generation_guardrail_flags_false(audit_rows)
    assert_generation_guardrail_flags_false(diagnostics)
    assert_generation_guardrail_flags_false(remaining)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(attribution)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(diagnostics)
    assert_no_gold_generation_source_fields(remaining)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["guardrails"] == summary["guardrails"]
    assert measurement["all_track_remeasurement_performed"] is True
    assert measurement["all_track_pass_count_after_by_lane"] == summary["all_track_pass_count_after_by_lane"]
    assert measurement["queue_source_of_truth_decision"] == summary["queue_source_of_truth_decision"]


def test_v3_1_4_pdf_residual_answer_span_renderer_triage_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_4_PDF_RESIDUAL_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_4_PDF_RESIDUAL_RESULTS)
    attribution = read_json(AGENTIC_V3_1_4_PDF_RESIDUAL_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_4_PDF_RESIDUAL_AUDIT_JSONL)
    diagnostics = read_jsonl(AGENTIC_V3_1_4_PDF_RESIDUAL_DIAGNOSTICS_JSONL)
    remaining = read_json(AGENTIC_V3_1_4_PDF_RESIDUAL_REMAINING_TRIAGE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    target_ids = ["gq_auto_010", "gq_pdf_section_question_001"]

    assert summary["run_id"] == AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID
    assert summary["measurement_classification"] == "pdf_residual_answer_span_renderer_triage_v3_1_4_diagnostic_only"
    assert summary["write_summary_markdown"] is False
    assert not AGENTIC_V3_1_4_PDF_RESIDUAL_SUMMARY_MD.exists()
    assert summary["target_query_ids"] == target_ids
    assert summary["queue_source_of_truth_decision"]["selected_source"] == report_artifact_repo_relative(
        AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "queue.json"
    )
    assert summary["queue_source_of_truth_decision"]["selected_source_type"] == "machine_remaining_queue_artifact"

    assert len(results) == 2
    assert len(audit_rows) == 2
    assert len(diagnostics) == 2
    assert [row["query_id"] for row in results] == target_ids
    assert [row["query_id"] for row in diagnostics] == target_ids
    assert summary["rows_by_source_family"] == {"PDF": 2, "TEXT": 0, "XLSX": 0}

    assert summary["target_queue_pass_count_before_by_lane"] == {
        "live_llm_query_bound_oracle": 0,
        "live_llm_retrieval_topk": 0,
        "v3_primary_replay": 2,
    }
    assert summary["target_queue_pass_count_after_by_lane"] == {
        "live_llm_query_bound_oracle": 1,
        "live_llm_retrieval_topk": 1,
        "v3_primary_replay": 2,
    }
    assert summary["all_track_remeasurement_performed"] is True
    assert summary["all_track_before_run_id"] == AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID
    assert summary["all_track_after_run_id"] == AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID
    assert summary["all_track_result_count_before"] == 29
    assert summary["all_track_result_count_after"] == 29
    assert summary["all_track_pass_count_before_by_lane"] == {
        "live_llm_query_bound_oracle": 22,
        "live_llm_retrieval_topk": 22,
        "v3_primary_replay": 24,
    }
    assert summary["all_track_pass_count_after_by_lane"] == {
        "live_llm_query_bound_oracle": 23,
        "live_llm_retrieval_topk": 23,
        "v3_primary_replay": 24,
    }
    assert summary["target_queue_answer_span_mismatch_before_by_lane"] == {
        "live_llm_query_bound_oracle": 2,
        "live_llm_retrieval_topk": 2,
        "v3_primary_replay": 0,
    }
    assert summary["target_queue_answer_span_mismatch_after_by_lane"] == {
        "live_llm_query_bound_oracle": 1,
        "live_llm_retrieval_topk": 1,
        "v3_primary_replay": 0,
    }
    assert summary["all_track_answer_span_mismatch_before_by_lane"] == {
        "live_llm_query_bound_oracle": 7,
        "live_llm_retrieval_topk": 7,
        "v3_primary_replay": 0,
    }
    assert summary["all_track_answer_span_mismatch_after_by_lane"] == {
        "live_llm_query_bound_oracle": 6,
        "live_llm_retrieval_topk": 6,
        "v3_primary_replay": 0,
    }
    assert all(value == 0 for value in summary["strict_json_parse_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_copy_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_missing_failure_count_by_lane"].values())
    assert all(value == 0 for value in summary["llm_generated_locator_field_mismatch_failure_count_by_lane"].values())
    assert summary["pdf_source_pdf_path_mismatch_count"] == 0
    assert summary["xlsx_row_label_mismatch_count"] == 0
    assert summary["text_text_locator_missing_count"] == 0
    assert all(
        all(value == 0 for value in item.values()) if isinstance(item, dict) else item == 0
        for item in summary["all_track_residuals_after"].values()
    )

    remaining_ids = [item["query_id"] for item in remaining["items"]]
    assert remaining_ids == ["gq_auto_010"]
    assert remaining["strict_json_or_locator_residual_count"] == 0
    assert remaining["source_queue_artifact"] == report_artifact_repo_relative(
        AGENTIC_V3_1_3_REMAINING_QUEUE_RUN_ID, "queue.json"
    )
    assert summary["pdf_table_axis_disambiguation"]["gq_pdf_section_question_001"]["applied_lanes"] == [
        "live_llm_retrieval_topk",
        "live_llm_query_bound_oracle",
    ]
    assert summary["pdf_table_axis_disambiguation"]["gq_auto_010"]["classification"] == (
        "retrieval_context_insufficiency"
    )

    for row in diagnostics:
        assert row["diagnostic_only"] is True
        assert row["promotion_evidence"] is False
        assert row["reference_span_audit_only"] is True
        assert row["reference_span_text_embedded"] is False
        for lane_diag in row["answer_span_renderer_diagnostics"].values():
            assert lane_diag["reference_span_text_embedded"] is False
            assert lane_diag["generation_used_expected_answer"] is False
            assert lane_diag["generation_used_supporting_evidence"] is False
            assert lane_diag["generation_used_gold_fields"] is False

    assert attribution["run_id"] == AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID
    assert attribution["guardrails"] == summary["guardrails"]
    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(results)
    assert_generation_guardrail_flags_false(attribution)
    assert_generation_guardrail_flags_false(audit_rows)
    assert_generation_guardrail_flags_false(diagnostics)
    assert_generation_guardrail_flags_false(remaining)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(attribution)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(diagnostics)
    assert_no_gold_generation_source_fields(remaining)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["guardrails"] == summary["guardrails"]
    assert measurement["all_track_remeasurement_performed"] is True
    assert measurement["all_track_pass_count_after_by_lane"] == summary["all_track_pass_count_after_by_lane"]
    assert measurement["queue_source_of_truth_decision"] == summary["queue_source_of_truth_decision"]


def test_v3_1_5_gq_auto_010_source_bound_context_coverage_diagnostic_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_SUMMARY_JSON)
    diagnostics = read_jsonl(AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_DIAGNOSTICS_JSONL)
    remaining = read_json(AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_TRIAGE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID
    assert summary["measurement_classification"] == (
        "gq_auto_010_source_bound_retrieval_context_coverage_diagnostic_v3_1_5_diagnostic_only"
    )
    assert summary["target_query_ids"] == ["gq_auto_010"]
    assert summary["source_queue_artifact"] == report_artifact_repo_relative(
        AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID, "queue.json"
    )
    assert summary["source_queue_preflight"]["only_gq_auto_010_remaining"] is True
    assert summary["source_queue_preflight"]["strict_json_or_locator_residual_count"] == 0
    assert summary["classification_result"]["query_id"] == "gq_auto_010"
    assert summary["classification_result"]["classification"] == "query_bound_searchunit_too_narrow"
    assert summary["classification_result"]["final_queue_decision"] == "remain_in_queue"
    assert summary["non_production_index_or_export_fix_applied"] is False
    assert summary["all_track_remeasurement_performed"] is False
    assert summary["official_retrieval_metrics_computed"] is False
    assert summary["artifact_policy"]["minimum_durable_artifacts"] == [
        "summary_json",
        "context_coverage_diagnostics_jsonl",
        "remaining_triage_queue_json",
        "rag_current_eval_status_jsonl",
    ]
    assert "results_jsonl" not in summary["artifact_paths"]
    assert "failure_attribution_json" not in summary["artifact_paths"]
    assert not (REPORT_DIR / f"{AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID}_results.jsonl").exists()
    assert not (REPORT_DIR / f"{AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID}_failure_attribution.json").exists()
    assert not (REPORT_DIR / f"{AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID}_actual_response_audit.jsonl").exists()

    assert len(diagnostics) == 1
    row = diagnostics[0]
    assert row["query_id"] == "gq_auto_010"
    assert row["diagnostic_only"] is True
    assert row["promotion_evidence"] is False
    assert row["reference_span_audit_only"] is True
    assert row["reference_span_text_embedded"] is False
    assert row["audit_numeric_span_probe_source"] == "expected_answer_numeric_tokens_audit_only"
    assert row["audit_numeric_span_count"] == 2
    assert row["v3_1_4_cited_context_contains_all_audit_numeric_spans"] is False
    assert row["current_cited_search_unit_contains_all_audit_numeric_spans"] is False
    assert row["same_document_search_unit_contains_all_audit_numeric_spans"] is False
    assert row["adjacent_page_window_search_unit_contains_all_audit_numeric_spans"] is False
    assert row["raw_source_pdf_text_contains_all_audit_numeric_spans"] is True
    assert row["issue_classification"] == "query_bound_searchunit_too_narrow"
    assert row["behavior_change_made"] is False
    assert row["official_retrieval_metric"] is False
    assert row["generation_used_expected_answer"] is False
    assert row["generation_used_supporting_evidence"] is False
    assert row["generation_used_gold_fields"] is False

    remaining_ids = [item["query_id"] for item in remaining["items"]]
    assert remaining_ids == ["gq_auto_010"]
    assert remaining["strict_json_or_locator_residual_count"] == 0
    assert remaining["source_queue_artifact"] == summary["source_queue_artifact"]
    assert remaining["items"][0]["coverage_classification"] == "query_bound_searchunit_too_narrow"
    assert remaining["items"][0]["recommended_next_step"] == (
        "decide_or_implement_safe_pdf_paragraph_window_expansion_before_live_generation"
    )

    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(diagnostics)
    assert_generation_guardrail_flags_false(remaining)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(diagnostics)
    assert_no_gold_generation_source_fields(remaining)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["guardrails"] == summary["guardrails"]
    assert measurement["classification_result"] == summary["classification_result"]
    assert measurement["source_queue_artifact"] == summary["source_queue_artifact"]


def test_v3_1_6_gq_auto_010_pdf_paragraph_window_expansion_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RESULTS)
    attribution = read_json(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_ATTRIBUTION_JSON)
    audit_rows = read_jsonl(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_AUDIT_JSONL)
    answer_span_rows = read_jsonl(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_ANSWER_SPAN_DIAGNOSTICS_JSONL)
    expansion_rows = read_jsonl(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_CONTEXT_DIAGNOSTICS_JSONL)
    remaining = read_json(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_REMAINING_TRIAGE_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    assert summary["run_id"] == AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID
    assert summary["source_queue_artifact"] == report_artifact_repo_relative(
        AGENTIC_V3_1_5_SOURCE_BOUND_COVERAGE_RUN_ID, "queue.json"
    )
    assert summary["target_query_ids"] == ["gq_auto_010"]
    assert summary["source_queue_preflight"]["queue_query_ids"] == ["gq_auto_010"]
    assert summary["source_queue_preflight"]["classification"] == "query_bound_searchunit_too_narrow"
    assert summary["source_queue_preflight"]["strict_json_or_locator_residual_count"] == 0
    assert summary["source_queue_preflight"]["ok"] is True
    assert summary["source_queue_preflight"]["errors"] == []
    assert summary["queue_source_of_truth_decision"]["selected_source_type"] == "machine_remaining_queue_artifact"
    assert summary["queue_source_of_truth_decision"]["docs_are_human_facing_narrative_only"] is True

    assert summary["result_count"] == 1
    assert summary["unique_query_id_count"] == 1
    assert summary["target_row_count"] == 1
    assert [row["query_id"] for row in results] == ["gq_auto_010"]
    assert [row["query_id"] for row in audit_rows] == ["gq_auto_010"]
    assert [row["query_id"] for row in answer_span_rows] == ["gq_auto_010"]
    assert [row["query_id"] for row in expansion_rows] == ["gq_auto_010"]

    row = results[0]
    assert set(row["lane_results"]) == {
        "v3_primary_replay",
        "live_llm_retrieval_topk",
        "live_llm_query_bound_oracle",
    }
    assert row["row_level_classification_change"]["improved_lane_names"] == [
        "live_llm_retrieval_topk",
        "live_llm_query_bound_oracle",
    ]
    assert row["row_level_classification_change"]["regressed_lane_names"] == []
    assert row["row_level_classification_change"]["unchanged_failed_lane_names"] == []
    assert summary["target_queue_pass_count_before_by_lane"] == {
        "v3_primary_replay": 1,
        "live_llm_retrieval_topk": 0,
        "live_llm_query_bound_oracle": 0,
    }
    assert summary["target_queue_pass_count_after_by_lane"] == {
        "v3_primary_replay": 1,
        "live_llm_retrieval_topk": 1,
        "live_llm_query_bound_oracle": 1,
    }
    assert summary["all_track_remeasurement_performed"] is True
    assert summary["all_track_before_run_id"] == AGENTIC_V3_1_4_PDF_RESIDUAL_RUN_ID
    assert summary["all_track_after_run_id"] == AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID
    assert summary["all_track_result_count_before"] == 29
    assert summary["all_track_result_count_after"] == 29
    assert summary["all_track_pass_count_before_by_lane"] == {
        "v3_primary_replay": 24,
        "live_llm_retrieval_topk": 23,
        "live_llm_query_bound_oracle": 23,
    }
    assert summary["all_track_pass_count_after_by_lane"] == {
        "v3_primary_replay": 24,
        "live_llm_retrieval_topk": 24,
        "live_llm_query_bound_oracle": 24,
    }
    assert summary["all_track_non_target_context_expansion_query_ids"] == []
    assert summary["all_track_non_target_unexpected_change_count"] == 0

    expansion = expansion_rows[0]
    assert expansion["expansion_policy_name"] == "same_page_pdf_paragraph_line_window_v1"
    assert expansion["expansion_policy_version"] == "v1"
    assert expansion["expansion_attempted"] is True
    assert expansion["expansion_applied"] is True
    assert expansion["locator_safe_metadata_available"] is True
    assert expansion["source_pdf_path"] == row["denominator_locator"]["source_pdf_path"]
    assert expansion["document_version_id"] == row["denominator_locator"]["document_version_id"]
    assert expansion["original_cited_search_unit_ids"] == ["7bf516bf-2a17-4303-86d8-3cffaa04846e"]
    assert expansion["expanded_context_contains_all_audit_numeric_spans"] is True
    assert expansion["audit_numeric_spans_used_only_post_generation"] is True
    assert expansion["reference_span_text_embedded"] is False
    assert expansion["generation_used_expected_answer"] is False
    assert expansion["generation_used_supporting_evidence"] is False
    assert expansion["generation_used_gold_fields"] is False
    assert expansion["generated_answer_cited_expansion_unit_by_lane"] == {
        "live_llm_retrieval_topk": True,
        "live_llm_query_bound_oracle": True,
    }
    assert expansion["generated_answer_cited_original_search_unit_by_lane"] == {
        "live_llm_retrieval_topk": False,
        "live_llm_query_bound_oracle": False,
    }
    assert expansion["locator_validation_passed_by_lane"] == {
        "live_llm_retrieval_topk": True,
        "live_llm_query_bound_oracle": True,
    }
    assert expansion["expansion_unit_ids"] == ["pdfwin_b1c6527f848018640ad5ed231877c662"]
    for unit in expansion["expansion_units"]:
        assert unit["source_pdf_path"] == expansion["source_pdf_path"]
        assert unit["document_version_id"] == expansion["document_version_id"]
        assert unit["page"] == expansion["page"]
        assert unit["physical_page_index"] == expansion["physical_page_index"]
        assert unit["source"] == "pymupdf_source_pdf_same_page_line_window"
        assert unit["expansion_policy_version"] == "v1"
        assert unit["bbox"] == [63.65, 95.06, 341.94, 163.68]
        assert unit["region_type"] == "paragraph_window"
        assert isinstance(unit["bbox"], list) and len(unit["bbox"]) == 4
        assert unit["search_unit_id"].startswith("pdfwin_")
        assert unit["non_production_diagnostic_context_expansion"] is True
        assert unit["normalized_excerpt_sha256"]
    for lane_name in ("live_llm_retrieval_topk", "live_llm_query_bound_oracle"):
        lane = row["lane_results"][lane_name]
        assert lane["cited_search_unit_ids"] == ["pdfwin_b1c6527f848018640ad5ed231877c662"]
        citation_payload = lane["scored_citations"][0]["search_unit_citation_payload"]
        assert citation_payload["source_bound_official_denominator"] is False
        assert citation_payload["source_bound_diagnostic_context_expansion"] is True
        assert citation_payload["locator_schema"] == "pdf_source_bound_context_expansion_v1"

    assert remaining["items"] == []
    assert remaining["processed_query_ids"] == ["gq_auto_010"]
    assert remaining["strict_json_or_locator_residual_count"] == 0
    assert remaining["source_queue_artifact"] == summary["source_queue_artifact"]
    assert remaining["all_track_remeasurement_performed"] is True

    assert summary["behavior_change_made"] is True
    assert summary["context_expansion_attempted"] is True
    assert summary["context_expansion_applied"] is True
    assert summary["non_production_index_or_export_fix_applied"] is False
    assert summary["official_retrieval_metrics_computed"] is False
    assert summary["official_ndcg_computed"] is False
    assert summary["official_mrr_computed"] is False
    assert summary["official_hit_at_k_computed"] is False
    assert summary["lane_score_collapsed"] is False
    assert summary["all_track_residuals_after"]["pdf_source_pdf_path_mismatch_count"] == 0
    assert summary["all_track_residuals_after"]["xlsx_row_label_mismatch_count"] == 0
    assert summary["all_track_residuals_after"]["text_text_locator_missing_count"] == 0
    assert all(
        value == 0
        for value in summary["all_track_residuals_after"]["strict_json_parse_failure_count_by_lane"].values()
    )
    assert all(
        value == 0
        for value in summary["all_track_residuals_after"]["llm_generated_locator_copy_failure_count_by_lane"].values()
    )
    assert summary["artifact_policy"]["minimum_durable_artifacts"] == [
        "summary_json",
        "results_jsonl",
        "failure_attribution_json",
        "actual_response_audit_jsonl",
        "answer_span_diagnostics_jsonl",
        "context_expansion_diagnostics_jsonl",
        "remaining_triage_queue_json",
        "rag_current_eval_status_jsonl",
    ]
    for key in (
        "results_jsonl",
        "failure_attribution_json",
        "actual_response_audit_jsonl",
        "answer_span_diagnostics_jsonl",
        "context_expansion_diagnostics_jsonl",
        "remaining_triage_queue_json",
    ):
        assert key in summary["artifact_paths"]
        assert f"{key}_sha256" in summary["artifact_paths"]
    assert not (REPORT_DIR / f"{AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID}_summary.md").exists()

    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(results)
    assert_generation_guardrail_flags_false(attribution)
    assert_generation_guardrail_flags_false(audit_rows)
    assert_generation_guardrail_flags_false(answer_span_rows)
    assert_generation_guardrail_flags_false(expansion_rows)
    assert_generation_guardrail_flags_false(remaining)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(results)
    assert_no_gold_generation_source_fields(attribution)
    assert_no_gold_generation_source_fields(audit_rows)
    assert_no_gold_generation_source_fields(answer_span_rows)
    assert_no_gold_generation_source_fields(expansion_rows)
    assert_no_gold_generation_source_fields(remaining)
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID}*silver*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID}*gold*"))
    assert not list(REPORT_DIR.glob(f"{AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID}*promotion*"))

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID
    )
    assert measurement["promotion_evidence"] is False
    assert measurement["diagnostic_only"] is True
    assert measurement["guardrails"] == summary["guardrails"]
    assert measurement["context_expansion_applied"] is True
    assert measurement["all_track_pass_count_after_by_lane"] == summary["all_track_pass_count_after_by_lane"]


def test_v3_1_7_post_residual_queue_closure_inventory_is_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SUMMARY_JSON)
    inventory_rows = read_jsonl(AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_INVENTORY_JSONL)
    remaining = read_json(AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_REMAINING_JSON)
    decision_packet = read_json(AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_DECISION_PACKET_JSON)
    silver_audit = read_json(AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SILVER_AUDIT_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    residual_query_ids = {
        "text_namu_v2_0012",
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0077",
        "text_namu_v2_0084",
    }
    lane_names = {"v3_primary_replay", "live_llm_retrieval_topk", "live_llm_query_bound_oracle"}

    assert summary["run_id"] == AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_RUN_ID
    assert summary["diagnostic_only"] is True
    assert summary["promotion_evidence"] is False
    assert summary["behavior_change_made"] is False
    assert summary["active_remaining_queue_empty"] is True
    assert summary["active_remaining_queue_status"] == "cleared"
    assert summary["closure_type"] == "diagnostic_queue_cleared_not_promotion"
    assert summary["source_closure_assertions"]["passed"] is True
    assert summary["all_track_live_generation_rerun"] is False
    assert summary["all_track_result_count_after"] == 29
    assert summary["all_track_reconstruction_matches_v3_1_6_summary"] is True
    assert summary["all_track_pass_count_after_by_lane"] == {
        "v3_primary_replay": 24,
        "live_llm_retrieval_topk": 24,
        "live_llm_query_bound_oracle": 24,
    }
    assert summary["all_track_non_pass_count_after_by_lane"] == {
        "v3_primary_replay": 5,
        "live_llm_retrieval_topk": 5,
        "live_llm_query_bound_oracle": 5,
    }
    assert summary["all_track_answer_span_mismatch_after_by_lane"] == {
        "v3_primary_replay": 0,
        "live_llm_retrieval_topk": 5,
        "live_llm_query_bound_oracle": 5,
    }
    assert set(summary["all_track_residual_query_ids"]) == residual_query_ids
    assert summary["residual_inventory_query_count"] == 5
    assert summary["residual_inventory_lane_item_count"] == 15
    assert summary["residual_inventory_bucket_counts"]["gold_policy_review_candidate"] == 15
    assert summary["residual_inventory_bucket_counts"]["implementation_safe_followup"] == 0
    assert summary["residual_inventory_bucket_counts"]["scorer_normalization_review_candidate"] == 3
    assert summary["any_residual_requires_user_decision"] is True
    assert summary["any_residual_safe_to_fix_without_user_decision"] is False
    assert summary["official_retrieval_metrics_still_blocked"] is True
    assert summary["next_phase"] == "gold_policy_review_packet_preparation"
    assert summary["non_binding_metric_readiness_memo"]["official_ndcg_mrr_hit_at_k_computed"] is False
    assert summary["non_binding_metric_readiness_memo"]["mmr_note"] == (
        "MMR is a retrieval/reranking strategy, not an evaluation metric."
    )
    assert summary["source_artifact_hash_audit"]["mismatch_count"] >= 1
    assert summary["source_artifact_hash_closure_passed"] is False

    assert len(inventory_rows) == 15
    assert {row["query_id"] for row in inventory_rows} == residual_query_ids
    assert {row["lane_name"] for row in inventory_rows} == lane_names
    assert {row["source_family"] for row in inventory_rows} == {"TEXT"}
    for row in inventory_rows:
        assert row["strict_json_parse_passed"] is True
        assert row["citation_locator_validation_passed"] is True
        assert row["citation_support_present"] is True
        assert row["failure_is_answer_span_related"] is True
        assert row["failure_is_gold_policy_related"] is True
        assert row["safe_to_fix_without_user_gold_decision"] is False
        assert row["requires_user_gold_policy_decision"] is True
        assert row["reference_span_text_embedded"] is False
        assert "gold_policy_review_candidate" in row["residual_buckets"]

    assert remaining["items"] == []
    assert remaining["active_implementation_queue_empty"] is True
    assert remaining["all_track_residuals_exist"] is True
    assert remaining["residuals_require_user_policy_review"] is True
    assert set(remaining["all_track_residual_query_ids"]) == residual_query_ids

    assert decision_packet["decision_item_count"] == 5
    assert {item["query_id"] for item in decision_packet["decision_items"]} == residual_query_ids
    for item in decision_packet["decision_items"]:
        assert item["safe_for_human_review_only"] is True
        assert item["raw_reference_text_embedded"] is False
        assert item["raw_supporting_text_embedded"] is False
        assert item["raw_gold_text_embedded"] is False
        assert item["safe_source_excerpt_hashes_counts"]

    assert silver_audit["silver_generation_closed"] is True
    assert silver_audit["silver_rows_created"] is False
    assert silver_audit["official_29_query_ids_excluded_from_silver_tuning_sets"] is True
    assert silver_audit["candidate_artifacts_excluded_as_generation_source"] is True
    assert silver_audit["silver_is_gold"] is False
    assert silver_audit["silver_is_official_denominator"] is False
    assert silver_audit["silver_is_promotion_evidence"] is False

    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(inventory_rows)
    assert_generation_guardrail_flags_false(remaining)
    assert_generation_guardrail_flags_false(decision_packet)
    assert_generation_guardrail_flags_false(silver_audit)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(inventory_rows)
    assert_no_gold_generation_source_fields(remaining)
    assert_no_gold_generation_source_fields(decision_packet)
    assert_no_gold_generation_source_fields(silver_audit)
    assert not (REPORT_DIR / f"{AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID}_summary.md").exists()

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID
    )
    assert measurement["diagnostic_only"] is True
    assert measurement["promotion_evidence"] is False
    assert measurement["active_remaining_queue_empty"] is True
    assert measurement["all_track_residuals_exist"] is True
    assert measurement["recommended_next_phase"] == "gold_policy_review_packet_preparation"
    assert measurement["official_retrieval_metrics_computed"] is False
    assert measurement["lane_score_collapsed"] is False


def test_v3_1_8_gold_policy_packet_preparation_is_compact_and_guarded() -> None:
    summary = read_json(AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_SUMMARY_JSON)
    packet = read_json(AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_HUMAN_REVIEW_JSON)
    decision_rows = read_jsonl(AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_DECISION_MATRIX_JSONL)
    remaining = read_json(AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_REMAINING_JSON)
    status_events = read_jsonl(REPORT_DIR / "status.jsonl")

    residual_query_ids = [
        "text_namu_v2_0012",
        "text_namu_v2_0014",
        "text_namu_v2_0017",
        "text_namu_v2_0077",
        "text_namu_v2_0084",
    ]
    decision_options = [
        "keep_current_strict_reference_boundary",
        "approve_scorer_or_renderer_review_without_gold_mutation",
        "revise_gold_or_label_policy",
    ]

    assert summary["run_id"] == AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID
    assert summary["source_run_id"] == AGENTIC_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_RUN_ID
    assert summary["diagnostic_only"] is True
    assert summary["promotion_evidence"] is False
    assert summary["behavior_change_made"] is False
    assert summary["production_mutation"] is False
    assert summary["denominator_mutation"] is False
    assert summary["gold_mutation"] is False
    assert summary["human_label_mutation"] is False
    assert summary["expected_answer_mutation"] is False
    assert summary["supporting_evidence_mutation"] is False
    assert summary["relevance_label_mutation"] is False
    assert summary["answerability_label_mutation"] is False
    assert summary["generation_used_expected_answer"] is False
    assert summary["generation_used_supporting_evidence"] is False
    assert summary["generation_used_gold_fields"] is False
    assert summary["candidate_artifacts_as_generation_source"] is False
    assert summary["official_ndcg_computed"] is False
    assert summary["official_mrr_computed"] is False
    assert summary["official_hit_at_k_computed"] is False
    assert summary["lane_score_collapsed"] is False
    assert summary["all_track_live_generation_rerun"] is False
    assert summary["active_implementation_queue_empty"] is True
    assert summary["implementation_safe_residual_count"] == 0
    assert summary["decision_item_count"] == 5
    assert summary["decision_query_ids"] == residual_query_ids
    assert summary["decision_options"] == decision_options
    assert summary["metadata_drift_observed"] is True
    assert summary["source_artifact_hash_closure_required_for_policy_packet"] is False
    assert summary["silver_generation_closed"] is True
    assert summary["silver_rows_created"] is False
    assert summary["human_review_packet_contains_policy_material"] is True
    assert summary["raw_reference_text_embedded_in_generation"] is False
    assert summary["raw_supporting_text_embedded_in_generation"] is False
    assert summary["raw_gold_text_embedded_in_generation"] is False

    assert set(summary["artifact_paths"]) == {
        "summary_json",
        "human_review_packet_json",
        "human_review_packet_json_sha256",
        "decision_matrix_jsonl",
        "decision_matrix_jsonl_sha256",
        "remaining_triage_queue_json",
        "remaining_triage_queue_json_sha256",
        "status_jsonl",
    }
    assert summary["artifact_policy"]["classification_only_minimum_artifact_set"] == [
        "summary_json",
        "human_review_packet_json",
        "decision_matrix_jsonl",
        "remaining_triage_queue_json",
        "status_jsonl",
    ]
    assert summary["artifact_policy"]["full_results_jsonl_created"] is False
    assert summary["artifact_policy"]["failure_attribution_json_created"] is False
    assert summary["artifact_policy"]["actual_response_audit_jsonl_created"] is False
    assert summary["artifact_policy"]["per_run_markdown_report_created"] is False
    for forbidden_key in (
        "results_jsonl",
        "failure_attribution_json",
        "actual_response_audit_jsonl",
        "summary_md",
    ):
        assert forbidden_key not in summary["artifact_paths"]
    for suffix in ("results.jsonl", "failure.json", "audit.jsonl", "summary.md"):
        assert not report_artifact_path(AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID, suffix).exists()

    assert packet["decision_item_count"] == 5
    assert [item["query_id"] for item in packet["decision_items"]] == residual_query_ids
    assert packet["decision_options"] == decision_options
    assert packet["human_review_packet_contains_policy_material"] is True
    assert packet["generation_source"] is False
    assert packet["raw_reference_text_embedded_in_generation"] is False
    assert packet["raw_supporting_text_embedded_in_generation"] is False
    assert packet["raw_gold_text_embedded_in_generation"] is False
    for item in packet["decision_items"]:
        assert item["source_family"] == "TEXT"
        assert item["policy_decision_options"] == decision_options
        assert item["requires_user_policy_decision"] is True
        assert item["requires_user_gold_policy_decision"] is True
        assert item["requires_user_relevance_label_decision"] is True
        assert item["requires_user_answerability_label_decision"] is True
        assert item["implementation_safe"] is False
        assert item["raw_reference_text_included"] is True
        assert item["raw_supporting_text_included"] is True
        assert item["raw_gold_text_included"] is True
        assert item["human_review_only"] is True
        assert item["generation_source"] is False
        assert item["not_silver_source"] is True
        assert item["not_gold_mutation"] is True
        assert item["policy_material_excluded_from_generation"] is True
        assert len(item["lane_level_status"]) == 3
        for lane in item["lane_level_status"]:
            assert lane["current_generated_answer"]
            assert lane["generation_source"] is False
            assert lane["human_review_only"] is True
            assert lane["citation_locator_validation_passed"] is True
            locator = lane["citation_locator_search_unit_metadata"]
            assert locator["search_unit_id"]
            assert locator["document_version_id"]
            assert locator["text_locator"]["chunk_id"]
            assert lane["scoring_reference_span_information"]["scoring_reference_span_sha256"]
        material = item["current_policy_material"]
        for key in ("expected_answer", "supporting_evidence"):
            assert material[key]["text"]
            assert material[key]["sha256"]
            assert material[key]["human_review_only"] is True
            assert material[key]["generation_source"] is False
            assert material[key]["not_silver_source"] is True
            assert material[key]["not_gold_mutation"] is True

    assert len(decision_rows) == 5
    assert [row["query_id"] for row in decision_rows] == residual_query_ids
    for row in decision_rows:
        assert row["decision_options"] == decision_options
        assert row["requires_user_policy_decision"] is True
        assert row["implementation_safe"] is False
        assert row["policy_material_generation_source"] is False
        assert row["human_review_only_policy_material_included"] is True

    assert remaining["items"] == []
    assert remaining["active_implementation_queue_empty"] is True
    assert remaining["implementation_safe_residual_count"] == 0
    assert remaining["policy_review_query_ids"] == residual_query_ids
    assert remaining["residuals_require_user_policy_review"] is True

    assert_generation_guardrail_flags_false(summary)
    assert_generation_guardrail_flags_false(packet)
    assert_generation_guardrail_flags_false(decision_rows)
    assert_generation_guardrail_flags_false(remaining)
    assert_no_gold_generation_source_fields(summary)
    assert_no_gold_generation_source_fields(decision_rows)
    assert_no_gold_generation_source_fields(remaining)

    measurement = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == AGENTIC_V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID
    )
    assert measurement["diagnostic_only"] is True
    assert measurement["promotion_evidence"] is False
    assert measurement["decision_item_count"] == 5
    assert measurement["decision_query_ids"] == residual_query_ids
    assert measurement["implementation_safe_residual_count"] == 0
    assert measurement["human_review_packet_contains_policy_material"] is True
    assert measurement["raw_reference_text_embedded_in_generation"] is False
    assert measurement["official_ndcg_computed"] is False
    assert measurement["lane_score_collapsed"] is False


def test_v3_1_7_pdf_window_expansion_preflight_fails_closed_without_safe_locator_metadata() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    units, diagnostic = runner.build_safe_pdf_paragraph_window_units_for_row(
        row={
            "track": "pdf_business_ocr_mm",
            "source_family": "PDF",
            "denominator_locator": {
                "source_pdf_path": "",
                "document_version_id": "",
                "page": 1,
                "physical_page_index": 0,
                "bbox": [0, 0, 10, 10],
                "region_type": "paragraph",
            },
        },
        query_id="gq_auto_010",
        generated_at="2026-05-18T00:00:00+00:00",
    )

    assert units == []
    assert diagnostic["expansion_attempted"] is True
    assert diagnostic["expansion_applied"] is False
    assert diagnostic["locator_safe_metadata_available"] is False
    assert diagnostic["fail_closed_blocker"] == "locator_safe_pdf_window_source_missing"
    assert diagnostic["candidate_artifacts_as_generation_source"] is False
    assert diagnostic["generation_used_expected_answer"] is False
    assert diagnostic["generation_used_supporting_evidence"] is False
    assert diagnostic["generation_used_gold_fields"] is False


def test_v3_1_7_pdf_context_expansion_citation_contract_is_diagnostic_only() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    expansion = read_jsonl(AGENTIC_V3_1_6_PDF_WINDOW_EXPANSION_CONTEXT_DIAGNOSTICS_JSONL)[0]
    citation = runner.build_source_bound_pdf_context_expansion_citation(
        expansion["expansion_units"][0],
        track="pdf_business_ocr_mm",
        query_id="gq_auto_010",
        source_family="PDF",
    )
    payload = citation["search_unit_citation_payload"]

    assert citation["context_expansion"] is True
    assert citation["citation_payload_validation"]["ok"] is True
    assert payload["source_bound_official_denominator"] is False
    assert payload["source_bound_diagnostic_context_expansion"] is True
    assert payload["non_production_diagnostic_context_expansion"] is True
    assert payload["locator_schema"] == "pdf_source_bound_context_expansion_v1"
    assert payload["search_unit_id"] == "pdfwin_b1c6527f848018640ad5ed231877c662"
    assert payload["expansion_policy_name"] == "same_page_pdf_paragraph_line_window_v1"
    assert payload["expansion_policy_version"] == "v1"


def test_v3_1_7_pdf_prompt_context_expansion_is_target_bound_and_query_bound() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    v3_1_4_rows = read_jsonl(AGENTIC_V3_1_4_PDF_RESIDUAL_RESULTS)
    source_queue = {
        "items": [
            {"query_id": "gq_auto_010"},
            {"query_id": "text_namu_v2_0012"},
            {"query_id": "gq_xlsx_lookup_008"},
        ]
    }
    units_by_query_id, diagnostics_by_query_id = runner.build_v3_1_6_pdf_window_expansion_units(
        v3_1_4_rows=v3_1_4_rows,
        remaining_queue=source_queue,
        generated_at="2026-05-18T00:00:00+00:00",
    )
    assert set(units_by_query_id) == {"gq_auto_010"}
    assert set(diagnostics_by_query_id) == {"gq_auto_010"}

    target_row = next(row for row in v3_1_4_rows if row["query_id"] == "gq_auto_010")
    context = runner.build_v3_prompt_context_from_row(
        target_row,
        use_query_bound_only=True,
        mode="query_bound_only_source_bound",
        context_expansion_units=units_by_query_id["gq_auto_010"],
    )
    assert context["prompt_context_source_bound_only"] is True
    assert context["prompt_context_policy"]["diagnostic_context_expansion_allowed"] is True
    assert context["prompt_context_policy"]["diagnostic_context_expansion_count"] == 1
    assert context["prompt_context_policy"]["candidate_artifacts_as_generation_source"] is False
    assert context["prompt_context_policy"]["generation_used_expected_answer"] is False
    assert context["prompt_context_policy"]["generation_used_supporting_evidence"] is False
    assert context["prompt_context_policy"]["generation_used_gold_fields"] is False
    expansion_citations = [citation for citation in context["citations"] if citation.get("context_expansion")]
    assert len(expansion_citations) == 1
    assert expansion_citations[0]["search_unit_id"] == "pdfwin_b1c6527f848018640ad5ed231877c662"
    assert expansion_citations[0]["query_bound"] is True


def test_v3_1_artifact_consistency_preflight_fails_closed_on_stale_summary() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    guardrails = runner.v3_1_guardrails()
    summary = {
        **guardrails,
        "guardrails": guardrails,
        "run_id": "stale-run",
        "status": "ALL_TRACK_FOUNDATION_MEASUREMENT_V3_1_COMPLETED",
        "result_count": 29,
        "diagnostic_only": True,
        "lane_names": list(runner.V3_1_LANE_NAMES),
    }
    rows = [{"query_id": query_id} for query_id in AGENTIC_V3_1_PRIORITY_QUERY_IDS]
    rows.extend({"query_id": f"extra_{idx:02d}"} for idx in range(24))
    triage = {
        "run_id": runner.V3_1_RUN_ID,
        "items": [
            {"priority_rank": idx + 1, "query_id": query_id}
            for idx, query_id in enumerate(AGENTIC_V3_1_PRIORITY_QUERY_IDS)
        ],
    }

    result = runner.v3_1_artifact_consistency_preflight(
        summary=summary,
        rows=rows,
        triage=triage,
        expected_priority_query_ids=AGENTIC_V3_1_PRIORITY_QUERY_IDS,
    )

    assert result["ok"] is False
    assert "v3_1_summary_run_id_mismatch" in result["errors"]
    assert "v3_1_row_run_id_mismatch" in result["errors"]
    assert "v3_1_row_lane_results_mismatch" in result["errors"]


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


def resolve_report_artifact_path(path: Path) -> Path:
    if path.exists():
        return path
    if path.parent == REPORT_ARCHIVE_DIR:
        archived_external = EXTERNAL_REPORT_ARCHIVE_DIR / path.name
        return archived_external if archived_external.exists() else path
    if path.parent == REPORT_DIR:
        archived_external = EXTERNAL_REPORT_ARCHIVE_DIR / path.name
        if archived_external.exists():
            return archived_external
        archived = REPORT_ARCHIVE_DIR / path.name
        if archived.exists():
            return archived
    return path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(resolve_report_artifact_path(path).read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in resolve_report_artifact_path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def assert_no_gold_generation_source_fields(value: Any) -> None:
    forbidden_keys = {"expected_answer", "supporting_evidence", "human_label"}
    if isinstance(value, dict):
        assert not forbidden_keys.intersection(value)
        for item in value.values():
            assert_no_gold_generation_source_fields(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_gold_generation_source_fields(item)


def assert_generation_guardrail_flags_false(value: Any) -> None:
    false_keys = {
        "promotion_evidence",
        "promotion_gate_auto_run",
        "threshold_tuning",
        "winner_selection",
        "candidate_artifacts_as_generation_source",
        "generation_used_expected_answer",
        "generation_used_supporting_evidence",
        "generation_used_gold_fields",
    }
    if isinstance(value, dict):
        for key in false_keys:
            if key in value:
                assert value[key] is False, key
        if "diagnostic_only" in value:
            assert value["diagnostic_only"] is True
        for item in value.values():
            assert_generation_guardrail_flags_false(item)
    elif isinstance(value, list):
        for item in value:
            assert_generation_guardrail_flags_false(item)


def official_file_identity(path: Path) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_metric_first_run_v1 as official

    return official.file_identity(resolve_report_artifact_path(path))


def numeric_bbox(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    try:
        return all(isinstance(float(item), float) for item in value)
    except (TypeError, ValueError):
        return False
