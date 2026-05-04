from __future__ import annotations

import pytest

from app.capabilities.rag_orchestrator.evidence import QueryPolicy
from app.capabilities.rag_orchestrator.graph import (
    LANGGRAPH_AVAILABLE,
    PDF_TOOL,
    XLSX_TOOL,
    answer_synthesis_stub,
    build_query_orchestrator_graph,
    initial_query_orchestrator_state,
    run_query_orchestrator_pure,
)
from app.capabilities.rag_orchestrator.state import FORBIDDEN_STATE_FIELDS
from app.capabilities.rag_orchestrator.tools import (
    TOOL_PDF_VECTOR_SEARCH,
    TOOL_XLSX_VECTOR_SEARCH,
)

pytestmark = pytest.mark.skipif(
    not LANGGRAPH_AVAILABLE,
    reason="LangGraph is an optional dependency for the POC graph skeleton",
)


def _policy(
    *,
    source_types=("PDF", "SPREADSHEET", "TEXT"),
    parser_versions=(
        "pdf-extract-v2",
        "xlsx-extract-v2-hidden-safe",
        "text-parser-v0",
    ),
    top_k=5,
) -> QueryPolicy:
    return QueryPolicy(
        request_id="req-graph-1",
        required_index_version="rag-ingestion-v2-candidate",
        allowed_source_file_types=list(source_types),
        allowed_parser_versions=list(parser_versions),
        top_k=top_k,
    )


def test_pdf_query_selects_pdf_fake_tool_with_compiled_graph():
    graph = build_query_orchestrator_graph()
    state = graph.invoke(
        initial_query_orchestrator_state(
            query="pdf 보고서 근거를 찾아줘",
            policy=_policy(),
        )
    )

    assert state["selected_tools"] == [PDF_TOOL]
    assert [item.tool for item in state["tool_results"]] == [TOOL_PDF_VECTOR_SEARCH]
    assert len(state["verified_evidence"]) == 1
    assert state["answer"]["status"] == "stub"
    assert state["answer"]["llm_called"] is False


def test_xlsx_aggregation_query_selects_xlsx_tool_and_aggregation_path():
    state = run_query_orchestrator_pure(
        query="xlsx 표 매출 합계를 보여줘",
        policy=_policy(),
    )

    assert state["selected_tools"] == [XLSX_TOOL]
    assert [item.tool for item in state["tool_results"]] == [TOOL_XLSX_VECTOR_SEARCH]
    assert len(state["aggregation_results"]) == 1
    aggregation = state["aggregation_results"][0]
    assert aggregation.status == "ok"
    assert aggregation.operation == "sum"
    assert aggregation.result["value"] == 700
    assert aggregation.deterministic is True


def test_mixed_query_calls_pdf_and_xlsx_tools():
    state = run_query_orchestrator_pure(
        query="pdf 설명과 xlsx 표 합계를 같이 확인해줘",
        policy=_policy(),
    )

    assert state["selected_tools"] == [PDF_TOOL, XLSX_TOOL]
    assert [item.tool for item in state["tool_results"]] == [
        TOOL_PDF_VECTOR_SEARCH,
        TOOL_XLSX_VECTOR_SEARCH,
    ]
    assert {item.source_file_type for item in state["verified_evidence"]} == {
        "PDF",
        "SPREADSHEET",
    }


def test_tool_results_are_merged_and_verified():
    state = run_query_orchestrator_pure(
        query="pdf와 xlsx 근거를 합쳐줘",
        policy=_policy(),
    )

    assert len(state["merged_evidence"]) == 2
    assert len(state["verified_evidence"]) == 2
    assert all(item.verification_status == "verified" for item in state["verified_evidence"])
    assert state["answer"]["used_evidence_ids"] == [
        item.evidence_id for item in state["verified_evidence"]
    ]


def test_no_evidence_path_blocks_hallucinated_answer():
    state = run_query_orchestrator_pure(
        query="pdf 근거를 찾아줘",
        policy=_policy(source_types=("PDF",), parser_versions=("pdf-extract-v2",)),
        fixture="mismatch",
    )

    assert state["verified_evidence"] == []
    assert state["merged_evidence"] == []
    assert state["answer"]["status"] == "blocked"
    assert state["answer"]["reason"] == "no_verified_evidence"
    assert state["answer"]["used_evidence_ids"] == []
    assert state["stop_reason"] == "no_verified_evidence"


def test_rejected_evidence_is_not_used_in_answer():
    state = run_query_orchestrator_pure(
        query="xlsx 합계",
        policy=_policy(
            source_types=("SPREADSHEET",),
            parser_versions=("xlsx-extract-v2-hidden-safe",),
        ),
        fixture="mixed",
    )

    rejected_ids = {
        item["evidenceId"]
        for item in state["rejected_evidence"]
        if "evidenceId" in item
    }
    used_ids = set(state["answer"]["used_evidence_ids"])

    assert rejected_ids
    assert used_ids == {item.evidence_id for item in state["verified_evidence"]}
    assert rejected_ids.isdisjoint(used_ids)


def test_answer_synthesis_stub_refuses_when_only_unverified_evidence_exists():
    state = answer_synthesis_stub(
        {
            "request_id": "req-graph-2",
            "query": "근거 없는 질문",
            "verified_evidence": [],
            "trace": [],
            "errors": [],
        }
    )

    assert state["answer"]["status"] == "blocked"
    assert state["answer"]["reason"] == "no_verified_evidence"
    assert state["answer"]["used_evidence_ids"] == []


def test_graph_state_excludes_forbidden_fields():
    state = run_query_orchestrator_pure(
        query="pdf와 xlsx 근거를 찾아줘",
        policy=_policy(),
    )

    assert set(state).isdisjoint(FORBIDDEN_STATE_FIELDS)
