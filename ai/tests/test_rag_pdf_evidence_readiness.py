from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_pdf_evidence_readiness.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_evidence_readiness_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pdf_readiness_keeps_rows_diagnostic_until_layout_ocr_and_source_metadata_exist(tmp_path: Path):
    module = load_module()
    paths = write_pdf_fixture(tmp_path)
    rows_jsonl = tmp_path / "readiness_rows.jsonl"
    report_json = tmp_path / "readiness_report.json"
    report_md = tmp_path / "readiness_report.md"

    report = module.run_readiness(
        pdf_strict_report=paths["pdf_strict_report"],
        pdf_gold_csv=paths["pdf_gold_csv"],
        output_jsonl=rows_jsonl,
        output_report=report_json,
        output_md=report_md,
    )

    assert report["status"] == "DIAGNOSTIC_ONLY_BLOCKED"
    assert report["diagnostic_only"] is True
    assert report["promotion_evidence"] is False
    assert report["answer_generation_run"] is False
    assert report["counts"]["input_rows"] == 2
    assert report["counts"]["rows_with_complete_page_bbox_region"] == 1
    assert report["counts"]["rows_with_matched_text"] == 2
    assert report["counts"]["rows_with_ocr_confidence"] == 0
    assert report["counts"]["rows_with_ocr_confidence_or_native_text_na"] == 0
    assert report["counts"]["rows_with_nearby_paragraphs"] == 0
    assert report["counts"]["rows_with_citation_locator"] == 1
    assert report["counts"]["rows_blocked_by_missing_layout"] == 2
    assert report["counts"]["rows_blocked_by_file_identity_ambiguity"] == 3
    assert report["counts"]["strict_gate_readiness_count"] == 0
    assert report["counts"]["generated_strict_rows_if_rerun"] == 0
    assert report["strict_gate_rerun"]["rerun_performed"] is False
    assert report["lane_separation"]["pdf_content_evidence"]["row_count"] == 2
    assert report["lane_separation"]["pdf_file_identity"]["blocked_by_stable_identity_required"] == 3
    assert report["missing_field_diagnosis"]["source_searchunit_id"]["missing_rows"] == 2
    assert report["missing_field_diagnosis"]["source_searchunit_rank"]["missing_rows"] == 2
    assert report["missing_field_diagnosis"]["parser_source_metadata"]["missing_rows"] == 2
    assert report["missing_field_diagnosis"]["OCR_confidence"]["missing_rows"] == 2

    rows = read_jsonl(rows_jsonl)
    assert len(rows) == 2
    assert all(row["diagnostic_only"] is True for row in rows)
    assert all(row["evidence_lane"] == "pdf_content_evidence" for row in rows)
    assert rows[0]["readiness"]["page_bbox_region_complete"] is True
    assert rows[0]["readiness"]["matched_text_present"] is True
    assert rows[0]["readiness"]["OCR_confidence_or_native_text_na"] is False
    assert rows[0]["citation_metadata"]["OCR_confidence_status"] == "missing"
    assert "source_searchunit_id" in rows[0]["missing_context_fields"]
    assert "source_searchunit_rank" in rows[0]["missing_context_fields"]
    assert "parser_source_metadata" in rows[0]["missing_context_fields"]
    assert "OCR_confidence" in rows[0]["missing_context_fields"]
    assert rows[1]["readiness"]["page_bbox_region_complete"] is False
    assert "bbox" in rows[1]["missing_context_fields"]


def test_pdf_readiness_can_fallback_when_strict_json_report_is_missing(tmp_path: Path):
    module = load_module()
    paths = write_pdf_fixture(tmp_path)
    paths["pdf_strict_report"].unlink()

    report = module.build_report(
        pdf_strict_report=paths["pdf_strict_report"],
        pdf_gold_csv=paths["pdf_gold_csv"],
    )

    assert report["status"] == "DIAGNOSTIC_ONLY_BLOCKED"
    assert report["source_artifacts"]["pdf_strict_report"]["exists"] is False
    assert report["source_artifacts"]["pdf_strict_report_fallback_used"] is True
    assert report["counts"]["input_rows"] == 2


def test_generic_filename_identity_stays_blocked_with_stable_identity_required(tmp_path: Path):
    module = load_module()
    paths = write_pdf_fixture(tmp_path)

    report = module.build_report(
        pdf_strict_report=paths["pdf_strict_report"],
        pdf_gold_csv=paths["pdf_gold_csv"],
    )

    assert report["file_identity_policy"]["generic_filename_only_identity_blocked"] is True
    assert report["file_identity_policy"]["blocker"] == "stable_identity_required"
    assert report["counts"]["rows_blocked_by_file_identity_ambiguity"] == 3
    assert report["guardrails"]["pdf_content_file_lanes_aggregated"] is False
    assert report["guardrails"]["pdf_answer_generation_opened"] is False


def test_pdf_readiness_fails_on_upstream_protected_guardrail(tmp_path: Path):
    module = load_module()
    paths = write_pdf_fixture(tmp_path)
    payload = json.loads(paths["pdf_strict_report"].read_text(encoding="utf-8"))
    payload["guardrails"]["official_denominator_registry_changed"] = True
    paths["pdf_strict_report"].write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = module.build_report(
        pdf_strict_report=paths["pdf_strict_report"],
        pdf_gold_csv=paths["pdf_gold_csv"],
    )

    assert report["status"] == "FAILED_GUARDRAIL"
    assert report["source_guardrails"]["official_denominator_registry_changed"] is True
    assert "strict guardrail violation: official_denominator_registry_changed=true" in report["validation"]["errors"]


def test_pdf_readiness_derives_guardrail_from_answer_denominator_count(tmp_path: Path):
    module = load_module()
    paths = write_pdf_fixture(tmp_path)
    payload = json.loads(paths["pdf_strict_report"].read_text(encoding="utf-8"))
    payload["counts"]["pdf_answer_generation_denominator"] = 5
    payload["official_metric"] = True
    payload["official_metric_input_rows"] = 2
    paths["pdf_strict_report"].write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = module.build_report(
        pdf_strict_report=paths["pdf_strict_report"],
        pdf_gold_csv=paths["pdf_gold_csv"],
    )

    assert report["status"] == "FAILED_GUARDRAIL"
    assert report["source_guardrails"]["pdf_answer_generation_denominator_opened"] is True
    assert report["source_guardrails"]["official_denominator_opened_or_frozen"] is True
    assert "strict guardrail violation: pdf_answer_generation_denominator_opened=true" in report[
        "validation"
    ]["errors"]


def write_pdf_fixture(tmp_path: Path) -> dict[str, Path]:
    pdf_gold_csv = tmp_path / "gold_queries_pdf_v0.csv"
    fieldnames = [
        "query_id",
        "query",
        "expected_file_name",
        "expected_document_version_id",
        "expected_chunk_type",
        "expected_physical_page_index",
        "expected_page_no",
        "expected_bbox",
        "expected_answer_text",
        "must_contain_terms",
    ]
    with pdf_gold_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "query_id": "gq_pdf_page_lookup_001",
                "query": "표지 찾아줘",
                "expected_file_name": "sample.pdf",
                "expected_document_version_id": "docv1",
                "expected_chunk_type": "paragraph",
                "expected_physical_page_index": "0",
                "expected_page_no": "1",
                "expected_bbox": "[1, 2, 3, 4]",
                "expected_answer_text": "표지",
                "must_contain_terms": "표지",
            }
        )
        writer.writerow(
            {
                "query_id": "gq_auto_010",
                "query": "문장 찾아줘",
                "expected_file_name": "sample.pdf",
                "expected_document_version_id": "docv1",
                "expected_chunk_type": "page",
                "expected_physical_page_index": "7",
                "expected_page_no": "8",
                "expected_bbox": "",
                "expected_answer_text": "문장",
                "must_contain_terms": "문장",
            }
        )
    pdf_strict_report = tmp_path / "pdf_strict_report.json"
    pdf_strict_report.write_text(
        json.dumps(
            {
                "status": "COMPLETED_DIAGNOSTIC_ONLY",
                "counts": {
                    "input_denominator_row_count": 2,
                    "generated_silver_row_count": 0,
                    "diagnostic_only_fallback_row_count": 2,
                    "stable_identity_required_row_count": 3,
                    "pdf_answer_generation_denominator": 0,
                },
                "input_denominator_query_ids": ["gq_pdf_page_lookup_001", "gq_auto_010"],
                "excluded_query_ids": {
                    "stable_identity_required": [
                        "pdf_file_lookup_content_anchor_017",
                        "pdf_file_lookup_content_anchor_018",
                        "pdf_file_lookup_content_anchor_020",
                    ]
                },
                "lane_separation": {
                    "content_evidence_lane": "pdf_content_evidence",
                    "file_identity_lane": "pdf_file_identity",
                    "content_and_file_identity_aggregated": False,
                },
                "guardrails": {
                    "promotion_evidence_created": False,
                    "pdf_answer_generation_denominator_opened": False,
                    "pdf_content_file_lanes_aggregated": False,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"pdf_gold_csv": pdf_gold_csv, "pdf_strict_report": pdf_strict_report}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
