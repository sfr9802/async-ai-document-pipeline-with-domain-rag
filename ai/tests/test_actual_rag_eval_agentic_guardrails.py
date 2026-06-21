from __future__ import annotations

import pytest

from ai.eval import actual_rag_eval
from ai.eval.actual_rag_eval import DatasetSchemaError, validate_actual_rag_guardrails
from ai.tests.actual_rag_eval_helpers import _minimal_agentic_planner_guardrail_summary


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("retrieval_executed", True, "retrieval_executed"),
        ("tool_call_executed", True, "tool_call_executed"),
        ("llm_retry_executed", True, "llm_retry_executed"),
        ("extra_query_count_executed", 1, "extra_query_count_executed"),
        ("tool_call_count_executed", 1, "tool_call_count_executed"),
        ("llm_retry_count_executed", 1, "llm_retry_count_executed"),
    ],
)
def test_validate_actual_rag_guardrails_rejects_agentic_planner_execution_mutation(
    field: str,
    value: object,
    match: str,
) -> None:
    summary = _minimal_agentic_planner_guardrail_summary()
    planner = summary["agentic_planner_dry_run"]
    assert isinstance(planner, dict)
    planner["planner_execution"][field] = value

    with pytest.raises(DatasetSchemaError, match=match):
        validate_actual_rag_guardrails(summary)


def test_validate_actual_rag_guardrails_rejects_agentic_planner_gate_mutation() -> None:
    summary = _minimal_agentic_planner_guardrail_summary()
    planner = summary["agentic_planner_dry_run"]
    assert isinstance(planner, dict)
    planner["gate_after_unchanged_because_dry_run"] = {"allowed_answer_count": 6}

    with pytest.raises(DatasetSchemaError, match="gate_after"):
        validate_actual_rag_guardrails(summary)


def test_validate_actual_rag_guardrails_rejects_agentic_planner_executed_decision() -> None:
    summary = _minimal_agentic_planner_guardrail_summary()
    planner = summary["agentic_planner_dry_run"]
    assert isinstance(planner, dict)
    planner["decisions"][0]["executed"] = True

    with pytest.raises(DatasetSchemaError, match="executed"):
        validate_actual_rag_guardrails(summary)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("broader_agent_loop_ready", True, "broader_agent_loop_ready"),
        ("broader_agent_loop_opened", True, "broader_agent_loop_opened"),
        ("production_routing_opened", True, "production_routing_opened"),
        ("raw_prompt_payload_written", True, "raw_prompt_payload_written"),
        ("raw_response_payload_written", True, "raw_response_payload_written"),
        ("retrieved_context_only_citation_promoted", True, "retrieved_context_only_citation_promoted"),
        ("gate_loosened", True, "gate_loosened"),
        (
            "gold_or_qrels_or_labels_or_expected_or_denominator_mutation",
            True,
            "gold_or_qrels_or_labels_or_expected_or_denominator_mutation",
        ),
    ],
)
def test_validate_actual_rag_guardrails_rejects_agentic_loop_review_opening(
    field: str,
    value: object,
    match: str,
) -> None:
    summary = _minimal_agentic_planner_guardrail_summary()
    summary["agentic_loop_review"] = actual_rag_eval.build_agentic_loop_review(summary)
    assert summary["agentic_loop_review"]["broader_agent_loop_ready"] is False
    validate_actual_rag_guardrails(summary)
    assert isinstance(summary["agentic_loop_review"], dict)
    summary["agentic_loop_review"][field] = value

    with pytest.raises(DatasetSchemaError, match=match):
        validate_actual_rag_guardrails(summary)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("query_id_used_for_planner_selection", True, "query_id_used_for_planner_selection"),
        ("row_id_used_for_planner_selection", True, "row_id_used_for_planner_selection"),
        ("target_id_used_for_planner_selection", True, "target_id_used_for_planner_selection"),
        ("expected_fields_used_for_planner_selection", True, "expected_fields_used_for_planner_selection"),
        ("qrels_used_for_planner_selection", True, "qrels_used_for_planner_selection"),
        ("labels_used_for_planner_selection", True, "labels_used_for_planner_selection"),
        ("baseline_topk_or_legacy_outputs_used", True, "baseline_topk_or_legacy_outputs_used"),
        ("row_specific_alias_or_shortcut_used", True, "row_specific_alias_or_shortcut_used"),
        ("retrieval_executed", True, "retrieval_executed"),
        ("tool_call_executed", True, "tool_call_executed"),
        ("llm_retry_executed", True, "llm_retry_executed"),
        ("raw_prompt_payload_written", True, "raw_prompt_payload_written"),
        ("raw_response_payload_written", True, "raw_response_payload_written"),
        ("evidence_gate_loosened", True, "evidence_gate_loosened"),
        ("retrieved_context_only_citation_promoted", True, "retrieved_context_only_citation_promoted"),
        ("official_metric", True, "official_metric"),
    ],
)
def test_validate_actual_rag_guardrails_rejects_forbidden_agentic_planner_flags(
    field: str,
    value: object,
    match: str,
) -> None:
    guardrail_flags = {
        "gold_or_qrels_mutation": False,
        "expected_fields_used_for_planner_selection": False,
        "query_id_used_for_planner_selection": False,
        "row_id_used_for_planner_selection": False,
        "target_id_used_for_planner_selection": False,
        "qrels_used_for_planner_selection": False,
        "labels_used_for_planner_selection": False,
        "baseline_topk_or_legacy_outputs_used": False,
        "row_specific_alias_or_shortcut_used": False,
        "retrieval_executed": False,
        "tool_call_executed": False,
        "llm_retry_executed": False,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "evidence_gate_loosened": False,
        "retrieved_context_only_citation_promoted": False,
        "official_metric": False,
        "production_routing_opened": False,
        "protected_namespace_mutation": False,
    }
    guardrail_flags[field] = value
    planner = {
        "schema_version": "actual_rag_eval.agentic_planner_dry_run.v1",
        "planner_enabled": True,
        "planner_mode": "dry-run",
        "planner_version": "actual_rag_eval.agentic_planner_dry_run.v1",
        "ran_after_selected_evidence_composer": True,
        "ran_after_evidence_gate": True,
        "planner_decision_count": 1,
        "planner_action_counts": {"deterministic_abstain": 1},
        "planner_failure_class_counts": {"no_safe_action": 1},
        "planner_no_safe_action_count": 1,
        "planner_forbidden_shortcut_detected_count": 0,
        "planner_expected_extra_query_count": 0,
        "planner_expected_tool_call_count": 0,
        "planner_heuristic_risk_class": "diagnostic_probe_only",
        "official_metric": False,
        "official_metric_input_rows": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "retrieved_context_only_citation_policy": "diagnostic_only_never_promoted",
        "planner_execution": {
            "retrieval_executed": False,
            "tool_call_executed": False,
            "llm_retry_executed": False,
            "extra_query_count_executed": 0,
            "tool_call_count_executed": 0,
            "llm_retry_count_executed": 0,
        },
        "guardrail_flags": guardrail_flags,
        "gate_before": {},
        "gate_after_unchanged_because_dry_run": {},
        "decisions": [
            {
                "item_index": 0,
                "query_sha256": "sha256:test",
                "query_preview": "test",
                "failure_class": "no_safe_action",
                "proposed_action": "deterministic_abstain",
                "expected_extra_query_count": 0,
                "expected_tool_call_count": 0,
                "executed": False,
            }
        ],
    }
    summary = {
        "run_id": "guarded_planner",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
        "agentic_planner_dry_run": planner,
    }

    with pytest.raises(DatasetSchemaError, match=match):
        validate_actual_rag_guardrails(summary)


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "case_id",
        "query_id",
        "row_id",
        "target_id",
        "answerability",
        "answerability_label",
        "expected_answer",
        "expected_evidence",
        "supporting_evidence",
        "qrels",
        "label",
        "labels",
        "baseline_topk",
        "legacy_outputs",
        "source_title",
        "workbook",
        "gold_locator",
        "target_locator",
        "normalized_value",
        "formula",
        "raw_prompt_payload",
        "raw_response_payload",
    ],
)
def test_validate_actual_rag_guardrails_rejects_forbidden_agentic_planner_decision_fields(
    forbidden_key: str,
) -> None:
    planner = {
        "schema_version": "actual_rag_eval.agentic_planner_dry_run.v1",
        "planner_enabled": True,
        "planner_mode": "dry-run",
        "planner_version": "actual_rag_eval.agentic_planner_dry_run.v1",
        "ran_after_selected_evidence_composer": True,
        "ran_after_evidence_gate": True,
        "planner_decision_count": 1,
        "planner_action_counts": {"deterministic_abstain": 1},
        "planner_failure_class_counts": {"no_safe_action": 1},
        "planner_no_safe_action_count": 1,
        "planner_forbidden_shortcut_detected_count": 0,
        "planner_expected_extra_query_count": 0,
        "planner_expected_tool_call_count": 0,
        "planner_heuristic_risk_class": "diagnostic_probe_only",
        "official_metric": False,
        "official_metric_input_rows": 0,
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "retrieved_context_only_citation_policy": "diagnostic_only_never_promoted",
        "planner_execution": {
            "retrieval_executed": False,
            "tool_call_executed": False,
            "llm_retry_executed": False,
            "extra_query_count_executed": 0,
            "tool_call_count_executed": 0,
            "llm_retry_count_executed": 0,
        },
        "guardrail_flags": {
            "gold_or_qrels_mutation": False,
            "expected_fields_used_for_planner_selection": False,
            "query_id_used_for_planner_selection": False,
            "row_id_used_for_planner_selection": False,
            "target_id_used_for_planner_selection": False,
            "qrels_used_for_planner_selection": False,
            "labels_used_for_planner_selection": False,
            "baseline_topk_or_legacy_outputs_used": False,
            "row_specific_alias_or_shortcut_used": False,
            "retrieval_executed": False,
            "tool_call_executed": False,
            "llm_retry_executed": False,
            "raw_prompt_payload_written": False,
            "raw_response_payload_written": False,
            "evidence_gate_loosened": False,
            "retrieved_context_only_citation_promoted": False,
            "official_metric": False,
            "production_routing_opened": False,
            "protected_namespace_mutation": False,
        },
        "gate_before": {},
        "gate_after_unchanged_because_dry_run": {},
        "decisions": [
            {
                "item_index": 0,
                "query_sha256": "sha256:test",
                "query_preview": "test",
                "failure_class": "no_safe_action",
                "proposed_action": "deterministic_abstain",
                "expected_extra_query_count": 0,
                "expected_tool_call_count": 0,
                "executed": False,
                forbidden_key: "unsafe",
            }
        ],
    }
    summary = {
        "run_id": "guarded_planner",
        "official_metric_input_rows": 0,
        "official_metric_input_rows_created": 0,
        "official_metric_input_rows_consumed": 0,
        "protected_namespaces_touched": [],
        "raw_prompt_payload_written": False,
        "raw_response_payload_written": False,
        "guardrails": {
            "gold_mutation": False,
            "qrels_mutation": False,
            "label_mutation": False,
            "answerability_label_mutation": False,
            "expected_answer_mutation": False,
            "expected_evidence_mutation": False,
            "denominator_mutation": False,
            "retriever_ranking_improvement": False,
            "official_metric": False,
            "promotion_evidence": False,
            "product_success_evidence_allowed": False,
            "live_readiness_claim": False,
        },
        "agentic_planner_dry_run": planner,
    }

    with pytest.raises(DatasetSchemaError, match=forbidden_key):
        validate_actual_rag_guardrails(summary)
