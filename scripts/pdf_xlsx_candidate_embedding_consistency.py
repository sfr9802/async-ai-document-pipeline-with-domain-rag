"""Report scoped PDF/XLSX candidate embedding consistency.

This is a read-only full-scope readiness check. By default it reads the
full72 gold query CSV and uses only the unique expected_document_version_id
values from those rows as scope. It reports DIAGNOSTIC_ONLY when that scope
cannot be proven from explicit inputs or the gold CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path("reports/pdf_xlsx_candidate_embedding_consistency_report.json")
DEFAULT_GOLD_QUERY_FILE = Path("eval/gold_queries_v0.csv")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
DEFAULT_SOURCE_FILE_TYPES = ("SPREADSHEET", "PDF")
DEFAULT_PARSER_VERSIONS = ("xlsx-extract-v2-hidden-safe", "pdf-extract-v1", "pdf-extract-v2")
DEFAULT_INDEX_VERSION = "rag-ingestion-v2-candidate"
DEFAULT_EXPECTED_GOLD_ROW_COUNT = 72
EXPECTED_XLSX_HIDDEN_POLICY = "exclude_hidden"
EXPECTED_XLSX_HIDDEN_POLICY_VERSION = "exclude-hidden-v1"
POLICY_EXCLUDED_SQL = """
(
  upper(coalesce(su.source_file_type, '')) = 'PDF'
  AND upper(coalesce(su.unit_type, '')) = 'DOCUMENT'
)
OR (
  su.embedding_status = 'SKIPPED'
  AND su.embedding_status_detail = 'ocr location_json.ocr_confidence is required for lower-trust indexing'
)
"""
CANDIDATE_ROW_SQL = f"NOT ({POLICY_EXCLUDED_SQL})"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    blockers: list[str] = []
    warnings: list[str] = []
    db_dsn = args.db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN
    gold_scope = load_gold_document_version_scope(
        Path(args.gold_query_file) if args.gold_query_file else None,
        args.expected_gold_row_count,
        warnings,
    )
    expected_ids = load_expected_document_version_ids(args, warnings)
    if gold_scope.get("document_version_ids"):
        expected_ids = sorted(set(expected_ids) | set(gold_scope["document_version_ids"]))
    derived_ids: list[str] = []
    snapshot: dict[str, Any] = {}
    scope_sources = document_version_scope_sources(args, gold_scope)

    try:
        with connect(db_dsn) as conn:
            derived_ids = derive_document_version_ids(conn, args, warnings)
            scope_ids = sorted(set(expected_ids or derived_ids))
            if not scope_ids and not args.allow_unscoped:
                snapshot = {}
            else:
                snapshot = query_consistency_snapshot(
                    conn,
                    document_version_ids=scope_ids,
                    source_file_types=[item.upper() for item in args.source_file_type],
                    parser_versions=list(args.parser_version),
                    expected_index_version=args.expected_index_version,
                    allow_unscoped=args.allow_unscoped,
                    run_started_at=args.run_started_at,
                )
    except Exception as exc:
        blockers.append(f"DB inspection failed: {type(exc).__name__}: {exc}")

    expected_document_version_count = args.expected_document_version_count
    if expected_document_version_count is None:
        expected_document_version_count = len(expected_ids or derived_ids)

    payload = build_consistency_payload(
        snapshot=snapshot,
        explicit_document_version_ids=expected_ids,
        derived_document_version_ids=derived_ids,
        gold_scope=gold_scope,
        document_version_scope_source=scope_sources,
        blockers=blockers,
        warnings=warnings,
        expected_document_version_count=expected_document_version_count,
        expected_index_version=args.expected_index_version,
        source_file_types=list(args.source_file_type),
        parser_versions=list(args.parser_version),
        allow_unscoped=args.allow_unscoped,
        run_started_at=args.run_started_at,
    )
    write_json(Path(args.output), payload)
    print_json(payload)
    return 0 if payload["status"] == "PASS" else 2


def build_consistency_payload(
    *,
    snapshot: dict[str, Any],
    explicit_document_version_ids: list[str],
    derived_document_version_ids: list[str],
    gold_scope: dict[str, Any] | None = None,
    document_version_scope_source: list[str] | None = None,
    blockers: list[str],
    warnings: list[str],
    expected_document_version_count: int,
    expected_index_version: str,
    source_file_types: list[str],
    parser_versions: list[str],
    allow_unscoped: bool,
    run_started_at: str | None,
) -> dict[str, Any]:
    blocker_list = list(blockers)
    warning_list = list(warnings)
    scoped_ids = sorted(set(explicit_document_version_ids or derived_document_version_ids))
    expected_count = int(expected_document_version_count or 0)
    scope_complete = bool(scoped_ids) and (expected_count == 0 or len(scoped_ids) >= expected_count)
    scoped_summary = dict(snapshot.get("scoped_summary") or {})
    missing_expected_ids = list(snapshot.get("missing_expected_document_version_ids") or [])
    missing_contracts: list[str] = []
    gold = dict(gold_scope or {})

    if not scoped_ids and not allow_unscoped:
        missing_contracts.append("expected_document_version_ids are required unless allowUnscoped=true")
    if scoped_ids and not scope_complete:
        missing_contracts.append(
            f"expected_document_version_ids incomplete: expected {expected_document_version_count}, got {len(scoped_ids)}"
        )
    if gold:
        if not gold.get("exists", True):
            missing_contracts.append(f"gold query file not found: {gold.get('path')}")
        expected_gold_rows = gold.get("expected_gold_row_count")
        gold_rows = gold.get("gold_row_count")
        if expected_gold_rows is not None and gold_rows != expected_gold_rows:
            missing_contracts.append(f"gold query row count mismatch: expected {expected_gold_rows}, got {gold_rows}")
        missing_gold_docv_count = int(gold.get("missing_expected_document_version_id_count") or 0)
        if missing_gold_docv_count != 0:
            missing_contracts.append(
                f"gold queries missing expected_document_version_id: {missing_gold_docv_count}"
            )
    document_scope_details = list(snapshot.get("document_scope_details") or [])
    missing_document_versions = [
        item.get("document_version_id")
        for item in document_scope_details
        if not item.get("document_version_exists")
    ]
    not_ready_sources = [
        item.get("document_version_id")
        for item in document_scope_details
        if item.get("document_version_exists")
        and item.get("source_file_status")
        and item.get("source_file_status") != "READY"
    ]
    if missing_document_versions:
        missing_contracts.append(f"expected document_version rows are missing: {missing_document_versions}")
    if not_ready_sources:
        missing_contracts.append(f"expected document_version source files are not READY: {not_ready_sources}")
    if missing_expected_ids:
        missing_contracts.append(f"expected document_version_ids have no scoped candidate rows: {missing_expected_ids}")

    for key in (
        "missing_embedding_text_count",
        "missing_location_json_count",
        "missing_citation_text_count",
        "not_embedded_count",
        "index_version_mismatch_count",
        "embedding_record_missing_count",
        "candidate_chunk_missing_count",
        "vector_namespace_mismatch_count",
        "chunk_sha_mismatch_count",
        "hidden_leakage_count",
        "xlsx_hidden_policy_mismatch_count",
        "xlsx_hidden_policy_version_mismatch_count",
        "outside_scope_recent_embedded_count",
    ):
        if int(scoped_summary.get(key) or 0) != 0:
            blocker_list.append(f"{key} must be 0")

    status = "PASS"
    if blocker_list:
        status = "FAIL"
    elif missing_contracts:
        status = "DIAGNOSTIC_ONLY"

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "expected_index_version": expected_index_version,
        "sourceFileTypes": source_file_types,
        "parserVersions": parser_versions,
        "allowUnscoped": bool(allow_unscoped),
        "run_started_at": run_started_at,
        "expected_document_version_count": int(expected_document_version_count),
        "gold": gold,
        "document_version_scope_source": list(document_version_scope_source or []),
        "document_version_ids": scoped_ids,
        "explicit_document_version_ids": explicit_document_version_ids,
        "derived_document_version_ids": derived_document_version_ids,
        "scope": {
            "document_version_id_count": len(scoped_ids),
            "complete": scope_complete,
            "missing_expected_document_version_ids": missing_expected_ids,
            "missing_contracts": missing_contracts,
        },
        "status_counts": dict(snapshot.get("status_counts") or {}),
        "parser_version_breakdown": dict(snapshot.get("parser_version_breakdown") or {}),
        "source_file_type_breakdown": dict(snapshot.get("source_file_type_breakdown") or {}),
        "document_scope_details": document_scope_details,
        "scoped_summary": scoped_summary,
        "sample_failures": list(snapshot.get("sample_failures") or []),
        "blockers": blocker_list,
        "warnings": warning_list,
    }


def query_consistency_snapshot(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
    expected_index_version: str,
    allow_unscoped: bool,
    run_started_at: str | None,
) -> dict[str, Any]:
    summary = _query_scoped_summary(
        conn,
        document_version_ids=document_version_ids,
        source_file_types=source_file_types,
        parser_versions=parser_versions,
        expected_index_version=expected_index_version,
        allow_unscoped=allow_unscoped,
    )
    if run_started_at:
        summary["outside_scope_recent_embedded_count"] = outside_scope_recent_count(
            conn,
            document_version_ids=document_version_ids,
            source_file_types=source_file_types,
            parser_versions=parser_versions,
            expected_index_version=expected_index_version,
            run_started_at=run_started_at,
        )
    else:
        summary["outside_scope_recent_embedded_count"] = 0
    status_counts = fetch_key_counts(
        conn,
        key_sql="su.embedding_status",
        document_version_ids=document_version_ids,
        source_file_types=source_file_types,
        parser_versions=parser_versions,
        allow_unscoped=allow_unscoped,
    )
    parser_breakdown = fetch_key_counts(
        conn,
        key_sql="su.parser_version",
        document_version_ids=document_version_ids,
        source_file_types=source_file_types,
        parser_versions=parser_versions,
        allow_unscoped=allow_unscoped,
    )
    source_type_breakdown = fetch_key_counts(
        conn,
        key_sql="upper(coalesce(su.source_file_type, 'UNKNOWN'))",
        document_version_ids=document_version_ids,
        source_file_types=source_file_types,
        parser_versions=parser_versions,
        allow_unscoped=allow_unscoped,
    )
    sample_failures = fetch_sample_failures(
        conn,
        document_version_ids=document_version_ids,
        source_file_types=source_file_types,
        parser_versions=parser_versions,
        expected_index_version=expected_index_version,
        allow_unscoped=allow_unscoped,
    )
    policy_exclusions = fetch_policy_exclusions(
        conn,
        document_version_ids=document_version_ids,
        source_file_types=source_file_types,
        parser_versions=parser_versions,
        allow_unscoped=allow_unscoped,
    )
    missing_expected_ids = missing_document_version_ids(conn, document_version_ids, source_file_types, parser_versions)
    document_scope_details = fetch_document_scope_details(
        conn,
        document_version_ids=document_version_ids,
        source_file_types=source_file_types,
        parser_versions=parser_versions,
    )
    return {
        "scoped_summary": row_to_plain(summary),
        "status_counts": status_counts,
        "parser_version_breakdown": parser_breakdown,
        "source_file_type_breakdown": source_type_breakdown,
        "document_scope_details": document_scope_details,
        "sample_failures": sample_failures,
        "sample_policy_exclusions": policy_exclusions,
        "missing_expected_document_version_ids": missing_expected_ids,
    }


def _query_scoped_summary(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
    expected_index_version: str,
    allow_unscoped: bool,
) -> dict[str, Any]:
    where, params = scoped_where(
        document_version_ids=document_version_ids,
        source_file_types=source_file_types,
        parser_versions=parser_versions,
        allow_unscoped=allow_unscoped,
    )
    return fetch_one(conn, f"""
        SELECT
          count(*)::int AS scoped_count,
          count(*) FILTER (WHERE {CANDIDATE_ROW_SQL})::int AS candidate_scoped_count,
          count(*) FILTER (WHERE {POLICY_EXCLUDED_SQL})::int AS policy_excluded_count,
          count(*) FILTER (
            WHERE upper(coalesce(su.source_file_type, '')) = 'PDF'
              AND upper(coalesce(su.unit_type, '')) = 'DOCUMENT'
          )::int AS policy_excluded_pdf_document_count,
          count(*) FILTER (
            WHERE su.embedding_status = 'SKIPPED'
              AND su.embedding_status_detail = 'ocr location_json.ocr_confidence is required for lower-trust indexing'
          )::int AS policy_excluded_lower_trust_ocr_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_ROW_SQL})
              AND (su.embedding_text IS NULL OR btrim(su.embedding_text) = '')
          )::int AS missing_embedding_text_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_ROW_SQL})
              AND su.location_json IS NULL
          )::int AS missing_location_json_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_ROW_SQL})
              AND (su.citation_text IS NULL OR btrim(su.citation_text) = '')
          )::int AS missing_citation_text_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_ROW_SQL})
              AND su.embedding_status = 'PENDING'
              AND su.embedding_text IS NOT NULL
              AND btrim(su.embedding_text) <> ''
              AND su.location_json IS NOT NULL
              AND su.citation_text IS NOT NULL
              AND btrim(su.citation_text) <> ''
          )::int AS claimable_pending_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_ROW_SQL})
              AND su.embedding_status IS DISTINCT FROM 'EMBEDDED'
          )::int AS not_embedded_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_ROW_SQL})
              AND su.index_version IS DISTINCT FROM %s
          )::int AS index_version_mismatch_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_ROW_SQL})
              AND er.id IS NULL
          )::int AS embedding_record_missing_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_ROW_SQL})
              AND c.chunk_id IS NULL
          )::int AS candidate_chunk_missing_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_ROW_SQL})
              AND er.id IS NOT NULL
              AND (er.vector_id IS NULL OR er.vector_id NOT LIKE %s)
          )::int AS vector_namespace_mismatch_count,
          count(*) FILTER (
            WHERE ({CANDIDATE_ROW_SQL})
              AND c.chunk_id IS NOT NULL
              AND er.id IS NOT NULL
              AND (
                c.extra_json->>'embeddingTextSha256' IS NULL
                OR c.extra_json->>'embeddingTextSha256' IS DISTINCT FROM er.embedding_text_sha256
              )
          )::int AS chunk_sha_mismatch_count,
          count(*) FILTER (
            WHERE upper(coalesce(su.source_file_type, '')) IN ('SPREADSHEET', 'XLSX', 'XLSM')
              AND (
                su.location_json->>'hidden' = 'true'
                OR su.location_json->>'hidden_sheet' = 'true'
                OR coalesce(su.citation_text, '') LIKE '%%숨김%%'
              )
          )::int AS hidden_leakage_count,
          count(*) FILTER (
            WHERE upper(coalesce(su.source_file_type, '')) IN ('SPREADSHEET', 'XLSX', 'XLSM')
              AND su.location_json->>'hidden_policy' IS DISTINCT FROM %s
          )::int AS xlsx_hidden_policy_mismatch_count,
          count(*) FILTER (
            WHERE upper(coalesce(su.source_file_type, '')) IN ('SPREADSHEET', 'XLSX', 'XLSM')
              AND su.location_json->>'hidden_policy_version' IS DISTINCT FROM %s
          )::int AS xlsx_hidden_policy_version_mismatch_count
          FROM search_unit su
          LEFT JOIN embedding_record er
            ON er.search_unit_id = su.id
           AND er.index_version = %s
          LEFT JOIN ragmeta.chunks c
            ON c.chunk_id = su.index_id
           AND c.index_version = %s
         WHERE {where}
    """, (
        expected_index_version,
        f"{expected_index_version}:%",
        EXPECTED_XLSX_HIDDEN_POLICY,
        EXPECTED_XLSX_HIDDEN_POLICY_VERSION,
        expected_index_version,
        expected_index_version,
        *params,
    ))


def fetch_key_counts(
    conn: Any,
    *,
    key_sql: str,
    document_version_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
    allow_unscoped: bool,
) -> dict[str, int]:
    where, params = scoped_where(
        document_version_ids=document_version_ids,
        source_file_types=source_file_types,
        parser_versions=parser_versions,
        allow_unscoped=allow_unscoped,
    )
    rows = fetch_all(conn, f"""
        SELECT coalesce(({key_sql})::text, 'UNKNOWN') AS key,
               count(*)::int AS count
          FROM search_unit su
         WHERE {where}
         GROUP BY 1
         ORDER BY 1
    """, tuple(params))
    return {str(row["key"]): int(row["count"]) for row in rows}


def fetch_policy_exclusions(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
    allow_unscoped: bool,
) -> list[dict[str, Any]]:
    where, params = scoped_where(
        document_version_ids=document_version_ids,
        source_file_types=source_file_types,
        parser_versions=parser_versions,
        allow_unscoped=allow_unscoped,
    )
    return rows_to_plain(fetch_all(conn, f"""
        SELECT su.id,
               su.document_version_id,
               su.source_file_name,
               su.source_file_type,
               su.parser_version,
               su.unit_type,
               su.chunk_type,
               su.embedding_status,
               su.embedding_status_detail,
               su.location_json->>'page_no' AS page_no,
               su.location_json->>'page_label' AS page_label
          FROM search_unit su
         WHERE {where}
           AND ({POLICY_EXCLUDED_SQL})
         ORDER BY su.document_version_id, su.id
         LIMIT 25
    """, tuple(params)))


def fetch_sample_failures(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
    expected_index_version: str,
    allow_unscoped: bool,
) -> list[dict[str, Any]]:
    where, params = scoped_where(
        document_version_ids=document_version_ids,
        source_file_types=source_file_types,
        parser_versions=parser_versions,
        allow_unscoped=allow_unscoped,
    )
    return rows_to_plain(fetch_all(conn, f"""
        SELECT su.id,
               su.document_version_id,
               su.source_file_type,
               su.parser_version,
               su.embedding_status,
               su.index_version,
               er.id IS NULL AS embedding_record_missing,
               c.chunk_id IS NULL AS candidate_chunk_missing,
               er.vector_id,
               su.index_id,
               su.location_json->>'hidden_policy' AS hidden_policy,
               su.location_json->>'hidden_policy_version' AS hidden_policy_version
          FROM search_unit su
          LEFT JOIN embedding_record er
            ON er.search_unit_id = su.id
           AND er.index_version = %s
          LEFT JOIN ragmeta.chunks c
            ON c.chunk_id = su.index_id
           AND c.index_version = %s
         WHERE {where}
           AND ({CANDIDATE_ROW_SQL})
           AND (
                su.embedding_status IS DISTINCT FROM 'EMBEDDED'
             OR su.index_version IS DISTINCT FROM %s
             OR er.id IS NULL
             OR c.chunk_id IS NULL
             OR er.vector_id IS NULL
             OR er.vector_id NOT LIKE %s
             OR (
                upper(coalesce(su.source_file_type, '')) IN ('SPREADSHEET', 'XLSX', 'XLSM')
                AND su.location_json->>'hidden_policy' IS DISTINCT FROM %s
             )
             OR (
                upper(coalesce(su.source_file_type, '')) IN ('SPREADSHEET', 'XLSX', 'XLSM')
                AND su.location_json->>'hidden_policy_version' IS DISTINCT FROM %s
             )
           )
         ORDER BY su.document_version_id, su.id
         LIMIT 25
    """, (
        expected_index_version,
        expected_index_version,
        *params,
        expected_index_version,
        f"{expected_index_version}:%",
        EXPECTED_XLSX_HIDDEN_POLICY,
        EXPECTED_XLSX_HIDDEN_POLICY_VERSION,
    )))


def outside_scope_recent_count(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
    expected_index_version: str,
    run_started_at: str,
) -> int:
    row = fetch_one(conn, """
        SELECT count(*)::int AS count
          FROM search_unit su
         WHERE upper(coalesce(su.source_file_type, '')) = ANY(%s)
           AND su.parser_version = ANY(%s)
           AND su.index_version = %s
           AND su.embedding_status = 'EMBEDDED'
           AND su.embedded_at >= %s::timestamp
           AND NOT (su.document_version_id = ANY(%s))
    """, (source_file_types, parser_versions, expected_index_version, run_started_at, document_version_ids))
    return int(row.get("count") or 0)


def missing_document_version_ids(
    conn: Any,
    document_version_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
) -> list[str]:
    if not document_version_ids:
        return []
    rows = fetch_all(conn, """
        SELECT DISTINCT document_version_id
          FROM search_unit
         WHERE document_version_id = ANY(%s)
           AND upper(coalesce(source_file_type, '')) = ANY(%s)
           AND parser_version = ANY(%s)
    """, (document_version_ids, source_file_types, parser_versions))
    present = {str(row["document_version_id"]) for row in rows}
    return [docv for docv in document_version_ids if docv not in present]


def fetch_document_scope_details(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
) -> list[dict[str, Any]]:
    if not document_version_ids:
        return []
    rows = fetch_all(conn, """
        WITH expected(docv) AS (
          SELECT unnest(%s::text[])
        ),
        scoped AS (
          SELECT document_version_id,
                 count(*)::int AS scoped_count,
                 count(*) FILTER (WHERE embedding_status = 'PENDING')::int AS pending_count,
                 count(*) FILTER (WHERE embedding_status = 'EMBEDDED')::int AS embedded_count
            FROM search_unit
           WHERE document_version_id = ANY(%s)
             AND upper(coalesce(source_file_type, '')) = ANY(%s)
             AND parser_version = ANY(%s)
           GROUP BY document_version_id
        ),
        all_units AS (
          SELECT document_version_id,
                 count(*)::int AS any_search_unit_count,
                 coalesce(json_agg(DISTINCT parser_version) FILTER (WHERE parser_version IS NOT NULL), '[]'::json) AS parser_versions,
                 coalesce(json_agg(DISTINCT upper(coalesce(source_file_type, 'UNKNOWN'))), '[]'::json) AS source_file_types
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
               sf.status_detail AS source_file_status_detail,
               coalesce(au.any_search_unit_count, 0)::int AS any_search_unit_count,
               coalesce(s.scoped_count, 0)::int AS scoped_count,
               coalesce(s.pending_count, 0)::int AS pending_count,
               coalesce(s.embedded_count, 0)::int AS embedded_count,
               coalesce(au.parser_versions, '[]'::json) AS observed_parser_versions,
               coalesce(au.source_file_types, '[]'::json) AS observed_source_file_types
          FROM expected e
          LEFT JOIN document_version dv ON dv.id = e.docv
          LEFT JOIN source_file sf ON sf.id = dv.source_file_id
          LEFT JOIN all_units au ON au.document_version_id = e.docv
          LEFT JOIN scoped s ON s.document_version_id = e.docv
         ORDER BY e.docv
    """, (
        document_version_ids,
        document_version_ids,
        source_file_types,
        parser_versions,
        document_version_ids,
    ))
    return rows_to_plain(rows)


def scoped_where(
    *,
    document_version_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
    allow_unscoped: bool,
) -> tuple[str, list[Any]]:
    clauses = [
        "upper(coalesce(su.source_file_type, '')) = ANY(%s)",
        "su.parser_version = ANY(%s)",
    ]
    params: list[Any] = [source_file_types, parser_versions]
    if document_version_ids or not allow_unscoped:
        clauses.append("su.document_version_id = ANY(%s)")
        params.append(document_version_ids)
    return " AND ".join(clauses), params


def derive_document_version_ids(conn: Any, args: argparse.Namespace, warnings: list[str]) -> list[str]:
    ids = set()
    for path in [Path(item) for item in args.derive_from_report]:
        if not path.exists():
            warnings.append(f"Derivation artifact not found: {path}")
            continue
        try:
            payload = read_json(path)
        except Exception as exc:
            warnings.append(f"Could not read derivation artifact {path}: {exc}")
            continue
        ids.update(extract_document_version_ids(payload))
        source_file_ids = extract_source_file_ids(payload)
        if source_file_ids:
            rows = fetch_all(conn, """
                SELECT id
                  FROM document_version
                 WHERE source_file_id = ANY(%s)
                 ORDER BY id
            """, (sorted(source_file_ids),))
            ids.update(str(row["id"]) for row in rows)
    return sorted(ids)


def load_gold_document_version_scope(
    path: Path | None,
    expected_gold_row_count: int | None,
    warnings: list[str],
) -> dict[str, Any]:
    if path is None:
        return {
            "enabled": False,
            "path": None,
            "exists": False,
            "expected_gold_row_count": expected_gold_row_count,
            "gold_row_count": 0,
            "gold_unique_document_version_count": 0,
            "missing_expected_document_version_id_count": 0,
            "document_version_ids": [],
        }

    info: dict[str, Any] = {
        "enabled": True,
        "path": str(path),
        "exists": path.exists(),
        "expected_gold_row_count": expected_gold_row_count,
        "gold_row_count": 0,
        "gold_unique_document_version_count": 0,
        "missing_expected_document_version_id_count": 0,
        "document_version_ids": [],
    }
    if not path.exists():
        warnings.append(f"Gold query file not found: {path}")
        return info

    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    ids: set[str] = set()
    missing_docv = 0
    for row in rows:
        docv = (
            row.get("expected_document_version_id")
            or row.get("document_version_id")
            or row.get("documentVersionId")
        )
        if docv and str(docv).strip():
            ids.add(str(docv).strip())
        else:
            missing_docv += 1

    info["gold_row_count"] = len(rows)
    info["gold_unique_document_version_count"] = len(ids)
    info["missing_expected_document_version_id_count"] = missing_docv
    info["document_version_ids"] = sorted(ids)
    return info


def document_version_scope_sources(args: argparse.Namespace, gold_scope: dict[str, Any]) -> list[str]:
    sources: list[str] = []
    if gold_scope.get("document_version_ids"):
        sources.append("gold_query_file")
    if args.expected_document_version_id:
        sources.append("expected_document_version_id")
    if args.expected_document_version_ids_file:
        sources.append("expected_document_version_ids_file")
    if args.derive_from_report:
        sources.append("derive_from_report")
    return sources


def extract_document_version_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"document_version_id", "documentVersionId", "expected_document_version_id"} and item:
                found.add(str(item))
            elif key in {"document_version_ids", "documentVersionIds"} and isinstance(item, list):
                found.update(str(docv) for docv in item if docv)
            else:
                found.update(extract_document_version_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(extract_document_version_ids(item))
    return found


def extract_source_file_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"source_file_id", "sourceFileId"} and item:
                found.add(str(item))
            else:
                found.update(extract_source_file_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.update(extract_source_file_ids(item))
    return found


def load_expected_document_version_ids(args: argparse.Namespace, warnings: list[str]) -> list[str]:
    ids = set(str(item) for item in (args.expected_document_version_id or []) if str(item).strip())
    for path_text in args.expected_document_version_ids_file or []:
        path = Path(path_text)
        if not path.exists():
            warnings.append(f"Expected document_version_id file not found: {path}")
            continue
        ids.update(parse_document_version_id_file(path))
    return sorted(ids)


def parse_document_version_id_file(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        return extract_document_version_ids(payload)
    if path.suffix.lower() == ".csv":
        rows = csv.DictReader(text.splitlines())
        found: set[str] = set()
        for row in rows:
            for key in ("document_version_id", "documentVersionId", "expected_document_version_id"):
                if row.get(key):
                    found.add(str(row[key]))
        return found
    return set(re.findall(r"docv_[A-Za-z0-9_:-]+", text))


def connect(dsn: str) -> Any:
    try:
        import psycopg2  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("psycopg2 is required for live DB inspection") from exc
    return psycopg2.connect(dsn)


def fetch_one(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return {}
        names = [desc[0] for desc in cur.description]
        return dict(zip(names, row))


def fetch_all(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        names = [desc[0] for desc in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]


def rows_to_plain(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row_to_plain(row) for row in rows]


def row_to_plain(row: dict[str, Any]) -> dict[str, Any]:
    return {key: plain_value(value) for key, value in row.items()}


def plain_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--db-dsn", default=None)
    parser.add_argument("--expected-index-version", default=DEFAULT_INDEX_VERSION)
    parser.add_argument("--gold-query-file", default=str(DEFAULT_GOLD_QUERY_FILE))
    parser.add_argument("--expected-gold-row-count", type=int, default=DEFAULT_EXPECTED_GOLD_ROW_COUNT)
    parser.add_argument("--source-file-type", action="append", default=None)
    parser.add_argument("--parser-version", action="append", default=None)
    parser.add_argument("--expected-document-version-id", action="append", default=[])
    parser.add_argument("--expected-document-version-ids-file", action="append", default=[])
    parser.add_argument(
        "--expected-document-version-count",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--derive-from-report",
        action="append",
        default=[],
    )
    parser.add_argument("--run-started-at")
    parser.add_argument("--allow-unscoped", action="store_true")
    args = parser.parse_args(argv)
    if args.source_file_type is None:
        args.source_file_type = list(DEFAULT_SOURCE_FILE_TYPES)
    if args.parser_version is None:
        args.parser_version = list(DEFAULT_PARSER_VERSIONS)
    return args


if __name__ == "__main__":
    sys.exit(main())
