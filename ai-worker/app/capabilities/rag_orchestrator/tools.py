"""Fake query-time vector tools for the RAG orchestrator POC.

These wrappers are fixture-only. They do not call Retriever, FAISS, DB, Spring
APIs, LangGraph, or LangChain.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Literal, Mapping

from app.capabilities.rag_orchestrator.citation_verify import (
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

TOOL_PDF_VECTOR_SEARCH = "fake_pdf_vector_search_tool"
TOOL_XLSX_VECTOR_SEARCH = "fake_xlsx_vector_search_tool"
TOOL_TEXT_VECTOR_SEARCH = "fake_text_vector_search_tool"

FAKE_VECTOR_BACKEND = "fake_vector"
TEXT_CONTRACT_READINESS_WARNING = "text_contract_not_production_ready"

FixtureMode = Literal["valid", "mismatch", "mixed"]

VECTOR_WRAPPER_TODOS = (
    "Replace fake fixture rows with bounded calls to the real vector retriever.",
    "Apply source type, parser version, embedding status, and index version filters before retrieval where possible.",
    "Keep library-search diagnostic-only and out of production Evidence.",
    "Preserve citation_verify_tool as the deterministic gate before answer synthesis.",
)


@dataclass(frozen=True)
class RejectedEvidence:
    evidence: Evidence
    reasons: tuple[str, ...]

    @property
    def evidence_id(self) -> str:
        return self.evidence.evidence_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidenceId": self.evidence_id,
            "reasons": list(self.reasons),
            "evidence": self.evidence.to_dict(),
        }


@dataclass(frozen=True)
class ToolResult:
    tool: str
    evidence: tuple[Evidence, ...]
    rejected: tuple[RejectedEvidence, ...]
    backend_identity: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "evidence": [item.to_dict() for item in self.evidence],
            "rejected": [item.to_dict() for item in self.rejected],
            "backend_identity": dict(self.backend_identity),
        }


def fake_pdf_vector_search_tool(
    query: str,
    policy: QueryPolicy,
    *,
    fixture: FixtureMode = "valid",
) -> ToolResult:
    """Return PDF Evidence fixtures in the shared tool result shape."""

    return _run_fake_tool(
        tool=TOOL_PDF_VECTOR_SEARCH,
        query=query,
        policy=policy,
        source_file_type=SOURCE_FILE_TYPE_PDF,
        parser_version="pdf-extract-v2",
        rows=_fixture_rows(
            fixture=fixture,
            source_file_type=SOURCE_FILE_TYPE_PDF,
            parser_version="pdf-extract-v2",
            policy=policy,
        ),
    )


def fake_xlsx_vector_search_tool(
    query: str,
    policy: QueryPolicy,
    *,
    fixture: FixtureMode = "valid",
) -> ToolResult:
    """Return XLSX/SPREADSHEET Evidence fixtures in the shared result shape."""

    return _run_fake_tool(
        tool=TOOL_XLSX_VECTOR_SEARCH,
        query=query,
        policy=policy,
        source_file_type=SOURCE_FILE_TYPE_SPREADSHEET,
        parser_version="xlsx-extract-v2-hidden-safe",
        rows=_fixture_rows(
            fixture=fixture,
            source_file_type=SOURCE_FILE_TYPE_SPREADSHEET,
            parser_version="xlsx-extract-v2-hidden-safe",
            policy=policy,
        ),
    )


def fake_text_vector_search_tool(
    query: str,
    policy: QueryPolicy,
    *,
    fixture: FixtureMode = "valid",
) -> ToolResult:
    """Return TEXT Evidence fixtures in the shared result shape.

    TEXT rows carry a readiness warning because the production typed locator
    contract is intentionally not finalized in this POC.
    """

    return _run_fake_tool(
        tool=TOOL_TEXT_VECTOR_SEARCH,
        query=query,
        policy=policy,
        source_file_type=SOURCE_FILE_TYPE_TEXT,
        parser_version="text-parser-v0",
        rows=_fixture_rows(
            fixture=fixture,
            source_file_type=SOURCE_FILE_TYPE_TEXT,
            parser_version="text-parser-v0",
            policy=policy,
        ),
    )


def _run_fake_tool(
    *,
    tool: str,
    query: str,
    policy: QueryPolicy,
    source_file_type: str,
    parser_version: str,
    rows: Iterable[Evidence],
) -> ToolResult:
    del query
    verification = citation_verify_tool(rows, policy)
    evidence = tuple(_verified_evidence(item) for item in verification.verified)
    rejected = tuple(_rejected_evidence(item) for item in verification.rejected)
    return ToolResult(
        tool=tool,
        evidence=evidence,
        rejected=rejected,
        backend_identity={
            "backend": FAKE_VECTOR_BACKEND,
            "retrieval_backend": RETRIEVAL_BACKEND_VECTOR,
            "index_namespace_filter": policy.required_index_version,
            "source_file_type_filter": source_file_type,
            "parser_version_fixture": parser_version,
        },
    )


def _verified_evidence(item) -> Evidence:
    warnings = tuple(item.evidence.verification_warnings) + tuple(item.warnings)
    return replace(
        item.evidence,
        verification_status="verified",
        verification_reasons=(),
        verification_warnings=_dedupe(warnings),
    )


def _rejected_evidence(item) -> RejectedEvidence:
    evidence = replace(
        item.evidence,
        verification_status="rejected",
        verification_reasons=item.fatal_reasons,
        verification_warnings=item.warnings,
    )
    return RejectedEvidence(evidence=evidence, reasons=item.fatal_reasons)


def _fixture_rows(
    *,
    fixture: FixtureMode,
    source_file_type: str,
    parser_version: str,
    policy: QueryPolicy,
) -> tuple[Evidence, ...]:
    valid = _valid_evidence(
        source_file_type=source_file_type,
        parser_version=parser_version,
        policy=policy,
        rank=1,
    )
    mismatches = _mismatch_evidence(
        source_file_type=source_file_type,
        parser_version=parser_version,
        policy=policy,
    )
    if fixture == "valid":
        return (valid,)
    if fixture == "mismatch":
        return mismatches
    if fixture == "mixed":
        return (valid, *mismatches)
    raise ValueError(f"unknown fixture mode: {fixture}")


def _valid_evidence(
    *,
    source_file_type: str,
    parser_version: str,
    policy: QueryPolicy,
    rank: int,
) -> Evidence:
    evidence_id = f"{source_file_type.lower()}-valid-{rank}"
    location_type, location_json, citation_text = _valid_locator(source_file_type)
    warnings = (
        (TEXT_CONTRACT_READINESS_WARNING,)
        if source_file_type == SOURCE_FILE_TYPE_TEXT
        else ()
    )
    return Evidence(
        evidence_id=evidence_id,
        retrieval_backend=RETRIEVAL_BACKEND_VECTOR,
        rank=rank,
        scores={"dense": 1.0 / rank, "final": 1.0 / rank},
        source_file_id=f"source-{evidence_id}",
        source_file_name=f"{evidence_id}.{_extension(source_file_type)}",
        source_file_type=source_file_type,
        document_id=f"doc-{evidence_id}",
        document_version_id=f"docver-{evidence_id}",
        parsed_artifact_id=f"artifact-{evidence_id}",
        index_version=policy.required_index_version,
        embedding_status=policy.required_embedding_status,
        embedding_model="fake-embedding-model",
        embedding_text_sha256=f"sha256-{evidence_id}",
        vector_id=f"{policy.required_index_version}:{evidence_id}",
        parser_name="fake-parser",
        parser_version=parser_version,
        search_unit_id=f"unit-{evidence_id}",
        chunk_id=f"chunk-{evidence_id}",
        unit_type=_unit_type(source_file_type),
        unit_key=f"{_unit_type(source_file_type).lower()}:{evidence_id}",
        chunk_type=_chunk_type(source_file_type),
        text=f"Fake {source_file_type} vector evidence for orchestrator tests.",
        display_text=f"Fake {source_file_type} evidence",
        snippet=f"Fake {source_file_type} evidence",
        citation_text=citation_text,
        location_type=location_type,
        location_json=location_json,
        hidden_policy_version=(
            "exclude-hidden-v1"
            if source_file_type == SOURCE_FILE_TYPE_SPREADSHEET
            else None
        ),
        verification_warnings=warnings,
        extra={"fixture": "valid"},
    )


def _mismatch_evidence(
    *,
    source_file_type: str,
    parser_version: str,
    policy: QueryPolicy,
) -> tuple[Evidence, ...]:
    valid = _valid_evidence(
        source_file_type=source_file_type,
        parser_version=parser_version,
        policy=policy,
        rank=1,
    )
    wrong_type = (
        SOURCE_FILE_TYPE_TEXT
        if source_file_type != SOURCE_FILE_TYPE_TEXT
        else SOURCE_FILE_TYPE_PDF
    )
    return (
        replace(
            valid,
            evidence_id=f"{source_file_type.lower()}-wrong-index",
            search_unit_id=f"unit-{source_file_type.lower()}-wrong-index",
            chunk_id=f"chunk-{source_file_type.lower()}-wrong-index",
            index_version=f"{policy.required_index_version}-wrong",
            extra={"fixture": "wrong_index_version"},
        ),
        replace(
            valid,
            evidence_id=f"{source_file_type.lower()}-wrong-parser",
            search_unit_id=f"unit-{source_file_type.lower()}-wrong-parser",
            chunk_id=f"chunk-{source_file_type.lower()}-wrong-parser",
            parser_version=f"{parser_version}-wrong",
            extra={"fixture": "wrong_parser_version"},
        ),
        replace(
            valid,
            evidence_id=f"{source_file_type.lower()}-missing-citation",
            search_unit_id=f"unit-{source_file_type.lower()}-missing-citation",
            chunk_id=f"chunk-{source_file_type.lower()}-missing-citation",
            citation_text="",
            extra={"fixture": "missing_citation"},
        ),
        replace(
            valid,
            evidence_id=f"{source_file_type.lower()}-missing-location",
            search_unit_id=f"unit-{source_file_type.lower()}-missing-location",
            chunk_id=f"chunk-{source_file_type.lower()}-missing-location",
            location_json={},
            extra={"fixture": "missing_location"},
        ),
        replace(
            valid,
            evidence_id=f"{source_file_type.lower()}-wrong-source-type",
            search_unit_id=f"unit-{source_file_type.lower()}-wrong-source-type",
            chunk_id=f"chunk-{source_file_type.lower()}-wrong-source-type",
            source_file_type=wrong_type,
            extra={"fixture": "wrong_source_type"},
        ),
    )


def _valid_locator(source_file_type: str) -> tuple[str, dict[str, Any], str]:
    if source_file_type == SOURCE_FILE_TYPE_PDF:
        return "pdf", {"page_no": 2, "page_label": "2"}, "fake.pdf p. 2"
    if source_file_type == SOURCE_FILE_TYPE_SPREADSHEET:
        return (
            "xlsx",
            {
                "sheetName": "Sales",
                "cellRange": "A1:D5",
                "tableId": "sales-table",
                "hidden_policy_version": "exclude-hidden-v1",
            },
            "fake.xlsx Sales!A1:D5",
        )
    return (
        "text",
        {"section_path": "Overview", "char_start": 0, "char_end": 48},
        "fake.txt Overview",
    )


def _extension(source_file_type: str) -> str:
    if source_file_type == SOURCE_FILE_TYPE_PDF:
        return "pdf"
    if source_file_type == SOURCE_FILE_TYPE_SPREADSHEET:
        return "xlsx"
    return "txt"


def _unit_type(source_file_type: str) -> str:
    if source_file_type == SOURCE_FILE_TYPE_PDF:
        return "PAGE"
    if source_file_type == SOURCE_FILE_TYPE_SPREADSHEET:
        return "TABLE"
    return "SPAN"


def _chunk_type(source_file_type: str) -> str:
    if source_file_type == SOURCE_FILE_TYPE_PDF:
        return "pdf_page"
    if source_file_type == SOURCE_FILE_TYPE_SPREADSHEET:
        return "xlsx_table"
    return "text_span"


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)
