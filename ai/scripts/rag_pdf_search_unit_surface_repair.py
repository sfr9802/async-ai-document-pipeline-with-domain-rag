"""Repair Track C PDF SearchUnit embedding_text surfaces in an explicit scope.

This utility is for the C2/C3 repair gap before C4. It consumes the C1 PDF
scope report and, in apply mode, updates only indexable PDF SearchUnits inside
that scope whose stored embedding_text lacks source/page/citation/block/OCR
trust surfaces. It does not run retrieval, build vectors, delete ragmeta
chunks, create candidate artifacts, or promote a baseline.
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
DEFAULT_OUTPUT = Path("reports/rag_eval/rag-ingestion/rag_pdf_search_unit_surface_repair_report.json")

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
    scope_report = read_json(scope_path, blockers, "c1_scope_report")
    document_version_ids = scope_document_version_ids(scope_report)
    source_file_ids = scope_source_file_ids(scope_report)
    parser_versions = scope_parser_versions(scope_report)

    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    samples: list[dict[str, Any]] = []
    mutations = {
        "apply": bool(args.apply),
        "updated_search_unit_count": 0,
        "deleted_embedding_record_count": 0,
        "deleted_ragmeta_chunk_count": 0,
    }

    try:
        validate_scope(scope_report, document_version_ids, source_file_ids, parser_versions, blockers)
        if not blockers:
            with connect(db_dsn) as conn:
                before_rows = query_candidate_rows(conn, document_version_ids, source_file_ids, parser_versions)
                before = summarize_rows(before_rows)
                mutation_rows = [row for row in before_rows if needs_repair(row) or needs_state_reset(row)]
                samples = [sample_for_report(row) for row in mutation_rows[: args.sample_limit]]
                if args.apply and mutation_rows:
                    mutations["updated_search_unit_count"] = apply_repairs(conn, mutation_rows)
                    conn.commit()
                after_rows = query_candidate_rows(conn, document_version_ids, source_file_ids, parser_versions)
                after = summarize_rows(after_rows)
    except Exception as exc:
        blockers.append(f"PDF SearchUnit surface repair failed: {type(exc).__name__}: {exc}")

    payload = build_payload(
        scope_report=scope_report,
        scope_report_path=scope_path,
        db_dsn=db_dsn,
        before=before,
        after=after,
        samples=samples,
        mutations=mutations,
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
    db_dsn: str,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    samples: list[dict[str, Any]],
    mutations: Mapping[str, Any],
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    blocker_list = list(blockers)
    warning_list = list(warnings)
    apply_mode = bool(mutations.get("apply"))
    after_mutation_needed = int((after.get("summary") or {}).get("mutation_needed_count") or 0)
    before_mutation_needed = int((before.get("summary") or {}).get("mutation_needed_count") or 0)
    if apply_mode and after_mutation_needed:
        blocker_list.append("mutation_needed_count must be 0 after apply")
    if not apply_mode and before_mutation_needed:
        warning_list.append(
            f"dry_run_mutation_needed_count={before_mutation_needed}; rerun with --apply to mutate scoped DB rows"
        )

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
        "phase": "C3_REPAIR",
        "report_role": "rag_pdf_search_unit_surface_repair",
        "source_file_type": "PDF",
        "promotion_evidence": False,
        "evidence_role": "repair_diagnostic",
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
            "document_version_ids": scope_document_version_ids(scope_report),
            "source_file_ids": list((scope_report.get("scope") or {}).get("source_file_ids") or []),
            "parser_versions": scope_parser_versions(scope_report),
            "inherited_warnings": list(scope_report.get("warnings") or []),
        },
        "policy": {
            "scope": "C1 document_version_ids + source_file_ids + source_file_type=PDF + C1 parser_versions",
            "policy_excluded_rows": "document summaries and OCR rows skipped for missing ocr_confidence",
            "repair_condition": "indexable rows missing source/page/citation/block/OCR trust surface in embedding_text",
            "mutation": (
                "embedding_text/content_sha256 refreshed where needed; all scoped stale indexable rows reset to "
                "PENDING; claim/index fields cleared; no ragmeta chunk deletion"
            ),
        },
        "before": before,
        "mutations": dict(mutations),
        "after": after,
        "sample_repairs": samples,
        "blockers": dedupe(blocker_list),
        "warnings": dedupe(warning_list),
        "next_action": (
            "Rerun C2/C3 after repair apply."
            if status != "FAIL" and apply_mode
            else "Review dry-run samples, then rerun with --apply if the scoped mutations are acceptable."
        ),
        "notes": [
            "This script does not repair existing ragmeta chunks directly.",
            "C4 should rebuild/upsert the PDF candidate namespace after C2/C3 pass.",
            "Rows excluded by OCR confidence policy stay skipped and are not repaired here.",
        ],
    }


def query_candidate_rows(
    conn: Any,
    document_version_ids: list[str],
    source_file_ids: list[str],
    parser_versions: list[str],
) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT su.id,
                   su.document_version_id,
                    su.source_file_id,
                    su.source_file_name,
                    su.source_file_type,
                    su.parser_version,
                    su.unit_type,
                   su.unit_key,
                   su.chunk_type,
                   su.title,
                   su.section_path,
                   su.page_start,
                   su.page_end,
                   su.text_content,
                   su.embedding_text,
                   su.content_sha256,
                   su.display_text,
                   su.citation_text,
                   su.location_json,
                   su.metadata_json,
                   su.embedding_status,
                   su.embedding_status_detail,
                   su.index_id,
                   su.index_version,
                   ({POLICY_EXCLUDED_SQL}) AS policy_excluded
              FROM search_unit su
              WHERE su.document_version_id = ANY(%s)
                AND su.source_file_id::text = ANY(%s)
                AND upper(coalesce(su.source_file_type, '')) = 'PDF'
                AND su.parser_version = ANY(%s)
              ORDER BY su.document_version_id, su.id
        """, (document_version_ids, source_file_ids, parser_versions))
        return rows_to_plain([dict(row) for row in cur.fetchall()])


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    repair_needed = [row for row in rows if needs_repair(row)]
    indexable = [row for row in rows if not row.get("policy_excluded")]
    return {
        "summary": {
            "scoped_rows": len(rows),
            "indexable_rows": len(indexable),
            "policy_excluded_rows": len(rows) - len(indexable),
            "repair_needed_count": len(repair_needed),
            "state_reset_needed_count": sum(1 for row in indexable if needs_state_reset(row)),
            "mutation_needed_count": sum(1 for row in indexable if needs_repair(row) or needs_state_reset(row)),
            "missing_source_file_surface_in_embedding_text_count": sum(
                1 for row in indexable if missing_source_surface(row)
            ),
            "missing_page_surface_in_embedding_text_count": sum(
                1 for row in indexable if missing_page_surface(row)
            ),
            "missing_citation_surface_in_embedding_text_count": sum(
                1 for row in indexable if missing_citation_surface(row)
            ),
            "missing_block_type_surface_in_embedding_text_count": sum(
                1 for row in indexable if missing_block_surface(row)
            ),
            "embedded_ocr_trust_marker_missing_count": sum(
                1 for row in indexable if missing_ocr_trust_surface(row)
            ),
        },
        "repair_reason_counts": reason_counts(repair_needed),
    }


def reason_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for reason in repair_reasons(row):
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def needs_repair(row: Mapping[str, Any]) -> bool:
    return bool(repair_reasons(row))


def needs_state_reset(row: Mapping[str, Any]) -> bool:
    if row.get("policy_excluded"):
        return False
    return (
        row.get("embedding_status") != "PENDING"
        or bool(clean(row.get("index_id")))
        or bool(clean(row.get("index_version")))
    )


def repair_reasons(row: Mapping[str, Any]) -> list[str]:
    if row.get("policy_excluded"):
        return []
    reasons: list[str] = []
    if missing_source_surface(row):
        reasons.append("missing_source_file_surface_in_embedding_text")
    if missing_page_surface(row):
        reasons.append("missing_page_surface_in_embedding_text")
    if missing_citation_surface(row):
        reasons.append("missing_citation_surface_in_embedding_text")
    if missing_block_surface(row):
        reasons.append("missing_block_type_surface_in_embedding_text")
    if missing_ocr_trust_surface(row):
        reasons.append("embedded_ocr_trust_marker_missing")
    return reasons


def canonical_embedding_text(row: Mapping[str, Any]) -> str:
    location = object_or_empty(row.get("location_json"))
    metadata = object_or_empty(row.get("metadata_json"))
    parts: list[str] = []
    append_labeled(parts, "Source", row.get("source_file_name"))
    append_labeled(parts, "Citation", row.get("citation_text"))
    append_labeled(parts, "Chunk", row.get("chunk_type"))
    append_labeled(parts, "Page", first_non_blank(
        value(metadata, "pageLabel", "page_label"),
        value(location, "page_label"),
        value(metadata, "pageNo", "pageNumber", "page"),
        value(location, "page_no"),
        row.get("page_start"),
    ))
    append_labeled(parts, "Section", first_non_blank(row.get("section_path"), value(location, "section_path")))
    append_labeled(parts, "Block", first_non_blank(
        value(metadata, "blockType", "block_type", "role"),
        value(location, "block_type"),
        row.get("chunk_type"),
    ))
    if truthy(value(metadata, "ocrUsed", "ocr_used")) or truthy(value(location, "ocr_used")):
        append_labeled(parts, "OCR", "used")
        append_labeled(parts, "OCR confidence", first_non_blank(
            value(metadata, "ocrConfidence", "ocr_confidence", "confidence"),
            value(location, "ocr_confidence"),
        ))
    body = clean(row.get("text_content")) or clean(row.get("title"))
    if body:
        parts.append("Content:\n" + body)
    return "\n".join(parts).strip()


def apply_repairs(conn: Any, rows: list[dict[str, Any]]) -> int:
    updated = 0
    with conn.cursor() as cur:
        for row in rows:
            new_text = canonical_embedding_text(row) if needs_repair(row) else clean(row.get("embedding_text"))
            if not new_text:
                continue
            cur.execute(
                """
                UPDATE search_unit
                   SET embedding_text = %s,
                       content_sha256 = %s,
                       embedding_status = 'PENDING',
                       embedding_status_detail = 'scoped pdf surface/state repair before candidate reindex',
                       embedding_claim_token = NULL,
                       embedding_claimed_at = NULL,
                       indexed_content_sha256 = NULL,
                       index_id = NULL,
                       index_version = NULL,
                       embedded_at = NULL,
                       updated_at = now()
                 WHERE id = %s
                   AND document_version_id = %s
                   AND source_file_id::text = %s
                   AND upper(coalesce(source_file_type, '')) = 'PDF'
                   AND parser_version = %s
                """,
                (
                    new_text,
                    sha256(new_text),
                    row.get("id"),
                    row.get("document_version_id"),
                    clean(row.get("source_file_id")),
                    row.get("parser_version"),
                ),
            )
            updated += cur.rowcount
    return updated


def sample_for_report(row: Mapping[str, Any]) -> dict[str, Any]:
    new_text = canonical_embedding_text(row) if needs_repair(row) else clean(row.get("embedding_text"))
    reasons = repair_reasons(row)
    if needs_state_reset(row):
        reasons.append("stale_embedding_state_reset")
    return {
        "id": row.get("id"),
        "document_version_id": row.get("document_version_id"),
        "source_file_name": row.get("source_file_name"),
        "chunk_type": row.get("chunk_type"),
        "page_no": object_or_empty(row.get("location_json")).get("page_no"),
        "embedding_status": row.get("embedding_status"),
        "index_version": row.get("index_version"),
        "repair_reasons": reasons,
        "before_embedding_text_preview": preview(row.get("embedding_text")),
        "after_embedding_text_preview": preview(new_text),
        "before_content_sha256": row.get("content_sha256"),
        "after_content_sha256": sha256(new_text) if new_text else None,
    }


def missing_source_surface(row: Mapping[str, Any]) -> bool:
    source = clean(row.get("source_file_name"))
    return bool(source and source not in clean(row.get("embedding_text")))


def missing_page_surface(row: Mapping[str, Any]) -> bool:
    location = object_or_empty(row.get("location_json"))
    page_no = clean(location.get("page_no"))
    if not page_no:
        return False
    text = clean(row.get("embedding_text"))
    return "Page:" not in text and "page:" not in text.lower() and f"p.{page_no}" not in text


def missing_citation_surface(row: Mapping[str, Any]) -> bool:
    citation = clean(row.get("citation_text"))
    return bool(citation and citation not in clean(row.get("embedding_text")))


def missing_block_surface(row: Mapping[str, Any]) -> bool:
    location = object_or_empty(row.get("location_json"))
    block_type = clean(first_non_blank(location.get("block_type"), row.get("chunk_type"), row.get("unit_type")))
    text = clean(row.get("embedding_text"))
    return bool(block_type and "Block:" not in text and "block_type" not in text.lower() and block_type not in text)


def missing_ocr_trust_surface(row: Mapping[str, Any]) -> bool:
    location = object_or_empty(row.get("location_json"))
    if not truthy(location.get("ocr_used")) or row.get("embedding_status") != "EMBEDDED":
        return False
    text = clean(row.get("embedding_text"))
    return "lower_trust_ocr" not in text and "OCR confidence" not in text and "OCR: used" not in text


def validate_scope(
    scope_report: Mapping[str, Any],
    document_version_ids: list[str],
    source_file_ids: list[str],
    parser_versions: list[str],
    blockers: list[str],
) -> None:
    if scope_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C1 scope report must pass before repair; got {scope_report.get('status')}")
    if scope_report.get("promotion_evidence") is not False:
        blockers.append("C1 scope report must keep promotion_evidence=false")
    if scope_report.get("evidence_role") != "diagnostic":
        blockers.append("C1 scope report must keep evidence_role=diagnostic")
    if scope_report.get("allowUnscoped") is not False:
        blockers.append("C1 scope report must keep allowUnscoped=false")
    if not document_version_ids:
        blockers.append("C1 scope report must provide document_version_ids")
    if not source_file_ids:
        blockers.append("C1 scope report must provide source_file_ids")
    if not parser_versions:
        blockers.append("C1 scope report must provide parser_versions")


def scope_document_version_ids(scope_report: Mapping[str, Any]) -> list[str]:
    return sorted(str(item) for item in ((scope_report.get("scope") or {}).get("document_version_ids") or []) if str(item))


def scope_source_file_ids(scope_report: Mapping[str, Any]) -> list[str]:
    return sorted(str(item) for item in ((scope_report.get("scope") or {}).get("source_file_ids") or []) if str(item))


def scope_parser_versions(scope_report: Mapping[str, Any]) -> list[str]:
    return sorted(str(item) for item in ((scope_report.get("scope") or {}).get("parser_versions") or []) if str(item))


def append_labeled(parts: list[str], label: str, raw_value: Any) -> None:
    text = clean(raw_value)
    if text:
        parts.append(f"{label}: {text}")


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


def value(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def first_non_blank(*items: Any) -> str | None:
    for item in items:
        text = clean(item)
        if text:
            return text
    return None


def clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return clean(value).lower() in {"true", "1", "yes", "y"}


def preview(value: Any, limit: int = 240) -> str:
    text = clean(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope-report", default=str(DEFAULT_SCOPE_REPORT))
    parser.add_argument("--output", "--report", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--db-dsn", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--sample-limit", type=int, default=25)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
