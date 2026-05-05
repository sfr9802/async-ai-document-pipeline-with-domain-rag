"""Preflight readiness for a future XLSX-only promotion-grade vector eval.

This report does not create promotion evidence. It checks whether the reviewed
XLSX eval set is ready for a later explicit rerun while preserving baseline
lineage and diagnostic-only guardrails.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/rag_xlsx_promotion_grade_eval_readiness.json")
DEFAULT_LINEAGE_REPORT = Path("eval/reports/rag-ingestion/rag_candidate_index_lineage_report.json")
DEFAULT_REVIEW_DECISIONS = Path("eval/reports/rag-ingestion/rag_xlsx_query_evidence_review_decisions.json")
DEFAULT_CONSISTENCY_REPORT = Path("eval/reports/rag-ingestion/xlsx_candidate_embedding_consistency_report.json")
DEFAULT_SCOPE_REPORT = Path("eval/reports/rag-ingestion/xlsx_candidate_scope_report.json")
DEFAULT_DIAGNOSTIC_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_xlsx_vector_diagnostic_report.json")
DEFAULT_BASELINE_DESCRIPTOR = Path("eval/reports/rag-ingestion/initial_immutable_vector_baseline_descriptor.json")
DEFAULT_CLEANED_GOLD = Path("eval/eval_queries/gold_queries_xlsx_v1.csv")
DEFAULT_CANDIDATE_INDEX_VERSION = "rag-ingestion-v2-xlsx-candidate-v1"
DEFAULT_BASELINE_INDEX_VERSION = "initial-full72-vector-baseline-v0"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_readiness(args)
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0 if payload["status"] == "READY" else 2


def build_readiness(args: argparse.Namespace) -> dict[str, Any]:
    missing: list[str] = []
    lineage = read_optional_json(Path(args.lineage_report), missing, "lineage_report")
    decisions = read_optional_json(Path(args.review_decisions), missing, "review_decisions")
    consistency = read_optional_json(Path(args.consistency_report), missing, "consistency_report")
    scope = read_optional_json(Path(args.scope_report), missing, "scope_report")
    diagnostic = read_optional_json(Path(args.diagnostic_report), missing, "diagnostic_report")
    baseline = read_optional_json(Path(args.baseline_descriptor), missing, "baseline_descriptor")
    cleaned_path = Path(args.cleaned_gold)
    blockers = list(missing)
    warnings: list[str] = []

    review_unresolved = int(decisions.get("unreviewed_unresolved_query_count") or 0)
    source_unresolved = int(decisions.get("source_unresolved_query_count") or 0)
    cleaned_hash = (decisions.get("cleaned_eval_set") or {}).get("sha256")
    cleaned_rows = int((decisions.get("cleaned_eval_set") or {}).get("row_count") or 0)
    cleaned_dataset_id = (decisions.get("cleaned_eval_set") or {}).get("eval_dataset_id")
    cleaned_dataset_version = (decisions.get("cleaned_eval_set") or {}).get("eval_dataset_version")
    diagnostic_identity = diagnostic.get("backend_identity") or {}
    consistency_summary = consistency.get("scoped_summary") or {}
    lineage_baseline = lineage.get("immutable_baseline") or {}
    lineage_candidate = lineage.get("xlsx_candidate") or {}
    lineage_interpretation = lineage.get("lineage_interpretation") or {}

    if source_unresolved != 0:
        warnings.append("source cleanup plan still has unresolved rows; reviewed cleaned XLSX v1 is the rerun input")
    if review_unresolved != 0:
        blockers.append("review overlay must resolve every source unresolved XLSX query")
    if cleaned_rows <= 0:
        blockers.append("cleaned eval dataset must contain at least one row")
    if not cleaned_path.exists():
        blockers.append(f"cleaned eval dataset missing: {cleaned_path}")
    if not cleaned_hash:
        blockers.append("cleaned eval dataset hash is required")
    if decisions.get("promotion_evidence") is not False:
        blockers.append("review decisions must remain promotion_evidence=false")
    if consistency.get("status") != "PASS":
        blockers.append("xlsx candidate consistency must PASS")
    if int(consistency_summary.get("hidden_leakage_count") or 0) != 0:
        blockers.append("hidden_leakage_count must be 0")
    if scope.get("status") != "PASS":
        blockers.append("xlsx candidate scope must PASS")
    if diagnostic.get("promotion_evidence") is not False:
        blockers.append("current diagnostic report must not be promotion evidence")
    if diagnostic.get("evidence_role") != "diagnostic":
        blockers.append("current diagnostic report must have evidence_role=diagnostic")
    if diagnostic_identity.get("index_namespace_filter") != args.candidate_index_version:
        blockers.append("diagnostic namespace must match XLSX candidate index version")
    if (diagnostic.get("metrics") or {}).get("required_index_version") != args.candidate_index_version:
        blockers.append("diagnostic required_index_version must match XLSX candidate index version")
    if baseline.get("baseline_index_version") != args.baseline_index_version:
        blockers.append("baseline descriptor index version mismatch")
    if baseline.get("promotion_evidence") is not False:
        blockers.append("baseline descriptor must remain promotion_evidence=false")
    if lineage_baseline.get("descriptor_hash_check", {}).get("status") == "MISMATCH":
        blockers.append("lineage report detected baseline descriptor hash mismatch")
    if any(check.get("status") == "MISMATCH" for check in lineage_baseline.get("artifact_hash_checks") or []):
        blockers.append("lineage report detected baseline artifact hash mismatch")
    if lineage_candidate.get("index_version") != args.candidate_index_version:
        blockers.append("lineage candidate index version mismatch")
    if lineage_candidate.get("diagnostic_promotion_evidence") is not False:
        blockers.append("lineage candidate diagnostic must remain promotion_evidence=false")
    if lineage_interpretation.get("xlsx_candidate_is_immutable_baseline") is not False:
        blockers.append("xlsx candidate artifact must not be treated as immutable baseline")
    baseline_dataset_blockers = dataset_compatibility_blockers(
        baseline=baseline,
        candidate_dataset_id=cleaned_dataset_id,
        candidate_dataset_version=cleaned_dataset_version,
        candidate_dataset_sha256=cleaned_hash,
        candidate_row_count=cleaned_rows,
    )
    blockers.extend(baseline_dataset_blockers)

    range_policy_missing = rows_missing_range_policy(decisions.get("decisions") or [])
    if range_policy_missing:
        blockers.append(f"range matching policy missing for reviewed positive rows: {range_policy_missing}")

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "READY" if not blockers else "BLOCKED",
        "report_role": "xlsx_promotion_grade_eval_readiness_preflight",
        "promotion_evidence": False,
        "candidate_index_version": args.candidate_index_version,
        "candidate_namespace": args.candidate_index_version,
        "baseline_index_version": args.baseline_index_version,
        "lineage_report": str(Path(args.lineage_report)),
        "review_decisions": str(Path(args.review_decisions)),
        "cleaned_eval_dataset": {
            "path": str(cleaned_path),
            "exists": cleaned_path.exists(),
            "eval_dataset_id": cleaned_dataset_id,
            "eval_dataset_version": cleaned_dataset_version,
            "sha256": cleaned_hash,
            "row_count": cleaned_rows,
        },
        "readiness_summary": {
            "source_unresolved_query_count": source_unresolved,
            "review_unresolved_query_count": review_unresolved,
            "promotion_eval_eligible_count": decisions.get("promotion_eval_eligible_count"),
            "xlsx_candidate_consistency_status": consistency.get("status"),
            "hidden_leakage_count": consistency_summary.get("hidden_leakage_count"),
            "candidate_namespace_present": bool(diagnostic_identity.get("index_namespace_filter")),
            "candidate_namespace": diagnostic_identity.get("index_namespace_filter"),
            "baseline_descriptor_hash_check": lineage_baseline.get("descriptor_hash_check") or {},
            "baseline_artifact_hash_checks": lineage_baseline.get("artifact_hash_checks") or [],
            "diagnostic_report_promotion_evidence": diagnostic.get("promotion_evidence"),
            "diagnostic_report_evidence_role": diagnostic.get("evidence_role"),
            "diagnostic_not_promotion_evidence": diagnostic.get("promotion_evidence") is False,
            "range_policy_missing_query_ids": range_policy_missing,
            "mixed_full72_reports_are_historical": lineage_interpretation.get(
                "mixed_full72_db_level_reports_are_historical"
            ),
            "baseline_eval_dataset_id": baseline.get("eval_dataset_id"),
            "baseline_dataset_version": baseline.get("baseline_dataset_version"),
            "baseline_eval_dataset_sha256": baseline.get("eval_dataset_sha256"),
            "baseline_gold_query_row_count": baseline.get("gold_query_row_count"),
            "baseline_dataset_compatible_with_cleaned_xlsx_v1": not baseline_dataset_blockers,
        },
        "next_diagnostic_rerun": (decisions.get("rerun_preparation") or {}).get("diagnostic_only_command") or [],
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "notes": [
            "READY means ready for a future XLSX-only rerun from the cleaned eval set, not that promotion was executed.",
            "Promotion-grade readiness remains blocked when the immutable baseline dataset differs from the cleaned XLSX dataset.",
            "This report does not set promotion_evidence=true.",
            "Thresholds, hybrid search, reranking, parser behavior, baseline descriptor, and baseline artifacts are unchanged.",
        ],
    }


def rows_missing_range_policy(decision_rows: list[Mapping[str, Any]]) -> list[str]:
    missing = []
    for row in decision_rows:
        if row.get("decision") != "KEEP_AS_POSITIVE":
            continue
        gold = row.get("gold_fields") or {}
        if not gold.get("range_match_policy"):
            missing.append(str(row.get("query_id") or ""))
    return missing


def dataset_compatibility_blockers(
    *,
    baseline: Mapping[str, Any],
    candidate_dataset_id: Any,
    candidate_dataset_version: Any,
    candidate_dataset_sha256: Any,
    candidate_row_count: int,
) -> list[str]:
    blockers: list[str] = []
    comparisons = (
        ("eval_dataset_id", candidate_dataset_id, "cleaned eval dataset id"),
        ("baseline_dataset_version", candidate_dataset_version, "cleaned eval dataset version"),
        ("eval_dataset_sha256", candidate_dataset_sha256, "cleaned eval dataset sha256"),
        ("gold_query_row_count", candidate_row_count, "cleaned eval row count"),
    )
    for baseline_key, candidate_value, label in comparisons:
        baseline_value = baseline.get(baseline_key)
        if baseline_value in (None, ""):
            blockers.append(f"baseline {baseline_key} is required for dataset compatibility")
        elif candidate_value in (None, ""):
            blockers.append(f"{label} is required for dataset compatibility")
        elif str(baseline_value) != str(candidate_value):
            blockers.append(f"{label} must match baseline {baseline_key}")
    return blockers


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
    result: list[str] = []
    seen: set[str] = set()
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


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--lineage-report", default=str(DEFAULT_LINEAGE_REPORT))
    parser.add_argument("--review-decisions", default=str(DEFAULT_REVIEW_DECISIONS))
    parser.add_argument("--consistency-report", default=str(DEFAULT_CONSISTENCY_REPORT))
    parser.add_argument("--scope-report", default=str(DEFAULT_SCOPE_REPORT))
    parser.add_argument("--diagnostic-report", default=str(DEFAULT_DIAGNOSTIC_REPORT))
    parser.add_argument("--baseline-descriptor", default=str(DEFAULT_BASELINE_DESCRIPTOR))
    parser.add_argument("--cleaned-gold", default=str(DEFAULT_CLEANED_GOLD))
    parser.add_argument("--candidate-index-version", default=DEFAULT_CANDIDATE_INDEX_VERSION)
    parser.add_argument("--baseline-index-version", default=DEFAULT_BASELINE_INDEX_VERSION)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
