"""Optional LangGraph skeleton for query-time RAG orchestration.

The graph is still a feature-flagged POC. By default it uses fake vector tools;
callers may inject the existing RAG Retriever to exercise the real vector
adapter path. It does not register a public endpoint, call LangChain, or claim
production-grade pre-retrieval policy enforcement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Protocol

from app.capabilities.rag_orchestrator.answer_policy import (
    build_no_evidence_response,
    prepare_answer_handoff,
)
from app.capabilities.rag_orchestrator.citation_verify import citation_verify_tool
from app.capabilities.rag_orchestrator.evidence import (
    SOURCE_FILE_TYPE_SPREADSHEET,
    Evidence,
    QueryPolicy,
)
from app.capabilities.rag_orchestrator.evidence_merge import evidence_merge_tool
from app.capabilities.rag_orchestrator.state import (
    QueryOrchestratorState,
    forbidden_state_keys_present,
)
from app.capabilities.rag_orchestrator.tools import (
    FixtureMode,
    ToolResult,
    fake_pdf_vector_search_tool,
    fake_text_vector_search_tool,
    fake_xlsx_vector_search_tool,
)
from app.capabilities.rag_orchestrator.vector_tools import (
    pdf_vector_search_tool,
    text_vector_search_tool,
    xlsx_vector_search_tool,
)
from app.capabilities.rag_orchestrator.xlsx_tools import (
    xlsx_aggregation_tool,
    xlsx_table_materialize_fixture_tool,
)

try:  # pragma: no cover - availability is environment-dependent.
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - exercised when optional dependency is absent.
    END = "__end__"
    START = "__start__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False
else:  # pragma: no cover - import branch itself is trivial.
    LANGGRAPH_AVAILABLE = True

PDF_TOOL = "pdf"
XLSX_TOOL = "xlsx"
TEXT_TOOL = "text"
ALL_TOOLS = (PDF_TOOL, XLSX_TOOL, TEXT_TOOL)

TRACK_TEXT_NAMUWIKI_ANIMATION = "text_namuwiki_animation"
TRACK_XLSX_BUSINESS_STRUCTURED = "xlsx_business_structured"
TRACK_PDF_BUSINESS_OCR_MM = "pdf_business_ocr_mm"
TRACK_MULTI_ROUTE = "diagnostic_multi_route"
TRACK_POLICY_BLOCKED = "policy_blocked"
TRACK_INSUFFICIENT_METADATA = "insufficient_metadata"

ALL_TRACK_ROUTES = (
    TRACK_TEXT_NAMUWIKI_ANIMATION,
    TRACK_XLSX_BUSINESS_STRUCTURED,
    TRACK_PDF_BUSINESS_OCR_MM,
)
ALL_PRIMARY_ROUTES = (
    *ALL_TRACK_ROUTES,
    TRACK_MULTI_ROUTE,
    TRACK_POLICY_BLOCKED,
    TRACK_INSUFFICIENT_METADATA,
)
NON_RETRIEVAL_PRIMARY_ROUTES = (
    TRACK_POLICY_BLOCKED,
    TRACK_INSUFFICIENT_METADATA,
)
ROUTE_TO_TOOL = {
    TRACK_TEXT_NAMUWIKI_ANIMATION: TEXT_TOOL,
    TRACK_XLSX_BUSINESS_STRUCTURED: XLSX_TOOL,
    TRACK_PDF_BUSINESS_OCR_MM: PDF_TOOL,
}
TOOL_TO_ROUTE = {tool: route for route, tool in ROUTE_TO_TOOL.items()}
ROUTE_REQUIRED_EVIDENCE_TYPE = {
    TRACK_TEXT_NAMUWIKI_ANIMATION: "namuwiki_animation_text",
    TRACK_XLSX_BUSINESS_STRUCTURED: "spreadsheet_table_context",
    TRACK_PDF_BUSINESS_OCR_MM: "pdf_ocr_mm_layout_context",
}
MULTI_ROUTE_EVIDENCE_TYPE = "multi_track_evidence_bundle"
LOW_ROUTE_CONFIDENCE_THRESHOLD = 0.55

LANE_TEXT_NAMUWIKI_CANDIDATE_PREP = "text_namuwiki_candidate_prep"
LANE_XLSX_STRICT_EVIDENCE_CITATION = "xlsx_strict_evidence_citation"
LANE_PDF_CONTENT_EVIDENCE = "pdf_content_evidence_lane"
LANE_PDF_FILE_DOCUMENT_IDENTITY = "pdf_file_document_identity"
LANE_PDF_FILE_DOCUMENT_IDENTITY_BLOCKED = "pdf_file_document_identity_policy_blocked"

DENOMINATOR_SCOPE_BY_ROUTE = {
    TRACK_TEXT_NAMUWIKI_ANIMATION: (
        "text_namuwiki_bound_diagnostic_denominator_47_"
        "answer_citation_denominator_not_open"
    ),
    TRACK_XLSX_BUSINESS_STRUCTURED: (
        "xlsx_retrieval_evidence_diagnostic_denominator_23_"
        "answer_generation_denominator_0"
    ),
    TRACK_PDF_BUSINESS_OCR_MM: (
        "pdf_conservative_content_and_file_identity_denominators_separate_"
        "answer_denominator_0"
    ),
    TRACK_MULTI_ROUTE: "track_separate_diagnostic_multi_route_no_cross_track_denominator",
    TRACK_POLICY_BLOCKED: "policy_blocked_no_denominator_member",
    TRACK_INSUFFICIENT_METADATA: "insufficient_metadata_no_denominator_member",
}

LLM_ROUTE_SCHEMA_VERSION = "rag_route_adjudicator_v1"
LLM_PRIMARY_ROUTES = frozenset(ALL_PRIMARY_ROUTES)
LLM_INTENTS = frozenset(
    {
        "text_content",
        "xlsx_lookup",
        "xlsx_aggregation",
        "xlsx_date_number_format",
        "pdf_content_evidence",
        "pdf_file_identity",
        "ambiguous",
        "unknown",
    }
)
LLM_EVIDENCE_LANES = frozenset(
    {
        "text_content",
        "xlsx_structured_evidence",
        "pdf_content_evidence",
        "pdf_file_identity",
        "none",
    }
)
LLM_REQUIRED_FIELDS = frozenset(
    {
        "primary_route",
        "candidate_routes",
        "route_confidence",
        "intent",
        "evidence_lane",
        "requires_multi_route",
        "fallback_plan",
        "policy_flags",
        "blocked_flags",
        "diagnostic_only",
        "reason",
    }
)
LLM_UNSAFE_TRUTHY_FIELDS = (
    "official_success",
    "official_denominator_registry_changed",
    "official_denominator_opened_or_frozen",
    "official_denominator_mutated",
    "denominator_status_mutated",
    "promotion_evidence_created",
    "diagnostic_only_row_promoted",
    "production_namespace_mutated",
    "production_vector_written",
    "production_vector_index_mutated",
    "allowUnscoped",
    "allow_unscoped",
)

XLSX_PENDING_EVIDENCE_IDS = frozenset(
    {
        "gq_xlsx_date_number_format_003",
        "gq_xlsx_aggregation_001",
    }
)
PDF_POLICY_EXCLUDED_IDS = frozenset(
    {
        "pdf_file_lookup_content_anchor_004",
        "pdf_file_lookup_content_anchor_012",
        "pdf_file_lookup_content_anchor_013",
        "pdf_file_lookup_content_anchor_014",
        "pdf_file_lookup_content_anchor_015",
        "pdf_file_lookup_metadata_002",
    }
)
PDF_STABLE_IDENTITY_REQUIRED_IDS = frozenset(
    {
        "pdf_file_lookup_content_anchor_017",
        "pdf_file_lookup_content_anchor_018",
        "pdf_file_lookup_content_anchor_020",
    }
)
TEXT_NAMU_UNRESOLVED_IDS = frozenset(
    {
        "text_namu_v2_0006",
        "text_namu_v2_0010",
        "text_namu_v2_0013",
        "text_namu_v2_0019",
        "text_namu_v2_0020",
        "text_namu_v2_0023",
        "text_namu_v2_0024",
        "text_namu_v2_0027",
        "text_namu_v2_0029",
        "text_namu_v2_0031",
        "text_namu_v2_0033",
        "text_namu_v2_0043",
        "text_namu_v2_0044",
        "text_namu_v2_0066",
        "text_namu_v2_0067",
        "text_namu_v2_0078",
        "text_namu_v2_0080",
        "text_namu_v2_0082",
        "text_namu_v2_0091",
        "text_namu_v2_0092",
        "text_namu_v2_0093",
        "text_namu_v2_0094",
        "text_namu_v2_0095",
    }
)

INTENT_PDF = "pdf"
INTENT_XLSX = "xlsx"
INTENT_TEXT = "text"
INTENT_AGGREGATION = "aggregation"
INTENT_MIXED = "mixed"
INTENT_FALLBACK = "fallback"

_PDF_KEYWORDS = ("pdf",)
_XLSX_KEYWORDS = ("xlsx", "excel", "sheet", "표", "합계")
_TEXT_KEYWORDS = ("text", "txt", "plain text", "문서", "텍스트")
_AGGREGATION_KEYWORDS = ("합계", "sum", "average", "avg", "평균", "count", "개수")

_NAMU_TEXT_KEYWORDS = (
    "namu",
    "나무위키",
    "애니",
    "애니메이션",
    "작품",
    "캐릭터",
    "등장인물",
    "성우",
    "줄거리",
)
_XLSX_ROUTE_KEYWORDS = (
    "xlsx",
    "xls",
    "excel",
    "엑셀",
    "spreadsheet",
    "sheet",
    "시트",
    "셀",
    "행",
    "열",
    "표",
    "합계",
    "평균",
    "승차",
    "승객수",
)
_PDF_ROUTE_KEYWORDS = (
    "pdf",
    ".pdf",
    "페이지",
    "쪽",
    "bbox",
    "bounding box",
    "ocr",
    "문단",
    "캡션",
    "footnote",
    "각주",
)


@dataclass(frozen=True)
class RouteDecision:
    """Stable 3-track route decision passed through graph trace output."""

    route: str
    routes: tuple[str, ...]
    route_confidence: float
    reason: str
    required_evidence_type: str
    allow_fallback: bool
    fallback_routes: tuple[str, ...]
    multi_route: bool
    route_scores: Mapping[str, float] = field(default_factory=dict)
    deterministic_hints: tuple[str, ...] = ()
    deterministic_score_signals: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    metadata_guards: tuple[str, ...] = ()
    policy_guards: tuple[str, ...] = ()
    blocked_flags: tuple[str, ...] = ()
    evidence_assembly_lane: str = ""
    evidence_lane: str = "none"
    denominator_scope: str = ""
    diagnostic_only: bool = True
    official_denominator_registry_changed: bool = False
    official_denominator_opened_or_frozen: bool = False
    production_namespace_mutated: bool = False
    production_vector_written: bool = False
    diagnostic_only_row_promoted: bool = False
    pdf_lanes_aggregated: bool = False
    hidden_xlsx_exposed: bool = False
    policy_excluded_rows_counted_as_retrieval_failures: bool = False
    route_metrics_official: bool = False
    route_label_status: str = "missing_route_gold_labels"
    fallback_outcome_label_status: str = "missing_fallback_outcome_labels"
    llm_decision_used: bool = False
    llm_adjudicator_called: bool = False
    llm_adjudicator_output: Mapping[str, Any] = field(default_factory=dict)
    llm_validation_status: str = "not_called"
    ambiguity_reasons: tuple[str, ...] = ()
    post_retrieval_validation: str = "required"
    fallback_attempts: tuple[Mapping[str, Any], ...] = ()
    final_diagnostic_status: str = "routed"

    def __post_init__(self) -> None:
        if self.route not in ALL_PRIMARY_ROUTES:
            raise ValueError(f"unsupported route: {self.route!r}")
        for route in (*self.routes, *self.fallback_routes):
            if route not in ALL_TRACK_ROUTES:
                raise ValueError(f"unsupported route in route decision: {route!r}")
        if not (0.0 <= self.route_confidence <= 1.0):
            raise ValueError("route_confidence must be in [0.0, 1.0]")
        object.__setattr__(
            self,
            "route_scores",
            {
                route: round(float(self.route_scores.get(route, 0.0)), 4)
                for route in ALL_TRACK_ROUTES
            },
        )
        object.__setattr__(
            self,
            "deterministic_score_signals",
            {
                route: tuple(self.deterministic_score_signals.get(route, ()))
                for route in ALL_TRACK_ROUTES
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "primary_route": self.route,
            "routes": list(self.routes),
            "candidate_routes": list(self.routes),
            "route_confidence": round(float(self.route_confidence), 4),
            "reason": self.reason,
            "required_evidence_type": self.required_evidence_type,
            "allow_fallback": self.allow_fallback,
            "fallback_routes": list(self.fallback_routes),
            "fallback_plan": list(self.fallback_routes),
            "multi_route": self.multi_route,
            "route_scores": dict(self.route_scores),
            "deterministic_hints": list(self.deterministic_hints),
            "deterministic_score_signals": {
                route: list(signals)
                for route, signals in self.deterministic_score_signals.items()
            },
            "metadata_guards": list(self.metadata_guards),
            "policy_guards": list(self.policy_guards),
            "blocked_flags": list(self.blocked_flags),
            "evidence_assembly_lane": self.evidence_assembly_lane,
            "evidence_lane": self.evidence_lane,
            "denominator_scope": self.denominator_scope,
            "route_result_diagnostic_only": self.diagnostic_only,
            "diagnostic_only": self.diagnostic_only,
            "official_denominator_registry_changed": self.official_denominator_registry_changed,
            "official_denominator_registry_mutated": self.official_denominator_registry_changed,
            "official_denominator_opened_or_frozen": self.official_denominator_opened_or_frozen,
            "production_namespace_mutated": self.production_namespace_mutated,
            "production_vector_written": self.production_vector_written,
            "production_vector_index_mutated": self.production_vector_written,
            "diagnostic_only_row_promoted": self.diagnostic_only_row_promoted,
            "pdf_lanes_aggregated": self.pdf_lanes_aggregated,
            "hidden_xlsx_exposed": self.hidden_xlsx_exposed,
            "policy_excluded_rows_counted_as_retrieval_failures": (
                self.policy_excluded_rows_counted_as_retrieval_failures
            ),
            "route_metrics_official": self.route_metrics_official,
            "route_label_status": self.route_label_status,
            "fallback_outcome_label_status": self.fallback_outcome_label_status,
            "llm_decision_used": self.llm_decision_used,
            "llm_adjudicator_called": self.llm_adjudicator_called,
            "llm_adjudicator_output": dict(self.llm_adjudicator_output),
            "llm_validation_status": self.llm_validation_status,
            "ambiguity_reasons": list(self.ambiguity_reasons),
            "post_retrieval_validation": self.post_retrieval_validation,
            "fallback_attempts": [dict(item) for item in self.fallback_attempts],
            "fallback_attempt_count": len(self.fallback_attempts),
            "final_diagnostic_status": self.final_diagnostic_status,
        }

    def to_diagnostic(self, *, query_id: str, query: str = "") -> dict[str, Any]:
        return {
            "query_id": query_id,
            "safe_query_text": _safe_query_text(query),
            "primary_route": self.route,
            "selected_primary_route": self.route,
            "candidate_routes": list(self.routes),
            "route_scores": dict(self.route_scores),
            "fallback_routes": list(self.fallback_routes),
            "fallback_plan": list(self.fallback_routes),
            "route_reason": self.reason,
            "selected_route_reason": self.reason,
            "deterministic_hints_used": list(self.deterministic_hints),
            "deterministic_score_signals": {
                route: list(signals)
                for route, signals in self.deterministic_score_signals.items()
            },
            "metadata_guards_applied": list(self.metadata_guards),
            "policy_guards_applied": list(self.policy_guards),
            "blocked_flags": list(self.blocked_flags),
            "route_result_diagnostic_only": self.diagnostic_only,
            "diagnostic_only": self.diagnostic_only,
            "evidence_assembly_lane": self.evidence_assembly_lane,
            "evidence_lane": self.evidence_lane,
            "llm_adjudicator_called": self.llm_adjudicator_called,
            "llm_adjudicator_output": dict(self.llm_adjudicator_output),
            "llm_validation_status": self.llm_validation_status,
            "ambiguity_reasons": list(self.ambiguity_reasons),
            "denominator_scope": self.denominator_scope,
            "official_denominator_registry_changed": self.official_denominator_registry_changed,
            "official_denominator_registry_mutated": self.official_denominator_registry_changed,
            "official_denominator_opened_or_frozen": self.official_denominator_opened_or_frozen,
            "production_namespace_mutated": self.production_namespace_mutated,
            "production_vector_written": self.production_vector_written,
            "production_vector_index_mutated": self.production_vector_written,
            "diagnostic_only_row_promoted": self.diagnostic_only_row_promoted,
            "pdf_lanes_aggregated": self.pdf_lanes_aggregated,
            "hidden_xlsx_exposed": self.hidden_xlsx_exposed,
            "policy_excluded_rows_counted_as_retrieval_failures": (
                self.policy_excluded_rows_counted_as_retrieval_failures
            ),
            "fallback_attempts": [dict(item) for item in self.fallback_attempts],
            "fallback_attempt_count": len(self.fallback_attempts),
            "final_diagnostic_status": self.final_diagnostic_status,
            "route_metrics_official": self.route_metrics_official,
            "route_label_status": self.route_label_status,
            "fallback_outcome_label_status": self.fallback_outcome_label_status,
        }


class RouteAdjudicator(Protocol):
    """Injectable diagnostic LLM route adjudicator.

    Implementations must return a JSON object shape. The graph validates that
    object before any route decision can use it.
    """

    def adjudicate(self, payload: Mapping[str, Any]) -> Mapping[str, Any] | str:
        ...


class LlmChatRouteAdjudicator:
    """Small adapter from the shared chat provider to route JSON adjudication."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    def adjudicate(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        from app.clients.llm_chat import ChatMessage

        return self._provider.chat_json(
            [
                ChatMessage(
                    role="system",
                    content=(
                        "You are a diagnostic-only RAG route adjudicator. "
                        "Return strict JSON only. Do not expose hidden/private "
                        "content. Deterministic hard guards are code-owned and "
                        "cannot be overridden."
                    ),
                ),
                ChatMessage(
                    role="user",
                    content=json.dumps(payload, ensure_ascii=False, sort_keys=True),
                ),
            ],
            schema_hint=LLM_ROUTE_SCHEMA_VERSION,
            max_tokens=512,
            temperature=0.0,
            timeout_s=15.0,
        )


class LangGraphUnavailableError(RuntimeError):
    """Raised when graph compilation is requested without LangGraph installed."""


def build_route_decision(
    *,
    query: str,
    policy: QueryPolicy | None = None,
    source_metadata: dict[str, Any] | None = None,
    llm_suggested_routes: Iterable[str] | None = None,
    route_adjudicator: RouteAdjudicator | None = None,
) -> RouteDecision:
    """Choose a guarded 3-track route for a query.

    Hard guards run first. Rule scores then choose a route. The optional LLM
    adjudicator is diagnostic-only and can only run when the scored route is
    ambiguous; its validated JSON can narrow inside the guarded route set but
    cannot relax guards or mutate denominator/promotion state.
    """

    allowed_routes, guard_reasons = _allowed_routes_from_policy_and_metadata(
        policy=policy,
        source_metadata=source_metadata,
    )
    guard = _hard_guard_result(
        query_id=_metadata_query_id(policy=policy, source_metadata=source_metadata),
        source_metadata=source_metadata,
        allowed_routes=allowed_routes,
    )
    score_result = _score_routes(
        query=query,
        policy=policy,
        source_metadata=source_metadata,
        allowed_routes=allowed_routes,
    )
    deterministic_routes, deterministic_hints = _deterministic_route_hints(query)
    llm_routes = _clean_routes(llm_suggested_routes)
    llm_only = bool(llm_routes and not deterministic_routes)

    reason_parts: list[str] = []
    if deterministic_hints:
        reason_parts.append("deterministic hints selected source track")
    if llm_only:
        reason_parts.append("LLM route suggestion kept inside metadata guard")
    if guard_reasons:
        reason_parts.append("metadata/source-type guard applied")

    candidate_routes = deterministic_routes or llm_routes or score_result["routes"]
    llm_used = llm_only
    policy_metadata_conflict = "policy_source_metadata_conflict" in guard_reasons
    if not allowed_routes:
        routes = ()
        route = TRACK_POLICY_BLOCKED if policy_metadata_conflict else TRACK_INSUFFICIENT_METADATA
        multi_route = False
        confidence = 0.0
        reason_parts.append("metadata/source-type guard blocked retrieval")
    else:
        if candidate_routes:
            guarded_routes = _intersect_routes(candidate_routes, allowed_routes)
            if guarded_routes:
                routes = guarded_routes
                if deterministic_routes and len(routes) == 1:
                    confidence = 0.9
                elif llm_only and len(routes) == 1:
                    confidence = 0.52
                elif not deterministic_routes and not llm_routes:
                    confidence = 0.35
                else:
                    confidence = 0.78
            else:
                routes = allowed_routes
                confidence = 0.45
                reason_parts.append("guard overrode conflicting route signal")
        else:
            routes = allowed_routes
            confidence = 0.35
            reason_parts.append("no strong source hint; schedule guarded multi-route retrieval")

        routes = _dedupe_routes(routes)
        multi_route = len(routes) > 1
        route = TRACK_MULTI_ROUTE if multi_route else routes[0]
        if guard["blocked_flags"]:
            route = guard["primary_route"]
            routes = _dedupe_routes(routes or allowed_routes)
            multi_route = False
            confidence = 0.0
            reason_parts.append("deterministic hard guard blocked retrieval")

    ambiguity_reasons = (
        ()
        if route in NON_RETRIEVAL_PRIMARY_ROUTES
        else _ambiguity_reasons(
            query=query,
            routes=routes,
            score_result=score_result,
            source_metadata=source_metadata,
            allowed_routes=allowed_routes,
        )
    )
    llm_payload: dict[str, Any] = {}
    llm_validation_status = "not_called"
    llm_output: dict[str, Any] = {}
    llm_blocked_flags: tuple[str, ...] = ()
    llm_called = False
    if route_adjudicator is not None and ambiguity_reasons and not guard["blocked_flags"]:
        llm_payload = _llm_adjudicator_payload(
            query=query,
            routes=routes,
            allowed_routes=allowed_routes,
            score_result=score_result,
            ambiguity_reasons=ambiguity_reasons,
            policy_guards=guard["policy_flags"],
            blocked_flags=guard["blocked_flags"],
        )
        llm_called = True
        validation = _call_and_validate_llm_adjudicator(
            route_adjudicator=route_adjudicator,
            payload=llm_payload,
            allowed_routes=allowed_routes,
        )
        llm_validation_status = validation["status"]
        llm_output = validation["output"]
        llm_blocked_flags = tuple(validation["blocked_flags"])
        if validation["status"] == "valid":
            llm_used = True
            reason_parts.append("validated diagnostic LLM adjudicator narrowed ambiguous route")
            route = validation["primary_route"]
            routes = validation["candidate_routes"]
            confidence = validation["route_confidence"]
            multi_route = route == TRACK_MULTI_ROUTE
            if route in NON_RETRIEVAL_PRIMARY_ROUTES:
                routes = validation["candidate_routes"]
                confidence = min(confidence, 0.0 if route == TRACK_POLICY_BLOCKED else confidence)
            fallback_routes = validation["fallback_plan"]
            evidence_lane = validation["evidence_lane"]
        else:
            reason_parts.append("invalid LLM adjudicator output ignored")
            fallback_routes = ()
            evidence_lane = ""
    else:
        fallback_routes = ()
        evidence_lane = ""

    if not llm_used:
        evidence_lane = _schema_evidence_lane(
            route=route,
            routes=routes,
            source_metadata=source_metadata,
        )

    fallback_routes = (
        fallback_routes
        or (
            tuple(route for route in allowed_routes if route not in routes)
            if confidence < LOW_ROUTE_CONFIDENCE_THRESHOLD
            and not multi_route
            and route not in NON_RETRIEVAL_PRIMARY_ROUTES
            else ()
        )
    )
    allow_fallback = bool(fallback_routes)
    required_evidence_type = _required_evidence_type(route=route, routes=routes)
    evidence_assembly_lane = _evidence_assembly_lane(
        route=route,
        routes=routes,
        source_metadata=source_metadata,
        evidence_lane=evidence_lane,
    )
    policy_guards = _policy_guards(
        route=route,
        routes=routes,
        confidence=confidence,
        evidence_assembly_lane=evidence_assembly_lane,
        source_metadata=source_metadata,
        extra_policy_flags=guard["policy_flags"],
    )
    conflict_flags = ("policy_source_metadata_conflict",) if policy_metadata_conflict else ()
    blocked_flags = _dedupe((*guard["blocked_flags"], *llm_blocked_flags, *conflict_flags))
    reason = "; ".join(reason_parts) or "deterministic source-type route"
    return RouteDecision(
        route=route,
        routes=routes,
        route_confidence=confidence,
        reason=reason,
        required_evidence_type=required_evidence_type,
        allow_fallback=allow_fallback,
        fallback_routes=fallback_routes,
        multi_route=multi_route,
        route_scores=score_result["scores"],
        deterministic_hints=deterministic_hints,
        deterministic_score_signals=score_result["signals"],
        metadata_guards=tuple(guard_reasons),
        policy_guards=policy_guards,
        blocked_flags=blocked_flags,
        evidence_assembly_lane=evidence_assembly_lane,
        evidence_lane=evidence_lane,
        denominator_scope=DENOMINATOR_SCOPE_BY_ROUTE[route],
        llm_decision_used=llm_used,
        llm_adjudicator_called=llm_called,
        llm_adjudicator_output=llm_output,
        llm_validation_status=llm_validation_status,
        ambiguity_reasons=ambiguity_reasons,
        final_diagnostic_status=(
            "policy_blocked"
            if route == TRACK_POLICY_BLOCKED
            else "insufficient_metadata"
            if route == TRACK_INSUFFICIENT_METADATA
            else TRACK_MULTI_ROUTE
            if route == TRACK_MULTI_ROUTE
            else "routed"
        ),
    )


def _required_evidence_type(*, route: str, routes: tuple[str, ...]) -> str:
    if route == TRACK_MULTI_ROUTE:
        return MULTI_ROUTE_EVIDENCE_TYPE
    if route == TRACK_POLICY_BLOCKED:
        return "policy_blocked"
    if route == TRACK_INSUFFICIENT_METADATA:
        return "insufficient_metadata"
    selected = routes[0] if routes else route
    return ROUTE_REQUIRED_EVIDENCE_TYPE[selected]


def _hard_guard_result(
    *,
    query_id: str,
    source_metadata: Mapping[str, Any] | None,
    allowed_routes: tuple[str, ...],
) -> dict[str, Any]:
    policy_flags = [
        "diagnostic_only",
        "no_official_denominator_mutation",
        "no_production_namespace_or_vector_mutation",
        "no_diagnostic_only_promotion",
    ]
    blocked_flags: list[str] = []
    primary_route = TRACK_POLICY_BLOCKED

    if TRACK_XLSX_BUSINESS_STRUCTURED in allowed_routes:
        if _metadata_hidden_or_excluded(source_metadata):
            blocked_flags.append("hidden_xlsx_content_blocked")
        if query_id in XLSX_PENDING_EVIDENCE_IDS:
            policy_flags.append("xlsx_pending_evidence_excluded_from_gold_v0_1")

    if TRACK_PDF_BUSINESS_OCR_MM in allowed_routes:
        if _is_pdf_file_identity_lane(source_metadata) and not _has_stable_pdf_identity(source_metadata):
            blocked_flags.append("stable_identity_required")
        if query_id in PDF_POLICY_EXCLUDED_IDS:
            blocked_flags.append("pdf_policy_excluded_row")
        if query_id in PDF_STABLE_IDENTITY_REQUIRED_IDS:
            blocked_flags.append("stable_identity_required")

    if TRACK_TEXT_NAMUWIKI_ANIMATION in allowed_routes and query_id in TEXT_NAMU_UNRESOLVED_IDS:
        policy_flags.append("text_namu_unresolved_carry_forward_excluded_from_gold_v0_1")
        policy_flags.append("text_namu_resolution_attempted_false")

    if not allowed_routes:
        blocked_flags.append("insufficient_metadata")
        primary_route = TRACK_INSUFFICIENT_METADATA

    return {
        "primary_route": primary_route,
        "policy_flags": tuple(_dedupe(policy_flags)),
        "blocked_flags": tuple(_dedupe(blocked_flags)),
    }


def _score_routes(
    *,
    query: str,
    policy: QueryPolicy | None,
    source_metadata: Mapping[str, Any] | None,
    allowed_routes: tuple[str, ...],
) -> dict[str, Any]:
    del policy
    scores = {route: 0.0 for route in ALL_TRACK_ROUTES}
    signals: dict[str, list[str]] = {route: [] for route in ALL_TRACK_ROUTES}
    lowered = (query or "").lower()

    def add(route: str, amount: float, signal: str) -> None:
        scores[route] = min(1.0, scores[route] + amount)
        signals[route].append(signal)

    for route, keyword_set, signal in (
        (TRACK_PDF_BUSINESS_OCR_MM, _PDF_ROUTE_KEYWORDS, "query_pdf_signal"),
        (TRACK_XLSX_BUSINESS_STRUCTURED, _XLSX_ROUTE_KEYWORDS, "query_xlsx_signal"),
        (TRACK_TEXT_NAMUWIKI_ANIMATION, _NAMU_TEXT_KEYWORDS, "query_namuwiki_signal"),
    ):
        if _has_keyword(lowered, keyword_set):
            add(route, 0.55, signal)

    if _has_keyword(lowered, _AGGREGATION_KEYWORDS):
        add(TRACK_XLSX_BUSINESS_STRUCTURED, 0.2, "query_aggregation_signal")

    metadata = source_metadata if isinstance(source_metadata, Mapping) else {}
    metadata_routes = _routes_for_source_types(
        [
            str(
                metadata.get("source_file_type")
                or metadata.get("sourceFileType")
                or metadata.get("file_type")
                or metadata.get("mime_type")
                or metadata.get("mimeType")
                or ""
            )
        ]
    )
    for route in metadata_routes:
        add(route, 0.7, "metadata_source_type_signal")

    parser_version = _metadata_text(metadata, "parser_version", "parserVersion").lower()
    if "xlsx" in parser_version:
        add(TRACK_XLSX_BUSINESS_STRUCTURED, 0.45, "metadata_parser_xlsx_signal")
    if "pdf" in parser_version:
        add(TRACK_PDF_BUSINESS_OCR_MM, 0.45, "metadata_parser_pdf_signal")
    if "text" in parser_version or "namu" in parser_version:
        add(TRACK_TEXT_NAMUWIKI_ANIMATION, 0.45, "metadata_parser_text_signal")

    location = metadata.get("location_json") or metadata.get("locationJson")
    if isinstance(location, Mapping):
        if _has_any(location, ("sheetName", "sheet_name", "cellRange", "cell_range", "tableId", "table_id")):
            add(TRACK_XLSX_BUSINESS_STRUCTURED, 0.45, "location_xlsx_locator_signal")
        if _has_any(location, ("page", "page_no", "pageNo", "bbox", "physical_page_index")):
            add(TRACK_PDF_BUSINESS_OCR_MM, 0.45, "location_pdf_locator_signal")

    citation_text = _metadata_text(metadata, "citation_text", "citationText").lower()
    if ".xlsx" in citation_text or "!" in citation_text:
        add(TRACK_XLSX_BUSINESS_STRUCTURED, 0.35, "citation_xlsx_signal")
    if ".pdf" in citation_text or " p." in citation_text:
        add(TRACK_PDF_BUSINESS_OCR_MM, 0.35, "citation_pdf_signal")

    for route in set(ALL_TRACK_ROUTES) - set(allowed_routes):
        signals[route].append("not_allowed_by_policy_or_metadata")
        scores[route] = min(scores[route], 0.05)

    ordered = sorted(
        allowed_routes,
        key=lambda route: (-scores[route], ALL_TRACK_ROUTES.index(route)),
    )
    if not ordered:
        routes = ()
    elif scores[ordered[0]] <= 0.05:
        routes = allowed_routes
    else:
        top_score = scores[ordered[0]]
        close = tuple(route for route in ordered if top_score - scores[route] <= 0.15)
        routes = close if len(close) > 1 else (ordered[0],)

    return {
        "scores": {route: round(scores[route], 4) for route in ALL_TRACK_ROUTES},
        "signals": {
            route: tuple(_dedupe(signals[route])) for route in ALL_TRACK_ROUTES
        },
        "routes": _dedupe_routes(routes),
    }


def _ambiguity_reasons(
    *,
    query: str,
    routes: tuple[str, ...],
    score_result: Mapping[str, Any],
    source_metadata: Mapping[str, Any] | None,
    allowed_routes: tuple[str, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    scores = score_result.get("scores") or {}
    allowed_scores = [
        float(scores.get(route, 0.0)) for route in allowed_routes
    ]
    sorted_scores = sorted(allowed_scores, reverse=True)
    if len(routes) > 1:
        reasons.append("multiple_scored_routes")
    if len(sorted_scores) > 1 and sorted_scores[0] - sorted_scores[1] <= 0.15:
        reasons.append("close_route_scores")
    if _short_or_underspecified_query(query):
        reasons.append("short_or_underspecified_query")
    if _is_pdf_file_identity_lane(source_metadata) and not _has_stable_pdf_identity(source_metadata):
        reasons.append("pdf_file_identity_unclear")
    route_set = set(routes)
    if {
        TRACK_TEXT_NAMUWIKI_ANIMATION,
        TRACK_PDF_BUSINESS_OCR_MM,
    }.issubset(route_set):
        reasons.append("text_pdf_content_unclear")
    return tuple(_dedupe(reasons))


def _short_or_underspecified_query(query: str) -> bool:
    text = " ".join((query or "").split())
    if len(text) <= 8:
        return True
    return len(text.split()) <= 2 and not any(ch.isdigit() for ch in text)


def _llm_adjudicator_payload(
    *,
    query: str,
    routes: tuple[str, ...],
    allowed_routes: tuple[str, ...],
    score_result: Mapping[str, Any],
    ambiguity_reasons: tuple[str, ...],
    policy_guards: tuple[str, ...],
    blocked_flags: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "schema_version": LLM_ROUTE_SCHEMA_VERSION,
        "diagnostic_only": True,
        "safe_query_text": _safe_query_text(query),
        "allowed_routes": list(allowed_routes),
        "candidate_routes": list(routes or allowed_routes),
        "route_scores": dict(score_result.get("scores") or {}),
        "deterministic_score_signals": {
            route: list(values)
            for route, values in (score_result.get("signals") or {}).items()
        },
        "ambiguity_reasons": list(ambiguity_reasons),
        "hard_policy_guards": list(policy_guards),
        "hard_blocked_flags": list(blocked_flags),
        "valid_primary_routes": list(ALL_PRIMARY_ROUTES),
        "valid_intents": sorted(LLM_INTENTS),
        "valid_evidence_lanes": sorted(LLM_EVIDENCE_LANES),
        "policy": {
            "llm_can_override_hard_guards": False,
            "llm_can_mark_official_success": False,
            "llm_can_mutate_denominator": False,
            "llm_can_promote_rows": False,
            "allow_unscoped_retrieval": False,
            "max_fallback_attempts": 1,
        },
    }


def _call_and_validate_llm_adjudicator(
    *,
    route_adjudicator: RouteAdjudicator,
    payload: Mapping[str, Any],
    allowed_routes: tuple[str, ...],
) -> dict[str, Any]:
    try:
        raw = route_adjudicator.adjudicate(payload)
    except Exception as ex:
        return {
            "status": "invalid",
            "output": {"error": "llm_adjudicator_error", "type": type(ex).__name__},
            "blocked_flags": ("llm_adjudicator_error",),
        }
    parsed, json_error = _parse_llm_raw_output(raw)
    if json_error:
        return {
            "status": "invalid",
            "output": {"error": json_error},
            "blocked_flags": (json_error,),
        }

    errors = _validate_llm_adjudication(parsed, allowed_routes=allowed_routes)
    output = _sanitize_llm_output(parsed)
    if errors:
        return {
            "status": "invalid",
            "output": output,
            "blocked_flags": tuple(errors),
        }

    primary_route = str(parsed["primary_route"])
    candidate_routes = _clean_routes(parsed.get("candidate_routes"))
    if primary_route in ALL_TRACK_ROUTES:
        candidate_routes = (primary_route,)
    elif primary_route == TRACK_MULTI_ROUTE and not candidate_routes:
        candidate_routes = allowed_routes
    confidence = max(0.0, min(1.0, float(parsed["route_confidence"])))
    return {
        "status": "valid",
        "output": output,
        "blocked_flags": (),
        "primary_route": primary_route,
        "candidate_routes": candidate_routes,
        "route_confidence": confidence,
        "evidence_lane": str(parsed["evidence_lane"]),
        "fallback_plan": _clean_routes(parsed.get("fallback_plan")),
    }


def _parse_llm_raw_output(raw: Mapping[str, Any] | str) -> tuple[dict[str, Any], str | None]:
    if isinstance(raw, Mapping):
        return dict(raw), None
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}, "invalid_llm_json"
        if isinstance(parsed, Mapping):
            return dict(parsed), None
    return {}, "invalid_llm_json"


def _validate_llm_adjudication(
    data: Mapping[str, Any],
    *,
    allowed_routes: tuple[str, ...],
) -> tuple[str, ...]:
    errors: list[str] = []
    missing = sorted(LLM_REQUIRED_FIELDS - set(data))
    if missing:
        errors.extend(f"llm_missing_{field}" for field in missing)
        return tuple(errors)
    primary_route = data.get("primary_route")
    if primary_route not in LLM_PRIMARY_ROUTES:
        errors.append("llm_primary_route_invalid")
    candidate_routes = _clean_routes(data.get("candidate_routes"))
    if any(route not in allowed_routes for route in candidate_routes):
        errors.append("llm_candidate_route_not_allowed")
    if primary_route in ALL_TRACK_ROUTES and primary_route not in allowed_routes:
        errors.append("llm_primary_route_not_allowed")
    try:
        confidence = float(data.get("route_confidence"))
    except (TypeError, ValueError):
        errors.append("llm_route_confidence_invalid")
    else:
        if not (0.0 <= confidence <= 1.0):
            errors.append("llm_route_confidence_invalid")
    if data.get("intent") not in LLM_INTENTS:
        errors.append("llm_intent_invalid")
    if data.get("evidence_lane") not in LLM_EVIDENCE_LANES:
        errors.append("llm_evidence_lane_invalid")
    for field in ("requires_multi_route", "diagnostic_only"):
        if not isinstance(data.get(field), bool):
            errors.append(f"llm_{field}_invalid")
    if data.get("diagnostic_only") is not True:
        errors.append("llm_diagnostic_only_must_be_true")
    for field in ("fallback_plan", "policy_flags", "blocked_flags"):
        if not isinstance(data.get(field), list) or not all(
            isinstance(item, str) for item in data.get(field, [])
        ):
            errors.append(f"llm_{field}_invalid")
    if data.get("blocked_flags") and primary_route not in {
        TRACK_POLICY_BLOCKED,
        TRACK_INSUFFICIENT_METADATA,
    }:
        errors.append("llm_blocked_flags_require_blocked_route")
    if primary_route == TRACK_MULTI_ROUTE and data.get("requires_multi_route") is not True:
        errors.append("llm_multi_route_requires_flag")
    if not isinstance(data.get("reason"), str) or not data.get("reason", "").strip():
        errors.append("llm_reason_invalid")
    for field in LLM_UNSAFE_TRUTHY_FIELDS:
        if _truthy(data.get(field)):
            errors.append(f"llm_unsafe_{field}")
    if "hidden" in str(data.get("reason", "")).lower():
        errors.append("llm_reason_may_expose_hidden_content")
    return tuple(_dedupe(errors))


def _sanitize_llm_output(data: Mapping[str, Any]) -> dict[str, Any]:
    output = {
        "primary_route": data.get("primary_route"),
        "candidate_routes": list(_clean_routes(data.get("candidate_routes"))),
        "route_confidence": _safe_float(data.get("route_confidence")),
        "intent": data.get("intent"),
        "evidence_lane": data.get("evidence_lane"),
        "requires_multi_route": bool(data.get("requires_multi_route")),
        "fallback_plan": list(_clean_routes(data.get("fallback_plan"))),
        "policy_flags": _safe_string_list(data.get("policy_flags")),
        "blocked_flags": _safe_string_list(data.get("blocked_flags")),
        "diagnostic_only": data.get("diagnostic_only"),
        "reason": _safe_reason(data.get("reason")),
    }
    return output


def _schema_evidence_lane(
    *,
    route: str,
    routes: tuple[str, ...],
    source_metadata: Mapping[str, Any] | None,
) -> str:
    if _is_pdf_file_identity_lane(source_metadata):
        return "pdf_file_identity"
    if route == TRACK_TEXT_NAMUWIKI_ANIMATION:
        return "text_content"
    if route == TRACK_XLSX_BUSINESS_STRUCTURED:
        return "xlsx_structured_evidence"
    if route == TRACK_PDF_BUSINESS_OCR_MM:
        return (
            "pdf_file_identity"
            if _is_pdf_file_identity_lane(source_metadata)
            else "pdf_content_evidence"
        )
    if route == TRACK_MULTI_ROUTE:
        return "none"
    return "none"


def _metadata_query_id(
    *,
    policy: QueryPolicy | None,
    source_metadata: Mapping[str, Any] | None,
) -> str:
    metadata = source_metadata if isinstance(source_metadata, Mapping) else {}
    value = (
        metadata.get("query_id")
        or metadata.get("queryId")
        or metadata.get("gold_query_id")
        or metadata.get("goldQueryId")
        or metadata.get("row_id")
        or metadata.get("rowId")
        or (policy.request_id if isinstance(policy, QueryPolicy) else "")
    )
    return str(value or "").strip()


def _safe_query_text(query: str, *, max_chars: int = 160) -> str:
    text = " ".join((query or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _safe_reason(value: Any, *, max_chars: int = 160) -> str:
    text = " ".join(str(value or "").split())
    text = text.replace("hidden", "[redacted]").replace("Hidden", "[redacted]")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _safe_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_reason(item, max_chars=80) for item in value if isinstance(item, str)]


def _safe_float(value: Any) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0.0


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _allowed_routes_from_policy_and_metadata(
    *,
    policy: QueryPolicy | None,
    source_metadata: dict[str, Any] | None,
) -> tuple[tuple[str, ...], list[str]]:
    allowed = set(ALL_TRACK_ROUTES)
    reasons: list[str] = []
    if isinstance(policy, QueryPolicy):
        policy_routes = set(_routes_for_source_types(policy.allowed_source_file_types))
        if policy_routes and policy_routes != allowed:
            allowed &= policy_routes
            reasons.append(
                "policy.allowed_source_file_types="
                + ",".join(policy.allowed_source_file_types)
            )

    metadata = source_metadata or {}
    metadata_type = (
        metadata.get("source_file_type")
        or metadata.get("sourceFileType")
        or metadata.get("file_type")
        or metadata.get("mime_type")
        or metadata.get("mimeType")
    )
    metadata_routes = set(_routes_for_source_types([str(metadata_type)])) if metadata_type else set()
    if metadata_routes:
        allowed &= metadata_routes
        reasons.append(f"source_metadata.source_file_type={metadata_type}")

    if not allowed:
        return (), reasons + ["policy_source_metadata_conflict"]
    ordered = tuple(route for route in ALL_TRACK_ROUTES if route in allowed)
    return ordered, reasons


def _routes_for_source_types(source_types: Iterable[str]) -> tuple[str, ...]:
    routes: list[str] = []
    for value in source_types:
        text = str(value or "").strip().upper()
        if text in {"PDF", "APPLICATION/PDF", "APPLICATION/X-PDF"}:
            routes.append(TRACK_PDF_BUSINESS_OCR_MM)
        elif text in {
            "SPREADSHEET",
            "XLSX",
            "XLS",
            "XLSM",
            "APPLICATION/VND.OPENXMLFORMATS-OFFICEDOCUMENT.SPREADSHEETML.SHEET",
        }:
            routes.append(TRACK_XLSX_BUSINESS_STRUCTURED)
        elif text in {"TEXT", "TXT", "PLAIN_TEXT", "MARKDOWN", "MD", "TEXT/PLAIN"}:
            routes.append(TRACK_TEXT_NAMUWIKI_ANIMATION)
    return _dedupe_routes(routes)


def _deterministic_route_hints(query: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    lowered = (query or "").lower()
    routes: list[str] = []
    hints: list[str] = []
    if _has_keyword(lowered, _PDF_ROUTE_KEYWORDS):
        routes.append(TRACK_PDF_BUSINESS_OCR_MM)
        hints.append("pdf_keyword")
    if _has_keyword(lowered, _XLSX_ROUTE_KEYWORDS):
        routes.append(TRACK_XLSX_BUSINESS_STRUCTURED)
        hints.append("xlsx_keyword")
    if _has_keyword(lowered, _NAMU_TEXT_KEYWORDS):
        routes.append(TRACK_TEXT_NAMUWIKI_ANIMATION)
        hints.append("namuwiki_animation_keyword")
    return _dedupe_routes(routes), tuple(hints)


def _clean_routes(routes: Iterable[str] | None) -> tuple[str, ...]:
    if not routes:
        return ()
    return _dedupe_routes(route for route in routes if route in ALL_TRACK_ROUTES)


def _intersect_routes(
    routes: Iterable[str],
    allowed_routes: Iterable[str],
) -> tuple[str, ...]:
    allowed = set(allowed_routes)
    return _dedupe_routes(route for route in routes if route in allowed)


def _dedupe_routes(routes: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for route in routes:
        if route not in ALL_TRACK_ROUTES or route in seen:
            continue
        seen.add(route)
        result.append(route)
    return tuple(result)


def _evidence_assembly_lane(
    *,
    route: str,
    routes: tuple[str, ...],
    source_metadata: Mapping[str, Any] | None,
    evidence_lane: str = "",
) -> str:
    if evidence_lane == "xlsx_structured_evidence":
        return LANE_XLSX_STRICT_EVIDENCE_CITATION
    if evidence_lane == "pdf_content_evidence":
        return LANE_PDF_CONTENT_EVIDENCE
    if evidence_lane == "pdf_file_identity":
        if _has_stable_pdf_identity(source_metadata):
            return LANE_PDF_FILE_DOCUMENT_IDENTITY
        return LANE_PDF_FILE_DOCUMENT_IDENTITY_BLOCKED
    if evidence_lane == "text_content":
        return LANE_TEXT_NAMUWIKI_CANDIDATE_PREP
    if route == TRACK_MULTI_ROUTE:
        return MULTI_ROUTE_EVIDENCE_TYPE
    if route in NON_RETRIEVAL_PRIMARY_ROUTES:
        return route
    if route == TRACK_TEXT_NAMUWIKI_ANIMATION:
        return LANE_TEXT_NAMUWIKI_CANDIDATE_PREP
    if route == TRACK_XLSX_BUSINESS_STRUCTURED:
        return LANE_XLSX_STRICT_EVIDENCE_CITATION
    if route == TRACK_PDF_BUSINESS_OCR_MM:
        if _is_pdf_file_identity_lane(source_metadata):
            if _has_stable_pdf_identity(source_metadata):
                return LANE_PDF_FILE_DOCUMENT_IDENTITY
            return LANE_PDF_FILE_DOCUMENT_IDENTITY_BLOCKED
        return LANE_PDF_CONTENT_EVIDENCE
    if TRACK_PDF_BUSINESS_OCR_MM in routes:
        return LANE_PDF_CONTENT_EVIDENCE
    return "unknown_diagnostic_lane"


def _policy_guards(
    *,
    route: str,
    routes: tuple[str, ...],
    confidence: float,
    evidence_assembly_lane: str,
    source_metadata: Mapping[str, Any] | None,
    extra_policy_flags: Iterable[str] = (),
) -> tuple[str, ...]:
    guards = [
        "diagnostic_only_until_route_gold_and_fallback_labels",
        *tuple(extra_policy_flags),
    ]
    if route == TRACK_TEXT_NAMUWIKI_ANIMATION:
        guards.append("text_namuwiki_noncommercial_limited_no_public_or_gold_promotion")
    if route == TRACK_MULTI_ROUTE or confidence < LOW_ROUTE_CONFIDENCE_THRESHOLD:
        guards.append("diagnostic_multi_route_or_fallback_not_official_success")
    if route == TRACK_POLICY_BLOCKED:
        guards.append("policy_blocked_not_retrieval_failure")
    if evidence_assembly_lane == LANE_PDF_FILE_DOCUMENT_IDENTITY_BLOCKED:
        guards.append("stable_identity_required")
    if TRACK_XLSX_BUSINESS_STRUCTURED in routes and _metadata_hidden_or_excluded(source_metadata):
        guards.append("hidden_negative_or_excluded_row_guard")
    return tuple(_dedupe(guards))


def _is_pdf_file_identity_lane(source_metadata: Mapping[str, Any] | None) -> bool:
    lane = _metadata_text(
        source_metadata,
        "requested_evidence_lane",
        "requestedEvidenceLane",
        "retrieval_lane",
        "retrievalLane",
        "target_lane",
        "targetLane",
    ).lower()
    return lane in {
        "pdf_file",
        "pdf_file_lookup",
        "pdf_file_document_identity",
        "file_document_identity",
        "file_identity",
    }


def _has_stable_pdf_identity(source_metadata: Mapping[str, Any] | None) -> bool:
    if _metadata_bool(
        source_metadata,
        "generic_filename_identity",
        "genericFilenameIdentity",
        "filename_only_identity",
        "filenameOnlyIdentity",
    ):
        return False
    return _metadata_bool(
        source_metadata,
        "stable_document_identity",
        "stableDocumentIdentity",
        "stable_identity",
        "stableIdentity",
    )


def _metadata_hidden_or_excluded(source_metadata: Mapping[str, Any] | None) -> bool:
    return _metadata_bool(
        source_metadata,
        "hidden",
        "hidden_sheet",
        "hiddenSheet",
        "hidden_row",
        "hiddenRow",
        "hidden_negative",
        "hiddenNegative",
        "excluded",
        "excluded_row",
        "excludedRow",
    )


def _metadata_text(source_metadata: Mapping[str, Any] | None, *keys: str) -> str:
    if not isinstance(source_metadata, Mapping):
        return ""
    for key in keys:
        value = source_metadata.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _metadata_bool(source_metadata: Mapping[str, Any] | None, *keys: str) -> bool:
    text = _metadata_text(source_metadata, *keys)
    if not text:
        return False
    return text.lower() in {"1", "true", "yes", "y"}


def build_query_orchestrator_graph():
    """Build the optional LangGraph skeleton.

    LangGraph is deliberately optional. Callers that need to run without it can
    use ``run_query_orchestrator_pure`` or skip graph-specific tests.
    """

    if StateGraph is None:
        raise LangGraphUnavailableError("langgraph is not installed")

    graph = StateGraph(QueryOrchestratorState)
    graph.add_node("policy_guard", policy_guard)
    graph.add_node("normalize_query", normalize_query)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("route_tools", route_tools)
    graph.add_node("run_selected_fake_tools", run_selected_fake_tools)
    graph.add_node("evidence_merge", evidence_merge_node)
    graph.add_node("citation_verify", citation_verify_node)
    graph.add_node("check_evidence_sufficiency", evidence_sufficiency_node)
    graph.add_node("maybe_xlsx_aggregation", maybe_xlsx_aggregation)
    graph.add_node("answer_synthesis_stub", answer_synthesis_stub)

    graph.add_edge(START, "policy_guard")
    graph.add_edge("policy_guard", "normalize_query")
    graph.add_edge("normalize_query", "classify_intent")
    graph.add_edge("classify_intent", "route_tools")
    graph.add_edge("route_tools", "run_selected_fake_tools")
    graph.add_edge("run_selected_fake_tools", "evidence_merge")
    graph.add_edge("evidence_merge", "citation_verify")
    graph.add_edge("citation_verify", "check_evidence_sufficiency")
    graph.add_edge("check_evidence_sufficiency", "maybe_xlsx_aggregation")
    graph.add_edge("maybe_xlsx_aggregation", "answer_synthesis_stub")
    graph.add_edge("answer_synthesis_stub", END)
    return graph.compile()


def initial_query_orchestrator_state(
    *,
    query: str,
    policy: QueryPolicy,
    request_id: str | None = None,
    source_metadata: Mapping[str, Any] | None = None,
    route_adjudicator: RouteAdjudicator | None = None,
    retriever: Any | None = None,
) -> QueryOrchestratorState:
    state: QueryOrchestratorState = {
        "request_id": request_id or policy.request_id,
        "query": query,
        "policy": policy,
        "source_metadata": dict(source_metadata or {}),
        "loop_states": [],
        "trace": [],
        "errors": [],
    }
    if route_adjudicator is not None:
        state["route_adjudicator"] = route_adjudicator
    if retriever is not None:
        state["vector_retriever"] = retriever
    return state


def run_query_orchestrator_pure(
    *,
    query: str,
    policy: QueryPolicy,
    request_id: str | None = None,
    source_metadata: Mapping[str, Any] | None = None,
    route_adjudicator: RouteAdjudicator | None = None,
    retriever: Any | None = None,
    fixture: FixtureMode = "valid",
) -> QueryOrchestratorState:
    """Run the graph flow as pure functions for deterministic unit tests."""

    state = initial_query_orchestrator_state(
        query=query,
        policy=policy,
        request_id=request_id,
        source_metadata=source_metadata,
        route_adjudicator=route_adjudicator,
        retriever=retriever,
    )
    for node in (
        policy_guard,
        normalize_query,
        classify_intent,
        route_tools,
    ):
        state = node(state)
    state = run_selected_fake_tools(state, fixture=fixture)
    for node in (
        evidence_merge_node,
        citation_verify_node,
        evidence_sufficiency_node,
        maybe_xlsx_aggregation,
        answer_synthesis_stub,
    ):
        state = node(state)
    return state


def policy_guard(state: QueryOrchestratorState) -> QueryOrchestratorState:
    current = _copy_state(state)
    errors = list(current.get("errors", []))

    forbidden_keys = forbidden_state_keys_present(dict(current))
    if forbidden_keys:
        errors.append(
            {
                "node": "policy_guard",
                "reason": "forbidden_state_fields",
                "fields": list(forbidden_keys),
            }
        )

    policy = current.get("policy")
    if not isinstance(policy, QueryPolicy):
        errors.append({"node": "policy_guard", "reason": "missing_query_policy"})

    if errors:
        current["errors"] = errors
        current["stop_reason"] = "policy_guard_failed"
    return _with_trace(current, "policy_guard")


def normalize_query(state: QueryOrchestratorState) -> QueryOrchestratorState:
    current = _copy_state(state)
    current["normalized_query"] = " ".join(current.get("query", "").split()).strip()
    return _with_trace(current, "normalize_query")


def classify_intent(state: QueryOrchestratorState) -> QueryOrchestratorState:
    current = _copy_state(state)
    query = current.get("normalized_query") or current.get("query", "")
    lowered = query.lower()
    route_decision = build_route_decision(
        query=query,
        policy=current.get("policy") if isinstance(current.get("policy"), QueryPolicy) else None,
        source_metadata=current.get("source_metadata"),
        route_adjudicator=current.get("route_adjudicator"),
    )

    source_intents: list[str] = []
    if TRACK_PDF_BUSINESS_OCR_MM in route_decision.routes:
        source_intents.append(INTENT_PDF)
    if TRACK_XLSX_BUSINESS_STRUCTURED in route_decision.routes:
        source_intents.append(INTENT_XLSX)
    if TRACK_TEXT_NAMUWIKI_ANIMATION in route_decision.routes:
        source_intents.append(INTENT_TEXT)

    intent_types = list(source_intents)
    if _has_keyword(lowered, _AGGREGATION_KEYWORDS):
        intent_types.append(INTENT_AGGREGATION)
    if len(source_intents) > 1:
        intent_types.append(INTENT_MIXED)
    if not source_intents:
        intent_types.append(INTENT_FALLBACK)

    current["intent"] = {
        "types": intent_types,
        "source_intents": source_intents,
        "requires_aggregation": INTENT_AGGREGATION in intent_types,
    }
    current["route_decision"] = route_decision.to_dict()
    policy_obj = current.get("policy")
    current["route_diagnostics"] = [
        route_decision.to_diagnostic(
            query_id=str(
                current.get("request_id")
                or (policy_obj.request_id if isinstance(policy_obj, QueryPolicy) else "")
            ),
            query=query,
        )
    ]
    current["loop_states"] = _append_loop_states(
        current.get("loop_states", []),
        _initial_loop_states(route_decision),
    )
    return _with_trace(
        current,
        "classify_intent",
        {
            "route_decision": route_decision.to_dict(),
            "route_diagnostics": list(current["route_diagnostics"]),
        },
    )


def route_tools(state: QueryOrchestratorState) -> QueryOrchestratorState:
    current = _copy_state(state)
    route_decision = current.get("route_decision") or {}
    if route_decision.get("route") in NON_RETRIEVAL_PRIMARY_ROUTES:
        current["selected_tools"] = []
        return _with_trace(
            current,
            "route_tools",
            {
                "route_decision": route_decision,
                "selected_tools": [],
                "retrieval_blocked": route_decision.get("route"),
            },
        )
    routes = tuple(route_decision.get("routes") or ())
    selected_tools = [
        ROUTE_TO_TOOL[route] for route in routes if route in ROUTE_TO_TOOL
    ]

    current["selected_tools"] = selected_tools
    return _with_trace(
        current,
        "route_tools",
        {
            "route_decision": route_decision,
            "selected_tools": selected_tools,
        },
    )


def run_selected_fake_tools(
    state: QueryOrchestratorState,
    *,
    fixture: FixtureMode = "valid",
) -> QueryOrchestratorState:
    current = _copy_state(state)
    retriever = current.get("vector_retriever")
    trace_node = "run_selected_vector_tools" if retriever is not None else "run_selected_fake_tools"
    if current.get("stop_reason") == "policy_guard_failed":
        current["tool_results"] = []
        current["evidence"] = []
        return _with_trace(current, trace_node)

    route_decision = current.get("route_decision") or {}
    if route_decision.get("route") in NON_RETRIEVAL_PRIMARY_ROUTES:
        current["tool_results"] = []
        current["fallback_routes_triggered"] = []
        current["fallback_attempts"] = []
        current["evidence"] = []
        current["rejected_evidence"] = []
        current["loop_states"] = _append_loop_states(
            current.get("loop_states", []),
            [str(route_decision.get("route")), "final_diagnostic_only"],
        )
        return _with_trace(
            current,
            trace_node,
            {"retrieval_blocked": route_decision.get("route")},
        )

    policy = current["policy"]
    query = current.get("normalized_query") or current.get("query", "")
    tool_results: list[ToolResult] = []

    selected_tools = list(current.get("selected_tools", []))
    tool_results.extend(
        _run_tool_sequence(
            selected_tools,
            query,
            policy,
            fixture=fixture,
            retriever=retriever,
        )
    )

    fallback_routes = tuple(route_decision.get("fallback_routes") or ())
    fallback_tools = [
        ROUTE_TO_TOOL[route]
        for route in fallback_routes
        if route in ROUTE_TO_TOOL and ROUTE_TO_TOOL[route] not in selected_tools
    ]
    fallback_triggered: list[str] = []
    fallback_attempts: list[dict[str, Any]] = []
    if (
        route_decision.get("allow_fallback")
        and fallback_tools
        and not any(result.evidence for result in tool_results)
    ):
        fallback_tool = fallback_tools[0]
        fallback_route = TOOL_TO_ROUTE[fallback_tool]
        fallback_triggered = [fallback_route]
        fallback_attempts = [{"attempt": 1, "route": fallback_route}]
        tool_results.extend(
            _run_tool_sequence(
                [fallback_tool],
                query,
                policy,
                fixture=fixture,
                retriever=retriever,
            )
        )

    current["tool_results"] = tool_results
    current["fallback_routes_triggered"] = fallback_triggered
    current["fallback_attempts"] = fallback_attempts
    current["evidence"] = [item for result in tool_results for item in result.evidence]
    current["rejected_evidence"] = [
        item.to_dict() for result in tool_results for item in result.rejected
    ]
    loop_updates = ["retrieved"]
    if fallback_attempts:
        loop_updates.append("fallback_attempted")
        if len(fallback_routes) > len(fallback_attempts):
            loop_updates.append("fallback_blocked")
    if not current["evidence"]:
        loop_updates.append("no_supported_evidence")
    current["loop_states"] = _append_loop_states(
        current.get("loop_states", []),
        loop_updates,
    )
    _update_first_route_diagnostic(
        current,
        fallback_attempts=fallback_attempts,
        fallback_attempt_count=len(fallback_attempts),
    )
    return _with_trace(
        current,
        trace_node,
        {
            "fallback_routes_triggered": fallback_triggered,
            "fallback_attempts": fallback_attempts,
            "tool_backend": "vector_retriever_poc" if retriever is not None else "fake_vector",
        },
    )


def _run_tool_sequence(
    tools: Iterable[str],
    query: str,
    policy: QueryPolicy,
    *,
    fixture: FixtureMode,
    retriever: Any | None = None,
) -> list[ToolResult]:
    tool_results: list[ToolResult] = []
    for tool in tools:
        if tool == PDF_TOOL:
            if retriever is None:
                tool_results.append(fake_pdf_vector_search_tool(query, policy, fixture=fixture))
            else:
                tool_results.append(pdf_vector_search_tool(query, policy, retriever=retriever))
        elif tool == XLSX_TOOL:
            if retriever is None:
                tool_results.append(fake_xlsx_vector_search_tool(query, policy, fixture=fixture))
            else:
                tool_results.append(xlsx_vector_search_tool(query, policy, retriever=retriever))
        elif tool == TEXT_TOOL:
            if retriever is None:
                tool_results.append(fake_text_vector_search_tool(query, policy, fixture=fixture))
            else:
                tool_results.append(text_vector_search_tool(query, policy, retriever=retriever))
    return tool_results


def evidence_merge_node(state: QueryOrchestratorState) -> QueryOrchestratorState:
    current = _copy_state(state)
    policy = current.get("policy")
    max_evidence = policy.top_k if isinstance(policy, QueryPolicy) else 10
    result = evidence_merge_tool(
        current.get("tool_results", []),
        strategy="rank_rrf_then_type_balance",
        max_evidence=max_evidence,
    )
    current["merged_evidence"] = list(result.merged_evidence)
    current["trace"] = _append_trace(
        current.get("trace", []),
        "evidence_merge",
        {
            "dedupe_stats": dict(result.dedupe_stats),
            "source_type_counts": dict(result.source_type_counts),
        },
    )
    return current


def citation_verify_node(state: QueryOrchestratorState) -> QueryOrchestratorState:
    current = _copy_state(state)
    if current.get("stop_reason") == "policy_guard_failed":
        current["verified_evidence"] = []
        return _with_trace(
            current,
            "citation_verify",
            {"metrics": {"verified_count": 0, "rejected_count": 0}},
        )

    policy = current["policy"]
    result = citation_verify_tool(current.get("merged_evidence", []), policy)
    current["verified_evidence"] = [
        _mark_verified(item.evidence, item.warnings) for item in result.verified
    ]

    existing_rejected = list(current.get("rejected_evidence", []))
    current["rejected_evidence"] = existing_rejected + [
        item.to_dict() for item in result.rejected
    ]
    current["trace"] = _append_trace(
        current.get("trace", []),
        "citation_verify",
        {"metrics": result.metrics},
    )
    return current


def evidence_sufficiency_node(state: QueryOrchestratorState) -> QueryOrchestratorState:
    current = _copy_state(state)
    route_decision = current.get("route_decision") or {}
    route = str(route_decision.get("route") or "")
    verified = list(current.get("verified_evidence", []))

    if route == TRACK_POLICY_BLOCKED:
        result = {
            "status": "policy_blocked",
            "sufficient": False,
            "reasons": list(route_decision.get("blocked_flags") or ["policy_blocked"]),
        }
        current["evidence_sufficiency"] = result
        _update_first_route_diagnostic(current, final_diagnostic_status="policy_blocked")
        return _with_trace(current, "evidence_sufficiency", result)
    if route == TRACK_INSUFFICIENT_METADATA:
        result = {
            "status": "insufficient_metadata",
            "sufficient": False,
            "reasons": ["insufficient_metadata"],
        }
        current["evidence_sufficiency"] = result
        _update_first_route_diagnostic(current, final_diagnostic_status="insufficient_metadata")
        return _with_trace(current, "evidence_sufficiency", result)

    reasons: list[str] = []
    expected_routes = tuple(route_decision.get("routes") or ())
    expected_source_types = {
        TRACK_TEXT_NAMUWIKI_ANIMATION: "TEXT",
        TRACK_XLSX_BUSINESS_STRUCTURED: "SPREADSHEET",
        TRACK_PDF_BUSINESS_OCR_MM: "PDF",
    }
    allowed_source_types = {
        expected_source_types[item] for item in expected_routes if item in expected_source_types
    }
    if not verified:
        reasons.append("no_verified_evidence")
    for item in verified:
        if allowed_source_types and item.source_file_type not in allowed_source_types:
            reasons.append("evidence_track_mismatch")
        if not item.citation_text:
            reasons.append("missing_citation_text")
        if not item.location_json:
            reasons.append("missing_location_json")
        if item.source_file_type == "SPREADSHEET" and not _xlsx_locator_sufficient(item.location_json):
            reasons.append("xlsx_structured_locator_missing")
        if item.source_file_type == "PDF":
            lane = route_decision.get("evidence_lane")
            if lane == "pdf_file_identity" and not _has_stable_pdf_evidence_identity(item):
                reasons.append("pdf_stable_document_identity_missing")
            if lane != "pdf_file_identity" and not _pdf_content_locator_sufficient(item.location_json):
                reasons.append("pdf_content_locator_missing")
        if item.source_file_type == "TEXT" and _metadata_query_id(policy=None, source_metadata=item.extra) in TEXT_NAMU_UNRESOLVED_IDS:
            reasons.append("text_namu_unresolved_excluded_from_gold_v0_1")

    sufficient = not reasons
    status = "evidence_sufficient" if sufficient else "no_supported_evidence"
    if not sufficient and current.get("fallback_attempts"):
        status = "fallback_blocked"
    result = {
        "status": status,
        "sufficient": sufficient,
        "reasons": list(_dedupe(reasons)),
        "checked_track": route,
        "checked_evidence_lane": route_decision.get("evidence_lane") or "none",
    }
    current["evidence_sufficiency"] = result
    current["loop_states"] = _append_loop_states(
        current.get("loop_states", []),
        [status, "final_diagnostic_only"],
    )
    _update_first_route_diagnostic(
        current,
        final_diagnostic_status=status,
        evidence_sufficiency=result,
    )
    return _with_trace(current, "evidence_sufficiency", result)


def maybe_xlsx_aggregation(state: QueryOrchestratorState) -> QueryOrchestratorState:
    current = _copy_state(state)
    intent = current.get("intent", {})
    if not intent.get("requires_aggregation"):
        current["aggregation_results"] = []
        return _with_trace(current, "maybe_xlsx_aggregation", {"selected": False})

    xlsx_evidence = [
        item
        for item in current.get("verified_evidence", [])
        if item.source_file_type == SOURCE_FILE_TYPE_SPREADSHEET
    ]
    if not xlsx_evidence:
        current["aggregation_results"] = []
        return _with_trace(current, "maybe_xlsx_aggregation", {"selected": False})

    table_ref = _table_ref_from_evidence(xlsx_evidence[0])
    table = xlsx_table_materialize_fixture_tool(
        table_ref,
        limits={"max_rows": 200, "max_columns": 50, "max_cells": 5000},
    )
    aggregation = xlsx_aggregation_tool(
        table,
        operation="sum",
        metric_column="Revenue",
    )
    current["aggregation_results"] = [aggregation]
    return _with_trace(
        current,
        "maybe_xlsx_aggregation",
        {"selected": True, "status": aggregation.status},
    )


def answer_synthesis_stub(state: QueryOrchestratorState) -> QueryOrchestratorState:
    current = _copy_state(state)
    query = current.get("normalized_query") or current.get("query", "")
    verified = current.get("verified_evidence", [])
    handoff = prepare_answer_handoff(query=query, evidence=verified)

    if handoff.status != "ready":
        current["answer"] = build_no_evidence_response(query=query).to_dict()
        if current.get("stop_reason") != "policy_guard_failed":
            current["stop_reason"] = "no_verified_evidence"
        return _with_trace(current, "answer_synthesis_stub")

    cited = [
        {
            "evidence_id": item.evidence_id,
            "citation_text": item.citation_text,
        }
        for item in handoff.verified_evidence
        if item.evidence_id in set(handoff.used_evidence_ids)
    ]
    current["answer"] = {
        "status": "stub",
        "answer": _stub_answer(cited),
        "used_evidence_ids": list(handoff.used_evidence_ids),
        "citations": cited,
        "llm_called": False,
    }
    current["stop_reason"] = "answered_with_verified_evidence_stub"
    return _with_trace(current, "answer_synthesis_stub")


def _copy_state(state: QueryOrchestratorState) -> QueryOrchestratorState:
    return dict(state)


def _initial_loop_states(route_decision: RouteDecision) -> list[str]:
    states = ["routed"]
    if route_decision.route == TRACK_MULTI_ROUTE:
        states.append(TRACK_MULTI_ROUTE)
    if route_decision.route == TRACK_POLICY_BLOCKED:
        states.append("policy_blocked")
    if route_decision.route == TRACK_INSUFFICIENT_METADATA:
        states.append("insufficient_metadata")
    return states


def _append_loop_states(
    existing: Iterable[str],
    additions: Iterable[str],
) -> list[str]:
    output = list(existing or [])
    for item in additions:
        if item:
            output.append(str(item))
    return output


def _update_first_route_diagnostic(
    state: QueryOrchestratorState,
    **updates: Any,
) -> None:
    diagnostics = list(state.get("route_diagnostics", []))
    if not diagnostics:
        return
    updated = dict(diagnostics[0])
    updated.update(updates)
    diagnostics[0] = updated
    state["route_diagnostics"] = diagnostics


def _with_trace(
    state: QueryOrchestratorState,
    node: str,
    extra: dict[str, Any] | None = None,
) -> QueryOrchestratorState:
    state["trace"] = _append_trace(state.get("trace", []), node, extra)
    return state


def _append_trace(
    trace: Iterable[dict[str, Any]],
    node: str,
    extra: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    item: dict[str, Any] = {"node": node}
    if extra:
        item.update(extra)
    return [*trace, item]


def _has_keyword(query: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in query for keyword in keywords)


def _mark_verified(evidence: Evidence, warnings: Iterable[str]) -> Evidence:
    return replace(
        evidence,
        verification_status="verified",
        verification_reasons=(),
        verification_warnings=_dedupe(
            (*evidence.verification_warnings, *tuple(warnings))
        ),
    )


def _xlsx_locator_sufficient(location_json: Any) -> bool:
    if not isinstance(location_json, Mapping):
        return False
    has_sheet = _has_any(location_json, ("sheetName", "sheet_name"))
    has_locator = _has_any(
        location_json,
        (
            "cellRange",
            "cell_range",
            "tableId",
            "table_id",
            "rowStart",
            "row_start",
            "columnStart",
            "column_start",
        ),
    )
    return has_sheet and has_locator


def _pdf_content_locator_sufficient(location_json: Any) -> bool:
    if not isinstance(location_json, Mapping):
        return False
    has_page = _has_any(
        location_json,
        ("page", "page_no", "pageNo", "page_start", "pageStart", "physical_page_index"),
    )
    has_content_locator = _has_any(
        location_json,
        ("bbox", "region_type", "regionType", "table_id", "tableId"),
    )
    return has_page and has_content_locator


def _has_stable_pdf_evidence_identity(evidence: Evidence) -> bool:
    sources = []
    if isinstance(evidence.location_json, Mapping):
        sources.append(evidence.location_json)
    if isinstance(evidence.extra, Mapping):
        sources.append(evidence.extra)
        retriever_metadata = evidence.extra.get("retriever_metadata")
        if isinstance(retriever_metadata, Mapping):
            sources.append(retriever_metadata)
    for source in sources:
        if _metadata_bool(source, "genericFilenameIdentity", "generic_filename_identity"):
            return False
        if _metadata_bool(source, "stableDocumentIdentity", "stable_document_identity", "stableIdentity", "stable_identity"):
            return True
    return False


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return tuple(output)


def _table_ref_from_evidence(evidence: Evidence) -> dict[str, Any]:
    location = evidence.location_json if isinstance(evidence.location_json, dict) else {}
    return {
        "fixture": location.get("tableId") or location.get("table_id") or "sales-table",
        "source_file_id": evidence.source_file_id,
        "sheet_name": location.get("sheetName") or location.get("sheet_name"),
        "cell_range": location.get("cellRange") or location.get("cell_range"),
        "table_id": location.get("tableId") or location.get("table_id"),
    }


def _has_any(data: Mapping[str, Any], keys: tuple[str, ...]) -> bool:
    return any(data.get(key) not in (None, "") for key in keys)


def _stub_answer(cited: list[dict[str, str]]) -> str:
    citation_parts = [
        f"{item['evidence_id']} ({item['citation_text']})" for item in cited
    ]
    return "Verified evidence stub: " + "; ".join(citation_parts)
