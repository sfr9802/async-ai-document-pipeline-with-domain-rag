"""Validate Track B B1 TEXT E2E gold v0.

This validator is intentionally narrow. It checks the B1 diagnostic seed CSV
contract and, when possible, verifies that bound source/chunk ids still exist
as READY TEXT catalog rows in the local DB.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_text_e2e_v0.csv")
DEFAULT_REPORT = Path("eval/reports/rag-ingestion/rag_text_e2e_gold_validate_report.json")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"

REQUIRED_COLUMNS = [
    "query_id",
    "bucket",
    "query",
    "expected_answer_summary",
    "expected_source_ids",
    "expected_chunk_ids",
    "expected_citation_texts",
    "must_contain_terms",
    "must_not_contain_terms",
    "allowed_abstain",
    "answer_type",
    "difficulty",
    "label_status",
    "notes",
]

VALID_LABEL_STATUSES = {"draft", "bound"}
VALID_BOOL_VALUES = {"true", "false"}
TEXT_TYPES = {"TEXT", "TXT", "MARKDOWN", "MD"}


@dataclass
class ValidationResult:
    ok: bool
    row_count: int
    bucket_counts: dict[str, int]
    missing_required_columns: list[str]
    duplicate_query_ids: list[str]
    row_errors: dict[str, list[str]]
    row_warnings: dict[str, list[str]]
    non_abstain_missing_source_ids: list[str]
    bound_missing_chunk_or_citation_ids: list[str]
    abstain_true_count: int


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows, columns = read_csv(Path(args.gold))
    validation = validate_rows(rows, columns=columns, min_rows=args.min_rows)
    db_check = (
        {"status": "SCHEMA_ONLY", "reason": "skip_db requested; live binding was not verified"}
        if args.skip_db
        else validate_live_bindings(rows, args.db_dsn)
    )
    payload = build_report(
        gold=Path(args.gold),
        validation=validation,
        db_check=db_check,
        min_rows=args.min_rows,
    )
    write_json(Path(args.report), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["validation"]["ok"] else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--db-dsn", default=DEFAULT_DB_DSN)
    parser.add_argument("--min-rows", type=int, default=10)
    parser.add_argument("--skip-db", action="store_true")
    return parser.parse_args(argv)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def validate_rows(
    rows: list[dict[str, str]],
    *,
    columns: list[str],
    min_rows: int = 10,
) -> ValidationResult:
    missing_required = [column for column in REQUIRED_COLUMNS if column not in columns]
    row_errors: dict[str, list[str]] = defaultdict(list)
    row_warnings: dict[str, list[str]] = defaultdict(list)
    query_ids = [clean(row.get("query_id")) for row in rows]
    duplicate_query_ids = sorted(
        query_id for query_id, count in Counter(query_ids).items() if query_id and count > 1
    )
    non_abstain_missing_source_ids: list[str] = []
    bound_missing_chunk_or_citation_ids: list[str] = []
    abstain_true_count = 0

    if len(rows) < min_rows:
        row_errors["__dataset__"].append(f"row_count must be >= {min_rows}")
    if missing_required:
        row_errors["__dataset__"].append("missing required columns: " + ", ".join(missing_required))
    for duplicate in duplicate_query_ids:
        row_errors[duplicate].append("duplicate query_id")

    for index, row in enumerate(rows, start=2):
        query_id = clean(row.get("query_id")) or f"<row:{index}>"
        bucket = clean(row.get("bucket"))
        query = clean(row.get("query"))
        label_status = clean(row.get("label_status")).lower()
        allowed_abstain = clean(row.get("allowed_abstain")).lower()
        source_ids = split_semicolon(row.get("expected_source_ids"))
        chunk_ids = split_semicolon(row.get("expected_chunk_ids"))
        citation_texts = split_semicolon(row.get("expected_citation_texts"))

        if not clean(row.get("query_id")):
            row_errors[query_id].append("query_id is required")
        if not bucket:
            row_errors[query_id].append("bucket is required")
        if not query:
            row_errors[query_id].append("query is required")
        if label_status not in VALID_LABEL_STATUSES:
            row_errors[query_id].append("label_status must be draft or bound")
        if allowed_abstain not in VALID_BOOL_VALUES:
            row_errors[query_id].append("allowed_abstain must be true or false")

        is_abstain = allowed_abstain == "true"
        if is_abstain:
            abstain_true_count += 1
            if source_ids or chunk_ids:
                row_warnings[query_id].append("abstain row should usually not carry source/chunk bindings")
        else:
            if not source_ids:
                non_abstain_missing_source_ids.append(query_id)
                row_errors[query_id].append("expected_source_ids is required for non-abstain rows")
            if label_status == "bound" and not (chunk_ids or citation_texts):
                bound_missing_chunk_or_citation_ids.append(query_id)
                row_errors[query_id].append(
                    "bound non-abstain rows require expected_chunk_ids or expected_citation_texts"
                )

    bucket_counts = dict(sorted(Counter(clean(row.get("bucket")) or "unknown" for row in rows).items()))
    if bucket_counts.get("text_abstain_required", 0) == 0:
        row_errors["__dataset__"].append("text_abstain_required bucket is required")
    if abstain_true_count == 0:
        row_errors["__dataset__"].append("at least one allowed_abstain=true row is required")

    return ValidationResult(
        ok=not row_errors,
        row_count=len(rows),
        bucket_counts=bucket_counts,
        missing_required_columns=missing_required,
        duplicate_query_ids=duplicate_query_ids,
        row_errors=dict(row_errors),
        row_warnings=dict(row_warnings),
        non_abstain_missing_source_ids=non_abstain_missing_source_ids,
        bound_missing_chunk_or_citation_ids=bound_missing_chunk_or_citation_ids,
        abstain_true_count=abstain_true_count,
    )


def validate_live_bindings(rows: list[dict[str, str]], db_dsn: str) -> dict[str, Any]:
    try:
        import psycopg2  # type: ignore[import-not-found]
        import psycopg2.extras  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on local env
        return {"status": "ERROR", "error": f"psycopg2 import failed: {type(exc).__name__}: {exc}"}

    source_ids = sorted({item for row in rows for item in split_semicolon(row.get("expected_source_ids"))})
    chunk_ids = sorted({item for row in rows for item in split_semicolon(row.get("expected_chunk_ids"))})

    try:
        with psycopg2.connect(db_dsn, cursor_factory=psycopg2.extras.RealDictCursor) as conn:
            with conn.cursor() as cur:
                source_records = fetch_sources(cur, source_ids)
                chunk_records = fetch_chunks(cur, chunk_ids)
    except Exception as exc:  # pragma: no cover - depends on local DB state
        return {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}

    source_by_id = {row["id"]: dict(row) for row in source_records}
    chunk_by_id = {row["id"]: dict(row) for row in chunk_records}
    missing_sources = [item for item in source_ids if item not in source_by_id]
    missing_chunks = [item for item in chunk_ids if item not in chunk_by_id]
    non_ready_sources = [
        item for item, row in source_by_id.items() if str(row.get("status") or "").upper() != "READY"
    ]
    non_text_sources = [
        item for item, row in source_by_id.items() if str(row.get("file_type") or "").upper() not in TEXT_TYPES
    ]
    non_text_chunks = [
        item for item, row in chunk_by_id.items() if str(row.get("source_file_type") or "").upper() not in TEXT_TYPES
    ]
    non_ready_chunk_sources = [
        item for item, row in chunk_by_id.items() if str(row.get("source_status") or "").upper() != "READY"
    ]
    chunk_source_mismatches = row_level_chunk_source_mismatches(rows, chunk_by_id)

    blockers = [
        *[f"missing source id: {item}" for item in missing_sources],
        *[f"missing chunk id: {item}" for item in missing_chunks],
        *[f"source is not READY: {item}" for item in non_ready_sources],
        *[f"source is not TEXT-family: {item}" for item in non_text_sources],
        *[f"chunk is not TEXT-family: {item}" for item in non_text_chunks],
        *[f"chunk parent source is not READY: {item}" for item in non_ready_chunk_sources],
        *[
            "row chunk/source mismatch: "
            f"{row['query_id']} chunk {row['chunk_id']} belongs to {row['actual_source_file_id']} "
            f"outside expected_source_ids={row['expected_source_ids']}"
            for row in chunk_source_mismatches
        ],
    ]
    return {
        "status": "OK" if not blockers else "FAILED",
        "source_id_count": len(source_ids),
        "chunk_id_count": len(chunk_ids),
        "missing_source_ids": missing_sources,
        "missing_chunk_ids": missing_chunks,
        "non_ready_source_ids": non_ready_sources,
        "non_text_source_ids": non_text_sources,
        "non_text_chunk_ids": non_text_chunks,
        "non_ready_chunk_source_ids": non_ready_chunk_sources,
        "chunk_source_mismatches": chunk_source_mismatches,
        "blockers": blockers,
    }


def row_level_chunk_source_mismatches(
    rows: list[dict[str, str]],
    chunk_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for row in rows:
        query_id = clean(row.get("query_id")) or "<missing query_id>"
        expected_source_ids = split_semicolon(row.get("expected_source_ids"))
        if not expected_source_ids:
            continue
        for chunk_id in split_semicolon(row.get("expected_chunk_ids")):
            chunk = chunk_by_id.get(chunk_id)
            if not chunk:
                continue
            actual_source_file_id = str(chunk.get("source_file_id") or "")
            if actual_source_file_id not in expected_source_ids:
                mismatches.append({
                    "query_id": query_id,
                    "chunk_id": chunk_id,
                    "actual_source_file_id": actual_source_file_id,
                    "expected_source_ids": expected_source_ids,
                })
    return mismatches


def fetch_sources(cur: Any, source_ids: list[str]) -> list[dict[str, Any]]:
    if not source_ids:
        return []
    cur.execute(
        """
        SELECT id, original_file_name, file_type, status
          FROM source_file
         WHERE id = ANY(%s)
        """,
        (source_ids,),
    )
    return [dict(row) for row in cur.fetchall()]


def fetch_chunks(cur: Any, chunk_ids: list[str]) -> list[dict[str, Any]]:
    if not chunk_ids:
        return []
    cur.execute(
        """
        SELECT su.id,
               su.source_file_id,
               su.source_file_type,
               su.unit_type,
               su.unit_key,
               sf.status AS source_status
          FROM search_unit su
          JOIN source_file sf ON sf.id = su.source_file_id
         WHERE su.id = ANY(%s)
        """,
        (chunk_ids,),
    )
    return [dict(row) for row in cur.fetchall()]


def build_report(
    *,
    gold: Path,
    validation: ValidationResult,
    db_check: dict[str, Any],
    min_rows: int,
) -> dict[str, Any]:
    db_blockers = list(db_check.get("blockers") or []) if db_check.get("status") == "FAILED" else []
    db_errors = [db_check.get("error")] if db_check.get("status") == "ERROR" else []
    db_skipped = db_check.get("reason") if db_check.get("status") == "SCHEMA_ONLY" else None
    blockers = [
        *sum(validation.row_errors.values(), []),
        *db_blockers,
        *[str(error) for error in db_errors if error],
        *([str(db_skipped)] if db_skipped else []),
    ]
    schema_ok = validation.ok
    live_binding_ok = db_check.get("status") == "OK"
    done_criteria = {
        "row_count_at_least_min": validation.row_count >= min_rows,
        "required_columns_exist": not validation.missing_required_columns,
        "query_id_unique": not validation.duplicate_query_ids,
        "non_abstain_expected_source_ids_missing_count_zero": not validation.non_abstain_missing_source_ids,
        "abstain_required_bucket_exists": validation.bucket_counts.get("text_abstain_required", 0) > 0,
        "allowed_abstain_true_row_exists": validation.abstain_true_count > 0,
        "label_status_valid": not any(
            "label_status must be draft or bound" in error
            for errors in validation.row_errors.values()
            for error in errors
        ),
        "live_binding_check_passed": live_binding_ok,
    }
    ok = schema_ok and live_binding_ok and all(done_criteria.values())
    status = "PASSED" if ok else ("SCHEMA_ONLY" if schema_ok and db_check.get("status") == "SCHEMA_ONLY" else "FAILED")
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "schema_version": "rag_text_e2e_gold_validate_v1",
        "status": status,
        "report_role": "rag_text_e2e_gold_validation",
        "scope": "track_b_text_retrieval_e2e",
        "phase": "B1",
        "gold": str(gold).replace("\\", "/"),
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "validation": {
            "ok": ok,
            "schema_ok": schema_ok,
            "row_count": validation.row_count,
            "bucket_counts": validation.bucket_counts,
            "missing_required_columns": validation.missing_required_columns,
            "duplicate_query_ids": validation.duplicate_query_ids,
            "non_abstain_missing_source_ids": validation.non_abstain_missing_source_ids,
            "bound_missing_chunk_or_citation_ids": validation.bound_missing_chunk_or_citation_ids,
            "abstain_true_count": validation.abstain_true_count,
            "row_errors": validation.row_errors,
            "row_warnings": validation.row_warnings,
        },
        "live_binding_check": db_check,
        "done_criteria": done_criteria,
        "blockers": blockers,
        "warnings": [
            "B1 gold v0 is a diagnostic seed set, not a human-reviewed benchmark.",
            "library_search remains lexical diagnostic evidence and not vector promotion evidence.",
        ],
        "next_phase_recommendation": (
            "Proceed to B2 retrieval diagnostic with TEXT-only sourceFileTypes filters."
            if ok
            else "Keep B2 blocked until B1 gold validation passes."
        ),
    }


def split_semicolon(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def clean(value: str | None) -> str:
    return (value or "").strip()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
