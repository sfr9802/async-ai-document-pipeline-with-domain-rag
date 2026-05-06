"""Report immutable baseline and XLSX candidate index lineage.

This script is read-only. It does not run promotion, rewrite baseline
descriptors, modify SearchUnits, or change vector artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/rag_candidate_index_lineage_report.json")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
DEFAULT_BASELINE_DESCRIPTOR = Path("eval/reports/rag-ingestion/initial_immutable_vector_baseline_descriptor.json")
DEFAULT_BASELINE_ARTIFACT_DIR = Path("eval/indexes/rag-data-canary")
DEFAULT_XLSX_CANDIDATE_ARTIFACT_DIR = Path("eval/indexes/rag-data-xlsx-candidate-v1")
DEFAULT_XLSX_SCOPE_REPORT = Path("eval/reports/rag-ingestion/xlsx_candidate_scope_report.json")
DEFAULT_XLSX_INDEXING_REPORT = Path("eval/reports/rag-ingestion/xlsx_candidate_indexing_report.json")
DEFAULT_XLSX_CONSISTENCY_REPORT = Path("eval/reports/rag-ingestion/xlsx_candidate_embedding_consistency_report.json")
DEFAULT_XLSX_DIAGNOSTIC_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json")
DEFAULT_FULL72_DIAGNOSTIC_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_full72_vector_diagnostic_report.json")
DEFAULT_MIXED_CONSISTENCY_REPORT = Path("eval/reports/rag-ingestion/pdf_xlsx_candidate_embedding_consistency_report.json")
DEFAULT_BASELINE_INDEX_VERSION = "initial-full72-vector-baseline-v0"
DEFAULT_XLSX_CANDIDATE_INDEX_VERSION = "rag-ingestion-v2-xlsx-candidate-v1"
PDF_PARSER_VERSIONS = ("pdf-extract-v1", "pdf-extract-v2")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_dsn = args.db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN
    blockers: list[str] = []
    warnings: list[str] = []
    baseline_descriptor = read_optional_json(Path(args.baseline_descriptor), warnings)
    xlsx_scope = read_optional_json(Path(args.xlsx_scope_report), warnings)
    xlsx_indexing = read_optional_json(Path(args.xlsx_indexing_report), warnings)
    xlsx_consistency = read_optional_json(Path(args.xlsx_consistency_report), warnings)
    xlsx_diagnostic = read_optional_json(Path(args.xlsx_diagnostic_report), warnings)
    full72_diagnostic = read_optional_json(Path(args.full72_diagnostic_report), warnings)
    mixed_consistency = read_optional_json(Path(args.mixed_consistency_report), warnings)

    db_distribution: dict[str, Any]
    try:
        with connect(db_dsn) as conn:
            db_distribution = fetch_index_distribution(conn)
    except Exception as exc:
        db_distribution = {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        warnings.append("DB distribution unavailable; lineage report uses file artifacts only")

    payload = build_report(
        args=args,
        db_dsn=db_dsn,
        baseline_descriptor=baseline_descriptor,
        xlsx_scope=xlsx_scope,
        xlsx_indexing=xlsx_indexing,
        xlsx_consistency=xlsx_consistency,
        xlsx_diagnostic=xlsx_diagnostic,
        full72_diagnostic=full72_diagnostic,
        mixed_consistency=mixed_consistency,
        db_distribution=db_distribution,
        blockers=blockers,
        warnings=warnings,
    )
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def build_report(
    *,
    args: argparse.Namespace,
    db_dsn: str,
    baseline_descriptor: Mapping[str, Any],
    xlsx_scope: Mapping[str, Any],
    xlsx_indexing: Mapping[str, Any],
    xlsx_consistency: Mapping[str, Any],
    xlsx_diagnostic: Mapping[str, Any],
    full72_diagnostic: Mapping[str, Any],
    mixed_consistency: Mapping[str, Any],
    db_distribution: Mapping[str, Any],
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    baseline_path = Path(args.baseline_descriptor)
    baseline_artifact_dir = Path(args.baseline_artifact_dir)
    xlsx_artifact_dir = Path(args.xlsx_candidate_artifact_dir)
    baseline_file_hash = sha256_file_optional(baseline_path)
    baseline_artifacts = artifact_hashes(baseline_artifact_dir)
    xlsx_artifacts = artifact_hashes(xlsx_artifact_dir)
    xlsx_build = read_optional_json(xlsx_artifact_dir / "build.json", warnings)

    if baseline_descriptor.get("baseline_index_version") != args.baseline_index_version:
        blockers.append("baseline descriptor index version mismatch")
    if baseline_descriptor.get("promotion_evidence") is not False:
        blockers.append("baseline descriptor must remain promotion_evidence=false")
    if baseline_descriptor.get("immutable_baseline") is not True:
        blockers.append("baseline descriptor must declare immutable_baseline=true")
    if xlsx_consistency.get("status") != "PASS":
        blockers.append("xlsx candidate consistency report must PASS")
    if xlsx_scope.get("status") != "PASS":
        blockers.append("xlsx candidate scope report must PASS")
    if xlsx_indexing.get("allowUnscoped") is not False:
        blockers.append("xlsx indexing report must declare allowUnscoped=false")
    if xlsx_diagnostic.get("promotion_evidence") is not False:
        blockers.append("xlsx diagnostic report must remain promotion_evidence=false")
    if xlsx_build.get("index_version") != args.xlsx_candidate_index_version:
        blockers.append("xlsx candidate build index_version mismatch")

    baseline_descriptor_hash_check = compare_hash(
        baseline_file_hash,
        args.expected_baseline_descriptor_hash,
    )
    if baseline_descriptor_hash_check["status"] == "MISMATCH":
        blockers.append("baseline descriptor hash changed from expected frozen value")
    baseline_artifact_checks = compare_baseline_artifacts(baseline_descriptor, baseline_artifacts)
    for item in baseline_artifact_checks:
        if item["status"] == "MISMATCH":
            blockers.append(f"baseline artifact hash mismatch: {item['name']}")

    historical_reports = historical_report_status(
        full72_diagnostic=full72_diagnostic,
        mixed_consistency=mixed_consistency,
        xlsx_consistency=xlsx_consistency,
        xlsx_build=xlsx_build,
        full72_path=Path(args.full72_diagnostic_report),
        mixed_consistency_path=Path(args.mixed_consistency_report),
    )
    for report in historical_reports:
        if report.get("historical_snapshot"):
            warnings.append(f"{report['path']} is historical relative to current XLSX candidate DB/artifact state")

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "FAIL" if blockers else ("PASS_WITH_WARNINGS" if warnings else "PASS"),
        "report_role": "candidate_index_lineage_report",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "db_dsn": redact_dsn(db_dsn),
        "immutable_baseline": {
            "descriptor_path": str(baseline_path),
            "descriptor_sha256": baseline_file_hash,
            "descriptor_hash_check": baseline_descriptor_hash_check,
            "baseline_type": baseline_descriptor.get("baseline_type"),
            "bootstrap_status": baseline_descriptor.get("bootstrap_status"),
            "immutable_baseline": baseline_descriptor.get("immutable_baseline"),
            "candidate_snapshot": baseline_descriptor.get("candidate_snapshot"),
            "candidate_snapshot_baseline": baseline_descriptor.get("candidate_snapshot_baseline"),
            "baseline_index_version": baseline_descriptor.get("baseline_index_version"),
            "source_candidate_index_version": baseline_descriptor.get("source_candidate_index_version"),
            "candidate_namespace_filter": baseline_descriptor.get("candidate_namespace_filter"),
            "retrieval_backend": baseline_descriptor.get("retrieval_backend"),
            "backend_identity": baseline_descriptor.get("backend_identity") or {},
            "eval_dataset_id": baseline_descriptor.get("eval_dataset_id"),
            "eval_dataset_version": baseline_descriptor.get("eval_dataset_version"),
            "baseline_dataset_version": baseline_descriptor.get("baseline_dataset_version"),
            "eval_dataset_sha256": baseline_descriptor.get("eval_dataset_sha256"),
            "gold_query_row_count": baseline_descriptor.get("gold_query_row_count"),
            "document_version_scope": baseline_descriptor.get("document_version_scope") or {},
            "embedding_model": baseline_descriptor.get("embedding_model"),
            "embedding_text_variant": baseline_descriptor.get("embedding_text_variant"),
            "embedding_text_builder_version": baseline_descriptor.get("embedding_text_builder_version"),
            "embedding_text_sha256": baseline_descriptor.get("embedding_text_sha256"),
            "vector_index_hash": baseline_descriptor.get("vector_index_hash"),
            "faiss_artifact_hash": baseline_descriptor.get("faiss_artifact_hash"),
            "faiss_artifact_hashes": baseline_descriptor.get("faiss_artifact_hashes") or {},
            "artifact_dir": str(baseline_artifact_dir),
            "artifact_hashes": baseline_artifacts,
            "artifact_hash_checks": baseline_artifact_checks,
            "retrieval_report_path": baseline_descriptor.get("retrieval_report_path"),
            "retrieval_report_sha256": baseline_descriptor.get("retrieval_report_sha256"),
            "immutable_baseline_report_hash": baseline_descriptor.get("immutable_baseline_report_hash"),
            "metrics_report_path": baseline_descriptor.get("metrics_report_path"),
            "metrics_report_sha256": baseline_descriptor.get("metrics_report_sha256"),
            "consistency_report_path": baseline_descriptor.get("consistency_report_path"),
            "consistency_report_sha256": baseline_descriptor.get("consistency_report_sha256"),
            "candidate_scope_readiness_report_path": baseline_descriptor.get("candidate_scope_readiness_report_path"),
            "candidate_scope_readiness_report_sha256": baseline_descriptor.get("candidate_scope_readiness_report_sha256"),
            "promotion_evidence": baseline_descriptor.get("promotion_evidence"),
            "promotion_gate_effect": baseline_descriptor.get("promotion_gate_effect"),
            "bootstrap_is_not_promotion": baseline_descriptor.get("bootstrap_is_not_promotion"),
            "current_candidate_promotion_evidence": baseline_descriptor.get("current_candidate_promotion_evidence"),
            "usable_as_baseline_for_future_candidates": baseline_descriptor.get("usable_as_baseline_for_future_candidates"),
        },
        "xlsx_candidate": {
            "index_version": args.xlsx_candidate_index_version,
            "namespace": args.xlsx_candidate_namespace,
            "artifact_dir": str(xlsx_artifact_dir),
            "artifact_hashes": xlsx_artifacts,
            "artifact_dir_hash": directory_hash(xlsx_artifacts),
            "build": xlsx_build,
            "chunk_count": xlsx_build.get("chunk_count"),
            "scope_report_path": str(Path(args.xlsx_scope_report)),
            "scope_report_sha256": sha256_file_optional(Path(args.xlsx_scope_report)),
            "scope_status": xlsx_scope.get("status"),
            "candidate_contract": xlsx_scope.get("candidate_contract") or {},
            "scope_summary": xlsx_scope.get("summary") or {},
            "scope_status_counts": xlsx_scope.get("status_counts") or {},
            "scope_index_version_counts": xlsx_scope.get("index_version_counts") or {},
            "chunk_type_counts": xlsx_scope.get("chunk_type_counts") or {},
            "candidate_document_version_ids": xlsx_scope.get("candidate_document_version_ids") or [],
            "candidate_source_file_ids": xlsx_scope.get("candidate_source_file_ids") or [],
            "indexing_cli_scope": xlsx_scope.get("indexing_cli_scope") or {},
            "indexing_report_path": str(Path(args.xlsx_indexing_report)),
            "indexing_report_sha256": sha256_file_optional(Path(args.xlsx_indexing_report)),
            "indexing_status": xlsx_indexing.get("status"),
            "indexing_totals": xlsx_indexing.get("totals") or {},
            "allowUnscoped": xlsx_indexing.get("allowUnscoped"),
            "consistency_report_path": str(Path(args.xlsx_consistency_report)),
            "consistency_report_sha256": sha256_file_optional(Path(args.xlsx_consistency_report)),
            "consistency_status": xlsx_consistency.get("status"),
            "consistency_summary": xlsx_consistency.get("scoped_summary") or {},
            "consistency_index_version_counts": xlsx_consistency.get("index_version_counts") or {},
            "diagnostic_report_path": str(Path(args.xlsx_diagnostic_report)),
            "diagnostic_report_sha256": sha256_file_optional(Path(args.xlsx_diagnostic_report)),
            "diagnostic_promotion_evidence": xlsx_diagnostic.get("promotion_evidence"),
            "diagnostic_evidence_role": xlsx_diagnostic.get("evidence_role"),
            "diagnostic_metrics": xlsx_diagnostic.get("metrics") or {},
        },
        "search_unit_index_version_distribution": db_distribution,
        "historical_reports": historical_reports,
        "lineage_interpretation": {
            "baseline_is_frozen_initial_bootstrap": True,
            "xlsx_candidate_is_diagnostic_only": True,
            "xlsx_candidate_is_immutable_baseline": False,
            "mixed_full72_db_level_reports_are_historical": any(
                report.get("historical_snapshot") for report in historical_reports
            ),
            "decision": (
                "Use the immutable baseline descriptor/artifacts only as frozen baseline lineage. "
                "Use rag-data-xlsx-candidate-v1 only as XLSX candidate diagnostic lineage."
            ),
        },
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "notes": [
            "This report is read-only and diagnostic-only.",
            "It does not run promotion or write a new immutable baseline descriptor.",
            "It marks mixed full72 reports as historical when their index namespace differs from the current XLSX candidate.",
        ],
    }


def historical_report_status(
    *,
    full72_diagnostic: Mapping[str, Any],
    mixed_consistency: Mapping[str, Any],
    xlsx_consistency: Mapping[str, Any],
    xlsx_build: Mapping[str, Any],
    full72_path: Path,
    mixed_consistency_path: Path,
) -> list[dict[str, Any]]:
    xlsx_index = str(xlsx_build.get("index_version") or xlsx_consistency.get("expected_index_version") or "")
    reports = []
    full72_backend = full72_diagnostic.get("backend_identity") or {}
    full72_required = full72_diagnostic.get("required_index_version") or (full72_diagnostic.get("metrics") or {}).get(
        "required_index_version"
    )
    full72_namespace = full72_backend.get("index_namespace_filter")
    full72_index_dir = full72_backend.get("index_dir")
    reports.append(
        {
            "path": str(full72_path),
            "report_role": "full72_vector_diagnostic_baseline_bootstrap_source",
            "promotion_evidence": full72_diagnostic.get("promotion_evidence"),
            "evidence_role": full72_diagnostic.get("evidence_role"),
            "required_index_version": full72_required,
            "index_namespace_filter": full72_namespace,
            "index_dir": full72_index_dir,
            "historical_snapshot": bool(xlsx_index and full72_required and full72_required != xlsx_index),
            "stale_relative_to": xlsx_index,
            "reason": "full72 diagnostic points to baseline/canary namespace, not current XLSX candidate namespace",
        }
    )
    mixed_expected = mixed_consistency.get("expected_index_version")
    reports.append(
        {
            "path": str(mixed_consistency_path),
            "report_role": "mixed_pdf_xlsx_consistency_historical_snapshot",
            "promotion_evidence": mixed_consistency.get("promotion_evidence"),
            "expected_index_version": mixed_expected,
            "sourceFileTypes": mixed_consistency.get("sourceFileTypes") or [],
            "parserVersions": mixed_consistency.get("parserVersions") or [],
            "historical_snapshot": bool(xlsx_index and mixed_expected and mixed_expected != xlsx_index),
            "stale_relative_to": xlsx_index,
            "reason": "mixed consistency expected index differs from XLSX-only candidate index after reindexing",
        }
    )
    return reports


def fetch_index_distribution(conn: Any) -> dict[str, Any]:
    rows = fetch_all(conn, """
        SELECT upper(coalesce(su.source_file_type, 'UNKNOWN')) AS source_file_type,
               coalesce(su.parser_version, '') AS parser_version,
               coalesce(su.index_version, '') AS index_version,
               coalesce(su.embedding_status, '') AS embedding_status,
               count(*)::int AS row_count
          FROM search_unit su
         WHERE (
                upper(coalesce(su.source_file_type, '')) = 'SPREADSHEET'
                AND su.parser_version = 'xlsx-extract-v2-hidden-safe'
               )
            OR (
                upper(coalesce(su.source_file_type, '')) = 'PDF'
                AND su.parser_version = ANY(%s)
               )
         GROUP BY 1, 2, 3, 4
         ORDER BY 1, 2, 3, 4
    """, (list(PDF_PARSER_VERSIONS),))
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        plain = dict(row)
        by_type[str(plain.get("source_file_type") or "UNKNOWN")].append(plain)
    return {
        "available": True,
        "rows": rows_to_plain(rows),
        "by_source_file_type": {key: rows_to_plain(value) for key, value in sorted(by_type.items())},
    }


def compare_baseline_artifacts(
    baseline_descriptor: Mapping[str, Any],
    observed: Mapping[str, str | None],
) -> list[dict[str, Any]]:
    expected = baseline_descriptor.get("faiss_artifact_hashes")
    if not isinstance(expected, Mapping):
        return []
    checks = []
    for name, expected_hash in sorted(expected.items()):
        checks.append(
            {
                "name": name,
                "expected_sha256": expected_hash,
                "observed_sha256": observed.get(str(name)),
                "status": compare_hash(observed.get(str(name)), str(expected_hash)).get("status"),
            }
        )
    return checks


def compare_hash(observed: str | None, expected: str | None) -> dict[str, Any]:
    if not expected:
        return {"status": "NOT_CHECKED", "observed_sha256": observed, "expected_sha256": expected}
    status = "MATCH" if observed and observed.lower() == expected.lower() else "MISMATCH"
    return {"status": status, "observed_sha256": observed, "expected_sha256": expected}


def artifact_hashes(path: Path) -> dict[str, str | None]:
    return {
        "faiss.index": sha256_file_optional(path / "faiss.index"),
        "build.json": sha256_file_optional(path / "build.json"),
        "ingest_manifest.json": sha256_file_optional(path / "ingest_manifest.json"),
    }


def directory_hash(hashes: Mapping[str, str | None]) -> str | None:
    if not hashes or any(value is None for value in hashes.values()):
        return None
    digest = hashlib.sha256()
    for name, value in sorted(hashes.items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def sha256_file_optional(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_optional_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"JSON report missing: {path}")
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        warnings.append(f"JSON report must be an object: {path}")
        return {}
    return payload


def connect(dsn: str) -> Any:
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("psycopg2 is required for live DB inspection") from exc
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)


def fetch_all(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def rows_to_plain(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_report(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def redact_dsn(value: str) -> str:
    parts = []
    for item in value.split():
        if item.lower().startswith("password="):
            parts.append("password=<redacted>")
        else:
            parts.append(item)
    return " ".join(parts)


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--db-dsn", default=None)
    parser.add_argument("--baseline-descriptor", default=str(DEFAULT_BASELINE_DESCRIPTOR))
    parser.add_argument("--baseline-artifact-dir", default=str(DEFAULT_BASELINE_ARTIFACT_DIR))
    parser.add_argument("--xlsx-candidate-artifact-dir", default=str(DEFAULT_XLSX_CANDIDATE_ARTIFACT_DIR))
    parser.add_argument("--xlsx-scope-report", default=str(DEFAULT_XLSX_SCOPE_REPORT))
    parser.add_argument("--xlsx-indexing-report", default=str(DEFAULT_XLSX_INDEXING_REPORT))
    parser.add_argument("--xlsx-consistency-report", default=str(DEFAULT_XLSX_CONSISTENCY_REPORT))
    parser.add_argument("--xlsx-diagnostic-report", default=str(DEFAULT_XLSX_DIAGNOSTIC_REPORT))
    parser.add_argument("--full72-diagnostic-report", default=str(DEFAULT_FULL72_DIAGNOSTIC_REPORT))
    parser.add_argument("--mixed-consistency-report", default=str(DEFAULT_MIXED_CONSISTENCY_REPORT))
    parser.add_argument("--baseline-index-version", default=DEFAULT_BASELINE_INDEX_VERSION)
    parser.add_argument("--xlsx-candidate-index-version", default=DEFAULT_XLSX_CANDIDATE_INDEX_VERSION)
    parser.add_argument("--xlsx-candidate-namespace", default=DEFAULT_XLSX_CANDIDATE_INDEX_VERSION)
    parser.add_argument(
        "--expected-baseline-descriptor-hash",
        default="3b9f09b078f01e2a9ab557dacb6059245bf3357ddb1092e834b3c52d7240662a",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
