"""Report the Track C PDF-only candidate scope.

This is a read-only C1 report. It uses the C0 snapshot and PDF gold rows to
define an explicit PDF document_version scope, then inspects SearchUnit and PDF
page metadata completeness for that scope. It does not run retrieval, claim
SearchUnits, build vectors, update artifacts, or create promotion evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/pdf_candidate_scope_report.json")
DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_v0.csv")
DEFAULT_C0_SNAPSHOT = Path("eval/reports/rag-ingestion/rag_pdf_current_diagnostic_snapshot.json")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
PDF_INDEX_VERSION = "rag-ingestion-v2-pdf-candidate-v1"
PDF_ARTIFACT_DIR = "eval/indexes/rag-data-pdf-candidate-v1"
DEFAULT_PARSER_VERSIONS = ("pdf-extract-v1", "pdf-extract-v2")
DEFAULT_EXPECTED_LOCATION_TYPE = "pdf"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_dsn = args.db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN
    blockers: list[str] = []
    warnings: list[str] = []

    try:
        c0_snapshot = read_json(Path(args.c0_snapshot), blockers, "c0_snapshot")
        gold_scope = read_pdf_gold_scope(Path(args.gold), args.expected_location_type, warnings)
        with connect(db_dsn) as conn:
            db_snapshot = query_db_snapshot(
                conn,
                document_version_ids=scope_document_version_ids(c0_snapshot, gold_scope),
                parser_versions=list(args.parser_version),
                expected_location_type=args.expected_location_type,
            )
    except Exception as exc:
        db_snapshot = {}
        blockers.append(f"C1 scope inspection failed: {type(exc).__name__}: {exc}")

    payload = build_payload(
        c0_snapshot=c0_snapshot if "c0_snapshot" in locals() else {},
        c0_snapshot_path=Path(args.c0_snapshot),
        gold_scope=gold_scope if "gold_scope" in locals() else {},
        gold_path=Path(args.gold),
        db_snapshot=db_snapshot,
        db_dsn=db_dsn,
        parser_versions=list(args.parser_version),
        expected_location_type=args.expected_location_type,
        blockers=blockers,
        warnings=warnings,
    )
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def build_payload(
    *,
    c0_snapshot: Mapping[str, Any],
    c0_snapshot_path: Path,
    gold_scope: Mapping[str, Any],
    gold_path: Path,
    db_snapshot: Mapping[str, Any],
    db_dsn: str,
    parser_versions: list[str],
    expected_location_type: str,
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    blocker_list = list(blockers)
    warning_list = list(warnings)

    if c0_snapshot.get("status") != "PASS":
        blocker_list.append(f"C0 snapshot must be PASS before C1; got {c0_snapshot.get('status')}")
    if c0_snapshot.get("promotion_evidence") is not False:
        blocker_list.append("C0 snapshot must keep promotion_evidence=false")
    if c0_snapshot.get("evidence_role") != "diagnostic":
        blocker_list.append("C0 snapshot must keep evidence_role=diagnostic")

    if not gold_scope.get("exists", True):
        blocker_list.append(f"gold query file missing: {gold_scope.get('path')}")
    if int(gold_scope.get("pdf_query_count") or 0) == 0:
        blocker_list.append("PDF gold query count must be greater than 0")
    if int(gold_scope.get("missing_document_version_id_count") or 0) != 0:
        blocker_list.append("PDF gold rows must all have expected_document_version_id")
    if int(gold_scope.get("bucket_location_mismatch_count") or 0) != 0:
        blocker_list.append("PDF gold rows must have matching pdf bucket and expected_location_type")

    document_version_ids = sorted(set(gold_scope.get("document_version_ids") or []))
    c0_document_version_ids = sorted(set(((c0_snapshot.get("scope") or {}).get("document_version_ids") or [])))
    if document_version_ids and c0_document_version_ids and document_version_ids != c0_document_version_ids:
        blocker_list.append(
            f"C1 gold document scope differs from C0 snapshot: c0={c0_document_version_ids}, gold={document_version_ids}"
        )

    summary = dict(db_snapshot.get("summary") or {})
    page_metadata = dict(db_snapshot.get("page_metadata") or {})
    pdf_artifact = dict(db_snapshot.get("pdf_candidate_artifact") or {})
    document_scope_details = list(db_snapshot.get("document_scope_details") or [])
    missing_scoped_docvs = [
        row.get("document_version_id")
        for row in document_scope_details
        if int(row.get("scoped_search_unit_count") or 0) == 0
    ]
    missing_document_versions = [
        row.get("document_version_id")
        for row in document_scope_details
        if row.get("document_version_exists") is False
    ]
    not_ready_sources = [
        row.get("document_version_id")
        for row in document_scope_details
        if row.get("source_file_status") and row.get("source_file_status") != "READY"
    ]
    for key in (
        "missing_location_json_count",
        "missing_citation_text_count",
        "missing_embedding_text_count",
        "missing_page_metadata_count",
        "path_mixing_count",
        "unsupported_parser_version_count",
    ):
        if int(summary.get(key) or page_metadata.get(key) or 0) != 0:
            blocker_list.append(f"{key} must be 0")
    if int(summary.get("scoped_search_unit_count") or 0) == 0:
        blocker_list.append("scoped_search_unit_count must be greater than 0")
    if int(summary.get("candidate_rows") or 0) == 0:
        blocker_list.append("candidate_rows must be greater than 0")
    if missing_scoped_docvs:
        blocker_list.append(f"PDF gold document_version_ids missing scoped SearchUnits: {missing_scoped_docvs}")
    if missing_document_versions:
        blocker_list.append(f"PDF gold document_version rows missing: {missing_document_versions}")
    if not_ready_sources:
        blocker_list.append(f"PDF source files are not READY: {not_ready_sources}")
    if pdf_artifact.get("exists") is True:
        blocker_list.append("PDF candidate artifact dir must not exist during C1")

    ocr_confidence_missing = int((db_snapshot.get("ocr_summary") or {}).get("ocr_confidence_missing_count") or 0)
    if ocr_confidence_missing:
        warning_list.append(
            f"ocr_confidence_missing_count={ocr_confidence_missing}; C2/C3 OCR trust readiness must classify this"
        )
    missing_required_bbox = int(summary.get("missing_required_bbox_count") or 0)
    if missing_required_bbox:
        warning_list.append(
            f"missing_required_bbox_count={missing_required_bbox}; C2/C3 location contract readiness must classify this"
        )
    ocr_bbox_missing = int((db_snapshot.get("ocr_summary") or {}).get("ocr_bbox_missing_count") or 0)
    if ocr_bbox_missing:
        warning_list.append(
            f"ocr_bbox_missing_count={ocr_bbox_missing}; C2/C3 OCR location readiness must classify this"
        )
    skipped_rows = int((db_snapshot.get("embedding_status_counts") or {}).get("SKIPPED") or 0)
    if skipped_rows:
        warning_list.append(
            f"embedding_status_counts.SKIPPED={skipped_rows}; C2/C3 embedding eligibility must classify skipped rows"
        )

    status = "PASS"
    if blocker_list:
        status = "FAIL"
    elif warning_list:
        status = "PASS_WITH_WARNINGS"

    candidate_docvs = sorted({
        str(row.get("document_version_id"))
        for row in document_scope_details
        if row.get("document_version_id") and int(row.get("candidate_rows") or 0) > 0
    })
    candidate_source_file_ids = sorted({
        str(row.get("source_file_id"))
        for row in document_scope_details
        if row.get("source_file_id") and int(row.get("candidate_rows") or 0) > 0
    })

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C1",
        "report_role": "pdf_candidate_scope_report",
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
        "input_artifacts": [
            artifact_identity(c0_snapshot_path),
            artifact_identity(gold_path),
        ],
        "c0_snapshot": {
            "path": str(c0_snapshot_path),
            "status": c0_snapshot.get("status"),
            "sha256": file_sha256(c0_snapshot_path) if c0_snapshot_path.exists() else None,
            "promotion_evidence": c0_snapshot.get("promotion_evidence"),
            "evidence_role": c0_snapshot.get("evidence_role"),
        },
        "candidate_contract": {
            "index_version": PDF_INDEX_VERSION,
            "artifact_dir": PDF_ARTIFACT_DIR,
            "source_file_type": "PDF",
            "expected_location_type": expected_location_type,
            "parser_versions": parser_versions,
        },
        "gold_scope": dict(gold_scope),
        "scope": {
            "document_version_ids": candidate_docvs or document_version_ids,
            "source_file_ids": candidate_source_file_ids,
            "parser_versions": parser_versions,
            "expected_location_type": expected_location_type,
            "complete": not blocker_list,
        },
        "summary": summary,
        "page_metadata": page_metadata,
        "ocr_summary": dict(db_snapshot.get("ocr_summary") or {}),
        "parser_version_distribution": dict(db_snapshot.get("parser_version_distribution") or {}),
        "block_type_distribution": dict(db_snapshot.get("block_type_distribution") or {}),
        "chunk_type_distribution": dict(db_snapshot.get("chunk_type_distribution") or {}),
        "embedding_status_counts": dict(db_snapshot.get("embedding_status_counts") or {}),
        "source_file_status_counts": dict(db_snapshot.get("source_file_status_counts") or {}),
        "document_scope_details": document_scope_details,
        "sample_warnings": list(db_snapshot.get("sample_warnings") or []),
        "pdf_candidate_artifact": pdf_artifact,
        "indexing_cli_scope": {
            "sourceFileTypes": ["PDF"],
            "parserVersions": parser_versions,
            "documentVersionIds": candidate_docvs or document_version_ids,
            "sourceFileIds": candidate_source_file_ids,
            "expectedIndexVersion": PDF_INDEX_VERSION,
            "indexVersion": PDF_INDEX_VERSION,
            "allowUnscoped": False,
        },
        "blockers": dedupe(blocker_list),
        "warnings": dedupe(warning_list),
        "next_action": (
            "Run C2/C3 using this explicit C1 scope; keep structured warnings visible."
            if status in {"PASS", "PASS_WITH_WARNINGS"}
            else "Resolve C1 blockers before C2/C3."
        ),
        "notes": [
            "C1 is a PDF-only scope report. It does not prove vector metadata projection or indexing consistency.",
            "Document summary rows are allowed to lack bbox/page metadata; text/page/OCR/table rows are checked by page-bound metadata policy.",
            "OCR confidence/bbox gaps and skipped rows are recorded here and should be handled by C2/C3 readiness.",
        ],
    }


def query_db_snapshot(
    conn: Any,
    *,
    document_version_ids: list[str],
    parser_versions: list[str],
    expected_location_type: str,
) -> dict[str, Any]:
    summary = query_summary(conn, document_version_ids, parser_versions, expected_location_type)
    page_metadata = query_page_metadata(conn, document_version_ids, parser_versions)
    distributions = query_distributions(conn, document_version_ids, parser_versions)
    document_scope_details = query_document_scope_details(conn, document_version_ids, parser_versions)
    source_status_counts = Counter(
        str(row.get("source_file_status") or "UNKNOWN") for row in document_scope_details
    )
    return {
        "summary": {**summary, **{"missing_page_metadata_count": page_metadata.get("missing_page_metadata_count", 0)}},
        "page_metadata": page_metadata,
        "ocr_summary": query_ocr_summary(conn, document_version_ids, parser_versions),
        "parser_version_distribution": distributions["parser_version_distribution"],
        "block_type_distribution": distributions["block_type_distribution"],
        "chunk_type_distribution": distributions["chunk_type_distribution"],
        "embedding_status_counts": distributions["embedding_status_counts"],
        "source_file_status_counts": dict(sorted(source_status_counts.items())),
        "document_scope_details": document_scope_details,
        "sample_warnings": query_sample_warnings(conn, document_version_ids, parser_versions),
        "pdf_candidate_artifact": {
            "artifact_dir": PDF_ARTIFACT_DIR,
            "exists": Path(PDF_ARTIFACT_DIR).exists(),
        },
    }


def query_summary(
    conn: Any,
    document_version_ids: list[str],
    parser_versions: list[str],
    expected_location_type: str,
) -> dict[str, int]:
    row = fetch_one(conn, """
        WITH scoped AS (
          SELECT su.*,
                 lower(coalesce(su.location_json->>'block_type', su.chunk_type, su.unit_type, '')) AS block_type_norm
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        ),
        path_mixing AS (
          SELECT count(*)::int AS path_mixing_count
            FROM search_unit su
            LEFT JOIN document_version dv ON dv.id = su.document_version_id
           WHERE su.document_version_id = ANY(%s)
             AND (
                  upper(coalesce(su.source_file_type, '')) <> 'PDF'
               OR upper(coalesce(dv.source_file_type, '')) <> 'PDF'
               OR (su.location_json IS NOT NULL AND su.location_json->>'type' IS DISTINCT FROM %s)
             )
        ),
        unsupported AS (
          SELECT count(*)::int AS unsupported_parser_version_count
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND NOT (su.parser_version = ANY(%s))
        )
        SELECT
          (SELECT count(*)::int FROM scoped) AS scoped_search_unit_count,
          count(*) FILTER (
            WHERE s.location_json IS NOT NULL
              AND s.citation_text IS NOT NULL
              AND btrim(s.citation_text) <> ''
              AND s.embedding_text IS NOT NULL
              AND btrim(s.embedding_text) <> ''
          )::int AS candidate_rows,
          count(*) FILTER (WHERE s.location_json IS NULL)::int AS missing_location_json_count,
          count(*) FILTER (WHERE s.citation_text IS NULL OR btrim(s.citation_text) = '')::int AS missing_citation_text_count,
          count(*) FILTER (WHERE s.embedding_text IS NULL OR btrim(s.embedding_text) = '')::int AS missing_embedding_text_count,
          count(*) FILTER (
            WHERE s.block_type_norm <> 'document_summary'
              AND s.location_json IS NOT NULL
              AND s.location_json->>'physical_page_index' IS NULL
              AND s.location_json->>'page_no' IS NULL
          )::int AS missing_page_identifier_count,
          count(*) FILTER (
            WHERE s.block_type_norm IN ('paragraph', 'text', 'ocr_text', 'ocr_line_group', 'table')
              AND s.location_json IS NOT NULL
              AND s.location_json->>'bbox' IS NULL
          )::int AS missing_required_bbox_count,
          (SELECT path_mixing_count FROM path_mixing) AS path_mixing_count,
          (SELECT unsupported_parser_version_count FROM unsupported) AS unsupported_parser_version_count
        FROM scoped s
    """, (
        document_version_ids,
        parser_versions,
        document_version_ids,
        expected_location_type,
        document_version_ids,
        parser_versions,
    ))
    return {key: int(value or 0) for key, value in row.items()}


def query_page_metadata(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, int]:
    row = fetch_one(conn, """
        WITH scoped AS (
          SELECT su.*,
                 lower(coalesce(su.location_json->>'block_type', su.chunk_type, su.unit_type, '')) AS block_type_norm,
                 CASE
                   WHEN su.location_json->>'physical_page_index' ~ '^-?\\d+$'
                   THEN (su.location_json->>'physical_page_index')::int
                   ELSE NULL
                 END AS physical_page_index_int,
                 CASE
                   WHEN su.location_json->>'page_no' ~ '^-?\\d+$'
                   THEN (su.location_json->>'page_no')::int
                   ELSE NULL
                 END AS page_no_int
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        ),
        page_bound AS (
          SELECT *
            FROM scoped
           WHERE location_json IS NOT NULL
             AND block_type_norm <> 'document_summary'
             AND (physical_page_index_int IS NOT NULL OR page_no_int IS NOT NULL)
        )
        SELECT
          count(*)::int AS page_bound_search_unit_count,
          count(*) FILTER (WHERE ppm.id IS NULL)::int AS missing_page_metadata_count,
          count(DISTINCT (
            pb.document_version_id || ':' || coalesce(pb.physical_page_index_int::text, '') || ':' || coalesce(pb.page_no_int::text, '')
          ))::int AS distinct_page_reference_count,
          count(DISTINCT CASE WHEN ppm.id IS NULL THEN (
            pb.document_version_id || ':' || coalesce(pb.physical_page_index_int::text, '') || ':' || coalesce(pb.page_no_int::text, '')
          ) END)::int AS missing_distinct_page_reference_count,
          count(DISTINCT ppm.id)::int AS matched_page_metadata_count
          FROM page_bound pb
          LEFT JOIN pdf_page_metadata ppm
            ON ppm.document_version_id = pb.document_version_id
           AND (
                (pb.physical_page_index_int IS NOT NULL AND ppm.physical_page_index = pb.physical_page_index_int)
             OR (pb.physical_page_index_int IS NULL AND pb.page_no_int IS NOT NULL AND ppm.page_no = pb.page_no_int)
           )
    """, (document_version_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_ocr_summary(conn: Any, document_version_ids: list[str], parser_versions: list[str]) -> dict[str, int]:
    row = fetch_one(conn, """
        SELECT
          count(*) FILTER (WHERE coalesce((su.location_json->>'ocr_used')::boolean, false))::int AS ocr_row_count,
          count(*) FILTER (WHERE NOT coalesce((su.location_json->>'ocr_used')::boolean, false))::int AS native_pdf_row_count,
          count(*) FILTER (
            WHERE coalesce((su.location_json->>'ocr_used')::boolean, false)
              AND su.location_json->>'ocr_confidence' IS NULL
          )::int AS ocr_confidence_missing_count,
          count(*) FILTER (
            WHERE coalesce((su.location_json->>'ocr_used')::boolean, false)
              AND su.location_json->>'bbox' IS NULL
          )::int AS ocr_bbox_missing_count
          FROM search_unit su
         WHERE su.document_version_id = ANY(%s)
           AND upper(coalesce(su.source_file_type, '')) = 'PDF'
           AND su.parser_version = ANY(%s)
    """, (document_version_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_distributions(
    conn: Any,
    document_version_ids: list[str],
    parser_versions: list[str],
) -> dict[str, dict[str, int]]:
    return {
        "parser_version_distribution": fetch_key_counts(
            conn,
            "coalesce(su.parser_version, 'UNKNOWN')",
            document_version_ids,
            parser_versions,
        ),
        "block_type_distribution": fetch_key_counts(
            conn,
            "coalesce(su.location_json->>'block_type', su.chunk_type, su.unit_type, 'UNKNOWN')",
            document_version_ids,
            parser_versions,
        ),
        "chunk_type_distribution": fetch_key_counts(
            conn,
            "coalesce(su.chunk_type, su.unit_type, 'UNKNOWN')",
            document_version_ids,
            parser_versions,
        ),
        "embedding_status_counts": fetch_key_counts(
            conn,
            "coalesce(su.embedding_status, 'UNKNOWN')",
            document_version_ids,
            parser_versions,
        ),
    }


def query_document_scope_details(
    conn: Any,
    document_version_ids: list[str],
    parser_versions: list[str],
) -> list[dict[str, Any]]:
    rows = fetch_all(conn, """
        WITH expected(docv) AS (
          SELECT unnest(%s::text[])
        ),
        scoped AS (
          SELECT document_version_id,
                 min(source_file_id) AS source_file_id,
                 min(source_file_name) AS source_file_name,
                 count(*)::int AS scoped_search_unit_count,
                 count(*) FILTER (
                   WHERE location_json IS NOT NULL
                     AND citation_text IS NOT NULL
                     AND btrim(citation_text) <> ''
                     AND embedding_text IS NOT NULL
                     AND btrim(embedding_text) <> ''
                 )::int AS candidate_rows,
                 count(*) FILTER (WHERE embedding_status = 'PENDING')::int AS pending_rows,
                 count(*) FILTER (WHERE embedding_status = 'EMBEDDED')::int AS embedded_rows,
                 count(*) FILTER (WHERE coalesce((location_json->>'ocr_used')::boolean, false))::int AS ocr_rows,
                 coalesce(json_agg(DISTINCT parser_version) FILTER (WHERE parser_version IS NOT NULL), '[]'::json) AS parser_versions,
                 coalesce(json_agg(DISTINCT coalesce(location_json->>'block_type', chunk_type, unit_type, 'UNKNOWN')), '[]'::json) AS block_types
            FROM search_unit
           WHERE document_version_id = ANY(%s)
             AND upper(coalesce(source_file_type, '')) = 'PDF'
             AND parser_version = ANY(%s)
           GROUP BY document_version_id
        ),
        page_meta AS (
          SELECT document_version_id,
                 count(*)::int AS page_metadata_count,
                 count(*) FILTER (WHERE ocr_used)::int AS ocr_page_count
            FROM pdf_page_metadata
           WHERE document_version_id = ANY(%s)
           GROUP BY document_version_id
        )
        SELECT e.docv AS document_version_id,
               dv.id IS NOT NULL AS document_version_exists,
               dv.source_file_name AS document_version_source_file_name,
               dv.source_file_type AS document_version_source_file_type,
               dv.parse_status,
               sf.id AS source_file_id,
               sf.status AS source_file_status,
               sf.status_detail AS source_file_status_detail,
               coalesce(s.source_file_name, dv.source_file_name) AS source_file_name,
               coalesce(s.scoped_search_unit_count, 0)::int AS scoped_search_unit_count,
               coalesce(s.candidate_rows, 0)::int AS candidate_rows,
               coalesce(s.pending_rows, 0)::int AS pending_rows,
               coalesce(s.embedded_rows, 0)::int AS embedded_rows,
               coalesce(s.ocr_rows, 0)::int AS ocr_rows,
               coalesce(pm.page_metadata_count, 0)::int AS page_metadata_count,
               coalesce(pm.ocr_page_count, 0)::int AS ocr_page_count,
               coalesce(s.parser_versions, '[]'::json) AS observed_parser_versions,
               coalesce(s.block_types, '[]'::json) AS observed_block_types
          FROM expected e
          LEFT JOIN document_version dv ON dv.id = e.docv
          LEFT JOIN source_file sf ON sf.id = dv.source_file_id
          LEFT JOIN scoped s ON s.document_version_id = e.docv
          LEFT JOIN page_meta pm ON pm.document_version_id = e.docv
         ORDER BY e.docv
    """, (document_version_ids, document_version_ids, parser_versions, document_version_ids))
    return rows_to_plain(rows)


def query_sample_warnings(
    conn: Any,
    document_version_ids: list[str],
    parser_versions: list[str],
) -> list[dict[str, Any]]:
    rows = fetch_all(conn, """
        SELECT id,
               document_version_id,
               source_file_name,
               coalesce(location_json->>'block_type', chunk_type, unit_type) AS block_type,
               location_json->>'page_no' AS page_no,
               location_json->>'physical_page_index' AS physical_page_index,
               location_json->>'bbox' AS bbox,
               location_json->>'ocr_used' AS ocr_used,
               location_json->>'ocr_confidence' AS ocr_confidence,
               embedding_status,
               embedding_status_detail
          FROM search_unit
         WHERE document_version_id = ANY(%s)
           AND upper(coalesce(source_file_type, '')) = 'PDF'
           AND parser_version = ANY(%s)
           AND (
                (
                 coalesce((location_json->>'ocr_used')::boolean, false)
                 AND (
                      location_json->>'ocr_confidence' IS NULL
                   OR location_json->>'bbox' IS NULL
                 )
                )
             OR embedding_status = 'SKIPPED'
           )
         ORDER BY document_version_id, id
         LIMIT 25
    """, (document_version_ids, parser_versions))
    return rows_to_plain(rows)


def fetch_key_counts(
    conn: Any,
    key_sql: str,
    document_version_ids: list[str],
    parser_versions: list[str],
) -> dict[str, int]:
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


def read_pdf_gold_scope(path: Path, expected_location_type: str, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"gold query file not found: {path}")
        return {"path": str(path), "exists": False}
    with path.open("r", encoding="utf-8-sig", newline="") as fp:
        rows = list(csv.DictReader(fp))
    expected_type = expected_location_type.strip().lower()
    pdf_rows = [
        row for row in rows
        if (row.get("expected_location_type") or "").strip().lower() == expected_type
    ]
    bucket_location_mismatches = [
        row.get("query_id")
        for row in rows
        if (
            (row.get("bucket") or "").strip().lower().startswith("pdf")
            != ((row.get("expected_location_type") or "").strip().lower() == expected_type)
        )
    ]
    missing_docv = [
        row.get("query_id")
        for row in pdf_rows
        if not (row.get("expected_document_version_id") or "").strip()
    ]
    bucket_counts = Counter(row.get("bucket") or "unknown" for row in pdf_rows)
    return {
        "path": str(path),
        "exists": True,
        "gold_row_count": len(rows),
        "pdf_query_count": len(pdf_rows),
        "pdf_positive_count": sum(1 for row in pdf_rows if (row.get("label_status") or "").lower() == "bound"),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "bucket_location_mismatch_count": len(bucket_location_mismatches),
        "bucket_location_mismatch_query_ids": bucket_location_mismatches,
        "missing_document_version_id_count": len(missing_docv),
        "missing_document_version_query_ids": missing_docv,
        "document_version_ids": sorted({
            row.get("expected_document_version_id", "").strip()
            for row in pdf_rows
            if row.get("expected_document_version_id", "").strip()
        }),
        "expected_file_names": sorted({
            row.get("expected_file_name", "").strip()
            for row in pdf_rows
            if row.get("expected_file_name", "").strip()
        }),
    }


def scope_document_version_ids(c0_snapshot: Mapping[str, Any], gold_scope: Mapping[str, Any]) -> list[str]:
    c0_ids = set((c0_snapshot.get("scope") or {}).get("document_version_ids") or [])
    gold_ids = set(gold_scope.get("document_version_ids") or [])
    return sorted(c0_ids | gold_ids)


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


def rows_to_plain(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: plain(value) for key, value in row.items()} for row in rows]


def plain(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def artifact_identity(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() and path.is_file() else None,
    }


def read_json(path: Path, blockers: list[str], label: str) -> dict[str, Any]:
    if not path.exists():
        blockers.append(f"{label} missing: {path}")
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        blockers.append(f"{label} must be a JSON object: {path}")
        return {}
    return payload


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


def redact_dsn(dsn: str) -> str:
    parts = []
    for part in str(dsn or "").split():
        if part.lower().startswith("password="):
            parts.append("password=<redacted>")
        else:
            parts.append(part)
    return " ".join(parts)


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


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "--report", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--c0-snapshot", default=str(DEFAULT_C0_SNAPSHOT))
    parser.add_argument("--db-dsn", default=None)
    parser.add_argument("--expected-location-type", default=DEFAULT_EXPECTED_LOCATION_TYPE)
    parser.add_argument("--parser-version", "--parser-versions", nargs="+", default=list(DEFAULT_PARSER_VERSIONS))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
