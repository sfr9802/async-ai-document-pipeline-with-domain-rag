"""Report candidate promotion-scope PDF/XLSX path readiness.

This deliberately does not replace the global path-hygiene report. It answers
only whether the promotion candidate scope from the full72 gold bindings is
free of parser/source/path/hidden-policy drift.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_GOLD = Path("eval/gold_queries_v0.csv")
DEFAULT_OUTPUT = Path("reports/rag_candidate_scope_path_readiness.json")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
DEFAULT_INDEX_VERSION = "rag-ingestion-v2-candidate"
DEFAULT_SOURCE_FILE_TYPES = ("SPREADSHEET", "PDF")
DEFAULT_PARSER_VERSIONS = ("xlsx-extract-v2-hidden-safe", "pdf-extract-v1", "pdf-extract-v2")
EXPECTED_XLSX_HIDDEN_POLICY = "exclude_hidden"
EXPECTED_XLSX_HIDDEN_POLICY_VERSION = "exclude-hidden-v1"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    warnings: list[str] = []
    blockers: list[str] = []
    document_version_ids = load_scope_ids(args, warnings)
    snapshot: dict[str, Any] = {}
    db_dsn = args.db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN
    try:
        with connect(db_dsn) as conn:
            snapshot = query_candidate_scope(
                conn,
                document_version_ids=document_version_ids,
                source_file_types=[item.upper() for item in args.source_file_type],
                parser_versions=list(args.parser_version),
                expected_index_version=args.expected_index_version,
            )
    except Exception as exc:
        blockers.append(f"DB inspection failed: {type(exc).__name__}: {exc}")

    summary = dict(snapshot.get("summary") or {})
    for key in (
        "missing_document_version_count",
        "source_file_not_ready_count",
        "missing_required_scope_row_count",
        "legacy_or_wrong_parser_row_count",
        "source_type_mismatch_count",
        "path_mixing_count",
        "missing_location_json_count",
        "missing_citation_text_count",
        "missing_embedding_text_count",
        "hidden_leakage_count",
        "xlsx_hidden_policy_mismatch_count",
        "xlsx_hidden_policy_version_mismatch_count",
    ):
        if int(summary.get(key) or 0) != 0:
            blockers.append(f"{key} must be 0 for candidate promotion-scope path readiness")

    payload = {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "scope": "candidate_promotion_scope_path_readiness",
        "global_path_hygiene_report": str(args.global_report),
        "status": "FAIL" if blockers else "PASS",
        "promotion_scope": True,
        "promotion_gate_input": True,
        "expected_index_version": args.expected_index_version,
        "sourceFileTypes": list(args.source_file_type),
        "parserVersions": list(args.parser_version),
        "document_version_ids": document_version_ids,
        "summary": summary,
        "document_versions": list(snapshot.get("document_versions") or []),
        "parser_version_breakdown": list(snapshot.get("parser_version_breakdown") or []),
        "path_mixing_findings": list(snapshot.get("path_mixing_findings") or []),
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "This report is scoped to full72 candidate document versions only.",
            "Global legacy XLSX/PDF drift belongs in the global path hygiene report and is not mixed into promotion-scope status.",
        ],
    }
    write_json(Path(args.output), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "PASS" else 2


def query_candidate_scope(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
    expected_index_version: str,
) -> dict[str, Any]:
    document_versions = fetch_all(conn, """
        WITH expected(docv) AS (SELECT unnest(%s::text[])),
        scoped AS (
          SELECT document_version_id,
                 count(*)::int AS scoped_count,
                 count(*) FILTER (WHERE embedding_status = 'PENDING')::int AS pending_count,
                 count(*) FILTER (WHERE embedding_status = 'EMBEDDED')::int AS embedded_count,
                 count(*) FILTER (WHERE index_version = %s)::int AS candidate_index_count,
                 count(*) FILTER (WHERE location_json IS NULL)::int AS missing_location_json_count,
                 count(*) FILTER (WHERE citation_text IS NULL OR btrim(citation_text) = '')::int AS missing_citation_text_count,
                 count(*) FILTER (WHERE embedding_text IS NULL OR btrim(embedding_text) = '')::int AS missing_embedding_text_count,
                 count(*) FILTER (
                   WHERE upper(coalesce(source_file_type, '')) = 'SPREADSHEET'
                     AND (
                       location_json->>'hidden' = 'true'
                       OR location_json->>'hidden_sheet' = 'true'
                       OR coalesce(citation_text, '') LIKE '%%숨김%%'
                     )
                 )::int AS hidden_leakage_count,
                 count(*) FILTER (
                   WHERE upper(coalesce(source_file_type, '')) = 'SPREADSHEET'
                     AND location_json->>'hidden_policy' IS DISTINCT FROM %s
                 )::int AS xlsx_hidden_policy_mismatch_count,
                 count(*) FILTER (
                   WHERE upper(coalesce(source_file_type, '')) = 'SPREADSHEET'
                     AND location_json->>'hidden_policy_version' IS DISTINCT FROM %s
                 )::int AS xlsx_hidden_policy_version_mismatch_count
            FROM search_unit
           WHERE document_version_id = ANY(%s)
             AND upper(coalesce(source_file_type, '')) = ANY(%s)
             AND parser_version = ANY(%s)
           GROUP BY document_version_id
        ),
        all_units AS (
          SELECT document_version_id,
                 count(*) FILTER (
                   WHERE parser_version <> ALL(%s)
                      OR upper(coalesce(source_file_type, '')) <> ALL(%s)
                 )::int AS legacy_or_wrong_parser_row_count
            FROM search_unit
           WHERE document_version_id = ANY(%s)
           GROUP BY document_version_id
        )
        SELECT e.docv AS document_version_id,
               dv.id IS NOT NULL AS document_version_exists,
               dv.source_file_name,
               dv.source_file_type AS document_version_source_file_type,
               dv.parse_status,
               sf.id AS source_file_id,
               sf.status AS source_file_status,
               coalesce(s.scoped_count, 0)::int AS scoped_count,
               coalesce(s.pending_count, 0)::int AS pending_count,
               coalesce(s.embedded_count, 0)::int AS embedded_count,
               coalesce(s.candidate_index_count, 0)::int AS candidate_index_count,
               coalesce(au.legacy_or_wrong_parser_row_count, 0)::int AS legacy_or_wrong_parser_row_count,
               coalesce(s.missing_location_json_count, 0)::int AS missing_location_json_count,
               coalesce(s.missing_citation_text_count, 0)::int AS missing_citation_text_count,
               coalesce(s.missing_embedding_text_count, 0)::int AS missing_embedding_text_count,
               coalesce(s.hidden_leakage_count, 0)::int AS hidden_leakage_count,
               coalesce(s.xlsx_hidden_policy_mismatch_count, 0)::int AS xlsx_hidden_policy_mismatch_count,
               coalesce(s.xlsx_hidden_policy_version_mismatch_count, 0)::int AS xlsx_hidden_policy_version_mismatch_count
          FROM expected e
          LEFT JOIN document_version dv ON dv.id = e.docv
          LEFT JOIN source_file sf ON sf.id = dv.source_file_id
          LEFT JOIN scoped s ON s.document_version_id = e.docv
          LEFT JOIN all_units au ON au.document_version_id = e.docv
         ORDER BY e.docv
    """, (
        document_version_ids,
        expected_index_version,
        EXPECTED_XLSX_HIDDEN_POLICY,
        EXPECTED_XLSX_HIDDEN_POLICY_VERSION,
        document_version_ids,
        source_file_types,
        parser_versions,
        parser_versions,
        source_file_types,
        document_version_ids,
    ))
    mixing = fetch_all(conn, """
        SELECT su.id AS search_unit_id,
               su.document_version_id,
               su.source_file_type,
               dv.source_file_type AS document_version_source_file_type,
               su.parser_version
          FROM search_unit su
          LEFT JOIN document_version dv ON dv.id = su.document_version_id
         WHERE su.document_version_id = ANY(%s)
           AND (
                (su.parser_version LIKE 'xlsx-%%' AND upper(coalesce(su.source_file_type, '')) <> 'SPREADSHEET')
             OR (su.parser_version LIKE 'pdf-%%' AND upper(coalesce(su.source_file_type, '')) <> 'PDF')
             OR (
                  dv.source_file_type IS NOT NULL
              AND upper(coalesce(su.source_file_type, '')) <> upper(coalesce(dv.source_file_type, ''))
             )
           )
         ORDER BY su.document_version_id, su.id
         LIMIT 25
    """, (document_version_ids,))
    breakdown = fetch_all(conn, """
        SELECT document_version_id,
               upper(coalesce(source_file_type, 'UNKNOWN')) AS source_file_type,
               coalesce(parser_version, 'UNKNOWN') AS parser_version,
               count(*)::int AS count
          FROM search_unit
         WHERE document_version_id = ANY(%s)
         GROUP BY 1, 2, 3
         ORDER BY 1, 2, 3
    """, (document_version_ids,))
    summary = {
        "document_version_count": len(document_version_ids),
        "missing_document_version_count": sum(1 for row in document_versions if not row.get("document_version_exists")),
        "source_file_not_ready_count": sum(
            1 for row in document_versions
            if row.get("document_version_exists")
            and row.get("source_file_status")
            and row.get("source_file_status") != "READY"
        ),
        "missing_required_scope_row_count": sum(1 for row in document_versions if int(row.get("scoped_count") or 0) == 0),
        "legacy_or_wrong_parser_row_count": sum(int(row.get("legacy_or_wrong_parser_row_count") or 0) for row in document_versions),
        "source_type_mismatch_count": sum(
            1 for row in document_versions
            if row.get("document_version_source_file_type")
            and row.get("document_version_source_file_type") not in source_file_types
        ),
        "path_mixing_count": len(mixing),
    }
    for key in (
        "scoped_count",
        "pending_count",
        "embedded_count",
        "candidate_index_count",
        "missing_location_json_count",
        "missing_citation_text_count",
        "missing_embedding_text_count",
        "hidden_leakage_count",
        "xlsx_hidden_policy_mismatch_count",
        "xlsx_hidden_policy_version_mismatch_count",
    ):
        summary[key] = sum(int(row.get(key) or 0) for row in document_versions)
    return {
        "summary": summary,
        "document_versions": rows_to_plain(document_versions),
        "parser_version_breakdown": rows_to_plain(breakdown),
        "path_mixing_findings": rows_to_plain(mixing),
    }


def load_scope_ids(args: argparse.Namespace, warnings: list[str]) -> list[str]:
    ids: set[str] = set(args.document_version_id or [])
    gold = Path(args.gold)
    if gold.exists():
        with gold.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                docv = (row.get("expected_document_version_id") or "").strip()
                if docv:
                    ids.add(docv)
    else:
        warnings.append(f"Gold query file not found: {gold}")
    return sorted(ids)


def connect(dsn: str) -> Any:
    try:
        import psycopg2  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("psycopg2 is required for live DB inspection") from exc
    return psycopg2.connect(dsn)


def fetch_all(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        names = [desc[0] for desc in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]


def rows_to_plain(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: plain_value(value) for key, value in row.items()} for row in rows]


def plain_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--global-report", default="reports/rag_path_separation_readiness.json")
    parser.add_argument("--db-dsn", default=None)
    parser.add_argument("--expected-index-version", default=DEFAULT_INDEX_VERSION)
    parser.add_argument("--document-version-id", action="append", default=None)
    parser.add_argument("--source-file-type", action="append", default=list(DEFAULT_SOURCE_FILE_TYPES))
    parser.add_argument("--parser-version", action="append", default=list(DEFAULT_PARSER_VERSIONS))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
