from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "scripts" / "rag_pdf_c8_rank_probe.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rank_module = load_module("rag_pdf_c8_rank_probe", MODULE_PATH)


def test_rank_probe_finds_expected_page_beyond_top10_and_exact_bbox(tmp_path: Path):
    case_path = tmp_path / "c8_1.json"
    case_path.write_text("{}", encoding="utf-8")
    artifact_dir = artifact_fixture(tmp_path)

    payload = rank_module.build_rank_probe_report(
        case_investigation=case_investigation([case("q1", "2024 6,836.1")]),
        units=[
            unit("u-target", "docv", 61, "paragraph", "2024 6,836.1", bbox=[1, 2, 3, 4]),
            unit("u-page", "docv", 61, "page", "table page 2024 6,836.1", bbox=None),
            unit("u-other", "other", 64, "paragraph", "2024 other values", bbox=[9, 9, 10, 10]),
        ],
        vector_results_by_query_id={
            "q1": [
                hit(rank, "other", 64, f"wrong-{rank}", bbox=[9, 9, 10, 10])
                for rank in range(1, 12)
            ] + [hit(51, "docv", 61, "u-target", bbox=[1, 2, 3, 4])],
        },
        case_investigation_path=case_path,
        c4_report=c4_report(artifact_dir),
        c4_report_path=tmp_path / "c4.json",
        top_k=100,
        blockers=[],
        warnings=[],
        artifact_dir=artifact_dir,
    )

    assert payload["status"] == "PASS"
    row = payload["rows"][0]
    assert row["vector_probe"]["expected_page_first_rank"] == 51
    assert row["vector_probe"]["expected_exact_bbox_first_rank"] == 51
    assert row["vector_probe"]["expected_page_found_at"] == {"at_10": False, "at_50": False, "at_100": True}
    assert payload["target_rank_summary"]["expected_page_found_top_k_count"] == 1
    assert row["lexical_probe"]["expected_page_exact_phrase_present"] is True
    assert row["broad_tuning_recommended"] is False


def test_rank_probe_keeps_generic_query_as_query_surface_review(tmp_path: Path):
    case_path = tmp_path / "c8_1.json"
    case_path.write_text("{}", encoding="utf-8")
    artifact_dir = artifact_fixture(tmp_path)

    payload = rank_module.build_rank_probe_report(
        case_investigation=case_investigation([case("q2", "달러")]),
        units=[
            unit("u-target", "docv", 79, "paragraph", "1인당 GDP 달러", bbox=[1, 2, 3, 4]),
            unit("u-compete", "docv", 72, "paragraph", "대미달러", bbox=[5, 6, 7, 8]),
            unit("u-compete2", "other", 10, "paragraph", "달러", bbox=[1, 1, 2, 2]),
        ],
        vector_results_by_query_id={
            "q2": [
                hit(1, "docv", 72, "u-compete", bbox=[5, 6, 7, 8]),
                hit(20, "docv", 79, "u-target", bbox=[1, 2, 3, 4]),
            ],
        },
        case_investigation_path=case_path,
        c4_report=c4_report(artifact_dir),
        c4_report_path=tmp_path / "c4.json",
        top_k=100,
        blockers=[],
        warnings=[],
        artifact_dir=artifact_dir,
    )

    row = payload["rows"][0]
    assert row["rank_probe_next_action"] == "QUERY_SURFACE_REVIEW"
    assert row["lexical_probe"]["competing_exact_phrase_page_count"] == 2


def test_rank_probe_blocks_when_vector_results_missing(tmp_path: Path):
    case_path = tmp_path / "c8_1.json"
    case_path.write_text("{}", encoding="utf-8")
    artifact_dir = artifact_fixture(tmp_path)

    payload = rank_module.build_rank_probe_report(
        case_investigation=case_investigation([case("q1", "목 차")]),
        units=[unit("u-target", "docv", 3, "paragraph", "목 차", bbox=[1, 2, 3, 4])],
        vector_results_by_query_id={},
        case_investigation_path=case_path,
        c4_report=c4_report(artifact_dir),
        c4_report_path=tmp_path / "c4.json",
        top_k=100,
        blockers=[],
        warnings=[],
        artifact_dir=artifact_dir,
    )

    assert payload["status"] == "BLOCKED_WITH_REASON"
    assert "vector top-k probe must be available for every C8.2 row" in payload["blockers"]


def test_rank_probe_requires_physical_page_match(tmp_path: Path):
    case_path = tmp_path / "c8_1.json"
    case_path.write_text("{}", encoding="utf-8")
    artifact_dir = artifact_fixture(tmp_path)

    payload = rank_module.build_rank_probe_report(
        case_investigation=case_investigation([case("q1", "2024 6,836.1")]),
        units=[unit("u-target", "docv", 61, "paragraph", "2024 6,836.1", bbox=[1, 2, 3, 4])],
        vector_results_by_query_id={
            "q1": [
                hit(1, "docv", 61, "wrong-physical", bbox=[1, 2, 3, 4], physical_page_index=999),
                hit(12, "docv", 61, "u-target", bbox=[1, 2, 3, 4]),
            ],
        },
        case_investigation_path=case_path,
        c4_report=c4_report(artifact_dir),
        c4_report_path=tmp_path / "c4.json",
        top_k=100,
        blockers=[],
        warnings=[],
        artifact_dir=artifact_dir,
    )

    row = payload["rows"][0]
    assert row["vector_probe"]["expected_page_hit_ranks"] == [12]
    assert row["vector_probe"]["expected_exact_bbox_first_rank"] == 12


def test_rank_probe_page_aggregation_can_surface_page_group_without_raw_top10(tmp_path: Path):
    case_path = tmp_path / "c8_1.json"
    case_path.write_text("{}", encoding="utf-8")
    artifact_dir = artifact_fixture(tmp_path)

    hits = [
        hit(1, "other", 10, "wrong-a", bbox=[9, 9, 10, 10]),
        hit(2, "other", 10, "wrong-a2", bbox=[9, 9, 10, 10]),
        hit(3, "other", 11, "wrong-b", bbox=[9, 9, 10, 10]),
        hit(4, "other", 11, "wrong-b2", bbox=[9, 9, 10, 10]),
        hit(5, "other", 12, "wrong-c", bbox=[9, 9, 10, 10]),
        hit(6, "other", 12, "wrong-c2", bbox=[9, 9, 10, 10]),
        hit(7, "other", 13, "wrong-d", bbox=[9, 9, 10, 10]),
        hit(8, "other", 13, "wrong-d2", bbox=[9, 9, 10, 10]),
        hit(9, "other", 14, "wrong-e", bbox=[9, 9, 10, 10]),
        hit(10, "other", 14, "wrong-e2", bbox=[9, 9, 10, 10]),
        hit(11, "docv", 61, "u-target", bbox=[1, 2, 3, 4]),
    ]
    payload = rank_module.build_rank_probe_report(
        case_investigation=case_investigation([case("q1", "2024 6,836.1")]),
        units=[unit("u-target", "docv", 61, "paragraph", "2024 6,836.1", bbox=[1, 2, 3, 4])],
        vector_results_by_query_id={"q1": hits},
        case_investigation_path=case_path,
        c4_report=c4_report(artifact_dir),
        c4_report_path=tmp_path / "c4.json",
        top_k=100,
        blockers=[],
        warnings=[],
        artifact_dir=artifact_dir,
    )

    row = payload["rows"][0]
    assert row["vector_probe"]["expected_page_found_at"]["at_10"] is False
    assert row["page_aggregation_probe"]["expected_page_group_rank"] == 6
    assert row["page_aggregation_probe"]["expected_page_group_in_top10"] is True


def case_investigation(cases: list[dict]) -> dict:
    return {
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_tuning_executed": False,
        "table_specific_retrieval_proven": False,
        "case_count": len(cases),
        "rows": cases,
    }


def case(query_id: str, query: str) -> dict:
    page = "61" if query_id == "q1" else "79"
    return {
        "query_id": query_id,
        "bucket": "pdf_section_question",
        "query": query,
        "root_cause": "EXPECTED_PAGE_PRESENT_BUT_DENSE_RANKING_MISS",
        "refined_next_action": "EMBEDDING_SURFACE_REVIEW",
        "expected_document_version_id": "docv",
        "expected_page_no": page,
        "expected_physical_page_index": str(int(page) - 1),
        "expected_bbox": "[1, 2, 3, 4]",
        "expected_file_absent": False,
    }


def unit(search_unit_id: str, docv: str, page: int, chunk_type: str, text: str, *, bbox: list[int] | None) -> dict:
    location = {"type": "pdf", "document_version_id": docv, "page_no": page, "physical_page_index": page - 1}
    if bbox is not None:
        location["bbox"] = bbox
    return {
        "id": search_unit_id,
        "source_file_name": "sample.pdf",
        "document_version_id": docv,
        "chunk_type": chunk_type,
        "page_start": page,
        "page_end": page,
        "citation_text": f"sample.pdf > p.{page}",
        "text_content": text,
        "embedding_text": f"Page: {page} Content: {text}",
        "location_json": location,
    }


def hit(
    rank: int,
    docv: str,
    page: int,
    search_unit_id: str,
    *,
    bbox: list[int],
    physical_page_index: int | None = None,
) -> dict:
    if physical_page_index is None:
        physical_page_index = page - 1
    return {
        "rank": rank,
        "score": 1.0 / rank,
        "index_version": "rag-ingestion-v2-pdf-candidate-v1",
        "embedding_status": "EMBEDDED",
        "source_file_name": "sample.pdf",
        "document_version_id": docv,
        "search_unit_id": search_unit_id,
        "chunk_type": "paragraph",
        "location_json": {
            "type": "pdf",
            "document_version_id": docv,
            "page_no": page,
            "physical_page_index": physical_page_index,
            "bbox": bbox,
        },
        "citation_text": f"sample.pdf > p.{page}",
    }


def c4_report(artifact_dir: Path) -> dict:
    return {
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "index_version": "rag-ingestion-v2-pdf-candidate-v1",
        "expected_index_version": "rag-ingestion-v2-pdf-candidate-v1",
        "artifact_dir": str(artifact_dir),
    }


def artifact_fixture(tmp_path: Path) -> Path:
    artifact_dir = tmp_path / "rag-data-pdf-candidate-v1"
    artifact_dir.mkdir()
    payload = {
        "index_version": "rag-ingestion-v2-pdf-candidate-v1",
        "embedding_model": "BAAI/bge-m3",
        "chunk_count": 3,
    }
    (artifact_dir / "build.json").write_text(rank_module.json.dumps(payload), encoding="utf-8")
    (artifact_dir / "ingest_manifest.json").write_text(rank_module.json.dumps(payload), encoding="utf-8")
    return artifact_dir
