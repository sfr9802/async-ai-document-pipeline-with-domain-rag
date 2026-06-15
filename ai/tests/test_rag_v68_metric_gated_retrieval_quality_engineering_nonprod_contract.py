from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v6_8_metric_gated_retrieval_quality_engineering_nonprod"
ROLLBACK_KEY = "v6_7_agentic_retry_fail_closed_policy_nonprod"
STATUS = "V6_8_METRIC_GATED_RETRIEVAL_QUALITY_ENGINEERING_NONPROD_READY"
LATEST_CURRENT_RUN_KEY = "v6_9_answer_quality_gate_packet_nonprod"
PROTECTED_PATHS = (
    "ai/eval/eval_queries",
    "ai/eval/source_registry",
    "ai/eval/indexes",
    "ai/eval/silver",
)
REQUIRED_FALSE_FIELDS = {
    "official_metric",
    "retrieval_quality_metric_computed",
    "answer_quality_metric_computed",
    "promotion_evidence",
    "product_success_evidence_allowed",
    "live_db_index_cache_readiness",
    "production_routing_enabled",
    "production_db_mutated",
    "production_index_mutation",
    "production_namespace_mutated",
    "production_cache_mutated",
    "gold_mutation",
    "qrels_mutation",
    "label_mutation",
    "relevance_label_mutation",
    "answerability_label_mutation",
    "expected_answer_mutation",
    "supporting_evidence_mutation",
    "denominator_mutation",
    "official_denominator_mutation",
    "source_registry_mutated",
    "training_dataset_created",
    "fine_tuning_dataset_export_created",
    "fine_tuning_started",
    "fine_tuning_executed",
    "ft_a_execution",
    "raw_prompt_payload_written",
    "raw_response_payload_written",
}


@pytest.fixture(scope="module")
def v68_module():
    from ai.eval import rag_v68_metric_gated_retrieval_quality_engineering_nonprod as v68

    return v68


@pytest.fixture()
def report(v68_module) -> dict[str, object]:
    built = v68_module.build_report(root=ROOT, generated_at="2026-06-07T05:00:00Z")
    v68_module.check_report(built)
    return built


def test_v68_schema_current_and_rollback(report: dict[str, object]) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_eval_registry as registry

    assert registry.resolve_run(RUN_KEY, root=ROOT).logical_key == RUN_KEY
    assert registry.resolve_run("current", root=ROOT).logical_key == LATEST_CURRENT_RUN_KEY
    assert registry.resolve_run(ROLLBACK_KEY, root=ROOT).logical_key == ROLLBACK_KEY
    assert runner.DEFAULT_RUN_KEY == LATEST_CURRENT_RUN_KEY
    assert runner.check_run(RUN_KEY)["logical_run_key"] == RUN_KEY
    assert runner.check_run("current")["logical_run_key"] == LATEST_CURRENT_RUN_KEY
    assert runner.check_run(ROLLBACK_KEY)["logical_run_key"] == ROLLBACK_KEY

    assert report["run_id"] == RUN_KEY
    assert report["schema_version"] == "v6_8_metric_gated_retrieval_quality_engineering_nonprod_report_v1"
    assert report["status"] == STATUS
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["rollback_key"] == ROLLBACK_KEY
    assert report["current_resolves_to"] == RUN_KEY
    assert report["current_alias_policy"]["current_moved_from"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["current_moved_to"] == RUN_KEY


def test_v68_retrieval_metric_gate_is_closed_without_safe_bridge(report: dict[str, object]) -> None:
    assert report["run_id"] == RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY
    gate = report["retrieval_quality_gate"]
    assert gate["safe_read_only_denominator_available"] is False
    assert report["retrieval_quality_metric_computed"] is False
    assert gate["computed_only_denominator"] == 0
    assert gate["hit_at_k_computed"] is False
    assert gate["mrr_computed"] is False
    assert gate["ndcg_computed"] is False
    assert gate["blocked_reason"] == "no_safe_read_only_label_qrels_bridge_available"
    assert gate["tool_outputs_excluded_from_true_rag_metrics"] is True
    assert gate["expected_supporting_qrels_used_for_candidate_generation"] is False


def test_v68_metric_denominators_are_separate(report: dict[str, object]) -> None:
    assert report["v6_4_coverage_adjusted_denominator"] == 300
    gate = report["retrieval_quality_gate"]
    assert gate["coverage_adjusted_denominator"] == 300
    assert gate["metric_denominator_separate_from_v6_4_coverage_denominator"] is True
    assert report["official_denominator_mutation"] is False
    assert report["source_v6_5_bridge_check"]["bridgeable_rows"] == 0


def test_v68_engineering_diagnostics_do_not_score_quality(report: dict[str, object]) -> None:
    diagnostics = report["retrieval_engineering_diagnostics"]
    assert diagnostics["diagnostic_only"] is True
    assert diagnostics["availability_counters_are_quality_metrics"] is False
    assert diagnostics["backend_latency_counters_are_quality_metrics"] is False
    assert diagnostics["fail_closed_reason_counters_are_quality_metrics"] is False
    assert set(diagnostics["by_backend"]) == {"vector", "bm25", "hybrid"}
    assert diagnostics["by_family"]["PDF"]["gold29_rows"] == 4
    assert diagnostics["by_family"]["TEXT"]["gold29_rows"] == 6
    assert diagnostics["by_family"]["XLSX"]["gold29_rows"] == 19
    for backend, counters in diagnostics["by_backend"].items():
        assert counters["attempted_rows"] == 300, backend
        assert counters["computed_only_denominator"] == 0, backend
        assert counters["retrieval_quality_metric_computed"] is False
        assert counters["tool_outputs_counted_as_rag_hit"] is False


def test_v68_boundaries_and_protected_surfaces_stay_closed(report: dict[str, object]) -> None:
    for field in REQUIRED_FALSE_FIELDS:
        assert report[field] is False, field
    assert report["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows_created"] == 0
    assert report["official_metric_input_rows_consumed"] == 0
    guard = report["candidate_generation_input_policy"]
    assert guard["expected_supporting_gold_qrels_used_for_candidate_generation"] is False
    assert guard["target_ids_used_for_candidate_generation"] is False
    assert guard["prior_route_diagnostics_used_for_candidate_generation"] is False
    assert guard["candidate_generation_allowed_input_surface"] == ["query_text", "allowed_corpus_index_source_surfaces"]
    protected = report["protected_surface_check"]
    assert protected["passed"] is True
    assert protected["mutated_paths"] == []
    assert protected["protected_namespaces_touched"] == []


def test_v68_single_primary_report_status_docs_and_hash_contract(
    tmp_path: Path,
    v68_module,
    report: dict[str, object],
) -> None:
    written, hashes = v68_module.write_report_bundle(tmp_path, report)
    v68_module.check_report(written, root=tmp_path)
    v68_module.update_docs(tmp_path, written)
    v68_module.append_status(tmp_path, written, artifact_hashes=hashes)
    v68_module.require_status_report_hash(tmp_path, written)

    run_root = tmp_path / "reports/rag_eval/rag-ingestion/runs" / RUN_KEY
    assert (run_root / "report.json").exists()
    assert set(path.name for path in run_root.iterdir()) == {"report.json"}
    assert written["artifact_sha256"]["report_json_sha256"] == hashlib.sha256(
        (run_root / "report.json").read_bytes()
    ).hexdigest()
    status_rows = [
        json.loads(line)
        for line in (tmp_path / "reports/rag_eval/rag-ingestion/status.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert status_rows[-1]["logical_run_key"] == RUN_KEY
    assert status_rows[-1]["current_resolves_to"] == RUN_KEY
    assert status_rows[-1]["rollback_key"] == ROLLBACK_KEY
    assert status_rows[-1]["retrieval_quality_metric_computed"] is False
    assert status_rows[-1]["computed_only_denominator"] == 0
    assert status_rows[-1]["official_metric"] is False

    for doc_name in ("rag-ingestion-progress.md", "rag-ingestion-measurements.md", "rag-ingestion-triage.md"):
        text = (tmp_path / "docs" / doc_name).read_text(encoding="utf-8")
        assert RUN_KEY in text
        assert "computed_only_denominator=0" in text
        assert "no official/product/promotion/live-readiness claim" in text.lower()


def test_protected_namespace_git_status_is_clean_for_v68() -> None:
    result = subprocess.run(
        ["git", "status", "--short", "--", *PROTECTED_PATHS],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.strip() == ""


@pytest.mark.parametrize(
    ("patch", "message"),
    (
        ({"current_resolves_to": ROLLBACK_KEY}, "current"),
        ({"retrieval_quality_metric_computed": True}, "retrieval quality"),
        ({"official_denominator_mutation": True}, "official denominator"),
        ({"retrieval_quality_gate": {"safe_read_only_denominator_available": True}}, "safe denominator"),
        (
            {
                "candidate_generation_input_policy": {
                    "expected_supporting_gold_qrels_used_for_candidate_generation": True
                }
            },
            "candidate generation",
        ),
    ),
)
def test_check_report_rejects_boundary_drift(
    report: dict[str, object],
    v68_module,
    patch: dict[str, object],
    message: str,
) -> None:
    poisoned = json.loads(json.dumps(report))
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(poisoned.get(key), dict):
            poisoned[key] = dict(poisoned[key], **value)
        else:
            poisoned[key] = value

    with pytest.raises(ValueError, match=message):
        v68_module.check_report(poisoned)
