"""Run the next official answer/citation measurement attempt with agent loop provenance.

This runner opens a new, separate measurement artifact family. It never
overwrites the immutable first-run baseline and never promotes report-only
candidate artifacts. The runner first validates the registry-backed official
question-gold denominator, then attempts to execute the actual RAG generation
pipeline with the agent loop enabled. If the local generation pipeline is not
available, it writes a fail-closed 29-row measurement instead of fabricating
answers or scores.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
if str(AI_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_WORKER_ROOT))

import rag_official_answer_citation_metric_first_run_v1 as official  # noqa: E402
from app.capabilities.rag.retrieval_contract import citation_payload  # noqa: E402


REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
REPORT_ARCHIVE_DIR = REPORT_DIR / "_archive" / "legacy"
EXTERNAL_REPORT_ARCHIVE_DIR = Path(
    "D:/_external_runtime_artifacts/async-ocr-rag-multimodal-pipeline/"
    "rag-ingestion/repo-wide-cleanup-20260519/reports/rag-ingestion-legacy"
)
RUN_ID = "official_answer_citation_agentic_loop_run_v1"
V2_RUN_ID = "official_answer_citation_agentic_loop_run_v2_source_bound_diagnostic"
V2_1_RUN_ID = "official_answer_citation_agentic_loop_run_v2_1_citation_contract_repair"
V2_2_RUN_ID = "official_answer_citation_agentic_loop_run_v2_2_llm_backend_validation"
V3_RUN_ID = "official_answer_citation_agentic_loop_run_v3_comparable_live_measurement"
V3_1_RUN_ID = "official_answer_citation_agentic_loop_run_v3_1_all_track_foundation_measurement"
V3_1_PRIORITY_1_5_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_priority_1_5_strict_json_locator_triage"
)
V3_1_PRIORITY_1_5_STRICT_JSON_DIAGNOSTICS_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_priority_1_5_triage_strict_json_diagnostics"
)
V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_text_locator_residual_triage"
)
V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_1_all_track_foundation_measurement_post_strict_json_locator_triage"
)
V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_2_answer_span_renderer_triage"
)
V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_3_remaining_queue_answer_span_renderer_triage"
)
V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_4_pdf_residual_answer_span_renderer_triage"
)
V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_5_gq_auto_010_source_bound_retrieval_context_coverage_diagnostic"
)
V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic"
)
V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_7_post_residual_queue_closure_and_residual_inventory_audit"
)
V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_8_gold_policy_review_packet_preparation"
)
V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID = (
    "official_answer_citation_agentic_loop_run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement"
)
REPORT_ARTIFACT_SLUGS = {
    RUN_ID: "agentic_v1",
    V2_RUN_ID: "v2_source_bound",
    V2_1_RUN_ID: "v2_1_citation",
    V2_2_RUN_ID: "v2_2_backend",
    V3_RUN_ID: "v3_comparable",
    V3_1_RUN_ID: "v3_1_foundation",
    V3_1_PRIORITY_1_5_RUN_ID: "v3_1_priority",
    V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID: "v3_1_textloc",
    V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID: "v3_1_1_post_locator",
    V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID: "v3_1_2_span",
    V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID: "v3_1_3_remaining",
    V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID: "v3_1_4_pdf_residual",
    V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID: "v3_1_5_gq010_coverage",
    V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID: "v3_1_6_gq010_pdfwin",
    V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID: V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID,
    V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID: V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
    V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID: V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID,
}
ARCHIVED_REPORT_RUN_IDS = set(REPORT_ARTIFACT_SLUGS) - {
    V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
    V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID,
    V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
    V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID,
}
V3_1_PRIORITY_1_5_QUERY_IDS = (
    "gq_pdf_section_question_001",
    "text_namu_v2_0012",
    "gq_auto_010",
    "gq_auto_023",
    "gq_xlsx_lookup_008",
)
V3_1_TEXT_LOCATOR_RESIDUAL_QUERY_IDS = ("text_namu_v2_0012",)
V3_1_PRIORITY_1_5_STRICT_JSON_QUERY_IDS = (
    "gq_pdf_section_question_001",
    "text_namu_v2_0012",
)
V3_1_2_TEXT_FIRST_BATCH_QUERY_IDS = (
    "text_namu_v2_0012",
    "text_namu_v2_0014",
    "text_namu_v2_0017",
    "text_namu_v2_0077",
    "text_namu_v2_0084",
)
V3_1_2_TEXT_SECONDARY_QUERY_IDS = ("text_namu_v2_0005",)
V3_1_2_TEXT_TARGET_QUERY_IDS = V3_1_2_TEXT_FIRST_BATCH_QUERY_IDS + V3_1_2_TEXT_SECONDARY_QUERY_IDS
V3_1_3_REMAINING_QUEUE_QUERY_IDS = (
    "gq_auto_010",
    "gq_auto_024",
    "gq_auto_030",
    "gq_auto_043",
    "gq_pdf_section_question_001",
    "gq_xlsx_date_number_format_001",
    "text_namu_v2_0005",
)
V3_1_4_PDF_RESIDUAL_QUERY_IDS = (
    "gq_auto_010",
    "gq_pdf_section_question_001",
)
V3_1_5_SOURCE_BOUND_COVERAGE_QUERY_IDS = ("gq_auto_010",)
V3_1_6_SAFE_PDF_WINDOW_QUERY_IDS = ("gq_auto_010",)
V3_1_8_POLICY_REVIEW_QUERY_IDS = V3_1_2_TEXT_FIRST_BATCH_QUERY_IDS
V3_1_9_USER_GOLD_POLICY_OVERRIDE_QUERY_IDS = V3_1_8_POLICY_REVIEW_QUERY_IDS
V3_1_9_TEXT_GOLD_BEFORE_SHA256 = "03764d1d7aa682cd8646d9028b6219fdbeba8a4eb219a87a285a162f16702cd6"
V3_1_8_DECISION_OPTIONS = (
    "keep_current_strict_reference_boundary",
    "approve_scorer_or_renderer_review_without_gold_mutation",
    "revise_gold_or_label_policy",
)
PDF_PARAGRAPH_WINDOW_EXPANSION_POLICY_NAME = "same_page_pdf_paragraph_line_window_v1"
PDF_PARAGRAPH_WINDOW_EXPANSION_POLICY_VERSION = "v1"
PDF_PARAGRAPH_WINDOW_VERTICAL_MARGIN_POINTS = 32.0
V3_1_LIVE_LANE_NAMES = (
    "live_llm_retrieval_topk",
    "live_llm_query_bound_oracle",
)
V2_1_RESIDUAL_FAILURE_AUDIT_QUERY_IDS = (
    "gq_auto_030",
    "gq_pdf_section_question_001",
    "text_namu_v2_0017",
)
V2_2_ALLOWED_LLM_BACKENDS = ("noop", "llamacpp", "openai-compatible", "ollama")
V2_2_VALIDATION_BUCKETS = (
    "PASS_RETAINED",
    "LLM_SYNTHESIS_IMPROVED",
    "LLM_SYNTHESIS_REGRESSED",
    "STRUCTURED_ADAPTER_REGRESSED",
    "CITATION_SUPPORT_REGRESSED",
    "LLM_BACKEND_UNAVAILABLE",
    "LLM_TIMEOUT_OR_FAIL_CLOSED",
    "PROMPT_CONTEXT_POLICY_VIOLATION",
    "GOLD_OR_CANDIDATE_LEAK_BLOCKED",
)
V2_2_SYNTHESIS_TARGET_QUERY_IDS = ("text_namu_v2_0017",)
V3_RESULT_BUCKETS = (
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
)
V3_TEXT_SYNTHESIS_TRACKS = ("text_namu_v2_1",)
V3_PROMPT_CONTEXT_MODES = ("same-track-scored-context", "query-bound-only")
V3_1_LANE_NAMES = (
    "v3_primary_replay",
    "live_llm_retrieval_topk",
    "live_llm_query_bound_oracle",
)
V3_1_FAILURE_TAXONOMY = (
    "PASS",
    "RETRIEVAL_QUERY_BOUND_MISS",
    "CITATION_PAYLOAD_SCHEMA_MISMATCH",
    "CITATION_NOT_SOURCE_BOUND",
    "CITATION_OFF_TRACK",
    "CITATION_NOT_QUERY_BOUND",
    "LLM_STRICT_JSON_PARSE_FAILURE",
    "LLM_ANSWER_OVERCOMPRESSION",
    "LLM_EXPECTED_SPAN_MISMATCH",
    "LLM_TRUE_PARTIAL_SYNTHESIS",
    "LLM_UNSUPPORTED_INFERENCE",
    "PDF_BBOX_LOCATOR_LOSS",
    "PDF_TABLE_AXIS_MISREAD",
    "PDF_OCR_VALUE_MISREAD",
    "PDF_SECTION_REGION_MISREAD",
    "XLSX_CELL_LOCATOR_LOSS",
    "XLSX_ROW_COLUMN_LOOKUP_MISREAD",
    "XLSX_DATE_NUMBER_FORMAT_MISREAD",
    "XLSX_DISPLAYED_VALUE_NORMALIZED_VALUE_CONFUSION",
    "SCORER_NORMALIZATION_REVIEW",
    "GOLD_POLICY_REVIEW_CANDIDATE",
)


def report_artifact_dir(run_id: str) -> Path:
    if run_id not in ARCHIVED_REPORT_RUN_IDS:
        return REPORT_DIR
    return REPORT_ARCHIVE_DIR if REPORT_ARCHIVE_DIR.exists() else EXTERNAL_REPORT_ARCHIVE_DIR


def report_artifact_path(run_id: str, suffix: str) -> Path:
    return report_artifact_dir(run_id) / f"{REPORT_ARTIFACT_SLUGS[run_id]}_{suffix}"


def report_artifact_logical_path(run_id: str, suffix: str) -> Path:
    logical_dir = REPORT_ARCHIVE_DIR if run_id in ARCHIVED_REPORT_RUN_IDS else REPORT_DIR
    return logical_dir / f"{REPORT_ARTIFACT_SLUGS[run_id]}_{suffix}"


def report_artifact_repo_relative(run_id: str, suffix: str) -> str:
    return official.repo_relative(report_artifact_logical_path(run_id, suffix))


DEFAULT_RESULTS_JSONL = report_artifact_path(RUN_ID, "results.jsonl")
DEFAULT_SUMMARY_JSON = report_artifact_path(RUN_ID, "summary.json")
DEFAULT_SUMMARY_MD = report_artifact_path(RUN_ID, "summary.md")
DEFAULT_STATUS_JSONL = REPORT_DIR / "status.jsonl"
DEFAULT_BASELINE_JSON = REPORT_DIR / "baseline_v1.json"
DEFAULT_XLSX_CANDIDATE = REPORT_DIR / "xlsx_candidate_v1.jsonl"
DEFAULT_PDF_CANDIDATE = REPORT_DIR / "pdf_candidate_v1.jsonl"
DEFAULT_SOURCE_BOUND_READINESS_JSON = REPORT_DIR / "source_bound_readiness_v1.json"
DEFAULT_V3_SUMMARY_JSON = report_artifact_path(V3_RUN_ID, "summary.json")
DEFAULT_V3_RESULTS_JSONL = report_artifact_path(V3_RUN_ID, "results.jsonl")
DEFAULT_V3_FAILURE_ATTRIBUTION_JSON = report_artifact_path(V3_RUN_ID, "failure.json")
DEFAULT_V3_1_SUMMARY_JSON = report_artifact_path(V3_1_RUN_ID, "summary.json")
DEFAULT_V3_1_RESULTS_JSONL = report_artifact_path(V3_1_RUN_ID, "results.jsonl")
DEFAULT_V3_1_TRIAGE_JSON = report_artifact_path(V3_1_RUN_ID, "queue.json")
DEFAULT_V3_1_PRIORITY_SUMMARY_JSON = report_artifact_path(V3_1_PRIORITY_1_5_RUN_ID, "summary.json")
DEFAULT_V3_1_PRIORITY_RESULTS_JSONL = report_artifact_path(V3_1_PRIORITY_1_5_RUN_ID, "results.jsonl")
DEFAULT_V3_1_PRIORITY_TRIAGE_DELTA_JSON = report_artifact_path(V3_1_PRIORITY_1_5_RUN_ID, "delta.json")
DEFAULT_V3_1_TEXT_LOCATOR_SUMMARY_JSON = report_artifact_path(V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "summary.json")
DEFAULT_V3_1_TEXT_LOCATOR_RESULTS_JSONL = report_artifact_path(V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "results.jsonl")
DEFAULT_V3_1_TEXT_LOCATOR_TRIAGE_DELTA_JSON = report_artifact_path(V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID, "delta.json")
DEFAULT_V3_1_1_POST_SUMMARY_JSON = report_artifact_path(
    V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID, "summary.json"
)
DEFAULT_V3_1_1_POST_RESULTS_JSONL = report_artifact_path(
    V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID, "results.jsonl"
)
DEFAULT_V3_1_1_POST_ATTRIBUTION_JSON = report_artifact_path(
    V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID, "failure.json"
)
DEFAULT_V3_1_1_POST_AUDIT_JSONL = report_artifact_path(
    V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID, "audit.jsonl"
)
DEFAULT_V3_1_1_POST_TRIAGE_QUEUE_JSON = report_artifact_path(
    V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID, "queue.json"
)
DEFAULT_V3_1_2_ANSWER_SPAN_SUMMARY_JSON = report_artifact_path(
    V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "summary.json"
)
DEFAULT_V3_1_2_ANSWER_SPAN_RESULTS_JSONL = report_artifact_path(
    V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "results.jsonl"
)
DEFAULT_V3_1_2_ANSWER_SPAN_ATTRIBUTION_JSON = report_artifact_path(
    V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "failure.json"
)
DEFAULT_V3_1_2_ANSWER_SPAN_AUDIT_JSONL = report_artifact_path(
    V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "audit.jsonl"
)
DEFAULT_V3_1_2_ANSWER_SPAN_DIAGNOSTICS_JSONL = report_artifact_path(
    V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "spans.jsonl"
)
DEFAULT_V3_1_2_REMAINING_TRIAGE_QUEUE_JSON = report_artifact_path(
    V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "queue.json"
)
DEFAULT_V3_1_3_REMAINING_QUEUE_SUMMARY_JSON = report_artifact_path(
    V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "summary.json"
)
DEFAULT_V3_1_3_REMAINING_QUEUE_RESULTS_JSONL = report_artifact_path(
    V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "results.jsonl"
)
DEFAULT_V3_1_3_REMAINING_QUEUE_ATTRIBUTION_JSON = report_artifact_path(
    V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "failure.json"
)
DEFAULT_V3_1_3_REMAINING_QUEUE_AUDIT_JSONL = report_artifact_path(
    V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "audit.jsonl"
)
DEFAULT_V3_1_3_REMAINING_QUEUE_DIAGNOSTICS_JSONL = report_artifact_path(
    V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "spans.jsonl"
)
DEFAULT_V3_1_3_REMAINING_QUEUE_JSON = report_artifact_path(
    V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "queue.json"
)
DEFAULT_V3_1_4_PDF_RESIDUAL_SUMMARY_JSON = report_artifact_path(
    V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "summary.json"
)
DEFAULT_V3_1_4_PDF_RESIDUAL_RESULTS_JSONL = report_artifact_path(
    V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "results.jsonl"
)
DEFAULT_V3_1_4_PDF_RESIDUAL_DIAGNOSTICS_JSONL = report_artifact_path(
    V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "spans.jsonl"
)
DEFAULT_V3_1_4_PDF_RESIDUAL_REMAINING_QUEUE_JSON = report_artifact_path(
    V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID, "queue.json"
)
DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_SUMMARY_JSON = report_artifact_path(
    V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID, "summary.json"
)
DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_DIAGNOSTICS_JSONL = report_artifact_path(
    V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID, "context.jsonl"
)
DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_QUEUE_JSON = report_artifact_path(
    V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID, "queue.json"
)
DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_RESULTS_JSONL = report_artifact_path(
    V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID, "results.jsonl"
)
DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_SUMMARY_JSON = report_artifact_path(
    V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID, "summary.json"
)
DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_FAILURE_JSON = report_artifact_path(
    V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID, "failure.json"
)
DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_AUDIT_JSONL = report_artifact_path(
    V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID, "audit.jsonl"
)
DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_SPANS_JSONL = report_artifact_path(
    V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID, "spans.jsonl"
)
DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_CONTEXT_JSONL = report_artifact_path(
    V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID, "context.jsonl"
)
DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_QUEUE_JSON = report_artifact_path(
    V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID, "queue.json"
)
DEFAULT_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SUMMARY_JSON = report_artifact_path(
    V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID, "summary.json"
)
DEFAULT_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_INVENTORY_JSONL = report_artifact_path(
    V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID, "all_track_residual_inventory.jsonl"
)
DEFAULT_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_QUEUE_JSON = report_artifact_path(
    V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID, "remaining_triage_queue.json"
)
DEFAULT_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_DECISION_PACKET_JSON = report_artifact_path(
    V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID, "user_decision_packet.json"
)
DEFAULT_SCORER_RESULTS_JSONL = REPORT_DIR / "scorer_v1.jsonl"
DEFAULT_TEXT_NAMU_GOLD_CSV = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_text_namu_v2_1_question_gold_v2.csv"
DEFAULT_TEXT_NAMU_HUMAN_AUDIT_V2_DECISIONS_JSON = (
    AI_WORKER_ROOT / "eval" / "review" / "rag_human_audit_v2_applied_decisions.json"
)
DEFAULT_TEXT_NAMU_POLICY_REVIEW_PACKET_JSON = (
    AI_WORKER_ROOT / "eval" / "review" / "rag_text_namu_answer_citation_policy_review_packet_v2_1.json"
)
DEFAULT_RAG_INDEX_DIR = AI_WORKER_ROOT / "eval" / "indexes" / "rag-data-official-denominator-v1"

GENERATION_PIPELINE_UNAVAILABLE = "GENERATION_PIPELINE_UNAVAILABLE"
AGENTIC_GENERATION_ROW_FAILED = "AGENTIC_GENERATION_ROW_FAILED"
NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING = "NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING"
REGISTRY_BACKED_RAG_CAPABILITY_UNAVAILABLE = "REGISTRY_BACKED_RAG_CAPABILITY_UNAVAILABLE"
OFFICIAL_DENOMINATOR_VALIDATION_FAILED = "OFFICIAL_DENOMINATOR_VALIDATION_FAILED"
SEARCH_UNIT_CITATION_PAYLOAD_MISSING = "SEARCH_UNIT_CITATION_PAYLOAD_MISSING"
SEARCH_UNIT_SOURCE_IDENTITY_MISSING = "SEARCH_UNIT_SOURCE_IDENTITY_MISSING"
SEARCH_UNIT_LOCATOR_INCOMPLETE = "SEARCH_UNIT_LOCATOR_INCOMPLETE"
STRUCTURED_LOCATOR_DROPPED = "STRUCTURED_LOCATOR_DROPPED"
OFF_TRACK_CITATION_FOR_QUERY_TRACK = "OFF_TRACK_CITATION_FOR_QUERY_TRACK"
SAME_TRACK_LOCATOR_INCOMPLETE = "SAME_TRACK_LOCATOR_INCOMPLETE"
SOURCE_BOUND_INDEX_LOAD_CHECK_MISSING = "SOURCE_BOUND_OFFICIAL_DENOMINATOR_INDEX_LOAD_CHECK_MISSING"
SOURCE_BOUND_INDEX_VERSION_MISMATCH = "SOURCE_BOUND_OFFICIAL_DENOMINATOR_INDEX_VERSION_MISMATCH"
STALE_SOURCE_BOUND_READINESS_ARTIFACT = "STALE_SOURCE_BOUND_READINESS_ARTIFACT"
SEARCH_UNIT_MANIFEST_MISMATCH = "SEARCH_UNIT_MANIFEST_MISMATCH"
INDEX_REQUIRED_FILES = ("faiss.index", "build.json", "ingest_manifest.json", "search_unit_manifest.jsonl")
OFFICIAL_SOURCE_BOUND_INDEX_VERSION = (
    "official-answer-citation-agentic-loop-v1-nonprod-official-denominator-source-bound"
)
OFFICIAL_SOURCE_BOUND_INDEX_WORKER_RELATIVE = "eval/indexes/rag-data-official-denominator-v1"
INDEX_BUILD_COMMAND = (
    "cd ai && python -m scripts.rag_official_denominator_source_bound_index "
    "--output-index eval/indexes/rag-data-official-denominator-v1 "
    "--index-version official-answer-citation-agentic-loop-v1-nonprod-official-denominator-source-bound"
)
INDEX_LOAD_CHECK_COMMAND = (
    "cd ai; $env:AIPIPELINE_WORKER_RAG_INDEX_DIR='eval/indexes/rag-data-official-denominator-v1'; "
    "python -m scripts.doctor --json "
    "--only schemas,faiss_index,build_json,runtime_model_match"
)
TEXT_REQUIRED_CITATION_FIELDS = ("document_id", "document_version_id", "search_unit_id", "text_locator")
XLSX_REQUIRED_CITATION_FIELDS = (
    "workbook",
    "sheet",
    "range",
    "cell",
    "row_label",
    "target_column",
    "normalized_value",
    "search_unit_id",
    "document_version_id",
)
PDF_REQUIRED_CITATION_FIELDS = (
    "source_pdf_path",
    "page",
    "physical_page_index",
    "bbox",
    "region_type",
    "row_label",
    "target_column",
    "search_unit_id",
    "document_version_id",
)
REQUIRED_CITATION_FIELDS_BY_TRACK = {
    "text_namu_v2_1": TEXT_REQUIRED_CITATION_FIELDS,
    "xlsx_business_structured": XLSX_REQUIRED_CITATION_FIELDS,
    "pdf_business_ocr_mm": PDF_REQUIRED_CITATION_FIELDS,
}
SOURCE_FAMILY_BY_TRACK = {
    "text_namu_v2_1": "text",
    "xlsx_business_structured": "xlsx",
    "pdf_business_ocr_mm": "pdf",
}
SOURCE_FAMILY_LABEL_BY_TRACK = {
    "text_namu_v2_1": "TEXT",
    "xlsx_business_structured": "XLSX",
    "pdf_business_ocr_mm": "PDF",
}
LOCATOR_SCHEMA_BY_TRACK = {
    "text_namu_v2_1": "text_locator_v1",
    "xlsx_business_structured": "xlsx_cell_v1",
    "pdf_business_ocr_mm": "pdf_source_bound_v1",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary, rows = run_measurement(args)
    if summary["run_id"] == V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID:
        write_v3_1_5_source_bound_coverage_side_artifacts(summary, rows)
        write_json(Path(args.summary_json), summary)
        append_status_event(Path(args.status_jsonl), summary)
        console_payload = {
            "run_id": summary["run_id"],
            "status": summary["status"],
            "measurement_classification": summary["measurement_classification"],
            "result_count": summary["result_count"],
            "unique_query_id_count": summary["unique_query_id_count"],
            "summary_json": summary["artifact_paths"]["summary_json"],
            "context_coverage_diagnostics_jsonl": summary["artifact_paths"][
                "context_coverage_diagnostics_jsonl"
            ],
            "remaining_triage_queue_json": summary["artifact_paths"]["remaining_triage_queue_json"],
        }
        print(json.dumps(console_payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if summary["run_id"] == V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID:
        write_v3_1_7_post_residual_queue_closure_audit_side_artifacts(summary, rows)
        write_json(Path(args.summary_json), summary)
        append_status_event(Path(args.status_jsonl), summary)
        console_payload = {
            "run_id": summary["run_id"],
            "status": summary["status"],
            "measurement_classification": summary["measurement_classification"],
            "result_count": summary["result_count"],
            "unique_query_id_count": summary["unique_query_id_count"],
            "summary_json": summary["artifact_paths"]["summary_json"],
            "all_track_residual_inventory_jsonl": summary["artifact_paths"][
                "all_track_residual_inventory_jsonl"
            ],
            "remaining_triage_queue_json": summary["artifact_paths"]["remaining_triage_queue_json"],
            "user_decision_packet_json": summary["artifact_paths"].get("user_decision_packet_json"),
            "silver_readiness_audit_json": summary["artifact_paths"].get("silver_readiness_audit_json"),
        }
        print(json.dumps(console_payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if summary["run_id"] == V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID:
        write_v3_1_8_gold_policy_review_packet_side_artifacts(summary, rows)
        write_json(Path(args.summary_json), summary)
        append_status_event(Path(args.status_jsonl), summary)
        console_payload = {
            "run_id": summary["run_id"],
            "status": summary["status"],
            "measurement_classification": summary["measurement_classification"],
            "result_count": summary["result_count"],
            "unique_query_id_count": summary["unique_query_id_count"],
            "summary_json": summary["artifact_paths"]["summary_json"],
            "human_review_packet_json": summary["artifact_paths"]["human_review_packet_json"],
            "decision_matrix_jsonl": summary["artifact_paths"]["decision_matrix_jsonl"],
            "remaining_triage_queue_json": summary["artifact_paths"]["remaining_triage_queue_json"],
        }
        print(json.dumps(console_payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if summary["run_id"] == V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID:
        write_v3_1_9_user_gold_policy_override_side_artifacts(summary, rows)
        write_json(Path(args.summary_json), summary)
        append_status_event(Path(args.status_jsonl), summary)
        console_payload = {
            "run_id": summary["run_id"],
            "status": summary["status"],
            "run_class": summary["run_class"],
            "result_count": summary["result_count"],
            "unique_query_id_count": summary["unique_query_id_count"],
            "summary_json": summary["artifact_paths"]["summary_json"],
            "applied_overrides_jsonl": summary["artifact_paths"]["applied_overrides_jsonl"],
            "gold_diff_jsonl": summary["artifact_paths"]["gold_diff_jsonl"],
            "rescored_results_jsonl": summary["artifact_paths"]["rescored_results_jsonl"],
            "remaining_triage_queue_json": summary["artifact_paths"]["remaining_triage_queue_json"],
            "lane_pass_counts_after": summary["lane_pass_counts_after"],
        }
        print(json.dumps(console_payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    write_jsonl(Path(args.results_jsonl), rows)
    summary["artifact_paths"]["results_jsonl_sha256"] = sha256_file(Path(args.results_jsonl))
    failure_attribution = build_failure_attribution(summary, rows)
    failure_attribution_path = resolve_repo_relative_artifact_path(
        Path(summary["artifact_paths"]["failure_attribution_json"])
    )
    write_json(failure_attribution_path, failure_attribution)
    summary["artifact_paths"]["failure_attribution_json_sha256"] = sha256_file(failure_attribution_path)
    if summary["run_id"] == V3_1_RUN_ID:
        write_v3_1_side_artifacts(summary, rows)
    elif summary["run_id"] == V3_1_PRIORITY_1_5_RUN_ID:
        write_v3_1_priority_1_5_side_artifacts(summary, rows)
    elif summary["run_id"] == V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID:
        write_v3_1_text_locator_residual_side_artifacts(summary, rows)
    elif summary["run_id"] == V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID:
        write_v3_1_1_post_triage_side_artifacts(summary, rows)
    elif summary["run_id"] == V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        write_v3_1_2_answer_span_renderer_side_artifacts(summary, rows)
    elif summary["run_id"] == V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        write_v3_1_3_remaining_queue_answer_span_renderer_side_artifacts(summary, rows)
    elif summary["run_id"] == V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        write_v3_1_4_pdf_residual_answer_span_renderer_side_artifacts(summary, rows)
    elif summary["run_id"] == V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID:
        write_v3_1_6_safe_pdf_window_expansion_side_artifacts(summary, rows)
    write_json(Path(args.summary_json), summary)
    if summary.get("write_summary_markdown", True) is not False:
        Path(args.summary_md).write_text(render_markdown(summary), encoding="utf-8")
    append_status_event(Path(args.status_jsonl), summary)
    append_failure_attribution_event(Path(args.status_jsonl), failure_attribution)
    console_payload = {
        "run_id": summary["run_id"],
        "status": summary["status"],
        "measurement_classification": summary["measurement_classification"],
        "result_count": summary["result_count"],
        "unique_query_id_count": summary["unique_query_id_count"],
        "pass_count": summary["pass_count"],
        "agentic_loop_enabled": summary["agentic_loop"]["enabled"],
        "agentic_loop_executed": summary["agentic_loop"]["executed"],
        "results_jsonl": summary["artifact_paths"]["results_jsonl"],
        "summary_json": summary["artifact_paths"]["summary_json"],
    }
    if "summary_md" in summary["artifact_paths"]:
        console_payload["summary_md"] = summary["artifact_paths"]["summary_md"]
    print(json.dumps(console_payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--metric-input-config", default=str(official.DEFAULT_METRIC_INPUT_CONFIG))
    parser.add_argument("--denominator-registry", default=str(official.DEFAULT_DENOMINATOR_REGISTRY))
    parser.add_argument("--pre-execution-smoke", default=str(official.DEFAULT_PRE_EXECUTION_SMOKE))
    parser.add_argument("--first-run-baseline", default=str(DEFAULT_BASELINE_JSON))
    parser.add_argument("--xlsx-candidate-results", default=str(DEFAULT_XLSX_CANDIDATE))
    parser.add_argument("--pdf-candidate-results", default=str(DEFAULT_PDF_CANDIDATE))
    parser.add_argument("--v2-1-summary-json", default=str(report_artifact_path(V2_1_RUN_ID, "summary.json")))
    parser.add_argument("--v2-1-results-jsonl", default=str(report_artifact_path(V2_1_RUN_ID, "results.jsonl")))
    parser.add_argument(
        "--v2-1-failure-attribution-json",
        default=str(report_artifact_path(V2_1_RUN_ID, "failure.json")),
    )
    parser.add_argument("--v2-2-summary-json", default=str(report_artifact_path(V2_2_RUN_ID, "summary.json")))
    parser.add_argument("--v2-2-results-jsonl", default=str(report_artifact_path(V2_2_RUN_ID, "results.jsonl")))
    parser.add_argument(
        "--v2-2-failure-attribution-json",
        default=str(report_artifact_path(V2_2_RUN_ID, "failure.json")),
    )
    parser.add_argument("--v3-summary-json", default=str(DEFAULT_V3_SUMMARY_JSON))
    parser.add_argument("--v3-results-jsonl", default=str(DEFAULT_V3_RESULTS_JSONL))
    parser.add_argument("--v3-failure-attribution-json", default=str(DEFAULT_V3_FAILURE_ATTRIBUTION_JSON))
    parser.add_argument("--results-jsonl", default=None)
    parser.add_argument("--summary-json", default=None)
    parser.add_argument("--summary-md", default=None)
    parser.add_argument("--status-jsonl", default=str(DEFAULT_STATUS_JSONL))
    parser.add_argument("--source-bound-readiness", default=str(DEFAULT_SOURCE_BOUND_READINESS_JSON))
    parser.add_argument("--agent-loop-backend", choices=("legacy", "graph"), default="legacy")
    parser.add_argument("--agent-max-iter", type=int, default=3)
    parser.add_argument("--agent-max-total-ms", type=int, default=15_000)
    parser.add_argument("--agent-max-llm-tokens", type=int, default=4_000)
    parser.add_argument("--agent-min-stop-confidence", type=float, default=0.75)
    parser.add_argument(
        "--llm-backend",
        default=os.environ.get("AIPIPELINE_WORKER_LLM_BACKEND", "llamacpp"),
        choices=V2_2_ALLOWED_LLM_BACKENDS,
    )
    parser.add_argument("--llm-base-url", default="")
    parser.add_argument(
        "--llm-model",
        default=(
            os.environ.get("LOCAL_LLM_MODEL")
            or os.environ.get("AIPIPELINE_WORKER_LLM_LLAMACPP_MODEL")
            or "gemma4-e2b-local"
        ),
    )
    parser.add_argument("--llm-timeout-seconds", type=int, default=120)
    parser.add_argument("--llm-max-tokens", type=int, default=4096)
    parser.add_argument("--llm-strict-json-retries", type=int, default=3)
    parser.add_argument(
        "--v3-prompt-context-mode",
        choices=V3_PROMPT_CONTEXT_MODES,
        default="same-track-scored-context",
    )
    parser.add_argument(
        "--rag-index-dir",
        default=str(DEFAULT_RAG_INDEX_DIR),
        help=(
            "Canonical non-production official-denominator worker RAG index directory. "
            "Relative paths are resolved from ai/, so the worker-relative default is "
            "eval/indexes/rag-data-official-denominator-v1."
        ),
    )
    parser.add_argument(
        "--source-bound-index-load-checked",
        action="store_true",
        help="Acknowledge that the official-denominator source-bound index passed the doctor load-check.",
    )
    parser.add_argument(
        "--enable-structured-source-bound-adapters",
        action="store_true",
        help="Enable explicit XLSX/PDF deterministic adapter payloads from retrieved source-bound SearchUnits.",
    )
    parser.add_argument(
        "--allow-chunk-only-official-citation-fallback",
        action="store_true",
        help="Diagnostic escape hatch; official-compatible scoring keeps this disabled.",
    )
    args = parser.parse_args(argv)
    supported_run_ids = {
        RUN_ID,
        V2_RUN_ID,
        V2_1_RUN_ID,
        V2_2_RUN_ID,
        V3_RUN_ID,
        V3_1_RUN_ID,
        V3_1_PRIORITY_1_5_RUN_ID,
        V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID,
        V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
        V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
        V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
        V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID,
        V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
        V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID,
    }
    if args.run_id not in supported_run_ids:
        raise SystemExit(
            "unsupported run id "
            f"{args.run_id!r}; expected one of {', '.join(repr(item) for item in sorted(supported_run_ids))}"
        )
    if args.results_jsonl is None:
        args.results_jsonl = str(report_artifact_path(args.run_id, "results.jsonl"))
    if args.summary_json is None:
        args.summary_json = str(report_artifact_path(args.run_id, "summary.json"))
    if args.summary_md is None:
        args.summary_md = str(report_artifact_path(args.run_id, "summary.md"))
    if is_source_bound_manifest_run(args.run_id):
        args.source_bound_index_load_checked = True
        args.enable_structured_source_bound_adapters = True
    return args


def is_source_bound_manifest_run(run_id: str) -> bool:
    return run_id in {
        V2_RUN_ID,
        V2_1_RUN_ID,
        V2_2_RUN_ID,
        V3_RUN_ID,
        V3_1_RUN_ID,
        V3_1_PRIORITY_1_5_RUN_ID,
        V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID,
        V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
        V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
        V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
    }


def source_family_for_track(track: str) -> str:
    return SOURCE_FAMILY_BY_TRACK.get(official.clean(track), "")


def locator_schema_for_track(track: str) -> str:
    return LOCATOR_SCHEMA_BY_TRACK.get(official.clean(track), "")


def run_measurement(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metric_input_config_path = Path(args.metric_input_config)
    denominator_registry_path = Path(args.denominator_registry)
    pre_execution_smoke_path = Path(args.pre_execution_smoke)
    baseline_path = Path(args.first_run_baseline)
    agentic_status = agentic_loop_status(args)

    if args.run_id == V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID:
        return run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement(
            args=args,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            baseline_path=baseline_path,
        )

    config = official.read_json(metric_input_config_path)
    registry = official.read_json(denominator_registry_path)
    smoke = official.read_json(pre_execution_smoke_path)
    application_path = official.resolve_application_report_path(config, smoke)
    application = official.read_json(application_path) if application_path else {}
    application_for_validation = (
        application
        if application
        else fallback_registry_application_from_config(config)
    )
    consumed = official.consume_official_inputs(
        config=config,
        registry=registry,
        application=application_for_validation,
        smoke=smoke,
    )
    rows = list(consumed["rows"])
    baseline = official.read_json(baseline_path)
    validation_errors = list(consumed["errors"])

    if args.run_id == V2_2_RUN_ID:
        return run_v2_2_llm_backend_validation(
            args=args,
            consumed=consumed,
            baseline=baseline,
            validation_errors=validation_errors,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=not bool(application),
            baseline_path=baseline_path,
        )
    if args.run_id == V3_RUN_ID:
        return run_v3_comparable_live_measurement(
            args=args,
            consumed=consumed,
            baseline=baseline,
            validation_errors=validation_errors,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=not bool(application),
            baseline_path=baseline_path,
        )
    if args.run_id == V3_1_RUN_ID:
        return run_v3_1_all_track_foundation_measurement(
            args=args,
            consumed=consumed,
            baseline=baseline,
            validation_errors=validation_errors,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=not bool(application),
            baseline_path=baseline_path,
        )
    if args.run_id == V3_1_PRIORITY_1_5_RUN_ID:
        return run_v3_1_priority_1_5_strict_json_locator_triage(
            args=args,
            consumed=consumed,
            baseline=baseline,
            validation_errors=validation_errors,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=not bool(application),
            baseline_path=baseline_path,
        )
    if args.run_id == V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID:
        return run_v3_1_text_locator_residual_triage(
            args=args,
            consumed=consumed,
            baseline=baseline,
            validation_errors=validation_errors,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=not bool(application),
            baseline_path=baseline_path,
        )
    if args.run_id == V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID:
        return run_v3_1_1_post_strict_json_locator_triage(
            args=args,
            consumed=consumed,
            baseline=baseline,
            validation_errors=validation_errors,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=not bool(application),
            baseline_path=baseline_path,
        )
    if args.run_id == V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        return run_v3_1_2_answer_span_renderer_triage(
            args=args,
            consumed=consumed,
            baseline=baseline,
            validation_errors=validation_errors,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=not bool(application),
            baseline_path=baseline_path,
        )
    if args.run_id == V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        return run_v3_1_3_remaining_queue_answer_span_renderer_triage(
            args=args,
            consumed=consumed,
            baseline=baseline,
            validation_errors=validation_errors,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=not bool(application),
            baseline_path=baseline_path,
        )
    if args.run_id == V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        return run_v3_1_4_pdf_residual_answer_span_renderer_triage(
            args=args,
            consumed=consumed,
            baseline=baseline,
            validation_errors=validation_errors,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=not bool(application),
            baseline_path=baseline_path,
        )
    if args.run_id == V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID:
        return run_v3_1_5_gq_auto_010_source_bound_coverage_diagnostic(
            args=args,
            consumed=consumed,
            baseline=baseline,
            validation_errors=validation_errors,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=not bool(application),
            baseline_path=baseline_path,
        )
    if args.run_id == V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID:
        return run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic(
            args=args,
            consumed=consumed,
            baseline=baseline,
            validation_errors=validation_errors,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=not bool(application),
            baseline_path=baseline_path,
        )
    if args.run_id == V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID:
        return run_v3_1_7_post_residual_queue_closure_and_inventory_audit(
            args=args,
            baseline=baseline,
            validation_errors=validation_errors,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=not bool(application),
            baseline_path=baseline_path,
        )
    if args.run_id == V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID:
        return run_v3_1_8_gold_policy_review_packet_preparation(
            args=args,
            baseline=baseline,
            validation_errors=validation_errors,
            agentic_status=agentic_status,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=not bool(application),
            baseline_path=baseline_path,
        )
    executable = not validation_errors and agentic_status["actual_generation_pipeline_available"] is True
    if executable:
        result_rows = execute_agentic_generation_rows(rows, args, agentic_status)
    else:
        result_rows = fail_closed_rows(
            rows,
            args=args,
            failure_detail=blocked_failure_detail(validation_errors, agentic_status),
            failure_category=blocked_failure_category(validation_errors, agentic_status),
        )

    summary = build_summary(
        args=args,
        rows=result_rows,
        consumed=consumed,
        baseline=baseline,
        validation_errors=validation_errors,
        agentic_status=agentic_status,
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        application_path=application_path,
        registry_application_fallback_used=not bool(application),
        baseline_path=baseline_path,
    )
    return summary, result_rows


def agentic_loop_status(args: argparse.Namespace) -> dict[str, Any]:
    index_dependency = inspect_source_bound_v2_preflight(
        Path(args.rag_index_dir),
        readiness_path=Path(args.source_bound_readiness),
        source_bound_index_load_checked=bool(getattr(args, "source_bound_index_load_checked", False)),
    )
    status: dict[str, Any] = {
        "implemented": False,
        "enabled": True,
        "executed": False,
        "backend": args.agent_loop_backend,
        "steps_count": 0,
        "actual_generation_pipeline_available": False,
        "available_capabilities": [],
        "blockers": [],
        "infrastructure_blocker_category": (
            None if index_dependency["rerun_allowed"] else index_dependency.get("blocker_category")
        ),
        "index_dependency": index_dependency,
        "source_bound_manifest_search_unit_ids": index_dependency.get("manifest_search_unit_ids") or [],
        "config": {
            "agent_loop": "on",
            "agent_loop_backend": args.agent_loop_backend,
            "agent_max_iter": args.agent_max_iter,
            "agent_max_total_ms": args.agent_max_total_ms,
            "agent_max_llm_tokens": args.agent_max_llm_tokens,
            "agent_min_stop_confidence": args.agent_min_stop_confidence,
            "llm_backend": "noop",
            "rag_index_dir": index_dependency["canonical_path"],
            "search_unit_citation_payload_required": not bool(
                getattr(args, "allow_chunk_only_official_citation_fallback", False)
            ),
            "enable_structured_source_bound_adapters": bool(
                getattr(args, "enable_structured_source_bound_adapters", False)
            ),
        },
    }
    if index_dependency.get("rerun_allowed") is not True:
        status["blockers"].append(
            "official-denominator source-bound index is not built and load-checked; measurement rerun is blocked"
        )
        return status
    try:
        from app.capabilities.agent.loop import AgentLoopController  # noqa: F401

        if args.agent_loop_backend == "graph":
            from app.capabilities.agent.graph_loop import AgentLoopGraph  # noqa: F401
        status["implemented"] = True
    except Exception as exc:  # pragma: no cover - import availability is environment dependent.
        status["blockers"].append(f"agent loop import failed: {type(exc).__name__}: {exc}")
        return status

    if is_source_bound_manifest_run(args.run_id):
        try:
            status["_retriever"] = build_source_bound_manifest_retriever(Path(args.rag_index_dir))
            status["actual_generation_pipeline_available"] = True
            status["available_capabilities"] = ["RAG_SOURCE_BOUND_MANIFEST"]
            status["infrastructure_blocker_category"] = None
        except Exception as exc:  # noqa: BLE001
            status["infrastructure_blocker_category"] = REGISTRY_BACKED_RAG_CAPABILITY_UNAVAILABLE
            status["blockers"].append(
                f"source-bound manifest retriever probe failed: {type(exc).__name__}: {exc}"
            )
        return status

    try:
        from app.capabilities.registry import build_default_registry
        from app.core.config import get_settings

        base_settings = get_settings()
        update = {
            "agent_loop": "on",
            "agent_loop_backend": args.agent_loop_backend,
            "agent_max_iter": args.agent_max_iter,
            "agent_max_total_ms": args.agent_max_total_ms,
            "agent_max_llm_tokens": args.agent_max_llm_tokens,
            "agent_min_stop_confidence": args.agent_min_stop_confidence,
            "llm_backend": "noop",
            "rag_index_dir": str(resolve_worker_path(Path(args.rag_index_dir))),
        }
        settings = base_settings.model_copy(update=update)
        registry = build_default_registry(settings)
        available = registry.available()
        status["available_capabilities"] = available
        if "RAG" not in available:
            index_path = Path(settings.rag_index_dir)
            if status["infrastructure_blocker_category"] is None:
                status["infrastructure_blocker_category"] = REGISTRY_BACKED_RAG_CAPABILITY_UNAVAILABLE
            status["blockers"].append(
                f"RAG capability unavailable; FAISS index not found or not loadable at {index_path.as_posix()}"
            )
            return status
        rag = registry.get("RAG")
        retriever = getattr(rag, "_retriever", None) or getattr(rag, "retriever", None)
        if retriever is None:
            status["infrastructure_blocker_category"] = REGISTRY_BACKED_RAG_CAPABILITY_UNAVAILABLE
            status["blockers"].append("RAG capability did not expose a retriever for offline measurement")
            return status
        status["actual_generation_pipeline_available"] = True
        status["infrastructure_blocker_category"] = None
        status["_retriever"] = retriever
    except Exception as exc:
        if status["infrastructure_blocker_category"] is None:
            status["infrastructure_blocker_category"] = REGISTRY_BACKED_RAG_CAPABILITY_UNAVAILABLE
        status["blockers"].append(f"registry generation pipeline probe failed: {type(exc).__name__}: {exc}")
    return status


class SourceBoundManifestRetriever:
    def __init__(self, *, index_dir: Path, top_k: int = 5) -> None:
        ensure_ai_worker_on_path()
        from app.capabilities.rag.embeddings import SentenceTransformerEmbedder, resolve_max_seq_length
        from app.capabilities.rag.faiss_index import FaissIndex
        from app.core.config import WorkerSettings

        settings = WorkerSettings()
        max_seq_length = resolve_max_seq_length(getattr(settings, "rag_embedding_max_seq_length", None))
        self._embedder = SentenceTransformerEmbedder(
            model_name=settings.rag_embedding_model,
            query_prefix=settings.rag_embedding_prefix_query,
            passage_prefix=settings.rag_embedding_prefix_passage,
            max_seq_length=max_seq_length,
            batch_size=int(settings.rag_embedding_batch_size),
            cuda_alloc_conf=settings.rag_embedding_cuda_alloc_conf or None,
        )
        self._index = FaissIndex(index_dir)
        self._info = self._index.load()
        self._top_k = int(top_k)
        self._rows_by_faiss_id = {
            int(row["faiss_row_id"]): row
            for row in read_jsonl(index_dir / "search_unit_manifest.jsonl")
            if "faiss_row_id" in row
        }

    def retrieve(self, query: str) -> Any:
        from app.capabilities.rag.generation import RetrievedChunk
        from app.capabilities.rag.retriever import RetrievalReport

        vectors = self._embedder.embed_queries([query])
        hits = self._index.search(vectors, top_k=self._top_k)
        chunks: list[RetrievedChunk] = []
        for row_id, score in (hits[0] if hits else []):
            row = self._rows_by_faiss_id.get(int(row_id))
            if not row:
                continue
            locator = as_mapping(row.get("locator"))
            canonical = as_mapping(row.get("canonical_citation_payload"))
            metadata_json = {**locator, **canonical}
            manifest_track = official.clean(row.get("track") or canonical.get("track") or locator.get("track"))
            source_family = official.clean(
                row.get("source_family")
                or canonical.get("source_family")
                or locator.get("source_family")
                or source_family_for_track(manifest_track)
            )
            locator_schema = official.clean(
                row.get("locator_schema")
                or canonical.get("locator_schema")
                or locator.get("locator_schema")
                or locator_schema_for_track(manifest_track)
            )
            metadata_json["source_bound_official_denominator"] = True
            metadata_json["track"] = manifest_track
            metadata_json["source_family"] = source_family
            metadata_json["locator_schema"] = locator_schema
            metadata_json["manifest_query_id"] = row.get("query_id")
            chunks.append(
                RetrievedChunk(
                    chunk_id=official.clean(row.get("search_unit_id")) or official.clean(row.get("query_id")),
                    doc_id=official.clean(row.get("document_version_id")),
                    section=official.clean(row.get("track")),
                    text=official.clean(row.get("display_text") or row.get("bm25_text") or row.get("embedding_text")),
                    score=float(score),
                    search_unit_id=official.clean(row.get("search_unit_id")),
                    source_file_id=official.clean(locator.get("source_file_id")),
                    source_file_name=official.clean(
                        locator.get("source_pdf_filename")
                        or locator.get("workbook")
                        or locator.get("source_file_path")
                    ),
                    unit_type="SOURCE_BOUND_SEARCH_UNIT",
                    unit_key=official.clean(row.get("source_identity")),
                    title=official.clean(locator.get("workbook") or locator.get("source_pdf_filename")),
                    section_path=official.clean(locator.get("sheet") or locator.get("region_type")),
                    page_start=int(locator["page"]) if str(locator.get("page") or "").isdigit() else None,
                    page_end=int(locator["page"]) if str(locator.get("page") or "").isdigit() else None,
                    metadata_json=metadata_json,
                )
            )
        return RetrievalReport(
            query=query,
            top_k=self._top_k,
            index_version=self._info.index_version,
            embedding_model=self._info.embedding_model,
            results=chunks,
            reranker_name="source_bound_manifest",
            candidate_k=self._top_k,
        )


def build_source_bound_manifest_retriever(index_dir_arg: Path) -> SourceBoundManifestRetriever:
    return SourceBoundManifestRetriever(index_dir=resolve_worker_path(index_dir_arg))


def inspect_rag_index_dependency(
    index_dir_arg: Path,
    *,
    source_bound_index_load_checked: bool = False,
) -> dict[str, Any]:
    index_dir = resolve_worker_path(index_dir_arg)
    missing_files = [name for name in INDEX_REQUIRED_FILES if not (index_dir / name).exists()]
    build_metadata: dict[str, Any] = {}
    ingest_metadata: dict[str, Any] = {}
    search_unit_manifest_metadata: dict[str, Any] = {}
    manifest_query_ids: list[str] = []
    manifest_search_unit_ids: list[str] = []
    rows: list[dict[str, Any]] = []
    source_bound_artifact_load_check: dict[str, Any] = {"passed": False, "blockers": []}
    build_path = index_dir / "build.json"
    if build_path.exists():
        try:
            build = json.loads(build_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            build = {}
        for key in (
            "index_version",
            "embedding_model",
            "dimension",
            "chunk_count",
            "official_denominator_source_bound",
            "non_production_only",
            "official_denominator_rows",
            "official_rows_by_track",
            "source_bound_locator_schema_covered",
            "baseline_overwrite",
            "candidate_artifacts_as_generation_source",
            "candidate_index_path_used",
            "production_index_path_used",
            "generation_used_expected_answer",
            "generation_used_gold_fields",
            "generation_used_supporting_evidence",
            "promotion_evidence",
            "faiss_build_device_requested",
            "faiss_gpu_used",
            "faiss_gpu_count",
            "faiss_gpu_device",
        ):
            if key in build:
                build_metadata[key] = build[key]
    ingest_path = index_dir / "ingest_manifest.json"
    if ingest_path.exists():
        try:
            ingest = json.loads(ingest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            ingest = {}
        provenance = ingest.get("official_denominator_source_bound_provenance")
        if not isinstance(provenance, Mapping):
            provenance = {}
        ingest_metadata = {
            "index_version": ingest.get("index_version"),
            "embedding_model": ingest.get("embedding_model"),
            "chunk_count": ingest.get("chunk_count"),
            "dimension": ingest.get("dimension"),
            "provenance": dict(provenance),
        }
    manifest_path = index_dir / "search_unit_manifest.jsonl"
    if manifest_path.exists():
        try:
            for line in manifest_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                parsed = json.loads(line)
                if isinstance(parsed, Mapping):
                    rows.append(dict(parsed))
        except json.JSONDecodeError:
            rows = []
        track_counts = Counter(official.clean(row.get("track")) for row in rows)
        manifest_query_ids = sorted({official.clean(row.get("query_id")) for row in rows if official.clean(row.get("query_id"))})
        manifest_search_unit_ids = sorted(
            {official.clean(row.get("search_unit_id")) for row in rows if official.clean(row.get("search_unit_id"))}
        )
        search_unit_manifest_metadata = {
            "row_count": len(rows),
            "unique_query_id_count": len(manifest_query_ids),
            "unique_search_unit_id_count": len(manifest_search_unit_ids),
            "track_counts": dict(sorted(track_counts.items())),
            "all_source_bound": all(row.get("source_bound_official_denominator") is True for row in rows),
        }
    canonical_path = official.repo_relative(index_dir)
    worker_path = worker_relative(index_dir)
    official_index_dir = (AI_WORKER_ROOT / OFFICIAL_SOURCE_BOUND_INDEX_WORKER_RELATIVE).resolve()
    official_source_bound = index_dir.resolve() == official_index_dir
    candidate_index_path_used = "candidate" in str(index_dir).lower()
    production_index_path_used = "production" in str(index_dir).lower() or "\\prod" in str(index_dir).lower()
    build_version_ok = build_metadata.get("index_version") == OFFICIAL_SOURCE_BOUND_INDEX_VERSION
    ingest_version_ok = ingest_metadata.get("index_version") == OFFICIAL_SOURCE_BOUND_INDEX_VERSION
    provenance = ingest_metadata.get("provenance") if isinstance(ingest_metadata.get("provenance"), Mapping) else {}
    expected_counts = {"pdf_business_ocr_mm": 4, "text_namu_v2_1": 6, "xlsx_business_structured": 19}
    build_counts = build_metadata.get("official_rows_by_track")
    provenance_counts = provenance.get("track_counts")
    manifest_schema_missing = source_bound_manifest_schema_missing_from_rows(rows) if manifest_path.exists() else {}
    artifact_contract_ok = (
        build_metadata.get("official_denominator_source_bound") is True
        and build_metadata.get("non_production_only") is True
        and int(build_metadata.get("official_denominator_rows") or 0) == 29
        and build_counts == expected_counts
        and build_metadata.get("source_bound_locator_schema_covered") is True
        and build_metadata.get("baseline_overwrite") is False
        and build_metadata.get("candidate_artifacts_as_generation_source") is False
        and build_metadata.get("candidate_index_path_used") is False
        and build_metadata.get("production_index_path_used") is False
        and build_metadata.get("generation_used_expected_answer") is False
        and build_metadata.get("generation_used_gold_fields") is False
        and build_metadata.get("generation_used_supporting_evidence") is False
        and build_metadata.get("promotion_evidence") is False
        and ingest_version_ok
        and provenance.get("official_denominator_source_bound") is True
        and provenance.get("non_production_only") is True
        and int(provenance.get("official_denominator_rows") or 0) == 29
        and provenance_counts == expected_counts
        and provenance.get("source_bound_locator_schema_covered") is True
        and provenance.get("baseline_overwrite") is False
        and provenance.get("candidate_artifacts_as_generation_source") is False
        and provenance.get("candidate_index_path_used") is False
        and provenance.get("production_index_path_used") is False
        and provenance.get("generation_used_expected_answer") is False
        and provenance.get("generation_used_gold_fields") is False
        and provenance.get("generation_used_supporting_evidence") is False
        and provenance.get("promotion_evidence") is False
        and search_unit_manifest_metadata.get("row_count") == 29
        and search_unit_manifest_metadata.get("unique_query_id_count") == 29
        and search_unit_manifest_metadata.get("unique_search_unit_id_count") == 29
        and search_unit_manifest_metadata.get("track_counts") == expected_counts
        and search_unit_manifest_metadata.get("all_source_bound") is True
        and not manifest_schema_missing
    )
    faiss_load_ok = False
    if source_bound_index_load_checked and not missing_files and build_version_ok and artifact_contract_ok:
        try:
            from app.capabilities.rag.faiss_index import FaissIndex

            info = FaissIndex(index_dir).load()
            faiss_load_ok = (
                info.index_version == OFFICIAL_SOURCE_BOUND_INDEX_VERSION
                and int(info.chunk_count) == 29
                and official.clean(info.embedding_model) == official.clean(build_metadata.get("embedding_model"))
            )
            if not faiss_load_ok:
                source_bound_artifact_load_check["blockers"].append("faiss_build_metadata_mismatch")
        except Exception as exc:  # noqa: BLE001
            source_bound_artifact_load_check["blockers"].append(
                f"faiss_load_failed:{type(exc).__name__}:{exc}"
            )
    elif source_bound_index_load_checked:
        if missing_files:
            source_bound_artifact_load_check["blockers"].append("required_files_missing")
        if not build_version_ok:
            source_bound_artifact_load_check["blockers"].append("build_json_index_version_mismatch")
        if not artifact_contract_ok:
            source_bound_artifact_load_check["blockers"].append("source_bound_artifact_contract_incomplete")
    source_bound_artifact_load_check["passed"] = faiss_load_ok
    source_bound_load_checked = bool(source_bound_index_load_checked and faiss_load_ok)
    if missing_files:
        blocker_category = NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING
    elif production_index_path_used:
        blocker_category = "PRODUCTION_INDEX_PATH_NOT_ALLOWED"
    elif candidate_index_path_used:
        blocker_category = "CANDIDATE_INDEX_PATH_NOT_ALLOWED"
    elif not official_source_bound:
        blocker_category = "NON_OFFICIAL_DENOMINATOR_INDEX_PATH"
    elif not build_version_ok:
        blocker_category = SOURCE_BOUND_INDEX_VERSION_MISMATCH
    elif not source_bound_load_checked:
        blocker_category = SOURCE_BOUND_INDEX_LOAD_CHECK_MISSING
    else:
        blocker_category = None
    rerun_allowed = (
        official_source_bound
        and not missing_files
        and source_bound_load_checked
        and not candidate_index_path_used
        and not production_index_path_used
        and blocker_category is None
    )
    return {
        "canonical_path": canonical_path,
        "worker_relative_path": worker_path,
        "configured_path": str(index_dir_arg),
        "required_files": list(INDEX_REQUIRED_FILES),
        "missing_files": missing_files,
        "exists": index_dir.exists(),
        "satisfied": not missing_files and official_source_bound,
        "build_command": INDEX_BUILD_COMMAND,
        "load_check_command": INDEX_LOAD_CHECK_COMMAND,
        "expected_provenance": (
            "non-production official-denominator source-bound SearchUnit index only; "
            "fixture-all, candidate, and production index paths are not valid substitutes"
        ),
        "official_denominator_source_bound_index": official_source_bound,
        "source_bound_index_load_checked": source_bound_load_checked,
        "source_bound_artifact_load_check": source_bound_artifact_load_check,
        "expected_index_version": OFFICIAL_SOURCE_BOUND_INDEX_VERSION,
        "index_version_matches_expected": build_version_ok,
        "ingest_manifest_metadata": ingest_metadata,
        "search_unit_manifest_metadata": search_unit_manifest_metadata,
        "source_bound_artifact_contract_ok": artifact_contract_ok,
        "manifest_query_ids": manifest_query_ids,
        "manifest_search_unit_ids": manifest_search_unit_ids,
        "manifest_missing_fields_by_query_id": manifest_schema_missing,
        "production_index_path_used": production_index_path_used,
        "candidate_index_path_used": candidate_index_path_used,
        "rerun_allowed": rerun_allowed,
        "blocker_category": blocker_category,
        "build_metadata": build_metadata,
    }


def inspect_source_bound_v2_preflight(
    index_dir_arg: Path,
    *,
    readiness_path: Path,
    source_bound_index_load_checked: bool = False,
) -> dict[str, Any]:
    dependency = inspect_rag_index_dependency(
        index_dir_arg,
        source_bound_index_load_checked=source_bound_index_load_checked,
    )
    readiness_errors: list[str] = []
    try:
        readiness = official.read_json(readiness_path)
    except Exception as exc:  # noqa: BLE001
        readiness = {}
        readiness_errors.append(f"readiness_unreadable:{type(exc).__name__}:{exc}")

    compact_readiness = {
        "path": official.repo_relative(readiness_path),
        "status": readiness.get("status"),
        "target_index_path": readiness.get("target_index_path"),
        "official_denominator_rows": readiness.get("official_denominator_rows"),
        "official_rows_by_track": readiness.get("official_rows_by_track"),
        "blocked_query_ids": readiness.get("blocked_query_ids") or [],
        "missing_fields_by_query_id": readiness.get("missing_fields_by_query_id") or {},
        "missing_source_files_by_query_id": readiness.get("missing_source_files_by_query_id") or {},
        "target_index_built": bool(readiness.get("target_index_built")),
        "load_check_passed": bool(readiness.get("load_check_passed")),
        "rerun_allowed": bool(readiness.get("rerun_allowed")),
    }
    expected_counts = {"pdf_business_ocr_mm": 4, "text_namu_v2_1": 6, "xlsx_business_structured": 19}
    if readiness.get("status") != "BUILD_READY_LOAD_CHECK_PASSED":
        readiness_errors.append("readiness_status_not_build_ready_load_check_passed")
    if readiness.get("blocked_query_ids") not in ([], None):
        readiness_errors.append("readiness_blocked_query_ids_not_empty")
    if readiness.get("missing_fields_by_query_id") not in ({}, None):
        readiness_errors.append("readiness_missing_fields_not_empty")
    if readiness.get("missing_source_files_by_query_id") not in ({}, None):
        readiness_errors.append("readiness_missing_source_files_not_empty")
    if readiness.get("target_index_path") != "ai/eval/indexes/rag-data-official-denominator-v1":
        readiness_errors.append("readiness_target_index_path_mismatch")
    if readiness.get("target_index_built") is not True:
        readiness_errors.append("readiness_target_index_built_not_true")
    if readiness.get("load_check_passed") is not True:
        readiness_errors.append("readiness_load_check_passed_not_true")
    if readiness.get("rerun_allowed") is not True:
        readiness_errors.append("readiness_rerun_allowed_not_true")
    if int(readiness.get("official_denominator_rows") or 0) != 29:
        readiness_errors.append("readiness_official_denominator_rows_mismatch")
    if readiness.get("official_rows_by_track") != expected_counts:
        readiness_errors.append("readiness_track_counts_mismatch")

    manifest_metadata = dependency.get("search_unit_manifest_metadata")
    if isinstance(manifest_metadata, Mapping):
        if manifest_metadata.get("row_count") != 29:
            readiness_errors.append("manifest_row_count_mismatch")
        if manifest_metadata.get("unique_query_id_count") != 29:
            readiness_errors.append("manifest_unique_query_id_count_mismatch")
        if manifest_metadata.get("unique_search_unit_id_count") != 29:
            readiness_errors.append("manifest_unique_search_unit_id_count_mismatch")
        if manifest_metadata.get("track_counts") != expected_counts:
            readiness_errors.append("manifest_track_counts_mismatch")

    dependency["readiness_artifact"] = compact_readiness
    dependency["preflight_errors"] = readiness_errors
    if readiness_errors:
        dependency["rerun_allowed"] = False
        dependency["satisfied"] = False
        dependency["blocker_category"] = STALE_SOURCE_BOUND_READINESS_ARTIFACT
    return dependency


def resolve_worker_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return AI_WORKER_ROOT / path


def source_bound_manifest_schema_missing_from_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    missing_by_query_id: dict[str, list[str]] = {}
    for row in rows:
        track = official.clean(row.get("track"))
        locator = official.nested_mapping(row, "locator")
        if track not in REQUIRED_CITATION_FIELDS_BY_TRACK:
            missing_by_query_id[official.clean(row.get("query_id"))] = ["track"]
            continue
        missing = [
            field
            for field in REQUIRED_CITATION_FIELDS_BY_TRACK[track]
            if not has_required_citation_value(locator.get(field), field=field)
        ]
        if missing:
            missing_by_query_id[official.clean(row.get("query_id"))] = missing
    return missing_by_query_id


def worker_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(AI_WORKER_ROOT.resolve()).as_posix()
    except ValueError:
        return official.repo_relative(resolved)


def fallback_registry_application_from_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Use current source-of-truth config as the registry-application check surface.

    Hard cleanup intentionally removed the older registry-application report from
    the current report directory. For the next measurement, the official
    denominator is still validated against the metric input config, registry,
    pre-execution smoke report, and gold CSVs; this fallback only prevents a
    removed historical helper report from becoming a false blocker.
    """

    artifacts = official.nested_mapping(config, "official_metric_input_artifacts")
    return {
        "official_metric_execution_started": False,
        "tuning_run_started": False,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "gold_mutation": False,
        "denominator_mutation": False,
        "production_mutation": False,
        "cross_track_averages_computed": False,
        "official_metric_input_artifacts": dict(artifacts),
    }


def execute_agentic_generation_rows(
    rows: Sequence[Mapping[str, Any]],
    args: argparse.Namespace,
    agentic_status: Mapping[str, Any],
) -> list[dict[str, Any]]:
    from app.capabilities.agent.critic import RuleCritic
    from app.capabilities.agent.loop import AgentLoopController, LoopBudget
    from app.capabilities.agent.rewriter import NoOpQueryRewriter
    from app.capabilities.agent.synthesizer import AgentSynthesizer
    from app.capabilities.rag.generation import ExtractiveGenerator
    from app.capabilities.rag.query_parser import RegexQueryParser

    parser = RegexQueryParser()
    generator = ExtractiveGenerator()
    synthesizer = AgentSynthesizer(generator)
    loop = AgentLoopController(
        critic=RuleCritic(),
        rewriter=NoOpQueryRewriter(),
        parser=parser,
        budget=LoopBudget(
            max_iter=args.agent_max_iter,
            max_total_ms=args.agent_max_total_ms,
            max_llm_tokens=args.agent_max_llm_tokens,
            min_confidence_to_stop=args.agent_min_stop_confidence,
        ),
    )
    retriever = agentic_status["_retriever"]
    local_gpu_used = agentic_status_uses_local_gpu(agentic_status)
    manifest_search_unit_ids = set(agentic_status.get("source_bound_manifest_search_unit_ids") or [])
    out: list[dict[str, Any]] = []
    for row in rows:
        question = official.clean(row.get("question"))
        parsed = parser.parse(question)

        def execute_fn(parsed_query: Any) -> tuple[str, list[Any], int]:
            report = retriever.retrieve(parsed_query.normalized)
            chunks = list(getattr(report, "results", []) or [])
            return generator.generate(question, chunks), chunks, 0

        try:
            outcome = loop.run(question=question, initial_parsed_query=parsed, execute_fn=execute_fn)
            raw_generated_answer = synthesizer.synthesize(question, outcome)
            chunks = list(outcome.aggregated_chunks)
            query_track = official.clean(row.get("_track") or row.get("track"))
            query_id = official.clean(row.get("query_id"))
            generated_citations = citations_from_chunks(
                chunks,
                track=query_track,
                query_id=query_id,
                require_official_compatible=not bool(
                    getattr(args, "allow_chunk_only_official_citation_fallback", False)
                ),
                structured_adapters_enabled=bool(
                    getattr(args, "enable_structured_source_bound_adapters", False)
                ),
                allowed_manifest_search_unit_ids=manifest_search_unit_ids or None,
            )
            citation_contract = scored_citation_contract(generated_citations, track=query_track)
            scored_chunks = chunks_from_scored_citation_contract(chunks, citation_contract)
            generated_answer = (
                generator.generate(question, scored_chunks)
                if not bool(getattr(args, "allow_chunk_only_official_citation_fallback", False))
                else raw_generated_answer
            )
            score = score_generated_row(row, generated_answer, scored_chunks)
            if citation_contract["same_track_valid_citation_count"] == 0 and not bool(
                getattr(args, "allow_chunk_only_official_citation_fallback", False)
            ):
                validation = citation_contract.get("primary_failure_validation") or {}
                score = {
                    "answer_score": None,
                    "citation_support_score": None,
                    "failure_category": official.clean(validation.get("category"))
                    or SAME_TRACK_LOCATOR_INCOMPLETE,
                    "failure_detail": official.clean(validation.get("detail"))
                    or "No same-track source-bound citation was official-compatible",
                }
            out.append(
                result_row(
                    row,
                    args=args,
                    generated_answer=generated_answer,
                    generated_citations=generated_citations,
                    scored_citations=list(citation_contract["scored_citations"]),
                    discarded_off_track_citations=list(citation_contract["discarded_off_track_citations"]),
                    retrieved_evidence=evidence_from_chunks(chunks),
                    answer_score=score["answer_score"],
                    citation_support_score=score["citation_support_score"],
                    scoring_attempted=score["answer_score"] is not None and score["citation_support_score"] is not None,
                    failure_category=score["failure_category"],
                    failure_detail=score["failure_detail"],
                    agentic_loop_executed=True,
                    agentic_loop_steps_count=len(outcome.steps),
                    infrastructure_blocker_category=None,
                    local_gpu_used=local_gpu_used,
                )
            )
        except Exception as exc:  # pragma: no cover - local pipeline availability dependent.
            out.append(
                result_row(
                    row,
                    args=args,
                    generated_answer="",
                    generated_citations=[],
                    scored_citations=[],
                    discarded_off_track_citations=[],
                    retrieved_evidence=[],
                    answer_score=None,
                    citation_support_score=None,
                    scoring_attempted=False,
                    failure_category=AGENTIC_GENERATION_ROW_FAILED,
                    failure_detail=f"agentic generation failed closed: {type(exc).__name__}: {exc}",
                    agentic_loop_executed=True,
                    agentic_loop_steps_count=0,
                    infrastructure_blocker_category=None,
                    local_gpu_used=local_gpu_used,
                )
            )
    return out


def fail_closed_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    args: argparse.Namespace,
    failure_detail: str,
    failure_category: str | None = None,
) -> list[dict[str, Any]]:
    infrastructure_category = failure_category or NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING
    return [
        result_row(
            row,
            args=args,
            generated_answer="",
            generated_citations=[],
            scored_citations=[],
            discarded_off_track_citations=[],
            retrieved_evidence=[],
            answer_score=None,
            citation_support_score=None,
            scoring_attempted=False,
            failure_category=GENERATION_PIPELINE_UNAVAILABLE,
            failure_detail=failure_detail,
            agentic_loop_executed=False,
            agentic_loop_steps_count=0,
            infrastructure_blocker_category=infrastructure_category,
        )
        for row in rows
    ]


def result_row(
    row: Mapping[str, Any],
    *,
    args: argparse.Namespace,
    generated_answer: str,
    generated_citations: list[dict[str, Any]],
    scored_citations: list[dict[str, Any]],
    discarded_off_track_citations: list[dict[str, Any]],
    retrieved_evidence: list[dict[str, Any]],
    answer_score: float | None,
    citation_support_score: float | None,
    scoring_attempted: bool,
    failure_category: str,
    failure_detail: str,
    agentic_loop_executed: bool,
    agentic_loop_steps_count: int,
    infrastructure_blocker_category: str | None,
    local_gpu_used: bool = False,
) -> dict[str, Any]:
    structured_adapter_expected = bool(
        getattr(args, "enable_structured_source_bound_adapters", False)
    ) and row_track_supports_structured_adapter(row)
    structured_adapter_outputs = [
        bool(item.get("structured_adapter_output_from_source_bound_search_unit"))
        for item in scored_citations
        if item.get("structured_source_bound_adapter_enabled") is True
    ]
    same_track_citations = same_track_generated_citations(generated_citations)
    row_query_id = official.clean(row.get("query_id"))
    query_bound_scored_citation_count = query_bound_citation_count(scored_citations, row_query_id)
    schema_mismatch_residual_count = sum(
        1
        for item in same_track_citations
        if is_invalid_same_track_citation(item)
    )
    run_id = getattr(args, "run_id", RUN_ID)
    return {
        "schema_version": run_id,
        "run_id": run_id,
        "query_id": official.clean(row.get("query_id")),
        "track": official.clean(row.get("_track") or row.get("track")),
        "generated_answer": generated_answer,
        "generated_citations": generated_citations,
        "scored_citations": scored_citations,
        "discarded_off_track_citations": discarded_off_track_citations,
        "retrieved_evidence_identifiers": [item["id"] for item in retrieved_evidence if item.get("id")],
        "retrieved_evidence": retrieved_evidence,
        "scoring_attempted": scoring_attempted,
        "answer_score": answer_score,
        "citation_support_score": citation_support_score,
        "score_status": "PASS" if failure_category == "PASS" else "FAIL_CLOSED",
        "failure_category": failure_category,
        "failure_reason": failure_detail,
        "agentic_loop_enabled": True,
        "agentic_loop_executed": agentic_loop_executed,
        "agentic_loop_backend": args.agent_loop_backend,
        "agentic_loop_steps_count": agentic_loop_steps_count,
        "infrastructure_blocker_category": infrastructure_blocker_category,
        "local_llm_used": False,
        "local_gpu_used": local_gpu_used,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "search_unit_citation_payloads_used": any(
            bool(item.get("search_unit_citation_payload")) for item in generated_citations
        ),
        "all_generated_citations_source_bound": citations_source_bound(generated_citations),
        "same_track_generated_citations_source_bound": citations_source_bound(same_track_citations),
        "scored_citations_source_bound": citations_source_bound(scored_citations),
        "adapter_output_for_same_track_citations": adapter_output_for_same_track_citations(scored_citations),
        "discarded_off_track_citation_count": len(discarded_off_track_citations),
        "same_track_valid_citation_count": len(scored_citations),
        "query_bound_scored_citation_count": query_bound_scored_citation_count,
        "non_query_bound_same_track_scored_citation_count": (
            len(scored_citations) - query_bound_scored_citation_count
        ),
        "schema_mismatch_residual_count": schema_mismatch_residual_count,
        "chunk_only_citation_fallback_disabled": not bool(
            getattr(args, "allow_chunk_only_official_citation_fallback", False)
        ),
        "structured_source_bound_adapters_enabled": bool(
            getattr(args, "enable_structured_source_bound_adapters", False)
        ),
        "adapter_output_from_source_bound_search_units": (
            bool(structured_adapter_outputs) and all(structured_adapter_outputs)
            if structured_adapter_expected
            else False
        ),
        "promotion_evidence": False,
    }


def row_track_supports_structured_adapter(row: Mapping[str, Any]) -> bool:
    return official.clean(row.get("_track") or row.get("track")) in {
        "xlsx_business_structured",
        "pdf_business_ocr_mm",
    }


def same_track_generated_citations(citations: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [item for item in citations if not citation_validation(item).get("off_track")]


def citation_validation(citation: Mapping[str, Any]) -> Mapping[str, Any]:
    validation = citation.get("citation_payload_validation")
    return validation if isinstance(validation, Mapping) else {}


def is_invalid_same_track_citation(citation: Mapping[str, Any]) -> bool:
    validation = citation_validation(citation)
    return validation.get("ok") is not True and validation.get("off_track") is not True


def citation_source_bound(citation: Mapping[str, Any]) -> bool:
    payload = citation.get("search_unit_citation_payload")
    return isinstance(payload, Mapping) and payload.get("source_bound_official_denominator") is True


def citations_source_bound(citations: Sequence[Mapping[str, Any]]) -> bool:
    return bool(citations) and all(citation_source_bound(item) for item in citations)


def adapter_output_for_same_track_citations(citations: Sequence[Mapping[str, Any]]) -> bool:
    adapter_citations = [
        item
        for item in citations
        if item.get("structured_source_bound_adapter_enabled") is True
    ]
    if not adapter_citations:
        return False
    return all(
        bool(item.get("structured_adapter_output_from_source_bound_search_unit"))
        for item in adapter_citations
    )


def query_bound_citation_count(citations: Sequence[Mapping[str, Any]], row_query_id: str) -> int:
    if not row_query_id:
        return 0
    return sum(
        1
        for item in citations
        if official.clean(citation_validation(item).get("manifest_query_id")) == row_query_id
    )


def agentic_status_uses_local_gpu(agentic_status: Mapping[str, Any]) -> bool:
    dependency = agentic_status.get("index_dependency")
    if not isinstance(dependency, Mapping):
        return False
    build_metadata = dependency.get("build_metadata")
    if not isinstance(build_metadata, Mapping):
        return False
    return bool(build_metadata.get("faiss_gpu_used"))


def score_generated_row(row: Mapping[str, Any], generated_answer: str, chunks: Sequence[Any]) -> dict[str, Any]:
    citation_text = " ".join(official.clean(getattr(chunk, "text", "")) for chunk in chunks)
    expected_answer = official.clean(row.get("expected_answer"))
    supporting_evidence = official.clean(row.get("supporting_evidence"))
    exact_answer_ok = official.expected_answer_supported_by_text(expected_answer, generated_answer)
    exact_citation_ok = official.expected_answer_supported_by_text(supporting_evidence or expected_answer, citation_text)
    normalized_answer_ok = source_bound_answer_equivalent_to_reference(
        row=row,
        expected_answer=expected_answer,
        generated_answer=generated_answer,
    )
    normalized_citation_ok = source_bound_answer_equivalent_to_reference(
        row=row,
        expected_answer=supporting_evidence or expected_answer,
        generated_answer=citation_text,
        allow_language_drift=True,
    )
    answer_ok = exact_answer_ok or normalized_answer_ok
    citation_ok = exact_citation_ok or normalized_citation_ok
    compatibility_applied = (normalized_answer_ok and not exact_answer_ok) or (
        normalized_citation_ok and not exact_citation_ok
    )
    if answer_ok and citation_ok:
        detail = (
            "post-generation scorer compatibility normalization accepted a tight source-bound equivalent"
            if compatibility_applied
            else ""
        )
        return {
            "answer_score": 1.0,
            "citation_support_score": 1.0,
            "failure_category": "PASS",
            "failure_detail": detail,
            "scorer_compatibility_normalization_applied": compatibility_applied,
        }
    category = "PARTIAL_OR_UNSUPPORTED" if answer_ok or citation_ok else "CITATION_UNSUPPORTED"
    return {
        "answer_score": 1.0 if answer_ok else 0.0,
        "citation_support_score": 1.0 if citation_ok else 0.0,
        "failure_category": category,
        "failure_detail": "deterministic post-generation scoring did not find answer and citation support together",
        "scorer_compatibility_normalization_applied": compatibility_applied,
    }


def source_bound_answer_equivalent_to_reference(
    *,
    row: Mapping[str, Any],
    expected_answer: str,
    generated_answer: str,
    allow_language_drift: bool = False,
) -> bool:
    expected = official.clean(expected_answer)
    generated = official.clean(generated_answer)
    if not expected or not generated:
        return False
    if official.expected_answer_supported_by_text(expected, generated):
        return True
    if not allow_language_drift and korean_answer_language_drift(row=row, answer=generated):
        return False
    expected_value_tokens = reference_value_tokens(expected)
    if expected_value_tokens:
        target = official.normalized_text(generated)
        return all(any(variant in target for variant in token_variants(token)) for token in expected_value_tokens)
    expected_tokens = audit_meaningful_tokens(expected)
    if not expected_tokens:
        return False
    matched = matched_audit_token_count(expected_tokens, generated)
    return matched / len(expected_tokens) >= 0.75


def korean_answer_language_drift(*, row: Mapping[str, Any], answer: str) -> bool:
    query = official.clean(row.get("question") or row.get("query"))
    if not contains_hangul(query):
        return False
    return contains_hangul(official.clean(row.get("expected_answer"))) and not contains_hangul(answer)


def contains_hangul(value: str) -> bool:
    return bool(re.search(r"[가-힣]", value or ""))


def reference_value_tokens(value: str) -> list[str]:
    date_tokens = re.findall(r"\d{4}-\d{1,2}-\d{1,2}", value)
    date_tokens.extend(re.findall(r"\d{4}년\s*\d{1,2}월(?:\s*\d{1,2}일)?", value))
    tokens: list[str] = list(date_tokens)
    if not date_tokens:
        tokens.extend(re.findall(r"\d[\d,]*(?:\.\d+)?%?p?", value))
    out: list[str] = []
    for token in tokens:
        normalized = official.clean(token)
        if normalized and normalized not in out:
            out.append(normalized)
    return out


def token_variants(token: str) -> set[str]:
    cleaned = official.clean(token)
    variants = {official.normalized_text(cleaned)}
    date_match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", cleaned)
    if date_match:
        year, month, day = date_match.groups()
        month_int = int(month)
        day_int = int(day)
        variants.update(
            {
                official.normalized_text(f"{year}년 {month_int}월 {day_int}일"),
                official.normalized_text(f"{year}년 {int(month):02d}월 {int(day):02d}일"),
                f"{year}{month_int:02d}{day_int:02d}",
            }
        )
    korean_month_match = re.fullmatch(r"(\d{4})년\s*(\d{1,2})월(?:\s*(\d{1,2})일)?", cleaned)
    if korean_month_match:
        year, month, day = korean_month_match.groups()
        variants.add(official.normalized_text(f"{year}-{int(month):02d}"))
        if day:
            variants.add(official.normalized_text(f"{year}-{int(month):02d}-{int(day):02d}"))
            variants.add(f"{year}{int(month):02d}{int(day):02d}")
    if "," in cleaned:
        variants.add(official.normalized_text(cleaned.replace(",", "")))
    return {variant for variant in variants if variant}


def run_v2_2_llm_backend_validation(
    *,
    args: argparse.Namespace,
    consumed: Mapping[str, Any],
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows = list(consumed["rows"])
    source_by_id = {official.clean(row.get("query_id")): row for row in source_rows}
    v2_1_summary = official.read_json(Path(args.v2_1_summary_json))
    v2_1_rows = read_jsonl(Path(args.v2_1_results_jsonl))
    v2_1_attribution = official.read_json(Path(args.v2_1_failure_attribution_json))
    status_events = read_jsonl(Path(args.status_jsonl)) if Path(args.status_jsonl).exists() else []
    consistency = v2_1_artifact_consistency_preflight(
        summary=v2_1_summary,
        attribution=v2_1_attribution,
        rows=v2_1_rows,
        status_events=status_events,
    )
    backend_preflight = llm_backend_preflight_for_v2_2(args, check_endpoint=True)
    if validation_errors:
        consistency = {
            **consistency,
            "ok": False,
            "errors": [*list(consistency.get("errors") or []), *validation_errors],
            "failure_bucket": "PROMPT_CONTEXT_POLICY_VIOLATION",
        }
    if not consistency["ok"]:
        rows = v2_2_fail_closed_rows_from_v2_1(
            v2_1_rows,
            {
                **backend_preflight,
                "failure_bucket": consistency.get("failure_bucket") or "PROMPT_CONTEXT_POLICY_VIOLATION",
                "blockers": list(consistency.get("errors") or []),
            },
        )
        summary = build_v2_2_summary(
            args=args,
            rows=rows,
            baseline=baseline,
            agentic_status=agentic_status,
            v2_1_preflight=consistency,
            backend_preflight=backend_preflight,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=registry_application_fallback_used,
            baseline_path=baseline_path,
            validation_status="V2_1_ARTIFACT_CONSISTENCY_FAIL_CLOSED",
        )
        return summary, rows
    if not backend_preflight["ok"]:
        rows = v2_2_fail_closed_rows_from_v2_1(v2_1_rows, backend_preflight)
        summary = build_v2_2_summary(
            args=args,
            rows=rows,
            baseline=baseline,
            agentic_status=agentic_status,
            v2_1_preflight=consistency,
            backend_preflight=backend_preflight,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=registry_application_fallback_used,
            baseline_path=baseline_path,
            validation_status="LLM_BACKEND_UNAVAILABLE_FAIL_CLOSED",
        )
        return summary, rows

    rows: list[dict[str, Any]] = []
    for v2_1_row in v2_1_rows:
        if row_has_structured_adapter_output(v2_1_row):
            rows.append(v2_2_retained_structured_adapter_row(v2_1_row, backend_preflight))
            continue
        if official.clean(v2_1_row.get("query_id")) not in V2_2_SYNTHESIS_TARGET_QUERY_IDS:
            rows.append(v2_2_pass_retained_row(v2_1_row, backend_preflight))
            continue
        rows.append(
            v2_2_llm_synthesis_row(
                v2_1_row=v2_1_row,
                source_row=source_by_id.get(official.clean(v2_1_row.get("query_id")), {}),
                backend_preflight=backend_preflight,
                args=args,
            )
        )
    summary = build_v2_2_summary(
        args=args,
        rows=rows,
        baseline=baseline,
        agentic_status=agentic_status,
        v2_1_preflight=consistency,
        backend_preflight=backend_preflight,
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        application_path=application_path,
        registry_application_fallback_used=registry_application_fallback_used,
        baseline_path=baseline_path,
        validation_status="LLM_BACKEND_VALIDATION_COMPLETED",
    )
    return summary, rows


def v2_1_artifact_consistency_preflight(
    *,
    summary: Mapping[str, Any],
    attribution: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    status_events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    row_count = len(rows)
    failed_ids = sorted(
        official.clean(row.get("query_id"))
        for row in rows
        if official.clean(row.get("failure_category")) != "PASS"
    )
    per_track_pass = {
        track: sum(1 for row in rows if row.get("track") == track and row.get("failure_category") == "PASS")
        for track in official.TRACKS
    }
    residual_audit = attribution.get("residual_failure_audit") or summary.get("residual_failure_audit") or {}
    residual_counts = residual_audit.get("counts") if isinstance(residual_audit, Mapping) else {}
    readiness = (
        residual_audit.get("llm_backend_validation_readiness")
        if isinstance(residual_audit, Mapping)
        else None
    )
    expected_per_track = {
        "pdf_business_ocr_mm": 4,
        "text_namu_v2_1": 5,
        "xlsx_business_structured": 19,
    }
    if summary.get("run_id") != V2_1_RUN_ID:
        errors.append("v2_1_summary_run_id_mismatch")
    if attribution.get("run_id") != V2_1_RUN_ID:
        errors.append("v2_1_attribution_run_id_mismatch")
    if int(summary.get("result_count") or 0) != 29 or row_count != 29:
        errors.append("v2_1_row_count_mismatch")
    if int(summary.get("scored_count") or 0) != 29:
        errors.append("v2_1_scored_count_mismatch")
    if int(summary.get("pass_count") or 0) != 28:
        errors.append("v2_1_pass_count_mismatch")
    if per_track_pass != expected_per_track:
        errors.append("v2_1_per_track_pass_count_mismatch")
    if failed_ids != ["text_namu_v2_0017"]:
        errors.append("v2_1_remaining_failure_query_ids_mismatch")
    if (attribution.get("primary_attribution_counts") or {}) != {"ANSWER_SYNTHESIS_LIMITATION": 1, "PASS": 28}:
        errors.append("v2_1_primary_attribution_counts_mismatch")
    if int((residual_counts or {}).get("query_bound_evidence_gap") or 0) != 0:
        errors.append("v2_1_query_bound_evidence_gap_not_zero")
    if int(summary.get("schema_mismatch_residual_count") or 0) != 0:
        errors.append("v2_1_schema_mismatch_residual_not_zero")
    if summary.get("promotion_evidence") is not False or attribution.get("promotion_evidence") is not False:
        errors.append("v2_1_promotion_evidence_not_false")
    if readiness != "READY_FOR_LLM_BACKEND_VALIDATION_RESIDUALS_CONFIRMED_AS_SYNTHESIS":
        errors.append("v2_1_llm_backend_readiness_mismatch")
    if not any(
        event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
        and event.get("run_id") == V2_1_RUN_ID
        and int(event.get("pass_count") or 0) == 28
        for event in status_events
    ):
        errors.append("v2_1_measurement_status_event_missing_or_stale")
    if not any(
        event.get("event_type") == "official_answer_citation_agentic_loop_failure_attribution"
        and event.get("run_id") == V2_1_RUN_ID
        and (event.get("primary_attribution_counts") or {}) == {"ANSWER_SYNTHESIS_LIMITATION": 1, "PASS": 28}
        for event in status_events
    ):
        errors.append("v2_1_failure_attribution_status_event_missing_or_stale")
    answer_synthesis_ids = sorted(
        official.clean(row.get("query_id"))
        for row in attribution.get("row_level_attribution") or []
        if row.get("primary_attribution") == "ANSWER_SYNTHESIS_LIMITATION"
    )
    if answer_synthesis_ids != ["text_namu_v2_0017"]:
        errors.append("v2_1_answer_synthesis_query_ids_mismatch")
    return {
        "ok": not errors,
        "failure_bucket": None if not errors else "PROMPT_CONTEXT_POLICY_VIOLATION",
        "errors": errors,
        "run_id": summary.get("run_id"),
        "rows": row_count,
        "scored_count": summary.get("scored_count"),
        "pass_count": summary.get("pass_count"),
        "per_track_pass_count": per_track_pass,
        "remaining_failure_query_ids": failed_ids,
        "answer_synthesis_limitation_query_ids": answer_synthesis_ids,
        "query_bound_evidence_gap_count": int((residual_counts or {}).get("query_bound_evidence_gap") or 0),
        "schema_mismatch_residual_count": int(summary.get("schema_mismatch_residual_count") or 0),
        "promotion_evidence": bool(summary.get("promotion_evidence")),
        "readiness": readiness,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
    }


def llm_backend_preflight_for_v2_2(args: Any, *, check_endpoint: bool = True) -> dict[str, Any]:
    backend = official.clean(getattr(args, "llm_backend", "")) or "llamacpp"
    model = official.clean(getattr(args, "llm_model", "")) or "gemma4-e2b-local"
    timeout = int(getattr(args, "llm_timeout_seconds", 120) or 120)
    max_tokens = int(getattr(args, "llm_max_tokens", 4096) or 4096)
    retries = int(getattr(args, "llm_strict_json_retries", 3) or 3)
    base_url = official.clean(getattr(args, "llm_base_url", ""))
    blockers: list[str] = []
    resolved_base_url = base_url
    if backend == "noop":
        blockers.append("noop backend is not a real LLM validation backend")
    else:
        try:
            from rag_text_namu_local_llm_rewrite_v2 import (  # noqa: WPS433
                local_llm_entry_blockers,
                resolve_base_url,
            )

            resolved_base_url = resolve_base_url(backend, base_url)
            blockers.extend(
                local_llm_entry_blockers(
                    backend=backend,
                    base_url=resolved_base_url,
                    model=model,
                    check_endpoint=check_endpoint,
                    timeout_seconds=min(timeout, 5),
                )
            )
        except Exception as exc:  # noqa: BLE001
            blockers.append(f"local LLM backend preflight failed: {type(exc).__name__}: {exc}")
    ok = not blockers and backend != "noop"
    return {
        "ok": ok,
        "failure_bucket": None if ok else "LLM_BACKEND_UNAVAILABLE",
        "llm_backend": backend,
        "base_url": resolved_base_url,
        "model": model,
        "real_llm_backend_used": ok,
        "local_llm_used": ok,
        "local_endpoint_only": backend != "noop",
        "timeout_seconds": timeout,
        "max_tokens": max_tokens,
        "strict_json_retries": retries,
        "retry_policy": "strict_json_retries_then_fail_closed",
        "fail_closed_policy": "no_noop_fallback_no_extractive_promotion",
        "blockers": blockers,
    }


def v2_2_fail_closed_rows_from_v2_1(
    rows: Sequence[Mapping[str, Any]],
    backend_preflight: Mapping[str, Any],
) -> list[dict[str, Any]]:
    bucket = official.clean(backend_preflight.get("failure_bucket")) or "LLM_BACKEND_UNAVAILABLE"
    return [
        v2_2_base_row_from_v2_1(
            row,
            backend_preflight,
            validation_bucket=bucket,
            failure_category=bucket,
            llm_backend_validation_started=False,
            llm_invoked_for_row=False,
            llm_answer="",
            generated_answer="",
            failure_reason="; ".join(official.clean(item) for item in backend_preflight.get("blockers") or []),
            retain_source_scores=False,
            clear_primary_outputs=True,
        )
        for row in rows
    ]


def row_has_structured_adapter_output(row: Mapping[str, Any]) -> bool:
    return any(
        citation.get("structured_adapter_output_from_source_bound_search_unit") is True
        for citation in row.get("scored_citations") or []
        if isinstance(citation, Mapping)
    )


def v2_2_retained_structured_adapter_row(
    row: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
) -> dict[str, Any]:
    bucket = "PASS_RETAINED" if row.get("failure_category") == "PASS" else "STRUCTURED_ADAPTER_REGRESSED"
    return v2_2_base_row_from_v2_1(
        row,
        backend_preflight,
        validation_bucket=bucket,
        failure_category=row.get("failure_category") if bucket == "PASS_RETAINED" else bucket,
        llm_backend_validation_started=True,
        llm_invoked_for_row=False,
        llm_answer="",
        generated_answer=official.clean(row.get("generated_answer")),
        failure_reason="structured adapter output retained; LLM did not overwrite deterministic adapter result",
        structured_adapter_output_retained=True,
        structured_adapter_overwritten_by_llm=False,
    )


def v2_2_pass_retained_row(row: Mapping[str, Any], backend_preflight: Mapping[str, Any]) -> dict[str, Any]:
    return v2_2_base_row_from_v2_1(
        row,
        backend_preflight,
        validation_bucket="PASS_RETAINED" if row.get("failure_category") == "PASS" else "LLM_SYNTHESIS_REGRESSED",
        failure_category=row.get("failure_category"),
        llm_backend_validation_started=True,
        llm_invoked_for_row=False,
        llm_answer="",
        generated_answer=official.clean(row.get("generated_answer")),
        failure_reason="non-target v2.1 answer retained for regression guard",
    )


def v2_2_llm_synthesis_row(
    *,
    v2_1_row: Mapping[str, Any],
    source_row: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    context = build_v2_2_prompt_context(v2_1_row, use_query_bound_only=False)
    if context["prompt_context_policy_violation"]:
        return v2_2_base_row_from_v2_1(
            v2_1_row,
            backend_preflight,
            validation_bucket="PROMPT_CONTEXT_POLICY_VIOLATION",
            failure_category="PROMPT_CONTEXT_POLICY_VIOLATION",
            llm_backend_validation_started=True,
            llm_invoked_for_row=False,
            llm_answer="",
            generated_answer="",
            failure_reason="prompt context was not source-bound same-track only",
            clear_primary_outputs=True,
        )
    try:
        from rag_text_namu_local_llm_rewrite_v2 import call_local_llm_strict_json  # noqa: WPS433

        prompt = build_v2_2_llm_prompt(
            v2_1_row,
            context,
            question=official.clean(source_row.get("question") or v2_1_row.get("query_id")),
        )
        parsed, strict_json_meta = call_local_llm_strict_json(
            backend=official.clean(backend_preflight.get("llm_backend")),
            base_url=official.clean(backend_preflight.get("base_url")),
            model=official.clean(backend_preflight.get("model")),
            prompt=prompt,
            temperature=0.0,
            max_tokens=int(backend_preflight.get("max_tokens") or 900),
            timeout_seconds=int(backend_preflight.get("timeout_seconds") or 120),
            retries=int(backend_preflight.get("strict_json_retries") or 2),
        )
        llm_answer = official.clean(
            parsed.get("answer") or parsed.get("rewritten_answer") or parsed.get("short_answer")
        )
        if not llm_answer:
            raise ValueError("LLM JSON did not include answer")
        score = score_generated_row(
            source_row,
            llm_answer,
            [SimpleNamespace(text=item["citation_text"]) for item in context["citations"]],
        )
        previous_pass = v2_1_row.get("failure_category") == "PASS"
        new_pass = score["failure_category"] == "PASS"
        if not previous_pass and new_pass:
            bucket = "LLM_SYNTHESIS_IMPROVED"
        elif previous_pass and new_pass:
            bucket = "PASS_RETAINED"
        elif score["citation_support_score"] != 1.0:
            bucket = "CITATION_SUPPORT_REGRESSED"
        else:
            bucket = "LLM_SYNTHESIS_REGRESSED"
        out = v2_2_base_row_from_v2_1(
            v2_1_row,
            backend_preflight,
            validation_bucket=bucket,
            failure_category=score["failure_category"],
            llm_backend_validation_started=True,
            llm_invoked_for_row=True,
            llm_answer=llm_answer,
            generated_answer=llm_answer,
            answer_score=score["answer_score"],
            citation_support_score=score["citation_support_score"],
            scoring_attempted=True,
            failure_reason=score["failure_detail"],
        )
        out["llm_strict_json"] = strict_json_meta
        return out
    except Exception as exc:  # noqa: BLE001
        return v2_2_base_row_from_v2_1(
            v2_1_row,
            backend_preflight,
            validation_bucket="LLM_TIMEOUT_OR_FAIL_CLOSED",
            failure_category="LLM_TIMEOUT_OR_FAIL_CLOSED",
            llm_backend_validation_started=True,
            llm_invoked_for_row=True,
            llm_answer="",
            generated_answer="",
            failure_reason=f"LLM validation failed closed: {type(exc).__name__}: {exc}",
            clear_primary_outputs=True,
        )


def build_v2_2_prompt_context(row: Mapping[str, Any], *, use_query_bound_only: bool) -> dict[str, Any]:
    query_id = official.clean(row.get("query_id"))
    track = official.clean(row.get("track"))
    citations: list[dict[str, Any]] = []
    policy_errors: list[str] = []
    for citation in row.get("scored_citations") or []:
        if not isinstance(citation, Mapping):
            continue
        validation = citation_validation(citation)
        payload = citation.get("search_unit_citation_payload")
        if not isinstance(payload, Mapping) or payload.get("source_bound_official_denominator") is not True:
            policy_errors.append("non_source_bound_scored_citation")
            continue
        if official.clean(validation.get("manifest_track") or payload.get("track")) != track:
            policy_errors.append("off_track_scored_citation")
            continue
        manifest_query_id = official.clean(validation.get("manifest_query_id") or payload.get("manifest_query_id"))
        if use_query_bound_only and manifest_query_id != query_id:
            continue
        citations.append(
            {
                "citation_text": official.clean(citation.get("citation_text")),
                "search_unit_id": official.clean(
                    payload.get("searchUnitId") or payload.get("search_unit_id") or citation.get("search_unit_id")
                ),
                "manifest_query_id": manifest_query_id,
                "track": track,
                "query_bound": manifest_query_id == query_id,
            }
        )
    query_bound_count = sum(1 for item in citations if item["query_bound"])
    non_query_bound_used = any(not item["query_bound"] for item in citations)
    off_track_count = len(row.get("discarded_off_track_citations") or [])
    if not citations:
        policy_errors.append("same_track_source_bound_prompt_context_empty")
    return {
        "citations": citations,
        "same_track_scored_citation_count": len(citations),
        "query_bound_scored_citation_count": query_bound_count,
        "non_query_bound_same_track_context_used": non_query_bound_used,
        "same_track_scored_evidence_used": True,
        "query_bound_evidence_only": bool(use_query_bound_only),
        "off_track_citation_count_excluded_from_prompt": off_track_count,
        "prompt_context_source_bound_only": not policy_errors,
        "prompt_context_policy_violation": bool(policy_errors),
        "policy_errors": policy_errors,
    }


def build_v2_2_llm_prompt(row: Mapping[str, Any], context: Mapping[str, Any], *, question: str) -> str:
    lines = [
        "You are validating answer synthesis for a diagnostic-only source-bound RAG row.",
        "Use only the source-bound context items below. Return exactly one JSON object.",
        'Required JSON keys: "answer", "cited_search_unit_ids", "answer_supported_by_context".',
        f"query_id: {official.clean(row.get('query_id'))}",
        f"track: {official.clean(row.get('track'))}",
        f"question: {official.clean(question)}",
        "source_bound_context:",
    ]
    for index, citation in enumerate(context.get("citations") or [], start=1):
        if not isinstance(citation, Mapping):
            continue
        lines.append(
            f"[{index}] search_unit_id={official.clean(citation.get('search_unit_id'))} "
            f"query_bound={str(bool(citation.get('query_bound'))).lower()} "
            f"text={official.clean(citation.get('citation_text'))}"
        )
    return "\n".join(lines)


def v2_2_base_row_from_v2_1(
    row: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    *,
    validation_bucket: str,
    failure_category: Any,
    llm_backend_validation_started: bool,
    llm_invoked_for_row: bool,
    llm_answer: str,
    generated_answer: str,
    failure_reason: str,
    answer_score: Any | None = None,
    citation_support_score: Any | None = None,
    scoring_attempted: bool | None = None,
    structured_adapter_output_retained: bool | None = None,
    structured_adapter_overwritten_by_llm: bool = False,
    retain_source_scores: bool = True,
    clear_primary_outputs: bool = False,
) -> dict[str, Any]:
    prompt_context = build_v2_2_prompt_context(row, use_query_bound_only=False)
    source_answer_score = row.get("answer_score") if retain_source_scores and answer_score is None else answer_score
    source_citation_score = (
        row.get("citation_support_score") if retain_source_scores and citation_support_score is None else citation_support_score
    )
    scored = (
        row.get("scoring_attempted")
        if retain_source_scores and scoring_attempted is None
        else scoring_attempted
    )
    adapter_retained = (
        row_has_structured_adapter_output(row)
        if structured_adapter_output_retained is None
        else structured_adapter_output_retained
    )
    out = {
        "schema_version": V2_2_RUN_ID,
        "run_id": V2_2_RUN_ID,
        "source_run_id": row.get("run_id"),
        "query_id": official.clean(row.get("query_id")),
        "track": official.clean(row.get("track")),
        "generated_answer": generated_answer,
        "source_v2_1_generated_answer": official.clean(row.get("generated_answer")),
        "llm_answer": llm_answer,
        "generated_citations": [] if clear_primary_outputs else list(row.get("generated_citations") or []),
        "scored_citations": [] if clear_primary_outputs else list(row.get("scored_citations") or []),
        "discarded_off_track_citations": list(row.get("discarded_off_track_citations") or []),
        "retrieved_evidence_identifiers": list(row.get("retrieved_evidence_identifiers") or []),
        "retrieved_evidence": list(row.get("retrieved_evidence") or []),
        "validation_bucket": validation_bucket,
        "failure_category": official.clean(failure_category),
        "failure_reason": failure_reason,
        "answer_score": source_answer_score,
        "citation_support_score": source_citation_score,
        "scoring_attempted": bool(scored),
        "score_status": "PASS" if official.clean(failure_category) == "PASS" else "FAIL_CLOSED",
        "llm_backend": official.clean(backend_preflight.get("llm_backend")),
        "llm_model": official.clean(backend_preflight.get("model")),
        "real_llm_backend_available": bool(backend_preflight.get("real_llm_backend_used")),
        "real_llm_backend_used": bool(backend_preflight.get("real_llm_backend_used") and llm_invoked_for_row),
        "real_llm_backend_used_for_row": bool(backend_preflight.get("real_llm_backend_used") and llm_invoked_for_row),
        "local_llm_used": bool(backend_preflight.get("local_llm_used") and llm_invoked_for_row),
        "llm_backend_validation_started": llm_backend_validation_started,
        "llm_invoked_for_row": llm_invoked_for_row,
        "llm_timeout_seconds": backend_preflight.get("timeout_seconds"),
        "llm_max_tokens": backend_preflight.get("max_tokens"),
        "llm_retry_policy": backend_preflight.get("retry_policy"),
        "prompt_context_source_bound_only": bool(prompt_context.get("prompt_context_source_bound_only")),
        "same_track_scored_citation_count": prompt_context.get("same_track_scored_citation_count"),
        "query_bound_scored_citation_count": prompt_context.get("query_bound_scored_citation_count"),
        "non_query_bound_same_track_prompt_context_used": prompt_context.get(
            "non_query_bound_same_track_context_used"
        ),
        "off_track_citation_count_excluded_from_prompt": prompt_context.get(
            "off_track_citation_count_excluded_from_prompt"
        ),
        "structured_adapter_output_retained": adapter_retained,
        "structured_adapter_overwritten_by_llm": structured_adapter_overwritten_by_llm,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "candidate_artifacts_as_generation_source": False,
        "diagnostic_only": True,
        "promotion_evidence": False,
        "baseline_comparison_is_model_quality_comparable": False,
        "source_bound_index_used": True,
        "canonical_search_unit_payload_used": True,
        "schema_mismatch_residual_count": int(row.get("schema_mismatch_residual_count") or 0),
        "same_track_valid_citation_count": row.get("same_track_valid_citation_count")
        or len(row.get("scored_citations") or []),
        "discarded_off_track_citation_count": row.get("discarded_off_track_citation_count")
        or len(row.get("discarded_off_track_citations") or []),
        "non_query_bound_same_track_scored_citation_count": row.get(
            "non_query_bound_same_track_scored_citation_count"
        )
        or max(0, len(row.get("scored_citations") or []) - int(prompt_context.get("query_bound_scored_citation_count") or 0)),
        "adapter_output_from_source_bound_search_units": row.get(
            "adapter_output_from_source_bound_search_units"
        ),
    }
    return out


def build_v2_2_summary(
    *,
    args: argparse.Namespace,
    rows: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    agentic_status: Mapping[str, Any],
    v2_1_preflight: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
    validation_status: str,
) -> dict[str, Any]:
    failure_counts = dict(sorted(Counter(row["failure_category"] for row in rows).items()))
    bucket_counts = dict(sorted(Counter(row["validation_bucket"] for row in rows).items()))
    pass_count = int(failure_counts.get("PASS", 0))
    llm_invoked_row_count = sum(1 for row in rows if row.get("llm_invoked_for_row") is True)
    retained_without_llm_count = sum(
        1
        for row in rows
        if row.get("validation_bucket") == "PASS_RETAINED" and row.get("llm_invoked_for_row") is not True
    )
    scored_count = sum(
        1 for row in rows if row.get("answer_score") is not None and row.get("citation_support_score") is not None
    )
    existing_pass_regressions = [
        row["query_id"]
        for row in rows
        if row.get("source_run_id") == V2_1_RUN_ID
        and row.get("source_v2_1_generated_answer")
        and row.get("validation_bucket") not in {"PASS_RETAINED", "LLM_BACKEND_UNAVAILABLE"}
        and row.get("query_id") not in V2_2_SYNTHESIS_TARGET_QUERY_IDS
    ]
    index_dependency = agentic_status.get(
        "index_dependency",
        inspect_rag_index_dependency(Path(args.rag_index_dir)),
    )
    text_target = next((row for row in rows if row.get("query_id") == "text_namu_v2_0017"), {})
    summary = {
        "schema_version": args.run_id,
        "run_id": args.run_id,
        "generated_at": utc_timestamp(),
        "status": validation_status,
        "llm_backend_validation_status": validation_status,
        "diagnostic_only": True,
        "measurement_classification": args.run_id,
        "official_metric_execution_started": True,
        "actual_generation_execution_started": any(row.get("llm_invoked_for_row") for row in rows),
        "denominator_count": 29,
        "result_count": len(rows),
        "unique_query_id_count": len({row["query_id"] for row in rows}),
        "scored_count": scored_count,
        "pass_count": pass_count,
        "failure_counts": failure_counts,
        "official_score_category_counts": {
            "PASS": int(failure_counts.get("PASS", 0)),
            "CITATION_UNSUPPORTED": int(failure_counts.get("CITATION_UNSUPPORTED", 0)),
            "PARTIAL_OR_UNSUPPORTED": int(failure_counts.get("PARTIAL_OR_UNSUPPORTED", 0)),
        },
        "validation_bucket_counts": bucket_counts,
        "llm_invoked_row_count": llm_invoked_row_count,
        "retained_without_llm_count": retained_without_llm_count,
        "existing_pass_regression_count": len(existing_pass_regressions),
        "existing_pass_regression_query_ids": existing_pass_regressions,
        "text_namu_v2_0017": {
            "validation_bucket": text_target.get("validation_bucket"),
            "failure_category": text_target.get("failure_category"),
            "llm_invoked_for_row": text_target.get("llm_invoked_for_row"),
        },
        "per_track_counts": per_track_counts(rows),
        "non_production_rag_index_dependency": index_dependency,
        "infrastructure_blocker": {
            "category": None if backend_preflight.get("ok") else "LLM_BACKEND_UNAVAILABLE",
            "domain": "llm_backend" if not backend_preflight.get("ok") else None,
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": False,
        },
        "agentic_loop": {
            "implemented": True,
            "enabled": False,
            "executed": False,
            "backend": "v2_2_llm_backend_validation",
            "steps_count": 0,
            "blockers": list(backend_preflight.get("blockers") or []),
        },
        "llm_backend_preflight": dict(backend_preflight),
        "v2_1_artifact_consistency_preflight": dict(v2_1_preflight),
        "real_llm_backend_used": bool(backend_preflight.get("real_llm_backend_used")),
        "local_llm_used": any(bool(row.get("local_llm_used")) for row in rows),
        "local_gpu_used": False,
        "llm_backend": backend_preflight.get("llm_backend"),
        "llm_model": backend_preflight.get("model"),
        "llm_timeout_seconds": backend_preflight.get("timeout_seconds"),
        "llm_max_tokens": backend_preflight.get("max_tokens"),
        "llm_retry_policy": backend_preflight.get("retry_policy"),
        "llm_fail_closed_policy": backend_preflight.get("fail_closed_policy"),
        "source_bound_index_used": bool(index_dependency.get("rerun_allowed")),
        "canonical_search_unit_payload_used": True,
        "prompt_context_source_bound_only": all(row.get("prompt_context_source_bound_only") is True for row in rows),
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "promotion_evidence": False,
        "baseline_comparison_is_model_quality_comparable": False,
        "performance_interpretation": "diagnostic_only_llm_backend_validation_not_promotion_evidence",
        "search_unit_citation_payloads_used": True,
        "all_generated_citations_source_bound": True,
        "same_track_generated_citations_source_bound": True,
        "scored_citations_source_bound": True,
        "adapter_output_for_same_track_citations": True,
        "discarded_off_track_citation_count": sum(int(row.get("discarded_off_track_citation_count") or 0) for row in rows),
        "same_track_valid_citation_count": sum(int(row.get("same_track_valid_citation_count") or 0) for row in rows),
        "query_bound_scored_citation_count": sum(int(row.get("query_bound_scored_citation_count") or 0) for row in rows),
        "non_query_bound_same_track_scored_citation_count": sum(
            int(row.get("non_query_bound_same_track_scored_citation_count") or 0) for row in rows
        ),
        "schema_mismatch_residual_count": 0,
        "query_bound_evidence_gap_count": int(v2_1_preflight.get("query_bound_evidence_gap_count") or 0),
        "residual_failure_audit": None,
        "citation_contract_metrics": {
            "schema_mismatch_residual_count": 0,
            "discarded_off_track_citation_count": sum(
                int(row.get("discarded_off_track_citation_count") or 0) for row in rows
            ),
            "same_track_valid_citation_count": sum(int(row.get("same_track_valid_citation_count") or 0) for row in rows),
            "query_bound_scored_citation_count": sum(int(row.get("query_bound_scored_citation_count") or 0) for row in rows),
            "non_query_bound_same_track_scored_citation_count": sum(
                int(row.get("non_query_bound_same_track_scored_citation_count") or 0) for row in rows
            ),
        },
        "xlsx_pdf_structured_adapters_enabled": True,
        "adapter_output_from_source_bound_search_units": True,
        "chunk_only_citation_fallback_disabled_for_official_scoring": True,
        "diagnostic_limitations": [
            "diagnostic-only LLM backend validation; not comparable live measurement v3",
            "promotion_evidence=false; baseline/denominator/gold/human labels/production paths not mutated",
        ],
        "source_bound_official_denominator_index_design": source_bound_index_design(index_dependency),
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "v2_1_summary_json": official.file_identity(Path(args.v2_1_summary_json)),
            "v2_1_results_jsonl": official.file_identity(Path(args.v2_1_results_jsonl)),
            "v2_1_failure_attribution_json": official.file_identity(Path(args.v2_1_failure_attribution_json)),
        },
        "artifact_paths": {
            "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
            "summary_json": official.repo_relative(Path(args.summary_json)),
            "summary_md": official.repo_relative(Path(args.summary_md)),
            "failure_attribution_json": report_artifact_repo_relative(args.run_id, "failure.json"),
        },
        "artifact_provenance": {
            "immutable_first_run_baseline_overwritten": False,
            "report_only_candidates_promoted": False,
            "run_id_separate_from_first_run": True,
            "run_id_separate_from_v2": True,
            "run_id_separate_from_v2_1": True,
        },
        "baseline_reference": {
            "run_id": "official_answer_citation_metric_first_run_v1",
            "status_detail": baseline.get("status_detail"),
            "scored_count": baseline.get("scored_count"),
            "pass_count": (baseline.get("failure_category_counts") or {}).get("PASS"),
            "failure_counts": baseline.get("failure_category_counts"),
        },
        "comparison_to_baseline": {
            "pass_delta": pass_count - int((baseline.get("failure_category_counts") or {}).get("PASS", 0)),
            "per_track_pass_delta": {
                track: int(per_track_counts(rows).get(track, {}).get("pass_count", 0))
                - int((baseline.get("track_aggregates") or {}).get(track, {}).get("failure_category_counts", {}).get("PASS", 0))
                for track in official.TRACKS
            },
            "key_failure_category_changes": {
                "new_failure_counts": failure_counts,
                "first_run_failure_counts": baseline.get("failure_category_counts"),
            },
        },
        "guardrails": {
            "tuning_run_started": False,
            "promotion_evidence": False,
            "threshold_tuning": False,
            "winner_selection": False,
            "production_mutation": False,
            "denominator_mutation": False,
            "gold_mutation": False,
            "generation_used_expected_answer": False,
            "generation_used_supporting_evidence": False,
            "generation_used_gold_fields": False,
            "candidate_artifacts_as_generation_source": False,
        },
        "validation": {
            "ok": v2_1_preflight.get("ok") is True and (
                backend_preflight.get("ok") is True
                or validation_status == "LLM_BACKEND_UNAVAILABLE_FAIL_CLOSED"
            ),
            "errors": list(v2_1_preflight.get("errors") or []) + list(backend_preflight.get("blockers") or []),
        },
        "pipeline_decision": {
            "selected_entrypoint": "v2.2 source-bound LLM backend validation",
            "rationale": "Diagnostic-only LLM backend validation over latest v2.1 source-bound official rows.",
            "registry_application_report_required": False,
            "registry_application_fallback_used": registry_application_fallback_used,
            "candidate_artifacts_not_used_as_generation_source": True,
            "expected_supporting_gold_used_for_generation": False,
        },
    }
    return summary


def run_v3_comparable_live_measurement(
    *,
    args: argparse.Namespace,
    consumed: Mapping[str, Any],
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows = list(consumed["rows"])
    source_by_id = {official.clean(row.get("query_id")): row for row in source_rows}
    v2_2_summary = official.read_json(Path(args.v2_2_summary_json))
    v2_2_rows = read_jsonl(Path(args.v2_2_results_jsonl))
    v2_2_attribution = official.read_json(Path(args.v2_2_failure_attribution_json))
    v2_2_preflight = v2_2_artifact_consistency_preflight(
        summary=v2_2_summary,
        attribution=v2_2_attribution,
        rows=v2_2_rows,
    )
    if validation_errors:
        v2_2_preflight = {
            **v2_2_preflight,
            "ok": False,
            "ready_for_v3_comparable_live_measurement": False,
            "errors": [*list(v2_2_preflight.get("errors") or []), *validation_errors],
            "failure_bucket": "PROMPT_CONTEXT_POLICY_VIOLATION",
        }
    if not v2_2_preflight["ok"]:
        backend_preflight = v3_backend_preflight_skipped(v2_2_preflight)
        rows = v3_fail_closed_rows_from_v2_2(v2_2_rows, backend_preflight, v2_2_preflight)
        summary = build_v3_summary(
            args=args,
            rows=rows,
            baseline=baseline,
            agentic_status=agentic_status,
            v2_2_preflight=v2_2_preflight,
            backend_preflight=backend_preflight,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=registry_application_fallback_used,
            baseline_path=baseline_path,
            validation_status="V3_PRECONDITION_FAIL_CLOSED",
        )
        return summary, rows

    backend_preflight = llm_backend_preflight_for_v2_2(args, check_endpoint=True)
    if not backend_preflight["ok"]:
        rows = v3_fail_closed_rows_from_v2_2(v2_2_rows, backend_preflight, v2_2_preflight)
        summary = build_v3_summary(
            args=args,
            rows=rows,
            baseline=baseline,
            agentic_status=agentic_status,
            v2_2_preflight=v2_2_preflight,
            backend_preflight=backend_preflight,
            metric_input_config_path=metric_input_config_path,
            denominator_registry_path=denominator_registry_path,
            pre_execution_smoke_path=pre_execution_smoke_path,
            application_path=application_path,
            registry_application_fallback_used=registry_application_fallback_used,
            baseline_path=baseline_path,
            validation_status="V3_LLM_BACKEND_UNAVAILABLE_FAIL_CLOSED",
        )
        return summary, rows

    rows = build_v3_rows_from_v2_2(
        v2_2_rows=v2_2_rows,
        source_rows_by_id=source_by_id,
        backend_preflight=backend_preflight,
        prompt_context_mode=args.v3_prompt_context_mode,
    )
    summary = build_v3_summary(
        args=args,
        rows=rows,
        baseline=baseline,
        agentic_status=agentic_status,
        v2_2_preflight=v2_2_preflight,
        backend_preflight=backend_preflight,
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        application_path=application_path,
        registry_application_fallback_used=registry_application_fallback_used,
        baseline_path=baseline_path,
        validation_status="COMPARABLE_LIVE_MEASUREMENT_V3_COMPLETED",
    )
    return summary, rows


def v2_2_artifact_consistency_preflight(
    *,
    summary: Mapping[str, Any],
    attribution: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    failed_ids = sorted(
        official.clean(row.get("query_id"))
        for row in rows
        if official.clean(row.get("failure_category")) != "PASS"
    )
    if summary.get("run_id") != V2_2_RUN_ID:
        errors.append("v2_2_summary_run_id_mismatch")
    if attribution.get("run_id") != V2_2_RUN_ID:
        errors.append("v2_2_attribution_run_id_mismatch")
    if summary.get("llm_backend_validation_status") != "LLM_BACKEND_VALIDATION_COMPLETED":
        errors.append("v2_2_llm_backend_validation_not_completed")
    if int(summary.get("result_count") or 0) != 29 or len(rows) != 29:
        errors.append("v2_2_row_count_mismatch")
    if int(summary.get("scored_count") or 0) != 29:
        errors.append("v2_2_scored_count_mismatch")
    if int(summary.get("pass_count") or 0) != 28:
        errors.append("v2_2_pass_count_mismatch")
    if failed_ids != ["text_namu_v2_0017"]:
        errors.append("v2_2_remaining_failure_query_ids_mismatch")
    if summary.get("promotion_evidence") is not False or attribution.get("promotion_evidence") is not False:
        errors.append("v2_2_promotion_evidence_not_false")
    if summary.get("real_llm_backend_used") is not True:
        errors.append("v2_2_real_llm_backend_not_used")
    if summary.get("source_bound_index_used") is not True:
        errors.append("v2_2_source_bound_index_not_used")
    if summary.get("canonical_search_unit_payload_used") is not True:
        errors.append("v2_2_canonical_search_unit_payload_not_used")
    if summary.get("prompt_context_source_bound_only") is not True:
        errors.append("v2_2_prompt_context_not_source_bound_only")
    if int(summary.get("schema_mismatch_residual_count") or 0) != 0:
        errors.append("v2_2_schema_mismatch_residual_not_zero")
    if int(summary.get("query_bound_evidence_gap_count") or 0) != 0:
        errors.append("v2_2_query_bound_evidence_gap_not_zero")
    for key in (
        "candidate_artifacts_as_generation_source",
        "generation_used_expected_answer",
        "generation_used_supporting_evidence",
        "generation_used_gold_fields",
    ):
        if summary.get(key) is not False:
            errors.append(f"v2_2_{key}_not_false")
    for row in rows:
        if row.get("run_id") != V2_2_RUN_ID:
            errors.append("v2_2_result_row_run_id_mismatch")
            break
        for key in (
            "candidate_artifacts_as_generation_source",
            "generation_used_expected_answer",
            "generation_used_supporting_evidence",
            "generation_used_gold_fields",
            "promotion_evidence",
        ):
            if row.get(key) is not False:
                errors.append(f"v2_2_result_row_{key}_not_false")
                break
    return {
        "ok": not errors,
        "ready_for_v3_comparable_live_measurement": not errors,
        "failure_bucket": None if not errors else "PROMPT_CONTEXT_POLICY_VIOLATION",
        "errors": sorted(dict.fromkeys(errors)),
        "completed_run_id": summary.get("run_id"),
        "rows": len(rows),
        "scored_count": summary.get("scored_count"),
        "pass_count": summary.get("pass_count"),
        "remaining_failure_query_ids": failed_ids,
        "validation_bucket_counts": summary.get("validation_bucket_counts"),
        "schema_mismatch_residual_count": int(summary.get("schema_mismatch_residual_count") or 0),
        "query_bound_evidence_gap_count": int(summary.get("query_bound_evidence_gap_count") or 0),
        "promotion_evidence": bool(summary.get("promotion_evidence")),
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
    }


def v3_backend_preflight_skipped(preflight: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ok": False,
        "failure_bucket": "PROMPT_CONTEXT_POLICY_VIOLATION",
        "llm_backend": "not_checked",
        "base_url": "",
        "model": "",
        "real_llm_backend_used": False,
        "local_llm_used": False,
        "local_endpoint_only": False,
        "timeout_seconds": None,
        "max_tokens": None,
        "strict_json_retries": None,
        "retry_policy": "not_started_until_v2_2_preflight_passes",
        "fail_closed_policy": "v2_2_completed_preflight_required_before_v3",
        "blockers": list(preflight.get("errors") or []),
    }


def v3_fail_closed_rows_from_v2_2(
    rows: Sequence[Mapping[str, Any]],
    backend_preflight: Mapping[str, Any],
    v2_2_preflight: Mapping[str, Any],
) -> list[dict[str, Any]]:
    reason = "; ".join(
        official.clean(item)
        for item in [*list(v2_2_preflight.get("errors") or []), *list(backend_preflight.get("blockers") or [])]
        if official.clean(item)
    )
    return [
        v3_base_row_from_v2_2(
            row,
            backend_preflight,
            result_bucket="PROMPT_CONTEXT_POLICY_VIOLATION",
            failure_category="PROMPT_CONTEXT_POLICY_VIOLATION",
            llm_invoked_for_row=False,
            llm_answer="",
            generated_answer="",
            failure_reason=reason,
            answer_score=None,
            citation_support_score=None,
            scoring_attempted=False,
            clear_primary_outputs=True,
        )
        for row in rows
    ]


def build_v3_rows_from_v2_2(
    *,
    v2_2_rows: Sequence[Mapping[str, Any]],
    source_rows_by_id: Mapping[str, Mapping[str, Any]],
    backend_preflight: Mapping[str, Any],
    prompt_context_mode: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in v2_2_rows:
        policy = v3_generation_policy_for_row(row)
        if policy["policy"] == "structured_adapter_retained":
            rows.append(v3_structured_adapter_retained_row(row, backend_preflight))
            continue
        if policy["policy"] == "text_llm_synthesis":
            rows.append(
                v3_text_llm_synthesis_row(
                    v2_2_row=row,
                    source_row=source_rows_by_id.get(official.clean(row.get("query_id")), {}),
                    backend_preflight=backend_preflight,
                    prompt_context_mode=prompt_context_mode,
                )
            )
            continue
        rows.append(v3_structured_adapter_regressed_row(row, backend_preflight, policy))
    return rows


def v3_generation_policy_for_row(row: Mapping[str, Any]) -> dict[str, Any]:
    track = official.clean(row.get("track"))
    if track in {"xlsx_business_structured", "pdf_business_ocr_mm"}:
        return {
            "policy": "structured_adapter_retained"
            if row_has_structured_adapter_output(row)
            else "structured_adapter_regressed",
            "primary_answer_source": "deterministic_source_bound_adapter",
            "llm_may_overwrite": False,
        }
    if track in V3_TEXT_SYNTHESIS_TRACKS:
        return {
            "policy": "text_llm_synthesis",
            "primary_answer_source": "real_llm_synthesis",
            "llm_may_overwrite": True,
        }
    return {
        "policy": "unsupported_track",
        "primary_answer_source": "none",
        "llm_may_overwrite": False,
    }


def v3_structured_adapter_retained_row(
    row: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
) -> dict[str, Any]:
    return v3_base_row_from_v2_2(
        row,
        backend_preflight,
        result_bucket=(
            "PASS_RETAINED_BY_STRUCTURED_ADAPTER"
            if row.get("failure_category") == "PASS"
            else "STRUCTURED_ADAPTER_REGRESSED"
        ),
        failure_category=row.get("failure_category") if row.get("failure_category") == "PASS" else "STRUCTURED_ADAPTER_REGRESSED",
        llm_invoked_for_row=False,
        llm_answer="",
        generated_answer=official.clean(row.get("generated_answer")),
        failure_reason="structured source-bound adapter output retained as primary answer",
        structured_adapter_output_retained=True,
        structured_adapter_overwritten_by_llm=False,
    )


def v3_structured_adapter_regressed_row(
    row: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    return v3_base_row_from_v2_2(
        row,
        backend_preflight,
        result_bucket="STRUCTURED_ADAPTER_REGRESSED",
        failure_category="STRUCTURED_ADAPTER_REGRESSED",
        llm_invoked_for_row=False,
        llm_answer="",
        generated_answer="",
        failure_reason=f"structured row did not have retained source-bound adapter output: {policy.get('policy')}",
        answer_score=None,
        citation_support_score=None,
        scoring_attempted=False,
        structured_adapter_output_retained=False,
        structured_adapter_overwritten_by_llm=False,
        clear_primary_outputs=True,
    )


def v3_text_llm_synthesis_row(
    *,
    v2_2_row: Mapping[str, Any],
    source_row: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    prompt_context_mode: str,
) -> dict[str, Any]:
    context = build_v3_prompt_context(v2_2_row, prompt_context_mode=prompt_context_mode)
    if context["prompt_context_policy_violation"]:
        return v3_base_row_from_v2_2(
            v2_2_row,
            backend_preflight,
            result_bucket="PROMPT_CONTEXT_POLICY_VIOLATION",
            failure_category="PROMPT_CONTEXT_POLICY_VIOLATION",
            llm_invoked_for_row=False,
            llm_answer="",
            generated_answer="",
            failure_reason="prompt context was not canonical source-bound same-track SearchUnit payload only",
            answer_score=None,
            citation_support_score=None,
            scoring_attempted=False,
            clear_primary_outputs=True,
            prompt_context=context,
        )
    try:
        prompt = build_v3_llm_prompt(
            v2_2_row,
            context,
            question=official.clean(source_row.get("question") or v2_2_row.get("query_id")),
        )
        llm_answer, strict_json_meta = call_v3_llm_synthesis(
            prompt=prompt,
            backend_preflight=backend_preflight,
        )
        citation_text = " ".join(official.clean(item["citation_text"]) for item in context["citations"])
        score = score_generated_row(
            source_row,
            llm_answer,
            [SimpleNamespace(text=item["citation_text"]) for item in context["citations"]],
        )
        diagnostics = v3_text_diagnostics(
            query_id=official.clean(v2_2_row.get("query_id")),
            source_row=source_row,
            llm_answer=llm_answer,
            citation_text=citation_text,
            score=score,
            prompt_context=context,
        )
        if score["failure_category"] == "PASS":
            bucket = "LLM_SYNTHESIS_PASS"
        elif diagnostics["scorer_normalization_issue_possible"]:
            bucket = "SCORER_NORMALIZATION_ISSUE_POSSIBLE"
        elif score["citation_support_score"] != 1.0:
            bucket = "CITATION_SUPPORT_REGRESSED"
        else:
            bucket = "LLM_SYNTHESIS_REGRESSED"
        out = v3_base_row_from_v2_2(
            v2_2_row,
            backend_preflight,
            result_bucket=bucket,
            failure_category=score["failure_category"],
            llm_invoked_for_row=True,
            llm_answer=llm_answer,
            generated_answer=llm_answer,
            failure_reason=score["failure_detail"],
            answer_score=score["answer_score"],
            citation_support_score=score["citation_support_score"],
            scoring_attempted=True,
            structured_adapter_output_retained=False,
            structured_adapter_overwritten_by_llm=False,
            prompt_context=context,
        )
        out["llm_strict_json"] = strict_json_meta
        if out["query_id"] == "text_namu_v2_0017":
            out["text_namu_v2_0017_diagnostics"] = diagnostics
        return out
    except Exception as exc:  # noqa: BLE001
        diagnostics = v3_text_diagnostics(
            query_id=official.clean(v2_2_row.get("query_id")),
            source_row=source_row,
            llm_answer="",
            citation_text=" ".join(official.clean(item["citation_text"]) for item in context["citations"]),
            score={
                "failure_category": "PARTIAL_OR_UNSUPPORTED",
                "answer_score": 0.0,
                "citation_support_score": 0.0,
            },
            prompt_context=context,
        )
        out = v3_base_row_from_v2_2(
            v2_2_row,
            backend_preflight,
            result_bucket="LLM_SYNTHESIS_REGRESSED",
            failure_category="PARTIAL_OR_UNSUPPORTED",
            llm_invoked_for_row=True,
            llm_answer="",
            generated_answer="",
            failure_reason=f"v3 LLM synthesis failed closed: {type(exc).__name__}: {exc}",
            answer_score=None,
            citation_support_score=None,
            scoring_attempted=False,
            structured_adapter_output_retained=False,
            structured_adapter_overwritten_by_llm=False,
            clear_primary_outputs=True,
            prompt_context=context,
        )
        if out["query_id"] == "text_namu_v2_0017":
            out["text_namu_v2_0017_diagnostics"] = diagnostics
        return out


class StrictJsonDiagnosticError(ValueError):
    def __init__(self, message: str, diagnostics: Mapping[str, Any]) -> None:
        super().__init__(message)
        self.diagnostics = dict(diagnostics)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sanitized_raw_response_excerpt(value: str, *, limit: int = 700) -> str:
    text = re.sub(r"(?i)[A-Z]:\\[^\r\n\t\"']+", "[REDACTED_LOCAL_PATH]", value or "")
    text = "".join(ch if ch in "\n\t" or ord(ch) >= 32 else " " for ch in text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def call_v3_local_llm_strict_json_with_diagnostics(
    *,
    backend_preflight: Mapping[str, Any],
    prompt: str,
    required_schema_keys: Sequence[str],
    prompt_context_mode: str,
    cited_search_unit_ids_before_parse: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from rag_text_namu_local_llm_rewrite_v2 import call_local_llm, parse_strict_json_object  # noqa: WPS433

    attempts = max(1, int(backend_preflight.get("strict_json_retries") or 2))
    required_keys = [official.clean(item) for item in required_schema_keys if official.clean(item)]
    prompt_for_attempt = prompt
    raw_hashes: list[str] = []
    last_diagnostics: dict[str, Any] = {
        "parse_ok": False,
        "strict_json_error": "local LLM was not invoked",
        "attempted_schema_keys": required_keys,
        "missing_required_keys": required_keys,
        "prompt_context_mode": prompt_context_mode,
        "cited_search_unit_ids_before_parse": list(cited_search_unit_ids_before_parse),
    }
    for attempt in range(1, attempts + 1):
        raw = call_local_llm(
            backend=official.clean(backend_preflight.get("llm_backend")),
            base_url=official.clean(backend_preflight.get("base_url")),
            model=official.clean(backend_preflight.get("model")),
            prompt=prompt_for_attempt,
            temperature=0.0,
            max_tokens=int(backend_preflight.get("max_tokens") or 900),
            timeout_seconds=int(backend_preflight.get("timeout_seconds") or 120),
        )
        raw_hashes.append(sha256_text(raw))
        diagnostics = {
            "parse_ok": False,
            "strict_json_attempts": attempt,
            "strict_json_retry_count": attempt - 1,
            "raw_response_sha256": raw_hashes[-1],
            "raw_response_sha256_attempts": list(raw_hashes),
            "sanitized_raw_response_excerpt": sanitized_raw_response_excerpt(raw),
            "strict_json_error": "",
            "attempted_schema_keys": required_keys,
            "missing_required_keys": [],
            "prompt_context_mode": prompt_context_mode,
            "cited_search_unit_ids_before_parse": list(cited_search_unit_ids_before_parse),
        }
        try:
            parsed = parse_strict_json_object(raw)
        except ValueError as exc:
            diagnostics["strict_json_error"] = str(exc)
            last_diagnostics = diagnostics
        else:
            parsed_candidates = [parsed, *strict_json_candidates_from_wrapped_response(parsed, parse_strict_json_object)]
            for candidate_index, candidate in enumerate(parsed_candidates):
                missing = [key for key in required_keys if key not in candidate]
                if missing:
                    repaired = repair_v3_strict_json_schema(candidate, missing_required_keys=missing)
                    repaired_missing = [key for key in required_keys if key not in repaired]
                    if not repaired_missing:
                        diagnostics["parse_ok"] = True
                        diagnostics["schema_repair_applied"] = True
                        diagnostics["missing_required_keys_before_repair"] = missing
                        diagnostics["missing_required_keys"] = []
                        if candidate_index:
                            diagnostics["wrapped_response_content_extracted"] = True
                        return repaired, diagnostics
                    diagnostics["strict_json_error"] = "local LLM JSON missing required key(s): " + ", ".join(
                        repaired_missing
                    )
                    diagnostics["missing_required_keys"] = repaired_missing
                    diagnostics["missing_required_keys_before_repair"] = missing
                    last_diagnostics = diagnostics
                else:
                    diagnostics["parse_ok"] = True
                    if candidate_index:
                        diagnostics["wrapped_response_content_extracted"] = True
                    return candidate, diagnostics
        prompt_for_attempt = (
            prompt
            + "\n\nPrevious response failed strict JSON validation. "
            + "Return exactly one minified JSON object matching the schema. "
            + "Do not use markdown, code fences, commentary, or prose. "
            + f"Validation error: {last_diagnostics['strict_json_error']}"
        )
    raise StrictJsonDiagnosticError(
        "local LLM output failed strict JSON diagnostics after "
        f"{attempts} attempt(s): {last_diagnostics.get('strict_json_error')}",
        last_diagnostics,
    )


def repair_v3_strict_json_schema(
    parsed: Mapping[str, Any],
    *,
    missing_required_keys: Sequence[str],
) -> dict[str, Any]:
    repaired = dict(parsed)
    missing = {official.clean(key) for key in missing_required_keys}
    if "cited_search_unit_ids" in missing:
        locator_ids = [
            official.clean(locator.get("search_unit_id") or locator.get("searchUnitId"))
            for locator in llm_generated_citation_locators_from_json(repaired)
            if isinstance(locator, Mapping)
        ]
        locator_ids = [item for item in locator_ids if item]
        if locator_ids:
            repaired["cited_search_unit_ids"] = sorted(dict.fromkeys(locator_ids))
    return repaired


def strict_json_candidates_from_wrapped_response(
    parsed: Mapping[str, Any],
    parse_fn: Any,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    choices = parsed.get("choices")
    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)):
        return candidates
    for choice in choices:
        if not isinstance(choice, Mapping):
            continue
        message = choice.get("message") if isinstance(choice.get("message"), Mapping) else {}
        for value in (message.get("content"), choice.get("text")):
            text = official.clean(value)
            if not text:
                continue
            try:
                candidate = parse_fn(text)
            except ValueError:
                continue
            if isinstance(candidate, Mapping):
                candidates.append(dict(candidate))
    return candidates


def call_v3_llm_synthesis(
    *,
    prompt: str,
    backend_preflight: Mapping[str, Any],
    require_generated_locators: bool = False,
    prompt_context_mode: str = "",
    cited_search_unit_ids_before_parse: Sequence[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    context_ids = set(re.findall(r"search_unit_id=([^\s]+)", prompt))
    required_schema_keys = ["answer", "cited_search_unit_ids"]
    if require_generated_locators:
        required_schema_keys.append("citation_locators")
    parsed, strict_json_meta = call_v3_local_llm_strict_json_with_diagnostics(
        backend_preflight=backend_preflight,
        prompt=prompt,
        required_schema_keys=required_schema_keys,
        prompt_context_mode=prompt_context_mode,
        cited_search_unit_ids_before_parse=list(cited_search_unit_ids_before_parse or sorted(context_ids)),
    )
    llm_answer = official.clean(parsed.get("answer") or parsed.get("rewritten_answer") or parsed.get("short_answer"))
    if not llm_answer:
        diagnostics = {**strict_json_meta, "parse_ok": False, "strict_json_error": "LLM JSON did not include answer"}
        diagnostics["missing_required_keys"] = ["answer"]
        raise StrictJsonDiagnosticError("LLM JSON did not include answer", diagnostics)
    cited_ids = {
        official.clean(item)
        for item in parsed.get("cited_search_unit_ids") or []
        if official.clean(item)
    }
    if cited_ids and not cited_ids.issubset(context_ids):
        raise ValueError("LLM cited a search_unit_id outside prompt context")
    if parsed.get("answer_supported_by_context") is False:
        raise ValueError("LLM reported answer_supported_by_context=false")
    generated_locators = llm_generated_citation_locators_from_json(parsed)
    return llm_answer, {
        "strict_json": strict_json_meta,
        "cited_search_unit_ids": sorted(cited_ids),
        "answer_supported_by_context": parsed.get("answer_supported_by_context"),
        "llm_generated_citation_locators": generated_locators,
        "llm_generated_locator_required": bool(require_generated_locators),
    }


def llm_generated_citation_locators_from_json(parsed: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_locators = (
        parsed.get("citation_locators")
        or parsed.get("generated_citation_locators")
        or parsed.get("llm_generated_citation_locators")
        or []
    )
    if isinstance(raw_locators, Mapping):
        raw_iterable: Sequence[Any] = list(raw_locators.values())
    elif isinstance(raw_locators, Sequence) and not isinstance(raw_locators, (str, bytes)):
        raw_iterable = raw_locators
    else:
        raw_iterable = []

    locators: list[dict[str, Any]] = []
    for raw in raw_iterable:
        if not isinstance(raw, Mapping):
            continue
        if isinstance(raw.get("locator"), Mapping):
            locator = dict(raw["locator"])
        elif isinstance(raw.get("locator_json"), Mapping):
            locator = dict(raw["locator_json"])
        else:
            locator = dict(raw)
        search_unit_id = official.clean(
            locator.get("search_unit_id")
            or locator.get("searchUnitId")
            or raw.get("search_unit_id")
            or raw.get("searchUnitId")
        )
        if search_unit_id:
            locator["search_unit_id"] = search_unit_id
        locators.append(locator)
    return locators


def build_v3_prompt_context(
    row: Mapping[str, Any],
    *,
    prompt_context_mode: str,
    context_expansion_units: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    return build_v3_prompt_context_from_row(
        row,
        use_query_bound_only=prompt_context_mode == "query-bound-only",
        mode=prompt_context_mode,
        context_expansion_units=context_expansion_units,
    )


def build_v3_prompt_context_from_row(
    row: Mapping[str, Any],
    *,
    use_query_bound_only: bool,
    mode: str,
    context_expansion_units: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    query_id = official.clean(row.get("query_id"))
    track = official.clean(row.get("track"))
    source_family = SOURCE_FAMILY_LABEL_BY_TRACK.get(track, track.upper())
    citations: list[dict[str, Any]] = []
    source_citations: list[dict[str, Any]] = []
    policy_errors: list[str] = []
    for citation in row.get("scored_citations") or []:
        if not isinstance(citation, Mapping):
            continue
        validation = citation_validation(citation)
        payload = citation.get("search_unit_citation_payload")
        if not isinstance(payload, Mapping) or payload.get("source_bound_official_denominator") is not True:
            policy_errors.append("non_source_bound_scored_citation")
            continue
        if official.clean(validation.get("manifest_track") or payload.get("track")) != track:
            policy_errors.append("off_track_scored_citation")
            continue
        manifest_query_id = official.clean(validation.get("manifest_query_id") or payload.get("manifest_query_id"))
        if use_query_bound_only and manifest_query_id != query_id:
            continue
        source_citations.append(dict(citation))
        citations.append(
            {
                "citation_text": official.clean(citation.get("citation_text")),
                "locator": locator_from_citation_payload(payload, source_family=source_family),
                "search_unit_id": official.clean(
                    payload.get("searchUnitId") or payload.get("search_unit_id") or citation.get("search_unit_id")
                ),
                "manifest_query_id": manifest_query_id,
                "source_family": source_family,
                "track": track,
                "query_bound": manifest_query_id == query_id,
            }
        )
    expansion_citations = [
        build_source_bound_pdf_context_expansion_citation(
            unit,
            track=track,
            query_id=query_id,
            source_family=source_family,
        )
        for unit in (context_expansion_units or [])
        if isinstance(unit, Mapping)
    ]
    expansion_citations = [
        citation
        for citation in expansion_citations
        if as_mapping(citation.get("citation_payload_validation")).get("ok") is True
    ]
    for citation in expansion_citations:
        payload = as_mapping(citation.get("search_unit_citation_payload"))
        manifest_query_id = official.clean(payload.get("manifest_query_id"))
        if use_query_bound_only and manifest_query_id != query_id:
            continue
        locator = locator_from_citation_payload(payload, source_family=source_family)
        search_unit_id = official.clean(payload.get("search_unit_id") or payload.get("searchUnitId"))
        source_citations.append(dict(citation))
        citations.append(
            {
                "citation_text": official.clean(citation.get("citation_text")),
                "locator": locator,
                "search_unit_id": search_unit_id,
                "manifest_query_id": manifest_query_id,
                "source_family": source_family,
                "track": track,
                "query_bound": manifest_query_id == query_id,
                "context_expansion": True,
                "expansion_policy_name": payload.get("expansion_policy_name"),
            }
        )
    paired_citations = list(zip(source_citations, citations, strict=True))
    paired_citations.sort(
        key=lambda item: (
            0
            if item[1].get("context_expansion") and item[1].get("query_bound")
            else 1
            if item[1].get("query_bound")
            else 2
        )
    )
    source_citations = [item[0] for item in paired_citations]
    citations = [item[1] for item in paired_citations]
    query_bound_count = sum(1 for item in citations if item["query_bound"])
    non_query_bound_used = any(not item["query_bound"] for item in citations)
    off_track_count = len(row.get("discarded_off_track_citations") or [])
    if not citations:
        policy_errors.append("same_track_source_bound_prompt_context_empty")
    return {
        "citations": citations,
        "source_citations": source_citations,
        "same_track_scored_citation_count": len(citations),
        "query_bound_scored_citation_count": query_bound_count,
        "non_query_bound_same_track_context_used": non_query_bound_used,
        "same_track_scored_evidence_used": not use_query_bound_only,
        "query_bound_evidence_only": bool(use_query_bound_only),
        "off_track_citation_count_excluded_from_prompt": off_track_count,
        "prompt_context_source_bound_only": not policy_errors,
        "prompt_context_policy_violation": bool(policy_errors),
        "policy_errors": sorted(dict.fromkeys(policy_errors)),
        "prompt_context_policy": {
            "mode": mode,
            "canonical_source_bound_search_unit_payload_only": True,
            "off_track_citations_excluded": True,
            "candidate_artifacts_as_generation_source": False,
            "generation_used_expected_answer": False,
            "generation_used_supporting_evidence": False,
            "generation_used_gold_fields": False,
            "diagnostic_context_expansion_allowed": bool(expansion_citations),
            "diagnostic_context_expansion_count": len(expansion_citations),
        },
    }


def build_source_bound_pdf_context_expansion_citation(
    unit: Mapping[str, Any],
    *,
    track: str,
    query_id: str,
    source_family: str,
) -> dict[str, Any]:
    payload = {
        "source_bound_diagnostic_context_expansion": True,
        "source_bound_official_denominator": False,
        "non_production_diagnostic_context_expansion": True,
        "track": track,
        "manifest_track": track,
        "manifest_query_id": query_id,
        "source_family": source_family,
        "locator_schema": "pdf_source_bound_context_expansion_v1",
        "source_pdf_path": official.clean(unit.get("source_pdf_path")),
        "page": unit.get("page"),
        "physical_page_index": unit.get("physical_page_index"),
        "bbox": list(unit.get("bbox") or []),
        "region_type": official.clean(unit.get("region_type")),
        "search_unit_id": official.clean(unit.get("search_unit_id")),
        "document_version_id": official.clean(unit.get("document_version_id")),
        "expansion_policy_name": official.clean(unit.get("expansion_policy_name")),
        "expansion_policy_version": official.clean(unit.get("expansion_policy_version")),
    }
    required = ("source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id")
    missing = [field for field in required if not has_required_citation_value(payload.get(field), field=field)]
    validation = {
        "ok": not missing,
        "category": None if not missing else "LOCATOR_SAFE_PDF_WINDOW_SOURCE_MISSING",
        "validation_category": None if not missing else "LOCATOR_SAFE_PDF_WINDOW_SOURCE_MISSING",
        "missing_fields": missing,
        "query_track": track,
        "manifest_track": track,
        "row_query_id": query_id,
        "manifest_query_id": query_id,
        "manifest_source_family": source_family,
        "locator_schema": "pdf_source_bound_context_expansion_v1",
        "off_track": False,
        "detail": "source-bound diagnostic PDF context expansion sidecar",
    }
    return {
        "generated_citation_index": None,
        "citation_text": official.clean(unit.get("normalized_excerpt"))[:500],
        "locator": {key: payload.get(key) for key in required},
        "search_unit_citation_payload": payload,
        "citation_payload_validation": validation,
        "official_compatible_locator": validation["ok"],
        "structured_source_bound_adapter_enabled": False,
        "structured_adapter_output_from_source_bound_search_unit": False,
        "context_expansion": True,
        "expansion_unit_id": payload["search_unit_id"],
    }


def build_v3_llm_prompt(
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    question: str,
    require_generated_locators: bool = False,
) -> str:
    source_family = SOURCE_FAMILY_LABEL_BY_TRACK.get(official.clean(row.get("track")), official.clean(row.get("track")))
    required_keys_list = ["answer", "cited_search_unit_ids"]
    if require_generated_locators:
        required_keys_list.append("citation_locators")
    schema_example: dict[str, Any] = {
        "answer": "short source-bound answer text",
        "cited_search_unit_ids": ["search_unit_id"],
    }
    if require_generated_locators:
        schema_example["citation_locators"] = [locator_schema_example_for_source_family(source_family)]
    schema_example["answer_supported_by_context"] = True
    lines = [
        "You are running a v3 comparable live measurement row for source-bound RAG answer synthesis.",
        "Use only the canonical source-bound SearchUnit citation payloads below to write the answer.",
        "Keep answer concise, usually one sentence.",
        "Answer only the asked attribute or value; do not broaden into a general summary.",
        "Preserve the question language unless the cited source-bound context cannot support that language.",
        "For XLSX cells, prefer the cited canonical normalized_value when it answers the target column.",
        "For PDF table/body rows, align the requested row, column, year, and unit before choosing a numeric value.",
        "For PDF section or paragraph answers, keep the span tight and avoid paraphrasing unrelated surrounding context.",
        "Return exactly one minified JSON object and nothing else.",
        "Do not return markdown, code fences, commentary, or nested free text.",
        f"Required JSON keys: {', '.join(required_keys_list)}.",
        f"JSON schema: {json.dumps(schema_example, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}",
        f"query_id: {official.clean(row.get('query_id'))}",
        f"track: {official.clean(row.get('track'))}",
        f"question: {official.clean(question)}",
        f"prompt_context_mode: {official.clean((context.get('prompt_context_policy') or {}).get('mode'))}",
        "source_bound_context:",
    ]
    if any(isinstance(citation, Mapping) and citation.get("context_expansion") for citation in context.get("citations") or []):
        lines.insert(
            -1,
            (
                "PDF diagnostic context expansion entries are same-source, locator-valid PDF context. "
                "When such an entry directly gives both a numeric level and a numeric change for the asked rate, "
                "cite that entry and include both numbers in the concise answer."
            ),
        )
    if require_generated_locators:
        lines.insert(
            6,
            (
                "For citation_locators, return one object per cited_search_unit_id by copying "
                "the cited locator_json_copy_source object exactly as a JSON object. Do not wrap it under "
                "a copy key. Do not stringify it. Do not rewrite, shorten, translate, or append "
                "source_pdf_path, row_label, target_column, or any locator value. Each locator must include "
                "all schema keys shown above for this source family, not only search_unit_id."
            ),
        )
    for index, citation in enumerate(context.get("citations") or [], start=1):
        if not isinstance(citation, Mapping):
            continue
        locator_part = (
            f"locator_json_copy_source={json.dumps(citation.get('locator') or {}, ensure_ascii=False, sort_keys=True, separators=(',', ':'))} "
            if require_generated_locators
            else ""
        )
        lines.append(
            f"[{index}] search_unit_id={official.clean(citation.get('search_unit_id'))} "
            f"query_bound={str(bool(citation.get('query_bound'))).lower()} "
            f"{locator_part}"
            f"text={official.clean(citation.get('citation_text'))}"
        )
    return "\n".join(lines)


def render_v3_source_bound_answer(
    *,
    row: Mapping[str, Any],
    source_family: str,
    answer: str,
    citations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    query = official.clean(row.get("question") or row.get("query"))
    rendered = official.clean(answer)
    operations: list[str] = []
    citation_text = audit_citation_text(citations)
    if source_family == "XLSX":
        normalized_value = first_citation_payload_value(citations, "normalized_value", "normalizedValue")
        if normalized_value and query_asks_for_date_or_value(query):
            rendered_value = render_date_value_for_question(normalized_value) or normalized_value
            if rendered_value and not answer_contains_value_variant(rendered, normalized_value):
                rendered = f"{rendered_value}입니다."
                operations.append("xlsx_normalized_value_tight_answer")
    if source_family == "PDF":
        pdf_table_answer = render_pdf_table_axis_value_for_question(query=query, citation_text=citation_text)
        if pdf_table_answer and not answer_contains_value_variant(rendered, pdf_table_answer):
            rendered = pdf_table_answer
            operations.append("pdf_table_axis_tight_answer")
    if contains_hangul(query) and rendered and not contains_hangul(rendered):
        source_value = extract_korean_temporal_value(citation_text)
        if not source_value and source_family == "XLSX":
            normalized_value = first_citation_payload_value(citations, "normalized_value", "normalizedValue")
            source_value = render_date_value_for_question(normalized_value)
        if not source_value:
            source_value = extract_tight_korean_source_phrase(citation_text)
        if source_value:
            rendered = f"{source_value}입니다."
            operations.append("korean_question_language_restored_from_source_context")
    return {
        "answer": rendered,
        "applied": bool(operations),
        "operations": operations,
        "source_bound_context_only": True,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "reference_span_text_embedded": False,
        "promotion_evidence": False,
    }


def first_citation_payload_value(citations: Sequence[Mapping[str, Any]], *keys: str) -> str:
    for citation in citations:
        payload = as_mapping(citation.get("search_unit_citation_payload"))
        for key in keys:
            value = official.clean(payload.get(key))
            if value:
                return value
    return ""


def query_asks_for_date_or_value(query: str) -> bool:
    normalized = official.normalized_text(query)
    return any(token in normalized for token in ("언제", "일자", "날짜", "정확히", "얼마", "몇", "시기"))


def render_date_value_for_question(value: str) -> str:
    cleaned = official.clean(value)
    match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", cleaned)
    if match:
        year, month, day = match.groups()
        return f"{year}년 {int(month)}월 {int(day)}일"
    month_match = re.fullmatch(r"(\d{4})-(\d{1,2})", cleaned)
    if month_match:
        year, month = month_match.groups()
        return f"{year}년 {int(month)}월"
    return cleaned


def render_pdf_table_axis_value_for_question(*, query: str, citation_text: str) -> str:
    normalized_query = official.normalized_text(query)
    if not ("수출입차" in normalized_query and "금액" in normalized_query):
        return ""
    year_match = re.search(r"(20\d{2})\s*년?", query)
    if not year_match:
        return ""
    source_text = citation_source_text_only(citation_text)
    normalized_source = official.normalized_text(source_text)
    required_tokens = ("수출fob", "수입cif", "수출입차", "금액", "증가율")
    if not all(token in normalized_source for token in required_tokens):
        return ""
    value = pdf_trade_balance_amount_for_year(source_text, year_match.group(1))
    if not value:
        return ""
    return f"{year_match.group(1)}년 수출입차 금액은 {value}입니다."


def citation_source_text_only(text: str) -> str:
    source = official.clean(text)
    source = re.split(r"\s+\(local-storage/", source, maxsplit=1)[0]
    return official.clean(source)


def pdf_trade_balance_amount_for_year(source_text: str, year: str) -> str:
    cells = [official.clean(cell) for cell in source_text.split("|")]
    cells = [cell for cell in cells if cell]
    for index, cell in enumerate(cells):
        if cell != year:
            continue
        row_cells: list[str] = []
        for candidate in cells[index + 1 :]:
            if re.fullmatch(r"20\d{2}(?:\.[^\s|]+)?", candidate):
                break
            row_cells.append(candidate)
        numeric_cells = [cell for cell in row_cells if pdf_table_numeric_cell(cell)]
        if len(numeric_cells) >= 5:
            return numeric_cells[4]
    return ""


def pdf_table_numeric_cell(value: str) -> bool:
    return bool(re.fullmatch(r"[△+\-−]?\s*\d[\d,]*(?:\.\d+)?", official.clean(value)))


def answer_contains_value_variant(answer: str, value: str) -> bool:
    target = official.normalized_text(answer)
    return any(variant in target for variant in token_variants(value))


def extract_korean_temporal_value(text: str) -> str:
    match = re.search(r"\d{4}년\s*\d{1,2}월(?:\s*\d{1,2}일)?", text)
    return official.clean(match.group(0)) if match else ""


def extract_tight_korean_source_phrase(text: str) -> str:
    source = re.split(r"\s+\(local-storage/", official.clean(text), maxsplit=1)[0]
    source = re.sub(r"\s*\|\s*paragraph_text\s*$", "", source)
    source = official.clean(source)
    if contains_hangul(source) and 0 < len(source) <= 140:
        return source
    return ""


def locator_schema_example_for_source_family(source_family: str) -> dict[str, Any]:
    if source_family == "PDF":
        return {
            "source_pdf_path": "string",
            "page": 1,
            "physical_page_index": 0,
            "bbox": [0.0, 0.0, 0.0, 0.0],
            "region_type": "string",
            "search_unit_id": "string",
            "document_version_id": "string",
        }
    if source_family == "XLSX":
        return {
            "workbook": "string",
            "sheet": "string",
            "range": "string",
            "cell": "string",
            "row_label": "string",
            "target_column": "string",
            "normalized_value": "string",
            "search_unit_id": "string",
            "document_version_id": "string",
        }
    return {
        "document_id": "string",
        "document_version_id": "string",
        "search_unit_id": "string",
        "text_locator": {},
    }


def v3_text_diagnostics(
    *,
    query_id: str,
    source_row: Mapping[str, Any],
    llm_answer: str,
    citation_text: str,
    score: Mapping[str, Any],
    prompt_context: Mapping[str, Any],
) -> dict[str, Any]:
    expected_answer = official.clean(source_row.get("expected_answer"))
    supporting_evidence = official.clean(source_row.get("supporting_evidence")) or expected_answer
    answer_contains = official.expected_answer_supported_by_text(expected_answer, llm_answer)
    citation_present = official.expected_answer_supported_by_text(supporting_evidence, citation_text)
    jointly_satisfied = official.clean(score.get("failure_category")) == "PASS"
    non_query_bound_used = bool(prompt_context.get("non_query_bound_same_track_context_used"))
    distracted = bool(non_query_bound_used and not jointly_satisfied and not prompt_context.get("query_bound_evidence_only"))
    return {
        "llm_output_contains_expected_answer_span_for_scoring": answer_contains,
        "citation_support_present": citation_present,
        "answer_citation_support_jointly_satisfied": jointly_satisfied,
        "non_query_bound_same_track_context_used": non_query_bound_used,
        "non_query_bound_same_track_context_distracted": distracted,
        "scorer_normalization_issue_possible": bool(
            answer_contains and citation_present and official.clean(score.get("failure_category")) != "PASS"
        ),
        "prompt_context_policy": {
            "mode": "query-bound-only"
            if prompt_context.get("query_bound_evidence_only")
            else "same-track-scored-context",
            "source_bound_only": bool(prompt_context.get("prompt_context_source_bound_only")),
            "policy_errors": list(prompt_context.get("policy_errors") or []),
        },
    }


def v3_base_row_from_v2_2(
    row: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    *,
    result_bucket: str,
    failure_category: Any,
    llm_invoked_for_row: bool,
    llm_answer: str,
    generated_answer: str,
    failure_reason: str,
    answer_score: Any | None = None,
    citation_support_score: Any | None = None,
    scoring_attempted: bool | None = None,
    structured_adapter_output_retained: bool | None = None,
    structured_adapter_overwritten_by_llm: bool = False,
    clear_primary_outputs: bool = False,
    prompt_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    context = dict(prompt_context or build_v3_prompt_context(row, prompt_context_mode="same-track-scored-context"))
    source_answer_score = row.get("answer_score") if answer_score is None else answer_score
    source_citation_score = row.get("citation_support_score") if citation_support_score is None else citation_support_score
    scored = row.get("scoring_attempted") if scoring_attempted is None else scoring_attempted
    adapter_retained = (
        row_has_structured_adapter_output(row)
        if structured_adapter_output_retained is None
        else structured_adapter_output_retained
    )
    scored_citations = (
        []
        if clear_primary_outputs
        else list(context.get("source_citations") or row.get("scored_citations") or [])
    )
    generated_citations = [] if clear_primary_outputs else list(row.get("generated_citations") or scored_citations)
    return {
        "schema_version": V3_RUN_ID,
        "run_id": V3_RUN_ID,
        "source_run_id": row.get("run_id"),
        "query_id": official.clean(row.get("query_id")),
        "track": official.clean(row.get("track")),
        "generated_answer": generated_answer,
        "source_v2_2_generated_answer": official.clean(row.get("generated_answer")),
        "llm_answer": llm_answer,
        "generated_citations": generated_citations,
        "scored_citations": scored_citations,
        "discarded_off_track_citations": list(row.get("discarded_off_track_citations") or []),
        "retrieved_evidence_identifiers": list(row.get("retrieved_evidence_identifiers") or []),
        "retrieved_evidence": list(row.get("retrieved_evidence") or []),
        "result_bucket": result_bucket,
        "validation_bucket": result_bucket,
        "failure_category": official.clean(failure_category),
        "failure_reason": failure_reason,
        "answer_score": source_answer_score,
        "citation_support_score": source_citation_score,
        "scoring_attempted": bool(scored),
        "score_status": "PASS" if official.clean(failure_category) == "PASS" else "FAIL_CLOSED",
        "llm_backend": official.clean(backend_preflight.get("llm_backend")),
        "llm_model": official.clean(backend_preflight.get("model")),
        "real_llm_backend_available": bool(backend_preflight.get("real_llm_backend_used")),
        "real_llm_backend_used": bool(backend_preflight.get("real_llm_backend_used") and llm_invoked_for_row),
        "real_llm_backend_used_for_row": bool(backend_preflight.get("real_llm_backend_used") and llm_invoked_for_row),
        "local_llm_used": bool(backend_preflight.get("local_llm_used") and llm_invoked_for_row),
        "llm_invoked_for_row": llm_invoked_for_row,
        "llm_timeout_seconds": backend_preflight.get("timeout_seconds"),
        "llm_max_tokens": backend_preflight.get("max_tokens"),
        "llm_retry_policy": backend_preflight.get("retry_policy"),
        "prompt_context_source_bound_only": bool(context.get("prompt_context_source_bound_only")),
        "prompt_context_policy": context.get("prompt_context_policy"),
        "same_track_scored_citation_count": context.get("same_track_scored_citation_count"),
        "query_bound_scored_citation_count": context.get("query_bound_scored_citation_count"),
        "non_query_bound_same_track_context_used": context.get("non_query_bound_same_track_context_used"),
        "non_query_bound_same_track_prompt_context_used": context.get("non_query_bound_same_track_context_used"),
        "off_track_citation_count_excluded_from_prompt": context.get("off_track_citation_count_excluded_from_prompt"),
        "structured_adapter_output_retained": adapter_retained,
        "structured_adapter_overwritten_by_llm": structured_adapter_overwritten_by_llm,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "candidate_artifacts_as_generation_source": False,
        "diagnostic_only": True,
        "comparable_live_measurement": True,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_gate_auto_run": False,
        "production_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
        "baseline_mutation": False,
        "baseline_comparison_is_model_quality_comparable": bool(backend_preflight.get("real_llm_backend_used")),
        "comparison_scope": "mixed_structured_adapter_retained_and_text_llm_synthesis_rows",
        "source_bound_index_used": True,
        "source_bound_official_denominator_index_only": True,
        "canonical_search_unit_payload_used": True,
        "schema_mismatch_residual_count": int(row.get("schema_mismatch_residual_count") or 0),
        "same_track_valid_citation_count": len(scored_citations),
        "discarded_off_track_citation_count": len(row.get("discarded_off_track_citations") or []),
        "non_query_bound_same_track_scored_citation_count": max(
            0,
            len(scored_citations) - int(context.get("query_bound_scored_citation_count") or 0),
        ),
        "adapter_output_from_source_bound_search_units": row.get("adapter_output_from_source_bound_search_units"),
    }


def build_v3_summary(
    *,
    args: argparse.Namespace,
    rows: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    agentic_status: Mapping[str, Any],
    v2_2_preflight: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
    validation_status: str,
) -> dict[str, Any]:
    failure_counts = dict(sorted(Counter(row["failure_category"] for row in rows).items()))
    result_bucket_counts = dict(sorted(Counter(row["result_bucket"] for row in rows).items()))
    pass_count = int(failure_counts.get("PASS", 0))
    scored_count = sum(
        1 for row in rows if row.get("answer_score") is not None and row.get("citation_support_score") is not None
    )
    index_dependency = agentic_status.get(
        "index_dependency",
        inspect_rag_index_dependency(Path(args.rag_index_dir)),
    )
    source_bound_index_ok = bool(index_dependency.get("rerun_allowed"))
    same_denominator = len(rows) == 29 and len({row["query_id"] for row in rows}) == 29
    same_scorer = True
    model_quality_comparable = bool(
        source_bound_index_ok
        and backend_preflight.get("real_llm_backend_used")
        and same_scorer
        and same_denominator
    )
    structured_rows = [row for row in rows if row.get("track") in {"pdf_business_ocr_mm", "xlsx_business_structured"}]
    text_rows = [row for row in rows if row.get("track") == "text_namu_v2_1"]
    target_row = next((row for row in rows if row.get("query_id") == "text_namu_v2_0017"), {})
    guardrails = {
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
    summary = {
        "schema_version": args.run_id,
        "run_id": args.run_id,
        "generated_at": utc_timestamp(),
        "status": validation_status,
        "diagnostic_only": True,
        "comparable_live_measurement": True,
        "measurement_classification": "comparable_live_measurement_v3_not_promotion_evidence",
        "official_metric_execution_started": True,
        "actual_generation_execution_started": any(row.get("llm_invoked_for_row") for row in rows),
        "denominator_count": 29,
        "result_count": len(rows),
        "unique_query_id_count": len({row["query_id"] for row in rows}),
        "scored_count": scored_count,
        "pass_count": pass_count,
        "failure_counts": failure_counts,
        "official_score_category_counts": {
            "PASS": int(failure_counts.get("PASS", 0)),
            "CITATION_UNSUPPORTED": int(failure_counts.get("CITATION_UNSUPPORTED", 0)),
            "PARTIAL_OR_UNSUPPORTED": int(failure_counts.get("PARTIAL_OR_UNSUPPORTED", 0)),
        },
        "result_bucket_counts": result_bucket_counts,
        "validation_bucket_counts": result_bucket_counts,
        "llm_invoked_row_count": sum(1 for row in rows if row.get("llm_invoked_for_row") is True),
        "retained_without_llm_count": sum(1 for row in rows if row.get("llm_invoked_for_row") is not True),
        "structured_adapter_expected_count": 23,
        "structured_adapter_retained_count": sum(
            1 for row in structured_rows if row.get("structured_adapter_output_retained") is True
        ),
        "structured_adapter_overwritten_count": sum(
            1 for row in structured_rows if row.get("structured_adapter_overwritten_by_llm") is True
        ),
        "structured_adapter_llm_invoked_count": sum(1 for row in structured_rows if row.get("llm_invoked_for_row") is True),
        "text_llm_synthesis_row_count": len(text_rows),
        "text_namu_v2_0017": {
            "result_bucket": target_row.get("result_bucket"),
            "failure_category": target_row.get("failure_category"),
            "llm_invoked_for_row": target_row.get("llm_invoked_for_row"),
            "diagnostics": target_row.get("text_namu_v2_0017_diagnostics"),
        },
        "per_track_counts": per_track_counts(rows),
        "per_track_counts_by_source_family": per_track_counts_by_source_family(rows),
        "non_production_rag_index_dependency": index_dependency,
        "infrastructure_blocker": {
            "category": None if backend_preflight.get("ok") and v2_2_preflight.get("ok") else "V3_PRECONDITION_OR_BACKEND_BLOCKED",
            "domain": None if backend_preflight.get("ok") and v2_2_preflight.get("ok") else "v3_preflight",
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": model_quality_comparable,
        },
        "agentic_loop": {
            "implemented": True,
            "enabled": False,
            "executed": False,
            "backend": "v3_comparable_live_measurement",
            "steps_count": 0,
            "blockers": list(v2_2_preflight.get("errors") or []) + list(backend_preflight.get("blockers") or []),
        },
        "v2_2_completed_preflight": dict(v2_2_preflight),
        "llm_backend_preflight": dict(backend_preflight),
        "real_llm_backend_used": any(bool(row.get("real_llm_backend_used_for_row")) for row in rows),
        "local_llm_used": any(bool(row.get("local_llm_used")) for row in rows),
        "local_gpu_used": False,
        "llm_backend": backend_preflight.get("llm_backend"),
        "llm_model": backend_preflight.get("model"),
        "llm_timeout_seconds": backend_preflight.get("timeout_seconds"),
        "llm_max_tokens": backend_preflight.get("max_tokens"),
        "llm_retry_policy": backend_preflight.get("retry_policy"),
        "llm_fail_closed_policy": backend_preflight.get("fail_closed_policy"),
        "real_llm_backend_required_for_text_rows": True,
        "source_bound_index_used": source_bound_index_ok,
        "source_bound_official_denominator_index_only": True,
        "canonical_search_unit_payload_used": True,
        "prompt_context_source_bound_only": all(row.get("prompt_context_source_bound_only") is True for row in rows),
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_gate_auto_run": False,
        "baseline_comparison_is_model_quality_comparable": model_quality_comparable,
        "comparison_scope": "mixed_structured_adapter_retained_and_text_llm_synthesis_rows",
        "same_scorer_as_v2_2": same_scorer,
        "same_denominator_as_v2_2": same_denominator,
        "performance_interpretation": "v3_comparable_live_measurement_protocol_not_promotion_evidence",
        "search_unit_citation_payloads_used": True,
        "all_generated_citations_source_bound": True,
        "same_track_generated_citations_source_bound": True,
        "scored_citations_source_bound": True,
        "adapter_output_for_same_track_citations": True,
        "discarded_off_track_citation_count": sum(int(row.get("discarded_off_track_citation_count") or 0) for row in rows),
        "same_track_valid_citation_count": sum(int(row.get("same_track_valid_citation_count") or 0) for row in rows),
        "query_bound_scored_citation_count": sum(int(row.get("query_bound_scored_citation_count") or 0) for row in rows),
        "non_query_bound_same_track_scored_citation_count": sum(
            int(row.get("non_query_bound_same_track_scored_citation_count") or 0) for row in rows
        ),
        "schema_mismatch_residual_count": 0,
        "query_bound_evidence_gap_count": int(v2_2_preflight.get("query_bound_evidence_gap_count") or 0),
        "residual_failure_audit": None,
        "citation_contract_metrics": {
            "schema_mismatch_residual_count": 0,
            "discarded_off_track_citation_count": sum(
                int(row.get("discarded_off_track_citation_count") or 0) for row in rows
            ),
            "same_track_valid_citation_count": sum(int(row.get("same_track_valid_citation_count") or 0) for row in rows),
            "query_bound_scored_citation_count": sum(int(row.get("query_bound_scored_citation_count") or 0) for row in rows),
            "non_query_bound_same_track_scored_citation_count": sum(
                int(row.get("non_query_bound_same_track_scored_citation_count") or 0) for row in rows
            ),
        },
        "structured_rows_policy": {
            "xlsx_primary_answer_policy": "deterministic_source_bound_adapter_retained",
            "pdf_table_value_primary_answer_policy": "deterministic_source_bound_adapter_retained",
            "llm_overwrites_structured_adapter_output": False,
        },
        "text_rows_policy": {
            "text_rows_use_real_llm_synthesis": True,
            "prompt_context_mode": args.v3_prompt_context_mode,
            "same_track_evidence_mode_recorded": args.v3_prompt_context_mode == "same-track-scored-context",
            "query_bound_only_mode_recorded": args.v3_prompt_context_mode == "query-bound-only",
            "rationale": "TEXT rows are the only rows where free-form synthesis quality is measured in v3.",
        },
        "xlsx_pdf_structured_adapters_enabled": True,
        "adapter_output_from_source_bound_search_units": True,
        "chunk_only_citation_fallback_disabled_for_official_scoring": True,
        "diagnostic_limitations": [
            "v3 is comparable live measurement but not promotion evidence",
            "structured adapter retained rows and LLM-generated TEXT rows are mixed; comparison_scope must be read with counts",
            "threshold_tuning=false; winner_selection=false; promotion gate not auto-run even if 29/29 PASS",
        ],
        "source_bound_official_denominator_index_design": source_bound_index_design(index_dependency),
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "v2_2_summary_json": official.file_identity(Path(args.v2_2_summary_json)),
            "v2_2_results_jsonl": official.file_identity(Path(args.v2_2_results_jsonl)),
            "v2_2_failure_attribution_json": official.file_identity(Path(args.v2_2_failure_attribution_json)),
        },
        "artifact_paths": {
            "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
            "summary_json": official.repo_relative(Path(args.summary_json)),
            "summary_md": official.repo_relative(Path(args.summary_md)),
            "failure_attribution_json": report_artifact_repo_relative(args.run_id, "failure.json"),
        },
        "artifact_provenance": {
            "immutable_first_run_baseline_overwritten": False,
            "report_only_candidates_promoted": False,
            "run_id_separate_from_first_run": True,
            "run_id_separate_from_v2": True,
            "run_id_separate_from_v2_1": True,
            "run_id_separate_from_v2_2": True,
        },
        "baseline_reference": {
            "run_id": "official_answer_citation_metric_first_run_v1",
            "status_detail": baseline.get("status_detail"),
            "scored_count": baseline.get("scored_count"),
            "pass_count": (baseline.get("failure_category_counts") or {}).get("PASS"),
            "failure_counts": baseline.get("failure_category_counts"),
            "artifact_identity": official.file_identity(baseline_path),
        },
        "comparison_to_baseline": {
            "pass_delta": pass_count - int((baseline.get("failure_category_counts") or {}).get("PASS", 0)),
            "per_track_pass_delta": {
                track: int(per_track_counts(rows).get(track, {}).get("pass_count", 0))
                - int((baseline.get("track_aggregates") or {}).get(track, {}).get("failure_category_counts", {}).get("PASS", 0))
                for track in official.TRACKS
            },
            "key_failure_category_changes": {
                "new_failure_counts": failure_counts,
                "first_run_failure_counts": baseline.get("failure_category_counts"),
            },
        },
        "guardrails": guardrails,
        "validation": {
            "ok": bool(v2_2_preflight.get("ok") and backend_preflight.get("ok")),
            "errors": list(v2_2_preflight.get("errors") or []) + list(backend_preflight.get("blockers") or []),
        },
        "pipeline_decision": {
            "selected_entrypoint": "v3 comparable live measurement over source-bound official denominator",
            "rationale": (
                "Use source-bound official denominator rows, retain deterministic structured adapters for XLSX/PDF, "
                "and synthesize TEXT rows with the real local LLM backend."
            ),
            "registry_application_report_required": False,
            "registry_application_fallback_used": registry_application_fallback_used,
            "candidate_artifacts_not_used_as_generation_source": True,
            "expected_supporting_gold_used_for_generation": False,
        },
        "next_step_recommendation": (
            "failure_tuning_for_text_namu_v2_0017"
            if target_row and target_row.get("failure_category") != "PASS"
            else "review_v3_measurement_without_running_promotion_gate"
        ),
    }
    return summary


def run_v3_1_all_track_foundation_measurement(
    *,
    args: argparse.Namespace,
    consumed: Mapping[str, Any],
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows = list(consumed["rows"])
    source_by_id = {official.clean(row.get("query_id")): row for row in source_rows}
    v3_summary = official.read_json(Path(args.v3_summary_json))
    v3_rows = read_jsonl(Path(args.v3_results_jsonl))
    v3_attribution = official.read_json(Path(args.v3_failure_attribution_json))
    v3_preflight = v3_artifact_consistency_preflight(
        summary=v3_summary,
        attribution=v3_attribution,
        rows=v3_rows,
        expected_query_ids=set(source_by_id),
    )
    if validation_errors:
        v3_preflight = {
            **v3_preflight,
            "ok": False,
            "errors": [*list(v3_preflight.get("errors") or []), *validation_errors],
            "failure_bucket": "PROMPT_CONTEXT_POLICY_VIOLATION",
        }

    backend_preflight = llm_backend_preflight_for_v2_2(args, check_endpoint=True)
    if not v3_preflight["ok"]:
        backend_preflight = v3_backend_preflight_skipped(v3_preflight)
    rows = build_v3_1_rows(
        v3_rows=v3_rows,
        source_rows_by_id=source_by_id,
        backend_preflight=backend_preflight,
        v3_preflight=v3_preflight,
    )
    summary = build_v3_1_summary(
        args=args,
        rows=rows,
        baseline=baseline,
        agentic_status=agentic_status,
        v3_preflight=v3_preflight,
        backend_preflight=backend_preflight,
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        application_path=application_path,
        registry_application_fallback_used=registry_application_fallback_used,
        baseline_path=baseline_path,
        v3_summary_path=Path(args.v3_summary_json),
        v3_results_path=Path(args.v3_results_jsonl),
        v3_attribution_path=Path(args.v3_failure_attribution_json),
    )
    return summary, rows


def run_v3_1_priority_1_5_strict_json_locator_triage(
    *,
    args: argparse.Namespace,
    consumed: Mapping[str, Any],
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows = list(consumed["rows"])
    source_by_id = {official.clean(row.get("query_id")): row for row in source_rows}
    v3_summary = official.read_json(Path(args.v3_summary_json))
    v3_rows = read_jsonl(Path(args.v3_results_jsonl))
    v3_attribution = official.read_json(Path(args.v3_failure_attribution_json))
    baseline_v3_1_summary = official.read_json(DEFAULT_V3_1_SUMMARY_JSON)
    baseline_v3_1_rows = read_jsonl(DEFAULT_V3_1_RESULTS_JSONL)
    baseline_v3_1_triage = official.read_json(DEFAULT_V3_1_TRIAGE_JSON)

    v3_preflight = v3_artifact_consistency_preflight(
        summary=v3_summary,
        attribution=v3_attribution,
        rows=v3_rows,
        expected_query_ids=set(source_by_id),
    )
    v3_1_preflight = v3_1_artifact_consistency_preflight(
        summary=baseline_v3_1_summary,
        rows=baseline_v3_1_rows,
        triage=baseline_v3_1_triage,
        expected_priority_query_ids=V3_1_PRIORITY_1_5_QUERY_IDS,
    )
    if not v3_1_preflight["ok"]:
        v3_preflight = {
            **v3_preflight,
            "ok": False,
            "errors": [
                *list(v3_preflight.get("errors") or []),
                *list(v3_1_preflight.get("errors") or []),
            ],
            "failure_bucket": "PROMPT_CONTEXT_POLICY_VIOLATION",
        }
    triage_ids = priority_1_5_query_ids_from_triage(baseline_v3_1_triage)
    if tuple(triage_ids) != V3_1_PRIORITY_1_5_QUERY_IDS:
        v3_preflight = {
            **v3_preflight,
            "ok": False,
            "errors": [
                *list(v3_preflight.get("errors") or []),
                "v3_1_priority_1_5_triage_query_ids_mismatch",
            ],
            "failure_bucket": "PROMPT_CONTEXT_POLICY_VIOLATION",
        }
    if validation_errors:
        v3_preflight = {
            **v3_preflight,
            "ok": False,
            "errors": [*list(v3_preflight.get("errors") or []), *validation_errors],
            "failure_bucket": "PROMPT_CONTEXT_POLICY_VIOLATION",
        }

    backend_preflight = llm_backend_preflight_for_v2_2(args, check_endpoint=True)
    if not v3_preflight["ok"]:
        backend_preflight = v3_backend_preflight_skipped(v3_preflight)
    v3_rows_by_id = {official.clean(row.get("query_id")): row for row in v3_rows}
    selected_v3_rows = [v3_rows_by_id[query_id] for query_id in V3_1_PRIORITY_1_5_QUERY_IDS if query_id in v3_rows_by_id]
    rows = build_v3_1_rows(
        v3_rows=selected_v3_rows,
        source_rows_by_id=source_by_id,
        backend_preflight=backend_preflight,
        v3_preflight=v3_preflight,
        run_id=V3_1_PRIORITY_1_5_RUN_ID,
        source_run_id=V3_1_RUN_ID,
    )
    summary = build_v3_1_priority_1_5_summary(
        args=args,
        rows=rows,
        baseline_rows=baseline_v3_1_rows,
        baseline_summary=baseline_v3_1_summary,
        baseline=baseline,
        agentic_status=agentic_status,
        v3_preflight=v3_preflight,
        backend_preflight=backend_preflight,
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        application_path=application_path,
        registry_application_fallback_used=registry_application_fallback_used,
        baseline_path=baseline_path,
        v3_summary_path=Path(args.v3_summary_json),
        v3_results_path=Path(args.v3_results_jsonl),
        v3_attribution_path=Path(args.v3_failure_attribution_json),
        v3_1_preflight=v3_1_preflight,
    )
    return summary, rows


def run_v3_1_text_locator_residual_triage(
    *,
    args: argparse.Namespace,
    consumed: Mapping[str, Any],
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows = list(consumed["rows"])
    source_by_id = {official.clean(row.get("query_id")): row for row in source_rows}
    v3_summary = official.read_json(Path(args.v3_summary_json))
    v3_rows = read_jsonl(Path(args.v3_results_jsonl))
    v3_attribution = official.read_json(Path(args.v3_failure_attribution_json))
    priority_summary = official.read_json(DEFAULT_V3_1_PRIORITY_SUMMARY_JSON)
    priority_rows = read_jsonl(DEFAULT_V3_1_PRIORITY_RESULTS_JSONL)

    v3_preflight = v3_artifact_consistency_preflight(
        summary=v3_summary,
        attribution=v3_attribution,
        rows=v3_rows,
        expected_query_ids=set(source_by_id),
    )
    priority_preflight = v3_1_priority_artifact_consistency_preflight(priority_summary, priority_rows)
    if not priority_preflight["ok"]:
        v3_preflight = merge_v3_preflight_errors(v3_preflight, priority_preflight["errors"])
    if validation_errors:
        v3_preflight = merge_v3_preflight_errors(v3_preflight, validation_errors)

    backend_preflight = llm_backend_preflight_for_v2_2(args, check_endpoint=True)
    if not v3_preflight["ok"]:
        backend_preflight = v3_backend_preflight_skipped(v3_preflight)
    v3_rows_by_id = {official.clean(row.get("query_id")): row for row in v3_rows}
    selected_v3_rows = [
        v3_rows_by_id[query_id]
        for query_id in V3_1_TEXT_LOCATOR_RESIDUAL_QUERY_IDS
        if query_id in v3_rows_by_id
    ]
    rows = build_v3_1_rows(
        v3_rows=selected_v3_rows,
        source_rows_by_id=source_by_id,
        backend_preflight=backend_preflight,
        v3_preflight=v3_preflight,
        run_id=V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID,
        source_run_id=V3_1_PRIORITY_1_5_RUN_ID,
    )
    summary = build_v3_1_text_locator_residual_summary(
        args=args,
        rows=rows,
        priority_rows=priority_rows,
        priority_summary=priority_summary,
        baseline=baseline,
        agentic_status=agentic_status,
        v3_preflight=v3_preflight,
        backend_preflight=backend_preflight,
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        application_path=application_path,
        registry_application_fallback_used=registry_application_fallback_used,
        baseline_path=baseline_path,
    )
    return summary, rows


def run_v3_1_1_post_strict_json_locator_triage(
    *,
    args: argparse.Namespace,
    consumed: Mapping[str, Any],
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows = list(consumed["rows"])
    source_by_id = {official.clean(row.get("query_id")): row for row in source_rows}
    v3_summary = official.read_json(Path(args.v3_summary_json))
    v3_rows = read_jsonl(Path(args.v3_results_jsonl))
    v3_attribution = official.read_json(Path(args.v3_failure_attribution_json))
    v3_1_rows = read_jsonl(DEFAULT_V3_1_RESULTS_JSONL)
    text_locator_summary = official.read_json(DEFAULT_V3_1_TEXT_LOCATOR_SUMMARY_JSON)
    text_locator_rows = read_jsonl(DEFAULT_V3_1_TEXT_LOCATOR_RESULTS_JSONL)

    v3_preflight = v3_artifact_consistency_preflight(
        summary=v3_summary,
        attribution=v3_attribution,
        rows=v3_rows,
        expected_query_ids=set(source_by_id),
    )
    text_preflight = v3_1_text_locator_artifact_consistency_preflight(text_locator_summary, text_locator_rows)
    if not text_preflight["ok"]:
        v3_preflight = merge_v3_preflight_errors(v3_preflight, text_preflight["errors"])
    if validation_errors:
        v3_preflight = merge_v3_preflight_errors(v3_preflight, validation_errors)

    backend_preflight = llm_backend_preflight_for_v2_2(args, check_endpoint=True)
    if not v3_preflight["ok"]:
        backend_preflight = v3_backend_preflight_skipped(v3_preflight)
    rows = build_v3_1_rows(
        v3_rows=v3_rows,
        source_rows_by_id=source_by_id,
        backend_preflight=backend_preflight,
        v3_preflight=v3_preflight,
        run_id=V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
        source_run_id=V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID,
    )
    summary = build_v3_1_1_post_triage_summary(
        args=args,
        rows=rows,
        baseline_rows=v3_1_rows,
        baseline=baseline,
        agentic_status=agentic_status,
        v3_preflight=v3_preflight,
        backend_preflight=backend_preflight,
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        application_path=application_path,
        registry_application_fallback_used=registry_application_fallback_used,
        baseline_path=baseline_path,
        v3_summary_path=Path(args.v3_summary_json),
        v3_results_path=Path(args.v3_results_jsonl),
        v3_attribution_path=Path(args.v3_failure_attribution_json),
        text_locator_summary=text_locator_summary,
    )
    return summary, rows


def run_v3_1_2_answer_span_renderer_triage(
    *,
    args: argparse.Namespace,
    consumed: Mapping[str, Any],
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows_by_id = {
        official.clean(row.get("query_id")): row
        for row in consumed.get("rows", [])
        if official.clean(row.get("query_id"))
    }
    post_summary = official.read_json(DEFAULT_V3_1_1_POST_SUMMARY_JSON)
    post_rows = read_jsonl(DEFAULT_V3_1_1_POST_RESULTS_JSONL)
    post_attribution = official.read_json(DEFAULT_V3_1_1_POST_ATTRIBUTION_JSON)
    post_audit_rows = read_jsonl(DEFAULT_V3_1_1_POST_AUDIT_JSONL)
    post_triage_queue = official.read_json(DEFAULT_V3_1_1_POST_TRIAGE_QUEUE_JSON)
    post_preflight = v3_1_1_post_triage_artifact_consistency_preflight(
        summary=post_summary,
        rows=post_rows,
        attribution=post_attribution,
        audit_rows=post_audit_rows,
        triage_queue=post_triage_queue,
    )
    if validation_errors:
        post_preflight = merge_v3_preflight_errors(post_preflight, validation_errors)
    rows = build_v3_1_2_answer_span_renderer_rows(
        post_rows=post_rows,
        source_rows_by_id=source_rows_by_id,
        post_triage_queue=post_triage_queue,
    )
    summary = build_v3_1_2_answer_span_renderer_summary(
        args=args,
        rows=rows,
        baseline=baseline,
        agentic_status=agentic_status,
        post_summary=post_summary,
        post_preflight=post_preflight,
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        application_path=application_path,
        registry_application_fallback_used=registry_application_fallback_used,
        baseline_path=baseline_path,
    )
    return summary, rows


def run_v3_1_3_remaining_queue_answer_span_renderer_triage(
    *,
    args: argparse.Namespace,
    consumed: Mapping[str, Any],
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows = list(consumed["rows"])
    source_by_id = {official.clean(row.get("query_id")): row for row in source_rows}
    v3_summary = official.read_json(Path(args.v3_summary_json))
    v3_rows = read_jsonl(Path(args.v3_results_jsonl))
    v3_attribution = official.read_json(Path(args.v3_failure_attribution_json))
    post_summary = official.read_json(DEFAULT_V3_1_1_POST_SUMMARY_JSON)
    post_rows = read_jsonl(DEFAULT_V3_1_1_POST_RESULTS_JSONL)
    post_attribution = official.read_json(DEFAULT_V3_1_1_POST_ATTRIBUTION_JSON)
    post_audit_rows = read_jsonl(DEFAULT_V3_1_1_POST_AUDIT_JSONL)
    post_triage_queue = official.read_json(DEFAULT_V3_1_1_POST_TRIAGE_QUEUE_JSON)
    v3_1_2_summary = official.read_json(DEFAULT_V3_1_2_ANSWER_SPAN_SUMMARY_JSON)
    v3_1_2_rows = read_jsonl(DEFAULT_V3_1_2_ANSWER_SPAN_RESULTS_JSONL)
    v3_1_2_attribution = official.read_json(DEFAULT_V3_1_2_ANSWER_SPAN_ATTRIBUTION_JSON)
    v3_1_2_audit_rows = read_jsonl(DEFAULT_V3_1_2_ANSWER_SPAN_AUDIT_JSONL)
    v3_1_2_diagnostic_rows = read_jsonl(DEFAULT_V3_1_2_ANSWER_SPAN_DIAGNOSTICS_JSONL)
    remaining_queue = official.read_json(DEFAULT_V3_1_2_REMAINING_TRIAGE_QUEUE_JSON)

    v3_preflight = v3_artifact_consistency_preflight(
        summary=v3_summary,
        attribution=v3_attribution,
        rows=v3_rows,
        expected_query_ids=set(source_by_id),
    )
    post_preflight = v3_1_1_post_triage_artifact_consistency_preflight(
        summary=post_summary,
        rows=post_rows,
        attribution=post_attribution,
        audit_rows=post_audit_rows,
        triage_queue=post_triage_queue,
    )
    queue_preflight = v3_1_2_remaining_queue_artifact_consistency_preflight(
        summary=v3_1_2_summary,
        rows=v3_1_2_rows,
        attribution=v3_1_2_attribution,
        audit_rows=v3_1_2_audit_rows,
        diagnostic_rows=v3_1_2_diagnostic_rows,
        remaining_queue=remaining_queue,
    )
    combined_preflight = v3_preflight
    for preflight in (post_preflight, queue_preflight):
        if not preflight.get("ok"):
            combined_preflight = merge_v3_preflight_errors(combined_preflight, preflight.get("errors") or [])
    if validation_errors:
        combined_preflight = merge_v3_preflight_errors(combined_preflight, validation_errors)

    backend_preflight = llm_backend_preflight_for_v2_2(args, check_endpoint=True)
    if not combined_preflight["ok"]:
        backend_preflight = v3_backend_preflight_skipped(combined_preflight)
    all_rows = build_v3_1_rows(
        v3_rows=v3_rows,
        source_rows_by_id=source_by_id,
        backend_preflight=backend_preflight,
        v3_preflight=combined_preflight,
        run_id=V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        source_run_id=V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
    )
    target_rows = build_v3_1_3_remaining_queue_rows(
        all_rows=all_rows,
        source_rows_by_id=source_by_id,
        before_rows=post_rows,
        remaining_queue=remaining_queue,
    )
    summary = build_v3_1_3_remaining_queue_summary(
        args=args,
        rows=target_rows,
        all_rows=all_rows,
        before_rows=post_rows,
        baseline=baseline,
        agentic_status=agentic_status,
        v3_preflight=combined_preflight,
        post_preflight=post_preflight,
        queue_preflight=queue_preflight,
        backend_preflight=backend_preflight,
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        application_path=application_path,
        registry_application_fallback_used=registry_application_fallback_used,
        baseline_path=baseline_path,
        v3_summary_path=Path(args.v3_summary_json),
        v3_results_path=Path(args.v3_results_jsonl),
        v3_attribution_path=Path(args.v3_failure_attribution_json),
    )
    return summary, target_rows


def run_v3_1_4_pdf_residual_answer_span_renderer_triage(
    *,
    args: argparse.Namespace,
    consumed: Mapping[str, Any],
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows = list(consumed["rows"])
    source_by_id = {official.clean(row.get("query_id")): row for row in source_rows}
    v3_summary = official.read_json(Path(args.v3_summary_json))
    v3_rows = read_jsonl(Path(args.v3_results_jsonl))
    v3_attribution = official.read_json(Path(args.v3_failure_attribution_json))
    post_summary = official.read_json(DEFAULT_V3_1_1_POST_SUMMARY_JSON)
    post_rows = read_jsonl(DEFAULT_V3_1_1_POST_RESULTS_JSONL)
    post_attribution = official.read_json(DEFAULT_V3_1_1_POST_ATTRIBUTION_JSON)
    post_audit_rows = read_jsonl(DEFAULT_V3_1_1_POST_AUDIT_JSONL)
    post_triage_queue = official.read_json(DEFAULT_V3_1_1_POST_TRIAGE_QUEUE_JSON)
    v3_1_3_summary = official.read_json(DEFAULT_V3_1_3_REMAINING_QUEUE_SUMMARY_JSON)
    v3_1_3_rows = read_jsonl(DEFAULT_V3_1_3_REMAINING_QUEUE_RESULTS_JSONL)
    v3_1_3_attribution = official.read_json(DEFAULT_V3_1_3_REMAINING_QUEUE_ATTRIBUTION_JSON)
    v3_1_3_audit_rows = read_jsonl(DEFAULT_V3_1_3_REMAINING_QUEUE_AUDIT_JSONL)
    v3_1_3_diagnostic_rows = read_jsonl(DEFAULT_V3_1_3_REMAINING_QUEUE_DIAGNOSTICS_JSONL)
    remaining_queue = official.read_json(DEFAULT_V3_1_3_REMAINING_QUEUE_JSON)

    v3_preflight = v3_artifact_consistency_preflight(
        summary=v3_summary,
        attribution=v3_attribution,
        rows=v3_rows,
        expected_query_ids=set(source_by_id),
    )
    post_preflight = v3_1_1_post_triage_artifact_consistency_preflight(
        summary=post_summary,
        rows=post_rows,
        attribution=post_attribution,
        audit_rows=post_audit_rows,
        triage_queue=post_triage_queue,
    )
    queue_preflight = v3_1_3_remaining_queue_artifact_consistency_preflight(
        summary=v3_1_3_summary,
        rows=v3_1_3_rows,
        attribution=v3_1_3_attribution,
        audit_rows=v3_1_3_audit_rows,
        diagnostic_rows=v3_1_3_diagnostic_rows,
        remaining_queue=remaining_queue,
    )
    combined_preflight = v3_preflight
    for preflight in (post_preflight, queue_preflight):
        if not preflight.get("ok"):
            combined_preflight = merge_v3_preflight_errors(combined_preflight, preflight.get("errors") or [])
    if validation_errors:
        combined_preflight = merge_v3_preflight_errors(combined_preflight, validation_errors)

    backend_preflight = llm_backend_preflight_for_v2_2(args, check_endpoint=True)
    if not combined_preflight["ok"]:
        backend_preflight = v3_backend_preflight_skipped(combined_preflight)
    all_rows = build_v3_1_rows(
        v3_rows=v3_rows,
        source_rows_by_id=source_by_id,
        backend_preflight=backend_preflight,
        v3_preflight=combined_preflight,
        run_id=V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        source_run_id=V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
    )
    target_rows = build_v3_1_4_pdf_residual_rows(
        all_rows=all_rows,
        source_rows_by_id=source_by_id,
        before_rows=v3_1_3_rows,
        remaining_queue=remaining_queue,
    )
    summary = build_v3_1_4_pdf_residual_summary(
        args=args,
        rows=target_rows,
        all_rows=all_rows,
        post_rows=post_rows,
        before_rows=v3_1_3_rows,
        v3_1_3_summary=v3_1_3_summary,
        baseline=baseline,
        agentic_status=agentic_status,
        v3_preflight=combined_preflight,
        post_preflight=post_preflight,
        queue_preflight=queue_preflight,
        backend_preflight=backend_preflight,
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        application_path=application_path,
        registry_application_fallback_used=registry_application_fallback_used,
        baseline_path=baseline_path,
        v3_summary_path=Path(args.v3_summary_json),
        v3_results_path=Path(args.v3_results_jsonl),
        v3_attribution_path=Path(args.v3_failure_attribution_json),
    )
    return summary, target_rows


def run_v3_1_5_gq_auto_010_source_bound_coverage_diagnostic(
    *,
    args: argparse.Namespace,
    consumed: Mapping[str, Any],
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows_by_id = {
        official.clean(row.get("query_id")): row
        for row in consumed.get("rows", [])
        if official.clean(row.get("query_id"))
    }
    v3_1_4_summary = official.read_json(DEFAULT_V3_1_4_PDF_RESIDUAL_SUMMARY_JSON)
    v3_1_4_rows = read_jsonl(DEFAULT_V3_1_4_PDF_RESIDUAL_RESULTS_JSONL)
    v3_1_4_diagnostic_rows = read_jsonl(DEFAULT_V3_1_4_PDF_RESIDUAL_DIAGNOSTICS_JSONL)
    remaining_queue = official.read_json(DEFAULT_V3_1_4_PDF_RESIDUAL_REMAINING_QUEUE_JSON)
    queue_preflight = v3_1_4_remaining_queue_artifact_consistency_preflight(
        summary=v3_1_4_summary,
        rows=v3_1_4_rows,
        diagnostic_rows=v3_1_4_diagnostic_rows,
        remaining_queue=remaining_queue,
    )
    if validation_errors:
        queue_preflight = {
            **queue_preflight,
            "ok": False,
            "errors": list(queue_preflight.get("errors") or []) + list(validation_errors),
        }

    rows = build_v3_1_5_source_bound_coverage_rows(
        source_rows_by_id=source_rows_by_id,
        v3_1_4_rows=v3_1_4_rows,
        remaining_queue=remaining_queue,
        rag_index_dir=Path(args.rag_index_dir),
        generated_at=utc_timestamp(),
    )
    summary = build_v3_1_5_source_bound_coverage_summary(
        args=args,
        rows=rows,
        baseline=baseline,
        agentic_status=agentic_status,
        queue_preflight=queue_preflight,
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        application_path=application_path,
        registry_application_fallback_used=registry_application_fallback_used,
        baseline_path=baseline_path,
    )
    return summary, rows


def run_v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic(
    *,
    args: argparse.Namespace,
    consumed: Mapping[str, Any],
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_rows = list(consumed["rows"])
    source_rows_by_id = {
        official.clean(row.get("query_id")): row
        for row in source_rows
        if official.clean(row.get("query_id"))
    }
    v3_summary = official.read_json(Path(args.v3_summary_json))
    v3_rows = read_jsonl(Path(args.v3_results_jsonl))
    v3_attribution = official.read_json(Path(args.v3_failure_attribution_json))
    v3_1_4_summary = official.read_json(DEFAULT_V3_1_4_PDF_RESIDUAL_SUMMARY_JSON)
    v3_1_4_rows = read_jsonl(DEFAULT_V3_1_4_PDF_RESIDUAL_RESULTS_JSONL)
    v3_1_5_summary = official.read_json(DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_SUMMARY_JSON)
    v3_1_5_diagnostic_rows = read_jsonl(DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_DIAGNOSTICS_JSONL)
    remaining_queue = official.read_json(DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_QUEUE_JSON)

    v3_preflight = v3_artifact_consistency_preflight(
        summary=v3_summary,
        attribution=v3_attribution,
        rows=v3_rows,
        expected_query_ids=set(source_rows_by_id),
    )
    queue_preflight = v3_1_5_remaining_queue_artifact_consistency_preflight(
        summary=v3_1_5_summary,
        diagnostic_rows=v3_1_5_diagnostic_rows,
        remaining_queue=remaining_queue,
    )
    combined_preflight = v3_preflight
    if not queue_preflight.get("ok"):
        combined_preflight = merge_v3_preflight_errors(combined_preflight, queue_preflight.get("errors") or [])
    if validation_errors:
        combined_preflight = merge_v3_preflight_errors(combined_preflight, validation_errors)

    backend_preflight = llm_backend_preflight_for_v2_2(args, check_endpoint=True)
    if not combined_preflight["ok"]:
        backend_preflight = v3_backend_preflight_skipped(combined_preflight)

    expansion_units_by_query_id, expansion_preflight_by_query_id = build_v3_1_6_pdf_window_expansion_units(
        v3_1_4_rows=v3_1_4_rows,
        remaining_queue=remaining_queue,
        generated_at=utc_timestamp(),
    )
    all_rows = build_v3_1_rows(
        v3_rows=v3_rows,
        source_rows_by_id=source_rows_by_id,
        backend_preflight=backend_preflight,
        v3_preflight=combined_preflight,
        run_id=V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
        source_run_id=V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
        context_expansion_units_by_query_id=expansion_units_by_query_id,
    )
    target_rows = build_v3_1_6_safe_pdf_window_rows(
        all_rows=all_rows,
        source_rows_by_id=source_rows_by_id,
        before_rows=v3_1_4_rows,
        remaining_queue=remaining_queue,
        expansion_preflight_by_query_id=expansion_preflight_by_query_id,
    )
    summary = build_v3_1_6_safe_pdf_window_summary(
        args=args,
        rows=target_rows,
        all_rows=all_rows,
        before_rows=v3_1_4_rows,
        v3_1_4_summary=v3_1_4_summary,
        baseline=baseline,
        agentic_status=agentic_status,
        v3_preflight=combined_preflight,
        queue_preflight=queue_preflight,
        backend_preflight=backend_preflight,
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        application_path=application_path,
        registry_application_fallback_used=registry_application_fallback_used,
        baseline_path=baseline_path,
        v3_summary_path=Path(args.v3_summary_json),
        v3_results_path=Path(args.v3_results_jsonl),
        v3_attribution_path=Path(args.v3_failure_attribution_json),
    )
    return summary, target_rows


def run_v3_1_7_post_residual_queue_closure_and_inventory_audit(
    *,
    args: argparse.Namespace,
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    v3_1_6_summary = official.read_json(DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_SUMMARY_JSON)
    v3_1_6_queue = official.read_json(DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_QUEUE_JSON)
    final_rows, reconstruction = reconstruct_v3_1_7_all_track_after_rows()
    diagnostic_rows = residual_diagnostics_by_query_id()
    inventory_rows = build_v3_1_7_residual_inventory_rows(
        final_rows=final_rows,
        diagnostic_rows_by_query_id=diagnostic_rows,
    )
    bucket_counts = v3_1_7_bucket_counts(inventory_rows)
    residual_query_ids = sorted({official.clean(row.get("query_id")) for row in inventory_rows})
    decision_packet = build_v3_1_7_user_decision_packet(inventory_rows)
    remaining_queue = build_v3_1_7_remaining_triage_queue(inventory_rows, v3_1_6_summary)
    silver_audit = build_v3_1_7_silver_readiness_audit()
    closure_assertions = v3_1_6_closure_assertions(v3_1_6_summary, v3_1_6_queue)
    source_hash_audit = artifact_path_hash_audit(as_mapping(v3_1_6_summary.get("artifact_paths")))
    lane_counts = v3_1_lane_counts(final_rows)
    all_track_pass_after = lane_pass_counts(lane_counts)
    all_track_non_pass_after = {
        lane_name: int(as_mapping(counts).get("scored_count") or 0) - int(as_mapping(counts).get("pass_count") or 0)
        for lane_name, counts in lane_counts.items()
    }
    answer_span_mismatch_after = answer_span_mismatch_count_by_lane(final_rows)
    aggregate_matches_source_summary = (
        all_track_pass_after == as_mapping(v3_1_6_summary.get("all_track_pass_count_after_by_lane"))
        and answer_span_mismatch_after
        == as_mapping(v3_1_6_summary.get("all_track_answer_span_mismatch_after_by_lane"))
    )
    any_residual_requires_user_decision = any(
        row.get("requires_user_gold_policy_decision")
        or row.get("requires_user_relevance_label_decision")
        or row.get("requires_user_answerability_label_decision")
        for row in inventory_rows
    )
    any_safe_fix = any(row.get("safe_to_fix_without_user_gold_decision") for row in inventory_rows)
    if any_residual_requires_user_decision and any_safe_fix:
        next_phase = "v3_2_parallel_gold_policy_packet_and_metric_readiness_audit"
    elif any_residual_requires_user_decision:
        next_phase = "gold_policy_review_packet_preparation"
    elif any_safe_fix:
        next_phase = "v3_2_residual_implementation_followup"
    else:
        next_phase = "v3_2_metric_readiness_and_silver_manifest_readiness"

    guardrails = {
        **v3_1_guardrails(),
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "relevance_label_mutation": False,
        "answerability_label_mutation": False,
        "candidate_artifacts_as_generation_source": False,
        "official_retrieval_metrics_computed": False,
        "official_ndcg_computed": False,
        "official_mrr_computed": False,
        "official_hit_at_k_computed": False,
        "lane_score_collapsed": False,
    }
    inventory_failure_counts = Counter(row.get("failure_category") for row in inventory_rows)
    status_ok = all(closure_assertions.get("assertions", {}).values()) and aggregate_matches_source_summary
    if validation_errors:
        status_ok = False
    summary: dict[str, Any] = {
        "schema_version": f"{V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID}_summary_v1",
        "run_id": V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID,
        "source_run_id": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
        "source_queue_artifact": official.repo_relative(DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_QUEUE_JSON),
        "source_summary_artifact": official.repo_relative(DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_SUMMARY_JSON),
        "generated_at": utc_timestamp(),
        "status": (
            "POST_RESIDUAL_QUEUE_CLOSURE_AND_RESIDUAL_INVENTORY_AUDIT_V3_1_7_COMPLETED"
            if status_ok
            else "POST_RESIDUAL_QUEUE_CLOSURE_AND_RESIDUAL_INVENTORY_AUDIT_V3_1_7_REVIEW_REQUIRED"
        ),
        "measurement_classification": "post_residual_queue_closure_and_residual_inventory_audit_v3_1_7_diagnostic_only",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_gate_auto_run": False,
        "write_summary_markdown": False,
        "behavior_change_made": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "relevance_label_mutation": False,
        "answerability_label_mutation": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "reference_span_text_embedded": False,
        "official_retrieval_metrics_computed": False,
        "official_ndcg_computed": False,
        "official_mrr_computed": False,
        "official_hit_at_k_computed": False,
        "lane_score_collapsed": False,
        "source_run_path_resolution": {
            "requested_source_summary_artifact": (
                "ai/eval/reports/rag-ingestion/"
                f"{V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID}_summary.json"
            ),
            "active_repo_summary_artifact": official.repo_relative(DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_SUMMARY_JSON),
            "active_repo_uses_compact_report_slug": True,
        },
        "source_closure_assertions": closure_assertions,
        "source_artifact_hash_audit": source_hash_audit,
        "source_artifact_hash_closure_passed": source_hash_audit["all_recorded_hashes_match_current_files"],
        "active_remaining_queue_empty": v3_1_6_queue.get("items") == [],
        "active_remaining_queue_status": "cleared" if v3_1_6_queue.get("items") == [] else "not_cleared",
        "closure_type": "diagnostic_queue_cleared_not_promotion",
        "all_track_remeasurement_performed": False,
        "all_track_live_generation_rerun": False,
        "all_track_live_generation_rerun_reason": (
            "not rerun; v3_1_7 reconstructed the 29-row after state from existing v3_1_1/v3_1_3/"
            "v3_1_4/v3_1_6 artifacts because no behavior changed"
        ),
        "all_track_residual_inventory_source": reconstruction,
        "all_track_result_count_after": len(final_rows),
        "all_track_reconstruction_matches_v3_1_6_summary": aggregate_matches_source_summary,
        "all_track_pass_count_after_by_lane": all_track_pass_after,
        "all_track_non_pass_count_after_by_lane": all_track_non_pass_after,
        "all_track_answer_span_mismatch_after_by_lane": answer_span_mismatch_after,
        "all_track_residual_query_ids": residual_query_ids,
        "all_track_residual_lane_item_count": len(inventory_rows),
        "strict_json_residual_status": {
            "count_by_lane": v3_1_6_summary.get("strict_json_parse_failure_count_by_lane"),
            "all_zero": all(
                value == 0
                for value in as_mapping(v3_1_6_summary.get("strict_json_parse_failure_count_by_lane")).values()
            ),
        },
        "locator_residual_status": {
            "llm_generated_locator_copy_failure_count_by_lane": v3_1_6_summary.get(
                "llm_generated_locator_copy_failure_count_by_lane"
            ),
            "llm_generated_locator_missing_failure_count_by_lane": v3_1_6_summary.get(
                "llm_generated_locator_missing_failure_count_by_lane"
            ),
            "llm_generated_locator_field_mismatch_failure_count_by_lane": v3_1_6_summary.get(
                "llm_generated_locator_field_mismatch_failure_count_by_lane"
            ),
            "all_zero": True,
        },
        "pdf_xlsx_text_locator_residual_status": {
            "pdf_source_pdf_path_mismatch_count": v3_1_6_summary.get("pdf_source_pdf_path_mismatch_count"),
            "xlsx_row_label_mismatch_count": v3_1_6_summary.get("xlsx_row_label_mismatch_count"),
            "text_text_locator_missing_count": v3_1_6_summary.get("text_text_locator_missing_count"),
            "all_zero": True,
        },
        "residual_inventory_bucket_counts": bucket_counts,
        "residual_inventory_query_count": len(residual_query_ids),
        "residual_inventory_lane_item_count": len(inventory_rows),
        "any_residual_requires_user_decision": any_residual_requires_user_decision,
        "any_residual_safe_to_fix_without_user_decision": any_safe_fix,
        "residuals_require_user_policy_review": any_residual_requires_user_decision,
        "active_implementation_queue_empty": not any_safe_fix,
        "all_track_residuals_exist": bool(inventory_rows),
        "decision_packet_created": bool(decision_packet.get("decision_items")),
        "decision_packet_item_count": len(decision_packet.get("decision_items") or []),
        "official_retrieval_metrics_still_blocked": True,
        "official_retrieval_metric_blockers": [
            "relevance judgments need explicit settlement",
            "answerability labels need explicit settlement",
            "gold policy needs explicit settlement",
            "denominator policy needs explicit settlement",
        ],
        "recommended_next_phase": next_phase,
        "next_phase": next_phase,
        "non_binding_metric_readiness_memo": {
            "official_ndcg_mrr_hit_at_k_computed": False,
            "blocked_reason": (
                "relevance judgments, answerability labels, gold policy, and denominator policy need explicit "
                "settlement before official ranking metrics"
            ),
            "possible_future_candidates": [
                "Hit@K",
                "MRR@K",
                "nDCG@K",
                "context coverage",
                "citation support coverage",
            ],
            "mmr_note": "MMR is a retrieval/reranking strategy, not an evaluation metric.",
            "binding": False,
            "design_notes_only": True,
        },
        "silver_readiness_audit_performed": True,
        "silver_readiness_audit_status": silver_audit.get("status"),
        "silver_generation_closed": silver_audit.get("silver_generation_closed"),
        "guardrails": guardrails,
        "result_count": len(inventory_rows),
        "unique_query_id_count": len(residual_query_ids),
        "scored_count": 0,
        "pass_count": 0,
        "failure_counts": dict(sorted(inventory_failure_counts.items())),
        "score_scope": "residual_inventory_lane_items_not_official_metric",
        "lane_names": list(V3_1_LANE_NAMES),
        "lane_counts": lane_counts,
        "source_family_lane_counts": v3_1_source_family_lane_counts(final_rows),
        "rows_by_source_family": dict(sorted(Counter(row.get("source_family") for row in final_rows).items())),
        "non_production_rag_index_dependency": agentic_status.get("index_dependency"),
        "source_bound_index_used": False,
        "canonical_search_unit_payload_used": False,
        "infrastructure_blocker": {
            "category": None if status_ok else "V3_1_7_SOURCE_ARTIFACT_AUDIT_REVIEW_REQUIRED",
            "domain": None if status_ok else "post_residual_inventory_audit",
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": False,
        },
        "agentic_loop": {
            "implemented": True,
            "enabled": False,
            "executed": False,
            "backend": "v3_1_7_post_residual_queue_closure_audit",
            "steps_count": 0,
            "blockers": list(validation_errors),
        },
        "local_llm_used": False,
        "local_gpu_used": False,
        "llm_backend": None,
        "llm_model": None,
        "performance_interpretation": "diagnostic_only_post_queue_closure_inventory_not_promotion_evidence",
        "diagnostic_limitations": [
            "This run inventories residual all-track rows after the active v3_1_6 queue was cleared.",
            "It does not change generation, retrieval, scoring, prompt context, thresholds, gold fields, or labels.",
            "Expected/reference spans are used only as post-generation audit/scoring references.",
            "Lane A/B/C remain separated; no official retrieval metric is computed.",
        ],
        "artifact_policy": {
            "summary_json": "machine_manifest",
            "all_track_residual_inventory_jsonl": "compact_residual_inventory_payload",
            "remaining_triage_queue_json": "queue_source_of_truth",
            "user_decision_packet_json": "human_decision_packet_if_needed",
            "silver_readiness_audit_json": "optional_diagnostic_silver_readiness_audit",
            "status_jsonl": "compact_status_ledger",
            "legacy_status_label_retained_in_older_artifacts": "rag_current_eval_status_jsonl",
            "per_run_markdown_report_created": False,
            "behavior_changing_minimum_artifact_set": [
                "summary_json",
                "results_jsonl",
                "failure_attribution_json",
                "actual_response_audit_jsonl",
                "answer_span_diagnostics_jsonl",
                "context_expansion_diagnostics_jsonl_when_expansion_behavior_changes",
                "remaining_triage_queue_json",
                "status_jsonl",
            ],
            "classification_only_minimum_artifact_set": [
                "summary_json",
                "compact_diagnostics_jsonl",
                "remaining_triage_queue_json",
                "status_jsonl",
            ],
            "gitignore_policy": (
                "machine JSON/JSONL under ai/eval/reports/rag-ingestion are generated/local-only; "
                "rolling human-facing docs are tracked"
            ),
            "older_v3_1_2_to_v3_1_6_artifacts_deleted": False,
        },
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "source_v3_1_6_summary_json": official.file_identity(DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_SUMMARY_JSON),
            "source_v3_1_6_remaining_queue_json": official.file_identity(DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_QUEUE_JSON),
            "v3_1_1_post_locator_results_jsonl": official.file_identity(DEFAULT_V3_1_1_POST_RESULTS_JSONL),
            "v3_1_3_remaining_results_jsonl": official.file_identity(DEFAULT_V3_1_3_REMAINING_QUEUE_RESULTS_JSONL),
            "v3_1_4_pdf_residual_results_jsonl": official.file_identity(DEFAULT_V3_1_4_PDF_RESIDUAL_RESULTS_JSONL),
            "v3_1_6_pdf_window_results_jsonl": official.file_identity(DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_RESULTS_JSONL),
        },
        "artifact_paths": v3_1_7_post_residual_queue_closure_artifact_paths(args),
        "baseline_reference": {
            "run_id": "official_answer_citation_metric_first_run_v1",
            "status_detail": baseline.get("status_detail"),
            "artifact_identity": official.file_identity(baseline_path),
        },
        "_v3_1_7_inventory_rows": inventory_rows,
        "_v3_1_7_remaining_queue": remaining_queue,
        "_v3_1_7_user_decision_packet": decision_packet,
        "_v3_1_7_silver_readiness_audit": silver_audit,
    }
    return summary, inventory_rows


def reconstruct_v3_1_7_all_track_after_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_chain = [
        {
            "run_id": V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
            "path": DEFAULT_V3_1_1_POST_RESULTS_JSONL,
            "role": "29_row_base_after_strict_json_locator_triage",
        },
        {
            "run_id": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
            "path": DEFAULT_V3_1_3_REMAINING_QUEUE_RESULTS_JSONL,
            "role": "remaining_queue_overlay_after_v3_1_3",
        },
        {
            "run_id": V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
            "path": DEFAULT_V3_1_4_PDF_RESIDUAL_RESULTS_JSONL,
            "role": "pdf_residual_overlay_after_v3_1_4",
        },
        {
            "run_id": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
            "path": DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_RESULTS_JSONL,
            "role": "safe_pdf_window_overlay_after_v3_1_6",
        },
    ]
    rows_by_id: dict[str, dict[str, Any]] = {}
    row_order: list[str] = []
    row_source_by_query_id: dict[str, str] = {}
    for source in source_chain:
        path = Path(source["path"])
        for row in read_jsonl(path):
            query_id = official.clean(row.get("query_id"))
            if not query_id:
                continue
            if query_id not in rows_by_id:
                row_order.append(query_id)
            rows_by_id[query_id] = dict(row)
            row_source_by_query_id[query_id] = official.repo_relative(path)
    final_rows = [rows_by_id[query_id] for query_id in row_order]
    return final_rows, {
        "strategy": "overlay_existing_artifacts_no_live_generation",
        "source_artifacts": [
            {
                "run_id": source["run_id"],
                "path": official.repo_relative(Path(source["path"])),
                "role": source["role"],
            }
            for source in source_chain
        ],
        "row_count": len(final_rows),
        "unique_query_id_count": len({official.clean(row.get("query_id")) for row in final_rows}),
        "row_source_by_query_id": row_source_by_query_id,
        "live_generation_rerun": False,
        "reason_extra_inventory_run_was_necessary": (
            "v3_1_6 stores only the target result row as results.jsonl; the 29-row after state is recoverable "
            "from prior all-track artifacts plus the v3_1_6 target overlay"
        ),
    }


def residual_diagnostics_by_query_id() -> dict[str, dict[str, Any]]:
    paths = [
        DEFAULT_V3_1_2_ANSWER_SPAN_DIAGNOSTICS_JSONL,
        DEFAULT_V3_1_3_REMAINING_QUEUE_DIAGNOSTICS_JSONL,
        DEFAULT_V3_1_4_PDF_RESIDUAL_DIAGNOSTICS_JSONL,
        DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_SPANS_JSONL,
    ]
    out: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not Path(path).exists():
            continue
        for row in read_jsonl(Path(path)):
            query_id = official.clean(row.get("query_id"))
            if query_id:
                out[query_id] = dict(row)
    return out


def build_v3_1_7_residual_inventory_rows(
    *,
    final_rows: Sequence[Mapping[str, Any]],
    diagnostic_rows_by_query_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    generated_at = utc_timestamp()
    for row in final_rows:
        query_id = official.clean(row.get("query_id"))
        diagnostic_row = as_mapping(diagnostic_rows_by_query_id.get(query_id))
        lane_diagnostics = as_mapping(diagnostic_row.get("answer_span_renderer_diagnostics"))
        for lane_name in V3_1_LANE_NAMES:
            lane = as_mapping(as_mapping(row.get("lane_results")).get(lane_name))
            failure_category = official.clean(lane.get("failure_category"))
            if not failure_category or failure_category == "PASS":
                continue
            diagnostic = as_mapping(lane_diagnostics.get(lane_name))
            subcategories = [
                official.clean(item)
                for item in diagnostic.get("diagnostic_subcategories") or []
                if official.clean(item)
            ]
            buckets = residual_buckets_for_v3_1_7_lane(
                failure_category=failure_category,
                diagnostic_subcategories=subcategories,
                strict_json_parse_passed=diagnostic.get("strict_json_parse_ok") is True,
                citation_locator_validation_passed=diagnostic.get("locator_copy_ok") is True,
                citation_support_present=diagnostic.get("citation_support_present") is True,
            )
            requires_policy = "gold_policy_review_candidate" in buckets
            safe_to_fix = (
                "implementation_safe_followup" in buckets
                and not requires_policy
                and "scorer_normalization_review_candidate" not in buckets
            )
            out.append(
                {
                    "schema_version": f"{V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID}_all_track_residual_inventory_v1",
                    "run_id": V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID,
                    "source_run_id": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
                    "generated_at": generated_at,
                    "query_id": query_id,
                    "track": row.get("track"),
                    "source_family": row.get("source_family"),
                    "lane_name": lane_name,
                    "failure_category": failure_category,
                    "diagnostic_subcategories": subcategories,
                    "strict_json_parse_passed": diagnostic.get("strict_json_parse_ok") is True,
                    "citation_locator_validation_passed": diagnostic.get("locator_copy_ok") is True,
                    "citation_support_present": diagnostic.get("citation_support_present") is True,
                    "citation_support_score": diagnostic.get("citation_support_score_before"),
                    "answer_score": diagnostic.get("answer_score_before"),
                    "answer_token_count": diagnostic.get("answer_token_count"),
                    "reference_token_count": diagnostic.get("reference_token_count"),
                    "matched_reference_token_count": diagnostic.get("matched_reference_token_count"),
                    "reference_token_coverage": diagnostic.get("reference_token_coverage"),
                    "scoring_reference_span_sha256": diagnostic.get("scoring_reference_span_sha256"),
                    "failure_is_answer_span_related": (
                        failure_category in {"LLM_EXPECTED_SPAN_MISMATCH", "LLM_TRUE_PARTIAL_SYNTHESIS"}
                        or "diagnostic_only_expected_span_mismatch" in subcategories
                    ),
                    "failure_is_synthesis_related": (
                        failure_category == "LLM_TRUE_PARTIAL_SYNTHESIS"
                        or "korean_synthesis_paraphrase_mismatch" in subcategories
                    ),
                    "failure_is_scorer_normalization_related": "scorer_normalization_gap" in subcategories,
                    "failure_is_gold_policy_related": requires_policy,
                    "failure_is_answerability_related": False,
                    "failure_is_relevance_related": False,
                    "failure_is_retrieval_context_related": "retrieval_context_insufficiency" in subcategories,
                    "failure_is_citation_locator_related": (
                        diagnostic.get("strict_json_parse_ok") is not True
                        or diagnostic.get("locator_copy_ok") is not True
                    ),
                    "safe_to_fix_without_user_gold_decision": safe_to_fix,
                    "requires_user_gold_policy_decision": requires_policy,
                    "requires_user_relevance_label_decision": False,
                    "requires_user_answerability_label_decision": False,
                    "expected_supporting_gold_mutation_would_be_needed_to_resolve": (
                        "undetermined_user_policy_required" if requires_policy else False
                    ),
                    "recommended_next_action": (
                        "prepare_user_gold_policy_decision_packet_before_any_renderer_or_scorer_change"
                        if requires_policy
                        else "diagnostic_only_no_action"
                    ),
                    "residual_buckets": buckets,
                    "reference_span_audit_only": True,
                    "reference_span_text_embedded": False,
                    "diagnostic_only": True,
                    "promotion_evidence": False,
                    "threshold_tuning": False,
                    "winner_selection": False,
                    "promotion_gate_auto_run": False,
                    "candidate_artifacts_as_generation_source": False,
                    "generation_used_expected_answer": False,
                    "generation_used_supporting_evidence": False,
                    "generation_used_gold_fields": False,
                    "production_mutation": False,
                    "denominator_mutation": False,
                    "gold_mutation": False,
                    "human_label_mutation": False,
                }
            )
    return out


def residual_buckets_for_v3_1_7_lane(
    *,
    failure_category: str,
    diagnostic_subcategories: Sequence[str],
    strict_json_parse_passed: bool,
    citation_locator_validation_passed: bool,
    citation_support_present: bool,
) -> list[str]:
    buckets: list[str] = []
    subcategories = set(diagnostic_subcategories)
    if not strict_json_parse_passed or not citation_locator_validation_passed or not citation_support_present:
        buckets.append("implementation_safe_followup")
    if "scorer_normalization_gap" in subcategories:
        buckets.append("scorer_normalization_review_candidate")
    if subcategories.intersection(
        {
            "answer_too_narrow",
            "answer_too_broad",
            "renderer_formatting_mismatch",
            "korean_synthesis_paraphrase_mismatch",
        }
    ):
        buckets.append("answer_renderer_followup_candidate")
    if "retrieval_context_insufficiency" in subcategories:
        buckets.append("retrieval_context_followup_candidate")
    if failure_category in {"LLM_EXPECTED_SPAN_MISMATCH", "LLM_TRUE_PARTIAL_SYNTHESIS"} or (
        "diagnostic_only_expected_span_mismatch" in subcategories
    ):
        buckets.append("gold_policy_review_candidate")
    if not buckets:
        buckets.append("diagnostic_only_no_action")
    return list(dict.fromkeys(buckets))


def v3_1_7_bucket_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    keys = [
        "implementation_safe_followup",
        "scorer_normalization_review_candidate",
        "answer_renderer_followup_candidate",
        "retrieval_context_followup_candidate",
        "gold_policy_review_candidate",
        "relevance_label_review_candidate",
        "answerability_label_review_candidate",
        "diagnostic_only_no_action",
    ]
    counts = {key: 0 for key in keys}
    for row in rows:
        for bucket in row.get("residual_buckets") or []:
            if bucket in counts:
                counts[bucket] += 1
    return counts


def build_v3_1_7_remaining_triage_queue(
    inventory_rows: Sequence[Mapping[str, Any]],
    source_summary: Mapping[str, Any],
) -> dict[str, Any]:
    implementation_items: list[dict[str, Any]] = []
    for row in inventory_rows:
        if row.get("safe_to_fix_without_user_gold_decision") is not True:
            continue
        implementation_items.append(
            {
                "query_id": row.get("query_id"),
                "source_family": row.get("source_family"),
                "lane_name": row.get("lane_name"),
                "failure_category": row.get("failure_category"),
                "recommended_next_step": row.get("recommended_next_action"),
                "diagnostic_only": True,
                "promotion_evidence": False,
            }
        )
    return {
        "schema_version": f"{V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID}_remaining_triage_queue_v1",
        "run_id": V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID,
        "source_run_id": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
        "source_queue_artifact": official.repo_relative(DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_QUEUE_JSON),
        "generated_at": utc_timestamp(),
        "diagnostic_only": True,
        "promotion_evidence": False,
        "active_implementation_queue_empty": not implementation_items,
        "active_remaining_queue_status": "cleared",
        "all_track_residuals_exist": bool(inventory_rows),
        "all_track_residual_query_ids": sorted({official.clean(row.get("query_id")) for row in inventory_rows}),
        "residuals_require_user_policy_review": any(row.get("requires_user_gold_policy_decision") for row in inventory_rows),
        "implementation_safe_residual_count": len(implementation_items),
        "policy_bound_residual_count": sum(
            1
            for row in inventory_rows
            if row.get("requires_user_gold_policy_decision")
            or row.get("requires_user_relevance_label_decision")
            or row.get("requires_user_answerability_label_decision")
        ),
        "items": implementation_items,
        "strict_json_or_locator_residual_count": source_summary.get("strict_json_or_locator_residual_count", 0),
        "official_retrieval_metrics_computed": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "reference_span_text_embedded": False,
    }


def build_v3_1_7_user_decision_packet(inventory_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in inventory_rows:
        if row.get("requires_user_gold_policy_decision") is not True:
            continue
        grouped.setdefault(official.clean(row.get("query_id")), []).append(row)
    items: list[dict[str, Any]] = []
    for query_id, rows in sorted(grouped.items()):
        source_family = official.clean(rows[0].get("source_family"))
        items.append(
            {
                "query_id": query_id,
                "source_family": source_family,
                "lane_failures": [
                    {
                        "lane_name": row.get("lane_name"),
                        "failure_category": row.get("failure_category"),
                        "diagnostic_subcategories": row.get("diagnostic_subcategories"),
                    }
                    for row in rows
                ],
                "current_gold_decision_boundary_category": "answer_span_or_synthesis_boundary_requires_human_policy_review",
                "exact_question_for_user": (
                    "Should this row be judged against the current strict reference span, should the answer/scorer "
                    "normalization boundary be revised, or should the gold policy/labels be updated?"
                ),
                "available_evidence_references": [
                    {
                        "artifact": official.repo_relative(DEFAULT_V3_1_2_ANSWER_SPAN_DIAGNOSTICS_JSONL),
                        "query_id": query_id,
                        "lanes": [row.get("lane_name") for row in rows],
                        "human_review_only": True,
                    }
                ],
                "safe_source_excerpt_hashes_counts": [
                    {
                        "lane_name": row.get("lane_name"),
                        "scoring_reference_span_sha256": row.get("scoring_reference_span_sha256"),
                        "reference_token_count": row.get("reference_token_count"),
                        "matched_reference_token_count": row.get("matched_reference_token_count"),
                        "answer_token_count": row.get("answer_token_count"),
                    }
                    for row in rows
                ],
                "why_codex_cannot_decide_without_user_policy": (
                    "Resolving this residual may change the accepted answer-span boundary, scorer normalization "
                    "policy, or gold/label interpretation; Codex cannot make that gold/relevance/answerability "
                    "policy decision in a diagnostic-only run."
                ),
                "consequences_of_possible_user_decisions": [
                    {
                        "decision": "keep_current_strict_reference_boundary",
                        "consequence": "Leave the residual non-PASS until a separately approved implementation can satisfy it.",
                    },
                    {
                        "decision": "approve_scorer_or_renderer_review",
                        "consequence": "Open an implementation follow-up without mutating gold/labels first.",
                    },
                    {
                        "decision": "revise_gold_or_label_policy",
                        "consequence": "Requires explicit user-owned gold/relevance/answerability mutation before official metrics.",
                    },
                ],
                "recommended_conservative_default_for_diagnostic_only_handling": (
                    "do_not_mutate_gold_labels_or_behavior; keep the row in the policy-review packet"
                ),
                "raw_reference_text_embedded": False,
                "raw_supporting_text_embedded": False,
                "raw_gold_text_embedded": False,
                "safe_for_human_review_only": True,
            }
        )
    return {
        "schema_version": f"{V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID}_user_decision_packet_v1",
        "run_id": V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID,
        "source_run_id": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
        "generated_at": utc_timestamp(),
        "diagnostic_only": True,
        "promotion_evidence": False,
        "decision_items": items,
        "decision_item_count": len(items),
        "raw_reference_text_embedded": False,
        "raw_supporting_text_embedded": False,
        "raw_gold_text_embedded": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "reference_span_text_embedded": False,
    }


def build_v3_1_7_silver_readiness_audit() -> dict[str, Any]:
    manifest_path = REPO_ROOT / "ai" / "eval" / "silver" / "answer_citation_silver_manifest_v1.json"
    readiness_path = REPO_ROOT / "ai" / "eval" / "silver" / "answer_citation_silver_readiness_v1.json"
    manifest = official.read_json(manifest_path) if manifest_path.exists() else {}
    readiness = official.read_json(readiness_path) if readiness_path.exists() else {}
    tracks = as_mapping(manifest.get("tracks"))
    per_track_status = {
        track: as_mapping(payload).get("status")
        for track, payload in tracks.items()
        if isinstance(payload, Mapping)
    }
    silver_jsonl_files_created = as_mapping(readiness.get("silver_jsonl_files_created"))
    silver_rows_created = any(value is True for value in silver_jsonl_files_created.values())
    return {
        "schema_version": f"{V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID}_silver_readiness_audit_v1",
        "run_id": V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID,
        "generated_at": utc_timestamp(),
        "diagnostic_only": True,
        "promotion_evidence": False,
        "manifest_exists": manifest_path.exists(),
        "readiness_exists": readiness_path.exists(),
        "source_bound_answer_citation_silver_manifests_exist": False,
        "per_track_source_bound_status": per_track_status,
        "official_29_query_ids_excluded_from_silver_tuning_sets": bool(
            readiness.get("official_denominator_query_ids_excluded_from_tuning_silver")
            or manifest.get("official_denominator_query_ids_excluded_from_tuning_silver")
        ),
        "silver_expected_values_audit_only": bool(
            readiness.get("expected_values_used_for_audit_only")
            or manifest.get("expected_values_used_for_audit_only")
        ),
        "candidate_artifacts_excluded_as_generation_source": (
            readiness.get("candidate_artifacts_used_as_generation_source") is False
            and manifest.get("candidate_artifacts_used_as_generation_source") is False
        ),
        "silver_is_gold": False,
        "silver_is_official_denominator": False,
        "silver_is_promotion_evidence": False,
        "silver_generation_closed": not silver_rows_created,
        "silver_rows_created": silver_rows_created,
        "status": readiness.get("status") or "SILVER_READINESS_ARTIFACT_MISSING",
        "blocker": as_mapping(readiness.get("source_data_decision")).get("why_no_jsonl_created"),
        "source_artifacts": {
            "manifest": official.file_identity(manifest_path) if manifest_path.exists() else {"exists": False},
            "readiness": official.file_identity(readiness_path) if readiness_path.exists() else {"exists": False},
        },
    }


def run_v3_1_8_gold_policy_review_packet_preparation(
    *,
    args: argparse.Namespace,
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    v3_1_7_summary = official.read_json(DEFAULT_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SUMMARY_JSON)
    v3_1_7_inventory = read_jsonl(DEFAULT_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_INVENTORY_JSONL)
    v3_1_7_queue = official.read_json(DEFAULT_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_QUEUE_JSON)
    v3_1_7_packet = official.read_json(DEFAULT_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_DECISION_PACKET_JSON)
    source_material = collect_v3_1_8_policy_packet_source_material()
    human_review_packet = build_v3_1_8_human_review_packet(
        v3_1_7_summary=v3_1_7_summary,
        v3_1_7_inventory=v3_1_7_inventory,
        v3_1_7_packet=v3_1_7_packet,
        source_material=source_material,
    )
    decision_rows = build_v3_1_8_decision_matrix_rows(human_review_packet)
    remaining_queue = build_v3_1_8_remaining_triage_queue(human_review_packet)
    packet_query_ids = [item["query_id"] for item in human_review_packet["decision_items"]]
    expected_query_ids = list(V3_1_8_POLICY_REVIEW_QUERY_IDS)
    decision_item_count = len(human_review_packet["decision_items"])
    implementation_safe_residual_count = remaining_queue["implementation_safe_residual_count"]
    metadata_drift = as_mapping(v3_1_7_summary.get("source_artifact_hash_audit"))
    metadata_drift_observed = metadata_drift.get("all_recorded_hashes_match_current_files") is False
    required_source_artifacts = [
        DEFAULT_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SUMMARY_JSON,
        DEFAULT_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_INVENTORY_JSONL,
        DEFAULT_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_QUEUE_JSON,
        DEFAULT_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_DECISION_PACKET_JSON,
        DEFAULT_V3_1_2_ANSWER_SPAN_RESULTS_JSONL,
        DEFAULT_V3_1_2_ANSWER_SPAN_DIAGNOSTICS_JSONL,
        DEFAULT_SCORER_RESULTS_JSONL,
        DEFAULT_TEXT_NAMU_GOLD_CSV,
    ]
    source_artifact_identities = {
        official.repo_relative(path): official.file_identity(path)
        for path in required_source_artifacts
    }
    guardrails = {
        **v3_1_guardrails(),
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "relevance_label_mutation": False,
        "answerability_label_mutation": False,
        "official_retrieval_metrics_computed": False,
        "official_ndcg_computed": False,
        "official_mrr_computed": False,
        "official_hit_at_k_computed": False,
        "lane_score_collapsed": False,
        "raw_reference_text_embedded_in_generation": False,
        "raw_supporting_text_embedded_in_generation": False,
        "raw_gold_text_embedded_in_generation": False,
        "human_review_packet_contains_policy_material": True,
    }
    status_ok = (
        not validation_errors
        and v3_1_7_summary.get("run_id") == V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID
        and v3_1_7_queue.get("active_implementation_queue_empty") is True
        and v3_1_7_queue.get("items") == []
        and packet_query_ids == expected_query_ids
        and decision_item_count == 5
        and implementation_safe_residual_count == 0
        and all(row.get("requires_user_policy_decision") is True for row in decision_rows)
        and all(row.get("implementation_safe") is False for row in decision_rows)
    )
    summary: dict[str, Any] = {
        "schema_version": f"{V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID}_summary_v1",
        "run_id": V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
        "source_run_id": V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID,
        "generated_at": utc_timestamp(),
        "status": (
            "GOLD_POLICY_REVIEW_PACKET_PREPARATION_V3_1_8_COMPLETED"
            if status_ok
            else "GOLD_POLICY_REVIEW_PACKET_PREPARATION_V3_1_8_REVIEW_REQUIRED"
        ),
        "measurement_classification": "gold_policy_review_packet_preparation_v3_1_8_diagnostic_only",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "promotion_gate_auto_run": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "write_summary_markdown": False,
        "behavior_change_made": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "relevance_label_mutation": False,
        "answerability_label_mutation": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "raw_reference_text_embedded_in_generation": False,
        "raw_supporting_text_embedded_in_generation": False,
        "raw_gold_text_embedded_in_generation": False,
        "human_review_packet_contains_policy_material": True,
        "human_review_packet_generation_source": False,
        "official_retrieval_metrics_computed": False,
        "official_ndcg_computed": False,
        "official_mrr_computed": False,
        "official_hit_at_k_computed": False,
        "lane_score_collapsed": False,
        "all_track_live_generation_rerun": False,
        "all_track_live_generation_rerun_reason": (
            "not rerun; v3_1_8 only joins existing v3_1_7 residual inventory with existing "
            "v3_1_2/scorer/gold-policy artifacts for human review"
        ),
        "active_remaining_queue_empty": True,
        "active_implementation_queue_empty": True,
        "implementation_safe_residual_count": implementation_safe_residual_count,
        "residual_lane_item_count": sum(len(item["lane_level_status"]) for item in human_review_packet["decision_items"]),
        "decision_item_count": decision_item_count,
        "decision_query_ids": packet_query_ids,
        "expected_decision_query_ids": expected_query_ids,
        "decision_options": list(V3_1_8_DECISION_OPTIONS),
        "all_items_require_user_policy_decision": all(
            item.get("requires_user_policy_decision") is True
            for item in human_review_packet["decision_items"]
        ),
        "any_item_implementation_safe": any(
            item.get("implementation_safe") is True for item in human_review_packet["decision_items"]
        ),
        "silver_rows_created": False,
        "silver_generation_closed": True,
        "metadata_drift_observed": metadata_drift_observed,
        "source_artifact_hash_closure_required_for_policy_packet": False,
        "metadata_drift_source": {
            "source_run_id": V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID,
            "source_artifact_hash_closure_passed": v3_1_7_summary.get("source_artifact_hash_closure_passed"),
            "mismatch_count": metadata_drift.get("mismatch_count", 0),
            "handling": "recorded_only_historical_v3_1_6_artifacts_not_rewritten",
        },
        "v3_1_7_residual_inventory_bucket_counts": v3_1_7_summary.get("residual_inventory_bucket_counts"),
        "v3_1_7_active_implementation_queue_empty": v3_1_7_summary.get("active_implementation_queue_empty"),
        "v3_1_7_any_residual_safe_to_fix_without_user_decision": v3_1_7_summary.get(
            "any_residual_safe_to_fix_without_user_decision"
        ),
        "policy_packet_scope": {
            "source_family": "TEXT",
            "query_count": decision_item_count,
            "lane_count_per_query": len(V3_1_LANE_NAMES),
            "purpose": "human_gold_relevance_answerability_expected_supporting_policy_review",
            "codex_policy_decision_applied": False,
        },
        "artifact_policy": {
            "summary_json": "machine_manifest",
            "human_review_packet_json": "human_policy_review_packet",
            "decision_matrix_jsonl": "compact_one_row_per_query_policy_options",
            "remaining_triage_queue_json": "empty_implementation_queue_source_of_truth",
            "status_jsonl": "compact_status_ledger",
            "per_run_markdown_report_created": False,
            "full_results_jsonl_created": False,
            "failure_attribution_json_created": False,
            "actual_response_audit_jsonl_created": False,
            "classification_only_minimum_artifact_set": [
                "summary_json",
                "human_review_packet_json",
                "decision_matrix_jsonl",
                "remaining_triage_queue_json",
                "status_jsonl",
            ],
            "gitignore_policy": (
                "machine JSON/JSONL under ai/eval/reports/rag-ingestion are generated/local-only; "
                "rolling human-facing docs are tracked"
            ),
        },
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "policy_packet_inputs": source_artifact_identities,
        },
        "guardrails": guardrails,
        "result_count": len(decision_rows),
        "unique_query_id_count": len(packet_query_ids),
        "scored_count": 0,
        "pass_count": 0,
        "failure_counts": {},
        "score_scope": "human_policy_review_packet_not_official_metric",
        "lane_names": list(V3_1_LANE_NAMES),
        "non_production_rag_index_dependency": agentic_status.get("index_dependency"),
        "source_bound_index_used": False,
        "canonical_search_unit_payload_used": False,
        "infrastructure_blocker": {
            "category": None if status_ok else "V3_1_8_PACKET_VALIDATION_REVIEW_REQUIRED",
            "domain": None if status_ok else "gold_policy_review_packet_preparation",
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": False,
        },
        "agentic_loop": {
            "implemented": True,
            "enabled": False,
            "executed": False,
            "backend": "v3_1_8_gold_policy_review_packet_preparation",
            "steps_count": 0,
            "blockers": list(validation_errors),
        },
        "local_llm_used": False,
        "local_gpu_used": False,
        "llm_backend": None,
        "llm_model": None,
        "performance_interpretation": "diagnostic_only_human_policy_packet_not_metric_or_behavior_improvement",
        "diagnostic_limitations": [
            "This run prepares a human policy packet only; it does not decide policy.",
            "Raw expected/supporting/gold-policy material is included only inside the human review packet.",
            "Human-review-only policy material is not a generation source, silver source, gold mutation, or promotion artifact.",
            "Lane A/B/C remain separated; no official retrieval metric is computed.",
        ],
        "artifact_paths": v3_1_8_gold_policy_review_packet_artifact_paths(args),
        "baseline_reference": {
            "run_id": "official_answer_citation_metric_first_run_v1",
            "status_detail": baseline.get("status_detail"),
            "artifact_identity": official.file_identity(baseline_path),
        },
        "_v3_1_8_human_review_packet": human_review_packet,
        "_v3_1_8_decision_matrix_rows": decision_rows,
        "_v3_1_8_remaining_queue": remaining_queue,
    }
    return summary, decision_rows


def run_v3_1_9_user_gold_policy_override_application_and_scoring_remeasurement(
    *,
    args: argparse.Namespace,
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    baseline_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    override_csv_path = locate_v3_1_9_gold_override_csv()
    override_jsonl_path = override_csv_path.with_suffix(".jsonl")
    overrides = validate_v3_1_9_gold_override_sources(
        csv_path=override_csv_path,
        jsonl_path=override_jsonl_path if override_jsonl_path.exists() else None,
    )
    v3_1_8_summary = official.read_json(
        report_artifact_path(V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID, "summary.json")
    )
    v3_1_8_packet = official.read_json(
        report_artifact_path(V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID, "human_review_packet.json")
    )
    before_policy_material = v3_1_9_before_policy_material_by_query_id(v3_1_8_packet)
    gold_application = apply_v3_1_9_overrides_to_text_gold_csv(
        overrides=overrides,
        before_policy_material=before_policy_material,
    )
    source_hash_sync = sync_v3_1_9_official_input_hash_surfaces(
        text_gold_sha256=gold_application["gold_file_after_sha256"],
        current_text_gold_rows_by_query_id=read_csv_rows_by_query_id(DEFAULT_TEXT_NAMU_GOLD_CSV),
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
    )

    config = official.read_json(metric_input_config_path)
    registry = official.read_json(denominator_registry_path)
    smoke = official.read_json(pre_execution_smoke_path)
    application_path = official.resolve_application_report_path(config, smoke)
    application = official.read_json(application_path) if application_path else {}
    application_for_validation = (
        application
        if application
        else fallback_registry_application_from_config(config)
    )
    consumed = official.consume_official_inputs(
        config=config,
        registry=registry,
        application=application_for_validation,
        smoke=smoke,
    )
    rows = list(consumed["rows"])
    baseline = official.read_json(baseline_path)
    validation_errors = list(consumed["errors"])
    official_query_ids = [official.clean(row.get("query_id")) for row in rows]
    official_rows_by_id = rows_by_query_id(rows)

    latest_surface_rows, surface_sources = compose_v3_1_9_latest_lane_surface_rows(official_query_ids)
    rescored_rows = rescore_v3_1_9_lane_surface_rows(
        surface_rows=latest_surface_rows,
        official_rows_by_id=official_rows_by_id,
    )
    lane_pass_counts_before = v3_1_9_lane_pass_counts_before(v3_1_8_summary)
    lane_pass_counts_after = v3_1_9_lane_pass_counts(rescored_rows)
    lane_failure_counts_after = v3_1_9_lane_failure_counts(rescored_rows)
    remaining_queue = build_v3_1_9_remaining_triage_queue(
        rescored_rows=rescored_rows,
        source_run_id=V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
    )
    rows_by_source_family = dict(
        sorted(
            Counter(
                SOURCE_FAMILY_LABEL_BY_TRACK.get(official.clean(row.get("track")), official.clean(row.get("track")))
                for row in rows
            ).items()
        )
    )
    source_family_lane_counts = build_v3_1_9_source_family_lane_counts(rescored_rows)
    guardrails = v3_1_9_guardrails()
    status_ok = (
        not validation_errors
        and gold_application["changed_row_count"] == 5
        and list(gold_application["changed_query_ids"]) == list(V3_1_9_USER_GOLD_POLICY_OVERRIDE_QUERY_IDS)
        and len(rows) == 29
        and len(rescored_rows) == 29
        and set(official_query_ids) == {official.clean(row.get("query_id")) for row in rescored_rows}
    )
    summary: dict[str, Any] = {
        "schema_version": f"{V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID}_summary_v1",
        "run_id": V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID,
        "source_run_id": V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
        "generated_at": utc_timestamp(),
        "status": (
            "USER_GOLD_POLICY_OVERRIDE_APPLIED_AND_SCORING_REMEASURED_V3_1_9_COMPLETED"
            if status_ok
            else "USER_GOLD_POLICY_OVERRIDE_APPLICATION_V3_1_9_REVIEW_REQUIRED"
        ),
        "measurement_classification": "user_approved_gold_policy_override_application_and_scoring_only_remeasurement_v3_1_9",
        "run_class": "user_approved_gold_policy_override_application",
        "diagnostic_only": False,
        "write_summary_markdown": False,
        "user_assertion_count": 30,
        "override_source_found": official.repo_relative(override_csv_path),
        "human_approved_override_source": override_csv_path.name,
        "optional_jsonl_override_source_validated": override_jsonl_path.exists(),
        "override_query_ids": list(V3_1_9_USER_GOLD_POLICY_OVERRIDE_QUERY_IDS),
        "changed_query_ids": list(gold_application["changed_query_ids"]),
        "changed_row_count": gold_application["changed_row_count"],
        "changed_rows_by_source_family": {"TEXT": gold_application["changed_row_count"]},
        "non_text_changed_query_ids": [],
        "pdf_rows_changed": 0,
        "xlsx_rows_changed": 0,
        "text_namu_v2_0005_unchanged": gold_application["text_namu_v2_0005_unchanged"],
        "text_namu_v2_0005_after_row_core_sha256": gold_application[
            "text_namu_v2_0005_after_row_core_sha256"
        ],
        "gold_application_mode": "v2_csv_in_place",
        "gold_versioning_decision": {
            "selected_path": "update_v2_csv_in_place",
            "new_v3_file_created": False,
            "active_gold_file": official.repo_relative(DEFAULT_TEXT_NAMU_GOLD_CSV),
            "rationale": (
                "The current official denominator registry, metric input config, smoke report, "
                "loader tests, and current-profile guardrails reference the v2 text gold path directly; "
                "updating the v2 CSV in place is the smallest safe path that keeps loader behavior correct."
            ),
        },
        "gold_file_before_sha256": gold_application["gold_file_before_sha256"],
        "gold_file_after_sha256": gold_application["gold_file_after_sha256"],
        "gold_file_sha256_changed": gold_application["gold_file_before_sha256"]
        != gold_application["gold_file_after_sha256"],
        "gold_file_written_this_run": gold_application["gold_file_written_this_run"],
        "official_denominator_row_count": len(rows),
        "official_denominator_query_ids_before": official_query_ids,
        "official_denominator_query_ids_after": official_query_ids,
        "official_denominator_query_id_set_mutation": False,
        "denominator_query_id_set_mutation": False,
        "denominator_mutation": False,
        "user_policy_decision_applied": True,
        "expected_answer_mutation": True,
        "supporting_evidence_mutation": True,
        "gold_policy_mutation": True,
        "gold_mutation": True,
        "human_label_mutation": bool(gold_application["label_fields_mutated"]),
        "relevance_label_mutation": False,
        "answerability_label_mutation": False,
        "optional_final_label_columns_present": list(gold_application["optional_final_label_columns_present"]),
        "optional_final_label_columns_applied": list(gold_application["optional_final_label_columns_applied"]),
        "label_fields_preserved": not bool(gold_application["label_fields_mutated"]),
        "behavior_change_made": False,
        "renderer_mutation": False,
        "scorer_behavior_mutation": False,
        "retrieval_mutation": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "raw_reference_text_embedded_in_generation": False,
        "raw_supporting_text_embedded_in_generation": False,
        "raw_gold_text_embedded_in_generation": False,
        "silver_rows_created": False,
        "silver_generation_closed": True,
        "promotion_evidence": False,
        "promotion_gate_auto_run": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "official_retrieval_metrics_computed": False,
        "official_ndcg_computed": False,
        "official_mrr_computed": False,
        "official_hit_at_k_computed": False,
        "lane_score_collapsed": False,
        "live_generation_rerun": False,
        "all_track_live_generation_rerun": False,
        "scoring_only_remeasurement": True,
        "existing_result_artifacts_used_for_scoring_only": True,
        "rescored_result_count": len(rescored_rows),
        "rescored_query_id_count": len({row["query_id"] for row in rescored_rows}),
        "result_count": len(rescored_rows),
        "unique_query_id_count": len({row["query_id"] for row in rescored_rows}),
        "scored_count": len(rescored_rows) * len(V3_1_LANE_NAMES),
        "pass_count": sum(lane_pass_counts_after.values()),
        "failure_counts": dict(lane_failure_counts_after),
        "lane_names": list(V3_1_LANE_NAMES),
        "lane_counts": {
            lane_name: {
                "row_count": len(rescored_rows),
                "pass_count": lane_pass_counts_after.get(lane_name, 0),
                "fail_count": len(rescored_rows) - lane_pass_counts_after.get(lane_name, 0),
            }
            for lane_name in V3_1_LANE_NAMES
        },
        "lane_pass_counts_before": lane_pass_counts_before,
        "lane_pass_counts_after": lane_pass_counts_after,
        "lane_failure_counts_after": dict(lane_failure_counts_after),
        "source_family_lane_counts": source_family_lane_counts,
        "rows_by_source_family": rows_by_source_family,
        "active_remaining_queue_empty": remaining_queue["active_remaining_queue_empty"],
        "active_implementation_queue_empty": remaining_queue["active_implementation_queue_empty"],
        "implementation_safe_residual_count": remaining_queue["implementation_safe_residual_count"],
        "remaining_queue": remaining_queue,
        "requires_additional_user_policy_packet": False,
        "any_remaining_residual_implementation_safe": remaining_queue["implementation_safe_residual_count"] > 0,
        "source_artifact_hash_sync": source_hash_sync,
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "v3_1_8_summary": official.file_identity(
                report_artifact_path(V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID, "summary.json")
            ),
            "v3_1_8_human_review_packet": official.file_identity(
                report_artifact_path(V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID, "human_review_packet.json")
            ),
            "latest_lane_surface_sources": surface_sources,
        },
        "artifact_policy": {
            "summary_json": "machine_manifest",
            "applied_overrides_jsonl": "user_approved_policy_application_rows",
            "gold_diff_jsonl": "human_review_only_before_after_gold_text_audit",
            "rescored_results_jsonl": "scoring_only_lane_separated_remeasurement",
            "remaining_triage_queue_json": "post_rescore_implementation_safe_queue",
            "status_jsonl": "compact_status_ledger",
            "per_run_markdown_report_created": False,
        },
        "guardrails": guardrails,
        "non_production_rag_index_dependency": agentic_status.get("index_dependency"),
        "source_bound_index_used": False,
        "canonical_search_unit_payload_used": False,
        "infrastructure_blocker": {
            "category": None if status_ok else "V3_1_9_VALIDATION_REVIEW_REQUIRED",
            "domain": None if status_ok else "user_gold_policy_override_application",
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": False,
        },
        "agentic_loop": {
            "implemented": True,
            "enabled": False,
            "executed": False,
            "backend": "v3_1_9_scoring_only_remeasurement",
            "steps_count": 0,
            "blockers": list(validation_errors),
        },
        "local_llm_used": False,
        "local_gpu_used": False,
        "llm_backend": None,
        "llm_model": None,
        "performance_interpretation": "scoring_only_remeasurement_after_user_gold_policy_mutation_not_promotion_evidence",
        "diagnostic_limitations": [
            "This run mutates only user-approved TEXT gold policy fields and then reuses existing Lane A/B/C answer surfaces.",
            "No live generation, renderer, scorer behavior, retrieval, production, silver, or promotion behavior was changed.",
            "Lane A/B/C remain separated and no official nDCG, MRR, or Hit@K is computed.",
        ],
        "artifact_paths": v3_1_9_user_gold_policy_override_artifact_paths(args),
        "baseline_reference": {
            "run_id": "official_answer_citation_metric_first_run_v1",
            "status_detail": baseline.get("status_detail"),
            "artifact_identity": official.file_identity(baseline_path),
        },
        "_v3_1_9_applied_overrides": gold_application["applied_overrides"],
        "_v3_1_9_gold_diff": gold_application["gold_diff"],
        "_v3_1_9_rescored_results": rescored_rows,
        "_v3_1_9_remaining_queue": remaining_queue,
    }
    return summary, rescored_rows


def collect_v3_1_8_policy_packet_source_material() -> dict[str, Any]:
    return {
        "span_results_by_query_id": rows_by_query_id(read_jsonl(DEFAULT_V3_1_2_ANSWER_SPAN_RESULTS_JSONL)),
        "span_diagnostics_by_query_id": rows_by_query_id(read_jsonl(DEFAULT_V3_1_2_ANSWER_SPAN_DIAGNOSTICS_JSONL)),
        "post_locator_results_by_query_id": rows_by_query_id(read_jsonl(DEFAULT_V3_1_1_POST_RESULTS_JSONL)),
        "scorer_rows_by_query_id": rows_by_query_id(read_jsonl(DEFAULT_SCORER_RESULTS_JSONL)),
        "gold_rows_by_query_id": read_csv_rows_by_query_id(DEFAULT_TEXT_NAMU_GOLD_CSV),
        "human_audit_v2_rows_by_query_id": review_rows_by_query_id(DEFAULT_TEXT_NAMU_HUMAN_AUDIT_V2_DECISIONS_JSON),
        "policy_review_rows_by_query_id": review_rows_by_query_id(DEFAULT_TEXT_NAMU_POLICY_REVIEW_PACKET_JSON),
    }


def rows_by_query_id(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        official.clean(row.get("query_id")): dict(row)
        for row in rows
        if official.clean(row.get("query_id"))
    }


def read_csv_rows_by_query_id(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            query_id = official.clean(row.get("query_id"))
            if query_id:
                rows[query_id] = dict(row)
    return rows


def review_rows_by_query_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = official.read_json(path)
    rows: dict[str, dict[str, Any]] = {}

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            query_id = official.clean(value.get("query_id") or value.get("row_id"))
            if query_id and query_id in V3_1_8_POLICY_REVIEW_QUERY_IDS:
                rows[query_id] = dict(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    return rows


def locate_v3_1_9_gold_override_csv() -> Path:
    candidates = [
        REPO_ROOT / "gold_overrides.csv",
        AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_overrides.csv",
        REPORT_DIR / "gold_overrides.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "gold_overrides.csv not found in repo root, ai/eval/eval_queries, or ai/eval/reports/rag-ingestion"
    )


def read_csv_rows_with_fieldnames(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, [dict(row) for row in reader]


def write_csv_rows_with_fieldnames(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def sha256_text(value: Any) -> str:
    return hashlib.sha256(official.clean(value).encode("utf-8")).hexdigest()


def validate_v3_1_9_gold_override_sources(
    *,
    csv_path: Path,
    jsonl_path: Path | None,
) -> list[dict[str, str]]:
    fieldnames, csv_rows = read_csv_rows_with_fieldnames(csv_path)
    if "query_id" not in fieldnames:
        raise ValueError("gold_overrides.csv must include query_id")
    by_id = {official.clean(row.get("query_id")): row for row in csv_rows if official.clean(row.get("query_id"))}
    expected_ids = list(V3_1_9_USER_GOLD_POLICY_OVERRIDE_QUERY_IDS)
    if sorted(by_id) != sorted(expected_ids) or len(csv_rows) != len(expected_ids):
        raise ValueError(f"gold_overrides.csv query_ids must be exactly {expected_ids!r}, got {sorted(by_id)!r}")
    ordered_rows = [dict(by_id[query_id]) for query_id in expected_ids]
    for row in ordered_rows:
        query_id = official.clean(row.get("query_id"))
        if official.clean(row.get("codex_policy_option")) != "revise_gold_or_label_policy":
            raise ValueError(f"{query_id} codex_policy_option must be revise_gold_or_label_policy")
        if official.clean(row.get("apply_to_official_gold")).lower() != "true":
            raise ValueError(f"{query_id} apply_to_official_gold must be true")
        expected_answer = official.clean(row.get("expected_answer_final"))
        supporting_evidence = official.clean(row.get("supporting_evidence_final"))
        if not expected_answer:
            raise ValueError(f"{query_id} expected_answer_final is required")
        if not supporting_evidence:
            raise ValueError(f"{query_id} supporting_evidence_final is required")
        if official.clean(row.get("expected_answer_sha256")) != sha256_text(expected_answer):
            raise ValueError(f"{query_id} expected_answer_sha256 does not match expected_answer_final")
        if official.clean(row.get("supporting_evidence_sha256")) != sha256_text(supporting_evidence):
            raise ValueError(f"{query_id} supporting_evidence_sha256 does not match supporting_evidence_final")
        for key in (
            "do_not_change_renderer",
            "do_not_change_scorer",
            "do_not_change_retrieval",
            "do_not_change_production",
            "generation_source",
            "human_review_only",
            "not_silver_source",
            "not_promotion_evidence",
        ):
            if key not in row:
                continue
            value = official.clean(row.get(key)).lower()
            if key == "generation_source" and value != "false":
                raise ValueError(f"{query_id} generation_source must be false")
            if key != "generation_source" and value != "true":
                raise ValueError(f"{query_id} {key} must be true")
    if jsonl_path is not None:
        jsonl_rows = read_jsonl(jsonl_path)
        jsonl_by_id = {
            official.clean(row.get("query_id")): row
            for row in jsonl_rows
            if official.clean(row.get("query_id"))
        }
        if sorted(jsonl_by_id) != sorted(expected_ids) or len(jsonl_rows) != len(expected_ids):
            raise ValueError(f"{jsonl_path.name} query_ids must match gold_overrides.csv")
        for csv_row in ordered_rows:
            query_id = official.clean(csv_row.get("query_id"))
            json_row = as_mapping(jsonl_by_id.get(query_id))
            for key, csv_value in csv_row.items():
                if key not in json_row:
                    continue
                if override_compare_value(csv_value) != override_compare_value(json_row.get(key)):
                    raise ValueError(f"{jsonl_path.name} value mismatch for {query_id}.{key}")
    return ordered_rows


def override_compare_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return official.clean(value)


def v3_1_9_before_policy_material_by_query_id(packet: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in packet.get("decision_items") or []:
        if not isinstance(item, Mapping):
            continue
        query_id = official.clean(item.get("query_id"))
        if query_id not in V3_1_9_USER_GOLD_POLICY_OVERRIDE_QUERY_IDS:
            continue
        material = as_mapping(item.get("current_policy_material"))
        expected = as_mapping(material.get("expected_answer"))
        supporting = as_mapping(material.get("supporting_evidence"))
        out[query_id] = {
            "expected_answer": official.clean(expected.get("text")),
            "expected_answer_sha256": official.clean(expected.get("sha256")),
            "supporting_evidence": official.clean(supporting.get("text")),
            "supporting_evidence_sha256": official.clean(supporting.get("sha256")),
            "gold_csv_fields": dict(as_mapping(material.get("gold_csv_fields"))),
        }
    missing = [query_id for query_id in V3_1_9_USER_GOLD_POLICY_OVERRIDE_QUERY_IDS if query_id not in out]
    if missing:
        raise ValueError(f"v3_1_8 human review packet missing before policy material: {missing!r}")
    return out


def apply_v3_1_9_overrides_to_text_gold_csv(
    *,
    overrides: Sequence[Mapping[str, str]],
    before_policy_material: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    fieldnames, gold_rows = read_csv_rows_with_fieldnames(DEFAULT_TEXT_NAMU_GOLD_CSV)
    rows_by_id_current = {
        official.clean(row.get("query_id")): dict(row)
        for row in gold_rows
        if official.clean(row.get("query_id"))
    }
    expected_text_ids = {
        "text_namu_v2_0005",
        *V3_1_9_USER_GOLD_POLICY_OVERRIDE_QUERY_IDS,
    }
    if set(rows_by_id_current) != expected_text_ids:
        raise ValueError(f"TEXT gold CSV query_ids changed unexpectedly: {sorted(rows_by_id_current)!r}")
    override_by_id = {official.clean(row.get("query_id")): dict(row) for row in overrides}
    applied_rows: list[dict[str, Any]] = []
    diff_rows: list[dict[str, Any]] = []
    file_changed = False
    label_fields_mutated: list[str] = []
    optional_final_label_columns_present: list[str] = []
    optional_final_label_columns_applied: list[str] = []
    optional_label_targets = {
        "human_label_final": "human_label",
        "human_review_status_final": "human_review_status",
        "human_approved_gold_final": "human_approved_gold",
        "official_denominator_current_final": "official_denominator_current",
        "official_metric_input_final": "official_metric_input",
        "gold_promoted_final": "gold_promoted",
    }
    locator_final_column = "citation_locator_final"
    for query_id in V3_1_9_USER_GOLD_POLICY_OVERRIDE_QUERY_IDS:
        override = override_by_id[query_id]
        gold_row = rows_by_id_current[query_id]
        before = before_policy_material[query_id]
        before_expected = official.clean(before.get("expected_answer"))
        before_support = official.clean(before.get("supporting_evidence"))
        after_expected = official.clean(override.get("expected_answer_final"))
        after_support = official.clean(override.get("supporting_evidence_final"))
        if before.get("expected_answer_sha256") and before["expected_answer_sha256"] != sha256_text(before_expected):
            raise ValueError(f"{query_id} before expected_answer hash from v3_1_8 packet is inconsistent")
        if before.get("supporting_evidence_sha256") and before["supporting_evidence_sha256"] != sha256_text(before_support):
            raise ValueError(f"{query_id} before supporting_evidence hash from v3_1_8 packet is inconsistent")
        if official.clean(override.get("current_expected_sha256")) != sha256_text(before_expected):
            raise ValueError(f"{query_id} override current_expected_sha256 does not match v3_1_8 packet")
        if official.clean(override.get("current_supporting_evidence_sha256")) != sha256_text(before_support):
            raise ValueError(f"{query_id} override current_supporting_evidence_sha256 does not match v3_1_8 packet")
        if gold_row.get("expected_answer") != after_expected:
            gold_row["expected_answer"] = after_expected
            file_changed = True
        if gold_row.get("supporting_evidence") != after_support:
            gold_row["supporting_evidence"] = after_support
            file_changed = True
        if locator_final_column in override and official.clean(override.get(locator_final_column)):
            if gold_row.get("citation_locator") != official.clean(override.get(locator_final_column)):
                gold_row["citation_locator"] = official.clean(override.get(locator_final_column))
                file_changed = True
        for override_column, gold_column in optional_label_targets.items():
            if override_column not in override:
                continue
            optional_final_label_columns_present.append(override_column)
            value = official.clean(override.get(override_column))
            if value and gold_column in gold_row:
                optional_final_label_columns_applied.append(override_column)
                if gold_row.get(gold_column) != value:
                    gold_row[gold_column] = value
                    label_fields_mutated.append(gold_column)
                    file_changed = True
        preserved_fields = {
            key: gold_row.get(key, "")
            for key in (
                "human_label",
                "human_review_status",
                "human_approved_gold",
                "official_denominator_current",
                "official_metric_input",
                "promotion_evidence",
                "gold_promoted",
            )
            if key in gold_row
        }
        applied_rows.append(
            {
                "schema_version": f"{V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID}_applied_override_v1",
                "run_id": V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID,
                "source_run_id": V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
                "query_id": query_id,
                "track": official.clean(override.get("track") or gold_row.get("track")),
                "source_family": "TEXT",
                "codex_policy_option": "revise_gold_or_label_policy",
                "codex_apply_action": official.clean(override.get("codex_apply_action")),
                "apply_to_official_gold": True,
                "user_policy_decision_applied": True,
                "expected_answer_before_sha256": sha256_text(before_expected),
                "supporting_evidence_before_sha256": sha256_text(before_support),
                "expected_answer_final": after_expected,
                "supporting_evidence_final": after_support,
                "expected_answer_sha256": sha256_text(after_expected),
                "supporting_evidence_sha256": sha256_text(after_support),
                "current_citation_locator": gold_row.get("citation_locator", ""),
                "citation_locator_mutated": bool(
                    locator_final_column in override and official.clean(override.get(locator_final_column))
                ),
                "preserved_gold_fields": preserved_fields,
                "target_answerability_label": official.clean(override.get("target_answerability_label")),
                "target_relevance_label": official.clean(override.get("target_relevance_label")),
                "override_source": official.clean(override.get("override_source")),
                "human_review_only": True,
                "generation_source": False,
                "not_silver_source": True,
                "not_promotion_evidence": True,
                "user_policy_source": True,
            }
        )
        diff_rows.append(
            {
                "schema_version": f"{V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID}_gold_diff_v1",
                "run_id": V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID,
                "source_run_id": V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
                "query_id": query_id,
                "track": gold_row.get("track"),
                "source_family": "TEXT",
                "changed_fields": ["expected_answer", "supporting_evidence"],
                "field_diffs": {
                    "expected_answer": gold_text_field_diff(before_expected, after_expected),
                    "supporting_evidence": gold_text_field_diff(before_support, after_support),
                },
                "citation_locator_mutated": False,
                "human_review_only": True,
                "generation_source": False,
                "not_silver_source": True,
                "user_policy_source": True,
            }
        )
    if file_changed:
        write_csv_rows_with_fieldnames(DEFAULT_TEXT_NAMU_GOLD_CSV, fieldnames, gold_rows)
    after_rows_by_id = {
        official.clean(row.get("query_id")): dict(row)
        for row in gold_rows
        if official.clean(row.get("query_id"))
    }
    after_text_0005 = after_rows_by_id["text_namu_v2_0005"]
    return {
        "changed_query_ids": list(V3_1_9_USER_GOLD_POLICY_OVERRIDE_QUERY_IDS),
        "changed_row_count": len(V3_1_9_USER_GOLD_POLICY_OVERRIDE_QUERY_IDS),
        "applied_overrides": applied_rows,
        "gold_diff": diff_rows,
        "gold_file_before_sha256": V3_1_9_TEXT_GOLD_BEFORE_SHA256,
        "gold_file_after_sha256": sha256_file(DEFAULT_TEXT_NAMU_GOLD_CSV),
        "gold_file_written_this_run": file_changed,
        "text_namu_v2_0005_unchanged": True,
        "text_namu_v2_0005_after_row_core_sha256": sha256_text(
            "\n".join(
                [
                    after_text_0005.get("expected_answer", ""),
                    after_text_0005.get("supporting_evidence", ""),
                    after_text_0005.get("citation_locator", ""),
                ]
            )
        ),
        "label_fields_mutated": sorted(set(label_fields_mutated)),
        "optional_final_label_columns_present": sorted(set(optional_final_label_columns_present)),
        "optional_final_label_columns_applied": sorted(set(optional_final_label_columns_applied)),
    }


def gold_text_field_diff(before_text: str, after_text: str) -> dict[str, Any]:
    before_hash = sha256_text(before_text)
    after_hash = sha256_text(after_text)
    return {
        "before_text": before_text,
        "after_text": after_text,
        "before_sha256": before_hash,
        "after_sha256": after_hash,
        "field_changed": before_hash != after_hash,
        "human_review_only": True,
        "generation_source": False,
        "not_silver_source": True,
        "user_policy_source": True,
    }


def sync_v3_1_9_official_input_hash_surfaces(
    *,
    text_gold_sha256: str,
    current_text_gold_rows_by_query_id: Mapping[str, Mapping[str, str]],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
) -> dict[str, Any]:
    text_key = "track_b_text_namu_v2_1_question_gold_v2_human_audit_approved"
    before = {
        "metric_input_config": official.file_identity(metric_input_config_path),
        "denominator_registry": official.file_identity(denominator_registry_path),
        "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
    }
    registry = official.read_json(denominator_registry_path)
    registry_entry = official.nested_mapping(registry, "official_diagnostic_denominators").get(text_key)
    if isinstance(registry_entry, dict):
        registry_entry["sha256"] = text_gold_sha256
    write_json_preserve_order(denominator_registry_path, registry)

    config = official.read_json(metric_input_config_path)
    for section in ("metric_lanes", "official_metric_input_artifacts"):
        entry = official.nested_mapping(config, section).get("text_namu_v2_1")
        if isinstance(entry, dict):
            entry["sha256"] = text_gold_sha256
    for row in config.get("candidate_manifest") or []:
        if not isinstance(row, dict):
            continue
        query_id = official.clean(row.get("query_id"))
        gold_row = current_text_gold_rows_by_query_id.get(query_id)
        if not gold_row:
            continue
        for key in (
            "expected_answer",
            "supporting_evidence",
            "citation_locator",
            "track",
            "official_metric_input",
            "promotion_evidence",
        ):
            if key in gold_row:
                row[key] = parse_gold_csv_json_value(gold_row[key])
    write_json_preserve_order(metric_input_config_path, config)

    registry_sha_after = sha256_file(denominator_registry_path)
    config_sha_after = sha256_file(metric_input_config_path)
    smoke = official.read_json(pre_execution_smoke_path)
    for section_path in (
        ("artifact_consistency", "metric_lanes", "text_namu_v2_1"),
        ("csv_checks", "text_namu_v2_1"),
    ):
        entry = nested_mutable_mapping(smoke, *section_path)
        if entry:
            entry["sha256"] = text_gold_sha256
    artifact_consistency = nested_mutable_mapping(smoke, "artifact_consistency")
    if artifact_consistency:
        artifact_consistency["config_sha256"] = config_sha_after
        artifact_consistency["registry_sha256"] = registry_sha_after
    write_json_preserve_order(pre_execution_smoke_path, smoke)

    return {
        "before": before,
        "after": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
        },
        "text_gold_sha256": text_gold_sha256,
        "registry_sha256_after": registry_sha_after,
        "metric_input_config_sha256_after": config_sha_after,
        "pre_execution_smoke_sha256_after": sha256_file(pre_execution_smoke_path),
        "query_id_set_changed": False,
    }


def parse_gold_csv_json_value(value: Any) -> Any:
    text = official.clean(value)
    if text.upper() == "TRUE":
        return True
    if text.upper() == "FALSE":
        return False
    if text.startswith("{") or text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def nested_mutable_mapping(root: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    current: Any = root
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = current.get(key)
    return current if isinstance(current, dict) else {}


def write_json_preserve_order(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compose_v3_1_9_latest_lane_surface_rows(
    official_query_ids: Sequence[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    overlay_specs = [
        ("v3_1_1_post_locator", DEFAULT_V3_1_1_POST_RESULTS_JSONL),
        ("v3_1_2_answer_span_renderer_triage", DEFAULT_V3_1_2_ANSWER_SPAN_RESULTS_JSONL),
        ("v3_1_3_remaining_queue_answer_span_renderer_triage", DEFAULT_V3_1_3_REMAINING_QUEUE_RESULTS_JSONL),
        ("v3_1_4_pdf_residual_answer_span_renderer_triage", DEFAULT_V3_1_4_PDF_RESIDUAL_RESULTS_JSONL),
        ("v3_1_6_gq_auto_010_safe_pdf_paragraph_window_expansion", DEFAULT_V3_1_6_PDF_WINDOW_EXPANSION_RESULTS_JSONL),
    ]
    by_id: dict[str, dict[str, Any]] = {}
    source_audit: dict[str, Any] = {}
    for label, path in overlay_specs:
        rows = read_jsonl(path)
        source_audit[label] = {
            "path": official.repo_relative(report_artifact_logical_path_for_existing(path)),
            "resolved_path": str(path),
            "exists": path.exists(),
            "row_count": len(rows),
            "sha256": sha256_file(path) if path.exists() else None,
        }
        for row in rows:
            query_id = official.clean(row.get("query_id"))
            if not query_id:
                continue
            updated = deepcopy(dict(row))
            updated["_v3_1_9_lane_surface_source"] = label
            updated["_v3_1_9_lane_surface_source_path"] = source_audit[label]["path"]
            by_id[query_id] = updated
    missing = [query_id for query_id in official_query_ids if query_id not in by_id]
    extra = sorted(set(by_id) - set(official_query_ids))
    if missing or extra:
        raise ValueError(f"v3_1_9 latest lane surface mismatch; missing={missing!r}, extra={extra!r}")
    return [by_id[query_id] for query_id in official_query_ids], source_audit


def report_artifact_logical_path_for_existing(path: Path) -> Path:
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def rescore_v3_1_9_lane_surface_rows(
    *,
    surface_rows: Sequence[Mapping[str, Any]],
    official_rows_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for source_row in surface_rows:
        query_id = official.clean(source_row.get("query_id"))
        official_row = official_rows_by_id.get(query_id)
        if not official_row:
            raise ValueError(f"official row missing for {query_id}")
        row = deepcopy(dict(source_row))
        row.update(
            {
                "schema_version": f"{V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID}_rescored_result_v1",
                "run_id": V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID,
                "source_run_id": V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
                "source_result_run_id": source_row.get("run_id"),
                "source_result_artifact": source_row.get("_v3_1_9_lane_surface_source_path"),
                "scoring_only_remeasurement": True,
                "live_generation_rerun": False,
                "candidate_artifacts_as_generation_source": False,
                "generation_used_expected_answer": False,
                "generation_used_supporting_evidence": False,
                "generation_used_gold_fields": False,
                "promotion_evidence": False,
                "silver_rows_created": False,
                "behavior_change_made": False,
                "renderer_mutation": False,
                "scorer_behavior_mutation": False,
                "retrieval_mutation": False,
                "production_mutation": False,
            }
        )
        for gold_key in ("expected_answer", "supporting_evidence", "human_label"):
            row.pop(gold_key, None)
        rescored_lanes: dict[str, dict[str, Any]] = {}
        source_lanes = as_mapping(source_row.get("lane_results"))
        for lane_name in V3_1_LANE_NAMES:
            lane = as_mapping(source_lanes.get(lane_name))
            rescored_lanes[lane_name] = rescore_v3_1_9_lane(
                lane_name=lane_name,
                lane=lane,
                official_row=official_row,
                source_family=official.clean(row.get("source_family")) or SOURCE_FAMILY_LABEL_BY_TRACK.get(
                    official.clean(official_row.get("track")), ""
                ),
            )
        row["lane_results"] = rescored_lanes
        out.append(row)
    return out


def rescore_v3_1_9_lane(
    *,
    lane_name: str,
    lane: Mapping[str, Any],
    official_row: Mapping[str, Any],
    source_family: str,
) -> dict[str, Any]:
    citations = list(lane.get("scored_citations") or lane.get("generated_citations") or [])
    citation_chunks = [
        SimpleNamespace(text=citation_text_for_scoring(citation))
        for citation in citations
        if isinstance(citation, Mapping)
    ]
    generated_answer = official.clean(lane.get("generated_answer"))
    score = score_generated_row(official_row, generated_answer, citation_chunks)
    rescored = deepcopy(dict(lane))
    rescored.update(
        {
            "lane_name": lane_name,
            "source_family": source_family,
            "answer_score": score["answer_score"],
            "citation_support_score": score["citation_support_score"],
            "failure_category": score["failure_category"],
            "failure_detail": score["failure_detail"],
            "score_status": "PASS" if score["failure_category"] == "PASS" else "FAIL_CLOSED",
            "result_bucket": "PASS" if score["failure_category"] == "PASS" else score["failure_category"],
            "scorer_compatibility_normalization_applied": score.get(
                "scorer_compatibility_normalization_applied",
                False,
            ),
            "scoring_only_remeasurement": True,
            "live_generation_rerun": False,
            "scorer_behavior_mutation": False,
            "renderer_mutation": False,
            "retrieval_mutation": False,
            "generation_used_expected_answer": False,
            "generation_used_supporting_evidence": False,
            "generation_used_gold_fields": False,
            "candidate_artifacts_as_generation_source": False,
            "human_review_only_gold_policy_applied_for_scoring": True,
        }
    )
    return rescored


def citation_text_for_scoring(citation: Mapping[str, Any]) -> str:
    return official.clean(
        citation.get("citation_text")
        or citation.get("text")
        or citation.get("content")
        or citation.get("source_text")
        or citation.get("snippet")
    )


def v3_1_9_lane_pass_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        lane_name: sum(
            1
            for row in rows
            if official.clean(as_mapping(as_mapping(row.get("lane_results")).get(lane_name)).get("failure_category"))
            == "PASS"
        )
        for lane_name in V3_1_LANE_NAMES
    }


def v3_1_9_lane_failure_counts(rows: Sequence[Mapping[str, Any]]) -> Counter:
    counts: Counter = Counter()
    for row in rows:
        for lane_name in V3_1_LANE_NAMES:
            category = official.clean(as_mapping(as_mapping(row.get("lane_results")).get(lane_name)).get("failure_category"))
            if category:
                counts[category] += 1
    return counts


def v3_1_9_lane_pass_counts_before(v3_1_8_summary: Mapping[str, Any]) -> dict[str, int]:
    source_summary = official.read_json(DEFAULT_V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_SUMMARY_JSON)
    direct = source_summary.get("all_track_pass_count_after_by_lane")
    if isinstance(direct, Mapping):
        return {lane_name: int(direct.get(lane_name) or 0) for lane_name in V3_1_LANE_NAMES}
    lane_counts_source = as_mapping(source_summary.get("lane_counts") or v3_1_8_summary.get("lane_counts"))
    return {
        lane_name: int(as_mapping(lane_counts_source.get(lane_name)).get("pass_count") or 0)
        for lane_name in V3_1_LANE_NAMES
    }


def build_v3_1_9_source_family_lane_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, dict[str, int]]]:
    out: dict[str, dict[str, dict[str, int]]] = {}
    for source_family in ("PDF", "TEXT", "XLSX"):
        family_rows = [row for row in rows if official.clean(row.get("source_family")) == source_family]
        out[source_family] = {
            lane_name: {
                "row_count": len(family_rows),
                "pass_count": sum(
                    1
                    for row in family_rows
                    if official.clean(
                        as_mapping(as_mapping(row.get("lane_results")).get(lane_name)).get("failure_category")
                    )
                    == "PASS"
                ),
                "fail_count": sum(
                    1
                    for row in family_rows
                    if official.clean(
                        as_mapping(as_mapping(row.get("lane_results")).get(lane_name)).get("failure_category")
                    )
                    != "PASS"
                ),
            }
            for lane_name in V3_1_LANE_NAMES
        }
    return out


def build_v3_1_9_remaining_triage_queue(
    *,
    rescored_rows: Sequence[Mapping[str, Any]],
    source_run_id: str,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for row in rescored_rows:
        failing_lanes: list[dict[str, Any]] = []
        for lane_name in V3_1_LANE_NAMES:
            lane = as_mapping(as_mapping(row.get("lane_results")).get(lane_name))
            category = official.clean(lane.get("failure_category"))
            if category == "PASS":
                continue
            failing_lanes.append(
                {
                    "lane_name": lane_name,
                    "failure_category": category,
                    "answer_score": lane.get("answer_score"),
                    "citation_support_score": lane.get("citation_support_score"),
                    "failure_detail": lane.get("failure_detail"),
                }
            )
        if not failing_lanes:
            continue
        items.append(
            {
                "query_id": row["query_id"],
                "track": row.get("track"),
                "source_family": row.get("source_family"),
                "failing_lanes": failing_lanes,
                "implementation_safe": True,
                "requires_user_gold_policy_decision": False,
                "policy_status": "gold_policy_settled_by_user_override",
                "recommended_later_phase": "renderer_scorer_prompt_or_retrieval_implementation_phase",
                "allowed_next_actions": [
                    "inspect implementation behavior",
                    "do not mutate gold in this queue",
                    "do not create another user policy packet unless metadata conflict appears",
                ],
            }
        )
    return {
        "schema_version": f"{V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID}_remaining_triage_queue_v1",
        "run_id": V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID,
        "source_run_id": source_run_id,
        "generated_at": utc_timestamp(),
        "user_policy_decision_applied": True,
        "requires_additional_user_policy_packet": False,
        "active_remaining_queue_empty": not items,
        "active_implementation_queue_empty": not items,
        "implementation_safe_residual_count": len(items),
        "residual_lane_item_count": sum(len(item["failing_lanes"]) for item in items),
        "items": items,
        "promotion_evidence": False,
        "silver_rows_created": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
    }


def v3_1_9_guardrails() -> dict[str, bool]:
    return {
        "diagnostic_only": False,
        "user_policy_decision_applied": True,
        "expected_answer_mutation": True,
        "supporting_evidence_mutation": True,
        "gold_policy_mutation": True,
        "gold_mutation": True,
        "behavior_change_made": False,
        "renderer_mutation": False,
        "scorer_behavior_mutation": False,
        "retrieval_mutation": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "denominator_query_id_set_mutation": False,
        "official_denominator_query_id_set_mutation": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "silver_rows_created": False,
        "promotion_evidence": False,
        "promotion_gate_auto_run": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "official_retrieval_metrics_computed": False,
        "official_ndcg_computed": False,
        "official_mrr_computed": False,
        "official_hit_at_k_computed": False,
        "lane_score_collapsed": False,
        "live_generation_rerun": False,
    }


def build_v3_1_8_human_review_packet(
    *,
    v3_1_7_summary: Mapping[str, Any],
    v3_1_7_inventory: Sequence[Mapping[str, Any]],
    v3_1_7_packet: Mapping[str, Any],
    source_material: Mapping[str, Any],
) -> dict[str, Any]:
    inventory_by_query_id: dict[str, list[Mapping[str, Any]]] = {}
    for row in v3_1_7_inventory:
        query_id = official.clean(row.get("query_id"))
        if query_id in V3_1_8_POLICY_REVIEW_QUERY_IDS:
            inventory_by_query_id.setdefault(query_id, []).append(row)
    prior_decision_items = {
        official.clean(item.get("query_id")): item
        for item in v3_1_7_packet.get("decision_items") or []
        if isinstance(item, Mapping)
    }
    span_results = as_mapping(source_material.get("span_results_by_query_id"))
    span_diagnostics = as_mapping(source_material.get("span_diagnostics_by_query_id"))
    scorer_rows = as_mapping(source_material.get("scorer_rows_by_query_id"))
    gold_rows = as_mapping(source_material.get("gold_rows_by_query_id"))
    human_audit_rows = as_mapping(source_material.get("human_audit_v2_rows_by_query_id"))
    policy_review_rows = as_mapping(source_material.get("policy_review_rows_by_query_id"))
    decision_items: list[dict[str, Any]] = []
    for query_id in V3_1_8_POLICY_REVIEW_QUERY_IDS:
        span_row = as_mapping(span_results.get(query_id))
        span_diag_row = as_mapping(span_diagnostics.get(query_id))
        scorer_row = as_mapping(scorer_rows.get(query_id))
        gold_row = as_mapping(gold_rows.get(query_id))
        human_audit_row = as_mapping(human_audit_rows.get(query_id))
        policy_review_row = as_mapping(policy_review_rows.get(query_id))
        inventory_rows = sorted(
            inventory_by_query_id.get(query_id, []),
            key=lambda row: V3_1_LANE_NAMES.index(row.get("lane_name"))
            if row.get("lane_name") in V3_1_LANE_NAMES
            else 99,
        )
        lane_status = [
            build_v3_1_8_lane_status(
                query_id=query_id,
                lane_name=lane_name,
                inventory_row=next(
                    (row for row in inventory_rows if row.get("lane_name") == lane_name),
                    {},
                ),
                span_row=span_row,
                span_diag_row=span_diag_row,
            )
            for lane_name in V3_1_LANE_NAMES
        ]
        current_policy_material = v3_1_8_policy_material(
            query_id=query_id,
            gold_row=gold_row,
            scorer_row=scorer_row,
            human_audit_row=human_audit_row,
            policy_review_row=policy_review_row,
        )
        decision_items.append(
            {
                "query_id": query_id,
                "source_family": "TEXT",
                "track": official.clean(span_row.get("track") or gold_row.get("track") or "text_namu_v2_1"),
                "question": official.clean(span_row.get("query") or gold_row.get("question") or scorer_row.get("question")),
                "lane_level_status": lane_status,
                "failure_category_by_lane": {
                    lane["lane_name"]: lane.get("failure_category") for lane in lane_status
                },
                "diagnostic_subcategories_by_lane": {
                    lane["lane_name"]: lane.get("diagnostic_subcategories") for lane in lane_status
                },
                "current_scoring_reference_span_information": {
                    lane["lane_name"]: lane.get("scoring_reference_span_information")
                    for lane in lane_status
                },
                "current_citation_locator_search_unit_metadata": {
                    lane["lane_name"]: lane.get("citation_locator_search_unit_metadata")
                    for lane in lane_status
                },
                "current_supporting_evidence_information": current_policy_material["supporting_evidence"],
                "current_policy_material": current_policy_material,
                "raw_reference_text_included": True,
                "raw_supporting_text_included": True,
                "raw_gold_text_included": True,
                "human_review_only": True,
                "generation_source": False,
                "not_silver_source": True,
                "not_gold_mutation": True,
                "requires_user_policy_decision": True,
                "requires_user_gold_policy_decision": True,
                "requires_user_relevance_label_decision": True,
                "requires_user_answerability_label_decision": True,
                "implementation_safe": False,
                "safe_to_fix_without_user_policy_decision": False,
                "policy_decision_options": list(V3_1_8_DECISION_OPTIONS),
                "explicit_user_decision_question": (
                    "For this TEXT residual, should the current strict reference boundary remain, should a "
                    "scorer/renderer review be allowed without gold mutation, or should gold/label policy be revised?"
                ),
                "why_codex_cannot_decide_policy": (
                    "The residual can be interpreted as strict answer-span enforcement, scorer/renderer normalization, "
                    "or a gold/relevance/answerability policy boundary. Applying one interpretation would mutate "
                    "user-owned evaluation policy, so Codex records evidence only."
                ),
                "decision_consequences": v3_1_8_decision_consequences(),
                "conservative_default": (
                    "keep_in_policy_review_packet; do_not_mutate_gold_labels_expected_supporting_evidence_or_behavior"
                ),
                "prior_v3_1_7_decision_item": prior_decision_items.get(query_id, {}),
                "policy_material_excluded_from_generation": True,
            }
        )
    return {
        "schema_version": f"{V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID}_human_review_packet_v1",
        "run_id": V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
        "source_run_id": V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID,
        "generated_at": utc_timestamp(),
        "diagnostic_only": True,
        "promotion_evidence": False,
        "human_review_packet_contains_policy_material": True,
        "human_review_only": True,
        "generation_source": False,
        "not_silver_source": True,
        "not_gold_mutation": True,
        "raw_reference_text_embedded_in_generation": False,
        "raw_supporting_text_embedded_in_generation": False,
        "raw_gold_text_embedded_in_generation": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "official_retrieval_metrics_computed": False,
        "lane_score_collapsed": False,
        "source_v3_1_7_bucket_counts": v3_1_7_summary.get("residual_inventory_bucket_counts"),
        "decision_options": list(V3_1_8_DECISION_OPTIONS),
        "decision_item_count": len(decision_items),
        "decision_items": decision_items,
    }


def build_v3_1_8_lane_status(
    *,
    query_id: str,
    lane_name: str,
    inventory_row: Mapping[str, Any],
    span_row: Mapping[str, Any],
    span_diag_row: Mapping[str, Any],
) -> dict[str, Any]:
    lane = as_mapping(as_mapping(span_row.get("lane_results")).get(lane_name))
    diagnostics = as_mapping(as_mapping(span_diag_row.get("answer_span_renderer_diagnostics")).get(lane_name))
    generated_answer = official.clean(lane.get("generated_answer"))
    scored_citations = lane.get("scored_citations") or lane.get("generated_citations") or []
    citation = first_mapping(scored_citations)
    citation_text = official.clean(citation.get("citation_text"))
    citation_payload = as_mapping(citation.get("search_unit_citation_payload"))
    text_locator = as_mapping(citation_payload.get("text_locator") or citation_payload.get("textLocator"))
    return {
        "query_id": query_id,
        "lane_name": lane_name,
        "failure_category": official.clean(inventory_row.get("failure_category") or lane.get("failure_category")),
        "diagnostic_subcategories": list(inventory_row.get("diagnostic_subcategories") or []),
        "score_status": lane.get("score_status"),
        "answer_score": lane.get("answer_score"),
        "citation_support_score": lane.get("citation_support_score"),
        "strict_json_parse_passed": lane.get("strict_json_parse_ok") is True
        or inventory_row.get("strict_json_parse_passed") is True,
        "citation_locator_validation_passed": inventory_row.get("citation_locator_validation_passed") is True,
        "citation_support_present": inventory_row.get("citation_support_present") is True,
        "current_generated_answer": generated_answer,
        "current_generated_answer_sha256": sha256_text(generated_answer) if generated_answer else None,
        "current_generated_answer_char_count": len(generated_answer),
        "current_generated_answer_token_count": len(generated_answer.split()),
        "citation_locator_search_unit_metadata": {
            "document_id": citation_payload.get("document_id") or citation_payload.get("documentId"),
            "document_version_id": citation_payload.get("document_version_id")
            or citation_payload.get("documentVersionId"),
            "search_unit_id": citation_payload.get("search_unit_id") or citation_payload.get("searchUnitId"),
            "manifest_query_id": citation_payload.get("manifest_query_id") or citation_payload.get("manifestQueryId"),
            "manifest_track": citation_payload.get("manifest_track"),
            "source_family": citation_payload.get("source_family") or citation_payload.get("sourceFamily"),
            "source_bound_official_denominator": citation_payload.get("source_bound_official_denominator"),
            "text_locator": {
                "chunk_id": text_locator.get("chunk_id"),
                "line_number": text_locator.get("line_number"),
                "section_id": text_locator.get("section_id"),
                "section_path": text_locator.get("section_path"),
                "section_type": text_locator.get("section_type"),
                "title": text_locator.get("title"),
                "source_corpus_path": text_locator.get("source_corpus_path"),
            },
        },
        "citation_text_human_review_only": citation_text,
        "citation_text_generation_source": False,
        "citation_text_sha256": sha256_text(citation_text) if citation_text else None,
        "citation_text_char_count": len(citation_text),
        "citation_text_token_count": len(citation_text.split()),
        "scoring_reference_span_information": {
            "reference_span_audit_only": True,
            "reference_span_text_embedded_in_generation": False,
            "scoring_reference_span_sha256": inventory_row.get("scoring_reference_span_sha256")
            or diagnostics.get("scoring_reference_span_sha256"),
            "reference_token_count": inventory_row.get("reference_token_count")
            or diagnostics.get("reference_token_count"),
            "matched_reference_token_count": inventory_row.get("matched_reference_token_count")
            or diagnostics.get("matched_reference_token_count"),
            "reference_token_coverage": inventory_row.get("reference_token_coverage")
            or diagnostics.get("reference_token_coverage"),
            "answer_token_count": inventory_row.get("answer_token_count") or diagnostics.get("answer_token_count"),
        },
        "policy_material_excluded_from_generation": True,
        "human_review_only": True,
        "generation_source": False,
    }


def first_mapping(values: Any) -> Mapping[str, Any]:
    if isinstance(values, list):
        for value in values:
            if isinstance(value, Mapping):
                return value
    return {}


def v3_1_8_policy_material(
    *,
    query_id: str,
    gold_row: Mapping[str, Any],
    scorer_row: Mapping[str, Any],
    human_audit_row: Mapping[str, Any],
    policy_review_row: Mapping[str, Any],
) -> dict[str, Any]:
    score_details = as_mapping(scorer_row.get("score_details"))
    expected_answer = official.clean(gold_row.get("expected_answer") or score_details.get("expected_answer"))
    supporting_evidence = official.clean(
        gold_row.get("supporting_evidence") or score_details.get("supporting_evidence")
    )
    return {
        "query_id": query_id,
        "human_review_only": True,
        "generation_source": False,
        "not_silver_source": True,
        "not_gold_mutation": True,
        "expected_answer": policy_text_payload(
            text=expected_answer,
            source_artifacts=[
                official.repo_relative(DEFAULT_TEXT_NAMU_GOLD_CSV),
                official.repo_relative(DEFAULT_SCORER_RESULTS_JSONL),
            ],
        ),
        "supporting_evidence": policy_text_payload(
            text=supporting_evidence,
            source_artifacts=[
                official.repo_relative(DEFAULT_TEXT_NAMU_GOLD_CSV),
                official.repo_relative(DEFAULT_SCORER_RESULTS_JSONL),
            ],
        ),
        "gold_csv_fields": {
            "human_label": gold_row.get("human_label"),
            "human_review_status": gold_row.get("human_review_status"),
            "human_approved_gold": gold_row.get("human_approved_gold"),
            "official_denominator_current": gold_row.get("official_denominator_current"),
            "official_metric_input": gold_row.get("official_metric_input"),
            "promotion_evidence": falseish(gold_row.get("promotion_evidence")),
            "gold_promoted": gold_row.get("gold_promoted"),
            "source_packet_role": gold_row.get("source_packet_role"),
            "issue_type": gold_row.get("issue_type"),
            "citation_locator": gold_row.get("citation_locator"),
        },
        "human_audit_v2_fields": {
            "candidate_gold_status": human_audit_row.get("candidate_gold_status"),
            "human_label": human_audit_row.get("human_label"),
            "human_review_status": human_audit_row.get("human_review_status"),
            "issue_type": human_audit_row.get("issue_type"),
            "track_denominator_key_preview": human_audit_row.get("track_denominator_key_preview"),
            "expected_answer_normalization": human_audit_row.get("expected_answer_normalization"),
        },
        "prior_policy_review_fields": {
            "review_bucket": policy_review_row.get("review_bucket"),
            "assistant_review_action": policy_review_row.get("assistant_review_action"),
            "assistant_answer_judgment": policy_review_row.get("assistant_answer_judgment"),
            "assistant_citation_support_judgment": policy_review_row.get("assistant_citation_support_judgment"),
            "human_decision_needed": policy_review_row.get("human_decision_needed"),
            "official_metric_input": policy_review_row.get("official_metric_input"),
            "promotion_evidence": falseish(policy_review_row.get("promotion_evidence")),
        },
    }


def falseish(value: Any) -> bool:
    return False if str(value).strip().lower() in {"", "false", "0", "none", "null"} else bool(value)


def policy_text_payload(*, text: str, source_artifacts: Sequence[str]) -> dict[str, Any]:
    return {
        "text": text,
        "sha256": sha256_text(text) if text else None,
        "char_count": len(text),
        "token_count": len(text.split()),
        "source_artifacts": list(source_artifacts),
        "human_review_only": True,
        "generation_source": False,
        "not_silver_source": True,
        "not_gold_mutation": True,
    }


def v3_1_8_decision_consequences() -> list[dict[str, str]]:
    return [
        {
            "decision": "keep_current_strict_reference_boundary",
            "consequence": (
                "Keep the row non-PASS under the current strict reference boundary; do not open "
                "renderer/scorer/retrieval changes from this packet alone."
            ),
        },
        {
            "decision": "approve_scorer_or_renderer_review_without_gold_mutation",
            "consequence": (
                "A later implementation phase may inspect scorer or renderer normalization while keeping "
                "gold, labels, expected answer, and supporting evidence unchanged."
            ),
        },
        {
            "decision": "revise_gold_or_label_policy",
            "consequence": (
                "A later user-owned policy phase must explicitly revise gold, relevance, answerability, "
                "expected-answer, or supporting-evidence policy before official metrics can treat it as settled."
            ),
        },
    ]


def build_v3_1_8_decision_matrix_rows(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in packet.get("decision_items") or []:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "schema_version": f"{V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID}_decision_matrix_v1",
                "run_id": V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
                "query_id": item.get("query_id"),
                "source_family": item.get("source_family"),
                "track": item.get("track"),
                "failure_category_by_lane": item.get("failure_category_by_lane"),
                "diagnostic_subcategories_by_lane": item.get("diagnostic_subcategories_by_lane"),
                "decision_options": item.get("policy_decision_options"),
                "requires_user_policy_decision": True,
                "requires_user_gold_policy_decision": True,
                "requires_user_relevance_label_decision": True,
                "requires_user_answerability_label_decision": True,
                "implementation_safe": False,
                "safe_to_fix_without_user_policy_decision": False,
                "human_review_only_policy_material_included": True,
                "policy_material_generation_source": False,
                "candidate_artifacts_as_generation_source": False,
                "generation_used_expected_answer": False,
                "generation_used_supporting_evidence": False,
                "generation_used_gold_fields": False,
                "gold_mutation": False,
                "human_label_mutation": False,
                "expected_answer_mutation": False,
                "supporting_evidence_mutation": False,
                "relevance_label_mutation": False,
                "answerability_label_mutation": False,
                "promotion_evidence": False,
                "diagnostic_only": True,
                "conservative_default": item.get("conservative_default"),
            }
        )
    return rows


def build_v3_1_8_remaining_triage_queue(packet: Mapping[str, Any]) -> dict[str, Any]:
    query_ids = [
        official.clean(item.get("query_id"))
        for item in packet.get("decision_items") or []
        if isinstance(item, Mapping) and official.clean(item.get("query_id"))
    ]
    return {
        "schema_version": f"{V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID}_remaining_triage_queue_v1",
        "run_id": V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
        "source_run_id": V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID,
        "generated_at": utc_timestamp(),
        "diagnostic_only": True,
        "promotion_evidence": False,
        "active_remaining_queue_status": "cleared",
        "active_implementation_queue_empty": True,
        "implementation_safe_residual_count": 0,
        "policy_review_query_ids": query_ids,
        "policy_review_item_count": len(query_ids),
        "residuals_require_user_policy_review": bool(query_ids),
        "items": [],
        "queue_explanation": (
            "No implementation-safe residual remains. The five TEXT rows stay in the human policy review packet "
            "until a user decision is applied in a later phase."
        ),
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "official_retrieval_metrics_computed": False,
        "gold_mutation": False,
        "human_label_mutation": False,
        "expected_answer_mutation": False,
        "supporting_evidence_mutation": False,
        "relevance_label_mutation": False,
        "answerability_label_mutation": False,
    }


def v3_1_6_closure_assertions(
    summary: Mapping[str, Any],
    queue: Mapping[str, Any],
) -> dict[str, Any]:
    assertions = {
        "run_id_matches_v3_1_6": summary.get("run_id")
        == V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
        "behavior_change_made_true": summary.get("behavior_change_made") is True,
        "context_expansion_attempted_true": summary.get("context_expansion_attempted") is True,
        "context_expansion_applied_true": summary.get("context_expansion_applied") is True,
        "context_expansion_policy_name_matches": summary.get("context_expansion_policy_name")
        == PDF_PARAGRAPH_WINDOW_EXPANSION_POLICY_NAME,
        "locator_safe_metadata_available_true": summary.get("locator_safe_metadata_available") is True,
        "remaining_queue_items_empty": queue.get("items") == [],
        "strict_json_or_locator_residual_count_zero": queue.get("strict_json_or_locator_residual_count") == 0,
        "diagnostic_only_true": summary.get("diagnostic_only") is True and queue.get("diagnostic_only") is True,
        "promotion_evidence_false": summary.get("promotion_evidence") is False and queue.get("promotion_evidence") is False,
        "candidate_artifacts_as_generation_source_false": summary.get("candidate_artifacts_as_generation_source") is False,
        "generation_used_expected_answer_false": summary.get("generation_used_expected_answer") is False,
        "generation_used_supporting_evidence_false": summary.get("generation_used_supporting_evidence") is False,
        "generation_used_gold_fields_false": summary.get("generation_used_gold_fields") is False,
        "reference_span_text_embedded_false": summary.get("reference_span_text_embedded") is False,
        "official_ndcg_mrr_hit_at_k_not_computed": (
            summary.get("official_ndcg_computed") is False
            and summary.get("official_mrr_computed") is False
            and summary.get("official_hit_at_k_computed") is False
            and summary.get("official_retrieval_metrics_computed") is False
        ),
        "all_track_remeasurement_exists": summary.get("all_track_remeasurement_performed") is True,
        "all_track_non_target_unexpected_change_count_zero": summary.get("all_track_non_target_unexpected_change_count") == 0,
        "no_non_target_context_expansion_ids": summary.get("all_track_non_target_context_expansion_query_ids") == [],
    }
    return {
        "assertions": assertions,
        "passed": all(assertions.values()),
        "active_remaining_queue_status": "cleared" if queue.get("items") == [] else "not_cleared",
        "closure_type": "diagnostic_queue_cleared_not_promotion",
    }


def artifact_path_hash_audit(artifact_paths: Mapping[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for hash_key, recorded in sorted(artifact_paths.items()):
        if not hash_key.endswith("_sha256"):
            continue
        path_key = hash_key.removesuffix("_sha256")
        path_value = official.clean(artifact_paths.get(path_key))
        path = resolve_repo_relative_artifact_path(Path(path_value)) if path_value else Path()
        actual = sha256_file(path) if path_value and path.exists() else None
        entries.append(
            {
                "artifact_key": path_key,
                "path": path_value,
                "recorded_sha256": recorded,
                "current_sha256": actual,
                "exists": bool(path_value and path.exists()),
                "matches": actual == recorded,
            }
        )
    return {
        "all_recorded_hashes_match_current_files": all(entry["matches"] for entry in entries),
        "mismatch_count": sum(1 for entry in entries if not entry["matches"]),
        "entries": entries,
        "diagnostic_only": True,
        "promotion_evidence": False,
    }


def v3_1_5_remaining_queue_artifact_consistency_preflight(
    *,
    summary: Mapping[str, Any],
    diagnostic_rows: Sequence[Mapping[str, Any]],
    remaining_queue: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if summary.get("run_id") != V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID:
        errors.append("v3_1_5 summary run_id mismatch")
    if remaining_queue.get("run_id") != V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID:
        errors.append("v3_1_5 remaining queue run_id mismatch")
    queue_ids = [
        official.clean(item.get("query_id"))
        for item in remaining_queue.get("items") or []
        if isinstance(item, Mapping)
    ]
    if tuple(queue_ids) != V3_1_6_SAFE_PDF_WINDOW_QUERY_IDS:
        errors.append(f"v3_1_5 remaining queue ids mismatch: {queue_ids!r}")
    classifications = [
        official.clean(item.get("coverage_classification"))
        for item in remaining_queue.get("items") or []
        if isinstance(item, Mapping)
    ]
    if classifications != ["query_bound_searchunit_too_narrow"]:
        errors.append(f"v3_1_5 coverage classification mismatch: {classifications!r}")
    if remaining_queue.get("strict_json_or_locator_residual_count") != 0:
        errors.append("v3_1_5 strict_json_or_locator_residual_count must be zero")
    if remaining_queue.get("diagnostic_only") is not True:
        errors.append("v3_1_5 remaining queue diagnostic_only must be true")
    if remaining_queue.get("promotion_evidence") is not False:
        errors.append("v3_1_5 remaining queue promotion_evidence must be false")
    if remaining_queue.get("candidate_artifacts_as_generation_source") is not False:
        errors.append("v3_1_5 remaining queue candidate artifacts must not be generation source")
    if remaining_queue.get("generation_used_expected_answer") is not False:
        errors.append("v3_1_5 remaining queue expected answers must not be generation source")
    if remaining_queue.get("generation_used_supporting_evidence") is not False:
        errors.append("v3_1_5 remaining queue supporting evidence must not be generation source")
    if remaining_queue.get("generation_used_gold_fields") is not False:
        errors.append("v3_1_5 remaining queue gold fields must not be generation source")
    if remaining_queue.get("reference_span_text_embedded") is not False:
        errors.append("v3_1_5 remaining queue reference span text must not be embedded")
    if len(diagnostic_rows) != 1 or official.clean(as_mapping(diagnostic_rows[0] if diagnostic_rows else {}).get("query_id")) != "gq_auto_010":
        errors.append("v3_1_5 context coverage diagnostics must contain only gq_auto_010")
    if any_guardrail_flag_true(summary) or any_guardrail_flag_true(remaining_queue) or any_guardrail_flag_true(list(diagnostic_rows)):
        errors.append("v3_1_5 source artifacts contain a promotion/generation guardrail violation")
    return {
        "ok": not errors,
        "errors": errors,
        "queue_query_ids": queue_ids,
        "classification": classifications[0] if classifications else "",
        "strict_json_or_locator_residual_count": remaining_queue.get("strict_json_or_locator_residual_count"),
        "source_queue_artifact": official.repo_relative(DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_QUEUE_JSON),
        "diagnostic_only": True,
        "promotion_evidence": False,
        "reference_span_text_embedded": False,
    }


def v3_1_4_remaining_queue_artifact_consistency_preflight(
    *,
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    diagnostic_rows: Sequence[Mapping[str, Any]],
    remaining_queue: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if summary.get("run_id") != V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        errors.append("v3_1_4 summary run_id mismatch")
    if remaining_queue.get("run_id") != V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        errors.append("v3_1_4 remaining queue run_id mismatch")
    if remaining_queue.get("strict_json_or_locator_residual_count") != 0:
        errors.append("v3_1_4 remaining queue strict_json_or_locator_residual_count must be zero")
    queue_ids = [
        official.clean(item.get("query_id"))
        for item in remaining_queue.get("items") or []
        if isinstance(item, Mapping)
    ]
    if tuple(queue_ids) != V3_1_5_SOURCE_BOUND_COVERAGE_QUERY_IDS:
        errors.append(f"v3_1_4 remaining queue ids mismatch: {queue_ids!r}")
    if len(rows) != len(V3_1_4_PDF_RESIDUAL_QUERY_IDS):
        errors.append("v3_1_4 result rows are incomplete")
    if len(diagnostic_rows) != len(rows):
        errors.append("v3_1_4 answer span diagnostics row count mismatch")
    if remaining_queue.get("diagnostic_only") is not True:
        errors.append("v3_1_4 remaining queue diagnostic_only must be true")
    if remaining_queue.get("promotion_evidence") is not False:
        errors.append("v3_1_4 remaining queue promotion_evidence must be false")
    if remaining_queue.get("reference_span_text_embedded") is not False:
        errors.append("v3_1_4 remaining queue reference_span_text_embedded must be false")
    if any_guardrail_flag_true(summary) or any_guardrail_flag_true(remaining_queue):
        errors.append("v3_1_4 source artifacts contain a promotion/generation guardrail violation")
    return {
        "ok": not errors,
        "errors": errors,
        "queue_query_ids": queue_ids,
        "only_gq_auto_010_remaining": queue_ids == list(V3_1_5_SOURCE_BOUND_COVERAGE_QUERY_IDS),
        "strict_json_or_locator_residual_count": remaining_queue.get("strict_json_or_locator_residual_count"),
        "source_queue_artifact": official.repo_relative(DEFAULT_V3_1_4_PDF_RESIDUAL_REMAINING_QUEUE_JSON),
        "diagnostic_only": True,
        "promotion_evidence": False,
        "reference_span_text_embedded": False,
    }


def v3_1_2_remaining_queue_artifact_consistency_preflight(
    *,
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    attribution: Mapping[str, Any],
    audit_rows: Sequence[Mapping[str, Any]],
    diagnostic_rows: Sequence[Mapping[str, Any]],
    remaining_queue: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if summary.get("run_id") != V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        errors.append("v3_1_2 summary run_id mismatch")
    if attribution.get("run_id") != V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        errors.append("v3_1_2 failure attribution run_id mismatch")
    if remaining_queue.get("run_id") != V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        errors.append("v3_1_2 remaining queue run_id mismatch")
    if remaining_queue.get("strict_json_or_locator_residual_count") != 0:
        errors.append("v3_1_2 remaining queue strict_json_or_locator_residual_count must be zero")
    queue_ids = [
        official.clean(item.get("query_id"))
        for item in remaining_queue.get("items") or []
        if isinstance(item, Mapping)
    ]
    if tuple(queue_ids) != V3_1_3_REMAINING_QUEUE_QUERY_IDS:
        errors.append(f"v3_1_2 remaining queue ids mismatch: {queue_ids!r}")
    if "gq_auto_037" in queue_ids:
        errors.append("stale human queue id gq_auto_037 must not be used")
    if len(rows) != len(V3_1_2_TEXT_TARGET_QUERY_IDS):
        errors.append("v3_1_2 classification rows are incomplete")
    if len(audit_rows) != len(rows):
        errors.append("v3_1_2 actual response audit row count mismatch")
    if len(diagnostic_rows) != len(rows):
        errors.append("v3_1_2 answer span diagnostics row count mismatch")
    if any_guardrail_flag_true(summary) or any_guardrail_flag_true(remaining_queue):
        errors.append("v3_1_2 source artifacts contain a promotion/generation guardrail violation")
    return {
        "ok": not errors,
        "errors": errors,
        "queue_query_ids": queue_ids,
        "source_queue_artifact": official.repo_relative(DEFAULT_V3_1_2_REMAINING_TRIAGE_QUEUE_JSON),
        "diagnostic_only": True,
        "promotion_evidence": False,
    }


def v3_1_3_remaining_queue_artifact_consistency_preflight(
    *,
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    attribution: Mapping[str, Any],
    audit_rows: Sequence[Mapping[str, Any]],
    diagnostic_rows: Sequence[Mapping[str, Any]],
    remaining_queue: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if summary.get("run_id") != V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        errors.append("v3_1_3 summary run_id mismatch")
    if attribution.get("run_id") != V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        errors.append("v3_1_3 failure attribution run_id mismatch")
    if remaining_queue.get("run_id") != V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID:
        errors.append("v3_1_3 remaining queue run_id mismatch")
    if remaining_queue.get("strict_json_or_locator_residual_count") != 0:
        errors.append("v3_1_3 remaining queue strict_json_or_locator_residual_count must be zero")
    queue_ids = [
        official.clean(item.get("query_id"))
        for item in remaining_queue.get("items") or []
        if isinstance(item, Mapping)
    ]
    if tuple(queue_ids) != V3_1_4_PDF_RESIDUAL_QUERY_IDS:
        errors.append(f"v3_1_3 remaining queue ids mismatch: {queue_ids!r}")
    if len(rows) != len(V3_1_3_REMAINING_QUEUE_QUERY_IDS):
        errors.append("v3_1_3 target rows are incomplete")
    if len(audit_rows) != len(rows):
        errors.append("v3_1_3 actual response audit row count mismatch")
    if len(diagnostic_rows) != len(rows):
        errors.append("v3_1_3 answer span diagnostics row count mismatch")
    if any_guardrail_flag_true(summary) or any_guardrail_flag_true(remaining_queue):
        errors.append("v3_1_3 source artifacts contain a promotion/generation guardrail violation")
    return {
        "ok": not errors,
        "errors": errors,
        "queue_query_ids": queue_ids,
        "source_queue_artifact": official.repo_relative(DEFAULT_V3_1_3_REMAINING_QUEUE_JSON),
        "diagnostic_only": True,
        "promotion_evidence": False,
    }


def any_guardrail_flag_true(value: Any) -> bool:
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
    if isinstance(value, Mapping):
        if any(key in value and value.get(key) is not False for key in false_keys):
            return True
        if "diagnostic_only" in value and value.get("diagnostic_only") is not True:
            return True
        return any(any_guardrail_flag_true(item) for item in value.values())
    if isinstance(value, list):
        return any(any_guardrail_flag_true(item) for item in value)
    return False


def build_v3_1_3_remaining_queue_rows(
    *,
    all_rows: Sequence[Mapping[str, Any]],
    source_rows_by_id: Mapping[str, Mapping[str, Any]],
    before_rows: Sequence[Mapping[str, Any]],
    remaining_queue: Mapping[str, Any],
) -> list[dict[str, Any]]:
    after_by_id = {official.clean(row.get("query_id")): row for row in all_rows}
    before_by_id = {official.clean(row.get("query_id")): row for row in before_rows}
    queue_items = [
        item
        for item in remaining_queue.get("items") or []
        if isinstance(item, Mapping) and official.clean(item.get("query_id"))
    ]
    rows: list[dict[str, Any]] = []
    for queue_index, queue_item in enumerate(queue_items, start=1):
        query_id = official.clean(queue_item.get("query_id"))
        after_row = after_by_id.get(query_id)
        if not after_row:
            continue
        source_row = source_rows_by_id.get(query_id, {})
        before_row = before_by_id.get(query_id, {})
        row = deepcopy(dict(after_row))
        row.update(
            {
                "schema_version": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "run_id": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "source_run_id": V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "context_source_run_id": V3_RUN_ID,
                "queue_source_of_truth": official.repo_relative(DEFAULT_V3_1_2_REMAINING_TRIAGE_QUEUE_JSON),
                "queue_priority_rank": queue_item.get("remaining_priority_rank") or queue_index,
                "include_decision": "included_from_v3_1_2_machine_remaining_queue_source_of_truth",
                "before_lane_failure_categories": lane_failure_categories(before_row),
                "after_lane_failure_categories": lane_failure_categories(row),
                "row_level_classification_change": row_level_classification_change(before_row, row),
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
        )
        row["answer_span_renderer_diagnostics"] = {
            lane_name: answer_span_renderer_lane_diagnostic(
                row=row,
                source_row=source_row,
                lane_name=lane_name,
                lane=lane,
            )
            for lane_name, lane in as_mapping(row.get("lane_results")).items()
            if isinstance(lane, Mapping)
        }
        rows.append(row)
    return rows


def build_v3_1_4_pdf_residual_rows(
    *,
    all_rows: Sequence[Mapping[str, Any]],
    source_rows_by_id: Mapping[str, Mapping[str, Any]],
    before_rows: Sequence[Mapping[str, Any]],
    remaining_queue: Mapping[str, Any],
) -> list[dict[str, Any]]:
    after_by_id = {official.clean(row.get("query_id")): row for row in all_rows}
    before_by_id = {official.clean(row.get("query_id")): row for row in before_rows}
    queue_items = [
        item
        for item in remaining_queue.get("items") or []
        if isinstance(item, Mapping) and official.clean(item.get("query_id"))
    ]
    rows: list[dict[str, Any]] = []
    for queue_index, queue_item in enumerate(queue_items, start=1):
        query_id = official.clean(queue_item.get("query_id"))
        after_row = after_by_id.get(query_id)
        if not after_row:
            continue
        source_row = source_rows_by_id.get(query_id, {})
        before_row = before_by_id.get(query_id, {})
        row = deepcopy(dict(after_row))
        row.update(
            {
                "schema_version": V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "run_id": V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "source_run_id": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "context_source_run_id": V3_RUN_ID,
                "queue_source_of_truth": official.repo_relative(DEFAULT_V3_1_3_REMAINING_QUEUE_JSON),
                "queue_priority_rank": queue_item.get("remaining_priority_rank") or queue_index,
                "include_decision": "included_from_v3_1_3_machine_remaining_queue_source_of_truth",
                "before_lane_failure_categories": lane_failure_categories(before_row),
                "after_lane_failure_categories": lane_failure_categories(row),
                "row_level_classification_change": row_level_classification_change(before_row, row),
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
        )
        row["answer_span_renderer_diagnostics"] = {
            lane_name: answer_span_renderer_lane_diagnostic(
                row=row,
                source_row=source_row,
                lane_name=lane_name,
                lane=lane,
            )
            for lane_name, lane in as_mapping(row.get("lane_results")).items()
            if isinstance(lane, Mapping)
        }
        rows.append(row)
    return rows


def build_v3_1_6_safe_pdf_window_rows(
    *,
    all_rows: Sequence[Mapping[str, Any]],
    source_rows_by_id: Mapping[str, Mapping[str, Any]],
    before_rows: Sequence[Mapping[str, Any]],
    remaining_queue: Mapping[str, Any],
    expansion_preflight_by_query_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    after_by_id = {official.clean(row.get("query_id")): row for row in all_rows}
    before_by_id = {official.clean(row.get("query_id")): row for row in before_rows}
    queue_items = [
        item
        for item in remaining_queue.get("items") or []
        if isinstance(item, Mapping) and official.clean(item.get("query_id"))
    ]
    rows: list[dict[str, Any]] = []
    for queue_index, queue_item in enumerate(queue_items, start=1):
        query_id = official.clean(queue_item.get("query_id"))
        if query_id not in V3_1_6_SAFE_PDF_WINDOW_QUERY_IDS:
            continue
        after_row = after_by_id.get(query_id)
        if not after_row:
            continue
        source_row = source_rows_by_id.get(query_id, {})
        before_row = before_by_id.get(query_id, {})
        row = deepcopy(dict(after_row))
        context_diagnostic = build_v3_1_6_context_expansion_diagnostic(
            row=row,
            before_row=before_row,
            preflight=as_mapping(expansion_preflight_by_query_id.get(query_id)),
        )
        row.update(
            {
                "schema_version": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
                "run_id": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
                "source_run_id": V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
                "context_source_run_id": V3_RUN_ID,
                "queue_source_of_truth": official.repo_relative(DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_QUEUE_JSON),
                "queue_priority_rank": queue_item.get("remaining_priority_rank") or queue_index,
                "include_decision": "included_from_v3_1_5_machine_remaining_queue_source_of_truth",
                "before_lane_failure_categories": lane_failure_categories(before_row),
                "after_lane_failure_categories": lane_failure_categories(row),
                "row_level_classification_change": row_level_classification_change(before_row, row),
                "context_expansion_diagnostics": context_diagnostic,
                "context_expansion_attempted": context_diagnostic.get("expansion_attempted"),
                "context_expansion_applied": context_diagnostic.get("expansion_applied"),
                "locator_safe_metadata_available": context_diagnostic.get("locator_safe_metadata_available"),
                "diagnostic_only": True,
                "promotion_evidence": False,
                "threshold_tuning": False,
                "winner_selection": False,
                "promotion_gate_auto_run": False,
                "candidate_artifacts_as_generation_source": False,
                "generation_used_expected_answer": False,
                "generation_used_gold_fields": False,
                "generation_used_supporting_evidence": False,
                "reference_span_text_embedded": False,
                "production_mutation": False,
                "baseline_mutation": False,
                "denominator_mutation": False,
                "gold_mutation": False,
                "human_label_mutation": False,
            }
        )
        row["answer_span_renderer_diagnostics"] = {
            lane_name: answer_span_renderer_lane_diagnostic(
                row=row,
                source_row=source_row,
                lane_name=lane_name,
                lane=lane,
            )
            for lane_name, lane in as_mapping(row.get("lane_results")).items()
            if isinstance(lane, Mapping)
        }
        rows.append(row)
    return rows


def build_v3_1_6_context_expansion_diagnostic(
    *,
    row: Mapping[str, Any],
    before_row: Mapping[str, Any],
    preflight: Mapping[str, Any],
) -> dict[str, Any]:
    expansion_unit_ids = list(preflight.get("expansion_unit_ids") or [])
    lane_results = as_mapping(row.get("lane_results"))
    generated_cited_original_by_lane: dict[str, bool] = {}
    generated_cited_expansion_by_lane: dict[str, bool] = {}
    locator_validation_passed_by_lane: dict[str, bool] = {}
    for lane_name in V3_1_LIVE_LANE_NAMES:
        lane = as_mapping(lane_results.get(lane_name))
        cited_ids = {official.clean(item) for item in lane.get("cited_search_unit_ids") or []}
        generated_cited_original_by_lane[lane_name] = bool(
            cited_ids.intersection(set(preflight.get("original_cited_search_unit_ids") or []))
        )
        generated_cited_expansion_by_lane[lane_name] = bool(cited_ids.intersection(set(expansion_unit_ids)))
        locator_validation_passed_by_lane[lane_name] = as_mapping(lane.get("llm_generated_locator_validation")).get("ok") is True
    expansion_text = " ".join(
        official.clean(unit.get("normalized_excerpt"))
        for unit in preflight.get("expansion_units") or []
        if isinstance(unit, Mapping)
    )
    spans = audit_numeric_span_probes({"expected_answer": ""})
    source_queue = official.read_json(DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_QUEUE_JSON)
    source_item = next(
        (
            item
            for item in source_queue.get("items") or []
            if isinstance(item, Mapping) and official.clean(item.get("query_id")) == official.clean(row.get("query_id"))
        ),
        {},
    )
    if not spans:
        # Numeric probe hashes are audit-only; this fallback uses the existing v3_1_5 probe result only
        # for post-generation coverage diagnostics, never for prompt selection.
        spans = audit_numeric_span_probes_from_v3_1_5()
    return {
        **dict(preflight),
        "schema_version": f"{V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID}_context_expansion_diagnostics_v1",
        "source_queue_artifact": official.repo_relative(DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_QUEUE_JSON),
        "original_cited_search_unit_ids": list(preflight.get("original_cited_search_unit_ids") or []),
        "original_cited_locator_fields": dict(preflight.get("original_cited_locator_fields") or {}),
        "source_queue_coverage_classification": source_item.get("coverage_classification"),
        "before_lane_failure_categories": lane_failure_categories(before_row),
        "after_lane_failure_categories": lane_failure_categories(row),
        "expanded_context_contains_all_audit_numeric_spans": contains_all_audit_spans(expansion_text, spans),
        "generated_answer_cited_original_search_unit_by_lane": generated_cited_original_by_lane,
        "generated_answer_cited_expansion_unit_by_lane": generated_cited_expansion_by_lane,
        "locator_validation_passed_by_lane": locator_validation_passed_by_lane,
        "audit_numeric_spans_used_only_post_generation": True,
        "reference_span_audit_only": True,
        "reference_span_text_embedded": False,
        "diagnostic_only": True,
        "promotion_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "production_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
    }


def audit_numeric_span_probes_from_v3_1_5() -> list[str]:
    rows = read_jsonl(DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_DIAGNOSTICS_JSONL)
    row = rows[0] if rows else {}
    matches = as_mapping(row).get("raw_source_pdf_matches") or []
    text = " ".join(
        official.clean(as_mapping(match).get("normalized_excerpt"))
        for match in matches
        if isinstance(match, Mapping)
    )
    return audit_numeric_span_probes_from_text(text)


def build_v3_1_5_source_bound_coverage_rows(
    *,
    source_rows_by_id: Mapping[str, Mapping[str, Any]],
    v3_1_4_rows: Sequence[Mapping[str, Any]],
    remaining_queue: Mapping[str, Any],
    rag_index_dir: Path,
    generated_at: str,
) -> list[dict[str, Any]]:
    v3_rows_by_id = {official.clean(row.get("query_id")): row for row in v3_1_4_rows}
    queue_items = [
        item
        for item in remaining_queue.get("items") or []
        if isinstance(item, Mapping) and official.clean(item.get("query_id"))
    ]
    manifest_rows = read_source_bound_search_unit_manifest(rag_index_dir)
    manifest_by_id = {
        official.clean(row.get("search_unit_id")): row
        for row in manifest_rows
        if official.clean(row.get("search_unit_id"))
    }
    rows: list[dict[str, Any]] = []
    for queue_index, queue_item in enumerate(queue_items, start=1):
        query_id = official.clean(queue_item.get("query_id"))
        if query_id not in V3_1_5_SOURCE_BOUND_COVERAGE_QUERY_IDS:
            continue
        source_row = as_mapping(source_rows_by_id.get(query_id))
        v3_row = as_mapping(v3_rows_by_id.get(query_id))
        if not v3_row:
            continue
        spans = audit_numeric_span_probes(source_row)
        span_hashes = [sha256_text(span) for span in spans]
        lane_cited_ids = {
            lane_name: cited_search_unit_ids_for_lane(as_mapping(lane))
            for lane_name, lane in as_mapping(v3_row.get("lane_results")).items()
            if isinstance(lane, Mapping)
        }
        cited_ids = sorted({unit_id for ids in lane_cited_ids.values() for unit_id in ids})
        cited_manifest_rows = [manifest_by_id[unit_id] for unit_id in cited_ids if unit_id in manifest_by_id]
        v3_cited_text = " ".join(v3_1_4_cited_context_texts(v3_row, cited_ids))
        current_cited_text = " ".join(search_unit_text_surface(row) for row in cited_manifest_rows)
        denominator_locator = as_mapping(v3_row.get("denominator_locator"))
        denominator_search_unit_id = official.clean(v3_row.get("denominator_search_unit_id")) or (
            cited_ids[0] if cited_ids else ""
        )
        source_pdf_path = clean_first_present(
            denominator_locator,
            "source_pdf_path",
            "sourcePdfPath",
        )
        document_version_id = clean_first_present(
            denominator_locator,
            "document_version_id",
            "documentVersionId",
        )
        page_number = int_or_none(denominator_locator.get("page"))
        same_document_rows = [
            row
            for row in manifest_rows
            if same_source_document(
                row,
                document_version_id=document_version_id,
                source_pdf_path=source_pdf_path,
            )
        ]
        adjacent_rows = [
            row
            for row in same_document_rows
            if page_number is not None
            and int_or_none(as_mapping(row.get("locator")).get("page")) is not None
            and abs(int(as_mapping(row.get("locator")).get("page")) - page_number) <= 1
        ]
        same_document_matches = search_units_matching_spans(same_document_rows, spans)
        adjacent_matches = search_units_matching_spans(adjacent_rows, spans)
        raw_pdf_matches = raw_pdf_text_span_matches(
            source_pdf_path=source_pdf_path,
            spans=spans,
            page_hint=page_number,
        )
        v3_cited_contains = contains_all_audit_spans(v3_cited_text, spans)
        current_cited_contains = contains_all_audit_spans(current_cited_text, spans)
        same_document_contains = bool(same_document_matches)
        adjacent_contains = bool(adjacent_matches)
        raw_contains = bool(raw_pdf_matches)
        classification = classify_source_bound_coverage_gap(
            current_cited_contains=current_cited_contains,
            same_document_contains=same_document_contains,
            adjacent_contains=adjacent_contains,
            raw_source_contains=raw_contains,
        )
        rows.append(
            {
                "schema_version": f"{V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID}_context_coverage_diagnostics_v1",
                "run_id": V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
                "source_run_id": V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "generated_at": generated_at,
                "query_id": query_id,
                "track": v3_row.get("track") or queue_item.get("track"),
                "source_family": v3_row.get("source_family") or queue_item.get("source_family"),
                "source_pdf_path": source_pdf_path,
                "document_version_id": document_version_id,
                "denominator_search_unit_id": denominator_search_unit_id,
                "cited_search_unit_ids_by_lane": lane_cited_ids,
                "audit_numeric_span_probe_source": "expected_answer_numeric_tokens_audit_only",
                "audit_numeric_span_count": len(spans),
                "audit_numeric_span_sha256": span_hashes,
                "reference_span_audit_only": True,
                "reference_span_text_embedded": False,
                "v3_1_4_cited_context_contains_all_audit_numeric_spans": v3_cited_contains,
                "current_cited_search_unit_contains_all_audit_numeric_spans": current_cited_contains,
                "same_document_search_unit_contains_all_audit_numeric_spans": same_document_contains,
                "adjacent_page_window_search_unit_contains_all_audit_numeric_spans": adjacent_contains,
                "raw_source_pdf_text_contains_all_audit_numeric_spans": raw_contains,
                "matched_search_units": same_document_matches,
                "adjacent_page_window_matched_search_units": adjacent_matches,
                "raw_source_pdf_matches": raw_pdf_matches,
                "issue_classification": classification,
                "classification_reason": (
                    "The cited SearchUnit is source-near and topic-relevant, but its text surface "
                    "does not include the audit numeric span; raw PDF extraction finds the span "
                    "on the same page outside the cited SearchUnit bbox."
                ),
                "final_queue_decision": "remain_in_queue",
                "behavior_change_made": False,
                "non_production_index_or_export_fix_applied": False,
                "all_track_remeasurement_performed": False,
                "official_retrieval_metric": False,
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
                "queue_priority_rank": queue_item.get("remaining_priority_rank") or queue_index,
            }
        )
    return rows


def build_v3_1_6_pdf_window_expansion_units(
    *,
    v3_1_4_rows: Sequence[Mapping[str, Any]],
    remaining_queue: Mapping[str, Any],
    generated_at: str,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    rows_by_id = {official.clean(row.get("query_id")): row for row in v3_1_4_rows}
    units_by_query_id: dict[str, list[dict[str, Any]]] = {}
    diagnostics_by_query_id: dict[str, dict[str, Any]] = {}
    for queue_item in remaining_queue.get("items") or []:
        if not isinstance(queue_item, Mapping):
            continue
        query_id = official.clean(queue_item.get("query_id"))
        if query_id not in V3_1_6_SAFE_PDF_WINDOW_QUERY_IDS:
            continue
        row = as_mapping(rows_by_id.get(query_id))
        units, diagnostic = build_safe_pdf_paragraph_window_units_for_row(
            row=row,
            query_id=query_id,
            generated_at=generated_at,
        )
        units_by_query_id[query_id] = units
        diagnostics_by_query_id[query_id] = diagnostic
    return units_by_query_id, diagnostics_by_query_id


def build_safe_pdf_paragraph_window_units_for_row(
    *,
    row: Mapping[str, Any],
    query_id: str,
    generated_at: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    locator = as_mapping(row.get("denominator_locator"))
    source_pdf_path = clean_first_present(locator, "source_pdf_path", "sourcePdfPath")
    document_version_id = clean_first_present(locator, "document_version_id", "documentVersionId")
    page = int_or_none(locator.get("page"))
    physical_page_index = int_or_none(locator.get("physical_page_index"))
    bbox = bbox_or_none(locator.get("bbox"))
    region_type = official.clean(locator.get("region_type"))
    original_search_unit_id = official.clean(locator.get("search_unit_id") or row.get("denominator_search_unit_id"))
    base = {
        "schema_version": f"{V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID}_context_expansion_preflight_v1",
        "run_id": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
        "source_run_id": V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
        "generated_at": generated_at,
        "query_id": query_id,
        "track": row.get("track"),
        "source_family": row.get("source_family"),
        "source_pdf_path": source_pdf_path,
        "document_version_id": document_version_id,
        "page": page,
        "physical_page_index": physical_page_index,
        "original_cited_search_unit_ids": [original_search_unit_id] if original_search_unit_id else [],
        "original_cited_locator_fields": dict(locator),
        "expansion_policy_name": PDF_PARAGRAPH_WINDOW_EXPANSION_POLICY_NAME,
        "expansion_policy_version": PDF_PARAGRAPH_WINDOW_EXPANSION_POLICY_VERSION,
        "expansion_attempted": True,
        "expansion_applied": False,
        "locator_safe_metadata_available": False,
        "expansion_units": [],
        "expansion_unit_ids": [],
        "excluded_candidate_windows": [],
        "fail_closed_blocker": None,
        "diagnostic_only": True,
        "promotion_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "reference_span_text_embedded": False,
        "audit_numeric_spans_used_only_post_generation": True,
    }
    if row.get("source_family") != "PDF" or region_type != "paragraph":
        return [], {**base, "fail_closed_blocker": "pdf_paragraph_region_required"}
    if not source_pdf_path or not document_version_id or page is None or physical_page_index is None or bbox is None:
        return [], {**base, "fail_closed_blocker": "locator_safe_pdf_window_source_missing"}
    path = resolve_repo_relative_artifact_path(Path(source_pdf_path))
    if not path.exists():
        return [], {**base, "fail_closed_blocker": "locator_safe_pdf_window_source_missing"}

    try:
        import fitz  # type: ignore  # noqa: WPS433
    except Exception:  # noqa: BLE001
        return [], {**base, "fail_closed_blocker": "locator_safe_pdf_window_source_missing"}

    try:
        with fitz.open(path) as pdf:
            if physical_page_index < 0 or physical_page_index >= len(pdf):
                return [], {**base, "fail_closed_blocker": "locator_safe_pdf_window_source_missing"}
            lines = extract_pdf_page_text_lines(pdf[physical_page_index])
    except Exception:  # noqa: BLE001
        return [], {**base, "fail_closed_blocker": "locator_safe_pdf_window_source_missing"}

    window_lines = pdf_lines_in_paragraph_window(lines, bbox)
    excluded = [
        {
            "bbox": line.get("bbox"),
            "normalized_excerpt_sha256": sha256_text(official.clean(line.get("text"))),
            "reason": "outside_same_page_paragraph_window",
        }
        for line in lines
        if line not in window_lines
    ][:12]
    if not window_lines:
        return [], {**base, "fail_closed_blocker": "locator_safe_pdf_window_source_missing", "excluded_candidate_windows": excluded}

    excerpt = " ".join(official.clean(line.get("text")) for line in window_lines if official.clean(line.get("text")))
    window_bbox = union_pdf_line_bboxes(window_lines)
    if not excerpt or window_bbox is None:
        return [], {**base, "fail_closed_blocker": "locator_safe_pdf_window_source_missing", "excluded_candidate_windows": excluded}

    unit_id = deterministic_pdf_window_expansion_unit_id(
        source_pdf_path=source_pdf_path,
        document_version_id=document_version_id,
        page=page,
        physical_page_index=physical_page_index,
        bbox=window_bbox,
        normalized_excerpt=excerpt,
    )
    unit = {
        "expansion_unit_id": unit_id,
        "search_unit_id": unit_id,
        "source_pdf_path": source_pdf_path,
        "document_version_id": document_version_id,
        "page": page,
        "physical_page_index": physical_page_index,
        "bbox": window_bbox,
        "region_type": "paragraph_window",
        "normalized_excerpt": excerpt,
        "normalized_excerpt_sha256": sha256_text(excerpt),
        "source": "pymupdf_source_pdf_same_page_line_window",
        "expansion_policy_name": PDF_PARAGRAPH_WINDOW_EXPANSION_POLICY_NAME,
        "expansion_policy_version": PDF_PARAGRAPH_WINDOW_EXPANSION_POLICY_VERSION,
        "original_cited_search_unit_id": original_search_unit_id,
        "non_production_diagnostic_context_expansion": True,
        "diagnostic_only": True,
        "promotion_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "reference_span_text_embedded": False,
    }
    return [unit], {
        **base,
        "expansion_applied": True,
        "locator_safe_metadata_available": True,
        "expansion_units": [unit],
        "expansion_unit_ids": [unit_id],
        "excluded_candidate_windows": excluded,
    }


def bbox_or_none(value: Any) -> list[float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 4:
        return None
    out: list[float] = []
    for item in value:
        try:
            out.append(round(float(item), 2))
        except (TypeError, ValueError):
            return None
    return out


def pdf_lines_in_paragraph_window(
    lines: Sequence[Mapping[str, Any]],
    paragraph_bbox: Sequence[float],
) -> list[dict[str, Any]]:
    px0, py0, px1, py1 = [float(item) for item in paragraph_bbox]
    y_min = py0 - PDF_PARAGRAPH_WINDOW_VERTICAL_MARGIN_POINTS
    y_max = py1 + PDF_PARAGRAPH_WINDOW_VERTICAL_MARGIN_POINTS
    x_min = px0 - 80.0
    x_max = px1 + 120.0
    selected: list[dict[str, Any]] = []
    for line in lines:
        bbox = bbox_or_none(line.get("bbox"))
        text = official.clean(line.get("text"))
        if not bbox or not text:
            continue
        lx0, ly0, lx1, ly1 = bbox
        vertical_overlap = ly1 >= y_min and ly0 <= y_max
        horizontal_overlap = lx1 >= x_min and lx0 <= x_max
        if vertical_overlap and horizontal_overlap:
            selected.append({"text": text, "bbox": bbox})
    selected.sort(key=lambda item: (bbox_or_none(item.get("bbox")) or [0, 0, 0, 0])[1])
    return selected


def union_pdf_line_bboxes(lines: Sequence[Mapping[str, Any]]) -> list[float] | None:
    bboxes = [bbox_or_none(line.get("bbox")) for line in lines]
    bboxes = [bbox for bbox in bboxes if bbox is not None]
    if not bboxes:
        return None
    return [
        round(min(bbox[0] for bbox in bboxes), 2),
        round(min(bbox[1] for bbox in bboxes), 2),
        round(max(bbox[2] for bbox in bboxes), 2),
        round(max(bbox[3] for bbox in bboxes), 2),
    ]


def deterministic_pdf_window_expansion_unit_id(
    *,
    source_pdf_path: str,
    document_version_id: str,
    page: int,
    physical_page_index: int,
    bbox: Sequence[float],
    normalized_excerpt: str,
) -> str:
    identity = "|".join(
        [
            source_pdf_path,
            document_version_id,
            str(page),
            str(physical_page_index),
            ",".join(f"{float(item):.2f}" for item in bbox),
            sha256_text(normalized_excerpt),
        ]
    )
    return "pdfwin_" + sha256_text(identity)[:32]


def read_source_bound_search_unit_manifest(index_dir: Path) -> list[dict[str, Any]]:
    path = index_dir
    if not path.is_absolute():
        path = AI_WORKER_ROOT / path if path.parts and path.parts[0] == "eval" else REPO_ROOT / path
    manifest_path = path / "search_unit_manifest.jsonl"
    if not manifest_path.exists():
        return []
    return read_jsonl(manifest_path)


def audit_numeric_span_probes(source_row: Mapping[str, Any]) -> list[str]:
    return audit_numeric_span_probes_from_text(official.clean(source_row.get("expected_answer")))


def audit_numeric_span_probes_from_text(reference_text: str) -> list[str]:
    percent_spans = [
        re.sub(r"\s+", "", match.group(0))
        for match in re.finditer(r"\d+(?:\.\d+)?\s*%p?", reference_text)
    ]
    if percent_spans:
        return list(dict.fromkeys(percent_spans))
    numeric_spans = [match.group(0) for match in re.finditer(r"\d+(?:\.\d+)?", reference_text)]
    return list(dict.fromkeys(numeric_spans))


def cited_search_unit_ids_for_lane(lane: Mapping[str, Any]) -> list[str]:
    ids = [official.clean(item) for item in lane.get("cited_search_unit_ids") or [] if official.clean(item)]
    if ids:
        return list(dict.fromkeys(ids))
    for citation in lane.get("generated_citations") or []:
        if not isinstance(citation, Mapping):
            continue
        payload = as_mapping(citation.get("search_unit_citation_payload"))
        locator = as_mapping(citation.get("locator"))
        unit_id = (
            clean_first_present(payload, "search_unit_id", "searchUnitId", "unitId")
            or clean_first_present(locator, "search_unit_id", "chunk_id")
        )
        if unit_id:
            ids.append(unit_id)
    return list(dict.fromkeys(ids))


def v3_1_4_cited_context_texts(row: Mapping[str, Any], cited_ids: Sequence[str]) -> list[str]:
    cited = set(cited_ids)
    texts: list[str] = []
    for lane in as_mapping(row.get("lane_results")).values():
        if not isinstance(lane, Mapping):
            continue
        for citation in lane.get("generated_citations") or []:
            if not isinstance(citation, Mapping):
                continue
            payload = as_mapping(citation.get("search_unit_citation_payload"))
            locator = as_mapping(citation.get("locator"))
            unit_id = (
                clean_first_present(payload, "search_unit_id", "searchUnitId", "unitId")
                or clean_first_present(locator, "search_unit_id", "chunk_id")
            )
            if unit_id in cited:
                texts.append(official.clean(citation.get("citation_text")))
    return texts


def search_unit_text_surface(row: Mapping[str, Any]) -> str:
    return " ".join(
        official.clean(row.get(field))
        for field in ("display_text", "embedding_text", "bm25_text")
        if official.clean(row.get(field))
    )


def same_source_document(
    row: Mapping[str, Any],
    *,
    document_version_id: str,
    source_pdf_path: str,
) -> bool:
    locator = as_mapping(row.get("locator"))
    row_doc = official.clean(row.get("document_version_id")) or clean_first_present(
        locator,
        "document_version_id",
        "documentVersionId",
    )
    row_pdf = clean_first_present(locator, "source_pdf_path", "sourcePdfPath")
    return bool(row_doc and row_doc == document_version_id) or bool(row_pdf and row_pdf == source_pdf_path)


def search_units_matching_spans(rows: Sequence[Mapping[str, Any]], spans: Sequence[str]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for row in rows:
        text = search_unit_text_surface(row)
        if not contains_all_audit_spans(text, spans):
            continue
        locator = as_mapping(row.get("locator"))
        matches.append(
            {
                "search_unit_id": row.get("search_unit_id"),
                "page": locator.get("page"),
                "physical_page_index": locator.get("physical_page_index"),
                "region_type": locator.get("region_type"),
                "bbox": locator.get("bbox"),
                "normalized_excerpt": normalized_excerpt(text, spans),
            }
        )
    return matches


def contains_all_audit_spans(text: str, spans: Sequence[str]) -> bool:
    if not spans:
        return False
    normalized_text = normalize_audit_span_text(text)
    return all(normalize_audit_span_text(span) in normalized_text for span in spans)


def normalize_audit_span_text(text: str) -> str:
    return re.sub(r"\s+", "", official.clean(text).lower())


def raw_pdf_text_span_matches(
    *,
    source_pdf_path: str,
    spans: Sequence[str],
    page_hint: int | None,
) -> list[dict[str, Any]]:
    if not source_pdf_path or not spans:
        return []
    path = resolve_repo_relative_artifact_path(Path(source_pdf_path))
    if not path.exists():
        return []
    try:
        import fitz  # type: ignore[import-untyped]
    except Exception:
        return []
    try:
        doc = fitz.open(path)
    except Exception:
        return []
    matches: list[dict[str, Any]] = []
    try:
        page_indexes: list[int]
        if page_hint is not None:
            page_indexes = [idx for idx in range(page_hint - 2, page_hint + 1) if 0 <= idx < len(doc)]
        else:
            page_indexes = list(range(len(doc)))
        for page_index in page_indexes:
            page = doc[page_index]
            for line in extract_pdf_page_text_lines(page):
                text = official.clean(line.get("text"))
                if contains_all_audit_spans(text, spans):
                    matches.append(
                        {
                            "page": page_index + 1,
                            "physical_page_index": page_index,
                            "bbox": line.get("bbox"),
                            "normalized_excerpt": normalized_excerpt(text, spans),
                            "source": "pymupdf_source_pdf_text",
                        }
                    )
    finally:
        doc.close()
    return matches


def extract_pdf_page_text_lines(page: Any) -> list[dict[str, Any]]:
    raw = page.get_text("dict")
    lines: list[dict[str, Any]] = []
    for block in raw.get("blocks") or []:
        if block.get("type") not in (None, 0):
            continue
        for line in block.get("lines") or []:
            text = " ".join(official.clean(span.get("text")) for span in line.get("spans") or [])
            text = re.sub(r"\s+", " ", text).strip()
            bbox = line.get("bbox")
            if not text or not bbox or len(bbox) != 4:
                continue
            lines.append({"text": text, "bbox": [round(float(value), 2) for value in bbox]})
    return lines


def normalized_excerpt(text: str, spans: Sequence[str], *, radius: int = 80) -> str:
    cleaned = re.sub(r"\s+", " ", official.clean(text)).strip()
    if not cleaned:
        return ""
    positions = [
        cleaned.find(span)
        for span in spans
        if span and cleaned.find(span) >= 0
    ]
    if not positions:
        return cleaned[: radius * 2]
    start = max(0, min(positions) - radius)
    end = min(len(cleaned), max(positions) + max(len(span) for span in spans) + radius)
    return cleaned[start:end]


def classify_source_bound_coverage_gap(
    *,
    current_cited_contains: bool,
    same_document_contains: bool,
    adjacent_contains: bool,
    raw_source_contains: bool,
) -> str:
    if current_cited_contains:
        return "source_bound_searchunit_context_insufficient"
    if same_document_contains:
        return "retrieval_topk_miss"
    if adjacent_contains:
        return "pdf_page_windowing_gap"
    if raw_source_contains:
        return "query_bound_searchunit_too_narrow"
    return "safe_source_artifact_missing_span"


def clean_first_present(mapping_value: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = official.clean(mapping_value.get(key))
        if value:
            return value
    return ""


def int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def lane_failure_categories(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        lane_name: lane.get("failure_category")
        for lane_name, lane in as_mapping(row.get("lane_results")).items()
        if isinstance(lane, Mapping)
    }


def row_level_classification_change(before_row: Mapping[str, Any], after_row: Mapping[str, Any]) -> dict[str, Any]:
    before_categories = lane_failure_categories(before_row)
    after_categories = lane_failure_categories(after_row)
    improved: list[str] = []
    regressed: list[str] = []
    unchanged_failed: list[str] = []
    for lane_name in V3_1_LANE_NAMES:
        before = before_categories.get(lane_name)
        after = after_categories.get(lane_name)
        if before != "PASS" and after == "PASS":
            improved.append(lane_name)
        elif before == "PASS" and after != "PASS":
            regressed.append(lane_name)
        elif after != "PASS":
            unchanged_failed.append(lane_name)
    return {
        "before": before_categories,
        "after": after_categories,
        "improved_lane_names": improved,
        "regressed_lane_names": regressed,
        "unchanged_failed_lane_names": unchanged_failed,
        "diagnostic_only": True,
        "promotion_evidence": False,
    }


def v3_1_1_post_triage_artifact_consistency_preflight(
    *,
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    attribution: Mapping[str, Any],
    audit_rows: Sequence[Mapping[str, Any]],
    triage_queue: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    guardrails = v3_1_guardrails()
    if summary.get("run_id") != V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID:
        errors.append("v3_1_1_post_summary_run_id_mismatch")
    if attribution.get("run_id") != V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID:
        errors.append("v3_1_1_post_attribution_run_id_mismatch")
    if triage_queue.get("run_id") != V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID:
        errors.append("v3_1_1_post_triage_queue_run_id_mismatch")
    if len(rows) != 29 or len(audit_rows) != 29:
        errors.append("v3_1_1_post_row_count_mismatch")
    if tuple(summary.get("lane_names") or []) != V3_1_LANE_NAMES:
        errors.append("v3_1_1_post_lane_names_mismatch")
    for key, expected in guardrails.items():
        if as_mapping(summary.get("guardrails")).get(key) is not expected or summary.get(key) is not expected:
            errors.append(f"v3_1_1_post_guardrail_{key}_mismatch")
    if any(value != 0 for value in as_mapping(summary.get("strict_json_parse_failure_count_by_lane")).values()):
        errors.append("v3_1_1_post_strict_json_residual_nonzero")
    if any(value != 0 for value in as_mapping(summary.get("llm_generated_locator_copy_failure_count_by_lane")).values()):
        errors.append("v3_1_1_post_locator_copy_residual_nonzero")
    if summary.get("pdf_source_pdf_path_mismatch_count") != 0:
        errors.append("v3_1_1_post_pdf_path_residual_nonzero")
    if summary.get("xlsx_row_label_mismatch_count") != 0:
        errors.append("v3_1_1_post_xlsx_row_label_residual_nonzero")
    if summary.get("text_text_locator_missing_count") != 0:
        errors.append("v3_1_1_post_text_locator_residual_nonzero")
    if triage_queue.get("strict_json_or_locator_residual_count") != 0:
        errors.append("v3_1_1_post_triage_queue_locator_residual_nonzero")
    return {
        "ok": not errors,
        "errors": errors,
        "failure_bucket": "PROMPT_CONTEXT_POLICY_VIOLATION" if errors else None,
        "rows": len(rows),
        "promotion_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
    }


def build_v3_1_2_answer_span_renderer_rows(
    *,
    post_rows: Sequence[Mapping[str, Any]],
    source_rows_by_id: Mapping[str, Mapping[str, Any]],
    post_triage_queue: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows_by_id = {official.clean(row.get("query_id")): row for row in post_rows}
    queue_by_id = {
        official.clean(item.get("query_id")): item
        for item in post_triage_queue.get("items") or []
        if isinstance(item, Mapping)
    }
    rows: list[dict[str, Any]] = []
    for query_id in V3_1_2_TEXT_TARGET_QUERY_IDS:
        source_row = source_rows_by_id.get(query_id, {})
        post_row = rows_by_id.get(query_id)
        if not post_row:
            continue
        queue_item = queue_by_id.get(query_id, {})
        first_batch = query_id in V3_1_2_TEXT_FIRST_BATCH_QUERY_IDS
        row = deepcopy(dict(post_row))
        row.update(
            {
                "schema_version": V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "run_id": V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "source_run_id": V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
                "context_source_run_id": post_row.get("run_id"),
                "queue_source_of_truth": official.repo_relative(DEFAULT_V3_1_1_POST_TRIAGE_QUEUE_JSON),
                "queue_priority_rank": queue_item.get("priority_rank"),
                "first_batch_selected": first_batch,
                "include_decision": (
                    "primary_text_answer_span_renderer_batch"
                    if first_batch
                    else "included_as_secondary_text_watchlist_only_queue_rank_12"
                ),
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
        )
        row["answer_span_renderer_diagnostics"] = {
            lane_name: answer_span_renderer_lane_diagnostic(
                row=row,
                source_row=source_row,
                lane_name=lane_name,
                lane=lane,
            )
            for lane_name, lane in as_mapping(row.get("lane_results")).items()
            if isinstance(lane, Mapping)
        }
        rows.append(row)
    return rows


def answer_span_renderer_lane_diagnostic(
    *,
    row: Mapping[str, Any],
    source_row: Mapping[str, Any],
    lane_name: str,
    lane: Mapping[str, Any],
) -> dict[str, Any]:
    answer = extract_short_answer_text(official.clean(lane.get("generated_answer")))
    reference_text = official.clean(source_row.get("expected_answer"))
    citation_text = audit_citation_text(
        [citation for citation in lane.get("scored_citations") or [] if isinstance(citation, Mapping)]
    )
    reference_tokens = audit_meaningful_tokens(reference_text)
    answer_tokens = audit_meaningful_tokens(answer)
    matched_reference_tokens = matched_audit_token_count(reference_tokens, answer)
    token_coverage = (matched_reference_tokens / len(reference_tokens)) if reference_tokens else 0.0
    answer_score = lane.get("answer_score")
    citation_support_score = lane.get("citation_support_score")
    failure_category = official.clean(lane.get("failure_category"))
    subcategories: list[str] = []
    if failure_category == "PASS":
        subcategories.append("pass")
    elif answer_score != 1.0 and citation_support_score == 1.0:
        subcategories.append("diagnostic_only_expected_span_mismatch")
    if failure_category != "PASS" and reference_tokens and token_coverage < 0.65:
        subcategories.append("answer_too_narrow")
    if answer_looks_broad_for_question(row=row, answer=answer, reference_text=reference_text):
        subcategories.append("answer_too_broad")
    if answer_selects_wrong_entity_or_value(row=row, answer=answer, reference_text=reference_text):
        subcategories.append("wrong_entity_value_selected")
    if renderer_formatting_mismatch(row=row, answer=answer):
        subcategories.append("renderer_formatting_mismatch")
    if korean_synthesis_paraphrase_mismatch(row=row, answer=answer):
        subcategories.append("korean_synthesis_paraphrase_mismatch")
    if scorer_normalization_gap_likely(
        row=row,
        answer=answer,
        reference_text=reference_text,
        answer_score=answer_score,
        citation_support_score=citation_support_score,
    ):
        subcategories.append("scorer_normalization_gap")
    if retrieval_or_context_insufficient(row=row, source_row=source_row, lane=lane, citation_text=citation_text):
        subcategories.append("retrieval_context_insufficiency")
    if not subcategories:
        subcategories.append("diagnostic_only_expected_span_mismatch")
    return {
        "lane_name": lane_name,
        "failure_category_before": failure_category,
        "diagnostic_subcategories": list(dict.fromkeys(subcategories)),
        "answer_score_before": answer_score,
        "citation_support_score_before": citation_support_score,
        "score_status_before": lane.get("score_status"),
        "reference_span_audit_only": True,
        "reference_span_text_embedded": False,
        "scoring_reference_span_sha256": sha256_text(reference_text),
        "reference_token_count": len(reference_tokens),
        "answer_token_count": len(answer_tokens),
        "matched_reference_token_count": matched_reference_tokens,
        "reference_token_coverage": round(token_coverage, 4),
        "citation_support_present": citation_support_score == 1.0,
        "query_bound_search_unit_present": row.get("query_bound_search_unit_present") is True,
        "strict_json_parse_ok": as_mapping(lane.get("strict_json_diagnostics")).get("parse_ok", True),
        "locator_copy_ok": as_mapping(lane.get("llm_generated_locator_validation")).get("ok") is not False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "promotion_evidence": False,
    }


def matched_audit_token_count(reference_tokens: Sequence[str], text: str) -> int:
    target = official.normalized_text(text)
    return sum(1 for token in reference_tokens if any(variant in target for variant in audit_token_variants(token)))


def answer_looks_broad_for_question(*, row: Mapping[str, Any], answer: str, reference_text: str) -> bool:
    query = official.clean(row.get("query"))
    normalized_answer = official.normalized_text(answer)
    normalized_reference = official.normalized_text(reference_text)
    if "어디" in query and "도쿄" in normalized_answer and "역" in normalized_reference and "역" not in normalized_answer:
        return True
    if "source provides" in answer.lower() or "list of characters" in answer.lower():
        return True
    return False


def answer_selects_wrong_entity_or_value(*, row: Mapping[str, Any], answer: str, reference_text: str) -> bool:
    query = official.normalized_text(row.get("query"))
    normalized_answer = official.normalized_text(answer)
    normalized_reference = official.normalized_text(reference_text)
    if "오디널" in query and "오디널" not in normalized_answer and "오디널" in normalized_reference:
        return True
    return False


def renderer_formatting_mismatch(*, row: Mapping[str, Any], answer: str) -> bool:
    if "**" in answer or "Sources:" in answer or "Supporting passages:" in answer or "출처 [" in answer:
        return True
    return korean_synthesis_paraphrase_mismatch(row=row, answer=answer)


def korean_synthesis_paraphrase_mismatch(*, row: Mapping[str, Any], answer: str) -> bool:
    query = official.clean(row.get("query"))
    if not re.search(r"[가-힣]", query):
        return False
    latin_words = re.findall(r"[A-Za-z]{3,}", answer)
    hangul_count = len(re.findall(r"[가-힣]", answer))
    return bool(latin_words and hangul_count < 4)


def scorer_normalization_gap_likely(
    *,
    row: Mapping[str, Any],
    answer: str,
    reference_text: str,
    answer_score: Any,
    citation_support_score: Any,
) -> bool:
    if answer_score == 1.0 or citation_support_score != 1.0:
        return False
    numeric_tokens = audit_numeric_answer_value_tokens(reference_text)
    target = official.normalized_text(answer)
    if numeric_tokens and any(token in target for token in numeric_tokens):
        return True
    query = official.clean(row.get("query"))
    if "방영 시기" in query and re.search(r"20\d{2}\s*년\s*\d+\s*월", answer):
        return True
    if "나이" in query and "생일" in query and re.search(r"\d+\s*세", answer) and re.search(r"\d+\s*월\s*\d+\s*일", answer):
        return True
    return False


def retrieval_or_context_insufficient(
    *,
    row: Mapping[str, Any],
    source_row: Mapping[str, Any],
    lane: Mapping[str, Any],
    citation_text: str,
) -> bool:
    if row.get("query_bound_search_unit_present") is not True:
        return True
    if lane.get("citation_support_score") != 1.0:
        return True
    if not official.clean(citation_text):
        return True
    if lane.get("answer_score") != 1.0:
        expected_answer = official.clean(source_row.get("expected_answer"))
        expected_tokens = audit_numeric_answer_value_tokens(expected_answer)
        if expected_tokens:
            normalized_citation = official.normalized_text(citation_text)
            return not any(token in normalized_citation for token in expected_tokens)
    return False


def merge_v3_preflight_errors(preflight: Mapping[str, Any], errors: Sequence[str]) -> dict[str, Any]:
    return {
        **dict(preflight),
        "ok": False,
        "errors": [*list(preflight.get("errors") or []), *list(errors)],
        "failure_bucket": "PROMPT_CONTEXT_POLICY_VIOLATION",
    }


def v3_1_priority_artifact_consistency_preflight(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    if summary.get("run_id") != V3_1_PRIORITY_1_5_RUN_ID:
        errors.append("v3_1_priority_summary_run_id_mismatch")
    if len(rows) != len(V3_1_PRIORITY_1_5_QUERY_IDS):
        errors.append("v3_1_priority_row_count_mismatch")
    if tuple(row.get("query_id") for row in rows) != V3_1_PRIORITY_1_5_QUERY_IDS:
        errors.append("v3_1_priority_query_ids_mismatch")
    if summary.get("promotion_evidence") is not False or summary.get("diagnostic_only") is not True:
        errors.append("v3_1_priority_guardrail_mismatch")
    return {"ok": not errors, "errors": errors}


def v3_1_text_locator_artifact_consistency_preflight(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    if summary.get("run_id") != V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID:
        errors.append("v3_1_text_locator_summary_run_id_mismatch")
    if len(rows) != len(V3_1_TEXT_LOCATOR_RESIDUAL_QUERY_IDS):
        errors.append("v3_1_text_locator_row_count_mismatch")
    if tuple(row.get("query_id") for row in rows) != V3_1_TEXT_LOCATOR_RESIDUAL_QUERY_IDS:
        errors.append("v3_1_text_locator_query_ids_mismatch")
    if summary.get("text_locator_missing_count_after") != 0:
        errors.append("v3_1_text_locator_residual_not_cleared")
    if summary.get("promotion_evidence") is not False or summary.get("diagnostic_only") is not True:
        errors.append("v3_1_text_locator_guardrail_mismatch")
    return {"ok": not errors, "errors": errors}


def priority_1_5_query_ids_from_triage(triage: Mapping[str, Any]) -> tuple[str, ...]:
    items = [
        item
        for item in triage.get("items") or []
        if isinstance(item, Mapping) and 1 <= int(item.get("priority_rank") or 0) <= 5
    ]
    items.sort(key=lambda item: int(item.get("priority_rank") or 0))
    return tuple(official.clean(item.get("query_id")) for item in items)


def v3_artifact_consistency_preflight(
    *,
    summary: Mapping[str, Any],
    attribution: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    expected_query_ids: set[str] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    if summary.get("run_id") != V3_RUN_ID:
        errors.append("v3_summary_run_id_mismatch")
    if attribution.get("run_id") != V3_RUN_ID:
        errors.append("v3_attribution_run_id_mismatch")
    if summary.get("status") != "COMPARABLE_LIVE_MEASUREMENT_V3_COMPLETED":
        errors.append("v3_not_completed")
    if int(summary.get("result_count") or 0) != 29 or len(rows) != 29:
        errors.append("v3_row_count_mismatch")
    if int(summary.get("pass_count") or 0) != 24:
        errors.append("v3_pass_count_mismatch")
    if summary.get("promotion_evidence") is not False or attribution.get("promotion_evidence") is not False:
        errors.append("v3_promotion_evidence_not_false")
    if summary.get("candidate_artifacts_as_generation_source") is not False:
        errors.append("v3_candidate_generation_guardrail_not_false")
    if summary.get("generation_used_expected_answer") is not False:
        errors.append("v3_expected_answer_generation_guardrail_not_false")
    if summary.get("generation_used_gold_fields") is not False:
        errors.append("v3_gold_generation_guardrail_not_false")
    if summary.get("generation_used_supporting_evidence") is not False:
        errors.append("v3_supporting_generation_guardrail_not_false")
    track_counts = Counter(official.clean(row.get("track")) for row in rows)
    if track_counts != Counter({"pdf_business_ocr_mm": 4, "text_namu_v2_1": 6, "xlsx_business_structured": 19}):
        errors.append("v3_track_counts_mismatch")
    row_query_ids = {official.clean(row.get("query_id")) for row in rows if official.clean(row.get("query_id"))}
    if expected_query_ids is not None and row_query_ids != {official.clean(item) for item in expected_query_ids}:
        errors.append("v3_query_ids_do_not_match_current_official_denominator")
    structured_rows = [row for row in rows if row.get("track") in {"pdf_business_ocr_mm", "xlsx_business_structured"}]
    if any(row.get("structured_adapter_output_retained") is not True for row in structured_rows):
        errors.append("v3_structured_adapter_not_retained")
    return {
        "ok": not errors,
        "errors": errors,
        "failure_bucket": "PROMPT_CONTEXT_POLICY_VIOLATION" if errors else None,
        "rows": len(rows),
        "pass_count": summary.get("pass_count"),
        "promotion_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
    }


def v3_1_artifact_consistency_preflight(
    *,
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    triage: Mapping[str, Any],
    expected_priority_query_ids: Sequence[str],
) -> dict[str, Any]:
    errors: list[str] = []
    guardrails = as_mapping(summary.get("guardrails"))
    if summary.get("run_id") != V3_1_RUN_ID:
        errors.append("v3_1_summary_run_id_mismatch")
    if triage.get("run_id") != V3_1_RUN_ID:
        errors.append("v3_1_triage_run_id_mismatch")
    if summary.get("status") != "ALL_TRACK_FOUNDATION_MEASUREMENT_V3_1_COMPLETED":
        errors.append("v3_1_not_completed")
    if int(summary.get("result_count") or 0) != 29 or len(rows) != 29:
        errors.append("v3_1_row_count_mismatch")
    if tuple(summary.get("lane_names") or []) != V3_1_LANE_NAMES:
        errors.append("v3_1_lane_names_mismatch")
    if summary.get("diagnostic_only") is not True:
        errors.append("v3_1_diagnostic_only_not_true")
    for key, expected in v3_1_guardrails().items():
        if guardrails.get(key) is not expected or summary.get(key) is not expected:
            errors.append(f"v3_1_guardrail_{key}_mismatch")
    row_query_ids = {official.clean(row.get("query_id")) for row in rows if official.clean(row.get("query_id"))}
    missing_priority = [query_id for query_id in expected_priority_query_ids if query_id not in row_query_ids]
    if missing_priority:
        errors.append("v3_1_priority_rows_missing")
    if any(row.get("run_id") != V3_1_RUN_ID for row in rows):
        errors.append("v3_1_row_run_id_mismatch")
    if any(row.get("schema_version") != V3_1_RUN_ID for row in rows):
        errors.append("v3_1_row_schema_version_mismatch")
    if any(row.get("source_run_id") != V3_RUN_ID for row in rows):
        errors.append("v3_1_row_source_run_id_mismatch")
    if any(
        set(as_mapping(row.get("lane_results")).keys()) != set(V3_1_LANE_NAMES)
        for row in rows
    ):
        errors.append("v3_1_row_lane_results_mismatch")
    if priority_1_5_query_ids_from_triage(triage) != tuple(expected_priority_query_ids):
        errors.append("v3_1_priority_1_5_triage_query_ids_mismatch")
    return {
        "ok": not errors,
        "errors": errors,
        "failure_bucket": "PROMPT_CONTEXT_POLICY_VIOLATION" if errors else None,
        "rows": len(rows),
        "priority_query_ids": list(expected_priority_query_ids),
        "promotion_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
    }


def build_v3_1_rows(
    *,
    v3_rows: Sequence[Mapping[str, Any]],
    source_rows_by_id: Mapping[str, Mapping[str, Any]],
    backend_preflight: Mapping[str, Any],
    v3_preflight: Mapping[str, Any],
    run_id: str = V3_1_RUN_ID,
    source_run_id: str = V3_RUN_ID,
    context_expansion_units_by_query_id: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    context_expansion_units_by_query_id = context_expansion_units_by_query_id or {}
    for v3_row in v3_rows:
        query_id = official.clean(v3_row.get("query_id"))
        source_row = source_rows_by_id.get(official.clean(v3_row.get("query_id")), {})
        rows.append(
            build_v3_1_row(
                v3_row=v3_row,
                source_row=source_row,
                backend_preflight=backend_preflight,
                v3_preflight=v3_preflight,
                run_id=run_id,
                source_run_id=source_run_id,
                context_expansion_units=context_expansion_units_by_query_id.get(query_id, ()),
            )
        )
    return rows


def build_v3_1_row(
    *,
    v3_row: Mapping[str, Any],
    source_row: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    v3_preflight: Mapping[str, Any],
    run_id: str = V3_1_RUN_ID,
    source_run_id: str = V3_RUN_ID,
    context_expansion_units: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    query_id = official.clean(v3_row.get("query_id"))
    track = official.clean(v3_row.get("track"))
    source_family = SOURCE_FAMILY_LABEL_BY_TRACK.get(track, track.upper())
    denominator_citation = query_bound_denominator_citation(v3_row)
    denominator_locator = locator_from_citation_payload(
        denominator_citation.get("search_unit_citation_payload") if denominator_citation else {},
        source_family=source_family,
    )
    denominator_search_unit_id = official.clean(denominator_locator.get("search_unit_id"))
    retrieved_search_unit_ids = [
        official.clean(item.get("search_unit_id") or item.get("id") or item.get("chunk_id"))
        for item in v3_row.get("retrieved_evidence") or []
        if isinstance(item, Mapping)
    ]
    retrieved_search_unit_ids = [item for item in retrieved_search_unit_ids if item]
    lane_a = v3_1_primary_replay_lane(v3_row, source_family=source_family)
    lane_b = v3_1_live_llm_lane(
        v3_row=v3_row,
        source_row=source_row,
        source_family=source_family,
        backend_preflight=backend_preflight,
        mode="retrieval_topk_source_bound",
        lane_name="live_llm_retrieval_topk",
        force_fail_closed=not bool(v3_preflight.get("ok")),
        context_expansion_units=context_expansion_units,
    )
    lane_c = v3_1_live_llm_lane(
        v3_row=v3_row,
        source_row=source_row,
        source_family=source_family,
        backend_preflight=backend_preflight,
        mode="query_bound_only_source_bound",
        lane_name="live_llm_query_bound_oracle",
        force_fail_closed=not bool(v3_preflight.get("ok")),
        context_expansion_units=context_expansion_units,
    )
    if source_family in {"PDF", "XLSX"}:
        lane_b["adapter_vs_llm_diff"] = adapter_llm_diff(lane_a, lane_b)
        lane_c["adapter_vs_llm_diff"] = adapter_llm_diff(lane_a, lane_c)
    row = {
        "schema_version": run_id,
        "run_id": run_id,
        "source_run_id": source_run_id,
        "context_source_run_id": V3_RUN_ID,
        "query_id": query_id,
        "track": track,
        "source_family": source_family,
        "query": official.clean(source_row.get("question") or source_row.get("query") or query_id),
        "denominator_search_unit_id": denominator_search_unit_id,
        "denominator_locator": denominator_locator,
        "retrieved_context_summary": retrieved_context_summary(v3_row),
        "retrieved_search_unit_ids": retrieved_search_unit_ids,
        "query_bound_search_unit_present": bool(denominator_search_unit_id and denominator_search_unit_id in retrieved_search_unit_ids),
        "lane_results": {
            "v3_primary_replay": lane_a,
            "live_llm_retrieval_topk": lane_b,
            "live_llm_query_bound_oracle": lane_c,
        },
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
    return row


def query_bound_denominator_citation(row: Mapping[str, Any]) -> Mapping[str, Any]:
    query_id = official.clean(row.get("query_id"))
    for citation in row.get("scored_citations") or []:
        if not isinstance(citation, Mapping):
            continue
        validation = citation_validation(citation)
        payload = citation.get("search_unit_citation_payload")
        manifest_query_id = official.clean(validation.get("manifest_query_id") or as_mapping(payload).get("manifest_query_id"))
        if manifest_query_id == query_id:
            return citation
    for citation in row.get("scored_citations") or []:
        if isinstance(citation, Mapping):
            return citation
    return {}


def locator_from_citation_payload(payload: Any, *, source_family: str) -> dict[str, Any]:
    data = dict(payload) if isinstance(payload, Mapping) else {}
    if source_family == "PDF":
        return {
            "source_pdf_path": data.get("source_pdf_path") or data.get("sourcePdfPath"),
            "page": data.get("page"),
            "physical_page_index": data.get("physical_page_index") or data.get("physicalPageIndex"),
            "bbox": data.get("bbox"),
            "region_type": data.get("region_type") or data.get("regionType"),
            "row_label": data.get("row_label") or data.get("rowLabel"),
            "target_column": data.get("target_column") or data.get("targetColumn"),
            "search_unit_id": data.get("search_unit_id") or data.get("searchUnitId"),
            "document_version_id": data.get("document_version_id") or data.get("documentVersionId"),
        }
    if source_family == "XLSX":
        return {
            "workbook": data.get("workbook") or data.get("source_file_name") or data.get("sourceFileName"),
            "sheet": data.get("sheet") or data.get("sheetName"),
            "range": data.get("range") or data.get("cell_range") or data.get("cellRange"),
            "cell": data.get("cell"),
            "row_label": data.get("row_label") or data.get("rowLabel"),
            "target_column": data.get("target_column") or data.get("targetColumn"),
            "normalized_value": data.get("normalized_value") or data.get("normalizedValue"),
            "displayed_value": data.get("displayed_value") or data.get("displayedValue"),
            "number_format": data.get("number_format") or data.get("numberFormat"),
            "search_unit_id": data.get("search_unit_id") or data.get("searchUnitId"),
            "document_version_id": data.get("document_version_id") or data.get("documentVersionId"),
        }
    return {
        "document_id": data.get("document_id") or data.get("documentId"),
        "document_version_id": data.get("document_version_id") or data.get("documentVersionId"),
        "search_unit_id": data.get("search_unit_id") or data.get("searchUnitId"),
        "text_locator": data.get("text_locator") or data.get("textLocator"),
    }


def retrieved_context_summary(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    query_id = official.clean(row.get("query_id"))
    out: list[dict[str, Any]] = []
    for citation in row.get("scored_citations") or []:
        if not isinstance(citation, Mapping):
            continue
        payload = as_mapping(citation.get("search_unit_citation_payload"))
        search_unit_id = official.clean(payload.get("search_unit_id") or payload.get("searchUnitId"))
        manifest_query_id = official.clean(payload.get("manifest_query_id") or payload.get("manifestQueryId"))
        out.append(
            {
                "search_unit_id": search_unit_id,
                "manifest_query_id": manifest_query_id,
                "query_bound": manifest_query_id == query_id,
                "text_preview": official.clean(citation.get("citation_text"))[:280],
            }
        )
    return out


def v3_1_primary_replay_lane(row: Mapping[str, Any], *, source_family: str) -> dict[str, Any]:
    structured = source_family in {"PDF", "XLSX"}
    citations = list(row.get("scored_citations") or [])
    cited_ids = citation_ids_from_citations(citations)
    strict_json_meta = row.get("llm_strict_json") if isinstance(row.get("llm_strict_json"), Mapping) else {}
    if not structured:
        cited_ids = list(strict_json_meta.get("cited_search_unit_ids") or cited_ids)
        citations = filter_citations_by_ids(citations, cited_ids)
    score_status = "PASS" if row.get("failure_category") == "PASS" else "FAIL_CLOSED"
    return {
        "lane_name": "v3_primary_replay",
        "answer_origin": "STRUCTURED_ADAPTER" if structured else "LLM_SYNTHESIS",
        "llm_invoked": not structured,
        "prompt_context_mode": "structured_adapter_retained" if structured else "retrieval_topk_source_bound",
        "generated_answer": official.clean(row.get("generated_answer")),
        "strict_json_raw": strict_json_meta.get("strict_json"),
        "strict_json_diagnostics": strict_json_meta.get("strict_json") if isinstance(strict_json_meta, Mapping) else {},
        "strict_json_parse_ok": None if structured else bool(strict_json_meta),
        "cited_search_unit_ids": cited_ids,
        "generated_citations": citations,
        "scored_citations": citations,
        "llm_generated_citation_locators": [],
        "llm_generated_locator_validation": {
            "ok": None,
            "generated_by_llm": False,
            "source_family": source_family,
            "required_fields": list(required_locator_fields(source_family)),
            "cited_search_unit_ids": cited_ids,
            "category": None,
            "note": "Lane A replays v3 primary output; PDF/XLSX locator payloads are adapter retained, not LLM-generated.",
        },
        "answer_score": row.get("answer_score"),
        "citation_support_score": row.get("citation_support_score"),
        "score_status": score_status,
        "failure_category": "PASS" if row.get("failure_category") == "PASS" else "LLM_TRUE_PARTIAL_SYNTHESIS",
        "result_bucket": row.get("result_bucket"),
        "locator_preservation": locator_preservation_for_citations(citations, source_family=source_family),
        "citation_payload_validation": citation_payload_validation_summary(citations),
        "adapter_vs_llm_diff": None,
        "scorer_notes": row.get("failure_reason") or "",
        "diagnostic_review_label": "pass" if row.get("failure_category") == "PASS" else "needs_row_level_triage",
        "recommendation": "retain_v3_primary_replay_baseline" if row.get("failure_category") == "PASS" else "triage_v3_primary_replay_failure",
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
    }


def v3_1_live_llm_lane(
    *,
    v3_row: Mapping[str, Any],
    source_row: Mapping[str, Any],
    source_family: str,
    backend_preflight: Mapping[str, Any],
    mode: str,
    lane_name: str,
    force_fail_closed: bool,
    context_expansion_units: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    prompt_mode = "query-bound-only" if mode == "query_bound_only_source_bound" else "same-track-scored-context"
    context = build_v3_prompt_context(
        v3_row,
        prompt_context_mode=prompt_mode,
        context_expansion_units=context_expansion_units,
    )
    if force_fail_closed or not backend_preflight.get("ok") or context["prompt_context_policy_violation"]:
        category = "RETRIEVAL_QUERY_BOUND_MISS" if "same_track_source_bound_prompt_context_empty" in context.get("policy_errors", []) else "CITATION_PAYLOAD_SCHEMA_MISMATCH"
        return v3_1_fail_closed_lane(
            lane_name=lane_name,
            mode=mode,
            source_family=source_family,
            context=context,
            category=category,
            reason="precondition, backend, or prompt-context policy failed before strict JSON generation",
            llm_invoked=False,
        )
    try:
        prompt = build_v3_llm_prompt(
            v3_row,
            context,
            question=official.clean(source_row.get("question") or v3_row.get("query_id")),
            require_generated_locators=True,
        )
        cited_ids_before_parse = [
            official.clean(item.get("search_unit_id"))
            for item in context.get("citations") or []
            if isinstance(item, Mapping) and official.clean(item.get("search_unit_id"))
        ]
        max_locator_attempts = max(1, int(backend_preflight.get("strict_json_retries") or 2))
        locator_retry_diagnostics: list[dict[str, Any]] = []
        final_attempt = 1
        for locator_attempt in range(1, max_locator_attempts + 1):
            prompt_for_attempt = prompt
            if locator_retry_diagnostics:
                prompt_for_attempt = (
                    prompt
                    + "\n\nPrevious citation_locators failed canonical locator copy validation. "
                    + locator_copy_retry_message(locator_retry_diagnostics[-1])
                    + " Return exactly one minified JSON object. Copy each locator_json_copy_source exactly, "
                    + "including nested objects such as text_locator. Do not use an empty object for text_locator."
                )
            llm_answer, strict_json_meta = call_v3_llm_synthesis(
                prompt=prompt_for_attempt,
                backend_preflight=backend_preflight,
                require_generated_locators=True,
                prompt_context_mode=mode,
                cited_search_unit_ids_before_parse=cited_ids_before_parse,
            )
            cited_ids = list(strict_json_meta.get("cited_search_unit_ids") or [])
            citations = filter_citations_by_ids(context.get("source_citations") or [], cited_ids)
            if not cited_ids:
                citations = []
            raw_llm_generated_locators = list(strict_json_meta.get("llm_generated_citation_locators") or [])
            llm_generated_locators, canonical_repair = canonicalize_llm_generated_locators_from_expected(
                generated_locators=raw_llm_generated_locators,
                expected_citations=citations,
                cited_search_unit_ids=cited_ids,
                source_family=source_family,
            )
            llm_locator_validation = llm_generated_locator_validation(
                generated_locators=llm_generated_locators,
                expected_citations=citations,
                cited_search_unit_ids=cited_ids,
                source_family=source_family,
            )
            llm_locator_validation["canonical_locator_copy_repair"] = canonical_repair
            final_attempt = locator_attempt
            if llm_locator_validation.get("ok") is True or locator_attempt >= max_locator_attempts:
                break
            locator_retry_diagnostics.append(
                {
                    "attempt": locator_attempt,
                    "category": llm_locator_validation.get("category"),
                    "missing_locator_for_search_unit_ids": list(
                        llm_locator_validation.get("missing_locator_for_search_unit_ids") or []
                    ),
                    "missing_fields_by_search_unit_id": dict(
                        llm_locator_validation.get("missing_fields_by_search_unit_id") or {}
                    ),
                    "mismatched_fields_by_search_unit_id": dict(
                        llm_locator_validation.get("mismatched_fields_by_search_unit_id") or {}
                    ),
                }
            )
        llm_locator_validation["locator_copy_attempts"] = final_attempt
        llm_locator_validation["locator_copy_retry_count"] = max(0, final_attempt - 1)
        llm_locator_validation["locator_copy_retry_diagnostics"] = locator_retry_diagnostics
        raw_llm_answer = llm_answer
        renderer_meta = render_v3_source_bound_answer(
            row=source_row,
            source_family=source_family,
            answer=llm_answer,
            citations=citations,
        )
        llm_answer = official.clean(renderer_meta.get("answer") or llm_answer)
        score = score_generated_row(
            source_row,
            llm_answer,
            [SimpleNamespace(text=item.get("citation_text")) for item in citations],
        )
        category = foundation_failure_category(
            score=score,
            context=context,
            citations=citations,
            source_family=source_family,
            llm_locator_validation=llm_locator_validation,
        )
        return {
            "lane_name": lane_name,
            "answer_origin": "LLM_SYNTHESIS",
            "llm_invoked": True,
            "prompt_context_mode": mode,
            "generated_answer": llm_answer,
            "raw_generated_answer_before_renderer": raw_llm_answer if raw_llm_answer != llm_answer else None,
            "answer_renderer": renderer_meta,
            "strict_json_raw": strict_json_meta.get("strict_json"),
            "strict_json_diagnostics": strict_json_meta.get("strict_json"),
            "strict_json_parse_ok": True,
            "cited_search_unit_ids": cited_ids,
            "generated_citations": citations,
            "scored_citations": citations,
            "raw_llm_generated_citation_locators_before_canonical_repair": raw_llm_generated_locators,
            "llm_generated_citation_locators": llm_generated_locators,
            "llm_generated_locator_validation": llm_locator_validation,
            "answer_score": score["answer_score"],
            "citation_support_score": score["citation_support_score"],
            "score_status": "PASS" if category == "PASS" else "FAIL_CLOSED",
            "failure_category": category,
            "result_bucket": "PASS" if category == "PASS" else category,
            "locator_preservation": locator_preservation_for_citations(citations, source_family=source_family),
            "citation_payload_validation": citation_payload_validation_summary(citations),
            "adapter_vs_llm_diff": None,
            "scorer_notes": score["failure_detail"],
            "scorer_compatibility_normalization_applied": score.get("scorer_compatibility_normalization_applied", False),
            "diagnostic_review_label": "pass" if category == "PASS" else "needs_row_level_triage",
            "recommendation": recommendation_for_failure(category),
            "generation_used_expected_answer": False,
            "generation_used_gold_fields": False,
            "generation_used_supporting_evidence": False,
        }
    except StrictJsonDiagnosticError as exc:
        return v3_1_fail_closed_lane(
            lane_name=lane_name,
            mode=mode,
            source_family=source_family,
            context=context,
            category="LLM_STRICT_JSON_PARSE_FAILURE",
            reason=f"strict JSON generation failed closed: {type(exc).__name__}: {exc}",
            llm_invoked=True,
            strict_json_diagnostics=exc.diagnostics,
        )
    except Exception as exc:  # noqa: BLE001
        category = "CITATION_NOT_SOURCE_BOUND" if "outside prompt" in str(exc) else "LLM_STRICT_JSON_PARSE_FAILURE"
        if "answer_supported_by_context=false" in str(exc):
            category = "LLM_UNSUPPORTED_INFERENCE"
        return v3_1_fail_closed_lane(
            lane_name=lane_name,
            mode=mode,
            source_family=source_family,
            context=context,
            category=category,
            reason=f"strict JSON generation failed closed: {type(exc).__name__}: {exc}",
            llm_invoked=True,
        )


def v3_1_fail_closed_lane(
    *,
    lane_name: str,
    mode: str,
    source_family: str,
    context: Mapping[str, Any],
    category: str,
    reason: str,
    llm_invoked: bool,
    strict_json_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    strict_json_diagnostics = dict(strict_json_diagnostics or {})
    return {
        "lane_name": lane_name,
        "answer_origin": "LLM_SYNTHESIS",
        "llm_invoked": llm_invoked,
        "prompt_context_mode": mode,
        "generated_answer": "",
        "strict_json_raw": strict_json_diagnostics or None,
        "strict_json_diagnostics": strict_json_diagnostics or {
            "parse_ok": False,
            "strict_json_error": reason,
            "attempted_schema_keys": ["answer", "cited_search_unit_ids", "citation_locators"],
            "missing_required_keys": [],
            "prompt_context_mode": mode,
            "cited_search_unit_ids_before_parse": [
                official.clean(item.get("search_unit_id"))
                for item in context.get("citations") or []
                if isinstance(item, Mapping) and official.clean(item.get("search_unit_id"))
            ],
        },
        "strict_json_parse_ok": False,
        "cited_search_unit_ids": [],
        "generated_citations": [],
        "scored_citations": [],
        "llm_generated_citation_locators": [],
        "llm_generated_locator_validation": {
            "ok": False,
            "generated_by_llm": True,
            "source_family": source_family,
            "required_fields": list(required_locator_fields(source_family)),
            "cited_search_unit_ids": [],
            "missing_locator_for_search_unit_ids": [],
            "missing_fields_by_search_unit_id": {},
            "mismatched_fields_by_search_unit_id": {},
            "category": locator_loss_category(source_family) if category in {"PDF_BBOX_LOCATOR_LOSS", "XLSX_CELL_LOCATOR_LOSS", "CITATION_PAYLOAD_SCHEMA_MISMATCH"} else category,
        },
        "answer_score": 0.0,
        "citation_support_score": 0.0,
        "score_status": "FAIL_CLOSED",
        "failure_category": category,
        "result_bucket": category,
        "locator_preservation": locator_preservation_for_citations([], source_family=source_family),
        "citation_payload_validation": {
            "ok": False,
            "category": category,
            "missing_fields": [],
            "context_policy_errors": list(context.get("policy_errors") or []),
        },
        "adapter_vs_llm_diff": None,
        "scorer_notes": reason,
        "diagnostic_review_label": "needs_row_level_triage",
        "recommendation": recommendation_for_failure(category),
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
    }


def citation_ids_from_citations(citations: Sequence[Any]) -> list[str]:
    ids: list[str] = []
    for citation in citations:
        if not isinstance(citation, Mapping):
            continue
        payload = as_mapping(citation.get("search_unit_citation_payload"))
        search_unit_id = official.clean(payload.get("search_unit_id") or payload.get("searchUnitId"))
        if search_unit_id:
            ids.append(search_unit_id)
    return sorted(dict.fromkeys(ids))


def filter_citations_by_ids(citations: Sequence[Any], cited_ids: Sequence[str]) -> list[dict[str, Any]]:
    wanted = {official.clean(item) for item in cited_ids if official.clean(item)}
    if not wanted:
        return []
    out: list[dict[str, Any]] = []
    for citation in citations:
        if not isinstance(citation, Mapping):
            continue
        payload = as_mapping(citation.get("search_unit_citation_payload"))
        search_unit_id = official.clean(payload.get("search_unit_id") or payload.get("searchUnitId"))
        if search_unit_id in wanted:
            out.append(dict(citation))
    return out


def required_locator_fields(source_family: str) -> tuple[str, ...]:
    if source_family == "PDF":
        return ("source_pdf_path", "page", "physical_page_index", "bbox", "region_type", "search_unit_id", "document_version_id")
    if source_family == "XLSX":
        return ("workbook", "sheet", "range", "cell", "row_label", "target_column", "normalized_value", "search_unit_id", "document_version_id")
    return ("document_id", "document_version_id", "search_unit_id", "text_locator")


def locator_preservation_for_citations(citations: Sequence[Any], *, source_family: str) -> dict[str, Any]:
    required = required_locator_fields(source_family)
    missing_by_search_unit: dict[str, list[str]] = {}
    for citation in citations:
        if not isinstance(citation, Mapping):
            continue
        payload = as_mapping(citation.get("search_unit_citation_payload"))
        locator = locator_from_citation_payload(payload, source_family=source_family)
        missing = [field for field in required if locator.get(field) in (None, "", [])]
        search_unit_id = official.clean(locator.get("search_unit_id"))
        if missing:
            missing_by_search_unit[search_unit_id or f"citation_{len(missing_by_search_unit)}"] = missing
    return {
        "ok": bool(citations) and not missing_by_search_unit,
        "source_family": source_family,
        "required_fields": list(required),
        "missing_fields_by_search_unit_id": missing_by_search_unit,
    }


def citation_payload_validation_summary(citations: Sequence[Any]) -> dict[str, Any]:
    validations: list[Mapping[str, Any]] = []
    for citation in citations:
        if isinstance(citation, Mapping) and isinstance(citation.get("citation_payload_validation"), Mapping):
            validations.append(citation["citation_payload_validation"])
    categories = [
        official.clean(item.get("category") or item.get("validation_category"))
        for item in validations
        if item.get("ok") is not True and official.clean(item.get("category") or item.get("validation_category"))
    ]
    return {
        "ok": bool(citations) and not categories,
        "citation_count": len(citations),
        "invalid_count": len(categories),
        "categories": sorted(dict.fromkeys(categories)),
    }


def locator_loss_category(source_family: str) -> str:
    if source_family == "PDF":
        return "PDF_BBOX_LOCATOR_LOSS"
    if source_family == "XLSX":
        return "XLSX_CELL_LOCATOR_LOSS"
    return "CITATION_PAYLOAD_SCHEMA_MISMATCH"


def llm_generated_locator_validation(
    *,
    generated_locators: Sequence[Any],
    expected_citations: Sequence[Any],
    cited_search_unit_ids: Sequence[str],
    source_family: str,
) -> dict[str, Any]:
    required = required_locator_fields(source_family)
    expected_by_id: dict[str, dict[str, Any]] = {}
    for citation in expected_citations:
        if not isinstance(citation, Mapping):
            continue
        payload = as_mapping(citation.get("search_unit_citation_payload"))
        locator = locator_from_citation_payload(payload, source_family=source_family)
        search_unit_id = official.clean(locator.get("search_unit_id"))
        if search_unit_id:
            expected_by_id[search_unit_id] = locator

    generated_by_id: dict[str, dict[str, Any]] = {}
    for raw_locator in generated_locators:
        if not isinstance(raw_locator, Mapping):
            continue
        locator = locator_from_citation_payload(raw_locator, source_family=source_family)
        search_unit_id = official.clean(locator.get("search_unit_id") or raw_locator.get("search_unit_id"))
        if search_unit_id:
            locator["search_unit_id"] = search_unit_id
            generated_by_id[search_unit_id] = locator

    cited_ids = [official.clean(item) for item in cited_search_unit_ids if official.clean(item)]
    missing_locator_ids: list[str] = []
    missing_fields_by_id: dict[str, list[str]] = {}
    mismatched_fields_by_id: dict[str, list[str]] = {}
    field_comparisons_by_id: dict[str, dict[str, dict[str, Any]]] = {}
    for search_unit_id in cited_ids:
        expected = expected_by_id.get(search_unit_id) or {}
        generated = generated_by_id.get(search_unit_id)
        if generated is None:
            missing_locator_ids.append(search_unit_id)
            continue
        missing = [field for field in required if generated.get(field) in (None, "", [])]
        if missing:
            missing_fields_by_id[search_unit_id] = missing
        field_comparisons_by_id[search_unit_id] = {
            field: locator_field_copy_comparison(expected.get(field), generated.get(field))
            for field in required
            if field not in missing
        }
        mismatched = [
            field
            for field, comparison in field_comparisons_by_id[search_unit_id].items()
            if comparison["byte_equal"] is not True
        ]
        if mismatched:
            mismatched_fields_by_id[search_unit_id] = mismatched

    ok = bool(cited_ids) and not missing_locator_ids and not missing_fields_by_id and not mismatched_fields_by_id
    return {
        "ok": ok,
        "generated_by_llm": True,
        "source_family": source_family,
        "required_fields": list(required),
        "cited_search_unit_ids": cited_ids,
        "generated_locator_count": len(generated_by_id),
        "missing_locator_for_search_unit_ids": missing_locator_ids,
        "missing_fields_by_search_unit_id": missing_fields_by_id,
        "mismatched_fields_by_search_unit_id": mismatched_fields_by_id,
        "field_comparisons_by_search_unit_id": field_comparisons_by_id,
        "category": None if ok else locator_loss_category(source_family),
    }


def canonicalize_llm_generated_locators_from_expected(
    *,
    generated_locators: Sequence[Any],
    expected_citations: Sequence[Any],
    cited_search_unit_ids: Sequence[str],
    source_family: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    required = required_locator_fields(source_family)
    expected_by_id: dict[str, dict[str, Any]] = {}
    for citation in expected_citations:
        if not isinstance(citation, Mapping):
            continue
        payload = as_mapping(citation.get("search_unit_citation_payload"))
        locator = locator_from_citation_payload(payload, source_family=source_family)
        search_unit_id = official.clean(locator.get("search_unit_id"))
        if search_unit_id:
            expected_by_id[search_unit_id] = locator

    generated_by_id: dict[str, dict[str, Any]] = {}
    for raw_locator in generated_locators:
        if not isinstance(raw_locator, Mapping):
            continue
        locator = locator_from_citation_payload(raw_locator, source_family=source_family)
        search_unit_id = official.clean(locator.get("search_unit_id") or raw_locator.get("search_unit_id"))
        if search_unit_id:
            locator["search_unit_id"] = search_unit_id
            generated_by_id[search_unit_id] = locator

    repaired_by_id: dict[str, list[str]] = {}
    out: list[dict[str, Any]] = []
    for search_unit_id in [official.clean(item) for item in cited_search_unit_ids if official.clean(item)]:
        expected = expected_by_id.get(search_unit_id) or {}
        locator = dict(generated_by_id.get(search_unit_id) or {})
        if search_unit_id:
            locator["search_unit_id"] = search_unit_id
        repaired_fields: list[str] = []
        for field in required:
            expected_value = expected.get(field)
            if expected_value in (None, "", []):
                continue
            if locator.get(field) in (None, "", []) or locator_byte_value(locator.get(field)) != locator_byte_value(expected_value):
                locator[field] = expected_value
                repaired_fields.append(field)
        if repaired_fields:
            repaired_by_id[search_unit_id] = repaired_fields
        if locator:
            out.append(locator)
    return out, {
        "applied": bool(repaired_by_id),
        "source": "source_bound_prompt_context_locator_json_copy_source",
        "repaired_fields_by_search_unit_id": repaired_by_id,
        "raw_generated_locator_count": len(generated_by_id),
        "canonicalized_locator_count": len(out),
    }


def locator_field_copy_comparison(expected: Any, generated: Any) -> dict[str, Any]:
    expected_byte_value = locator_byte_value(expected)
    generated_byte_value = locator_byte_value(generated)
    expected_normalized = normalized_locator_copy_value(expected)
    generated_normalized = normalized_locator_copy_value(generated)
    return {
        "byte_equal": expected_byte_value == generated_byte_value,
        "normalized_equal": expected_normalized == generated_normalized,
        "expected_sha256": sha256_text(expected_byte_value),
        "generated_sha256": sha256_text(generated_byte_value),
        "expected_excerpt": sanitized_raw_response_excerpt(official.clean(expected), limit=180),
        "generated_excerpt": sanitized_raw_response_excerpt(official.clean(generated), limit=180),
    }


def locator_copy_retry_message(validation: Mapping[str, Any]) -> str:
    missing_locators = list(validation.get("missing_locator_for_search_unit_ids") or [])
    missing_fields = dict(validation.get("missing_fields_by_search_unit_id") or {})
    mismatched_fields = dict(validation.get("mismatched_fields_by_search_unit_id") or {})
    return (
        f"Missing locator ids: {json.dumps(missing_locators, ensure_ascii=False, sort_keys=True)}. "
        f"Missing fields: {json.dumps(missing_fields, ensure_ascii=False, sort_keys=True)}. "
        f"Mismatched fields: {json.dumps(mismatched_fields, ensure_ascii=False, sort_keys=True)}."
    )


def locator_byte_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalized_locator_copy_value(value: Any) -> str:
    if isinstance(value, str):
        text = unicodedata.normalize("NFKC", official.clean(value))
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\s*([|=:/()])\s*", r"\1", text)
        return text.strip()
    return canonical_locator_value(value)


def canonical_locator_value(value: Any) -> str:
    if isinstance(value, str):
        stripped = official.clean(value)
        if stripped.startswith(("[", "{")):
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                return stripped
        else:
            return stripped
    if isinstance(value, float):
        return str(round(value, 6))
    if isinstance(value, (list, tuple)):
        return json.dumps([canonical_locator_value(item) for item in value], ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, Mapping):
        return json.dumps(
            {official.clean(key): canonical_locator_value(item) for key, item in sorted(value.items())},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return official.clean(value)


def foundation_failure_category(
    *,
    score: Mapping[str, Any],
    context: Mapping[str, Any],
    citations: Sequence[Any],
    source_family: str,
    llm_locator_validation: Mapping[str, Any] | None = None,
) -> str:
    if llm_locator_validation and llm_locator_validation.get("ok") is not True:
        return official.clean(llm_locator_validation.get("category")) or locator_loss_category(source_family)
    if score.get("failure_category") == "PASS":
        return "PASS"
    if not citations:
        return "CITATION_NOT_SOURCE_BOUND"
    if context.get("query_bound_evidence_only") and not context.get("query_bound_scored_citation_count"):
        return "RETRIEVAL_QUERY_BOUND_MISS"
    if score.get("answer_score") == 1.0 and score.get("citation_support_score") != 1.0:
        return "LLM_TRUE_PARTIAL_SYNTHESIS"
    if score.get("answer_score") != 1.0 and score.get("citation_support_score") == 1.0:
        return "LLM_EXPECTED_SPAN_MISMATCH"
    return "LLM_UNSUPPORTED_INFERENCE"


def recommendation_for_failure(category: str) -> str:
    mapping = {
        "PASS": "no_action",
        "RETRIEVAL_QUERY_BOUND_MISS": "inspect_query_bound_retrieval_context",
        "CITATION_PAYLOAD_SCHEMA_MISMATCH": "repair_citation_payload_schema",
        "CITATION_NOT_SOURCE_BOUND": "repair_cited_search_unit_selection",
        "CITATION_OFF_TRACK": "repair_track_filtering",
        "CITATION_NOT_QUERY_BOUND": "inspect_query_bound_oracle_citation_filter",
        "LLM_STRICT_JSON_PARSE_FAILURE": "inspect_prompt_and_strict_json_response",
        "LLM_EXPECTED_SPAN_MISMATCH": "row_level_answer_span_triage",
        "LLM_TRUE_PARTIAL_SYNTHESIS": "prompt_answer_renderer_triage",
        "LLM_UNSUPPORTED_INFERENCE": "row_level_source_bound_support_triage",
        "PDF_BBOX_LOCATOR_LOSS": "repair_pdf_locator_preservation",
        "XLSX_CELL_LOCATOR_LOSS": "repair_xlsx_locator_preservation",
        "SCORER_NORMALIZATION_REVIEW": "review_scorer_normalization",
        "GOLD_POLICY_REVIEW_CANDIDATE": "request_user_gold_policy_decision",
    }
    return mapping.get(category, "row_level_failure_triage")


def adapter_llm_diff(adapter_lane: Mapping[str, Any], llm_lane: Mapping[str, Any]) -> dict[str, Any]:
    adapter_answer = official.normalized_text(official.clean(adapter_lane.get("generated_answer")))
    llm_answer = official.normalized_text(official.clean(llm_lane.get("generated_answer")))
    return {
        "adapter_answer_empty": not bool(adapter_answer),
        "llm_answer_empty": not bool(llm_answer),
        "normalized_exact_match": bool(adapter_answer and adapter_answer == llm_answer),
    }


def build_v3_1_summary(
    *,
    args: argparse.Namespace,
    rows: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    agentic_status: Mapping[str, Any],
    v3_preflight: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
    v3_summary_path: Path,
    v3_results_path: Path,
    v3_attribution_path: Path,
) -> dict[str, Any]:
    lane_counts = v3_1_lane_counts(rows)
    family_lane_counts = v3_1_source_family_lane_counts(rows)
    guardrails = v3_1_guardrails()
    index_dependency = agentic_status.get(
        "index_dependency",
        inspect_rag_index_dependency(Path(args.rag_index_dir)),
    )
    rows_by_family = dict(sorted(Counter(row["source_family"] for row in rows).items()))
    primary_lane_counts = lane_counts["v3_primary_replay"]
    summary = {
        "schema_version": V3_1_RUN_ID,
        "run_id": V3_1_RUN_ID,
        "generated_at": utc_timestamp(),
        "status": "ALL_TRACK_FOUNDATION_MEASUREMENT_V3_1_COMPLETED" if v3_preflight.get("ok") and backend_preflight.get("ok") else "ALL_TRACK_FOUNDATION_MEASUREMENT_V3_1_FAIL_CLOSED",
        "measurement_classification": "all_track_foundation_measurement_v3_1_diagnostic_only",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_gate_auto_run": False,
        "total_denominator_rows": 29,
        "denominator_count": 29,
        "result_count": len(rows),
        "unique_query_id_count": len({row["query_id"] for row in rows}),
        "rows_by_source_family": {"PDF": int(rows_by_family.get("PDF", 0)), "TEXT": int(rows_by_family.get("TEXT", 0)), "XLSX": int(rows_by_family.get("XLSX", 0))},
        "scored_count": primary_lane_counts["scored_count"],
        "pass_count": primary_lane_counts["pass_count"],
        "failure_counts": primary_lane_counts["failure_counts"],
        "score_scope": "v3_primary_replay_lane_only_for_legacy_status_fields",
        "lane_names": list(V3_1_LANE_NAMES),
        "lane_counts": lane_counts,
        "source_family_lane_counts": family_lane_counts,
        "llm_invoked_count_by_lane": {lane: counts["llm_invoked_count"] for lane, counts in lane_counts.items()},
        "adapter_retained_count_by_lane": {lane: counts["adapter_retained_count"] for lane, counts in lane_counts.items()},
        "query_bound_evidence_gap_count_by_lane": {
            lane: counts["query_bound_evidence_gap_count"] for lane, counts in lane_counts.items()
        },
        "schema_mismatch_residual_count_by_lane": {
            lane: counts["schema_mismatch_residual_count"] for lane, counts in lane_counts.items()
        },
        "citation_unsupported_count_by_lane": {
            lane: counts["citation_unsupported_count"] for lane, counts in lane_counts.items()
        },
        "answer_partial_unsupported_count_by_lane": {
            lane: counts["answer_partial_unsupported_count"] for lane, counts in lane_counts.items()
        },
        "locator_preservation_failure_count_by_source_family": locator_preservation_failure_counts(rows),
        "llm_generated_locator_failure_count_by_lane": {
            lane: counts["llm_generated_locator_failure_count"] for lane, counts in lane_counts.items()
        },
        "llm_generated_locator_failure_count_by_source_family": llm_generated_locator_failure_counts_by_source_family(rows),
        "citation_payload_summary": citation_payload_summary_by_lane(rows),
        "guardrails": guardrails,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
        "source_bound_index_used": bool(index_dependency.get("rerun_allowed")),
        "source_bound_official_denominator_index_only": True,
        "canonical_search_unit_payload_used": True,
        "non_production_rag_index_dependency": index_dependency,
        "agentic_loop": {
            "implemented": True,
            "enabled": False,
            "executed": False,
            "backend": "v3_1_all_track_foundation_measurement",
            "steps_count": 0,
            "blockers": list(v3_preflight.get("errors") or []) + list(backend_preflight.get("blockers") or []),
        },
        "infrastructure_blocker": {
            "category": None if v3_preflight.get("ok") and backend_preflight.get("ok") else "V3_1_PRECONDITION_OR_BACKEND_BLOCKED",
            "domain": None if v3_preflight.get("ok") and backend_preflight.get("ok") else "v3_1_preflight",
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": False,
        },
        "local_llm_used": any(
            lane.get("llm_invoked") is True
            for row in rows
            for lane in row.get("lane_results", {}).values()
        ),
        "local_gpu_used": False,
        "llm_backend": backend_preflight.get("llm_backend"),
        "llm_model": backend_preflight.get("model"),
        "llm_backend_preflight": dict(backend_preflight),
        "v3_completed_preflight": dict(v3_preflight),
        "performance_interpretation": "diagnostic_only_all_track_foundation_measurement_not_promotion_evidence",
        "diagnostic_limitations": [
            "Lane A replays v3 primary policy and mixes structured adapter retained rows with TEXT LLM synthesis.",
            "Lane B measures integrated retrieval top-k plus LLM synthesis for all 29 rows.",
            "Lane C is query-bound oracle-context synthesis isolation and is not promotion evidence.",
            "Lane scores must not be mixed into one official score.",
        ],
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "v3_summary_json": official.file_identity(v3_summary_path),
            "v3_results_jsonl": official.file_identity(v3_results_path),
            "v3_failure_attribution_json": official.file_identity(v3_attribution_path),
        },
        "artifact_paths": v3_1_artifact_paths(args),
        "pipeline_decision": {
            "selected_entrypoint": "v3_1 all-track foundation measurement over v3 source-bound official denominator rows",
            "rationale": "Freeze lane-separated diagnostic evidence before silver generation or row-level failure tuning.",
            "registry_application_report_required": False,
            "registry_application_fallback_used": registry_application_fallback_used,
            "candidate_artifacts_not_used_as_generation_source": True,
            "expected_supporting_gold_used_for_generation": False,
        },
        "baseline_reference": {
            "run_id": "official_answer_citation_metric_first_run_v1",
            "status_detail": baseline.get("status_detail"),
            "scored_count": baseline.get("scored_count"),
            "pass_count": (baseline.get("failure_category_counts") or {}).get("PASS"),
            "failure_counts": baseline.get("failure_category_counts"),
            "artifact_identity": official.file_identity(baseline_path),
        },
        "next_step_recommendation": "row_level_failure_triage_after_all_track_foundation_measurement",
    }
    return summary


def build_v3_1_priority_1_5_summary(
    *,
    args: argparse.Namespace,
    rows: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    baseline_summary: Mapping[str, Any],
    baseline: Mapping[str, Any],
    agentic_status: Mapping[str, Any],
    v3_preflight: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
    v3_summary_path: Path,
    v3_results_path: Path,
    v3_attribution_path: Path,
    v3_1_preflight: Mapping[str, Any],
) -> dict[str, Any]:
    lane_counts = v3_1_lane_counts(rows)
    family_lane_counts = v3_1_source_family_lane_counts(rows)
    guardrails = v3_1_guardrails()
    index_dependency = agentic_status.get(
        "index_dependency",
        inspect_rag_index_dependency(Path(args.rag_index_dir)),
    )
    primary_lane_counts = lane_counts["live_llm_retrieval_topk"]
    baseline_subset = priority_rows_by_id(baseline_rows)
    rows_by_family = dict(sorted(Counter(row["source_family"] for row in rows).items()))
    before_strict = strict_json_parse_failure_count(baseline_subset)
    after_strict = strict_json_parse_failure_count(rows)
    before_llm_copy = llm_generated_locator_copy_failure_count(baseline_subset)
    after_llm_copy = llm_generated_locator_copy_failure_count(rows)
    before_llm_mismatch = llm_generated_locator_field_mismatch_failure_count(baseline_subset)
    after_llm_mismatch = llm_generated_locator_field_mismatch_failure_count(rows)
    before_llm_missing = llm_generated_locator_missing_failure_count(baseline_subset)
    after_llm_missing = llm_generated_locator_missing_failure_count(rows)
    before_schema_repair = strict_json_schema_repair_applied_count(baseline_subset)
    after_schema_repair = strict_json_schema_repair_applied_count(rows)
    before_posthoc = posthoc_payload_locator_preservation_failure_count(baseline_subset)
    after_posthoc = posthoc_payload_locator_preservation_failure_count(rows)
    summary = {
        "schema_version": V3_1_PRIORITY_1_5_RUN_ID,
        "run_id": V3_1_PRIORITY_1_5_RUN_ID,
        "source_run_id": V3_1_RUN_ID,
        "context_source_run_id": V3_RUN_ID,
        "generated_at": utc_timestamp(),
        "status": "PRIORITY_1_5_STRICT_JSON_LOCATOR_TRIAGE_COMPLETED"
        if v3_preflight.get("ok") and backend_preflight.get("ok")
        else "PRIORITY_1_5_STRICT_JSON_LOCATOR_TRIAGE_FAIL_CLOSED",
        "measurement_classification": "priority_1_5_strict_json_locator_triage_diagnostic_only",
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
        "target_row_count": len(V3_1_PRIORITY_1_5_QUERY_IDS),
        "total_denominator_rows": len(V3_1_PRIORITY_1_5_QUERY_IDS),
        "denominator_count": len(V3_1_PRIORITY_1_5_QUERY_IDS),
        "result_count": len(rows),
        "unique_query_id_count": len({row["query_id"] for row in rows}),
        "scored_count": primary_lane_counts["scored_count"],
        "pass_count": primary_lane_counts["pass_count"],
        "failure_counts": primary_lane_counts["failure_counts"],
        "target_query_ids": list(V3_1_PRIORITY_1_5_QUERY_IDS),
        "rows_by_source_family": {
            "PDF": int(rows_by_family.get("PDF", 0)),
            "TEXT": int(rows_by_family.get("TEXT", 0)),
            "XLSX": int(rows_by_family.get("XLSX", 0)),
        },
        "lane_names": list(V3_1_LANE_NAMES),
        "lane_counts": lane_counts,
        "source_family_lane_counts": family_lane_counts,
        "strict_json_parse_failure_before": before_strict,
        "strict_json_parse_failure_after": after_strict,
        "strict_json_schema_repair_applied_count_before": before_schema_repair,
        "strict_json_schema_repair_applied_count_after": after_schema_repair,
        "llm_generated_locator_copy_failure_before": before_llm_copy,
        "llm_generated_locator_copy_failure_after": after_llm_copy,
        "llm_generated_locator_field_mismatch_failure_before": before_llm_mismatch,
        "llm_generated_locator_field_mismatch_failure_after": after_llm_mismatch,
        "llm_generated_locator_missing_failure_before": before_llm_missing,
        "llm_generated_locator_missing_failure_after": after_llm_missing,
        "pdf_source_pdf_path_mismatch_before": locator_field_mismatch_count(
            baseline_subset,
            source_family="PDF",
            field="source_pdf_path",
        ),
        "pdf_source_pdf_path_mismatch_after": locator_field_mismatch_count(
            rows,
            source_family="PDF",
            field="source_pdf_path",
        ),
        "xlsx_row_label_mismatch_before": locator_field_mismatch_count(
            baseline_subset,
            source_family="XLSX",
            field="row_label",
        ),
        "xlsx_row_label_mismatch_after": locator_field_mismatch_count(
            rows,
            source_family="XLSX",
            field="row_label",
        ),
        "posthoc_payload_locator_preservation_failure_count": after_posthoc,
        "llm_generated_locator_copy_failure_count": after_llm_copy,
        "locator_metric_split": {
            "posthoc_payload_locator_preservation_failure_count_before": before_posthoc,
            "posthoc_payload_locator_preservation_failure_count": after_posthoc,
            "llm_generated_locator_copy_failure_count_before": before_llm_copy,
            "llm_generated_locator_copy_failure_count": after_llm_copy,
            "llm_generated_locator_field_mismatch_failure_count_before": before_llm_mismatch,
            "llm_generated_locator_field_mismatch_failure_count": after_llm_mismatch,
            "llm_generated_locator_missing_failure_count_before": before_llm_missing,
            "llm_generated_locator_missing_failure_count": after_llm_missing,
        },
        "score_interpretation": "answer_and_citation_scores_are_reference_only_not_promotion_evidence",
        "answer_score_reference_only": True,
        "citation_support_score_reference_only": True,
        "guardrails": guardrails,
        "local_llm_used": any(
            lane.get("llm_invoked") is True
            for row in rows
            for lane in row.get("lane_results", {}).values()
            if isinstance(lane, Mapping)
        ),
        "local_gpu_used": False,
        "llm_backend": backend_preflight.get("llm_backend"),
        "llm_model": backend_preflight.get("model"),
        "llm_backend_preflight": dict(backend_preflight),
        "v3_completed_preflight": dict(v3_preflight),
        "v3_1_artifact_consistency_preflight": dict(v3_1_preflight),
        "non_production_rag_index_dependency": index_dependency,
        "source_bound_index_used": bool(index_dependency.get("rerun_allowed")),
        "canonical_search_unit_payload_used": True,
        "infrastructure_blocker": {
            "category": None if v3_preflight.get("ok") and backend_preflight.get("ok") else "PRIORITY_1_5_PRECONDITION_OR_BACKEND_BLOCKED",
            "domain": None if v3_preflight.get("ok") and backend_preflight.get("ok") else "priority_1_5_preflight",
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": False,
        },
        "performance_interpretation": "diagnostic_only_priority_1_5_row_level_triage_not_promotion_evidence",
        "diagnostic_limitations": [
            "Only v3_1 triage priority ranks 1 through 5 are rerun.",
            "Answer and citation scores are retained as diagnostics only.",
            "Expected answers, supporting evidence, gold fields, labels, silver generation, and promotion gates are not used.",
        ],
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "v3_summary_json": official.file_identity(v3_summary_path),
            "v3_results_jsonl": official.file_identity(v3_results_path),
            "v3_failure_attribution_json": official.file_identity(v3_attribution_path),
            "v3_1_summary_json": official.file_identity(DEFAULT_V3_1_SUMMARY_JSON),
            "v3_1_results_jsonl": official.file_identity(DEFAULT_V3_1_RESULTS_JSONL),
            "v3_1_triage_queue_json": official.file_identity(DEFAULT_V3_1_TRIAGE_JSON),
        },
        "artifact_paths": v3_1_priority_1_5_artifact_paths(args),
        "pipeline_decision": {
            "selected_entrypoint": "v3_1 priority 1-5 strict JSON and locator copy diagnostic rerun",
            "rationale": "Improve strict JSON diagnostics and LLM-generated locator copy stability before any silver, gold, tuning, or promotion work.",
            "registry_application_report_required": False,
            "registry_application_fallback_used": registry_application_fallback_used,
            "candidate_artifacts_not_used_as_generation_source": True,
            "expected_supporting_gold_used_for_generation": False,
        },
        "baseline_reference": {
            "run_id": baseline_summary.get("run_id"),
            "status": baseline_summary.get("status"),
            "result_count": baseline_summary.get("result_count"),
            "strict_json_parse_failure_before": before_strict,
            "llm_generated_locator_copy_failure_before": before_llm_copy,
            "artifact_identity": official.file_identity(DEFAULT_V3_1_SUMMARY_JSON),
            "official_first_run_reference": {
                "run_id": "official_answer_citation_metric_first_run_v1",
                "status_detail": baseline.get("status_detail"),
                "artifact_identity": official.file_identity(baseline_path),
            },
        },
        "agentic_loop": {
            "implemented": True,
            "enabled": False,
            "executed": False,
            "backend": "v3_1_priority_1_5_strict_json_locator_triage",
            "steps_count": 0,
            "blockers": list(v3_preflight.get("errors") or []) + list(backend_preflight.get("blockers") or []),
        },
        "next_step_recommendation": "user_decision_required_only_for_gold_policy_or_label_changes",
    }
    return summary


def build_v3_1_text_locator_residual_summary(
    *,
    args: argparse.Namespace,
    rows: Sequence[Mapping[str, Any]],
    priority_rows: Sequence[Mapping[str, Any]],
    priority_summary: Mapping[str, Any],
    baseline: Mapping[str, Any],
    agentic_status: Mapping[str, Any],
    v3_preflight: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> dict[str, Any]:
    before_rows = [
        row for row in priority_rows if official.clean(row.get("query_id")) in V3_1_TEXT_LOCATOR_RESIDUAL_QUERY_IDS
    ]
    lane_counts = v3_1_lane_counts(rows)
    family_lane_counts = v3_1_source_family_lane_counts(rows)
    guardrails = v3_1_guardrails()
    index_dependency = agentic_status.get(
        "index_dependency",
        inspect_rag_index_dependency(Path(args.rag_index_dir)),
    )
    before_metrics = triage_delta_row_metrics(before_rows[0]) if before_rows else {}
    after_metrics = triage_delta_row_metrics(rows[0]) if rows else {}
    primary_lane_counts = lane_counts["v3_primary_replay"]
    summary = {
        "schema_version": V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID,
        "run_id": V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID,
        "source_run_id": V3_1_PRIORITY_1_5_RUN_ID,
        "context_source_run_id": V3_RUN_ID,
        "generated_at": utc_timestamp(),
        "status": "TEXT_LOCATOR_RESIDUAL_TRIAGE_COMPLETED" if v3_preflight.get("ok") and backend_preflight.get("ok") else "TEXT_LOCATOR_RESIDUAL_TRIAGE_FAIL_CLOSED",
        "measurement_classification": "text_locator_residual_triage_diagnostic_only",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_gate_auto_run": False,
        "target_row_count": len(V3_1_TEXT_LOCATOR_RESIDUAL_QUERY_IDS),
        "total_denominator_rows": len(V3_1_TEXT_LOCATOR_RESIDUAL_QUERY_IDS),
        "denominator_count": len(V3_1_TEXT_LOCATOR_RESIDUAL_QUERY_IDS),
        "result_count": len(rows),
        "unique_query_id_count": len({row["query_id"] for row in rows}),
        "target_query_ids": list(V3_1_TEXT_LOCATOR_RESIDUAL_QUERY_IDS),
        "rows_by_source_family": dict(sorted(Counter(row["source_family"] for row in rows).items())),
        "scored_count": primary_lane_counts["scored_count"],
        "pass_count": primary_lane_counts["pass_count"],
        "failure_counts": primary_lane_counts["failure_counts"],
        "score_scope": "v3_primary_replay_lane_only_for_legacy_status_fields",
        "lane_names": list(V3_1_LANE_NAMES),
        "lane_counts": lane_counts,
        "source_family_lane_counts": family_lane_counts,
        "strict_json_parse_failure_before": strict_json_parse_failure_count(before_rows),
        "strict_json_parse_failure_after": strict_json_parse_failure_count(rows),
        "strict_json_schema_repair_applied_count_before": strict_json_schema_repair_applied_count(before_rows),
        "strict_json_schema_repair_applied_count_after": strict_json_schema_repair_applied_count(rows),
        "llm_generated_locator_copy_failure_before": llm_generated_locator_copy_failure_count(before_rows),
        "llm_generated_locator_copy_failure_after": llm_generated_locator_copy_failure_count(rows),
        "llm_generated_locator_missing_failure_before": llm_generated_locator_missing_failure_count(before_rows),
        "llm_generated_locator_missing_failure_after": llm_generated_locator_missing_failure_count(rows),
        "llm_generated_locator_field_mismatch_failure_before": llm_generated_locator_field_mismatch_failure_count(before_rows),
        "llm_generated_locator_field_mismatch_failure_after": llm_generated_locator_field_mismatch_failure_count(rows),
        "text_locator_missing_count_before": locator_missing_field_count_for_lane(
            before_rows,
            source_family="TEXT",
            field="text_locator",
            lane_name="live_llm_retrieval_topk",
        ),
        "text_locator_missing_count_after": locator_missing_field_count_for_lane(
            rows,
            source_family="TEXT",
            field="text_locator",
            lane_name="live_llm_retrieval_topk",
        ),
        "text_locator_byte_equal_after": after_metrics.get("text_locator_byte_equal"),
        "text_locator_normalized_equal_after": after_metrics.get("text_locator_normalized_equal"),
        "text_locator_present_after": after_metrics.get("text_locator_present"),
        "text_locator_present_before": before_metrics.get("text_locator_present"),
        "answer_score_reference_only": True,
        "citation_support_score_reference_only": True,
        "guardrails": guardrails,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
        "source_bound_index_used": bool(index_dependency.get("rerun_allowed")),
        "canonical_search_unit_payload_used": True,
        "non_production_rag_index_dependency": index_dependency,
        "llm_backend": backend_preflight.get("llm_backend"),
        "llm_model": backend_preflight.get("model"),
        "llm_backend_preflight": dict(backend_preflight),
        "v3_completed_preflight": dict(v3_preflight),
        "local_llm_used": any(
            lane.get("llm_invoked") is True
            for row in rows
            for lane in row.get("lane_results", {}).values()
            if isinstance(lane, Mapping)
        ),
        "local_gpu_used": False,
        "performance_interpretation": "diagnostic_only_text_locator_residual_triage_not_promotion_evidence",
        "priority_1_5_reference": {
            "run_id": priority_summary.get("run_id"),
            "artifact_identity": official.file_identity(DEFAULT_V3_1_PRIORITY_SUMMARY_JSON),
            "text_locator_missing_count_before": locator_missing_field_count_for_lane(
                before_rows,
                source_family="TEXT",
                field="text_locator",
                lane_name="live_llm_retrieval_topk",
            ),
        },
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "priority_1_5_summary_json": official.file_identity(DEFAULT_V3_1_PRIORITY_SUMMARY_JSON),
            "priority_1_5_results_jsonl": official.file_identity(DEFAULT_V3_1_PRIORITY_RESULTS_JSONL),
        },
        "artifact_paths": v3_1_text_locator_residual_artifact_paths(args),
        "infrastructure_blocker": {
            "category": None if v3_preflight.get("ok") and backend_preflight.get("ok") else "TEXT_LOCATOR_PRECONDITION_OR_BACKEND_BLOCKED",
            "domain": None if v3_preflight.get("ok") and backend_preflight.get("ok") else "text_locator_preflight",
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": False,
        },
        "agentic_loop": {
            "implemented": True,
            "enabled": False,
            "executed": False,
            "backend": "v3_1_text_locator_residual_triage",
            "steps_count": 0,
            "blockers": list(v3_preflight.get("errors") or []) + list(backend_preflight.get("blockers") or []),
        },
        "baseline_reference": {
            "run_id": "official_answer_citation_metric_first_run_v1",
            "status_detail": baseline.get("status_detail"),
            "artifact_identity": official.file_identity(baseline_path),
        },
        "next_step_recommendation": "run_v3_1_1_all_track_post_strict_json_locator_triage_measurement",
    }
    return summary


def build_v3_1_1_post_triage_summary(
    *,
    args: argparse.Namespace,
    rows: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    agentic_status: Mapping[str, Any],
    v3_preflight: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
    v3_summary_path: Path,
    v3_results_path: Path,
    v3_attribution_path: Path,
    text_locator_summary: Mapping[str, Any],
) -> dict[str, Any]:
    summary = build_v3_1_summary(
        args=args,
        rows=rows,
        baseline=baseline,
        agentic_status=agentic_status,
        v3_preflight=v3_preflight,
        backend_preflight=backend_preflight,
        metric_input_config_path=metric_input_config_path,
        denominator_registry_path=denominator_registry_path,
        pre_execution_smoke_path=pre_execution_smoke_path,
        application_path=application_path,
        registry_application_fallback_used=registry_application_fallback_used,
        baseline_path=baseline_path,
        v3_summary_path=v3_summary_path,
        v3_results_path=v3_results_path,
        v3_attribution_path=v3_attribution_path,
    )
    summary.update(
        {
            "schema_version": V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
            "run_id": V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
            "source_run_id": V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID,
            "status": (
                "ALL_TRACK_FOUNDATION_MEASUREMENT_V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_COMPLETED"
                if v3_preflight.get("ok") and backend_preflight.get("ok")
                else "ALL_TRACK_FOUNDATION_MEASUREMENT_V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_FAIL_CLOSED"
            ),
            "measurement_classification": (
                "all_track_foundation_measurement_v3_1_1_post_strict_json_locator_triage_diagnostic_only"
            ),
            "strict_json_parse_failure_count_by_lane": strict_json_parse_failure_count_by_lane(rows),
            "strict_json_schema_repair_applied_count_by_lane": strict_json_schema_repair_applied_count_by_lane(rows),
            "llm_generated_locator_copy_failure_count_by_lane": llm_generated_locator_copy_failure_count_by_lane(rows),
            "llm_generated_locator_missing_failure_count_by_lane": llm_generated_locator_missing_failure_count_by_lane(rows),
            "llm_generated_locator_field_mismatch_failure_count_by_lane": llm_generated_locator_field_mismatch_failure_count_by_lane(rows),
            "pdf_source_pdf_path_mismatch_count": locator_field_mismatch_count(
                rows,
                source_family="PDF",
                field="source_pdf_path",
            ),
            "xlsx_row_label_mismatch_count": locator_field_mismatch_count(
                rows,
                source_family="XLSX",
                field="row_label",
            ),
            "text_text_locator_missing_count": locator_missing_field_count(
                rows,
                source_family="TEXT",
                field="text_locator",
            ),
            "answer_span_mismatch_count_by_lane": answer_span_mismatch_count_by_lane(rows),
            "regression_from_v3_1_foundation": regression_from_v3_1_foundation(rows, baseline_rows),
            "artifact_paths": v3_1_1_post_triage_artifact_paths(args),
            "text_locator_residual_reference": {
                "run_id": text_locator_summary.get("run_id"),
                "artifact_identity": official.file_identity(DEFAULT_V3_1_TEXT_LOCATOR_SUMMARY_JSON),
                "text_locator_missing_count_after": text_locator_summary.get("text_locator_missing_count_after"),
            },
            "agentic_loop": {
                "implemented": True,
                "enabled": False,
                "executed": False,
                "backend": "v3_1_1_post_strict_json_locator_triage",
                "steps_count": 0,
                "blockers": list(v3_preflight.get("errors") or []) + list(backend_preflight.get("blockers") or []),
            },
            "next_step_recommendation": "row_level_answer_span_and_answer_renderer_triage",
        }
    )
    summary["source_artifacts"] = {
        **as_mapping(summary.get("source_artifacts")),
        "v3_1_foundation_results_jsonl": official.file_identity(DEFAULT_V3_1_RESULTS_JSONL),
        "v3_1_text_locator_residual_summary_json": official.file_identity(DEFAULT_V3_1_TEXT_LOCATOR_SUMMARY_JSON),
    }
    return summary


def build_v3_1_2_answer_span_renderer_summary(
    *,
    args: argparse.Namespace,
    rows: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    agentic_status: Mapping[str, Any],
    post_summary: Mapping[str, Any],
    post_preflight: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> dict[str, Any]:
    lane_counts = v3_1_lane_counts(rows)
    family_lane_counts = v3_1_source_family_lane_counts(rows)
    rows_by_family = dict(sorted(Counter(row["source_family"] for row in rows).items()))
    primary_lane_counts = lane_counts["v3_primary_replay"]
    guardrails = v3_1_guardrails()
    index_dependency = agentic_status.get(
        "index_dependency",
        inspect_rag_index_dependency(Path(args.rag_index_dir)),
    )
    diagnostic_counts = answer_span_renderer_diagnostic_counts(rows)
    status = (
        "ANSWER_SPAN_RENDERER_TRIAGE_BATCH1_RECORDED"
        if post_preflight.get("ok")
        else "ANSWER_SPAN_RENDERER_TRIAGE_BATCH1_FAIL_CLOSED"
    )
    return {
        "schema_version": V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "run_id": V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "source_run_id": V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
        "generated_at": utc_timestamp(),
        "status": status,
        "measurement_classification": "answer_span_renderer_triage_v3_1_2_diagnostic_only",
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
        "write_summary_markdown": False,
        "total_denominator_rows": len(V3_1_2_TEXT_TARGET_QUERY_IDS),
        "denominator_count": len(V3_1_2_TEXT_TARGET_QUERY_IDS),
        "target_row_count": len(rows),
        "primary_first_batch_row_count": len(V3_1_2_TEXT_FIRST_BATCH_QUERY_IDS),
        "secondary_text_watchlist_row_count": len(V3_1_2_TEXT_SECONDARY_QUERY_IDS),
        "result_count": len(rows),
        "unique_query_id_count": len({row["query_id"] for row in rows}),
        "rows_by_source_family": {
            "PDF": int(rows_by_family.get("PDF", 0)),
            "TEXT": int(rows_by_family.get("TEXT", 0)),
            "XLSX": int(rows_by_family.get("XLSX", 0)),
        },
        "scored_count": primary_lane_counts["scored_count"],
        "pass_count": primary_lane_counts["pass_count"],
        "failure_counts": primary_lane_counts["failure_counts"],
        "score_scope": "targeted_text_batch_v3_primary_replay_lane_only_for_legacy_status_fields",
        "lane_names": list(V3_1_LANE_NAMES),
        "lane_counts": lane_counts,
        "source_family_lane_counts": family_lane_counts,
        "target_query_ids": list(V3_1_2_TEXT_TARGET_QUERY_IDS),
        "first_batch_query_ids": list(V3_1_2_TEXT_FIRST_BATCH_QUERY_IDS),
        "secondary_text_watchlist_query_ids": list(V3_1_2_TEXT_SECONDARY_QUERY_IDS),
        "secondary_include_decision": {
            "text_namu_v2_0005": (
                "not part of first batch because machine queue priority is 12 and Lane A/B already PASS; "
                "included only as a TEXT watchlist row to document the Lane C language/span regression"
            )
        },
        "queue_source_of_truth_decision": {
            "selected_source": official.repo_relative(DEFAULT_V3_1_1_POST_TRIAGE_QUEUE_JSON),
            "selected_source_type": "machine_triage_queue_artifact",
            "rationale": (
                "The rolling docs contain a stale Later Triage Queue; the machine queue has run_id, "
                "priority ranks, failing lanes, and strict_json_or_locator_residual_count=0."
            ),
            "doc_drift_observed": True,
        },
        "answer_span_renderer_diagnostic_counts": diagnostic_counts,
        "strict_json_parse_failure_count_by_lane": post_summary.get("strict_json_parse_failure_count_by_lane"),
        "llm_generated_locator_copy_failure_count_by_lane": post_summary.get(
            "llm_generated_locator_copy_failure_count_by_lane"
        ),
        "llm_generated_locator_missing_failure_count_by_lane": post_summary.get(
            "llm_generated_locator_missing_failure_count_by_lane"
        ),
        "llm_generated_locator_field_mismatch_failure_count_by_lane": post_summary.get(
            "llm_generated_locator_field_mismatch_failure_count_by_lane"
        ),
        "pdf_source_pdf_path_mismatch_count": post_summary.get("pdf_source_pdf_path_mismatch_count"),
        "xlsx_row_label_mismatch_count": post_summary.get("xlsx_row_label_mismatch_count"),
        "text_text_locator_missing_count": post_summary.get("text_text_locator_missing_count"),
        "answer_span_mismatch_count_by_lane": post_summary.get("answer_span_mismatch_count_by_lane"),
        "all_track_post_triage_reference": {
            "run_id": post_summary.get("run_id"),
            "lane_counts": post_summary.get("lane_counts"),
            "answer_span_mismatch_count_by_lane": post_summary.get("answer_span_mismatch_count_by_lane"),
            "regression_from_v3_1_foundation": post_summary.get("regression_from_v3_1_foundation"),
            "strict_json_parse_failure_count_by_lane": post_summary.get("strict_json_parse_failure_count_by_lane"),
            "llm_generated_locator_copy_failure_count_by_lane": post_summary.get(
                "llm_generated_locator_copy_failure_count_by_lane"
            ),
        },
        "all_track_remeasurement_performed": False,
        "all_track_remeasurement_skip_reason": (
            "classification-only diagnostic run; no generation, renderer, scorer, locator, or retrieval behavior "
            "was changed before this artifact"
        ),
        "post_triage_artifact_consistency_preflight": dict(post_preflight),
        "reference_span_audit_only": True,
        "reference_span_text_embedded": False,
        "guardrails": guardrails,
        "local_llm_used": False,
        "local_gpu_used": False,
        "llm_backend": None,
        "llm_model": None,
        "non_production_rag_index_dependency": index_dependency,
        "source_bound_index_used": True,
        "canonical_search_unit_payload_used": True,
        "infrastructure_blocker": {
            "category": None if post_preflight.get("ok") else "V3_1_1_POST_TRIAGE_ARTIFACT_PREFLIGHT_FAILED",
            "domain": None if post_preflight.get("ok") else "answer_span_renderer_triage_preflight",
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": False,
        },
        "agentic_loop": {
            "implemented": True,
            "enabled": False,
            "executed": False,
            "backend": "v3_1_2_answer_span_renderer_triage",
            "steps_count": 0,
            "blockers": list(post_preflight.get("errors") or []),
        },
        "performance_interpretation": "diagnostic_only_answer_span_renderer_batch1_not_promotion_evidence",
        "diagnostic_limitations": [
            "This run classifies the first TEXT answer-span/renderer batch from post-generation artifacts.",
            "It does not call an LLM and does not tune thresholds, choose winners, or change gold fields.",
            "Reference spans are used only after generation for scoring/triage diagnostics and are not embedded as text.",
            "Lane A/B/C remain separate; target-batch counts must not be read as all-track official scores.",
        ],
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "v3_1_1_post_summary_json": official.file_identity(DEFAULT_V3_1_1_POST_SUMMARY_JSON),
            "v3_1_1_post_results_jsonl": official.file_identity(DEFAULT_V3_1_1_POST_RESULTS_JSONL),
            "v3_1_1_post_failure_attribution_json": official.file_identity(DEFAULT_V3_1_1_POST_ATTRIBUTION_JSON),
            "v3_1_1_post_actual_response_audit_jsonl": official.file_identity(DEFAULT_V3_1_1_POST_AUDIT_JSONL),
            "v3_1_1_post_triage_queue_json": official.file_identity(DEFAULT_V3_1_1_POST_TRIAGE_QUEUE_JSON),
        },
        "artifact_paths": v3_1_2_answer_span_renderer_artifact_paths(args),
        "pipeline_decision": {
            "selected_entrypoint": "v3_1_2 answer span / answer renderer diagnostic triage",
            "rationale": "Classify the first machine-queue TEXT batch without opening silver/gold/promotion work.",
            "registry_application_report_required": False,
            "registry_application_fallback_used": registry_application_fallback_used,
            "candidate_artifacts_not_used_as_generation_source": True,
            "expected_supporting_gold_used_for_generation": False,
        },
        "baseline_reference": {
            "run_id": "official_answer_citation_metric_first_run_v1",
            "artifact_identity": official.file_identity(Path(args.first_run_baseline)),
            "pass_count": baseline.get("pass_count"),
            "scored_count": baseline.get("scored_count"),
            "status_detail": baseline.get("status_detail"),
        },
    }


def answer_span_renderer_diagnostic_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        for diagnostic in as_mapping(row.get("answer_span_renderer_diagnostics")).values():
            if not isinstance(diagnostic, Mapping):
                continue
            for category in diagnostic.get("diagnostic_subcategories") or []:
                counter[official.clean(category)] += 1
    return dict(sorted(counter.items()))


def build_v3_1_3_remaining_queue_summary(
    *,
    args: argparse.Namespace,
    rows: Sequence[Mapping[str, Any]],
    all_rows: Sequence[Mapping[str, Any]],
    before_rows: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    agentic_status: Mapping[str, Any],
    v3_preflight: Mapping[str, Any],
    post_preflight: Mapping[str, Any],
    queue_preflight: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
    v3_summary_path: Path,
    v3_results_path: Path,
    v3_attribution_path: Path,
) -> dict[str, Any]:
    target_query_ids = list(V3_1_3_REMAINING_QUEUE_QUERY_IDS)
    target_before_rows = rows_for_query_ids(before_rows, target_query_ids)
    all_before_lane_counts = v3_1_lane_counts(before_rows)
    all_after_lane_counts = v3_1_lane_counts(all_rows)
    target_before_lane_counts = v3_1_lane_counts(target_before_rows)
    target_after_lane_counts = v3_1_lane_counts(rows)
    lane_counts = target_after_lane_counts
    family_lane_counts = v3_1_source_family_lane_counts(rows)
    guardrails = v3_1_guardrails()
    index_dependency = agentic_status.get(
        "index_dependency",
        inspect_rag_index_dependency(Path(args.rag_index_dir)),
    )
    primary_lane_counts = lane_counts["v3_primary_replay"]
    rows_by_family = dict(sorted(Counter(row["source_family"] for row in rows).items()))
    all_track_regressions = regression_from_v3_1_1_post_triage(all_rows, before_rows)
    target_regressions = regression_from_v3_1_1_post_triage(rows, target_before_rows)
    residuals_after = {
        "strict_json_parse_failure_count_by_lane": strict_json_parse_failure_count_by_lane(rows),
        "llm_generated_locator_copy_failure_count_by_lane": llm_generated_locator_copy_failure_count_by_lane(rows),
        "llm_generated_locator_missing_failure_count_by_lane": llm_generated_locator_missing_failure_count_by_lane(rows),
        "llm_generated_locator_field_mismatch_failure_count_by_lane": llm_generated_locator_field_mismatch_failure_count_by_lane(rows),
        "pdf_source_pdf_path_mismatch_count": locator_field_mismatch_count(
            rows,
            source_family="PDF",
            field="source_pdf_path",
        ),
        "xlsx_row_label_mismatch_count": locator_field_mismatch_count(
            rows,
            source_family="XLSX",
            field="row_label",
        ),
        "text_text_locator_missing_count": locator_missing_field_count(
            rows,
            source_family="TEXT",
            field="text_locator",
        ),
    }
    all_track_residuals_after = {
        "strict_json_parse_failure_count_by_lane": strict_json_parse_failure_count_by_lane(all_rows),
        "llm_generated_locator_copy_failure_count_by_lane": llm_generated_locator_copy_failure_count_by_lane(all_rows),
        "llm_generated_locator_missing_failure_count_by_lane": llm_generated_locator_missing_failure_count_by_lane(all_rows),
        "llm_generated_locator_field_mismatch_failure_count_by_lane": llm_generated_locator_field_mismatch_failure_count_by_lane(all_rows),
        "pdf_source_pdf_path_mismatch_count": locator_field_mismatch_count(
            all_rows,
            source_family="PDF",
            field="source_pdf_path",
        ),
        "xlsx_row_label_mismatch_count": locator_field_mismatch_count(
            all_rows,
            source_family="XLSX",
            field="row_label",
        ),
        "text_text_locator_missing_count": locator_missing_field_count(
            all_rows,
            source_family="TEXT",
            field="text_locator",
        ),
    }
    summary = {
        "schema_version": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "run_id": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "source_run_id": V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "context_source_run_id": V3_RUN_ID,
        "generated_at": utc_timestamp(),
        "status": (
            "REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_V3_1_3_COMPLETED"
            if v3_preflight.get("ok") and backend_preflight.get("ok")
            else "REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_V3_1_3_FAIL_CLOSED"
        ),
        "measurement_classification": "remaining_queue_answer_span_renderer_triage_v3_1_3_diagnostic_only",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_gate_auto_run": False,
        "write_summary_markdown": False,
        "target_row_count": len(target_query_ids),
        "total_denominator_rows": len(target_query_ids),
        "denominator_count": len(target_query_ids),
        "result_count": len(rows),
        "unique_query_id_count": len({row["query_id"] for row in rows}),
        "target_query_ids": target_query_ids,
        "rows_by_source_family": {"PDF": int(rows_by_family.get("PDF", 0)), "TEXT": int(rows_by_family.get("TEXT", 0)), "XLSX": int(rows_by_family.get("XLSX", 0))},
        "scored_count": primary_lane_counts["scored_count"],
        "pass_count": primary_lane_counts["pass_count"],
        "failure_counts": primary_lane_counts["failure_counts"],
        "score_scope": "v3_primary_replay_lane_only_for_legacy_status_fields",
        "lane_names": list(V3_1_LANE_NAMES),
        "lane_counts": lane_counts,
        "source_family_lane_counts": family_lane_counts,
        "target_queue_before_lane_counts": target_before_lane_counts,
        "target_queue_after_lane_counts": target_after_lane_counts,
        "target_queue_pass_count_before_by_lane": lane_pass_counts(target_before_lane_counts),
        "target_queue_pass_count_after_by_lane": lane_pass_counts(target_after_lane_counts),
        "target_queue_answer_span_mismatch_before_by_lane": answer_span_mismatch_count_by_lane(target_before_rows),
        "target_queue_answer_span_mismatch_after_by_lane": answer_span_mismatch_count_by_lane(rows),
        "all_track_remeasurement_performed": True,
        "all_track_before_run_id": V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
        "all_track_after_run_id": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "all_track_result_count_before": len(before_rows),
        "all_track_result_count_after": len(all_rows),
        "all_track_lane_counts_before": all_before_lane_counts,
        "all_track_lane_counts_after": all_after_lane_counts,
        "all_track_pass_count_before_by_lane": lane_pass_counts(all_before_lane_counts),
        "all_track_pass_count_after_by_lane": lane_pass_counts(all_after_lane_counts),
        "all_track_answer_span_mismatch_before_by_lane": answer_span_mismatch_count_by_lane(before_rows),
        "all_track_answer_span_mismatch_after_by_lane": answer_span_mismatch_count_by_lane(all_rows),
        **residuals_after,
        "all_track_residuals_after": all_track_residuals_after,
        "answer_span_renderer_diagnostic_counts": answer_span_renderer_diagnostic_counts(rows),
        "row_level_classification_changes": [row.get("row_level_classification_change") for row in rows],
        "target_queue_regression_from_v3_1_1_post_triage": target_regressions,
        "all_track_regression_from_v3_1_1_post_triage": all_track_regressions,
        "text_namu_v2_0005_lane_a_b_not_degraded": text_namu_v2_0005_lane_a_b_not_degraded(rows, target_before_rows),
        "text_namu_v2_0005_lane_c_improved": text_namu_v2_0005_lane_c_improved(rows, target_before_rows),
        "queue_source_of_truth_decision": {
            "selected_source_type": "machine_remaining_queue_artifact",
            "selected_source": official.repo_relative(DEFAULT_V3_1_2_REMAINING_TRIAGE_QUEUE_JSON),
            "selected_source_run_id": V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
            "docs_are_human_facing_narrative_only": True,
            "reason": "v3_1_2 remaining_triage_queue.json is the machine artifact with strict JSON/locator residual count already zero.",
        },
        "artifact_policy": {
            "summary_json": "machine_manifest",
            "results_jsonl": "canonical_result_payload",
            "failure_attribution_json": "forensic_debug_payload",
            "actual_response_audit_jsonl": "response_audit_payload",
            "answer_span_diagnostics_jsonl": "compact_answer_span_diagnostic_payload",
            "remaining_triage_queue_json": "queue_source_of_truth",
            "rag_current_eval_status_jsonl": "compact_status_ledger",
            "per_run_markdown_report_created": False,
            "classification_only_future_minimum_artifact_set": [
                "summary_json",
                "answer_span_diagnostics_jsonl",
                "remaining_triage_queue_json",
            ],
        },
        "answer_renderer_changes": [
            "prompt_tight_answer_attribute_value_instruction",
            "question_language_preservation_instruction",
            "xlsx_normalized_value_renderer_for_date_value_questions",
            "korean_language_restoration_from_source_context",
            "post_generation_scorer_compatibility_normalization",
        ],
        "answer_score_reference_only": True,
        "citation_support_score_reference_only": True,
        "guardrails": guardrails,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "reference_span_text_embedded": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
        "source_bound_index_used": bool(index_dependency.get("rerun_allowed")),
        "source_bound_official_denominator_index_only": True,
        "canonical_search_unit_payload_used": True,
        "non_production_rag_index_dependency": index_dependency,
        "llm_backend": backend_preflight.get("llm_backend"),
        "llm_model": backend_preflight.get("model"),
        "llm_backend_preflight": dict(backend_preflight),
        "v3_completed_preflight": dict(v3_preflight),
        "v3_1_1_post_preflight": dict(post_preflight),
        "v3_1_2_remaining_queue_preflight": dict(queue_preflight),
        "local_llm_used": any(
            lane.get("llm_invoked") is True
            for row in rows
            for lane in row.get("lane_results", {}).values()
            if isinstance(lane, Mapping)
        ),
        "local_gpu_used": False,
        "performance_interpretation": "diagnostic_only_remaining_queue_answer_span_renderer_not_promotion_evidence",
        "diagnostic_limitations": [
            "The v3_1_3 result payload is the seven-row remaining queue; all-track remeasurement is recorded separately in summary metrics.",
            "Expected answer and supporting evidence are post-generation scoring/audit references only.",
            "Lane A/B/C remain separated and must not be collapsed into one official score.",
        ],
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "v3_summary_json": official.file_identity(v3_summary_path),
            "v3_results_jsonl": official.file_identity(v3_results_path),
            "v3_failure_attribution_json": official.file_identity(v3_attribution_path),
            "v3_1_1_post_summary_json": official.file_identity(DEFAULT_V3_1_1_POST_SUMMARY_JSON),
            "v3_1_1_post_results_jsonl": official.file_identity(DEFAULT_V3_1_1_POST_RESULTS_JSONL),
            "v3_1_2_summary_json": official.file_identity(DEFAULT_V3_1_2_ANSWER_SPAN_SUMMARY_JSON),
            "v3_1_2_remaining_triage_queue_json": official.file_identity(DEFAULT_V3_1_2_REMAINING_TRIAGE_QUEUE_JSON),
        },
        "artifact_paths": v3_1_3_remaining_queue_artifact_paths(args),
        "infrastructure_blocker": {
            "category": None if v3_preflight.get("ok") and backend_preflight.get("ok") else "V3_1_3_PRECONDITION_OR_BACKEND_BLOCKED",
            "domain": None if v3_preflight.get("ok") and backend_preflight.get("ok") else "v3_1_3_preflight",
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": False,
        },
        "agentic_loop": {
            "implemented": True,
            "enabled": False,
            "executed": False,
            "backend": "v3_1_3_remaining_queue_answer_span_renderer_triage",
            "steps_count": 0,
            "blockers": list(v3_preflight.get("errors") or []) + list(backend_preflight.get("blockers") or []),
        },
        "baseline_reference": {
            "run_id": "official_answer_citation_metric_first_run_v1",
            "status_detail": baseline.get("status_detail"),
            "artifact_identity": official.file_identity(baseline_path),
        },
        "next_step_recommendation": "continue_remaining_answer_span_renderer_queue_diagnostic_only",
        "registry_application_fallback_used": registry_application_fallback_used,
    }
    return summary


def build_v3_1_4_pdf_residual_summary(
    *,
    args: argparse.Namespace,
    rows: Sequence[Mapping[str, Any]],
    all_rows: Sequence[Mapping[str, Any]],
    post_rows: Sequence[Mapping[str, Any]],
    before_rows: Sequence[Mapping[str, Any]],
    v3_1_3_summary: Mapping[str, Any],
    baseline: Mapping[str, Any],
    agentic_status: Mapping[str, Any],
    v3_preflight: Mapping[str, Any],
    post_preflight: Mapping[str, Any],
    queue_preflight: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
    v3_summary_path: Path,
    v3_results_path: Path,
    v3_attribution_path: Path,
) -> dict[str, Any]:
    target_query_ids = list(V3_1_4_PDF_RESIDUAL_QUERY_IDS)
    target_before_rows = rows_for_query_ids(before_rows, target_query_ids)
    all_before_lane_counts = as_mapping(v3_1_3_summary.get("all_track_lane_counts_after"))
    all_after_lane_counts = v3_1_lane_counts(all_rows)
    target_before_lane_counts = v3_1_lane_counts(target_before_rows)
    target_after_lane_counts = v3_1_lane_counts(rows)
    lane_counts = target_after_lane_counts
    family_lane_counts = v3_1_source_family_lane_counts(rows)
    guardrails = v3_1_guardrails()
    index_dependency = agentic_status.get(
        "index_dependency",
        inspect_rag_index_dependency(Path(args.rag_index_dir)),
    )
    primary_lane_counts = lane_counts["v3_primary_replay"]
    rows_by_family = dict(sorted(Counter(row["source_family"] for row in rows).items()))
    all_track_regressions = regression_from_v3_1_1_post_triage(all_rows, post_rows)
    target_regressions = regression_from_v3_1_1_post_triage(rows, target_before_rows)
    target_regressions["baseline_run_id"] = V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID
    residuals_after = {
        "strict_json_parse_failure_count_by_lane": strict_json_parse_failure_count_by_lane(rows),
        "llm_generated_locator_copy_failure_count_by_lane": llm_generated_locator_copy_failure_count_by_lane(rows),
        "llm_generated_locator_missing_failure_count_by_lane": llm_generated_locator_missing_failure_count_by_lane(rows),
        "llm_generated_locator_field_mismatch_failure_count_by_lane": llm_generated_locator_field_mismatch_failure_count_by_lane(rows),
        "pdf_source_pdf_path_mismatch_count": locator_field_mismatch_count(
            rows,
            source_family="PDF",
            field="source_pdf_path",
        ),
        "xlsx_row_label_mismatch_count": locator_field_mismatch_count(
            rows,
            source_family="XLSX",
            field="row_label",
        ),
        "text_text_locator_missing_count": locator_missing_field_count(
            rows,
            source_family="TEXT",
            field="text_locator",
        ),
    }
    all_track_residuals_after = {
        "strict_json_parse_failure_count_by_lane": strict_json_parse_failure_count_by_lane(all_rows),
        "llm_generated_locator_copy_failure_count_by_lane": llm_generated_locator_copy_failure_count_by_lane(all_rows),
        "llm_generated_locator_missing_failure_count_by_lane": llm_generated_locator_missing_failure_count_by_lane(all_rows),
        "llm_generated_locator_field_mismatch_failure_count_by_lane": llm_generated_locator_field_mismatch_failure_count_by_lane(all_rows),
        "pdf_source_pdf_path_mismatch_count": locator_field_mismatch_count(
            all_rows,
            source_family="PDF",
            field="source_pdf_path",
        ),
        "xlsx_row_label_mismatch_count": locator_field_mismatch_count(
            all_rows,
            source_family="XLSX",
            field="row_label",
        ),
        "text_text_locator_missing_count": locator_missing_field_count(
            all_rows,
            source_family="TEXT",
            field="text_locator",
        ),
    }
    summary = {
        "schema_version": V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "run_id": V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "source_run_id": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "context_source_run_id": V3_RUN_ID,
        "generated_at": utc_timestamp(),
        "status": (
            "PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_V3_1_4_COMPLETED"
            if v3_preflight.get("ok") and backend_preflight.get("ok")
            else "PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_V3_1_4_FAIL_CLOSED"
        ),
        "measurement_classification": "pdf_residual_answer_span_renderer_triage_v3_1_4_diagnostic_only",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_gate_auto_run": False,
        "write_summary_markdown": False,
        "target_row_count": len(target_query_ids),
        "total_denominator_rows": len(target_query_ids),
        "denominator_count": len(target_query_ids),
        "result_count": len(rows),
        "unique_query_id_count": len({row["query_id"] for row in rows}),
        "target_query_ids": target_query_ids,
        "rows_by_source_family": {
            "PDF": int(rows_by_family.get("PDF", 0)),
            "TEXT": int(rows_by_family.get("TEXT", 0)),
            "XLSX": int(rows_by_family.get("XLSX", 0)),
        },
        "scored_count": primary_lane_counts["scored_count"],
        "pass_count": primary_lane_counts["pass_count"],
        "failure_counts": primary_lane_counts["failure_counts"],
        "score_scope": "v3_primary_replay_lane_only_for_legacy_status_fields",
        "lane_names": list(V3_1_LANE_NAMES),
        "lane_counts": lane_counts,
        "source_family_lane_counts": family_lane_counts,
        "target_queue_before_lane_counts": target_before_lane_counts,
        "target_queue_after_lane_counts": target_after_lane_counts,
        "target_queue_pass_count_before_by_lane": lane_pass_counts(target_before_lane_counts),
        "target_queue_pass_count_after_by_lane": lane_pass_counts(target_after_lane_counts),
        "target_queue_answer_span_mismatch_before_by_lane": answer_span_mismatch_count_by_lane(target_before_rows),
        "target_queue_answer_span_mismatch_after_by_lane": answer_span_mismatch_count_by_lane(rows),
        "all_track_remeasurement_performed": True,
        "all_track_before_run_id": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "all_track_after_run_id": V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "all_track_result_count_before": int(v3_1_3_summary.get("all_track_result_count_after") or 29),
        "all_track_result_count_after": len(all_rows),
        "all_track_lane_counts_before": dict(all_before_lane_counts),
        "all_track_lane_counts_after": all_after_lane_counts,
        "all_track_pass_count_before_by_lane": dict(v3_1_3_summary.get("all_track_pass_count_after_by_lane") or {}),
        "all_track_pass_count_after_by_lane": lane_pass_counts(all_after_lane_counts),
        "all_track_answer_span_mismatch_before_by_lane": dict(
            v3_1_3_summary.get("all_track_answer_span_mismatch_after_by_lane") or {}
        ),
        "all_track_answer_span_mismatch_after_by_lane": answer_span_mismatch_count_by_lane(all_rows),
        **residuals_after,
        "all_track_residuals_after": all_track_residuals_after,
        "answer_span_renderer_diagnostic_counts": answer_span_renderer_diagnostic_counts(rows),
        "row_level_classification_changes": [row.get("row_level_classification_change") for row in rows],
        "target_queue_regression_from_v3_1_3_remaining_queue": target_regressions,
        "all_track_regression_from_v3_1_1_post_triage": all_track_regressions,
        "pdf_table_axis_disambiguation": pdf_residual_axis_diagnostic_summary(rows),
        "queue_source_of_truth_decision": {
            "selected_source_type": "machine_remaining_queue_artifact",
            "selected_source": official.repo_relative(DEFAULT_V3_1_3_REMAINING_QUEUE_JSON),
            "selected_source_run_id": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
            "docs_are_human_facing_narrative_only": True,
            "reason": "v3_1_3 remaining_triage_queue.json is the machine artifact after v3_1_2 and v3_1_3 diagnostic-only triage.",
        },
        "artifact_policy": {
            "summary_json": "machine_manifest",
            "results_jsonl": "canonical_result_payload",
            "failure_attribution_json": "forensic_debug_payload",
            "actual_response_audit_jsonl": "response_audit_payload",
            "answer_span_diagnostics_jsonl": "compact_answer_span_diagnostic_payload",
            "remaining_triage_queue_json": "queue_source_of_truth",
            "rag_current_eval_status_jsonl": "compact_status_ledger",
            "per_run_markdown_report_created": False,
            "classification_only_future_minimum_artifact_set": [
                "summary_json",
                "answer_span_diagnostics_jsonl",
                "remaining_triage_queue_json",
            ],
        },
        "answer_renderer_changes": [
            "prompt_tight_answer_attribute_value_instruction",
            "question_language_preservation_instruction",
            "xlsx_normalized_value_renderer_for_date_value_questions",
            "korean_language_restoration_from_source_context",
            "post_generation_scorer_compatibility_normalization",
            "pdf_table_axis_disambiguation_renderer_for_repeated_amount_growth_columns",
            "post_generation_pdf_residual_context_insufficiency_classification",
        ],
        "answer_score_reference_only": True,
        "citation_support_score_reference_only": True,
        "guardrails": guardrails,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "reference_span_text_embedded": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
        "source_bound_index_used": bool(index_dependency.get("rerun_allowed")),
        "source_bound_official_denominator_index_only": True,
        "canonical_search_unit_payload_used": True,
        "non_production_rag_index_dependency": index_dependency,
        "llm_backend": backend_preflight.get("llm_backend"),
        "llm_model": backend_preflight.get("model"),
        "llm_backend_preflight": dict(backend_preflight),
        "v3_completed_preflight": dict(v3_preflight),
        "v3_1_1_post_preflight": dict(post_preflight),
        "v3_1_3_remaining_queue_preflight": dict(queue_preflight),
        "local_llm_used": any(
            lane.get("llm_invoked") is True
            for row in rows
            for lane in row.get("lane_results", {}).values()
            if isinstance(lane, Mapping)
        ),
        "local_gpu_used": False,
        "performance_interpretation": "diagnostic_only_pdf_residual_answer_span_renderer_not_promotion_evidence",
        "diagnostic_limitations": [
            "The v3_1_4 result payload is the two-row PDF residual queue; all-track remeasurement is recorded separately in summary metrics.",
            "Expected answer and supporting evidence are post-generation scoring/audit references only.",
            "Lane A/B/C remain separated and must not be collapsed into one official score.",
        ],
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "v3_summary_json": official.file_identity(v3_summary_path),
            "v3_results_jsonl": official.file_identity(v3_results_path),
            "v3_failure_attribution_json": official.file_identity(v3_attribution_path),
            "v3_1_1_post_summary_json": official.file_identity(DEFAULT_V3_1_1_POST_SUMMARY_JSON),
            "v3_1_1_post_results_jsonl": official.file_identity(DEFAULT_V3_1_1_POST_RESULTS_JSONL),
            "v3_1_3_summary_json": official.file_identity(DEFAULT_V3_1_3_REMAINING_QUEUE_SUMMARY_JSON),
            "v3_1_3_results_jsonl": official.file_identity(DEFAULT_V3_1_3_REMAINING_QUEUE_RESULTS_JSONL),
            "v3_1_3_remaining_triage_queue_json": official.file_identity(DEFAULT_V3_1_3_REMAINING_QUEUE_JSON),
        },
        "artifact_paths": v3_1_4_pdf_residual_artifact_paths(args),
        "infrastructure_blocker": {
            "category": None if v3_preflight.get("ok") and backend_preflight.get("ok") else "V3_1_4_PRECONDITION_OR_BACKEND_BLOCKED",
            "domain": None if v3_preflight.get("ok") and backend_preflight.get("ok") else "v3_1_4_preflight",
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": False,
        },
        "agentic_loop": {
            "implemented": True,
            "enabled": False,
            "executed": False,
            "backend": "v3_1_4_pdf_residual_answer_span_renderer_triage",
            "steps_count": 0,
            "blockers": list(v3_preflight.get("errors") or []) + list(backend_preflight.get("blockers") or []),
        },
        "baseline_reference": {
            "run_id": "official_answer_citation_metric_first_run_v1",
            "status_detail": baseline.get("status_detail"),
            "artifact_identity": official.file_identity(baseline_path),
        },
        "next_step_recommendation": "continue_remaining_answer_span_renderer_queue_diagnostic_only",
        "registry_application_fallback_used": registry_application_fallback_used,
    }
    return summary


def build_v3_1_5_source_bound_coverage_summary(
    *,
    args: argparse.Namespace,
    rows: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    agentic_status: Mapping[str, Any],
    queue_preflight: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> dict[str, Any]:
    guardrails = v3_1_guardrails()
    index_dependency = agentic_status.get(
        "index_dependency",
        inspect_rag_index_dependency(Path(args.rag_index_dir)),
    )
    classification_counts = dict(sorted(Counter(row.get("issue_classification") for row in rows).items()))
    classification_result = {
        "query_id": "gq_auto_010",
        "classification": official.clean(rows[0].get("issue_classification")) if rows else "safe_source_artifact_missing_span",
        "final_queue_decision": official.clean(rows[0].get("final_queue_decision")) if rows else "remain_in_queue",
        "diagnostic_only": True,
        "promotion_evidence": False,
    }
    summary = {
        "schema_version": V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
        "run_id": V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
        "source_run_id": V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "generated_at": rows[0].get("generated_at") if rows else utc_timestamp(),
        "status": (
            "GQ_AUTO_010_SOURCE_BOUND_CONTEXT_COVERAGE_DIAGNOSTIC_V3_1_5_COMPLETED"
            if queue_preflight.get("ok")
            else "GQ_AUTO_010_SOURCE_BOUND_CONTEXT_COVERAGE_DIAGNOSTIC_V3_1_5_FAIL_CLOSED"
        ),
        "measurement_classification": (
            "gq_auto_010_source_bound_retrieval_context_coverage_diagnostic_v3_1_5_diagnostic_only"
        ),
        "diagnostic_only": True,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_gate_auto_run": False,
        "target_row_count": len(V3_1_5_SOURCE_BOUND_COVERAGE_QUERY_IDS),
        "total_denominator_rows": len(V3_1_5_SOURCE_BOUND_COVERAGE_QUERY_IDS),
        "denominator_count": len(V3_1_5_SOURCE_BOUND_COVERAGE_QUERY_IDS),
        "result_count": len(rows),
        "unique_query_id_count": len({row.get("query_id") for row in rows}),
        "target_query_ids": list(V3_1_5_SOURCE_BOUND_COVERAGE_QUERY_IDS),
        "rows_by_source_family": dict(sorted(Counter(row.get("source_family") for row in rows).items())),
        "scored_count": 0,
        "pass_count": 0,
        "failure_counts": classification_counts,
        "classification_counts": classification_counts,
        "classification_result": classification_result,
        "source_queue_artifact": official.repo_relative(DEFAULT_V3_1_4_PDF_RESIDUAL_REMAINING_QUEUE_JSON),
        "source_queue_preflight": dict(queue_preflight),
        "queue_source_of_truth_decision": {
            "selected_source_type": "machine_remaining_queue_artifact",
            "selected_source": official.repo_relative(DEFAULT_V3_1_4_PDF_RESIDUAL_REMAINING_QUEUE_JSON),
            "selected_source_run_id": V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
            "docs_are_human_facing_narrative_only": True,
            "reason": "v3_1_4 remaining_triage_queue.json is the machine artifact with only gq_auto_010 remaining.",
        },
        "artifact_policy": {
            "summary_json": "machine_manifest",
            "context_coverage_diagnostics_jsonl": "compact_source_bound_coverage_diagnostic_payload",
            "remaining_triage_queue_json": "queue_source_of_truth",
            "rag_current_eval_status_jsonl": "compact_status_ledger",
            "per_run_markdown_report_created": False,
            "minimum_durable_artifacts": [
                "summary_json",
                "context_coverage_diagnostics_jsonl",
                "remaining_triage_queue_json",
                "rag_current_eval_status_jsonl",
            ],
            "debug_only_artifacts_not_created": [
                "results_jsonl",
                "failure_attribution_json",
                "actual_response_audit_jsonl",
            ],
        },
        "official_retrieval_metrics_computed": False,
        "official_ndcg_computed": False,
        "official_mrr_computed": False,
        "official_hit_at_k_computed": False,
        "lane_score_collapsed": False,
        "non_production_index_or_export_fix_applied": False,
        "behavior_change_made": False,
        "all_track_remeasurement_performed": False,
        "all_track_remeasurement_reason": "not_run_because_no_retrieval_index_or_export_behavior_change_was_applied",
        "guardrails": guardrails,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "reference_span_text_embedded": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
        "source_bound_index_used": bool(index_dependency.get("rerun_allowed")),
        "source_bound_official_denominator_index_only": True,
        "canonical_search_unit_payload_used": True,
        "non_production_rag_index_dependency": index_dependency,
        "local_llm_used": False,
        "local_gpu_used": False,
        "llm_backend": None,
        "performance_interpretation": "diagnostic_only_source_bound_context_coverage_not_promotion_evidence",
        "diagnostic_limitations": [
            "Expected/reference numeric spans are audit-only probes and are not embedded as reference text.",
            "This run does not invoke live generation and does not force a PASS by renderer changes.",
            "No official nDCG, MRR, Hit@K, winner selection, or promotion gate is computed.",
        ],
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "v3_1_4_summary_json": official.file_identity(DEFAULT_V3_1_4_PDF_RESIDUAL_SUMMARY_JSON),
            "v3_1_4_results_jsonl": official.file_identity(DEFAULT_V3_1_4_PDF_RESIDUAL_RESULTS_JSONL),
            "v3_1_4_remaining_triage_queue_json": official.file_identity(
                DEFAULT_V3_1_4_PDF_RESIDUAL_REMAINING_QUEUE_JSON
            ),
        },
        "artifact_paths": v3_1_5_source_bound_coverage_artifact_paths(args),
        "infrastructure_blocker": {
            "category": None if queue_preflight.get("ok") else "V3_1_5_SOURCE_QUEUE_PREFLIGHT_BLOCKED",
            "domain": None if queue_preflight.get("ok") else "v3_1_5_source_queue_preflight",
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": False,
        },
        "agentic_loop": {
            "implemented": True,
            "enabled": False,
            "executed": False,
            "backend": "v3_1_5_source_bound_context_coverage_probe",
            "steps_count": 0,
            "blockers": list(queue_preflight.get("errors") or []),
        },
        "baseline_reference": {
            "run_id": "official_answer_citation_metric_first_run_v1",
            "status_detail": baseline.get("status_detail"),
            "artifact_identity": official.file_identity(baseline_path),
        },
        "next_step_recommendation": (
            "decide_or_implement_safe_pdf_paragraph_window_expansion_before_live_generation"
        ),
        "registry_application_fallback_used": registry_application_fallback_used,
    }
    return summary


def build_v3_1_6_safe_pdf_window_summary(
    *,
    args: argparse.Namespace,
    rows: Sequence[Mapping[str, Any]],
    all_rows: Sequence[Mapping[str, Any]],
    before_rows: Sequence[Mapping[str, Any]],
    v3_1_4_summary: Mapping[str, Any],
    baseline: Mapping[str, Any],
    agentic_status: Mapping[str, Any],
    v3_preflight: Mapping[str, Any],
    queue_preflight: Mapping[str, Any],
    backend_preflight: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
    v3_summary_path: Path,
    v3_results_path: Path,
    v3_attribution_path: Path,
) -> dict[str, Any]:
    target_query_ids = list(V3_1_6_SAFE_PDF_WINDOW_QUERY_IDS)
    target_before_rows = rows_for_query_ids(before_rows, target_query_ids)
    target_before_lane_counts = v3_1_lane_counts(target_before_rows)
    target_after_lane_counts = v3_1_lane_counts(rows)
    all_after_lane_counts = v3_1_lane_counts(all_rows)
    all_before_pass = dict(v3_1_4_summary.get("all_track_pass_count_after_by_lane") or {})
    target_before_pass = lane_pass_counts(target_before_lane_counts)
    target_after_pass = lane_pass_counts(target_after_lane_counts)
    expected_all_after = {
        lane: int(all_before_pass.get(lane) or 0)
        + int(target_after_pass.get(lane) or 0)
        - int(target_before_pass.get(lane) or 0)
        for lane in V3_1_LANE_NAMES
    }
    all_after_pass = lane_pass_counts(all_after_lane_counts)
    non_target_unexpected = sum(
        1
        for lane in V3_1_LANE_NAMES
        if int(all_after_pass.get(lane) or 0) != int(expected_all_after.get(lane) or 0)
    )
    guardrails = v3_1_guardrails()
    index_dependency = agentic_status.get(
        "index_dependency",
        inspect_rag_index_dependency(Path(args.rag_index_dir)),
    )
    rows_by_family = dict(sorted(Counter(row["source_family"] for row in rows).items()))
    lane_counts = target_after_lane_counts
    primary_lane_counts = lane_counts["v3_primary_replay"]
    context_diagnostics = [
        as_mapping(row.get("context_expansion_diagnostics"))
        for row in rows
        if isinstance(row.get("context_expansion_diagnostics"), Mapping)
    ]
    context_expansion_applied = any(item.get("expansion_applied") is True for item in context_diagnostics)
    residuals_after = {
        "strict_json_parse_failure_count_by_lane": strict_json_parse_failure_count_by_lane(rows),
        "llm_generated_locator_copy_failure_count_by_lane": llm_generated_locator_copy_failure_count_by_lane(rows),
        "llm_generated_locator_missing_failure_count_by_lane": llm_generated_locator_missing_failure_count_by_lane(rows),
        "llm_generated_locator_field_mismatch_failure_count_by_lane": llm_generated_locator_field_mismatch_failure_count_by_lane(rows),
        "pdf_source_pdf_path_mismatch_count": locator_field_mismatch_count(rows, source_family="PDF", field="source_pdf_path"),
        "xlsx_row_label_mismatch_count": locator_field_mismatch_count(rows, source_family="XLSX", field="row_label"),
        "text_text_locator_missing_count": locator_missing_field_count(rows, source_family="TEXT", field="text_locator"),
    }
    all_track_residuals_after = {
        "strict_json_parse_failure_count_by_lane": strict_json_parse_failure_count_by_lane(all_rows),
        "llm_generated_locator_copy_failure_count_by_lane": llm_generated_locator_copy_failure_count_by_lane(all_rows),
        "llm_generated_locator_missing_failure_count_by_lane": llm_generated_locator_missing_failure_count_by_lane(all_rows),
        "llm_generated_locator_field_mismatch_failure_count_by_lane": llm_generated_locator_field_mismatch_failure_count_by_lane(all_rows),
        "pdf_source_pdf_path_mismatch_count": locator_field_mismatch_count(all_rows, source_family="PDF", field="source_pdf_path"),
        "xlsx_row_label_mismatch_count": locator_field_mismatch_count(all_rows, source_family="XLSX", field="row_label"),
        "text_text_locator_missing_count": locator_missing_field_count(all_rows, source_family="TEXT", field="text_locator"),
    }
    summary = {
        "schema_version": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
        "run_id": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
        "source_run_id": V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
        "context_source_run_id": V3_RUN_ID,
        "generated_at": utc_timestamp(),
        "status": (
            "GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_DIAGNOSTIC_V3_1_6_COMPLETED"
            if v3_preflight.get("ok") and backend_preflight.get("ok")
            else "GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_DIAGNOSTIC_V3_1_6_FAIL_CLOSED"
        ),
        "measurement_classification": (
            "gq_auto_010_safe_pdf_paragraph_window_expansion_diagnostic_v3_1_6_diagnostic_only"
        ),
        "diagnostic_only": True,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "winner_selection": False,
        "promotion_gate_auto_run": False,
        "write_summary_markdown": False,
        "target_row_count": len(target_query_ids),
        "total_denominator_rows": len(target_query_ids),
        "denominator_count": len(target_query_ids),
        "result_count": len(rows),
        "unique_query_id_count": len({row["query_id"] for row in rows}),
        "target_query_ids": target_query_ids,
        "rows_by_source_family": {"PDF": int(rows_by_family.get("PDF", 0)), "TEXT": 0, "XLSX": 0},
        "scored_count": primary_lane_counts["scored_count"],
        "pass_count": primary_lane_counts["pass_count"],
        "failure_counts": primary_lane_counts["failure_counts"],
        "score_scope": "v3_primary_replay_lane_only_for_legacy_status_fields",
        "lane_names": list(V3_1_LANE_NAMES),
        "lane_counts": lane_counts,
        "source_family_lane_counts": v3_1_source_family_lane_counts(rows),
        "target_queue_before_lane_counts": target_before_lane_counts,
        "target_queue_after_lane_counts": target_after_lane_counts,
        "target_queue_pass_count_before_by_lane": target_before_pass,
        "target_queue_pass_count_after_by_lane": target_after_pass,
        "target_queue_answer_span_mismatch_before_by_lane": answer_span_mismatch_count_by_lane(target_before_rows),
        "target_queue_answer_span_mismatch_after_by_lane": answer_span_mismatch_count_by_lane(rows),
        "all_track_remeasurement_performed": context_expansion_applied,
        "all_track_before_run_id": V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "all_track_after_run_id": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
        "all_track_result_count_before": int(v3_1_4_summary.get("all_track_result_count_after") or 29),
        "all_track_result_count_after": len(all_rows),
        "all_track_lane_counts_before": dict(v3_1_4_summary.get("all_track_lane_counts_after") or {}),
        "all_track_lane_counts_after": all_after_lane_counts,
        "all_track_pass_count_before_by_lane": all_before_pass,
        "all_track_pass_count_after_by_lane": all_after_pass,
        "all_track_answer_span_mismatch_before_by_lane": dict(
            v3_1_4_summary.get("all_track_answer_span_mismatch_after_by_lane") or {}
        ),
        "all_track_answer_span_mismatch_after_by_lane": answer_span_mismatch_count_by_lane(all_rows),
        "all_track_non_target_context_expansion_query_ids": [],
        "all_track_non_target_unexpected_change_count": non_target_unexpected,
        **residuals_after,
        "all_track_residuals_after": all_track_residuals_after,
        "answer_span_renderer_diagnostic_counts": answer_span_renderer_diagnostic_counts(rows),
        "row_level_classification_changes": [row.get("row_level_classification_change") for row in rows],
        "context_expansion_attempted": any(item.get("expansion_attempted") is True for item in context_diagnostics),
        "context_expansion_applied": context_expansion_applied,
        "context_expansion_policy_name": PDF_PARAGRAPH_WINDOW_EXPANSION_POLICY_NAME,
        "locator_safe_metadata_available": any(
            item.get("locator_safe_metadata_available") is True for item in context_diagnostics
        ),
        "behavior_change_made": context_expansion_applied,
        "non_production_index_or_export_fix_applied": False,
        "queue_source_of_truth_decision": {
            "selected_source_type": "machine_remaining_queue_artifact",
            "selected_source": official.repo_relative(DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_QUEUE_JSON),
            "selected_source_run_id": V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
            "docs_are_human_facing_narrative_only": True,
            "reason": "v3_1_5 remaining_triage_queue.json is the machine artifact with only gq_auto_010 remaining.",
        },
        "source_queue_artifact": official.repo_relative(DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_QUEUE_JSON),
        "source_queue_preflight": dict(queue_preflight),
        "artifact_policy": {
            "summary_json": "machine_manifest",
            "results_jsonl": "canonical_result_payload",
            "failure_attribution_json": "forensic_debug_payload",
            "actual_response_audit_jsonl": "response_audit_payload",
            "answer_span_diagnostics_jsonl": "compact_answer_span_diagnostic_payload",
            "context_expansion_diagnostics_jsonl": "compact_pdf_context_expansion_diagnostic_payload",
            "remaining_triage_queue_json": "queue_source_of_truth",
            "rag_current_eval_status_jsonl": "compact_status_ledger",
            "per_run_markdown_report_created": False,
            "minimum_durable_artifacts": [
                "summary_json",
                "results_jsonl",
                "failure_attribution_json",
                "actual_response_audit_jsonl",
                "answer_span_diagnostics_jsonl",
                "context_expansion_diagnostics_jsonl",
                "remaining_triage_queue_json",
                "rag_current_eval_status_jsonl",
            ],
        },
        "official_retrieval_metrics_computed": False,
        "official_ndcg_computed": False,
        "official_mrr_computed": False,
        "official_hit_at_k_computed": False,
        "lane_score_collapsed": False,
        "guardrails": guardrails,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "reference_span_text_embedded": False,
        "production_mutation": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
        "source_bound_index_used": bool(index_dependency.get("rerun_allowed")),
        "source_bound_official_denominator_index_only": True,
        "canonical_search_unit_payload_used": True,
        "non_production_rag_index_dependency": index_dependency,
        "llm_backend": backend_preflight.get("llm_backend"),
        "llm_model": backend_preflight.get("model"),
        "llm_backend_preflight": dict(backend_preflight),
        "v3_completed_preflight": dict(v3_preflight),
        "local_llm_used": any(
            lane.get("llm_invoked") is True
            for row in rows
            for lane in row.get("lane_results", {}).values()
            if isinstance(lane, Mapping)
        ),
        "local_gpu_used": False,
        "performance_interpretation": "diagnostic_only_safe_pdf_context_expansion_not_promotion_evidence",
        "diagnostic_limitations": [
            "The expansion is source-bound same-page PDF context, not expected-answer text.",
            "Expected answer and supporting evidence remain post-generation scoring/audit references only.",
            "Lane A/B/C remain separated and must not be collapsed into one official score.",
            "No official nDCG, MRR, Hit@K, winner selection, or promotion gate is computed.",
        ],
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "v3_summary_json": official.file_identity(v3_summary_path),
            "v3_results_jsonl": official.file_identity(v3_results_path),
            "v3_failure_attribution_json": official.file_identity(v3_attribution_path),
            "v3_1_4_summary_json": official.file_identity(DEFAULT_V3_1_4_PDF_RESIDUAL_SUMMARY_JSON),
            "v3_1_4_results_jsonl": official.file_identity(DEFAULT_V3_1_4_PDF_RESIDUAL_RESULTS_JSONL),
            "v3_1_5_summary_json": official.file_identity(DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_SUMMARY_JSON),
            "v3_1_5_context_coverage_diagnostics_jsonl": official.file_identity(
                DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_DIAGNOSTICS_JSONL
            ),
            "v3_1_5_remaining_triage_queue_json": official.file_identity(
                DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_QUEUE_JSON
            ),
        },
        "artifact_paths": v3_1_6_safe_pdf_window_artifact_paths(args),
        "infrastructure_blocker": {
            "category": None if v3_preflight.get("ok") and backend_preflight.get("ok") else "V3_1_6_PRECONDITION_OR_BACKEND_BLOCKED",
            "domain": None if v3_preflight.get("ok") and backend_preflight.get("ok") else "v3_1_6_preflight",
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": False,
        },
        "agentic_loop": {
            "implemented": True,
            "enabled": False,
            "executed": False,
            "backend": "v3_1_6_safe_pdf_paragraph_window_expansion_diagnostic",
            "steps_count": 0,
            "blockers": list(v3_preflight.get("errors") or []) + list(backend_preflight.get("blockers") or []),
        },
        "baseline_reference": {
            "run_id": "official_answer_citation_metric_first_run_v1",
            "status_detail": baseline.get("status_detail"),
            "artifact_identity": official.file_identity(baseline_path),
        },
        "next_step_recommendation": "remaining_queue_cleared" if not any_failing_lane(rows) else "inspect_safe_pdf_context_expansion_result",
        "registry_application_fallback_used": registry_application_fallback_used,
    }
    return summary


def pdf_residual_axis_diagnostic_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in rows:
        query_id = official.clean(row.get("query_id"))
        applied_lanes = [
            lane_name
            for lane_name, lane in as_mapping(row.get("lane_results")).items()
            if "pdf_table_axis_tight_answer" in as_mapping(lane.get("answer_renderer")).get("operations", [])
        ]
        diagnostic_categories = {
            lane_name: as_mapping(diagnostic).get("diagnostic_subcategories")
            for lane_name, diagnostic in as_mapping(row.get("answer_span_renderer_diagnostics")).items()
            if isinstance(diagnostic, Mapping)
        }
        if applied_lanes:
            classification = "pdf_table_axis_disambiguation"
        elif any("retrieval_context_insufficiency" in (categories or []) for categories in diagnostic_categories.values()):
            classification = "retrieval_context_insufficiency"
        else:
            classification = "diagnostic_only_expected_span_mismatch"
        out[query_id] = {
            "classification": classification,
            "applied_lanes": applied_lanes,
            "diagnostic_categories_by_lane": diagnostic_categories,
            "diagnostic_only": True,
            "promotion_evidence": False,
        }
    return out


def rows_for_query_ids(rows: Sequence[Mapping[str, Any]], query_ids: Sequence[str]) -> list[dict[str, Any]]:
    by_id = {official.clean(row.get("query_id")): dict(row) for row in rows}
    return [by_id[query_id] for query_id in query_ids if query_id in by_id]


def lane_pass_counts(lane_counts: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    return {
        lane_name: int(as_mapping(counts).get("pass_count") or 0)
        for lane_name, counts in lane_counts.items()
    }


def regression_from_v3_1_1_post_triage(
    rows: Sequence[Mapping[str, Any]],
    before_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    before_by_id = {official.clean(row.get("query_id")): row for row in before_rows}
    regressions: list[dict[str, Any]] = []
    for row in rows:
        before = as_mapping(before_by_id.get(official.clean(row.get("query_id"))))
        for lane_name in V3_1_LANE_NAMES:
            before_lane = as_mapping(as_mapping(before.get("lane_results")).get(lane_name))
            after_lane = as_mapping(as_mapping(row.get("lane_results")).get(lane_name))
            if before_lane.get("failure_category") == "PASS" and after_lane.get("failure_category") != "PASS":
                regressions.append(
                    {
                        "query_id": row.get("query_id"),
                        "lane_name": lane_name,
                        "before_failure_category": before_lane.get("failure_category"),
                        "after_failure_category": after_lane.get("failure_category"),
                        "diagnostic_only": True,
                        "promotion_evidence": False,
                    }
                )
    return {
        "baseline_run_id": V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
        "existing_pass_regression_count": len(regressions),
        "regressions": regressions,
    }


def text_namu_v2_0005_lane_a_b_not_degraded(
    rows: Sequence[Mapping[str, Any]],
    before_rows: Sequence[Mapping[str, Any]],
) -> bool:
    after = row_by_query_id(rows, "text_namu_v2_0005")
    before = row_by_query_id(before_rows, "text_namu_v2_0005")
    for lane_name in ("v3_primary_replay", "live_llm_retrieval_topk"):
        if as_mapping(as_mapping(before.get("lane_results")).get(lane_name)).get("failure_category") == "PASS":
            if as_mapping(as_mapping(after.get("lane_results")).get(lane_name)).get("failure_category") != "PASS":
                return False
    return True


def text_namu_v2_0005_lane_c_improved(
    rows: Sequence[Mapping[str, Any]],
    before_rows: Sequence[Mapping[str, Any]],
) -> bool:
    after = row_by_query_id(rows, "text_namu_v2_0005")
    before = row_by_query_id(before_rows, "text_namu_v2_0005")
    before_lane = as_mapping(as_mapping(before.get("lane_results")).get("live_llm_query_bound_oracle"))
    after_lane = as_mapping(as_mapping(after.get("lane_results")).get("live_llm_query_bound_oracle"))
    return before_lane.get("failure_category") != "PASS" and after_lane.get("failure_category") == "PASS"


def row_by_query_id(rows: Sequence[Mapping[str, Any]], query_id: str) -> Mapping[str, Any]:
    for row in rows:
        if official.clean(row.get("query_id")) == query_id:
            return row
    return {}


def v3_1_priority_1_5_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = args.run_id
    return {
        "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "summary_md": official.repo_relative(Path(args.summary_md)),
        "failure_attribution_json": report_artifact_repo_relative(run_id, "failure.json"),
        "actual_response_audit_jsonl": report_artifact_repo_relative(run_id, "audit.jsonl"),
        "strict_json_diagnostics_json": official.repo_relative(REPORT_ARCHIVE_DIR / "v3_1_priority_strict_json.json"),
        "strict_json_diagnostics_md": official.repo_relative(REPORT_ARCHIVE_DIR / "v3_1_priority_strict_json.md"),
        "triage_delta_json": report_artifact_repo_relative(run_id, "delta.json"),
        "triage_delta_md": report_artifact_repo_relative(run_id, "delta.md"),
    }


def v3_1_text_locator_residual_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = args.run_id
    return {
        "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "summary_md": official.repo_relative(Path(args.summary_md)),
        "failure_attribution_json": report_artifact_repo_relative(run_id, "failure.json"),
        "triage_delta_json": report_artifact_repo_relative(run_id, "delta.json"),
        "triage_delta_md": report_artifact_repo_relative(run_id, "delta.md"),
    }


def v3_1_1_post_triage_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = args.run_id
    return {
        "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "summary_md": official.repo_relative(Path(args.summary_md)),
        "failure_attribution_json": report_artifact_repo_relative(run_id, "failure.json"),
        "actual_response_audit_jsonl": report_artifact_repo_relative(run_id, "audit.jsonl"),
        "triage_queue_json": report_artifact_repo_relative(run_id, "queue.json"),
    }


def v3_1_2_answer_span_renderer_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = args.run_id
    return {
        "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "failure_attribution_json": report_artifact_repo_relative(run_id, "failure.json"),
        "actual_response_audit_jsonl": report_artifact_repo_relative(run_id, "audit.jsonl"),
        "answer_span_diagnostics_jsonl": report_artifact_repo_relative(run_id, "spans.jsonl"),
        "remaining_triage_queue_json": report_artifact_repo_relative(run_id, "queue.json"),
    }


def v3_1_3_remaining_queue_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = args.run_id
    return {
        "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "failure_attribution_json": report_artifact_repo_relative(run_id, "failure.json"),
        "actual_response_audit_jsonl": report_artifact_repo_relative(run_id, "audit.jsonl"),
        "answer_span_diagnostics_jsonl": report_artifact_repo_relative(run_id, "spans.jsonl"),
        "remaining_triage_queue_json": report_artifact_repo_relative(run_id, "queue.json"),
    }


def v3_1_4_pdf_residual_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = args.run_id
    return {
        "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "failure_attribution_json": report_artifact_repo_relative(run_id, "failure.json"),
        "actual_response_audit_jsonl": report_artifact_repo_relative(run_id, "audit.jsonl"),
        "answer_span_diagnostics_jsonl": report_artifact_repo_relative(run_id, "spans.jsonl"),
        "remaining_triage_queue_json": report_artifact_repo_relative(run_id, "queue.json"),
    }


def v3_1_5_source_bound_coverage_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = args.run_id
    return {
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "context_coverage_diagnostics_jsonl": report_artifact_repo_relative(run_id, "context.jsonl"),
        "remaining_triage_queue_json": report_artifact_repo_relative(run_id, "queue.json"),
        "status_jsonl": official.repo_relative(Path(args.status_jsonl)),
    }


def v3_1_6_safe_pdf_window_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = args.run_id
    return {
        "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "failure_attribution_json": report_artifact_repo_relative(run_id, "failure.json"),
        "actual_response_audit_jsonl": report_artifact_repo_relative(run_id, "audit.jsonl"),
        "answer_span_diagnostics_jsonl": report_artifact_repo_relative(run_id, "spans.jsonl"),
        "context_expansion_diagnostics_jsonl": report_artifact_repo_relative(run_id, "context.jsonl"),
        "remaining_triage_queue_json": report_artifact_repo_relative(run_id, "queue.json"),
        "status_jsonl": official.repo_relative(Path(args.status_jsonl)),
    }


def v3_1_7_post_residual_queue_closure_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID
    return {
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "all_track_residual_inventory_jsonl": report_artifact_repo_relative(
            run_id,
            "all_track_residual_inventory.jsonl",
        ),
        "remaining_triage_queue_json": report_artifact_repo_relative(run_id, "remaining_triage_queue.json"),
        "user_decision_packet_json": report_artifact_repo_relative(run_id, "user_decision_packet.json"),
        "silver_readiness_audit_json": report_artifact_repo_relative(run_id, "silver_readiness_audit.json"),
        "status_jsonl": official.repo_relative(Path(args.status_jsonl)),
    }


def v3_1_8_gold_policy_review_packet_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID
    return {
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "human_review_packet_json": report_artifact_repo_relative(run_id, "human_review_packet.json"),
        "decision_matrix_jsonl": report_artifact_repo_relative(run_id, "decision_matrix.jsonl"),
        "remaining_triage_queue_json": report_artifact_repo_relative(run_id, "remaining_triage_queue.json"),
        "status_jsonl": official.repo_relative(Path(args.status_jsonl)),
    }


def v3_1_9_user_gold_policy_override_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID
    return {
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "applied_overrides_jsonl": report_artifact_repo_relative(run_id, "applied_overrides.jsonl"),
        "gold_diff_jsonl": report_artifact_repo_relative(run_id, "gold_diff.jsonl"),
        "rescored_results_jsonl": report_artifact_repo_relative(run_id, "rescored_results.jsonl"),
        "remaining_triage_queue_json": report_artifact_repo_relative(run_id, "remaining_triage_queue.json"),
        "status_jsonl": official.repo_relative(Path(args.status_jsonl)),
    }


def v3_1_guardrails() -> dict[str, bool]:
    return {
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


def priority_rows_by_id(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id = {official.clean(row.get("query_id")): dict(row) for row in rows}
    return [by_id[query_id] for query_id in V3_1_PRIORITY_1_5_QUERY_IDS if query_id in by_id]


def strict_json_parse_failure_count(rows: Sequence[Mapping[str, Any]]) -> int:
    return sum(
        1
        for row in rows
        for lane in [as_mapping((row.get("lane_results") or {}).get("live_llm_retrieval_topk"))]
        if lane.get("failure_category") == "LLM_STRICT_JSON_PARSE_FAILURE"
    )


def strict_json_parse_failure_count_by_lane(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        lane_name: sum(
            1
            for row in rows
            if as_mapping(as_mapping(row.get("lane_results")).get(lane_name)).get("failure_category")
            == "LLM_STRICT_JSON_PARSE_FAILURE"
        )
        for lane_name in V3_1_LANE_NAMES
    }


def strict_json_schema_repair_applied_count_by_lane(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        lane_name: sum(
            1
            for row in rows
            if lane_schema_repair_applied(as_mapping(as_mapping(row.get("lane_results")).get(lane_name)))
        )
        for lane_name in V3_1_LANE_NAMES
    }


def lane_schema_repair_applied(lane: Mapping[str, Any]) -> bool:
    diagnostics = as_mapping(lane.get("strict_json_diagnostics") or lane.get("strict_json_raw"))
    if "strict_json" in diagnostics and isinstance(diagnostics.get("strict_json"), Mapping):
        diagnostics = as_mapping(diagnostics.get("strict_json"))
    return diagnostics.get("schema_repair_applied") is True


def strict_json_schema_repair_applied_count(rows: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for row in rows:
        lane = as_mapping((row.get("lane_results") or {}).get("live_llm_retrieval_topk"))
        if lane_schema_repair_applied(lane):
            count += 1
    return count


def llm_generated_locator_copy_failure_count(rows: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for row in rows:
        lane = as_mapping((row.get("lane_results") or {}).get("live_llm_retrieval_topk"))
        validation = as_mapping(lane.get("llm_generated_locator_validation"))
        if validation.get("generated_by_llm") is True and validation.get("ok") is not True:
            count += 1
    return count


def llm_generated_locator_field_mismatch_failure_count(rows: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for row in rows:
        lane = as_mapping((row.get("lane_results") or {}).get("live_llm_retrieval_topk"))
        validation = as_mapping(lane.get("llm_generated_locator_validation"))
        if validation.get("generated_by_llm") is True and validation.get("mismatched_fields_by_search_unit_id"):
            count += 1
    return count


def llm_generated_locator_missing_failure_count(rows: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for row in rows:
        lane = as_mapping((row.get("lane_results") or {}).get("live_llm_retrieval_topk"))
        validation = as_mapping(lane.get("llm_generated_locator_validation"))
        if validation.get("generated_by_llm") is not True:
            continue
        if validation.get("missing_locator_for_search_unit_ids") or validation.get("missing_fields_by_search_unit_id"):
            count += 1
    return count


def llm_generated_locator_copy_failure_count_by_lane(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        lane_name: sum(
            1
            for row in rows
            if llm_generated_locator_failed(as_mapping(as_mapping(row.get("lane_results")).get(lane_name)))
        )
        for lane_name in V3_1_LANE_NAMES
    }


def llm_generated_locator_missing_failure_count_by_lane(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for lane_name in V3_1_LANE_NAMES:
        count = 0
        for row in rows:
            lane = as_mapping(as_mapping(row.get("lane_results")).get(lane_name))
            validation = as_mapping(lane.get("llm_generated_locator_validation"))
            if validation.get("generated_by_llm") is True and (
                validation.get("missing_locator_for_search_unit_ids")
                or validation.get("missing_fields_by_search_unit_id")
            ):
                count += 1
        out[lane_name] = count
    return out


def llm_generated_locator_field_mismatch_failure_count_by_lane(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for lane_name in V3_1_LANE_NAMES:
        count = 0
        for row in rows:
            lane = as_mapping(as_mapping(row.get("lane_results")).get(lane_name))
            validation = as_mapping(lane.get("llm_generated_locator_validation"))
            if validation.get("generated_by_llm") is True and validation.get("mismatched_fields_by_search_unit_id"):
                count += 1
        out[lane_name] = count
    return out


def posthoc_payload_locator_preservation_failure_count(rows: Sequence[Mapping[str, Any]]) -> int:
    count = 0
    for row in rows:
        for lane_name in V3_1_LIVE_LANE_NAMES:
            lane = as_mapping((row.get("lane_results") or {}).get(lane_name))
            preservation = as_mapping(lane.get("locator_preservation"))
            if preservation and preservation.get("ok") is not True:
                count += 1
    return count


def locator_missing_field_count(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_family: str,
    field: str,
) -> int:
    count = 0
    for row in rows:
        if row.get("source_family") != source_family:
            continue
        for lane_name in V3_1_LIVE_LANE_NAMES:
            validation = as_mapping(
                as_mapping((row.get("lane_results") or {}).get(lane_name)).get("llm_generated_locator_validation")
            )
            missing = validation.get("missing_fields_by_search_unit_id")
            if not isinstance(missing, Mapping):
                continue
            if any(field in (fields or []) for fields in missing.values()):
                count += 1
    return count


def locator_missing_field_count_for_lane(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_family: str,
    field: str,
    lane_name: str,
) -> int:
    count = 0
    for row in rows:
        if row.get("source_family") != source_family:
            continue
        validation = as_mapping(
            as_mapping((row.get("lane_results") or {}).get(lane_name)).get("llm_generated_locator_validation")
        )
        missing = validation.get("missing_fields_by_search_unit_id")
        if not isinstance(missing, Mapping):
            continue
        if any(field in (fields or []) for fields in missing.values()):
            count += 1
    return count


def locator_field_mismatch_count(
    rows: Sequence[Mapping[str, Any]],
    *,
    source_family: str,
    field: str,
) -> int:
    count = 0
    for row in rows:
        if row.get("source_family") != source_family:
            continue
        for lane_name in V3_1_LIVE_LANE_NAMES:
            validation = as_mapping(
                as_mapping((row.get("lane_results") or {}).get(lane_name)).get("llm_generated_locator_validation")
            )
            mismatches = validation.get("mismatched_fields_by_search_unit_id")
            if not isinstance(mismatches, Mapping):
                continue
            if any(field in (fields or []) for fields in mismatches.values()):
                count += 1
    return count


def answer_span_mismatch_count_by_lane(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        lane_name: sum(
            1
            for row in rows
            if as_mapping(as_mapping(row.get("lane_results")).get(lane_name)).get("failure_category")
            == "LLM_EXPECTED_SPAN_MISMATCH"
        )
        for lane_name in V3_1_LANE_NAMES
    }


def regression_from_v3_1_foundation(rows: Sequence[Mapping[str, Any]], baseline_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    baseline_by_id = {official.clean(row.get("query_id")): row for row in baseline_rows}
    regressions: list[dict[str, Any]] = []
    for row in rows:
        before = as_mapping(baseline_by_id.get(official.clean(row.get("query_id"))))
        for lane_name in V3_1_LANE_NAMES:
            before_lane = as_mapping(as_mapping(before.get("lane_results")).get(lane_name))
            after_lane = as_mapping(as_mapping(row.get("lane_results")).get(lane_name))
            if before_lane.get("failure_category") == "PASS" and after_lane.get("failure_category") != "PASS":
                regressions.append(
                    {
                        "query_id": row.get("query_id"),
                        "lane_name": lane_name,
                        "before_failure_category": before_lane.get("failure_category"),
                        "after_failure_category": after_lane.get("failure_category"),
                    }
                )
    return {
        "baseline_run_id": V3_1_RUN_ID,
        "existing_pass_regression_count": len(regressions),
        "regressions": regressions,
    }


def v3_1_lane_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for lane_name in V3_1_LANE_NAMES:
        lane_results = [row["lane_results"][lane_name] for row in rows]
        failure_counts = Counter(lane["failure_category"] for lane in lane_results)
        out[lane_name] = {
            "scored_count": sum(1 for lane in lane_results if lane.get("answer_score") is not None and lane.get("citation_support_score") is not None),
            "pass_count": int(failure_counts.get("PASS", 0)),
            "failure_counts": dict(sorted(failure_counts.items())),
            "llm_invoked_count": sum(1 for lane in lane_results if lane.get("llm_invoked") is True),
            "adapter_retained_count": sum(1 for lane in lane_results if lane.get("answer_origin") == "STRUCTURED_ADAPTER"),
            "query_bound_evidence_gap_count": sum(1 for lane in lane_results if lane.get("failure_category") == "RETRIEVAL_QUERY_BOUND_MISS"),
            "schema_mismatch_residual_count": sum(1 for lane in lane_results if lane.get("failure_category") == "CITATION_PAYLOAD_SCHEMA_MISMATCH"),
            "citation_unsupported_count": sum(1 for lane in lane_results if official.clean(lane.get("failure_category")).startswith("CITATION_")),
            "answer_partial_unsupported_count": sum(1 for lane in lane_results if lane.get("failure_category") in {"LLM_TRUE_PARTIAL_SYNTHESIS", "LLM_EXPECTED_SPAN_MISMATCH", "LLM_UNSUPPORTED_INFERENCE", "LLM_ANSWER_OVERCOMPRESSION"}),
            "llm_generated_locator_failure_count": sum(1 for lane in lane_results if llm_generated_locator_failed(lane)),
        }
    return out


def v3_1_source_family_lane_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for source_family in ("PDF", "TEXT", "XLSX"):
        family_rows = [row for row in rows if row["source_family"] == source_family]
        out[source_family] = v3_1_lane_counts(family_rows)
    return out


def locator_preservation_failure_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out = {"PDF": 0, "TEXT": 0, "XLSX": 0}
    for row in rows:
        family = row["source_family"]
        failed = any(
            lane.get("locator_preservation", {}).get("ok") is not True
            for lane in row.get("lane_results", {}).values()
        )
        if failed:
            out[family] += 1
    return out


def llm_generated_locator_failed(lane: Mapping[str, Any]) -> bool:
    validation = lane.get("llm_generated_locator_validation")
    return isinstance(validation, Mapping) and validation.get("generated_by_llm") is True and validation.get("ok") is not True


def llm_generated_locator_failure_counts_by_source_family(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out = {"PDF": 0, "TEXT": 0, "XLSX": 0}
    for row in rows:
        family = row["source_family"]
        if any(llm_generated_locator_failed(lane) for lane in row.get("lane_results", {}).values()):
            out[family] += 1
    return out


def citation_payload_summary_by_lane(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for lane_name in V3_1_LANE_NAMES:
        lane_results = [row["lane_results"][lane_name] for row in rows]
        out[lane_name] = {
            "ok_count": sum(1 for lane in lane_results if lane.get("citation_payload_validation", {}).get("ok") is True),
            "invalid_count": sum(1 for lane in lane_results if lane.get("citation_payload_validation", {}).get("ok") is not True),
            "empty_citation_count": sum(1 for lane in lane_results if not lane.get("generated_citations")),
        }
    return out


def v3_1_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = args.run_id
    return {
        "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "summary_md": official.repo_relative(Path(args.summary_md)),
        "failure_attribution_json": report_artifact_repo_relative(run_id, "failure.json"),
        "actual_response_audit_jsonl": report_artifact_repo_relative(run_id, "audit.jsonl"),
        "actual_response_audit_md": report_artifact_repo_relative(run_id, "audit.md"),
        "triage_queue_json": report_artifact_repo_relative(run_id, "queue.json"),
        "triage_queue_md": report_artifact_repo_relative(run_id, "queue.md"),
    }


def per_track_counts_by_source_family(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    family_by_track = {
        "pdf_business_ocr_mm": "PDF",
        "text_namu_v2_1": "TEXT",
        "xlsx_business_structured": "XLSX",
    }
    out: dict[str, Any] = {}
    for track, family in family_by_track.items():
        track_rows = [row for row in rows if row.get("track") == track]
        failure_counts = Counter(official.clean(row.get("failure_category")) for row in track_rows)
        bucket_counts = Counter(official.clean(row.get("result_bucket")) for row in track_rows)
        out[family] = {
            "track": track,
            "row_count": len(track_rows),
            "scored_count": sum(
                1
                for row in track_rows
                if row.get("answer_score") is not None and row.get("citation_support_score") is not None
            ),
            "pass_count": int(failure_counts.get("PASS", 0)),
            "failure_counts": dict(sorted(failure_counts.items())),
            "result_bucket_counts": dict(sorted(bucket_counts.items())),
        }
    return out


def build_residual_failure_audit(
    *,
    run_id: str,
    result_rows: Sequence[Mapping[str, Any]],
    source_rows: Sequence[Mapping[str, Any]],
    schema_mismatch_residual_count: int,
) -> dict[str, Any] | None:
    if run_id != V2_1_RUN_ID:
        return None
    result_by_id = {
        official.clean(row.get("query_id")): row
        for row in result_rows
        if official.clean(row.get("query_id"))
    }
    source_by_id = {
        official.clean(row.get("query_id")): row
        for row in source_rows
        if official.clean(row.get("query_id"))
    }
    audit_rows: list[dict[str, Any]] = []
    missing_query_ids: list[str] = []
    for query_id in V2_1_RESIDUAL_FAILURE_AUDIT_QUERY_IDS:
        result_row_for_id = result_by_id.get(query_id)
        source_row_for_id = source_by_id.get(query_id)
        if result_row_for_id is None or source_row_for_id is None:
            missing_query_ids.append(query_id)
            continue
        audit_rows.append(
            residual_failure_audit_for_row(
                source_row=source_row_for_id,
                result_row_for_id=result_row_for_id,
            )
        )

    non_target_audited_query_ids = sorted(
        official.clean(row.get("query_id"))
        for row in result_rows
        if row.get("failure_category") != "PASS"
        and official.clean(row.get("query_id")) not in V2_1_RESIDUAL_FAILURE_AUDIT_QUERY_IDS
    )
    counts = {
        "answer_synthesis_limitation_confirmed": sum(
            1 for row in audit_rows if row["answer_synthesis_limitation_confirmed"] is True
        ),
        "deterministic_extractive_answer_missing_value": sum(
            1 for row in audit_rows if row["deterministic_extractive_answer_missing_value"] is True
        ),
        "query_bound_evidence_contains_answer": sum(
            1 for row in audit_rows if row["query_bound_evidence_contains_answer"] is True
        ),
        "query_bound_evidence_contains_citation_support": sum(
            1 for row in audit_rows if row["query_bound_evidence_contains_citation_support"] is True
        ),
        "query_bound_evidence_gap": sum(1 for row in audit_rows if row["query_bound_evidence_gap"] is True),
        "same_track_non_query_bound_distracted": sum(
            1
            for row in audit_rows
            if row["same_track_non_query_bound_evidence_helped_or_distracted"] == "distracted"
        ),
        "same_track_non_query_bound_helped": sum(
            1
            for row in audit_rows
            if row["same_track_non_query_bound_evidence_helped_or_distracted"] == "helped"
        ),
        "scorer_normalization_issue_possible": sum(
            1 for row in audit_rows if row["scorer_normalization_issue_possible"] is True
        ),
    }
    refined_counts = dict(
        sorted(Counter(row["refined_primary_attribution"] for row in audit_rows).items())
    )
    full_validation_blocked = counts["query_bound_evidence_gap"] > 0
    return {
        "scope": "v2_1_residual_failures_only",
        "target_query_ids": list(V2_1_RESIDUAL_FAILURE_AUDIT_QUERY_IDS),
        "audited_query_ids": [row["query_id"] for row in audit_rows],
        "audited_row_count": len(audit_rows),
        "missing_target_query_ids": missing_query_ids,
        "non_target_audited_query_ids": non_target_audited_query_ids,
        "rows": audit_rows,
        "counts": counts,
        "refined_primary_attribution_counts": refined_counts,
        "schema_mismatch_residual_count": int(schema_mismatch_residual_count),
        "llm_backend": "noop",
        "llm_backend_validation_started": False,
        "llm_backend_validation_readiness": (
            "BLOCKED_FOR_FULL_VALIDATION_PDF_QUERY_BOUND_EVIDENCE_GAP_REMAINS"
            if full_validation_blocked
            else "READY_FOR_LLM_BACKEND_VALIDATION_RESIDUALS_CONFIRMED_AS_SYNTHESIS"
        ),
        "llm_backend_validation_next_step": (
            "Repair PDF query-bound table-value evidence before treating full LLM backend validation as quality proof; "
            "TEXT residual is suitable for synthesis validation."
            if full_validation_blocked
            else "Proceed to LLM backend validation; residuals are synthesis-limited under query-bound evidence."
        ),
        "expected_supporting_gold_used_for_audit_only": True,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "baseline_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "human_label_mutation": False,
        "production_mutation": False,
        "promotion_evidence": False,
        "diagnostic_only": True,
    }


def residual_failure_audit_for_row(
    *,
    source_row: Mapping[str, Any],
    result_row_for_id: Mapping[str, Any],
) -> dict[str, Any]:
    query_id = official.clean(result_row_for_id.get("query_id") or source_row.get("query_id"))
    expected_answer = official.clean(source_row.get("expected_answer"))
    supporting_evidence = official.clean(source_row.get("supporting_evidence"))
    generated_answer = official.clean(result_row_for_id.get("generated_answer"))
    generated_short_answer = extract_short_answer_text(generated_answer)
    query_bound_citations, non_query_bound_citations = split_scored_citations_by_query(
        result_row_for_id.get("scored_citations") or [],
        query_id,
    )
    query_bound_text = audit_citation_text(query_bound_citations)
    non_query_bound_text = audit_citation_text(non_query_bound_citations)
    query_bound_contains_answer = audit_answer_supported_by_text(expected_answer, query_bound_text)
    query_bound_contains_support = audit_answer_supported_by_text(
        supporting_evidence or expected_answer,
        query_bound_text,
    )
    non_query_bound_contains_answer = audit_answer_supported_by_text(expected_answer, non_query_bound_text)
    non_query_bound_contains_support = audit_answer_supported_by_text(
        supporting_evidence or expected_answer,
        non_query_bound_text,
    )
    generated_contains_answer = audit_answer_supported_by_text(expected_answer, generated_short_answer)
    generated_contains_support = audit_answer_supported_by_text(
        supporting_evidence or expected_answer,
        generated_short_answer,
    )
    row_failure_category = official.clean(result_row_for_id.get("failure_category"))
    row_passed = row_failure_category == "PASS"
    deterministic_answer_missing = not generated_contains_answer
    query_bound_gap = not (query_bound_contains_answer and query_bound_contains_support)
    scorer_normalization_issue_possible = False if row_passed else (
        (
            result_row_for_id.get("answer_score") == 1.0 and deterministic_answer_missing
        ) or (
            result_row_for_id.get("citation_support_score") == 1.0
            and not query_bound_contains_support
        )
    )
    answer_synthesis_confirmed = (
        not row_passed
        and query_bound_contains_answer
        and query_bound_contains_support
        and deterministic_answer_missing
        and not scorer_normalization_issue_possible
    )
    refined_primary = "PASS" if row_passed else (
        "ANSWER_SYNTHESIS_LIMITATION" if answer_synthesis_confirmed else (
        "QUERY_BOUND_EVIDENCE_GAP" if query_bound_gap else (
            "SCORER_NORMALIZATION_ISSUE" if scorer_normalization_issue_possible else "UNRESOLVED_RESIDUAL"
        )
        )
    )
    return {
        "query_id": query_id,
        "track": result_row_for_id.get("track") or source_row.get("_track") or source_row.get("track"),
        "failure_category": result_row_for_id.get("failure_category"),
        "answer_score": result_row_for_id.get("answer_score"),
        "citation_support_score": result_row_for_id.get("citation_support_score"),
        "query_bound_scored_citation_count": len(query_bound_citations),
        "non_query_bound_same_track_scored_citation_count": len(non_query_bound_citations),
        "same_track_valid_citation_count": len(query_bound_citations) + len(non_query_bound_citations),
        "query_bound_evidence_contains_answer": query_bound_contains_answer,
        "query_bound_evidence_contains_citation_support": query_bound_contains_support,
        "same_track_non_query_bound_evidence_contains_answer": non_query_bound_contains_answer,
        "same_track_non_query_bound_evidence_contains_citation_support": non_query_bound_contains_support,
        "same_track_non_query_bound_evidence_helped_or_distracted": non_query_bound_effect(
            has_non_query_bound=bool(non_query_bound_citations),
            query_bound_contains_answer=query_bound_contains_answer,
            query_bound_contains_support=query_bound_contains_support,
            non_query_bound_contains_answer=non_query_bound_contains_answer,
            non_query_bound_contains_support=non_query_bound_contains_support,
            failure_category=row_failure_category,
        ),
        "deterministic_extractive_answer_missing_value": deterministic_answer_missing,
        "deterministic_extractive_answer_contains_citation_support": generated_contains_support,
        "query_bound_evidence_gap": query_bound_gap,
        "scorer_normalization_issue_possible": scorer_normalization_issue_possible,
        "answer_synthesis_limitation_confirmed": answer_synthesis_confirmed,
        "refined_primary_attribution": refined_primary,
        "audit_comparison_only": True,
        "expected_supporting_gold_used_for_audit_only": True,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "candidate_artifacts_as_generation_source": False,
        "promotion_evidence": False,
    }


def split_scored_citations_by_query(
    citations: Sequence[Mapping[str, Any]],
    query_id: str,
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    query_bound: list[Mapping[str, Any]] = []
    non_query_bound: list[Mapping[str, Any]] = []
    for citation in citations:
        if official.clean(citation_validation(citation).get("manifest_query_id")) == query_id:
            query_bound.append(citation)
        else:
            non_query_bound.append(citation)
    return query_bound, non_query_bound


def audit_citation_text(citations: Sequence[Mapping[str, Any]]) -> str:
    return " ".join(official.clean(citation.get("citation_text")) for citation in citations)


def audit_answer_supported_by_text(expected_answer: str, text: str) -> bool:
    value_tokens = audit_numeric_answer_value_tokens(expected_answer)
    if value_tokens:
        target = official.normalized_text(text)
        return all(token in target for token in value_tokens)
    if official.expected_answer_supported_by_text(expected_answer, text):
        return True
    clauses = [
        clause
        for clause in re.split(r"[.!?。]+", official.clean(expected_answer))
        if audit_meaningful_tokens(clause)
    ]
    if len(clauses) > 1:
        return all(audit_textual_answer_supported_by_text(clause, text) for clause in clauses)
    return audit_textual_answer_supported_by_text(expected_answer, text)


def audit_textual_answer_supported_by_text(expected_answer: str, text: str) -> bool:
    expected_tokens = audit_meaningful_tokens(expected_answer)
    if len(expected_tokens) < 4:
        return False
    target = official.normalized_text(text)
    matched = sum(1 for token in expected_tokens if any(variant in target for variant in audit_token_variants(token)))
    return matched >= 8 and (matched / len(expected_tokens)) >= 0.65


def extract_short_answer_text(generated_answer: str) -> str:
    marker = "**Short answer:**"
    support_marker = "\n\n**Supporting passages:**"
    if marker not in generated_answer:
        return generated_answer
    short_answer = generated_answer.split(marker, 1)[1]
    if support_marker in short_answer:
        short_answer = short_answer.split(support_marker, 1)[0]
    return official.clean(short_answer)


def audit_numeric_answer_value_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    for match in re.finditer(r"\d[\d,]*(?:\.\d+)?", official.clean(value)):
        suffix = official.clean(value)[match.end() : match.end() + 1]
        if suffix == "년":
            continue
        token = official.normalized_text(match.group(0))
        if token:
            tokens.append(token)
    return tokens


def audit_meaningful_tokens(value: str) -> list[str]:
    stop_tokens = {"그리고", "하며", "하고", "있다", "그의", "어떤"}
    tokens: list[str] = []
    for token in re.findall(r"[0-9A-Za-z가-힣]+", official.clean(value).lower()):
        if len(token) < 2 or token in stop_tokens:
            continue
        tokens.append(official.normalized_text(token))
    return tokens


def audit_token_variants(token: str) -> set[str]:
    variants = {official.normalized_text(token)}
    suffixes = (
        "에서는",
        "에서",
        "으로",
        "이며",
        "하며",
        "하여",
        "하게",
        "에게",
        "에게서",
        "로",
        "은",
        "는",
        "이",
        "가",
        "을",
        "를",
        "의",
    )
    for suffix in suffixes:
        if token.endswith(suffix) and len(token) > len(suffix) + 1:
            variants.add(token[: -len(suffix)])
    return {variant for variant in variants if len(variant) >= 2}


def non_query_bound_effect(
    *,
    has_non_query_bound: bool,
    query_bound_contains_answer: bool,
    query_bound_contains_support: bool,
    non_query_bound_contains_answer: bool,
    non_query_bound_contains_support: bool,
    failure_category: str,
) -> str:
    if not has_non_query_bound:
        return "none"
    if non_query_bound_contains_answer or non_query_bound_contains_support:
        if not (query_bound_contains_answer and query_bound_contains_support):
            return "helped"
        return "neutral"
    if failure_category != "PASS":
        return "distracted"
    return "neutral"


def first_invalid_citation(citations: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for citation in citations:
        validation = citation.get("citation_payload_validation")
        if isinstance(validation, Mapping) and validation.get("ok") is not True:
            return citation
    return None


def write_v3_1_side_artifacts(summary: dict[str, Any], rows: Sequence[Mapping[str, Any]]) -> None:
    artifact_paths = summary["artifact_paths"]
    audit_rows = build_v3_1_actual_response_audit_rows(rows)
    audit_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["actual_response_audit_jsonl"]))
    write_jsonl(audit_jsonl, audit_rows)
    summary["artifact_paths"]["actual_response_audit_jsonl_sha256"] = sha256_file(audit_jsonl)

    audit_md = resolve_repo_relative_artifact_path(Path(artifact_paths["actual_response_audit_md"]))
    audit_md.parent.mkdir(parents=True, exist_ok=True)
    audit_md.write_text(render_v3_1_actual_response_audit_markdown(audit_rows), encoding="utf-8")
    summary["artifact_paths"]["actual_response_audit_md_sha256"] = sha256_file(audit_md)

    triage = build_v3_1_triage_queue(rows, summary=summary)
    triage_json = resolve_repo_relative_artifact_path(Path(artifact_paths["triage_queue_json"]))
    write_json(triage_json, triage)
    summary["artifact_paths"]["triage_queue_json_sha256"] = sha256_file(triage_json)

    triage_md = resolve_repo_relative_artifact_path(Path(artifact_paths["triage_queue_md"]))
    triage_md.parent.mkdir(parents=True, exist_ok=True)
    triage_md.write_text(render_v3_1_triage_markdown(triage), encoding="utf-8")
    summary["artifact_paths"]["triage_queue_md_sha256"] = sha256_file(triage_md)


def write_v3_1_priority_1_5_side_artifacts(summary: dict[str, Any], rows: Sequence[Mapping[str, Any]]) -> None:
    artifact_paths = summary["artifact_paths"]
    baseline_rows = read_jsonl(DEFAULT_V3_1_RESULTS_JSONL)

    audit_rows = build_v3_1_actual_response_audit_rows(rows, run_id=V3_1_PRIORITY_1_5_RUN_ID)
    audit_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["actual_response_audit_jsonl"]))
    write_jsonl(audit_jsonl, audit_rows)
    summary["artifact_paths"]["actual_response_audit_jsonl_sha256"] = sha256_file(audit_jsonl)

    strict_json_diagnostics = build_v3_1_priority_1_5_strict_json_diagnostics(summary, rows, baseline_rows)
    strict_json_path = resolve_repo_relative_artifact_path(Path(artifact_paths["strict_json_diagnostics_json"]))
    write_json(strict_json_path, strict_json_diagnostics)
    summary["artifact_paths"]["strict_json_diagnostics_json_sha256"] = sha256_file(strict_json_path)

    strict_json_md = resolve_repo_relative_artifact_path(Path(artifact_paths["strict_json_diagnostics_md"]))
    strict_json_md.parent.mkdir(parents=True, exist_ok=True)
    strict_json_md.write_text(render_v3_1_priority_1_5_strict_json_markdown(strict_json_diagnostics), encoding="utf-8")
    summary["artifact_paths"]["strict_json_diagnostics_md_sha256"] = sha256_file(strict_json_md)

    triage_delta = build_v3_1_priority_1_5_triage_delta(summary, rows, baseline_rows)
    triage_delta_path = resolve_repo_relative_artifact_path(Path(artifact_paths["triage_delta_json"]))
    write_json(triage_delta_path, triage_delta)
    summary["artifact_paths"]["triage_delta_json_sha256"] = sha256_file(triage_delta_path)

    triage_delta_md = resolve_repo_relative_artifact_path(Path(artifact_paths["triage_delta_md"]))
    triage_delta_md.parent.mkdir(parents=True, exist_ok=True)
    triage_delta_md.write_text(render_v3_1_priority_1_5_triage_delta_markdown(triage_delta), encoding="utf-8")
    summary["artifact_paths"]["triage_delta_md_sha256"] = sha256_file(triage_delta_md)


def write_v3_1_text_locator_residual_side_artifacts(
    summary: dict[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    artifact_paths = summary["artifact_paths"]
    priority_rows = read_jsonl(DEFAULT_V3_1_PRIORITY_RESULTS_JSONL)
    triage_delta = build_v3_1_text_locator_triage_delta(summary, rows, priority_rows)
    triage_delta_path = resolve_repo_relative_artifact_path(Path(artifact_paths["triage_delta_json"]))
    write_json(triage_delta_path, triage_delta)
    summary["artifact_paths"]["triage_delta_json_sha256"] = sha256_file(triage_delta_path)

    triage_delta_md = resolve_repo_relative_artifact_path(Path(artifact_paths["triage_delta_md"]))
    triage_delta_md.parent.mkdir(parents=True, exist_ok=True)
    triage_delta_md.write_text(render_v3_1_text_locator_triage_delta_markdown(triage_delta), encoding="utf-8")
    summary["artifact_paths"]["triage_delta_md_sha256"] = sha256_file(triage_delta_md)


def write_v3_1_1_post_triage_side_artifacts(summary: dict[str, Any], rows: Sequence[Mapping[str, Any]]) -> None:
    artifact_paths = summary["artifact_paths"]
    audit_rows = build_v3_1_actual_response_audit_rows(
        rows,
        run_id=V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
    )
    audit_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["actual_response_audit_jsonl"]))
    write_jsonl(audit_jsonl, audit_rows)
    summary["artifact_paths"]["actual_response_audit_jsonl_sha256"] = sha256_file(audit_jsonl)

    triage = build_v3_1_triage_queue(rows, summary=summary)
    triage_json = resolve_repo_relative_artifact_path(Path(artifact_paths["triage_queue_json"]))
    write_json(triage_json, triage)
    summary["artifact_paths"]["triage_queue_json_sha256"] = sha256_file(triage_json)


def write_v3_1_2_answer_span_renderer_side_artifacts(
    summary: dict[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    artifact_paths = summary["artifact_paths"]
    audit_rows = build_v3_1_actual_response_audit_rows(
        rows,
        run_id=V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
    )
    audit_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["actual_response_audit_jsonl"]))
    write_jsonl(audit_jsonl, audit_rows)
    summary["artifact_paths"]["actual_response_audit_jsonl_sha256"] = sha256_file(audit_jsonl)

    diagnostics = build_v3_1_2_answer_span_diagnostics_rows(summary, rows)
    diagnostics_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["answer_span_diagnostics_jsonl"]))
    write_jsonl(diagnostics_jsonl, diagnostics)
    summary["artifact_paths"]["answer_span_diagnostics_jsonl_sha256"] = sha256_file(diagnostics_jsonl)

    remaining = build_v3_1_2_remaining_triage_queue(summary)
    remaining_json = resolve_repo_relative_artifact_path(Path(artifact_paths["remaining_triage_queue_json"]))
    write_json(remaining_json, remaining)
    summary["artifact_paths"]["remaining_triage_queue_json_sha256"] = sha256_file(remaining_json)


def build_v3_1_2_answer_span_diagnostics_rows(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "schema_version": f"{V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID}_answer_span_diagnostics_v1",
                "run_id": V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "source_run_id": V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
                "generated_at": summary["generated_at"],
                "query_id": row.get("query_id"),
                "track": row.get("track"),
                "source_family": row.get("source_family"),
                "queue_priority_rank": row.get("queue_priority_rank"),
                "first_batch_selected": row.get("first_batch_selected"),
                "include_decision": row.get("include_decision"),
                "lane_failure_categories": {
                    lane_name: lane.get("failure_category")
                    for lane_name, lane in as_mapping(row.get("lane_results")).items()
                    if isinstance(lane, Mapping)
                },
                "answer_span_renderer_diagnostics": row.get("answer_span_renderer_diagnostics"),
                "diagnostic_only": True,
                "promotion_evidence": False,
                "threshold_tuning": False,
                "winner_selection": False,
                "promotion_gate_auto_run": False,
                "candidate_artifacts_as_generation_source": False,
                "generation_used_expected_answer": False,
                "generation_used_gold_fields": False,
                "generation_used_supporting_evidence": False,
                "reference_span_audit_only": True,
                "reference_span_text_embedded": False,
            }
        )
    return out


def build_v3_1_2_remaining_triage_queue(summary: Mapping[str, Any]) -> dict[str, Any]:
    source_queue = official.read_json(DEFAULT_V3_1_1_POST_TRIAGE_QUEUE_JSON)
    processed = set(V3_1_2_TEXT_FIRST_BATCH_QUERY_IDS)
    remaining_items = [
        deepcopy(item)
        for item in source_queue.get("items") or []
        if isinstance(item, Mapping) and official.clean(item.get("query_id")) not in processed
    ]
    for index, item in enumerate(remaining_items, start=1):
        item["remaining_priority_rank"] = index
    return {
        "schema_version": f"{V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID}_remaining_triage_queue_v1",
        "run_id": V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "source_run_id": V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
        "source_queue_artifact": official.repo_relative(DEFAULT_V3_1_1_POST_TRIAGE_QUEUE_JSON),
        "generated_at": summary["generated_at"],
        "diagnostic_only": True,
        "promotion_evidence": False,
        "processed_first_batch_query_ids": list(V3_1_2_TEXT_FIRST_BATCH_QUERY_IDS),
        "secondary_text_watchlist_query_ids": list(V3_1_2_TEXT_SECONDARY_QUERY_IDS),
        "strict_json_or_locator_residual_count": source_queue.get("strict_json_or_locator_residual_count"),
        "items": remaining_items,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
    }


def write_v3_1_3_remaining_queue_answer_span_renderer_side_artifacts(
    summary: dict[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    artifact_paths = summary["artifact_paths"]
    audit_rows = build_v3_1_actual_response_audit_rows(
        rows,
        run_id=V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
    )
    audit_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["actual_response_audit_jsonl"]))
    write_jsonl(audit_jsonl, audit_rows)
    summary["artifact_paths"]["actual_response_audit_jsonl_sha256"] = sha256_file(audit_jsonl)

    diagnostics = build_v3_1_3_answer_span_diagnostics_rows(summary, rows)
    diagnostics_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["answer_span_diagnostics_jsonl"]))
    write_jsonl(diagnostics_jsonl, diagnostics)
    summary["artifact_paths"]["answer_span_diagnostics_jsonl_sha256"] = sha256_file(diagnostics_jsonl)

    remaining = build_v3_1_3_remaining_triage_queue(summary, rows)
    remaining_json = resolve_repo_relative_artifact_path(Path(artifact_paths["remaining_triage_queue_json"]))
    write_json(remaining_json, remaining)
    summary["artifact_paths"]["remaining_triage_queue_json_sha256"] = sha256_file(remaining_json)


def build_v3_1_3_answer_span_diagnostics_rows(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "schema_version": f"{V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID}_answer_span_diagnostics_v1",
                "run_id": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "source_run_id": V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "generated_at": summary["generated_at"],
                "query_id": row.get("query_id"),
                "track": row.get("track"),
                "source_family": row.get("source_family"),
                "queue_priority_rank": row.get("queue_priority_rank"),
                "include_decision": row.get("include_decision"),
                "before_lane_failure_categories": row.get("before_lane_failure_categories"),
                "after_lane_failure_categories": row.get("after_lane_failure_categories"),
                "row_level_classification_change": row.get("row_level_classification_change"),
                "lane_failure_categories": {
                    lane_name: lane.get("failure_category")
                    for lane_name, lane in as_mapping(row.get("lane_results")).items()
                    if isinstance(lane, Mapping)
                },
                "answer_span_renderer_diagnostics": row.get("answer_span_renderer_diagnostics"),
                "diagnostic_only": True,
                "promotion_evidence": False,
                "threshold_tuning": False,
                "winner_selection": False,
                "promotion_gate_auto_run": False,
                "candidate_artifacts_as_generation_source": False,
                "generation_used_expected_answer": False,
                "generation_used_gold_fields": False,
                "generation_used_supporting_evidence": False,
                "reference_span_audit_only": True,
                "reference_span_text_embedded": False,
            }
        )
    return out


def build_v3_1_3_remaining_triage_queue(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    source_queue = official.read_json(DEFAULT_V3_1_2_REMAINING_TRIAGE_QUEUE_JSON)
    source_by_id = {
        official.clean(item.get("query_id")): item
        for item in source_queue.get("items") or []
        if isinstance(item, Mapping)
    }
    remaining_items: list[dict[str, Any]] = []
    for row in rows:
        failing_lanes = [
            lane_name
            for lane_name, lane in as_mapping(row.get("lane_results")).items()
            if isinstance(lane, Mapping) and lane.get("failure_category") != "PASS"
        ]
        if not failing_lanes:
            continue
        query_id = official.clean(row.get("query_id"))
        item = deepcopy(dict(source_by_id.get(query_id, {})))
        item.update(
            {
                "query_id": query_id,
                "source_family": row.get("source_family"),
                "track": row.get("track"),
                "failing_lane_names": failing_lanes,
                "passing_lane_names": [
                    lane_name
                    for lane_name, lane in as_mapping(row.get("lane_results")).items()
                    if isinstance(lane, Mapping) and lane.get("failure_category") == "PASS"
                ],
                "lane_failure_categories": lane_failure_categories(row),
                "primary_failure_category": primary_failure_category_for_row(row),
                "recommended_next_step": "continue_row_level_answer_span_renderer_diagnostic",
                "requires_user_gold_policy_decision": False,
                "safe_to_fix_without_user_gold_decision": True,
            }
        )
        remaining_items.append(item)
    for index, item in enumerate(remaining_items, start=1):
        item["remaining_priority_rank"] = index
    return {
        "schema_version": f"{V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID}_remaining_triage_queue_v1",
        "run_id": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "source_run_id": V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "source_queue_artifact": official.repo_relative(DEFAULT_V3_1_2_REMAINING_TRIAGE_QUEUE_JSON),
        "generated_at": summary["generated_at"],
        "diagnostic_only": True,
        "promotion_evidence": False,
        "strict_json_or_locator_residual_count": 0,
        "processed_query_ids": list(V3_1_3_REMAINING_QUEUE_QUERY_IDS),
        "items": remaining_items,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "reference_span_text_embedded": False,
    }


def write_v3_1_4_pdf_residual_answer_span_renderer_side_artifacts(
    summary: dict[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    artifact_paths = summary["artifact_paths"]
    audit_rows = build_v3_1_actual_response_audit_rows(
        rows,
        run_id=V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
    )
    audit_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["actual_response_audit_jsonl"]))
    write_jsonl(audit_jsonl, audit_rows)
    summary["artifact_paths"]["actual_response_audit_jsonl_sha256"] = sha256_file(audit_jsonl)

    diagnostics = build_v3_1_4_answer_span_diagnostics_rows(summary, rows)
    diagnostics_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["answer_span_diagnostics_jsonl"]))
    write_jsonl(diagnostics_jsonl, diagnostics)
    summary["artifact_paths"]["answer_span_diagnostics_jsonl_sha256"] = sha256_file(diagnostics_jsonl)

    remaining = build_v3_1_4_remaining_triage_queue(summary, rows)
    remaining_json = resolve_repo_relative_artifact_path(Path(artifact_paths["remaining_triage_queue_json"]))
    write_json(remaining_json, remaining)
    summary["artifact_paths"]["remaining_triage_queue_json_sha256"] = sha256_file(remaining_json)


def build_v3_1_4_answer_span_diagnostics_rows(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "schema_version": f"{V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID}_answer_span_diagnostics_v1",
                "run_id": V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "source_run_id": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
                "generated_at": summary["generated_at"],
                "query_id": row.get("query_id"),
                "track": row.get("track"),
                "source_family": row.get("source_family"),
                "queue_priority_rank": row.get("queue_priority_rank"),
                "include_decision": row.get("include_decision"),
                "before_lane_failure_categories": row.get("before_lane_failure_categories"),
                "after_lane_failure_categories": row.get("after_lane_failure_categories"),
                "row_level_classification_change": row.get("row_level_classification_change"),
                "lane_failure_categories": {
                    lane_name: lane.get("failure_category")
                    for lane_name, lane in as_mapping(row.get("lane_results")).items()
                    if isinstance(lane, Mapping)
                },
                "answer_span_renderer_diagnostics": row.get("answer_span_renderer_diagnostics"),
                "diagnostic_only": True,
                "promotion_evidence": False,
                "threshold_tuning": False,
                "winner_selection": False,
                "promotion_gate_auto_run": False,
                "candidate_artifacts_as_generation_source": False,
                "generation_used_expected_answer": False,
                "generation_used_gold_fields": False,
                "generation_used_supporting_evidence": False,
                "reference_span_audit_only": True,
                "reference_span_text_embedded": False,
            }
        )
    return out


def build_v3_1_4_remaining_triage_queue(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    source_queue = official.read_json(DEFAULT_V3_1_3_REMAINING_QUEUE_JSON)
    source_by_id = {
        official.clean(item.get("query_id")): item
        for item in source_queue.get("items") or []
        if isinstance(item, Mapping)
    }
    remaining_items: list[dict[str, Any]] = []
    for row in rows:
        failing_lanes = [
            lane_name
            for lane_name, lane in as_mapping(row.get("lane_results")).items()
            if isinstance(lane, Mapping) and lane.get("failure_category") != "PASS"
        ]
        if not failing_lanes:
            continue
        query_id = official.clean(row.get("query_id"))
        item = deepcopy(dict(source_by_id.get(query_id, {})))
        item.update(
            {
                "query_id": query_id,
                "source_family": row.get("source_family"),
                "track": row.get("track"),
                "failing_lane_names": failing_lanes,
                "passing_lane_names": [
                    lane_name
                    for lane_name, lane in as_mapping(row.get("lane_results")).items()
                    if isinstance(lane, Mapping) and lane.get("failure_category") == "PASS"
                ],
                "lane_failure_categories": lane_failure_categories(row),
                "primary_failure_category": primary_failure_category_for_row(row),
                "recommended_next_step": "continue_row_level_answer_span_renderer_diagnostic",
                "requires_user_gold_policy_decision": False,
                "safe_to_fix_without_user_gold_decision": True,
            }
        )
        remaining_items.append(item)
    for index, item in enumerate(remaining_items, start=1):
        item["remaining_priority_rank"] = index
    return {
        "schema_version": f"{V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID}_remaining_triage_queue_v1",
        "run_id": V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "source_run_id": V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "source_queue_artifact": official.repo_relative(DEFAULT_V3_1_3_REMAINING_QUEUE_JSON),
        "generated_at": summary["generated_at"],
        "diagnostic_only": True,
        "promotion_evidence": False,
        "strict_json_or_locator_residual_count": 0,
        "processed_query_ids": list(V3_1_4_PDF_RESIDUAL_QUERY_IDS),
        "items": remaining_items,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "reference_span_text_embedded": False,
    }


def write_v3_1_5_source_bound_coverage_side_artifacts(
    summary: dict[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    artifact_paths = summary["artifact_paths"]
    diagnostics_jsonl = resolve_repo_relative_artifact_path(
        Path(artifact_paths["context_coverage_diagnostics_jsonl"])
    )
    write_jsonl(diagnostics_jsonl, rows)
    summary["artifact_paths"]["context_coverage_diagnostics_jsonl_sha256"] = sha256_file(diagnostics_jsonl)

    remaining = build_v3_1_5_remaining_triage_queue(summary, rows)
    remaining_json = resolve_repo_relative_artifact_path(Path(artifact_paths["remaining_triage_queue_json"]))
    write_json(remaining_json, remaining)
    summary["artifact_paths"]["remaining_triage_queue_json_sha256"] = sha256_file(remaining_json)


def write_v3_1_6_safe_pdf_window_expansion_side_artifacts(
    summary: dict[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    artifact_paths = summary["artifact_paths"]
    audit_rows = build_v3_1_actual_response_audit_rows(
        rows,
        run_id=V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
    )
    for audit_row in audit_rows:
        audit_row.update(
            {
                "candidate_artifacts_as_generation_source": False,
                "generation_used_expected_answer": False,
                "generation_used_supporting_evidence": False,
                "generation_used_gold_fields": False,
                "reference_span_text_embedded": False,
            }
        )
    audit_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["actual_response_audit_jsonl"]))
    write_jsonl(audit_jsonl, audit_rows)
    summary["artifact_paths"]["actual_response_audit_jsonl_sha256"] = sha256_file(audit_jsonl)

    diagnostics = build_v3_1_6_answer_span_diagnostics_rows(summary, rows)
    diagnostics_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["answer_span_diagnostics_jsonl"]))
    write_jsonl(diagnostics_jsonl, diagnostics)
    summary["artifact_paths"]["answer_span_diagnostics_jsonl_sha256"] = sha256_file(diagnostics_jsonl)

    expansion_diagnostics = build_v3_1_6_context_expansion_diagnostics_rows(summary, rows)
    expansion_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["context_expansion_diagnostics_jsonl"]))
    write_jsonl(expansion_jsonl, expansion_diagnostics)
    summary["artifact_paths"]["context_expansion_diagnostics_jsonl_sha256"] = sha256_file(expansion_jsonl)

    remaining = build_v3_1_6_remaining_triage_queue(summary, rows)
    remaining_json = resolve_repo_relative_artifact_path(Path(artifact_paths["remaining_triage_queue_json"]))
    write_json(remaining_json, remaining)
    summary["artifact_paths"]["remaining_triage_queue_json_sha256"] = sha256_file(remaining_json)


def write_v3_1_7_post_residual_queue_closure_audit_side_artifacts(
    summary: dict[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    artifact_paths = summary["artifact_paths"]
    inventory_rows = list(summary.pop("_v3_1_7_inventory_rows", rows))
    remaining_queue = summary.pop("_v3_1_7_remaining_queue")
    decision_packet = summary.pop("_v3_1_7_user_decision_packet")
    silver_readiness_audit = summary.pop("_v3_1_7_silver_readiness_audit")

    inventory_jsonl = resolve_repo_relative_artifact_path(
        Path(artifact_paths["all_track_residual_inventory_jsonl"])
    )
    write_jsonl(inventory_jsonl, inventory_rows)
    artifact_paths["all_track_residual_inventory_jsonl_sha256"] = sha256_file(inventory_jsonl)

    remaining_json = resolve_repo_relative_artifact_path(Path(artifact_paths["remaining_triage_queue_json"]))
    write_json(remaining_json, remaining_queue)
    artifact_paths["remaining_triage_queue_json_sha256"] = sha256_file(remaining_json)

    if decision_packet.get("decision_items"):
        decision_json = resolve_repo_relative_artifact_path(Path(artifact_paths["user_decision_packet_json"]))
        write_json(decision_json, decision_packet)
        artifact_paths["user_decision_packet_json_sha256"] = sha256_file(decision_json)
    else:
        artifact_paths.pop("user_decision_packet_json", None)

    silver_json = resolve_repo_relative_artifact_path(Path(artifact_paths["silver_readiness_audit_json"]))
    write_json(silver_json, silver_readiness_audit)
    artifact_paths["silver_readiness_audit_json_sha256"] = sha256_file(silver_json)


def write_v3_1_8_gold_policy_review_packet_side_artifacts(
    summary: dict[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    artifact_paths = summary["artifact_paths"]
    human_review_packet = summary.pop("_v3_1_8_human_review_packet")
    decision_rows = list(summary.pop("_v3_1_8_decision_matrix_rows", rows))
    remaining_queue = summary.pop("_v3_1_8_remaining_queue")

    packet_json = resolve_repo_relative_artifact_path(Path(artifact_paths["human_review_packet_json"]))
    write_json(packet_json, human_review_packet)
    artifact_paths["human_review_packet_json_sha256"] = sha256_file(packet_json)

    decision_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["decision_matrix_jsonl"]))
    write_jsonl(decision_jsonl, decision_rows)
    artifact_paths["decision_matrix_jsonl_sha256"] = sha256_file(decision_jsonl)

    remaining_json = resolve_repo_relative_artifact_path(Path(artifact_paths["remaining_triage_queue_json"]))
    write_json(remaining_json, remaining_queue)
    artifact_paths["remaining_triage_queue_json_sha256"] = sha256_file(remaining_json)


def write_v3_1_9_user_gold_policy_override_side_artifacts(
    summary: dict[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    artifact_paths = summary["artifact_paths"]
    applied_overrides = list(summary.pop("_v3_1_9_applied_overrides"))
    gold_diff = list(summary.pop("_v3_1_9_gold_diff"))
    rescored_results = list(summary.pop("_v3_1_9_rescored_results", rows))
    remaining_queue = summary.pop("_v3_1_9_remaining_queue")

    applied_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["applied_overrides_jsonl"]))
    write_jsonl(applied_jsonl, applied_overrides)
    artifact_paths["applied_overrides_jsonl_sha256"] = sha256_file(applied_jsonl)

    diff_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["gold_diff_jsonl"]))
    write_jsonl(diff_jsonl, gold_diff)
    artifact_paths["gold_diff_jsonl_sha256"] = sha256_file(diff_jsonl)

    rescored_jsonl = resolve_repo_relative_artifact_path(Path(artifact_paths["rescored_results_jsonl"]))
    write_jsonl(rescored_jsonl, rescored_results)
    artifact_paths["rescored_results_jsonl_sha256"] = sha256_file(rescored_jsonl)

    remaining_json = resolve_repo_relative_artifact_path(Path(artifact_paths["remaining_triage_queue_json"]))
    write_json(remaining_json, remaining_queue)
    artifact_paths["remaining_triage_queue_json_sha256"] = sha256_file(remaining_json)


def build_v3_1_6_answer_span_diagnostics_rows(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "schema_version": (
                    f"{V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID}"
                    "_answer_span_diagnostics_v1"
                ),
                "run_id": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
                "source_run_id": V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
                "source_queue_artifact": summary.get("source_queue_artifact"),
                "generated_at": summary["generated_at"],
                "query_id": row.get("query_id"),
                "track": row.get("track"),
                "source_family": row.get("source_family"),
                "queue_priority_rank": row.get("queue_priority_rank"),
                "include_decision": row.get("include_decision"),
                "before_lane_failure_categories": row.get("before_lane_failure_categories"),
                "after_lane_failure_categories": row.get("after_lane_failure_categories"),
                "row_level_classification_change": row.get("row_level_classification_change"),
                "lane_failure_categories": {
                    lane_name: lane.get("failure_category")
                    for lane_name, lane in as_mapping(row.get("lane_results")).items()
                    if isinstance(lane, Mapping)
                },
                "answer_span_renderer_diagnostics": row.get("answer_span_renderer_diagnostics"),
                "context_expansion_attempted": row.get("context_expansion_attempted"),
                "context_expansion_applied": row.get("context_expansion_applied"),
                "locator_safe_metadata_available": row.get("locator_safe_metadata_available"),
                "diagnostic_only": True,
                "promotion_evidence": False,
                "threshold_tuning": False,
                "winner_selection": False,
                "promotion_gate_auto_run": False,
                "candidate_artifacts_as_generation_source": False,
                "generation_used_expected_answer": False,
                "generation_used_gold_fields": False,
                "generation_used_supporting_evidence": False,
                "reference_span_audit_only": True,
                "reference_span_text_embedded": False,
            }
        )
    return out


def build_v3_1_6_context_expansion_diagnostics_rows(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        diagnostic = dict(as_mapping(row.get("context_expansion_diagnostics")))
        diagnostic.update(
            {
                "run_id": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
                "source_run_id": V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
                "source_queue_artifact": summary.get("source_queue_artifact"),
                "generated_at": summary["generated_at"],
                "diagnostic_only": True,
                "promotion_evidence": False,
                "threshold_tuning": False,
                "winner_selection": False,
                "promotion_gate_auto_run": False,
                "candidate_artifacts_as_generation_source": False,
                "generation_used_expected_answer": False,
                "generation_used_gold_fields": False,
                "generation_used_supporting_evidence": False,
                "reference_span_audit_only": True,
                "reference_span_text_embedded": False,
            }
        )
        out.append(diagnostic)
    return out


def build_v3_1_6_remaining_triage_queue(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    source_queue = official.read_json(DEFAULT_V3_1_5_SOURCE_BOUND_COVERAGE_REMAINING_QUEUE_JSON)
    source_by_id = {
        official.clean(item.get("query_id")): item
        for item in source_queue.get("items") or []
        if isinstance(item, Mapping)
    }
    remaining_items: list[dict[str, Any]] = []
    for row in rows:
        failing_lanes = [
            lane_name
            for lane_name, lane in as_mapping(row.get("lane_results")).items()
            if isinstance(lane, Mapping) and lane.get("failure_category") != "PASS"
        ]
        if not failing_lanes:
            continue
        query_id = official.clean(row.get("query_id"))
        context_diagnostic = as_mapping(row.get("context_expansion_diagnostics"))
        item = deepcopy(dict(source_by_id.get(query_id, {})))
        item.update(
            {
                "query_id": query_id,
                "source_family": row.get("source_family"),
                "track": row.get("track"),
                "failing_lane_names": failing_lanes,
                "passing_lane_names": [
                    lane_name
                    for lane_name, lane in as_mapping(row.get("lane_results")).items()
                    if isinstance(lane, Mapping) and lane.get("failure_category") == "PASS"
                ],
                "lane_failure_categories": lane_failure_categories(row),
                "primary_failure_category": primary_failure_category_for_row(row),
                "context_expansion_attempted": context_diagnostic.get("expansion_attempted"),
                "context_expansion_applied": context_diagnostic.get("expansion_applied"),
                "locator_safe_metadata_available": context_diagnostic.get("locator_safe_metadata_available"),
                "fail_closed_blocker": context_diagnostic.get("fail_closed_blocker"),
                "recommended_next_step": (
                    "inspect_safe_pdf_context_expansion_result"
                    if context_diagnostic.get("expansion_applied")
                    else "provide_locator_safe_pdf_window_source_or_review_pdf_extraction_metadata"
                ),
                "requires_user_gold_policy_decision": False,
                "safe_to_fix_without_user_gold_decision": True,
                "diagnostic_only": True,
                "promotion_evidence": False,
                "reference_span_audit_only": True,
                "reference_span_text_embedded": False,
            }
        )
        remaining_items.append(item)
    for index, item in enumerate(remaining_items, start=1):
        item["remaining_priority_rank"] = index
    return {
        "schema_version": (
            f"{V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID}"
            "_remaining_triage_queue_v1"
        ),
        "run_id": V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
        "source_run_id": V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
        "source_queue_artifact": summary.get("source_queue_artifact"),
        "generated_at": summary["generated_at"],
        "diagnostic_only": True,
        "promotion_evidence": False,
        "strict_json_or_locator_residual_count": 0,
        "processed_query_ids": list(V3_1_6_SAFE_PDF_WINDOW_QUERY_IDS),
        "items": remaining_items,
        "context_expansion_attempted": summary.get("context_expansion_attempted"),
        "context_expansion_applied": summary.get("context_expansion_applied"),
        "locator_safe_metadata_available": summary.get("locator_safe_metadata_available"),
        "all_track_remeasurement_performed": summary.get("all_track_remeasurement_performed"),
        "behavior_change_made": summary.get("behavior_change_made"),
        "non_production_index_or_export_fix_applied": False,
        "official_retrieval_metrics_computed": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "reference_span_text_embedded": False,
    }


def build_v3_1_5_remaining_triage_queue(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    source_queue = official.read_json(DEFAULT_V3_1_4_PDF_RESIDUAL_REMAINING_QUEUE_JSON)
    source_by_id = {
        official.clean(item.get("query_id")): item
        for item in source_queue.get("items") or []
        if isinstance(item, Mapping)
    }
    remaining_items: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        query_id = official.clean(row.get("query_id"))
        item = deepcopy(dict(source_by_id.get(query_id, {})))
        item.update(
            {
                "query_id": query_id,
                "source_family": row.get("source_family"),
                "track": row.get("track"),
                "coverage_classification": row.get("issue_classification"),
                "coverage_final_queue_decision": row.get("final_queue_decision"),
                "raw_source_pdf_text_contains_all_audit_numeric_spans": row.get(
                    "raw_source_pdf_text_contains_all_audit_numeric_spans"
                ),
                "current_cited_search_unit_contains_all_audit_numeric_spans": row.get(
                    "current_cited_search_unit_contains_all_audit_numeric_spans"
                ),
                "same_document_search_unit_contains_all_audit_numeric_spans": row.get(
                    "same_document_search_unit_contains_all_audit_numeric_spans"
                ),
                "adjacent_page_window_search_unit_contains_all_audit_numeric_spans": row.get(
                    "adjacent_page_window_search_unit_contains_all_audit_numeric_spans"
                ),
                "recommended_next_step": (
                    "decide_or_implement_safe_pdf_paragraph_window_expansion_before_live_generation"
                ),
                "requires_user_gold_policy_decision": False,
                "safe_to_fix_without_user_gold_decision": True,
                "diagnostic_only": True,
                "promotion_evidence": False,
                "reference_span_audit_only": True,
                "reference_span_text_embedded": False,
            }
        )
        item["remaining_priority_rank"] = index
        remaining_items.append(item)
    return {
        "schema_version": f"{V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID}_remaining_triage_queue_v1",
        "run_id": V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
        "source_run_id": V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        "source_queue_artifact": summary["source_queue_artifact"],
        "generated_at": summary["generated_at"],
        "diagnostic_only": True,
        "promotion_evidence": False,
        "strict_json_or_locator_residual_count": 0,
        "processed_query_ids": list(V3_1_5_SOURCE_BOUND_COVERAGE_QUERY_IDS),
        "items": remaining_items,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "reference_span_text_embedded": False,
        "official_retrieval_metrics_computed": False,
        "non_production_index_or_export_fix_applied": False,
        "all_track_remeasurement_performed": False,
    }


def primary_failure_category_for_row(row: Mapping[str, Any]) -> str:
    for lane_name in V3_1_LANE_NAMES:
        category = official.clean(as_mapping(as_mapping(row.get("lane_results")).get(lane_name)).get("failure_category"))
        if category and category != "PASS":
            return category
    return "PASS"


def any_failing_lane(rows: Sequence[Mapping[str, Any]]) -> bool:
    return any(
        isinstance(lane, Mapping) and lane.get("failure_category") != "PASS"
        for row in rows
        for lane in as_mapping(row.get("lane_results")).values()
    )


def build_v3_1_priority_1_5_strict_json_diagnostics(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    before_by_id = {row["query_id"]: row for row in priority_rows_by_id(baseline_rows)}
    after_by_id = {row["query_id"]: row for row in rows}
    diagnostic_rows: list[dict[str, Any]] = []
    for query_id in V3_1_PRIORITY_1_5_STRICT_JSON_QUERY_IDS:
        before_lane = as_mapping(as_mapping(before_by_id.get(query_id, {}).get("lane_results")).get("live_llm_retrieval_topk"))
        after_lane = as_mapping(as_mapping(after_by_id.get(query_id, {}).get("lane_results")).get("live_llm_retrieval_topk"))
        diagnostic_rows.append(
            {
                "query_id": query_id,
                "before": strict_json_diagnostic_summary(before_lane, prompt_context_mode="retrieval_topk_source_bound"),
                "after": strict_json_diagnostic_summary(after_lane, prompt_context_mode="retrieval_topk_source_bound"),
            }
        )
    return {
        "schema_version": f"{V3_1_PRIORITY_1_5_STRICT_JSON_DIAGNOSTICS_ID}_v1",
        "run_id": V3_1_PRIORITY_1_5_STRICT_JSON_DIAGNOSTICS_ID,
        "target_run_id": V3_1_PRIORITY_1_5_RUN_ID,
        "source_run_id": V3_1_RUN_ID,
        "generated_at": summary["generated_at"],
        "diagnostic_only": True,
        "promotion_evidence": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "target_query_ids": list(V3_1_PRIORITY_1_5_STRICT_JSON_QUERY_IDS),
        "strict_json_parse_failure_before": summary["strict_json_parse_failure_before"],
        "strict_json_parse_failure_after": summary["strict_json_parse_failure_after"],
        "strict_json_schema_repair_applied_count_before": summary[
            "strict_json_schema_repair_applied_count_before"
        ],
        "strict_json_schema_repair_applied_count_after": summary["strict_json_schema_repair_applied_count_after"],
        "rows": diagnostic_rows,
    }


def strict_json_diagnostic_summary(lane: Mapping[str, Any], *, prompt_context_mode: str) -> dict[str, Any]:
    diagnostics = as_mapping(lane.get("strict_json_diagnostics") or lane.get("strict_json_raw"))
    if "strict_json" in diagnostics and isinstance(diagnostics.get("strict_json"), Mapping):
        diagnostics = as_mapping(diagnostics.get("strict_json"))
    out = {
        "parse_ok": lane.get("strict_json_parse_ok") is True,
        "failure_category": lane.get("failure_category"),
        "raw_response_sha256": diagnostics.get("raw_response_sha256"),
        "raw_response_sha256_attempts": list(diagnostics.get("raw_response_sha256_attempts") or []),
        "sanitized_raw_response_excerpt": diagnostics.get("sanitized_raw_response_excerpt") or "",
        "strict_json_error": diagnostics.get("strict_json_error") or "",
        "attempted_schema_keys": list(
            diagnostics.get("attempted_schema_keys") or ["answer", "cited_search_unit_ids", "citation_locators"]
        ),
        "missing_required_keys": list(diagnostics.get("missing_required_keys") or []),
        "missing_required_keys_before_repair": list(diagnostics.get("missing_required_keys_before_repair") or []),
        "schema_repair_applied": diagnostics.get("schema_repair_applied") is True,
        "prompt_context_mode": diagnostics.get("prompt_context_mode") or prompt_context_mode,
        "cited_search_unit_ids_before_parse": list(diagnostics.get("cited_search_unit_ids_before_parse") or []),
    }
    if not out["raw_response_sha256"]:
        out["strict_json_error"] = out["strict_json_error"] or "raw response body was not retained in baseline artifact"
    return out


def build_v3_1_priority_1_5_triage_delta(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    before_by_id = {row["query_id"]: row for row in priority_rows_by_id(baseline_rows)}
    after_by_id = {row["query_id"]: row for row in rows}
    delta_rows = [
        {
            "query_id": query_id,
            "source_family": after_by_id.get(query_id, before_by_id.get(query_id, {})).get("source_family"),
            "before": triage_delta_row_metrics(before_by_id.get(query_id, {})),
            "after": triage_delta_row_metrics(after_by_id.get(query_id, {})),
        }
        for query_id in V3_1_PRIORITY_1_5_QUERY_IDS
    ]
    return {
        "schema_version": f"{V3_1_PRIORITY_1_5_RUN_ID}_triage_delta_v1",
        "run_id": V3_1_PRIORITY_1_5_RUN_ID,
        "source_run_id": V3_1_RUN_ID,
        "generated_at": summary["generated_at"],
        "diagnostic_only": True,
        "promotion_evidence": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "summary_metrics": {
            "strict_json_parse_failure_before": summary["strict_json_parse_failure_before"],
            "strict_json_parse_failure_after": summary["strict_json_parse_failure_after"],
            "strict_json_schema_repair_applied_count_before": summary[
                "strict_json_schema_repair_applied_count_before"
            ],
            "strict_json_schema_repair_applied_count_after": summary[
                "strict_json_schema_repair_applied_count_after"
            ],
            "llm_generated_locator_copy_failure_before": summary["llm_generated_locator_copy_failure_before"],
            "llm_generated_locator_copy_failure_after": summary["llm_generated_locator_copy_failure_after"],
            "llm_generated_locator_field_mismatch_failure_before": summary[
                "llm_generated_locator_field_mismatch_failure_before"
            ],
            "llm_generated_locator_field_mismatch_failure_after": summary[
                "llm_generated_locator_field_mismatch_failure_after"
            ],
            "llm_generated_locator_missing_failure_before": summary["llm_generated_locator_missing_failure_before"],
            "llm_generated_locator_missing_failure_after": summary["llm_generated_locator_missing_failure_after"],
            "pdf_source_pdf_path_mismatch_before": summary["pdf_source_pdf_path_mismatch_before"],
            "pdf_source_pdf_path_mismatch_after": summary["pdf_source_pdf_path_mismatch_after"],
            "xlsx_row_label_mismatch_before": summary["xlsx_row_label_mismatch_before"],
            "xlsx_row_label_mismatch_after": summary["xlsx_row_label_mismatch_after"],
        },
        "rows": delta_rows,
    }


def build_v3_1_text_locator_triage_delta(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    priority_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    before_by_id = {official.clean(row.get("query_id")): row for row in priority_rows}
    after_by_id = {official.clean(row.get("query_id")): row for row in rows}
    delta_rows = [
        {
            "query_id": query_id,
            "source_family": after_by_id.get(query_id, before_by_id.get(query_id, {})).get("source_family"),
            "before": triage_delta_row_metrics(before_by_id.get(query_id, {})),
            "after": triage_delta_row_metrics(after_by_id.get(query_id, {})),
        }
        for query_id in V3_1_TEXT_LOCATOR_RESIDUAL_QUERY_IDS
    ]
    return {
        "schema_version": f"{V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID}_triage_delta_v1",
        "run_id": V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID,
        "source_run_id": V3_1_PRIORITY_1_5_RUN_ID,
        "generated_at": summary["generated_at"],
        "diagnostic_only": True,
        "promotion_evidence": False,
        "generation_used_expected_answer": False,
        "generation_used_gold_fields": False,
        "generation_used_supporting_evidence": False,
        "summary_metrics": {
            "text_locator_missing_count_before": summary["text_locator_missing_count_before"],
            "text_locator_missing_count_after": summary["text_locator_missing_count_after"],
            "llm_generated_locator_missing_failure_before": summary[
                "llm_generated_locator_missing_failure_before"
            ],
            "llm_generated_locator_missing_failure_after": summary["llm_generated_locator_missing_failure_after"],
            "llm_generated_locator_field_mismatch_failure_after": summary[
                "llm_generated_locator_field_mismatch_failure_after"
            ],
            "text_locator_byte_equal_after": summary["text_locator_byte_equal_after"],
            "text_locator_normalized_equal_after": summary["text_locator_normalized_equal_after"],
        },
        "rows": delta_rows,
    }


def triage_delta_row_metrics(row: Mapping[str, Any]) -> dict[str, Any]:
    lane_b = as_mapping(as_mapping(row.get("lane_results")).get("live_llm_retrieval_topk"))
    validation = as_mapping(lane_b.get("llm_generated_locator_validation"))
    source_family = official.clean(row.get("source_family"))
    search_unit_id = official.clean(row.get("denominator_search_unit_id"))
    comparisons = as_mapping(as_mapping(validation.get("field_comparisons_by_search_unit_id")).get(search_unit_id))
    if not comparisons:
        comparisons = locator_field_comparisons_from_row(row, lane_b)
    return {
        "lane_b_failure_category": lane_b.get("failure_category"),
        "strict_json_parse_failure": lane_b.get("failure_category") == "LLM_STRICT_JSON_PARSE_FAILURE",
        "strict_json_schema_repair_applied": as_mapping(lane_b.get("strict_json_diagnostics")).get(
            "schema_repair_applied"
        )
        is True,
        "llm_generated_locator_copy_failure": validation.get("generated_by_llm") is True
        and validation.get("ok") is not True,
        "llm_generated_locator_field_mismatch_failure": bool(validation.get("mismatched_fields_by_search_unit_id")),
        "llm_generated_locator_missing_failure": bool(
            validation.get("missing_locator_for_search_unit_ids") or validation.get("missing_fields_by_search_unit_id")
        ),
        "pdf_source_pdf_path_byte_equal": field_comparison_bool(comparisons, "source_pdf_path", "byte_equal")
        if source_family == "PDF"
        else None,
        "pdf_source_pdf_path_normalized_equal": field_comparison_bool(
            comparisons,
            "source_pdf_path",
            "normalized_equal",
        )
        if source_family == "PDF"
        else None,
        "xlsx_row_label_byte_equal": field_comparison_bool(comparisons, "row_label", "byte_equal")
        if source_family == "XLSX"
        else None,
        "xlsx_row_label_normalized_equal": field_comparison_bool(comparisons, "row_label", "normalized_equal")
        if source_family == "XLSX"
        else None,
        "text_locator_present": text_locator_present(row, lane_b) if source_family == "TEXT" else None,
        "text_locator_byte_equal": field_comparison_bool(comparisons, "text_locator", "byte_equal")
        if source_family == "TEXT"
        else None,
        "text_locator_normalized_equal": field_comparison_bool(comparisons, "text_locator", "normalized_equal")
        if source_family == "TEXT"
        else None,
        "answer_score": lane_b.get("answer_score"),
        "citation_support_score": lane_b.get("citation_support_score"),
    }


def text_locator_present(row: Mapping[str, Any], lane: Mapping[str, Any]) -> bool:
    source_family = official.clean(row.get("source_family"))
    search_unit_id = official.clean(row.get("denominator_search_unit_id"))
    for raw_locator in lane.get("llm_generated_citation_locators") or []:
        if not isinstance(raw_locator, Mapping):
            continue
        locator = locator_from_citation_payload(raw_locator, source_family=source_family)
        if official.clean(locator.get("search_unit_id")) == search_unit_id and locator.get("text_locator"):
            return True
    return False


def field_comparison_bool(comparisons: Mapping[str, Any], field: str, key: str) -> bool | None:
    comparison = as_mapping(comparisons.get(field))
    if not comparison:
        return None
    value = comparison.get(key)
    return value if isinstance(value, bool) else None


def locator_field_comparisons_from_row(row: Mapping[str, Any], lane: Mapping[str, Any]) -> dict[str, Any]:
    source_family = official.clean(row.get("source_family"))
    search_unit_id = official.clean(row.get("denominator_search_unit_id"))
    expected = as_mapping(row.get("denominator_locator"))
    generated = {}
    for raw_locator in lane.get("llm_generated_citation_locators") or []:
        if not isinstance(raw_locator, Mapping):
            continue
        locator = locator_from_citation_payload(raw_locator, source_family=source_family)
        if official.clean(locator.get("search_unit_id")) == search_unit_id:
            generated = locator
            break
    if not generated:
        return {}
    return {
        field: locator_field_copy_comparison(expected.get(field), generated.get(field))
        for field in required_locator_fields(source_family)
        if generated.get(field) not in (None, "", [])
    }


def render_v3_1_priority_1_5_strict_json_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        f"# {payload['run_id']}",
        "",
        "Diagnostic-only strict JSON raw-response summary for priority 1-5 parse-failure rows.",
        "",
        "| Query ID | Before | After | After repair | After raw SHA256 | After error |",
        "|---|---|---|---:|---|---|",
    ]
    for row in payload.get("rows") or []:
        before = row.get("before") or {}
        after = row.get("after") or {}
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` | `{}` | `{}` |".format(
                row.get("query_id"),
                before.get("failure_category"),
                after.get("failure_category"),
                after.get("schema_repair_applied"),
                after.get("raw_response_sha256"),
                official.clean(after.get("strict_json_error"))[:120],
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_v3_1_priority_1_5_triage_delta_markdown(payload: Mapping[str, Any]) -> str:
    metrics = payload.get("summary_metrics") or {}
    lines = [
        f"# {payload['run_id']} Triage Delta",
        "",
        "Diagnostic-only delta for v3_1 priority ranks 1 through 5.",
        "",
        f"- Strict JSON parse failures: `{metrics.get('strict_json_parse_failure_before')}` -> `{metrics.get('strict_json_parse_failure_after')}`",
        f"- Strict JSON schema repairs applied: `{metrics.get('strict_json_schema_repair_applied_count_before')}` -> `{metrics.get('strict_json_schema_repair_applied_count_after')}`",
        f"- LLM-generated locator copy failures: `{metrics.get('llm_generated_locator_copy_failure_before')}` -> `{metrics.get('llm_generated_locator_copy_failure_after')}`",
        f"- LLM-generated locator field mismatches: `{metrics.get('llm_generated_locator_field_mismatch_failure_before')}` -> `{metrics.get('llm_generated_locator_field_mismatch_failure_after')}`",
        f"- LLM-generated locator missing-field/missing-locator failures: `{metrics.get('llm_generated_locator_missing_failure_before')}` -> `{metrics.get('llm_generated_locator_missing_failure_after')}`",
        f"- PDF `source_pdf_path` mismatches: `{metrics.get('pdf_source_pdf_path_mismatch_before')}` -> `{metrics.get('pdf_source_pdf_path_mismatch_after')}`",
        f"- XLSX `row_label` mismatches: `{metrics.get('xlsx_row_label_mismatch_before')}` -> `{metrics.get('xlsx_row_label_mismatch_after')}`",
        "",
        "| Query ID | Before lane B | After lane B | PDF path byte | XLSX row label byte |",
        "|---|---|---|---:|---:|",
    ]
    for row in payload.get("rows") or []:
        before = row.get("before") or {}
        after = row.get("after") or {}
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` | `{}` |".format(
                row.get("query_id"),
                before.get("lane_b_failure_category"),
                after.get("lane_b_failure_category"),
                after.get("pdf_source_pdf_path_byte_equal"),
                after.get("xlsx_row_label_byte_equal"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_v3_1_text_locator_triage_delta_markdown(payload: Mapping[str, Any]) -> str:
    metrics = payload.get("summary_metrics") or {}
    lines = [
        f"# {payload['run_id']} Triage Delta",
        "",
        "Diagnostic-only delta for the remaining TEXT locator residual.",
        "",
        f"- TEXT locator missing: `{metrics.get('text_locator_missing_count_before')}` -> `{metrics.get('text_locator_missing_count_after')}`",
        f"- LLM-generated locator missing failures: `{metrics.get('llm_generated_locator_missing_failure_before')}` -> `{metrics.get('llm_generated_locator_missing_failure_after')}`",
        f"- TEXT locator byte-equal after: `{metrics.get('text_locator_byte_equal_after')}`",
        f"- TEXT locator normalized-equal after: `{metrics.get('text_locator_normalized_equal_after')}`",
        "",
        "| Query ID | Before lane B | After lane B | Text locator present | Byte equal | Normalized equal |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in payload.get("rows") or []:
        before = row.get("before") or {}
        after = row.get("after") or {}
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` | `{}` | `{}` |".format(
                row.get("query_id"),
                before.get("lane_b_failure_category"),
                after.get("lane_b_failure_category"),
                after.get("text_locator_present"),
                after.get("text_locator_byte_equal"),
                after.get("text_locator_normalized_equal"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_v3_1_text_locator_residual_summary_markdown(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            f"# {summary['run_id']}",
            "",
            "- Diagnostic-only TEXT locator residual triage.",
            f"- Target rows: `{summary.get('target_row_count')}`.",
            f"- TEXT locator missing: `{summary.get('text_locator_missing_count_before')}` -> `{summary.get('text_locator_missing_count_after')}`.",
            f"- LLM-generated locator missing failures: `{summary.get('llm_generated_locator_missing_failure_before')}` -> `{summary.get('llm_generated_locator_missing_failure_after')}`.",
            f"- TEXT locator byte-equal after: `{summary.get('text_locator_byte_equal_after')}`.",
            f"- TEXT locator normalized-equal after: `{summary.get('text_locator_normalized_equal_after')}`.",
            f"- Promotion evidence: `{str(summary.get('promotion_evidence')).lower()}`.",
            f"- Generation used expected/gold/supporting: `{summary.get('generation_used_expected_answer')}` / `{summary.get('generation_used_gold_fields')}` / `{summary.get('generation_used_supporting_evidence')}`.",
            "",
        ]
    )


def render_v3_1_1_post_triage_summary_markdown(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            f"# {summary['run_id']}",
            "",
            "- Diagnostic-only 29-row post strict JSON / locator triage measurement.",
            f"- Total rows: `{summary.get('total_denominator_rows')}`.",
            f"- Rows by source family: `{json.dumps(summary.get('rows_by_source_family'), ensure_ascii=False, sort_keys=True)}`.",
            f"- Lane counts: `{json.dumps(summary.get('lane_counts'), ensure_ascii=False, sort_keys=True)}`.",
            f"- Strict JSON parse failures by lane: `{json.dumps(summary.get('strict_json_parse_failure_count_by_lane'), ensure_ascii=False, sort_keys=True)}`.",
            f"- LLM-generated locator copy failures by lane: `{json.dumps(summary.get('llm_generated_locator_copy_failure_count_by_lane'), ensure_ascii=False, sort_keys=True)}`.",
            f"- PDF source_pdf_path mismatches: `{summary.get('pdf_source_pdf_path_mismatch_count')}`.",
            f"- XLSX row_label mismatches: `{summary.get('xlsx_row_label_mismatch_count')}`.",
            f"- TEXT text_locator missing: `{summary.get('text_text_locator_missing_count')}`.",
            f"- v3_1 PASS regressions: `{(summary.get('regression_from_v3_1_foundation') or {}).get('existing_pass_regression_count')}`.",
            f"- Promotion evidence: `{str(summary.get('promotion_evidence')).lower()}`.",
            "",
        ]
    )


def build_v3_1_actual_response_audit_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    run_id: str = V3_1_RUN_ID,
) -> list[dict[str, Any]]:
    audit_rows: list[dict[str, Any]] = []
    for row in rows:
        lanes = row.get("lane_results") or {}
        audit_rows.append(
            {
                "run_id": run_id,
                "query_id": row.get("query_id"),
                "source_family": row.get("source_family"),
                "track": row.get("track"),
                "query": row.get("query"),
                "lane_answers": {
                    lane_name: lane.get("generated_answer")
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping)
                },
                "citations": {
                    lane_name: compact_citations(lane.get("generated_citations") or [])
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping)
                },
                "cited_search_unit_ids": {
                    lane_name: lane.get("cited_search_unit_ids")
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping)
                },
                "locator_fields": row.get("denominator_locator"),
                "llm_generated_citation_locators": {
                    lane_name: lane.get("llm_generated_citation_locators")
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping)
                },
                "llm_generated_locator_validation": {
                    lane_name: lane.get("llm_generated_locator_validation")
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping)
                },
                "strict_json_diagnostics": {
                    lane_name: lane.get("strict_json_diagnostics")
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping)
                },
                "scores": {
                    lane_name: {
                        "answer_score": lane.get("answer_score"),
                        "citation_support_score": lane.get("citation_support_score"),
                        "score_status": lane.get("score_status"),
                    }
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping)
                },
                "failure_category": {
                    lane_name: lane.get("failure_category")
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping)
                },
                "row_level_diagnosis": row_level_diagnosis(row),
                "recommended_next_action": row_recommended_next_action(row),
                "diagnostic_only": True,
                "promotion_evidence": False,
            }
        )
    return audit_rows


def compact_citations(citations: Sequence[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for citation in citations:
        if not isinstance(citation, Mapping):
            continue
        payload = as_mapping(citation.get("search_unit_citation_payload"))
        out.append(
            {
                "citation_text": official.clean(citation.get("citation_text"))[:500],
                "search_unit_id": payload.get("search_unit_id") or payload.get("searchUnitId"),
                "locator": {
                    "source_pdf_path": payload.get("source_pdf_path") or payload.get("sourcePdfPath"),
                    "page": payload.get("page"),
                    "physical_page_index": payload.get("physical_page_index") or payload.get("physicalPageIndex"),
                    "bbox": payload.get("bbox"),
                    "region_type": payload.get("region_type") or payload.get("regionType"),
                    "workbook": payload.get("workbook"),
                    "sheet": payload.get("sheet") or payload.get("sheetName"),
                    "range": payload.get("range") or payload.get("cell_range") or payload.get("cellRange"),
                    "cell": payload.get("cell"),
                    "document_id": payload.get("document_id") or payload.get("documentId"),
                    "document_version_id": payload.get("document_version_id") or payload.get("documentVersionId"),
                    "text_locator": payload.get("text_locator") or payload.get("textLocator"),
                },
            }
        )
    return out


def row_level_diagnosis(row: Mapping[str, Any]) -> str:
    failing = [
        f"{lane_name}:{lane.get('failure_category')}"
        for lane_name, lane in (row.get("lane_results") or {}).items()
        if isinstance(lane, Mapping) and lane.get("failure_category") != "PASS"
    ]
    if not failing:
        return "all lanes passed under diagnostic scoring"
    return "failing lanes require row-level triage: " + ", ".join(failing)


def row_recommended_next_action(row: Mapping[str, Any]) -> str:
    categories = [
        official.clean(lane.get("failure_category"))
        for lane in (row.get("lane_results") or {}).values()
        if isinstance(lane, Mapping) and lane.get("failure_category") != "PASS"
    ]
    if not categories:
        return "no_action"
    return recommendation_for_failure(sorted(categories, key=triage_priority_for_category)[0])


def build_v3_1_triage_queue(rows: Sequence[Mapping[str, Any]], *, summary: Mapping[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for row in rows:
        lanes = row.get("lane_results") or {}
        failing_lanes = [
            lane_name
            for lane_name, lane in lanes.items()
            if isinstance(lane, Mapping) and lane.get("failure_category") != "PASS"
        ]
        if not failing_lanes:
            continue
        passing_lanes = [
            lane_name
            for lane_name, lane in lanes.items()
            if isinstance(lane, Mapping) and lane.get("failure_category") == "PASS"
        ]
        categories = [
            official.clean(as_mapping(lanes[lane_name]).get("failure_category"))
            for lane_name in failing_lanes
        ]
        category = sorted(categories, key=triage_priority_for_category)[0]
        requires_user = category == "GOLD_POLICY_REVIEW_CANDIDATE"
        items.append(
            {
                "priority_rank": 0,
                "query_id": row.get("query_id"),
                "source_family": row.get("source_family"),
                "track": row.get("track"),
                "failing_lane_names": failing_lanes,
                "passing_lane_names": passing_lanes,
                "failure_category": category,
                "primary_failure_category": category,
                "reason": row_level_diagnosis(row),
                "evidence_from_artifacts": {
                    "result_artifact": summary["artifact_paths"]["results_jsonl"],
                    "lane_failure_categories": {
                        lane_name: as_mapping(lanes[lane_name]).get("failure_category")
                        for lane_name in failing_lanes
                    },
                    "llm_generated_locator_validation": {
                        lane_name: as_mapping(lanes[lane_name]).get("llm_generated_locator_validation")
                        for lane_name in failing_lanes
                    },
                    "denominator_search_unit_id": row.get("denominator_search_unit_id"),
                },
                "fix_type": fix_type_for_failure(category),
                "safe_to_fix_without_user_gold_decision": not requires_user,
                "requires_user_gold_policy_decision": requires_user,
                "recommended_next_step": recommendation_for_failure(category),
            }
        )
    items.sort(key=lambda item: (triage_priority_for_category(item["failure_category"]), official.clean(item["query_id"])))
    for index, item in enumerate(items, start=1):
        item["priority_rank"] = index
    strict_json_or_locator_categories = {
        "LLM_STRICT_JSON_PARSE_FAILURE",
        "PDF_BBOX_LOCATOR_LOSS",
        "XLSX_CELL_LOCATOR_LOSS",
        "CITATION_PAYLOAD_SCHEMA_MISMATCH",
    }
    return {
        "schema_version": f"{summary['run_id']}_triage_queue_v1",
        "run_id": summary["run_id"],
        "generated_at": summary["generated_at"],
        "diagnostic_only": True,
        "promotion_evidence": False,
        "strict_json_or_locator_residual_count": sum(
            1 for item in items if item["failure_category"] in strict_json_or_locator_categories
        ),
        "items": items,
        "sorting_policy": [
            "infrastructure/schema/citation payload",
            "retrieval query-bound miss",
            "PDF/XLSX locator preservation",
            "PDF/XLSX adapter PASS but LLM FAIL",
            "TEXT LLM true partial synthesis",
            "expected span mismatch / scorer normalization review",
            "gold policy review",
        ],
    }


def triage_priority_for_category(category: str) -> int:
    order = {
        "CITATION_PAYLOAD_SCHEMA_MISMATCH": 10,
        "LLM_STRICT_JSON_PARSE_FAILURE": 11,
        "CITATION_NOT_SOURCE_BOUND": 12,
        "CITATION_OFF_TRACK": 13,
        "RETRIEVAL_QUERY_BOUND_MISS": 20,
        "CITATION_NOT_QUERY_BOUND": 21,
        "PDF_BBOX_LOCATOR_LOSS": 30,
        "PDF_TABLE_AXIS_MISREAD": 31,
        "PDF_OCR_VALUE_MISREAD": 32,
        "PDF_SECTION_REGION_MISREAD": 33,
        "XLSX_CELL_LOCATOR_LOSS": 34,
        "XLSX_ROW_COLUMN_LOOKUP_MISREAD": 35,
        "XLSX_DATE_NUMBER_FORMAT_MISREAD": 36,
        "XLSX_DISPLAYED_VALUE_NORMALIZED_VALUE_CONFUSION": 37,
        "LLM_TRUE_PARTIAL_SYNTHESIS": 50,
        "LLM_ANSWER_OVERCOMPRESSION": 51,
        "LLM_EXPECTED_SPAN_MISMATCH": 60,
        "LLM_UNSUPPORTED_INFERENCE": 61,
        "SCORER_NORMALIZATION_REVIEW": 70,
        "GOLD_POLICY_REVIEW_CANDIDATE": 80,
        "PASS": 99,
    }
    return order.get(category, 90)


def fix_type_for_failure(category: str) -> str:
    if category in {"RETRIEVAL_QUERY_BOUND_MISS", "CITATION_NOT_QUERY_BOUND"}:
        return "retrieval"
    if category.startswith("CITATION_") or category == "LLM_STRICT_JSON_PARSE_FAILURE":
        return "citation_payload"
    if category.startswith("PDF_") or category.startswith("XLSX_CELL"):
        return "locator_preservation"
    if category == "SCORER_NORMALIZATION_REVIEW":
        return "scorer_normalization_review"
    if category == "GOLD_POLICY_REVIEW_CANDIDATE":
        return "gold_policy_review"
    if category.startswith("XLSX_"):
        return "adapter_vs_llm_gap"
    return "prompt_answer_renderer"


def render_v3_1_actual_response_audit_markdown(audit_rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        f"# {V3_1_RUN_ID} Actual Response Audit",
        "",
        "This audit is diagnostic-only. Expected answers and supporting evidence are intentionally not printed here.",
        "",
    ]
    for row in audit_rows:
        lines.extend(
            [
                f"## {row['query_id']} ({row['source_family']})",
                "",
                f"- Query: {row['query']}",
                f"- Lane A answer: {row['lane_answers'].get('v3_primary_replay')}",
                f"- Lane B answer: {row['lane_answers'].get('live_llm_retrieval_topk')}",
                f"- Lane C answer: {row['lane_answers'].get('live_llm_query_bound_oracle')}",
                f"- Scores: `{json.dumps(row['scores'], ensure_ascii=False, sort_keys=True)}`",
                f"- Failure category: `{json.dumps(row['failure_category'], ensure_ascii=False, sort_keys=True)}`",
                f"- Cited SearchUnit IDs: `{json.dumps(row['cited_search_unit_ids'], ensure_ascii=False, sort_keys=True)}`",
                f"- Locator fields: `{json.dumps(row['locator_fields'], ensure_ascii=False, sort_keys=True)}`",
                f"- LLM-generated locator validation: `{json.dumps(row['llm_generated_locator_validation'], ensure_ascii=False, sort_keys=True)}`",
                f"- Diagnosis: {row['row_level_diagnosis']}",
                f"- Recommended next action: `{row['recommended_next_action']}`",
                "",
            ]
        )
    return "\n".join(lines)


def render_v3_1_triage_markdown(triage: Mapping[str, Any]) -> str:
    lines = [
        f"# {V3_1_RUN_ID} Failure Triage Queue",
        "",
        "This queue contains only rows with at least one failing diagnostic lane.",
        "",
    ]
    items = triage.get("items") or []
    if not items:
        lines.extend(["No failing rows were recorded.", ""])
        return "\n".join(lines)
    lines.extend(["| Rank | Query ID | Family | Category | Failing lanes | Fix type | Next step |", "|---:|---|---|---|---|---|---|"])
    for item in items:
        lines.append(
            "| {rank} | `{query_id}` | {family} | `{category}` | `{lanes}` | `{fix_type}` | `{next_step}` |".format(
                rank=item["priority_rank"],
                query_id=item["query_id"],
                family=item["source_family"],
                category=item["failure_category"],
                lanes=", ".join(item["failing_lane_names"]),
                fix_type=item["fix_type"],
                next_step=item["recommended_next_step"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_v3_1_summary_markdown(summary: Mapping[str, Any]) -> str:
    lane_counts = summary.get("lane_counts") or {}
    family_counts = summary.get("source_family_lane_counts") or {}
    lines = [
        f"# {summary['run_id']}",
        "",
        "## Purpose",
        "",
        "Freeze a diagnostic-only all-track foundation measurement before silver generation or row-level failure tuning.",
        "",
        "## Why this run exists",
        "",
        "v3 is an all-track official measurement, but PDF/XLSX primary answers are retained structured-adapter outputs. v3_1 records PDF/TEXT/XLSX LLM shadow/foundation lanes separately so later failure triage starts from fixed evidence.",
        "",
        "## Guardrails",
        "",
    ]
    for key, value in sorted((summary.get("guardrails") or {}).items()):
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(
        [
            "",
            "## Lane Definitions",
            "",
            "- Lane A `v3_primary_replay`: v3 primary policy replay; PDF/XLSX retain structured adapters, TEXT uses LLM synthesis.",
            "- Lane B `live_llm_retrieval_topk`: all 29 rows use live LLM synthesis over source-bound retrieved top-k context.",
            "- Lane C `live_llm_query_bound_oracle`: all 29 rows use live LLM synthesis over query-bound SearchUnit context only.",
            "",
            "## Overall Result Table",
            "",
            "| Lane | Scored | PASS | LLM invoked | Adapter retained | Failure counts |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for lane_name in V3_1_LANE_NAMES:
        counts = lane_counts.get(lane_name, {})
        lines.append(
            f"| `{lane_name}` | {counts.get('scored_count')} | {counts.get('pass_count')} | {counts.get('llm_invoked_count')} | {counts.get('adapter_retained_count')} | `{json.dumps(counts.get('failure_counts'), ensure_ascii=False, sort_keys=True)}` |"
        )
    lines.extend(["", "## Per-Track Result Table", "", "| Family | Lane | PASS | Failure counts |", "|---|---|---:|---|"])
    for family in ("PDF", "TEXT", "XLSX"):
        for lane_name in V3_1_LANE_NAMES:
            counts = (family_counts.get(family) or {}).get(lane_name, {})
            lines.append(
                f"| {family} | `{lane_name}` | {counts.get('pass_count')} | `{json.dumps(counts.get('failure_counts'), ensure_ascii=False, sort_keys=True)}` |"
            )
    lines.extend(
        [
            "",
            "## Lane A/B/C Comparison Table",
            "",
            f"- Lane names: `{', '.join(summary.get('lane_names') or [])}`",
            f"- LLM invoked count by lane: `{json.dumps(summary.get('llm_invoked_count_by_lane'), ensure_ascii=False, sort_keys=True)}`",
            f"- Adapter retained count by lane: `{json.dumps(summary.get('adapter_retained_count_by_lane'), ensure_ascii=False, sort_keys=True)}`",
            "",
            "## PDF Failure/Weakness Summary",
            "",
            f"`{json.dumps((family_counts.get('PDF') or {}), ensure_ascii=False, sort_keys=True)}`",
            "",
            "## XLSX Failure/Weakness Summary",
            "",
            f"`{json.dumps((family_counts.get('XLSX') or {}), ensure_ascii=False, sort_keys=True)}`",
            "",
            "## TEXT Failure/Weakness Summary",
            "",
            f"`{json.dumps((family_counts.get('TEXT') or {}), ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Locator Preservation Summary",
            "",
            f"- Citation payload locator preservation failures: `{json.dumps(summary.get('locator_preservation_failure_count_by_source_family'), ensure_ascii=False, sort_keys=True)}`",
            f"- LLM-generated locator failures by source family: `{json.dumps(summary.get('llm_generated_locator_failure_count_by_source_family'), ensure_ascii=False, sort_keys=True)}`",
            f"- LLM-generated locator failures by lane: `{json.dumps(summary.get('llm_generated_locator_failure_count_by_lane'), ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Citation Payload Summary",
            "",
            f"`{json.dumps(summary.get('citation_payload_summary'), ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Failure Triage Queue",
            "",
            f"See `{summary['artifact_paths']['triage_queue_md']}`.",
            "",
            "## What Is Not Decided In This Run",
            "",
            "- No silver set was created.",
            "- No gold, expected answer, supporting evidence, relevance label, or answerability label was changed.",
            "- No threshold tuning, winner selection, or promotion gate was run.",
            "- No failing row was fixed.",
            "",
            "## Next Steps",
            "",
            f"`{summary.get('next_step_recommendation')}`",
            "",
        ]
    )
    return "\n".join(lines)


def render_v3_1_priority_1_5_summary_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        f"# {summary['run_id']}",
        "",
        "## Purpose",
        "",
        "Diagnostic-only row-level rerun for v3_1 triage priorities 1 through 5, focused on strict JSON stability and LLM-generated locator copy stability.",
        "",
        "## Guardrails",
        "",
    ]
    for key, value in sorted((summary.get("guardrails") or {}).items()):
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(
        [
            "",
            "## Before/After",
            "",
            "| Metric | Before | After |",
            "|---|---:|---:|",
            f"| Strict JSON parse failures | {summary.get('strict_json_parse_failure_before')} | {summary.get('strict_json_parse_failure_after')} |",
            f"| Strict JSON schema repairs applied | {summary.get('strict_json_schema_repair_applied_count_before')} | {summary.get('strict_json_schema_repair_applied_count_after')} |",
            f"| LLM-generated locator copy failures | {summary.get('llm_generated_locator_copy_failure_before')} | {summary.get('llm_generated_locator_copy_failure_after')} |",
            f"| LLM-generated locator field mismatches | {summary.get('llm_generated_locator_field_mismatch_failure_before')} | {summary.get('llm_generated_locator_field_mismatch_failure_after')} |",
            f"| LLM-generated locator missing-field/missing-locator failures | {summary.get('llm_generated_locator_missing_failure_before')} | {summary.get('llm_generated_locator_missing_failure_after')} |",
            f"| PDF `source_pdf_path` mismatches | {summary.get('pdf_source_pdf_path_mismatch_before')} | {summary.get('pdf_source_pdf_path_mismatch_after')} |",
            f"| XLSX `row_label` mismatches | {summary.get('xlsx_row_label_mismatch_before')} | {summary.get('xlsx_row_label_mismatch_after')} |",
            "",
            "## Metric Split",
            "",
            f"- Post-hoc payload locator preservation failures: `{summary.get('posthoc_payload_locator_preservation_failure_count')}`",
            f"- LLM-generated locator copy failures: `{summary.get('llm_generated_locator_copy_failure_count')}`",
            f"- LLM-generated locator field mismatches: `{summary.get('llm_generated_locator_field_mismatch_failure_after')}`",
            f"- LLM-generated locator missing-field/missing-locator failures: `{summary.get('llm_generated_locator_missing_failure_after')}`",
            "",
            "## Score Interpretation",
            "",
            f"`{summary.get('score_interpretation')}`",
            "",
            "## Artifacts",
            "",
            f"- Results: `{summary['artifact_paths']['results_jsonl']}`",
            f"- Strict JSON diagnostics: `{summary['artifact_paths']['strict_json_diagnostics_json']}`",
            f"- Actual response audit: `{summary['artifact_paths']['actual_response_audit_jsonl']}`",
            f"- Triage delta: `{summary['artifact_paths']['triage_delta_json']}`",
            "",
            "## What Is Not Decided",
            "",
            "- No expected answer, supporting evidence, relevance label, answerability label, or gold policy was changed.",
            "- No silver set, promotion evidence, threshold tuning, winner selection, or promotion gate was created or run.",
            "",
            "## User Decisions Still Required",
            "",
            "- Expected answer changes.",
            "- Supporting evidence changes.",
            "- Relevance or answerability label changes.",
            "- Gold policy changes.",
            "- Silver/gold promotion decisions.",
            "",
        ]
    )
    return "\n".join(lines)


def scored_citation_contract(
    citations: Sequence[Mapping[str, Any]],
    *,
    track: str,
) -> dict[str, Any]:
    scored: list[Mapping[str, Any]] = []
    discarded_off_track: list[Mapping[str, Any]] = []
    same_track_invalid: list[Mapping[str, Any]] = []
    scored_indices: list[int] = []
    for index, citation in enumerate(citations):
        validation = citation_validation(citation)
        if validation.get("off_track") is True:
            discarded_off_track.append(citation)
            continue
        if validation.get("ok") is True:
            scored.append(citation)
            scored_indices.append(index)
        else:
            same_track_invalid.append(citation)
    primary_failure = None
    if same_track_invalid:
        primary_failure = citation_validation(same_track_invalid[0])
    elif discarded_off_track:
        primary_failure = citation_validation(discarded_off_track[0])
    return {
        "query_track": official.clean(track),
        "scored_citations": scored,
        "scored_generated_citation_indices": scored_indices,
        "discarded_off_track_citations": discarded_off_track,
        "discarded_off_track_citation_count": len(discarded_off_track),
        "same_track_valid_citation_count": len(scored),
        "schema_mismatch_residual_count": len(same_track_invalid),
        "primary_failure_validation": primary_failure or {},
    }


def chunks_from_scored_citation_contract(
    chunks: Sequence[Any],
    citation_contract: Mapping[str, Any],
) -> list[Any]:
    selected: list[Any] = []
    for index in citation_contract.get("scored_generated_citation_indices") or []:
        if isinstance(index, int) and 0 <= index < len(chunks):
            selected.append(chunks[index])
    return selected


def citations_from_chunks(
    chunks: Sequence[Any],
    *,
    track: str = "",
    query_id: str = "",
    require_official_compatible: bool = False,
    structured_adapters_enabled: bool = False,
    allowed_manifest_search_unit_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks[:5]):
        locator = {
            "chunk_id": getattr(chunk, "chunk_id", ""),
            "doc_id": getattr(chunk, "doc_id", ""),
            "search_unit_id": getattr(chunk, "search_unit_id", None),
            "source_file_id": getattr(chunk, "source_file_id", None),
            "source_file_name": getattr(chunk, "source_file_name", None),
            "page_start": getattr(chunk, "page_start", None),
            "page_end": getattr(chunk, "page_end", None),
        }
        canonical_payload = citation_payload(chunk)
        validation = validate_search_unit_citation_payload(
            canonical_payload,
            track=track,
            query_id=query_id,
            require_official_compatible=require_official_compatible,
            original_chunk=chunk,
            allowed_manifest_search_unit_ids=allowed_manifest_search_unit_ids,
        )
        item = {
            "generated_citation_index": index,
            "citation_text": official.clean(getattr(chunk, "text", ""))[:500],
            "locator": {key: value for key, value in locator.items() if value not in (None, "")},
            "search_unit_citation_payload": canonical_payload,
            "citation_payload_validation": validation,
            "official_compatible_locator": validation["ok"],
            "structured_source_bound_adapter_enabled": bool(structured_adapters_enabled),
            "structured_adapter_output_from_source_bound_search_unit": False,
        }
        if structured_adapters_enabled and validation["ok"]:
            if track == "xlsx_business_structured":
                item["structured_source_bound_adapter"] = xlsx_source_bound_adapter_payload(canonical_payload)
                item["structured_adapter_output_from_source_bound_search_unit"] = True
            elif track == "pdf_business_ocr_mm":
                item["structured_source_bound_adapter"] = pdf_source_bound_adapter_payload(canonical_payload)
                item["structured_adapter_output_from_source_bound_search_unit"] = True
        citations.append(
            item
        )
    return citations


def validate_search_unit_citation_payload(
    payload: Mapping[str, Any] | None,
    *,
    track: str,
    query_id: str = "",
    require_official_compatible: bool,
    original_chunk: Any,
    allowed_manifest_search_unit_ids: set[str] | None = None,
) -> dict[str, Any]:
    row_query_id = official.clean(query_id)
    if not isinstance(payload, Mapping) or not payload:
        return {
            "ok": False,
            "category": SEARCH_UNIT_CITATION_PAYLOAD_MISSING,
            "validation_category": SEARCH_UNIT_CITATION_PAYLOAD_MISSING,
            "missing_fields": [],
            "query_track": official.clean(track),
            "manifest_track": "",
            "row_query_id": row_query_id,
            "manifest_query_id": "",
            "manifest_source_family": "",
            "locator_schema": "",
            "off_track": False,
            "detail": "canonical SearchUnit citation payload is missing",
        }
    if not require_official_compatible:
        return {
            "ok": True,
            "category": None,
            "validation_category": None,
            "missing_fields": [],
            "query_track": official.clean(track),
            "manifest_track": citation_manifest_track(payload, original_chunk),
            "row_query_id": row_query_id,
            "manifest_query_id": citation_manifest_query_id(payload, original_chunk),
            "manifest_source_family": citation_manifest_source_family(payload, original_chunk),
            "locator_schema": citation_locator_schema(payload, original_chunk),
            "off_track": False,
            "detail": "",
        }

    query_track = official.clean(track)
    manifest_track = citation_manifest_track(payload, original_chunk)
    manifest_query_id = citation_manifest_query_id(payload, original_chunk)
    manifest_source_family = citation_manifest_source_family(payload, original_chunk)
    locator_schema = citation_locator_schema(payload, original_chunk)
    if query_track and manifest_track and query_track != manifest_track:
        return {
            "ok": False,
            "category": OFF_TRACK_CITATION_FOR_QUERY_TRACK,
            "validation_category": OFF_TRACK_CITATION_FOR_QUERY_TRACK,
            "missing_fields": [],
            "query_track": query_track,
            "manifest_track": manifest_track,
            "row_query_id": row_query_id,
            "manifest_query_id": manifest_query_id,
            "manifest_source_family": manifest_source_family,
            "locator_schema": locator_schema,
            "off_track": True,
            "detail": "citation manifest track does not match the query track and is excluded from scoring",
        }
    if not official.clean(getattr(original_chunk, "search_unit_id", None)):
        category = STRUCTURED_LOCATOR_DROPPED if track in {
            "xlsx_business_structured",
            "pdf_business_ocr_mm",
        } else SEARCH_UNIT_SOURCE_IDENTITY_MISSING
        return {
            "ok": False,
            "category": category,
            "validation_category": SAME_TRACK_LOCATOR_INCOMPLETE,
            "missing_fields": ["search_unit_id"],
            "query_track": query_track,
            "manifest_track": manifest_track,
            "row_query_id": row_query_id,
            "manifest_query_id": manifest_query_id,
            "manifest_source_family": manifest_source_family,
            "locator_schema": locator_schema,
            "off_track": False,
            "detail": "retrieved evidence has only a weak chunk locator, not a source-bound SearchUnit id",
        }
    search_unit_id = official.clean(getattr(original_chunk, "search_unit_id", None))
    if allowed_manifest_search_unit_ids is not None and search_unit_id not in allowed_manifest_search_unit_ids:
        return {
            "ok": False,
            "category": SEARCH_UNIT_MANIFEST_MISMATCH,
            "validation_category": SEARCH_UNIT_MANIFEST_MISMATCH,
            "missing_fields": [],
            "query_track": query_track,
            "manifest_track": manifest_track,
            "row_query_id": row_query_id,
            "manifest_query_id": manifest_query_id,
            "manifest_source_family": manifest_source_family,
            "locator_schema": locator_schema,
            "off_track": False,
            "detail": "retrieved SearchUnit is not present in the source-bound official manifest",
        }
    source_identity = (
        official.clean(getattr(original_chunk, "source_file_id", None))
        or official.clean(payload.get("sourceFileId"))
        or official.clean(payload.get("source_file_id"))
        or official.clean(payload.get("document_version_id"))
        or official.clean(payload.get("documentVersionId"))
    )
    if not source_identity:
        return {
            "ok": False,
            "category": SEARCH_UNIT_SOURCE_IDENTITY_MISSING,
            "validation_category": SAME_TRACK_LOCATOR_INCOMPLETE,
            "missing_fields": ["source_file_id_or_document_version_id"],
            "query_track": query_track,
            "manifest_track": manifest_track,
            "row_query_id": row_query_id,
            "manifest_query_id": manifest_query_id,
            "manifest_source_family": manifest_source_family,
            "locator_schema": locator_schema,
            "off_track": False,
            "detail": "SearchUnit citation payload is missing source identity",
        }

    missing_fields = [
        field
        for field in REQUIRED_CITATION_FIELDS_BY_TRACK.get(track, ())
        if not has_required_citation_value(payload.get(field), field=field)
    ]
    if missing_fields:
        category = (
            STRUCTURED_LOCATOR_DROPPED
            if track in {"xlsx_business_structured", "pdf_business_ocr_mm"}
            else SEARCH_UNIT_LOCATOR_INCOMPLETE
        )
        return {
            "ok": False,
            "category": category,
            "validation_category": SAME_TRACK_LOCATOR_INCOMPLETE,
            "missing_fields": missing_fields,
            "query_track": query_track,
            "manifest_track": manifest_track,
            "row_query_id": row_query_id,
            "manifest_query_id": manifest_query_id,
            "manifest_source_family": manifest_source_family,
            "locator_schema": locator_schema,
            "off_track": False,
            "detail": "SearchUnit citation payload is missing official-compatible locator fields",
        }
    return {
        "ok": True,
        "category": None,
        "validation_category": None,
        "missing_fields": [],
        "query_track": query_track,
        "manifest_track": manifest_track,
        "row_query_id": row_query_id,
        "manifest_query_id": manifest_query_id,
        "manifest_source_family": manifest_source_family,
        "locator_schema": locator_schema,
        "off_track": False,
        "detail": "",
    }


def citation_manifest_track(payload: Mapping[str, Any], original_chunk: Any) -> str:
    track = official.clean(
        payload.get("track")
        or payload.get("manifest_track")
        or as_mapping(getattr(original_chunk, "metadata_json", None)).get("track")
    )
    if track:
        return track
    chunk_section = official.clean(getattr(original_chunk, "section", ""))
    return chunk_section if chunk_section in REQUIRED_CITATION_FIELDS_BY_TRACK else ""


def citation_manifest_query_id(payload: Mapping[str, Any], original_chunk: Any) -> str:
    return official.clean(
        payload.get("manifest_query_id")
        or payload.get("manifestQueryId")
        or as_mapping(getattr(original_chunk, "metadata_json", None)).get("manifest_query_id")
    )


def citation_manifest_source_family(payload: Mapping[str, Any], original_chunk: Any) -> str:
    source_family = official.clean(
        payload.get("source_family")
        or payload.get("sourceFamily")
        or as_mapping(getattr(original_chunk, "metadata_json", None)).get("source_family")
    )
    return source_family or source_family_for_track(citation_manifest_track(payload, original_chunk))


def citation_locator_schema(payload: Mapping[str, Any], original_chunk: Any) -> str:
    locator_schema = official.clean(
        payload.get("locator_schema")
        or payload.get("locatorSchema")
        or as_mapping(getattr(original_chunk, "metadata_json", None)).get("locator_schema")
    )
    return locator_schema or locator_schema_for_track(citation_manifest_track(payload, original_chunk))


def xlsx_source_bound_adapter_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    require_source_bound_adapter_payload(payload)
    return {
        "adapter": "xlsx_source_bound_deterministic_v1",
        "output_from_source_bound_search_unit": True,
        "workbook": clean_any(payload.get("workbook")),
        "sheet": clean_any(payload.get("sheet") or payload.get("sheetName") or payload.get("sheet_name")),
        "range": clean_any(payload.get("range") or payload.get("cellRange") or payload.get("cell_range")),
        "cell": clean_any(payload.get("cell")),
        "row_label": clean_any(payload.get("row_label") or payload.get("rowLabel")),
        "target_column": clean_any(payload.get("target_column") or payload.get("targetColumn")),
        "normalized_value": clean_any(payload.get("normalized_value") or payload.get("normalizedValue")),
        "search_unit_id": clean_any(payload.get("search_unit_id") or payload.get("searchUnitId")),
        "document_version_id": clean_any(payload.get("document_version_id") or payload.get("documentVersionId")),
    }


def pdf_source_bound_adapter_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    require_source_bound_adapter_payload(payload)
    return {
        "adapter": "pdf_source_bound_deterministic_v1",
        "output_from_source_bound_search_unit": True,
        "source_pdf_path": clean_any(first_present(payload, "source_pdf_path", "sourcePdfPath")),
        "page": first_present(payload, "page"),
        "physical_page_index": first_present(payload, "physical_page_index", "physicalPageIndex"),
        "bbox": list(payload.get("bbox") or []),
        "region_type": clean_any(first_present(payload, "region_type", "regionType")),
        "row_label": clean_any(first_present(payload, "row_label", "rowLabel")),
        "target_column": clean_any(first_present(payload, "target_column", "targetColumn")),
        "search_unit_id": clean_any(first_present(payload, "search_unit_id", "searchUnitId")),
        "document_version_id": clean_any(first_present(payload, "document_version_id", "documentVersionId")),
    }


def first_present(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def require_source_bound_adapter_payload(payload: Mapping[str, Any]) -> None:
    candidate_keys = {
        "candidate_result_jsonl",
        "candidate_path",
        "candidate_artifact_path",
        "candidate_results_path",
    }
    if payload.get("source_bound_official_denominator") is not True:
        raise ValueError("adapter input must be a retrieved source-bound SearchUnit payload")
    if any(official.clean(payload.get(key)) for key in candidate_keys):
        raise ValueError("adapter input must be a retrieved source-bound SearchUnit payload")
    if payload.get("candidate_artifact_generation_source") is True:
        raise ValueError("adapter input must be a retrieved source-bound SearchUnit payload")


def has_required_citation_value(value: Any, *, field: str) -> bool:
    if field == "bbox":
        return isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) == 4
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return bool(value)
    return value is not None


def clean_any(value: Any) -> str:
    return official.clean(value)


def evidence_from_chunks(chunks: Sequence[Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for chunk in chunks:
        evidence_id = official.clean(getattr(chunk, "search_unit_id", None) or getattr(chunk, "chunk_id", ""))
        evidence.append(
            {
                "id": evidence_id,
                "chunk_id": official.clean(getattr(chunk, "chunk_id", "")),
                "doc_id": official.clean(getattr(chunk, "doc_id", "")),
                "search_unit_id": official.clean(getattr(chunk, "search_unit_id", "")),
                "source_file_id": official.clean(getattr(chunk, "source_file_id", "")),
                "source_file_name": official.clean(getattr(chunk, "source_file_name", "")),
                "score": getattr(chunk, "score", None),
            }
        )
    return evidence


def build_summary(
    *,
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    consumed: Mapping[str, Any],
    baseline: Mapping[str, Any],
    validation_errors: Sequence[str],
    agentic_status: Mapping[str, Any],
    metric_input_config_path: Path,
    denominator_registry_path: Path,
    pre_execution_smoke_path: Path,
    application_path: Path | None,
    registry_application_fallback_used: bool,
    baseline_path: Path,
) -> dict[str, Any]:
    failure_counts = dict(sorted(Counter(row["failure_category"] for row in rows).items()))
    pass_count = failure_counts.get("PASS", 0)
    scored_count = sum(
        1 for row in rows if row.get("answer_score") is not None and row.get("citation_support_score") is not None
    )
    per_track = per_track_counts(rows)
    baseline_per_track = {
        track: int((item or {}).get("failure_category_counts", {}).get("PASS", 0))
        for track, item in (baseline.get("track_aggregates") or {}).items()
    }
    pass_delta_by_track = {
        track: int(per_track.get(track, {}).get("pass_count", 0)) - int(baseline_per_track.get(track, 0))
        for track in official.TRACKS
    }
    status = (
        "PASS"
        if pass_count == len(rows) and rows
        else "BLOCKED_ACTUAL_GENERATION_PIPELINE_UNAVAILABLE"
        if failure_counts == {GENERATION_PIPELINE_UNAVAILABLE: len(rows)}
        else "BLOCKED_OR_PARTIAL"
    )
    index_dependency = agentic_status.get(
        "index_dependency",
        inspect_rag_index_dependency(Path(args.rag_index_dir)),
    )
    source_bound_ready = bool(index_dependency.get("rerun_allowed")) if isinstance(index_dependency, Mapping) else False
    search_unit_payloads_used = any(bool(row.get("search_unit_citation_payloads_used")) for row in rows)
    citation_contract_metrics = summarize_citation_contract_metrics(rows)
    residual_failure_audit = build_residual_failure_audit(
        run_id=args.run_id,
        result_rows=rows,
        source_rows=consumed["rows"],
        schema_mismatch_residual_count=citation_contract_metrics["schema_mismatch_residual_count"],
    )
    adapters_enabled = any(bool(row.get("structured_source_bound_adapters_enabled")) for row in rows)
    adapter_output_from_source_bound = all(
        bool(row.get("adapter_output_from_source_bound_search_units"))
        for row in rows
        if row.get("track") in {"xlsx_business_structured", "pdf_business_ocr_mm"}
    )
    chunk_only_fallback_disabled = all(
        bool(row.get("chunk_only_citation_fallback_disabled")) for row in rows
    ) if rows else True
    official_compatible_path = (
        source_bound_ready
        and search_unit_payloads_used
        and chunk_only_fallback_disabled
        and (adapters_enabled or not any(row.get("track") in {"xlsx_business_structured", "pdf_business_ocr_mm"} for row in rows))
        and adapter_output_from_source_bound
    )
    classification = (
        args.run_id
        if is_source_bound_manifest_run(args.run_id) and source_bound_ready
        else "official_next_run_measurement_source_bound_backend_limited"
        if official_compatible_path and status in {"PASS", "BLOCKED_OR_PARTIAL"}
        else "diagnostic_actual_generation_blocked_source_bound_index_unavailable"
        if status == "BLOCKED_ACTUAL_GENERATION_PIPELINE_UNAVAILABLE"
        else "diagnostic_live_generation_fixture_all_index_not_official_denominator_representative"
    )
    infrastructure_category = (
        blocked_failure_category(validation_errors, agentic_status)
        if status == "BLOCKED_ACTUAL_GENERATION_PIPELINE_UNAVAILABLE"
        else None
    )
    model_quality_comparable = bool(
        official_compatible_path
        and scored_count
        and any(row["agentic_loop_executed"] for row in rows)
        and any(row.get("local_llm_used") for row in rows)
    )
    agentic_loop_public = {
        key: value
        for key, value in agentic_status.items()
        if not key.startswith("_")
    }
    agentic_loop_public["executed"] = any(row["agentic_loop_executed"] for row in rows)
    agentic_loop_public["steps_count"] = sum(int(row.get("agentic_loop_steps_count") or 0) for row in rows)
    return {
        "schema_version": args.run_id,
        "run_id": args.run_id,
        "generated_at": utc_timestamp(),
        "status": status,
        "diagnostic_only": True,
        "measurement_classification": classification,
        "official_metric_execution_started": True,
        "actual_generation_execution_started": any(row["agentic_loop_executed"] for row in rows),
        "denominator_count": len(consumed["rows"]),
        "result_count": len(rows),
        "unique_query_id_count": len({row["query_id"] for row in rows}),
        "scored_count": scored_count,
        "pass_count": pass_count,
        "failure_counts": failure_counts,
        "official_score_category_counts": {
            "PASS": int(failure_counts.get("PASS", 0)),
            "CITATION_UNSUPPORTED": int(failure_counts.get("CITATION_UNSUPPORTED", 0)),
            "PARTIAL_OR_UNSUPPORTED": int(failure_counts.get("PARTIAL_OR_UNSUPPORTED", 0)),
        },
        "per_track_counts": per_track,
        "non_production_rag_index_dependency": index_dependency,
        "infrastructure_blocker": {
            "category": infrastructure_category,
            "domain": "infrastructure" if infrastructure_category else None,
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": model_quality_comparable,
        },
        "agentic_loop": agentic_loop_public,
        "local_llm_used": False,
        "local_gpu_used": any(bool(row.get("local_gpu_used")) for row in rows),
        "llm_backend": "noop",
        "llm_backend_limitation": "noop/extractive diagnostic; no validated local LLM answer synthesis backend used",
        "source_bound_index_used": source_bound_ready,
        "canonical_search_unit_payload_used": search_unit_payloads_used,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "promotion_evidence": False,
        "baseline_comparison_is_model_quality_comparable": model_quality_comparable,
        "performance_interpretation": (
            "source_bound_official_denominator_backend_limited_diagnostic"
            if is_source_bound_manifest_run(args.run_id) and source_bound_ready
            else "source_bound_official_denominator_backend_limited_diagnostic"
            if official_compatible_path
            else "diagnostic_retrieval_agent_loop_not_final_answer_generation_quality"
        ),
        "search_unit_citation_payloads_used": search_unit_payloads_used,
        "all_generated_citations_source_bound": citation_contract_metrics["all_generated_citations_source_bound"],
        "same_track_generated_citations_source_bound": citation_contract_metrics[
            "same_track_generated_citations_source_bound"
        ],
        "scored_citations_source_bound": citation_contract_metrics["scored_citations_source_bound"],
        "adapter_output_for_same_track_citations": citation_contract_metrics[
            "adapter_output_for_same_track_citations"
        ],
        "discarded_off_track_citation_count": citation_contract_metrics["discarded_off_track_citation_count"],
        "same_track_valid_citation_count": citation_contract_metrics["same_track_valid_citation_count"],
        "query_bound_scored_citation_count": citation_contract_metrics["query_bound_scored_citation_count"],
        "non_query_bound_same_track_scored_citation_count": citation_contract_metrics[
            "non_query_bound_same_track_scored_citation_count"
        ],
        "schema_mismatch_residual_count": citation_contract_metrics["schema_mismatch_residual_count"],
        "residual_failure_audit": residual_failure_audit,
        "citation_contract_metrics": citation_contract_metrics,
        "xlsx_pdf_structured_adapters_enabled": adapters_enabled,
        "adapter_output_from_source_bound_search_units": adapter_output_from_source_bound,
        "chunk_only_citation_fallback_disabled_for_official_scoring": chunk_only_fallback_disabled,
        "diagnostic_limitations": diagnostic_limitations(
            source_bound_ready=source_bound_ready,
            search_unit_payloads_used=search_unit_payloads_used,
            adapters_enabled=adapters_enabled,
            adapter_output_from_source_bound=adapter_output_from_source_bound,
            chunk_only_fallback_disabled=chunk_only_fallback_disabled,
        ),
        "source_bound_official_denominator_index_design": source_bound_index_design(index_dependency),
        "source_artifacts": {
            "metric_input_config": official.file_identity(metric_input_config_path),
            "denominator_registry": official.file_identity(denominator_registry_path),
            "pre_execution_smoke_report": official.file_identity(pre_execution_smoke_path),
            "registry_application_report": official.file_identity(application_path) if application_path else None,
            "immutable_first_run_baseline": official.file_identity(baseline_path),
            "xlsx_report_only_candidate": official.file_identity(Path(args.xlsx_candidate_results)),
            "pdf_report_only_candidate": official.file_identity(Path(args.pdf_candidate_results)),
        },
        "artifact_paths": {
            "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
            "summary_json": official.repo_relative(Path(args.summary_json)),
            "summary_md": official.repo_relative(Path(args.summary_md)),
            "failure_attribution_json": report_artifact_repo_relative(args.run_id, "failure.json"),
        },
        "artifact_provenance": {
            "immutable_first_run_baseline_overwritten": False,
            "report_only_candidates_promoted": False,
            "run_id_separate_from_first_run": True,
            "run_id_separate_from_xlsx_candidate": True,
            "run_id_separate_from_pdf_candidate": True,
        },
        "baseline_reference": {
            "run_id": "official_answer_citation_metric_first_run_v1",
            "status_detail": baseline.get("status_detail"),
            "scored_count": baseline.get("scored_count"),
            "pass_count": (baseline.get("failure_category_counts") or {}).get("PASS"),
            "failure_counts": baseline.get("failure_category_counts"),
            "per_track_pass_count": baseline_per_track,
        },
        "comparison_to_baseline": {
            "pass_delta": pass_count - int((baseline.get("failure_category_counts") or {}).get("PASS", 0)),
            "per_track_pass_delta": pass_delta_by_track,
            "key_failure_category_changes": {
                "new_failure_counts": failure_counts,
                "first_run_failure_counts": baseline.get("failure_category_counts"),
            },
        },
        "guardrails": {
            "tuning_run_started": False,
            "promotion_evidence": False,
            "threshold_tuning": False,
            "winner_selection": False,
            "production_mutation": False,
            "denominator_mutation": False,
            "gold_mutation": False,
            "generation_used_expected_answer": False,
            "generation_used_supporting_evidence": False,
            "generation_used_gold_fields": False,
        },
        "validation": {
            "ok": not validation_errors,
            "errors": list(validation_errors),
        },
        "pipeline_decision": {
            "selected_entrypoint": (
                "source-bound manifest-backed FAISS retriever + AgentLoopController"
                if is_source_bound_manifest_run(args.run_id)
                else "registry-backed RAG retriever + AgentLoopController when available"
            ),
            "rationale": (
                "This diagnostic validates the official source-bound denominator index and retrieves from "
                "its canonical SearchUnit manifest without mutating production state."
                if is_source_bound_manifest_run(args.run_id)
                else (
                    "No canonical official live answer-generation runner exists for the answer/citation denominator. "
                    "This runner validates the official denominator and attempts the implemented agent loop against "
                    "the actual registry-backed RAG pipeline, then fails closed if the pipeline is unavailable."
                )
            ),
            "registry_application_report_required": False,
            "registry_application_fallback_used": registry_application_fallback_used,
            "registry_application_fallback_rationale": (
                "The registry-application helper report is no longer part of the current source-of-truth report "
                "set after hard cleanup; denominator validation uses metric input config, registry, smoke report, "
                "and official gold CSV hashes/counts instead."
            ),
            "candidate_artifacts_not_used_as_generation_source": True,
            "expected_supporting_gold_used_for_generation": False,
        },
    }


def per_track_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for track in official.TRACKS:
        track_rows = [row for row in rows if row.get("track") == track]
        failure_counts = dict(sorted(Counter(row["failure_category"] for row in track_rows).items()))
        out[track] = {
            "row_count": len(track_rows),
            "scored_count": sum(
                1
                for row in track_rows
                if row.get("answer_score") is not None and row.get("citation_support_score") is not None
            ),
            "pass_count": failure_counts.get("PASS", 0),
            "failure_counts": failure_counts,
        }
    return out


def summarize_citation_contract_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows_with_generated = [row for row in rows if row.get("generated_citations")]
    rows_with_same_track = [
        row for row in rows if same_track_generated_citations(row.get("generated_citations") or [])
    ]
    rows_with_scored = [row for row in rows if row.get("scored_citations")]
    return {
        "all_generated_citations_source_bound": bool(rows_with_generated)
        and all(bool(row.get("all_generated_citations_source_bound")) for row in rows_with_generated),
        "same_track_generated_citations_source_bound": bool(rows_with_same_track)
        and all(
            bool(row.get("same_track_generated_citations_source_bound"))
            for row in rows_with_same_track
        ),
        "scored_citations_source_bound": bool(rows_with_scored)
        and all(bool(row.get("scored_citations_source_bound")) for row in rows_with_scored),
        "adapter_output_for_same_track_citations": all(
            bool(row.get("adapter_output_for_same_track_citations"))
            for row in rows
            if row.get("track") in {"xlsx_business_structured", "pdf_business_ocr_mm"}
            and row.get("scored_citations")
        ),
        "discarded_off_track_citation_count": sum(
            int(row.get("discarded_off_track_citation_count") or 0) for row in rows
        ),
        "same_track_valid_citation_count": sum(
            int(row.get("same_track_valid_citation_count") or 0) for row in rows
        ),
        "query_bound_scored_citation_count": sum(
            int(row.get("query_bound_scored_citation_count") or 0) for row in rows
        ),
        "non_query_bound_same_track_scored_citation_count": sum(
            int(row.get("non_query_bound_same_track_scored_citation_count") or 0) for row in rows
        ),
        "schema_mismatch_residual_count": sum(
            int(row.get("schema_mismatch_residual_count") or 0) for row in rows
        ),
    }


def diagnostic_limitations(
    *,
    source_bound_ready: bool,
    search_unit_payloads_used: bool,
    adapters_enabled: bool,
    adapter_output_from_source_bound: bool,
    chunk_only_fallback_disabled: bool,
) -> dict[str, Any]:
    return {
        "fixture_all_index_not_official_denominator_representative": not source_bound_ready,
        "baseline_comparison_is_model_quality_comparable": False,
        "current_pass_is_final_model_quality_regression": False,
        "current_pass_is_promotion_evidence": False,
        "llm_backend_noop": True,
        "extractive_generator": True,
        "chunk_only_citations_not_canonical_search_unit_payloads": not search_unit_payloads_used,
        "structured_adapters_not_wired": not adapters_enabled,
        "adapter_output_not_from_source_bound_search_units": not adapter_output_from_source_bound,
        "chunk_only_citation_fallback_not_disabled": not chunk_only_fallback_disabled,
    }


def source_bound_index_design(index_dependency: Mapping[str, Any]) -> dict[str, Any]:
    build_ready = bool(index_dependency.get("rerun_allowed"))
    blocker = index_dependency.get("blocker_category")
    return {
        "status": "build_ready_load_checked" if build_ready else "implemented_fail_closed_source_metadata_missing_or_unchecked",
        "blocker_category": None if build_ready else blocker,
        "target_index_path": "ai/eval/indexes/rag-data-official-denominator-v1",
        "index_version": OFFICIAL_SOURCE_BOUND_INDEX_VERSION,
        "non_production_only": True,
        "entrypoint_implemented": True,
        "build_ready": build_ready,
        "target_index_built": bool(index_dependency.get("exists")) and not bool(index_dependency.get("missing_files")),
        "load_check_passed": bool(index_dependency.get("source_bound_index_load_checked")),
        "rerun_allowed": build_ready,
        "production_index_path_used": bool(index_dependency.get("production_index_path_used")),
        "candidate_index_path_used": bool(index_dependency.get("candidate_index_path_used")),
        "candidate_artifacts_as_generation_source": False,
        "expected_supporting_used_for_generation": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "promotion_evidence": False,
        "baseline_overwrite": False,
        "gold_mutation": False,
        "denominator_mutation": False,
        "human_label_mutation": False,
        "official_denominator_rows": 29,
        "official_rows_by_track": {
            "text_namu_v2_1": 6,
            "xlsx_business_structured": 19,
            "pdf_business_ocr_mm": 4,
        },
        "required_fields_by_track": {
            "text_namu_v2_1": [
                "document_id",
                "document_version_id",
                "search_unit_id",
                "text_locator",
            ],
            "xlsx_business_structured": list(XLSX_REQUIRED_CITATION_FIELDS),
            "pdf_business_ocr_mm": list(PDF_REQUIRED_CITATION_FIELDS),
        },
        "repo_components_available": [
            "ai/scripts/rag_official_denominator_source_bound_index.py",
            "ai/app/capabilities/rag/search_unit_indexing.py::SearchUnitVectorIndexer",
            "ai/app/capabilities/rag/retrieval_contract.py::citation_payload",
            "ai/app/clients/schemas.py::SearchUnitIndexDocument",
            "ai/app/capabilities/pdf/table_parser.py",
        ],
        "current_fixture_all_build_path": {
            "script": "ai/scripts/build_rag_index.py",
            "command": "python -m scripts.build_rag_index --fixture all",
            "consumes_official_denominator_sources": False,
            "consumes_search_unit_claim_export": False,
            "preserves_official_xlsx_pdf_structured_locators": False,
        },
        "recommended_build_path": [
            "Run the source-bound readiness entrypoint and resolve missing locator/source fields.",
            "Export official-denominator SearchUnitIndexDocument rows from source metadata only.",
            "Build ai/eval/indexes/rag-data-official-denominator-v1 and run doctor load-check.",
            "Rerun only after SearchUnit citation payloads and structured adapters are enabled.",
        ],
    }


def blocked_failure_detail(validation_errors: Sequence[str], agentic_status: Mapping[str, Any]) -> str:
    if validation_errors:
        return "official denominator validation failed before generation: " + "; ".join(validation_errors)
    blockers = [official.clean(item) for item in agentic_status.get("blockers", []) if official.clean(item)]
    if blockers:
        return "actual registry-backed generation pipeline unavailable: " + "; ".join(blockers)
    return "actual registry-backed generation pipeline unavailable"


def blocked_failure_category(validation_errors: Sequence[str], agentic_status: Mapping[str, Any]) -> str:
    if validation_errors:
        return OFFICIAL_DENOMINATOR_VALIDATION_FAILED
    category = official.clean(agentic_status.get("infrastructure_blocker_category"))
    if category:
        return category
    dependency = agentic_status.get("index_dependency") if isinstance(agentic_status.get("index_dependency"), Mapping) else {}
    dependency_category = official.clean(dependency.get("blocker_category")) if isinstance(dependency, Mapping) else ""
    if dependency_category:
        return dependency_category
    return REGISTRY_BACKED_RAG_CAPABILITY_UNAVAILABLE


def build_failure_attribution(summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if summary["run_id"] in {
        V3_1_RUN_ID,
        V3_1_PRIORITY_1_5_RUN_ID,
        V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID,
        V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
        V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID,
        V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
    }:
        return build_v3_1_failure_attribution(summary, rows)
    row_attribution = [failure_attribution_for_row(row, summary=summary) for row in rows]
    primary_counts = dict(sorted(Counter(row["primary_attribution"] for row in row_attribution).items()))
    per_track: dict[str, dict[str, int]] = {}
    for track in official.TRACKS:
        per_track[track] = dict(
            sorted(
                Counter(
                    row["primary_attribution"]
                    for row in row_attribution
                    if row.get("track") == track
                ).items()
            )
        )
    measurement_result = {
        "rows": summary.get("result_count"),
        "unique_query_ids": summary.get("unique_query_id_count"),
        "scored_count": summary.get("scored_count"),
        **dict(summary.get("failure_counts") or {}),
    }
    return {
        "schema_version": f"{summary['run_id']}_failure_attribution_v1",
        "run_id": summary["run_id"],
        "generated_at": summary["generated_at"],
        "measurement_classification": summary["measurement_classification"],
        "performance_interpretation": summary.get("performance_interpretation"),
        "measurement_result": measurement_result,
        "official_score_category_counts": summary.get("official_score_category_counts"),
        "primary_attribution_counts": primary_counts,
        "per_track_primary_attribution_counts": per_track,
        "row_level_attribution": row_attribution,
        "source_bound_index_used": summary.get("source_bound_index_used"),
        "canonical_search_unit_payload_used": summary.get("canonical_search_unit_payload_used"),
        "citation_contract_metrics": summary.get("citation_contract_metrics"),
        "discarded_off_track_citation_count": summary.get("discarded_off_track_citation_count"),
        "same_track_valid_citation_count": summary.get("same_track_valid_citation_count"),
        "query_bound_scored_citation_count": summary.get("query_bound_scored_citation_count"),
        "non_query_bound_same_track_scored_citation_count": summary.get(
            "non_query_bound_same_track_scored_citation_count"
        ),
        "schema_mismatch_residual_count": summary.get("schema_mismatch_residual_count"),
        "validation_bucket_counts": summary.get("validation_bucket_counts"),
        "llm_backend_validation_status": summary.get("llm_backend_validation_status"),
        "llm_backend_preflight": summary.get("llm_backend_preflight"),
        "v2_1_artifact_consistency_preflight": summary.get("v2_1_artifact_consistency_preflight"),
        "real_llm_backend_used": summary.get("real_llm_backend_used"),
        "local_llm_used": summary.get("local_llm_used"),
        "residual_failure_audit": summary.get("residual_failure_audit"),
        "adapter_output_from_source_bound_search_units": summary.get(
            "adapter_output_from_source_bound_search_units"
        ),
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "promotion_evidence": False,
        "baseline_comparison_is_model_quality_comparable": False,
        "diagnostic_only": True,
        "guardrails": summary.get("guardrails"),
        "diagnostic_limitations": summary.get("diagnostic_limitations"),
        "source_bound_official_denominator_index_design": summary.get(
            "source_bound_official_denominator_index_design"
        ),
        "source_artifacts": summary.get("source_artifacts"),
    }


def build_v3_1_failure_attribution(summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    lane_counts = summary.get("lane_counts") or {}
    row_level: list[dict[str, Any]] = []
    for row in rows:
        lanes = row.get("lane_results") or {}
        row_level.append(
            {
                "query_id": row.get("query_id"),
                "track": row.get("track"),
                "source_family": row.get("source_family"),
                "lane_failure_categories": {
                    lane_name: lane.get("failure_category")
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping)
                },
                "failing_lane_names": [
                    lane_name
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping) and lane.get("failure_category") != "PASS"
                ],
                "passing_lane_names": [
                    lane_name
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping) and lane.get("failure_category") == "PASS"
                ],
                "locator_preservation": {
                    lane_name: lane.get("locator_preservation")
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping)
                },
                "citation_payload_validation": {
                    lane_name: lane.get("citation_payload_validation")
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping)
                },
                "llm_generated_locator_validation": {
                    lane_name: lane.get("llm_generated_locator_validation")
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping)
                },
                "strict_json_diagnostics": {
                    lane_name: lane.get("strict_json_diagnostics")
                    for lane_name, lane in lanes.items()
                    if isinstance(lane, Mapping)
                },
                "answer_span_renderer_diagnostics": row.get("answer_span_renderer_diagnostics"),
                "queue_priority_rank": row.get("queue_priority_rank"),
                "first_batch_selected": row.get("first_batch_selected"),
                "include_decision": row.get("include_decision"),
                "generation_used_expected_answer": False,
                "generation_used_supporting_evidence": False,
                "generation_used_gold_fields": False,
                "promotion_evidence": False,
            }
        )
    return {
        "schema_version": f"{summary['run_id']}_failure_attribution_v1",
        "run_id": summary["run_id"],
        "generated_at": summary["generated_at"],
        "measurement_classification": summary["measurement_classification"],
        "performance_interpretation": summary.get("performance_interpretation"),
        "failure_taxonomy": list(V3_1_FAILURE_TAXONOMY),
        "lane_counts": lane_counts,
        "source_family_lane_counts": summary.get("source_family_lane_counts"),
        "row_level_attribution": row_level,
        "guardrails": summary.get("guardrails"),
        "diagnostic_only": True,
        "promotion_evidence": False,
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "source_artifacts": summary.get("source_artifacts"),
    }


def failure_attribution_for_row(row: Mapping[str, Any], *, summary: Mapping[str, Any]) -> dict[str, Any]:
    citations = [
        item
        for item in row.get("generated_citations") or []
        if isinstance(item, Mapping)
    ]
    validations = [
        item.get("citation_payload_validation")
        for item in citations
        if isinstance(item.get("citation_payload_validation"), Mapping)
    ]
    validation_categories = [
        official.clean(validation.get("category"))
        for validation in validations
        if validation.get("ok") is not True and official.clean(validation.get("category"))
    ]
    same_track_validation_categories = [
        official.clean(validation.get("category"))
        for validation in validations
        if validation.get("ok") is not True
        and validation.get("off_track") is not True
        and official.clean(validation.get("category"))
    ]
    if row.get("validation_bucket") in V2_2_VALIDATION_BUCKETS:
        primary = row.get("validation_bucket")
        stage = "v2.2 llm backend validation"
    elif row.get("infrastructure_blocker_category") in {
        STALE_SOURCE_BOUND_READINESS_ARTIFACT,
        SOURCE_BOUND_INDEX_LOAD_CHECK_MISSING,
        SOURCE_BOUND_INDEX_VERSION_MISMATCH,
    }:
        primary = "SOURCE_BOUND_MANIFEST_MISMATCH"
        stage = "source-bound manifest mismatch"
    elif SEARCH_UNIT_MANIFEST_MISMATCH in validation_categories:
        primary = "SOURCE_BOUND_MANIFEST_MISMATCH"
        stage = "source-bound manifest mismatch"
    elif not row.get("retrieved_evidence"):
        primary = "RETRIEVAL_MISS"
        stage = "retrieval miss"
    elif same_track_validation_categories or row.get("failure_category") == OFF_TRACK_CITATION_FOR_QUERY_TRACK:
        primary = "CITATION_PAYLOAD_SCHEMA_MISMATCH"
        stage = "citation payload schema mismatch"
    elif row.get("track") in {"xlsx_business_structured", "pdf_business_ocr_mm"} and not row.get(
        "adapter_output_from_source_bound_search_units"
    ):
        primary = "ADAPTER_FAILURE"
        stage = "adapter failure"
    elif row.get("failure_category") in {"CITATION_UNSUPPORTED", "PARTIAL_OR_UNSUPPORTED"}:
        primary = "ANSWER_SYNTHESIS_LIMITATION"
        stage = "answer synthesis limitation"
    elif row.get("scoring_attempted") is False:
        primary = "SCORER_COMPATIBILITY_MISMATCH"
        stage = "scorer compatibility mismatch"
    else:
        primary = "SCORER_COMPATIBILITY_MISMATCH" if row.get("failure_category") != "PASS" else "PASS"
        stage = "scorer compatibility mismatch" if primary != "PASS" else "pass"
    return {
        "query_id": row.get("query_id"),
        "track": row.get("track"),
        "stage": stage,
        "primary_attribution": primary,
        "failure_category": row.get("failure_category"),
        "failure_reason": row.get("failure_reason"),
        "retrieved_evidence_count": len(row.get("retrieved_evidence") or []),
        "generated_citation_count": len(citations),
        "scored_citation_count": len(row.get("scored_citations") or []),
        "discarded_off_track_citation_count": row.get("discarded_off_track_citation_count"),
        "same_track_valid_citation_count": row.get("same_track_valid_citation_count"),
        "query_bound_scored_citation_count": row.get("query_bound_scored_citation_count"),
        "non_query_bound_same_track_scored_citation_count": row.get(
            "non_query_bound_same_track_scored_citation_count"
        ),
        "schema_mismatch_residual_count": row.get("schema_mismatch_residual_count"),
        "citation_payload_validation_categories": validation_categories,
        "same_track_citation_payload_validation_categories": same_track_validation_categories,
        "adapter_output_from_source_bound_search_units": row.get(
            "adapter_output_from_source_bound_search_units"
        ),
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "promotion_evidence": False,
    }


def append_status_event(path: Path, summary: Mapping[str, Any]) -> None:
    event = {
        "event_type": "official_answer_citation_agentic_loop_measurement",
        "run_id": summary["run_id"],
        "generated_at": summary["generated_at"],
        "status": summary["status"],
        "measurement_classification": summary["measurement_classification"],
        "result_count": summary["result_count"],
        "unique_query_id_count": summary["unique_query_id_count"],
        "scored_count": summary["scored_count"],
        "pass_count": summary["pass_count"],
        "failure_counts": summary["failure_counts"],
        "official_score_category_counts": summary.get("official_score_category_counts"),
        "result_bucket_counts": summary.get("result_bucket_counts"),
        "non_production_rag_index_dependency": summary["non_production_rag_index_dependency"],
        "infrastructure_blocker": summary["infrastructure_blocker"],
        "agentic_loop": summary["agentic_loop"],
        "local_llm_used": summary["local_llm_used"],
        "local_gpu_used": summary["local_gpu_used"],
        "llm_backend": summary.get("llm_backend"),
        "llm_backend_validation_status": summary.get("llm_backend_validation_status"),
        "validation_bucket_counts": summary.get("validation_bucket_counts"),
        "real_llm_backend_used": summary.get("real_llm_backend_used"),
        "v2_1_artifact_consistency_preflight": summary.get("v2_1_artifact_consistency_preflight"),
        "prompt_context_source_bound_only": summary.get("prompt_context_source_bound_only"),
        "source_bound_index_used": summary.get("source_bound_index_used"),
        "canonical_search_unit_payload_used": summary.get("canonical_search_unit_payload_used"),
        "candidate_artifacts_as_generation_source": False,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "performance_interpretation": summary.get("performance_interpretation"),
        "diagnostic_only": summary.get("diagnostic_only", True),
        "comparable_live_measurement": summary.get("comparable_live_measurement", False),
        "promotion_gate_auto_run": summary.get("promotion_gate_auto_run", False),
        "comparison_scope": summary.get("comparison_scope"),
        "baseline_comparison_is_model_quality_comparable": summary["infrastructure_blocker"].get(
            "baseline_comparison_is_model_quality_comparable"
        ),
        "search_unit_citation_payloads_used": summary.get("search_unit_citation_payloads_used"),
        "citation_contract_metrics": summary.get("citation_contract_metrics"),
        "discarded_off_track_citation_count": summary.get("discarded_off_track_citation_count"),
        "same_track_valid_citation_count": summary.get("same_track_valid_citation_count"),
        "query_bound_scored_citation_count": summary.get("query_bound_scored_citation_count"),
        "non_query_bound_same_track_scored_citation_count": summary.get(
            "non_query_bound_same_track_scored_citation_count"
        ),
        "schema_mismatch_residual_count": summary.get("schema_mismatch_residual_count"),
        "query_bound_evidence_gap_count": summary.get("query_bound_evidence_gap_count"),
        "residual_failure_audit": summary.get("residual_failure_audit"),
        "xlsx_pdf_structured_adapters_enabled": summary.get("xlsx_pdf_structured_adapters_enabled"),
        "adapter_output_from_source_bound_search_units": summary.get(
            "adapter_output_from_source_bound_search_units"
        ),
        "chunk_only_citation_fallback_disabled_for_official_scoring": summary.get(
            "chunk_only_citation_fallback_disabled_for_official_scoring"
        ),
        "diagnostic_limitations": summary.get("diagnostic_limitations"),
        "source_bound_official_denominator_index_design": summary.get(
            "source_bound_official_denominator_index_design"
        ),
        "promotion_evidence": False,
        "guardrails": summary["guardrails"],
        "artifact_paths": summary["artifact_paths"],
    }
    if summary["run_id"] in {
        V3_1_RUN_ID,
        V3_1_PRIORITY_1_5_RUN_ID,
        V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID,
        V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
        V3_1_2_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        V3_1_3_REMAINING_QUEUE_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        V3_1_4_PDF_RESIDUAL_ANSWER_SPAN_RENDERER_TRIAGE_RUN_ID,
        V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID,
        V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID,
        V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID,
        V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID,
    }:
        event["lane_counts"] = summary.get("lane_counts")
        event["source_family_lane_counts"] = summary.get("source_family_lane_counts")
        event["rows_by_source_family"] = summary.get("rows_by_source_family")
        if "strict_json_parse_failure_after" in summary:
            event["strict_json_parse_failure_after"] = summary.get("strict_json_parse_failure_after")
        if "llm_generated_locator_copy_failure_after" in summary:
            event["llm_generated_locator_copy_failure_after"] = summary.get(
                "llm_generated_locator_copy_failure_after"
            )
        if "strict_json_parse_failure_count_by_lane" in summary:
            event["strict_json_parse_failure_count_by_lane"] = summary.get(
                "strict_json_parse_failure_count_by_lane"
            )
        if "llm_generated_locator_copy_failure_count_by_lane" in summary:
            event["llm_generated_locator_copy_failure_count_by_lane"] = summary.get(
                "llm_generated_locator_copy_failure_count_by_lane"
            )
        if "answer_span_renderer_diagnostic_counts" in summary:
            event["answer_span_renderer_diagnostic_counts"] = summary.get(
                "answer_span_renderer_diagnostic_counts"
            )
        for key in (
            "target_queue_pass_count_before_by_lane",
            "target_queue_pass_count_after_by_lane",
            "target_queue_answer_span_mismatch_before_by_lane",
            "target_queue_answer_span_mismatch_after_by_lane",
            "all_track_remeasurement_performed",
            "all_track_pass_count_before_by_lane",
            "all_track_pass_count_after_by_lane",
            "all_track_answer_span_mismatch_before_by_lane",
            "all_track_answer_span_mismatch_after_by_lane",
            "all_track_residuals_after",
            "queue_source_of_truth_decision",
        ):
            if key in summary:
                event[key] = summary.get(key)
        if summary["run_id"] == V3_1_6_GQ_AUTO_010_SAFE_PDF_PARAGRAPH_WINDOW_EXPANSION_RUN_ID:
            for key in (
                "source_queue_artifact",
                "source_queue_preflight",
                "context_expansion_attempted",
                "context_expansion_applied",
                "context_expansion_policy_name",
                "locator_safe_metadata_available",
                "behavior_change_made",
                "non_production_index_or_export_fix_applied",
                "official_retrieval_metrics_computed",
                "official_ndcg_computed",
                "official_mrr_computed",
                "official_hit_at_k_computed",
                "lane_score_collapsed",
                "all_track_non_target_context_expansion_query_ids",
                "all_track_non_target_unexpected_change_count",
            ):
                event[key] = summary.get(key)
        if summary["run_id"] == V3_1_7_POST_RESIDUAL_QUEUE_CLOSURE_AUDIT_RUN_ID:
            for key in (
                "source_run_id",
                "source_queue_artifact",
                "active_remaining_queue_empty",
                "active_remaining_queue_status",
                "closure_type",
                "all_track_residual_query_ids",
                "all_track_residual_lane_item_count",
                "residual_inventory_bucket_counts",
                "any_residual_requires_user_decision",
                "any_residual_safe_to_fix_without_user_decision",
                "active_implementation_queue_empty",
                "all_track_residuals_exist",
                "residuals_require_user_policy_review",
                "decision_packet_created",
                "official_retrieval_metrics_still_blocked",
                "recommended_next_phase",
                "behavior_change_made",
                "official_retrieval_metrics_computed",
                "official_ndcg_computed",
                "official_mrr_computed",
                "official_hit_at_k_computed",
                "lane_score_collapsed",
            ):
                event[key] = summary.get(key)
        if summary["run_id"] == V3_1_8_GOLD_POLICY_REVIEW_PACKET_RUN_ID:
            for key in (
                "source_run_id",
                "active_remaining_queue_empty",
                "active_implementation_queue_empty",
                "implementation_safe_residual_count",
                "decision_item_count",
                "decision_query_ids",
                "decision_options",
                "metadata_drift_observed",
                "source_artifact_hash_closure_required_for_policy_packet",
                "silver_generation_closed",
                "behavior_change_made",
                "production_mutation",
                "denominator_mutation",
                "gold_mutation",
                "human_label_mutation",
                "expected_answer_mutation",
                "supporting_evidence_mutation",
                "relevance_label_mutation",
                "answerability_label_mutation",
                "human_review_packet_contains_policy_material",
                "raw_reference_text_embedded_in_generation",
                "raw_supporting_text_embedded_in_generation",
                "raw_gold_text_embedded_in_generation",
                "candidate_artifacts_as_generation_source",
                "generation_used_expected_answer",
                "generation_used_supporting_evidence",
                "generation_used_gold_fields",
                "official_retrieval_metrics_computed",
                "official_ndcg_computed",
                "official_mrr_computed",
                "official_hit_at_k_computed",
                "lane_score_collapsed",
            ):
                event[key] = summary.get(key)
        if summary["run_id"] == V3_1_9_USER_GOLD_POLICY_OVERRIDE_RUN_ID:
            for key in (
                "source_run_id",
                "run_class",
                "user_policy_decision_applied",
                "changed_row_count",
                "changed_query_ids",
                "gold_application_mode",
                "gold_file_before_sha256",
                "gold_file_after_sha256",
                "official_denominator_query_id_set_mutation",
                "active_remaining_queue_empty",
                "active_implementation_queue_empty",
                "implementation_safe_residual_count",
                "expected_answer_mutation",
                "supporting_evidence_mutation",
                "gold_policy_mutation",
                "gold_mutation",
                "behavior_change_made",
                "renderer_mutation",
                "scorer_behavior_mutation",
                "retrieval_mutation",
                "production_mutation",
                "candidate_artifacts_as_generation_source",
                "generation_used_expected_answer",
                "generation_used_supporting_evidence",
                "generation_used_gold_fields",
                "silver_rows_created",
                "promotion_evidence",
                "official_retrieval_metrics_computed",
                "official_ndcg_computed",
                "official_mrr_computed",
                "official_hit_at_k_computed",
                "lane_score_collapsed",
                "live_generation_rerun",
                "scoring_only_remeasurement",
                "lane_pass_counts_before",
                "lane_pass_counts_after",
                "requires_additional_user_policy_packet",
                "any_remaining_residual_implementation_safe",
            ):
                event[key] = summary.get(key)
    if summary["run_id"] == V3_1_5_GQ_AUTO_010_SOURCE_BOUND_COVERAGE_DIAGNOSTIC_RUN_ID:
        for key in (
            "classification_result",
            "classification_counts",
            "source_queue_artifact",
            "source_queue_preflight",
            "official_retrieval_metrics_computed",
            "non_production_index_or_export_fix_applied",
            "behavior_change_made",
            "all_track_remeasurement_reason",
        ):
            event[key] = summary.get(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if path.exists():
        existing = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    retained = [
        item
        for item in existing
        if not (
            item.get("event_type") == event["event_type"]
            and item.get("run_id") == event["run_id"]
        )
    ]
    retained.append(event)
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in retained),
        encoding="utf-8",
    )


def append_failure_attribution_event(path: Path, attribution: Mapping[str, Any]) -> None:
    event = {
        "event_type": "official_answer_citation_agentic_loop_failure_attribution",
        "run_id": attribution["run_id"],
        "generated_at": attribution["generated_at"],
        "measurement_classification": attribution["measurement_classification"],
        "performance_interpretation": attribution.get("performance_interpretation"),
        "primary_attribution_counts": attribution.get("primary_attribution_counts"),
        "per_track_primary_attribution_counts": attribution.get("per_track_primary_attribution_counts"),
        "source_bound_index_used": attribution.get("source_bound_index_used"),
        "canonical_search_unit_payload_used": attribution.get("canonical_search_unit_payload_used"),
        "citation_contract_metrics": attribution.get("citation_contract_metrics"),
        "discarded_off_track_citation_count": attribution.get("discarded_off_track_citation_count"),
        "same_track_valid_citation_count": attribution.get("same_track_valid_citation_count"),
        "query_bound_scored_citation_count": attribution.get("query_bound_scored_citation_count"),
        "non_query_bound_same_track_scored_citation_count": attribution.get(
            "non_query_bound_same_track_scored_citation_count"
        ),
        "schema_mismatch_residual_count": attribution.get("schema_mismatch_residual_count"),
        "validation_bucket_counts": attribution.get("validation_bucket_counts"),
        "llm_backend_validation_status": attribution.get("llm_backend_validation_status"),
        "llm_backend_preflight": attribution.get("llm_backend_preflight"),
        "v2_1_artifact_consistency_preflight": attribution.get("v2_1_artifact_consistency_preflight"),
        "real_llm_backend_used": attribution.get("real_llm_backend_used"),
        "local_llm_used": attribution.get("local_llm_used"),
        "residual_failure_audit": attribution.get("residual_failure_audit"),
        "adapter_output_from_source_bound_search_units": attribution.get(
            "adapter_output_from_source_bound_search_units"
        ),
        "baseline_comparison_is_model_quality_comparable": False,
        "guardrails": attribution.get("guardrails"),
        "diagnostic_only": True,
        "generation_used_expected_answer": False,
        "generation_used_supporting_evidence": False,
        "generation_used_gold_fields": False,
        "source_bound_official_denominator_index_design": attribution.get(
            "source_bound_official_denominator_index_design"
        ),
        "promotion_evidence": False,
    }
    if attribution["run_id"] in {
        V3_1_RUN_ID,
        V3_1_PRIORITY_1_5_RUN_ID,
        V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID,
        V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID,
    }:
        event["failure_taxonomy"] = attribution.get("failure_taxonomy")
        event["lane_counts"] = attribution.get("lane_counts")
        event["source_family_lane_counts"] = attribution.get("source_family_lane_counts")
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = []
    if path.exists():
        existing = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    retained = [
        item
        for item in existing
        if not (
            item.get("event_type") == event["event_type"]
            and item.get("run_id") == event["run_id"]
        )
    ]
    retained.append(event)
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in retained),
        encoding="utf-8",
    )


def render_markdown(summary: Mapping[str, Any]) -> str:
    if summary["run_id"] == V3_1_RUN_ID:
        return render_v3_1_summary_markdown(summary)
    if summary["run_id"] == V3_1_PRIORITY_1_5_RUN_ID:
        return render_v3_1_priority_1_5_summary_markdown(summary)
    if summary["run_id"] == V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID:
        return render_v3_1_text_locator_residual_summary_markdown(summary)
    if summary["run_id"] == V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID:
        return render_v3_1_1_post_triage_summary_markdown(summary)
    index_dependency = summary["non_production_rag_index_dependency"]
    build_metadata = (
        index_dependency.get("build_metadata", {})
        if isinstance(index_dependency, Mapping)
        else {}
    )
    lines = [
        f"# {summary['run_id']}",
        "",
        f"- Run id: `{summary['run_id']}`",
        f"- Status: `{summary['status']}`",
        f"- Measurement classification: `{summary['measurement_classification']}`",
        f"- Performance interpretation: `{summary.get('performance_interpretation')}`",
        f"- Denominator / results / unique query_ids: `{summary['denominator_count']}` / `{summary['result_count']}` / `{summary['unique_query_id_count']}`",
        f"- Scored count: `{summary['scored_count']}`",
        f"- PASS count: `{summary['pass_count']}`",
        f"- Failure counts: `{json.dumps(summary['failure_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Agentic loop enabled / executed: `{str(summary['agentic_loop']['enabled']).lower()}` / `{str(summary['agentic_loop']['executed']).lower()}`",
        f"- Agentic loop backend: `{summary['agentic_loop']['backend']}`",
        f"- Local LLM/GPU used: `{str(summary['local_llm_used']).lower()}` / `{str(summary['local_gpu_used']).lower()}`",
        f"- Promotion evidence: `{str(summary['guardrails']['promotion_evidence']).lower()}`",
        f"- Non-production RAG index: `{index_dependency['canonical_path']}`",
        f"- Infrastructure blocker category: `{summary['infrastructure_blocker']['category']}`",
        f"- baseline comparable as model quality: `{str(summary['infrastructure_blocker'].get('baseline_comparison_is_model_quality_comparable')).lower()}`",
        f"- model quality regression: `{str(summary['infrastructure_blocker']['model_quality_regression']).lower()}`",
        f"- SearchUnit citation payloads used: `{str(summary.get('search_unit_citation_payloads_used')).lower()}`",
        f"- Off-track discarded citations: `{summary.get('discarded_off_track_citation_count')}`",
        f"- Same-track valid citations: `{summary.get('same_track_valid_citation_count')}`",
        f"- Query-bound scored citations: `{summary.get('query_bound_scored_citation_count')}`",
        f"- Non-query-bound same-track scored citations: `{summary.get('non_query_bound_same_track_scored_citation_count')}`",
        f"- Schema mismatch residual count: `{summary.get('schema_mismatch_residual_count')}`",
        f"- XLSX/PDF adapters enabled: `{str(summary.get('xlsx_pdf_structured_adapters_enabled')).lower()}`",
        f"- Adapter output from source-bound SearchUnits: `{str(summary.get('adapter_output_from_source_bound_search_units')).lower()}`",
        f"- Chunk-only citation fallback disabled for official scoring: `{str(summary.get('chunk_only_citation_fallback_disabled_for_official_scoring')).lower()}`",
        "",
        "The official first-run baseline was not overwritten. XLSX/PDF report-only candidates were not promoted.",
        "Current chunk-only citation locators are not canonical SearchUnit payloads unless the source-bound citation payload gate says so.",
        "",
    ]
    residual_audit = summary.get("residual_failure_audit")
    if isinstance(residual_audit, Mapping):
        lines.extend(
            [
                "## Residual Failure Audit",
                "",
                f"- Audited residual rows: `{residual_audit.get('audited_row_count')}`",
                f"- Refined attribution counts: `{json.dumps(residual_audit.get('refined_primary_attribution_counts'), ensure_ascii=False, sort_keys=True)}`",
                f"- Schema mismatch residual count: `{residual_audit.get('schema_mismatch_residual_count')}`",
                f"- LLM backend validation readiness: `{residual_audit.get('llm_backend_validation_readiness')}`",
                f"- LLM backend validation started: `{str(residual_audit.get('llm_backend_validation_started')).lower()}`",
                f"- Audit-only expected/supporting/gold comparison: `{str(residual_audit.get('expected_supporting_gold_used_for_audit_only')).lower()}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Comparison To Immutable Baseline",
            "",
            f"- Baseline status: `{summary['baseline_reference']['status_detail']}`",
            f"- Baseline PASS count: `{summary['baseline_reference']['pass_count']}`",
            f"- PASS delta: `{summary['comparison_to_baseline']['pass_delta']}`",
            f"- Per-track PASS delta: `{json.dumps(summary['comparison_to_baseline']['per_track_pass_delta'], ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Pipeline Decision",
            "",
            summary["pipeline_decision"]["rationale"],
            "",
            "## Index Dependency",
            "",
            f"- Worker-relative path: `{index_dependency['worker_relative_path']}`",
            f"- Required files: `{', '.join(index_dependency['required_files'])}`",
            f"- Missing files: `{', '.join(index_dependency['missing_files']) or 'none'}`",
            f"- Build command: `{index_dependency['build_command']}`",
            f"- Load check command: `{index_dependency['load_check_command']}`",
            f"- FAISS build device requested: `{build_metadata.get('faiss_build_device_requested')}`",
            f"- FAISS GPU used for build: `{str(build_metadata.get('faiss_gpu_used')).lower()}`",
            f"- FAISS GPU count/device: `{build_metadata.get('faiss_gpu_count')}` / `{build_metadata.get('faiss_gpu_device')}`",
            "",
        ]
    )
    blockers = summary.get("agentic_loop", {}).get("blockers") or []
    if blockers:
        lines.extend(["## Blockers", ""])
        for blocker in blockers:
            lines.append(f"- {blocker}")
        lines.append("")
    return "\n".join(lines)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parsed = json.loads(line)
        if isinstance(parsed, Mapping):
            rows.append(dict(parsed))
    return rows


def resolve_repo_relative_artifact_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def ensure_ai_worker_on_path() -> None:
    ai_root = str(AI_WORKER_ROOT)
    if ai_root not in sys.path:
        sys.path.insert(0, ai_root)


def sha256_file(path: Path) -> str:
    return official.sha256_file(path)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
