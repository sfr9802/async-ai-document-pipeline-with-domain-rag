"""Inventory supplemental elec/lh PDFs for diagnostic-only PDF experiments."""

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
    ROOT,
    SOURCE_DIRECTORIES,
    artifact_dir_for,
    artifact_identity,
    display_path,
    read_json,
    relative_to_root,
    resolve_path,
    run_id,
    sha256_file,
    source_for_path,
    sorted_counter,
    source_for_path,
    table_like_score,
    text_stats,
    utc_timestamp,
    write_csv,
    write_json,
)


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_elec_lh_inventory.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_elec_lh_inventory.csv"

CSV_FIELDS = [
    "dataset_source",
    "is_pdf",
    "relative_path",
    "absolute_path",
    "file_name",
    "sha256",
    "file_size_bytes",
    "page_count",
    "pymupdf_open_ok",
    "text_layer_present",
    "total_text_chars",
    "chars_per_page_min",
    "chars_per_page_median",
    "chars_per_page_max",
    "likely_native_text_pdf",
    "likely_table_centered_pdf",
    "likely_ocr_needed_pdf",
    "extraction_error",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id_value = args.run_id or run_id()
    artifact_dir = artifact_dir_for(run_id_value)
    manifest_path = artifact_dir / "supplemental_pdf_manifest.json"
    source_dirs = [resolve_path(item) for item in args.source_dir]
    json_report_path = resolve_path(args.report)
    csv_report_path = resolve_path(args.csv)

    payload = build_inventory(
        run_id_value=run_id_value,
        source_dirs=source_dirs,
        manifest_path=manifest_path,
        json_report_path=json_report_path,
        csv_report_path=csv_report_path,
    )
    write_json(json_report_path, payload["report"])
    write_csv(csv_report_path, payload["rows"], CSV_FIELDS)
    write_json(manifest_path, payload["manifest"])
    print(json.dumps({
        "status": payload["report"]["status"],
        "run_id": run_id_value,
        "json_report": display_path(json_report_path),
        "csv_report": display_path(csv_report_path),
        "manifest": display_path(manifest_path),
        "counts": payload["report"]["counts"],
    }, ensure_ascii=False, indent=2))
    return 0 if not payload["report"]["blockers"] else 2


def build_inventory(
    *,
    run_id_value: str,
    source_dirs: list[Path],
    manifest_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    pdf_manifest_rows: list[dict[str, Any]] = []
    non_pdf_rows: list[dict[str, Any]] = []
    missing_dirs = [path for path in source_dirs if not path.exists()]
    if missing_dirs:
        blockers.extend(f"source directory missing: {display_path(path)}" for path in missing_dirs)

    for source_dir in source_dirs:
        if not source_dir.exists():
            continue
        files = sorted([path for path in source_dir.rglob("*") if path.is_file()], key=lambda path: display_path(path).lower())
        if not files:
            warnings.append(f"source directory has no files: {display_path(source_dir)}")
        for path in files:
            row = inspect_file(path)
            rows.append(row)
            if row["is_pdf"]:
                pdf_manifest_rows.append(row)
            else:
                non_pdf_rows.append(row)
    if not pdf_manifest_rows:
        blockers.append("No PDF files found under supplemental source directories.")

    source_counts = Counter(row["dataset_source"] for row in pdf_manifest_rows)
    status = "PASS_WITH_WARNINGS" if warnings else "PASS"
    if blockers:
        status = "FAIL_CLOSED_NO_SUPPLEMENTAL_PDFS"
    report = {
        "schema_version": "pdf_supplemental_elec_lh_inventory_v1",
        "run_id": run_id_value,
        "generated_at": utc_timestamp(),
        "status": status,
        **COMMON_GUARDRAILS,
        "source_directories": SOURCE_DIRECTORIES,
        "artifact_dir": display_path(manifest_path.parent),
        "output_artifacts": {
            "json_report": display_path(json_report_path),
            "csv_report": display_path(csv_report_path),
            "supplemental_pdf_manifest": display_path(manifest_path),
        },
        "counts": {
            "file_count": len(rows),
            "pdf_count": len(pdf_manifest_rows),
            "non_pdf_count": len(non_pdf_rows),
            "pymupdf_open_ok_count": sum(1 for row in pdf_manifest_rows if row["pymupdf_open_ok"]),
            "text_layer_present_count": sum(1 for row in pdf_manifest_rows if row["text_layer_present"]),
            "native_text_pdf_count": sum(1 for row in pdf_manifest_rows if row["likely_native_text_pdf"]),
            "table_centered_pdf_count": sum(1 for row in pdf_manifest_rows if row["likely_table_centered_pdf"]),
            "ocr_needed_candidate_count": sum(1 for row in pdf_manifest_rows if row["likely_ocr_needed_pdf"]),
            "page_count_total": sum(int(row["page_count"] or 0) for row in pdf_manifest_rows),
            "dataset_source_pdf_counts": sorted_counter(source_counts),
        },
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "elec/lh PDFs are supplemental diagnostic inputs only, not Track C gold.",
            "No official denominator, C7 policy, promotion, DB, SearchUnit, or candidate artifact mutation is performed.",
        ],
    }
    manifest = {
        "schema_version": "pdf_supplemental_elec_lh_manifest_v1",
        "run_id": run_id_value,
        "generated_at": report["generated_at"],
        "status": status,
        **COMMON_GUARDRAILS,
        "source_directories": SOURCE_DIRECTORIES,
        "pdfs": pdf_manifest_rows,
        "non_pdf_files": non_pdf_rows,
        "counts": report["counts"],
        "blockers": blockers,
        "warnings": warnings,
    }
    return {"report": report, "manifest": manifest, "rows": rows}


def inspect_file(path: Path) -> dict[str, Any]:
    is_pdf = path.suffix.lower() == ".pdf"
    base = {
        "dataset_source": source_for_path(path),
        "is_pdf": is_pdf,
        "relative_path": relative_to_root(path),
        "absolute_path": str(path.resolve()),
        "file_name": path.name,
        "sha256": sha256_file(path),
        "file_size_bytes": path.stat().st_size,
        "page_count": None,
        "pymupdf_open_ok": False,
        "text_layer_present": False,
        "total_text_chars": 0,
        "chars_per_page_min": None,
        "chars_per_page_median": None,
        "chars_per_page_max": None,
        "likely_native_text_pdf": False,
        "likely_table_centered_pdf": False,
        "likely_ocr_needed_pdf": False,
        "extraction_error": None,
    }
    if not is_pdf:
        base["extraction_error"] = "non_pdf_file_excluded_from_pdf_canary"
        return base
    try:
        import fitz  # type: ignore

        document = fitz.open(str(path))
        try:
            page_text_lengths: list[int] = []
            page_table_scores: list[int] = []
            total_text = 0
            for page in document:
                text = page.get_text("text") or ""
                text_len = len(text.strip())
                page_text_lengths.append(text_len)
                total_text += text_len
                page_table_scores.append(int(table_like_score(text)["score"]))
            stats = text_stats(page_text_lengths)
            page_count = int(document.page_count)
            text_layer_present = total_text > 0
            base.update({
                "page_count": page_count,
                "pymupdf_open_ok": True,
                "text_layer_present": text_layer_present,
                "total_text_chars": total_text,
                "chars_per_page_min": stats["min"],
                "chars_per_page_median": stats["median"],
                "chars_per_page_max": stats["max"],
                "likely_native_text_pdf": bool(text_layer_present and (stats["median"] or 0) >= 80),
                "likely_table_centered_pdf": bool(text_layer_present and (max(page_table_scores or [0]) >= 3 or "요금표" in path.name)),
                "likely_ocr_needed_pdf": bool(page_count > 0 and total_text < max(100, page_count * 20)),
            })
        finally:
            document.close()
    except Exception as exc:  # pragma: no cover - depends on local PDF parser
        base["extraction_error"] = f"{type(exc).__name__}: {exc}"
        base["likely_ocr_needed_pdf"] = True
    return base


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--source-dir", action="append", default=SOURCE_DIRECTORIES)
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
