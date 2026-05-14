from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_pdf_layout_gap_closure.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_layout_gap_closure_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_layout_gap_closure_promotes_only_source_bound_bbox(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture(tmp_path)

    layout_source = tmp_path / "layout_source.jsonl"
    layout_source.write_text(
        json.dumps(
            {
                "query_id": "gq_auto_010",
                "search_unit_id": "su-paragraph",
                "search_unit_rank": 1,
                "retrieval_rank": 1,
                "page": 8,
                "physical_page_index": 7,
                "bbox": [63.65, 121.56, 227.84, 131.77],
                "region_type": "paragraph",
                "bbox_source": "parser_block_bbox",
                "layout_resolution_method": "exact_parser_block_bbox",
                "source_bound_bbox": True,
                "source_artifact_ref": "parsed_artifact:pa-test:raw_page.blocks[2]",
                "matched_text": "target paragraph",
                "citation_text": "sample.pdf > p.8 > bbox [63.65,121.56,227.84,131.77]",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    report = module.run_closure(
        enrichment_report_path=paths["enrichment"],
        repair_report_path=paths["repair"],
        layout_source_paths=[layout_source],
        output_json_path=paths["closure_json"],
        output_md_path=paths["closure_md"],
        refreshed_enrichment_json_path=paths["refreshed_enrichment"],
        refreshed_enrichment_md_path=paths["refreshed_enrichment_md"],
        refreshed_repair_json_path=paths["refreshed_repair"],
        refreshed_repair_md_path=paths["refreshed_repair_md"],
    )

    assert report["strict_ready_rows_before"] == 1
    assert report["strict_ready_rows_after"] == 2
    assert report["diagnostic_only_fallback_rows_after"] == 0
    assert report["source_bound_bbox_resolved_count"] == 1
    assert report["page_anchor_only_count"] == 0
    assert report["official_metric_input_rows"] == 0
    assert report["answer_generation_opened"] is False

    row = report["row_results"][0]
    assert row["query_id"] == "gq_auto_010"
    assert row["classification"] == "strict_ready_diagnostic_only"
    assert row["bbox_source"] == "parser_block_bbox"
    assert row["layout_resolution_method"] == "exact_parser_block_bbox"
    assert row["search_unit_id"] == "su-paragraph"
    assert row["content_evidence_lane"] == "pdf_content_evidence"
    assert row["file_identity_lane"]["lane"] == "pdf_file_identity"
    assert row["file_identity_lane"]["merged_with_content_evidence"] is False
    assert all(strict_row["diagnostic_only"] for strict_row in report["generated_strict_rows"])

    refreshed = json.loads(paths["refreshed_enrichment"].read_text(encoding="utf-8"))
    refreshed_row = next(row for row in refreshed["rows"] if row["query_id"] == "gq_auto_010")
    assert refreshed["after_counts"]["strict_ready_rows"] == 2
    assert refreshed_row["strict_ready"] is True
    assert refreshed_row["bbox"] == [63.65, 121.56, 227.84, 131.77]


def test_layout_gap_closure_rejects_generated_and_full_page_fallback_bboxes(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture(tmp_path, include_second_fallback=True)

    layout_source = tmp_path / "layout_source.jsonl"
    layout_source.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "query_id": "gq_auto_010",
                        "bbox": [0, 0, 595, 842],
                        "region_type": "page",
                        "bbox_source": "full_page_fallback",
                        "layout_resolution_method": "full_page_fallback_bbox",
                        "source_bound_bbox": False,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "query_id": "gq_auto_015",
                        "bbox": [10, 10, 20, 20],
                        "region_type": "paragraph",
                        "bbox_source": "generated_estimate",
                        "layout_resolution_method": "generated_bbox_estimate",
                        "source_bound_bbox": False,
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = module.run_closure(
        enrichment_report_path=paths["enrichment"],
        repair_report_path=paths["repair"],
        layout_source_paths=[layout_source],
        output_json_path=paths["closure_json"],
        output_md_path=paths["closure_md"],
        refreshed_enrichment_json_path=paths["refreshed_enrichment"],
        refreshed_enrichment_md_path=paths["refreshed_enrichment_md"],
        refreshed_repair_json_path=paths["refreshed_repair"],
        refreshed_repair_md_path=paths["refreshed_repair_md"],
    )

    assert report["strict_ready_rows_before"] == 1
    assert report["strict_ready_rows_after"] == 1
    assert report["source_bound_bbox_resolved_count"] == 0
    assert report["page_anchor_only_count"] == 1
    assert report["unresolved_layout_count"] == 1

    by_id = {row["query_id"]: row for row in report["row_results"]}
    assert by_id["gq_auto_010"]["classification"] == "diagnostic_only_fallback"
    assert "blocked_page_anchor_only" in by_id["gq_auto_010"]["blocker_classifications"]
    assert by_id["gq_auto_010"]["bbox_source"] == "full_page_fallback"
    assert by_id["gq_auto_015"]["classification"] == "diagnostic_only_fallback"
    assert "blocked_missing_source_bound_bbox" in by_id["gq_auto_015"]["blocker_classifications"]
    assert by_id["gq_auto_015"]["layout_resolution_method"] == "generated_bbox_estimate"


def write_fixture(tmp_path: Path, include_second_fallback: bool = False) -> dict[str, Path]:
    enrichment = tmp_path / "enrichment.json"
    repair = tmp_path / "repair.json"
    rows = [
        ready_row("ready_001"),
        fallback_row("gq_auto_010"),
        fallback_row("gq_auto_015"),
    ]
    fixture_rows = rows if include_second_fallback else rows[:2]
    input_rows = len(fixture_rows)
    fallback_rows = input_rows - 1
    enrichment.write_text(
        json.dumps(
            {
                "schema_version": "pdf_evidence_metadata_enrichment_report_v1",
                "generated_at": "2026-05-14T00:00:00+00:00",
                "status": "PDF_METADATA_ENRICHMENT_COMPLETED_PARTIAL_STRICT_READY",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "answer_generation_opened": False,
                "official_metric_input_rows": 0,
                "after_counts": {
                    "input_rows": input_rows,
                    "strict_ready_rows": 1,
                    "diagnostic_only_fallback_rows": fallback_rows,
                    "citation_locator_complete_count": input_rows,
                    "search_unit_id_available_count": input_rows,
                    "parser_source_metadata_available_count": input_rows,
                    "nearby_paragraph_count": input_rows,
                    "native_or_ocr_trust_available_count": input_rows,
                },
                "rows": fixture_rows,
                "strict_gate_rerun": {"strict_gate_rerun_performed": True},
                "guardrails": {"official_metric_input_rows_remain_zero": True},
                "validation": {"ok": True, "errors": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    repair.write_text(
        json.dumps(
            {
                "schema_version": "pdf_evidence_readiness_repair_report_v1",
                "generated_at": "2026-05-14T00:00:00+00:00",
                "status": "EVIDENCE_READINESS_BLOCKED",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "answer_generation_opened": False,
                "official_metric_input_rows": 0,
                "input_rows": input_rows,
                "strict_ready_rows": 1,
                "diagnostic_only_fallback_rows": fallback_rows,
                "repair_rows": fixture_rows,
                "lane_separation": {"content_and_file_identity_aggregated": False},
                "file_identity_policy": {
                    "generic_filename_only_identity_blocked": True,
                    "blocker": "stable_identity_required",
                    "filename_only_identity_accepted": False,
                },
                "validation": {"ok": True, "errors": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {
        "enrichment": enrichment,
        "repair": repair,
        "closure_json": tmp_path / "closure.json",
        "closure_md": tmp_path / "closure.md",
        "refreshed_enrichment": tmp_path / "refreshed_enrichment.json",
        "refreshed_enrichment_md": tmp_path / "refreshed_enrichment.md",
        "refreshed_repair": tmp_path / "refreshed_repair.json",
        "refreshed_repair_md": tmp_path / "refreshed_repair.md",
    }


def ready_row(query_id: str) -> dict[str, object]:
    row = fallback_row(query_id)
    row.update(
        {
            "bbox": [1, 2, 3, 4],
            "bbox_source": "parser_block_bbox",
            "layout_resolution_method": "exact_parser_block_bbox",
            "source_bound_bbox": True,
            "region_type": "paragraph",
            "citation_locator": {
                "file": "sample.pdf",
                "document_version_id": "docv-test",
                "page": 1,
                "physical_page_index": 0,
                "bbox": [1, 2, 3, 4],
                "region_type": "paragraph",
                "search_unit_id": "su-ready",
            },
            "search_unit_id": "su-ready",
            "search_unit_rank": 1,
            "strict_ready": True,
            "blocked_reasons": [],
            "blocker_classifications": ["strict_ready_diagnostic_only"],
        }
    )
    return row


def fallback_row(query_id: str) -> dict[str, object]:
    return {
        "schema_version": "pdf_evidence_readiness_repair_row_v1",
        "query_id": query_id,
        "track": "pdf_business_ocr_mm",
        "content_evidence_lane": "pdf_content_evidence",
        "file_identity_lane": {
            "lane": "pdf_file_identity",
            "blocker": "stable_identity_required",
            "merged_with_content_evidence": False,
            "filename_only_identity_accepted": False,
        },
        "source_file_id": "sf-test",
        "document_version_id": "docv-test",
        "stable_source_identity": "docv-test",
        "extracted_artifact_id": "artifact-test",
        "search_unit_id": "su-page",
        "search_unit_rank": 3,
        "retrieval_rank": 3,
        "parser_version": "pdf-extract-v2",
        "source_metadata": {"parser_version": "pdf-extract-v2"},
        "page": 8,
        "physical_page_index": 7,
        "bbox": [],
        "region_type": "page",
        "matched_text": "target paragraph",
        "citation_text": "sample.pdf > p.8",
        "citation_locator": {
            "file": "sample.pdf",
            "document_version_id": "docv-test",
            "page": 8,
            "physical_page_index": 7,
            "region_type": "page",
            "search_unit_id": "su-page",
        },
        "citation_locator_complete": True,
        "section_heading": "",
        "table_caption_footnote": "",
        "nearby_paragraphs": ["nearby"],
        "OCR_confidence": None,
        "native_text_available": True,
        "OCR_fallback_used": False,
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "strict_ready": False,
        "blocked_reasons": ["missing_layout"],
        "blocker_classifications": ["blocked_missing_layout_bbox_region", "diagnostic_only_fallback"],
    }
