"""Validate Track B R3 namu-v4 TEXT gold bindings against v4 corpus files."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_text_namu_v4_v0.csv")
DEFAULT_CORPUS_DIR = Path("ai-worker/eval/corpora/namu-v4-structured-combined")
DEFAULT_REPORT = Path("eval/reports/rag-ingestion/rag_text_namu_v4_gold_validate_report.json")
EXPECTED_SOURCE_DATASET = (
    "eval/reports/phase7/seeds/gold_seed_50_manual_curated/gold_seed_50_candidates.jsonl"
)
DEFAULT_EXPECTED_ROW_COUNT = 50
DEFAULT_EXPECTED_POSITIVE_ROW_COUNT = 47
DEFAULT_EXPECTED_NEEDS_REVIEW_ROW_COUNT = 3

REQUIRED_COLUMNS = [
    "query_id",
    "bucket",
    "query",
    "expected_page_ids",
    "expected_section_ids",
    "expected_chunk_ids",
    "expected_answer_summary",
    "must_contain_terms",
    "must_not_contain_terms",
    "allowed_abstain",
    "answer_type",
    "label_status",
    "source_dataset",
    "notes",
]

VALID_LABEL_STATUSES = {"bound", "needs_review"}
VALID_BOOL_VALUES = {"true", "false"}
POSITIVE_DENOMINATOR_LABEL_STATUSES = {"bound"}


@dataclass
class ValidationResult:
    ok: bool
    row_count: int
    positive_row_count: int
    needs_review_row_count: int
    abstain_or_review_row_count: int
    bucket_counts: dict[str, int]
    label_status_counts: dict[str, int]
    missing_required_columns: list[str]
    duplicate_query_ids: list[str]
    row_errors: dict[str, list[str]]
    row_warnings: dict[str, list[str]]
    missing_page_ids: list[str]
    missing_chunk_ids: list[str]
    missing_section_ids: list[str]
    source_dataset_counts: dict[str, int]
    allowed_abstain_true_count: int
    section_path_mismatch_count: int


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows, columns = read_csv(Path(args.gold))
    pages = load_pages(Path(args.corpus_dir) / "pages_v4.jsonl")
    chunks = load_rag_chunks(Path(args.corpus_dir) / "rag_chunks.jsonl")
    validation = validate_rows(rows, columns=columns, pages=pages, chunks=chunks, min_rows=args.min_rows)
    report = build_report(
        gold=Path(args.gold),
        corpus_dir=Path(args.corpus_dir),
        validation=validation,
        min_rows=args.min_rows,
        expected_row_count=args.expected_row_count,
        expected_positive_row_count=args.expected_positive_row_count,
        expected_needs_review_row_count=args.expected_needs_review_row_count,
    )
    write_json(Path(args.report), report)
    print_json({
        "status": report["status"],
        "row_count": validation.row_count,
        "positive_row_count": validation.positive_row_count,
        "needs_review_row_count": validation.needs_review_row_count,
        "report": str(Path(args.report)),
    })
    return 0 if report["status"] == "PASSED" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--corpus-dir", default=str(DEFAULT_CORPUS_DIR))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--min-rows", type=int, default=10)
    parser.add_argument("--expected-row-count", type=int, default=DEFAULT_EXPECTED_ROW_COUNT)
    parser.add_argument("--expected-positive-row-count", type=int, default=DEFAULT_EXPECTED_POSITIVE_ROW_COUNT)
    parser.add_argument(
        "--expected-needs-review-row-count",
        type=int,
        default=DEFAULT_EXPECTED_NEEDS_REVIEW_ROW_COUNT,
    )
    return parser.parse_args(argv)


def validate_rows(
    rows: list[dict[str, str]],
    *,
    columns: list[str],
    pages: Mapping[str, Mapping[str, Any]],
    chunks: Mapping[str, Mapping[str, Any]],
    min_rows: int = 10,
) -> ValidationResult:
    missing_required_columns = [column for column in REQUIRED_COLUMNS if column not in columns]
    row_errors: dict[str, list[str]] = defaultdict(list)
    row_warnings: dict[str, list[str]] = defaultdict(list)
    query_ids = [clean(row.get("query_id")) for row in rows]
    duplicate_query_ids = sorted(query_id for query_id, count in Counter(query_ids).items() if query_id and count > 1)
    missing_page_ids: list[str] = []
    missing_chunk_ids: list[str] = []
    missing_section_ids: list[str] = []
    section_path_mismatch_count = 0

    if len(rows) < min_rows:
        row_errors["__dataset__"].append(f"row_count must be >= {min_rows}")
    if missing_required_columns:
        row_errors["__dataset__"].append("missing required columns: " + ", ".join(missing_required_columns))
    for query_id in duplicate_query_ids:
        row_errors[query_id].append("duplicate query_id")

    for index, row in enumerate(rows, start=2):
        query_id = clean(row.get("query_id")) or f"<row:{index}>"
        query = clean(row.get("query"))
        label_status = clean(row.get("label_status")).lower()
        allowed_abstain = clean(row.get("allowed_abstain")).lower()
        expected_page_ids = split_ids(row.get("expected_page_ids"))
        expected_section_ids = split_ids(row.get("expected_section_ids"))
        expected_chunk_ids = split_ids(row.get("expected_chunk_ids"))
        expected_section_path = expected_section_path_from_notes(row.get("notes"))
        positive = label_status in POSITIVE_DENOMINATOR_LABEL_STATUSES and allowed_abstain == "false"

        if not clean(row.get("query_id")):
            row_errors[query_id].append("query_id is required")
        if not clean(row.get("bucket")):
            row_errors[query_id].append("bucket is required")
        if not query:
            row_errors[query_id].append("query is required")
        if label_status not in VALID_LABEL_STATUSES:
            row_errors[query_id].append("label_status must be bound or needs_review")
        if allowed_abstain not in VALID_BOOL_VALUES:
            row_errors[query_id].append("allowed_abstain must be true or false")
        if positive and not (expected_page_ids or expected_chunk_ids):
            row_errors[query_id].append("positive row requires expected_page_ids or expected_chunk_ids")
        if positive and not clean(row.get("expected_answer_summary")):
            row_errors[query_id].append("positive row requires expected_answer_summary")
        if label_status == "needs_review":
            row_warnings[query_id].append("needs_review row is excluded from positive retrieval denominator")

        for page_id in expected_page_ids:
            if page_id not in pages:
                missing_page_ids.append(page_id)
                row_errors[query_id].append(f"expected_page_id not found in pages_v4: {page_id}")
        for chunk_id in expected_chunk_ids:
            chunk = chunks.get(chunk_id)
            if chunk is None:
                missing_chunk_ids.append(chunk_id)
                row_errors[query_id].append(f"expected_chunk_id not found in rag_chunks: {chunk_id}")
                continue
            chunk_doc_id = clean(chunk.get("doc_id") or chunk.get("page_id"))
            if expected_page_ids and chunk_doc_id not in expected_page_ids:
                row_errors[query_id].append(
                    f"chunk {chunk_id} doc_id={chunk_doc_id} outside expected_page_ids={expected_page_ids}"
                )
            if is_empty(chunk.get("chunk_text")):
                row_errors[query_id].append(f"chunk {chunk_id} has empty chunk_text")
            if expected_section_path:
                chunk_section_path = as_path_list(chunk.get("section_path"))
                if chunk_section_path != expected_section_path:
                    section_path_mismatch_count += 1
                    row_errors[query_id].append(
                        "chunk "
                        f"{chunk_id} section_path={chunk_section_path} "
                        f"does not match expected_section_path={expected_section_path}"
                    )
        if expected_section_ids:
            chunk_section_ids = {
                clean(chunks[chunk_id].get("section_id"))
                for chunk_id in expected_chunk_ids
                if chunk_id in chunks
            }
            page_section_ids = section_ids_for_pages(expected_page_ids, pages)
            unresolved_sections = sorted(
                section_id for section_id in expected_section_ids if section_id not in chunk_section_ids
            )
            unresolved_page_sections = sorted(
                section_id for section_id in expected_section_ids if section_id not in page_section_ids
            )
            for section_id in unresolved_sections:
                missing_section_ids.append(section_id)
                row_errors[query_id].append(f"expected_section_id not found on expected chunks: {section_id}")
            for section_id in unresolved_page_sections:
                missing_section_ids.append(section_id)
                row_errors[query_id].append(f"expected_section_id not found under expected pages: {section_id}")

    bucket_counts = dict(sorted(Counter(clean(row.get("bucket")) or "unknown" for row in rows).items()))
    label_status_counts = dict(sorted(Counter(clean(row.get("label_status")).lower() or "unknown" for row in rows).items()))
    source_dataset_counts = dict(
        sorted(
            Counter(
                normalise_path_text(clean(row.get("source_dataset"))) or "unknown"
                for row in rows
            ).items()
        )
    )
    positive_row_count = sum(
        1
        for row in rows
        if clean(row.get("label_status")).lower() in POSITIVE_DENOMINATOR_LABEL_STATUSES
        and clean(row.get("allowed_abstain")).lower() == "false"
    )
    needs_review_row_count = label_status_counts.get("needs_review", 0)
    allowed_abstain_true_count = sum(
        1 for row in rows if clean(row.get("allowed_abstain")).lower() == "true"
    )
    abstain_or_review_row_count = sum(
        1
        for row in rows
        if clean(row.get("label_status")).lower() == "needs_review"
        or clean(row.get("allowed_abstain")).lower() == "true"
    )

    return ValidationResult(
        ok=not row_errors,
        row_count=len(rows),
        positive_row_count=positive_row_count,
        needs_review_row_count=needs_review_row_count,
        abstain_or_review_row_count=abstain_or_review_row_count,
        bucket_counts=bucket_counts,
        label_status_counts=label_status_counts,
        missing_required_columns=missing_required_columns,
        duplicate_query_ids=duplicate_query_ids,
        row_errors=dict(row_errors),
        row_warnings=dict(row_warnings),
        missing_page_ids=sorted(set(missing_page_ids)),
        missing_chunk_ids=sorted(set(missing_chunk_ids)),
        missing_section_ids=sorted(set(missing_section_ids)),
        source_dataset_counts=source_dataset_counts,
        allowed_abstain_true_count=allowed_abstain_true_count,
        section_path_mismatch_count=section_path_mismatch_count,
    )


def build_report(
    *,
    gold: Path,
    corpus_dir: Path,
    validation: ValidationResult,
    min_rows: int,
    expected_row_count: int | None = DEFAULT_EXPECTED_ROW_COUNT,
    expected_positive_row_count: int | None = DEFAULT_EXPECTED_POSITIVE_ROW_COUNT,
    expected_needs_review_row_count: int | None = DEFAULT_EXPECTED_NEEDS_REVIEW_ROW_COUNT,
) -> dict[str, Any]:
    done_criteria = {
        "row_count_at_least_min": validation.row_count >= min_rows,
        "current_seed_row_count_matches_expected": (
            expected_row_count is None or validation.row_count == expected_row_count
        ),
        "current_seed_positive_row_count_matches_expected": (
            expected_positive_row_count is None
            or validation.positive_row_count == expected_positive_row_count
        ),
        "current_seed_needs_review_row_count_matches_expected": (
            expected_needs_review_row_count is None
            or validation.needs_review_row_count == expected_needs_review_row_count
        ),
        "required_columns_exist": not validation.missing_required_columns,
        "query_id_unique": not validation.duplicate_query_ids,
        "source_dataset_is_manual_curated_seed": validation.source_dataset_counts
        == {EXPECTED_SOURCE_DATASET: validation.row_count},
        "all_allowed_abstain_false": validation.allowed_abstain_true_count == 0,
        "positive_rows_have_bindings": not any(
            "positive row requires expected_page_ids or expected_chunk_ids" in error
            for errors in validation.row_errors.values()
            for error in errors
        ),
        "all_expected_page_ids_resolve": not validation.missing_page_ids,
        "all_expected_chunk_ids_resolve": not validation.missing_chunk_ids,
        "all_expected_section_ids_resolve": not validation.missing_section_ids,
        "section_path_mismatch_is_blocker": validation.section_path_mismatch_count == 0,
        "needs_review_rows_excluded_from_positive_denominator": True,
        "promotion_evidence_false": True,
    }
    ok = validation.ok and all(done_criteria.values())
    failed_done_criteria = [key for key, value in done_criteria.items() if not value]
    row_error_blockers = [error for errors in validation.row_errors.values() for error in errors]
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "schema_version": "rag_text_namu_v4_gold_validate_v1",
        "status": "PASSED" if ok else "FAILED",
        "report_role": "rag_text_namu_v4_gold_validation",
        "scope": "track_b_text_retrieval_e2e",
        "phase": "R3",
        "gold": normalise_path(gold),
        "corpus_dir": normalise_path(corpus_dir),
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "validation": {
            "ok": ok,
            "row_count": validation.row_count,
            "positive_row_count": validation.positive_row_count,
            "needs_review_row_count": validation.needs_review_row_count,
            "abstain_or_review_row_count": validation.abstain_or_review_row_count,
            "bucket_counts": validation.bucket_counts,
            "label_status_counts": validation.label_status_counts,
            "missing_required_columns": validation.missing_required_columns,
            "duplicate_query_ids": validation.duplicate_query_ids,
            "missing_page_ids": validation.missing_page_ids,
            "missing_chunk_ids": validation.missing_chunk_ids,
            "missing_section_ids": validation.missing_section_ids,
            "source_dataset_counts": validation.source_dataset_counts,
            "allowed_abstain_true_count": validation.allowed_abstain_true_count,
            "section_path_mismatch_count": validation.section_path_mismatch_count,
            "row_errors": validation.row_errors,
            "row_warnings": validation.row_warnings,
        },
        "current_seed_policy": {
            "expected_source_dataset": EXPECTED_SOURCE_DATASET,
            "expected_row_count": expected_row_count,
            "expected_positive_row_count": expected_positive_row_count,
            "expected_needs_review_row_count": expected_needs_review_row_count,
            "allowed_abstain_true_count": validation.allowed_abstain_true_count,
            "fabricated_abstain_row_count": validation.allowed_abstain_true_count,
            "section_path_mismatch_count": validation.section_path_mismatch_count,
        },
        "positive_denominator_policy": {
            "include_label_status": ["bound"],
            "exclude_label_status": ["needs_review"],
            "exclude_allowed_abstain_true": True,
            "positive_row_count": validation.positive_row_count,
            "needs_review_row_count": validation.needs_review_row_count,
            "abstain_or_review_row_count": validation.abstain_or_review_row_count,
            "allowed_abstain_true_count": validation.allowed_abstain_true_count,
        },
        "done_criteria": done_criteria,
        "failed_done_criteria": failed_done_criteria,
        "blockers": [
            *row_error_blockers,
            *(f"done_criteria failed: {key}" for key in failed_done_criteria),
        ],
        "warnings": [
            "R3 validates gold binding only; it does not run retrieval, indexing, answer generation, or citation scoring.",
            "Rows with label_status=needs_review or allowed_abstain=true are excluded from positive retrieval denominators.",
        ],
        "next_phase_recommendation": (
            "Proceed to R4 retrieval emit inventory."
            if ok
            else "Keep R4 blocked until R3 gold binding validation passes."
        ),
    }


def load_pages(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for record in iter_jsonl_objects(path):
        page_id = clean(record.get("page_id"))
        if page_id:
            out[page_id] = dict(record)
    return out


def load_rag_chunks(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for record in iter_jsonl_objects(path):
        chunk_id = clean(record.get("chunk_id"))
        if chunk_id:
            out[chunk_id] = dict(record)
    return out


def section_ids_for_pages(
    page_ids: Iterable[str],
    pages: Mapping[str, Mapping[str, Any]],
) -> set[str]:
    out: set[str] = set()
    for page_id in page_ids:
        page = pages.get(page_id)
        if page is None:
            continue
        for section in page.get("sections") or []:
            if isinstance(section, Mapping):
                section_id = clean(section.get("section_id"))
                if section_id:
                    out.add(section_id)
    return out


def iter_jsonl_objects(path: Path) -> Iterable[Mapping[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: invalid JSON on line {line_no}: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}: line {line_no} must be an object")
            yield record


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def split_ids(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def expected_section_path_from_notes(value: str | None) -> list[str]:
    for part in (value or "").split(";"):
        text = part.strip()
        if not text.startswith("expected_section_path="):
            continue
        section_path = text.split("=", 1)[1].strip()
        if not section_path:
            return []
        return [piece.strip() for piece in section_path.split(" > ") if piece.strip()]
    return []


def as_path_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, list):
                return [clean(item) for item in decoded if clean(item)]
        return [part.strip() for part in text.split(" > ") if part.strip()]
    return [clean(value)] if clean(value) else []


def clean(value: Any) -> str:
    return str(value or "").strip()


def is_empty(value: Any) -> bool:
    return clean(value) == ""


def normalise_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def normalise_path_text(value: str) -> str:
    return value.replace("\\", "/")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    sys.exit(main())
