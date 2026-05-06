"""Run a file-based PyMuPDF parse canary for supplemental elec/lh PDFs."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from rag_pdf_supplemental_common import (
    COMMON_GUARDRAILS,
    REPORT_DIR,
    artifact_identity,
    display_path,
    latest_supplemental_artifact_dir,
    read_json,
    resolve_path,
    short_text,
    sorted_counter,
    table_like_score,
    utc_timestamp,
    write_csv,
    write_json,
    write_jsonl,
)


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_parse_canary_report.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_parse_canary.csv"

CSV_FIELDS = [
    "dataset_source",
    "relative_path",
    "file_name",
    "sha256",
    "parse_success",
    "page_count",
    "parsed_page_count",
    "block_count",
    "block_with_bbox_count",
    "table_like_block_candidate_count",
    "empty_text_page_count",
    "native_text_pdf",
    "table_centered_pdf",
    "ocr_required_candidate",
    "parse_error",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_path = resolve_manifest_path(args.manifest)
    manifest = read_json(manifest_path)
    artifact_dir = manifest_path.parent
    parsed_pages_path = resolve_artifact_path(args.parsed_pages, artifact_dir, default_name="parsed_pages.jsonl")
    parsed_blocks_path = resolve_artifact_path(args.parsed_blocks, artifact_dir, default_name="parsed_blocks.jsonl")
    json_report_path = resolve_path(args.report)
    csv_report_path = resolve_path(args.csv)

    payload = build_parse_canary(
        manifest=manifest,
        manifest_path=manifest_path,
        parsed_pages_path=parsed_pages_path,
        parsed_blocks_path=parsed_blocks_path,
        json_report_path=json_report_path,
        csv_report_path=csv_report_path,
    )
    write_jsonl(parsed_pages_path, payload["page_rows"])
    write_jsonl(parsed_blocks_path, payload["block_rows"])
    write_json(json_report_path, payload["report"])
    write_csv(csv_report_path, payload["csv_rows"], CSV_FIELDS)
    print(json.dumps({
        "status": payload["report"]["status"],
        "json_report": display_path(json_report_path),
        "csv_report": display_path(csv_report_path),
        "parsed_pages": display_path(parsed_pages_path),
        "parsed_blocks": display_path(parsed_blocks_path),
        "counts": payload["report"]["counts"],
        "blockers": payload["report"]["blockers"],
    }, ensure_ascii=False, indent=2))
    return 0 if not payload["report"]["blockers"] else 2


def build_parse_canary(
    *,
    manifest: Mapping[str, Any],
    manifest_path: Path,
    parsed_pages_path: Path,
    parsed_blocks_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if manifest.get("promotion_evidence") is not False:
        blockers.append("supplemental manifest must keep promotion_evidence=false")
    pdf_rows = [row for row in list(manifest.get("pdfs") or []) if isinstance(row, Mapping)]
    if not pdf_rows:
        blockers.append("supplemental manifest has no PDF rows")

    page_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    csv_rows: list[dict[str, Any]] = []
    source_counter: Counter[str] = Counter()
    for pdf_row in pdf_rows:
        result = parse_pdf_row(pdf_row)
        csv_rows.append(result["csv_row"])
        page_rows.extend(result["page_rows"])
        block_rows.extend(result["block_rows"])
        source_counter[str(pdf_row.get("dataset_source") or "unknown")] += 1

    counts = {
        "pdf_count": len(pdf_rows),
        "parse_success_count": sum(1 for row in csv_rows if row["parse_success"]),
        "parse_failure_count": sum(1 for row in csv_rows if not row["parse_success"]),
        "native_text_pdf_count": sum(1 for row in csv_rows if row["native_text_pdf"]),
        "table_centered_pdf_count": sum(1 for row in csv_rows if row["table_centered_pdf"]),
        "ocr_needed_candidate_count": sum(1 for row in csv_rows if row["ocr_required_candidate"]),
        "page_count_total": sum(int(row["parsed_page_count"] or 0) for row in csv_rows),
        "block_count_total": len(block_rows),
        "block_with_bbox_count": sum(1 for row in block_rows if row.get("bbox")),
        "table_like_block_candidate_count": sum(1 for row in block_rows if row.get("table_like_block_candidate")),
        "empty_text_page_count": sum(1 for row in page_rows if row.get("empty_text_page")),
        "dataset_source_pdf_counts": sorted_counter(source_counter),
    }
    status = "PASS"
    if blockers:
        status = "FAIL_CLOSED_INPUT_ERROR"
    elif counts["parse_failure_count"]:
        status = "PASS_WITH_PARSE_FAILURES"
    elif counts["ocr_needed_candidate_count"]:
        status = "PASS_WITH_OCR_NEEDED_CANDIDATES"
    report = {
        "schema_version": "pdf_supplemental_parse_canary_report_v1",
        "run_id": str(manifest.get("run_id") or ""),
        "generated_at": utc_timestamp(),
        "status": status,
        **COMMON_GUARDRAILS,
        "source_directories": manifest.get("source_directories") or [],
        "ocr_execution": "not_run_by_this_script",
        "parser_execution": "file_based_pymupdf_parse_only",
        "input_artifacts": [artifact_identity(manifest_path)],
        "output_artifacts": {
            "json_report": display_path(json_report_path),
            "csv_report": display_path(csv_report_path),
            "parsed_pages_jsonl": display_path(parsed_pages_path),
            "parsed_blocks_jsonl": display_path(parsed_blocks_path),
        },
        "counts": counts,
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "This canary parses files directly with PyMuPDF and does not import to DB.",
            "Table-like blocks are heuristic candidates only, not table semantics success.",
            "OCR-needed candidates are marked without executing OCR.",
        ],
    }
    return {
        "report": report,
        "csv_rows": csv_rows,
        "page_rows": page_rows,
        "block_rows": block_rows,
    }


def parse_pdf_row(pdf_row: Mapping[str, Any]) -> dict[str, Any]:
    path = resolve_path(str(pdf_row.get("relative_path") or pdf_row.get("absolute_path") or ""))
    page_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    csv_row = {
        "dataset_source": pdf_row.get("dataset_source"),
        "relative_path": pdf_row.get("relative_path"),
        "file_name": pdf_row.get("file_name"),
        "sha256": pdf_row.get("sha256"),
        "parse_success": False,
        "page_count": pdf_row.get("page_count"),
        "parsed_page_count": 0,
        "block_count": 0,
        "block_with_bbox_count": 0,
        "table_like_block_candidate_count": 0,
        "empty_text_page_count": 0,
        "native_text_pdf": False,
        "table_centered_pdf": False,
        "ocr_required_candidate": bool(pdf_row.get("likely_ocr_needed_pdf")),
        "parse_error": None,
    }
    try:
        import fitz  # type: ignore

        document = fitz.open(str(path))
        try:
            csv_row["parse_success"] = True
            csv_row["parsed_page_count"] = int(document.page_count)
            total_text_chars = 0
            table_like_count = 0
            block_with_bbox_count = 0
            for page_index, page in enumerate(document):
                page_no = page_index + 1
                page_text = page.get_text("text") or ""
                page_text_stripped = page_text.strip()
                total_text_chars += len(page_text_stripped)
                blocks = page.get_text("blocks") or []
                page_table_candidates = 0
                for block_index, block in enumerate(blocks):
                    block_row = build_block_row(pdf_row, page_no, page_index, block_index, block)
                    block_rows.append(block_row)
                    if block_row["bbox"]:
                        block_with_bbox_count += 1
                    if block_row["table_like_block_candidate"]:
                        table_like_count += 1
                        page_table_candidates += 1
                page_rows.append({
                    "schema_version": "pdf_supplemental_parsed_page_v1",
                    "dataset_source": pdf_row.get("dataset_source"),
                    "relative_path": pdf_row.get("relative_path"),
                    "file_name": pdf_row.get("file_name"),
                    "sha256": pdf_row.get("sha256"),
                    "page_no": page_no,
                    "physical_page_index": page_index,
                    "page_text": page_text,
                    "page_text_excerpt": short_text(page_text, 360),
                    "text_char_count": len(page_text_stripped),
                    "empty_text_page": len(page_text_stripped) == 0,
                    "block_count": len(blocks),
                    "table_like_block_candidate_count": page_table_candidates,
                    **COMMON_GUARDRAILS,
                })
            csv_row["block_count"] = len(block_rows)
            csv_row["block_with_bbox_count"] = block_with_bbox_count
            csv_row["table_like_block_candidate_count"] = table_like_count
            csv_row["empty_text_page_count"] = sum(1 for row in page_rows if row["empty_text_page"])
            csv_row["native_text_pdf"] = total_text_chars >= max(100, int(document.page_count) * 40)
            csv_row["table_centered_pdf"] = table_like_count >= max(2, int(document.page_count))
            csv_row["ocr_required_candidate"] = total_text_chars < max(100, int(document.page_count) * 20)
        finally:
            document.close()
    except Exception as exc:  # pragma: no cover - depends on local PDFs
        csv_row["parse_error"] = f"{type(exc).__name__}: {exc}"
        csv_row["ocr_required_candidate"] = True
    return {"csv_row": csv_row, "page_rows": page_rows, "block_rows": block_rows}


def build_block_row(
    pdf_row: Mapping[str, Any],
    page_no: int,
    page_index: int,
    block_index: int,
    block: Any,
) -> dict[str, Any]:
    values = list(block) if isinstance(block, (list, tuple)) else []
    bbox = [float(item) for item in values[:4]] if len(values) >= 4 else None
    text = str(values[4] if len(values) >= 5 else "")
    block_no = values[5] if len(values) >= 6 else block_index
    pymupdf_block_type = values[6] if len(values) >= 7 else None
    score = table_like_score(text, bbox)
    text_stripped = text.strip()
    return {
        "schema_version": "pdf_supplemental_parsed_block_v1",
        "dataset_source": pdf_row.get("dataset_source"),
        "relative_path": pdf_row.get("relative_path"),
        "file_name": pdf_row.get("file_name"),
        "sha256": pdf_row.get("sha256"),
        "page_no": page_no,
        "physical_page_index": page_index,
        "block_index": block_index,
        "pymupdf_block_no": block_no,
        "pymupdf_block_type": pymupdf_block_type,
        "block_type_candidate": "table_like" if score["is_table_like"] else "text",
        "bbox": bbox,
        "text": text,
        "text_excerpt": short_text(text, 360),
        "text_char_count": len(text_stripped),
        "empty_text_block": len(text_stripped) == 0,
        "table_like_block_candidate": score["is_table_like"],
        "table_like_score": score["score"],
        "table_like_reasons": score["reasons"],
        "table_like_numeric_token_ratio": score["numeric_token_ratio"],
        "table_like_line_numeric_ratio": score["line_numeric_ratio"],
        **COMMON_GUARDRAILS,
    }


def resolve_manifest_path(value: str | None) -> Path:
    if value:
        return resolve_path(value)
    return latest_supplemental_artifact_dir() / "supplemental_pdf_manifest.json"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--parsed-pages", default=None)
    parser.add_argument("--parsed-blocks", default=None)
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    args = parser.parse_args(argv)
    return args


def resolve_artifact_path(value: str | None, artifact_dir: Path, *, default_name: str | None = None) -> Path:
    if value:
        return resolve_path(value)
    if not default_name:
        raise ValueError("default_name is required")
    return (artifact_dir / default_name).resolve()


if __name__ == "__main__":
    sys.exit(main())
