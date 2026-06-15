from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v6_1_true_rag_corpus_expansion_and_metric_split_hardening"
ROLLBACK_KEY = "v6_0_agentic_true_rag_and_tool_loop_rewrite"
STATUS = "V6_1_TRUE_RAG_CORPUS_EXPANSION_AND_METRIC_SPLIT_HARDENING_NONPROD_READY"

REQUIRED_ARTIFACTS = {
    "report.json",
    "metric_results.json",
    "metric_tiers.json",
    "leakage_probe_summary.json",
    "denominator_manifest.jsonl",
    "row_eligibility_ledger.jsonl",
    "exclusion_ledger.jsonl",
    "true_rag_index_payload_schema.json",
    "true_rag_candidate_diagnostics.jsonl",
    "agentic_loop_trace.jsonl",
    "structured_tool_diagnostics.jsonl",
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


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def v61_module():
    from ai.eval import rag_v61_true_rag_corpus_expansion_and_metric_split_hardening as v61

    return v61


@pytest.fixture(scope="module")
def report(v61_module) -> dict[str, object]:
    built = v61_module.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    v61_module.check_report(built, root=ROOT)
    return built


def test_v61_registers_resolves_current_and_keeps_v60_as_rollback(report: dict[str, object]) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_eval_registry as registry

    assert registry.resolve_run(RUN_KEY, root=ROOT).logical_key == RUN_KEY
    assert registry.resolve_run("current", root=ROOT).logical_key == RUN_KEY
    assert runner.DEFAULT_RUN_KEY == RUN_KEY

    checked = runner.check_run(RUN_KEY)
    assert checked["logical_run_key"] == RUN_KEY
    assert checked["status"] == STATUS
    assert runner.check_run("current")["logical_run_key"] == RUN_KEY

    assert report["current_resolves_to"] == RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["current_moved_from"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["rollback_key"] == ROLLBACK_KEY

    v60 = runner.check_run(ROLLBACK_KEY)
    assert v60["logical_run_key"] == ROLLBACK_KEY


def test_search_unit_search_view_schema_is_source_derived_candidate_only_and_covers_all_families(
    report: dict[str, object],
    v61_module,
) -> None:
    schema = report["true_rag_index_payload_schema"]
    assert schema["source_derived_only"] is True
    assert schema["candidate_only"] is True
    assert schema["namespace_prefix"] == "v6_1_true_rag_nonprod_"
    assert set(schema["source_family_coverage"]) == {"PDF", "XLSX", "TEXT"}
    assert schema["validation_result"]["passed"] is True
    assert schema["validation_result"]["forbidden_field_violation_count"] == 0
    assert "formula_text" in schema["forbidden_fields"]
    assert "source_workbook" in schema["forbidden_fields"]
    assert "target_search_unit_id" in schema["forbidden_fields"]
    assert "citation_locator" in schema["forbidden_fields"]

    units = report["materialized_search_units"]
    views = report["materialized_search_views"]
    payloads = report["true_rag_index_payloads"]
    assert len(units) == len(views) == len(payloads)
    assert {unit["source_family"] for unit in units} == {"PDF", "XLSX", "TEXT"}
    assert report["materialization_summary"]["source_family_coverage"] == {"PDF": True, "XLSX": True, "TEXT": True}
    assert report["materialization_summary"]["query_time_raw_pdf_xlsx_text_parse_in_true_rag"] is False
    assert report["materialization_summary"]["source_derived_search_unit_count"] == len(units)
    assert report["materialization_summary"]["source_derived_search_view_count"] == len(views)
    assert report["materialization_summary"]["source_seed_manifest"] == (
        "ai/eval/indexes/rag-data-all-source-nonprod-v1/search_unit_manifest.jsonl"
    )
    assert report["materialization_summary"]["source_seed_manifest_sha256"]
    assert report["materialization_summary"]["source_seed_selected_rows_by_family"] == {
        "PDF": 4,
        "XLSX": 4,
        "TEXT": 3,
    }
    assert report["materialization_summary"]["official_denominator_rows_selected"] == 0
    assert all(
        row["not_official_denominator"] is True
        for row in report["materialization_summary"]["source_seed_selected_rows"]
    )
    assert all(
        row["manifest_path"]
        == "ai/eval/indexes/rag-data-all-source-nonprod-v1/search_unit_manifest.jsonl"
        for row in report["materialization_summary"]["source_seed_selected_rows"]
    )

    for payload in payloads:
        v61_module.validate_true_rag_index_payload(payload)
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        for forbidden in schema["forbidden_fields"]:
            assert forbidden not in serialized

    poisoned = dict(payloads[0])
    poisoned["metadata"] = dict(poisoned["metadata"], expected_answer="oracle", source_title="shortcut")
    with pytest.raises(ValueError, match="forbidden"):
        v61_module.validate_true_rag_index_payload(poisoned)
    for forbidden_key in ("expectedAnswer", "sourceTitle", "queryId"):
        poisoned_top_level = dict(payloads[0], **{forbidden_key: "oracle"})
        with pytest.raises(ValueError, match="forbidden|unexpected"):
            v61_module.validate_true_rag_index_payload(poisoned_top_level)


def test_repo_local_backend_is_built_queried_nonproduction_and_records_counters(
    report: dict[str, object],
    v61_module,
) -> None:
    backend = report["backend_summary"]
    assert backend["backend_kind"] == "repo_local_sqlite_bm25"
    assert backend["backend_build_invoked"] is True
    assert backend["backend_query_invoked"] is True
    assert backend["bm25_only_baseline_passed"] is True
    assert backend["namespace"].startswith("v6_1_true_rag_nonprod_")
    assert backend["protected_namespaces_touched"] == []
    assert backend["production_db_index_cache_mutated"] is False
    assert backend["indexed_search_unit_count"] == len(report["materialized_search_units"])
    assert backend["indexed_search_view_count"] == len(report["materialized_search_views"])
    assert backend["query_count"] > 0
    assert backend["candidate_count_distribution"]["max"] >= backend["candidate_count_distribution"]["p50"]
    assert backend["query_latency_ms"]["p95"] >= backend["query_latency_ms"]["p50"]
    assert backend["build_latency_ms"] >= 0
    assert backend["sqlite_path"].endswith("true_rag_bm25_index.sqlite")

    adapter = v61_module.RepoLocalTrueRagBackend(namespace="v6_1_true_rag_nonprod_test")
    with pytest.raises(ValueError, match="raw parser"):
        adapter.query_from_raw_source_parse("ignored.pdf", query_text="shortcut")


def test_metric_lanes_are_separate_objects_and_tool_outputs_cannot_create_rag_hits(
    report: dict[str, object],
) -> None:
    metric_results = report["metric_results"]
    assert set(metric_results) == {
        "true_rag_retrieval_metric",
        "structured_tool_metric",
        "agentic_answer_metric",
    }
    assert report["true_rag_lane_summary"] == metric_results["true_rag_retrieval_metric"]
    assert report["structured_tool_lane_summary"] == metric_results["structured_tool_metric"]
    assert report["agentic_answer_lane_summary"] == metric_results["agentic_answer_metric"]

    true_rag = metric_results["true_rag_retrieval_metric"]
    tool = metric_results["structured_tool_metric"]
    agentic = metric_results["agentic_answer_metric"]
    assert true_rag["metric_kind"] == "true_rag_retrieval_hit_mrr_ndcg"
    assert {"hit_at_1", "hit_at_3", "hit_at_5", "mrr_at_5", "ndcg_at_5"} <= set(true_rag["metrics"])
    assert true_rag["attempted_rows"] == report["metric_tiers"]["diagnostic_true_rag_source_derived"]["attempted_rows"]
    assert true_rag["tool_outputs_excluded_from_true_rag_retrieval"] is True
    assert true_rag["structured_tool_success_counted_as_retrieval_hit"] is False
    assert true_rag["raw_parser_result_counted_as_retrieval_hit"] is False
    assert true_rag["archived_replay_counted_as_true_rag_retrieval"] is False
    assert tool["metric_kind"] == "structured_tool_metric"
    assert tool["tool_outputs_excluded_from_true_rag_retrieval"] is True
    assert tool["tool_required_rows"] >= tool["tool_attempted_rows"] >= tool["tool_success_rows"]
    assert agentic["metric_kind"] == "agentic_answer_metric"
    assert agentic["answer_quality_metric_computed"] is False
    assert agentic["raw_prompt_payload_written"] is False
    assert agentic["raw_response_payload_written"] is False

    for row in report["row_eligibility_ledger"]:
        if row["metric_tier"] != "diagnostic_true_rag_source_derived":
            assert row["included_in_true_rag_retrieval_metric"] is False
        if row["tool_required"]:
            assert row["included_in_true_rag_retrieval_metric"] is False
            assert row["structured_tool_outputs_counted_as_rag_hit"] is False


def test_agentic_loop_trace_has_required_nodes_bounded_retry_and_no_raw_payloads(
    report: dict[str, object],
) -> None:
    loop = report["agentic_loop"]
    assert loop["nodes"] == [
        "classify",
        "true_rag_retrieve",
        "hydrate",
        "tool_plan",
        "tool_execute",
        "synthesize",
        "citation_verify",
        "retry_or_finalize",
    ]
    assert loop["bounded_retry_max"] == 2
    assert loop["llm_output_can_relax_deterministic_guards"] is False
    assert loop["classify_constructs_candidates"] is False
    assert loop["retrieve_uses_search_unit_search_view_backend_only"] is True
    assert loop["hydrate_uses_source_atom_evidence_bundle_truth"] is True

    traces = report["agentic_loop_trace"]
    assert traces
    for row in traces:
        assert set(row) >= {
            "diagnostic_row_key",
            "classification_result",
            "rag_attempted",
            "rag_candidate_count",
            "hydrate_attempted",
            "hydrate_success",
            "tool_planned",
            "tool_attempted",
            "tool_success",
            "synthesize_attempted",
            "citation_verify_attempted",
            "citation_verify_outcome",
            "retry_count",
            "fail_closed_reason",
            "answer_metric_eligible",
            "raw_prompt_payload_written",
            "raw_response_payload_written",
        }
        assert row["retry_count"] <= 2
        assert row["raw_prompt_payload_written"] is False
        assert row["raw_response_payload_written"] is False


def test_leakage_probes_poison_forbidden_fields_for_all_sensitive_stages(report: dict[str, object]) -> None:
    leakage = report["leakage_probe_summary"]
    assert leakage["passed"] is True
    assert leakage["forbidden_input_forwarded_count"] == 0
    assert leakage["forbidden_input_forwarded_fields"] == []
    assert leakage["identity_lookup_dependency_failed_count"] == 0
    assert leakage["source_shortcut_dependency_failed_count"] == 0
    assert leakage["target_qrels_gold_dependency_failed_count"] == 0
    assert leakage["candidate_ids_changed_by_poisoned_fields"] is False
    assert leakage["candidate_scores_changed_by_poisoned_fields"] is False
    assert leakage["route_decisions_used_forbidden_locators"] is False
    assert leakage["tool_lane_poison_created_true_rag_hit"] is False
    assert leakage["answer_synthesis_received_expected_supporting_gold_text"] is False

    required_stages = {
        "classify",
        "true_rag_retrieve",
        "hydrate",
        "tool_plan",
        "tool_execute",
        "synthesize",
        "citation_verify",
        "metric_computation",
        "report_generation",
    }
    assert set(leakage["stage_probe_results"]) == required_stages
    assert all(stage["passed"] for stage in leakage["stage_probe_results"].values())


def test_local_llm_and_gpu_paths_are_optional_env_gated_and_fail_closed_by_default(report: dict[str, object]) -> None:
    policy = report["local_llm_gpu_permission_policy"]
    assert policy["diagnostic_nonproduction_only"] is True
    assert policy["baseline_requires_local_llm"] is False
    assert policy["baseline_requires_gpu"] is False
    assert policy["raw_prompt_payload_written"] is False
    assert policy["raw_response_payload_written"] is False

    llm = report["local_llm_status"]
    gpu = report["gpu_status"]
    assert llm["env_gate"] == "RAG_V6_1_ENABLE_LOCAL_LLM"
    assert llm["env_enabled"] is False
    assert llm["available"] is False
    assert llm["llm_invoked_count"] == 0
    assert llm["fail_closed_reason"] == "env_gate_disabled"
    assert gpu["env_gate"] == "RAG_V6_1_ENABLE_GPU"
    assert gpu["env_enabled"] is False
    assert gpu["used"] is False
    assert gpu["baseline_passed_without_gpu"] is True


def test_report_bundle_writes_required_artifacts_docs_and_status(tmp_path: Path, v61_module) -> None:
    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        path = tmp_path / doc
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Ledger\n\nLast updated: 2026-06-06 KST.\n", encoding="utf-8")

    built = v61_module.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    written, hashes = v61_module.write_report_bundle(tmp_path, built)
    v61_module.check_report(written, root=tmp_path)
    v61_module.update_docs(tmp_path, written)
    v61_module.append_status(tmp_path, written, artifact_hashes=hashes)

    run_root = tmp_path / "reports/rag_eval/rag-ingestion/runs" / RUN_KEY
    for name in REQUIRED_ARTIFACTS:
        assert (run_root / name).exists(), name

    assert len(_jsonl(run_root / "denominator_manifest.jsonl")) == written["denominator_manifest_rows"]
    assert len(_jsonl(run_root / "row_eligibility_ledger.jsonl")) == written["row_eligibility_ledger_rows"]
    assert len(_jsonl(run_root / "agentic_loop_trace.jsonl")) == len(written["agentic_loop_trace"])
    assert len(_jsonl(run_root / "structured_tool_diagnostics.jsonl")) == len(written["structured_tool_diagnostics"])
    status_lines = _jsonl(tmp_path / "reports/rag_eval/rag-ingestion/status.jsonl")
    assert status_lines[-1]["current_resolves_to"] == RUN_KEY
    assert status_lines[-1]["rollback_key"] == ROLLBACK_KEY
    assert status_lines[-1]["metric_lanes_separate"] is True
    actual_report_hash = hashlib.sha256((run_root / "report.json").read_bytes()).hexdigest()
    assert status_lines[-1]["artifact_sha256"]["report_json_sha256"] == actual_report_hash
    assert "report_json_sha256" not in written["artifact_sha256"]
    assert written["report_json_sha256_policy"] == "status_ledger_only_after_final_write"
    v61_module.require_status_report_hash(tmp_path, written)
    status_lines[-1]["artifact_sha256"]["report_json_sha256"] = "0" * 64
    status_path = tmp_path / "reports/rag_eval/rag-ingestion/status.jsonl"
    status_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in status_lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="status report hash"):
        v61_module.require_status_report_hash(tmp_path, written)

    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        text = (tmp_path / doc).read_text(encoding="utf-8")
        assert "diagnostic-only" in text
        assert f"current moved from `{ROLLBACK_KEY}` to `{RUN_KEY}`" in text
        assert f"rollback key is `{ROLLBACK_KEY}`" in text
        assert "true RAG retrieval, structured tool, and agentic answer metrics are separated" in text
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

    assert "ai/eval/rag_v61_true_rag_corpus_expansion_and_metric_split_hardening.py" in report["changed_files"]
    assert set(report["generated_artifacts"]) >= {
        f"reports/rag_eval/rag-ingestion/runs/{RUN_KEY}/{name}" for name in REQUIRED_ARTIFACTS
    }
    assert report["remaining_blockers"]["user_owned_decision_blockers"] == []
