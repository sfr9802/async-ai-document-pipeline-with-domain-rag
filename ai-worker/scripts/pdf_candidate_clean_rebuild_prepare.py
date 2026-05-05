"""Prepare a scoped clean rebuild for the Track C PDF candidate namespace.

This C4 helper is intentionally narrow. It consumes the C1 PDF scope report,
removes only stale rows for the PDF candidate namespace inside that explicit
scope, and resets indexable SearchUnits to PENDING before the scoped indexing
wrapper runs. It does not run broad indexing, retrieval, or promotion.
"""

from __future__ import annotations

import argparse
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


DEFAULT_SCOPE_REPORT = Path("eval/reports/rag-ingestion/pdf_candidate_scope_report.json")
DEFAULT_C2_REPORT = Path("eval/reports/rag-ingestion/pdf_vector_metadata_projection_readiness.json")
DEFAULT_C3_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_embedding_text_contract_audit.json")
DEFAULT_REPAIR_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_search_unit_surface_repair_report.json")
DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/pdf_candidate_clean_rebuild_prepare_report.json")
DEFAULT_ARTIFACT_DIR = Path(PDF_ARTIFACT_DIR)
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

SCOPED_CTE = f"""
WITH scoped AS (
  SELECT su.*,
         ('source_file:' || su.source_file_id::text || ':unit:' ||
          upper(coalesce(su.unit_type, '')) || ':' || su.unit_key) AS stable_index_id,
         ({POLICY_EXCLUDED_SQL}) AS policy_excluded
    FROM search_unit su
   WHERE su.document_version_id = ANY(%s)
     AND su.source_file_id::text = ANY(%s)
     AND upper(coalesce(su.source_file_type, '')) = 'PDF'
     AND su.parser_version = ANY(%s)
)
"""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_dsn = args.db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN
    blockers: list[str] = []
    warnings: list[str] = []

    scope_path = resolve_existing_path(Path(args.scope_report))
    c2_path = resolve_existing_path(Path(args.c2_report))
    c3_path = resolve_existing_path(Path(args.c3_report))
    repair_path = resolve_existing_path(Path(args.repair_report))
    output_path = resolve_output_path(Path(args.output))
    artifact_dir = resolve_path(Path(args.artifact_dir))

    scope_report = read_json(scope_path, blockers, "c1_scope_report")
    c2_report = read_json(c2_path, blockers, "c2_report")
    c3_report = read_json(c3_path, blockers, "c3_report")
    repair_report = read_json(repair_path, blockers, "repair_report")

    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    mutations: dict[str, Any] = {
        "apply": bool(args.apply),
        "deleted_embedding_record_count": 0,
        "deleted_ragmeta_chunk_count": 0,
        "deleted_index_build_count": 0,
        "reset_indexable_search_unit_count": 0,
        "cleared_policy_excluded_candidate_state_count": 0,
    }

    try:
        document_version_ids = scope_document_version_ids(scope_report)
        source_file_ids = scope_source_file_ids(scope_report)
        parser_versions = scope_parser_versions(scope_report)
        validate_inputs(
            scope_report=scope_report,
            c2_report=c2_report,
            c3_report=c3_report,
            repair_report=repair_report,
            expected_index_version=args.expected_index_version,
            document_version_ids=document_version_ids,
            source_file_ids=source_file_ids,
            parser_versions=parser_versions,
            artifact_dir=artifact_dir,
            blockers=blockers,
        )
        if not blockers:
            with connect(db_dsn) as conn:
                before = inspect_scope(
                    conn,
                    document_version_ids=document_version_ids,
                    source_file_ids=source_file_ids,
                    parser_versions=parser_versions,
                    expected_index_version=args.expected_index_version,
                    sample_limit=args.sample_limit,
                )
                if args.apply:
                    mutations.update(apply_prepare(
                        conn,
                        document_version_ids=document_version_ids,
                        source_file_ids=source_file_ids,
                        parser_versions=parser_versions,
                        expected_index_version=args.expected_index_version,
                    ))
                    conn.commit()
                after = inspect_scope(
                    conn,
                    document_version_ids=document_version_ids,
                    source_file_ids=source_file_ids,
                    parser_versions=parser_versions,
                    expected_index_version=args.expected_index_version,
                    sample_limit=args.sample_limit,
                )
    except Exception as exc:
        blockers.append(f"scoped clean rebuild prepare failed: {type(exc).__name__}: {exc}")

    payload = build_payload(
        scope_report=scope_report,
        scope_path=scope_path,
        c2_report=c2_report,
        c2_path=c2_path,
        c3_report=c3_report,
        c3_path=c3_path,
        repair_report=repair_report,
        repair_path=repair_path,
        db_dsn=db_dsn,
        expected_index_version=args.expected_index_version,
        artifact_dir=artifact_dir,
        before=before,
        mutations=mutations,
        after=after,
        blockers=blockers,
        warnings=warnings,
    )
    write_json(output_path, payload)
    print_report(payload)
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def validate_inputs(
    *,
    scope_report: Mapping[str, Any],
    c2_report: Mapping[str, Any],
    c3_report: Mapping[str, Any],
    repair_report: Mapping[str, Any],
    expected_index_version: str,
    document_version_ids: list[str],
    source_file_ids: list[str],
    parser_versions: list[str],
    artifact_dir: Path,
    blockers: list[str],
) -> None:
    if scope_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C1 scope report must pass before C4 cleanup: {scope_report.get('status')}")
    if scope_report.get("promotion_evidence") is not False:
        blockers.append("C1 scope report must keep promotion_evidence=false")
    if scope_report.get("evidence_role") != "diagnostic":
        blockers.append("C1 scope report must keep evidence_role=diagnostic")
    if scope_report.get("allowUnscoped") is not False:
        blockers.append("C1 scope report must keep allowUnscoped=false")
    cli_scope = scope_report.get("indexing_cli_scope") if isinstance(scope_report.get("indexing_cli_scope"), Mapping) else {}
    if cli_scope.get("allowUnscoped") is not False:
        blockers.append("C1 indexing_cli_scope must keep allowUnscoped=false")
    if (cli_scope.get("expectedIndexVersion") or scope_report.get("index_version")) != expected_index_version:
        blockers.append("C1 expectedIndexVersion must match the requested PDF candidate namespace")
    if sorted(str(item).upper() for item in cli_scope.get("sourceFileTypes") or []) != ["PDF"]:
        blockers.append("C1 sourceFileTypes must be PDF only")
    if set(parser_versions) != set(PDF_PARSER_VERSIONS):
        blockers.append(f"C1 parser_versions must be {sorted(PDF_PARSER_VERSIONS)}")
    if not document_version_ids:
        blockers.append("C1 scope report must provide documentVersionIds")
    if not source_file_ids:
        blockers.append("C1 scope report must provide sourceFileIds")
    if artifact_dir.exists():
        blockers.append(f"artifact_dir already exists; refusing silent reuse/overwrite: {display_path(artifact_dir)}")
    for label, report in (("C2", c2_report), ("C3", c3_report), ("repair", repair_report)):
        if report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
            blockers.append(f"{label} report must pass before C4 cleanup: {report.get('status')}")
        if report.get("promotion_evidence") is not False:
            blockers.append(f"{label} report must keep promotion_evidence=false")
    expected_counts = expected_scope_counts(c2_report)
    if expected_counts["scoped"] != 8203:
        blockers.append(f"C2 scoped_rows must be 8203 before C4 cleanup: {expected_counts['scoped']}")
    if expected_counts["indexable"] != 8194:
        blockers.append(f"C2 indexable_rows must be 8194 before C4 cleanup: {expected_counts['indexable']}")
    if expected_counts["policy_excluded"] != 9:
        blockers.append(
            f"C2 policy_excluded_rows must be 9 before C4 cleanup: {expected_counts['policy_excluded']}"
        )


def inspect_scope(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_ids: list[str],
    parser_versions: list[str],
    expected_index_version: str,
    sample_limit: int,
) -> dict[str, Any]:
    params = (document_version_ids, source_file_ids, parser_versions)
    summary = fetch_one(conn, SCOPED_CTE + """
        SELECT count(*)::int AS scoped_search_unit_count,
               count(*) FILTER (WHERE NOT policy_excluded)::int AS indexable_search_unit_count,
               count(*) FILTER (WHERE policy_excluded)::int AS policy_excluded_search_unit_count,
               count(*) FILTER (WHERE NOT policy_excluded AND embedding_status = 'PENDING')::int
                 AS indexable_pending_count,
               count(*) FILTER (WHERE NOT policy_excluded AND embedding_status = 'FAILED')::int
                 AS indexable_failed_count,
               count(*) FILTER (WHERE NOT policy_excluded AND embedding_status = 'EMBEDDED')::int
                 AS indexable_embedded_count,
               count(*) FILTER (WHERE policy_excluded AND embedding_status = 'SKIPPED')::int
                 AS policy_excluded_skipped_count,
               count(*) FILTER (WHERE index_version = %s)::int AS search_unit_candidate_index_count,
               count(*) FILTER (WHERE index_id IS NOT NULL)::int AS search_unit_index_id_count,
               count(*) FILTER (WHERE embedding_claim_token IS NOT NULL)::int AS claimed_count
          FROM scoped
    """, params + (expected_index_version,))
    namespace_summary = fetch_one(conn, SCOPED_CTE + """
        SELECT (SELECT count(*)::int
                  FROM ragmeta.chunks c
                 WHERE c.index_version = %s) AS namespace_chunk_count,
               (SELECT count(*)::int
                  FROM ragmeta.chunks c
                  JOIN scoped s ON s.stable_index_id = c.chunk_id
                 WHERE c.index_version = %s) AS scoped_namespace_chunk_count,
               (SELECT count(*)::int
                  FROM ragmeta.chunks c
                  LEFT JOIN scoped s ON s.stable_index_id = c.chunk_id
                 WHERE c.index_version = %s
                   AND s.id IS NULL) AS unexpected_namespace_chunk_count,
               (SELECT count(*)::int
                  FROM embedding_record er
                  JOIN scoped s ON s.id = er.search_unit_id
                 WHERE er.index_version = %s) AS scoped_embedding_record_count,
               (SELECT count(*)::int
                  FROM embedding_record er
                  LEFT JOIN scoped s ON s.id = er.search_unit_id
                 WHERE er.index_version = %s
                   AND s.id IS NULL) AS unexpected_embedding_record_count,
               (SELECT count(*)::int
                  FROM ragmeta.index_builds ib
                 WHERE ib.index_version = %s) AS index_build_count
    """, params + (
        expected_index_version,
        expected_index_version,
        expected_index_version,
        expected_index_version,
        expected_index_version,
        expected_index_version,
    ))
    status_counts = fetch_all(conn, SCOPED_CTE + """
        SELECT embedding_status,
               coalesce(index_version, '<null>') AS index_version,
               count(*)::int AS count
          FROM scoped
         GROUP BY embedding_status, coalesce(index_version, '<null>')
         ORDER BY embedding_status, coalesce(index_version, '<null>')
    """, params)
    namespace_samples = fetch_all(conn, SCOPED_CTE + """
        SELECT c.chunk_id,
               c.faiss_row_id,
               c.doc_id,
               c.extra_json->>'sourceFileId' AS source_file_id,
               c.extra_json->>'documentVersionId' AS document_version_id,
               c.extra_json->>'parserVersion' AS parser_version,
               (s.id IS NOT NULL) AS in_c1_scope
          FROM ragmeta.chunks c
          LEFT JOIN scoped s ON s.stable_index_id = c.chunk_id
         WHERE c.index_version = %s
         ORDER BY c.faiss_row_id
         LIMIT %s
    """, params + (expected_index_version, sample_limit))
    return {
        "summary": plain(summary),
        "namespace_summary": plain(namespace_summary),
        "status_counts": rows_to_plain(status_counts),
        "sample_namespace_chunks": rows_to_plain(namespace_samples),
    }


def apply_prepare(
    conn: Any,
    *,
    document_version_ids: list[str],
    source_file_ids: list[str],
    parser_versions: list[str],
    expected_index_version: str,
) -> dict[str, Any]:
    params = (document_version_ids, source_file_ids, parser_versions)
    with conn.cursor() as cur:
        cur.execute(SCOPED_CTE + """
            DELETE FROM embedding_record er
             USING scoped s
             WHERE er.search_unit_id = s.id
               AND er.index_version = %s
             RETURNING er.id
        """, params + (expected_index_version,))
        deleted_embedding_records = cur.rowcount

        cur.execute(SCOPED_CTE + """
            DELETE FROM ragmeta.chunks c
             USING scoped s
             WHERE c.index_version = %s
               AND c.chunk_id = s.stable_index_id
             RETURNING c.chunk_id
        """, params + (expected_index_version,))
        deleted_chunks = cur.rowcount

        cur.execute("DELETE FROM ragmeta.index_builds WHERE index_version = %s RETURNING index_version", (
            expected_index_version,
        ))
        deleted_index_builds = cur.rowcount

        cur.execute(SCOPED_CTE + """
            UPDATE search_unit su
               SET embedding_status = 'PENDING',
                   embedding_status_detail = 'scoped pdf c4 clean rebuild prepare',
                   index_id = NULL,
                   index_version = NULL,
                   indexed_content_sha256 = NULL,
                   embedding_claim_token = NULL,
                   embedding_claimed_at = NULL,
                   embedded_at = NULL,
                   updated_at = now()
              FROM scoped s
             WHERE su.id = s.id
               AND NOT s.policy_excluded
             RETURNING su.id
        """, params)
        reset_indexable = cur.rowcount

        cur.execute(SCOPED_CTE + """
            UPDATE search_unit su
               SET index_id = NULL,
                   index_version = NULL,
                   indexed_content_sha256 = NULL,
                   embedding_claim_token = NULL,
                   embedding_claimed_at = NULL,
                   embedded_at = NULL,
                   updated_at = now()
              FROM scoped s
             WHERE su.id = s.id
               AND s.policy_excluded
               AND (
                    su.index_id IS NOT NULL
                 OR su.index_version IS NOT NULL
                 OR su.indexed_content_sha256 IS NOT NULL
                 OR su.embedding_claim_token IS NOT NULL
                 OR su.embedding_claimed_at IS NOT NULL
                 OR su.embedded_at IS NOT NULL
               )
             RETURNING su.id
        """, params)
        cleared_policy_excluded = cur.rowcount

    return {
        "apply": True,
        "deleted_embedding_record_count": int(deleted_embedding_records),
        "deleted_ragmeta_chunk_count": int(deleted_chunks),
        "deleted_index_build_count": int(deleted_index_builds),
        "reset_indexable_search_unit_count": int(reset_indexable),
        "cleared_policy_excluded_candidate_state_count": int(cleared_policy_excluded),
    }


def build_payload(
    *,
    scope_report: Mapping[str, Any],
    scope_path: Path,
    c2_report: Mapping[str, Any],
    c2_path: Path,
    c3_report: Mapping[str, Any],
    c3_path: Path,
    repair_report: Mapping[str, Any],
    repair_path: Path,
    db_dsn: str,
    expected_index_version: str,
    artifact_dir: Path,
    before: Mapping[str, Any],
    mutations: Mapping[str, Any],
    after: Mapping[str, Any],
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    blocker_list = list(blockers)
    warning_list = list(warnings)
    after_summary = dict(after.get("summary") or {})
    after_namespace = dict(after.get("namespace_summary") or {})
    counts = expected_scope_counts(c2_report)
    apply_mode = bool(mutations.get("apply"))

    if apply_mode and not blocker_list:
        if int(after_summary.get("scoped_search_unit_count") or 0) != counts["scoped"]:
            blocker_list.append("post-cleanup scoped_search_unit_count does not match C2")
        if int(after_summary.get("indexable_search_unit_count") or 0) != counts["indexable"]:
            blocker_list.append("post-cleanup indexable_search_unit_count does not match C2")
        if int(after_summary.get("policy_excluded_search_unit_count") or 0) != counts["policy_excluded"]:
            blocker_list.append("post-cleanup policy_excluded_search_unit_count does not match C2")
        if int(after_summary.get("indexable_pending_count") or 0) != counts["indexable"]:
            blocker_list.append("post-cleanup indexable rows must all be PENDING")
        if int(after_summary.get("policy_excluded_skipped_count") or 0) != counts["policy_excluded"]:
            blocker_list.append("post-cleanup policy-excluded rows must stay SKIPPED")
        if int(after_namespace.get("namespace_chunk_count") or 0) != 0:
            blocker_list.append("post-cleanup PDF candidate namespace chunks must be 0 before rebuild")
        if int(after_namespace.get("scoped_embedding_record_count") or 0) != 0:
            blocker_list.append("post-cleanup scoped embedding_record rows must be 0 before rebuild")
        if int(after_namespace.get("unexpected_embedding_record_count") or 0) != 0:
            blocker_list.append("post-cleanup unexpected embedding_record rows remain in candidate namespace")
        if int(after_namespace.get("index_build_count") or 0) != 0:
            blocker_list.append("post-cleanup ragmeta.index_builds rows must be 0 before rebuild")

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
        "phase": "C4_CLEAN_REBUILD_PREPARE",
        "report_role": "pdf_candidate_clean_rebuild_prepare",
        "source_file_type": "PDF",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "namespace": expected_index_version,
        "index_version": expected_index_version,
        "artifact_dir": display_path(artifact_dir),
        "allowUnscoped": False,
        "retrieval_execution": "not_run_by_this_script",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "db_dsn": redact_dsn(db_dsn),
        "input_artifacts": [
            artifact_identity(scope_path),
            artifact_identity(c2_path),
            artifact_identity(c3_path),
            artifact_identity(repair_path),
        ],
        "c1_scope_report": report_ref(scope_path, scope_report),
        "c2_report": report_ref(c2_path, c2_report),
        "c3_report": report_ref(c3_path, c3_report),
        "repair_report": report_ref(repair_path, repair_report),
        "scope": {
            "document_version_ids": scope_document_version_ids(scope_report),
            "source_file_ids": scope_source_file_ids(scope_report),
            "parser_versions": scope_parser_versions(scope_report),
            "source_file_type": "PDF",
            "allowUnscoped": False,
            "expected_scoped_rows": counts["scoped"],
            "expected_indexable_rows": counts["indexable"],
            "expected_policy_excluded_rows": counts["policy_excluded"],
        },
        "policy": {
            "allow_global_delete": False,
            "cleanup_scope": "C1 documentVersionIds + sourceFileIds + source_file_type=PDF + parserVersions",
            "ragmeta_chunk_delete_scope": "PDF candidate namespace plus scoped stable SearchUnit chunk_id only",
            "embedding_record_delete_scope": "PDF candidate namespace plus scoped SearchUnit ids only",
            "index_build_delete_scope": "PDF candidate namespace only",
            "artifact_dir_policy": "must not pre-exist for this cleanup run",
        },
        "before": before,
        "mutations": dict(mutations),
        "after": after,
        "blocker_category": "non_gold_candidate_namespace_clean_rebuild_prepare" if blocker_list else None,
        "blockers": dedupe(blocker_list),
        "warnings": dedupe(warning_list),
        "next_action": (
            "Run C4 scoped indexing with the explicit PDF C1 scope."
            if status in {"PASS", "PASS_WITH_WARNINGS"} and apply_mode
            else "Resolve cleanup blockers before rerunning C4 scoped indexing."
        ),
        "notes": [
            "This report is diagnostic-only and is not promotion evidence.",
            "The cleanup is scoped to the PDF candidate namespace and C1 PDF SearchUnits.",
            "Policy-excluded PDF rows stay excluded before C4 indexing.",
        ],
    }


def expected_scope_counts(c2_report: Mapping[str, Any]) -> dict[str, int]:
    summary = c2_report.get("summary") if isinstance(c2_report.get("summary"), Mapping) else {}
    return {
        "scoped": int(summary.get("scoped_rows") or 0),
        "indexable": int(summary.get("indexable_rows") or 0),
        "policy_excluded": int(summary.get("policy_excluded_rows") or 0),
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


def plain(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: plain_value(value) for key, value in row.items()}


def plain_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def resolve_existing_path(path: Path) -> Path:
    resolved = resolve_path(path)
    if resolved.exists():
        return resolved
    if not path.is_absolute() and (AI_WORKER / path).exists():
        return AI_WORKER / path
    return resolved


def resolve_output_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai-worker":
        return ROOT / path
    if (Path.cwd().resolve() == ROOT.resolve()) and path.parts and path.parts[0] == "eval":
        return AI_WORKER / path
    return Path.cwd() / path


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai-worker":
        return ROOT / path
    if (Path.cwd().resolve() == ROOT.resolve()) and path.parts and path.parts[0] == "eval":
        return AI_WORKER / path
    return Path.cwd() / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--scope-report", default=str(DEFAULT_SCOPE_REPORT))
    parser.add_argument("--c2-report", default=str(DEFAULT_C2_REPORT))
    parser.add_argument("--c3-report", default=str(DEFAULT_C3_REPORT))
    parser.add_argument("--repair-report", default=str(DEFAULT_REPAIR_REPORT))
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--expected-index-version", default=PDF_INDEX_VERSION)
    parser.add_argument("--db-dsn", default=None)
    parser.add_argument("--sample-limit", type=int, default=10)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
