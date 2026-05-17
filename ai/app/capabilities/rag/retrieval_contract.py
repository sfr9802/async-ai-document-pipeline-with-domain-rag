"""SearchUnit-aware retrieval result and citation contract helpers."""

from __future__ import annotations

from typing import Any

from app.capabilities.rag.generation import RetrievedChunk


def retrieval_result_row(rank: int, chunk: RetrievedChunk) -> dict[str, Any]:
    return {
        "rank": rank,
        "chunkId": chunk.chunk_id,
        "docId": chunk.doc_id,
        "section": chunk.section,
        "score": round(chunk.score, 6),
        "text": chunk.text,
        "searchUnitId": chunk.search_unit_id,
        "sourceFileId": chunk.source_file_id,
        "sourceFileName": chunk.source_file_name,
        "extractedArtifactId": chunk.extracted_artifact_id,
        "artifactType": chunk.artifact_type,
        "unitType": chunk.unit_type or "CHUNK",
        "unitKey": chunk.unit_key,
        "title": chunk.title,
        "sectionPath": chunk.section_path,
        "pageStart": chunk.page_start,
        "pageEnd": chunk.page_end,
        "snippet": preview(chunk.text),
        "textPreview": preview(chunk.text),
        "denseScore": (
            round(chunk.dense_score, 6)
            if chunk.dense_score is not None
            else round(chunk.score, 6)
        ),
        "sparseScore": (
            round(chunk.sparse_score, 6) if chunk.sparse_score is not None else None
        ),
        "rerankScore": (
            round(chunk.rerank_score, 6) if chunk.rerank_score is not None else None
        ),
        "metadataJson": chunk.metadata_json,
        "citation": citation_payload(chunk),
        "grounding": grounding_readiness(chunk, selected_for_context=True),
    }


def citation_payload(chunk: RetrievedChunk) -> dict[str, Any]:
    metadata = chunk.metadata_json or {}
    search_unit_id = chunk.search_unit_id
    unit_type = chunk.unit_type or "CHUNK"
    table_id = metadata.get("tableId") or metadata.get("tableName") or _id_from_unit_key(chunk.unit_key, "table")
    source_file_id = chunk.source_file_id or _meta(metadata, "sourceFileId", "source_file_id")
    return {
        "track": _meta(metadata, "track", "manifest_track"),
        "manifest_track": _meta(metadata, "manifest_track", "track"),
        "source_family": _meta(metadata, "source_family", "sourceFamily"),
        "sourceFamily": _meta(metadata, "sourceFamily", "source_family"),
        "locator_schema": _meta(metadata, "locator_schema", "locatorSchema"),
        "locatorSchema": _meta(metadata, "locatorSchema", "locator_schema"),
        "manifest_query_id": _meta(metadata, "manifest_query_id", "manifestQueryId"),
        "manifestQueryId": _meta(metadata, "manifestQueryId", "manifest_query_id"),
        "sourceFileId": source_file_id,
        "source_file_id": source_file_id,
        "diagnosticDocId": chunk.doc_id,
        "diagnostic_doc_id": chunk.doc_id,
        "sourceFileName": chunk.source_file_name,
        "source_file_name": chunk.source_file_name,
        "searchUnitId": search_unit_id,
        "search_unit_id": search_unit_id,
        "unitId": search_unit_id,
        "unitType": unit_type,
        "unit_type": unit_type,
        "unitKey": chunk.unit_key,
        "unit_key": chunk.unit_key,
        "title": chunk.title,
        "pageStart": chunk.page_start,
        "page_start": chunk.page_start,
        "pageEnd": chunk.page_end,
        "page_end": chunk.page_end,
        "sectionPath": chunk.section_path or chunk.section,
        "section_path": chunk.section_path or chunk.section,
        "document_id": _meta(metadata, "document_id", "documentId", "doc_id"),
        "documentId": _meta(metadata, "documentId", "document_id", "doc_id"),
        "documentVersionId": _meta(metadata, "documentVersionId", "document_version_id"),
        "document_version_id": _meta(metadata, "document_version_id", "documentVersionId"),
        "text_locator": _meta(metadata, "text_locator", "textLocator"),
        "textLocator": _meta(metadata, "textLocator", "text_locator"),
        "workbook": _meta(metadata, "workbook", "source_workbook", "sourceWorkbook", "file") or chunk.source_file_name,
        "sheetName": _meta(metadata, "sheetName", "sheet_name", "sheet"),
        "sheet_name": _meta(metadata, "sheet_name", "sheetName", "sheet"),
        "sheet": _meta(metadata, "sheet", "sheetName", "sheet_name"),
        "sheetIndex": _meta(metadata, "sheetIndex", "sheet_index"),
        "sheet_index": _meta(metadata, "sheet_index", "sheetIndex"),
        "cellRange": _meta(metadata, "cellRange", "range", "usedRange", "cell_range"),
        "cell_range": _meta(metadata, "cell_range", "cellRange", "range", "usedRange"),
        "range": _meta(metadata, "range", "cellRange", "cell_range", "usedRange"),
        "cell": _meta(metadata, "cell", "matchedCell", "matched_cell"),
        "rowStart": _meta(metadata, "rowStart", "row_start"),
        "row_start": _meta(metadata, "row_start", "rowStart"),
        "rowEnd": _meta(metadata, "rowEnd", "row_end"),
        "row_end": _meta(metadata, "row_end", "rowEnd"),
        "columnStart": _meta(metadata, "columnStart", "column_start"),
        "column_start": _meta(metadata, "column_start", "columnStart"),
        "columnEnd": _meta(metadata, "columnEnd", "column_end"),
        "column_end": _meta(metadata, "column_end", "columnEnd"),
        "row_label": _meta(metadata, "row_label", "rowLabel", "row_label_normalized", "row_label_raw"),
        "rowLabel": _meta(metadata, "rowLabel", "row_label", "row_label_normalized", "row_label_raw"),
        "target_column": _meta(metadata, "target_column", "targetColumn"),
        "targetColumn": _meta(metadata, "targetColumn", "target_column"),
        "normalized_value": _meta(metadata, "normalized_value", "normalizedValue"),
        "normalizedValue": _meta(metadata, "normalizedValue", "normalized_value"),
        "source_pdf_path": _meta(metadata, "source_pdf_path", "sourcePdfPath"),
        "sourcePdfPath": _meta(metadata, "sourcePdfPath", "source_pdf_path"),
        "page": _meta(metadata, "page", "page_no", "pageNo") or chunk.page_start,
        "physical_page_index": _meta(metadata, "physical_page_index", "physicalPageIndex"),
        "physicalPageIndex": _meta(metadata, "physicalPageIndex", "physical_page_index"),
        "region_type": _meta(metadata, "region_type", "regionType"),
        "regionType": _meta(metadata, "regionType", "region_type"),
        "tableId": table_id,
        "table_id": table_id,
        "imageId": _id_from_unit_key(chunk.unit_key, "image"),
        "bbox": _meta(metadata, "bbox", "boundingBox"),
        "artifactId": chunk.extracted_artifact_id,
        "artifact_id": chunk.extracted_artifact_id,
        "artifactType": chunk.artifact_type,
        "artifact_type": chunk.artifact_type,
        "source_bound_official_denominator": _meta(
            metadata,
            "source_bound_official_denominator",
            "sourceBoundOfficialDenominator",
        ),
    }


def grounding_readiness(
    chunk: RetrievedChunk,
    *,
    selected_for_context: bool,
) -> dict[str, Any]:
    citation = citation_payload(chunk)
    has_page_range = chunk.page_start is not None and chunk.page_end is not None
    return {
        "hasCitation": citation is not None,
        "hasSearchUnitId": bool(chunk.search_unit_id),
        "hasSourceFileId": bool(chunk.source_file_id),
        "hasDiagnosticDocId": bool(chunk.doc_id),
        "hasPageRange": has_page_range,
        "hasTextPreview": bool(preview(chunk.text)),
        "selectedForContext": bool(selected_for_context),
    }


def preview(text: str, *, max_chars: int = 240) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3] + "..."


def _id_from_unit_key(unit_key: str | None, kind: str) -> str | None:
    if not unit_key:
        return None
    prefix = f"{kind}:"
    if unit_key.startswith(prefix):
        return unit_key[len(prefix):] or None
    infix = f":{kind}:"
    index = unit_key.find(infix)
    if index < 0:
        return None
    return unit_key[index + len(infix):] or None


def _meta(metadata: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = metadata.get(key)
        if value not in (None, ""):
            return value
    return None
