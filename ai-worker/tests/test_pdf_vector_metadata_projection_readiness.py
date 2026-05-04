from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "pdf_vector_metadata_projection_readiness.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pdf_vector_metadata_projection_readiness", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


c2_module = load_module()


def test_c2_passes_with_candidate_namespace_warning_only(tmp_path: Path):
    c1_path = write_c1(tmp_path)
    payload = c2_module.build_payload(
        scope_report=c1_report(),
        scope_report_path=c1_path,
        db_snapshot=db_snapshot(),
        db_dsn="host=localhost password=secret",
        expected_index_version="rag-ingestion-v2-pdf-candidate-v1",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["allowUnscoped"] is False
    assert payload["db_dsn"] == "host=localhost password=<redacted>"
    assert payload["summary"]["metadata_projection_blocker_count"] == 0
    assert payload["blockers"] == []
    assert payload["warnings"] == [
        "ragmeta_candidate_chunk_count=0; stored chunk projection comparison is deferred until C4"
    ]


def test_c2_fails_on_current_ragmeta_jackson_shape_projection(tmp_path: Path):
    c1_path = write_c1(tmp_path)
    snapshot = db_snapshot()
    snapshot["current_ragmeta_projection"] = {
        "current_ragmeta_joined_embedded_count": 10,
        "current_ragmeta_location_json_object_count": 10,
        "current_ragmeta_location_json_jackson_shape_count": 10,
        "current_ragmeta_location_json_unusable_count": 10,
        "current_ragmeta_missing_physical_page_index_count": 10,
        "current_ragmeta_missing_bbox_for_text_block_count": 8,
    }

    payload = c2_module.build_payload(
        scope_report=c1_report(),
        scope_report_path=c1_path,
        db_snapshot=snapshot,
        db_dsn="host=localhost password=secret",
        expected_index_version="rag-ingestion-v2-pdf-candidate-v1",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert "metadata_projection_blocker_count must be 0" in payload["blockers"]
    assert payload["summary"]["metadata_projection_blocker_count"] == 28
    assert payload["completion_counters"]["current_ragmeta_location_json_unusable_count"] == 10


def test_c2_preserves_current_ragmeta_sample_blockers(tmp_path: Path):
    c1_path = write_c1(tmp_path)
    snapshot = db_snapshot()
    snapshot["current_ragmeta_projection"] = {
        "current_ragmeta_joined_embedded_count": 1,
        "current_ragmeta_location_json_unusable_count": 1,
        "current_ragmeta_missing_physical_page_index_count": 1,
        "current_ragmeta_missing_bbox_for_text_block_count": 1,
    }
    snapshot["sample_blockers"] = [
        {
            "id": "unit-1",
            "blocker_reason": "current_ragmeta_location_json_jackson_shape",
            "chunk_location_preview": "{\"nodeType\":\"OBJECT\"}",
        }
    ]

    payload = c2_module.build_payload(
        scope_report=c1_report(),
        scope_report_path=c1_path,
        db_snapshot=snapshot,
        db_dsn="host=localhost password=secret",
        expected_index_version="rag-ingestion-v2-pdf-candidate-v1",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert payload["sample_blockers"][0]["blocker_reason"] == "current_ragmeta_location_json_jackson_shape"


def test_c2_fails_on_bad_c1_guardrails(tmp_path: Path):
    c1_path = write_c1(tmp_path)
    c1 = c1_report()
    c1["status"] = "FAIL"
    c1["allowUnscoped"] = True

    payload = c2_module.build_payload(
        scope_report=c1,
        scope_report_path=c1_path,
        db_snapshot=db_snapshot(),
        db_dsn="host=localhost password=secret",
        expected_index_version="rag-ingestion-v2-pdf-candidate-v1",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert "C1 scope report must pass before C2; got FAIL" in payload["blockers"]
    assert "C1 scope report must keep allowUnscoped=false" in payload["blockers"]


def c1_report() -> dict:
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
        "warnings": [],
    }


def db_snapshot() -> dict:
    return {
        "summary": {
            "scoped_rows": 10,
            "indexable_rows": 10,
            "policy_excluded_rows": 0,
            "missing_physical_page_index_for_page_bound_chunks": 0,
            "missing_page_no_for_page_bound_chunks": 0,
            "missing_bbox_for_text_block_chunks": 0,
            "missing_ocr_confidence_for_ocr_chunks": 0,
            "vector_hit_location_reconstruction_failure_count": 0,
            "missing_block_type_count": 0,
            "missing_ocr_used_count": 0,
            "citation_reconstruction_missing_count": 0,
            "source_lookup_missing_count": 0,
        },
        "ragmeta_projection": {
            "ragmeta_candidate_chunk_count": 0,
            "stored_ragmeta_location_mismatch_count": 0,
            "stored_ragmeta_missing_location_json_count": 0,
            "stored_ragmeta_missing_citation_text_count": 0,
        },
        "current_ragmeta_projection": {
            "current_ragmeta_joined_embedded_count": 0,
            "current_ragmeta_location_json_unusable_count": 0,
            "current_ragmeta_missing_physical_page_index_count": 0,
            "current_ragmeta_missing_bbox_for_text_block_count": 0,
        },
        "distributions": {},
        "document_scope_details": [],
        "sample_blockers": [],
        "sample_warnings": [],
    }


def write_c1(tmp_path: Path) -> Path:
    c1_path = tmp_path / "c1.json"
    c1_path.write_text(json.dumps(c1_report()), encoding="utf-8")
    return c1_path
