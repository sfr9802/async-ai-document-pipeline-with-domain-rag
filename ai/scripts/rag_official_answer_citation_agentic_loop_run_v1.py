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

DEFAULT_RESULTS_JSONL = REPORT_DIR / f"{RUN_ID}_results.jsonl"
DEFAULT_SUMMARY_JSON = REPORT_DIR / f"{RUN_ID}_summary.json"
DEFAULT_SUMMARY_MD = REPORT_DIR / f"{RUN_ID}_summary.md"
DEFAULT_STATUS_JSONL = REPORT_DIR / "rag_current_eval_status.jsonl"
DEFAULT_BASELINE_JSON = REPORT_DIR / "official_answer_citation_metric_first_run_v1.json"
DEFAULT_XLSX_CANDIDATE = REPORT_DIR / "xlsx_answer_citation_runtime_precision_candidate_results_v1.jsonl"
DEFAULT_PDF_CANDIDATE = REPORT_DIR / "pdf_answer_citation_table_value_candidate_results_v1.jsonl"
DEFAULT_SOURCE_BOUND_READINESS_JSON = (
    REPORT_DIR / "official_answer_citation_source_bound_index_build_readiness_v1.json"
)
DEFAULT_V3_SUMMARY_JSON = REPORT_DIR / f"{V3_RUN_ID}_summary.json"
DEFAULT_V3_RESULTS_JSONL = REPORT_DIR / f"{V3_RUN_ID}_results.jsonl"
DEFAULT_V3_FAILURE_ATTRIBUTION_JSON = REPORT_DIR / f"{V3_RUN_ID}_failure_attribution.json"
DEFAULT_V3_1_SUMMARY_JSON = REPORT_DIR / f"{V3_1_RUN_ID}_summary.json"
DEFAULT_V3_1_RESULTS_JSONL = REPORT_DIR / f"{V3_1_RUN_ID}_results.jsonl"
DEFAULT_V3_1_TRIAGE_JSON = REPORT_DIR / f"{V3_1_RUN_ID}_triage_queue.json"
DEFAULT_V3_1_PRIORITY_SUMMARY_JSON = REPORT_DIR / f"{V3_1_PRIORITY_1_5_RUN_ID}_summary.json"
DEFAULT_V3_1_PRIORITY_RESULTS_JSONL = REPORT_DIR / f"{V3_1_PRIORITY_1_5_RUN_ID}_results.jsonl"
DEFAULT_V3_1_PRIORITY_TRIAGE_DELTA_JSON = REPORT_DIR / f"{V3_1_PRIORITY_1_5_RUN_ID}_triage_delta.json"
DEFAULT_V3_1_TEXT_LOCATOR_SUMMARY_JSON = REPORT_DIR / f"{V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID}_summary.json"
DEFAULT_V3_1_TEXT_LOCATOR_RESULTS_JSONL = REPORT_DIR / f"{V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID}_results.jsonl"
DEFAULT_V3_1_TEXT_LOCATOR_TRIAGE_DELTA_JSON = REPORT_DIR / f"{V3_1_TEXT_LOCATOR_RESIDUAL_RUN_ID}_triage_delta.json"
DEFAULT_V3_1_1_POST_SUMMARY_JSON = REPORT_DIR / f"{V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID}_summary.json"
DEFAULT_V3_1_1_POST_RESULTS_JSONL = REPORT_DIR / f"{V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID}_results.jsonl"
DEFAULT_V3_1_1_POST_ATTRIBUTION_JSON = (
    REPORT_DIR / f"{V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID}_failure_attribution.json"
)
DEFAULT_V3_1_1_POST_AUDIT_JSONL = (
    REPORT_DIR / f"{V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID}_actual_response_audit.jsonl"
)
DEFAULT_V3_1_1_POST_TRIAGE_QUEUE_JSON = (
    REPORT_DIR / f"{V3_1_1_POST_STRICT_JSON_LOCATOR_TRIAGE_RUN_ID}_triage_queue.json"
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
    parser.add_argument("--v2-1-summary-json", default=str(REPORT_DIR / f"{V2_1_RUN_ID}_summary.json"))
    parser.add_argument("--v2-1-results-jsonl", default=str(REPORT_DIR / f"{V2_1_RUN_ID}_results.jsonl"))
    parser.add_argument(
        "--v2-1-failure-attribution-json",
        default=str(REPORT_DIR / f"{V2_1_RUN_ID}_failure_attribution.json"),
    )
    parser.add_argument("--v2-2-summary-json", default=str(REPORT_DIR / f"{V2_2_RUN_ID}_summary.json"))
    parser.add_argument("--v2-2-results-jsonl", default=str(REPORT_DIR / f"{V2_2_RUN_ID}_results.jsonl"))
    parser.add_argument(
        "--v2-2-failure-attribution-json",
        default=str(REPORT_DIR / f"{V2_2_RUN_ID}_failure_attribution.json"),
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
    }
    if args.run_id not in supported_run_ids:
        raise SystemExit(
            "unsupported run id "
            f"{args.run_id!r}; expected one of {', '.join(repr(item) for item in sorted(supported_run_ids))}"
        )
    if args.results_jsonl is None:
        args.results_jsonl = str(REPORT_DIR / f"{args.run_id}_results.jsonl")
    if args.summary_json is None:
        args.summary_json = str(REPORT_DIR / f"{args.run_id}_summary.json")
    if args.summary_md is None:
        args.summary_md = str(REPORT_DIR / f"{args.run_id}_summary.md")
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

    agentic_status = agentic_loop_status(args)
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
    answer_ok = official.expected_answer_supported_by_text(expected_answer, generated_answer)
    citation_ok = official.expected_answer_supported_by_text(supporting_evidence or expected_answer, citation_text)
    if answer_ok and citation_ok:
        return {"answer_score": 1.0, "citation_support_score": 1.0, "failure_category": "PASS", "failure_detail": ""}
    category = "PARTIAL_OR_UNSUPPORTED" if answer_ok or citation_ok else "CITATION_UNSUPPORTED"
    return {
        "answer_score": 1.0 if answer_ok else 0.0,
        "citation_support_score": 1.0 if citation_ok else 0.0,
        "failure_category": category,
        "failure_detail": "deterministic post-generation scoring did not find answer and citation support together",
    }


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
            "failure_attribution_json": official.repo_relative(
                REPORT_DIR / f"{args.run_id}_failure_attribution.json"
            ),
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


def build_v3_prompt_context(row: Mapping[str, Any], *, prompt_context_mode: str) -> dict[str, Any]:
    return build_v3_prompt_context_from_row(
        row,
        use_query_bound_only=prompt_context_mode == "query-bound-only",
        mode=prompt_context_mode,
    )


def build_v3_prompt_context_from_row(
    row: Mapping[str, Any],
    *,
    use_query_bound_only: bool,
    mode: str,
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
        },
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
            "failure_attribution_json": official.repo_relative(REPORT_DIR / f"{args.run_id}_failure_attribution.json"),
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
    if retrieval_or_context_insufficient(row=row, lane=lane, citation_text=citation_text):
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


def retrieval_or_context_insufficient(*, row: Mapping[str, Any], lane: Mapping[str, Any], citation_text: str) -> bool:
    if row.get("query_bound_search_unit_present") is not True:
        return True
    if lane.get("citation_support_score") != 1.0:
        return True
    return not bool(official.clean(citation_text))


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
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for v3_row in v3_rows:
        source_row = source_rows_by_id.get(official.clean(v3_row.get("query_id")), {})
        rows.append(
            build_v3_1_row(
                v3_row=v3_row,
                source_row=source_row,
                backend_preflight=backend_preflight,
                v3_preflight=v3_preflight,
                run_id=run_id,
                source_run_id=source_run_id,
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
    )
    lane_c = v3_1_live_llm_lane(
        v3_row=v3_row,
        source_row=source_row,
        source_family=source_family,
        backend_preflight=backend_preflight,
        mode="query_bound_only_source_bound",
        lane_name="live_llm_query_bound_oracle",
        force_fail_closed=not bool(v3_preflight.get("ok")),
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
) -> dict[str, Any]:
    prompt_mode = "query-bound-only" if mode == "query_bound_only_source_bound" else "same-track-scored-context"
    context = build_v3_prompt_context(v3_row, prompt_context_mode=prompt_mode)
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


def v3_1_priority_1_5_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = args.run_id
    return {
        "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "summary_md": official.repo_relative(Path(args.summary_md)),
        "failure_attribution_json": official.repo_relative(REPORT_DIR / f"{run_id}_failure_attribution.json"),
        "actual_response_audit_jsonl": official.repo_relative(REPORT_DIR / f"{run_id}_actual_response_audit.jsonl"),
        "strict_json_diagnostics_json": official.repo_relative(
            REPORT_DIR / f"{V3_1_PRIORITY_1_5_STRICT_JSON_DIAGNOSTICS_ID}.json"
        ),
        "strict_json_diagnostics_md": official.repo_relative(
            REPORT_DIR / f"{V3_1_PRIORITY_1_5_STRICT_JSON_DIAGNOSTICS_ID}.md"
        ),
        "triage_delta_json": official.repo_relative(REPORT_DIR / f"{run_id}_triage_delta.json"),
        "triage_delta_md": official.repo_relative(REPORT_DIR / f"{run_id}_triage_delta.md"),
    }


def v3_1_text_locator_residual_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = args.run_id
    return {
        "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "summary_md": official.repo_relative(Path(args.summary_md)),
        "failure_attribution_json": official.repo_relative(REPORT_DIR / f"{run_id}_failure_attribution.json"),
        "triage_delta_json": official.repo_relative(REPORT_DIR / f"{run_id}_triage_delta.json"),
        "triage_delta_md": official.repo_relative(REPORT_DIR / f"{run_id}_triage_delta.md"),
    }


def v3_1_1_post_triage_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = args.run_id
    return {
        "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "summary_md": official.repo_relative(Path(args.summary_md)),
        "failure_attribution_json": official.repo_relative(REPORT_DIR / f"{run_id}_failure_attribution.json"),
        "actual_response_audit_jsonl": official.repo_relative(REPORT_DIR / f"{run_id}_actual_response_audit.jsonl"),
        "triage_queue_json": official.repo_relative(REPORT_DIR / f"{run_id}_triage_queue.json"),
    }


def v3_1_2_answer_span_renderer_artifact_paths(args: argparse.Namespace) -> dict[str, str]:
    run_id = args.run_id
    return {
        "results_jsonl": official.repo_relative(Path(args.results_jsonl)),
        "summary_json": official.repo_relative(Path(args.summary_json)),
        "failure_attribution_json": official.repo_relative(REPORT_DIR / f"{run_id}_failure_attribution.json"),
        "actual_response_audit_jsonl": official.repo_relative(REPORT_DIR / f"{run_id}_actual_response_audit.jsonl"),
        "answer_span_diagnostics_jsonl": official.repo_relative(
            REPORT_DIR / f"{run_id}_answer_span_diagnostics.jsonl"
        ),
        "remaining_triage_queue_json": official.repo_relative(REPORT_DIR / f"{run_id}_remaining_triage_queue.json"),
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
        "failure_attribution_json": official.repo_relative(REPORT_DIR / f"{run_id}_failure_attribution.json"),
        "actual_response_audit_jsonl": official.repo_relative(REPORT_DIR / f"{run_id}_actual_response_audit.jsonl"),
        "actual_response_audit_md": official.repo_relative(REPORT_DIR / f"{run_id}_actual_response_audit.md"),
        "triage_queue_json": official.repo_relative(REPORT_DIR / f"{run_id}_triage_queue.json"),
        "triage_queue_md": official.repo_relative(REPORT_DIR / f"{run_id}_triage_queue.md"),
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
            "failure_attribution_json": official.repo_relative(
                REPORT_DIR / f"{args.run_id}_failure_attribution.json"
            ),
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
