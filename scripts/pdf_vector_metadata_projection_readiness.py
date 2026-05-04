"""Audit Track C PDF vector metadata projection readiness.

This is a read-only C2 report. It consumes the explicit C1 PDF scope and
checks whether SearchUnit location/citation metadata can survive the
SearchUnit -> ragmeta chunk -> vector-hit conversion contract. It does not run
retrieval, claim SearchUnits, build vectors, update artifacts, or create
promotion evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pdf_candidate_scope_report import (  # noqa: E402
    DEFAULT_DB_DSN,
    PDF_ARTIFACT_DIR,
    PDF_INDEX_VERSION,
    artifact_identity,
    connect,
    dedupe,
    fetch_all,
    fetch_one,
    file_sha256,
    print_report,
    read_json,
    redact_dsn,
    rows_to_plain,
    utc_run_id,
    utc_timestamp,
    write_json,
)


DEFAULT_SCOPE_REPORT = Path("reports/pdf_candidate_scope_report.json")
DEFAULT_OUTPUT = Path("reports/pdf_vector_metadata_projection_readiness.json")

POLICY_EXCLUDED_SQL = """
(
  upper(coalesce(su.unit_type, '')) = 'DOCUMENT'
  OR lower(coalesce(su.chunk_type, '')) = 'document_summary'
)
OR (
  su.embedding_status = 'SKIPPED'
  AND su.embedding_status_detail = 'ocr location_json.ocr_confidence is required for lower-trust indexing'
)
"""
INDEXABLE_SQL = f"NOT ({POLICY_EXCLUDED_SQL})"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_dsn = args.db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN
    blockers: list[str] = []
    warnings: list[str] = []
    scope_path = Path(args.scope_report)
    scope_report = read_json(scope_path, blockers, "c1_scope_report")

    try:
        document_version_ids = scope_document_version_ids(scope_report)
        parser_versions = scope_parser_versions(scope_report)
        with connect(db_dsn) as conn:
            snapshot = query_snapshot(
                conn,
                document_version_ids=document_version_ids,
                parser_versions=parser_versions,
                expected_index_version=args.expected_index_version,
            )
    except Exception as exc:
        snapshot = {}
        blockers.append(f"C2 metadata projection inspection failed: {type(exc).__name__}: {exc}")

    payload = build_payload(
        scope_report=scope_report,
        scope_report_path=scope_path,
        db_snapshot=snapshot,
        db_dsn=db_dsn,
        expected_index_version=args.expected_index_version,
        blockers=blockers,
        warnings=warnings,
    )
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def build_payload(
    *,
    scope_report: Mapping[str, Any],
    scope_report_path: Path,
    db_snapshot: Mapping[str, Any],
    db_dsn: str,
    expected_index_version: str,
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    blocker_list = list(blockers)
    warning_list = list(warnings)
    summary = dict(db_snapshot.get("summary") or {})
    ragmeta_projection = dict(db_snapshot.get("ragmeta_projection") or {})
    current_projection = dict(db_snapshot.get("current_ragmeta_projection") or {})
    inherited_warnings = list(scope_report.get("warnings") or [])

    if scope_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blocker_list.append(f"C1 scope report must pass before C2; got {scope_report.get('status')}")
    if scope_report.get("promotion_evidence") is not False:
        blocker_list.append("C1 scope report must keep promotion_evidence=false")
    if scope_report.get("evidence_role") != "diagnostic":
        blocker_list.append("C1 scope report must keep evidence_role=diagnostic")
    if scope_report.get("allowUnscoped") is not False:
        blocker_list.append("C1 scope report must keep allowUnscoped=false")

    document_version_ids = scope_document_version_ids(scope_report)
    source_file_ids = list((scope_report.get("scope") or {}).get("source_file_ids") or [])
    parser_versions = scope_parser_versions(scope_report)
    if not document_version_ids:
        blocker_list.append("C1 scope report must provide document_version_ids")
    if not parser_versions:
        blocker_list.append("C1 scope report must provide parser_versions")

    completion_counters = {
        "missing_physical_page_index_for_page_bound_chunks": int(
            summary.get("missing_physical_page_index_for_page_bound_chunks") or 0
        ),
        "missing_page_no_for_page_bound_chunks": int(summary.get("missing_page_no_for_page_bound_chunks") or 0),
        "missing_bbox_for_text_block_chunks": int(summary.get("missing_bbox_for_text_block_chunks") or 0),
        "missing_ocr_confidence_for_ocr_chunks": int(summary.get("missing_ocr_confidence_for_ocr_chunks") or 0),
        "vector_hit_location_reconstruction_failure_count": int(
            summary.get("vector_hit_location_reconstruction_failure_count") or 0
        ),
        "missing_block_type_count": int(summary.get("missing_block_type_count") or 0),
        "missing_ocr_used_count": int(summary.get("missing_ocr_used_count") or 0),
        "citation_reconstruction_missing_count": int(summary.get("citation_reconstruction_missing_count") or 0),
        "source_lookup_missing_count": int(summary.get("source_lookup_missing_count") or 0),
        "stored_ragmeta_location_mismatch_count": int(
            ragmeta_projection.get("stored_ragmeta_location_mismatch_count") or 0
        ),
        "stored_ragmeta_missing_location_json_count": int(
            ragmeta_projection.get("stored_ragmeta_missing_location_json_count") or 0
        ),
        "stored_ragmeta_missing_citation_text_count": int(
            ragmeta_projection.get("stored_ragmeta_missing_citation_text_count") or 0
        ),
        "current_ragmeta_location_json_unusable_count": int(
            current_projection.get("current_ragmeta_location_json_unusable_count") or 0
        ),
        "current_ragmeta_missing_physical_page_index_count": int(
            current_projection.get("current_ragmeta_missing_physical_page_index_count") or 0
        ),
        "current_ragmeta_missing_bbox_for_text_block_count": int(
            current_projection.get("current_ragmeta_missing_bbox_for_text_block_count") or 0
        ),
    }
    metadata_projection_blocker_count = sum(completion_counters.values())
    if metadata_projection_blocker_count:
        blocker_list.append("metadata_projection_blocker_count must be 0")

    if int(summary.get("indexable_rows") or 0) == 0:
        blocker_list.append("indexable_rows must be greater than 0")

    policy_excluded_ocr = int(summary.get("policy_excluded_ocr_confidence_missing_count") or 0)
    if policy_excluded_ocr:
        warning_list.append(
            f"policy_excluded_ocr_confidence_missing_count={policy_excluded_ocr}; excluded before C4 indexing"
        )
    policy_excluded_document = int(summary.get("policy_excluded_document_summary_count") or 0)
    if policy_excluded_document:
        warning_list.append(
            f"policy_excluded_document_summary_count={policy_excluded_document}; document summaries are not directly embedded"
        )
    if int(ragmeta_projection.get("ragmeta_candidate_chunk_count") or 0) == 0:
        warning_list.append("ragmeta_candidate_chunk_count=0; stored chunk projection comparison is deferred until C4")

    status = "PASS"
    if blocker_list:
        status = "FAIL"
    elif warning_list or inherited_warnings:
        status = "PASS_WITH_WARNINGS"

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C2",
        "report_role": "pdf_vector_metadata_projection_readiness",
        "source_file_type": "PDF",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "index_version": expected_index_version,
        "artifact_dir": PDF_ARTIFACT_DIR,
        "allowUnscoped": False,
        "retrieval_execution": "not_run_by_this_script",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "db_dsn": redact_dsn(db_dsn),
        "input_artifacts": [artifact_identity(scope_report_path)],
        "c1_scope": {
            "path": str(scope_report_path),
            "status": scope_report.get("status"),
            "sha256": file_sha256(scope_report_path) if scope_report_path.exists() else None,
            "document_version_ids": document_version_ids,
            "source_file_ids": source_file_ids,
            "parser_versions": parser_versions,
            "inherited_warnings": inherited_warnings,
        },
        "summary": {
            **summary,
            "metadata_projection_blocker_count": metadata_projection_blocker_count,
            "block_type_bbox_policy_applied": True,
        },
        "completion_counters": completion_counters,
        "ragmeta_projection": ragmeta_projection,
        "current_ragmeta_projection": current_projection,
        "vector_hit_conversion_contract": {
            "mode": "current_ragmeta_and_simulated_search_unit_index_metadata",
            "search_unit_indexing_service_keys": [
                "location_json",
                "locationJson",
                "citation_text",
                "citationText",
                "source_file_name",
                "sourceFileName",
                "document_version_id",
                "documentVersionId",
            ],
            "retrieval_eval_location_lookup_keys": ["locationJson", "location_json"],
            "stored_candidate_ragmeta_chunk_projection_checked": bool(
                int(ragmeta_projection.get("ragmeta_candidate_chunk_count") or 0)
            ),
            "current_ragmeta_chunk_projection_checked": bool(
                int(current_projection.get("current_ragmeta_joined_embedded_count") or 0)
            ),
        },
        "distributions": dict(db_snapshot.get("distributions") or {}),
        "document_scope_details": list(db_snapshot.get("document_scope_details") or []),
        "sample_blockers": list(db_snapshot.get("sample_blockers") or []),
        "sample_warnings": list(db_snapshot.get("sample_warnings") or []),
        "blockers": dedupe(blocker_list),
        "warnings": dedupe([*inherited_warnings, *warning_list]),
        "next_action": (
            "Run C3 or resolve C2 blockers before C4 indexing."
            if status == "FAIL"
            else "Use this C2 report with C3 before C4 indexing."
        ),
        "notes": [
            "C2 is diagnostic-only and does not prove retrieval ranking quality.",
            "C1 OCR/bbox warnings are classified here as policy exclusions unless they affect indexable rows.",
            "Stored ragmeta candidate chunk projection is expected to be absent before C4 creates the PDF candidate namespace.",
            "Existing non-PDF-candidate ragmeta chunks are checked separately so legacy projection failures are not mistaken for C4 proof.",
        ],
    }


def query_snapshot(
    conn: Any,
    *,
    document_version_ids: list[str],
    parser_versions: list[str],
    expected_index_version: str,
) -> dict[str, Any]:
    summary = query_summary(conn, document_version_ids, parser_versions)
    ragmeta_projection = query_ragmeta_projection(conn, document_version_ids, parser_versions, expected_index_version)
    current_ragmeta_projection = query_current_ragmeta_projection(conn, document_version_ids, parser_versions)
    return {
        "summary": summary,
        "ragmeta_projection": ragmeta_projection,
        "current_ragmeta_projection": current_ragmeta_projection,
        "distributions": query_distributions(conn, document_version_ids, parser_versions),
        "document_scope_details": query_document_scope_details(conn, document_version_ids, parser_versions),
        "sample_blockers": [
            *query_sample_blockers(conn, document_version_ids, parser_versions),
            *query_current_ragmeta_sample_blockers(conn, document_version_ids, parser_versions),
        ],
        "sample_warnings": query_sample_warnings(conn, document_version_ids, parser_versions),
    }


def query_summary(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, int]:
    row = fetch_one(conn, f"""
        WITH scoped AS (
          SELECT su.*,
                 lower(coalesce(su.chunk_type, su.location_json->>'block_type', su.unit_type, '')) AS chunk_type_norm,
                 lower(coalesce(su.location_json->>'block_type', su.chunk_type, su.unit_type, '')) AS block_type_norm,
                 ({POLICY_EXCLUDED_SQL}) AS policy_excluded
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        )
        SELECT
          count(*)::int AS scoped_rows,
          count(*) FILTER (WHERE NOT policy_excluded)::int AS indexable_rows,
          count(*) FILTER (WHERE policy_excluded)::int AS policy_excluded_rows,
          count(*) FILTER (
            WHERE upper(coalesce(unit_type, '')) = 'DOCUMENT'
               OR lower(coalesce(chunk_type, '')) = 'document_summary'
          )::int AS policy_excluded_document_summary_count,
          count(*) FILTER (
            WHERE embedding_status = 'SKIPPED'
              AND embedding_status_detail = 'ocr location_json.ocr_confidence is required for lower-trust indexing'
          )::int AS policy_excluded_ocr_confidence_missing_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND location_json IS NULL
          )::int AS missing_location_json_for_indexable_chunks,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND block_type_norm <> 'document_summary'
              AND location_json->>'physical_page_index' IS NULL
          )::int AS missing_physical_page_index_for_page_bound_chunks,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND block_type_norm <> 'document_summary'
              AND location_json->>'page_no' IS NULL
          )::int AS missing_page_no_for_page_bound_chunks,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND location_json->>'block_type' IS NULL
          )::int AS missing_block_type_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND location_json->>'ocr_used' IS NULL
          )::int AS missing_ocr_used_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND chunk_type_norm IN ('paragraph', 'text', 'ocr_text', 'ocr_line_group', 'table')
              AND location_json->>'bbox' IS NULL
          )::int AS missing_bbox_for_text_block_chunks,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND coalesce((location_json->>'ocr_used')::boolean, false)
              AND location_json->>'ocr_confidence' IS NULL
          )::int AS missing_ocr_confidence_for_ocr_chunks,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND (citation_text IS NULL OR btrim(citation_text) = '')
          )::int AS citation_reconstruction_missing_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND source_file_id IS NULL
          )::int AS source_lookup_missing_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND NOT (
                location_json ? 'type'
                AND (
                     location_json ? 'physical_page_index'
                  OR location_json ? 'page_no'
                  OR location_json ? 'page_label'
                )
              )
          )::int AS vector_hit_location_reconstruction_failure_count
          FROM scoped
    """, (document_version_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_ragmeta_projection(
    conn: Any,
    document_version_ids: list[str],
    parser_versions: list[str],
    expected_index_version: str,
) -> dict[str, int]:
    row = fetch_one(conn, """
        SELECT
          count(c.chunk_id)::int AS ragmeta_candidate_chunk_count,
          count(*) FILTER (
            WHERE c.chunk_id IS NOT NULL
              AND NOT (c.extra_json ? 'locationJson' OR c.extra_json ? 'location_json')
          )::int AS stored_ragmeta_missing_location_json_count,
          count(*) FILTER (
            WHERE c.chunk_id IS NOT NULL
              AND c.extra_json->'locationJson' IS DISTINCT FROM su.location_json
              AND c.extra_json->'location_json' IS DISTINCT FROM su.location_json
          )::int AS stored_ragmeta_location_mismatch_count,
          count(*) FILTER (
            WHERE c.chunk_id IS NOT NULL
              AND coalesce(c.extra_json->>'citationText', c.extra_json->>'citation_text', '') = ''
          )::int AS stored_ragmeta_missing_citation_text_count
          FROM search_unit su
          LEFT JOIN ragmeta.chunks c
            ON c.chunk_id = su.index_id
           AND c.index_version = %s
         WHERE su.document_version_id = ANY(%s)
           AND upper(coalesce(su.source_file_type, '')) = 'PDF'
           AND su.parser_version = ANY(%s)
    """, (expected_index_version, document_version_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_current_ragmeta_projection(
    conn: Any,
    document_version_ids: list[str],
    parser_versions: list[str],
) -> dict[str, int]:
    row = fetch_one(conn, """
        WITH joined AS (
          SELECT su.*,
                 lower(coalesce(su.chunk_type, su.location_json->>'block_type', su.unit_type, '')) AS chunk_type_norm,
                 c.extra_json,
                 coalesce(c.extra_json->'location_json', c.extra_json->'locationJson') AS chunk_location
            FROM search_unit su
            JOIN ragmeta.chunks c
              ON c.chunk_id = su.index_id
             AND c.index_version = su.index_version
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
             AND su.embedding_status = 'EMBEDDED'
        )
        SELECT
          count(*)::int AS current_ragmeta_joined_embedded_count,
          count(*) FILTER (
            WHERE chunk_location IS NOT NULL
          )::int AS current_ragmeta_location_json_object_count,
          count(*) FILTER (
            WHERE chunk_location IS NOT NULL
              AND chunk_location ? 'nodeType'
              AND NOT (chunk_location ? 'type')
          )::int AS current_ragmeta_location_json_jackson_shape_count,
          count(*) FILTER (
            WHERE chunk_location IS NULL
               OR NOT (chunk_location ? 'type')
          )::int AS current_ragmeta_location_json_unusable_count,
          count(*) FILTER (
            WHERE chunk_location IS NULL
               OR NOT (chunk_location ? 'physical_page_index')
          )::int AS current_ragmeta_missing_physical_page_index_count,
          count(*) FILTER (
            WHERE chunk_type_norm IN ('paragraph', 'text', 'ocr_text', 'ocr_line_group', 'table')
              AND (chunk_location IS NULL OR NOT (chunk_location ? 'bbox'))
          )::int AS current_ragmeta_missing_bbox_for_text_block_count,
          count(*) FILTER (
            WHERE extra_json ? 'physicalPageIndex'
               OR extra_json ? 'physical_page_index'
          )::int AS current_ragmeta_top_level_page_index_count,
          count(*) FILTER (
            WHERE extra_json ? 'bbox'
          )::int AS current_ragmeta_top_level_bbox_count
          FROM joined
    """, (document_version_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_current_ragmeta_sample_blockers(
    conn: Any,
    document_version_ids: list[str],
    parser_versions: list[str],
) -> list[dict[str, Any]]:
    rows = fetch_all(conn, """
        WITH joined AS (
          SELECT su.id,
                 su.document_version_id,
                 su.source_file_name,
                 su.unit_type,
                 su.chunk_type,
                 su.location_json,
                 su.citation_text,
                 su.index_id,
                 su.index_version,
                 lower(coalesce(su.chunk_type, su.location_json->>'block_type', su.unit_type, '')) AS chunk_type_norm,
                 c.extra_json,
                 coalesce(c.extra_json->'location_json', c.extra_json->'locationJson') AS chunk_location
            FROM search_unit su
            JOIN ragmeta.chunks c
              ON c.chunk_id = su.index_id
             AND c.index_version = su.index_version
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
             AND su.embedding_status = 'EMBEDDED'
        )
        SELECT id,
               document_version_id,
               source_file_name,
               unit_type,
               chunk_type,
               index_id,
               index_version,
               location_json->>'page_no' AS source_page_no,
               location_json->>'physical_page_index' AS source_physical_page_index,
               location_json->>'bbox' AS source_bbox,
               citation_text,
               CASE
                 WHEN chunk_location IS NULL THEN 'current_ragmeta_missing_location_json'
                 WHEN chunk_location ? 'nodeType' AND NOT (chunk_location ? 'type')
                   THEN 'current_ragmeta_location_json_jackson_shape'
                 WHEN NOT (chunk_location ? 'type') THEN 'current_ragmeta_location_json_unusable'
                 WHEN NOT (chunk_location ? 'physical_page_index') THEN 'current_ragmeta_missing_physical_page_index'
                 WHEN chunk_type_norm IN ('paragraph', 'text', 'ocr_text', 'ocr_line_group', 'table')
                   AND NOT (chunk_location ? 'bbox') THEN 'current_ragmeta_missing_bbox'
                 ELSE 'current_ragmeta_projection_unknown'
               END AS blocker_reason,
               left(chunk_location::text, 320) AS chunk_location_preview,
               left(extra_json::text, 320) AS extra_json_preview
          FROM joined
         WHERE chunk_location IS NULL
            OR NOT (chunk_location ? 'type')
            OR NOT (chunk_location ? 'physical_page_index')
            OR (
                 chunk_type_norm IN ('paragraph', 'text', 'ocr_text', 'ocr_line_group', 'table')
                 AND NOT (chunk_location ? 'bbox')
               )
         ORDER BY document_version_id, id
         LIMIT 25
    """, (document_version_ids, parser_versions))
    return rows_to_plain(rows)


def query_distributions(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, dict[str, int]]:
    return {
        "embedding_status_counts": key_counts(conn, "coalesce(su.embedding_status, 'UNKNOWN')", document_version_ids, parser_versions),
        "chunk_type_counts": key_counts(conn, "coalesce(su.chunk_type, su.unit_type, 'UNKNOWN')", document_version_ids, parser_versions),
        "block_type_counts": key_counts(conn, "coalesce(su.location_json->>'block_type', su.chunk_type, su.unit_type, 'UNKNOWN')", document_version_ids, parser_versions),
    }


def key_counts(conn: Any, key_sql: str, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, int]:
    rows = fetch_all(conn, f"""
        SELECT ({key_sql})::text AS key, count(*)::int AS count
          FROM search_unit su
         WHERE su.document_version_id = ANY(%s)
           AND upper(coalesce(su.source_file_type, '')) = 'PDF'
           AND su.parser_version = ANY(%s)
         GROUP BY 1
         ORDER BY 1
    """, (document_version_ids, parser_versions))
    return {str(row.get("key") or "UNKNOWN"): int(row.get("count") or 0) for row in rows}


def query_document_scope_details(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> list[dict[str, Any]]:
    rows = fetch_all(conn, f"""
        WITH scoped AS (
          SELECT document_version_id,
                 count(*)::int AS scoped_rows,
                 count(*) FILTER (WHERE NOT ({POLICY_EXCLUDED_SQL}))::int AS indexable_rows,
                 count(*) FILTER (WHERE {POLICY_EXCLUDED_SQL})::int AS policy_excluded_rows
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
           GROUP BY document_version_id
        )
        SELECT document_version_id, scoped_rows, indexable_rows, policy_excluded_rows
          FROM scoped
         ORDER BY document_version_id
    """, (document_version_ids, parser_versions))
    return rows_to_plain(rows)


def query_sample_blockers(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> list[dict[str, Any]]:
    rows = fetch_all(conn, f"""
        WITH scoped AS (
          SELECT su.*,
                 lower(coalesce(su.chunk_type, su.location_json->>'block_type', su.unit_type, '')) AS chunk_type_norm,
                 lower(coalesce(su.location_json->>'block_type', su.chunk_type, su.unit_type, '')) AS block_type_norm,
                 ({POLICY_EXCLUDED_SQL}) AS policy_excluded
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        )
        SELECT id,
               document_version_id,
               source_file_name,
               unit_type,
               chunk_type,
               location_json->>'page_no' AS page_no,
               location_json->>'physical_page_index' AS physical_page_index,
               location_json->>'bbox' AS bbox,
               location_json->>'ocr_used' AS ocr_used,
               location_json->>'ocr_confidence' AS ocr_confidence,
               citation_text,
               embedding_status,
               embedding_status_detail
          FROM scoped
         WHERE NOT policy_excluded
           AND (
                location_json IS NULL
             OR location_json->>'physical_page_index' IS NULL
             OR location_json->>'page_no' IS NULL
             OR location_json->>'block_type' IS NULL
             OR location_json->>'ocr_used' IS NULL
             OR (
                  chunk_type_norm IN ('paragraph', 'text', 'ocr_text', 'ocr_line_group', 'table')
                  AND location_json->>'bbox' IS NULL
                )
             OR (
                  coalesce((location_json->>'ocr_used')::boolean, false)
                  AND location_json->>'ocr_confidence' IS NULL
                )
             OR citation_text IS NULL
             OR btrim(citation_text) = ''
           )
         ORDER BY document_version_id, id
         LIMIT 25
    """, (document_version_ids, parser_versions))
    return rows_to_plain(rows)


def query_sample_warnings(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> list[dict[str, Any]]:
    rows = fetch_all(conn, f"""
        SELECT id,
               document_version_id,
               source_file_name,
               unit_type,
               chunk_type,
               location_json->>'page_no' AS page_no,
               location_json->>'physical_page_index' AS physical_page_index,
               location_json->>'bbox' AS bbox,
               location_json->>'ocr_used' AS ocr_used,
               location_json->>'ocr_confidence' AS ocr_confidence,
               embedding_status,
               embedding_status_detail
          FROM search_unit su
         WHERE su.document_version_id = ANY(%s)
           AND upper(coalesce(su.source_file_type, '')) = 'PDF'
           AND su.parser_version = ANY(%s)
           AND ({POLICY_EXCLUDED_SQL})
         ORDER BY document_version_id, id
         LIMIT 25
    """, (document_version_ids, parser_versions))
    return rows_to_plain(rows)


def scope_document_version_ids(scope_report: Mapping[str, Any]) -> list[str]:
    return sorted(str(item) for item in ((scope_report.get("scope") or {}).get("document_version_ids") or []) if str(item))


def scope_parser_versions(scope_report: Mapping[str, Any]) -> list[str]:
    return sorted(str(item) for item in ((scope_report.get("scope") or {}).get("parser_versions") or []) if str(item))


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope-report", default=str(DEFAULT_SCOPE_REPORT))
    parser.add_argument("--output", "--report", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--expected-index-version", default=PDF_INDEX_VERSION)
    parser.add_argument("--db-dsn", default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
