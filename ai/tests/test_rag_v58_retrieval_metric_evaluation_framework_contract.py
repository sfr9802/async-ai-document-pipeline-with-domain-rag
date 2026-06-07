from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v5_8_retrieval_metric_evaluation_framework"
SHORT_RUN_ID = "v5_8_retrieval_metric_evaluation_framework_diagnostic_nonprod"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def v58_report() -> dict[str, object]:
    from ai.eval import rag_v58_retrieval_metric_evaluation_framework_diagnostic_nonprod as v58

    report = v58.build_report(root=ROOT, generated_at="2026-06-06T00:00:00Z")
    v58.check_report(report)
    return report


def test_v58_report_defines_separate_metric_tiers_without_moving_current(v58_report: dict[str, object]) -> None:
    report = v58_report
    assert report["logical_run_key"] == RUN_KEY
    assert report["short_run_id"] == SHORT_RUN_ID
    assert report["current_resolves_to"] == "v5_6"
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["official_metric"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["source_official_metric_input_rows"] == 29
    assert report["official_denominator_mutation"] is False
    assert report["promotion_evidence"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["live_db_index_cache_readiness"] is False
    assert report["answer_quality_metric_computed"] is False

    tiers = report["metric_tiers"]
    assert set(tiers) == {
        "official_gold_smoke_metric",
        "valid_live_retrieval_metric",
        "balanced_diagnostic_retrieval_metric",
        "stress_diagnostic_metric",
    }
    assert report["metric_tier_order"] == [
        "official_gold_smoke_metric",
        "valid_live_retrieval_metric",
        "balanced_diagnostic_retrieval_metric",
        "stress_diagnostic_metric",
    ]

    official = tiers["official_gold_smoke_metric"]
    assert official["source_artifact"] == "ai/eval/reports/rag-ingestion/runs/v5_5/official_metric_input.jsonl"
    assert official["attempted_rows"] == 29
    assert official["official_denominator"] == 29
    assert official["diagnostic_denominator"] == 0
    assert official["source_family_distribution"] == {"PDF": 4, "TEXT": 6, "XLSX": 19}
    assert official["official_denominator_expanded"] is False

    live = tiers["valid_live_retrieval_metric"]
    assert live["source_artifact"] == official["source_artifact"]
    assert live["attempted_rows"] == 29
    assert live["computed_rows"] == report["valid_live_retrieval_metric_rows"]
    assert live["computed_rows"] == 18
    assert live["leakage_excluded_rows"] == 0
    assert live["backend_index_cache_unavailable_rows"] == 0
    assert live["coverage_adjusted_denominator"] == 29
    assert live["computed_only_denominator"] == 18

    balanced = tiers["balanced_diagnostic_retrieval_metric"]
    assert balanced["not_official_qrels"] is True
    assert balanced["promotion_evidence"] is False
    assert balanced["product_success_evidence_allowed"] is False
    assert balanced["attempted_rows"] == 300
    assert balanced["diagnostic_denominator"] == 300
    assert balanced["source_family_distribution"] == {"PDF": 100, "TEXT": 100, "XLSX": 100}
    assert balanced["balanced_target_met"] is True
    assert balanced["headline_diagnostic_metric"] is True

    stress = tiers["stress_diagnostic_metric"]
    assert stress["partition"] == "stress_or_challenge"
    assert stress["not_official_qrels"] is True
    assert stress["headline_diagnostic_metric"] is False
    assert stress["attempted_rows"] == 90
    assert stress["source_family_distribution"] == {"PDF": 30, "TEXT": 30, "XLSX": 30}


def test_v58_metrics_record_computed_only_and_coverage_adjusted_results(v58_report: dict[str, object]) -> None:
    results = v58_report["metric_results"]
    for tier_name in (
        "official_gold_smoke_metric",
        "valid_live_retrieval_metric",
        "balanced_diagnostic_retrieval_metric",
        "stress_diagnostic_metric",
    ):
        tier_result = results[tier_name]
        for view_name in ("computed_only", "coverage_adjusted"):
            view = tier_result[view_name]
            assert set(view["metrics"]) == {"hit_at_1", "hit_at_3", "hit_at_5", "mrr_at_5", "ndcg_at_5"}
            assert set(view["micro_overall"]) == set(view["metrics"])
            assert set(view["macro_by_source_family"]) == set(view["metrics"])
            assert set(view["per_family"]) == {"PDF", "TEXT", "XLSX"}

    live = results["valid_live_retrieval_metric"]
    assert live["computed_only"]["denominator"] == 18
    assert live["coverage_adjusted"]["denominator"] == 29
    assert live["coverage_adjusted"]["metrics"]["hit_at_1"] <= live["computed_only"]["metrics"]["hit_at_1"]
    assert live["coverage_adjusted"]["metrics"]["mrr_at_5"] <= live["computed_only"]["metrics"]["mrr_at_5"]


def test_v58_ledgers_account_for_every_row_and_every_exclusion(v58_report: dict[str, object]) -> None:
    denominator_rows = v58_report["denominator_manifest"]
    eligibility_rows = v58_report["row_eligibility_ledger"]
    exclusion_rows = v58_report["exclusion_ledger"]
    attempted = sum(tier["attempted_rows"] for tier in v58_report["metric_tiers"].values())

    assert len(denominator_rows) == attempted
    assert len(eligibility_rows) == attempted
    assert all(row["metric_tier"] in v58_report["metric_tiers"] for row in denominator_rows)
    assert all(row["eligibility_status"] for row in eligibility_rows)

    official_rows = [row for row in denominator_rows if row["metric_tier"] == "official_gold_smoke_metric"]
    assert len(official_rows) == 29
    assert {row["source_artifact"] for row in official_rows} == {
        "ai/eval/reports/rag-ingestion/runs/v5_5/official_metric_input.jsonl"
    }
    assert all("silver" not in row["source_artifact"] for row in official_rows)

    live_exclusions = [row for row in exclusion_rows if row["metric_tier"] == "valid_live_retrieval_metric"]
    assert live_exclusions
    assert all(row["exclusion_reason"] for row in live_exclusions)
    assert any(row["exclusion_reason"] == "no_live_candidates" for row in live_exclusions)


def test_v58_leakage_probe_summary_is_tiered_and_helpers_reject_sensitive_candidate_features(
    v58_report: dict[str, object],
) -> None:
    from ai.eval import rag_v58_retrieval_metric_evaluation_framework_diagnostic_nonprod as v58

    summary = v58_report["leakage_probe_summary"]
    assert set(summary["tiers"]) == set(v58_report["metric_tiers"])
    for tier in summary["tiers"].values():
        assert tier["leakage_probe_failed_count"] == 0
        assert tier["identity_leakage_failed_count"] == 0
        assert tier["source_shortcut_dependency_failed_count"] == 0

    bad = v58.classify_leakage_probe_result(
        metric_tier="valid_live_retrieval_metric",
        scoring_row={"row_id": "r", "query_id": "q", "source_family": "TEXT", "retrieval_metric_eligible": True},
        original_candidate_ids=["a", "b"],
        mutated_candidate_ids_by_probe={
            "target_search_unit_id_poison": ["target"],
            "qrels_positive_poison": ["qrels"],
            "baseline_topk_new_removed_or_shuffled": ["b", "a"],
            "supporting_expected_citation_removed": ["a"],
            "query_row_id_poison": ["identity-sensitive"],
            "source_title_workbook_filename_redaction": ["shortcut-sensitive"],
        },
    )
    assert bad["leakage_probe_failed"] is True
    assert bad["target_qrels_baseline_leakage_failed"] is True
    assert bad["identity_leakage_failed"] is True
    assert bad["source_shortcut_dependency_failed"] is True


def test_v58_artifacts_status_docs_runner_and_current_alias_are_additive(
    tmp_path: Path,
    v58_report: dict[str, object],
) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_v58_retrieval_metric_evaluation_framework_diagnostic_nonprod as v58
    from ai.tests.rag_current_profile import NON_CURRENT_RAG_TEST_FILES

    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        path = tmp_path / doc
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Ledger\n\nLast updated: 2026-06-06 KST.\n", encoding="utf-8")

    written, artifact_hashes = v58.write_report_bundle(tmp_path, v58_report)
    v58.check_report(written, root=tmp_path)
    v58.update_docs(tmp_path, written)
    v58.append_status(tmp_path, written, artifact_hashes=artifact_hashes)

    expected_artifacts = {
        "report_json",
        "metric_tiers_json",
        "denominator_manifest_jsonl",
        "row_eligibility_ledger_jsonl",
        "metric_results_json",
        "exclusion_ledger_jsonl",
        "leakage_probe_summary_json",
        "status_jsonl",
    }
    assert set(written["artifact_paths"]) == expected_artifacts
    assert written["generated_artifacts"] == [
        written["artifact_paths"]["report_json"],
        written["artifact_paths"]["metric_tiers_json"],
        written["artifact_paths"]["denominator_manifest_jsonl"],
        written["artifact_paths"]["row_eligibility_ledger_jsonl"],
        written["artifact_paths"]["metric_results_json"],
        written["artifact_paths"]["exclusion_ledger_jsonl"],
        written["artifact_paths"]["leakage_probe_summary_json"],
    ]
    run_root = tmp_path / "ai/eval/reports/rag-ingestion/runs/v5_8_retrieval_metric_evaluation_framework"
    assert not list(run_root.glob("*.md"))
    written_report_json = json.loads((tmp_path / written["artifact_paths"]["report_json"]).read_text(encoding="utf-8"))
    assert written_report_json["metric_tier_order"] == written["metric_tier_order"]
    assert set(written_report_json["metric_tiers"]) == set(written["metric_tiers"])
    assert len(_read_jsonl(tmp_path / written["artifact_paths"]["denominator_manifest_jsonl"])) == sum(
        tier["attempted_rows"] for tier in written["metric_tiers"].values()
    )

    status_rows = _read_jsonl(tmp_path / "ai/eval/reports/rag-ingestion/status.jsonl")
    latest = status_rows[-1]
    assert latest["short_run_id"] == SHORT_RUN_ID
    assert latest["current_resolves_to"] == "v5_6"
    assert latest["tier_count"] == 4
    assert latest["balanced_diagnostic_rows"] == 300

    for doc in (
        "docs/rag-ingestion-progress.md",
        "docs/rag-ingestion-measurements.md",
        "docs/rag-ingestion-triage.md",
    ):
        text = (tmp_path / doc).read_text(encoding="utf-8")
        assert SHORT_RUN_ID in text
        assert "current` remains `v5_6" in text or "current remains `v5_6" in text

    assert "ai/tests/test_rag_v58_retrieval_metric_evaluation_framework_contract.py" in NON_CURRENT_RAG_TEST_FILES
    checked = runner.check_run(RUN_KEY)
    assert checked["short_run_id"] == SHORT_RUN_ID
    assert runner.check_run("current")["short_run_id"] == "v5_6_official_metric_scored_execution_and_failure_attribution_nonprod"


def test_v58_check_report_rejects_opened_gates_drift_and_silver_in_official_tier(
    v58_report: dict[str, object],
) -> None:
    from ai.eval import rag_v58_retrieval_metric_evaluation_framework_diagnostic_nonprod as v58

    for path, value, message in (
        (("current_resolves_to",), "v5_8", "current"),
        (("official_metric",), True, "official"),
        (("official_metric_input_rows",), 29, "official metric input"),
        (("source_official_metric_input_rows",), 30, "source official"),
        (("official_denominator_mutation",), True, "closed gate"),
        (("gold_mutation",), True, "closed gate"),
        (("qrels_mutation",), True, "closed gate"),
        (("label_mutation",), True, "closed gate"),
        (("expected_answer_mutation",), True, "closed gate"),
        (("supporting_evidence_mutation",), True, "closed gate"),
        (("denominator_mutation",), True, "closed gate"),
        (("source_registry_mutated",), True, "closed gate"),
        (("index_rebuilt",), True, "closed gate"),
        (("answer_quality_metric_computed",), True, "answer quality"),
        (("live_db_index_cache_readiness",), True, "closed gate"),
        (("promotion_evidence",), True, "closed gate"),
        (("metric_tiers", "official_gold_smoke_metric", "attempted_rows"), 30, "official tier"),
        (
            ("metric_tiers", "official_gold_smoke_metric", "source_artifact"),
            "ai/eval/reports/rag-ingestion/runs/v4_7_15/silver.jsonl",
            "official tier",
        ),
        (("metric_tiers", "balanced_diagnostic_retrieval_metric", "source_family_distribution"), {"XLSX": 300}, "balanced"),
    ):
        mutated = json.loads(json.dumps(v58_report))
        cursor = mutated
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        with pytest.raises(ValueError, match=message):
            v58.check_report(mutated)
