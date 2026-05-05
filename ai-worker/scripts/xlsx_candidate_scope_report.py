"""Report the XLSX-only hidden-safe candidate scope for ingestion v2.

This is a read-only scope report. It does not claim SearchUnits, write vectors,
modify parser output, or produce promotion evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/xlsx_candidate_scope_report.json")
DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_v0.csv")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
DEFAULT_BASELINE_DESCRIPTOR = Path("eval/reports/rag-ingestion/initial_immutable_vector_baseline_descriptor.json")
DEFAULT_BASELINE_INDEX_VERSION = "initial-full72-vector-baseline-v0"
DEFAULT_CANDIDATE_INDEX_VERSION = "rag-ingestion-v2-xlsx-candidate-v1"
EXPECTED_SOURCE_FILE_TYPE = "SPREADSHEET"
EXPECTED_PARSER_VERSION = "xlsx-extract-v2-hidden-safe"
EXPECTED_HIDDEN_POLICY = "exclude_hidden"
EXPECTED_HIDDEN_POLICY_VERSION = "exclude-hidden-v1"
EXPECTED_SANITIZER_VERSION = "exclude-hidden-v1"

BASE_SCOPE_SQL = """
upper(coalesce(su.source_file_type, '')) = 'SPREADSHEET'
AND su.parser_version = 'xlsx-extract-v2-hidden-safe'
"""

CONTRACT_SQL = f"""
({BASE_SCOPE_SQL})
AND su.location_json IS NOT NULL
AND su.embedding_text IS NOT NULL
AND btrim(su.embedding_text) <> ''
AND su.citation_text IS NOT NULL
AND btrim(su.citation_text) <> ''
AND su.location_json->>'hidden_policy' = '{EXPECTED_HIDDEN_POLICY}'
AND su.location_json->>'hidden_policy_version' = '{EXPECTED_HIDDEN_POLICY_VERSION}'
AND su.location_json->>'sanitizer_version' = '{EXPECTED_SANITIZER_VERSION}'
AND NOT (
    coalesce(su.location_json->>'hidden', 'false') = 'true'
    OR coalesce(su.location_json->>'hidden_sheet', 'false') = 'true'
    OR coalesce(su.citation_text, '') LIKE '%%숨김%%'
)
AND EXISTS (
    SELECT 1
      FROM source_file sf
     WHERE sf.id = su.source_file_id
       AND sf.status = 'READY'
)
"""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_dsn = args.db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN
    blockers: list[str] = []
    warnings: list[str] = []
    try:
        baseline = read_optional_json(Path(args.baseline_descriptor))
        gold_scope = read_gold_scope(Path(args.gold), warnings)
        with connect(db_dsn) as conn:
            payload = build_report(
                conn,
                baseline=baseline,
                gold_scope=gold_scope,
                args=args,
                db_dsn=db_dsn,
                warnings=warnings,
                blockers=blockers,
            )
    except Exception as exc:
        payload = {
            "run_id": utc_run_id(),
            "generated_at": utc_timestamp(),
            "status": "FAIL",
            "report_role": "xlsx_candidate_scope_readiness",
            "promotion_evidence": False,
            "blockers": [f"scope inspection failed: {type(exc).__name__}: {exc}"],
            "warnings": warnings,
        }
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0 if payload.get("status") == "PASS" else 2


def build_report(
    conn: Any,
    *,
    baseline: dict[str, Any],
    gold_scope: dict[str, Any],
    args: argparse.Namespace,
    db_dsn: str,
    warnings: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    summary = fetch_one(conn, f"""
        SELECT
          count(*) FILTER (WHERE {BASE_SCOPE_SQL})::int AS hidden_safe_v2_rows,
          count(*) FILTER (WHERE {CONTRACT_SQL})::int AS candidate_rows,
          count(*) FILTER (
            WHERE upper(coalesce(su.source_file_type, '')) = 'SPREADSHEET'
              AND su.parser_version IS DISTINCT FROM %s
          )::int AS legacy_or_wrong_parser_rows_excluded,
          count(*) FILTER (
            WHERE {BASE_SCOPE_SQL}
              AND su.location_json->>'hidden_policy' IS DISTINCT FROM %s
          )::int AS hidden_policy_mismatch_count,
          count(*) FILTER (
            WHERE {BASE_SCOPE_SQL}
              AND su.location_json->>'hidden_policy_version' IS DISTINCT FROM %s
          )::int AS hidden_policy_version_mismatch_count,
          count(*) FILTER (
            WHERE {BASE_SCOPE_SQL}
              AND su.location_json->>'sanitizer_version' IS DISTINCT FROM %s
          )::int AS sanitizer_version_mismatch_count,
          count(*) FILTER (
            WHERE {BASE_SCOPE_SQL}
              AND (su.embedding_text IS NULL OR btrim(su.embedding_text) = '')
          )::int AS missing_embedding_text_count,
          count(*) FILTER (
            WHERE {BASE_SCOPE_SQL}
              AND (su.citation_text IS NULL OR btrim(su.citation_text) = '')
          )::int AS missing_citation_text_count,
          count(*) FILTER (
            WHERE {BASE_SCOPE_SQL}
              AND su.location_json IS NULL
          )::int AS missing_location_json_count,
          count(*) FILTER (
            WHERE {BASE_SCOPE_SQL}
              AND upper(coalesce(su.unit_type, '')) <> 'DOCUMENT'
              AND su.location_json->>'sheet_name' IS NULL
          )::int AS missing_sheet_name_count,
          count(*) FILTER (
            WHERE {BASE_SCOPE_SQL}
              AND upper(coalesce(su.unit_type, '')) <> 'DOCUMENT'
              AND su.location_json->>'cell_range' IS NULL
          )::int AS missing_cell_range_count,
          count(*) FILTER (
            WHERE {BASE_SCOPE_SQL}
              AND (
                upper(coalesce(su.unit_type, '')) = 'TABLE'
                OR lower(coalesce(su.chunk_type, '')) = 'table'
              )
              AND su.location_json->>'table_id' IS NULL
          )::int AS missing_table_metadata_count,
          count(*) FILTER (
            WHERE {BASE_SCOPE_SQL}
              AND (
                su.location_json->>'hidden' = 'true'
                OR su.location_json->>'hidden_sheet' = 'true'
                OR coalesce(su.citation_text, '') LIKE '%%숨김%%'
              )
          )::int AS hidden_leakage_count,
          count(*) FILTER (
            WHERE {BASE_SCOPE_SQL}
              AND NOT EXISTS (
                SELECT 1
                  FROM source_file sf
                 WHERE sf.id = su.source_file_id
                   AND sf.status = 'READY'
              )
          )::int AS source_not_ready_count
          FROM search_unit su
    """, (
        EXPECTED_PARSER_VERSION,
        EXPECTED_HIDDEN_POLICY,
        EXPECTED_HIDDEN_POLICY_VERSION,
        EXPECTED_SANITIZER_VERSION,
    ))
    status_counts = fetch_key_counts(conn, "coalesce(su.embedding_status, '')", f"WHERE {BASE_SCOPE_SQL}")
    index_counts = fetch_key_counts(conn, "coalesce(su.index_version, '')", f"WHERE {BASE_SCOPE_SQL}")
    chunk_counts = fetch_key_counts(conn, "coalesce(su.chunk_type, su.unit_type, '')", f"WHERE {BASE_SCOPE_SQL}")
    doc_rows = fetch_all(conn, f"""
        SELECT su.document_version_id,
               min(su.source_file_id) AS source_file_id,
               min(su.source_file_name) AS source_file_name,
               count(*)::int AS scoped_rows,
               count(*) FILTER (WHERE {CONTRACT_SQL})::int AS candidate_rows,
               count(*) FILTER (WHERE su.embedding_status = 'PENDING')::int AS pending_rows,
               count(*) FILTER (WHERE su.embedding_status = 'EMBEDDED')::int AS embedded_rows,
               count(*) FILTER (WHERE su.index_version = %s)::int AS rows_at_new_candidate_index_version
          FROM search_unit su
         WHERE {BASE_SCOPE_SQL}
         GROUP BY su.document_version_id
         ORDER BY su.document_version_id
    """, (args.candidate_index_version,))
    candidate_document_version_ids = sorted(
        str(row["document_version_id"])
        for row in doc_rows
        if row.get("document_version_id") and int(row.get("candidate_rows") or 0) > 0
    )
    candidate_source_file_ids = sorted({
        str(row["source_file_id"])
        for row in doc_rows
        if row.get("source_file_id") and int(row.get("candidate_rows") or 0) > 0
    })

    for key in (
        "hidden_policy_mismatch_count",
        "hidden_policy_version_mismatch_count",
        "sanitizer_version_mismatch_count",
        "missing_embedding_text_count",
        "missing_citation_text_count",
        "missing_location_json_count",
        "missing_sheet_name_count",
        "missing_cell_range_count",
        "missing_table_metadata_count",
        "hidden_leakage_count",
        "source_not_ready_count",
    ):
        if int(summary.get(key) or 0) != 0:
            blockers.append(f"{key} must be 0")
    if int(summary.get("candidate_rows") or 0) == 0:
        blockers.append("candidate_rows must be greater than 0")
    baseline_index = baseline.get("baseline_index_version")
    if baseline and baseline_index != args.baseline_index_version:
        blockers.append(
            f"baseline descriptor mismatch: expected {args.baseline_index_version}, got {baseline_index}"
        )
    if baseline and baseline.get("promotion_evidence") is not False:
        blockers.append("baseline descriptor must remain promotion_evidence=false")

    gold_docv = set(gold_scope.get("xlsx_document_version_ids") or [])
    candidate_docv = set(candidate_document_version_ids)
    missing_gold_docv = sorted(gold_docv - candidate_docv)
    if missing_gold_docv:
        blockers.append(f"xlsx gold document_version_ids missing from candidate scope: {missing_gold_docv}")

    payload = {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "PASS" if not blockers else "FAIL",
        "report_role": "xlsx_candidate_scope_readiness",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "allowUnscoped": False,
        "db_dsn": redact_dsn(db_dsn),
        "baseline": {
            "descriptor_path": str(Path(args.baseline_descriptor)),
            "baseline_index_version": baseline.get("baseline_index_version"),
            "vector_index_hash": baseline.get("vector_index_hash"),
            "faiss_artifact_hash": baseline.get("faiss_artifact_hash"),
            "promotion_evidence": baseline.get("promotion_evidence"),
        },
        "candidate_contract": {
            "candidate_index_version": args.candidate_index_version,
            "candidate_namespace_filter": args.candidate_namespace_filter,
            "source_file_type": EXPECTED_SOURCE_FILE_TYPE,
            "parser_version": EXPECTED_PARSER_VERSION,
            "hidden_policy": EXPECTED_HIDDEN_POLICY,
            "hidden_policy_version": EXPECTED_HIDDEN_POLICY_VERSION,
            "sanitizer_version": EXPECTED_SANITIZER_VERSION,
        },
        "gold_scope": gold_scope,
        "summary": summary,
        "status_counts": status_counts,
        "index_version_counts": index_counts,
        "chunk_type_counts": chunk_counts,
        "candidate_document_version_ids": candidate_document_version_ids,
        "candidate_source_file_ids": candidate_source_file_ids,
        "document_scope_details": rows_to_plain(doc_rows),
        "indexing_cli_scope": {
            "sourceFileTypes": [EXPECTED_SOURCE_FILE_TYPE],
            "parserVersions": [EXPECTED_PARSER_VERSION],
            "documentVersionIds": candidate_document_version_ids,
            "sourceFileIds": candidate_source_file_ids,
            "expectedIndexVersion": args.candidate_index_version,
            "indexVersion": args.candidate_index_version,
            "allowUnscoped": False,
        },
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "XLSX-only scope includes only hidden-safe v2 SearchUnits.",
            "Legacy xlsx-extract-v1, hidden-policy drift, sanitizer drift, and hidden leakage are excluded.",
            "This report is diagnostic scope evidence only and is not promotion evidence.",
        ],
    }
    return payload


def read_gold_scope(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"gold query file not found: {path}")
        return {"path": str(path), "exists": False}
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(row)
    xlsx_rows = [
        row for row in rows
        if (row.get("expected_location_type") or "").strip().lower() == "xlsx"
        or (row.get("bucket") or "").startswith("xlsx")
        or (row.get("bucket") or "") == "mixed_text_table"
    ]
    bucket_counts = Counter(row.get("bucket") or "unknown" for row in xlsx_rows)
    return {
        "path": str(path),
        "exists": True,
        "gold_row_count": len(rows),
        "xlsx_query_count": len(xlsx_rows),
        "xlsx_bucket_counts": dict(sorted(bucket_counts.items())),
        "xlsx_document_version_ids": sorted({
            row.get("expected_document_version_id", "").strip()
            for row in xlsx_rows
            if row.get("expected_document_version_id", "").strip()
        }),
    }


def connect(dsn: str) -> Any:
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("psycopg2 is required for DB inspection") from exc
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)


def fetch_one(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return dict(row or {})


def fetch_all(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def fetch_key_counts(conn: Any, key_sql: str, where_sql: str) -> dict[str, int]:
    rows = fetch_all(conn, f"""
        SELECT ({key_sql})::text AS key, count(*)::int AS count
          FROM search_unit su
          {where_sql}
         GROUP BY 1
         ORDER BY 1
    """)
    return {str(row["key"] or "UNKNOWN"): int(row["count"]) for row in rows}


def rows_to_plain(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: plain(value) for key, value in row.items()} for row in rows]


def plain(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_report(payload: dict[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_dsn(dsn: str) -> str:
    parts = []
    for part in str(dsn or "").split():
        if part.lower().startswith("password="):
            parts.append("password=<redacted>")
        else:
            parts.append(part)
    return " ".join(parts)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--db-dsn", default=None)
    parser.add_argument("--baseline-descriptor", default=str(DEFAULT_BASELINE_DESCRIPTOR))
    parser.add_argument("--baseline-index-version", default=DEFAULT_BASELINE_INDEX_VERSION)
    parser.add_argument("--candidate-index-version", default=DEFAULT_CANDIDATE_INDEX_VERSION)
    parser.add_argument("--candidate-namespace-filter", default=DEFAULT_CANDIDATE_INDEX_VERSION)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
