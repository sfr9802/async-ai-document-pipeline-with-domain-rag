from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "scripts" / "rag_pdf_search_unit_surface_repair.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_search_unit_surface_repair", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


repair_module = load_module()


def test_canonical_embedding_text_adds_pdf_context_and_ocr_marker():
    row = pdf_row(
        embedding_text="raw text",
        location_json={
            "type": "pdf",
            "page_no": 7,
            "block_type": "paragraph",
            "ocr_used": True,
            "ocr_confidence": 0.91,
        },
    )

    text = repair_module.canonical_embedding_text(row)

    assert "Source: sample.pdf" in text
    assert "Citation: sample.pdf > p.7 > bbox [1,2,3,4]" in text
    assert "Chunk: paragraph" in text
    assert "Page: 7" in text
    assert "Block: paragraph" in text
    assert "OCR: used" in text
    assert "OCR confidence: 0.91" in text
    assert "Content:\nGDP increased." in text


def test_needs_repair_for_raw_pdf_embedding_text():
    row = pdf_row(embedding_text="GDP increased.")

    assert repair_module.needs_repair(row) is True
    assert repair_module.repair_reasons(row) == [
        "missing_source_file_surface_in_embedding_text",
        "missing_page_surface_in_embedding_text",
        "missing_citation_surface_in_embedding_text",
        "missing_block_type_surface_in_embedding_text",
    ]


def test_does_not_repair_policy_excluded_rows():
    row = pdf_row(embedding_text="raw", policy_excluded=True)

    assert repair_module.needs_repair(row) is False
    assert repair_module.needs_state_reset(row) is False
    assert repair_module.repair_reasons(row) == []


def test_state_reset_needed_for_structured_embedded_legacy_row():
    text = "\n".join([
        "Source: sample.pdf",
        "Citation: sample.pdf > p.7 > bbox [1,2,3,4]",
        "Chunk: paragraph",
        "Page: 7",
        "Block: paragraph",
        "Content:\nGDP increased.",
    ])
    row = pdf_row(embedding_text=text)

    assert repair_module.needs_repair(row) is False
    assert repair_module.needs_state_reset(row) is True
    assert repair_module.sample_for_report(row)["repair_reasons"] == ["stale_embedding_state_reset"]


def test_build_payload_marks_dry_run_with_repairs_as_warning(tmp_path: Path):
    c1_path = write_c1(tmp_path)
    before = {
        "summary": {
            "scoped_rows": 2,
            "indexable_rows": 1,
            "policy_excluded_rows": 1,
            "repair_needed_count": 1,
            "state_reset_needed_count": 2,
            "mutation_needed_count": 2,
        }
    }

    payload = repair_module.build_payload(
        scope_report=c1_report(),
        scope_report_path=c1_path,
        db_dsn="host=localhost password=secret",
        before=before,
        after=before,
        samples=[repair_module.sample_for_report(pdf_row(embedding_text="raw"))],
        mutations={"apply": False, "updated_search_unit_count": 0},
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["promotion_evidence"] is False
    assert payload["allowUnscoped"] is False
    assert payload["db_dsn"] == "host=localhost password=<redacted>"
    assert payload["warnings"] == ["dry_run_mutation_needed_count=2; rerun with --apply to mutate scoped DB rows"]


def test_build_payload_blocks_when_apply_leaves_repairs(tmp_path: Path):
    c1_path = write_c1(tmp_path)
    after = {"summary": {"mutation_needed_count": 1}}

    payload = repair_module.build_payload(
        scope_report=c1_report(),
        scope_report_path=c1_path,
        db_dsn="host=localhost password=secret",
        before={"summary": {"mutation_needed_count": 2}},
        after=after,
        samples=[],
        mutations={"apply": True, "updated_search_unit_count": 1},
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert "mutation_needed_count must be 0 after apply" in payload["blockers"]


def pdf_row(
    *,
    embedding_text: str,
    location_json: dict | None = None,
    policy_excluded: bool = False,
) -> dict:
    location = location_json or {
        "type": "pdf",
        "page_no": 7,
        "block_type": "paragraph",
        "ocr_used": False,
    }
    return {
        "id": "unit-1",
        "document_version_id": "docv_pdf",
        "source_file_name": "sample.pdf",
        "unit_type": "CHUNK",
        "chunk_type": "paragraph",
        "text_content": "GDP increased.",
        "embedding_text": embedding_text,
        "content_sha256": "old",
        "citation_text": "sample.pdf > p.7 > bbox [1,2,3,4]",
        "location_json": location,
        "metadata_json": {},
        "embedding_status": "EMBEDDED",
        "index_version": "rag-ingestion-v2-candidate",
        "policy_excluded": policy_excluded,
    }


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


def write_c1(tmp_path: Path) -> Path:
    c1_path = tmp_path / "c1.json"
    c1_path.write_text(json.dumps(c1_report()), encoding="utf-8")
    return c1_path
