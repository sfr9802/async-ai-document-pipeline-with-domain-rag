from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_report_only_tuning_dry_run_plan_v1.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_report_only_tuning_dry_run_plan_v1_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dry_run_plan_is_track_specific_report_only_and_keeps_official_rows_closed(tmp_path: Path) -> None:
    module = load_module()
    paths = write_canonical_bundle(tmp_path)

    result = module.run_plan(
        board_path=paths["board"],
        readiness_plan_path=paths["readiness_plan"],
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_metadata_report_path=paths["pdf_metadata"],
        pdf_layout_report_path=paths["pdf_layout"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer"],
        progress_doc_path=paths["progress_doc"],
        output_report=tmp_path / "report_only_tuning_dry_run_plan_v1.json",
        output_md=tmp_path / "report_only_tuning_dry_run_plan_v1.md",
        checklist_report=tmp_path / "official_metric_transition_readiness_checklist_v1.json",
        checklist_md=tmp_path / "official_metric_transition_readiness_checklist_v1.md",
        human_audit_packet_path=tmp_path / "rag_human_audit_packet_v1.json",
    )

    plan = result["plan"]
    checklist = result["checklist"]

    assert plan["status"] == "REPORT_ONLY_DRY_RUN_PLAN_READY"
    assert plan["report_only"] is True
    assert plan["tuning_run_started"] is False
    assert plan["official_metrics_closed"] is True
    assert plan["official_metric_input_rows_by_track"] == {
        "text_namu_v2_1": 0,
        "xlsx_business_structured": 0,
        "pdf_business_ocr_mm": 0,
    }
    assert plan["cross_track_average_optimization_allowed"] is False
    assert plan["split_policy"]["final_holdout_opened"] is False
    assert plan["split_policy"]["sealed_holdout_consumed"] is False
    assert plan["split_policy"]["parameter_winner_selected"] is False
    assert plan["track_dev_set_policy"]["text_namu_v2_1"]["input_rows"] == 66
    assert plan["track_dev_set_policy"]["text_namu_v2_1"]["dev_set_role"] == "diagnostic_dev_not_final_holdout"
    assert plan["track_dev_set_policy"]["xlsx_business_structured"]["eligible_diagnostic_dev_rows"] == 23
    assert plan["track_dev_set_policy"]["pdf_business_ocr_mm"]["answer_citation_dry_run_eligibility"] == "eligible"
    assert "verifier_strictness_report_only" in plan["parameter_matrix"]["allowed_report_only"]["text_namu_v2_1"]
    assert "table_context_window_report_only" in plan["parameter_matrix"]["allowed_report_only"]["xlsx_business_structured"]
    assert "bbox_region_strictness_report_only" in plan["parameter_matrix"]["allowed_report_only"]["pdf_business_ocr_mm"]
    assert "multi_route_diagnostic_policy_report_only" in plan["parameter_matrix"]["allowed_report_only"]["route_orchestration_diagnostic_only"]
    assert "candidate_artifact_promotion" in plan["parameter_matrix"]["blocked_parameters"]
    assert plan["dry_run_evaluation_matrix"]["pdf_business_ocr_mm"]["lane_checks"][
        "content_file_identity_lane_merge_detected"
    ] is False
    assert plan["dry_run_evaluation_matrix"]["xlsx_business_structured"]["leakage_lane_checks"][
        "hidden_excluded_rows_in_candidates"
    ] is False
    assert plan["validation"]["ok"] is True
    assert all(item["sha256"] for item in plan["canonical_freshness"]["artifacts"])
    assert checklist["official_denominator_registry_opened"] is False
    assert checklist["official_metric_input_rows"] == 0
    assert checklist["human_audit_completed"] is False
    assert checklist["production_mutation"] is False
    assert checklist["cross_track_average"] is False


def test_dry_run_plan_fails_closed_if_pdf_answer_packet_missing_but_board_marks_answer_ready(
    tmp_path: Path,
) -> None:
    module = load_module()
    paths = write_canonical_bundle(tmp_path)
    paths["pdf_answer"].unlink()

    result = module.run_plan(
        board_path=paths["board"],
        readiness_plan_path=paths["readiness_plan"],
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_metadata_report_path=paths["pdf_metadata"],
        pdf_layout_report_path=paths["pdf_layout"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer"],
        progress_doc_path=paths["progress_doc"],
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
        checklist_report=tmp_path / "checklist.json",
        checklist_md=tmp_path / "checklist.md",
        human_audit_packet_path=tmp_path / "missing_audit.json",
    )

    plan = result["plan"]

    assert plan["status"] == "FAIL_CLOSED_CANONICAL_FRESHNESS"
    assert "PDF_ANSWER_CITATION_PACKET_MISSING_FAIL_CLOSED" in plan["validation"]["errors"]
    assert plan["track_dev_set_policy"]["pdf_business_ocr_mm"]["answer_citation_dry_run_eligibility"] == "blocked"
    assert plan["tuning_run_started"] is False
    assert plan["official_metric_input_rows_by_track"]["pdf_business_ocr_mm"] == 0


def test_dry_run_plan_fails_closed_if_pdf_answer_packet_exists_but_is_not_ready(tmp_path: Path) -> None:
    module = load_module()
    paths = write_canonical_bundle(tmp_path)
    pdf_answer = json.loads(paths["pdf_answer"].read_text(encoding="utf-8"))
    pdf_answer["status"] = "DIAGNOSTIC_POLICY_PACKET_BLOCKED_BY_LANE_OR_EVIDENCE_GUARD"
    pdf_answer["clean_pass_rows"] = 0
    pdf_answer["lane_policy_blocked_rows"] = 7
    paths["pdf_answer"].write_text(json.dumps(pdf_answer, ensure_ascii=False), encoding="utf-8")

    result = module.run_plan(
        board_path=paths["board"],
        readiness_plan_path=paths["readiness_plan"],
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_metadata_report_path=paths["pdf_metadata"],
        pdf_layout_report_path=paths["pdf_layout"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer"],
        progress_doc_path=paths["progress_doc"],
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
        checklist_report=tmp_path / "checklist.json",
        checklist_md=tmp_path / "checklist.md",
        human_audit_packet_path=tmp_path / "missing_audit.json",
    )

    plan = result["plan"]
    assert plan["status"] == "FAIL_CLOSED_GUARDRAIL"
    assert "PDF_ANSWER_CITATION_PACKET_NOT_READY_FAIL_CLOSED" in plan["validation"]["errors"]
    assert plan["track_dev_set_policy"]["pdf_business_ocr_mm"]["answer_citation_dry_run_eligibility"] == "blocked"


def test_dry_run_plan_fails_closed_on_xlsx_leakage_pdf_shortfall_or_lane_merge(tmp_path: Path) -> None:
    module = load_module()
    paths = write_canonical_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_packet"].read_text(encoding="utf-8"))
    xlsx["leakage_raw_status"] = "FAIL"
    paths["xlsx_packet"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")
    pdf = json.loads(paths["pdf_repair"].read_text(encoding="utf-8"))
    pdf["strict_ready_rows"] = 6
    pdf["lane_separation"]["content_and_file_identity_aggregated"] = True
    paths["pdf_repair"].write_text(json.dumps(pdf, ensure_ascii=False), encoding="utf-8")

    result = module.run_plan(
        board_path=paths["board"],
        readiness_plan_path=paths["readiness_plan"],
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_metadata_report_path=paths["pdf_metadata"],
        pdf_layout_report_path=paths["pdf_layout"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer"],
        progress_doc_path=paths["progress_doc"],
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
        checklist_report=tmp_path / "checklist.json",
        checklist_md=tmp_path / "checklist.md",
        human_audit_packet_path=tmp_path / "missing_audit.json",
    )

    errors = result["plan"]["validation"]["errors"]
    assert result["plan"]["status"] == "FAIL_CLOSED_GUARDRAIL"
    assert "XLSX_LEAKAGE_STATUS_NOT_PASS" in errors
    assert "PDF_EVIDENCE_STRICT_READY_ROWS_LT_7" in errors
    assert "PDF_CONTENT_FILE_IDENTITY_LANE_MERGE_DETECTED" in errors
    assert result["plan"]["official_metric_input_rows_by_track"] == {
        "text_namu_v2_1": 0,
        "xlsx_business_structured": 0,
        "pdf_business_ocr_mm": 0,
    }


def test_dry_run_plan_fails_closed_if_board_is_failed_or_protected_guardrail_true(tmp_path: Path) -> None:
    module = load_module()
    paths = write_canonical_bundle(tmp_path)
    board = json.loads(paths["board"].read_text(encoding="utf-8"))
    board["status"] = "FAILED_GUARDRAIL"
    board["validation"] = {"ok": False, "errors": ["synthetic board failure"]}
    board["guardrails"]["production_vector_written"] = True
    paths["board"].write_text(json.dumps(board, ensure_ascii=False), encoding="utf-8")

    result = module.run_plan(
        board_path=paths["board"],
        readiness_plan_path=paths["readiness_plan"],
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_metadata_report_path=paths["pdf_metadata"],
        pdf_layout_report_path=paths["pdf_layout"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer"],
        progress_doc_path=paths["progress_doc"],
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
        checklist_report=tmp_path / "checklist.json",
        checklist_md=tmp_path / "checklist.md",
        human_audit_packet_path=tmp_path / "missing_audit.json",
    )

    errors = result["plan"]["validation"]["errors"]
    assert result["plan"]["status"] == "FAIL_CLOSED_GUARDRAIL"
    assert "BOARD_STATUS_NOT_DIAGNOSTIC_PREFLIGHT_READY" in errors
    assert "BOARD_VALIDATION_NOT_OK" in errors
    assert "BOARD_PROTECTED_GUARDRAIL_TRUE:production_vector_written" in errors


def test_dry_run_plan_fails_closed_if_board_cross_track_average_is_computed(tmp_path: Path) -> None:
    module = load_module()
    paths = write_canonical_bundle(tmp_path)
    board = json.loads(paths["board"].read_text(encoding="utf-8"))
    board["cross_track_averages_computed"] = True
    paths["board"].write_text(json.dumps(board, ensure_ascii=False), encoding="utf-8")

    result = module.run_plan(
        board_path=paths["board"],
        readiness_plan_path=paths["readiness_plan"],
        text_packet_path=paths["text_packet"],
        xlsx_packet_path=paths["xlsx_packet"],
        pdf_metadata_report_path=paths["pdf_metadata"],
        pdf_layout_report_path=paths["pdf_layout"],
        pdf_repair_report_path=paths["pdf_repair"],
        pdf_answer_packet_path=paths["pdf_answer"],
        progress_doc_path=paths["progress_doc"],
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
        checklist_report=tmp_path / "checklist.json",
        checklist_md=tmp_path / "checklist.md",
        human_audit_packet_path=tmp_path / "missing_audit.json",
    )

    errors = result["plan"]["validation"]["errors"]
    assert result["plan"]["status"] == "FAIL_CLOSED_GUARDRAIL"
    assert "BOARD_CROSS_TRACK_AVERAGES_COMPUTED" in errors
    assert result["plan"]["cross_track_averages_computed"] is False


def write_canonical_bundle(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "board": tmp_path / "three_track_metric_preflight_board.json",
        "readiness_plan": tmp_path / "hyperparameter_tuning_readiness_plan.json",
        "text_packet": tmp_path / "rag_text_namu_answer_citation_policy_review_packet_v2_1.json",
        "xlsx_packet": tmp_path / "rag_xlsx_answer_citation_policy_review_packet_v1.json",
        "pdf_metadata": tmp_path / "pdf_evidence_metadata_enrichment_report.json",
        "pdf_layout": tmp_path / "pdf_layout_gap_closure_report.json",
        "pdf_repair": tmp_path / "pdf_evidence_readiness_repair_report.json",
        "pdf_answer": tmp_path / "rag_pdf_answer_citation_policy_review_packet_v1.json",
        "progress_doc": tmp_path / "rag-ingestion-progress.md",
    }
    write_json(
        paths["board"],
        {
            "schema_version": "three_track_metric_preflight_board_v1",
            "generated_at": "2026-05-15T02:11:51+09:00",
            "status": "DIAGNOSTIC_PREFLIGHT_READY",
            "diagnostic_only": True,
            "official_metric": False,
            "promotion_evidence": False,
            "official_metric_input_rows_by_track": {
                "text_namu_v2_1": 0,
                "xlsx_business_structured": 0,
                "pdf_business_ocr_mm": 0,
            },
            "cross_track_averages_computed": False,
            "blocker_status": {
                "xlsx_leakage_blocked": False,
                "pdf_evidence_readiness_blocked": False,
                "pdf_answer_citation_blocked": False,
            },
            "tracks": {
                "text_namu_v2_1": {"official_metric_input_rows": 0},
                "xlsx_business_structured": {
                    "official_metric_input_rows": 0,
                    "leakage_status": "PASS",
                    "leakage_count": 0,
                },
                "pdf_business_ocr_mm": {
                    "official_metric_input_rows": 0,
                    "input_rows": 7,
                    "strict_gate_readiness_count": 7,
                    "strict_gate_rerun_eligible": True,
                    "answer_citation_status": "DIAGNOSTIC_POLICY_PACKET_READY",
                },
            },
            "guardrails": {"official_metric_input_rows_remain_zero": True},
            "validation": {"ok": True, "errors": []},
        },
    )
    write_json(
        paths["readiness_plan"],
        {
            "schema_version": "hyperparameter_tuning_readiness_plan_v1",
            "generated_at": "2026-05-15T02:11:51+09:00",
            "status": "REPORT_ONLY_READY",
            "report_only": True,
            "tuning_run_started": False,
            "official_metrics_closed": True,
            "official_metric_input_rows": 0,
            "cross_track_average_optimization_allowed": False,
            "validation": {"ok": True, "errors": []},
        },
    )
    write_json(
        paths["text_packet"],
        {
            "schema_version": "rag_text_namu_answer_citation_policy_review_packet_v2_1",
            "generated_at": "2026-05-14T00:33:33+09:00",
            "status": "POLICY_REVIEW_PACKET_READY",
            "diagnostic_only": True,
            "row_count": 66,
            "diagnostic_metric_preview": {
                "strict_clean_answer_preview": {"numerator": 60, "denominator": 66},
                "citation_supported_preview": {"numerator": 65, "denominator": 66},
                "unresolved_count": 1,
                "official_metric_input_rows": 0,
            },
            "row_groups": {
                "cleanup_rows": {"row_count": 5},
                "unresolved_rows": {"row_count": 1},
            },
            "source_artifacts": {},
        },
    )
    write_json(
        paths["xlsx_packet"],
        {
            "schema_version": "rag_xlsx_answer_citation_policy_review_packet_v1",
            "generated_at": "2026-05-14T14:54:10+09:00",
            "status": "DIAGNOSTIC_POLICY_PACKET_READY",
            "diagnostic_only": True,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "strict_silver_rows": 23,
            "leakage_raw_status": "PASS",
            "leakage_raw_total": 0,
            "hidden_negative_rows": 3,
            "normalized_excluded_rows": 14,
            "pending_excluded_rows": 2,
            "diagnostic_metric_preview": {
                "generated_answer_rows": 23,
                "clean_pass_rows": 23,
                "cleanup_rows": 0,
                "rewrite_unresolved_rows": 0,
                "citation_fully_supported_rows": 23,
                "citation_locator_valid_rows": 23,
                "leakage_status": "PASS",
                "leakage_count": 0,
                "official_metric_input_rows": 0,
            },
            "source_artifacts": {},
        },
    )
    write_json(
        paths["pdf_metadata"],
        {
            "schema_version": "pdf_evidence_metadata_enrichment_report_v1",
            "generated_at": "2026-05-15T02:06:34+09:00",
            "status": "PDF_METADATA_ENRICHMENT_COMPLETED_STRICT_READY",
            "diagnostic_only": True,
            "official_metric_input_rows": 0,
            "after_counts": {"input_rows": 7, "strict_ready_rows": 7},
        },
    )
    write_json(
        paths["pdf_layout"],
        {
            "schema_version": "pdf_layout_gap_closure_report_v1",
            "generated_at": "2026-05-15T02:06:34+09:00",
            "status": "PDF_LAYOUT_GAP_CLOSED_ALL_STRICT_READY",
            "diagnostic_only": True,
            "official_metric_input_rows": 0,
            "input_rows": 7,
            "strict_ready_rows_after": 7,
            "diagnostic_only_fallback_rows_after": 0,
            "remaining_blockers": {},
        },
    )
    write_json(
        paths["pdf_repair"],
        {
            "schema_version": "pdf_evidence_readiness_repair_report_v1",
            "generated_at": "2026-05-15T02:06:34+09:00",
            "status": "READY_FOR_DIAGNOSTIC_STRICT_GATE_RERUN",
            "diagnostic_only": True,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "input_rows": 7,
            "strict_ready_rows": 7,
            "diagnostic_only_fallback_rows": 0,
            "search_unit_id_available_count": 7,
            "parser_source_metadata_available_count": 7,
            "nearby_paragraph_count": 7,
            "native_or_ocr_trust_available_count": 7,
            "citation_locator_complete_count": 7,
            "lane_separation": {"content_and_file_identity_aggregated": False},
            "strict_gate_rerun": {"eligible": True, "rerun_performed": True},
        },
    )
    write_json(
        paths["pdf_answer"],
        {
            "schema_version": "rag_pdf_answer_citation_policy_review_packet_v1",
            "generated_at": "2026-05-15T02:11:51+09:00",
            "status": "DIAGNOSTIC_POLICY_PACKET_READY",
            "diagnostic_only": True,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "input_rows": 7,
            "strict_ready_rows": 7,
            "generated_answer_rows": 7,
            "answer_support_pass_count": 7,
            "citation_locator_valid_count": 7,
            "clean_pass_rows": 7,
            "cleanup_rows": 0,
            "unresolved_rows": 0,
            "lane_policy_blocked_rows": 0,
            "pdf_answer_generation_denominator_opened": False,
            "content_file_identity_lane_merge": False,
            "filename_only_identity_accepted": False,
            "guardrails": {"content_file_identity_lane_merge": False},
        },
    )
    paths["progress_doc"].write_text(
        "Current PDF strict ready rows `7`; XLSX leakage `PASS`; official_metric_input_rows `0`.\n",
        encoding="utf-8",
    )
    return paths


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
