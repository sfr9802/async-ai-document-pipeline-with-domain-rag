from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-worker" / "scripts" / "rag_pdf_embedding_text_contract_audit.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_embedding_text_contract_audit", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


c3_module = load_module()


def test_c3_passes_when_text_surfaces_are_complete(tmp_path: Path):
    c1_path = write_c1(tmp_path)
    payload = c3_module.build_payload(
        scope_report=c1_report(),
        scope_report_path=c1_path,
        db_snapshot=db_snapshot(),
        db_dsn="host=localhost password=secret",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "PASS"
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["allowUnscoped"] is False
    assert payload["summary"]["text_contract_blocker_count"] == 0
    assert payload["blockers"] == []
    assert payload["warnings"] == []


def test_c3_fails_when_embedding_text_lacks_pdf_context_surfaces(tmp_path: Path):
    c1_path = write_c1(tmp_path)
    snapshot = db_snapshot()
    snapshot["summary"].update(
        {
            "missing_source_file_surface_in_embedding_text_count": 9,
            "missing_page_surface_in_embedding_text_count": 9,
            "missing_citation_surface_in_embedding_text_count": 9,
            "missing_block_type_surface_in_embedding_text_count": 9,
        }
    )

    payload = c3_module.build_payload(
        scope_report=c1_report(),
        scope_report_path=c1_path,
        db_snapshot=snapshot,
        db_dsn="host=localhost password=secret",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert "text_contract_blocker_count must be 0" in payload["blockers"]
    assert payload["summary"]["text_contract_blocker_count"] == 36


def test_c3_fails_on_embedded_ocr_without_trust_marker(tmp_path: Path):
    c1_path = write_c1(tmp_path)
    snapshot = db_snapshot()
    snapshot["ocr_trust_contract"]["embedded_ocr_trust_marker_missing_count"] = 2

    payload = c3_module.build_payload(
        scope_report=c1_report(),
        scope_report_path=c1_path,
        db_snapshot=snapshot,
        db_dsn="host=localhost password=secret",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert payload["blocker_counters"]["embedded_ocr_trust_marker_missing_count"] == 2


def test_c3_keeps_policy_excluded_rows_as_warnings(tmp_path: Path):
    c1_path = write_c1(tmp_path)
    c1 = c1_report(pdf_table_lookup=6)
    snapshot = db_snapshot()
    snapshot["summary"]["skipped_searchable_row_count"] = 3
    snapshot["ocr_trust_contract"]["policy_excluded_ocr_confidence_missing_count"] = 3
    snapshot["bbox_policy_contract"]["page_or_document_bbox_missing_count"] = 2
    snapshot["table_contract"]["table_like_search_unit_count"] = 0

    payload = c3_module.build_payload(
        scope_report=c1,
        scope_report_path=c1_path,
        db_snapshot=snapshot,
        db_dsn="host=localhost password=secret",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["blockers"] == []
    assert payload["warnings"] == [
        "skipped_searchable_row_count=3; C4 should not index skipped rows",
        "policy_excluded_ocr_confidence_missing_count=3; excluded before C4 indexing",
        "page_or_document_bbox_missing_count=2; bbox is optional for page/document summary rows",
        "pdf_table_gold_without_table_blocks_count=6; current parser stores table-like PDF evidence as paragraphs/pages",
    ]


def test_c3_uses_pdf_table_gold_count_from_c1_scope(tmp_path: Path):
    c1_path = write_c1(tmp_path)
    snapshot = db_snapshot()
    snapshot["table_contract"]["table_like_search_unit_count"] = 0

    payload = c3_module.build_payload(
        scope_report=c1_report(pdf_table_lookup=4),
        scope_report_path=c1_path,
        db_snapshot=snapshot,
        db_dsn="host=localhost password=secret",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["table_contract"]["pdf_table_gold_count"] == 4
    assert payload["warnings"] == [
        "pdf_table_gold_without_table_blocks_count=4; current parser stores table-like PDF evidence as paragraphs/pages"
    ]


def test_c3_does_not_warn_when_c1_has_no_pdf_table_gold(tmp_path: Path):
    c1_path = write_c1(tmp_path)
    snapshot = db_snapshot()
    snapshot["table_contract"]["table_like_search_unit_count"] = 0

    payload = c3_module.build_payload(
        scope_report=c1_report(pdf_table_lookup=0),
        scope_report_path=c1_path,
        db_snapshot=snapshot,
        db_dsn="host=localhost password=secret",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "PASS"
    assert payload["table_contract"]["pdf_table_gold_count"] == 0
    assert payload["warnings"] == []


def test_c3_fails_on_bad_c1_guardrails(tmp_path: Path):
    c1_path = write_c1(tmp_path)
    c1 = c1_report()
    c1["promotion_evidence"] = True
    c1["allowUnscoped"] = True

    payload = c3_module.build_payload(
        scope_report=c1,
        scope_report_path=c1_path,
        db_snapshot=db_snapshot(),
        db_dsn="host=localhost password=secret",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert "C1 scope report must keep promotion_evidence=false" in payload["blockers"]
    assert "C1 scope report must keep allowUnscoped=false" in payload["blockers"]


def c1_report(pdf_table_lookup: int = 0) -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "allowUnscoped": False,
        "scope": {
            "document_version_ids": ["docv_pdf"],
            "source_file_ids": ["sf_pdf"],
            "parser_versions": ["pdf-extract-v1"],
        },
        "gold_scope": {
            "bucket_counts": {
                "pdf_table_lookup": pdf_table_lookup,
            },
        },
        "warnings": [],
    }


def db_snapshot() -> dict:
    return {
        "summary": {
            "scoped_rows": 10,
            "indexable_rows": 10,
            "policy_excluded_rows": 0,
            "skipped_searchable_row_count": 0,
            "missing_embedding_text_count": 0,
            "missing_bm25_text_count": 0,
            "missing_display_text_count": 0,
            "missing_citation_text_count": 0,
            "missing_source_file_surface_in_embedding_text_count": 0,
            "missing_page_surface_in_embedding_text_count": 0,
            "missing_citation_surface_in_embedding_text_count": 0,
            "missing_block_type_surface_in_embedding_text_count": 0,
            "missing_section_surface_for_sectioned_rows": 0,
            "debug_text_leakage_count": 0,
            "warning_text_leakage_count": 0,
            "hidden_or_internal_field_leakage_count": 0,
            "raw_json_leakage_count": 0,
            "citation_location_mismatch_count": 0,
        },
        "embedding_text_contract": {},
        "citation_contract": {},
        "bm25_display_contract": {},
        "ocr_trust_contract": {
            "embedded_ocr_trust_marker_missing_count": 0,
            "policy_excluded_ocr_confidence_missing_count": 0,
        },
        "bbox_policy_contract": {
            "required_bbox_missing_after_chunk_type_policy_count": 0,
            "page_or_document_bbox_missing_count": 0,
        },
        "table_contract": {
            "missing_table_surface_for_table_rows": 0,
            "table_like_search_unit_count": 0,
        },
        "leakage_contract": {},
        "distributions": {},
        "sample_blockers": [],
        "sample_warnings": [],
        "sample_passes": [],
    }


def write_c1(tmp_path: Path) -> Path:
    c1_path = tmp_path / "c1.json"
    c1_path.write_text(json.dumps(c1_report()), encoding="utf-8")
    return c1_path
