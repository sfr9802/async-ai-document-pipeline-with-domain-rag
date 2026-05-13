from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_xlsx_pdf_diagnostic_metric_preview.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_xlsx_pdf_diagnostic_metric_preview_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_metric_preview_keeps_tracks_separate_and_official_inputs_closed(tmp_path: Path):
    module = load_module()
    xlsx_report = tmp_path / "xlsx_report.json"
    xlsx_report.write_text(
        json.dumps(
            {
                "status": "PASS",
                "track": "xlsx_business_structured",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "official_metric_input_rows": 0,
                "counts": {
                    "generated_review_input_rows": 23,
                    "answer_claim_supported_rows": 23,
                    "citation_locator_resolved_rows": 23,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    pdf_report = tmp_path / "pdf_report.json"
    pdf_report.write_text(
        json.dumps(
            {
                "status": "DIAGNOSTIC_ONLY_BLOCKED",
                "track": "pdf_business_ocr_mm",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "counts": {
                    "input_rows": 7,
                    "strict_gate_readiness_count": 0,
                    "rows_blocked_by_missing_layout": 7,
                    "rows_blocked_by_file_identity_ambiguity": 3,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output_json = tmp_path / "preview.json"
    output_md = tmp_path / "preview.md"

    report = module.run_preview(
        xlsx_answer_report=xlsx_report,
        pdf_readiness_report=pdf_report,
        output_report=output_json,
        output_md=output_md,
    )

    assert report["status"] == "PASS"
    assert report["official_metric_input_rows"] == 0
    assert report["cross_track_averages_computed"] is False
    assert report["guardrails"]["official_metric_input_rows_remain_zero"] is True
    assert report["guardrails"]["route_fallback_labels_diagnostic_only"] is True
    assert report["guardrails"]["model_assisted_outputs_promoted_to_gold"] is False
    assert set(report["track_previews"]) == {"xlsx_business_structured", "pdf_business_ocr_mm"}
    assert "cross_track_average_value" not in json.dumps(report, ensure_ascii=False)
    assert output_json.exists()
    assert output_md.exists()


def test_metric_preview_fails_when_source_report_failed(tmp_path: Path):
    module = load_module()
    xlsx_report = tmp_path / "xlsx_report.json"
    xlsx_report.write_text(
        json.dumps(
            {
                "status": "FAIL",
                "track": "xlsx_business_structured",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "official_metric_input_rows": 0,
                "validation": {"ok": False, "errors": ["leakage"]},
                "counts": {"generated_review_input_rows": 23},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    pdf_report = tmp_path / "pdf_report.json"
    pdf_report.write_text(
        json.dumps(
            {
                "status": "DIAGNOSTIC_ONLY_BLOCKED",
                "track": "pdf_business_ocr_mm",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "validation": {"ok": True, "errors": []},
                "counts": {"input_rows": 7, "strict_gate_readiness_count": 0},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = module.run_preview(
        xlsx_answer_report=xlsx_report,
        pdf_readiness_report=pdf_report,
        output_report=tmp_path / "preview.json",
        output_md=tmp_path / "preview.md",
    )

    assert report["status"] == "FAIL"
    assert "xlsx_business_structured source report status is FAIL" in report["validation"]["errors"]


def test_metric_preview_fails_when_pdf_source_opens_answer_or_lane_guardrails(tmp_path: Path):
    module = load_module()
    xlsx_report = tmp_path / "xlsx_report.json"
    xlsx_report.write_text(
        json.dumps(
            {
                "status": "PASS",
                "track": "xlsx_business_structured",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "official_metric_input_rows": 0,
                "validation": {"ok": True, "errors": []},
                "counts": {
                    "generated_review_input_rows": 23,
                    "answer_claim_supported_rows": 23,
                    "citation_locator_resolved_rows": 23,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    pdf_report = tmp_path / "pdf_report.json"
    pdf_report.write_text(
        json.dumps(
            {
                "status": "DIAGNOSTIC_ONLY_BLOCKED",
                "track": "pdf_business_ocr_mm",
                "diagnostic_only": True,
                "official_metric": True,
                "official_metric_input_rows": 3,
                "promotion_evidence": False,
                "answer_generation_run": True,
                "validation": {"ok": True, "errors": []},
                "counts": {
                    "input_rows": 7,
                    "strict_gate_readiness_count": 0,
                    "pdf_answer_generation_denominator": 1,
                },
                "guardrails": {
                    "pdf_answer_generation_denominator_opened": True,
                    "pdf_content_file_lanes_aggregated": True,
                },
                "lane_separation": {"content_and_file_identity_aggregated": True},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = module.run_preview(
        xlsx_answer_report=xlsx_report,
        pdf_readiness_report=pdf_report,
        output_report=tmp_path / "preview.json",
        output_md=tmp_path / "preview.md",
    )

    assert report["status"] == "FAIL"
    assert report["track_previews"]["pdf_business_ocr_mm"]["official_metric_input_rows"] == 3
    assert "pdf_business_ocr_mm source report must keep official_metric=false" in report["validation"]["errors"]
    assert "pdf_business_ocr_mm answer generation must remain closed" in report["validation"]["errors"]
    assert "pdf_business_ocr_mm answer denominator must remain 0" in report["validation"]["errors"]
    assert "pdf_business_ocr_mm content/file identity lanes must remain separate" in report["validation"]["errors"]
