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
    search_view_id = _meta(metadata, "search_view_id", "searchViewId")
    source_atom_id = _meta(metadata, "source_atom_id", "sourceAtomId")
    source_atom_ids = _meta(metadata, "source_atom_ids", "sourceAtomIds")
    source_atom_hydrated = bool(
        _meta(metadata, "source_atom_hydrated_from_registry", "sourceAtomHydratedFromRegistry")
    )
    search_view_candidate = bool(search_view_id or source_atom_id or source_atom_ids)
    canonical_metadata_allowed = not search_view_candidate or source_atom_hydrated
    metadata_source_identity = _meta(metadata, "source_identity", "sourceIdentity")
    metadata_locator_fingerprint = _meta(metadata, "locator_fingerprint", "locatorFingerprint")
    metadata_canonical_payload = _meta(metadata, "canonical_citation_payload", "canonicalCitationPayload")
    metadata_canonical_payload_source = _meta(metadata, "canonical_payload_source", "canonicalPayloadSource")
    canonical_payload_source = (
        metadata_canonical_payload_source
        if canonical_metadata_allowed
        else "source_registry_hydration_required"
    )
    return {
        "track": _meta(metadata, "track", "manifest_track"),
        "manifest_track": _meta(metadata, "manifest_track", "track"),
        "source_family": _meta(metadata, "source_family", "sourceFamily"),
        "sourceFamily": _meta(metadata, "sourceFamily", "source_family"),
        "locator_schema": _meta(metadata, "locator_schema", "locatorSchema"),
        "locatorSchema": _meta(metadata, "locatorSchema", "locator_schema"),
        "manifest_query_id": _meta(metadata, "manifest_query_id", "manifestQueryId"),
        "manifestQueryId": _meta(metadata, "manifestQueryId", "manifest_query_id"),
        "source_identity": metadata_source_identity if canonical_metadata_allowed else None,
        "sourceIdentity": metadata_source_identity if canonical_metadata_allowed else None,
        "candidate_source_identity": metadata_source_identity if search_view_candidate else None,
        "candidateSourceIdentity": metadata_source_identity if search_view_candidate else None,
        "locator_fingerprint": metadata_locator_fingerprint if canonical_metadata_allowed else None,
        "locatorFingerprint": metadata_locator_fingerprint if canonical_metadata_allowed else None,
        "candidate_locator_fingerprint": metadata_locator_fingerprint if search_view_candidate else None,
        "candidateLocatorFingerprint": metadata_locator_fingerprint if search_view_candidate else None,
        "canonical_payload_status": _meta(metadata, "canonical_payload_status", "canonicalPayloadStatus"),
        "canonicalPayloadStatus": _meta(metadata, "canonicalPayloadStatus", "canonical_payload_status"),
        "canonical_citation_payload": metadata_canonical_payload if canonical_metadata_allowed else None,
        "canonicalCitationPayload": metadata_canonical_payload if canonical_metadata_allowed else None,
        "candidate_canonical_citation_payload": (
            metadata_canonical_payload if search_view_candidate and not canonical_metadata_allowed else None
        ),
        "candidateCanonicalCitationPayload": (
            metadata_canonical_payload if search_view_candidate and not canonical_metadata_allowed else None
        ),
        "track_locator_payload": _meta(metadata, "track_locator_payload", "trackLocatorPayload"),
        "trackLocatorPayload": _meta(metadata, "trackLocatorPayload", "track_locator_payload"),
        "canonical_payload_renderable": _meta(metadata, "canonical_payload_renderable", "canonicalPayloadRenderable"),
        "canonicalPayloadRenderable": _meta(metadata, "canonicalPayloadRenderable", "canonical_payload_renderable"),
        "canonical_payload_source": canonical_payload_source,
        "canonicalPayloadSource": canonical_payload_source,
        "source_registry_hydration_required": bool(search_view_candidate and not source_atom_hydrated),
        "sourceRegistryHydrationRequired": bool(search_view_candidate and not source_atom_hydrated),
        "vector_payload_used_as_evidence_truth": False if search_view_candidate else None,
        "vectorPayloadUsedAsEvidenceTruth": False if search_view_candidate else None,
        "search_view_id": search_view_id,
        "searchViewId": search_view_id,
        "search_view_kind": _meta(metadata, "search_view_kind", "searchViewKind"),
        "searchViewKind": _meta(metadata, "searchViewKind", "search_view_kind"),
        "source_atom_id": source_atom_id,
        "sourceAtomId": source_atom_id,
        "source_atom_ids": source_atom_ids,
        "sourceAtomIds": source_atom_ids,
        "source_atom_hydrated_from_registry": source_atom_hydrated,
        "sourceAtomHydratedFromRegistry": source_atom_hydrated,
        "source_registry_version": _meta(metadata, "source_registry_version", "sourceRegistryVersion"),
        "sourceRegistryVersion": _meta(metadata, "sourceRegistryVersion", "source_registry_version"),
        "generation_source_allowed": _meta(metadata, "generation_source_allowed", "generationSourceAllowed"),
        "generationSourceAllowed": _meta(metadata, "generationSourceAllowed", "generation_source_allowed"),
        "official_denominator_overlap": _meta(metadata, "official_denominator_overlap", "officialDenominatorOverlap"),
        "officialDenominatorOverlap": _meta(metadata, "officialDenominatorOverlap", "official_denominator_overlap"),
        "silver_source_overlap": _meta(metadata, "silver_source_overlap", "silverSourceOverlap"),
        "silverSourceOverlap": _meta(metadata, "silverSourceOverlap", "silver_source_overlap"),
        "review_only": _meta(metadata, "review_only", "reviewOnly"),
        "reviewOnly": _meta(metadata, "reviewOnly", "review_only"),
        "quarantine": _meta(metadata, "quarantine"),
        "not_official_denominator": _meta(metadata, "not_official_denominator", "notOfficialDenominator"),
        "notOfficialDenominator": _meta(metadata, "notOfficialDenominator", "not_official_denominator"),
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
