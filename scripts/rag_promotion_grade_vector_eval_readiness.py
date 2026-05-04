"""Check readiness for a future promotion-grade full72 vector eval.

The current full72 vector diagnostic can explain quality failures, but it must
not be treated as promotion evidence. This report keeps that guard in place
while checking whether the candidate scope, source-qualified inputs, baseline,
and query-evidence cleanup are ready for a later promotion-evidence run.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_RETRIEVAL_REPORT = Path("reports/rag_retrieval_eval_full72_vector_diagnostic_report.json")
DEFAULT_QUALITY_BREAKDOWN = Path("reports/rag_retrieval_full72_vector_quality_breakdown.json")
DEFAULT_CLEANUP_PLAN = Path("reports/rag_full72_query_evidence_cleanup_plan.json")
DEFAULT_METRICS_REPORT = Path("reports/rag_ingestion_a5_promotion_gate_metrics.json")
DEFAULT_SOURCE_QUALIFIED_READINESS_REPORT = Path("reports/a5_c2_source_qualified_report_contract_readiness.json")
DEFAULT_CONSISTENCY_REPORT = Path("reports/pdf_xlsx_candidate_embedding_consistency_report.json")
DEFAULT_CANDIDATE_SCOPE_REPORT = Path("reports/rag_candidate_scope_path_readiness.json")
DEFAULT_C3_READINESS_REPORT = Path("reports/a5_c3_immutable_baseline_readiness.json")
DEFAULT_GATE_REPORT = Path("reports/rag_ingestion_a5_promotion_gate_report.json")
DEFAULT_OUTPUT = Path("reports/rag_promotion_grade_vector_eval_readiness.json")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_readiness(args)
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0 if payload["status"] == "READY" else 2


def build_readiness(args: argparse.Namespace) -> dict[str, Any]:
    missing_reports: list[str] = []
    retrieval = read_optional_json(Path(args.retrieval_report), missing_reports, "retrieval_report")
    breakdown = read_optional_json(Path(args.quality_breakdown), missing_reports, "quality_breakdown_report")
    cleanup = read_optional_json(Path(args.cleanup_plan), missing_reports, "cleanup_plan")
    metrics_report = read_optional_json(Path(args.metrics_report), missing_reports, "metrics_report")
    source_qualified = read_optional_json(
        Path(args.source_qualified_readiness_report),
        missing_reports,
        "source_qualified_readiness_report",
    )
    consistency = read_optional_json(Path(args.consistency_report), missing_reports, "consistency_report")
    candidate_scope = read_optional_json(Path(args.candidate_scope_report), missing_reports, "candidate_scope_report")
    c3 = read_optional_json(Path(args.c3_readiness_report), missing_reports, "c3_readiness_report")
    gate = read_optional_json(Path(args.gate_report), missing_reports, "gate_report")

    metrics = dict(metrics_report.get("metrics") or {}) if isinstance(metrics_report, Mapping) else {}
    backend_identity = dict(retrieval.get("backend_identity") or {}) if isinstance(retrieval, Mapping) else {}
    blockers: list[str] = []
    warnings: list[str] = []

    blockers.extend(missing_reports)
    if retrieval.get("retrieval_backend") != "vector":
        blockers.append("retrieval report must be vector-backed")
    if backend_identity.get("backend") == "library_search" or retrieval.get("retrieval_backend") == "library_search":
        blockers.append("library_search report cannot be promotion-grade vector evidence")
    if backend_identity.get("backend") and backend_identity.get("backend") != "faiss":
        blockers.append("backend_identity.backend must be faiss for this readiness check")
    namespace = backend_identity.get("index_namespace_filter")
    if not namespace:
        blockers.append("backend_identity.index_namespace_filter is required")
    elif namespace != args.candidate_index_version:
        blockers.append("backend_identity.index_namespace_filter must match candidate index version")
    if retrieval.get("promotion_evidence") is not True:
        blockers.append("current retrieval report is diagnostic-only; rerun with --promotion-evidence after cleanup")
    if retrieval.get("evidence_role") == "diagnostic":
        warnings.append("current retrieval report evidence_role=diagnostic and is usable only for cleanup analysis")

    gate_missing_present = "gate_input_missing_count" in metrics or "gate_input_missing_count" in metrics_report
    gate_missing = int(metrics.get("gate_input_missing_count") or metrics_report.get("gate_input_missing_count") or 0)
    if not gate_missing_present:
        blockers.append("source-qualified gate_input_missing_count is required")
    if gate_missing != 0:
        blockers.append("source-qualified gate_input_missing_count must be 0")
    if metrics.get("retrieval_backend") == "library_search":
        blockers.append("source-qualified metrics must not come from library_search retrieval")
    if metrics.get("promotion_evidence") is not True:
        blockers.append("source-qualified retrieval metrics are not promotion evidence")
    if source_qualified.get("status") != "PASS":
        blockers.append("source-qualified gate input readiness must PASS")
    source_qualified_missing_present = "gate_input_missing_count" in source_qualified
    if not source_qualified_missing_present:
        blockers.append("source-qualified readiness gate_input_missing_count is required")
    elif int(source_qualified.get("gate_input_missing_count") or 0) != 0:
        blockers.append("source-qualified readiness gate_input_missing_count must be 0")
    if source_qualified.get("retrieval_backend") == "library_search":
        blockers.append("source-qualified readiness must not use library_search")
    if source_qualified.get("derived_metric_sources"):
        blockers.append("source-qualified readiness derived_metric_sources must be empty")

    unresolved_cleanup = int(cleanup.get("unresolved_query_count") or 0)
    if unresolved_cleanup != 0:
        blockers.append("query-level evidence cleanup must have unresolved_query_count=0")
    if cleanup.get("promotion_evidence") is not False:
        blockers.append("cleanup plan must be diagnostic-only promotion_evidence=false")

    if consistency.get("status") != "PASS":
        blockers.append("candidate embedding consistency report must PASS")
    if candidate_scope.get("status") != "PASS":
        blockers.append("candidate promotion-scope path readiness must PASS")
    if c3.get("status") != "PASS":
        blockers.append("C3 immutable baseline readiness must PASS")
    if c3.get("candidate_snapshot") is True:
        blockers.append("candidate snapshot baseline cannot be used")
    if c3.get("baseline_type") == "INITIAL_BASELINE_BOOTSTRAP" and c3.get("promotion_evidence") is not False:
        blockers.append("INITIAL_BASELINE_BOOTSTRAP must remain promotion_evidence=false")

    threshold_reasons = list(gate.get("reasons") or [])
    quality_reasons = [
        reason for reason in threshold_reasons
        if "must be >=" in str(reason) or "must be <=" in str(reason)
    ]

    return {
        "run_id": utc_run_id(),
        "status": "READY" if not blockers else "BLOCKED",
        "report_role": "promotion_grade_vector_eval_readiness",
        "promotion_evidence": False,
        "candidate_index_version": args.candidate_index_version,
        "baseline_index_version": args.baseline_index_version,
        "current_retrieval_report": str(Path(args.retrieval_report)),
        "quality_breakdown_report": str(Path(args.quality_breakdown)),
        "cleanup_plan": str(Path(args.cleanup_plan)),
        "metrics_report": str(Path(args.metrics_report)),
        "source_qualified_readiness_report": str(Path(args.source_qualified_readiness_report)),
        "candidate_embedding_consistency_report": str(Path(args.consistency_report)),
        "candidate_scope_path_readiness_report": str(Path(args.candidate_scope_report)),
        "c3_immutable_baseline_readiness_report": str(Path(args.c3_readiness_report)),
        "promotion_gate_report": str(Path(args.gate_report)),
        "readiness_summary": {
            "vector_backend": retrieval.get("retrieval_backend"),
            "backend_identity": backend_identity,
            "current_report_promotion_evidence": retrieval.get("promotion_evidence"),
            "current_report_evidence_role": retrieval.get("evidence_role"),
            "source_qualified_gate_input_missing_count": gate_missing,
            "source_qualified_readiness_status": source_qualified.get("status"),
            "cleanup_status": cleanup.get("status"),
            "unresolved_query_count": unresolved_cleanup,
            "candidate_embedding_consistency_status": consistency.get("status"),
            "candidate_scope_status": candidate_scope.get("status"),
            "c3_status": c3.get("status"),
            "gate_decision": gate.get("decision"),
            "quality_threshold_reasons": quality_reasons,
        },
        "source_qualified_gate_input": {
            "status": "PASS" if gate_missing_present and gate_missing == 0 and source_qualified.get("status") == "PASS" else "FAIL",
            "gate_input_missing_count": gate_missing,
            "gate_input_missing": metrics.get("gate_input_missing") or metrics_report.get("gate_input_missing") or [],
            "readiness_status": source_qualified.get("status"),
            "readiness_gate_input_missing_count": source_qualified.get("gate_input_missing_count"),
            "readiness_gate_input_missing": source_qualified.get("gate_input_missing") or [],
            "readiness_derived_metric_sources": source_qualified.get("derived_metric_sources") or {},
            "source_reports": metrics.get("source_reports") or [],
        },
        "global_path_hygiene_separation": {
            "candidate_scope_status": candidate_scope.get("status"),
            "decision": (
                "Candidate promotion-scope readiness is checked here. Global legacy parser/path drift "
                "belongs to the separate hygiene backlog and is not mixed into this readiness status."
            ),
        },
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "next_allowed_step": (
            "After query cleanup resolves to zero unresolved rows, rerun vector eval with --promotion-evidence "
            "and rebuild source-qualified metrics. Do not use this diagnostic report as promotion evidence."
        ),
        "notes": [
            "This readiness check does not execute promotion.",
            "It does not relax thresholds, add hybrid search, add reranking, or change parser behavior.",
            "Library-search reports and candidate snapshots are rejected as promotion-grade vector evidence.",
        ],
    }


def read_optional_json(path: Path, missing: list[str], label: str) -> dict[str, Any]:
    if not path.exists():
        missing.append(f"{label} missing: {path}")
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        missing.append(f"{label} must be a JSON object: {path}")
        return {}
    return payload


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_report(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval-report", default=str(DEFAULT_RETRIEVAL_REPORT))
    parser.add_argument("--quality-breakdown", default=str(DEFAULT_QUALITY_BREAKDOWN))
    parser.add_argument("--cleanup-plan", default=str(DEFAULT_CLEANUP_PLAN))
    parser.add_argument("--metrics-report", default=str(DEFAULT_METRICS_REPORT))
    parser.add_argument("--source-qualified-readiness-report", default=str(DEFAULT_SOURCE_QUALIFIED_READINESS_REPORT))
    parser.add_argument("--consistency-report", default=str(DEFAULT_CONSISTENCY_REPORT))
    parser.add_argument("--candidate-scope-report", default=str(DEFAULT_CANDIDATE_SCOPE_REPORT))
    parser.add_argument("--c3-readiness-report", default=str(DEFAULT_C3_READINESS_REPORT))
    parser.add_argument("--gate-report", default=str(DEFAULT_GATE_REPORT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--candidate-index-version", default="rag-ingestion-v2-candidate")
    parser.add_argument("--baseline-index-version", default="initial-full72-vector-baseline-v0")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
