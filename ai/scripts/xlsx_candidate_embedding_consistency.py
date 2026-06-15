"""Verify XLSX-only candidate embedding consistency for a candidate namespace.

This report is diagnostic-only. It checks the hidden-safe v2 spreadsheet
SearchUnit path against embedding_record, ragmeta.chunks, and vector namespace
metadata without running promotion.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path("reports/rag_eval/rag-ingestion/xlsx_candidate_embedding_consistency_report.json")
DEFAULT_SCOPE_REPORT = Path("reports/rag_eval/rag-ingestion/xlsx_candidate_scope_report.json")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
DEFAULT_INDEX_VERSION = "rag-ingestion-v2-xlsx-candidate-v1"
EXPECTED_HIDDEN_POLICY = "exclude_hidden"
EXPECTED_HIDDEN_POLICY_VERSION = "exclude-hidden-v1"
EXPECTED_SANITIZER_VERSION = "exclude-hidden-v1"

BASE_SCOPE_SQL = """
upper(coalesce(su.source_file_type, '')) = 'SPREADSHEET'
AND su.parser_version = 'xlsx-extract-v2-hidden-safe'
"""

CANDIDATE_SCOPE_SQL = f"""
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
"""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_dsn = args.db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN
    blockers: list[str] = []
    warnings: list[str] = []
    try:
        scope_report = read_optional_json(Path(args.scope_report))
        document_version_ids = scope_document_version_ids(scope_report)
        if not document_version_ids and not args.allow_unscoped:
            blockers.append("scope report did not provide documentVersionIds and allowUnscoped=false")
        with connect(db_dsn) as conn:
            payload = build_report(
                conn,
                args=args,
                db_dsn=db_dsn,
                document_version_ids=document_version_ids,
                scope_report=scope_report,
                blockers=blockers,
                warnings=warnings,
            )
    except Exception as exc:
        payload = {
            "run_id": utc_run_id(),
            "generated_at": utc_timestamp(),
            "status": "FAIL",
            "report_role": "xlsx_candidate_embedding_consistency",
            "promotion_evidence": False,
            "blockers": [f"consistency inspection failed: {type(exc).__name__}: {exc}", *blockers],
            "warnings": warnings,
        }
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0 if payload.get("status") == "PASS" else 2


def build_report(
    conn: Any,
    *,
    args: argparse.Namespace,
    db_dsn: str,
    document_version_ids: list[str],
    scope_report: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    where, params = scoped_where(document_version_ids, allow_unscoped=args.allow_unscoped)
    expected = args.expected_index_version
    summary = fetch_one(conn, f"""
        SELECT
          count(*)::int AS scoped_rows,
          count(*) FILTER (WHERE {CANDIDATE_SCOPE_SQL})::int AS candidate_rows,
          count(*) FILTER (WHERE NOT ({CANDIDATE_SCOPE_SQL}))::int AS policy_excluded_rows,
          count(*) FILTER (
            WHERE upper(coalesce(su.source_file_type, '')) = 'SPREADSHEET'
              AND su.parser_version IS DISTINCT FROM 'xlsx-extract-v2-hidden-safe'
          )::int AS legacy_or_wrong_parser_rows_excluded,
          count(*) FILTER (
            WHERE ({CANDIDATE_SCOPE_SQL})
              AND su.embedding_status IS DISTINCT FROM 'EMBEDDED'
          )::int AS not_embedded_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_SCOPE_SQL})
              AND su.index_version IS DISTINCT FROM %s
          )::int AS index_version_mismatch_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_SCOPE_SQL})
              AND er.id IS NULL
          )::int AS embedding_record_missing_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_SCOPE_SQL})
              AND c.chunk_id IS NULL
          )::int AS candidate_chunk_missing_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_SCOPE_SQL})
              AND er.id IS NOT NULL
              AND (er.vector_id IS NULL OR er.vector_id NOT LIKE %s)
          )::int AS vector_namespace_mismatch_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_SCOPE_SQL})
              AND c.chunk_id IS NOT NULL
              AND er.id IS NOT NULL
              AND (
                c.extra_json->>'embeddingTextSha256' IS NULL
                OR c.extra_json->>'embeddingTextSha256' IS DISTINCT FROM er.embedding_text_sha256
              )
          )::int AS chunk_sha_mismatch_count,
          count(*) FILTER (
            WHERE ({BASE_SCOPE_SQL})
              AND (
                su.location_json->>'hidden' = 'true'
                OR su.location_json->>'hidden_sheet' = 'true'
                OR coalesce(su.citation_text, '') LIKE '%%숨김%%'
              )
          )::int AS hidden_leakage_count,
          count(*) FILTER (
            WHERE ({BASE_SCOPE_SQL})
              AND su.location_json->>'hidden_policy' IS DISTINCT FROM %s
          )::int AS hidden_policy_mismatch_count,
          count(*) FILTER (
            WHERE ({BASE_SCOPE_SQL})
              AND su.location_json->>'hidden_policy_version' IS DISTINCT FROM %s
          )::int AS hidden_policy_version_mismatch_count,
          count(*) FILTER (
            WHERE ({BASE_SCOPE_SQL})
              AND su.location_json->>'sanitizer_version' IS DISTINCT FROM %s
          )::int AS sanitizer_version_mismatch_count,
          count(*) FILTER (
            WHERE ({BASE_SCOPE_SQL})
              AND upper(coalesce(su.unit_type, '')) <> 'DOCUMENT'
              AND su.location_json->>'sheet_name' IS NULL
          )::int AS missing_sheet_name_count,
          count(*) FILTER (
            WHERE ({BASE_SCOPE_SQL})
              AND upper(coalesce(su.unit_type, '')) <> 'DOCUMENT'
              AND su.location_json->>'cell_range' IS NULL
          )::int AS missing_cell_range_count,
          count(*) FILTER (
            WHERE ({BASE_SCOPE_SQL})
              AND (
                upper(coalesce(su.unit_type, '')) = 'TABLE'
                OR lower(coalesce(su.chunk_type, '')) = 'table'
              )
              AND su.location_json->>'table_id' IS NULL
          )::int AS missing_table_metadata_count
          FROM search_unit su
          LEFT JOIN embedding_record er
            ON er.search_unit_id = su.id
           AND er.index_version = %s
          LEFT JOIN ragmeta.chunks c
            ON c.chunk_id = su.index_id
           AND c.index_version = %s
         WHERE {where}
    """, (
        expected,
        f"{expected}:%",
        EXPECTED_HIDDEN_POLICY,
        EXPECTED_HIDDEN_POLICY_VERSION,
        EXPECTED_SANITIZER_VERSION,
        expected,
        expected,
        *params,
    ))
    status_counts = fetch_key_counts(conn, "coalesce(su.embedding_status, '')", where, params)
    index_counts = fetch_key_counts(conn, "coalesce(su.index_version, '')", where, params)
    doc_rows = fetch_all(conn, f"""
        SELECT su.document_version_id,
               min(su.source_file_id) AS source_file_id,
               min(su.source_file_name) AS source_file_name,
               count(*)::int AS scoped_rows,
               count(*) FILTER (WHERE {CANDIDATE_SCOPE_SQL})::int AS candidate_rows,
               count(*) FILTER (WHERE su.embedding_status = 'EMBEDDED')::int AS embedded_rows,
               count(*) FILTER (WHERE su.index_version = %s)::int AS expected_index_version_rows
          FROM search_unit su
         WHERE {where}
         GROUP BY su.document_version_id
         ORDER BY su.document_version_id
    """, (expected, *params))
    sample_failures = fetch_all(conn, f"""
        SELECT su.id,
               su.document_version_id,
               su.source_file_name,
               su.unit_type,
               su.chunk_type,
               su.embedding_status,
               su.index_version,
               er.id IS NULL AS embedding_record_missing,
               c.chunk_id IS NULL AS candidate_chunk_missing,
               er.vector_id,
               su.index_id,
               su.location_json->>'sheet_name' AS sheet_name,
               su.location_json->>'cell_range' AS cell_range,
               su.location_json->>'table_id' AS table_id,
               su.location_json->>'hidden_policy' AS hidden_policy,
               su.location_json->>'hidden_policy_version' AS hidden_policy_version,
               su.location_json->>'sanitizer_version' AS sanitizer_version
          FROM search_unit su
          LEFT JOIN embedding_record er
            ON er.search_unit_id = su.id
           AND er.index_version = %s
          LEFT JOIN ragmeta.chunks c
            ON c.chunk_id = su.index_id
           AND c.index_version = %s
         WHERE {where}
           AND (
                NOT ({CANDIDATE_SCOPE_SQL})
             OR su.embedding_status IS DISTINCT FROM 'EMBEDDED'
             OR su.index_version IS DISTINCT FROM %s
             OR er.id IS NULL
             OR c.chunk_id IS NULL
             OR er.vector_id IS NULL
             OR er.vector_id NOT LIKE %s
             OR (
                c.extra_json->>'embeddingTextSha256' IS NULL
                OR c.extra_json->>'embeddingTextSha256' IS DISTINCT FROM er.embedding_text_sha256
             )
           )
         ORDER BY su.document_version_id, su.id
         LIMIT 25
    """, (
        expected,
        expected,
        *params,
        expected,
        f"{expected}:%",
    ))

    for key in (
        "not_embedded_count",
        "index_version_mismatch_count",
        "embedding_record_missing_count",
        "candidate_chunk_missing_count",
        "vector_namespace_mismatch_count",
        "chunk_sha_mismatch_count",
        "hidden_leakage_count",
        "hidden_policy_mismatch_count",
        "hidden_policy_version_mismatch_count",
        "sanitizer_version_mismatch_count",
        "missing_sheet_name_count",
        "missing_cell_range_count",
        "missing_table_metadata_count",
    ):
        if int(summary.get(key) or 0) != 0:
            blockers.append(f"{key} must be 0")
    if int(summary.get("candidate_rows") or 0) == 0:
        blockers.append("candidate_rows must be greater than 0")

    payload = {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "PASS" if not blockers else "FAIL",
        "report_role": "xlsx_candidate_embedding_consistency",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "expected_index_version": expected,
        "candidate_namespace_filter": args.candidate_namespace_filter,
        "allowUnscoped": bool(args.allow_unscoped),
        "db_dsn": redact_dsn(db_dsn),
        "scope_report": str(Path(args.scope_report)),
        "scope_report_status": scope_report.get("status"),
        "document_version_ids": document_version_ids,
        "sourceFileTypes": ["SPREADSHEET"],
        "parserVersions": ["xlsx-extract-v2-hidden-safe"],
        "hidden_policy": EXPECTED_HIDDEN_POLICY,
        "hidden_policy_version": EXPECTED_HIDDEN_POLICY_VERSION,
        "sanitizer_version": EXPECTED_SANITIZER_VERSION,
        "scoped_summary": summary,
        "status_counts": status_counts,
        "index_version_counts": index_counts,
        "document_scope_details": rows_to_plain(doc_rows),
        "sample_failures": rows_to_plain(sample_failures),
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "XLSX-only consistency checks are diagnostic-only and do not alter the promotion gate.",
            "Global legacy XLSX rows remain outside this candidate scope.",
        ],
    }
    return payload


def scoped_where(document_version_ids: list[str], *, allow_unscoped: bool) -> tuple[str, list[Any]]:
    where = f"({BASE_SCOPE_SQL})"
    params: list[Any] = []
    if document_version_ids or not allow_unscoped:
        where += " AND su.document_version_id = ANY(%s)"
        params.append(document_version_ids)
    return where, params


def scope_document_version_ids(scope_report: dict[str, Any]) -> list[str]:
    cli_scope = scope_report.get("indexing_cli_scope")
    if isinstance(cli_scope, dict):
        values = cli_scope.get("documentVersionIds")
    else:
        values = scope_report.get("candidate_document_version_ids")
    if not isinstance(values, list):
        return []
    return sorted({str(value).strip() for value in values if str(value).strip()})


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


def fetch_key_counts(conn: Any, key_sql: str, where: str, params: list[Any]) -> dict[str, int]:
    rows = fetch_all(conn, f"""
        SELECT ({key_sql})::text AS key, count(*)::int AS count
          FROM search_unit su
         WHERE {where}
         GROUP BY 1
         ORDER BY 1
    """, tuple(params))
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
    parser.add_argument("--scope-report", default=str(DEFAULT_SCOPE_REPORT))
    parser.add_argument("--db-dsn", default=None)
    parser.add_argument("--expected-index-version", default=DEFAULT_INDEX_VERSION)
    parser.add_argument("--candidate-namespace-filter", default=DEFAULT_INDEX_VERSION)
    parser.add_argument("--allow-unscoped", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
