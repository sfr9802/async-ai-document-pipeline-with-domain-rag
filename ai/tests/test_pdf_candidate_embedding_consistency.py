from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "scripts" / "pdf_candidate_embedding_consistency.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pdf_candidate_embedding_consistency", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


c4_module = load_module()


def test_c4_passes_with_carried_warnings_and_diagnostic_identity(tmp_path: Path):
    paths = fixture_paths(tmp_path)
    payload = c4_module.build_payload(
        c0_snapshot=c0_snapshot(paths),
        c0_path=write_json(tmp_path / "c0.json", {"status": "PASS"}),
        c1_report=c1_report(),
        c1_path=write_json(tmp_path / "c1.json", c1_report()),
        c2_report=c2_report(),
        c2_path=write_json(tmp_path / "c2.json", c2_report()),
        c3_report=c3_report(),
        c3_path=write_json(tmp_path / "c3.json", c3_report()),
        repair_report=repair_report(),
        repair_path=write_json(tmp_path / "repair.json", repair_report()),
        db_snapshot=db_snapshot(),
        db_dsn="host=localhost password=secret",
        expected_index_version="rag-ingestion-v2-pdf-candidate-v1",
        artifact_dir=paths["pdf"],
        baseline_artifact_dir=paths["baseline"],
        xlsx_artifact_dir=paths["xlsx"],
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["allowUnscoped"] is False
    assert payload["candidate_namespace_chunk_count"] == 10
    assert payload["candidate_chunk_count_matches_indexable_rows"] is True
    assert payload["c5_ready"] is True
    assert payload["immutable_baseline_changed"] is False
    assert payload["xlsx_candidate_artifact_changed"] is False
    assert payload["warnings_carried_forward"] == [
        "OCR confidence missing rows are policy-excluded before C4: 6",
        "document summaries are policy-excluded before C4: 3",
        "skipped searchable rows remain visible for C4 exclusion: 9",
        "current PDF table gold rows have no table-like SearchUnits: 6",
    ]


def test_c4_fails_when_candidate_namespace_count_mismatches_indexable_rows(tmp_path: Path):
    paths = fixture_paths(tmp_path)
    snapshot = db_snapshot()
    snapshot["namespace_summary"]["candidate_namespace_chunk_count"] = 9

    payload = c4_module.build_payload(
        c0_snapshot=c0_snapshot(paths),
        c0_path=write_json(tmp_path / "c0.json", {"status": "PASS"}),
        c1_report=c1_report(),
        c1_path=write_json(tmp_path / "c1.json", c1_report()),
        c2_report=c2_report(),
        c2_path=write_json(tmp_path / "c2.json", c2_report()),
        c3_report=c3_report(),
        c3_path=write_json(tmp_path / "c3.json", c3_report()),
        repair_report=repair_report(),
        repair_path=write_json(tmp_path / "repair.json", repair_report()),
        db_snapshot=snapshot,
        db_dsn="host=localhost password=secret",
        expected_index_version="rag-ingestion-v2-pdf-candidate-v1",
        artifact_dir=paths["pdf"],
        baseline_artifact_dir=paths["baseline"],
        xlsx_artifact_dir=paths["xlsx"],
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert payload["candidate_chunk_count_matches_indexable_rows"] is False
    assert any("candidate_namespace_chunk_count must equal indexable rows" in item for item in payload["blockers"])


def test_c4_fails_on_scope_leakage_and_metadata_blockers(tmp_path: Path):
    paths = fixture_paths(tmp_path)
    snapshot = db_snapshot()
    snapshot["namespace_summary"]["unexpected_sourceFileId_count"] = 1
    snapshot["namespace_summary"]["non_pdf_row_count"] = 1
    snapshot["metadata_projection_counters"]["unusable_location_count"] = 1
    snapshot["embedding_text_contract_counters"]["ocr_trust_marker_missing_count"] = 1

    payload = c4_module.build_payload(
        c0_snapshot=c0_snapshot(paths),
        c0_path=write_json(tmp_path / "c0.json", {"status": "PASS"}),
        c1_report=c1_report(),
        c1_path=write_json(tmp_path / "c1.json", c1_report()),
        c2_report=c2_report(),
        c2_path=write_json(tmp_path / "c2.json", c2_report()),
        c3_report=c3_report(),
        c3_path=write_json(tmp_path / "c3.json", c3_report()),
        repair_report=repair_report(),
        repair_path=write_json(tmp_path / "repair.json", repair_report()),
        db_snapshot=snapshot,
        db_dsn="host=localhost password=secret",
        expected_index_version="rag-ingestion-v2-pdf-candidate-v1",
        artifact_dir=paths["pdf"],
        baseline_artifact_dir=paths["baseline"],
        xlsx_artifact_dir=paths["xlsx"],
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert "unexpected_sourceFileId_count must be 0" in payload["blockers"]
    assert "non_pdf_row_count must be 0" in payload["blockers"]
    assert "unusable_location_count must be 0" in payload["blockers"]
    assert "ocr_trust_marker_missing_count must be 0" in payload["blockers"]


def test_c4_fails_on_bad_input_report_guardrails(tmp_path: Path):
    paths = fixture_paths(tmp_path)
    c1 = c1_report()
    c1["allowUnscoped"] = True
    c1["indexing_cli_scope"]["allowUnscoped"] = True

    payload = c4_module.build_payload(
        c0_snapshot=c0_snapshot(paths),
        c0_path=write_json(tmp_path / "c0.json", {"status": "PASS"}),
        c1_report=c1,
        c1_path=write_json(tmp_path / "c1.json", c1),
        c2_report=c2_report(),
        c2_path=write_json(tmp_path / "c2.json", c2_report()),
        c3_report=c3_report(),
        c3_path=write_json(tmp_path / "c3.json", c3_report()),
        repair_report=repair_report(),
        repair_path=write_json(tmp_path / "repair.json", repair_report()),
        db_snapshot=db_snapshot(),
        db_dsn="host=localhost password=secret",
        expected_index_version="rag-ingestion-v2-pdf-candidate-v1",
        artifact_dir=paths["pdf"],
        baseline_artifact_dir=paths["baseline"],
        xlsx_artifact_dir=paths["xlsx"],
        blockers=[],
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert "C1 scope report must keep allowUnscoped=false" in payload["blockers"]
    assert "C1 indexing_cli_scope must keep allowUnscoped=false" in payload["blockers"]


def fixture_paths(tmp_path: Path) -> dict[str, Path]:
    baseline = tmp_path / "baseline"
    xlsx = tmp_path / "xlsx"
    pdf = tmp_path / "pdf"
    for path in (baseline, xlsx, pdf):
        path.mkdir()
        (path / "faiss.index").write_text(path.name, encoding="utf-8")
        (path / "ingest_manifest.json").write_text("{}", encoding="utf-8")
    (baseline / "build.json").write_text('{"index_version":"baseline","chunk_count":10}', encoding="utf-8")
    (xlsx / "build.json").write_text('{"index_version":"xlsx","chunk_count":10}', encoding="utf-8")
    (pdf / "build.json").write_text(
        '{"index_version":"rag-ingestion-v2-pdf-candidate-v1","chunk_count":10}',
        encoding="utf-8",
    )
    return {"baseline": baseline, "xlsx": xlsx, "pdf": pdf}


def c0_snapshot(paths: dict[str, Path]) -> dict:
    return {
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "immutable_baseline": artifact_section(paths["baseline"]),
        "xlsx_candidate_artifact": artifact_section(paths["xlsx"]),
    }


def artifact_section(path: Path) -> dict:
    checks = []
    for name in c4_module.ARTIFACT_FILES:
        target = path / name
        checks.append({
            "name": name,
            "observed_sha256": c4_module.file_sha256(target) if target.exists() else None,
            "status": "MATCH",
        })
    return {"artifact_hash_checks": checks}


def c1_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "allowUnscoped": False,
        "index_version": "rag-ingestion-v2-pdf-candidate-v1",
        "scope": {
            "document_version_ids": ["docv_pdf"],
            "source_file_ids": ["sf_pdf"],
            "parser_versions": ["pdf-extract-v1", "pdf-extract-v2"],
        },
        "indexing_cli_scope": {
            "sourceFileTypes": ["PDF"],
            "parserVersions": ["pdf-extract-v1", "pdf-extract-v2"],
            "documentVersionIds": ["docv_pdf"],
            "sourceFileIds": ["sf_pdf"],
            "expectedIndexVersion": "rag-ingestion-v2-pdf-candidate-v1",
            "allowUnscoped": False,
        },
        "warnings": [],
    }


def c2_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "summary": {
            "scoped_rows": 19,
            "indexable_rows": 10,
            "policy_excluded_rows": 9,
            "policy_excluded_ocr_confidence_missing_count": 6,
            "policy_excluded_document_summary_count": 3,
        },
    }


def c3_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "summary": {
            "scoped_rows": 19,
            "indexable_rows": 10,
            "policy_excluded_rows": 9,
            "skipped_searchable_row_count": 9,
        },
        "table_contract": {
            "pdf_table_gold_count": 6,
            "table_like_search_unit_count": 0,
        },
    }


def repair_report() -> dict:
    return {
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "repair_diagnostic",
    }


def db_snapshot() -> dict:
    return {
        "scoped_summary": {
            "scoped_search_unit_count": 19,
            "indexable_search_unit_count": 10,
            "policy_excluded_search_unit_count": 9,
            "not_embedded_count": 0,
            "index_version_mismatch_count": 0,
            "embedding_record_missing_count": 0,
            "candidate_chunk_missing_count": 0,
            "vector_namespace_mismatch_count": 0,
            "chunk_sha_mismatch_count": 0,
        },
        "namespace_summary": {
            "candidate_namespace_chunk_count": 10,
            "unexpected_sourceFileId_count": 0,
            "unexpected_documentVersionId_count": 0,
            "non_pdf_row_count": 0,
            "policy_excluded_leakage_count": 0,
        },
        "metadata_projection_counters": {
            "missing_location_json_locationJson_count": 0,
            "jackson_jsonnode_shape_location_count": 0,
            "unusable_location_count": 0,
            "missing_physical_page_index_count": 0,
            "missing_page_no_count": 0,
            "missing_bbox_count": 0,
            "missing_citation_text_count": 0,
        },
        "embedding_text_contract_counters": {
            "missing_embedding_text_count": 0,
            "missing_source_page_citation_block_surface_count": 0,
            "ocr_trust_marker_missing_count": 0,
        },
        "sample_failures": [],
    }


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
