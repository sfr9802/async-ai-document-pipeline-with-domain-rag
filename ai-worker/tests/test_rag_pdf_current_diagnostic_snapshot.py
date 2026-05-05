from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-worker" / "scripts" / "rag_pdf_current_diagnostic_snapshot.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_current_diagnostic_snapshot", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


snapshot_module = load_module()


def test_pdf_snapshot_passes_and_redacts_backend_identity(tmp_path: Path):
    fixture = make_fixture(tmp_path)

    payload = snapshot_module.build_snapshot(fixture.args)

    assert payload["status"] == "PASS"
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["pdf_query_coverage"]["complete"] is True
    assert payload["current_full72_report"]["backend_identity"]["db_dsn"] == "<redacted>"
    assert payload["current_full72_report"]["backend_identity"]["nested"] == "<redacted>"
    assert payload["current_full72_report"]["backend_identity"]["connection_uri"] == "<redacted>"
    assert "password=secret" not in json.dumps(payload)
    assert "secretpass" not in json.dumps(payload)
    assert payload["current_pdf_failure_counters"]["page_no_hit_at_top_k_count"] == 2
    assert payload["current_pdf_failure_counters"]["correct_page_no_hit_but_missing_physical_page_index_count"] == 1
    assert payload["current_pdf_failure_counters"]["correct_page_no_hit_but_missing_bbox_count"] == 1
    assert payload["side_effect_status"]["immutable_baseline_changed"] is False
    assert payload["side_effect_status"]["xlsx_candidate_artifact_changed"] is False
    assert payload["side_effect_status"]["pdf_candidate_artifact_exists"] is False


def test_pdf_snapshot_blocks_preexisting_pdf_candidate_artifact(tmp_path: Path):
    fixture = make_fixture(tmp_path)
    fixture.pdf_artifact_dir.mkdir()
    (fixture.pdf_artifact_dir / "faiss.index").write_bytes(b"unexpected-pdf-index")

    payload = snapshot_module.build_snapshot(fixture.args)

    assert payload["status"] == "FAIL"
    assert payload["pdf_candidate_artifact"]["exists"] is True
    assert payload["side_effect_status"]["pdf_candidate_artifact_changed"] is True
    assert any("PDF candidate artifact dir must not exist during C0" in item for item in payload["blockers"])


def test_pdf_snapshot_blocks_duplicate_and_missing_pdf_query_ids(tmp_path: Path):
    fixture = make_fixture(tmp_path)
    retrieval = read_json(fixture.retrieval_path)
    retrieval["query_results"] = [
        retrieval["query_results"][0],
        dict(retrieval["query_results"][0]),
    ]
    write_json(fixture.retrieval_path, retrieval)
    update_baseline_retrieval_hash(fixture)

    payload = snapshot_module.build_snapshot(fixture.args)

    assert payload["status"] == "FAIL"
    assert payload["pdf_query_coverage"]["duplicate_result_query_ids"] == ["q_pdf_1"]
    assert payload["pdf_query_coverage"]["missing_result_query_ids"] == ["q_pdf_2"]
    assert any("duplicate PDF result query_ids" in item for item in payload["blockers"])
    assert any("PDF query results missing ids" in item for item in payload["blockers"])


def test_pdf_snapshot_blocks_malformed_pdf_result_without_query_id(tmp_path: Path):
    fixture = make_fixture(tmp_path)
    retrieval = read_json(fixture.retrieval_path)
    retrieval["query_results"].append({
        "bucket": "pdf_page_lookup",
        "failure_reason": "expected_page_not_found",
        "top_k_results": [],
    })
    write_json(fixture.retrieval_path, retrieval)
    update_baseline_retrieval_hash(fixture)

    payload = snapshot_module.build_snapshot(fixture.args)

    assert payload["status"] == "FAIL"
    assert payload["pdf_query_coverage"]["complete"] is False
    assert payload["pdf_query_coverage"]["malformed_result_rows"] == [
        {"result_index": 2, "bucket": "pdf_page_lookup", "reason": "missing query_id"}
    ]
    assert any("malformed rows" in item for item in payload["blockers"])


def test_pdf_snapshot_blocks_baseline_artifact_mismatch(tmp_path: Path):
    fixture = make_fixture(tmp_path)
    (fixture.baseline_artifact_dir / "build.json").write_text("changed", encoding="utf-8")

    payload = snapshot_module.build_snapshot(fixture.args)

    assert payload["status"] == "FAIL"
    assert payload["immutable_baseline"]["baseline_changed"] is True
    assert any("immutable baseline" in item for item in payload["blockers"])


def test_pdf_snapshot_blocks_xlsx_artifact_mismatch(tmp_path: Path):
    fixture = make_fixture(tmp_path)
    (fixture.xlsx_artifact_dir / "ingest_manifest.json").write_text("changed", encoding="utf-8")

    payload = snapshot_module.build_snapshot(fixture.args)

    assert payload["status"] == "FAIL"
    assert payload["xlsx_candidate_artifact"]["xlsx_candidate_artifact_changed"] is True
    assert any("XLSX candidate artifact changed" in item for item in payload["blockers"])


def make_fixture(tmp_path: Path) -> SimpleNamespace:
    baseline_artifact_dir = tmp_path / "rag-data-canary"
    xlsx_artifact_dir = tmp_path / "rag-data-xlsx-candidate-v1"
    pdf_artifact_dir = tmp_path / "rag-data-pdf-candidate-v1"
    baseline_hashes = write_artifact_dir(baseline_artifact_dir, "baseline")
    xlsx_hashes = write_artifact_dir(xlsx_artifact_dir, "xlsx")

    retrieval_path = tmp_path / "retrieval.json"
    gold_path = tmp_path / "gold.csv"
    quality_path = tmp_path / "quality.json"
    baseline_path = tmp_path / "baseline.json"
    lineage_path = tmp_path / "lineage.json"
    output_path = tmp_path / "snapshot.json"

    write_gold(gold_path)
    write_json(retrieval_path, retrieval_payload())
    write_json(quality_path, quality_payload())
    write_json(
        baseline_path,
        {
            "baseline_index_version": "initial-full72-vector-baseline-v0",
            "baseline_type": "INITIAL_BASELINE_BOOTSTRAP",
            "bootstrap_status": "BOOTSTRAP_READY_NOT_PROMOTION",
            "promotion_evidence": False,
            "retrieval_report_sha256": sha256_file(retrieval_path),
            "faiss_artifact_hashes": baseline_hashes,
        },
    )
    write_json(
        lineage_path,
        {
            "xlsx_candidate": {
                "index_version": "rag-ingestion-v2-xlsx-candidate-v1",
                "namespace": "rag-ingestion-v2-xlsx-candidate-v1",
                "artifact_hashes": xlsx_hashes,
            }
        },
    )

    args = SimpleNamespace(
        retrieval_report=str(retrieval_path),
        quality_breakdown=str(quality_path),
        gold=str(gold_path),
        baseline_descriptor=str(baseline_path),
        baseline_artifact_dir=str(baseline_artifact_dir),
        lineage_report=str(lineage_path),
        xlsx_candidate_artifact_dir=str(xlsx_artifact_dir),
        pdf_index_version="rag-ingestion-v2-pdf-candidate-v1",
        pdf_artifact_dir=str(pdf_artifact_dir),
        output=str(output_path),
    )
    return SimpleNamespace(
        args=args,
        retrieval_path=retrieval_path,
        baseline_path=baseline_path,
        baseline_artifact_dir=baseline_artifact_dir,
        xlsx_artifact_dir=xlsx_artifact_dir,
        pdf_artifact_dir=pdf_artifact_dir,
    )


def retrieval_payload() -> dict:
    return {
        "status": "COMPLETED",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_backend": "vector",
        "backend_identity": {
            "backend": "faiss",
            "db_dsn": "host=localhost password=secret",
            "connection_uri": "postgresql://user:secretpass@localhost/db",
            "index_namespace_filter": "rag-ingestion-v2-candidate",
            "nested": {"api_token": "token=abc123"},
        },
        "candidate_index_version": "rag-ingestion-v2-candidate",
        "required_index_version": "rag-ingestion-v2-candidate",
        "required_embedding_status": "EMBEDDED",
        "top_k": 10,
        "validation": {"ok": True, "row_count": 2},
        "metrics": {
            "pdf_file_hit@10": 1.0,
            "pdf_page_hit@10": 0.5,
            "pdf_bbox_overlap@10": 0.5,
            "pdf_exact_bbox@10": 0.0,
            "pdf_citation_location_accuracy": 0.5,
            "result_empty_count": 0,
            "candidate_index_mismatch_count": 0,
            "embedding_status_mismatch_count": 0,
            "required_index_version_mismatch_count": 0,
        },
        "query_results": [
            pdf_query_result(
                "q_pdf_1",
                page_no=1,
                physical_page_index=None,
                bbox=None,
                pdf_page_match=False,
                pdf_bbox_overlap=False,
                location_match=False,
            ),
            pdf_query_result(
                "q_pdf_2",
                page_no=2,
                physical_page_index=1,
                bbox=[1.0, 2.0, 3.0, 4.0],
                pdf_page_match=True,
                pdf_bbox_overlap=True,
                location_match=True,
            ),
        ],
    }


def pdf_query_result(
    query_id: str,
    *,
    page_no: int,
    physical_page_index: int | None,
    bbox: list[float] | None,
    pdf_page_match: bool,
    pdf_bbox_overlap: bool,
    location_match: bool,
) -> dict:
    return {
        "query_id": query_id,
        "bucket": "pdf_page_lookup",
        "failure_reason": None if location_match else "expected_page_not_found",
        "location_match": location_match,
        "top_k_results": [
            {
                "rank": 1,
                "match_breakdown": {
                    "file_match": True,
                    "document_version_match": True,
                    "pdf_page_match": pdf_page_match,
                    "pdf_bbox_overlap": pdf_bbox_overlap,
                    "pdf_exact_bbox": False,
                },
                "location_json": {
                    "type": "pdf",
                    "page_no": page_no,
                    "physical_page_index": physical_page_index,
                    "bbox": bbox,
                },
            }
        ],
    }


def quality_payload() -> dict:
    return {
        "status": "COMPLETED",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "pdf_page_bbox_failure_breakdown": {
            "query_count": 2,
            "diagnostic_flag_counts": {
                "correct_page_no_hit_but_missing_physical_page_index": 1,
                "correct_page_no_hit_but_missing_bbox": 1,
            },
        },
    }


def write_gold(path: Path) -> None:
    fieldnames = [
        "query_id",
        "bucket",
        "expected_location_type",
        "expected_file_name",
        "expected_document_version_id",
        "expected_page_no",
        "expected_physical_page_index",
        "expected_bbox",
        "label_status",
    ]
    rows = [
        {
            "query_id": "q_pdf_1",
            "bucket": "pdf_page_lookup",
            "expected_location_type": "pdf",
            "expected_file_name": "sample.pdf",
            "expected_document_version_id": "docv_pdf",
            "expected_page_no": "1",
            "expected_physical_page_index": "0",
            "expected_bbox": "[1,2,3,4]",
            "label_status": "bound",
        },
        {
            "query_id": "q_pdf_2",
            "bucket": "pdf_page_lookup",
            "expected_location_type": "pdf",
            "expected_file_name": "sample.pdf",
            "expected_document_version_id": "docv_pdf",
            "expected_page_no": "2",
            "expected_physical_page_index": "1",
            "expected_bbox": "[1,2,3,4]",
            "label_status": "bound",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_artifact_dir(path: Path, prefix: str) -> dict[str, str]:
    path.mkdir(parents=True)
    values = {
        "faiss.index": f"{prefix}-faiss".encode("utf-8"),
        "build.json": json.dumps({"index_version": prefix}).encode("utf-8"),
        "ingest_manifest.json": json.dumps({"embedding_model": "test"}).encode("utf-8"),
    }
    for name, content in values.items():
        (path / name).write_bytes(content)
    return {name: sha256_file(path / name) for name in values}


def update_baseline_retrieval_hash(fixture: SimpleNamespace) -> None:
    baseline = read_json(fixture.baseline_path)
    baseline["retrieval_report_sha256"] = sha256_file(fixture.retrieval_path)
    write_json(fixture.baseline_path, baseline)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
