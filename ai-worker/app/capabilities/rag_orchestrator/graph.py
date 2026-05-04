"""Optional LangGraph skeleton for query-time RAG orchestration.

The graph is unit-test-only in this POC. It uses fake vector tools, does not
register a runtime endpoint, and does not call LangChain, Spring APIs, DBs, or
real vector retrievers.
"""

from __future__ import annotations

from dataclasses import replace
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


class LangGraphUnavailableError(RuntimeError):
    """Raised when graph compilation is requested without LangGraph installed."""


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

    source_intents: list[str] = []
    if _has_keyword(lowered, _PDF_KEYWORDS):
        source_intents.append(INTENT_PDF)
    if _has_keyword(lowered, _XLSX_KEYWORDS):
        source_intents.append(INTENT_XLSX)
    if _has_keyword(lowered, _TEXT_KEYWORDS):
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
    return _with_trace(current, "classify_intent")


def route_tools(state: QueryOrchestratorState) -> QueryOrchestratorState:
    current = _copy_state(state)
    intent = current.get("intent", {})
    source_intents = tuple(intent.get("source_intents", ()))

    if not source_intents:
        selected_tools = list(ALL_TOOLS)
    else:
        selected_tools = []
        if INTENT_PDF in source_intents:
            selected_tools.append(PDF_TOOL)
        if INTENT_XLSX in source_intents:
            selected_tools.append(XLSX_TOOL)
        if INTENT_TEXT in source_intents:
            selected_tools.append(TEXT_TOOL)

    current["selected_tools"] = selected_tools
    return _with_trace(current, "route_tools")


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

    for tool in current.get("selected_tools", []):
        if tool == PDF_TOOL:
            tool_results.append(fake_pdf_vector_search_tool(query, policy, fixture=fixture))
        elif tool == XLSX_TOOL:
            tool_results.append(fake_xlsx_vector_search_tool(query, policy, fixture=fixture))
        elif tool == TEXT_TOOL:
            tool_results.append(fake_text_vector_search_tool(query, policy, fixture=fixture))
        else:
            current.setdefault("errors", []).append(
                {"node": "run_selected_fake_tools", "reason": "unknown_tool", "tool": tool}
            )

    current["tool_results"] = tool_results
    current["evidence"] = [item for result in tool_results for item in result.evidence]
    current["rejected_evidence"] = [
        item.to_dict() for result in tool_results for item in result.rejected
    ]
    return _with_trace(current, "run_selected_fake_tools")


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
