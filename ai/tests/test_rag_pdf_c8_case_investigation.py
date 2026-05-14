from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "scripts" / "rag_pdf_c8_case_investigation.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


investigation_module = load_module("rag_pdf_c8_case_investigation", MODULE_PATH)


def test_investigation_refines_short_query_to_query_surface_review(tmp_path: Path):
    case_pack_path = tmp_path / "case_pack.json"
    case_pack_path.write_text("{}", encoding="utf-8")

    payload = investigation_module.build_investigation_report(
        case_pack=case_pack([case("q-short", "기간중", same_file=[1, 2], same_page=[])]),
        db_context={
            "available": True,
            "expected_units": {
                "q-short": [
                    unit("expected-page", "page", "기간중 호주 브라질"),
                    unit("expected-row", "paragraph", "기간중 멕시코 네덜란드"),
                ],
            },
            "top_hit_units": {
                "hit-1": unit("hit-1", "paragraph", "기간중", page=74),
            },
        },
        case_pack_path=case_pack_path,
        warnings=[],
    )

    assert payload["status"] == "PASS"
    assert payload["promotion_evidence"] is False
    assert payload["retrieval_tuning_executed"] is False
    assert payload["root_cause_counts"] == {"SHORT_OR_GENERIC_QUERY_SURFACE_TOO_WEAK": 1}
    assert payload["refined_next_action_counts"] == {"QUERY_SURFACE_REVIEW": 1}
    row = payload["rows"][0]
    assert row["expected_page_surface"]["expected_page_has_query_surface"] is True
    assert row["top_hit_surface"]["top10_query_token_overlap_hit_count"] == 1
    assert row["broad_tuning_recommended"] is False


def test_investigation_keeps_file_absent_as_file_recall(tmp_path: Path):
    case_pack_path = tmp_path / "case_pack.json"
    case_pack_path.write_text("{}", encoding="utf-8")

    payload = investigation_module.build_investigation_report(
        case_pack=case_pack([case("q-file", "수입(CIF)", same_file=[], same_page=[], expected_file_absent=True)]),
        db_context={
            "available": True,
            "expected_units": {
                "q-file": [unit("expected-page", "page", "수 출(FOB) 수 입(CIF)")],
            },
            "top_hit_units": {
                "hit-1": unit("hit-1", "paragraph", "상품수입(CIF)", page=74),
            },
        },
        case_pack_path=case_pack_path,
        warnings=[],
    )

    assert payload["status"] == "PASS"
    assert payload["root_cause_counts"] == {"CROSS_DOCUMENT_REPEATED_TABLE_LABEL_FILE_RECALL": 1}
    assert payload["refined_next_action_counts"] == {"FILE_RECALL_INVESTIGATION": 1}


def test_investigation_blocks_promoted_case_pack(tmp_path: Path):
    case_pack_path = tmp_path / "case_pack.json"
    case_pack_path.write_text("{}", encoding="utf-8")
    promoted = case_pack([case("q-short", "기간중", same_file=[1], same_page=[])])
    promoted["promotion_evidence"] = True

    payload = investigation_module.build_investigation_report(
        case_pack=promoted,
        db_context={"available": False, "expected_units": {}, "top_hit_units": {}},
        case_pack_path=case_pack_path,
        warnings=[],
    )

    assert payload["status"] == "FAIL"
    assert "C8 case pack must keep promotion_evidence=false" in payload["blockers"]


def case_pack(cases: list[dict]) -> dict:
    return {
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_tuning_executed": False,
        "table_specific_retrieval_proven": False,
        "pdf_candidate_namespace": "rag-ingestion-v2-pdf-candidate-v1",
        "case_count": len(cases),
        "next_action_counts": {"PAGE_RANKING_INVESTIGATION": len(cases)},
        "cases": cases,
    }


def case(
    query_id: str,
    query: str,
    *,
    same_file: list[int],
    same_page: list[int],
    expected_file_absent: bool = False,
) -> dict:
    return {
        "query_id": query_id,
        "bucket": "pdf_page_lookup",
        "query": query,
        "expected_document_version_id": "docv",
        "expected_page_no": "3",
        "expected_physical_page_index": "2",
        "expected_bbox": "[1, 2, 3, 4]",
        "same_file_hit_ranks": same_file,
        "same_page_hit_ranks": same_page,
        "expected_file_absent": expected_file_absent,
        "expected_page_absent": not same_page,
        "next_action": "PAGE_RANKING_INVESTIGATION",
        "top10_hit_summary": [
            {
                "rank": 1,
                "score": 0.5,
                "search_unit_id": "hit-1",
                "source_file_name": "sample.pdf",
                "page_no": 74,
                "chunk_type": "paragraph",
                "file_match": not expected_file_absent,
                "pdf_page_match": False,
            }
        ],
    }


def unit(search_unit_id: str, chunk_type: str, text: str, *, page: int = 3) -> dict:
    return {
        "id": search_unit_id,
        "chunk_type": chunk_type,
        "citation_text": f"sample.pdf > p.{page}",
        "text_content": text,
        "embedding_text": f"Source: sample.pdf Citation: sample.pdf > p.{page} Page: {page} Content: {text}",
    }
