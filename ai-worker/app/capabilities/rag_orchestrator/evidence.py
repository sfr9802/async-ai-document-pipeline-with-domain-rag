"""Evidence contract for the query-time RAG orchestrator POC."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

EVIDENCE_CONTRACT_VERSION = "rag-evidence-v0"
RETRIEVAL_BACKEND_VECTOR = "vector"
EMBEDDING_STATUS_EMBEDDED = "EMBEDDED"

SOURCE_FILE_TYPE_PDF = "PDF"
SOURCE_FILE_TYPE_SPREADSHEET = "SPREADSHEET"
SOURCE_FILE_TYPE_TEXT = "TEXT"


def _clean_str(value: str | None) -> str:
    return (value or "").strip()


def _upper(value: str | None) -> str:
    return _clean_str(value).upper()


def _lower(value: str | None) -> str:
    return _clean_str(value).lower()


def _tuple_str(values: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    return tuple(str(v).strip() for v in (values or ()) if str(v).strip())


def _tuple_upper(values: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    return tuple(_upper(v) for v in (values or ()) if _clean_str(v))


@dataclass(frozen=True)
class QueryPolicy:
    """Code-created retrieval policy.

    The orchestrator must receive this from trusted application code. LLM output
    can suggest intent, but cannot create or relax these filters.
    """

    request_id: str
    required_index_version: str
    allowed_source_file_types: tuple[str, ...] | list[str]
    allowed_parser_versions: tuple[str, ...] | list[str]
    user_id: str | None = None
    tenant_id: str | None = None
    acl_tags: tuple[str, ...] | list[str] = field(default_factory=tuple)
    required_embedding_status: str = EMBEDDING_STATUS_EMBEDDED
    top_k: int = 10
    created_by: str = field(default="code", init=False)

    def __post_init__(self) -> None:
        request_id = _clean_str(self.request_id)
        index_version = _clean_str(self.required_index_version)
        source_types = _tuple_upper(self.allowed_source_file_types)
        parser_versions = _tuple_str(self.allowed_parser_versions)
        embedding_status = _upper(self.required_embedding_status)
        acl_tags = _tuple_str(self.acl_tags)

        if not request_id:
            raise ValueError("request_id is required")
        if not index_version:
            raise ValueError("required_index_version is required")
        if not source_types:
            raise ValueError("allowed_source_file_types is required")
        if not parser_versions:
            raise ValueError("allowed_parser_versions is required")
        if self.top_k < 1:
            raise ValueError("top_k must be positive")

        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "required_index_version", index_version)
        object.__setattr__(self, "allowed_source_file_types", source_types)
        object.__setattr__(self, "allowed_parser_versions", parser_versions)
        object.__setattr__(self, "acl_tags", acl_tags)
        object.__setattr__(self, "required_embedding_status", embedding_status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requestId": self.request_id,
            "userId": self.user_id,
            "tenantId": self.tenant_id,
            "aclTags": list(self.acl_tags),
            "requiredIndexVersion": self.required_index_version,
            "allowedSourceFileTypes": list(self.allowed_source_file_types),
            "allowedParserVersions": list(self.allowed_parser_versions),
            "requiredEmbeddingStatus": self.required_embedding_status,
            "topK": self.top_k,
            "createdBy": self.created_by,
        }


@dataclass(frozen=True)
class Evidence:
    """Single vector-backed evidence item shared by PDF/XLSX/TEXT tools."""

    evidence_id: str
    retrieval_backend: str
    rank: int
    source_file_id: str
    source_file_type: str
    index_version: str
    embedding_status: str
    parser_version: str
    citation_text: str
    location_json: Any
    search_unit_id: str
    chunk_id: str
    text: str
    evidence_contract_version: str = EVIDENCE_CONTRACT_VERSION
    source_file_name: str | None = None
    document_id: str | None = None
    document_version_id: str | None = None
    parsed_artifact_id: str | None = None
    parser_name: str | None = None
    embedding_model: str | None = None
    embedding_text_sha256: str | None = None
    vector_id: str | None = None
    unit_type: str | None = None
    unit_key: str | None = None
    chunk_type: str | None = None
    display_text: str | None = None
    snippet: str | None = None
    location_type: str | None = None
    scores: Mapping[str, float | None] = field(default_factory=dict)
    tenant_id: str | None = None
    acl_tags: tuple[str, ...] | list[str] = field(default_factory=tuple)
    hidden_policy_version: str | None = None
    diagnostic_only: bool = False
    extra: Mapping[str, Any] = field(default_factory=dict)
    verification_status: str = "unchecked"
    verification_reasons: tuple[str, ...] | list[str] = field(default_factory=tuple)
    verification_warnings: tuple[str, ...] | list[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.evidence_contract_version != EVIDENCE_CONTRACT_VERSION:
            raise ValueError(
                "unsupported evidence_contract_version: "
                f"{self.evidence_contract_version}"
            )
        if self.rank < 1:
            raise ValueError("rank must be positive")
        if not _clean_str(self.evidence_id):
            raise ValueError("evidence_id is required")
        if not _clean_str(self.search_unit_id):
            raise ValueError("search_unit_id is required")
        if not _clean_str(self.chunk_id):
            raise ValueError("chunk_id is required")

        object.__setattr__(self, "evidence_id", _clean_str(self.evidence_id))
        object.__setattr__(self, "retrieval_backend", _lower(self.retrieval_backend))
        object.__setattr__(self, "source_file_type", _upper(self.source_file_type))
        object.__setattr__(self, "index_version", _clean_str(self.index_version))
        object.__setattr__(self, "embedding_status", _upper(self.embedding_status))
        object.__setattr__(self, "parser_version", _clean_str(self.parser_version))
        object.__setattr__(self, "citation_text", _clean_str(self.citation_text))
        object.__setattr__(self, "search_unit_id", _clean_str(self.search_unit_id))
        object.__setattr__(self, "chunk_id", _clean_str(self.chunk_id))
        object.__setattr__(self, "acl_tags", _tuple_str(self.acl_tags))
        object.__setattr__(self, "scores", dict(self.scores or {}))
        location_json = (
            dict(self.location_json)
            if isinstance(self.location_json, Mapping)
            else self.location_json
        )
        object.__setattr__(self, "location_json", location_json)
        object.__setattr__(self, "extra", dict(self.extra or {}))
        object.__setattr__(
            self, "verification_reasons", _tuple_str(self.verification_reasons)
        )
        object.__setattr__(
            self, "verification_warnings", _tuple_str(self.verification_warnings)
        )

    def to_dict(self) -> dict[str, Any]:
        display_text = self.display_text if self.display_text is not None else self.text
        snippet = self.snippet if self.snippet is not None else _preview(self.text)
        location_json = (
            dict(self.location_json)
            if isinstance(self.location_json, Mapping)
            else self.location_json
        )
        return {
            "evidenceContractVersion": self.evidence_contract_version,
            "evidenceId": self.evidence_id,
            "retrievalBackend": self.retrieval_backend,
            "diagnosticOnly": self.diagnostic_only,
            "rank": self.rank,
            "scores": dict(self.scores),
            "source": {
                "sourceFileId": self.source_file_id,
                "sourceFileName": self.source_file_name,
                "sourceFileType": self.source_file_type,
                "documentId": self.document_id,
                "documentVersionId": self.document_version_id,
                "parsedArtifactId": self.parsed_artifact_id,
                "parserName": self.parser_name,
                "parserVersion": self.parser_version,
            },
            "index": {
                "indexVersion": self.index_version,
                "embeddingStatus": self.embedding_status,
                "embeddingModel": self.embedding_model,
                "embeddingTextSha256": self.embedding_text_sha256,
                "vectorId": self.vector_id,
            },
            "unit": {
                "searchUnitId": self.search_unit_id,
                "chunkId": self.chunk_id,
                "unitType": self.unit_type,
                "unitKey": self.unit_key,
                "chunkType": self.chunk_type,
            },
            "content": {
                "text": self.text,
                "displayText": display_text,
                "snippet": snippet,
                "citationText": self.citation_text,
            },
            "location": {
                "locationType": self.location_type,
                "locationJson": location_json,
            },
            "policy": {
                "tenantId": self.tenant_id,
                "aclTags": list(self.acl_tags),
                "hiddenPolicyVersion": self.hidden_policy_version,
            },
            "verification": {
                "status": self.verification_status,
                "reasons": list(self.verification_reasons),
                "warnings": list(self.verification_warnings),
            },
            "extra": dict(self.extra),
        }


def _preview(text: str, *, max_chars: int = 240) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3] + "..."
