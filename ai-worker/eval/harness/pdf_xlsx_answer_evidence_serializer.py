"""Serialize PDF/XLSX answer-shape inputs into content evidence objects.

This module is diagnostic-only. It does not run retrieval, expand parsers,
mutate SearchUnit, update candidate artifacts, or change official denominators.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = AI_WORKER_ROOT.parent
DEFAULT_INPUTS = (
    AI_WORKER_ROOT
    / "eval"
    / "artifacts"
    / "eval_runs"
    / "pdf_xlsx_answer_shape_local_llm_20260506T015846Z"
    / "answer_generation_inputs.jsonl"
)

SCHEMA_VERSION = "rag_pdf_xlsx_answer_evidence_objects_v1"
POLICY_SHAPE = "NOT_ANSWERABLE_OR_POLICY_PENDING"
DEFAULT_MAX_SUMMARY_CHARS = 700
XLSX_ALLOWED_SHAPES = {
    "TABLE_ROW_VALUE",
    "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT",
    "LOCATION_PLUS_CONTENT",
    "EVIDENCE_LOCATOR_WITH_CONTENT",
    "YES_NO_WITH_EVIDENCE",
}
PDF_ALLOWED_SHAPES = {
    "PDF_SECTION_WITH_SUMMARY",
    "PDF_TABLE_VALUE_WITH_CONTEXT",
    "LOCATION_PLUS_CONTENT",
    "EVIDENCE_LOCATOR_WITH_CONTENT",
    "YES_NO_WITH_EVIDENCE",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_rows = read_jsonl(Path(args.inputs))
    evidence_rows = serialize_input_rows(
        input_rows,
        run_id=args.run_id or utc_run_id(),
        max_summary_chars=args.max_summary_chars,
    )
    write_jsonl(Path(args.output), evidence_rows)
    print_json(
        {
            "status": "PASS",
            "schema_version": SCHEMA_VERSION,
            "output": repo_relative(Path(args.output)),
            "row_count": len(evidence_rows),
            "answer_generation_allowed_count": sum(
                1 for row in evidence_rows if parse_bool(row.get("answer_generation_allowed"))
            ),
            "policy_pending_count": sum(1 for row in evidence_rows if parse_bool(row.get("policy_pending"))),
            "content_summary_missing_count": sum(
                1 for row in evidence_rows if not clean(row.get("content_summary"))
            ),
            "promotion_evidence": False,
            "external_live_llm_run": False,
            "optional_judge_run": False,
        }
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", default=str(DEFAULT_INPUTS))
    parser.add_argument("--output", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--max-summary-chars", type=int, default=DEFAULT_MAX_SUMMARY_CHARS)
    return parser.parse_args(argv)


def serialize_input_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    run_id: str,
    max_summary_chars: int = DEFAULT_MAX_SUMMARY_CHARS,
) -> list[dict[str, Any]]:
    return [
        serialize_input_row(row, run_id=run_id, max_summary_chars=max_summary_chars)
        for row in rows
    ]


def serialize_input_row(
    row: Mapping[str, Any],
    *,
    run_id: str,
    max_summary_chars: int = DEFAULT_MAX_SUMMARY_CHARS,
) -> dict[str, Any]:
    context = row.get("context") if isinstance(row.get("context"), Mapping) else {}
    policy = row.get("policy") if isinstance(row.get("policy"), Mapping) else {}
    track = clean(row.get("track")).upper()
    expected_shape = clean(row.get("expected_answer_shape"))
    malformed_input = "context" in row and not isinstance(row.get("context"), Mapping)
    policy_pending, policy_pending_reason = policy_pending_state(row, policy)
    if track == "XLSX":
        evidence = xlsx_evidence_object(
            row,
            context,
            policy_pending=policy_pending,
            max_summary_chars=max_summary_chars,
        )
    elif track == "PDF":
        evidence = pdf_evidence_object(row, context, max_summary_chars=max_summary_chars)
    else:
        evidence = {"evidence_type": clean(track).lower() or "unknown"}
        malformed_input = True
    content_summary = clean(evidence.get("content_summary"))
    content_available = content_evidence_available(evidence)
    keyword_only = content_is_keyword_only(content_summary, row)
    locator_only = evidence_has_locator(evidence) and not content_available
    evidence_quality = evidence_quality_flags(
        evidence,
        track=track,
        policy_pending=policy_pending,
        keyword_only=keyword_only,
        locator_only=locator_only,
        malformed_input=malformed_input,
    )
    blocker = fail_closed_reason_for(
        track=track,
        expected_shape=expected_shape,
        evidence=evidence,
        evidence_quality=evidence_quality,
        content_available=content_available,
        policy_pending=policy_pending,
        keyword_only=keyword_only,
        locator_only=locator_only,
        malformed_input=malformed_input,
    )
    allowed = not blocker

    row_out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "source_input_run_id": clean(row.get("run_id")),
        "row_index": row.get("row_index"),
        "track": track,
        "query_id": clean(row.get("query_id")),
        "query": clean(row.get("query")),
        "bucket": clean(row.get("bucket")),
        "review_group": clean(row.get("review_group")),
        "expected_answer_shape": expected_shape,
        "expected_answer_text": clean(row.get("expected_answer_text")),
        "must_contain_terms": string_list(row.get("must_contain_terms")),
        "policy": dict(policy),
        "policy_pending": policy_pending,
        "policy_pending_reason": policy_pending_reason,
        "diagnostic_only": parse_bool(policy.get("diagnostic_only")),
        "answer_allowed": allowed,
        "answer_generation_allowed": allowed,
        "answer_generation_blocker": blocker,
        "answer_disallowed_reason": blocker,
        "fail_closed_reason": blocker,
        "keyword_only_evidence": keyword_only,
        "locator_only_evidence": locator_only,
        "content_window_available": content_available,
        "content_window_basis": content_window_basis(evidence),
        "content_source_fields": string_list(evidence.get("content_source_fields")),
        "evidence_quality": evidence_quality,
        "content_summary": content_summary,
        "evidence_object": evidence,
        "context_available": parse_bool(context.get("context_available")),
        "context_has_expected_terms": parse_bool(context.get("context_has_expected_terms")),
        "context_errors": string_list(context.get("context_errors")),
        "retrieval_context": context.get("retrieval_context") if isinstance(context.get("retrieval_context"), Mapping) else {},
        "dry_run_preview_used_as_actual_answer": False,
        "local_llm_run": False,
        "external_live_llm_run": False,
        "optional_judge_run": False,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "guardrails": diagnostic_guardrails(),
    }
    return row_out


def xlsx_evidence_object(
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    policy_pending: bool,
    max_summary_chars: int,
) -> dict[str, Any]:
    locator = context.get("locator") if isinstance(context.get("locator"), Mapping) else {}
    extracted = empty_xlsx_extraction() if policy_pending else extract_xlsx_content_fields(row, context)
    value_context = [] if policy_pending else mapping_list(context.get("value_context"))
    first_value = value_context[0] if value_context else {}
    header_context = [] if policy_pending else unique_strings(
        [
            *string_list(context.get("header_context")),
            *string_list(context.get("headers")),
            *extracted["header_context"],
        ]
    )
    nearby_rows = [] if policy_pending else unique_strings(
        [
            *xlsx_table_strings(string_list(context.get("nearby_table_context")), row),
            *xlsx_table_strings(string_list(context.get("nearby_rows")), row),
            *extracted["nearby_rows"],
        ]
    )
    table_context = [] if policy_pending else unique_strings(
        [
            *xlsx_table_strings(string_list(context.get("table_context")), row),
            *xlsx_table_strings(string_list(context.get("table_or_value_context")), row),
            *extracted["table_context"],
        ]
    )
    matched_keyword = "" if policy_pending else matched_keyword_for(row, context)
    row_values = merge_mapping_lists(xlsx_row_values(value_context, []), extracted["row_values"])
    column_values = extracted["column_values"]
    cell_values = extracted["cell_values"]
    row_label = (
        clean(first_value.get("row_label"))
        or clean(context.get("row_label"))
        or first_mapping_value(row_values, "row_label")
    )
    column_label = (
        clean(first_value.get("column_label"))
        or clean(context.get("column_label"))
        or first_mapping_value(row_values, "column_label")
        or first_mapping_value(cell_values, "column_label")
    )
    value = clean(first_value.get("value")) or first_mapping_value(row_values, "value") or first_mapping_value(
        cell_values, "value"
    )
    sheet = clean(context.get("sheet_name") or locator.get("sheet"))
    cell_range = clean(context.get("cell_range") or locator.get("range") or locator.get("cell"))
    table_title = clean(context.get("table_id")) or clean(locator.get("table"))
    inferred_table_context = infer_xlsx_table_context(table_title, header_context, [*table_context, *nearby_rows])
    summary = summarize_xlsx_content(
        sheet=sheet,
        cell_range=cell_range,
        table_title=table_title,
        row_label=row_label,
        column_label=column_label,
        value=value,
        row_values=row_values,
        column_values=column_values,
        cell_values=cell_values,
        header_context=header_context,
        table_context=table_context,
        nearby_rows=nearby_rows,
        input_summaries=extracted["content_summaries"],
        max_summary_chars=max_summary_chars,
    )
    content_source_fields = unique_strings(
        [
            *extracted["content_source_fields"],
            *(
                ["context.value_context"]
                if any(clean(item.get("value")) for item in value_context)
                else []
            ),
        ]
    )
    return compact_dict(
        {
            "evidence_type": "xlsx",
            "matched_keyword": matched_keyword,
            "file_name": clean(context.get("file_name") or locator.get("file")),
            "document_version_id": clean(locator.get("document_version_id") or locator.get("docv")),
            "sheet": sheet,
            "range": cell_range,
            "cell": clean(locator.get("cell") or first_value.get("cell")),
            "table_title": table_title,
            "inferred_table_context": inferred_table_context,
            "row_label": row_label,
            "column_label": column_label,
            "column_labels": [column_label] if column_label else header_context,
            "value": value,
            "row_values": row_values,
            "column_values": column_values,
            "cell_values": cell_values,
            "header_context": header_context,
            "table_context": table_context[:8],
            "nearby_row_context": nearby_rows[:8],
            "nearby_rows": nearby_rows[:8],
            "content_summary": summary,
            "locator": compact_dict(dict(locator)),
            "content_source": first_nonempty(content_source_fields),
            "content_source_fields": content_source_fields,
            "unsupported_content_field_count": extracted["unsupported_content_field_count"],
            "candidate_content_field_count": extracted["candidate_content_field_count"],
        }
    )


def pdf_evidence_object(
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    max_summary_chars: int,
) -> dict[str, Any]:
    locator = context.get("locator") if isinstance(context.get("locator"), Mapping) else {}
    paragraph_context = string_list(context.get("paragraph_context"))
    table_context = string_list(context.get("table_or_value_context"))
    sentence_context = string_list(context.get("sentence_context"))
    matched_keyword = matched_keyword_for(row, context)
    text_source = first_nonempty([*table_context, *paragraph_context, *sentence_context])
    summary = summarize_pdf_content(text_source, max_summary_chars=max_summary_chars)
    row_label, column_label, value, unit = infer_pdf_table_parts(text_source, row)
    nearby_text_window = nearby_pdf_text_window(table_context, paragraph_context, sentence_context, max_summary_chars)
    section = clean(context.get("section_id"))
    return compact_dict(
        {
            "evidence_type": "pdf",
            "matched_keyword": matched_keyword,
            "file_name": clean(context.get("file_name") or locator.get("file")),
            "document_version_id": clean(locator.get("document_version_id") or locator.get("docv")),
            "page": clean(context.get("page_no") or locator.get("page")),
            "page_label": clean(context.get("page_label") or locator.get("page_label")),
            "physical_page_index": clean(context.get("physical_page_index") or locator.get("physical_page_index")),
            "bbox": context.get("bbox") if context.get("bbox") not in (None, "") else locator.get("bbox"),
            "section": section,
            "section_path": [section] if section else [],
            "paragraph_block_text": truncate(clean_whitespace(text_source), max_summary_chars),
            "paragraph_or_table_text": truncate(clean_whitespace(text_source), max_summary_chars),
            "row_label": row_label,
            "column_label": column_label,
            "column_labels": [column_label] if column_label else [],
            "value": value,
            "unit": unit,
            "nearby_text_window": nearby_text_window,
            "content_summary": summary,
            "locator": compact_dict(dict(locator)),
            "content_source": "table_or_value_context"
            if table_context
            else "paragraph_context"
            if paragraph_context
            else "sentence_context"
            if sentence_context
            else "",
        }
    )


def summarize_xlsx_content(
    *,
    sheet: str,
    cell_range: str,
    table_title: str,
    row_label: str,
    column_label: str,
    value: str,
    row_values: list[dict[str, str]],
    column_values: list[dict[str, str]],
    cell_values: list[dict[str, str]],
    header_context: list[str],
    table_context: list[str],
    nearby_rows: list[str],
    input_summaries: list[str],
    max_summary_chars: int,
) -> str:
    if row_label and column_label and value:
        prefix = f"Row '{row_label}' / column '{column_label}' has value '{value}'."
    elif cell_values:
        cell_value = cell_values[0]
        cell = clean(cell_value.get("cell"))
        value_text = clean(cell_value.get("value")) or clean(cell_value.get("row_text"))
        prefix = f"Cell {cell or 'unknown cell'} has value '{value_text}'."
    elif row_values:
        first_row = row_values[0]
        row_text = clean(first_row.get("row_text"))
        value_text = clean(first_row.get("value"))
        if row_text:
            prefix = f"Visible row context: {row_text}"
        elif value_text:
            row_part = clean(first_row.get("row_label")) or "row"
            column_part = clean(first_row.get("column_label")) or "value"
            prefix = f"{row_part} / {column_part} has value '{value_text}'."
        else:
            return ""
    elif column_values:
        first_column = column_values[0]
        column_text = clean(first_column.get("column_text")) or clean(first_column.get("row_text"))
        value_text = clean(first_column.get("value"))
        if column_text:
            prefix = f"Visible column context: {column_text}"
        elif value_text:
            prefix = f"Column '{clean(first_column.get('column_label')) or 'value'}' includes value '{value_text}'."
        else:
            return ""
    elif table_context:
        prefix = f"Visible table context: {table_context[0]}"
    elif nearby_rows:
        prefix = f"Range {cell_range or 'unknown range'} contains visible row context: {nearby_rows[0]}"
    elif input_summaries:
        prefix = f"Content summary from input evidence: {input_summaries[0]}"
    else:
        return ""
    scope = []
    if table_title:
        scope.append(f"table '{table_title}'")
    if sheet:
        scope.append(f"sheet '{sheet}'")
    if cell_range:
        scope.append(f"range {cell_range}")
    suffix = f" Evidence scope: {', '.join(scope)}." if scope else ""
    if header_context and not (row_label and column_label and value):
        suffix += f" Major headers: {', '.join(header_context[:8])}."
    return truncate(clean_whitespace(prefix + suffix), max_summary_chars)


def summarize_pdf_content(text: str, *, max_summary_chars: int) -> str:
    cleaned = clean_whitespace(text)
    if not cleaned:
        return ""
    sentences = [clean(item) for item in re.split(r"(?<=[.!?。！？])\s+|\n+", cleaned) if clean(item)]
    selected = first_nonempty(sentences) or cleaned
    return truncate(selected, max_summary_chars)


def infer_pdf_table_parts(text: str, row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    del row
    numbers = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", text)
    row_label = ""
    column_label = ""
    if numbers:
        prefix = clean(text.split(numbers[0], 1)[0])
        if prefix and len(prefix) <= 120:
            row_label = prefix.strip(" :-|")
    value = first_nonempty(numbers)
    unit_match = re.search(r"\(([^)]{1,40})\)", text)
    unit = clean(unit_match.group(1)) if unit_match else ""
    return row_label, column_label, value, unit


def extract_xlsx_content_fields(row: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    extracted = empty_xlsx_extraction()
    collect_xlsx_value(context.get("value_context"), "context.value_context", row, extracted)
    collect_xlsx_value(context.get("row_values"), "context.row_values", row, extracted)
    collect_xlsx_value(context.get("candidate_rows"), "context.candidate_rows", row, extracted)
    collect_xlsx_value(context.get("column_values"), "context.column_values", row, extracted)
    collect_xlsx_value(context.get("cell_values"), "context.cell_values", row, extracted)
    collect_xlsx_value(context.get("candidate_cells"), "context.candidate_cells", row, extracted)
    collect_xlsx_value(context.get("table_context"), "context.table_context", row, extracted)
    collect_xlsx_value(context.get("nearby_rows"), "context.nearby_rows", row, extracted)
    collect_xlsx_value(context.get("nearby_table_context"), "context.nearby_table_context", row, extracted)
    collect_xlsx_value(context.get("header_context"), "context.header_context", row, extracted)
    walk_xlsx_content(context, "context", row, extracted)
    extracted["row_values"] = unique_mappings(extracted["row_values"])[:16]
    extracted["column_values"] = unique_mappings(extracted["column_values"])[:12]
    extracted["cell_values"] = unique_mappings(extracted["cell_values"])[:12]
    for key in ("header_context", "nearby_rows", "table_context", "content_summaries", "content_source_fields"):
        extracted[key] = unique_strings(extracted[key])[:16]
    return extracted


def empty_xlsx_extraction() -> dict[str, Any]:
    return {
        "row_values": [],
        "column_values": [],
        "cell_values": [],
        "header_context": [],
        "nearby_rows": [],
        "table_context": [],
        "content_summaries": [],
        "content_source_fields": [],
        "candidate_content_field_count": 0,
        "unsupported_content_field_count": 0,
    }


def walk_xlsx_content(value: Any, path: str, row: Mapping[str, Any], extracted: dict[str, Any]) -> None:
    if xlsx_path_excluded(path):
        return
    key = path_key(path)
    if isinstance(value, Mapping):
        if xlsx_mapping_is_locator(value):
            return
        if xlsx_key_has_hint(key, ("row", "record", "candidate")):
            before = len(extracted["row_values"])
            row_value = normalize_xlsx_row_mapping(value, path, row)
            if row_value:
                extracted["row_values"].append(row_value)
                add_content_source(extracted, path)
            elif before == len(extracted["row_values"]) and contentish_key(key):
                extracted["unsupported_content_field_count"] += 1
        if xlsx_key_has_hint(key, ("cell",)):
            cell_value = normalize_xlsx_cell_mapping(value, path, row)
            if cell_value:
                extracted["cell_values"].append(cell_value)
                add_content_source(extracted, path)
        if xlsx_key_has_hint(key, ("column", "col")):
            column_value = normalize_xlsx_column_mapping(value, path, row)
            if column_value:
                extracted["column_values"].append(column_value)
                add_content_source(extracted, path)
        for child_key, child_value in value.items():
            walk_xlsx_content(child_value, f"{path}.{child_key}", row, extracted)
        return
    if isinstance(value, list):
        collect_xlsx_value(value, path, row, extracted)
        for index, item in enumerate(value):
            walk_xlsx_content(item, f"{path}[{index}]", row, extracted)
        return
    collect_xlsx_scalar(clean(value), path, row, extracted)


def collect_xlsx_value(value: Any, path: str, row: Mapping[str, Any], extracted: dict[str, Any]) -> None:
    if xlsx_path_excluded(path) or value in (None, "", [], {}):
        return
    key = path_key(path)
    if isinstance(value, Mapping):
        if xlsx_mapping_is_locator(value):
            return
        row_value = normalize_xlsx_row_mapping(value, path, row)
        cell_value = normalize_xlsx_cell_mapping(value, path, row)
        column_value = normalize_xlsx_column_mapping(value, path, row)
        if row_value and (xlsx_key_has_hint(key, ("row", "value_context", "candidate")) or not cell_value):
            extracted["row_values"].append(row_value)
            add_content_source(extracted, path)
        if cell_value and xlsx_key_has_hint(key, ("cell", "value_context")):
            extracted["cell_values"].append(cell_value)
            add_content_source(extracted, path)
        if column_value and xlsx_key_has_hint(key, ("column", "col")):
            extracted["column_values"].append(column_value)
            add_content_source(extracted, path)
        if not any((row_value, cell_value, column_value)) and contentish_key(key):
            extracted["unsupported_content_field_count"] += 1
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            collect_xlsx_value(item, f"{path}[{index}]", row, extracted)
        return
    collect_xlsx_scalar(clean(value), path, row, extracted)


def collect_xlsx_scalar(value: str, path: str, row: Mapping[str, Any], extracted: dict[str, Any]) -> None:
    if not xlsx_text_is_content(value, row):
        return
    key = path_key(path)
    extracted["candidate_content_field_count"] += 1
    if xlsx_key_has_hint(key, ("header", "column_label", "columns")):
        extracted["header_context"].append(value)
        add_content_source(extracted, path)
    elif xlsx_key_has_hint(key, ("nearby", "row_context", "row_text", "table_row")):
        if not xlsx_table_text_is_content(value, row):
            extracted["unsupported_content_field_count"] += 1
            return
        extracted["nearby_rows"].append(value)
        add_content_source(extracted, path)
    elif xlsx_key_has_hint(key, ("table", "markdown", "snippet", "excerpt", "text", "content", "summary")):
        if not xlsx_table_text_is_content(value, row):
            extracted["unsupported_content_field_count"] += 1
            return
        if xlsx_key_has_hint(key, ("summary", "content_summary")):
            extracted["content_summaries"].append(value)
        else:
            extracted["table_context"].append(value)
        add_content_source(extracted, path)
    elif xlsx_key_has_hint(key, ("value", "display", "formatted", "cell")):
        extracted["cell_values"].append({"value": value, "source_field": path})
        add_content_source(extracted, path)


def normalize_xlsx_row_mapping(value: Mapping[str, Any], path: str, row: Mapping[str, Any]) -> dict[str, str]:
    row_label = first_by_keys(value, ("row_label", "row_name", "record_label", "label", "name"))
    column_label = first_by_keys(value, ("column_label", "column", "header", "field"))
    cell = first_by_keys(value, ("cell", "cell_ref", "cell_address", "address"))
    scalar_value = first_by_keys(value, ("value", "cell_value", "display_value", "formatted_value", "raw_value"))
    row_text = first_by_keys(value, ("row_text", "text", "content", "snippet", "markdown"))
    if row_text and not xlsx_text_is_content(row_text, row):
        row_text = ""
    if scalar_value and not xlsx_text_is_content(scalar_value, row):
        scalar_value = ""
    if not row_text:
        row_text = format_xlsx_mapping_values(value, row)
    if not scalar_value and row_text and not looks_like_locator_only(row_text):
        scalar_value = first_non_locator_scalar(value, row)
    return compact_dict(
        {
            "cell": cell,
            "row_label": row_label,
            "column_label": column_label,
            "value": scalar_value,
            "row_text": row_text,
            "source_field": path,
        }
    )


def normalize_xlsx_cell_mapping(value: Mapping[str, Any], path: str, row: Mapping[str, Any]) -> dict[str, str]:
    cell = first_by_keys(value, ("cell", "cell_ref", "cell_address", "address"))
    scalar_value = first_by_keys(value, ("value", "cell_value", "display_value", "formatted_value", "raw_value", "text"))
    if not xlsx_text_is_content(scalar_value, row):
        return {}
    return compact_dict(
        {
            "cell": cell,
            "row_label": first_by_keys(value, ("row_label", "row_name")),
            "column_label": first_by_keys(value, ("column_label", "column", "header")),
            "value": scalar_value,
            "source_field": path,
        }
    )


def normalize_xlsx_column_mapping(value: Mapping[str, Any], path: str, row: Mapping[str, Any]) -> dict[str, str]:
    column_label = first_by_keys(value, ("column_label", "column", "header", "name"))
    scalar_value = first_by_keys(value, ("value", "cell_value", "display_value", "formatted_value", "raw_value"))
    column_text = first_by_keys(value, ("column_text", "text", "content", "snippet", "markdown"))
    if column_text and not xlsx_text_is_content(column_text, row):
        column_text = ""
    if scalar_value and not xlsx_text_is_content(scalar_value, row):
        scalar_value = ""
    if not column_text:
        column_text = format_xlsx_mapping_values(value, row)
    return compact_dict(
        {
            "column_label": column_label,
            "value": scalar_value,
            "column_text": column_text,
            "source_field": path,
        }
    )


def format_xlsx_mapping_values(value: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    pairs: list[str] = []
    for key, item in value.items():
        key_text = clean(key)
        if not key_text or xlsx_metadata_key(key_text):
            continue
        if isinstance(item, (Mapping, list)):
            continue
        item_text = clean(item)
        if not xlsx_text_is_content(item_text, row):
            continue
        pairs.append(f"{key_text}: {item_text}")
    if len(pairs) < 2:
        return ""
    return " | ".join(pairs[:12])


def first_non_locator_scalar(value: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    for key, item in value.items():
        if xlsx_metadata_key(clean(key)) or isinstance(item, (Mapping, list)):
            continue
        text = clean(item)
        if xlsx_text_is_content(text, row):
            return text
    return ""


def fail_closed_reason_for(
    *,
    track: str,
    expected_shape: str,
    evidence: Mapping[str, Any],
    evidence_quality: Mapping[str, Any],
    content_available: bool,
    policy_pending: bool,
    keyword_only: bool,
    locator_only: bool,
    malformed_input: bool,
) -> str:
    track = clean(track).upper()
    if malformed_input:
        return f"{track or 'INPUT'}_MALFORMED_INPUT"
    if policy_pending:
        return f"{track}_POLICY_PENDING"
    if track == "XLSX" and expected_shape and expected_shape not in XLSX_ALLOWED_SHAPES and expected_shape != POLICY_SHAPE:
        return "XLSX_UNSUPPORTED_TASK_TYPE"
    if track == "PDF" and expected_shape and expected_shape not in PDF_ALLOWED_SHAPES and expected_shape != POLICY_SHAPE:
        return "PDF_UNSUPPORTED_TASK_TYPE"
    if keyword_only:
        return f"{track}_KEYWORD_ONLY"
    if locator_only and track != "XLSX":
        return f"{track}_LOCATOR_ONLY"
    if content_available and (track != "XLSX" or xlsx_shape_content_available(expected_shape, evidence)):
        return ""
    if track == "XLSX":
        if parse_bool(evidence_quality.get("has_matched_keyword")) and not parse_bool(
            evidence_quality.get("has_concrete_content")
        ):
            return "XLSX_KEYWORD_ONLY"
        if content_available and expected_shape == "TABLE_ROW_VALUE":
            return "XLSX_NO_CELL_OR_ROW_VALUE"
        if content_available:
            return "XLSX_NO_TABLE_CONTEXT"
        if parse_bool(evidence_quality.get("has_locator")) and not parse_bool(evidence_quality.get("has_table_context")):
            return "XLSX_LOCATOR_ONLY"
        if parse_bool(evidence_quality.get("has_header_context")) and not (
            parse_bool(evidence_quality.get("has_cell_value")) or parse_bool(evidence_quality.get("has_row_values"))
        ):
            return "XLSX_NO_CELL_OR_ROW_VALUE"
        if parse_bool(evidence_quality.get("content_present_but_unsupported_shape")):
            return "XLSX_CONTENT_PRESENT_BUT_UNSUPPORTED_SHAPE"
        if not parse_bool(evidence_quality.get("has_table_context")):
            return "XLSX_NO_TABLE_CONTEXT"
        return "XLSX_NO_CONTENT_WINDOW"
    if track == "PDF":
        if parse_bool(evidence_quality.get("has_locator")):
            return "PDF_LOCATOR_ONLY"
        return "PDF_NO_CONTENT_WINDOW"
    return "CONTENT_SUMMARY_MISSING_FAIL_CLOSED"


def evidence_quality_flags(
    evidence: Mapping[str, Any],
    *,
    track: str,
    policy_pending: bool,
    keyword_only: bool,
    locator_only: bool,
    malformed_input: bool,
) -> dict[str, Any]:
    row_values = mapping_list(evidence.get("row_values"))
    column_values = mapping_list(evidence.get("column_values"))
    cell_values = mapping_list(evidence.get("cell_values"))
    has_row_values = any(clean(item.get("value")) or clean(item.get("row_text")) for item in row_values)
    has_column_values = any(clean(item.get("value")) or clean(item.get("column_text")) for item in column_values)
    has_cell_value = bool(clean(evidence.get("value"))) or any(clean(item.get("value")) for item in cell_values)
    has_table_context = bool(string_list(evidence.get("table_context")) or string_list(evidence.get("nearby_rows")))
    has_concrete_content = bool(
        clean(evidence.get("content_summary"))
        or has_cell_value
        or has_row_values
        or has_column_values
        or clean(evidence.get("paragraph_block_text"))
        or clean(evidence.get("paragraph_or_table_text"))
        or clean(evidence.get("nearby_text_window"))
    )
    unsupported_count = int_or_zero(evidence.get("unsupported_content_field_count"))
    candidate_count = int_or_zero(evidence.get("candidate_content_field_count"))
    return {
        "track": clean(track).upper(),
        "has_content_summary": bool(clean(evidence.get("content_summary"))),
        "has_cell_value": has_cell_value,
        "has_row_values": has_row_values,
        "has_column_values": has_column_values,
        "has_header_context": bool(string_list(evidence.get("header_context"))),
        "has_table_context": has_table_context,
        "has_nearby_rows": bool(string_list(evidence.get("nearby_rows"))),
        "has_matched_keyword": bool(clean(evidence.get("matched_keyword"))),
        "has_locator": evidence_has_locator(evidence),
        "has_concrete_content": has_concrete_content,
        "content_bearing_field_count": len(string_list(evidence.get("content_source_fields"))),
        "candidate_content_field_count": candidate_count,
        "unsupported_content_field_count": unsupported_count,
        "content_present_but_unsupported_shape": candidate_count > 0 and not has_concrete_content,
        "locator_only": locator_only,
        "keyword_only": keyword_only,
        "policy_pending": policy_pending,
        "malformed_input": malformed_input,
    }


def xlsx_shape_content_available(expected_shape: str, evidence: Mapping[str, Any]) -> bool:
    row_values = mapping_list(evidence.get("row_values"))
    column_values = mapping_list(evidence.get("column_values"))
    cell_values = mapping_list(evidence.get("cell_values"))
    row_value_triplet = bool(
        clean(evidence.get("row_label"))
        and clean(evidence.get("column_label"))
        and clean(evidence.get("value"))
    ) or any(
        clean(item.get("row_label")) and clean(item.get("column_label")) and clean(item.get("value"))
        for item in row_values
    )
    if expected_shape == "TABLE_ROW_VALUE":
        return row_value_triplet
    value_context = bool(
        row_values
        or column_values
        or cell_values
        or clean(evidence.get("value"))
        or string_list(evidence.get("table_context"))
        or string_list(evidence.get("nearby_rows"))
    )
    if expected_shape in {"TABLE_COLUMN_OR_RANGE_WITH_CONTEXT", "LOCATION_PLUS_CONTENT", "EVIDENCE_LOCATOR_WITH_CONTENT"}:
        return value_context
    if expected_shape == "YES_NO_WITH_EVIDENCE":
        return value_context and bool(clean(evidence.get("content_summary")))
    return bool(clean(evidence.get("content_summary")) and value_context)


def matched_keyword_for(row: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    del row
    candidates: list[str] = []
    for key in ("matched_keyword", "matched_term", "matched_value", "keyword"):
        candidates.extend(values_for_key(context, key))
    for candidate in candidates:
        if clean(candidate) and not looks_like_locator_only(candidate):
            return clean(candidate)
    return ""


def values_for_key(value: Any, wanted_key: str) -> list[str]:
    matches: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if clean(key).lower() == wanted_key.lower():
                matches.extend(flatten_strings(item))
            elif not xlsx_path_excluded(clean(key)):
                matches.extend(values_for_key(item, wanted_key))
    elif isinstance(value, list):
        for item in value:
            matches.extend(values_for_key(item, wanted_key))
    return matches


def flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [clean(value)] if clean(value) else []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [clean(value)]
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(flatten_strings(item))
        return items
    if isinstance(value, Mapping):
        items = []
        for item in value.values():
            items.extend(flatten_strings(item))
        return items
    return []


def unique_strings(values: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = clean(value)
        if not text:
            continue
        key = normalize(text)
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def unique_mappings(values: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    seen = set()
    result: list[dict[str, str]] = []
    for value in values:
        compact = {key: clean(item) for key, item in value.items() if clean(item)}
        if not compact:
            continue
        key = json.dumps(compact, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        result.append(compact)
    return result


def merge_mapping_lists(*values: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    merged: list[Mapping[str, Any]] = []
    for items in values:
        merged.extend(items)
    return unique_mappings(merged)


def first_mapping_value(values: Iterable[Mapping[str, Any]], key: str) -> str:
    for value in values:
        text = clean(value.get(key))
        if text:
            return text
    return ""


def add_content_source(extracted: dict[str, Any], path: str) -> None:
    if clean(path):
        extracted["content_source_fields"].append(clean(path))


def path_key(path: str) -> str:
    text = clean(path).replace("]", "")
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    if "[" in text:
        text = text.split("[", 1)[0]
    return text.lower()


def xlsx_key_has_hint(key: str, hints: Iterable[str]) -> bool:
    lowered = clean(key).lower()
    return any(hint in lowered for hint in hints)


def contentish_key(key: str) -> bool:
    return xlsx_key_has_hint(
        key,
        (
            "content",
            "summary",
            "text",
            "snippet",
            "markdown",
            "row",
            "column",
            "cell",
            "value",
            "header",
            "table",
            "nearby",
            "candidate",
        ),
    )


def xlsx_path_excluded(path: str) -> bool:
    lowered = clean(path).lower()
    excluded = (
        "query",
        "expected",
        "must_contain",
        "answer_instruction",
        "content_target_needed",
        "citation_target_policy",
        "policy",
        "review_group",
        "source_review_csv",
        "source_expected",
        "source_must",
        "match_breakdown",
        "hidden",
        "formula",
        "date_policy",
        "number_format_policy",
        "range_relation",
        "score",
        "rank",
        "document_version_id",
        "source_file_name",
        "file_name",
        "location_json",
        "locator",
        "classification_rationale",
        "failure_or_quality_classification",
        "context_errors",
        "context_type",
        "run_id",
        "schema_version",
    )
    return any(item in lowered for item in excluded)


def xlsx_metadata_key(key: str) -> bool:
    lowered = clean(key).lower()
    metadata = (
        "rank",
        "score",
        "file",
        "source",
        "locator",
        "location",
        "sheet",
        "range",
        "cell_range",
        "document_version",
        "chunk_type",
        "match",
        "policy",
        "formula_present",
        "hidden",
        "type",
    )
    return any(item in lowered for item in metadata)


def xlsx_mapping_is_locator(value: Mapping[str, Any]) -> bool:
    scalar_text = " ".join(clean(item) for item in value.values() if not isinstance(item, (Mapping, list)))
    keys = {clean(key).lower() for key in value.keys()}
    if keys and keys <= {
        "file",
        "sheet",
        "sheet_name",
        "range",
        "cell",
        "cell_range",
        "table",
        "table_id",
        "document_version_id",
        "docv",
        "type",
        "sheet_index",
    }:
        return True
    return bool(scalar_text and looks_like_locator_only(scalar_text))


def first_by_keys(value: Mapping[str, Any], keys: Iterable[str]) -> str:
    lowered = {clean(key).lower(): item for key, item in value.items()}
    for key in keys:
        item = lowered.get(key.lower())
        if item is not None and not isinstance(item, (Mapping, list)):
            text = clean(item)
            if text:
                return text
    return ""


def xlsx_text_is_content(value: str, row: Mapping[str, Any]) -> bool:
    text = clean(value)
    if not text:
        return False
    if looks_like_locator_only(text):
        return False
    if content_is_keyword_only(text, row):
        return False
    if text in {"True", "False", "None"}:
        return False
    return True


def xlsx_table_text_is_content(value: str, row: Mapping[str, Any]) -> bool:
    text = clean(value)
    if not xlsx_text_is_content(text, row):
        return False
    if re.search(r"\d", text):
        return True
    if any(separator in text for separator in ("|", "\t", "\n")):
        return True
    if len(re.findall(r"[^:：|,\t\n]{1,40}[:：][^:：|,\t\n]{1,80}", text)) >= 2:
        return True
    return False


def xlsx_table_strings(values: Iterable[str], row: Mapping[str, Any]) -> list[str]:
    return [value for value in values if xlsx_table_text_is_content(value, row)]


def looks_like_locator_only(value: object) -> bool:
    text = clean(value)
    if not text:
        return False
    lowered = text.lower()
    range_or_cell = r"\b[A-Z]{1,3}\d+(?::[A-Z]{1,3}\d+)?\b"
    if re.fullmatch(range_or_cell, text):
        return True
    if re.fullmatch(r"(?:sheet|range|cell|page|bbox|시트|범위|페이지)\s*[:#]?\s*[\w가-힣 .:-]+", text, flags=re.IGNORECASE):
        return True
    if (".xlsx" in lowered or ".xlsm" in lowered or ".pdf" in lowered) and re.search(range_or_cell, text):
        return True
    if ">" in text and re.search(range_or_cell, text) and not any(token in text for token in ("|", "\t", "\n")):
        return True
    return False


def int_or_zero(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def xlsx_row_values(value_context: list[dict[str, Any]], nearby_rows: list[str]) -> list[dict[str, str]]:
    row_values: list[dict[str, str]] = []
    for item in value_context:
        value = clean(item.get("value"))
        if not value:
            continue
        row_values.append(
            compact_dict(
                {
                    "cell": clean(item.get("cell")),
                    "row_label": clean(item.get("row_label")),
                    "column_label": clean(item.get("column_label")),
                    "value": value,
                }
            )
        )
    if row_values:
        return row_values[:12]
    for row_text in nearby_rows[:4]:
        row_values.append({"row_text": row_text})
    return row_values


def infer_xlsx_table_context(table_title: str, header_context: list[str], nearby_rows: list[str]) -> str:
    if table_title:
        return table_title
    if header_context:
        return f"headers: {', '.join(header_context[:8])}"
    if nearby_rows:
        return f"nearby row: {nearby_rows[0]}"
    return ""


def nearby_pdf_text_window(
    table_context: list[str],
    paragraph_context: list[str],
    sentence_context: list[str],
    max_summary_chars: int,
) -> str:
    window = " ".join([*table_context[:2], *paragraph_context[:2], *sentence_context[:3]])
    return truncate(clean_whitespace(window), max_summary_chars)


def content_evidence_available(evidence: Mapping[str, Any]) -> bool:
    if clean(evidence.get("content_summary")):
        return True
    if clean(evidence.get("paragraph_block_text")) or clean(evidence.get("paragraph_or_table_text")):
        return True
    if clean(evidence.get("nearby_text_window")):
        return True
    if clean(evidence.get("row_label")) and (
        clean(evidence.get("value"))
        or bool(mapping_list(evidence.get("row_values")))
        or bool(string_list(evidence.get("nearby_rows")))
    ):
        return True
    return False


def content_window_basis(evidence: Mapping[str, Any]) -> list[str]:
    basis = []
    for key in (
        "content_summary",
        "row_label",
        "column_label",
        "value",
        "row_values",
        "paragraph_block_text",
        "paragraph_or_table_text",
        "nearby_text_window",
        "nearby_rows",
        "header_context",
    ):
        value = evidence.get(key)
        if value not in (None, "", [], {}):
            basis.append(key)
    return basis


def policy_pending_state(row: Mapping[str, Any], policy: Mapping[str, Any]) -> tuple[bool, str]:
    reasons = []
    if clean(row.get("expected_answer_shape")) == POLICY_SHAPE:
        reasons.append("expected_answer_shape_policy_pending")
    if parse_bool(policy.get("not_answerable_or_policy_pending")):
        reasons.append("not_answerable_or_policy_pending")
    if parse_bool(policy.get("hidden_policy_blocked")):
        reasons.append("hidden_policy_blocked")
    if parse_bool(policy.get("pdf_c7_policy_pending")):
        reasons.append("pdf_c7_policy_pending")
    if parse_bool(policy.get("formula_date_policy_blocked")):
        reasons.append("formula_date_policy_blocked")
    return bool(reasons), ";".join(reasons)


def content_is_keyword_only(content_summary: str, row: Mapping[str, Any]) -> bool:
    summary = normalize(content_summary)
    if not summary:
        return False
    terms = [clean(row.get("expected_answer_text")), *string_list(row.get("must_contain_terms"))]
    normalized_terms = [normalize(term) for term in terms if normalize(term)]
    if not normalized_terms:
        return False
    return summary in normalized_terms or (len(summary) <= 40 and any(summary == term for term in normalized_terms))


def evidence_has_locator(evidence: Mapping[str, Any]) -> bool:
    return any(clean(evidence.get(key)) for key in ("sheet", "range", "cell", "page", "bbox", "section"))


def diagnostic_guardrails() -> dict[str, bool]:
    return {
        "retrieval_tuning_run": False,
        "reranking_run": False,
        "parser_expansion_run": False,
        "threshold_relaxation_run": False,
        "db_mutation_run": False,
        "searchunit_mutation_run": False,
        "candidate_artifact_changed": False,
        "immutable_baseline_changed": False,
        "existing_gold_csv_overwritten": False,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def print_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def compact_dict(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in (None, "", [], {})}


def mapping_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    text = clean(value)
    if not text:
        return []
    return [clean(item) for item in re.split(r"[;|]", text) if clean(item)]


def first_nonempty(values: Iterable[str]) -> str:
    for value in values:
        if clean(value):
            return clean(value)
    return ""


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def clean_whitespace(value: object) -> str:
    return re.sub(r"\s+", " ", clean(value)).strip()


def normalize(value: object) -> str:
    return re.sub(r"\s+", "", clean(value)).lower()


def truncate(value: str, max_chars: int) -> str:
    text = clean(value)
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return clean(value).lower() in {"1", "true", "yes", "y"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    sys.exit(main())
