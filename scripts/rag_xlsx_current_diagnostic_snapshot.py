"""Freeze current XLSX v3 diagnostic evidence for Track A."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_POSITIVE_GOLD = Path("eval/gold_queries_xlsx_v3_positive.csv")
DEFAULT_DIAGNOSTIC_REPORT = Path("reports/rag_retrieval_eval_xlsx_v3_positive_vector_diagnostic_report.json")
DEFAULT_PERFORMANCE_SUMMARY = Path("reports/rag_xlsx_v3_retrieval_performance_summary.json")
DEFAULT_FAILURE_BREAKDOWN = Path("reports/rag_xlsx_v3_failure_breakdown.json")
DEFAULT_HIDDEN_LEAKAGE_REPORT = Path("reports/rag_xlsx_hidden_negative_leakage_diagnostic.json")
DEFAULT_ARTIFACT_DIR = Path("rag-data-xlsx-candidate-v1")
DEFAULT_BASELINE_DESCRIPTOR = Path("reports/initial_immutable_vector_baseline_descriptor.json")
DEFAULT_RAG_DATA_CANARY = Path("rag-data-canary")
DEFAULT_LINEAGE_OUTPUT = Path("reports/rag_xlsx_candidate_lineage_before_tuning.json")
DEFAULT_SNAPSHOT_OUTPUT = Path("reports/rag_xlsx_v3_current_diagnostic_snapshot.json")

XLSX_CANDIDATE_INDEX_VERSION = "rag-ingestion-v2-xlsx-candidate-v1"
METRIC_KEYS = [
    "Hit@1",
    "Hit@3",
    "Hit@5",
    "Hit@10",
    "MRR@10",
    "xlsx_file_hit@10",
    "xlsx_sheet_hit@10",
    "xlsx_range_overlap@10",
    "xlsx_range_contains@10",
    "xlsx_exact_range@10",
    "xlsx_citation_location_accuracy",
    "result_empty_count",
    "hidden_content_leakage_count",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    positive_rows = read_csv_rows(Path(args.positive_gold))
    diagnostic_report = read_json(Path(args.diagnostic_report))
    performance_summary = read_json(Path(args.performance_summary))
    failure_breakdown = read_json(Path(args.failure_breakdown))
    hidden_report = read_json(Path(args.hidden_leakage_report))

    lineage = build_lineage_report(
        args=args,
        positive_rows=positive_rows,
        diagnostic_report=diagnostic_report,
        performance_summary=performance_summary,
        failure_breakdown=failure_breakdown,
        hidden_report=hidden_report,
    )
    snapshot = build_snapshot_report(
        args=args,
        positive_rows=positive_rows,
        diagnostic_report=diagnostic_report,
        performance_summary=performance_summary,
        failure_breakdown=failure_breakdown,
        hidden_report=hidden_report,
    )

    write_json(Path(args.lineage_output), lineage)
    write_json(Path(args.snapshot_output), snapshot)
    print_json(
        {
            "status": snapshot["status"],
            "lineage_status": lineage["status"],
            "lineage_output": args.lineage_output,
            "snapshot_output": args.snapshot_output,
            "positive_row_count": len(positive_rows),
            "degraded_query_count": snapshot["degraded_query_count"],
            "blocker_count": len(snapshot["blockers"]),
        }
    )
    return 0 if snapshot["status"] == "COMPLETED" and lineage["status"] == "COMPLETED" else 1


def build_lineage_report(
    *,
    args: argparse.Namespace,
    positive_rows: list[dict[str, str]],
    diagnostic_report: Mapping[str, Any],
    performance_summary: Mapping[str, Any],
    failure_breakdown: Mapping[str, Any],
    hidden_report: Mapping[str, Any],
) -> dict[str, Any]:
    artifact_dir = Path(args.artifact_dir)
    baseline_descriptor = Path(args.baseline_descriptor)
    rag_data_canary = Path(args.rag_data_canary)
    required_index_version = args.required_index_version or args.candidate_index_version
    hidden_metrics = hidden_report.get("metrics") or {}
    artifact_checks = build_artifact_checks(args=args)
    completion_criteria = completion_criteria_payload(
        args=args,
        positive_rows=positive_rows,
        diagnostic_report=diagnostic_report,
        performance_summary=performance_summary,
        failure_breakdown=failure_breakdown,
        hidden_report=hidden_report,
        artifact_checks=artifact_checks,
    )
    blockers = blockers_for_completion(completion_criteria)
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED" if not blockers else "BLOCKED",
        "report_role": "xlsx_candidate_lineage_before_tuning",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_backend": "vector",
        "candidate_index_version": args.candidate_index_version,
        "namespace": required_index_version,
        "artifact_dir": str(artifact_dir),
        "inputs": {
            "positive_gold": file_record(Path(args.positive_gold), row_count=len(positive_rows)),
            "diagnostic_report": file_record(Path(args.diagnostic_report), report_status=diagnostic_report.get("status")),
            "performance_summary": file_record(
                Path(args.performance_summary),
                report_status=performance_summary.get("status"),
            ),
            "failure_breakdown": file_record(
                Path(args.failure_breakdown),
                report_status=failure_breakdown.get("status"),
                failed_or_degraded_count=failure_breakdown.get("failed_or_degraded_count"),
            ),
            "hidden_negative_leakage_report": file_record(
                Path(args.hidden_leakage_report),
                report_status=hidden_report.get("status"),
                hidden_content_leakage_count=hidden_metrics.get("hidden_content_leakage_count"),
            ),
        },
        "candidate_artifact": artifact_checks["candidate_artifact"],
        "immutable_baseline": {
            "descriptor": file_record(baseline_descriptor),
            "baseline_hash_unchanged": artifact_checks["baseline_hash_unchanged"],
            "mutation_performed_by_this_phase": False,
            "hash_mismatches": artifact_checks["baseline_hash_mismatches"],
        },
        "rag_data_canary": {
            "artifact": artifact_checks["rag_data_canary_artifact"],
            "rag_data_canary_hash_unchanged": artifact_checks["rag_data_canary_hash_unchanged"],
            "mutation_performed_by_this_phase": False,
            "hash_mismatches": artifact_checks["rag_data_canary_hash_mismatches"],
        },
        "guardrails": guardrails_payload(),
        "completion_criteria": completion_criteria,
        "blockers": blockers,
        "notes": [
            "This report freezes existing diagnostic evidence only.",
            "No gold, baseline, canary, candidate namespace, or vector artifact is modified by this script.",
        ],
    }


def build_snapshot_report(
    *,
    args: argparse.Namespace,
    positive_rows: list[dict[str, str]],
    diagnostic_report: Mapping[str, Any],
    performance_summary: Mapping[str, Any],
    failure_breakdown: Mapping[str, Any],
    hidden_report: Mapping[str, Any],
) -> dict[str, Any]:
    metrics = performance_summary.get("metrics") or diagnostic_report.get("metrics") or {}
    hidden_metrics = hidden_report.get("metrics") or {}
    degraded_rows = list(failure_breakdown.get("failed_or_degraded_rows") or [])
    artifact_checks = build_artifact_checks(args=args)
    completion_criteria = completion_criteria_payload(
        args=args,
        positive_rows=positive_rows,
        diagnostic_report=diagnostic_report,
        performance_summary=performance_summary,
        failure_breakdown=failure_breakdown,
        hidden_report=hidden_report,
        artifact_checks=artifact_checks,
    )
    blockers = blockers_for_completion(completion_criteria)
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED" if not blockers else "BLOCKED",
        "report_role": "xlsx_v3_current_diagnostic_snapshot",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_backend": "vector",
        "candidate_index_version": args.candidate_index_version,
        "namespace": args.required_index_version or args.candidate_index_version,
        "artifact_dir": args.artifact_dir,
        "positive_gold": str(Path(args.positive_gold)),
        "positive_gold_sha256": sha256_file(Path(args.positive_gold)),
        "positive_row_count": len(positive_rows),
        "diagnostic_report": file_record(Path(args.diagnostic_report), report_status=diagnostic_report.get("status")),
        "performance_summary": file_record(
            Path(args.performance_summary),
            report_status=performance_summary.get("status"),
        ),
        "failure_breakdown": file_record(
            Path(args.failure_breakdown),
            report_status=failure_breakdown.get("status"),
            failed_or_degraded_count=failure_breakdown.get("failed_or_degraded_count"),
        ),
        "hidden_negative_leakage_report": file_record(
            Path(args.hidden_leakage_report),
            report_status=hidden_report.get("status"),
            hidden_content_leakage_count=hidden_metrics.get("hidden_content_leakage_count"),
        ),
        "metrics": {key: metrics.get(key) for key in METRIC_KEYS},
        "hidden_negative_metrics": {
            "hidden_content_leakage_count": hidden_metrics.get("hidden_content_leakage_count"),
            "hidden_negative_pass_count": hidden_metrics.get("hidden_negative_pass_count"),
            "positive_metric_mix_allowed": False,
        },
        "category_counts": failure_breakdown.get("category_counts") or {},
        "degradation_axis_counts": failure_breakdown.get("degradation_axis_counts") or {},
        "degraded_query_count": len(degraded_rows),
        "degraded_query_ids": [str(row.get("query_id") or "") for row in degraded_rows],
        "degraded_queries": [snapshot_degraded_row(row) for row in degraded_rows],
        "guardrails": guardrails_payload(),
        "completion_criteria": completion_criteria,
        "blockers": blockers,
        "notes": [
            "Snapshot is sourced from existing XLSX v3 positive diagnostic reports.",
            "Hidden-negative leakage remains separate from positive retrieval metrics.",
        ],
    }


def snapshot_degraded_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "query_id": row.get("query_id"),
        "category": row.get("category"),
        "bucket": row.get("bucket"),
        "query": row.get("v3_query"),
        "original_query": row.get("v2_query"),
        "expected_file_name": row.get("expected_file_name"),
        "expected_sheet_name": row.get("expected_sheet_name"),
        "expected_cell_range": row.get("expected_cell_range"),
        "range_match_policy": row.get("range_match_policy"),
        "failure_reason": row.get("v3_failure_reason"),
        "v3_hit_rank": row.get("v3_hit_rank"),
        "v3_location_match": row.get("v3_location_match"),
        "recommended_target_phase": target_phase_for_category(str(row.get("category") or "")),
        "rationale": row.get("rationale"),
    }


def target_phase_for_category(category: str) -> str:
    return {
        "QUERY_NATURALIZATION_DRIFT": "A2",
        "RANGE_POLICY_MISMATCH": "A3",
        "FORMULA_DATE_CONTRACT_MISMATCH": "A4",
    }.get(category, "A1_REVIEW_REQUIRED")


def guardrails_payload() -> dict[str, Any]:
    return {
        "promotion_evidence_true_set": False,
        "candidate_v1_mutated": False,
        "immutable_baseline_changed": False,
        "rag_data_canary_changed": False,
        "broad_reindex_executed": False,
        "hidden_negative_in_positive_metrics": False,
        "hybrid_search_introduced": False,
        "reranking_introduced": False,
        "parser_expansion_introduced": False,
        "answer_generation_changed": False,
    }


def build_artifact_checks(*, args: argparse.Namespace) -> dict[str, Any]:
    artifact_dir = Path(args.artifact_dir)
    baseline_descriptor_path = Path(args.baseline_descriptor)
    rag_data_canary = Path(args.rag_data_canary)
    baseline_descriptor = read_json(baseline_descriptor_path) if baseline_descriptor_path.exists() else {}
    expected_canary_hashes = baseline_descriptor.get("faiss_artifact_hashes") or {}
    candidate_artifact = directory_record(artifact_dir)
    rag_data_canary_artifact = directory_record(rag_data_canary)
    canary_mismatches = artifact_hash_mismatches(rag_data_canary_artifact, expected_canary_hashes)
    candidate_build = read_json(artifact_dir / "build.json") if (artifact_dir / "build.json").exists() else {}
    candidate_manifest = read_json(artifact_dir / "ingest_manifest.json") if (artifact_dir / "ingest_manifest.json").exists() else {}
    candidate_index_version = candidate_build.get("index_version") or candidate_manifest.get("index_version")
    return {
        "candidate_artifact": candidate_artifact,
        "rag_data_canary_artifact": rag_data_canary_artifact,
        "baseline_descriptor_exists": baseline_descriptor_path.exists(),
        "baseline_expected_hashes_present": bool(expected_canary_hashes),
        "baseline_hash_unchanged": bool(expected_canary_hashes) and not canary_mismatches,
        "baseline_hash_mismatches": canary_mismatches,
        "rag_data_canary_hash_unchanged": bool(expected_canary_hashes) and not canary_mismatches,
        "rag_data_canary_hash_mismatches": canary_mismatches,
        "candidate_artifact_exists": candidate_artifact["exists"],
        "candidate_index_version": candidate_index_version,
        "candidate_index_version_matches_build": candidate_index_version == args.candidate_index_version,
    }


def artifact_hash_mismatches(artifact_record: Mapping[str, Any], expected_hashes: Mapping[str, Any]) -> list[dict[str, Any]]:
    actual_by_path = {
        str(entry.get("relative_path")): entry.get("sha256")
        for entry in artifact_record.get("files") or []
        if isinstance(entry, Mapping)
    }
    mismatches = []
    for relative_path, expected_hash in sorted(expected_hashes.items()):
        actual_hash = actual_by_path.get(str(relative_path))
        if actual_hash != expected_hash:
            mismatches.append(
                {
                    "relative_path": str(relative_path),
                    "expected_sha256": expected_hash,
                    "actual_sha256": actual_hash,
                }
            )
    return mismatches


def completion_criteria_payload(
    *,
    args: argparse.Namespace,
    positive_rows: list[dict[str, str]],
    diagnostic_report: Mapping[str, Any],
    performance_summary: Mapping[str, Any],
    failure_breakdown: Mapping[str, Any],
    hidden_report: Mapping[str, Any],
    artifact_checks: Mapping[str, Any],
) -> dict[str, Any]:
    hidden_metrics = hidden_report.get("metrics") or {}
    return {
        "diagnostic_report_completed": diagnostic_report.get("status") == "COMPLETED",
        "performance_summary_completed": performance_summary.get("status") == "COMPLETED",
        "failure_breakdown_completed": failure_breakdown.get("status") == "COMPLETED",
        "hidden_negative_report_completed": hidden_report.get("status") == "COMPLETED",
        "promotion_evidence_is_false": diagnostic_report.get("promotion_evidence") is False
        and hidden_report.get("promotion_evidence") is False,
        "evidence_role_is_diagnostic": diagnostic_report.get("evidence_role") == "diagnostic"
        and hidden_report.get("evidence_role") == "diagnostic",
        "candidate_index_version_matches": args.candidate_index_version == XLSX_CANDIDATE_INDEX_VERSION,
        "candidate_artifact_exists": bool(artifact_checks.get("candidate_artifact_exists")),
        "candidate_index_version_matches_build": bool(artifact_checks.get("candidate_index_version_matches_build")),
        "retrieval_backend_is_vector": diagnostic_report.get("retrieval_backend") == "vector",
        "positive_row_count": len(positive_rows),
        "positive_row_count_is_35": len(positive_rows) == 35,
        "hidden_content_leakage_count": hidden_metrics.get("hidden_content_leakage_count"),
        "hidden_content_leakage_count_is_0": hidden_metrics.get("hidden_content_leakage_count") == 0,
        "baseline_descriptor_exists": bool(artifact_checks.get("baseline_descriptor_exists")),
        "baseline_expected_hashes_present": bool(artifact_checks.get("baseline_expected_hashes_present")),
        "baseline_hash_unchanged": bool(artifact_checks.get("baseline_hash_unchanged")),
        "rag_data_canary_hash_unchanged": bool(artifact_checks.get("rag_data_canary_hash_unchanged")),
    }


def blockers_for_completion(criteria: Mapping[str, Any]) -> list[str]:
    blockers = []
    for key, value in criteria.items():
        if key.endswith("_count") or key == "positive_row_count":
            continue
        if value is not True:
            blockers.append(key)
    return blockers


def file_record(path: Path, **extra: Any) -> dict[str, Any]:
    record = {
        "path": str(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
        "bytes": path.stat().st_size if path.exists() and path.is_file() else None,
    }
    record.update(extra)
    return record


def directory_record(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "sha256": None,
            "file_count": 0,
            "total_bytes": 0,
            "files": [],
        }
    files = []
    total_bytes = 0
    for file_path in sorted(path.rglob("*")):
        if not file_path.is_file():
            continue
        stat = file_path.stat()
        total_bytes += stat.st_size
        files.append(
            {
                "relative_path": file_path.relative_to(path).as_posix(),
                "bytes": stat.st_size,
                "sha256": sha256_file(file_path),
            }
        )
    digest = hashlib.sha256()
    for entry in files:
        digest.update(entry["relative_path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(entry["bytes"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(entry["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return {
        "path": str(path),
        "exists": True,
        "sha256": digest.hexdigest(),
        "file_count": len(files),
        "total_bytes": total_bytes,
        "files": files,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON report must be an object: {path}")
    return payload


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
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
    parser.add_argument("--positive-gold", default=str(DEFAULT_POSITIVE_GOLD))
    parser.add_argument("--diagnostic-report", default=str(DEFAULT_DIAGNOSTIC_REPORT))
    parser.add_argument("--performance-summary", default=str(DEFAULT_PERFORMANCE_SUMMARY))
    parser.add_argument("--failure-breakdown", default=str(DEFAULT_FAILURE_BREAKDOWN))
    parser.add_argument("--hidden-leakage-report", default=str(DEFAULT_HIDDEN_LEAKAGE_REPORT))
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--baseline-descriptor", default=str(DEFAULT_BASELINE_DESCRIPTOR))
    parser.add_argument("--rag-data-canary", default=str(DEFAULT_RAG_DATA_CANARY))
    parser.add_argument("--lineage-output", default=str(DEFAULT_LINEAGE_OUTPUT))
    parser.add_argument("--snapshot-output", default=str(DEFAULT_SNAPSHOT_OUTPUT))
    parser.add_argument("--candidate-index-version", default=XLSX_CANDIDATE_INDEX_VERSION)
    parser.add_argument("--required-index-version", default=XLSX_CANDIDATE_INDEX_VERSION)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
