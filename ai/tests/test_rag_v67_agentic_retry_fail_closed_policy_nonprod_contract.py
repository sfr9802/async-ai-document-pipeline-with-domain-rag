from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v6_7_agentic_retry_fail_closed_policy_nonprod"
ROLLBACK_KEY = "v6_6_structured_tool_operation_taxonomy_nonprod"
STATUS = "V6_7_AGENTIC_RETRY_FAIL_CLOSED_POLICY_NONPROD_READY"
LATEST_CURRENT_RUN_KEY = "v6_9_answer_quality_gate_packet_nonprod"
PROTECTED_PATHS = (
    "ai/eval/eval_queries",
    "ai/eval/source_registry",
    "ai/eval/indexes",
    "ai/eval/silver",
)
REQUIRED_FALSE_FIELDS = {
    "official_metric",
    "agentic_loop_metric_computed",
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
def v67_module():
    from ai.eval import rag_v67_agentic_retry_fail_closed_policy_nonprod as v67

    return v67


@pytest.fixture()
def report(v67_module) -> dict[str, object]:
    built = v67_module.build_report(root=ROOT, generated_at="2026-06-07T04:00:00Z")
    v67_module.check_report(built)
    return built


def test_v67_schema_current_and_rollback(report: dict[str, object]) -> None:
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
    assert report["schema_version"] == "v6_7_agentic_retry_fail_closed_policy_nonprod_report_v1"
    assert report["status"] == STATUS
    assert report["rollback_key"] == ROLLBACK_KEY
    assert report["current_resolves_to"] == RUN_KEY
    assert report["current_alias_policy"]["current_moved_from"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["current_moved_to"] == RUN_KEY


def test_v67_agentic_policy_separates_choices_from_quality(report: dict[str, object]) -> None:
    assert report["run_id"] == RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY
    assert report["agentic_loop_metric_computed"] is False
    assert report["answer_quality_metric_computed"] is False
    assert report["product_success_evidence_allowed"] is False
    assert report["raw_prompt_payload_written"] is False
    assert report["raw_response_payload_written"] is False
    assert report["source_v6_6_report_check"]["tool_operation_rows"] == 29


def test_v67_retry_policy_is_fail_closed(report: dict[str, object]) -> None:
    policy = report["agentic_retry_policy"]
    assert policy["max_retry_count"] >= 0
    assert policy["retry_requires_new_allowed_signal"] is True
    assert policy["retry_may_use_expected_or_qrels"] is False
    assert policy["fail_closed_on_verification_failure"] is True
    assert policy["selection_may_use_expected_or_qrels"] is False
    for row in report["agentic_loop_rows"]:
        assert row["selected_path"] in {"rag_only", "tool_only", "rag_then_tool", "tool_then_rag", "none_fail_closed"}
        assert row["verification_state"] in {"passed", "failed", "skipped_no_answer", "not_applicable"}
        assert row["expected_supporting_qrels_used_in_loop"] is False
        assert row["raw_prompt_payload_written"] is False
        assert row["raw_response_payload_written"] is False


def test_v67_agentic_rows_never_drop_and_remain_compact(report: dict[str, object]) -> None:
    rows = report["agentic_loop_rows"]
    summary = report["agentic_loop_summary"]

    assert len(rows) == 29
    assert summary["agentic_loop_rows"] == 29
    assert summary["silently_dropped_rows"] == 0
    assert summary["retry_attempted_rows"] == 0
    assert summary["expected_supporting_qrels_used_in_loop_count"] == 0
    assert summary["final_answer_rendered_rows"] == 10
    assert summary["final_citation_verified_rows"] == 10
    assert summary["fail_closed_rows"] == 19
    assert sum(1 for row in rows if row["final_answer_rendered"]) == summary["final_answer_rendered_rows"]
    assert sum(1 for row in rows if row["final_citation_verified"]) == summary["final_citation_verified_rows"]
    for row in rows:
        assert row["gold_row_hash"]
        assert row["query_hash"]
        assert row["source_family"] in {"PDF", "TEXT", "XLSX"}
        assert isinstance(row["rag_attempted"], bool)
        assert row["tool_attempted"] is False
        assert row["retry_count"] == 0


def test_v67_boundaries_and_protected_surfaces_stay_closed(report: dict[str, object]) -> None:
    for field in REQUIRED_FALSE_FIELDS:
        assert report[field] is False, field
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows_created"] == 0
    assert report["official_metric_input_rows_consumed"] == 0
    assert report["candidate_generation_input_policy"]["expected_supporting_qrels_used_for_selection_or_retry"] is False
    assert report["candidate_generation_input_policy"]["tool_outputs_used_for_true_rag_metric"] is False
    guard = report["tool_to_rag_leakage_guard"]
    assert guard["tool_success_contributed_to_hit_at_k"] is False
    assert guard["tool_success_contributed_to_mrr"] is False
    assert guard["tool_success_contributed_to_ndcg"] is False
    protected = report["protected_surface_check"]
    assert protected["passed"] is True
    assert protected["mutated_paths"] == []
    assert protected["protected_namespaces_touched"] == []


def test_v67_single_primary_report_status_docs_and_hash_contract(
    tmp_path: Path,
    v67_module,
    report: dict[str, object],
) -> None:
    written, hashes = v67_module.write_report_bundle(tmp_path, report)
    v67_module.check_report(written, root=tmp_path)
    v67_module.update_docs(tmp_path, written)
    v67_module.append_status(tmp_path, written, artifact_hashes=hashes)
    v67_module.require_status_report_hash(tmp_path, written)

    run_root = tmp_path / "ai/eval/reports/rag-ingestion/runs" / RUN_KEY
    assert (run_root / "report.json").exists()
    assert set(path.name for path in run_root.iterdir()) == {"report.json"}
    assert written["artifact_sha256"]["report_json_sha256"] == hashlib.sha256(
        (run_root / "report.json").read_bytes()
    ).hexdigest()
    status_rows = [
        json.loads(line)
        for line in (tmp_path / "ai/eval/reports/rag-ingestion/status.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert status_rows[-1]["logical_run_key"] == RUN_KEY
    assert status_rows[-1]["current_resolves_to"] == RUN_KEY
    assert status_rows[-1]["rollback_key"] == ROLLBACK_KEY
    assert status_rows[-1]["agentic_loop_metric_computed"] is False
    assert status_rows[-1]["answer_quality_metric_computed"] is False

    for doc_name in ("rag-ingestion-progress.md", "rag-ingestion-measurements.md", "rag-ingestion-triage.md"):
        text = (tmp_path / "docs" / doc_name).read_text(encoding="utf-8")
        assert RUN_KEY in text
        assert "retry" in text
        assert "no official/product/promotion/live-readiness claim" in text.lower()


def test_protected_namespace_git_status_is_clean_for_v67() -> None:
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
        ({"agentic_loop_summary": {"silently_dropped_rows": 1}}, "dropped"),
        ({"agentic_loop_metric_computed": True}, "agentic loop"),
        ({"agentic_retry_policy": {"retry_may_use_expected_or_qrels": True}}, "retry"),
        ({"candidate_generation_input_policy": {"expected_supporting_qrels_used_for_selection_or_retry": True}}, "selection"),
    ),
)
def test_check_report_rejects_boundary_drift(
    report: dict[str, object],
    v67_module,
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
        v67_module.check_report(poisoned)
