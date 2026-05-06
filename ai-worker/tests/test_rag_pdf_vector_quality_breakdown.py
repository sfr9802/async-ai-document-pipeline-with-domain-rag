from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-worker" / "scripts" / "rag_pdf_vector_quality_breakdown.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_vector_quality_breakdown", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


c6_module = load_module()


def test_c6_classifies_pdf_failures_without_unknowns(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    c5 = c5_report([
        query_row("q_match", "pdf_page_lookup", location_match=True, hits=[
            hit(rank=1, page_no=1, bbox=[0, 0, 10, 10], location_match=True, bbox_overlap=True),
            hit(rank=2, page_no=1, bbox=None, location_match=False, bbox_overlap=False),
        ]),
        query_row("q_meta", "pdf_page_lookup", failure_reason="bbox_mismatch", hits=[
            hit(rank=1, page_no=1, bbox=None, location_match=False, bbox_overlap=False),
        ]),
        query_row("q_table", "pdf_table_lookup", failure_reason="expected_page_not_found", hits=[
            hit(rank=1, page_no=9, bbox=[0, 0, 10, 10], location_match=False, bbox_overlap=False),
        ]),
        query_row("q_chunk", "pdf_section_question", failure_reason="unknown", hits=[
            hit(rank=1, page_no=1, bbox=[0, 0, 10, 10], location_match=True, chunk_type="paragraph", chunk_type_match=False),
        ]),
        query_row("q_file", "pdf_section_question", failure_reason="expected_file_not_found", hits=[
            hit(rank=1, page_no=1, bbox=[0, 0, 10, 10], file_match=False, docv_match=False),
        ]),
        query_row("q_page", "pdf_page_lookup", failure_reason="expected_page_not_found", hits=[
            hit(rank=1, page_no=9, bbox=[0, 0, 10, 10], location_match=False),
        ]),
        query_row("q_bbox", "pdf_page_lookup", failure_reason="bbox_mismatch", hits=[
            hit(rank=1, page_no=1, bbox=[20, 20, 30, 30], location_match=False, bbox_overlap=False),
        ]),
    ])

    payload = c6_module.build_breakdown(
        c5_report=c5,
        c2_report=c2_report(),
        gold_rows=gold_rows(),
        eval_path=paths["c5"],
        c2_path=paths["c2"],
        gold_path=paths["gold"],
    )

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["unknown_failure_count"] == 0
    assert payload["failed_query_count"] == 6
    assert payload["failure_type_counts"] == {
        "MATCHED": 1,
        "PDF_BBOX_POLICY_MISMATCH": 1,
        "PDF_CHUNK_GRANULARITY_ISSUE": 1,
        "PDF_EXPECTED_FILE_ABSENT_IN_TOP10": 1,
        "PDF_EXPECTED_PAGE_ABSENT_IN_TOP10": 1,
        "PDF_METADATA_PROJECTION_MISSING_BBOX": 1,
        "PDF_TABLE_GOLD_BINDING_MISMATCH": 1,
    }
    assert payload["metadata_projection"]["observation_count"] == 2
    assert payload["metadata_projection"]["primary_failure_count"] == 1
    assert payload["metadata_projection"]["secondary_warning_count"] == 1
    assert payload["retrieval_ranking_failure_count"] == 2
    assert payload["retrieval_ranking_candidates_present"] is True
    assert payload["retrieval_tuning_ready"] is False
    assert payload["gold_policy_candidate_count"] == 2
    assert payload["gold_policy_candidate_query_ids"] == ["q_table", "q_bbox"]
    assert payload["chunk_granularity_candidate_count"] == 1
    assert payload["parser_chunk_contract_candidate_count"] == 2
    assert payload["c7_ready"] is True
    assert all(row["next_action"] for row in payload["query_breakdown"])


def test_c6_treats_generic_numeric_page_miss_as_gold_policy_not_ranking(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    c5 = c5_report([
        query_row("q_numeric", "pdf_section_question", failure_reason="expected_page_not_found", hits=[
            hit(rank=1, page_no=64, bbox=[0, 0, 10, 10], location_match=False),
        ]),
    ])
    c5["query_results"][0]["query"] = "2024 6,836.1"
    rows = [gold_row("q_numeric", "pdf_section_question", expected_chunk_type="paragraph", page_no="61", bbox="[0,0,10,10]")]

    payload = c6_module.build_breakdown(
        c5_report=c5,
        c2_report=c2_report(),
        gold_rows=rows,
        eval_path=paths["c5"],
        c2_path=paths["c2"],
        gold_path=paths["gold"],
    )

    row = payload["classified_failed_query_rows"][0]
    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["retrieval_ranking_failure_count"] == 0
    assert payload["gold_policy_candidate_count"] == 1
    assert row["failure_type"] == "PDF_EXPECTED_PAGE_ABSENT_IN_TOP10"
    assert row["primary_disposition"] == "gold_policy"


def test_c6_fails_closed_on_hidden_content_leakage(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    c5 = c5_report([query_row("q_match", "pdf_page_lookup", location_match=True, hits=[
        hit(rank=1, page_no=1, bbox=[0, 0, 10, 10], location_match=True, bbox_overlap=True),
    ])])
    c5["pdf_metrics"]["hidden_content_leakage_count"] = 1
    c5["vector_contract_counters"]["hidden_content_leakage_count"] = 1

    payload = c6_module.build_breakdown(
        c5_report=c5,
        c2_report=c2_report(),
        gold_rows=gold_rows(),
        eval_path=paths["c5"],
        c2_path=paths["c2"],
        gold_path=paths["gold"],
    )

    assert payload["status"] == "FAIL"
    assert "C5 pdf_metrics.hidden_content_leakage_count must be 0 before C6" in payload["blockers"]
    assert "C5 hidden_content_leakage_count must be 0 before C6" in payload["blockers"]


def test_c6_fails_closed_when_c5_is_not_ready(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    c5 = c5_report([query_row("q_match", "pdf_page_lookup", location_match=True, hits=[
        hit(rank=1, page_no=1, bbox=[0, 0, 10, 10], location_match=True, bbox_overlap=True),
    ])])
    c5["c6_ready"] = False
    c5["pdf_metrics"]["search_error_count"] = 1

    payload = c6_module.build_breakdown(
        c5_report=c5,
        c2_report=c2_report(),
        gold_rows=gold_rows(),
        eval_path=paths["c5"],
        c2_path=paths["c2"],
        gold_path=paths["gold"],
    )

    assert payload["status"] == "FAIL"
    assert "C5 report must mark c6_ready=true before C6" in payload["blockers"]
    assert "C5 search_error_count must be 0 before C6" in payload["blockers"]


def test_c6_fails_when_classifier_produces_unknown(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    c5 = c5_report([
        query_row("q_unknown", "pdf_page_lookup", failure_reason=None, hits=[
            hit(rank=1, page_no=1, bbox=[0, 0, 10, 10], location_match=False),
        ]),
    ])
    rows = [gold_row("q_unknown", "pdf_page_lookup", expected_chunk_type="paragraph", page_no="1", bbox="")]

    payload = c6_module.build_breakdown(
        c5_report=c5,
        c2_report=c2_report(),
        gold_rows=rows,
        eval_path=paths["c5"],
        c2_path=paths["c2"],
        gold_path=paths["gold"],
    )

    assert payload["status"] == "FAIL"
    assert payload["unknown_failure_count"] == 1
    assert "UNKNOWN failure count must be 0" in payload["blockers"]


def fixture_paths(tmp_path: Path, monkeypatch) -> dict[str, Path]:
    root = tmp_path
    ai_worker = root / "ai-worker"
    monkeypatch.setattr(c6_module, "ROOT", root)
    monkeypatch.setattr(c6_module, "AI_WORKER", ai_worker)
    paths = {
        "c5": ai_worker / "eval" / "reports" / "rag-ingestion" / "rag_retrieval_eval_pdf_vector_diagnostic_report.json",
        "c2": ai_worker / "eval" / "reports" / "rag-ingestion" / "pdf_vector_metadata_projection_readiness.json",
        "gold": ai_worker / "eval" / "eval_queries" / "gold_queries_pdf_v0.csv",
    }
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    return paths


def c5_report(query_results: list[dict]) -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_backend": "vector",
        "namespace": c6_module.PDF_INDEX_VERSION,
        "index_version": c6_module.PDF_INDEX_VERSION,
        "artifact_dir": "ai-worker/eval/indexes/rag-data-pdf-candidate-v1",
        "c6_ready": True,
        "query_level_results_available": True,
        "query_result_count": len(query_results),
        "pdf_metrics": {
            "search_error_count": 0,
            "hidden_content_leakage_count": 0,
        },
        "vector_contract_counters": {
            key: 0 for key in c6_module.BLOCKING_C5_COUNTERS
        },
        "warnings": [],
        "warnings_carried_forward": [],
        "query_results": query_results,
    }


def c2_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
    }


def query_row(
    query_id: str,
    bucket: str,
    *,
    failure_reason: str | None = None,
    location_match: bool = False,
    hits: list[dict],
) -> dict:
    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": f"query {query_id}",
        "label_status": "bound",
        "failure_reason": failure_reason,
        "location_match": location_match,
        "hit_rank": 1 if hits else None,
        "location_rank": 1 if location_match else None,
        "expected_file_name": "sample.pdf",
        "expected_page_no": "1",
        "expected_physical_page_index": "0",
        "top_k_results": hits,
    }


def hit(
    *,
    rank: int,
    page_no: int,
    bbox: list[int] | None,
    location_match: bool = False,
    bbox_overlap: bool = False,
    file_match: bool = True,
    docv_match: bool = True,
    chunk_type: str = "paragraph",
    chunk_type_match: bool = True,
) -> dict:
    location = {
        "type": "pdf",
        "page_no": page_no,
        "physical_page_index": page_no - 1,
        "index_version": c6_module.PDF_INDEX_VERSION,
    }
    if bbox is not None:
        location["bbox"] = bbox
    return {
        "rank": rank,
        "search_unit_id": f"su_{rank}",
        "score": 1.0 / rank,
        "source_file_name": "sample.pdf" if file_match else "other.pdf",
        "effective_source_file_type": "PDF",
        "chunk_type": chunk_type,
        "citation_text": f"sample.pdf > p.{page_no}",
        "location_json": location,
        "match_breakdown": {
            "identity_match": file_match and docv_match and chunk_type_match,
            "location_match": location_match,
            "file_match": file_match,
            "document_version_match": docv_match,
            "chunk_type_match": chunk_type_match,
            "location_type_match": True,
            "pdf_page_match": page_no == 1,
            "pdf_bbox_overlap": bbox_overlap,
            "pdf_exact_bbox": bbox_overlap,
            "indexing_contract_match": True,
            "required_index_version_match": True,
            "embedding_status_match": True,
        },
    }


def gold_rows() -> list[dict[str, str]]:
    return [
        gold_row("q_match", "pdf_page_lookup", expected_chunk_type="paragraph", page_no="1", bbox="[0,0,10,10]"),
        gold_row("q_meta", "pdf_page_lookup", expected_chunk_type="paragraph", page_no="1", bbox="[0,0,10,10]"),
        gold_row("q_table", "pdf_table_lookup", expected_chunk_type="paragraph", page_no="2", bbox="[0,0,10,10]"),
        gold_row("q_chunk", "pdf_section_question", expected_chunk_type="page", page_no="1", bbox=""),
        gold_row("q_file", "pdf_section_question", expected_chunk_type="paragraph", page_no="1", bbox="[0,0,10,10]"),
        gold_row("q_page", "pdf_page_lookup", expected_chunk_type="paragraph", page_no="1", bbox="[0,0,10,10]"),
        gold_row("q_bbox", "pdf_page_lookup", expected_chunk_type="paragraph", page_no="1", bbox="[0,0,10,10]"),
    ]


def gold_row(
    query_id: str,
    bucket: str,
    *,
    expected_chunk_type: str,
    page_no: str,
    bbox: str,
) -> dict[str, str]:
    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": f"query {query_id}",
        "expected_file_name": "sample.pdf",
        "expected_document_version_id": "docv_pdf",
        "expected_chunk_type": expected_chunk_type,
        "expected_location_type": "pdf",
        "expected_physical_page_index": str(int(page_no) - 1),
        "expected_page_no": page_no,
        "expected_page_label": "",
        "expected_bbox": bbox,
        "label_status": "bound",
    }
