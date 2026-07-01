from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "ai"
if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))

from app.capabilities.rag.generation import ExtractiveGenerator, RetrievedChunk


WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V1 = "weaviate_source_atom_v1"
WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2 = "weaviate_source_atom_v2"
WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION = WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V1
WEAVIATE_SOURCE_ATOM_SCHEMA_VERSIONS = frozenset(
    {WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V1, WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2}
)
WEAVIATE_SOURCE_ATOM_INDEX_CHECKPOINT_VERSION = "weaviate_source_atom_index_checkpoint_v1"
WEAVIATE_STREAMING_BGE_M3_VECTOR_SOURCE = "streaming-bge-m3"
WEAVIATE_CANDIDATE_INPUT_POLICY = "query_text_and_query_embedding_only_no_gold_qrels_labels_ids_or_baseline"
WEAVIATE_CANDIDATE_SURFACE_COMPLETE_MANIFEST_SCHEMA_VERSION = "candidate_surface_complete_manifest.v1"
WEAVIATE_ROUTE_SELECTED_CANDIDATE_SURFACE_V2_COLLECTION = "SourceAtomNonprodRouteSelectedCandidateSurfaceV2"
WEAVIATE_CANDIDATE_SURFACE_DIRTY_STATUSES = frozenset({"dirty", "dirty_partial", "partial_dirty"})
WEAVIATE_ROUTE_SELECTED_NONPROD_DEFAULT_CONFIG_PATH = (
    "ai/eval/configs/weaviate_route_selected_nonprod_default.json"
)
WEAVIATE_FULL_INDEX_NONPROD_ROLLBACK_CONFIG_PATH = "ai/eval/configs/weaviate_full_index_nonprod_rollback.json"
WEAVIATE_ROUTE_SELECTED_NONPROD_DEFAULT_KEY = "route_selected_nonprod_default"
WEAVIATE_FULL_INDEX_NONPROD_ROLLBACK_KEY = "weaviate_full_index_nonprod_rollback"
WEAVIATE_SOURCE_ATOM_REQUIRED_PROPERTIES = (
    "source_atom_id",
    "evidence_bundle_id",
    "doc_id",
    "chunk_id",
    "source_family",
    "granularity",
    "retrieval_route",
    "vectorized_semantic_content",
    "source_track",
    "title",
    "section",
    "text",
    "text_sha256",
    "source_uri_hash",
    "source_hash",
    "ingestion_run_id",
    "ingestion_version",
    "namespace",
    "visibility",
    "created_at",
    "updated_at",
)
WEAVIATE_SOURCE_ATOM_V2_EXTRA_PROPERTIES = (
    "vectorization_policy",
    "workbook_id",
    "workbook_version_id",
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
    "display_value",
    "candidate_surface_materialization",
    "candidate_surface_materialization_policy",
    "source_date_aliases_json",
    "same_row_period_cells_json",
    "source_atom_ids_json",
    "page_number",
    "physical_page_index",
    "block_index",
    "bbox",
    "region_type",
    "section_title",
    "table_caption",
    "locator_fingerprint",
    "parent_source_unit_id",
)
WEAVIATE_FILTERABLE_PROPERTIES = frozenset(
    {
        "source_atom_id",
        "doc_id",
        "chunk_id",
        "evidence_bundle_id",
        "source_family",
        "granularity",
        "retrieval_route",
        "vectorized_semantic_content",
        "vectorization_policy",
        "workbook_id",
        "workbook_version_id",
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
        "display_value",
        "candidate_surface_materialization",
        "page_number",
        "physical_page_index",
        "block_index",
        "region_type",
        "section_title",
        "table_caption",
        "locator_fingerprint",
        "parent_source_unit_id",
        "source_track",
        "namespace",
        "visibility",
    }
)
WEAVIATE_SEARCHABLE_PROPERTIES = frozenset({"text", "title"})
WEAVIATE_FORBIDDEN_CANDIDATE_FIELD_NAMES = frozenset(
    {
        "answerability",
        "answerability_label",
        "answerability_labels",
        "baseline_topk",
        "baseline_top_k",
        "baseline_topk_candidate_ids",
        "case_id",
        "expected_answer",
        "expected_answer_aliases",
        "expected_answer_text",
        "expected_chunk_id",
        "expected_doc_id",
        "expected_evidence",
        "expected_evidence_text",
        "gold",
        "gold_label",
        "gold_labels",
        "gold_locator",
        "label",
        "labels",
        "legacy_output",
        "legacy_outputs",
        "previous_winning_candidate",
        "qrels",
        "qrels_positive_id",
        "qrels_positive_ids",
        "query_id",
        "raw_prompt_payload",
        "raw_response_payload",
        "relevance",
        "relevance_label",
        "relevance_labels",
        "row_id",
        "search_unit_id",
        "search_view_id",
        "supporting_evidence",
        "target_chunk_id",
        "target_doc_id",
        "target_id",
        "target_locator",
    }
)
WEAVIATE_FORBIDDEN_CANDIDATE_CANONICAL_FIELDS = frozenset(
    re.sub(r"[^a-z0-9]+", "", field.casefold()) for field in WEAVIATE_FORBIDDEN_CANDIDATE_FIELD_NAMES
)
WEAVIATE_BACKEND_ALIASES = {
    "weaviate-vector": "weaviate_vector",
    "weaviate_vector": "weaviate_vector",
    "weaviate-bm25": "weaviate_bm25",
    "weaviate_bm25": "weaviate_bm25",
    "weaviate-hybrid": "weaviate_hybrid",
    "weaviate_hybrid": "weaviate_hybrid",
    "weaviate-auto": "weaviate_hybrid",
    "weaviate_auto": "weaviate_hybrid",
}
WEAVIATE_QUERY_MODES = {
    "weaviate_vector": "vector",
    "weaviate_bm25": "bm25",
    "weaviate_hybrid": "hybrid",
}
WEAVIATE_RETRIEVAL_ROUTE_MODES = frozenset({"full_index", "text_only", "mixed_pool", "route_selected"})
WEAVIATE_SOURCE_FAMILIES = frozenset({"TEXT", "PDF", "XLSX", "UNKNOWN"})
WEAVIATE_GRANULARITIES = frozenset(
    {
        "paragraph",
        "heading_context_block",
        "page_block",
        "table_summary",
        "table_row",
        "cell",
        "caption",
        "metadata_only",
        "unknown",
    }
)
WEAVIATE_RETRIEVAL_ROUTES = frozenset(
    {
        "text_general",
        "pdf_paragraph",
        "pdf_table",
        "xlsx_table",
        "xlsx_cell_trace",
        "mixed_fallback",
        "unknown",
    }
)
WEAVIATE_ROUTE_PLANNER_VERSION = "weaviate_route_planner_v1"
WEAVIATE_ROUTE_TAXONOMY_VERSION = "weaviate_route_taxonomy_v1"
WEAVIATE_QUERY_REFORMULATION_VERSION = "weaviate_query_reformulation_v3"
WEAVIATE_QUERY_REFORMULATION_INPUT_POLICY = (
    "query_text_only_bounded_token_number_punctuation_anchor_variants_no_gold_qrels_labels_ids_or_baseline"
)
WEAVIATE_QUERY_VARIANT_MERGE_POLICY = "bounded_round_robin_query_variant_rank_v1"
WEAVIATE_MAX_QUERY_VARIANTS = 8
WEAVIATE_KOREAN_SINO_DIGITS: Mapping[str, int] = {
    "일": 1,
    "이": 2,
    "삼": 3,
    "사": 4,
    "오": 5,
    "육": 6,
    "칠": 7,
    "팔": 8,
    "구": 9,
}
WEAVIATE_KOREAN_QUERY_PARTICLES = (
    "으로는",
    "으로",
    "에게는",
    "에게",
    "에서는",
    "에서",
    "에는",
    "으로서",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "와",
    "과",
    "도",
    "만",
)
WEAVIATE_QUERY_CONTENT_STOPWORDS = frozenset(
    {
        "어떤",
        "어떻게",
        "무엇",
        "뭐",
        "어디",
        "언제",
        "누구",
        "식",
        "식으로",
        "올라",
        "올라와",
        "적혀",
        "있어",
        "알려줘",
        "설명해",
        "말해줘",
    }
)
WEAVIATE_SAME_DOC_RESIDUAL_RETRIEVAL_POLICY = "bounded_query_variant_same_doc_weaviate_v1"
WEAVIATE_SAME_DOC_RESIDUAL_MAX_DOCS = 2
WEAVIATE_SAME_DOC_RESIDUAL_TOP_K_PER_DOC = 3
WEAVIATE_XLSX_SCOPED_EXPANSION_POLICY = "bounded_source_owned_xlsx_scope_weaviate_v1"
WEAVIATE_XLSX_ROW_VALUE_BUNDLE_MATERIALIZATION = "xlsx_row_value_bundle_v1"
WEAVIATE_XLSX_ROW_VALUE_BUNDLE_RECALL_POLICY = "source_owned_same_row_bundle_recall_v1"
WEAVIATE_XLSX_SCOPED_EXPANSION_MAX_SCOPES = 2
WEAVIATE_XLSX_SCOPED_EXPANSION_TOP_K_PER_SCOPE = 3
WEAVIATE_XLSX_SCOPED_QUERY_AXIS_FIELDS = (
    "row_label",
    "column_label",
    "target_column",
    "header",
    "header_path",
)
WEAVIATE_PDF_SCOPED_EXPANSION_POLICY = "bounded_source_owned_pdf_scope_weaviate_v1"
WEAVIATE_PDF_SCOPED_EXPANSION_MAX_SCOPES = 2
WEAVIATE_PDF_SCOPED_EXPANSION_TOP_K_PER_SCOPE = 3
WEAVIATE_PDF_SCOPED_QUERY_AXIS_FIELDS = (
    "row_label",
    "column_label",
)
WEAVIATE_SOURCE_OWNED_TEXT_TAG_FIELD_ALIASES: Mapping[str, tuple[str, ...]] = {
    "sheet": ("sheet", "sheet_name"),
    "cell_range": ("cell_range", "range"),
    "cell": ("cell",),
    "row_index_1based": ("row_index_1based", "row_number", "row"),
    "row_label": ("row_label",),
    "column_label": ("column_label",),
    "target_column": ("target_column",),
    "header": ("header",),
    "header_path": ("header_path", "column_header_path"),
    "table_id": ("table_id",),
    "display_value": ("display_value",),
    "page_number": ("page_number", "page"),
    "physical_page_index": ("physical_page_index",),
    "block_index": ("block_index",),
    "bbox": ("bbox",),
    "region_type": ("region_type",),
    "section_title": ("section_title",),
    "table_caption": ("table_caption",),
    "locator_fingerprint": ("locator_fingerprint", "stable_locator_fingerprint"),
}
WEAVIATE_SOURCE_OWNED_TEXT_TAG_BOUNDARY_NAMES = tuple(
    sorted(
        {
            alias
            for aliases in WEAVIATE_SOURCE_OWNED_TEXT_TAG_FIELD_ALIASES.values()
            for alias in aliases
        }
        | {
            "value",
            "normalized_value",
            "formula",
            "workbook",
            "source_workbook",
            "workbook_id",
            "workbook_version_id",
            "source_path",
            "source_file_name",
            "file_name",
            "title",
            "source_title",
        },
        key=len,
        reverse=True,
    )
)
WEAVIATE_SOURCE_OWNED_TEXT_TAG_STRIPPED_SEARCHABLE_ALIASES = (
    "normalized_value",
    "formula",
    "source_path",
    "source_file_name",
    "file_name",
    "source_workbook",
    "workbook",
    "workbook_id",
    "workbook_version_id",
    "title",
    "source_title",
)
WEAVIATE_VECTORIZED_GRANULARITIES = frozenset(
    {
        "paragraph",
        "heading_context_block",
        "table_summary",
        "table_row",
        "caption",
    }
)
WEAVIATE_METADATA_ONLY_GRANULARITIES = frozenset(
    {
        "cell",
        "metadata_only",
    }
)
WEAVIATE_METADATA_ONLY_POLICY_OBJECT_TYPES = frozenset(
    {
        "cell",
        "empty_fragment",
        "local_path_source_trace_fields",
        "metadata_only",
        "page_marker",
        "repeated_header_footer",
    }
)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clean_text_list_json(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = _clean(value)
        if not text:
            return ""
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            values: Iterable[Any] = (text,)
        else:
            if isinstance(parsed, Sequence) and not isinstance(parsed, (str, bytes, bytearray)):
                values = parsed
            else:
                values = (parsed,)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        values = value
    else:
        values = (value,)

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _clean(item)
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    if not cleaned:
        return ""
    return json.dumps(cleaned, ensure_ascii=False)


def _clean_mapping_list_json(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = _clean(value)
        if not text:
            return ""
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            return ""
    else:
        parsed = value
    if not isinstance(parsed, Sequence) or isinstance(parsed, (str, bytes, bytearray)):
        return ""
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in parsed:
        if not isinstance(item, Mapping):
            continue
        row = {str(key): value for key, value in item.items() if _clean(key)}
        if not row:
            continue
        key = json.dumps(row, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        cleaned.append(row)
        seen.add(key)
    if not cleaned:
        return ""
    return json.dumps(cleaned, ensure_ascii=False, sort_keys=True)


WEAVIATE_SAME_ROW_PERIOD_CELL_PACKET_FIELDS = frozenset(
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


def _clean_same_row_period_cells_json(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = _clean(value)
        if not text:
            return ""
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            return ""
    else:
        parsed = value
    if not isinstance(parsed, Sequence) or isinstance(parsed, (str, bytes, bytearray)):
        return ""
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in parsed:
        if not isinstance(item, Mapping):
            return ""
        keys = {str(key) for key in item if _clean(key)}
        if keys != WEAVIATE_SAME_ROW_PERIOD_CELL_PACKET_FIELDS:
            return ""
        if _forbidden_candidate_field_paths(item):
            return ""
        if _clean(item.get("schema_version")) != "actual_rag_eval.xlsx.same_row_period_cell.v1":
            return ""
        if _clean(item.get("provenance_policy")) != "source_owned_same_row_period_cell_v1":
            return ""
        raw_value = _clean(item.get("raw_value"))
        parsed_date = _clean(item.get("parsed_date"))
        if raw_value != parsed_date or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", parsed_date):
            return ""
        try:
            year = int(item.get("year"))
            month = int(item.get("month"))
            day = int(item.get("day"))
        except (TypeError, ValueError):
            return ""
        if not (1 <= month <= 12 and 1 <= day <= 31 and parsed_date == f"{year:04d}-{month:02d}-{day:02d}"):
            return ""
        row = {
            "schema_version": "actual_rag_eval.xlsx.same_row_period_cell.v1",
            "provenance_policy": "source_owned_same_row_period_cell_v1",
            "source_atom_id": _clean(item.get("source_atom_id")),
            "doc_id": _clean(item.get("doc_id")),
            "sheet": _clean(item.get("sheet")),
            "cell_range": _clean(item.get("cell_range")),
            "cell": _clean(item.get("cell")),
            "row_index_1based": _clean(item.get("row_index_1based")),
            "row_label": _clean(item.get("row_label")),
            "column_label": _clean(item.get("column_label")),
            "raw_value": raw_value,
            "parsed_date": parsed_date,
            "year": year,
            "month": month,
            "day": day,
        }
        if any(
            not row[field]
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
            )
        ):
            return ""
        key = json.dumps(row, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        cleaned.append(row)
        seen.add(key)
    if not cleaned:
        return ""
    return json.dumps(cleaned, ensure_ascii=False, sort_keys=True)


def _source_owned_axis_term_parts(value: Any) -> list[str]:
    text = _clean(value)
    if not text:
        return []
    parts = [text]
    for part in re.split(r"\s*(?:>|/|\||,|;)\s*", text):
        cleaned = _clean(part)
        if cleaned:
            parts.append(cleaned)
    seen: set[str] = set()
    result: list[str] = []
    for part in parts:
        if part in seen:
            continue
        seen.add(part)
        result.append(part)
    return result


def _source_owned_scope_axis_terms(
    context: Mapping[str, Any],
    fields: Sequence[str],
    *,
    max_terms: int = 8,
) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for field in fields:
        value = context.get(field)
        for term in _source_owned_axis_term_parts(value):
            if term in seen:
                continue
            terms.append(term)
            seen.add(term)
            if len(terms) >= max_terms:
                return terms
    return terms


def _source_owned_text_tag_boundary_pattern() -> str:
    boundary_names = "|".join(re.escape(name) for name in WEAVIATE_SOURCE_OWNED_TEXT_TAG_BOUNDARY_NAMES)
    return rf"(?=\s*\|\s*|\s*;\s*|\s*,\s*(?:{boundary_names})\s*=|\s+(?:{boundary_names})\s*=|$)"


def _source_owned_text_tag_value(text: str, aliases: Sequence[str]) -> str:
    if not text:
        return ""
    boundary = _source_owned_text_tag_boundary_pattern()
    for alias in aliases:
        pattern = rf"(?:^|[\s|;,]){re.escape(alias)}\s*=\s*(.*?){boundary}"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = _clean(match.group(1)).strip("|;,")
        if value:
            return value
    return ""


def _source_owned_text_tags(text: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for field, aliases in WEAVIATE_SOURCE_OWNED_TEXT_TAG_FIELD_ALIASES.items():
        value = _source_owned_text_tag_value(text, aliases)
        if value:
            tags[field] = value
    cell = _clean(tags.get("cell"))
    if cell and not _clean(tags.get("row_index_1based")):
        match = re.match(r"^[A-Z]{1,3}(\d+)$", cell, flags=re.I)
        if match:
            tags["row_index_1based"] = match.group(1)
    return tags


def _strip_source_owned_forbidden_searchable_text_tags(text: str) -> str:
    cleaned = _clean(text)
    if not cleaned:
        return ""
    boundary = _source_owned_text_tag_boundary_pattern()
    for alias in WEAVIATE_SOURCE_OWNED_TEXT_TAG_STRIPPED_SEARCHABLE_ALIASES:
        pattern = rf"(^|[\s|;,]){re.escape(alias)}\s*=\s*.*?{boundary}"
        cleaned = re.sub(pattern, lambda match: " | " if "|" in match.group(1) else " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:\s*\|\s*){2,}", " | ", cleaned)
    cleaned = re.sub(r"^\s*\|\s*|\s*\|\s*$", "", cleaned)
    return " ".join(cleaned.split())


def _sha256_text(value: Any) -> str:
    return hashlib.sha256(_clean(value).encode("utf-8")).hexdigest()


def _sha256_file_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _env_bool(value: Any, *, default: bool = False) -> bool:
    text = _clean(value)
    if not text:
        return default
    return text.casefold() in {"1", "true", "yes", "y", "on"}


def _nonprod_namespace(value: str) -> bool:
    return bool(re.search(r"(nonprod|dev|test|local|diagnostic)", _clean(value), flags=re.I))


class WeaviateUnavailableError(RuntimeError):
    """Raised when the Weaviate lane cannot query Weaviate and must not fall back."""


def _repo_relative_posix(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_repo_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _read_json_mapping(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WeaviateUnavailableError(f"weaviate_unavailable: config_path_missing:{path.as_posix()}") from exc
    except json.JSONDecodeError as exc:
        raise WeaviateUnavailableError(f"weaviate_unavailable: config_path_invalid_json:{path.as_posix()}") from exc
    if not isinstance(data, Mapping):
        raise WeaviateUnavailableError(f"weaviate_unavailable: config_path_not_object:{path.as_posix()}")
    return dict(data)


def _config_path_from_env(env: Mapping[str, str]) -> str:
    return _clean(
        env.get("ACTUAL_RAG_EVAL_WEAVIATE_CONFIG_PATH")
        or env.get("WEAVIATE_SOURCE_ATOM_CONFIG_PATH")
        or env.get("WEAVIATE_CONFIG_PATH")
    )


def _default_config_path_for_route_mode(route_mode: str | None) -> str:
    normalized = _clean(route_mode).replace("-", "_").casefold()
    if normalized == "full_index":
        return WEAVIATE_FULL_INDEX_NONPROD_ROLLBACK_CONFIG_PATH
    return WEAVIATE_ROUTE_SELECTED_NONPROD_DEFAULT_CONFIG_PATH


def _rollback_report_from_config(data: Mapping[str, Any]) -> dict[str, Any]:
    rollback = data.get("rollback") if isinstance(data.get("rollback"), Mapping) else {}
    if rollback:
        return {
            "rollback_key": _clean(rollback.get("rollback_key")) or WEAVIATE_FULL_INDEX_NONPROD_ROLLBACK_KEY,
            "config_path": _clean(rollback.get("config_path")) or WEAVIATE_FULL_INDEX_NONPROD_ROLLBACK_CONFIG_PATH,
            "retrieval_route_mode": _clean(rollback.get("retrieval_route_mode")) or "full_index",
            "collection": _clean(rollback.get("collection")) or "SourceAtomNonprod",
            "schema_version_source_atom": _clean(rollback.get("schema_version_source_atom"))
            or WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V1,
            "index_manifest_path": _clean(rollback.get("index_manifest_path"))
            or "reports/rag_eval/weaviate_source_atom_index_manifest_nonprod/index_manifest.json",
        }
    return {
        "rollback_key": _clean(data.get("rollback_key")) or WEAVIATE_FULL_INDEX_NONPROD_ROLLBACK_KEY,
        "config_path": _clean(data.get("config_path")) or WEAVIATE_FULL_INDEX_NONPROD_ROLLBACK_CONFIG_PATH,
        "retrieval_route_mode": _clean(data.get("retrieval_route_mode")) or "full_index",
        "collection": _clean(data.get("collection")) or "SourceAtomNonprod",
        "schema_version_source_atom": _clean(data.get("schema_version_source_atom"))
        or WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V1,
        "index_manifest_path": _clean(data.get("index_manifest_path"))
        or "reports/rag_eval/weaviate_source_atom_index_manifest_nonprod/index_manifest.json",
    }


def _implicit_weaviate_config_report(config: "WeaviateSourceAtomConfig", route_mode: str) -> dict[str, Any]:
    rollback = {
        "rollback_key": WEAVIATE_FULL_INDEX_NONPROD_ROLLBACK_KEY,
        "config_path": WEAVIATE_FULL_INDEX_NONPROD_ROLLBACK_CONFIG_PATH,
        "retrieval_route_mode": "full_index",
        "collection": "SourceAtomNonprod",
        "schema_version_source_atom": WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V1,
        "index_manifest_path": "reports/rag_eval/weaviate_source_atom_index_manifest_nonprod/index_manifest.json",
    }
    return {
        "selection": "manual_weaviate_adapter_config",
        "config_path": "",
        "explicit_nonprod_config_path": False,
        "retrieval_route_mode": route_mode,
        "active_retrieval_service_boundary": "weaviate",
        "collection": config.collection_name,
        "schema_version_source_atom": config.schema_version,
        "index_manifest_path": config.index_manifest_path,
        "fallback_used": False,
        "fail_closed_on_unavailable": True,
        "rollback_key": rollback["rollback_key"],
        "rollback": rollback,
    }


class WeaviateSourceAtomClientProtocol(Protocol):
    def ping(self) -> bool:
        ...

    def ensure_collection(self, schema: Mapping[str, Any]) -> None:
        ...

    def recreate_collection(self, schema: Mapping[str, Any]) -> None:
        ...

    def upsert_many(self, objects: Sequence[Mapping[str, Any]], vectors: Sequence[Sequence[float]]) -> int:
        ...

    def upsert_many_metadata_only(self, objects: Sequence[Mapping[str, Any]]) -> int:
        ...

    def query(
        self,
        *,
        mode: str,
        query_text: str,
        query_vector: Sequence[float] | None,
        filters: Mapping[str, Any],
        limit: int,
        alpha: float,
    ) -> list[dict[str, Any]]:
        ...

    def close(self) -> None:
        ...


@dataclass(frozen=True)
class WeaviateSourceAtomConfig:
    vector_db: str = "weaviate"
    url: str = "http://localhost:8080"
    grpc_port: int = 50051
    api_key: str = ""
    collection_name: str = "SourceAtomNonprod"
    namespace: str = "actual_rag_eval_nonprod"
    use_local_docker: bool = True
    timeout_seconds: float = 30.0
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "auto"
    visibility: str = "nonprod"
    hybrid_alpha: float = 0.5
    schema_version: str = WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION
    index_manifest_path: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "WeaviateSourceAtomConfig":
        source = env if env is not None else os.environ
        vector_db = _clean(source.get("RAG_VECTOR_DB") or source.get("ACTUAL_RAG_EVAL_VECTOR_DB") or "weaviate").casefold()
        url = _clean(source.get("WEAVIATE_URL") or source.get("ACTUAL_RAG_EVAL_WEAVIATE_URL") or "http://localhost:8080")
        collection = _clean(
            source.get("WEAVIATE_COLLECTION_SOURCE_ATOM")
            or source.get("ACTUAL_RAG_EVAL_WEAVIATE_COLLECTION_SOURCE_ATOM")
            or "SourceAtomNonprod"
        )
        namespace = _clean(
            source.get("WEAVIATE_NAMESPACE")
            or source.get("ACTUAL_RAG_EVAL_VECTOR_NAMESPACE")
            or source.get("RAG_VECTOR_NAMESPACE")
            or "actual_rag_eval_nonprod"
        )
        grpc_raw = _clean(source.get("WEAVIATE_GRPC_PORT") or source.get("ACTUAL_RAG_EVAL_WEAVIATE_GRPC_PORT") or "50051")
        timeout_raw = _clean(
            source.get("WEAVIATE_TIMEOUT_SECONDS") or source.get("ACTUAL_RAG_EVAL_WEAVIATE_TIMEOUT_SECONDS") or "30"
        )
        alpha_raw = _clean(source.get("WEAVIATE_HYBRID_ALPHA") or source.get("ACTUAL_RAG_EVAL_WEAVIATE_HYBRID_ALPHA") or "0.5")
        index_manifest_path = _clean(
            source.get("WEAVIATE_INDEX_MANIFEST_PATH")
            or source.get("ACTUAL_RAG_EVAL_WEAVIATE_INDEX_MANIFEST_PATH")
            or "reports/rag_eval/weaviate_source_atom_index_manifest_nonprod/index_manifest.json"
        )
        schema_version = _clean(
            source.get("WEAVIATE_SCHEMA_VERSION")
            or source.get("ACTUAL_RAG_EVAL_WEAVIATE_SCHEMA_VERSION")
            or WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION
        )
        use_local_docker = _env_bool(
            source.get("WEAVIATE_USE_LOCAL_DOCKER") or source.get("ACTUAL_RAG_EVAL_WEAVIATE_USE_LOCAL_DOCKER"),
            default=True,
        )
        try:
            grpc_port = int(grpc_raw)
        except ValueError:
            grpc_port = 50051
        try:
            timeout_seconds = float(timeout_raw)
        except ValueError:
            timeout_seconds = 30.0
        try:
            hybrid_alpha = min(1.0, max(0.0, float(alpha_raw)))
        except ValueError:
            hybrid_alpha = 0.5
        return cls(
            vector_db=vector_db,
            url=url,
            grpc_port=grpc_port,
            api_key=_clean(source.get("WEAVIATE_API_KEY") or source.get("ACTUAL_RAG_EVAL_WEAVIATE_API_KEY")),
            collection_name=collection,
            namespace=namespace,
            use_local_docker=use_local_docker,
            timeout_seconds=timeout_seconds,
            embedding_model=_clean(source.get("EMBEDDING_MODEL") or source.get("ACTUAL_RAG_EVAL_EMBEDDING_MODEL") or "BAAI/bge-m3"),
            embedding_device=_clean(source.get("EMBEDDING_DEVICE") or source.get("ACTUAL_RAG_EVAL_EMBEDDING_DEVICE") or "auto"),
            visibility=_clean(source.get("WEAVIATE_VISIBILITY") or source.get("ACTUAL_RAG_EVAL_WEAVIATE_VISIBILITY") or "nonprod"),
            hybrid_alpha=hybrid_alpha,
            schema_version=schema_version,
            index_manifest_path=index_manifest_path,
        )

    @property
    def configured(self) -> bool:
        return self.vector_db == "weaviate" and bool(self.url and self.collection_name and self.namespace)

    @property
    def production_namespace(self) -> bool:
        return bool(self.configured and not _nonprod_namespace(self.namespace))

    @property
    def url_hash(self) -> str:
        return f"sha256:{_sha256_text(self.url)}" if self.url else ""

    @property
    def collection_hash(self) -> str:
        return f"sha256:{_sha256_text(self.collection_name)}" if self.collection_name else ""

    def validate_for_nonprod(self) -> None:
        if self.vector_db != "weaviate":
            raise WeaviateUnavailableError(f"weaviate_unavailable: RAG_VECTOR_DB must be weaviate, got {self.vector_db!r}")
        if not self.url:
            raise WeaviateUnavailableError("weaviate_unavailable: WEAVIATE_URL is required")
        if not self.collection_name:
            raise WeaviateUnavailableError("weaviate_unavailable: WEAVIATE_COLLECTION_SOURCE_ATOM is required")
        if not self.namespace:
            raise WeaviateUnavailableError("weaviate_unavailable: WEAVIATE_NAMESPACE is required")
        if self.production_namespace:
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: production_or_ambiguous_namespace_blocked:{self.namespace}"
            )
        if self.embedding_model != "BAAI/bge-m3":
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: embedding_model_must_be_BAAI_bge_m3:{self.embedding_model}"
            )
        if self.schema_version not in WEAVIATE_SOURCE_ATOM_SCHEMA_VERSIONS:
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: unsupported_source_atom_schema_version:{self.schema_version}"
            )

    def external_vector_db_report(self, *, invoked: bool, reachable: bool, fallback_reason: str = "") -> dict[str, Any]:
        configured = self.configured
        return {
            "configured": configured,
            "invoked": bool(invoked),
            "reachable": bool(reachable),
            "backend": "weaviate",
            "provider": "weaviate",
            "namespace": self.namespace,
            "production_namespace": self.production_namespace,
            "collection_name": self.collection_name,
            "collection_name_hash": self.collection_hash,
            "weaviate_url_hash": self.url_hash,
            "grpc_port": self.grpc_port,
            "use_local_docker": self.use_local_docker,
            "timeout_seconds": self.timeout_seconds,
            "embedding_model": self.embedding_model,
            "embedding_device": self.embedding_device,
            "index_manifest_path": self.index_manifest_path,
            "fallback_reason": fallback_reason
            or (
                ""
                if configured and reachable
                else "weaviate_unreachable"
                if configured and invoked
                else "weaviate_not_invoked"
            ),
        }


def load_weaviate_adapter_config_path(
    *,
    requested_route_mode: str | None = None,
    config_path: str | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[WeaviateSourceAtomConfig, str, dict[str, Any]]:
    source = env if env is not None else os.environ
    requested_route_mode_normalized = _clean(requested_route_mode).replace("-", "_").casefold()
    requested_path = _clean(config_path)
    env_config_path = "" if requested_route_mode_normalized else _config_path_from_env(source)
    selected_path_text = (
        requested_path
        or env_config_path
        or _default_config_path_for_route_mode(requested_route_mode_normalized or None)
    )
    selected_path = _resolve_repo_path(selected_path_text)
    data = _read_json_mapping(selected_path)
    selection = _clean(data.get("selection") or data.get("config_key")) or WEAVIATE_ROUTE_SELECTED_NONPROD_DEFAULT_KEY
    configured_route_mode = _clean(data.get("retrieval_route_mode")).replace("-", "_").casefold()
    route_mode = requested_route_mode_normalized or configured_route_mode
    if route_mode not in WEAVIATE_RETRIEVAL_ROUTE_MODES:
        raise WeaviateUnavailableError(f"weaviate_unavailable: unsupported_route_mode:{route_mode}")
    fallback_used = bool(data.get("fallback_used"))
    fail_closed_on_unavailable = data.get("fail_closed_on_unavailable") is not False
    if fallback_used:
        raise WeaviateUnavailableError(f"weaviate_unavailable: config_enables_fallback:{selected_path.as_posix()}")
    if not fail_closed_on_unavailable:
        raise WeaviateUnavailableError(f"weaviate_unavailable: config_not_fail_closed:{selected_path.as_posix()}")

    env_for_config = dict(source)
    config_overrides = {
        "RAG_VECTOR_DB": _clean(data.get("vector_db")) or "weaviate",
        "WEAVIATE_URL": _clean(data.get("url")) or _clean(source.get("WEAVIATE_URL")) or "http://localhost:8080",
        "WEAVIATE_GRPC_PORT": _clean(data.get("grpc_port")) or _clean(source.get("WEAVIATE_GRPC_PORT")) or "50051",
        "WEAVIATE_COLLECTION_SOURCE_ATOM": _clean(data.get("collection")) or _clean(data.get("collection_name")),
        "WEAVIATE_NAMESPACE": _clean(data.get("namespace")) or "actual_rag_eval_nonprod",
        "WEAVIATE_VISIBILITY": _clean(data.get("visibility")) or "nonprod",
        "WEAVIATE_SCHEMA_VERSION": _clean(data.get("schema_version_source_atom")) or _clean(data.get("schema_version")),
        "WEAVIATE_INDEX_MANIFEST_PATH": _clean(data.get("index_manifest_path")),
        "WEAVIATE_HYBRID_ALPHA": _clean(data.get("hybrid_alpha")) or "0.5",
        "WEAVIATE_USE_LOCAL_DOCKER": _clean(data.get("use_local_docker")) or "true",
        "EMBEDDING_MODEL": _clean(data.get("embedding_model")) or "BAAI/bge-m3",
        "EMBEDDING_DEVICE": _clean(data.get("embedding_device")) or _clean(source.get("EMBEDDING_DEVICE")) or "auto",
    }
    env_for_config.update({key: value for key, value in config_overrides.items() if value})
    config = WeaviateSourceAtomConfig.from_env(env_for_config)
    config.validate_for_nonprod()
    rollback_report = _rollback_report_from_config(data)
    selection_report = {
        "selection": selection,
        "config_path": _repo_relative_posix(selected_path),
        "explicit_nonprod_config_path": True,
        "retrieval_route_mode": route_mode,
        "active_retrieval_backend": "weaviate_hybrid",
        "active_retrieval_service_boundary": "weaviate",
        "collection": config.collection_name,
        "schema_version_source_atom": config.schema_version,
        "route_planner_version": WEAVIATE_ROUTE_PLANNER_VERSION,
        "index_manifest_path": config.index_manifest_path,
        "namespace": config.namespace,
        "visibility": config.visibility,
        "use_local_docker": config.use_local_docker,
        "fallback_used": False,
        "fail_closed_on_unavailable": True,
        "rollback_key": rollback_report["rollback_key"],
        "rollback": rollback_report,
    }
    candidate_surface = data.get("candidate_surface_rebuild")
    if isinstance(candidate_surface, Mapping):
        candidate_surface_report = dict(candidate_surface)
        candidate_surface_report.setdefault("schema_version", "actual_rag_eval.candidate_surface_rebuild.v1")
        candidate_surface_report.setdefault("report_only_diagnostic", True)
        candidate_surface_report.setdefault("official_metric", False)
        candidate_surface_report.setdefault("official_metric_input_rows", 0)
        candidate_surface_report.setdefault("candidate_collection", config.collection_name)
        candidate_surface_report.setdefault("surface_status", "ready")
        candidate_surface_report.setdefault("metric_blocked_until_complete_manifest", False)
        candidate_surface_report.setdefault("complete_manifest_required", False)
        candidate_surface_report.setdefault("production_namespace", config.production_namespace)
        candidate_surface_report.setdefault("source_registry_mutated", False)
        candidate_surface_report.setdefault("latest_current_mutated", False)
        candidate_surface_report.setdefault("external_archive_profiled", False)
        candidate_surface_report.setdefault("external_archive_indexed", False)
        if candidate_surface_report.get("report_only_diagnostic") is not True:
            raise WeaviateUnavailableError(
                "weaviate_unavailable: candidate_surface_report_only_diagnostic_required"
            )
        if candidate_surface_report.get("official_metric") is not False:
            raise WeaviateUnavailableError("weaviate_unavailable: candidate_surface_official_metric_blocked")
        try:
            official_metric_input_rows = int(candidate_surface_report.get("official_metric_input_rows") or 0)
        except (TypeError, ValueError) as exc:
            raise WeaviateUnavailableError(
                "weaviate_unavailable: candidate_surface_official_metric_input_rows_invalid"
            ) from exc
        if official_metric_input_rows != 0:
            raise WeaviateUnavailableError(
                "weaviate_unavailable: candidate_surface_official_metric_input_rows_blocked"
            )
        for protected_flag in (
            "production_namespace",
            "source_registry_mutated",
            "latest_current_mutated",
            "external_archive_profiled",
            "external_archive_indexed",
        ):
            if candidate_surface_report.get(protected_flag) is not False:
                raise WeaviateUnavailableError(
                    f"weaviate_unavailable: candidate_surface_{protected_flag}_blocked"
                )
        selection_report["candidate_surface_rebuild"] = candidate_surface_report
    return config, route_mode, selection_report


def build_weaviate_source_atom_schema(config: WeaviateSourceAtomConfig) -> dict[str, Any]:
    properties: list[dict[str, Any]] = []
    property_names = list(WEAVIATE_SOURCE_ATOM_REQUIRED_PROPERTIES)
    if config.schema_version == WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2:
        property_names.extend(WEAVIATE_SOURCE_ATOM_V2_EXTRA_PROPERTIES)
    for name in property_names:
        properties.append(
            {
                "name": name,
                "data_type": "text",
                "index_filterable": name in WEAVIATE_FILTERABLE_PROPERTIES,
                "index_searchable": name in WEAVIATE_SEARCHABLE_PROPERTIES,
                "tokenization": "word" if name in WEAVIATE_SEARCHABLE_PROPERTIES else "field",
            }
        )
    return {
        "schema_version": config.schema_version,
        "collection_name": config.collection_name,
        "vectorizer": "none",
        "vector_index": "hnsw",
        "distance_metric": "cosine",
        "multi_tenancy": False,
        "properties": properties,
        "filter_policy": {
            "namespace": config.namespace,
            "visibility": config.visibility,
            "metadata_filters_sent_to_weaviate": True,
            "python_post_filtering": "safety_validation_only",
        },
        "metadata_vector_policy": {
            "policy_version": "weaviate_source_atom_vectorization_policy_v1",
            "schema_version": config.schema_version,
            "index_time_metadata_only_supported": config.schema_version == WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2,
            "vectorized_by_default": sorted(WEAVIATE_VECTORIZED_GRANULARITIES),
            "metadata_only_by_default": sorted(WEAVIATE_METADATA_ONLY_POLICY_OBJECT_TYPES),
            "metadata_only_granularities": sorted(WEAVIATE_METADATA_ONLY_GRANULARITIES),
        },
        "korean_japanese_tokenization_note": "word tokenization is the conservative portable setting for mixed Korean/Japanese text.",
    }


def _canonical_candidate_field_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean(value).casefold())


def _forbidden_candidate_field_paths(value: Any, *, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            canonical = _canonical_candidate_field_name(key_text)
            if canonical in WEAVIATE_FORBIDDEN_CANDIDATE_CANONICAL_FIELDS or canonical.startswith("human"):
                paths.append(path)
            paths.extend(_forbidden_candidate_field_paths(child, prefix=path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            paths.extend(_forbidden_candidate_field_paths(child, prefix=f"{prefix}[{index}]"))
    return paths


def _raise_forbidden_candidate_fields(*values: Any) -> None:
    forbidden: list[str] = []
    for value in values:
        forbidden.extend(_forbidden_candidate_field_paths(value))
    if forbidden:
        raise ValueError(f"forbidden_candidate_generation_field: {sorted(set(forbidden))}")


def _source_family(value: Any) -> str:
    family = _clean(value).upper()
    return family if family in {"TEXT", "PDF", "XLSX"} else "UNKNOWN"


def _metadata_value(row: Mapping[str, Any], metadata: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        for source in (row, metadata):
            value = source.get(key)
            if _clean(value):
                return _clean(value)
    return ""


def _derive_granularity(row: Mapping[str, Any], metadata: Mapping[str, Any], source_family: str) -> str:
    declared = _clean(
        _metadata_value(
            row,
            metadata,
            "granularity",
            "source_granularity",
            "chunk_granularity",
            "region_type",
            "block_type",
            "target_column",
        )
    ).casefold()
    source_atom_id = _clean(row.get("source_atom_id") or metadata.get("source_atom_id")).casefold()
    section = _clean(row.get("section") or metadata.get("section")).casefold()
    text = _clean(row.get("text") or row.get("bm25_text") or row.get("embedding_text") or row.get("display_text")).casefold()
    source_identity = _clean(
        row.get("source_identity") or row.get("sourceIdentity") or metadata.get("source_identity") or metadata.get("sourceIdentity")
    ).casefold()
    searchable = "\n".join([declared, source_atom_id, section, text, source_identity])
    if "metadata" in declared and "only" in declared:
        return "metadata_only"
    if "caption" in searchable:
        return "caption"
    if source_family == "XLSX":
        if re.search(r"\bcell\s*=", searchable) or re.search(r":[a-z]{1,3}\d+\b", source_identity):
            return "cell"
        if "range=" in searchable or re.search(r":[a-z]{1,3}\d+:[a-z]{1,3}\d+", source_identity):
            return "table_row"
        return "table_summary"
    if source_family == "PDF":
        if "table" in searchable:
            return "table_row"
        if "heading" in searchable or "section_heading" in searchable:
            return "heading_context_block"
        if "page_block" in searchable or declared == "page":
            return "page_block"
        if "paragraph" in searchable or "text_block" in searchable:
            return "paragraph"
        return "page_block"
    if source_family == "TEXT":
        if "heading" in searchable:
            return "heading_context_block"
        if "caption" in searchable:
            return "caption"
        return "paragraph"
    return "unknown"


def _retrieval_route_for(source_family: str, granularity: str) -> str:
    if source_family == "TEXT":
        return "text_general"
    if source_family == "PDF":
        if granularity in {"table_summary", "table_row", "caption"}:
            return "pdf_table"
        return "pdf_paragraph"
    if source_family == "XLSX":
        if granularity == "cell":
            return "xlsx_table"
        return "xlsx_table"
    return "unknown"


def derive_weaviate_route_taxonomy(row: Mapping[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    _raise_forbidden_candidate_fields(row, metadata)
    family = _source_family(
        row.get("source_family")
        or row.get("sourceFamily")
        or metadata.get("source_family")
        or metadata.get("sourceFamily")
    )
    granularity = _derive_granularity(row, metadata, family)
    if granularity not in WEAVIATE_GRANULARITIES:
        granularity = "unknown"
    route = _retrieval_route_for(family, granularity)
    vectorized = granularity in WEAVIATE_VECTORIZED_GRANULARITIES
    return {
        "taxonomy_version": WEAVIATE_ROUTE_TAXONOMY_VERSION,
        "source_family": family,
        "granularity": granularity,
        "retrieval_route": route if route in WEAVIATE_RETRIEVAL_ROUTES else "unknown",
        "vectorized_semantic_content": vectorized,
        "vectorization_policy": "vectorized_by_default" if vectorized else "metadata_only_by_default",
        "route_taxonomy_source": "source_owned_metadata_only",
        "route_taxonomy_uses_gold_fields": False,
        "route_taxonomy_uses_expected_fields": False,
        "route_taxonomy_uses_qrels": False,
        "route_taxonomy_uses_labels": False,
        "route_taxonomy_uses_ids_or_legacy_outputs": False,
        "route_taxonomy_uses_legacy_fields": False,
    }


def _route_plan(
    *,
    selected_route: str,
    source_families: Sequence[str],
    granularities: Sequence[str],
    reasons: Sequence[str],
    confidence: float,
) -> dict[str, Any]:
    return {
        "selected_route": selected_route,
        "selected_source_family_filter": list(source_families),
        "selected_granularity_filter": list(granularities),
        "route_reasons": list(reasons),
        "route_confidence": round(float(confidence), 6),
        "route_planner_version": WEAVIATE_ROUTE_PLANNER_VERSION,
        "route_uses_gold_fields": False,
        "route_uses_expected_fields": False,
        "route_uses_qrels": False,
        "route_uses_labels": False,
        "route_uses_ids": False,
        "route_uses_legacy_fields": False,
    }


def _source_family_hint_route_plan(source_family_hint: str) -> dict[str, Any] | None:
    hint = _clean(source_family_hint).lower()
    if hint == "text":
        return _route_plan(
            selected_route="text_general",
            source_families=["TEXT"],
            granularities=["paragraph", "heading_context_block", "caption"],
            reasons=["query_evidence_source_family_hint"],
            confidence=0.9,
        )
    if hint == "pdf":
        return _route_plan(
            selected_route="pdf_paragraph",
            source_families=["PDF"],
            granularities=["paragraph", "heading_context_block", "page_block", "caption"],
            reasons=["query_evidence_source_family_hint"],
            confidence=0.9,
        )
    if hint == "xlsx":
        return _route_plan(
            selected_route="xlsx_table",
            source_families=["XLSX"],
            granularities=["table_summary", "table_row", "cell"],
            reasons=["query_evidence_source_family_hint"],
            confidence=0.9,
        )
    return None


def plan_weaviate_retrieval_route(query_text: str, *, source_family_hint: str = "") -> dict[str, Any]:
    hinted = _source_family_hint_route_plan(source_family_hint)
    if hinted is not None:
        hinted["source_family_hint"] = _clean(source_family_hint).lower()
        return hinted
    query = _clean(query_text).casefold()
    if not query:
        return _route_plan(
            selected_route="mixed_fallback",
            source_families=["TEXT", "PDF", "XLSX"],
            granularities=["paragraph", "heading_context_block", "table_summary", "table_row", "caption"],
            reasons=["empty_query_uses_mixed_fallback"],
            confidence=0.2,
        )
    xlsx_hits = bool(
        re.search(
            r"(xlsx|excel|workbook|sheet|worksheet|cell|row|column|table|range|amount|approval|승인|금액|시트|셀|행|열|테이블|기관|우편번호|주소|승차|승객|요양원|장기요양|시도|시군구|법정동|지정)",
            query,
        )
    )
    pdf_hits = bool(
        re.search(
            r"(pdf|page|figure|caption|report|페이지|그림|도표|보고서|수출입차|정관|감사|실업률|전년동월|전년 같은 달|산업활동|생산 지표|광공업|서비스업|건설투자|경제동향)",
            query,
        )
    )
    text_hits = bool(re.search(r"(애니|방영|등장인물|원작|극장판|문서|무엇|어떻게|언제)", query))
    if xlsx_hits and not pdf_hits:
        return _route_plan(
            selected_route="xlsx_table",
            source_families=["XLSX"],
            granularities=["table_summary", "table_row", "cell"],
            reasons=["query_contains_xlsx_table_or_cell_terms"],
            confidence=0.84,
        )
    if pdf_hits and not xlsx_hits:
        route = "pdf_table" if re.search(r"(table|caption|도표|그림)", query) else "pdf_paragraph"
        granularities = ["table_summary", "table_row", "caption"] if route == "pdf_table" else [
            "paragraph",
            "heading_context_block",
            "page_block",
            "caption",
        ]
        return _route_plan(
            selected_route=route,
            source_families=["PDF"],
            granularities=granularities,
            reasons=["query_contains_pdf_document_locator_terms"],
            confidence=0.78,
        )
    if text_hits and not xlsx_hits and not pdf_hits:
        if query in {"문서에 적힌 주요 내용은 무엇인가요?", "문서의 주요 내용은 무엇인가요?"}:
            return _route_plan(
                selected_route="mixed_fallback",
                source_families=["TEXT", "PDF", "XLSX"],
                granularities=["paragraph", "heading_context_block", "table_summary", "table_row", "caption"],
                reasons=["generic_document_query_without_source_family_signal"],
                confidence=0.35,
            )
        return _route_plan(
            selected_route="text_general",
            source_families=["TEXT"],
            granularities=["paragraph", "heading_context_block", "caption"],
            reasons=["query_contains_general_text_entity_or_fact_terms"],
            confidence=0.72,
        )
    return _route_plan(
        selected_route="mixed_fallback",
        source_families=["TEXT", "PDF", "XLSX"],
        granularities=["paragraph", "heading_context_block", "table_summary", "table_row", "caption"],
        reasons=["ambiguous_or_cross_family_query"],
        confidence=0.42,
    )


def _apply_query_alias_replacements(query: str, replacements: Mapping[str, str]) -> str:
    normalized_replacements = {
        _clean(source): _clean(replacement)
        for source, replacement in replacements.items()
        if _clean(source) and _clean(replacement)
    }
    normalized_query = _clean(query)
    if not normalized_replacements:
        return " ".join(normalized_query.split())

    parts: list[str] = []
    last_end = 0
    replaced = False
    for match in re.finditer(r"[A-Za-z0-9][A-Za-z0-9'_-]*|[가-힣]+", normalized_query):
        source = _query_content_term(match.group(0))
        replacement = normalized_replacements.get(source)
        if not replacement:
            continue
        parts.append(normalized_query[last_end : match.start()])
        parts.append(replacement)
        last_end = match.end()
        replaced = True
    if not replaced:
        return " ".join(normalized_query.split())
    parts.append(normalized_query[last_end:])
    return " ".join("".join(parts).split())


def _strip_korean_query_particle(token: str) -> str:
    cleaned = _clean(token)
    for suffix in WEAVIATE_KOREAN_QUERY_PARTICLES:
        if cleaned.endswith(suffix) and len(cleaned) > len(suffix):
            return cleaned[: -len(suffix)]
    return cleaned


def _korean_sino_number_to_int(token: str) -> int | None:
    cleaned = _strip_korean_query_particle(token)
    if not cleaned:
        return None
    if cleaned in WEAVIATE_KOREAN_SINO_DIGITS:
        return WEAVIATE_KOREAN_SINO_DIGITS[cleaned]
    if cleaned == "십":
        return 10
    if "십" not in cleaned:
        return None
    tens_text, ones_text = cleaned.split("십", 1)
    if tens_text:
        tens = WEAVIATE_KOREAN_SINO_DIGITS.get(tens_text)
        if tens is None:
            return None
    else:
        tens = 1
    if ones_text:
        ones = WEAVIATE_KOREAN_SINO_DIGITS.get(ones_text)
        if ones is None:
            return None
    else:
        ones = 0
    return tens * 10 + ones


def _query_terms(query: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]*|[가-힣]+", _clean(query))


def _query_content_term(term: str) -> str:
    cleaned = _strip_korean_query_particle(term)
    if not cleaned or cleaned in WEAVIATE_QUERY_CONTENT_STOPWORDS:
        return ""
    return cleaned


def _query_term_aliases(term: str) -> tuple[str, ...]:
    cleaned = _strip_korean_query_particle(term)
    aliases: list[str] = []
    number = _korean_sino_number_to_int(cleaned)
    if number is not None:
        numeric = str(number)
        aliases.append(numeric)
        if 10 <= number <= 99:
            aliases.append(f"'{numeric}")
    unique: list[str] = []
    for alias in aliases:
        normalized = _clean(alias)
        if normalized and normalized not in unique and normalized != cleaned:
            unique.append(normalized)
    return tuple(unique)


def _punctuation_normalized_query_variant(query: str) -> str:
    normalized = " ".join(_clean(query).split())
    normalized = re.sub(r"(?<=[^\s'])\s+(\d{2})(?=\b)", r" '\1", normalized)
    normalized = re.sub(r"\s+([,.?:;])", r"\1", normalized)
    return " ".join(normalized.split())


def _alias_anchor_for_term(alias: str) -> str:
    return _punctuation_normalized_query_variant(alias)


def _compact_query_anchor_variants(term_aliases: Sequence[Mapping[str, Any]]) -> list[tuple[str, str]]:
    anchor_terms: list[dict[str, str]] = []
    for entry in term_aliases:
        alias = _alias_anchor_for_term(_clean(entry.get("primary_alias")))
        if not alias:
            continue
        kind = _clean(entry.get("kind")) or "alias"
        if kind == "number" and re.fullmatch(r"\d{2}", alias):
            alias = f"'{alias}"
        anchor_terms.append({"alias": alias, "kind": kind})
    if len(anchor_terms) < 2:
        return []

    variants: list[tuple[str, str]] = []
    compact_terms = [entry["alias"] for entry in anchor_terms]
    compact_query = _punctuation_normalized_query_variant(" ".join(compact_terms))
    if compact_query:
        variants.append((compact_query, "punctuation_normalized_anchor_query"))
    return variants


def plan_weaviate_query_variants(query_text: str) -> dict[str, Any]:
    query = _clean(query_text)
    variants: list[str] = []
    reasons: list[str] = []
    normalization_policies: list[str] = []

    def add_variant(variant: str, reason: str) -> None:
        cleaned = _punctuation_normalized_query_variant(variant) if reason.endswith("anchor_query") else _clean(variant)
        if not cleaned or cleaned in variants or len(variants) >= WEAVIATE_MAX_QUERY_VARIANTS:
            return
        variants.append(cleaned)
        if reason not in reasons:
            reasons.append(reason)

    def add_policy(policy: str) -> None:
        if policy not in normalization_policies:
            normalization_policies.append(policy)

    add_variant(query, "original_query")
    if not query:
        return {
            "version": WEAVIATE_QUERY_REFORMULATION_VERSION,
            "enabled": False,
            "query_variants": variants,
            "query_variant_count": len(variants),
            "max_query_variants": WEAVIATE_MAX_QUERY_VARIANTS,
            "query_variant_merge_policy": WEAVIATE_QUERY_VARIANT_MERGE_POLICY,
            "input_policy": WEAVIATE_QUERY_REFORMULATION_INPUT_POLICY,
            "candidate_generation_input_policy": WEAVIATE_CANDIDATE_INPUT_POLICY,
            "uses_gold_fields": False,
            "uses_expected_fields": False,
            "uses_qrels": False,
            "uses_labels": False,
            "uses_ids": False,
            "uses_baseline_topk": False,
            "uses_legacy_outputs": False,
            "normalization_policies": normalization_policies,
            "reasons": reasons,
        }

    replacement_terms: list[dict[str, Any]] = []
    anchor_terms: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for term in _query_terms(query):
        source = _query_content_term(term)
        if not source or source in seen_sources:
            continue
        seen_sources.add(source)
        aliases = _query_term_aliases(source)
        kind = "number" if _korean_sino_number_to_int(source) is not None else "alias"
        primary_anchor = aliases[-1] if aliases else source
        anchor_terms.append({"source": source, "aliases": aliases, "primary_alias": primary_anchor, "kind": kind})
        if aliases:
            replacement_terms.append({"source": source, "aliases": aliases, "primary_alias": aliases[0], "kind": kind})
        if kind == "number":
            add_policy("korean_sino_number_normalization")

    if replacement_terms:
        primary_replacements = {
            _clean(entry["source"]): _clean(entry["primary_alias"])
            for entry in replacement_terms
            if _clean(entry.get("source")) and _clean(entry.get("primary_alias"))
        }
        primary_variant = _apply_query_alias_replacements(query, primary_replacements)
        add_variant(primary_variant, "primary_query_alias_expansion")
        punctuated_primary = _punctuation_normalized_query_variant(primary_variant)
        if punctuated_primary != primary_variant:
            add_policy("punctuation_normalization")
            add_variant(punctuated_primary, "punctuation_normalization")
        for entry in replacement_terms:
            source = _clean(entry["source"])
            for alias in entry["aliases"]:
                add_variant(
                    _apply_query_alias_replacements(query, {source: alias}),
                    f"single_query_alias:{source}",
                )
    if anchor_terms and replacement_terms:
        for anchor_variant, reason in _compact_query_anchor_variants(anchor_terms):
            if anchor_variant != query:
                add_policy("punctuation_normalization")
                add_policy("query_text_only_content_anchor_compaction")
            if reason == "collision_aware_anchor_query":
                add_policy("collision_aware_query_formulation")
            add_variant(anchor_variant, reason)

    return {
        "version": WEAVIATE_QUERY_REFORMULATION_VERSION,
        "enabled": len(variants) > 1,
        "query_variants": variants,
        "query_variant_count": len(variants),
        "max_query_variants": WEAVIATE_MAX_QUERY_VARIANTS,
        "query_variant_merge_policy": WEAVIATE_QUERY_VARIANT_MERGE_POLICY,
        "input_policy": WEAVIATE_QUERY_REFORMULATION_INPUT_POLICY,
        "candidate_generation_input_policy": WEAVIATE_CANDIDATE_INPUT_POLICY,
        "uses_gold_fields": False,
        "uses_expected_fields": False,
        "uses_qrels": False,
        "uses_labels": False,
        "uses_ids": False,
        "uses_baseline_topk": False,
        "uses_legacy_outputs": False,
        "normalization_policies": normalization_policies,
        "reasons": reasons,
    }


def _require_source_atom_record(record: Mapping[str, Any]) -> None:
    missing = [
        field
        for field in (
            "source_atom_id",
            "doc_id",
            "chunk_id",
            "source_family",
            "granularity",
            "retrieval_route",
            "text",
            "text_sha256",
            "namespace",
            "visibility",
        )
        if not _clean(record.get(field))
    ]
    if missing:
        raise ValueError(f"weaviate SourceAtom record missing required fields: {missing}")
    _raise_forbidden_candidate_fields(record)


def source_atom_record_from_mapping(row: Mapping[str, Any], config: WeaviateSourceAtomConfig) -> dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    _raise_forbidden_candidate_fields(row, metadata)
    source_text = _clean(row.get("text") or row.get("bm25_text") or row.get("embedding_text"))
    source_owned_text_tags = _source_owned_text_tags(source_text)
    text = _strip_source_owned_forbidden_searchable_text_tags(source_text)
    source_atom_id = _clean(row.get("source_atom_id") or metadata.get("source_atom_id"))
    evidence_bundle_id = _clean(row.get("evidence_bundle_id") or metadata.get("evidence_bundle_id"))
    taxonomy = derive_weaviate_route_taxonomy(row)
    text_sha256 = (
        _sha256_text(text)
        if config.schema_version == WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2
        else _clean(row.get("text_sha256") or metadata.get("source_text_sha256") or _sha256_text(text))
    )
    record = {
        "source_atom_id": source_atom_id,
        "evidence_bundle_id": evidence_bundle_id,
        "doc_id": _clean(row.get("doc_id") or row.get("document_id") or metadata.get("doc_id") or metadata.get("source_safe_id")),
        "chunk_id": _clean(row.get("chunk_id") or row.get("unit_id") or source_atom_id),
        "source_family": taxonomy["source_family"],
        "granularity": _clean(taxonomy["granularity"]),
        "retrieval_route": _clean(taxonomy["retrieval_route"]),
        "vectorized_semantic_content": "true" if taxonomy["vectorized_semantic_content"] else "false",
        "source_track": _clean(row.get("source_track") or metadata.get("source_track") or "actual_rag_eval"),
        "title": _clean(row.get("title") or metadata.get("title")),
        "section": _clean(row.get("section") or metadata.get("section")),
        "text": text,
        "text_sha256": text_sha256,
        "source_uri_hash": _clean(row.get("source_uri_hash") or metadata.get("source_uri_hash")),
        "source_hash": _clean(row.get("source_hash") or metadata.get("source_hash")),
        "ingestion_run_id": _clean(row.get("ingestion_run_id") or metadata.get("ingestion_run_id") or "actual_rag_eval_nonprod"),
        "ingestion_version": _clean(row.get("ingestion_version") or metadata.get("ingestion_version") or "v1"),
        "namespace": _clean(row.get("namespace") or metadata.get("namespace") or config.namespace),
        "visibility": _clean(row.get("visibility") or metadata.get("visibility") or config.visibility),
        "created_at": _clean(row.get("created_at") or metadata.get("created_at")),
        "updated_at": _clean(row.get("updated_at") or metadata.get("updated_at")),
    }
    if config.schema_version == WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2:
        record["vectorization_policy"] = _clean(taxonomy["vectorization_policy"])
        for key in (
            "workbook_id",
            "workbook_version_id",
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
            "display_value",
            "candidate_surface_materialization",
            "candidate_surface_materialization_policy",
            "page_number",
            "physical_page_index",
            "block_index",
            "bbox",
            "region_type",
            "section_title",
            "table_caption",
            "locator_fingerprint",
            "parent_source_unit_id",
        ):
            value = _clean(row.get(key) or metadata.get(key) or source_owned_text_tags.get(key))
            if value:
                record[key] = value
        source_date_aliases_json = _clean_text_list_json(
            row.get("source_date_aliases_json")
            or metadata.get("source_date_aliases_json")
            or row.get("source_date_aliases")
            or metadata.get("source_date_aliases")
        )
        if source_date_aliases_json:
            record["source_date_aliases_json"] = source_date_aliases_json
        same_row_period_cells_json = _clean_same_row_period_cells_json(
            row.get("same_row_period_cells_json")
            or metadata.get("same_row_period_cells_json")
            or row.get("same_row_period_cells")
            or metadata.get("same_row_period_cells")
        )
        if same_row_period_cells_json:
            record["same_row_period_cells_json"] = same_row_period_cells_json
        source_atom_ids_json = _clean_text_list_json(
            row.get("source_atom_ids_json")
            or metadata.get("source_atom_ids_json")
            or row.get("source_atom_ids")
            or metadata.get("source_atom_ids")
        )
        if source_atom_ids_json:
            record["source_atom_ids_json"] = source_atom_ids_json
    _require_source_atom_record(record)
    return record


def _increment_count(counts: dict[str, int], value: Any, *, default: str) -> None:
    key = _clean(value) or default
    counts[key] = counts.get(key, 0) + 1


def _schema_v2_metadata_only_supported(config: WeaviateSourceAtomConfig) -> bool:
    return _clean(config.schema_version) == WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2


def _record_should_be_vectorized(record: Mapping[str, Any], config: WeaviateSourceAtomConfig) -> bool:
    if not _schema_v2_metadata_only_supported(config):
        return True
    if _clean(record.get("vectorized_semantic_content")).casefold() == "false":
        return False
    return _clean(record.get("granularity")) in WEAVIATE_VECTORIZED_GRANULARITIES


def _split_records_by_vectorization(
    records: Sequence[Mapping[str, Any]],
    config: WeaviateSourceAtomConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    vectorized: list[dict[str, Any]] = []
    metadata_only: list[dict[str, Any]] = []
    for record in records:
        row = dict(record)
        if _record_should_be_vectorized(row, config):
            vectorized.append(row)
        else:
            metadata_only.append(row)
    return vectorized, metadata_only


def _count_records_by_route_fields(records: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    granularity_counts: dict[str, int] = {}
    source_family_counts: dict[str, int] = {}
    for record in records:
        _increment_count(granularity_counts, record.get("granularity"), default="unknown")
        _increment_count(source_family_counts, record.get("source_family"), default="UNKNOWN")
    return {
        "granularity": granularity_counts,
        "source_family": source_family_counts,
    }


def _vectorization_policy_report_from_counts(
    *,
    index_object_count: int,
    vectorized_object_count: int,
    vectorized_by_granularity: Mapping[str, int],
    vectorized_by_source_family: Mapping[str, int],
    metadata_only_object_count: int = 0,
    metadata_only_by_granularity: Mapping[str, int] | None = None,
    metadata_only_by_source_family: Mapping[str, int] | None = None,
    current_index_vectorizes_all_source_atoms: bool = True,
) -> dict[str, Any]:
    object_count = max(0, int(index_object_count))
    vector_count = max(0, int(vectorized_object_count))
    metadata_only_count = max(0, int(metadata_only_object_count))
    granularity_counts = {
        _clean(key): int(value)
        for key, value in sorted(vectorized_by_granularity.items())
        if _clean(key) and int(value) > 0
    }
    source_family_counts = {
        _clean(key): int(value)
        for key, value in sorted(vectorized_by_source_family.items())
        if _clean(key) and int(value) > 0
    }
    actual_metadata_only_counts = {
        _clean(key): int(value)
        for key, value in sorted((metadata_only_by_granularity or {}).items())
        if _clean(key) and int(value) > 0
    }
    actual_metadata_only_source_family_counts = {
        _clean(key): int(value)
        for key, value in sorted((metadata_only_by_source_family or {}).items())
        if _clean(key) and int(value) > 0
    }
    metadata_only_recommended_counts: dict[str, int] = {}
    for key, value in granularity_counts.items():
        if key in WEAVIATE_METADATA_ONLY_GRANULARITIES:
            metadata_only_recommended_counts[key] = metadata_only_recommended_counts.get(key, 0) + int(value)
    for key, value in actual_metadata_only_counts.items():
        if key in WEAVIATE_METADATA_ONLY_GRANULARITIES:
            metadata_only_recommended_counts[key] = metadata_only_recommended_counts.get(key, 0) + int(value)
    rebuild_required = bool(current_index_vectorizes_all_source_atoms and metadata_only_recommended_counts)
    route_taxonomy_filterable_fields = [
        "source_family",
        "granularity",
        "retrieval_route",
        "vectorized_semantic_content",
    ]
    if not current_index_vectorizes_all_source_atoms:
        route_taxonomy_filterable_fields.append("candidate_surface_materialization")
    return {
        "route_taxonomy_available": True,
        "route_taxonomy_version": WEAVIATE_ROUTE_TAXONOMY_VERSION,
        "route_taxonomy_filterable_fields": route_taxonomy_filterable_fields,
        "source_family_filterable": True,
        "granularity_filterable": True,
        "retrieval_route_filterable": True,
        "index_object_count": object_count,
        "vectorized_object_count": vector_count,
        "metadata_only_object_count": metadata_only_count,
        "vectorized_object_ratio": round(float(vector_count) / float(object_count), 6) if object_count else 0.0,
        "vectorized_by_granularity": granularity_counts,
        "vectorized_by_source_family": source_family_counts,
        "metadata_only_by_granularity": actual_metadata_only_counts,
        "metadata_only_by_source_family": actual_metadata_only_source_family_counts,
        "metadata_only_recommended_granularity_counts": metadata_only_recommended_counts,
        "schema_index_v2_rebuild_required_for_metadata_only_policy": rebuild_required,
        "vectorization_policy": {
            "policy_version": "weaviate_source_atom_vectorization_policy_v1",
            "current_index_vectorizes_all_source_atoms": bool(current_index_vectorizes_all_source_atoms),
            "vectorized_by_default": sorted(WEAVIATE_VECTORIZED_GRANULARITIES),
            "metadata_only_by_default": sorted(WEAVIATE_METADATA_ONLY_POLICY_OBJECT_TYPES),
            "schema_index_v2_required_to_stop_vectorizing_metadata_only_objects": rebuild_required,
            "index_time_metadata_only_supported": not current_index_vectorizes_all_source_atoms,
        },
    }


def _vectorization_policy_report(records: Sequence[Mapping[str, Any]], *, vectorized_object_count: int | None = None) -> dict[str, Any]:
    granularity_counts: dict[str, int] = {}
    source_family_counts: dict[str, int] = {}
    for record in records:
        _increment_count(granularity_counts, record.get("granularity"), default="unknown")
        _increment_count(source_family_counts, record.get("source_family"), default="UNKNOWN")
    object_count = len(records)
    return _vectorization_policy_report_from_counts(
        index_object_count=object_count,
        vectorized_object_count=object_count if vectorized_object_count is None else int(vectorized_object_count),
        vectorized_by_granularity=granularity_counts,
        vectorized_by_source_family=source_family_counts,
    )


def _context_from_record(record: Mapping[str, Any], *, rank: int, score: float, backend: str) -> dict[str, Any]:
    text = _clean(record.get("text"))
    text_sha = _clean(record.get("text_sha256")) or _sha256_text(text)
    return {
        "rank": int(rank),
        "doc_id": _clean(record.get("doc_id")),
        "chunk_id": _clean(record.get("chunk_id")),
        "score": round(float(score), 6),
        "text": text,
        "retrieval_backend": backend,
        "retrieval_surface": "source_native",
        "source_family": _clean(record.get("source_family")),
        "granularity": _clean(record.get("granularity")),
        "retrieval_route": _clean(record.get("retrieval_route")),
        "source_atom_id": _clean(record.get("source_atom_id")),
        "evidence_bundle_id": _clean(record.get("evidence_bundle_id")),
        "title": _clean(record.get("title")),
        "section": _clean(record.get("section")),
        "source_text_sha256": text_sha,
        "text_sha256": text_sha,
        "weaviate_object_id": _clean(record.get("uuid") or record.get("_uuid")),
        "workbook_id": _clean(record.get("workbook_id")),
        "workbook_version_id": _clean(record.get("workbook_version_id")),
        "sheet": _clean(record.get("sheet")),
        "cell_range": _clean(record.get("cell_range")),
        "cell": _clean(record.get("cell")),
        "row_index_1based": _clean(record.get("row_index_1based")),
        "row_label": _clean(record.get("row_label")),
        "column_label": _clean(record.get("column_label")),
        "target_column": _clean(record.get("target_column")),
        "header": _clean(record.get("header")),
        "header_path": _clean(record.get("header_path")),
        "table_id": _clean(record.get("table_id")),
        "display_value": _clean(record.get("display_value")),
        "candidate_surface_materialization": _clean(record.get("candidate_surface_materialization")),
        "candidate_surface_materialization_policy": _clean(record.get("candidate_surface_materialization_policy")),
        "source_date_aliases_json": _clean(record.get("source_date_aliases_json")),
        "same_row_period_cells_json": _clean(record.get("same_row_period_cells_json")),
        "source_atom_ids_json": _clean(record.get("source_atom_ids_json")),
        "page_number": _clean(record.get("page_number")),
        "physical_page_index": _clean(record.get("physical_page_index")),
        "block_index": _clean(record.get("block_index")),
        "bbox": _clean(record.get("bbox")),
        "region_type": _clean(record.get("region_type")),
        "section_title": _clean(record.get("section_title")),
        "table_caption": _clean(record.get("table_caption")),
        "locator_fingerprint": _clean(record.get("locator_fingerprint")),
        "parent_source_unit_id": _clean(record.get("parent_source_unit_id")),
    }


def _context_to_chunk(context: Mapping[str, Any]) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=_clean(context.get("chunk_id")) or f"rank-{context.get('rank')}",
        doc_id=_clean(context.get("doc_id")) or "unknown-doc",
        section=_clean(context.get("section")) or _clean(context.get("chunk_id")) or "context",
        text=_clean(context.get("text")),
        score=float(context.get("score") or 0.0),
    )


def _normalize_citation(context: Mapping[str, Any]) -> dict[str, Any]:
    normalized = {
        "doc_id": _clean(context.get("doc_id")),
        "chunk_id": _clean(context.get("chunk_id")),
        "text": _clean(context.get("text")),
        "source_atom_id": _clean(context.get("source_atom_id")),
        "evidence_bundle_id": _clean(context.get("evidence_bundle_id")),
        "source_text_sha256": _clean(context.get("source_text_sha256") or context.get("text_sha256")),
        "text_sha256": _clean(context.get("text_sha256") or context.get("source_text_sha256")),
    }
    for field in WEAVIATE_SOURCE_ATOM_V2_EXTRA_PROPERTIES:
        value = _clean(context.get(field))
        if value:
            normalized[field] = value
    return normalized


def _latency_distribution_ms(values: Sequence[float]) -> dict[str, float]:
    numeric = sorted(float(value) for value in values if isinstance(value, (int, float)))
    if not numeric:
        return {"p50": 0.0, "p95": 0.0}
    midpoint = len(numeric) // 2
    p50 = numeric[midpoint] if len(numeric) % 2 else (numeric[midpoint - 1] + numeric[midpoint]) / 2
    p95_index = min(len(numeric) - 1, max(0, int(len(numeric) * 0.95 + 0.999999) - 1))
    return {"p50": round(float(p50), 6), "p95": round(float(numeric[p95_index]), 6)}


def _average(values: Sequence[int | float]) -> float:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(numeric) / len(numeric), 6) if numeric else 0.0


def _preview(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rank": context.get("rank"),
        "doc_id": _clean(context.get("doc_id")),
        "chunk_id": _clean(context.get("chunk_id")),
        "score": context.get("score"),
        "retrieval_backend": _clean(context.get("retrieval_backend")),
        "source_family": _clean(context.get("source_family")),
        "granularity": _clean(context.get("granularity")),
        "retrieval_route": _clean(context.get("retrieval_route")),
        "text_sha256": _sha256_text(context.get("text")),
        "text_preview": _clean(context.get("text"))[:180],
    }


def _comparison(
    *,
    requested_backend: str,
    selected_backend: str,
    bm25_contexts: Sequence[Mapping[str, Any]],
    vector_contexts: Sequence[Mapping[str, Any]],
    hybrid_contexts: Sequence[Mapping[str, Any]],
    selected_contexts: Sequence[Mapping[str, Any]],
    bm25_latency_ms: float,
    vector_latency_ms: float,
    hybrid_latency_ms: float,
    vector_dim: int,
    embedding_model: str,
) -> dict[str, Any]:
    return {
        "requested_backend": requested_backend,
        "selected_backend": selected_backend,
        "bm25_top_k": [_preview(row) for row in bm25_contexts],
        "vector_top_k": [_preview(row) for row in vector_contexts],
        "hybrid_top_k": [_preview(row) for row in hybrid_contexts],
        "selected_top_k": [_preview(row) for row in selected_contexts],
        "bm25_top_k_count": len(bm25_contexts),
        "vector_top_k_count": len(vector_contexts),
        "hybrid_top_k_count": len(hybrid_contexts),
        "candidate_counts": {
            "bm25": len(bm25_contexts),
            "vector": len(vector_contexts),
            "hybrid": len(hybrid_contexts),
            "selected": len(selected_contexts),
        },
        "latency_ms": {
            "bm25": round(float(bm25_latency_ms), 6),
            "vector": round(float(vector_latency_ms), 6),
            "hybrid": round(float(hybrid_latency_ms), 6),
        },
        "overlap_counts": {"bm25_vector_topk": 0},
        "bm25_vector_topk_overlap_count": 0,
        "vector_available": True,
        "vector_fallback_reason": "",
        "candidate_generation_input_policy": WEAVIATE_CANDIDATE_INPUT_POLICY,
        "source_native_vector_invocation": {
            "vector_backend_invoked": selected_backend in {"weaviate_vector", "weaviate_hybrid"},
            "query_embedding_created_or_loaded": selected_backend in {"weaviate_vector", "weaviate_hybrid"},
            "query_embedding_model": embedding_model,
            "query_embedding_dim": int(vector_dim),
            "vector_top_k_count": len(vector_contexts) or len(hybrid_contexts),
            "vector_latency_ms": round(float(vector_latency_ms or hybrid_latency_ms), 6),
            "vector_candidate_doc_ids": [_clean(row.get("doc_id")) for row in (vector_contexts or hybrid_contexts)],
            "vector_candidate_chunk_ids": [_clean(row.get("chunk_id")) for row in (vector_contexts or hybrid_contexts)],
            "vector_candidate_scores": [round(float(row.get("score") or 0.0), 6) for row in (vector_contexts or hybrid_contexts)],
            "vector_candidate_text_hashes": [_sha256_text(row.get("text")) for row in (vector_contexts or hybrid_contexts)],
            "vector_hydration_success_count": len(vector_contexts) or len(hybrid_contexts),
            "vector_hydration_failure_count": 0,
            "vector_candidate_generation_input_policy": WEAVIATE_CANDIDATE_INPUT_POLICY,
        },
    }


class FakeWeaviateSourceAtomClient:
    def __init__(self, *, objects: Sequence[Mapping[str, Any]] | None = None, available: bool = True) -> None:
        self.objects = [dict(obj) for obj in objects or []]
        self.available = bool(available)
        self.query_log: list[dict[str, Any]] = []
        self.upsert_log: list[dict[str, Any]] = []
        self.metadata_only_upsert_log: list[dict[str, Any]] = []
        self.schema_log: list[dict[str, Any]] = []
        self.recreate_schema_log: list[dict[str, Any]] = []
        self.local_scan_used = False

    def ping(self) -> bool:
        if not self.available:
            raise WeaviateUnavailableError("weaviate_unavailable: fake client unavailable")
        return True

    def ensure_collection(self, schema: Mapping[str, Any]) -> None:
        if not self.available:
            raise WeaviateUnavailableError("weaviate_unavailable: fake client unavailable")
        self.schema_log.append(dict(schema))

    def recreate_collection(self, schema: Mapping[str, Any]) -> None:
        if not self.available:
            raise WeaviateUnavailableError("weaviate_unavailable: fake client unavailable")
        self.recreate_schema_log.append(dict(schema))
        self.objects.clear()

    def upsert_many(self, objects: Sequence[Mapping[str, Any]], vectors: Sequence[Sequence[float]]) -> int:
        if not self.available:
            raise WeaviateUnavailableError("weaviate_unavailable: fake client unavailable")
        count = 0
        for obj, vector in zip(objects, vectors, strict=True):
            row = dict(obj)
            row["_vector_dim"] = len(vector)
            self.objects.append(row)
            count += 1
        self.upsert_log.append(
            {
                "count": count,
                "objects": [dict(obj) for obj in objects],
                "vectors": [list(vector) for vector in vectors],
            }
        )
        return count

    def upsert_many_metadata_only(self, objects: Sequence[Mapping[str, Any]]) -> int:
        if not self.available:
            raise WeaviateUnavailableError("weaviate_unavailable: fake client unavailable")
        count = 0
        for obj in objects:
            row = dict(obj)
            row["_vector_dim"] = 0
            row["_metadata_only_no_vector"] = True
            self.objects.append(row)
            count += 1
        self.metadata_only_upsert_log.append(
            {
                "count": count,
                "objects": [dict(obj) for obj in objects],
            }
        )
        return count

    def query(
        self,
        *,
        mode: str,
        query_text: str,
        query_vector: Sequence[float] | None,
        filters: Mapping[str, Any],
        limit: int,
        alpha: float,
    ) -> list[dict[str, Any]]:
        if not self.available:
            raise WeaviateUnavailableError("weaviate_unavailable: fake client unavailable")
        self.query_log.append(
            {
                "mode": mode,
                "query_text": query_text,
                "vector_dim": len(query_vector or []),
                "filters": dict(filters),
                "limit": int(limit),
                "alpha": float(alpha),
            }
        )
        def matches(obj: Mapping[str, Any], key: str, value: Any) -> bool:
            if key == "neighbor_granularity":
                return True
            if not value:
                return True
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                return _clean(obj.get(key)) in {_clean(item) for item in value if _clean(item)}
            return _clean(obj.get(key)) == _clean(value)

        if mode == "neighbor_by_id":
            anchor_id = _clean(filters.get("source_atom_id"))
            neighbor_granularity = _clean(filters.get("neighbor_granularity"))
            anchor = next((obj for obj in self.objects if _clean(obj.get("source_atom_id")) == anchor_id), None)
            filtered = []
            if anchor is not None:
                for obj in self.objects:
                    if _clean(obj.get("source_atom_id")) == anchor_id:
                        continue
                    if _clean(obj.get("namespace")) != _clean(anchor.get("namespace")):
                        continue
                    if _clean(obj.get("visibility")) != _clean(anchor.get("visibility")):
                        continue
                    if _clean(obj.get("doc_id")) != _clean(anchor.get("doc_id")):
                        continue
                    if neighbor_granularity and _clean(obj.get("granularity")) != neighbor_granularity:
                        continue
                    if _clean(anchor.get("sheet")) and _clean(obj.get("sheet")) != _clean(anchor.get("sheet")):
                        continue
                    if _clean(anchor.get("cell_range")) and _clean(obj.get("cell_range")) != _clean(anchor.get("cell_range")):
                        continue
                    if _clean(anchor.get("page_number")) and _clean(obj.get("page_number")) != _clean(anchor.get("page_number")):
                        continue
                    filtered.append(dict(obj))
        else:
            filtered = [dict(obj) for obj in self.objects if all(matches(obj, key, value) for key, value in filters.items())]
        rows: list[dict[str, Any]] = []
        for index, obj in enumerate(filtered[: max(0, int(limit))], start=1):
            row = dict(obj)
            row["_score"] = round(1.0 / index, 6)
            row["_backend"] = mode
            rows.append(row)
        return rows

    def close(self) -> None:
        return None


class WeaviateSourceAtomClient:
    def __init__(self, config: WeaviateSourceAtomConfig) -> None:
        self.config = config
        self._client: Any | None = None
        self._collection: Any | None = None

    def _connect(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import weaviate  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on optional package
            raise WeaviateUnavailableError(f"weaviate_unavailable: weaviate-client import failed:{type(exc).__name__}: {exc}") from exc
        parsed = urlparse(self.config.url)
        host = parsed.hostname or "localhost"
        port = int(parsed.port or 8080)
        try:
            if host in {"localhost", "127.0.0.1", "::1"} and not self.config.api_key:
                self._client = weaviate.connect_to_local(host=host, port=port, grpc_port=self.config.grpc_port)
            else:
                auth = None
                if self.config.api_key:
                    auth_cls = getattr(getattr(weaviate, "classes", object()), "init", None)
                    try:
                        from weaviate.auth import AuthApiKey  # type: ignore

                        auth = AuthApiKey(self.config.api_key)
                    except Exception:
                        auth = self.config.api_key if auth_cls is None else auth_cls.Auth.api_key(self.config.api_key)
                self._client = weaviate.connect_to_weaviate_cloud(cluster_url=self.config.url, auth_credentials=auth)
        except Exception as exc:  # pragma: no cover - depends on live service
            raise WeaviateUnavailableError(f"weaviate_unavailable: connect failed:{type(exc).__name__}: {exc}") from exc
        return self._client

    def _use_collection(self) -> Any:
        if self._collection is None:
            client = self._connect()
            self._collection = client.collections.use(self.config.collection_name)
        return self._collection

    def ping(self) -> bool:
        client = self._connect()
        try:
            return bool(client.is_ready())
        except Exception as exc:  # pragma: no cover - depends on live service
            raise WeaviateUnavailableError(f"weaviate_unavailable: readiness failed:{type(exc).__name__}: {exc}") from exc

    def _existing_collection_schema_mismatches(self, schema: Mapping[str, Any], collection: Any) -> list[str]:
        def enum_text(value: Any) -> str:
            return _clean(getattr(value, "value", value)).casefold()

        def bool_attr(value: Any, *names: str) -> bool:
            for name in names:
                if hasattr(value, name):
                    return bool(getattr(value, name))
            return False

        try:
            config = collection.config.get()
            existing_props = {
                _clean(getattr(prop, "name", "")): prop
                for prop in getattr(config, "properties", []) or []
                if _clean(getattr(prop, "name", ""))
            }
            mismatches: list[str] = []
            for prop in schema.get("properties") or []:
                name = _clean(prop.get("name"))
                existing = existing_props.get(name)
                if existing is None:
                    mismatches.append(f"missing_property:{name}")
                    continue
                if bool_attr(existing, "index_filterable", "indexFilterable") != bool(prop.get("index_filterable")):
                    mismatches.append(f"filterable_mismatch:{name}")
                if bool_attr(existing, "index_searchable", "indexSearchable") != bool(prop.get("index_searchable")):
                    mismatches.append(f"searchable_mismatch:{name}")
                if enum_text(getattr(existing, "tokenization", "")) != _clean(prop.get("tokenization")).casefold():
                    mismatches.append(f"tokenization_mismatch:{name}")

            vectorizer_ok = enum_text(getattr(config, "vectorizer", "")) in {"", "none"}
            distance_ok = False
            vector_config = getattr(config, "vector_config", None)
            if isinstance(vector_config, Mapping):
                vector_configs = list(vector_config.values())
            else:
                vector_configs = [vector_config] if vector_config is not None else []
            for vector in vector_configs:
                vectorizer = getattr(getattr(vector, "vectorizer", None), "vectorizer", None)
                if enum_text(vectorizer) == "none":
                    vectorizer_ok = True
                distance = getattr(getattr(vector, "vector_index_config", None), "distance_metric", None)
                if enum_text(distance) == "cosine":
                    distance_ok = True
            if not vectorizer_ok:
                mismatches.append("vectorizer_not_self_provided")
            if vector_configs and not distance_ok:
                mismatches.append("distance_metric_not_cosine")
            return sorted(mismatches)
        except Exception as exc:  # pragma: no cover - depends on live client versions
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: collection_schema_validation_failed:{type(exc).__name__}: {exc}"
            ) from exc

    def _validate_existing_collection(self, schema: Mapping[str, Any], collection: Any) -> None:
        mismatches = self._existing_collection_schema_mismatches(schema, collection)
        if mismatches:
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: collection_schema_mismatch:{','.join(mismatches)}"
            )

    def _missing_existing_collection_property_names(self, schema: Mapping[str, Any], collection: Any) -> list[str]:
        try:
            config = collection.config.get()
            existing_names = {
                _clean(getattr(prop, "name", ""))
                for prop in getattr(config, "properties", []) or []
                if _clean(getattr(prop, "name", ""))
            }
            return [
                name
                for prop in schema.get("properties") or []
                for name in [_clean(prop.get("name"))]
                if name and name not in existing_names
            ]
        except Exception as exc:  # pragma: no cover - depends on live client versions
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: collection_schema_validation_failed:{type(exc).__name__}: {exc}"
            ) from exc

    def _weaviate_property_from_schema(self, prop: Mapping[str, Any]) -> Any:
        from weaviate.classes.config import DataType, Property, Tokenization  # type: ignore

        tokenizations = {
            "field": Tokenization.FIELD,
            "word": Tokenization.WORD,
            "whitespace": Tokenization.WHITESPACE,
            "lowercase": Tokenization.LOWERCASE,
            "trigram": Tokenization.TRIGRAM,
            "kagome_ja": Tokenization.KAGOME_JA,
            "kagome_kr": Tokenization.KAGOME_KR,
        }
        return Property(
            name=prop["name"],
            data_type=DataType.TEXT,
            index_filterable=bool(prop.get("index_filterable")),
            index_searchable=bool(prop.get("index_searchable")),
            tokenization=tokenizations.get(_clean(prop.get("tokenization")).casefold(), Tokenization.WORD),
        )

    def _create_collection(self, client: Any, schema: Mapping[str, Any]) -> None:
        try:
            from weaviate.classes.config import Configure, VectorDistances  # type: ignore

            props = []
            for prop in schema.get("properties") or []:
                props.append(self._weaviate_property_from_schema(prop))
            self._collection = client.collections.create(
                self.config.collection_name,
                properties=props,
                vector_config=Configure.Vectors.self_provided(
                    vector_index_config=Configure.VectorIndex.hnsw(distance_metric=VectorDistances.COSINE)
                ),
            )
        except Exception as exc:  # pragma: no cover - depends on live service/client version
            raise WeaviateUnavailableError(f"weaviate_unavailable: schema create failed:{type(exc).__name__}: {exc}") from exc

    def _add_missing_existing_v2_properties(self, schema: Mapping[str, Any], collection: Any) -> None:
        if _clean(schema.get("schema_version")) != WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2:
            return
        mismatches = self._existing_collection_schema_mismatches(schema, collection)
        missing_names = [
            mismatch.removeprefix("missing_property:")
            for mismatch in mismatches
            if mismatch.startswith("missing_property:")
        ]
        if not missing_names:
            return
        if any(not mismatch.startswith("missing_property:") for mismatch in mismatches):
            return
        allowed_missing = set(WEAVIATE_SOURCE_ATOM_V2_EXTRA_PROPERTIES)
        if any(name not in allowed_missing for name in missing_names):
            return
        by_name = {
            _clean(prop.get("name")): prop
            for prop in schema.get("properties") or []
            if _clean(prop.get("name"))
        }
        try:
            for name in missing_names:
                collection.config.add_property(self._weaviate_property_from_schema(by_name[name]))
        except Exception as exc:  # pragma: no cover - depends on live service/client version
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: schema property add failed:{type(exc).__name__}: {exc}"
            ) from exc

    def ensure_collection(self, schema: Mapping[str, Any]) -> None:
        client = self._connect()
        if client.collections.exists(self.config.collection_name):
            self._collection = client.collections.use(self.config.collection_name)
            self._add_missing_existing_v2_properties(schema, self._collection)
            self._validate_existing_collection(schema, self._collection)
            return
        self._create_collection(client, schema)

    def recreate_collection(self, schema: Mapping[str, Any]) -> None:
        self.config.validate_for_nonprod()
        collection_name = _clean(self.config.collection_name)
        if collection_name != WEAVIATE_ROUTE_SELECTED_CANDIDATE_SURFACE_V2_COLLECTION:
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: collection_recreate_nonprod_candidate_surface_v2_required:{collection_name}"
            )
        try:
            client = self._connect()
            if client.collections.exists(collection_name):
                client.collections.delete(collection_name)
            self._collection = None
            self._create_collection(client, schema)
        except Exception as exc:  # pragma: no cover - depends on live service/client version
            if isinstance(exc, WeaviateUnavailableError):
                raise
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: collection recreate failed:{type(exc).__name__}: {exc}"
            ) from exc

    def upsert_many(self, objects: Sequence[Mapping[str, Any]], vectors: Sequence[Sequence[float]]) -> int:
        collection = self._use_collection()
        count = 0
        try:
            with collection.batch.fixed_size(batch_size=max(1, min(len(objects), 512))) as batch:
                for obj, vector in zip(objects, vectors, strict=True):
                    batch.add_object(
                        properties=dict(obj),
                        vector=list(float(value) for value in vector),
                        uuid=_sha256_text(obj.get("source_atom_id"))[:32],
                    )
                    count += 1
            batch_errors = int(getattr(batch, "number_errors", 0) or 0)
            if batch_errors:
                failed_objects = getattr(batch, "failed_objects", [])
                detail = _clean(failed_objects[:1] if isinstance(failed_objects, list) else failed_objects)
                raise WeaviateUnavailableError(
                    f"weaviate_unavailable: upsert batch reported {batch_errors} failed objects:{detail}"
                )
        except Exception as exc:  # pragma: no cover - depends on live service
            if isinstance(exc, WeaviateUnavailableError):
                raise
            raise WeaviateUnavailableError(f"weaviate_unavailable: upsert failed:{type(exc).__name__}: {exc}") from exc
        return count

    def upsert_many_metadata_only(self, objects: Sequence[Mapping[str, Any]]) -> int:
        collection = self._use_collection()
        if not objects:
            return 0
        count = 0
        try:
            with collection.batch.fixed_size(batch_size=max(1, min(len(objects), 512))) as batch:
                for obj in objects:
                    batch.add_object(
                        properties=dict(obj),
                        uuid=_sha256_text(obj.get("source_atom_id"))[:32],
                    )
                    count += 1
            batch_errors = int(getattr(batch, "number_errors", 0) or 0)
            if batch_errors:
                failed_objects = getattr(batch, "failed_objects", [])
                detail = _clean(failed_objects[:1] if isinstance(failed_objects, list) else failed_objects)
                raise WeaviateUnavailableError(
                    f"weaviate_unavailable: metadata-only upsert batch reported {batch_errors} failed objects:{detail}"
                )
        except Exception as exc:  # pragma: no cover - depends on live service
            if isinstance(exc, WeaviateUnavailableError):
                raise
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: metadata-only upsert failed:{type(exc).__name__}: {exc}"
            ) from exc
        return count

    def _filters(self, filters: Mapping[str, Any]) -> Any:
        try:
            from weaviate.classes.query import Filter  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise WeaviateUnavailableError(f"weaviate_unavailable: filter import failed:{type(exc).__name__}: {exc}") from exc
        built = None
        for key, value in filters.items():
            if not _clean(value):
                continue
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                options = [_clean(item) for item in value if _clean(item)]
                if not options:
                    continue
                clause = None
                for option in options:
                    option_clause = Filter.by_property(key).equal(option)
                    clause = option_clause if clause is None else clause | option_clause
            else:
                clause = Filter.by_property(key).equal(_clean(value))
            built = clause if built is None else built & clause
        return built

    def _metadata_query(self, *, mode: str) -> Any:
        try:
            from weaviate.classes.query import MetadataQuery  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise WeaviateUnavailableError(f"weaviate_unavailable: metadata import failed:{type(exc).__name__}: {exc}") from exc
        if mode == "vector":
            return MetadataQuery(distance=True)
        return MetadataQuery(score=True, explain_score=True)

    def _query_properties_for_filters(self, filters: Mapping[str, Any]) -> list[str]:
        source_family = filters.get("source_family")
        if isinstance(source_family, Sequence) and not isinstance(source_family, (str, bytes, bytearray)):
            families = {_clean(value).upper() for value in source_family if _clean(value)}
        else:
            families = {_clean(source_family).upper()} if _clean(source_family) else set()
        if families == {"TEXT"}:
            return ["text", "title"]
        return ["text"]

    def query(
        self,
        *,
        mode: str,
        query_text: str,
        query_vector: Sequence[float] | None,
        filters: Mapping[str, Any],
        limit: int,
        alpha: float,
    ) -> list[dict[str, Any]]:
        if mode == "neighbor_by_id":
            return self._query_neighbor_by_id(filters=filters, limit=limit)
        collection = self._use_collection()
        where_filter = self._filters(filters)
        query_properties = self._query_properties_for_filters(filters)
        try:
            if mode == "vector":
                response = collection.query.near_vector(
                    near_vector=list(float(value) for value in query_vector or []),
                    limit=limit,
                    filters=where_filter,
                    return_metadata=self._metadata_query(mode=mode),
                )
            elif mode == "bm25":
                response = collection.query.bm25(
                    query=query_text,
                    query_properties=query_properties,
                    limit=limit,
                    filters=where_filter,
                    return_metadata=self._metadata_query(mode=mode),
                )
            elif mode == "hybrid":
                response = collection.query.hybrid(
                    query=query_text,
                    vector=list(float(value) for value in query_vector or []),
                    alpha=alpha,
                    query_properties=query_properties,
                    limit=limit,
                    filters=where_filter,
                    return_metadata=self._metadata_query(mode=mode),
                )
            else:
                raise ValueError(f"unsupported Weaviate query mode: {mode}")
        except Exception as exc:  # pragma: no cover - depends on live service
            raise WeaviateUnavailableError(f"weaviate_unavailable: query failed:{type(exc).__name__}: {exc}") from exc
        rows: list[dict[str, Any]] = []
        for obj in response.objects:
            row = dict(getattr(obj, "properties", {}) or {})
            metadata = getattr(obj, "metadata", None)
            row["_uuid"] = _clean(getattr(obj, "uuid", ""))
            row["_score"] = float(getattr(metadata, "score", 0.0) or 0.0) if metadata is not None else 0.0
            row["_backend"] = mode
            rows.append(row)
        return rows

    def _query_neighbor_by_id(self, *, filters: Mapping[str, Any], limit: int) -> list[dict[str, Any]]:
        anchor_id = _clean(filters.get("source_atom_id"))
        if not anchor_id:
            return []
        collection = self._use_collection()
        try:
            anchor_filter = self._filters(
                {
                    "namespace": filters.get("namespace"),
                    "visibility": filters.get("visibility"),
                    "source_atom_id": anchor_id,
                }
            )
            anchor_response = collection.query.fetch_objects(limit=1, filters=anchor_filter)
            anchors = list(getattr(anchor_response, "objects", []) or [])
            if not anchors:
                return []
            anchor = dict(getattr(anchors[0], "properties", {}) or {})
            neighbor_filters: dict[str, Any] = {
                "namespace": filters.get("namespace"),
                "visibility": filters.get("visibility"),
                "doc_id": anchor.get("doc_id"),
            }
            if _clean(filters.get("neighbor_granularity")):
                neighbor_filters["granularity"] = _clean(filters.get("neighbor_granularity"))
            for key in ("sheet", "cell_range", "page_number"):
                if _clean(anchor.get(key)):
                    neighbor_filters[key] = _clean(anchor.get(key))
            response = collection.query.fetch_objects(limit=max(0, int(limit)) + 1, filters=self._filters(neighbor_filters))
        except Exception as exc:  # pragma: no cover - depends on live service
            raise WeaviateUnavailableError(f"weaviate_unavailable: neighbor query failed:{type(exc).__name__}: {exc}") from exc
        rows: list[dict[str, Any]] = []
        for obj in getattr(response, "objects", []) or []:
            row = dict(getattr(obj, "properties", {}) or {})
            if _clean(row.get("source_atom_id")) == anchor_id:
                continue
            row["_uuid"] = _clean(getattr(obj, "uuid", ""))
            row["_score"] = 0.0
            row["_backend"] = "neighbor_by_id"
            rows.append(row)
            if len(rows) >= max(0, int(limit)):
                break
        return rows

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._collection = None


class BgeM3EmbeddingBuilder:
    def __init__(
        self,
        *,
        embedding_provider: Any | None = None,
        model_name: str = "BAAI/bge-m3",
        device: str = "auto",
        batch_size: int = 32,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.model_name = model_name
        self.device = device
        self.batch_size = int(batch_size)
        self.last_report: dict[str, Any] = {}

    def _provider(self) -> Any:
        if self.embedding_provider is not None:
            return self.embedding_provider
        from app.capabilities.rag.embeddings import SentenceTransformerEmbedder, resolve_max_seq_length

        self.embedding_provider = SentenceTransformerEmbedder(
            model_name=self.model_name,
            max_seq_length=resolve_max_seq_length(int(os.environ.get("ACTUAL_RAG_EVAL_BGE_M3_MAX_SEQ_LENGTH", "1024"))),
            batch_size=self.batch_size,
            show_progress_bar=False,
            local_files_only=True,
        )
        return self.embedding_provider

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        if self.model_name != "BAAI/bge-m3":
            raise WeaviateUnavailableError(f"weaviate_unavailable: embedding_model_must_be_BAAI_bge_m3:{self.model_name}")
        provider = self._provider()
        started = time.perf_counter()
        vectors = provider.embed_passages(list(texts))
        latency_ms = round((time.perf_counter() - started) * 1000, 6)
        rows = _vectors_to_lists(vectors)
        dim = len(rows[0]) if rows else int(getattr(provider, "dimension", 0) or 0)
        provider_device = _clean(getattr(provider, "device", ""))
        model = getattr(provider, "_model", None)
        model_device = _clean(getattr(model, "device", ""))
        self.last_report = {
            "embedding_model": _clean(getattr(provider, "model_name", "")) or self.model_name,
            "embedding_dim": dim,
            "embedding_device": provider_device or model_device or self.device,
            "embedding_batch_size": self.batch_size,
            "embedding_count": len(rows),
            "embedding_latency_ms": latency_ms,
            "embedding_cache_path_hash": "",
            "diagnostic_hash_vector_used": False,
        }
        return rows

    def embed_queries(self, texts: Sequence[str]) -> list[list[float]]:
        provider = self._provider()
        vectors = provider.embed_queries(list(texts))
        return _vectors_to_lists(vectors)


def _vectors_to_lists(vectors: Any) -> list[list[float]]:
    if hasattr(vectors, "tolist"):
        raw = vectors.tolist()
    else:
        raw = vectors
    rows: list[list[float]] = []
    for row in raw:
        rows.append([float(value) for value in row])
    return rows


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    last_error: PermissionError | None = None
    for _ in range(20):
        try:
            temp_path.replace(path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.25)
    if last_error is not None:
        raise last_error


def _batched(rows: Sequence[Mapping[str, Any]], size: int) -> Iterable[Sequence[Mapping[str, Any]]]:
    batch_size = max(1, int(size))
    for start in range(0, len(rows), batch_size):
        yield rows[start : start + batch_size]


class WeaviateSourceAtomIndexer:
    def __init__(
        self,
        *,
        config: WeaviateSourceAtomConfig,
        client: WeaviateSourceAtomClientProtocol | None = None,
        embedding_builder: BgeM3EmbeddingBuilder | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.config = config
        self.client = client or WeaviateSourceAtomClient(config)
        self.embedding_builder = embedding_builder or BgeM3EmbeddingBuilder(
            model_name=config.embedding_model,
            device=config.embedding_device,
        )
        self.progress_callback = progress_callback

    def _load_checkpoint(self, checkpoint_path: Path | None) -> dict[str, Any]:
        if checkpoint_path is None or not checkpoint_path.exists():
            return {}
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: checkpoint_invalid_json:{checkpoint_path.as_posix()}"
            ) from exc
        if not isinstance(checkpoint, Mapping):
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: checkpoint_invalid_payload:{checkpoint_path.as_posix()}"
            )
        if _clean(checkpoint.get("schema_version")) != WEAVIATE_SOURCE_ATOM_INDEX_CHECKPOINT_VERSION:
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: checkpoint_schema_version_mismatch:{checkpoint.get('schema_version')}"
            )
        if _clean(checkpoint.get("index_vector_source")) != WEAVIATE_STREAMING_BGE_M3_VECTOR_SOURCE:
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: checkpoint_vector_source_mismatch:{checkpoint.get('index_vector_source')}"
            )
        if bool(checkpoint.get("diagnostic_hash_vector_used")):
            raise WeaviateUnavailableError("weaviate_unavailable: checkpoint_diagnostic_hash_vector_blocked")
        if bool(checkpoint.get("faiss_used_for_index_seed")):
            raise WeaviateUnavailableError("weaviate_unavailable: checkpoint_faiss_seed_blocked")
        if _clean(checkpoint.get("collection_name")) and _clean(checkpoint.get("collection_name")) != self.config.collection_name:
            raise WeaviateUnavailableError(
                "weaviate_unavailable: checkpoint_collection_mismatch:"
                f"{checkpoint.get('collection_name')}!={self.config.collection_name}"
            )
        if _clean(checkpoint.get("namespace")) and _clean(checkpoint.get("namespace")) != self.config.namespace:
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: checkpoint_namespace_mismatch:{checkpoint.get('namespace')}!={self.config.namespace}"
            )
        if _clean(checkpoint.get("source_atom_schema_version")) and _clean(
            checkpoint.get("source_atom_schema_version")
        ) != self.config.schema_version:
            raise WeaviateUnavailableError(
                "weaviate_unavailable: checkpoint_source_atom_schema_version_mismatch:"
                f"{checkpoint.get('source_atom_schema_version')}!={self.config.schema_version}"
            )
        if _clean(checkpoint.get("embedding_model")) and _clean(checkpoint.get("embedding_model")) != "BAAI/bge-m3":
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: checkpoint_embedding_model_not_bge_m3:{checkpoint.get('embedding_model')}"
            )
        if checkpoint.get("completed_source_atom_ids") and not isinstance(checkpoint.get("source_atom_text_sha256"), Mapping):
            raise WeaviateUnavailableError("weaviate_unavailable: checkpoint_missing_source_atom_text_sha256")
        return dict(checkpoint)

    def _write_checkpoint(
        self,
        checkpoint_path: Path | None,
        *,
        completed_source_atom_ids: Sequence[str],
        upserted_count_this_run: int,
        skipped_count: int,
        embedding_dim: int,
        embedding_device: str,
        vectorized_object_count: int,
        metadata_only_object_count: int,
        source_atom_text_sha256: Mapping[str, str],
        source_atom_registry_path_hash: str,
        started_at: str,
    ) -> None:
        if checkpoint_path is None:
            return
        _write_json_atomic(
            checkpoint_path,
            {
                "schema_version": WEAVIATE_SOURCE_ATOM_INDEX_CHECKPOINT_VERSION,
                "vector_db_backend": "weaviate",
                "collection_name": self.config.collection_name,
                "namespace": self.config.namespace,
                "visibility": self.config.visibility,
                "source_atom_schema_version": self.config.schema_version,
                "embedding_model": self.config.embedding_model,
                "embedding_dim": int(embedding_dim),
                "embedding_device": _clean(embedding_device),
                "index_vector_source": WEAVIATE_STREAMING_BGE_M3_VECTOR_SOURCE,
                "completed_source_atom_ids": list(completed_source_atom_ids),
                "source_atom_text_sha256": dict(source_atom_text_sha256),
                "source_atom_registry_path_hash": source_atom_registry_path_hash,
                "completed_count": len(completed_source_atom_ids),
                "vectorized_object_count": int(vectorized_object_count),
                "metadata_only_object_count": int(metadata_only_object_count),
                "upserted_count_this_run": int(upserted_count_this_run),
                "skipped_count_this_run": int(skipped_count),
                "started_at": started_at,
                "updated_at": _utc_now_iso(),
                "production_namespace": self.config.production_namespace,
                "diagnostic_hash_vector_used": False,
                "faiss_used_for_index_seed": False,
                "faiss_used_for_active_retrieval": False,
            },
        )

    def index_records_streaming(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        checkpoint_path: Path | str | None = None,
        source_atom_registry_path: Path | str | None = None,
        total_count: int | None = None,
        recreate_collection: bool = False,
    ) -> dict[str, Any]:
        self.config.validate_for_nonprod()
        started_at = _utc_now_iso()
        started = time.perf_counter()
        checkpoint = self._load_checkpoint(Path(checkpoint_path) if checkpoint_path is not None else None)
        completed_ids: list[str] = [
            _clean(value)
            for value in checkpoint.get("completed_source_atom_ids", [])
            if _clean(value)
        ]
        completed_set = set(completed_ids)
        completed_text_sha_by_id: dict[str, str] = {
            _clean(key): _clean(value)
            for key, value in dict(checkpoint.get("source_atom_text_sha256") or {}).items()
            if _clean(key) and _clean(value)
        }
        checkpoint_resumed = bool(completed_set)
        schema = build_weaviate_source_atom_schema(self.config)
        self.client.ping()
        collection_recreated_this_run = False
        if recreate_collection:
            self.client.recreate_collection(schema)
            collection_recreated_this_run = True
        else:
            self.client.ensure_collection(schema)

        pending: list[dict[str, Any]] = []
        text_hashes: list[str] = []
        vectorized_by_granularity: dict[str, int] = {}
        vectorized_by_source_family: dict[str, int] = {}
        metadata_only_by_granularity: dict[str, int] = {}
        metadata_only_by_source_family: dict[str, int] = {}
        vectorized_object_count = 0
        metadata_only_object_count = 0
        encountered_count = 0
        skipped_count = 0
        upserted_count = 0
        embedding_count = 0
        embedding_latency_ms = 0.0
        embedding_dim = 0
        embedding_device = self.config.embedding_device
        embedding_model = self.config.embedding_model
        source_path = Path(source_atom_registry_path) if source_atom_registry_path is not None else None
        source_path_hash = f"sha256:{_sha256_text(source_path.as_posix())}" if source_path else ""
        if checkpoint_resumed and _clean(checkpoint.get("source_atom_registry_path_hash")) != source_path_hash:
            raise WeaviateUnavailableError(
                "weaviate_unavailable: checkpoint_source_atom_registry_path_hash_mismatch:"
                f"{checkpoint.get('source_atom_registry_path_hash')}!={source_path_hash}"
            )
        checkpoint_file = Path(checkpoint_path) if checkpoint_path is not None else None

        def flush_pending() -> None:
            nonlocal upserted_count, embedding_count, embedding_latency_ms, embedding_dim, embedding_device, embedding_model
            if not pending:
                return
            batch = list(pending)
            pending.clear()
            vectorized_batch, metadata_only_batch = _split_records_by_vectorization(batch, self.config)
            indexed_in_batch = 0
            if vectorized_batch:
                texts = [_clean(row.get("text")) for row in vectorized_batch]
                vectors = self.embedding_builder.embed_passages(texts)
                if len(vectors) != len(vectorized_batch):
                    raise WeaviateUnavailableError(
                        f"weaviate_unavailable: embedding_record_count_mismatch:{len(vectors)}!={len(vectorized_batch)}"
                    )
                indexed_vectorized = self.client.upsert_many(vectorized_batch, vectors)
                if int(indexed_vectorized) != len(vectorized_batch):
                    raise WeaviateUnavailableError(
                        "weaviate_unavailable: partial_weaviate_vector_upsert_count:"
                        f"{indexed_vectorized}!={len(vectorized_batch)}"
                    )
                indexed_in_batch += int(indexed_vectorized)
                embedding_count += int(self.embedding_builder.last_report.get("embedding_count") or len(vectors))
                embedding_latency_ms += float(self.embedding_builder.last_report.get("embedding_latency_ms") or 0.0)
                embedding_dim = embedding_dim or int(
                    self.embedding_builder.last_report.get("embedding_dim") or (len(vectors[0]) if vectors else 0)
                )
                embedding_device = _clean(self.embedding_builder.last_report.get("embedding_device") or embedding_device)
                embedding_model = _clean(self.embedding_builder.last_report.get("embedding_model") or embedding_model)
            if metadata_only_batch:
                indexed_metadata_only = self.client.upsert_many_metadata_only(metadata_only_batch)
                if int(indexed_metadata_only) != len(metadata_only_batch):
                    raise WeaviateUnavailableError(
                        "weaviate_unavailable: partial_weaviate_metadata_only_upsert_count:"
                        f"{indexed_metadata_only}!={len(metadata_only_batch)}"
                    )
                indexed_in_batch += int(indexed_metadata_only)
            if int(indexed_in_batch) != len(batch):
                raise WeaviateUnavailableError(
                    f"weaviate_unavailable: partial_weaviate_upsert_count:{indexed_in_batch}!={len(batch)}"
                )
            upserted_count += int(indexed_in_batch)
            for row in batch:
                source_atom_id = _clean(row.get("source_atom_id"))
                if source_atom_id not in completed_set:
                    completed_set.add(source_atom_id)
                    completed_ids.append(source_atom_id)
                completed_text_sha_by_id[source_atom_id] = _clean(row.get("text_sha256"))
            self._write_checkpoint(
                checkpoint_file,
                completed_source_atom_ids=completed_ids,
                upserted_count_this_run=upserted_count,
                skipped_count=skipped_count,
                embedding_dim=embedding_dim,
                embedding_device=embedding_device,
                vectorized_object_count=vectorized_object_count,
                metadata_only_object_count=metadata_only_object_count,
                source_atom_text_sha256=completed_text_sha_by_id,
                source_atom_registry_path_hash=source_path_hash,
                started_at=started_at,
            )
            if self.progress_callback is not None:
                self.progress_callback(
                    {
                        "batch": max(1, (upserted_count + skipped_count) // max(1, self.embedding_builder.batch_size)),
                        "completed_count": len(completed_ids),
                        "indexed_count": len(completed_ids),
                        "skipped_count": skipped_count,
                        "upserted_count_this_run": upserted_count,
                        "total_count": total_count,
                        "embedding_latency_ms": self.embedding_builder.last_report.get("embedding_latency_ms"),
                        "checkpoint_path": checkpoint_file.as_posix() if checkpoint_file else "",
                    }
                )

        for row in records:
            normalized = source_atom_record_from_mapping(row, self.config)
            encountered_count += 1
            if _record_should_be_vectorized(normalized, self.config):
                vectorized_object_count += 1
                _increment_count(vectorized_by_granularity, normalized.get("granularity"), default="unknown")
                _increment_count(vectorized_by_source_family, normalized.get("source_family"), default="UNKNOWN")
            else:
                metadata_only_object_count += 1
                _increment_count(metadata_only_by_granularity, normalized.get("granularity"), default="unknown")
                _increment_count(metadata_only_by_source_family, normalized.get("source_family"), default="UNKNOWN")
            text_hashes.append(normalized["text_sha256"])
            source_atom_id = _clean(normalized.get("source_atom_id"))
            if source_atom_id in completed_set:
                checkpoint_text_sha = completed_text_sha_by_id.get(source_atom_id)
                if checkpoint_text_sha == _clean(normalized.get("text_sha256")):
                    skipped_count += 1
                    continue
            pending.append(normalized)
            if len(pending) >= max(1, self.embedding_builder.batch_size):
                flush_pending()
        flush_pending()

        if encountered_count <= 0 and not completed_ids:
            raise WeaviateUnavailableError("weaviate_unavailable: refusing_to_index_zero_source_atom_records")
        if len(completed_ids) <= 0:
            raise WeaviateUnavailableError("weaviate_unavailable: refusing_to_accept_zero_indexed_source_atom_records")
        if not text_hashes:
            text_hashes = [_sha256_text(value) for value in completed_ids]
        embedding_dim = embedding_dim or int(checkpoint.get("embedding_dim") or 0)
        if embedding_count <= 0 and _clean(checkpoint.get("embedding_device")):
            embedding_device = _clean(checkpoint.get("embedding_device"))
        else:
            embedding_device = _clean(embedding_device or self.config.embedding_device)
        finished_at = _utc_now_iso()
        manifest = {
            "schema_version": "weaviate_source_atom_index_manifest_v1",
            "vector_db_backend": "weaviate",
            "weaviate_url_hash": self.config.url_hash,
            "collection_name": self.config.collection_name,
            "schema_version_source_atom": self.config.schema_version,
            "embedding_model": embedding_model,
            "embedding_dim": embedding_dim,
            "embedding_device": embedding_device,
            "embedding_batch_size": self.embedding_builder.batch_size,
            "embedding_count": len(completed_ids)
            if not _schema_v2_metadata_only_supported(self.config)
            else vectorized_object_count,
            "embedding_count_this_run": embedding_count,
            "embedding_latency_ms": round(embedding_latency_ms, 6),
            "embedding_latency_ms_this_run": round(embedding_latency_ms, 6),
            "embedding_cache_path_hash": _clean(self.embedding_builder.last_report.get("embedding_cache_path_hash")),
            "embedding_source": "sentence_transformers_bge_m3_streaming",
            "index_vector_source": WEAVIATE_STREAMING_BGE_M3_VECTOR_SOURCE,
            "indexed_count": len(completed_ids),
            "upserted_count_this_run": upserted_count,
            "skipped_count": skipped_count,
            "failed_count": 0,
            "encountered_count": encountered_count,
            "total_count": total_count,
            "checkpoint_resumed": checkpoint_resumed,
            "checkpoint_path": checkpoint_file.as_posix() if checkpoint_file else "",
            "checkpoint_completed_count": len(completed_ids),
            "collection_recreate_requested": bool(recreate_collection),
            "collection_recreated_this_run": collection_recreated_this_run,
            "corpus_fingerprint": f"sha256:{_sha256_text(json.dumps(sorted(text_hashes), sort_keys=True))}",
            "source_atom_registry_path_hash": f"sha256:{_sha256_text(source_path.as_posix())}" if source_path else "",
            "started_at": started_at,
            "finished_at": finished_at,
            "latency_ms": round((time.perf_counter() - started) * 1000, 6),
            "production_namespace": self.config.production_namespace,
            "diagnostic_hash_vector_used": False,
            "faiss_used_for_index_seed": False,
            "faiss_used_for_active_retrieval": False,
            "python_local_corpus_scan_used_for_candidate_generation": False,
            "source_native_layered_retrieval_used_for_candidate_generation": False,
            "searchunit_searchview_used_as_candidate_surface": False,
        }
        manifest.update(
            _vectorization_policy_report_from_counts(
                index_object_count=len(completed_ids),
                vectorized_object_count=len(completed_ids)
                if not _schema_v2_metadata_only_supported(self.config)
                else vectorized_object_count,
                vectorized_by_granularity=vectorized_by_granularity,
                vectorized_by_source_family=vectorized_by_source_family,
                metadata_only_object_count=0
                if not _schema_v2_metadata_only_supported(self.config)
                else metadata_only_object_count,
                metadata_only_by_granularity=metadata_only_by_granularity,
                metadata_only_by_source_family=metadata_only_by_source_family,
                current_index_vectorizes_all_source_atoms=not _schema_v2_metadata_only_supported(self.config),
            )
        )
        return manifest

    def index_records(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        source_atom_registry_path: Path | str | None = None,
    ) -> dict[str, Any]:
        self.config.validate_for_nonprod()
        started_at = _utc_now_iso()
        started = time.perf_counter()
        normalized = [source_atom_record_from_mapping(row, self.config) for row in records]
        if not normalized:
            raise WeaviateUnavailableError("weaviate_unavailable: refusing_to_index_zero_source_atom_records")
        schema = build_weaviate_source_atom_schema(self.config)
        self.client.ping()
        self.client.ensure_collection(schema)
        indexed_count = 0
        vectorized_indexed_count = 0
        metadata_only_indexed_count = 0
        embedding_count = 0
        embedding_latency_ms = 0.0
        embedding_dim = 0
        embedding_device = self.config.embedding_device
        embedding_model = self.config.embedding_model
        for batch_number, batch in enumerate(_batched(normalized, self.embedding_builder.batch_size), start=1):
            vectorized_batch, metadata_only_batch = _split_records_by_vectorization(batch, self.config)
            indexed_in_batch = 0
            if vectorized_batch:
                texts = [_clean(row.get("text")) for row in vectorized_batch]
                vectors = self.embedding_builder.embed_passages(texts)
                indexed_vectorized = self.client.upsert_many(vectorized_batch, vectors)
                if int(indexed_vectorized) != len(vectorized_batch):
                    raise WeaviateUnavailableError(
                        "weaviate_unavailable: partial_weaviate_vector_upsert_count:"
                        f"{indexed_vectorized}!={len(vectorized_batch)}"
                    )
                indexed_in_batch += int(indexed_vectorized)
                vectorized_indexed_count += int(indexed_vectorized)
                embedding_count += int(self.embedding_builder.last_report.get("embedding_count") or len(vectors))
                embedding_latency_ms += float(self.embedding_builder.last_report.get("embedding_latency_ms") or 0.0)
                embedding_dim = embedding_dim or int(
                    self.embedding_builder.last_report.get("embedding_dim") or (len(vectors[0]) if vectors else 0)
                )
                embedding_device = _clean(self.embedding_builder.last_report.get("embedding_device") or embedding_device)
                embedding_model = _clean(self.embedding_builder.last_report.get("embedding_model") or embedding_model)
            if metadata_only_batch:
                indexed_metadata_only = self.client.upsert_many_metadata_only(metadata_only_batch)
                if int(indexed_metadata_only) != len(metadata_only_batch):
                    raise WeaviateUnavailableError(
                        "weaviate_unavailable: partial_weaviate_metadata_only_upsert_count:"
                        f"{indexed_metadata_only}!={len(metadata_only_batch)}"
                    )
                indexed_in_batch += int(indexed_metadata_only)
                metadata_only_indexed_count += int(indexed_metadata_only)
            if int(indexed_in_batch) != len(batch):
                raise WeaviateUnavailableError(
                    f"weaviate_unavailable: partial_weaviate_upsert_count:{indexed_in_batch}!={len(batch)}"
                )
            indexed_count += int(indexed_in_batch)
            if self.progress_callback is not None:
                self.progress_callback(
                    {
                        "batch": batch_number,
                        "indexed_count": indexed_count,
                        "total_count": len(normalized),
                        "embedding_latency_ms": self.embedding_builder.last_report.get("embedding_latency_ms"),
                    }
                )
        finished_at = _utc_now_iso()
        text_hashes = [row["text_sha256"] for row in normalized]
        source_path = Path(source_atom_registry_path) if source_atom_registry_path is not None else None
        manifest = {
            "schema_version": "weaviate_source_atom_index_manifest_v1",
            "vector_db_backend": "weaviate",
            "weaviate_url_hash": self.config.url_hash,
            "collection_name": self.config.collection_name,
            "schema_version_source_atom": self.config.schema_version,
            "embedding_model": embedding_model,
            "embedding_dim": embedding_dim,
            "embedding_device": embedding_device,
            "embedding_batch_size": self.embedding_builder.batch_size,
            "embedding_count": embedding_count,
            "embedding_latency_ms": round(embedding_latency_ms, 6),
            "embedding_cache_path_hash": _clean(self.embedding_builder.last_report.get("embedding_cache_path_hash")),
            "indexed_count": int(indexed_count),
            "skipped_count": 0,
            "failed_count": max(len(normalized) - int(indexed_count), 0),
            "corpus_fingerprint": f"sha256:{_sha256_text(json.dumps(sorted(text_hashes), sort_keys=True))}",
            "source_atom_registry_path_hash": f"sha256:{_sha256_text(source_path.as_posix())}" if source_path else "",
            "started_at": started_at,
            "finished_at": finished_at,
            "latency_ms": round((time.perf_counter() - started) * 1000, 6),
            "production_namespace": self.config.production_namespace,
            "diagnostic_hash_vector_used": False,
            "faiss_used_for_index_seed": False,
            "faiss_used_for_active_retrieval": False,
            "python_local_corpus_scan_used_for_candidate_generation": False,
            "source_native_layered_retrieval_used_for_candidate_generation": False,
            "searchunit_searchview_used_as_candidate_surface": False,
        }
        vectorized_records, metadata_only_records = _split_records_by_vectorization(normalized, self.config)
        vectorized_counts = _count_records_by_route_fields(vectorized_records)
        metadata_only_counts = _count_records_by_route_fields(metadata_only_records)
        manifest.update(
            _vectorization_policy_report_from_counts(
                index_object_count=int(indexed_count),
                vectorized_object_count=vectorized_indexed_count,
                vectorized_by_granularity=vectorized_counts["granularity"],
                vectorized_by_source_family=vectorized_counts["source_family"],
                metadata_only_object_count=metadata_only_indexed_count,
                metadata_only_by_granularity=metadata_only_counts["granularity"],
                metadata_only_by_source_family=metadata_only_counts["source_family"],
                current_index_vectorizes_all_source_atoms=not _schema_v2_metadata_only_supported(self.config),
            )
        )
        if manifest["indexed_count"] <= 0:
            raise WeaviateUnavailableError("weaviate_unavailable: refusing_to_accept_zero_indexed_source_atom_records")
        return manifest

    def index_records_with_vectors(
        self,
        records: Sequence[Mapping[str, Any]],
        vectors: Sequence[Sequence[float]],
        *,
        embedding_report: Mapping[str, Any],
        source_atom_registry_path: Path | str | None = None,
        vector_source: str = "provided_bge_m3_vectors",
    ) -> dict[str, Any]:
        # Legacy diagnostic/offline transfer helper only. The active non-production
        # Weaviate indexing CLI uses index_records_streaming() and never calls this
        # FAISS/provided-vector path.
        self.config.validate_for_nonprod()
        started_at = _utc_now_iso()
        started = time.perf_counter()
        normalized = [source_atom_record_from_mapping(row, self.config) for row in records]
        if not normalized:
            raise WeaviateUnavailableError("weaviate_unavailable: refusing_to_index_zero_source_atom_records")
        vectorized_records, metadata_only_records = _split_records_by_vectorization(normalized, self.config)
        if _schema_v2_metadata_only_supported(self.config) and len(vectors) == len(normalized):
            vector_lookup = {
                _clean(record.get("source_atom_id")): vector
                for record, vector in zip(normalized, vectors, strict=True)
                if _record_should_be_vectorized(record, self.config)
            }
            vectorized_vectors = [vector_lookup[_clean(record.get("source_atom_id"))] for record in vectorized_records]
        else:
            vectorized_vectors = list(vectors)
        expected_vector_count = len(vectorized_records) if _schema_v2_metadata_only_supported(self.config) else len(normalized)
        if len(vectorized_vectors) != expected_vector_count:
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: vector_record_count_mismatch:{len(vectorized_vectors)}!={expected_vector_count}"
            )
        schema = build_weaviate_source_atom_schema(self.config)
        self.client.ping()
        self.client.ensure_collection(schema)
        indexed_count = 0
        vectorized_indexed_count = 0
        metadata_only_indexed_count = 0
        for start in range(0, len(vectorized_records), self.embedding_builder.batch_size):
            batch = vectorized_records[start : start + self.embedding_builder.batch_size]
            vector_batch = vectorized_vectors[start : start + self.embedding_builder.batch_size]
            indexed_vectorized = self.client.upsert_many(batch, vector_batch)
            if int(indexed_vectorized) != len(batch):
                raise WeaviateUnavailableError(
                    "weaviate_unavailable: partial_weaviate_vector_upsert_count:"
                    f"{indexed_vectorized}!={len(batch)}"
                )
            indexed_count += int(indexed_vectorized)
            vectorized_indexed_count += int(indexed_vectorized)
            if self.progress_callback is not None:
                self.progress_callback(
                    {
                        "batch": (start // self.embedding_builder.batch_size) + 1,
                        "indexed_count": indexed_count,
                        "total_count": len(normalized),
                        "embedding_source": vector_source,
                    }
                )
        for metadata_batch in _batched(metadata_only_records, self.embedding_builder.batch_size):
            indexed_metadata_only = self.client.upsert_many_metadata_only(metadata_batch)
            if int(indexed_metadata_only) != len(metadata_batch):
                raise WeaviateUnavailableError(
                    "weaviate_unavailable: partial_weaviate_metadata_only_upsert_count:"
                    f"{indexed_metadata_only}!={len(metadata_batch)}"
                )
            indexed_count += int(indexed_metadata_only)
            metadata_only_indexed_count += int(indexed_metadata_only)
        finished_at = _utc_now_iso()
        text_hashes = [row["text_sha256"] for row in normalized]
        source_path = Path(source_atom_registry_path) if source_atom_registry_path is not None else None
        dim = int(embedding_report.get("dimension") or embedding_report.get("embedding_dim") or 0)
        if not dim and len(vectors):
            dim = len(vectors[0])
        manifest = {
            "schema_version": "weaviate_source_atom_index_manifest_v1",
            "vector_db_backend": "weaviate",
            "weaviate_url_hash": self.config.url_hash,
            "collection_name": self.config.collection_name,
            "schema_version_source_atom": self.config.schema_version,
            "embedding_model": _clean(embedding_report.get("embedding_model") or self.config.embedding_model),
            "embedding_dim": dim,
            "embedding_device": _clean(embedding_report.get("embedding_device") or self.config.embedding_device),
            "embedding_batch_size": self.embedding_builder.batch_size,
            "embedding_count": len(vectorized_vectors),
            "embedding_latency_ms": float(embedding_report.get("embedding_build_latency_ms") or 0.0),
            "embedding_cache_path_hash": _clean(embedding_report.get("embedding_cache_path_hash")),
            "embedding_source": vector_source,
            "indexed_count": int(indexed_count),
            "skipped_count": 0,
            "failed_count": max(len(normalized) - int(indexed_count), 0),
            "corpus_fingerprint": f"sha256:{_sha256_text(json.dumps(sorted(text_hashes), sort_keys=True))}",
            "source_atom_registry_path_hash": f"sha256:{_sha256_text(source_path.as_posix())}" if source_path else "",
            "started_at": started_at,
            "finished_at": finished_at,
            "latency_ms": round((time.perf_counter() - started) * 1000, 6),
            "production_namespace": self.config.production_namespace,
            "diagnostic_hash_vector_used": False,
            "faiss_used_for_index_seed": "faiss" in _clean(vector_source).casefold(),
            "faiss_used_for_active_retrieval": False,
            "python_local_corpus_scan_used_for_candidate_generation": False,
            "source_native_layered_retrieval_used_for_candidate_generation": False,
            "searchunit_searchview_used_as_candidate_surface": False,
        }
        vectorized_counts = _count_records_by_route_fields(vectorized_records)
        metadata_only_counts = _count_records_by_route_fields(metadata_only_records)
        manifest.update(
            _vectorization_policy_report_from_counts(
                index_object_count=int(indexed_count),
                vectorized_object_count=vectorized_indexed_count,
                vectorized_by_granularity=vectorized_counts["granularity"],
                vectorized_by_source_family=vectorized_counts["source_family"],
                metadata_only_object_count=metadata_only_indexed_count,
                metadata_only_by_granularity=metadata_only_counts["granularity"],
                metadata_only_by_source_family=metadata_only_counts["source_family"],
                current_index_vectorizes_all_source_atoms=not _schema_v2_metadata_only_supported(self.config),
            )
        )
        if manifest["embedding_model"] != "BAAI/bge-m3":
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: embedding_model_must_be_BAAI_bge_m3:{manifest['embedding_model']}"
            )
        if manifest["indexed_count"] <= 0:
            raise WeaviateUnavailableError("weaviate_unavailable: refusing_to_accept_zero_indexed_source_atom_records")
        return manifest


class WeaviateSourceAtomAdapter:
    def __init__(
        self,
        *,
        config: WeaviateSourceAtomConfig,
        client: WeaviateSourceAtomClientProtocol | None = None,
        embedding_provider: Any | None = None,
        requested_backend: str = "weaviate-hybrid",
        retrieval_route_mode: str = "full_index",
        route_filter_fields_available: Mapping[str, bool] | None = None,
        default_config_report: Mapping[str, Any] | None = None,
    ) -> None:
        normalized = WEAVIATE_BACKEND_ALIASES.get(_clean(requested_backend).casefold())
        if normalized is None:
            raise WeaviateUnavailableError(f"weaviate_unavailable: unsupported_weaviate_backend:{requested_backend}")
        normalized_route_mode = _clean(retrieval_route_mode).replace("-", "_").casefold() or "full_index"
        if normalized_route_mode not in WEAVIATE_RETRIEVAL_ROUTE_MODES:
            raise WeaviateUnavailableError(f"weaviate_unavailable: unsupported_route_mode:{retrieval_route_mode}")
        self.config_obj = config
        self.client = client or WeaviateSourceAtomClient(config)
        self.embedding_builder = BgeM3EmbeddingBuilder(
            embedding_provider=embedding_provider,
            model_name=config.embedding_model,
            device=config.embedding_device,
        )
        self.requested_backend = _clean(requested_backend)
        self.selected_backend = normalized
        self.retrieval_route_mode = normalized_route_mode
        self.default_config_report = (
            dict(default_config_report)
            if isinstance(default_config_report, Mapping)
            else _implicit_weaviate_config_report(config, normalized_route_mode)
        )
        self._route_filter_fields_available_override = dict(route_filter_fields_available or {})
        self.generator = ExtractiveGenerator()
        self._reachable = False
        self._validated = False
        self._query_count = 0
        self._weaviate_query_call_count = 0
        self._last_filter_policy: dict[str, Any] = {}
        self._post_filter_removed_count = 0
        self._duplicate_collapse_removed_count = 0
        self._neighbor_expansion_added_count = 0
        self._neighbor_expansion_query_count = 0
        self._neighbor_expansion_latency_ms: list[float] = []
        self._same_doc_residual_query_count = 0
        self._same_doc_residual_added_count = 0
        self._same_doc_residual_expanded_item_count = 0
        self._same_doc_residual_latency_ms: list[float] = []
        self._xlsx_scoped_expansion_query_count = 0
        self._xlsx_scoped_expansion_added_count = 0
        self._xlsx_scoped_expansion_expanded_item_count = 0
        self._xlsx_scoped_expansion_latency_ms: list[float] = []
        self._xlsx_scoped_expansion_scope_counts: dict[str, int] = {}
        self._pdf_scoped_expansion_query_count = 0
        self._pdf_scoped_expansion_added_count = 0
        self._pdf_scoped_expansion_expanded_item_count = 0
        self._pdf_scoped_expansion_latency_ms: list[float] = []
        self._pdf_scoped_expansion_scope_counts: dict[str, int] = {}
        self._candidate_counts: dict[str, list[int]] = {"bm25": [], "vector": [], "hybrid": []}
        self._latencies: dict[str, list[float]] = {"bm25": [], "vector": [], "hybrid": []}
        self._query_variant_counts: list[int] = []
        self._query_variant_expanded_item_count = 0
        self._last_query_variant_plan: dict[str, Any] = {}
        self._vector_dim = 0
        self._index_manifest: dict[str, Any] | None = None

    def _load_index_manifest(self) -> dict[str, Any]:
        if self._index_manifest is not None:
            return self._index_manifest
        manifest_path = self.config_obj.index_manifest_path
        if not manifest_path:
            self._index_manifest = {}
            return self._index_manifest
        try:
            data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            data = {}
        except json.JSONDecodeError:
            data = {"valid": False, "fallback_reason": "weaviate_index_manifest_invalid_json"}
        self._index_manifest = data if isinstance(data, dict) else {}
        return self._index_manifest

    def _candidate_surface_manifest_checkpoint_blocked_reason(
        self,
        manifest: Mapping[str, Any],
    ) -> str:
        checkpoint_path_text = _clean(manifest.get("checkpoint_path"))
        manifest_path_text = _clean(self.config_obj.index_manifest_path)
        if not checkpoint_path_text or not manifest_path_text:
            return ""
        checkpoint_path = _resolve_repo_path(checkpoint_path_text)
        manifest_path = _resolve_repo_path(manifest_path_text)
        if not checkpoint_path.exists() or not manifest_path.exists():
            return ""
        try:
            checkpoint_mtime_ns = checkpoint_path.stat().st_mtime_ns
            manifest_mtime_ns = manifest_path.stat().st_mtime_ns
        except OSError:
            return "candidate_surface_complete_manifest_checkpoint_stat_unavailable"
        if checkpoint_mtime_ns > manifest_mtime_ns:
            return "candidate_surface_complete_manifest_checkpoint_newer_than_manifest"
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "candidate_surface_complete_manifest_checkpoint_invalid"
        if not isinstance(checkpoint, Mapping):
            return "candidate_surface_complete_manifest_checkpoint_invalid"
        if _clean(checkpoint.get("collection_name")) != self.config_obj.collection_name:
            return "candidate_surface_complete_manifest_checkpoint_collection_mismatch"

        def int_or_none(value: Any) -> int | None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        manifest_checkpoint_completed = int_or_none(manifest.get("checkpoint_completed_count"))
        checkpoint_completed = int_or_none(checkpoint.get("completed_count"))
        if (
            manifest_checkpoint_completed is not None
            and checkpoint_completed is not None
            and manifest_checkpoint_completed != checkpoint_completed
        ):
            return "candidate_surface_complete_manifest_checkpoint_count_mismatch"
        checkpoint_upserted = int_or_none(checkpoint.get("upserted_count_this_run"))
        manifest_upserted = int_or_none(manifest.get("upserted_count_this_run"))
        if (
            checkpoint_upserted is not None
            and manifest_upserted is not None
            and checkpoint_upserted != manifest_upserted
        ):
            return "candidate_surface_complete_manifest_checkpoint_count_mismatch"
        return ""

    def _candidate_surface_metric_gate_report(self) -> dict[str, Any]:
        candidate_surface = self.default_config_report.get("candidate_surface_rebuild")
        manifest = self._load_index_manifest()
        manifest_claims_complete = manifest.get("candidate_surface_complete_manifest") is True
        collection_requires_gate = "CandidateSurface" in self.config_obj.collection_name
        if not isinstance(candidate_surface, Mapping):
            if not collection_requires_gate and not manifest_claims_complete:
                return {}
            candidate_surface = {}
        status = _clean(candidate_surface.get("surface_status")).casefold()
        metric_blocked = candidate_surface.get("metric_blocked_until_complete_manifest") is True
        complete_required = (
            candidate_surface.get("complete_manifest_required") is True
            or collection_requires_gate
            or manifest_claims_complete
        )
        report: dict[str, Any] = {
            "surface_status": status or "ready",
            "metric_blocked_until_complete_manifest": metric_blocked,
            "complete_manifest_required": complete_required,
            "complete_manifest_verified": False,
            "complete_manifest_schema_version_required": WEAVIATE_CANDIDATE_SURFACE_COMPLETE_MANIFEST_SCHEMA_VERSION,
        }
        if status in WEAVIATE_CANDIDATE_SURFACE_DIRTY_STATUSES:
            report["blocked_reason"] = "candidate_surface_dirty_partial_metrics_blocked"
            return report
        if not metric_blocked and not complete_required:
            report["complete_manifest_verified"] = True
            return report

        report["manifest_present"] = bool(manifest)
        report["manifest_valid"] = manifest.get("valid") is True
        report["manifest_collection"] = _clean(manifest.get("collection_name"))
        if not manifest:
            report["blocked_reason"] = "candidate_surface_complete_manifest_missing"
            return report
        if manifest.get("valid") is not True:
            report["blocked_reason"] = "candidate_surface_complete_manifest_invalid"
            return report
        if manifest.get("candidate_surface_complete_manifest") is not True:
            report["blocked_reason"] = "candidate_surface_complete_manifest_missing"
            return report
        if (
            _clean(manifest.get("candidate_surface_complete_manifest_schema_version"))
            != WEAVIATE_CANDIDATE_SURFACE_COMPLETE_MANIFEST_SCHEMA_VERSION
        ):
            report["blocked_reason"] = "candidate_surface_complete_manifest_schema_version_invalid"
            return report
        if _clean(manifest.get("collection_name")) != self.config_obj.collection_name:
            report["blocked_reason"] = "candidate_surface_complete_manifest_collection_mismatch"
            return report
        if self.config_obj.collection_name != WEAVIATE_ROUTE_SELECTED_CANDIDATE_SURFACE_V2_COLLECTION:
            report["blocked_reason"] = "candidate_surface_complete_manifest_collection_allowlist_blocked"
            return report
        manifest_schema_version_source_atom = _clean(manifest.get("schema_version_source_atom"))
        if (
            manifest_schema_version_source_atom != self.config_obj.schema_version
            or manifest_schema_version_source_atom != WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2
        ):
            report["blocked_reason"] = "candidate_surface_complete_manifest_schema_version_source_atom_mismatch"
            return report
        if manifest.get("candidate_surface_full_corpus_index") is not True:
            report["blocked_reason"] = "candidate_surface_complete_manifest_full_corpus_index_missing"
            return report
        for protected_flag in ("production_namespace", "source_registry_mutated", "latest_current_mutated"):
            if manifest.get(protected_flag) is not False:
                report["blocked_reason"] = f"candidate_surface_complete_manifest_{protected_flag}_blocked"
                return report
        count_fields = (
            "official_metric_input_rows",
            "indexed_count",
            "skipped_count",
            "failed_count",
            "upserted_count_this_run",
        )
        if any(field not in manifest or manifest.get(field) is None for field in count_fields):
            report["blocked_reason"] = "candidate_surface_complete_manifest_count_invalid"
            return report
        try:
            official_metric_input_rows = int(manifest.get("official_metric_input_rows"))
            indexed_count = int(manifest.get("indexed_count"))
            skipped_count = int(manifest.get("skipped_count"))
            failed_count = int(manifest.get("failed_count"))
            upserted_count_this_run = int(manifest.get("upserted_count_this_run"))
        except (TypeError, ValueError):
            report["blocked_reason"] = "candidate_surface_complete_manifest_count_invalid"
            return report
        if official_metric_input_rows != 0:
            report["blocked_reason"] = "candidate_surface_complete_manifest_official_metric_input_rows_blocked"
            return report
        if indexed_count <= 0:
            report["blocked_reason"] = "candidate_surface_complete_manifest_indexed_count_invalid"
            return report
        if manifest.get("checkpoint_resumed") is not False:
            report["blocked_reason"] = "candidate_surface_complete_manifest_checkpoint_resumed_blocked"
            return report
        if manifest.get("collection_recreate_requested") is not True:
            report["blocked_reason"] = "candidate_surface_complete_manifest_collection_recreate_missing"
            return report
        if manifest.get("collection_recreated_this_run") is not True:
            report["blocked_reason"] = "candidate_surface_complete_manifest_collection_recreate_missing"
            return report
        checkpoint_blocked_reason = self._candidate_surface_manifest_checkpoint_blocked_reason(manifest)
        if checkpoint_blocked_reason:
            report["blocked_reason"] = checkpoint_blocked_reason
            return report
        if skipped_count != 0:
            report["blocked_reason"] = "candidate_surface_complete_manifest_skipped_count_blocked"
            return report
        if failed_count != 0:
            report["blocked_reason"] = "candidate_surface_complete_manifest_failed_count_blocked"
            return report
        if upserted_count_this_run != indexed_count:
            report["blocked_reason"] = "candidate_surface_complete_manifest_upserted_indexed_count_mismatch"
            return report
        report["surface_status"] = "ready"
        report["metric_blocked_until_complete_manifest"] = False
        report["complete_manifest_verified"] = True
        return report

    def _validate_candidate_surface_metric_gate(self) -> None:
        gate_report = self._candidate_surface_metric_gate_report()
        blocked_reason = _clean(gate_report.get("blocked_reason"))
        if blocked_reason:
            raise WeaviateUnavailableError(f"weaviate_unavailable: {blocked_reason}")

    def _reader_facing_default_config_report(
        self,
        *,
        candidate_surface_gate: Mapping[str, Any] | None = None,
        candidate_surface_report: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        default_config = dict(self.default_config_report)
        candidate_surface = default_config.get("candidate_surface_rebuild")
        if not isinstance(candidate_surface, Mapping):
            return default_config
        candidate_surface_snapshot = dict(candidate_surface)
        if isinstance(candidate_surface_report, Mapping):
            candidate_surface_snapshot.update(candidate_surface_report)
        gate_report = (
            candidate_surface_gate
            if isinstance(candidate_surface_gate, Mapping)
            else self._candidate_surface_metric_gate_report()
        )
        if gate_report.get("complete_manifest_verified") is True:
            candidate_surface_snapshot["surface_status"] = "ready"
            candidate_surface_snapshot["metric_blocked_until_complete_manifest"] = False
            candidate_surface_snapshot.pop("metrics_blocked_reason", None)
        default_config["candidate_surface_rebuild"] = candidate_surface_snapshot
        return default_config

    def _indexed_object_count(self) -> int:
        manifest = self._load_index_manifest()
        for key in ("index_object_count", "indexed_count", "weaviate_indexed_object_count"):
            value = manifest.get(key)
            if isinstance(value, int):
                return max(0, value)
        return 0

    def _route_filter_field_available(self, field: str) -> bool:
        if field in self._route_filter_fields_available_override:
            return bool(self._route_filter_fields_available_override[field])
        if field == "source_family":
            return True
        manifest = self._load_index_manifest()
        if bool(manifest.get("route_taxonomy_available")):
            fields = manifest.get("route_taxonomy_filterable_fields")
            if isinstance(fields, Sequence) and not isinstance(fields, (str, bytes, bytearray)):
                return field in {_clean(item) for item in fields}
        return bool(manifest.get(f"{field}_filterable"))

    def _base_filters(self) -> dict[str, Any]:
        return {
            "namespace": self.config_obj.namespace,
            "visibility": self.config_obj.visibility,
        }

    def _lane_filter_plan(self, query: str, *, source_family_hint: str = "") -> tuple[dict[str, Any], dict[str, Any]]:
        plan = (
            plan_weaviate_retrieval_route(query, source_family_hint=source_family_hint)
            if self.retrieval_route_mode == "route_selected"
            else _route_plan(
                selected_route=self.retrieval_route_mode,
                source_families=[],
                granularities=[],
                reasons=[f"explicit_{self.retrieval_route_mode}_lane"],
                confidence=1.0,
            )
        )
        filters = self._base_filters()
        source_family_filter: list[str] = []
        granularity_filter: list[str] = []
        retrieval_route_filter: list[str] = []
        if self.retrieval_route_mode == "text_only":
            source_family_filter = ["TEXT"]
            granularity_filter = ["paragraph", "heading_context_block", "caption"]
            retrieval_route_filter = ["text_general"]
        elif self.retrieval_route_mode == "mixed_pool":
            source_family_filter = ["TEXT", "PDF", "XLSX"]
        elif self.retrieval_route_mode == "route_selected":
            source_family_filter = list(plan.get("selected_source_family_filter") or [])
            granularity_filter = list(plan.get("selected_granularity_filter") or [])
            selected_route = _clean(plan.get("selected_route"))
            if selected_route and selected_route in WEAVIATE_RETRIEVAL_ROUTES and selected_route != "mixed_fallback":
                retrieval_route_filter = [selected_route]

        source_family_filter_sent = False
        granularity_filter_sent = False
        retrieval_route_filter_sent = False
        if source_family_filter and self._route_filter_field_available("source_family"):
            filters["source_family"] = source_family_filter[0] if len(source_family_filter) == 1 else source_family_filter
            source_family_filter_sent = True
        if granularity_filter and self._route_filter_field_available("granularity"):
            filters["granularity"] = granularity_filter[0] if len(granularity_filter) == 1 else granularity_filter
            granularity_filter_sent = True
        if retrieval_route_filter and self._route_filter_field_available("retrieval_route"):
            filters["retrieval_route"] = retrieval_route_filter[0] if len(retrieval_route_filter) == 1 else retrieval_route_filter
            retrieval_route_filter_sent = True

        route_filter_requested = bool(source_family_filter or granularity_filter or retrieval_route_filter)
        route_filter_sent = bool(source_family_filter_sent or granularity_filter_sent or retrieval_route_filter_sent)
        route_filter_missing = bool(
            (source_family_filter and not source_family_filter_sent)
            or (granularity_filter and not granularity_filter_sent)
            or (retrieval_route_filter and not retrieval_route_filter_sent)
        )

        policy = {
            "route_mode": self.retrieval_route_mode,
            "metadata_filters_sent_to_weaviate": True,
            "base_filter_sent": True,
            "route_filter_requested": route_filter_requested,
            "route_filter_sent": route_filter_sent,
            "weaviate_filter_sent": route_filter_sent,
            "source_family_filter_sent": source_family_filter_sent,
            "granularity_filter_sent": granularity_filter_sent,
            "retrieval_route_filter_sent": retrieval_route_filter_sent,
            "requested_source_family_filter": source_family_filter,
            "requested_granularity_filter": granularity_filter,
            "requested_retrieval_route_filter": retrieval_route_filter,
            "source_family_filterable_available": self._route_filter_field_available("source_family"),
            "granularity_filterable_available": self._route_filter_field_available("granularity"),
            "retrieval_route_filterable_available": self._route_filter_field_available("retrieval_route"),
            "python_post_filtering": "safety_validation_only",
            "filters": dict(filters),
            "schema_index_v2_rebuild_required": route_filter_missing,
        }
        return filters, {**plan, "weaviate_filter_policy": policy}

    @staticmethod
    def _query_evidence_source_family_hint_for_query(query: str, planner: Mapping[str, Any]) -> str:
        if not isinstance(planner, Mapping):
            return ""
        if _clean(planner.get("planner_status")) != "planned_validated":
            return ""
        clean_query = _clean(query)
        expected_query_sha256 = f"sha256:{_sha256_text(clean_query)}" if clean_query else ""
        if not expected_query_sha256 or _clean(planner.get("query_sha256")) != expected_query_sha256:
            return ""
        hint = _clean(planner.get("source_family_hint")).lower()
        return hint if hint in {"text", "pdf", "xlsx"} else ""

    def _context_matches_filter(self, context: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
        for key in ("source_family", "granularity", "retrieval_route"):
            if key not in filters:
                continue
            value = filters[key]
            actual = _clean(context.get(key))
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                if actual not in {_clean(item) for item in value if _clean(item)}:
                    return False
            elif actual != _clean(value):
                return False
        return True

    def _safety_filter_contexts(
        self,
        contexts: Sequence[Mapping[str, Any]],
        *,
        filters: Mapping[str, Any],
    ) -> tuple[list[dict[str, Any]], int]:
        if self.retrieval_route_mode == "full_index":
            return [dict(context) for context in contexts], 0
        kept = [dict(context) for context in contexts if self._context_matches_filter(context, filters)]
        return kept, max(len(contexts) - len(kept), 0)

    @property
    def config(self) -> dict[str, Any]:
        default_config = self._reader_facing_default_config_report()
        return {
            "adapter": "weaviate_source_atom_retrieval",
            "surface": "source_native",
            "requested_backend": self.requested_backend,
            "selected_backend": self.selected_backend,
            "retrieval_route_mode": self.retrieval_route_mode,
            "active_retrieval_service_boundary": "weaviate",
            "candidate_generation_input_policy": WEAVIATE_CANDIDATE_INPUT_POLICY,
            "python_local_corpus_scan_used_for_candidate_generation": False,
            "source_native_layered_retrieval_used_for_candidate_generation": False,
            "searchunit_searchview_role": "legacy_comparison_debug_only",
            "external_api_calls": True,
            "weaviate_collection_name": self.config_obj.collection_name,
            "weaviate_schema_version": self.config_obj.schema_version,
            "weaviate_default_config": default_config,
            "rollback_key": _clean(default_config.get("rollback_key")),
            "rollback_config": dict(default_config.get("rollback") or {}),
            "fallback_used": bool(default_config.get("fallback_used", False)),
            "fail_closed_on_unavailable": bool(default_config.get("fail_closed_on_unavailable", True)),
        }

    @property
    def active_path_report(self) -> dict[str, Any]:
        latency_hybrid = _latency_distribution_ms(self._latencies["hybrid"])
        indexed_object_count = self._indexed_object_count()
        manifest = self._load_index_manifest()
        base_default_config = dict(self.default_config_report)
        rollback_config = dict(base_default_config.get("rollback") or {})
        route_filters_sent = dict(self._last_filter_policy.get("filters") or self._base_filters())
        promotion_blockers: list[str] = []
        if self.retrieval_route_mode != "route_selected":
            promotion_blockers.append("route_selected_default_not_active")
        if self._query_count <= 0:
            promotion_blockers.append("weaviate_not_invoked")
        if self.retrieval_route_mode == "route_selected" and not self._last_filter_policy.get("route_filter_sent"):
            promotion_blockers.append("route_selected_weaviate_route_filters_not_sent")
        if self._post_filter_removed_count > 0:
            promotion_blockers.append("route_filter_safety_post_filter_removed_contexts")
        promotion_blockers.append("route_ab_comparative_gate_not_run_in_routine_single_mode")
        promotion_decision = "blocked_keep_full_index_rollback" if promotion_blockers else "promote_route_selected_nonprod_default"
        raw_vectorized_count = manifest.get("vectorized_object_count")
        vectorized_object_count = (
            max(0, int(raw_vectorized_count)) if isinstance(raw_vectorized_count, int) else indexed_object_count
        )
        raw_vectorized_ratio = manifest.get("vectorized_object_ratio")
        vectorized_object_ratio = (
            float(raw_vectorized_ratio)
            if isinstance(raw_vectorized_ratio, (int, float))
            else (round(float(vectorized_object_count) / float(indexed_object_count), 6) if indexed_object_count else 0.0)
        )
        vectorized_by_granularity = (
            dict(manifest.get("vectorized_by_granularity") or {})
            if isinstance(manifest.get("vectorized_by_granularity"), Mapping)
            else {}
        )
        if not vectorized_by_granularity and indexed_object_count:
            vectorized_by_granularity = {"unknown": indexed_object_count}
        metadata_only_object_count = (
            max(0, int(manifest.get("metadata_only_object_count")))
            if isinstance(manifest.get("metadata_only_object_count"), int)
            else 0
        )
        metadata_only_by_granularity = (
            dict(manifest.get("metadata_only_by_granularity") or {})
            if isinstance(manifest.get("metadata_only_by_granularity"), Mapping)
            else {}
        )
        metadata_only_by_source_family = (
            dict(manifest.get("metadata_only_by_source_family") or {})
            if isinstance(manifest.get("metadata_only_by_source_family"), Mapping)
            else {}
        )
        vectorization_policy = (
            dict(manifest.get("vectorization_policy") or {})
            if isinstance(manifest.get("vectorization_policy"), Mapping)
            else {}
        )
        current_index_vectorizes_all_source_atoms = bool(
            vectorization_policy.get("current_index_vectorizes_all_source_atoms", True)
        )
        index_time_metadata_only_supported = bool(
            vectorization_policy.get("index_time_metadata_only_supported")
            or (
                _clean(manifest.get("schema_version_source_atom")) == WEAVIATE_SOURCE_ATOM_SCHEMA_VERSION_V2
                and not current_index_vectorizes_all_source_atoms
            )
        )
        candidate_surface_rebuild = (
            dict(base_default_config.get("candidate_surface_rebuild") or {})
            if isinstance(base_default_config.get("candidate_surface_rebuild"), Mapping)
            else {}
        )
        candidate_surface_gate = self._candidate_surface_metric_gate_report()
        if candidate_surface_rebuild:
            if candidate_surface_gate.get("complete_manifest_verified") is True:
                candidate_surface_rebuild["surface_status"] = "ready"
                candidate_surface_rebuild["metric_blocked_until_complete_manifest"] = False
                candidate_surface_rebuild.pop("metrics_blocked_reason", None)
            manifest_path = Path(self.config_obj.index_manifest_path)
            manifest_fingerprint = (
                f"sha256:{_sha256_file_bytes(manifest_path)}"
                if manifest and manifest_path.exists()
                else ""
            )
            candidate_surface_rebuild.update(
                {
                    "candidate_collection": self.config_obj.collection_name,
                    "production_namespace": self.config_obj.production_namespace,
                    "index_manifest_path": self.config_obj.index_manifest_path,
                    "index_manifest_sha256": manifest_fingerprint,
                    "metric_gate": candidate_surface_gate,
                    "axis_materialization_summary": {
                        "vectorized_by_granularity": vectorized_by_granularity,
                        "metadata_only_by_granularity": metadata_only_by_granularity,
                        "metadata_only_by_source_family": metadata_only_by_source_family,
                    },
                    "vectorization_policy": {
                        "current_index_vectorizes_all_source_atoms": current_index_vectorizes_all_source_atoms,
                        "index_time_metadata_only_supported": index_time_metadata_only_supported,
                        "schema_index_v2_rebuild_required_for_metadata_only_policy": bool(
                            manifest.get("schema_index_v2_rebuild_required_for_metadata_only_policy")
                        ),
                    },
                }
            )
        default_config = self._reader_facing_default_config_report(
            candidate_surface_gate=candidate_surface_gate,
            candidate_surface_report=candidate_surface_rebuild,
        )
        return {
            "active_retrieval_backend": self.selected_backend,
            "active_retrieval_service_boundary": "weaviate",
            "collection": self.config_obj.collection_name,
            "python_local_corpus_scan_used_for_candidate_generation": False,
            "source_native_layered_retrieval_used_for_candidate_generation": False,
            "diagnostic_hash_vector_used": False,
            "faiss_used_for_active_retrieval": False,
            "searchunit_searchview_used_as_candidate_surface": False,
            "weaviate_collection_name": self.config_obj.collection_name,
            "weaviate_schema_version": self.config_obj.schema_version,
            "schema_version_source_atom": _clean(manifest.get("schema_version_source_atom")) or self.config_obj.schema_version,
            "weaviate_index_manifest_path": self.config_obj.index_manifest_path,
            "weaviate_indexed_object_count": indexed_object_count,
            "index_object_count": indexed_object_count,
            "route_planner_version": WEAVIATE_ROUTE_PLANNER_VERSION,
            "route_filters_sent_to_weaviate": route_filters_sent,
            "fallback_used": bool(default_config.get("fallback_used", False)),
            "fail_closed_on_unavailable": bool(default_config.get("fail_closed_on_unavailable", True)),
            "weaviate_default_config": default_config,
            "rollback_key": _clean(default_config.get("rollback_key")),
            "rollback_config": rollback_config,
            "promotion_decision": promotion_decision,
            "promotion_blockers": promotion_blockers,
            "weaviate_invoked": self._query_count > 0,
            "local_fallback_surfaces": False,
            "residual_risks": [
                "route-selected default remains non-production diagnostic until fresh text and mixed diagnostic runs are reviewed",
                "full-index Weaviate rollback must remain available through rollback_config",
                "answer composition and citation formatting remain diagnostic and must stay evidence-gated",
            ],
            "next_recommended_goal": "selected_evidence_answer_composer_citation_formatter_nonprod",
            "vectorized_object_count": vectorized_object_count,
            "metadata_only_object_count": metadata_only_object_count,
            "vectorized_object_ratio": round(vectorized_object_ratio, 6),
            "vectorized_by_granularity": vectorized_by_granularity,
            "metadata_only_by_granularity": metadata_only_by_granularity,
            "metadata_only_by_source_family": metadata_only_by_source_family,
            "current_index_vectorizes_all_source_atoms": current_index_vectorizes_all_source_atoms,
            "index_time_metadata_only_supported": index_time_metadata_only_supported,
            "candidate_surface_rebuild": candidate_surface_rebuild,
            "schema_index_v2_rebuild_required_for_metadata_only_policy": bool(
                manifest.get("schema_index_v2_rebuild_required_for_metadata_only_policy")
            ),
            "weaviate_query_latency_ms_p50": latency_hybrid["p50"],
            "weaviate_query_latency_ms_p95": latency_hybrid["p95"],
            "weaviate_query_count_per_item": round(
                float(self._weaviate_query_call_count) / float(self._query_count), 6
            )
            if self._query_count
            else 0.0,
            "weaviate_query_reformulation": {
                "version": WEAVIATE_QUERY_REFORMULATION_VERSION,
                "enabled": self._query_variant_expanded_item_count > 0,
                "expanded_item_count": self._query_variant_expanded_item_count,
                "item_count": self._query_count,
                "query_variant_count_avg": round(
                    sum(self._query_variant_counts) / float(len(self._query_variant_counts)), 6
                )
                if self._query_variant_counts
                else 0.0,
                "last_query_variant_count": int(self._last_query_variant_plan.get("query_variant_count") or 0),
                "max_query_variants": WEAVIATE_MAX_QUERY_VARIANTS,
                "query_variant_merge_policy": WEAVIATE_QUERY_VARIANT_MERGE_POLICY,
                "input_policy": WEAVIATE_QUERY_REFORMULATION_INPUT_POLICY,
                "candidate_generation_input_policy": WEAVIATE_CANDIDATE_INPUT_POLICY,
                "uses_gold_fields": False,
                "uses_expected_fields": False,
                "uses_qrels": False,
                "uses_labels": False,
                "uses_ids": False,
                "uses_baseline_topk": False,
                "uses_legacy_outputs": False,
            },
            "weaviate_hybrid_alpha": self.config_obj.hybrid_alpha if self.selected_backend == "weaviate_hybrid" else None,
            "weaviate_filter_sent": bool(self._last_filter_policy.get("weaviate_filter_sent", True)),
            "weaviate_filter_policy": dict(self._last_filter_policy)
            if self._last_filter_policy
            else {
                "route_mode": self.retrieval_route_mode,
                "metadata_filters_sent_to_weaviate": True,
                "base_filter_sent": True,
                "route_filter_requested": False,
                "route_filter_sent": False,
                "weaviate_filter_sent": False,
                "python_post_filtering": "safety_validation_only",
                "filters": self._base_filters(),
            },
            "python_post_filter_only_safety_validation": True,
            "post_filter_removed_count": self._post_filter_removed_count,
            "weaviate_post_processing": self.weaviate_post_processing_report,
            "candidate_generation_input_policy": WEAVIATE_CANDIDATE_INPUT_POLICY,
        }

    @property
    def weaviate_post_processing_report(self) -> dict[str, Any]:
        latency = _latency_distribution_ms(self._neighbor_expansion_latency_ms)
        same_doc_latency = _latency_distribution_ms(self._same_doc_residual_latency_ms)
        xlsx_scope_latency = _latency_distribution_ms(self._xlsx_scoped_expansion_latency_ms)
        pdf_scope_latency = _latency_distribution_ms(self._pdf_scoped_expansion_latency_ms)
        return {
            "duplicate_collapse_enabled": True,
            "duplicate_collapse_policy": "route_selected_structural_diversity_doc_cap_v2",
            "same_doc_duplicate_collapse_removed_count": self._duplicate_collapse_removed_count,
            "neighbor_expansion_enabled": True,
            "neighbor_expansion_policy": "bounded_weaviate_id_only_v1",
            "neighbor_expansion_query_count": self._neighbor_expansion_query_count,
            "neighbor_expansion_added_count": self._neighbor_expansion_added_count,
            "neighbor_expansion_latency_ms_p50": latency["p50"],
            "neighbor_expansion_latency_ms_p95": latency["p95"],
            "neighbor_expansion_candidate_generation": "weaviate_id_only_no_local_corpus_scan",
            "python_local_corpus_scan_used_for_neighbor_expansion": False,
            "faiss_used_for_neighbor_expansion": False,
            "searchunit_searchview_used_for_neighbor_expansion": False,
            "same_doc_residual_retrieval_enabled": self._same_doc_residual_query_count > 0,
            "same_doc_residual_expanded_item_count": self._same_doc_residual_expanded_item_count,
            "same_doc_residual_query_count": self._same_doc_residual_query_count,
            "same_doc_residual_added_count": self._same_doc_residual_added_count,
            "same_doc_residual_policy": WEAVIATE_SAME_DOC_RESIDUAL_RETRIEVAL_POLICY,
            "same_doc_residual_max_docs": WEAVIATE_SAME_DOC_RESIDUAL_MAX_DOCS,
            "same_doc_residual_top_k_per_doc": WEAVIATE_SAME_DOC_RESIDUAL_TOP_K_PER_DOC,
            "same_doc_residual_latency_ms_p50": same_doc_latency["p50"],
            "same_doc_residual_latency_ms_p95": same_doc_latency["p95"],
            "same_doc_residual_candidate_generation": (
                "weaviate_doc_id_filter_plus_query_variants_no_gold_qrels_labels_ids_or_baseline"
            ),
            "python_local_corpus_scan_used_for_same_doc_residual": False,
            "faiss_used_for_same_doc_residual": False,
            "searchunit_searchview_used_for_same_doc_residual": False,
            "xlsx_scoped_expansion_enabled": self._xlsx_scoped_expansion_query_count > 0,
            "xlsx_scoped_expansion_expanded_item_count": self._xlsx_scoped_expansion_expanded_item_count,
            "xlsx_scoped_expansion_query_count": self._xlsx_scoped_expansion_query_count,
            "xlsx_scoped_expansion_added_count": self._xlsx_scoped_expansion_added_count,
            "xlsx_scoped_expansion_policy": WEAVIATE_XLSX_SCOPED_EXPANSION_POLICY,
            "xlsx_scoped_expansion_max_scopes": WEAVIATE_XLSX_SCOPED_EXPANSION_MAX_SCOPES,
            "xlsx_scoped_expansion_top_k_per_scope": WEAVIATE_XLSX_SCOPED_EXPANSION_TOP_K_PER_SCOPE,
            "xlsx_scoped_expansion_scope_counts": dict(sorted(self._xlsx_scoped_expansion_scope_counts.items())),
            "xlsx_scoped_expansion_latency_ms_p50": xlsx_scope_latency["p50"],
            "xlsx_scoped_expansion_latency_ms_p95": xlsx_scope_latency["p95"],
            "xlsx_scoped_expansion_candidate_generation": (
                "weaviate_source_owned_scope_filter_plus_query_text_no_gold_qrels_labels_ids_or_baseline"
            ),
            "python_local_corpus_scan_used_for_xlsx_scoped_expansion": False,
            "faiss_used_for_xlsx_scoped_expansion": False,
            "searchunit_searchview_used_for_xlsx_scoped_expansion": False,
            "pdf_scoped_expansion_enabled": self._pdf_scoped_expansion_query_count > 0,
            "pdf_scoped_expansion_expanded_item_count": self._pdf_scoped_expansion_expanded_item_count,
            "pdf_scoped_expansion_query_count": self._pdf_scoped_expansion_query_count,
            "pdf_scoped_expansion_added_count": self._pdf_scoped_expansion_added_count,
            "pdf_scoped_expansion_policy": WEAVIATE_PDF_SCOPED_EXPANSION_POLICY,
            "pdf_scoped_expansion_max_scopes": WEAVIATE_PDF_SCOPED_EXPANSION_MAX_SCOPES,
            "pdf_scoped_expansion_top_k_per_scope": WEAVIATE_PDF_SCOPED_EXPANSION_TOP_K_PER_SCOPE,
            "pdf_scoped_expansion_scope_counts": dict(sorted(self._pdf_scoped_expansion_scope_counts.items())),
            "pdf_scoped_expansion_latency_ms_p50": pdf_scope_latency["p50"],
            "pdf_scoped_expansion_latency_ms_p95": pdf_scope_latency["p95"],
            "pdf_scoped_expansion_candidate_generation": (
                "weaviate_source_owned_pdf_scope_filter_plus_query_text_no_gold_qrels_labels_ids_or_baseline"
            ),
            "python_local_corpus_scan_used_for_pdf_scoped_expansion": False,
            "faiss_used_for_pdf_scoped_expansion": False,
            "searchunit_searchview_used_for_pdf_scoped_expansion": False,
        }

    @property
    def retrieval_backend_report(self) -> dict[str, Any]:
        selected_mode = WEAVIATE_QUERY_MODES[self.selected_backend]
        indexed_object_count = self._indexed_object_count()
        return {
            "requested": self.requested_backend,
            "selected": self.selected_backend,
            "bm25_enabled": selected_mode in {"bm25", "hybrid"},
            "vector_enabled": selected_mode in {"vector", "hybrid"},
            "hybrid_enabled": selected_mode == "hybrid",
            "embedding_model": self.config_obj.embedding_model,
            "embedding_device": self.embedding_builder.last_report.get("embedding_device") or self.config_obj.embedding_device,
            "gpu_used_for_embedding": "cuda" in _clean(self.embedding_builder.last_report.get("embedding_device")).casefold(),
            "vector_index_kind": "weaviate_hnsw",
            "vector_index_type": "weaviate_hnsw_cosine",
            "vector_dim": self._vector_dim,
            "indexed_unit_count": indexed_object_count,
            "query_count": self._query_count,
            "weaviate_query_call_count": self._weaviate_query_call_count,
            "weaviate_query_count_per_item": round(
                float(self._weaviate_query_call_count) / float(self._query_count), 6
            )
            if self._query_count
            else 0.0,
            "fallback_reason": None if self._reachable else "weaviate_not_yet_invoked",
        }

    @property
    def retrieval_surface_report(self) -> dict[str, Any]:
        return {
            "requested": "source_native",
            "selected": "source_native",
            "source_native_available": True,
            "source_native_unit_count": 0,
            "source_native_selected": True,
            "searchunit_searchview_role": "legacy_comparison_debug_only",
            "searchunit_searchview_candidate_surface_enabled": False,
            "legacy_surface_comparison_enabled": False,
            "auto_fallback_to_searchunit_searchview": False,
            "fallback_reason": "",
        }

    @property
    def retrieval_surface_decision(self) -> dict[str, Any]:
        return {
            "selected_default_surface": "source_native",
            "searchunit_searchview_demoted": True,
            "demotion_reason": "weaviate_source_atom_service_boundary_selected",
            "source_native_available": True,
            "source_native_selected": True,
            "fallback_reason": "",
            "recommendation": "keep_weaviate_source_atom_boundary_for_active_candidate_generation",
        }

    @property
    def backend_diagnostics(self) -> dict[str, Any]:
        return {
            "embedding_build_latency_ms": float(self.embedding_builder.last_report.get("embedding_latency_ms") or 0.0),
            "index_load_or_build_latency_ms": 0.0,
            "vector_index_available": self._reachable,
            "gpu_used_for_embedding": "cuda" in _clean(self.embedding_builder.last_report.get("embedding_device")).casefold(),
            "fallback_reason": "" if self._reachable else "weaviate_not_yet_invoked",
        }

    @property
    def vector_index_audit_report(self) -> dict[str, Any]:
        indexed_object_count = self._indexed_object_count()
        return {
            "enabled": True,
            "status": "connected_weaviate_source_atom_candidate" if self._reachable else "weaviate_not_yet_invoked",
            "vector_surface": "source_native",
            "vector_backend": "weaviate",
            "vector_index_available": self._reachable,
            "vector_index_kind": "weaviate_hnsw",
            "vector_index_type": "weaviate_hnsw_cosine",
            "embedding_model": self.config_obj.embedding_model,
            "embedding_dim": self._vector_dim,
            "embedding_device": self.embedding_builder.last_report.get("embedding_device") or self.config_obj.embedding_device,
            "gpu_used_for_embedding": "cuda" in _clean(self.embedding_builder.last_report.get("embedding_device")).casefold(),
            "bge_m3_replacement_needed": False,
            "indexed_unit_count": indexed_object_count,
            "source_native_unit_count": indexed_object_count,
            "id_map_count": indexed_object_count,
            "index_integrity_passed": self._reachable,
            "query_invocation_passed": self._query_count > 0,
            "hydration_passed": self._query_count > 0,
            "hybrid_comparison_available": bool(self._candidate_counts["hybrid"]),
            "semantic_quality_claim_allowed": False,
            "raw_local_paths_exposed": False,
            "diagnostic_hash_vector_used": False,
            "faiss_used_for_active_retrieval": False,
            "limitations": ["Weaviate retrieval is non-production diagnostic evidence until larger evaluation closes."],
        }

    @property
    def external_vector_db_report(self) -> dict[str, Any]:
        return self.config_obj.external_vector_db_report(invoked=self._query_count > 0, reachable=self._reachable)

    def validate_ready_for_run(self) -> None:
        self.config_obj.validate_for_nonprod()
        self._validate_candidate_surface_metric_gate()
        try:
            self._reachable = bool(self.client.ping())
        except WeaviateUnavailableError:
            raise
        except Exception as exc:
            raise WeaviateUnavailableError(f"weaviate_unavailable: readiness failed:{type(exc).__name__}: {exc}") from exc
        if not self._reachable:
            raise WeaviateUnavailableError("weaviate_unavailable: readiness returned false")
        self._validated = True

    def _query_vector(self, query: str) -> list[float]:
        if self.selected_backend == "weaviate_bm25":
            return []
        vectors = self.embedding_builder.embed_queries([query])
        vector = vectors[0] if vectors else []
        self._vector_dim = len(vector)
        return vector

    def _query_mode(
        self,
        mode: str,
        query: str,
        query_vector: Sequence[float],
        *,
        top_k: int,
        filters: Mapping[str, Any],
    ) -> tuple[list[dict[str, Any]], float]:
        started = time.perf_counter()
        try:
            rows = self.client.query(
                mode=mode,
                query_text=query,
                query_vector=query_vector if mode in {"vector", "hybrid"} else None,
                filters=filters,
                limit=top_k,
                alpha=self.config_obj.hybrid_alpha,
            )
            self._weaviate_query_call_count += 1
        except WeaviateUnavailableError:
            raise
        except Exception as exc:
            raise WeaviateUnavailableError(f"weaviate_unavailable: {mode} query failed:{type(exc).__name__}: {exc}") from exc
        latency = round((time.perf_counter() - started) * 1000, 6)
        contexts = [
            _context_from_record(row, rank=rank, score=float(row.get("_score") or 0.0), backend=f"weaviate_{mode}")
            for rank, row in enumerate(rows[: max(0, int(top_k))], start=1)
        ]
        self._candidate_counts[mode].append(len(contexts))
        self._latencies[mode].append(latency)
        return contexts, latency

    def _query_variant_plan(self, query: str) -> dict[str, Any]:
        plan = plan_weaviate_query_variants(query)
        if self.retrieval_route_mode != "route_selected":
            variants = [_clean(query)] if _clean(query) else []
            return {
                **plan,
                "enabled": False,
                "query_variants": variants,
                "query_variant_count": len(variants),
                "disabled_reason": f"route_mode_{self.retrieval_route_mode}_uses_single_query",
            }
        return plan

    def _round_robin_query_variant_contexts(
        self,
        variant_contexts: Sequence[Sequence[Mapping[str, Any]]],
        *,
        top_k: int,
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        limit = max(0, int(top_k))
        if limit <= 0:
            return merged
        for rank_index in range(limit):
            for contexts in variant_contexts:
                if rank_index >= len(contexts):
                    continue
                merged.append(dict(contexts[rank_index]))
        return merged

    def _query_mode_with_variants(
        self,
        mode: str,
        query_variant_plan: Mapping[str, Any],
        *,
        top_k: int,
        filters: Mapping[str, Any],
    ) -> tuple[list[dict[str, Any]], float]:
        variants = [_clean(variant) for variant in query_variant_plan.get("query_variants") or [] if _clean(variant)]
        if not variants:
            return [], 0.0
        variant_contexts: list[list[dict[str, Any]]] = []
        total_latency = 0.0
        for variant_index, variant in enumerate(variants, start=1):
            query_vector = self._query_vector(variant) if mode in {"vector", "hybrid"} else []
            contexts, latency = self._query_mode(
                mode,
                variant,
                query_vector,
                top_k=top_k,
                filters=filters,
            )
            for context in contexts:
                context["query_variant_provenance"] = [variant]
                context["query_variant_rank"] = variant_index
                context["query_variant_planner_version"] = WEAVIATE_QUERY_REFORMULATION_VERSION
            variant_contexts.append(contexts)
            total_latency += latency
        return self._round_robin_query_variant_contexts(variant_contexts, top_k=top_k), round(total_latency, 6)

    def _same_doc_residual_doc_ids(self, contexts: Sequence[Mapping[str, Any]]) -> list[str]:
        doc_ids: list[str] = []
        for context in contexts:
            if _clean(context.get("source_family")) != "TEXT":
                continue
            doc_id = _clean(context.get("doc_id"))
            if doc_id and doc_id not in doc_ids:
                doc_ids.append(doc_id)
            if len(doc_ids) >= WEAVIATE_SAME_DOC_RESIDUAL_MAX_DOCS:
                break
        return doc_ids

    def _query_same_doc_residual_contexts(
        self,
        mode: str,
        query_variant_plan: Mapping[str, Any],
        contexts: Sequence[Mapping[str, Any]],
        *,
        filters: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        if self.retrieval_route_mode != "route_selected":
            return []
        if int(query_variant_plan.get("query_variant_count") or 0) <= 1:
            return []
        doc_ids = self._same_doc_residual_doc_ids(contexts)
        if not doc_ids:
            return []
        existing_ids = {_clean(context.get("source_atom_id")) for context in contexts if _clean(context.get("source_atom_id"))}
        added: list[dict[str, Any]] = []
        queries_before = self._weaviate_query_call_count
        for doc_id in doc_ids:
            residual_filters = dict(filters)
            residual_filters["doc_id"] = doc_id
            started = time.perf_counter()
            candidates, _latency = self._query_mode_with_variants(
                mode,
                query_variant_plan,
                top_k=WEAVIATE_SAME_DOC_RESIDUAL_TOP_K_PER_DOC,
                filters=residual_filters,
            )
            self._same_doc_residual_latency_ms.append(round((time.perf_counter() - started) * 1000, 6))
            candidates, removed = self._safety_filter_contexts(candidates, filters=filters)
            self._post_filter_removed_count += removed
            for candidate in candidates:
                source_atom_id = _clean(candidate.get("source_atom_id"))
                if source_atom_id and source_atom_id in existing_ids:
                    continue
                if _clean(candidate.get("doc_id")) != doc_id:
                    continue
                row = dict(candidate)
                row["same_doc_residual_expansion_policy"] = WEAVIATE_SAME_DOC_RESIDUAL_RETRIEVAL_POLICY
                row["same_doc_residual_source_doc_id"] = doc_id
                row["same_doc_residual_candidate_generation"] = (
                    "weaviate_doc_id_filter_plus_query_variants_no_gold_qrels_labels_ids_or_baseline"
                )
                added.append(row)
                if source_atom_id:
                    existing_ids.add(source_atom_id)
                if len(added) >= WEAVIATE_SAME_DOC_RESIDUAL_TOP_K_PER_DOC:
                    break
            if len(added) >= WEAVIATE_SAME_DOC_RESIDUAL_TOP_K_PER_DOC:
                break
        query_delta = self._weaviate_query_call_count - queries_before
        self._same_doc_residual_query_count += max(0, query_delta)
        if added:
            self._same_doc_residual_added_count += len(added)
            self._same_doc_residual_expanded_item_count += 1
        return added

    def _xlsx_scoped_expansion_scopes(self, contexts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        scopes: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str, str]] = set()
        for context in contexts:
            if _clean(context.get("source_family")) != "XLSX":
                continue
            doc_id = _clean(context.get("doc_id"))
            sheet = _clean(context.get("sheet"))
            if not doc_id or not sheet:
                continue
            table_id = _clean(context.get("table_id"))
            cell_range = _clean(context.get("cell_range"))
            row_index = _clean(context.get("row_index_1based"))
            row_label = _clean(context.get("row_label"))
            if table_id:
                scope_type = "same_table_row" if row_index else "same_table"
                scope_filters = {"source_family": "XLSX", "doc_id": doc_id, "sheet": sheet, "table_id": table_id}
            elif cell_range:
                scope_type = "same_cell_range_row" if row_index else "same_cell_range"
                scope_filters = {"source_family": "XLSX", "doc_id": doc_id, "sheet": sheet, "cell_range": cell_range}
            else:
                scope_type = "same_sheet"
                scope_filters = {"source_family": "XLSX", "doc_id": doc_id, "sheet": sheet}
            if row_index:
                scope_filters["row_index_1based"] = row_index
            key = (
                scope_type,
                doc_id,
                sheet,
                _clean(scope_filters.get("table_id")),
                _clean(scope_filters.get("cell_range")),
                _clean(scope_filters.get("row_index_1based")),
            )
            if key in seen:
                continue
            seen.add(key)
            scopes.append(
                {
                    "scope_type": scope_type,
                    "filters": scope_filters,
                    "row_label": row_label,
                    "source_atom_id": _clean(context.get("source_atom_id")),
                    "chunk_id": _clean(context.get("chunk_id")),
                    "axis_terms": _source_owned_scope_axis_terms(
                        context,
                        WEAVIATE_XLSX_SCOPED_QUERY_AXIS_FIELDS,
                    ),
                }
            )
            if len(scopes) >= WEAVIATE_XLSX_SCOPED_EXPANSION_MAX_SCOPES:
                break
        return scopes

    def _xlsx_scoped_query_text(self, query: str, scope: Mapping[str, Any]) -> str:
        filters = scope.get("filters") if isinstance(scope.get("filters"), Mapping) else {}
        parts = [_clean(query), _clean(filters.get("sheet"))]
        for key in ("table_id", "cell_range"):
            value = _clean(filters.get(key))
            if value:
                parts.append(value)
        axis_terms = scope.get("axis_terms") if isinstance(scope.get("axis_terms"), Sequence) else []
        for term in axis_terms:
            value = _clean(term)
            if value:
                parts.append(value)
        seen: set[str] = set()
        cleaned: list[str] = []
        for part in parts:
            if part and part not in seen:
                cleaned.append(part)
                seen.add(part)
        return " ".join(cleaned)

    def _context_matches_xlsx_scope(self, context: Mapping[str, Any], scope: Mapping[str, Any]) -> bool:
        filters = scope.get("filters") if isinstance(scope.get("filters"), Mapping) else {}
        for key in ("doc_id", "sheet", "table_id", "cell_range", "row_index_1based"):
            value = _clean(filters.get(key))
            if value and _clean(context.get(key)) != value:
                return False
        return _clean(context.get("source_family")) == "XLSX"

    def _query_xlsx_row_value_bundle_contexts_for_scope(
        self,
        mode: str,
        query: str,
        scope: Mapping[str, Any],
        *,
        filters: Mapping[str, Any],
        existing_ids: set[str],
    ) -> list[dict[str, Any]]:
        if not self._route_filter_field_available("candidate_surface_materialization"):
            return []
        scope_filters = scope.get("filters") if isinstance(scope.get("filters"), Mapping) else {}
        bundle_filters = dict(filters)
        bundle_filters.update(scope_filters)
        bundle_filters["candidate_surface_materialization"] = WEAVIATE_XLSX_ROW_VALUE_BUNDLE_MATERIALIZATION
        if not _clean(bundle_filters.get("row_index_1based")):
            row_label = _clean(scope.get("row_label"))
            if not row_label:
                return []
            bundle_filters["row_label"] = row_label
        bundle_query = " ".join(
            part
            for part in (
                self._xlsx_scoped_query_text(query, scope),
                WEAVIATE_XLSX_ROW_VALUE_BUNDLE_MATERIALIZATION,
            )
            if _clean(part)
        )
        query_vector = self._query_vector(bundle_query) if mode in {"vector", "hybrid"} else []
        started = time.perf_counter()
        candidates, _latency = self._query_mode(
            mode,
            bundle_query,
            query_vector,
            top_k=WEAVIATE_XLSX_SCOPED_EXPANSION_TOP_K_PER_SCOPE,
            filters=bundle_filters,
        )
        self._xlsx_scoped_expansion_latency_ms.append(round((time.perf_counter() - started) * 1000, 6))
        candidates, removed = self._safety_filter_contexts(candidates, filters=filters)
        self._post_filter_removed_count += removed
        scope_type = _clean(scope.get("scope_type"))
        added: list[dict[str, Any]] = []
        for candidate in candidates:
            source_atom_id = _clean(candidate.get("source_atom_id"))
            if source_atom_id and source_atom_id in existing_ids:
                continue
            if _clean(candidate.get("candidate_surface_materialization")) != WEAVIATE_XLSX_ROW_VALUE_BUNDLE_MATERIALIZATION:
                continue
            if not self._context_matches_xlsx_scope(candidate, scope):
                continue
            if not _clean(scope_filters.get("row_index_1based")):
                row_label = _clean(scope.get("row_label"))
                if row_label and _clean(candidate.get("row_label")) != row_label:
                    continue
            row = dict(candidate)
            row["xlsx_scoped_expansion_policy"] = WEAVIATE_XLSX_SCOPED_EXPANSION_POLICY
            row["xlsx_scoped_expansion_scope_type"] = scope_type
            row["xlsx_scoped_expansion_source_atom_id"] = _clean(scope.get("source_atom_id"))
            row["xlsx_scoped_expansion_source_chunk_id"] = _clean(scope.get("chunk_id"))
            row["xlsx_scoped_expansion_candidate_generation"] = (
                "weaviate_source_owned_same_row_bundle_filter_plus_query_text_no_gold_qrels_labels_ids_or_baseline"
            )
            row["xlsx_row_value_bundle_recall_policy"] = WEAVIATE_XLSX_ROW_VALUE_BUNDLE_RECALL_POLICY
            row["xlsx_row_value_bundle_recall_candidate_generation"] = (
                "weaviate_source_owned_same_row_bundle_filter_plus_query_text_no_gold_qrels_labels_ids_or_baseline"
            )
            added.append(row)
            if source_atom_id:
                existing_ids.add(source_atom_id)
            self._xlsx_scoped_expansion_scope_counts[scope_type] = (
                self._xlsx_scoped_expansion_scope_counts.get(scope_type, 0) + 1
            )
            if len(added) >= WEAVIATE_XLSX_SCOPED_EXPANSION_TOP_K_PER_SCOPE:
                break
        return added

    def _query_xlsx_scoped_expansion_contexts(
        self,
        mode: str,
        query: str,
        contexts: Sequence[Mapping[str, Any]],
        *,
        filters: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        if self.retrieval_route_mode != "route_selected":
            return []
        scopes = self._xlsx_scoped_expansion_scopes(contexts)
        if not scopes:
            return []
        existing_ids = {_clean(context.get("source_atom_id")) for context in contexts if _clean(context.get("source_atom_id"))}
        added: list[dict[str, Any]] = []
        queries_before = self._weaviate_query_call_count
        for scope in scopes:
            scope_filters = scope.get("filters") if isinstance(scope.get("filters"), Mapping) else {}
            residual_filters = dict(filters)
            residual_filters.update(scope_filters)
            for row in self._query_xlsx_row_value_bundle_contexts_for_scope(
                mode,
                query,
                scope,
                filters=filters,
                existing_ids=existing_ids,
            ):
                added.append(row)
                if len(added) >= WEAVIATE_XLSX_SCOPED_EXPANSION_TOP_K_PER_SCOPE:
                    break
            if len(added) >= WEAVIATE_XLSX_SCOPED_EXPANSION_TOP_K_PER_SCOPE:
                break
            scoped_query = self._xlsx_scoped_query_text(query, scope)
            query_vector = self._query_vector(scoped_query) if mode in {"vector", "hybrid"} else []
            started = time.perf_counter()
            candidates, _latency = self._query_mode(
                mode,
                scoped_query,
                query_vector,
                top_k=WEAVIATE_XLSX_SCOPED_EXPANSION_TOP_K_PER_SCOPE,
                filters=residual_filters,
            )
            self._xlsx_scoped_expansion_latency_ms.append(round((time.perf_counter() - started) * 1000, 6))
            candidates, removed = self._safety_filter_contexts(candidates, filters=filters)
            self._post_filter_removed_count += removed
            scope_type = _clean(scope.get("scope_type"))
            for candidate in candidates:
                source_atom_id = _clean(candidate.get("source_atom_id"))
                if source_atom_id and source_atom_id in existing_ids:
                    continue
                if not self._context_matches_xlsx_scope(candidate, scope):
                    continue
                row = dict(candidate)
                row["xlsx_scoped_expansion_policy"] = WEAVIATE_XLSX_SCOPED_EXPANSION_POLICY
                row["xlsx_scoped_expansion_scope_type"] = scope_type
                row["xlsx_scoped_expansion_source_atom_id"] = _clean(scope.get("source_atom_id"))
                row["xlsx_scoped_expansion_source_chunk_id"] = _clean(scope.get("chunk_id"))
                row["xlsx_scoped_expansion_candidate_generation"] = (
                    "weaviate_source_owned_scope_filter_plus_query_text_no_gold_qrels_labels_ids_or_baseline"
                )
                added.append(row)
                if source_atom_id:
                    existing_ids.add(source_atom_id)
                self._xlsx_scoped_expansion_scope_counts[scope_type] = (
                    self._xlsx_scoped_expansion_scope_counts.get(scope_type, 0) + 1
                )
                if len(added) >= WEAVIATE_XLSX_SCOPED_EXPANSION_TOP_K_PER_SCOPE:
                    break
            if len(added) >= WEAVIATE_XLSX_SCOPED_EXPANSION_TOP_K_PER_SCOPE:
                break
        query_delta = self._weaviate_query_call_count - queries_before
        self._xlsx_scoped_expansion_query_count += max(0, query_delta)
        if added:
            self._xlsx_scoped_expansion_added_count += len(added)
            self._xlsx_scoped_expansion_expanded_item_count += 1
        return added

    def _pdf_scoped_expansion_scopes(self, contexts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        scopes: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str, str]] = set()
        for context in contexts:
            if _clean(context.get("source_family")) != "PDF":
                continue
            doc_id = _clean(context.get("doc_id"))
            if not doc_id:
                continue
            page_number = _clean(context.get("page_number") or context.get("page"))
            section_title = _clean(context.get("section_title"))
            table_caption = _clean(context.get("table_caption"))
            if page_number and table_caption:
                scope_type = "same_table"
                scope_filters = {
                    "source_family": "PDF",
                    "doc_id": doc_id,
                    "page_number": page_number,
                    "table_caption": table_caption,
                }
                if section_title:
                    scope_filters["section_title"] = section_title
            elif page_number:
                scope_type = "same_page"
                scope_filters = {"source_family": "PDF", "doc_id": doc_id, "page_number": page_number}
            elif section_title:
                scope_type = "same_section"
                scope_filters = {"source_family": "PDF", "doc_id": doc_id, "section_title": section_title}
            else:
                scope_type = "same_doc"
                scope_filters = {"source_family": "PDF", "doc_id": doc_id}
            key = (
                scope_type,
                doc_id,
                _clean(scope_filters.get("page_number")),
                _clean(scope_filters.get("section_title")),
                _clean(scope_filters.get("table_caption")),
            )
            if key in seen:
                continue
            seen.add(key)
            scopes.append(
                {
                    "scope_type": scope_type,
                    "filters": scope_filters,
                    "source_atom_id": _clean(context.get("source_atom_id")),
                    "chunk_id": _clean(context.get("chunk_id")),
                    "axis_terms": _source_owned_scope_axis_terms(
                        context,
                        WEAVIATE_PDF_SCOPED_QUERY_AXIS_FIELDS,
                    ),
                }
            )
            if len(scopes) >= WEAVIATE_PDF_SCOPED_EXPANSION_MAX_SCOPES:
                break
        return scopes

    def _pdf_scoped_query_text(self, query: str, scope: Mapping[str, Any]) -> str:
        filters = scope.get("filters") if isinstance(scope.get("filters"), Mapping) else {}
        parts = [
            _clean(query),
            _clean(filters.get("page_number")),
            _clean(filters.get("section_title")),
            _clean(filters.get("table_caption")),
        ]
        axis_terms = scope.get("axis_terms") if isinstance(scope.get("axis_terms"), Sequence) else []
        for term in axis_terms:
            value = _clean(term)
            if value:
                parts.append(value)
        seen: set[str] = set()
        cleaned: list[str] = []
        for part in parts:
            if part and part not in seen:
                cleaned.append(part)
                seen.add(part)
        return " ".join(cleaned)

    def _context_matches_pdf_scope(self, context: Mapping[str, Any], scope: Mapping[str, Any]) -> bool:
        filters = scope.get("filters") if isinstance(scope.get("filters"), Mapping) else {}
        for key in ("doc_id", "page_number", "section_title", "table_caption"):
            value = _clean(filters.get(key))
            if value and _clean(context.get(key)) != value:
                return False
        return _clean(context.get("source_family")) == "PDF"

    def _query_pdf_scoped_expansion_contexts(
        self,
        mode: str,
        query: str,
        contexts: Sequence[Mapping[str, Any]],
        *,
        filters: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        if self.retrieval_route_mode != "route_selected":
            return []
        scopes = self._pdf_scoped_expansion_scopes(contexts)
        if not scopes:
            return []
        existing_ids = {_clean(context.get("source_atom_id")) for context in contexts if _clean(context.get("source_atom_id"))}
        added: list[dict[str, Any]] = []
        queries_before = self._weaviate_query_call_count
        for scope in scopes:
            scope_filters = scope.get("filters") if isinstance(scope.get("filters"), Mapping) else {}
            residual_filters = dict(filters)
            residual_filters.update(scope_filters)
            scoped_query = self._pdf_scoped_query_text(query, scope)
            query_vector = self._query_vector(scoped_query) if mode in {"vector", "hybrid"} else []
            started = time.perf_counter()
            candidates, _latency = self._query_mode(
                mode,
                scoped_query,
                query_vector,
                top_k=WEAVIATE_PDF_SCOPED_EXPANSION_TOP_K_PER_SCOPE,
                filters=residual_filters,
            )
            self._pdf_scoped_expansion_latency_ms.append(round((time.perf_counter() - started) * 1000, 6))
            candidates, removed = self._safety_filter_contexts(candidates, filters=filters)
            self._post_filter_removed_count += removed
            scope_type = _clean(scope.get("scope_type"))
            for candidate in candidates:
                source_atom_id = _clean(candidate.get("source_atom_id"))
                if source_atom_id and source_atom_id in existing_ids:
                    continue
                if not self._context_matches_pdf_scope(candidate, scope):
                    continue
                row = dict(candidate)
                row["pdf_scoped_expansion_policy"] = WEAVIATE_PDF_SCOPED_EXPANSION_POLICY
                row["pdf_scoped_expansion_scope_type"] = scope_type
                row["pdf_scoped_expansion_source_atom_id"] = _clean(scope.get("source_atom_id"))
                row["pdf_scoped_expansion_source_chunk_id"] = _clean(scope.get("chunk_id"))
                row["pdf_scoped_expansion_candidate_generation"] = (
                    "weaviate_source_owned_pdf_scope_filter_plus_query_text_no_gold_qrels_labels_ids_or_baseline"
                )
                added.append(row)
                if source_atom_id:
                    existing_ids.add(source_atom_id)
                self._pdf_scoped_expansion_scope_counts[scope_type] = (
                    self._pdf_scoped_expansion_scope_counts.get(scope_type, 0) + 1
                )
                if len(added) >= WEAVIATE_PDF_SCOPED_EXPANSION_TOP_K_PER_SCOPE:
                    break
            if len(added) >= WEAVIATE_PDF_SCOPED_EXPANSION_TOP_K_PER_SCOPE:
                break
        query_delta = self._weaviate_query_call_count - queries_before
        self._pdf_scoped_expansion_query_count += max(0, query_delta)
        if added:
            self._pdf_scoped_expansion_added_count += len(added)
            self._pdf_scoped_expansion_expanded_item_count += 1
        return added

    def _structural_key(self, context: Mapping[str, Any]) -> str:
        source_family = _clean(context.get("source_family"))
        if source_family == "XLSX":
            materialization = _clean(context.get("candidate_surface_materialization"))
            locator = [
                materialization
                if materialization == WEAVIATE_XLSX_ROW_VALUE_BUNDLE_MATERIALIZATION
                else "",
                _clean(context.get("sheet")),
                _clean(context.get("cell_range")),
                _clean(context.get("row_index_1based")),
                _clean(context.get("cell")),
                _clean(context.get("row_label")),
                _clean(context.get("column_label")),
                _clean(context.get("target_column")),
                _clean(context.get("header_path")),
                _clean(context.get("table_id")),
            ]
            if any(locator):
                return "|".join([source_family, _clean(context.get("doc_id")), *locator])
            return "|".join([source_family, _clean(context.get("doc_id")), _clean(context.get("chunk_id"))])
        if source_family == "PDF":
            locator = [_clean(context.get("page_number")), _clean(context.get("bbox"))]
            if any(locator):
                return "|".join([source_family, _clean(context.get("doc_id")), *locator])
            return "|".join([source_family, _clean(context.get("doc_id")), _clean(context.get("chunk_id"))])
        return "|".join([source_family, _clean(context.get("doc_id")), _clean(context.get("chunk_id"))])

    def _collapse_route_selected_duplicates(
        self,
        contexts: Sequence[Mapping[str, Any]],
        *,
        top_k: int,
    ) -> tuple[list[dict[str, Any]], int]:
        if self.retrieval_route_mode != "route_selected":
            return [dict(context) for context in contexts[: max(0, int(top_k))]], 0
        kept: list[dict[str, Any]] = []
        seen_text: set[str] = set()
        seen_structure: set[str] = set()
        doc_counts: dict[str, int] = {}
        removed = 0
        for context in contexts:
            row = dict(context)
            text_key = _clean(row.get("text_sha256") or row.get("source_text_sha256"))
            structure_key = self._structural_key(row)
            doc_key = _clean(row.get("doc_id"))
            source_family = _clean(row.get("source_family"))
            granularity = _clean(row.get("granularity"))
            if (
                source_family == "XLSX"
                and _clean(row.get("candidate_surface_materialization"))
                == WEAVIATE_XLSX_ROW_VALUE_BUNDLE_MATERIALIZATION
            ):
                doc_limit = 4
            elif source_family == "XLSX" and granularity == "cell":
                doc_limit = 4
            elif source_family == "PDF" and _clean(row.get("pdf_scoped_expansion_policy")):
                doc_limit = 2
            elif source_family in {"PDF", "XLSX"}:
                doc_limit = 1
            else:
                doc_limit = 3
            if text_key and text_key in seen_text:
                removed += 1
                continue
            if structure_key and structure_key in seen_structure:
                removed += 1
                continue
            if doc_key and doc_counts.get(doc_key, 0) >= doc_limit:
                removed += 1
                continue
            kept.append(row)
            if text_key:
                seen_text.add(text_key)
            if structure_key:
                seen_structure.add(structure_key)
            if doc_key:
                doc_counts[doc_key] = doc_counts.get(doc_key, 0) + 1
            if len(kept) >= max(0, int(top_k)):
                break
        return kept, removed

    def _context_matches_neighbor_filter(
        self,
        anchor: Mapping[str, Any],
        neighbor: Mapping[str, Any],
        filters: Mapping[str, Any],
    ) -> bool:
        if _clean(filters.get("source_family")) and _clean(neighbor.get("source_family")) != _clean(anchor.get("source_family")):
            return False
        if _clean(neighbor.get("doc_id")) != _clean(anchor.get("doc_id")):
            return False
        if _clean(anchor.get("sheet")) and _clean(neighbor.get("sheet")) != _clean(anchor.get("sheet")):
            return False
        if _clean(anchor.get("cell_range")) and _clean(neighbor.get("cell_range")) != _clean(anchor.get("cell_range")):
            return False
        if _clean(anchor.get("page_number")) and _clean(neighbor.get("page_number")) != _clean(anchor.get("page_number")):
            return False
        return True

    def _neighbor_granularity_for_anchor(self, anchor: Mapping[str, Any]) -> str:
        if _clean(anchor.get("source_family")) == "XLSX" and _clean(anchor.get("granularity")) in {
            "table_row",
            "table_summary",
        } and (_clean(anchor.get("sheet")) or _clean(anchor.get("cell_range"))):
            return "cell"
        return ""

    def _fetch_weaviate_id_neighbor(
        self,
        anchor: Mapping[str, Any],
        *,
        filters: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        neighbor_granularity = self._neighbor_granularity_for_anchor(anchor)
        anchor_id = _clean(anchor.get("source_atom_id"))
        if not anchor_id or not neighbor_granularity:
            return None
        neighbor_filters = {
            "namespace": filters.get("namespace"),
            "visibility": filters.get("visibility"),
            "source_atom_id": anchor_id,
            "neighbor_granularity": neighbor_granularity,
        }
        started = time.perf_counter()
        try:
            rows = self.client.query(
                mode="neighbor_by_id",
                query_text="",
                query_vector=None,
                filters=neighbor_filters,
                limit=1,
                alpha=self.config_obj.hybrid_alpha,
            )
            self._weaviate_query_call_count += 1
        except WeaviateUnavailableError:
            raise
        except Exception as exc:
            raise WeaviateUnavailableError(
                f"weaviate_unavailable: neighbor_by_id query failed:{type(exc).__name__}: {exc}"
            ) from exc
        self._neighbor_expansion_query_count += 1
        self._neighbor_expansion_latency_ms.append(round((time.perf_counter() - started) * 1000, 6))
        if not rows:
            return None
        neighbor = _context_from_record(rows[0], rank=0, score=0.0, backend="weaviate_neighbor_by_id")
        neighbor["neighbor_expansion_source_atom_id"] = anchor_id
        neighbor["neighbor_expansion_source_chunk_id"] = _clean(anchor.get("chunk_id"))
        return neighbor

    def _post_process_selected_contexts(
        self,
        contexts: Sequence[Mapping[str, Any]],
        *,
        filters: Mapping[str, Any],
        top_k: int,
    ) -> list[dict[str, Any]]:
        collapsed, removed = self._collapse_route_selected_duplicates(contexts, top_k=top_k)
        self._duplicate_collapse_removed_count += removed
        if self.retrieval_route_mode != "route_selected":
            return collapsed
        result: list[dict[str, Any]] = []
        seen_source_atom_ids = {
            _clean(context.get("source_atom_id")) for context in collapsed if _clean(context.get("source_atom_id"))
        }
        neighbor_added_for_item = 0
        neighbor_attempted_for_item = 0
        for context in collapsed:
            result.append(dict(context))
            if len(result) >= max(0, int(top_k)):
                break
            if neighbor_added_for_item >= 1 or neighbor_attempted_for_item >= 1:
                continue
            neighbor_attempted_for_item += 1
            neighbor = self._fetch_weaviate_id_neighbor(context, filters=filters)
            if not neighbor:
                continue
            neighbor_id = _clean(neighbor.get("source_atom_id"))
            if neighbor_id and neighbor_id in seen_source_atom_ids:
                continue
            if not self._context_matches_neighbor_filter(context, neighbor, filters):
                continue
            result.append(neighbor)
            if neighbor_id:
                seen_source_atom_ids.add(neighbor_id)
            self._neighbor_expansion_added_count += 1
            neighbor_added_for_item += 1
            if len(result) >= max(0, int(top_k)):
                break
        for rank, context in enumerate(result, start=1):
            context["rank"] = rank
        return result[: max(0, int(top_k))]

    def run_item(self, item: Any, *, top_k: int) -> dict[str, Any]:
        if not self._validated:
            self.validate_ready_for_run()
        query = _clean(getattr(item, "query", ""))
        source_row = getattr(item, "source_row", {})
        planner = source_row.get("query_evidence_planner") if isinstance(source_row, Mapping) else {}
        source_family_hint = self._query_evidence_source_family_hint_for_query(query, planner)
        filters, route_plan = self._lane_filter_plan(query, source_family_hint=source_family_hint)
        self._last_filter_policy = dict(route_plan.get("weaviate_filter_policy") or {})
        query_variant_plan = self._query_variant_plan(query)
        query_variant_count = int(query_variant_plan.get("query_variant_count") or 0)
        self._query_variant_counts.append(query_variant_count)
        self._last_query_variant_plan = dict(query_variant_plan)
        if query_variant_count > 1:
            self._query_variant_expanded_item_count += 1
        selected_mode = WEAVIATE_QUERY_MODES[self.selected_backend]
        selected_contexts, selected_latency = self._query_mode_with_variants(
            selected_mode,
            query_variant_plan,
            top_k=top_k,
            filters=filters,
        )
        selected_contexts, post_filter_removed_count = self._safety_filter_contexts(selected_contexts, filters=filters)
        self._post_filter_removed_count += post_filter_removed_count
        same_doc_residual_contexts = self._query_same_doc_residual_contexts(
            selected_mode,
            query_variant_plan,
            selected_contexts,
            filters=filters,
        )
        xlsx_scoped_expansion_contexts = self._query_xlsx_scoped_expansion_contexts(
            selected_mode,
            query,
            selected_contexts,
            filters=filters,
        )
        pdf_scoped_expansion_contexts = self._query_pdf_scoped_expansion_contexts(
            selected_mode,
            query,
            selected_contexts,
            filters=filters,
        )
        if same_doc_residual_contexts:
            selected_contexts = [*same_doc_residual_contexts, *selected_contexts]
        if xlsx_scoped_expansion_contexts:
            selected_contexts = [*xlsx_scoped_expansion_contexts, *selected_contexts]
        if pdf_scoped_expansion_contexts:
            selected_contexts = [*pdf_scoped_expansion_contexts, *selected_contexts]
        selected_contexts = self._post_process_selected_contexts(
            selected_contexts,
            filters=filters,
            top_k=top_k,
        )
        self._query_count += 1

        bm25_contexts: list[dict[str, Any]] = []
        vector_contexts: list[dict[str, Any]] = []
        hybrid_contexts: list[dict[str, Any]] = []
        bm25_latency = vector_latency = hybrid_latency = 0.0
        if selected_mode == "bm25":
            bm25_contexts, bm25_latency = selected_contexts, selected_latency
        elif selected_mode == "vector":
            vector_contexts, vector_latency = selected_contexts, selected_latency
        else:
            hybrid_contexts, hybrid_latency = selected_contexts, selected_latency
            query_vector = self._query_vector(query)
            vector_contexts, vector_latency = self._query_mode("vector", query, query_vector, top_k=top_k, filters=filters)
            vector_contexts, removed = self._safety_filter_contexts(vector_contexts, filters=filters)
            self._post_filter_removed_count += removed
            bm25_contexts, bm25_latency = self._query_mode("bm25", query, query_vector, top_k=top_k, filters=filters)
            bm25_contexts, removed = self._safety_filter_contexts(bm25_contexts, filters=filters)
            self._post_filter_removed_count += removed

        citations = [_normalize_citation(context) for context in selected_contexts]
        generated_answer = self.generator.generate(query, [_context_to_chunk(context) for context in selected_contexts])
        output = {
            "id": _clean(getattr(item, "id", "")),
            "query": query,
            "answerability": _clean(getattr(item, "answerability", "")) or "unknown",
            "generated_answer": generated_answer,
            "retrieved_contexts": [dict(context) for context in selected_contexts],
            "weaviate_route_plan": {
                key: value for key, value in route_plan.items() if key != "weaviate_filter_policy"
            },
            "weaviate_filter_policy": dict(route_plan.get("weaviate_filter_policy") or {}),
            "weaviate_filter_sent": bool((route_plan.get("weaviate_filter_policy") or {}).get("weaviate_filter_sent")),
            "weaviate_query_reformulation": dict(query_variant_plan),
            "weaviate_same_doc_residual_retrieval": {
                "enabled": bool(same_doc_residual_contexts),
                "policy": WEAVIATE_SAME_DOC_RESIDUAL_RETRIEVAL_POLICY,
                "query_count": self._same_doc_residual_query_count,
                "added_count": len(same_doc_residual_contexts),
                "candidate_generation": "weaviate_doc_id_filter_plus_query_variants_no_gold_qrels_labels_ids_or_baseline",
                "uses_gold_fields": False,
                "uses_expected_fields": False,
                "uses_qrels": False,
                "uses_labels": False,
                "uses_ids": False,
                "uses_protected_eval_ids": False,
                "uses_source_owned_scope_ids": True,
                "uses_baseline_topk": False,
                "uses_legacy_outputs": False,
            },
            "weaviate_xlsx_scoped_expansion": {
                "enabled": bool(xlsx_scoped_expansion_contexts),
                "policy": WEAVIATE_XLSX_SCOPED_EXPANSION_POLICY,
                "query_count": self._xlsx_scoped_expansion_query_count,
                "added_count": len(xlsx_scoped_expansion_contexts),
                "scope_counts": dict(sorted(self._xlsx_scoped_expansion_scope_counts.items())),
                "candidate_generation": (
                    "weaviate_source_owned_scope_filter_plus_query_text_no_gold_qrels_labels_ids_or_baseline"
                ),
                "uses_gold_fields": False,
                "uses_expected_fields": False,
                "uses_qrels": False,
                "uses_labels": False,
                "uses_ids": False,
                "uses_protected_eval_ids": False,
                "uses_source_owned_scope_ids": True,
                "uses_baseline_topk": False,
                "uses_legacy_outputs": False,
                "uses_formula": False,
                "uses_normalized_value": False,
                "uses_raw_xlsx_query_time_parsing": False,
            },
            "weaviate_pdf_scoped_expansion": {
                "enabled": bool(pdf_scoped_expansion_contexts),
                "policy": WEAVIATE_PDF_SCOPED_EXPANSION_POLICY,
                "query_count": self._pdf_scoped_expansion_query_count,
                "added_count": len(pdf_scoped_expansion_contexts),
                "scope_counts": dict(sorted(self._pdf_scoped_expansion_scope_counts.items())),
                "candidate_generation": (
                    "weaviate_source_owned_pdf_scope_filter_plus_query_text_no_gold_qrels_labels_ids_or_baseline"
                ),
                "uses_gold_fields": False,
                "uses_expected_fields": False,
                "uses_qrels": False,
                "uses_labels": False,
                "uses_ids": False,
                "uses_protected_eval_ids": False,
                "uses_source_owned_scope_ids": True,
                "uses_baseline_topk": False,
                "uses_legacy_outputs": False,
                "uses_filename_or_title_shortcut": False,
                "uses_raw_pdf_query_time_parsing": False,
            },
            "python_post_filter_only_safety_validation": True,
            "post_filter_removed_count": post_filter_removed_count,
            "weaviate_post_processing": self.weaviate_post_processing_report,
            "citations": citations,
            "expected_answer": _clean(getattr(item, "expected_answer", "")),
            "expected_answer_aliases": list(getattr(item, "expected_answer_aliases", []) or []),
            "expected_evidence": [evidence.to_dict() for evidence in getattr(item, "expected_evidence", [])],
            "metric_inputs_available": {
                "has_expected_answer": bool(getattr(item, "has_expected_answer", False)),
                "has_expected_evidence": bool(getattr(item, "has_expected_evidence", False)),
                "has_answerability_label": bool(getattr(item, "has_answerability_label", False)),
                "has_citations": bool(citations),
            },
            "diagnostics": {
                "retrieval_empty": not bool(selected_contexts),
                "generation_empty": not bool(generated_answer),
                "citation_empty": not bool(citations),
                "gold_incomplete": True,
            },
            "retrieval_backend_comparison": _comparison(
                requested_backend=self.requested_backend,
                selected_backend=self.selected_backend,
                bm25_contexts=bm25_contexts,
                vector_contexts=vector_contexts,
                hybrid_contexts=hybrid_contexts,
                selected_contexts=selected_contexts,
                bm25_latency_ms=bm25_latency,
                vector_latency_ms=vector_latency,
                hybrid_latency_ms=hybrid_latency,
                vector_dim=self._vector_dim,
                embedding_model=self.config_obj.embedding_model,
            ),
            "source_native_layered_retrieval": {
                "enabled": False,
                "planner": "weaviate_source_atom_service_boundary",
                "selected_surface": "source_native",
                "selected_backend": self.selected_backend,
                "layers": [],
                "final_candidate_count": 0,
                "source_native_units_only": False,
                "fallback_reason": "disabled_for_weaviate_active_lane",
            },
        }
        output["diagnostics"]["retrieval_backend_comparison"] = output["retrieval_backend_comparison"]
        output["diagnostics"]["source_native_layered_retrieval"] = output["source_native_layered_retrieval"]
        return output

    def evidence_candidates(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        if not self._validated:
            self.validate_ready_for_run()
        filters, _route_plan = self._lane_filter_plan(query)
        query_variant_plan = self._query_variant_plan(query)
        contexts, _latency = self._query_mode_with_variants(
            WEAVIATE_QUERY_MODES[self.selected_backend],
            query_variant_plan,
            top_k=top_k,
            filters=filters,
        )
        contexts, _removed = self._safety_filter_contexts(contexts, filters=filters)
        return contexts

    def full_corpus_evidence_candidates(self, item: Any, evidence: Any, *, top_k: int) -> list[dict[str, Any]]:
        return []

    def close(self) -> None:
        self.client.close()


def build_default_weaviate_adapter(
    *,
    requested_backend: str,
    retrieval_route_mode: str | None = None,
    config_path: str | None = None,
    client: WeaviateSourceAtomClientProtocol | None = None,
    embedding_provider: Any | None = None,
) -> WeaviateSourceAtomAdapter:
    config, selected_route_mode, config_report = load_weaviate_adapter_config_path(
        requested_route_mode=retrieval_route_mode,
        config_path=config_path,
    )
    return WeaviateSourceAtomAdapter(
        config=config,
        client=client,
        embedding_provider=embedding_provider,
        requested_backend=requested_backend,
        retrieval_route_mode=selected_route_mode,
        default_config_report=config_report,
    )
