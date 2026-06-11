from __future__ import annotations

from copy import deepcopy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))


def _agentops_portfolio_smoke_trace_payload() -> dict[str, object]:
    from app.capabilities.rag_orchestrator.agentops_runtime import (
        AgentOpsRequestContext,
        run_agentops_diagnostic,
    )

    trace = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-portfolio-smoke",
            query="Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            candidate_source_atom_ids=("atom-xlsx-a1",),
            request_context={"active_source_atom_ids": ("atom-xlsx-a1",)},
        ),
        source_registry={
            "atom-xlsx-a1": {
                "source_atom_id": "atom-xlsx-a1",
                "mock_source_atom": True,
                "source_family": "XLSX",
                "source_identity": "XLSX:Book.xlsx:Sheet1:A1",
                "raw_locator": {"workbook": "Book.xlsx", "sheet": "Sheet1", "cell": "A1", "range": "A1:B2"},
                "canonical_citation_payload": {"workbook": "Book.xlsx", "sheet": "Sheet1", "cell": "A1", "range": "A1:B2"},
                "normalized_text_or_value_snapshot": "Book.xlsx / Sheet1 A1: 계약금=42",
            }
        },
    )
    return trace.to_dict()


def _agentops_runtime_result(
    request,
    *,
    selected_source_atom_ids: tuple[str, ...] = ("atom-xlsx-a1",),
    evidence_bundle_ids: tuple[str, ...] = ("bundle:atom-xlsx-a1",),
    tool_call_sequence: tuple[str, ...] = ("rag.l0.query_routing", "rag.l4.sourceatom_hydration"),
    runtime_contract_violation: bool = False,
    answer_allowed_by_policy: bool = True,
    fail_closed_reason: str = "",
    blocked_reason: str = "",
    response_policy_bucket: str = "ANSWER_ALLOWED",
):
    from app.capabilities.rag_orchestrator.agent_runtime import AgentRuntimeResult

    return AgentRuntimeResult(
        run_id=request.run_id,
        query_id=request.query_id,
        diagnostic_case_id="",
        route_lane="USER_LOCATOR",
        agent_route="tool_registry",
        final_answer="unsafe raw answer should not be persisted",
        selected_source_atom_ids=selected_source_atom_ids,
        evidence_bundle_ids=evidence_bundle_ids,
        trace_rows=(),
        tool_call_sequence=list(tool_call_sequence),
        runtime_contract_violation=runtime_contract_violation,
        fail_closed_reason=fail_closed_reason,
        blocked_reason=blocked_reason,
        locator_resolution_bucket="LOCATION_FOUND",
        locator_bounds_answerability="answerable",
        response_policy_bucket=response_policy_bucket,
        answer_allowed_by_policy=answer_allowed_by_policy,
        user_clarification_required=False,
        ambiguity_requires_clarification=False,
        active_context_required=False,
        active_context_present=True,
        deictic_query=False,
        page_only_locator=False,
        sheet_only_locator=False,
        final_answer_policy="answer_allowed" if answer_allowed_by_policy else "fail_closed",
        evidence_truth_source="source_atom_evidence_bundle" if evidence_bundle_ids else "none",
        abstained=not answer_allowed_by_policy,
    )


def test_agentops_tool_registry_maps_existing_capabilities_and_boundaries() -> None:
    from app.capabilities.rag_orchestrator.agentops_runtime import build_agentops_tool_registry

    registry = build_agentops_tool_registry()
    specs = {spec.name: spec for spec in registry}

    assert set(specs) == {
        "retrieve_txt_corpus",
        "retrieve_xlsx_table",
        "retrieve_pdf_ocr",
        "validate_evidence",
        "classify_answerability",
        "generate_eval_report",
    }
    for spec in specs.values():
        payload = spec.to_dict()
        assert payload["name"] == spec.name
        assert payload["description"]
        assert payload["inputExpectation"]
        assert payload["outputExpectation"]
        assert payload["allowedNamespaces"]
        assert payload["diagnosticOnly"] is True
        assert payload["official"] is False
        assert "production" not in " ".join(payload["allowedNamespaces"]).lower()

    assert specs["retrieve_txt_corpus"].allowed_source_families == ("TEXT",)
    assert specs["retrieve_xlsx_table"].allowed_source_families == ("XLSX",)
    assert specs["retrieve_pdf_ocr"].allowed_source_families == ("PDF",)
    assert specs["validate_evidence"].evidence_required is True
    assert specs["classify_answerability"].evidence_required is True
    assert specs["generate_eval_report"].mapped_runtime_layers == ("report.json", "status.jsonl")


def test_agentops_policy_uses_conservative_diagnostic_and_fail_closed_decisions() -> None:
    from app.capabilities.rag_orchestrator.agentops_runtime import (
        AgentOpsPolicy,
        AgentOpsRequestContext,
    )

    policy = AgentOpsPolicy()

    allowed = policy.decide(
        AgentOpsRequestContext(
            run_id="agentops-test",
            query="Sheet1 A1 값을 알려줘",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
        )
    )
    assert allowed.allowed is True
    assert allowed.fail_closed is False
    assert allowed.diagnostic_only is True
    assert allowed.policy_decision == "allow_diagnostic"
    assert "retrieve_xlsx_table" in allowed.selected_tools

    official_requested = policy.decide(
        AgentOpsRequestContext(
            run_id="agentops-test",
            query="공식 지표로 평가해줘",
            source_family="PDF",
            namespace="rag-data-all-source-citable-nonprod-v1",
            official_requested=True,
        )
    )
    assert official_requested.allowed is False
    assert official_requested.diagnostic_only is True
    assert official_requested.policy_decision == "fail_closed"
    assert official_requested.fail_closed is True
    assert official_requested.failure_category == "official_policy_not_opened"

    namespace_blocked = policy.decide(
        AgentOpsRequestContext(
            run_id="agentops-test",
            query="answer",
            source_family="TEXT",
            namespace="prod-rag-index",
        )
    )
    assert namespace_blocked.allowed is False
    assert namespace_blocked.fail_closed is True
    assert namespace_blocked.failure_category == "namespace_mismatch"

    missing_evidence = policy.decide(
        AgentOpsRequestContext(
            run_id="agentops-test",
            query="validate",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            requested_tools=("validate_evidence",),
        )
    )
    assert missing_evidence.allowed is False
    assert missing_evidence.fail_closed is True
    assert missing_evidence.failure_category == "missing_evidence"

    evidence_only = policy.decide(
        AgentOpsRequestContext(
            run_id="agentops-test",
            query="validate",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            requested_tools=("validate_evidence",),
            evidence_ids=("bundle:atom-xlsx-a1",),
        )
    )
    assert evidence_only.allowed is False
    assert evidence_only.fail_closed is True
    assert evidence_only.failure_category == "unsupported_evidence_only_tool_path"


def test_agentops_policy_blocks_context_override_and_non_read_only_indexing_scope() -> None:
    from app.capabilities.rag_orchestrator.agentops_runtime import (
        AgentOpsPolicy,
        AgentOpsRequestContext,
    )

    policy = AgentOpsPolicy()
    override = policy.decide(
        AgentOpsRequestContext(
            run_id="agentops-test",
            query="answer",
            source_family="TEXT",
            namespace="rag-data-all-source-citable-nonprod-v1",
            request_context={"namespace": "prod-rag-index"},
        )
    )
    assert override.allowed is False
    assert override.fail_closed is True
    assert override.failure_category == "reserved_request_context_key"

    malformed_context = policy.decide(
        AgentOpsRequestContext(
            run_id="agentops-test",
            query="answer",
            source_family="TEXT",
            namespace="rag-data-all-source-citable-nonprod-v1",
            request_context="C:/Users/sfr99/raw-request-context namespace=prod-rag-index",  # type: ignore[arg-type]
        )
    )
    assert malformed_context.allowed is False
    assert malformed_context.fail_closed is True
    assert malformed_context.failure_category == "request_context_malformed"

    for scope in ("prod_source_derived_write", "nonprod_source_derived_read_write"):
        decision = policy.decide(
            AgentOpsRequestContext(
                run_id="agentops-test",
                query="answer",
                source_family="TEXT",
                namespace="rag-data-all-source-citable-nonprod-v1",
                indexing_scope=scope,
            )
        )
        assert decision.allowed is False
        assert decision.fail_closed is True
        assert decision.failure_category == "indexing_scope_blocked"


def test_agentops_policy_blocks_unsafe_answer_format_requirement() -> None:
    from app.capabilities.rag_orchestrator.agentops_runtime import AgentOpsPolicy, AgentOpsRequestContext

    decision = AgentOpsPolicy().decide(
        AgentOpsRequestContext(
            run_id="agentops-answer-format",
            query="Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            answer_format_requirement="raw_answer_without_citations",
        )
    )

    assert decision.allowed is False
    assert decision.fail_closed is True
    assert decision.failure_category == "answer_format_blocked"


def test_agentops_runtime_blocks_malformed_request_context_before_tool_calls() -> None:
    from jsonschema import Draft202012Validator
    from app.capabilities.rag_orchestrator.agentops_runtime import AgentOpsRequestContext, run_agentops_diagnostic

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    trace = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-malformed-request-context",
            query="Book.xlsx Sheet1 A1 값",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            candidate_source_atom_ids=("atom-xlsx-a1",),
            request_context="C:/Users/sfr99/raw-request-context namespace=prod-rag-index",  # type: ignore[arg-type]
        ),
        source_registry={
            "atom-xlsx-a1": {
                "source_atom_id": "atom-xlsx-a1",
                "mock_source_atom": True,
                "source_family": "XLSX",
                "source_identity": "XLSX:Secret.xlsx:Sheet1:A1",
            }
        },
    ).to_dict()
    serialized = json.dumps(trace, ensure_ascii=False)

    assert trace["policy_decision"] == "fail_closed"
    assert trace["final_decision"] == "fail_closed"
    assert trace["failure_category"] == "request_context_malformed"
    assert trace["retry_repair_fallback"]["failure_category"] == "request_context_malformed"
    assert trace["tools_called"] == []
    assert trace["evidence_ids"] == []
    assert "raw-request-context" not in serialized
    assert "prod-rag-index" not in serialized
    assert "C:/Users" not in serialized
    assert "XLSX:Secret" not in serialized
    assert sorted(validator.iter_errors(trace), key=lambda error: error.path) == []


def test_agentops_context_rejects_blank_run_id_before_trace_emit() -> None:
    from app.capabilities.rag_orchestrator.agentops_runtime import AgentOpsRequestContext

    with pytest.raises(ValueError, match="run_id"):
        AgentOpsRequestContext(
            run_id=" ",
            query="report status",
            source_family="PDF",
            namespace="ai/eval/reports/rag-ingestion/runs",
            requested_tools=("generate_eval_report",),
        )


def test_agentops_context_rejects_unsafe_run_id_before_trace_emit() -> None:
    from app.capabilities.rag_orchestrator.agentops_runtime import AgentOpsRequestContext

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["run_id"]["pattern"] == r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"

    safe = AgentOpsRequestContext(
        run_id="agentops-safe_01.v1",
        query="report status",
        source_family="PDF",
        namespace="ai/eval/reports/rag-ingestion/runs",
        requested_tools=("generate_eval_report",),
    )
    assert safe.run_id == "agentops-safe_01.v1"
    safe_query_id = AgentOpsRequestContext(
        run_id="agentops-safe-run",
        query_id="agentops-safe-query_01.v1",
        query="report status",
        source_family="PDF",
        namespace="ai/eval/reports/rag-ingestion/runs",
        requested_tools=("generate_eval_report",),
    )
    assert safe_query_id.query_id == "agentops-safe-query_01.v1"

    for unsafe_run_id in (
        "C:/Users/sfr99/raw-agentops-report",
        "..\\secret-agentops-trace",
        "agentops raw prompt",
        "agentops\nraw",
    ):
        with pytest.raises(ValueError, match="run_id"):
            AgentOpsRequestContext(
                run_id=unsafe_run_id,
                query="report status",
                source_family="PDF",
                namespace="ai/eval/reports/rag-ingestion/runs",
                requested_tools=("generate_eval_report",),
            )

    for unsafe_query_id in (
        "C:/Users/sfr99/raw-runtime-trace",
        "..\\secret-agentops-query",
        "agentops raw query id",
        "agentops\nraw-query",
    ):
        with pytest.raises(ValueError, match="query_id"):
            AgentOpsRequestContext(
                run_id="agentops-safe-run",
                query_id=unsafe_query_id,
                query="report status",
                source_family="PDF",
                namespace="ai/eval/reports/rag-ingestion/runs",
                requested_tools=("generate_eval_report",),
            )


def test_agentops_normalizes_partial_retrieval_tool_requests_to_runtime_chain() -> None:
    from app.capabilities.rag_orchestrator.agentops_runtime import AgentOpsPolicy, AgentOpsRequestContext

    decision = AgentOpsPolicy().decide(
        AgentOpsRequestContext(
            run_id="agentops-partial-request",
            query="Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            requested_tools=("retrieve_xlsx_table",),
            candidate_source_atom_ids=("atom-xlsx-a1",),
        )
    )

    assert decision.allowed is True
    assert decision.selected_tools == (
        "retrieve_xlsx_table",
        "validate_evidence",
        "classify_answerability",
    )


def test_agentops_report_only_tool_does_not_require_candidate_scope() -> None:
    from app.capabilities.rag_orchestrator.agentops_runtime import (
        AgentOpsRequestContext,
        run_agentops_diagnostic,
    )

    trace = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-report-only",
            query="report status",
            source_family="PDF",
            namespace="ai/eval/reports/rag-ingestion/runs",
            requested_tools=("generate_eval_report",),
        ),
        source_registry={},
    ).to_dict()

    assert trace["selected_tools"] == ["generate_eval_report"]
    assert trace["tools_called"] == []
    assert trace["evidence_ids"] == []
    assert trace["policy_decision"] == "allow_diagnostic"
    assert trace["final_decision"] == "diagnostic_only_handoff"
    assert trace["failure_category"] == ""


def test_agentops_runtime_emits_run_trace_without_opening_gold_labels() -> None:
    from app.capabilities.rag_orchestrator.agentops_runtime import (
        AGENTOPS_TRACE_SCHEMA_VERSION,
    )

    payload = _agentops_portfolio_smoke_trace_payload()

    assert payload["schema_version"] == AGENTOPS_TRACE_SCHEMA_VERSION
    assert payload["run_id"] == "agentops-portfolio-smoke"
    assert re.fullmatch(r"query_ref:[0-9a-f]{16}", str(payload["query"]))
    assert str(payload["query"]) != "sha256:8486028a5ce05ee5c3aacd446a2c33e389396f5cd88a4b6c228dfe071faac7ed"
    assert payload["retrieval_namespace"] == "rag-data-all-source-citable-nonprod-v1"
    assert payload["indexing_scope"] == "nonprod_source_derived_read_only"
    assert payload["selected_tools"] == [
        "retrieve_xlsx_table",
        "validate_evidence",
        "classify_answerability",
    ]
    assert payload["tools_called"]
    assert payload["evidence_ids"] == ["evidence_ref:01"]
    assert payload["answerability_label"] == "diagnostic_answerable_from_bounds"
    assert payload["answerability_label_source"] == "machine_policy_not_gold"
    assert payload["relevance_label"] == ""
    assert payload["relevance_label_source"] == "not_evaluated_without_user_gold"
    assert payload["policy_decision"] == "allow_diagnostic"
    assert payload["diagnostic_only"] is True
    assert payload["final_decision"] == "diagnostic_only_answer"
    assert payload["report_artifact_path"] == "reports/portfolio_agentops_report.md"
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "Book.xlsx" not in serialized
    assert "Sheet1" not in serialized
    assert "A1" not in serialized
    assert "계약금=42" not in serialized


def test_agentops_trace_schema_and_sample_match_runtime_contract() -> None:
    from jsonschema import Draft202012Validator
    from app.capabilities.rag_orchestrator.agentops_runtime import (
        AgentOpsRequestContext,
        run_agentops_diagnostic,
    )

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    sample = json.loads((ROOT / "reports" / "agentops_sample_trace.json").read_text(encoding="utf-8"))
    payload = _agentops_portfolio_smoke_trace_payload()
    unsupported_tool_payload = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-unsupported-tool",
            query="raw unsupported tool call",
            source_family="TEXT",
            namespace="rag-data-all-source-citable-nonprod-v1",
            requested_tools=("dump_raw_prompt",),
        ),
        source_registry={},
    ).to_dict()
    mixed_unsupported_tool_payload = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-mixed-unsupported-tool",
            query="known and unknown tool call",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            requested_tools=("retrieve_xlsx_table", "dump_raw_prompt"),
            candidate_source_atom_ids=("atom-xlsx-a1",),
        ),
        source_registry={},
    ).to_dict()

    assert schema["$id"] == (
        "https://github.com/sfr9802/async-ai-document-pipeline-with-domain-rag/blob/main/"
        "docs/agentops_trace_schema.json"
    )
    assert schema["properties"]["policy_decision"]["enum"] == ["allow_diagnostic", "fail_closed"]
    assert sample == payload

    errors = sorted(Draft202012Validator(schema).iter_errors(sample), key=lambda error: error.path)
    assert errors == []
    blocked_errors = sorted(
        Draft202012Validator(schema).iter_errors(unsupported_tool_payload),
        key=lambda error: error.path,
    )
    assert blocked_errors == []
    assert unsupported_tool_payload["policy_decision"] == "fail_closed"
    assert unsupported_tool_payload["failure_category"] == "unsupported_tool"
    assert unsupported_tool_payload["selected_tools"] == []
    mixed_blocked_errors = sorted(
        Draft202012Validator(schema).iter_errors(mixed_unsupported_tool_payload),
        key=lambda error: error.path,
    )
    assert mixed_blocked_errors == []
    assert mixed_unsupported_tool_payload["policy_decision"] == "fail_closed"
    assert mixed_unsupported_tool_payload["failure_category"] == "unsupported_tool"
    assert mixed_unsupported_tool_payload["tools_called"] == []
    assert mixed_unsupported_tool_payload["selected_tools"] == []


def test_agentops_trace_schema_rejects_policy_boundary_drift() -> None:
    from jsonschema import Draft202012Validator
    from app.capabilities.rag_orchestrator.agentops_runtime import AgentOpsRequestContext, run_agentops_diagnostic

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    payload = _agentops_portfolio_smoke_trace_payload()
    validator = Draft202012Validator(schema)

    def assert_rejected(mutated: dict[str, object]) -> None:
        errors = sorted(validator.iter_errors(mutated), key=lambda error: error.path)
        assert errors

    top_level_prod_namespace = deepcopy(payload)
    top_level_prod_namespace["retrieval_namespace"] = "prod-rag-index"
    assert_rejected(top_level_prod_namespace)

    context_prod_namespace = deepcopy(payload)
    context_prod_namespace["request_context"]["namespace"] = "prod-rag-index"  # type: ignore[index]
    assert_rejected(context_prod_namespace)

    top_level_write_scope = deepcopy(payload)
    top_level_write_scope["indexing_scope"] = "nonprod_source_derived_read_write"
    assert_rejected(top_level_write_scope)

    context_write_scope = deepcopy(payload)
    context_write_scope["request_context"]["indexing_scope"] = "nonprod_source_derived_read_write"  # type: ignore[index]
    assert_rejected(context_write_scope)

    raw_answer_format = deepcopy(payload)
    raw_answer_format["request_context"]["answer_format_requirement"] = "raw_answer_without_citations"  # type: ignore[index]
    assert_rejected(raw_answer_format)

    unsupported_family = deepcopy(payload)
    unsupported_family["request_context"]["source_family"] = "IMAGE"  # type: ignore[index]
    assert_rejected(unsupported_family)

    unsafe_policy_context_trace = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-unsafe-policy-context",
            query="raw prompt must become an opaque query ref",
            source_family="C:/Users/sfr99/raw-source-family.txt",
            namespace="D:/async-ocr-rag-multimodal-pipeline/raw-namespace.txt",
            indexing_scope="../prod_source_derived_write",
            answer_format_requirement="raw_answer_without_citations C:/Users/sfr99/raw-format.txt",
        ),
        source_registry={},
    ).to_dict()
    serialized = json.dumps(unsafe_policy_context_trace, ensure_ascii=False)

    assert unsafe_policy_context_trace["policy_decision"] == "fail_closed"
    assert unsafe_policy_context_trace["final_decision"] == "fail_closed"
    assert unsafe_policy_context_trace["failure_category"] == "unsupported_source_family"
    assert unsafe_policy_context_trace["retrieval_namespace"] == "UNSUPPORTED_NAMESPACE"
    assert unsafe_policy_context_trace["indexing_scope"] == "UNSUPPORTED_INDEXING_SCOPE"
    assert unsafe_policy_context_trace["request_context"] == {
        "source_family": "UNSUPPORTED_SOURCE_FAMILY",
        "namespace": "UNSUPPORTED_NAMESPACE",
        "indexing_scope": "UNSUPPORTED_INDEXING_SCOPE",
        "answer_format_requirement": "UNSUPPORTED_ANSWER_FORMAT_REQUIREMENT",
        "official_requested": False,
    }
    assert sorted(validator.iter_errors(unsafe_policy_context_trace), key=lambda error: error.path) == []
    for raw_fragment in (
        "C:/Users",
        "D:/async-ocr-rag-multimodal-pipeline",
        "raw-source-family",
        "raw-namespace",
        "raw_answer_without_citations",
        "raw-format",
        "../prod_source",
    ):
        assert raw_fragment not in serialized

    raw_fail_closed_context = deepcopy(unsafe_policy_context_trace)
    raw_fail_closed_context["request_context"]["namespace"] = "C:/Users/sfr99/raw-namespace.txt"  # type: ignore[index]
    assert_rejected(raw_fail_closed_context)

    raw_fail_closed_top_level = deepcopy(unsafe_policy_context_trace)
    raw_fail_closed_top_level["retrieval_namespace"] = "D:/async-ocr-rag-multimodal-pipeline/raw-namespace.txt"
    assert_rejected(raw_fail_closed_top_level)


def test_agentops_trace_schema_rejects_unknown_runtime_tool_names() -> None:
    from jsonschema import Draft202012Validator

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    payload = _agentops_portfolio_smoke_trace_payload()
    validator = Draft202012Validator(schema)

    expected_tools = {
        "rag.l0.query_routing",
        "rag.l1.coarse_candidate_generation",
        "rag.l2.file_workbook_identity",
        "rag.l3.structural_locator",
        "rag.l4.sourceatom_hydration",
        "rag.l5.evidence_bundle_assembly",
        "rag.l6.evidence_selector",
        "rag.l7.answer_ready_context",
        "rag.l8.final_llm_answer_generation",
    }
    assert set(payload["tools_called"]) == expected_tools

    unknown_tool_payload = deepcopy(payload)
    unknown_tool_payload["tools_called"] = [*payload["tools_called"], "rag.raw_prompt_dump"]
    errors = sorted(validator.iter_errors(unknown_tool_payload), key=lambda error: error.path)

    assert errors
    assert any(
        list(error.path) == ["tools_called", len(payload["tools_called"])]
        for error in errors
    )

    repeated_tool_payload = deepcopy(payload)
    repeated_tool_payload["selected_tools"] = ["retrieve_xlsx_table"] * 10
    repeated_tool_payload["tools_called"] = ["rag.l0.query_routing"] * 10
    repeated_errors = sorted(validator.iter_errors(repeated_tool_payload), key=lambda error: error.path)

    assert schema["properties"]["selected_tools"]["maxItems"] == 6
    assert schema["properties"]["selected_tools"]["uniqueItems"] is True
    assert schema["properties"]["tools_called"]["maxItems"] == 9
    assert schema["properties"]["tools_called"]["uniqueItems"] is True
    assert repeated_errors
    assert any(list(error.path) == ["selected_tools"] for error in repeated_errors)
    assert any(list(error.path) == ["tools_called"] for error in repeated_errors)


def test_agentops_trace_sanitizes_runtime_failure_category_before_persistence() -> None:
    from jsonschema import Draft202012Validator
    from app.capabilities.rag_orchestrator.agent_runtime import AgentRuntimeResult
    from app.capabilities.rag_orchestrator.agentops_runtime import AgentOpsRequestContext, run_agentops_diagnostic

    class RawFailureRuntime:
        def invoke(self, request):  # type: ignore[no-untyped-def]
            return AgentRuntimeResult(
                run_id=request.run_id,
                query_id=request.query_id,
                diagnostic_case_id="",
                route_lane="USER_LOCATOR",
                agent_route="tool_registry",
                final_answer="",
                selected_source_atom_ids=(),
                evidence_bundle_ids=(),
                trace_rows=(),
                tool_call_sequence=["rag.l0.query_routing"],
                runtime_contract_violation=False,
                fail_closed_reason="C:/Users/sfr99/AppData/Local/Temp/raw-runtime-reason.txt",
                blocked_reason="",
                locator_resolution_bucket="NO_USER_LOCATOR",
                locator_bounds_answerability="unanswerable",
                response_policy_bucket="INSUFFICIENT_EVIDENCE",
                answer_allowed_by_policy=False,
                user_clarification_required=False,
                ambiguity_requires_clarification=False,
                active_context_required=False,
                active_context_present=False,
                deictic_query=False,
                page_only_locator=False,
                sheet_only_locator=False,
                final_answer_policy="fail_closed",
                evidence_truth_source="none",
                abstained=True,
            )

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    trace = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-runtime-failure-category",
            query="Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            candidate_source_atom_ids=("atom-xlsx-a1",),
        ),
        source_registry={
            "atom-xlsx-a1": {
                "source_atom_id": "atom-xlsx-a1",
                "mock_source_atom": True,
                "source_family": "XLSX",
            }
        },
        runtime=RawFailureRuntime(),
    ).to_dict()
    serialized = json.dumps(trace, ensure_ascii=False)

    assert trace["final_decision"] == "fail_closed"
    assert trace["failure_category"] == "runtime_fail_closed"
    assert trace["retry_repair_fallback"]["failure_category"] == "runtime_fail_closed"
    assert "C:/Users" not in serialized
    assert "raw-runtime-reason" not in serialized
    assert sorted(validator.iter_errors(trace), key=lambda error: error.path) == []

    mutated = _agentops_portfolio_smoke_trace_payload()
    mutated["failure_category"] = "C:/Users/sfr99/raw-runtime-reason.txt"
    mutated["retry_repair_fallback"]["failure_category"] = "C:/Users/sfr99/raw-runtime-reason.txt"  # type: ignore[index]
    assert sorted(validator.iter_errors(mutated), key=lambda error: error.path)


def test_agentops_runtime_contract_violation_forces_fail_closed_trace() -> None:
    from jsonschema import Draft202012Validator
    from app.capabilities.rag_orchestrator.agent_runtime import AgentRuntimeResult
    from app.capabilities.rag_orchestrator.agentops_runtime import AgentOpsRequestContext, run_agentops_diagnostic

    class ContractViolationRuntime:
        def invoke(self, request):  # type: ignore[no-untyped-def]
            return AgentRuntimeResult(
                run_id=request.run_id,
                query_id=request.query_id,
                diagnostic_case_id="",
                route_lane="USER_LOCATOR",
                agent_route="tool_registry",
                final_answer="unsafe raw answer should not be persisted",
                selected_source_atom_ids=("atom-xlsx-a1",),
                evidence_bundle_ids=("bundle:atom-xlsx-a1",),
                trace_rows=(),
                tool_call_sequence=("rag.l0.query_routing", "rag.l4.sourceatom_hydration"),
                runtime_contract_violation=True,
                fail_closed_reason="CONTRACT_VIOLATION: target_locator_used C:/Users/sfr99/raw-runtime.txt",
                blocked_reason="",
                locator_resolution_bucket="LOCATION_FOUND",
                locator_bounds_answerability="answerable",
                response_policy_bucket="ANSWER_ALLOWED",
                answer_allowed_by_policy=True,
                user_clarification_required=False,
                ambiguity_requires_clarification=False,
                active_context_required=False,
                active_context_present=True,
                deictic_query=False,
                page_only_locator=False,
                sheet_only_locator=False,
                final_answer_policy="answer_allowed",
                evidence_truth_source="source_atom_evidence_bundle",
                abstained=False,
            )

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    trace = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-runtime-contract-violation",
            query="Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            candidate_source_atom_ids=("atom-xlsx-a1",),
        ),
        source_registry={
            "atom-xlsx-a1": {
                "source_atom_id": "atom-xlsx-a1",
                "mock_source_atom": True,
                "source_family": "XLSX",
                "source_identity": "XLSX:Secret.xlsx:Sheet1:A1",
            }
        },
        runtime=ContractViolationRuntime(),
    ).to_dict()
    serialized = json.dumps(trace, ensure_ascii=False)

    assert trace["final_decision"] == "fail_closed"
    assert trace["failure_category"] == "runtime_contract_violation"
    assert trace["retry_repair_fallback"]["failure_category"] == "runtime_contract_violation"
    assert trace["answerability_label"] == "diagnostic_unanswerable_from_bounds"
    assert trace["evidence_ids"] == []
    assert "unsafe raw answer" not in serialized
    assert "target_locator_used" not in serialized
    assert "C:/Users" not in serialized
    assert "XLSX:Secret" not in serialized
    assert sorted(validator.iter_errors(trace), key=lambda error: error.path) == []


def test_agentops_runtime_exception_fails_closed_without_raw_exception_leak() -> None:
    from jsonschema import Draft202012Validator
    from app.capabilities.rag_orchestrator.agentops_runtime import AgentOpsRequestContext, run_agentops_diagnostic

    class RaisingRuntime:
        def invoke(self, request):  # type: ignore[no-untyped-def]
            raise RuntimeError("C:/Users/sfr99/AppData/Local/Temp/raw-runtime-exception.txt Book.xlsx Sheet1 A1")

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    trace = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-runtime-exception",
            query="Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            candidate_source_atom_ids=("atom-xlsx-a1",),
        ),
        source_registry={
            "atom-xlsx-a1": {
                "source_atom_id": "atom-xlsx-a1",
                "mock_source_atom": True,
                "source_family": "XLSX",
                "source_identity": "XLSX:Secret.xlsx:Sheet1:A1",
            }
        },
        runtime=RaisingRuntime(),
    ).to_dict()
    serialized = json.dumps(trace, ensure_ascii=False)

    assert trace["final_decision"] == "fail_closed"
    assert trace["failure_category"] == "runtime_fail_closed"
    assert trace["retry_repair_fallback"]["failure_category"] == "runtime_fail_closed"
    assert trace["tools_called"] == []
    assert trace["evidence_ids"] == []
    assert "raw-runtime-exception" not in serialized
    assert "C:/Users" not in serialized
    assert "Book.xlsx" not in serialized
    assert "Sheet1" not in serialized
    assert "A1" not in serialized
    assert "XLSX:Secret" not in serialized
    assert sorted(validator.iter_errors(trace), key=lambda error: error.path) == []


def test_agentops_trace_fails_closed_when_evidence_reference_count_exceeds_schema_bound() -> None:
    from jsonschema import Draft202012Validator
    from app.capabilities.rag_orchestrator.agent_runtime import AgentRuntimeResult
    from app.capabilities.rag_orchestrator.agentops_runtime import AgentOpsRequestContext, run_agentops_diagnostic

    class TooManyEvidenceRuntime:
        def invoke(self, request):  # type: ignore[no-untyped-def]
            return AgentRuntimeResult(
                run_id=request.run_id,
                query_id=request.query_id,
                diagnostic_case_id="",
                route_lane="USER_LOCATOR",
                agent_route="tool_registry",
                final_answer="unsafe raw answer should not be persisted",
                selected_source_atom_ids=("atom-xlsx-a1",),
                evidence_bundle_ids=tuple(f"bundle:atom-xlsx-{index:03d}" for index in range(1, 101)),
                trace_rows=(),
                tool_call_sequence=("rag.l0.query_routing", "rag.l4.sourceatom_hydration"),
                runtime_contract_violation=False,
                fail_closed_reason="",
                blocked_reason="",
                locator_resolution_bucket="LOCATION_FOUND",
                locator_bounds_answerability="answerable",
                response_policy_bucket="ANSWER_ALLOWED",
                answer_allowed_by_policy=True,
                user_clarification_required=False,
                ambiguity_requires_clarification=False,
                active_context_required=False,
                active_context_present=True,
                deictic_query=False,
                page_only_locator=False,
                sheet_only_locator=False,
                final_answer_policy="answer_allowed",
                evidence_truth_source="source_atom_evidence_bundle",
                abstained=False,
            )

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    assert schema["properties"]["evidence_ids"]["maxItems"] == 99
    validator = Draft202012Validator(schema)
    trace = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-evidence-ref-bound",
            query="Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            candidate_source_atom_ids=("atom-xlsx-a1",),
        ),
        source_registry={
            "atom-xlsx-a1": {
                "source_atom_id": "atom-xlsx-a1",
                "mock_source_atom": True,
                "source_family": "XLSX",
                "source_identity": "XLSX:Secret.xlsx:Sheet1:A1",
            }
        },
        runtime=TooManyEvidenceRuntime(),
    ).to_dict()
    serialized = json.dumps(trace, ensure_ascii=False)

    assert trace["final_decision"] == "fail_closed"
    assert trace["failure_category"] == "runtime_contract_violation"
    assert trace["retry_repair_fallback"]["failure_category"] == "runtime_contract_violation"
    assert trace["answerability_label"] == "diagnostic_unanswerable_from_bounds"
    assert trace["evidence_ids"] == []
    assert "evidence_ref:100" not in serialized
    assert "unsafe raw answer" not in serialized
    assert "XLSX:Secret" not in serialized
    assert sorted(validator.iter_errors(trace), key=lambda error: error.path) == []


def test_agentops_trace_fails_closed_for_unknown_runtime_tool_call_names() -> None:
    from jsonschema import Draft202012Validator
    from app.capabilities.rag_orchestrator.agent_runtime import AgentRuntimeResult
    from app.capabilities.rag_orchestrator.agentops_runtime import AgentOpsRequestContext, run_agentops_diagnostic

    class UnknownToolRuntime:
        def invoke(self, request):  # type: ignore[no-untyped-def]
            return AgentRuntimeResult(
                run_id=request.run_id,
                query_id=request.query_id,
                diagnostic_case_id="",
                route_lane="USER_LOCATOR",
                agent_route="tool_registry",
                final_answer="would be unsafe to persist",
                selected_source_atom_ids=("atom-xlsx-a1",),
                evidence_bundle_ids=("bundle:atom-xlsx-a1",),
                trace_rows=(),
                tool_call_sequence=("rag.l0.query_routing", "rag.raw_prompt_dump"),
                runtime_contract_violation=False,
                fail_closed_reason="",
                blocked_reason="",
                locator_resolution_bucket="LOCATION_FOUND",
                locator_bounds_answerability="answerable",
                response_policy_bucket="ANSWER_ALLOWED",
                answer_allowed_by_policy=True,
                user_clarification_required=False,
                ambiguity_requires_clarification=False,
                active_context_required=False,
                active_context_present=True,
                deictic_query=False,
                page_only_locator=False,
                sheet_only_locator=False,
                final_answer_policy="answer_allowed",
                evidence_truth_source="source_atom_evidence_bundle",
                abstained=False,
            )

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    trace = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-runtime-tool-call-drift",
            query="Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            candidate_source_atom_ids=("atom-xlsx-a1",),
        ),
        source_registry={
            "atom-xlsx-a1": {
                "source_atom_id": "atom-xlsx-a1",
                "mock_source_atom": True,
                "source_family": "XLSX",
            }
        },
        runtime=UnknownToolRuntime(),
    ).to_dict()

    assert trace["final_decision"] == "fail_closed"
    assert trace["failure_category"] == "runtime_tool_call_drift"
    assert trace["retry_repair_fallback"]["failure_category"] == "runtime_tool_call_drift"
    assert trace["tools_called"] == ["rag.l0.query_routing"]
    assert "rag.raw_prompt_dump" not in json.dumps(trace, ensure_ascii=False)
    assert sorted(validator.iter_errors(trace), key=lambda error: error.path) == []


def test_agentops_trace_fails_closed_for_repeated_runtime_tool_call_names() -> None:
    from jsonschema import Draft202012Validator
    from app.capabilities.rag_orchestrator.agentops_runtime import AgentOpsRequestContext, run_agentops_diagnostic

    class RepeatedToolRuntime:
        def invoke(self, request):  # type: ignore[no-untyped-def]
            return _agentops_runtime_result(
                request,
                tool_call_sequence=("rag.l0.query_routing",) * 10,
            )

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    trace = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-runtime-repeated-tool-drift",
            query="Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            candidate_source_atom_ids=("atom-xlsx-a1",),
        ),
        source_registry={
            "atom-xlsx-a1": {
                "source_atom_id": "atom-xlsx-a1",
                "mock_source_atom": True,
                "source_family": "XLSX",
            }
        },
        runtime=RepeatedToolRuntime(),
    ).to_dict()

    assert trace["final_decision"] == "fail_closed"
    assert trace["failure_category"] == "runtime_tool_call_drift"
    assert trace["retry_repair_fallback"]["failure_category"] == "runtime_tool_call_drift"
    assert trace["tools_called"] == ["rag.l0.query_routing"]
    assert trace["evidence_ids"] == []
    assert sorted(validator.iter_errors(trace), key=lambda error: error.path) == []


def test_agentops_trace_fails_closed_for_post_runtime_candidate_scope_drift() -> None:
    from jsonschema import Draft202012Validator
    from app.capabilities.rag_orchestrator.agentops_runtime import AgentOpsRequestContext, run_agentops_diagnostic

    class OutOfScopeRuntime:
        def invoke(self, request):  # type: ignore[no-untyped-def]
            return _agentops_runtime_result(
                request,
                selected_source_atom_ids=("secret-atom",),
                evidence_bundle_ids=("bundle:secret-atom",),
                tool_call_sequence=("rag.l0.query_routing", "rag.l4.sourceatom_hydration"),
            )

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    trace = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-post-runtime-scope-drift",
            query="Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            candidate_source_atom_ids=("atom-xlsx-a1",),
        ),
        source_registry={
            "atom-xlsx-a1": {
                "source_atom_id": "atom-xlsx-a1",
                "mock_source_atom": True,
                "source_family": "XLSX",
                "source_identity": "XLSX:Allowed.xlsx:Sheet1:A1",
            }
        },
        runtime=OutOfScopeRuntime(),
    ).to_dict()
    serialized = json.dumps(trace, ensure_ascii=False)

    assert trace["final_decision"] == "fail_closed"
    assert trace["failure_category"] == "runtime_contract_violation"
    assert trace["retry_repair_fallback"]["failure_category"] == "runtime_contract_violation"
    assert trace["answerability_label"] == "diagnostic_unanswerable_from_bounds"
    assert trace["evidence_ids"] == []
    assert "secret-atom" not in serialized
    assert "unsafe raw answer" not in serialized
    assert "XLSX:Allowed" not in serialized
    assert sorted(validator.iter_errors(trace), key=lambda error: error.path) == []


def test_agentops_trace_blocks_unsafe_report_artifact_paths() -> None:
    from jsonschema import Draft202012Validator
    from app.capabilities.rag_orchestrator.agentops_runtime import (
        DEFAULT_REPORT_ARTIFACT_PATH,
        AgentOpsRequestContext,
        run_agentops_diagnostic,
    )

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    unsafe_paths = (
        "C:/Users/sfr99/AppData/Local/Temp/raw-agentops-report.md",
        "D:/async-ocr-rag-multimodal-pipeline/reports/raw-agentops-report.md",
        "../reports/raw-agentops-report.md",
        "reports/raw-agentops-report.md",
    )

    for unsafe_path in unsafe_paths:
        trace = run_agentops_diagnostic(
            AgentOpsRequestContext(
                run_id="agentops-unsafe-report-path",
                query="Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
                source_family="XLSX",
                namespace="rag-data-all-source-citable-nonprod-v1",
                candidate_source_atom_ids=("atom-xlsx-a1",),
            ),
            source_registry={
                "atom-xlsx-a1": {
                    "source_atom_id": "atom-xlsx-a1",
                    "mock_source_atom": True,
                    "source_family": "XLSX",
                    "source_identity": "XLSX:Book.xlsx:Sheet1:A1",
                    "raw_locator": {"workbook": "Book.xlsx", "sheet": "Sheet1", "cell": "A1"},
                    "canonical_citation_payload": {"workbook": "Book.xlsx", "sheet": "Sheet1", "cell": "A1"},
                    "normalized_text_or_value_snapshot": "Book.xlsx / Sheet1 A1: 계약금=42",
                }
            },
            report_artifact_path=unsafe_path,
        ).to_dict()
        serialized = json.dumps(trace, ensure_ascii=False)

        assert trace["final_decision"] == "fail_closed"
        assert trace["failure_category"] == "report_artifact_path_blocked"
        assert trace["report_artifact_path"] == DEFAULT_REPORT_ARTIFACT_PATH
        assert trace["tools_called"] == []
        assert unsafe_path not in serialized
        assert "C:/" not in serialized
        assert "D:/" not in serialized
        assert "Users" not in serialized
        assert sorted(validator.iter_errors(trace), key=lambda error: error.path) == []

    mutated = _agentops_portfolio_smoke_trace_payload()
    mutated["report_artifact_path"] = "reports/raw-agentops-report.md"
    assert sorted(validator.iter_errors(mutated), key=lambda error: error.path)


def test_resume_builder_importable_from_repo_root() -> None:
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-B", "-c", "import docs.portfolio.build_resume_pdf"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_portfolio_pdf_copy_tracks_opaque_agentops_trace_contract() -> None:
    source = (ROOT / "docs" / "portfolio" / "build_portfolio_pdf.py").read_text(encoding="utf-8")

    assert "sha256" not in source
    assert "hash 기반" not in source
    assert "hash로 기록" not in source
    for stale_count in range(36, 53):
        assert f"{stale_count} passed" not in source
        assert f"{stale_count}개 통과" not in source
    assert '"query": "query_ref:8a3fa83080fc7cb5"' in source
    assert '"evidence_ids": ["evidence_ref:01"]' in source
    assert "계약 테스트: 53개 통과" in source
    assert "Dense / Sparse / Hybrid 검색 실험" in source
    assert "SearchUnit/SearchView 구축" in source
    assert "Dense Retrieval" in source
    assert "Sparse Retrieval" in source
    assert "Hybrid Retrieval" in source
    assert "XLSX 예시" in source
    assert "PDF 예시" in source
    assert "TEXT 예시" in source
    assert "추가 질의 예시(PDF/XLSX/TEXT) 및 평가 관련 문서는 GitHub README에서 확인할 수 있습니다." in source
    assert "https://github.com/sfr9802/async-ai-document-pipeline-with-domain-rag/blob/main/ai/eval/README.md" in source
    assert "Actual Response Smoke" in source
    assert "answer quality metric이 아니라 response policy smoke" in source


def test_portfolio_and_resume_pdf_builders_render_artifact_text_contract(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    from docs.portfolio import build_portfolio_pdf, build_resume_pdf

    portfolio_path = build_portfolio_pdf.build_pdf(tmp_path / "portfolio.pdf")
    resume_path = build_resume_pdf.build_pdf(tmp_path / "resume.pdf")

    portfolio_doc = fitz.open(portfolio_path)
    resume_doc = fitz.open(resume_path)
    portfolio_page_texts = [page.get_text() for page in portfolio_doc]
    portfolio_text = "\n".join(portfolio_page_texts)
    resume_text = "\n".join(page.get_text() for page in resume_doc)
    combined_text = f"{portfolio_text}\n{resume_text}"

    assert portfolio_doc.page_count == 10
    assert resume_doc.page_count == 2
    assert "Evidence-Grounded RAG Backend" in portfolio_text
    assert "Evidence-Grounded Document QA Backend" not in portfolio_text
    assert "XLSX 예시" in portfolio_page_texts[1]
    assert "PDF 예시" in portfolio_page_texts[2]
    assert "TEXT 예시" in portfolio_page_texts[3]
    assert "2020년 한국 원달러 기말 환율" in portfolio_text
    assert "유우야키의 나이는 16세이고 생일은 9월 29일" in portfolio_text
    assert "추가 질의 예시(PDF/XLSX/TEXT) 및 평가 관련 문서는 GitHub README에서 확인할 수 있습니다." in portfolio_text
    assert "https://github.com/sfr9802/async-ai-document-pipeline-with-domain-rag/blob/main/ai/eval/README.md" in portfolio_text
    assert "Dense / Sparse / Hybrid 검색 실험" in portfolio_text
    assert "SearchUnit/SearchView 구축" in portfolio_text
    assert "Dense Retrieval" in portfolio_text
    assert "Sparse Retrieval" in portfolio_text
    assert "Hybrid Retrieval" in portfolio_text
    assert "Actual Response Smoke" in portfolio_text
    assert "answer quality metric이 아니라 response policy smoke" in portfolio_text
    assert "29개 승인 질의" in portfolio_text
    assert "stopped / fail_closed" in portfolio_text
    assert "53개 통과" in portfolio_text
    assert "Actual Response Smoke" in portfolio_page_texts[7]
    assert "검색 설계 포인트" in portfolio_page_texts[8]
    assert "회고" in portfolio_page_texts[9]
    assert "프로젝트를 진행하며 배운 점" in portfolio_page_texts[9]
    assert "검색 후보와 답변 근거는 다르다" in portfolio_page_texts[9]
    assert "Retrieval 성능과 Answer Quality는 별개다" in portfolio_page_texts[9]
    assert "PDF/XLSX는 일반 텍스트 검색과 다르다" in portfolio_page_texts[9]
    assert "근거 부족 시 답변 중단 정책이 중요하다" in portfolio_page_texts[9]
    assert "이번 프로젝트에서는 검색 후보, 근거 검증, 중단 정책을 분리해 설계하는 부분의 중요성을 크게 체감했습니다." in portfolio_page_texts[9]
    assert "AI 백엔드 엔지니어" in resume_text
    assert "Evidence-Grounded RAG Backend with Execution Trace" in resume_text
    assert "reports/agentops_sample_trace.json" in resume_text

    forbidden_terms = (
        "sha256",
        "Book.xlsx",
        "Sheet1",
        "계약금=42",
        "Governed RAG & AgentOps Platform",
        "production readiness",
        "product-success",
        "live-ready claim",
        "official quality metric",
        "AgentOps Platform",
        "공식 답변 품질 지표",
        "실서비스 준비 완료",
        "운영 준비 완료",
    )
    for term in forbidden_terms:
        assert term not in combined_text
    for stale_count in range(36, 53):
        assert f"{stale_count} passed" not in combined_text
        assert f"{stale_count}개 통과" not in combined_text


def test_agentops_runtime_fails_closed_for_unsupported_or_empty_evidence_path() -> None:
    from app.capabilities.rag_orchestrator.agentops_runtime import (
        AgentOpsRequestContext,
        run_agentops_diagnostic,
    )

    unsupported = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-fail-closed",
            query="이미지 파일을 분석해줘",
            source_family="IMAGE",
            namespace="rag-data-all-source-citable-nonprod-v1",
        ),
        source_registry={},
    ).to_dict()

    assert unsupported["diagnostic_only"] is True
    assert unsupported["final_decision"] == "fail_closed"
    assert unsupported["failure_category"] == "unsupported_source_family"
    assert unsupported["evidence_ids"] == []

    empty_evidence = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-empty-evidence",
            query="문서 근거로 답해줘",
            source_family="TEXT",
            namespace="rag-data-all-source-citable-nonprod-v1",
        ),
        source_registry={},
    ).to_dict()

    assert empty_evidence["diagnostic_only"] is True
    assert empty_evidence["final_decision"] == "fail_closed"
    assert empty_evidence["failure_category"] == "no_candidate_evidence_scope"
    assert empty_evidence["retry_repair_fallback"]["max_retry_count"] == 1
    assert empty_evidence["retry_repair_fallback"]["unbounded_retry_allowed"] is False


def test_agentops_runtime_blocks_invalid_candidate_scope_before_tool_calls() -> None:
    from jsonschema import Draft202012Validator
    from app.capabilities.rag_orchestrator.agentops_runtime import (
        AgentOpsRequestContext,
        run_agentops_diagnostic,
    )

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    base_context = {
        "query": "Book.xlsx Sheet1 A1 값",
        "source_family": "XLSX",
        "namespace": "rag-data-all-source-citable-nonprod-v1",
        "candidate_source_atom_ids": ("atom-xlsx-a1",),
    }

    missing_candidate = run_agentops_diagnostic(
        AgentOpsRequestContext(run_id="agentops-missing-candidate", **base_context),
        source_registry={},
    ).to_dict()
    missing_family_candidate = run_agentops_diagnostic(
        AgentOpsRequestContext(run_id="agentops-missing-family-candidate", **base_context),
        source_registry={
            "atom-xlsx-a1": {
                "source_atom_id": "atom-xlsx-a1",
                "mock_source_atom": True,
                "source_identity": "XLSX:Secret.xlsx:Sheet1:A1",
                "raw_locator": {"workbook": "Secret.xlsx", "sheet": "Sheet1", "cell": "A1"},
                "canonical_citation_payload": {"workbook": "Secret.xlsx", "sheet": "Sheet1", "cell": "A1"},
                "normalized_text_or_value_snapshot": "secret value",
            }
        },
    ).to_dict()
    wrong_family_candidate = run_agentops_diagnostic(
        AgentOpsRequestContext(run_id="agentops-wrong-family-candidate", **base_context),
        source_registry={
            "atom-xlsx-a1": {
                "source_atom_id": "atom-xlsx-a1",
                "mock_source_atom": True,
                "source_family": "PDF",
                "source_identity": "PDF:Secret.pdf:page1",
                "raw_locator": {"source_pdf_path": "Secret.pdf", "page": 1},
                "canonical_citation_payload": {"source_pdf_path": "Secret.pdf", "page": 1},
                "normalized_text_or_value_snapshot": "secret value",
            }
        },
    ).to_dict()
    try:
        non_mapping_candidate = run_agentops_diagnostic(
            AgentOpsRequestContext(run_id="agentops-non-mapping-candidate", **base_context),
            source_registry={"atom-xlsx-a1": "XLSX:Secret.xlsx:Sheet1:A1"},  # type: ignore[dict-item]
        ).to_dict()
    except AttributeError as exc:
        pytest.fail(f"non-mapping candidate records must fail closed before runtime, not crash: {exc}")

    for trace, category in (
        (missing_candidate, "candidate_scope_missing"),
        (missing_family_candidate, "candidate_scope_source_family_mismatch"),
        (wrong_family_candidate, "candidate_scope_source_family_mismatch"),
        (non_mapping_candidate, "candidate_scope_source_family_mismatch"),
    ):
        serialized = json.dumps(trace, ensure_ascii=False)

        assert trace["policy_decision"] == "fail_closed"
        assert trace["final_decision"] == "fail_closed"
        assert trace["failure_category"] == category
        assert trace["tools_called"] == []
        assert trace["evidence_ids"] == []
        assert trace["retry_repair_fallback"]["failure_category"] == category
        assert sorted(validator.iter_errors(trace), key=lambda error: error.path) == []
        assert "atom-xlsx-a1" not in serialized
        assert "Secret.pdf" not in serialized
        assert "Secret.xlsx" not in serialized
        assert "secret value" not in serialized
        assert "XLSX:Secret" not in serialized
        assert "LOCATION_NOT_FOUND" not in serialized


def test_agentops_runtime_blocks_malformed_source_registry_before_tool_calls() -> None:
    from jsonschema import Draft202012Validator
    from app.capabilities.rag_orchestrator.agentops_runtime import (
        AgentOpsRequestContext,
        run_agentops_diagnostic,
    )

    schema = json.loads((ROOT / "docs" / "agentops_trace_schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    trace = run_agentops_diagnostic(
        AgentOpsRequestContext(
            run_id="agentops-malformed-source-registry",
            query="Book.xlsx Sheet1 A1 값",
            source_family="XLSX",
            namespace="rag-data-all-source-citable-nonprod-v1",
            candidate_source_atom_ids=("atom-xlsx-a1",),
        ),
        source_registry="atom-xlsx-a1 C:/Users/sfr99/raw-source-registry.txt XLSX:Secret.xlsx:Sheet1:A1",  # type: ignore[arg-type]
    ).to_dict()
    serialized = json.dumps(trace, ensure_ascii=False)

    assert trace["final_decision"] == "fail_closed"
    assert trace["failure_category"] == "source_atom_store_unavailable"
    assert trace["retry_repair_fallback"]["failure_category"] == "source_atom_store_unavailable"
    assert trace["tools_called"] == []
    assert trace["evidence_ids"] == []
    assert "raw-source-registry" not in serialized
    assert "C:/Users" not in serialized
    assert "XLSX:Secret" not in serialized
    assert sorted(validator.iter_errors(trace), key=lambda error: error.path) == []


def test_gitignore_keeps_agentops_report_exceptions_narrow() -> None:
    tracked_report = subprocess.run(
        ["git", "check-ignore", "-q", "reports/portfolio_agentops_report.md"],
        cwd=ROOT,
    )
    tracked_sample = subprocess.run(
        ["git", "check-ignore", "-q", "reports/agentops_sample_trace.json"],
        cwd=ROOT,
    )
    unrelated_report_payload = subprocess.run(
        ["git", "check-ignore", "-q", "reports/unrequested_agentops_payload.bin"],
        cwd=ROOT,
    )

    assert tracked_report.returncode == 1
    assert tracked_sample.returncode == 1
    assert unrelated_report_payload.returncode == 0
