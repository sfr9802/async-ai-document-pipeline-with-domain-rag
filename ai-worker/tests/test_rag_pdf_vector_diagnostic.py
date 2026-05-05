from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "rag_pdf_vector_diagnostic.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_vector_diagnostic", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


diag = load_module()


def test_filter_pdf_positive_rows_keeps_only_bound_pdf_positive_rows():
    rows = [
        gold_row(query_id="pdf-1"),
        gold_row(query_id="pdf-pending", label_status="pending"),
        gold_row(query_id="pdf-negative", hidden_policy="negative"),
        gold_row(query_id="xlsx", expected_location_type="xlsx"),
    ]

    filtered = diag.filter_pdf_positive_rows(rows, expected_location_type="pdf", label_status="bound")

    assert [row["query_id"] for row in filtered] == ["pdf-1"]


def test_pdf_vector_diagnostic_builds_pass_payload(tmp_path: Path):
    rows = [gold_row()]
    evaluation = diag.evaluate_pdf_rows(
        rows,
        search_fn=lambda _query, _top_k: [pdf_hit()],
        top_k=10,
        index_version="rag-ingestion-v2-pdf-candidate-v1",
    )

    payload = diag.build_payload(
        evaluation=evaluation,
        all_rows=rows,
        filtered_rows=rows,
        args=args(tmp_path),
        c4_report=c4_report(),
        blockers=[],
        promotion_evidence=False,
        evidence_role="diagnostic",
    )

    assert payload["status"] == "PASS"
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["retrieval_backend"] == "vector"
    assert payload["query_level_results_available"] is True
    assert payload["gate_counters"]["required_index_version_mismatch_count"] == 0
    assert payload["metadata_projection_failure_count"] == 0
    assert payload["true_retrieval_ranking_failure_count"] == 0
    assert payload["metrics"]["pdf_citation_location_accuracy"] == 1.0


def test_pdf_vector_diagnostic_separates_ranking_failure(tmp_path: Path):
    rows = [gold_row()]
    evaluation = diag.evaluate_pdf_rows(
        rows,
        search_fn=lambda _query, _top_k: [pdf_hit(page_no=99)],
        top_k=10,
        index_version="rag-ingestion-v2-pdf-candidate-v1",
    )

    payload = diag.build_payload(
        evaluation=evaluation,
        all_rows=rows,
        filtered_rows=rows,
        args=args(tmp_path),
        c4_report=c4_report(),
        blockers=[],
        promotion_evidence=False,
        evidence_role="diagnostic",
    )

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["metadata_projection_failure_count"] == 0
    assert payload["true_retrieval_ranking_failure_count"] == 1
    assert payload["diagnostic_breakdown"]["failure_reason_counts"] == {
        "expected_page_not_found": 1,
    }


def test_pdf_vector_diagnostic_rejects_promotion_evidence(tmp_path: Path):
    blockers = diag.validate_prerequisites(
        c4_report=c4_report(),
        c4_report_path=tmp_path / "c4.json",
        index_version="rag-ingestion-v2-pdf-candidate-v1",
        artifact_dir=tmp_path / "rag-data-pdf-candidate-v1",
        promotion_evidence=True,
        evidence_role="diagnostic",
    )

    assert "C5 must keep promotion_evidence=false" in blockers


def args(tmp_path: Path) -> SimpleNamespace:
    artifact = tmp_path / "rag-data-pdf-candidate-v1"
    artifact.mkdir()
    (artifact / "build.json").write_text(
        json.dumps({
            "index_version": "rag-ingestion-v2-pdf-candidate-v1",
            "embedding_model": "BAAI/bge-m3",
            "dimension": 1024,
            "chunk_count": 1,
        }),
        encoding="utf-8",
    )
    (artifact / "ingest_manifest.json").write_text(
        json.dumps({
            "index_version": "rag-ingestion-v2-pdf-candidate-v1",
            "chunk_count": 1,
            "document_count": 1,
        }),
        encoding="utf-8",
    )
    (artifact / "faiss.index").write_bytes(b"idx")
    c4_path = tmp_path / "c4.json"
    c4_path.write_text(json.dumps(c4_report()), encoding="utf-8")
    return SimpleNamespace(
        gold="gold.csv",
        expected_location_type="pdf",
        label_status="bound",
        index_version="rag-ingestion-v2-pdf-candidate-v1",
        artifact_dir=str(artifact),
        c4_consistency_report=str(c4_path),
        db_dsn="host=localhost password=secret",
        embedding_model="BAAI/bge-m3",
        query_prefix="",
        passage_prefix="",
        max_seq_length=1024,
        batch_size=32,
        top_k=10,
    )


def c4_report() -> dict:
    return {
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "index_version": "rag-ingestion-v2-pdf-candidate-v1",
        "artifact_dir": "rag-data-pdf-candidate-v1",
        "scoped_summary": {"candidate_rows": 1},
    }


def gold_row(
    *,
    query_id: str = "pdf-1",
    label_status: str = "bound",
    hidden_policy: str = "",
    expected_location_type: str = "pdf",
) -> dict[str, str]:
    return {
        "query_id": query_id,
        "bucket": "pdf_page_lookup",
        "query": "find page",
        "expected_file_name": "doc.pdf",
        "expected_document_version_id": "docv_pdf",
        "expected_chunk_type": "paragraph",
        "expected_location_type": expected_location_type,
        "expected_sheet_name": "",
        "expected_cell_range": "",
        "expected_table_id": "",
        "expected_physical_page_index": "0",
        "expected_page_no": "1",
        "expected_page_label": "1",
        "expected_bbox": "[1, 2, 3, 4]",
        "expected_answer_text": "answer",
        "must_contain_terms": "",
        "must_not_contain_terms": "",
        "range_match_policy": "none",
        "hidden_policy": hidden_policy,
        "requires_formula_value": "false",
        "requires_formatted_value": "false",
        "requires_aggregation": "false",
        "source_sample_id": "sample",
        "label_status": label_status,
        "notes": "",
    }


def pdf_hit(*, page_no: int = 1) -> dict:
    location = {
        "type": "pdf",
        "document_version_id": "docv_pdf",
        "physical_page_index": 0,
        "page_no": page_no,
        "page_label": str(page_no),
        "bbox": [1, 2, 3, 4],
    }
    return {
        "rank": 1,
        "score": 0.9,
        "indexVersion": "rag-ingestion-v2-pdf-candidate-v1",
        "embeddingStatus": "EMBEDDED",
        "sourceFileName": "doc.pdf",
        "documentVersionId": "docv_pdf",
        "sourceFile": {
            "id": "sf_pdf",
            "sourceFileId": "sf_pdf",
            "originalFileName": "doc.pdf",
            "fileName": "doc.pdf",
        },
        "searchUnit": {
            "id": "unit-1",
            "searchUnitId": "unit-1",
            "embeddingStatus": "EMBEDDED",
            "indexVersion": "rag-ingestion-v2-pdf-candidate-v1",
            "chunkType": "paragraph",
            "locationType": "pdf",
            "locationJson": json.dumps(location),
            "citationText": "doc.pdf > p.1",
            "unitType": "CHUNK",
            "unitKey": "page:1:block:1",
            "documentVersionId": "docv_pdf",
        },
    }
