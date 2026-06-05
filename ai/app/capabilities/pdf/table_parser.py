"""General deterministic PDF table extraction from native text blocks.

The parser is intentionally conservative: it extracts only repeated numeric
grid structures that are already explicit in native PDF text blocks. It does
not assign domain semantics to columns, run OCR, inspect gold answers, or treat
the extracted grid as proof of answer quality.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any, Mapping, Sequence, TypedDict

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover - exercised only in minimal envs
    END = START = StateGraph = None


PARSER_VERSION = "pdf-table-general-v1"
TABLE_NODE_CONTRACT_SEQUENCE = ("table_candidate", "table_interpretation")
NUMERIC_RE = re.compile(r"^[△▲-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?$|^[△▲-]?\d+(?:\.\d+)?%?$")
PERIOD_RE = re.compile(r"^\d{4}(?:\.\s*(?:\d{1,2}|[ⅠⅡⅢⅣIVX]+))?$")
ROW_LABEL_WITH_DIGIT_RE = re.compile(r"^(?=.*\d)[A-Za-z가-힣0-9_.() \-]{1,80}$")
_MIN_GRID_ROWS = 2
_MIN_GRID_VALUES = 2
_MAX_GRID_VALUES = 12
_MAX_ROW_LABEL_CHARS = 80


class PdfTableUnderstandingState(TypedDict, total=False):
    pdf_blocks: list[Mapping[str, Any]]
    blocks: list[Mapping[str, Any]]
    page_no: int
    page: int
    physical_page_index: int
    page_label: str
    table_candidates: list[dict[str, Any]]
    table_interpretations: list[dict[str, Any]]
    trace: list[dict[str, Any]]


class TableCandidateNodeInput(TypedDict, total=False):
    pdf_blocks: list[Mapping[str, Any]]
    blocks: list[Mapping[str, Any]]
    page_no: int
    page: int
    physical_page_index: int
    page_label: str
    trace: list[dict[str, Any]]


class TableCandidateNodeOutput(TypedDict, total=False):
    table_candidates: list[dict[str, Any]]
    trace: list[dict[str, Any]]


class TableInterpretationNodeInput(TypedDict, total=False):
    table_candidates: list[dict[str, Any]]
    trace: list[dict[str, Any]]


class TableInterpretationNodeOutput(TypedDict, total=False):
    table_interpretations: list[dict[str, Any]]
    trace: list[dict[str, Any]]


class PdfTableGraphUnavailableError(RuntimeError):
    """Raised when LangGraph table execution is requested without LangGraph."""


def extract_pdf_table_records(
    blocks: list[Mapping[str, Any]],
    *,
    page_no: int,
    physical_page_index: int,
    page_label: str | None = None,
) -> list[dict[str, Any]]:
    native_blocks = [
        block
        for block in sorted(blocks, key=lambda item: (int_or_zero(item.get("reading_order")), clean(item.get("block_id"))))
        if clean(block.get("text")) and block.get("ocr_used") is not True and not clean(block.get("block_type")).startswith("ocr")
    ]
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for parsed in parse_numeric_grid_tables(native_blocks):
        if not parsed.get("row_records"):
            continue
        row_source_ids = unique_strings(
            source_id
            for row in parsed.get("row_records") or []
            for source_id in row.get("source_block_ids") or []
        )
        key = (parsed["table_type"], tuple(row_source_ids or parsed["source_block_ids"]))
        if key in seen:
            continue
        seen.add(key)
        parsed.update(
            {
                "table_id": table_id_for(page_no, parsed["table_type"], parsed["source_block_ids"]),
                "page_no": page_no,
                "physical_page_index": physical_page_index,
                "page_label": page_label or str(page_no),
                "parser_version": PARSER_VERSION,
                "confidence": parsed.get("confidence") or "MEDIUM",
                "ocr_used": False,
                "table_semantics_success_claimed": False,
            }
        )
        records.append(parsed)
    return records


def looks_like_pdf_table_text(text: str) -> bool:
    blocks = [
        {
            "block_id": "probe",
            "block_type": "paragraph",
            "text": clean(text),
            "bbox": [],
            "reading_order": 0,
        }
    ]
    return bool(parse_numeric_grid_tables(blocks))


def table_candidate_node(state: Mapping[str, Any]) -> dict[str, Any]:
    """Extract deterministic table structure candidates from PDF blocks."""

    current = dict(state)
    candidates = extract_pdf_table_records(
        list(current.get("pdf_blocks") or current.get("blocks") or []),
        page_no=int_or_zero(current.get("page_no") or current.get("page")),
        physical_page_index=int_or_zero(current.get("physical_page_index")),
        page_label=clean(current.get("page_label")),
    )
    current["table_candidates"] = candidates
    current["trace"] = append_trace(
        current.get("trace", []),
        "table_candidate",
        {
            "candidate_count": len(candidates),
            "semantic_claimed": False,
        },
    )
    return current


def table_interpretation_node(
    state: Mapping[str, Any],
    *,
    semantic_provider: Any | None = None,
) -> dict[str, Any]:
    """Attach optional semantic interpretations without approving evidence."""

    current = dict(state)
    interpretations: list[dict[str, Any]] = []
    for candidate in list(current.get("table_candidates") or []):
        base = {
            "table_id": clean(candidate.get("table_id")),
            "semantic_status": "not_adjudicated",
            "table_semantics_success_claimed": False,
            "llm_or_mm_provider_used": False,
            "provider_version": "",
            "column_semantics": [],
            "row_semantics": [],
        }
        if semantic_provider is not None:
            base.update(_safe_table_semantic_proposal(semantic_provider, candidate))
        interpretations.append(base)
    current["table_interpretations"] = interpretations
    current["trace"] = append_trace(
        current.get("trace", []),
        "table_interpretation",
        {
            "interpretation_count": len(interpretations),
            "semantic_claimed": False,
        },
    )
    return current


def build_table_understanding_graph(*, semantic_provider: Any | None = None):
    """Compile the PDF table candidate/interpretation nodes as a LangGraph."""

    if StateGraph is None:
        raise PdfTableGraphUnavailableError("langgraph is not installed")
    graph = StateGraph(PdfTableUnderstandingState)
    graph.add_node("table_candidate_node", table_candidate_node)
    graph.add_node(
        "table_interpretation_node",
        lambda state: table_interpretation_node(state, semantic_provider=semantic_provider),
    )
    graph.add_edge(START, "table_candidate_node")
    graph.add_edge("table_candidate_node", "table_interpretation_node")
    graph.add_edge("table_interpretation_node", END)
    return graph.compile()


def run_table_understanding_langgraph(
    state: Mapping[str, Any],
    *,
    semantic_provider: Any | None = None,
) -> dict[str, Any]:
    """Run deterministic table candidates and optional semantic proposals via LangGraph."""

    graph = build_table_understanding_graph(semantic_provider=semantic_provider)
    return dict(graph.invoke(dict(state)))


def parse_numeric_grid_tables(blocks: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    tokens = tokenized_lines(blocks)
    groups = _numeric_row_groups(tokens)
    tables: list[dict[str, Any]] = []
    for group_index, group in enumerate(groups):
        if len(group) < _MIN_GRID_ROWS:
            continue
        value_count = len(group[0]["value_tokens"])
        headers, title_text, header_blocks = _infer_headers_and_title(
            tokens,
            blocks,
            first_row_start=int(group[0]["start"]),
            value_count=value_count,
        )
        rows: list[dict[str, Any]] = []
        total_tokens_by_block = Counter(token["block_id"] for token in tokens)
        for row_index, row in enumerate(group):
            row_tokens = [row["label_token"], *row["value_tokens"]]
            source_blocks = unique_blocks(row_tokens)
            row_bbox = union_bbox([token["bbox"] for token in row_tokens])
            row_tokens_by_block = Counter(token["block_id"] for token in row_tokens)
            bbox_granularity = (
                "row_only"
                if len(source_blocks) == 1
                and total_tokens_by_block[source_blocks[0]] == row_tokens_by_block[source_blocks[0]]
                else "table_only"
            )
            cells = []
            for column_index, value_token in enumerate(row["value_tokens"]):
                value = value_token["text"]
                cells.append(
                    {
                        "column_path": headers[column_index + 1],
                        "value_raw": value,
                        "value_number": numeric_value(value),
                        "unit": "",
                        "sign_convention": sign_convention(value),
                        "cell_bbox": None,
                        "bbox_granularity": bbox_granularity,
                        "source_block_id": value_token["block_id"],
                    }
                )
            rows.append(
                {
                    "row_index": row_index,
                    "row_label_raw": row["label_token"]["text"],
                    "row_label_normalized": row["label"],
                    "row_bbox": row_bbox,
                    "bbox_granularity": bbox_granularity,
                    "source_block_ids": source_blocks,
                    "cells": cells,
                }
            )
        source_block_ids = unique_blocks(
            token
            for row in group
            for token in [row["label_token"], *row["value_tokens"]]
        )
        source_id_set = set(source_block_ids)
        table_blocks = [
            block
            for block in blocks
            if clean(block.get("block_id")) in source_id_set
        ]
        if not table_blocks and blocks:
            table_blocks = [blocks[0]]
        tables.append(
            {
                "table_type": "numeric_grid",
                "title_block_id": clean(table_blocks[0].get("block_id")) if table_blocks else "",
                "title_text": title_text,
                "headers": headers,
                "header_blocks": header_blocks,
                "source_block_ids": source_block_ids,
                "table_bbox": union_bbox([parse_bbox(block.get("bbox")) for block in table_blocks]),
                "bbox_granularity": "row_only"
                if all(row["bbox_granularity"] == "row_only" for row in rows)
                else "table_only",
                "row_records": rows,
                "table_structure": {
                    "row_count": len(rows),
                    "value_column_count": value_count,
                    "detection_basis": "repeated_row_label_plus_numeric_values",
                    "group_index": group_index,
                },
            }
        )
    return tables


def _safe_table_semantic_proposal(
    semantic_provider: Any,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        proposal = semantic_provider.interpret_table(candidate)
    except Exception as ex:
        return {
            "semantic_status": "provider_error",
            "llm_or_mm_provider_used": True,
            "provider_error_type": type(ex).__name__,
        }
    if not isinstance(proposal, Mapping):
        return {
            "semantic_status": "invalid_provider_output",
            "llm_or_mm_provider_used": True,
        }
    provider_version = clean(proposal.get("provider_version"))
    column_semantics = proposal.get("column_semantics") or []
    row_semantics = proposal.get("row_semantics") or []
    if (
        not provider_version
        or not _valid_semantics_list(column_semantics)
        or not _valid_semantics_list(row_semantics)
    ):
        return {
            "semantic_status": "invalid_provider_output",
            "llm_or_mm_provider_used": True,
        }
    return {
        "semantic_status": "provider_proposed",
        "table_semantics_success_claimed": False,
        "llm_or_mm_provider_used": True,
        "provider_version": provider_version,
        "column_semantics": list(column_semantics),
        "row_semantics": list(row_semantics),
    }


def _valid_semantics_list(value: Any) -> bool:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        return False
    return all(isinstance(item, Mapping) for item in value)


def _numeric_row_groups(tokens: list[Mapping[str, Any]]) -> list[list[dict[str, Any]]]:
    candidates = _numeric_row_candidates(tokens)
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    previous_end = -1
    previous_value_count = 0
    for candidate in candidates:
        value_count = len(candidate["value_tokens"])
        if (
            current
            and value_count == previous_value_count
            and int(candidate["start"]) <= previous_end + 3
        ):
            current.append(candidate)
        else:
            if current:
                groups.append(current)
            current = [candidate]
        previous_end = int(candidate["end"])
        previous_value_count = value_count
    if current:
        groups.append(current)
    return [group for group in groups if len(group) >= _MIN_GRID_ROWS]


def _numeric_row_candidates(tokens: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    index = 0
    while index < len(tokens):
        label = normalize_row_label(tokens[index]["text"])
        if label:
            value_tokens: list[Mapping[str, Any]] = []
            cursor = index + 1
            while cursor < len(tokens) and len(value_tokens) < _MAX_GRID_VALUES:
                if not is_numeric_value(tokens[cursor]["text"]):
                    break
                value_tokens.append(tokens[cursor])
                cursor += 1
            value_count = _select_value_count(tokens, index, len(value_tokens))
            if value_count >= _MIN_GRID_VALUES:
                candidates.append(
                    {
                        "start": index,
                        "end": index + 1 + value_count,
                        "label": label,
                        "label_token": tokens[index],
                        "value_tokens": value_tokens[:value_count],
                    }
                )
                index = index + 1 + value_count
                continue
        index += 1
    return candidates


def _select_value_count(tokens: list[Mapping[str, Any]], label_index: int, numeric_run_length: int) -> int:
    for value_count in range(_MIN_GRID_VALUES, numeric_run_length + 1):
        next_index = label_index + 1 + value_count
        if next_index >= len(tokens) or normalize_row_label(tokens[next_index]["text"]):
            return value_count
    return 0


def _infer_headers_and_title(
    tokens: list[Mapping[str, Any]],
    blocks: list[Mapping[str, Any]],
    *,
    first_row_start: int,
    value_count: int,
) -> tuple[list[str], str, list[dict[str, Any]]]:
    prefix = [
        token
        for token in tokens[max(0, first_row_start - value_count - 6) : first_row_start]
        if _header_token_text(token["text"])
    ]
    value_headers = [_header_token_text(token["text"]) for token in prefix[-value_count:]]
    value_headers = [header for header in value_headers if header]
    while len(value_headers) < value_count:
        value_headers.append(f"value_{len(value_headers) + 1}")
    title_tokens = prefix[: max(0, len(prefix) - value_count)]
    title_text = " ".join(_header_token_text(token["text"]) for token in title_tokens if _header_token_text(token["text"]))
    if not title_text and blocks:
        title_text = _first_non_row_text(blocks)
    header_block_ids = {token["block_id"] for token in prefix}
    header_blocks = [
        block_summary(block)
        for block in blocks
        if clean(block.get("block_id")) in header_block_ids
    ][:4]
    return ["row_label", *value_headers[:value_count]], title_text, header_blocks


def _header_token_text(value: str) -> str:
    text = clean(value)
    if not text or is_numeric_value(text) or normalize_row_label(text):
        return ""
    if len(text) > _MAX_ROW_LABEL_CHARS:
        return ""
    return text


def _first_non_row_text(blocks: list[Mapping[str, Any]]) -> str:
    for block in blocks:
        for line in clean(block.get("text")).splitlines():
            text = _header_token_text(line)
            if text:
                return text
    return ""


def tokenized_lines(blocks: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    for block in blocks:
        block_id = clean(block.get("block_id"))
        bbox = parse_bbox(block.get("bbox"))
        for line in clean(block.get("text")).splitlines():
            text = clean(line)
            if not text:
                continue
            tokens.append({"text": text, "block_id": block_id, "bbox": bbox})
    return tokens


def block_summary(block: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "block_id": clean(block.get("block_id")),
        "block_type": clean(block.get("block_type")),
        "text": clean(block.get("text")),
        "bbox": parse_bbox(block.get("bbox")),
        "reading_order": int_or_none(block.get("reading_order")),
    }


def normalize_row_label(value: str) -> str:
    text = clean(value)
    if not text:
        return ""
    if PERIOD_RE.match(text):
        return re.sub(r"\.\s+", ". ", text)
    if is_numeric_value(text):
        return ""
    if ROW_LABEL_WITH_DIGIT_RE.match(text):
        return text
    return ""


def is_numeric_value(value: str) -> bool:
    return bool(NUMERIC_RE.match(clean(value)))


def numeric_value(value: str) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    text = text.replace("△", "-").replace("▲", "")
    try:
        return float(text)
    except ValueError:
        return None


def sign_convention(value: str) -> str:
    text = clean(value)
    if text.startswith("△"):
        return "negative_triangle"
    if text.startswith("▲"):
        return "positive_triangle"
    if text.startswith("-"):
        return "negative_minus"
    return "plain"


def table_id_for(page_no: int, table_type: str, source_block_ids: list[str]) -> str:
    digest = hashlib.sha256(f"{page_no}:{table_type}:{','.join(source_block_ids)}".encode("utf-8")).hexdigest()[:12]
    return f"pdf_table_{page_no}_{digest}"


def unique_blocks(tokens: Sequence[Mapping[str, Any]]) -> list[str]:
    return unique_strings(clean(token.get("block_id")) for token in tokens)


def unique_strings(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = clean(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def union_bbox(boxes: list[list[float]]) -> list[float]:
    valid = [box for box in boxes if len(box) == 4]
    if not valid:
        return []
    return [
        round(min(box[0] for box in valid), 2),
        round(min(box[1] for box in valid), 2),
        round(max(box[2] for box in valid), 2),
        round(max(box[3] for box in valid), 2),
    ]


def parse_bbox(value: Any) -> list[float]:
    if isinstance(value, list) and len(value) == 4:
        try:
            return [round(float(item), 2) for item in value]
        except (TypeError, ValueError):
            return []
    return []


def int_or_zero(value: Any) -> int:
    parsed = int_or_none(value)
    return parsed if parsed is not None else 0


def int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def append_trace(
    trace: Any,
    node: str,
    extra: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    item: dict[str, Any] = {"node": node}
    if extra:
        item.update(dict(extra))
    return [*(trace or []), item]


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").strip()
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", clean(value))
