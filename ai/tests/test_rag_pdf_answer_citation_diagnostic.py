from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_pdf_answer_citation_diagnostic.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_answer_citation_diagnostic_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pdf_answer_diagnostic_uses_only_strict_ready_content_rows(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture(tmp_path)

    report = module.run_generation(
        readiness_report=paths["readiness"],
        output_jsonl=paths["review_input"],
        output_report=paths["report"],
        output_md=paths["report_md"],
    )

    assert report["status"] == "PASS"
    assert report["input_rows"] == 4
    assert report["strict_ready_rows"] == 1
    assert report["generated_answer_rows"] == 1
    assert report["clean_pass_rows"] == 1
    assert report["cleanup_rows"] == 0
    assert report["unresolved_rows"] == 0
    assert report["lane_policy_blocked_rows"] == 0
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["pdf_answer_generation_denominator_opened"] is False
    assert report["diagnostic_answer_generation_run"] is True
    assert report["excluded_query_ids"]["diagnostic_fallback"] == ["fallback_001"]
    assert report["excluded_query_ids"]["file_identity_lane"] == ["file_lane_001"]
    assert report["excluded_query_ids"]["policy_excluded_or_identity_blocked"] == ["filename_only_001"]

    rows = [json.loads(line) for line in paths["review_input"].read_text(encoding="utf-8").splitlines()]
    assert [row["query_id"] for row in rows] == ["strict_001"]
    row = rows[0]
    assert row["diagnostic_answer"] == "수출은 증가했다"
    assert row["generated_answer"] == "수출은 증가했다"
    assert row["answer_claims"] == ["수출은 증가했다"]
    assert row["answer_supported_by_matched_text_or_nearby_paragraph"] is True
    assert row["answer_claims_supported"] is True
    assert row["citation_locator_valid"] is True
    assert row["citation_locator_has_page_bbox_region_search_unit"] is True
    assert row["citation_text_matches_source_bound_evidence"] is True
    assert row["no_file_identity_lane_used_as_content_evidence"] is True
    assert row["no_filename_only_identity_acceptance"] is True
    assert row["no_diagnostic_fallback_row_used"] is True
    assert row["official_metric_input"] is False
    assert row["diagnostic_only"] is True
    assert row["promotion_evidence"] is False


def test_pdf_answer_diagnostic_blocks_synthetic_bbox_and_unsupported_answers(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture(tmp_path, rows=[strict_row("synthetic_001"), strict_row("unsupported_001")])
    payload = json.loads(paths["readiness"].read_text(encoding="utf-8"))
    payload["repair_rows"][0]["bbox_source"] = "generated_estimate"
    payload["repair_rows"][0]["layout_resolution_method"] = "generated_bbox_estimate"
    payload["repair_rows"][0]["source_bound_bbox"] = False
    payload["repair_rows"][1]["diagnostic_answer_override"] = "근거에 없는 답"
    paths["readiness"].write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = module.run_generation(
        readiness_report=paths["readiness"],
        output_jsonl=paths["review_input"],
        output_report=paths["report"],
        output_md=paths["report_md"],
    )

    rows = {row["query_id"]: row for row in read_jsonl(paths["review_input"])}
    assert report["generated_answer_rows"] == 2
    assert report["clean_pass_rows"] == 0
    assert report["cleanup_rows"] == 2
    assert report["citation_locator_incomplete_rows"] == 1
    assert report["unsupported_answer_rows"] == 1
    assert rows["synthetic_001"]["bucket"] == "citation_locator_incomplete"
    assert rows["synthetic_001"]["citation_locator_valid"] is False
    assert rows["unsupported_001"]["bucket"] == "unsupported_answer"
    assert rows["unsupported_001"]["answer_claims_supported"] is False


def test_pdf_answer_diagnostic_flags_citation_text_that_does_not_match_source_locator(tmp_path: Path) -> None:
    module = load_module()
    paths = write_fixture(tmp_path, rows=[strict_row("bad_citation_001")])
    payload = json.loads(paths["readiness"].read_text(encoding="utf-8"))
    payload["repair_rows"][0]["citation_text"] = "sample.pdf > p.4 > bbox [9.0,9.0,9.0,9.0]"
    paths["readiness"].write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    report = module.run_generation(
        readiness_report=paths["readiness"],
        output_jsonl=paths["review_input"],
        output_report=paths["report"],
        output_md=paths["report_md"],
    )

    rows = read_jsonl(paths["review_input"])
    assert report["clean_pass_rows"] == 0
    assert report["cleanup_rows"] == 1
    assert rows[0]["citation_locator_valid"] is True
    assert rows[0]["citation_text_matches_source_bound_evidence"] is False
    assert rows[0]["bucket"] == "cleanup_required"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_fixture(tmp_path: Path, rows: list[dict[str, object]] | None = None) -> dict[str, Path]:
    readiness = tmp_path / "pdf_repair.json"
    review_input = tmp_path / "review_input.jsonl"
    report = tmp_path / "diagnostic_report.json"
    report_md = tmp_path / "diagnostic_report.md"
    repair_rows = rows or [
        strict_row("strict_001"),
        {**strict_row("fallback_001"), "strict_ready": False, "blocker_classifications": ["diagnostic_only_fallback"]},
        {**strict_row("file_lane_001"), "content_evidence_lane": "pdf_file_identity"},
        {
            **strict_row("filename_only_001"),
            "file_identity_lane": {
                "lane": "pdf_file_identity",
                "merged_with_content_evidence": False,
                "filename_only_identity_accepted": True,
            },
        },
    ]
    readiness.write_text(
        json.dumps(
            {
                "schema_version": "pdf_evidence_readiness_repair_report_v1",
                "generated_at": "2026-05-15T00:00:00+00:00",
                "status": "READY_FOR_DIAGNOSTIC_STRICT_GATE_RERUN",
                "diagnostic_only": True,
                "official_metric": False,
                "promotion_evidence": False,
                "official_metric_input_rows": 0,
                "input_rows": len(repair_rows),
                "strict_ready_rows": sum(1 for row in repair_rows if row.get("strict_ready") is True),
                "diagnostic_only_fallback_rows": sum(1 for row in repair_rows if row.get("strict_ready") is not True),
                "repair_rows": repair_rows,
                "lane_separation": {"content_and_file_identity_aggregated": False},
                "guardrails": {
                    "official_metric_input_rows_remain_zero": True,
                    "official_denominator_registry_opened": False,
                    "official_denominator_registry_mutation": False,
                },
                "validation": {"ok": True, "errors": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {"readiness": readiness, "review_input": review_input, "report": report, "report_md": report_md}


def strict_row(query_id: str) -> dict[str, object]:
    bbox = [1.0, 2.0, 3.0, 4.0]
    return {
        "query_id": query_id,
        "strict_ready": True,
        "diagnostic_only": True,
        "official_metric_input": False,
        "promotion_evidence": False,
        "content_evidence_lane": "pdf_content_evidence",
        "file_identity_lane": {
            "lane": "pdf_file_identity",
            "merged_with_content_evidence": False,
            "filename_only_identity_accepted": False,
        },
        "source_file_id": "sf-1",
        "document_version_id": "docv-1",
        "stable_source_identity": "docv-1",
        "extracted_artifact_id": "artifact-1",
        "search_unit_id": "su-1",
        "search_unit_rank": 1,
        "retrieval_rank": 1,
        "parser_version": "pdf-extract-v2",
        "page": 3,
        "physical_page_index": 2,
        "bbox": bbox,
        "bbox_source": "local_db.search_unit.location_json.bbox",
        "source_bound_bbox": True,
        "layout_resolution_method": "exact_search_unit_bbox",
        "region_type": "paragraph",
        "matched_text": "수출은 증가했다",
        "citation_text": "sample.pdf > p.3 > bbox [1.0,2.0,3.0,4.0]",
        "citation_locator": {
            "file": "sample.pdf",
            "document_version_id": "docv-1",
            "page": 3,
            "physical_page_index": 2,
            "bbox": bbox,
            "region_type": "paragraph",
            "search_unit_id": "su-1",
        },
        "section_heading": "",
        "table_caption_footnote": "",
        "nearby_paragraphs": ["수출은 증가했다"],
        "native_text_available": True,
        "OCR_confidence": None,
        "OCR_fallback_used": False,
        "blocker_classifications": ["strict_ready_diagnostic_only"],
    }
