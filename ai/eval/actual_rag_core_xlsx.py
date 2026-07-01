from __future__ import annotations

import json
from datetime import datetime

from ai.eval.actual_rag_core_base import *

def _agentic_planner_tool_locator_text(context: Mapping[str, Any], *, action: str) -> str:
    if action == "pdf_locator_tool":
        fields = (
            "pdf_locator_text",
            "locator_text",
            "page_text",
            "ocr_text",
            "native_text",
            "tool_text",
        )
    elif action == "xlsx_cell_or_table_tool":
        fields = (
            "xlsx_cell_or_table_text",
            "xlsx_locator_text",
            "cell_text",
            "table_text",
            "row_text",
            "tool_text",
        )
    else:
        fields = ()
    for field in fields:
        value = _clean(context.get(field))
        if value:
            return value
    return ""


def _agentic_planner_tool_context(row: Mapping[str, Any], *, action: str) -> dict[str, Any] | None:
    for context in _as_list(row.get("retrieved_contexts")):
        if not isinstance(context, Mapping):
            continue
        source_family = _clean(context.get("source_family")).upper()
        if action == "pdf_locator_tool" and source_family != "PDF":
            continue
        if action == "xlsx_cell_or_table_tool" and source_family not in {"XLSX", "XLS", "SPREADSHEET"}:
            continue
        locator_text = _agentic_planner_tool_locator_text(context, action=action)
        if not locator_text:
            continue
        tool_context = dict(context)
        tool_context["text"] = locator_text
        tool_context["rank"] = 1
        tool_context["agentic_planner_tool_name"] = action
        tool_context["agentic_planner_tool_output"] = True
        tool_context["agentic_planner_tool_input_policy"] = "source_derived_locator_fields_only_no_eval_row_fields"
        return tool_context
    return None


def _agentic_planner_pdf_ocr_allowed(context: Mapping[str, Any]) -> bool:
    ocr_used = _clean(context.get("ocr_used") or context.get("ocr")).lower()
    if ocr_used not in {"true", "1", "yes", "y"}:
        return False
    confidence = _safe_float(context.get("ocr_confidence") or context.get("ocr_mean_confidence"), -1.0)
    if confidence > 1.0:
        confidence = confidence / 100.0
    if confidence < 0.75:
        return False
    metadata_values = _query_evidence_metadata_values_by_axis([context])
    return bool([value for value in metadata_values.get("bbox", ()) if _clean(value)])


def _agentic_planner_pdf_locator_text(context: Mapping[str, Any]) -> tuple[str, str]:
    for field in ("pdf_locator_text", "locator_text", "native_text", "page_text", "tool_text"):
        value = _clean(context.get(field))
        if value:
            return value, field
    if _agentic_planner_pdf_ocr_allowed(context):
        value = _clean(context.get("ocr_text"))
        if value:
            return value, "ocr_text"
    return "", ""


def _agentic_planner_pdf_locator_candidate(row: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    for context in _as_list(row.get("retrieved_contexts")):
        if not isinstance(context, Mapping):
            continue
        if _clean(context.get("source_family")).upper() != "PDF":
            continue
        if not _has_sourceatom_evidence_identity(context):
            continue
        if _clean(context.get("granularity")).lower() == "page_summary":
            continue
        metadata_text, metadata_fields = source_derived_evidence_metadata(context)
        fields = set(metadata_fields)
        has_page_or_section_axis = bool(
            fields & {"page_number", "page", "physical_page_index", "section_title", "table_caption"}
        )
        has_local_locator_axis = bool(
            fields & {"block_index", "bbox", "table_caption", "locator_fingerprint"}
        )
        if not (has_page_or_section_axis and has_local_locator_axis):
            continue
        ocr_used = _clean(context.get("ocr_used") or context.get("ocr")).lower()
        if ocr_used in {"true", "1", "yes", "y"} and not _agentic_planner_pdf_ocr_allowed(context):
            continue
        locator_text, text_field = _agentic_planner_pdf_locator_text(context)
        if not locator_text:
            continue
        tool_context = dict(context)
        tool_context["text"] = locator_text
        tool_context["rank"] = 1
        tool_context["agentic_planner_tool_name"] = "pdf_locator_tool"
        tool_context["agentic_planner_tool_output"] = True
        tool_context["agentic_planner_pdf_locator_text_field"] = text_field
        tool_context["agentic_planner_pdf_locator_metadata_text"] = metadata_text
        tool_context["agentic_planner_tool_input_policy"] = PDF_LOCATOR_TOOL_POLICY
        return tool_context, "candidate_found"
    return None, "skipped_missing_source_locator"


def _agentic_planner_pdf_locator_tool_output(
    row: Mapping[str, Any],
    *,
    evidence_gate_mode: str,
    citation_format: str,
    composer_provider: str,
    local_llm_backend: str,
    local_llm_base_url: str,
    local_llm_model: str,
    local_llm_timeout_seconds: int,
    local_llm_max_tokens: int,
    skip_local_llm_endpoint_check: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base_row = dict(row)
    query = _clean(row.get("query"))
    planner = _query_evidence_planner_for_row(row)
    base_meta: dict[str, Any] = {
        "tool_name": "pdf_locator_tool",
        "tool_implementation": PDF_LOCATOR_TOOL_NAME,
        "tool_call_count": 0,
        "input_policy": PDF_LOCATOR_TOOL_POLICY,
        "output_policy": PDF_LOCATOR_TOOL_OUTPUT_POLICY,
        "uses_query_id_or_row_id_or_target_id": False,
        "uses_expected_answer_or_evidence": False,
        "uses_qrels_or_labels": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }
    if _query_evidence_source_family_hint(planner) != "pdf":
        return base_row, {
            **base_meta,
            "status": "deferred_requires_explicit_execution_gate",
            "execution_gate_required": True,
        }
    tool_context, candidate_status = _agentic_planner_pdf_locator_candidate(row)
    if tool_context is None:
        return base_row, {
            **base_meta,
            "status": candidate_status,
        }
    axis_complete, matched_axes, missing_axes = _query_evidence_context_has_complete_validated_axes(
        query=query,
        query_evidence_planner=planner,
        context=tool_context,
    )
    candidate_count = 1
    if not axis_complete or not _pdf_selected_evidence_has_value_and_axes(
        query,
        tool_context,
        query_evidence_planner=planner,
    ):
        return base_row, {
            **base_meta,
            "status": "rejected_missing_validated_axes_after_tool",
            "tool_call_count": 1,
            "candidate_count": candidate_count,
            "accepted_candidate_count": 0,
            "matched_validated_required_axes": matched_axes,
            "remaining_missing_validated_required_axes": missing_axes,
        }
    tool_context["tool_name"] = PDF_LOCATOR_TOOL_NAME
    tool_context["tool_policy"] = PDF_LOCATOR_TOOL_POLICY
    tool_context["tool_output_policy"] = PDF_LOCATOR_TOOL_OUTPUT_POLICY
    tool_context["pdf_locator_tool_output"] = True
    tool_output = dict(row)
    original_contexts = [
        dict(context)
        for context in _as_list(row.get("retrieved_contexts"))
        if isinstance(context, Mapping)
    ]
    tool_output["retrieved_contexts"] = [
        _runtime_safe_evidence_context(tool_context),
        *[_runtime_safe_evidence_context(context) for context in original_contexts],
    ]
    tool_output["citations"] = []
    composed_tool = apply_selected_evidence_composer_to_outputs(
        [tool_output],
        citation_format=citation_format,
        composer_provider=composer_provider,
        local_llm_backend=local_llm_backend,
        local_llm_base_url=local_llm_base_url,
        local_llm_model=local_llm_model,
        local_llm_timeout_seconds=local_llm_timeout_seconds,
        local_llm_max_tokens=local_llm_max_tokens,
        skip_local_llm_endpoint_check=skip_local_llm_endpoint_check,
        retry_mode="off",
    )
    gated_tool, _tool_gate = apply_evidence_gate_to_outputs(composed_tool, mode=evidence_gate_mode)
    gated_row = dict(gated_tool[0])
    status = (
        "accepted_after_regating"
        if _clean(gated_row.get("answer_gate_decision")) == "allow_answer"
        else "rejected_gate_insufficient"
    )
    tool_use = {
        **base_meta,
        "status": status,
        "execution_status": status,
        "tool_call_count": 1,
        "candidate_count": candidate_count,
        "accepted_candidate_count": 1 if status == "accepted_after_regating" else 0,
        "matched_validated_required_axes": matched_axes,
        "remaining_missing_validated_required_axes": missing_axes,
    }
    gated_row["pdf_locator_tool_use"] = tool_use
    return gated_row, tool_use


def _xlsx_locator_metadata_sources(context: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    sources: list[Mapping[str, Any]] = [context]
    for container_key in (
        "metadata",
        "raw_locator",
        "location_json",
        "xlsx_locator_metadata",
        "xlsx_locator",
        "locator_metadata",
    ):
        parsed = _parse_jsonish(context.get(container_key))
        if isinstance(parsed, Mapping):
            sources.append(parsed)
    return sources


def _canonical_xlsx_locator_field_name(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", text)
    canonical = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").casefold()
    aliases = {
        "baseline_top_k": "baseline_topk",
        "file": "file_name",
        "filename": "file_name",
        "source_filename": "source_file_name",
    }
    return aliases.get(canonical, canonical)


def _xlsx_locator_text_marker_aliases(marker: str) -> set[str]:
    canonical = _canonical_xlsx_locator_field_name(marker)
    parts = [part for part in canonical.split("_") if part]
    camel = parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:]) if parts else canonical
    pascal = "".join(part[:1].upper() + part[1:] for part in parts)
    aliases = {
        canonical,
        canonical.replace("_", ""),
        canonical.replace("_", "-"),
        camel,
        pascal,
    }
    if canonical == "file_name":
        aliases.update({"filename", "fileName", "FileName", "source_file_name", "sourceFileName", "SourceFileName"})
    if canonical == "source_file_name":
        aliases.update({"file_name", "fileName", "filename"})
    if canonical == "baseline_topk":
        aliases.update({"baseline_top_k", "baselineTopK", "BaselineTopK"})
    return {alias for alias in aliases if alias}


def _xlsx_locator_forbidden_text_fields(value: Any) -> set[str]:
    text = _clean(value).casefold()
    if not text:
        return set()
    seen: set[str] = set()
    for marker in XLSX_LOCATOR_FORBIDDEN_TEXT_MARKERS:
        for alias in _xlsx_locator_text_marker_aliases(marker):
            normalized = alias.casefold()
            if (
                re.search(rf"(?<![a-z0-9_]){re.escape(normalized)}\s*[:=]", text)
                or f'"{normalized}"' in text
                or f"'{normalized}'" in text
            ):
                seen.add(_canonical_xlsx_locator_field_name(marker))
                break
    return seen


def _collect_xlsx_locator_forbidden_input_fields(value: Any) -> set[str]:
    seen: set[str] = set()
    forbidden_keys = set(XLSX_PDF_RESIDUAL_FORBIDDEN_SHORTCUT_FIELDS)
    forbidden_keys.update(SOURCE_DERIVED_EVIDENCE_FORBIDDEN_FIELDS)
    forbidden_keys.update(
        {
            "raw_prompt",
            "raw_response",
            "prompt_payload",
            "raw_prompt_payload",
            "raw_response_payload",
            "raw_tool_payload",
            "source_path",
            "tool_payload",
            "workbook_id",
            "workbook_version_id",
        }
    )
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = _canonical_xlsx_locator_field_name(key)
            if key_text in forbidden_keys:
                seen.add(key_text)
            if key_text in {"forbidden_input_fields_seen", "forbidden_input_fields_used"}:
                seen.update(
                    canonical
                    for canonical in (_canonical_xlsx_locator_field_name(field) for field in _as_list(nested))
                    if canonical in forbidden_keys
                )
            if isinstance(nested, str):
                seen.update(_xlsx_locator_forbidden_text_fields(nested))
            elif isinstance(nested, (Mapping, list, tuple)):
                seen.update(_collect_xlsx_locator_forbidden_input_fields(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            if isinstance(nested, str):
                seen.update(_xlsx_locator_forbidden_text_fields(nested))
            elif isinstance(nested, (Mapping, list, tuple)):
                seen.update(_collect_xlsx_locator_forbidden_input_fields(nested))
    elif isinstance(value, str):
        seen.update(_xlsx_locator_forbidden_text_fields(value))
    return seen


def _xlsx_locator_forbidden_seen_fields_requiring_fail_closed(fields: Sequence[str]) -> list[str]:
    return sorted(
        {
            _clean(field)
            for field in fields
            if _clean(field)
            and _clean(field) not in XLSX_LOCATOR_DIAGNOSTIC_ONLY_FORBIDDEN_SEEN_FIELDS
        }
    )


def _xlsx_locator_source_owned_value(context: Mapping[str, Any], field: str) -> str:
    if field in SOURCE_DERIVED_EVIDENCE_FORBIDDEN_FIELDS:
        return ""
    for source in _xlsx_locator_metadata_sources(context):
        value = _clean(source.get(field))
        if value:
            return value
    return ""


def _xlsx_locator_source_owned_text(context: Mapping[str, Any]) -> tuple[str, tuple[str, ...]]:
    values: list[str] = []
    fields: list[str] = []
    for field in (
        "sheet",
        "cell_range",
        "cell",
        "row_index_1based",
        "row_label",
        "column_label",
        "target_column",
        "header",
        "header_path",
        "table_id",
        "synthetic_table_id",
        "display_value",
    ):
        value = _xlsx_locator_source_owned_value(context, field)
        if not value:
            continue
        values.append(f"{field}={value}")
        fields.append(field)
    return " | ".join(values), tuple(fields)


def _strip_xlsx_locator_forbidden_text_segments(text: str) -> str:
    clean_text = _clean(text)
    if not clean_text:
        return ""
    safe_parts: list[str] = []
    for part in re.split(r"\s+\|\s+", clean_text):
        segment = _clean(part)
        if not segment:
            continue
        if _xlsx_locator_forbidden_text_fields(segment):
            continue
        safe_parts.append(segment)
    return " | ".join(safe_parts)


def _xlsx_locator_used_input_view(
    *,
    locator_text: str,
    locator_text_fields_used: Sequence[str],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    used: dict[str, Any] = {
        "locator_text": locator_text,
        "locator_text_fields_used": list(locator_text_fields_used),
    }
    for field in XLSX_LOCATOR_SOURCE_OWNED_FIELDS:
        value = _clean(candidate.get(field))
        if value:
            used[field] = value
    source_date_aliases = [
        _clean(alias)
        for alias in _as_list(candidate.get("source_date_aliases"))
        if _clean(alias)
    ]
    if source_date_aliases:
        used["source_date_aliases"] = source_date_aliases
    return used


def _xlsx_locator_candidate_text(context: Mapping[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    preserved_locator_text = _clean(context.get("xlsx_locator_text"))
    preserved_locator_text_source = _clean(context.get("locator_text_source"))
    if preserved_locator_text and preserved_locator_text_source:
        fields_used = tuple(
            _clean(field)
            for field in _as_list(context.get("locator_text_fields_used"))
            if _clean(field)
        )
        if not fields_used:
            fields_used = ("xlsx_locator_text",)
        return preserved_locator_text, preserved_locator_text_source, fields_used
    for field in (
        "xlsx_cell_or_table_text",
        "xlsx_locator_text",
        "cell_text",
        "table_text",
        "row_text",
        "tool_text",
    ):
        locator_text = _clean(context.get(field))
        if locator_text:
            return locator_text, "explicit_locator_text", (field,)
    source_owned_text, source_owned_fields = _xlsx_locator_source_owned_text(context)
    row_text = _strip_xlsx_locator_forbidden_text_segments(_gate_row_text(context))
    support_text = " | ".join(part for part in (source_owned_text, row_text) if part)
    if support_text and source_owned_fields:
        text_fields = [
            field
            for field in ("text", "citation_text", "display_text", "embedding_text", "bm25_text")
            if _clean(context.get(field))
        ]
        return support_text, "source_owned_support_text", tuple([*source_owned_fields, *text_fields[:1]])
    return "", "", ()


def _xlsx_locator_split_header_data_segment(segment: str) -> list[str]:
    clean_segment = _clean(segment)
    if not clean_segment:
        return []
    match = re.match(r"^(.+?[A-Za-z가-힣ぁ-んァ-ン一-龯々][^|=]*?)\s+(\d{6,}.*)$", clean_segment)
    if not match:
        return [clean_segment]
    left = _clean(match.group(1)).strip(" |")
    right = _clean(match.group(2)).strip(" |")
    if not left or not right:
        return [clean_segment]
    return [left, right]


def _xlsx_locator_table_segments(text: str) -> list[str]:
    clean_text = _strip_xlsx_locator_forbidden_text_segments(text)
    segments: list[str] = []
    for part in re.split(r"\s+\|\s+|\n+", clean_text):
        for segment in _xlsx_locator_split_header_data_segment(part):
            if segment:
                segments.append(segment)
    return segments


def _xlsx_locator_table_metadata_segment(segment: str) -> bool:
    key, separator, _value = _clean(segment).partition("=")
    if not separator:
        return False
    return _canonical_xlsx_locator_field_name(key) in {
        "sheet",
        "range",
        "cell_range",
        "cell",
        "row_label",
        "column_label",
        "target_column",
        "header",
        "header_path",
        "table_id",
        "synthetic_table_id",
        "display_value",
    }


def _xlsx_locator_target_column_display_value_from_segments(
    *,
    candidate: Mapping[str, Any],
    text: str,
) -> str:
    target_labels = [
        _clean(value)
        for value in (
            candidate.get("target_column"),
            candidate.get("column_label"),
            candidate.get("header"),
            candidate.get("header_path"),
        )
        if _clean(value)
    ]
    normalized_targets = {
        normalize_answer_text(label)
        for label in target_labels
        if normalize_answer_text(label)
    }
    if not normalized_targets:
        return ""
    matches: list[str] = []
    for segment in _xlsx_locator_table_segments(text):
        key, separator, value = _clean(segment).partition("=")
        if not separator:
            continue
        normalized_key = normalize_answer_text(key)
        clean_value = _clean(value)
        if not normalized_key or normalized_key not in normalized_targets or not clean_value:
            continue
        matches.append(clean_value)
    if len(matches) != 1:
        return ""
    return matches[0]


def _xlsx_locator_table_header_labels(text: str) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for segment in _xlsx_locator_table_segments(text):
        if _xlsx_locator_table_metadata_segment(segment):
            continue
        if re.search(r"\d{6,}", segment):
            break
        label = _clean(segment).strip(" |")
        if not label or "=" in label or re.search(r"\d", label):
            continue
        normalized = normalize_answer_text(label)
        if not normalized or normalized in seen:
            continue
        if not re.search(r"[A-Za-z가-힣ぁ-んァ-ン一-龯々]", normalized):
            continue
        labels.append(label)
        seen.add(normalized)
    return labels


def _xlsx_locator_table_row_records(text: str) -> list[dict[str, Any]]:
    segments = _xlsx_locator_table_segments(text)
    data_start = -1
    header_segments: list[str] = []
    for index, segment in enumerate(segments):
        if _xlsx_locator_table_metadata_segment(segment):
            continue
        if re.search(r"\d{6,}", segment):
            data_start = index
            break
        if "=" not in segment and not re.search(r"\d", segment):
            header_segments.append(segment)
    if data_start < 0 or not header_segments:
        return []
    headers = list(dict.fromkeys(_clean(header) for header in header_segments if _clean(header)))
    if not headers:
        return []
    data_segments = [_clean(segment) for segment in segments[data_start:] if _clean(segment)]
    first_value_is_identifier = bool(data_segments and re.fullmatch(r"\d{6,}", data_segments[0]))
    row_headers = list(headers)
    if first_value_is_identifier and not any("장기요양기관코드" in normalize_answer_text(header) for header in row_headers):
        row_headers = ["장기요양기관코드", *row_headers]
    width = len(row_headers)
    if width <= 0:
        return []
    records: list[dict[str, Any]] = []
    for offset in range(0, len(data_segments), width):
        values = data_segments[offset : offset + width]
        if len(values) < width:
            break
        mapping = {row_headers[index]: values[index] for index in range(width)}
        row_text = " | ".join(f"{header}={mapping[header]}" for header in row_headers if _clean(mapping.get(header)))
        records.append(
            {
                "headers": row_headers,
                "mapping": mapping,
                "text": row_text,
            }
        )
    return records


def _xlsx_locator_target_header_from_query(query: str, header_labels: Sequence[str]) -> str:
    query_norm = normalize_answer_text(query)
    best = ""
    for label in header_labels:
        label_norm = normalize_answer_text(label)
        if not label_norm:
            continue
        label_tokens = [token for token in label_norm.split() if token]
        if label_tokens and all(token in query_norm for token in label_tokens):
            if len(label_norm) > len(normalize_answer_text(best)):
                best = _clean(label)
    return best


def _xlsx_locator_source_term_for_anchor(anchor: str, text: str) -> str:
    normalized_anchor = normalize_answer_text(anchor)
    if not normalized_anchor:
        return ""
    for segment in re.split(r"\s+\|\s+|\n+", text):
        clean_segment = _clean(segment)
        if not clean_segment or not _anchor_in_text([normalized_anchor], clean_segment):
            continue
        if "=" in clean_segment:
            clean_segment = _clean(clean_segment.rsplit("=", 1)[-1])
        for token in re.findall(r"[A-Za-z0-9_-]{2,}|[가-힣0-9]{2,}|[ぁ-んァ-ン一-龯々0-9]{2,}", clean_segment):
            normalized_token = normalize_answer_text(token)
            if normalized_anchor in normalized_token or normalized_token in normalized_anchor:
                return _clean(token)[:80]
        return clean_segment[:80]
    return ""


def _xlsx_locator_row_anchor_from_query(query: str, text: str, header_labels: Sequence[str]) -> str:
    header_norm = normalize_answer_text(" ".join(header_labels))
    stopwords = _anchor_stopwords() | {normalize_answer_text(value) for value in EVIDENCE_GATE_QUERY_INTENT_STOPWORDS}
    for anchor in sorted(_gate_query_focus_anchors(query), key=lambda value: (-len(value), value)):
        normalized = normalize_answer_text(anchor)
        if not normalized or re.search(r"\d", normalized):
            continue
        if _is_generic_anchor(normalized, stopwords):
            continue
        if normalized in header_norm:
            continue
        if not _anchor_in_text([normalized], text):
            continue
        source_term = _xlsx_locator_source_term_for_anchor(normalized, text)
        return source_term or normalized
    return ""


def _xlsx_locator_anchor_position(text: str, anchor: str) -> int:
    for candidate in (anchor, anchor.replace(" ", "")):
        if not candidate:
            continue
        position = text.find(candidate)
        if position >= 0:
            return position
    for match in re.finditer(r"[A-Za-z0-9_-]{2,}|[가-힣0-9]{2,}|[ぁ-んァ-ン一-龯々0-9]{2,}", text):
        if _anchor_in_text([anchor], match.group(0)):
            return match.start()
    return -1


def _xlsx_locator_date_aliases(text: str) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()

    def valid_year(value: str) -> bool:
        try:
            year = int(value)
        except ValueError:
            return False
        return 1900 <= year <= 2099

    def add(value: str) -> None:
        clean_value = _clean(value)
        if clean_value and clean_value not in seen:
            aliases.append(clean_value)
            seen.add(clean_value)

    for match in re.finditer(r"\b(\d{4})[-./](0?[1-9]|1[0-2])(?:[-./](0?[1-9]|[12]\d|3[01]))?\b", text):
        year = match.group(1)
        if not valid_year(year):
            continue
        month = str(int(match.group(2)))
        day = str(int(match.group(3))) if match.group(3) else ""
        add(f"{year}년 {month}월")
        add(f"{year}년")
        add(f"{month}월")
        if day:
            add(f"{day}일")
    compact_period_pattern = re.compile(
        r"(?:년월|연월|기간|period|date|지정일자|설치신고일자)\s*[:=]?\s*(\d{4})(0[1-9]|1[0-2])\b",
        re.IGNORECASE,
    )
    for match in compact_period_pattern.finditer(text):
        year = match.group(1)
        if not valid_year(year):
            continue
        month = str(int(match.group(2)))
        add(f"{year}년 {month}월")
        add(f"{year}년")
        add(f"{month}월")
    return aliases


def _xlsx_locator_apply_source_date_alias_diagnostic(
    candidate: MutableMapping[str, Any],
    support_text: str,
) -> None:
    aliases = _xlsx_locator_date_aliases(support_text)
    if aliases:
        candidate["source_date_aliases"] = aliases


def _xlsx_locator_source_date_alias_candidate_values(value: Any) -> list[str]:
    parsed = _parse_jsonish(value)
    raw_values = parsed if isinstance(parsed, list) else [parsed]
    aliases: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        alias = _clean(raw_value)
        if not alias:
            continue
        if not (
            re.search(r"\b\d{4}년\b", alias)
            or re.search(r"\b\d{4}년\s+\d{1,2}월\b", alias)
            or re.search(r"\b\d{1,2}월\b", alias)
            or re.search(r"\b\d{4}[-./](0?[1-9]|1[0-2])\b", alias)
        ):
            continue
        if alias not in seen:
            aliases.append(alias)
            seen.add(alias)
    return aliases


def _xlsx_locator_source_date_aliases_from_context(context: Mapping[str, Any]) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()
    safe_text = _gate_row_text(context)
    for alias in _xlsx_locator_date_aliases(safe_text):
        if alias not in seen:
            aliases.append(alias)
            seen.add(alias)
    metadata = context.get("metadata") if isinstance(context.get("metadata"), Mapping) else {}
    verified_bundle = _clean(
        context.get("candidate_surface_materialization") or metadata.get("candidate_surface_materialization")
    ) == "xlsx_row_value_bundle_v1"
    if verified_bundle:
        for source in (context, metadata):
            for field in ("source_date_aliases", "source_date_aliases_json", "source_date_alias"):
                for alias in _xlsx_locator_source_date_alias_candidate_values(source.get(field)):
                    if alias not in seen:
                        aliases.append(alias)
                        seen.add(alias)
    return aliases


def _xlsx_locator_candidate_can_use_same_candidate_source_date_alias_package(
    candidate: Mapping[str, Any],
) -> bool:
    if _clean(candidate.get("source_family")).upper() != "XLSX":
        return False
    if not _has_sourceatom_evidence_identity(candidate) or not _clean(candidate.get("doc_id")):
        return False
    if not _clean(candidate.get("display_value")):
        return False
    if not (_clean(candidate.get("target_column")) or _clean(candidate.get("column_label"))):
        return False
    if not (_clean(candidate.get("row_label")) or _clean(candidate.get("row_index_1based"))):
        return False
    if not (_clean(candidate.get("sheet")) or _clean(candidate.get("cell_range")) or _clean(candidate.get("cell"))):
        return False
    return True


def _xlsx_locator_apply_same_candidate_source_date_alias_package(
    *,
    context: Mapping[str, Any],
    candidate: MutableMapping[str, Any],
    locator_text: str,
    locator_text_source: str,
    locator_text_fields_used: Sequence[str],
) -> tuple[str, str, tuple[str, ...]]:
    aliases = [
        *(
            _clean(alias)
            for alias in _as_list(candidate.get("source_date_aliases"))
            if _clean(alias)
        ),
        *_xlsx_locator_source_date_aliases_from_context(context),
    ]
    aliases = list(dict.fromkeys(alias for alias in aliases if alias))
    if not aliases or not _xlsx_locator_candidate_can_use_same_candidate_source_date_alias_package(candidate):
        return locator_text, locator_text_source, tuple(locator_text_fields_used)

    text = _clean(candidate.get("text") or locator_text)
    existing_text = normalize_answer_text(text)
    alias_parts = [
        f"source_date_alias={alias}"
        for alias in aliases
        if normalize_answer_text(alias) not in existing_text
    ]
    if alias_parts:
        text = " | ".join(part for part in (text, *alias_parts) if part)
        candidate["text"] = text
    candidate["source_date_aliases"] = aliases
    candidate["source_owned_same_candidate_package"] = True
    candidate["source_owned_same_candidate_package_policy"] = (
        "source_owned_same_candidate_date_aliases_only_no_gold_qrels_labels_ids_titles_or_files_v1"
    )
    fields = tuple(dict.fromkeys([*locator_text_fields_used, "source_date_aliases"]))
    return text, locator_text_source, fields


def _xlsx_locator_table_row_text(
    *,
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    text: str,
) -> tuple[str, str, str, str, str] | None:
    clean_text = _strip_xlsx_locator_forbidden_text_segments(text)
    query = _clean(row.get("query"))
    if not clean_text or not query:
        return None
    row_records = _xlsx_locator_table_row_records(clean_text)
    if not row_records:
        return None
    header_labels = list(row_records[0].get("headers") or [])
    target_header = _xlsx_locator_target_header_from_query(query, header_labels)
    if not target_header:
        return None
    query_anchors = _query_focus_anchors_for_row(row)
    numeric_query_anchors = _numeric_or_date_anchors(query_anchors)
    matching_rows: list[tuple[str, str, str]] = []
    for record in row_records:
        row_text = _clean(record.get("text"))
        if not row_text:
            continue
        row_anchor = _xlsx_locator_row_anchor_from_query(query, row_text, header_labels)
        if not row_anchor:
            continue
        date_alias_parts = [f"source_date_alias={alias}" for alias in _xlsx_locator_date_aliases(row_text)]
        support_text = " | ".join(part for part in (row_text, *date_alias_parts) if part)
        matched = _gate_anchor_hits(query_anchors, [support_text])
        if any(anchor not in matched for anchor in numeric_query_anchors):
            continue
        target_value = _clean((record.get("mapping") or {}).get(target_header))
        if not target_value:
            continue
        matching_rows.append((support_text, row_anchor, target_value))
    if len(matching_rows) != 1:
        return None
    support_text, row_anchor, target_value = matching_rows[0]
    sheet = _xlsx_locator_source_owned_value(context, "sheet")
    cell_range = _xlsx_locator_source_owned_value(context, "cell_range")
    support_text = " | ".join(
        part
        for part in (
            f"sheet={sheet}" if sheet else "",
            f"cell_range={cell_range}" if cell_range else "",
            f"row_label={row_anchor}",
            f"target_column={target_header}",
            f"display_value={target_value}",
            support_text,
        )
        if part
    )
    synthetic_seed = "|".join(
        [
            _xlsx_locator_source_owned_value(context, "doc_id"),
            sheet,
            cell_range,
            row_anchor,
            target_header,
        ]
    )
    synthetic_table_id = f"{XLSX_LOCATOR_SYNTHETIC_TABLE_ID_PREFIX}{_sha256_text(synthetic_seed)[:16]}"
    return support_text, row_anchor, target_header, target_value, synthetic_table_id


def _apply_xlsx_locator_table_row_overlay(
    *,
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    candidate: MutableMapping[str, Any],
    locator_text: str,
    locator_text_source: str,
    locator_text_fields_used: Sequence[str],
) -> tuple[str, str, tuple[str, ...]]:
    if _xlsx_locator_confidence_tier(candidate) == "high":
        return locator_text, locator_text_source, tuple(locator_text_fields_used)
    if locator_text_source not in {"source_owned_support_text", "explicit_locator_text"}:
        return locator_text, locator_text_source, tuple(locator_text_fields_used)
    table_row = _xlsx_locator_table_row_text(row=row, context=context, text=_gate_row_text(context))
    if table_row is None:
        return locator_text, locator_text_source, tuple(locator_text_fields_used)
    support_text, row_label, target_header, display_value, synthetic_table_id = table_row
    candidate.update(
        {
            "text": support_text,
            "row_label": row_label,
            "column_label": target_header,
            "target_column": target_header,
            "header": target_header,
            "header_path": target_header,
            "display_value": display_value,
            "synthetic_table_id": synthetic_table_id,
            "granularity": "xlsx_locator_table_row",
            "locator_text_source": "source_owned_table_row_text",
        }
    )
    fields = tuple(
        dict.fromkeys(
            [
                *locator_text_fields_used,
                "row_label",
                "column_label",
                "target_column",
                "header",
                "header_path",
                "display_value",
                "synthetic_table_id",
            ]
        )
    )
    return support_text, "source_owned_table_row_text", fields


def _xlsx_locator_axis_fields_used(candidate: Mapping[str, Any]) -> list[str]:
    return [
        field
        for field in XLSX_LOCATOR_SOURCE_OWNED_FIELDS
        if field not in {"source_atom_id", "evidence_bundle_id", "doc_id", "display_value"}
        and _clean(candidate.get(field))
    ]


def _xlsx_locator_confidence_tier(candidate: Mapping[str, Any]) -> str:
    fields = set(_xlsx_locator_axis_fields_used(candidate))
    has_scope = bool(fields & {"sheet", "cell", "cell_range", "table_id", "synthetic_table_id"})
    has_cell_axis = bool(fields & {"cell", "row_index_1based"})
    has_semantic_axis = bool(
        fields
        & {
            "row_label",
            "column_label",
            "target_column",
            "header",
            "header_path",
            "table_id",
            "synthetic_table_id",
        }
    )
    if has_scope and has_semantic_axis:
        return "high"
    if has_scope or has_cell_axis or has_semantic_axis:
        return "medium"
    return "low"


def _axis_value_hits_text(values: Sequence[str], texts: Sequence[str]) -> bool:
    clean_values = [_clean(value) for value in values if _clean(value)]
    if not clean_values:
        return False
    clean_texts = [_clean(text) for text in texts if _clean(text)]
    return any(_anchor_in_text([value], text) for value in clean_values for text in clean_texts)


def _xlsx_locator_period_axis_hit_from_period_cells(
    *,
    planner: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> bool:
    query_periods = _xlsx_materializer_query_periods(planner)
    if not query_periods:
        return False
    for packet in _xlsx_same_row_period_cell_packets(candidate):
        if not _xlsx_period_cell_scope_matches_candidate(candidate, packet):
            continue
        for query_period in query_periods:
            if _source_period_cell_matches_query_period(packet, query_period):
                return True
    return False


def _xlsx_locator_validated_required_axis_hits(
    *,
    row: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    planner = _query_evidence_planner_for_row(row)
    required_axes = [
        _clean(axis)
        for axis in _as_list(planner.get("validated_required_axes"))
        if _clean(axis)
    ]
    if not required_axes:
        return [], []
    support_text = _gate_support_text(candidate)
    metadata_values = _query_evidence_metadata_values_by_axis([candidate])
    field_texts = {
        axis: [support_text, *metadata_values.get(axis, [])]
        for axis in QUERY_EVIDENCE_AXIS_ORDER
    }
    matched: list[str] = []
    missing: list[str] = []
    for axis in required_axes:
        if axis == "display_value":
            axis_ok = bool(_clean(candidate.get("display_value")))
        elif axis == "period":
            axis_ok = _xlsx_locator_period_axis_hit_from_period_cells(
                planner=planner,
                candidate=candidate,
            )
        else:
            axis_ok = _query_evidence_axis_hit(
                axis=axis,
                planner=planner,
                field_texts=field_texts,
                metadata_values=metadata_values,
            )
        if axis_ok:
            matched.append(axis)
        else:
            missing.append(axis)
    return matched, missing


def _xlsx_locator_candidate_from_context(
    row: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any] | None:
    source_family = _clean(context.get("source_family")).upper()
    if source_family not in {"XLSX", "XLS", "SPREADSHEET"}:
        return None
    locator_text, locator_text_source, locator_text_fields_used = _xlsx_locator_candidate_text(context)
    if not locator_text:
        return None
    candidate: dict[str, Any] = {
        "source_family": "XLSX",
        "granularity": _clean(context.get("granularity")) or "xlsx_locator_tool_candidate",
        "text": locator_text,
        "rank": 1,
        "tool_name": XLSX_LOCATOR_TOOL_NAME,
        "tool_policy": XLSX_LOCATOR_TOOL_POLICY,
        "agentic_planner_tool_name": "xlsx_cell_or_table_tool",
        "agentic_planner_tool_output": True,
        "agentic_planner_tool_input_policy": XLSX_LOCATOR_TOOL_POLICY,
        "xlsx_locator_tool_output": True,
        "locator_text_source": locator_text_source,
    }
    for field in XLSX_LOCATOR_SOURCE_OWNED_FIELDS:
        value = _xlsx_locator_source_owned_value(context, field)
        if value:
            candidate[field] = value
    if _clean(context.get("chunk_id")):
        candidate["chunk_id"] = _clean(context.get("chunk_id"))
    locator_text, locator_text_source, locator_text_fields_used = _apply_xlsx_locator_table_row_overlay(
        row=row,
        context=context,
        candidate=candidate,
        locator_text=locator_text,
        locator_text_source=locator_text_source,
        locator_text_fields_used=locator_text_fields_used,
    )
    if not _clean(candidate.get("display_value")):
        materialized_display_value = _xlsx_locator_target_column_display_value_from_segments(
            candidate=candidate,
            text=_gate_support_text(candidate),
        )
        if materialized_display_value:
            candidate["display_value"] = materialized_display_value
            candidate["display_value_source"] = "source_owned_target_column_segment"
            locator_text_fields_used = tuple(dict.fromkeys([*locator_text_fields_used, "display_value"]))
    period_cells = [
        packet
        for packet in _xlsx_same_row_period_cell_packets(context)
        if _xlsx_period_cell_scope_matches_candidate(candidate, packet)
    ]
    if period_cells:
        candidate["same_row_period_cells"] = period_cells
        candidate["same_row_period_cells_json"] = json.dumps(period_cells, ensure_ascii=False, sort_keys=True)
    locator_text, locator_text_source, locator_text_fields_used = (
        _xlsx_locator_apply_same_candidate_source_date_alias_package(
            context=context,
            candidate=candidate,
            locator_text=locator_text,
            locator_text_source=locator_text_source,
            locator_text_fields_used=locator_text_fields_used,
        )
    )
    query = _clean(row.get("query"))
    query_anchors = _query_focus_anchors_for_row(row)
    support_text = _gate_support_text(candidate)
    _xlsx_locator_apply_source_date_alias_diagnostic(candidate, support_text)
    if _as_list(candidate.get("source_date_aliases")):
        locator_text_fields_used = tuple(dict.fromkeys([*locator_text_fields_used, "source_date_aliases"]))
    matched = sorted(_gate_anchor_hits(query_anchors, [support_text]))
    missing = sorted(query_anchors - set(matched))
    query_anchor_coverage = _gate_coverage(query_anchors, set(matched))
    matched_required_axes, missing_required_axes = _xlsx_locator_validated_required_axis_hits(
        row=row,
        candidate=candidate,
    )
    if "period" in matched_required_axes and _as_list(candidate.get("same_row_period_cells")):
        candidate["source_owned_same_candidate_package"] = True
        candidate["source_owned_same_candidate_package_policy"] = "source_owned_same_row_period_cell_v1"
        locator_text_fields_used = tuple(
            dict.fromkeys([*locator_text_fields_used, "same_row_period_cells_json"])
        )
    required_axes_available = bool(matched_required_axes or missing_required_axes)
    planner = _query_evidence_planner_for_row(row)
    source_family_hint = _clean(planner.get("source_family_hint")).lower() if planner else ""
    source_family_hint_allows_xlsx = source_family_hint in {"", "unknown", "xlsx"}
    previous_forbidden_seen = {
        _canonical_xlsx_locator_field_name(field)
        for field in (
            *_as_list(candidate.get("forbidden_input_fields_rejected")),
            *_as_list(candidate.get("forbidden_input_fields_used_for_candidate")),
        )
        if _clean(field)
    }
    forbidden_input_fields_seen = sorted(
        {
            *previous_forbidden_seen,
            *_collect_xlsx_locator_forbidden_input_fields(context),
        }
    )
    forbidden_seen_fail_closed = _xlsx_locator_forbidden_seen_fields_requiring_fail_closed(
        forbidden_input_fields_seen
    )
    forbidden_input_fields = sorted(
        _collect_xlsx_locator_forbidden_input_fields(
            _xlsx_locator_used_input_view(
                locator_text=locator_text,
                locator_text_fields_used=locator_text_fields_used,
                candidate=candidate,
            )
        )
    )
    input_fields_used = sorted(
        {
            *locator_text_fields_used,
            *(
                field
                for field in XLSX_LOCATOR_SOURCE_OWNED_FIELDS
                if _clean(context.get(field))
                or _clean(candidate.get(field))
                or any(_clean(source.get(field)) for source in _xlsx_locator_metadata_sources(context))
            ),
            "locator_text_source",
        }
    )
    confidence_tier = _xlsx_locator_confidence_tier(candidate)
    query_anchor_sufficient = not query_anchors or query_anchor_coverage >= EVIDENCE_GATE_MIN_QUERY_ANCHOR_COVERAGE
    required_axes_sufficient = required_axes_available and not missing_required_axes
    accepted = bool(
        not forbidden_input_fields
        and not forbidden_seen_fail_closed
        and _has_sourceatom_evidence_identity(candidate)
        and _clean(candidate.get("doc_id"))
        and _clean(candidate.get("text"))
        and source_family_hint_allows_xlsx
        and (required_axes_sufficient if required_axes_available else bool(matched and query_anchor_sufficient))
        and confidence_tier == "high"
    )
    if accepted:
        rejection_reason = ""
    elif forbidden_input_fields or forbidden_seen_fail_closed:
        rejection_reason = "forbidden_input_fields_present"
    elif not source_family_hint_allows_xlsx:
        rejection_reason = "source_family_hint_mismatch"
    elif required_axes_available and missing_required_axes:
        rejection_reason = "missing_validated_required_axes_after_tool"
    elif not matched or not query_anchor_sufficient:
        rejection_reason = "missing_query_anchor_after_tool"
    elif confidence_tier != "high":
        rejection_reason = "missing_required_locator_axes"
    else:
        rejection_reason = "missing_source_identity_doc_id_text_or_locator_axes"
    candidate.update(
        {
            "matched_query_anchors": matched,
            "missing_query_anchors_after_tool": missing,
            "matched_validated_required_axes": matched_required_axes,
            "missing_validated_required_axes": missing_required_axes,
            "confidence_tier": confidence_tier,
            "query_anchor_coverage": query_anchor_coverage,
            "validated_required_axes_coverage": _gate_coverage(matched_required_axes + missing_required_axes, matched_required_axes),
            "source_family_hint": source_family_hint,
            "source_family_hint_matches_candidate": source_family_hint_allows_xlsx,
            "accepted_for_regating": accepted,
            "rejection_reason": rejection_reason,
            "input_fields_used": input_fields_used,
            "forbidden_input_fields_seen": forbidden_input_fields_seen,
            "forbidden_input_fields_used_for_candidate": forbidden_input_fields,
            "forbidden_input_fields_rejected": forbidden_seen_fail_closed,
        }
    )
    return candidate


def _xlsx_locator_axis_hit_in_text(axis: str, planner: Mapping[str, Any], text: str) -> bool:
    clean_text = _clean(text)
    if not clean_text:
        return False
    field_texts = {axis_name: [clean_text] for axis_name in QUERY_EVIDENCE_AXIS_ORDER}
    field_texts["period"] = [
        *field_texts.get("period", []),
        *_xlsx_locator_date_aliases(clean_text),
    ]
    return _query_evidence_axis_hit(
        axis=axis,
        planner=planner,
        field_texts=field_texts,
        metadata_values={},
    )


def _xlsx_locator_same_source_document_identity(
    base_candidate: Mapping[str, Any],
    sibling_context: Mapping[str, Any],
) -> bool:
    base_doc_id = _clean(base_candidate.get("doc_id"))
    sibling_doc_id = _clean(sibling_context.get("doc_id"))
    return bool(base_doc_id and sibling_doc_id and base_doc_id == sibling_doc_id)


def _xlsx_locator_same_source_row_context_window(
    *,
    row: Mapping[str, Any],
    base_candidate: Mapping[str, Any],
    sibling_context: Mapping[str, Any],
    clean_text: str,
) -> str:
    planner = _query_evidence_planner_for_row(row)
    if not planner:
        return ""
    base_row_index = _clean(base_candidate.get("row_index_1based"))
    sibling_row_index = _xlsx_locator_source_owned_value(sibling_context, "row_index_1based")
    if not base_row_index or not sibling_row_index or base_row_index != sibling_row_index:
        return ""
    source_owned_text, _source_owned_fields = _xlsx_locator_source_owned_text(sibling_context)
    context_text = " | ".join(part for part in (source_owned_text, clean_text) if part)
    segments = _xlsx_locator_table_segments(context_text)
    if not segments:
        return ""
    matched_windows: list[tuple[str, str]] = []
    for index, _segment in enumerate(segments):
        window_segments = segments[max(0, index - 6) : min(len(segments), index + 7)]
        window_text = " | ".join(window_segments)
        if not _xlsx_locator_axis_hit_in_text("period", planner, window_text):
            continue
        if not _xlsx_locator_axis_hit_in_text("row_entity", planner, window_text):
            continue
        period_signature = "|".join(
            sorted(
                {
                    normalize_answer_text(alias)
                    for alias in _xlsx_locator_date_aliases(window_text)
                    if _clean(alias)
                }
            )
        )
        row_signature = "|".join(
            normalize_answer_text(value)
            for value in _query_evidence_axis_values(planner, "row_entity")
            if _axis_value_hits_text([value], [window_text])
        )
        signature = "|".join(part for part in (row_signature, period_signature) if part)
        if signature:
            matched_windows.append((signature, window_text))
    signatures = {signature for signature, _window in matched_windows if signature}
    if len(signatures) != 1:
        return ""
    return min((window for _signature, window in matched_windows), key=len)


def _xlsx_locator_sibling_row_context_window(
    *,
    row: Mapping[str, Any],
    base_candidate: Mapping[str, Any],
    sibling_context: Mapping[str, Any],
) -> str:
    planner = _query_evidence_planner_for_row(row)
    if not planner:
        return ""
    display_value = _clean(base_candidate.get("display_value"))
    if not display_value:
        return ""
    if not _clean(base_candidate.get("target_column")) and not _clean(base_candidate.get("column_label")):
        return ""
    if not _clean(base_candidate.get("sheet")) or not _clean(base_candidate.get("cell_range")):
        return ""
    if _clean(base_candidate.get("sheet")) != _xlsx_locator_source_owned_value(sibling_context, "sheet"):
        return ""
    if _clean(base_candidate.get("cell_range")) != _xlsx_locator_source_owned_value(sibling_context, "cell_range"):
        return ""
    if _clean(base_candidate.get("source_atom_id")) == _clean(sibling_context.get("source_atom_id")):
        return ""
    if not _xlsx_locator_same_source_document_identity(base_candidate, sibling_context):
        return ""
    if not _has_sourceatom_evidence_identity(sibling_context) or not _clean(sibling_context.get("doc_id")):
        return ""
    clean_text = _strip_xlsx_locator_forbidden_text_segments(_gate_row_text(sibling_context))
    if not clean_text:
        return ""
    same_row_window = _xlsx_locator_same_source_row_context_window(
        row=row,
        base_candidate=base_candidate,
        sibling_context=sibling_context,
        clean_text=clean_text,
    )
    if same_row_window:
        return same_row_window
    return ""


def _xlsx_locator_refresh_candidate_decision(
    *,
    row: Mapping[str, Any],
    context: Mapping[str, Any],
    candidate: MutableMapping[str, Any],
    locator_text: str,
    locator_text_source: str,
    locator_text_fields_used: Sequence[str],
    extra_input_fields_used: Sequence[str] = (),
) -> None:
    query_anchors = _query_focus_anchors_for_row(row)
    support_text = _gate_support_text(candidate)
    _xlsx_locator_apply_source_date_alias_diagnostic(candidate, support_text)
    if _as_list(candidate.get("source_date_aliases")):
        locator_text_fields_used = tuple(dict.fromkeys([*locator_text_fields_used, "source_date_aliases"]))
    matched = sorted(_gate_anchor_hits(query_anchors, [support_text]))
    missing = sorted(query_anchors - set(matched))
    query_anchor_coverage = _gate_coverage(query_anchors, set(matched))
    matched_required_axes, missing_required_axes = _xlsx_locator_validated_required_axis_hits(
        row=row,
        candidate=candidate,
    )
    required_axes_available = bool(matched_required_axes or missing_required_axes)
    planner = _query_evidence_planner_for_row(row)
    source_family_hint = _clean(planner.get("source_family_hint")).lower() if planner else ""
    source_family_hint_allows_xlsx = source_family_hint in {"", "unknown", "xlsx"}
    previous_forbidden_seen = {
        _canonical_xlsx_locator_field_name(field)
        for field in (
            *_as_list(candidate.get("forbidden_input_fields_rejected")),
            *_as_list(candidate.get("forbidden_input_fields_used_for_candidate")),
        )
        if _clean(field)
    }
    forbidden_input_fields_seen = sorted(
        {
            *previous_forbidden_seen,
            *_collect_xlsx_locator_forbidden_input_fields(context),
        }
    )
    forbidden_seen_fail_closed = _xlsx_locator_forbidden_seen_fields_requiring_fail_closed(
        forbidden_input_fields_seen
    )
    used_input_view = _xlsx_locator_used_input_view(
        locator_text=locator_text,
        locator_text_fields_used=locator_text_fields_used,
        candidate=candidate,
    )
    for field in extra_input_fields_used:
        value = _clean(candidate.get(field))
        if value:
            used_input_view[field] = value
    forbidden_input_fields = sorted(
        {
            *(
                _canonical_xlsx_locator_field_name(field)
                for field in _as_list(candidate.get("forbidden_input_fields_used_for_candidate"))
                if _clean(field)
            ),
            *_collect_xlsx_locator_forbidden_input_fields(used_input_view),
        }
    )
    input_fields_used = sorted(
        {
            *locator_text_fields_used,
            *extra_input_fields_used,
            *(
                field
                for field in XLSX_LOCATOR_SOURCE_OWNED_FIELDS
                if _clean(context.get(field))
                or _clean(candidate.get(field))
                or any(_clean(source.get(field)) for source in _xlsx_locator_metadata_sources(context))
            ),
            "locator_text_source",
        }
    )
    confidence_tier = _xlsx_locator_confidence_tier(candidate)
    query_anchor_sufficient = not query_anchors or query_anchor_coverage >= EVIDENCE_GATE_MIN_QUERY_ANCHOR_COVERAGE
    required_axes_sufficient = required_axes_available and not missing_required_axes
    accepted = bool(
        not forbidden_input_fields
        and not forbidden_seen_fail_closed
        and _has_sourceatom_evidence_identity(candidate)
        and _clean(candidate.get("doc_id"))
        and _clean(candidate.get("text"))
        and source_family_hint_allows_xlsx
        and (required_axes_sufficient if required_axes_available else bool(matched and query_anchor_sufficient))
        and confidence_tier == "high"
    )
    if accepted:
        rejection_reason = ""
    elif forbidden_input_fields or forbidden_seen_fail_closed:
        rejection_reason = "forbidden_input_fields_present"
    elif not source_family_hint_allows_xlsx:
        rejection_reason = "source_family_hint_mismatch"
    elif required_axes_available and missing_required_axes:
        rejection_reason = "missing_validated_required_axes_after_tool"
    elif not matched or not query_anchor_sufficient:
        rejection_reason = "missing_query_anchor_after_tool"
    elif confidence_tier != "high":
        rejection_reason = "missing_required_locator_axes"
    else:
        rejection_reason = "missing_source_identity_doc_id_text_or_locator_axes"
    candidate.update(
        {
            "locator_text_source": locator_text_source,
            "matched_query_anchors": matched,
            "missing_query_anchors_after_tool": missing,
            "matched_validated_required_axes": matched_required_axes,
            "missing_validated_required_axes": missing_required_axes,
            "confidence_tier": confidence_tier,
            "query_anchor_coverage": query_anchor_coverage,
            "validated_required_axes_coverage": _gate_coverage(
                matched_required_axes + missing_required_axes,
                matched_required_axes,
            ),
            "source_family_hint": source_family_hint,
            "source_family_hint_matches_candidate": source_family_hint_allows_xlsx,
            "accepted_for_regating": accepted,
            "rejection_reason": rejection_reason,
            "input_fields_used": input_fields_used,
            "forbidden_input_fields_seen": forbidden_input_fields_seen,
            "forbidden_input_fields_used_for_candidate": forbidden_input_fields,
            "forbidden_input_fields_rejected": forbidden_seen_fail_closed,
        }
    )


def _xlsx_locator_sibling_row_composite_candidates(
    *,
    row: Mapping[str, Any],
    source_contexts: Sequence[Mapping[str, Any]],
    base_candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    composites: list[dict[str, Any]] = []
    for base_candidate in base_candidates:
        if _clean(base_candidate.get("source_family")).upper() != "XLSX":
            continue
        if base_candidate.get("accepted_for_regating") is True:
            continue
        if "period" not in _as_list(base_candidate.get("missing_validated_required_axes")):
            continue
        if not _clean(base_candidate.get("display_value")):
            continue
        if _clean(base_candidate.get("confidence_tier")) != "high":
            continue
        base_composites: list[dict[str, Any]] = []
        for sibling_context in source_contexts:
            if not isinstance(sibling_context, Mapping):
                continue
            if _clean(sibling_context.get("source_family")).upper() not in {"XLSX", "XLS", "SPREADSHEET"}:
                continue
            sibling_window = _xlsx_locator_sibling_row_context_window(
                row=row,
                base_candidate=base_candidate,
                sibling_context=sibling_context,
            )
            if not sibling_window:
                continue
            composite = dict(base_candidate)
            source_row_context_source_atom_id = _clean(sibling_context.get("source_atom_id"))
            source_row_context_doc_id = _clean(sibling_context.get("doc_id"))
            base_support_text = _xlsx_locator_source_owned_text(composite)[0]
            support_text = " | ".join(
                part
                for part in (
                    base_support_text,
                    f"source_row_context={sibling_window}",
                )
                if part
            )
            synthetic_seed = "|".join(
                [
                    _clean(base_candidate.get("source_atom_id")),
                    source_row_context_source_atom_id,
                    _clean(base_candidate.get("sheet")),
                    _clean(base_candidate.get("cell_range")),
                    _clean(base_candidate.get("target_column")),
                    _clean(base_candidate.get("display_value")),
                ]
            )
            composite.update(
                {
                    "text": support_text,
                    "granularity": "xlsx_locator_sibling_row_composite",
                    "locator_text_source": XLSX_LOCATOR_SIBLING_ROW_COMPOSITE_SOURCE,
                    "synthetic_table_id": f"{XLSX_LOCATOR_SYNTHETIC_TABLE_ID_PREFIX}{_sha256_text(synthetic_seed)[:16]}",
                    "source_row_context_source_atom_id": source_row_context_source_atom_id,
                    "source_row_context_doc_id": source_row_context_doc_id,
                }
            )
            locator_text_fields_used = tuple(
                dict.fromkeys(
                    [
                        *_as_list(base_candidate.get("input_fields_used")),
                        "text",
                        "source_row_context_source_atom_id",
                        "source_row_context_doc_id",
                        "synthetic_table_id",
                    ]
                )
            )
            _xlsx_locator_refresh_candidate_decision(
                row=row,
                context=sibling_context,
                candidate=composite,
                locator_text=support_text,
                locator_text_source=XLSX_LOCATOR_SIBLING_ROW_COMPOSITE_SOURCE,
                locator_text_fields_used=locator_text_fields_used,
                extra_input_fields_used=("source_row_context_source_atom_id", "source_row_context_doc_id"),
            )
            if composite.get("accepted_for_regating") is True:
                base_composites.append(composite)
        if len(base_composites) == 1:
            composites.extend(base_composites)
    return composites


def _xlsx_locator_source_owned_diversification_key(candidate: Mapping[str, Any]) -> str:
    parts = [
        _clean(candidate.get("sheet")),
        _clean(candidate.get("table_id")) or _clean(candidate.get("synthetic_table_id")),
        _clean(candidate.get("cell_range")),
        _clean(candidate.get("target_column"))
        or _clean(candidate.get("column_label"))
        or _clean(candidate.get("header_path"))
        or _clean(candidate.get("row_label")),
    ]
    return "|".join(part or "-" for part in parts)


def _xlsx_locator_with_candidate_budget_metadata(
    candidate: Mapping[str, Any],
    *,
    pool_count_before_budget: int,
    dedupe_removed_count: int,
    budget_exhausted: bool,
) -> dict[str, Any]:
    updated = dict(candidate)
    updated["candidate_budget_per_query"] = XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET
    updated["candidate_pool_count_before_budget"] = int(pool_count_before_budget)
    updated["candidate_budget_exhausted"] = bool(budget_exhausted)
    updated["dedupe_removed_candidate_count"] = int(dedupe_removed_count)
    updated["source_owned_candidate_diversification"] = True
    updated["source_owned_candidate_diversification_policy"] = XLSX_LOCATOR_SOURCE_OWNED_DIVERSIFICATION_POLICY
    updated["source_owned_diversification_key"] = _xlsx_locator_source_owned_diversification_key(updated)
    updated["same_sheet_candidate"] = bool(_clean(updated.get("sheet")))
    updated["same_table_candidate"] = bool(_clean(updated.get("table_id")) or _clean(updated.get("synthetic_table_id")))
    updated["same_range_candidate"] = bool(_clean(updated.get("cell_range")))
    return updated


def _select_xlsx_locator_budgeted_candidates(
    ordered_candidates: Sequence[Mapping[str, Any]],
    *,
    dedupe_removed_count: int,
) -> list[dict[str, Any]]:
    selected: list[Mapping[str, Any]] = []
    selected_identities: set[str] = set()
    selected_keys: set[str] = set()
    for candidate in ordered_candidates:
        key = _xlsx_locator_source_owned_diversification_key(candidate)
        identity = f"{_context_identity(candidate)}:{_sha256_text(_gate_row_text(candidate))}"
        if key in selected_keys:
            continue
        selected.append(candidate)
        selected_identities.add(identity)
        selected_keys.add(key)
        if len(selected) >= XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET:
            break
    if len(selected) < XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET:
        for candidate in ordered_candidates:
            identity = f"{_context_identity(candidate)}:{_sha256_text(_gate_row_text(candidate))}"
            if identity in selected_identities:
                continue
            selected.append(candidate)
            selected_identities.add(identity)
            if len(selected) >= XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET:
                break
    pool_count = len(ordered_candidates)
    budget_exhausted = pool_count > XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET
    return [
        _xlsx_locator_with_candidate_budget_metadata(
            candidate,
            pool_count_before_budget=pool_count,
            dedupe_removed_count=dedupe_removed_count,
            budget_exhausted=budget_exhausted,
        )
        for candidate in selected
    ]


def _xlsx_locator_candidate_sort_key(candidate: Mapping[str, Any], source_index: int) -> tuple[float, ...]:
    tier_scores = {"high": 3.0, "medium": 2.0, "low": 1.0}
    accepted_score = 1.0 if candidate.get("accepted_for_regating") is True else 0.0
    coverage_score = _safe_float(candidate.get("query_anchor_coverage"))
    tier_score = tier_scores.get(_clean(candidate.get("confidence_tier")), 0.0)
    matched_count = float(len(_as_list(candidate.get("matched_query_anchors"))))
    missing_count = float(len(_as_list(candidate.get("missing_query_anchors_after_tool"))))
    return (-accepted_score, -coverage_score, -tier_score, -matched_count, missing_count, float(source_index))


def _xlsx_locator_tool_candidates(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[tuple[tuple[float, ...], dict[str, Any]]] = []
    seen: set[str] = set()
    dedupe_removed_count = 0
    raw_source_contexts = _as_list(row.get(INTERNAL_XLSX_LOCATOR_SOURCE_CONTEXTS_KEY)) or _as_list(
        row.get("retrieved_contexts")
    )
    source_contexts = [context for context in raw_source_contexts if isinstance(context, Mapping)]
    for source_index, context in enumerate(source_contexts):
        candidate = _xlsx_locator_candidate_from_context(row, context)
        if candidate is None:
            continue
        identity = _context_identity(candidate)
        text_hash = _sha256_text(_gate_row_text(candidate))
        dedupe_key = f"{identity}:{text_hash}"
        if dedupe_key in seen:
            dedupe_removed_count += 1
            continue
        seen.add(dedupe_key)
        candidates.append((_xlsx_locator_candidate_sort_key(candidate, source_index), candidate))
    base_candidates = [candidate for _sort_key, candidate in candidates]
    for composite_index, candidate in enumerate(
        _xlsx_locator_sibling_row_composite_candidates(
            row=row,
            source_contexts=source_contexts,
            base_candidates=base_candidates,
        )
    ):
        identity = _context_identity(candidate)
        text_hash = _sha256_text(_gate_row_text(candidate))
        dedupe_key = f"{identity}:{text_hash}"
        if dedupe_key in seen:
            dedupe_removed_count += 1
            continue
        seen.add(dedupe_key)
        source_index = len(source_contexts) + composite_index
        candidates.append((_xlsx_locator_candidate_sort_key(candidate, source_index), candidate))
    candidates.sort(key=lambda item: item[0])
    return _select_xlsx_locator_budgeted_candidates(
        [candidate for _sort_key, candidate in candidates],
        dedupe_removed_count=dedupe_removed_count,
    )


def _xlsx_locator_source_context_snapshot(context: Mapping[str, Any]) -> dict[str, Any] | None:
    if _clean(context.get("source_family")).upper() not in {"XLSX", "XLS", "SPREADSHEET"}:
        return None
    locator_text, locator_text_source, locator_text_fields_used = _xlsx_locator_candidate_text(context)
    if not locator_text:
        return None
    snapshot: dict[str, Any] = {
        "source_family": _clean(context.get("source_family")) or "XLSX",
        "text": _clean(context.get("text")),
        "xlsx_locator_text": locator_text,
        "locator_text_source": locator_text_source,
        "locator_text_fields_used": list(locator_text_fields_used),
    }
    for key in (
        "chunk_id",
        "source_atom_id",
        "evidence_bundle_id",
        "doc_id",
        "granularity",
        "rank",
    ):
        value = context.get(key)
        if _source_value_present(value):
            snapshot[key] = value
    for field in XLSX_LOCATOR_SOURCE_OWNED_FIELDS:
        value = _xlsx_locator_source_owned_value(context, field)
        if value:
            snapshot[field] = value
    metadata = context.get("metadata") if isinstance(context.get("metadata"), Mapping) else {}
    materialization = _clean(
        context.get("candidate_surface_materialization")
        or metadata.get("candidate_surface_materialization")
    )
    if materialization == "xlsx_row_value_bundle_v1":
        aliases: list[str] = []
        seen_aliases: set[str] = set()
        for source in (context, metadata):
            for field in ("source_date_aliases", "source_date_aliases_json", "source_date_alias"):
                for alias in _xlsx_locator_source_date_alias_candidate_values(source.get(field)):
                    if alias not in seen_aliases:
                        aliases.append(alias)
                        seen_aliases.add(alias)
        snapshot["candidate_surface_materialization"] = materialization
        if aliases:
            snapshot["source_date_aliases"] = aliases
        period_cells = _parse_jsonish(
            context.get("same_row_period_cells_json") or metadata.get("same_row_period_cells_json")
        )
        if isinstance(period_cells, list) and period_cells:
            snapshot["same_row_period_cells_json"] = json.dumps(
                [cell for cell in period_cells if isinstance(cell, Mapping)],
                ensure_ascii=False,
                sort_keys=True,
            )
    period_cells = _parse_jsonish(
        context.get("same_row_period_cells_json") or metadata.get("same_row_period_cells_json")
    )
    if isinstance(period_cells, list) and period_cells:
        snapshot["same_row_period_cells_json"] = json.dumps(
            [cell for cell in period_cells if isinstance(cell, Mapping)],
            ensure_ascii=False,
            sort_keys=True,
        )
    forbidden_seen = sorted(_collect_xlsx_locator_forbidden_input_fields(context))
    if forbidden_seen:
        snapshot["forbidden_input_fields_seen"] = forbidden_seen
    return snapshot


def preserve_xlsx_locator_source_contexts(raw_outputs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    preserved: list[dict[str, Any]] = []
    for row in raw_outputs:
        output = dict(row)
        snapshots: list[dict[str, Any]] = []
        for context in _as_list(row.get("retrieved_contexts")):
            if not isinstance(context, Mapping):
                continue
            nested_snapshots = [
                dict(snapshot)
                for snapshot in _as_list(context.get(INTERNAL_XLSX_LOCATOR_SOURCE_CONTEXTS_KEY))
                if isinstance(snapshot, Mapping)
            ]
            if nested_snapshots:
                snapshots.extend(nested_snapshots)
                continue
            snapshot = _xlsx_locator_source_context_snapshot(context)
            if snapshot is not None:
                snapshots.append(snapshot)
        if snapshots:
            output[INTERNAL_XLSX_LOCATOR_SOURCE_CONTEXTS_KEY] = snapshots
        preserved.append(output)
    return preserved


def _xlsx_locator_residual_snapshot(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    breakdown = build_xlsx_pdf_residual_breakdown(items=[], rows=rows)
    return {
        "schema_version": breakdown["schema_version"],
        "residual_row_count": breakdown["residual_row_count"],
        "classification_counts": dict(breakdown["classification_counts"]),
        "excluded_classification_counts": dict(breakdown["excluded_classification_counts"]),
        "forbidden_shortcut_fields_seen": list(breakdown["forbidden_shortcut_fields_seen"]),
        "forbidden_shortcut_fields_used": list(breakdown["forbidden_shortcut_fields_used"]),
    }


def _annotate_xlsx_locator_source_row_context_doc_mismatches(
    candidates: Sequence[Mapping[str, Any]],
) -> int:
    count = 0
    for base_index, base_candidate in enumerate(candidates):
        if not isinstance(base_candidate, Mapping):
            continue
        if _clean(base_candidate.get("source_family")).upper() not in {"XLSX", "XLS", "SPREADSHEET"}:
            continue
        if "period" not in _as_list(base_candidate.get("missing_validated_required_axes")):
            continue
        if not _clean(base_candidate.get("display_value")):
            continue
        if not _clean(base_candidate.get("target_column")) and not _clean(base_candidate.get("column_label")):
            continue
        base_sheet = _clean(base_candidate.get("sheet"))
        base_cell_range = _clean(base_candidate.get("cell_range"))
        base_doc_id = _clean(base_candidate.get("doc_id"))
        if not base_sheet or not base_cell_range or not base_doc_id:
            continue
        base_source_atom_id = _clean(base_candidate.get("source_atom_id"))
        blocked_by_doc_identity = False
        for sibling_index, sibling_candidate in enumerate(candidates):
            if base_index == sibling_index or not isinstance(sibling_candidate, Mapping):
                continue
            if _clean(sibling_candidate.get("source_family")).upper() not in {"XLSX", "XLS", "SPREADSHEET"}:
                continue
            if base_sheet != _clean(sibling_candidate.get("sheet")):
                continue
            if base_cell_range != _clean(sibling_candidate.get("cell_range")):
                continue
            if base_source_atom_id and base_source_atom_id == _clean(sibling_candidate.get("source_atom_id")):
                continue
            sibling_doc_id = _clean(sibling_candidate.get("doc_id"))
            if not sibling_doc_id or sibling_doc_id == base_doc_id:
                continue
            sibling_axes = {
                _clean(axis)
                for axis in _as_list(sibling_candidate.get("matched_validated_required_axes"))
                if _clean(axis)
            }
            if {"period", "row_entity"}.issubset(sibling_axes):
                if isinstance(base_candidate, MutableMapping):
                    base_candidate["source_row_context_source_atom_id"] = _clean(
                        sibling_candidate.get("source_atom_id")
                    )
                    base_candidate["source_row_context_doc_id"] = sibling_doc_id
                blocked_by_doc_identity = True
                break
        if blocked_by_doc_identity:
            count += 1
    return count


def _xlsx_locator_tool_use_meta(
    *,
    status: str,
    candidates: Sequence[Mapping[str, Any]],
    gated_row: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    accepted_candidates = [candidate for candidate in candidates if candidate.get("accepted_for_regating") is True]
    candidate_pool_count_before_budget = max(
        (
            int(candidate.get("candidate_pool_count_before_budget") or 0)
            for candidate in candidates
            if isinstance(candidate, Mapping)
        ),
        default=0,
    )
    if candidate_pool_count_before_budget <= 0:
        candidate_pool_count_before_budget = len(candidates)
    gate = gated_row.get("evidence_gate") if isinstance(gated_row, Mapping) and isinstance(gated_row.get("evidence_gate"), Mapping) else {}
    remaining_missing = [
        _clean(anchor)
        for anchor in _as_list(gate.get("missing_query_anchors"))
        if _clean(anchor)
    ]
    matched = sorted(
        {
            _clean(anchor)
            for candidate in candidates
            for anchor in _as_list(candidate.get("matched_query_anchors"))
            if _clean(anchor)
        }
    )
    matched_required_axes = sorted(
        {
            _clean(axis)
            for candidate in candidates
            for axis in _as_list(candidate.get("matched_validated_required_axes"))
            if _clean(axis)
        },
        key=lambda axis: QUERY_EVIDENCE_AXIS_ORDER.index(axis) if axis in QUERY_EVIDENCE_AXIS_ORDER else len(QUERY_EVIDENCE_AXIS_ORDER),
    )
    remaining_required_axes = sorted(
        {
            _clean(axis)
            for candidate in candidates
            for axis in _as_list(candidate.get("missing_validated_required_axes"))
            if _clean(axis) and _clean(axis) not in set(matched_required_axes)
        },
        key=lambda axis: QUERY_EVIDENCE_AXIS_ORDER.index(axis) if axis in QUERY_EVIDENCE_AXIS_ORDER else len(QUERY_EVIDENCE_AXIS_ORDER),
    )
    candidate_axis_rows: list[tuple[int, list[str], list[str]]] = []
    for index, candidate in enumerate(candidates):
        matched_axes = [
            _clean(axis)
            for axis in _as_list(candidate.get("matched_validated_required_axes"))
            if _clean(axis)
        ]
        missing_axes = [
            _clean(axis)
            for axis in _as_list(candidate.get("missing_validated_required_axes"))
            if _clean(axis)
        ]
        if matched_axes or missing_axes:
            candidate_axis_rows.append((index, matched_axes, missing_axes))
    complete_candidate_count = sum(1 for _index, _matched, missing_axes in candidate_axis_rows if not missing_axes)
    if candidate_axis_rows:
        _best_index, _best_matched, best_missing_axes = min(
            candidate_axis_rows,
            key=lambda row: (
                len(row[2]),
                -len(row[1]),
                row[0],
            ),
        )
    else:
        best_missing_axes = []
    validated_axis_split_across_candidates = bool(
        candidate_axis_rows
        and complete_candidate_count == 0
        and matched_required_axes
        and not remaining_required_axes
    )
    source_row_context_candidate_count = sum(
        1
        for candidate in candidates
        if _clean(candidate.get("locator_text_source")) == XLSX_LOCATOR_SIBLING_ROW_COMPOSITE_SOURCE
    )
    source_row_context_doc_identity_mismatch_candidate_count = (
        _annotate_xlsx_locator_source_row_context_doc_mismatches(candidates)
    )
    return {
        "tool_name": XLSX_LOCATOR_TOOL_NAME,
        "execution_status": status,
        "candidate_count": len(candidates),
        "accepted_candidate_count": len(accepted_candidates),
        "complete_validated_axis_candidate_count": complete_candidate_count,
        "validated_axis_split_across_candidates": validated_axis_split_across_candidates,
        "source_row_context_candidate_count": source_row_context_candidate_count,
        "source_row_context_doc_identity_mismatch_candidate_count": source_row_context_doc_identity_mismatch_candidate_count,
        "source_row_context_blocked_by_doc_identity_mismatch": (
            source_row_context_doc_identity_mismatch_candidate_count > 0
        ),
        "source_row_context_fail_closed_policy": XLSX_LOCATOR_SOURCE_ROW_CONTEXT_FAIL_CLOSED_POLICY,
        "best_candidate_missing_validated_required_axes": best_missing_axes,
        "candidate_budget_per_query": XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET,
        "candidate_pool_count_before_budget": candidate_pool_count_before_budget,
        "candidate_budget_exhausted": candidate_pool_count_before_budget > XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET,
        "source_owned_candidate_diversification_policy": XLSX_LOCATOR_SOURCE_OWNED_DIVERSIFICATION_POLICY,
        "matched_query_anchors": matched,
        "remaining_missing_query_anchors": remaining_missing,
        "matched_validated_required_axes": matched_required_axes,
        "remaining_missing_validated_required_axes": remaining_required_axes,
        "input_policy": XLSX_LOCATOR_TOOL_POLICY,
        "output_policy": XLSX_LOCATOR_TOOL_OUTPUT_POLICY,
    }


def _xlsx_locator_tool_use_record(
    *,
    item_index: int,
    item_id: str,
    meta: Mapping[str, Any],
) -> XlsxLocatorToolUseRecord:
    return XlsxLocatorToolUseRecord(
        item_index=item_index,
        item_id=item_id,
        execution_status=_clean(meta.get("execution_status")),
        candidate_count=int(meta.get("candidate_count") or 0),
        accepted_candidate_count=int(meta.get("accepted_candidate_count") or 0),
        candidate_pool_count_before_budget=int(meta.get("candidate_pool_count_before_budget") or meta.get("candidate_count") or 0),
        complete_validated_axis_candidate_count=int(meta.get("complete_validated_axis_candidate_count") or 0),
        validated_axis_split_across_candidates=bool(meta.get("validated_axis_split_across_candidates") is True),
        source_row_context_candidate_count=int(meta.get("source_row_context_candidate_count") or 0),
        source_row_context_doc_identity_mismatch_candidate_count=int(
            meta.get("source_row_context_doc_identity_mismatch_candidate_count") or 0
        ),
        source_row_context_blocked_by_doc_identity_mismatch=bool(
            meta.get("source_row_context_blocked_by_doc_identity_mismatch") is True
        ),
        best_candidate_missing_validated_required_axes=tuple(
            _clean(axis)
            for axis in _as_list(meta.get("best_candidate_missing_validated_required_axes"))
            if _clean(axis)
        ),
        matched_query_anchors=tuple(_clean(anchor) for anchor in _as_list(meta.get("matched_query_anchors")) if _clean(anchor)),
        remaining_missing_query_anchors=tuple(
            _clean(anchor) for anchor in _as_list(meta.get("remaining_missing_query_anchors")) if _clean(anchor)
        ),
        matched_validated_required_axes=tuple(
            _clean(axis) for axis in _as_list(meta.get("matched_validated_required_axes")) if _clean(axis)
        ),
        remaining_missing_validated_required_axes=tuple(
            _clean(axis) for axis in _as_list(meta.get("remaining_missing_validated_required_axes")) if _clean(axis)
        ),
        source_family_hint=_clean(meta.get("source_family_hint")),
        query_task=_clean(meta.get("query_task")),
        before_gate_status=_clean(meta.get("before_gate_status")),
        after_gate_status=_clean(meta.get("after_gate_status")),
        before_residual_class=_clean(meta.get("before_residual_class")),
        after_residual_class=_clean(meta.get("after_residual_class")),
        input_policy=_clean(meta.get("input_policy")) or XLSX_LOCATOR_TOOL_POLICY,
        output_policy=_clean(meta.get("output_policy")) or XLSX_LOCATOR_TOOL_OUTPUT_POLICY,
    )


def _xlsx_locator_candidate_record(
    *,
    item_index: int,
    candidate_index: int,
    candidate: Mapping[str, Any],
) -> XlsxLocatorEvidenceCandidateRecord:
    return XlsxLocatorEvidenceCandidateRecord(
        item_index=item_index,
        candidate_index=candidate_index,
        source_family=_clean(candidate.get("source_family")),
        tool_name=_clean(candidate.get("tool_name")) or XLSX_LOCATOR_TOOL_NAME,
        tool_policy=_clean(candidate.get("tool_policy")) or XLSX_LOCATOR_TOOL_POLICY,
        source_atom_id=_clean(candidate.get("source_atom_id")),
        evidence_bundle_id=_clean(candidate.get("evidence_bundle_id")),
        doc_id=_clean(candidate.get("doc_id")),
        sheet=_clean(candidate.get("sheet")),
        cell_range=_clean(candidate.get("cell_range")),
        cell=_clean(candidate.get("cell")),
        row_index_1based=_clean(candidate.get("row_index_1based")),
        row_label=_clean(candidate.get("row_label")),
        column_label=_clean(candidate.get("column_label")),
        target_column=_clean(candidate.get("target_column")),
        header=_clean(candidate.get("header")),
        header_path=_clean(candidate.get("header_path")),
        table_id=_clean(candidate.get("table_id")),
        synthetic_table_id=_clean(candidate.get("synthetic_table_id")),
        display_value=_clean(candidate.get("display_value")),
        source_row_context_source_atom_id=_clean(candidate.get("source_row_context_source_atom_id")),
        source_row_context_doc_id=_clean(candidate.get("source_row_context_doc_id")),
        source_date_aliases=tuple(
            _clean(alias)
            for alias in _as_list(candidate.get("source_date_aliases"))
            if _clean(alias)
        ),
        same_row_period_cells=tuple(
            dict(packet)
            for packet in _as_list(candidate.get("same_row_period_cells"))
            if isinstance(packet, Mapping)
        ),
        locator_text_source=_clean(candidate.get("locator_text_source")),
        matched_query_anchors=tuple(
            _clean(anchor) for anchor in _as_list(candidate.get("matched_query_anchors")) if _clean(anchor)
        ),
        missing_query_anchors_after_tool=tuple(
            _clean(anchor)
            for anchor in _as_list(candidate.get("missing_query_anchors_after_tool"))
            if _clean(anchor)
        ),
        matched_validated_required_axes=tuple(
            _clean(axis)
            for axis in _as_list(candidate.get("matched_validated_required_axes"))
            if _clean(axis)
        ),
        missing_validated_required_axes=tuple(
            _clean(axis)
            for axis in _as_list(candidate.get("missing_validated_required_axes"))
            if _clean(axis)
        ),
        confidence_tier=_clean(candidate.get("confidence_tier")) or "low",
        accepted_for_regating=candidate.get("accepted_for_regating") is True,
        rejection_reason=_clean(candidate.get("rejection_reason")),
        input_fields_used=tuple(_clean(field) for field in _as_list(candidate.get("input_fields_used")) if _clean(field)),
        source_owned_same_candidate_package=candidate.get("source_owned_same_candidate_package") is True,
        source_owned_same_candidate_package_policy=_clean(candidate.get("source_owned_same_candidate_package_policy")),
        xlsx_required_axis_materializer_tool_output=candidate.get("xlsx_required_axis_materializer_tool_output") is True,
        xlsx_required_axis_materializer_tool_name=_clean(candidate.get("xlsx_required_axis_materializer_tool_name")),
        xlsx_required_axis_materializer_execution_status=_clean(
            candidate.get("xlsx_required_axis_materializer_execution_status")
        ),
        xlsx_required_axis_materializer_materialized_axes=tuple(
            _clean(axis)
            for axis in _as_list(candidate.get("xlsx_required_axis_materializer_materialized_axes"))
            if _clean(axis)
        ),
        xlsx_required_axis_materializer_rejected_context_count=int(
            candidate.get("xlsx_required_axis_materializer_rejected_context_count") or 0
        ),
        xlsx_required_axis_materializer_report_only_diagnostic=(
            candidate.get("xlsx_required_axis_materializer_report_only_diagnostic") is True
        ),
        xlsx_required_axis_materializer_official_metric=(
            candidate.get("xlsx_required_axis_materializer_official_metric") is True
        ),
        xlsx_required_axis_materializer_accepted_for_regating=(
            candidate.get("xlsx_required_axis_materializer_accepted_for_regating") is True
        ),
    )


def _anchor_classifier_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row.get("query_anchor_classifier")
        for row in rows
        if isinstance(row.get("query_anchor_classifier"), Mapping)
    ]


def _anchor_classifier_required_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    classifiers = _anchor_classifier_rows(rows)
    before = sorted(
        {
            _clean(anchor)
            for classifier in classifiers
            for anchor in _as_list(classifier.get("required_anchor_before"))
            if _clean(anchor)
        }
    )
    after = sorted(
        {
            _clean(anchor)
            for classifier in classifiers
            for anchor in _as_list(classifier.get("required_anchor_after"))
            if _clean(anchor)
        }
    )
    removed = sorted(
        {
            _clean(anchor)
            for classifier in classifiers
            for anchor in _as_list(classifier.get("removed_intent_tokens"))
            if _clean(anchor)
        }
    )
    restored = sorted(
        {
            _clean(anchor)
            for classifier in classifiers
            for anchor in _as_list(classifier.get("protected_intent_tokens_restored"))
            if _clean(anchor)
        }
    )
    status_counts = Counter(_clean(classifier.get("status")) or "unknown" for classifier in classifiers)
    return {
        "enabled": bool(classifiers),
        "row_count": len(classifiers),
        "before": {"anchor_count": len(before), "anchors": before},
        "after": {"anchor_count": len(after), "anchors": after},
        "removed_intent_tokens": removed,
        "protected_intent_tokens_restored": restored,
        "status_counts": dict(sorted(status_counts.items())),
    }


def _anchor_classifier_first_value(rows: Sequence[Mapping[str, Any]], key: str) -> str:
    for classifier in _anchor_classifier_rows(rows):
        value = _clean(classifier.get(key))
        if value:
            return value
    return ""


def _query_evidence_planner_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [
        row.get("query_evidence_planner")
        for row in rows
        if isinstance(row.get("query_evidence_planner"), Mapping)
    ]


def _query_evidence_planner_required_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    planners = _query_evidence_planner_rows(rows)
    status_counts = Counter(_clean(planner.get("planner_status")) or "unknown" for planner in planners)
    source_family_counts = Counter(_clean(planner.get("source_family_hint")) or "unknown" for planner in planners)
    query_task_counts = Counter(_clean(planner.get("query_task")) or "unknown" for planner in planners)
    axes = _ordered_query_evidence_axes(
        axis
        for planner in planners
        for axis in _as_list(planner.get("validated_required_axes"))
        if _clean(axis)
    )
    return {
        "enabled": bool(planners),
        "row_count": len(planners),
        "status_counts": dict(sorted(status_counts.items())),
        "source_family_hint_counts": dict(sorted(source_family_counts.items())),
        "query_task_counts": dict(sorted(query_task_counts.items())),
        "validated_required_axes": axes,
    }


def _build_xlsx_locator_run_record(
    *,
    before_rows: Sequence[Mapping[str, Any]],
    after_rows: Sequence[Mapping[str, Any]],
    gate_before: Mapping[str, Any],
    gate_after: Mapping[str, Any],
    decisions: Sequence[Mapping[str, Any]],
) -> XlsxLocatorRunRecord:
    xlsx_decisions = [
        decision
        for decision in decisions
        if _clean(decision.get("proposed_action")) == "xlsx_cell_or_table_tool"
    ]
    forbidden_seen = sorted(
        {
            _clean(field)
            for decision in xlsx_decisions
            for field in _as_list(decision.get("forbidden_input_fields_seen"))
            if _clean(field)
        }
    )
    forbidden_used = sorted(
        {
            _clean(field)
            for decision in xlsx_decisions
            for field in _as_list(decision.get("forbidden_input_fields_used"))
            if _clean(field)
        }
    )
    forbidden_rejected = sorted(
        {
            _clean(field)
            for decision in xlsx_decisions
            for candidate in _as_list(decision.get("candidates"))
            if isinstance(candidate, Mapping)
            and _clean(candidate.get("rejection_reason")) == "forbidden_input_fields_present"
            for field in _as_list(candidate.get("forbidden_input_fields_rejected"))
            if _clean(field)
        }
    )
    tool_uses: list[XlsxLocatorToolUseRecord] = []
    candidates: list[XlsxLocatorEvidenceCandidateRecord] = []
    for decision in xlsx_decisions:
        item_index = int(decision.get("item_index") or 0)
        item_id = _clean(decision.get("item_id")) or _report_item_id(
            before_rows[item_index] if item_index < len(before_rows) else {},
            item_index,
        )
        before_row = before_rows[item_index] if item_index < len(before_rows) else {}
        after_row = after_rows[item_index] if item_index < len(after_rows) else {}
        before_residual = _classify_xlsx_pdf_residual_row(before_row) if isinstance(before_row, Mapping) else {}
        after_residual = _classify_xlsx_pdf_residual_row(after_row) if isinstance(after_row, Mapping) else {}
        before_gate = before_row.get("evidence_gate") if isinstance(before_row.get("evidence_gate"), Mapping) else {}
        after_gate = after_row.get("evidence_gate") if isinstance(after_row.get("evidence_gate"), Mapping) else {}
        planner_projection = _query_evidence_item_projection(before_row) if isinstance(before_row, Mapping) else {}
        meta = dict(decision.get("tool_use")) if isinstance(decision.get("tool_use"), Mapping) else {}
        meta.update(
            {
                "source_family_hint": _clean(planner_projection.get("source_family_hint")),
                "query_task": _clean(planner_projection.get("query_task")),
                "before_gate_status": _clean(before_gate.get("answer_gate_decision")),
                "after_gate_status": _clean(after_gate.get("answer_gate_decision")),
                "before_residual_class": _clean(before_residual.get("classification")),
                "after_residual_class": _clean(after_residual.get("classification")),
            }
        )
        tool_uses.append(_xlsx_locator_tool_use_record(item_index=item_index, item_id=item_id, meta=meta))
        for candidate_index, candidate in enumerate(_as_list(decision.get("candidates"))):
            if isinstance(candidate, Mapping):
                candidates.append(
                    _xlsx_locator_candidate_record(
                        item_index=item_index,
                        candidate_index=candidate_index,
                        candidate=candidate,
                    )
                )
    accepted_candidate_count = sum(int(decision.get("accepted_candidate_count") or 0) for decision in xlsx_decisions)
    candidate_count = sum(int(decision.get("candidate_count") or 0) for decision in xlsx_decisions)
    tool_invocation_count = sum(int(decision.get("tool_call_count_executed") or 0) for decision in xlsx_decisions)
    anchor_summary = _anchor_classifier_required_summary(before_rows)
    query_planner_summary = _query_evidence_planner_required_summary(before_rows)
    return XlsxLocatorRunRecord(
        schema_version=XLSX_LOCATOR_TOOL_EXECUTE_ONCE_SCHEMA_VERSION,
        enabled=True,
        report_only_diagnostic=True,
        official_metric=False,
        tool_name=XLSX_LOCATOR_TOOL_NAME,
        eligible_failed_row_count=len(xlsx_decisions),
        tool_invocation_count=tool_invocation_count,
        accepted_candidate_count=accepted_candidate_count,
        rejected_candidate_count=max(0, candidate_count - accepted_candidate_count),
        gate_delta_record=XlsxLocatorGateDeltaRecord(
            before_gate=dict(gate_before),
            after_gate=dict(gate_after),
            gate_delta=_agentic_planner_gate_delta(gate_before, gate_after),
            residual_before=_xlsx_locator_residual_snapshot(before_rows),
            residual_after=_xlsx_locator_residual_snapshot(after_rows),
        ),
        guardrail_record=XlsxLocatorGuardrailRecord(
            forbidden_input_fields_seen=tuple(forbidden_seen),
            forbidden_input_fields_used=tuple(forbidden_used),
            forbidden_input_fields_rejected=tuple(forbidden_rejected),
        ),
        anchor_classifier_model=_anchor_classifier_first_value(before_rows, "model"),
        anchor_classifier_prompt_version=_anchor_classifier_first_value(before_rows, "prompt_version"),
        anchor_classifier_raw_payload_written=any(
            bool(classifier.get("raw_payload_written")) for classifier in _anchor_classifier_rows(before_rows)
        ),
        required_anchor_summary=anchor_summary,
        query_planner_summary=query_planner_summary,
        tool_uses=tuple(tool_uses),
        candidates=tuple(candidates),
    )


def _xlsx_locator_transition(before: str, after: str) -> str:
    return f"{_clean(before) or 'unknown'}->{_clean(after) or 'unknown'}"


def _xlsx_locator_query_anchor_tool_acceptance_diagnostic(record: XlsxLocatorRunRecord) -> dict[str, Any]:
    query_anchor_rejected = [
        candidate
        for candidate in record.candidates
        if not candidate.accepted_for_regating
        and candidate.rejection_reason == "missing_query_anchor_after_tool"
    ]
    query_anchor_rejected_item_indexes = {candidate.item_index for candidate in query_anchor_rejected}
    missing_anchor_counts = Counter(
        anchor
        for candidate in query_anchor_rejected
        for anchor in candidate.missing_query_anchors_after_tool
        if _clean(anchor)
    )
    source_owned_field_presence = {
        "cell_range": sum(1 for candidate in query_anchor_rejected if _clean(candidate.cell_range)),
        "display_value": sum(1 for candidate in query_anchor_rejected if _clean(candidate.display_value)),
        "row_label": sum(1 for candidate in query_anchor_rejected if _clean(candidate.row_label)),
        "source_date_aliases": sum(1 for candidate in query_anchor_rejected if candidate.source_date_aliases),
        "target_column": sum(1 for candidate in query_anchor_rejected if _clean(candidate.target_column)),
    }
    item_candidate_counts = Counter(candidate.item_index for candidate in query_anchor_rejected)
    source_family_hint_counts = Counter(
        _clean(tool_use.source_family_hint) or "unknown"
        for tool_use in record.tool_uses
    )
    query_task_counts = Counter(
        _clean(tool_use.query_task) or "unknown"
        for tool_use in record.tool_uses
    )
    gate_transition_counts = Counter(
        _xlsx_locator_transition(tool_use.before_gate_status, tool_use.after_gate_status)
        for tool_use in record.tool_uses
    )
    residual_transition_counts = Counter(
        _xlsx_locator_transition(tool_use.before_residual_class, tool_use.after_residual_class)
        for tool_use in record.tool_uses
    )
    rejection_by_hint_task = Counter(
        (
            _clean(tool_use.source_family_hint) or "unknown",
            _clean(tool_use.query_task) or "unknown",
            "missing_query_anchor_after_tool" if tool_use.item_index in query_anchor_rejected_item_indexes else "other",
        )
        for tool_use in record.tool_uses
    )
    item_summaries = [
        {
            "item_index": tool_use.item_index,
            "source_family_hint": _clean(tool_use.source_family_hint) or "unknown",
            "query_task": _clean(tool_use.query_task) or "unknown",
            "execution_status": tool_use.execution_status,
            "candidate_count": tool_use.candidate_count,
            "accepted_candidate_count": tool_use.accepted_candidate_count,
            "missing_query_anchor_after_tool_candidate_count": item_candidate_counts.get(tool_use.item_index, 0),
            "remaining_missing_query_anchors": list(tool_use.remaining_missing_query_anchors),
            "remaining_missing_validated_required_axes": list(tool_use.remaining_missing_validated_required_axes),
            "gate_transition": _xlsx_locator_transition(tool_use.before_gate_status, tool_use.after_gate_status),
            "residual_transition": _xlsx_locator_transition(
                tool_use.before_residual_class,
                tool_use.after_residual_class,
            ),
        }
        for tool_use in sorted(record.tool_uses, key=lambda use: use.item_index)
    ]
    return {
        "schema_version": XLSX_LOCATOR_QUERY_ANCHOR_TOOL_ACCEPTANCE_DIAGNOSTIC_SCHEMA_VERSION,
        "report_only_diagnostic": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "tool_invocation_count": record.tool_invocation_count,
        "candidate_count": len(record.candidates),
        "accepted_for_regating_candidate_count": record.accepted_candidate_count,
        "rejected_candidate_count": record.rejected_candidate_count,
        "missing_query_anchor_after_tool_candidate_count": len(query_anchor_rejected),
        "missing_query_anchor_after_tool_item_count": len(query_anchor_rejected_item_indexes),
        "query_anchor_rejected_with_complete_axes_candidate_count": sum(
            1
            for candidate in query_anchor_rejected
            if candidate.matched_validated_required_axes and not candidate.missing_validated_required_axes
        ),
        "query_anchor_rejected_with_missing_axes_candidate_count": sum(
            1 for candidate in query_anchor_rejected if candidate.missing_validated_required_axes
        ),
        "query_anchor_rejected_without_validated_axes_candidate_count": sum(
            1
            for candidate in query_anchor_rejected
            if not candidate.matched_validated_required_axes and not candidate.missing_validated_required_axes
        ),
        "source_family_hint_counts": dict(sorted(source_family_hint_counts.items())),
        "query_task_counts": dict(sorted(query_task_counts.items())),
        "gate_flip_direction_counts": dict(sorted(gate_transition_counts.items())),
        "residual_transition_counts": dict(sorted(residual_transition_counts.items())),
        "missing_query_anchor_after_tool_by_source_family_hint_query_task": [
            {
                "source_family_hint": source_family_hint,
                "query_task": query_task,
                "bucket": bucket,
                "item_count": count,
            }
            for (source_family_hint, query_task, bucket), count in sorted(rejection_by_hint_task.items())
        ],
        "top_missing_query_anchors": [
            {"anchor": anchor, "candidate_count": count}
            for anchor, count in sorted(missing_anchor_counts.items(), key=lambda item: (-item[1], item[0]))[:20]
        ],
        "source_owned_field_presence_on_query_anchor_rejected_candidates": source_owned_field_presence,
        "item_summaries": item_summaries,
        "uses_expected_fields": False,
        "uses_gold_fields": False,
        "uses_qrels_or_labels": False,
        "uses_ids_as_runtime_inputs": False,
        "uses_file_workbook_title": False,
        "uses_formula_or_normalized_value": False,
        "evidence_gate_loosened": record.guardrail_record.evidence_gate_loosened,
    }


def _agentic_xlsx_optional_clean_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(_clean(item) for item in value if _clean(item))


def _agentic_xlsx_ordered_axes(axes: Iterable[str]) -> tuple[str, ...]:
    cleaned = {_clean(axis) for axis in axes if _clean(axis)}
    return tuple(
        sorted(
            cleaned,
            key=lambda axis: QUERY_EVIDENCE_AXIS_ORDER.index(axis)
            if axis in QUERY_EVIDENCE_AXIS_ORDER
            else len(QUERY_EVIDENCE_AXIS_ORDER),
        )
    )


def agentic_xlsx_axis_inspector_tool(
    candidate: XlsxLocatorEvidenceCandidateRecord | Mapping[str, Any],
) -> AgenticXlsxAxisInspectionRecord:
    matched_axes = set(
        _agentic_xlsx_ordered_axes(
            _agentic_xlsx_optional_clean_tuple(
                _agentic_xlsx_record_value(candidate, "matched_validated_required_axes")
            )
        )
    )
    missing_axes = _agentic_xlsx_ordered_axes(
        _agentic_xlsx_optional_clean_tuple(
            _agentic_xlsx_record_value(candidate, "missing_validated_required_axes")
        )
    )
    source_owned_axis_evidence = {
        axis: "missing" if axis in missing_axes else ("matched" if axis in matched_axes else "not_required_or_not_observed")
        for axis in QUERY_EVIDENCE_COMMON_AXES
    }
    inspection = AgenticXlsxAxisInspectionRecord(
        has_required_period_axis="period" in matched_axes,
        has_required_entity_axis="row_entity" in matched_axes,
        has_required_measure_axis="target_column" in matched_axes,
        has_display_value="display_value" in matched_axes and "display_value" not in missing_axes,
        missing_axes=missing_axes,
        source_owned_axis_evidence=source_owned_axis_evidence,
    )
    validate_agentic_xlsx_axis_inspector_output("agentic_xlsx", inspection)
    return inspection


def agentic_xlsx_candidate_repair_explainer_tool(
    candidate: XlsxLocatorEvidenceCandidateRecord | Mapping[str, Any],
    *,
    axis_inspection: AgenticXlsxAxisInspectionRecord | Mapping[str, Any],
) -> AgenticXlsxRepairExplanationRecord:
    validate_agentic_xlsx_axis_inspector_output("agentic_xlsx", axis_inspection)
    missing_axes = _agentic_xlsx_clean_tuple(
        "agentic_xlsx",
        "xlsx_axis_inspector",
        "missing_axes",
        _agentic_xlsx_record_value(axis_inspection, "missing_axes"),
    )
    missing_query_anchors = tuple(
        _clean(anchor)
        for anchor in _agentic_xlsx_optional_clean_tuple(
            _agentic_xlsx_record_value(candidate, "missing_query_anchors_after_tool")
        )
        if _clean(anchor)
    )
    rejection_reason = _clean(_agentic_xlsx_record_value(candidate, "rejection_reason"))
    if missing_axes and missing_query_anchors:
        primary = "query_anchor_and_axis_missing"
        secondary = ("axis_materialization_gap",)
        safe_to_simulate = False
        recommendation = "repair missing XLSX axes before simulating intent-token removal"
        evidence_summary = "candidate still has missing query anchors and missing validated XLSX axes"
    elif missing_axes or rejection_reason == "missing_validated_required_axes_after_tool":
        primary = "axis_materialization_gap"
        secondary = ()
        safe_to_simulate = False
        recommendation = "materialize missing source-owned XLSX axes before regating"
        evidence_summary = "candidate is blocked by missing validated XLSX axes"
    elif missing_query_anchors or rejection_reason == "missing_query_anchor_after_tool":
        primary = "intent_anchor_only"
        secondary = ()
        safe_to_simulate = True
        recommendation = "simulate only verifier-approved intent-token removal"
        evidence_summary = "candidate has complete validated XLSX axes and only query-anchor residue"
    elif "budget" in rejection_reason:
        primary = "candidate_budget_gap"
        secondary = ()
        safe_to_simulate = False
        recommendation = "inspect candidate budget and source-owned diversification before regating"
        evidence_summary = "candidate selection appears blocked by budget or diversification limits"
    elif rejection_reason in {"source_family_hint_mismatch", "missing_source_identity_doc_id_text_or_locator_axes"}:
        primary = "source_family_or_route_gap"
        secondary = ()
        safe_to_simulate = False
        recommendation = "repair source-family routing or source-owned locator coverage"
        evidence_summary = "candidate lacks the required XLSX route or locator identity"
    else:
        primary = "unknown_fail_closed"
        secondary = ()
        safe_to_simulate = False
        recommendation = "keep diagnostic fail-closed until a source-owned repair path is identified"
        evidence_summary = "candidate rejection family is not specific enough for intent-removal simulation"
    explanation = AgenticXlsxRepairExplanationRecord(
        primary_failure_family=primary,
        secondary_failure_families=secondary,
        safe_to_simulate_intent_removal=safe_to_simulate,
        repair_recommendation=recommendation,
        evidence_summary=evidence_summary,
    )
    validate_agentic_xlsx_repair_explainer_output(
        "agentic_xlsx",
        explanation,
        axis_inspection=axis_inspection,
    )
    return explanation


def agentic_xlsx_regated_candidate_simulator_tool(
    candidate: XlsxLocatorEvidenceCandidateRecord | Mapping[str, Any],
    *,
    approved_removed_tokens: Sequence[str],
    protected_tokens_preserved: Sequence[str],
    axis_inspection: AgenticXlsxAxisInspectionRecord | Mapping[str, Any],
) -> AgenticXlsxRegatedCandidateSimulationRecord:
    validate_agentic_xlsx_axis_inspector_output("agentic_xlsx", axis_inspection)
    approved = _agentic_xlsx_optional_clean_tuple(approved_removed_tokens)
    preserved = _agentic_xlsx_optional_clean_tuple(protected_tokens_preserved)
    missing_axes = list(
        _agentic_xlsx_ordered_axes(
            _agentic_xlsx_record_value(axis_inspection, "missing_axes") or ()
        )
    )
    missing_query_anchors = [
        anchor
        for anchor in _agentic_xlsx_optional_clean_tuple(
            _agentic_xlsx_record_value(candidate, "missing_query_anchors_after_tool")
        )
        if anchor not in set(approved)
    ]
    if missing_query_anchors:
        simulated_rejection_reason = "missing_query_anchor_after_tool"
    elif missing_axes:
        simulated_rejection_reason = "missing_validated_required_axes_after_tool"
    else:
        simulated_rejection_reason = "accepted_after_regating"
    simulation = AgenticXlsxRegatedCandidateSimulationRecord(
        original_rejection_reason=_clean(_agentic_xlsx_record_value(candidate, "rejection_reason"))
        or "accepted_for_regating",
        simulated_rejection_reason=simulated_rejection_reason,
        approved_removed_tokens=approved,
        protected_tokens_preserved=preserved,
        axis_status_after_simulation={
            "missing_axes": missing_axes,
            "remaining_missing_query_anchors": missing_query_anchors,
        },
        would_be_accepted_by_existing_gate=simulated_rejection_reason == "accepted_after_regating",
    )
    validate_agentic_xlsx_regated_candidate_simulator_output("agentic_xlsx", simulation)
    return simulation


def _xlsx_required_axis_materializer_scope(candidate: Mapping[str, Any]) -> dict[str, str]:
    proof: dict[str, str] = {}
    for field in ("doc_id", "sheet", "cell_range", "row_index_1based", "row_label"):
        value = _clean(candidate.get(field))
        if value:
            proof[field] = value
    return proof


def _xlsx_required_axis_materializer_same_row(
    answer_candidate: Mapping[str, Any],
    context: Mapping[str, Any],
) -> bool:
    for field in ("doc_id", "sheet", "cell_range"):
        if _clean(answer_candidate.get(field)) != _clean(context.get(field)):
            return False
    row_index_matches = _clean(answer_candidate.get("row_index_1based")) and (
        _clean(answer_candidate.get("row_index_1based")) == _clean(context.get("row_index_1based"))
    )
    row_label_matches = _clean(answer_candidate.get("row_label")) and (
        _clean(answer_candidate.get("row_label")) == _clean(context.get("row_label"))
    )
    return bool(row_index_matches or row_label_matches)


def _xlsx_required_axis_materializer_period_aliases(context: Mapping[str, Any]) -> list[str]:
    aliases = [
        alias
        for alias in _xlsx_locator_date_aliases(_gate_row_text(context))
        if not alias.endswith("일")
    ]
    return list(dict.fromkeys(aliases))


def _parse_source_owned_xlsx_date_value(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    match = re.match(
        r"^\s*(\d{4})[-./](0?[1-9]|1[0-2])[-./](0?[1-9]|[12]\d|3[01])(?:[T\s].*)?\s*$",
        text,
    )
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _xlsx_materializer_query_periods(query_focus_contract: Mapping[str, Any]) -> list[dict[str, int | str]]:
    axis_values = query_focus_contract.get("validated_axis_values")
    raw_values = []
    if isinstance(axis_values, Mapping):
        raw_values.extend(_as_list(axis_values.get("period")))
    raw_values.extend(_as_list(query_focus_contract.get("period")))
    periods: list[dict[str, int | str]] = []
    seen: set[tuple[int, int, int, str]] = set()

    def add(year: int, month: int = 0, day: int = 0, granularity: str = "year") -> None:
        if year < 1900 or year > 2099:
            return
        if granularity in {"month", "day"} and not (1 <= month <= 12):
            return
        if granularity == "day" and not (1 <= day <= 31):
            return
        key = (year, month, day, granularity)
        if key in seen:
            return
        seen.add(key)
        period: dict[str, int | str] = {"year": year, "granularity": granularity}
        if granularity in {"month", "day"}:
            period["month"] = month
        if granularity == "day":
            period["day"] = day
        periods.append(period)

    for raw in raw_values:
        text = _clean(raw)
        if not text:
            continue
        for match in re.finditer(r"\b(\d{4})[-./](0?[1-9]|1[0-2])[-./](0?[1-9]|[12]\d|3[01])\b", text):
            add(int(match.group(1)), int(match.group(2)), int(match.group(3)), "day")
        for match in re.finditer(r"\b(\d{4})[-./](0?[1-9]|1[0-2])\b", text):
            add(int(match.group(1)), int(match.group(2)), 0, "month")
        for match in re.finditer(r"(\d{4})\s*년\s*(0?[1-9]|1[0-2])\s*월(?:\s*(0?[1-9]|[12]\d|3[01])\s*일)?", text):
            if match.group(3):
                add(int(match.group(1)), int(match.group(2)), int(match.group(3)), "day")
            else:
                add(int(match.group(1)), int(match.group(2)), 0, "month")
        compact = re.fullmatch(r"(\d{4})(0[1-9]|1[0-2])", text)
        if compact:
            add(int(compact.group(1)), int(compact.group(2)), 0, "month")
        year_only = re.fullmatch(r"(\d{4})\s*년?", text)
        if year_only:
            add(int(year_only.group(1)), 0, 0, "year")
    return periods


def _source_period_cell_matches_query_period(
    cell: Mapping[str, Any],
    query_period: Mapping[str, Any],
) -> bool:
    if _clean(cell.get("provenance_policy")) != "source_owned_same_row_period_cell_v1":
        return False
    try:
        year = int(cell.get("year"))
        month = int(cell.get("month"))
        day = int(cell.get("day") or 0)
        query_year = int(query_period.get("year"))
    except (TypeError, ValueError):
        return False
    granularity = _clean(query_period.get("granularity"))
    if granularity == "year":
        return year == query_year
    try:
        query_month = int(query_period.get("month"))
    except (TypeError, ValueError):
        return False
    if granularity == "month":
        return year == query_year and month == query_month
    if granularity == "day":
        try:
            query_day = int(query_period.get("day"))
        except (TypeError, ValueError):
            return False
        return year == query_year and month == query_month and day == query_day
    return False


def _xlsx_materializer_json_list(value: Any) -> list[Any]:
    parsed = _parse_jsonish(value)
    return parsed if isinstance(parsed, list) else []


SAME_ROW_PERIOD_CELL_PACKET_FIELDS = frozenset(
    {
        "schema_version",
        "provenance_policy",
        "source_atom_id",
        "doc_id",
        "sheet",
        "cell_range",
        "cell",
        "row_index_1based",
        "row_label",
        "column_label",
        "raw_value",
        "parsed_date",
        "year",
        "month",
        "day",
    }
)


def _xlsx_same_row_period_cell_forbidden_scalar(value: Any) -> bool:
    text = _clean(value)
    if not text:
        return False
    return bool(
        _xlsx_locator_forbidden_text_fields(text)
        or re.search(r"(?:[A-Za-z]:[\\/]|\\\\|/home/|/Users/)", text)
    )


def _sanitize_same_row_period_cell_packet(cell: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(cell, Mapping):
        return None
    keys = {str(key) for key in cell if _clean(key)}
    if keys != SAME_ROW_PERIOD_CELL_PACKET_FIELDS:
        return None
    if _clean(cell.get("schema_version")) != "actual_rag_eval.xlsx.same_row_period_cell.v1":
        return None
    if _clean(cell.get("provenance_policy")) != "source_owned_same_row_period_cell_v1":
        return None
    parsed = _parse_source_owned_xlsx_date_value(cell.get("parsed_date") or cell.get("raw_value"))
    if parsed is None:
        return None
    try:
        year = int(cell.get("year"))
        month = int(cell.get("month"))
        day = int(cell.get("day"))
    except (TypeError, ValueError):
        return None
    if (year, month, day) != (parsed.year, parsed.month, parsed.day):
        return None
    sanitized = {
        "schema_version": "actual_rag_eval.xlsx.same_row_period_cell.v1",
        "provenance_policy": "source_owned_same_row_period_cell_v1",
        "source_atom_id": _clean(cell.get("source_atom_id")),
        "doc_id": _clean(cell.get("doc_id")),
        "sheet": _clean(cell.get("sheet")),
        "cell_range": _clean(cell.get("cell_range")),
        "cell": _clean(cell.get("cell")).upper(),
        "row_index_1based": _clean(cell.get("row_index_1based")),
        "row_label": _clean(cell.get("row_label")),
        "column_label": _clean(cell.get("column_label")),
        "raw_value": _clean(cell.get("raw_value")),
        "parsed_date": parsed.date().isoformat(),
        "year": year,
        "month": month,
        "day": day,
    }
    required = (
        "source_atom_id",
        "doc_id",
        "sheet",
        "cell_range",
        "cell",
        "row_index_1based",
        "column_label",
        "raw_value",
    )
    if any(not sanitized[field] for field in required):
        return None
    for value in sanitized.values():
        if isinstance(value, str) and _xlsx_same_row_period_cell_forbidden_scalar(value):
            return None
    return sanitized


def _xlsx_period_cell_scope_matches_candidate(
    candidate: Mapping[str, Any],
    packet: Mapping[str, Any],
) -> bool:
    for field in ("doc_id", "sheet", "cell_range"):
        candidate_value = _clean(candidate.get(field))
        packet_value = _clean(packet.get(field))
        if not candidate_value or not packet_value or candidate_value != packet_value:
            return False
    candidate_row = _clean(candidate.get("row_index_1based"))
    packet_row = _clean(packet.get("row_index_1based"))
    if candidate_row and packet_row and candidate_row == packet_row:
        return True
    candidate_label = _clean(candidate.get("row_label"))
    packet_label = _clean(packet.get("row_label"))
    return bool(candidate_label and packet_label and candidate_label == packet_label)


def _xlsx_same_row_period_cell_packets(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    metadata = context.get("metadata") if isinstance(context.get("metadata"), Mapping) else {}
    for source in (context, metadata):
        for field in ("same_row_period_cells_json", "same_row_period_cells"):
            for item in _xlsx_materializer_json_list(source.get(field)):
                if not isinstance(item, Mapping):
                    continue
                packet = _sanitize_same_row_period_cell_packet(item)
                if packet is None:
                    continue
                key = (packet["source_atom_id"], packet["cell"], packet["raw_value"])
                if key in seen:
                    continue
                packets.append(packet)
                seen.add(key)
    return packets


def _xlsx_required_axis_materializer_period_cell_same_row(
    answer_candidate: Mapping[str, Any],
    context: Mapping[str, Any],
    cell: Mapping[str, Any],
) -> bool:
    for field in ("doc_id", "sheet", "cell_range"):
        answer_value = _clean(answer_candidate.get(field))
        context_value = _clean(context.get(field) or cell.get(field))
        if answer_value != context_value:
            return False
    answer_row = _clean(answer_candidate.get("row_index_1based"))
    cell_row = _clean(context.get("row_index_1based") or cell.get("row_index_1based"))
    if answer_row and cell_row and answer_row == cell_row:
        return True
    answer_label = _clean(answer_candidate.get("row_label"))
    cell_label = _clean(context.get("row_label") or cell.get("row_label"))
    return bool(answer_label and cell_label and answer_label == cell_label)


def _xlsx_period_cells_match_query(
    *,
    answer_candidate: Mapping[str, Any],
    context: Mapping[str, Any],
    query_periods: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], Mapping[str, Any] | None]:
    matched_cells: list[dict[str, Any]] = []
    matched_query_period: Mapping[str, Any] | None = None
    for packet in _xlsx_same_row_period_cell_packets(context):
        if not _xlsx_required_axis_materializer_period_cell_same_row(answer_candidate, context, packet):
            continue
        for query_period in query_periods:
            if _source_period_cell_matches_query_period(packet, query_period):
                matched_cells.append(packet)
                matched_query_period = query_period
                break
    return matched_cells, matched_query_period


def validate_agentic_xlsx_required_axis_materializer_output(
    run_id: str,
    materializer: AgenticXlsxRequiredAxisMaterializerRecord | Mapping[str, Any],
) -> None:
    tool_name = "xlsx_required_axis_materializer_tool"
    if not isinstance(materializer, (AgenticXlsxRequiredAxisMaterializerRecord, Mapping)):
        raise DatasetSchemaError(f"{run_id}: {tool_name} must be a materializer record")
    if _agentic_xlsx_record_value(materializer, "schema_version") != AGENTIC_XLSX_REQUIRED_AXIS_MATERIALIZER_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.schema_version unsupported")
    if _agentic_xlsx_record_value(materializer, "tool_name") != tool_name:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.tool_name unsupported")
    if _agentic_xlsx_record_value(materializer, "report_only_diagnostic") is not True:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.report_only_diagnostic must be True")
    if _agentic_xlsx_record_value(materializer, "official_metric") is not False:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.official_metric must be False")
    if _agentic_xlsx_record_value(materializer, "accepted_for_regating") is not False:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.accepted_for_regating must be False")
    axes = _agentic_xlsx_clean_tuple(
        run_id,
        tool_name,
        "materialized_axes",
        _agentic_xlsx_record_value(materializer, "materialized_axes"),
    )
    axis_packages = _agentic_xlsx_record_value(materializer, "axis_packages")
    scope_proof = _agentic_xlsx_record_value(materializer, "scope_proof")
    if not isinstance(axis_packages, Mapping) or not isinstance(scope_proof, Mapping):
        raise DatasetSchemaError(f"{run_id}: {tool_name}.axis_packages and scope_proof must be present")
    forbidden = sorted(_collect_xlsx_locator_forbidden_input_fields(axis_packages))
    if forbidden:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.axis_packages contains forbidden field {forbidden[0]}")
    for axis in axes:
        package = axis_packages.get(axis)
        if not isinstance(package, Mapping):
            raise DatasetSchemaError(f"{run_id}: {tool_name}.axis_packages.{axis} missing package")
        provenance_policy = _clean(package.get("provenance_policy"))
        period_cells = _as_list(package.get("period_cells"))
        if period_cells:
            if provenance_policy != "source_owned_same_row_period_cell_v1":
                raise DatasetSchemaError(f"{run_id}: {tool_name}.axis_packages.{axis}.provenance_policy unsupported")
            for cell in period_cells:
                if not isinstance(cell, Mapping) or _sanitize_same_row_period_cell_packet(cell) is None:
                    raise DatasetSchemaError(f"{run_id}: {tool_name}.axis_packages.{axis}.period_cells invalid")
            continue
        raise DatasetSchemaError(f"{run_id}: {tool_name}.axis_packages.{axis} missing period_cells")
    if axes:
        for field in ("doc_id", "sheet", "cell_range"):
            if not _clean(scope_proof.get(field)):
                raise DatasetSchemaError(f"{run_id}: {tool_name}.scope_proof.{field} required")


def xlsx_required_axis_materializer_tool(
    *,
    answer_candidate: Mapping[str, Any],
    query_focus_contract: Mapping[str, Any],
    source_owned_contexts: Sequence[Mapping[str, Any]],
) -> AgenticXlsxRequiredAxisMaterializerRecord:
    missing_axes = set(_agentic_xlsx_optional_clean_tuple(answer_candidate.get("missing_validated_required_axes")))
    required_axes = set(_agentic_xlsx_optional_clean_tuple(query_focus_contract.get("validated_required_axes")))
    if "period" not in missing_axes or "period" not in required_axes:
        materializer = AgenticXlsxRequiredAxisMaterializerRecord()
        validate_agentic_xlsx_required_axis_materializer_output("agentic_xlsx", materializer)
        return materializer
    rejected_count = 0
    query_periods = _xlsx_materializer_query_periods(query_focus_contract)
    materialized_period_cells: list[dict[str, Any]] | None = None
    materialized_query_period: Mapping[str, Any] | None = None
    for context in source_owned_contexts:
        if not isinstance(context, Mapping):
            rejected_count += 1
            continue
        if _collect_xlsx_locator_forbidden_input_fields(context):
            rejected_count += 1
            continue
        period_cells, query_period = _xlsx_period_cells_match_query(
            answer_candidate=answer_candidate,
            context=context,
            query_periods=query_periods,
        )
        if not period_cells:
            rejected_count += 1
            continue
        if materialized_period_cells is None:
            materialized_period_cells = period_cells
            materialized_query_period = query_period
    if materialized_period_cells is not None:
        materializer = AgenticXlsxRequiredAxisMaterializerRecord(
            materialized_axes=("period",),
            axis_packages={
                "period": {
                    "period_cells": materialized_period_cells,
                    "query_period": dict(materialized_query_period or {}),
                    "provenance_policy": "source_owned_same_row_period_cell_v1",
                }
            },
            scope_proof=_xlsx_required_axis_materializer_scope(answer_candidate),
            rejected_context_count=rejected_count,
        )
        validate_agentic_xlsx_required_axis_materializer_output("agentic_xlsx", materializer)
        return materializer
    materializer = AgenticXlsxRequiredAxisMaterializerRecord(rejected_context_count=rejected_count)
    validate_agentic_xlsx_required_axis_materializer_output("agentic_xlsx", materializer)
    return materializer


def _xlsx_locator_apply_required_axis_materializer_actions(
    *,
    row: Mapping[str, Any],
    candidates: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    if any(candidate.get("accepted_for_regating") is True for candidate in candidates):
        return list(candidates)
    query_focus_contract = _query_evidence_planner_for_row(row)
    if not query_focus_contract:
        return list(candidates)
    raw_source_contexts = _as_list(row.get(INTERNAL_XLSX_LOCATOR_SOURCE_CONTEXTS_KEY)) or _as_list(
        row.get("retrieved_contexts")
    )
    source_contexts = [context for context in raw_source_contexts if isinstance(context, Mapping)]
    for candidate in candidates:
        if "period" not in _as_list(candidate.get("missing_validated_required_axes")):
            continue
        materializer = xlsx_required_axis_materializer_tool(
            answer_candidate=candidate,
            query_focus_contract=query_focus_contract,
            source_owned_contexts=source_contexts,
        )
        candidate.update(
            {
                "xlsx_required_axis_materializer_tool_output": True,
                "xlsx_required_axis_materializer_tool_name": materializer.tool_name,
                "xlsx_required_axis_materializer_report_only_diagnostic": materializer.report_only_diagnostic,
                "xlsx_required_axis_materializer_official_metric": materializer.official_metric,
                "xlsx_required_axis_materializer_accepted_for_regating": materializer.accepted_for_regating,
                "xlsx_required_axis_materializer_materialized_axes": list(materializer.materialized_axes),
                "xlsx_required_axis_materializer_rejected_context_count": materializer.rejected_context_count,
            }
        )
        candidate["input_fields_used"] = tuple(
            dict.fromkeys([*_as_list(candidate.get("input_fields_used")), "xlsx_required_axis_materializer_tool"])
        )
        if "period" not in materializer.materialized_axes:
            candidate["xlsx_required_axis_materializer_execution_status"] = (
                "rejected_no_source_owned_same_row_period_cell"
            )
            continue
        period_package = materializer.axis_packages.get("period")
        period_cells = _as_list(period_package.get("period_cells")) if isinstance(period_package, Mapping) else []
        period_cells = [
            packet
            for packet in (_sanitize_same_row_period_cell_packet(cell) for cell in period_cells if isinstance(cell, Mapping))
            if packet is not None
        ]
        if not period_cells:
            candidate["xlsx_required_axis_materializer_execution_status"] = (
                "rejected_invalid_source_owned_period_cell_packet"
            )
            continue
        candidate.update(
            {
                "same_row_period_cells": period_cells,
                "same_row_period_cells_json": json.dumps(period_cells, ensure_ascii=False, sort_keys=True),
                "source_owned_same_candidate_package": True,
                "source_owned_same_candidate_package_policy": "source_owned_same_row_period_cell_v1",
                "xlsx_required_axis_materializer_execution_status": "materialized_axis_package",
            }
        )
        candidate["input_fields_used"] = tuple(
            dict.fromkeys(
                [
                    *_as_list(candidate.get("input_fields_used")),
                    "same_row_period_cells_json",
                    "xlsx_required_axis_materializer_tool",
                ]
            )
        )
    return list(candidates)


def _agentic_xlsx_regated_simulation_summary(
    record: XlsxLocatorRunRecord,
) -> dict[str, Any]:
    approved_removed_tokens = tuple(
        _clean(token)
        for token in _as_list(dict(record.required_anchor_summary).get("removed_intent_tokens"))
        if _clean(token)
    )
    protected_tokens_preserved = tuple(
        _clean(token)
        for token in _as_list(dict(record.required_anchor_summary).get("protected_intent_tokens_restored"))
        if _clean(token)
    )
    simulations: list[dict[str, Any]] = []
    simulated_rejection_counts: Counter[str] = Counter()
    for candidate in record.candidates:
        if candidate.accepted_for_regating or candidate.rejection_reason != "missing_query_anchor_after_tool":
            continue
        axis_inspection = agentic_xlsx_axis_inspector_tool(candidate)
        simulation = agentic_xlsx_regated_candidate_simulator_tool(
            candidate,
            approved_removed_tokens=approved_removed_tokens,
            protected_tokens_preserved=protected_tokens_preserved,
            axis_inspection=axis_inspection,
        )
        simulated_rejection_counts[simulation.simulated_rejection_reason] += 1
        simulations.append(
            {
                "item_index": candidate.item_index,
                "candidate_index": candidate.candidate_index,
                "original_rejection_reason": simulation.original_rejection_reason,
                "simulated_rejection_reason": simulation.simulated_rejection_reason,
                "approved_removed_tokens": list(simulation.approved_removed_tokens),
                "protected_tokens_preserved": list(simulation.protected_tokens_preserved),
                "axis_status_after_simulation": dict(simulation.axis_status_after_simulation),
                "would_be_accepted_by_existing_gate": simulation.would_be_accepted_by_existing_gate,
            }
        )
    summary = {
        "schema_version": AGENTIC_XLSX_REGATED_CANDIDATE_SIMULATOR_SCHEMA_VERSION,
        "report_only_diagnostic": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "approved_removed_tokens": list(approved_removed_tokens),
        "protected_tokens_preserved": list(protected_tokens_preserved),
        "simulated_candidate_count": len(simulations),
        "would_be_accepted_by_existing_gate_candidate_count": sum(
            1 for simulation in simulations if simulation["would_be_accepted_by_existing_gate"] is True
        ),
        "query_anchor_to_axis_materialization_candidate_count": sum(
            1
            for simulation in simulations
            if simulation["original_rejection_reason"] == "missing_query_anchor_after_tool"
            and simulation["simulated_rejection_reason"] == "missing_validated_required_axes_after_tool"
        ),
        "query_anchor_to_accepted_candidate_count": sum(
            1
            for simulation in simulations
            if simulation["original_rejection_reason"] == "missing_query_anchor_after_tool"
            and simulation["simulated_rejection_reason"] == "accepted_after_regating"
        ),
        "simulated_rejection_reason_counts": dict(sorted(simulated_rejection_counts.items())),
        "quality_delta_claim_supported": False,
        "simulations": simulations,
    }
    validate_agentic_xlsx_regated_simulation_summary("agentic_xlsx", summary)
    return summary


def _agentic_xlsx_axis_repair_diagnostic(record: XlsxLocatorRunRecord) -> dict[str, Any]:
    inspected: list[tuple[XlsxLocatorEvidenceCandidateRecord, AgenticXlsxAxisInspectionRecord]] = [
        (candidate, agentic_xlsx_axis_inspector_tool(candidate))
        for candidate in record.candidates
    ]
    primary_counts: Counter[str] = Counter()
    secondary_counts: Counter[str] = Counter()
    missing_axis_counts: Counter[str] = Counter()
    candidate_summaries: list[dict[str, Any]] = []
    safe_to_simulate_count = 0
    for candidate, inspection in inspected:
        missing_axes = list(inspection.missing_axes)
        missing_axis_counts.update(missing_axes)
        if candidate.accepted_for_regating:
            continue
        explanation = agentic_xlsx_candidate_repair_explainer_tool(
            candidate,
            axis_inspection=inspection,
        )
        primary_counts[explanation.primary_failure_family] += 1
        secondary_counts.update(explanation.secondary_failure_families)
        if explanation.safe_to_simulate_intent_removal:
            safe_to_simulate_count += 1
        candidate_summaries.append(
            {
                "item_index": candidate.item_index,
                "candidate_index": candidate.candidate_index,
                "rejection_reason": candidate.rejection_reason or "accepted_for_regating",
                "primary_failure_family": explanation.primary_failure_family,
                "secondary_failure_families": list(explanation.secondary_failure_families),
                "missing_axes": missing_axes,
                "safe_to_simulate_intent_removal": explanation.safe_to_simulate_intent_removal,
            }
        )
    diagnostic = {
        "schema_version": AGENTIC_XLSX_AXIS_REPAIR_DIAGNOSTIC_SCHEMA_VERSION,
        "axis_inspector_schema_version": AGENTIC_XLSX_AXIS_INSPECTOR_SCHEMA_VERSION,
        "repair_explainer_schema_version": AGENTIC_XLSX_REPAIR_EXPLAINER_SCHEMA_VERSION,
        "report_only_diagnostic": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "candidate_count": len(record.candidates),
        "inspected_candidate_count": len(inspected),
        "repair_explained_candidate_count": len(candidate_summaries),
        "missing_axis_candidate_count": sum(1 for _candidate, inspection in inspected if inspection.missing_axes),
        "safe_to_simulate_intent_removal_candidate_count": safe_to_simulate_count,
        "primary_failure_family_counts": dict(sorted(primary_counts.items())),
        "secondary_failure_family_counts": dict(sorted(secondary_counts.items())),
        "missing_axis_counts": dict(sorted(missing_axis_counts.items())),
        "candidate_summaries": candidate_summaries,
        "regated_simulation_summary": _agentic_xlsx_regated_simulation_summary(record),
        "uses_expected_fields": False,
        "uses_gold_fields": False,
        "uses_qrels_or_labels": False,
        "uses_ids_as_runtime_inputs": False,
        "uses_file_workbook_title": False,
        "uses_formula_or_normalized_value": False,
        "evidence_gate_loosened": record.guardrail_record.evidence_gate_loosened,
    }
    validate_agentic_xlsx_axis_repair_diagnostic("agentic_xlsx", diagnostic)
    return diagnostic


XLSX_LOCATOR_QUERY_ANCHOR_DIAGNOSTIC_FORBIDDEN_KEYS = frozenset(
    {
        *XLSX_PDF_RESIDUAL_FORBIDDEN_SHORTCUT_FIELDS,
        "candidate_id",
        "chunk_id",
        "doc_id",
        "document_id",
        "evidence_bundle_id",
        "file_name",
        "file_path",
        "filename",
        "gold_locator",
        "item_id",
        "path",
        "prompt_payload",
        "raw_payload",
        "raw_prompt",
        "raw_prompt_payload",
        "raw_response",
        "raw_response_payload",
        "raw_tool_payload",
        "response_payload",
        "source_atom_id",
        "source_file_name",
        "source_id",
        "source_path",
        "source_title",
        "source_workbook",
        "source_workbook_title",
        "supporting_evidence",
        "title",
        "tool_payload",
        "workbook",
        "workbook_id",
        "workbook_name",
        "workbook_title",
        "workbook_version_id",
    }
)
XLSX_LOCATOR_QUERY_ANCHOR_DIAGNOSTIC_REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "report_only_diagnostic",
        "official_metric",
        "official_metric_input_rows",
        "tool_invocation_count",
        "candidate_count",
        "accepted_for_regating_candidate_count",
        "rejected_candidate_count",
        "missing_query_anchor_after_tool_candidate_count",
        "missing_query_anchor_after_tool_item_count",
        "query_anchor_rejected_with_complete_axes_candidate_count",
        "query_anchor_rejected_with_missing_axes_candidate_count",
        "query_anchor_rejected_without_validated_axes_candidate_count",
        "source_family_hint_counts",
        "query_task_counts",
        "gate_flip_direction_counts",
        "residual_transition_counts",
        "missing_query_anchor_after_tool_by_source_family_hint_query_task",
        "top_missing_query_anchors",
        "source_owned_field_presence_on_query_anchor_rejected_candidates",
        "item_summaries",
        "uses_expected_fields",
        "uses_gold_fields",
        "uses_qrels_or_labels",
        "uses_ids_as_runtime_inputs",
        "uses_file_workbook_title",
        "uses_formula_or_normalized_value",
        "evidence_gate_loosened",
    }
)


def _collect_xlsx_locator_query_anchor_diagnostic_forbidden_keys(value: Any) -> set[str]:
    seen: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = _canonical_xlsx_locator_field_name(key)
            if key_text in XLSX_LOCATOR_QUERY_ANCHOR_DIAGNOSTIC_FORBIDDEN_KEYS:
                seen.add(key_text)
            if isinstance(nested, (Mapping, list, tuple)):
                seen.update(_collect_xlsx_locator_query_anchor_diagnostic_forbidden_keys(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            if isinstance(nested, (Mapping, list, tuple)):
                seen.update(_collect_xlsx_locator_query_anchor_diagnostic_forbidden_keys(nested))
    return seen


def _required_non_negative_int(run_id: str, owner: str, mapping: Mapping[str, Any], key: str) -> int:
    if key not in mapping:
        raise DatasetSchemaError(f"{run_id}: {owner}.{key} must be present")
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise DatasetSchemaError(f"{run_id}: {owner}.{key} must be an integer")
    if value < 0:
        raise DatasetSchemaError(f"{run_id}: {owner}.{key} must be non-negative")
    return value


def validate_pdf_source_native_decomposition(run_id: str, decomposition: Mapping[str, Any]) -> None:
    owner = "pdf_source_native_decomposition"
    if decomposition.get("schema_version") != PDF_SOURCE_NATIVE_DECOMPOSITION_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: {owner}.schema_version unsupported")
    if decomposition.get("report_only_diagnostic") is not True:
        raise DatasetSchemaError(f"{run_id}: {owner}.report_only_diagnostic must be True")
    if decomposition.get("official_metric") is not False:
        raise DatasetSchemaError(f"{run_id}: {owner}.official_metric must be False")
    if _required_non_negative_int(run_id, owner, decomposition, "official_metric_input_rows") != 0:
        raise DatasetSchemaError(f"{run_id}: {owner}.official_metric_input_rows must be 0")
    for key in (
        "uses_expected_fields",
        "uses_gold_fields",
        "uses_qrels",
        "uses_labels",
        "uses_ids",
        "uses_raw_xlsx_or_pdf_query_time_parsing",
    ):
        if decomposition.get(key) is not False:
            raise DatasetSchemaError(f"{run_id}: {owner}.{key} must be False")
    counts = {
        key: _required_non_negative_int(run_id, owner, decomposition, key)
        for key in (
            "pdf_query_count",
            "page_present_count",
            "bbox_present_count",
            "page_bbox_co_located_count",
            "section_or_table_axis_present_count",
            "ocr_confidence_present_count",
            "lower_trust_due_to_ocr_count",
        )
    }
    pdf_query_count = counts["pdf_query_count"]
    for key in (
        "page_present_count",
        "bbox_present_count",
        "section_or_table_axis_present_count",
        "ocr_confidence_present_count",
    ):
        if counts[key] > pdf_query_count:
            raise DatasetSchemaError(f"{run_id}: {owner}.{key} exceeds pdf_query_count")
    if counts["page_bbox_co_located_count"] > min(counts["page_present_count"], counts["bbox_present_count"]):
        raise DatasetSchemaError(f"{run_id}: {owner}.page_bbox_co_located_count exceeds page/bbox counts")
    if counts["lower_trust_due_to_ocr_count"] > counts["ocr_confidence_present_count"]:
        raise DatasetSchemaError(f"{run_id}: {owner}.lower_trust_due_to_ocr_count exceeds ocr confidence count")


def _xlsx_locator_candidate_budget_diagnostic(record: XlsxLocatorRunRecord) -> dict[str, Any]:
    rejected_by_reason = Counter(
        candidate.rejection_reason
        for candidate in record.candidates
        if not candidate.accepted_for_regating and candidate.rejection_reason
    )
    zero_candidate_row_count = sum(1 for tool_use in record.tool_uses if tool_use.candidate_count == 0)
    at_budget_row_count = sum(
        1
        for tool_use in record.tool_uses
        if tool_use.candidate_count >= XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET
    )
    candidate_budget_exhaustion_count = sum(
        1
        for tool_use in record.tool_uses
        if tool_use.candidate_pool_count_before_budget > XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET
    )
    source_row_context_doc_identity_mismatch_candidate_count = sum(
        int(tool_use.source_row_context_doc_identity_mismatch_candidate_count)
        for tool_use in record.tool_uses
    )
    return {
        "schema_version": "actual_rag_eval.xlsx_locator_candidate_budget_diagnostic.v1",
        "report_only_diagnostic": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "candidate_budget_per_query": XLSX_LOCATOR_TOOL_CANDIDATE_BUDGET,
        "zero_candidate_row_count": zero_candidate_row_count,
        "candidate_budget_exhaustion_count": candidate_budget_exhaustion_count,
        "at_budget_row_count": at_budget_row_count,
        "accepted_for_regating_count": record.accepted_candidate_count,
        "same_sheet_candidate_count": sum(1 for candidate in record.candidates if _clean(candidate.sheet)),
        "same_table_candidate_count": sum(
            1 for candidate in record.candidates if _clean(candidate.table_id) or _clean(candidate.synthetic_table_id)
        ),
        "same_range_candidate_count": sum(1 for candidate in record.candidates if _clean(candidate.cell_range)),
        "deduped_candidate_count": len(record.candidates),
        "rejected_candidate_count_by_reason": dict(sorted(rejected_by_reason.items())),
        "source_row_context_candidate_count": sum(
            int(tool_use.source_row_context_candidate_count)
            for tool_use in record.tool_uses
        ),
        "source_row_context_doc_identity_mismatch_candidate_count": (
            source_row_context_doc_identity_mismatch_candidate_count
        ),
        "source_row_context_doc_identity_mismatch_row_count": sum(
            1
            for tool_use in record.tool_uses
            if tool_use.source_row_context_blocked_by_doc_identity_mismatch
        ),
        "source_row_context_fail_closed_policy": XLSX_LOCATOR_SOURCE_ROW_CONTEXT_FAIL_CLOSED_POLICY,
        "source_owned_candidate_diversification_policy": XLSX_LOCATOR_SOURCE_OWNED_DIVERSIFICATION_POLICY,
        "candidate_cap_and_dedupe_policy": "fixed_budget_after_source_identity_and_text_hash_dedupe",
        "uses_raw_workbook": False,
        "uses_formula": False,
        "uses_normalized_value": False,
        "uses_expected_fields": False,
        "uses_qrels_or_labels": False,
        "uses_ids": False,
        "uses_filename_or_workbook_title": False,
    }


def _xlsx_required_axis_materializer_runtime_diagnostic(record: XlsxLocatorRunRecord) -> dict[str, Any]:
    candidates = [c for c in record.candidates if c.xlsx_required_axis_materializer_tool_output]
    status_counts = Counter(c.xlsx_required_axis_materializer_execution_status or "unknown" for c in candidates)
    axes_counts = Counter(axis for c in candidates for axis in c.xlsx_required_axis_materializer_materialized_axes)
    policy_counts = Counter(
        c.source_owned_same_candidate_package_policy or "unknown"
        for c in candidates
        if c.source_owned_same_candidate_package and c.xlsx_required_axis_materializer_materialized_axes
    )
    period_cell_policy_counts = Counter(
        _clean(cell.get("provenance_policy")) or "unknown"
        for candidate in candidates
        for cell in candidate.same_row_period_cells
    )
    return {
        "schema_version": "actual_rag_eval.xlsx_required_axis_materializer_runtime.v1",
        "tool_name": "xlsx_required_axis_materializer_tool",
        "report_only_diagnostic": True,
        "official_metric": False,
        "action_count": len(candidates),
        "materialized_action_count": sum(int(bool(c.xlsx_required_axis_materializer_materialized_axes)) for c in candidates),
        "materializer_accepted_candidate_count": sum(
            int(c.xlsx_required_axis_materializer_accepted_for_regating) for c in candidates
        ),
        "locator_accepted_after_materialization_count": sum(int(c.accepted_for_regating) for c in candidates),
        "rejected_context_count": sum(c.xlsx_required_axis_materializer_rejected_context_count for c in candidates),
        "execution_status_counts": dict(sorted(status_counts.items())),
        "materialized_axes_counts": dict(sorted(axes_counts.items())),
        "source_owned_same_candidate_package_policy_counts": dict(sorted(policy_counts.items())),
        "period_cell_packet_count": sum(len(c.same_row_period_cells) for c in candidates),
        "period_cell_packet_policy_counts": dict(sorted(period_cell_policy_counts.items())),
    }


def project_xlsx_locator_run_record(
    record: XlsxLocatorRunRecord,
    *,
    run_store_path: Path | str | None = None,
) -> dict[str, Any]:
    guardrails = asdict(record.guardrail_record)
    tool_status_counts = Counter(tool_use.execution_status for tool_use in record.tool_uses)
    candidate_confidence_counts = Counter(candidate.confidence_tier for candidate in record.candidates)
    candidate_rejection_counts = Counter(
        candidate.rejection_reason or "accepted_for_regating"
        for candidate in record.candidates
    )
    candidate_source_family_counts = Counter(candidate.source_family for candidate in record.candidates)
    complete_validated_axis_candidate_count = sum(
        int(tool_use.complete_validated_axis_candidate_count)
        for tool_use in record.tool_uses
    )
    validated_axis_split_row_count = sum(
        1 for tool_use in record.tool_uses if tool_use.validated_axis_split_across_candidates
    )
    candidate_budget_diagnostic = _xlsx_locator_candidate_budget_diagnostic(record)
    query_anchor_tool_acceptance_diagnostic = _xlsx_locator_query_anchor_tool_acceptance_diagnostic(record)
    axis_repair_diagnostic = _agentic_xlsx_axis_repair_diagnostic(record)
    materializer_runtime_diagnostic = _xlsx_required_axis_materializer_runtime_diagnostic(record)
    projection = {
        "schema_version": record.schema_version,
        "enabled": record.enabled,
        "report_only_diagnostic": record.report_only_diagnostic,
        "official_metric": record.official_metric,
        "official_metric_input_rows": record.guardrail_record.official_metric_input_rows,
        "official_metric_input_rows_created": record.guardrail_record.official_metric_input_rows_created,
        "official_metric_input_rows_consumed": record.guardrail_record.official_metric_input_rows_consumed,
        "tool_name": record.tool_name,
        "eligible_failed_row_count": record.eligible_failed_row_count,
        "tool_invocation_count": record.tool_invocation_count,
        "accepted_candidate_count": record.accepted_candidate_count,
        "rejected_candidate_count": record.rejected_candidate_count,
        "complete_validated_axis_candidate_count": complete_validated_axis_candidate_count,
        "validated_axis_split_row_count": validated_axis_split_row_count,
        "anchor_classifier_model": record.anchor_classifier_model,
        "anchor_classifier_prompt_version": record.anchor_classifier_prompt_version,
        "anchor_classifier_raw_payload_written": record.anchor_classifier_raw_payload_written,
        "required_anchor_summary": dict(record.required_anchor_summary),
        "query_planner_summary": dict(record.query_planner_summary),
        "tool_execution_status_counts": dict(sorted(tool_status_counts.items())),
        "candidate_confidence_tier_counts": dict(sorted(candidate_confidence_counts.items())),
        "candidate_rejection_reason_counts": dict(sorted(candidate_rejection_counts.items())),
        "candidate_source_family_counts": dict(sorted(candidate_source_family_counts.items())),
        "candidate_budget_diagnostic": candidate_budget_diagnostic,
        "query_anchor_tool_acceptance_diagnostic": query_anchor_tool_acceptance_diagnostic,
        "agentic_xlsx_axis_repair_diagnostic": axis_repair_diagnostic,
        "xlsx_required_axis_materializer_runtime_diagnostic": materializer_runtime_diagnostic,
        "zero_candidate_row_count": candidate_budget_diagnostic["zero_candidate_row_count"],
        "candidate_budget_exhaustion_count": candidate_budget_diagnostic["candidate_budget_exhaustion_count"],
        "at_budget_row_count": candidate_budget_diagnostic["at_budget_row_count"],
        "candidate_budget_per_query": candidate_budget_diagnostic["candidate_budget_per_query"],
        "accepted_for_regating_count": candidate_budget_diagnostic["accepted_for_regating_count"],
        "source_row_context_candidate_count": candidate_budget_diagnostic["source_row_context_candidate_count"],
        "source_row_context_doc_identity_mismatch_candidate_count": candidate_budget_diagnostic[
            "source_row_context_doc_identity_mismatch_candidate_count"
        ],
        "source_row_context_doc_identity_mismatch_row_count": candidate_budget_diagnostic[
            "source_row_context_doc_identity_mismatch_row_count"
        ],
        "source_row_context_fail_closed_policy": candidate_budget_diagnostic["source_row_context_fail_closed_policy"],
        "same_sheet_candidate_count": candidate_budget_diagnostic["same_sheet_candidate_count"],
        "same_table_candidate_count": candidate_budget_diagnostic["same_table_candidate_count"],
        "same_range_candidate_count": candidate_budget_diagnostic["same_range_candidate_count"],
        "deduped_candidate_count": candidate_budget_diagnostic["deduped_candidate_count"],
        "rejected_candidate_count_by_reason": candidate_budget_diagnostic["rejected_candidate_count_by_reason"],
        "before_gate": dict(record.gate_delta_record.before_gate),
        "after_gate": dict(record.gate_delta_record.after_gate),
        "gate_delta": dict(record.gate_delta_record.gate_delta),
        "residual_before": dict(record.gate_delta_record.residual_before),
        "residual_after": dict(record.gate_delta_record.residual_after),
        "guardrail_status": {
            "raw_xlsx_query_time_parsing_used": record.guardrail_record.raw_xlsx_query_time_parsing_used,
            "gold_or_qrels_or_label_or_expected_used": record.guardrail_record.gold_or_qrels_or_label_or_expected_used,
            "retrieved_context_only_citation_promoted": record.guardrail_record.retrieved_context_only_citation_promoted,
            "evidence_gate_loosened": record.guardrail_record.evidence_gate_loosened,
            "report_only_diagnostic": record.guardrail_record.report_only_diagnostic,
            "official_metric": record.guardrail_record.official_metric,
            "official_metric_input_rows": record.guardrail_record.official_metric_input_rows,
            "official_metric_input_rows_created": record.guardrail_record.official_metric_input_rows_created,
            "official_metric_input_rows_consumed": record.guardrail_record.official_metric_input_rows_consumed,
        },
        "forbidden_input_fields_seen": list(record.guardrail_record.forbidden_input_fields_seen),
        "forbidden_input_fields_used": list(record.guardrail_record.forbidden_input_fields_used),
        "forbidden_input_fields_rejected": list(record.guardrail_record.forbidden_input_fields_rejected),
        "raw_xlsx_query_time_parsing_used": record.guardrail_record.raw_xlsx_query_time_parsing_used,
        "gold_or_qrels_or_label_or_expected_used": record.guardrail_record.gold_or_qrels_or_label_or_expected_used,
        "run_record": {
            "record_type": "XlsxLocatorRunRecord",
            "contract": "typed_record_projection_v1",
            "serializer": "compact_report_projection",
        },
        "guardrails": guardrails,
    }
    if run_store_path is not None:
        projection["run_store"] = {
            "backend": XLSX_LOCATOR_RUN_STORE_BACKEND,
            "path": _report_path_value(run_store_path),
            "tables": list(XLSX_LOCATOR_RUN_STORE_TABLES),
        }
    return projection


def apply_xlsx_locator_tool_execute_once_to_outputs(
    raw_outputs: Sequence[Mapping[str, Any]],
    *,
    evidence_gate_mode: str,
    citation_format: str,
    composer_provider: str = "selected-evidence-deterministic-v1",
    local_llm_backend: str = "",
    local_llm_base_url: str = "",
    local_llm_model: str = "",
    local_llm_timeout_seconds: int = 60,
    local_llm_max_tokens: int = 360,
    skip_local_llm_endpoint_check: bool = False,
) -> tuple[list[dict[str, Any]], XlsxLocatorRunRecord]:
    before_rows = [dict(row) for row in raw_outputs]
    before_gate_summary = build_evidence_gate_summary(before_rows, mode=evidence_gate_mode)
    gate_before = _portfolio_gate_summary({"evidence_gate": before_gate_summary})
    updated_rows = [dict(row) for row in before_rows]
    decisions: list[dict[str, Any]] = []

    for item_index, row in enumerate(before_rows):
        if _clean(row.get("answer_gate_decision")) == "allow_answer":
            continue
        residual = _classify_xlsx_pdf_residual_row(row)
        if residual.get("source_family") != "XLSX":
            continue
        if residual.get("classification") not in {
            "selected_evidence_has_value_missing_axis",
            "selected_evidence_absent",
            "candidate_present_anchor_missing",
        }:
            continue
        query = _clean(row.get("query"))
        candidates = _xlsx_locator_tool_candidates(row)
        candidates = _xlsx_locator_apply_required_axis_materializer_actions(row=row, candidates=candidates)
        accepted_candidates = [candidate for candidate in candidates if candidate.get("accepted_for_regating") is True]
        forbidden_seen = sorted(
            {
                _clean(field)
                for candidate in candidates
                for field in _as_list(candidate.get("forbidden_input_fields_seen"))
                if _clean(field)
            }
        )
        decision: dict[str, Any] = {
            "item_index": item_index,
            "item_id": _report_item_id(row, item_index),
            "query_sha256": f"sha256:{_sha256_text(query)}" if query else "",
            "query_preview": _bounded_text_preview(query, 160),
            "failure_class": "tool_required_xlsx",
            "proposed_action": "xlsx_cell_or_table_tool",
            "expected_extra_query_count": 0,
            "expected_tool_call_count": 1,
            "expected_llm_retry_count": 0,
            "expected_memory_lookup_count": 0,
            "executed": True,
            "extra_query_count_executed": 0,
            "tool_call_count_executed": 1,
            "llm_retry_count_executed": 0,
            "memory_lookup_count_executed": 0,
            "candidate_count": len(candidates),
            "accepted_candidate_count": len(accepted_candidates),
            "forbidden_input_fields_seen": forbidden_seen,
            "forbidden_input_fields_used": [],
            "tool_name": "xlsx_cell_or_table_tool",
            "tool_input_policy": XLSX_LOCATOR_TOOL_POLICY,
            "input_policy": (
                "query_text_public_gate_diagnostics_and_source_owned_locator_metadata_only_no_ids_expected_qrels_labels_baseline"
            ),
            "candidates": candidates,
        }
        if not accepted_candidates:
            status = "skipped_missing_source_locator"
            output_row = dict(row)
            tool_use = _xlsx_locator_tool_use_meta(
                status=status,
                candidates=candidates,
                gated_row=row,
            )
            output_row["xlsx_locator_tool_use"] = tool_use
            updated_rows[item_index] = output_row
            decision["execution_status"] = status
            decision["tool_use"] = tool_use
            decisions.append(decision)
            continue

        original_contexts = [
            dict(context)
            for context in _as_list(row.get("retrieved_contexts"))
            if isinstance(context, Mapping)
        ]
        tool_output = dict(row)
        tool_output["retrieved_contexts"] = [
            *[_runtime_safe_evidence_context(candidate) for candidate in accepted_candidates],
            *[_runtime_safe_evidence_context(context) for context in original_contexts],
        ]
        tool_output["citations"] = []
        composed_tool = apply_selected_evidence_composer_to_outputs(
            [tool_output],
            citation_format=citation_format,
            composer_provider=composer_provider,
            local_llm_backend=local_llm_backend,
            local_llm_base_url=local_llm_base_url,
            local_llm_model=local_llm_model,
            local_llm_timeout_seconds=local_llm_timeout_seconds,
            local_llm_max_tokens=local_llm_max_tokens,
            skip_local_llm_endpoint_check=skip_local_llm_endpoint_check,
            retry_mode="off",
        )
        gated_tool, _tool_gate = apply_evidence_gate_to_outputs(composed_tool, mode=evidence_gate_mode)
        gated_row = gated_tool[0]
        if _clean(gated_row.get("answer_gate_decision")) == "allow_answer":
            status = "accepted_after_regating"
            tool_use = _xlsx_locator_tool_use_meta(
                status=status,
                candidates=candidates,
                gated_row=gated_row,
            )
            gated_row["xlsx_locator_tool_use"] = tool_use
            updated_rows[item_index] = gated_row
        else:
            status = "rejected_gate_insufficient"
            output_row = dict(row)
            tool_use = _xlsx_locator_tool_use_meta(
                status=status,
                candidates=candidates,
                gated_row=gated_row,
            )
            output_row["xlsx_locator_tool_use"] = tool_use
            updated_rows[item_index] = output_row
        decision["execution_status"] = status
        decision["tool_use"] = tool_use
        decisions.append(decision)

    after_gate_summary = build_evidence_gate_summary(updated_rows, mode=evidence_gate_mode)
    gate_after = _portfolio_gate_summary({"evidence_gate": after_gate_summary})
    run_record = _build_xlsx_locator_run_record(
        before_rows=before_rows,
        after_rows=updated_rows,
        gate_before=gate_before,
        gate_after=gate_after,
        decisions=decisions,
    )
    return updated_rows, run_record


def _agentic_planner_run_local_memory_bank(rows: Sequence[Any]) -> list[dict[str, Any]]:
    memory: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if _clean(row.get("answer_gate_decision")) != "allow_answer":
            continue
        gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
        for evidence in _as_list(gate.get("selected_evidence")):
            if not isinstance(evidence, Mapping):
                continue
            if not _has_sourceatom_evidence_identity(evidence):
                continue
            text = _gate_row_text(evidence)
            identity = _context_identity(evidence)
            if not text or not identity or identity in seen:
                continue
            memory_context = dict(evidence)
            memory_context["agentic_planner_run_local_memory"] = True
            memory_context["agentic_planner_memory_source_query_sha256"] = f"sha256:{_sha256_text(_clean(row.get('query')))}"
            memory_context["agentic_planner_memory_input_policy"] = AGENTIC_PLANNER_RUN_LOCAL_MEMORY_INPUT_POLICY
            memory.append(
                {
                    "context": memory_context,
                    "source_query_sha256": memory_context["agentic_planner_memory_source_query_sha256"],
                    "source_query_preview": _bounded_text_preview(_clean(row.get("query")), 160),
                    "evidence_ids": _selected_evidence_ids([memory_context]),
                }
            )
            seen.add(identity)
    return memory


def _agentic_planner_missing_query_anchors(row: Mapping[str, Any]) -> set[str]:
    gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
    anchors: set[str] = set()
    for key in ("missing_query_anchors", "missing_query_focus_anchors"):
        for anchor in _as_list(gate.get(key)):
            normalized = normalize_answer_text(_clean(anchor))
            if normalized:
                anchors.add(normalized)
    return anchors


def _agentic_planner_run_local_memory_match(
    row: Mapping[str, Any],
    memory_bank: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    query = _clean(row.get("query"))
    if not query:
        return None
    existing_ids = {_context_identity(context) for context in _contexts_from_row(row)}
    query_anchors = _query_focus_anchors_for_row(row)
    best: tuple[float, int, dict[str, Any]] | None = None
    for index, memory in enumerate(memory_bank):
        context = memory.get("context") if isinstance(memory.get("context"), Mapping) else {}
        if not context:
            continue
        identity = _context_identity(context)
        if identity and identity in existing_ids:
            continue
        text = _gate_row_text(context)
        if not text:
            continue
        missing_anchors = _agentic_planner_missing_query_anchors(row)
        if missing_anchors:
            missing_anchor_hits = _gate_anchor_hits(missing_anchors, [text])
            if missing_anchor_hits != missing_anchors:
                continue
        anchor_hits = _gate_anchor_hits(query_anchors, [text])
        query_overlap = _token_overlap_ratio(query, text)
        if query_anchors:
            if not anchor_hits and query_overlap < 0.2:
                continue
        elif query_overlap < 0.2:
            continue
        score = (10.0 * len(anchor_hits)) + query_overlap
        candidate = {
            "context": dict(context),
            "source_query_sha256": _clean(memory.get("source_query_sha256")),
            "source_query_preview": _bounded_text_preview(memory.get("source_query_preview"), 160),
            "evidence_ids": [value for value in _as_list(memory.get("evidence_ids")) if isinstance(value, str)],
            "anchor_hits": sorted(anchor_hits),
            "query_overlap": round(query_overlap, 6),
            "score": round(score, 6),
        }
        if best is None or score > best[0]:
            best = (score, index, candidate)
    return best[2] if best else None


def _agentic_planner_selected_evidence_for_llm_retry(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
    selected = [dict(context) for context in _as_list(gate.get("selected_evidence")) if isinstance(context, Mapping)]
    if selected:
        return selected
    return select_composer_evidence(
        _clean(row.get("query")),
        _contexts_from_row(row),
        max_evidence=3,
        query_evidence_planner=(
            row.get("query_evidence_planner") if isinstance(row.get("query_evidence_planner"), Mapping) else None
        ),
    )


def _agentic_planner_llm_retry_prompt(
    *,
    row: Mapping[str, Any],
    selected_evidence: Sequence[Mapping[str, Any]],
    previous_answer_preview: str,
) -> str:
    gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
    evidence_payload: list[dict[str, Any]] = []
    for evidence in selected_evidence:
        citation = _normalize_citation(evidence)
        metadata_text, metadata_fields = source_derived_evidence_metadata(evidence)
        evidence_payload.append(
            {
                "evidence_id": _clean(evidence.get("evidence_bundle_id"))
                or _clean(evidence.get("source_atom_id"))
                or _context_identity(evidence),
                "source_atom_id": _clean(evidence.get("source_atom_id")),
                "evidence_bundle_id": _clean(evidence.get("evidence_bundle_id")),
                "doc_id": _clean(citation.get("doc_id")),
                "chunk_id": _clean(citation.get("chunk_id")),
                "source_family": _clean(evidence.get("source_family")) or "UNKNOWN",
                "granularity": _clean(evidence.get("granularity")) or "unknown",
                "text_sha256": _gate_row_hash(evidence),
                "text_preview": _bounded_text_preview(_gate_support_text(evidence), 1000),
                "source_derived_metadata_text": _bounded_text_preview(metadata_text, 500),
                "source_derived_metadata_fields": metadata_fields,
            }
        )
    payload = {
        "query": _clean(row.get("query")),
        "input_policy": AGENTIC_PLANNER_LLM_RETRY_INPUT_POLICY,
        "selected_evidence": evidence_payload,
        "gate_diagnostics": {
            "failure_class": _agentic_planner_failure_class(row),
            "evidence_package_status": _clean(gate.get("evidence_package_status")),
            "answer_gate_decision": _clean(gate.get("answer_gate_decision") or row.get("answer_gate_decision")),
            "abstention_reason": _clean(gate.get("abstention_reason") or row.get("abstention_reason")),
            "validation_reasons": [
                _clean(reason) for reason in _as_list(gate.get("validation_reasons")) if _clean(reason)
            ],
            "missing_query_focus_anchors": [
                _clean(anchor) for anchor in _as_list(gate.get("missing_query_anchors")) if _clean(anchor)
            ],
        },
        "previous_answer_preview": _bounded_text_preview(previous_answer_preview),
        "citation_policy": "citation_evidence_ids must be selected evidence_id, evidence_bundle_id, or source_atom_id values only",
        "max_retry_count": 1,
    }
    return (
        "You are a non-production selected-evidence answer composer retry.\n"
        "Return exactly one JSON object with keys: answer (string) and citation_evidence_ids (array of strings).\n"
        "Use only the JSON payload below. Do not use outside knowledge.\n"
        "If the selected evidence is insufficient, return an empty answer and an empty citation_evidence_ids array.\n\n"
        f"Payload:\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n"
    )


def _agentic_planner_llm_retry_output(
    row: Mapping[str, Any],
    *,
    citation_format: str,
    local_llm_backend: str,
    local_llm_base_url: str,
    local_llm_model: str,
    local_llm_timeout_seconds: int,
    local_llm_max_tokens: int,
    skip_local_llm_endpoint_check: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    selected_evidence = _agentic_planner_selected_evidence_for_llm_retry(row)
    previous_answer_preview = _bounded_text_preview(
        _clean(row.get(INTERNAL_PRE_GATE_ANSWER_KEY)) or _clean(row.get("generated_answer"))
    )
    base_meta: dict[str, Any] = {
        "tool_name": "selected_evidence_llm_rewrite",
        "status": "skipped",
        "attempt_count": 0,
        "max_retry_count": 1,
        "input_policy": AGENTIC_PLANNER_LLM_RETRY_INPUT_POLICY,
        "prompt_template_id": AGENTIC_PLANNER_LLM_RETRY_PROMPT_VERSION,
        "selected_evidence_count": len(selected_evidence),
        "selected_evidence_ids": _selected_evidence_ids(selected_evidence),
        "previous_answer_preview": previous_answer_preview,
        "previous_answer_preview_sha256": f"sha256:{_sha256_text(previous_answer_preview)}"
        if previous_answer_preview
        else "",
        "uses_query_id_or_row_id_or_target_id": False,
        "uses_expected_answer_or_evidence": False,
        "uses_qrels_or_labels": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }
    if not selected_evidence:
        return None, {**base_meta, "status": "skipped_no_selected_evidence"}

    config = _local_llm_composer_config(
        backend=local_llm_backend,
        base_url=local_llm_base_url,
        model=local_llm_model,
        timeout_seconds=local_llm_timeout_seconds,
        max_tokens=local_llm_max_tokens,
        check_endpoint=not skip_local_llm_endpoint_check,
    )
    if not config.get("available"):
        return None, {
            **base_meta,
            "status": "skipped_local_llm_unavailable",
            "blockers": list(config.get("blockers") or []),
        }

    prompt = _agentic_planner_llm_retry_prompt(
        row=row,
        selected_evidence=selected_evidence,
        previous_answer_preview=previous_answer_preview,
    )
    prompt_sha256 = f"sha256:{_sha256_text(prompt)}"
    retry_base = {
        **base_meta,
        "status": "attempted",
        "attempt_count": 1,
        "retry_prompt_sha256": prompt_sha256,
    }
    try:
        parsed, meta = LOCAL_LLM_HELPER.call_local_llm_strict_json(
            backend=_clean(config.get("backend")),
            base_url=_clean(config.get("base_url")),
            model=_clean(config.get("model")),
            prompt=prompt,
            temperature=0.0,
            max_tokens=int(config.get("max_tokens") or local_llm_max_tokens),
            timeout_seconds=int(config.get("timeout_seconds") or local_llm_timeout_seconds),
        )
    except Exception as exc:
        return None, {
            **retry_base,
            "status": "error",
            "error": f"LOCAL_LLM_PLANNER_RETRY_ERROR: {type(exc).__name__}: {exc}",
        }

    retry_answer = _clean(parsed.get("answer") or parsed.get("short_answer"))
    retry_citation_ids = _ids_from_local_llm_citation_field(
        parsed.get("citation_evidence_ids") or parsed.get("citations") or parsed.get("evidence_ids")
    )
    retry_raw_sha = _clean((meta or {}).get("raw_response_sha256"))
    retry_output = _selected_evidence_local_llm_output_from_answer(
        row=row,
        query=_clean(row.get("query")),
        query_selected=selected_evidence,
        answer=retry_answer,
        citation_ids=retry_citation_ids,
        normalized_citation_format=_normalize_selected_evidence_citation_format(citation_format),
        config=config,
        prompt_sha256=prompt_sha256,
        raw_response_sha256=retry_raw_sha,
    )
    retry_meta = {
        **retry_base,
        "retry_raw_response_sha256": retry_raw_sha,
        "retry_answer_preview": _bounded_text_preview(retry_answer),
    }
    if retry_output is None:
        return None, {**retry_meta, "status": "rejected_empty_or_unselected_evidence"}
    return retry_output, retry_meta


def apply_agentic_planner_execute_once_to_outputs(
    raw_outputs: Sequence[Mapping[str, Any]],
    *,
    adapter: Any,
    top_k: int,
    evidence_gate_mode: str,
    citation_format: str,
    composer_provider: str = "selected-evidence-deterministic-v1",
    local_llm_backend: str = "",
    local_llm_base_url: str = "",
    local_llm_model: str = "",
    local_llm_timeout_seconds: int = 60,
    local_llm_max_tokens: int = 360,
    skip_local_llm_endpoint_check: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    before_rows = [dict(row) for row in raw_outputs]
    before_gate_summary = build_evidence_gate_summary(before_rows, mode=evidence_gate_mode)
    gate_before = _portfolio_gate_summary({"evidence_gate": before_gate_summary})
    updated_rows = [dict(row) for row in before_rows]
    decisions: list[dict[str, Any]] = []
    executed_extra_query_count = 0
    executed_tool_call_count = 0
    executed_llm_retry_count = 0
    executed_memory_lookup_count = 0
    memory_bank = _agentic_planner_run_local_memory_bank(before_rows)
    probe_top_k = max(int(top_k) + AGENTIC_PLANNER_EXECUTE_ONCE_PROBE_TOP_K_INCREMENT, 2)

    for item_index, row in enumerate(before_rows):
        if _clean(row.get("answer_gate_decision")) == "allow_answer":
            continue
        failure_class = _agentic_planner_failure_class(row)
        action = _agentic_planner_action_for_failure(failure_class)
        memory_match = _agentic_planner_run_local_memory_match(row, memory_bank)
        if failure_class in {"insufficient_evidence", "missing_query_anchor"} and memory_match is not None:
            action = "run_local_memory_reuse"
        query = _clean(row.get("query"))
        decision: dict[str, Any] = {
            "item_index": item_index,
            "query_sha256": f"sha256:{_sha256_text(query)}" if query else "",
            "query_preview": _bounded_text_preview(query, 160),
            "failure_class": failure_class,
            "proposed_action": action,
            "expected_extra_query_count": _agentic_planner_expected_extra_query_count(action),
            "expected_tool_call_count": _agentic_planner_expected_tool_call_count(action),
            "expected_llm_retry_count": _agentic_planner_expected_llm_retry_count(action),
            "expected_memory_lookup_count": _agentic_planner_expected_memory_lookup_count(action),
            "executed": False,
            "execution_status": "skipped_no_safe_executor",
            "input_policy": (
                "query_text_and_public_gate_diagnostics_only_no_ids_expected_qrels_labels_baseline_or_legacy_outputs"
            ),
        }
        if action not in {
            "query_text_only_reformulation",
            "route_selected_probe",
            "pdf_locator_tool",
            "xlsx_cell_or_table_tool",
        }:
            decision.update(
                {
                    "extra_query_count_executed": 0,
                    "tool_call_count_executed": 0,
                    "llm_retry_count_executed": 0,
                    "memory_lookup_count_executed": 0,
                    "execution_status": "deferred_requires_explicit_execution_gate",
                    "execution_gate_required": True,
                }
            )
            decisions.append(decision)
            continue
        if action in {"query_text_only_reformulation", "route_selected_probe"}:
            probe_output = adapter.run_item(_agentic_planner_sanitized_item_for_retrieval(row), top_k=probe_top_k)
            probe_output = dict(probe_output)
            probe_output["id"] = _clean(row.get("id"))
            probe_output["query"] = query
            probe_output["answerability"] = _clean(row.get("answerability")) or "unknown"
            probe_output["agentic_planner_execute_once_probe"] = {
                "planner_action": action,
                "probe_top_k": probe_top_k,
                "input_policy": "sanitized_query_text_only_no_ids_expected_qrels_labels_or_baseline",
                "uses_query_id_or_row_id_or_target_id": False,
                "uses_expected_answer_or_evidence": False,
                "uses_qrels_or_labels": False,
            }
            composed_probe = apply_selected_evidence_composer_to_outputs(
                [probe_output],
                citation_format=citation_format,
                composer_provider=composer_provider,
                local_llm_backend=local_llm_backend,
                local_llm_base_url=local_llm_base_url,
                local_llm_model=local_llm_model,
                local_llm_timeout_seconds=local_llm_timeout_seconds,
                local_llm_max_tokens=local_llm_max_tokens,
                skip_local_llm_endpoint_check=skip_local_llm_endpoint_check,
                retry_mode="off",
            )
            gated_probe, _probe_gate = apply_evidence_gate_to_outputs(composed_probe, mode=evidence_gate_mode)
            updated_rows[item_index] = gated_probe[0]
            executed_extra_query_count += 1
            decision.update(
                {
                    "executed": True,
                    "execution_status": "executed",
                    "extra_query_count_executed": 1,
                    "tool_call_count_executed": 0,
                    "llm_retry_count_executed": 0,
                    "probe_top_k": probe_top_k,
                }
            )
        elif action == "pdf_locator_tool":
            gated_row, tool_use = _agentic_planner_pdf_locator_tool_output(
                row,
                evidence_gate_mode=evidence_gate_mode,
                citation_format=citation_format,
                composer_provider=composer_provider,
                local_llm_backend=local_llm_backend,
                local_llm_base_url=local_llm_base_url,
                local_llm_model=local_llm_model,
                local_llm_timeout_seconds=local_llm_timeout_seconds,
                local_llm_max_tokens=local_llm_max_tokens,
                skip_local_llm_endpoint_check=skip_local_llm_endpoint_check,
            )
            tool_call_count = int(tool_use.get("tool_call_count") or 0)
            tool_status = _clean(tool_use.get("execution_status") or tool_use.get("status")) or "skipped_missing_source_locator"
            if tool_status == "accepted_after_regating":
                gated_row["agentic_planner_tool_use"] = {
                    "tool_name": action,
                    "tool_implementation": PDF_LOCATOR_TOOL_NAME,
                    "tool_call_count": tool_call_count,
                    "input_policy": PDF_LOCATOR_TOOL_POLICY,
                    "output_policy": PDF_LOCATOR_TOOL_OUTPUT_POLICY,
                    "pdf_locator_execution_status": tool_status,
                    "uses_query_id_or_row_id_or_target_id": False,
                    "uses_expected_answer_or_evidence": False,
                    "uses_qrels_or_labels": False,
                    "raw_prompt_payload_written": False,
                    "raw_response_payload_written": False,
                }
                updated_rows[item_index] = gated_row
            executed_tool_call_count += tool_call_count
            decision_update = {
                "executed": tool_status == "accepted_after_regating",
                "execution_status": tool_status,
                "extra_query_count_executed": 0,
                "tool_call_count_executed": tool_call_count,
                "llm_retry_count_executed": 0,
                "tool_name": PDF_LOCATOR_TOOL_NAME,
                "tool_input_policy": PDF_LOCATOR_TOOL_POLICY,
                "tool_output_policy": PDF_LOCATOR_TOOL_OUTPUT_POLICY,
                "pdf_locator_candidate_count": int(tool_use.get("candidate_count") or 0),
                "pdf_locator_accepted_candidate_count": int(tool_use.get("accepted_candidate_count") or 0),
            }
            if tool_use.get("execution_gate_required") is True:
                decision_update["execution_gate_required"] = True
            decision.update(decision_update)
        elif action == "xlsx_cell_or_table_tool":
            tool_rows, tool_record = apply_xlsx_locator_tool_execute_once_to_outputs(
                [row],
                evidence_gate_mode=evidence_gate_mode,
                citation_format=citation_format,
                composer_provider=composer_provider,
                local_llm_backend=local_llm_backend,
                local_llm_base_url=local_llm_base_url,
                local_llm_model=local_llm_model,
                local_llm_timeout_seconds=local_llm_timeout_seconds,
                local_llm_max_tokens=local_llm_max_tokens,
                skip_local_llm_endpoint_check=skip_local_llm_endpoint_check,
            )
            gated_row = dict(tool_rows[0])
            tool_use = gated_row.get("xlsx_locator_tool_use") if isinstance(gated_row.get("xlsx_locator_tool_use"), Mapping) else {}
            tool_call_count = int(tool_record.tool_invocation_count)
            tool_status = _clean(tool_use.get("execution_status")) or "skipped_missing_source_locator"
            gated_row["agentic_planner_tool_use"] = {
                "tool_name": action,
                "tool_implementation": XLSX_LOCATOR_TOOL_NAME,
                "tool_call_count": tool_call_count,
                "input_policy": XLSX_LOCATOR_TOOL_POLICY,
                "output_policy": XLSX_LOCATOR_TOOL_OUTPUT_POLICY,
                "xlsx_locator_execution_status": tool_status,
                "uses_query_id_or_row_id_or_target_id": False,
                "uses_expected_answer_or_evidence": False,
                "uses_qrels_or_labels": False,
                "raw_prompt_payload_written": False,
                "raw_response_payload_written": False,
            }
            updated_rows[item_index] = gated_row
            executed_tool_call_count += tool_call_count
            decision.update(
                {
                    "executed": tool_call_count > 0,
                    "execution_status": tool_status,
                    "extra_query_count_executed": 0,
                    "tool_call_count_executed": tool_call_count,
                    "llm_retry_count_executed": 0,
                    "tool_name": XLSX_LOCATOR_TOOL_NAME,
                    "tool_input_policy": XLSX_LOCATOR_TOOL_POLICY,
                    "tool_output_policy": XLSX_LOCATOR_TOOL_OUTPUT_POLICY,
                    "xlsx_locator_candidate_count": int(tool_record.accepted_candidate_count + tool_record.rejected_candidate_count),
                    "xlsx_locator_accepted_candidate_count": int(tool_record.accepted_candidate_count),
                }
            )
        elif action == "run_local_memory_reuse":
            if memory_match is not None:
                memory_context = dict(memory_match["context"])
                memory_context["rank"] = 1
                original_contexts = [
                    dict(context)
                    for context in _as_list(row.get("retrieved_contexts"))
                    if isinstance(context, Mapping)
                ]
                memory_output = dict(row)
                memory_output["retrieved_contexts"] = [
                    _runtime_safe_evidence_context(memory_context),
                    *[_runtime_safe_evidence_context(context) for context in original_contexts],
                ]
                memory_output["citations"] = []
                memory_meta = {
                    "status": "attempted",
                    "input_policy": AGENTIC_PLANNER_RUN_LOCAL_MEMORY_INPUT_POLICY,
                    "memory_lookup_count": 1,
                    "memory_source_query_sha256": _clean(memory_match.get("source_query_sha256")),
                    "memory_evidence_ids": list(memory_match.get("evidence_ids") or []),
                    "memory_anchor_hits": list(memory_match.get("anchor_hits") or []),
                    "memory_query_overlap": memory_match.get("query_overlap"),
                    "uses_query_id_or_row_id_or_target_id": False,
                    "uses_expected_answer_or_evidence": False,
                    "uses_qrels_or_labels": False,
                    "retrieved_context_only_citation_promoted": False,
                    "raw_prompt_payload_written": False,
                    "raw_response_payload_written": False,
                }
                composed_memory = apply_selected_evidence_composer_to_outputs(
                    [memory_output],
                    citation_format=citation_format,
                    composer_provider=composer_provider,
                    local_llm_backend=local_llm_backend,
                    local_llm_base_url=local_llm_base_url,
                    local_llm_model=local_llm_model,
                    local_llm_timeout_seconds=local_llm_timeout_seconds,
                    local_llm_max_tokens=local_llm_max_tokens,
                    skip_local_llm_endpoint_check=skip_local_llm_endpoint_check,
                    retry_mode="off",
                )
                gated_memory, _memory_gate = apply_evidence_gate_to_outputs(composed_memory, mode=evidence_gate_mode)
                gated_row = gated_memory[0]
                memory_gate = gated_row.get("evidence_gate") if isinstance(gated_row.get("evidence_gate"), Mapping) else {}
                if _clean(gated_row.get("answer_gate_decision")) == "allow_answer":
                    accepted_meta = {
                        **memory_meta,
                        "status": "accepted",
                        "memory_evidence_package_status": _clean(memory_gate.get("evidence_package_status")),
                        "memory_answer_gate_decision": _clean(gated_row.get("answer_gate_decision")),
                    }
                    gated_row["agentic_planner_run_local_memory"] = accepted_meta
                    updated_rows[item_index] = gated_row
                    executed_memory_lookup_count += 1
                    decision.update(
                        {
                            "executed": True,
                            "execution_status": "executed",
                            "extra_query_count_executed": 0,
                            "tool_call_count_executed": 0,
                            "llm_retry_count_executed": 0,
                            "memory_lookup_count_executed": 1,
                            "memory_input_policy": AGENTIC_PLANNER_RUN_LOCAL_MEMORY_INPUT_POLICY,
                            "memory_source_query_sha256": accepted_meta["memory_source_query_sha256"],
                            "memory_evidence_ids": accepted_meta["memory_evidence_ids"],
                        }
                    )
                else:
                    decision.update(
                        {
                            "extra_query_count_executed": 0,
                            "tool_call_count_executed": 0,
                            "llm_retry_count_executed": 0,
                            "memory_lookup_count_executed": 0,
                            "execution_status": "rejected_gate_insufficient",
                            "memory_input_policy": AGENTIC_PLANNER_RUN_LOCAL_MEMORY_INPUT_POLICY,
                        }
                    )
            else:
                decision.update(
                    {
                        "extra_query_count_executed": 0,
                        "tool_call_count_executed": 0,
                        "llm_retry_count_executed": 0,
                        "memory_lookup_count_executed": 0,
                        "execution_status": "skipped_no_run_local_memory_match",
                        "memory_input_policy": AGENTIC_PLANNER_RUN_LOCAL_MEMORY_INPUT_POLICY,
                    }
                )
        elif action == "selected_evidence_llm_rewrite":
            retry_output, retry_meta = _agentic_planner_llm_retry_output(
                row,
                citation_format=citation_format,
                local_llm_backend=local_llm_backend,
                local_llm_base_url=local_llm_base_url,
                local_llm_model=local_llm_model,
                local_llm_timeout_seconds=local_llm_timeout_seconds,
                local_llm_max_tokens=local_llm_max_tokens,
                skip_local_llm_endpoint_check=skip_local_llm_endpoint_check,
            )
            if retry_output is not None:
                gated_retry, _retry_gate = apply_evidence_gate_to_outputs([retry_output], mode=evidence_gate_mode)
                gated_row = gated_retry[0]
                retry_validation = gated_row.get("evidence_gate") if isinstance(gated_row.get("evidence_gate"), Mapping) else {}
                retry_decision = _clean(gated_row.get("answer_gate_decision"))
                if retry_decision == "allow_answer":
                    accepted_meta = {
                        **retry_meta,
                        "status": "accepted",
                        "retry_evidence_package_status": _clean(retry_validation.get("evidence_package_status")),
                        "retry_answer_gate_decision": retry_decision,
                        "retry_abstention_reason": _clean(retry_validation.get("abstention_reason")),
                    }
                    gated_row["agentic_planner_llm_retry"] = accepted_meta
                    updated_rows[item_index] = gated_row
                    executed_llm_retry_count += 1
                    decision.update(
                        {
                            "executed": True,
                            "execution_status": "executed",
                            "extra_query_count_executed": 0,
                            "tool_call_count_executed": 0,
                            "llm_retry_count_executed": 1,
                            "llm_retry_input_policy": AGENTIC_PLANNER_LLM_RETRY_INPUT_POLICY,
                        }
                    )
                else:
                    rejected_meta = {
                        **retry_meta,
                        "status": "rejected_gate_insufficient",
                        "retry_evidence_package_status": _clean(retry_validation.get("evidence_package_status")),
                        "retry_answer_gate_decision": retry_decision,
                        "retry_abstention_reason": _clean(retry_validation.get("abstention_reason")),
                    }
                    decision.update(
                        {
                            "extra_query_count_executed": 0,
                            "tool_call_count_executed": 0,
                            "llm_retry_count_executed": 0,
                            "execution_status": rejected_meta["status"],
                            "llm_retry_input_policy": AGENTIC_PLANNER_LLM_RETRY_INPUT_POLICY,
                        }
                    )
            else:
                decision.update(
                    {
                        "extra_query_count_executed": 0,
                        "tool_call_count_executed": 0,
                        "llm_retry_count_executed": 0,
                        "execution_status": _clean(retry_meta.get("status")) or "skipped_llm_retry_unavailable",
                        "llm_retry_input_policy": AGENTIC_PLANNER_LLM_RETRY_INPUT_POLICY,
                    }
                )
        else:
            decision["extra_query_count_executed"] = 0
            decision["tool_call_count_executed"] = 0
            decision["llm_retry_count_executed"] = 0
            decision["memory_lookup_count_executed"] = 0
        decisions.append(decision)

    after_gate_summary = build_evidence_gate_summary(updated_rows, mode=evidence_gate_mode)
    gate_after = _portfolio_gate_summary({"evidence_gate": after_gate_summary})
    action_counts = Counter(_clean(decision.get("proposed_action")) for decision in decisions)
    failure_counts = Counter(_clean(decision.get("failure_class")) for decision in decisions)
    report = {
        "schema_version": AGENTIC_PLANNER_EXECUTE_ONCE_SCHEMA_VERSION,
        "planner_enabled": True,
        "planner_mode": "execute-once",
        "planner_version": AGENTIC_PLANNER_EXECUTE_ONCE_SCHEMA_VERSION,
        "ran_after_selected_evidence_composer": True,
        "ran_after_evidence_gate": True,
        "planner_scope": "failed_rows_after_selected_evidence_composer_and_evidence_gate",
        "planner_decision_count": len(decisions),
        "planner_executed_decision_count": sum(1 for decision in decisions if decision.get("executed") is True),
        "planner_action_counts": dict(sorted(action_counts.items())),
        "planner_failure_class_counts": dict(sorted(failure_counts.items())),
        "planner_no_safe_action_count": int(failure_counts.get("no_safe_action", 0)),
        "planner_forbidden_shortcut_detected_count": _agentic_planner_forbidden_shortcut_count(decisions),
        "planner_expected_extra_query_count": sum(int(decision.get("expected_extra_query_count") or 0) for decision in decisions),
        "planner_expected_tool_call_count": sum(int(decision.get("expected_tool_call_count") or 0) for decision in decisions),
        "planner_expected_llm_retry_count": sum(int(decision.get("expected_llm_retry_count") or 0) for decision in decisions),
        "planner_expected_memory_lookup_count": sum(int(decision.get("expected_memory_lookup_count") or 0) for decision in decisions),
        "planner_memory_lookup_count_executed": executed_memory_lookup_count,
        "planner_heuristic_risk_class": "diagnostic_probe_only",
        "candidate_generation_input_policy": (
            "query_text_and_public_gate_diagnostics_only_no_ids_expected_qrels_labels_baseline_or_legacy_outputs"
        ),
        "retrieved_context_only_citation_policy": "diagnostic_only_never_promoted",
        "official_metric": False,
        "official_metric_input_rows": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "planner_execution": _agentic_planner_execute_once_execution(
            extra_query_count=executed_extra_query_count,
            tool_call_count=executed_tool_call_count,
            llm_retry_count=executed_llm_retry_count,
        ),
        "guardrail_mutation_flags": _agentic_planner_execute_once_guardrail_flags(),
        "gate_before": gate_before,
        "gate_after": gate_after,
        "gate_delta": _agentic_planner_gate_delta(gate_before, gate_after),
        "decisions": decisions,
        "execute_once_readiness": {
            "ready": False,
            "assessment": (
                "execute_once_checkpoint_executed_bounded_query_source_locator_llm_retry_or_run_local_memory_action_only; "
                "broader agent loops remain closed"
            ),
            "quality_improvement_measured": int(gate_after.get("allowed_answer_count") or 0)
            > int(gate_before.get("allowed_answer_count") or 0),
            "reason": "execute-once measures post-gate delta under unchanged evidence gate",
        },
    }
    return updated_rows, report


def validate_agentic_planner_dry_run(run_id: str, planner: Mapping[str, Any]) -> None:
    if planner.get("schema_version") != AGENTIC_PLANNER_DRY_RUN_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.schema_version unsupported")
    if planner.get("official_metric") is not False:
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.official_metric must be False")
    if int(planner.get("official_metric_input_rows") or 0) != 0:
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.official_metric_input_rows must be 0")
    for key in ("raw_prompt_payload_written", "raw_response_payload_written"):
        if planner.get(key) is not False:
            raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.{key} must be False")
    mode = _clean(planner.get("planner_mode")).lower() or "off"
    if mode not in AGENTIC_PLANNER_MODE_CHOICES:
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.planner_mode unsupported: {mode}")
    enabled = bool(planner.get("planner_enabled"))
    if enabled and mode != "dry-run":
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.planner_enabled requires dry-run mode")
    if enabled and planner.get("ran_after_selected_evidence_composer") is not True:
        raise DatasetSchemaError(
            f"{run_id}: agentic_planner_dry_run.ran_after_selected_evidence_composer must be True"
        )
    if enabled and planner.get("ran_after_evidence_gate") is not True:
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.ran_after_evidence_gate must be True")
    if planner.get("planner_heuristic_risk_class") != "diagnostic_probe_only":
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.planner_heuristic_risk_class must be diagnostic_probe_only")
    guardrail_flags = planner.get("guardrail_flags")
    if not isinstance(guardrail_flags, Mapping):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.guardrail_flags must be present")
    for key in AGENTIC_PLANNER_GUARDRAIL_FLAGS:
        if guardrail_flags.get(key) is not False:
            raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.guardrail_flags.{key} must be False")
    execution = planner.get("planner_execution")
    if not isinstance(execution, Mapping):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.planner_execution must be present")
    for key in ("retrieval_executed", "tool_call_executed", "llm_retry_executed"):
        if execution.get(key) is not False:
            raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.planner_execution.{key} must be False")
    for key in ("extra_query_count_executed", "tool_call_count_executed", "llm_retry_count_executed"):
        if int(execution.get(key) or 0) != 0:
            raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.planner_execution.{key} must be 0")
    if planner.get("retrieved_context_only_citation_policy") != "diagnostic_only_never_promoted":
        raise DatasetSchemaError(
            f"{run_id}: agentic_planner_dry_run.retrieved_context_only_citation_policy must be diagnostic_only_never_promoted"
        )
    gate_before = planner.get("gate_before")
    gate_after = planner.get("gate_after_unchanged_because_dry_run")
    if isinstance(gate_before, Mapping) and isinstance(gate_after, Mapping) and dict(gate_before) != dict(gate_after):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run gate_after must equal gate_before in dry-run")
    decisions = [decision for decision in _as_list(planner.get("decisions")) if isinstance(decision, Mapping)]
    if int(planner.get("planner_decision_count") or 0) != len(decisions):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.planner_decision_count mismatch")
    if int(planner.get("planner_forbidden_shortcut_detected_count") or 0) != 0:
        raise DatasetSchemaError(
            f"{run_id}: agentic_planner_dry_run.planner_forbidden_shortcut_detected_count must be 0"
        )
    expected_action_counts = dict(sorted(Counter(_clean(decision.get("proposed_action")) for decision in decisions).items()))
    if dict(planner.get("planner_action_counts") or {}) != expected_action_counts:
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.planner_action_counts mismatch")
    expected_failure_counts = dict(sorted(Counter(_clean(decision.get("failure_class")) for decision in decisions).items()))
    if dict(planner.get("planner_failure_class_counts") or {}) != expected_failure_counts:
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.planner_failure_class_counts mismatch")
    if int(planner.get("planner_expected_extra_query_count") or 0) != sum(
        int(decision.get("expected_extra_query_count") or 0) for decision in decisions
    ):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.planner_expected_extra_query_count mismatch")
    if int(planner.get("planner_expected_tool_call_count") or 0) != sum(
        int(decision.get("expected_tool_call_count") or 0) for decision in decisions
    ):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.planner_expected_tool_call_count mismatch")
    if int(planner.get("planner_expected_llm_retry_count") or 0) != sum(
        int(decision.get("expected_llm_retry_count") or 0) for decision in decisions
    ):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.planner_expected_llm_retry_count mismatch")
    if int(planner.get("planner_expected_memory_lookup_count") or 0) != sum(
        int(decision.get("expected_memory_lookup_count") or 0) for decision in decisions
    ):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run.planner_expected_memory_lookup_count mismatch")
    for decision in decisions:
        present_forbidden = sorted(key for key in AGENTIC_PLANNER_FORBIDDEN_DECISION_FIELDS if key in decision)
        if present_forbidden:
            raise DatasetSchemaError(
                f"{run_id}: agentic_planner_dry_run decision contains forbidden field {present_forbidden[0]}"
            )
        if "proposed_actions" in decision:
            raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run decision must contain exactly one proposed_action")
        failure_class = _clean(decision.get("failure_class"))
        if failure_class not in AGENTIC_PLANNER_FAILURE_CLASSES:
            raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run unsupported failure_class {failure_class}")
        action = _clean(decision.get("proposed_action"))
        if action not in AGENTIC_PLANNER_ACTIONS:
            raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run unsupported proposed_action {action}")
        if decision.get("executed") is not False:
            raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run decision.executed must be False")
        if int(decision.get("expected_extra_query_count") or 0) != _agentic_planner_expected_extra_query_count(action):
            raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run decision expected_extra_query_count mismatch")
        if int(decision.get("expected_tool_call_count") or 0) != _agentic_planner_expected_tool_call_count(action):
            raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run decision expected_tool_call_count mismatch")
        if int(decision.get("expected_llm_retry_count") or 0) != _agentic_planner_expected_llm_retry_count(action):
            raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run decision expected_llm_retry_count mismatch")
        if int(decision.get("expected_memory_lookup_count") or 0) != _agentic_planner_expected_memory_lookup_count(action):
            raise DatasetSchemaError(f"{run_id}: agentic_planner_dry_run decision expected_memory_lookup_count mismatch")


def validate_agentic_planner_execute_once(run_id: str, planner: Mapping[str, Any]) -> None:
    if planner.get("schema_version") != AGENTIC_PLANNER_EXECUTE_ONCE_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.schema_version unsupported")
    if planner.get("planner_mode") != "execute-once" or planner.get("planner_enabled") is not True:
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once must be enabled execute-once mode")
    if planner.get("official_metric") is not False:
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.official_metric must be False")
    if int(planner.get("official_metric_input_rows") or 0) != 0:
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.official_metric_input_rows must be 0")
    for key in ("raw_prompt_payload_written", "raw_response_payload_written"):
        if planner.get(key) is not False:
            raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.{key} must be False")
    if planner.get("planner_heuristic_risk_class") != "diagnostic_probe_only":
        raise DatasetSchemaError(
            f"{run_id}: agentic_planner_execute_once.planner_heuristic_risk_class must be diagnostic_probe_only"
        )
    if planner.get("retrieved_context_only_citation_policy") != "diagnostic_only_never_promoted":
        raise DatasetSchemaError(
            f"{run_id}: agentic_planner_execute_once.retrieved_context_only_citation_policy must be diagnostic_only_never_promoted"
        )
    flags = planner.get("guardrail_mutation_flags")
    if not isinstance(flags, Mapping):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.guardrail_mutation_flags must be present")
    for key, value in flags.items():
        if value is not False:
            raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.guardrail_mutation_flags.{key} must be False")
    execution = planner.get("planner_execution")
    if not isinstance(execution, Mapping):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.planner_execution must be present")
    decisions = [decision for decision in _as_list(planner.get("decisions")) if isinstance(decision, Mapping)]
    if int(planner.get("planner_decision_count") or 0) != len(decisions):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.planner_decision_count mismatch")
    executed = [decision for decision in decisions if decision.get("executed") is True]
    if int(planner.get("planner_executed_decision_count") or 0) != len(executed):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.planner_executed_decision_count mismatch")
    if int(planner.get("planner_forbidden_shortcut_detected_count") or 0) != 0:
        raise DatasetSchemaError(
            f"{run_id}: agentic_planner_execute_once.planner_forbidden_shortcut_detected_count must be 0"
        )
    if int(execution.get("extra_query_count_executed") or 0) != sum(
        int(decision.get("extra_query_count_executed") or 0) for decision in decisions
    ):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.extra_query_count_executed mismatch")
    if bool(execution.get("retrieval_executed")) != (int(execution.get("extra_query_count_executed") or 0) > 0):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.retrieval_executed mismatch")
    if int(execution.get("tool_call_count_executed") or 0) != sum(
        int(decision.get("tool_call_count_executed") or 0) for decision in decisions
    ):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.tool_call_count_executed mismatch")
    if bool(execution.get("tool_call_executed")) != (int(execution.get("tool_call_count_executed") or 0) > 0):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.tool_call_executed mismatch")
    if int(execution.get("llm_retry_count_executed") or 0) != sum(
        int(decision.get("llm_retry_count_executed") or 0) for decision in decisions
    ):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.llm_retry_count_executed mismatch")
    if bool(execution.get("llm_retry_executed")) != (int(execution.get("llm_retry_count_executed") or 0) > 0):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.llm_retry_executed mismatch")
    if int(planner.get("planner_expected_llm_retry_count") or 0) != sum(
        int(decision.get("expected_llm_retry_count") or 0) for decision in decisions
    ):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.planner_expected_llm_retry_count mismatch")
    if int(planner.get("planner_expected_memory_lookup_count") or 0) != sum(
        int(decision.get("expected_memory_lookup_count") or 0) for decision in decisions
    ):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.planner_expected_memory_lookup_count mismatch")
    if int(planner.get("planner_memory_lookup_count_executed") or 0) != sum(
        int(decision.get("memory_lookup_count_executed") or 0) for decision in decisions
    ):
        raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once.planner_memory_lookup_count_executed mismatch")
    for decision in decisions:
        present_forbidden = sorted(key for key in AGENTIC_PLANNER_FORBIDDEN_DECISION_FIELDS if key in decision)
        if present_forbidden:
            raise DatasetSchemaError(
                f"{run_id}: agentic_planner_execute_once decision contains forbidden field {present_forbidden[0]}"
            )
        if "proposed_actions" in decision:
            raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once decision must contain exactly one proposed_action")
        failure_class = _clean(decision.get("failure_class"))
        if failure_class not in AGENTIC_PLANNER_FAILURE_CLASSES:
            raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once unsupported failure_class {failure_class}")
        action = _clean(decision.get("proposed_action"))
        if action not in AGENTIC_PLANNER_ACTIONS:
            raise DatasetSchemaError(f"{run_id}: agentic_planner_execute_once unsupported proposed_action {action}")
        if decision.get("executed") is True and action not in {
            "query_text_only_reformulation",
            "route_selected_probe",
            "pdf_locator_tool",
            "xlsx_cell_or_table_tool",
        }:
            raise DatasetSchemaError(
                f"{run_id}: agentic_planner_execute_once unsupported executed action for this checkpoint"
            )


def validate_xlsx_locator_query_anchor_tool_acceptance_diagnostic(
    run_id: str,
    diagnostic: Mapping[str, Any],
    *,
    locator: Mapping[str, Any] | None = None,
) -> None:
    missing_required = sorted(XLSX_LOCATOR_QUERY_ANCHOR_DIAGNOSTIC_REQUIRED_KEYS - set(diagnostic))
    if missing_required:
        raise DatasetSchemaError(
            f"{run_id}: query_anchor_tool_acceptance_diagnostic.{missing_required[0]} must be present"
        )
    forbidden_keys = sorted(_collect_xlsx_locator_query_anchor_diagnostic_forbidden_keys(diagnostic))
    if forbidden_keys:
        raise DatasetSchemaError(
            f"{run_id}: query_anchor_tool_acceptance_diagnostic contains forbidden field {forbidden_keys[0]}"
        )
    if diagnostic.get("schema_version") != XLSX_LOCATOR_QUERY_ANCHOR_TOOL_ACCEPTANCE_DIAGNOSTIC_SCHEMA_VERSION:
        raise DatasetSchemaError(
            f"{run_id}: query_anchor_tool_acceptance_diagnostic.schema_version unsupported"
        )
    if diagnostic.get("report_only_diagnostic") is not True:
        raise DatasetSchemaError(
            f"{run_id}: query_anchor_tool_acceptance_diagnostic.report_only_diagnostic must be True"
        )
    if diagnostic.get("official_metric") is not False:
        raise DatasetSchemaError(
            f"{run_id}: query_anchor_tool_acceptance_diagnostic.official_metric must be False"
        )
    if int(diagnostic.get("official_metric_input_rows") or 0) != 0:
        raise DatasetSchemaError(
            f"{run_id}: query_anchor_tool_acceptance_diagnostic.official_metric_input_rows must be 0"
        )
    for key in (
        "uses_expected_fields",
        "uses_gold_fields",
        "uses_qrels_or_labels",
        "uses_ids_as_runtime_inputs",
        "uses_file_workbook_title",
        "uses_formula_or_normalized_value",
        "evidence_gate_loosened",
    ):
        if diagnostic.get(key) is not False:
            raise DatasetSchemaError(f"{run_id}: query_anchor_tool_acceptance_diagnostic.{key} must be False")
    count_keys = (
        "tool_invocation_count",
        "candidate_count",
        "accepted_for_regating_candidate_count",
        "rejected_candidate_count",
        "missing_query_anchor_after_tool_candidate_count",
        "missing_query_anchor_after_tool_item_count",
        "query_anchor_rejected_with_complete_axes_candidate_count",
        "query_anchor_rejected_with_missing_axes_candidate_count",
        "query_anchor_rejected_without_validated_axes_candidate_count",
    )
    counts = {
        key: _required_non_negative_int(run_id, "query_anchor_tool_acceptance_diagnostic", diagnostic, key)
        for key in count_keys
    }
    if locator is not None:
        for diagnostic_key, locator_key in (
            ("tool_invocation_count", "tool_invocation_count"),
            ("candidate_count", None),
            ("accepted_for_regating_candidate_count", "accepted_candidate_count"),
            ("rejected_candidate_count", "rejected_candidate_count"),
        ):
            locator_count = (
                int(locator.get("accepted_candidate_count") or 0) + int(locator.get("rejected_candidate_count") or 0)
                if locator_key is None
                else int(locator.get(locator_key) or 0)
            )
            if counts[diagnostic_key] != locator_count:
                raise DatasetSchemaError(
                    f"{run_id}: query_anchor_tool_acceptance_diagnostic.{diagnostic_key} mismatch"
                )
    if counts["accepted_for_regating_candidate_count"] + counts["rejected_candidate_count"] != counts["candidate_count"]:
        raise DatasetSchemaError(f"{run_id}: query_anchor_tool_acceptance_diagnostic candidate count mismatch")
    if counts["missing_query_anchor_after_tool_candidate_count"] > counts["rejected_candidate_count"]:
        raise DatasetSchemaError(
            f"{run_id}: query_anchor_tool_acceptance_diagnostic missing-query-anchor count mismatch"
        )
    axis_bucket_total = (
        counts["query_anchor_rejected_with_complete_axes_candidate_count"]
        + counts["query_anchor_rejected_with_missing_axes_candidate_count"]
        + counts["query_anchor_rejected_without_validated_axes_candidate_count"]
    )
    if axis_bucket_total != counts["missing_query_anchor_after_tool_candidate_count"]:
        raise DatasetSchemaError(f"{run_id}: query_anchor_tool_acceptance_diagnostic axis bucket count mismatch")
    allowed_source_hints = set(QUERY_EVIDENCE_SOURCE_FAMILY_HINTS) | {"unknown"}
    source_hint_counts = diagnostic.get("source_family_hint_counts")
    if not isinstance(source_hint_counts, Mapping):
        raise DatasetSchemaError(
            f"{run_id}: query_anchor_tool_acceptance_diagnostic.source_family_hint_counts must be present"
        )
    for hint in source_hint_counts:
        if _clean(hint) not in allowed_source_hints:
            raise DatasetSchemaError(
                f"{run_id}: query_anchor_tool_acceptance_diagnostic.source_family_hint_counts invalid"
            )
    query_task_counts = diagnostic.get("query_task_counts")
    if not isinstance(query_task_counts, Mapping):
        raise DatasetSchemaError(f"{run_id}: query_anchor_tool_acceptance_diagnostic.query_task_counts must be present")
    for task in query_task_counts:
        if _clean(task) not in QUERY_EVIDENCE_TASKS | {"unknown"}:
            raise DatasetSchemaError(f"{run_id}: query_anchor_tool_acceptance_diagnostic.query_task_counts invalid")
    for transition_counts_key in ("gate_flip_direction_counts", "residual_transition_counts"):
        transition_counts = diagnostic.get(transition_counts_key)
        if not isinstance(transition_counts, Mapping):
            raise DatasetSchemaError(
                f"{run_id}: query_anchor_tool_acceptance_diagnostic.{transition_counts_key} must be present"
            )
        for count in transition_counts.values():
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise DatasetSchemaError(
                    f"{run_id}: query_anchor_tool_acceptance_diagnostic.{transition_counts_key} counts invalid"
                )
    field_presence = diagnostic.get("source_owned_field_presence_on_query_anchor_rejected_candidates")
    if not isinstance(field_presence, Mapping):
        raise DatasetSchemaError(
            f"{run_id}: query_anchor_tool_acceptance_diagnostic.source_owned_field_presence_on_query_anchor_rejected_candidates must be present"
        )
    for value in field_presence.values():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise DatasetSchemaError(
                f"{run_id}: query_anchor_tool_acceptance_diagnostic.source_owned_field_presence_on_query_anchor_rejected_candidates counts invalid"
            )
    top_missing = diagnostic.get("top_missing_query_anchors")
    if not isinstance(top_missing, Sequence) or isinstance(top_missing, (str, bytes)):
        raise DatasetSchemaError(
            f"{run_id}: query_anchor_tool_acceptance_diagnostic.top_missing_query_anchors must be present"
        )
    for entry in top_missing:
        if not isinstance(entry, Mapping) or "anchor" not in entry:
            raise DatasetSchemaError(f"{run_id}: query_anchor_tool_acceptance_diagnostic.top_missing_query_anchors invalid")
        _required_non_negative_int(run_id, "query_anchor_tool_acceptance_diagnostic.top_missing_query_anchors", entry, "candidate_count")
    breakdown = diagnostic.get("missing_query_anchor_after_tool_by_source_family_hint_query_task")
    if not isinstance(breakdown, Sequence) or isinstance(breakdown, (str, bytes)):
        raise DatasetSchemaError(
            f"{run_id}: query_anchor_tool_acceptance_diagnostic.missing_query_anchor_after_tool_by_source_family_hint_query_task must be present"
        )
    for entry in breakdown:
        if not isinstance(entry, Mapping):
            raise DatasetSchemaError(
                f"{run_id}: query_anchor_tool_acceptance_diagnostic.missing_query_anchor_after_tool_by_source_family_hint_query_task invalid"
            )
        source_family_hint = _clean(entry.get("source_family_hint"))
        query_task = _clean(entry.get("query_task"))
        bucket = _clean(entry.get("bucket"))
        if source_family_hint not in allowed_source_hints:
            raise DatasetSchemaError(
                f"{run_id}: query_anchor_tool_acceptance_diagnostic.missing_query_anchor_after_tool_by_source_family_hint_query_task source_family_hint invalid"
            )
        if query_task not in QUERY_EVIDENCE_TASKS | {"unknown"}:
            raise DatasetSchemaError(
                f"{run_id}: query_anchor_tool_acceptance_diagnostic.missing_query_anchor_after_tool_by_source_family_hint_query_task query_task invalid"
            )
        if bucket not in {"missing_query_anchor_after_tool", "other"}:
            raise DatasetSchemaError(
                f"{run_id}: query_anchor_tool_acceptance_diagnostic.missing_query_anchor_after_tool_by_source_family_hint_query_task bucket invalid"
            )
        _required_non_negative_int(
            run_id,
            "query_anchor_tool_acceptance_diagnostic.missing_query_anchor_after_tool_by_source_family_hint_query_task",
            entry,
            "item_count",
        )
    item_summaries = diagnostic.get("item_summaries")
    if not isinstance(item_summaries, Sequence) or isinstance(item_summaries, (str, bytes)):
        raise DatasetSchemaError(f"{run_id}: query_anchor_tool_acceptance_diagnostic.item_summaries must be present")
    for summary in item_summaries:
        if not isinstance(summary, Mapping):
            raise DatasetSchemaError(f"{run_id}: query_anchor_tool_acceptance_diagnostic.item_summaries invalid")
        for key in (
            "item_index",
            "candidate_count",
            "accepted_candidate_count",
            "missing_query_anchor_after_tool_candidate_count",
        ):
            _required_non_negative_int(run_id, "query_anchor_tool_acceptance_diagnostic.item_summaries", summary, key)
        source_family_hint = _clean(summary.get("source_family_hint"))
        query_task = _clean(summary.get("query_task"))
        if source_family_hint not in allowed_source_hints:
            raise DatasetSchemaError(f"{run_id}: query_anchor_tool_acceptance_diagnostic.item_summaries source_family_hint invalid")
        if query_task not in QUERY_EVIDENCE_TASKS | {"unknown"}:
            raise DatasetSchemaError(f"{run_id}: query_anchor_tool_acceptance_diagnostic.item_summaries query_task invalid")
        for list_key in ("remaining_missing_query_anchors", "remaining_missing_validated_required_axes"):
            values = summary.get(list_key)
            if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
                raise DatasetSchemaError(
                    f"{run_id}: query_anchor_tool_acceptance_diagnostic.item_summaries.{list_key} invalid"
                )


def validate_agentic_xlsx_axis_repair_diagnostic(
    run_id: str,
    diagnostic: Mapping[str, Any],
    *,
    locator: Mapping[str, Any] | None = None,
) -> None:
    owner = "agentic_xlsx_axis_repair_diagnostic"
    if not isinstance(diagnostic, Mapping):
        raise DatasetSchemaError(f"{run_id}: {owner} must be present")
    forbidden_keys = sorted(_collect_xlsx_locator_query_anchor_diagnostic_forbidden_keys(diagnostic))
    if forbidden_keys:
        raise DatasetSchemaError(f"{run_id}: {owner} contains forbidden field {forbidden_keys[0]}")
    if diagnostic.get("schema_version") != AGENTIC_XLSX_AXIS_REPAIR_DIAGNOSTIC_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: {owner}.schema_version unsupported")
    if diagnostic.get("axis_inspector_schema_version") != AGENTIC_XLSX_AXIS_INSPECTOR_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: {owner}.axis_inspector_schema_version unsupported")
    if diagnostic.get("repair_explainer_schema_version") != AGENTIC_XLSX_REPAIR_EXPLAINER_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: {owner}.repair_explainer_schema_version unsupported")
    if diagnostic.get("report_only_diagnostic") is not True:
        raise DatasetSchemaError(f"{run_id}: {owner}.report_only_diagnostic must be True")
    if diagnostic.get("official_metric") is not False:
        raise DatasetSchemaError(f"{run_id}: {owner}.official_metric must be False")
    if int(diagnostic.get("official_metric_input_rows") or 0) != 0:
        raise DatasetSchemaError(f"{run_id}: {owner}.official_metric_input_rows must be 0")
    for key in (
        "uses_expected_fields",
        "uses_gold_fields",
        "uses_qrels_or_labels",
        "uses_ids_as_runtime_inputs",
        "uses_file_workbook_title",
        "uses_formula_or_normalized_value",
        "evidence_gate_loosened",
    ):
        if diagnostic.get(key) is not False:
            raise DatasetSchemaError(f"{run_id}: {owner}.{key} must be False")
    count_keys = (
        "candidate_count",
        "inspected_candidate_count",
        "repair_explained_candidate_count",
        "missing_axis_candidate_count",
        "safe_to_simulate_intent_removal_candidate_count",
    )
    counts = {
        key: _required_non_negative_int(run_id, owner, diagnostic, key)
        for key in count_keys
    }
    if locator is not None:
        locator_candidate_count = int(locator.get("accepted_candidate_count") or 0) + int(
            locator.get("rejected_candidate_count") or 0
        )
        if counts["candidate_count"] != locator_candidate_count:
            raise DatasetSchemaError(f"{run_id}: {owner}.candidate_count mismatch")
    if counts["inspected_candidate_count"] != counts["candidate_count"]:
        raise DatasetSchemaError(f"{run_id}: {owner}.inspected_candidate_count mismatch")
    if counts["repair_explained_candidate_count"] > counts["candidate_count"]:
        raise DatasetSchemaError(f"{run_id}: {owner}.repair_explained_candidate_count mismatch")
    family_counts = diagnostic.get("primary_failure_family_counts")
    if not isinstance(family_counts, Mapping):
        raise DatasetSchemaError(f"{run_id}: {owner}.primary_failure_family_counts must be present")
    for family, count in family_counts.items():
        if _clean(family) not in AGENTIC_XLSX_REPAIR_FAILURE_FAMILIES:
            raise DatasetSchemaError(f"{run_id}: {owner}.primary_failure_family_counts unsupported")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise DatasetSchemaError(f"{run_id}: {owner}.primary_failure_family_counts invalid")
    secondary_counts = diagnostic.get("secondary_failure_family_counts")
    if not isinstance(secondary_counts, Mapping):
        raise DatasetSchemaError(f"{run_id}: {owner}.secondary_failure_family_counts must be present")
    for family, count in secondary_counts.items():
        if _clean(family) not in AGENTIC_XLSX_REPAIR_FAILURE_FAMILIES:
            raise DatasetSchemaError(f"{run_id}: {owner}.secondary_failure_family_counts unsupported")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise DatasetSchemaError(f"{run_id}: {owner}.secondary_failure_family_counts invalid")
    missing_axis_counts = diagnostic.get("missing_axis_counts")
    if not isinstance(missing_axis_counts, Mapping):
        raise DatasetSchemaError(f"{run_id}: {owner}.missing_axis_counts must be present")
    for axis, count in missing_axis_counts.items():
        if _clean(axis) not in QUERY_EVIDENCE_AXIS_ORDER:
            raise DatasetSchemaError(f"{run_id}: {owner}.missing_axis_counts unsupported")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise DatasetSchemaError(f"{run_id}: {owner}.missing_axis_counts invalid")
    summaries = diagnostic.get("candidate_summaries")
    if not isinstance(summaries, Sequence) or isinstance(summaries, (str, bytes, bytearray)):
        raise DatasetSchemaError(f"{run_id}: {owner}.candidate_summaries must be present")
    if len(summaries) != counts["repair_explained_candidate_count"]:
        raise DatasetSchemaError(f"{run_id}: {owner}.candidate_summaries count mismatch")
    safe_count = 0
    observed_primary_counts: Counter[str] = Counter()
    observed_missing_axis_candidates = 0
    for summary in summaries:
        if not isinstance(summary, Mapping):
            raise DatasetSchemaError(f"{run_id}: {owner}.candidate_summaries invalid")
        for key in ("item_index", "candidate_index"):
            _required_non_negative_int(run_id, f"{owner}.candidate_summaries", summary, key)
        primary = _clean(summary.get("primary_failure_family"))
        if primary not in AGENTIC_XLSX_REPAIR_FAILURE_FAMILIES:
            raise DatasetSchemaError(f"{run_id}: {owner}.candidate_summaries primary unsupported")
        observed_primary_counts[primary] += 1
        secondary = summary.get("secondary_failure_families")
        if not isinstance(secondary, Sequence) or isinstance(secondary, (str, bytes, bytearray)):
            raise DatasetSchemaError(f"{run_id}: {owner}.candidate_summaries secondary invalid")
        for family in secondary:
            if _clean(family) not in AGENTIC_XLSX_REPAIR_FAILURE_FAMILIES:
                raise DatasetSchemaError(f"{run_id}: {owner}.candidate_summaries secondary unsupported")
        missing_axes = summary.get("missing_axes")
        if not isinstance(missing_axes, Sequence) or isinstance(missing_axes, (str, bytes, bytearray)):
            raise DatasetSchemaError(f"{run_id}: {owner}.candidate_summaries missing_axes invalid")
        cleaned_missing_axes = [_clean(axis) for axis in missing_axes if _clean(axis)]
        for axis in cleaned_missing_axes:
            if axis not in QUERY_EVIDENCE_AXIS_ORDER:
                raise DatasetSchemaError(f"{run_id}: {owner}.candidate_summaries missing_axes unsupported")
        if cleaned_missing_axes:
            observed_missing_axis_candidates += 1
        safe_to_simulate = summary.get("safe_to_simulate_intent_removal")
        if not isinstance(safe_to_simulate, bool):
            raise DatasetSchemaError(f"{run_id}: {owner}.candidate_summaries safe flag invalid")
        if cleaned_missing_axes and (primary == "intent_anchor_only" or safe_to_simulate):
            raise DatasetSchemaError(f"{run_id}: {owner}.candidate_summaries missing axes cannot be solved by intent removal")
        if safe_to_simulate:
            safe_count += 1
    if dict(sorted(observed_primary_counts.items())) != dict(sorted(family_counts.items())):
        raise DatasetSchemaError(f"{run_id}: {owner}.primary_failure_family_counts mismatch")
    if safe_count != counts["safe_to_simulate_intent_removal_candidate_count"]:
        raise DatasetSchemaError(f"{run_id}: {owner}.safe_to_simulate_intent_removal_candidate_count mismatch")
    if observed_missing_axis_candidates > counts["missing_axis_candidate_count"]:
        raise DatasetSchemaError(f"{run_id}: {owner}.missing_axis_candidate_count mismatch")
    validate_agentic_xlsx_regated_simulation_summary(
        run_id,
        diagnostic.get("regated_simulation_summary"),
    )


def validate_agentic_xlsx_regated_simulation_summary(run_id: str, summary: Mapping[str, Any]) -> None:
    owner = "regated_simulation_summary"
    if not isinstance(summary, Mapping):
        raise DatasetSchemaError(f"{run_id}: {owner} must be present")
    forbidden_keys = sorted(_collect_xlsx_locator_query_anchor_diagnostic_forbidden_keys(summary))
    if forbidden_keys:
        raise DatasetSchemaError(f"{run_id}: {owner} contains forbidden field {forbidden_keys[0]}")
    if summary.get("schema_version") != AGENTIC_XLSX_REGATED_CANDIDATE_SIMULATOR_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: {owner}.schema_version unsupported")
    if summary.get("report_only_diagnostic") is not True:
        raise DatasetSchemaError(f"{run_id}: {owner}.report_only_diagnostic must be True")
    if summary.get("official_metric") is not False:
        raise DatasetSchemaError(f"{run_id}: {owner}.official_metric must be False")
    if int(summary.get("official_metric_input_rows") or 0) != 0:
        raise DatasetSchemaError(f"{run_id}: {owner}.official_metric_input_rows must be 0")
    if summary.get("quality_delta_claim_supported") is not False:
        raise DatasetSchemaError(f"{run_id}: {owner}.quality_delta_claim_supported must be False")
    for key in (
        "simulated_candidate_count",
        "would_be_accepted_by_existing_gate_candidate_count",
        "query_anchor_to_axis_materialization_candidate_count",
        "query_anchor_to_accepted_candidate_count",
    ):
        _required_non_negative_int(run_id, owner, summary, key)
    approved = _agentic_xlsx_optional_clean_tuple(summary.get("approved_removed_tokens"))
    protected = _agentic_xlsx_optional_clean_tuple(summary.get("protected_tokens_preserved"))
    if set(approved) & set(protected):
        raise DatasetSchemaError(f"{run_id}: {owner}.approved_removed_tokens overlap protected tokens")
    reason_counts = summary.get("simulated_rejection_reason_counts")
    if not isinstance(reason_counts, Mapping):
        raise DatasetSchemaError(f"{run_id}: {owner}.simulated_rejection_reason_counts must be present")
    for reason, count in reason_counts.items():
        if not _clean(reason):
            raise DatasetSchemaError(f"{run_id}: {owner}.simulated_rejection_reason_counts invalid")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise DatasetSchemaError(f"{run_id}: {owner}.simulated_rejection_reason_counts invalid")
    simulations = summary.get("simulations")
    if not isinstance(simulations, Sequence) or isinstance(simulations, (str, bytes, bytearray)):
        raise DatasetSchemaError(f"{run_id}: {owner}.simulations must be present")
    if len(simulations) != int(summary.get("simulated_candidate_count") or 0):
        raise DatasetSchemaError(f"{run_id}: {owner}.simulated_candidate_count mismatch")
    observed_reason_counts: Counter[str] = Counter()
    accepted_count = 0
    axis_shift_count = 0
    accepted_shift_count = 0
    for simulation in simulations:
        if not isinstance(simulation, Mapping):
            raise DatasetSchemaError(f"{run_id}: {owner}.simulations invalid")
        for key in ("item_index", "candidate_index"):
            _required_non_negative_int(run_id, f"{owner}.simulations", simulation, key)
        original = _clean(simulation.get("original_rejection_reason"))
        simulated = _clean(simulation.get("simulated_rejection_reason"))
        if not original or not simulated:
            raise DatasetSchemaError(f"{run_id}: {owner}.simulations rejection reasons invalid")
        observed_reason_counts[simulated] += 1
        sim_approved = _agentic_xlsx_optional_clean_tuple(simulation.get("approved_removed_tokens"))
        sim_protected = _agentic_xlsx_optional_clean_tuple(simulation.get("protected_tokens_preserved"))
        if set(sim_approved) & set(sim_protected):
            raise DatasetSchemaError(f"{run_id}: {owner}.simulations approved/protected overlap")
        if not set(sim_approved).issubset(set(approved)) or not set(protected).issubset(set(sim_protected)):
            raise DatasetSchemaError(f"{run_id}: {owner}.simulations token mismatch")
        axis_status = simulation.get("axis_status_after_simulation")
        if not isinstance(axis_status, Mapping):
            raise DatasetSchemaError(f"{run_id}: {owner}.simulations axis status missing")
        missing_axes = _agentic_xlsx_optional_clean_tuple(axis_status.get("missing_axes"))
        remaining_anchors = _agentic_xlsx_optional_clean_tuple(axis_status.get("remaining_missing_query_anchors"))
        if any(axis not in QUERY_EVIDENCE_AXIS_ORDER for axis in missing_axes):
            raise DatasetSchemaError(f"{run_id}: {owner}.simulations missing axes unsupported")
        would_accept = simulation.get("would_be_accepted_by_existing_gate")
        if not isinstance(would_accept, bool):
            raise DatasetSchemaError(f"{run_id}: {owner}.simulations accept flag invalid")
        if would_accept:
            accepted_count += 1
            if missing_axes or remaining_anchors or simulated != "accepted_after_regating":
                raise DatasetSchemaError(f"{run_id}: {owner}.simulations acceptance invalid")
        if original == "missing_query_anchor_after_tool" and simulated == "missing_validated_required_axes_after_tool":
            axis_shift_count += 1
        if original == "missing_query_anchor_after_tool" and simulated == "accepted_after_regating":
            accepted_shift_count += 1
    if dict(sorted(observed_reason_counts.items())) != dict(sorted(reason_counts.items())):
        raise DatasetSchemaError(f"{run_id}: {owner}.simulated_rejection_reason_counts mismatch")
    if accepted_count != int(summary.get("would_be_accepted_by_existing_gate_candidate_count") or 0):
        raise DatasetSchemaError(f"{run_id}: {owner}.accepted count mismatch")
    if axis_shift_count != int(summary.get("query_anchor_to_axis_materialization_candidate_count") or 0):
        raise DatasetSchemaError(f"{run_id}: {owner}.axis shift count mismatch")
    if accepted_shift_count != int(summary.get("query_anchor_to_accepted_candidate_count") or 0):
        raise DatasetSchemaError(f"{run_id}: {owner}.accepted shift count mismatch")


def validate_xlsx_locator_tool_execute_once(run_id: str, locator: Mapping[str, Any]) -> None:
    if locator.get("schema_version") != XLSX_LOCATOR_TOOL_EXECUTE_ONCE_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.schema_version unsupported")
    if locator.get("enabled") is not True:
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.enabled must be True")
    if locator.get("report_only_diagnostic") is not True:
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.report_only_diagnostic must be True")
    if locator.get("official_metric") is not False:
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.official_metric must be False")
    for key in (
        "official_metric_input_rows",
        "official_metric_input_rows_created",
        "official_metric_input_rows_consumed",
    ):
        if int(locator.get(key) or 0) != 0:
            raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.{key} must be 0")
    if locator.get("tool_name") != XLSX_LOCATOR_TOOL_NAME:
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.tool_name unsupported")
    for key in ("decisions", "tool_uses", "candidates"):
        if key in locator:
            raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.{key} must stay in RunStore")
    record_meta = locator.get("run_record")
    if not isinstance(record_meta, Mapping) or record_meta.get("record_type") != "XlsxLocatorRunRecord":
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.run_record must identify XlsxLocatorRunRecord")
    if record_meta.get("serializer") != "compact_report_projection":
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once must be a compact report projection")
    run_store = locator.get("run_store")
    if not isinstance(run_store, Mapping):
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.run_store must be present")
    if run_store.get("backend") != XLSX_LOCATOR_RUN_STORE_BACKEND:
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.run_store.backend unsupported")
    if not _clean(run_store.get("path")).endswith(XLSX_LOCATOR_RUN_STORE_FILENAME):
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.run_store.path must end with run.sqlite")
    required_report_tables = set(XLSX_LOCATOR_RUN_STORE_TABLES) - {"tool_candidate_period_cells"}
    missing_tables = sorted(required_report_tables - set(_as_list(run_store.get("tables"))))
    if missing_tables:
        raise DatasetSchemaError(
            f"{run_id}: xlsx_locator_tool_execute_once.run_store missing table {missing_tables[0]}"
        )
    guardrail_status = locator.get("guardrail_status")
    if not isinstance(guardrail_status, Mapping):
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.guardrail_status must be present")
    for key in (
        "raw_xlsx_query_time_parsing_used",
        "gold_or_qrels_or_label_or_expected_used",
        "retrieved_context_only_citation_promoted",
        "evidence_gate_loosened",
        "official_metric",
    ):
        if guardrail_status.get(key) is not False:
            raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.guardrail_status.{key} must be False")
    if guardrail_status.get("report_only_diagnostic") is not True:
        raise DatasetSchemaError(
            f"{run_id}: xlsx_locator_tool_execute_once.guardrail_status.report_only_diagnostic must be True"
        )
    for key in (
        "official_metric_input_rows",
        "official_metric_input_rows_created",
        "official_metric_input_rows_consumed",
    ):
        if int(guardrail_status.get(key) or 0) != 0:
            raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.guardrail_status.{key} must be 0")
    if _as_list(locator.get("forbidden_input_fields_used")):
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.forbidden_input_fields_used must be empty")
    if locator.get("raw_xlsx_query_time_parsing_used") is not False:
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.raw_xlsx_query_time_parsing_used must be False")
    if locator.get("gold_or_qrels_or_label_or_expected_used") is not False:
        raise DatasetSchemaError(
            f"{run_id}: xlsx_locator_tool_execute_once.gold_or_qrels_or_label_or_expected_used must be False"
        )
    diagnostic = locator.get("query_anchor_tool_acceptance_diagnostic")
    if not isinstance(diagnostic, Mapping):
        raise DatasetSchemaError(
            f"{run_id}: xlsx_locator_tool_execute_once.query_anchor_tool_acceptance_diagnostic must be present"
        )
    validate_xlsx_locator_query_anchor_tool_acceptance_diagnostic(run_id, diagnostic, locator=locator)
    axis_repair_diagnostic = locator.get("agentic_xlsx_axis_repair_diagnostic")
    if not isinstance(axis_repair_diagnostic, Mapping):
        raise DatasetSchemaError(
            f"{run_id}: xlsx_locator_tool_execute_once.agentic_xlsx_axis_repair_diagnostic must be present"
        )
    validate_agentic_xlsx_axis_repair_diagnostic(run_id, axis_repair_diagnostic, locator=locator)
    eligible_failed = int(locator.get("eligible_failed_row_count") or 0)
    tool_invocations = int(locator.get("tool_invocation_count") or 0)
    accepted = int(locator.get("accepted_candidate_count") or 0)
    rejected = int(locator.get("rejected_candidate_count") or 0)
    if min(eligible_failed, tool_invocations, accepted, rejected) < 0:
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once counts must be non-negative")
    if tool_invocations != eligible_failed:
        raise DatasetSchemaError(
            f"{run_id}: xlsx_locator_tool_execute_once must execute one tool call per eligible failed row"
        )
    before_gate = locator.get("before_gate") if isinstance(locator.get("before_gate"), Mapping) else {}
    after_gate = locator.get("after_gate") if isinstance(locator.get("after_gate"), Mapping) else {}
    gate_delta = locator.get("gate_delta") if isinstance(locator.get("gate_delta"), Mapping) else {}
    expected_allowed_delta = int(after_gate.get("allowed_answer_count") or 0) - int(
        before_gate.get("allowed_answer_count") or 0
    )
    if int(gate_delta.get("allowed_answer_count_delta") or 0) != expected_allowed_delta:
        raise DatasetSchemaError(f"{run_id}: xlsx_locator_tool_execute_once.gate_delta mismatch")


def _resolve_xlsx_locator_run_store_path(path: Any) -> Path:
    path_text = _clean(path)
    if not path_text:
        return Path()
    path_obj = Path(path_text)
    if path_obj.is_absolute():
        return path_obj
    return ROOT / path_obj


def validate_xlsx_locator_run_store(
    run_id: str,
    locator: Mapping[str, Any],
    *,
    run_store_path: Path | str | None = None,
) -> None:
    run_store = locator.get("run_store") if isinstance(locator.get("run_store"), Mapping) else {}
    path = Path(run_store_path) if run_store_path is not None else _resolve_xlsx_locator_run_store_path(run_store.get("path"))
    if not path.exists():
        raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore missing: {_report_path_value(path)}")
    required_columns = {
        "runs": {
            "run_id",
            "dataset_slug",
            "collection",
            "schema_version",
            "schema_versions_json",
            "backend",
            "tool_name",
            "enabled",
            "report_only_diagnostic",
            "official_metric",
            "official_metric_input_rows",
            "anchor_classifier_model",
            "anchor_classifier_prompt_version",
            "anchor_classifier_raw_payload_written",
            "required_anchor_summary_json",
            "query_planner_summary_json",
            "guardrail_summary_json",
            "record_json",
        },
        "items": {
            "source_family_hint",
            "query_task",
            "planner_status",
            "row_filters_json",
            "target_axis_json",
            "validated_required_axes_json",
        },
        "selected_evidence": {
            "cell",
            "row_index_1based",
            "row_label",
            "column_label",
            "target_column",
            "header_path",
            "table_id",
            "display_value",
            "source_row_context_source_atom_id",
            "source_row_context_doc_id",
        },
        "tool_invocations": {
            "best_candidate_missing_validated_required_axes_json",
            "complete_validated_axis_candidate_count",
            "matched_validated_required_axes_json",
            "remaining_missing_validated_required_axes_json",
            "source_row_context_candidate_count",
            "source_row_context_doc_identity_mismatch_candidate_count",
            "source_row_context_blocked_by_doc_identity_mismatch",
            "validated_axis_split_across_candidates",
        },
        "tool_candidates": {
            "locator_text_source",
            "input_fields_used_json",
            "matched_validated_required_axes_json",
            "missing_validated_required_axes_json",
            "accepted_for_regating",
            "rejection_reason",
            "source_row_context_source_atom_id",
            "source_row_context_doc_id",
        },
        "tool_candidate_period_cells": {
            "item_index",
            "candidate_index",
            "period_cell_index",
            "source_atom_id",
            "doc_id",
            "sheet",
            "cell_range",
            "cell",
            "row_index_1based",
            "row_label",
            "column_label",
            "raw_value",
            "parsed_date",
            "year",
            "month",
            "day",
            "provenance_policy",
        },
    }
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        optional_tables = {"tool_candidate_period_cells"}
        missing_tables = sorted((set(XLSX_LOCATOR_RUN_STORE_TABLES) - optional_tables) - tables)
        if missing_tables:
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore missing table {missing_tables[0]}")
        for table, columns in required_columns.items():
            if table not in tables:
                continue
            present = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            missing_columns = sorted(columns - present)
            if missing_columns:
                raise DatasetSchemaError(
                    f"{run_id}: xlsx locator RunStore {table} missing column {missing_columns[0]}"
                )
        count_tables = [table for table in XLSX_LOCATOR_RUN_STORE_TABLES if table in tables]
        counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in count_tables}
        if counts["runs"] != 1:
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore must contain one runs row")
        item_count = counts["items"]
        if counts["gate_results"] != item_count * 2:
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore gate_results count mismatch")
        if counts["residuals"] != item_count * 2:
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore residuals count mismatch")
        tool_invocation_count = int(locator.get("tool_invocation_count") or 0)
        if counts["tool_invocations"] != tool_invocation_count:
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore tool_invocations count mismatch")
        candidate_count = int(locator.get("accepted_candidate_count") or 0) + int(
            locator.get("rejected_candidate_count") or 0
        )
        if counts["tool_candidates"] != candidate_count:
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore tool_candidates count mismatch")
        if "tool_candidate_period_cells" in tables:
            for period_cell in conn.execute(
                "SELECT source_atom_id, doc_id, sheet, cell_range, cell, row_index_1based, column_label, "
                "raw_value, parsed_date, year, month, day, provenance_policy FROM tool_candidate_period_cells"
            ):
                for field in (
                    "source_atom_id",
                    "doc_id",
                    "sheet",
                    "cell_range",
                    "cell",
                    "row_index_1based",
                    "column_label",
                    "raw_value",
                    "parsed_date",
                ):
                    if not _clean(period_cell[field]):
                        raise DatasetSchemaError(
                            f"{run_id}: xlsx locator RunStore tool_candidate_period_cells.{field} missing"
                        )
                if _clean(period_cell["provenance_policy"]) != "source_owned_same_row_period_cell_v1":
                    raise DatasetSchemaError(
                        f"{run_id}: xlsx locator RunStore tool_candidate_period_cells.provenance_policy invalid"
                    )
                if (
                    int(period_cell["year"] or 0) <= 0
                    or int(period_cell["month"] or 0) <= 0
                    or int(period_cell["day"] or 0) <= 0
                ):
                    raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore tool_candidate_period_cells date invalid")
        allowed_planner_statuses = {
            "",
            "skipped_no_query",
            "unavailable_deterministic_fallback",
            "error_deterministic_fallback",
            "malformed_payload_deterministic_fallback",
            "empty_after_validation_deterministic_fallback",
            "planned_validated",
        }
        allowed_axes = set(QUERY_EVIDENCE_AXIS_ORDER)
        for item in conn.execute(
            "SELECT item_index, source_family_hint, query_task, planner_status, row_filters_json, "
            "target_axis_json, validated_required_axes_json FROM items"
        ):
            item_index = int(item["item_index"] or 0)
            source_family_hint = _clean(item["source_family_hint"]).lower()
            if source_family_hint and source_family_hint not in QUERY_EVIDENCE_SOURCE_FAMILY_HINTS:
                raise DatasetSchemaError(
                    f"{run_id}: xlsx locator RunStore items.source_family_hint invalid at item {item_index}"
                )
            query_task = _clean(item["query_task"]).lower()
            if query_task and query_task not in QUERY_EVIDENCE_TASKS:
                raise DatasetSchemaError(
                    f"{run_id}: xlsx locator RunStore items.query_task invalid at item {item_index}"
                )
            planner_status = _clean(item["planner_status"])
            if planner_status not in allowed_planner_statuses:
                raise DatasetSchemaError(
                    f"{run_id}: xlsx locator RunStore items.planner_status invalid at item {item_index}"
                )
            row_filters = _parse_jsonish(item["row_filters_json"])
            if not isinstance(row_filters, Mapping):
                raise DatasetSchemaError(
                    f"{run_id}: xlsx locator RunStore items.row_filters_json invalid at item {item_index}"
                )
            target_axis = _parse_jsonish(item["target_axis_json"])
            if not isinstance(target_axis, Mapping):
                raise DatasetSchemaError(
                    f"{run_id}: xlsx locator RunStore items.target_axis_json invalid at item {item_index}"
                )
            value_type = _clean(target_axis.get("value_type")).lower() if target_axis else ""
            if value_type and value_type not in QUERY_EVIDENCE_VALUE_TYPES:
                raise DatasetSchemaError(
                    f"{run_id}: xlsx locator RunStore items.target_axis.value_type invalid at item {item_index}"
                )
            validated_axes = _parse_jsonish(item["validated_required_axes_json"])
            if not isinstance(validated_axes, Sequence) or isinstance(validated_axes, (str, bytes, bytearray)):
                raise DatasetSchemaError(
                    f"{run_id}: xlsx locator RunStore items.validated_required_axes_json invalid at item {item_index}"
                )
            for axis in validated_axes:
                if _clean(axis) not in allowed_axes:
                    raise DatasetSchemaError(
                        f"{run_id}: xlsx locator RunStore items.validated_required_axes invalid at item {item_index}"
                    )
            if planner_status == "planned_validated" and not validated_axes:
                raise DatasetSchemaError(
                    f"{run_id}: xlsx locator RunStore items.validated_required_axes empty at item {item_index}"
                )
        run = conn.execute(
            "SELECT run_id, schema_version, backend, tool_name, official_metric, official_metric_input_rows, "
            "anchor_classifier_raw_payload_written, required_anchor_summary_json, query_planner_summary_json, record_json "
            "FROM runs"
        ).fetchone()
        if not run:
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore runs row missing")
        if run["run_id"] != run_id:
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore run_id mismatch")
        if run["schema_version"] != XLSX_LOCATOR_TOOL_EXECUTE_ONCE_SCHEMA_VERSION:
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore schema_version mismatch")
        if run["backend"] != XLSX_LOCATOR_RUN_STORE_BACKEND:
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore backend mismatch")
        if run["tool_name"] != XLSX_LOCATOR_TOOL_NAME:
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore tool_name mismatch")
        if int(run["official_metric"] or 0) != 0 or int(run["official_metric_input_rows"] or 0) != 0:
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore official metric fields must stay closed")
        if int(run["anchor_classifier_raw_payload_written"] or 0) != 0:
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore anchor classifier raw payload must stay closed")
        required_anchor_summary = _parse_jsonish(run["required_anchor_summary_json"])
        if not isinstance(required_anchor_summary, Mapping):
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore required_anchor_summary_json invalid")
        query_planner_summary = _parse_jsonish(run["query_planner_summary_json"])
        if not isinstance(query_planner_summary, Mapping):
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore query_planner_summary_json invalid")
        record_json = _parse_jsonish(run["record_json"])
        if not isinstance(record_json, Mapping):
            raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore record_json invalid")
        for key in ("tool_invocation_count", "accepted_candidate_count", "rejected_candidate_count"):
            if int(record_json.get(key) or 0) != int(locator.get(key) or 0):
                raise DatasetSchemaError(f"{run_id}: xlsx locator RunStore record_json {key} mismatch")
        for invocation in conn.execute(
            "SELECT item_index, source_row_context_doc_identity_mismatch_candidate_count "
            "FROM tool_invocations WHERE source_row_context_doc_identity_mismatch_candidate_count > 0"
        ):
            mismatch_count = int(invocation["source_row_context_doc_identity_mismatch_candidate_count"] or 0)
            item_index = int(invocation["item_index"] or 0)
            candidate_diagnostic_count = conn.execute(
                "SELECT COUNT(*) FROM tool_candidates "
                "WHERE item_index = ? AND source_row_context_source_atom_id != '' "
                "AND source_row_context_doc_id != ''",
                (item_index,),
            ).fetchone()[0]
            if int(candidate_diagnostic_count or 0) < mismatch_count:
                raise DatasetSchemaError(
                    f"{run_id}: xlsx locator RunStore doc mismatch diagnostics missing at item {item_index}"
                )
    finally:
        conn.close()


def _heuristic_risk_entry(
    *,
    rule_id: str,
    classification: str,
    status: str,
    description: str,
    input_policy: str,
    scope: str,
    diagnostic_only: bool = True,
    uses_source_derived_fields: bool = False,
    uses_query_text_only: bool = False,
    uses_query_id_or_row_id_or_target_id: bool = False,
    uses_expected_answer_or_evidence: bool = False,
    uses_qrels_or_labels: bool = False,
    per_row_alias_table: bool = False,
    composer_or_gate_loosening_for_single_residual: bool = False,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "classification": classification,
        "status": status,
        "description": description,
        "input_policy": input_policy,
        "scope": scope,
        "diagnostic_only": diagnostic_only,
        "official_metric_input": False,
        "uses_source_derived_fields": uses_source_derived_fields,
        "uses_query_text_only": uses_query_text_only,
        "uses_query_id_or_row_id_or_target_id": uses_query_id_or_row_id_or_target_id,
        "uses_expected_answer_or_evidence": uses_expected_answer_or_evidence,
        "uses_qrels_or_labels": uses_qrels_or_labels,
        "per_row_alias_table": per_row_alias_table,
        "composer_or_gate_loosening_for_single_residual": composer_or_gate_loosening_for_single_residual,
    }


def _active_candidate_rule(summary: Mapping[str, Any]) -> dict[str, Any]:
    index = summary.get("index_retrieval_config") if isinstance(summary.get("index_retrieval_config"), Mapping) else {}
    retrieval_surface = summary.get("retrieval_surface") if isinstance(summary.get("retrieval_surface"), Mapping) else {}
    policy = _clean(summary.get("candidate_generation_input_policy") or index.get("candidate_generation_input_policy"))
    boundary = _clean(summary.get("active_retrieval_service_boundary") or index.get("active_retrieval_service_boundary"))
    selected_surface = _clean(retrieval_surface.get("selected"))
    if index.get("adapter") == "jsonl_context_override":
        return _heuristic_risk_entry(
            rule_id="precomputed_context_fixture",
            classification="diagnostic_probe_only",
            status="active",
            description="Precomputed context rows are used only as deterministic test/report input.",
            input_policy=policy or "precomputed_fixture_rows_not_retrieval_improvement",
            scope="whole_run",
        )
    if boundary == "weaviate" or "weaviate" in json.dumps(index, ensure_ascii=False).casefold():
        return _heuristic_risk_entry(
            rule_id="source_derived_route_selected_index_policy",
            classification="source_derived_index_feature",
            status="active",
            description="Route-selected retrieval uses source-owned taxonomy/index metadata, not eval-row fields.",
            input_policy=policy or WEAVIATE_CANDIDATE_INPUT_POLICY,
            scope="whole_corpus",
            uses_source_derived_fields=True,
            uses_query_text_only=True,
        )
    return _heuristic_risk_entry(
        rule_id="active_query_text_candidate_generation",
        classification="query_text_only_reformulation",
        status="active",
        description="Active candidate generation is constrained to query text and source-derived retrieval state.",
        input_policy=policy or "query_text_only_no_gold_qrels_labels_ids_or_baseline_topk",
        scope=selected_surface or "whole_run",
        uses_query_text_only=True,
    )


def build_heuristic_risk_ledger(summary: Mapping[str, Any]) -> dict[str, Any]:
    config = summary.get("generator_config") if isinstance(summary.get("generator_config"), Mapping) else {}
    gate = summary.get("evidence_gate") if isinstance(summary.get("evidence_gate"), Mapping) else {}
    corpus_audit = summary.get("corpus_coverage_audit") if isinstance(summary.get("corpus_coverage_audit"), Mapping) else {}
    agentic_planner = (
        summary.get("agentic_planner_dry_run")
        if isinstance(summary.get("agentic_planner_dry_run"), Mapping)
        else {}
    )
    agentic_execute_once = (
        summary.get("agentic_planner_execute_once")
        if isinstance(summary.get("agentic_planner_execute_once"), Mapping)
        else {}
    )
    entries: list[dict[str, Any]] = [
        _heuristic_risk_entry(
            rule_id="global_query_text_normalization",
            classification="global_normalization",
            status="active",
            description="Shared query/token normalization is applied globally without row-specific aliases.",
            input_policy="query_text_only_global_normalization_no_eval_row_fields",
            scope="whole_run",
            uses_query_text_only=True,
        ),
        _active_candidate_rule(summary),
    ]
    if config.get("selected_evidence_composer_invoked"):
        entries.append(
            _heuristic_risk_entry(
                rule_id="selected_evidence_composer",
                classification="query_text_only_reformulation",
                status="active",
                description="The selected-evidence composer formulates answers only from query text plus selected SourceAtom/EvidenceBundle evidence.",
                input_policy=_clean(config.get("selected_evidence_composer_input_policy"))
                or SELECTED_EVIDENCE_COMPOSER_INPUT_POLICY,
                scope="all_eval_items",
                uses_query_text_only=True,
                uses_source_derived_fields=True,
            )
        )
    if _clean(gate.get("evidence_gate_mode")) not in {"", "off"}:
        entries.append(
            _heuristic_risk_entry(
                rule_id="evidence_gate_enforcement",
                classification="diagnostic_probe_only",
                status="active",
                description="Evidence gate blocks or abstains unsupported outputs without loosening composer behavior for a residual row.",
                input_policy="selected_evidence_validation_only_no_expected_or_gold_fields",
                scope="all_eval_items",
                uses_source_derived_fields=True,
            )
        )
    if corpus_audit.get("enabled"):
        entries.append(
            _heuristic_risk_entry(
                rule_id="corpus_coverage_audit_probe",
                classification="diagnostic_probe_only",
                status="active",
                description="Target-anchor probes are report-only diagnostics after the main run and are not candidate generation or metric inputs.",
                input_policy=_clean(corpus_audit.get("candidate_generation_input_policy"))
                or "main_eval_unchanged_report_only_diagnostic_probe",
                scope="post_run_audit",
                uses_query_text_only=True,
            )
        )
    if agentic_planner.get("planner_enabled"):
        entries.append(
            _heuristic_risk_entry(
                rule_id="agentic_planner_dry_run",
                classification="diagnostic_probe_only",
                status="active",
                description="Planner dry-run classifies post-gate failures and records one proposed action per failed row without executing retrieval, tools, or LLM retry.",
                input_policy=_clean(agentic_planner.get("candidate_generation_input_policy"))
                or "query_text_and_public_gate_diagnostics_only_no_ids_expected_qrels_labels_baseline_or_legacy_outputs",
                scope="failed_rows_after_gate",
                uses_query_text_only=True,
                uses_source_derived_fields=True,
            )
        )
    if agentic_execute_once.get("planner_enabled"):
        entries.append(
            _heuristic_risk_entry(
                rule_id="agentic_planner_execute_once",
                classification="diagnostic_probe_only",
                status="active",
                description=(
                    "Planner execute-once runs only one bounded failed-row action: route-selected probe, "
                    "source-derived locator context, or selected-evidence LLM rewrite, then reuses the unchanged evidence gate."
                ),
                input_policy=_clean(agentic_execute_once.get("candidate_generation_input_policy"))
                or "query_text_and_public_gate_diagnostics_only_no_ids_expected_qrels_labels_baseline_or_legacy_outputs",
                scope="failed_rows_after_gate",
                uses_query_text_only=True,
                uses_source_derived_fields=True,
            )
        )
    entries.append(
        _heuristic_risk_entry(
            rule_id="agentic_loop_review",
            classification="diagnostic_probe_only",
            status="active",
            description="Broader agent-loop readiness is a report-only review and does not open production, official metrics, raw payloads, or gate loosening.",
            input_policy="report_diagnostics_only_no_eval_row_shortcuts_no_raw_payloads",
            scope="post_run_review",
            uses_source_derived_fields=True,
        )
    )
    entries.extend(
        [
            _heuristic_risk_entry(
                rule_id="forbidden_query_id_row_id_target_id_aliasing",
                classification="forbidden_eval_row_shortcut",
                status="rejected",
                description="Reject query_id, row_id, or target_id based aliasing or expansion.",
                input_policy="rejected_for_active_retrieval_and_generation",
                scope="all_eval_items",
                uses_query_id_or_row_id_or_target_id=True,
            ),
            _heuristic_risk_entry(
                rule_id="forbidden_expected_answer_evidence_qrels_label_expansion",
                classification="forbidden_eval_row_shortcut",
                status="rejected",
                description="Reject expected answer/evidence/qrels/label based query expansion.",
                input_policy="rejected_for_active_retrieval_and_generation",
                scope="all_eval_items",
                uses_expected_answer_or_evidence=True,
                uses_qrels_or_labels=True,
            ),
            _heuristic_risk_entry(
                rule_id="forbidden_per_row_alias_table",
                classification="forbidden_eval_row_shortcut",
                status="rejected",
                description="Reject per-row alias tables, including aliases for text_namu_v2_0014.",
                input_policy="rejected_for_active_retrieval_and_generation",
                scope="all_eval_items",
                per_row_alias_table=True,
            ),
            _heuristic_risk_entry(
                rule_id="forbidden_single_residual_gate_or_composer_loosening",
                classification="forbidden_eval_row_shortcut",
                status="rejected",
                description="Reject composer or gate loosening for a single residual row.",
                input_policy="rejected_for_active_retrieval_and_generation",
                scope="all_eval_items",
                composer_or_gate_loosening_for_single_residual=True,
            ),
        ]
    )
    active_entries = [entry for entry in entries if _clean(entry.get("status")) == "active"]
    active_counts = Counter(_clean(entry.get("classification")) for entry in active_entries)
    return {
        "schema_version": HEURISTIC_RISK_LEDGER_SCHEMA_VERSION,
        "enabled": True,
        "report_only_diagnostic": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "allowed_classifications": list(HEURISTIC_RISK_ALLOWED_CLASSIFICATIONS),
        "all_classifications": list(HEURISTIC_RISK_ALL_CLASSIFICATIONS),
        "entries": entries,
        "active_entry_count": len(active_entries),
        "rejected_entry_count": len(entries) - len(active_entries),
        "active_classification_counts": dict(sorted(active_counts.items())),
        "forbidden_eval_row_shortcut_active": any(
            _clean(entry.get("classification")) == "forbidden_eval_row_shortcut"
            or any(entry.get(flag) is True for flag in HEURISTIC_RISK_FORBIDDEN_ACTIVE_FLAGS)
            for entry in active_entries
        ),
        "gold_or_qrels_mutation": False,
        "source_registry_mutation": False,
        "denominator_mutation": False,
        "current_alias_mutation": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }


def _query_count_per_item(summary: Mapping[str, Any], item_count: int) -> float | None:
    for value in (
        summary.get("weaviate_query_count_per_item"),
        (summary.get("backend_comparison") or {}).get("weaviate_query_count_per_item")
        if isinstance(summary.get("backend_comparison"), Mapping)
        else None,
    ):
        if isinstance(value, (int, float)):
            return round(float(value), 6)
    backend = summary.get("retrieval_backend") if isinstance(summary.get("retrieval_backend"), Mapping) else {}
    query_count = backend.get("query_count")
    if isinstance(query_count, (int, float)) and item_count:
        return round(float(query_count) / float(item_count), 6)
    return None


def _metric_continuity_guardrail_flags(summary: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "gold_or_qrels_mutation": bool(summary.get("gold_or_qrels_mutation")),
        "expected_fields_used_for_candidate_generation": bool(summary.get("expected_fields_used_for_candidate_generation")),
        "query_id_used_for_candidate_generation": bool(summary.get("query_id_used_for_candidate_generation")),
        "row_id_used_for_candidate_generation": bool(summary.get("row_id_used_for_candidate_generation")),
        "target_id_used_for_candidate_generation": bool(summary.get("target_id_used_for_candidate_generation")),
        "qrels_used_for_candidate_generation": bool(summary.get("qrels_used_for_candidate_generation")),
        "answerability_labels_used_for_candidate_generation": bool(summary.get("answerability_labels_used_for_candidate_generation")),
        "gate_uses_expected_fields": bool(summary.get("gate_uses_expected_fields")),
        "gate_uses_gold_fields": bool(summary.get("gate_uses_gold_fields")),
        "evidence_gate_retrieval_loop_triggered": bool(summary.get("evidence_gate_retrieval_loop_triggered")),
    }


def build_metric_continuity_checkpoint(summary: Mapping[str, Any]) -> dict[str, Any]:
    gate = summary.get("evidence_gate") if isinstance(summary.get("evidence_gate"), Mapping) else {}
    item_count = int(gate.get("item_count") or summary.get("total_item_count") or len(_as_list(summary.get("items"))))
    allowed = int(gate.get("allowed_answer_count") or 0)
    blocked = int(gate.get("unsupported_answer_blocked_count") or 0) + int(
        gate.get("would_block_unsupported_answer_count") or 0
    )
    status_counts = {
        "sufficient": int(gate.get("sufficient_evidence_package_count") or 0),
        "insufficient": int(gate.get("insufficient_evidence_package_count") or 0),
        "conflicting": int(gate.get("conflicting_evidence_package_count") or 0),
        "unresolved": int(gate.get("unresolved_evidence_package_count") or 0),
    }
    backend = summary.get("backend_comparison") if isinstance(summary.get("backend_comparison"), Mapping) else {}
    latency = {
        "elapsed_ms": summary.get("elapsed_ms"),
        "bm25_latency_ms_p50": backend.get("bm25_latency_ms_p50"),
        "bm25_latency_ms_p95": backend.get("bm25_latency_ms_p95"),
        "vector_latency_ms_p50": backend.get("vector_latency_ms_p50"),
        "vector_latency_ms_p95": backend.get("vector_latency_ms_p95"),
        "hybrid_latency_ms_p50": backend.get("hybrid_latency_ms_p50"),
        "hybrid_latency_ms_p95": backend.get("hybrid_latency_ms_p95"),
        "weaviate_query_latency_ms_p50": summary.get("weaviate_query_latency_ms_p50") or backend.get("hybrid_latency_ms_p50"),
        "weaviate_query_latency_ms_p95": summary.get("weaviate_query_latency_ms_p95") or backend.get("hybrid_latency_ms_p95"),
    }
    guardrail_flags = _metric_continuity_guardrail_flags(summary)
    return {
        "schema_version": METRIC_CONTINUITY_CHECKPOINT_SCHEMA_VERSION,
        "enabled": True,
        "report_only_diagnostic": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "gate_outcome": {
            "item_count": item_count,
            "allowed_answer_count": allowed,
            "blocked_or_would_block_count": blocked,
            "allowed_over_item_count": f"{allowed}/{item_count}" if item_count else "0/0",
        },
        "selected_evidence_gate_outcome_preserved": bool(item_count == 6 and allowed == 5 and blocked == 1),
        "evidence_package_status_counts": status_counts,
        "unsupported_answer_rate_before_gate": gate.get("unsupported_answer_rate_before_gate"),
        "unsupported_answer_rate_after_gate": gate.get("unsupported_answer_rate_after_gate"),
        "citation_supported_count": int(gate.get("citation_supported_count") or 0),
        "retrieved_context_only_diagnostic_count": int(
            gate.get("citation_retrieved_context_only_diagnostic_count") or 0
        ),
        "selected_evidence_citation_precision": _portfolio_selected_evidence_citation_precision(gate),
        "query_count_per_item": _query_count_per_item(summary, item_count),
        "latency": latency,
        "residual_taxonomy": _portfolio_residual_taxonomy(summary),
        "guardrail_mutation_flags": guardrail_flags,
        "guardrail_mutation_detected": any(guardrail_flags.values()),
        "residual_resolution_assessment": (
            "residual_remains_general_retrieval_limitation"
            if blocked
            else "no_selected_evidence_residual_blocked_by_gate"
        ),
        "residual_policy": "do_not_apply_row_specific_alias_or_single_residual_gate_loosening",
    }


def _agentic_loop_review_guardrail_flags(summary: Mapping[str, Any]) -> dict[str, bool]:
    guardrails = summary.get("guardrails") if isinstance(summary.get("guardrails"), Mapping) else {}
    planner = (
        summary.get("agentic_planner_execute_once")
        if isinstance(summary.get("agentic_planner_execute_once"), Mapping)
        else summary.get("agentic_planner_dry_run")
        if isinstance(summary.get("agentic_planner_dry_run"), Mapping)
        else {}
    )
    planner_flags = planner.get("guardrail_mutation_flags") or planner.get("guardrail_flags")
    if not isinstance(planner_flags, Mapping):
        planner_flags = {}
    return {
        "gold_or_qrels_mutation": bool(guardrails.get("gold_mutation") or guardrails.get("qrels_mutation")),
        "label_mutation": bool(guardrails.get("label_mutation") or guardrails.get("answerability_label_mutation")),
        "expected_answer_or_evidence_mutation": bool(
            guardrails.get("expected_answer_mutation") or guardrails.get("expected_evidence_mutation")
        ),
        "denominator_mutation": bool(guardrails.get("denominator_mutation")),
        "query_id_row_id_target_id_used": bool(
            planner_flags.get("query_id_used_for_planner_selection")
            or planner_flags.get("row_id_used_for_planner_selection")
            or planner_flags.get("target_id_used_for_planner_selection")
        ),
        "expected_qrels_labels_or_baseline_used": bool(
            planner_flags.get("expected_fields_used_for_planner_selection")
            or planner_flags.get("qrels_used_for_planner_selection")
            or planner_flags.get("labels_used_for_planner_selection")
            or planner_flags.get("baseline_topk_or_legacy_outputs_used")
        ),
        "row_specific_alias_or_shortcut_used": bool(planner_flags.get("row_specific_alias_or_shortcut_used")),
        "raw_prompt_payload_written": bool(summary.get("raw_prompt_payload_written") or planner.get("raw_prompt_payload_written")),
        "raw_response_payload_written": bool(
            summary.get("raw_response_payload_written") or planner.get("raw_response_payload_written")
        ),
        "gate_loosened": bool(
            planner_flags.get("gate_loosened") or planner_flags.get("evidence_gate_loosened")
        ),
        "retrieved_context_only_citation_promoted": bool(
            planner_flags.get("retrieved_context_only_citation_promoted")
        ),
        "official_metric": bool(summary.get("official_metric") or planner.get("official_metric")),
        "production_routing_opened": bool(planner_flags.get("production_routing_opened")),
        "protected_namespace_mutation": bool(planner_flags.get("protected_namespace_mutation")),
    }


def build_agentic_loop_review(summary: Mapping[str, Any]) -> dict[str, Any]:
    execute_once = (
        summary.get("agentic_planner_execute_once")
        if isinstance(summary.get("agentic_planner_execute_once"), Mapping)
        else {}
    )
    dry_run = (
        summary.get("agentic_planner_dry_run")
        if isinstance(summary.get("agentic_planner_dry_run"), Mapping)
        else {}
    )
    planner = execute_once or dry_run
    execution = planner.get("planner_execution") if isinstance(planner.get("planner_execution"), Mapping) else {}
    gate_delta = planner.get("gate_delta") if isinstance(planner.get("gate_delta"), Mapping) else {}
    readiness = (
        planner.get("execute_once_readiness")
        if isinstance(planner.get("execute_once_readiness"), Mapping)
        else {}
    )
    quality_improvement_measured = bool(readiness.get("quality_improvement_measured")) or any(
        int(gate_delta.get(key) or 0) > 0
        for key in ("allowed_answer_count_delta", "citation_supported_count_delta")
    )
    dataset_path = _clean(summary.get("dataset_path"))
    dataset_name = Path(dataset_path).name if dataset_path else ""
    index = summary.get("index_retrieval_config") if isinstance(summary.get("index_retrieval_config"), Mapping) else {}
    live_text_gold_metric_measured = bool(
        dataset_name == "gold_queries_text_namu_v2_1_question_gold_v2.csv"
        and _clean(index.get("active_retrieval_service_boundary")) == "weaviate"
    )
    guardrail_flags = _agentic_loop_review_guardrail_flags(summary)
    guardrail_mutation_detected = any(guardrail_flags.values())
    required_before_broader_loop = [
        "fresh_live_text_gold_report_with_weaviate_reachable",
        "human_approved_gold_qrels_answerability_relevance_expected_evidence_denominator_policy",
        "multi_checkpoint_non_fake_quality_improvement_under_unchanged_gate",
        "per_action_budget_and_one_action_per_failed_row_policy_review",
        "retrieved_context_only_citations_remain_diagnostic_only",
    ]
    return {
        "schema_version": AGENTIC_LOOP_REVIEW_SCHEMA_VERSION,
        "enabled": True,
        "review_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "heuristic_risk_class": "diagnostic_probe_only",
        "planner_enabled": bool(planner.get("planner_enabled")),
        "planner_mode": _clean(planner.get("planner_mode")) or "off",
        "planner_version": _clean(planner.get("planner_version")),
        "broader_agent_loop_ready": False,
        "broader_agent_loop_opened": False,
        "production_routing_opened": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "retrieved_context_only_citation_promoted": False,
        "gate_loosened": False,
        "gold_or_qrels_or_labels_or_expected_or_denominator_mutation": False,
        "evidence_gate_required_for_all_actions": True,
        "one_action_per_failed_row_policy": True,
        "official_metric_policy": (
            "official_metric_false_until_human_approved_gold_qrels_answerability_relevance_expected_evidence_denominator_policy"
        ),
        "bounded_action_evidence": {
            "planner_present": bool(planner),
            "planner_mode": _clean(planner.get("planner_mode")) or "off",
            "planner_decision_count": int(planner.get("planner_decision_count") or 0),
            "planner_executed_decision_count": int(planner.get("planner_executed_decision_count") or 0),
            "planner_action_counts": dict(planner.get("planner_action_counts") or {}),
            "planner_failure_class_counts": dict(planner.get("planner_failure_class_counts") or {}),
            "expected_extra_query_count": int(planner.get("planner_expected_extra_query_count") or 0),
            "expected_tool_call_count": int(planner.get("planner_expected_tool_call_count") or 0),
            "expected_llm_retry_count": int(planner.get("planner_expected_llm_retry_count") or 0),
            "expected_memory_lookup_count": int(planner.get("planner_expected_memory_lookup_count") or 0),
            "executed_extra_query_count": int(execution.get("extra_query_count_executed") or 0),
            "executed_tool_call_count": int(execution.get("tool_call_count_executed") or 0),
            "executed_llm_retry_count": int(execution.get("llm_retry_count_executed") or 0),
            "executed_memory_lookup_count": int(planner.get("planner_memory_lookup_count_executed") or 0),
            "gate_delta": dict(gate_delta),
            "quality_improvement_measured": quality_improvement_measured,
            "live_text_gold_metric_measured": live_text_gold_metric_measured,
        },
        "planner_memory_tool_llm_retry_loop_status": {
            "planner_loop_measured": bool(planner),
            "query_probe_executed_count": int(execution.get("extra_query_count_executed") or 0),
            "tool_use_executed_count": int(execution.get("tool_call_count_executed") or 0),
            "llm_retry_executed_count": int(execution.get("llm_retry_count_executed") or 0),
            "run_local_memory_lookup_executed_count": int(planner.get("planner_memory_lookup_count_executed") or 0),
            "quality_improvement_measured": quality_improvement_measured,
        },
        "guardrail_mutation_flags": guardrail_flags,
        "guardrail_mutation_detected": guardrail_mutation_detected,
        "readiness_assessment": (
            "bounded_single_action_quality_delta_observed_but_broader_loop_requires_live_text_gold_multi_checkpoint_evidence"
            if quality_improvement_measured
            else "no_bounded_quality_delta_observed_for_broader_agent_loop_review"
        ),
        "recommendation": "keep_broader_agent_loop_closed_continue_bounded_execute_once_evidence_gate_checkpoints",
        "allowed_next_scope": "bounded_single_action_checkpoints_only",
        "required_before_broader_loop": required_before_broader_loop,
    }


def validate_agentic_loop_review(run_id: str, review: Mapping[str, Any]) -> None:
    if review.get("schema_version") != AGENTIC_LOOP_REVIEW_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: agentic_loop_review.schema_version unsupported")
    if review.get("review_only") is not True:
        raise DatasetSchemaError(f"{run_id}: agentic_loop_review.review_only must be True")
    if review.get("official_metric") is not False:
        raise DatasetSchemaError(f"{run_id}: agentic_loop_review.official_metric must be False")
    if int(review.get("official_metric_input_rows") or 0) != 0:
        raise DatasetSchemaError(f"{run_id}: agentic_loop_review.official_metric_input_rows must be 0")
    for key in (
        "broader_agent_loop_ready",
        "broader_agent_loop_opened",
        "production_routing_opened",
        "raw_prompt_payload_written",
        "raw_response_payload_written",
        "retrieved_context_only_citation_promoted",
        "gate_loosened",
        "gold_or_qrels_or_labels_or_expected_or_denominator_mutation",
    ):
        if review.get(key) is not False:
            raise DatasetSchemaError(f"{run_id}: agentic_loop_review.{key} must be False")
    if review.get("evidence_gate_required_for_all_actions") is not True:
        raise DatasetSchemaError(f"{run_id}: agentic_loop_review.evidence_gate_required_for_all_actions must be True")
    if review.get("one_action_per_failed_row_policy") is not True:
        raise DatasetSchemaError(f"{run_id}: agentic_loop_review.one_action_per_failed_row_policy must be True")
    if review.get("heuristic_risk_class") != "diagnostic_probe_only":
        raise DatasetSchemaError(f"{run_id}: agentic_loop_review.heuristic_risk_class must be diagnostic_probe_only")
    flags = review.get("guardrail_mutation_flags")
    if not isinstance(flags, Mapping):
        raise DatasetSchemaError(f"{run_id}: agentic_loop_review.guardrail_mutation_flags must be present")
    for key, value in flags.items():
        if value is not False:
            raise DatasetSchemaError(f"{run_id}: agentic_loop_review.guardrail_mutation_flags.{key} must be False")
    if review.get("guardrail_mutation_detected") is not False:
        raise DatasetSchemaError(f"{run_id}: agentic_loop_review.guardrail_mutation_detected must be False")
    required = _as_list(review.get("required_before_broader_loop"))
    if "fresh_live_text_gold_report_with_weaviate_reachable" not in required:
        raise DatasetSchemaError(
            f"{run_id}: agentic_loop_review.required_before_broader_loop must include live text-gold evidence"
        )
    if review.get("recommendation") != (
        "keep_broader_agent_loop_closed_continue_bounded_execute_once_evidence_gate_checkpoints"
    ):
        raise DatasetSchemaError(f"{run_id}: agentic_loop_review.recommendation must keep broader loop closed")


def _portfolio_lane_summary(label: str, path: str, summary: Mapping[str, Any]) -> dict[str, Any]:
    config = summary.get("generator_config") if isinstance(summary.get("generator_config"), Mapping) else {}
    artifact = summary.get("artifact_contract") if isinstance(summary.get("artifact_contract"), Mapping) else {}
    index = summary.get("index_retrieval_config") if isinstance(summary.get("index_retrieval_config"), Mapping) else {}
    gate = _portfolio_gate_summary(summary)
    return {
        "label": label,
        "run_id": _clean(summary.get("run_id")),
        "report_path": path,
        "provider": _clean(config.get("answer_composer_provider") or config.get("generator_provider") or config.get("provider")),
        "selected_evidence_composer_invoked": bool(config.get("selected_evidence_composer_invoked")),
        "selected_evidence_citation_format": _clean(config.get("selected_evidence_citation_format")),
        "selected_evidence_composer_retry_mode": _clean(config.get("selected_evidence_composer_retry_mode")) or "off",
        "local_llm_generation_available": bool(config.get("local_llm_generation_available")),
        "local_llm_status_counts": dict(config.get("local_llm_status_counts") or {}),
        "retry_status_counts": dict(config.get("selected_evidence_composer_retry_status_counts") or {}),
        "active_retrieval_service_boundary": _clean(index.get("active_retrieval_service_boundary")),
        "retrieval_route_mode": _clean(index.get("retrieval_route_mode")),
        "rollback_key": _clean(index.get("rollback_key")),
        "emitted_files_report_only": bool(artifact.get("single_artifact_default")),
        "portfolio_sidecar_written": bool(artifact.get("portfolio_experiment_sidecar_written")),
        "raw_prompt_payload_written": bool(summary.get("raw_prompt_payload_written")),
        "raw_response_payload_written": bool(summary.get("raw_response_payload_written")),
        "gate": gate,
        "citation_precision_against_selected_evidence": _portfolio_selected_evidence_citation_precision(gate),
        "residual_failure_taxonomy": _portfolio_residual_taxonomy(summary),
    }


def _portfolio_answer_diff_rows(
    baseline_label: str,
    baseline_summary: Mapping[str, Any],
    current_label: str,
    current_summary: Mapping[str, Any],
) -> list[dict[str, Any]]:
    baseline_items = _portfolio_report_items(baseline_summary)
    current_items = _portfolio_report_items(current_summary)
    rows: list[dict[str, Any]] = []
    for item_id in sorted(set(baseline_items) | set(current_items)):
        before = baseline_items.get(item_id, {})
        after = current_items.get(item_id, {})
        before_answer = _portfolio_answer_preview(before)
        after_answer = _portfolio_answer_preview(after)
        before_citations = _portfolio_citation_snapshot(before)
        after_citations = _portfolio_citation_snapshot(after)
        rows.append(
            {
                "id": item_id,
                "baseline_label": baseline_label,
                "current_label": current_label,
                "answer_changed": before_answer["answer_sha256"] != after_answer["answer_sha256"],
                "baseline_answer": before_answer,
                "current_answer": after_answer,
                "citation_changed": before_citations["citation_identity_hash"]
                != after_citations["citation_identity_hash"]
                or before_citations["formatted_citation_hash"] != after_citations["formatted_citation_hash"],
                "baseline_citations": before_citations,
                "current_citations": after_citations,
                "baseline_gate_decision": _clean(before.get("answer_gate_decision")),
                "current_gate_decision": _clean(after.get("answer_gate_decision")),
                "baseline_abstention_reason": _clean(
                    (before.get("evidence_gate") if isinstance(before.get("evidence_gate"), Mapping) else {}).get(
                        "abstention_reason"
                    )
                ),
                "current_abstention_reason": _clean(
                    (after.get("evidence_gate") if isinstance(after.get("evidence_gate"), Mapping) else {}).get(
                        "abstention_reason"
                    )
                ),
            }
        )
    return rows


def _portfolio_gate_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    before_gate = _portfolio_gate_summary(before)
    after_gate = _portfolio_gate_summary(after)
    fields = (
        "allowed_answer_count",
        "abstained_count",
        "unsupported_answer_blocked_count",
        "would_abstain_count",
        "would_block_unsupported_answer_count",
        "citation_supported_count",
        "citation_retrieved_context_only_diagnostic_count",
    )
    return {
        "before": before_gate,
        "after": after_gate,
        "delta": {
            field: int(after_gate.get(field) or 0) - int(before_gate.get(field) or 0)
            for field in fields
        },
        "unsupported_answer_rate_after_gate_delta": (
            round(float(after_gate["unsupported_answer_rate_after_gate"]) - float(before_gate["unsupported_answer_rate_after_gate"]), 6)
            if isinstance(after_gate.get("unsupported_answer_rate_after_gate"), (int, float))
            and isinstance(before_gate.get("unsupported_answer_rate_after_gate"), (int, float))
            else None
        ),
    }


def _portfolio_lane_mode_key(lane: Mapping[str, Any]) -> str:
    return "|".join(
        [
            _clean(lane.get("provider")),
            _clean(lane.get("selected_evidence_citation_format")),
            _clean(lane.get("selected_evidence_composer_retry_mode")) or "off",
        ]
    )


def _portfolio_diagnostic_enforce_pairs(lanes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Mapping[str, Any]]] = {}
    for lane in lanes:
        mode = _clean((lane.get("gate") or {}).get("evidence_gate_mode"))
        if mode not in {"diagnostic", "enforce"}:
            continue
        grouped.setdefault(_portfolio_lane_mode_key(lane), {})[mode] = lane
    pairs: list[dict[str, Any]] = []
    for key, by_mode in sorted(grouped.items()):
        diagnostic = by_mode.get("diagnostic")
        enforce = by_mode.get("enforce")
        if not diagnostic or not enforce:
            continue
        diagnostic_gate = diagnostic.get("gate") if isinstance(diagnostic.get("gate"), Mapping) else {}
        enforce_gate = enforce.get("gate") if isinstance(enforce.get("gate"), Mapping) else {}
        pairs.append(
            {
                "lane_key": key,
                "diagnostic_label": diagnostic.get("label"),
                "enforce_label": enforce.get("label"),
                "diagnostic_after_gate_rate": diagnostic_gate.get("unsupported_answer_rate_after_gate"),
                "enforce_after_gate_rate": enforce_gate.get("unsupported_answer_rate_after_gate"),
                "unsupported_after_gate_delta": (
                    round(
                        float(enforce_gate["unsupported_answer_rate_after_gate"])
                        - float(diagnostic_gate["unsupported_answer_rate_after_gate"]),
                        6,
                    )
                    if isinstance(enforce_gate.get("unsupported_answer_rate_after_gate"), (int, float))
                    and isinstance(diagnostic_gate.get("unsupported_answer_rate_after_gate"), (int, float))
                    else None
                ),
                "blocked_delta": int(enforce_gate.get("unsupported_answer_blocked_count") or 0)
                - int(diagnostic_gate.get("unsupported_answer_blocked_count") or 0),
                "abstained_delta": int(enforce_gate.get("abstained_count") or 0)
                - int(diagnostic_gate.get("abstained_count") or 0),
            }
        )
    return pairs


def build_portfolio_experiment_comparison(
    *,
    comparison_reports: Sequence[Mapping[str, Any]],
    current_summary: Mapping[str, Any],
) -> dict[str, Any]:
    current_label = "current"
    all_reports: list[dict[str, Any]] = [dict(report) for report in comparison_reports]
    all_reports.append(
        {
            "label": current_label,
            "path": _report_path_value(current_summary.get("artifact_paths", {}).get("report_json"))
            if isinstance(current_summary.get("artifact_paths"), Mapping)
            else "",
            "summary": current_summary,
        }
    )
    lanes = [
        _portfolio_lane_summary(_clean(report.get("label")), _clean(report.get("path")), report.get("summary") or {})
        for report in all_reports
        if isinstance(report.get("summary"), Mapping)
    ]
    baseline = all_reports[0] if all_reports else {"label": current_label, "summary": current_summary}
    baseline_label = _clean(baseline.get("label")) or "baseline"
    baseline_summary = baseline.get("summary") if isinstance(baseline.get("summary"), Mapping) else {}
    pairwise_diffs: list[dict[str, Any]] = []
    for report in all_reports[1:]:
        summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
        label = _clean(report.get("label")) or "comparison"
        pairwise_diffs.append(
            {
                "baseline_label": baseline_label,
                "current_label": label,
                "gate_delta": _portfolio_gate_delta(baseline_summary, summary),
                "answer_diffs": _portfolio_answer_diff_rows(baseline_label, baseline_summary, label, summary),
            }
        )
    return {
        "schema_version": PORTFOLIO_COMPARISON_SCHEMA_VERSION,
        "enabled": True,
        "non_production": True,
        "report_only_contract": "embedded_in_report_json_no_portfolio_sidecar",
        "portfolio_experiment_sidecar_written": False,
        "comparison_input_policy": "post_run_report_json_only_not_generation_input_no_gold_qrels_labels_or_denominator_mutation",
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "baseline_label": baseline_label,
        "current_run_id": current_summary.get("run_id"),
        "lane_count": len(lanes),
        "lanes": lanes,
        "diagnostic_vs_enforce_pairs": _portfolio_diagnostic_enforce_pairs(lanes),
        "pairwise_diffs": pairwise_diffs,
        "residual_failure_taxonomy_by_lane": {
            _clean(lane.get("label")): dict(lane.get("residual_failure_taxonomy") or {}) for lane in lanes
        },
        "next_experiment_recommendations": [
            "prefer deterministic selected-evidence composer while local LLM remains less gate-compatible",
            "use comparison evidence to design the explicit portfolio sidecar behind a future flag",
            "do not mutate gold, qrels, labels, answerability, expected fields, denominator, source registry, or current",
        ],
    }


def _portfolio_md_value(value: Any) -> str:
    if value is None:
        return ""
    text = _clean(value)
    return text.replace("|", "\\|")


def render_portfolio_experiment_summary(comparison: Mapping[str, Any]) -> str:
    lanes = [lane for lane in _as_list(comparison.get("lanes")) if isinstance(lane, Mapping)]
    diffs = [diff for diff in _as_list(comparison.get("pairwise_diffs")) if isinstance(diff, Mapping)]
    lines = [
        "# Non-Production Selected-Evidence Portfolio Experiment",
        "",
        "This sidecar is an explicit non-production portfolio experiment artifact. It is not production readiness, not an official metric, and not promotion evidence.",
        "",
        f"- Comparison schema: `{comparison.get('schema_version')}`",
        f"- Current run: `{comparison.get('current_run_id')}`",
        f"- Lane count: `{comparison.get('lane_count')}`",
        "- Sidecar policy: `explicit_flag_required_sidecar_from_embedded_comparison`",
        f"- Comparison source policy: `{comparison.get('report_only_contract')}`",
        f"- Raw prompt payload written: `{comparison.get('raw_prompt_payload_written')}`",
        f"- Raw response payload written: `{comparison.get('raw_response_payload_written')}`",
        "",
        "## Gate Before/After",
        "",
        "| Lane | Provider | Mode | Unsupported before | Unsupported after | Unsupported answer blocked count | Abstain count | Citation precision against selected evidence | Retrieved-context-only citation count |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for lane in lanes:
        gate = lane.get("gate") if isinstance(lane.get("gate"), Mapping) else {}
        lines.append(
            "| "
            + " | ".join(
                [
                    _portfolio_md_value(lane.get("label")),
                    _portfolio_md_value(lane.get("provider")),
                    _portfolio_md_value(gate.get("evidence_gate_mode")),
                    _portfolio_md_value(gate.get("unsupported_answer_rate_before_gate")),
                    _portfolio_md_value(gate.get("unsupported_answer_rate_after_gate")),
                    _portfolio_md_value(gate.get("unsupported_answer_blocked_count")),
                    _portfolio_md_value(gate.get("abstained_count")),
                    _portfolio_md_value(lane.get("citation_precision_against_selected_evidence")),
                    _portfolio_md_value(gate.get("citation_retrieved_context_only_diagnostic_count")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Answer Diff",
            "",
            "| Baseline | Current | Changed answers | Example changed item | Baseline answer preview | Current answer preview |",
            "|---|---|---:|---|---|---|",
        ]
    )
    for diff in diffs:
        answer_diffs = [row for row in _as_list(diff.get("answer_diffs")) if isinstance(row, Mapping)]
        changed = [row for row in answer_diffs if row.get("answer_changed")]
        example = changed[0] if changed else (answer_diffs[0] if answer_diffs else {})
        baseline_answer = example.get("baseline_answer") if isinstance(example.get("baseline_answer"), Mapping) else {}
        current_answer = example.get("current_answer") if isinstance(example.get("current_answer"), Mapping) else {}
        lines.append(
            "| "
            + " | ".join(
                [
                    _portfolio_md_value(diff.get("baseline_label")),
                    _portfolio_md_value(diff.get("current_label")),
                    str(len(changed)),
                    _portfolio_md_value(example.get("id")),
                    _portfolio_md_value(baseline_answer.get("answer_preview")),
                    _portfolio_md_value(current_answer.get("answer_preview")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Citation Diff",
            "",
            "| Baseline | Current | Changed citations | Retrieved-context-only delta | Supported citation delta |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for diff in diffs:
        answer_diffs = [row for row in _as_list(diff.get("answer_diffs")) if isinstance(row, Mapping)]
        changed_citations = sum(1 for row in answer_diffs if isinstance(row, Mapping) and row.get("citation_changed"))
        gate_delta = diff.get("gate_delta") if isinstance(diff.get("gate_delta"), Mapping) else {}
        delta = gate_delta.get("delta") if isinstance(gate_delta.get("delta"), Mapping) else {}
        lines.append(
            "| "
            + " | ".join(
                [
                    _portfolio_md_value(diff.get("baseline_label")),
                    _portfolio_md_value(diff.get("current_label")),
                    str(changed_citations),
                    _portfolio_md_value(delta.get("citation_retrieved_context_only_diagnostic_count")),
                    _portfolio_md_value(delta.get("citation_supported_count")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Residual Failure Taxonomy",
            "",
            "| Lane | Residual taxonomy |",
            "|---|---|",
        ]
    )
    taxonomy = comparison.get("residual_failure_taxonomy_by_lane") if isinstance(
        comparison.get("residual_failure_taxonomy_by_lane"), Mapping
    ) else {}
    for lane_label, lane_taxonomy in taxonomy.items():
        if isinstance(lane_taxonomy, Mapping):
            rendered = ", ".join(f"{key}={value}" for key, value in sorted(lane_taxonomy.items()))
        else:
            rendered = ""
        lines.append(f"| {_portfolio_md_value(lane_label)} | {_portfolio_md_value(rendered)} |")

    lines.extend(
        [
            "",
            "## Diagnostic/Enforce Pairs",
            "",
            "| Lane key | Diagnostic | Enforce | Unsupported after delta | Blocked delta | Abstain delta |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    for pair in _as_list(comparison.get("diagnostic_vs_enforce_pairs")):
        if not isinstance(pair, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _portfolio_md_value(pair.get("lane_key")),
                    _portfolio_md_value(pair.get("diagnostic_label")),
                    _portfolio_md_value(pair.get("enforce_label")),
                    _portfolio_md_value(pair.get("unsupported_after_gate_delta")),
                    _portfolio_md_value(pair.get("blocked_delta")),
                    _portfolio_md_value(pair.get("abstained_delta")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Next Experiment Recommendations",
            "",
        ]
    )
    for recommendation in _as_list(comparison.get("next_experiment_recommendations")):
        if _clean(recommendation):
            lines.append(f"- {_clean(recommendation)}")
    lines.extend(
        [
            "",
            "Guardrails: no gold/qrels/labels/answerability/expected/denominator/source-registry/current mutation, no production claim, no official metric claim, and no raw prompt/response payload artifacts.",
        ]
    )
    return "\n".join(lines) + "\n"


def _git_marker() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        ).stdout
        return {
            "commit": commit or "unavailable",
            "working_tree_dirty": bool(status.strip()),
            "working_tree_marker": "dirty" if status.strip() else "clean",
        }
    except Exception as exc:
        return {"commit": "unavailable", "working_tree_marker": f"unavailable:{type(exc).__name__}"}


def _artifact_path(summary: Mapping[str, Any], key: str) -> str:
    artifact_paths = summary.get("artifact_paths")
    if isinstance(artifact_paths, Mapping):
        return _clean(artifact_paths.get(key))
    return ""


def _evidence_resolution_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = summary.get("diagnostic_metrics") if isinstance(summary.get("diagnostic_metrics"), Mapping) else {}
    provisional = summary.get("provisional_metrics") if isinstance(summary.get("provisional_metrics"), Mapping) else {}
    keys = [
        "expected_evidence_resolution_enabled",
        "expected_evidence_resolution_scope",
        "expected_evidence_row_count",
        "expected_evidence_id_present_count",
        "expected_evidence_id_missing_count",
        "expected_evidence_id_resolved_exact_count",
        "expected_evidence_id_resolved_candidate_count",
        "expected_evidence_id_unresolved_count",
        "expected_evidence_resolution_candidate_count",
        "expected_evidence_resolution_high_confidence_count",
        "expected_evidence_resolution_medium_confidence_count",
        "expected_evidence_resolution_low_confidence_count",
        "expected_evidence_resolution_review_only_count",
        "expected_evidence_full_corpus_candidate_count",
        "expected_evidence_full_corpus_high_confidence_count",
        "expected_evidence_full_corpus_medium_confidence_count",
        "expected_evidence_full_corpus_low_confidence_count",
        "expected_evidence_full_corpus_review_only_count",
        "expected_evidence_full_corpus_resolved_candidate_count",
        "expected_evidence_full_corpus_collision_count",
        "expected_evidence_full_corpus_unresolved_count",
        "gold_or_qrels_mutation",
        "human_decision_fields_filled_by_codex",
    ]
    metric_names = [
        "resolved_evidence_available_rate",
        f"resolved_evidence_recall@{int(summary.get('top_k') or DEFAULT_TOP_K_VALUES[-1])}_provisional",
        "citation_matches_resolved_evidence_precision_provisional",
        "citation_matches_resolved_evidence_recall_provisional",
        "e2e_rag_success_resolved_evidence_provisional",
    ]
    return {
        "enabled": bool(diagnostics.get("expected_evidence_resolution_enabled")),
        "scope": diagnostics.get("expected_evidence_resolution_scope"),
        "full_corpus_candidate_count": diagnostics.get("expected_evidence_full_corpus_candidate_count", 0),
        "full_corpus_resolved_candidate_count": diagnostics.get(
            "expected_evidence_full_corpus_resolved_candidate_count",
            0,
        ),
        "full_corpus_collision_count": diagnostics.get("expected_evidence_full_corpus_collision_count", 0),
        "gold_or_qrels_mutation": bool(diagnostics.get("gold_or_qrels_mutation")),
        "human_decision_fields_filled_by_codex": bool(diagnostics.get("human_decision_fields_filled_by_codex")),
        **{key: diagnostics.get(key) for key in keys if key in diagnostics},
        "artifact_paths": {
            "evidence_resolution_candidates_jsonl": _artifact_path(summary, "evidence_resolution_candidates_jsonl"),
            "evidence_resolution_review_md": _artifact_path(summary, "evidence_resolution_review_md"),
        },
        "provisional_metrics": _metrics_subset(provisional, metric_names),
    }


def _evidence_mapping_packet_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = summary.get("diagnostic_metrics") if isinstance(summary.get("diagnostic_metrics"), Mapping) else {}
    keys = [
        "evidence_mapping_packet_enabled",
        "evidence_mapping_packet_row_count",
        "evidence_mapping_packet_item_count",
        "evidence_mapping_packet_candidate_count",
        "evidence_mapping_packet_likely_accept_count",
        "evidence_mapping_packet_possible_match_count",
        "evidence_mapping_packet_review_needed_count",
        "evidence_mapping_packet_likely_reject_count",
        "evidence_mapping_packet_p0_count",
        "evidence_mapping_packet_p1_count",
        "evidence_mapping_packet_p2_count",
        "evidence_mapping_packet_p3_count",
        "evidence_mapping_packet_p4_count",
        "source_metadata_resolved_candidate_count",
        "source_metadata_unresolved_candidate_count",
        "source_metadata_redacted_path_count",
        "human_decision_fields_filled_by_codex",
    ]
    return {
        "enabled": bool(diagnostics.get("evidence_mapping_packet_enabled")),
        **{key: diagnostics.get(key) for key in keys if key in diagnostics},
        "artifact_paths": {
            "evidence_mapping_review_packet_csv": _artifact_path(summary, "evidence_mapping_review_packet_csv"),
            "evidence_mapping_review_packet_jsonl": _artifact_path(summary, "evidence_mapping_review_packet_jsonl"),
            "evidence_mapping_review_packet_md": _artifact_path(summary, "evidence_mapping_review_packet_md"),
            "evidence_mapping_packet_summary_json": _artifact_path(summary, "evidence_mapping_packet_summary_json"),
        },
        "guardrails": {
            "diagnostic_review_packet_only": True,
            "human_decision_fields_filled_by_codex": False,
            "machine_recommendation_not_gold": True,
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
        },
    }


def build_registry_event(summary: Mapping[str, Any]) -> dict[str, Any]:
    validate_actual_rag_guardrails(summary)
    diagnostics = summary.get("diagnostic_metrics") if isinstance(summary.get("diagnostic_metrics"), Mapping) else {}
    top_k = int(summary.get("top_k") or DEFAULT_TOP_K_VALUES[-1])
    event = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "run_id": summary.get("run_id"),
        "generated_at": summary.get("generated_at"),
        "dataset_path": summary.get("dataset_path"),
        "dataset_slug": _summary_dataset_slug(summary),
        "output_dir": summary.get("output_dir"),
        "summary_json": _artifact_path(summary, "summary_json"),
        "markdown_report": _artifact_path(summary, "markdown_report"),
        "items_jsonl": _artifact_path(summary, "items_jsonl"),
        "top_k": summary.get("top_k"),
        "judge_mode": summary.get("judge_mode"),
        "judge_config": summary.get("judge_config"),
        "run_kind": summary.get("run_kind"),
        "total_item_count": summary.get("total_item_count"),
        "strict_metrics_summary": _metrics_subset(
            summary.get("strict_metrics") if isinstance(summary.get("strict_metrics"), Mapping) else {},
            [
                "exact_or_alias_answer_correctness",
                f"evidence_recall@{top_k}",
                "citation_precision",
                "citation_recall",
                "e2e_rag_success_strict",
            ],
        ),
        "provisional_metrics_summary": _metrics_subset(
            summary.get("provisional_metrics") if isinstance(summary.get("provisional_metrics"), Mapping) else {},
            [
                "judged_answer_correctness_provisional",
                f"weak_evidence_match_recall@{top_k}",
                "e2e_rag_success_provisional",
                f"resolved_evidence_recall@{top_k}_provisional",
                "resolved_evidence_available_rate",
                "citation_matches_resolved_evidence_precision_provisional",
                "citation_matches_resolved_evidence_recall_provisional",
                "e2e_rag_success_resolved_evidence_provisional",
            ],
        ),
        "diagnostic_metrics_summary": {
            key: diagnostics.get(key)
            for key in [
                "retrieval_empty_rate",
                "generation_empty_rate",
                "citation_empty_rate",
                "pipeline_error_count",
                "schema_warning_count",
                "gold_missing_count",
                "expected_evidence_id_missing_count",
                "expected_evidence_id_unresolved_count",
                "expected_evidence_id_resolved_candidate_count",
                "expected_evidence_resolution_candidate_count",
                "evidence_mapping_packet_candidate_count",
                "evidence_mapping_packet_likely_accept_count",
                "evidence_mapping_packet_possible_match_count",
                "evidence_mapping_packet_review_needed_count",
                "evidence_mapping_packet_likely_reject_count",
                "source_metadata_resolved_candidate_count",
                "source_metadata_unresolved_candidate_count",
                *sorted(BACKEND_COMPARISON_METRICS),
                *sorted(SURFACE_COMPARISON_METRICS),
            ]
            if key in diagnostics
        },
        "retrieval_backend": summary.get("retrieval_backend"),
        "retrieval_surface": summary.get("retrieval_surface"),
        "retrieval_surface_decision": summary.get("retrieval_surface_decision"),
        "surface_migration": summary.get("surface_migration"),
        "surface_deprecation": summary.get("surface_deprecation"),
        "backend_comparison": summary.get("backend_comparison"),
        "surface_comparison": summary.get("surface_comparison"),
        "gpu_preflight": summary.get("gpu_preflight"),
        "external_vector_db": summary.get("external_vector_db"),
        "evidence_resolution": _evidence_resolution_summary(summary),
        "evidence_mapping_packet": _evidence_mapping_packet_summary(summary),
        "guardrails": summary.get("guardrails"),
        "official_metric_input_rows": summary.get("official_metric_input_rows"),
        "official_metric_input_rows_created": summary.get("official_metric_input_rows_created"),
        "official_metric_input_rows_consumed": summary.get("official_metric_input_rows_consumed"),
        "protected_namespaces_touched": summary.get("protected_namespaces_touched"),
        "raw_prompt_payload_written": summary.get("raw_prompt_payload_written"),
        "raw_response_payload_written": summary.get("raw_response_payload_written"),
        "git": _git_marker(),
        "command": summary.get("command"),
        "elapsed_ms": summary.get("elapsed_ms"),
        "pipeline_error_count": diagnostics.get("pipeline_error_count", 0),
        "schema_warning_count": diagnostics.get("schema_warning_count", 0),
        "comparison_target": (summary.get("comparison") or {}).get("target_run_id")
        if isinstance(summary.get("comparison"), Mapping)
        else None,
        "notes": "nonprod actual-RAG eval infrastructure; not official, product-readiness, promotion, or live-readiness evidence",
        "warnings": sorted((diagnostics.get("failure_category_counts") or {}).keys())
        if isinstance(diagnostics.get("failure_category_counts"), Mapping)
        else [],
    }
    return event


def append_run_registry(summary: Mapping[str, Any], *, registry_path: Path | str) -> dict[str, Any]:
    event = build_registry_event(summary)
    path = Path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def _latest_pointer_payload(summary: Mapping[str, Any]) -> dict[str, Any]:
    validate_actual_rag_guardrails(summary)
    return {
        "schema_version": LATEST_POINTER_SCHEMA_VERSION,
        "run_id": summary.get("run_id"),
        "generated_at": summary.get("generated_at"),
        "dataset_path": summary.get("dataset_path"),
        "dataset_slug": _summary_dataset_slug(summary),
        "run_kind": summary.get("run_kind"),
        "output_dir": summary.get("output_dir"),
        "summary_json": _artifact_path(summary, "summary_json"),
        "markdown_report": _artifact_path(summary, "markdown_report"),
        "items_jsonl": _artifact_path(summary, "items_jsonl"),
        "top_k": summary.get("top_k"),
        "judge_mode": summary.get("judge_mode"),
        "total_item_count": summary.get("total_item_count"),
        "guardrails": summary.get("guardrails"),
        "evidence_resolution": _evidence_resolution_summary(summary),
        "evidence_mapping_packet": _evidence_mapping_packet_summary(summary),
        "notes": "latest pointer only; historical run directories are append-only",
    }


def write_latest_pointers(summary: Mapping[str, Any], *, report_root: Path | str = REPORT_ROOT) -> list[Path]:
    root = Path(report_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = _latest_pointer_payload(summary)
    paths = [root / "latest.json", root / f"latest_{payload['dataset_slug']}.json"]
    for path in paths:
        write_json(path, payload)
    return paths


def _short_result_interpretation(summary: Mapping[str, Any]) -> str:
    comparison = summary.get("comparison")
    if not isinstance(comparison, Mapping) or not comparison.get("target_run_id"):
        return "baseline recorded; no comparison target supplied"
    rows = comparison.get("rows") if isinstance(comparison.get("rows"), list) else []
    regressed = [row for row in rows if isinstance(row, Mapping) and row.get("interpretation") == "regressed"]
    improved = [row for row in rows if isinstance(row, Mapping) and row.get("interpretation") == "improved"]
    denominator_changed = [
        row for row in rows if isinstance(row, Mapping) and row.get("interpretation") == "denominator changed"
    ]
    if regressed:
        return f"comparison recorded with {len(regressed)} regression signal(s); inspect diagnostics before acting"
    if denominator_changed:
        return "comparison recorded with denominator changes; do not overclaim improvement"
    if improved:
        return f"comparison recorded with {len(improved)} improvement signal(s); nonprod diagnostic only"
    return "comparison recorded; no comparable metric changes"


def _next_repair_target(summary: Mapping[str, Any]) -> str:
    diagnostics = summary.get("diagnostic_metrics") if isinstance(summary.get("diagnostic_metrics"), Mapping) else {}
    if int(diagnostics.get("pipeline_error_count") or 0) > 0:
        return "debug_pipeline_errors"
    if int(diagnostics.get("evidence_mapping_packet_review_needed_count") or 0) > 0 or int(
        diagnostics.get("evidence_mapping_packet_likely_reject_count") or 0
    ) > 0:
        return "human_review_evidence_mapping_packet"
    if int(diagnostics.get("source_native_target_span_present_but_not_retrieved_count") or 0) > 0:
        return "repair_source_native_retrieval_ranking_query_formulation"
    if int(diagnostics.get("source_native_target_span_absent_count") or 0) > 0:
        return "repair_source_native_corpus_source_coverage"
    if float(diagnostics.get("retrieval_empty_rate") or 0.0) > 0:
        return "repair_retrieval_empty_queries"
    if int(diagnostics.get("expected_evidence_id_unresolved_count") or 0) > 0:
        return "repair_expected_evidence_id_resolution"
    if int(diagnostics.get("gold_missing_count") or 0) > 0:
        return "human_gold_review_for_missing_expected_fields"
    return "monitor_accumulated_actual_rag_eval_runs"


def append_actual_rag_status_event(
    summary: Mapping[str, Any],
    *,
    status_jsonl_path: Path | str = STATUS_JSONL_PATH,
) -> dict[str, Any]:
    validate_actual_rag_guardrails(summary)
    diagnostics = summary.get("diagnostic_metrics") if isinstance(summary.get("diagnostic_metrics"), Mapping) else {}
    top_k = int(summary.get("top_k") or DEFAULT_TOP_K_VALUES[-1])
    event = {
        "schema_version": STATUS_EVENT_SCHEMA_VERSION,
        "event_type": "actual_rag_eval_run",
        "status": "ACTUAL_RAG_EVAL_RUN_RECORDED_NONPROD",
        "run_id": summary.get("run_id"),
        "generated_at": summary.get("generated_at"),
        "dataset_path": summary.get("dataset_path"),
        "dataset_slug": _summary_dataset_slug(summary),
        "output_dir": summary.get("output_dir"),
        "total_item_count": summary.get("total_item_count"),
        "strict_metrics": _metrics_subset(
            summary.get("strict_metrics") if isinstance(summary.get("strict_metrics"), Mapping) else {},
            ["exact_or_alias_answer_correctness", f"evidence_recall@{top_k}", "e2e_rag_success_strict"],
        ),
        "provisional_metrics": _metrics_subset(
            summary.get("provisional_metrics") if isinstance(summary.get("provisional_metrics"), Mapping) else {},
            ["judged_answer_correctness_provisional", f"weak_evidence_match_recall@{top_k}", "e2e_rag_success_provisional"],
        ),
        "diagnostics": {
            key: diagnostics.get(key)
            for key in [
                "retrieval_empty_rate",
                "generation_empty_rate",
                "citation_empty_rate",
                "pipeline_error_count",
                "schema_warning_count",
                "gold_missing_count",
                "expected_evidence_id_missing_count",
                "expected_evidence_id_unresolved_count",
                "expected_evidence_id_resolved_candidate_count",
                "expected_evidence_resolution_candidate_count",
                "evidence_mapping_packet_candidate_count",
                "evidence_mapping_packet_likely_accept_count",
                "evidence_mapping_packet_possible_match_count",
                "evidence_mapping_packet_review_needed_count",
                "evidence_mapping_packet_likely_reject_count",
                "source_metadata_resolved_candidate_count",
                "source_metadata_unresolved_candidate_count",
                *sorted(BACKEND_COMPARISON_METRICS),
                *sorted(SURFACE_COMPARISON_METRICS),
            ]
            if key in diagnostics
        },
        "retrieval_backend": summary.get("retrieval_backend"),
        "retrieval_surface": summary.get("retrieval_surface"),
        "retrieval_surface_decision": summary.get("retrieval_surface_decision"),
        "surface_migration": summary.get("surface_migration"),
        "surface_deprecation": summary.get("surface_deprecation"),
        "backend_comparison": summary.get("backend_comparison"),
        "surface_comparison": summary.get("surface_comparison"),
        "gpu_preflight": summary.get("gpu_preflight"),
        "external_vector_db": summary.get("external_vector_db"),
        "evidence_id_missing_count": diagnostics.get("expected_evidence_id_missing_count"),
        "evidence_id_unresolved_count": diagnostics.get("expected_evidence_id_unresolved_count"),
        "evidence_id_resolved_candidate_count": diagnostics.get("expected_evidence_id_resolved_candidate_count"),
        "evidence_resolution_candidate_count": diagnostics.get("expected_evidence_resolution_candidate_count"),
        "evidence_resolution": _evidence_resolution_summary(summary),
        "evidence_mapping_packet": _evidence_mapping_packet_summary(summary),
        "guardrails": summary.get("guardrails"),
        "official_metric_input_rows": summary.get("official_metric_input_rows"),
        "official_metric_input_rows_created": summary.get("official_metric_input_rows_created"),
        "official_metric_input_rows_consumed": summary.get("official_metric_input_rows_consumed"),
        "protected_namespaces_touched": summary.get("protected_namespaces_touched"),
        "raw_prompt_payload_written": summary.get("raw_prompt_payload_written"),
        "raw_response_payload_written": summary.get("raw_response_payload_written"),
        "comparison_target": (summary.get("comparison") or {}).get("target_run_id")
        if isinstance(summary.get("comparison"), Mapping)
        else None,
        "short_result_interpretation": _short_result_interpretation(summary),
        "next_suggested_repair_target": _next_repair_target(summary),
    }
    path = Path(status_jsonl_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def _read_json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DatasetSchemaError(f"{path}: expected JSON object")
    return payload


def _load_summary_from_pointer_or_path(path: Path) -> dict[str, Any]:
    if path.is_dir():
        report_json = path / "report.json"
        legacy_summary = path / "rag_eval_summary.json"
        target = report_json if report_json.exists() else legacy_summary
    else:
        target = path
    payload = _read_json_file(target)
    if "summary_json" in payload and "run_id" in payload and "strict_metrics" not in payload:
        target = Path(_clean(payload["summary_json"]))
        payload = _read_json_file(target)
    validate_actual_rag_guardrails(payload)
    return payload


def _registry_rows(registry_path: Path) -> list[dict[str, Any]]:
    if not registry_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in registry_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def resolve_comparison_summary(
    compare_to: str,
    *,
    dataset_path: Path | str,
    report_root: Path | str = REPORT_ROOT,
    registry_path: Path | str | None = None,
) -> tuple[dict[str, Any] | None, str]:
    target = _clean(compare_to)
    if not target:
        return None, ""
    root = Path(report_root)
    registry = Path(registry_path) if registry_path is not None else root / REGISTRY_FILENAME
    slug = dataset_slug_for_path(dataset_path)
    if target == "latest":
        pointer = root / f"latest_{slug}.json"
        if not pointer.exists():
            pointer = root / "latest.json"
        if not pointer.exists():
            return None, "latest_unavailable"
        return _load_summary_from_pointer_or_path(pointer), "latest"
    if target == "previous":
        for row in reversed(_registry_rows(registry)):
            if row.get("dataset_slug") != slug:
                continue
            if row.get("run_kind") != RUN_KIND:
                continue
            summary_path = Path(_clean(row.get("summary_json")))
            if summary_path.exists():
                return _load_summary_from_pointer_or_path(summary_path), "previous"
        return None, "previous_unavailable"
    path = Path(target)
    if not path.exists():
        raise DatasetSchemaError(f"comparison target does not exist: {target}")
    return _load_summary_from_pointer_or_path(path), target


def write_report_index(*, report_root: Path | str = REPORT_ROOT) -> Path:
    root = Path(report_root)
    rows = _registry_rows(root / REGISTRY_FILENAME)
    pointer_paths = sorted(root.glob("latest*.json"))
    lines = [
        "# Actual RAG Eval Runs",
        "",
        "This directory accumulates non-production actual-RAG eval artifacts. Reports are diagnostic infrastructure only: they do not mutate gold/qrels, do not promote official metrics, and do not claim product or live readiness.",
        "",
        "## Latest Pointers",
        "",
        "| Pointer | Run id | Dataset | Summary |",
        "|---|---|---|---|",
    ]
    if pointer_paths:
        for path in pointer_paths:
            try:
                payload = _read_json_file(path)
            except Exception:
                continue
            lines.append(
                f"| `{path.name}` | `{payload.get('run_id')}` | `{payload.get('dataset_slug')}` | `{payload.get('summary_json')}` |"
            )
    else:
        lines.append("| none |  |  |  |")
    lines.extend(
        [
            "",
            "## Recent Runs",
            "",
            "| Generated at | Run id | Dataset | Items | Comparison target | Report |",
            "|---|---|---|---:|---|---|",
        ]
    )
    for row in rows[-12:]:
        lines.append(
            f"| `{row.get('generated_at')}` | `{row.get('run_id')}` | `{row.get('dataset_slug')}` | "
            f"{row.get('total_item_count') or ''} | `{row.get('comparison_target') or ''}` | `{row.get('markdown_report')}` |"
        )
    if not rows:
        lines.append("| none |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Compare Runs",
            "",
            "- Use `python -m ai.scripts.rag_actual_eval ... --append-registry --write-latest --compare-to previous` to compare the new run against the previous registered run for the same dataset slug.",
            "- Use `--compare-to latest` to compare against the current latest pointer before it is updated.",
            "- Denominator changes are called out separately; do not read score movement across changed denominators as quality improvement.",
        ]
    )
    path = root / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _evidence_resolution_config(
    *,
    enabled: bool = True,
    scope: str = "full-corpus",
    max_candidates: int = 5,
    min_score: float = 0.35,
    count_medium: bool = False,
) -> EvidenceResolutionConfig:
    normalized_scope = _clean(scope) or "full-corpus"
    if normalized_scope not in {"retrieved-only", "index-candidate-lookup", "both", "full-corpus", "full-corpus-review-only"}:
        raise DatasetSchemaError(f"unsupported evidence resolution scope: {scope}")
    return EvidenceResolutionConfig(
        enabled=bool(enabled),
        scope=normalized_scope,
        max_candidates=max(1, int(max_candidates)),
        min_score=float(min_score),
        count_medium=bool(count_medium),
    )


def _adapter_is_weaviate_lane(adapter: Any) -> bool:
    if isinstance(adapter, WeaviateSourceAtomAdapter):
        return True
    selected = _clean(getattr(adapter, "selected_backend", "")).casefold()
    requested = _clean(getattr(adapter, "requested_backend", "")).replace("-", "_").casefold()
    return selected.startswith("weaviate_") or requested.startswith("weaviate_")


def _resolution_index_candidates(
    adapter: Any,
    item: EvalItem,
    evidence: ExpectedEvidence,
    *,
    config: EvidenceResolutionConfig,
) -> tuple[list[dict[str, Any]], list[str]]:
    candidates: list[dict[str, Any]] = []
    limitations: list[str] = []
    if config.scope in {"index-candidate-lookup", "both"}:
        if not hasattr(adapter, "evidence_candidates"):
            limitations.append("index_candidate_lookup_unavailable")
        else:
            try:
                candidates.extend(adapter.evidence_candidates(item.query, top_k=config.max_candidates))
            except Exception as exc:
                if _adapter_is_weaviate_lane(adapter):
                    raise
                limitations.append(f"index_candidate_lookup_error:{type(exc).__name__}")
    if config.scope in {"full-corpus", "full-corpus-review-only"}:
        method = getattr(adapter, "full_corpus_evidence_candidates", None)
        if not callable(method):
            limitations.append("full_corpus_source_native_lookup_unavailable")
        else:
            try:
                candidates.extend(method(item, evidence, top_k=config.max_candidates))
            except Exception as exc:
                limitations.append(f"full_corpus_source_native_lookup_error:{type(exc).__name__}")
    if config.scope not in {"index-candidate-lookup", "both", "full-corpus", "full-corpus-review-only"}:
        return [], []
    return [dict(candidate) for candidate in candidates if isinstance(candidate, Mapping)], limitations


def apply_expected_evidence_resolution(
    *,
    items: Sequence[EvalItem],
    raw_outputs: Sequence[Mapping[str, Any]],
    adapter: Any,
    config: EvidenceResolutionConfig,
) -> list[dict[str, Any]]:
    if not config.enabled:
        return [dict(output) for output in raw_outputs]
    outputs_by_id = {_clean(output.get("id")): dict(output) for output in raw_outputs}
    resolver = ExpectedEvidenceResolver(config)
    resolved_outputs: list[dict[str, Any]] = []
    for item in items:
        output = dict(outputs_by_id.get(item.id) or _pipeline_error_output(item, "missing_pipeline_output"))
        contexts = [dict(row) for row in _as_list(output.get("retrieved_contexts")) if isinstance(row, Mapping)]
        all_index_candidates: list[dict[str, Any]] = []
        limitations: list[str] = []
        for evidence in item.expected_evidence:
            candidates, candidate_limitations = _resolution_index_candidates(adapter, item, evidence, config=config)
            all_index_candidates.extend(candidates)
            limitations.extend(candidate_limitations)
        output["expected_evidence_resolution"] = resolver.resolve_item(
            item,
            retrieved_contexts=contexts,
            index_candidates=all_index_candidates,
            limitations=sorted(set(limitations)),
        )
        resolved_outputs.append(output)
    return resolved_outputs


def evidence_resolution_candidate_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        resolution = row.get("expected_evidence_resolution") if isinstance(row.get("expected_evidence_resolution"), Mapping) else {}
        for evidence_row in resolution.get("rows") or []:
            if not isinstance(evidence_row, Mapping):
                continue
            candidates.append(
                {
                    "id": row.get("id"),
                    "query": row.get("query"),
                    "expected_answer": row.get("expected_answer"),
                    "expected_evidence": {
                        "index": evidence_row.get("expected_evidence_index"),
                        "doc_id": evidence_row.get("input_doc_id"),
                        "chunk_id": evidence_row.get("input_chunk_id"),
                        "text": evidence_row.get("input_text"),
                    },
                    "candidates": evidence_row.get("candidates") or [],
                    "selected_candidate": evidence_row.get("selected_candidate"),
                    "id_status": evidence_row.get("id_status"),
                    "resolved": evidence_row.get("resolved"),
                    "confidence": (evidence_row.get("selected_candidate") or {}).get("confidence")
                    if isinstance(evidence_row.get("selected_candidate"), Mapping)
                    else None,
                    "resolution_warnings": evidence_row.get("resolution_warnings") or [],
                }
            )
    return candidates


def render_evidence_resolution_review(summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    candidate_rows = evidence_resolution_candidate_rows(rows)

    def preview(value: Any, limit: int = 120) -> str:
        text = re.sub(r"\s+", " ", _clean(value))
        return text if len(text) <= limit else text[: max(0, limit - 3)].rstrip() + "..."

    lines = [
        "# Expected Evidence Resolution Review",
        "",
        "These mappings are diagnostic and do not mutate gold/qrels.",
        "",
        f"- Run id: `{summary.get('run_id')}`",
        f"- Enabled: `{(summary.get('diagnostic_metrics') or {}).get('expected_evidence_resolution_enabled')}`",
        f"- Scope: `{(summary.get('diagnostic_metrics') or {}).get('expected_evidence_resolution_scope')}`",
        "",
        "## High And Medium Confidence Candidates",
        "",
        "| Item | Evidence preview | Selected doc_id | Selected chunk_id | Confidence | Score | Match reasons |",
        "|---|---|---|---|---|---:|---|",
    ]
    visible = False
    for candidate in candidate_rows:
        selected = candidate.get("selected_candidate") if isinstance(candidate.get("selected_candidate"), Mapping) else {}
        if selected.get("confidence") not in {"high", "medium"}:
            continue
        visible = True
        lines.append(
            f"| `{candidate.get('id')}` | {preview((candidate.get('expected_evidence') or {}).get('text'))} | "
            f"`{selected.get('doc_id')}` | `{selected.get('chunk_id')}` | `{selected.get('confidence')}` | "
            f"{selected.get('score')} | {', '.join(selected.get('match_reasons') or [])} |"
        )
    if not visible:
        lines.append("| none |  |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Unresolved Evidence Rows",
            "",
            "| Item | Query | Expected answer | Evidence preview | Warnings | Top candidate preview |",
            "|---|---|---|---|---|---|",
        ]
    )
    visible = False
    for candidate in candidate_rows:
        if candidate.get("resolved"):
            continue
        visible = True
        top = (candidate.get("candidates") or [{}])[0] if candidate.get("candidates") else {}
        lines.append(
            f"| `{candidate.get('id')}` | {preview(candidate.get('query'))} | {preview(candidate.get('expected_answer'))} | "
            f"{preview((candidate.get('expected_evidence') or {}).get('text'))} | "
            f"{', '.join(candidate.get('resolution_warnings') or [])} | {preview(top.get('text_preview'))} |"
        )
    if not visible:
        lines.append("| none |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Low Confidence Review-Only Candidates",
            "",
            "| Item | Evidence preview | Candidate doc_id | Candidate chunk_id | Score | Match reasons | Preview |",
            "|---|---|---|---|---:|---|---|",
        ]
    )
    visible = False
    for candidate in candidate_rows:
        for row_candidate in candidate.get("candidates") or []:
            if not isinstance(row_candidate, Mapping) or row_candidate.get("confidence") != "low":
                continue
            visible = True
            lines.append(
                f"| `{candidate.get('id')}` | {preview((candidate.get('expected_evidence') or {}).get('text'))} | "
                f"`{row_candidate.get('doc_id')}` | `{row_candidate.get('chunk_id')}` | {row_candidate.get('score')} | "
                f"{', '.join(row_candidate.get('match_reasons') or [])} | {preview(row_candidate.get('text_preview'))} |"
            )
    if not visible:
        lines.append("| none |  |  |  |  |  |  |")
    return "\n".join(lines) + "\n"


def write_evidence_resolution_artifacts(
    *,
    output_dir: Path,
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> tuple[Path, Path]:
    candidates_path = output_dir / "evidence_resolution_candidates.jsonl"
    review_path = output_dir / "evidence_resolution_review.md"
    write_jsonl(candidates_path, evidence_resolution_candidate_rows(rows))
    review_path.write_text(render_evidence_resolution_review(summary, rows), encoding="utf-8")
    return candidates_path, review_path


HUMAN_EVIDENCE_MAPPING_FIELDS = (
    "human_mapping_decision",
    "human_accepted_doc_id",
    "human_accepted_chunk_id",
    "human_evidence_sufficient",
    "human_accept",
    "human_reject_reason",
    "human_expected_answer_override",
    "human_expected_evidence_override",
    "human_answerability_label",
    "human_relevance_label",
    "human_notes",
    "reviewed_by",
    "reviewed_at",
)

EVIDENCE_MAPPING_PACKET_FIELDS = (
    "run_id",
    "item_id",
    "query_id",
    "query",
    "expected_answer",
    "expected_answer_aliases",
    "expected_evidence_index",
    "expected_evidence_text",
    "expected_input_doc_id",
    "expected_input_chunk_id",
    "candidate_rank",
    "candidate_doc_id",
    "candidate_chunk_id",
    "candidate_source_family",
    "candidate_source_kind",
    "candidate_source_title_or_safe_display_name",
    "candidate_score",
    "candidate_confidence",
    "match_type",
    "match_reasons",
    "candidate_match_reasons",
    "candidate_text_preview",
    "candidate_text_hash",
    "candidate_full_text_hash",
    "anchor_hits",
    "candidate_anchor_hits",
    "missing_numeric_or_date_anchors",
    "candidate_missing_numeric_or_date_anchors",
    "candidate_generic_overlap_terms",
    "candidate_non_generic_anchor_overlap_terms",
    "collision_warning",
    "retrieval_rank_if_present",
    "candidate_source",
    "candidate_source_atom_id",
    "source_atom_id",
    "candidate_evidence_bundle_id",
    "search_unit_id",
    "search_view_id",
    "registry_source_identity_hash",
    "manifest_path_kind",
    "source_metadata_resolved",
    "metadata_resolution_warnings",
    "machine_recommendation",
    "machine_recommendation_reason",
    "review_priority",
    "primary_blocker",
    "risk_flags",
    "guardrail_flags",
    "human_decision_fields_filled_by_codex",
    *HUMAN_EVIDENCE_MAPPING_FIELDS,
)


def _source_family_from_text(value: Any) -> str:
    text = _clean(value)
    match = re.match(r"^(TEXT|PDF|XLSX)\s+source\s+text\b", text, flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _expected_source_family(row: Mapping[str, Any]) -> str:
    track = _clean(row.get("source_track") or row.get("track")).casefold()
    if "text" in track:
        return "TEXT"
    if "pdf" in track:
        return "PDF"
    if "xlsx" in track or "excel" in track:
        return "XLSX"
    return ""


def _safe_metadata_from_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    metadata = mapping.get("metadata") if isinstance(mapping.get("metadata"), Mapping) else {}

    def first(*keys: str) -> str:
        for key in keys:
            value = _clean(mapping.get(key))
            if value:
                return value
            value = _clean(metadata.get(key))
            if value:
                return value
        return ""

    warnings: list[str] = []
    risk_flags: list[str] = []
    redacted_path_count = 0
    title = first(
        "source_title",
        "candidate_source_title_or_safe_display_name",
        "safe_display_name",
        "display_name",
        "source_safe_id",
    )
    redacted_title, title_redacted = _redact_pathish_metadata(title)
    if title_redacted:
        redacted_path_count += 1
        risk_flags.append("raw_path_redacted")
    source_family = (
        first("source_family", "family", "track").upper()
        or _source_family_from_text(first("text", "bm25_text", "embedding_text", "text_preview"))
    )
    source_kind = first("source_kind", "unit_type", "candidate_only_payload_role", "kind")
    source_atom_id = first("source_atom_id")
    search_unit_id = first("search_unit_id", "chunk_id")
    search_view_id = first("search_view_id", "payload_id")
    identity_hash = first("registry_source_identity_hash", "provenance_hash", "source_text_sha256")
    for key in ("source_path", "local_path", "file_path", "raw_path", "path"):
        raw_value = first(key)
        if not raw_value:
            continue
        redacted, was_redacted = _redact_pathish_metadata(raw_value)
        if was_redacted:
            redacted_path_count += 1
            risk_flags.append("raw_path_redacted")
            warnings.append(f"{key}_redacted:{redacted}")
    for key, value in list(mapping.items()) + list(metadata.items()):
        if key == "source_path_redacted" and value is True:
            redacted_path_count += 1
            risk_flags.append("raw_path_redacted")
            warnings.append("source_path_redacted")
        elif str(key).endswith("_redacted") and _clean(value).startswith("redacted_path_sha256:"):
            redacted_path_count += 1
            risk_flags.append("raw_path_redacted")
            warnings.append(f"{key}:{_clean(value)}")
    resolved = bool(source_family or source_kind or source_atom_id or search_unit_id or search_view_id or identity_hash)
    if not resolved:
        warnings.append("source_metadata_unresolved")
    return {
        "candidate_source_family": source_family,
        "candidate_source_kind": source_kind,
        "candidate_source_title_or_safe_display_name": redacted_title,
        "source_atom_id": source_atom_id,
        "search_unit_id": search_unit_id,
        "search_view_id": search_view_id,
        "registry_source_identity_hash": identity_hash,
        "manifest_path_kind": first("manifest_path_kind") or ("v63_payload_in_memory" if search_unit_id else ""),
        "source_metadata_resolved": resolved,
        "metadata_resolution_warnings": sorted(set(warnings)),
        "source_metadata_redacted_path_count": redacted_path_count,
        "risk_flags": sorted(set(risk_flags)),
    }


def _candidate_lookup_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return _clean(row.get("doc_id")), _clean(row.get("chunk_id"))


def _source_metadata_lookup(
    rows: Sequence[Mapping[str, Any]],
    adapter: Any,
) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        for context in _as_list(row.get("retrieved_contexts")):
            if not isinstance(context, Mapping):
                continue
            key = _candidate_lookup_key(context)
            if any(key):
                lookup[key] = _safe_metadata_from_mapping(context)
    if hasattr(adapter, "_load_payloads"):
        try:
            payloads = adapter._load_payloads()  # type: ignore[attr-defined]
        except Exception:
            payloads = []
        for payload in payloads:
            if not isinstance(payload, Mapping):
                continue
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
            doc_id = _clean(metadata.get("source_safe_id") or payload.get("source_family"))
            chunk_id = _clean(payload.get("search_unit_id"))
            if doc_id or chunk_id:
                lookup[(doc_id, chunk_id)] = _safe_metadata_from_mapping(payload)
    return lookup


def _retrieval_rank_for_candidate(row: Mapping[str, Any], candidate: Mapping[str, Any]) -> int | str:
    candidate_key = (_clean(candidate.get("doc_id")), _clean(candidate.get("chunk_id")))
    for context in _as_list(row.get("retrieved_contexts")):
        if not isinstance(context, Mapping):
            continue
        if _candidate_lookup_key(context) == candidate_key:
            return int(context.get("rank") or 0) or ""
    return ""


def _candidate_family_mismatch(expected_family: str, candidate_family: str) -> bool:
    return bool(expected_family and candidate_family and expected_family != candidate_family)


def _recommend_mapping(
    *,
    confidence: str,
    match_reasons: Sequence[str],
    anchor_hits: Sequence[str],
    missing_numeric: Sequence[str],
    generic_terms: Sequence[str],
    non_generic_terms: Sequence[str],
    expected_family: str,
    candidate_family: str,
) -> tuple[str, str, list[str], str, str]:
    reasons = set(match_reasons)
    risk_flags: list[str] = []
    if _candidate_family_mismatch(expected_family, candidate_family):
        risk_flags.append("source_family_mismatch")
        return (
            "likely_reject",
            f"source family mismatch: expected {expected_family}, candidate {candidate_family}",
            risk_flags,
            "P3",
            "source family mismatch",
        )
    if missing_numeric:
        risk_flags.append("missing_numeric_or_date_anchor")
        if anchor_hits and len([anchor for anchor in anchor_hits if anchor not in generic_terms]) >= 1:
            return (
                "review_needed",
                "rare/entity anchor present but required numeric/date anchor is missing",
                risk_flags,
                "P1",
                "missing numeric/date anchor",
            )
        return (
            "likely_reject",
            "required numeric/date anchor missing",
            risk_flags,
            "P1",
            "missing numeric/date anchor",
        )
    if "no_non_generic_anchor_overlap" in reasons or (not anchor_hits and not non_generic_terms):
        risk_flags.append("generic_overlap_only")
        return ("likely_reject", "generic overlap only", risk_flags, "P2", "generic overlap only")
    if confidence == "high" and (anchor_hits or non_generic_terms):
        return ("likely_accept", "high confidence candidate with required anchors satisfied", risk_flags, "P4", "control/high confidence")
    if confidence == "medium" and (anchor_hits or non_generic_terms):
        return ("possible_match", "medium confidence candidate needs human review", risk_flags, "P4", "medium confidence")
    if confidence == "low" and (anchor_hits or non_generic_terms):
        return ("review_needed", "low confidence candidate has some non-generic overlap", risk_flags, "P1", "low confidence with rare/entity overlap")
    return ("likely_reject", "candidate preview appears unrelated", risk_flags, "P2", "unrelated preview")


def _empty_mapping_packet_summary(enabled: bool) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "evidence_mapping_packet_enabled": bool(enabled),
        "evidence_mapping_packet_row_count": 0,
        "evidence_mapping_packet_item_count": 0,
        "evidence_mapping_packet_candidate_count": 0,
        "evidence_mapping_packet_likely_accept_count": 0,
        "evidence_mapping_packet_possible_match_count": 0,
        "evidence_mapping_packet_review_needed_count": 0,
        "evidence_mapping_packet_likely_reject_count": 0,
        "evidence_mapping_packet_p0_count": 0,
        "evidence_mapping_packet_p1_count": 0,
        "evidence_mapping_packet_p2_count": 0,
        "evidence_mapping_packet_p3_count": 0,
        "evidence_mapping_packet_p4_count": 0,
        "source_metadata_resolved_candidate_count": 0,
        "source_metadata_unresolved_candidate_count": 0,
        "source_metadata_redacted_path_count": 0,
        "human_decision_fields_filled_by_codex": False,
        "guardrails": {
            "diagnostic_review_packet_only": True,
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
        },
    }


def build_evidence_mapping_packet(
    *,
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    adapter: Any,
    enabled: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not enabled:
        return [], _empty_mapping_packet_summary(False)
    metadata_lookup = _source_metadata_lookup(rows, adapter)
    packet_rows: list[dict[str, Any]] = []
    recommendation_counts = Counter()
    priority_counts = Counter()
    item_ids: set[str] = set()
    source_metadata_resolved = 0
    source_metadata_unresolved = 0
    redacted_path_count = 0
    for row in rows:
        item_id = _clean(row.get("id"))
        item_ids.add(item_id)
        resolution = row.get("expected_evidence_resolution") if isinstance(row.get("expected_evidence_resolution"), Mapping) else {}
        expected_family = _expected_source_family(row)
        retrieval_empty = not bool(_as_list(row.get("retrieved_contexts")))
        generated_answer_preview = _clean(row.get("generated_answer"))[:240]
        top_context = ""
        contexts = [context for context in _as_list(row.get("retrieved_contexts")) if isinstance(context, Mapping)]
        if contexts:
            top_context = _clean(contexts[0].get("text"))[:240]
        for evidence_row in _as_list(resolution.get("rows")):
            if not isinstance(evidence_row, Mapping):
                continue
            candidates = [candidate for candidate in _as_list(evidence_row.get("candidates")) if isinstance(candidate, Mapping)]
            if not candidates:
                priority = "P0" if retrieval_empty else "P2"
                recommendation = "likely_reject"
                recommendation_reason = "no candidate available"
                base = {
                    "run_id": summary.get("run_id"),
                    "item_id": item_id,
                    "query_id": item_id,
                    "query": row.get("query"),
                    "expected_answer": row.get("expected_answer"),
                    "expected_answer_aliases": list(row.get("expected_answer_aliases") or []),
                    "expected_evidence_index": evidence_row.get("expected_evidence_index"),
                    "expected_evidence_text": evidence_row.get("input_text"),
                    "expected_input_doc_id": evidence_row.get("input_doc_id"),
                    "expected_input_chunk_id": evidence_row.get("input_chunk_id"),
                    "candidate_rank": "",
                    "candidate_doc_id": "",
                    "candidate_chunk_id": "",
                    "candidate_source_family": "",
                    "candidate_source_kind": "",
                    "candidate_source_title_or_safe_display_name": "",
                    "candidate_score": "",
                    "candidate_confidence": "",
                    "match_type": "",
                    "match_reasons": [],
                    "candidate_match_reasons": [],
                    "candidate_text_preview": "",
                    "candidate_text_hash": "",
                    "candidate_full_text_hash": "",
                    "anchor_hits": [],
                    "candidate_anchor_hits": [],
                    "missing_numeric_or_date_anchors": [],
                    "candidate_missing_numeric_or_date_anchors": [],
                    "candidate_generic_overlap_terms": [],
                    "candidate_non_generic_anchor_overlap_terms": [],
                    "collision_warning": "",
                    "retrieval_rank_if_present": "",
                    "candidate_source": "",
                    "candidate_source_atom_id": "",
                    "source_atom_id": "",
                    "candidate_evidence_bundle_id": "",
                    "search_unit_id": "",
                    "search_view_id": "",
                    "registry_source_identity_hash": "",
                    "manifest_path_kind": "",
                    "source_metadata_resolved": False,
                    "metadata_resolution_warnings": ["no_candidate"],
                    "machine_recommendation": recommendation,
                    "machine_recommendation_reason": recommendation_reason,
                    "review_priority": priority,
                    "primary_blocker": "no candidate",
                    "risk_flags": ["no_candidate"],
                    "guardrail_flags": ["diagnostic_review_packet_only", "human_decision_required"],
                    "human_decision_fields_filled_by_codex": False,
                    "generated_answer_preview": generated_answer_preview,
                    "top_retrieved_context_preview": top_context,
                    "retrieval_empty": retrieval_empty,
                }
                for human_field in HUMAN_EVIDENCE_MAPPING_FIELDS:
                    base[human_field] = ""
                packet_rows.append(base)
                recommendation_counts[recommendation] += 1
                priority_counts[priority] += 1
                source_metadata_unresolved += 1
                continue
            for candidate in candidates:
                candidate_doc_id = _clean(candidate.get("doc_id"))
                candidate_chunk_id = _clean(candidate.get("chunk_id"))
                metadata = metadata_lookup.get((candidate_doc_id, candidate_chunk_id)) or _safe_metadata_from_mapping(candidate)
                candidate_family = _clean(metadata.get("candidate_source_family")) or _source_family_from_text(candidate.get("text_preview"))
                metadata_resolved = bool(metadata.get("source_metadata_resolved"))
                if metadata_resolved:
                    source_metadata_resolved += 1
                else:
                    source_metadata_unresolved += 1
                redacted_path_count += int(metadata.get("source_metadata_redacted_path_count") or 0)
                match_reasons = list(candidate.get("match_reasons") or [])
                anchor_hits = list(candidate.get("anchor_hits") or [])
                missing_numeric = list(candidate.get("missing_numeric_or_date_anchors") or [])
                generic_terms = list(candidate.get("candidate_generic_overlap_terms") or [])
                non_generic_terms = list(candidate.get("candidate_non_generic_anchor_overlap_terms") or anchor_hits)
                recommendation, recommendation_reason, risk_flags, priority, blocker = _recommend_mapping(
                    confidence=_clean(candidate.get("confidence")),
                    match_reasons=match_reasons,
                    anchor_hits=anchor_hits,
                    missing_numeric=missing_numeric,
                    generic_terms=generic_terms,
                    non_generic_terms=non_generic_terms,
                    expected_family=expected_family,
                    candidate_family=candidate_family,
                )
                risk_flags = sorted(set([*risk_flags, *list(metadata.get("risk_flags") or [])]))
                metadata_warnings = list(metadata.get("metadata_resolution_warnings") or [])
                packet = {
                    "run_id": summary.get("run_id"),
                    "item_id": item_id,
                    "query_id": item_id,
                    "query": row.get("query"),
                    "expected_answer": row.get("expected_answer"),
                    "expected_answer_aliases": list(row.get("expected_answer_aliases") or []),
                    "expected_evidence_index": evidence_row.get("expected_evidence_index"),
                    "expected_evidence_text": evidence_row.get("input_text"),
                    "expected_input_doc_id": evidence_row.get("input_doc_id"),
                    "expected_input_chunk_id": evidence_row.get("input_chunk_id"),
                    "candidate_rank": candidate.get("rank"),
                    "candidate_doc_id": candidate_doc_id,
                    "candidate_chunk_id": candidate_chunk_id,
                    "candidate_source_family": candidate_family,
                    "candidate_source_kind": metadata.get("candidate_source_kind") or "",
                    "candidate_source_title_or_safe_display_name": metadata.get("candidate_source_title_or_safe_display_name") or "",
                    "candidate_score": candidate.get("score"),
                    "candidate_confidence": candidate.get("confidence"),
                    "match_type": candidate.get("match_type") or "",
                    "match_reasons": match_reasons,
                    "candidate_match_reasons": match_reasons,
                    "candidate_text_preview": candidate.get("text_preview") or "",
                    "candidate_text_hash": candidate.get("candidate_text_hash") or candidate.get("candidate_full_text_hash") or _sha256_text(candidate.get("text_preview")),
                    "candidate_full_text_hash": candidate.get("candidate_full_text_hash") or _sha256_text(candidate.get("text_preview")),
                    "anchor_hits": anchor_hits,
                    "candidate_anchor_hits": anchor_hits,
                    "missing_numeric_or_date_anchors": missing_numeric,
                    "candidate_missing_numeric_or_date_anchors": missing_numeric,
                    "candidate_generic_overlap_terms": generic_terms,
                    "candidate_non_generic_anchor_overlap_terms": non_generic_terms,
                    "collision_warning": candidate.get("collision_warning") or "",
                    "retrieval_rank_if_present": _retrieval_rank_for_candidate(row, candidate),
                    "candidate_source": candidate.get("source") or "",
                    "candidate_source_atom_id": metadata.get("source_atom_id") or candidate.get("source_atom_id") or "",
                    "source_atom_id": metadata.get("source_atom_id") or candidate.get("source_atom_id") or "",
                    "candidate_evidence_bundle_id": candidate.get("evidence_bundle_id") or "",
                    "search_unit_id": metadata.get("search_unit_id") or candidate_chunk_id,
                    "search_view_id": metadata.get("search_view_id") or "",
                    "registry_source_identity_hash": metadata.get("registry_source_identity_hash") or "",
                    "manifest_path_kind": metadata.get("manifest_path_kind") or "",
                    "source_metadata_resolved": metadata_resolved,
                    "metadata_resolution_warnings": metadata_warnings,
                    "machine_recommendation": recommendation,
                    "machine_recommendation_reason": recommendation_reason,
                    "review_priority": priority,
                    "primary_blocker": blocker,
                    "risk_flags": risk_flags,
                    "guardrail_flags": [
                        "diagnostic_review_packet_only",
                        "human_decision_required",
                        "machine_recommendation_not_gold",
                        "no_gold_qrels_label_mutation",
                        "no_retriever_ranking_change",
                    ],
                    "human_decision_fields_filled_by_codex": False,
                    "generated_answer_preview": generated_answer_preview,
                    "top_retrieved_context_preview": top_context,
                    "retrieval_empty": retrieval_empty,
                }
                for human_field in HUMAN_EVIDENCE_MAPPING_FIELDS:
                    packet[human_field] = ""
                packet_rows.append(packet)
                recommendation_counts[recommendation] += 1
                priority_counts[priority] += 1
    packet_summary = _empty_mapping_packet_summary(True)
    packet_summary.update(
        {
            "evidence_mapping_packet_row_count": len(packet_rows),
            "evidence_mapping_packet_item_count": len({row.get("item_id") for row in packet_rows if row.get("item_id")}),
            "evidence_mapping_packet_candidate_count": sum(1 for row in packet_rows if row.get("candidate_doc_id") or row.get("candidate_chunk_id")),
            "evidence_mapping_packet_likely_accept_count": recommendation_counts.get("likely_accept", 0),
            "evidence_mapping_packet_possible_match_count": recommendation_counts.get("possible_match", 0),
            "evidence_mapping_packet_review_needed_count": recommendation_counts.get("review_needed", 0),
            "evidence_mapping_packet_likely_reject_count": recommendation_counts.get("likely_reject", 0),
            "evidence_mapping_packet_p0_count": priority_counts.get("P0", 0),
            "evidence_mapping_packet_p1_count": priority_counts.get("P1", 0),
            "evidence_mapping_packet_p2_count": priority_counts.get("P2", 0),
            "evidence_mapping_packet_p3_count": priority_counts.get("P3", 0),
            "evidence_mapping_packet_p4_count": priority_counts.get("P4", 0),
            "source_metadata_resolved_candidate_count": source_metadata_resolved,
            "source_metadata_unresolved_candidate_count": source_metadata_unresolved,
            "source_metadata_redacted_path_count": redacted_path_count,
            "human_decision_fields_filled_by_codex": any(
                bool(_clean(packet.get(field)))
                for packet in packet_rows
                for field in HUMAN_EVIDENCE_MAPPING_FIELDS
            ),
        }
    )
    packet_summary["human_decision_fields_filled_by_codex"] = False
    return packet_rows, packet_summary


def _apply_mapping_packet_summary(summary: dict[str, Any], packet_summary: Mapping[str, Any]) -> None:
    diagnostics = summary.setdefault("diagnostic_metrics", {})
    for key, value in packet_summary.items():
        if key in {"enabled", "guardrails"}:
            continue
        diagnostics[key] = value
    summary["evidence_mapping_packet_summary"] = dict(packet_summary)


def render_evidence_mapping_packet_markdown(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    packet_summary: Mapping[str, Any],
) -> str:
    def preview(value: Any, limit: int = 140) -> str:
        text = re.sub(r"\s+", " ", _clean(value))
        return text if len(text) <= limit else text[: max(0, limit - 3)].rstrip() + "..."

    lines = [
        "# Evidence Mapping Review Packet",
        "",
        "This packet is diagnostic and human-reviewable. Machine recommendations are not gold, and human-owned fields are intentionally blank.",
        "",
        f"- Run id: `{summary.get('run_id')}`",
        f"- Enabled: `{packet_summary.get('evidence_mapping_packet_enabled')}`",
        f"- Packet rows: `{packet_summary.get('evidence_mapping_packet_row_count')}`",
        f"- Item count: `{packet_summary.get('evidence_mapping_packet_item_count')}`",
        f"- Human decision fields filled by Codex: `{packet_summary.get('human_decision_fields_filled_by_codex')}`",
        "",
        "## Compact Review Table",
        "",
        "| item_id | expected evidence preview | best candidate doc/chunk | confidence | recommendation | primary blocker | review priority |",
        "|---|---|---|---|---|---|---|",
    ]
    best_by_item: dict[str, Mapping[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        item_id = _clean(row.get("item_id"))
        if item_id and item_id not in best_by_item:
            best_by_item[item_id] = row
            order.append(item_id)
    if not order:
        lines.append("| none |  |  |  |  |  |  |")
    for item_id in order:
        row = best_by_item[item_id]
        lines.append(
            f"| `{item_id}` | {preview(row.get('expected_evidence_text'), 90)} | "
            f"`{row.get('candidate_doc_id')}` / `{row.get('candidate_chunk_id')}` | "
            f"`{row.get('candidate_confidence')}` | `{row.get('machine_recommendation')}` | "
            f"{preview(row.get('primary_blocker'), 80)} | `{row.get('review_priority')}` |"
        )
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_clean(row.get("item_id")), []).append(row)
    lines.extend(["", "## Items", ""])
    for item_id in order:
        item_rows = grouped.get(item_id, [])
        first = item_rows[0]
        lines.extend(
            [
                f"### `{item_id}`",
                "",
                f"- Query: {preview(first.get('query'), 220)}",
                f"- Expected answer: {preview(first.get('expected_answer'), 220)}",
                f"- Expected evidence: {preview(first.get('expected_evidence_text'), 260)}",
                f"- Current generated answer preview: {preview(first.get('generated_answer_preview'), 220)}",
                f"- Top retrieved context preview: {preview(first.get('top_retrieved_context_preview'), 260)}",
                f"- Retrieval empty: `{first.get('retrieval_empty')}`",
                "- Human review fields: `human_mapping_decision`, `human_accepted_doc_id`, `human_accepted_chunk_id`, `human_evidence_sufficient`, `human_answerability_label`, `human_relevance_label`, `human_notes`, `reviewed_by`, and `reviewed_at` are blank.",
                "",
                "| candidate | source | confidence | recommendation | failed high/medium reason | preview |",
                "|---|---|---|---|---|---|",
            ]
        )
        for candidate in item_rows:
            failed_reasons = ", ".join(
                [
                    *[str(value) for value in candidate.get("candidate_missing_numeric_or_date_anchors") or []],
                    *[str(value) for value in candidate.get("risk_flags") or []],
                    *[str(value) for value in candidate.get("metadata_resolution_warnings") or []],
                ]
            ) or candidate.get("machine_recommendation_reason")
            lines.append(
                f"| `{candidate.get('candidate_doc_id')}` / `{candidate.get('candidate_chunk_id')}` | "
                f"`{candidate.get('candidate_source')}` | `{candidate.get('candidate_confidence')}` | "
                f"`{candidate.get('machine_recommendation')}` | {preview(failed_reasons, 120)} | "
                f"{preview(candidate.get('candidate_text_preview'), 160)} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Guardrails",
            "",
            "- No gold/qrels/labels were mutated.",
            "- Human-owned fields are blank; machine recommendations are not accepted mappings.",
            "- Source metadata enrichment is diagnostic only and redacts raw local paths.",
            "- Retriever ranking and generated answers are not changed by this packet.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_evidence_mapping_packet_artifacts(
    *,
    output_dir: Path,
    summary: Mapping[str, Any],
    packet_rows: Sequence[Mapping[str, Any]],
    packet_summary: Mapping[str, Any],
) -> tuple[Path, Path, Path, Path]:
    csv_path = output_dir / "evidence_mapping_review_packet.csv"
    jsonl_path = output_dir / "evidence_mapping_review_packet.jsonl"
    md_path = output_dir / "evidence_mapping_review_packet.md"
    summary_path = output_dir / "evidence_mapping_packet_summary.json"
    write_jsonl(jsonl_path, packet_rows)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(EVIDENCE_MAPPING_PACKET_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in packet_rows:
            rendered = {
                key: json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            }
            writer.writerow(rendered)
    md_path.write_text(render_evidence_mapping_packet_markdown(summary, packet_rows, packet_summary), encoding="utf-8")
    write_json(summary_path, packet_summary)
    return csv_path, jsonl_path, md_path, summary_path


def build_gpu_preflight() -> dict[str, Any]:
    preflight: dict[str, Any] = {
        "checked": True,
        "gpu_available": False,
        "cuda_available": False,
        "device": "cpu",
        "device_name": "",
        "nvidia_smi_available": False,
        "torch_available": False,
        "torch_cuda_available": False,
        "torch_cuda_device_count": 0,
        "sentence_transformers_available": False,
        "bge_m3_model": "BAAI/bge-m3",
        "bge_m3_cache_path": "",
        "bge_m3_cache_available": False,
        "faiss_available": False,
        "faiss_gpu_capable": False,
        "faiss_version": "",
        "fallback_reason": "",
    }
    try:
        availability_probe = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-c",
                (
                    "import importlib.util, json\n"
                    "print(json.dumps({'sentence_transformers_available': "
                    "importlib.util.find_spec('sentence_transformers') is not None}))\n"
                ),
            ],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        if availability_probe.stdout.strip():
            availability = json.loads(availability_probe.stdout.strip().splitlines()[-1])
            preflight["sentence_transformers_available"] = bool(
                availability.get("sentence_transformers_available")
            )
    except Exception as exc:
        preflight["sentence_transformers_error"] = f"{type(exc).__name__}: {exc}"

    try:
        import faiss  # type: ignore

        preflight["faiss_available"] = True
        preflight["faiss_version"] = _clean(getattr(faiss, "__version__", "unknown"))
        get_num_gpus = getattr(faiss, "get_num_gpus", None)
        faiss_gpu_count = int(get_num_gpus()) if callable(get_num_gpus) else 0
        preflight["faiss_gpu_count"] = faiss_gpu_count
        preflight["faiss_gpu_capable"] = bool(
            faiss_gpu_count > 0
            and hasattr(faiss, "StandardGpuResources")
            and hasattr(faiss, "index_cpu_to_gpu")
            and hasattr(faiss, "index_gpu_to_cpu")
        )
    except Exception as exc:
        preflight["faiss_error"] = f"{type(exc).__name__}: {exc}"

    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        if completed.returncode == 0:
            names = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
            preflight["nvidia_smi_available"] = True
            preflight["nvidia_smi_device_names"] = names
            if names and not preflight["device_name"]:
                preflight["device_name"] = names[0]
    except Exception as exc:
        preflight["nvidia_smi_error"] = f"{type(exc).__name__}: {exc}"

    try:
        probe = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-c",
                (
                    "import json\n"
                    "try:\n"
                    " import torch\n"
                    " cuda=bool(torch.cuda.is_available())\n"
                    " count=int(torch.cuda.device_count()) if cuda else 0\n"
                    " name=torch.cuda.get_device_name(0) if count else ''\n"
                    " print(json.dumps({'torch_available': True, 'torch_cuda_available': cuda, "
                    "'torch_cuda_device_count': count, 'device_name': name}))\n"
                    "except Exception as exc:\n"
                    " print(json.dumps({'torch_available': False, 'torch_error': type(exc).__name__ + ': ' + str(exc)}))\n"
                ),
            ],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        if probe.stdout.strip():
            torch_probe = json.loads(probe.stdout.strip().splitlines()[-1])
            preflight["torch_available"] = bool(torch_probe.get("torch_available"))
            preflight["torch_cuda_available"] = bool(torch_probe.get("torch_cuda_available"))
            preflight["cuda_available"] = bool(torch_probe.get("torch_cuda_available"))
            preflight["torch_cuda_device_count"] = int(torch_probe.get("torch_cuda_device_count") or 0)
            preflight["gpu_available"] = preflight["torch_cuda_device_count"] > 0
            preflight["device"] = "cuda:0" if preflight["gpu_available"] else "cpu"
            if _clean(torch_probe.get("device_name")):
                preflight["device_name"] = _clean(torch_probe.get("device_name"))
            if _clean(torch_probe.get("torch_error")):
                preflight["torch_error"] = _clean(torch_probe.get("torch_error"))
        elif probe.stderr.strip():
            preflight["torch_error"] = probe.stderr.strip()[:400]
    except Exception as exc:
        preflight["torch_error"] = f"{type(exc).__name__}: {exc}"

    cache_root = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub" / "models--BAAI--bge-m3"
    preflight["bge_m3_cache_path"] = _report_path_value(cache_root)
    preflight["bge_m3_cache_path_sha256"] = f"sha256:{_sha256_text(cache_root.as_posix())}"
    preflight["bge_m3_cache_available"] = cache_root.exists()
    if preflight["gpu_available"] and preflight["cuda_available"]:
        preflight["fallback_reason"] = ""
    elif not preflight["torch_available"]:
        preflight["fallback_reason"] = "torch_unavailable"
    elif not preflight["torch_cuda_available"]:
        preflight["fallback_reason"] = "torch_cuda_unavailable"
    elif not preflight["nvidia_smi_available"]:
        preflight["fallback_reason"] = "nvidia_smi_unavailable"
    return preflight


def discover_external_vector_db() -> dict[str, Any]:
    vector_db = _clean(os.environ.get("RAG_VECTOR_DB") or os.environ.get("ACTUAL_RAG_EVAL_VECTOR_DB")).casefold()
    if vector_db == "weaviate" or _clean(os.environ.get("WEAVIATE_URL")):
        config = WeaviateSourceAtomConfig.from_env()
        return config.external_vector_db_report(
            invoked=False,
            reachable=False,
            fallback_reason=(
                "production_or_ambiguous_namespace_blocked"
                if config.production_namespace
                else "weaviate_adapter_not_invoked_yet"
            ),
        )
    namespace = _clean(
        os.environ.get("ACTUAL_RAG_EVAL_VECTOR_NAMESPACE")
        or os.environ.get("RAG_VECTOR_NAMESPACE")
        or os.environ.get("VECTOR_DB_NAMESPACE")
    )
    dsn_present = bool(
        _clean(os.environ.get("ACTUAL_RAG_EVAL_VECTOR_DB_DSN"))
        or _clean(os.environ.get("RAG_VECTOR_DB_DSN"))
        or _clean(os.environ.get("VECTOR_DB_DSN"))
    )
    configured = bool(namespace or dsn_present)
    nonprod = bool(namespace and re.search(r"(nonprod|dev|test|local|diagnostic)", namespace, flags=re.I))
    allowed = os.environ.get("ACTUAL_RAG_EVAL_ALLOW_EXTERNAL_VECTOR_DB") == "1"
    return {
        "configured": configured,
        "invoked": False,
        "reachable": False,
        "namespace": namespace,
        "production_namespace": bool(configured and not nonprod),
        "fallback_reason": (
            "not_configured"
            if not configured
            else "production_or_ambiguous_namespace_blocked"
            if not nonprod
            else "explicit_external_vectordb_invocation_disabled" if not allowed else "adapter_not_implemented"
        ),
    }


def build_backend_comparison_metrics(raw_outputs: Sequence[Mapping[str, Any]], adapter: Any) -> dict[str, Any]:
    comparisons = [
        output.get("retrieval_backend_comparison")
        for output in raw_outputs
        if isinstance(output.get("retrieval_backend_comparison"), Mapping)
    ]
    item_count = max(len(comparisons), 1)

    def candidate_counts(name: str) -> list[int]:
        return [
            int(((comparison.get("candidate_counts") or {}).get(name)) or 0)
            for comparison in comparisons
            if isinstance(comparison, Mapping)
        ]

    def latency_values(name: str) -> list[float]:
        return [
            float(((comparison.get("latency_ms") or {}).get(name)) or 0.0)
            for comparison in comparisons
            if isinstance(comparison, Mapping)
        ]

    overlap = [
        int(((comparison.get("overlap_counts") or {}).get("bm25_vector_topk")) or 0)
        for comparison in comparisons
        if isinstance(comparison, Mapping)
    ]
    backend_diagnostics = (
        getattr(adapter, "backend_diagnostics", {})
        if isinstance(getattr(adapter, "backend_diagnostics", {}), Mapping)
        else {}
    )
    vector_available = bool(backend_diagnostics.get("vector_index_available", False))
    if not comparisons:
        return {
            "comparison_available": False,
            "comparison_row_count": 0,
            "comparison_missing_row_count": len(raw_outputs),
            "bm25_retrieval_empty_rate": None,
            "vector_retrieval_empty_rate": None,
            "hybrid_retrieval_empty_rate": None,
            "bm25_candidate_count_avg": None,
            "vector_candidate_count_avg": None,
            "hybrid_candidate_count_avg": None,
            "bm25_vector_topk_overlap_avg": None,
            "vector_latency_ms_p50": None,
            "vector_latency_ms_p95": None,
            "bm25_latency_ms_p50": None,
            "bm25_latency_ms_p95": None,
            "hybrid_latency_ms_p50": None,
            "hybrid_latency_ms_p95": None,
            "embedding_build_latency_ms": float(backend_diagnostics.get("embedding_build_latency_ms") or 0.0),
            "index_load_or_build_latency_ms": float(backend_diagnostics.get("index_load_or_build_latency_ms") or 0.0),
            "gpu_used_for_embedding_count": 0,
            "vector_index_available": vector_available,
            "fallback_reason": _clean(backend_diagnostics.get("fallback_reason")) or "item_backend_comparison_unavailable",
        }
    return {
        "comparison_available": True,
        "comparison_row_count": len(comparisons),
        "comparison_missing_row_count": max(len(raw_outputs) - len(comparisons), 0),
        "bm25_retrieval_empty_rate": round(sum(1 for value in candidate_counts("bm25") if value == 0) / item_count, 6),
        "vector_retrieval_empty_rate": round(sum(1 for value in candidate_counts("vector") if value == 0) / item_count, 6),
        "hybrid_retrieval_empty_rate": round(sum(1 for value in candidate_counts("hybrid") if value == 0) / item_count, 6),
        "bm25_candidate_count_avg": _average(candidate_counts("bm25")),
        "vector_candidate_count_avg": _average(candidate_counts("vector")),
        "hybrid_candidate_count_avg": _average(candidate_counts("hybrid")),
        "bm25_vector_topk_overlap_avg": _average(overlap),
        "vector_latency_ms_p50": _latency_distribution_ms(latency_values("vector"))["p50"],
        "vector_latency_ms_p95": _latency_distribution_ms(latency_values("vector"))["p95"],
        "bm25_latency_ms_p50": _latency_distribution_ms(latency_values("bm25"))["p50"],
        "bm25_latency_ms_p95": _latency_distribution_ms(latency_values("bm25"))["p95"],
        "hybrid_latency_ms_p50": _latency_distribution_ms(latency_values("hybrid"))["p50"],
        "hybrid_latency_ms_p95": _latency_distribution_ms(latency_values("hybrid"))["p95"],
        "embedding_build_latency_ms": float(backend_diagnostics.get("embedding_build_latency_ms") or 0.0),
        "index_load_or_build_latency_ms": float(backend_diagnostics.get("index_load_or_build_latency_ms") or 0.0),
        "gpu_used_for_embedding_count": sum(
            1 for _comparison in comparisons if bool(backend_diagnostics.get("gpu_used_for_embedding"))
        ),
        "vector_index_available": vector_available,
        "fallback_reason": _clean(backend_diagnostics.get("fallback_reason")),
    }


def build_surface_comparison_metrics(raw_outputs: Sequence[Mapping[str, Any]], top_k: int) -> dict[str, Any]:
    comparisons = [
        output.get("retrieval_surface_comparison")
        for output in raw_outputs
        if isinstance(output.get("retrieval_surface_comparison"), Mapping)
    ]
    denominator = max(len(comparisons), 1)

    def surface(name: str, comparison: Mapping[str, Any]) -> Mapping[str, Any]:
        value = comparison.get(name)
        return value if isinstance(value, Mapping) else {}

    source_rows = [surface("source_native", comparison) for comparison in comparisons]
    searchunit_rows = [
        row
        for row in (surface("searchunit_searchview", comparison) for comparison in comparisons)
        if row.get("comparison_enabled") is not False
    ]
    source_retrieved = sum(1 for row in source_rows if row.get("expected_evidence_retrieved"))
    searchunit_retrieved = sum(1 for row in searchunit_rows if row.get("expected_evidence_retrieved"))
    searchunit_denominator = len(searchunit_rows)

    def _rate_or_none(numerator: int, denom: int) -> float | None:
        if denom <= 0:
            return None
        return round(numerator / denom, 6)

    metrics = {
        "surface_comparison_available": bool(comparisons),
        "surface_comparison_row_count": len(comparisons),
        "searchunit_surface_comparison_row_count": searchunit_denominator,
        "source_native_retrieval_empty_rate": round(
            sum(1 for row in source_rows if row.get("retrieval_empty")) / denominator,
            6,
        ),
        "searchunit_retrieval_empty_rate": _rate_or_none(
            sum(1 for row in searchunit_rows if row.get("retrieval_empty")),
            searchunit_denominator,
        ),
        "source_native_expected_anchor_recall@k_diagnostic": round(source_retrieved / denominator, 6),
        "searchunit_expected_anchor_recall@k_diagnostic": _rate_or_none(searchunit_retrieved, searchunit_denominator),
        f"source_native_expected_anchor_recall@{top_k}_diagnostic": round(source_retrieved / denominator, 6),
        f"searchunit_expected_anchor_recall@{top_k}_diagnostic": _rate_or_none(searchunit_retrieved, searchunit_denominator),
        "source_native_expected_evidence_text_presence_rate": round(
            sum(1 for row in source_rows if row.get("expected_evidence_in_corpus_normalized")) / denominator,
            6,
        ),
        "searchunit_expected_evidence_text_presence_rate": _rate_or_none(
            sum(1 for row in searchunit_rows if row.get("expected_evidence_in_corpus_normalized")),
            searchunit_denominator,
        ),
        "expected_evidence_exact_present_in_source_native_count": sum(
            1 for row in source_rows if row.get("expected_evidence_in_corpus_exact")
        ),
        "expected_evidence_normalized_present_in_source_native_count": sum(
            1 for row in source_rows if row.get("expected_evidence_in_corpus_normalized")
        ),
        "expected_anchor_present_in_source_native_count": sum(1 for row in source_rows if row.get("expected_anchor_in_corpus")),
        "expected_anchor_present_in_searchunit_count": sum(1 for row in searchunit_rows if row.get("expected_anchor_in_corpus")),
        "source_native_target_span_present_but_not_retrieved_count": sum(
            1
            for row in source_rows
            if row.get("expected_evidence_in_corpus_normalized") and not row.get("expected_evidence_retrieved")
        ),
        "source_native_target_span_absent_count": sum(
            1 for row in source_rows if not row.get("expected_evidence_in_corpus_normalized")
        ),
        "searchunit_target_span_absent_count": sum(
            1 for row in searchunit_rows if not row.get("expected_evidence_in_corpus_normalized")
        ),
        "source_native_beats_searchunit_count": sum(1 for row in comparisons if row.get("source_native_beats_searchunit")),
        "searchunit_beats_source_native_count": sum(1 for row in comparisons if row.get("searchunit_beats_source_native")),
        "both_surfaces_fail_count": sum(1 for row in comparisons if row.get("both_surfaces_fail")),
    }
    return metrics


def add_surface_metrics(summary: dict[str, Any], surface_metrics: Mapping[str, Any], *, top_k: int) -> None:
    summary["diagnostic_metrics"].update(surface_metrics)
    source_num = int(surface_metrics.get(f"source_native_expected_anchor_recall@{top_k}_diagnostic") is not None and round(float(surface_metrics.get(f"source_native_expected_anchor_recall@{top_k}_diagnostic") or 0) * int(surface_metrics.get("surface_comparison_row_count") or 0)))
    search_denominator = int(surface_metrics.get("searchunit_surface_comparison_row_count") or 0)
    search_num = int(surface_metrics.get(f"searchunit_expected_anchor_recall@{top_k}_diagnostic") is not None and round(float(surface_metrics.get(f"searchunit_expected_anchor_recall@{top_k}_diagnostic") or 0) * search_denominator))
    denominator = int(surface_metrics.get("surface_comparison_row_count") or 0)
    for name, numerator, tier in (
        ("source_native_resolved_evidence_available_rate_provisional", int(surface_metrics.get("expected_evidence_normalized_present_in_source_native_count") or 0), "provisional"),
        (f"source_native_weak_evidence_match_recall@{top_k}", source_num, "provisional"),
        ("surface_selected_e2e_rag_success_provisional", source_num, "provisional"),
        (f"source_native_expected_anchor_recall@{top_k}_diagnostic", source_num, "diagnostic"),
        (f"searchunit_expected_anchor_recall@{top_k}_diagnostic", search_num, "diagnostic"),
    ):
        metric = _metric_template(name, "surface comparison diagnostics; non-official", tier=tier)
        metric["numerator"] = numerator
        metric["denominator"] = search_denominator if name.startswith("searchunit_") else denominator
        metric = _finish_metric(metric)
        if tier == "provisional":
            summary["provisional_metrics"][name] = metric
        else:
            summary.setdefault("diagnostic_metric_details", {})[name] = metric


def build_surface_migration_report(
    *,
    retrieval_surface_report: Mapping[str, Any],
    retrieval_backend_report: Mapping[str, Any],
    surface_comparison: Mapping[str, Any],
    legacy_surface_comparison: bool,
) -> dict[str, Any]:
    selected_surface = _clean(retrieval_surface_report.get("selected")) or "unknown"
    selected_backend = _clean(retrieval_backend_report.get("selected")) or "unknown"
    source_available = bool(retrieval_surface_report.get("source_native_available"))
    present_not_retrieved = int(surface_comparison.get("source_native_target_span_present_but_not_retrieved_count") or 0)
    absent = int(surface_comparison.get("source_native_target_span_absent_count") or 0)
    remaining_target = "source_native_ranking_query_formulation"
    statement = (
        "remaining failures are source-native ranking/query formulation misses; "
        "SearchUnit/SearchView repair is not the target"
    )
    basis_keys = [
        "source_native_expected_evidence_text_presence_rate",
        "searchunit_expected_evidence_text_presence_rate",
        "expected_evidence_normalized_present_in_source_native_count",
        "source_native_target_span_absent_count",
        "searchunit_target_span_absent_count",
        "source_native_beats_searchunit_count",
        "searchunit_beats_source_native_count",
        "both_surfaces_fail_count",
    ]
    return {
        "run_key": "actual_rag_eval_source_native_surface_hard_switch_nonprod",
        "selected_surface": selected_surface,
        "selected_backend": selected_backend,
        "source_native_available": source_available,
        "source_native_unit_count": int(retrieval_surface_report.get("source_native_unit_count") or 0),
        "hard_switched": bool(
            selected_surface == "source_native"
            and source_available
            and not bool(retrieval_surface_report.get("auto_fallback_to_searchunit_searchview"))
        ),
        "searchunit_searchview_candidate_surface_enabled": bool(
            retrieval_surface_report.get("searchunit_searchview_candidate_surface_enabled")
        ),
        "searchunit_searchview_role": "legacy_comparison_debug_only",
        "legacy_comparison_enabled": bool(legacy_surface_comparison),
        "auto_fallback_to_searchunit_searchview": bool(
            retrieval_surface_report.get("auto_fallback_to_searchunit_searchview")
        ),
        "deprecation_decision": "demote_from_routine_actual_rag_candidate_surface",
        "deprecation_basis": {key: surface_comparison.get(key) for key in basis_keys},
        "remaining_failure_statement": statement,
        "remaining_failure_target": remaining_target,
        "remaining_surface_bottleneck": remaining_target,
        "source_native_corpus_coverage_note": (
            "source_native_target_span_absent_count is diagnostic context only for this hard-switch; "
            "it does not re-enable SearchUnit/SearchView as a routine candidate surface"
            if absent > 0
            else ""
        ),
        "source_native_present_not_retrieved_count": present_not_retrieved,
    }


def build_source_native_layered_retrieval_report(
    *,
    raw_outputs: Sequence[Mapping[str, Any]],
    retrieval_surface_report: Mapping[str, Any],
    retrieval_backend_report: Mapping[str, Any],
    legacy_surface_comparison: bool,
) -> dict[str, Any]:
    selected_surface = _clean(retrieval_surface_report.get("selected")) or "unknown"
    selected_backend = _clean(retrieval_backend_report.get("selected")) or "unknown"
    rows = [
        output.get("source_native_layered_retrieval")
        for output in raw_outputs
        if isinstance(output.get("source_native_layered_retrieval"), Mapping)
    ]
    enabled_rows = [dict(row) for row in rows if bool(row.get("enabled"))]
    if selected_surface != "source_native" or not enabled_rows:
        return _empty_source_native_layered_retrieval_report(
            selected_surface=selected_surface,
            selected_backend=selected_backend,
            legacy_surface_comparison=legacy_surface_comparison,
            fallback_reason="source_native_layered_retrieval_not_run",
        )

    def max_int(field: str) -> int:
        return max(int(row.get(field) or 0) for row in enabled_rows)

    per_layer_candidate_counts = {
        layer: max(
            int(((row.get("per_layer_candidate_counts") or {}).get(layer)) or 0)
            for row in enabled_rows
        )
        for layer in SOURCE_NATIVE_LAYERED_RETRIEVAL_LAYERS
    }
    per_layer_latency_ms = {
        layer: max(
            float(((row.get("per_layer_latency_ms") or {}).get(layer)) or 0.0)
            for row in enabled_rows
        )
        for layer in SOURCE_NATIVE_LAYERED_RETRIEVAL_LAYERS
    }
    first_variants = next((list(row.get("query_variants") or []) for row in enabled_rows if row.get("query_variants")), [])
    report = {
        "enabled": True,
        "planner": "bounded_deterministic_source_native_layered_retrieval_v1",
        "selected_surface": selected_surface,
        "selected_backend": selected_backend,
        "layers": list(SOURCE_NATIVE_LAYERED_RETRIEVAL_LAYERS),
        "query_variants": first_variants,
        "query_variant_count": max_int("query_variant_count"),
        "backend_call_count": max_int("backend_call_count"),
        "item_count": len(enabled_rows),
        "per_layer_candidate_counts": per_layer_candidate_counts,
        "per_layer_candidate_count_policy": "max_per_item",
        "per_layer_latency_ms": {key: round(float(value), 6) for key, value in per_layer_latency_ms.items()},
        "per_layer_latency_policy": "max_per_item_ms",
        "merge_policy": "rrf_v1",
        "rerank_policy": "anchor_aware_diagnostic_rerank_v1",
        "final_candidate_count": max_int("final_candidate_count"),
        "final_candidate_count_policy": "max_per_item",
        "bounds": dict(SOURCE_NATIVE_LAYERED_RETRIEVAL_BOUNDS),
        "gold_fields_used_for_candidate_generation": any(
            bool(row.get("gold_fields_used_for_candidate_generation")) for row in enabled_rows
        ),
        "expected_fields_used_for_candidate_generation": any(
            bool(row.get("expected_fields_used_for_candidate_generation")) for row in enabled_rows
        ),
        "qrels_used_for_candidate_generation": any(bool(row.get("qrels_used_for_candidate_generation")) for row in enabled_rows),
        "answerability_labels_used_for_candidate_generation": any(
            bool(row.get("answerability_labels_used_for_candidate_generation")) for row in enabled_rows
        ),
        "ids_used_for_candidate_generation": any(bool(row.get("ids_used_for_candidate_generation")) for row in enabled_rows),
        "baseline_topk_used_for_candidate_generation": any(
            bool(row.get("baseline_topk_used_for_candidate_generation")) for row in enabled_rows
        ),
        "searchunit_searchview_used_as_candidate_surface": any(
            bool(row.get("searchunit_searchview_used_as_candidate_surface")) for row in enabled_rows
        ),
        "legacy_searchunit_comparison_enabled": bool(legacy_surface_comparison),
        "source_native_units_only": all(bool(row.get("source_native_units_only")) for row in enabled_rows),
        "diagnostic_hash_faiss_fallback_recorded": any(
            "diagnostic_hash" in _clean(row.get("fallback_reason")) for row in enabled_rows
        ),
        "fallback_reasons": sorted(
            {
                _clean(row.get("fallback_reason"))
                for row in enabled_rows
                if _clean(row.get("fallback_reason"))
            }
        ),
    }
    return report


def build_vector_index_audit_report(
    *,
    raw_outputs: Sequence[Mapping[str, Any]],
    adapter: Any,
    retrieval_surface_report: Mapping[str, Any],
    retrieval_backend_report: Mapping[str, Any],
    backend_comparison: Mapping[str, Any],
    external_vector_db: Mapping[str, Any],
) -> dict[str, Any]:
    base = (
        dict(adapter.vector_index_audit_report)
        if isinstance(getattr(adapter, "vector_index_audit_report", None), Mapping)
        else {
            "enabled": False,
            "status": "adapter_did_not_report_vector_index_audit",
            "vector_surface": _clean(retrieval_surface_report.get("selected")) or "unknown",
            "semantic_quality_claim_allowed": False,
        }
    )
    comparisons = [
        output.get("retrieval_backend_comparison")
        for output in raw_outputs
        if isinstance(output.get("retrieval_backend_comparison"), Mapping)
    ]
    vector_invocations = [
        comparison.get("source_native_vector_invocation")
        for comparison in comparisons
        if isinstance(comparison.get("source_native_vector_invocation"), Mapping)
    ]
    target_rows = [
        comparison.get("post_retrieval_target_diagnostics")
        for comparison in comparisons
        if isinstance(comparison.get("post_retrieval_target_diagnostics"), Mapping)
    ]

    surface_comparisons = [
        output.get("retrieval_surface_comparison")
        for output in raw_outputs
        if isinstance(output.get("retrieval_surface_comparison"), Mapping)
    ]
    source_presence = [
        bool(((comparison.get("source_native") or {}).get("expected_evidence_in_corpus_normalized")))
        for comparison in surface_comparisons
        if isinstance(comparison.get("source_native"), Mapping)
    ]
    denominator = max(len(target_rows), 1)
    bm25_hits = sum(1 for row in target_rows if row.get("bm25_expected_anchor_retrieved"))
    vector_hits = sum(1 for row in target_rows if row.get("vector_expected_anchor_retrieved"))
    hybrid_hits = sum(1 for row in target_rows if row.get("hybrid_expected_anchor_retrieved"))

    def present_not_retrieved_count(field: str) -> int:
        return sum(
            1
            for present, row in zip(source_presence, target_rows, strict=False)
            if present and not bool(row.get(field))
        )

    vector_invoked_rows = sum(1 for row in vector_invocations if row.get("vector_backend_invoked"))
    vector_created_rows = sum(1 for row in vector_invocations if row.get("query_embedding_created_or_loaded"))
    vector_hydration_failures = sum(int(row.get("vector_hydration_failure_count") or 0) for row in vector_invocations)
    vector_hydration_successes = sum(int(row.get("vector_hydration_success_count") or 0) for row in vector_invocations)
    vector_candidate_count = sum(int(row.get("vector_top_k_count") or 0) for row in vector_invocations)
    query_invocation_passed = bool(vector_invocations and vector_invoked_rows == len(vector_invocations) and vector_created_rows == len(vector_invocations))
    hydration_passed = bool(vector_invocations and vector_candidate_count > 0 and vector_hydration_failures == 0)

    def avg_comparison(field: str) -> float:
        values = [float(comparison.get(field) or 0.0) for comparison in comparisons]
        return _average(values)

    target_presence = {
        "expected_fields_used_for_candidate_generation": False,
        "gold_fields_used_for_candidate_generation": False,
        "qrels_used_for_candidate_generation": False,
        "ids_used_for_candidate_generation": False,
        "baseline_topk_used_for_candidate_generation": False,
        "expected_fields_used_for_post_retrieval_diagnostics": any(
            bool(row.get("expected_fields_used_for_post_retrieval_diagnostics")) for row in target_rows
        ),
        "bm25_expected_anchor_recall@k_diagnostic": round(bm25_hits / denominator, 6),
        "vector_expected_anchor_recall@k_diagnostic": round(vector_hits / denominator, 6),
        "hybrid_expected_anchor_recall@k_diagnostic": round(hybrid_hits / denominator, 6),
        "bm25_target_span_present_but_not_retrieved_count": present_not_retrieved_count("bm25_expected_anchor_retrieved"),
        "vector_target_span_present_but_not_retrieved_count": present_not_retrieved_count("vector_expected_anchor_retrieved"),
        "hybrid_target_span_present_but_not_retrieved_count": present_not_retrieved_count("hybrid_expected_anchor_retrieved"),
    }
    base.update(
        {
            "external_vector_db_configured": bool(external_vector_db.get("configured")),
            "external_vector_db_invoked": bool(external_vector_db.get("invoked")),
            "external_vector_db_reachable": bool(external_vector_db.get("reachable")),
            "embedding_model": _clean(base.get("embedding_model") or retrieval_backend_report.get("embedding_model")),
            "embedding_dim": int(base.get("embedding_dim") or retrieval_backend_report.get("vector_dim") or 0),
            "embedding_device": _clean(base.get("embedding_device") or retrieval_backend_report.get("embedding_device")),
            "gpu_used_for_embedding": bool(base.get("gpu_used_for_embedding") or retrieval_backend_report.get("gpu_used_for_embedding")),
            "index_integrity_passed": bool(base.get("index_integrity_passed")),
            "query_invocation_passed": query_invocation_passed,
            "hydration_passed": hydration_passed,
            "hybrid_comparison_available": bool(backend_comparison.get("comparison_available")),
            "semantic_quality_claim_allowed": False,
            "query_invocation_summary": {
                "item_count": len(vector_invocations),
                "vector_backend_invoked_count": vector_invoked_rows,
                "query_embedding_created_or_loaded_count": vector_created_rows,
                "vector_candidate_count": vector_candidate_count,
                "vector_hydration_success_count": vector_hydration_successes,
                "vector_hydration_failure_count": vector_hydration_failures,
            },
            "bm25_vector_hybrid_comparison": {
                "comparison_available": bool(backend_comparison.get("comparison_available")),
                "bm25_candidate_count_avg": backend_comparison.get("bm25_candidate_count_avg"),
                "vector_candidate_count_avg": backend_comparison.get("vector_candidate_count_avg"),
                "hybrid_candidate_count_avg": backend_comparison.get("hybrid_candidate_count_avg"),
                "bm25_vector_topk_overlap_avg": backend_comparison.get("bm25_vector_topk_overlap_avg"),
                "bm25_only_candidate_count_avg": avg_comparison("bm25_only_candidate_count"),
                "vector_only_candidate_count_avg": avg_comparison("vector_only_candidate_count"),
                "hybrid_contains_vector_only_candidate_count_avg": avg_comparison("hybrid_contains_vector_only_candidate_count"),
                "hybrid_contains_bm25_only_candidate_count_avg": avg_comparison("hybrid_contains_bm25_only_candidate_count"),
                "vector_contribution_to_hybrid_topk_count_avg": avg_comparison("vector_contribution_to_hybrid_topk_count"),
                "bm25_contribution_to_hybrid_topk_count_avg": avg_comparison("bm25_contribution_to_hybrid_topk_count"),
                "vector_contribution_to_selected_topk_count_avg": avg_comparison("vector_contribution_to_selected_topk_count"),
                "bm25_contribution_to_selected_topk_count_avg": avg_comparison("bm25_contribution_to_selected_topk_count"),
                "bm25_retrieval_empty_rate": backend_comparison.get("bm25_retrieval_empty_rate"),
                "vector_retrieval_empty_rate": backend_comparison.get("vector_retrieval_empty_rate"),
                "hybrid_retrieval_empty_rate": backend_comparison.get("hybrid_retrieval_empty_rate"),
            },
            "target_presence_diagnostics": target_presence,
        }
    )
    return base


def build_final_rag_target_report() -> dict[str, Any]:
    return {
        "retrieval_surface": "source_native",
        "evidence_truth": "SourceAtom/EvidenceBundle",
        "candidate_generators": ["bm25", "vector", "hybrid", "bounded_layered_multi_search_future"],
        "vector_role": "candidate_generation_only",
        "bm25_role": "lexical_anchor_candidate_generation",
        "agentic_layer_role": "bounded_query_planning_and_evidence_validation_after_index_audit",
        "searchunit_searchview_role": "legacy_comparison_debug_only",
        "final_answer_policy": "use_validated_evidence_context_only; fail_closed_or_abstain_when_evidence_is_insufficient",
    }


def write_human_review_packet_csv(output_dir: Path, packet_rows: Sequence[Mapping[str, Any]]) -> tuple[Path, int]:
    path = output_dir / "human_review_packet.csv"
    fieldnames = list(EVIDENCE_MAPPING_PACKET_FIELDS)
    for row in packet_rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(str(key))
    output_dir.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in packet_rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return path, len(packet_rows)


MACHINE_MAPPING_RECOMMENDATIONS = frozenset(
    {
        "likely_accept",
        "possible_match",
        "review_needed",
        "likely_reject",
    }
)
HUMAN_DECISION_INPUT_FIELDS = (
    "human_mapping_decision",
    "human_accepted_doc_id",
    "human_accepted_chunk_id",
    "human_evidence_sufficient",
    "human_accept",
    "human_reject_reason",
    "human_expected_answer_override",
    "human_expected_evidence_override",
    "human_answerability_label",
    "human_relevance_label",
    "human_notes",
)
MACHINE_RECOMMENDATION_REJECT_FIELDS = (
    "human_mapping_decision",
    "human_evidence_sufficient",
    "human_accept",
    "human_answerability_label",
    "human_relevance_label",
)
ACCEPT_DECISIONS = frozenset({"accept", "accepted", "approve", "approved", "yes", "y", "true", "1", "use"})
REJECT_DECISIONS = frozenset({"reject", "rejected", "no", "n", "false", "0"})


def _strict_denominator_snapshot(items: Sequence[EvalItem]) -> dict[str, Any]:
    return {
        "strict_answer_denominator": sum(1 for item in items if item.answerability == "answerable" and item.has_expected_answer),
        "strict_evidence_denominator": sum(1 for item in items if item.answerability == "answerable" and item.has_expected_evidence),
        "strict_e2e_denominator": sum(
            1
            for item in items
            if item.answerability == "answerable" and item.has_expected_answer and item.has_expected_evidence
        ),
        "answerable_count": sum(1 for item in items if item.answerability == "answerable"),
        "unanswerable_count": sum(1 for item in items if item.answerability == "unanswerable"),
        "unknown_answerability_count": sum(1 for item in items if item.answerability == "unknown"),
        "expected_evidence_id_complete_count": sum(
            1
            for item in items
            for evidence in item.expected_evidence
            if bool(evidence.doc_id and evidence.chunk_id)
        ),
        "expected_evidence_row_count": sum(len(item.expected_evidence) for item in items),
    }


def _denominator_change_report(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    keys = sorted({*before.keys(), *after.keys()})
    return {
        key: {
            "before": before.get(key, 0),
            "after": after.get(key, 0),
            "delta": (after.get(key, 0) or 0) - (before.get(key, 0) or 0),
        }
        for key in keys
    }


def refresh_metric_tiers(summary: dict[str, Any]) -> None:
    summary["metric_tiers"] = {
        "strict": list((summary.get("strict_metrics") or {}).keys()),
        "provisional": list((summary.get("provisional_metrics") or {}).keys()),
        "inferred_answerable": list((summary.get("inferred_answerable_metrics") or {}).keys()),
        "diagnostic": [
            *(summary.get("diagnostic_metrics") or {}).keys(),
            *(summary.get("diagnostic_metric_details") or {}).keys(),
        ],
    }


def _is_accept_decision(value: Any) -> bool:
    return _clean(value).casefold() in ACCEPT_DECISIONS


def _is_reject_decision(value: Any) -> bool:
    return _clean(value).casefold() in REJECT_DECISIONS


def _reviewed_row_query_id(row: Mapping[str, Any]) -> str:
    return _clean(row.get("query_id") or row.get("item_id") or row.get("id"))


def _reviewed_row_evidence_index(row: Mapping[str, Any]) -> int:
    raw = _clean(row.get("expected_evidence_index") or row.get("expected_evidence_idx"))
    if not raw:
        return 0
    try:
        index = int(raw)
    except ValueError as exc:
        raise DatasetSchemaError(f"reviewed evidence mapping has invalid expected_evidence_index: {raw}") from exc
    if index < 0:
        raise DatasetSchemaError(f"reviewed evidence mapping has negative expected_evidence_index: {raw}")
    return index


def _explicit_human_field_values(row: Mapping[str, Any]) -> dict[str, str]:
    return {field: _clean(row.get(field)) for field in HUMAN_DECISION_INPUT_FIELDS if _clean(row.get(field))}


def _validate_reviewed_mapping_row(row: Mapping[str, Any], *, row_number: int) -> dict[str, str]:
    human_values = _explicit_human_field_values(row)
    if not human_values:
        return {}
    machine = _clean(row.get("machine_recommendation")).casefold()
    for field in MACHINE_RECOMMENDATION_REJECT_FIELDS:
        value = _clean(row.get(field)).casefold()
        if value and (value in MACHINE_MAPPING_RECOMMENDATIONS or (machine and value == machine)):
            raise DatasetSchemaError(
                f"reviewed evidence mapping row {row_number}: machine recommendation value cannot be used as a human decision"
            )
    query_id = _reviewed_row_query_id(row)
    if not query_id:
        raise DatasetSchemaError(f"reviewed evidence mapping row {row_number}: missing query_id")
    answerability = _clean(row.get("human_answerability_label")).casefold()
    if answerability and answerability not in ANSWERABILITY_VALUES:
        raise DatasetSchemaError(
            f"reviewed evidence mapping row {row_number}: human_answerability_label must be one of {sorted(ANSWERABILITY_VALUES)}"
        )
    accepted = _is_accept_decision(row.get("human_accept")) or _is_accept_decision(row.get("human_mapping_decision"))
    if accepted:
        doc_id = _clean(row.get("human_accepted_doc_id") or row.get("candidate_doc_id"))
        chunk_id = _clean(row.get("human_accepted_chunk_id") or row.get("candidate_chunk_id"))
        evidence_override = _clean(row.get("human_expected_evidence_override"))
        answer_override = _clean(row.get("human_expected_answer_override"))
        if not (doc_id or chunk_id or evidence_override or answer_override):
            raise DatasetSchemaError(
                f"reviewed evidence mapping row {row_number}: accepted mapping requires candidate IDs or explicit human override"
            )
    return human_values


def _read_reviewed_evidence_mapping_csv(path: Path) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        raise DatasetSchemaError(f"reviewed evidence mapping CSV not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise DatasetSchemaError(f"reviewed evidence mapping CSV has no header: {path}")
        rows = [dict(row) for row in reader]
    reviewed_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        human_values = _validate_reviewed_mapping_row(row, row_number=index)
        if human_values:
            copied = dict(row)
            copied["_human_values"] = human_values
            copied["_row_number"] = index
            reviewed_rows.append(copied)
    if not reviewed_rows:
        raise DatasetSchemaError("reviewed evidence mapping CSV requires at least one explicit human decision field")
    return reviewed_rows, len(rows)


def _empty_reviewed_mapping_summary(path: Path | None = None) -> dict[str, Any]:
    return {
        "enabled": bool(path),
        "input_path": path.as_posix() if path else "",
        "applied": False,
        "row_count": 0,
        "source_row_count": 0,
        "accepted_mapping_count": 0,
        "rejected_mapping_count": 0,
        "answerability_label_applied_count": 0,
        "expected_answer_override_count": 0,
        "expected_evidence_text_override_count": 0,
        "machine_recommendation_treated_as_gold": False,
        "gold_or_qrels_mutation": False,
        "human_decision_fields_filled_by_codex": False,
        "changes": [],
        "rejections": [],
        "guardrails": {
            "original_dataset_overwritten": False,
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "expected_fields_used_for_candidate_generation": False,
            "machine_recommendation_not_gold": True,
        },
    }


def apply_reviewed_evidence_mapping(
    items: Sequence[EvalItem],
    *,
    reviewed_mapping_csv: Path | None,
) -> tuple[list[EvalItem], dict[str, Any]]:
    if reviewed_mapping_csv is None:
        return list(items), _empty_reviewed_mapping_summary(None)
    reviewed_rows, source_row_count = _read_reviewed_evidence_mapping_csv(reviewed_mapping_csv)
    by_id = {item.id: item for item in items}
    derived = {item.id: item for item in items}
    changes: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    accepted_count = 0
    rejected_count = 0
    answerability_count = 0
    answer_override_count = 0
    evidence_override_count = 0
    for row in reviewed_rows:
        query_id = _reviewed_row_query_id(row)
        item = derived.get(query_id)
        if item is None:
            raise DatasetSchemaError(f"reviewed evidence mapping row {row.get('_row_number')}: unknown query_id {query_id}")
        evidence_index = _reviewed_row_evidence_index(row)
        change_types: list[str] = []
        reason: list[str] = []
        expected_evidence = list(item.expected_evidence)
        accepted = _is_accept_decision(row.get("human_accept")) or _is_accept_decision(row.get("human_mapping_decision"))
        rejected = _is_reject_decision(row.get("human_accept")) or _is_reject_decision(row.get("human_mapping_decision"))
        answerability = _clean(row.get("human_answerability_label")).casefold()
        expected_answer_override = _clean(row.get("human_expected_answer_override"))
        expected_evidence_override = _clean(row.get("human_expected_evidence_override"))
        candidate_doc_id = _clean(row.get("human_accepted_doc_id") or row.get("candidate_doc_id"))
        candidate_chunk_id = _clean(row.get("human_accepted_chunk_id") or row.get("candidate_chunk_id"))
        if rejected and not accepted:
            rejected_count += 1
            rejections.append(
                {
                    "query_id": query_id,
                    "expected_evidence_index": evidence_index,
                    "reason": _clean(row.get("human_reject_reason")) or "human_rejected_mapping",
                    "candidate_doc_id": candidate_doc_id,
                    "candidate_chunk_id": candidate_chunk_id,
                }
            )
        if accepted:
            if evidence_index >= len(expected_evidence):
                raise DatasetSchemaError(
                    f"reviewed evidence mapping row {row.get('_row_number')}: expected_evidence_index out of range"
                )
            existing = expected_evidence[evidence_index]
            expected_evidence[evidence_index] = ExpectedEvidence(
                doc_id=candidate_doc_id or existing.doc_id,
                chunk_id=candidate_chunk_id or existing.chunk_id,
                text=expected_evidence_override or existing.text or _clean(row.get("expected_evidence_text")),
                required=existing.required,
            )
            accepted_count += 1
            change_types.append("expected_evidence_id_mapping_applied")
            reason.append("human_accept")
            if expected_evidence_override:
                evidence_override_count += 1
                change_types.append("expected_evidence_text_override_applied")
        if expected_answer_override:
            answer_override_count += 1
            change_types.append("expected_answer_override_applied")
        if answerability:
            answerability_count += 1
            change_types.append("answerability_label_applied")
        if not change_types:
            continue
        source_row = dict(item.source_row)
        prior_changes = list(source_row.get("reviewed_mapping_change_types") or [])
        source_row.update(
            {
                "reviewed_mapping_applied": True,
                "reviewed_mapping_input_path": reviewed_mapping_csv.as_posix(),
                "reviewed_mapping_change_types": sorted(set([*prior_changes, *change_types])),
            }
        )
        derived[query_id] = replace(
            item,
            answerability=answerability or item.answerability,
            expected_answer=expected_answer_override or item.expected_answer,
            expected_evidence=tuple(expected_evidence),
            has_answerability_label=bool(answerability) or item.has_answerability_label,
            source_row=source_row,
        )
        changes.append(
            {
                "query_id": query_id,
                "expected_evidence_index": evidence_index,
                "candidate_doc_id": candidate_doc_id,
                "candidate_chunk_id": candidate_chunk_id,
                "candidate_text_hash": _clean(row.get("candidate_text_hash") or row.get("candidate_full_text_hash")),
                "change_types": sorted(set(change_types)),
                "reason": "; ".join(reason) or "explicit_human_reviewed_mapping_input",
                "human_notes": _clean(row.get("human_notes")),
            }
        )
    summary = _empty_reviewed_mapping_summary(reviewed_mapping_csv)
    summary.update(
        {
            "applied": bool(changes),
            "row_count": len(reviewed_rows),
            "source_row_count": source_row_count,
            "accepted_mapping_count": accepted_count,
            "rejected_mapping_count": rejected_count,
            "answerability_label_applied_count": answerability_count,
            "expected_answer_override_count": answer_override_count,
            "expected_evidence_text_override_count": evidence_override_count,
            "changes": changes,
            "rejections": rejections,
        }
    )
    return [derived[item.id] if item.id in derived else by_id[item.id] for item in items], summary


def write_reviewed_mapping_patch_artifact(output_dir: Path, reviewed_mapping: Mapping[str, Any]) -> Path:
    path = output_dir / "reviewed_evidence_mapping_patch.json"
    payload = {
        "schema_version": "actual_rag_eval.reviewed_evidence_mapping_patch.v1",
        "input_path": reviewed_mapping.get("input_path", ""),
        "row_count": reviewed_mapping.get("row_count", 0),
        "accepted_mapping_count": reviewed_mapping.get("accepted_mapping_count", 0),
        "answerability_label_applied_count": reviewed_mapping.get("answerability_label_applied_count", 0),
        "gold_or_qrels_mutation": False,
        "machine_recommendation_treated_as_gold": False,
        "changes": reviewed_mapping.get("changes") or [],
        "rejections": reviewed_mapping.get("rejections") or [],
    }
    write_json(path, payload)
    return path


def _artifact_contract(
    *,
    output_mode: str,
    report_path: Path,
    legacy_written: bool,
    human_review_packet_path: Path | None,
    reviewed_mapping_patch_path: Path | None = None,
) -> dict[str, Any]:
    return {
        "output_mode": output_mode,
        "primary_report_json": report_path.as_posix() if output_mode in {"single", "both"} else "",
        "single_artifact_default": output_mode == "single",
        "runstore_only": output_mode == "runstore",
        "legacy_sidecars_written": bool(legacy_written),
        "human_review_packet_exception": bool(human_review_packet_path),
        "human_review_packet_path": human_review_packet_path.as_posix() if human_review_packet_path else "",
        "reviewed_mapping_patch_exception": bool(reviewed_mapping_patch_path),
        "reviewed_mapping_patch_path": reviewed_mapping_patch_path.as_posix() if reviewed_mapping_patch_path else "",
        "routine_run_file_policy": (
            "run.sqlite_only_no_report_json"
            if output_mode == "runstore"
            else "report.json_only_unless_legacy_human_review_packet_or_reviewed_mapping_input_requested"
        ),
        "legacy_artifacts_allowed_only_by_output_mode": True,
    }


def _source_native_legacy_cleanup_inventory() -> list[dict[str, Any]]:
    return [
        {
            "category": "searchunit_searchview_runtime_reference",
            "subject": "SurfaceComparingRagAdapter, RepoCurrentBm25Adapter, RepoCurrentHybridAdapter",
            "classification": "EXPLICIT_LEGACY_DEBUG_KEEP",
            "decision": "keep_fenced",
            "rationale": "SearchUnit/SearchView remains available only behind explicit legacy/debug comparison paths.",
        },
        {
            "category": "searchunit_searchview_runtime_reference",
            "subject": "SourceNativeCorpusLoader, SourceNativeHybridAdapter",
            "classification": "ACTIVE_SOURCE_NATIVE_KEEP",
            "decision": "keep_routine",
            "rationale": "SourceAtom/EvidenceBundle-backed source-native units are the routine actual-RAG surface when available.",
        },
        {
            "category": "searchunit_searchview_test_reference",
            "subject": "ai/tests/test_actual_rag_eval_metric_generation.py",
            "classification": "EXPLICIT_LEGACY_DEBUG_KEEP",
            "decision": "keep_focused_contract_tests",
            "rationale": "Tests keep the legacy/debug fence observable without restoring SearchUnit/SearchView as a routine candidate surface.",
        },
        {
            "category": "searchunit_searchview_docs_reference",
            "subject": "ignored local rolling handoff notes; ai/eval/README.md; ai/scripts/README.md",
            "classification": "DOCS_ONLY_UPDATE",
            "decision": "compact_stale_wording",
            "rationale": "Worker-authored notes and reader docs may describe source-native routine behavior, but runtime code must not depend on local docs paths.",
        },
        {
            "category": "actual_rag_sidecar_writer",
            "subject": "output_mode=legacy|both sidecar writer block",
            "classification": "EXPLICIT_LEGACY_DEBUG_KEEP",
            "decision": "fence_by_output_mode",
            "rationale": "Routine output-mode single writes report.json only; old JSONL/Markdown/evidence sidecars require explicit legacy mode.",
        },
        {
            "category": "legacy_report_writer",
            "subject": "rag_eval_items.jsonl, rag_eval_summary.json, rag_eval_report.md",
            "classification": "EXPLICIT_LEGACY_DEBUG_KEEP",
            "decision": "legacy_mode_only",
            "rationale": "Historical report shape is retained for explicit legacy compatibility and excluded from routine single output.",
        },
        {
            "category": "legacy_cli_alias",
            "subject": "--legacy-surface-comparison; --retrieval-surface searchunit-searchview",
            "classification": "EXPLICIT_LEGACY_COMPARISON_KEEP",
            "decision": "keep_explicit_check_only",
            "rationale": "The legacy comparison flag is the intentional opt-in boundary for SearchUnit/SearchView diagnostics.",
        },
        {
            "category": "legacy_cli_alias",
            "subject": "--retrieval-surface searchunit-searchview without --legacy-surface-comparison",
            "classification": "DEPRECATE_FAIL_CLOSED",
            "decision": "fail_closed",
            "rationale": "SearchUnit/SearchView cannot be selected silently as a routine actual-RAG surface.",
        },
        {
            "category": "stale_generated_ignored_artifact",
            "subject": "reports/rag_eval/rag-ingestion/** and reports/rag_eval/**",
            "classification": "REVIEW_MANUAL_HOLD",
            "decision": "hold_unless_unreferenced",
            "rationale": "Ignored generated diagnostics may still be registry-, latest-, docs-, or test-readable.",
        },
        {
            "category": "transient_cache_build_artifact",
            "subject": ".pytest_cache; __pycache__; temporary fixture directories",
            "classification": "SAFE_TRANSIENT_DELETE",
            "decision": "delete_when_present_after_path_check",
            "rationale": "Caches and temporary fixture directories are regenerable and not diagnostic evidence.",
        },
        {
            "category": "routine_generated_sidecar",
            "subject": "CSV/JSONL/Markdown/evidence sidecars in output-mode single",
            "classification": "SAFE_GENERATED_DELETE",
            "decision": "delete_if_created_by_routine_single_run",
            "rationale": "Routine actual-RAG single output has a one-file report.json contract.",
        },
        {
            "category": "protected_namespace_reference",
            "subject": "ai/eval/eval_queries; ai/eval/source_registry; ai/eval/indexes; gold/qrels/labels/answerability/expected/denominator/current",
            "classification": "PROTECTED_HOLD",
            "decision": "do_not_modify",
            "rationale": "Cleanup must not mutate source truth, gold policy, qrels, labels, answerability, expected fields, denominators, indexes, or current.",
        },
    ]


def _classification_counts(entries: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {classification: 0 for classification in SOURCE_NATIVE_LEGACY_CLEANUP_CLASSIFICATIONS}
    for entry in entries:
        classification = _clean(entry.get("classification"))
        if classification:
            counts[classification] = counts.get(classification, 0) + 1
    return counts


def build_source_native_legacy_cleanup_sections(summary: Mapping[str, Any]) -> dict[str, Any]:
    retrieval_surface = summary.get("retrieval_surface")
    if not isinstance(retrieval_surface, Mapping):
        retrieval_surface = {}
    artifact_contract = summary.get("artifact_contract")
    if not isinstance(artifact_contract, Mapping):
        artifact_contract = {}
    selected_surface = _clean(retrieval_surface.get("selected"))
    auto_fallback = bool(retrieval_surface.get("auto_fallback_to_searchunit_searchview"))
    routine_candidate_surface_enabled = False
    source_native_hard_switch_preserved = (
        selected_surface == "source_native"
        and bool(retrieval_surface.get("source_native_available", selected_surface == "source_native"))
        and not auto_fallback
        and not routine_candidate_surface_enabled
    )
    legacy_sidecars_written = bool(artifact_contract.get("legacy_sidecars_written"))
    human_review_packet_written = bool(artifact_contract.get("human_review_packet_exception"))
    reviewed_mapping_patch_written = bool(artifact_contract.get("reviewed_mapping_patch_exception"))
    output_mode = _clean(artifact_contract.get("output_mode"))
    return {
        "legacy_cleanup": {
            "enabled": True,
            "searchunit_searchview_routine_candidate_surface_enabled": routine_candidate_surface_enabled,
            "searchunit_searchview_role": "explicit_legacy_comparison_debug_only",
            "auto_fallback_to_searchunit_searchview": False,
            "source_native_hard_switch_preserved": source_native_hard_switch_preserved,
        },
        "artifact_cleanup": {
            "output_mode_single_report_json_only": output_mode == "single"
            and not legacy_sidecars_written
            and not human_review_packet_written
            and not reviewed_mapping_patch_written,
            "legacy_sidecars_routine_disabled": True,
            "human_review_packet_exception_preserved": True,
            "reviewed_mapping_patch_exception_preserved": True,
            "raw_prompt_payload_written": bool(summary.get("raw_prompt_payload_written")),
            "raw_response_payload_written": bool(summary.get("raw_response_payload_written")),
            "legacy_sidecars_written_in_this_run": legacy_sidecars_written,
            "human_review_packet_written_in_this_run": human_review_packet_written,
            "reviewed_mapping_patch_written_in_this_run": reviewed_mapping_patch_written,
        },
        "runner_alias_cleanup": {
            "current_moved": False,
            "aliases_removed": [],
            "aliases_deprecated_fail_closed": [
                "--retrieval-surface searchunit-searchview without --legacy-surface-comparison",
            ],
            "aliases_kept_check_only": [
                "--legacy-surface-comparison",
                "--retrieval-surface searchunit-searchview",
                "--output-mode legacy",
                "--output-mode both",
            ],
            "manual_hold_aliases": [
                "--write-evidence-mapping-packet",
                "--index current",
            ],
        },
    }


def _cleanup_guardrails_from_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    source_guardrails = summary.get("guardrails")
    guardrails = dict(source_guardrails) if isinstance(source_guardrails, Mapping) else {}
    guardrails.update(
        {
            "non_production": True,
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
            "current_moved": False,
            "protected_namespaces_touched": [],
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
            "gold_or_qrels_mutation": False,
            "human_decision_fields_filled_by_codex": False,
            "gold_fields_used_for_candidate_generation": False,
            "expected_fields_used_for_candidate_generation": False,
            "qrels_used_for_candidate_generation": False,
            "answerability_labels_used_for_candidate_generation": False,
            "ids_used_for_candidate_generation": False,
            "query_id_used_for_candidate_generation": False,
            "row_id_used_for_candidate_generation": False,
            "target_id_used_for_candidate_generation": False,
            "baseline_topk_used_for_candidate_generation": False,
            "retriever_oracle_shortcut_used": False,
        }
    )
    return guardrails


def build_source_native_legacy_cleanup_report(
    *,
    routine_summary: Mapping[str, Any],
    changed_files: Sequence[str] = (),
    deleted_files: Sequence[str] = (),
    explicitly_held_files: Sequence[str] = (),
    temporary_files_removed: Sequence[str] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    validate_actual_rag_guardrails(routine_summary)
    sections = build_source_native_legacy_cleanup_sections(routine_summary)
    inventory = _source_native_legacy_cleanup_inventory()
    classification_counts = _classification_counts(inventory)
    guardrails = _cleanup_guardrails_from_summary(routine_summary)
    routine_artifact_contract = routine_summary.get("artifact_contract")
    if not isinstance(routine_artifact_contract, Mapping):
        routine_artifact_contract = {}
    report = {
        "schema_version": "actual_rag_eval.source_native_legacy_cleanup.v1",
        "run_id": SOURCE_NATIVE_LEGACY_CLEANUP_RUN_ID,
        "generated_at": generated_at or utc_now_iso(),
        "non_production": True,
        "cleanup_scope": "source_native_actual_rag_legacy_searchunit_searchview_cleanup_nonprod",
        "routine_run_id": _clean(routine_summary.get("run_id")),
        "routine_artifact_contract": dict(routine_artifact_contract),
        "inventory": inventory,
        "classification_counts": classification_counts,
        "cleanup_decisions": {
            "changed_files": sorted(_clean(path) for path in changed_files if _clean(path)),
            "deletions": sorted(_clean(path) for path in deleted_files if _clean(path)),
            "explicit_holds": sorted(_clean(path) for path in explicitly_held_files if _clean(path)),
            "temporary_files_removed": sorted(_clean(path) for path in temporary_files_removed if _clean(path)),
            "generated_artifacts_deleted": [],
            "protected_holds": [
                "ai/eval/eval_queries",
                "ai/eval/source_registry",
                "ai/eval/indexes",
                "gold/qrels/labels/answerability/expected/denominator/current",
                "reports/rag_eval/latest*.json",
                "reports/rag_eval/runs.jsonl",
                "reports/rag_eval/rag-ingestion/status.jsonl",
            ],
        },
        "holds": {
            "explicit_legacy_debug": [
                entry["subject"]
                for entry in inventory
                if entry.get("classification") in {"EXPLICIT_LEGACY_DEBUG_KEEP", "EXPLICIT_LEGACY_COMPARISON_KEEP"}
            ],
            "protected": [
                entry["subject"] for entry in inventory if entry.get("classification") == "PROTECTED_HOLD"
            ],
            "manual_review": [
                entry["subject"] for entry in inventory if entry.get("classification") == "REVIEW_MANUAL_HOLD"
            ],
        },
        "protected_namespace_checks": {
            "protected_namespaces_touched": [],
            "gold_qrels_labels_answerability_expected_denominator_current_untouched": True,
            "source_registry_untouched": True,
            "source_native_indexes_untouched_by_cleanup": True,
            "production_config_untouched": True,
        },
        "remaining_debt": [
            "source_native_ranking_query_formulation",
            "bge_m3_artifacts_held_read_only_future_remeasurement_when_explicitly_opened_or_not_current",
            "extractive_v1_answer_generation_replacement",
        ],
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": guardrails,
    }
    report.update(sections)
    validate_actual_rag_guardrails(report)
    return report


def write_source_native_legacy_cleanup_report(
    report_path: Path | str = SOURCE_NATIVE_LEGACY_CLEANUP_REPORT_PATH,
    *,
    routine_summary: Mapping[str, Any],
    changed_files: Sequence[str] = (),
    deleted_files: Sequence[str] = (),
    explicitly_held_files: Sequence[str] = (),
    temporary_files_removed: Sequence[str] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    report = build_source_native_legacy_cleanup_report(
        routine_summary=routine_summary,
        changed_files=changed_files,
        deleted_files=deleted_files,
        explicitly_held_files=explicitly_held_files,
        temporary_files_removed=temporary_files_removed,
        generated_at=generated_at,
    )
    write_json(Path(report_path), report)
    return report
