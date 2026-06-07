from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v7_0_e2e_eval_architecture_closeout_nonprod"
V6_4_RUN_KEY = "v6_4_e2e_coverage_and_failure_taxonomy_nonprod"
V6_5_RUN_KEY = "v6_5_retrieval_metric_unlock_packet_nonprod"
V6_5_1_RUN_KEY = "v6_5_1_gold29_actual_response_smoke_nonprod"
V6_6_RUN_KEY = "v6_6_structured_tool_operation_taxonomy_nonprod"
V6_7_RUN_KEY = "v6_7_agentic_retry_fail_closed_policy_nonprod"
V6_8_RUN_KEY = "v6_8_metric_gated_retrieval_quality_engineering_nonprod"
V6_9_RUN_KEY = "v6_9_answer_quality_gate_packet_nonprod"
ROLLBACK_KEY = "v6_3_e2e_bge_m3_faiss_agentic_rag_smoke_single_report"
STATUS = "V7_0_E2E_EVAL_ARCHITECTURE_CLOSEOUT_NONPROD_READY"
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
def v70_module():
    from ai.eval import rag_v70_e2e_eval_architecture_closeout_nonprod as v70

    return v70


@pytest.fixture()
def source_v63_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, object]:
    from ai.eval import rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report as v63

    monkeypatch.setattr(v63, "SentenceTransformerEmbedder", StubBgeM3Embedder)
    built = v63.build_report(
        root=ROOT,
        generated_at="2026-06-06T00:00:00Z",
        run_artifact_root=tmp_path / "v6_3_run",
    )
    v63.check_report(built)
    return built


@pytest.fixture()
def report(v70_module, source_v63_report: dict[str, object]) -> dict[str, object]:
    built = v70_module.build_report(
        root=ROOT,
        generated_at="2026-06-07T00:00:00Z",
        source_report=source_v63_report,
    )
    v70_module.check_report(built)
    return built


def test_v70_registers_explicitly_and_v64_recovery_is_current(
    report: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_eval_registry as registry
    from ai.eval import rag_v63_e2e_bge_m3_faiss_agentic_rag_smoke_single_report as v63

    monkeypatch.setattr(v63, "SentenceTransformerEmbedder", StubBgeM3Embedder)

    assert registry.resolve_run(RUN_KEY, root=ROOT).logical_key == RUN_KEY
    assert registry.resolve_run("current", root=ROOT).logical_key == V6_9_RUN_KEY
    assert runner.DEFAULT_RUN_KEY == V6_9_RUN_KEY

    checked = runner.check_run(RUN_KEY)
    assert checked["logical_run_key"] == RUN_KEY
    assert checked["status"] == STATUS
    assert runner.check_run("current")["logical_run_key"] == V6_9_RUN_KEY
    assert runner.check_run(ROLLBACK_KEY)["logical_run_key"] == ROLLBACK_KEY

    assert report["current_resolves_to"] == V6_9_RUN_KEY
    assert report["current_alias_policy"]["current_moved_from"] == RUN_KEY
    assert report["current_alias_policy"]["current_moved_to"] == V6_9_RUN_KEY
    assert report["current_alias_policy"]["historical_marker_current_moved_from"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["historical_marker_current_moved_to"] == RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY


def test_source_v63_e2e_architecture_is_hash_locked_and_closed(report: dict[str, object]) -> None:
    source = report["source_report_lock"]
    architecture = report["architecture_closeout_summary"]
    checkpoints = report["checkpoint_results"]

    assert source["source_run_key"] == ROLLBACK_KEY
    assert source["source_status"] == "V6_3_E2E_BGE_M3_FAISS_AGENTIC_RAG_SMOKE_SINGLE_REPORT_NONPROD_READY"
    assert source["source_report_payload_sha256"]
    assert source["source_artifact_report_sha256"]
    assert source["source_current_resolves_to"] == ROLLBACK_KEY
    assert source["source_rollback_key"] == "v6_2_source_derived_materialization_scaleout_and_denominator_reality_check"

    assert architecture["source_e2e_contract_verified"] is True
    assert architecture["source_bge_m3_faiss_verified"] is True
    assert architecture["source_citation_verification_passed"] is True
    assert architecture["metric_lanes_separate"] is True
    assert architecture["single_report_policy_preserved"] is True
    assert architecture["codex_owned_architecture_checkpoints_closed"] is False
    assert architecture["premature_closeout_marker_only"] is True
    assert architecture["v7_completion_claim"] is False
    assert architecture["required_predecessor_checkpoints_exist_or_skipped"] is True
    assert architecture["missing_required_predecessor_checkpoints"] == []
    assert architecture["quality_or_promotion_gate_opened"] is False
    assert architecture["remaining_human_owned_decision_gates"] == [
        "gold",
        "qrels",
        "expected_evidence",
        "relevance",
        "answerability",
        "official_denominator",
        "promotion",
    ]

    assert {row["checkpoint_id"] for row in checkpoints} == {
        "plan_recovery",
        "source_v6_3_evidence_lock",
        "metric_boundary_closeout",
        "rollback_current_contract",
        "protected_surface_audit",
        "human_owned_gate_boundary",
    }
    assert all(row["status"] == "passed" for row in checkpoints)
    predecessor_rows = report["predecessor_checkpoint_audit"]
    assert {row["checkpoint_key"] for row in predecessor_rows} == {
        V6_4_RUN_KEY,
        "v6_5_retrieval_metric_unlock_packet_nonprod",
        "v6_6_structured_tool_operation_taxonomy_nonprod",
        "v6_7_agentic_retry_fail_closed_policy_nonprod",
        "v6_8_metric_gated_retrieval_quality_engineering_nonprod",
        "v6_9_answer_quality_gate_packet_nonprod",
    }
    assert all(row["status"] == "present" for row in predecessor_rows)


def test_build_report_fails_closed_when_v63_rollback_artifact_is_missing(
    tmp_path: Path,
    v70_module,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_load_report(*args: object, **kwargs: object) -> dict[str, object]:
        raise FileNotFoundError("source report intentionally absent")

    monkeypatch.setattr(v70_module.registry, "load_report", fake_load_report)

    with pytest.raises(FileNotFoundError, match="source report intentionally absent"):
        v70_module.build_report(root=tmp_path, generated_at="2026-06-07T00:00:00Z")


def test_report_bundle_writes_single_report_status_docs_and_plan(
    tmp_path: Path,
    v70_module,
    source_v63_report: dict[str, object],
) -> None:
    built = v70_module.build_report(
        root=tmp_path,
        generated_at="2026-06-07T00:00:00Z",
        source_report=source_v63_report,
    )
    written, hashes = v70_module.write_report_bundle(tmp_path, built)
    v70_module.check_report(written, root=tmp_path)
    v70_module.update_docs(tmp_path, written)
    v70_module.append_status(tmp_path, written, artifact_hashes=hashes)
    v70_module.require_status_report_hash(tmp_path, written)

    run_root = tmp_path / "ai/eval/reports/rag-ingestion/runs" / RUN_KEY
    assert (run_root / "report.json").exists()
    assert set(path.name for path in run_root.iterdir()) == {"report.json"}
    assert written["consolidated_report_policy"]["primary_report_only"] is True
    assert "codex_goal_plan_md" not in written["artifact_paths"]
    assert written["artifact_sha256"]["report_json_sha256"] == hashlib.sha256(
        (run_root / "report.json").read_bytes()
    ).hexdigest()

    status_rows = [
        json.loads(line)
        for line in (tmp_path / "ai/eval/reports/rag-ingestion/status.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert status_rows[-1]["current_resolves_to"] == V6_9_RUN_KEY
    assert status_rows[-1]["current_moved_from"] == RUN_KEY
    assert status_rows[-1]["current_moved_to"] == V6_9_RUN_KEY
    assert status_rows[-1]["rollback_key"] == ROLLBACK_KEY
    assert status_rows[-1]["artifact_sha256"]["report_json_sha256"] == written["artifact_sha256"]["report_json_sha256"]

    plan_text = (tmp_path / "docs/codex-goals/rag-v7-e2e-evaluation-plan.md").read_text(encoding="utf-8")
    assert "v7_0_e2e_eval_architecture_closeout_nonprod" in plan_text
    assert "checkpoint by checkpoint" in plan_text
    assert "No gold, qrels, expected evidence" in plan_text

    for doc_name in ("rag-ingestion-progress.md", "rag-ingestion-measurements.md", "rag-ingestion-triage.md"):
        text = (tmp_path / "docs" / doc_name).read_text(encoding="utf-8")
        assert RUN_KEY in text
        assert f"current resolves to `{V6_9_RUN_KEY}`" in text or f"`{V6_9_RUN_KEY}` supersedes it as current" in text
        assert f"`{ROLLBACK_KEY}` to `{RUN_KEY}`" in text
        assert f"rollback key is `{ROLLBACK_KEY}`" in text
        assert "diagnostic-only" in text
        assert "no official/product/promotion/live-readiness claim" in text.lower()


def test_required_fields_and_protected_surfaces_stay_closed(report: dict[str, object]) -> None:
    assert report["run_id"] == RUN_KEY
    assert report["canonical_long_run_id"] == RUN_KEY
    assert report["schema_version"].endswith("_report_v1")
    assert report["diagnostic_only"] is True
    assert report["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows_created"] == 0
    assert report["official_metric_input_rows_consumed"] == 0
    assert report["answer_quality_metric_computed"] is False
    assert report["retrieval_quality_metric_computed"] is False
    assert report["product_success_evidence_allowed"] is False

    for field in REQUIRED_FALSE_FIELDS:
        assert report[field] is False, field

    protected = report["protected_surface_check"]
    assert protected["passed"] is True
    assert protected["mutated_paths"] == []
    assert protected["gold_qrels_expected_supporting_relevance_answerability_clean"] is True
    assert protected["official_denominator_clean"] is True
    assert protected["production_index_namespace_clean"] is True
    assert protected["protected_namespaces_touched"] == []

    decisions = report["conservative_diagnostic_only_decisions"]
    assert decisions["missing_v7_plan_file_recovered_in_place"] is True
    assert decisions["retrieval_quality_labels_remain_user_owned"] is True
    assert decisions["answer_quality_evidence_remains_user_owned"] is True
    assert decisions["denominator_policy_remains_user_owned"] is True
    assert decisions["v7_0_recorded_as_premature_closeout_marker_only"] is True
    assert decisions["v7_completion_claim_from_v7_0"] is False


def test_protected_namespace_git_status_is_clean_for_v70() -> None:
    result = subprocess.run(
        ["git", "status", "--short", "--", *PROTECTED_PATHS],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.strip() == ""


@pytest.mark.parametrize(
    ("protected_patch", "message"),
    (
        ({"source_registry_clean": False}, "source_registry_clean"),
        ({"production_db_cache_clean": False}, "production_db_cache_clean"),
        ({"protected_namespaces_touched": ["prod-index"]}, "protected namespaces touched"),
    ),
)
def test_check_report_rejects_nested_protected_surface_drift(
    report: dict[str, object],
    v70_module,
    protected_patch: dict[str, object],
    message: str,
) -> None:
    poisoned = json.loads(json.dumps(report))
    poisoned["protected_surface_check"] = dict(poisoned["protected_surface_check"], **protected_patch)

    with pytest.raises(ValueError, match=message):
        v70_module.check_report(poisoned)


def test_check_report_rejects_closeout_claim_when_human_owned_gates_remain(
    report: dict[str, object],
    v70_module,
) -> None:
    poisoned = json.loads(json.dumps(report))
    poisoned["architecture_closeout_summary"]["codex_owned_architecture_checkpoints_closed"] = True

    with pytest.raises(ValueError, match="human-owned decision gates"):
        v70_module.check_report(poisoned)


def test_check_report_rejects_closeout_claim_when_predecessor_audit_is_poisoned(
    report: dict[str, object],
    v70_module,
) -> None:
    poisoned = json.loads(json.dumps(report))
    poisoned["architecture_closeout_summary"]["codex_owned_architecture_checkpoints_closed"] = True
    poisoned["predecessor_checkpoint_audit"][0]["status"] = "missing"

    with pytest.raises(ValueError, match="required predecessor checkpoints"):
        v70_module.check_report(poisoned)
