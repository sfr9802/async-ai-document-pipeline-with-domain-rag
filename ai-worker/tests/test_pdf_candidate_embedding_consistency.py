from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "pdf_candidate_embedding_consistency.py"
INDEXING_MODULE_PATH = ROOT / "scripts" / "rag_scoped_candidate_indexing.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


c4_module = load_module("pdf_candidate_embedding_consistency", MODULE_PATH)
indexing_module = load_module("rag_scoped_candidate_indexing", INDEXING_MODULE_PATH)


def test_pdf_candidate_consistency_passes_clean_scope(tmp_path: Path):
    scope_path = write_json(tmp_path / "scope.json", scope_report())
    c2_path = write_json(tmp_path / "c2.json", readiness_report("C2"))
    c3_path = write_json(tmp_path / "c3.json", readiness_report("C3"))
    indexing_path = write_json(tmp_path / "indexing.json", indexing_report())
    xlsx_dir = tmp_path / "rag-data-xlsx-candidate-v1"
    xlsx_dir.mkdir()
    (xlsx_dir / "build.json").write_text("{}", encoding="utf-8")
    baseline = write_json(tmp_path / "baseline.json", {"immutable": True})

    payload = c4_module.build_payload(
        scope_report=scope_report(),
        scope_report_path=scope_path,
        c2_report=readiness_report("C2"),
        c2_report_path=c2_path,
        c3_report=readiness_report("C3"),
        c3_report_path=c3_path,
        indexing_report=indexing_report(),
        indexing_report_path=indexing_path,
        db_rows=[candidate_row()],
        db_dsn="host=localhost password=secret",
        expected_index_version="rag-ingestion-v2-pdf-candidate-v1",
        blockers=[],
        warnings=[],
        xlsx_artifact_dir=xlsx_dir,
        immutable_baseline_path=baseline,
    )

    assert payload["status"] == "PASS"
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["allowUnscoped"] is False
    assert payload["db_dsn"] == "host=localhost password=<redacted>"
    assert payload["scoped_summary"]["candidate_rows"] == 1
    assert payload["scoped_summary"]["not_embedded_count"] == 0
    assert payload["scoped_summary"]["outside_scope_pdf_candidate_count"] == 0
    assert payload["indexing_reconciliation"]["previously_embedded_count"] == 0
    assert payload["artifact_guardrails"]["xlsx_artifact_changed"] is False
    assert payload["artifact_guardrails"]["immutable_baseline_changed"] is False


def test_pdf_candidate_consistency_blocks_missing_record_and_chunk_sha_mismatch(tmp_path: Path):
    missing_record = candidate_row()
    missing_record["id"] = "unit-missing-record"
    missing_record["embedding_record_id"] = None

    bad_chunk_sha = candidate_row()
    bad_chunk_sha["id"] = "unit-bad-chunk-sha"
    bad_chunk_sha["index_id"] = "source_file:sf_pdf:unit:CHUNK:page:7:block:2"
    bad_chunk_sha["chunk_id"] = bad_chunk_sha["index_id"]
    bad_chunk_sha["embedding_record_vector_id"] = (
        f"rag-ingestion-v2-pdf-candidate-v1:{bad_chunk_sha['index_id']}"
    )
    bad_chunk_sha["chunk_extra_json"]["vectorId"] = bad_chunk_sha["embedding_record_vector_id"]
    bad_chunk_sha["chunk_extra_json"]["embeddingTextSha256"] = "wrong"
    payload = c4_module.build_payload(
        scope_report=scope_report(),
        scope_report_path=write_json(tmp_path / "scope.json", scope_report()),
        c2_report=readiness_report("C2"),
        c2_report_path=write_json(tmp_path / "c2.json", readiness_report("C2")),
        c3_report=readiness_report("C3"),
        c3_report_path=write_json(tmp_path / "c3.json", readiness_report("C3")),
        indexing_report=indexing_report(),
        indexing_report_path=write_json(tmp_path / "indexing.json", indexing_report()),
        db_rows=[missing_record, bad_chunk_sha],
        db_dsn="dsn",
        expected_index_version="rag-ingestion-v2-pdf-candidate-v1",
        blockers=[],
        warnings=[],
        xlsx_artifact_dir=tmp_path / "missing-xlsx-dir",
        immutable_baseline_path=tmp_path / "missing-baseline.json",
    )

    assert payload["status"] == "FAIL"
    assert "embedding_record_missing_count must be 0" in payload["blockers"]
    assert "chunk_sha_mismatch_count must be 0" in payload["blockers"]
    failure_reasons = {
        reason
        for failure in payload["sample_failures"]
        for reason in failure["failure_reasons"]
    }
    assert "embedding_record_missing" in failure_reasons
    assert "chunk_sha_mismatch" in failure_reasons


def test_pdf_candidate_consistency_blocks_dry_run_indexing_report(tmp_path: Path):
    report = indexing_report()
    report["dryRun"] = True
    report["totals"] = {"claimed": 0, "indexed": 0, "failed": 0}

    payload = c4_module.build_payload(
        scope_report=scope_report(),
        scope_report_path=write_json(tmp_path / "scope.json", scope_report()),
        c2_report=readiness_report("C2"),
        c2_report_path=write_json(tmp_path / "c2.json", readiness_report("C2")),
        c3_report=readiness_report("C3"),
        c3_report_path=write_json(tmp_path / "c3.json", readiness_report("C3")),
        indexing_report=report,
        indexing_report_path=write_json(tmp_path / "indexing.json", report),
        db_rows=[candidate_row()],
        db_dsn="dsn",
        expected_index_version="rag-ingestion-v2-pdf-candidate-v1",
        blockers=[],
        warnings=[],
        xlsx_artifact_dir=tmp_path / "missing-xlsx-dir",
        immutable_baseline_path=tmp_path / "missing-baseline.json",
    )

    assert payload["status"] == "FAIL"
    assert "C4 indexing report must be non-dry-run" in payload["blockers"]
    assert "indexing_report.totals.claimed must be greater than 0" in payload["blockers"]


def test_pdf_candidate_consistency_blocks_outside_scope_candidates(tmp_path: Path):
    payload = c4_module.build_payload(
        scope_report=scope_report(),
        scope_report_path=write_json(tmp_path / "scope.json", scope_report()),
        c2_report=readiness_report("C2"),
        c2_report_path=write_json(tmp_path / "c2.json", readiness_report("C2")),
        c3_report=readiness_report("C3"),
        c3_report_path=write_json(tmp_path / "c3.json", readiness_report("C3")),
        indexing_report=indexing_report(),
        indexing_report_path=write_json(tmp_path / "indexing.json", indexing_report()),
        db_rows=[candidate_row()],
        outside_scope_rows=[{"id": "outside", "document_version_id": "docv_other"}],
        db_dsn="dsn",
        expected_index_version="rag-ingestion-v2-pdf-candidate-v1",
        blockers=[],
        warnings=[],
        xlsx_artifact_dir=tmp_path / "missing-xlsx-dir",
        immutable_baseline_path=tmp_path / "missing-baseline.json",
    )

    assert payload["status"] == "FAIL"
    assert payload["scoped_summary"]["outside_scope_pdf_candidate_count"] == 1
    assert "outside_scope_pdf_candidate_count must be 0" in payload["blockers"]


def test_scoped_candidate_indexing_scope_report_does_not_union_gold(tmp_path: Path):
    scope_path = write_json(tmp_path / "scope.json", scope_report())
    gold_path = tmp_path / "gold.csv"
    gold_path.write_text(
        "\n".join([
            "query_id,expected_document_version_id",
            "q1,docv_xlsx",
            "q2,docv_other_pdf",
        ]),
        encoding="utf-8",
    )
    args = indexing_module.parse_args([
        "--scope-report", str(scope_path),
        "--gold", str(gold_path),
        "--expected-index-version", "rag-ingestion-v2-pdf-candidate-v1",
    ])

    scope = indexing_module.load_scope(args)

    assert scope["document_version_ids"] == ["docv_pdf"]
    assert scope["source_file_ids"] == ["sf_pdf"]
    assert scope["source_file_types"] == ["PDF"]
    assert scope["parser_versions"] == ["pdf-extract-v1"]
    assert scope["expected_index_version"] == "rag-ingestion-v2-pdf-candidate-v1"


def test_scoped_candidate_indexing_uses_scope_report_expected_index_version(tmp_path: Path):
    scope_path = write_json(tmp_path / "scope.json", scope_report())
    args = indexing_module.parse_args(["--scope-report", str(scope_path)])
    scope = indexing_module.load_scope(args)

    assert indexing_module.resolve_expected_index_version(args, scope) == "rag-ingestion-v2-pdf-candidate-v1"


def test_scoped_candidate_indexing_rejects_scope_report_expected_index_version_mismatch(tmp_path: Path):
    scope_path = write_json(tmp_path / "scope.json", scope_report())
    args = indexing_module.parse_args([
        "--scope-report", str(scope_path),
        "--expected-index-version", "rag-ingestion-v2-candidate",
    ])
    scope = indexing_module.load_scope(args)

    try:
        indexing_module.resolve_expected_index_version(args, scope)
    except ValueError as exc:
        assert "scope report expectedIndexVersion must match" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def candidate_row() -> dict:
    text = "Source: sample.pdf\nCitation: sample.pdf > p.7\nPage: 7\nBlock: paragraph\nContent:\nGDP increased."
    sha = c4_module.sha256(text)
    location = {"type": "pdf", "page_no": 7, "physical_page_index": 6, "block_type": "paragraph", "ocr_used": False}
    vector_id = "rag-ingestion-v2-pdf-candidate-v1:source_file:sf_pdf:unit:CHUNK:page:7:block:1"
    return {
        "id": "unit-1",
        "document_version_id": "docv_pdf",
        "source_file_id": "sf_pdf",
        "source_file_name": "sample.pdf",
        "source_file_type": "PDF",
        "parser_version": "pdf-extract-v1",
        "unit_type": "CHUNK",
        "unit_key": "page:7:block:1",
        "chunk_type": "paragraph",
        "embedding_status": "EMBEDDED",
        "embedding_status_detail": None,
        "embedding_claimed_at": None,
        "index_id": "source_file:sf_pdf:unit:CHUNK:page:7:block:1",
        "index_version": "rag-ingestion-v2-pdf-candidate-v1",
        "embedding_text": text,
        "location_json": location,
        "citation_text": "sample.pdf > p.7",
        "embedding_record_id": "er-1",
        "embedding_record_model": "BAAI/bge-m3",
        "embedding_record_sha256": sha,
        "embedding_record_vector_id": vector_id,
        "chunk_id": "source_file:sf_pdf:unit:CHUNK:page:7:block:1",
        "chunk_index_version": "rag-ingestion-v2-pdf-candidate-v1",
        "chunk_text": text,
        "chunk_extra_json": {
            "embeddingTextSha256": sha,
            "vectorId": vector_id,
            "locationJson": location,
            "citationText": "sample.pdf > p.7",
        },
        "policy_excluded": False,
    }


def scope_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "source_file_type": "PDF",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "allowUnscoped": False,
        "scope": {
            "document_version_ids": ["docv_pdf"],
            "source_file_ids": ["sf_pdf"],
            "parser_versions": ["pdf-extract-v1"],
        },
        "indexing_cli_scope": {
            "documentVersionIds": ["docv_pdf"],
            "sourceFileIds": ["sf_pdf"],
            "sourceFileTypes": ["PDF"],
            "parserVersions": ["pdf-extract-v1"],
            "expectedIndexVersion": "rag-ingestion-v2-pdf-candidate-v1",
            "indexVersion": "rag-ingestion-v2-pdf-candidate-v1",
        },
        "warnings": [],
    }


def readiness_report(phase: str) -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "phase": phase,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "allowUnscoped": False,
        "warnings": [],
    }


def indexing_report() -> dict:
    return {
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "index_version": "rag-ingestion-v2-pdf-candidate-v1",
        "artifact_dir": "rag-data-pdf-candidate-v1",
        "dryRun": False,
        "allowUnscoped": False,
        "expectedIndexVersion": "rag-ingestion-v2-pdf-candidate-v1",
        "documentVersionIds": ["docv_pdf"],
        "sourceFileIds": ["sf_pdf"],
        "sourceFileTypes": ["PDF"],
        "parserVersions": ["pdf-extract-v1"],
        "totals": {"claimed": 1, "indexed": 1, "failed": 0, "stale": 0, "skipped_local": 0},
        "artifact_contract": {
            "expected_index_version": "rag-ingestion-v2-pdf-candidate-v1",
            "build_matches_expected_index_version": True,
            "manifest_matches_expected_index_version": True,
            "build_json": {"exists": True, "sha256": "build-sha"},
            "ingest_manifest_json": {"exists": True, "sha256": "manifest-sha"},
            "faiss_index": {"exists": True, "sha256": "faiss-sha"},
        },
    }


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
