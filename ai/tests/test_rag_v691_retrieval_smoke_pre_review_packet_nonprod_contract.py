from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_KEY = "v6_9_1_retrieval_smoke_pre_review_packet_nonprod"
CURRENT_RUN_KEY = "v6_9_answer_quality_gate_packet_nonprod"
STATUS = "V6_9_1_RETRIEVAL_SMOKE_PRE_REVIEW_PACKET_NONPROD_READY"
PROTECTED_PATHS = (
    "ai/eval/eval_queries",
    "ai/eval/source_registry",
    "ai/eval/indexes",
    "ai/eval/silver",
)
USER_OWNED_FIELDS = (
    "relevance_label",
    "answerability_label",
    "official_positive_qrels",
    "denominator_inclusion",
    "expected_answer_or_evidence_decision",
    "review_notes",
)
REQUIRED_FALSE_FIELDS = {
    "official_metric",
    "retrieval_quality_metric_computed",
    "answer_quality_metric_computed",
    "agentic_answer_metric_computed",
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
def v691_module():
    from ai.eval import rag_v691_retrieval_smoke_pre_review_packet_nonprod as v691

    return v691


@pytest.fixture(scope="module")
def report(v691_module) -> dict[str, object]:
    built = v691_module.build_report(root=ROOT, generated_at="2026-06-10T00:00:00Z")
    v691_module.check_report(built)
    return built


def test_v691_schema_is_additive_and_current_stays_v69(report: dict[str, object]) -> None:
    import ai.scripts.rag_eval as runner
    from ai.eval import rag_eval_registry as registry

    assert registry.resolve_run(RUN_KEY, root=ROOT).logical_key == RUN_KEY
    assert registry.resolve_run("current", root=ROOT).logical_key == CURRENT_RUN_KEY
    assert runner.DEFAULT_RUN_KEY == CURRENT_RUN_KEY
    assert runner.check_run("current")["logical_run_key"] == CURRENT_RUN_KEY

    assert report["run_id"] == RUN_KEY
    assert report["schema_version"] == f"{RUN_KEY}_report_v1"
    assert report["status"] == STATUS
    assert report["diagnostic_only"] is True
    assert report["non_production"] is True
    assert report["current_resolves_to"] == CURRENT_RUN_KEY
    assert report["current_alias_policy"]["current_moved"] is False


def test_v691_records_existing_v68_v69_state_without_opening_metrics(report: dict[str, object]) -> None:
    v68 = report["source_v6_8_retrieval_gate_check"]
    assert v68["safe_read_only_denominator_available"] is False
    assert v68["computed_only_denominator"] == 0
    assert v68["coverage_adjusted_denominator"] == 300
    assert v68["retrieval_quality_metric_computed"] is False
    assert v68["hit_at_k_computed"] is False
    assert v68["mrr_computed"] is False
    assert v68["ndcg_computed"] is False
    assert v68["by_backend"]["vector"]["with_candidates_rows"] == 299
    assert v68["by_backend"]["vector"]["hydrated_rows"] == 299
    assert v68["by_backend"]["bm25"]["with_candidates_rows"] == 300
    assert v68["by_backend"]["bm25"]["hydrated_rows"] == 300
    assert v68["by_backend"]["hybrid"]["with_candidates_rows"] == 300
    assert v68["by_backend"]["hybrid"]["hydrated_rows"] == 300

    v69 = report["source_v6_9_answer_quality_gate_check"]
    assert v69["packet_rows"] == 29
    assert v69["rows_by_family"] == {"PDF": 4, "TEXT": 6, "XLSX": 19}
    assert v69["agentic_verification_state_counts"]["passed"] == 10
    assert v69["agentic_verification_state_counts"]["skipped_no_answer"] == 19
    assert v69["human_owned_blank_rows"] == 29
    assert v69["answer_quality_metric_computed"] is False


def test_v691_metric_gate_fails_closed_pending_user_review(report: dict[str, object]) -> None:
    gate = report["metric_gate"]
    diagnosis = report["metric_unlock_diagnosis"]

    assert report["source_v6_5_bridge_check"]["bridgeable_rows"] == 0
    assert gate["gate_status"] == "closed_pending_user_review"
    assert gate["safe_read_only_denominator_available"] is False
    assert gate["computed_only_denominator"] == 0
    assert gate["coverage_adjusted_denominator"] == 300
    assert gate["retrieval_quality_metric_computed"] is False
    assert gate["answer_quality_metric_computed"] is False
    assert gate["hit_at_k_computed"] is False
    assert gate["mrr_computed"] is False
    assert gate["ndcg_computed"] is False
    assert gate["hit_at_k"] is None
    assert gate["mrr"] is None
    assert gate["ndcg"] is None
    assert gate["tool_outputs_excluded_from_true_rag_metrics"] is True
    assert gate["searchview_vector_payload_candidate_only"] is True
    assert gate["sourceatom_evidencebundle_evidence_truth"] is True
    assert diagnosis["metric_can_open_now"] is False
    assert diagnosis["legacy_v5_5_v6_5_bridge_forced"] is False
    assert diagnosis["current_based_qrels_review_packet_needed"] is True


def test_v691_review_packet_is_current_candidate_surface_only(report: dict[str, object]) -> None:
    packet = report["retrieval_smoke_review_packet"]
    summary = report["retrieval_smoke_review_packet_summary"]
    rows = packet["rows"]

    assert packet["review_packet_created"] is True
    assert packet["metric_computed_from_packet"] is False
    assert packet["packet_includes_tool_outputs"] is False
    assert summary["selected_query_count"] == 9
    assert summary["selected_queries_by_family"] == {"PDF": 3, "TEXT": 3, "XLSX": 3}
    assert set(summary["candidate_rows_by_backend"]) == {"vector", "bm25", "hybrid"}
    assert all(summary["candidate_rows_by_backend"][backend] > 0 for backend in ("vector", "bm25", "hybrid"))
    assert summary["user_owned_field_filled_count"] == 0
    assert len(rows) == summary["review_packet_row_count"]

    for row in rows:
        assert row["query_id"]
        assert row["source_family"] in {"PDF", "TEXT", "XLSX"}
        assert row["backend"] in {"vector", "bm25", "hybrid"}
        assert row["search_unit_id"].startswith("v63_su_")
        assert row["search_view_id"].startswith("v63_sv_")
        assert row["source_atom_id"].startswith("srcatom_v1_")
        assert row["locator_sha256"]
        assert row["excerpt_sha256"]
        assert row["candidate_surface_role"] == "SearchView candidate-only"
        assert row["evidence_truth_role"] == "SourceAtom/EvidenceBundle"
        assert row["tool_output"] is False
        assert row["review_status"] == "pending_user_review"
        for field in USER_OWNED_FIELDS:
            assert row[field] == ""
        forbidden_locator_keys = {"source_identity", "source_pdf_path", "source_pdf_filename", "workbook_name"}
        assert not (forbidden_locator_keys & set(row["locator"]))


def test_v691_boundaries_and_protected_surfaces_stay_closed(report: dict[str, object]) -> None:
    for field in REQUIRED_FALSE_FIELDS:
        assert report[field] is False, field
    assert report["official_metric_input_rows"] == 0
    assert report["official_metric_input_rows_created"] == 0
    assert report["official_metric_input_rows_consumed"] == 0
    assert report["candidate_generation_input_policy"]["expected_supporting_gold_qrels_used_for_candidate_generation"] is False
    assert report["candidate_generation_input_policy"]["target_ids_used_for_candidate_generation"] is False
    assert report["candidate_generation_input_policy"]["tool_outputs_used_for_true_rag_metric"] is False
    protected = report["protected_surface_check"]
    assert protected["passed"] is True
    assert protected["mutated_paths"] == []
    assert protected["protected_namespaces_touched"] == []


def test_v691_writes_review_packet_status_docs_and_hashes(
    tmp_path: Path,
    v691_module,
    report: dict[str, object],
) -> None:
    written, hashes = v691_module.write_report_bundle(tmp_path, report)
    v691_module.check_report(written, root=tmp_path)
    v691_module.update_docs(tmp_path, written)
    v691_module.append_status(tmp_path, written, artifact_hashes=hashes)
    v691_module.require_status_report_hash(tmp_path, written)

    run_root = tmp_path / "reports/rag_eval/rag-ingestion/runs" / RUN_KEY
    assert set(path.name for path in run_root.iterdir()) == {
        "report.json",
        "retrieval_smoke_review_packet.jsonl",
        "retrieval_smoke_review_packet.csv",
    }
    assert hashes["report_json_sha256"] == hashlib.sha256((run_root / "report.json").read_bytes()).hexdigest()
    assert hashes["retrieval_smoke_review_packet_jsonl_sha256"] == hashlib.sha256(
        (run_root / "retrieval_smoke_review_packet.jsonl").read_bytes()
    ).hexdigest()
    assert hashes["retrieval_smoke_review_packet_csv_sha256"] == hashlib.sha256(
        (run_root / "retrieval_smoke_review_packet.csv").read_bytes()
    ).hexdigest()

    status_rows = [
        json.loads(line)
        for line in (tmp_path / "reports/rag_eval/rag-ingestion/status.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert status_rows[-1]["logical_run_key"] == RUN_KEY
    assert status_rows[-1]["current_resolves_to"] == CURRENT_RUN_KEY
    assert status_rows[-1]["current_moved"] is False
    assert status_rows[-1]["retrieval_quality_metric_computed"] is False
    assert status_rows[-1]["review_packet_created"] is True

    for doc_name in ("rag-ingestion-progress.md", "rag-ingestion-measurements.md", "rag-ingestion-triage.md"):
        text = (tmp_path / "docs" / doc_name).read_text(encoding="utf-8")
        assert RUN_KEY in text
        assert "Hit@K/MRR/nDCG" in text
        assert "human-owned" in text


def test_protected_namespace_git_status_is_clean_for_v691() -> None:
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
        ({"current_resolves_to": RUN_KEY}, "current"),
        ({"retrieval_quality_metric_computed": True}, "retrieval quality"),
        ({"answer_quality_metric_computed": True}, "answer quality"),
        ({"human_owned_decisions_filled": True}, "human-owned"),
        ({"metric_gate": {"hit_at_k_computed": True}}, "hit_at_k"),
        ({"metric_unlock_diagnosis": {"legacy_v5_5_v6_5_bridge_forced": True}}, "legacy bridge"),
        ({"retrieval_smoke_review_packet_summary": {"user_owned_field_filled_count": 1}}, "user-owned"),
    ),
)
def test_check_report_rejects_boundary_drift(
    report: dict[str, object],
    v691_module,
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
        v691_module.check_report(poisoned)
