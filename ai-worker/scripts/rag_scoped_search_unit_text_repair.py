"""Repair scoped SearchUnit rows that are claim-blocked by missing text fields.

This is a narrowly scoped live-DB utility for candidate indexing canaries. It
does not create, delete, or globally rewrite SearchUnits. In apply mode it only
restores canonical citation/page embedding_text plus content_sha256 for rows
inside the supplied document_version_id/source_file_type/parser_version scope.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_v0.csv")
DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/scoped_search_unit_text_repair_report.json")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
DEFAULT_SOURCE_FILE_TYPES = ("SPREADSHEET", "PDF")
DEFAULT_PARSER_VERSIONS = ("xlsx-extract-v2-hidden-safe", "pdf-extract-v1", "pdf-extract-v2")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    warnings: list[str] = []
    docvs = load_scope_ids(args, warnings)
    db_dsn = args.db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN
    source_types = [item.upper() for item in args.source_file_type]
    parser_versions = list(args.parser_version)

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "documentVersionIds": docvs,
            "sourceFileTypes": source_types,
            "parserVersions": parser_versions,
            "apply": bool(args.apply),
        },
        "policy": {
            "global_delete": False,
            "repair_policy": (
                "for scoped rows only, restore missing embedding_text from "
                "source/citation/page metadata and set content_sha256 to "
                "sha256(embedding_text)"
            ),
        },
        "warnings": warnings,
        "before": {},
        "after": {},
        "samples": [],
    }

    if not docvs:
        report["status"] = "FAIL"
        report["blockers"] = ["document_version_id scope is required"]
        write_json(Path(args.output), report)
        return 2

    with connect(db_dsn) as conn:
        before = inspect_rows(conn, docvs, source_types, parser_versions)
        report["before"] = summarize(before)
        report["samples"] = [
            sample_for_report(row)
            for row in before[: min(len(before), args.sample_limit)]
        ]
        repairable = [row for row in before if build_repair(row).get("repairable")]
        report["repairable_count"] = len(repairable)

        applied_count = 0
        if args.apply and repairable:
            applied_count = apply_repairs(conn, repairable)
            conn.commit()

        after = inspect_rows(conn, docvs, source_types, parser_versions)
        report["after"] = summarize(after)
        report["applied_count"] = applied_count

    remaining = int(report["after"].get("missing_embedding_text_or_content_sha_count") or 0)
    report["status"] = "PASS" if remaining == 0 else "FAIL"
    report["blockers"] = [] if remaining == 0 else [
        "scoped rows still have missing embedding_text or content_sha256"
    ]
    write_json(Path(args.output), report)
    return 0 if report["status"] == "PASS" else 2


def inspect_rows(
    conn: Any,
    document_version_ids: list[str],
    source_file_types: list[str],
    parser_versions: list[str],
) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id,
                   document_version_id,
                   source_file_name,
                   source_file_type,
                   parser_version,
                   unit_type,
                   unit_key,
                   chunk_type,
                   title,
                   section_path,
                   page_start,
                   page_end,
                   text_content,
                   embedding_text,
                   content_sha256,
                   display_text,
                   citation_text,
                   location_json,
                   metadata_json,
                   embedding_status,
                   embedding_status_detail
              FROM search_unit
             WHERE document_version_id = ANY(%s)
               AND upper(source_file_type) = ANY(%s)
               AND parser_version = ANY(%s)
               AND (
                    embedding_text IS NULL
                    OR btrim(embedding_text) = ''
                    OR content_sha256 IS NULL
                    OR btrim(content_sha256) = ''
               )
             ORDER BY document_version_id, id
            """,
            (document_version_ids, source_file_types, parser_versions),
        )
        return [dict_from_cursor(cur, row) for row in cur.fetchall()]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_docv: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        docv = str(row.get("document_version_id") or "")
        by_docv[docv]["rows"] += 1
        if is_blank(row.get("embedding_text")):
            by_docv[docv]["missing_embedding_text"] += 1
        if is_blank(row.get("content_sha256")):
            by_docv[docv]["missing_content_sha256"] += 1
        if build_repair(row).get("repairable"):
            by_docv[docv]["repairable"] += 1
    return {
        "missing_embedding_text_or_content_sha_count": len(rows),
        "missing_embedding_text_count": sum(1 for row in rows if is_blank(row.get("embedding_text"))),
        "missing_content_sha256_count": sum(1 for row in rows if is_blank(row.get("content_sha256"))),
        "repairable_count": sum(1 for row in rows if build_repair(row).get("repairable")),
        "by_document_version_id": {
            docv: dict(counter)
            for docv, counter in sorted(by_docv.items())
        },
    }


def build_repair(row: dict[str, Any]) -> dict[str, Any]:
    citation_text = clean(row.get("citation_text"))
    location = parse_json(row.get("location_json"))
    metadata = parse_json(row.get("metadata_json"))
    if not citation_text:
        return {"repairable": False, "reason": "citation_text is blank"}
    if not isinstance(location, dict):
        return {"repairable": False, "reason": "location_json is not an object"}

    embedding_text = clean(row.get("embedding_text"))
    if not embedding_text:
        embedding_text = canonical_embedding_text(row, metadata, location, citation_text)
    if not embedding_text:
        return {"repairable": False, "reason": "canonical embedding_text is blank"}

    return {
        "repairable": True,
        "embedding_text": embedding_text,
        "content_sha256": sha256(embedding_text),
        "display_text": clean(row.get("display_text")) or citation_text,
    }


def canonical_embedding_text(
    row: dict[str, Any],
    metadata: dict[str, Any],
    location: dict[str, Any],
    citation_text: str,
) -> str:
    parts: list[str] = []
    append_labeled(parts, "Source", row.get("source_file_name"))
    append_labeled(parts, "Citation", citation_text)
    append_labeled(parts, "Chunk", row.get("chunk_type"))
    if str(location.get("type") or "").strip().lower() in {"xlsx", "spreadsheet"}:
        append_labeled(parts, "Sheet", first_value(metadata, "sheetName", "sheet_name"))
        append_labeled(parts, "Table", first_value(metadata, "tableName", "tableId", "table_name", "table_id"))
        append_labeled(parts, "Range", first_value(metadata, "cellRange", "range", "usedRange", "cell_range"))
        headers = metadata.get("headers") or metadata.get("header") or metadata.get("headerRow")
        append_labeled(parts, "Headers", header_text(headers))
    else:
        append_labeled(parts, "Page", first_non_blank(
            first_value(metadata, "pageLabel", "page_label"),
            first_value(location, "page_label"),
            first_value(metadata, "pageNo", "pageNumber", "page"),
            first_value(location, "page_no"),
            row.get("page_start"),
        ))
        append_labeled(parts, "Section", row.get("section_path"))
        append_labeled(parts, "Block", first_non_blank(
            first_value(metadata, "blockType", "block_type", "role"),
            first_value(location, "block_type"),
        ))
        if bool(metadata.get("ocrUsed") or metadata.get("ocr_used") or location.get("ocr_used")):
            append_labeled(parts, "OCR", "used")
            append_labeled(parts, "OCR confidence", first_non_blank(
                first_value(metadata, "ocrConfidence", "ocr_confidence", "confidence"),
                first_value(location, "ocr_confidence"),
            ))

    body = clean(row.get("text_content")) or clean(row.get("title"))
    if body:
        parts.append("Content:\n" + body)
    return "\n".join(parts).strip()


def apply_repairs(conn: Any, rows: list[dict[str, Any]]) -> int:
    applied = 0
    with conn.cursor() as cur:
        for row in rows:
            repair = build_repair(row)
            if not repair.get("repairable"):
                continue
            cur.execute(
                """
                UPDATE search_unit
                   SET embedding_text = %s,
                       content_sha256 = %s,
                       display_text = COALESCE(NULLIF(btrim(display_text), ''), %s),
                       embedding_status = 'PENDING',
                       embedding_status_detail = 'scoped text repair: canonical embedding_text restored',
                       embedding_claim_token = NULL,
                       embedding_claimed_at = NULL,
                       indexed_content_sha256 = NULL,
                       index_id = NULL,
                       index_version = NULL,
                       updated_at = now()
                 WHERE id = %s
                   AND (
                        embedding_text IS NULL
                        OR btrim(embedding_text) = ''
                        OR content_sha256 IS NULL
                        OR btrim(content_sha256) = ''
                   )
                """,
                (
                    repair["embedding_text"],
                    repair["content_sha256"],
                    repair["display_text"],
                    row["id"],
                ),
            )
            applied += cur.rowcount
    return applied


def sample_for_report(row: dict[str, Any]) -> dict[str, Any]:
    repair = build_repair(row)
    return {
        "search_unit_id": row.get("id"),
        "document_version_id": row.get("document_version_id"),
        "source_file_name": row.get("source_file_name"),
        "parser_version": row.get("parser_version"),
        "chunk_type": row.get("chunk_type"),
        "page_start": row.get("page_start"),
        "missing_embedding_text": is_blank(row.get("embedding_text")),
        "missing_content_sha256": is_blank(row.get("content_sha256")),
        "repairable": bool(repair.get("repairable")),
        "repair_reason": repair.get("reason"),
    }


def load_scope_ids(args: argparse.Namespace, warnings: list[str]) -> list[str]:
    ids: set[str] = set(args.document_version_id or [])
    gold = Path(args.gold)
    if gold.exists():
        with gold.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                docv = (row.get("expected_document_version_id") or "").strip()
                if docv:
                    ids.add(docv)
    else:
        warnings.append(f"gold file not found: {gold}")
    return sorted(ids)


def parse_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def dict_from_cursor(cur: Any, row: Any) -> dict[str, Any]:
    return {
        cur.description[index][0]: row[index]
        for index in range(len(cur.description))
    }


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_blank(value: Any) -> bool:
    return clean(value) == ""


def first_value(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = clean(mapping.get(key))
        if value:
            return value
    return ""


def first_non_blank(*values: Any) -> str:
    for value in values:
        text = clean(value)
        if text:
            return text
    return ""


def append_labeled(parts: list[str], label: str, value: Any) -> None:
    text = clean(value)
    if text:
        parts.append(f"{label}: {text}")


def header_text(value: Any) -> str:
    if isinstance(value, list):
        return " | ".join(clean(item) for item in value if clean(item))
    if isinstance(value, dict):
        return " | ".join(clean(item) for item in value.values() if clean(item))
    return clean(value)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def connect(dsn: str) -> Any:
    try:
        import psycopg2  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("psycopg2 is required for scoped SearchUnit text repair") from exc
    return psycopg2.connect(dsn)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--document-version-id", action="append", default=[])
    parser.add_argument("--source-file-type", action="append", default=list(DEFAULT_SOURCE_FILE_TYPES))
    parser.add_argument("--parser-version", action="append", default=list(DEFAULT_PARSER_VERSIONS))
    parser.add_argument("--db-dsn", default=os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--sample-limit", type=int, default=20)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
