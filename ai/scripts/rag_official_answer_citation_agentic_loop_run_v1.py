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
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
if str(AI_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_WORKER_ROOT))

import rag_official_answer_citation_metric_first_run_v1 as official  # noqa: E402


REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
RUN_ID = "official_answer_citation_agentic_loop_run_v1"

DEFAULT_RESULTS_JSONL = REPORT_DIR / f"{RUN_ID}_results.jsonl"
DEFAULT_SUMMARY_JSON = REPORT_DIR / f"{RUN_ID}_summary.json"
DEFAULT_SUMMARY_MD = REPORT_DIR / f"{RUN_ID}_summary.md"
DEFAULT_STATUS_JSONL = REPORT_DIR / "rag_current_eval_status.jsonl"
DEFAULT_BASELINE_JSON = REPORT_DIR / "official_answer_citation_metric_first_run_v1.json"
DEFAULT_XLSX_CANDIDATE = REPORT_DIR / "xlsx_answer_citation_runtime_precision_candidate_results_v1.jsonl"
DEFAULT_PDF_CANDIDATE = REPORT_DIR / "pdf_answer_citation_table_value_candidate_results_v1.jsonl"
DEFAULT_RAG_INDEX_DIR = AI_WORKER_ROOT / "eval" / "indexes" / "rag-data"

GENERATION_PIPELINE_UNAVAILABLE = "GENERATION_PIPELINE_UNAVAILABLE"
AGENTIC_GENERATION_ROW_FAILED = "AGENTIC_GENERATION_ROW_FAILED"
NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING = "NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING"
REGISTRY_BACKED_RAG_CAPABILITY_UNAVAILABLE = "REGISTRY_BACKED_RAG_CAPABILITY_UNAVAILABLE"
OFFICIAL_DENOMINATOR_VALIDATION_FAILED = "OFFICIAL_DENOMINATOR_VALIDATION_FAILED"
INDEX_REQUIRED_FILES = ("faiss.index", "build.json", "ingest_manifest.json")
INDEX_BUILD_COMMAND = (
    "cd ai && AIPIPELINE_WORKER_RAG_FAISS_BUILD_DEVICE=cuda "
    "python -m scripts.build_rag_index --fixture all "
    "--index-version official-answer-citation-agentic-loop-v1-nonprod-fixture-all"
)
INDEX_LOAD_CHECK_COMMAND = (
    "cd ai && python -m scripts.doctor --json "
    "--only schemas,faiss_index,build_json,runtime_model_match"
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary, rows = run_measurement(args)
    write_jsonl(Path(args.results_jsonl), rows)
    summary["artifact_paths"]["results_jsonl_sha256"] = sha256_file(Path(args.results_jsonl))
    write_json(Path(args.summary_json), summary)
    Path(args.summary_md).write_text(render_markdown(summary), encoding="utf-8")
    append_status_event(Path(args.status_jsonl), summary)
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
    parser.add_argument("--results-jsonl", default=str(DEFAULT_RESULTS_JSONL))
    parser.add_argument("--summary-json", default=str(DEFAULT_SUMMARY_JSON))
    parser.add_argument("--summary-md", default=str(DEFAULT_SUMMARY_MD))
    parser.add_argument("--status-jsonl", default=str(DEFAULT_STATUS_JSONL))
    parser.add_argument("--agent-loop-backend", choices=("legacy", "graph"), default="legacy")
    parser.add_argument("--agent-max-iter", type=int, default=3)
    parser.add_argument("--agent-max-total-ms", type=int, default=15_000)
    parser.add_argument("--agent-max-llm-tokens", type=int, default=4_000)
    parser.add_argument("--agent-min-stop-confidence", type=float, default=0.75)
    parser.add_argument(
        "--rag-index-dir",
        default=str(DEFAULT_RAG_INDEX_DIR),
        help=(
            "Canonical non-production worker RAG index directory. Relative paths "
            "are resolved from ai/, so the worker-relative default is eval/indexes/rag-data."
        ),
    )
    args = parser.parse_args(argv)
    if args.run_id != RUN_ID:
        raise SystemExit(f"unsupported run id {args.run_id!r}; expected {RUN_ID!r}")
    return args


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
    index_dependency = inspect_rag_index_dependency(Path(args.rag_index_dir))
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
            None if index_dependency["satisfied"] else NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING
        ),
        "index_dependency": index_dependency,
        "config": {
            "agent_loop": "on",
            "agent_loop_backend": args.agent_loop_backend,
            "agent_max_iter": args.agent_max_iter,
            "agent_max_total_ms": args.agent_max_total_ms,
            "agent_max_llm_tokens": args.agent_max_llm_tokens,
            "agent_min_stop_confidence": args.agent_min_stop_confidence,
            "llm_backend": "noop",
            "rag_index_dir": index_dependency["canonical_path"],
        },
    }
    try:
        from app.capabilities.agent.loop import AgentLoopController  # noqa: F401

        if args.agent_loop_backend == "graph":
            from app.capabilities.agent.graph_loop import AgentLoopGraph  # noqa: F401
        status["implemented"] = True
    except Exception as exc:  # pragma: no cover - import availability is environment dependent.
        status["blockers"].append(f"agent loop import failed: {type(exc).__name__}: {exc}")
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


def inspect_rag_index_dependency(index_dir_arg: Path) -> dict[str, Any]:
    index_dir = resolve_worker_path(index_dir_arg)
    missing_files = [name for name in INDEX_REQUIRED_FILES if not (index_dir / name).exists()]
    build_metadata: dict[str, Any] = {}
    build_path = index_dir / "build.json"
    if build_path.exists():
        try:
            build = json.loads(build_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            build = {}
        for key in (
            "faiss_build_device_requested",
            "faiss_gpu_used",
            "faiss_gpu_count",
            "faiss_gpu_device",
        ):
            if key in build:
                build_metadata[key] = build[key]
    return {
        "canonical_path": official.repo_relative(index_dir),
        "worker_relative_path": worker_relative(index_dir),
        "configured_path": str(index_dir_arg),
        "required_files": list(INDEX_REQUIRED_FILES),
        "missing_files": missing_files,
        "exists": index_dir.exists(),
        "satisfied": not missing_files,
        "build_command": INDEX_BUILD_COMMAND,
        "load_check_command": INDEX_LOAD_CHECK_COMMAND,
        "expected_provenance": (
            "non-production worker RAG index only; candidate and production index paths are not valid substitutes"
        ),
        "production_index_path_used": False,
        "candidate_index_path_used": False,
        "blocker_category": None if not missing_files else NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING,
        "build_metadata": build_metadata,
    }


def resolve_worker_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return AI_WORKER_ROOT / path


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
            generated_answer = synthesizer.synthesize(question, outcome)
            chunks = list(outcome.aggregated_chunks)
            score = score_generated_row(row, generated_answer, chunks)
            out.append(
                result_row(
                    row,
                    args=args,
                    generated_answer=generated_answer,
                    generated_citations=citations_from_chunks(chunks),
                    retrieved_evidence=evidence_from_chunks(chunks),
                    answer_score=score["answer_score"],
                    citation_support_score=score["citation_support_score"],
                    scoring_attempted=True,
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
    return {
        "schema_version": RUN_ID,
        "run_id": RUN_ID,
        "query_id": official.clean(row.get("query_id")),
        "track": official.clean(row.get("_track") or row.get("track")),
        "generated_answer": generated_answer,
        "generated_citations": generated_citations,
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
        "promotion_evidence": False,
    }


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


def citations_from_chunks(chunks: Sequence[Any]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for chunk in chunks[:5]:
        locator = {
            "chunk_id": getattr(chunk, "chunk_id", ""),
            "doc_id": getattr(chunk, "doc_id", ""),
            "search_unit_id": getattr(chunk, "search_unit_id", None),
            "source_file_id": getattr(chunk, "source_file_id", None),
            "source_file_name": getattr(chunk, "source_file_name", None),
            "page_start": getattr(chunk, "page_start", None),
            "page_end": getattr(chunk, "page_end", None),
        }
        citations.append(
            {
                "citation_text": official.clean(getattr(chunk, "text", ""))[:500],
                "locator": {key: value for key, value in locator.items() if value not in (None, "")},
            }
        )
    return citations


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
    classification = (
        "official_next_run_measurement"
        if status == "PASS" or status == "BLOCKED_OR_PARTIAL"
        else "diagnostic_actual_generation_blocked_pipeline_unavailable"
    )
    infrastructure_category = (
        blocked_failure_category(validation_errors, agentic_status)
        if status == "BLOCKED_ACTUAL_GENERATION_PIPELINE_UNAVAILABLE"
        else None
    )
    model_quality_comparable = bool(scored_count and any(row["agentic_loop_executed"] for row in rows))
    agentic_loop_public = {
        key: value
        for key, value in agentic_status.items()
        if not key.startswith("_")
    }
    agentic_loop_public["executed"] = any(row["agentic_loop_executed"] for row in rows)
    agentic_loop_public["steps_count"] = sum(int(row.get("agentic_loop_steps_count") or 0) for row in rows)
    return {
        "schema_version": RUN_ID,
        "run_id": RUN_ID,
        "generated_at": utc_timestamp(),
        "status": status,
        "measurement_classification": classification,
        "official_metric_execution_started": True,
        "actual_generation_execution_started": any(row["agentic_loop_executed"] for row in rows),
        "denominator_count": len(consumed["rows"]),
        "result_count": len(rows),
        "unique_query_id_count": len({row["query_id"] for row in rows}),
        "scored_count": scored_count,
        "pass_count": pass_count,
        "failure_counts": failure_counts,
        "per_track_counts": per_track,
        "non_production_rag_index_dependency": agentic_status.get(
            "index_dependency",
            inspect_rag_index_dependency(Path(args.rag_index_dir)),
        ),
        "infrastructure_blocker": {
            "category": infrastructure_category,
            "domain": "infrastructure" if infrastructure_category else None,
            "model_quality_regression": False,
            "baseline_comparison_is_model_quality_comparable": model_quality_comparable,
        },
        "agentic_loop": agentic_loop_public,
        "local_llm_used": False,
        "local_gpu_used": any(bool(row.get("local_gpu_used")) for row in rows),
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
            "selected_entrypoint": "registry-backed RAG retriever + AgentLoopController when available",
            "rationale": (
                "No canonical official live answer-generation runner exists for the answer/citation denominator. "
                "This runner validates the official denominator and attempts the implemented agent loop against "
                "the actual registry-backed RAG pipeline, then fails closed if the pipeline is unavailable."
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
        "non_production_rag_index_dependency": summary["non_production_rag_index_dependency"],
        "infrastructure_blocker": summary["infrastructure_blocker"],
        "agentic_loop": summary["agentic_loop"],
        "local_llm_used": summary["local_llm_used"],
        "local_gpu_used": summary["local_gpu_used"],
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


def render_markdown(summary: Mapping[str, Any]) -> str:
    index_dependency = summary["non_production_rag_index_dependency"]
    build_metadata = (
        index_dependency.get("build_metadata", {})
        if isinstance(index_dependency, Mapping)
        else {}
    )
    lines = [
        "# Official Answer/Citation Agentic Loop Run v1",
        "",
        f"- Run id: `{summary['run_id']}`",
        f"- Status: `{summary['status']}`",
        f"- Measurement classification: `{summary['measurement_classification']}`",
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
        f"- model quality regression: `{str(summary['infrastructure_blocker']['model_quality_regression']).lower()}`",
        "",
        "The official first-run baseline was not overwritten. XLSX/PDF report-only candidates were not promoted.",
        "",
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


def sha256_file(path: Path) -> str:
    return official.sha256_file(path)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
