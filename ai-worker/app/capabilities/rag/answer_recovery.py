"""Diagnostic answer sufficiency and recovery bridge for RAG answers.

This module is intentionally policy-heavy and side-effect-free. It does not
promote answer denominators, mutate indexes, train profiles, or relax lane
boundaries. It decides whether a draft answer is sufficiently cited and, when
not, routes the request to a clarification question or to the existing internal
agent loop under RAG-specific guardrails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from app.capabilities.agent.critic import RuleCritic
from app.capabilities.agent.loop import AgentLoopController, LoopBudget, LoopOutcome
from app.capabilities.agent.rewriter import NoOpQueryRewriter
from app.capabilities.rag.generation import RetrievedChunk
from app.capabilities.rag.query_parser import RegexQueryParser
from app.capabilities.rag.shadow_lane_contract import (
    DIAGNOSTIC_ONLY,
    IDP_TABLE_MEDIUM,
    MULTIMODAL_CAPTION_LOW,
    NATIVE_TEXT_HIGH,
    OCR_MEDIUM,
    STRUCTURED_XLSX_HIGH,
    TRUST_RANK,
)


SUPPORTED = "SUPPORTED"
NEEDS_RECOVERY = "NEEDS_RECOVERY"
NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
UNSUPPORTED = "UNSUPPORTED"

INSUFFICIENT_RETRIEVAL = "INSUFFICIENT_RETRIEVAL"
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
AMBIGUOUS_QUERY = "AMBIGUOUS_QUERY"
LANE_MISMATCH = "LANE_MISMATCH"
CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
NEEDS_USER_CONSTRAINT = "NEEDS_USER_CONSTRAINT"
UNANSWERABLE_WITH_AVAILABLE_CONTEXT = "UNANSWERABLE_WITH_AVAILABLE_CONTEXT"

TEXT = "TEXT"
XLSX = "XLSX"
PDF_CONTENT = "PDF_CONTENT"
PDF_FILE_LOOKUP = "PDF_FILE_LOOKUP"
OCR_SHADOW = "OCR_SHADOW"
IDP_SHADOW = "IDP_SHADOW"
MULTIMODAL_SHADOW = "MULTIMODAL_SHADOW"

ASK_CLARIFICATION = "ASK_CLARIFICATION"
AGENTIC_RETRIEVAL_LOOP = "AGENTIC_RETRIEVAL_LOOP"
ADJACENT_CONTEXT_EXPANSION = "ADJACENT_CONTEXT_EXPANSION"
LANE_REROUTE = "LANE_REROUTE"
PREFER_HIGHER_TRUST_EVIDENCE = "PREFER_HIGHER_TRUST_EVIDENCE"
GROUNDED_INSUFFICIENCY = "GROUNDED_INSUFFICIENCY"
NOOP_SUPPORTED = "NOOP_SUPPORTED"

SHADOW_DIAGNOSTIC_TRUST_TIERS = {OCR_MEDIUM, IDP_TABLE_MEDIUM, MULTIMODAL_CAPTION_LOW, DIAGNOSTIC_ONLY}
CONTENT_INTENT_MARKERS = {
    "content",
    "page",
    "bbox",
    "table",
    "row",
    "column",
    "value",
    "본문",
    "내용",
    "페이지",
    "표",
    "행",
    "열",
    "값",
    "요약",
}


@dataclass(frozen=True)
class AnswerEvidenceCandidate:
    lane: str
    text: str = ""
    citation_text: str = ""
    location_json: Mapping[str, Any] | None = None
    trust_tier: str = NATIVE_TEXT_HIGH
    evidence_role: str = "official"
    denominator_role: str = ""
    diagnostic_only: bool = False
    hidden: bool = False
    source_file_type: str = ""
    unit_type: str = ""
    confidence: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_any(cls, value: "AnswerEvidenceCandidate | Mapping[str, Any]") -> "AnswerEvidenceCandidate":
        if isinstance(value, cls):
            return value
        metadata = dict(value.get("metadata") or value.get("extra") or {})
        location = value.get("location_json") or value.get("locationJson") or value.get("location")
        if isinstance(location, Mapping) and "locationJson" in location:
            location = location.get("locationJson")
        citation = (
            value.get("citation_text")
            or value.get("citationText")
            or nested(value, "content", "citationText")
            or ""
        )
        text = value.get("text") or nested(value, "content", "text") or value.get("display_text") or ""
        lane = clean(value.get("lane") or value.get("retrieval_lane") or value.get("source_file_type") or "")
        return cls(
            lane=lane.upper() or TEXT,
            text=clean(text),
            citation_text=clean(citation),
            location_json=dict(location) if isinstance(location, Mapping) else None,
            trust_tier=clean(value.get("trust_tier") or value.get("trustTier") or metadata.get("trust_tier") or NATIVE_TEXT_HIGH),
            evidence_role=clean(value.get("evidence_role") or value.get("evidenceRole") or metadata.get("evidence_role") or "official"),
            denominator_role=clean(value.get("denominator_role") or value.get("denominatorRole") or metadata.get("denominator_role")),
            diagnostic_only=as_bool(value.get("diagnostic_only") or value.get("diagnosticOnly") or metadata.get("diagnostic_only")),
            hidden=as_bool(value.get("hidden") or value.get("hidden_content") or metadata.get("hidden") or metadata.get("hidden_content")),
            source_file_type=clean(value.get("source_file_type") or nested(value, "source", "sourceFileType")),
            unit_type=clean(value.get("unit_type") or value.get("unitType") or nested(value, "unit", "unitType")),
            confidence=to_float(value.get("confidence") or metadata.get("confidence")),
            metadata=metadata,
        )

    @property
    def has_citation_support(self) -> bool:
        return bool(self.citation_text and self.location_json)

    @property
    def is_shadow_diagnostic(self) -> bool:
        return (
            self.diagnostic_only
            or self.denominator_role == DIAGNOSTIC_ONLY
            or self.evidence_role == "diagnostic"
            or self.trust_tier in SHADOW_DIAGNOSTIC_TRUST_TIERS
            or self.lane in {OCR_SHADOW, IDP_SHADOW, MULTIMODAL_SHADOW}
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "text": self.text,
            "citation_text": self.citation_text,
            "location_json": dict(self.location_json or {}),
            "trust_tier": self.trust_tier,
            "evidence_role": self.evidence_role,
            "denominator_role": self.denominator_role,
            "diagnostic_only": self.diagnostic_only,
            "hidden": self.hidden,
            "source_file_type": self.source_file_type,
            "unit_type": self.unit_type,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AnswerSufficiencyDecision:
    sufficiency_status: str
    failure_type: str
    support_score: float
    citation_coverage: float
    recommended_recovery_actions: tuple[str, ...]
    required_followup_question: str
    allowed_lanes: tuple[str, ...]
    blocked_lanes: tuple[str, ...]
    diagnostic_reason: str
    evidence_count: int = 0
    cited_evidence_count: int = 0
    official_support: bool = False
    best_trust_tier: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sufficiency_status": self.sufficiency_status,
            "failure_type": self.failure_type,
            "support_score": self.support_score,
            "citation_coverage": self.citation_coverage,
            "recommended_recovery_actions": list(self.recommended_recovery_actions),
            "required_followup_question": self.required_followup_question,
            "allowed_lanes": list(self.allowed_lanes),
            "blocked_lanes": list(self.blocked_lanes),
            "diagnostic_reason": self.diagnostic_reason,
            "evidence_count": self.evidence_count,
            "cited_evidence_count": self.cited_evidence_count,
            "official_support": self.official_support,
            "best_trust_tier": self.best_trust_tier,
        }


class AnswerSufficiencyJudge:
    """Deterministic, fail-closed answer support checker."""

    def evaluate(
        self,
        *,
        user_query: str,
        lane: str,
        draft_answer: str,
        retrieved_evidence_candidates: Sequence[AnswerEvidenceCandidate | Mapping[str, Any]],
        answer_shape_metadata: Mapping[str, Any] | None = None,
    ) -> AnswerSufficiencyDecision:
        lane = normalize_lane(lane)
        metadata = dict(answer_shape_metadata or {})
        candidates = [AnswerEvidenceCandidate.from_any(item) for item in retrieved_evidence_candidates]
        ranked = rank_candidates_by_trust(candidates)
        cited = [item for item in candidates if item.has_citation_support]
        citation_coverage = round(len(cited) / len(candidates), 6) if candidates else 0.0
        best_trust = ranked[0].trust_tier if ranked else ""

        if metadata.get("requires_user_constraint"):
            return decision(
                NEEDS_CLARIFICATION,
                NEEDS_USER_CONSTRAINT,
                0.0,
                citation_coverage,
                (),
                targeted_question(user_query, lane, NEEDS_USER_CONSTRAINT),
                allowed_lanes_for(lane),
                (),
                "The query needs a user-supplied sheet, period, metric, file, or entity constraint.",
                candidates,
                cited,
                best_trust,
            )

        if metadata.get("ambiguous_query") or is_ambiguous_query(user_query, lane, metadata):
            return decision(
                NEEDS_CLARIFICATION,
                AMBIGUOUS_QUERY,
                0.0,
                citation_coverage,
                (),
                targeted_question(user_query, lane, AMBIGUOUS_QUERY),
                allowed_lanes_for(lane),
                (),
                "The query is ambiguous enough that recovery should ask a targeted clarification first.",
                candidates,
                cited,
                best_trust,
            )

        if lane == PDF_FILE_LOOKUP and asks_for_content_answer(user_query, metadata):
            return decision(
                NEEDS_RECOVERY,
                LANE_MISMATCH,
                0.1,
                citation_coverage,
                ("lane_reroute:PDF_CONTENT", "file_identity_clarification"),
                "",
                (PDF_CONTENT,),
                (PDF_FILE_LOOKUP,),
                "PDF FILE lookup is file identity only and cannot support content/page/bbox/table/row/column/value answers.",
                candidates,
                cited,
                best_trust,
            )

        if lane == XLSX and any(item.hidden for item in candidates):
            return decision(
                UNSUPPORTED,
                INSUFFICIENT_EVIDENCE,
                0.0,
                citation_coverage,
                ("xlsx_strict_wrapper_context_expansion",),
                "",
                (XLSX,),
                ("XLSX_HIDDEN_CONTENT",),
                "Hidden XLSX content is blocked from query, answer, gold, and candidate surfaces.",
                candidates,
                cited,
                best_trust,
            )

        if lane == XLSX and candidates and not all(xlsx_strict_wrapper_allowed(item) for item in candidates):
            return decision(
                UNSUPPORTED,
                INSUFFICIENT_EVIDENCE,
                0.0,
                citation_coverage,
                ("xlsx_strict_wrapper_context_expansion",),
                "",
                (XLSX,),
                ("NON_STRICT_XLSX_WRAPPER",),
                "XLSX answer recovery may use only the strict wrapper path.",
                candidates,
                cited,
                best_trust,
            )

        if metadata.get("local_llm_smoke_output"):
            return decision(
                NEEDS_RECOVERY,
                INSUFFICIENT_EVIDENCE,
                0.2,
                citation_coverage,
                ("deterministic_citation_check",),
                "",
                allowed_lanes_for(lane),
                ("LOCAL_LLM_SMOKE_PROMOTION_EVIDENCE",),
                "Local LLM smoke output is diagnostic-only and cannot be promotion evidence.",
                candidates,
                cited,
                best_trust,
            )

        if not candidates:
            return decision(
                NEEDS_RECOVERY,
                INSUFFICIENT_RETRIEVAL,
                0.0,
                0.0,
                ("query_rewrite", "top_k_expansion", "lane_rerouting"),
                "",
                allowed_lanes_for(lane),
                (),
                "No retrieved evidence candidates were available.",
                candidates,
                cited,
                best_trust,
            )

        if not cited:
            return decision(
                UNSUPPORTED,
                INSUFFICIENT_EVIDENCE,
                0.0,
                0.0,
                ("adjacent_context_expansion", "lane_specific_retrieval_loop"),
                "",
                allowed_lanes_for(lane),
                (),
                "No citation_text plus location_json support was available.",
                candidates,
                cited,
                best_trust,
            )

        if native_ocr_conflict(candidates):
            return decision(
                NEEDS_RECOVERY,
                CONFLICTING_EVIDENCE,
                0.55,
                citation_coverage,
                ("prefer_higher_trust_evidence", "report_native_ocr_conflict"),
                "",
                allowed_lanes_for(lane),
                (OCR_SHADOW,),
                "Native PDF text and OCR fallback conflict; native text must be preferred and the conflict reported.",
                candidates,
                cited,
                best_trust,
            )

        if all(item.is_shadow_diagnostic for item in candidates):
            return decision(
                NEEDS_RECOVERY,
                INSUFFICIENT_EVIDENCE,
                min(0.69, support_score(draft_answer, candidates, citation_coverage)),
                citation_coverage,
                ("diagnostic_hint_only", "retrieve_official_or_high_trust_evidence"),
                "",
                allowed_lanes_for(lane),
                tuple(sorted({item.lane for item in candidates})),
                "Diagnostic-only OCR/IDP/multimodal evidence cannot make an answer officially supported.",
                candidates,
                cited,
                best_trust,
            )

        if not clean(draft_answer) or len(clean(draft_answer)) < 20:
            return decision(
                NEEDS_RECOVERY,
                INSUFFICIENT_EVIDENCE,
                0.35,
                citation_coverage,
                ("adjacent_context_expansion", "lane_specific_retrieval_loop"),
                "",
                allowed_lanes_for(lane),
                (),
                "Draft answer is too short to be considered supported by the cited evidence.",
                candidates,
                cited,
                best_trust,
            )

        score = support_score(draft_answer, candidates, citation_coverage)
        return decision(
            SUPPORTED,
            "",
            score,
            citation_coverage,
            (),
            "",
            allowed_lanes_for(lane),
            (),
            "Answer has cited, non-diagnostic evidence and passes deterministic sufficiency checks.",
            candidates,
            cited,
            best_trust,
            official_support=True,
        )


@dataclass(frozen=True)
class RecoveryRoute:
    action: str
    target_lane: str
    clarification_question: str
    recovery_actions: tuple[str, ...]
    diagnostic_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "target_lane": self.target_lane,
            "clarification_question": self.clarification_question,
            "recovery_actions": list(self.recovery_actions),
            "diagnostic_reason": self.diagnostic_reason,
        }


class RecoveryPolicyRouter:
    """Maps sufficiency failures to clarification or bounded recovery."""

    def route(
        self,
        *,
        user_query: str,
        lane: str,
        decision: AnswerSufficiencyDecision,
    ) -> RecoveryRoute:
        lane = normalize_lane(lane)
        failure = decision.failure_type
        if decision.sufficiency_status == SUPPORTED:
            return RecoveryRoute(NOOP_SUPPORTED, lane, "", (), "Answer already supported.")
        if failure in {AMBIGUOUS_QUERY, NEEDS_USER_CONSTRAINT}:
            question = decision.required_followup_question or targeted_question(user_query, lane, failure)
            return RecoveryRoute(ASK_CLARIFICATION, lane, question, (), "Ask a targeted clarification question.")
        if failure == INSUFFICIENT_RETRIEVAL:
            return RecoveryRoute(
                AGENTIC_RETRIEVAL_LOOP,
                lane,
                "",
                ("query_rewrite", "top_k_expansion", "lane_rerouting"),
                "Invoke the bounded internal agentic retrieval loop.",
            )
        if failure == INSUFFICIENT_EVIDENCE:
            return RecoveryRoute(
                ADJACENT_CONTEXT_EXPANSION,
                lane,
                "",
                ("adjacent_context_expansion", "lane_specific_retrieval_loop"),
                "Expand adjacent context or rerun lane-specific retrieval under guardrails.",
            )
        if failure == LANE_MISMATCH:
            if len(decision.allowed_lanes) == 1:
                return RecoveryRoute(
                    LANE_REROUTE,
                    decision.allowed_lanes[0],
                    "",
                    ("lane_rerouting",),
                    "Reroute to the deterministic compatible lane.",
                )
            return RecoveryRoute(
                ASK_CLARIFICATION,
                lane,
                targeted_question(user_query, lane, failure),
                (),
                "Lane mismatch is not deterministic; ask the user to choose the route.",
            )
        if failure == CONFLICTING_EVIDENCE:
            return RecoveryRoute(
                PREFER_HIGHER_TRUST_EVIDENCE,
                lane,
                "",
                ("prefer_higher_trust_evidence", "report_conflict"),
                "Prefer higher-trust native evidence and surface the conflict.",
            )
        if failure == UNANSWERABLE_WITH_AVAILABLE_CONTEXT:
            return RecoveryRoute(
                GROUNDED_INSUFFICIENCY,
                lane,
                "",
                (),
                "Return a grounded insufficiency response.",
            )
        return RecoveryRoute(
            GROUNDED_INSUFFICIENCY,
            lane,
            "",
            (),
            "Fail closed with a grounded insufficiency response.",
        )


@dataclass(frozen=True)
class RecoveryGuardrails:
    max_iterations: int = 2
    max_query_rewrites: int = 3
    allow_broad_indexing: bool = False
    allow_unscoped: bool = False
    production_index_mutation: bool = False
    official_denominator_mutation: bool = False
    diagnostic_trace_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "max_query_rewrites": self.max_query_rewrites,
            "allow_broad_indexing": self.allow_broad_indexing,
            "allow_unscoped": self.allow_unscoped,
            "production_index_mutation": self.production_index_mutation,
            "official_denominator_mutation": self.official_denominator_mutation,
            "diagnostic_trace_required": self.diagnostic_trace_required,
        }


@dataclass(frozen=True)
class RecoveryLoopResult:
    action: str
    existing_loop_component: str
    existing_loop_invoked: bool
    recovered: bool
    loop_iterations: int
    query_rewrite_count: int
    stop_reason: str
    final_answer: str
    trace: tuple[Mapping[str, Any], ...]
    guardrails: RecoveryGuardrails

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "existing_loop_component": self.existing_loop_component,
            "existing_loop_invoked": self.existing_loop_invoked,
            "recovered": self.recovered,
            "loop_iterations": self.loop_iterations,
            "query_rewrite_count": self.query_rewrite_count,
            "stop_reason": self.stop_reason,
            "final_answer": self.final_answer,
            "trace": [dict(item) for item in self.trace],
            "guardrails": self.guardrails.to_dict(),
        }


RecoveryExecutor = Callable[[Any], tuple[str, list[RetrievedChunk], int]]


class AgenticRetrievalLoopAdapter:
    """Thin RAG guardrail wrapper around the existing AgentLoopController."""

    allowed_recovery_actions = (
        "query_rewrite",
        "lane_rerouting",
        "top_k_expansion",
        "adjacent_chunk_expansion",
        "adjacent_section_expansion",
        "adjacent_page_expansion",
        "xlsx_strict_wrapper_context_expansion",
        "pdf_native_text_context_expansion",
        "file_identity_clarification",
        "ocr_idp_multimodal_diagnostic_hints_only",
    )
    blocked_recovery_actions = (
        "broad_indexing",
        "production_index_mutation",
        "using_hidden_xlsx_content",
        "ocr_idp_multimodal_official_evidence",
        "pdf_file_lookup_as_content_evidence",
        "local_llm_smoke_as_promotion_evidence",
    )

    def __init__(self, guardrails: RecoveryGuardrails | None = None) -> None:
        self.guardrails = guardrails or RecoveryGuardrails()
        if self.guardrails.max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")

    def run(
        self,
        *,
        user_query: str,
        lane: str,
        route: RecoveryRoute,
        recovery_executor: RecoveryExecutor | None = None,
    ) -> RecoveryLoopResult:
        if route.action not in {AGENTIC_RETRIEVAL_LOOP, ADJACENT_CONTEXT_EXPANSION, LANE_REROUTE}:
            return RecoveryLoopResult(
                action=route.action,
                existing_loop_component="app.capabilities.agent.loop.AgentLoopController",
                existing_loop_invoked=False,
                recovered=False,
                loop_iterations=0,
                query_rewrite_count=0,
                stop_reason="not_invoked_for_route",
                final_answer="",
                trace=(),
                guardrails=self.guardrails,
            )

        parser = RegexQueryParser()
        controller = AgentLoopController(
            critic=RuleCritic(),
            rewriter=NoOpQueryRewriter(),
            parser=parser,
            budget=LoopBudget(
                max_iter=self.guardrails.max_iterations,
                max_total_ms=5_000,
                max_llm_tokens=4_000,
                min_confidence_to_stop=0.60,
            ),
        )
        executor = recovery_executor or empty_recovery_executor
        outcome = controller.run(
            question=user_query,
            initial_parsed_query=parser.parse(user_query),
            execute_fn=executor,
        )
        trace = loop_trace(outcome, lane=lane, route=route)
        rewrite_count = min(
            max(0, len(outcome.steps) - 1),
            self.guardrails.max_query_rewrites,
        )
        return RecoveryLoopResult(
            action=route.action,
            existing_loop_component="app.capabilities.agent.loop.AgentLoopController",
            existing_loop_invoked=True,
            recovered=bool(outcome.final_answer and outcome.aggregated_chunks and outcome.stop_reason == "converged"),
            loop_iterations=len(outcome.steps),
            query_rewrite_count=rewrite_count,
            stop_reason=outcome.stop_reason,
            final_answer=outcome.final_answer,
            trace=tuple(trace),
            guardrails=self.guardrails,
        )


def empty_recovery_executor(parsed_query: Any) -> tuple[str, list[RetrievedChunk], int]:
    del parsed_query
    return ("근거를 찾지 못했습니다.", [], 0)


def loop_trace(outcome: LoopOutcome, *, lane: str, route: RecoveryRoute) -> list[dict[str, Any]]:
    return [
        {
            "iter": step.iter,
            "lane": normalize_lane(lane),
            "route_action": route.action,
            "query": step.query.to_dict(),
            "retrieved_chunk_ids": list(step.retrieved_chunk_ids),
            "critique": step.critique.to_dict(),
            "guardrails": {
                "allow_broad_indexing": False,
                "allow_unscoped": False,
                "production_index_mutation": False,
                "official_denominator_mutation": False,
            },
        }
        for step in outcome.steps
    ]


def rank_candidates_by_trust(candidates: Sequence[AnswerEvidenceCandidate | Mapping[str, Any]]) -> list[AnswerEvidenceCandidate]:
    normalized = [AnswerEvidenceCandidate.from_any(item) for item in candidates]
    return sorted(
        normalized,
        key=lambda item: (
            TRUST_RANK.get(item.trust_tier, 0),
            item.confidence if item.confidence is not None else 0.0,
            1 if item.has_citation_support else 0,
        ),
        reverse=True,
    )


def decision(
    status: str,
    failure_type: str,
    score: float,
    citation_coverage: float,
    actions: Sequence[str],
    question: str,
    allowed_lanes: Sequence[str],
    blocked_lanes: Sequence[str],
    reason: str,
    candidates: Sequence[AnswerEvidenceCandidate],
    cited: Sequence[AnswerEvidenceCandidate],
    best_trust: str,
    *,
    official_support: bool = False,
) -> AnswerSufficiencyDecision:
    return AnswerSufficiencyDecision(
        sufficiency_status=status,
        failure_type=failure_type,
        support_score=round(float(score), 6),
        citation_coverage=round(float(citation_coverage), 6),
        recommended_recovery_actions=tuple(actions),
        required_followup_question=question,
        allowed_lanes=tuple(allowed_lanes),
        blocked_lanes=tuple(blocked_lanes),
        diagnostic_reason=reason,
        evidence_count=len(candidates),
        cited_evidence_count=len(cited),
        official_support=official_support,
        best_trust_tier=best_trust,
    )


def support_score(draft_answer: str, candidates: Sequence[AnswerEvidenceCandidate], citation_coverage: float) -> float:
    trust = max([TRUST_RANK.get(item.trust_tier, 0) for item in candidates] or [0]) / 100.0
    answer_part = min(len(clean(draft_answer)) / 160.0, 1.0) * 0.15
    count_part = min(len(candidates), 3) / 3.0 * 0.15
    return min(1.0, citation_coverage * 0.50 + trust * 0.20 + answer_part + count_part)


def allowed_lanes_for(lane: str) -> tuple[str, ...]:
    lane = normalize_lane(lane)
    if lane == PDF_FILE_LOOKUP:
        return (PDF_FILE_LOOKUP,)
    if lane == PDF_CONTENT:
        return (PDF_CONTENT, OCR_SHADOW)
    if lane == XLSX:
        return (XLSX,)
    if lane == TEXT:
        return (TEXT,)
    if lane in {OCR_SHADOW, IDP_SHADOW, MULTIMODAL_SHADOW}:
        return (lane,)
    return (lane,)


def targeted_question(user_query: str, lane: str, failure_type: str) -> str:
    del user_query
    lane = normalize_lane(lane)
    if lane == XLSX:
        return "어느 시트, 기간, 지표를 기준으로 확인할까요? 예: Sheet1의 2024년 매출 합계처럼 범위를 지정해 주세요."
    if lane == PDF_FILE_LOOKUP:
        return "파일 이름이나 시행일 기준으로 찾을까요, 아니면 PDF 본문 내용 기준으로 확인할까요?"
    if lane == PDF_CONTENT:
        return "어느 PDF 파일, 기간, 또는 섹션의 본문을 기준으로 확인할까요?"
    if lane == TEXT:
        return "어떤 작품명, 문서 제목, 또는 섹션을 기준으로 확인할까요?"
    if failure_type == LANE_MISMATCH:
        return "파일 식별자 기준인지, 본문 내용 기준인지 한 가지를 지정해 주세요."
    return "확인할 파일, 시트, 기간, 지표, 또는 문서 제목 중 하나를 지정해 주세요."


def is_ambiguous_query(query: str, lane: str, metadata: Mapping[str, Any]) -> bool:
    if metadata.get("has_user_constraint"):
        return False
    tokens = [part for part in clean(query).split() if part]
    if lane == XLSX and len(tokens) <= 2 and any(word in query for word in ("매출", "값", "합계", "표", "자료")):
        return True
    return False


def asks_for_content_answer(query: str, metadata: Mapping[str, Any]) -> bool:
    if metadata.get("answer_intent") in {"file_identity", "document_identity"}:
        return False
    if metadata.get("answer_intent") in {"content", "page", "bbox", "table", "row", "column", "value"}:
        return True
    joined = f"{query} {metadata.get('answer_shape', '')} {metadata.get('expected_answer_shape', '')}".lower()
    return any(marker.lower() in joined for marker in CONTENT_INTENT_MARKERS)


def xlsx_strict_wrapper_allowed(candidate: AnswerEvidenceCandidate) -> bool:
    if candidate.lane != XLSX and candidate.source_file_type.upper() not in {"SPREADSHEET", "XLSX", "XLSM"}:
        return True
    if "strict_wrapper" not in candidate.metadata:
        return True
    return as_bool(candidate.metadata.get("strict_wrapper"))


def native_ocr_conflict(candidates: Sequence[AnswerEvidenceCandidate]) -> bool:
    has_native = any(item.trust_tier == NATIVE_TEXT_HIGH for item in candidates)
    return has_native and any(
        item.trust_tier == OCR_MEDIUM and as_bool(item.metadata.get("native_text_conflict"))
        for item in candidates
    )


def normalize_lane(value: str) -> str:
    normalized = clean(value).upper()
    aliases = {
        "PDF": PDF_CONTENT,
        "PDF_CONTENT": PDF_CONTENT,
        "PDF_FILE": PDF_FILE_LOOKUP,
        "PDF_FILE_LOOKUP": PDF_FILE_LOOKUP,
        "SPREADSHEET": XLSX,
        "XLSM": XLSX,
        "XLSX": XLSX,
        "TEXT": TEXT,
    }
    return aliases.get(normalized, normalized or TEXT)


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def nested(data: Mapping[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current
