from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v6_0_agentic_true_rag_and_tool_loop_rewrite"
STATUS = "V6_0_AGENTIC_TRUE_RAG_AND_TOOL_LOOP_REWRITE_NONPROD_READY"


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def report() -> dict[str, object]:
    from ai.eval import rag_v60_agentic_true_rag_and_tool_loop_rewrite as v60a

    built = v60a.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    v60a.check_report(built, root=ROOT)
    return built


def test_legacy_non_rag_paths_are_inventoried_with_owner_call_site_risk_and_isolated(
    report: dict[str, object],
) -> None:
    expected = {
        "file_level_retrieval_then_runtime_file_parsing_search",
        "raw_pdf_xlsx_query_time_candidate_parsing",
        "archived_topk_baseline_topk_replay_projection_candidate_generation",
        "route_policy_forced_search",
        "row_specific_exception",
        "query_id_row_id_case_id_lookup",
        "source_title_workbook_filename_raw_path_shortcut",
        "direct_normalized_answer_value_matching",
        "formula_text_or_evaluation_shortcut",
        "target_qrels_gold_expected_supporting_citation_locator_candidate_construction",
    }
    inventory = report["legacy_non_rag_path_inventory"]
    assert {row["path_id"] for row in inventory} == expected
    assert all(row["owner"] for row in inventory)
    assert all(row["call_site"] for row in inventory)
    assert all(row["risk"] for row in inventory)
    assert {row["v6_status"] for row in inventory} <= {"legacy_non_rag_path", "tool_lane_only"}
    assert report["legacy_non_rag_path_isolated_from_true_rag"] is True
    assert report["legacy_non_rag_comparison_metric"]["uses_true_rag_denominator"] is False


def test_true_rag_schema_allows_safe_source_ids_and_rejects_oracle_eval_shortcuts(
    report: dict[str, object],
) -> None:
    from ai.eval import rag_v60_agentic_true_rag_and_tool_loop_rewrite as v60a

    schema = report["true_rag_index_payload_schema"]
    assert set(schema["schema_names"]) == {
        "TrueRagSearchUnit",
        "TrueRagSearchView",
        "TrueRagIndexPayload",
        "TrueRagCandidate",
        "TrueRagRetrievalResult",
    }
    assert {"document_id", "workbook_id", "sheet_id"} <= set(schema["allowed_safe_metadata_fields"])
    assert "raw_source_file_title" in schema["forbidden_fields"]
    assert "workbook_filename" in schema["forbidden_fields"]
    assert "query_id" in schema["forbidden_fields"]
    assert "row_id" in schema["forbidden_fields"]
    assert "case_id" in schema["forbidden_fields"]
    assert "expected_answer" in schema["forbidden_fields"]
    assert "supporting_evidence_id" in schema["forbidden_fields"]
    assert "qrels_positive_id" in schema["forbidden_fields"]
    assert "baseline_topk_candidate_ids" in schema["forbidden_fields"]
    assert "direct_normalized_answer_value" in schema["forbidden_fields"]

    for payload in report["true_rag_index_payloads"]:
        v60a.validate_true_rag_index_payload(payload)
        assert payload["metadata"].get("document_id") or payload["metadata"].get("workbook_id")

    safe_payload = dict(report["true_rag_index_payloads"][0])
    safe_payload["metadata"] = dict(safe_payload["metadata"], document_id="doc-safe", workbook_id="wb-safe")
    v60a.validate_true_rag_index_payload(safe_payload)

    poisoned = dict(safe_payload)
    poisoned["metadata"] = dict(poisoned["metadata"], query_id="q-1", expected_answer="oracle")
    with pytest.raises(ValueError, match="forbidden"):
        v60a.validate_true_rag_index_payload(poisoned)


def test_materialization_builds_pdf_xlsx_text_search_units_without_raw_query_time_parsing(
    report: dict[str, object],
) -> None:
    materialization = report["materialization_summary"]
    assert materialization["query_time_raw_pdf_open_or_parse_in_true_rag"] is False
    assert materialization["query_time_raw_xlsx_open_or_parse_in_true_rag"] is False
    assert materialization["production_source_registry_index_cache_mutated"] is False
    assert materialization["nonprod_namespace_mutated"] is True
    assert materialization["indexed_search_unit_count"] == len(report["true_rag_index_payloads"])

    pdf_units = [unit for unit in report["materialized_search_units"] if unit["source_family"] == "PDF"]
    xlsx_units = [unit for unit in report["materialized_search_units"] if unit["source_family"] == "XLSX"]
    text_units = [unit for unit in report["materialized_search_units"] if unit["source_family"] == "TEXT"]
    assert {unit["unit_type"] for unit in pdf_units} >= {
        "page_block",
        "paragraph",
        "table_row",
        "table_cell_or_row_summary",
        "caption_context",
    }
    assert {unit["unit_type"] for unit in xlsx_units} >= {"row", "column", "cell_or_small_range"}
    assert {unit["unit_type"] for unit in text_units} >= {"section_chunk", "lexical_alias"}

    xlsx_meta = [unit["metadata"] for unit in xlsx_units]
    assert any(meta.get("merged_header_propagation") for meta in xlsx_meta)
    assert all("workbook_filename" not in meta for meta in xlsx_meta)
    assert all("formula_text" not in meta for meta in xlsx_meta)


def test_real_repo_local_hybrid_backend_builds_index_queries_and_rejects_replay_backend(
    report: dict[str, object],
) -> None:
    from ai.eval import rag_v60_agentic_true_rag_and_tool_loop_rewrite as v60a

    backend = report["real_nonprod_backend"]
    assert backend["backend_kind"] == "repo_local_sqlite_bm25_hybrid"
    assert backend["namespace"].startswith("v6_0_true_rag_nonprod_")
    assert backend["real_vectordb_or_hybrid_backend_invoked"] is True
    assert backend["indexed_search_unit_count"] > 0
    assert backend["query_count"] > 0
    assert backend["p50_latency_ms"] >= 0
    assert backend["p95_latency_ms"] >= backend["p50_latency_ms"]
    assert backend["fake_noop_or_replay_backend_used"] is False
    assert backend["archived_topk_replay_projection_backend_rejected"] is True

    adapter = v60a.RepoLocalTrueRagHybridBackend(namespace="v6_0_true_rag_nonprod_test")
    with pytest.raises(ValueError, match="replay"):
        adapter.build_index_from_replay_candidate_ids(["su-1"])


def test_langgraph_agentic_loop_has_bounded_retry_and_route_node_cannot_make_candidates(
    report: dict[str, object],
) -> None:
    from ai.eval import rag_v60_agentic_true_rag_and_tool_loop_rewrite as v60a

    loop = report["langgraph_agentic_loop"]
    assert loop["nodes"] == [
        "classify_query_node",
        "true_rag_retrieve_node",
        "evidence_hydrate_node",
        "tool_plan_node",
        "tool_execute_node",
        "answer_synthesize_node",
        "citation_verify_node",
        "retry_or_finalize_node",
    ]
    assert loop["bounded_retry_max"] == 2
    assert set(loop["allowed_agent_choices"]) == {
        "true_rag_only",
        "true_rag_plus_pdf_tool",
        "true_rag_plus_xlsx_tool",
        "true_rag_plus_text_source_tool",
        "insufficient_evidence",
    }
    assert loop["route_node_candidate_construction_allowed"] is False
    assert loop["route_node_row_specific_policy_allowed"] is False
    assert loop["route_node_forced_parser_routing_allowed"] is False
    assert report["agentic_loop_trace_summary"]
    assert max(row["retry_count"] for row in report["agentic_loop_trace_summary"]) <= 2

    mutated = dict(loop)
    mutated["route_node_candidate_construction_allowed"] = True
    with pytest.raises(ValueError, match="route node"):
        v60a.assert_langgraph_agentic_loop_contract(mutated)


def test_tool_lane_is_available_bounded_and_excluded_from_true_rag_hit_metrics(
    report: dict[str, object],
) -> None:
    tools = report["tool_lane"]
    assert set(tools["tools"]) == {"PDF", "XLSX", "TEXT"}
    assert tools["tool_results_mixed_into_true_rag_hit_at_k"] is False
    assert tools["pdf_tool"]["bounded_source_access"] is True
    assert tools["pdf_tool"]["full_raw_dump_by_default"] is False
    assert tools["xlsx_tool"]["bounded_source_access"] is True
    assert tools["xlsx_tool"]["formula_text_exposed_by_default"] is False
    assert tools["xlsx_tool"]["cached_formula_value_allowed_when_needed"] is True
    assert tools["text_tool"]["neighboring_chunk_expansion_allowed"] is True

    metrics = report["tool_metric_results"]
    assert metrics["structured_tool_metric_gold_29"]["true_rag_metric_inclusion"] is False
    assert metrics["structured_tool_metric_silver_sample"]["true_rag_metric_inclusion"] is False
    assert metrics["tool_required_row_ratio"] > 0
    assert report["true_rag_metric_results"]["tool_outputs_excluded"] is True


def test_metric_policy_reuses_gold_29_and_silver_1000_read_only_with_separate_lanes(
    report: dict[str, object],
) -> None:
    metric_policy = report["metric_policy"]
    expected_metrics = {
        "true_rag_retrieval_metric_gold_29",
        "true_rag_retrieval_metric_silver_1000",
        "structured_tool_metric_gold_29",
        "structured_tool_metric_silver_sample",
        "agentic_end_to_end_answer_metric_gold_29",
        "agentic_end_to_end_answer_metric_silver_diagnostic",
        "legacy_non_rag_comparison_metric",
    }
    assert set(metric_policy["defined_metrics"]) == expected_metrics
    assert metric_policy["gold_source"]["row_count"] == 29
    assert metric_policy["silver_source"]["row_count"] == 1000
    assert metric_policy["gold_expected_supporting_relevance_answerability_read_only"] is True
    assert metric_policy["silver_diagnostic_only_not_promoted_to_gold"] is True
    assert report["gold_silver_immutability"]["gold_qrels_expected_supporting_labels_mutated"] is False
    assert report["official_denominator_policy_mutated"] is False

    true_rag = report["true_rag_metric_results"]
    assert true_rag["true_rag_retrieval_metric_gold_29"]["metric_kind"] == "retrieval_hit_mrr_ndcg"
    assert true_rag["true_rag_retrieval_metric_silver_1000"]["metric_kind"] == "retrieval_hit_mrr_ndcg"
    assert true_rag["structured_tool_outputs_mixed"] is False
    assert set(true_rag["family_breakdown"]) == {"PDF", "TEXT", "XLSX"}

    agentic = report["agentic_end_to_end_metric_results"]
    assert agentic["agentic_end_to_end_answer_metric_gold_29"]["answer_quality_metric_computed"] is True
    assert agentic["agentic_end_to_end_answer_metric_gold_29"]["raw_prompt_response_stored"] is False
    assert agentic["agentic_end_to_end_answer_metric_silver_diagnostic"]["diagnostic_only"] is True


def test_guardrail_cleanup_current_alias_and_runner_are_relaxed_but_leakage_guards_stay(
    report: dict[str, object],
) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_eval_registry as registry

    assert report["current_alias_policy"]["current_moved_from"] == "v5_6"
    assert report["current_alias_policy"]["current_moved_to"] == RUN_KEY
    assert report["current_resolves_to"] == RUN_KEY
    assert registry.resolve_run(RUN_KEY, root=ROOT).logical_key == RUN_KEY
    assert registry.resolve_run("current", root=ROOT).logical_key in {
        RUN_KEY,
        "v6_1_true_rag_corpus_expansion_and_metric_split_hardening",
        "v6_2_source_derived_materialization_scaleout_and_denominator_reality_check",
        "v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report",
        "v6_4_e2e_coverage_and_failure_taxonomy_nonprod",
        "v7_0_e2e_eval_architecture_closeout_nonprod",
    }
    checked = runner.check_run(RUN_KEY)
    assert checked["logical_run_key"] == RUN_KEY
    assert checked["status"] == STATUS

    cleanup = report["guardrail_cleanup"]
    assert cleanup["answer_quality_metric_computed_no_longer_forced_false"] is True
    assert cleanup["nonprod_index_cache_mutation_allowed"] is True
    assert cleanup["current_v5_6_pin_removed"] is True
    assert cleanup["agentic_loop_no_longer_always_fail_closed"] is True
    assert cleanup["tool_execution_unblocked_into_tool_lane"] is True
    assert cleanup["route_policy_manifest_no_longer_blocks_retrieval_or_tool_execution"] is True

    retained = report["retained_minimum_guardrails"]
    assert retained["gold_qrels_expected_supporting_relevance_answerability_mutation_forbidden"] is True
    assert retained["oracle_eval_field_candidate_input_forbidden"] is True
    assert retained["production_namespace_mutation_forbidden"] is True
    assert retained["source_atom_evidence_bundle_evidence_truth"] is True


def test_report_bundle_artifacts_docs_status_and_ledgers_are_written_consistently(tmp_path: Path) -> None:
    from ai.eval import rag_v60_agentic_true_rag_and_tool_loop_rewrite as v60a

    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        path = tmp_path / doc
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Ledger\n\nLast updated: 2026-06-06 KST.\n", encoding="utf-8")

    built = v60a.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    written, hashes = v60a.write_report_bundle(tmp_path, built)
    v60a.check_report(written, root=tmp_path)
    v60a.update_docs(tmp_path, written)
    v60a.append_status(tmp_path, written, artifact_hashes=hashes)

    run_root = tmp_path / "ai/eval/reports/rag-ingestion/runs" / RUN_KEY
    for name in {
        "report.json",
        "true_rag_metric_results.json",
        "tool_metric_results.json",
        "agentic_end_to_end_metric_results.json",
        "legacy_non_rag_path_inventory.jsonl",
        "true_rag_index_payload_schema.json",
        "true_rag_candidate_diagnostics.jsonl",
        "tool_execution_diagnostics.jsonl",
        "agentic_loop_trace_summary.jsonl",
        "leakage_probe_summary.json",
        "denominator_manifest.jsonl",
        "row_eligibility_ledger.jsonl",
        "exclusion_ledger.jsonl",
    }:
        assert (run_root / name).exists(), name

    assert len(_jsonl(run_root / "denominator_manifest.jsonl")) == written["denominator_manifest_rows"]
    assert len(_jsonl(run_root / "row_eligibility_ledger.jsonl")) == written["row_eligibility_ledger_rows"]
    assert len(_jsonl(run_root / "legacy_non_rag_path_inventory.jsonl")) == len(
        written["legacy_non_rag_path_inventory"]
    )
    status_lines = _jsonl(tmp_path / "ai/eval/reports/rag-ingestion/status.jsonl")
    assert status_lines[-1]["status"] == STATUS
    assert status_lines[-1]["current_resolves_to"] == RUN_KEY

    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        text = (tmp_path / doc).read_text(encoding="utf-8")
        assert "legacy non-RAG/tool/extraction path" in text
        assert "pre-materialized SearchUnit/SearchView" in text
        assert "repo-local SQLite/BM25 hybrid" in text
        assert "current moved from `v5_6` to `v6_0_agentic_true_rag_and_tool_loop_rewrite`" in text
