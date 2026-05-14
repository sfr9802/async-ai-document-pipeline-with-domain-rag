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
    assert board["cross_track_averages_computed"] is False
    assert "cross_track_average_value" not in json.dumps(board, ensure_ascii=False)
    assert board["route_fallback_label_status"]["route_labels"] == "diagnostic_only"
    assert board["route_fallback_label_status"]["fallback_labels"] == "diagnostic_only"
    assert board["guardrails"]["official_denominator_registry_mutation"] is False
    assert board["guardrails"]["production_namespace_vector_index_mutation"] is False
    assert board["guardrails"]["model_assisted_outputs_promoted_to_gold"] is False
    assert board["validation"]["ok"] is True


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
