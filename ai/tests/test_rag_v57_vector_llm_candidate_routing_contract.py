from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v57_report_preserves_v56_full_packet_retrieval_baseline_and_closed_gates() -> None:
    from ai.eval import rag_v57_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod as v57

    report = v57.build_report(root=ROOT, generated_at="2026-06-05T00:00:00Z")
    v57.check_report(report)

    assert report["logical_run_key"] == "v5_7_vector_llm_candidate_routing"
    assert report["short_run_id"] == "v5_7_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod"
    assert report["baseline_logical_run_key"] == "v5_6_full_packet_route_retrieval_comparison"
    assert report["current_resolves_to"] == "v5_6"
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows_consumed"] == 0
    assert report["official_metric_input_rows_created"] == 0
    assert report["source_official_metric_input_rows"] == 29
    assert report["route_comparison_rows"] == 29
    assert report["retrieval_metric_eligible_rows"] == 28
    assert report["answer_metric_rows"] == 0
    assert report["scored_answer_rows"] == 0
    assert report["answer_quality_metric_computed"] is False
    assert report["retrieval_quality_delta_computed"] is True
    assert report["diagnostic_retrieval_delta_only"] is True
    assert report["quality_delta_claim_supported"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["promotion_evidence"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["source_registry_mutated"] is False
    assert report["production_db_mutated"] is False
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False
    assert report["training_dataset_created"] is False
    assert report["training_manifest_jsonl_created"] is False
    assert report["fine_tuning_dataset_export_created"] is False
    assert report["fine_tuning_started"] is False
    assert report["fine_tuning_executed"] is False
    assert report["ft_a_execution"] is False
    assert report["gold_mutation"] is False
    assert report["qrels_mutation"] is False
    assert report["label_mutation"] is False
    assert report["expected_answer_mutation"] is False
    assert report["supporting_evidence_mutation"] is False
    assert report["denominator_mutation"] is False
    assert report["protected_namespaces_touched"] == []
    assert report["vector_payload_evidence_truth_violation_count"] == 0

    metrics = report["diagnostic_retrieval_delta_table"]["metrics"]
    expected_perfect = {
        "hit_at_1": 1.0,
        "hit_at_3": 1.0,
        "hit_at_5": 1.0,
        "mrr_at_5": 1.0,
        "ndcg_at_5": 1.0,
    }
    assert metrics["baseline_new"] == expected_perfect
    assert metrics["v5_7"] == expected_perfect
    assert report["quality_regression_count"] == 0
    assert report["fine_tuning_readiness_candidate_count"] == 0
    assert report["fine_tuning_dataset_export_blocked_reason"] == "diagnostic_only_no_training_export"


def test_v57_vector_payload_is_candidate_only_and_missing_index_fails_closed_without_fake_answer() -> None:
    from ai.eval import rag_v57_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod as v57

    adapter = v57.DiagnosticVectorCandidateAdapter(index=None)
    result = adapter.retrieve(
        {
            "query_id": "q-missing-index",
            "source_family": "PDF",
            "query": "ambiguous query",
            "target_search_unit_id": "su-target",
        },
        top_k=5,
    )

    assert result["status"] == "fail_closed"
    assert result["fail_closed_reason"] == "diagnostic_vector_index_unavailable"
    assert result["candidates"] == []
    assert result["answer_fallback_used"] is False
    assert result["fake_noop_answer_generated"] is False

    with pytest.raises(ValueError, match="candidate-only"):
        v57.assert_vector_payload_cannot_be_evidence_truth(
            {
                "candidate_id": "su-1",
                "payload_kind": "vector_candidate",
                "evidence_truth": True,
                "citation_locator": "forbidden-locator",
            }
        )


def test_v57_llm_adjudicator_strict_json_fail_closes_invalid_json_guard_relaxation_and_unsupported_route() -> None:
    from ai.eval import rag_v57_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod as v57

    invalid = v57.parse_llm_adjudication(
        "{not-json",
        allowed_routes={"pdf_business_ocr_mm"},
        evidence_candidate_ids={"su-1"},
        hard_guard_blocked=False,
    )
    assert invalid["parse_status"] == "invalid_json"
    assert invalid["fail_closed"] is True
    assert invalid["fail_closed_reason"] == "invalid_llm_json"

    relaxing = v57.parse_llm_adjudication(
        json.dumps(
            {
                "selected_route": "pdf_business_ocr_mm",
                "selected_candidate_id": "su-1",
                "decision": "route",
                "confidence": 0.9,
                "relax_hard_guard": True,
            }
        ),
        allowed_routes={"pdf_business_ocr_mm"},
        evidence_candidate_ids={"su-1"},
        hard_guard_blocked=True,
    )
    assert relaxing["parse_status"] == "guard_relaxation_attempt"
    assert relaxing["fail_closed"] is True
    assert relaxing["fail_closed_reason"] == "llm_guard_relaxation_attempt"

    unsupported = v57.parse_llm_adjudication(
        json.dumps(
            {
                "selected_route": "unsupported_route",
                "selected_candidate_id": "su-1",
                "decision": "route",
                "confidence": 0.9,
            }
        ),
        allowed_routes={"pdf_business_ocr_mm"},
        evidence_candidate_ids={"su-1"},
        hard_guard_blocked=False,
    )
    assert unsupported["parse_status"] == "unsupported_route"
    assert unsupported["fail_closed"] is True
    assert unsupported["raw_response_payload_written"] is False
    assert "output_hash" in unsupported


def test_v57_rejects_row_id_source_title_raw_parse_and_direct_answer_shortcuts_for_scoring() -> None:
    from ai.eval import rag_v57_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod as v57

    shortcut_rows = [
        {"signal_type": "row_id_special_case", "value": "v5_4_review_019"},
        {"signal_type": "query_id_special_case", "value": "text_namu_v2_0005"},
        {"signal_type": "source_title_shortcut", "value": "Known workbook title"},
        {"signal_type": "workbook_file_name_shortcut", "value": "election_results.xlsx"},
        {"signal_type": "raw_xlsx_query_time_parsing", "value": "A1:B2"},
        {"signal_type": "raw_pdf_query_time_parsing", "value": "page 3 bbox"},
        {"signal_type": "formula_text_evaluation", "value": "=SUM(A1:A2)"},
        {"signal_type": "direct_normalized_answer_value_matching", "value": "42"},
        {"signal_type": "target_locator_shortcut", "value": "page=3"},
        {"signal_type": "gold_locator_shortcut", "value": "sheet=A"},
        {"signal_type": "supporting_evidence_shortcut", "value": "approved evidence"},
        {"signal_type": "expected_answer_shortcut", "value": "expected"},
    ]

    decisions = [v57.evaluate_scoring_signal(row) for row in shortcut_rows]

    assert all(decision["accepted_for_route_or_candidate_scoring"] is False for decision in decisions)
    assert all(decision["blocked_reason"] for decision in decisions)
    assert all(decision["replacement_plan"] for decision in decisions)


def test_v57_regression_attribution_never_sends_retrieval_candidate_or_evidence_boundary_failures_to_ft() -> None:
    from ai.eval import rag_v57_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod as v57

    route = v57.classify_regression(
        {
            "query_id": "q-route",
            "source_family": "XLSX",
            "baseline_rank": 1,
            "v5_7_rank": None,
            "route_changed": True,
            "vector_candidates_missing": False,
            "evidence_assembly_failed": False,
            "answer_synthesis_failed": False,
            "latency_ms_delta": 10,
        }
    )
    assert route["regression_cause"] == "route_regression"
    assert route["recommended_remediation_lane"] == "bounded_llm_adjudicator_prompt_schema"
    assert route["fine_tuning_readiness_candidate"] is False

    vector = v57.classify_regression(
        {
            "query_id": "q-vector",
            "source_family": "PDF",
            "baseline_rank": 1,
            "v5_7_rank": None,
            "route_changed": False,
            "vector_candidates_missing": True,
            "evidence_assembly_failed": False,
            "answer_synthesis_failed": False,
            "latency_ms_delta": 10,
        }
    )
    assert vector["regression_cause"] == "vector_candidate_generation_regression"
    assert vector["recommended_remediation_lane"] == "vector_payload_or_index_repair"
    assert vector["fine_tuning_readiness_candidate"] is False

    answer = v57.classify_regression(
        {
            "query_id": "q-answer",
            "source_family": "TEXT",
            "baseline_rank": 1,
            "v5_7_rank": 1,
            "route_changed": False,
            "vector_candidates_missing": False,
            "evidence_assembly_failed": False,
            "answer_synthesis_failed": True,
            "citation_grounded_status": "unsupported_claim",
            "latency_ms_delta": 10,
        }
    )
    assert answer["regression_cause"] == "answer_synthesis_regression"
    assert answer["recommended_remediation_lane"] == "fine_tuning_readiness_candidate"
    assert answer["fine_tuning_readiness_candidate"] is True


def test_v57_finetuning_readiness_packet_blocks_export_and_excludes_forbidden_gold_or_raw_fields() -> None:
    from ai.eval import rag_v57_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod as v57

    candidate = v57.build_finetuning_readiness_candidate(
        {
            "row_id": "v5_4_review_999",
            "query_id": "q-answer",
            "source_family": "TEXT",
            "regression_cause": "answer_synthesis_regression",
            "evidence_available": True,
            "retrieval_hit_status": "hit_at_1",
            "citation_grounded_status": "unsupported_claim",
            "answer_failure_reason": "unsupported_claim_repeated_after_correct_retrieval",
        }
    )

    assert candidate is not None
    assert candidate["proposed_training_objective"] == "answer_synthesis"
    assert candidate["dataset_export_status"] == "blocked"
    assert candidate["training_execution_status"] == "blocked"
    assert candidate["source_disjoint_split_required"] is True
    assert candidate["user_owned_gold_label_required"] is True
    assert candidate["forbidden_field_violation_count"] == 0

    forbidden_names = {
        "target_locator",
        "gold_locator",
        "expected_answer",
        "supporting_evidence",
        "raw_local_path",
        "source_title",
        "direct_answer_value",
        "official_denominator_mutation",
        "qrels_mutation",
        "label_mutation",
        "gold_mutation",
    }
    assert forbidden_names.isdisjoint(candidate)
    assert "official_metric_input_rows" not in candidate["allowed_input_field_names"]

    assert v57.build_finetuning_readiness_candidate(
        {
            "row_id": "v5_4_review_001",
            "query_id": "q-retrieval",
            "source_family": "PDF",
            "regression_cause": "evidence_assembly_regression",
            "evidence_available": False,
            "retrieval_hit_status": "hit_at_5",
            "citation_grounded_status": "missing_evidence",
            "answer_failure_reason": "evidence_missing",
        }
    ) is None


def test_v57_written_artifacts_status_and_runner_are_additive_without_moving_current(tmp_path: Path) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_v57_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod as v57

    report = v57.build_report(root=ROOT, generated_at="2026-06-05T00:00:00Z")
    written, artifact_hashes = v57.write_report_bundle(tmp_path, report)
    v57.check_report(written, root=tmp_path)
    v57.append_status(tmp_path, written, artifact_hashes=artifact_hashes)

    expected_paths = {
        "report_json": "reports/rag_eval/rag-ingestion/runs/v5_7_vector_llm_candidate_routing/report.json",
        "route_candidate_diagnostics_jsonl": (
            "reports/rag_eval/rag-ingestion/runs/v5_7_vector_llm_candidate_routing/"
            "route_candidate_diagnostics.jsonl"
        ),
        "heuristic_inventory_jsonl": (
            "reports/rag_eval/rag-ingestion/runs/v5_7_vector_llm_candidate_routing/heuristic_inventory.jsonl"
        ),
        "quality_regression_attribution_jsonl": (
            "reports/rag_eval/rag-ingestion/runs/v5_7_vector_llm_candidate_routing/"
            "quality_regression_attribution.jsonl"
        ),
        "finetuning_readiness_candidates_jsonl": (
            "reports/rag_eval/rag-ingestion/runs/v5_7_vector_llm_candidate_routing/"
            "finetuning_readiness_candidates.jsonl"
        ),
        "vector_candidate_metrics_json": (
            "reports/rag_eval/rag-ingestion/runs/v5_7_vector_llm_candidate_routing/"
            "vector_candidate_metrics.json"
        ),
        "status_jsonl": "reports/rag_eval/rag-ingestion/status.jsonl",
    }
    assert written["artifact_paths"] == expected_paths
    for key, path in expected_paths.items():
        if key == "status_jsonl":
            continue
        assert artifact_hashes[f"{key}_sha256"] == _sha256_file(tmp_path / path)

    assert len(_read_jsonl(tmp_path / expected_paths["route_candidate_diagnostics_jsonl"])) == 29
    assert len(_read_jsonl(tmp_path / expected_paths["quality_regression_attribution_jsonl"])) == 0
    assert len(_read_jsonl(tmp_path / expected_paths["finetuning_readiness_candidates_jsonl"])) == 0
    assert len(_read_jsonl(tmp_path / expected_paths["heuristic_inventory_jsonl"])) == written["heuristic_inventory_count"]

    status_rows = _read_jsonl(tmp_path / "reports/rag_eval/rag-ingestion/status.jsonl")
    latest = status_rows[-1]
    assert latest["short_run_id"] == written["short_run_id"]
    assert latest["source_official_metric_input_rows"] == 29
    assert latest["route_comparison_rows"] == 29
    assert latest["retrieval_metric_eligible_rows"] == 28
    assert latest["answer_metric_rows"] == 0
    assert latest["quality_regression_count"] == 0
    assert latest["fine_tuning_readiness_candidate_count"] == 0
    assert latest["current_resolves_to"] == "v5_6"

    checked = runner.check_run("v5_7_vector_llm_candidate_routing")
    assert checked["short_run_id"] == written["short_run_id"]
    assert runner.check_run("current")["short_run_id"] == "v5_6_official_metric_scored_execution_and_failure_attribution_nonprod"


def test_v57_check_report_rejects_opened_gates_payload_truth_drift_and_denominator_changes() -> None:
    from ai.eval import rag_v57_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod as v57

    report = v57.build_report(root=ROOT, generated_at="2026-06-05T00:00:00Z")
    v57.check_report(report)

    for path, value, message in (
        (("diagnostic_only",), False, "diagnostic"),
        (("official_metric",), True, "official"),
        (("official_metric_input_rows",), 29, "official metric input"),
        (("official_metric_input_rows_consumed",), 29, "official metric input"),
        (("source_official_metric_input_rows",), 30, "source official"),
        (("route_comparison_rows",), 30, "route comparison"),
        (("retrieval_metric_eligible_rows",), 29, "retrieval metric"),
        (("answer_metric_rows",), 1, "answer metric"),
        (("scored_answer_rows",), 1, "scored answer"),
        (("answer_quality_metric_computed",), True, "answer quality"),
        (("quality_delta_claim_supported",), True, "quality delta"),
        (("production_db_mutated",), True, "closed gate"),
        (("source_registry_mutated",), True, "closed gate"),
        (("fine_tuning_executed",), True, "closed gate"),
        (("training_dataset_created",), True, "closed gate"),
        (("gold_mutation",), True, "closed gate"),
        (("qrels_mutation",), True, "closed gate"),
        (("protected_namespaces_touched",), ["ai/eval/eval_queries"], "protected"),
        (("vector_payload_evidence_truth_violation_count",), 1, "vector payload"),
        (("route_candidate_diagnostics", 0, "vector_payload", "evidence_truth"), True, "candidate-only"),
        (("route_candidate_diagnostics", 0, "vector_payload", "citation_locator"), "page=1", "candidate-only"),
        (("finetuning_readiness_candidates",), [{"query_id": "q", "expected_answer": "leak"}], "forbidden"),
    ):
        mutated = json.loads(json.dumps(report))
        cursor = mutated
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        with pytest.raises(ValueError, match=message):
            v57.check_report(mutated)


def test_v57_duplicate_supporting_evidence_id_stays_row_level_precision_audit_not_collapsed() -> None:
    from ai.eval import rag_v57_vector_llm_candidate_routing_with_regression_remediation_diagnostic_nonprod as v57

    report = v57.build_report(root=ROOT, generated_at="2026-06-05T00:00:00Z")
    audit = report["citation_precision_audit"]

    assert audit["duplicate_supporting_evidence_id_count"] == 1
    assert audit["duplicate_supporting_evidence_row_count"] == 2
    assert audit["collapsed_by_supporting_evidence_id"] is False
    assert audit["precision_key_uses_citation_locator_or_search_unit_id"] is True
    assert audit["row_level_precision_key_count"] == 29
