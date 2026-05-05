"""Run Track C C5 PDF-only vector diagnostics.

This script is diagnostic-only. It filters the v0 gold set to bound positive
PDF rows, searches the PDF candidate FAISS/ragmeta artifact, and records
query-level details for C6. It does not run promotion, baseline comparison, or
hybrid/rerank tuning.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[1]
AI_WORKER = ROOT / "ai-worker"
if str(AI_WORKER) not in sys.path:
    sys.path.insert(0, str(AI_WORKER))

from eval.harness.rag_ingestion_retrieval_eval import (  # noqa: E402
    evaluate_gold_rows,
    print_report,
    search_vector,
    validate_gold_rows,
)


DEFAULT_GOLD = Path("eval/gold_queries_v0.csv")
DEFAULT_C4_REPORT = Path("reports/pdf_candidate_embedding_consistency_report.json")
DEFAULT_REPORT = Path("reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json")
DEFAULT_INDEX_VERSION = "rag-ingestion-v2-pdf-candidate-v1"
DEFAULT_ARTIFACT_DIR = Path("rag-data-pdf-candidate-v1")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"

METADATA_FAILURE_REASONS = {
    "candidate_index_mismatch",
    "embedding_status_mismatch",
    "required_index_version_mismatch",
}
RANKING_FAILURE_REASONS = {
    "search_result_empty",
    "expected_file_not_found",
    "expected_page_not_found",
    "bbox_mismatch",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    promotion_evidence = parse_bool(args.promotion_evidence)
    evidence_role = str(args.evidence_role or "diagnostic").strip()
    all_rows = read_csv(Path(args.gold))
    rows = filter_pdf_positive_rows(
        all_rows,
        expected_location_type=args.expected_location_type,
        label_status=args.label_status,
    )
    c4_report = read_json(Path(args.c4_consistency_report))
    blockers = validate_prerequisites(
        c4_report=c4_report,
        c4_report_path=Path(args.c4_consistency_report),
        index_version=args.index_version,
        artifact_dir=Path(args.artifact_dir),
        promotion_evidence=promotion_evidence,
        evidence_role=evidence_role,
    )
    validation = validate_gold_rows(rows, require_live_bound=True)
    if not validation.ok:
        blockers.append("C5 PDF gold filter produced validation errors")

    if blockers or args.validate_only:
        payload = build_payload(
            evaluation=empty_evaluation(rows, validation),
            all_rows=all_rows,
            filtered_rows=rows,
            args=args,
            c4_report=c4_report,
            blockers=blockers,
            promotion_evidence=promotion_evidence,
            evidence_role=evidence_role,
        )
        write_json(Path(args.report), payload)
        print_report(payload)
        return 0 if not blockers else 2

    search_fn = search_vector(
        index_dir=args.artifact_dir,
        db_dsn=args.db_dsn,
        embedding_model=args.embedding_model,
        query_prefix=args.query_prefix,
        passage_prefix=args.passage_prefix,
        max_seq_length=args.max_seq_length,
        batch_size=args.batch_size,
        expected_index_version=args.index_version,
    )
    evaluation = evaluate_pdf_rows(
        rows,
        search_fn=search_fn,
        top_k=args.top_k,
        index_version=args.index_version,
    )
    payload = build_payload(
        evaluation=evaluation,
        all_rows=all_rows,
        filtered_rows=rows,
        args=args,
        c4_report=c4_report,
        blockers=[],
        promotion_evidence=promotion_evidence,
        evidence_role=evidence_role,
    )
    write_json(Path(args.report), payload)
    print_report(payload)
    return 0 if payload["status"] in {"PASS", "PASS_WITH_WARNINGS"} else 2


def evaluate_pdf_rows(
    rows: list[dict[str, str]],
    *,
    search_fn: Callable[[str, int], list[dict[str, Any]]],
    top_k: int,
    index_version: str,
) -> dict[str, Any]:
    return evaluate_gold_rows(
        rows,
        search_fn=search_fn,
        top_k=top_k,
        candidate_index_version=index_version,
        required_embedding_status="EMBEDDED",
        required_index_version=index_version,
    )


def build_payload(
    *,
    evaluation: Mapping[str, Any],
    all_rows: list[dict[str, str]],
    filtered_rows: list[dict[str, str]],
    args: argparse.Namespace,
    c4_report: Mapping[str, Any],
    blockers: list[str],
    promotion_evidence: bool,
    evidence_role: str,
) -> dict[str, Any]:
    artifact = artifact_contract(Path(args.artifact_dir), args.index_version)
    c4_candidate_rows = int(((c4_report.get("scoped_summary") or {}).get("candidate_rows") or 0))
    artifact_blockers = artifact_blockers_for(
        artifact=artifact,
        expected_index_version=args.index_version,
        expected_chunk_count=c4_candidate_rows,
    )
    blocker_list = list(blockers) + artifact_blockers
    breakdown = diagnostic_breakdown(evaluation, expected_index_version=args.index_version)
    metrics = dict(evaluation.get("metrics") or {})
    gate_counters = {
        "candidate_index_mismatch_count": int(metrics.get("candidate_index_mismatch_count") or 0),
        "required_index_version_mismatch_count": int(metrics.get("required_index_version_mismatch_count") or 0),
        "embedding_status_mismatch_count": int(metrics.get("embedding_status_mismatch_count") or 0),
        "wrong_index_version_hit_count": int(metrics.get("wrong_index_version_hit_count") or 0),
        "unembedded_hit_count": int(metrics.get("unembedded_hit_count") or 0),
        "top_k_hit_missing_location_json_count": breakdown["top_k_hit_missing_location_json_count"],
        "top_k_hit_non_pdf_location_type_count": breakdown["top_k_hit_non_pdf_location_type_count"],
    }
    for key, value in gate_counters.items():
        if value:
            blocker_list.append(f"{key} must be 0")
    query_level_results_available = bool(evaluation.get("query_results")) and (
        len(evaluation.get("query_results") or []) == len(filtered_rows)
    )
    if filtered_rows and not query_level_results_available:
        blocker_list.append("query-level results must be available for every C5 row")

    warnings: list[str] = []
    if breakdown["true_retrieval_ranking_failure_count"]:
        warnings.append(
            "true_retrieval_ranking_failure_count="
            f"{breakdown['true_retrieval_ranking_failure_count']}; classify in C6"
        )
    if breakdown["metadata_projection_failure_count"]:
        warnings.append(
            "metadata_projection_failure_count="
            f"{breakdown['metadata_projection_failure_count']}; separated for C6"
        )
    status = "PASS"
    if blocker_list:
        status = "BLOCKED" if blockers else "FAIL"
    elif warnings:
        status = "PASS_WITH_WARNINGS"

    payload = dict(evaluation)
    payload.update({
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C5",
        "report_role": "pdf_only_vector_diagnostic",
        "retrieval_backend": "vector",
        "promotion_evidence": promotion_evidence,
        "evidence_role": evidence_role,
        "index_version": args.index_version,
        "candidate_index_version": args.index_version,
        "required_index_version": args.index_version,
        "artifact_dir": str(args.artifact_dir),
        "top_k": int(args.top_k),
        "gold": str(args.gold),
        "row_filter": {
            "expected_location_type": args.expected_location_type,
            "label_status": args.label_status,
            "positive_rows_only": True,
            "excluded_hidden_policies": ["negative"],
            "original_row_count": len(all_rows),
            "filtered_row_count": len(filtered_rows),
            "bucket_counts": dict(sorted(Counter(row.get("bucket") or "" for row in filtered_rows).items())),
        },
        "backend_identity": {
            "backend": "faiss",
            "index_dir": str(args.artifact_dir),
            "index_namespace_filter": args.index_version,
            "db_dsn": redact_dsn(args.db_dsn),
            "filtering_mode": "vector_namespace_then_contract_filter",
        },
        "input_artifacts": [
            artifact_identity(Path(args.gold)),
            artifact_identity(Path(args.c4_consistency_report)),
        ],
        "c4_consistency": {
            "path": str(args.c4_consistency_report),
            "status": c4_report.get("status"),
            "sha256": file_sha256(Path(args.c4_consistency_report)) if Path(args.c4_consistency_report).exists() else None,
            "candidate_rows": c4_candidate_rows,
            "promotion_evidence": c4_report.get("promotion_evidence"),
            "evidence_role": c4_report.get("evidence_role"),
        },
        "artifact_contract": artifact,
        "gate_counters": gate_counters,
        "diagnostic_breakdown": breakdown,
        "query_level_results_available": query_level_results_available,
        "metadata_projection_failure_count": breakdown["metadata_projection_failure_count"],
        "true_retrieval_ranking_failure_count": breakdown["true_retrieval_ranking_failure_count"],
        "blockers": dedupe(blocker_list),
        "warnings": dedupe(warnings),
        "notes": [
            "This is PDF-only vector diagnostic evidence, not promotion evidence.",
            "C5 records retrieval behavior after C4 consistency; ranking and gold-policy failures belong to C6/C7.",
            "No baseline descriptor or XLSX candidate artifact is written by this script.",
        ],
    })
    return payload


def validate_prerequisites(
    *,
    c4_report: Mapping[str, Any],
    c4_report_path: Path,
    index_version: str,
    artifact_dir: Path,
    promotion_evidence: bool,
    evidence_role: str,
) -> list[str]:
    blockers: list[str] = []
    if promotion_evidence:
        blockers.append("C5 must keep promotion_evidence=false")
    if evidence_role != "diagnostic":
        blockers.append("C5 must keep evidence_role=diagnostic")
    if not c4_report_path.exists():
        blockers.append(f"C4 consistency report is missing: {c4_report_path}")
    if c4_report.get("status") != "PASS":
        blockers.append(f"C4 consistency report must be PASS; got {c4_report.get('status')}")
    if c4_report.get("promotion_evidence") is not False:
        blockers.append("C4 consistency report must keep promotion_evidence=false")
    if c4_report.get("evidence_role") != "diagnostic":
        blockers.append("C4 consistency report must keep evidence_role=diagnostic")
    if c4_report.get("index_version") != index_version:
        blockers.append("C4 consistency report index_version must match C5 index version")
    if str(c4_report.get("artifact_dir") or "") != str(artifact_dir):
        blockers.append("C4 consistency report artifact_dir must match C5 artifact dir")
    return blockers


def artifact_blockers_for(
    *,
    artifact: Mapping[str, Any],
    expected_index_version: str,
    expected_chunk_count: int,
) -> list[str]:
    blockers: list[str] = []
    if not artifact.get("exists"):
        return ["PDF candidate artifact dir must exist"]
    build = artifact.get("build_json") or {}
    manifest = artifact.get("ingest_manifest_json") or {}
    if build.get("index_version") != expected_index_version:
        blockers.append("artifact build.json index_version must match C5 index version")
    if manifest.get("index_version") != expected_index_version:
        blockers.append("artifact ingest_manifest.json index_version must match C5 index version")
    if expected_chunk_count and int(build.get("chunk_count") or 0) != expected_chunk_count:
        blockers.append("artifact build.json chunk_count must match C4 candidate_rows")
    if expected_chunk_count and int(manifest.get("chunk_count") or 0) != expected_chunk_count:
        blockers.append("artifact ingest_manifest.json chunk_count must match C4 candidate_rows")
    if not artifact.get("faiss_index_exists"):
        blockers.append("artifact faiss.index must exist")
    return blockers


def diagnostic_breakdown(evaluation: Mapping[str, Any], *, expected_index_version: str) -> dict[str, Any]:
    query_results = list(evaluation.get("query_results") or [])
    failure_counts = Counter(
        str(row.get("failure_reason"))
        for row in query_results
        if row.get("failure_reason")
    )
    metadata_query_ids: set[str] = set()
    missing_location_hits = 0
    non_pdf_location_hits = 0
    wrong_index_hits = 0
    for row in query_results:
        query_id = str(row.get("query_id") or "")
        for hit in list(row.get("top_k_results") or []):
            location = hit.get("location_json")
            if not isinstance(location, dict) or not location:
                missing_location_hits += 1
                metadata_query_ids.add(query_id)
            else:
                location_type = str(location.get("type") or "").lower()
                if location_type and location_type != "pdf":
                    non_pdf_location_hits += 1
                    metadata_query_ids.add(query_id)
            if hit.get("index_version") and hit.get("index_version") != expected_index_version:
                wrong_index_hits += 1
                metadata_query_ids.add(query_id)
        if row.get("failure_reason") in METADATA_FAILURE_REASONS:
            metadata_query_ids.add(query_id)
    ranking_query_ids = {
        str(row.get("query_id") or "")
        for row in query_results
        if row.get("failure_reason") in RANKING_FAILURE_REASONS
    }
    return {
        "failure_reason_counts": dict(sorted(failure_counts.items())),
        "metadata_projection_failure_count": len(metadata_query_ids),
        "metadata_projection_failure_query_ids": sorted(item for item in metadata_query_ids if item),
        "true_retrieval_ranking_failure_count": len(ranking_query_ids),
        "true_retrieval_ranking_failure_query_ids": sorted(item for item in ranking_query_ids if item),
        "top_k_hit_missing_location_json_count": missing_location_hits,
        "top_k_hit_non_pdf_location_type_count": non_pdf_location_hits,
        "top_k_hit_wrong_index_version_count": wrong_index_hits,
    }


def filter_pdf_positive_rows(
    rows: list[dict[str, str]],
    *,
    expected_location_type: str,
    label_status: str,
) -> list[dict[str, str]]:
    expected = expected_location_type.strip().lower()
    label = label_status.strip().lower()
    return [
        row
        for row in rows
        if str(row.get("expected_location_type") or "").strip().lower() == expected
        and str(row.get("label_status") or "").strip().lower() == label
        and str(row.get("hidden_policy") or "").strip().lower() != "negative"
        and bool(str(row.get("expected_file_name") or "").strip())
    ]


def empty_evaluation(rows: list[dict[str, str]], validation: Any) -> dict[str, Any]:
    return {
        "validation": {
            "ok": validation.ok,
            "errors": validation.errors,
            "row_errors": validation.row_errors,
            "row_count": validation.row_count,
            "bucket_counts": validation.bucket_counts,
        },
        "metrics": {},
        "bucket_metrics": {},
        "per_query": [],
        "query_results": [],
    }


def artifact_contract(path: Path, expected_index_version: str) -> dict[str, Any]:
    build_path = path / "build.json"
    manifest_path = path / "ingest_manifest.json"
    faiss_path = path / "faiss.index"
    return {
        "path": str(path),
        "exists": path.exists() and path.is_dir(),
        "expected_index_version": expected_index_version,
        "build_json": read_json(build_path),
        "build_json_sha256": file_sha256(build_path) if build_path.exists() else None,
        "ingest_manifest_json": read_json(manifest_path),
        "ingest_manifest_json_sha256": file_sha256(manifest_path) if manifest_path.exists() else None,
        "faiss_index_exists": faiss_path.exists(),
        "faiss_index_sha256": file_sha256(faiss_path) if faiss_path.exists() else None,
    }


def artifact_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() and path.is_file() else None,
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n", ""}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def redact_dsn(dsn: str) -> str:
    parts = []
    for part in str(dsn or "").split():
        if part.lower().startswith("password="):
            parts.append("password=<redacted>")
        else:
            parts.append(part)
    return " ".join(parts)


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--expected-location-type", default="pdf")
    parser.add_argument("--label-status", default="bound")
    parser.add_argument("--index-version", default=DEFAULT_INDEX_VERSION)
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--c4-consistency-report", default=str(DEFAULT_C4_REPORT))
    parser.add_argument("--db-dsn", default=DEFAULT_DB_DSN)
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--query-prefix", default="")
    parser.add_argument("--passage-prefix", default="")
    parser.add_argument("--max-seq-length", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--promotion-evidence", default="false")
    parser.add_argument("--evidence-role", default="diagnostic")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
