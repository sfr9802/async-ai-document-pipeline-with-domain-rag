"""Build Track B R3 namu-v4 TEXT gold CSV from curated v4 seed candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent

DEFAULT_SOURCE = Path(
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "phase7" / "seeds"
    / "gold_seed_50_manual_curated" / "gold_seed_50_candidates.jsonl"
)
DEFAULT_CORPUS_DIR = AI_WORKER_ROOT / "eval" / "corpora" / "namu-v4-structured-combined"
DEFAULT_OUTPUT_CSV = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_text_namu_v4_v0.csv"
DEFAULT_REPORT = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_gold_build_report.json"

GOLD_FIELDNAMES = [
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

RISK_QUERY_TYPES = {"wrong_assumption", "ambiguous"}
POLICY_QUERY_TYPES = {"wrong_assumption", "ambiguous"}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    build = build_gold(
        source_path=Path(args.source),
        corpus_dir=Path(args.corpus_dir),
        output_csv=Path(args.output_csv),
    )
    write_csv(Path(args.output_csv), build["rows"])
    report = build["report"]
    report["dataset"]["sha256"] = sha256_file(Path(args.output_csv))
    write_json(Path(args.report), report)
    print_json({
        "status": report["status"],
        "row_count": report["row_count"],
        "positive_row_count": report["positive_row_count"],
        "needs_review_row_count": report["needs_review_row_count"],
        "output_csv": str(Path(args.output_csv)),
        "report": str(Path(args.report)),
    })
    return 0 if report["status"] == "COMPLETED" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--corpus-dir", default=str(DEFAULT_CORPUS_DIR))
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    return parser.parse_args(argv)


def build_gold(*, source_path: Path, corpus_dir: Path, output_csv: Path) -> dict[str, Any]:
    source_rows = read_jsonl(source_path)
    pages = load_pages(corpus_dir / "pages_v4.jsonl")
    chunks = load_rag_chunks(corpus_dir / "rag_chunks.jsonl")
    rows: list[dict[str, str]] = []
    row_errors: dict[str, list[str]] = defaultdict(list)
    row_warnings: dict[str, list[str]] = defaultdict(list)

    for index, source in enumerate(source_rows, start=1):
        row, errors, warnings = build_gold_row(
            source,
            source_path=source_path,
            pages=pages,
            chunks=chunks,
            ordinal=index,
        )
        rows.append(row)
        if errors:
            row_errors[row["query_id"]] = errors
        if warnings:
            row_warnings[row["query_id"]] = warnings

    query_ids = [row["query_id"] for row in rows]
    duplicate_query_ids = sorted(query_id for query_id, count in Counter(query_ids).items() if count > 1)
    for query_id in duplicate_query_ids:
        row_errors[query_id].append("duplicate query_id")

    label_counts = Counter(row["label_status"] for row in rows)
    bucket_counts = Counter(row["bucket"] for row in rows)
    query_type_counts = Counter(clean(source.get("query_type")) or "unknown" for source in source_rows)
    answerability_counts = Counter(clean(source.get("answerability")) or "unknown" for source in source_rows)
    status = "COMPLETED" if not row_errors else "FAILED"
    report = {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "schema_version": "rag_text_namu_v4_gold_build_v1",
        "status": status,
        "report_role": "rag_text_namu_v4_gold_build",
        "scope": "track_b_text_retrieval_e2e",
        "phase": "R3",
        "source_dataset": normalise_path(source_path),
        "corpus_dir": normalise_path(corpus_dir),
        "dataset": {
            "path": normalise_path(output_csv),
            "row_count": len(rows),
            "sha256": None,
        },
        "row_count": len(rows),
        "positive_row_count": sum(
            1 for row in rows if row["label_status"] == "bound" and row["allowed_abstain"] == "false"
        ),
        "needs_review_row_count": label_counts.get("needs_review", 0),
        "abstain_or_review_row_count": sum(
            1 for row in rows if row["label_status"] == "needs_review" or row["allowed_abstain"] == "true"
        ),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "label_status_counts": dict(sorted(label_counts.items())),
        "query_type_counts": dict(sorted(query_type_counts.items())),
        "answerability_counts": dict(sorted(answerability_counts.items())),
        "duplicate_query_ids": duplicate_query_ids,
        "row_errors": dict(row_errors),
        "row_warnings": dict(row_warnings),
        "binding_policy": {
            "positive_rows_require_expected_page_or_chunk": True,
            "expected_chunk_ids_resolve_in_rag_chunks": True,
            "chunk_doc_id_must_match_expected_page_ids": True,
            "needs_review_rows_excluded_from_positive_denominator": True,
            "current_seed_does_not_fabricate_abstain_rows": True,
            "expected_section_ids_resolve_in_pages_v4": True,
            "expected_section_path_matches_rag_chunk": True,
            "source_fixture": "rag_chunks.jsonl",
            "raw_context_field": "chunk_text",
        },
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "next_phase_recommendation": (
            "Run R3 validator; proceed to R4 only when validation status is PASSED."
            if status == "COMPLETED"
            else "Keep R4 blocked until build errors are resolved."
        ),
    }
    return {"rows": rows, "report": report}


def build_gold_row(
    source: Mapping[str, Any],
    *,
    source_path: Path,
    pages: Mapping[str, Mapping[str, Any]],
    chunks: Mapping[str, Mapping[str, Any]],
    ordinal: int,
) -> tuple[dict[str, str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    source_query_id = clean(source.get("source_query_id")) or clean(source.get("query_id"))
    query_id = clean(source.get("seed_id")) or f"gold_seed_{ordinal:04d}"
    query = clean(source.get("query"))
    query_type = clean(source.get("query_type"))
    answerability = clean(source.get("answerability"))
    expected_page_ids = as_list(source.get("expected_doc_ids")) or as_list(source.get("expected_doc_id"))
    expected_chunk_ids = as_list(source.get("expected_chunk_ids"))
    expected_section_path = as_list(source.get("expected_section_path"))
    expected_title = clean(source.get("expected_title"))

    label_status = "needs_review" if query_type in RISK_QUERY_TYPES or answerability != "answerable" else "bound"
    allowed_abstain = "false"
    bucket = bucket_for(query_type=query_type, label_status=label_status)
    answer_type = answer_type_for(query_type=query_type, label_status=label_status)

    for page_id in expected_page_ids:
        if page_id not in pages:
            errors.append(f"expected_page_id not found in pages_v4: {page_id}")
    section_ids: list[str] = []
    for chunk_id in expected_chunk_ids:
        chunk = chunks.get(chunk_id)
        if chunk is None:
            errors.append(f"expected_chunk_id not found in rag_chunks: {chunk_id}")
            continue
        chunk_doc_id = clean(chunk.get("doc_id") or chunk.get("page_id"))
        if expected_page_ids and chunk_doc_id not in expected_page_ids:
            errors.append(
                f"chunk {chunk_id} doc_id={chunk_doc_id} outside expected_page_ids={expected_page_ids}"
            )
        section_id = clean(chunk.get("section_id"))
        if section_id:
            section_ids.append(section_id)
            if expected_page_ids and not section_id_exists_in_pages(section_id, expected_page_ids, pages):
                errors.append(f"chunk {chunk_id} section_id={section_id} not found under expected pages")
        chunk_section_path = as_list(chunk.get("section_path"))
        if expected_section_path and chunk_section_path != expected_section_path:
            errors.append(
                "chunk "
                f"{chunk_id} section_path={chunk_section_path} "
                f"does not match expected_section_path={expected_section_path}"
            )
        if is_empty(chunk.get("chunk_text")):
            errors.append(f"chunk {chunk_id} has empty chunk_text")

    if label_status == "bound" and not (expected_page_ids or expected_chunk_ids):
        errors.append("positive row requires at least one expected_page_id or expected_chunk_id")
    if not query:
        errors.append("query is required")
    if label_status == "needs_review":
        warnings.append("needs_review row is excluded from positive retrieval denominator")

    notes = [
        f"source_query_id={source_query_id}" if source_query_id else "",
        f"query_type={query_type}" if query_type else "",
        f"difficulty={clean(source.get('difficulty'))}" if clean(source.get("difficulty")) else "",
        f"answerability={answerability}" if answerability else "",
        "manual_curated_seed_pending_human_label",
        f"expected_section_path={' > '.join(expected_section_path)}" if expected_section_path else "",
    ]
    must_terms = unique([expected_title, *expected_section_path])
    row = {
        "query_id": query_id,
        "bucket": bucket,
        "query": query,
        "expected_page_ids": join_ids(expected_page_ids),
        "expected_section_ids": join_ids(unique(section_ids)),
        "expected_chunk_ids": join_ids(expected_chunk_ids),
        "expected_answer_summary": clean(source.get("source_evidence")),
        "must_contain_terms": join_ids(must_terms),
        "must_not_contain_terms": "",
        "allowed_abstain": allowed_abstain,
        "answer_type": answer_type,
        "label_status": label_status,
        "source_dataset": normalise_path(source_path),
        "notes": "; ".join(part for part in notes if part),
    }
    return row, errors, warnings


def bucket_for(*, query_type: str, label_status: str) -> str:
    if query_type in POLICY_QUERY_TYPES:
        return "text_policy_question"
    if query_type in {"plot_memory", "theme_question", "vague_recall"}:
        return "text_multi_chunk_summary"
    if query_type in {"character_question", "setting_question"}:
        return "text_fact_lookup"
    if query_type in {"title_direct", "title_partial", "alias"}:
        return "text_fact_lookup"
    return "text_fact_lookup"


def answer_type_for(*, query_type: str, label_status: str) -> str:
    if label_status == "needs_review":
        return "claim_check"
    if query_type in {"plot_memory", "theme_question", "vague_recall"}:
        return "summary"
    return "short_fact"


def load_pages(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for record in iter_jsonl_objects(path):
        page_id = clean(record.get("page_id"))
        if page_id:
            out[page_id] = dict(record)
    return out


def section_id_exists_in_pages(
    section_id: str,
    page_ids: Iterable[str],
    pages: Mapping[str, Mapping[str, Any]],
) -> bool:
    for page_id in page_ids:
        page = pages.get(page_id)
        if page is None:
            continue
        for section in page.get("sections") or []:
            if isinstance(section, Mapping) and clean(section.get("section_id")) == section_id:
                return True
    return False


def load_rag_chunks(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for record in iter_jsonl_objects(path):
        chunk_id = clean(record.get("chunk_id"))
        if chunk_id:
            out[chunk_id] = dict(record)
    return out


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [dict(record) for record in iter_jsonl_objects(path)]


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


def write_csv(path: Path, rows: list[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GOLD_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def as_list(value: Any) -> list[str]:
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
        return [part.strip() for part in text.split(";") if part.strip()]
    return [clean(value)] if clean(value) else []


def join_ids(values: Iterable[str]) -> str:
    return ";".join(value for value in values if value)


def unique(values: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        value = clean(value)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def clean(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return " > ".join(clean(item) for item in value if clean(item)).strip()
    return str(value or "").strip()


def is_empty(value: Any) -> bool:
    return clean(value) == ""


def normalise_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    sys.exit(main())
