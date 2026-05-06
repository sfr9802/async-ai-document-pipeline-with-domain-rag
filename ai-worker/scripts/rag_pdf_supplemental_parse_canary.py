"""Run a file-based PyMuPDF parse canary for supplemental elec/lh PDFs."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from rag_pdf_supplemental_common import (
    AI_WORKER,
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
    "ocr_fallback_attempted",
    "ocr_fallback_success",
    "ocr_fallback_unavailable",
    "ocr_used_page_count",
    "ocr_used_block_count",
    "ocr_engine",
    "ocr_confidence_avg",
    "ocr_warning_codes",
    "ocr_fallback_error",
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
        enable_existing_ocr_fallback=bool(args.enable_existing_ocr_fallback),
        ocr_lang=args.ocr_lang,
        ocr_pdf_dpi=args.ocr_pdf_dpi,
        max_ocr_pdfs=args.max_ocr_pdfs,
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
    enable_existing_ocr_fallback: bool = False,
    ocr_lang: str = "korean",
    ocr_pdf_dpi: int = 200,
    max_ocr_pdfs: int = 0,
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
    ocr_attempted = 0
    for pdf_row in pdf_rows:
        result = parse_pdf_row(
            pdf_row,
            enable_existing_ocr_fallback=enable_existing_ocr_fallback
            and (max_ocr_pdfs <= 0 or ocr_attempted < max_ocr_pdfs),
            ocr_lang=ocr_lang,
            ocr_pdf_dpi=ocr_pdf_dpi,
        )
        if result["csv_row"]["ocr_fallback_attempted"]:
            ocr_attempted += 1
        csv_rows.append(result["csv_row"])
        page_rows.extend(result["page_rows"])
        block_rows.extend(result["block_rows"])
        source_counter[str(pdf_row.get("dataset_source") or "unknown")] += 1

    ocr_confidences = [
        float(row["ocr_confidence"])
        for row in block_rows
        if row.get("ocr_used") and row.get("ocr_confidence") is not None
    ]
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
        "existing_ocr_fallback_enabled": enable_existing_ocr_fallback,
        "existing_ocr_fallback_attempted_count": sum(1 for row in csv_rows if row["ocr_fallback_attempted"]),
        "existing_ocr_fallback_success_count": sum(1 for row in csv_rows if row["ocr_fallback_success"]),
        "existing_ocr_fallback_unavailable_count": sum(1 for row in csv_rows if row["ocr_fallback_unavailable"]),
        "ocr_used_pdf_count": sum(1 for row in csv_rows if int(row["ocr_used_block_count"] or 0) > 0),
        "ocr_used_page_count": sum(1 for row in page_rows if row.get("ocr_used") is True),
        "ocr_used_block_count": sum(1 for row in block_rows if row.get("ocr_used") is True),
        "ocr_confidence_avg": round(sum(ocr_confidences) / len(ocr_confidences), 4) if ocr_confidences else None,
        "ocr_engine_counts": sorted_counter(Counter(str(row.get("ocr_engine") or "unknown") for row in block_rows if row.get("ocr_used"))),
        "dataset_source_pdf_counts": sorted_counter(source_counter),
    }
    status = "PASS"
    if blockers:
        status = "FAIL_CLOSED_INPUT_ERROR"
    elif counts["parse_failure_count"]:
        status = "PASS_WITH_PARSE_FAILURES"
    elif counts["existing_ocr_fallback_unavailable_count"]:
        status = "PASS_WITH_OCR_FALLBACK_WARNINGS"
    elif counts["ocr_needed_candidate_count"] and not enable_existing_ocr_fallback:
        status = "PASS_WITH_OCR_NEEDED_CANDIDATES"
    report = {
        "schema_version": "pdf_supplemental_parse_canary_report_v1",
        "run_id": str(manifest.get("run_id") or ""),
        "generated_at": utc_timestamp(),
        "status": status,
        **COMMON_GUARDRAILS,
        "source_directories": manifest.get("source_directories") or [],
        "ocr_execution": "existing_pdf_extract_service_ocr_fallback" if enable_existing_ocr_fallback else "not_run_by_this_script",
        "existing_ocr_module_used": bool(counts["ocr_used_block_count"]),
        "existing_ocr_module": "app.capabilities.pdf.service.PdfExtractService",
        "ocr_fallback_scope": "ocr_required_candidate_pages_only",
        "ocr_trust_policy": "lower_trust_diagnostic_only",
        "parser_execution": "file_based_pymupdf_parse_with_existing_ocr_fallback"
        if enable_existing_ocr_fallback else "file_based_pymupdf_parse_only",
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
            "Existing OCR fallback is lower-trust diagnostic evidence and is not gold, denominator, C7, promotion, DB, or SearchUnit evidence.",
        ],
    }
    return {
        "report": report,
        "csv_rows": csv_rows,
        "page_rows": page_rows,
        "block_rows": block_rows,
    }


def parse_pdf_row(
    pdf_row: Mapping[str, Any],
    *,
    enable_existing_ocr_fallback: bool = False,
    ocr_lang: str = "korean",
    ocr_pdf_dpi: int = 200,
) -> dict[str, Any]:
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
        "ocr_fallback_attempted": False,
        "ocr_fallback_success": False,
        "ocr_fallback_unavailable": False,
        "ocr_used_page_count": 0,
        "ocr_used_block_count": 0,
        "ocr_engine": "",
        "ocr_confidence_avg": None,
        "ocr_warning_codes": [],
        "ocr_fallback_error": None,
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
                    "ocr_used": False,
                    "ocr_engine": None,
                    "ocr_confidence_avg": None,
                    "lower_trust_ocr": False,
                    "parser_name": "pymupdf",
                    "parser_version": "pdf-extract-v1",
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
        if enable_existing_ocr_fallback and csv_row["ocr_required_candidate"]:
            csv_row["ocr_fallback_attempted"] = True
            try:
                payload = run_existing_pdf_ocr_fallback(
                    path,
                    pdf_row=pdf_row,
                    ocr_lang=ocr_lang,
                    ocr_pdf_dpi=ocr_pdf_dpi,
                )
                merge_existing_ocr_payload(
                    pdf_row=pdf_row,
                    payload=payload,
                    csv_row=csv_row,
                    page_rows=page_rows,
                    block_rows=block_rows,
                )
            except Exception as exc:  # pragma: no cover - depends on local OCR runtime
                csv_row["ocr_fallback_unavailable"] = True
                csv_row["ocr_fallback_error"] = f"{type(exc).__name__}: {exc}"
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
        "ocr_used": False,
        "ocr_engine": None,
        "ocr_confidence": None,
        "ocr_language": None,
        "lower_trust_ocr": False,
        **COMMON_GUARDRAILS,
    }


def run_existing_pdf_ocr_fallback(
    path: Path,
    *,
    pdf_row: Mapping[str, Any],
    ocr_lang: str,
    ocr_pdf_dpi: int,
) -> dict[str, Any]:
    if str(AI_WORKER) not in sys.path:
        sys.path.insert(0, str(AI_WORKER))
    from app.capabilities.base import CapabilityInput, CapabilityInputArtifact
    from app.capabilities.pdf.artifact_builder import PDF_PARSED_JSON
    from app.capabilities.pdf.service import PdfExtractCapability, PdfExtractService

    service = PdfExtractService(
        ocr_fallback_enabled=True,
        ocr_lang=ocr_lang,
        ocr_pdf_dpi=ocr_pdf_dpi,
    )
    capability = PdfExtractCapability(service=service)
    source_record_id = f"supplemental:{pdf_row.get('sha256') or pdf_row.get('relative_path')}"
    result = capability.run(
        CapabilityInput(
            job_id=f"supplemental-ocr-{pdf_row.get('sha256') or path.stem}",
            capability="PDF_EXTRACT",
            attempt_no=1,
            inputs=[
                CapabilityInputArtifact(
                    artifact_id=f"supplemental-input-{path.stem}",
                    source_file_id=source_record_id,
                    type="INPUT_FILE",
                    content=path.read_bytes(),
                    content_type="application/pdf",
                    filename=str(pdf_row.get("file_name") or path.name),
                )
            ],
        )
    )
    for artifact in result.outputs:
        if artifact.type == PDF_PARSED_JSON:
            payload = json.loads(artifact.content.decode("utf-8"))
            if isinstance(payload, dict):
                return payload
    raise RuntimeError("PDF_EXTRACT did not return PDF_PARSED_JSON")


def merge_existing_ocr_payload(
    *,
    pdf_row: Mapping[str, Any],
    payload: Mapping[str, Any],
    csv_row: dict[str, Any],
    page_rows: list[dict[str, Any]],
    block_rows: list[dict[str, Any]],
) -> None:
    page_by_no = {int(row.get("page_no") or 0): row for row in page_rows}
    warnings = [warning for warning in list(payload.get("warnings") or []) if isinstance(warning, Mapping)]
    warning_codes = sorted({str(warning.get("code") or "") for warning in warnings if warning.get("code")})
    ocr_blocks_added = 0
    ocr_pages_used = 0
    confidences: list[float] = []
    engines: Counter[str] = Counter()
    for page_payload in list(payload.get("pages") or []):
        if not isinstance(page_payload, Mapping):
            continue
        page_no = int(page_payload.get("page_no") or page_payload.get("pageNo") or 0)
        blocks = [block for block in list(page_payload.get("blocks") or []) if isinstance(block, Mapping)]
        page_text = "\n".join(str(block.get("text") or "") for block in blocks if str(block.get("text") or "").strip())
        ocr_page_used = bool(page_payload.get("ocr_used"))
        ocr_blocks = [block for block in blocks if block.get("ocr_used")]
        if ocr_page_used:
            ocr_pages_used += 1
        if page_no in page_by_no:
            page_row = page_by_no[page_no]
            page_row["page_text"] = page_text
            page_row["page_text_excerpt"] = short_text(page_text, 360)
            page_row["text_char_count"] = len(page_text.strip())
            page_row["empty_text_page"] = len(page_text.strip()) == 0
            page_row["block_count"] = len(blocks)
            page_row["ocr_used"] = ocr_page_used
            page_row["ocr_engine"] = page_payload.get("ocr_engine")
            page_row["ocr_confidence_avg"] = page_payload.get("ocr_confidence_avg")
            page_row["lower_trust_ocr"] = ocr_page_used
            page_row["parser_name"] = payload.get("parser_name")
            page_row["parser_version"] = payload.get("parser_version")
        for ocr_block in ocr_blocks:
            block_index = len([row for row in block_rows if int(row.get("page_no") or 0) == page_no])
            block_row = build_existing_ocr_block_row(pdf_row, page_no, page_no - 1, block_index, ocr_block)
            block_rows.append(block_row)
            ocr_blocks_added += 1
            if block_row["ocr_confidence"] is not None:
                confidences.append(float(block_row["ocr_confidence"]))
            if block_row["ocr_engine"]:
                engines[str(block_row["ocr_engine"])] += 1
    csv_row["ocr_fallback_success"] = ocr_blocks_added > 0
    csv_row["ocr_fallback_unavailable"] = bool(not ocr_blocks_added and any(code == "OCR_FALLBACK_UNAVAILABLE" for code in warning_codes))
    csv_row["ocr_used_page_count"] = ocr_pages_used
    csv_row["ocr_used_block_count"] = ocr_blocks_added
    csv_row["ocr_engine"] = ",".join(sorted(engines))
    csv_row["ocr_confidence_avg"] = round(sum(confidences) / len(confidences), 4) if confidences else None
    csv_row["ocr_warning_codes"] = warning_codes
    csv_row["block_count"] = len(block_rows)
    csv_row["block_with_bbox_count"] = sum(1 for row in block_rows if row.get("bbox"))
    csv_row["table_like_block_candidate_count"] = sum(1 for row in block_rows if row.get("table_like_block_candidate"))
    csv_row["empty_text_page_count"] = sum(1 for row in page_rows if row.get("empty_text_page"))
    if not csv_row["ocr_fallback_success"] and warning_codes and not csv_row["ocr_fallback_error"]:
        csv_row["ocr_fallback_error"] = ",".join(warning_codes)


def build_existing_ocr_block_row(
    pdf_row: Mapping[str, Any],
    page_no: int,
    page_index: int,
    block_index: int,
    block: Mapping[str, Any],
) -> dict[str, Any]:
    bbox = block.get("bbox") if isinstance(block.get("bbox"), list) else None
    if bbox is not None:
        bbox = [float(item) for item in bbox[:4]]
    text = str(block.get("text") or "")
    score = table_like_score(text, bbox)
    return {
        "schema_version": "pdf_supplemental_parsed_block_v1",
        "dataset_source": pdf_row.get("dataset_source"),
        "relative_path": pdf_row.get("relative_path"),
        "file_name": pdf_row.get("file_name"),
        "sha256": pdf_row.get("sha256"),
        "page_no": page_no,
        "physical_page_index": page_index,
        "block_index": block_index,
        "pymupdf_block_no": None,
        "pymupdf_block_type": None,
        "block_type_candidate": "ocr_table_like" if score["is_table_like"] else "ocr_text",
        "bbox": bbox,
        "text": text,
        "text_excerpt": short_text(text, 360),
        "text_char_count": len(text.strip()),
        "empty_text_block": len(text.strip()) == 0,
        "table_like_block_candidate": score["is_table_like"],
        "table_like_score": score["score"],
        "table_like_reasons": score["reasons"],
        "table_like_numeric_token_ratio": score["numeric_token_ratio"],
        "table_like_line_numeric_ratio": score["line_numeric_ratio"],
        "ocr_used": True,
        "ocr_engine": block.get("ocr_engine") or "paddleocr",
        "ocr_confidence": block.get("ocr_confidence"),
        "ocr_language": block.get("ocr_language"),
        "lower_trust_ocr": True,
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
    parser.add_argument("--enable-existing-ocr-fallback", action="store_true")
    parser.add_argument("--ocr-lang", default="korean")
    parser.add_argument("--ocr-pdf-dpi", type=int, default=200)
    parser.add_argument("--max-ocr-pdfs", type=int, default=0)
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
