"""Claude-backed grounded generation provider.

Replaces the extractive heuristic with actual LLM-generated answers
that cite retrieved passages. The extractive generator stays as the
CI / offline / test fallback and as the automatic fallback when the
Claude API is unreachable (controlled by fallback_on_error).

Activation:

    AIPIPELINE_WORKER_RAG_GENERATOR=claude
    AIPIPELINE_WORKER_ANTHROPIC_API_KEY=sk-ant-...

Output format: identical 3-part markdown structure to ExtractiveGenerator
(Short answer / Supporting passages / Sources) so downstream
FINAL_RESPONSE consumers need zero changes.
"""

from __future__ import annotations

import logging
import time
from typing import Any, List, Mapping, Sequence

from app.capabilities.rag.generation import (
    ExtractiveGenerator,
    GenerationProvider,
    RetrievedChunk,
)
from app.capabilities.rag.retrieval_contract import citation_payload

log = logging.getLogger(__name__)


class GenerationError(Exception):
    """Typed generation failure — separates Claude API errors from general
    exceptions so the fallback policy can distinguish retryable failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_SYSTEM_PROMPT = (
    "You are a retrieval-augmented answer generator.\n"
    "Answer ONLY from the supplied passages and structured locators. Cite "
    "every factual claim with the supplied Citation ID, such as `[S1]`, and "
    "keep the original source ref `[doc_id#section]` when it helps audit the "
    "answer.\n"
    "Answer in the query language; for Korean or fragment-like Korean queries, "
    "answer in Korean.\n"
    "For PDF evidence, use page, bbox, region, and source_pdf_path only when "
    "they are supplied. For XLSX evidence, use workbook, sheet, range, cell, "
    "row_label, target_column, and normalized_value only when they are "
    "supplied.\n"
    "When citing long file paths, keep the answer compact: cite page/bbox or "
    "sheet/cell/range first, and use a path suffix instead of copying a full "
    "absolute path.\n"
    "If the passages don't contain the answer, respond exactly:\n"
    "Korean query: '제공된 자료에서 답을 찾을 수 없습니다.'\n"
    "English query: 'The provided sources do not contain an answer.'\n"
    "Never use outside knowledge. Never hallucinate document IDs, pages, "
    "sheets, cells, values, or citation IDs.\n\n"
    "Format your answer in three sections:\n"
    "1. **Short answer:** — a concise 1-3 sentence answer\n"
    "2. **Supporting passages:** — numbered list citing each passage and "
    "locator used\n"
    "3. **Sources:** — comma-separated list of unique doc_ids"
)


class ClaudeGenerationProvider(GenerationProvider):
    """Claude LLM-backed generation with extractive fallback.

    Dependencies: `anthropic` SDK (pip install anthropic>=0.40.0).
    Requires AIPIPELINE_WORKER_ANTHROPIC_API_KEY at runtime.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        timeout_seconds: float = 60.0,
        fallback_on_error: bool = True,
    ) -> None:
        import anthropic  # local import — registry catches ImportError

        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=timeout_seconds,
        )
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._fallback_on_error = fallback_on_error
        self._extractive_fallback = ExtractiveGenerator()

    @property
    def name(self) -> str:
        return "claude-generation-v1"

    def generate(self, query: str, chunks: List[RetrievedChunk]) -> str:
        if not chunks:
            return (
                "No relevant passages were retrieved for your query.\n\n"
                f"> {query}"
            )

        try:
            return self._call_claude(query, chunks)
        except Exception as ex:
            if self._fallback_on_error:
                log.warning(
                    "ClaudeGenerationProvider failed, falling back to "
                    "extractive: %s: %s",
                    type(ex).__name__, ex,
                )
                return self._extractive_fallback.generate(query, chunks)
            # Re-raise as a CapabilityError-compatible exception.
            from app.capabilities.base import CapabilityError

            raise CapabilityError(
                "GENERATION_API_FAILED",
                f"Claude generation failed and fallback is disabled: "
                f"{type(ex).__name__}: {ex}",
            ) from ex

    def _call_claude(self, query: str, chunks: List[RetrievedChunk]) -> str:
        import anthropic

        user_message = _build_user_message(query, chunks)
        started_at = time.perf_counter()

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                temperature=0,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APITimeoutError as ex:
            raise GenerationError(
                "GENERATION_TIMEOUT",
                f"Claude generation timed out after {self._timeout_seconds}s: {ex}",
            ) from ex
        except anthropic.RateLimitError as ex:
            raise GenerationError(
                "GENERATION_RATE_LIMIT",
                f"Claude generation rate-limited: {ex}",
            ) from ex
        except anthropic.APIStatusError as ex:
            raise GenerationError(
                "GENERATION_API_ERROR",
                f"Claude generation API error {ex.status_code}: {ex}",
            ) from ex

        elapsed_ms = (time.perf_counter() - started_at) * 1000.0

        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text += block.text

        if not raw_text.strip():
            raise GenerationError(
                "GENERATION_EMPTY_RESPONSE",
                "Claude generation returned an empty response.",
            )

        log.info(
            "ClaudeGenerationProvider generated answer: model=%s "
            "latency_ms=%.2f answer_len=%d chunk_count=%d",
            self._model, elapsed_ms, len(raw_text), len(chunks),
        )

        return raw_text.strip()


def _build_user_message(query: str, chunks: List[RetrievedChunk]) -> str:
    """Build the user message with query, locator context, and passages."""
    lines = [f"질문: {query}", "", "관련 자료:"]
    for i, chunk in enumerate(chunks, start=1):
        lines.extend(_chunk_context_lines(i, chunk))
        lines.append("")
    return "\n".join(lines)


def _chunk_context_lines(index: int, chunk: RetrievedChunk) -> list[str]:
    citation = citation_payload(chunk)
    metadata = _as_mapping(chunk.metadata_json)
    canonical = _as_mapping(
        citation.get("canonical_citation_payload")
        or citation.get("canonicalCitationPayload")
    )
    track_locator = _as_mapping(
        citation.get("track_locator_payload")
        or citation.get("trackLocatorPayload")
    )
    source_registry_hydration_required = bool(
        citation.get("source_registry_hydration_required")
        or citation.get("sourceRegistryHydrationRequired")
    )
    payloads: Sequence[Mapping[str, Any]] = (
        track_locator,
        canonical,
        citation,
        metadata,
    )
    locator_payloads: Sequence[Mapping[str, Any]] = (
        ()
        if source_registry_hydration_required
        else (
            track_locator,
            canonical,
            citation,
            metadata,
        )
    )
    source_family = _clean(
        _first_value(payloads, "source_family", "sourceFamily")
        or chunk.artifact_type
        or ""
    ).upper()
    lines = [
        f"Citation ID: [S{index}]",
        f"Original ref: [{chunk.doc_id}#{chunk.section}] (score={chunk.score:.3f})",
    ]

    ids = _format_pairs(
        "Evidence IDs:",
        (
            ("search_unit_id", _first_value(payloads, "search_unit_id", "searchUnitId")),
            ("source_atom_id", _first_value(payloads, "source_atom_id", "sourceAtomId")),
            (
                "document_version_id",
                _first_value(payloads, "document_version_id", "documentVersionId"),
            ),
            ("source_family", source_family),
        ),
    )
    if ids:
        lines.append(ids)

    pdf_locator = _format_pairs(
        "PDF locator:",
        (
            ("source_pdf_path", _first_value(locator_payloads, "source_pdf_path", "sourcePdfPath")),
            (
                "page",
                _first_value(locator_payloads, "page", "pageStart", "page_start")
                or (chunk.page_start if not source_registry_hydration_required else None),
            ),
            (
                "page_end",
                _first_value(locator_payloads, "pageEnd", "page_end")
                or (chunk.page_end if not source_registry_hydration_required else None),
            ),
            (
                "physical_page_index",
                _first_value(locator_payloads, "physical_page_index", "physicalPageIndex"),
            ),
            ("bbox", _first_value(locator_payloads, "bbox", "boundingBox")),
            ("region_type", _first_value(locator_payloads, "region_type", "regionType")),
            ("row_label", _first_value(locator_payloads, "row_label", "rowLabel")),
            ("target_column", _first_value(locator_payloads, "target_column", "targetColumn")),
        ),
    )
    if pdf_locator and (source_family == "PDF" or _contains_any(pdf_locator, ("page=", "bbox=", "source_pdf_path="))):
        lines.append(pdf_locator)

    xlsx_locator = _format_pairs(
        "XLSX locator:",
        (
            ("workbook", _first_value(locator_payloads, "workbook")),
            ("sheet", _first_value(locator_payloads, "sheet", "sheetName", "sheet_name")),
            ("range", _first_value(locator_payloads, "range", "cellRange", "cell_range")),
            ("cell", _first_value(locator_payloads, "cell", "matchedCell", "matched_cell")),
            ("row_label", _first_value(locator_payloads, "row_label", "rowLabel")),
            ("column_label", _first_value(locator_payloads, "column_label", "columnLabel")),
            ("target_column", _first_value(locator_payloads, "target_column", "targetColumn")),
            ("normalized_value", _first_value(locator_payloads, "normalized_value", "normalizedValue")),
        ),
    )
    if xlsx_locator and (
        source_family == "XLSX"
        or _contains_any(xlsx_locator, ("workbook=", "sheet=", "cell=", "range="))
    ):
        lines.append(xlsx_locator)

    title = _clean(chunk.title)
    if title:
        lines.append(f"Title: {title}")
    section_path = _clean(chunk.section_path)
    if section_path and section_path != _clean(chunk.section):
        lines.append(f"Section path: {section_path}")
    lines.append("Passage:")
    lines.append(_truncate_passage(chunk.text))
    return lines


def _format_pairs(label: str, pairs: Sequence[tuple[str, Any]]) -> str:
    formatted: list[str] = []
    for key, value in pairs:
        clean_value = _format_value(key, value)
        if clean_value:
            formatted.append(f"{key}={clean_value}")
    if not formatted:
        return ""
    return f"{label} " + " | ".join(formatted)


def _first_value(payloads: Sequence[Mapping[str, Any]], *keys: str) -> Any:
    for payload in payloads:
        for key in keys:
            value = payload.get(key)
            if value not in (None, "", [], {}):
                return value
    return None


def _format_value(key: str, value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, (list, tuple, dict)):
        return json_dumps(value)
    text = _clean(value)
    if key in {"source_pdf_path", "source_path"} and len(text) > 120:
        normalized = text.replace("\\", "/")
        return ".../" + normalized.rsplit("/", 1)[-1]
    return text


def json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _truncate_passage(text: str, *, max_chars: int = 1800) -> str:
    normalized = _clean(text)
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _contains_any(value: str, needles: Sequence[str]) -> bool:
    return any(needle in value for needle in needles)
