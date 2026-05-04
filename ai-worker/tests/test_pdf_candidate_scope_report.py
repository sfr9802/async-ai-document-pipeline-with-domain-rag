from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "pdf_candidate_scope_report.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pdf_candidate_scope_report", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


scope_module = load_module()


def test_pdf_scope_report_passes_with_ocr_warning(tmp_path: Path):
    c0_path, gold_path = write_inputs(tmp_path)
    payload = scope_module.build_payload(
        c0_snapshot=c0_snapshot(),
        c0_snapshot_path=c0_path,
        gold_scope=gold_scope(),
        gold_path=gold_path,
        db_snapshot=db_snapshot(ocr_missing=2),
        db_dsn="host=localhost password=secret",
        parser_versions=["pdf-extract-v1", "pdf-extract-v2"],
        expected_location_type="pdf",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["db_dsn"] == "host=localhost password=<redacted>"
    assert payload["summary"]["missing_page_metadata_count"] == 0
    assert payload["scope"]["document_version_ids"] == ["docv_pdf"]
    assert payload["warnings"] == [
        "ocr_confidence_missing_count=2; C2/C3 OCR trust readiness must classify this"
    ]


def test_pdf_scope_report_blocks_gate_counter_and_pdf_artifact(tmp_path: Path):
    c0_path, gold_path = write_inputs(tmp_path)
    snapshot = db_snapshot()
    snapshot["summary"]["missing_location_json_count"] = 1
    snapshot["pdf_candidate_artifact"]["exists"] = True

    payload = scope_module.build_payload(
        c0_snapshot=c0_snapshot(),
        c0_snapshot_path=c0_path,
        gold_scope=gold_scope(),
        gold_path=gold_path,
        db_snapshot=snapshot,
        db_dsn="host=localhost password=secret",
        parser_versions=["pdf-extract-v1", "pdf-extract-v2"],
        expected_location_type="pdf",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert "missing_location_json_count must be 0" in payload["blockers"]
    assert "PDF candidate artifact dir must not exist during C1" in payload["blockers"]


def test_pdf_scope_report_blocks_c0_scope_mismatch(tmp_path: Path):
    c0_path, gold_path = write_inputs(tmp_path)
    c0 = c0_snapshot()
    c0["scope"]["document_version_ids"] = ["docv_other"]

    payload = scope_module.build_payload(
        c0_snapshot=c0,
        c0_snapshot_path=c0_path,
        gold_scope=gold_scope(),
        gold_path=gold_path,
        db_snapshot=db_snapshot(),
        db_dsn="host=localhost password=secret",
        parser_versions=["pdf-extract-v1", "pdf-extract-v2"],
        expected_location_type="pdf",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert any("differs from C0 snapshot" in item for item in payload["blockers"])


def test_pdf_scope_report_blocks_missing_gold_docv(tmp_path: Path):
    c0_path, gold_path = write_inputs(tmp_path)
    gold = gold_scope()
    gold["missing_document_version_id_count"] = 1

    payload = scope_module.build_payload(
        c0_snapshot=c0_snapshot(),
        c0_snapshot_path=c0_path,
        gold_scope=gold,
        gold_path=gold_path,
        db_snapshot=db_snapshot(),
        db_dsn="host=localhost password=secret",
        parser_versions=["pdf-extract-v1", "pdf-extract-v2"],
        expected_location_type="pdf",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert "PDF gold rows must all have expected_document_version_id" in payload["blockers"]


def test_pdf_scope_report_blocks_pdf_bucket_location_mismatch(tmp_path: Path):
    c0_path, _ = write_inputs(tmp_path)
    gold_path = tmp_path / "gold_mismatch.csv"
    gold_path.write_text(
        "\n".join([
            "query_id,bucket,expected_location_type,expected_document_version_id,label_status,expected_file_name",
            "q_good,pdf_page_lookup,pdf,docv_pdf,bound,sample.pdf",
            "q_bad,pdf_table_lookup,xlsx,docv_xlsx,bound,sample.xlsx",
        ]),
        encoding="utf-8",
    )
    warnings: list[str] = []
    gold = scope_module.read_pdf_gold_scope(gold_path, "pdf", warnings)

    assert gold["pdf_query_count"] == 1
    assert gold["bucket_location_mismatch_count"] == 1
    assert gold["bucket_location_mismatch_query_ids"] == ["q_bad"]

    payload = scope_module.build_payload(
        c0_snapshot=c0_snapshot(),
        c0_snapshot_path=c0_path,
        gold_scope=gold,
        gold_path=gold_path,
        db_snapshot=db_snapshot(),
        db_dsn="host=localhost password=secret",
        parser_versions=["pdf-extract-v1", "pdf-extract-v2"],
        expected_location_type="pdf",
        blockers=[],
        warnings=warnings,
    )

    assert payload["status"] == "FAIL"
    assert "PDF gold rows must have matching pdf bucket and expected_location_type" in payload["blockers"]


def test_pdf_scope_report_warns_on_bbox_and_skipped_rows(tmp_path: Path):
    c0_path, gold_path = write_inputs(tmp_path)
    payload = scope_module.build_payload(
        c0_snapshot=c0_snapshot(),
        c0_snapshot_path=c0_path,
        gold_scope=gold_scope(),
        gold_path=gold_path,
        db_snapshot=db_snapshot(missing_bbox=2, ocr_bbox_missing=2, skipped=3),
        db_dsn="host=localhost password=secret",
        parser_versions=["pdf-extract-v1", "pdf-extract-v2"],
        expected_location_type="pdf",
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert "missing_required_bbox_count=2; C2/C3 location contract readiness must classify this" in payload["warnings"]
    assert "ocr_bbox_missing_count=2; C2/C3 OCR location readiness must classify this" in payload["warnings"]
    assert "embedding_status_counts.SKIPPED=3; C2/C3 embedding eligibility must classify skipped rows" in payload["warnings"]


def c0_snapshot() -> dict:
    return {
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "scope": {"document_version_ids": ["docv_pdf"]},
    }


def gold_scope() -> dict:
    return {
        "path": "gold.csv",
        "exists": True,
        "gold_row_count": 2,
        "pdf_query_count": 2,
        "pdf_positive_count": 2,
        "bucket_counts": {"pdf_page_lookup": 2},
        "missing_document_version_id_count": 0,
        "missing_document_version_query_ids": [],
        "document_version_ids": ["docv_pdf"],
        "expected_file_names": ["sample.pdf"],
    }


def db_snapshot(
    ocr_missing: int = 0,
    missing_bbox: int = 0,
    ocr_bbox_missing: int = 0,
    skipped: int = 0,
) -> dict:
    return {
        "summary": {
            "scoped_search_unit_count": 10,
            "candidate_rows": 10,
            "missing_location_json_count": 0,
            "missing_citation_text_count": 0,
            "missing_embedding_text_count": 0,
            "missing_required_bbox_count": missing_bbox,
            "missing_page_metadata_count": 0,
            "path_mixing_count": 0,
            "unsupported_parser_version_count": 0,
        },
        "page_metadata": {
            "missing_page_metadata_count": 0,
            "page_bound_search_unit_count": 10,
        },
        "ocr_summary": {
            "ocr_row_count": 3,
            "native_pdf_row_count": 7,
            "ocr_confidence_missing_count": ocr_missing,
            "ocr_bbox_missing_count": ocr_bbox_missing,
        },
        "parser_version_distribution": {"pdf-extract-v1": 10},
        "block_type_distribution": {"paragraph": 10},
        "chunk_type_distribution": {"paragraph": 10},
        "embedding_status_counts": {"EMBEDDED": 10 - skipped, "SKIPPED": skipped},
        "source_file_status_counts": {"READY": 1},
        "document_scope_details": [
            {
                "document_version_id": "docv_pdf",
                "document_version_exists": True,
                "source_file_id": "sf_pdf",
                "source_file_status": "READY",
                "scoped_search_unit_count": 10,
                "candidate_rows": 10,
            }
        ],
        "sample_warnings": [],
        "pdf_candidate_artifact": {"artifact_dir": "rag-data-pdf-candidate-v1", "exists": False},
    }


def write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    c0_path = tmp_path / "c0.json"
    gold_path = tmp_path / "gold.csv"
    c0_path.write_text(json.dumps(c0_snapshot()), encoding="utf-8")
    gold_path.write_text("query_id,bucket,expected_location_type\nq,pdf_page_lookup,pdf\n", encoding="utf-8")
    return c0_path, gold_path
