from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v6_2_source_derived_materialization_scaleout_and_denominator_reality_check"
V6_3_RUN_KEY = "v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report"
V6_4_RUN_KEY = "v6_4_e2e_coverage_and_failure_taxonomy_nonprod"
V6_5_RUN_KEY = "v6_5_retrieval_metric_unlock_packet_nonprod"
V6_5_1_RUN_KEY = "v6_5_1_gold29_actual_response_smoke_nonprod"
V6_6_RUN_KEY = "v6_6_structured_tool_operation_taxonomy_nonprod"
V6_7_RUN_KEY = "v6_7_agentic_retry_fail_closed_policy_nonprod"
V6_8_RUN_KEY = "v6_8_metric_gated_retrieval_quality_engineering_nonprod"
V6_9_RUN_KEY = "v6_9_answer_quality_gate_packet_nonprod"
V7_0_RUN_KEY = "v7_0_e2e_eval_architecture_closeout_nonprod"
ROLLBACK_KEY = "v6_1_true_rag_corpus_expansion_and_metric_split_hardening"
STATUS = "V6_2_SOURCE_DERIVED_MATERIALIZATION_SCALEOUT_DENOMINATOR_REALITY_CHECK_NONPROD_READY"
V6_1_RUN_ROOT = ROOT / "ai/eval/reports/rag-ingestion/runs" / ROLLBACK_KEY

REQUIRED_ARTIFACTS = {
    "report.json",
    "metric_results.json",
    "metric_tiers.json",
    "leakage_probe_summary.json",
    "denominator_manifest.jsonl",
    "row_eligibility_ledger.jsonl",
    "exclusion_ledger.jsonl",
    "denominator_reality_audit.json",
    "retrieval_metric_coverage.json",
    "true_rag_index_payload_schema.json",
    "true_rag_candidate_diagnostics.jsonl",
    "candidate_text_quality_audit.json",
    "materialization_coverage.json",
    "agentic_loop_trace.jsonl",
    "structured_tool_diagnostics.jsonl",
    "true_rag_bm25_index.sqlite",
}

REQUIRED_REPORT_FALSE_FIELDS = {
    "official_metric",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_routing_enabled",
    "production_db_mutated",
    "production_index_mutation",
    "production_namespace_mutated",
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "relevance_label_mutation",
    "answerability_label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "source_registry_mutated",
    "training_dataset_created",
    "fine_tuning_dataset_export_created",
    "fine_tuning_started",
    "fine_tuning_executed",
    "ft_a_execution",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
}

FORBIDDEN_TEXT_TOKENS = (
    "expected_answer",
    "supporting_evidence",
    "citation_locator",
    "target_search_unit_id",
    "query_id",
    "row_id",
    "case_id",
    "source_title",
    "source_workbook",
    "workbook=",
    "workbook:",
    "source_path",
    "raw_path",
    "local-storage",
    ".xlsx",
    ".pdf",
    "formula_text",
    "formula_evaluation",
    "normalized_value",
)


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def v62_module():
    from ai.eval import rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check as v62

    return v62


@pytest.fixture(scope="module")
def report(v62_module) -> dict[str, object]:
    built = v62_module.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    v62_module.check_report(built, root=ROOT)
    return built


def test_v62_registers_resolves_current_and_keeps_v61_as_rollback(report: dict[str, object]) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_eval_registry as registry

    assert registry.resolve_run(RUN_KEY, root=ROOT).logical_key == RUN_KEY
    assert registry.resolve_run("current", root=ROOT).logical_key in {RUN_KEY, V6_3_RUN_KEY, V6_4_RUN_KEY, V6_5_RUN_KEY, V6_5_1_RUN_KEY, V6_6_RUN_KEY, V6_7_RUN_KEY, V6_8_RUN_KEY, V6_9_RUN_KEY, V7_0_RUN_KEY}
    assert runner.DEFAULT_RUN_KEY in {RUN_KEY, V6_3_RUN_KEY, V6_4_RUN_KEY, V6_5_RUN_KEY, V6_5_1_RUN_KEY, V6_6_RUN_KEY, V6_7_RUN_KEY, V6_8_RUN_KEY, V6_9_RUN_KEY, V7_0_RUN_KEY}

    checked = runner.check_run(RUN_KEY)
    assert checked["logical_run_key"] == RUN_KEY
    assert checked["status"] == STATUS
    assert runner.check_run("current")["logical_run_key"] in {RUN_KEY, V6_3_RUN_KEY, V6_4_RUN_KEY, V6_5_RUN_KEY, V6_6_RUN_KEY, V6_5_1_RUN_KEY, V6_7_RUN_KEY, V6_8_RUN_KEY, V6_9_RUN_KEY, V7_0_RUN_KEY}

    assert report["current_resolves_to"] == RUN_KEY
    assert report["current_alias_policy"]["current_moved_from"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["current_moved_to"] == RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY
    assert runner.check_run(ROLLBACK_KEY)["logical_run_key"] == ROLLBACK_KEY


def test_materialization_scaleout_sanitizes_source_derived_payloads_and_quality(
    report: dict[str, object],
    v62_module,
) -> None:
    v61_report = json.loads((V6_1_RUN_ROOT / "report.json").read_text(encoding="utf-8"))
    backend = report["backend_summary"]
    materialization = report["materialization_summary"]
    quality = report["candidate_text_quality_audit"]

    assert backend["backend_kind"] == "repo_local_sqlite_bm25"
    assert backend["namespace"] == "v6_2_true_rag_nonprod_materialization_scaleout_denominator_reality"
    assert backend["indexed_search_unit_count"] >= 300
    assert backend["indexed_search_view_count"] >= 300
    assert backend["indexed_search_unit_count"] > v61_report["backend_summary"]["indexed_search_unit_count"]
    assert backend["indexed_search_view_count"] > v61_report["backend_summary"]["indexed_search_view_count"]
    assert materialization["source_family_counts"]["PDF"] >= 50
    assert materialization["source_family_counts"]["XLSX"] >= 50
    assert materialization["source_family_counts"]["TEXT"] >= 50
    assert materialization["materialization_source_availability_blocker"] is False
    assert materialization["source_artifact"] == (
        "ai/eval/indexes/rag-data-all-source-citable-nonprod-v1/search_view_manifest.jsonl"
    )
    assert materialization["v5_8_balanced_surface_reuse_status"]["available"] is True
    assert materialization["v5_8_balanced_surface_reuse_status"]["used_as_label_truth"] is False

    assert quality["total_search_units"] == backend["indexed_search_unit_count"]
    assert quality["meaningful_text_count"] >= 200
    assert quality["semantic_retrieval_text_eligible_count"] >= 200
    assert quality["meaningful_text_count_by_family"]["PDF"] >= 30
    assert quality["meaningful_text_count_by_family"]["XLSX"] >= 30
    assert quality["meaningful_text_count_by_family"]["TEXT"] >= 30
    assert quality["candidate_text_quality_passed"] is True
    assert quality["hash_only_or_digest_only_count"] == 0
    assert quality["source_manifest_only_count"] == 0

    schema = report["true_rag_index_payload_schema"]
    assert schema["source_derived_only"] is True
    assert schema["candidate_only"] is True
    assert schema["namespace_prefix"] == "v6_2_true_rag_nonprod_"
    assert schema["validation_result"]["forbidden_field_violation_count"] == 0
    assert set(schema["source_family_coverage"]) == {"PDF", "XLSX", "TEXT"}

    for payload in report["true_rag_index_payloads"]:
        v62_module.validate_true_rag_index_payload(payload)
        candidate_text = (payload["embedding_text"] + "\n" + payload["bm25_text"]).lower()
        for forbidden in FORBIDDEN_TEXT_TOKENS:
            assert forbidden not in candidate_text
        assert payload["metadata"]["candidate_only_payload_role"] == "SearchView"
        assert payload["metadata"]["evidence_truth_role"] == "SourceAtom/EvidenceBundle"

    poisoned = dict(report["true_rag_index_payloads"][0])
    poisoned["metadata"] = dict(poisoned["metadata"], expected_answer="oracle")
    with pytest.raises(ValueError, match="forbidden"):
        v62_module.validate_true_rag_index_payload(poisoned)


def test_denominator_reality_ledgers_and_metric_lanes_expose_coverage_limits(report: dict[str, object]) -> None:
    denominator = report["denominator_manifest"]
    eligibility = report["row_eligibility_ledger"]
    exclusion = report["exclusion_ledger"]
    reality = report["denominator_reality_audit"]
    coverage = report["retrieval_metric_coverage"]
    metrics = report["metric_results"]

    assert len(denominator) == 300
    assert len(eligibility) == 300
    assert len(exclusion) == 300
    assert denominator != eligibility
    assert denominator != exclusion
    assert eligibility != exclusion
    assert reality["denominator_manifest_and_eligibility_ledger_distinct"] is True
    assert reality["denominator_manifest_and_exclusion_ledger_distinct"] is True
    assert reality["no_silent_drop"] is True
    assert reality["attempted_rows"] == 300
    assert reality["coverage_adjusted_rows"] == 300
    assert reality["computed_only_rows"] == 0
    assert reality["excluded_rows"] == 300
    assert reality["family_breakdown"] == {"PDF": 100, "TEXT": 100, "XLSX": 100}
    assert reality["v5_8_balanced_surface_reuse_status"]["used_as_label_truth"] is False

    true_rag = metrics["true_rag_retrieval_metric"]
    assert true_rag["metric_kind"] == "true_rag_retrieval_hit_mrr_ndcg"
    assert true_rag["retrieval_metric_rows_attempted"] == 300
    assert true_rag["retrieval_metric_rows_computed"] == 0
    assert true_rag["retrieval_metric_rows_excluded"] == 300
    assert true_rag["no_authorized_label_count"] == 300
    assert true_rag["coverage_limited"] is True
    assert true_rag["computed_only"]["denominator"] == 0
    assert true_rag["coverage_adjusted"]["denominator"] == 300
    assert true_rag["tool_outputs_excluded_from_true_rag_retrieval"] is True
    assert set(true_rag["computed_only"]["metrics"]) == {"hit_at_1", "hit_at_3", "hit_at_5", "mrr_at_5", "ndcg_at_5"}

    assert coverage["retrieval_metric_coverage_ratio"] == 0.0
    assert coverage["coverage_adjusted_denominator"] == 300
    assert coverage["computed_only_denominator"] == 0
    assert coverage["coverage_limited_reason"] == "no_authorized_after_fact_label_available"

    for row in denominator:
        assert row["official_metric_row"] is False
        assert row["user_owned_gold_required"] is False
        assert row["included_in_coverage_adjusted_denominator"] is True
        assert row["included_in_computed_only_denominator"] is False
    for row in eligibility:
        assert row["candidate_generation_allowed"] is True
        assert row["backend_invoked"] is True
        assert row["rag_context_retrieval_attempted"] is True
        assert row["rag_metric_retrieval_attempted"] is True
        assert row["tool_outputs_counted_as_rag_hit"] is False
        assert row["authorized_after_fact_label_available"] is False
    for row in exclusion:
        assert row["excluded_from"] == "true_rag_retrieval_metric_computed_only"
        assert row["no_authorized_after_fact_label"] is True


def test_backend_tool_and_agentic_lanes_are_separate_and_fail_closed(report: dict[str, object]) -> None:
    backend = report["backend_summary"]
    metrics = report["metric_results"]
    tool = metrics["structured_tool_metric"]
    agentic = metrics["agentic_answer_metric"]

    assert backend["backend_build_invoked"] is True
    assert backend["backend_query_invoked"] is True
    assert backend["query_count"] == 300
    assert backend["bm25_only_baseline_passed"] is True
    assert backend["fake_noop_or_replay_backend_used"] is False
    assert backend["archived_topk_replay_projection_backend_rejected"] is True
    assert backend["production_db_index_cache_mutated"] is False
    assert backend["protected_namespaces_touched"] == []
    assert backend["candidate_count_distribution"]["max"] >= backend["candidate_count_distribution"]["p50"]

    assert tool["metric_kind"] == "structured_tool_metric"
    assert tool["tool_outputs_excluded_from_true_rag_retrieval"] is True
    assert tool["tool_success_contributed_to_hit_at_k"] is False
    assert tool["tool_success_contributed_to_mrr"] is False
    assert tool["tool_success_contributed_to_ndcg"] is False
    assert tool["tool_required_rows"] > 0
    assert tool["tool_attempted_rows"] == tool["tool_required_rows"]

    assert agentic["metric_kind"] == "agentic_answer_metric"
    assert agentic["answer_quality_metric_computed"] is False
    assert agentic["local_llm_unavailable_fail_closed"] is True
    assert agentic["fake_noop_or_extractive_fallback_used"] is False
    assert agentic["raw_prompt_payload_written"] is False
    assert agentic["raw_response_payload_written"] is False

    for row in report["agentic_loop_trace"]:
        assert row["retry_count"] <= 2
        assert row["raw_prompt_payload_written"] is False
        assert row["raw_response_payload_written"] is False
    assert {
        "classify",
        "true_rag_retrieve",
        "hydrate",
        "tool_plan",
        "tool_execute",
        "synthesize",
        "citation_verify",
        "retry_or_finalize",
    } <= {row["stage"] for row in report["agentic_loop_trace"]}


def test_leakage_probes_and_local_llm_gpu_paths_are_fail_closed(report: dict[str, object]) -> None:
    leakage = report["leakage_probe_summary"]
    assert leakage["passed"] is True
    assert leakage["forbidden_input_forwarded_count"] == 0
    assert leakage["forbidden_input_forwarded_fields"] == []
    assert leakage["candidate_ids_changed_by_poisoned_fields"] is False
    assert leakage["candidate_scores_changed_by_poisoned_fields"] is False
    assert leakage["route_decisions_used_forbidden_locators"] is False
    assert leakage["source_shortcut_dependency_failed_count"] == 0
    assert leakage["identity_lookup_dependency_failed_count"] == 0
    assert leakage["target_qrels_gold_dependency_failed_count"] == 0
    assert leakage["formula_dependency_failed_count"] == 0
    assert leakage["status_hash_changed_by_forbidden_fields"] is False
    assert set(leakage["stage_probe_results"]) == {
        "materialization",
        "candidate_text_construction",
        "classify",
        "true_rag_retrieve",
        "hydrate",
        "tool_plan",
        "tool_execute",
        "synthesize",
        "citation_verify",
        "metric_computation",
        "report_generation",
        "status_append",
        "current_alias_resolution",
    }
    assert all(stage["passed"] for stage in leakage["stage_probe_results"].values())

    llm = report["local_llm_status"]
    gpu = report["gpu_status"]
    assert llm["env_gate"] == "RAG_V6_2_ENABLE_LOCAL_LLM"
    assert llm["env_enabled"] is False
    assert llm["available"] is False
    assert llm["fail_closed_reason"] == "env_gate_disabled"
    assert gpu["env_gate"] == "RAG_V6_2_ENABLE_GPU"
    assert gpu["used"] is False
    assert gpu["baseline_passed_without_gpu"] is True
    assert report["external_vectordb_status"]["real_vectordb_metric"] is False


def test_report_bundle_writes_required_artifacts_docs_and_status(tmp_path: Path, v62_module) -> None:
    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        path = tmp_path / doc
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Ledger\n\nLast updated: 2026-06-06 KST.\n", encoding="utf-8")

    built = v62_module.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    written, hashes = v62_module.write_report_bundle(tmp_path, built)
    v62_module.check_report(written, root=tmp_path)
    v62_module.update_docs(tmp_path, written)
    v62_module.append_status(tmp_path, written, artifact_hashes=hashes)

    run_root = tmp_path / "ai/eval/reports/rag-ingestion/runs" / RUN_KEY
    for name in REQUIRED_ARTIFACTS:
        assert (run_root / name).exists(), name

    assert len(_jsonl(run_root / "denominator_manifest.jsonl")) == written["denominator_reality_audit"]["attempted_rows"]
    assert len(_jsonl(run_root / "row_eligibility_ledger.jsonl")) == written["denominator_reality_audit"]["attempted_rows"]
    assert len(_jsonl(run_root / "exclusion_ledger.jsonl")) == written["denominator_reality_audit"]["excluded_rows"]
    status_lines = _jsonl(tmp_path / "ai/eval/reports/rag-ingestion/status.jsonl")
    assert status_lines[-1]["current_resolves_to"] == RUN_KEY
    assert status_lines[-1]["rollback_key"] == ROLLBACK_KEY
    assert status_lines[-1]["backend_namespace"] == "v6_2_true_rag_nonprod_materialization_scaleout_denominator_reality"
    actual_report_hash = hashlib.sha256((run_root / "report.json").read_bytes()).hexdigest()
    assert status_lines[-1]["artifact_sha256"]["report_json_sha256"] == actual_report_hash
    v62_module.require_status_report_hash(tmp_path, written)

    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        text = (tmp_path / doc).read_text(encoding="utf-8")
        assert "diagnostic-only" in text
        assert f"current moved from `{ROLLBACK_KEY}` to `{RUN_KEY}`" in text
        assert f"rollback key is `{ROLLBACK_KEY}`" in text
        assert "computed-only and coverage-adjusted" in text
        assert "local LLM/GPU usage is optional and env-gated" in text
        assert "no official/product/promotion/live-readiness claim" in text


def test_required_report_fields_and_protected_surfaces_are_closed(report: dict[str, object]) -> None:
    assert report["run_id"] == RUN_KEY
    assert report["schema_version"].endswith("_report_v1")
    assert report["status"] == STATUS
    assert report["diagnostic_only"] is True
    assert report["current_resolves_to"] == RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY
    assert report["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows_created"] == 0
    assert report["official_metric_input_rows_consumed"] == 0
    assert report["protected_namespaces_touched"] == []

    for field in REQUIRED_REPORT_FALSE_FIELDS:
        assert report[field] is False, field

    protected = report["protected_surface_check"]
    assert protected["passed"] is True
    assert protected["mutated_paths"] == []
    assert protected["gold_qrels_expected_supporting_relevance_answerability_clean"] is True
    assert protected["official_denominator_clean"] is True
    assert protected["source_registry_clean"] is True
    assert protected["production_index_namespace_clean"] is True

    assert "ai/eval/rag_v62_source_derived_materialization_scaleout_and_denominator_reality_check.py" in report[
        "changed_files"
    ]
    assert set(report["generated_artifacts"]) >= {
        f"ai/eval/reports/rag-ingestion/runs/{RUN_KEY}/{name}" for name in REQUIRED_ARTIFACTS
    }
    assert report["remaining_blockers"]["user_owned_decision_blockers"] == []
    assert report["remaining_blockers"]["denominator_coverage_gaps"] == [
        "no authorized after-the-fact labels found for v5_8 balanced diagnostic rows"
    ]
