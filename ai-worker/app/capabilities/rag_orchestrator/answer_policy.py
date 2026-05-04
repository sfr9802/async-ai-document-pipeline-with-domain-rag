"""Answer handoff policy for the RAG orchestrator POC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal, Sequence

from app.capabilities.rag_orchestrator.evidence import Evidence

NO_EVIDENCE_MESSAGE = "근거를 찾지 못했습니다."

NoEvidenceAction = Literal["refusal", "clarification_needed", "fallback_required"]


@dataclass(frozen=True)
class AnswerPolicyResult:
    status: str
    answer: str
    used_evidence_ids: tuple[str, ...]
    verified_evidence: tuple[Evidence, ...]
    reason: str
    action: NoEvidenceAction | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "answer": self.answer,
            "used_evidence_ids": list(self.used_evidence_ids),
            "verified_evidence": [item.to_dict() for item in self.verified_evidence],
            "reason": self.reason,
            "action": self.action,
        }


def verified_evidence_for_answer(evidence: Iterable[Evidence]) -> tuple[Evidence, ...]:
    return tuple(item for item in evidence if item.verification_status == "verified")


def build_no_evidence_response(
    *,
    query: str,
    action: NoEvidenceAction = "refusal",
) -> AnswerPolicyResult:
    del query
    return AnswerPolicyResult(
        status="blocked",
        answer=NO_EVIDENCE_MESSAGE,
        used_evidence_ids=(),
        verified_evidence=(),
        reason="no_verified_evidence",
        action=action,
    )


def prepare_answer_handoff(
    *,
    query: str,
    evidence: Iterable[Evidence],
    used_evidence_ids: Sequence[str] | None = None,
    no_evidence_action: NoEvidenceAction = "refusal",
) -> AnswerPolicyResult:
    verified = verified_evidence_for_answer(evidence)
    if not verified:
        return build_no_evidence_response(query=query, action=no_evidence_action)

    allowed_ids = {item.evidence_id for item in verified}
    requested_ids = (
        tuple(item.evidence_id for item in verified)
        if used_evidence_ids is None
        else tuple(used_evidence_ids)
    )
    invalid_ids = tuple(item for item in requested_ids if item not in allowed_ids)
    if invalid_ids:
        raise ValueError(
            "used_evidence_ids must be a subset of verified evidence ids: "
            + ", ".join(invalid_ids)
        )

    ordered_ids = tuple(item.evidence_id for item in verified if item.evidence_id in requested_ids)
    return AnswerPolicyResult(
        status="ready",
        answer="",
        used_evidence_ids=ordered_ids,
        verified_evidence=verified,
        reason="verified_evidence_available",
        action=None,
    )
