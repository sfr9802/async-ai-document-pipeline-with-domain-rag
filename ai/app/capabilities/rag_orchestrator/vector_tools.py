"""POC vector retriever wrappers for the query-time RAG orchestrator.

These tools adapt the existing ``Retriever.retrieve(query, filters=None)``
boundary into the shared Evidence contract. They are intentionally not a
production-grade filter-enforcement claim: the current retriever filter surface
may not enforce source type, parser version, index version, ACL, or tenant
constraints before FAISS ranking. This POC starts with bounded overfetch,
post-filtering, and the deterministic citation verifier.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from typing import Any, Iterable, Mapping, Protocol

from app.capabilities.rag_orchestrator.citation_verify import (
    FATAL_SOURCE_TYPE,
    citation_verify_tool,
)
from app.capabilities.rag_orchestrator.evidence import (
    RETRIEVAL_BACKEND_VECTOR,
    SOURCE_FILE_TYPE_PDF,
    SOURCE_FILE_TYPE_SPREADSHEET,
    SOURCE_FILE_TYPE_TEXT,
    Evidence,
    QueryPolicy,
)
from app.capabilities.rag_orchestrator.pdf_tools import evidence_with_pdf_context
from app.capabilities.rag_orchestrator.tools import RejectedEvidence, ToolResult
from app.capabilities.rag_orchestrator.xlsx_tools import evidence_with_xlsx_context

TOOL_PDF_VECTOR_SEARCH = "pdf_vector_search_tool"
TOOL_XLSX_VECTOR_SEARCH = "xlsx_vector_search_tool"
TOOL_TEXT_VECTOR_SEARCH = "text_vector_search_tool"

VECTOR_BACKEND_FAISS = "faiss"
DEFAULT_OVERFETCH_FACTOR = 5
TEXT_VECTOR_READINESS_WARNING = "text_vector_contract_not_production_ready"

PRODUCTION_READINESS_TODOS = (
    "Replace the temporary private-attribute overfetch shim with a per-call "
    "safe retrieval API that accepts bounded top_k/candidate_k explicitly.",
    "Enforce tenant, ACL, index_version, source_file_type, parser_version, and "
    "embedding_status before vector ranking, or use a dedicated safe retrieval "
    "API that can prove those filters are fail-closed.",
    "Keep library-search diagnostic-only; do not adapt it into production "
    "Evidence.",
)


class RetrieverLike(Protocol):
    def retrieve(self, query: str, filters: Mapping[str, Any] | None = None) -> Any:
        ...


def pdf_vector_search_tool(
    query: str,
    policy: QueryPolicy,
    *,
    retriever: RetrieverLike,
    overfetch_factor: int = DEFAULT_OVERFETCH_FACTOR,
) -> ToolResult:
    return _vector_search_tool(
        tool=TOOL_PDF_VECTOR_SEARCH,
        query=query,
        policy=policy,
        retriever=retriever,
        target_source_file_type=SOURCE_FILE_TYPE_PDF,
        overfetch_factor=overfetch_factor,
    )


def xlsx_vector_search_tool(
    query: str,
    policy: QueryPolicy,
    *,
    retriever: RetrieverLike,
    overfetch_factor: int = DEFAULT_OVERFETCH_FACTOR,
) -> ToolResult:
    return _vector_search_tool(
        tool=TOOL_XLSX_VECTOR_SEARCH,
        query=query,
        policy=policy,
        retriever=retriever,
        target_source_file_type=SOURCE_FILE_TYPE_SPREADSHEET,
        overfetch_factor=overfetch_factor,
    )


def text_vector_search_tool(
    query: str,
    policy: QueryPolicy,
    *,
    retriever: RetrieverLike,
    overfetch_factor: int = DEFAULT_OVERFETCH_FACTOR,
) -> ToolResult:
    return _vector_search_tool(
        tool=TOOL_TEXT_VECTOR_SEARCH,
        query=query,
        policy=policy,
        retriever=retriever,
        target_source_file_type=SOURCE_FILE_TYPE_TEXT,
        overfetch_factor=overfetch_factor,
    )


def _vector_search_tool(
    *,
    tool: str,
    query: str,
    policy: QueryPolicy,
    retriever: RetrieverLike,
    target_source_file_type: str,
    overfetch_factor: int,
) -> ToolResult:
    overfetch_k = _overfetch_k(policy, overfetch_factor=overfetch_factor)
    with _temporary_overfetch(retriever, overfetch_k=overfetch_k):
        report = retriever.retrieve(query, filters=None)

    candidates = tuple(
        retrieved_chunk_to_evidence(
            chunk,
            report=report,
            rank=rank,
        )
        for rank, chunk in enumerate(_report_results(report), start=1)
    )

    matched_source: list[Evidence] = []
    rejected: list[RejectedEvidence] = []
    for evidence in candidates:
        if evidence.source_file_type != target_source_file_type:
            rejected.append(_rejected_evidence(evidence, (FATAL_SOURCE_TYPE,)))
            continue
        matched_source.append(evidence)

    verification = citation_verify_tool(matched_source, policy)
    verified = tuple(
        _verified_evidence(
            item.evidence,
            item.warnings,
            target_source_file_type=target_source_file_type,
        )
        for item in verification.verified[: policy.top_k]
    )
    rejected.extend(
        _rejected_evidence(item.evidence, item.fatal_reasons, warnings=item.warnings)
        for item in verification.rejected
    )

    return ToolResult(
        tool=tool,
        evidence=verified,
        rejected=tuple(rejected),
        backend_identity={
            "backend": VECTOR_BACKEND_FAISS,
            "retrieval_backend": RETRIEVAL_BACKEND_VECTOR,
            "index_namespace_filter": policy.required_index_version,
            "overfetch_k": overfetch_k,
            "post_filter_applied": True,
            "poc_wrapper": True,
            "production_filter_enforcement": False,
            "library_search_used": False,
            "target_source_file_type": target_source_file_type,
        },
    )


def retrieved_chunk_to_evidence(
    chunk: Any,
    *,
    report: Any,
    rank: int,
) -> Evidence:
    metadata = _metadata_for(chunk)
    safe_metadata, redacted_metadata_fields = _sanitized_retriever_metadata(metadata)
    source_file_type = _source_file_type(chunk, metadata)
    location_json = _location_json(chunk, metadata, source_file_type)
    score = _float_or_none(_get_any(chunk, "score")) or 0.0
    rerank_score = _float_or_none(_get_any(chunk, "rerank_score", "rerankScore"))
    dense_score = _float_or_none(_get_any(chunk, "dense_score", "denseScore"))
    sparse_score = _float_or_none(_get_any(chunk, "sparse_score", "sparseScore"))
    final_score = rerank_score if rerank_score is not None else score
    chunk_id = _string(
        _get_any(chunk, "chunk_id", "chunkId"),
        fallback=f"retrieved-chunk-{rank}",
    )
    search_unit_id = _string(
        _get_any(chunk, "search_unit_id", "searchUnitId")
        or _metadata_any(metadata, "searchUnitId", "search_unit_id"),
        fallback=chunk_id,
    )

    evidence = Evidence(
        evidence_id=f"vector-{chunk_id}",
        retrieval_backend=RETRIEVAL_BACKEND_VECTOR,
        rank=rank,
        scores={
            "dense": dense_score if dense_score is not None else score,
            "sparse": sparse_score,
            "rerank": rerank_score,
            "final": final_score,
        },
        source_file_id=_string(
            _get_any(chunk, "source_file_id", "sourceFileId")
            or _metadata_any(metadata, "sourceFileId", "source_file_id")
            or _get_any(chunk, "doc_id", "docId"),
        ),
        source_file_name=_optional_string(
            _get_any(chunk, "source_file_name", "sourceFileName")
            or _metadata_any(metadata, "sourceFileName", "source_file_name")
        ),
        source_file_type=source_file_type,
        document_id=_optional_string(_get_any(chunk, "doc_id", "docId")),
        document_version_id=_optional_string(
            _metadata_any(metadata, "documentVersionId", "document_version_id")
        ),
        parsed_artifact_id=_optional_string(
            _get_any(chunk, "extracted_artifact_id", "extractedArtifactId")
            or _metadata_any(
                metadata,
                "parsedArtifactId",
                "parsed_artifact_id",
                "artifactId",
            )
        ),
        index_version=_string(
            _metadata_any(metadata, "indexVersion", "index_version")
            or _get_any(report, "index_version", "indexVersion")
        ),
        embedding_status=_string(
            _metadata_any(metadata, "embeddingStatus", "embedding_status")
        ),
        embedding_model=_optional_string(
            _metadata_any(metadata, "embeddingModel", "embedding_model")
            or _get_any(report, "embedding_model", "embeddingModel")
        ),
        embedding_text_sha256=_optional_string(
            _metadata_any(metadata, "embeddingTextSha256", "embedding_text_sha256")
        ),
        vector_id=_optional_string(_metadata_any(metadata, "vectorId", "vector_id")),
        parser_name=_optional_string(
            _metadata_any(metadata, "parserName", "parser_name")
        ),
        parser_version=_string(
            _metadata_any(metadata, "parserVersion", "parser_version")
        ),
        search_unit_id=search_unit_id,
        chunk_id=chunk_id,
        unit_type=_optional_string(
            _get_any(chunk, "unit_type", "unitType")
            or _metadata_any(metadata, "unitType", "unit_type")
        ),
        unit_key=_optional_string(
            _get_any(chunk, "unit_key", "unitKey")
            or _metadata_any(metadata, "unitKey", "unit_key")
        ),
        chunk_type=_optional_string(_metadata_any(metadata, "chunkType", "chunk_type")),
        text=_string(_get_any(chunk, "text"), fallback=""),
        display_text=_optional_string(_metadata_any(metadata, "displayText", "display_text")),
        snippet=_optional_string(_metadata_any(metadata, "snippet")),
        citation_text=_string(
            _metadata_any(metadata, "citationText", "citation_text")
        ),
        location_type=_optional_string(
            _metadata_any(metadata, "locationType", "location_type")
        )
        or _default_location_type(source_file_type),
        location_json=location_json,
        tenant_id=_optional_string(
            _metadata_any(metadata, "tenantId", "tenant_id")
        ),
        acl_tags=_list_strings(_metadata_any(metadata, "aclTags", "acl_tags")),
        hidden_policy_version=_optional_string(
            _metadata_any(metadata, "hiddenPolicyVersion", "hidden_policy_version")
            or _location_value(location_json, "hidden_policy_version")
        ),
        diagnostic_only=_bool_metadata(metadata, "diagnosticOnly", "diagnostic_only"),
        extra={
            "poc_vector_wrapper": True,
            "retriever_metadata": safe_metadata,
            "retriever_metadata_redacted_fields": list(redacted_metadata_fields),
            "vector_payload_candidate_only": True,
            "vector_payload_used_as_evidence_truth": False,
        },
    )
    return _with_track_context(evidence)


def _overfetch_k(policy: QueryPolicy, *, overfetch_factor: int) -> int:
    factor = max(2, int(overfetch_factor))
    return max(policy.top_k + 1, policy.top_k * factor)


@contextmanager
def _temporary_overfetch(retriever: RetrieverLike, *, overfetch_k: int):
    """POC-only shim until Retriever exposes a safe per-call top_k argument."""

    originals: dict[str, Any] = {}
    for attr in ("_top_k", "_candidate_k"):
        if not hasattr(retriever, attr):
            continue
        value = getattr(retriever, attr)
        if not isinstance(value, int):
            continue
        originals[attr] = value
        setattr(retriever, attr, max(value, overfetch_k))
    try:
        yield
    finally:
        for attr, value in originals.items():
            setattr(retriever, attr, value)


def _report_results(report: Any) -> tuple[Any, ...]:
    results = _get_any(report, "results")
    return tuple(results or ())


def _verified_evidence(
    evidence: Evidence,
    warnings: Iterable[str],
    *,
    target_source_file_type: str,
) -> Evidence:
    all_warnings = [*evidence.verification_warnings, *tuple(warnings)]
    if target_source_file_type == SOURCE_FILE_TYPE_TEXT:
        all_warnings.append(TEXT_VECTOR_READINESS_WARNING)
    return replace(
        evidence,
        verification_status="verified",
        verification_reasons=(),
        verification_warnings=_dedupe(all_warnings),
    )


def _with_track_context(evidence: Evidence) -> Evidence:
    if evidence.source_file_type == SOURCE_FILE_TYPE_SPREADSHEET:
        return evidence_with_xlsx_context(evidence)
    if evidence.source_file_type == SOURCE_FILE_TYPE_PDF:
        return evidence_with_pdf_context(evidence)
    return evidence


def _rejected_evidence(
    evidence: Evidence,
    reasons: Iterable[str],
    *,
    warnings: Iterable[str] = (),
) -> RejectedEvidence:
    reason_tuple = tuple(reasons)
    return RejectedEvidence(
        evidence=replace(
            evidence,
            verification_status="rejected",
            verification_reasons=reason_tuple,
            verification_warnings=tuple(warnings),
        ),
        reasons=reason_tuple,
    )


def _metadata_for(chunk: Any) -> dict[str, Any]:
    metadata = _get_any(chunk, "metadata_json", "metadataJson", "metadata")
    if isinstance(metadata, Mapping):
        return dict(metadata)
    return {}


def _sanitized_retriever_metadata(metadata: Mapping[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
    safe: dict[str, Any] = {}
    redacted: list[str] = []
    for key, value in metadata.items():
        key_text = str(key)
        if _is_candidate_payload_metadata_key(key_text):
            redacted.append(key_text)
            continue
        safe[key_text] = value
    return safe, tuple(sorted(redacted))


_PROTECTED_VECTOR_METADATA_KEYS = {
    "canonicalpayload",
    "canonicalcitationpayload",
    "candidatecanonicalcitationpayload",
    "embeddingtext",
    "embeddingtextraw",
    "expectedanswer",
    "expectedanswerpayload",
    "expectedanswertext",
    "fullprompt",
    "goldanswer",
    "goldlabel",
    "goldlocator",
    "hiddentargetlocator",
    "llmresponse",
    "modelresponse",
    "oraclepayload",
    "prompt",
    "promptmanifest",
    "promptpayload",
    "prompttext",
    "qrels",
    "qrelslabel",
    "rawllmpayload",
    "rawllmrequest",
    "rawllmresponse",
    "rawprompt",
    "rawresponse",
    "rawvectorpayload",
    "responsepayload",
    "searchpayload",
    "supportingevidence",
    "supportingevidencefinal",
    "supportingevidencetext",
    "targetlocator",
    "vectorpayload",
    "vectorpayloadtext",
}
_PROTECTED_VECTOR_METADATA_KEY_FRAGMENTS = (
    "canonicalpayload",
    "canonicalcitationpayload",
    "candidatecanonicalcitationpayload",
    "expectedanswer",
    "goldanswer",
    "goldlabel",
    "goldlocator",
    "hiddentargetlocator",
    "oraclepayload",
    "promptpayload",
    "qrels",
    "rawllmresponse",
    "rawprompt",
    "responsepayload",
    "supportingevidence",
    "targetlocator",
    "vectorpayload",
)


def _is_candidate_payload_metadata_key(key: str) -> bool:
    normalized = "".join(ch for ch in key if ch.isalnum()).lower()
    return normalized in _PROTECTED_VECTOR_METADATA_KEYS or any(
        fragment in normalized for fragment in _PROTECTED_VECTOR_METADATA_KEY_FRAGMENTS
    )


def _source_file_type(chunk: Any, metadata: Mapping[str, Any]) -> str:
    raw = (
        _metadata_any(metadata, "sourceFileType", "source_file_type")
        or _get_any(chunk, "artifact_type", "artifactType")
        or _metadata_any(metadata, "artifactType", "artifact_type")
    )
    return _normalize_source_file_type(raw)


def _normalize_source_file_type(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in {"PDF", "APPLICATION/PDF"}:
        return SOURCE_FILE_TYPE_PDF
    if text in {
        "SPREADSHEET",
        "XLSX",
        "XLSM",
        "XLSX_WORKBOOK_JSON",
        "APPLICATION/VND.OPENXMLFORMATS-OFFICEDOCUMENT.SPREADSHEETML.SHEET",
    }:
        return SOURCE_FILE_TYPE_SPREADSHEET
    if text in {"TEXT", "TXT", "PLAIN_TEXT", "MARKDOWN", "MD"}:
        return SOURCE_FILE_TYPE_TEXT
    return text


def _location_json(
    chunk: Any,
    metadata: Mapping[str, Any],
    source_file_type: str,
) -> dict[str, Any]:
    explicit = _metadata_any(metadata, "locationJson", "location_json")
    if isinstance(explicit, Mapping):
        return dict(explicit)

    if source_file_type == SOURCE_FILE_TYPE_PDF:
        page_start = _get_any(chunk, "page_start", "pageStart") or _metadata_any(
            metadata,
            "pageStart",
            "page_start",
            "page",
            "page_no",
            "pageNo",
        )
        page_end = _get_any(chunk, "page_end", "pageEnd") or _metadata_any(
            metadata,
            "pageEnd",
            "page_end",
        )
        location: dict[str, Any] = {}
        if page_start not in (None, ""):
            location["page_start"] = page_start
        if page_end not in (None, ""):
            location["page_end"] = page_end
        return location

    if source_file_type == SOURCE_FILE_TYPE_SPREADSHEET:
        location = _pick_metadata(
            metadata,
            {
                "sheetName": ("sheetName", "sheet_name"),
                "sheetIndex": ("sheetIndex", "sheet_index"),
                "cellRange": ("cellRange", "cell_range", "range", "usedRange"),
                "tableId": ("tableId", "table_id", "tableName"),
                "rowStart": ("rowStart", "row_start"),
                "rowEnd": ("rowEnd", "row_end"),
                "columnStart": ("columnStart", "column_start"),
                "columnEnd": ("columnEnd", "column_end"),
                "hidden_policy_version": (
                    "hidden_policy_version",
                    "hiddenPolicyVersion",
                ),
            },
        )
        return location

    return _pick_metadata(
        metadata,
        {
            "section_path": ("sectionPath", "section_path"),
            "char_start": ("charStart", "char_start"),
            "char_end": ("charEnd", "char_end"),
        },
    )


def _pick_metadata(
    metadata: Mapping[str, Any],
    keys_by_output: Mapping[str, tuple[str, ...]],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for output_key, keys in keys_by_output.items():
        value = _metadata_any(metadata, *keys)
        if value not in (None, ""):
            output[output_key] = value
    return output


def _default_location_type(source_file_type: str) -> str | None:
    if source_file_type == SOURCE_FILE_TYPE_PDF:
        return "pdf"
    if source_file_type == SOURCE_FILE_TYPE_SPREADSHEET:
        return "xlsx"
    if source_file_type == SOURCE_FILE_TYPE_TEXT:
        return "text"
    return None


def _get_any(value: Any, *keys: str) -> Any:
    if isinstance(value, Mapping):
        for key in keys:
            if key in value:
                return value[key]
        return None
    for key in keys:
        if hasattr(value, key):
            return getattr(value, key)
    return None


def _metadata_any(metadata: Mapping[str, Any], *keys: str) -> Any:
    return _get_any(metadata, *keys)


def _location_value(location_json: Mapping[str, Any], key: str) -> Any:
    return location_json.get(key) if isinstance(location_json, Mapping) else None


def _string(value: Any, *, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _optional_string(value: Any) -> str | None:
    text = _string(value)
    return text or None


def _list_strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _bool_metadata(metadata: Mapping[str, Any], *keys: str) -> bool:
    value = _metadata_any(metadata, *keys)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return tuple(output)
