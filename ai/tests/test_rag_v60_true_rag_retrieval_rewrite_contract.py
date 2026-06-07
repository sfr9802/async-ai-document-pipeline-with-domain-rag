from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v6_0_true_rag_retrieval_rewrite"
SHORT_RUN_ID = "v6_0_true_rag_retrieval_rewrite"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def v60_report() -> dict[str, object]:
    from ai.eval import rag_v60_true_rag_retrieval_rewrite as v60

    report = v60.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    v60.check_report(report)
    return report


def test_v60_defines_true_rag_schemas_and_rejects_forbidden_oracle_payload_fields(
    v60_report: dict[str, object],
) -> None:
    from ai.eval import rag_v60_true_rag_retrieval_rewrite as v60

    assert v60_report["logical_run_key"] == RUN_KEY
    assert v60_report["short_run_id"] == SHORT_RUN_ID
    assert v60_report["current_resolves_to"] == "v5_6"
    assert v60_report["diagnostic_only"] is True
    assert v60_report["non_production"] is True
    assert v60_report["official_metric"] is False
    assert v60_report["official_metric_input_rows"] == 0
    assert v60_report["answer_quality_metric_computed"] is False

    schema = v60_report["true_rag_index_payload_schema"]
    assert set(schema["families"]) == {"PDF", "TEXT", "XLSX"}
    assert set(schema["schema_names"]) == {
        "TrueRagSearchUnit",
        "TrueRagSearchView",
        "TrueRagIndexPayload",
        "TrueRagCandidate",
    }
    assert "source_title" in schema["forbidden_fields"]
    assert "workbook_filename" in schema["forbidden_fields"]
    assert "query_id" in schema["forbidden_fields"]
    assert "row_id" in schema["forbidden_fields"]
    assert "case_id" in schema["forbidden_fields"]
    assert "target_search_unit_id" in schema["forbidden_fields"]
    assert "expected_answer" in schema["forbidden_fields"]
    assert "supporting_evidence" in schema["forbidden_fields"]
    assert "formula_text" in schema["forbidden_fields"]
    assert "direct_normalized_answer_value" in schema["forbidden_fields"]

    poison_payload = {
        "payload_id": "poison",
        "namespace": "v6_0_true_rag_nonprod_test",
        "source_family": "XLSX",
        "search_view_id": "sv-poison",
        "source_atom_ids": ["sa-poison"],
        "embedding_text": "safe source text",
        "bm25_text": "safe source text",
        "metadata": {
            "workbook_safe_id": "wb-safe",
            "sheet_safe_id": "sheet-safe",
            "row_header_path": ["region"],
            "query_id": "q-oracle",
            "expected_answer": "gold",
        },
    }
    with pytest.raises(ValueError, match="forbidden"):
        v60.validate_true_rag_index_payload(poison_payload)

    for row in v60_report["materialized_search_units"]:
        v60.validate_true_rag_search_unit(row)
    for row in v60_report["materialized_search_views"]:
        v60.validate_true_rag_search_view(row)
    for row in v60_report["index_payload_diagnostics"]:
        v60.validate_true_rag_index_payload(row["index_payload"])


def test_v60_materializes_pdf_xlsx_text_without_query_time_raw_parsing(v60_report: dict[str, object]) -> None:
    materialization = v60_report["materialization_contract"]
    pdf = materialization["PDF"]
    xlsx = materialization["XLSX"]
    text = materialization["TEXT"]

    assert pdf["query_time_pdf_file_open_or_parse_allowed"] is False
    assert set(pdf["unit_granularity"]) >= {
        "page",
        "block",
        "paragraph",
        "table-row",
        "table-cell-or-row-summary",
        "caption",
        "section-path",
    }
    assert set(pdf["source_derived_metadata"]) >= {
        "page",
        "block_id",
        "bbox",
        "section_path",
        "table_id",
        "row_column_hints",
        "caption",
        "ocr_native_text_trust",
    }

    assert xlsx["query_time_xlsx_file_open_or_parse_allowed"] is False
    assert set(xlsx["unit_granularity"]) >= {
        "workbook-safe-id",
        "sheet-safe-id",
        "table",
        "range",
        "row",
        "column",
        "cell-or-small-range",
        "header-path",
        "display-value",
        "value-type",
        "number-format-class",
    }
    assert set(xlsx["source_derived_metadata"]) >= {
        "merged_header_propagation",
        "row_header_path",
        "column_header_path",
        "table_boundary",
    }
    assert "workbook_filename" not in xlsx["source_derived_metadata"]
    assert "formula_text" not in xlsx["source_derived_metadata"]
    assert "formula_evaluation" not in xlsx["source_derived_metadata"]

    assert text["depends_on_archived_topk_replay"] is False
    assert set(text["unit_granularity"]) >= {"section", "heading", "chunk", "lexical_alias"}


def test_v60_legacy_retrieval_paths_are_classified_non_rag_and_isolated(
    v60_report: dict[str, object],
) -> None:
    expected = {
        "file_level_retrieval_then_runtime_parser_search",
        "raw_pdf_xlsx_query_time_parsing",
        "route_policy_forced_search",
        "row_specific_exception",
        "query_id_row_id_case_id_lookup",
        "source_title_workbook_file_name_shortcut",
        "direct_normalized_answer_value_matching",
        "formula_text_or_evaluation",
        "target_qrels_gold_expected_supporting_citation_locator_use",
        "baseline_topk_replay",
    }
    legacy = v60_report["legacy_non_rag_retrieval_path"]
    assert set(legacy["classified_items"]) == expected
    assert legacy["isolated_from_true_rag_retrieval"] is True
    assert legacy["true_rag_candidate_generation_uses_any_legacy_path"] is False
    assert legacy["legacy_path_metric_namespace"] == "legacy_non_rag_retrieval_path"


def test_v60_real_nonprod_adapter_fails_closed_without_fake_noop_or_replay_backend(
    v60_report: dict[str, object],
) -> None:
    from ai.eval import rag_v60_true_rag_retrieval_rewrite as v60

    adapter = v60_report["backend_adapter"]
    assert adapter["adapter_name"] == "real_nonprod_true_rag_hybrid_adapter"
    assert adapter["fake_noop_or_replay_backend_used"] is False
    assert adapter["baseline_topk_replay_used"] is False
    assert adapter["run_local_projection_replay_path_used"] is False
    assert adapter["nonprod_namespace_proof"]["namespace"].startswith("v6_0_true_rag_nonprod_")

    unavailable = v60.RealNonprodTrueRagHybridAdapter(backend_url="", namespace="v6_0_true_rag_nonprod_test").retrieve(
        query_text="sample",
        source_family="TEXT",
        top_k=5,
    )
    assert unavailable.fail_closed is True
    assert unavailable.candidates == ()
    assert unavailable.unavailable_reason == "nonprod_backend_url_missing"
    assert unavailable.fake_noop_or_replay_backend_used is False

    assert adapter["real_vectordb_metric"] is False
    assert adapter["real_vectordb_metric_requirements"]["backend_call_proof"] is False
    assert adapter["real_vectordb_metric_requirements"]["namespace_proof"] is True
    assert adapter["real_vectordb_metric_requirements"]["forbidden_input_isolation_proof"] is True
    assert adapter["real_vectordb_metric_requirements"]["latency_or_unavailable_reason_recorded"] is True


def test_v60_langgraph_contract_keeps_routing_orchestration_only(v60_report: dict[str, object]) -> None:
    from ai.eval import rag_v60_true_rag_retrieval_rewrite as v60

    contract = v60_report["langgraph_contract"]
    assert contract["route_node_role"] == "query_classification_only"
    assert contract["route_node_candidate_construction_allowed"] is False
    assert contract["route_node_forced_parser_routing_allowed"] is False
    assert contract["retrieval_node_allowed_adapter"] == "real_nonprod_true_rag_hybrid_adapter"
    assert contract["row_specific_exception_allowed"] is False
    assert contract["deterministic_hard_guard_llm_relaxation_allowed"] is False

    mutated = dict(contract)
    mutated["deterministic_hard_guard_llm_relaxation_allowed"] = True
    with pytest.raises(ValueError, match="LLM"):
        v60.assert_langgraph_contract(mutated)

    mutated = dict(contract)
    mutated["route_node_candidate_construction_allowed"] = True
    with pytest.raises(ValueError, match="route node"):
        v60.assert_langgraph_contract(mutated)


def test_v60_metrics_keep_true_rag_retrieval_separate_from_structured_tool_lane(
    v60_report: dict[str, object],
) -> None:
    tiers = v60_report["metric_tiers"]
    assert set(tiers) == {"true_rag_retrieval_metric", "structured_tool_required_diagnostic_metric"}
    true_rag = tiers["true_rag_retrieval_metric"]
    assert set(true_rag["family_breakdown"]) == {"PDF", "TEXT", "XLSX"}
    assert true_rag["computed_rows"] == 0
    assert true_rag["no_candidate_count"] == true_rag["attempted_rows"]
    assert true_rag["file_routing_accuracy_mixed_into_rag_metric"] is False
    assert true_rag["locator_extraction_accuracy_mixed_into_rag_metric"] is False
    assert true_rag["structured_computation_tool_success_mixed_into_rag_metric"] is False

    structured = tiers["structured_tool_required_diagnostic_metric"]
    assert structured["structured_tool_required_rows"] > 0
    assert structured["included_in_true_rag_retrieval_denominator"] is False
    assert v60_report["metric_results"]["true_rag_retrieval_metric"]["family_breakdown"] == true_rag["family_breakdown"]
    assert v60_report["forbidden_input_isolation_probe"]["passed"] is True
    assert v60_report["hydration_success_count"] == v60_report["evidence_bundle_renderable_count"]


def test_v60_artifacts_status_docs_runner_current_and_ledger_consistency(
    tmp_path: Path,
    v60_report: dict[str, object],
) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_v60_true_rag_retrieval_rewrite as v60
    from ai.tests.rag_current_profile import NON_CURRENT_RAG_TEST_FILES

    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        path = tmp_path / doc
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Ledger\n\nLast updated: 2026-06-06 KST.\n", encoding="utf-8")

    written, artifact_hashes = v60.write_report_bundle(tmp_path, v60_report)
    v60.check_report(written, root=tmp_path)
    v60.update_docs(tmp_path, written)
    v60.append_status(tmp_path, written, artifact_hashes=artifact_hashes)

    expected_artifacts = {
        "report_json",
        "metric_results_json",
        "metric_tiers_json",
        "leakage_probe_summary_json",
        "denominator_manifest_jsonl",
        "row_eligibility_ledger_jsonl",
        "exclusion_ledger_jsonl",
        "true_rag_index_payload_schema_json",
        "true_rag_candidate_diagnostics_jsonl",
        "status_jsonl",
    }
    assert set(written["artifact_paths"]) == expected_artifacts
    run_root = tmp_path / "ai/eval/reports/rag-ingestion/runs/v6_0_true_rag_retrieval_rewrite"
    assert not list(run_root.glob("*.md"))

    denominator_rows = _read_jsonl(tmp_path / written["artifact_paths"]["denominator_manifest_jsonl"])
    eligibility_rows = _read_jsonl(tmp_path / written["artifact_paths"]["row_eligibility_ledger_jsonl"])
    exclusion_rows = _read_jsonl(tmp_path / written["artifact_paths"]["exclusion_ledger_jsonl"])
    attempted = sum(tier["attempted_rows"] for tier in written["metric_tiers"].values())
    assert len(denominator_rows) == attempted
    assert len(eligibility_rows) == attempted
    assert len(exclusion_rows) == sum(1 for row in eligibility_rows if row["included_in_metric"] is False)

    status_rows = _read_jsonl(tmp_path / "ai/eval/reports/rag-ingestion/status.jsonl")
    latest = status_rows[-1]
    assert latest["short_run_id"] == SHORT_RUN_ID
    assert latest["current_resolves_to"] == "v5_6"
    assert latest["real_nonprod_backend_invoked"] is False
    assert latest["real_vectordb_metric"] is False

    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        text = (tmp_path / doc).read_text(encoding="utf-8")
        assert SHORT_RUN_ID in text
        assert "legacy non-RAG" in text
        assert "current remains `v5_6`" in text or "current` remains `v5_6" in text
        assert "diagnostic-only" in text
        assert "structured tool" in text

    assert "ai/tests/test_rag_v60_true_rag_retrieval_rewrite_contract.py" in NON_CURRENT_RAG_TEST_FILES
    checked = runner.check_run(RUN_KEY)
    assert checked["short_run_id"] == SHORT_RUN_ID
    assert runner.check_run("current")["short_run_id"] == "v5_6_official_metric_scored_execution_and_failure_attribution_nonprod"


def test_v60_check_report_rejects_gate_and_payload_drift(v60_report: dict[str, object]) -> None:
    from ai.eval import rag_v60_true_rag_retrieval_rewrite as v60

    for path, value, message in (
        (("current_resolves_to",), "v6_0_true_rag_retrieval_rewrite", "current"),
        (("official_metric",), True, "official"),
        (("official_metric_input_rows",), 29, "official metric input"),
        (("gold_mutation",), True, "closed gate"),
        (("qrels_mutation",), True, "closed gate"),
        (("expected_answer_mutation",), True, "closed gate"),
        (("supporting_evidence_mutation",), True, "closed gate"),
        (("source_registry_mutated",), True, "closed gate"),
        (("production_index_mutation",), True, "closed gate"),
        (("backend_adapter", "fake_noop_or_replay_backend_used"), True, "fake"),
        (("backend_adapter", "real_vectordb_metric"), True, "real vectordb"),
        (("true_rag_index_payload_schema", "forbidden_fields"), ["expected_answer"], "schema"),
    ):
        mutated = json.loads(json.dumps(v60_report))
        cursor = mutated
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        with pytest.raises(ValueError, match=message):
            v60.check_report(mutated)
