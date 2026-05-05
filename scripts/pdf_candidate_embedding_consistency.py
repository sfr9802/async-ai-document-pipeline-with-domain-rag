"""Verify Track C PDF-only candidate embedding consistency.

This is a read-only C4 report. It consumes the explicit C1 PDF scope plus
the C2/C3 readiness reports and verifies that PDF candidate SearchUnits,
embedding_record rows, ragmeta chunks, vector ids, and text hashes all point
at the same candidate namespace. It does not run retrieval, promotion,
baseline updates, or cleanup.
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
DEFAULT_C2_REPORT = Path("reports/pdf_vector_metadata_projection_readiness.json")
DEFAULT_C3_REPORT = Path("reports/rag_pdf_embedding_text_contract_audit.json")
DEFAULT_INDEXING_REPORT = Path("reports/pdf_candidate_indexing_report.json")
DEFAULT_OUTPUT = Path("reports/pdf_candidate_embedding_consistency_report.json")
DEFAULT_XLSX_ARTIFACT_DIR = Path("rag-data-xlsx-candidate-v1")
DEFAULT_IMMUTABLE_BASELINE = Path("reports/initial_immutable_vector_baseline_descriptor.json")

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
    scope_path = Path(args.scope_report)
    c2_path = Path(args.c2_report)
    c3_path = Path(args.c3_report)
    indexing_path = Path(args.indexing_report)
    scope_report = read_json(scope_path, blockers, "c1_scope_report")
    c2_report = read_json(c2_path, blockers, "c2_report")
    c3_report = read_json(c3_path, blockers, "c3_report")
    indexing_report = read_json(indexing_path, blockers, "c4_indexing_report")

    try:
        document_version_ids = scope_document_version_ids(scope_report)
        source_file_ids = scope_source_file_ids(scope_report)
        parser_versions = scope_parser_versions(scope_report)
        with connect(db_dsn) as conn:
            rows = query_candidate_rows(
                conn,
                document_version_ids=document_version_ids,
                source_file_ids=source_file_ids,
                parser_versions=parser_versions,
                expected_index_version=args.expected_index_version,
            )
            outside_scope_rows = query_outside_scope_pdf_candidates(
                conn,
                document_version_ids=document_version_ids,
                source_file_ids=source_file_ids,
                parser_versions=parser_versions,
                expected_index_version=args.expected_index_version,
            )
    except Exception as exc:
        rows = []
        outside_scope_rows = []
        blockers.append(f"C4 PDF candidate consistency inspection failed: {type(exc).__name__}: {exc}")

    payload = build_payload(
        scope_report=scope_report,
        scope_report_path=scope_path,
        c2_report=c2_report,
        c2_report_path=c2_path,
        c3_report=c3_report,
        c3_report_path=c3_path,
        indexing_report=indexing_report,
        indexing_report_path=indexing_path,
        db_rows=rows,
        outside_scope_rows=outside_scope_rows,
        db_dsn=db_dsn,
        expected_index_version=args.expected_index_version,
        blockers=blockers,
        warnings=warnings,
        xlsx_artifact_dir=Path(args.xlsx_artifact_dir),
        immutable_baseline_path=Path(args.immutable_baseline),
    )
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0 if payload.get("status") == "PASS" else 2


def build_payload(
    *,
    scope_report: Mapping[str, Any],
    scope_report_path: Path,
    c2_report: Mapping[str, Any],
    c2_report_path: Path,
    c3_report: Mapping[str, Any],
    c3_report_path: Path,
    indexing_report: Mapping[str, Any],
    indexing_report_path: Path,
    db_rows: list[Mapping[str, Any]],
    outside_scope_rows: list[Mapping[str, Any]] | None = None,
    db_dsn: str,
    expected_index_version: str,
    blockers: list[str],
    warnings: list[str],
    xlsx_artifact_dir: Path = DEFAULT_XLSX_ARTIFACT_DIR,
    immutable_baseline_path: Path = DEFAULT_IMMUTABLE_BASELINE,
) -> dict[str, Any]:
    blocker_list = list(blockers)
    warning_list = list(warnings)
    validate_inputs(
        scope_report=scope_report,
        c2_report=c2_report,
        c3_report=c3_report,
        indexing_report=indexing_report,
        expected_index_version=expected_index_version,
        blockers=blocker_list,
        warnings=warning_list,
    )
    rows = [dict(row) for row in db_rows]
    scoped_rows = len(rows)
    candidate_rows = [row for row in rows if is_candidate_row(row)]
    policy_excluded_rows = [row for row in rows if is_policy_excluded(row)]
    outside_rows = [dict(row) for row in (outside_scope_rows or [])]
    summary = consistency_summary(
        candidate_rows,
        rows,
        expected_index_version,
        outside_scope_count=len(outside_rows),
    )

    for key in (
        "missing_embedding_text_count",
        "missing_location_json_count",
        "missing_citation_text_count",
        "not_embedded_count",
        "failed_count",
        "embedding_claimed_count",
        "index_version_mismatch_count",
        "embedding_record_missing_count",
        "embedding_text_sha_mismatch_count",
        "candidate_chunk_missing_count",
        "vector_namespace_mismatch_count",
        "chunk_sha_mismatch_count",
        "chunk_location_json_mismatch_count",
        "chunk_citation_text_mismatch_count",
        "source_file_type_mismatch_count",
        "parser_version_mismatch_count",
        "outside_scope_pdf_candidate_count",
    ):
        if int(summary.get(key) or 0) != 0:
            blocker_list.append(f"{key} must be 0")
    if int(summary.get("candidate_rows") or 0) == 0:
        blocker_list.append("candidate_rows must be greater than 0")
    if int(indexing_totals(indexing_report).get("claimed") or 0) <= 0:
        blocker_list.append("indexing_report.totals.claimed must be greater than 0")

    sample_failures = [
        sample_failure(row, expected_index_version)
        for row in candidate_rows
        if row_failure_reasons(row, expected_index_version)
    ][:25]
    status = "PASS" if not blocker_list else "FAIL"
    document_version_ids = scope_document_version_ids(scope_report)
    source_file_ids = scope_source_file_ids(scope_report)
    parser_versions = scope_parser_versions(scope_report)

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
        "index_version": expected_index_version,
        "expected_index_version": expected_index_version,
        "artifact_dir": PDF_ARTIFACT_DIR,
        "allowUnscoped": False,
        "retrieval_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "db_dsn": redact_dsn(db_dsn),
        "input_artifacts": [
            artifact_identity(scope_report_path),
            artifact_identity(c2_report_path),
            artifact_identity(c3_report_path),
            artifact_identity(indexing_report_path),
        ],
        "c1_scope": {
            "path": str(scope_report_path),
            "status": scope_report.get("status"),
            "sha256": file_sha256(scope_report_path) if scope_report_path.exists() else None,
            "document_version_ids": document_version_ids,
            "source_file_ids": source_file_ids,
            "parser_versions": parser_versions,
        },
        "c2_report": report_ref(c2_report, c2_report_path),
        "c3_report": report_ref(c3_report, c3_report_path),
        "indexing_report": {
            **report_ref(indexing_report, indexing_report_path),
            "index_version": indexing_report.get("index_version"),
            "artifact_dir": indexing_report.get("artifact_dir"),
            "resolvedIndexDir": indexing_report.get("resolvedIndexDir"),
            "dryRun": indexing_report.get("dryRun"),
            "allowUnscoped": indexing_report.get("allowUnscoped"),
            "totals": indexing_totals(indexing_report),
            "artifact_contract": indexing_report.get("artifact_contract"),
        },
        "indexing_reconciliation": indexing_reconciliation(indexing_report, len(candidate_rows)),
        "scoped_summary": {
            "scoped_rows": scoped_rows,
            "candidate_rows": len(candidate_rows),
            "policy_excluded_rows": len(policy_excluded_rows),
            **summary,
        },
        "status_counts": key_counts(rows, "embedding_status"),
        "index_version_counts": key_counts(rows, "index_version"),
        "parser_version_counts": key_counts(rows, "parser_version"),
        "document_scope_details": document_scope_details(rows, candidate_rows, expected_index_version),
        "sample_failures": sample_failures,
        "sample_outside_scope_pdf_candidates": outside_rows[:25],
        "sample_policy_exclusions": [sample_policy_exclusion(row) for row in policy_excluded_rows[:25]],
        "artifact_guardrails": {
            "xlsx_candidate_artifact": artifact_tree_identity(xlsx_artifact_dir),
            "immutable_baseline": artifact_identity(immutable_baseline_path),
            "xlsx_artifact_changed": False,
            "immutable_baseline_changed": False,
            "reason": "This C4 consistency script is read-only and does not write XLSX artifacts or baseline descriptors.",
        },
        "blockers": dedupe(blocker_list),
        "warnings": dedupe(warning_list),
        "next_action": (
            "C4 consistency passed; C5 PDF-only vector diagnostic may run separately."
            if status == "PASS"
            else "Resolve C4 indexing/consistency blockers before C5."
        ),
        "notes": [
            "This report proves PDF-only candidate namespace consistency, not retrieval ranking quality.",
            "Promotion evidence remains false and immutable baseline artifacts are not updated.",
            "Policy-excluded document summaries and lower-trust OCR rows remain visible but are not C4 candidate rows.",
        ],
    }


def validate_inputs(
    *,
    scope_report: Mapping[str, Any],
    c2_report: Mapping[str, Any],
    c3_report: Mapping[str, Any],
    indexing_report: Mapping[str, Any],
    expected_index_version: str,
    blockers: list[str],
    warnings: list[str],
) -> None:
    for label, report in (("C1", scope_report), ("C2", c2_report), ("C3", c3_report)):
        if report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
            blockers.append(f"{label} report must pass before C4; got {report.get('status')}")
        if report.get("promotion_evidence") is not False:
            blockers.append(f"{label} report must keep promotion_evidence=false")
        if report.get("evidence_role") != "diagnostic":
            blockers.append(f"{label} report must keep evidence_role=diagnostic")
        if report.get("allowUnscoped") is not False:
            blockers.append(f"{label} report must keep allowUnscoped=false")
    if scope_report.get("source_file_type") != "PDF":
        blockers.append("C1 scope report must be source_file_type=PDF")
    if not scope_document_version_ids(scope_report):
        blockers.append("C1 scope report must provide document_version_ids")
    if not scope_source_file_ids(scope_report):
        blockers.append("C1 scope report must provide source_file_ids")
    if not scope_parser_versions(scope_report):
        blockers.append("C1 scope report must provide parser_versions")
    if indexing_report.get("status") != "PASS":
        blockers.append(f"C4 indexing report must be PASS; got {indexing_report.get('status')}")
    if indexing_report.get("dryRun") is not False:
        blockers.append("C4 indexing report must be non-dry-run")
    if indexing_report.get("allowUnscoped") is not False:
        blockers.append("C4 indexing report must keep allowUnscoped=false")
    if indexing_report.get("promotion_evidence") is not False:
        blockers.append("C4 indexing report must keep promotion_evidence=false")
    if indexing_report.get("evidence_role") != "diagnostic":
        blockers.append("C4 indexing report must keep evidence_role=diagnostic")
    if indexing_report.get("index_version") != expected_index_version:
        blockers.append("C4 indexing report index_version must match PDF candidate namespace")
    if indexing_report.get("expectedIndexVersion") != expected_index_version:
        blockers.append("C4 indexing report expectedIndexVersion must match PDF candidate namespace")
    artifact_contract = indexing_report.get("artifact_contract") if isinstance(indexing_report.get("artifact_contract"), dict) else {}
    if not artifact_contract:
        blockers.append("C4 indexing report must include artifact_contract")
    else:
        if artifact_contract.get("expected_index_version") != expected_index_version:
            blockers.append("C4 indexing report artifact_contract expected_index_version must match PDF candidate namespace")
        if artifact_contract.get("build_matches_expected_index_version") is not True:
            blockers.append("C4 indexing report artifact build.json must match PDF candidate namespace")
        if artifact_contract.get("manifest_matches_expected_index_version") is not True:
            blockers.append("C4 indexing report artifact ingest_manifest.json must match PDF candidate namespace")
        for label in ("build_json", "ingest_manifest_json", "faiss_index"):
            item = artifact_contract.get(label)
            if not isinstance(item, dict) or item.get("exists") is not True or not item.get("sha256"):
                blockers.append(f"C4 indexing report artifact_contract.{label} must exist with sha256")
    totals = indexing_totals(indexing_report)
    if int(totals.get("failed") or 0) != 0:
        blockers.append("indexing_report.totals.failed must be 0")
    if int(totals.get("indexed") or 0) != int(totals.get("claimed") or 0):
        blockers.append("indexing_report.totals.indexed must equal claimed")
    if indexing_report.get("documentVersionIds") and sorted(indexing_report.get("documentVersionIds")) != scope_document_version_ids(scope_report):
        blockers.append("C4 indexing documentVersionIds must match C1 scope exactly")
    if indexing_report.get("sourceFileIds") and sorted(indexing_report.get("sourceFileIds")) != scope_source_file_ids(scope_report):
        blockers.append("C4 indexing sourceFileIds must match C1 scope exactly")
    inherited = list(scope_report.get("warnings") or [])
    if inherited:
        warnings.extend(inherited)


def query_candidate_rows(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_ids: list[str],
    parser_versions: list[str],
    expected_index_version: str,
) -> list[dict[str, Any]]:
    rows = fetch_all(conn, f"""
        SELECT su.id,
               su.document_version_id,
               su.source_file_id::text AS source_file_id,
               su.source_file_name,
               su.source_file_type,
               su.parser_version,
               su.unit_type,
               su.unit_key,
               su.chunk_type,
               su.embedding_status,
               su.embedding_status_detail,
               su.embedding_claimed_at,
               su.index_id,
               su.index_version,
               su.embedding_text,
               su.location_json,
               su.citation_text,
               er.id AS embedding_record_id,
               er.embedding_model AS embedding_record_model,
               er.embedding_text_sha256 AS embedding_record_sha256,
               er.vector_id AS embedding_record_vector_id,
               c.chunk_id AS chunk_id,
               c.index_version AS chunk_index_version,
               c.text AS chunk_text,
               c.extra_json AS chunk_extra_json,
               ({POLICY_EXCLUDED_SQL}) AS policy_excluded
          FROM search_unit su
          LEFT JOIN embedding_record er
            ON er.search_unit_id = su.id
           AND er.index_version = %s
          LEFT JOIN ragmeta.chunks c
            ON c.chunk_id = su.index_id
           AND c.index_version = %s
         WHERE su.document_version_id = ANY(%s)
           AND su.source_file_id::text = ANY(%s)
           AND upper(coalesce(su.source_file_type, '')) = 'PDF'
           AND su.parser_version = ANY(%s)
         ORDER BY su.document_version_id, su.id
    """, (expected_index_version, expected_index_version, document_version_ids, source_file_ids, parser_versions))
    return rows_to_plain(rows)


def query_outside_scope_pdf_candidates(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_ids: list[str],
    parser_versions: list[str],
    expected_index_version: str,
) -> list[dict[str, Any]]:
    rows = fetch_all(conn, f"""
        SELECT su.id,
               su.document_version_id,
               su.source_file_id::text AS source_file_id,
               su.source_file_name,
               su.source_file_type,
               su.parser_version,
               su.embedding_status,
               su.index_id,
               su.index_version,
               er.id AS embedding_record_id,
               c.chunk_id AS chunk_id,
               ({POLICY_EXCLUDED_SQL}) AS policy_excluded
          FROM search_unit su
          LEFT JOIN embedding_record er
            ON er.search_unit_id = su.id
           AND er.index_version = %s
          LEFT JOIN ragmeta.chunks c
            ON c.chunk_id = su.index_id
           AND c.index_version = %s
         WHERE upper(coalesce(su.source_file_type, '')) = 'PDF'
           AND (
                su.index_version = %s
                OR er.id IS NOT NULL
                OR c.chunk_id IS NOT NULL
           )
           AND NOT (
                su.document_version_id = ANY(%s)
                AND su.source_file_id::text = ANY(%s)
                AND su.parser_version = ANY(%s)
           )
         ORDER BY su.document_version_id, su.id
         LIMIT 100
    """, (
        expected_index_version,
        expected_index_version,
        expected_index_version,
        document_version_ids,
        source_file_ids,
        parser_versions,
    ))
    return rows_to_plain(rows)


def consistency_summary(
    candidate_rows: list[dict[str, Any]],
    scoped_rows: list[dict[str, Any]],
    expected_index_version: str,
    *,
    outside_scope_count: int = 0,
) -> dict[str, int]:
    return {
        "candidate_rows": len(candidate_rows),
        "missing_embedding_text_count": sum(1 for row in scoped_rows if not is_policy_excluded(row) and not clean(row.get("embedding_text"))),
        "missing_location_json_count": sum(1 for row in scoped_rows if not is_policy_excluded(row) and not object_or_empty(row.get("location_json"))),
        "missing_citation_text_count": sum(1 for row in scoped_rows if not is_policy_excluded(row) and not clean(row.get("citation_text"))),
        "not_embedded_count": sum(1 for row in candidate_rows if row.get("embedding_status") != "EMBEDDED"),
        "failed_count": sum(1 for row in candidate_rows if row.get("embedding_status") == "FAILED"),
        "embedding_claimed_count": sum(1 for row in candidate_rows if clean(row.get("embedding_claimed_at"))),
        "index_version_mismatch_count": sum(1 for row in candidate_rows if row.get("index_version") != expected_index_version),
        "embedding_record_missing_count": sum(1 for row in candidate_rows if not row.get("embedding_record_id")),
        "embedding_text_sha_mismatch_count": sum(1 for row in candidate_rows if embedding_text_sha_mismatch(row)),
        "candidate_chunk_missing_count": sum(1 for row in candidate_rows if not row.get("chunk_id")),
        "vector_namespace_mismatch_count": sum(1 for row in candidate_rows if vector_namespace_mismatch(row, expected_index_version)),
        "chunk_sha_mismatch_count": sum(1 for row in candidate_rows if chunk_sha_mismatch(row)),
        "chunk_location_json_mismatch_count": sum(1 for row in candidate_rows if chunk_location_json_mismatch(row)),
        "chunk_citation_text_mismatch_count": sum(1 for row in candidate_rows if chunk_citation_text_mismatch(row)),
        "source_file_type_mismatch_count": sum(1 for row in scoped_rows if str(row.get("source_file_type") or "").upper() != "PDF"),
        "parser_version_mismatch_count": 0,
        "outside_scope_pdf_candidate_count": outside_scope_count,
    }


def is_policy_excluded(row: Mapping[str, Any]) -> bool:
    return bool(row.get("policy_excluded"))


def is_candidate_row(row: Mapping[str, Any]) -> bool:
    return (
        not is_policy_excluded(row)
        and bool(clean(row.get("embedding_text")))
        and bool(object_or_empty(row.get("location_json")))
        and bool(clean(row.get("citation_text")))
    )


def row_failure_reasons(row: Mapping[str, Any], expected_index_version: str) -> list[str]:
    reasons: list[str] = []
    if row.get("embedding_status") != "EMBEDDED":
        reasons.append("not_embedded")
    if row.get("embedding_status") == "FAILED":
        reasons.append("failed")
    if clean(row.get("embedding_claimed_at")):
        reasons.append("embedding_claim_still_set")
    if row.get("index_version") != expected_index_version:
        reasons.append("index_version_mismatch")
    if not row.get("embedding_record_id"):
        reasons.append("embedding_record_missing")
    if embedding_text_sha_mismatch(row):
        reasons.append("embedding_text_sha_mismatch")
    if not row.get("chunk_id"):
        reasons.append("candidate_chunk_missing")
    if vector_namespace_mismatch(row, expected_index_version):
        reasons.append("vector_namespace_mismatch")
    if chunk_sha_mismatch(row):
        reasons.append("chunk_sha_mismatch")
    if chunk_location_json_mismatch(row):
        reasons.append("chunk_location_json_mismatch")
    if chunk_citation_text_mismatch(row):
        reasons.append("chunk_citation_text_mismatch")
    return reasons


def sample_failure(row: Mapping[str, Any], expected_index_version: str) -> dict[str, Any]:
    extra = object_or_empty(row.get("chunk_extra_json"))
    return {
        "id": row.get("id"),
        "document_version_id": row.get("document_version_id"),
        "source_file_id": row.get("source_file_id"),
        "source_file_name": row.get("source_file_name"),
        "parser_version": row.get("parser_version"),
        "embedding_status": row.get("embedding_status"),
        "index_version": row.get("index_version"),
        "index_id": row.get("index_id"),
        "embedding_record_id": row.get("embedding_record_id"),
        "embedding_record_vector_id": row.get("embedding_record_vector_id"),
        "chunk_id": row.get("chunk_id"),
        "chunk_vector_id": first_value(extra, "vectorId", "vector_id"),
        "failure_reasons": row_failure_reasons(row, expected_index_version),
    }


def sample_policy_exclusion(row: Mapping[str, Any]) -> dict[str, Any]:
    location = object_or_empty(row.get("location_json"))
    return {
        "id": row.get("id"),
        "document_version_id": row.get("document_version_id"),
        "source_file_name": row.get("source_file_name"),
        "unit_type": row.get("unit_type"),
        "chunk_type": row.get("chunk_type"),
        "page_no": location.get("page_no"),
        "ocr_used": location.get("ocr_used"),
        "ocr_confidence": location.get("ocr_confidence"),
        "embedding_status": row.get("embedding_status"),
        "embedding_status_detail": row.get("embedding_status_detail"),
    }


def embedding_text_sha_mismatch(row: Mapping[str, Any]) -> bool:
    stored = clean(row.get("embedding_record_sha256"))
    text = clean(row.get("embedding_text"))
    return bool(stored and text and stored != sha256(text))


def vector_namespace_mismatch(row: Mapping[str, Any], expected_index_version: str) -> bool:
    prefix = f"{expected_index_version}:"
    er_vector = clean(row.get("embedding_record_vector_id"))
    extra = object_or_empty(row.get("chunk_extra_json"))
    chunk_vector = clean(first_value(extra, "vectorId", "vector_id"))
    if row.get("embedding_record_id") and not er_vector:
        return True
    if row.get("chunk_id") and not chunk_vector:
        return True
    if er_vector and not er_vector.startswith(prefix):
        return True
    if chunk_vector and not chunk_vector.startswith(prefix):
        return True
    expected = clean(row.get("index_id"))
    if er_vector and expected and er_vector != f"{expected_index_version}:{expected}":
        return True
    if chunk_vector and er_vector and chunk_vector != er_vector:
        return True
    return False


def chunk_sha_mismatch(row: Mapping[str, Any]) -> bool:
    if not row.get("chunk_id") or not row.get("embedding_record_id"):
        return False
    extra = object_or_empty(row.get("chunk_extra_json"))
    chunk_sha = clean(first_value(extra, "embeddingTextSha256", "embedding_text_sha256"))
    er_sha = clean(row.get("embedding_record_sha256"))
    return not chunk_sha or not er_sha or chunk_sha != er_sha


def chunk_location_json_mismatch(row: Mapping[str, Any]) -> bool:
    if not row.get("chunk_id"):
        return False
    extra = object_or_empty(row.get("chunk_extra_json"))
    chunk_location = object_or_empty(first_value(extra, "locationJson", "location_json"))
    source_location = object_or_empty(row.get("location_json"))
    return not chunk_location or chunk_location != source_location


def chunk_citation_text_mismatch(row: Mapping[str, Any]) -> bool:
    if not row.get("chunk_id"):
        return False
    extra = object_or_empty(row.get("chunk_extra_json"))
    chunk_citation = clean(first_value(extra, "citationText", "citation_text"))
    source_citation = clean(row.get("citation_text"))
    return not chunk_citation or chunk_citation != source_citation


def document_scope_details(
    rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    expected_index_version: str,
) -> list[dict[str, Any]]:
    by_doc: dict[str, list[dict[str, Any]]] = {}
    candidate_by_doc: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_doc.setdefault(str(row.get("document_version_id")), []).append(row)
    for row in candidate_rows:
        candidate_by_doc.setdefault(str(row.get("document_version_id")), []).append(row)
    details = []
    for docv in sorted(by_doc):
        doc_rows = by_doc[docv]
        cand = candidate_by_doc.get(docv, [])
        details.append({
            "document_version_id": docv,
            "source_file_ids": sorted({str(row.get("source_file_id")) for row in doc_rows if row.get("source_file_id")}),
            "source_file_names": sorted({str(row.get("source_file_name")) for row in doc_rows if row.get("source_file_name")}),
            "scoped_rows": len(doc_rows),
            "candidate_rows": len(cand),
            "embedded_rows": sum(1 for row in cand if row.get("embedding_status") == "EMBEDDED"),
            "expected_index_version_rows": sum(1 for row in cand if row.get("index_version") == expected_index_version),
            "embedding_record_rows": sum(1 for row in cand if row.get("embedding_record_id")),
            "ragmeta_chunk_rows": sum(1 for row in cand if row.get("chunk_id")),
        })
    return details


def key_counts(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "UNKNOWN")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def report_ref(report: Mapping[str, Any], path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() else None,
        "status": report.get("status"),
        "promotion_evidence": report.get("promotion_evidence"),
        "evidence_role": report.get("evidence_role"),
        "allowUnscoped": report.get("allowUnscoped"),
    }


def indexing_totals(report: Mapping[str, Any]) -> dict[str, int]:
    totals = report.get("totals")
    if not isinstance(totals, dict):
        return {"claimed": 0, "indexed": 0, "failed": 0, "stale": 0, "skipped_local": 0}
    return {
        "claimed": int(totals.get("claimed") or 0),
        "indexed": int(totals.get("indexed") or 0),
        "failed": int(totals.get("failed") or 0),
        "stale": int(totals.get("stale") or 0),
        "skipped_local": int(totals.get("skipped_local") or 0),
    }


def indexing_reconciliation(report: Mapping[str, Any], final_candidate_rows: int) -> dict[str, int]:
    totals = indexing_totals(report)
    newly_indexed = totals["indexed"]
    return {
        "claimed_count": totals["claimed"],
        "newly_indexed_count": newly_indexed,
        "final_embedded_candidate_count": final_candidate_rows,
        "previously_embedded_count": max(0, final_candidate_rows - newly_indexed),
    }


def artifact_tree_identity(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "sha256": None, "files": []}
    if path.is_file():
        return artifact_identity(path)
    h = hashlib.sha256()
    files: list[dict[str, Any]] = []
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        rel = file_path.relative_to(path).as_posix()
        digest = file_sha256(file_path)
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(digest.encode("ascii"))
        h.update(b"\n")
        files.append({"path": rel, "size": file_path.stat().st_size, "sha256": digest})
    return {"path": str(path), "exists": True, "sha256": h.hexdigest(), "files": files}


def scope_document_version_ids(scope_report: Mapping[str, Any]) -> list[str]:
    return sorted(str(item) for item in ((scope_report.get("scope") or {}).get("document_version_ids") or []) if str(item))


def scope_source_file_ids(scope_report: Mapping[str, Any]) -> list[str]:
    return sorted(str(item) for item in ((scope_report.get("scope") or {}).get("source_file_ids") or []) if str(item))


def scope_parser_versions(scope_report: Mapping[str, Any]) -> list[str]:
    return sorted(str(item) for item in ((scope_report.get("scope") or {}).get("parser_versions") or []) if str(item))


def object_or_empty(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def first_value(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope-report", default=str(DEFAULT_SCOPE_REPORT))
    parser.add_argument("--c2-report", default=str(DEFAULT_C2_REPORT))
    parser.add_argument("--c3-report", default=str(DEFAULT_C3_REPORT))
    parser.add_argument("--indexing-report", default=str(DEFAULT_INDEXING_REPORT))
    parser.add_argument("--output", "--report", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--expected-index-version", default=PDF_INDEX_VERSION)
    parser.add_argument("--db-dsn", default=None)
    parser.add_argument("--xlsx-artifact-dir", default=str(DEFAULT_XLSX_ARTIFACT_DIR))
    parser.add_argument("--immutable-baseline", default=str(DEFAULT_IMMUTABLE_BASELINE))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
