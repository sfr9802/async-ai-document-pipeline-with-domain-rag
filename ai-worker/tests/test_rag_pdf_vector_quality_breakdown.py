from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "rag_pdf_vector_quality_breakdown.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


c6_module = load_module("rag_pdf_vector_quality_breakdown", MODULE_PATH)


def test_c6_classifies_bbox_policy_and_records_next_action():
    payload = c6_module.build_breakdown(
        eval_report=eval_report([
            query_result(
                failure_reason="bbox_mismatch",
                expected_bbox="[10, 10, 20, 20]",
                top_k_results=[
                    hit(rank=1, page_no=7, file_match=True, docv_match=True, bbox=True),
                    hit(
                        rank=2,
                        page_no=1,
                        chunk_type="page",
                        file_match=True,
                        docv_match=True,
                        page_match=True,
                        bbox=False,
                    ),
                ],
            )
        ]),
        gold_rows=[gold_row(expected_bbox="[10, 10, 20, 20]")],
        c2_report=c2_report(),
        eval_report_path=Path("c5.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["status"] == "PASS"
    assert payload["unknown_failure_count"] == 0
    assert payload["gold_policy_candidate_count"] == 1
    row = payload["classified_query_rows"][0]
    assert row["failure_type"] == "PDF_BBOX_POLICY_MISMATCH"
    assert row["next_action"]


def test_c6_resolves_unknown_chunk_granularity():
    payload = c6_module.build_breakdown(
        eval_report=eval_report([
            query_result(
                query_id="q-chunk",
                failure_reason="unknown",
                expected_bbox="",
                top_k_results=[
                    hit(
                        rank=1,
                        page_no=12,
                        chunk_type="paragraph",
                        file_match=True,
                        docv_match=True,
                        page_match=True,
                        location_match=True,
                        chunk_type_match=False,
                    )
                ],
            )
        ]),
        gold_rows=[gold_row(query_id="q-chunk", expected_chunk_type="page", expected_bbox="")],
        c2_report=c2_report(),
        eval_report_path=Path("c5.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["status"] == "PASS"
    assert payload["unknown_failure_count"] == 0
    assert payload["chunk_granularity_candidate_count"] == 1
    assert payload["classified_query_rows"][0]["failure_type"] == "PDF_CHUNK_GRANULARITY_ISSUE"


def test_c6_classifies_table_gold_binding_before_ranking():
    payload = c6_module.build_breakdown(
        eval_report=eval_report([
            query_result(
                query_id="q-table",
                bucket="pdf_table_lookup",
                failure_reason="expected_page_not_found",
                top_k_results=[
                    hit(rank=1, page_no=51, file_match=True, docv_match=True, bbox=True),
                ],
            )
        ]),
        gold_rows=[gold_row(query_id="q-table", bucket="pdf_table_lookup")],
        c2_report=c2_report(),
        eval_report_path=Path("c5.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["status"] == "PASS"
    assert payload["gold_policy_candidate_count"] == 1
    assert payload["true_retrieval_ranking_failure_count"] == 0
    assert payload["classified_query_rows"][0]["failure_type"] == "PDF_TABLE_GOLD_BINDING_MISMATCH"


def test_c6_blocks_bad_gate_counter():
    report = eval_report([query_result(failure_reason=None, location_match=True)])
    report["gate_counters"] = {"wrong_index_version_hit_count": 1}

    payload = c6_module.build_breakdown(
        eval_report=report,
        gold_rows=[gold_row()],
        c2_report=c2_report(),
        eval_report_path=Path("c5.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["status"] == "FAIL"
    assert "C5 gate counter wrong_index_version_hit_count must be 0" in payload["blockers"]


def eval_report(rows: list[dict]) -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "retrieval_backend": "vector",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "index_version": "rag-ingestion-v2-pdf-candidate-v1",
        "artifact_dir": "rag-data-pdf-candidate-v1",
        "gate_counters": {
            "candidate_index_mismatch_count": 0,
            "required_index_version_mismatch_count": 0,
            "embedding_status_mismatch_count": 0,
        },
        "query_results": rows,
    }


def query_result(
    *,
    query_id: str = "q1",
    bucket: str = "pdf_page_lookup",
    failure_reason: str | None = "expected_page_not_found",
    expected_bbox: str = "[1, 2, 3, 4]",
    location_match: bool = False,
    top_k_results: list[dict] | None = None,
) -> dict:
    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": "query",
        "expected_file_name": "sample.pdf",
        "expected_page_no": "1",
        "expected_physical_page_index": "0",
        "expected_bbox": expected_bbox,
        "label_status": "bound",
        "top_k_results": top_k_results or [],
        "hit_rank": 1 if top_k_results else None,
        "location_rank": None,
        "hit_at_10": bool(top_k_results),
        "location_match": location_match,
        "failure_reason": failure_reason,
    }


def hit(
    *,
    rank: int,
    page_no: int,
    chunk_type: str = "paragraph",
    file_match: bool = True,
    docv_match: bool = True,
    page_match: bool = False,
    location_match: bool = False,
    bbox: bool = False,
    chunk_type_match: bool = True,
) -> dict:
    location = {
        "type": "pdf",
        "document_version_id": "docv_pdf",
        "page_no": page_no,
        "physical_page_index": page_no - 1,
    }
    if bbox:
        location["bbox"] = [1, 2, 3, 4]
    return {
        "rank": rank,
        "search_unit_id": f"su-{rank}",
        "source_file_name": "sample.pdf",
        "chunk_type": chunk_type,
        "citation_text": f"sample.pdf > p.{page_no}",
        "location_json": location,
        "match_breakdown": {
            "file_match": file_match,
            "document_version_match": docv_match,
            "chunk_type_match": chunk_type_match,
            "pdf_page_match": page_match,
            "pdf_bbox_overlap": bbox and page_match,
            "location_match": location_match,
        },
    }


def gold_row(
    *,
    query_id: str = "q1",
    bucket: str = "pdf_page_lookup",
    expected_chunk_type: str = "paragraph",
    expected_bbox: str = "[1, 2, 3, 4]",
) -> dict:
    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": "query",
        "expected_file_name": "sample.pdf",
        "expected_document_version_id": "docv_pdf",
        "expected_chunk_type": expected_chunk_type,
        "expected_location_type": "pdf",
        "expected_page_no": "1",
        "expected_physical_page_index": "0",
        "expected_bbox": expected_bbox,
        "label_status": "bound",
    }


def c2_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
    }
