from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v5_9_real_nonprod_structured_hybrid_retrieval_reset"
SHORT_RUN_ID = "v5_9_real_nonprod_structured_hybrid_retrieval_reset_diagnostic_nonprod"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def v59_report() -> dict[str, object]:
    from ai.eval import rag_v59_real_nonprod_structured_hybrid_retrieval_reset_diagnostic_nonprod as v59

    report = v59.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    v59.check_report(report)
    return report


def test_v59_keeps_current_and_all_official_product_gates_closed(v59_report: dict[str, object]) -> None:
    report = v59_report
    assert report["logical_run_key"] == RUN_KEY
    assert report["short_run_id"] == SHORT_RUN_ID
    assert report["current_resolves_to"] == "v5_6"
    assert report["source_v5_8_short_run_id"] == "v5_8_retrieval_metric_evaluation_framework_diagnostic_nonprod"
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["source_official_metric_input_rows"] == 29
    assert report["answer_quality_metric_computed"] is False

    for key in (
        "gold_mutation",
        "qrels_mutation",
        "label_mutation",
        "expected_answer_mutation",
        "supporting_evidence_mutation",
        "denominator_mutation",
        "official_denominator_mutation",
        "source_registry_mutated",
        "production_index_mutation",
        "production_db_mutated",
        "cache_mutated",
        "training_dataset_created",
        "fine_tuning_started",
        "fine_tuning_executed",
        "ft_a_execution",
        "promotion_evidence",
        "product_success_evidence_allowed",
        "live_db_index_cache_readiness",
    ):
        assert report[key] is False
    assert report["protected_namespaces_touched"] == []


def test_v59_invokes_real_nonprod_structured_hybrid_adapter_not_projection_replay(
    v59_report: dict[str, object],
) -> None:
    adapter = v59_report["backend_adapter"]
    assert adapter["adapter_name"] == "nonprod_structured_hybrid_adapter"
    assert adapter["adapter_classification"] == "run_local_nonprod_faiss_plus_structural_lexical_hybrid"
    assert adapter["real_nonprod_adapter_invoked"] is True
    assert adapter["real_nonprod_index_query_path_invoked"] is True
    assert adapter["run_local_projection_replay_path_used"] is False
    assert adapter["nonprod_vector_backend_available"] is True
    assert adapter["real_vectordb_metric"] is True
    assert adapter["production_namespace_mutation"] is False
    assert adapter["nonprod_index_namespace"].startswith("v5_9_nonprod_structured_hybrid_")
    assert adapter["latency_counters"]["query_latency_ms_count"] == sum(
        tier["attempted_rows"] for tier in v59_report["metric_tiers"].values()
    )
    assert adapter["latency_counters"]["query_latency_ms_max"] > 0
    assert adapter["cost_counters"]["cost_counters_available"] is False
    assert "cost_usd" not in adapter["cost_counters"]
    assert adapter["cost_counters"]["unavailable_reason"]

    comparison = v59_report["comparison_to_prior_projection"]
    assert comparison["v5_8_backend_adapter"] == "run_local_sanitized_projection_adapter"
    assert comparison["quality_or_product_success_claim"] is False
    assert set(comparison["metric_delta_by_family"]) == {"PDF", "TEXT", "XLSX"}


def test_v59_candidate_request_is_sealed_and_forbidden_inputs_are_not_forwarded(
    v59_report: dict[str, object],
) -> None:
    from ai.eval import rag_v59_real_nonprod_structured_hybrid_retrieval_reset_diagnostic_nonprod as v59

    poison = {
        "query_text": "공급 현황을 알려줘",
        "source_family": "XLSX",
        "route_policy_manifest_id": "route-policy-v1",
        "top_k": 5,
        "index_namespace": "v5_9_nonprod_structured_hybrid_test",
        "target_search_unit_id": "target-su",
        "qrels_positive_candidate_id": "qrels-su",
        "baseline_topk_new": ["baseline-su"],
        "query_id": "q-sensitive",
        "row_id": "row-sensitive",
        "case_id": "case-sensitive",
        "source_title": "title shortcut",
        "workbook": "workbook shortcut.xlsx",
        "expected_answer": "gold answer",
        "supporting_evidence": "supporting text",
        "citation_locator": "page=1",
        "formula_result": "42",
        "direct_normalized_answer_value": "42",
    }
    sealed = v59.build_sealed_candidate_request(poison)
    assert set(sealed) == {"query_text", "source_family", "route_policy_manifest_id", "top_k", "index_namespace"}
    serialized = json.dumps(sealed, ensure_ascii=False)
    for forbidden in v59_report["candidate_generator_forbidden_input_fields"]:
        assert forbidden not in sealed
        assert forbidden not in serialized

    audit = v59.assert_candidate_request_isolation(poison)
    assert audit["forbidden_input_forwarded_count"] == 0
    assert audit["sealed_input_fence_passed"] is True
    assert v59_report["candidate_generation_sealed_input_fence"] is True
    assert v59_report["route_policy_manifest_hard_guard_preserved"] is True
    assert v59_report["llm_route_adjudication_guard_relaxation_allowed"] is False


def test_v59_structured_searchunit_searchview_schema_is_source_derived_and_redacted(
    v59_report: dict[str, object],
) -> None:
    from ai.eval import rag_v59_real_nonprod_structured_hybrid_retrieval_reset_diagnostic_nonprod as v59

    schema = v59_report["search_unit_search_view_schema"]
    assert set(schema) == {"XLSX", "PDF", "TEXT"}
    assert set(schema["XLSX"]["required_payload_fields"]) >= {
        "workbook_safe_id",
        "sheet_safe_id",
        "table_range_id",
        "row_index_range",
        "column_index_range",
        "row_header_path",
        "column_header_path",
        "merged_cell_header_propagation",
        "display_value",
        "value_type",
        "number_date_format_class",
        "table_boundary",
        "source_atom_id",
    }
    assert set(schema["PDF"]["required_payload_fields"]) >= {
        "document_safe_id",
        "page",
        "block_id",
        "bbox",
        "section_path",
        "table_id",
        "row_column_hints",
        "caption_context",
        "native_ocr_trust",
        "source_atom_id",
    }
    assert set(schema["TEXT"]["required_payload_fields"]) >= {
        "section_heading_path",
        "chunk_id",
        "lexical_aliases",
        "source_atom_id",
    }

    rows = v59_report["structured_search_view_diagnostic_rows"]
    assert rows
    assert {row["source_family"] for row in rows} == {"PDF", "TEXT", "XLSX"}
    for row in rows:
        v59.validate_structured_search_view(row)
        payload = json.dumps(row["search_view_payload"], ensure_ascii=False)
        for forbidden in (
            "source_title",
            "workbook_filename",
            "source_file_name",
            "raw_local_path",
            "formula_text",
            "formula_result",
            "expected_answer",
            "supporting_evidence",
            "qrels_positive_candidate_id",
            "target_search_unit_id",
            "citation_locator",
            "direct_normalized_answer_value",
        ):
            assert forbidden not in payload


def test_v59_sourceatom_evidencebundle_truth_and_ledgers_are_consistent(v59_report: dict[str, object]) -> None:
    report = v59_report
    hydration = report["source_atom_evidence_bundle_hydration"]
    assert hydration["SourceAtom_EvidenceBundle_role"] == "evidence_truth"
    assert hydration["SearchView_vector_payload_role"] == "candidate_only"
    assert hydration["source_atom_hydration_success_count"] > 0
    assert hydration["vector_payload_evidence_truth_violation_count"] == 0
    assert hydration["source_atom_store_broad_scan_attempt_count"] == 0

    attempted = sum(tier["attempted_rows"] for tier in report["metric_tiers"].values())
    assert len(report["denominator_manifest"]) == attempted
    assert len(report["row_eligibility_ledger"]) == attempted
    assert len(report["adapter_query_diagnostics"]) == attempted
    assert all(row["metric_tier"] in report["metric_tiers"] for row in report["denominator_manifest"])
    assert all(row["eligibility_status"] for row in report["row_eligibility_ledger"])
    assert all(row["candidate_generation_adapter_classification"] == "nonprod_structured_hybrid_adapter" for row in report["row_eligibility_ledger"])

    for tier_name, tier in report["metric_tiers"].items():
        assert tier["attempted_rows"] == report["metric_results"][tier_name]["coverage_adjusted"]["denominator"]
        assert tier["computed_rows"] == report["metric_results"][tier_name]["computed_only"]["denominator"]


def test_v59_artifacts_status_docs_runner_current_and_mutation_rejection(
    tmp_path: Path,
    v59_report: dict[str, object],
) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_v59_real_nonprod_structured_hybrid_retrieval_reset_diagnostic_nonprod as v59
    from ai.tests.rag_current_profile import NON_CURRENT_RAG_TEST_FILES

    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        path = tmp_path / doc
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Ledger\n\nLast updated: 2026-06-06 KST.\n", encoding="utf-8")

    written, artifact_hashes = v59.write_report_bundle(tmp_path, v59_report)
    v59.check_report(written, root=tmp_path)
    v59.update_docs(tmp_path, written)
    v59.append_status(tmp_path, written, artifact_hashes=artifact_hashes)

    expected_artifacts = {
        "report_json",
        "metric_tiers_json",
        "metric_results_json",
        "leakage_probe_summary_json",
        "denominator_manifest_jsonl",
        "row_eligibility_ledger_jsonl",
        "exclusion_ledger_jsonl",
        "adapter_query_diagnostics_jsonl",
        "structured_search_views_jsonl",
        "status_jsonl",
    }
    assert set(written["artifact_paths"]) == expected_artifacts
    run_root = tmp_path / "reports/rag_eval/rag-ingestion/runs/v5_9_real_nonprod_structured_hybrid_retrieval_reset"
    assert not list(run_root.glob("*.md"))
    assert len(_read_jsonl(tmp_path / written["artifact_paths"]["denominator_manifest_jsonl"])) == sum(
        tier["attempted_rows"] for tier in written["metric_tiers"].values()
    )

    status_rows = _read_jsonl(tmp_path / "reports/rag_eval/rag-ingestion/status.jsonl")
    latest = status_rows[-1]
    assert latest["short_run_id"] == SHORT_RUN_ID
    assert latest["current_resolves_to"] == "v5_6"
    assert latest["real_nonprod_adapter_invoked"] is True
    assert latest["balanced_diagnostic_rows"] == 300

    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        text = (tmp_path / doc).read_text(encoding="utf-8")
        assert SHORT_RUN_ID in text
        assert "current remains `v5_6`" in text or "current` remains `v5_6" in text
        assert "diagnostic-only" in text

    assert "ai/tests/test_rag_v59_real_nonprod_structured_hybrid_retrieval_reset_contract.py" in NON_CURRENT_RAG_TEST_FILES
    checked = runner.check_run(RUN_KEY)
    assert checked["short_run_id"] == SHORT_RUN_ID
    assert runner.check_run("current")["short_run_id"] == "v5_6_official_metric_scored_execution_and_failure_attribution_nonprod"

    for path, value, message in (
        (("current_resolves_to",), "v5_9", "current"),
        (("official_metric",), True, "official"),
        (("official_metric_input_rows",), 29, "official metric input"),
        (("gold_mutation",), True, "closed gate"),
        (("source_registry_mutated",), True, "closed gate"),
        (("production_index_mutation",), True, "closed gate"),
        (("live_db_index_cache_readiness",), True, "closed gate"),
        (("promotion_evidence",), True, "closed gate"),
        (("backend_adapter", "run_local_projection_replay_path_used"), True, "projection"),
        (("backend_adapter", "real_nonprod_adapter_invoked"), False, "adapter"),
    ):
        mutated = json.loads(json.dumps(v59_report))
        cursor = mutated
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        with pytest.raises(ValueError, match=message):
            v59.check_report(mutated)
