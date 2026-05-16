from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_three_track_metric_preflight_board.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_three_track_metric_preflight_board_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_board_keeps_tracks_separate_and_official_inputs_closed(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)

    board = module.run_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
        output_report=tmp_path / "three_track_metric_preflight_board.json",
        output_md=tmp_path / "three_track_metric_preflight_board.md",
    )

    assert board["status"] == "DIAGNOSTIC_PREFLIGHT_BLOCKED"
    assert set(board["tracks"]) == {
        "text_namu_v2_1",
        "xlsx_business_structured",
        "pdf_business_ocr_mm",
    }
    assert board["tracks"]["text_namu_v2_1"]["official_metric_input_rows"] == 0
    assert board["tracks"]["xlsx_business_structured"]["official_metric_input_rows"] == 0
    assert board["tracks"]["pdf_business_ocr_mm"]["official_metric_input_rows"] == 0
    assert board["tracks"]["text_namu_v2_1"]["status"] == "FROZEN_DIAGNOSTIC_V2_1"
    assert board["tracks"]["text_namu_v2_1"]["source_policy_packet_role"] == "frozen_source_packet_provenance"
    assert board["tracks"]["text_namu_v2_1"]["answer_citation_status"] == "frozen_diagnostic_v2_1"
    assert board["tracks"]["xlsx_business_structured"]["ready_rows"] == 0
    assert board["tracks"]["xlsx_business_structured"]["pre_leakage_support_pass_rows"] == 23
    assert board["cross_track_averages_computed"] is False
    assert "cross_track_average_value" not in json.dumps(board, ensure_ascii=False)
    assert "POLICY_REVIEW_PACKET_READY" not in json.dumps(board, ensure_ascii=False)
    assert "Supported/Ready" not in (tmp_path / "three_track_metric_preflight_board.md").read_text(encoding="utf-8")
    assert board["route_fallback_label_status"]["route_labels"] == "diagnostic_only"
    assert board["route_fallback_label_status"]["fallback_labels"] == "diagnostic_only"
    assert board["blocker_status"]["xlsx_leakage_blocked"] is True
    assert board["blocker_status"]["pdf_evidence_readiness_blocked"] is True


def test_board_status_identifies_single_xlsx_leakage_blocker(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    pdf = json.loads(paths["pdf_report"].read_text(encoding="utf-8"))
    pdf["status"] = "READY_FOR_STRICT_GATE_RERUN"
    pdf["counts"]["input_rows"] = 2
    pdf["counts"]["strict_gate_readiness_count"] = 2
    pdf["strict_gate_rerun"] = {"eligible": True, "rerun_performed": False}
    paths["pdf_report"].write_text(json.dumps(pdf, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "DIAGNOSTIC_PREFLIGHT_BLOCKED"
    assert board["cross_track_averages_computed"] is False


def test_board_uses_current_xlsx_leakage_fail_over_historical_pass_marker(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_report"].read_text(encoding="utf-8"))
    xlsx["status"] = "PASS"
    xlsx["historical_hidden_excluded_probe_status"] = "PASS"
    xlsx["leakage_raw_status"] = "FAIL"
    xlsx["diagnostic_metric_preview"]["leakage_status"] = "FAIL"
    xlsx["diagnostic_metric_preview"]["clean_pass_rows"] = 23
    paths["xlsx_report"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")
    pdf = json.loads(paths["pdf_report"].read_text(encoding="utf-8"))
    pdf["status"] = "READY_FOR_DIAGNOSTIC_STRICT_GATE_RERUN"
    pdf["input_rows"] = 7
    pdf["strict_ready_rows"] = 7
    pdf["strict_gate_rerun"] = {"eligible": True, "rerun_performed": False}
    paths["pdf_report"].write_text(json.dumps(pdf, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "DIAGNOSTIC_PREFLIGHT_BLOCKED"
    assert board["tracks"]["xlsx_business_structured"]["leakage_status"] == "FAIL"
    assert board["tracks"]["xlsx_business_structured"]["diagnostic_status"] == "blocked_by_leakage_reprobe"
    assert board["blocker_status"]["xlsx_leakage_blocked"] is True


def test_board_status_identifies_single_pdf_readiness_blocker(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_report"].read_text(encoding="utf-8"))
    xlsx["status"] = "DIAGNOSTIC_POLICY_PACKET_READY"
    xlsx["leakage_raw_status"] = "PASS"
    xlsx["leakage_reprobe"] = {"status": "PASS", "surface_leakage_count": 0}
    xlsx["diagnostic_metric_preview"]["leakage_status"] = "PASS"
    xlsx["diagnostic_metric_preview"]["leakage_count"] = 0
    xlsx["diagnostic_metric_preview"]["clean_pass_rows"] = 23
    xlsx["diagnostic_metric_preview"]["cleanup_rows"] = 0
    paths["xlsx_report"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "DIAGNOSTIC_PREFLIGHT_BLOCKED"
    assert "cross_track_average_value" not in json.dumps(board, ensure_ascii=False)
    assert board["guardrails"]["official_denominator_registry_mutation"] is False
    assert board["guardrails"]["production_namespace_vector_index_mutation"] is False
    assert board["guardrails"]["model_assisted_outputs_promoted_to_gold"] is False
    assert board["validation"]["ok"] is True


def test_board_blocks_when_xlsx_pass_claim_has_nonzero_leakage_count(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_report"].read_text(encoding="utf-8"))
    xlsx["status"] = "DIAGNOSTIC_POLICY_PACKET_READY"
    xlsx["leakage_raw_status"] = "PASS"
    xlsx["leakage_reprobe"] = {"status": "PASS", "surface_leakage_count": 1}
    xlsx["diagnostic_metric_preview"]["leakage_status"] = "PASS"
    xlsx["diagnostic_metric_preview"]["leakage_count"] = 1
    xlsx["diagnostic_metric_preview"]["clean_pass_rows"] = 23
    paths["xlsx_report"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")
    pdf = json.loads(paths["pdf_report"].read_text(encoding="utf-8"))
    pdf["status"] = "READY_FOR_DIAGNOSTIC_STRICT_GATE_RERUN"
    pdf["input_rows"] = 7
    pdf["strict_ready_rows"] = 7
    pdf["strict_gate_rerun"] = {"eligible": True, "rerun_performed": False}
    paths["pdf_report"].write_text(json.dumps(pdf, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "DIAGNOSTIC_PREFLIGHT_BLOCKED"
    assert board["blocker_status"]["xlsx_leakage_blocked"] is True


def test_board_blocks_when_xlsx_top_level_raw_total_is_nonzero(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_report"].read_text(encoding="utf-8"))
    xlsx["status"] = "DIAGNOSTIC_POLICY_PACKET_READY"
    xlsx["leakage_raw_status"] = "PASS"
    xlsx["leakage_raw_total"] = 1
    xlsx["leakage_reprobe"] = {"status": "PASS", "surface_leakage_count": 0}
    xlsx["diagnostic_metric_preview"]["leakage_status"] = "PASS"
    xlsx["diagnostic_metric_preview"]["leakage_count"] = 0
    xlsx["diagnostic_metric_preview"]["clean_pass_rows"] = 23
    paths["xlsx_report"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")
    pdf = json.loads(paths["pdf_report"].read_text(encoding="utf-8"))
    pdf["status"] = "READY_FOR_DIAGNOSTIC_STRICT_GATE_RERUN"
    pdf["input_rows"] = 7
    pdf["strict_ready_rows"] = 7
    pdf["strict_gate_rerun"] = {"eligible": True, "rerun_performed": False}
    paths["pdf_report"].write_text(json.dumps(pdf, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "DIAGNOSTIC_PREFLIGHT_BLOCKED"
    assert board["tracks"]["xlsx_business_structured"]["leakage_count"] == 1
    assert board["blocker_status"]["xlsx_leakage_blocked"] is True


def test_board_blocks_when_pdf_answer_packet_missing_after_pdf_evidence_ready(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_report"].read_text(encoding="utf-8"))
    xlsx["status"] = "DIAGNOSTIC_POLICY_PACKET_READY"
    xlsx["leakage_raw_status"] = "PASS"
    xlsx["leakage_reprobe"] = {"status": "PASS", "surface_leakage_count": 0}
    xlsx["diagnostic_metric_preview"]["leakage_status"] = "PASS"
    xlsx["diagnostic_metric_preview"]["leakage_count"] = 0
    xlsx["diagnostic_metric_preview"]["clean_pass_rows"] = 23
    xlsx["diagnostic_metric_preview"]["cleanup_rows"] = 0
    paths["xlsx_report"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")
    pdf = json.loads(paths["pdf_report"].read_text(encoding="utf-8"))
    pdf["status"] = "READY_FOR_DIAGNOSTIC_STRICT_GATE_RERUN"
    pdf["input_rows"] = 7
    pdf["strict_ready_rows"] = 7
    pdf["strict_gate_rerun"] = {"eligible": True, "rerun_performed": False}
    paths["pdf_report"].write_text(json.dumps(pdf, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "DIAGNOSTIC_PREFLIGHT_BLOCKED_BY_PDF_ANSWER_CITATION"
    assert board["blocker_status"]["xlsx_leakage_blocked"] is False
    assert board["blocker_status"]["pdf_evidence_readiness_blocked"] is False
    assert board["blocker_status"]["pdf_answer_citation_blocked"] is True
    assert "PDF answer/citation diagnostic packet is missing or not ready." in board["remaining_blockers"]


def test_board_reads_pdf_answer_packet_ready_without_blocking_preflight(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    make_xlsx_ready(paths["xlsx_report"])
    make_pdf_readiness_ready(paths["pdf_report"])
    pdf_answer = tmp_path / "pdf_answer_packet.json"
    write_pdf_answer_packet(pdf_answer, status="DIAGNOSTIC_POLICY_PACKET_READY", clean_pass_rows=7, cleanup_rows=0)

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
        pdf_answer_report=pdf_answer,
    )

    assert board["status"] == "DIAGNOSTIC_PREFLIGHT_READY"
    assert board["tracks"]["pdf_business_ocr_mm"]["answer_citation_status"] == "DIAGNOSTIC_POLICY_PACKET_READY"
    assert board["tracks"]["pdf_business_ocr_mm"]["answer_clean_pass_rows"] == 7
    assert board["blocker_status"]["pdf_answer_citation_blocked"] is False
    assert board["official_metric_input_rows_by_track"]["pdf_business_ocr_mm"] == 0


def test_board_marks_completed_human_audit_as_report_only_next_gate(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    make_xlsx_ready(paths["xlsx_report"])
    make_pdf_readiness_ready(paths["pdf_report"])
    pdf_answer = tmp_path / "pdf_answer_packet.json"
    human_audit = tmp_path / "human_audit_v2.json"
    write_pdf_answer_packet(pdf_answer, status="DIAGNOSTIC_POLICY_PACKET_READY", clean_pass_rows=7, cleanup_rows=0)
    human_audit.write_text(
        json.dumps(
            {
                "status": "HUMAN_AUDIT_PACKET_V2_READY",
                "diagnostic_only": True,
                "official_metric": False,
                "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "human_audit_completed": True,
            "summary": {
                "pdf_generated_candidates": 4,
                "xlsx_generated_candidates": 23,
                "official_metric_input_rows": 0,
                "promotion_evidence": False,
            },
            "guardrails": {
                "official_denominator_registry_opened": False,
                "official_denominator_registry_mutation": False,
                "gold_registry_mutation": False,
                "candidate_artifact_mutation": False,
                "production_vector_written": False,
                "tuning_run_started": False,
            },
            "actionable_rows": [
                {
                    "query_id": "pdf_1",
                    "human_label": "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE",
                    "allowed_decision_values": ["INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE"],
                },
                {
                    "query_id": "xlsx_1",
                    "human_label": "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE",
                    "allowed_decision_values": ["INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE"],
                },
            ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
        pdf_answer_report=pdf_answer,
        human_audit_packet=human_audit,
    )

    assert board["status"] == "DIAGNOSTIC_PREFLIGHT_READY"
    assert board["official_question_gold_status"] == "HUMAN_AUDIT_COMPLETED_PENDING_REPORT_ONLY_DECISION_APPLICATION"
    assert board["blocker_status"]["human_audit_completed"] is True
    assert "Human audit decisions must be applied report-only before any official metric candidate can open." in board["remaining_blockers"]
    assert board["guardrails"]["official_metric_input_rows_remain_zero"] is True


def test_board_blocks_when_pdf_answer_packet_is_lane_guard_blocked(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    make_xlsx_ready(paths["xlsx_report"])
    make_pdf_readiness_ready(paths["pdf_report"])
    pdf_answer = tmp_path / "pdf_answer_packet.json"
    write_pdf_answer_packet(
        pdf_answer,
        status="DIAGNOSTIC_POLICY_PACKET_BLOCKED_BY_LANE_OR_EVIDENCE_GUARD",
        clean_pass_rows=6,
        cleanup_rows=0,
        lane_policy_blocked_rows=1,
    )

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
        pdf_answer_report=pdf_answer,
    )

    assert board["status"] == "DIAGNOSTIC_PREFLIGHT_BLOCKED_BY_PDF_ANSWER_CITATION"
    assert board["blocker_status"]["pdf_evidence_readiness_blocked"] is False
    assert board["blocker_status"]["pdf_answer_citation_blocked"] is True
    assert "PDF answer/citation diagnostic packet is missing or not ready." in board["remaining_blockers"]


def test_board_keeps_pdf_blocked_when_only_some_rows_are_strict_ready(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_report"].read_text(encoding="utf-8"))
    xlsx["status"] = "DIAGNOSTIC_POLICY_PACKET_READY"
    xlsx["leakage_raw_status"] = "PASS"
    xlsx["leakage_reprobe"] = {"status": "PASS", "surface_leakage_count": 0}
    xlsx["diagnostic_metric_preview"]["leakage_status"] = "PASS"
    xlsx["diagnostic_metric_preview"]["leakage_count"] = 0
    paths["xlsx_report"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")
    pdf = json.loads(paths["pdf_report"].read_text(encoding="utf-8"))
    pdf["status"] = "EVIDENCE_READINESS_BLOCKED"
    pdf["input_rows"] = 7
    pdf["strict_ready_rows"] = 1
    pdf["strict_gate_rerun"] = {"eligible": False, "rerun_performed": False}
    paths["pdf_report"].write_text(json.dumps(pdf, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "DIAGNOSTIC_PREFLIGHT_BLOCKED"
    assert board["blocker_status"]["pdf_evidence_readiness_blocked"] is True


def test_board_keeps_pdf_blocked_when_partial_rows_claim_rerun_eligible(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_report"].read_text(encoding="utf-8"))
    xlsx["status"] = "DIAGNOSTIC_POLICY_PACKET_READY"
    xlsx["leakage_raw_status"] = "PASS"
    xlsx["leakage_reprobe"] = {"status": "PASS", "surface_leakage_count": 0}
    xlsx["diagnostic_metric_preview"]["leakage_status"] = "PASS"
    xlsx["diagnostic_metric_preview"]["leakage_count"] = 0
    paths["xlsx_report"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")
    pdf = json.loads(paths["pdf_report"].read_text(encoding="utf-8"))
    pdf["status"] = "READY_FOR_STRICT_GATE_RERUN"
    pdf["input_rows"] = 7
    pdf["strict_ready_rows"] = 1
    pdf["strict_gate_rerun"] = {"eligible": True, "rerun_performed": False}
    paths["pdf_report"].write_text(json.dumps(pdf, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "DIAGNOSTIC_PREFLIGHT_BLOCKED"
    assert board["blocker_status"]["pdf_evidence_readiness_blocked"] is True


def test_board_keeps_pdf_blocked_when_zero_input_claims_strict_rows(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_report"].read_text(encoding="utf-8"))
    xlsx["status"] = "DIAGNOSTIC_POLICY_PACKET_READY"
    xlsx["leakage_raw_status"] = "PASS"
    xlsx["leakage_reprobe"] = {"status": "PASS", "surface_leakage_count": 0}
    xlsx["diagnostic_metric_preview"]["leakage_status"] = "PASS"
    xlsx["diagnostic_metric_preview"]["leakage_count"] = 0
    paths["xlsx_report"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")
    pdf = json.loads(paths["pdf_report"].read_text(encoding="utf-8"))
    pdf["status"] = "READY_FOR_DIAGNOSTIC_STRICT_GATE_RERUN"
    pdf["input_rows"] = 0
    pdf["strict_ready_rows"] = 1
    pdf["strict_gate_rerun"] = {"eligible": True, "rerun_performed": False}
    paths["pdf_report"].write_text(json.dumps(pdf, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "DIAGNOSTIC_PREFLIGHT_BLOCKED"
    assert board["blocker_status"]["pdf_evidence_readiness_blocked"] is True


def test_board_refuses_cross_track_average_request(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
        cross_track_averages_requested=True,
    )

    assert board["status"] == "FAILED_GUARDRAIL"
    assert "cross-track averages are not allowed for this diagnostic board" in board["validation"]["errors"]
    assert board["cross_track_averages_computed"] is False
    assert board["official_metric_input_rows_by_track"] == {
        "text_namu_v2_1": 0,
        "xlsx_business_structured": 0,
        "pdf_business_ocr_mm": 0,
    }


def test_board_fails_when_any_track_opens_official_metric_input(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_report"].read_text(encoding="utf-8"))
    xlsx["official_metric_input_rows"] = 1
    paths["xlsx_report"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "FAILED_GUARDRAIL"
    assert "xlsx_business_structured official_metric_input_rows must remain 0" in board["validation"]["errors"]
    assert board["guardrails"]["official_metric_input_rows_remain_zero"] is False


def test_board_fails_when_source_report_validation_is_not_ok(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_report"].read_text(encoding="utf-8"))
    xlsx["validation"] = {"ok": False, "errors": ["upstream xlsx validation failed"]}
    paths["xlsx_report"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "FAILED_GUARDRAIL"
    assert "xlsx_business_structured source validation failed: upstream xlsx validation failed" in board["validation"]["errors"]


def test_board_fails_when_xlsx_preview_opens_official_metric_input(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_report"].read_text(encoding="utf-8"))
    xlsx["diagnostic_metric_preview"]["official_metric_input_rows"] = 1
    paths["xlsx_report"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "FAILED_GUARDRAIL"
    assert board["tracks"]["xlsx_business_structured"]["official_metric_input_rows"] == 1
    assert "xlsx_business_structured official_metric_input_rows must remain 0" in board["validation"]["errors"]


def test_board_fails_when_source_report_opens_official_metric_or_pdf_lane_guardrail(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    pdf = json.loads(paths["pdf_report"].read_text(encoding="utf-8"))
    pdf["official_metric"] = True
    pdf["official_metric_input_rows"] = 2
    pdf["answer_generation_run"] = True
    pdf["counts"]["pdf_answer_generation_denominator"] = 1
    pdf["guardrails"] = {
        "pdf_answer_generation_denominator_opened": True,
        "pdf_content_file_lanes_aggregated": True,
        "production_vector_written": True,
    }
    pdf["lane_separation"]["content_and_file_identity_aggregated"] = True
    paths["pdf_report"].write_text(json.dumps(pdf, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "FAILED_GUARDRAIL"
    assert board["tracks"]["pdf_business_ocr_mm"]["official_metric_input_rows"] == 2
    assert board["tracks"]["pdf_business_ocr_mm"]["answer_denominator_rows"] == 1
    assert "pdf_business_ocr_mm source report must keep official_metric=false" in board["validation"]["errors"]
    assert "pdf_business_ocr_mm answer generation must remain closed" in board["validation"]["errors"]
    assert "pdf content and file identity lanes must not be aggregated" in board["validation"]["errors"]
    assert "pdf_business_ocr_mm source guardrail violation: production_vector_written=true" in board[
        "validation"
    ]["errors"]


def test_board_fails_when_source_reports_registry_or_gold_mutation(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_report"].read_text(encoding="utf-8"))
    xlsx["guardrails"] = {}
    xlsx["guardrails"]["official_denominator_registry_mutation"] = True
    xlsx["guardrails"]["official_denominator_registry_changed"] = True
    xlsx["guardrails"]["gold_registry_mutation"] = True
    paths["xlsx_report"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "FAILED_GUARDRAIL"
    assert board["guardrails"]["official_denominator_registry_mutation"] is True
    assert board["guardrails"]["gold_registry_mutation"] is True
    assert "xlsx_business_structured source guardrail violation: official_denominator_registry_mutation=true" in board[
        "validation"
    ]["errors"]
    assert "xlsx_business_structured source guardrail violation: official_denominator_registry_changed=true" in board[
        "validation"
    ]["errors"]
    assert "xlsx_business_structured source guardrail violation: gold_registry_mutation=true" in board[
        "validation"
    ]["errors"]


def test_board_fails_when_source_guardrails_report_registry_or_gold_mutation(tmp_path: Path):
    module = load_module()
    paths = write_fixture_bundle(tmp_path)
    xlsx = json.loads(paths["xlsx_report"].read_text(encoding="utf-8"))
    xlsx["source_guardrails"] = {
        "official_denominator_registry_opened": True,
        "gold_registry_mutation": True,
    }
    paths["xlsx_report"].write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")

    board = module.build_board(
        text_policy_packet=paths["text_packet"],
        xlsx_answer_report=paths["xlsx_report"],
        pdf_readiness_report=paths["pdf_report"],
    )

    assert board["status"] == "FAILED_GUARDRAIL"
    assert board["guardrails"]["official_denominator_registry_opened"] is True
    assert board["guardrails"]["gold_registry_mutation"] is True
    assert "xlsx_business_structured source guardrail violation: official_denominator_registry_opened=true" in board[
        "validation"
    ]["errors"]
    assert "xlsx_business_structured source guardrail violation: gold_registry_mutation=true" in board[
        "validation"
    ]["errors"]


def write_fixture_bundle(tmp_path: Path) -> dict[str, Path]:
    text_packet = tmp_path / "text_packet.json"
    xlsx_report = tmp_path / "xlsx_report.json"
    pdf_report = tmp_path / "pdf_report.json"
    text_packet.write_text(
        json.dumps(
            {
                "status": "POLICY_REVIEW_PACKET_READY",
                "diagnostic_only": True,
                "not_official_metric": True,
                "guardrails": {
                    "official_metric_input_rows": 0,
                    "promotion_evidence_rows": 0,
                    "official_denominator_registry_mutation": False,
                },
                "diagnostic_metric_preview": {
                    "strict_clean_answer_preview": {"numerator": 60, "denominator": 66},
                    "cleanup_inclusive_answer_preview": {"numerator": 65, "denominator": 66},
                    "citation_supported_preview": {"numerator": 65, "denominator": 66},
                    "official_metric_input_rows": 0,
                    "metric_pass_candidate": True,
                },
                "row_groups": {
                    "cleanup_rows": {"row_count": 5},
                    "unresolved_rows": {"row_count": 1},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    xlsx_report.write_text(
        json.dumps(
            {
                "status": "FAIL",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "official_metric_input_rows": 0,
                "counts": {
                    "generated_review_input_rows": 23,
                    "answer_claim_supported_rows": 23,
                    "citation_locator_resolved_rows": 23,
                },
                "diagnostic_metric_preview": {
                    "generated_answer_rows": 23,
                    "clean_pass_rows": 0,
                    "cleanup_rows": 23,
                    "rewrite_unresolved_rows": 0,
                    "citation_fully_supported_rows": 23,
                    "citation_locator_valid_rows": 23,
                    "leakage_count": 14,
                    "official_metric_input_rows": 0,
                },
                "leakage_reprobe": {"status": "FAIL", "surface_leakage_count": 14},
                "validation": {"ok": False, "errors": ["hidden/excluded leakage reprobe failed"]},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    pdf_report.write_text(
        json.dumps(
            {
                "status": "DIAGNOSTIC_ONLY_BLOCKED",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "answer_generation_run": False,
                "counts": {
                    "input_rows": 7,
                    "rows_with_complete_page_bbox_region": 4,
                    "rows_with_matched_text": 7,
                    "rows_with_nearby_paragraphs": 0,
                    "rows_with_ocr_confidence": 0,
                    "rows_with_ocr_confidence_or_native_text_na": 0,
                    "rows_with_citation_locator": 4,
                    "rows_blocked_by_missing_layout": 7,
                    "rows_blocked_by_file_identity_ambiguity": 3,
                    "strict_gate_readiness_count": 0,
                    "generated_strict_rows_if_rerun": 0,
                },
                "lane_separation": {
                    "content_and_file_identity_aggregated": False,
                    "pdf_content_evidence": {"row_count": 7},
                    "pdf_file_identity": {"blocked_by_stable_identity_required": 3},
                },
                "strict_gate_rerun": {"rerun_performed": False},
                "validation": {"ok": True, "errors": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"text_packet": text_packet, "xlsx_report": xlsx_report, "pdf_report": pdf_report}


def make_xlsx_ready(path: Path) -> None:
    xlsx = json.loads(path.read_text(encoding="utf-8"))
    xlsx["status"] = "DIAGNOSTIC_POLICY_PACKET_READY"
    xlsx["leakage_raw_status"] = "PASS"
    xlsx["leakage_reprobe"] = {"status": "PASS", "surface_leakage_count": 0}
    xlsx["diagnostic_metric_preview"]["leakage_status"] = "PASS"
    xlsx["diagnostic_metric_preview"]["leakage_count"] = 0
    xlsx["diagnostic_metric_preview"]["clean_pass_rows"] = 23
    xlsx["diagnostic_metric_preview"]["cleanup_rows"] = 0
    path.write_text(json.dumps(xlsx, ensure_ascii=False), encoding="utf-8")


def make_pdf_readiness_ready(path: Path) -> None:
    pdf = json.loads(path.read_text(encoding="utf-8"))
    pdf["status"] = "READY_FOR_DIAGNOSTIC_STRICT_GATE_RERUN"
    pdf["input_rows"] = 7
    pdf["strict_ready_rows"] = 7
    pdf["strict_gate_rerun"] = {"eligible": True, "rerun_performed": True}
    path.write_text(json.dumps(pdf, ensure_ascii=False), encoding="utf-8")


def write_pdf_answer_packet(
    path: Path,
    *,
    status: str,
    clean_pass_rows: int,
    cleanup_rows: int,
    lane_policy_blocked_rows: int = 0,
) -> None:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "input_rows": 7,
                "strict_ready_rows": 7,
                "generated_answer_rows": 7,
                "answer_support_pass_count": clean_pass_rows,
                "citation_locator_valid_count": clean_pass_rows,
                "clean_pass_rows": clean_pass_rows,
                "cleanup_rows": cleanup_rows,
                "unresolved_rows": 0,
                "lane_policy_blocked_rows": lane_policy_blocked_rows,
                "official_metric_input_rows": 0,
                "pdf_answer_generation_denominator_opened": False,
                "content_file_identity_lane_merge": False,
                "filename_only_identity_accepted": False,
                "guardrails": {
                    "official_metric_input_rows_remain_zero": True,
                    "official_denominator_registry_opened": False,
                    "official_denominator_registry_mutation": False,
                    "promotion_evidence_created": False,
                },
                "validation": {"ok": True, "errors": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
