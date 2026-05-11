"""PDF OCR/MM layout context assembly for RAG orchestrator Evidence."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from app.capabilities.rag_orchestrator.evidence import (
    SOURCE_FILE_TYPE_PDF,
    Evidence,
)

PDF_CONTEXT_CONTRACT_VERSION = "pdf-business-ocr-mm-context-v1"
PDF_CONTEXT_DIAGNOSTIC_WARNING = "pdf_context_diagnostic_only_missing_layout"
PDF_CONTEXT_ASSEMBLY_POLICY = (
    "matched_block",
    "page_number",
    "bbox",
    "section_heading",
    "table_caption_footnote",
    "nearby_paragraph",
    "ocr_confidence_if_available",
)


@dataclass(frozen=True)
class PdfEvidenceContext:
    """Layout-aware answer context assembled from one PDF candidate."""

    file: str
    page: int | str | None
    region_type: str | None
    bbox: tuple[float, ...]
    matched_text: str
    section_heading: str | None
    table_caption_footnote: str | None
    nearby_paragraphs: tuple[str, ...]
    ocr_confidence: float | None
    score: float | None
    diagnostic_only: bool
    missing_context_fields: tuple[str, ...]
    context_assembly_policy: tuple[str, ...] = PDF_CONTEXT_ASSEMBLY_POLICY
    contract_version: str = PDF_CONTEXT_CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "file": self.file,
            "page": self.page,
            "region_type": self.region_type,
            "bbox": list(self.bbox),
            "matched_text": self.matched_text,
            "section_heading": self.section_heading,
            "table_caption_footnote": self.table_caption_footnote,
            "nearby_paragraphs": list(self.nearby_paragraphs),
            "OCR_confidence": self.ocr_confidence,
            "score": self.score,
            "diagnostic_only": self.diagnostic_only,
            "missing_context_fields": list(self.missing_context_fields),
            "context_assembly_policy": list(self.context_assembly_policy),
        }


def assemble_pdf_evidence_context(evidence: Evidence) -> PdfEvidenceContext:
    """Assemble OCR/MM layout context from a retrieved PDF candidate."""

    if evidence.source_file_type != SOURCE_FILE_TYPE_PDF:
        raise ValueError("assemble_pdf_evidence_context requires PDF evidence")

    location = dict(evidence.location_json) if isinstance(evidence.location_json, Mapping) else {}
    metadata = _evidence_metadata(evidence)
    page = _first_present(
        location,
        metadata,
        "page_no",
        "pageNo",
        "page",
        "page_label",
        "pageLabel",
        "physical_page_index",
        "physicalPageIndex",
    )
    bbox = _bbox_tuple(
        _first_present(location, metadata, "bbox", "boundingBox", "bounding_box")
    )
    region_type = _str_or_none(
        _first_present(
            location,
            metadata,
            "regionType",
            "region_type",
            "blockType",
            "block_type",
            "chunkType",
            "chunk_type",
        )
    )
    section_heading = _str_or_none(
        _first_present(
            location,
            metadata,
            "sectionHeading",
            "section_heading",
            "sectionPath",
            "section_path",
        )
    )
    table_caption_footnote = _str_or_none(
        _first_present(
            location,
            metadata,
            "tableCaptionFootnote",
            "table_caption_footnote",
            "caption",
            "tableCaption",
            "footnote",
        )
    )
    nearby_paragraphs = _tuple_strings(
        _first_present(
            location,
            metadata,
            "nearbyParagraphs",
            "nearby_paragraphs",
            "nearby_paragraph",
        )
    )
    ocr_confidence = _float_or_none(
        _first_present(
            location,
            metadata,
            "OCR_confidence",
            "ocr_confidence",
            "ocrConfidence",
        )
    )

    missing = []
    if page in (None, ""):
        missing.append("page")
    if not region_type:
        missing.append("region_type")
    if not bbox:
        missing.append("bbox")
    if not section_heading:
        missing.append("section_heading")
    if not nearby_paragraphs:
        missing.append("nearby_paragraphs")
    diagnostic_only = bool(missing)

    return PdfEvidenceContext(
        file=evidence.source_file_name or evidence.source_file_id,
        page=page,
        region_type=region_type,
        bbox=bbox,
        matched_text=evidence.text,
        section_heading=section_heading,
        table_caption_footnote=table_caption_footnote,
        nearby_paragraphs=nearby_paragraphs,
        ocr_confidence=ocr_confidence,
        score=_score(evidence),
        diagnostic_only=diagnostic_only,
        missing_context_fields=tuple(missing),
    )


def evidence_with_pdf_context(evidence: Evidence) -> Evidence:
    """Attach PDF layout context assembly output to an Evidence item."""

    context = assemble_pdf_evidence_context(evidence)
    warnings = tuple(evidence.verification_warnings)
    if context.diagnostic_only and PDF_CONTEXT_DIAGNOSTIC_WARNING not in warnings:
        warnings = (*warnings, PDF_CONTEXT_DIAGNOSTIC_WARNING)
    extra = dict(evidence.extra)
    extra["track_evidence_contract"] = PDF_CONTEXT_CONTRACT_VERSION
    extra["pdf_evidence_context"] = context.to_dict()
    return replace(
        evidence,
        diagnostic_only=evidence.diagnostic_only or context.diagnostic_only,
        verification_warnings=warnings,
        extra=extra,
    )


def _evidence_metadata(evidence: Evidence) -> dict[str, Any]:
    metadata = dict(evidence.extra.get("retriever_metadata") or {})
    metadata.update(
        {
            key: value
            for key, value in evidence.extra.items()
            if key not in {"retriever_metadata", "pdf_evidence_context"}
        }
    )
    return metadata


def _first_present(
    primary: Mapping[str, Any],
    secondary: Mapping[str, Any],
    *keys: str,
) -> Any:
    for source in (primary, secondary):
        for key in keys:
            value = source.get(key)
            if value not in (None, ""):
                return value
    return None


def _tuple_strings(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, Mapping):
        return tuple(str(item).strip() for item in value.values() if str(item).strip())
    if isinstance(value, Iterable):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value).strip(),) if str(value).strip() else ()


def _bbox_tuple(value: Any) -> tuple[float, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        parts = [part.strip() for part in value.replace("[", "").replace("]", "").split(",")]
    elif isinstance(value, Iterable):
        parts = list(value)
    else:
        return ()
    output: list[float] = []
    for part in parts[:4]:
        parsed = _float_or_none(part)
        if parsed is None:
            return ()
        output.append(parsed)
    return tuple(output) if len(output) == 4 else ()


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score(evidence: Evidence) -> float | None:
    for key in ("final", "rerank", "dense"):
        value = evidence.scores.get(key) if evidence.scores else None
        if isinstance(value, (int, float)):
            return float(value)
    return None
