from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_pdf_evidence_metadata_enrichment.py"


def load_script():
    spec = importlib.util.spec_from_file_location(
        "rag_pdf_evidence_metadata_enrichment", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_fixture(tmp_path: Path) -> dict[str, Path]:
    report_path = tmp_path / "pdf_evidence_readiness_report.json"
    rows_path = tmp_path / "pdf_evidence_readiness_rows.jsonl"
    metadata_path = tmp_path / "row_metadata.jsonl"
    enrichment_report_path = tmp_path / "metadata_report.json"
    enrichment_md_path = tmp_path / "metadata_report.md"
    repair_report_path = tmp_path / "repair_report.json"
    repair_md_path = tmp_path / "repair_report.md"

    report_path.write_text(
        json.dumps(
            {
                "status": "DIAGNOSTIC_ONLY_BLOCKED",
                "input_rows": 2,
                "strict_gate_readiness_count": 0,
                "answer_generation_run": False,
                "official_metric_input_rows": 0,
                "source_artifacts": {
                    "readiness_rows_jsonl": str(rows_path),
                },
            }
        ),
        encoding="utf-8",
    )

    rows = [
        {
            "query_id": "ready_001",
            "document_id": "2025_report.pdf",
            "stable_source_identity": "docv-ready",
            "page": 3,
            "bbox": [1.0, 2.0, 3.0, 4.0],
            "region_type": "paragraph",
            "matched_text": "ready matched text",
            "citation_text": "ready citation text",
            "citation_locator": {
                "page": 3,
                "bbox": [1.0, 2.0, 3.0, 4.0],
                "region_type": "paragraph",
            },
            "citation_locator_complete": True,
            "citation_metadata": {},
            "file_identity_policy": {
                "content_evidence_lane": "pdf_content_evidence",
                "file_identity_lane": "pdf_file_identity",
                "stable_identity_required": True,
            },
        },
        {
            "query_id": "blocked_001",
            "document_id": "ambiguous.pdf",
            "stable_source_identity": None,
            "page": None,
            "bbox": [],
            "region_type": "",
            "matched_text": "blocked matched text",
            "citation_text": "blocked citation text",
            "citation_locator": {},
            "citation_locator_complete": False,
            "citation_metadata": {},
            "file_identity_policy": {
                "content_evidence_lane": "pdf_content_evidence",
                "file_identity_lane": "pdf_file_identity",
                "stable_identity_required": True,
            },
        },
    ]
    rows_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    metadata_path.write_text(
        json.dumps(
            {
                "query_id": "ready_001",
                "source_file_id": "sf-ready",
                "extracted_artifact_id": "artifact-ready",
                "search_unit_id": "su-ready",
                "search_unit_rank": 1,
                "retrieval_rank": 1,
                "parser_version": "pdf-extract-v2",
                "bbox_source": "parser_block_bbox",
                "layout_resolution_method": "exact_parser_block_bbox",
                "source_bound_bbox": True,
                "source_metadata": {
                    "parser_version": "pdf-extract-v2",
                    "artifact_kind": "pdf_layout_json",
                },
                "section_heading": "Ready section",
                "table_caption_footnote": "",
                "nearby_paragraphs": ["previous paragraph", "next paragraph"],
                "native_text_available": True,
                "OCR_confidence": None,
                "OCR_fallback_used": False,
                "physical_page_index": 2,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "report": report_path,
        "rows": rows_path,
        "metadata": metadata_path,
        "enrichment_report": enrichment_report_path,
        "enrichment_md": enrichment_md_path,
        "repair_report": repair_report_path,
        "repair_md": repair_md_path,
    }


def test_pdf_metadata_enrichment_merges_row_metadata_and_keeps_strict_rows_diagnostic_only(
    tmp_path: Path,
) -> None:
    module = load_script()
    paths = write_fixture(tmp_path)

    report = module.run_enrichment(
        readiness_report_path=paths["report"],
        readiness_rows_path=paths["rows"],
        metadata_source_paths=[paths["metadata"]],
        output_json_path=paths["enrichment_report"],
        output_md_path=paths["enrichment_md"],
        repair_output_json_path=paths["repair_report"],
        repair_output_md_path=paths["repair_md"],
    )

    assert report["before_counts"]["search_unit_id_available_count"] == 0
    assert report["before_counts"]["parser_source_metadata_available_count"] == 0
    assert report["after_counts"]["search_unit_id_available_count"] == 1
    assert report["after_counts"]["parser_source_metadata_available_count"] == 1
    assert report["after_counts"]["nearby_paragraph_count"] == 1
    assert report["after_counts"]["native_or_ocr_trust_available_count"] == 1
    assert report["after_counts"]["strict_ready_rows"] == 1
    assert report["strict_gate_rerun"]["strict_gate_rerun_eligible"] is True
    assert report["strict_gate_rerun"]["strict_gate_rerun_performed"] is True
    assert report["strict_gate_rerun"]["generated_strict_silver_rows"] == 1
    assert report["strict_gate_rerun"]["remaining_fallback_rows"] == 1
    assert report["answer_generation_opened"] is False
    assert report["official_metric_input_rows"] == 0
    assert all(row["diagnostic_only"] for row in report["generated_strict_rows"])

    ready_row = next(row for row in report["rows"] if row["query_id"] == "ready_001")
    blocked_row = next(row for row in report["rows"] if row["query_id"] == "blocked_001")

    assert ready_row["search_unit_id"] == "su-ready"
    assert ready_row["parser_version"] == "pdf-extract-v2"
    assert ready_row["source_bound_bbox"] is True
    assert ready_row["bbox_source"] == "parser_block_bbox"
    assert ready_row["layout_resolution_method"] == "exact_parser_block_bbox"
    assert ready_row["blocker_classifications"] == ["strict_ready_diagnostic_only"]
    assert ready_row["content_evidence_lane"] == "pdf_content_evidence"
    assert ready_row["file_identity_lane"]["lane"] == "pdf_file_identity"
    assert ready_row["file_identity_lane"]["merged_with_content_evidence"] is False

    assert "blocked_missing_search_unit" in blocked_row["blocker_classifications"]
    assert "blocked_missing_parser_source_metadata" in blocked_row["blocker_classifications"]
    assert "blocked_missing_layout_bbox_region" in blocked_row["blocker_classifications"]
    assert "blocked_missing_nearby_paragraphs" in blocked_row["blocker_classifications"]
    assert "blocked_missing_ocr_or_native_text_trust" in blocked_row["blocker_classifications"]
    assert "blocked_file_identity_ambiguity" in blocked_row["blocker_classifications"]
    assert "blocked_unresolved_source_artifact" in blocked_row["blocker_classifications"]
    assert "diagnostic_only_fallback" in blocked_row["blocker_classifications"]

    refreshed_repair = json.loads(paths["repair_report"].read_text(encoding="utf-8"))
    assert refreshed_repair["strict_ready_rows"] == 1
    assert refreshed_repair["strict_gate_rerun"]["strict_gate_rerun_performed"] is True
    assert refreshed_repair["official_metric_input_rows"] == 0
    assert refreshed_repair["answer_generation_opened"] is False


def test_pdf_metadata_enrichment_skips_strict_gate_when_required_metadata_is_absent(
    tmp_path: Path,
) -> None:
    module = load_script()
    paths = write_fixture(tmp_path)

    report = module.run_enrichment(
        readiness_report_path=paths["report"],
        readiness_rows_path=paths["rows"],
        metadata_source_paths=[],
        output_json_path=paths["enrichment_report"],
        output_md_path=paths["enrichment_md"],
        repair_output_json_path=paths["repair_report"],
        repair_output_md_path=paths["repair_md"],
    )

    assert report["after_counts"]["search_unit_id_available_count"] == 0
    assert report["after_counts"]["parser_source_metadata_available_count"] == 0
    assert report["after_counts"]["strict_ready_rows"] == 0
    assert report["strict_gate_rerun"]["strict_gate_rerun_eligible"] is False
    assert report["strict_gate_rerun"]["strict_gate_rerun_performed"] is False
    assert report["strict_gate_rerun"]["generated_strict_silver_rows"] == 0
    assert report["answer_generation_opened"] is False
    assert report["official_metric_input_rows"] == 0
