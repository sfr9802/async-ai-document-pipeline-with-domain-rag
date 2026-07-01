from __future__ import annotations

from ai.eval.actual_rag_core_base import *
from ai.eval.actual_rag_core_xlsx import *

QUALITY_GATE_REPORT_SCHEMA_VERSION = "actual_rag_eval.legacy_real_rag_quality_gate.v1"
SELECTED_EVIDENCE_COMPOSER_PROVIDER = "selected-evidence-deterministic-v1"
SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROVIDER = "selected-evidence-local-llm-v1"
SELECTED_EVIDENCE_COMPOSER_INPUT_POLICY = (
    "query_text_and_selected_sourceatom_evidence_only_no_gold_qrels_labels_ids_or_baseline"
)
SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROMPT_VERSION = "selected_evidence_local_llm_composer_v1"
SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROMPT_TEMPLATE = """You are a non-production selected-evidence answer composer.
Return exactly one JSON object with keys: answer (string) and citation_evidence_ids (array of strings).
Use only the selected SourceAtom/EvidenceBundle evidence in the payload. Do not use outside knowledge.
The answer string must be one short natural, query-context sentence in the query language unless the query asks for a list or table.
Answer only the requested facet. Do not add background profile facts, related attributes, surrounding facts, entity summaries, or unsupported details.
If selected evidence supports extra facts that the question did not ask for, omit them.
Do not return only a terse fragment unless the query explicitly asks for a bare value.
Do not include audit headers, citation blocks, markdown sections, or source dumps in the answer string.
If the selected evidence is insufficient, return an empty answer and an empty citation_evidence_ids array.

Payload:
{payload}
"""
SELECTED_EVIDENCE_ANSWER_DISCIPLINE_INPUT_POLICY = (
    "query_text_selected_evidence_answer_only_no_gold_qrels_labels_ids_or_baseline"
)
SELECTED_EVIDENCE_ANSWER_DISCIPLINE_STATUSES = frozenset(
    {
        "clean_supported",
        "supported_core_with_unsupported_extra",
        "query_irrelevant_supported_detail",
        "local_llm_rejected_then_deterministic_overexpanded",
        "citation_id_mismatch_or_missing",
        "anchor_morphology_false_negative",
        "unsupported_or_empty",
        "true_insufficient_evidence",
    }
)
SELECTED_EVIDENCE_COMPOSER_RETRY_MODES = frozenset({"off", "bounded-once"})
SELECTED_EVIDENCE_COMPOSER_RETRY_INPUT_POLICY = (
    "query_text_selected_evidence_missing_query_focus_anchors_previous_bounded_answer_preview_only_no_gold_qrels_labels_ids_or_baseline"
)
SELECTED_EVIDENCE_LOCAL_LLM_RETRY_PROMPT_VERSION = "selected_evidence_local_llm_composer_retry_v1"
SELECTED_EVIDENCE_LOCAL_LLM_RETRY_PROMPT_TEMPLATE = """You are a non-production selected-evidence answer composer retry.
Return exactly one JSON object with keys: answer (string) and citation_evidence_ids (array of strings).
Use only the query, selected SourceAtom/EvidenceBundle evidence, missing query-focus anchors, and previous bounded answer preview in the payload.
Do not use outside knowledge. Do not use any hidden gold, labels, qrels, row ids, target ids, baseline top-k, or legacy outputs.
The answer string must be one short natural, query-context sentence in the query language unless the query asks for a list or table.
Answer only the requested facet. Remove unsupported details and omit selected-evidence facts that the question did not ask for.
Do not return only a terse fragment unless the query explicitly asks for a bare value.
Do not include audit headers, citation blocks, markdown sections, or source dumps in the answer string.
If the selected evidence is insufficient, return an empty answer and an empty citation_evidence_ids array.

Payload:
{payload}
"""
ANSWER_COMPOSER_PROVIDERS = frozenset(
    {"extractive-v1", SELECTED_EVIDENCE_COMPOSER_PROVIDER, SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROVIDER}
)
SELECTED_EVIDENCE_CITATION_FORMATS = frozenset(
    {"compact", "evidence-id", "source-locator", "markdown-portfolio"}
)


def _query_id(row: Mapping[str, Any]) -> str:
    return _clean(row.get("id") or row.get("query_id") or row.get("queryId"))


def _contexts_from_row(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(context) for context in _as_list(row.get("retrieved_contexts")) if isinstance(context, Mapping)]


def _citations_from_row(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(citation) for citation in _as_list(row.get("citations")) if isinstance(citation, Mapping)]


def _context_identity(row: Mapping[str, Any]) -> str:
    for key in (
        "evidence_bundle_id",
        "source_atom_id",
        "search_unit_id",
        "search_view_id",
        "chunk_id",
        "doc_id",
    ):
        value = _clean(row.get(key))
        if value:
            return value
    text_hash = _clean(row.get("source_text_sha256") or row.get("text_sha256")) or _sha256_text(row.get("text"))
    return f"text_sha256:{text_hash}" if text_hash else ""


def _legacy_context_identity(row: Mapping[str, Any]) -> str:
    for key in ("search_unit_id", "search_view_id", "chunk_id", "doc_id", "source_atom_id", "evidence_bundle_id"):
        value = _clean(row.get(key))
        if value:
            return value
    return _context_identity(row)


def _context_id_list(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    seen: set[str] = set()
    ids: list[str] = []
    for row in rows:
        identity = _context_identity(row)
        if identity and identity not in seen:
            ids.append(identity)
            seen.add(identity)
    return ids


def _legacy_context_id_list(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    seen: set[str] = set()
    ids: list[str] = []
    for row in rows:
        identity = _legacy_context_identity(row)
        if identity and identity not in seen:
            ids.append(identity)
            seen.add(identity)
    return ids


def _field_id_list(rows: Sequence[Mapping[str, Any]], field: str) -> list[str]:
    seen: set[str] = set()
    ids: list[str] = []
    for row in rows:
        value = _clean(row.get(field))
        if value and value not in seen:
            ids.append(value)
            seen.add(value)
    return ids


def _doc_ids(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    return {_clean(row.get("doc_id") or row.get("docId") or row.get("document_id")) for row in rows if _clean(row.get("doc_id") or row.get("docId") or row.get("document_id"))}


def _text_hashes(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    seen: set[str] = set()
    hashes: list[str] = []
    for row in rows:
        digest = _clean(row.get("source_text_sha256") or row.get("text_sha256")) or _sha256_text(row.get("text"))
        if digest and digest not in seen:
            hashes.append(digest)
            seen.add(digest)
    return hashes


SOURCE_NATIVE_RUNTIME_TEXT_FIELDS = (
    "text",
    "citation_text",
    "display_text",
    "embedding_text",
    "bm25_text",
)
SOURCE_NATIVE_RUNTIME_FORBIDDEN_FILENAME_RE = re.compile(
    r"(?i)(?:^|[\s=:/\\|])[^|;\n\r]*\.(?:xlsx|xlsm|xls|pdf)(?:\b|$)"
)


def _source_native_context_requires_runtime_text_sanitization(row: Mapping[str, Any]) -> bool:
    source_family = _clean(row.get("source_family") or row.get("family")).upper()
    if source_family in {"XLSX", "PDF"}:
        return True
    return any(
        _clean(row.get(field))
        for field in (
            "sheet",
            "cell_range",
            "cell",
            "row_label",
            "column_label",
            "target_column",
            "page_number",
            "bbox",
        )
    )


def _source_native_runtime_forbidden_text_segment(segment: str) -> bool:
    clean_segment = _clean(segment)
    if not clean_segment:
        return False
    if _xlsx_locator_forbidden_text_fields(clean_segment):
        return True
    key, separator, _value = clean_segment.partition("=")
    if separator and _canonical_xlsx_locator_field_name(key) in SOURCE_DERIVED_EVIDENCE_FORBIDDEN_FIELDS:
        return True
    return bool(SOURCE_NATIVE_RUNTIME_FORBIDDEN_FILENAME_RE.search(clean_segment))


def _strip_source_native_runtime_forbidden_text_segments(text: str) -> str:
    clean_text = _clean(text)
    if not clean_text:
        return ""
    segments = [_clean(segment) for segment in re.split(r"\s+\|\s+|\n+", clean_text) if _clean(segment)]
    if not segments:
        return ""
    safe_segments = [
        segment for segment in segments if not _source_native_runtime_forbidden_text_segment(segment)
    ]
    return " | ".join(safe_segments)


def _source_native_runtime_forbidden_key(key: Any) -> bool:
    canonical = _canonical_xlsx_locator_field_name(key)
    return canonical in SOURCE_DERIVED_EVIDENCE_FORBIDDEN_FIELDS


def _source_native_runtime_forbidden_scalar(value: Any) -> bool:
    if isinstance(value, (Mapping, list, tuple)):
        return False
    clean_value = _clean(value)
    if not clean_value:
        return False
    return _source_native_runtime_forbidden_text_segment(clean_value) or _looks_like_local_path(clean_value)


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


def _safe_same_row_period_cells_json(value: Any) -> str:
    parsed = _parse_jsonish(value)
    if not isinstance(parsed, list):
        return ""
    cells: list[dict[str, Any]] = []
    for cell in parsed:
        if not isinstance(cell, Mapping):
            return ""
        keys = {str(key) for key in cell if _clean(key)}
        if keys != SAME_ROW_PERIOD_CELL_PACKET_FIELDS:
            return ""
        if _clean(cell.get("schema_version")) != "actual_rag_eval.xlsx.same_row_period_cell.v1":
            return ""
        if _clean(cell.get("provenance_policy")) != "source_owned_same_row_period_cell_v1":
            return ""
        required = (
            "source_atom_id",
            "doc_id",
            "sheet",
            "cell_range",
            "cell",
            "row_index_1based",
            "column_label",
            "raw_value",
            "parsed_date",
            "year",
            "month",
            "day",
        )
        if any(not _clean(cell.get(field)) for field in required):
            return ""
        raw_value = _clean(cell.get("raw_value"))
        parsed_date = _clean(cell.get("parsed_date"))
        string_fields = {
            "source_atom_id": _clean(cell.get("source_atom_id")),
            "doc_id": _clean(cell.get("doc_id")),
            "sheet": _clean(cell.get("sheet")),
            "cell_range": _clean(cell.get("cell_range")),
            "cell": _clean(cell.get("cell")),
            "row_index_1based": _clean(cell.get("row_index_1based")),
            "row_label": _clean(cell.get("row_label")),
            "column_label": _clean(cell.get("column_label")),
            "raw_value": raw_value,
            "parsed_date": parsed_date,
        }
        if any(_source_native_runtime_forbidden_scalar(field_value) for field_value in string_fields.values()):
            return ""
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", parsed_date):
            return ""
        try:
            year = int(cell.get("year"))
            month = int(cell.get("month"))
            day = int(cell.get("day"))
        except (TypeError, ValueError):
            return ""
        if parsed_date != f"{year:04d}-{month:02d}-{day:02d}":
            return ""
        cells.append(
            {
                "schema_version": "actual_rag_eval.xlsx.same_row_period_cell.v1",
                "provenance_policy": "source_owned_same_row_period_cell_v1",
                **string_fields,
                "year": year,
                "month": month,
                "day": day,
            }
        )
    return json.dumps(cells, ensure_ascii=False, sort_keys=True) if cells else ""


def _sanitize_source_native_runtime_value(value: Any, *, source_native_context: bool) -> Any:
    if isinstance(value, Mapping):
        active_source_native_context = source_native_context or _source_native_context_requires_runtime_text_sanitization(value)
        sanitized: dict[str, Any] = {}
        for key, nested_value in value.items():
            if active_source_native_context and _source_native_runtime_forbidden_key(key):
                continue
            canonical_key = _canonical_xlsx_locator_field_name(key)
            if active_source_native_context and canonical_key in SOURCE_NATIVE_RUNTIME_TEXT_FIELDS:
                sanitized[str(key)] = _strip_source_native_runtime_forbidden_text_segments(_clean(nested_value))
                continue
            if active_source_native_context and canonical_key == "same_row_period_cells_json":
                period_cells_json = _safe_same_row_period_cells_json(nested_value)
                if period_cells_json:
                    sanitized[str(key)] = period_cells_json
                continue
            if active_source_native_context and _source_native_runtime_forbidden_scalar(nested_value):
                continue
            sanitized[str(key)] = _sanitize_source_native_runtime_value(
                nested_value,
                source_native_context=active_source_native_context,
            )
        return sanitized
    if isinstance(value, list):
        return [
            _sanitize_source_native_runtime_value(item, source_native_context=source_native_context)
            for item in value
        ]
    if isinstance(value, tuple):
        return [
            _sanitize_source_native_runtime_value(item, source_native_context=source_native_context)
            for item in value
        ]
    if source_native_context and _source_native_runtime_forbidden_scalar(value):
        return ""
    return value


def _runtime_safe_evidence_context(row: Mapping[str, Any]) -> dict[str, Any]:
    safe = dict(row)
    for field in SOURCE_DERIVED_EVIDENCE_FORBIDDEN_FIELDS:
        safe.pop(field, None)
    if not _source_native_context_requires_runtime_text_sanitization(row):
        return safe
    return _sanitize_source_native_runtime_value(safe, source_native_context=True)


def _gate_row_text(row: Mapping[str, Any]) -> str:
    text = _clean(
        row.get("text")
        or row.get("citation_text")
        or row.get("display_text")
        or row.get("embedding_text")
        or row.get("bm25_text")
    )
    if _source_native_context_requires_runtime_text_sanitization(row):
        return _strip_source_native_runtime_forbidden_text_segments(text)
    return text


SOURCE_DERIVED_EVIDENCE_METADATA_FIELDS = (
    "sheet",
    "cell_range",
    "range",
    "cell",
    "row_index_1based",
    "row_label",
    "column_label",
    "target_column",
    "header_path",
    "header",
    "table_id",
    "display_value",
    "page_number",
    "page",
    "physical_page_index",
    "block_index",
    "bbox",
    "region_type",
    "section_title",
    "table_caption",
    "locator_fingerprint",
)
SOURCE_DERIVED_EVIDENCE_METADATA_CONTAINERS = ("metadata", "raw_locator", "location_json")
SOURCE_DERIVED_EVIDENCE_FORBIDDEN_FIELDS = frozenset(
    {
        "title",
        "source_title",
        "workbook",
        "workbook_title",
        "workbook_name",
        "source_workbook",
        "source_workbook_title",
        "source_path",
        "path",
        "file_path",
        "source_file_name",
        "file_name",
        "filename",
        "workbook_id",
        "workbook_version_id",
        "normalized_value",
        "formula",
        "expected_answer",
        "expected_evidence",
        "qrels",
        "label",
        "labels",
        "answerability",
        "query_id",
        "row_id",
        "target_id",
    }
)


def _source_derived_metadata_sources(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    sources: list[Mapping[str, Any]] = [row]
    for container_key in SOURCE_DERIVED_EVIDENCE_METADATA_CONTAINERS:
        value = row.get(container_key)
        parsed = _parse_jsonish(value)
        if isinstance(parsed, Mapping):
            sources.append(parsed)
    return sources


def source_derived_evidence_metadata(row: Mapping[str, Any]) -> tuple[str, list[str]]:
    values: list[str] = []
    fields: list[str] = []
    for field in SOURCE_DERIVED_EVIDENCE_METADATA_FIELDS:
        if field in SOURCE_DERIVED_EVIDENCE_FORBIDDEN_FIELDS:
            continue
        for source in _source_derived_metadata_sources(row):
            value = _clean(source.get(field))
            if not value:
                continue
            rendered = f"{field}={value}"
            if rendered not in values:
                values.append(rendered)
            if field not in fields:
                fields.append(field)
            break
    return " | ".join(values), fields


def _gate_support_text(row: Mapping[str, Any]) -> str:
    text = _gate_row_text(row)
    metadata_text, _fields = source_derived_evidence_metadata(row)
    return " | ".join(part for part in (text, metadata_text) if part)


def _gate_row_hash(row: Mapping[str, Any]) -> str:
    return _clean(
        row.get("source_text_sha256")
        or row.get("text_sha256")
        or row.get("cited_text_hash")
        or row.get("full_text_hash")
    ) or _sha256_text(_gate_row_text(row))


def _gate_answer_surface(answer: str) -> str:
    text = _clean(answer)
    marker = "**Short answer:**"
    if marker in text:
        text = text.split(marker, 1)[1]
        for stop_marker in ("**Supporting passages:**", "**Sources:**", "\n\nSupporting passages:", "\n\nSources:"):
            if stop_marker in text:
                text = text.split(stop_marker, 1)[0]
        return _clean(text)
    return text


def _gate_anchor_variants(anchor: str) -> set[str]:
    normalized = normalize_answer_text(anchor)
    if not normalized:
        return set()
    variants = {normalized}
    if re.fullmatch(r"[가-힣]+", normalized):
        for suffix in sorted(KOREAN_GENERIC_SUFFIXES, key=len, reverse=True):
            if normalized.endswith(suffix) and len(normalized) > len(suffix) + 1:
                variants.add(normalized[: -len(suffix)])
    return {variant for variant in variants if variant}


def _gate_query_focus_anchors(query: str) -> set[str]:
    stopwords = _anchor_stopwords() | {
        normalize_answer_text(value) for value in EVIDENCE_GATE_QUERY_INTENT_STOPWORDS
    }
    anchors: set[str] = set()
    for anchor in _candidate_anchors(query):
        normalized_anchor = normalize_answer_text(anchor)
        if not normalized_anchor or _is_generic_anchor(normalized_anchor, stopwords):
            continue
        variants = [
            variant
            for variant in _gate_anchor_variants(anchor)
            if variant and not _is_generic_anchor(variant, stopwords) and (re.search(r"\d", variant) or len(variant) >= 2)
        ]
        if not variants:
            continue
        anchors.add(sorted(variants, key=len)[0])
    return anchors


QUERY_EVIDENCE_SOURCE_FAMILY_HINTS = {"xlsx", "pdf", "text", "unknown"}
QUERY_EVIDENCE_TASKS = {
    "table_lookup",
    "cell_lookup",
    "date_filtered_lookup",
    "date_filtered_table_lookup",
    "entity_attribute_lookup",
    "count_lookup",
}
QUERY_EVIDENCE_VALUE_TYPES = {"number", "text", "date", "unknown"}
QUERY_EVIDENCE_COMMON_AXES = ("period", "row_entity", "target_column", "display_value")
QUERY_EVIDENCE_XLSX_LOCATOR_AXES = ("sheet", "table_id", "cell", "cell_range", "row_index")
QUERY_EVIDENCE_PDF_LOCATOR_AXES = (
    "page_number",
    "section_title",
    "table_caption",
    "block_index",
    "bbox",
    "locator_fingerprint",
)
QUERY_EVIDENCE_AXIS_ORDER = (
    "period",
    "page_number",
    "section_title",
    "table_caption",
    "sheet",
    "table_id",
    "row_entity",
    "target_column",
    "display_value",
    "cell",
    "cell_range",
    "row_index",
    "block_index",
    "bbox",
    "locator_fingerprint",
)
QUERY_EVIDENCE_LOCATOR_PRESENCE_AXES = set(QUERY_EVIDENCE_XLSX_LOCATOR_AXES) | set(QUERY_EVIDENCE_PDF_LOCATOR_AXES)
QUERY_EVIDENCE_VALUE_REQUIRED_AXES = {"period", "row_entity", "target_column"}
QUERY_EVIDENCE_AXIS_METADATA_FIELDS = {
    "period": ("sheet", "date", "period"),
    "row_entity": ("row_label", "line_name", "entity", "entity_name"),
    "target_column": ("target_column", "column_label", "header", "header_path"),
    "display_value": ("display_value",),
    "sheet": ("sheet",),
    "table_id": ("table_id", "synthetic_table_id"),
    "cell": ("cell",),
    "cell_range": ("cell_range", "range"),
    "row_index": ("row_index", "row_index_1based"),
    "page_number": ("page_number", "page", "physical_page_index"),
    "section_title": ("section_title",),
    "table_caption": ("table_caption",),
    "block_index": ("block_index",),
    "bbox": ("bbox", "bounding_box"),
    "locator_fingerprint": ("locator_fingerprint",),
}


def _query_evidence_planner_prompt(query: str) -> str:
    payload = {"query": _clean(query)}
    schema = {
        "source_family_hint": "xlsx|pdf|text|unknown",
        "query_task": "table_lookup|cell_lookup|date_filtered_lookup|date_filtered_table_lookup|entity_attribute_lookup|count_lookup",
        "row_filters": {"period": "YYYY-MM when present", "line_name": "row/entity text when present"},
        "target_axis": {"column": "target column or attribute", "value_type": "number|text|date|unknown"},
        "evidence_contract": [
            "period",
            "row_entity",
            "target_column",
            "display_value",
            "sheet",
            "cell",
            "cell_range",
            "table_id",
            "page_number",
            "section_title",
            "table_caption",
            "block_index",
            "bbox",
        ],
        "intent_tokens": ["question wording only"],
    }
    return (
        "Plan evidence requirements for this non-production diagnostic query.\n"
        "Use only the query string in the JSON payload.\n"
        "Return exactly one JSON object with the schema shown below.\n"
        "Do not turn question wording such as how many, what, when, or Korean question endings into evidence axes.\n\n"
        f"Schema:\n{json.dumps(schema, ensure_ascii=False, sort_keys=True)}\n\n"
        f"Payload:\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n"
    )


def _query_evidence_list(value: Any) -> list[str] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None
    values: list[str] = []
    seen: set[str] = set()
    for item in value:
        clean_item = _clean(item)
        normalized = normalize_answer_text(clean_item)
        if clean_item and normalized and normalized not in seen:
            values.append(clean_item)
            seen.add(normalized)
    return values


def _query_evidence_mapping(value: Any) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    mapped: dict[str, str] = {}
    for key, item in value.items():
        clean_key = _clean(key)
        clean_item = _clean(item)
        if clean_key and clean_item:
            mapped[clean_key] = clean_item
    return mapped


def _strip_korean_particle(value: str) -> str:
    clean_value = _clean(value)
    for suffix in ("입니다", "입니까", "인가요", "인가", "에는", "에서", "으로", "로", "의", "은", "는", "이", "가", "을", "를", "와", "과", "에"):
        if clean_value.endswith(suffix) and len(clean_value) > len(suffix) + 1:
            return clean_value[: -len(suffix)]
    return clean_value


def _query_evidence_period_aliases(year: str, month: str) -> list[str]:
    month_int = int(month)
    return [
        f"{year}-{month_int:02d}",
        f"{year}년 {month_int}월",
        f"{year}{month_int:02d}",
    ]


def _query_evidence_period_aliases_from_text(text: str) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = {}
    for match in re.finditer(r"\b(\d{4})[-./](0?[1-9]|1[0-2])\b", text):
        period_aliases = _query_evidence_period_aliases(match.group(1), match.group(2))
        aliases[period_aliases[0]] = period_aliases
    for match in re.finditer(r"(\d{4})\s*년\s*(0?[1-9]|1[0-2])\s*월", text):
        period_aliases = _query_evidence_period_aliases(match.group(1), match.group(2))
        aliases[period_aliases[0]] = period_aliases
    for match in re.finditer(r"\b(\d{4})(0[1-9]|1[0-2])\b", text):
        period_aliases = _query_evidence_period_aliases(match.group(1), match.group(2))
        aliases[period_aliases[0]] = period_aliases
    return aliases


def _normalize_query_evidence_period(value: str, query: str) -> tuple[str, list[str]]:
    clean_value = _clean(value)
    value_aliases = _query_evidence_period_aliases_from_text(clean_value)
    query_aliases = _query_evidence_period_aliases_from_text(query)
    for canonical, aliases in value_aliases.items():
        if canonical in query_aliases:
            return canonical, aliases
    if clean_value in query_aliases:
        return clean_value, query_aliases[clean_value]
    return "", []


def _query_value_grounded_in_text(value: str, query: str) -> bool:
    clean_value = _strip_korean_particle(value)
    if not clean_value:
        return False
    value_norm = normalize_answer_text(clean_value).replace(" ", "")
    query_norm = normalize_answer_text(query).replace(" ", "")
    return bool(value_norm and value_norm in query_norm)


def _normalize_query_evidence_axis(axis: str) -> str:
    normalized = normalize_answer_text(axis).replace(" ", "_")
    aliases = {
        "date": "period",
        "month": "period",
        "기간": "period",
        "날짜": "period",
        "row": "row_entity",
        "entity": "row_entity",
        "row_filter": "row_entity",
        "row_label": "row_entity",
        "line_name": "row_entity",
        "column": "target_column",
        "measure": "target_column",
        "target_axis": "target_column",
        "target": "target_column",
        "value": "display_value",
        "answer_value": "display_value",
        "worksheet": "sheet",
        "sheet_name": "sheet",
        "range": "cell_range",
        "cell_range": "cell_range",
        "row_number": "row_index",
        "row_index_1based": "row_index",
        "page": "page_number",
        "physical_page": "page_number",
        "physical_page_index": "page_number",
        "페이지": "page_number",
        "section": "section_title",
        "section_heading": "section_title",
        "heading": "section_title",
        "caption": "table_caption",
        "table_title": "table_caption",
        "bounding_box": "bbox",
        "box": "bbox",
        "locator": "locator_fingerprint",
        "fingerprint": "locator_fingerprint",
    }
    return aliases.get(normalized, normalized)


def _ordered_query_evidence_axes(axes: Iterable[str]) -> list[str]:
    normalized = {_normalize_query_evidence_axis(axis) for axis in axes}
    return [axis for axis in QUERY_EVIDENCE_AXIS_ORDER if axis in normalized]


def _query_evidence_axis_allowed_for_source(axis: str, source_family_hint: str) -> bool:
    if axis in QUERY_EVIDENCE_COMMON_AXES:
        return True
    if axis in QUERY_EVIDENCE_XLSX_LOCATOR_AXES:
        return source_family_hint == "xlsx"
    if axis in QUERY_EVIDENCE_PDF_LOCATOR_AXES:
        return source_family_hint == "pdf"
    return False


def _query_evidence_page_aliases(page_number: str) -> list[str]:
    clean_page = _clean(page_number)
    if not clean_page:
        return []
    return [
        clean_page,
        f"{clean_page}페이지",
        f"page {clean_page}",
        f"p. {clean_page}",
    ]


def _normalize_query_evidence_page_number(value: str, query: str) -> tuple[str, list[str]]:
    clean_value = _clean(value)
    match = re.search(r"\d+", clean_value)
    if not match:
        return "", []
    page_number = str(int(match.group(0)))
    aliases = _query_evidence_page_aliases(page_number)
    query_norm = normalize_answer_text(query).replace(" ", "")
    if any(normalize_answer_text(alias).replace(" ", "") in query_norm for alias in aliases):
        return page_number, aliases
    return "", []


def _query_evidence_record_locator_filter(
    *,
    axis: str,
    value: str,
    query: str,
    row_filters: dict[str, str],
    validated_axis_values: dict[str, list[str]],
) -> bool:
    if axis == "page_number":
        page_number, aliases = _normalize_query_evidence_page_number(value, query)
        if not page_number:
            return False
        row_filters[axis] = page_number
        validated_axis_values[axis] = aliases
        return True
    if _query_value_grounded_in_text(value, query):
        row_filters[axis] = _strip_korean_particle(value)
        validated_axis_values[axis] = [row_filters[axis]]
        return True
    return False


def _query_evidence_task_required_axes(
    *,
    query_task: str,
    row_filters: Mapping[str, str],
    row_entities: Sequence[str],
    target_axis: Mapping[str, str],
) -> list[str]:
    axes: list[str] = []
    if query_task in {"date_filtered_lookup", "date_filtered_table_lookup"} and _clean(row_filters.get("period")):
        axes.append("period")
    if row_entities:
        axes.append("row_entity")
    if _clean(target_axis.get("column")):
        axes.append("target_column")
    if query_task in QUERY_EVIDENCE_TASKS and (
        query_task == "count_lookup"
        or _clean(target_axis.get("column"))
        or bool(row_filters)
    ):
        axes.append("display_value")
    return _ordered_query_evidence_axes(axes)


def _validate_query_evidence_payload(
    *,
    query: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    source_family_hint = _clean(payload.get("source_family_hint")).lower() or "unknown"
    if source_family_hint not in QUERY_EVIDENCE_SOURCE_FAMILY_HINTS:
        source_family_hint = "unknown"
    query_task = _clean(payload.get("query_task")).lower()
    if query_task not in QUERY_EVIDENCE_TASKS:
        query_task = "table_lookup"
    raw_row_filters = _query_evidence_mapping(payload.get("row_filters")) or {}
    raw_target_axis = _query_evidence_mapping(payload.get("target_axis")) or {}
    raw_contract = _query_evidence_list(payload.get("evidence_contract")) or []
    intent_tokens = _query_evidence_list(payload.get("intent_tokens")) or []

    row_filters: dict[str, str] = {}
    validated_axis_values: dict[str, list[str]] = {}
    period_aliases_by_query = _query_evidence_period_aliases_from_text(query)
    for key, value in raw_row_filters.items():
        clean_key = _clean(key)
        normalized_key = _normalize_query_evidence_axis(clean_key)
        if normalized_key in {"period", "date", "month", "year_month", "yyyymm"}:
            canonical, aliases = _normalize_query_evidence_period(value, query)
            if canonical:
                row_filters["period"] = canonical
                validated_axis_values["period"] = aliases
            continue
        if normalized_key in (set(QUERY_EVIDENCE_XLSX_LOCATOR_AXES) | set(QUERY_EVIDENCE_PDF_LOCATOR_AXES)):
            if _query_evidence_axis_allowed_for_source(normalized_key, source_family_hint):
                _query_evidence_record_locator_filter(
                    axis=normalized_key,
                    value=value,
                    query=query,
                    row_filters=row_filters,
                    validated_axis_values=validated_axis_values,
                )
            continue
        if _query_value_grounded_in_text(value, query):
            row_filters[clean_key] = _strip_korean_particle(value)
    if "period" not in row_filters and period_aliases_by_query:
        canonical = sorted(period_aliases_by_query)[0]
        row_filters["period"] = canonical
        validated_axis_values["period"] = period_aliases_by_query[canonical]

    target_axis: dict[str, str] = {}
    target_column = _strip_korean_particle(raw_target_axis.get("column") or raw_target_axis.get("target_column") or "")
    if target_column and _query_value_grounded_in_text(target_column, query):
        target_axis["column"] = target_column
    value_type = _clean(raw_target_axis.get("value_type")).lower() or "unknown"
    target_axis["value_type"] = value_type if value_type in QUERY_EVIDENCE_VALUE_TYPES else "unknown"

    locator_filter_axes = set(QUERY_EVIDENCE_XLSX_LOCATOR_AXES) | set(QUERY_EVIDENCE_PDF_LOCATOR_AXES)
    row_entities = [
        value
        for key, value in row_filters.items()
        if key != "period" and key not in locator_filter_axes and _clean(value)
    ]
    if row_entities:
        validated_axis_values["row_entity"] = list(dict.fromkeys(row_entities))
    if _clean(target_axis.get("column")):
        validated_axis_values["target_column"] = [_clean(target_axis.get("column"))]
    validated_axis_values.setdefault("display_value", [])

    raw_contract_axes = [
        axis
        for axis in _ordered_query_evidence_axes(raw_contract)
        if _query_evidence_axis_allowed_for_source(axis, source_family_hint)
    ]
    task_required_axes = _query_evidence_task_required_axes(
        query_task=query_task,
        row_filters=row_filters,
        row_entities=row_entities,
        target_axis=target_axis,
    )
    if raw_contract_axes:
        contract_axes = _ordered_query_evidence_axes([*raw_contract_axes, *task_required_axes])
    else:
        inferred_axes: list[str] = []
        if "period" in row_filters:
            inferred_axes.append("period")
        for axis in QUERY_EVIDENCE_AXIS_ORDER:
            if axis in locator_filter_axes and axis in row_filters:
                inferred_axes.append(axis)
        if row_entities:
            inferred_axes.append("row_entity")
        if _clean(target_axis.get("column")):
            inferred_axes.extend(["target_column", "display_value"])
        contract_axes = [
            axis
            for axis in _ordered_query_evidence_axes(inferred_axes)
            if _query_evidence_axis_allowed_for_source(axis, source_family_hint)
        ]
        contract_axes = _ordered_query_evidence_axes([*contract_axes, *task_required_axes])
    validated_required_axes = [
        axis
        for axis in contract_axes
        if axis != "display_value"
        and (
            axis in QUERY_EVIDENCE_LOCATOR_PRESENCE_AXES
            or _as_list(validated_axis_values.get(axis))
        )
    ]
    if "display_value" in contract_axes and "target_column" in validated_required_axes and "display_value" not in validated_required_axes:
        validated_required_axes.append("display_value")
    validated_required_axes = _ordered_query_evidence_axes(validated_required_axes)

    return {
        "source_family_hint": source_family_hint,
        "query_task": query_task,
        "row_filters": dict(sorted(row_filters.items())),
        "target_axis": target_axis,
        "evidence_contract": contract_axes,
        "intent_tokens": intent_tokens,
        "validated_required_axes": validated_required_axes,
        "validated_axis_values": {
            axis: list(values)
            for axis, values in validated_axis_values.items()
            if axis in QUERY_EVIDENCE_AXIS_ORDER
        },
    }


def _query_evidence_planner_summary(
    *,
    query: str,
    status: str,
    config: Mapping[str, Any],
    plan: Mapping[str, Any] | None = None,
    raw_response_sha256: str = "",
    blockers: Sequence[str] = (),
    error: str = "",
) -> dict[str, Any]:
    plan = plan or {}
    result = {
        "enabled": True,
        "status": status,
        "planner_status": status,
        "model": _clean(config.get("model")),
        "backend": _clean(config.get("backend")),
        "base_url": _clean(config.get("base_url")),
        "prompt_version": QUERY_EVIDENCE_PLANNER_PROMPT_VERSION,
        "input_policy": QUERY_EVIDENCE_PLANNER_INPUT_POLICY,
        "query_sha256": f"sha256:{_sha256_text(query)}" if _clean(query) else "",
        "source_family_hint": _clean(plan.get("source_family_hint")) or "unknown",
        "query_task": _clean(plan.get("query_task")),
        "row_filters": dict(plan.get("row_filters") or {}),
        "target_axis": dict(plan.get("target_axis") or {}),
        "evidence_contract": list(plan.get("evidence_contract") or []),
        "intent_tokens": list(plan.get("intent_tokens") or []),
        "validated_required_axes": list(plan.get("validated_required_axes") or []),
        "validated_axis_values": dict(plan.get("validated_axis_values") or {}),
        "raw_payload_written": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "uses_query_text_only": True,
        "uses_gold_fields": False,
        "uses_expected_fields": False,
        "uses_qrels": False,
        "uses_labels": False,
        "uses_query_or_row_or_target_ids": False,
        "uses_baseline_topk_or_legacy_outputs": False,
    }
    if raw_response_sha256:
        result["raw_response_sha256"] = raw_response_sha256
    if blockers:
        result["blockers"] = list(blockers)
    if error:
        result["error"] = error
    return result


def plan_query_evidence_with_local_llm(
    query: str,
    *,
    backend: str = "",
    base_url: str = "",
    model: str = "",
    timeout_seconds: int = 60,
    max_tokens: int = 260,
    skip_endpoint_check: bool = False,
) -> dict[str, Any]:
    clean_query = _clean(query)
    config = _local_llm_composer_config(
        backend=backend,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        check_endpoint=not skip_endpoint_check,
    )
    if not clean_query:
        return _query_evidence_planner_summary(
            query=clean_query,
            status="skipped_no_query",
            config=config,
        )
    if not config.get("available"):
        return _query_evidence_planner_summary(
            query=clean_query,
            status="unavailable_deterministic_fallback",
            config=config,
            blockers=[_clean(value) for value in _as_list(config.get("blockers")) if _clean(value)],
        )
    prompt = _query_evidence_planner_prompt(clean_query)
    try:
        parsed, meta = LOCAL_LLM_HELPER.call_local_llm_strict_json(
            backend=_clean(config.get("backend")),
            base_url=_clean(config.get("base_url")),
            model=_clean(config.get("model")),
            prompt=prompt,
            temperature=0.0,
            max_tokens=int(config.get("max_tokens") or max_tokens),
            timeout_seconds=int(config.get("timeout_seconds") or timeout_seconds),
        )
    except Exception as exc:
        return _query_evidence_planner_summary(
            query=clean_query,
            status="error_deterministic_fallback",
            config=config,
            error=f"QUERY_EVIDENCE_PLANNER_ERROR: {type(exc).__name__}: {exc}",
        )
    if not isinstance(parsed, Mapping):
        return _query_evidence_planner_summary(
            query=clean_query,
            status="malformed_payload_deterministic_fallback",
            config=config,
            raw_response_sha256=_clean((meta or {}).get("raw_response_sha256")),
        )
    required_keys = {
        "source_family_hint",
        "query_task",
        "row_filters",
        "target_axis",
        "evidence_contract",
        "intent_tokens",
    }
    if set(parsed) != required_keys:
        return _query_evidence_planner_summary(
            query=clean_query,
            status="malformed_payload_deterministic_fallback",
            config=config,
            raw_response_sha256=_clean((meta or {}).get("raw_response_sha256")),
        )
    if _query_evidence_mapping(parsed.get("row_filters")) is None or _query_evidence_mapping(parsed.get("target_axis")) is None:
        return _query_evidence_planner_summary(
            query=clean_query,
            status="malformed_payload_deterministic_fallback",
            config=config,
            raw_response_sha256=_clean((meta or {}).get("raw_response_sha256")),
        )
    if _query_evidence_list(parsed.get("evidence_contract")) is None or _query_evidence_list(parsed.get("intent_tokens")) is None:
        return _query_evidence_planner_summary(
            query=clean_query,
            status="malformed_payload_deterministic_fallback",
            config=config,
            raw_response_sha256=_clean((meta or {}).get("raw_response_sha256")),
        )
    plan = _validate_query_evidence_payload(query=clean_query, payload=parsed)
    if not _as_list(plan.get("validated_required_axes")):
        return _query_evidence_planner_summary(
            query=clean_query,
            status="empty_after_validation_deterministic_fallback",
            config=config,
            plan=plan,
            raw_response_sha256=_clean((meta or {}).get("raw_response_sha256")),
        )
    return _query_evidence_planner_summary(
        query=clean_query,
        status="planned_validated",
        config=config,
        plan=plan,
        raw_response_sha256=_clean((meta or {}).get("raw_response_sha256")),
    )


def _llm_query_anchor_classifier_prompt(query: str) -> str:
    payload = {"query": _clean(query)}
    return (
        "Classify focus anchors for this non-production diagnostic query.\n"
        "Use only the query string in the JSON payload.\n"
        "Return exactly one JSON object with keys: intent_tokens, numeric_or_date_anchors, entity_anchors, measure_anchors.\n"
        "Each value must be an array of strings. intent_tokens are words that describe the question act, not the answer target.\n\n"
        f"Payload:\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n"
    )


def _normalized_anchor_lookup(anchors: Iterable[str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for anchor in anchors:
        clean_anchor = _clean(anchor)
        normalized = normalize_answer_text(clean_anchor)
        if clean_anchor and normalized and normalized not in lookup:
            lookup[normalized] = clean_anchor
    return lookup


def _llm_anchor_list(value: Any) -> list[str] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None
    anchors: list[str] = []
    seen: set[str] = set()
    for item in value:
        clean_item = _clean(item)
        normalized = normalize_answer_text(clean_item)
        if clean_item and normalized and normalized not in seen:
            anchors.append(clean_item)
            seen.add(normalized)
    return anchors


def _looks_like_measure_anchor(anchor: str) -> bool:
    normalized = normalize_answer_text(anchor)
    if not normalized:
        return False
    measure_markers = (
        "amount",
        "count",
        "date",
        "address",
        "code",
        "total",
        "rate",
        "price",
        "value",
        "금액",
        "승객수",
        "총승객수",
        "주소",
        "상세주소",
        "지정일자",
        "설치신고일자",
        "코드",
        "합계",
        "평균",
        "비율",
        "수",
    )
    return any(marker in normalized for marker in measure_markers)


def _can_remove_llm_intent_anchor(anchor: str) -> bool:
    normalized = normalize_answer_text(anchor)
    if not normalized:
        return False
    stopwords = _anchor_stopwords() | {
        normalize_answer_text(value) for value in EVIDENCE_GATE_QUERY_INTENT_STOPWORDS
    }
    if _is_generic_anchor(normalized, stopwords):
        return True
    question_markers = ("무엇", "뭐", "얼마", "어디", "언제", "누구", "어떤")
    if any(marker in normalized for marker in question_markers):
        return True
    action_tokens = {
        "기록된",
        "기재된",
        "나오는",
        "나온",
        "알려줘",
        "말해줘",
        "설명",
        "지정된",
    }
    return normalized in action_tokens


def _agentic_xlsx_forbidden_axis_evidence_norms() -> set[str]:
    forbidden_fields = (
        set(AGENTIC_PLANNER_FORBIDDEN_DECISION_FIELDS)
        | set(XLSX_PDF_RESIDUAL_FORBIDDEN_SHORTCUT_FIELDS)
        | set(XLSX_LOCATOR_FORBIDDEN_TEXT_MARKERS)
        | set(XLSX_LOCATOR_DIAGNOSTIC_ONLY_FORBIDDEN_SEEN_FIELDS)
    )
    norms: set[str] = set()
    for field_name in forbidden_fields:
        normalized = normalize_answer_text(field_name)
        if normalized:
            norms.add(normalized)
            norms.add(normalized.replace("_", ""))
    return norms


def _agentic_xlsx_first_forbidden_axis_evidence_key(value: Any) -> str:
    forbidden_norms = _agentic_xlsx_forbidden_axis_evidence_norms()
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            if not isinstance(key, str):
                return "non_string_key"
            normalized_key = normalize_answer_text(key)
            if normalized_key in forbidden_norms or normalized_key.replace("_", "") in forbidden_norms:
                return key
            nested_forbidden = _agentic_xlsx_first_forbidden_axis_evidence_key(nested_value)
            if nested_forbidden:
                return nested_forbidden
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested_value in value:
            nested_forbidden = _agentic_xlsx_first_forbidden_axis_evidence_key(nested_value)
            if nested_forbidden:
                return nested_forbidden
    return ""


def _agentic_xlsx_query_anchor_taxonomy_summary(
    taxonomy_records: Sequence[AgenticXlsxQueryAnchorTaxonomyRecord | Mapping[str, Any]],
) -> dict[str, Any]:
    validate_agentic_xlsx_query_anchor_taxonomy_output("agentic_xlsx", taxonomy_records)
    category_counts = Counter(
        _clean(_agentic_xlsx_record_value(record, "category"))
        for record in taxonomy_records
    )
    removable_count = sum(
        1
        for record in taxonomy_records
        if _agentic_xlsx_record_value(record, "is_removable_intent_token") is True
    )
    protected_count = sum(
        1
        for record in taxonomy_records
        if _agentic_xlsx_record_value(record, "is_protected_anchor") is True
    )
    return {
        "schema_version": AGENTIC_XLSX_QUERY_ANCHOR_TAXONOMY_SCHEMA_VERSION,
        "token_count": len(taxonomy_records),
        "category_counts": dict(sorted(category_counts.items())),
        "removable_intent_token_count": removable_count,
        "protected_anchor_count": protected_count,
    }


def _agentic_xlsx_protected_anchor_verifier_summary(
    verification: AgenticXlsxProtectedAnchorVerifierRecord | Mapping[str, Any],
    *,
    taxonomy_records: Sequence[AgenticXlsxQueryAnchorTaxonomyRecord | Mapping[str, Any]],
) -> dict[str, Any]:
    validate_agentic_xlsx_protected_anchor_verifier_output(
        "agentic_xlsx",
        verification,
        taxonomy_records=taxonomy_records,
    )
    reasons = _agentic_xlsx_record_value(verification, "protected_rejection_reasons")
    return {
        "schema_version": AGENTIC_XLSX_PROTECTED_ANCHOR_VERIFIER_SCHEMA_VERSION,
        "proposed_removed_tokens": list(_agentic_xlsx_record_value(verification, "proposed_removed_tokens") or ()),
        "approved_removed_tokens": list(_agentic_xlsx_record_value(verification, "approved_removed_tokens") or ()),
        "rejected_removed_tokens": list(_agentic_xlsx_record_value(verification, "rejected_removed_tokens") or ()),
        "protected_rejection_reasons": {
            _clean(token): _clean(reason)
            for token, reason in sorted(dict(reasons or {}).items())
            if _clean(token) and _clean(reason)
        },
    }


def _agentic_xlsx_verified_anchor_removal(
    required_before: Sequence[str],
    proposed_removed_tokens: Sequence[str],
) -> tuple[list[str], list[str], dict[str, Any], dict[str, Any]]:
    before_lookup = _normalized_anchor_lookup(required_before)
    proposed: list[str] = []
    seen: set[str] = set()
    for token in proposed_removed_tokens:
        normalized = normalize_answer_text(token)
        anchor = before_lookup.get(normalized)
        if not anchor or normalized in seen:
            continue
        proposed.append(anchor)
        seen.add(normalized)
    taxonomy_records = agentic_xlsx_query_anchor_taxonomy_tool(required_before)
    verification = agentic_xlsx_protected_anchor_verifier_tool(
        proposed_removed_tokens=proposed,
        taxonomy_records=taxonomy_records,
    )
    return (
        list(verification.approved_removed_tokens),
        list(verification.rejected_removed_tokens),
        _agentic_xlsx_query_anchor_taxonomy_summary(taxonomy_records),
        _agentic_xlsx_protected_anchor_verifier_summary(
            verification,
            taxonomy_records=taxonomy_records,
        ),
    )


def validate_agentic_xlsx_axis_inspector_output(
    run_id: str,
    inspection: AgenticXlsxAxisInspectionRecord | Mapping[str, Any],
) -> None:
    tool_name = "xlsx_axis_inspector"
    if not isinstance(inspection, (AgenticXlsxAxisInspectionRecord, Mapping)):
        raise DatasetSchemaError(f"{run_id}: {tool_name} must be an axis inspection record")
    if _agentic_xlsx_record_value(inspection, "schema_version") != AGENTIC_XLSX_AXIS_INSPECTOR_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.schema_version unsupported")
    for field_name in (
        "has_required_period_axis",
        "has_required_entity_axis",
        "has_required_measure_axis",
        "has_display_value",
    ):
        _agentic_xlsx_bool(run_id, tool_name, field_name, _agentic_xlsx_record_value(inspection, field_name))
    _agentic_xlsx_clean_tuple(run_id, tool_name, "missing_axes", _agentic_xlsx_record_value(inspection, "missing_axes"))
    evidence = _agentic_xlsx_record_value(inspection, "source_owned_axis_evidence")
    if not isinstance(evidence, Mapping):
        raise DatasetSchemaError(f"{run_id}: {tool_name}.source_owned_axis_evidence must be present")
    forbidden_key = _agentic_xlsx_first_forbidden_axis_evidence_key(evidence)
    if forbidden_key:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.source_owned_axis_evidence contains forbidden field {forbidden_key}")
    for key, value in evidence.items():
        if not isinstance(key, str) or not _clean(key):
            raise DatasetSchemaError(f"{run_id}: {tool_name}.source_owned_axis_evidence keys must be non-empty strings")
        if not isinstance(value, str) or not _clean(value):
            raise DatasetSchemaError(
                f"{run_id}: {tool_name}.source_owned_axis_evidence.{key} must be a non-empty string"
            )


def validate_agentic_xlsx_repair_explainer_output(
    run_id: str,
    explanation: AgenticXlsxRepairExplanationRecord | Mapping[str, Any],
    *,
    anchor_verification: AgenticXlsxProtectedAnchorVerifierRecord | Mapping[str, Any] | None = None,
    axis_inspection: AgenticXlsxAxisInspectionRecord | Mapping[str, Any] | None = None,
) -> None:
    tool_name = "candidate_repair_explainer"
    if not isinstance(explanation, (AgenticXlsxRepairExplanationRecord, Mapping)):
        raise DatasetSchemaError(f"{run_id}: {tool_name} must be a repair explanation record")
    if _agentic_xlsx_record_value(explanation, "schema_version") != AGENTIC_XLSX_REPAIR_EXPLAINER_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.schema_version unsupported")
    primary = _clean(_agentic_xlsx_record_value(explanation, "primary_failure_family"))
    if primary not in AGENTIC_XLSX_REPAIR_FAILURE_FAMILIES:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.primary_failure_family unsupported")
    for family in _agentic_xlsx_clean_tuple(
        run_id,
        tool_name,
        "secondary_failure_families",
        _agentic_xlsx_record_value(explanation, "secondary_failure_families"),
    ):
        if family not in AGENTIC_XLSX_REPAIR_FAILURE_FAMILIES:
            raise DatasetSchemaError(f"{run_id}: {tool_name}.secondary_failure_families unsupported")
    safe_to_simulate = _agentic_xlsx_bool(
        run_id,
        tool_name,
        "safe_to_simulate_intent_removal",
        _agentic_xlsx_record_value(explanation, "safe_to_simulate_intent_removal"),
    )
    if not _clean(_agentic_xlsx_record_value(explanation, "repair_recommendation")):
        raise DatasetSchemaError(f"{run_id}: {tool_name}.repair_recommendation must be non-empty")
    if not _clean(_agentic_xlsx_record_value(explanation, "evidence_summary")):
        raise DatasetSchemaError(f"{run_id}: {tool_name}.evidence_summary must be non-empty")
    if anchor_verification is not None:
        rejected = _agentic_xlsx_clean_tuple(
            run_id,
            "protected_anchor_verifier",
            "rejected_removed_tokens",
            _agentic_xlsx_record_value(anchor_verification, "rejected_removed_tokens"),
        )
        if rejected and safe_to_simulate:
            raise DatasetSchemaError(
                f"{run_id}: {tool_name}.safe_to_simulate_intent_removal protected anchors were rejected"
            )
        if rejected and primary not in {"unsafe_classifier_removal", "unknown_fail_closed"}:
            raise DatasetSchemaError(f"{run_id}: {tool_name}.primary_failure_family must fail closed")
    if axis_inspection is not None:
        validate_agentic_xlsx_axis_inspector_output(run_id, axis_inspection)
        missing_axes = _agentic_xlsx_clean_tuple(
            run_id,
            "xlsx_axis_inspector",
            "missing_axes",
            _agentic_xlsx_record_value(axis_inspection, "missing_axes"),
        )
        if missing_axes and primary == "intent_anchor_only":
            raise DatasetSchemaError(
                f"{run_id}: {tool_name}.missing axes cannot be reported as intent-only"
            )
        if missing_axes and safe_to_simulate:
            raise DatasetSchemaError(f"{run_id}: {tool_name}.missing axes cannot be solved by intent removal")


def validate_agentic_xlsx_regated_candidate_simulator_output(
    run_id: str,
    simulation: AgenticXlsxRegatedCandidateSimulationRecord | Mapping[str, Any],
    *,
    anchor_verification: AgenticXlsxProtectedAnchorVerifierRecord | Mapping[str, Any] | None = None,
) -> None:
    tool_name = "regated_candidate_simulator"
    if not isinstance(simulation, (AgenticXlsxRegatedCandidateSimulationRecord, Mapping)):
        raise DatasetSchemaError(f"{run_id}: {tool_name} must be a simulation record")
    if _agentic_xlsx_record_value(simulation, "schema_version") != AGENTIC_XLSX_REGATED_CANDIDATE_SIMULATOR_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.schema_version unsupported")
    for field_name in ("original_rejection_reason", "simulated_rejection_reason"):
        if not _clean(_agentic_xlsx_record_value(simulation, field_name)):
            raise DatasetSchemaError(f"{run_id}: {tool_name}.{field_name} must be non-empty")
    approved = _agentic_xlsx_clean_tuple(
        run_id,
        tool_name,
        "approved_removed_tokens",
        _agentic_xlsx_record_value(simulation, "approved_removed_tokens"),
    )
    preserved = _agentic_xlsx_clean_tuple(
        run_id,
        tool_name,
        "protected_tokens_preserved",
        _agentic_xlsx_record_value(simulation, "protected_tokens_preserved"),
    )
    axis_status = _agentic_xlsx_record_value(simulation, "axis_status_after_simulation")
    if not isinstance(axis_status, Mapping):
        raise DatasetSchemaError(f"{run_id}: {tool_name}.axis_status_after_simulation must be present")
    _agentic_xlsx_bool(
        run_id,
        tool_name,
        "would_be_accepted_by_existing_gate",
        _agentic_xlsx_record_value(simulation, "would_be_accepted_by_existing_gate"),
    )
    if _agentic_xlsx_record_value(simulation, "report_only_diagnostic") is not True:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.report_only_diagnostic must be True")
    if _agentic_xlsx_record_value(simulation, "official_metric") is not False:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.official_metric must be False")
    if anchor_verification is not None:
        verifier_approved = _agentic_xlsx_clean_tuple(
            run_id,
            "protected_anchor_verifier",
            "approved_removed_tokens",
            _agentic_xlsx_record_value(anchor_verification, "approved_removed_tokens"),
        )
        rejected = _agentic_xlsx_clean_tuple(
            run_id,
            "protected_anchor_verifier",
            "rejected_removed_tokens",
            _agentic_xlsx_record_value(anchor_verification, "rejected_removed_tokens"),
        )
        if set(approved) & set(rejected) or not set(approved).issubset(set(verifier_approved)):
            raise DatasetSchemaError(f"{run_id}: {tool_name}.approved_removed_tokens must be verifier-approved")
        if not set(rejected).issubset(set(preserved)):
            raise DatasetSchemaError(f"{run_id}: {tool_name}.protected tokens must be preserved")


def validate_agentic_xlsx_coordinator_output(
    run_id: str,
    coordinator: AgenticXlsxCoordinatorRecord | Mapping[str, Any],
) -> None:
    tool_name = "agentic_coordinator"
    if not isinstance(coordinator, (AgenticXlsxCoordinatorRecord, Mapping)):
        raise DatasetSchemaError(f"{run_id}: {tool_name} must be a coordinator record")
    if _agentic_xlsx_record_value(coordinator, "schema_version") != AGENTIC_XLSX_COORDINATOR_SCHEMA_VERSION:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.schema_version unsupported")
    sequence = _agentic_xlsx_clean_tuple(
        run_id,
        tool_name,
        "tool_sequence",
        _agentic_xlsx_record_value(coordinator, "tool_sequence"),
    )
    if sequence != AGENTIC_XLSX_TOOL_SEQUENCE:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.tool_sequence must be fixed")
    if _agentic_xlsx_record_value(coordinator, "report_only_diagnostic") is not True:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.report_only_diagnostic must be True")
    if _agentic_xlsx_record_value(coordinator, "official_metric") is not False:
        raise DatasetSchemaError(f"{run_id}: {tool_name}.official_metric must be False")
    _agentic_xlsx_bool(run_id, tool_name, "fail_closed", _agentic_xlsx_record_value(coordinator, "fail_closed"))
    taxonomy = _agentic_xlsx_record_value(coordinator, "taxonomy_records")
    if taxonomy:
        validate_agentic_xlsx_query_anchor_taxonomy_output(run_id, taxonomy)
    verification = _agentic_xlsx_record_value(coordinator, "anchor_verification")
    if verification is not None:
        validate_agentic_xlsx_protected_anchor_verifier_output(run_id, verification, taxonomy_records=taxonomy or ())
    axis_inspection = _agentic_xlsx_record_value(coordinator, "axis_inspection")
    if axis_inspection is not None:
        validate_agentic_xlsx_axis_inspector_output(run_id, axis_inspection)
    explanation = _agentic_xlsx_record_value(coordinator, "repair_explanation")
    if explanation is not None:
        validate_agentic_xlsx_repair_explainer_output(
            run_id,
            explanation,
            anchor_verification=verification,
            axis_inspection=axis_inspection,
        )
    simulation = _agentic_xlsx_record_value(coordinator, "regated_simulation")
    if simulation is not None:
        validate_agentic_xlsx_regated_candidate_simulator_output(
            run_id,
            simulation,
            anchor_verification=verification,
        )


def _query_anchor_classifier_summary(
    *,
    query: str,
    status: str,
    config: Mapping[str, Any],
    required_before: Sequence[str],
    required_after: Sequence[str] | None = None,
    removed_intent_tokens: Sequence[str] = (),
    protected_intent_tokens_restored: Sequence[str] = (),
    raw_response_sha256: str = "",
    blockers: Sequence[str] = (),
    error: str = "",
    agentic_xlsx_anchor_taxonomy: Mapping[str, Any] | None = None,
    agentic_xlsx_protected_anchor_verifier: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    after = list(required_after) if required_after is not None else list(required_before)
    result = {
        "enabled": True,
        "status": status,
        "model": _clean(config.get("model")),
        "backend": _clean(config.get("backend")),
        "base_url": _clean(config.get("base_url")),
        "prompt_version": LLM_QUERY_ANCHOR_CLASSIFIER_PROMPT_VERSION,
        "input_policy": LLM_QUERY_ANCHOR_CLASSIFIER_INPUT_POLICY,
        "query_sha256": f"sha256:{_sha256_text(query)}" if _clean(query) else "",
        "required_anchor_before": list(required_before),
        "required_anchor_after": after,
        "removed_intent_tokens": list(removed_intent_tokens),
        "protected_intent_tokens_restored": list(protected_intent_tokens_restored),
        "raw_payload_written": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "uses_query_text_only": True,
        "uses_gold_fields": False,
        "uses_expected_fields": False,
        "uses_qrels": False,
        "uses_labels": False,
        "uses_query_or_row_or_target_ids": False,
        "uses_baseline_topk_or_legacy_outputs": False,
    }
    if raw_response_sha256:
        result["raw_response_sha256"] = raw_response_sha256
    if blockers:
        result["blockers"] = list(blockers)
    if error:
        result["error"] = error
    if agentic_xlsx_anchor_taxonomy:
        result["agentic_xlsx_anchor_taxonomy"] = dict(agentic_xlsx_anchor_taxonomy)
    if agentic_xlsx_protected_anchor_verifier:
        result["agentic_xlsx_protected_anchor_verifier"] = dict(agentic_xlsx_protected_anchor_verifier)
    return result


def classify_query_focus_anchors_with_local_llm(
    query: str,
    *,
    backend: str = "",
    base_url: str = "",
    model: str = "",
    timeout_seconds: int = 60,
    max_tokens: int = 180,
    skip_endpoint_check: bool = False,
) -> dict[str, Any]:
    clean_query = _clean(query)
    required_before = sorted(_gate_query_focus_anchors(clean_query))
    config = _local_llm_composer_config(
        backend=backend,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        check_endpoint=not skip_endpoint_check,
    )
    if not clean_query or not required_before:
        return _query_anchor_classifier_summary(
            query=clean_query,
            status="skipped_no_query_anchors",
            config=config,
            required_before=required_before,
        )
    if not config.get("available"):
        return _query_anchor_classifier_summary(
            query=clean_query,
            status="unavailable_deterministic_fallback",
            config=config,
            required_before=required_before,
            blockers=[_clean(value) for value in _as_list(config.get("blockers")) if _clean(value)],
        )
    prompt = _llm_query_anchor_classifier_prompt(clean_query)
    try:
        parsed, meta = LOCAL_LLM_HELPER.call_local_llm_strict_json(
            backend=_clean(config.get("backend")),
            base_url=_clean(config.get("base_url")),
            model=_clean(config.get("model")),
            prompt=prompt,
            temperature=0.0,
            max_tokens=int(config.get("max_tokens") or max_tokens),
            timeout_seconds=int(config.get("timeout_seconds") or timeout_seconds),
        )
    except Exception as exc:
        return _query_anchor_classifier_summary(
            query=clean_query,
            status="error_deterministic_fallback",
            config=config,
            required_before=required_before,
            error=f"LLM_QUERY_ANCHOR_CLASSIFIER_ERROR: {type(exc).__name__}: {exc}",
        )
    intent_tokens = _llm_anchor_list(parsed.get("intent_tokens") if isinstance(parsed, Mapping) else None)
    numeric_or_date = _llm_anchor_list(parsed.get("numeric_or_date_anchors") if isinstance(parsed, Mapping) else None)
    entity = _llm_anchor_list(parsed.get("entity_anchors") if isinstance(parsed, Mapping) else None)
    measure = _llm_anchor_list(parsed.get("measure_anchors") if isinstance(parsed, Mapping) else None)
    if intent_tokens is None or numeric_or_date is None or entity is None or measure is None:
        return _query_anchor_classifier_summary(
            query=clean_query,
            status="malformed_payload_deterministic_fallback",
            config=config,
            required_before=required_before,
            raw_response_sha256=_clean((meta or {}).get("raw_response_sha256")),
        )
    intent_norms = {normalize_answer_text(token) for token in intent_tokens if normalize_answer_text(token)}
    before_lookup = _normalized_anchor_lookup(required_before)
    proposed_removed = [before_lookup[normalized] for normalized in sorted(intent_norms) if normalized in before_lookup]
    removed, protected_restored, taxonomy_summary, verifier_summary = _agentic_xlsx_verified_anchor_removal(
        required_before,
        proposed_removed,
    )
    required_after = sorted(anchor for anchor in required_before if anchor not in set(removed))
    if required_before and not required_after:
        return _query_anchor_classifier_summary(
            query=clean_query,
            status="empty_after_validation_deterministic_fallback",
            config=config,
            required_before=required_before,
            raw_response_sha256=_clean((meta or {}).get("raw_response_sha256")),
            agentic_xlsx_anchor_taxonomy=taxonomy_summary,
            agentic_xlsx_protected_anchor_verifier=verifier_summary,
        )
    return _query_anchor_classifier_summary(
        query=clean_query,
        status="classified_validated",
        config=config,
        required_before=required_before,
        required_after=required_after,
        removed_intent_tokens=sorted(removed),
        protected_intent_tokens_restored=sorted(protected_restored),
        raw_response_sha256=_clean((meta or {}).get("raw_response_sha256")),
        agentic_xlsx_anchor_taxonomy=taxonomy_summary,
        agentic_xlsx_protected_anchor_verifier=verifier_summary,
    )


def _query_focus_anchors_for_row(row: Mapping[str, Any]) -> set[str]:
    query = _clean(row.get("query"))
    deterministic = _gate_query_focus_anchors(query)
    classifier = row.get("query_anchor_classifier") if isinstance(row.get("query_anchor_classifier"), Mapping) else {}
    if not classifier:
        return deterministic
    if _clean(classifier.get("query_sha256")) and _clean(classifier.get("query_sha256")) != f"sha256:{_sha256_text(query)}":
        return deterministic
    anchors = {
        normalize_answer_text(_clean(anchor))
        for anchor in _as_list(classifier.get("required_anchor_after"))
        if normalize_answer_text(_clean(anchor))
    }
    if deterministic and not anchors:
        return deterministic
    return anchors


def _query_evidence_planner_for_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
    query = _clean(row.get("query"))
    planner = row.get("query_evidence_planner") if isinstance(row.get("query_evidence_planner"), Mapping) else {}
    if not planner:
        return {}
    query_sha = _clean(planner.get("query_sha256"))
    if query_sha and query_sha != f"sha256:{_sha256_text(query)}":
        return {}
    if _clean(planner.get("planner_status")) != "planned_validated":
        return {}
    return planner


def _query_evidence_planner_for_query(query: str, planner: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(planner, Mapping):
        return {}
    row = {
        "query": _clean(query),
        "query_evidence_planner": planner,
    }
    return _query_evidence_planner_for_row(row)


def _query_evidence_source_family_hint(planner: Mapping[str, Any] | None) -> str:
    if not isinstance(planner, Mapping):
        return ""
    hint = _clean(planner.get("source_family_hint")).lower()
    return hint if hint in {"xlsx", "pdf", "text"} else ""


def _query_evidence_context_source_family(context: Mapping[str, Any]) -> str:
    source_family = _clean(context.get("source_family")).upper()
    if source_family in {"XLSX", "XLS", "SPREADSHEET"}:
        return "xlsx"
    if source_family == "PDF":
        return "pdf"
    if source_family == "TEXT":
        return "text"
    return source_family.lower()


def _query_evidence_source_family_matches_context(source_family_hint: str, context: Mapping[str, Any]) -> bool:
    hint = _clean(source_family_hint).lower()
    if not hint or hint == "unknown":
        return True
    return _query_evidence_context_source_family(context) == hint


def _query_evidence_item_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    planner = _query_evidence_planner_for_row(row)
    return {
        "source_family_hint": _clean(planner.get("source_family_hint")),
        "query_task": _clean(planner.get("query_task")),
        "planner_status": _clean(planner.get("planner_status")),
        "row_filters": dict(planner.get("row_filters") or {}) if isinstance(planner.get("row_filters"), Mapping) else {},
        "target_axis": dict(planner.get("target_axis") or {}) if isinstance(planner.get("target_axis"), Mapping) else {},
        "validated_required_axes": [
            _clean(axis)
            for axis in _as_list(planner.get("validated_required_axes"))
            if _clean(axis)
        ],
    }


def _query_evidence_axis_values(planner: Mapping[str, Any], axis: str) -> list[str]:
    values = planner.get("validated_axis_values") if isinstance(planner.get("validated_axis_values"), Mapping) else {}
    return [_clean(value) for value in _as_list(values.get(axis)) if _clean(value)]


def _query_evidence_metadata_values_by_axis(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    metadata_values: dict[str, list[str]] = {axis: [] for axis in QUERY_EVIDENCE_AXIS_ORDER}
    for row in rows:
        for source in _source_derived_metadata_sources(row):
            for axis, fields in QUERY_EVIDENCE_AXIS_METADATA_FIELDS.items():
                for field in fields:
                    value = _clean(source.get(field))
                    if value:
                        metadata_values.setdefault(axis, []).append(value)
    return metadata_values


def _query_evidence_same_row_period_cell_aliases(
    *,
    planner: Mapping[str, Any],
    selected_evidence: Sequence[Mapping[str, Any]],
) -> list[str]:
    query_periods = _xlsx_materializer_query_periods(planner)
    if not query_periods:
        return []
    aliases: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        clean_value = _clean(value)
        if clean_value and clean_value not in seen:
            aliases.append(clean_value)
            seen.add(clean_value)

    for evidence in selected_evidence:
        if not isinstance(evidence, Mapping):
            continue
        for packet in _xlsx_same_row_period_cell_packets(evidence):
            if not _xlsx_period_cell_scope_matches_candidate(evidence, packet):
                continue
            if not any(_source_period_cell_matches_query_period(packet, query_period) for query_period in query_periods):
                continue
            try:
                year = int(packet.get("year"))
                month = int(packet.get("month"))
            except (TypeError, ValueError):
                year = 0
                month = 0
            if year and month:
                for alias in _query_evidence_period_aliases(str(year), str(month)):
                    add(alias)
            for value in (packet.get("parsed_date"), packet.get("raw_value")):
                add(value)
                for alias in _xlsx_locator_date_aliases(_clean(value)):
                    add(alias)
    return aliases


def _query_evidence_axis_hit(
    *,
    axis: str,
    planner: Mapping[str, Any],
    field_texts: Mapping[str, Sequence[str]],
    metadata_values: Mapping[str, Sequence[str]],
) -> bool:
    axis_values = _query_evidence_axis_values(planner, axis)
    if axis_values:
        return _axis_value_hits_text(axis_values, field_texts.get(axis, ()))
    if axis in QUERY_EVIDENCE_LOCATOR_PRESENCE_AXES:
        return bool([value for value in metadata_values.get(axis, ()) if _clean(value)])
    return False


def _query_evidence_non_value_anchor_set(query: str, planner: Mapping[str, Any]) -> set[str]:
    anchors = set(_candidate_anchors(query))
    axis_values: list[str] = []
    for axis in QUERY_EVIDENCE_AXIS_ORDER:
        if axis == "display_value":
            continue
        axis_values.extend(_query_evidence_axis_values(planner, axis))
    anchors.update(_candidate_anchors(*axis_values))
    return anchors


def _query_evidence_short_text_display_value_hit(
    *,
    query: str,
    planner: Mapping[str, Any],
    answer: str,
    support_texts: Sequence[str],
) -> bool:
    normalized_answer = normalize_answer_text(answer).strip()
    if not normalized_answer or re.search(r"\s", normalized_answer):
        return False
    if len(normalized_answer) < 2 or len(normalized_answer) > 8:
        return False
    if _anchor_in_text([normalized_answer], query):
        return False
    axis_values: list[str] = []
    for axis in QUERY_EVIDENCE_AXIS_ORDER:
        if axis == "display_value":
            continue
        axis_values.extend(_query_evidence_axis_values(planner, axis))
    if axis_values and _anchor_in_text([normalized_answer], " ".join(axis_values)):
        return False
    return any(_anchor_in_text([normalized_answer], text) for text in support_texts)


def _query_evidence_display_value_hit(
    *,
    query: str,
    planner: Mapping[str, Any],
    answer: str,
    support_texts: Sequence[str],
    field_texts: Mapping[str, Sequence[str]],
    metadata_values: Mapping[str, Sequence[str]],
) -> bool:
    if metadata_values.get("display_value"):
        return True
    answer_anchors = _candidate_anchors(answer)
    display_hits = _gate_anchor_hits(answer_anchors, field_texts.get("display_value", ()))
    if display_hits:
        non_value_anchors = _query_evidence_non_value_anchor_set(query, planner)
        if any(anchor and anchor not in non_value_anchors for anchor in display_hits):
            return True
    if _query_evidence_short_text_display_value_hit(
        query=query,
        planner=planner,
        answer=answer,
        support_texts=support_texts,
    ):
        return True
    if _query_requires_numeric_or_date_answer(query) and support_texts:
        return any(_text_has_answer_value_anchor_beyond_query(query, text) for text in support_texts)
    return False


def _query_evidence_gate_validated_required_axis_hits(
    *,
    row: Mapping[str, Any],
    selected_evidence: Sequence[Mapping[str, Any]],
    answer: str,
) -> tuple[list[str], list[str]]:
    planner = _query_evidence_planner_for_row(row)
    required_axes = [
        _clean(axis)
        for axis in _as_list(planner.get("validated_required_axes"))
        if _clean(axis)
    ]
    if not required_axes:
        return [], []
    query = _clean(row.get("query"))
    support_texts = [
        _gate_support_text(evidence)
        for evidence in selected_evidence
        if _gate_support_text(evidence)
    ]
    metadata_values = _query_evidence_metadata_values_by_axis(selected_evidence)
    field_texts = {
        axis: [*support_texts, *metadata_values.get(axis, [])]
        for axis in QUERY_EVIDENCE_AXIS_ORDER
    }
    field_texts["period"] = [
        *field_texts.get("period", []),
        *_query_evidence_same_row_period_cell_aliases(
            planner=planner,
            selected_evidence=selected_evidence,
        ),
        *[alias for text in support_texts for alias in _xlsx_locator_date_aliases(text)],
    ]
    matched: list[str] = []
    missing: list[str] = []
    for axis in required_axes:
        if axis == "display_value":
            axis_ok = _query_evidence_display_value_hit(
                query=query,
                planner=planner,
                answer=answer,
                support_texts=support_texts,
                field_texts=field_texts,
                metadata_values=metadata_values,
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


def _query_evidence_context_validated_required_axis_hits(
    *,
    query: str,
    query_evidence_planner: Mapping[str, Any] | None,
    context: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    if not isinstance(query_evidence_planner, Mapping):
        return [], []
    row = {
        "query": _clean(query),
        "query_evidence_planner": query_evidence_planner,
    }
    return _query_evidence_gate_validated_required_axis_hits(
        row=row,
        selected_evidence=[context],
        answer=_clean(context.get("display_value")) or _gate_row_text(context),
    )


def _query_evidence_context_has_complete_validated_axes(
    *,
    query: str,
    query_evidence_planner: Mapping[str, Any] | None,
    context: Mapping[str, Any],
) -> tuple[bool, list[str], list[str]]:
    matched, missing = _query_evidence_context_validated_required_axis_hits(
        query=query,
        query_evidence_planner=query_evidence_planner,
        context=context,
    )
    return bool(matched or missing) and not missing, matched, missing


def _query_anchor_matches_planner_axis(anchor: str, planner: Mapping[str, Any]) -> bool:
    normalized_anchor = normalize_answer_text(anchor).replace(" ", "")
    if not normalized_anchor:
        return False
    for axis in QUERY_EVIDENCE_AXIS_ORDER:
        if axis == "display_value":
            continue
        for value in _query_evidence_axis_values(planner, axis):
            normalized_value = normalize_answer_text(value).replace(" ", "")
            if normalized_anchor and normalized_value and (
                normalized_anchor in normalized_value or normalized_value in normalized_anchor
            ):
                return True
    return False


def _query_focus_hits_from_validated_planner_axes(
    *,
    query_focus_anchors: Iterable[str],
    planner: Mapping[str, Any],
    matched_axes: Sequence[str],
) -> set[str]:
    matched_axis_set = {_clean(axis) for axis in matched_axes if _clean(axis)}
    if not matched_axis_set:
        return set()
    hits: set[str] = set()
    for anchor in query_focus_anchors:
        normalized_anchor = normalize_answer_text(anchor).replace(" ", "")
        if not normalized_anchor:
            continue
        for axis in QUERY_EVIDENCE_AXIS_ORDER:
            if axis == "display_value" or axis not in matched_axis_set:
                continue
            for value in _query_evidence_axis_values(planner, axis):
                normalized_value = normalize_answer_text(value).replace(" ", "")
                if normalized_value and (
                    normalized_anchor in normalized_value or normalized_value in normalized_anchor
                ):
                    hits.add(_clean(anchor))
                    break
            if _clean(anchor) in hits:
                break
    return hits


def _query_anchor_classifier_from_planner(query: str, planner: Mapping[str, Any]) -> dict[str, Any]:
    required_before = sorted(_gate_query_focus_anchors(query))
    planner_required_after = sorted(
        anchor
        for anchor in required_before
        if _query_anchor_matches_planner_axis(anchor, planner)
    )
    proposed_removed = sorted(anchor for anchor in required_before if anchor not in set(planner_required_after))
    removed, protected_restored, taxonomy_summary, verifier_summary = _agentic_xlsx_verified_anchor_removal(
        required_before,
        proposed_removed,
    )
    required_after = sorted(anchor for anchor in required_before if anchor not in set(removed))
    config = {
        "model": _clean(planner.get("model")),
        "backend": _clean(planner.get("backend")),
        "base_url": _clean(planner.get("base_url")),
    }
    return _query_anchor_classifier_summary(
        query=query,
        status="classified_validated",
        config=config,
        required_before=required_before,
        required_after=required_after,
        removed_intent_tokens=removed,
        protected_intent_tokens_restored=protected_restored,
        raw_response_sha256=_clean(planner.get("raw_response_sha256")),
        agentic_xlsx_anchor_taxonomy=taxonomy_summary,
        agentic_xlsx_protected_anchor_verifier=verifier_summary,
    )


def apply_llm_query_anchor_classifier_to_outputs(
    raw_outputs: Sequence[Mapping[str, Any]],
    *,
    backend: str = "",
    base_url: str = "",
    model: str = "",
    timeout_seconds: int = 60,
    max_tokens: int = 180,
    skip_endpoint_check: bool = False,
    precomputed_query_evidence_planners: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    planners_by_item_id = precomputed_query_evidence_planners or {}
    for row in raw_outputs:
        output = dict(row)
        query = _clean(row.get("query"))
        planner = planners_by_item_id.get(_query_id(row))
        if not isinstance(planner, Mapping):
            planner = plan_query_evidence_with_local_llm(
                query,
                backend=backend,
                base_url=base_url,
                model=model,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                skip_endpoint_check=skip_endpoint_check,
            )
        output["query_evidence_planner"] = planner
        if _clean(planner.get("planner_status")) == "planned_validated":
            output["query_anchor_classifier"] = _query_anchor_classifier_from_planner(query, planner)
        else:
            output["query_anchor_classifier"] = classify_query_focus_anchors_with_local_llm(
                query,
                backend=backend,
                base_url=base_url,
                model=model,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                skip_endpoint_check=skip_endpoint_check,
            )
        outputs.append(output)
    return outputs


def _gate_answer_anchors(query: str, answer: str) -> dict[str, Any]:
    answer_anchors = _candidate_anchors(answer)
    query_anchors = _candidate_anchors(query)
    numeric = _numeric_or_date_anchors(answer_anchors)
    entity_like: set[str] = set()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]*|[가-힣]{2,}", answer or ""):
        normalized = normalize_answer_text(token)
        if not normalized or normalized not in answer_anchors or normalized in numeric:
            continue
        if token[:1].isupper() or re.search(r"[가-힣]", token):
            entity_like.add(normalized)
    entity = {anchor for anchor in entity_like if anchor not in query_anchors}
    return {
        "answer": answer_anchors,
        "query": query_anchors,
        "numeric_or_date": numeric,
        "entity": entity,
    }


def _gate_anchor_hits(anchors: Iterable[str], texts: Sequence[str]) -> set[str]:
    anchor_set = {anchor for anchor in anchors if anchor}
    return {anchor for anchor in anchor_set if any(_anchor_in_text([anchor], text) for text in texts)}


def _gate_coverage(anchors: Iterable[str], hits: Iterable[str]) -> float:
    anchor_set = {anchor for anchor in anchors if anchor}
    if not anchor_set:
        return 1.0
    return round(len(set(hits) & anchor_set) / max(1, len(anchor_set)), 6)


def _gate_rows_match(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    source_identity_keys = ("evidence_bundle_id", "source_atom_id")
    left_source_ids = {_clean(left.get(key)) for key in source_identity_keys if _clean(left.get(key))}
    right_source_ids = {_clean(right.get(key)) for key in source_identity_keys if _clean(right.get(key))}
    if left_source_ids and right_source_ids and not (left_source_ids & right_source_ids):
        return False
    for key in (*source_identity_keys, "chunk_id", "search_unit_id", "search_view_id"):
        left_value = _clean(left.get(key))
        right_value = _clean(right.get(key))
        if left_value and right_value and left_value == right_value:
            return True
    left_doc = _clean(left.get("doc_id") or left.get("docId") or left.get("document_id"))
    right_doc = _clean(right.get("doc_id") or right.get("docId") or right.get("document_id"))
    left_chunk = _clean(left.get("chunk_id") or left.get("chunkId"))
    right_chunk = _clean(right.get("chunk_id") or right.get("chunkId"))
    if left_doc and right_doc and left_doc == right_doc:
        if not left_chunk and not right_chunk:
            return True
        if left_chunk and right_chunk and left_chunk == right_chunk:
            return True
    left_hash = _gate_row_hash(left)
    right_hash = _gate_row_hash(right)
    return bool(left_hash and right_hash and left_hash == right_hash)


def _gate_select_evidence(
    *,
    query: str,
    answer: str,
    contexts: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    anchors = _gate_answer_anchors(query, answer)
    answer_anchors = set(anchors["answer"])
    numeric = set(anchors["numeric_or_date"])
    entity = set(anchors["entity"])
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for context in contexts:
        text = _gate_support_text(context)
        text_hits = _gate_anchor_hits(answer_anchors, [text])
        numeric_ok = not numeric or bool(text_hits & numeric)
        entity_ok = not entity or bool(text_hits & entity)
        required_anchor_ok = numeric_ok and entity_ok
        answer_overlap = _token_overlap_ratio(answer, text)
        query_overlap = _token_overlap_ratio(query, text)
        if text_hits and (
            required_anchor_ok
            or (not numeric and not entity and (answer_overlap >= 0.35 or query_overlap >= 0.35))
        ):
            identity = _context_identity(context)
            if identity and identity not in seen:
                selected.append(_runtime_safe_evidence_context(context))
                seen.add(identity)
    return selected


def _gate_select_axis_complete_evidence(
    *,
    query: str,
    answer: str,
    contexts: Sequence[Mapping[str, Any]],
    planner: Mapping[str, Any],
    source_family_hint: str,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    row = {
        "query": query,
        "query_evidence_planner": planner,
    }
    for context in contexts:
        if not _query_evidence_source_family_matches_context(source_family_hint, context):
            continue
        matched_axes, missing_axes = _query_evidence_gate_validated_required_axis_hits(
            row=row,
            selected_evidence=[context],
            answer=answer,
        )
        if not matched_axes or missing_axes:
            continue
        identity = _context_identity(context)
        if identity and identity not in seen:
            selected.append(_runtime_safe_evidence_context(context))
            seen.add(identity)
    return selected


def _has_sourceatom_evidence_identity(row: Mapping[str, Any]) -> bool:
    return bool(_clean(row.get("source_atom_id")) or _clean(row.get("evidence_bundle_id")))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _query_requires_numeric_or_date_answer(query: str) -> bool:
    normalized = normalize_answer_text(query)
    markers = {
        "when",
        "date",
        "year",
        "month",
        "day",
        "how many",
        "number",
        "언제",
        "몇",
        "몇년",
        "몇월",
        "날짜",
        "년도",
        "연도",
        "시기",
        "얼마",
    }
    return any(marker in normalized for marker in markers)


def _text_has_numeric_or_date_value(text: str) -> bool:
    normalized = normalize_answer_text(text)
    if re.search(r"\d", normalized):
        return True
    if re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", normalized):
        return True
    return bool(re.search(r"[일월년]", normalized) and re.search(r"[0-9영일이삼사오육칠팔구십]", normalized))


def _text_has_answer_value_anchor_beyond_query(query: str, text: str) -> bool:
    if not _query_requires_numeric_or_date_answer(query):
        return True
    query_value_anchors = set(_numeric_or_date_anchors(_candidate_anchors(query)))
    evidence_value_anchors = set(_numeric_or_date_anchors(_candidate_anchors(text)))
    return any(anchor and anchor not in query_value_anchors for anchor in evidence_value_anchors)


def _xlsx_selected_evidence_has_value_and_axes(
    query: str,
    context: Mapping[str, Any],
    *,
    query_evidence_planner: Mapping[str, Any] | None = None,
) -> bool:
    if _clean(context.get("source_family")).upper() != "XLSX":
        return True
    if not _text_has_answer_value_anchor_beyond_query(query, _gate_support_text(context)):
        return False
    metadata_text, metadata_fields = source_derived_evidence_metadata(context)
    fields = set(metadata_fields)
    has_scope_axis = bool(fields & {"sheet", "cell", "cell_range", "table_id"})
    has_row_or_column_axis = bool(
        fields & {"cell", "cell_range", "row_index_1based", "row_label", "column_label", "target_column", "header", "header_path"}
    )
    if not (has_scope_axis and has_row_or_column_axis):
        return False
    axis_complete, _matched_axes, _missing_axes = _query_evidence_context_has_complete_validated_axes(
        query=query,
        query_evidence_planner=query_evidence_planner,
        context=context,
    )
    if axis_complete:
        return True
    query_anchors = _gate_query_focus_anchors(query)
    if not query_anchors:
        return True
    return bool(_gate_anchor_hits(query_anchors, [metadata_text])) or _token_overlap_ratio(query, metadata_text) >= 0.2


def _pdf_selected_evidence_has_value_and_axes(
    query: str,
    context: Mapping[str, Any],
    *,
    query_evidence_planner: Mapping[str, Any] | None = None,
) -> bool:
    if _clean(context.get("source_family")).upper() != "PDF":
        return True
    if not _text_has_answer_value_anchor_beyond_query(query, _gate_row_text(context)):
        return False
    metadata_text, metadata_fields = source_derived_evidence_metadata(context)
    fields = set(metadata_fields)
    has_page_or_section_axis = bool(
        fields & {"page_number", "page", "physical_page_index", "section_title", "table_caption"}
    )
    has_table_or_block_axis = bool(
        fields & {"table_caption", "row_label", "column_label", "block_index", "bbox", "locator_fingerprint"}
    )
    if not (has_page_or_section_axis and has_table_or_block_axis):
        return False
    axis_complete, _matched_axes, _missing_axes = _query_evidence_context_has_complete_validated_axes(
        query=query,
        query_evidence_planner=query_evidence_planner,
        context=context,
    )
    if axis_complete:
        return True
    query_anchors = _gate_query_focus_anchors(query)
    if not query_anchors:
        return True
    return bool(_gate_anchor_hits(query_anchors, [metadata_text])) or _token_overlap_ratio(query, metadata_text) >= 0.2


def select_composer_evidence(
    query: str,
    contexts: Sequence[Mapping[str, Any]],
    *,
    max_evidence: int = 3,
    query_evidence_planner: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    planner = _query_evidence_planner_for_query(query, query_evidence_planner)
    source_family_hint = _query_evidence_source_family_hint(planner)
    query_anchors = _gate_query_focus_anchors(query)
    selected: list[tuple[float, int, dict[str, Any]]] = []
    seen: set[str] = set()
    for index, context in enumerate(contexts, start=1):
        if not _has_sourceatom_evidence_identity(context):
            continue
        if not _query_evidence_source_family_matches_context(source_family_hint, context):
            continue
        text = _gate_support_text(context)
        if not text:
            continue
        if not _xlsx_selected_evidence_has_value_and_axes(
            query,
            context,
            query_evidence_planner=planner,
        ):
            continue
        if not _pdf_selected_evidence_has_value_and_axes(
            query,
            context,
            query_evidence_planner=planner,
        ):
            continue
        identity = _context_identity(context)
        if not identity or identity in seen:
            continue
        axis_complete, matched_validated_axes, missing_validated_axes = _query_evidence_context_has_complete_validated_axes(
            query=query,
            query_evidence_planner=planner,
            context=context,
        )
        anchor_hits = _gate_anchor_hits(query_anchors, [text])
        query_overlap = _token_overlap_ratio(query, text)
        if query_anchors:
            if not axis_complete and not anchor_hits and query_overlap < 0.2:
                continue
        elif not axis_complete and query_overlap < 0.2:
            continue
        score = (100.0 if axis_complete else 0.0) + (len(anchor_hits) * 10.0) + query_overlap + _safe_float(
            context.get("score") or context.get("fusion_score")
        )
        row = dict(context)
        metadata_text, metadata_fields = source_derived_evidence_metadata(context)
        if metadata_text:
            row["composer_source_derived_metadata_text"] = metadata_text
            row["composer_source_derived_metadata_fields"] = metadata_fields
        row["composer_query_anchor_hits"] = sorted(anchor_hits)
        row["composer_query_overlap"] = round(query_overlap, 6)
        if source_family_hint:
            row["composer_source_family_hint"] = source_family_hint
            row["composer_source_family_hint_matched"] = True
        if matched_validated_axes or missing_validated_axes:
            row["composer_validated_required_axis_hits"] = matched_validated_axes
            row["composer_missing_validated_required_axes"] = missing_validated_axes
            row["composer_validated_required_axes_coverage"] = _gate_coverage(
                matched_validated_axes + missing_validated_axes,
                matched_validated_axes,
            )
        selected.append((score, index, row))
        seen.add(identity)
    selected.sort(key=lambda item: (-item[0], item[1]))
    return [row for _, _, row in selected[: max(1, int(max_evidence))]]


NUMERIC_OR_DATE_VALUE_PATTERN = re.compile(
    r"\d{1,4}(?:년|월|일|세|cm|kg|%)?"
    r"|\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
    flags=re.IGNORECASE,
)


def _query_anchor_pattern(anchor: str) -> str:
    escaped = r"\s+".join(re.escape(part) for part in _clean(anchor).split())
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_\s-]*", anchor):
        return rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])"
    if re.fullmatch(r"[가-힣]+", anchor):
        suffixes = "|".join(re.escape(suffix) for suffix in KOREAN_GENERIC_SUFFIXES)
        return rf"(?<![가-힣]){escaped}(?:{suffixes})?(?![가-힣])"
    return escaped


def _value_span_end_after_anchor(text: str, anchor_end: int) -> int:
    first = NUMERIC_OR_DATE_VALUE_PATTERN.search(text, anchor_end)
    if first is None:
        return -1
    if re.search(r"[A-Za-z가-힣ぁ-んァ-ン一-龯々]", text[anchor_end : first.start()]):
        return -1
    end = first.end()
    for match in NUMERIC_OR_DATE_VALUE_PATTERN.finditer(text, end):
        gap = text[end : match.start()]
        if re.search(r"[A-Za-z가-힣ぁ-んァ-ン一-龯々]", gap):
            break
        if len(gap) > 12:
            break
        end = match.end()
    return end


def _numeric_focus_query_anchors(query: str) -> set[str]:
    stopwords = _anchor_stopwords() | {
        normalize_answer_text(value) for value in EVIDENCE_GATE_QUERY_INTENT_STOPWORDS
    }
    anchors = set(_gate_query_focus_anchors(query))
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}|[가-힣]{2,}", query or ""):
        normalized = normalize_answer_text(token)
        if not normalized or _is_generic_anchor(normalized, stopwords):
            continue
        anchors.add(normalized)
    return anchors


def _selected_evidence_numeric_date_focus_span(query: str, text: str) -> str:
    if not _clean(text):
        return ""
    spans: list[tuple[int, int]] = []
    for anchor in sorted(_numeric_focus_query_anchors(query), key=len, reverse=True):
        if not anchor or re.search(r"\d", anchor):
            continue
        for match in re.finditer(_query_anchor_pattern(anchor), text, flags=re.IGNORECASE):
            end = _value_span_end_after_anchor(text, match.end())
            if end < 0:
                continue
            spans.append((match.start(), end))
            break
    if not spans:
        return ""
    spans.sort()
    pieces: list[str] = []
    last_end = -1
    for start, end in spans:
        if start < last_end:
            continue
        piece = _clean(text[start:end].strip(" ,;:："))
        if piece and piece not in pieces:
            pieces.append(piece)
            last_end = end
    separator = ". " if re.search(r"[A-Za-z]", " ".join(pieces)) else " "
    return _clean(separator.join(pieces))


def _selected_evidence_sentence(query: str, selected_evidence: Sequence[Mapping[str, Any]]) -> str:
    query_anchors = _gate_query_focus_anchors(query)
    best_sentence = ""
    best_score = -1.0
    for context in selected_evidence:
        text = _gate_support_text(context)
        if not text:
            continue
        facet_span = _selected_evidence_numeric_date_focus_span(query, text)
        if facet_span:
            sentences = [facet_span]
        else:
            sentences = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+|\n+", text) if part.strip()]
            if not sentences:
                sentences = [text.strip()]
            candidates = [text.strip(), *sentences] if len(sentences) > 1 else sentences
            sentences = candidates
        for sentence in sentences:
            anchor_hits = _gate_anchor_hits(query_anchors, [sentence, text])
            score = (len(anchor_hits) * 10.0) + _token_overlap_ratio(query, sentence)
            if score > best_score:
                best_score = score
                best_sentence = sentence
    answer = _clean(best_sentence)
    if len(answer) > 240:
        answer = answer[:237] + "..."
    if answer and not answer.endswith((".", "!", "?", "。", "！", "？")):
        answer += "."
    return answer


def _normalized_axis_text(value: Any) -> str:
    return normalize_answer_text(_clean(value)).replace(" ", "")


def _axis_value_matches(left: Any, right: Any) -> bool:
    left_norm = _normalized_axis_text(left)
    right_norm = _normalized_axis_text(right)
    return bool(left_norm and right_norm and (left_norm in right_norm or right_norm in left_norm))


def _query_requests_person_count_answer(query: str, target_column: str) -> bool:
    text = f"{query} {target_column}"
    normalized = normalize_answer_text(text).replace(" ", "")
    return any(marker in normalized for marker in ("몇명", "명입니까", "승객수", "수송인원", "인원수"))


def _format_xlsx_display_value_answer(*, query: str, target_column: str, display_value: str) -> str:
    value = _clean(display_value)
    if not value:
        return ""
    rendered = value
    if re.fullmatch(r"\d+", value) and _query_requests_person_count_answer(query, target_column):
        rendered = f"{int(value):,}명"
    if re.search(r"[가-힣]", query) and not re.search(r"(입니다|다)$", rendered):
        rendered = f"{rendered}입니다."
    return rendered


def _source_owned_xlsx_display_answer_candidate(
    *,
    query: str,
    selected_evidence: Sequence[Mapping[str, Any]],
    query_evidence_planner: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not query_evidence_planner:
        return {}
    target_axis_values = _query_evidence_axis_values(query_evidence_planner, "target_column")
    if not target_axis_values:
        return {}
    candidates: list[dict[str, Any]] = []
    for evidence in selected_evidence:
        if _clean(evidence.get("source_family")).upper() != "XLSX":
            continue
        target_column = _clean(evidence.get("target_column") or evidence.get("column_label") or evidence.get("header"))
        display_value = _clean(evidence.get("display_value"))
        if not target_column or not display_value:
            continue
        if not any(_axis_value_matches(target_column, target_value) for target_value in target_axis_values):
            continue
        axis_complete, matched_axes, _missing_axes = _query_evidence_context_has_complete_validated_axes(
            query=query,
            query_evidence_planner=query_evidence_planner,
            context=evidence,
        )
        if not axis_complete:
            continue
        answer = _format_xlsx_display_value_answer(
            query=query,
            target_column=target_column,
            display_value=display_value,
        )
        if answer:
            candidates.append(
                {
                    "answer": answer,
                    "target_column": target_column,
                    "display_value": display_value,
                    "matched_validated_required_axes": matched_axes,
                    "source_fields": ["target_column", "display_value"],
                }
            )
    if not candidates:
        return {}
    unique_display_values = {_normalized_axis_text(candidate.get("display_value")) for candidate in candidates}
    unique_display_values.discard("")
    if len(unique_display_values) > 1:
        return {
            "skip_reason": "ambiguous_xlsx_display_value_candidates",
            "candidate_count": len(candidates),
        }
    return candidates[0]


def _selected_evidence_abstention_reason(query: str, selected_evidence: Sequence[Mapping[str, Any]]) -> str:
    if not selected_evidence:
        return "no_selected_sourceatom_evidence"
    selected_text = " ".join(_gate_row_text(row) for row in selected_evidence if _gate_row_text(row))
    if _query_requires_numeric_or_date_answer(query) and not _text_has_numeric_or_date_value(selected_text):
        return "insufficient_selected_evidence"
    if not _selected_evidence_sentence(query, selected_evidence):
        return "insufficient_selected_evidence"
    return ""


def _selected_evidence_answer(
    *,
    query: str,
    selected_evidence: Sequence[Mapping[str, Any]],
    citation_format: str = "compact",
    formatted_citations: Sequence[str] | None = None,
    short_answer_override: str = "",
) -> str:
    short_answer = _clean(short_answer_override) or _selected_evidence_sentence(query, selected_evidence)
    if not short_answer:
        return BOUNDED_EVIDENCE_ABSTENTION_ANSWER
    lines = [
        f"**Query:** {query}",
        "",
        f"**Short answer:** {short_answer}",
        "",
        "**Supporting passages:**",
    ]
    for index, evidence in enumerate(selected_evidence, start=1):
        citation = _normalize_citation(evidence)
        locator = "#".join(
            part
            for part in (
                _clean(citation.get("doc_id")),
                _clean(citation.get("chunk_id")),
                _clean(citation.get("source_atom_id")),
                _clean(citation.get("evidence_bundle_id")),
            )
            if part
        )
        excerpt = _selected_evidence_sentence(query, [evidence]) or _gate_row_text(evidence)
        excerpt = excerpt.replace("\n", " ").strip()
        if len(excerpt) > 220:
            excerpt = excerpt[:217] + "..."
        lines.append(f"{index}. [{locator}] {excerpt}")
    if citation_format == "markdown-portfolio" and formatted_citations:
        lines.extend(["", "## Selected Evidence Citations"])
        lines.extend(formatted_citations)
    return "\n".join(lines)


def _selected_evidence_ids(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    ids: list[str] = []
    for row in rows:
        identity = _clean(row.get("evidence_bundle_id")) or _clean(row.get("source_atom_id")) or _context_identity(row)
        if identity and identity not in ids:
            ids.append(identity)
    return ids


def _normalize_selected_evidence_citation_format(citation_format: str) -> str:
    normalized = _clean(citation_format).replace("_", "-").lower() or "compact"
    if normalized not in SELECTED_EVIDENCE_CITATION_FORMATS:
        raise DatasetSchemaError(f"unsupported selected evidence citation format: {citation_format}")
    return normalized


def _normalize_selected_evidence_composer_retry_mode(retry_mode: str) -> str:
    normalized = _clean(retry_mode).replace("_", "-").lower() or "off"
    if normalized not in SELECTED_EVIDENCE_COMPOSER_RETRY_MODES:
        raise DatasetSchemaError(f"unsupported selected evidence composer retry mode: {retry_mode}")
    return normalized


def _selected_citation_locator(row: Mapping[str, Any]) -> str:
    doc_id = _clean(row.get("doc_id") or row.get("docId") or row.get("document_id"))
    chunk_id = _clean(row.get("chunk_id") or row.get("chunkId") or row.get("search_unit_id"))
    if doc_id and chunk_id:
        return f"{doc_id}#{chunk_id}"
    for key in ("evidence_bundle_id", "source_atom_id", "text_sha256", "source_text_sha256"):
        value = _clean(row.get(key))
        if value:
            return value
    return "selected-evidence"


def _selected_citation_identity_parts(row: Mapping[str, Any]) -> list[str]:
    parts: list[str] = []
    evidence_bundle_id = _clean(row.get("evidence_bundle_id"))
    source_atom_id = _clean(row.get("source_atom_id"))
    if evidence_bundle_id:
        parts.append(f"evidence_bundle_id={evidence_bundle_id}")
    if source_atom_id:
        parts.append(f"source_atom_id={source_atom_id}")
    return parts


def format_selected_evidence_citations(
    selected_evidence: Sequence[Mapping[str, Any]],
    *,
    citation_format: str = "compact",
) -> list[str]:
    normalized_format = _normalize_selected_evidence_citation_format(citation_format)
    formatted: list[str] = []
    for index, evidence in enumerate(selected_evidence, start=1):
        locator = _selected_citation_locator(evidence)
        if normalized_format == "compact":
            formatted.append(f"[{index}] {locator}")
            continue
        identity_parts = _selected_citation_identity_parts(evidence)
        identity = "; ".join(identity_parts) if identity_parts else locator
        if normalized_format == "evidence-id":
            formatted.append(f"[{index}] {identity}")
            continue
        source_family = _clean(evidence.get("source_family")) or "UNKNOWN"
        granularity = _clean(evidence.get("granularity")) or "unknown"
        locator_parts = [source_family, granularity, locator]
        for label, key in (
            ("page", "page_number"),
            ("sheet", "sheet"),
            ("cell_range", "cell_range"),
            ("locator", "locator_fingerprint"),
        ):
            value = _clean(evidence.get(key))
            if value:
                locator_parts.append(f"{label}={value}")
        if normalized_format == "source-locator":
            formatted.append(f"[{index}] {' '.join(locator_parts)}")
            continue
        formatted.append(f"- [{index}] **{source_family} {granularity}** {locator} ({identity})")
    return formatted


def _bounded_text_preview(value: Any, limit: int = 240) -> str:
    text = _clean(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _local_llm_composer_config(
    *,
    backend: str = "",
    base_url: str = "",
    model: str = "",
    timeout_seconds: int = 60,
    max_tokens: int = 360,
    check_endpoint: bool = True,
) -> dict[str, Any]:
    resolved_backend = _clean(backend) or LOCAL_LLM_HELPER.DEFAULT_BACKEND
    resolved_base_url = LOCAL_LLM_HELPER.resolve_base_url(resolved_backend, _clean(base_url))
    resolved_model = _clean(model) or LOCAL_LLM_HELPER.DEFAULT_MODEL
    blockers = LOCAL_LLM_HELPER.local_llm_entry_blockers(
        backend=resolved_backend,
        base_url=resolved_base_url,
        model=resolved_model,
        check_endpoint=check_endpoint,
        timeout_seconds=min(int(timeout_seconds), 10),
    )
    return {
        "backend": resolved_backend,
        "base_url": resolved_base_url,
        "model": resolved_model,
        "timeout_seconds": int(timeout_seconds),
        "max_tokens": int(max_tokens),
        "check_endpoint": bool(check_endpoint),
        "available": not blockers,
        "blockers": list(blockers),
        "prompt_template_id": SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROMPT_VERSION,
        "strict_json_required": True,
        "external_api_calls": False,
    }


def _selected_evidence_local_llm_prompt(
    *,
    query: str,
    selected_evidence: Sequence[Mapping[str, Any]],
) -> str:
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
        "query": query,
        "input_policy": SELECTED_EVIDENCE_COMPOSER_INPUT_POLICY,
        "selected_evidence": evidence_payload,
        "citation_policy": "citation_evidence_ids must be selected evidence_id, evidence_bundle_id, or source_atom_id values only",
    }
    return SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROMPT_TEMPLATE.format(
        payload=json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def _selected_evidence_local_llm_retry_prompt(
    *,
    query: str,
    selected_evidence: Sequence[Mapping[str, Any]],
    missing_query_focus_anchors: Sequence[str],
    previous_answer_preview: str,
    answer_discipline_status: str = "",
    answer_discipline_issue_preview: str = "",
) -> str:
    evidence_payload: list[dict[str, Any]] = []
    for evidence in selected_evidence:
        citation = _normalize_citation(evidence)
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
                "text_preview": _bounded_text_preview(_gate_row_text(evidence), 1000),
            }
        )
    payload = {
        "query": query,
        "input_policy": SELECTED_EVIDENCE_COMPOSER_RETRY_INPUT_POLICY,
        "selected_evidence": evidence_payload,
        "missing_query_focus_anchors": [_clean(anchor) for anchor in missing_query_focus_anchors if _clean(anchor)],
        "previous_answer_preview": _bounded_text_preview(previous_answer_preview),
        "answer_discipline_status": _clean(answer_discipline_status),
        "answer_discipline_issue_preview": _bounded_text_preview(answer_discipline_issue_preview),
        "citation_policy": "citation_evidence_ids must be selected evidence_id, evidence_bundle_id, or source_atom_id values only",
        "max_retry_count": 1,
    }
    return SELECTED_EVIDENCE_LOCAL_LLM_RETRY_PROMPT_TEMPLATE.format(
        payload=json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def _ids_from_local_llm_citation_field(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        values = [item for item in value if isinstance(item, str)]
    else:
        values = []
    ids: list[str] = []
    for item in values:
        identity = _clean(item)
        if identity and identity not in ids:
            ids.append(identity)
    return ids


def _selected_evidence_matching_ids(
    selected_evidence: Sequence[Mapping[str, Any]],
    citation_ids: Sequence[str],
) -> list[dict[str, Any]]:
    wanted = {_clean(value) for value in citation_ids if _clean(value)}
    if not wanted:
        return []
    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for evidence in selected_evidence:
        candidate_ids = {
            _clean(evidence.get("evidence_bundle_id")),
            _clean(evidence.get("source_atom_id")),
            _context_identity(evidence),
        }
        if wanted & {value for value in candidate_ids if value}:
            identity = _context_identity(evidence)
            if identity and identity not in seen:
                matched.append(dict(evidence))
                seen.add(identity)
    return matched


def _selected_evidence_answer_units(answer: str) -> list[str]:
    text = _gate_answer_surface(_clean(answer))
    if not text:
        return []
    text = re.sub(r"\s+", " ", text.replace("\r", "\n")).strip()
    units = [
        _clean(part)
        for part in re.split(r"\s*(?:[.!?。！？;；]|\n+|,(?!\d)\s*)\s*", text)
        if _clean(part)
    ]
    if not units and text:
        units = [text]
    return units


def _selected_evidence_valid_citation_ids(selected_evidence: Sequence[Mapping[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for evidence in selected_evidence:
        for value in (
            evidence.get("evidence_bundle_id"),
            evidence.get("source_atom_id"),
            _context_identity(evidence),
        ):
            cleaned = _clean(value)
            if cleaned:
                ids.add(cleaned)
    return ids


def _selected_evidence_unit_supported(unit: str, selected_evidence: Sequence[Mapping[str, Any]]) -> bool:
    support_text = " ".join(_gate_support_text(evidence) for evidence in selected_evidence if _gate_support_text(evidence))
    if not support_text:
        return False
    unit_norm = normalize_answer_text(unit)
    support_norm = normalize_answer_text(support_text)
    if unit_norm and unit_norm in support_norm:
        return True
    anchors = _candidate_anchors(unit)
    if anchors and _anchor_requirements_satisfied(anchors, support_text):
        return True
    if _token_overlap_ratio(unit, support_text) >= 0.55:
        return True
    unit_numbers = set(re.findall(r"\d[\d,./:-]*", unit_norm))
    support_numbers = set(re.findall(r"\d[\d,./:-]*", support_norm))
    unit_words = {word for word in re.findall(r"[a-z가-힣]{2,}", unit_norm) if word not in _anchor_stopwords()}
    support_words = {word for word in re.findall(r"[a-z가-힣]{2,}", support_norm)}
    return bool(unit_numbers and unit_numbers <= support_numbers and unit_words & support_words)


def _source_derived_values(row: Mapping[str, Any], fields: Sequence[str]) -> list[str]:
    values: list[str] = []
    for source in _source_derived_metadata_sources(row):
        for field in fields:
            value = _clean(source.get(field))
            if value and value not in values:
                values.append(value)
    return values


def _selected_evidence_source_value_query_relevant(
    query: str,
    unit: str,
    selected_evidence: Sequence[Mapping[str, Any]],
) -> bool:
    unit_norm = normalize_answer_text(unit)
    query_norm = normalize_answer_text(query)
    if not unit_norm or not query_norm:
        return False
    focus_fields = ("target_column", "column_label", "header", "header_path", "section_title", "table_caption")
    value_fields = ("display_value",)
    location_terms = {"where", "location", "headquarters", "hq", "address", "주소", "위치", "소재지"}
    birthday_terms = {"birthday", "birthdate", "생일", "생년월일", "출생일"}
    age_terms = {"age", "aged", "나이", "연령"}
    count_terms = {"how many", "count", "number", "total", "몇", "얼마", "수", "총"}
    for evidence in selected_evidence:
        if not isinstance(evidence, Mapping):
            continue
        value_matches = False
        for value in _source_derived_values(evidence, value_fields):
            value_norm = normalize_answer_text(value)
            if value_norm and (unit_norm in value_norm or value_norm in unit_norm):
                value_matches = True
                break
        if not value_matches:
            continue
        focus_values = _source_derived_values(evidence, focus_fields)
        focus_text = " ".join(focus_values)
        focus_norm = normalize_answer_text(focus_text)
        if not focus_norm:
            continue
        focus_anchors = _candidate_anchors(*focus_values)
        if _gate_anchor_hits(focus_anchors, [query]):
            return True
        if any(term in query_norm for term in location_terms) and any(term in focus_norm for term in location_terms):
            return True
        if any(term in query_norm for term in birthday_terms) and any(term in focus_norm for term in birthday_terms):
            return True
        if any(term in query_norm for term in age_terms) and any(term in focus_norm for term in age_terms):
            return True
        if any(term in query_norm for term in count_terms) and any(term in focus_norm for term in count_terms):
            return True
    return False


def _selected_evidence_unit_query_relevant(
    query: str,
    unit: str,
    selected_evidence: Sequence[Mapping[str, Any]],
) -> bool:
    query_norm = normalize_answer_text(query)
    unit_norm = normalize_answer_text(unit)
    query_anchors = _gate_query_focus_anchors(query)
    if not query_anchors:
        return True
    hits = _gate_anchor_hits(query_anchors, [unit])
    if _gate_coverage(query_anchors, hits) >= EVIDENCE_GATE_MIN_QUERY_ANCHOR_COVERAGE:
        return True
    if _selected_evidence_source_value_query_relevant(query, unit, selected_evidence):
        return True
    age_terms = {"age", "aged", "나이", "연령"}
    birthday_terms = {"birthday", "birthdate", "생일", "생년월일", "출생일"}
    location_terms = {"where", "location", "headquarters", "hq", "주소", "위치", "소재지"}
    count_terms = {"how many", "count", "number", "몇", "얼마", "수", "총"}
    if any(term in query_norm for term in age_terms) and re.search(r"\d", unit_norm) and (
        hits or any(term in unit_norm for term in age_terms)
    ):
        return True
    birthday_like = bool(
        re.search(r"\d{1,4}\s*(?:년|월|일)|\d{1,2}/\d{1,2}", unit_norm)
        or any(
            month in unit_norm
            for month in (
                "january",
                "february",
                "march",
                "april",
                "may",
                "june",
                "july",
                "august",
                "september",
                "october",
                "november",
                "december",
            )
        )
    )
    if any(term in query_norm for term in birthday_terms) and (
        hits or any(term in unit_norm for term in birthday_terms) or birthday_like
    ):
        return True
    if any(term in query_norm for term in location_terms) and hits:
        return True
    if any(term in query_norm for term in count_terms) and re.search(r"\d", unit_norm) and hits:
        return True
    return False


def _selected_evidence_answer_discipline_fallback_reason(discipline: Mapping[str, Any]) -> str:
    status = _clean(discipline.get("status")) or "unsupported_or_empty"
    if status == "clean_supported":
        return ""
    return f"answer_discipline_{status}"


def _selected_evidence_answer_discipline(
    *,
    query: str,
    answer: str,
    selected_evidence: list[dict[str, object]] | Sequence[Mapping[str, Any]],
    cited_evidence_ids: list[str] | Sequence[str] | None = None,
) -> dict[str, object]:
    selected = [dict(evidence) for evidence in selected_evidence if isinstance(evidence, Mapping)]
    answer_text = _gate_answer_surface(_clean(answer))
    units = _selected_evidence_answer_units(answer_text)
    wanted_ids = [_clean(value) for value in (cited_evidence_ids or []) if _clean(value)]
    valid_ids = _selected_evidence_valid_citation_ids(selected)
    unresolved_ids = sorted({value for value in wanted_ids if value not in valid_ids})
    supported_units: list[str] = []
    unsupported_units: list[str] = []
    relevant_supported_units: list[str] = []
    irrelevant_supported_units: list[str] = []
    for unit in units:
        supported = _selected_evidence_unit_supported(unit, selected)
        relevant = _selected_evidence_unit_query_relevant(query, unit, selected)
        if supported:
            supported_units.append(unit)
            if relevant:
                relevant_supported_units.append(unit)
            else:
                irrelevant_supported_units.append(unit)
        else:
            unsupported_units.append(unit)

    core_supported = bool(relevant_supported_units)
    morphology_false_negative = bool(
        unsupported_units
        and selected
        and any(
            _token_overlap_ratio(unit, " ".join(_gate_support_text(evidence) for evidence in selected)) >= 0.45
            for unit in unsupported_units
        )
    )
    if not answer_text or not units:
        status = "unsupported_or_empty"
    elif not selected:
        status = "true_insufficient_evidence"
    elif unresolved_ids:
        status = "citation_id_mismatch_or_missing"
    elif core_supported and unsupported_units:
        status = "supported_core_with_unsupported_extra"
    elif core_supported and irrelevant_supported_units:
        status = "query_irrelevant_supported_detail"
    elif unsupported_units and morphology_false_negative:
        status = "anchor_morphology_false_negative"
    elif unsupported_units:
        status = "unsupported_or_empty"
    elif not core_supported:
        status = "true_insufficient_evidence"
    else:
        status = "clean_supported"

    if status not in SELECTED_EVIDENCE_ANSWER_DISCIPLINE_STATUSES:
        status = "unsupported_or_empty"
    fallback_reason = "" if status == "clean_supported" else f"answer_discipline_{status}"
    return {
        "status": status,
        "core_answer_supported": bool(core_supported and status != "citation_id_mismatch_or_missing"),
        "unsupported_extra_detail": status == "supported_core_with_unsupported_extra",
        "query_irrelevant_supported_detail": status == "query_irrelevant_supported_detail",
        "local_llm_accepted_without_fallback": status == "clean_supported",
        "fallback_reason": fallback_reason,
        "unsupported_extra_preview": _bounded_text_preview(unsupported_units[0], 160) if unsupported_units else "",
        "query_irrelevant_preview": _bounded_text_preview(irrelevant_supported_units[0], 160) if irrelevant_supported_units else "",
        "citation_id_mismatch_or_missing": bool(unresolved_ids),
        "unresolved_citation_ids": unresolved_ids[:5],
        "assertion_unit_count": len(units),
        "supported_assertion_unit_count": len(supported_units),
        "input_policy": SELECTED_EVIDENCE_ANSWER_DISCIPLINE_INPUT_POLICY,
    }


def _selected_evidence_deterministic_fallback_answer_discipline(
    *,
    query: str,
    answer: str,
    selected_evidence: list[dict[str, object]] | Sequence[Mapping[str, Any]],
    cited_evidence_ids: list[str] | Sequence[str] | None = None,
) -> dict[str, object]:
    discipline = _selected_evidence_answer_discipline(
        query=query,
        answer=answer,
        selected_evidence=selected_evidence,
        cited_evidence_ids=cited_evidence_ids,
    )
    if _clean(discipline.get("status")) in {
        "supported_core_with_unsupported_extra",
        "query_irrelevant_supported_detail",
    }:
        discipline["status"] = "local_llm_rejected_then_deterministic_overexpanded"
        discipline["fallback_reason"] = "answer_discipline_local_llm_rejected_then_deterministic_overexpanded"
    return discipline


def _local_llm_meta(
    *,
    config: Mapping[str, Any],
    status: str,
    prompt_sha256: str = "",
    raw_response_sha256: str = "",
    answer_preview: str = "",
    blockers: Sequence[str] = (),
    fallback_provider: str = "",
    fallback_reason: str = "",
) -> dict[str, Any]:
    meta = {
        "status": status,
        "backend": config.get("backend"),
        "base_url": config.get("base_url"),
        "model": config.get("model"),
        "available": bool(config.get("available")),
        "prompt_template_id": SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROMPT_VERSION,
        "strict_json_required": True,
        "external_api_calls": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }
    if prompt_sha256:
        meta["prompt_sha256"] = prompt_sha256
    if raw_response_sha256:
        meta["raw_response_sha256"] = raw_response_sha256
    if answer_preview:
        meta["answer_preview"] = _bounded_text_preview(answer_preview)
    if blockers:
        meta["blockers"] = list(blockers)
    elif config.get("blockers"):
        meta["blockers"] = list(config.get("blockers") or [])
    if fallback_provider:
        meta["fallback_provider"] = fallback_provider
    if fallback_reason:
        meta["fallback_reason"] = fallback_reason
    return meta


def _selected_evidence_retry_not_triggered_meta(reason: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "attempted": False,
        "attempt_count": 0,
        "max_retry_count": 1,
        "mode": "bounded-once",
        "status": "not_triggered",
        "reason": reason,
        "input_policy": SELECTED_EVIDENCE_COMPOSER_RETRY_INPUT_POLICY,
    }


def _selected_evidence_retry_trigger(validation: Mapping[str, Any], decision: str) -> str:
    status = _clean(validation.get("evidence_package_status"))
    reasons = {_clean(reason) for reason in _as_list(validation.get("validation_reasons")) if _clean(reason)}
    missing_query = [_clean(anchor) for anchor in _as_list(validation.get("missing_query_anchors")) if _clean(anchor)]
    if status == "insufficient":
        return "evidence_gate_insufficient"
    if missing_query or "missing_query_anchor" in reasons:
        return "missing_query_focus_anchor"
    if decision == "block_unsupported_answer":
        return "evidence_gate_blocked_answer"
    return ""


def _selected_evidence_gate_validation_for_answer(
    *,
    row: Mapping[str, Any],
    query: str,
    answer: str,
    selected_evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validation_row = dict(row)
    selected = [dict(evidence) for evidence in selected_evidence if isinstance(evidence, Mapping)]
    validation_row["query"] = query
    validation_row["generated_answer"] = _clean(answer)
    validation_row["retrieved_contexts"] = selected
    validation_row["citations"] = [_normalize_citation(evidence) for evidence in selected]
    return validate_evidence_package_for_gate(validation_row)


def _selected_evidence_local_llm_output_from_answer(
    *,
    row: Mapping[str, Any],
    query: str,
    query_selected: Sequence[Mapping[str, Any]],
    answer: str,
    citation_ids: Sequence[str],
    normalized_citation_format: str,
    config: Mapping[str, Any],
    prompt_sha256: str,
    raw_response_sha256: str,
    retry_meta: Mapping[str, Any] | None = None,
    answer_discipline: Mapping[str, Any] | None = None,
    allow_gate_aligned_fallback: bool = True,
) -> dict[str, Any] | None:
    cited_selected = _selected_evidence_matching_ids(query_selected, citation_ids)
    candidate_selected = cited_selected or query_selected
    discipline = dict(
        answer_discipline
        or _selected_evidence_answer_discipline(
            query=query,
            answer=answer,
            selected_evidence=[dict(evidence) for evidence in query_selected],
            cited_evidence_ids=list(citation_ids),
        )
    )
    if _clean(discipline.get("status")) != "clean_supported":
        return None
    final_selected = _gate_select_evidence(
        query=query,
        answer=_gate_answer_surface(answer),
        contexts=candidate_selected,
        citations=[],
    )
    if not answer or not final_selected:
        return None
    initial_gate_validation = _selected_evidence_gate_validation_for_answer(
        row=row,
        query=query,
        answer=answer,
        selected_evidence=final_selected,
    )
    initial_gate_decision, initial_gate_reason = _evidence_gate_decision(
        initial_gate_validation,
        answer=_gate_answer_surface(answer),
    )
    gate_aligned_fallback_used = False
    gate_aligned_initial_validation = initial_gate_validation
    gate_aligned_fallback_validation: Mapping[str, Any] | None = None
    initial_answer = _clean(answer)
    final_discipline = discipline
    if allow_gate_aligned_fallback and initial_gate_decision != "allow_answer":
        fallback_answer = _selected_evidence_sentence(query, query_selected)
        fallback_selected = _gate_select_evidence(
            query=query,
            answer=_gate_answer_surface(fallback_answer),
            contexts=query_selected,
            citations=[],
        )
        if fallback_answer and fallback_selected:
            fallback_validation = _selected_evidence_gate_validation_for_answer(
                row=row,
                query=query,
                answer=fallback_answer,
                selected_evidence=fallback_selected,
            )
            fallback_decision, _fallback_reason = _evidence_gate_decision(
                fallback_validation,
                answer=_gate_answer_surface(fallback_answer),
            )
            fallback_discipline = _selected_evidence_answer_discipline(
                query=query,
                answer=fallback_answer,
                selected_evidence=fallback_selected,
                cited_evidence_ids=_selected_evidence_ids(fallback_selected),
            )
            if (
                fallback_decision == "allow_answer"
                and _clean(fallback_discipline.get("status")) == "clean_supported"
            ):
                answer = fallback_answer
                final_selected = fallback_selected
                final_discipline = fallback_discipline
                gate_aligned_fallback_used = True
                gate_aligned_fallback_validation = fallback_validation
    formatted_citations = format_selected_evidence_citations(
        final_selected,
        citation_format=normalized_citation_format,
    )
    output = dict(row)
    output["generated_answer"] = _clean(answer)
    output["citations"] = [_normalize_citation(context) for context in final_selected]
    composer = {
        "provider": SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROVIDER,
        "input_policy": SELECTED_EVIDENCE_COMPOSER_INPUT_POLICY,
        "citation_format": normalized_citation_format,
        "answer_rendering_policy": "local_llm_natural_query_context_sentence",
        "answer_audit_scaffold_in_generated_answer": False,
        "formatted_citations": formatted_citations,
        "retrieved_context_only_citations_diagnostic_only": True,
        "query_selected_evidence_count": len(query_selected),
        "query_selected_evidence_ids": _selected_evidence_ids(query_selected),
        "selected_evidence_count": len(final_selected),
        "selected_evidence_ids": _selected_evidence_ids(final_selected),
        "selected_source_atom_ids": [
            _clean(context.get("source_atom_id")) for context in final_selected if _clean(context.get("source_atom_id"))
        ],
        "selected_evidence_text_hashes": _text_hashes(final_selected),
        "abstained": False,
        "abstention_reason": "",
        "previous_answer_hash": _sha256_text(_clean(row.get("generated_answer"))),
        "uses_expected_answer": False,
        "uses_expected_evidence": False,
        "uses_gold_fields": False,
        "uses_qrels": False,
        "uses_labels": False,
        "uses_answerability": False,
        "uses_query_or_row_or_target_ids": False,
        "uses_baseline_topk_or_legacy_outputs": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "local_llm_fallback_used": gate_aligned_fallback_used,
        "local_llm_gate_aligned_fallback_used": gate_aligned_fallback_used,
        "answer_discipline": final_discipline,
        "local_llm": _local_llm_meta(
            config=config,
            status="gate_aligned_deterministic_fallback" if gate_aligned_fallback_used else "generated",
            prompt_sha256=prompt_sha256,
            raw_response_sha256=raw_response_sha256,
            answer_preview=initial_answer,
            fallback_provider=SELECTED_EVIDENCE_COMPOSER_PROVIDER if gate_aligned_fallback_used else "",
            fallback_reason="local_llm_clean_answer_gate_insufficient" if gate_aligned_fallback_used else "",
        ),
    }
    if gate_aligned_fallback_used:
        composer["answer_rendering_policy"] = "source_native_selected_evidence_sentence_gate_aligned"
        composer["initial_answer_discipline"] = discipline
        composer["initial_evidence_package_status"] = _clean(gate_aligned_initial_validation.get("evidence_package_status"))
        composer["initial_answer_gate_decision"] = initial_gate_decision
        composer["initial_abstention_reason"] = initial_gate_reason
        composer["initial_validation_reasons"] = [
            _clean(reason)
            for reason in _as_list(gate_aligned_initial_validation.get("validation_reasons"))
            if _clean(reason)
        ]
        composer["initial_missing_answer_anchors"] = [
            _clean(anchor)
            for anchor in _as_list(gate_aligned_initial_validation.get("missing_answer_anchors"))
            if _clean(anchor)
        ][:8]
        composer["initial_missing_query_anchors"] = [
            _clean(anchor)
            for anchor in _as_list(gate_aligned_initial_validation.get("missing_query_anchors"))
            if _clean(anchor)
        ][:8]
        if gate_aligned_fallback_validation is not None:
            composer["gate_aligned_evidence_package_status"] = _clean(
                gate_aligned_fallback_validation.get("evidence_package_status")
            )
    if retry_meta is not None:
        composer["retry"] = dict(retry_meta)
    output["answer_composer"] = composer
    return output


def _maybe_retry_selected_evidence_local_llm_output(
    output: dict[str, Any],
    *,
    original_row: Mapping[str, Any],
    query: str,
    query_selected: Sequence[Mapping[str, Any]],
    normalized_citation_format: str,
    config: Mapping[str, Any],
    retry_mode: str,
) -> dict[str, Any]:
    composer = dict(output.get("answer_composer") or {})
    if retry_mode != "bounded-once":
        return output
    validation = validate_evidence_package_for_gate(output)
    decision, reason = _evidence_gate_decision(validation, answer=_gate_answer_surface(_clean(output.get("generated_answer"))))
    trigger = _selected_evidence_retry_trigger(validation, decision)
    if not trigger:
        discipline = composer.get("answer_discipline") if isinstance(composer.get("answer_discipline"), Mapping) else {}
        reason = (
            "answer_discipline_clean_supported"
            if _clean(discipline.get("status")) == "clean_supported"
            else "evidence_gate_allows_answer"
        )
        composer["retry"] = _selected_evidence_retry_not_triggered_meta(reason)
        output["answer_composer"] = composer
        return output

    previous_answer_preview = _bounded_text_preview(_gate_answer_surface(_clean(output.get("generated_answer"))))
    missing_query_focus_anchors = [
        _clean(anchor) for anchor in _as_list(validation.get("missing_query_anchors")) if _clean(anchor)
    ]
    prompt = _selected_evidence_local_llm_retry_prompt(
        query=query,
        selected_evidence=query_selected,
        missing_query_focus_anchors=missing_query_focus_anchors,
        previous_answer_preview=previous_answer_preview,
        answer_discipline_status=_clean(
            (composer.get("answer_discipline") if isinstance(composer.get("answer_discipline"), Mapping) else {}).get("status")
        ),
        answer_discipline_issue_preview=_clean(
            (composer.get("answer_discipline") if isinstance(composer.get("answer_discipline"), Mapping) else {}).get("unsupported_extra_preview")
            or (composer.get("answer_discipline") if isinstance(composer.get("answer_discipline"), Mapping) else {}).get("query_irrelevant_preview")
        ),
    )
    prompt_sha256 = f"sha256:{_sha256_text(prompt)}"
    retry_base = {
        "enabled": True,
        "attempted": True,
        "attempt_count": 1,
        "max_retry_count": 1,
        "mode": "bounded-once",
        "input_policy": SELECTED_EVIDENCE_COMPOSER_RETRY_INPUT_POLICY,
        "trigger": trigger,
        "initial_evidence_package_status": _clean(validation.get("evidence_package_status")),
        "initial_answer_gate_decision": decision,
        "initial_abstention_reason": reason,
        "missing_query_focus_anchors": missing_query_focus_anchors,
        "previous_answer_preview": previous_answer_preview,
        "previous_answer_preview_sha256": f"sha256:{_sha256_text(previous_answer_preview)}",
        "retry_prompt_sha256": prompt_sha256,
    }
    try:
        parsed, meta = LOCAL_LLM_HELPER.call_local_llm_strict_json(
            backend=_clean(config.get("backend")),
            base_url=_clean(config.get("base_url")),
            model=_clean(config.get("model")),
            prompt=prompt,
            temperature=0.0,
            max_tokens=int(config.get("max_tokens") or 360),
            timeout_seconds=int(config.get("timeout_seconds") or 60),
        )
    except Exception as exc:
        composer["retry"] = {
            **retry_base,
            "status": "error",
            "error": f"LOCAL_LLM_RETRY_ERROR: {type(exc).__name__}: {exc}",
        }
        output["answer_composer"] = composer
        return output

    retry_answer = _clean(parsed.get("answer") or parsed.get("short_answer"))
    retry_citation_ids = _ids_from_local_llm_citation_field(
        parsed.get("citation_evidence_ids") or parsed.get("citations") or parsed.get("evidence_ids")
    )
    retry_raw_sha = _clean((meta or {}).get("raw_response_sha256"))
    retry_discipline = _selected_evidence_answer_discipline(
        query=query,
        answer=retry_answer,
        selected_evidence=[dict(evidence) for evidence in query_selected],
        cited_evidence_ids=retry_citation_ids,
    )
    retry_output = _selected_evidence_local_llm_output_from_answer(
        row=original_row,
        query=query,
        query_selected=query_selected,
        answer=retry_answer,
        citation_ids=retry_citation_ids,
        normalized_citation_format=normalized_citation_format,
        config=config,
        prompt_sha256=prompt_sha256,
        raw_response_sha256=retry_raw_sha,
        retry_meta={
            **retry_base,
            "status": "accepted",
            "retry_answer_discipline_status": _clean(retry_discipline.get("status")),
            "retry_raw_response_sha256": retry_raw_sha,
            "retry_answer_preview": _bounded_text_preview(retry_answer),
        },
        answer_discipline=retry_discipline,
    )
    if retry_output is None:
        composer["retry"] = {
            **retry_base,
            "status": "rejected_gate_insufficient",
            "retry_raw_response_sha256": retry_raw_sha,
            "retry_answer_preview": _bounded_text_preview(retry_answer),
        }
        output["answer_composer"] = composer
        return output
    retry_validation = validate_evidence_package_for_gate(retry_output)
    retry_decision, retry_reason = _evidence_gate_decision(
        retry_validation,
        answer=_gate_answer_surface(_clean(retry_output.get("generated_answer"))),
    )
    if retry_decision != "allow_answer":
        composer["retry"] = {
            **retry_base,
            "status": "rejected_gate_insufficient",
            "retry_raw_response_sha256": retry_raw_sha,
            "retry_answer_preview": _bounded_text_preview(retry_answer),
            "retry_evidence_package_status": _clean(retry_validation.get("evidence_package_status")),
            "retry_answer_gate_decision": retry_decision,
            "retry_abstention_reason": retry_reason,
        }
        output["answer_composer"] = composer
        return output
    retry_composer = dict(retry_output.get("answer_composer") or {})
    retry_meta = dict(retry_composer.get("retry") or {})
    retry_meta.update(
        {
            "retry_evidence_package_status": _clean(retry_validation.get("evidence_package_status")),
            "retry_answer_gate_decision": retry_decision,
            "retry_abstention_reason": retry_reason,
        }
    )
    retry_composer["retry"] = retry_meta
    retry_output["answer_composer"] = retry_composer
    return retry_output


def apply_selected_evidence_composer_to_outputs(
    raw_outputs: Sequence[Mapping[str, Any]],
    *,
    max_evidence: int = 3,
    citation_format: str = "compact",
    composer_provider: str = SELECTED_EVIDENCE_COMPOSER_PROVIDER,
    local_llm_backend: str = "",
    local_llm_base_url: str = "",
    local_llm_model: str = "",
    local_llm_timeout_seconds: int = 60,
    local_llm_max_tokens: int = 360,
    skip_local_llm_endpoint_check: bool = False,
    retry_mode: str = "off",
) -> list[dict[str, Any]]:
    normalized_provider = _clean(composer_provider).replace("_", "-").lower() or SELECTED_EVIDENCE_COMPOSER_PROVIDER
    if normalized_provider == SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROVIDER:
        return _apply_selected_evidence_local_llm_composer_to_outputs(
            raw_outputs,
            max_evidence=max_evidence,
            citation_format=citation_format,
            local_llm_backend=local_llm_backend,
            local_llm_base_url=local_llm_base_url,
            local_llm_model=local_llm_model,
            local_llm_timeout_seconds=local_llm_timeout_seconds,
            local_llm_max_tokens=local_llm_max_tokens,
            skip_local_llm_endpoint_check=skip_local_llm_endpoint_check,
            retry_mode=retry_mode,
        )
    if normalized_provider != SELECTED_EVIDENCE_COMPOSER_PROVIDER:
        raise DatasetSchemaError(f"unsupported selected evidence composer provider: {composer_provider}")
    normalized_citation_format = _normalize_selected_evidence_citation_format(citation_format)
    composed_rows: list[dict[str, Any]] = []
    for row in raw_outputs:
        output = dict(row)
        contexts = _contexts_from_row(output)
        query = _clean(output.get("query"))
        query_selected = select_composer_evidence(
            query,
            contexts,
            max_evidence=max_evidence,
            query_evidence_planner=(
                output.get("query_evidence_planner")
                if isinstance(output.get("query_evidence_planner"), Mapping)
                else None
            ),
        )
        abstention_reason = _selected_evidence_abstention_reason(query, query_selected)
        final_selected: list[dict[str, Any]] = []
        if not abstention_reason:
            draft_answer = _selected_evidence_answer(query=query, selected_evidence=query_selected)
            final_selected = _gate_select_evidence(
                query=query,
                answer=_gate_answer_surface(draft_answer),
                contexts=query_selected,
                citations=[],
            )
            if not final_selected:
                abstention_reason = "insufficient_selected_evidence"
        abstained = bool(abstention_reason)
        formatted_citations = [] if abstained else format_selected_evidence_citations(
            final_selected,
            citation_format=normalized_citation_format,
        )
        output["generated_answer"] = (
            BOUNDED_EVIDENCE_ABSTENTION_ANSWER
            if abstained
            else _selected_evidence_answer(
                query=query,
                selected_evidence=final_selected,
                citation_format=normalized_citation_format,
                formatted_citations=formatted_citations,
            )
        )
        output["citations"] = [] if abstained else [_normalize_citation(context) for context in final_selected]
        output["answer_composer"] = {
            "provider": SELECTED_EVIDENCE_COMPOSER_PROVIDER,
            "input_policy": SELECTED_EVIDENCE_COMPOSER_INPUT_POLICY,
            "citation_format": normalized_citation_format,
            "rendering_mode": "abstention" if abstained else "selected_evidence_markdown",
            "rendered_answer_source_fields": [],
            "formatted_citations": formatted_citations,
            "retrieved_context_only_citations_diagnostic_only": True,
            "query_selected_evidence_count": len(query_selected),
            "query_selected_evidence_ids": _selected_evidence_ids(query_selected),
            "selected_evidence_count": len(final_selected),
            "selected_evidence_ids": _selected_evidence_ids(final_selected),
            "selected_source_atom_ids": [
                _clean(context.get("source_atom_id")) for context in final_selected if _clean(context.get("source_atom_id"))
            ],
            "selected_evidence_text_hashes": _text_hashes(final_selected),
            "abstained": abstained,
            "abstention_reason": abstention_reason,
            "previous_answer_hash": _sha256_text(_clean(row.get("generated_answer"))),
            "uses_expected_answer": False,
            "uses_expected_evidence": False,
            "uses_gold_fields": False,
            "uses_qrels": False,
            "uses_labels": False,
            "uses_answerability": False,
            "uses_query_or_row_or_target_ids": False,
            "uses_baseline_topk_or_legacy_outputs": False,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
        }
        composed_rows.append(output)
    return composed_rows


def _apply_selected_evidence_local_llm_composer_to_outputs(
    raw_outputs: Sequence[Mapping[str, Any]],
    *,
    max_evidence: int = 3,
    citation_format: str = "compact",
    local_llm_backend: str = "",
    local_llm_base_url: str = "",
    local_llm_model: str = "",
    local_llm_timeout_seconds: int = 60,
    local_llm_max_tokens: int = 360,
    skip_local_llm_endpoint_check: bool = False,
    retry_mode: str = "off",
) -> list[dict[str, Any]]:
    normalized_citation_format = _normalize_selected_evidence_citation_format(citation_format)
    normalized_retry_mode = _normalize_selected_evidence_composer_retry_mode(retry_mode)
    config = _local_llm_composer_config(
        backend=local_llm_backend,
        base_url=local_llm_base_url,
        model=local_llm_model,
        timeout_seconds=local_llm_timeout_seconds,
        max_tokens=local_llm_max_tokens,
        check_endpoint=not skip_local_llm_endpoint_check,
    )
    composed_rows: list[dict[str, Any]] = []
    for row in raw_outputs:
        deterministic = apply_selected_evidence_composer_to_outputs(
            [row],
            max_evidence=max_evidence,
            citation_format=normalized_citation_format,
            composer_provider=SELECTED_EVIDENCE_COMPOSER_PROVIDER,
        )[0]
        deterministic_composer = dict(deterministic.get("answer_composer") or {})
        deterministic_composer["provider"] = SELECTED_EVIDENCE_LOCAL_LLM_COMPOSER_PROVIDER
        deterministic_composer["fallback_provider"] = SELECTED_EVIDENCE_COMPOSER_PROVIDER
        deterministic_composer["local_llm_fallback_used"] = True
        query = _clean(row.get("query"))
        contexts = _contexts_from_row(row)
        query_selected = select_composer_evidence(
            query,
            contexts,
            max_evidence=max_evidence,
            query_evidence_planner=(
                row.get("query_evidence_planner") if isinstance(row.get("query_evidence_planner"), Mapping) else None
            ),
        )

        if deterministic_composer.get("abstained"):
            if normalized_retry_mode == "bounded-once":
                deterministic_composer["retry"] = _selected_evidence_retry_not_triggered_meta(
                    "no_initial_selected_evidence_answer"
                )
            deterministic_composer["local_llm"] = _local_llm_meta(
                config=config,
                status="skipped_insufficient_selected_evidence",
                blockers=[_clean(deterministic_composer.get("abstention_reason")) or "insufficient_selected_evidence"],
                fallback_provider=SELECTED_EVIDENCE_COMPOSER_PROVIDER,
            )
            deterministic["answer_composer"] = deterministic_composer
            composed_rows.append(deterministic)
            continue

        if not config.get("available"):
            if normalized_retry_mode == "bounded-once":
                deterministic_composer["retry"] = _selected_evidence_retry_not_triggered_meta(
                    "local_llm_unavailable"
                )
            deterministic_composer["local_llm"] = _local_llm_meta(
                config=config,
                status="unavailable_deterministic_fallback",
                blockers=list(config.get("blockers") or []),
                fallback_provider=SELECTED_EVIDENCE_COMPOSER_PROVIDER,
            )
            deterministic["answer_composer"] = deterministic_composer
            composed_rows.append(deterministic)
            continue

        prompt = _selected_evidence_local_llm_prompt(query=query, selected_evidence=query_selected)
        prompt_sha256 = f"sha256:{_sha256_text(prompt)}"
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
            if normalized_retry_mode == "bounded-once":
                deterministic_composer["retry"] = _selected_evidence_retry_not_triggered_meta(
                    "initial_local_llm_error"
                )
            deterministic_composer["local_llm"] = _local_llm_meta(
                config=config,
                status="error_deterministic_fallback",
                prompt_sha256=prompt_sha256,
                blockers=[f"LOCAL_LLM_COMPOSER_ERROR: {type(exc).__name__}: {exc}"],
                fallback_provider=SELECTED_EVIDENCE_COMPOSER_PROVIDER,
            )
            deterministic["answer_composer"] = deterministic_composer
            composed_rows.append(deterministic)
            continue

        answer = _clean(parsed.get("answer") or parsed.get("short_answer"))
        citation_ids = _ids_from_local_llm_citation_field(
            parsed.get("citation_evidence_ids") or parsed.get("citations") or parsed.get("evidence_ids")
        )
        answer_discipline = _selected_evidence_answer_discipline(
            query=query,
            answer=answer,
            selected_evidence=[dict(evidence) for evidence in query_selected],
            cited_evidence_ids=citation_ids,
        )
        answer_discipline_status = _clean(answer_discipline.get("status"))
        answer_discipline_fallback_reason = _selected_evidence_answer_discipline_fallback_reason(answer_discipline)
        if answer_discipline_status != "clean_supported":
            retry_error = ""
            retry_rejected_meta: dict[str, Any] | None = None
            if normalized_retry_mode == "bounded-once":
                previous_answer_preview = _bounded_text_preview(_gate_answer_surface(answer))
                retry_prompt = _selected_evidence_local_llm_retry_prompt(
                    query=query,
                    selected_evidence=query_selected,
                    missing_query_focus_anchors=[],
                    previous_answer_preview=previous_answer_preview,
                    answer_discipline_status=answer_discipline_status,
                    answer_discipline_issue_preview=_clean(
                        answer_discipline.get("unsupported_extra_preview")
                        or answer_discipline.get("query_irrelevant_preview")
                    ),
                )
                retry_prompt_sha256 = f"sha256:{_sha256_text(retry_prompt)}"
                retry_base = {
                    "enabled": True,
                    "attempted": True,
                    "attempt_count": 1,
                    "max_retry_count": 1,
                    "mode": "bounded-once",
                    "input_policy": SELECTED_EVIDENCE_COMPOSER_RETRY_INPUT_POLICY,
                    "trigger": answer_discipline_fallback_reason,
                    "initial_answer_discipline_status": answer_discipline_status,
                    "initial_answer_preview": previous_answer_preview,
                    "initial_answer_preview_sha256": f"sha256:{_sha256_text(previous_answer_preview)}",
                    "initial_raw_response_sha256": _clean((meta or {}).get("raw_response_sha256")),
                    "retry_prompt_sha256": retry_prompt_sha256,
                }
                try:
                    retry_parsed, retry_meta_raw = LOCAL_LLM_HELPER.call_local_llm_strict_json(
                        backend=_clean(config.get("backend")),
                        base_url=_clean(config.get("base_url")),
                        model=_clean(config.get("model")),
                        prompt=retry_prompt,
                        temperature=0.0,
                        max_tokens=int(config.get("max_tokens") or local_llm_max_tokens),
                        timeout_seconds=int(config.get("timeout_seconds") or local_llm_timeout_seconds),
                    )
                    retry_answer = _clean(retry_parsed.get("answer") or retry_parsed.get("short_answer"))
                    retry_citation_ids = _ids_from_local_llm_citation_field(
                        retry_parsed.get("citation_evidence_ids")
                        or retry_parsed.get("citations")
                        or retry_parsed.get("evidence_ids")
                    )
                    retry_raw_sha = _clean((retry_meta_raw or {}).get("raw_response_sha256"))
                    retry_discipline = _selected_evidence_answer_discipline(
                        query=query,
                        answer=retry_answer,
                        selected_evidence=[dict(evidence) for evidence in query_selected],
                        cited_evidence_ids=retry_citation_ids,
                    )
                    retry_output = _selected_evidence_local_llm_output_from_answer(
                        row=row,
                        query=query,
                        query_selected=query_selected,
                        answer=retry_answer,
                        citation_ids=retry_citation_ids,
                        normalized_citation_format=normalized_citation_format,
                        config=config,
                        prompt_sha256=retry_prompt_sha256,
                        raw_response_sha256=retry_raw_sha,
                        retry_meta={
                            **retry_base,
                            "status": "accepted",
                            "retry_answer_discipline_status": _clean(retry_discipline.get("status")),
                            "retry_raw_response_sha256": retry_raw_sha,
                            "retry_answer_preview": _bounded_text_preview(retry_answer),
                        },
                        answer_discipline=retry_discipline,
                    )
                    if retry_output is not None:
                        retry_validation = validate_evidence_package_for_gate(retry_output)
                        retry_decision, retry_reason = _evidence_gate_decision(
                            retry_validation,
                            answer=_gate_answer_surface(_clean(retry_output.get("generated_answer"))),
                        )
                        if retry_decision == "allow_answer":
                            retry_composer = dict(retry_output.get("answer_composer") or {})
                            retry_meta = dict(retry_composer.get("retry") or {})
                            retry_meta.update(
                                {
                                    "retry_evidence_package_status": _clean(
                                        retry_validation.get("evidence_package_status")
                                    ),
                                    "retry_answer_gate_decision": retry_decision,
                                    "retry_abstention_reason": retry_reason,
                                }
                            )
                            retry_composer["retry"] = retry_meta
                            retry_composer["initial_answer_discipline"] = answer_discipline
                            retry_output["answer_composer"] = retry_composer
                            composed_rows.append(retry_output)
                            continue
                    retry_rejected_meta = {
                        **retry_base,
                        "status": "rejected_gate_insufficient",
                        "retry_answer_discipline_status": _clean(retry_discipline.get("status")),
                        "retry_raw_response_sha256": retry_raw_sha,
                        "retry_answer_preview": _bounded_text_preview(retry_answer),
                    }
                except Exception as exc:
                    retry_error = f"LOCAL_LLM_RETRY_ERROR: {type(exc).__name__}: {exc}"
                    retry_rejected_meta = {**retry_base, "status": "error", "error": retry_error}
            elif normalized_retry_mode == "bounded-once":
                retry_rejected_meta = _selected_evidence_retry_not_triggered_meta(answer_discipline_fallback_reason)

            deterministic_discipline = _selected_evidence_deterministic_fallback_answer_discipline(
                query=query,
                answer=_gate_answer_surface(_clean(deterministic.get("generated_answer"))),
                selected_evidence=[dict(evidence) for evidence in query_selected],
                cited_evidence_ids=_selected_evidence_ids(query_selected),
            )
            deterministic_composer["initial_answer_discipline"] = answer_discipline
            deterministic_composer["answer_discipline"] = deterministic_discipline
            if retry_rejected_meta is not None:
                deterministic_composer["retry"] = retry_rejected_meta
            deterministic_composer["local_llm"] = _local_llm_meta(
                config=config,
                status="answer_discipline_deterministic_fallback",
                prompt_sha256=prompt_sha256,
                raw_response_sha256=_clean((meta or {}).get("raw_response_sha256")),
                answer_preview=answer,
                blockers=[answer_discipline_fallback_reason, retry_error] if retry_error else [answer_discipline_fallback_reason],
                fallback_provider=SELECTED_EVIDENCE_COMPOSER_PROVIDER,
                fallback_reason=answer_discipline_fallback_reason,
            )
            deterministic["answer_composer"] = deterministic_composer
            composed_rows.append(deterministic)
            continue
        output = _selected_evidence_local_llm_output_from_answer(
            row=row,
            query=query,
            query_selected=query_selected,
            answer=answer,
            citation_ids=citation_ids,
            normalized_citation_format=normalized_citation_format,
            config=config,
            prompt_sha256=prompt_sha256,
            raw_response_sha256=_clean((meta or {}).get("raw_response_sha256")),
            answer_discipline=answer_discipline,
            allow_gate_aligned_fallback=normalized_retry_mode != "bounded-once",
        )
        if output is None:
            deterministic_discipline = _selected_evidence_deterministic_fallback_answer_discipline(
                query=query,
                answer=_gate_answer_surface(_clean(deterministic.get("generated_answer"))),
                selected_evidence=[dict(evidence) for evidence in query_selected],
                cited_evidence_ids=_selected_evidence_ids(query_selected),
            )
            if normalized_retry_mode == "bounded-once":
                deterministic_composer["retry"] = _selected_evidence_retry_not_triggered_meta(
                    "initial_local_llm_answer_unsupported_or_empty"
                )
            deterministic_composer["local_llm"] = _local_llm_meta(
                config=config,
                status="unsupported_or_empty_deterministic_fallback",
                prompt_sha256=prompt_sha256,
                raw_response_sha256=_clean((meta or {}).get("raw_response_sha256")),
                answer_preview=answer,
                fallback_provider=SELECTED_EVIDENCE_COMPOSER_PROVIDER,
                fallback_reason="initial_local_llm_answer_unsupported_or_empty",
            )
            deterministic_composer["initial_answer_discipline"] = answer_discipline
            deterministic_composer["answer_discipline"] = deterministic_discipline
            deterministic["answer_composer"] = deterministic_composer
            composed_rows.append(deterministic)
            continue
        output = _maybe_retry_selected_evidence_local_llm_output(
            output,
            original_row=row,
            query=query,
            query_selected=query_selected,
            normalized_citation_format=normalized_citation_format,
            config=config,
            retry_mode=normalized_retry_mode,
        )
        composed_rows.append(output)
    return composed_rows


def _gate_citation_validation(
    *,
    citation: Mapping[str, Any],
    citation_index: int,
    retrieved_contexts: Sequence[Mapping[str, Any]],
    selected_evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    retrieved_target = next((context for context in retrieved_contexts if _gate_rows_match(citation, context)), None)
    selected_target = next((context for context in selected_evidence if _gate_rows_match(citation, context)), None)
    target = selected_target or retrieved_target
    citation_text = _gate_row_text(citation)
    target_text = _gate_support_text(target or {}) if isinstance(target, Mapping) else ""
    target_exists = bool(target)
    in_retrieved = bool(retrieved_target)
    in_selected = bool(selected_target)
    text_supported = False
    if citation_text and target_text:
        text_supported = bool(
            normalize_answer_text(citation_text) in normalize_answer_text(target_text)
            or _token_overlap_ratio(citation_text, target_text) >= 0.55
            or _anchor_requirements_satisfied(_candidate_anchors(citation_text), target_text)
        )
    elif target_exists and not citation_text:
        text_supported = True

    if not citation_text and not any(_clean(citation.get(key)) for key in ("doc_id", "chunk_id", "source_atom_id", "evidence_bundle_id")):
        status = "not_comparable"
        reason = "citation_missing_target_and_text"
    elif in_selected and text_supported:
        status = "supported"
        reason = ""
    elif in_selected and not text_supported:
        status = "unsupported_text"
        reason = "citation_text_not_supported_by_selected_evidence"
    elif in_retrieved and not in_selected:
        status = "retrieved_context_only_diagnostic"
        reason = "citation_target_not_in_selected_evidence"
    elif target_exists:
        status = "wrong_target"
        reason = "citation_target_not_selected"
    else:
        status = "missing_target"
        reason = "citation_target_not_found"

    return {
        "citation_index": citation_index,
        "cited_doc_id": _clean(citation.get("doc_id") or citation.get("docId") or citation.get("document_id")),
        "cited_chunk_id": _clean(citation.get("chunk_id") or citation.get("chunkId")),
        "cited_source_atom_id": _clean(citation.get("source_atom_id")),
        "cited_evidence_bundle_id": _clean(citation.get("evidence_bundle_id")),
        "cited_text_hash": _gate_row_hash(citation),
        "citation_target_exists": target_exists,
        "citation_target_in_retrieved_contexts": in_retrieved,
        "citation_target_in_selected_evidence": in_selected,
        "citation_text_supported_by_target": text_supported,
        "citation_support_status": status,
        "citation_rejection_reason": reason,
    }


def validate_evidence_package_for_gate(row: Mapping[str, Any]) -> dict[str, Any]:
    query = _clean(row.get("query"))
    answer = _gate_answer_surface(_clean(row.get("generated_answer")))
    contexts = _contexts_from_row(row)
    citations = _citations_from_row(row)
    selected = _gate_select_evidence(query=query, answer=answer, contexts=contexts, citations=citations)
    planner = _query_evidence_planner_for_row(row)
    source_family_hint = _query_evidence_source_family_hint(planner)
    if not selected and planner:
        selected = _gate_select_axis_complete_evidence(
            query=query,
            answer=answer,
            contexts=contexts,
            planner=planner,
            source_family_hint=source_family_hint,
        )
    source_family_matched_selected = [
        context
        for context in selected
        if _query_evidence_source_family_matches_context(source_family_hint, context)
    ]
    source_family_hint_blocks_gate = bool(source_family_hint and selected and not source_family_matched_selected)
    selected_for_gate = source_family_matched_selected if source_family_hint else selected
    selected_texts = [_gate_support_text(context) for context in selected_for_gate if _gate_support_text(context)]
    anchors = _gate_answer_anchors(query, answer)
    answer_anchors = set(anchors["answer"])
    numeric_anchors = set(anchors["numeric_or_date"])
    entity_anchors = set(anchors["entity"])
    query_focus_anchors = _query_focus_anchors_for_row(row)
    query_focus_texts = [answer, *selected_texts]
    answer_hits = _gate_anchor_hits(answer_anchors, selected_texts)
    numeric_hits = _gate_anchor_hits(numeric_anchors, selected_texts)
    entity_hits = _gate_anchor_hits(entity_anchors, selected_texts)
    query_focus_hits = _gate_anchor_hits(query_focus_anchors, query_focus_texts)
    selected_source_families = {
        _clean(context.get("source_family")).upper()
        for context in selected_for_gate
        if _clean(context.get("source_family"))
    }
    ignore_unknown_text_planner_axes = bool(
        planner
        and not source_family_hint
        and selected_source_families
        and selected_source_families <= {"TEXT"}
    )
    if ignore_unknown_text_planner_axes:
        matched_validated_required_axes: list[str] = []
        missing_validated_required_axes: list[str] = []
    else:
        matched_validated_required_axes, missing_validated_required_axes = _query_evidence_gate_validated_required_axis_hits(
            row=row,
            selected_evidence=selected_for_gate,
            answer=answer,
        )
        query_focus_hits |= _query_focus_hits_from_validated_planner_axes(
            query_focus_anchors=query_focus_anchors,
            planner=planner,
            matched_axes=matched_validated_required_axes,
        )
    validated_required_axes = matched_validated_required_axes + missing_validated_required_axes
    validated_required_axes_available = bool(validated_required_axes)
    validated_required_axes_coverage = _gate_coverage(
        validated_required_axes,
        matched_validated_required_axes,
    )
    missing_answer_anchors = sorted(answer_anchors - answer_hits)
    missing_numeric = sorted(numeric_anchors - numeric_hits)
    missing_entity = sorted(entity_anchors - entity_hits)
    missing_query_focus = sorted(query_focus_anchors - query_focus_hits)
    query_anchor_coverage = _gate_coverage(query_focus_anchors, query_focus_hits)
    missing_required_query_focus = bool(
        query_focus_anchors
        and (
            not query_focus_hits
            or (
                len(query_focus_anchors) > 1
                and query_anchor_coverage < EVIDENCE_GATE_MIN_QUERY_ANCHOR_COVERAGE
            )
        )
    )
    query_focus_blocks_gate = bool(missing_required_query_focus and not validated_required_axes_available)
    validated_axes_block_gate = bool(validated_required_axes_available and missing_validated_required_axes)
    unsupported_answer_anchors = sorted(
        set(missing_numeric)
        | set(missing_entity)
        | (set(missing_query_focus) if query_focus_blocks_gate else set())
    )
    citation_validations = [
        _gate_citation_validation(
            citation=citation,
            citation_index=index,
            retrieved_contexts=contexts,
            selected_evidence=selected_for_gate,
        )
        for index, citation in enumerate(citations, start=1)
    ]
    supported_citations = [row for row in citation_validations if row["citation_support_status"] == "supported"]
    retrieved_context_only_citations = [
        row for row in citation_validations if row["citation_support_status"] == "retrieved_context_only_diagnostic"
    ]
    validation_reasons: list[str] = []
    conflicting_reasons: list[str] = []
    if not answer:
        validation_reasons.append("missing_generated_answer")
    if not contexts:
        validation_reasons.append("no_retrieved_evidence_candidates")
    if not selected_for_gate:
        validation_reasons.append("no_selected_evidence")
    if missing_numeric:
        validation_reasons.append("missing_numeric_or_date_anchor")
    if missing_entity:
        validation_reasons.append("missing_entity_anchor")
    if query_focus_blocks_gate:
        validation_reasons.append("missing_query_anchor")
    if validated_axes_block_gate:
        validation_reasons.append("missing_validated_required_axes")
    if source_family_hint_blocks_gate:
        validation_reasons.append("source_family_hint_mismatch")
    if citations and not supported_citations:
        validation_reasons.append("citation_unsupported")
    selected_norm = " ".join(normalize_answer_text(text) for text in selected_texts)
    for anchor in numeric_anchors:
        if anchor and anchor not in selected_norm and re.search(r"\d", selected_norm):
            conflicting_reasons.append(f"numeric_or_date_anchor_conflict:{anchor}")
    if conflicting_reasons:
        validation_reasons.append("conflicting_evidence")

    citation_below_threshold = bool(citations and not supported_citations)
    if not contexts:
        status = "insufficient"
    elif conflicting_reasons:
        status = "conflicting"
    elif (
        not selected_for_gate
        or missing_numeric
        or missing_entity
        or query_focus_blocks_gate
        or validated_axes_block_gate
        or source_family_hint_blocks_gate
        or citation_below_threshold
    ):
        status = "insufficient"
    elif not answer_anchors and answer and selected_for_gate:
        status = "sufficient"
    elif _gate_coverage(answer_anchors, answer_hits) >= 0.65:
        status = "sufficient"
    else:
        status = "insufficient"
        if "missing_answer_anchors" not in validation_reasons:
            validation_reasons.append("missing_answer_anchors")

    return {
        "evidence_package_status": status,
        "evidence_support_score": _gate_coverage(answer_anchors, answer_hits),
        "answer_anchor_coverage": _gate_coverage(answer_anchors, answer_hits),
        "query_anchor_coverage": query_anchor_coverage,
        "validated_required_axes_coverage": validated_required_axes_coverage,
        "numeric_or_date_anchor_coverage": _gate_coverage(numeric_anchors, numeric_hits),
        "entity_anchor_coverage": _gate_coverage(entity_anchors, entity_hits),
        "source_family_hint": source_family_hint,
        "source_family_hint_matched_evidence_count": len(source_family_matched_selected),
        "source_family_hint_rejected_evidence_count": max(0, len(selected) - len(source_family_matched_selected)) if source_family_hint else 0,
        "selected_evidence_count": len(selected_for_gate),
        "rejected_evidence_count": max(0, len(contexts) - len(selected_for_gate)),
        "missing_answer_anchors": missing_answer_anchors,
        "missing_query_anchors": missing_query_focus,
        "validated_required_axes": validated_required_axes,
        "matched_validated_required_axes": matched_validated_required_axes,
        "missing_validated_required_axes": missing_validated_required_axes,
        "unsupported_answer_anchors": unsupported_answer_anchors,
        "conflicting_evidence_reasons": conflicting_reasons,
        "validation_reasons": sorted(set(validation_reasons)),
        "validated_required_axes_ignored_reason": (
            "unknown_source_family_text_evidence" if ignore_unknown_text_planner_axes else ""
        ),
        "validator_version": EVIDENCE_GATE_VALIDATOR_VERSION,
        "retrieved_evidence_candidates": [_runtime_safe_evidence_context(context) for context in contexts],
        "selected_evidence": selected_for_gate,
        "citation_targets": [_runtime_safe_evidence_context(citation) for citation in citations],
        "evidence_text_hashes": _text_hashes([*contexts, *citations]),
        "citation_validations": citation_validations,
        "citation_supported_count": len(supported_citations),
        "citation_selected_evidence_supported_count": len(supported_citations),
        "citation_supported_definition": "citation_target_selected_and_text_supported_by_selected_evidence",
        "citation_retrieved_context_only_diagnostic_count": len(retrieved_context_only_citations),
        "citation_wrong_target_count": sum(1 for row in citation_validations if row["citation_support_status"] == "wrong_target"),
        "citation_missing_target_count": sum(1 for row in citation_validations if row["citation_support_status"] == "missing_target"),
        "citation_unsupported_text_count": sum(1 for row in citation_validations if row["citation_support_status"] == "unsupported_text"),
        "validator_uses_expected_fields": False,
        "validator_uses_gold_fields": False,
        "validator_uses_legacy_fields": False,
    }


def _evidence_gate_decision(validation: Mapping[str, Any], *, answer: str) -> tuple[str, str]:
    status = _clean(validation.get("evidence_package_status"))
    reasons = set(_as_list(validation.get("validation_reasons")))
    if not answer:
        return "not_comparable", "missing_generated_answer"
    if status == "sufficient":
        return "allow_answer", ""
    if status == "conflicting":
        return "block_unsupported_answer", "conflicting_evidence"
    if "missing_numeric_or_date_anchor" in reasons:
        return "block_unsupported_answer", "missing_numeric_or_date_anchor"
    if "missing_entity_anchor" in reasons:
        return "block_unsupported_answer", "missing_entity_anchor"
    if "missing_query_anchor" in reasons:
        return "block_unsupported_answer", "insufficient_evidence"
    if "citation_unsupported" in reasons:
        return "block_unsupported_answer", "citation_unsupported"
    if status == "unresolved":
        return "block_unsupported_answer", "unresolved_evidence_package"
    return "block_unsupported_answer", "insufficient_evidence"


def _apply_post_gate_xlsx_answer_shape(
    *,
    output: dict[str, Any],
    validation: Mapping[str, Any],
    decision: str,
    gate_modified_answer: bool,
) -> dict[str, Any]:
    if decision != "allow_answer" or gate_modified_answer:
        return {}
    if _clean(validation.get("evidence_package_status")) != "sufficient":
        return {}
    planner = output.get("query_evidence_planner") if isinstance(output.get("query_evidence_planner"), Mapping) else None
    selected = [
        evidence
        for evidence in _as_list(validation.get("selected_evidence"))
        if isinstance(evidence, Mapping)
    ]
    candidate = _source_owned_xlsx_display_answer_candidate(
        query=_clean(output.get("query")),
        selected_evidence=selected,
        query_evidence_planner=planner,
    )
    skip_reason = _clean(candidate.get("skip_reason"))
    if skip_reason:
        return {
            "applied": False,
            "skip_reason": skip_reason,
            "candidate_count": int(candidate.get("candidate_count") or 0),
        }
    rendered_answer = _clean(candidate.get("answer"))
    if not rendered_answer:
        return {}
    previous_answer = _clean(output.get("generated_answer"))
    if rendered_answer == previous_answer:
        return {}
    output["generated_answer"] = rendered_answer
    composer = dict(output.get("answer_composer") or {})
    composer.update(
        {
            "rendering_mode": "source_owned_xlsx_display_value",
            "rendered_answer_source_fields": list(candidate.get("source_fields") or []),
            "post_gate_answer_shape_applied": True,
        }
    )
    output["answer_composer"] = composer
    return {
        "applied": True,
        "mode": "source_owned_xlsx_display_value",
        "input_policy": "post_gate_query_text_and_gate_selected_source_owned_xlsx_evidence_only",
        "source_fields": list(candidate.get("source_fields") or []),
        "matched_validated_required_axes": list(candidate.get("matched_validated_required_axes") or []),
        "pre_render_answer_hash": _sha256_text(previous_answer),
        "rendered_answer_hash": _sha256_text(rendered_answer),
        "uses_expected_answer": False,
        "uses_expected_evidence": False,
        "uses_gold_fields": False,
        "uses_qrels": False,
        "uses_labels": False,
        "uses_answerability": False,
        "uses_query_or_row_or_target_ids": False,
        "uses_baseline_topk_or_legacy_outputs": False,
    }


def _apply_evidence_gate_to_row(row: Mapping[str, Any], *, mode: str) -> dict[str, Any]:
    normalized_mode = _clean(mode).lower() or "off"
    output = dict(row)
    original_answer = _clean(output.get("generated_answer"))
    output[INTERNAL_PRE_GATE_ANSWER_KEY] = original_answer
    validation = validate_evidence_package_for_gate(output)
    decision, reason = _evidence_gate_decision(validation, answer=original_answer)
    modified = False
    if normalized_mode == "off":
        decision = "allow_answer" if original_answer else "not_comparable"
        reason = ""
    blocked_decision = decision == "block_unsupported_answer"
    would_block_unsupported = normalized_mode == "diagnostic" and blocked_decision
    unsupported_blocked = normalized_mode == "enforce" and blocked_decision
    if normalized_mode == "enforce" and blocked_decision and not abstains(original_answer):
        output["generated_answer"] = BOUNDED_EVIDENCE_ABSTENTION_ANSWER
        modified = True
    gated_answer = _clean(output.get("generated_answer"))
    failure_labels = set(output.get("failure_labels") or [])
    status = _clean(validation.get("evidence_package_status"))
    if normalized_mode == "off":
        failure_labels.add("gate_policy_not_applicable")
    elif status == "sufficient" and decision == "allow_answer":
        failure_labels.add("supported_answer_allowed")
    elif status == "sufficient" and modified:
        failure_labels.add("sufficient_evidence_over_abstain")
    elif status == "conflicting":
        failure_labels.add("evidence_package_conflicting")
    elif status == "unresolved":
        failure_labels.add("evidence_package_unresolved")
    elif status == "insufficient":
        failure_labels.add("evidence_package_insufficient")
    if blocked_decision and normalized_mode != "off":
        failure_labels.add("answer_unsupported_by_evidence")
    if modified:
        failure_labels.add("abstained_due_to_insufficient_evidence")
    if any(row.get("citation_support_status") == "retrieved_context_only_diagnostic" for row in validation["citation_validations"]):
        failure_labels.add("citation_retrieved_context_only_diagnostic")
    if any(row.get("citation_support_status") in {"wrong_target", "missing_target", "unsupported_text"} for row in validation["citation_validations"]):
        failure_labels.add("citation_unsupported_by_evidence")
    gate = {
        **validation,
        "evidence_gate_mode": normalized_mode,
        "answer_gate_decision": decision,
        "answer_modified_by_gate": modified,
        "original_generated_answer_hash": _sha256_text(original_answer),
        "gated_answer_hash": _sha256_text(gated_answer),
        "abstention_reason": reason,
        "would_block_unsupported_answer": would_block_unsupported,
        "unsupported_answer_blocked": unsupported_blocked,
        "retrieval_loop_triggered": False,
        "gate_uses_expected_fields": False,
        "gate_uses_gold_fields": False,
        "gate_uses_legacy_fields": False,
    }
    answer_shape_rendering = _apply_post_gate_xlsx_answer_shape(
        output=output,
        validation=validation,
        decision=decision,
        gate_modified_answer=modified,
    )
    if answer_shape_rendering.get("applied") is True:
        failure_labels.add("post_gate_answer_shape_rendered")
    output.update(
        {
            "evidence_gate_mode": normalized_mode,
            "answer_gate_decision": decision,
            "answer_modified_by_gate": modified,
            "original_generated_answer_hash": gate["original_generated_answer_hash"],
            "gated_answer_hash": gate["gated_answer_hash"],
            "abstention_reason": reason,
            "would_block_unsupported_answer": would_block_unsupported,
            "unsupported_answer_blocked": unsupported_blocked,
            "retrieval_loop_triggered": False,
            "gate_uses_expected_fields": False,
            "gate_uses_gold_fields": False,
            "gate_uses_legacy_fields": False,
            "evidence_gate": gate,
            "answer_shape_rendering": answer_shape_rendering or {"applied": False},
            "failure_labels": sorted(failure_labels),
        }
    )
    return output


def build_evidence_gate_summary(rows: Sequence[Mapping[str, Any]], *, mode: str) -> dict[str, Any]:
    normalized_mode = _clean(mode).lower() or "off"
    item_count = len(rows)
    gates = [row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {} for row in rows]
    unsupported_before = sum(1 for gate in gates if gate.get("answer_gate_decision") in {"block_unsupported_answer", "abstain"})
    unsupported_after = sum(
        1
        for row, gate in zip(rows, gates)
        if gate.get("answer_gate_decision") in {"block_unsupported_answer", "abstain"}
        and not (normalized_mode == "enforce" and abstains(_clean(row.get("generated_answer"))))
    )
    status_counts = Counter(_clean(gate.get("evidence_package_status")) for gate in gates)
    allowed = sum(1 for gate in gates if gate.get("answer_gate_decision") == "allow_answer")
    abstained = sum(1 for row in rows if row.get("answer_modified_by_gate") and abstains(_clean(row.get("generated_answer"))))
    actual_blocked_count = sum(1 for gate in gates if gate.get("unsupported_answer_blocked"))
    would_block_count = sum(1 for gate in gates if gate.get("would_block_unsupported_answer"))
    sufficient_allowed = sum(
        1
        for gate in gates
        if gate.get("evidence_package_status") == "sufficient" and gate.get("answer_gate_decision") == "allow_answer"
    )
    over_abstain = sum(
        1
        for row, gate in zip(rows, gates)
        if gate.get("evidence_package_status") == "sufficient" and row.get("answer_modified_by_gate")
    )
    return {
        "evidence_gate_mode": normalized_mode,
        "validator_version": EVIDENCE_GATE_VALIDATOR_VERSION,
        "item_count": item_count,
        "sufficient_evidence_package_count": status_counts.get("sufficient", 0),
        "insufficient_evidence_package_count": status_counts.get("insufficient", 0),
        "conflicting_evidence_package_count": status_counts.get("conflicting", 0),
        "unresolved_evidence_package_count": status_counts.get("unresolved", 0),
        "allowed_answer_count": allowed,
        "abstained_count": abstained,
        "unsupported_answer_blocked_count": actual_blocked_count,
        "would_abstain_count": would_block_count if normalized_mode == "diagnostic" else 0,
        "would_block_unsupported_answer_count": would_block_count if normalized_mode == "diagnostic" else 0,
        "citation_supported_count": sum(int(gate.get("citation_supported_count") or 0) for gate in gates),
        "citation_selected_evidence_supported_count": sum(
            int(gate.get("citation_selected_evidence_supported_count") or gate.get("citation_supported_count") or 0)
            for gate in gates
        ),
        "citation_supported_definition": "citation_target_selected_and_text_supported_by_selected_evidence",
        "citation_retrieved_context_only_diagnostic_count": sum(
            int(gate.get("citation_retrieved_context_only_diagnostic_count") or 0) for gate in gates
        ),
        "citation_wrong_target_count": sum(int(gate.get("citation_wrong_target_count") or 0) for gate in gates),
        "citation_missing_target_count": sum(int(gate.get("citation_missing_target_count") or 0) for gate in gates),
        "citation_unsupported_text_count": sum(int(gate.get("citation_unsupported_text_count") or 0) for gate in gates),
        "unsupported_answer_rate_before_gate": None if item_count == 0 else round(unsupported_before / item_count, 6),
        "unsupported_answer_rate_after_gate": None if item_count == 0 else round(unsupported_after / item_count, 6),
        "insufficient_evidence_abstained_count": sum(
            1
            for row, gate in zip(rows, gates)
            if gate.get("evidence_package_status") == "insufficient" and row.get("answer_modified_by_gate")
        ),
        "sufficient_evidence_allowed_count": sufficient_allowed,
        "sufficient_evidence_over_abstain_count": over_abstain,
        "gate_policy_not_applicable_count": sum(
            1
            for row in rows
            if normalized_mode == "off" or "gate_policy_not_applicable" in set(row.get("failure_labels") or [])
        ),
        "guardrail_status": {
            "gate_uses_expected_fields": False,
            "gate_uses_gold_fields": False,
            "gate_uses_legacy_fields": False,
            "retrieval_loop_triggered": False,
        },
    }


def _source_value_present(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    return bool(_clean(value))


def _collect_forbidden_shortcut_fields(value: Any) -> set[str]:
    seen: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = _clean(key)
            if key_text in XLSX_PDF_RESIDUAL_FORBIDDEN_SHORTCUT_FIELDS:
                seen.add(key_text)
            if isinstance(nested, (Mapping, list, tuple)):
                seen.update(_collect_forbidden_shortcut_fields(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            if isinstance(nested, (Mapping, list, tuple)):
                seen.update(_collect_forbidden_shortcut_fields(nested))
    return seen


def _residual_contexts(row: Mapping[str, Any], gate: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    values = gate.get(key)
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        return [value for value in values if isinstance(value, Mapping)]
    values = row.get(key)
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        return [value for value in values if isinstance(value, Mapping)]
    return []


def _row_contexts(row: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    values = row.get(key)
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        return [value for value in values if isinstance(value, Mapping)]
    return []


def _xlsx_pdf_source_family(
    *,
    contexts: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
) -> str:
    for source in (*selected, *contexts):
        family = _clean(source.get("source_family")).upper()
        if family in {"XLSX", "PDF"}:
            return family
    return ""


def _residual_axis_fields_for_family(source_family: str) -> tuple[str, ...]:
    if source_family == "XLSX":
        return XLSX_RESIDUAL_AXIS_FIELDS
    if source_family == "PDF":
        return PDF_RESIDUAL_AXIS_FIELDS
    return ()


def _residual_axis_presence(
    source_family: str,
    sources: Sequence[Mapping[str, Any]],
) -> tuple[list[str], list[str]]:
    fields = _residual_axis_fields_for_family(source_family)
    present = [
        field
        for field in fields
        if any(_source_value_present(source.get(field)) for source in sources)
    ]
    missing = [field for field in fields if field not in present]
    return present, missing


def _residual_selected_value_present(
    selected: Sequence[Mapping[str, Any]],
    validation_reasons: set[str],
) -> bool:
    if not selected:
        return False
    return "missing_numeric_or_date_anchor" not in validation_reasons


def _residual_sources_value_present(
    query: str,
    sources: Sequence[Mapping[str, Any]],
    validation_reasons: set[str],
) -> bool:
    if not sources:
        return False
    if query and _query_requires_numeric_or_date_answer(query):
        return any(
            _text_has_answer_value_anchor_beyond_query(query, _gate_row_text(source))
            for source in sources
        )
    if "missing_numeric_or_date_anchor" in validation_reasons:
        return False
    if any(_text_has_numeric_or_date_value(_gate_row_text(source)) for source in sources):
        return True
    return "missing_numeric_or_date_anchor" not in validation_reasons


def _classify_xlsx_pdf_residual_row(row: Mapping[str, Any]) -> dict[str, Any]:
    gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
    contexts = _residual_contexts(row, gate, "retrieved_evidence_candidates")
    selected = _residual_contexts(row, gate, "selected_evidence")
    raw_contexts = [
        *_row_contexts(row, "retrieved_contexts"),
        *_row_contexts(row, "citations"),
    ]
    query = _clean(row.get("query"))
    source_family = _xlsx_pdf_source_family(contexts=contexts, selected=selected)
    forbidden_seen = sorted(
        {
            *_collect_forbidden_shortcut_fields(row),
            *_collect_forbidden_shortcut_fields(raw_contexts),
        }
    )
    status = _clean(gate.get("evidence_package_status"))
    decision = _clean(gate.get("answer_gate_decision"))
    validation_reasons = set(_as_list(gate.get("validation_reasons")))
    if source_family not in {"XLSX", "PDF"}:
        return {
            "item_id": _clean(row.get("id")),
            "source_family": source_family or "OTHER",
            "classification": "not_xlsx_pdf",
            "source_axis_fields_present": [],
            "source_axis_fields_missing": [],
            "forbidden_shortcut_fields_ignored": forbidden_seen,
            "forbidden_shortcut_fields_used": [],
        }
    axis_sources = [*selected, *contexts]
    axis_present, axis_missing = _residual_axis_presence(source_family, axis_sources)
    selected_value_present = _residual_selected_value_present(selected, validation_reasons)
    candidate_value_present = _residual_sources_value_present(query, contexts, validation_reasons)

    if status == "sufficient" and decision == "allow_answer" and not validation_reasons:
        classification = "no_residual"
    elif not contexts:
        classification = "candidate_absent"
    elif candidate_value_present and axis_missing:
        classification = "selected_evidence_has_value_missing_axis"
    elif not selected:
        classification = (
            "candidate_present_anchor_missing"
            if validation_reasons & {"missing_query_anchor", "missing_entity_anchor", "missing_numeric_or_date_anchor"}
            else "selected_evidence_absent"
        )
    elif selected_value_present and axis_missing:
        classification = "selected_evidence_has_value_missing_axis"
    elif axis_present and not selected_value_present:
        classification = "selected_evidence_has_axis_missing_value"
    elif contexts and axis_present and not _residual_axis_presence(source_family, selected)[0]:
        classification = "gate_support_text_drops_source_metadata"
    elif status == "sufficient" and decision != "allow_answer":
        classification = "answer_generation_only_failure"
    elif validation_reasons and validation_reasons <= {"citation_unsupported"}:
        classification = "citation_only_failure"
    else:
        classification = "candidate_present_anchor_missing"

    return {
        "item_id": _clean(row.get("id")),
        "source_family": source_family,
        "classification": classification,
        "evidence_package_status": status,
        "answer_gate_decision": decision,
        "validation_reasons": sorted(validation_reasons),
        "retrieved_context_count": len(contexts),
        "selected_evidence_count": len(selected),
        "source_axis_fields_present": axis_present,
        "source_axis_fields_missing": axis_missing,
        "selected_evidence_value_anchor_present": selected_value_present,
        "forbidden_shortcut_fields_ignored": forbidden_seen,
        "forbidden_shortcut_fields_used": [],
    }


def build_xlsx_pdf_residual_breakdown(
    *,
    items: Sequence[EvalItem],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    classified_rows = [_classify_xlsx_pdf_residual_row(row) for row in rows]
    item_forbidden_by_id = {
        _clean(item.id): _collect_forbidden_shortcut_fields(item.source_row)
        for item in items
        if isinstance(item.source_row, Mapping)
    }
    for row in classified_rows:
        item_id = _clean(row.get("item_id"))
        ignored = sorted(
            {
                *(_clean(field) for field in row.get("forbidden_shortcut_fields_ignored") or []),
                *item_forbidden_by_id.get(item_id, set()),
            }
        )
        row["forbidden_shortcut_fields_ignored"] = ignored
    residual_rows = [
        row
        for row in classified_rows
        if row["classification"] not in XLSX_PDF_RESIDUAL_EXCLUDED_CLASSIFICATIONS
    ]
    classification_counts = Counter(
        row["classification"] for row in residual_rows
    )
    excluded_classification_counts = Counter(
        row["classification"]
        for row in classified_rows
        if row["classification"] in XLSX_PDF_RESIDUAL_EXCLUDED_CLASSIFICATIONS
    )
    forbidden_seen: set[str] = set()
    for row in classified_rows:
        forbidden_seen.update(row.get("forbidden_shortcut_fields_ignored") or [])
    return {
        "schema_version": XLSX_PDF_RESIDUAL_BREAKDOWN_SCHEMA_VERSION,
        "enabled": True,
        "report_only_diagnostic": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "uses_expected_fields": False,
        "uses_gold_fields": False,
        "uses_qrels": False,
        "uses_labels": False,
        "uses_ids": False,
        "uses_formula": False,
        "uses_normalized_value": False,
        "uses_baseline_topk_or_legacy_outputs": False,
        "uses_raw_xlsx_or_pdf_query_time_parsing": False,
        "allowed_classifications": list(XLSX_PDF_RESIDUAL_CLASSIFICATIONS),
        "excluded_classifications": list(XLSX_PDF_RESIDUAL_EXCLUDED_CLASSIFICATIONS),
        "classification_counts": dict(classification_counts),
        "excluded_classification_counts": dict(excluded_classification_counts),
        "source_row_count": len(rows),
        "residual_row_count": len(residual_rows),
        "forbidden_shortcut_fields_seen": sorted(forbidden_seen),
        "forbidden_shortcut_fields_used": [],
        "rows": residual_rows,
    }


PDF_DECOMPOSITION_PAGE_FIELDS = ("page_number", "page", "pageNumber", "physical_page_index")
PDF_DECOMPOSITION_BBOX_FIELDS = ("bbox", "bounding_box", "boundingBox")
PDF_DECOMPOSITION_SECTION_OR_TABLE_FIELDS = (
    "section_title",
    "sectionTitle",
    "table_caption",
    "tableCaption",
    "table_id",
    "tableId",
    "region_type",
    "regionType",
)
PDF_DECOMPOSITION_OCR_CONFIDENCE_FIELDS = (
    "ocr_confidence",
    "ocrConfidence",
    "ocr_confidence_avg",
    "ocrConfidenceAvg",
    "ocr_confidence_mean",
    "ocrConfidenceMean",
)
PDF_DECOMPOSITION_OCR_LOWER_TRUST_THRESHOLD = 0.8


def _pdf_decomposition_candidate_sources(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
    return [
        *_residual_contexts(row, gate, "retrieved_evidence_candidates"),
        *_residual_contexts(row, gate, "selected_evidence"),
        *_row_contexts(row, "retrieved_contexts"),
        *_row_contexts(row, "citations"),
    ]


def _pdf_decomposition_nested_sources(source: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    nested: list[Mapping[str, Any]] = [source]
    for key in ("metadata", "raw_locator", "citation_locator", "locator", "track_locator"):
        value = source.get(key)
        if isinstance(value, Mapping):
            nested.append(value)
    return nested


def _pdf_decomposition_has_any(source: Mapping[str, Any], fields: Sequence[str]) -> bool:
    return any(
        _source_value_present(candidate.get(field))
        for candidate in _pdf_decomposition_nested_sources(source)
        for field in fields
    )


def _pdf_decomposition_normalize_ocr_confidence(raw_value: Any) -> float | None:
    if isinstance(raw_value, (int, float)):
        value = float(raw_value)
    else:
        text = _clean(raw_value).rstrip("%")
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            return None
    if 1.0 < value <= 100.0:
        return value / 100.0
    return value


def _pdf_decomposition_ocr_confidences(source: Mapping[str, Any]) -> list[float]:
    values: list[float] = []
    for candidate in _pdf_decomposition_nested_sources(source):
        for field in PDF_DECOMPOSITION_OCR_CONFIDENCE_FIELDS:
            value = _pdf_decomposition_normalize_ocr_confidence(candidate.get(field))
            if value is not None:
                values.append(value)
    return values


def build_pdf_source_native_decomposition(
    *,
    items: Sequence[EvalItem],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    del items
    pdf_query_count = 0
    page_present_count = 0
    bbox_present_count = 0
    page_bbox_co_located_count = 0
    section_or_table_axis_present_count = 0
    ocr_confidence_present_count = 0
    lower_trust_due_to_ocr_count = 0

    for row in rows:
        sources = [
            source
            for source in _pdf_decomposition_candidate_sources(row)
            if _clean(source.get("source_family")).upper() == "PDF"
        ]
        if not sources:
            continue
        pdf_query_count += 1
        source_has_page = [
            _pdf_decomposition_has_any(source, PDF_DECOMPOSITION_PAGE_FIELDS)
            for source in sources
        ]
        source_has_bbox = [
            _pdf_decomposition_has_any(source, PDF_DECOMPOSITION_BBOX_FIELDS)
            for source in sources
        ]
        if any(source_has_page):
            page_present_count += 1
        if any(source_has_bbox):
            bbox_present_count += 1
        if any(has_page and has_bbox for has_page, has_bbox in zip(source_has_page, source_has_bbox)):
            page_bbox_co_located_count += 1
        if any(_pdf_decomposition_has_any(source, PDF_DECOMPOSITION_SECTION_OR_TABLE_FIELDS) for source in sources):
            section_or_table_axis_present_count += 1
        ocr_confidences = [
            confidence
            for source in sources
            for confidence in _pdf_decomposition_ocr_confidences(source)
        ]
        if ocr_confidences:
            ocr_confidence_present_count += 1
        if any(confidence < PDF_DECOMPOSITION_OCR_LOWER_TRUST_THRESHOLD for confidence in ocr_confidences):
            lower_trust_due_to_ocr_count += 1

    return {
        "schema_version": PDF_SOURCE_NATIVE_DECOMPOSITION_SCHEMA_VERSION,
        "report_only_diagnostic": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "pdf_query_count": pdf_query_count,
        "page_present_count": page_present_count,
        "bbox_present_count": bbox_present_count,
        "page_bbox_co_located_count": page_bbox_co_located_count,
        "section_or_table_axis_present_count": section_or_table_axis_present_count,
        "ocr_confidence_present_count": ocr_confidence_present_count,
        "lower_trust_due_to_ocr_count": lower_trust_due_to_ocr_count,
        "uses_expected_fields": False,
        "uses_gold_fields": False,
        "uses_qrels": False,
        "uses_labels": False,
        "uses_ids": False,
        "uses_raw_xlsx_or_pdf_query_time_parsing": False,
    }


SOURCE_NATIVE_AXIS_PROVENANCE_FIELDS = (
    "sheet",
    "cell_range",
    "cell",
    "row_label",
    "column_label",
    "target_column",
    "header_path",
    "table_id",
    "display_value",
    "page_number",
    "section_title",
    "table_caption",
    "bbox",
)


def _axis_presence_for_fields(
    sources: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> dict[str, list[str]]:
    present = [
        field
        for field in fields
        if any(_source_value_present(source.get(field)) for source in sources)
    ]
    return {
        "present": present,
        "missing": [field for field in fields if field not in present],
    }


def _stage_text(sources: Sequence[Mapping[str, Any]]) -> str:
    return " ".join(_gate_support_text(source) for source in sources if _gate_support_text(source))


def _stage_anchor_presence(
    *,
    query: str,
    answer: str,
    sources: Sequence[Mapping[str, Any]],
    source_family: str,
) -> dict[str, bool]:
    text = _stage_text(sources)
    query_anchors = _candidate_anchors(query)
    entity_anchors = set(query_anchors) - _numeric_or_date_anchors(query_anchors)
    answer_value_present = _text_has_answer_value_anchor_beyond_query(query, text) if text else False
    if answer and not answer_value_present:
        answer_value_present = _text_has_answer_value_anchor_beyond_query(query, answer)
    axis_present = bool(_residual_axis_presence(source_family, sources)[0])
    date_or_number_present = _text_has_numeric_or_date_value(text)
    return {
        "query_anchor_present": bool(query_anchors and _anchor_in_text(query_anchors, text)),
        "entity_anchor_present": bool(entity_anchors and _anchor_in_text(entity_anchors, text)),
        "value_anchor_present": bool(answer_value_present),
        "date_or_number_anchor_present": bool(date_or_number_present),
        "axis_anchor_present": axis_present,
    }


def _final_answer_sources(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    answer = _clean(row.get("generated_answer"))
    if not answer:
        return []
    return [{"text": answer}]


def _gate_validation_reasons_for_matrix(row: Mapping[str, Any], residual_classification: str) -> list[str]:
    gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
    reasons = [
        _clean(reason)
        for reason in _as_list(gate.get("validation_reasons"))
        if _clean(reason)
    ]
    if (
        residual_classification == "selected_evidence_has_value_missing_axis"
        and "missing_validated_required_axes" not in reasons
    ):
        reasons.append("missing_validated_required_axes")
    return reasons


def _residual_anchor_matrix_row(row: Mapping[str, Any]) -> dict[str, Any]:
    retrieved = _row_retrieved_contexts(row)
    selected = _row_selected_evidence(row)
    final_answer = _final_answer_sources(row)
    source_family = _source_family_for_diagnostic(row)
    query = _clean(row.get("query"))
    answer = _clean(row.get("generated_answer"))
    residual = _classify_xlsx_pdf_residual_row(row)
    residual_classification = _clean(residual.get("classification")) or "not_classified"
    query_shape = _query_shape(query)
    if source_family == "XLSX" and query_shape in {"numeric_date_fact", "entity_fact"}:
        query_shape = "table_lookup"
    elif source_family == "PDF" and query_shape in {"numeric_date_fact", "entity_fact"}:
        query_shape = "page_section_lookup"
    return {
        "item_id": _diagnostic_row_id(row.get("id")),
        "source_family": source_family,
        "query_shape": query_shape,
        "retrieval_empty": not bool(retrieved),
        "topk_anchor_presence": _stage_anchor_presence(
            query=query,
            answer=answer,
            sources=retrieved,
            source_family=source_family,
        ),
        "selected_evidence_anchor_presence": _stage_anchor_presence(
            query=query,
            answer=answer,
            sources=selected,
            source_family=source_family,
        ),
        "final_answer_anchor_presence": _stage_anchor_presence(
            query=query,
            answer=answer,
            sources=final_answer,
            source_family=source_family,
        ),
        "gate_validation_reasons": _gate_validation_reasons_for_matrix(row, residual_classification),
        "residual_classification": residual_classification,
    }


def build_residual_anchor_matrix(
    *,
    items: Sequence[EvalItem],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    _ = items
    matrix_rows = [_residual_anchor_matrix_row(row) for row in rows]
    return {
        "schema_version": RESIDUAL_ANCHOR_MATRIX_SCHEMA_VERSION,
        "report_only_diagnostic": True,
        "official_metric": False,
        "uses_gold_fields_as_runtime_inputs": False,
        "uses_expected_fields_as_runtime_inputs": False,
        "uses_qrels_or_labels_as_runtime_inputs": False,
        "row_count": len(matrix_rows),
        "rows": matrix_rows,
    }


def _axis_fields_for_provenance_family(source_family: str) -> tuple[str, ...]:
    if source_family == "XLSX":
        return (
            "sheet",
            "cell_range",
            "cell",
            "row_label",
            "column_label",
            "target_column",
            "header_path",
            "table_id",
            "display_value",
        )
    if source_family == "PDF":
        return (
            "page_number",
            "section_title",
            "table_caption",
            "bbox",
            "row_label",
            "column_label",
        )
    return SOURCE_NATIVE_AXIS_PROVENANCE_FIELDS


def _source_owned_metadata_sources_for_stage(sources: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    metadata_sources: list[Mapping[str, Any]] = []
    for source in sources:
        for container_key in SOURCE_DERIVED_EVIDENCE_METADATA_CONTAINERS:
            metadata_source = _parse_jsonish(source.get(container_key))
            if not isinstance(metadata_source, Mapping):
                continue
            if metadata_source not in metadata_sources:
                metadata_sources.append(metadata_source)
    return metadata_sources


def _axis_provenance_row(row: Mapping[str, Any]) -> dict[str, Any]:
    retrieved = _row_retrieved_contexts(row)
    selected = _row_selected_evidence(row)
    citations = _row_contexts(row, "citations")
    source_family = _source_family_for_diagnostic(row)
    family_fields = _axis_fields_for_provenance_family(source_family)
    source_registry_or_manifest = _axis_presence_for_fields([], family_fields)
    source_registry_or_manifest["stage_status"] = "not_inspected"
    source_registry_or_manifest[
        "not_inspected_reason"
    ] = "report_only_output_axis_loss_diagnostic_no_source_registry_or_manifest_runtime_input"
    return {
        "item_id": _diagnostic_row_id(row.get("id")),
        "source_family": source_family,
        "axis_presence_by_stage": {
            "source_registry_or_manifest": source_registry_or_manifest,
            "raw_locator_metadata": _axis_presence_for_fields(
                _source_owned_metadata_sources_for_stage(retrieved),
                family_fields,
            ),
            "weaviate_payload": _axis_presence_for_fields(retrieved, family_fields),
            "retrieved_context": _axis_presence_for_fields(retrieved, family_fields),
            "selected_evidence": _axis_presence_for_fields(selected, family_fields),
            "final_citation": _axis_presence_for_fields(citations, family_fields),
        },
    }


def build_source_native_axis_provenance(
    *,
    items: Sequence[EvalItem],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    _ = items
    return {
        "schema_version": SOURCE_NATIVE_AXIS_PROVENANCE_SCHEMA_VERSION,
        "report_only_diagnostic": True,
        "official_metric": False,
        "axis_fields": list(SOURCE_NATIVE_AXIS_PROVENANCE_FIELDS),
        "stage_notes": {
            "source_registry_or_manifest": "not_inspected_report_only_diagnostic_no_source_registry_or_manifest_runtime_input"
        },
        "rows": [_axis_provenance_row(row) for row in rows],
    }


def _diagnostic_row_id(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    if "SECRET" in text.upper():
        return ""
    return text


def _row_retrieved_contexts(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    contexts = _row_contexts(row, "retrieved_contexts")
    if contexts:
        return contexts
    gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
    return _residual_contexts(row, gate, "retrieved_evidence_candidates")


def _row_selected_evidence(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
    selected = _residual_contexts(row, gate, "selected_evidence")
    if selected:
        return selected
    composer = row.get("answer_composer") if isinstance(row.get("answer_composer"), Mapping) else {}
    values = composer.get("selected_evidence")
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        return [value for value in values if isinstance(value, Mapping)]
    return []


def _source_family_for_diagnostic(row: Mapping[str, Any]) -> str:
    for source in (*_row_selected_evidence(row), *_row_retrieved_contexts(row), *_row_contexts(row, "citations")):
        family = _clean(source.get("source_family")).upper()
        if family in {"TEXT", "XLSX", "PDF", "CSV"}:
            return family
    return "unknown"


def _row_has_source_value(sources: Sequence[Mapping[str, Any]]) -> bool:
    value_fields = (
        "display_value",
        "value",
        "answer_value",
        "cell_value",
        "table_value",
        "normalized_display_value",
    )
    for source in sources:
        if any(_source_value_present(source.get(field)) for field in value_fields):
            return True
        text = _gate_row_text(source)
        if _text_has_numeric_or_date_value(text):
            return True
    return False


def _answer_discipline_maps(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    composer = row.get("answer_composer") if isinstance(row.get("answer_composer"), Mapping) else {}
    maps: list[Mapping[str, Any]] = []
    for key in ("initial_answer_discipline", "answer_discipline"):
        value = composer.get(key)
        if isinstance(value, Mapping):
            maps.append(value)
    return maps


def _selected_evidence_failure_row(row: Mapping[str, Any]) -> dict[str, Any]:
    gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
    composer = row.get("answer_composer") if isinstance(row.get("answer_composer"), Mapping) else {}
    retrieved = _row_retrieved_contexts(row)
    selected = _row_selected_evidence(row)
    selected_count = int(composer.get("selected_evidence_count") or len(selected) or 0)
    validation_reasons = {_clean(value) for value in _as_list(gate.get("validation_reasons")) if _clean(value)}
    answer_gate_decision = _clean(gate.get("answer_gate_decision"))
    evidence_status = _clean(gate.get("evidence_package_status"))
    local_llm = composer.get("local_llm") if isinstance(composer.get("local_llm"), Mapping) else {}
    initial_discipline = (
        composer.get("initial_answer_discipline")
        if isinstance(composer.get("initial_answer_discipline"), Mapping)
        else {}
    )
    discipline_maps = _answer_discipline_maps(row)
    discipline_statuses = {_clean(discipline.get("status")) for discipline in discipline_maps}
    pre_fallback_true_insufficient = bool(
        _clean(local_llm.get("fallback_reason")) == "answer_discipline_true_insufficient_evidence"
        or _clean(local_llm.get("status")) == "answer_discipline_deterministic_fallback"
        or _clean(initial_discipline.get("status")) == "true_insufficient_evidence"
    )
    local_llm_clean_gate_blocked = (
        _clean(local_llm.get("status")) == "generated"
        and "clean_supported" in discipline_statuses
        and answer_gate_decision == "block_unsupported_answer"
    )
    selected_anchor_missing = bool(
        selected_count
        and validation_reasons
        & {"missing_query_anchor", "missing_entity_anchor", "missing_numeric_or_date_anchor"}
    )
    selected_absent = bool(retrieved and selected_count == 0)
    selected_value_present_anchor_missing = bool(
        _row_has_source_value([*selected, *retrieved])
        and (selected_anchor_missing or selected_absent)
    )
    citation_mismatch = bool(
        any(_clean(discipline.get("status")) == "citation_id_mismatch_or_missing" for discipline in discipline_maps)
        or int(gate.get("citation_wrong_target_count") or 0)
        or int(gate.get("citation_missing_target_count") or 0)
    )
    answer_overexpanded = any(
        bool(discipline.get("unsupported_extra_detail"))
        or bool(discipline.get("query_irrelevant_supported_detail"))
        or _clean(discipline.get("status"))
        in {
            "supported_core_with_unsupported_extra",
            "query_irrelevant_supported_detail",
            "local_llm_rejected_then_deterministic_overexpanded",
        }
        for discipline in discipline_maps
    )
    retrieval_empty = not retrieved
    corpus_missing = bool(retrieval_empty or (evidence_status == "insufficient" and not selected_count))
    true_insufficient = bool(
        retrieval_empty
        or selected_absent
        or (evidence_status == "insufficient" and not selected_count)
        or evidence_status == "insufficient"
        or answer_gate_decision == "block_unsupported_answer"
    )
    classifications: list[str] = []
    if retrieval_empty:
        classifications.append("retrieval_empty")
    if selected_absent:
        classifications.append("selected_evidence_absent")
    if selected_anchor_missing:
        classifications.append("selected_evidence_anchor_missing")
    if selected_value_present_anchor_missing:
        classifications.append("selected_evidence_value_present_anchor_missing")
    if citation_mismatch:
        classifications.append("citation_id_mismatch_or_missing")
    if local_llm_clean_gate_blocked:
        classifications.append("gate_blocked_clean_local_llm")
    if corpus_missing:
        classifications.append("corpus_coverage_suspected_missing")
    if answer_overexpanded:
        classifications.append("answer_discipline_overexpansion")
    if pre_fallback_true_insufficient:
        classifications.append("pre_fallback_true_insufficient_evidence")
    if true_insufficient:
        classifications.append("true_insufficient_evidence")
    if not classifications:
        classifications.append("no_failure_detected")
    answer_preview = _bounded_text_preview(row.get("generated_answer"), 160)
    evidence_preview = ""
    if selected:
        evidence_preview = _bounded_text_preview(_gate_support_text(selected[0]), 160)
    elif retrieved:
        evidence_preview = _bounded_text_preview(_gate_support_text(retrieved[0]), 160)
    return {
        "id": _diagnostic_row_id(row.get("id")),
        "classifications": classifications,
        "source_family": _source_family_for_diagnostic(row),
        "retrieved_context_count": len(retrieved),
        "selected_evidence_count": selected_count,
        "evidence_package_status": evidence_status,
        "answer_gate_decision": answer_gate_decision,
        "validation_reasons": sorted(validation_reasons),
        "retrieval_empty": retrieval_empty,
        "selected_evidence_absent": selected_absent,
        "selected_evidence_anchor_missing": selected_anchor_missing,
        "selected_evidence_value_present_anchor_missing": selected_value_present_anchor_missing,
        "citation_id_mismatch_or_missing": citation_mismatch,
        "local_llm_clean_answer_gate_blocked": local_llm_clean_gate_blocked,
        "pre_fallback_true_insufficient_evidence": pre_fallback_true_insufficient,
        "corpus_coverage_suspected_missing": corpus_missing,
        "answer_discipline_overexpansion": answer_overexpanded,
        "true_insufficient_evidence": true_insufficient,
        "bounded_answer_preview": answer_preview,
        "bounded_selected_evidence_preview": evidence_preview,
    }


def build_selected_evidence_failure_decomposition(
    *,
    items: Sequence[EvalItem],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    _ = items
    diagnostic_rows = [_selected_evidence_failure_row(row) for row in rows]
    def count(flag: str) -> int:
        return sum(1 for row in diagnostic_rows if bool(row.get(flag)))

    return {
        "schema_version": "selected_evidence_failure_decomposition_v1",
        "report_only_diagnostic": True,
        "official_metric": False,
        "uses_expected_fields_as_runtime_inputs": False,
        "post_run_expected_evidence_diagnostics_used": False,
        "uses_gold_fields": False,
        "uses_qrels": False,
        "uses_labels": False,
        "uses_ids_as_runtime_inputs": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "retrieval_empty_count": count("retrieval_empty"),
        "retrieval_related_but_expected_evidence_unresolved_count_diagnostic": 0,
        "selected_evidence_absent_count": count("selected_evidence_absent"),
        "selected_evidence_anchor_missing_count": count("selected_evidence_anchor_missing"),
        "selected_evidence_value_present_anchor_missing_count": count(
            "selected_evidence_value_present_anchor_missing"
        ),
        "citation_id_mismatch_or_missing_count": count("citation_id_mismatch_or_missing"),
        "gate_blocked_clean_local_llm_count": count("local_llm_clean_answer_gate_blocked"),
        "pre_fallback_true_insufficient_evidence_count": count("pre_fallback_true_insufficient_evidence"),
        "corpus_coverage_suspected_missing_count": count("corpus_coverage_suspected_missing"),
        "answer_discipline_overexpansion_count": count("answer_discipline_overexpansion"),
        "true_insufficient_evidence_count": count("true_insufficient_evidence"),
        "rows": diagnostic_rows,
    }


def _query_shape(query: str) -> str:
    text = normalize_answer_text(query)
    if any(term in text for term in ("page", "section", "chapter", "페이지", "쪽", "섹션", "장")):
        return "page_section_lookup"
    if any(term in text for term in ("table", "row", "column", "cell", "sheet", "표", "행", "열", "셀", "시트")):
        return "table_lookup"
    if any(term in text for term in ("compare", "versus", "vs", "difference", "비교", "차이")):
        return "comparison"
    if re.search(r"\d", text) or any(
        term in text
        for term in (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
            "년",
            "월",
            "일",
        )
    ):
        return "numeric_date_fact"
    if any(term in text for term in ("average", "sum", "total", "count", "how many", "합계", "평균", "총", "몇")):
        return "aggregate"
    if any(term in text for term in ("why", "how", "explain", "method", "왜", "어떻게", "설명", "방법")):
        return "explanatory"
    return "entity_fact"


def _language_script(query: str) -> str:
    has_ko = bool(re.search(r"[가-힣]", query))
    has_en = bool(re.search(r"[A-Za-z]", query))
    if has_ko and has_en:
        return "mixed"
    if has_ko:
        return "Korean"
    if has_en:
        return "English"
    return "unknown"


def _composer_outcome(row: Mapping[str, Any]) -> str:
    composer = row.get("answer_composer") if isinstance(row.get("answer_composer"), Mapping) else {}
    local_llm = composer.get("local_llm") if isinstance(composer.get("local_llm"), Mapping) else {}
    if local_llm:
        status = _clean(local_llm.get("status")) or "unknown"
        if status == "generated" and not composer.get("local_llm_fallback_used"):
            return "local_llm_accepted"
        if "fallback" in status:
            return "local_llm_fallback"
        if "abstain" in status:
            return "local_llm_abstained"
        return f"local_llm_{status}"
    if composer.get("abstained"):
        return "deterministic_abstained"
    if composer:
        return "deterministic_allowed"
    return "unknown"


def build_dataset_sufficiency_diagnostic(
    *,
    items: Sequence[EvalItem],
    rows: Sequence[Mapping[str, Any]],
    dataset_path: Path,
) -> dict[str, Any]:
    item_by_id = {_clean(item.id): item for item in items}
    source_counts: Counter[str] = Counter()
    shape_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    availability_counts: Counter[str] = Counter()
    composer_counts: Counter[str] = Counter()
    diagnostic_rows: list[dict[str, Any]] = []
    coverage_gaps: list[dict[str, Any]] = []
    rows_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        item_id_raw = _clean(row.get("id"))
        item = item_by_id.get(item_id_raw)
        query = _clean(row.get("query") or (item.query if item else ""))
        gate = row.get("evidence_gate") if isinstance(row.get("evidence_gate"), Mapping) else {}
        retrieved = _row_retrieved_contexts(row)
        selected = _row_selected_evidence(row)
        family = _source_family_for_diagnostic(row)
        shape = _query_shape(query)
        language = _language_script(query)
        selected_present = bool(selected)
        retrieved_present = bool(retrieved)
        coverage_suspected = not retrieved_present
        availability = (
            "selected_evidence_present"
            if selected_present
            else "retrieved_context_present"
            if retrieved_present
            else "corpus_coverage_suspected_missing"
        )
        source_counts[family] += 1
        shape_counts[shape] += 1
        language_counts[language] += 1
        availability_counts[availability] += 1
        composer_outcome = _composer_outcome(row)
        composer_counts[composer_outcome] += 1
        safe_id = _diagnostic_row_id(item_id_raw)
        external_needed = bool(coverage_suspected)
        row_diagnostic = {
            "id": safe_id,
            "source_family": family,
            "query_shape": shape,
            "language_script": language,
            "evidence_availability": availability,
            "composer_outcome": composer_outcome,
            "retrieved_context_present": retrieved_present,
            "selected_evidence_present": selected_present,
            "corpus_coverage_suspected_missing": coverage_suspected,
            "external_archive_candidate_needed": external_needed,
        }
        diagnostic_rows.append(row_diagnostic)
        if safe_id:
            rows_by_id[safe_id] = row_diagnostic
        if external_needed:
            coverage_gaps.append(
                {
                    "id": safe_id,
                    "source_family": family,
                    "query_shape": shape,
                    "reason": "retrieval_empty_or_corpus_coverage_suspected",
                }
            )
    dataset_text = _clean(dataset_path.as_posix()).casefold()
    return {
        "schema_version": "dataset_sufficiency_diagnostic_v1",
        "report_only_diagnostic": True,
        "official_metric": False,
        "uses_gold_fields": False,
        "uses_expected_fields_as_runtime_inputs": False,
        "uses_qrels": False,
        "uses_labels": False,
        "uses_ids_as_runtime_inputs": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "gold_rows_checked": len(rows) if "gold" in dataset_text else 0,
        "silver_rows_checked": len(rows) if "silver" in dataset_text else 0,
        "source_families_observed": dict(source_counts),
        "query_shape_counts": dict(shape_counts),
        "language_script_counts": dict(language_counts),
        "evidence_availability_counts": dict(availability_counts),
        "composer_outcome_counts": dict(composer_counts),
        "coverage_gaps": coverage_gaps,
        "external_archive_recommended": bool(coverage_gaps),
        "external_archive_used": False,
        "external_archive_root": "",
        "rows": diagnostic_rows,
        "rows_by_id": rows_by_id,
    }


RULE_SURFACE_KEY_TOKENS = (
    "heuristic_rule",
    "rule_surface",
    "literal_case",
    "literal_terms",
    "case_specific",
    "hardcoded_alias",
    "row_specific",
    "dataset_specific",
)
ROW_RULE_KEY_TOKENS = ("row_specific", "query_id_rule", "target_id_rule")
DATASET_RULE_KEY_TOKENS = ("dataset_specific",)
LITERAL_RULE_KEY_TOKENS = ("literal_case", "literal_terms", "case_specific", "hardcoded_alias")
ROW_SPECIFIC_RULE_RE = re.compile(r"\b(?:text_namu_v\d+_\d+|gq_[\w-]+|row[_-]?id|query[_-]?id|target[_-]?id)\b", re.IGNORECASE)
DATASET_SPECIFIC_RULE_RE = re.compile(
    r"\b(?:gold(?:\d+)?|silver(?:\d+)?|six[-_\s]?row|namu[_-]?v\d+|dataset[-_\s]?specific)\b",
    re.IGNORECASE,
)


def _heuristic_rule_kinds_for_key(key: str) -> set[str]:
    normalized = _clean(key).casefold()
    kinds: set[str] = set()
    if any(token in normalized for token in LITERAL_RULE_KEY_TOKENS):
        kinds.add("literal")
    if any(token in normalized for token in ROW_RULE_KEY_TOKENS):
        kinds.add("row")
    if any(token in normalized for token in DATASET_RULE_KEY_TOKENS):
        kinds.add("dataset")
    if any(token in normalized for token in RULE_SURFACE_KEY_TOKENS):
        kinds.add("surface")
    if ROW_SPECIFIC_RULE_RE.search(normalized):
        kinds.add("row")
    if DATASET_SPECIFIC_RULE_RE.search(normalized):
        kinds.add("dataset")
    return kinds


def _collect_configured_rule_surfaces(
    value: Any,
    *,
    path: tuple[str, ...] = (),
    active_kinds: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = _clean(raw_key)
            if not key:
                continue
            key_kinds = _heuristic_rule_kinds_for_key(key)
            next_kinds = frozenset(set(active_kinds) | key_kinds)
            if key_kinds - {"surface"}:
                surfaces.append(
                    {
                        "path": ".".join((*path, key)),
                        "kinds": sorted(key_kinds - {"surface"}),
                        "term": key,
                    }
                )
            surfaces.extend(_collect_configured_rule_surfaces(child, path=(*path, key), active_kinds=next_kinds))
        return surfaces
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            surfaces.extend(_collect_configured_rule_surfaces(child, path=(*path, str(index)), active_kinds=active_kinds))
        return surfaces
    term = _clean(value)
    if not term or not active_kinds:
        return surfaces
    kinds = set(active_kinds) - {"surface"}
    if "row" not in kinds and ROW_SPECIFIC_RULE_RE.search(term):
        kinds.add("row")
    if "dataset" not in kinds and DATASET_SPECIFIC_RULE_RE.search(term):
        kinds.add("dataset")
    if "literal" not in kinds and ("surface" in active_kinds):
        kinds.add("literal")
    if not kinds:
        return surfaces
    surfaces.append(
        {
            "path": ".".join(path),
            "kinds": sorted(kinds),
            "term": _bounded_text_preview(term, 120),
        }
    )
    return surfaces


def build_overfit_and_heuristic_audit(
    *,
    rows: Sequence[Mapping[str, Any]],
    generator_config: Mapping[str, Any],
) -> dict[str, Any]:
    detected_surfaces = _collect_configured_rule_surfaces(generator_config)
    literal_terms = sorted(
        {
            _clean(surface.get("term"))
            for surface in detected_surfaces
            if "literal" in set(surface.get("kinds") or []) and _clean(surface.get("term"))
        }
    )
    row_specific_detected = any("row" in set(surface.get("kinds") or []) for surface in detected_surfaces)
    dataset_specific_detected = any("dataset" in set(surface.get("kinds") or []) for surface in detected_surfaces)
    return {
        "schema_version": "overfit_and_heuristic_audit_v1",
        "report_only_diagnostic": True,
        "gold_or_expected_runtime_input_detected": False,
        "audit_method": "configured_rule_surface_scan_v1",
        "rule_surface_count": len(detected_surfaces),
        "row_specific_rule_detected": row_specific_detected,
        "dataset_specific_rule_detected": dataset_specific_detected,
        "literal_case_term_rule_detected": bool(literal_terms),
        "literal_case_terms_detected": literal_terms,
        "detected_rule_surfaces": detected_surfaces,
        "uses_expected_answers": False,
        "uses_expected_evidence": False,
        "uses_qrels": False,
        "uses_labels": False,
        "uses_ids_as_runtime_inputs": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "remaining_rule_based_components": [
            "answer_focus_generic_terms",
            "bounded_evidence_gate_v1",
            "source_family_query_shape_classifier",
        ],
        "row_count_checked": len(rows),
        "input_policy": (
            _clean(generator_config.get("selected_evidence_composer_input_policy"))
            or "query_text_and_selected_sourceatom_evidence_only_no_gold_qrels_labels_ids_or_baseline"
        ),
    }


def apply_evidence_gate_to_outputs(
    raw_outputs: Sequence[Mapping[str, Any]],
    *,
    mode: str = "off",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized_mode = _clean(mode).lower() or "off"
    if normalized_mode not in {"off", "diagnostic", "enforce"}:
        raise DatasetSchemaError(f"unsupported evidence gate mode: {mode}")
    rows = [_apply_evidence_gate_to_row(row, mode=normalized_mode) for row in raw_outputs]
    return rows, build_evidence_gate_summary(rows, mode=normalized_mode)


def _answer_matches_expected_deterministic(answer: str, item: EvalItem) -> bool:
    if answer_correct(answer, expected_answer=item.expected_answer, aliases=item.expected_answer_aliases):
        return True
    answer_norm = normalize_answer_text(answer)
    expected_values = [item.expected_answer, *item.expected_answer_aliases]
    expected_norms = [normalize_answer_text(value) for value in expected_values if normalize_answer_text(value)]
    if any(expected_norm and expected_norm in answer_norm for expected_norm in expected_norms):
        return True
    if any(answer_norm and answer_norm in expected_norm for expected_norm in expected_norms):
        return True
    anchors = _candidate_anchors(*expected_values)
    if anchors and _anchor_requirements_satisfied(anchors, answer):
        numeric_anchors = _numeric_or_date_anchors(anchors)
        non_numeric = anchors - numeric_anchors
        return bool(numeric_anchors or non_numeric)
    return False


def _answers_equivalent_deterministic(left: str, right: str, item: EvalItem) -> bool:
    left_norm = normalize_answer_text(left)
    right_norm = normalize_answer_text(right)
    if left_norm and left_norm == right_norm:
        return True
    if left_norm and right_norm and (left_norm in right_norm or right_norm in left_norm):
        return True
    if _answer_matches_expected_deterministic(left, item) and _answer_matches_expected_deterministic(right, item):
        return True
    if abstains(left) and abstains(right):
        return True
    anchors = _candidate_anchors(item.expected_answer, *item.expected_answer_aliases)
    return bool(anchors and _anchor_requirements_satisfied(anchors, left) and _anchor_requirements_satisfied(anchors, right))


def _required_evidence_missing(item: EvalItem, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for evidence in _required_evidence(item):
        anchors = _evidence_match_anchors(item, evidence)
        if any(_evidence_matches_row(evidence, row) or _weak_evidence_matches_row(evidence, row, anchors=anchors) for row in rows):
            continue
        missing.append(evidence.to_dict())
    return missing


def _support_status(item: EvalItem, contexts: Sequence[Mapping[str, Any]], citations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    context_hit = bool(item.has_expected_evidence and not _required_evidence_missing(item, contexts))
    citation_hit = bool(item.has_expected_evidence and citations and not _required_evidence_missing(item, citations))
    citation_points_to_context = False
    if citations and contexts:
        for citation in citations:
            citation_key = _context_key(citation)[:2]
            if any(citation_key == _context_key(context)[:2] and any(citation_key) for context in contexts):
                citation_points_to_context = True
                break
            citation_text = _clean(citation.get("text"))
            if citation_text and any(
                _weak_evidence_matches_row(
                    ExpectedEvidence(text=citation_text),
                    context,
                    anchors=_candidate_anchors(citation_text),
                )
                for context in contexts
            ):
                citation_points_to_context = True
                break
    return {
        "expected_evidence_hit": context_hit,
        "citation_expected_evidence_hit": citation_hit,
        "citation_points_to_retrieved_context": citation_points_to_context,
        "supported": bool(context_hit or citation_hit),
    }


def _evidence_package_for_item(item: EvalItem, real_row: Mapping[str, Any]) -> dict[str, Any]:
    contexts = _contexts_from_row(real_row)
    citations = _citations_from_row(real_row)
    citation_ids = set(_context_id_list(citations))
    selected = [
        dict(context)
        for context in contexts
        if _context_identity(context) in citation_ids
        or any(
            _evidence_matches_row(evidence, context)
            or _weak_evidence_matches_row(evidence, context, anchors=_evidence_match_anchors(item, evidence))
            for evidence in _required_evidence(item)
        )
    ]
    resolution = real_row.get("expected_evidence_resolution") if isinstance(real_row.get("expected_evidence_resolution"), Mapping) else {}
    low_confidence: list[dict[str, Any]] = []
    unresolved = False
    for resolution_row in _as_list(resolution.get("rows")):
        if not isinstance(resolution_row, Mapping):
            continue
        if not resolution_row.get("resolved"):
            unresolved = True
        for candidate in _as_list(resolution_row.get("candidates")):
            if isinstance(candidate, Mapping) and _clean(candidate.get("confidence")) in {"low", "medium"}:
                low_confidence.append(dict(candidate))
    missing = _required_evidence_missing(item, [*contexts, *citations])
    support = _support_status(item, contexts, citations)
    if not item.has_expected_evidence:
        status = "not_comparable"
    elif support["supported"] and not missing:
        status = "sufficient"
    elif missing:
        status = "insufficient"
    elif unresolved:
        status = "unresolved"
    elif contexts:
        status = "conflicting"
    else:
        status = "insufficient"
    return {
        "retrieved_evidence_candidates": contexts,
        "selected_evidence": selected,
        "citation_targets": citations,
        "evidence_text_hashes": _text_hashes([*contexts, *citations]),
        "rejected_or_low_confidence_evidence": low_confidence,
        "missing_required_evidence": missing,
        "evidence_package_status": status,
        "support": support,
    }


def _diagnostic_critic_for_item(
    *,
    real_supported: bool,
    citation_supported_by_evidence: bool,
    citation_points_to_retrieved_context: bool,
    evidence_package_status: str,
    real_matches_expected: bool,
    real_answer: str,
) -> dict[str, Any]:
    evidence_sufficient = evidence_package_status == "sufficient"
    should_abstain = bool((not real_matches_expected or not real_supported or not evidence_sufficient) and not abstains(real_answer))
    if evidence_sufficient and real_matches_expected and real_supported:
        reason = ""
    elif not evidence_sufficient:
        reason = "evidence_package_not_sufficient"
    elif not real_matches_expected:
        reason = "answer_not_deterministically_supported_by_gold"
    else:
        reason = "citation_or_answer_support_incomplete"
    return {
        "answer_supported_by_evidence": bool(real_supported),
        "citation_supported_by_evidence": bool(citation_supported_by_evidence),
        "citation_points_to_retrieved_context_diagnostic_only": bool(citation_points_to_retrieved_context),
        "evidence_sufficient": evidence_sufficient,
        "needs_more_retrieval": not evidence_sufficient,
        "should_abstain": should_abstain,
        "critic_rejection_reason": reason,
        "critic_result_tier": "diagnostic",
        "retrieval_loop_triggered": False,
    }


def _quality_gate_guardrail_status(real_report: Mapping[str, Any]) -> dict[str, Any]:
    guardrails = real_report.get("guardrails") if isinstance(real_report.get("guardrails"), Mapping) else {}
    retrieval_surface = real_report.get("retrieval_surface") if isinstance(real_report.get("retrieval_surface"), Mapping) else {}
    layered = real_report.get("source_native_layered_retrieval") if isinstance(real_report.get("source_native_layered_retrieval"), Mapping) else {}
    evidence_gate = real_report.get("evidence_gate") if isinstance(real_report.get("evidence_gate"), Mapping) else {}
    evidence_gate_guardrails = (
        evidence_gate.get("guardrail_status")
        if isinstance(evidence_gate.get("guardrail_status"), Mapping)
        else {}
    )
    expected_fields_closed = not any(
        bool(guardrails.get(key) or real_report.get(key) or layered.get(key))
        for key in (
            "expected_fields_used_for_candidate_generation",
            "gold_fields_used_for_candidate_generation",
            "qrels_used_for_candidate_generation",
            "answerability_labels_used_for_candidate_generation",
            "ids_used_for_candidate_generation",
            "baseline_topk_used_for_candidate_generation",
        )
    )
    gate_enforcement_closed = not any(
        bool(evidence_gate_guardrails.get(key) or real_report.get(key) or guardrails.get(key))
        for key in (
            "gate_uses_expected_fields",
            "gate_uses_gold_fields",
            "gate_uses_legacy_fields",
            "retrieval_loop_triggered",
            "evidence_gate_retrieval_loop_triggered",
        )
    )
    source_native_selected = bool(
        retrieval_surface.get("selected") == "source_native"
        or retrieval_surface.get("source_native_selected")
        or layered.get("selected_surface") == "source_native"
    )
    source_native_units_only = bool(
        layered.get("source_native_units_only") is True
        or (
            source_native_selected
            and not bool(retrieval_surface.get("searchunit_searchview_candidate_surface_enabled"))
            and not bool(retrieval_surface.get("auto_fallback_to_searchunit_searchview"))
        )
    )
    searchunit_searchview_used = bool(
        retrieval_surface.get("searchunit_searchview_candidate_surface_enabled")
        or retrieval_surface.get("auto_fallback_to_searchunit_searchview")
        or retrieval_surface.get("legacy_surface_comparison_enabled")
        or real_report.get("searchunit_searchview_candidate_surface_enabled")
        or real_report.get("auto_fallback_to_searchunit_searchview")
        or real_report.get("legacy_surface_comparison_enabled")
        or guardrails.get("searchunit_searchview_candidate_surface_enabled")
        or guardrails.get("auto_fallback_to_searchunit_searchview")
        or guardrails.get("legacy_surface_comparison_enabled")
    )
    status = {
        "gold_qrels_labels_not_mutated": not any(
            bool(guardrails.get(key) or real_report.get(key))
            for key in (
                "gold_mutation",
                "qrels_mutation",
                "label_mutation",
                "answerability_label_mutation",
                "expected_answer_mutation",
                "expected_evidence_mutation",
                "denominator_mutation",
                "gold_or_qrels_mutation",
            )
        ),
        "expected_fields_not_used_for_candidate_generation": expected_fields_closed,
        "expected_gold_legacy_not_used_for_evidence_gate_enforcement": gate_enforcement_closed,
        "legacy_outputs_not_used_for_candidate_generation": not bool(
            guardrails.get("baseline_topk_used_for_candidate_generation")
            or real_report.get("baseline_topk_used_for_candidate_generation")
            or layered.get("baseline_topk_used_for_candidate_generation")
        ),
        "searchunit_searchview_not_used_in_real_rag_lane": not searchunit_searchview_used,
        "source_native_selected": source_native_selected,
        "source_native_units_only": source_native_units_only,
        "production_namespace_untouched": not bool(guardrails.get("protected_namespaces_touched") or real_report.get("protected_namespaces_touched")),
        "raw_prompt_response_payloads_not_written": not bool(
            guardrails.get("raw_prompt_payload_written")
            or guardrails.get("raw_response_payload_written")
            or real_report.get("raw_prompt_payload_written")
            or real_report.get("raw_response_payload_written")
        ),
        "official_metric_closed": not bool(guardrails.get("official_metric") or real_report.get("official_metric")),
    }
    violations = [key for key, value in status.items() if value is not True]
    status["valid"] = not violations
    status["violations"] = violations
    return status


def _answer_delta_category(
    *,
    legacy_answer: str,
    real_answer: str,
    item: EvalItem,
    legacy_matches_expected: bool,
    real_matches_expected: bool,
    same_support: bool,
    different_support_but_valid: bool,
    baseline_missing: bool,
) -> str:
    if baseline_missing:
        return "not_comparable_missing_baseline"
    if not bool(getattr(item, "has_expected_answer", bool(_clean(getattr(item, "expected_answer", ""))))):
        return "not_comparable_missing_gold"
    if abstains(real_answer) and not abstains(legacy_answer):
        return "real_abstained_legacy_answered"
    if abstains(legacy_answer) and not abstains(real_answer):
        return "legacy_abstained_real_answered"
    exact_same = _clean(legacy_answer) == _clean(real_answer) and bool(_clean(real_answer))
    normalized_same = normalize_answer_text(legacy_answer) == normalize_answer_text(real_answer) and bool(normalize_answer_text(real_answer))
    equivalent = _answers_equivalent_deterministic(legacy_answer, real_answer, item)
    if exact_same or normalized_same:
        return "same_answer_same_support" if same_support else "same_answer_different_support"
    if equivalent:
        if legacy_matches_expected and real_matches_expected and not same_support and not different_support_but_valid:
            return "both_correct_different_wording"
        return "equivalent_answer_same_support" if same_support else "equivalent_answer_different_support"
    if legacy_matches_expected and not real_matches_expected:
        return "legacy_correct_real_wrong"
    if real_matches_expected and not legacy_matches_expected:
        return "legacy_wrong_real_correct"
    if legacy_matches_expected and real_matches_expected:
        return "both_correct_different_wording"
    return "both_wrong_same" if normalized_same else "both_wrong_different"


def _delta_category_for_support(
    *,
    legacy_supported: bool,
    real_supported: bool,
    same_support: bool,
    baseline_missing: bool,
    missing_gold: bool,
) -> str:
    if baseline_missing:
        return "not_comparable_missing_baseline"
    if missing_gold:
        return "not_comparable_missing_gold"
    if legacy_supported and real_supported and same_support:
        return "same_support"
    if legacy_supported and real_supported:
        return "different_support_but_valid"
    if legacy_supported and not real_supported:
        return "legacy_supported_real_unsupported"
    if real_supported and not legacy_supported:
        return "legacy_unsupported_real_supported"
    return "both_unsupported"


def build_legacy_real_rag_quality_gate_report(
    *,
    gold_items: Sequence[EvalItem],
    existing_gold_set_path: Path | str,
    legacy_baseline_report: Mapping[str, Any],
    legacy_baseline_path: Path | str,
    real_rag_report: Mapping[str, Any],
    real_rag_report_path: Path | str,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    legacy_items = [
        dict(row)
        for row in _as_list(legacy_baseline_report.get("items"))
        if isinstance(row, Mapping)
    ]
    real_items = [
        dict(row)
        for row in _as_list(real_rag_report.get("items"))
        if isinstance(row, Mapping)
    ]
    legacy_by_id = {_query_id(row): row for row in legacy_items}
    real_by_id = {_query_id(row): row for row in real_items}
    guardrail_status = _quality_gate_guardrail_status(real_rag_report)
    rows: list[dict[str, Any]] = []
    not_comparable_reasons: Counter[str] = Counter()
    for item in gold_items:
        legacy_row = legacy_by_id.get(item.id, {})
        real_row = real_by_id.get(item.id, {})
        legacy_contexts = _contexts_from_row(legacy_row)
        real_contexts = _contexts_from_row(real_row)
        legacy_citations = _citations_from_row(legacy_row)
        real_citations = _citations_from_row(real_row)
        real_gate = real_row.get("evidence_gate") if isinstance(real_row.get("evidence_gate"), Mapping) else {}
        legacy_answer = _clean(legacy_row.get("generated_answer"))
        real_answer = _clean(real_row.get("generated_answer"))
        real_answer_before_gate = _clean(real_row.get(INTERNAL_PRE_GATE_ANSWER_KEY)) or real_answer
        baseline_missing = not bool(legacy_row)
        real_missing = not bool(real_row)
        evidence_package = _evidence_package_for_item(item, real_row)
        legacy_support = _support_status(item, legacy_contexts, legacy_citations)
        real_support = evidence_package["support"]
        legacy_matches_expected = _answer_matches_expected_deterministic(legacy_answer, item)
        real_matches_expected_before_gate = _answer_matches_expected_deterministic(real_answer_before_gate, item)
        real_matches_expected = _answer_matches_expected_deterministic(real_answer, item)
        legacy_doc_ids = _doc_ids([*legacy_contexts, *legacy_citations])
        real_doc_ids = _doc_ids([*real_contexts, *real_citations])
        source_atom_overlap = bool(
            set(_field_id_list([*legacy_contexts, *legacy_citations], "source_atom_id"))
            & set(_field_id_list([*real_contexts, *real_citations], "source_atom_id"))
        )
        evidence_bundle_overlap = bool(
            set(_field_id_list([*legacy_contexts, *legacy_citations], "evidence_bundle_id"))
            & set(_field_id_list([*real_contexts, *real_citations], "evidence_bundle_id"))
        )
        text_hash_overlap = bool(set(_text_hashes([*legacy_contexts, *legacy_citations])) & set(_text_hashes([*real_contexts, *real_citations])))
        normalized_text_overlap = bool(
            {
                normalize_answer_text(_clean(row.get("text")))
                for row in [*legacy_contexts, *legacy_citations]
                if normalize_answer_text(_clean(row.get("text")))
            }
            & {
                normalize_answer_text(_clean(row.get("text")))
                for row in [*real_contexts, *real_citations]
                if normalize_answer_text(_clean(row.get("text")))
            }
        )
        same_support = bool(
            legacy_support["supported"]
            and real_support["supported"]
            and (legacy_doc_ids & real_doc_ids or source_atom_overlap or evidence_bundle_overlap or text_hash_overlap or normalized_text_overlap)
        )
        different_support_but_valid = bool(legacy_support["supported"] and real_support["supported"] and not same_support)
        answer_delta = _answer_delta_category(
            legacy_answer=legacy_answer,
            real_answer=real_answer,
            item=item,
            legacy_matches_expected=legacy_matches_expected,
            real_matches_expected=real_matches_expected,
            same_support=same_support,
            different_support_but_valid=different_support_but_valid,
            baseline_missing=baseline_missing,
        )
        answer_delta_before_gate = _answer_delta_category(
            legacy_answer=legacy_answer,
            real_answer=real_answer_before_gate,
            item=item,
            legacy_matches_expected=legacy_matches_expected,
            real_matches_expected=real_matches_expected_before_gate,
            same_support=same_support,
            different_support_but_valid=different_support_but_valid,
            baseline_missing=baseline_missing,
        )
        if real_missing:
            answer_delta = "not_comparable_missing_baseline"
            answer_delta_before_gate = "not_comparable_missing_baseline"
        evidence_delta = _delta_category_for_support(
            legacy_supported=bool(legacy_support["supported"]),
            real_supported=bool(real_support["supported"]),
            same_support=same_support,
            baseline_missing=baseline_missing or real_missing,
            missing_gold=not item.has_expected_evidence,
        )
        citation_delta = _delta_category_for_support(
            legacy_supported=bool(legacy_support["citation_expected_evidence_hit"]),
            real_supported=bool(real_support["citation_expected_evidence_hit"]),
            same_support=same_support,
            baseline_missing=baseline_missing or real_missing,
            missing_gold=not item.has_expected_evidence,
        )
        if answer_delta.startswith("not_comparable"):
            not_comparable_reasons[answer_delta] += 1
        critic = _diagnostic_critic_for_item(
            real_supported=bool(real_support["supported"]),
            citation_supported_by_evidence=bool(real_support["citation_expected_evidence_hit"]),
            citation_points_to_retrieved_context=bool(real_support["citation_points_to_retrieved_context"]),
            evidence_package_status=evidence_package["evidence_package_status"],
            real_matches_expected=real_matches_expected,
            real_answer=real_answer,
        )
        rows.append(
            {
                "query_id": item.id,
                "query": item.query,
                "expected_answer": item.expected_answer,
                "expected_answer_aliases": list(item.expected_answer_aliases),
                "expected_evidence": [evidence.to_dict() for evidence in item.expected_evidence],
                "answerability_label": item.answerability if item.has_answerability_label else "",
                "legacy_answer": legacy_answer,
                "real_rag_answer": real_answer,
                "legacy_citations": legacy_citations,
                "real_rag_citations": real_citations,
                "legacy_retrieved_context_ids": _legacy_context_id_list(legacy_contexts),
                "real_rag_source_atom_ids": _field_id_list(real_contexts, "source_atom_id"),
                "real_rag_evidence_bundle_ids": _field_id_list(real_contexts, "evidence_bundle_id"),
                "legacy_failure_labels": list(legacy_row.get("failure_labels") or []),
                "real_rag_failure_labels": list(real_row.get("failure_labels") or []),
                "retrieved_evidence_candidates": evidence_package["retrieved_evidence_candidates"],
                "selected_evidence": evidence_package["selected_evidence"],
                "citation_targets": evidence_package["citation_targets"],
                "evidence_text_hashes": evidence_package["evidence_text_hashes"],
                "rejected_or_low_confidence_evidence": evidence_package["rejected_or_low_confidence_evidence"],
                "missing_required_evidence": evidence_package["missing_required_evidence"],
                "evidence_package_status": evidence_package["evidence_package_status"],
                "answer_exact_same": _clean(legacy_answer) == _clean(real_answer) and bool(_clean(real_answer)),
                "answer_normalized_same": normalize_answer_text(legacy_answer) == normalize_answer_text(real_answer) and bool(normalize_answer_text(real_answer)),
                "answer_equivalent_deterministic": _answers_equivalent_deterministic(legacy_answer, real_answer, item),
                "legacy_matches_expected": legacy_matches_expected,
                "real_rag_matches_expected": real_matches_expected,
                "answer_delta_category": answer_delta,
                "evidence_delta_category": evidence_delta,
                "citation_delta_category": citation_delta,
                "doc_id_overlap": sorted(legacy_doc_ids & real_doc_ids),
                "source_atom_id_overlap": source_atom_overlap,
                "evidence_bundle_id_overlap": evidence_bundle_overlap,
                "text_hash_overlap": text_hash_overlap,
                "normalized_evidence_text_overlap": normalized_text_overlap,
                "expected_evidence_hit_in_legacy_topk": bool(legacy_support["expected_evidence_hit"]),
                "expected_evidence_hit_in_real_rag_topk": bool(real_support["expected_evidence_hit"]),
                "citation_points_to_expected_or_resolved_evidence": bool(real_support["citation_expected_evidence_hit"]),
                "citation_points_to_retrieved_context_diagnostic_only": bool(real_support["citation_points_to_retrieved_context"]),
                "real_rag_supported": bool(real_support["supported"]),
                "legacy_supported": bool(legacy_support["supported"]),
                "same_support": same_support,
                "different_support_but_valid": different_support_but_valid,
                "unsupported_same_answer": bool(
                    (normalize_answer_text(legacy_answer) == normalize_answer_text(real_answer) or _answers_equivalent_deterministic(legacy_answer, real_answer, item))
                    and not real_support["supported"]
                ),
                "diagnostic_critic": critic,
                "evidence_validator": dict(real_gate),
                "evidence_support_score": real_gate.get("evidence_support_score"),
                "answer_anchor_coverage": real_gate.get("answer_anchor_coverage"),
                "query_anchor_coverage": real_gate.get("query_anchor_coverage"),
                "numeric_or_date_anchor_coverage": real_gate.get("numeric_or_date_anchor_coverage"),
                "entity_anchor_coverage": real_gate.get("entity_anchor_coverage"),
                "selected_evidence_count": int(real_gate.get("selected_evidence_count") or 0),
                "rejected_evidence_count": int(real_gate.get("rejected_evidence_count") or 0),
                "missing_answer_anchors": list(real_gate.get("missing_answer_anchors") or []),
                "missing_query_anchors": list(real_gate.get("missing_query_anchors") or []),
                "unsupported_answer_anchors": list(real_gate.get("unsupported_answer_anchors") or []),
                "conflicting_evidence_reasons": list(real_gate.get("conflicting_evidence_reasons") or []),
                "validation_reasons": list(real_gate.get("validation_reasons") or []),
                "validator_version": _clean(real_gate.get("validator_version") or real_rag_report.get("validator_version")),
                "citation_validations": list(real_gate.get("citation_validations") or []),
                "evidence_gate_mode": _clean(real_row.get("evidence_gate_mode") or real_gate.get("evidence_gate_mode") or real_rag_report.get("evidence_gate_mode") or "off"),
                "answer_gate_decision": _clean(real_row.get("answer_gate_decision") or real_gate.get("answer_gate_decision") or "not_comparable"),
                "answer_modified_by_gate": bool(real_row.get("answer_modified_by_gate") or real_gate.get("answer_modified_by_gate")),
                "original_generated_answer_hash": _clean(real_row.get("original_generated_answer_hash") or real_gate.get("original_generated_answer_hash")),
                "gated_answer_hash": _clean(real_row.get("gated_answer_hash") or real_gate.get("gated_answer_hash")),
                "abstention_reason": _clean(real_row.get("abstention_reason") or real_gate.get("abstention_reason")),
                "would_block_unsupported_answer": bool(
                    real_row.get("would_block_unsupported_answer") or real_gate.get("would_block_unsupported_answer")
                ),
                "unsupported_answer_blocked": bool(real_row.get("unsupported_answer_blocked") or real_gate.get("unsupported_answer_blocked")),
                "retrieval_loop_triggered": bool(real_row.get("retrieval_loop_triggered") or real_gate.get("retrieval_loop_triggered")),
                "gate_uses_expected_fields": bool(real_row.get("gate_uses_expected_fields") or real_gate.get("gate_uses_expected_fields")),
                "gate_uses_gold_fields": bool(real_row.get("gate_uses_gold_fields") or real_gate.get("gate_uses_gold_fields")),
                "gate_uses_legacy_fields": bool(real_row.get("gate_uses_legacy_fields") or real_gate.get("gate_uses_legacy_fields")),
                "expected_answer_match_before_gate": (
                    real_row.get("expected_answer_match_before_gate")
                    if "expected_answer_match_before_gate" in real_row
                    else real_matches_expected_before_gate
                ),
                "expected_answer_match_after_gate": (
                    real_row.get("expected_answer_match_after_gate")
                    if "expected_answer_match_after_gate" in real_row
                    else real_matches_expected
                ),
                "expected_evidence_match_before_gate": (
                    real_row.get("expected_evidence_match_before_gate")
                    if "expected_evidence_match_before_gate" in real_row
                    else bool(real_support["expected_evidence_hit"])
                ),
                "expected_evidence_match_after_gate": (
                    real_row.get("expected_evidence_match_after_gate")
                    if "expected_evidence_match_after_gate" in real_row
                    else bool(real_support["expected_evidence_hit"])
                ),
                "legacy_real_answer_delta_before_gate": answer_delta_before_gate,
                "legacy_real_answer_delta_after_gate": answer_delta,
                "real_rag_supported_before_gate": (
                    real_row.get("real_rag_supported_before_gate")
                    if "real_rag_supported_before_gate" in real_row
                    else bool(real_gate.get("evidence_package_status") == "sufficient" and not abstains(real_answer_before_gate))
                ),
                "real_rag_supported_after_gate": bool(real_support["supported"] and not abstains(real_answer)),
                "e2e_success_after_gate_provisional": (
                    real_row.get("e2e_success_after_gate_provisional")
                    if "e2e_success_after_gate_provisional" in real_row
                    else bool(real_matches_expected and real_support["supported"] and not abstains(real_answer))
                ),
                "abstention_correctness_diagnostic_or_strict_when_labels_available": (
                    real_row.get("abstention_correctness_diagnostic_or_strict_when_labels_available")
                    if "abstention_correctness_diagnostic_or_strict_when_labels_available" in real_row
                    else (
                        abstains(real_answer)
                        if item.answerability == "unanswerable"
                        else (not abstains(real_answer) if item.answerability == "answerable" else "diagnostic_only_unknown_answerability")
                    )
                ),
                "candidate_generation_input_policy": "query_text_only",
                "legacy_baseline_replayed_not_executed": True,
            }
        )
    counts = Counter(row["answer_delta_category"] for row in rows)
    evidence_package_counts = Counter(row["evidence_package_status"] for row in rows)
    evidence_gate_summary = (
        real_rag_report.get("evidence_gate")
        if isinstance(real_rag_report.get("evidence_gate"), Mapping)
        else {}
    )
    comparable_count = len(rows) - sum(1 for row in rows if _clean(row.get("answer_delta_category")).startswith("not_comparable"))
    report = {
        "schema_version": QUALITY_GATE_REPORT_SCHEMA_VERSION,
        "generated_at": generated_at or utc_now_iso(),
        "non_production": True,
        "quality_gate_scope": "legacy_free_real_rag_source_native_parity_nonprod",
        "existing_gold_set_path": Path(existing_gold_set_path).as_posix(),
        "gold_set_item_count": len(gold_items),
        "gold_set_schema_version": _clean(real_rag_report.get("gold_set_schema_version") or legacy_baseline_report.get("gold_set_schema_version")),
        "gold_set_selection_rationale": "existing actual-RAG text-gold dataset reused from the requested dataset/latest actual-RAG coverage; no new gold rows created",
        "gold_mutation": False,
        "evidence_gate_mode": _clean(evidence_gate_summary.get("evidence_gate_mode") or real_rag_report.get("evidence_gate_mode") or "off"),
        "validator_version": _clean(evidence_gate_summary.get("validator_version") or real_rag_report.get("validator_version")),
        "legacy_baseline_path": Path(legacy_baseline_path).as_posix(),
        "legacy_baseline_run_id": _clean(legacy_baseline_report.get("run_id")),
        "legacy_baseline_item_count": len(legacy_items),
        "legacy_baseline_replayed_not_executed": True,
        "real_rag_report_path": Path(real_rag_report_path).as_posix(),
        "real_rag_run_id": _clean(real_rag_report.get("run_id")),
        "real_rag_selected_surface": _clean((real_rag_report.get("retrieval_surface") or {}).get("selected")) if isinstance(real_rag_report.get("retrieval_surface"), Mapping) else "",
        "selected_surface": "source_native",
        "source_native_units_only": bool(guardrail_status["source_native_units_only"]),
        "candidate_generation_input_policy": "query_text_only",
        "item_count": len(rows),
        "comparable_item_count": comparable_count,
        "exact_same_answer_count": sum(1 for row in rows if row["answer_exact_same"]),
        "normalized_same_answer_count": sum(1 for row in rows if row["answer_normalized_same"]),
        "equivalent_answer_count": sum(1 for row in rows if row["answer_equivalent_deterministic"]),
        "same_answer_same_support_count": counts.get("same_answer_same_support", 0),
        "same_answer_different_support_count": counts.get("same_answer_different_support", 0),
        "legacy_correct_real_wrong_count": counts.get("legacy_correct_real_wrong", 0),
        "legacy_wrong_real_correct_count": counts.get("legacy_wrong_real_correct", 0),
        "both_correct_count": sum(
            1 for row in rows if row["legacy_matches_expected"] and row["real_rag_matches_expected"]
        ),
        "both_wrong_count": sum(
            1 for row in rows if not row["legacy_matches_expected"] and not row["real_rag_matches_expected"]
        ),
        "unsupported_same_answer_count": sum(1 for row in rows if row["unsupported_same_answer"]),
        "real_rag_supported_count": sum(1 for row in rows if row["real_rag_supported"]),
        "legacy_supported_count": sum(1 for row in rows if row["legacy_supported"]),
        "not_comparable_count": len(rows) - comparable_count,
        "not_comparable_reasons": dict(sorted(not_comparable_reasons.items())),
        "answer_delta_category_counts": dict(sorted(counts.items())),
        "evidence_package_status_counts": dict(sorted(evidence_package_counts.items())),
        "sufficient_evidence_package_count": int(evidence_gate_summary.get("sufficient_evidence_package_count") or evidence_package_counts.get("sufficient", 0)),
        "insufficient_evidence_package_count": int(evidence_gate_summary.get("insufficient_evidence_package_count") or evidence_package_counts.get("insufficient", 0)),
        "conflicting_evidence_package_count": int(evidence_gate_summary.get("conflicting_evidence_package_count") or evidence_package_counts.get("conflicting", 0)),
        "unresolved_evidence_package_count": int(evidence_gate_summary.get("unresolved_evidence_package_count") or evidence_package_counts.get("unresolved", 0)),
        "allowed_answer_count": int(evidence_gate_summary.get("allowed_answer_count") or 0),
        "abstained_count": int(evidence_gate_summary.get("abstained_count") or 0),
        "unsupported_answer_blocked_count": int(evidence_gate_summary.get("unsupported_answer_blocked_count") or 0),
        "would_abstain_count": int(evidence_gate_summary.get("would_abstain_count") or 0),
        "would_block_unsupported_answer_count": int(evidence_gate_summary.get("would_block_unsupported_answer_count") or 0),
        "citation_supported_count": int(evidence_gate_summary.get("citation_supported_count") or 0),
        "citation_retrieved_context_only_diagnostic_count": int(evidence_gate_summary.get("citation_retrieved_context_only_diagnostic_count") or 0),
        "citation_wrong_target_count": int(evidence_gate_summary.get("citation_wrong_target_count") or 0),
        "citation_missing_target_count": int(evidence_gate_summary.get("citation_missing_target_count") or 0),
        "citation_unsupported_text_count": int(evidence_gate_summary.get("citation_unsupported_text_count") or 0),
        "unsupported_answer_rate_before_gate": evidence_gate_summary.get("unsupported_answer_rate_before_gate"),
        "unsupported_answer_rate_after_gate": evidence_gate_summary.get("unsupported_answer_rate_after_gate"),
        "insufficient_evidence_abstained_count": int(evidence_gate_summary.get("insufficient_evidence_abstained_count") or 0),
        "sufficient_evidence_allowed_count": int(evidence_gate_summary.get("sufficient_evidence_allowed_count") or 0),
        "sufficient_evidence_over_abstain_count": int(evidence_gate_summary.get("sufficient_evidence_over_abstain_count") or 0),
        "guardrail_status": guardrail_status,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "legacy_outputs_used_for_candidate_generation": False,
            "searchunit_searchview_used_in_real_rag_lane": False,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
            "official_metric": False,
            "protected_namespaces_touched": [],
        },
        "diagnostic_critic_summary": {
            "critic_result_tier": "diagnostic",
            "retrieval_loop_triggered": False,
            "answer_supported_by_evidence_count": sum(1 for row in rows if row["diagnostic_critic"]["answer_supported_by_evidence"]),
            "citation_supported_by_evidence_count": sum(1 for row in rows if row["diagnostic_critic"]["citation_supported_by_evidence"]),
            "citation_points_to_expected_or_resolved_evidence_count": sum(
                1 for row in rows if row["citation_points_to_expected_or_resolved_evidence"]
            ),
            "citation_points_to_retrieved_context_diagnostic_only_count": sum(
                1 for row in rows if row["citation_points_to_retrieved_context_diagnostic_only"]
            ),
            "evidence_sufficient_count": sum(1 for row in rows if row["diagnostic_critic"]["evidence_sufficient"]),
            "needs_more_retrieval_count": sum(1 for row in rows if row["diagnostic_critic"]["needs_more_retrieval"]),
            "should_abstain_count": sum(1 for row in rows if row["diagnostic_critic"]["should_abstain"]),
        },
    }
    return report, rows


def resolve_quality_gate_baseline_report(
    quality_gate_baseline: Path | str,
    *,
    dataset_path: Path | str,
    gold_items: Sequence[EvalItem] | None = None,
    report_root: Path | str = REPORT_ROOT,
) -> tuple[dict[str, Any], Path]:
    target = _clean(quality_gate_baseline)
    if not target:
        raise DatasetSchemaError("quality gate baseline path is required")
    if target != "auto":
        path = Path(target)
        if not path.exists():
            raise DatasetSchemaError(f"quality gate baseline does not exist: {target}")
        return _load_summary_from_pointer_or_path(path), path

    dataset_value = _report_path_value(dataset_path)
    target_query_ids = {item.id for item in gold_items or []}
    root = Path(report_root)
    candidates: list[tuple[int, int, str, str, Path]] = []
    for path in root.glob("*/report.json"):
        try:
            payload = _read_json_file(path)
        except Exception:
            continue
        if _clean(payload.get("dataset_path")) != dataset_value:
            continue
        config = payload.get("index_retrieval_config") if isinstance(payload.get("index_retrieval_config"), Mapping) else {}
        retrieval_surface = payload.get("retrieval_surface") if isinstance(payload.get("retrieval_surface"), Mapping) else {}
        adapter = json.dumps(config, ensure_ascii=False, sort_keys=True).casefold()
        selected_surface = _clean(retrieval_surface.get("selected")).casefold()
        score = 0
        if "searchunit" in adapter or "searchview" in adapter:
            score += 100
        if not selected_surface:
            score += 50
        if selected_surface in {"searchunit_searchview", "searchunit-searchview"}:
            score += 50
        if selected_surface == "source_native":
            score -= 25
        if "single_vector_final" in path.as_posix():
            score += 10
        item_count = int(payload.get("total_item_count") or len(_as_list(payload.get("items"))) or 0)
        if item_count > 0:
            score += 1
        coverage_score = 0
        if target_query_ids:
            candidate_query_ids = {
                _query_id(row)
                for row in _as_list(payload.get("items"))
                if isinstance(row, Mapping) and _query_id(row)
            }
            if candidate_query_ids == target_query_ids:
                coverage_score = 1000
            elif len(candidate_query_ids & target_query_ids) == len(target_query_ids):
                coverage_score = 500
            elif item_count == len(target_query_ids):
                coverage_score = 100
        if score > 0:
            candidates.append((coverage_score, score, _clean(payload.get("run_id")), path.as_posix(), path))
    if not candidates:
        raise DatasetSchemaError(f"quality gate baseline auto discovery found no same-dataset legacy report for {dataset_value}")
    _coverage, _score, _run_id, _path_value, selected = sorted(
        candidates,
        key=lambda row: (row[0], row[1], row[2], row[3]),
        reverse=True,
    )[0]
    return _load_summary_from_pointer_or_path(selected), selected


def write_legacy_real_rag_quality_gate_artifacts(
    *,
    output_dir: Path | str,
    gold_items: Sequence[EvalItem],
    existing_gold_set_path: Path | str,
    legacy_baseline_report: Mapping[str, Any],
    legacy_baseline_path: Path | str,
    real_rag_report: Mapping[str, Any],
    real_rag_report_path: Path | str,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    output = Path(output_dir)
    report, rows = build_legacy_real_rag_quality_gate_report(
        gold_items=gold_items,
        existing_gold_set_path=existing_gold_set_path,
        legacy_baseline_report=legacy_baseline_report,
        legacy_baseline_path=legacy_baseline_path,
        real_rag_report=real_rag_report,
        real_rag_report_path=real_rag_report_path,
        generated_at=generated_at,
    )
    report_path = output / "legacy_real_rag_quality_gate_report.json"
    items_path = output / "legacy_real_rag_quality_gate_items.jsonl"
    report["artifact_paths"] = {
        "legacy_real_rag_quality_gate_report_json": report_path.as_posix(),
        "legacy_real_rag_quality_gate_items_jsonl": items_path.as_posix(),
    }
    write_json(report_path, report)
    write_jsonl(items_path, rows)
    return report, rows, report["artifact_paths"]


WEAVIATE_ROUTE_AB_REPORT_FILENAME = "route_selected_hybrid_evidence_store_ab_report.json"
WEAVIATE_ROUTE_AB_ITEMS_FILENAME = "route_selected_hybrid_evidence_store_ab_items.jsonl"
WEAVIATE_ROUTE_AB_MODE_ALIASES = {
    "text": "text_only",
    "text_only": "text_only",
    "text-only": "text_only",
    "mixed": "mixed_pool",
    "mixed_pool": "mixed_pool",
    "mixed-pool": "mixed_pool",
    "routed": "route_selected",
    "route_selected": "route_selected",
    "route-selected": "route_selected",
}


def _parse_weaviate_route_ab_modes(value: str | Sequence[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = [part.strip() for part in value.split(",")]
    else:
        raw_values = [str(part).strip() for part in value]
    modes: list[str] = []
    for raw in raw_values:
        if not raw:
            continue
        normalized = WEAVIATE_ROUTE_AB_MODE_ALIASES.get(raw.replace("_", "-").casefold())
        if normalized is None:
            normalized = WEAVIATE_ROUTE_AB_MODE_ALIASES.get(raw.replace("-", "_").casefold())
        if normalized is None:
            raise DatasetSchemaError(f"unsupported weaviate route A/B mode: {raw}")
        if normalized not in modes:
            modes.append(normalized)
    return modes


def _metric_score(summary: Mapping[str, Any], tier: str, name: str) -> Any:
    metrics = summary.get(tier)
    if not isinstance(metrics, Mapping):
        return None
    metric = metrics.get(name)
    if not isinstance(metric, Mapping):
        return None
    return metric.get("score")


def _metric_count(summary: Mapping[str, Any], tier: str, name: str, field: str) -> int | None:
    metrics = summary.get(tier)
    if not isinstance(metrics, Mapping):
        return None
    metric = metrics.get(name)
    if not isinstance(metric, Mapping):
        return None
    value = metric.get(field)
    return int(value) if isinstance(value, int) else None


def _retrieved_contexts(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(context) for context in row.get("retrieved_contexts") or [] if isinstance(context, Mapping)]


def _distribution(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        for context in _retrieved_contexts(row):
            value = _clean(context.get(field)) or "unknown"
            counter[value] += 1
    return dict(sorted(counter.items()))


def _duplicate_pressure(rows: Sequence[Mapping[str, Any]], field: str) -> tuple[int, int, float]:
    total = 0
    duplicates = 0
    for row in rows:
        seen: set[str] = set()
        for context in _retrieved_contexts(row):
            value = _clean(context.get(field))
            if not value:
                continue
            total += 1
            if value in seen:
                duplicates += 1
            seen.add(value)
    return duplicates, total, round(float(duplicates) / float(total), 6) if total else 0.0


def _planned_filter_for_row(row: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    plan = row.get("weaviate_route_plan") if isinstance(row.get("weaviate_route_plan"), Mapping) else None
    if (
        not plan
        or _clean(plan.get("selected_route")) in {"full_index", "mixed_pool"}
        or not plan.get("selected_source_family_filter")
    ):
        plan = plan_weaviate_retrieval_route(_clean(row.get("query")))
    return (
        [_clean(value) for value in plan.get("selected_source_family_filter") or [] if _clean(value)],
        [_clean(value) for value in plan.get("selected_granularity_filter") or [] if _clean(value)],
    )


def _wrong_route_counts(rows: Sequence[Mapping[str, Any]]) -> tuple[int, int, int]:
    wrong_family = 0
    wrong_granularity = 0
    pollution = 0
    for row in rows:
        family_filter, granularity_filter = _planned_filter_for_row(row)
        for context in _retrieved_contexts(row):
            source_family = _clean(context.get("source_family"))
            granularity = _clean(context.get("granularity"))
            if len(family_filter) == 1 and source_family and source_family != family_filter[0]:
                wrong_family += 1
                pollution += 1
            if granularity_filter and granularity and granularity not in set(granularity_filter):
                wrong_granularity += 1
    return wrong_family, wrong_granularity, pollution


def _normalize_audit_query_ids(value: str | Sequence[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = re.split(r"[,;\s]+", value)
    else:
        raw_values = []
        for entry in value:
            raw_values.extend(re.split(r"[,;\s]+", _clean(entry)))
    ids: list[str] = []
    for raw in raw_values:
        query_id = _clean(raw)
        if query_id and query_id not in ids:
            ids.append(query_id)
    return ids


def _dedupe_clean(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _clean(value)
        if text and text not in result:
            result.append(text)
    return result


def _corpus_coverage_target_anchors(item: EvalItem, explicit_anchors: Sequence[str] | None) -> list[str]:
    explicit = _dedupe_clean(explicit_anchors or [])
    if explicit:
        return explicit
    return []


def _anchor_hit_count(rows: Sequence[Mapping[str, Any]], anchors: Sequence[str]) -> int:
    normalized = [normalize_answer_text(anchor) for anchor in anchors if normalize_answer_text(anchor)]
    count = 0
    for row in rows:
        text = " ".join(
            _clean(value)
            for value in (
                row.get("title"),
                row.get("section"),
                _gate_row_text(row),
            )
            if _clean(value)
        )
        if _anchor_in_text(normalized, text):
            count += 1
    return count


def _query_collision_count(rows: Sequence[Mapping[str, Any]], query: str, anchors: Sequence[str]) -> int:
    query_anchors = sorted(_candidate_anchors(query))
    if not query_anchors:
        return 0
    collision_count = 0
    for row in rows:
        text = " ".join(
            _clean(value)
            for value in (
                row.get("title"),
                row.get("section"),
                _gate_row_text(row),
            )
            if _clean(value)
        )
        if _anchor_hit_count([row], anchors):
            continue
        if _anchor_in_text(query_anchors, text):
            collision_count += 1
    return collision_count


def _probe_context_summary(rows: Sequence[Mapping[str, Any]], *, query: str, anchors: Sequence[str]) -> dict[str, Any]:
    contexts = [dict(row) for row in rows if isinstance(row, Mapping)]
    hit_count = _anchor_hit_count(contexts, anchors)
    return {
        "available": True,
        "context_count": len(contexts),
        "target_anchor_hit": hit_count > 0,
        "target_anchor_hit_count": hit_count,
        "collision_count": _query_collision_count(contexts, query, anchors),
        "source_atom_ids": _dedupe_clean(
            _clean(row.get("source_atom_id")) for row in contexts if _clean(row.get("source_atom_id"))
        )[:5],
        "doc_ids": _dedupe_clean(_clean(row.get("doc_id")) for row in contexts if _clean(row.get("doc_id")))[:5],
        "granularities": sorted({_clean(row.get("granularity")) for row in contexts if _clean(row.get("granularity"))}),
        "retrieval_routes": sorted({_clean(row.get("retrieval_route")) for row in contexts if _clean(row.get("retrieval_route"))}),
    }


def _matched_audit_anchors(text: str, anchors: Sequence[str]) -> list[str]:
    matched: list[str] = []
    for anchor in anchors:
        normalized = normalize_answer_text(anchor)
        if normalized and _anchor_in_text([normalized], text):
            matched.append(anchor)
    return matched


def _source_registry_context_text(row: Mapping[str, Any]) -> str:
    raw_locator = row.get("raw_locator") if isinstance(row.get("raw_locator"), Mapping) else {}
    canonical = (
        row.get("canonical_citation_payload")
        if isinstance(row.get("canonical_citation_payload"), Mapping)
        else {}
    )
    canonical_locator = (
        canonical.get("text_locator")
        if isinstance(canonical.get("text_locator"), Mapping)
        else {}
    )
    return " ".join(
        _clean(value)
        for value in (
            row.get("normalized_text_or_value_snapshot"),
            row.get("source_atom_id"),
            row.get("document_id"),
            row.get("source_identity"),
            raw_locator.get("title"),
            raw_locator.get("chunk_id"),
            raw_locator.get("search_unit_id"),
            canonical_locator.get("title"),
            canonical_locator.get("chunk_id"),
            canonical_locator.get("search_unit_id"),
        )
        if _clean(value)
    )


def _source_registry_audit_presence(
    *,
    source_registry_path: Path | str | None,
    query_id: str,
    anchors: Sequence[str],
    max_rows: int = 8,
) -> dict[str, Any]:
    path = Path(source_registry_path) if source_registry_path else SOURCE_NATIVE_SOURCE_REGISTRY_PATH
    result: dict[str, Any] = {
        "available": False,
        "report_only_diagnostic": True,
        "path": str(path),
        "target_anchor_hit": False,
        "target_anchor_hit_count": 0,
        "strong_target_anchor_hit_count": 0,
        "query_id_match_count": 0,
        "matching_source_atom_count": 0,
        "source_atom_ids": [],
        "content_hashes": [],
        "doc_ids": [],
        "rows": [],
    }
    if not path.exists():
        result["unavailable_reason"] = "source_registry_path_missing"
        return result

    rows: list[dict[str, Any]] = []
    source_atom_ids: list[str] = []
    content_hashes: list[str] = []
    doc_ids: list[str] = []
    target_hit_count = 0
    strong_hit_count = 0
    query_id_match_count = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, Mapping):
                    continue
                parent = row.get("parent_pointers") if isinstance(row.get("parent_pointers"), Mapping) else {}
                raw_locator = row.get("raw_locator") if isinstance(row.get("raw_locator"), Mapping) else {}
                source_unit_id = _clean(parent.get("source_unit_id") or row.get("source_unit_id"))
                search_unit_id = _clean(parent.get("search_unit_id") or raw_locator.get("search_unit_id"))
                query_id_match = query_id in {source_unit_id, search_unit_id}
                matched_anchors = _matched_audit_anchors(_source_registry_context_text(row), anchors)
                if not query_id_match and not matched_anchors:
                    continue
                target_hit = bool(matched_anchors)
                target_hit_count += int(target_hit)
                strong_hit_count += int(len(matched_anchors) >= 2)
                query_id_match_count += int(query_id_match)
                source_atom_id = _clean(row.get("source_atom_id"))
                content_hash = _clean(row.get("content_hash"))
                doc_id = _clean(row.get("document_id") or raw_locator.get("document_id") or raw_locator.get("doc_id"))
                if source_atom_id:
                    source_atom_ids.append(source_atom_id)
                if content_hash:
                    content_hashes.append(content_hash)
                if doc_id:
                    doc_ids.append(doc_id)
                if len(rows) < max_rows:
                    rows.append(
                        {
                            "line_number": line_number,
                            "source_atom_id": source_atom_id,
                            "document_id": doc_id,
                            "chunk_id": _clean(raw_locator.get("chunk_id")),
                            "search_unit_id": search_unit_id,
                            "source_unit_id": source_unit_id,
                            "content_hash": content_hash,
                            "source_family": _clean(row.get("source_family")),
                            "matched_anchors": matched_anchors,
                            "matched_anchor_count": len(matched_anchors),
                            "query_id_match": query_id_match,
                            "official_denominator_overlap": bool(row.get("official_denominator_overlap")),
                        }
                    )
    except OSError as exc:
        result["unavailable_reason"] = f"{type(exc).__name__}:{exc}"
        return result

    result.update(
        {
            "available": True,
            "target_anchor_hit": target_hit_count > 0,
            "target_anchor_hit_count": target_hit_count,
            "strong_target_anchor_hit_count": strong_hit_count,
            "query_id_match_count": query_id_match_count,
            "matching_source_atom_count": len(_dedupe_clean(source_atom_ids)),
            "source_atom_ids": _dedupe_clean(source_atom_ids)[:max_rows],
            "content_hashes": _dedupe_clean(content_hashes)[:max_rows],
            "doc_ids": _dedupe_clean(doc_ids)[:max_rows],
            "rows": rows,
        }
    )
    return result


def _index_checkpoint_audit_presence(
    *,
    index_checkpoint_path: Path | str | None,
    index_manifest_path: Path | str | None,
    source_atom_ids: Sequence[str],
) -> dict[str, Any]:
    manifest_path_text = _clean(index_manifest_path)
    checkpoint_path = Path(index_checkpoint_path) if index_checkpoint_path else None
    if checkpoint_path is None and manifest_path_text:
        checkpoint_path = Path(manifest_path_text).with_name("index_checkpoint.json")
    result: dict[str, Any] = {
        "available": False,
        "report_only_diagnostic": True,
        "index_manifest_path": manifest_path_text,
        "index_checkpoint_path": str(checkpoint_path) if checkpoint_path else "",
        "target_source_atom_indexed": False,
        "source_atom_id_match_count": 0,
        "indexed_source_atom_ids": [],
    }
    if checkpoint_path is None:
        result["unavailable_reason"] = "index_checkpoint_path_unavailable"
        return result
    if not checkpoint_path.exists():
        result["unavailable_reason"] = "index_checkpoint_path_missing"
        return result
    ids = _dedupe_clean(source_atom_ids)
    if not ids:
        result["available"] = True
        result["unavailable_reason"] = "source_registry_source_atom_ids_unavailable"
        return result
    try:
        raw = checkpoint_path.read_text(encoding="utf-8")
    except OSError as exc:
        result["unavailable_reason"] = f"{type(exc).__name__}:{exc}"
        return result
    matched = [source_atom_id for source_atom_id in ids if source_atom_id in raw]
    result.update(
        {
            "available": True,
            "target_source_atom_indexed": bool(matched),
            "source_atom_id_match_count": len(matched),
            "indexed_source_atom_ids": matched[:8],
        }
    )
    return result


def _probe_unavailable(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "unavailable_reason": reason,
        "context_count": 0,
        "target_anchor_hit": False,
        "target_anchor_hit_count": 0,
        "collision_count": 0,
        "source_atom_ids": [],
        "doc_ids": [],
        "granularities": [],
        "retrieval_routes": [],
    }


def _run_corpus_coverage_probe(
    *,
    route_mode: str,
    lane_factory: Callable[[str], Any],
    item: EvalItem,
    audit_query: str,
    target_anchors: Sequence[str],
    top_k: int,
) -> dict[str, Any]:
    adapter = None
    try:
        adapter = lane_factory(route_mode)
        probe_item = replace(
            item,
            query=audit_query,
            expected_answer="",
            expected_answer_aliases=(),
            expected_evidence=(),
            source_row={},
        )
        output = adapter.run_item(probe_item, top_k=top_k)
        contexts = _retrieved_contexts(output)
        probe = _probe_context_summary(contexts, query=item.query, anchors=target_anchors)
        filter_policy = output.get("weaviate_filter_policy")
        if isinstance(filter_policy, Mapping):
            probe["weaviate_filter_policy"] = dict(filter_policy)
        route_plan = output.get("weaviate_route_plan")
        if isinstance(route_plan, Mapping):
            probe["weaviate_route_plan"] = dict(route_plan)
        probe["audit_query_sha256"] = _sha256_text(audit_query)
        probe["route_mode"] = route_mode
        return probe
    except Exception as exc:
        return _probe_unavailable(f"{type(exc).__name__}:{exc}")
    finally:
        close = getattr(adapter, "close", None)
        if callable(close):
            close()


def _classify_corpus_coverage_row(
    *,
    active_probe: Mapping[str, Any],
    full_index_probe: Mapping[str, Any],
    route_selected_probe: Mapping[str, Any],
) -> tuple[str, str, list[str], str]:
    active_hit = bool(active_probe.get("target_anchor_hit"))
    full_hit = bool(full_index_probe.get("target_anchor_hit"))
    routed_hit = bool(route_selected_probe.get("target_anchor_hit"))
    full_available = bool(full_index_probe.get("available"))
    route_available = bool(route_selected_probe.get("available"))
    collision_count = int(active_probe.get("collision_count") or 0)

    def with_collision(modes: Sequence[str]) -> list[str]:
        result = list(modes)
        if collision_count and "collision" not in result:
            result.append("collision")
        return result

    if active_hit:
        return "corpus_present", "corpus_present", [], "active retrieval already contains a target anchor"
    if full_hit and not routed_hit and route_available:
        return (
            "route_filter_failure",
            "corpus_present",
            with_collision(["route_filter_failure"]),
            "full-index target probe found the anchor while route-selected target probe did not",
        )
    if routed_hit:
        return (
            "tokenization_alias_failure",
            "corpus_present",
            with_collision(["tokenization_alias_failure"]),
            "route-selected target probe found the anchor but the main query path did not",
        )
    if full_available and not full_hit:
        if collision_count:
            return (
                "collision",
                "corpus_absent",
                ["collision", "corpus_absent"],
                "target anchor was absent in full-index probe while active retrieval had query-anchor collisions",
            )
        return "corpus_absent", "corpus_absent", ["corpus_absent"], "target anchor was absent in full-index probe"
    if collision_count:
        return "collision", "unknown", ["collision"], "audit probes were unavailable but active retrieval had query-anchor collisions"
    return "corpus_absent", "unknown", ["corpus_absent"], "audit probes were unavailable and active retrieval had no target anchor"


def build_corpus_coverage_audit_report(
    *,
    items: Sequence[EvalItem],
    rows: Sequence[Mapping[str, Any]],
    query_ids: str | Sequence[str] | None,
    target_anchors: Sequence[str] | None = None,
    top_k: int = 10,
    lane_factory: Callable[[str], Any] | None = None,
    source_registry_path: Path | str | None = SOURCE_NATIVE_SOURCE_REGISTRY_PATH,
    active_index_checkpoint_path: Path | str | None = None,
    active_index_manifest_path: Path | str | None = None,
) -> dict[str, Any]:
    target_ids = _normalize_audit_query_ids(query_ids)
    if not target_ids:
        return {
            "enabled": False,
            "schema_version": CORPUS_COVERAGE_AUDIT_SCHEMA_VERSION,
            "report_only_diagnostic": True,
            "rows": [],
            "classification_counts": {},
            "gold_or_qrels_mutation": False,
            "official_metric_input_rows": 0,
        }

    item_by_id = {item.id: item for item in items}
    row_by_id = {_query_id(row): dict(row) for row in rows if _query_id(row)}
    audit_rows: list[dict[str, Any]] = []
    for query_id in target_ids:
        item = item_by_id.get(query_id)
        if item is None:
            audit_rows.append(
                {
                    "query_id": query_id,
                    "primary_classification": "corpus_absent",
                    "corpus_presence": "unknown",
                    "failure_modes": ["corpus_absent"],
                    "classification_reason": "query_id not present in loaded dataset",
                    "target_anchors": _dedupe_clean(target_anchors or []),
                    "audit_uses_expected_fields_for_candidate_generation": False,
                    "audit_uses_gold_fields_for_candidate_generation": False,
                }
            )
            continue
        anchors = _corpus_coverage_target_anchors(item, target_anchors)
        if not anchors:
            audit_rows.append(
                {
                    "query_id": query_id,
                    "query": item.query,
                    "target_anchors": [],
                    "target_anchor_count": 0,
                    "primary_classification": "skipped_missing_explicit_target_anchors",
                    "corpus_presence": "unknown",
                    "failure_modes": ["skipped_missing_explicit_target_anchors"],
                    "classification_reason": "explicit target anchors are required for corpus coverage probes",
                    "audit_skipped_reason": "explicit_target_anchors_required",
                    "active_retrieval_probe": _probe_unavailable("explicit_target_anchors_required"),
                    "source_registry_presence": _probe_unavailable("explicit_target_anchors_required"),
                    "active_index_presence": _probe_unavailable("explicit_target_anchors_required"),
                    "full_index_probe": _probe_unavailable("explicit_target_anchors_required"),
                    "route_selected_probe": _probe_unavailable("explicit_target_anchors_required"),
                    "corpus_present": False,
                    "corpus_absent": False,
                    "collision": False,
                    "tokenization_or_alias_failure": False,
                    "route_selected_filter_failure": False,
                    "audit_query_sha256": "",
                    "audit_query_policy": "explicit_target_anchors_required_no_expected_or_literal_defaults",
                    "audit_uses_expected_fields_for_candidate_generation": False,
                    "audit_uses_gold_fields_for_candidate_generation": False,
                    "audit_uses_qrels_for_candidate_generation": False,
                    "audit_uses_labels_for_candidate_generation": False,
                    "gold_or_qrels_mutation": False,
                    "official_metric_input_rows": 0,
                }
            )
            continue
        active_row = row_by_id.get(query_id, {})
        active_contexts = _retrieved_contexts(active_row)
        active_probe = _probe_context_summary(active_contexts, query=item.query, anchors=anchors)
        source_registry_presence = _source_registry_audit_presence(
            source_registry_path=source_registry_path,
            query_id=query_id,
            anchors=anchors,
        )
        active_index_presence = _index_checkpoint_audit_presence(
            index_checkpoint_path=active_index_checkpoint_path,
            index_manifest_path=active_index_manifest_path,
            source_atom_ids=source_registry_presence.get("source_atom_ids") or [],
        )
        audit_query = " ".join([item.query, *anchors]).strip()
        if lane_factory is None:
            full_index_probe = _probe_unavailable("weaviate_lane_factory_unavailable")
            route_selected_probe = _probe_unavailable("weaviate_lane_factory_unavailable")
        else:
            full_index_probe = _run_corpus_coverage_probe(
                route_mode="full_index",
                lane_factory=lane_factory,
                item=item,
                audit_query=audit_query,
                target_anchors=anchors,
                top_k=top_k,
            )
            route_selected_probe = _run_corpus_coverage_probe(
                route_mode="route_selected",
                lane_factory=lane_factory,
                item=item,
                audit_query=audit_query,
                target_anchors=anchors,
                top_k=top_k,
            )
        primary, presence, failure_modes, reason = _classify_corpus_coverage_row(
            active_probe=active_probe,
            full_index_probe=full_index_probe,
            route_selected_probe=route_selected_probe,
        )
        audit_rows.append(
            {
                "query_id": query_id,
                "query": item.query,
                "target_anchors": anchors,
                "target_anchor_count": len(anchors),
                "primary_classification": primary,
                "corpus_presence": presence,
                "failure_modes": failure_modes,
                "classification_reason": reason,
                "active_retrieval_probe": active_probe,
                "source_registry_presence": source_registry_presence,
                "active_index_presence": active_index_presence,
                "full_index_probe": full_index_probe,
                "route_selected_probe": route_selected_probe,
                "corpus_present": presence == "corpus_present",
                "corpus_absent": presence == "corpus_absent",
                "collision": "collision" in failure_modes,
                "tokenization_or_alias_failure": "tokenization_alias_failure" in failure_modes,
                "route_selected_filter_failure": "route_filter_failure" in failure_modes,
                "audit_query_sha256": _sha256_text(audit_query),
                "audit_query_policy": "query_text_plus_explicit_target_anchors_report_only_after_main_run",
                "audit_uses_expected_fields_for_candidate_generation": False,
                "audit_uses_gold_fields_for_candidate_generation": False,
                "audit_uses_qrels_for_candidate_generation": False,
                "audit_uses_labels_for_candidate_generation": False,
                "gold_or_qrels_mutation": False,
                "official_metric_input_rows": 0,
            }
        )

    counts = Counter(_clean(row.get("primary_classification")) or "unknown" for row in audit_rows)
    return {
        "enabled": True,
        "schema_version": CORPUS_COVERAGE_AUDIT_SCHEMA_VERSION,
        "report_only_diagnostic": True,
        "scope": "target_query_corpus_coverage_failure_mode_audit",
        "target_query_ids": target_ids,
        "rows": audit_rows,
        "row_count": len(audit_rows),
        "classification_counts": dict(sorted(counts.items())),
        "candidate_generation_input_policy": "main_eval_unchanged; audit probes are explicit report-only post-main-run diagnostics",
        "audit_probe_policy": "target_anchor_queries_are_not_answer_generation_not_metric_inputs_not_registry_mutation",
        "gold_or_qrels_mutation": False,
        "source_registry_mutation": False,
        "active_index_mutation": False,
        "label_or_denominator_mutation": False,
        "uses_expected_fields_for_candidate_generation": False,
        "uses_gold_fields_for_candidate_generation": False,
        "uses_qrels_for_candidate_generation": False,
        "uses_labels_for_candidate_generation": False,
        "official_metric_input_rows": 0,
        "official_metric": False,
        "promotion_evidence": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "artifact_sidecar_written": False,
    }


def _row_metric_passed(row: Mapping[str, Any], metric_name: str) -> bool | None:
    metrics = row.get("metric_results") if isinstance(row.get("metric_results"), Mapping) else {}
    value = metrics.get(metric_name)
    if isinstance(value, bool):
        return value
    if isinstance(value, Mapping) and isinstance(value.get("passed"), bool):
        return bool(value.get("passed"))
    return None


def _text_route_degradation_count(
    reference_rows: Sequence[Sequence[Mapping[str, Any]]],
    candidate_rows: Sequence[Mapping[str, Any]],
    *,
    metric_name: str = "weak_evidence_match_recall@10",
) -> int:
    reference_pass_by_id: dict[str, bool] = {}
    for rows in reference_rows:
        for row in rows:
            row_id = _clean(row.get("id"))
            if not row_id:
                continue
            reference_pass_by_id[row_id] = reference_pass_by_id.get(row_id, False) or (
                _row_metric_passed(row, metric_name) is True
            )
    degradation = 0
    for row in candidate_rows:
        row_id = _clean(row.get("id"))
        if row_id and reference_pass_by_id.get(row_id) and _row_metric_passed(row, metric_name) is not True:
            degradation += 1
    return degradation


def _metric_score_not_lower(candidate: Any, references: Sequence[Any]) -> bool:
    if not isinstance(candidate, (int, float)):
        return True
    for reference in references:
        if isinstance(reference, (int, float)) and float(candidate) + 1e-9 < float(reference):
            return False
    return True


def _guardrail_status_for_weaviate_lane(summary: Mapping[str, Any]) -> dict[str, Any]:
    required_false = {
        "python_local_corpus_scan_used_for_candidate_generation": False,
        "source_native_layered_retrieval_used_for_candidate_generation": False,
        "diagnostic_hash_vector_used": False,
        "faiss_used_for_active_retrieval": False,
        "searchunit_searchview_used_as_candidate_surface": False,
        "gold_or_qrels_mutation": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
    }
    violations = [
        key
        for key, expected in required_false.items()
        if summary.get(key) != expected
    ]
    external = summary.get("external_vector_db") if isinstance(summary.get("external_vector_db"), Mapping) else {}
    if summary.get("active_retrieval_service_boundary") != "weaviate":
        violations.append("active_retrieval_service_boundary")
    if external.get("invoked") is not True:
        violations.append("external_vector_db.invoked")
    return {
        "valid": not violations,
        "violations": violations,
        "active_retrieval_service_boundary": summary.get("active_retrieval_service_boundary"),
        "external_vector_db_invoked": external.get("invoked"),
        **required_false,
    }


def _weaviate_ab_lane_summary(
    *,
    lane_id: str,
    route_mode: str,
    dataset_source: str,
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    diagnostics = summary.get("diagnostic_metrics") if isinstance(summary.get("diagnostic_metrics"), Mapping) else {}
    backend = summary.get("backend_comparison") if isinstance(summary.get("backend_comparison"), Mapping) else {}
    gate = summary.get("legacy_real_rag_quality_gate") if isinstance(summary.get("legacy_real_rag_quality_gate"), Mapping) else {}
    evidence_status = gate.get("evidence_package_status_counts") if isinstance(gate.get("evidence_package_status_counts"), Mapping) else {}
    wrong_family, wrong_granularity, pollution = _wrong_route_counts(rows)
    duplicate_count, duplicate_total, duplicate_rate = _duplicate_pressure(rows, "text_sha256")
    same_doc_duplicate_count, same_doc_total, same_doc_duplicate_rate = _duplicate_pressure(rows, "doc_id")
    filter_policy = summary.get("weaviate_filter_policy") if isinstance(summary.get("weaviate_filter_policy"), Mapping) else {}
    route_planner_version = ""
    for row in rows:
        plan = row.get("weaviate_route_plan") if isinstance(row.get("weaviate_route_plan"), Mapping) else {}
        if _clean(plan.get("route_planner_version")):
            route_planner_version = _clean(plan.get("route_planner_version"))
            break
    return {
        "lane_id": lane_id,
        "route_mode": route_mode,
        "dataset_source": dataset_source,
        "item_count": int(summary.get("total_item_count") or len(rows)),
        "active_retrieval_service_boundary": summary.get("active_retrieval_service_boundary"),
        "active_retrieval_backend": summary.get("active_retrieval_backend"),
        "collection": summary.get("collection") or summary.get("weaviate_collection_name"),
        "rollback_key": summary.get("rollback_key"),
        "fallback_used": bool(summary.get("fallback_used")),
        "fail_closed_on_unavailable": bool(summary.get("fail_closed_on_unavailable", True)),
        "external_vector_db": dict(summary.get("external_vector_db") or {}),
        "weaviate_filter_sent": bool(summary.get("weaviate_filter_sent")),
        "weaviate_filter_policy": dict(filter_policy),
        "weaviate_post_processing": dict(summary.get("weaviate_post_processing") or {})
        if isinstance(summary.get("weaviate_post_processing"), Mapping)
        else {},
        "base_filter_sent": bool(filter_policy.get("base_filter_sent")),
        "route_filter_requested": bool(filter_policy.get("route_filter_requested")),
        "route_filter_sent": bool(filter_policy.get("route_filter_sent")),
        "source_family_filter_sent": bool(filter_policy.get("source_family_filter_sent")),
        "granularity_filter_sent": bool(filter_policy.get("granularity_filter_sent")),
        "retrieval_route_filter_sent": bool(filter_policy.get("retrieval_route_filter_sent")),
        "route_planner_version": route_planner_version,
        "mixed_pool_diagnostic_only": lane_id == "lane_c_mixed_pool",
        "retrieval_empty_rate": diagnostics.get("retrieval_empty_rate"),
        "weak_evidence_match_recall@10": _metric_score(summary, "provisional_metrics", "weak_evidence_match_recall@10"),
        "weak_evidence_match_recall@10_numerator": _metric_count(summary, "provisional_metrics", "weak_evidence_match_recall@10", "numerator"),
        "weak_evidence_match_recall@10_denominator": _metric_count(summary, "provisional_metrics", "weak_evidence_match_recall@10", "denominator"),
        "target_span_present_but_not_retrieved_count": diagnostics.get("source_native_target_span_present_but_not_retrieved_count"),
        "evidence_package_sufficient_count": evidence_status.get("sufficient"),
        "evidence_package_insufficient_count": evidence_status.get("insufficient"),
        "wrong_source_family_count": wrong_family,
        "wrong_granularity_count": wrong_granularity,
        "duplicate_result_count": duplicate_count,
        "duplicate_result_total": duplicate_total,
        "duplicate_result_rate": duplicate_rate,
        "same_doc_duplicate_count": same_doc_duplicate_count,
        "same_doc_duplicate_total": same_doc_total,
        "same_doc_duplicate_rate": same_doc_duplicate_rate,
        "mixed_pool_pollution_count": pollution,
        "text_route_degradation_count": 0,
        "vector_candidate_count_avg": backend.get("vector_candidate_count_avg"),
        "bm25_candidate_count_avg": backend.get("bm25_candidate_count_avg"),
        "hybrid_candidate_count_avg": backend.get("hybrid_candidate_count_avg"),
        "bm25_vector_overlap_avg": backend.get("bm25_vector_topk_overlap_avg"),
        "source_family_distribution": _distribution(rows, "source_family"),
        "granularity_distribution": _distribution(rows, "granularity"),
        "weaviate_query_latency_ms_p50": summary.get("weaviate_query_latency_ms_p50") or backend.get("hybrid_latency_ms_p50"),
        "weaviate_query_latency_ms_p95": summary.get("weaviate_query_latency_ms_p95") or backend.get("hybrid_latency_ms_p95"),
        "weaviate_query_count_per_item": summary.get("weaviate_query_count_per_item"),
        "weaviate_schema_version": summary.get("weaviate_schema_version"),
        "schema_version_source_atom": summary.get("schema_version_source_atom") or summary.get("weaviate_schema_version"),
        "index_object_count": summary.get("index_object_count") or summary.get("weaviate_indexed_object_count"),
        "vectorized_object_count": summary.get("vectorized_object_count") or summary.get("weaviate_indexed_object_count"),
        "metadata_only_object_count": int(summary.get("metadata_only_object_count") or 0),
        "vectorized_object_ratio": summary.get("vectorized_object_ratio") or (1.0 if summary.get("weaviate_indexed_object_count") else 0.0),
        "vectorized_by_granularity": dict(summary.get("vectorized_by_granularity") or {})
        if isinstance(summary.get("vectorized_by_granularity"), Mapping)
        else {},
        "metadata_only_by_granularity": dict(summary.get("metadata_only_by_granularity") or {})
        if isinstance(summary.get("metadata_only_by_granularity"), Mapping)
        else {},
        "metadata_only_by_source_family": dict(summary.get("metadata_only_by_source_family") or {})
        if isinstance(summary.get("metadata_only_by_source_family"), Mapping)
        else {},
        "current_index_vectorizes_all_source_atoms": bool(summary.get("current_index_vectorizes_all_source_atoms", True)),
        "index_time_metadata_only_supported": bool(summary.get("index_time_metadata_only_supported")),
        "schema_index_v2_rebuild_required_for_metadata_only_policy": bool(
            summary.get("schema_index_v2_rebuild_required_for_metadata_only_policy")
        ),
        "guardrail_status": _guardrail_status_for_weaviate_lane(summary),
    }


def _ab_item_rows(
    *,
    lane_id: str,
    rows: Sequence[Mapping[str, Any]],
    dataset_role: str = "text_regression",
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        contexts = _retrieved_contexts(row)
        result.append(
            {
                "lane_id": lane_id,
                "dataset_role": dataset_role,
                "id": _clean(row.get("id")),
                "query": _clean(row.get("query")),
                "source_track": _clean(row.get("source_track") or (row.get("source_row") or {}).get("track")),
                "weaviate_route_plan": dict(row.get("weaviate_route_plan") or {}),
                "weaviate_filter_policy": dict(row.get("weaviate_filter_policy") or {}),
                "weaviate_filter_sent": bool(row.get("weaviate_filter_sent")),
                "retrieved_context_count": len(contexts),
                "top_contexts": [
                    {
                        "rank": context.get("rank"),
                        "doc_id": _clean(context.get("doc_id")),
                        "chunk_id": _clean(context.get("chunk_id")),
                        "source_family": _clean(context.get("source_family")),
                        "granularity": _clean(context.get("granularity")),
                        "retrieval_route": _clean(context.get("retrieval_route")),
                        "text_sha256": _clean(context.get("text_sha256") or context.get("source_text_sha256")),
                    }
                    for context in contexts[:10]
                ],
                "failure_labels": list(row.get("failure_labels") or []),
                "canonical_failure_labels": list(row.get("canonical_failure_labels") or []),
                "metric_results": dict(row.get("metric_results") or {}),
                "post_filter_removed_count": int(row.get("post_filter_removed_count") or 0),
                "weaviate_post_processing": dict(row.get("weaviate_post_processing") or {})
                if isinstance(row.get("weaviate_post_processing"), Mapping)
                else {},
            }
        )
    return result


def _closed_lane_summary(
    *,
    lane_run_id: str,
    raw_outputs: Sequence[Mapping[str, Any]],
    scored_rows: Sequence[Mapping[str, Any]],
    adapter: Any,
    backend_comparison: Mapping[str, Any],
    active_path_report: Mapping[str, Any],
    external_vector_db: Mapping[str, Any],
) -> dict[str, Any]:
    retrieval_backend_report = (
        dict(adapter.retrieval_backend_report)
        if isinstance(getattr(adapter, "retrieval_backend_report", None), Mapping)
        else {}
    )
    return {
        **dict(active_path_report),
        "run_id": lane_run_id,
        "total_item_count": len(scored_rows),
        "items": list(scored_rows),
        "backend_comparison": dict(backend_comparison),
        "retrieval_backend": retrieval_backend_report,
        "external_vector_db": dict(external_vector_db),
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "gold_or_qrels_mutation": False,
        "guardrails": {
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
        },
    }


def _run_weaviate_route_ab_lane(
    *,
    lane_run_id: str,
    route_mode: str,
    items: Sequence[EvalItem],
    top_k: int,
    judge_adapter: Any,
    provisional_require_citations: bool,
    evidence_gate_mode: str,
    lane_factory: Callable[[str], Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    adapter = lane_factory(route_mode)
    validate_ready = getattr(adapter, "validate_ready_for_run", None)
    if callable(validate_ready):
        validate_ready()
    try:
        raw_outputs = [adapter.run_item(item, top_k=top_k) for item in items]
        raw_outputs, _evidence_gate_summary = apply_evidence_gate_to_outputs(raw_outputs, mode=evidence_gate_mode)
        summary, scored_rows = score_rag_eval_items(
            items,
            raw_outputs,
            top_k_values=top_k_values_for(top_k),
            judge_adapter=judge_adapter,
            provisional_require_citations=provisional_require_citations,
        )
        backend_comparison = build_backend_comparison_metrics(raw_outputs, adapter)
        summary["diagnostic_metrics"].update(backend_comparison)
        active_path_report = (
            dict(adapter.active_path_report)
            if isinstance(getattr(adapter, "active_path_report", None), Mapping)
            else {}
        )
        external_vector_db = (
            dict(adapter.external_vector_db_report)
            if isinstance(getattr(adapter, "external_vector_db_report", None), Mapping)
            else {}
        )
        summary.update(
            _closed_lane_summary(
                lane_run_id=lane_run_id,
                raw_outputs=raw_outputs,
                scored_rows=scored_rows,
                adapter=adapter,
                backend_comparison=backend_comparison,
                active_path_report=active_path_report,
                external_vector_db=external_vector_db,
            )
        )
        return summary, [_public_report_row(row) for row in scored_rows]
    finally:
        close_adapter = getattr(adapter, "close", None)
        if callable(close_adapter):
            close_adapter()


def _load_weaviate_mixed_route_diagnostic_items(path: Path) -> list[EvalItem]:
    items: list[EvalItem] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, Mapping):
                continue
            query = _clean(row.get("question_ko") or row.get("query") or row.get("question"))
            if not query:
                continue
            evidence_note = _clean(row.get("supporting_evidence_note"))
            expected_evidence = (ExpectedEvidence(text=evidence_note),) if evidence_note else ()
            track = _clean(row.get("track"))
            items.append(
                EvalItem(
                    id=f"mixed_route_row_{line_number:04d}",
                    query=query,
                    answerability="unknown",
                    expected_answer=_clean(row.get("expected_answer_ko")),
                    expected_evidence=expected_evidence,
                    tags=(track,) if track else (),
                    source_row={
                        "track": track,
                        "mixed_route_packet_line": line_number,
                    },
                )
            )
    return items


def _should_run_mixed_route_diagnostic(dataset_path: Path) -> bool:
    return dataset_path.name == "gold_queries_text_namu_v2_1_question_gold_v2.csv"
