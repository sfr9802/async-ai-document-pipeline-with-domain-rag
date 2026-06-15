from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v7_0_1_premature_closeout_audit_and_v6_4_recovery_nonprod"
V6_4_RUN_KEY = "v6_4_e2e_coverage_and_failure_taxonomy_nonprod"
V6_5_RUN_KEY = "v6_5_retrieval_metric_unlock_packet_nonprod"
V6_5_1_RUN_KEY = "v6_5_1_gold29_actual_response_smoke_nonprod"
V6_6_RUN_KEY = "v6_6_structured_tool_operation_taxonomy_nonprod"
V6_7_RUN_KEY = "v6_7_agentic_retry_fail_closed_policy_nonprod"
V6_8_RUN_KEY = "v6_8_metric_gated_retrieval_quality_engineering_nonprod"
V6_9_RUN_KEY = "v6_9_answer_quality_gate_packet_nonprod"
V7_0_RUN_KEY = "v7_0_e2e_eval_architecture_closeout_nonprod"
ROLLBACK_KEY = "v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report"
STATUS = "V7_0_1_PREMATURE_CLOSEOUT_AUDIT_AND_V6_4_RECOVERY_NONPROD_READY"
EXPECTED_PREDECESSORS = {
    V6_4_RUN_KEY,
    "v6_5_retrieval_metric_unlock_packet_nonprod",
    "v6_6_structured_tool_operation_taxonomy_nonprod",
    "v6_7_agentic_retry_fail_closed_policy_nonprod",
    "v6_8_metric_gated_retrieval_quality_engineering_nonprod",
    "v6_9_answer_quality_gate_packet_nonprod",
}
PROTECTED_PATHS = (
    "ai/eval/eval_queries",
    "ai/eval/source_registry",
    "ai/eval/indexes",
    "ai/eval/silver",
)

REQUIRED_FALSE_FIELDS = {
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


def assert_no_exact_keys(value: object, forbidden_keys: set[str]) -> None:
    if isinstance(value, dict):
        assert not (set(value) & forbidden_keys)
        for child in value.values():
            assert_no_exact_keys(child, forbidden_keys)
    elif isinstance(value, list):
        for child in value:
            assert_no_exact_keys(child, forbidden_keys)


class StubBgeM3Embedder:
    instances: list["StubBgeM3Embedder"] = []

    def __init__(self, model_name: str, **kwargs: object) -> None:
        self.model_name = model_name
        self.max_seq_length = kwargs.get("max_seq_length")
        self._dimension = 16
        StubBgeM3Embedder.instances.append(self)

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._vector(text) for text in texts]).astype(np.float32)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._vector(text) for text in texts]).astype(np.float32)

    def _vector(self, text: str) -> np.ndarray:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = np.array([(digest[i] + 1) / 256.0 for i in range(self._dimension)], dtype=np.float32)
        return values / float(np.linalg.norm(values))


@pytest.fixture(autouse=True)
def _reset_stub() -> None:
    StubBgeM3Embedder.instances.clear()


@pytest.fixture(scope="module")
def v701_module():
    from ai.eval import rag_v701_premature_closeout_audit_and_v64_recovery_nonprod as v701

    return v701


@pytest.fixture()
def v64_report(v701_module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, object]:
    monkeypatch.setattr(v701_module.v64.v63, "SentenceTransformerEmbedder", StubBgeM3Embedder)
    built = v701_module.v64.build_report(
        root=ROOT,
        generated_at="2026-06-07T00:10:00Z",
        run_artifact_root=tmp_path / "v6_4_runtime",
    )
    v701_module.v64.check_report(built)
    return built


@pytest.fixture()
def v70_report(v701_module, v64_report: dict[str, object]) -> dict[str, object]:
    v70 = v701_module.v70
    source_report = v64_report["source_v6_3_report_snapshot"]
    built = v70.build_report(
        root=ROOT,
        generated_at="2026-06-07T00:00:00Z",
        source_report=source_report,
    )
    v70.check_report(built)
    return built


@pytest.fixture()
def report(
    v701_module,
    v64_report: dict[str, object],
    v70_report: dict[str, object],
) -> dict[str, object]:
    built = v701_module.build_report(
        root=ROOT,
        generated_at="2026-06-07T00:20:00Z",
        v7_0_report=v70_report,
        v6_4_report=v64_report,
    )
    v701_module.check_report(built)
    return built


def test_v701_registers_explicitly_and_preserves_live_current_v69(report: dict[str, object]) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_eval_registry as registry

    assert registry.resolve_run(RUN_KEY, root=ROOT).logical_key == RUN_KEY
    assert registry.resolve_run(V6_4_RUN_KEY, root=ROOT).logical_key == V6_4_RUN_KEY
    assert registry.resolve_run("current", root=ROOT).logical_key == V6_9_RUN_KEY
    assert runner.DEFAULT_RUN_KEY == V6_9_RUN_KEY
    assert runner.check_run(RUN_KEY)["logical_run_key"] == RUN_KEY
    assert runner.check_run(V6_4_RUN_KEY)["logical_run_key"] == V6_4_RUN_KEY
    assert runner.check_run("current")["logical_run_key"] == V6_9_RUN_KEY
    assert runner.check_run(ROLLBACK_KEY)["logical_run_key"] == ROLLBACK_KEY

    assert report["status"] == STATUS
    assert report["current_resolves_to"] == V6_9_RUN_KEY
    assert report["audit_run_does_not_move_current"] is True
    assert report["current_alias_policy"]["current_moved_from"] == ""
    assert report["current_alias_policy"]["current_moved_to"] == ""
    assert report["current_alias_policy"]["historical_recovery_current_moved_from"] == V7_0_RUN_KEY
    assert report["current_alias_policy"]["historical_recovery_current_moved_to"] == V6_4_RUN_KEY
    assert report["current_alias_policy"]["live_current_resolves_to"] == V6_9_RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY


def test_v701_records_v70_as_premature_closeout_marker_only(report: dict[str, object]) -> None:
    audit = report["v7_0_premature_closeout_audit"]
    summary = audit["summary"]
    predecessor_audit = audit["predecessor_checkpoint_audit"]
    by_key = {row["checkpoint_key"]: row for row in predecessor_audit}

    assert summary["v7_0_report_preserved"] is True
    assert summary["v7_0_deleted"] is False
    assert summary["v7_0_completion_claim_allowed"] is False
    assert summary["v7_0_recorded_as_premature_closeout_marker_only"] is True
    assert summary["v7_completion_claim_from_v7_0"] is False
    assert summary["predecessor_required_count"] == 6
    assert summary["predecessor_present_count"] == 6
    assert summary["predecessor_missing_count"] == 0
    assert summary["all_required_predecessors_satisfied_or_skipped"] is True

    assert set(by_key) == EXPECTED_PREDECESSORS
    assert by_key[V6_4_RUN_KEY]["artifact_status"] == "present"
    assert by_key[V6_4_RUN_KEY]["status"] == "present"
    assert by_key[V6_5_RUN_KEY]["artifact_status"] == "present"
    assert by_key[V6_5_RUN_KEY]["status"] == "present"
    assert by_key[V6_6_RUN_KEY]["artifact_status"] == "present"
    assert by_key[V6_6_RUN_KEY]["status"] == "present"
    assert by_key[V6_7_RUN_KEY]["artifact_status"] == "present"
    assert by_key[V6_7_RUN_KEY]["status"] == "present"
    assert by_key[V6_8_RUN_KEY]["artifact_status"] == "present"
    assert by_key[V6_8_RUN_KEY]["status"] == "present"
    assert by_key[V6_9_RUN_KEY]["artifact_status"] == "present"
    assert by_key[V6_9_RUN_KEY]["status"] == "present"


def test_predecessor_closeout_guard_rejects_missing_without_skip_reason(
    v701_module,
    v70_report: dict[str, object],
    v64_report: dict[str, object],
) -> None:
    audit = v701_module.audit_predecessor_checkpoints(root=ROOT, v6_4_report=v64_report)
    assert audit["all_required_predecessors_satisfied_or_skipped"] is True

    poisoned_v70 = json.loads(json.dumps(v70_report))
    poisoned_v70["architecture_closeout_summary"]["codex_owned_architecture_checkpoints_closed"] = True

    with pytest.raises(ValueError, match="human-owned decision gates"):
        v701_module.validate_v7_closeout_predecessor_guard(poisoned_v70, predecessor_audit=audit)


def test_v701_links_v64_recovery_and_preserves_diagnostic_boundaries(report: dict[str, object]) -> None:
    recovery = report["v6_4_recovery_summary"]

    assert recovery["run_key"] == V6_4_RUN_KEY
    assert recovery["status"] == "V6_4_E2E_COVERAGE_AND_FAILURE_TAXONOMY_NONPROD_READY"
    assert recovery["candidate_coverage_attempted_rows"] == 300
    assert recovery["family_breakdown"] == {"PDF": 100, "TEXT": 100, "XLSX": 100}
    assert recovery["bounded_e2e_expanded_rows"] == 30
    assert recovery["answer_quality_metric_computed"] is False
    assert recovery["computed_only_denominator"] == 0
    assert recovery["coverage_adjusted_denominator"] == 300
    assert recovery["label_unavailable_exclusion_reason"] == "no_authorized_after_fact_label_available"
    assert recovery["current_move_allowed_after_v6_4_checks"] is True

    assert report["answer_quality_metric_computed"] is False
    assert report["retrieval_quality_metric_computed"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows_created"] == 0
    assert report["official_metric_input_rows_consumed"] == 0
    for field in REQUIRED_FALSE_FIELDS:
        assert report[field] is False, field

    protected = report["protected_surface_check"]
    assert protected["passed"] is True
    assert protected["mutated_paths"] == []
    assert protected["protected_namespaces_touched"] == []
    assert protected["official_denominator_clean"] is True
    assert protected["source_registry_clean"] is True
    assert protected["production_index_namespace_clean"] is True


def test_report_bundle_writes_one_primary_report_status_docs_and_plan(
    tmp_path: Path,
    v701_module,
    v64_report: dict[str, object],
    v70_report: dict[str, object],
) -> None:
    built = v701_module.build_report(
        root=tmp_path,
        generated_at="2026-06-07T00:20:00Z",
        v7_0_report=v70_report,
        v6_4_report=v64_report,
    )
    written, hashes = v701_module.write_report_bundle(tmp_path, built)
    v701_module.check_report(written, root=tmp_path)
    v701_module.update_docs(tmp_path, written)
    v701_module.append_status(tmp_path, written, artifact_hashes=hashes)
    v701_module.require_status_report_hash(tmp_path, written)

    run_root = tmp_path / "reports/rag_eval/rag-ingestion/runs" / RUN_KEY
    assert (run_root / "report.json").exists()
    assert set(path.name for path in run_root.iterdir()) == {"report.json"}
    assert written["consolidated_report_policy"]["primary_report_only"] is True
    assert written["artifact_sha256"]["report_json_sha256"] == hashlib.sha256(
        (run_root / "report.json").read_bytes()
    ).hexdigest()

    status_rows = [
        json.loads(line)
        for line in (tmp_path / "reports/rag_eval/rag-ingestion/status.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert status_rows[-1]["logical_run_key"] == RUN_KEY
    assert status_rows[-1]["current_resolves_to"] == V6_9_RUN_KEY
    assert status_rows[-1]["current_moved_to"] == ""
    assert status_rows[-1]["historical_recovery_current_moved_to"] == V6_4_RUN_KEY
    assert status_rows[-1]["artifact_sha256"]["report_json_sha256"] == written["artifact_sha256"]["report_json_sha256"]

    plan_text = (tmp_path / "docs/codex-goals/rag-v7-e2e-evaluation-plan.md").read_text(encoding="utf-8")
    assert "v7_0 is preserved as diagnostic audit evidence only" in plan_text
    assert V6_4_RUN_KEY in plan_text
    assert "v6_5_retrieval_metric_unlock_packet_nonprod" in plan_text
    assert "v6_9_answer_quality_gate_packet_nonprod" in plan_text
    assert "Do not claim v7 completion from v7_0" in plan_text

    for doc_name in ("rag-ingestion-progress.md", "rag-ingestion-measurements.md", "rag-ingestion-triage.md"):
        text = (tmp_path / "docs" / doc_name).read_text(encoding="utf-8")
        assert RUN_KEY in text
        assert "premature closeout marker" in text
        assert f"live current resolves to `{V6_9_RUN_KEY}`" in text
        assert f"Historical recovery movement from `{V7_0_RUN_KEY}` to `{V6_4_RUN_KEY}`" in text
        assert "no official/product/promotion/live-readiness claim" in text.lower()


def test_no_raw_prompt_response_or_tool_to_rag_leakage(report: dict[str, object]) -> None:
    assert_no_exact_keys(
        report,
        {
            "raw_prompt_payload",
            "raw_response_payload",
            "raw_llm_response",
            "formula_text",
            "formula_evaluation",
            "direct_normalized_answer_value",
            "expected_answer",
            "supporting_evidence",
            "qrels_positive_ids",
        },
    )

    leakage = report["tool_to_rag_leakage_guard"]
    assert leakage["tool_outputs_counted_as_rag_hit"] is False
    assert leakage["tool_success_contributed_to_hit_at_k"] is False
    assert leakage["tool_success_contributed_to_mrr"] is False
    assert leakage["tool_success_contributed_to_ndcg"] is False
    assert leakage["tool_lane_created_retrieval_hit"] is False


def test_protected_namespace_git_status_is_clean_for_v701() -> None:
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
        ({"current_resolves_to": V7_0_RUN_KEY}, "current"),
        ({"v7_0_premature_closeout_audit": {"summary": {"v7_0_completion_claim_allowed": True}}}, "v7_0 completion"),
        ({"official_metric_input_rows": 1}, "official metric"),
        ({"protected_surface_check": {"protected_namespaces_touched": ["prod"]}}, "protected"),
    ),
)
def test_check_report_rejects_audit_boundary_drift(
    report: dict[str, object],
    v701_module,
    patch: dict[str, object],
    message: str,
) -> None:
    poisoned = json.loads(json.dumps(report))
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(poisoned.get(key), dict):
            nested = dict(poisoned[key])
            for inner_key, inner_value in value.items():
                if isinstance(inner_value, dict) and isinstance(nested.get(inner_key), dict):
                    nested[inner_key] = dict(nested[inner_key], **inner_value)
                else:
                    nested[inner_key] = inner_value
            poisoned[key] = nested
        else:
            poisoned[key] = value

    with pytest.raises(ValueError, match=message):
        v701_module.check_report(poisoned)
