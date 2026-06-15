from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v6_5_1_gold29_actual_response_smoke_nonprod"
ROLLBACK_KEY = "v6_5_retrieval_metric_unlock_packet_nonprod"
V6_6_RUN_KEY = "v6_6_structured_tool_operation_taxonomy_nonprod"
V6_7_RUN_KEY = "v6_7_agentic_retry_fail_closed_policy_nonprod"
V6_8_RUN_KEY = "v6_8_metric_gated_retrieval_quality_engineering_nonprod"
V6_9_RUN_KEY = "v6_9_answer_quality_gate_packet_nonprod"
V6_4_RUN_KEY = "v6_4_e2e_coverage_and_failure_taxonomy_nonprod"
V7_0_RUN_KEY = "v7_0_e2e_eval_architecture_closeout_nonprod"
STATUS = "V6_5_1_GOLD29_ACTUAL_RESPONSE_SMOKE_NONPROD_READY"
V5_5_ROOT = Path("reports/rag_eval/rag-ingestion/runs/v5_5")
V5_5_ARTIFACTS = {
    "official_metric_input": V5_5_ROOT / "official_metric_input.jsonl",
    "user_approved_gold_packet": V5_5_ROOT / "user_approved_gold_packet.jsonl",
    "user_approved_qrels": V5_5_ROOT / "user_approved_qrels.jsonl",
    "user_approved_expected_answers": V5_5_ROOT / "user_approved_expected_answers.jsonl",
    "user_approved_denominator": V5_5_ROOT / "user_approved_denominator.jsonl",
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
    "row_id",
    "case_id",
}
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
def v651_module():
    from ai.eval import rag_v651_gold29_actual_response_smoke_nonprod as v651

    return v651


@pytest.fixture()
def report(v651_module, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, object]:
    monkeypatch.setattr(v651_module.v63, "SentenceTransformerEmbedder", StubBgeM3Embedder)
    built = v651_module.build_report(
        root=ROOT,
        generated_at="2026-06-07T02:00:00Z",
        run_artifact_root=tmp_path / "v6_5_1_runtime",
    )
    v651_module.check_report(built)
    return built


def test_v651_report_schema_current_resolver_and_v65_rollback(report: dict[str, object]) -> None:
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
    assert report["logical_run_key"] == RUN_KEY
    assert report["status"] == STATUS
    assert report["current_resolves_to"] == RUN_KEY
    assert report["rollback_key"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["current_moved_from"] == ROLLBACK_KEY
    assert report["current_alias_policy"]["current_moved_to"] == RUN_KEY


def test_v651_reads_and_respects_v65_bridge_audit(report: dict[str, object]) -> None:
    source = report["source_v6_5_report_check"]

    assert source["run_key"] == ROLLBACK_KEY
    assert source["audited_rows"] == 29
    assert source["bridgeable_rows"] == 0
    assert source["bridged_retrieval_metric_computed"] is False
    assert source["bridged_metric_denominator"] == 0
    assert source["coverage_adjusted_denominator"] == 300
    assert source["coverage_adjusted_denominator_source"] == V6_4_RUN_KEY
    assert source["official_product_promotion_live_readiness_claim"] is False
    assert source["answer_quality_metric_computed"] is False


def test_v651_reads_v55_gold29_read_only_and_attempts_all_rows(report: dict[str, object]) -> None:
    source = report["v5_5_gold29_read_only_source"]
    smoke = report["actual_response_smoke_summary"]

    assert source["read_only"] is True
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
    assert source["post_render_alignment_only"] is True

    assert smoke["all_29_gold_rows_targeted"] is True
    assert smoke["actual_response_rows_attempted"] == 29
    assert smoke["silently_dropped_rows"] == 0
    assert smoke["skipped_rows"] == 0
    assert smoke["skip_reasons"] == {}
    assert smoke["rows_attempted_by_family"]["PDF"] >= 1
    assert smoke["rows_attempted_by_family"]["TEXT"] >= 3
    assert smoke["rows_attempted_by_family"]["XLSX"] >= 5


def test_v651_response_diagnostics_are_compact_and_never_drop_rows(report: dict[str, object]) -> None:
    rows = report["response_diagnostics"]
    summary = report["actual_response_smoke_summary"]

    assert len(rows) == 29
    assert summary["response_diagnostic_rows"] == 29
    assert report["actual_response_rows_attempted"] == summary["actual_response_rows_attempted"] == 29
    assert report["actual_response_rows_rendered"] == summary["actual_response_rows_rendered"]
    assert report["citation_verified_rows"] == summary["citation_verified_rows"]
    assert report["fail_closed_rows"] == summary["fail_closed_rows"]
    assert summary["actual_response_rows_rendered"] == sum(1 for row in rows if row["answer_rendered"])
    assert summary["citation_verified_rows"] == sum(1 for row in rows if row["citation_verified"])
    assert summary["fail_closed_rows"] == sum(1 for row in rows if row["fail_closed_reason"])

    seen = set()
    for row in rows:
        assert row["gold_row_hash"]
        assert row["query_hash"]
        assert row["source_family"] in {"PDF", "TEXT", "XLSX"}
        assert row["route_decision"] in {
            "pdf_rag_response_smoke",
            "text_rag_response_smoke",
            "xlsx_tool_augmented_rag_response_smoke",
        }
        assert row["retrieval_backend_used"] in {"vector", "bm25", "hybrid", "none"}
        assert isinstance(row["candidate_count"], int)
        assert isinstance(row["hydrated_evidence_count"], int)
        assert row["tool_required"] is (row["source_family"] == "XLSX")
        assert isinstance(row["tool_executed"], bool)
        assert isinstance(row["answer_rendered"], bool)
        assert isinstance(row["citation_rendered"], bool)
        assert isinstance(row["citation_verified"], bool)
        assert "answer_preview_redacted_or_hash" in row
        assert "evidence_ids_or_hashes" in row
        assert row["raw_prompt_payload_written"] is False
        assert row["raw_response_payload_written"] is False
        assert row["gold_row_hash"] not in seen
        seen.add(row["gold_row_hash"])
        assert_no_exact_keys(row, FORBIDDEN_PAYLOAD_KEYS)


def test_v651_candidate_generation_leakage_and_shortcut_guards(report: dict[str, object]) -> None:
    policy = report["candidate_generation_input_policy"]
    probe = report["candidate_generation_leakage_probe"]

    assert policy["allowed_fields"] == ["query_text", "source_family", "top_k"]
    assert policy["qrels_expected_supporting_loaded_after_render_only"] is True
    assert policy["expected_supporting_gold_qrels_used_for_candidate_generation"] is False
    assert policy["target_ids_used_for_candidate_generation"] is False
    assert policy["row_or_case_ids_used_for_candidate_generation"] is False
    assert policy["source_title_or_file_name_shortcuts_used"] is False
    assert policy["workbook_or_file_name_shortcuts_used"] is False
    assert policy["baseline_topk_or_prior_route_diagnostics_used"] is False
    assert policy["prior_v6_5_bridge_rows_used_for_candidate_generation"] is False
    assert policy["forbidden_fields_present_in_candidate_request_count"] == 0
    assert probe["passed"] is True
    assert probe["candidate_ids_changed_by_forbidden_field_poison_count"] == 0
    assert probe["probed_rows"] == 29


def test_v651_human_review_packet_contains_actual_answers_but_no_decisions(report: dict[str, object]) -> None:
    packet = report["actual_response_review_packet"]

    assert packet["packet_location"] == "primary_report_json_only"
    assert packet["row_count"] == 29
    assert packet["query_text_display_allowed"] is True
    assert packet["generated_final_answer_text_included"] is True
    assert packet["review_fields_left_blank"] is True
    assert packet["human_owned_decisions_filled"] is False
    assert packet["expected_answer_text_included"] is False
    assert packet["supporting_evidence_text_included"] is False
    assert packet["qrels_payload_included"] is False
    for row in packet["rows"]:
        assert row["query_text"]
        assert "generated_final_answer_text" in row
        assert "rendered_citations" in row
        assert "expected_answer_hash" in row
        assert "supporting_evidence_hash" in row
        assert row["review_answer_quality_label"] == ""
        assert row["review_relevance_label"] == ""
        assert row["review_answerability_label"] == ""
        assert_no_exact_keys(row, FORBIDDEN_PAYLOAD_KEYS)


def test_v651_metrics_tools_evidence_truth_and_protected_surfaces_stay_closed(report: dict[str, object]) -> None:
    for field in REQUIRED_FALSE_FIELDS:
        assert report[field] is False, field
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows_created"] == 0
    assert report["official_metric_input_rows_consumed"] == 0

    metric_policy = report["metrics_policy"]
    assert metric_policy["retrieval_quality_metric_computed"] is False
    assert metric_policy["answer_quality_metric_computed"] is False
    assert metric_policy["hit_at_k_computed"] is False
    assert metric_policy["mrr_computed"] is False
    assert metric_policy["ndcg_computed"] is False
    assert metric_policy["blocked_reason"] == "v6_5_bridgeable_rows_zero_no_safe_retrieval_metric_bridge"

    guard = report["tool_to_rag_leakage_guard"]
    assert guard["tool_outputs_counted_as_rag_hit"] is False
    assert guard["tool_success_contributed_to_hit_at_k"] is False
    assert guard["tool_success_contributed_to_mrr"] is False
    assert guard["tool_success_contributed_to_ndcg"] is False

    evidence = report["evidence_truth_boundary"]
    assert evidence["source_atom_evidence_bundle_role"] == "evidence_truth"
    assert evidence["search_view_vector_payload_role"] == "candidate_only"
    assert evidence["vector_payload_used_as_evidence_truth"] is False
    assert evidence["hydration_source"] == "SourceAtom/EvidenceBundle"
    assert evidence["evidence_truth_violation_count"] == 0

    protected = report["protected_surface_check"]
    assert protected["passed"] is True
    assert protected["mutated_paths"] == []
    assert protected["protected_namespaces_touched"] == []
    assert protected["gold_qrels_expected_supporting_relevance_answerability_clean"] is True
    assert protected["official_denominator_clean"] is True
    assert protected["production_db_cache_clean"] is True
    assert_no_exact_keys(report, {"raw_prompt_payload", "raw_response_payload", "raw_llm_response"})


def test_v651_v7_marker_guard_remains_active(report: dict[str, object]) -> None:
    guard = report["v7_guard"]

    assert guard["v7_0_run_key"] == V7_0_RUN_KEY
    assert guard["v7_0_recorded_as_premature_closeout_marker_only"] is True
    assert guard["v7_completion_claim_from_v7_0"] is False
    assert guard["v7_0_can_be_current_before_v6_6_to_v6_9_satisfied_or_skipped"] is False
    assert guard["missing_or_unskipped_predecessors"] == [
        "v6_6_structured_tool_operation_taxonomy_nonprod",
        "v6_7_agentic_retry_fail_closed_policy_nonprod",
        "v6_8_metric_gated_retrieval_quality_engineering_nonprod",
        "v6_9_answer_quality_gate_packet_nonprod",
    ]


def test_v651_single_primary_report_status_docs_and_hash_contract(
    tmp_path: Path,
    v651_module,
    report: dict[str, object],
) -> None:
    written, hashes = v651_module.write_report_bundle(tmp_path, report)
    v651_module.check_report(written, root=tmp_path)
    v651_module.update_docs(tmp_path, written)
    v651_module.append_status(tmp_path, written, artifact_hashes=hashes)
    v651_module.require_status_report_hash(tmp_path, written)

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
    assert status_rows[-1]["current_resolves_to"] == RUN_KEY
    assert status_rows[-1]["rollback_key"] == ROLLBACK_KEY
    assert status_rows[-1]["official_metric"] is False
    assert status_rows[-1]["artifact_sha256"]["report_json_sha256"] == written["artifact_sha256"]["report_json_sha256"]

    forbidden_sidecars = {
        "review_packet.csv",
        "review_packet.xlsx",
        "review_packet.jsonl",
        "actual_response_review_packet.jsonl",
        "metric_results.json",
        "metric_tiers.json",
        "denominator_manifest.jsonl",
        "structured_tool_diagnostics.jsonl",
        "agentic_loop_trace.jsonl",
        "true_rag_candidate_diagnostics.jsonl",
    }
    assert not (forbidden_sidecars & {path.name for path in run_root.iterdir()})

    for doc_name in ("rag-ingestion-progress.md", "rag-ingestion-measurements.md", "rag-ingestion-triage.md"):
        text = (tmp_path / "docs" / doc_name).read_text(encoding="utf-8")
        assert RUN_KEY in text
        assert "actual response" in text
        assert "v5_5" in text
        assert "no official/product/promotion/live-readiness claim" in text.lower()


def test_protected_namespace_git_status_is_clean_for_v651() -> None:
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
        ({"source_v6_5_report_check": {"bridgeable_rows": 1}}, "bridgeable"),
        ({"metrics_policy": {"retrieval_quality_metric_computed": True}}, "retrieval quality"),
        ({"candidate_generation_input_policy": {"expected_supporting_gold_qrels_used_for_candidate_generation": True}}, "candidate"),
        ({"actual_response_smoke_summary": {"silently_dropped_rows": 1}}, "silently dropped"),
        ({"v7_guard": {"v7_0_recorded_as_premature_closeout_marker_only": False}}, "v7_0"),
    ),
)
def test_check_report_rejects_boundary_drift(
    report: dict[str, object],
    v651_module,
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
        v651_module.check_report(poisoned)
