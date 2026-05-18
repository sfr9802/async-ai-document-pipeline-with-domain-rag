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
import json
import os
import re
import sys
from collections import Counter
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
    write_json(Path(args.summary_json), summary)
    Path(args.summary_md).write_text(render_markdown(summary), encoding="utf-8")
    append_status_event(Path(args.status_jsonl), summary)
    append_failure_attribution_event(Path(args.status_jsonl), failure_attribution)
    print(
        json.dumps(
            {
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
                "summary_md": summary["artifact_paths"]["summary_md"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
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
    parser.add_argument("--llm-max-tokens", type=int, default=900)
    parser.add_argument("--llm-strict-json-retries", type=int, default=2)
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
    if args.run_id not in {RUN_ID, V2_RUN_ID, V2_1_RUN_ID, V2_2_RUN_ID, V3_RUN_ID}:
        raise SystemExit(
            f"unsupported run id {args.run_id!r}; expected {RUN_ID!r}, {V2_RUN_ID!r}, {V2_1_RUN_ID!r}, {V2_2_RUN_ID!r}, or {V3_RUN_ID!r}"
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
    return run_id in {V2_RUN_ID, V2_1_RUN_ID, V2_2_RUN_ID, V3_RUN_ID}


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
    max_tokens = int(getattr(args, "llm_max_tokens", 900) or 900)
    retries = int(getattr(args, "llm_strict_json_retries", 2) or 2)
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


def call_v3_llm_synthesis(
    *,
    prompt: str,
    backend_preflight: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    from rag_text_namu_local_llm_rewrite_v2 import call_local_llm_strict_json  # noqa: WPS433

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
    llm_answer = official.clean(parsed.get("answer") or parsed.get("rewritten_answer") or parsed.get("short_answer"))
    if not llm_answer:
        raise ValueError("LLM JSON did not include answer")
    context_ids = set(re.findall(r"search_unit_id=([^\s]+)", prompt))
    cited_ids = {
        official.clean(item)
        for item in parsed.get("cited_search_unit_ids") or []
        if official.clean(item)
    }
    if cited_ids and not cited_ids.issubset(context_ids):
        raise ValueError("LLM cited a search_unit_id outside prompt context")
    if parsed.get("answer_supported_by_context") is False:
        raise ValueError("LLM reported answer_supported_by_context=false")
    return llm_answer, {
        "strict_json": strict_json_meta,
        "cited_search_unit_ids": sorted(cited_ids),
        "answer_supported_by_context": parsed.get("answer_supported_by_context"),
    }


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


def build_v3_llm_prompt(row: Mapping[str, Any], context: Mapping[str, Any], *, question: str) -> str:
    lines = [
        "You are running a v3 comparable live measurement row for source-bound RAG answer synthesis.",
        "Use only the canonical source-bound SearchUnit citation payloads below. Return exactly one JSON object.",
        'Required JSON keys: "answer", "cited_search_unit_ids", "answer_supported_by_context".',
        f"query_id: {official.clean(row.get('query_id'))}",
        f"track: {official.clean(row.get('track'))}",
        f"question: {official.clean(question)}",
        f"prompt_context_mode: {official.clean((context.get('prompt_context_policy') or {}).get('mode'))}",
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
        "source_bound_official_denominator_index_design": attribution.get(
            "source_bound_official_denominator_index_design"
        ),
        "promotion_evidence": False,
    }
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
