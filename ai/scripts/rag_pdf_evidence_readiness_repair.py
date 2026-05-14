"""Build a diagnostic-only PDF evidence readiness repair report.

The repair packet normalizes the current PDF readiness rows into explicit
row-level blocker fields for a future strict gate rerun. It does not generate
answers, run retrieval, open official metrics, or merge PDF CONTENT evidence
with FILE/document identity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"

DEFAULT_READINESS_REPORT = REPORT_DIR / "pdf_evidence_readiness_report.json"
DEFAULT_READINESS_ROWS = REPORT_DIR / "pdf_evidence_readiness_rows.jsonl"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "pdf_evidence_readiness_repair_report.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "pdf_evidence_readiness_repair_report.md"

SCHEMA_VERSION = "pdf_evidence_readiness_repair_report_v1"
ROW_SCHEMA_VERSION = "pdf_evidence_readiness_repair_row_v1"
TRACK = "pdf_business_ocr_mm"
PDF_CONTENT_EVIDENCE = "pdf_content_evidence"
PDF_FILE_IDENTITY = "pdf_file_identity"
STABLE_IDENTITY_REQUIRED = "stable_identity_required"
CONTEXT_METADATA_BLOCKERS = {
    "missing_search_unit_id",
    "missing_search_unit_rank",
    "missing_source_file_id",
    "missing_stable_source_identity",
    "missing_extracted_artifact_id",
    "missing_parser_source_metadata",
    "missing_nearby_paragraphs",
    "missing_ocr_confidence_or_native_text",
}
BLOCKER_CLASSIFICATION_ORDER = (
    "blocked_missing_search_unit",
    "blocked_missing_parser_source_metadata",
    "blocked_missing_layout_bbox_region",
    "blocked_missing_source_bound_bbox",
    "blocked_missing_nearby_paragraphs",
    "blocked_missing_ocr_or_native_text_trust",
    "blocked_file_identity_ambiguity",
    "blocked_content_file_lane_separation",
    "blocked_unresolved_source_artifact",
    "diagnostic_only_fallback",
)
PROTECTED_SOURCE_GUARDRAILS = (
    "official_denominator_registry_changed",
    "official_denominator_opened_or_frozen",
    "promotion_evidence_created",
    "pdf_answer_generation_denominator_opened",
    "pdf_content_file_lanes_aggregated",
    "production_namespace_mutated",
    "production_vector_index_mutated",
    "production_vector_written",
    "candidate_artifact_mutated",
    "immutable_baseline_mutated",
    "answer_generation_run",
    "diagnostic_only_row_promoted",
    "repo_local_pdf_silver_manifest_written",
    "route_fallback_labels_promoted_to_official_metrics",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_repair(
        readiness_report=Path(args.readiness_report),
        readiness_rows=Path(args.readiness_rows),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "input_rows": report["input_rows"],
                "strict_ready_rows": report["strict_ready_rows"],
                "official_metric_input_rows": report["official_metric_input_rows"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] != "FAILED_GUARDRAIL" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness-report", default=str(DEFAULT_READINESS_REPORT))
    parser.add_argument("--readiness-rows", default=str(DEFAULT_READINESS_ROWS))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_repair(
    *,
    readiness_report: Path,
    readiness_rows: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    report = build_repair(readiness_report=readiness_report, readiness_rows=readiness_rows)
    report["artifact_paths"]["report_json"] = repo_relative(output_report)
    report["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def build_repair(*, readiness_report: Path, readiness_rows: Path) -> dict[str, Any]:
    source_report = read_json(readiness_report)
    source_rows = read_jsonl(readiness_rows) if readiness_rows.exists() else list(source_report.get("readiness_rows_preview") or [])
    report = build_repair_from_payload(source_report=source_report, source_rows=source_rows)
    report["source_artifacts"] = {
        "readiness_report": file_identity(readiness_report),
        "readiness_rows": file_identity(readiness_rows),
    }
    return report


def build_repair_from_payload(
    *,
    source_report: Mapping[str, Any],
    source_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    repair_rows = [repair_row(row) for row in source_rows if isinstance(row, Mapping)]
    counts = repair_counts(repair_rows, source_report)
    source_guardrails = source_guardrail_summary(source_report)
    guardrail_errors = validation_errors_for(source_report=source_report, repair_rows=repair_rows, counts=counts)
    strict_ready_all = counts["input_rows"] > 0 and counts["strict_ready_rows"] == counts["input_rows"]
    status = "READY_FOR_DIAGNOSTIC_STRICT_GATE_RERUN" if strict_ready_all else "EVIDENCE_READINESS_BLOCKED"
    if guardrail_errors:
        status = "FAILED_GUARDRAIL"
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "pdf_evidence_readiness_repair",
        "track": TRACK,
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric": False,
        "answer_generation_run": False,
        "answer_generation_opened": False,
        "retrieval_run": False,
        **counts,
        "repair_rows": repair_rows,
        "strict_gate_rerun": {
            "rerun_performed": False,
            "strict_gate_rerun_performed": False,
            "eligible": counts["strict_ready_rows"] > 0,
            "strict_gate_rerun_eligible": counts["strict_ready_rows"] > 0,
            "generated_strict_silver_rows": counts["generated_strict_silver_rows"],
            "strict_ready_rows": counts["strict_ready_rows"],
            "remaining_fallback_rows": counts["diagnostic_only_fallback_rows"],
            "blocker_reasons_by_row": {
                str(row.get("query_id")): list(row.get("blocked_reasons") or [])
                for row in repair_rows
                if row.get("blocked_reasons")
            },
            "reason": (
                "all rows expose search unit, parser/source metadata, page/bbox/region, and citation locators"
                if strict_ready_all
                else "at least one diagnostic row is strict-ready; remaining rows still block full PDF readiness"
                if counts["strict_ready_rows"] > 0
                else "evidence readiness blocked; missing layout/source-unit/parser metadata remains"
            ),
        },
        "lane_separation": {
            "content_evidence_lane": PDF_CONTENT_EVIDENCE,
            "file_identity_lane": PDF_FILE_IDENTITY,
            "content_and_file_identity_aggregated": False,
        },
        "file_identity_policy": file_identity_policy(source_report),
        "terminology": {
            "blocked_by_missing_layout_count": (
                "backward-compatible alias for blocked_by_missing_layout_or_context_metadata_count"
            ),
            "blocked_by_missing_page_bbox_region_count": "rows missing page, bbox, or region_type",
            "blocked_by_missing_context_metadata_count": (
                "rows missing SearchUnit id/rank, parser/source metadata, nearby paragraphs, or OCR/native-text trust"
            ),
            "blocked_by_missing_layout_or_context_metadata_count": (
                "rows blocked by either page/bbox/region gaps or missing context/source metadata"
            ),
        },
        "source_artifacts": {},
        "artifact_paths": {
            "report_json": "",
            "report_md": "",
        },
        "guardrails": {
            **source_guardrails,
            "official_metric_input_rows_remain_zero": counts["official_metric_input_rows"] == 0,
            "answer_generation_opened": False,
            "official_denominator_registry_opened": False,
            "official_denominator_registry_mutation": False,
            "content_file_identity_lane_merge": source_guardrails["pdf_content_file_lanes_aggregated"],
            "filename_only_identity_acceptance": file_identity_policy(source_report)["filename_only_identity_accepted"],
        },
        "validation": {
            "ok": not guardrail_errors,
            "errors": guardrail_errors,
        },
        "next_safe_actions": [
            "Populate SearchUnit id/rank and parser/source metadata from active artifacts before any strict gate rerun.",
            "Keep filename-only PDF identity blocked by stable_identity_required.",
            "Keep PDF answer generation closed; generated strict rows, if any, are diagnostic only.",
        ],
    }
    return report


def repair_row(row: Mapping[str, Any]) -> dict[str, Any]:
    metadata = row.get("citation_metadata") if isinstance(row.get("citation_metadata"), Mapping) else {}
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    nested_locator = metadata.get("citation_locator") if isinstance(metadata.get("citation_locator"), Mapping) else {}
    citation_locator = locator or nested_locator
    parser_source_metadata = (
        metadata.get("parser_source_metadata")
        if isinstance(metadata.get("parser_source_metadata"), Mapping)
        else metadata.get("source_metadata")
        if isinstance(metadata.get("source_metadata"), Mapping)
        else row.get("source_metadata")
        if isinstance(row.get("source_metadata"), Mapping)
        else {}
    )
    search_unit_id = clean(
        first_present(
            metadata,
            "source_searchunit_id",
            "source_search_unit_id",
            "search_unit_id",
        )
        or row.get("search_unit_id")
        or citation_locator.get("search_unit_id")
    )
    search_unit_rank = (
        first_present(metadata, "source_searchunit_rank", "source_search_unit_rank", "search_unit_rank", "retrieval_rank")
        or row.get("search_unit_rank")
        or row.get("retrieval_rank")
    )
    bbox = first_present(metadata, "bbox") or row.get("bbox") or citation_locator.get("bbox") or []
    page = first_present(metadata, "page") or row.get("page") or citation_locator.get("page")
    physical_page_index = (
        first_present(metadata, "physical_page_index") or row.get("physical_page_index") or citation_locator.get("physical_page_index")
    )
    region_type = clean(first_present(metadata, "region_type") or row.get("region_type") or citation_locator.get("region_type"))
    matched_text = clean(metadata.get("matched_text") or row.get("matched_text"))
    citation_text = clean(metadata.get("citation_text") or row.get("citation_text") or matched_text)
    nearby = list_value(metadata.get("nearby_paragraphs") or row.get("nearby_paragraphs"))
    ocr_confidence = metadata.get("OCR_confidence") if "OCR_confidence" in metadata else row.get("OCR_confidence")
    native_text_available = bool(metadata.get("native_text_available") is True or row.get("native_text_available") is True)
    ocr_fallback_used = bool(metadata.get("OCR_fallback_used") is True or row.get("OCR_fallback_used") is True)
    bbox_source = clean(metadata.get("bbox_source") or row.get("bbox_source"))
    layout_resolution_method = clean(metadata.get("layout_resolution_method") or row.get("layout_resolution_method"))
    source_bound_bbox = bool(metadata.get("source_bound_bbox") is True or row.get("source_bound_bbox") is True)
    source_location = (
        parser_source_metadata.get("location_json")
        if isinstance(parser_source_metadata.get("location_json"), Mapping)
        else {}
    )
    if not source_bound_bbox and same_bbox(bbox, source_location.get("bbox")):
        source_bound_bbox = True
        bbox_source = bbox_source or "local_db.search_unit.location_json.bbox"
        layout_resolution_method = layout_resolution_method or "existing_source_metadata_location_json_bbox"
    source_file_id = clean(metadata.get("source_file_id") or row.get("source_file_id"))
    stable_source_identity = clean(
        metadata.get("document_version_id") or row.get("document_version_id") or row.get("stable_source_identity")
    )
    extracted_artifact_id = clean(metadata.get("extracted_artifact_id") or row.get("extracted_artifact_id"))
    citation_locator_complete = locator_complete(citation_locator)
    blocked_reasons = blocked_reasons_for(
        page=page,
        bbox=bbox,
        region_type=region_type,
        matched_text=matched_text,
        citation_locator_complete=citation_locator_complete,
        source_file_id=source_file_id,
        stable_source_identity=stable_source_identity,
        extracted_artifact_id=extracted_artifact_id,
        search_unit_id=search_unit_id,
        search_unit_rank=search_unit_rank,
        parser_source_metadata=parser_source_metadata,
        nearby_paragraphs=nearby,
        ocr_confidence=ocr_confidence,
        native_text_available=native_text_available,
        source_bound_bbox=source_bound_bbox,
    )
    strict_ready = not blocked_reasons
    return {
        "schema_version": ROW_SCHEMA_VERSION,
        "query_id": clean(row.get("query_id")),
        "track": TRACK,
        "content_evidence_lane": PDF_CONTENT_EVIDENCE,
        "file_identity_lane": {
            "lane": PDF_FILE_IDENTITY,
            "blocker": STABLE_IDENTITY_REQUIRED,
            "merged_with_content_evidence": False,
            "filename_only_identity_accepted": False,
        },
        "source_file_id": source_file_id,
        "document_version_id": stable_source_identity,
        "stable_source_identity": stable_source_identity,
        "extracted_artifact_id": extracted_artifact_id,
        "search_unit_id": search_unit_id,
        "search_unit_rank": int_or_none(search_unit_rank),
        "retrieval_rank": int_or_none(first_present(metadata, "retrieval_rank") or search_unit_rank),
        "parser_version": clean(first_present(metadata, "parser_version") or first_present(parser_source_metadata, "parser_version", "parser")),
        "source_metadata": parser_source_metadata,
        "page": int_or_none(page),
        "physical_page_index": int_or_none(physical_page_index),
        "bbox": bbox if isinstance(bbox, list) else [],
        "bbox_source": bbox_source,
        "layout_resolution_method": layout_resolution_method,
        "source_bound_bbox": source_bound_bbox,
        "region_type": region_type,
        "matched_text": matched_text,
        "citation_text": citation_text,
        "citation_locator": citation_locator,
        "citation_locator_complete": citation_locator_complete,
        "section_heading": clean(metadata.get("section_heading")),
        "table_caption_footnote": clean(metadata.get("table_caption_footnote")),
        "nearby_paragraphs": nearby,
        "OCR_confidence": ocr_confidence,
        "native_text_available": native_text_available,
        "OCR_fallback_used": ocr_fallback_used,
        "diagnostic_only": True,
        "official_metric_input": row.get("official_metric_input") if "official_metric_input" in row else False,
        "promotion_evidence": False,
        "strict_ready": strict_ready,
        "blocked_reasons": blocked_reasons,
        "blocker_classifications": blocker_classifications_for(
            strict_ready=strict_ready,
            blocked_reasons=blocked_reasons,
            source_file_id=source_file_id,
            stable_source_identity=stable_source_identity,
            extracted_artifact_id=extracted_artifact_id,
        ),
        "metadata_resolution": {
            "resolved_fields": resolved_fields_for(
                {
                    "source_file_id": source_file_id,
                    "document_version_id": stable_source_identity,
                    "search_unit_id": search_unit_id,
                    "search_unit_rank": int_or_none(search_unit_rank),
                    "parser_version": clean(
                        first_present(metadata, "parser_version")
                        or first_present(parser_source_metadata, "parser_version", "parser")
                    ),
                    "source_metadata": parser_source_metadata,
                    "page": int_or_none(page),
                    "physical_page_index": int_or_none(physical_page_index),
                    "bbox": bbox if isinstance(bbox, list) else [],
                    "region_type": region_type,
                    "nearby_paragraphs": nearby,
                    "native_text_available": native_text_available,
                    "OCR_confidence": ocr_confidence,
                }
            ),
            "missing_fields": blocked_reasons,
        },
    }


def blocked_reasons_for(
    *,
    page: Any,
    bbox: Any,
    region_type: str,
    matched_text: str,
    citation_locator_complete: bool,
    source_file_id: str,
    stable_source_identity: str,
    extracted_artifact_id: str,
    search_unit_id: str,
    search_unit_rank: Any,
    parser_source_metadata: Mapping[str, Any],
    nearby_paragraphs: Sequence[Any],
    ocr_confidence: Any,
    native_text_available: bool,
    source_bound_bbox: bool,
) -> list[str]:
    reasons: list[str] = []
    layout_complete = nonempty(page) and nonempty(bbox) and region_type
    if not layout_complete:
        reasons.append("missing_layout")
    elif not source_bound_bbox:
        reasons.append("missing_source_bound_bbox")
    if not matched_text:
        reasons.append("missing_matched_text")
    if not citation_locator_complete:
        reasons.append("missing_or_incomplete_citation_locator")
    if not source_file_id:
        reasons.append("missing_source_file_id")
    if not stable_source_identity:
        reasons.append("missing_stable_source_identity")
    if not extracted_artifact_id:
        reasons.append("missing_extracted_artifact_id")
    if not search_unit_id:
        reasons.append("missing_search_unit_id")
    if not nonempty(search_unit_rank):
        reasons.append("missing_search_unit_rank")
    if not parser_source_metadata:
        reasons.append("missing_parser_source_metadata")
    if not nearby_paragraphs:
        reasons.append("missing_nearby_paragraphs")
    if not (nonempty(ocr_confidence) or native_text_available):
        reasons.append("missing_ocr_confidence_or_native_text")
    return reasons


def blocker_classifications_for(
    *,
    strict_ready: bool,
    blocked_reasons: Sequence[str],
    source_file_id: str,
    stable_source_identity: str,
    extracted_artifact_id: str,
) -> list[str]:
    if strict_ready:
        return ["strict_ready_diagnostic_only"]
    reasons = set(blocked_reasons)
    classifications: set[str] = {"diagnostic_only_fallback"}
    if {"missing_search_unit_id", "missing_search_unit_rank"} & reasons:
        classifications.add("blocked_missing_search_unit")
    if "missing_parser_source_metadata" in reasons:
        classifications.add("blocked_missing_parser_source_metadata")
    if "missing_layout" in reasons or "missing_source_bound_bbox" in reasons or "missing_or_incomplete_citation_locator" in reasons:
        classifications.add("blocked_missing_layout_bbox_region")
    if "missing_source_bound_bbox" in reasons:
        classifications.add("blocked_missing_source_bound_bbox")
    if "missing_nearby_paragraphs" in reasons:
        classifications.add("blocked_missing_nearby_paragraphs")
    if "missing_ocr_confidence_or_native_text" in reasons:
        classifications.add("blocked_missing_ocr_or_native_text_trust")
    if "missing_stable_source_identity" in reasons or not stable_source_identity:
        classifications.add("blocked_file_identity_ambiguity")
    if not source_file_id or not stable_source_identity or not extracted_artifact_id:
        classifications.add("blocked_unresolved_source_artifact")
    return [name for name in BLOCKER_CLASSIFICATION_ORDER if name in classifications]


def resolved_fields_for(fields: Mapping[str, Any]) -> list[str]:
    return [key for key, value in fields.items() if nonempty(value)]


def same_bbox(left: Any, right: Any) -> bool:
    if not isinstance(left, list) or not isinstance(right, list) or len(left) != len(right):
        return False
    return [str(value) for value in left] == [str(value) for value in right]


def repair_counts(rows: Sequence[Mapping[str, Any]], source_report: Mapping[str, Any]) -> dict[str, int]:
    input_rows = len(rows)
    source_counts = nested_mapping(source_report, "counts")
    file_identity_count = int_value(nested_mapping(source_report, "file_identity_policy").get("blocked_query_ids_count"))
    if file_identity_count == 0:
        blocked_ids = nested_mapping(source_report, "file_identity_policy").get("blocked_query_ids")
        file_identity_count = len(blocked_ids) if isinstance(blocked_ids, list) else 0
    if file_identity_count == 0:
        file_identity_count = int_value(nested_mapping(source_report, "counts").get("rows_blocked_by_file_identity_ambiguity"))
    strict_ready_rows = sum(1 for row in rows if row.get("strict_ready") is True)
    row_reason_sets = [set(row.get("blocked_reasons", [])) for row in rows]
    computed_missing_layout = sum(1 for reasons in row_reason_sets if "missing_layout" in reasons)
    computed_missing_source_bound_bbox = sum(1 for reasons in row_reason_sets if "missing_source_bound_bbox" in reasons)
    computed_missing_context = sum(1 for reasons in row_reason_sets if reasons & CONTEXT_METADATA_BLOCKERS)
    computed_missing_layout_or_context = sum(
        1
        for reasons in row_reason_sets
        if "missing_layout" in reasons or "missing_source_bound_bbox" in reasons or reasons & CONTEXT_METADATA_BLOCKERS
    )
    source_layout_or_context = int_value(source_counts.get("rows_blocked_by_missing_layout")) if input_rows == 0 else 0
    official_rows = int_value(source_report.get("official_metric_input_rows")) + int_value(
        source_counts.get("official_metric_input_rows")
    ) + sum(
        1 for row in rows if row.get("official_metric_input") is not False
    )
    return {
        "input_rows": input_rows,
        "complete_page_bbox_region_count": sum(
            1 for row in rows if nonempty(row.get("page")) and nonempty(row.get("bbox")) and clean(row.get("region_type"))
        ),
        "matched_text_count": sum(1 for row in rows if clean(row.get("matched_text"))),
        "nearby_paragraph_count": sum(1 for row in rows if nonempty(row.get("nearby_paragraphs"))),
        "OCR_confidence_available_count": sum(1 for row in rows if nonempty(row.get("OCR_confidence"))),
        "native_text_available_count": sum(1 for row in rows if row.get("native_text_available") is True),
        "native_or_ocr_trust_available_count": sum(
            1 for row in rows if nonempty(row.get("OCR_confidence")) or row.get("native_text_available") is True
        ),
        "citation_locator_complete_count": sum(1 for row in rows if row.get("citation_locator_complete") is True),
        "search_unit_id_available_count": sum(1 for row in rows if clean(row.get("search_unit_id"))),
        "parser_source_metadata_available_count": sum(1 for row in rows if nonempty(row.get("source_metadata"))),
        "file_identity_ambiguous_count": file_identity_count,
        "strict_ready_rows": strict_ready_rows,
        "generated_strict_silver_rows": strict_ready_rows,
        "diagnostic_only_fallback_rows": max(input_rows - strict_ready_rows, 0),
        "blocked_by_missing_layout_count": source_layout_or_context or computed_missing_layout_or_context,
        "blocked_by_missing_page_bbox_region_count": computed_missing_layout,
        "blocked_by_missing_source_bound_bbox_count": computed_missing_source_bound_bbox,
        "blocked_by_missing_context_metadata_count": computed_missing_context,
        "blocked_by_missing_layout_or_context_metadata_count": source_layout_or_context
        or computed_missing_layout_or_context,
        "blocked_by_missing_source_unit_count": sum(
            1
            for row in rows
            if {"missing_search_unit_id", "missing_search_unit_rank"} & set(row.get("blocked_reasons", []))
        ),
        "blocked_by_file_identity_count": file_identity_count,
        "official_metric_input_rows": official_rows,
    }


def validation_errors_for(
    *,
    source_report: Mapping[str, Any],
    repair_rows: Sequence[Mapping[str, Any]],
    counts: Mapping[str, int],
) -> list[str]:
    errors: list[str] = []
    if source_report.get("official_metric") is True:
        errors.append("source readiness report must keep official_metric=false")
    if source_report.get("promotion_evidence") is True:
        errors.append("source readiness report must keep promotion_evidence=false")
    if source_report.get("answer_generation_run") is True:
        errors.append("PDF answer generation must remain closed")
    source_guardrails = source_guardrail_summary(source_report)
    for key in PROTECTED_SOURCE_GUARDRAILS:
        if source_guardrails.get(key) is True:
            errors.append(f"source guardrail violation: {key}=true")
    if int_value(counts.get("official_metric_input_rows")) != 0:
        errors.append("official_metric_input_rows must remain 0")
    lane = nested_mapping(source_report, "lane_separation")
    if lane.get("content_and_file_identity_aggregated") is True:
        errors.append("PDF CONTENT evidence and FILE identity lanes must not be merged")
    policy = nested_mapping(source_report, "file_identity_policy")
    if policy.get("generic_filename_only_identity_blocked") is False or policy.get("filename_only_identity_accepted") is True:
        errors.append("filename-only PDF identity must remain blocked")
    for row in repair_rows:
        if row.get("official_metric_input") is not False:
            errors.append(f"{row.get('query_id')} official_metric_input must be false")
        if row.get("promotion_evidence") is not False:
            errors.append(f"{row.get('query_id')} promotion_evidence must be false")
    return errors


def source_guardrail_summary(source_report: Mapping[str, Any]) -> dict[str, bool]:
    guardrails = nested_mapping(source_report, "guardrails")
    source_guardrails = nested_mapping(source_report, "source_guardrails")
    lane = nested_mapping(source_report, "lane_separation")
    counts = nested_mapping(source_report, "counts")
    summary: dict[str, bool] = {}
    for key in PROTECTED_SOURCE_GUARDRAILS:
        summary[key] = bool(guardrails.get(key) is True or source_guardrails.get(key) is True)
    summary["answer_generation_run"] = summary["answer_generation_run"] or source_report.get("answer_generation_run") is True
    summary["promotion_evidence_created"] = (
        summary["promotion_evidence_created"] or source_report.get("promotion_evidence") is True
    )
    summary["pdf_content_file_lanes_aggregated"] = (
        summary["pdf_content_file_lanes_aggregated"] or lane.get("content_and_file_identity_aggregated") is True
    )
    summary["official_denominator_opened_or_frozen"] = (
        summary["official_denominator_opened_or_frozen"]
        or source_report.get("official_metric") is True
        or int_value(source_report.get("official_metric_input_rows")) > 0
        or int_value(counts.get("official_metric_input_rows")) > 0
    )
    return summary


def file_identity_policy(source_report: Mapping[str, Any]) -> dict[str, Any]:
    policy = nested_mapping(source_report, "file_identity_policy")
    blocked_ids = policy.get("blocked_query_ids") if isinstance(policy.get("blocked_query_ids"), list) else []
    if not blocked_ids:
        blocked_ids = nested_mapping(source_report, "lane_separation", PDF_FILE_IDENTITY).get(
            "stable_identity_required_query_ids", []
        )
        if not isinstance(blocked_ids, list):
            blocked_ids = []
    return {
        "generic_filename_only_identity_blocked": policy.get("generic_filename_only_identity_blocked") is not False,
        "blocker": clean(policy.get("blocker") or STABLE_IDENTITY_REQUIRED),
        "blocked_query_ids": blocked_ids,
        "filename_only_identity_accepted": policy.get("filename_only_identity_accepted") is True,
    }


def locator_complete(locator: Mapping[str, Any]) -> bool:
    return bool(
        clean(locator.get("file"))
        and clean(locator.get("document_version_id"))
        and nonempty(locator.get("page"))
        and clean(locator.get("region_type"))
        and (nonempty(locator.get("bbox")) or clean(locator.get("search_unit_id")))
    )


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# PDF Evidence Readiness Repair Report",
        "",
        f"- Status: `{report['status']}`",
        "- Scope: diagnostic-only PDF evidence readiness repair; answer generation remains closed.",
        f"- Input rows: `{report['input_rows']}`",
        f"- Complete page/bbox/region: `{report['complete_page_bbox_region_count']}`",
        f"- Matched text: `{report['matched_text_count']}`",
        f"- Nearby paragraphs: `{report['nearby_paragraph_count']}`",
        f"- OCR confidence available: `{report['OCR_confidence_available_count']}`",
        f"- Native text available: `{report['native_text_available_count']}`",
        f"- Citation locator complete: `{report['citation_locator_complete_count']}`",
        f"- SearchUnit id available: `{report['search_unit_id_available_count']}`",
        f"- Parser/source metadata available: `{report['parser_source_metadata_available_count']}`",
        f"- File identity ambiguous: `{report['file_identity_ambiguous_count']}`",
        f"- Strict ready rows: `{report['strict_ready_rows']}`",
        f"- Diagnostic-only fallback rows: `{report['diagnostic_only_fallback_rows']}`",
        f"- Missing page/bbox/region rows: `{report['blocked_by_missing_page_bbox_region_count']}`",
        f"- Missing context/source metadata rows: `{report['blocked_by_missing_context_metadata_count']}`",
        "- Missing layout/context metadata rows: "
        f"`{report['blocked_by_missing_layout_or_context_metadata_count']}`",
        f"- Official metric input rows: `{report['official_metric_input_rows']}`",
        f"- Answer generation opened: `{str(report['answer_generation_opened']).lower()}`",
        f"- Promotion evidence: `{str(report['promotion_evidence']).lower()}`",
        "",
        "## Next Safe Actions",
        "",
    ]
    for action in report["next_safe_actions"]:
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "## Terminology",
            "",
            "- `blocked_by_missing_layout_count` is a backward-compatible alias for layout-or-context metadata blockers.",
            "- `blocked_by_missing_page_bbox_region_count` counts only page, bbox, or region_type gaps.",
            "- `blocked_by_missing_context_metadata_count` counts SearchUnit, parser/source, nearby paragraph, and OCR/native-text trust gaps.",
        ]
    )
    return "\n".join(lines) + "\n"


def file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() else None,
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def first_present(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if nonempty(value):
            return value
    return None


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else ([] if value in (None, "") else [value])


def nested_mapping(payload: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return current if isinstance(current, Mapping) else {}


def int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def int_value(value: Any) -> int:
    parsed = int_or_none(value)
    return parsed if parsed is not None else 0


def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    return True


def clean(value: Any) -> str:
    return str(value or "").strip()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
