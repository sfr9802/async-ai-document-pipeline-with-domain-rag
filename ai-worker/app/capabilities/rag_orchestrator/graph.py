"""Optional LangGraph skeleton for query-time RAG orchestration.

The graph is unit-test-only in this POC. It uses fake vector tools, does not
register a runtime endpoint, and does not call LangChain, Spring APIs, DBs, or
real vector retrievers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable

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
TRACK_MULTI_ROUTE = "multi_route"

ALL_TRACK_ROUTES = (
    TRACK_TEXT_NAMUWIKI_ANIMATION,
    TRACK_XLSX_BUSINESS_STRUCTURED,
    TRACK_PDF_BUSINESS_OCR_MM,
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
    deterministic_hints: tuple[str, ...] = ()
    metadata_guards: tuple[str, ...] = ()
    llm_decision_used: bool = False
    post_retrieval_validation: str = "required"

    def __post_init__(self) -> None:
        if self.route != TRACK_MULTI_ROUTE and self.route not in ALL_TRACK_ROUTES:
            raise ValueError(f"unsupported route: {self.route!r}")
        for route in (*self.routes, *self.fallback_routes):
            if route not in ALL_TRACK_ROUTES:
                raise ValueError(f"unsupported route in route decision: {route!r}")
        if not (0.0 <= self.route_confidence <= 1.0):
            raise ValueError("route_confidence must be in [0.0, 1.0]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "routes": list(self.routes),
            "route_confidence": round(float(self.route_confidence), 4),
            "reason": self.reason,
            "required_evidence_type": self.required_evidence_type,
            "allow_fallback": self.allow_fallback,
            "fallback_routes": list(self.fallback_routes),
            "multi_route": self.multi_route,
            "deterministic_hints": list(self.deterministic_hints),
            "metadata_guards": list(self.metadata_guards),
            "llm_decision_used": self.llm_decision_used,
            "post_retrieval_validation": self.post_retrieval_validation,
        }


class LangGraphUnavailableError(RuntimeError):
    """Raised when graph compilation is requested without LangGraph installed."""


def build_route_decision(
    *,
    query: str,
    policy: QueryPolicy | None = None,
    source_metadata: dict[str, Any] | None = None,
    llm_suggested_routes: Iterable[str] | None = None,
) -> RouteDecision:
    """Choose a guarded 3-track route for a query.

    Deterministic query hints propose a route first. Source-file metadata and
    code-created policy source-type allowlists then act as hard guards; LLM
    suggestions can only narrow within those guards and never relax them.
    """

    allowed_routes, guard_reasons = _allowed_routes_from_policy_and_metadata(
        policy=policy,
        source_metadata=source_metadata,
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

    candidate_routes = deterministic_routes or llm_routes
    llm_used = llm_only
    if candidate_routes:
        guarded_routes = _intersect_routes(candidate_routes, allowed_routes)
        if guarded_routes:
            routes = guarded_routes
            if deterministic_routes and len(routes) == 1:
                confidence = 0.9
            elif llm_only and len(routes) == 1:
                confidence = 0.52
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
    fallback_routes = (
        tuple(route for route in allowed_routes if route not in routes)
        if confidence < LOW_ROUTE_CONFIDENCE_THRESHOLD and not multi_route
        else ()
    )
    allow_fallback = bool(fallback_routes)
    required_evidence_type = (
        MULTI_ROUTE_EVIDENCE_TYPE
        if multi_route
        else ROUTE_REQUIRED_EVIDENCE_TYPE[routes[0]]
    )
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
        deterministic_hints=deterministic_hints,
        metadata_guards=tuple(guard_reasons),
        llm_decision_used=llm_used,
    )


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
        return ALL_TRACK_ROUTES, reasons + ["empty_guard_reset_to_all_tracks"]
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
    graph.add_node("maybe_xlsx_aggregation", maybe_xlsx_aggregation)
    graph.add_node("answer_synthesis_stub", answer_synthesis_stub)

    graph.add_edge(START, "policy_guard")
    graph.add_edge("policy_guard", "normalize_query")
    graph.add_edge("normalize_query", "classify_intent")
    graph.add_edge("classify_intent", "route_tools")
    graph.add_edge("route_tools", "run_selected_fake_tools")
    graph.add_edge("run_selected_fake_tools", "evidence_merge")
    graph.add_edge("evidence_merge", "citation_verify")
    graph.add_edge("citation_verify", "maybe_xlsx_aggregation")
    graph.add_edge("maybe_xlsx_aggregation", "answer_synthesis_stub")
    graph.add_edge("answer_synthesis_stub", END)
    return graph.compile()


def initial_query_orchestrator_state(
    *,
    query: str,
    policy: QueryPolicy,
    request_id: str | None = None,
) -> QueryOrchestratorState:
    return {
        "request_id": request_id or policy.request_id,
        "query": query,
        "policy": policy,
        "trace": [],
        "errors": [],
    }


def run_query_orchestrator_pure(
    *,
    query: str,
    policy: QueryPolicy,
    request_id: str | None = None,
    fixture: FixtureMode = "valid",
) -> QueryOrchestratorState:
    """Run the graph flow as pure functions for deterministic unit tests."""

    state = initial_query_orchestrator_state(
        query=query,
        policy=policy,
        request_id=request_id,
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
    return _with_trace(
        current,
        "classify_intent",
        {"route_decision": route_decision.to_dict()},
    )


def route_tools(state: QueryOrchestratorState) -> QueryOrchestratorState:
    current = _copy_state(state)
    route_decision = current.get("route_decision") or {}
    routes = tuple(route_decision.get("routes") or ())
    selected_tools = [
        ROUTE_TO_TOOL[route] for route in routes if route in ROUTE_TO_TOOL
    ]
    if not selected_tools:
        selected_tools = list(ALL_TOOLS)

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
    if current.get("stop_reason") == "policy_guard_failed":
        current["tool_results"] = []
        current["evidence"] = []
        return _with_trace(current, "run_selected_fake_tools")

    policy = current["policy"]
    query = current.get("normalized_query") or current.get("query", "")
    tool_results: list[ToolResult] = []

    selected_tools = list(current.get("selected_tools", []))
    tool_results.extend(_run_fake_tool_sequence(selected_tools, query, policy, fixture=fixture))

    route_decision = current.get("route_decision") or {}
    fallback_routes = tuple(route_decision.get("fallback_routes") or ())
    fallback_tools = [
        ROUTE_TO_TOOL[route]
        for route in fallback_routes
        if route in ROUTE_TO_TOOL and ROUTE_TO_TOOL[route] not in selected_tools
    ]
    fallback_triggered: list[str] = []
    if (
        route_decision.get("allow_fallback")
        and fallback_tools
        and not any(result.evidence for result in tool_results)
    ):
        fallback_triggered = [
            TOOL_TO_ROUTE[tool] for tool in fallback_tools if tool in TOOL_TO_ROUTE
        ]
        tool_results.extend(
            _run_fake_tool_sequence(fallback_tools, query, policy, fixture=fixture)
        )

    current["tool_results"] = tool_results
    current["fallback_routes_triggered"] = fallback_triggered
    current["evidence"] = [item for result in tool_results for item in result.evidence]
    current["rejected_evidence"] = [
        item.to_dict() for result in tool_results for item in result.rejected
    ]
    return _with_trace(
        current,
        "run_selected_fake_tools",
        {"fallback_routes_triggered": fallback_triggered},
    )


def _run_fake_tool_sequence(
    tools: Iterable[str],
    query: str,
    policy: QueryPolicy,
    *,
    fixture: FixtureMode,
) -> list[ToolResult]:
    tool_results: list[ToolResult] = []
    for tool in tools:
        if tool == PDF_TOOL:
            tool_results.append(fake_pdf_vector_search_tool(query, policy, fixture=fixture))
        elif tool == XLSX_TOOL:
            tool_results.append(fake_xlsx_vector_search_tool(query, policy, fixture=fixture))
        elif tool == TEXT_TOOL:
            tool_results.append(fake_text_vector_search_tool(query, policy, fixture=fixture))
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


def _stub_answer(cited: list[dict[str, str]]) -> str:
    citation_parts = [
        f"{item['evidence_id']} ({item['citation_text']})" for item in cited
    ]
    return "Verified evidence stub: " + "; ".join(citation_parts)
