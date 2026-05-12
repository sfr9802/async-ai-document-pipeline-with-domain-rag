from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_pdf_strict_silver_generation.py"
REGISTRY_PATH = ROOT / "ai-worker" / "eval" / "eval_queries" / "official_denominator_registry.json"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_strict_silver_generation_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pdf_strict_report_uses_current_policy_inputs_without_registry_mutation():
    module = load_module()
    before = REGISTRY_PATH.read_bytes()

    report, silver_rows = module.build_generation()

    assert report["status"] == "COMPLETED_DIAGNOSTIC_ONLY"
    assert report["report_role"] == "pdf_strict_retrieval_evidence_silver_generation_diagnostic"
    assert report["track"] == "pdf_business_ocr_mm"
    assert report["diagnostic_only"] is True
    assert report["promotion_evidence"] is False
    assert report["official_metric"] is False
    assert report["answer_generation_run"] is False
    assert report["counts"]["registry_pdf_row_count"] == 22
    assert report["counts"]["input_denominator_row_count"] == 7
    assert report["counts"]["generated_silver_row_count"] == 0
    assert report["counts"]["diagnostic_only_fallback_row_count"] == 7
    assert report["counts"]["candidate_row_count"] == 9
    assert report["counts"]["registry_diagnostic_only_row_count"] == 6
    assert report["counts"]["policy_excluded_row_count"] == 6
    assert report["counts"]["stable_identity_required_row_count"] == 3
    assert report["counts"]["pending_deferred_ocr_or_parsing_row_count"] == 2
    assert len(report["input_denominator_query_ids"]) == 7
    assert silver_rows == []
    assert REGISTRY_PATH.read_bytes() == before


def test_policy_excluded_and_stable_identity_rows_are_excluded_not_failures():
    module = load_module()

    report = module.build_report()

    assert set(report["excluded_query_ids"]["policy_excluded"]) == {
        "pdf_file_lookup_content_anchor_004",
        "pdf_file_lookup_content_anchor_012",
        "pdf_file_lookup_content_anchor_013",
        "pdf_file_lookup_content_anchor_014",
        "pdf_file_lookup_content_anchor_015",
        "pdf_file_lookup_metadata_002",
    }
    assert set(report["excluded_query_ids"]["stable_identity_required"]) == {
        "pdf_file_lookup_content_anchor_017",
        "pdf_file_lookup_content_anchor_018",
        "pdf_file_lookup_content_anchor_020",
    }
    assert set(report["included_query_ids"]).isdisjoint(report["excluded_query_ids"]["policy_excluded"])
    assert set(report["included_query_ids"]).isdisjoint(report["excluded_query_ids"]["stable_identity_required"])
    assert report["retrieval_failure_accounting"]["policy_excluded_retrieval_failure_count"] == 0
    assert report["retrieval_failure_accounting"]["stable_identity_required_retrieval_failure_count"] == 0
    assert report["guardrails"]["policy_excluded_rows_counted_as_retrieval_failures"] is False


def test_pdf_content_and_file_identity_lanes_are_not_aggregated():
    module = load_module()

    report = module.build_report()

    assert report["lane_separation"]["status"] == "PASS"
    assert report["lane_separation"]["content_evidence_lane"] == "pdf_content_evidence"
    assert report["lane_separation"]["file_identity_lane"] == "pdf_file_identity"
    assert report["lane_separation"]["content_and_file_identity_aggregated"] is False
    assert report["lane_separation"]["strict_silver_lanes"] == {"pdf_content_evidence": 0, "pdf_file_identity": 0}
    assert report["guardrails"]["pdf_content_file_lanes_aggregated"] is False


def test_missing_bbox_ocr_layout_source_and_flattened_only_are_diagnostic_only():
    module = load_module()

    missing = module.silver_row_from_sources(
        query_id="missing-layout",
        gold_row={
            "expected_file_name": "2025_12_recent_economic_trends.pdf",
            "expected_document_version_id": "docv_8b23a58c27c5518a",
            "expected_page_no": "1",
            "expected_physical_page_index": "0",
            "expected_chunk_type": "paragraph",
            "expected_answer_text": "recent economy cover",
            "expected_bbox": "",
        },
        review_row={},
        retrieval_hit={},
    )
    flattened = module.silver_row_from_sources(
        query_id="flattened-only",
        gold_row={
            "expected_file_name": "2025_12_recent_economic_trends.pdf",
            "expected_document_version_id": "docv_8b23a58c27c5518a",
            "expected_page_no": "1",
            "expected_physical_page_index": "0",
            "expected_chunk_type": "paragraph",
            "expected_bbox": "[1, 2, 3, 4]",
            "expected_answer_text": "flattened text",
        },
        review_row={},
        retrieval_hit={"flattened_only": True},
    )

    assert missing["diagnostic_only"] is True
    assert missing["diagnostic_only_reason"] == "pdf_context_diagnostic_only_missing_layout"
    assert set(missing["missing_context_fields"]) >= {
        "bbox",
        "nearby_paragraphs",
        "source_searchunit_id",
        "source_searchunit_rank",
        "parser_source_metadata",
    }
    assert flattened["diagnostic_only"] is True
    assert flattened["diagnostic_only_reason"] == "flattened_only"


def test_complete_content_evidence_row_preserves_citation_metadata():
    module = load_module()

    row = module.silver_row_from_sources(
        query_id="complete-content",
        gold_row={
            "expected_file_name": "2025_12_recent_economic_trends.pdf",
            "expected_document_version_id": "docv_8b23a58c27c5518a",
            "expected_page_no": "61",
            "expected_physical_page_index": "60",
            "expected_chunk_type": "table",
            "expected_location_type": "pdf",
            "expected_bbox": "[76.68,103.92,483.52,672.6]",
            "expected_answer_text": "수출입 표 문단",
            "must_contain_terms": "수 출(FOB);수 입(CIF)",
        },
        review_row={
            "expected_table_id": "table-61-1",
            "table_caption_footnote": "수출입 통관",
            "section_heading": "대외거래",
        },
        retrieval_hit={
            "source_searchunit_id": "su-pdf-61",
            "source_searchunit_rank": 1,
            "nearby_paragraphs": ["수 출(FOB)", "수 입(CIF)"],
            "OCR_confidence": 0.98,
            "parser_source_metadata": {"parser": "pdf_business_ocr_mm", "source": "layout_ocr"},
            "score": 0.91,
        },
    )

    assert row["diagnostic_only"] is False
    assert row["track"] == "pdf_business_ocr_mm"
    assert row["evidence_lane"] == "pdf_content_evidence"
    assert set(module.REQUIRED_PDF_EVIDENCE_METADATA_FIELDS).issubset(row["citation_metadata"])
    assert row["citation_metadata"]["bbox"] == [76.68, 103.92, 483.52, 672.6]
    assert row["citation_metadata"]["nearby_paragraphs"] == ["수 출(FOB)", "수 입(CIF)"]
    assert row["citation_locator"]["file"] == "2025_12_recent_economic_trends.pdf"
    assert row["citation_locator"]["page"] == 61
    assert row["citation_locator"]["search_unit_id"] == "su-pdf-61"
    assert row["answer_generation_denominator_included"] is False
    assert row["official_metric_input"] is False


def test_generic_filename_file_identity_row_is_blocked_as_stable_identity_required():
    module = load_module()

    row = module.silver_row_from_sources(
        query_id="pdf_file_lookup_content_anchor_017",
        gold_row={"expected_file_name": "report.pdf", "expected_document_version_id": ""},
        review_row={},
        retrieval_hit={"file": "report.pdf", "filename_only_identity": True},
        evidence_lane="pdf_file_identity",
        stable_identity_required=True,
    )

    assert row["evidence_lane"] == "pdf_file_identity"
    assert row["diagnostic_only"] is True
    assert row["diagnostic_only_reason"] == "stable_identity_required"
    assert row["retrieval_denominator_included"] is False


def test_repo_local_pdf_silver_manifest_path_is_rejected():
    module = load_module()
    forbidden_path = ROOT / "ai-worker" / "eval" / "reports" / "rag-ingestion" / "pdf_strict_manifest.jsonl"

    with pytest.raises(ValueError, match="outside the repository"):
        module.build_generation(silver_output=forbidden_path)

    report = module.build_report()
    assert report["silver_artifact_policy"]["full_manifest_location_guard"] == "assert_external_pdf_silver_output_path"
    assert report["silver_artifact_policy"]["repo_local_full_manifest_allowed"] is False


def test_build_generation_rejects_noncanonical_pdf_inputs(tmp_path: Path):
    module = load_module()
    gold_clone = tmp_path / "gold_queries_pdf_v0.csv"
    gold_clone.write_bytes(module.DEFAULT_PDF_GOLD_CSV.read_bytes())
    registry_clone = tmp_path / "official_denominator_registry.json"
    registry_clone.write_bytes(module.DEFAULT_REGISTRY.read_bytes())

    with pytest.raises(ValueError, match="canonical PDF strict input"):
        module.build_generation(pdf_gold_csv=gold_clone)
    with pytest.raises(ValueError, match="canonical PDF strict input"):
        module.build_generation(official_denominator_registry=registry_clone)


@pytest.mark.parametrize(
    ("key_path", "value", "expected_guardrail"),
    [
        (("production_vector_written",), True, "production_vector_written"),
        (("promotion_evidence_created",), True, "promotion_evidence_created"),
        (("route_fallback_label_review_pack_generation", "candidate_artifact_mutated"), True, "candidate_artifact_mutated"),
        (("route_fallback_label_review_applied", "immutable_baseline_mutated"), True, "immutable_baseline_mutated"),
        (("route_fallback_label_review_applied", "fallback_metrics_official"), True, "route_fallback_labels_promoted_to_official_metrics"),
        (("route_fallback_label_review_applied", "pdf_content_and_file_identity_aggregated"), True, "pdf_content_file_lanes_aggregated"),
    ],
)
def test_pdf_strict_generation_fails_on_nested_guardrails(
    tmp_path: Path,
    key_path: tuple[str, ...],
    value: object,
    expected_guardrail: str,
):
    module = load_module()
    three_track_payload = json.loads(module.DEFAULT_THREE_TRACK_REPORT.read_text(encoding="utf-8"))
    target = three_track_payload
    for key in key_path[:-1]:
        target = target[key]
    target[key_path[-1]] = value
    three_track_path = tmp_path / "three_track_guardrail_fail.json"
    three_track_path.write_text(json.dumps(three_track_payload, ensure_ascii=False), encoding="utf-8")

    report = module.build_report(three_track_report=three_track_path)

    assert report["status"] == "FAILED_GUARDRAIL"
    assert report["guardrails"][expected_guardrail] is True
    assert f"guardrail violation: {expected_guardrail}=true" in report["validation"]["errors"]


def test_cli_does_not_write_pdf_silver_manifest_when_guardrail_failed(tmp_path: Path):
    module = load_module()
    three_track_payload = json.loads(module.DEFAULT_THREE_TRACK_REPORT.read_text(encoding="utf-8"))
    three_track_payload["production_vector_written"] = True
    three_track_path = tmp_path / "three_track_guardrail_fail.json"
    three_track_path.write_text(json.dumps(three_track_payload, ensure_ascii=False), encoding="utf-8")
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"
    silver_path = tmp_path / "manifest.jsonl"

    code = module.main(
        [
            "--three-track-report",
            str(three_track_path),
            "--json-output",
            str(json_path),
            "--md-output",
            str(md_path),
            "--silver-output",
            str(silver_path),
        ]
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert code == 2
    assert payload["status"] == "FAILED_GUARDRAIL"
    assert payload["guardrails"]["production_vector_written"] is True
    assert payload["silver_artifact_policy"]["external_silver_artifact_written"] is False
    assert not silver_path.exists()


def test_pdf_strict_guardrails_and_answer_surfaces_remain_closed():
    module = load_module()

    report = module.build_report()

    assert report["surface_status"]["answer"] == "NOT_OPENED"
    assert report["surface_status"]["citation"] == "NOT_OPENED"
    assert report["counts"]["pdf_answer_generation_denominator"] == 0
    for key in (
        "official_denominator_registry_changed",
        "official_denominator_opened_or_frozen",
        "promotion_evidence_created",
        "pdf_answer_generation_denominator_opened",
        "production_namespace_mutated",
        "production_vector_index_mutated",
        "production_vector_written",
        "repo_local_pdf_silver_manifest_written",
        "candidate_artifact_mutated",
        "immutable_baseline_mutated",
        "diagnostic_only_row_promoted",
        "policy_excluded_rows_counted_as_retrieval_failures",
        "route_fallback_labels_promoted_to_official_metrics",
        "pdf_content_file_lanes_aggregated",
    ):
        assert report["guardrails"][key] is False
