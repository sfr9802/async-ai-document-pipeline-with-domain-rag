"""Freeze the current PDF diagnostic state for Track C C0.

This script is intentionally file-based. It reads the existing full72 vector
diagnostic report, gold CSV, immutable baseline descriptor, and lineage report,
then writes a diagnostic-only PDF snapshot. It does not query the database,
build vectors, run retrieval, index SearchUnits, or mutate any baseline.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_RETRIEVAL_REPORT = Path("reports/rag_eval/rag-ingestion/rag_retrieval_eval_full72_vector_diagnostic_report.json")
DEFAULT_QUALITY_BREAKDOWN = Path("reports/rag_eval/rag-ingestion/rag_retrieval_full72_vector_quality_breakdown.json")
DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_pdf_v0.csv")
DEFAULT_BASELINE_DESCRIPTOR = Path("reports/rag_eval/rag-ingestion/initial_immutable_vector_baseline_descriptor.json")
DEFAULT_BASELINE_ARTIFACT_DIR = Path("eval/indexes/rag-data-canary")
DEFAULT_LINEAGE_REPORT = Path("reports/rag_eval/rag-ingestion/rag_candidate_index_lineage_report.json")
DEFAULT_XLSX_CANDIDATE_ARTIFACT_DIR = Path("eval/indexes/rag-data-xlsx-candidate-v1")
DEFAULT_OUTPUT = Path("reports/rag_eval/rag-ingestion/rag_pdf_current_diagnostic_snapshot.json")

PDF_INDEX_VERSION = "rag-ingestion-v2-pdf-candidate-v1"
PDF_ARTIFACT_DIR = "eval/indexes/rag-data-pdf-candidate-v1"
PDF_PARSER_VERSIONS = ["pdf-extract-v1", "pdf-extract-v2"]
ARTIFACT_FILES = ("faiss.index", "build.json", "ingest_manifest.json")
SAFE_BACKEND_IDENTITY_KEYS = {
    "backend",
    "chunk_count",
    "dimension",
    "embedding_model",
    "filtering_mode",
    "index_dir",
    "index_namespace_filter",
}
SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "connection",
    "credential",
    "dsn",
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "uri",
    "url",
)
URI_USERINFO_RE = re.compile(r"://[^/@\s]+:[^/@\s]+@")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_snapshot(args)
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0 if payload.get("status") == "PASS" else 2


def build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []

    retrieval_path = Path(args.retrieval_report)
    quality_path = Path(args.quality_breakdown)
    gold_path = Path(args.gold)
    baseline_path = Path(args.baseline_descriptor)
    lineage_path = Path(args.lineage_report)
    baseline_artifact_dir = Path(args.baseline_artifact_dir)
    xlsx_artifact_dir = Path(args.xlsx_candidate_artifact_dir)

    retrieval = read_json(retrieval_path, blockers, "retrieval_report")
    quality = read_optional_json(quality_path, warnings, "quality_breakdown_report")
    gold_rows = read_gold_rows(gold_path, blockers)
    baseline = read_json(baseline_path, blockers, "baseline_descriptor")
    lineage = read_optional_json(lineage_path, warnings, "lineage_report")

    pdf_gold_rows = filter_pdf_rows(gold_rows)
    query_results, query_coverage = select_pdf_query_results(
        pdf_gold_rows,
        list(retrieval.get("query_results") or []),
    )
    pdf_counters = build_pdf_counters(pdf_gold_rows, query_results)
    pdf_metrics = pick_pdf_metrics(dict(retrieval.get("metrics") or {}))
    baseline_checks = build_baseline_checks(
        baseline=baseline,
        retrieval_path=retrieval_path,
        baseline_path=baseline_path,
        baseline_artifact_dir=baseline_artifact_dir,
        blockers=blockers,
    )
    xlsx_checks = build_xlsx_candidate_checks(
        lineage=lineage,
        lineage_path=lineage_path,
        xlsx_artifact_dir=xlsx_artifact_dir,
        warnings=warnings,
    )
    pdf_artifact = build_pdf_candidate_artifact_check(
        pdf_artifact_dir=Path(args.pdf_artifact_dir),
        blockers=blockers,
    )

    if retrieval and retrieval.get("promotion_evidence") is not False:
        blockers.append("retrieval_report must keep promotion_evidence=false")
    if retrieval and retrieval.get("evidence_role") != "diagnostic":
        blockers.append("retrieval_report must keep evidence_role=diagnostic")
    if retrieval and retrieval.get("retrieval_backend") != "vector":
        blockers.append("retrieval_report must be vector-backed")
    if not pdf_gold_rows:
        blockers.append("PDF gold subset must not be empty")
    if query_coverage.get("duplicate_gold_query_ids"):
        blockers.append(f"duplicate PDF gold query_ids: {query_coverage['duplicate_gold_query_ids']}")
    if query_coverage.get("duplicate_result_query_ids"):
        blockers.append(f"duplicate PDF result query_ids: {query_coverage['duplicate_result_query_ids']}")
    if query_coverage.get("missing_result_query_ids"):
        blockers.append(f"PDF query results missing ids: {query_coverage['missing_result_query_ids']}")
    if query_coverage.get("extra_result_query_ids"):
        blockers.append(f"PDF query results contain ids outside gold subset: {query_coverage['extra_result_query_ids']}")
    if query_coverage.get("malformed_result_rows"):
        blockers.append(f"PDF query results contain malformed rows: {query_coverage['malformed_result_rows']}")
    if baseline_checks.get("baseline_changed") is True:
        blockers.append("immutable baseline descriptor/artifacts changed relative to recorded hashes")
    if xlsx_checks.get("xlsx_candidate_artifact_changed") is True:
        blockers.append("XLSX candidate artifact changed relative to lineage report")

    quality_pdf_breakdown = {}
    if quality:
        value = quality.get("pdf_page_bbox_failure_breakdown")
        quality_pdf_breakdown = value if isinstance(value, dict) else {}

    payload = {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "PASS" if not blockers else "FAIL",
        "track": "C",
        "phase": "C0",
        "report_role": "pdf_current_diagnostic_snapshot",
        "source_file_type": "PDF",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "index_version": args.pdf_index_version,
        "artifact_dir": args.pdf_artifact_dir,
        "retrieval_execution": "not_run_by_this_script",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "input_artifacts": [
            artifact_identity(retrieval_path),
            artifact_identity(gold_path),
            artifact_identity(baseline_path),
            artifact_identity(quality_path),
            artifact_identity(lineage_path),
        ],
        "scope": {
            "source_file_type": "PDF",
            "document_version_ids": sorted({
                row.get("expected_document_version_id", "").strip()
                for row in pdf_gold_rows
                if row.get("expected_document_version_id", "").strip()
            }),
            "parser_versions": list(PDF_PARSER_VERSIONS),
            "expected_location_type": "pdf",
        },
        "pdf_query_subset": build_pdf_query_subset(gold_path, gold_rows, pdf_gold_rows),
        "pdf_query_coverage": query_coverage,
        "current_full72_report": {
            "path": str(retrieval_path),
            "sha256": file_sha256(retrieval_path) if retrieval_path.exists() else None,
            "status": retrieval.get("status"),
            "retrieval_backend": retrieval.get("retrieval_backend"),
            "backend_identity": sanitize_backend_identity(retrieval.get("backend_identity") or {}),
            "candidate_index_version": retrieval.get("candidate_index_version"),
            "required_index_version": retrieval.get("required_index_version"),
            "required_embedding_status": retrieval.get("required_embedding_status"),
            "top_k": retrieval.get("top_k"),
            "promotion_evidence": retrieval.get("promotion_evidence"),
            "evidence_role": retrieval.get("evidence_role"),
            "validation": retrieval.get("validation") or {},
        },
        "current_pdf_metrics": pdf_metrics,
        "current_pdf_failure_counters": pdf_counters,
        "current_quality_breakdown": {
            "path": str(quality_path),
            "sha256": file_sha256(quality_path) if quality_path.exists() else None,
            "status": quality.get("status"),
            "promotion_evidence": quality.get("promotion_evidence"),
            "evidence_role": quality.get("evidence_role"),
            "pdf_page_bbox_failure_breakdown": quality_pdf_breakdown,
        },
        "immutable_baseline": baseline_checks,
        "xlsx_candidate_artifact": xlsx_checks,
        "pdf_candidate_artifact": pdf_artifact,
        "side_effect_status": {
            "retrieval_run": False,
            "indexing_run": False,
            "promotion_run": False,
            "immutable_baseline_changed": bool(baseline_checks.get("baseline_changed")),
            "xlsx_candidate_artifact_changed": bool(xlsx_checks.get("xlsx_candidate_artifact_changed")),
            "pdf_candidate_artifact_exists": bool(pdf_artifact.get("exists")),
            "pdf_candidate_artifact_changed": bool(pdf_artifact.get("exists")),
        },
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "next_action": (
            "Run C1 PDF candidate scope report from this explicit PDF gold/document scope."
            if not blockers
            else "Resolve C0 blockers before starting C1."
        ),
        "notes": [
            "C0 freezes the current mixed full72 PDF diagnostic state only.",
            "This report does not prove PDF metadata projection, text contract, indexing consistency, or ranking quality.",
            "All Track C PDF reports remain diagnostic-only until a separate post-C7 decision.",
        ],
    }
    return payload


def build_pdf_query_subset(
    gold_path: Path,
    gold_rows: list[dict[str, str]],
    pdf_rows: list[dict[str, str]],
) -> dict[str, Any]:
    bucket_counts = Counter(row.get("bucket") or "unknown" for row in pdf_rows)
    positive_rows = [row for row in pdf_rows if (row.get("label_status") or "").strip().lower() == "bound"]
    return {
        "gold_path": str(gold_path),
        "gold_row_count": len(gold_rows),
        "pdf_query_count": len(pdf_rows),
        "pdf_positive_count": len(positive_rows),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "expected_file_row_count": sum(1 for row in pdf_rows if row.get("expected_file_name")),
        "expected_document_version_row_count": sum(
            1 for row in pdf_rows if row.get("expected_document_version_id")
        ),
        "expected_page_row_count": sum(1 for row in pdf_rows if row.get("expected_page_no")),
        "expected_physical_page_index_row_count": sum(
            1 for row in pdf_rows if row.get("expected_physical_page_index")
        ),
        "expected_bbox_row_count": sum(1 for row in pdf_rows if row.get("expected_bbox")),
        "expected_file_names": sorted({
            row.get("expected_file_name", "").strip()
            for row in pdf_rows
            if row.get("expected_file_name", "").strip()
        }),
        "expected_document_version_ids": sorted({
            row.get("expected_document_version_id", "").strip()
            for row in pdf_rows
            if row.get("expected_document_version_id", "").strip()
        }),
    }


def select_pdf_query_results(
    pdf_gold_rows: list[dict[str, str]],
    query_results: list[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], dict[str, Any]]:
    gold_ids = [row.get("query_id", "").strip() for row in pdf_gold_rows if row.get("query_id")]
    gold_counter = Counter(gold_ids)
    gold_id_set = set(gold_counter)
    pdf_results: list[Mapping[str, Any]] = []
    malformed_rows: list[dict[str, Any]] = []
    for index, row in enumerate(query_results):
        query_id = str(row.get("query_id") or "").strip()
        is_pdf_bucket = str(row.get("bucket") or "").startswith("pdf")
        if query_id in gold_id_set or is_pdf_bucket:
            pdf_results.append(row)
            if not query_id:
                malformed_rows.append({
                    "result_index": index,
                    "bucket": row.get("bucket"),
                    "reason": "missing query_id",
                })
    result_ids = [str(row.get("query_id") or "").strip() for row in pdf_results if row.get("query_id")]
    result_counter = Counter(result_ids)
    duplicate_gold = sorted(query_id for query_id, count in gold_counter.items() if count > 1)
    duplicate_results = sorted(query_id for query_id, count in result_counter.items() if count > 1)
    missing = sorted(query_id for query_id in gold_id_set if result_counter.get(query_id, 0) == 0)
    extra = sorted(query_id for query_id in result_counter if query_id not in gold_id_set)
    return pdf_results, {
        "gold_query_count": len(gold_ids),
        "gold_unique_query_count": len(gold_id_set),
        "result_query_count": len(result_ids),
        "result_unique_query_count": len(set(result_ids)),
        "duplicate_gold_query_ids": duplicate_gold,
        "duplicate_result_query_ids": duplicate_results,
        "missing_result_query_ids": missing,
        "extra_result_query_ids": extra,
        "malformed_result_rows": malformed_rows,
        "complete": not (duplicate_gold or duplicate_results or missing or extra or malformed_rows),
    }


def build_pdf_counters(
    pdf_gold_rows: list[dict[str, str]],
    query_results: list[Mapping[str, Any]],
) -> dict[str, Any]:
    gold_by_id = {row.get("query_id", ""): row for row in pdf_gold_rows}
    failure_reasons: Counter[str] = Counter()
    bucket_failure_reasons: dict[str, Counter[str]] = {}
    counters: Counter[str] = Counter()
    rows_with_page_no_hit_missing_physical: list[str] = []
    rows_with_page_no_hit_missing_bbox: list[str] = []

    stable_counter_keys = (
        "query_result_count",
        "empty_result_count",
        "expected_file_hit_at_top_k_count",
        "expected_file_absent_in_top_k_count",
        "expected_document_version_hit_at_top_k_count",
        "expected_document_version_absent_in_top_k_count",
        "page_no_hit_at_top_k_count",
        "expected_page_no_absent_in_top_k_count",
        "pdf_page_policy_match_at_top_k_count",
        "pdf_bbox_overlap_at_top_k_count",
        "pdf_exact_bbox_at_top_k_count",
        "location_match_count",
        "correct_page_no_hit_but_missing_physical_page_index_count",
        "correct_page_no_hit_but_missing_bbox_count",
        "expected_bbox_overlap_absent_in_top_k_count",
    )

    for row in query_results:
        query_id = str(row.get("query_id") or "")
        gold = gold_by_id.get(query_id, {})
        bucket = str(row.get("bucket") or gold.get("bucket") or "unknown")
        failure_reason = str(row.get("failure_reason") or "matched")
        failure_reasons[failure_reason] += 1
        bucket_failure_reasons.setdefault(bucket, Counter())[failure_reason] += 1
        counters["query_result_count"] += 1
        top_hits = list(row.get("top_k_results") or [])
        if not top_hits:
            counters["empty_result_count"] += 1
        expected_page_no = to_int(gold.get("expected_page_no") or row.get("expected_page_no"))
        expected_bbox = bool(gold.get("expected_bbox") or row.get("expected_bbox"))
        file_hits = [hit for hit in top_hits if breakdown(hit).get("file_match") is True]
        docv_hits = [hit for hit in file_hits if breakdown(hit).get("document_version_match") is True]
        page_no_hits = [
            hit for hit in docv_hits
            if expected_page_no is not None and location(hit).get("page_no") == expected_page_no
        ]
        page_policy_hits = [
            hit for hit in page_no_hits
            if breakdown(hit).get("pdf_page_match") is True
        ]
        bbox_overlap_hits = [
            hit for hit in page_no_hits
            if breakdown(hit).get("pdf_bbox_overlap") is True
        ]
        exact_bbox_hits = [
            hit for hit in page_no_hits
            if breakdown(hit).get("pdf_exact_bbox") is True
        ]
        missing_physical_hits = [
            hit for hit in page_no_hits
            if location(hit).get("physical_page_index") is None
        ]
        missing_bbox_hits = [
            hit for hit in page_no_hits
            if expected_bbox and not location(hit).get("bbox")
        ]

        if file_hits:
            counters["expected_file_hit_at_top_k_count"] += 1
        else:
            counters["expected_file_absent_in_top_k_count"] += 1
        if docv_hits:
            counters["expected_document_version_hit_at_top_k_count"] += 1
        else:
            counters["expected_document_version_absent_in_top_k_count"] += 1
        if page_no_hits:
            counters["page_no_hit_at_top_k_count"] += 1
        else:
            counters["expected_page_no_absent_in_top_k_count"] += 1
        if page_policy_hits:
            counters["pdf_page_policy_match_at_top_k_count"] += 1
        if bbox_overlap_hits:
            counters["pdf_bbox_overlap_at_top_k_count"] += 1
        if exact_bbox_hits:
            counters["pdf_exact_bbox_at_top_k_count"] += 1
        if row.get("location_match") is True:
            counters["location_match_count"] += 1
        if missing_physical_hits:
            counters["correct_page_no_hit_but_missing_physical_page_index_count"] += 1
            rows_with_page_no_hit_missing_physical.append(query_id)
        if missing_bbox_hits:
            counters["correct_page_no_hit_but_missing_bbox_count"] += 1
            rows_with_page_no_hit_missing_bbox.append(query_id)
        if expected_bbox and not bbox_overlap_hits:
            counters["expected_bbox_overlap_absent_in_top_k_count"] += 1

    return {
        **{key: int(counters.get(key) or 0) for key in stable_counter_keys},
        "failure_reason_counts": dict(sorted(failure_reasons.items())),
        "bucket_failure_reason_counts": {
            bucket: dict(sorted(counts.items()))
            for bucket, counts in sorted(bucket_failure_reasons.items())
        },
        "rows_with_correct_page_no_hit_but_missing_physical_page_index": rows_with_page_no_hit_missing_physical,
        "rows_with_correct_page_no_hit_but_missing_bbox": rows_with_page_no_hit_missing_bbox,
    }


def build_baseline_checks(
    *,
    baseline: Mapping[str, Any],
    retrieval_path: Path,
    baseline_path: Path,
    baseline_artifact_dir: Path,
    blockers: list[str],
) -> dict[str, Any]:
    observed_artifacts = artifact_hashes(baseline_artifact_dir)
    expected_artifacts = baseline.get("faiss_artifact_hashes") or {}
    artifact_checks = compare_hashes(expected_artifacts, observed_artifacts)
    retrieval_sha = file_sha256(retrieval_path) if retrieval_path.exists() else None
    descriptor_sha = file_sha256(baseline_path) if baseline_path.exists() else None
    descriptor_promotion_evidence = baseline.get("promotion_evidence")
    baseline_changed = any(check.get("status") != "MATCH" for check in artifact_checks)
    expected_retrieval_sha = baseline.get("retrieval_report_sha256")
    retrieval_hash_check = {
        "expected_sha256": expected_retrieval_sha,
        "observed_sha256": retrieval_sha,
        "status": "MATCH" if expected_retrieval_sha and expected_retrieval_sha == retrieval_sha else "MISMATCH",
    }
    if retrieval_hash_check["status"] != "MATCH":
        baseline_changed = True
    if descriptor_promotion_evidence is not False:
        blockers.append("baseline descriptor must keep promotion_evidence=false")
    return {
        "descriptor_path": str(baseline_path),
        "descriptor_sha256": descriptor_sha,
        "baseline_index_version": baseline.get("baseline_index_version"),
        "baseline_type": baseline.get("baseline_type"),
        "bootstrap_status": baseline.get("bootstrap_status"),
        "promotion_evidence": descriptor_promotion_evidence,
        "retrieval_report_hash_check": retrieval_hash_check,
        "artifact_dir": str(baseline_artifact_dir),
        "artifact_hash_checks": artifact_checks,
        "baseline_changed": baseline_changed,
    }


def build_xlsx_candidate_checks(
    *,
    lineage: Mapping[str, Any],
    lineage_path: Path,
    xlsx_artifact_dir: Path,
    warnings: list[str],
) -> dict[str, Any]:
    observed = artifact_hashes(xlsx_artifact_dir)
    xlsx_lineage = lineage.get("xlsx_candidate") if isinstance(lineage, Mapping) else {}
    xlsx_lineage = xlsx_lineage if isinstance(xlsx_lineage, Mapping) else {}
    expected = xlsx_lineage.get("artifact_hashes") if isinstance(xlsx_lineage, Mapping) else {}
    expected = expected if isinstance(expected, Mapping) else {}
    checks = compare_hashes(expected, observed)
    if not expected:
        warnings.append("xlsx candidate lineage artifact hashes unavailable; current hashes recorded only")
    changed = bool(expected) and any(check.get("status") != "MATCH" for check in checks)
    return {
        "lineage_report_path": str(lineage_path),
        "lineage_report_sha256": file_sha256(lineage_path) if lineage_path.exists() else None,
        "artifact_dir": str(xlsx_artifact_dir),
        "expected_index_version": xlsx_lineage.get("index_version"),
        "namespace": xlsx_lineage.get("namespace"),
        "artifact_hash_checks": checks,
        "xlsx_candidate_artifact_changed": changed,
    }


def build_pdf_candidate_artifact_check(
    *,
    pdf_artifact_dir: Path,
    blockers: list[str],
) -> dict[str, Any]:
    exists = pdf_artifact_dir.exists()
    artifact_hash_map = artifact_hashes(pdf_artifact_dir) if exists else {}
    if exists:
        blockers.append(
            "PDF candidate artifact dir must not exist during C0; run C2/C3 before creating PDF candidate artifacts"
        )
    return {
        "artifact_dir": str(pdf_artifact_dir),
        "exists": exists,
        "artifact_hashes": artifact_hash_map,
        "preexisting_artifact_blocker": exists,
    }


def compare_hashes(expected: Mapping[str, Any], observed: Mapping[str, Any]) -> list[dict[str, Any]]:
    names = sorted(set(expected.keys()) | set(observed.keys()) | set(ARTIFACT_FILES))
    checks = []
    for name in names:
        expected_hash = expected.get(name)
        observed_hash = observed.get(name)
        if expected_hash and observed_hash and expected_hash == observed_hash:
            status = "MATCH"
        elif expected_hash or observed_hash:
            status = "MISMATCH"
        else:
            status = "MISSING"
        checks.append({
            "name": name,
            "expected_sha256": expected_hash,
            "observed_sha256": observed_hash,
            "status": status,
        })
    return checks


def artifact_hashes(path: Path) -> dict[str, str]:
    return {
        name: file_sha256(path / name)
        for name in ARTIFACT_FILES
        if (path / name).exists()
    }


def pick_pdf_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "pdf_file_hit@10",
        "pdf_page_hit@10",
        "pdf_bbox_overlap@10",
        "pdf_exact_bbox@10",
        "pdf_citation_location_accuracy",
        "result_empty_count",
        "gold_label_invalid_count",
        "candidate_index_mismatch_count",
        "embedding_status_mismatch_count",
        "required_index_version_mismatch_count",
        "indexing_filtered_hit_count",
        "hidden_content_leakage_count",
        "search_error_count",
    )
    return {key: metrics.get(key) for key in keys if key in metrics}


def filter_pdf_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    result = []
    for row in rows:
        expected_type = (row.get("expected_location_type") or "").strip().lower()
        bucket = row.get("bucket") or ""
        if expected_type == "pdf" or bucket.startswith("pdf"):
            result.append(row)
    return result


def artifact_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() and path.is_file() else None,
    }


def breakdown(hit: Mapping[str, Any]) -> Mapping[str, Any]:
    value = hit.get("match_breakdown")
    return value if isinstance(value, Mapping) else {}


def location(hit: Mapping[str, Any]) -> Mapping[str, Any]:
    value = hit.get("location_json")
    return value if isinstance(value, Mapping) else {}


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def read_json(path: Path, blockers: list[str], label: str) -> dict[str, Any]:
    if not path.exists():
        blockers.append(f"{label} missing: {path}")
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        blockers.append(f"{label} must be a JSON object: {path}")
        return {}
    return payload


def read_optional_json(path: Path, warnings: list[str], label: str) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"{label} missing: {path}")
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def read_gold_rows(path: Path, blockers: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        blockers.append(f"gold CSV missing: {path}")
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        return list(csv.DictReader(fp))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def sanitize_backend_identity(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return sanitize_for_report(value)
    sanitized = {}
    for key, item in value.items():
        key_text = str(key)
        if key_text in SAFE_BACKEND_IDENTITY_KEYS:
            sanitized[key_text] = sanitize_for_report(item)
        else:
            sanitized[key_text] = "<redacted>"
    return sanitized


def sanitize_for_report(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized = {}
        for key, item in value.items():
            key_text = str(key)
            if is_sensitive_key(key_text):
                sanitized[key_text] = "<redacted>"
            else:
                sanitized[key_text] = sanitize_for_report(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_for_report(item) for item in value]
    if isinstance(value, str):
        return redact_sensitive_text(value)
    return value


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def redact_sensitive_text(value: str) -> str:
    lowered = value.lower()
    if any(marker in lowered for marker in ("password=", "token=", "secret=", "api_key=", "apikey=")):
        return "<redacted>"
    if URI_USERINFO_RE.search(value):
        return "<redacted>"
    return value


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval-report", default=str(DEFAULT_RETRIEVAL_REPORT))
    parser.add_argument("--quality-breakdown", default=str(DEFAULT_QUALITY_BREAKDOWN))
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--baseline-descriptor", default=str(DEFAULT_BASELINE_DESCRIPTOR))
    parser.add_argument("--baseline-artifact-dir", default=str(DEFAULT_BASELINE_ARTIFACT_DIR))
    parser.add_argument("--lineage-report", default=str(DEFAULT_LINEAGE_REPORT))
    parser.add_argument("--xlsx-candidate-artifact-dir", default=str(DEFAULT_XLSX_CANDIDATE_ARTIFACT_DIR))
    parser.add_argument("--pdf-index-version", default=PDF_INDEX_VERSION)
    parser.add_argument("--pdf-artifact-dir", default=PDF_ARTIFACT_DIR)
    parser.add_argument("--output", "--report", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
