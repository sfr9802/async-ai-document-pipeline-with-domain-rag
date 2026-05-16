"""Deterministic PDF table extraction from native text blocks.

This parser is intentionally narrow and fail-closed. It only emits table
records for layouts whose row arity and column groups are explicit in the text
blocks. OCR fragments and chart-like labels are left out.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any, Mapping


PARSER_VERSION = "pdf-table-deterministic-v1"
NUMERIC_RE = re.compile(r"^[△▲-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?$|^[△▲-]?\d+(?:\.\d+)?%?$")
PERIOD_RE = re.compile(r"^\d{4}(?:\.\s*(?:\d{1,2}|[ⅠⅡⅢⅣIVX]+))?$")


EXPORT_IMPORT_HEADERS = [
    "period",
    "수출(FOB) 금액",
    "수출(FOB) 증가율",
    "수입(CIF) 금액",
    "수입(CIF) 증가율",
    "수출입차 금액",
]

CURRENCY_HEADERS = [
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
    for index, block in enumerate(native_blocks):
        window = native_blocks[index : index + 16]
        block_text = normalize(clean(block.get("text")))
        parsed: dict[str, Any] | None = None
        if export_import_like(block_text):
            parsed = parse_fixed_arity_table(
                window,
                table_type="export_import",
                headers=EXPORT_IMPORT_HEADERS,
                value_count=5,
                title_block=block,
            )
        elif currency_like(block_text):
            parsed = parse_fixed_arity_table(
                window,
                table_type="currency_comparison",
                headers=CURRENCY_HEADERS,
                value_count=9,
                title_block=block,
            )
        if not parsed or not parsed["row_records"]:
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
                "confidence": "HIGH",
                "ocr_used": False,
                "table_semantics_success_claimed": True,
            }
        )
        records.append(parsed)
    return records


def parse_fixed_arity_table(
    blocks: list[Mapping[str, Any]],
    *,
    table_type: str,
    headers: list[str],
    value_count: int,
    title_block: Mapping[str, Any],
) -> dict[str, Any]:
    tokens = tokenized_lines(blocks)
    rows: list[dict[str, Any]] = []
    index = 0
    total_tokens_by_block = Counter(token["block_id"] for token in tokens)
    while index < len(tokens):
        period = normalize_period(tokens[index]["text"])
        if period and index + value_count < len(tokens):
            value_tokens = tokens[index + 1 : index + 1 + value_count]
            if all(is_numeric_value(token["text"]) for token in value_tokens):
                row_tokens = [tokens[index], *value_tokens]
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
                for column_index, header in enumerate(headers[1:]):
                    value = value_tokens[column_index]["text"]
                    cells.append(
                        {
                            "column_path": header,
                            "value_raw": value,
                            "value_number": numeric_value(value),
                            "unit": "",
                            "sign_convention": sign_convention(value),
                            "cell_bbox": None,
                            "bbox_granularity": bbox_granularity,
                            "source_block_id": value_tokens[column_index]["block_id"],
                        }
                    )
                rows.append(
                    {
                        "row_index": len(rows),
                        "row_label_raw": period,
                        "row_label_normalized": period,
                        "row_bbox": row_bbox,
                        "bbox_granularity": bbox_granularity,
                        "source_block_ids": source_blocks,
                        "cells": cells,
                    }
                )
                index += value_count + 1
                continue
        index += 1
    source_block_ids = unique_blocks(token for row in rows for token in row_tokens_for_source(row, tokens))
    if not source_block_ids:
        source_block_ids = [clean(title_block.get("block_id"))]
    table_blocks = [block for block in blocks if clean(block.get("block_id")) in set(source_block_ids) or block is title_block]
    header_blocks = [
        block_summary(block)
        for block in blocks
        if clean(block.get("block_id")) not in set(source_block_ids)
        and clean(block.get("block_id")) != clean(title_block.get("block_id"))
        and clean(block.get("text"))
    ][:4]
    return {
        "table_type": table_type,
        "title_block_id": clean(title_block.get("block_id")),
        "title_text": clean(title_block.get("text")),
        "headers": headers if rows else [],
        "header_blocks": header_blocks,
        "source_block_ids": unique_strings([clean(title_block.get("block_id")), *source_block_ids]),
        "table_bbox": union_bbox([parse_bbox(block.get("bbox")) for block in table_blocks]),
        "bbox_granularity": "row_only" if all(row["bbox_granularity"] == "row_only" for row in rows) else "table_only",
        "row_records": rows,
    }


def row_tokens_for_source(row: Mapping[str, Any], tokens: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    source_ids = set(row.get("source_block_ids") or [])
    return [token for token in tokens if token.get("block_id") in source_ids]


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


def export_import_like(text: str) -> bool:
    return "수출" in text and "수입" in text and "수출입차" in text


def currency_like(text: str) -> bool:
    return "주요국가의환율변동비교" in text or ("한국" in text and "유로" in text and "절상률" in text)


def normalize_period(value: str) -> str:
    text = clean(value)
    if PERIOD_RE.match(text):
        return re.sub(r"\.\s+", ". ", text)
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


def unique_blocks(tokens: list[Mapping[str, Any]]) -> list[str]:
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


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").strip()
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", clean(value))
