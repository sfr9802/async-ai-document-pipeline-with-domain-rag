"""Verify Track C PDF-only candidate embedding consistency.

This C4 report is diagnostic-only. It consumes the C1 explicit PDF scope plus
C2/C3/repair reports, then checks the PDF candidate namespace against
SearchUnit state, embedding_record rows, ragmeta chunks, and artifact
side-effect guardrails. It does not run retrieval or promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER = SCRIPT_DIR.parents[0]
ROOT = AI_WORKER.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pdf_candidate_scope_report import (  # noqa: E402
    DEFAULT_DB_DSN,
    PDF_INDEX_VERSION,
    connect,
    dedupe,
    fetch_all,
    fetch_one,
    print_report,
    redact_dsn,
    rows_to_plain,
    utc_run_id,
    utc_timestamp,
    write_json,
)


DEFAULT_C0_SNAPSHOT = Path("eval/reports/rag-ingestion/rag_pdf_current_diagnostic_snapshot.json")
DEFAULT_SCOPE_REPORT = Path("eval/reports/rag-ingestion/pdf_candidate_scope_report.json")
DEFAULT_C2_REPORT = Path("eval/reports/rag-ingestion/pdf_vector_metadata_projection_readiness.json")
DEFAULT_C3_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_embedding_text_contract_audit.json")
DEFAULT_REPAIR_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_search_unit_surface_repair_report.json")
DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/pdf_candidate_embedding_consistency_report.json")
DEFAULT_ARTIFACT_DIR = Path("eval/indexes/rag-data-pdf-candidate-v1")
DEFAULT_BASELINE_ARTIFACT_DIR = Path("eval/indexes/rag-data-canary")
DEFAULT_XLSX_CANDIDATE_ARTIFACT_DIR = Path("eval/indexes/rag-data-xlsx-candidate-v1")
ARTIFACT_FILES = ("faiss.index", "build.json", "ingest_manifest.json")
PDF_PARSER_VERSIONS = ("pdf-extract-v1", "pdf-extract-v2")

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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_dsn = args.db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN
    blockers: list[str] = []
    warnings: list[str] = []

    c0_path = resolve_existing_path(Path(args.c0_snapshot))
    c1_path = resolve_existing_path(Path(args.scope_report))
    c2_path = resolve_existing_path(Path(args.c2_report))
    c3_path = resolve_existing_path(Path(args.c3_report))
    repair_path = resolve_existing_path(Path(args.repair_report))
    artifact_dir = resolve_path(Path(args.artifact_dir))
    baseline_artifact_dir = resolve_path(Path(args.baseline_artifact_dir))
    xlsx_artifact_dir = resolve_path(Path(args.xlsx_candidate_artifact_dir))

    c0_snapshot = read_json(c0_path, blockers, "c0_snapshot")
    c1_report = read_json(c1_path, blockers, "c1_scope_report")
    c2_report = read_json(c2_path, blockers, "c2_report")
    c3_report = read_json(c3_path, blockers, "c3_report")
    repair_report = read_json(repair_path, blockers, "repair_report")

    snapshot: dict[str, Any] = {}
    try:
        document_version_ids = scope_document_version_ids(c1_report)
        source_file_ids = scope_source_file_ids(c1_report)
        parser_versions = scope_parser_versions(c1_report)
        if not blockers:
            with connect(db_dsn) as conn:
                snapshot = query_snapshot(
                    conn,
                    document_version_ids=document_version_ids,
                    source_file_ids=source_file_ids,
                    parser_versions=parser_versions,
                    expected_index_version=args.expected_index_version,
                )
    except Exception as exc:
        blockers.append(f"C4 consistency inspection failed: {type(exc).__name__}: {exc}")

    payload = build_payload(
        c0_snapshot=c0_snapshot,
        c0_path=c0_path,
        c1_report=c1_report,
        c1_path=c1_path,
        c2_report=c2_report,
        c2_path=c2_path,
        c3_report=c3_report,
        c3_path=c3_path,
        repair_report=repair_report,
        repair_path=repair_path,
        db_snapshot=snapshot,
        db_dsn=db_dsn,
        expected_index_version=args.expected_index_version,
        artifact_dir=artifact_dir,
        baseline_artifact_dir=baseline_artifact_dir,
        xlsx_artifact_dir=xlsx_artifact_dir,
        blockers=blockers,
        warnings=warnings,
    )
    write_json(resolve_output_path(Path(args.output)), payload)
    print_report(payload)
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def build_payload(
    *,
    c0_snapshot: Mapping[str, Any],
    c0_path: Path,
    c1_report: Mapping[str, Any],
    c1_path: Path,
    c2_report: Mapping[str, Any],
    c2_path: Path,
    c3_report: Mapping[str, Any],
    c3_path: Path,
    repair_report: Mapping[str, Any],
    repair_path: Path,
    db_snapshot: Mapping[str, Any],
    db_dsn: str,
    expected_index_version: str,
    artifact_dir: Path,
    baseline_artifact_dir: Path,
    xlsx_artifact_dir: Path,
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    blocker_list = list(blockers)
    warning_list = list(warnings)

    validate_input_reports(
        c0_snapshot=c0_snapshot,
        c1_report=c1_report,
        c2_report=c2_report,
        c3_report=c3_report,
        repair_report=repair_report,
        expected_index_version=expected_index_version,
        blockers=blocker_list,
    )

    document_version_ids = scope_document_version_ids(c1_report)
    source_file_ids = scope_source_file_ids(c1_report)
    parser_versions = scope_parser_versions(c1_report)
    c2_summary = dict(c2_report.get("summary") or {})
    c3_summary = dict(c3_report.get("summary") or {})
    scoped_summary = dict(db_snapshot.get("scoped_summary") or {})
    namespace_summary = dict(db_snapshot.get("namespace_summary") or {})
    metadata_counters = dict(db_snapshot.get("metadata_projection_counters") or {})
    text_counters = dict(db_snapshot.get("embedding_text_contract_counters") or {})

    carry_forward = carry_forward_warnings(c2_report, c3_report)
    warning_list.extend(carry_forward)

    baseline_check = artifact_change_check(
        c0_snapshot.get("immutable_baseline") if isinstance(c0_snapshot, Mapping) else {},
        baseline_artifact_dir,
        changed_key="immutable_baseline_changed",
    )
    xlsx_check = artifact_change_check(
        c0_snapshot.get("xlsx_candidate_artifact") if isinstance(c0_snapshot, Mapping) else {},
        xlsx_artifact_dir,
        changed_key="xlsx_candidate_artifact_changed",
    )
    artifact_build = read_artifact_build(artifact_dir)

    expected_scoped = int(c2_summary.get("scoped_rows") or 0)
    expected_indexable = int(c2_summary.get("indexable_rows") or 0)
    expected_policy_excluded = int(c2_summary.get("policy_excluded_rows") or 0)
    scoped_count = int(scoped_summary.get("scoped_search_unit_count") or 0)
    indexable_count = int(scoped_summary.get("indexable_search_unit_count") or 0)
    policy_excluded_count = int(scoped_summary.get("policy_excluded_search_unit_count") or 0)
    candidate_chunk_count = int(namespace_summary.get("candidate_namespace_chunk_count") or 0)

    if expected_scoped and scoped_count != expected_scoped:
        blocker_list.append(f"scoped_search_unit_count mismatch: expected {expected_scoped}, got {scoped_count}")
    if expected_indexable and indexable_count != expected_indexable:
        blocker_list.append(
            f"indexable_search_unit_count mismatch: expected {expected_indexable}, got {indexable_count}"
        )
    if expected_policy_excluded and policy_excluded_count != expected_policy_excluded:
        blocker_list.append(
            "policy_excluded_search_unit_count mismatch: "
            f"expected {expected_policy_excluded}, got {policy_excluded_count}"
        )
    if c3_summary.get("indexable_rows") is not None and indexable_count != int(c3_summary.get("indexable_rows") or 0):
        blocker_list.append("C3 indexable_rows must match C4 scoped indexable rows")
    if candidate_chunk_count != indexable_count:
        blocker_list.append(
            f"candidate_namespace_chunk_count must equal indexable rows: chunks={candidate_chunk_count} "
            f"indexable={indexable_count}"
        )
    if not artifact_build.get("exists"):
        blocker_list.append("PDF candidate artifact_dir must exist after C4 indexing")
    if not artifact_build.get("build_json_sha256"):
        blocker_list.append("PDF candidate artifact build.json must exist after C4 indexing")
    if not artifact_build.get("manifest_sha256"):
        blocker_list.append("PDF candidate artifact ingest_manifest.json must exist after C4 indexing")
    if artifact_build.get("chunk_count") is not None and int(artifact_build.get("chunk_count") or 0) != candidate_chunk_count:
        blocker_list.append(
            "artifact build chunk_count must match candidate namespace chunk count: "
            f"build={artifact_build.get('chunk_count')} namespace={candidate_chunk_count}"
        )
    if artifact_build.get("index_version") and artifact_build.get("index_version") != expected_index_version:
        blocker_list.append(
            f"artifact build index_version mismatch: {artifact_build.get('index_version')} != {expected_index_version}"
        )

    required_zero_counters = {
        "not_embedded_count": scoped_summary.get("not_embedded_count"),
        "index_version_mismatch_count": scoped_summary.get("index_version_mismatch_count"),
        "embedding_record_missing_count": scoped_summary.get("embedding_record_missing_count"),
        "candidate_chunk_missing_count": scoped_summary.get("candidate_chunk_missing_count"),
        "vector_namespace_mismatch_count": scoped_summary.get("vector_namespace_mismatch_count"),
        "chunk_sha_mismatch_count": scoped_summary.get("chunk_sha_mismatch_count"),
        "unexpected_sourceFileId_count": namespace_summary.get("unexpected_sourceFileId_count"),
        "unexpected_documentVersionId_count": namespace_summary.get("unexpected_documentVersionId_count"),
        "non_pdf_row_count": namespace_summary.get("non_pdf_row_count"),
        "policy_excluded_leakage_count": namespace_summary.get("policy_excluded_leakage_count"),
        "missing_location_json_locationJson_count": metadata_counters.get("missing_location_json_locationJson_count"),
        "jackson_jsonnode_shape_location_count": metadata_counters.get("jackson_jsonnode_shape_location_count"),
        "unusable_location_count": metadata_counters.get("unusable_location_count"),
        "missing_physical_page_index_count": metadata_counters.get("missing_physical_page_index_count"),
        "missing_page_no_count": metadata_counters.get("missing_page_no_count"),
        "missing_bbox_count": metadata_counters.get("missing_bbox_count"),
        "missing_citation_text_count": metadata_counters.get("missing_citation_text_count"),
        "missing_embedding_text_count": text_counters.get("missing_embedding_text_count"),
        "missing_source_page_citation_block_surface_count": text_counters.get(
            "missing_source_page_citation_block_surface_count"
        ),
        "ocr_trust_marker_missing_count": text_counters.get("ocr_trust_marker_missing_count"),
    }
    for key, value in required_zero_counters.items():
        if int(value or 0) != 0:
            blocker_list.append(f"{key} must be 0")
    if baseline_check.get("immutable_baseline_changed") is True:
        blocker_list.append("immutable baseline changed")
    if xlsx_check.get("xlsx_candidate_artifact_changed") is True:
        blocker_list.append("XLSX candidate artifact changed")

    status = "PASS"
    if blocker_list:
        status = "FAIL"
    elif warning_list:
        status = "PASS_WITH_WARNINGS"

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C4",
        "report_role": "pdf_candidate_embedding_consistency",
        "source_file_type": "PDF",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "namespace": expected_index_version,
        "index_version": expected_index_version,
        "artifact_dir": display_path(artifact_dir),
        "allowUnscoped": False,
        "db_dsn": redact_dsn(db_dsn),
        "input_artifacts": [
            artifact_identity(c0_path),
            artifact_identity(c1_path),
            artifact_identity(c2_path),
            artifact_identity(c3_path),
            artifact_identity(repair_path),
        ],
        "c0_snapshot": report_ref(c0_path, c0_snapshot),
        "c1_scope_report": report_ref(c1_path, c1_report),
        "c2_report": report_ref(c2_path, c2_report),
        "c3_report": report_ref(c3_path, c3_report),
        "repair_report": report_ref(repair_path, repair_report),
        "scope": {
            "document_version_ids": document_version_ids,
            "source_file_ids": source_file_ids,
            "parser_versions": parser_versions,
            "source_file_type": "PDF",
            "allowUnscoped": False,
        },
        "scoped_search_unit_count": scoped_count,
        "indexable_search_unit_count": indexable_count,
        "policy_excluded_search_unit_count": policy_excluded_count,
        "candidate_namespace_chunk_count": candidate_chunk_count,
        "candidate_chunk_count_matches_indexable_rows": candidate_chunk_count == indexable_count,
        "unexpected_sourceFileId_count": int(namespace_summary.get("unexpected_sourceFileId_count") or 0),
        "unexpected_documentVersionId_count": int(namespace_summary.get("unexpected_documentVersionId_count") or 0),
        "non_pdf_row_count": int(namespace_summary.get("non_pdf_row_count") or 0),
        "policy_excluded_leakage_count": int(namespace_summary.get("policy_excluded_leakage_count") or 0),
        "missing_location_json_locationJson_count": int(
            metadata_counters.get("missing_location_json_locationJson_count") or 0
        ),
        "jackson_jsonnode_shape_location_count": int(
            metadata_counters.get("jackson_jsonnode_shape_location_count") or 0
        ),
        "unusable_location_count": int(metadata_counters.get("unusable_location_count") or 0),
        "missing_physical_page_index_count": int(metadata_counters.get("missing_physical_page_index_count") or 0),
        "missing_page_no_count": int(metadata_counters.get("missing_page_no_count") or 0),
        "missing_bbox_count": int(metadata_counters.get("missing_bbox_count") or 0),
        "missing_citation_text_count": int(metadata_counters.get("missing_citation_text_count") or 0),
        "missing_embedding_text_count": int(text_counters.get("missing_embedding_text_count") or 0),
        "missing_source_page_citation_block_surface_count": int(
            text_counters.get("missing_source_page_citation_block_surface_count") or 0
        ),
        "ocr_trust_marker_missing_count": int(text_counters.get("ocr_trust_marker_missing_count") or 0),
        "immutable_baseline_changed": bool(baseline_check.get("immutable_baseline_changed")),
        "xlsx_candidate_artifact_changed": bool(xlsx_check.get("xlsx_candidate_artifact_changed")),
        "retrieval_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "c5_ready": status in {"PASS", "PASS_WITH_WARNINGS"},
        "scoped_summary": scoped_summary,
        "namespace_summary": namespace_summary,
        "metadata_projection_consistency": metadata_counters,
        "embedding_text_contract_consistency": text_counters,
        "artifact_build": artifact_build,
        "immutable_baseline": baseline_check,
        "xlsx_candidate_artifact": xlsx_check,
        "warnings_carried_forward": dedupe(carry_forward),
        "sample_failures": list(db_snapshot.get("sample_failures") or []),
        "blockers": dedupe(blocker_list),
        "warnings": dedupe(warning_list),
        "next_action": (
            "Proceed to C5 PDF-only vector diagnostic."
            if status in {"PASS", "PASS_WITH_WARNINGS"}
            else "Keep C5/C6/C7 blocked until C4 consistency blockers are resolved."
        ),
        "notes": [
            "C4 validates PDF candidate indexing consistency only; it is not promotion evidence.",
            "PDF table gold policy is intentionally carried as a warning and is not a C4 blocker.",
            "Candidate namespace count is checked against the C1/C2/C3 indexable row contract.",
        ],
    }


def validate_input_reports(
    *,
    c0_snapshot: Mapping[str, Any],
    c1_report: Mapping[str, Any],
    c2_report: Mapping[str, Any],
    c3_report: Mapping[str, Any],
    repair_report: Mapping[str, Any],
    expected_index_version: str,
    blockers: list[str],
) -> None:
    if c0_snapshot.get("status") != "PASS":
        blockers.append(f"C0 snapshot must be PASS before C4; got {c0_snapshot.get('status')}")
    if c1_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C1 scope report must pass before C4; got {c1_report.get('status')}")
    if c2_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C2 report must pass before C4; got {c2_report.get('status')}")
    if c3_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C3 report must pass before C4; got {c3_report.get('status')}")
    if repair_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"repair report must pass before C4; got {repair_report.get('status')}")
    for label, report in (
        ("C0", c0_snapshot),
        ("C1", c1_report),
        ("C2", c2_report),
        ("C3", c3_report),
        ("repair", repair_report),
    ):
        if report and report.get("promotion_evidence") is not False:
            blockers.append(f"{label} report must keep promotion_evidence=false")
    for label, report in (("C0", c0_snapshot), ("C1", c1_report), ("C2", c2_report), ("C3", c3_report)):
        if report and report.get("evidence_role") != "diagnostic":
            blockers.append(f"{label} report must keep evidence_role=diagnostic")
    if repair_report and repair_report.get("evidence_role") != "repair_diagnostic":
        blockers.append("repair report must keep evidence_role=repair_diagnostic")
    if c1_report.get("allowUnscoped") is not False:
        blockers.append("C1 scope report must keep allowUnscoped=false")
    cli_scope = c1_report.get("indexing_cli_scope") if isinstance(c1_report.get("indexing_cli_scope"), dict) else {}
    if cli_scope.get("allowUnscoped") is not False:
        blockers.append("C1 indexing_cli_scope must keep allowUnscoped=false")
    if (cli_scope.get("expectedIndexVersion") or c1_report.get("index_version")) != expected_index_version:
        blockers.append("C1 expectedIndexVersion must match C4 namespace")
    if set(scope_parser_versions(c1_report)) != set(PDF_PARSER_VERSIONS):
        blockers.append("C1 parserVersions must match PDF parser scope")
    if not scope_document_version_ids(c1_report):
        blockers.append("C1 scope report must provide documentVersionIds")
    if not scope_source_file_ids(c1_report):
        blockers.append("C1 scope report must provide sourceFileIds")


def query_snapshot(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_ids: list[str],
    parser_versions: list[str],
    expected_index_version: str,
) -> dict[str, Any]:
    return {
        "scoped_summary": query_scoped_summary(
            conn,
            document_version_ids=document_version_ids,
            source_file_ids=source_file_ids,
            parser_versions=parser_versions,
            expected_index_version=expected_index_version,
        ),
        "namespace_summary": query_namespace_summary(
            conn,
            document_version_ids=document_version_ids,
            source_file_ids=source_file_ids,
            expected_index_version=expected_index_version,
        ),
        "metadata_projection_counters": query_metadata_projection_counters(
            conn,
            document_version_ids=document_version_ids,
            source_file_ids=source_file_ids,
            parser_versions=parser_versions,
            expected_index_version=expected_index_version,
        ),
        "embedding_text_contract_counters": query_embedding_text_counters(
            conn,
            document_version_ids=document_version_ids,
            source_file_ids=source_file_ids,
            parser_versions=parser_versions,
            expected_index_version=expected_index_version,
        ),
        "sample_failures": query_sample_failures(
            conn,
            document_version_ids=document_version_ids,
            source_file_ids=source_file_ids,
            parser_versions=parser_versions,
            expected_index_version=expected_index_version,
        ),
    }


def query_scoped_summary(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_ids: list[str],
    parser_versions: list[str],
    expected_index_version: str,
) -> dict[str, int]:
    row = fetch_one(conn, f"""
        WITH scoped AS (
          SELECT su.*,
                 ({POLICY_EXCLUDED_SQL}) AS policy_excluded
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND su.source_file_id::text = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        ),
        joined AS (
          SELECT s.*,
                 er.id AS embedding_record_id,
                 er.embedding_text_sha256,
                 er.vector_id,
                 c.chunk_id,
                 c.extra_json
            FROM scoped s
            LEFT JOIN embedding_record er
              ON er.search_unit_id = s.id
             AND er.index_version = %s
            LEFT JOIN ragmeta.chunks c
              ON c.chunk_id = s.index_id
             AND c.index_version = %s
        )
        SELECT
          count(*)::int AS scoped_search_unit_count,
          count(*) FILTER (WHERE NOT policy_excluded)::int AS indexable_search_unit_count,
          count(*) FILTER (WHERE policy_excluded)::int AS policy_excluded_search_unit_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND embedding_status IS DISTINCT FROM 'EMBEDDED'
          )::int AS not_embedded_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND index_version IS DISTINCT FROM %s
          )::int AS index_version_mismatch_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND embedding_record_id IS NULL
          )::int AS embedding_record_missing_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND chunk_id IS NULL
          )::int AS candidate_chunk_missing_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND (vector_id IS NULL OR vector_id NOT LIKE %s)
          )::int AS vector_namespace_mismatch_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND chunk_id IS NOT NULL
              AND embedding_record_id IS NOT NULL
              AND (
                   extra_json->>'embeddingTextSha256' IS NULL
                OR extra_json->>'embeddingTextSha256' IS DISTINCT FROM embedding_text_sha256
              )
          )::int AS chunk_sha_mismatch_count
          FROM joined
    """, (
        document_version_ids,
        source_file_ids,
        parser_versions,
        expected_index_version,
        expected_index_version,
        expected_index_version,
        f"{expected_index_version}:%",
    ))
    return {key: int(value or 0) for key, value in row.items()}


def query_namespace_summary(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_ids: list[str],
    expected_index_version: str,
) -> dict[str, int]:
    row = fetch_one(conn, f"""
        WITH namespace_chunks AS (
          SELECT c.chunk_id,
                 c.index_version,
                 su.id AS search_unit_id,
                 su.document_version_id,
                 su.source_file_id,
                 su.source_file_type,
                 su.unit_type,
                 su.chunk_type,
                 su.embedding_status,
                 su.embedding_status_detail,
                 ({POLICY_EXCLUDED_SQL}) AS policy_excluded
            FROM ragmeta.chunks c
            LEFT JOIN search_unit su
              ON su.index_id = c.chunk_id
           WHERE c.index_version = %s
        )
        SELECT
          count(*)::int AS candidate_namespace_chunk_count,
          count(*) FILTER (
            WHERE search_unit_id IS NULL
               OR source_file_id::text <> ALL(%s)
          )::int AS "unexpected_sourceFileId_count",
          count(*) FILTER (
            WHERE search_unit_id IS NULL
               OR document_version_id <> ALL(%s)
          )::int AS "unexpected_documentVersionId_count",
          count(*) FILTER (
            WHERE search_unit_id IS NULL
               OR upper(coalesce(source_file_type, '')) <> 'PDF'
          )::int AS non_pdf_row_count,
          count(*) FILTER (
            WHERE search_unit_id IS NOT NULL
              AND policy_excluded
          )::int AS policy_excluded_leakage_count
          FROM namespace_chunks
    """, (expected_index_version, source_file_ids, document_version_ids))
    return {key: int(value or 0) for key, value in row.items()}


def query_metadata_projection_counters(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_ids: list[str],
    parser_versions: list[str],
    expected_index_version: str,
) -> dict[str, int]:
    row = fetch_one(conn, f"""
        WITH joined AS (
          SELECT su.*,
                 ({POLICY_EXCLUDED_SQL}) AS policy_excluded,
                 lower(coalesce(su.chunk_type, su.location_json->>'block_type', su.unit_type, '')) AS chunk_type_norm,
                 c.extra_json,
                 coalesce(c.extra_json->'locationJson', c.extra_json->'location_json') AS chunk_location
            FROM search_unit su
            LEFT JOIN ragmeta.chunks c
              ON c.chunk_id = su.index_id
             AND c.index_version = %s
           WHERE su.document_version_id = ANY(%s)
             AND su.source_file_id::text = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        )
        SELECT
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND extra_json IS NOT NULL
              AND NOT (extra_json ? 'locationJson' OR extra_json ? 'location_json')
          )::int AS "missing_location_json_locationJson_count",
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND chunk_location IS NOT NULL
              AND chunk_location ? 'nodeType'
              AND NOT (chunk_location ? 'type')
          )::int AS jackson_jsonnode_shape_location_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND (chunk_location IS NULL OR NOT (chunk_location ? 'type'))
          )::int AS unusable_location_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND (chunk_location IS NULL OR NOT (chunk_location ? 'physical_page_index'))
          )::int AS missing_physical_page_index_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND (chunk_location IS NULL OR NOT (chunk_location ? 'page_no'))
          )::int AS missing_page_no_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND chunk_type_norm IN ('paragraph', 'text', 'ocr_text', 'ocr_line_group', 'table')
              AND (chunk_location IS NULL OR NOT (chunk_location ? 'bbox'))
          )::int AS missing_bbox_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND coalesce(extra_json->>'citationText', extra_json->>'citation_text', '') = ''
          )::int AS missing_citation_text_count
          FROM joined
    """, (expected_index_version, document_version_ids, source_file_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_embedding_text_counters(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_ids: list[str],
    parser_versions: list[str],
    expected_index_version: str,
) -> dict[str, int]:
    row = fetch_one(conn, f"""
        WITH scoped AS (
          SELECT su.*,
                 ({POLICY_EXCLUDED_SQL}) AS policy_excluded
            FROM search_unit su
            JOIN ragmeta.chunks c
              ON c.chunk_id = su.index_id
             AND c.index_version = %s
           WHERE su.document_version_id = ANY(%s)
             AND su.source_file_id::text = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        )
        SELECT
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND (embedding_text IS NULL OR btrim(embedding_text) = '')
          )::int AS missing_embedding_text_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND (
                   position(coalesce(source_file_name, '') in coalesce(embedding_text, '')) = 0
                OR (
                     location_json->>'page_no' IS NOT NULL
                     AND position('Page:' in coalesce(embedding_text, '')) = 0
                     AND position('page:' in lower(coalesce(embedding_text, ''))) = 0
                     AND position('p.' || (location_json->>'page_no') in coalesce(embedding_text, '')) = 0
                   )
                OR (
                     citation_text IS NOT NULL
                     AND btrim(citation_text) <> ''
                     AND position(citation_text in coalesce(embedding_text, '')) = 0
                   )
                OR (
                     coalesce(location_json->>'block_type', chunk_type, unit_type) IS NOT NULL
                     AND position('Block:' in coalesce(embedding_text, '')) = 0
                     AND position('block_type' in lower(coalesce(embedding_text, ''))) = 0
                     AND position(coalesce(location_json->>'block_type', chunk_type, unit_type) in coalesce(embedding_text, '')) = 0
                   )
              )
          )::int AS missing_source_page_citation_block_surface_count,
          count(*) FILTER (
            WHERE NOT policy_excluded
              AND coalesce((location_json->>'ocr_used')::boolean, false)
              AND position('lower_trust_ocr' in coalesce(embedding_text, '')) = 0
              AND position('OCR confidence' in coalesce(embedding_text, '')) = 0
              AND position('OCR: used' in coalesce(embedding_text, '')) = 0
          )::int AS ocr_trust_marker_missing_count
          FROM scoped
    """, (expected_index_version, document_version_ids, source_file_ids, parser_versions))
    return {key: int(value or 0) for key, value in row.items()}


def query_sample_failures(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_ids: list[str],
    parser_versions: list[str],
    expected_index_version: str,
) -> list[dict[str, Any]]:
    rows = fetch_all(conn, f"""
        WITH scoped AS (
          SELECT su.*,
                 ({POLICY_EXCLUDED_SQL}) AS policy_excluded
            FROM search_unit su
           WHERE su.document_version_id = ANY(%s)
             AND su.source_file_id::text = ANY(%s)
             AND upper(coalesce(su.source_file_type, '')) = 'PDF'
             AND su.parser_version = ANY(%s)
        ),
        joined AS (
          SELECT s.*,
                 er.id AS embedding_record_id,
                 er.vector_id,
                 c.chunk_id,
                 c.extra_json,
                 coalesce(c.extra_json->'locationJson', c.extra_json->'location_json') AS chunk_location
            FROM scoped s
            LEFT JOIN embedding_record er
              ON er.search_unit_id = s.id
             AND er.index_version = %s
            LEFT JOIN ragmeta.chunks c
              ON c.chunk_id = s.index_id
             AND c.index_version = %s
        )
        SELECT id,
               document_version_id,
               source_file_id,
               source_file_name,
               unit_type,
               chunk_type,
               embedding_status,
               index_version,
               index_id,
               embedding_record_id IS NULL AS embedding_record_missing,
               chunk_id IS NULL AS candidate_chunk_missing,
               vector_id,
               left(chunk_location::text, 240) AS chunk_location_preview,
               left(extra_json::text, 240) AS extra_json_preview
          FROM joined
         WHERE NOT policy_excluded
           AND (
                embedding_status IS DISTINCT FROM 'EMBEDDED'
             OR index_version IS DISTINCT FROM %s
             OR embedding_record_id IS NULL
             OR chunk_id IS NULL
             OR vector_id IS NULL
             OR vector_id NOT LIKE %s
             OR chunk_location IS NULL
             OR NOT (chunk_location ? 'type')
           )
         ORDER BY document_version_id, id
         LIMIT 25
    """, (
        document_version_ids,
        source_file_ids,
        parser_versions,
        expected_index_version,
        expected_index_version,
        expected_index_version,
        f"{expected_index_version}:%",
    ))
    return rows_to_plain(rows)


def carry_forward_warnings(c2_report: Mapping[str, Any], c3_report: Mapping[str, Any]) -> list[str]:
    c2_summary = dict(c2_report.get("summary") or {})
    c3_summary = dict(c3_report.get("summary") or {})
    c3_table = dict(c3_report.get("table_contract") or {})
    return [
        "OCR confidence missing rows are policy-excluded before C4: "
        f"{int(c2_summary.get('policy_excluded_ocr_confidence_missing_count') or 0)}",
        "document summaries are policy-excluded before C4: "
        f"{int(c2_summary.get('policy_excluded_document_summary_count') or 0)}",
        "skipped searchable rows remain visible for C4 exclusion: "
        f"{int(c3_summary.get('skipped_searchable_row_count') or 0)}",
        "current PDF table gold rows have no table-like SearchUnits: "
        f"{int(c3_table.get('pdf_table_gold_count') or 0)}",
    ]


def artifact_change_check(section: Any, artifact_dir: Path, *, changed_key: str) -> dict[str, Any]:
    section = section if isinstance(section, Mapping) else {}
    before_by_name: dict[str, str | None] = {}
    for item in section.get("artifact_hash_checks") or []:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or "")
        if not name:
            continue
        before_by_name[name] = item.get("observed_sha256") or item.get("expected_sha256")
    current = artifact_hashes(artifact_dir)
    checks: list[dict[str, Any]] = []
    changed = False
    for name in sorted(set(ARTIFACT_FILES) | set(before_by_name) | set(current)):
        before = before_by_name.get(name)
        observed = current.get(name)
        if before == observed:
            status = "MATCH"
        elif before or observed:
            status = "MISMATCH"
            changed = True
        else:
            status = "MISSING"
        checks.append({
            "name": name,
            "before_sha256": before,
            "observed_sha256": observed,
            "status": status,
        })
    return {
        "artifact_dir": display_path(artifact_dir),
        "artifact_hash_checks": checks,
        changed_key: changed,
    }


def read_artifact_build(artifact_dir: Path) -> dict[str, Any]:
    build_path = artifact_dir / "build.json"
    manifest_path = artifact_dir / "ingest_manifest.json"
    build = read_optional_json(build_path)
    manifest = read_optional_json(manifest_path)
    return {
        "artifact_dir": display_path(artifact_dir),
        "exists": artifact_dir.exists(),
        "build_json_path": display_path(build_path),
        "build_json_sha256": file_sha256(build_path) if build_path.exists() else None,
        "manifest_path": display_path(manifest_path),
        "manifest_sha256": file_sha256(manifest_path) if manifest_path.exists() else None,
        "index_version": build.get("index_version") or manifest.get("index_version"),
        "chunk_count": build.get("chunk_count") if build.get("chunk_count") is not None else manifest.get("chunk_count"),
        "embedding_model": build.get("embedding_model") or manifest.get("embedding_model"),
        "dimension": build.get("dimension") or manifest.get("dimension"),
    }


def scope_document_version_ids(report: Mapping[str, Any]) -> list[str]:
    cli_scope = report.get("indexing_cli_scope") if isinstance(report.get("indexing_cli_scope"), Mapping) else {}
    scope = report.get("scope") if isinstance(report.get("scope"), Mapping) else {}
    values = cli_scope.get("documentVersionIds") or scope.get("document_version_ids") or []
    return sorted({str(item) for item in values if str(item)})


def scope_source_file_ids(report: Mapping[str, Any]) -> list[str]:
    cli_scope = report.get("indexing_cli_scope") if isinstance(report.get("indexing_cli_scope"), Mapping) else {}
    scope = report.get("scope") if isinstance(report.get("scope"), Mapping) else {}
    values = cli_scope.get("sourceFileIds") or scope.get("source_file_ids") or []
    return sorted({str(item) for item in values if str(item)})


def scope_parser_versions(report: Mapping[str, Any]) -> list[str]:
    cli_scope = report.get("indexing_cli_scope") if isinstance(report.get("indexing_cli_scope"), Mapping) else {}
    scope = report.get("scope") if isinstance(report.get("scope"), Mapping) else {}
    values = cli_scope.get("parserVersions") or scope.get("parser_versions") or []
    return sorted({str(item) for item in values if str(item)})


def report_ref(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": display_path(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() and path.is_file() else None,
        "status": payload.get("status"),
        "promotion_evidence": payload.get("promotion_evidence"),
        "evidence_role": payload.get("evidence_role"),
    }


def artifact_identity(path: Path) -> dict[str, Any]:
    return {
        "path": display_path(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() and path.is_file() else None,
    }


def artifact_hashes(path: Path) -> dict[str, str]:
    return {
        name: file_sha256(path / name)
        for name in ARTIFACT_FILES
        if (path / name).exists()
    }


def read_json(path: Path, blockers: list[str], label: str) -> dict[str, Any]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        blockers.append(f"{label} must be a JSON object: {display_path(path)}")
        return {}
    return payload


def read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_existing_path(path: Path) -> Path:
    direct = resolve_path(path)
    if direct.exists() or path.is_absolute():
        return direct
    worker = AI_WORKER / path
    return worker if worker.exists() else direct


def resolve_output_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai":
        return ROOT / path
    if (Path.cwd() / path).parent.exists():
        return Path.cwd() / path
    return AI_WORKER / path


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai":
        return ROOT / path
    return Path.cwd() / path


def display_path(path: Path) -> str:
    try:
        rel = path.resolve().relative_to(ROOT.resolve())
        return str(rel).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "--report", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--c0-snapshot", default=str(DEFAULT_C0_SNAPSHOT))
    parser.add_argument("--scope-report", default=str(DEFAULT_SCOPE_REPORT))
    parser.add_argument("--c2-report", default=str(DEFAULT_C2_REPORT))
    parser.add_argument("--c3-report", default=str(DEFAULT_C3_REPORT))
    parser.add_argument("--repair-report", default=str(DEFAULT_REPAIR_REPORT))
    parser.add_argument("--expected-index-version", default=PDF_INDEX_VERSION)
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--baseline-artifact-dir", default=str(DEFAULT_BASELINE_ARTIFACT_DIR))
    parser.add_argument("--xlsx-candidate-artifact-dir", default=str(DEFAULT_XLSX_CANDIDATE_ARTIFACT_DIR))
    parser.add_argument("--db-dsn", default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
