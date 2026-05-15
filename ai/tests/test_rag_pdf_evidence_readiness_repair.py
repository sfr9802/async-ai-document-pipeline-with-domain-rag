from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_pdf_evidence_readiness_repair.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_evidence_readiness_repair_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pdf_repair_blocks_missing_source_unit_parser_metadata_and_filename_identity(tmp_path: Path):
    module = load_module()
    paths = write_fixture(tmp_path)

    report = module.run_repair(
        readiness_report=paths["readiness_report"],
        readiness_rows=paths["readiness_rows"],
        output_report=tmp_path / "repair.json",
        output_md=tmp_path / "repair.md",
    )

    assert report["status"] == "EVIDENCE_READINESS_BLOCKED"
    assert report["input_rows"] == 2
    assert report["complete_page_bbox_region_count"] == 1
    assert report["matched_text_count"] == 2
    assert report["nearby_paragraph_count"] == 1
    assert report["OCR_confidence_available_count"] == 1
    assert report["native_text_available_count"] == 1
    assert report["citation_locator_complete_count"] == 1
    assert report["search_unit_id_available_count"] == 1
    assert report["parser_source_metadata_available_count"] == 1
    assert report["file_identity_ambiguous_count"] == 3
    assert report["strict_ready_rows"] == 1
    assert report["generated_strict_silver_rows"] == 1
    assert report["diagnostic_only_fallback_rows"] == 1
    assert report["blocked_by_missing_layout_count"] == 1
    assert report["blocked_by_missing_page_bbox_region_count"] == 1
    assert report["blocked_by_missing_context_metadata_count"] == 1
    assert report["blocked_by_missing_layout_or_context_metadata_count"] == 1
    assert report["blocked_by_missing_source_unit_count"] == 1
    assert report["blocked_by_file_identity_count"] == 3
    assert report["official_metric_input_rows"] == 0
    assert report["answer_generation_opened"] is False
    assert report["promotion_evidence"] is False
    assert report["strict_gate_rerun"]["rerun_performed"] is False
    assert report["lane_separation"]["content_and_file_identity_aggregated"] is False

    rows = {row["query_id"]: row for row in report["repair_rows"]}
    assert rows["ready_001"]["content_evidence_lane"] == "pdf_content_evidence"
    assert rows["ready_001"]["file_identity_lane"]["merged_with_content_evidence"] is False
    assert rows["ready_001"]["source_file_id"] == "sf-ready"
    assert rows["ready_001"]["extracted_artifact_id"] == "artifact-ready"
    assert rows["ready_001"]["document_version_id"] == "docv1"
    assert rows["ready_001"]["native_text_available"] is True
    assert rows["ready_001"]["OCR_fallback_used"] is False
    assert rows["ready_001"]["source_bound_bbox"] is True
    assert rows["ready_001"]["bbox_source"] == "parser_block_bbox"
    assert rows["ready_001"]["layout_resolution_method"] == "exact_parser_block_bbox"
    assert rows["ready_001"]["blocker_classifications"] == ["strict_ready_diagnostic_only"]
    assert rows["blocked_001"]["strict_ready"] is False
    assert "missing_search_unit_id" in rows["blocked_001"]["blocked_reasons"]
    assert "missing_parser_source_metadata" in rows["blocked_001"]["blocked_reasons"]
    assert "missing_or_incomplete_citation_locator" in rows["blocked_001"]["blocked_reasons"]
    assert "blocked_missing_search_unit" in rows["blocked_001"]["blocker_classifications"]
    assert "blocked_missing_parser_source_metadata" in rows["blocked_001"]["blocker_classifications"]
    assert "blocked_missing_layout_bbox_region" in rows["blocked_001"]["blocker_classifications"]
    assert "blocked_missing_nearby_paragraphs" in rows["blocked_001"]["blocker_classifications"]
    assert "blocked_missing_ocr_or_native_text_trust" in rows["blocked_001"]["blocker_classifications"]
    assert "blocked_unresolved_source_artifact" in rows["blocked_001"]["blocker_classifications"]
    assert "diagnostic_only_fallback" in rows["blocked_001"]["blocker_classifications"]
    assert report["file_identity_policy"]["blocker"] == "stable_identity_required"
    assert report["terminology"]["blocked_by_missing_layout_count"] == (
        "backward-compatible alias for blocked_by_missing_layout_or_context_metadata_count"
    )
    assert report["terminology"]["blocked_by_missing_page_bbox_region_count"] == (
        "rows missing page, bbox, or region_type"
    )


def test_pdf_repair_fails_on_source_guardrail_or_unsafe_file_identity(tmp_path: Path):
    module = load_module()
    paths = write_fixture(tmp_path)
    payload = json.loads(paths["readiness_report"].read_text(encoding="utf-8"))
    payload["source_guardrails"]["production_vector_written"] = True
    payload["file_identity_policy"]["generic_filename_only_identity_blocked"] = False
    payload["file_identity_policy"]["filename_only_identity_accepted"] = True
    paths["readiness_report"].write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = module.build_repair(
        readiness_report=paths["readiness_report"],
        readiness_rows=paths["readiness_rows"],
    )

    assert report["status"] == "FAILED_GUARDRAIL"
    assert "source guardrail violation: production_vector_written=true" in report["validation"]["errors"]
    assert "filename-only PDF identity must remain blocked" in report["validation"]["errors"]
    assert report["guardrails"]["production_vector_written"] is True


def test_pdf_repair_requires_source_bound_bbox_for_strict_ready(tmp_path: Path):
    module = load_module()
    paths = write_fixture(tmp_path)
    rows = [json.loads(line) for line in paths["readiness_rows"].read_text(encoding="utf-8").splitlines() if line]
    rows[0]["citation_metadata"].pop("source_bound_bbox")
    rows[0]["citation_metadata"].pop("bbox_source")
    rows[0]["citation_metadata"].pop("layout_resolution_method")
    paths["readiness_rows"].write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    report = module.build_repair(
        readiness_report=paths["readiness_report"],
        readiness_rows=paths["readiness_rows"],
    )

    ready_row = next(row for row in report["repair_rows"] if row["query_id"] == "ready_001")
    assert ready_row["strict_ready"] is False
    assert "missing_source_bound_bbox" in ready_row["blocked_reasons"]
    assert "blocked_missing_source_bound_bbox" in ready_row["blocker_classifications"]
    assert report["strict_ready_rows"] == 0
    assert report["diagnostic_only_fallback_rows"] == 2


def test_pdf_repair_infers_source_bound_bbox_from_source_location_json(tmp_path: Path):
    module = load_module()
    paths = write_fixture(tmp_path)
    rows = [json.loads(line) for line in paths["readiness_rows"].read_text(encoding="utf-8").splitlines() if line]
    metadata = rows[0]["citation_metadata"]
    metadata.pop("source_bound_bbox")
    metadata.pop("bbox_source")
    metadata.pop("layout_resolution_method")
    metadata["parser_source_metadata"] = {
        "parser_version": "pdf-native-v1",
        "source": "native_text",
        "location_json": {"bbox": [1, 2, 3, 4]},
    }
    paths["readiness_rows"].write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    report = module.build_repair(
        readiness_report=paths["readiness_report"],
        readiness_rows=paths["readiness_rows"],
    )

    ready_row = next(row for row in report["repair_rows"] if row["query_id"] == "ready_001")
    assert ready_row["strict_ready"] is True
    assert ready_row["source_bound_bbox"] is True
    assert ready_row["bbox_source"] == "local_db.search_unit.location_json.bbox"
    assert ready_row["layout_resolution_method"] == "existing_source_metadata_location_json_bbox"


def test_pdf_repair_next_actions_shift_to_answer_packet_when_all_rows_strict_ready(tmp_path: Path):
    module = load_module()
    paths = write_fixture(tmp_path)
    rows = [json.loads(line) for line in paths["readiness_rows"].read_text(encoding="utf-8").splitlines() if line]
    rows = [rows[0]]
    paths["readiness_rows"].write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    report = module.build_repair(
        readiness_report=paths["readiness_report"],
        readiness_rows=paths["readiness_rows"],
    )

    joined = "\n".join(report["next_safe_actions"])
    assert report["strict_ready_rows"] == report["input_rows"]
    assert "PDF evidence readiness is complete for 7 diagnostic rows." in joined
    assert "Next safe action is answer/citation diagnostic or human audit depending on the current stage." in joined
    assert "Populate SearchUnit id/rank" not in joined


def test_pdf_repair_fails_when_source_or_rows_open_official_metric_input(tmp_path: Path):
    module = load_module()
    paths = write_fixture(tmp_path)
    payload = json.loads(paths["readiness_report"].read_text(encoding="utf-8"))
    payload["official_metric_input_rows"] = 1
    paths["readiness_report"].write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    rows = [json.loads(line) for line in paths["readiness_rows"].read_text(encoding="utf-8").splitlines() if line]
    rows[0]["official_metric_input"] = True
    paths["readiness_rows"].write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    report = module.build_repair(
        readiness_report=paths["readiness_report"],
        readiness_rows=paths["readiness_rows"],
    )

    assert report["status"] == "FAILED_GUARDRAIL"
    assert report["official_metric_input_rows"] > 0
    assert "official_metric_input_rows must remain 0" in report["validation"]["errors"]
    assert "ready_001 official_metric_input must be false" in report["validation"]["errors"]


def write_fixture(tmp_path: Path) -> dict[str, Path]:
    readiness_report = tmp_path / "readiness_report.json"
    readiness_rows = tmp_path / "readiness_rows.jsonl"
    readiness_report.write_text(
        json.dumps(
            {
                "status": "DIAGNOSTIC_ONLY_BLOCKED",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "answer_generation_run": False,
                "counts": {
                    "input_rows": 2,
                    "rows_blocked_by_file_identity_ambiguity": 3,
                    "official_metric_input_rows": 0,
                },
                "file_identity_policy": {
                    "generic_filename_only_identity_blocked": True,
                    "blocker": "stable_identity_required",
                    "blocked_query_ids": ["file_a", "file_b", "file_c"],
                },
                "lane_separation": {
                    "content_and_file_identity_aggregated": False,
                    "pdf_content_evidence": {"row_count": 2},
                    "pdf_file_identity": {"blocked_by_stable_identity_required": 3},
                },
                "source_guardrails": {
                    "answer_generation_run": False,
                    "official_denominator_opened_or_frozen": False,
                    "promotion_evidence_created": False,
                },
                "validation": {"ok": True, "errors": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rows = [
        {
            "query_id": "ready_001",
            "diagnostic_only": True,
            "official_metric_input": False,
            "promotion_evidence": False,
            "citation_metadata": {
                "file": "sample.pdf",
                "source_file_id": "sf-ready",
                "extracted_artifact_id": "artifact-ready",
                "document_version_id": "docv1",
                "page": 2,
                "bbox": [1, 2, 3, 4],
                "region_type": "paragraph",
                "matched_text": "본문",
                "citation_text": "본문",
                "section_heading": "섹션",
                "table_caption_footnote": "",
                "nearby_paragraphs": ["앞 문단"],
                "OCR_confidence": 0.99,
                "native_text_available": True,
                "OCR_fallback_used": False,
                "source_searchunit_id": "su-1",
                "source_searchunit_rank": 1,
                "source_bound_bbox": True,
                "bbox_source": "parser_block_bbox",
                "layout_resolution_method": "exact_parser_block_bbox",
                "parser_source_metadata": {"parser_version": "pdf-native-v1", "source": "native_text"},
                "citation_locator": {
                    "file": "sample.pdf",
                    "document_version_id": "docv1",
                    "page": 2,
                    "bbox": [1, 2, 3, 4],
                    "region_type": "paragraph",
                    "search_unit_id": "su-1",
                },
            },
        },
        {
            "query_id": "blocked_001",
            "diagnostic_only": True,
            "official_metric_input": False,
            "promotion_evidence": False,
            "citation_metadata": {
                "file": "sample.pdf",
                "document_version_id": "docv1",
                "page": 3,
                "bbox": [],
                "region_type": "page",
                "matched_text": "표",
                "nearby_paragraphs": [],
                "OCR_confidence": None,
                "native_text_available": False,
                "OCR_fallback_used": True,
                "source_searchunit_id": "",
                "source_searchunit_rank": None,
                "parser_source_metadata": {},
                "citation_locator": {
                    "file": "sample.pdf",
                    "document_version_id": "docv1",
                    "page": 3,
                    "bbox": [],
                    "region_type": "page",
                    "search_unit_id": "",
                },
            },
        },
    ]
    readiness_rows.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    return {"readiness_report": readiness_report, "readiness_rows": readiness_rows}
