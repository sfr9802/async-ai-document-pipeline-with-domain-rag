from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v6_5_retrieval_metric_unlock_packet_nonprod"
V6_5_1_RUN_KEY = "v6_5_1_gold29_actual_response_smoke_nonprod"
V6_6_RUN_KEY = "v6_6_structured_tool_operation_taxonomy_nonprod"
V6_7_RUN_KEY = "v6_7_agentic_retry_fail_closed_policy_nonprod"
V6_8_RUN_KEY = "v6_8_metric_gated_retrieval_quality_engineering_nonprod"
V6_9_RUN_KEY = "v6_9_answer_quality_gate_packet_nonprod"
ROLLBACK_KEY = "v6_4_e2e_coverage_and_failure_taxonomy_nonprod"
V7_0_RUN_KEY = "v7_0_e2e_eval_architecture_closeout_nonprod"
V701_RUN_KEY = "v7_0_1_premature_closeout_audit_and_v6_4_recovery_nonprod"
STATUS = "V6_5_RETRIEVAL_METRIC_UNLOCK_PACKET_NONPROD_READY"
V5_5_ROOT = Path("ai/eval/reports/rag-ingestion/runs/v5_5")
V5_5_ARTIFACTS = {
    "official_metric_input": V5_5_ROOT / "official_metric_input.jsonl",
    "user_approved_gold_packet": V5_5_ROOT / "user_approved_gold_packet.jsonl",
    "user_approved_qrels": V5_5_ROOT / "user_approved_qrels.jsonl",
    "user_approved_expected_answers": V5_5_ROOT / "user_approved_expected_answers.jsonl",
    "user_approved_denominator": V5_5_ROOT / "user_approved_denominator.jsonl",
}
BRIDGE_STATES = {
    "exact_search_unit_bridge",
    "exact_source_atom_bridge",
    "locator_precision_bridge",
    "duplicate_evidence_ambiguous",
    "stale_locator_no_bridge",
    "family_mismatch_no_bridge",
    "source_identity_mismatch_no_bridge",
    "no_current_v6_4_candidate_surface",
    "unsupported_tool_only_row",
}
BRIDGEABLE_STATES = {
    "exact_search_unit_bridge",
    "exact_source_atom_bridge",
    "locator_precision_bridge",
}
PROTECTED_PATHS = (
    "ai/eval/eval_queries",
    "ai/eval/source_registry",
    "ai/eval/indexes",
    "ai/eval/silver",
)
FORBIDDEN_PAYLOAD_KEYS = {
    "raw_prompt_payload",
    "raw_response_payload",
    "raw_llm_response",
    "expected_answer_ko",
    "expected_answer",
    "expected_answer_text",
    "supporting_evidence",
    "supporting_evidence_ids",
    "qrels_positive_ids",
    "qrels_positive_candidate_ids",
    "citation_locator",
    "baseline_topk_new",
    "target_search_unit_id",
    "source_title",
    "source_workbook",
    "source_file_name",
    "workbook",
}
REQUIRED_FALSE_FIELDS = {
    "official_metric",
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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        self.passage_batches: list[list[str]] = []
        self.query_batches: list[list[str]] = []
        self._dimension = 16
        StubBgeM3Embedder.instances.append(self)

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        self.passage_batches.append(list(texts))
        return np.vstack([self._vector(text) for text in texts]).astype(np.float32)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        self.query_batches.append(list(texts))
        return np.vstack([self._vector(text) for text in texts]).astype(np.float32)

    def _vector(self, text: str) -> np.ndarray:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = np.array([(digest[i] + 1) / 256.0 for i in range(self._dimension)], dtype=np.float32)
        return values / float(np.linalg.norm(values))


@pytest.fixture(autouse=True)
def _reset_stub() -> None:
    StubBgeM3Embedder.instances.clear()


@pytest.fixture(scope="module")
def v65_module():
    from ai.eval import rag_v65_retrieval_metric_unlock_packet_nonprod as v65

    return v65


@pytest.fixture()
def report(v65_module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, object]:
    monkeypatch.setattr(v65_module.v63, "SentenceTransformerEmbedder", StubBgeM3Embedder)
    built = v65_module.build_report(
        root=ROOT,
        generated_at="2026-06-07T01:00:00Z",
        run_artifact_root=tmp_path / "v6_5_runtime",
    )
    v65_module.check_report(built)
    return built


def test_v65_report_schema_current_resolver_and_v64_rollback(report: dict[str, object]) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_eval_registry as registry

    assert registry.resolve_run(RUN_KEY, root=ROOT).logical_key == RUN_KEY
    assert registry.resolve_run("current", root=ROOT).logical_key == V6_9_RUN_KEY
    assert registry.resolve_run(ROLLBACK_KEY, root=ROOT).logical_key == ROLLBACK_KEY
    assert runner.DEFAULT_RUN_KEY == V6_9_RUN_KEY
    assert runner.check_run(RUN_KEY)["logical_run_key"] == RUN_KEY
    assert runner.check_run("current")["logical_run_key"] == V6_9_RUN_KEY
    assert runner.check_run(ROLLBACK_KEY)["logical_run_key"] == ROLLBACK_KEY

    assert report["schema_version"] == f"{RUN_KEY}_report_v1"
    assert report["run_id"] == RUN_KEY
    assert report["short_run_id"] == RUN_KEY
    assert report["logical_run_key"] == RUN_KEY
    assert report["canonical_long_run_id"] == RUN_KEY
    assert report["status"] == STATUS
    assert report["current_resolves_to"] == RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["current_moved_from"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["current_moved_to"] == RUN_KEY


def test_v65_reads_and_verifies_v64_recovery_contract_before_bridge(report: dict[str, object]) -> None:
    source = report["source_v6_4_report_check"]

    assert source["run_key"] == ROLLBACK_KEY
    assert source["status"] == "V6_4_E2E_COVERAGE_AND_FAILURE_TAXONOMY_NONPROD_READY"
    assert source["candidate_coverage_attempted_rows"] == 300
    assert source["coverage_adjusted_denominator"] == 300
    assert source["computed_only_denominator_before_bridge"] == 0
    assert source["family_breakdown"] == {"PDF": 100, "TEXT": 100, "XLSX": 100}
    assert set(source["candidate_availability_backends"]) == {"vector", "bm25", "hybrid"}
    assert source["answer_quality_metric_computed"] is False
    assert source["official_product_promotion_live_readiness_claim"] is False


def test_v65_reads_v55_approved_artifacts_immutably(report: dict[str, object]) -> None:
    source = report["v5_5_read_only_source"]

    assert source["read_only"] is True
    assert source["official_metric_dry_run_only"] is True
    assert source["approved_item_count"] == 29
    assert source["artifact_row_counts"] == {
        "official_metric_input": 29,
        "user_approved_gold_packet": 29,
        "user_approved_qrels": 29,
        "user_approved_expected_answers": 29,
        "user_approved_denominator": 29,
    }
    for name, relative_path in source["artifact_paths"].items():
        assert relative_path == V5_5_ARTIFACTS[name].as_posix()
        assert source["artifact_sha256"][name] == _sha256(ROOT / relative_path)
    assert source["raw_expected_supporting_qrels_payload_copied"] is False
    assert source["human_owned_fields_filled_by_codex"] is False


def test_bridge_states_are_exhaustive_mutually_exclusive_and_no_rows_drop(report: dict[str, object]) -> None:
    audit = report["bridge_audit"]
    rows = audit["rows"]
    state_counts = audit["state_counts"]

    assert audit["bridge_state_taxonomy"] == sorted(BRIDGE_STATES)
    assert len(rows) == 29
    assert audit["input_rows"] == 29
    assert audit["audited_rows"] == 29
    assert audit["silently_dropped_rows"] == 0
    assert sum(state_counts.values()) == 29
    assert set(state_counts) == BRIDGE_STATES

    seen = set()
    for row in rows:
        assert row["source_query_id"]
        assert row["source_family"] in {"PDF", "TEXT", "XLSX"}
        assert row["bridge_state"] in BRIDGE_STATES
        assert row["bridgeable"] is (row["bridge_state"] in BRIDGEABLE_STATES)
        assert row["bridge_state_exclusive_count"] == 1
        assert row["locator_sha256"]
        assert row["source_identity_sha256"]
        assert "candidate_preview_hashes" in row
        assert "bridge_reason" in row
        assert row["diagnostic_metric_eligible"] is False
        assert row["metric_computation_requires_explicit_user_denominator_gate"] is True
        assert row["source_query_id"] not in seen
        seen.add(row["source_query_id"])
        assert_no_exact_keys(row, FORBIDDEN_PAYLOAD_KEYS)


def test_retrieval_metrics_stay_closed_without_explicit_user_denominator_gate(report: dict[str, object]) -> None:
    audit = report["bridge_audit"]
    metric_packet = report["bridged_retrieval_metric_packet"]

    assert metric_packet["official_metric"] is False
    assert metric_packet["promotion_evidence"] is False
    assert metric_packet["product_success_evidence_allowed"] is False
    assert metric_packet["bridged_gold_read_only"] is True
    assert metric_packet["coverage_adjusted_denominator"] == 300
    assert metric_packet["coverage_adjusted_denominator_source"] == ROLLBACK_KEY
    assert metric_packet["metric_denominator_separate_from_v6_4_coverage_denominator"] is True
    assert set(metric_packet["backend_metrics"]) == {"vector", "bm25", "hybrid"}
    assert metric_packet["computed"] is False
    assert metric_packet["computed_only_denominator"] == 0
    assert metric_packet["bridged_metric_denominator"] == 0
    assert metric_packet["bridgeable_rows_preserved_for_human_review"] == audit["bridgeable_row_count"]
    assert metric_packet["not_official_denominator"] is True
    assert (
        metric_packet["not_computed_reason"]
        == "explicit_user_owned_retrieval_qrels_denominator_approval_required"
    )
    assert (
        metric_packet["metric_computation_blocked_reason"]
        == "explicit_user_owned_retrieval_qrels_denominator_approval_required"
    )
    for metric in metric_packet["backend_metrics"].values():
        assert metric["computed"] is False
        assert metric["denominator"] == 0
        assert metric["metrics"] is None


def test_metric_packet_fails_closed_even_when_bridgeable_rows_exist(v65_module) -> None:
    bridge_audit = {
        "bridgeable_row_count": 1,
        "rows": [
            {
                "bridgeable": True,
                "rank_by_backend": {"vector": 1, "bm25": 2, "hybrid": 3},
            }
        ],
    }
    packet = v65_module._metric_packet(bridge_audit, {"coverage_adjusted_denominator": 300})

    assert packet["computed"] is False
    assert packet["computed_only_denominator"] == 0
    assert packet["bridged_metric_denominator"] == 0
    assert packet["bridgeable_rows_preserved_for_human_review"] == 1
    for metric in packet["backend_metrics"].values():
        assert metric["computed"] is False
        assert metric["denominator"] == 0
        assert metric["metrics"] is None


def test_no_gold_qrels_expected_or_baseline_leakage_into_candidate_generation(report: dict[str, object]) -> None:
    policy = report["candidate_generation_input_policy"]
    probe = report["candidate_generation_leakage_probe"]

    assert policy["allowed_fields"] == ["query_text", "source_family", "top_k"]
    assert policy["forbidden_fields_present_in_candidate_request_count"] == 0
    assert policy["expected_supporting_gold_qrels_used_for_candidate_generation"] is False
    assert policy["target_ids_used_for_candidate_generation"] is False
    assert policy["row_or_case_ids_used_for_candidate_generation"] is False
    assert policy["source_title_or_file_name_shortcuts_used"] is False
    assert policy["baseline_topk_replay_used"] is False
    assert probe["passed"] is True
    assert probe["candidate_ids_changed_by_forbidden_field_poison_count"] == 0
    assert probe["probed_rows"] == 29


def test_human_review_packet_is_compact_no_decisions_and_no_raw_payloads(report: dict[str, object]) -> None:
    packet = report["human_review_packet"]

    assert packet["included_rows"] == report["bridge_audit"]["non_bridgeable_or_ambiguous_row_count"]
    assert packet["rows_are_ambiguous_or_no_bridge_only"] is True
    assert packet["human_owned_decisions_filled"] is False
    assert packet["raw_expected_answer_text_included"] is False
    assert packet["raw_supporting_evidence_text_included"] is False
    assert packet["raw_qrels_included"] is False
    for row in packet["rows"]:
        assert set(row) == {
            "source_query_id",
            "source_family",
            "bridge_state",
            "bridge_reason",
            "locator_sha256",
            "source_identity_sha256",
            "candidate_preview_hashes",
        }
    assert_no_exact_keys(packet, FORBIDDEN_PAYLOAD_KEYS)


def test_tool_outputs_answer_quality_official_and_protected_surfaces_stay_closed(report: dict[str, object]) -> None:
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["answer_quality_metric_computed"] is False
    assert report["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows_created"] == 0
    assert report["official_metric_input_rows_consumed"] == 0
    for field in REQUIRED_FALSE_FIELDS:
        assert report[field] is False, field

    guard = report["tool_to_rag_leakage_guard"]
    assert guard["tool_outputs_counted_as_rag_hit"] is False
    assert guard["tool_success_contributed_to_hit_at_k"] is False
    assert guard["tool_success_contributed_to_mrr"] is False
    assert guard["tool_success_contributed_to_ndcg"] is False

    protected = report["protected_surface_check"]
    assert protected["passed"] is True
    assert protected["mutated_paths"] == []
    assert protected["protected_namespaces_touched"] == []
    assert protected["gold_qrels_expected_supporting_relevance_answerability_clean"] is True
    assert protected["official_denominator_clean"] is True
    assert protected["production_db_cache_clean"] is True
    assert_no_exact_keys(report, FORBIDDEN_PAYLOAD_KEYS)


def test_v70_marker_and_v701_audit_identity_guards(report: dict[str, object]) -> None:
    guard = report["v7_guard"]
    identity = report["v7_0_1_audit_identity_guard"]

    assert guard["v7_0_run_key"] == V7_0_RUN_KEY
    assert guard["v7_0_recorded_as_premature_closeout_marker_only"] is True
    assert guard["v7_completion_claim_from_v7_0"] is False
    assert guard["v7_0_can_be_current_before_v6_5_to_v6_9_satisfied_or_skipped"] is False
    assert guard["missing_or_unskipped_predecessors"] == [
        "v6_6_structured_tool_operation_taxonomy_nonprod",
        "v6_7_agentic_retry_fail_closed_policy_nonprod",
        "v6_8_metric_gated_retrieval_quality_engineering_nonprod",
        "v6_9_answer_quality_gate_packet_nonprod",
    ]

    assert identity["run_key"] == V701_RUN_KEY
    assert identity["has_primary_report_path"] is True
    assert identity["has_own_run_id"] is True
    assert identity["has_own_schema_version"] is True
    assert identity["represented_only_as_different_run_id"] is False


def test_single_primary_report_status_docs_and_hash_contract(
    tmp_path: Path,
    v65_module,
    report: dict[str, object],
) -> None:
    written, hashes = v65_module.write_report_bundle(tmp_path, report)
    v65_module.check_report(written, root=tmp_path)
    v65_module.update_docs(tmp_path, written)
    v65_module.append_status(tmp_path, written, artifact_hashes=hashes)
    v65_module.require_status_report_hash(tmp_path, written)

    run_root = tmp_path / "ai/eval/reports/rag-ingestion/runs" / RUN_KEY
    assert (run_root / "report.json").exists()
    assert set(path.name for path in run_root.iterdir()) == {"report.json"}
    assert written["consolidated_report_policy"]["primary_report_only"] is True
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
    assert status_rows[-1]["artifact_sha256"]["report_json_sha256"] == written["artifact_sha256"]["report_json_sha256"]

    forbidden_sidecars = {
        "metric_results.json",
        "metric_tiers.json",
        "denominator_manifest.jsonl",
        "exclusion_ledger.jsonl",
        "structured_tool_diagnostics.jsonl",
        "true_rag_candidate_diagnostics.jsonl",
        "agentic_loop_trace.jsonl",
        "human_review_packet.jsonl",
        "bridge_audit.jsonl",
    }
    assert not (forbidden_sidecars & {path.name for path in run_root.iterdir()})

    for doc_name in ("rag-ingestion-progress.md", "rag-ingestion-measurements.md", "rag-ingestion-triage.md"):
        text = (tmp_path / "docs" / doc_name).read_text(encoding="utf-8")
        assert RUN_KEY in text
        assert "v5_5" in text
        assert "read-only bridge" in text
        assert "no official/product/promotion/live-readiness claim" in text.lower()


def test_protected_namespace_git_status_is_clean_for_v65() -> None:
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
        ({"bridged_retrieval_metric_packet": {"official_metric": True}}, "official"),
        ({"candidate_generation_input_policy": {"baseline_topk_replay_used": True}}, "baseline"),
        ({"bridge_audit": {"silently_dropped_rows": 1}}, "silently dropped"),
        ({"v7_guard": {"v7_0_recorded_as_premature_closeout_marker_only": False}}, "v7_0"),
        ({"v7_0_1_audit_identity_guard": {"represented_only_as_different_run_id": True}}, "audit identity"),
    ),
)
def test_check_report_rejects_boundary_drift(
    report: dict[str, object],
    v65_module,
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
        v65_module.check_report(poisoned)
