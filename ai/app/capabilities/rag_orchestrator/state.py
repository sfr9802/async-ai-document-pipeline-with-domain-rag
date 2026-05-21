"""Query-run state contract for the optional LangGraph RAG POC."""

from __future__ import annotations

from typing import Any, TypedDict

from app.capabilities.rag_orchestrator.evidence import Evidence, QueryPolicy
from app.capabilities.rag_orchestrator.tools import ToolResult
from app.capabilities.rag_orchestrator.xlsx_tools import XlsxAggregationResult

FORBIDDEN_STATE_FIELDS = frozenset(
    {
        "db_credentials",
        "database_credentials",
        "db_dsn",
        "db_password",
        "spring_db_lifecycle_state",
        "unbounded_db_results",
        "source_file_mutation_state",
        "job_mutation_state",
        "search_unit_mutation_state",
        "active_index_promotion_state",
        "raw_llm_hidden_reasoning",
        "llm_hidden_reasoning",
    }
)


class QueryOrchestratorState(TypedDict, total=False):
    """Bounded state for one query-time orchestration run.

    This state intentionally excludes Spring DB lifecycle state, ingestion
    mutation state, index promotion state, and raw hidden LLM reasoning.
    """

    request_id: str
    query: str
    normalized_query: str
    policy: QueryPolicy
    source_metadata: dict[str, Any]
    intent: dict[str, Any]
    route_decision: dict[str, Any]
    route_diagnostics: list[dict[str, Any]]
    route_adjudicator: Any
    vector_retriever: Any
    loop_states: list[str]
    selected_tools: list[str]
    tool_results: list[ToolResult]
    fallback_routes_triggered: list[str]
    fallback_attempts: list[dict[str, Any]]
    evidence: list[Evidence]
    merged_evidence: list[Evidence]
    verified_evidence: list[Evidence]
    rejected_evidence: list[dict[str, Any]]
    evidence_sufficiency: dict[str, Any]
    aggregation_results: list[XlsxAggregationResult]
    answer: dict[str, Any]
    stop_reason: str
    trace: list[dict[str, Any]]
    errors: list[dict[str, Any]]


def forbidden_state_keys_present(state: dict[str, Any]) -> tuple[str, ...]:
    """Return forbidden graph-state keys that are present in a candidate state."""

    return tuple(sorted(set(state) & FORBIDDEN_STATE_FIELDS))
