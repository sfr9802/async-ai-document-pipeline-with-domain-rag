"""Build a small PDF evidence-object v2 canary from lineage audit results.

The canary is deliberately diagnostic-only. It keeps PDF CONTENT evidence and
FILE identity separate, blocks title/table-label/OCR-fragment surfaces from
answer candidates, and requires source text to travel with citation locators.
"""

from __future__ import annotations

import argparse
import json
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

from rag_local_llm_expected_answer_generation_v1 import (  # noqa: E402
    clean,
    read_json,
    repo_relative,
    utc_timestamp,
    write_json,
)
from rag_pdf_gold_evidence_lineage_audit_v1 import (  # noqa: E402
    has_locator_only_nearby,
    is_locator_text,
    parse_bbox,
)
from rag_question_quality_gate_v1 import classify_question  # noqa: E402


REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
DEFAULT_REPAIR_REPORT = REPORT_DIR / "pdf_evidence_readiness_repair_report.json"
DEFAULT_LINEAGE_REPORT = REPORT_DIR / "pdf_gold_evidence_lineage_audit_v1.json"
DEFAULT_CONTEXT_ENRICHMENT_REPORT = REPORT_DIR / "pdf_evidence_context_v2_enrichment_report.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "pdf_evidence_object_v2_canary_report.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "pdf_evidence_object_v2_canary_report.md"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_canary(
        repair_report=Path(args.repair_report),
        lineage_report=Path(args.lineage_report),
        context_enrichment_report=Path(args.context_enrichment_report),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
        include_prior_review_rows=args.include_prior_review_rows or not args.exclude_prior_review_rows,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "canary_rows": report["summary"]["canary_rows"],
                "candidate_for_local_llm_rows": report["summary"]["candidate_for_local_llm_rows"],
                "table_parser_required_rows": report["summary"]["table_parser_required_rows"],
                "report": report["artifact_paths"]["report_json"],
                "official_metric_input_rows": report["official_metric_input_rows"],
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
    parser.add_argument("--lineage-report", default=str(DEFAULT_LINEAGE_REPORT))
    parser.add_argument("--context-enrichment-report", default=str(DEFAULT_CONTEXT_ENRICHMENT_REPORT))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--include-prior-review-rows", action="store_true", help="Deprecated no-op; prior rows are included by default.")
    parser.add_argument("--exclude-prior-review-rows", action="store_true")
    return parser.parse_args(argv)


def content_nearby_paragraphs(row: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for item in list_value(row.get("nearby_paragraphs")):
        text = clean(item)
        if not text:
            continue
        if " > p." in text and "bbox" in text:
            continue
        values.append(text)
    return values


def run_canary(
    *,
    repair_report: Path = DEFAULT_REPAIR_REPORT,
    lineage_report: Path = DEFAULT_LINEAGE_REPORT,
    context_enrichment_report: Path | None = None,
    output_report: Path = DEFAULT_OUTPUT_JSON,
    output_md: Path = DEFAULT_OUTPUT_MD,
    include_prior_review_rows: bool = True,
) -> dict[str, Any]:
    repair_payload = read_json(repair_report)
    lineage_payload = read_json(lineage_report)
    context_input_errors: list[str] = []
    if context_enrichment_report:
        if context_enrichment_report.exists():
            context_payload = read_json(context_enrichment_report)
        else:
            context_payload = {}
            context_input_errors.append("context_enrichment_report was provided but does not exist")
    else:
        context_payload = {}
    repair_rows = [row for row in repair_payload.get("repair_rows") or [] if isinstance(row, Mapping)]
    context_lookup = {
        clean(row.get("query_id")): row
        for row in context_payload.get("context_rows") or []
        if isinstance(row, Mapping) and clean(row.get("query_id"))
    }
    lineage_lookup = {
        clean(row.get("query_id")): row
        for row in lineage_payload.get("lineage_rows") or []
        if isinstance(row, Mapping) and clean(row.get("query_id"))
    }
    canary_rows = [
        evidence_object_from_repair_row(
            row,
            lineage_lookup.get(clean(row.get("query_id")), {}),
            context_lookup.get(clean(row.get("query_id")), {}),
        )
        for row in repair_rows
    ]
    prior_rows = []
    if include_prior_review_rows:
        prior_rows = [
            evidence_object_from_prior_row(row)
            for row in lineage_payload.get("prior_good_candidate_rows") or []
            if isinstance(row, Mapping)
        ]
        canary_rows.extend(prior_rows)

    gate_counts = Counter(clean(row.get("answerability_gate")) for row in canary_rows)
    chunk_counts = Counter(clean(row.get("chunk_type")) for row in canary_rows)
    validation_errors = validation_errors_for(repair_payload, lineage_payload, context_payload, canary_rows)
    validation_errors.extend(context_input_errors)
    status = status_for(validation_errors=validation_errors, rows=canary_rows)
    report = {
        "schema_version": "rag_pdf_evidence_object_v2_canary_report",
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
            "lineage_report": repo_relative(lineage_report),
            "context_enrichment_report": repo_relative(context_enrichment_report) if context_enrichment_report else "",
        },
        "summary": {
            "repair_rows": len(repair_rows),
            "prior_review_rows": len(prior_rows),
            "canary_rows": len(canary_rows),
            "candidate_for_local_llm_rows": sum(1 for row in canary_rows if row.get("candidate_for_local_llm") is True),
            "table_parser_required_rows": gate_counts["TABLE_PARSER_REQUIRED"],
            "locator_only_context_rows": sum(1 for row in canary_rows if row.get("locator_only_context") is True),
            "native_block_text_missing_rows": sum(
                1
                for row in canary_rows
                if not clean(
                    nested_mapping(row, "pdf_evidence_context_v2")
                    .get("text_context", {})
                    .get("native_block_text")
                    if isinstance(nested_mapping(row, "pdf_evidence_context_v2").get("text_context"), Mapping)
                    else ""
                )
            ),
            "structured_table_claim_allowed_rows": sum(
                1
                for row in canary_rows
                if nested_mapping(nested_mapping(row, "pdf_evidence_context_v2"), "table_context").get(
                    "structured_table_claim_allowed"
                )
                is True
            ),
            "chunk_type_counts": dict(sorted(chunk_counts.items())),
            "answerability_gate_counts": dict(sorted(gate_counts.items())),
        },
        "evidence_object_v2_contract": evidence_object_v2_contract(),
        "canary_checks": canary_checks(canary_rows),
        "canary_rows": canary_rows,
        "next_safe_actions": [
            "Repair native/OCR paragraph materialization before reopening PDF answer candidates.",
            "Add deterministic PDF table extraction for table_label/table_body rows before LLM phrasing.",
            "Use this canary before any wider PDF rechunking or retrieval rerun.",
        ],
        "artifact_paths": {"report_json": repo_relative(output_report), "report_md": repo_relative(output_md)},
        "validation": {"ok": not validation_errors, "errors": validation_errors},
    }
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def evidence_object_from_repair_row(
    row: Mapping[str, Any],
    lineage_row: Mapping[str, Any],
    context_row: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    context_row = context_row if isinstance(context_row, Mapping) else {}
    query_id = clean(row.get("query_id"))
    lineage_vector = lineage_row.get("vector_diagnostic") if isinstance(lineage_row.get("vector_diagnostic"), Mapping) else {}
    lineage_human = lineage_row.get("human_audit_v1") if isinstance(lineage_row.get("human_audit_v1"), Mapping) else {}
    actual_question = clean(lineage_human.get("question") or lineage_vector.get("query") or row.get("question") or query_id)
    context_text = nested_mapping(context_row, "text_context")
    matched_text = clean(context_row.get("matched_text") or context_text.get("matched_text") or row.get("matched_text"))
    nearby_native = enriched_nearby_texts(context_row) or dedupe(content_nearby_paragraphs(row))
    locator_only = has_locator_only_nearby(row) and not enriched_nearby_texts(context_row)
    chunk_type = clean(context_row.get("chunk_type")) or classify_chunk_type(
        row,
        actual_question=actual_question,
        matched_text=matched_text,
        nearby_native=nearby_native,
    )
    table_payload = enriched_table_payload(context_row) or extract_table_payload(row)
    answerable_evidence = enriched_answerable_evidence(context_row, matched_text, nearby_native, chunk_type) or answerable_evidence_text(
        matched_text,
        nearby_native,
        chunk_type,
    )
    native_block_text = clean(context_text.get("native_block_text")) or native_block_text_for(row)
    if context_row:
        gate, blockers = enriched_gate_for(context_row, answerable_evidence)
    else:
        gate, blockers = answerability_gate_for(
            row=row,
            question=actual_question,
            matched_text=matched_text,
            nearby_native=nearby_native,
            chunk_type=chunk_type,
            answerable_evidence=answerable_evidence,
            table_payload=table_payload,
            locator_only=locator_only,
            native_block_text=native_block_text,
        )
    locator = enriched_locator(context_row) or citation_locator(row)
    candidate = gate in {"ANSWERABLE", "TABLE_PARSER_READY"} and bool(answerable_evidence)
    evidence_context = enriched_evidence_context(context_row) or pdf_evidence_context_v2(
        source_identity=source_identity(row),
        locator=locator,
        matched_text=matched_text,
        native_block_text=native_block_text,
        nearby_native=nearby_native,
        table_payload=table_payload,
        row=row,
    )
    return {
        "schema_version": "pdf_evidence_object_v2_canary_row",
        "source_kind": "current_repair_row",
        "query_id": query_id,
        "actual_question_or_human_reviewed_query": actual_question,
        "answerable_evidence_text": answerable_evidence,
        "matched_text": matched_text,
        "nearby_native_paragraphs": nearby_native,
        "raw_nearby_paragraphs": list_value(row.get("nearby_paragraphs")),
        "table_body_rows": table_payload["table_body_rows"],
        "table_columns": table_payload["table_columns"],
        "table_values": table_payload["table_values"],
        "page": locator["page"],
        "bbox": locator["bbox"],
        "region_type": locator["region_type"],
        "search_unit_id": locator["search_unit_id"],
        "document_version_id": locator["document_version_id"],
        "file": locator["file"],
        "citation_locator": locator,
        "pdf_evidence_context_v2": evidence_context,
        "chunk_type": chunk_type,
        "answerability_gate": gate,
        "answerability_blockers": blockers,
        "candidate_for_local_llm": candidate,
        "locator_only_context": locator_only,
        "native_text_available": row.get("native_text_available") is True,
        "OCR_fallback_used": row.get("OCR_fallback_used") is True,
        "content_evidence_lane": clean(row.get("content_evidence_lane")),
        "file_identity_lane": row.get("file_identity_lane") if isinstance(row.get("file_identity_lane"), Mapping) else {},
        "human_review_required": True,
        "model_assisted_diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "official_denominator_current": False,
    }


def evidence_object_from_prior_row(row: Mapping[str, Any]) -> dict[str, Any]:
    query_id = clean(row.get("query_id"))
    question = clean(row.get("query"))
    evidence = clean(row.get("expected_answer_text"))
    bbox = row.get("expected_bbox")
    if not isinstance(bbox, list):
        bbox = parse_bbox(bbox)
    page = int_or_none(row.get("expected_page_no"))
    chunk_type = clean(row.get("expected_chunk_type")) or "paragraph"
    locator = {
        "file": clean(row.get("expected_file_name")),
        "document_version_id": clean(row.get("expected_document_version_id")),
        "page": page,
        "physical_page_index": page - 1 if isinstance(page, int) and page > 0 else None,
        "bbox": bbox,
        "region_type": chunk_type,
        "search_unit_id": clean(row.get("search_unit_id")),
    }
    file_identity = prior_row_is_file_identity(row)
    if file_identity:
        gate = "FILE_IDENTITY_ONLY"
    elif evidence and question and chunk_type not in {"table_label", "title", "heading"}:
        gate = "ANSWERABLE"
    else:
        gate = "NOT_ANSWERABLE"
    content_evidence = "" if file_identity else evidence
    content_nearby = [] if file_identity else [evidence] if evidence else []
    evidence_context = pdf_evidence_context_v2(
        source_identity={
            "source_file_id": "",
            "document_version_id": locator["document_version_id"],
            "extracted_artifact_id": "",
            "parsed_artifact_id": "",
            "parser_name": "",
            "parser_version": "",
            "index_version": "",
        },
        locator=locator,
        matched_text=content_evidence,
        native_block_text=content_evidence,
        nearby_native=content_nearby,
        table_payload={"table_body_rows": [], "table_columns": [], "table_values": []},
        row=row,
    )
    return {
        "schema_version": "pdf_evidence_object_v2_canary_row",
        "source_kind": "prior_review_source",
        "query_id": query_id,
        "actual_question_or_human_reviewed_query": question,
        "answerable_evidence_text": content_evidence,
        "matched_text": content_evidence,
        "nearby_native_paragraphs": content_nearby,
        "identity_reference_text": evidence if file_identity else "",
        "raw_nearby_paragraphs": [],
        "table_body_rows": [],
        "table_columns": [],
        "table_values": [],
        "page": locator["page"],
        "bbox": locator["bbox"],
        "region_type": locator["region_type"],
        "search_unit_id": locator["search_unit_id"],
        "document_version_id": locator["document_version_id"],
        "file": locator["file"],
        "citation_locator": locator,
        "pdf_evidence_context_v2": evidence_context,
        "chunk_type": chunk_type,
        "answerability_gate": gate,
        "answerability_blockers": prior_row_blockers(gate),
        "candidate_for_local_llm": gate == "ANSWERABLE",
        "locator_only_context": False,
        "native_text_available": True,
        "OCR_fallback_used": False,
        "content_evidence_lane": "pdf_file_identity" if file_identity else "pdf_content_evidence",
        "file_identity_lane": {
            "merged_with_content_evidence": False,
            "filename_only_identity_accepted": False,
            "source_review_lane": "PDF_FILE_LOOKUP" if file_identity else "PDF_CONTENT",
        },
        "human_review_required": True,
        "model_assisted_diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "official_denominator_current": False,
    }


def classify_chunk_type(
    row: Mapping[str, Any], *, actual_question: str, matched_text: str, nearby_native: list[str]
) -> str:
    region = clean(row.get("region_type")).lower()
    quality = classify_question(
        actual_question or matched_text,
        query_id=clean(row.get("query_id")),
        track="pdf_business_ocr_mm",
        region_type=region,
        evidence_text=matched_text,
    )
    labels = set(quality["classifications"])
    if clean(row.get("content_evidence_lane")) != "pdf_content_evidence":
        return "file_identity"
    if region in {"table_body", "table_cell", "table_row"} or extract_table_payload(row)["table_body_rows"]:
        return "table_body"
    if (
        "PDF_TABLE_LABEL_AS_QUERY" in labels
        or region in {"table", "table_label", "table_caption", "table_caption_footnote"}
        or table_label_like(actual_question)
        or table_label_like(matched_text)
    ):
        return "table_label"
    if "PDF_OCR_FRAGMENT_AS_QUERY" in labels:
        return "OCR_fragment"
    if "PDF_HEADING_OR_TITLE_AS_QUERY" in labels or region in {"title", "document_title", "heading", "section_heading"}:
        return "heading" if "heading" in region else "title"
    if not matched_text and not nearby_native and has_locator_only_nearby(row):
        return "locator_only"
    return "paragraph"


def answerability_gate_for(
    *,
    row: Mapping[str, Any],
    question: str,
    matched_text: str,
    nearby_native: list[str],
    chunk_type: str,
    answerable_evidence: str,
    table_payload: Mapping[str, Any],
    locator_only: bool,
    native_block_text: str,
) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if clean(row.get("content_evidence_lane")) != "pdf_content_evidence":
        blockers.append("PDF_FILE_IDENTITY_LANE_BLOCKED")
        return "FILE_IDENTITY_ONLY", blockers
    if chunk_type == "table_label":
        blockers.append("PDF_TABLE_LABEL_REQUIRES_DETERMINISTIC_TABLE_PARSER")
        if not table_payload.get("table_values"):
            blockers.append("PDF_TABLE_BODY_VALUE_MISSING")
        return "TABLE_PARSER_REQUIRED", blockers
    if chunk_type == "table_body" and not table_payload.get("table_values"):
        blockers.append("PDF_TABLE_BODY_VALUE_MISSING")
        return "TABLE_PARSER_REQUIRED", blockers
    if chunk_type in {"title", "heading"}:
        blockers.append("PDF_TITLE_OR_HEADING_ONLY")
        return "NOT_ANSWERABLE", blockers
    if chunk_type == "OCR_fragment":
        blockers.append("PDF_OCR_FRAGMENT_NOT_REASSEMBLED")
        return "NEEDS_NATIVE_TEXT_REPAIR", blockers
    if locator_only and not nearby_native:
        blockers.append("PDF_NEARBY_CONTEXT_LOCATOR_ONLY")
        if not is_complete_sentence_or_numeric_claim(matched_text):
            return "NEEDS_NATIVE_TEXT_REPAIR", blockers
    if not answerable_evidence:
        blockers.append("PDF_ANSWERABLE_EVIDENCE_TEXT_MISSING")
        return "NEEDS_NATIVE_TEXT_REPAIR", blockers
    if not native_block_text and not list_value(row.get("ocr_fragments")):
        blockers.append("PDF_NATIVE_BLOCK_TEXT_OR_OCR_FRAGMENT_MISSING")
        return "NEEDS_NATIVE_TEXT_REPAIR", blockers
    quality = classify_question(question, track="pdf_business_ocr_mm", evidence_text=answerable_evidence)
    if "PDF_CONTENT_SNIPPET_AS_QUERY" in quality["classifications"]:
        blockers.append("PDF_QUESTION_REWRITE_REQUIRED")
    return "ANSWERABLE", blockers


def answerable_evidence_text(matched_text: str, nearby_native: list[str], chunk_type: str) -> str:
    if chunk_type in {"title", "heading", "table_label", "OCR_fragment", "file_identity", "locator_only"}:
        return ""
    return "\n".join(dedupe([matched_text, *nearby_native]))


def extract_table_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "table_body_rows": list_value(row.get("table_body_rows") or row.get("table_rows")),
        "table_columns": list_value(row.get("table_columns") or row.get("column_headers")),
        "table_values": list_value(row.get("table_values") or row.get("cell_values") or row.get("deterministic_table_values")),
    }


def enriched_nearby_texts(context_row: Mapping[str, Any]) -> list[str]:
    texts = []
    for block in context_row.get("nearby_blocks") or []:
        if isinstance(block, Mapping):
            texts.append(clean(block.get("text")))
    return dedupe(texts)


def enriched_table_payload(context_row: Mapping[str, Any]) -> dict[str, Any]:
    table = nested_mapping(context_row, "table_context")
    if not table:
        return {}
    return {
        "table_body_rows": list_value(table.get("rows")),
        "table_columns": list_value(table.get("headers")),
        "table_values": list_value(table.get("row_values") or table.get("cell_values")),
    }


def enriched_answerable_evidence(
    context_row: Mapping[str, Any],
    matched_text: str,
    nearby_native: list[str],
    chunk_type: str,
) -> str:
    table = nested_mapping(context_row, "table_context")
    if table.get("structured_table_claim_allowed") is True:
        lines = []
        for row in table.get("row_values") or []:
            if not isinstance(row, Mapping):
                continue
            period = clean(row.get("period"))
            values = [
                f"{key}={clean(value)}"
                for key, value in row.items()
                if key != "period" and clean(value)
            ]
            if period and values:
                lines.append(f"{period}: " + "; ".join(values))
        return "\n".join(lines)
    gate = clean(context_row.get("answerability_gate"))
    if gate.startswith("NOT_ANSWERABLE") or gate in {"TABLE_PARSER_REQUIRED", "OCR_REASSEMBLY_REQUIRED"}:
        return ""
    return answerable_evidence_text(matched_text, nearby_native, chunk_type)


def enriched_gate_for(context_row: Mapping[str, Any], answerable_evidence: str) -> tuple[str, list[str]]:
    gate = clean(context_row.get("answerability_gate"))
    blockers = list_value(context_row.get("answerability_blockers"))
    if gate == "TABLE_PARSER_READY" and answerable_evidence:
        return "TABLE_PARSER_READY", []
    if gate == "EVIDENCE_TEXT_READY" and answerable_evidence:
        return "ANSWERABLE", []
    if gate == "NOT_ANSWERABLE_TITLE_OR_HEADING":
        return "NOT_ANSWERABLE_TITLE_OR_HEADING", blockers or ["PDF_TITLE_OR_HEADING_ONLY"]
    if gate == "OCR_REASSEMBLY_REQUIRED":
        return "OCR_REASSEMBLY_REQUIRED", blockers or ["PDF_OCR_FRAGMENT_NOT_REASSEMBLED"]
    if gate == "TABLE_PARSER_REQUIRED":
        return "TABLE_PARSER_REQUIRED", blockers or ["PDF_TABLE_OR_CHART_LABEL_WITHOUT_DETERMINISTIC_BODY"]
    return gate or "NEEDS_NATIVE_TEXT_REPAIR", blockers or ["PDF_CONTEXT_ENRICHMENT_UNANSWERABLE"]


def enriched_locator(context_row: Mapping[str, Any]) -> dict[str, Any]:
    locator = nested_mapping(context_row, "locator")
    if not locator:
        return {}
    return {
        "file": clean(locator.get("file")),
        "document_version_id": clean(context_row.get("document_version_id")),
        "page": locator.get("page_no"),
        "physical_page_index": locator.get("physical_page_index"),
        "bbox": locator.get("bbox") or [],
        "region_type": clean(locator.get("block_type")),
        "search_unit_id": locator.get("search_unit_id"),
        "block_id": clean(locator.get("block_id")),
        "reading_order": locator.get("reading_order"),
    }


def enriched_evidence_context(context_row: Mapping[str, Any]) -> dict[str, Any]:
    if not context_row:
        return {}
    return {
        "schema_version": "pdf_evidence_context_v2",
        "source_identity": dict(nested_mapping(context_row, "source_identity")),
        "locator": dict(nested_mapping(context_row, "locator")),
        "text_context": dict(nested_mapping(context_row, "text_context")),
        "ocr_context": dict(nested_mapping(context_row, "ocr_context")),
        "table_context": dict(nested_mapping(context_row, "table_context")),
        "nearby_blocks": list_value(context_row.get("nearby_blocks")),
        "lineage": {
            "retrieved_search_unit_id": clean(context_row.get("search_unit_id")),
            "evidence_search_unit_id": clean(context_row.get("search_unit_id")),
            "context_enrichment_report": True,
        },
    }


def source_identity(row: Mapping[str, Any]) -> dict[str, Any]:
    metadata = row.get("source_metadata") if isinstance(row.get("source_metadata"), Mapping) else {}
    location = metadata.get("location_json") if isinstance(metadata.get("location_json"), Mapping) else {}
    return {
        "source_file_id": clean(row.get("source_file_id")),
        "document_version_id": clean(row.get("document_version_id") or location.get("document_version_id")),
        "extracted_artifact_id": clean(row.get("extracted_artifact_id")),
        "parsed_artifact_id": metadata_identifier(metadata.get("parsed_artifact")),
        "parser_name": clean(metadata.get("parser_name") or metadata.get("parser")),
        "parser_version": clean(row.get("parser_version") or metadata.get("parser_version")),
        "index_version": clean(metadata.get("index_version") or metadata.get("candidate_index_version")),
    }


def native_block_text_for(row: Mapping[str, Any]) -> str:
    metadata = row.get("source_metadata") if isinstance(row.get("source_metadata"), Mapping) else {}
    for key in ("native_block_text", "block_text", "text", "normalized_block_text"):
        value = clean(row.get(key) or metadata.get(key))
        if value:
            return value
    location = metadata.get("location_json") if isinstance(metadata.get("location_json"), Mapping) else {}
    for key in ("native_block_text", "block_text", "text"):
        value = clean(location.get(key))
        if value:
            return value
    return ""


def metadata_identifier(value: Any) -> str:
    if isinstance(value, Mapping):
        return clean(value.get("id") or value.get("artifact_id") or value.get("parsed_artifact_id"))
    return clean(value)


def pdf_evidence_context_v2(
    *,
    source_identity: Mapping[str, Any],
    locator: Mapping[str, Any],
    matched_text: str,
    native_block_text: str,
    nearby_native: list[str],
    table_payload: Mapping[str, Any],
    row: Mapping[str, Any],
) -> dict[str, Any]:
    metadata = row.get("source_metadata") if isinstance(row.get("source_metadata"), Mapping) else {}
    location = metadata.get("location_json") if isinstance(metadata.get("location_json"), Mapping) else {}
    text_source = "ocr" if row.get("OCR_fallback_used") is True else "native" if row.get("native_text_available") is True else "missing"
    text_bridge = text_bridge_status(matched_text=matched_text, native_block_text=native_block_text)
    table_values = list_value(table_payload.get("table_values"))
    table_rows = list_value(table_payload.get("table_body_rows"))
    table_status = "parser_table" if table_values or table_rows else "table_like_paragraph" if table_label_like(matched_text) else "none"
    return {
        "schema_version": "pdf_evidence_context_v2",
        "source_identity": dict(source_identity),
        "locator": {
            "file": locator.get("file"),
            "page_no": locator.get("page"),
            "physical_page_index": locator.get("physical_page_index"),
            "page_label": clean(location.get("page_label")),
            "bbox": locator.get("bbox") or [],
            "bbox_unit": "pt" if locator.get("bbox") else "",
            "block_id": clean(location.get("block_id") or location.get("page_block_id")),
            "block_type": clean(location.get("block_type") or locator.get("region_type")),
            "reading_order": location.get("reading_order"),
            "search_unit_id": locator.get("search_unit_id"),
            "citation_text": clean(row.get("citation_text")),
        },
        "text_context": {
            "matched_text": matched_text,
            "native_block_text": native_block_text,
            "normalized_block_text": normalize(native_block_text),
            "text_source": text_source,
            "native_text_matches_matched_text": text_bridge in {"exact", "normalized"},
            "text_bridge_status": text_bridge,
        },
        "ocr_context": {
            "ocr_used": row.get("OCR_fallback_used") is True,
            "page_ocr_confidence_avg": row.get("OCR_confidence"),
            "ocr_fragments": list_value(row.get("ocr_fragments")),
        },
        "table_context": {
            "table_status": table_status,
            "raw_table_text": matched_text if table_status == "table_like_paragraph" else "",
            "headers": list_value(table_payload.get("table_columns")),
            "rows": table_rows,
            "row_values": table_values,
            "column_values": list_value(row.get("column_values")),
            "cell_values": list_value(row.get("cell_values")),
            "structured_table_claim_allowed": bool(table_values or table_rows),
        },
        "nearby_blocks": [
            {"text": text, "citation_text": "", "bbox": [], "search_unit_id": ""}
            for text in nearby_native
        ],
        "lineage": {
            "retrieved_search_unit_id": clean(row.get("search_unit_id")),
            "evidence_search_unit_id": locator.get("search_unit_id"),
            "layout_resolution_method": clean(row.get("layout_resolution_method")),
            "source_bound_bbox": row.get("source_bound_bbox") is True,
        },
    }


def text_bridge_status(*, matched_text: str, native_block_text: str) -> str:
    if not native_block_text:
        return "missing"
    if matched_text == native_block_text:
        return "exact"
    if normalize(matched_text) and normalize(matched_text) in normalize(native_block_text):
        return "normalized"
    if table_label_like(matched_text):
        return "label_only"
    return "mismatch"


def table_label_like(value: str) -> bool:
    text = clean(value)
    compact = normalize(text)
    if not text:
        return False
    patterns = (
        r"수\s*출\s*\(\s*FOB\s*\)",
        r"수출입",
        r"경상수지\s*추이",
        r"환율변동\s*비교",
        r"주요국가의\s*환율변동\s*비교",
    )
    if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
        return True
    return compact.endswith(("추이", "비교", "현황", "통계표"))


def citation_locator(row: Mapping[str, Any]) -> dict[str, Any]:
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    page = row.get("page") if row.get("page") is not None else locator.get("page")
    return {
        "file": clean(row.get("file") or locator.get("file") or row.get("source_file_id")),
        "document_version_id": clean(row.get("document_version_id") or locator.get("document_version_id")),
        "page": page,
        "physical_page_index": row.get("physical_page_index")
        if row.get("physical_page_index") is not None
        else locator.get("physical_page_index"),
        "bbox": row.get("bbox") if row.get("bbox") else locator.get("bbox") or [],
        "region_type": clean(row.get("region_type") or locator.get("region_type")),
        "search_unit_id": clean(row.get("search_unit_id") or locator.get("search_unit_id")),
    }


def evidence_object_v2_contract() -> dict[str, Any]:
    return {
        "required_fields": [
            "actual_question_or_human_reviewed_query",
            "answerable_evidence_text",
            "matched_text",
            "nearby_native_paragraphs",
            "table_body_rows",
            "table_columns",
            "table_values",
            "page",
            "bbox",
            "search_unit_id",
            "citation_locator",
            "chunk_type",
            "answerability_gate",
        ],
        "chunk_types": ["title", "heading", "paragraph", "table_label", "table_body", "OCR_fragment", "locator_only"],
        "answerability_gates": [
            "ANSWERABLE",
            "NOT_ANSWERABLE",
            "NOT_ANSWERABLE_TITLE_OR_HEADING",
            "TABLE_PARSER_READY",
            "TABLE_PARSER_REQUIRED",
            "NEEDS_NATIVE_TEXT_REPAIR",
            "OCR_REASSEMBLY_REQUIRED",
            "FILE_IDENTITY_ONLY",
        ],
        "policy": {
            "native_text_priority": True,
            "ocr_is_fallback_only": True,
            "locator_without_text_blocked": True,
            "table_values_must_be_deterministic_before_llm": True,
            "file_identity_lane_cannot_be_content_answer_candidate": True,
        },
    }


def canary_checks(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "title_only_chunk_answer_candidates": [
            clean(row.get("query_id")) for row in rows if row.get("chunk_type") in {"title", "heading"} and row.get("candidate_for_local_llm")
        ],
        "table_label_candidates_without_table_parser": [
            clean(row.get("query_id"))
            for row in rows
            if row.get("chunk_type") == "table_label" and row.get("candidate_for_local_llm")
        ],
        "locator_with_evidence_text_missing": [
            clean(row.get("query_id"))
            for row in rows
            if not row.get("answerable_evidence_text") and row.get("candidate_for_local_llm")
        ],
        "file_identity_as_content_candidates": [
            clean(row.get("query_id"))
            for row in rows
            if clean(row.get("content_evidence_lane")) != "pdf_content_evidence" and row.get("candidate_for_local_llm")
        ],
    }


def validation_errors_for(
    repair_payload: Mapping[str, Any],
    lineage_payload: Mapping[str, Any],
    context_payload: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
) -> list[str]:
    errors: list[str] = []
    lineage_validation = lineage_payload.get("validation") if isinstance(lineage_payload.get("validation"), Mapping) else {}
    if lineage_validation.get("ok") is not True:
        errors.append("lineage_report validation.ok must be true")
    if lineage_payload.get("status") == "FAILED_GUARDRAIL":
        errors.append("lineage_report status must not be FAILED_GUARDRAIL")
    if int_or_none(lineage_payload.get("official_metric_input_rows")) not in (None, 0):
        errors.append("lineage_report official_metric_input_rows must remain 0")
    if lineage_payload.get("promotion_evidence") is True:
        errors.append("lineage_report promotion_evidence must remain false")
    if lineage_payload.get("official_denominator_registry_opened") is True:
        errors.append("lineage_report official_denominator_registry_opened must remain false")
    if int_or_none(repair_payload.get("official_metric_input_rows")) not in (None, 0):
        errors.append("repair_report official_metric_input_rows must remain 0")
    if repair_payload.get("promotion_evidence") is True:
        errors.append("repair_report promotion_evidence must remain false")
    if context_payload:
        context_validation = context_payload.get("validation") if isinstance(context_payload.get("validation"), Mapping) else {}
        if context_validation and context_validation.get("ok") is not True:
            errors.append("context_enrichment_report validation.ok must be true")
        if context_payload.get("status") == "FAILED_GUARDRAIL":
            errors.append("context_enrichment_report status must not be FAILED_GUARDRAIL")
        if "official_metric_input_rows" not in context_payload or int_or_none(context_payload.get("official_metric_input_rows")) != 0:
            errors.append("context_enrichment_report official_metric_input_rows must be present and remain 0")
        for key in (
            "promotion_evidence",
            "official_denominator_registry_opened",
            "tuning_run_started",
            "gold_registry_mutated",
            "candidate_artifact_mutated",
            "production_vector_index_mutated",
        ):
            if key not in context_payload or context_payload.get(key) is not False:
                errors.append(f"context_enrichment_report {key} must be present and remain false")
    for check_name, query_ids in canary_checks(rows).items():
        if query_ids:
            errors.append(f"{check_name}: {query_ids}")
    if any(row.get("official_metric_input") is True for row in rows):
        errors.append("canary rows must not set official_metric_input=true")
    if any(row.get("promotion_evidence") is True for row in rows):
        errors.append("canary rows must not set promotion_evidence=true")
    return errors


def status_for(*, validation_errors: list[str], rows: list[Mapping[str, Any]]) -> str:
    if validation_errors:
        return "FAILED_GUARDRAIL"
    if not any(row.get("candidate_for_local_llm") is True for row in rows):
        return "PDF_EVIDENCE_OBJECT_V2_CANARY_BLOCKED_BY_CONTEXT_GAPS"
    return "PDF_EVIDENCE_OBJECT_V2_CANARY_COMPLETE"


def prior_row_is_file_identity(row: Mapping[str, Any]) -> bool:
    query_id = clean(row.get("query_id"))
    role = clean(row.get("source_role")).lower()
    source_path = clean(row.get("source_path")).lower()
    lane = clean(row.get("retrieval_lane") or row.get("lane") or row.get("review_group")).lower()
    return (
        query_id.startswith("pdf_file_lookup")
        or "file_lookup" in query_id
        or "file_lookup" in role
        or "file_lookup" in source_path
        or "file_lookup" in lane
        or "file_identity" in lane
    )


def prior_row_blockers(gate: str) -> list[str]:
    if gate == "ANSWERABLE":
        return []
    if gate == "FILE_IDENTITY_ONLY":
        return ["PRIOR_REVIEW_SOURCE_FILE_IDENTITY_LANE_BLOCKED"]
    return ["PRIOR_REVIEW_SOURCE_NOT_ANSWERABLE"]


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    lines = [
        "# PDF Evidence Object v2 Canary",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Canary rows: `{summary.get('canary_rows')}`",
        f"- Candidate for local LLM rows: `{summary.get('candidate_for_local_llm_rows')}`",
        f"- Table parser required rows: `{summary.get('table_parser_required_rows')}`",
        f"- Locator-only context rows: `{summary.get('locator_only_context_rows')}`",
        f"- Native block text missing rows: `{summary.get('native_block_text_missing_rows')}`",
        f"- Official metric input rows: `{report.get('official_metric_input_rows')}`",
        f"- Promotion evidence: `{str(report.get('promotion_evidence')).lower()}`",
        "",
        "## Canary Rows",
        "",
    ]
    for row in report.get("canary_rows", []):
        lines.append(
            f"- `{row.get('query_id')}` chunk=`{row.get('chunk_type')}` "
            f"gate=`{row.get('answerability_gate')}` candidate=`{str(row.get('candidate_for_local_llm')).lower()}`"
        )
    return "\n".join(lines) + "\n"


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def nested_mapping(row: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = row.get(key)
    return value if isinstance(value, Mapping) else {}


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = clean(value)
        if not item:
            continue
        if is_locator_text(item):
            continue
        key = normalize(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def is_complete_sentence_or_numeric_claim(value: str) -> bool:
    text = clean(value)
    if not text:
        return False
    if text.endswith(("다.", "다", "요.", "요")):
        return True
    if re.search(r"\d", text) and len(text) >= 12 and not re.search(r"\s,\s|,\s*$", text):
        return True
    return False


def int_or_none(value: Any) -> int | None:
    try:
        if value in ("", None):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize(value: str) -> str:
    return "".join(clean(value).lower().split())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
