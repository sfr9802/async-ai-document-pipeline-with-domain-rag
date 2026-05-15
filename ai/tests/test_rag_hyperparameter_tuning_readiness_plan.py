from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_hyperparameter_tuning_readiness_plan.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_hyperparameter_tuning_readiness_plan_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_readiness_plan_is_report_only_and_keeps_official_metrics_closed(tmp_path: Path):
    module = load_module()
    board = write_board_fixture(tmp_path, xlsx_leakage="FAIL", pdf_strict_ready=0)

    plan = module.run_plan(
        metric_board=board,
        output_report=tmp_path / "hyperparameter_tuning_readiness_plan.json",
        output_md=tmp_path / "hyperparameter_tuning_readiness_plan.md",
    )

    assert plan["status"] == "REPORT_ONLY_PRE_TUNING_READINESS_BLOCKED"
    assert plan["tuning_run_started"] is False
    assert plan["official_metrics_closed"] is True
    assert plan["cross_track_average_optimization_allowed"] is False
    assert plan["current_text_66_rows_policy"] == "diagnostic_dev_not_final_holdout"
    assert plan["guardrails"]["official_denominator_registry_mutation"] is False
    assert plan["guardrails"]["production_namespace_vector_index_mutation"] is False
    assert plan["guardrails"]["candidate_artifact_mutation"] is False
    assert plan["guardrails"]["official_metric_input_rows"] == 0
    assert plan["guardrails"]["promotion_evidence"] is False
    assert plan["validation"]["ok"] is True
    assert set(plan["track_policies"]) == {
        "text_namu_v2_1",
        "xlsx_business_structured",
        "pdf_business_ocr_mm",
    }
    assert plan["track_policies"]["text_namu_v2_1"]["readiness_status"] == "FROZEN_DIAGNOSTIC_V2_1"
    assert plan["track_policies"]["xlsx_business_structured"]["readiness_status"] == "REPORT_ONLY_BLOCKED_BY_LEAKAGE"
    assert plan["track_policies"]["pdf_business_ocr_mm"]["readiness_status"] == "REPORT_ONLY_BLOCKED_BY_EVIDENCE_READINESS"
    assert "REPORT_ONLY_READY" not in json.dumps(plan, ensure_ascii=False)


def test_readiness_plan_has_track_specific_dev_holdout_and_allowed_parameters():
    module = load_module()

    plan = module.build_plan(metric_board_payload={})

    assert plan["track_policies"]["text_namu_v2_1"]["dev_policy"] == "diagnostic_dev_only"
    assert plan["track_policies"]["text_namu_v2_1"]["holdout_policy"] == "not_final_holdout"
    assert "rewrite_formatter_mode" in plan["track_policies"]["text_namu_v2_1"]["allowed_parameters"]
    assert plan["track_policies"]["xlsx_business_structured"]["holdout_policy"] == "strict_silver_not_official_holdout"
    assert "structured_evidence_field_subset" in plan["track_policies"]["xlsx_business_structured"]["allowed_parameters"]
    assert plan["track_policies"]["pdf_business_ocr_mm"]["dev_policy"] == "readiness_artifact_only"
    assert plan["track_policies"]["pdf_business_ocr_mm"]["allowed_parameters"] == [
        "layout_metadata_completeness_threshold",
        "citation_locator_required_fields",
        "stable_identity_policy_variant_report_only",
    ]


def test_plan_ready_keeps_human_audit_as_only_transition_blocker(tmp_path: Path):
    module = load_module()
    board = write_board_fixture(tmp_path, xlsx_leakage="PASS", pdf_strict_ready=7)
    payload = json.loads(board.read_text(encoding="utf-8"))
    payload["status"] = "DIAGNOSTIC_PREFLIGHT_READY"
    payload["blocker_status"] = {
        "xlsx_leakage_blocked": False,
        "pdf_evidence_readiness_blocked": False,
        "pdf_answer_citation_blocked": False,
    }
    payload["tracks"]["pdf_business_ocr_mm"]["answer_citation_status"] = "DIAGNOSTIC_POLICY_PACKET_READY"
    board.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    plan = module.run_plan(
        metric_board=board,
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
    )

    assert plan["status"] == "REPORT_ONLY_READY"
    assert plan["tuning_run_started"] is False
    assert plan["official_metrics_closed"] is True
    assert plan["official_metric_input_rows"] == 0
    assert plan["cross_track_average_optimization_allowed"] is False
    assert plan["technical_readiness_blockers"] == []
    assert plan["readiness_blockers"] == ["human_audit_required_before_official_metric_open"]
    assert plan["official_transition_blockers"] == ["human_audit_required_before_official_metric_open"]


def test_plan_fails_closed_if_a_guardrail_requests_mutation():
    module = load_module()

    plan = module.build_plan(
        guardrail_overrides={
            "official_denominator_registry_mutation": True,
            "production_namespace_vector_index_mutation": True,
        }
    )

    assert plan["status"] == "FAILED_GUARDRAIL"
    assert "official_denominator_registry_mutation must remain false" in plan["validation"]["errors"]
    assert "production_namespace_vector_index_mutation must remain false" in plan["validation"]["errors"]


def test_plan_keeps_tuning_run_false_even_when_board_is_blocked(tmp_path: Path):
    module = load_module()
    board = write_board_fixture(tmp_path, xlsx_leakage="FAIL", pdf_strict_ready=0)

    plan = module.run_plan(
        metric_board=board,
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
    )

    assert plan["tuning_run_started"] is False
    assert plan["official_metrics_closed"] is True
    assert plan["cross_track_average_optimization_allowed"] is False
    assert plan["guardrails"]["official_metric_input_rows"] == 0
    assert plan["readiness_blockers"] == [
        "xlsx_business_structured leakage_raw_status=FAIL",
        "pdf_business_ocr_mm evidence_readiness_blocked",
        "human_audit_required_before_official_metric_open",
    ]
    assert plan["technical_readiness_blockers"] == [
        "xlsx_business_structured leakage_raw_status=FAIL",
        "pdf_business_ocr_mm evidence_readiness_blocked",
    ]


def test_plan_blocks_top_level_on_xlsx_leakage_even_when_pdf_ready(tmp_path: Path):
    module = load_module()
    board = write_board_fixture(tmp_path, xlsx_leakage="FAIL", pdf_strict_ready=7)

    plan = module.run_plan(
        metric_board=board,
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
    )

    assert plan["status"] != "REPORT_ONLY_READY"
    assert plan["status"] == "REPORT_ONLY_PRE_TUNING_READINESS_BLOCKED"
    assert plan["readiness_blockers"] == [
        "xlsx_business_structured leakage_raw_status=FAIL",
        "human_audit_required_before_official_metric_open",
    ]
    assert plan["tuning_run_started"] is False


def test_plan_blocks_top_level_on_pdf_zero_strict_rows_even_when_xlsx_passes(tmp_path: Path):
    module = load_module()
    board = write_board_fixture(tmp_path, xlsx_leakage="PASS", pdf_strict_ready=0)

    plan = module.run_plan(
        metric_board=board,
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
    )

    assert plan["status"] != "REPORT_ONLY_READY"
    assert plan["status"] == "REPORT_ONLY_PRE_TUNING_READINESS_BLOCKED"
    assert plan["readiness_blockers"] == [
        "pdf_business_ocr_mm evidence_readiness_blocked",
        "human_audit_required_before_official_metric_open",
    ]
    assert plan["tuning_run_started"] is False


def test_plan_blocks_when_metric_board_failed_guardrail(tmp_path: Path):
    module = load_module()
    board = write_board_fixture(tmp_path, xlsx_leakage="PASS", pdf_strict_ready=7)
    payload = json.loads(board.read_text(encoding="utf-8"))
    payload["status"] = "FAILED_GUARDRAIL"
    payload["validation"] = {"ok": False, "errors": ["cross-track averages are not allowed"]}
    board.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    plan = module.run_plan(
        metric_board=board,
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
    )

    assert plan["status"] == "FAILED_GUARDRAIL"
    assert "metric board status is FAILED_GUARDRAIL" in plan["validation"]["errors"]
    assert "metric board validation failed: cross-track averages are not allowed" in plan["validation"]["errors"]


def test_plan_fails_when_metric_board_reports_gold_registry_mutation(tmp_path: Path):
    module = load_module()
    board = write_board_fixture(tmp_path, xlsx_leakage="PASS", pdf_strict_ready=7)
    payload = json.loads(board.read_text(encoding="utf-8"))
    payload["guardrails"]["gold_registry_mutation"] = True
    board.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    plan = module.run_plan(
        metric_board=board,
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
    )

    assert plan["status"] == "FAILED_GUARDRAIL"
    assert plan["tuning_run_started"] is False
    assert plan["guardrails"]["gold_registry_mutation"] is True
    assert "metric board guardrail gold_registry_mutation must remain false" in plan["validation"]["errors"]


def test_plan_consumes_pdf_board_blocker_even_when_partial_strict_rows_exist(tmp_path: Path):
    module = load_module()
    board = write_board_fixture(tmp_path, xlsx_leakage="PASS", pdf_strict_ready=1)
    payload = json.loads(board.read_text(encoding="utf-8"))
    payload["status"] = "DIAGNOSTIC_PREFLIGHT_BLOCKED_BY_PDF_EVIDENCE_READINESS"
    payload["blocker_status"] = {
        "xlsx_leakage_blocked": False,
        "pdf_evidence_readiness_blocked": True,
    }
    payload["tracks"]["pdf_business_ocr_mm"]["input_rows"] = 7
    payload["tracks"]["pdf_business_ocr_mm"]["strict_gate_rerun_eligible"] = True
    board.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    plan = module.run_plan(
        metric_board=board,
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
    )

    assert plan["status"] == "REPORT_ONLY_PRE_TUNING_READINESS_BLOCKED"
    assert plan["track_policies"]["pdf_business_ocr_mm"]["readiness_status"] == (
        "REPORT_ONLY_BLOCKED_BY_EVIDENCE_READINESS"
    )
    assert plan["readiness_blockers"] == [
        "pdf_business_ocr_mm evidence_readiness_blocked",
        "human_audit_required_before_official_metric_open",
    ]


def test_plan_blocks_malformed_pdf_zero_input_positive_strict_rows(tmp_path: Path):
    module = load_module()
    board = write_board_fixture(tmp_path, xlsx_leakage="PASS", pdf_strict_ready=1)
    payload = json.loads(board.read_text(encoding="utf-8"))
    payload["status"] = "DIAGNOSTIC_PREFLIGHT_READY"
    payload["blocker_status"] = {
        "xlsx_leakage_blocked": False,
        "pdf_evidence_readiness_blocked": False,
    }
    payload["tracks"]["pdf_business_ocr_mm"]["input_rows"] = 0
    payload["tracks"]["pdf_business_ocr_mm"]["strict_gate_rerun_eligible"] = True
    board.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    plan = module.run_plan(
        metric_board=board,
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
    )

    assert plan["status"] == "REPORT_ONLY_PRE_TUNING_READINESS_BLOCKED"
    assert plan["track_policies"]["pdf_business_ocr_mm"]["readiness_status"] == (
        "REPORT_ONLY_BLOCKED_BY_EVIDENCE_READINESS"
    )
    assert plan["readiness_blockers"] == [
        "pdf_business_ocr_mm evidence_readiness_blocked",
        "human_audit_required_before_official_metric_open",
    ]


def test_plan_recomputes_xlsx_leakage_fail_even_if_board_claims_ready(tmp_path: Path):
    module = load_module()
    board = write_board_fixture(tmp_path, xlsx_leakage="FAIL", pdf_strict_ready=7)
    payload = json.loads(board.read_text(encoding="utf-8"))
    payload["status"] = "DIAGNOSTIC_PREFLIGHT_READY"
    payload["blocker_status"] = {
        "xlsx_leakage_blocked": False,
        "pdf_evidence_readiness_blocked": False,
    }
    board.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    plan = module.run_plan(
        metric_board=board,
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
    )

    assert plan["status"] == "REPORT_ONLY_PRE_TUNING_READINESS_BLOCKED"
    assert plan["track_policies"]["xlsx_business_structured"]["readiness_status"] == (
        "REPORT_ONLY_BLOCKED_BY_LEAKAGE"
    )
    assert "REPORT_ONLY_READY" not in json.dumps(plan, ensure_ascii=False)


def test_plan_blocks_when_pdf_answer_citation_packet_is_blocked(tmp_path: Path):
    module = load_module()
    board = write_board_fixture(tmp_path, xlsx_leakage="PASS", pdf_strict_ready=7)
    payload = json.loads(board.read_text(encoding="utf-8"))
    payload["status"] = "DIAGNOSTIC_PREFLIGHT_BLOCKED_BY_PDF_ANSWER_CITATION"
    payload["blocker_status"] = {
        "xlsx_leakage_blocked": False,
        "pdf_evidence_readiness_blocked": False,
        "pdf_answer_citation_blocked": True,
    }
    payload["tracks"]["pdf_business_ocr_mm"]["answer_citation_status"] = (
        "DIAGNOSTIC_POLICY_PACKET_BLOCKED_BY_LANE_OR_EVIDENCE_GUARD"
    )
    board.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    plan = module.run_plan(
        metric_board=board,
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
    )

    assert plan["status"] == "REPORT_ONLY_PRE_TUNING_READINESS_BLOCKED"
    assert plan["track_policies"]["pdf_business_ocr_mm"]["readiness_status"] == (
        "REPORT_ONLY_BLOCKED_BY_ANSWER_CITATION"
    )
    assert plan["readiness_blockers"] == [
        "pdf_business_ocr_mm answer_citation_blocked",
        "human_audit_required_before_official_metric_open",
    ]


def test_plan_recomputes_xlsx_nonzero_leakage_count_even_if_board_claims_ready(tmp_path: Path):
    module = load_module()
    board = write_board_fixture(tmp_path, xlsx_leakage="PASS", pdf_strict_ready=7)
    payload = json.loads(board.read_text(encoding="utf-8"))
    payload["status"] = "DIAGNOSTIC_PREFLIGHT_READY"
    payload["blocker_status"] = {
        "xlsx_leakage_blocked": False,
        "pdf_evidence_readiness_blocked": False,
    }
    payload["tracks"]["xlsx_business_structured"]["leakage_count"] = 1
    board.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    plan = module.run_plan(
        metric_board=board,
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
    )

    assert plan["status"] == "REPORT_ONLY_PRE_TUNING_READINESS_BLOCKED"
    assert plan["track_policies"]["xlsx_business_structured"]["readiness_status"] == (
        "REPORT_ONLY_BLOCKED_BY_LEAKAGE"
    )
    assert plan["readiness_blockers"] == [
        "xlsx_business_structured leakage_raw_status=FAIL",
        "human_audit_required_before_official_metric_open",
    ]


def test_plan_recomputes_pdf_zero_strict_rows_even_if_board_claims_ready(tmp_path: Path):
    module = load_module()
    board = write_board_fixture(tmp_path, xlsx_leakage="PASS", pdf_strict_ready=0)
    payload = json.loads(board.read_text(encoding="utf-8"))
    payload["status"] = "DIAGNOSTIC_PREFLIGHT_READY"
    payload["blocker_status"] = {
        "xlsx_leakage_blocked": False,
        "pdf_evidence_readiness_blocked": False,
    }
    payload["tracks"]["pdf_business_ocr_mm"]["strict_gate_rerun_eligible"] = True
    board.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    plan = module.run_plan(
        metric_board=board,
        output_report=tmp_path / "plan.json",
        output_md=tmp_path / "plan.md",
    )

    assert plan["status"] == "REPORT_ONLY_PRE_TUNING_READINESS_BLOCKED"
    assert plan["track_policies"]["pdf_business_ocr_mm"]["readiness_status"] == (
        "REPORT_ONLY_BLOCKED_BY_EVIDENCE_READINESS"
    )
    assert "REPORT_ONLY_READY" not in json.dumps(plan, ensure_ascii=False)


def write_board_fixture(tmp_path: Path, *, xlsx_leakage: str, pdf_strict_ready: int) -> Path:
    board = tmp_path / "three_track_metric_preflight_board.json"
    board.write_text(
        json.dumps(
            {
                "status": "DIAGNOSTIC_PREFLIGHT_BLOCKED",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "official_metric_input_rows_by_track": {
                    "text_namu_v2_1": 0,
                    "xlsx_business_structured": 0,
                    "pdf_business_ocr_mm": 0,
                },
                "tracks": {
                    "text_namu_v2_1": {"official_metric_input_rows": 0},
                    "xlsx_business_structured": {
                        "official_metric_input_rows": 0,
                        "leakage_status": xlsx_leakage,
                    },
                    "pdf_business_ocr_mm": {
                        "official_metric_input_rows": 0,
                        "input_rows": 7,
                        "strict_gate_readiness_count": pdf_strict_ready,
                        "strict_gate_rerun_eligible": pdf_strict_ready == 7,
                    },
                },
                "blocker_status": {
                    "xlsx_leakage_blocked": xlsx_leakage != "PASS",
                    "pdf_evidence_readiness_blocked": pdf_strict_ready != 7,
                },
                "guardrails": {"official_metric_input_rows_remain_zero": True},
                "validation": {"ok": True, "errors": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return board
