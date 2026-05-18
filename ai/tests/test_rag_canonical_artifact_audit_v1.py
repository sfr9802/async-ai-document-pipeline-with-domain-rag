from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_canonical_artifact_audit_v1.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_canonical_artifact_audit_v1_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_canonical_artifact_audit_passes_current_ready_pack_and_writes_slim_outputs(tmp_path: Path) -> None:
    module = load_module()
    paths = write_canonical_pack(tmp_path)

    result = module.run_audit(
        canonical_paths=paths["canonical_paths"],
        output_report=tmp_path / "canonical_artifact_audit_v1.json",
        output_md=tmp_path / "canonical_artifact_audit_v1.md",
        slim_manifest_report=tmp_path / "slim_canonical_pack_manifest_v1.json",
        slim_manifest_md=tmp_path / "slim_canonical_pack_manifest_v1.md",
        script_plan_report=tmp_path / "script_simplification_plan_v1.json",
        script_plan_md=tmp_path / "script_simplification_plan_v1.md",
    )

    audit = result["audit"]
    manifest = result["slim_manifest"]
    script_plan = result["script_plan"]

    assert audit["status"] == "CANONICAL_ARTIFACT_AUDIT_PASS"
    assert audit["validation"]["ok"] is True
    assert audit["summary"]["official_metric_input_rows_total"] == 2
    assert audit["summary"]["promotion_evidence_true_count"] == 0
    assert audit["summary"]["tuning_run_started"] is False
    assert all(row["exists"] and row["sha256"] for row in audit["artifacts"])
    assert audit["artifact_index"]["report_only_tuning_dry_run_plan"]["status"] == "REPORT_ONLY_DRY_RUN_PLAN_READY"
    assert audit["artifact_index"]["human_audit_packet"]["status"] == "HUMAN_AUDIT_PACKET_V2_READY"

    canonical_paths = {row["path"] for row in manifest["keep_as_canonical_current_reports"]}
    assert "ai/eval/reports/rag-ingestion/three_track_metric_preflight_board.json" in canonical_paths
    assert "ai/eval/reports/rag-ingestion/stale_pdf_strict_ready_rows_0_board.json" not in canonical_paths
    assert manifest["validation"]["ok"] is True
    assert "rag_canonical_artifact_audit_v1.py" in script_plan["groups"]["keep_guardrail_audit"]
    assert "rag_anti_shortcut_guardrail_audit_v1.py" in script_plan["groups"]["keep_guardrail_audit"]


def test_canonical_artifact_audit_fails_if_stale_blocked_board_is_selected(tmp_path: Path) -> None:
    module = load_module()
    paths = write_canonical_pack(tmp_path)
    board = read_json(paths["board"])
    board["generated_at"] = "2026-05-13T00:00:00+00:00"
    board["status"] = "DIAGNOSTIC_PREFLIGHT_BLOCKED"
    board["tracks"]["xlsx_business_structured"]["leakage_status"] = "FAIL"
    board["tracks"]["pdf_business_ocr_mm"]["strict_gate_readiness_count"] = 0
    write_json(paths["board"], board)

    result = module.run_audit(
        canonical_paths=paths["canonical_paths"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
        slim_manifest_report=tmp_path / "manifest.json",
        slim_manifest_md=tmp_path / "manifest.md",
        script_plan_report=tmp_path / "script_plan.json",
        script_plan_md=tmp_path / "script_plan.md",
    )

    assert result["audit"]["status"] == "CANONICAL_ARTIFACT_AUDIT_FAIL_CLOSED"
    errors = result["audit"]["validation"]["errors"]
    assert "board status must be DIAGNOSTIC_PREFLIGHT_READY" in errors
    assert "selected board contains stale XLSX leakage FAIL state" in errors
    assert "selected board contains stale PDF strict_ready_rows=0 state" in errors


def test_canonical_artifact_audit_fails_if_ready_plan_missing_human_audit(tmp_path: Path) -> None:
    module = load_module()
    paths = write_canonical_pack(tmp_path)
    paths["human_audit"].unlink()

    result = module.run_audit(
        canonical_paths=paths["canonical_paths"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
        slim_manifest_report=tmp_path / "manifest.json",
        slim_manifest_md=tmp_path / "manifest.md",
        script_plan_report=tmp_path / "script_plan.json",
        script_plan_md=tmp_path / "script_plan.md",
    )

    errors = result["audit"]["validation"]["errors"]
    assert result["audit"]["status"] == "CANONICAL_ARTIFACT_AUDIT_FAIL_CLOSED"
    assert "missing required canonical file: human_audit_packet" in errors
    assert "latest plan says ready but human audit packet is missing" in errors


def test_canonical_artifact_audit_fails_if_pdf_packet_missing_while_plan_answer_ready(tmp_path: Path) -> None:
    module = load_module()
    paths = write_canonical_pack(tmp_path)
    paths["pdf_answer"].unlink()

    result = module.run_audit(
        canonical_paths=paths["canonical_paths"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
        slim_manifest_report=tmp_path / "manifest.json",
        slim_manifest_md=tmp_path / "manifest.md",
        script_plan_report=tmp_path / "script_plan.json",
        script_plan_md=tmp_path / "script_plan.md",
    )

    errors = result["audit"]["validation"]["errors"]
    assert result["audit"]["status"] == "CANONICAL_ARTIFACT_AUDIT_FAIL_CLOSED"
    assert "latest board says ready but PDF answer/citation packet is missing" in errors
    assert "dry-run plan treats PDF as answer-ready but PDF answer/citation packet is missing" in errors


def test_canonical_artifact_audit_fails_if_pdf_packet_exists_but_blocked_or_stale(tmp_path: Path) -> None:
    module = load_module()
    paths = write_canonical_pack(tmp_path)
    pdf = read_json(paths["pdf_answer"])
    pdf["status"] = "DIAGNOSTIC_POLICY_PACKET_BLOCKED_BY_LANE_OR_EVIDENCE_GUARD"
    pdf["clean_pass_rows"] = 0
    pdf["lane_policy_blocked_rows"] = 7
    pdf["validation"] = {"ok": False, "errors": ["blocked by lane"]}
    write_json(paths["pdf_answer"], pdf)

    result = module.run_audit(
        canonical_paths=paths["canonical_paths"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
        slim_manifest_report=tmp_path / "manifest.json",
        slim_manifest_md=tmp_path / "manifest.md",
        script_plan_report=tmp_path / "script_plan.json",
        script_plan_md=tmp_path / "script_plan.md",
    )

    errors = result["audit"]["validation"]["errors"]
    assert result["audit"]["status"] == "CANONICAL_ARTIFACT_AUDIT_FAIL_CLOSED"
    assert "PDF answer/citation packet must be DIAGNOSTIC_POLICY_PACKET_READY" in errors
    assert "PDF answer/citation packet must have 7 clean/support/citation rows and 0 lane blockers" in errors
    assert "PDF answer/citation packet validation.ok must be true" in errors


def test_canonical_artifact_audit_fails_if_cross_track_average_flags_are_open(tmp_path: Path) -> None:
    module = load_module()
    paths = write_canonical_pack(tmp_path)
    dry_plan = read_json(paths["dry_plan"])
    dry_plan["cross_track_average_optimization_allowed"] = True
    dry_plan["cross_track_averages_computed"] = True
    dry_plan["split_policy"]["cross_track_average_computed"] = True
    write_json(paths["dry_plan"], dry_plan)

    result = module.run_audit(
        canonical_paths=paths["canonical_paths"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
        slim_manifest_report=tmp_path / "manifest.json",
        slim_manifest_md=tmp_path / "manifest.md",
        script_plan_report=tmp_path / "script_plan.json",
        script_plan_md=tmp_path / "script_plan.md",
    )

    errors = result["audit"]["validation"]["errors"]
    assert result["audit"]["status"] == "CANONICAL_ARTIFACT_AUDIT_FAIL_CLOSED"
    assert "report_only_tuning_dry_run_plan cross-track average flags must remain false" in errors


def test_canonical_artifact_audit_fails_if_progress_doc_contradicts_ready_state(tmp_path: Path) -> None:
    module = load_module()
    paths = write_canonical_pack(tmp_path)
    paths["progress_doc"].write_text(
        "Current state says XLSX leakage FAIL and PDF strict_ready_rows=0 without historical marker.\n",
        encoding="utf-8",
    )

    result = module.run_audit(
        canonical_paths=paths["canonical_paths"],
        output_report=tmp_path / "audit.json",
        output_md=tmp_path / "audit.md",
        slim_manifest_report=tmp_path / "manifest.json",
        slim_manifest_md=tmp_path / "manifest.md",
        script_plan_report=tmp_path / "script_plan.json",
        script_plan_md=tmp_path / "script_plan.md",
    )

    errors = result["audit"]["validation"]["errors"]
    assert "progress doc contradicts current XLSX PASS state" in errors
    assert "progress doc contradicts current PDF strict_ready_rows=7 state" in errors


def write_canonical_pack(tmp_path: Path) -> dict[str, object]:
    reports = tmp_path / "ai" / "eval" / "reports" / "rag-ingestion"
    review = tmp_path / "ai" / "eval" / "review"
    docs = tmp_path / "docs"
    reports.mkdir(parents=True)
    review.mkdir(parents=True)
    docs.mkdir(parents=True)

    paths = {
        "board": reports / "three_track_metric_preflight_board.json",
        "board_md": reports / "three_track_metric_preflight_board.md",
        "readiness": reports / "hyperparameter_tuning_readiness_plan.json",
        "readiness_md": reports / "hyperparameter_tuning_readiness_plan.md",
        "dry_plan": reports / "report_only_tuning_dry_run_plan_v1.json",
        "dry_plan_md": reports / "report_only_tuning_dry_run_plan_v1.md",
        "checklist": reports / "official_metric_transition_readiness_checklist_v1.json",
        "checklist_md": reports / "official_metric_transition_readiness_checklist_v1.md",
        "human_audit": review / "rag_human_audit_packet_v2_question_quality_local_llm.json",
        "human_audit_md": review / "rag_human_audit_packet_v2_question_quality_local_llm.md",
        "applied_decisions": review / "rag_human_audit_v2_applied_decisions.json",
        "applied_decisions_md": review / "rag_human_audit_v2_applied_decisions.md",
        "denominator_preview": reports / "official_denominator_candidate_diff_preview_v1.json",
        "denominator_preview_md": reports / "official_denominator_candidate_diff_preview_v1.md",
        "registry_application": reports / "official_question_gold_v2_registry_application_report.json",
        "registry_application_md": reports / "official_question_gold_v2_registry_application_report.md",
        "metric_config": reports / "metric_input_v1.json",
        "metric_config_md": reports / "metric_input_v1.md",
        "xlsx": reports / "rag_xlsx_answer_citation_policy_review_packet_v1.json",
        "pdf_answer": reports / "rag_pdf_answer_citation_policy_review_packet_v1.json",
        "pdf_metadata": reports / "pdf_evidence_metadata_enrichment_report.json",
        "pdf_layout": reports / "pdf_layout_gap_closure_report.json",
        "pdf_repair": reports / "pdf_evidence_readiness_repair_report.json",
        "text": review / "rag_text_namu_answer_citation_policy_review_packet_v2_1.json",
        "progress_doc": docs / "rag-ingestion-progress.md",
    }
    write_json(paths["board"], board_payload())
    write_json(paths["readiness"], readiness_payload())
    write_json(paths["dry_plan"], dry_plan_payload())
    write_json(paths["checklist"], checklist_payload())
    write_json(paths["human_audit"], human_audit_payload())
    write_json(paths["applied_decisions"], applied_decisions_payload())
    write_json(paths["denominator_preview"], denominator_preview_payload())
    write_json(paths["registry_application"], registry_application_payload())
    write_json(paths["metric_config"], metric_config_payload())
    write_json(paths["xlsx"], xlsx_payload())
    write_json(paths["pdf_answer"], pdf_answer_payload())
    write_json(paths["pdf_metadata"], pdf_metadata_payload())
    write_json(paths["pdf_layout"], pdf_layout_payload())
    write_json(paths["pdf_repair"], pdf_repair_payload())
    write_json(paths["text"], text_payload())
    for key in (
        "board_md",
        "readiness_md",
        "dry_plan_md",
        "checklist_md",
        "human_audit_md",
        "applied_decisions_md",
        "denominator_preview_md",
        "registry_application_md",
        "metric_config_md",
    ):
        paths[key].write_text("# current report\n", encoding="utf-8")
    paths["progress_doc"].write_text(
        "Current board DIAGNOSTIC_PREFLIGHT_READY; XLSX leakage PASS; PDF strict_ready_rows=7; "
        "official_metric_input_rows=0; tuning_run_started=false; registry unchanged.\n",
        encoding="utf-8",
    )
    canonical_paths = {
        name: path
        for name, path in {
            "three_track_metric_preflight_board": paths["board"],
            "hyperparameter_tuning_readiness_plan": paths["readiness"],
            "report_only_tuning_dry_run_plan": paths["dry_plan"],
            "official_metric_transition_readiness_checklist": paths["checklist"],
            "human_audit_packet": paths["human_audit"],
            "human_audit_v2_applied_decisions": paths["applied_decisions"],
            "official_denominator_candidate_diff_preview": paths["denominator_preview"],
            "official_question_gold_v2_registry_application": paths["registry_application"],
            "official_metric_input_config": paths["metric_config"],
            "xlsx_answer_citation_policy_packet": paths["xlsx"],
            "pdf_answer_citation_policy_packet": paths["pdf_answer"],
            "pdf_evidence_metadata_enrichment": paths["pdf_metadata"],
            "pdf_layout_gap_closure": paths["pdf_layout"],
            "pdf_evidence_readiness_repair": paths["pdf_repair"],
            "text_namu_policy_packet": paths["text"],
            "progress_doc": paths["progress_doc"],
        }.items()
    }
    paths["canonical_paths"] = canonical_paths
    return paths


def board_payload() -> dict[str, object]:
    return {
        "schema_version": "three_track_metric_preflight_board_v1",
        "generated_at": "2026-05-15T00:00:00+00:00",
        "status": "DIAGNOSTIC_PREFLIGHT_READY",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "official_metric_input_rows_by_track": {
            "text_namu_v2_1": 0,
            "xlsx_business_structured": 0,
            "pdf_business_ocr_mm": 0,
        },
        "tracks": {
            "text_namu_v2_1": {"status": "FROZEN_DIAGNOSTIC_V2_1", "official_metric_input_rows": 0},
            "xlsx_business_structured": {"status": "DIAGNOSTIC_POLICY_PACKET_READY", "leakage_status": "PASS", "leakage_count": 0, "official_metric_input_rows": 0},
            "pdf_business_ocr_mm": {"status": "READY_FOR_DIAGNOSTIC_STRICT_GATE_RERUN", "answer_citation_status": "DIAGNOSTIC_POLICY_PACKET_READY", "strict_gate_readiness_count": 7, "official_metric_input_rows": 0},
        },
        "guardrails": {"official_metric_input_rows_remain_zero": True, "production_vector_written": False},
        "validation": {"ok": True, "errors": []},
    }


def readiness_payload() -> dict[str, object]:
    return {
        "schema_version": "hyperparameter_tuning_readiness_plan_v1",
        "generated_at": "2026-05-15T00:01:00+00:00",
        "status": "REPORT_ONLY_READY",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "tuning_run_started": False,
        "official_metrics_closed": True,
        "cross_track_average_optimization_allowed": False,
        "validation": {"ok": True, "errors": []},
    }


def dry_plan_payload() -> dict[str, object]:
    return {
        "schema_version": "report_only_tuning_dry_run_plan_v1",
        "generated_at": "2026-05-15T00:02:00+00:00",
        "status": "REPORT_ONLY_DRY_RUN_PLAN_READY",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "official_metric_input_rows_by_track": {
            "text_namu_v2_1": 0,
            "xlsx_business_structured": 0,
            "pdf_business_ocr_mm": 0,
        },
        "tuning_run_started": False,
        "official_metrics_closed": True,
        "cross_track_average_optimization_allowed": False,
        "track_dev_set_policy": {"pdf_business_ocr_mm": {"answer_citation_dry_run_eligibility": "eligible"}},
        "split_policy": {"parameter_winner_selected": False, "cross_track_average_computed": False},
        "validation": {"ok": True, "errors": []},
    }


def checklist_payload() -> dict[str, object]:
    return {
        "schema_version": "official_metric_transition_readiness_checklist_v1",
        "generated_at": "2026-05-15T00:03:00+00:00",
        "status": "OFFICIAL_TRANSITION_BLOCKED_PENDING_REPORT_ONLY_DECISION_APPLICATION",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "official_denominator_registry_opened": False,
        "human_audit_packet_generated": True,
        "human_audit_completed": True,
        "validation": {"ok": True, "errors": []},
    }


def human_audit_payload() -> dict[str, object]:
    return {
        "schema_version": "rag_human_audit_packet_v2_question_quality_local_llm",
        "generated_at": "2026-05-15T00:04:00+00:00",
        "status": "HUMAN_AUDIT_PACKET_V2_READY",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "human_audit_completed": True,
        "human_audit_label_counts": {"INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE": 2},
        "summary": {
            "total_user_action_rows": 19,
            "pdf_generated_candidates": 4,
            "xlsx_generated_candidates": 23,
            "human_labeled_rows": 2,
            "human_unlabeled_rows": 0,
            "human_audit_completed": True,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
        },
        "actionable_rows": [
            {
                "query_id": "pdf_1",
                "human_label": "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE",
                "allowed_decision_values": ["INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE"],
                "official_metric_input": False,
                "promotion_evidence": False,
            },
            {
                "query_id": "xlsx_1",
                "human_label": "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE",
                "allowed_decision_values": ["INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE"],
                "official_metric_input": False,
                "promotion_evidence": False,
            },
        ],
        "validation": {"ok": True, "errors": []},
    }


def applied_decisions_payload() -> dict[str, object]:
    return {
        "schema_version": "rag_human_audit_v2_applied_decisions_v1",
        "generated_at": "2026-05-15T00:04:30+00:00",
        "status": "HUMAN_AUDIT_V2_APPLIED_DECISIONS_READY",
        "report_only": True,
        "promotion_evidence": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "proposed_official_metric_candidate_rows": 2,
        "summary": {
            "approved_gold_candidate_rows": 2,
            "approved_rows_by_track": {"pdf_business_ocr_mm": 1, "xlsx_business_structured": 1},
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
        },
        "guardrails": {
            "official_denominator_registry_changed": False,
            "official_denominator_registry_mutation": False,
            "official_metric_executed": False,
        },
        "validation": {"ok": True, "errors": []},
    }


def denominator_preview_payload() -> dict[str, object]:
    return {
        "schema_version": "official_denominator_candidate_diff_preview_v1",
        "generated_at": "2026-05-15T00:04:40+00:00",
        "status": "OFFICIAL_DENOMINATOR_CANDIDATE_DIFF_PREVIEW_READY",
        "registry_diff_status": "PREVIEW_ONLY_NO_MUTATION",
        "promotion_evidence": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "proposed_official_metric_candidate_rows": 2,
        "summary": {
            "proposed_rows_total": 2,
            "proposed_rows_by_track": {"pdf_business_ocr_mm": 1, "xlsx_business_structured": 1},
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
        },
        "guardrails": {
            "official_denominator_registry_changed": False,
            "official_denominator_registry_mutation": False,
            "official_metric_executed": False,
        },
        "validation": {"ok": True, "errors": []},
    }


def metric_config_payload() -> dict[str, object]:
    return {
        "schema_version": "official_metric_input_config_v1",
        "generated_at": "2026-05-15T00:04:50+00:00",
        "status": "OFFICIAL_METRIC_INPUT_CONFIG_READY_PENDING_REGISTRY_APPLICATION",
        "promotion_evidence": False,
        "official_metric": False,
        "official_metric_execution_started": False,
        "metric_execution_allowed": False,
        "official_metric_input_rows": 0,
        "proposed_metric_input_rows": 2,
        "proposed_metric_input_rows_by_track": {"pdf_business_ocr_mm": 1, "xlsx_business_structured": 1},
        "tuning_run_started": False,
        "guardrails": {
            "official_denominator_registry_changed": False,
            "official_denominator_registry_mutation": False,
            "official_metric_executed": False,
        },
        "validation": {"ok": True, "errors": []},
    }


def registry_application_payload() -> dict[str, object]:
    return {
        "schema_version": "official_question_gold_v2_registry_application_v1",
        "generated_at": "2026-05-15T00:04:45+00:00",
        "status": "OFFICIAL_QUESTION_GOLD_V2_REGISTRY_APPLIED",
        "registry_updated": True,
        "promotion_evidence": False,
        "official_metric": False,
        "official_metric_execution_started": False,
        "official_metric_input_rows": 2,
        "official_metric_input_rows_by_track": {"pdf_business_ocr_mm": 1, "xlsx_business_structured": 1},
        "tuning_run_started": False,
        "guardrails": {
            "official_metric_execution_started": False,
            "gold_registry_mutation": False,
            "candidate_artifact_mutation": False,
            "immutable_baseline_mutation": False,
            "production_namespace_vector_index_mutation": False,
            "production_vector_written": False,
        },
        "validation": {"ok": True, "errors": []},
    }


def xlsx_payload() -> dict[str, object]:
    return {
        "schema_version": "rag_xlsx_answer_citation_policy_review_packet_v1",
        "generated_at": "2026-05-15T00:05:00+00:00",
        "status": "DIAGNOSTIC_POLICY_PACKET_READY",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "leakage_raw_status": "PASS",
        "leakage_raw_total": 0,
        "validation": {"ok": True, "errors": []},
    }


def pdf_answer_payload() -> dict[str, object]:
    return {
        "schema_version": "rag_pdf_answer_citation_policy_review_packet_v1",
        "generated_at": "2026-05-15T00:06:00+00:00",
        "status": "DIAGNOSTIC_POLICY_PACKET_READY",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "input_rows": 7,
        "strict_ready_rows": 7,
        "generated_answer_rows": 7,
        "clean_pass_rows": 7,
        "cleanup_rows": 0,
        "unresolved_rows": 0,
        "answer_support_pass_count": 7,
        "citation_locator_valid_count": 7,
        "lane_policy_blocked_rows": 0,
        "diagnostic_fallback_rows_used": 0,
        "content_file_identity_lane_merge": False,
        "filename_only_identity_accepted": False,
        "pdf_answer_generation_denominator_opened": False,
        "validation": {"ok": True, "errors": []},
    }


def pdf_metadata_payload() -> dict[str, object]:
    return {
        "schema_version": "pdf_evidence_metadata_enrichment_report_v1",
        "generated_at": "2026-05-15T00:07:00+00:00",
        "status": "PDF_METADATA_ENRICHMENT_COMPLETED_STRICT_READY",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "after_counts": {"strict_ready_rows": 7, "official_metric_input_rows": 0},
        "validation": {"ok": True, "errors": []},
    }


def pdf_layout_payload() -> dict[str, object]:
    return {
        "schema_version": "pdf_layout_gap_closure_report_v1",
        "generated_at": "2026-05-15T00:08:00+00:00",
        "status": "PDF_LAYOUT_GAP_CLOSED_ALL_STRICT_READY",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "strict_ready_rows_after": 7,
        "remaining_blockers": {},
        "validation": {"ok": True, "errors": []},
    }


def pdf_repair_payload() -> dict[str, object]:
    return {
        "schema_version": "pdf_evidence_readiness_repair_report_v1",
        "generated_at": "2026-05-15T00:09:00+00:00",
        "status": "READY_FOR_DIAGNOSTIC_STRICT_GATE_RERUN",
        "diagnostic_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "strict_ready_rows": 7,
        "repair_rows": [],
        "validation": {"ok": True, "errors": []},
    }


def text_payload() -> dict[str, object]:
    return {
        "schema_version": "rag_text_namu_answer_citation_policy_review_packet_v2_1",
        "generated_at": "2026-05-15T00:10:00+00:00",
        "status": "POLICY_REVIEW_PACKET_READY",
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "guardrails": {"official_metric_input_rows": 0, "promotion_evidence_rows": 0},
        "validation": {"ok": True, "errors": []},
    }


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
