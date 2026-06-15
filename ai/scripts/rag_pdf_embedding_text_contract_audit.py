"""Audit Track C PDF embedding/search text contract readiness.

This is a read-only C3 report. It consumes the explicit C1 PDF scope and
checks SearchUnit text surfaces before PDF candidate indexing. It does not run
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


DEFAULT_SCOPE_REPORT = Path("reports/rag_eval/rag-ingestion/pdf_candidate_scope_report.json")
DEFAULT_OUTPUT = Path("reports/rag_eval/rag-ingestion/rag_pdf_embedding_text_contract_audit.json")

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
            )
    except Exception as exc:
        snapshot = {}
        blockers.append(f"C3 embedding text contract inspection failed: {type(exc).__name__}: {exc}")

    payload = build_payload(
        scope_report=scope_report,
        scope_report_path=scope_path,
        db_snapshot=snapshot,
        db_dsn=db_dsn,
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
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    blocker_list = list(blockers)
    warning_list = list(warnings)
    inherited_warnings = list(scope_report.get("warnings") or [])
    summary = dict(db_snapshot.get("summary") or {})
    ocr_contract = dict(db_snapshot.get("ocr_trust_contract") or {})
    bbox_contract = dict(db_snapshot.get("bbox_policy_contract") or {})
    table_contract = dict(db_snapshot.get("table_contract") or {})

    if scope_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blocker_list.append(f"C1 scope report must pass before C3; got {scope_report.get('status')}")
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

    blocker_counters = {
        "missing_embedding_text_count": int(summary.get("missing_embedding_text_count") or 0),
        "missing_bm25_text_count": int(summary.get("missing_bm25_text_count") or 0),
        "missing_display_text_count": int(summary.get("missing_display_text_count") or 0),
        "missing_citation_text_count": int(summary.get("missing_citation_text_count") or 0),
        "missing_source_file_surface_in_embedding_text_count": int(
            summary.get("missing_source_file_surface_in_embedding_text_count") or 0
        ),
        "missing_page_surface_in_embedding_text_count": int(
            summary.get("missing_page_surface_in_embedding_text_count") or 0
        ),
        "missing_citation_surface_in_embedding_text_count": int(
            summary.get("missing_citation_surface_in_embedding_text_count") or 0
        ),
        "missing_block_type_surface_in_embedding_text_count": int(
            summary.get("missing_block_type_surface_in_embedding_text_count") or 0
        ),
        "missing_section_surface_for_sectioned_rows": int(
            summary.get("missing_section_surface_for_sectioned_rows") or 0
        ),
        "missing_table_surface_for_table_rows": int(
            table_contract.get("missing_table_surface_for_table_rows") or 0
        ),
        "embedded_ocr_trust_marker_missing_count": int(
            ocr_contract.get("embedded_ocr_trust_marker_missing_count") or 0
        ),
        "debug_text_leakage_count": int(summary.get("debug_text_leakage_count") or 0),
        "warning_text_leakage_count": int(summary.get("warning_text_leakage_count") or 0),
        "hidden_or_internal_field_leakage_count": int(summary.get("hidden_or_internal_field_leakage_count") or 0),
        "raw_json_leakage_count": int(summary.get("raw_json_leakage_count") or 0),
        "citation_location_mismatch_count": int(summary.get("citation_location_mismatch_count") or 0),
        "required_bbox_missing_after_chunk_type_policy_count": int(
            bbox_contract.get("required_bbox_missing_after_chunk_type_policy_count") or 0
        ),
    }
    text_contract_blocker_count = sum(blocker_counters.values())
    if text_contract_blocker_count:
        blocker_list.append("text_contract_blocker_count must be 0")
    if int(summary.get("indexable_rows") or 0) == 0:
        blocker_list.append("indexable_rows must be greater than 0")

    skipped_searchable = int(summary.get("skipped_searchable_row_count") or 0)
    if skipped_searchable:
        warning_list.append(f"skipped_searchable_row_count={skipped_searchable}; C4 should not index skipped rows")
    policy_excluded_ocr_missing = int(ocr_contract.get("policy_excluded_ocr_confidence_missing_count") or 0)
    if policy_excluded_ocr_missing:
        warning_list.append(
            f"policy_excluded_ocr_confidence_missing_count={policy_excluded_ocr_missing}; excluded before C4 indexing"
        )
    page_bbox_missing = int(bbox_contract.get("page_or_document_bbox_missing_count") or 0)
    if page_bbox_missing:
        warning_list.append(
            f"page_or_document_bbox_missing_count={page_bbox_missing}; bbox is optional for page/document summary rows"
        )
    pdf_table_gold_count = int(
        (((scope_report.get("gold_scope") or {}).get("bucket_counts") or {}).get("pdf_table_lookup") or 0)
    )
    if pdf_table_gold_count and int(table_contract.get("table_like_search_unit_count") or 0) == 0:
        warning_list.append(
            "pdf_table_gold_without_table_blocks_count="
            f"{pdf_table_gold_count}; current parser stores table-like PDF evidence as paragraphs/pages"
        )

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
        "phase": "C3",
        "report_role": "rag_pdf_embedding_text_contract_audit",
        "source_file_type": "PDF",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "index_version": PDF_INDEX_VERSION,
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
            "text_contract_blocker_count": text_contract_blocker_count,
        },
        "blocker_counters": blocker_counters,
        "embedding_text_contract": dict(db_snapshot.get("embedding_text_contract") or {}),
        "citation_contract": dict(db_snapshot.get("citation_contract") or {}),
        "bm25_display_contract": dict(db_snapshot.get("bm25_display_contract") or {}),
        "ocr_trust_contract": ocr_contract,
        "bbox_policy_contract": bbox_contract,
        "table_contract": {
            **table_contract,
            "pdf_table_gold_count": pdf_table_gold_count,
        },
        "leakage_contract": dict(db_snapshot.get("leakage_contract") or {}),
        "distributions": dict(db_snapshot.get("distributions") or {}),
        "sample_blockers": list(db_snapshot.get("sample_blockers") or []),
        "sample_warnings": list(db_snapshot.get("sample_warnings") or []),
        "sample_passes": list(db_snapshot.get("sample_passes") or []),
        "blockers": dedupe(blocker_list),
        "warnings": dedupe([*inherited_warnings, *warning_list]),
        "next_action": (
            "Repair or rebuild PDF SearchUnit text surfaces before C4 indexing."
            if status == "FAIL"
            else "Use this C3 report with C2 before C4 indexing."
        ),
        "notes": [
            "C3 is diagnostic-only and does not prove ranking quality.",
            "The audit is intentionally strict about DB embedding_text surface because C4 indexing consumes SearchUnit claim text.",
            "Existing raw embedding_text is not treated as acceptable just because bm25_text or citation_text carries location context.",
        ],
    }


def query_snapshot(conn: Any, *, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, Any]:
    summary = query_summary(conn, document_version_ids, parser_versions)
    return {
        "summary": summary,
        "embedding_text_contract": query_embedding_contract(conn, document_version_ids, parser_versions),
        "citation_contract": query_citation_contract(conn, document_version_ids, parser_versions),
        "bm25_display_contract": query_bm25_display_contract(conn, document_version_ids, parser_versions),
        "ocr_trust_contract": query_ocr_contract(conn, document_version_ids, parser_versions),
        "bbox_policy_contract": query_bbox_contract(conn, document_version_ids, parser_versions),
        "table_contract": query_table_contract(conn, document_version_ids, parser_versions),
        "leakage_contract": query_leakage_contract(conn, document_version_ids, parser_versions),
        "distributions": query_distributions(conn, document_version_ids, parser_versions),
        "sample_blockers": query_sample_blockers(conn, document_version_ids, parser_versions),
        "sample_warnings": query_sample_warnings(conn, document_version_ids, parser_versions),
        "sample_passes": query_sample_passes(conn, document_version_ids, parser_versions),
    }


def query_summary(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, int]:
    row = fetch_one(conn, f"""
        WITH scoped AS (
          SELECT su.*,
                 lower(coalesce(su.chunk_type, su.location_json->>'block_type', su.unit_type, '')) AS chunk_type_norm,
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
            WHERE embedding_status = 'SKIPPED'
              AND (
                   btrim(coalesce(embedding_text, '')) <> ''
                OR btrim(coalesce(bm25_text, '')) <> ''
                OR btrim(coalesce(display_text, '')) <> ''
                OR btrim(coalesce(citation_text, '')) <> ''
              )
          )::int AS skipped_searchable_row_count,
          count(*) FILTER (WHERE NOT policy_excluded AND (embedding_text IS NULL OR btrim(embedding_text) = ''))::int AS missing_embedding_text_count,
          count(*) FILTER (WHERE NOT policy_excluded AND (bm25_text IS NULL OR btrim(bm25_text) = ''))::int AS missing_bm25_text_count,
          count(*) FILTER (WHERE NOT policy_excluded AND (display_text IS NULL OR btrim(display_text) = ''))::int AS missing_display_text_count,
          count(*) FILTER (WHERE NOT policy_excluded AND (citation_text IS NULL OR btrim(citation_text) = ''))::int AS missing_citation_text_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND position(coalesce(source_file_name, '') in coalesce(embedding_text, '')) = 0
          )::int AS missing_source_file_surface_in_embedding_text_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND location_json->>'page_no' IS NOT NULL
              AND position('Page:' in coalesce(embedding_text, '')) = 0
              AND position('page:' in lower(coalesce(embedding_text, ''))) = 0
              AND position('p.' || (location_json->>'page_no') in coalesce(embedding_text, '')) = 0
          )::int AS missing_page_surface_in_embedding_text_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND citation_text IS NOT NULL
              AND btrim(citation_text) <> ''
              AND position(citation_text in coalesce(embedding_text, '')) = 0
          )::int AS missing_citation_surface_in_embedding_text_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND coalesce(location_json->>'block_type', chunk_type, unit_type) IS NOT NULL
              AND position('Block:' in coalesce(embedding_text, '')) = 0
              AND position('block_type' in lower(coalesce(embedding_text, ''))) = 0
              AND position(coalesce(location_json->>'block_type', chunk_type, unit_type) in coalesce(embedding_text, '')) = 0
          )::int AS missing_block_type_surface_in_embedding_text_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND location_json ? 'section_path'
              AND position('Section:' in coalesce(embedding_text, '')) = 0
          )::int AS missing_section_surface_for_sectioned_rows,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND citation_text IS NOT NULL
              AND (
                   (location_json->>'page_no' IS NOT NULL AND position('p.' || (location_json->>'page_no') in citation_text) = 0)
                OR (location_json->>'bbox' IS NOT NULL AND position('bbox' in citation_text) = 0)
              )
          )::int AS citation_location_mismatch_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND concat_ws(E'\n', embedding_text, bm25_text, display_text, citation_text)
                  ~* '(stack trace|traceback|exception|debug)'
          )::int AS debug_text_leakage_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND concat_ws(E'\n', embedding_text, bm25_text, display_text, citation_text)
                  ~* '(OCR_EMPTY_TEXT|OCR_REQUIRED|PDF_TEXT_LAYER_EMPTY|embedding_status_detail)'
          )::int AS warning_text_leakage_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND concat_ws(E'\n', embedding_text, bm25_text, display_text, citation_text)
                  ~* '(embedding_claim_token|claim_token|parsed_artifact_id|source_file_id|document_version_id|location_json|metadata_json)'
          )::int AS hidden_or_internal_field_leakage_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND concat_ws(E'\n', embedding_text, bm25_text, display_text, citation_text) ~* '\\{{\\s*"'
          )::int AS raw_json_leakage_count
          FROM scoped
    """, (document_version_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_embedding_contract(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, int]:
    row = fetch_one(conn, f"""
        WITH scoped AS (
          SELECT su.*, ({POLICY_EXCLUDED_SQL}) AS policy_excluded
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        )
        SELECT
          count(*) FILTER (WHERE NOT policy_excluded)::int AS checked_rows,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND position(coalesce(source_file_name, '') in coalesce(embedding_text, '')) > 0
          )::int AS source_surface_present_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND (position('Page:' in coalesce(embedding_text, '')) > 0 OR position('p.' in coalesce(embedding_text, '')) > 0)
          )::int AS page_surface_present_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND citation_text IS NOT NULL
              AND position(citation_text in coalesce(embedding_text, '')) > 0
          )::int AS citation_surface_present_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND (position('Block:' in coalesce(embedding_text, '')) > 0 OR position('block_type' in lower(coalesce(embedding_text, ''))) > 0)
          )::int AS block_surface_present_count
          FROM scoped
    """, (document_version_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_citation_contract(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, int]:
    row = fetch_one(conn, f"""
        WITH scoped AS (
          SELECT su.*, ({POLICY_EXCLUDED_SQL}) AS policy_excluded
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        )
        SELECT
          count(*) FILTER (WHERE NOT policy_excluded)::int AS checked_rows,
          count(*) FILTER (WHERE NOT policy_excluded AND position(source_file_name in coalesce(citation_text, '')) > 0)::int AS source_surface_present_count,
          count(*) FILTER (WHERE NOT policy_excluded AND location_json->>'page_no' IS NOT NULL AND position('p.' || (location_json->>'page_no') in coalesce(citation_text, '')) > 0)::int AS page_surface_present_count,
          count(*) FILTER (WHERE NOT policy_excluded AND location_json->>'bbox' IS NOT NULL AND position('bbox' in coalesce(citation_text, '')) > 0)::int AS bbox_surface_present_count
          FROM scoped
    """, (document_version_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_bm25_display_contract(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, int]:
    row = fetch_one(conn, f"""
        WITH scoped AS (
          SELECT su.*, ({POLICY_EXCLUDED_SQL}) AS policy_excluded
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        )
        SELECT
          count(*) FILTER (WHERE NOT policy_excluded)::int AS checked_rows,
          count(*) FILTER (WHERE NOT policy_excluded AND position(source_file_name in coalesce(bm25_text, '')) > 0)::int AS bm25_source_surface_present_count,
          count(*) FILTER (WHERE NOT policy_excluded AND citation_text IS NOT NULL AND position(citation_text in coalesce(bm25_text, '')) > 0)::int AS bm25_citation_surface_present_count,
          count(*) FILTER (WHERE NOT policy_excluded AND btrim(coalesce(display_text, '')) <> '')::int AS display_text_present_count
          FROM scoped
    """, (document_version_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_ocr_contract(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, int]:
    row = fetch_one(conn, f"""
        WITH scoped AS (
          SELECT su.*, ({POLICY_EXCLUDED_SQL}) AS policy_excluded
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        )
        SELECT
          count(*) FILTER (WHERE coalesce((location_json->>'ocr_used')::boolean, false))::int AS ocr_row_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND coalesce((location_json->>'ocr_used')::boolean, false)
          )::int AS embedded_ocr_row_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND coalesce((location_json->>'ocr_used')::boolean, false)
              AND position('lower_trust_ocr' in coalesce(embedding_text, '')) = 0
              AND position('OCR confidence' in coalesce(embedding_text, '')) = 0
          )::int AS embedded_ocr_trust_marker_missing_count,
          count(*) FILTER (
            WHERE policy_excluded
              AND coalesce((location_json->>'ocr_used')::boolean, false)
              AND location_json->>'ocr_confidence' IS NULL
          )::int AS policy_excluded_ocr_confidence_missing_count
          FROM scoped
    """, (document_version_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_bbox_contract(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, int]:
    row = fetch_one(conn, f"""
        WITH scoped AS (
          SELECT su.*,
                 lower(coalesce(su.chunk_type, su.location_json->>'block_type', su.unit_type, '')) AS chunk_type_norm,
                 ({POLICY_EXCLUDED_SQL}) AS policy_excluded
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        )
        SELECT
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND chunk_type_norm IN ('paragraph', 'text', 'ocr_text', 'ocr_line_group', 'table')
              AND location_json->>'bbox' IS NULL
          )::int AS required_bbox_missing_after_chunk_type_policy_count,
          count(*) FILTER (
            WHERE policy_excluded
              AND location_json->>'bbox' IS NULL
          )::int AS page_or_document_bbox_missing_count
          FROM scoped
    """, (document_version_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_table_contract(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, int]:
    row = fetch_one(conn, f"""
        WITH scoped AS (
          SELECT su.*, ({POLICY_EXCLUDED_SQL}) AS policy_excluded
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        )
        SELECT
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND (
                   lower(coalesce(chunk_type, '')) LIKE '%%table%%'
                OR lower(coalesce(location_json->>'block_type', '')) LIKE '%%table%%'
                OR lower(coalesce(unit_key, '')) LIKE '%%table%%'
              )
          )::int AS table_like_search_unit_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND (
                   lower(coalesce(chunk_type, '')) LIKE '%%table%%'
                OR lower(coalesce(location_json->>'block_type', '')) LIKE '%%table%%'
                OR lower(coalesce(unit_key, '')) LIKE '%%table%%'
              )
              AND position('Table:' in coalesce(embedding_text, '')) = 0
          )::int AS missing_table_surface_for_table_rows
          FROM scoped
    """, (document_version_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_leakage_contract(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, int]:
    return {
        key: int(value or 0)
        for key, value in query_summary(conn, document_version_ids, parser_versions).items()
        if key.endswith("_leakage_count")
    }


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


def query_sample_blockers(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> list[dict[str, Any]]:
    rows = fetch_all(conn, f"""
        SELECT id,
               document_version_id,
               source_file_name,
               chunk_type,
               location_json->>'page_no' AS page_no,
               citation_text,
               left(embedding_text, 240) AS embedding_text_preview,
               left(bm25_text, 160) AS bm25_text_preview,
               embedding_status,
               embedding_status_detail
          FROM search_unit su
         WHERE su.document_version_id = ANY(%s)
           AND upper(coalesce(su.source_file_type, '')) = 'PDF'
           AND su.parser_version = ANY(%s)
           AND NOT ({POLICY_EXCLUDED_SQL})
           AND (
                position(coalesce(source_file_name, '') in coalesce(embedding_text, '')) = 0
             OR (
                  location_json->>'page_no' IS NOT NULL
                  AND position('Page:' in coalesce(embedding_text, '')) = 0
                  AND position('p.' || (location_json->>'page_no') in coalesce(embedding_text, '')) = 0
                )
             OR (
                  citation_text IS NOT NULL
                  AND position(citation_text in coalesce(embedding_text, '')) = 0
                )
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
               chunk_type,
               location_json->>'page_no' AS page_no,
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


def query_sample_passes(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> list[dict[str, Any]]:
    rows = fetch_all(conn, f"""
        SELECT id,
               document_version_id,
               source_file_name,
               chunk_type,
               location_json->>'page_no' AS page_no,
               left(embedding_text, 180) AS embedding_text_preview
          FROM search_unit su
         WHERE su.document_version_id = ANY(%s)
           AND upper(coalesce(su.source_file_type, '')) = 'PDF'
           AND su.parser_version = ANY(%s)
           AND NOT ({POLICY_EXCLUDED_SQL})
           AND position(coalesce(source_file_name, '') in coalesce(embedding_text, '')) > 0
         ORDER BY document_version_id, id
         LIMIT 10
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
    parser.add_argument("--db-dsn", default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
