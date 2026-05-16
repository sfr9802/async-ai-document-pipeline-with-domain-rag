"""Materialize PDF evidence context v2 from parsed native/OCR block artifacts.

This report-only script joins current PDF repair rows to their parsed PDF JSON
artifacts, recovers the actual matched block text plus nearby page-local block
body text, and extracts deterministic table rows/columns/values where the PDF
text layer contains a table-like block. It does not generate questions, compute
official metrics, mutate registries, or promote anything to gold.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(AI_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_WORKER_ROOT))

from app.capabilities.pdf.table_parser import extract_pdf_table_records  # noqa: E402
from rag_local_llm_expected_answer_generation_v1 import (  # noqa: E402
    clean,
    read_json,
    repo_relative,
    utc_timestamp,
    write_json,
)


REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
DEFAULT_REPAIR_REPORT = REPORT_DIR / "pdf_evidence_readiness_repair_report.json"
DEFAULT_METADATA_ENRICHMENT_REPORT = REPORT_DIR / "pdf_evidence_metadata_enrichment_report.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "pdf_evidence_context_v2_enrichment_report.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "pdf_evidence_context_v2_enrichment_report.md"
DEFAULT_LOCAL_STORAGE_ROOT = REPO_ROOT / "local-storage"

NUMERIC_RE = re.compile(r"^[△▲-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?$|^[△▲-]?\d+(?:\.\d+)?%?$")
PERIOD_RE = re.compile(r"^\d{4}(?:\.\s*(?:\d{1,2}|[ⅠⅡⅢⅣIVX]+))?$")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_enrichment(
        repair_report=Path(args.repair_report),
        metadata_enrichment_report=Path(args.metadata_enrichment_report),
        local_storage_root=Path(args.local_storage_root),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "context_rows": report["summary"]["context_rows"],
                "native_block_text_resolved_rows": report["summary"]["native_block_text_resolved_rows"],
                "deterministic_table_ready_rows": report["summary"]["deterministic_table_ready_rows"],
                "official_metric_input_rows": report["official_metric_input_rows"],
                "report": report["artifact_paths"]["report_json"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["validation"]["ok"] else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair-report", default=str(DEFAULT_REPAIR_REPORT))
    parser.add_argument("--metadata-enrichment-report", default=str(DEFAULT_METADATA_ENRICHMENT_REPORT))
    parser.add_argument("--local-storage-root", default=str(DEFAULT_LOCAL_STORAGE_ROOT))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_enrichment(
    *,
    repair_report: Path = DEFAULT_REPAIR_REPORT,
    metadata_enrichment_report: Path = DEFAULT_METADATA_ENRICHMENT_REPORT,
    local_storage_root: Path = DEFAULT_LOCAL_STORAGE_ROOT,
    output_report: Path = DEFAULT_OUTPUT_JSON,
    output_md: Path = DEFAULT_OUTPUT_MD,
) -> dict[str, Any]:
    repair_payload = read_json(repair_report)
    metadata_payload = read_json(metadata_enrichment_report)
    repair_rows = rows_from_payload(repair_payload, "repair_rows")
    metadata_rows = rows_from_payload(metadata_payload, "enriched_rows")
    metadata_lookup = {
        clean(row.get("query_id")): row for row in metadata_rows if clean(row.get("query_id"))
    }

    validation_errors = guardrail_errors(repair_payload, "repair_report")
    validation_errors.extend(guardrail_errors(metadata_payload, "metadata_enrichment_report"))
    artifact_cache: dict[str, Mapping[str, Any]] = {}
    context_rows: list[dict[str, Any]] = []
    for repair_row in repair_rows:
        row = merged_row(repair_row, metadata_lookup.get(clean(repair_row.get("query_id")), {}))
        context_row, errors = build_context_row(row, artifact_cache=artifact_cache, local_storage_root=local_storage_root)
        context_rows.append(context_row)
        validation_errors.extend(errors)

    gate_counts = Counter(clean(row.get("answerability_gate")) for row in context_rows)
    chunk_counts = Counter(clean(row.get("chunk_type")) for row in context_rows)
    table_counts = Counter(clean(nested(row, "table_context").get("table_status")) for row in context_rows)
    if validation_errors:
        status = "FAILED_GUARDRAIL"
    elif context_rows and all(row.get("candidate_for_answer_generation") is False for row in context_rows):
        status = "PDF_EVIDENCE_CONTEXT_V2_BLOCKED_BY_CONTEXT_GAPS"
    else:
        status = "PDF_EVIDENCE_CONTEXT_V2_READY_FOR_MANUAL_QUERY_AUTHORING"

    report = {
        "schema_version": "rag_pdf_evidence_context_v2_enrichment_report",
        "generated_at": utc_timestamp(),
        "status": status,
        "diagnostic_only": True,
        "report_only": True,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "official_denominator_registry_opened": False,
        "tuning_run_started": False,
        "gold_registry_mutated": False,
        "candidate_artifact_mutated": False,
        "production_vector_index_mutated": False,
        "source_artifacts": {
            "repair_report": repo_relative(repair_report),
            "metadata_enrichment_report": repo_relative(metadata_enrichment_report),
            "local_storage_root": repo_relative(local_storage_root),
        },
        "summary": {
            "repair_rows": len(repair_rows),
            "metadata_rows": len(metadata_rows),
            "context_rows": len(context_rows),
            "native_block_text_resolved_rows": sum(
                1
                for row in context_rows
                if nested(row, "text_context").get("text_source") == "native"
                and clean(nested(row, "text_context").get("native_block_text"))
            ),
            "nearby_block_text_resolved_rows": sum(
                1 for row in context_rows if row.get("nearby_blocks") and row.get("chunk_type") != "OCR_fragment"
            ),
            "ocr_fragment_rows": chunk_counts["OCR_fragment"],
            "deterministic_table_ready_rows": table_counts["deterministic_table_body"],
            "chart_or_table_label_without_body_rows": table_counts["chart_or_table_label_without_body"],
            "candidate_for_answer_generation_rows": sum(
                1 for row in context_rows if row.get("candidate_for_answer_generation") is True
            ),
            "answerability_gate_counts": dict(sorted(gate_counts.items())),
            "chunk_type_counts": dict(sorted(chunk_counts.items())),
            "table_status_counts": dict(sorted(table_counts.items())),
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
        },
        "context_rows": context_rows,
        "next_safe_actions": [
            "Use these source-bound block/table contexts for manually authored PDF question rewrites.",
            "Keep OCR line groups out of answer candidates until they are reassembled into complete blocks.",
            "Allow LLM phrasing only after deterministic table rows/columns/values are present.",
            "Do not treat this diagnostic report as gold, official denominator input, or promotion evidence.",
        ],
        "artifact_paths": {"report_json": repo_relative(output_report), "report_md": repo_relative(output_md)},
        "validation": {"ok": not validation_errors, "errors": validation_errors},
    }
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def rows_from_payload(payload: Mapping[str, Any], preferred_key: str) -> list[Mapping[str, Any]]:
    candidates = (
        payload.get(preferred_key),
        payload.get("enriched_rows"),
        payload.get("repair_rows"),
        payload.get("rows"),
        payload.get("context_rows"),
    )
    for value in candidates:
        if isinstance(value, list):
            return [row for row in value if isinstance(row, Mapping)]
    return []


def merged_row(repair_row: Mapping[str, Any], metadata_row: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(metadata_row)
    for key, value in repair_row.items():
        if value not in ("", None, [], {}):
            merged[key] = value
    if isinstance(repair_row.get("source_metadata"), Mapping) or isinstance(metadata_row.get("source_metadata"), Mapping):
        source_metadata = dict(metadata_row.get("source_metadata") or {})
        source_metadata.update(dict(repair_row.get("source_metadata") or {}))
        merged["source_metadata"] = source_metadata
    return merged


def build_context_row(
    row: Mapping[str, Any],
    *,
    artifact_cache: dict[str, Mapping[str, Any]],
    local_storage_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    query_id = clean(row.get("query_id"))
    source_metadata = row.get("source_metadata") if isinstance(row.get("source_metadata"), Mapping) else {}
    parsed_info = source_metadata.get("parsed_artifact") if isinstance(source_metadata.get("parsed_artifact"), Mapping) else {}
    storage_uri = clean(parsed_info.get("storage_uri"))
    parsed_artifact: Mapping[str, Any] = {}
    parsed_path: Path | None = None
    if storage_uri:
        try:
            parsed_path = resolve_local_storage_uri(storage_uri, local_storage_root)
            cache_key = str(parsed_path)
            if cache_key not in artifact_cache:
                artifact_cache[cache_key] = read_json(parsed_path)
            parsed_artifact = artifact_cache[cache_key]
        except Exception as exc:
            errors.append(f"{query_id}: {type(exc).__name__}: {exc}")
    else:
        errors.append(f"{query_id}: PARSED_ARTIFACT_STORAGE_URI_MISSING")

    page = find_page(parsed_artifact, row)
    matched_block, match_method = find_matched_block(page, row) if page else ({}, "page_missing")
    nearby = nearby_blocks(page, matched_block) if page and matched_block else []
    ocr = ocr_context(page, row) if page else empty_ocr_context(row)
    table_context = table_context_for(row, page, matched_block) if page and matched_block else empty_table_context()
    chunk_type = chunk_type_for(row, matched_block, table_context)
    native_text = clean(matched_block.get("text"))
    matched_text = clean(row.get("matched_text"))
    bridge = text_bridge_status(matched_text, native_text)
    gate, blockers = answerability_gate_for(
        row=row,
        chunk_type=chunk_type,
        table_context=table_context,
        ocr=ocr,
        native_text=native_text,
        text_bridge=bridge,
    )
    candidate = gate in {"EVIDENCE_TEXT_READY", "TABLE_PARSER_READY"}
    locator = locator_for(row, source_metadata, page, matched_block)
    context_row = {
        "schema_version": "pdf_evidence_context_v2_row",
        "query_id": query_id,
        "source_file_id": clean(row.get("source_file_id")),
        "document_version_id": clean(row.get("document_version_id") or parsed_artifact.get("document_version_id")),
        "search_unit_id": clean(row.get("search_unit_id")),
        "source_identity": source_identity_for(row, source_metadata, parsed_artifact, parsed_path),
        "locator": locator,
        "matched_block": matched_block_summary(matched_block, match_method),
        "matched_text": matched_text,
        "text_context": {
            "matched_text": matched_text,
            "native_block_text": native_text,
            "normalized_block_text": normalize(native_text),
            "text_source": text_source_for(row, matched_block, page),
            "text_bridge_status": bridge,
            "native_text_matches_matched_text": bridge in {"exact", "normalized_contains"},
        },
        "nearby_blocks": nearby,
        "ocr_context": ocr,
        "table_context": table_context,
        "chunk_type": chunk_type,
        "answerability_gate": gate,
        "answerability_blockers": blockers,
        "candidate_for_answer_generation": candidate,
        "manual_query_authoring_required": True,
        "human_review_required": True,
        "model_assisted_diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "official_denominator_current": False,
    }
    return context_row, errors


def resolve_local_storage_uri(uri: str, local_storage_root: Path) -> Path:
    if not uri.startswith("local://"):
        raise ValueError(f"LOCAL_STORAGE_URI_UNSUPPORTED: {uri}")
    raw = uri[len("local://") :].lstrip("/\\")
    parts = [part for part in re.split(r"[\\/]+", raw) if part and part != "."]
    candidate = local_storage_root.joinpath(*parts).resolve()
    root = local_storage_root.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"LOCAL_STORAGE_URI_ESCAPE: {uri}")
    return candidate


def find_page(parsed_artifact: Mapping[str, Any], row: Mapping[str, Any]) -> Mapping[str, Any]:
    pages = [page for page in parsed_artifact.get("pages") or [] if isinstance(page, Mapping)]
    page_no = int_or_none(row.get("page") or nested(row, "source_metadata").get("page_no"))
    physical = int_or_none(row.get("physical_page_index"))
    if physical is None:
        source_metadata = nested(row, "source_metadata")
        location = source_metadata.get("location_json") if isinstance(source_metadata.get("location_json"), Mapping) else {}
        physical = int_or_none(location.get("physical_page_index"))
    for page in pages:
        if page_no is not None and int_or_none(page.get("page_no")) == page_no:
            return page
    for page in pages:
        if physical is not None and int_or_none(page.get("physical_page_index")) == physical:
            return page
    return {}


def find_matched_block(page: Mapping[str, Any], row: Mapping[str, Any]) -> tuple[Mapping[str, Any], str]:
    blocks = sorted(
        [block for block in page.get("blocks") or [] if isinstance(block, Mapping)],
        key=lambda block: (int_or_none(block.get("reading_order")) or 0, clean(block.get("block_id"))),
    )
    row_bbox = parse_bbox(row.get("bbox"))
    if not row_bbox:
        source_metadata = nested(row, "source_metadata")
        location = source_metadata.get("location_json") if isinstance(source_metadata.get("location_json"), Mapping) else {}
        row_bbox = parse_bbox(location.get("bbox"))
    if row_bbox:
        for block in blocks:
            if bbox_close(row_bbox, parse_bbox(block.get("bbox"))):
                return block, "bbox_exact"
        overlaps = [(bbox_iou(row_bbox, parse_bbox(block.get("bbox"))), block) for block in blocks]
        overlaps = [(score, block) for score, block in overlaps if score > 0]
        if overlaps:
            score, block = max(overlaps, key=lambda item: item[0])
            if score >= 0.2:
                return block, "bbox_overlap"
    matched_text = normalize(clean(row.get("matched_text")))
    if matched_text:
        for block in blocks:
            block_text = normalize(clean(block.get("text")))
            if block_text and (matched_text == block_text or matched_text in block_text):
                return block, "text_contains"
    if row_bbox and blocks:
        return min(blocks, key=lambda block: bbox_distance(row_bbox, parse_bbox(block.get("bbox")))), "bbox_nearest"
    return ({}, "block_missing")


def nearby_blocks(page: Mapping[str, Any], matched_block: Mapping[str, Any], *, window: int = 3) -> list[dict[str, Any]]:
    blocks = sorted(
        [block for block in page.get("blocks") or [] if isinstance(block, Mapping)],
        key=lambda block: (int_or_none(block.get("reading_order")) or 0, clean(block.get("block_id"))),
    )
    target_order = int_or_none(matched_block.get("reading_order"))
    if target_order is None:
        return []
    by_order = {int_or_none(block.get("reading_order")): block for block in blocks}
    result: list[dict[str, Any]] = []
    for offset in range(1, window + 1):
        for order in (target_order - offset, target_order + offset):
            block = by_order.get(order)
            text = clean(block.get("text") if block else "")
            if not block or not text or is_ocr_block(block):
                continue
            result.append(block_summary(block))
    return result


def ocr_context(page: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    fragments = []
    for block in page.get("blocks") or []:
        if not isinstance(block, Mapping):
            continue
        if block.get("ocr_used") is True or clean(block.get("block_type")).startswith("ocr"):
            fragments.append(
                {
                    "block_id": clean(block.get("block_id")),
                    "text": clean(block.get("text")),
                    "bbox": parse_bbox(block.get("bbox")),
                    "reading_order": int_or_none(block.get("reading_order")),
                    "ocr_confidence": block.get("ocr_confidence"),
                }
            )
    ocr_used = page.get("ocr_used") is True or row.get("OCR_fallback_used") is True or bool(fragments)
    avg = page.get("ocr_confidence_avg") if page.get("ocr_confidence_avg") is not None else row.get("OCR_confidence")
    return {
        "ocr_used": ocr_used,
        "page_ocr_confidence_avg": avg,
        "ocr_fragments": fragments,
        "ocr_trust_label": ocr_trust_label(ocr_used=ocr_used, confidence=avg, fragments=fragments),
    }


def empty_ocr_context(row: Mapping[str, Any]) -> dict[str, Any]:
    ocr_used = row.get("OCR_fallback_used") is True
    return {
        "ocr_used": ocr_used,
        "page_ocr_confidence_avg": row.get("OCR_confidence"),
        "ocr_fragments": [],
        "ocr_trust_label": "OCR_FRAGMENT_MISSING" if ocr_used else "NATIVE_OR_UNKNOWN",
    }


def ocr_trust_label(*, ocr_used: bool, confidence: Any, fragments: list[Mapping[str, Any]]) -> str:
    if not ocr_used:
        return "NATIVE_TEXT_PRIMARY"
    try:
        numeric_confidence = float(confidence)
    except (TypeError, ValueError):
        numeric_confidence = None
    if not fragments:
        return "OCR_FRAGMENT_MISSING"
    if numeric_confidence is None or numeric_confidence < 0.8:
        return "LOW_TRUST_OCR_FRAGMENT"
    return "OCR_FALLBACK_FRAGMENT"


def table_context_for(row: Mapping[str, Any], page: Mapping[str, Any], matched_block: Mapping[str, Any]) -> dict[str, Any]:
    table_records = extract_pdf_table_records(
        [block for block in page.get("blocks") or [] if isinstance(block, Mapping)],
        page_no=int_or_none(page.get("page_no")) or int_or_none(row.get("page")) or 0,
        physical_page_index=int_or_none(page.get("physical_page_index")) or int_or_none(row.get("physical_page_index")) or 0,
        page_label=clean(page.get("page_label")),
    )
    table_record = relevant_table_record(table_records, matched_block)
    if table_record:
        return table_context_from_record(table_record)
    raw_text = table_raw_text(page, matched_block)
    parsed = parse_known_pdf_table(raw_text)
    if parsed["row_values"]:
        return {
            "table_status": "deterministic_table_body",
            "raw_table_text": raw_text,
            "headers": parsed["headers"],
            "rows": parsed["rows"],
            "row_values": parsed["row_values"],
            "cell_values": parsed["cell_values"],
            "structured_table_claim_allowed": True,
            "parser": parsed["parser"],
        }
    if table_label_like(clean(row.get("matched_text")) or clean(matched_block.get("text")) or raw_text):
        return {
            "table_status": "chart_or_table_label_without_body",
            "raw_table_text": raw_text,
            "headers": [],
            "rows": [],
            "row_values": [],
            "cell_values": [],
            "structured_table_claim_allowed": False,
            "parser": "no_deterministic_table_rows",
        }
    return empty_table_context(raw_text=raw_text)


def relevant_table_record(table_records: list[Mapping[str, Any]], matched_block: Mapping[str, Any]) -> Mapping[str, Any]:
    block_id = clean(matched_block.get("block_id"))
    if not table_records:
        return {}
    for record in table_records:
        header_ids = [
            clean(block.get("block_id"))
            for block in record.get("header_blocks") or []
            if isinstance(block, Mapping)
        ]
        source_ids = [clean(value) for value in record.get("source_block_ids") or []]
        if block_id and (block_id in source_ids or block_id in header_ids or block_id == clean(record.get("title_block_id"))):
            return record
    return {}


def table_context_from_record(record: Mapping[str, Any]) -> dict[str, Any]:
    row_values = []
    rows = []
    cell_values = []
    for row in record.get("row_records") or []:
        if not isinstance(row, Mapping):
            continue
        period = clean(row.get("row_label_normalized") or row.get("row_label_raw"))
        values: dict[str, str] = {}
        for cell in row.get("cells") or []:
            if not isinstance(cell, Mapping):
                continue
            column = clean(cell.get("column_path"))
            value = clean(cell.get("value_raw"))
            values[column] = value
            cell_values.append(
                {
                    "period": period,
                    "column": column,
                    "value": value,
                    "value_number": cell.get("value_number"),
                    "source_block_id": clean(cell.get("source_block_id")),
                    "bbox_granularity": clean(cell.get("bbox_granularity")),
                }
            )
        row_values.append({"period": period, **values})
        rows.append(
            {
                "period": period,
                "values": values,
                "row_bbox": row.get("row_bbox") or [],
                "source_block_ids": row.get("source_block_ids") or [],
                "bbox_granularity": clean(row.get("bbox_granularity")),
            }
        )
    raw_parts = [clean(record.get("title_text"))]
    raw_parts.extend(clean(block.get("text")) for block in record.get("header_blocks") or [] if isinstance(block, Mapping))
    return {
        "table_status": "deterministic_table_body",
        "raw_table_text": "\n".join(part for part in raw_parts if part),
        "headers": list(record.get("headers") or []),
        "rows": rows,
        "row_values": row_values,
        "cell_values": cell_values,
        "structured_table_claim_allowed": True,
        "parser": clean(record.get("parser_version")),
        "table_id": clean(record.get("table_id")),
        "table_type": clean(record.get("table_type")),
        "bbox_granularity": clean(record.get("bbox_granularity")),
        "table_bbox": record.get("table_bbox") or [],
        "source_block_ids": record.get("source_block_ids") or [],
    }


def empty_table_context(*, raw_text: str = "") -> dict[str, Any]:
    return {
        "table_status": "none",
        "raw_table_text": raw_text,
        "headers": [],
        "rows": [],
        "row_values": [],
        "cell_values": [],
        "structured_table_claim_allowed": False,
        "parser": "",
    }


def table_raw_text(page: Mapping[str, Any], matched_block: Mapping[str, Any]) -> str:
    blocks = sorted(
        [block for block in page.get("blocks") or [] if isinstance(block, Mapping)],
        key=lambda block: (int_or_none(block.get("reading_order")) or 0, clean(block.get("block_id"))),
    )
    target_order = int_or_none(matched_block.get("reading_order"))
    if target_order is None:
        return clean(matched_block.get("text"))
    table_like = table_label_like(clean(matched_block.get("text")))
    if table_like:
        selected = [
            clean(block.get("text"))
            for block in blocks
            if target_order <= (int_or_none(block.get("reading_order")) or -1) <= target_order + 14
        ]
    else:
        selected = [clean(matched_block.get("text"))]
    return "\n".join(text for text in selected if text)


def parse_known_pdf_table(raw_text: str) -> dict[str, Any]:
    lines = nonempty_lines(raw_text)
    normalized = normalize(raw_text)
    if "수출" in normalized and "수입" in normalized and "수출입차" in normalized:
        return parse_export_import_table(lines)
    if "주요국가의환율변동비교" in normalized or ("한국" in normalized and "유로" in normalized and "절상률" in normalized):
        return parse_currency_table(lines)
    return {"headers": [], "rows": [], "row_values": [], "cell_values": [], "parser": ""}


def parse_export_import_table(lines: list[str]) -> dict[str, Any]:
    headers = [
        "period",
        "수출(FOB) 금액",
        "수출(FOB) 증가율",
        "수입(CIF) 금액",
        "수입(CIF) 증가율",
        "수출입차 금액",
    ]
    rows = parse_rows_with_fixed_values(lines, headers, value_count=5)
    return table_parse_payload(headers=headers, rows=rows, parser="pdf_export_import_table_v1")


def parse_currency_table(lines: list[str]) -> dict[str, Any]:
    headers = [
        "period",
        "한국(원/달러) 기말",
        "한국(원/달러) 절상률",
        "한국(원/달러) 기간평균",
        "일본(엔/달러) 기말",
        "일본(엔/달러) 절상률",
        "대만(NT달러/달러) 기말",
        "대만(NT달러/달러) 절상률",
        "유로(달러/EUR) 기말",
        "유로(달러/EUR) 절상률",
    ]
    rows = parse_rows_with_fixed_values(lines, headers, value_count=9)
    return table_parse_payload(headers=headers, rows=rows, parser="pdf_currency_comparison_table_v1")


def parse_rows_with_fixed_values(lines: list[str], headers: list[str], *, value_count: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    index = 0
    while index < len(lines):
        period = normalize_period(lines[index])
        if period and index + value_count < len(lines):
            values = lines[index + 1 : index + 1 + value_count]
            if all(is_numeric_value(value) for value in values):
                row = {"period": period}
                for header, value in zip(headers[1:], values):
                    row[header] = value
                rows.append(row)
                index += value_count + 1
                continue
        index += 1
    return rows


def table_parse_payload(*, headers: list[str], rows: list[dict[str, str]], parser: str) -> dict[str, Any]:
    cell_values = []
    for row in rows:
        period = row.get("period", "")
        for header in headers[1:]:
            cell_values.append({"period": period, "column": header, "value": row.get(header, "")})
    return {
        "headers": headers if rows else [],
        "rows": [{"period": row.get("period", ""), "values": {key: value for key, value in row.items() if key != "period"}} for row in rows],
        "row_values": rows,
        "cell_values": cell_values,
        "parser": parser if rows else "",
    }


def answerability_gate_for(
    *,
    row: Mapping[str, Any],
    chunk_type: str,
    table_context: Mapping[str, Any],
    ocr: Mapping[str, Any],
    native_text: str,
    text_bridge: str,
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if clean(row.get("content_evidence_lane")) and clean(row.get("content_evidence_lane")) != "pdf_content_evidence":
        return "FILE_IDENTITY_BLOCKED", ["PDF_FILE_IDENTITY_LANE_BLOCKED"]
    if chunk_type == "OCR_fragment":
        blockers.append("PDF_OCR_FRAGMENT_NOT_REASSEMBLED")
        if ocr.get("ocr_trust_label") == "LOW_TRUST_OCR_FRAGMENT":
            blockers.append("PDF_LOW_TRUST_OCR_FRAGMENT")
        return "OCR_REASSEMBLY_REQUIRED", blockers
    if chunk_type in {"title", "heading"}:
        return "NOT_ANSWERABLE_TITLE_OR_HEADING", ["PDF_TITLE_OR_HEADING_ONLY"]
    if table_context.get("structured_table_claim_allowed") is True:
        return "TABLE_PARSER_READY", blockers
    if table_context.get("table_status") == "chart_or_table_label_without_body":
        return "TABLE_PARSER_REQUIRED", ["PDF_TABLE_OR_CHART_LABEL_WITHOUT_DETERMINISTIC_BODY"]
    if not clean(native_text):
        return "NEEDS_NATIVE_TEXT_REPAIR", ["PDF_NATIVE_BLOCK_TEXT_MISSING"]
    if clean(row.get("matched_text")) and text_bridge not in {"exact", "normalized_contains"}:
        return "NEEDS_NATIVE_TEXT_REPAIR", ["PDF_MATCHED_TEXT_NATIVE_BLOCK_MISMATCH"]
    return "EVIDENCE_TEXT_READY", blockers


def chunk_type_for(row: Mapping[str, Any], matched_block: Mapping[str, Any], table_context: Mapping[str, Any]) -> str:
    region = clean(row.get("region_type") or matched_block.get("block_type")).lower()
    text = clean(row.get("matched_text") or matched_block.get("text"))
    if row.get("OCR_fallback_used") is True or region.startswith("ocr") or matched_block.get("ocr_used") is True:
        return "OCR_fragment"
    if table_context.get("structured_table_claim_allowed") is True:
        return "table_body"
    if table_context.get("table_status") == "chart_or_table_label_without_body":
        return "table_label"
    if title_or_heading_like(text, row=row, matched_block=matched_block):
        return "title"
    if region in {"title", "document_title"}:
        return "title"
    if region in {"heading", "section_heading"}:
        return "heading"
    if table_label_like(text):
        return "table_label"
    return "paragraph"


def source_identity_for(
    row: Mapping[str, Any],
    source_metadata: Mapping[str, Any],
    parsed_artifact: Mapping[str, Any],
    parsed_path: Path | None,
) -> dict[str, Any]:
    parsed_info = source_metadata.get("parsed_artifact") if isinstance(source_metadata.get("parsed_artifact"), Mapping) else {}
    parser_info = source_metadata.get("parser") if isinstance(source_metadata.get("parser"), Mapping) else {}
    return {
        "source_file_id": clean(row.get("source_file_id")),
        "document_version_id": clean(row.get("document_version_id") or parsed_artifact.get("document_version_id")),
        "extracted_artifact_id": clean(row.get("extracted_artifact_id")),
        "parsed_artifact_id": clean(parsed_info.get("id")),
        "parsed_artifact_path": repo_relative(parsed_path) if parsed_path else "",
        "parser_name": clean(parser_info.get("parser_name") or parsed_artifact.get("parser_name")),
        "parser_version": clean(row.get("parser_version") or parser_info.get("parser_version") or parsed_artifact.get("parser_version")),
    }


def locator_for(
    row: Mapping[str, Any],
    source_metadata: Mapping[str, Any],
    page: Mapping[str, Any],
    matched_block: Mapping[str, Any],
) -> dict[str, Any]:
    location = source_metadata.get("location_json") if isinstance(source_metadata.get("location_json"), Mapping) else {}
    return {
        "file": clean(row.get("file") or row.get("source_file_id")),
        "page_no": int_or_none(row.get("page") or page.get("page_no")),
        "physical_page_index": int_or_none(row.get("physical_page_index") or page.get("physical_page_index")),
        "page_label": clean(page.get("page_label")),
        "bbox": parse_bbox(row.get("bbox") or matched_block.get("bbox") or location.get("bbox")),
        "bbox_unit": "pt",
        "block_id": clean(matched_block.get("block_id")),
        "block_type": clean(matched_block.get("block_type") or row.get("region_type")),
        "reading_order": int_or_none(matched_block.get("reading_order")),
        "search_unit_id": clean(row.get("search_unit_id")),
    }


def matched_block_summary(block: Mapping[str, Any], match_method: str) -> dict[str, Any]:
    if not block:
        return {"match_method": match_method, "block_id": "", "block_type": "", "text": "", "bbox": [], "reading_order": None}
    summary = block_summary(block)
    summary["match_method"] = match_method
    return summary


def block_summary(block: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "block_id": clean(block.get("block_id")),
        "block_type": clean(block.get("block_type")),
        "text": clean(block.get("text")),
        "bbox": parse_bbox(block.get("bbox")),
        "reading_order": int_or_none(block.get("reading_order")),
        "ocr_used": block.get("ocr_used") is True,
        "ocr_confidence": block.get("ocr_confidence"),
    }


def text_source_for(row: Mapping[str, Any], matched_block: Mapping[str, Any], page: Mapping[str, Any]) -> str:
    if row.get("OCR_fallback_used") is True or is_ocr_block(matched_block):
        return "ocr"
    if page.get("text_layer_present") is True or row.get("native_text_available") is True:
        return "native"
    return "missing"


def is_ocr_block(block: Mapping[str, Any]) -> bool:
    return block.get("ocr_used") is True or clean(block.get("block_type")).startswith("ocr")


def text_bridge_status(matched_text: str, native_block_text: str) -> str:
    if not native_block_text:
        return "missing"
    if matched_text == native_block_text:
        return "exact"
    normalized_match = normalize(matched_text)
    normalized_native = normalize(native_block_text)
    if normalized_match and normalized_match in normalized_native:
        return "normalized_contains"
    return "mismatch"


def table_label_like(value: str) -> bool:
    text = clean(value)
    compact = normalize(text)
    if not compact:
        return False
    return any(
        token in compact
        for token in (
            "수출(FOB)",
            "수입(CIF)",
            "수출입차",
            "경상수지추이",
            "주요국가의환율변동비교",
            "환율변동비교",
        )
    ) or compact.endswith(("추이", "비교", "현황", "통계표"))


def title_or_heading_like(value: str, *, row: Mapping[str, Any], matched_block: Mapping[str, Any]) -> bool:
    text = clean(value)
    compact = normalize(text)
    if not compact:
        return False
    if compact in {"최근경제동향"}:
        return True
    page_no = int_or_none(row.get("page"))
    reading_order = int_or_none(matched_block.get("reading_order"))
    if page_no is not None and page_no <= 2 and reading_order == 0 and len(compact) <= 30:
        return True
    if re.match(r"^[ⅠⅡⅢⅣIVX]+\.\s*\S+", text) and len(compact) <= 30:
        return True
    return False


def nonempty_lines(text: str) -> list[str]:
    return [clean(line) for line in text.splitlines() if clean(line)]


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", clean(value))


def normalize_period(value: str) -> str:
    text = clean(value)
    if PERIOD_RE.match(text):
        return re.sub(r"\.\s+", ". ", text)
    return ""


def is_numeric_value(value: str) -> bool:
    return bool(NUMERIC_RE.match(clean(value)))


def parse_bbox(value: Any) -> list[float]:
    if isinstance(value, list) and len(value) == 4:
        try:
            return [float(item) for item in value]
        except (TypeError, ValueError):
            return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parse_bbox(parsed)
    return []


def bbox_close(left: list[float], right: list[float], *, tolerance: float = 1.0) -> bool:
    return len(left) == 4 and len(right) == 4 and all(abs(a - b) <= tolerance for a, b in zip(left, right))


def bbox_iou(left: list[float], right: list[float]) -> float:
    if len(left) != 4 or len(right) != 4:
        return 0.0
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[2], right[2])
    y2 = min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    if intersection <= 0:
        return 0.0
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def bbox_distance(left: list[float], right: list[float]) -> float:
    if len(left) != 4 or len(right) != 4:
        return math.inf
    left_center = ((left[0] + left[2]) / 2, (left[1] + left[3]) / 2)
    right_center = ((right[0] + right[2]) / 2, (right[1] + right[3]) / 2)
    return math.dist(left_center, right_center)


def int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def nested(row: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = row.get(key)
    return value if isinstance(value, Mapping) else {}


def guardrail_errors(payload: Mapping[str, Any], name: str) -> list[str]:
    errors: list[str] = []
    if "official_metric_input_rows" not in payload or int(payload.get("official_metric_input_rows") or 0) != 0:
        errors.append(f"{name}: official_metric_input_rows must be present and remain 0")
    if payload.get("promotion_evidence") is not False:
        errors.append(f"{name}: promotion_evidence must be present and remain false")
    for key in (
        "official_denominator_registry_opened",
        "tuning_run_started",
        "gold_registry_mutated",
        "candidate_artifact_mutated",
        "production_vector_index_mutated",
        "production_vector_written",
    ):
        if payload.get(key) is True:
            errors.append(f"{name}: {key} must remain false")
    return errors


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    lines = [
        "# PDF Evidence Context V2 Enrichment",
        "",
        f"- status: `{report.get('status')}`",
        f"- context_rows: `{summary.get('context_rows')}`",
        f"- native_block_text_resolved_rows: `{summary.get('native_block_text_resolved_rows')}`",
        f"- nearby_block_text_resolved_rows: `{summary.get('nearby_block_text_resolved_rows')}`",
        f"- deterministic_table_ready_rows: `{summary.get('deterministic_table_ready_rows')}`",
        f"- official_metric_input_rows: `{report.get('official_metric_input_rows')}`",
        f"- promotion_evidence: `{report.get('promotion_evidence')}`",
        "",
        "## Rows",
        "",
        "| query_id | block | gate | table_status | nearby_blocks |",
        "|---|---|---|---|---:|",
    ]
    for row in report.get("context_rows") or []:
        if not isinstance(row, Mapping):
            continue
        matched = nested(row, "matched_block")
        table = nested(row, "table_context")
        lines.append(
            "| "
            + " | ".join(
                [
                    clean(row.get("query_id")),
                    clean(matched.get("block_id")),
                    clean(row.get("answerability_gate")),
                    clean(table.get("table_status")),
                    str(len(row.get("nearby_blocks") or [])),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
