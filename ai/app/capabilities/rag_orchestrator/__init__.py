"""Query-time RAG orchestrator POC primitives.

This package keeps the orchestration contract and deterministic helper code
small. The worker registry may expose the POC as an opt-in capability, but it
does not add a public endpoint.
"""

from app.capabilities.rag_orchestrator.citation_verify import (
    CitationVerificationResult,
    EvidenceVerification,
    citation_verify_tool,
    verify_evidence,
)
from app.capabilities.rag_orchestrator.answer_policy import (
    AnswerPolicyResult,
    build_no_evidence_response,
    prepare_answer_handoff,
    verified_evidence_for_answer,
)
from app.capabilities.rag_orchestrator.evidence import (
    EVIDENCE_CONTRACT_VERSION,
    EMBEDDING_STATUS_EMBEDDED,
    RETRIEVAL_BACKEND_VECTOR,
    Evidence,
    QueryPolicy,
)
from app.capabilities.rag_orchestrator.evidence_merge import (
    EvidenceMergeResult,
    evidence_merge_tool,
)
from app.capabilities.rag_orchestrator.tools import (
    FAKE_VECTOR_BACKEND,
    TEXT_CONTRACT_READINESS_WARNING,
    RejectedEvidence,
    ToolResult,
    fake_pdf_vector_search_tool,
    fake_text_vector_search_tool,
    fake_xlsx_vector_search_tool,
)

__all__ = [
    "AnswerPolicyResult",
    "CitationVerificationResult",
    "EVIDENCE_CONTRACT_VERSION",
    "EMBEDDING_STATUS_EMBEDDED",
    "Evidence",
    "EvidenceMergeResult",
    "EvidenceVerification",
    "FAKE_VECTOR_BACKEND",
    "QueryPolicy",
    "RETRIEVAL_BACKEND_VECTOR",
    "RejectedEvidence",
    "TEXT_CONTRACT_READINESS_WARNING",
    "ToolResult",
    "build_no_evidence_response",
    "citation_verify_tool",
    "evidence_merge_tool",
    "fake_pdf_vector_search_tool",
    "fake_text_vector_search_tool",
    "fake_xlsx_vector_search_tool",
    "prepare_answer_handoff",
    "verify_evidence",
    "verified_evidence_for_answer",
]
