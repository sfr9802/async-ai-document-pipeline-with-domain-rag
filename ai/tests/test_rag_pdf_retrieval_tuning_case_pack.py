from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "scripts" / "rag_pdf_retrieval_tuning_case_pack.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


case_module = load_module("rag_pdf_retrieval_tuning_case_pack", MODULE_PATH)


def test_case_pack_packages_only_true_failures_without_tuning(tmp_path: Path):
    payload = case_module.build_case_pack(
        after_policy_breakdown=after_policy(),
        reviewed_diagnostic=reviewed_diagnostic(),
        source_eval_report=source_eval_report(),
        reviewed_manifest_rows=manifest_rows(),
        c3_report=c3_report(),
        artifact_manifest=artifact_manifest(),
        after_policy_path=Path("c61.json"),
        reviewed_diagnostic_path=Path("c51.json"),
        source_eval_report_path=Path("c5.json"),
        reviewed_manifest_path=Path("reviewed.csv"),
        c3_report_path=Path("c3.json"),
        artifact_dir=tmp_path,
    )

    assert payload["status"] == "PASS"
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["retrieval_tuning_executed"] is False
    assert payload["case_count"] == 2
    assert payload["next_action_counts"] == {
        "FILE_RECALL_INVESTIGATION": 1,
        "PAGE_RANKING_INVESTIGATION": 1,
    }
    q_file = next(case for case in payload["cases"] if case["query_id"] == "q-file")
    assert q_file["expected_file_absent"] is True
    q_page = next(case for case in payload["cases"] if case["query_id"] == "q-page")
    assert q_page["expected_file_absent"] is False
    assert q_page["expected_page_absent"] is True
    assert q_page["embedding_text_surface_evidence"]["artifact_samples_include_page_surface"] is True


def test_case_pack_blocks_when_reviewed_diagnostic_promotes():
    reviewed = reviewed_diagnostic()
    reviewed["promotion_evidence"] = True

    payload = case_module.build_case_pack(
        after_policy_breakdown=after_policy(),
        reviewed_diagnostic=reviewed,
        source_eval_report=source_eval_report(),
        reviewed_manifest_rows=manifest_rows(),
        c3_report=c3_report(),
        artifact_manifest=artifact_manifest(),
        after_policy_path=Path("c61.json"),
        reviewed_diagnostic_path=Path("c51.json"),
        source_eval_report_path=Path("c5.json"),
        reviewed_manifest_path=Path("reviewed.csv"),
        c3_report_path=Path("c3.json"),
        artifact_dir=Path("artifact"),
    )

    assert payload["status"] == "FAIL"
    assert "C5.1 reviewed diagnostic must keep promotion_evidence=false" in payload["blockers"]


def test_case_pack_blocks_failed_upstream_statuses():
    reviewed = reviewed_diagnostic()
    reviewed["status"] = "FAIL"
    source = source_eval_report()
    source["status"] = "FAIL"

    payload = case_module.build_case_pack(
        after_policy_breakdown=after_policy(),
        reviewed_diagnostic=reviewed,
        source_eval_report=source,
        reviewed_manifest_rows=manifest_rows(),
        c3_report=c3_report(),
        artifact_manifest=artifact_manifest(),
        after_policy_path=Path("c61.json"),
        reviewed_diagnostic_path=Path("c51.json"),
        source_eval_report_path=Path("c5.json"),
        reviewed_manifest_path=Path("reviewed.csv"),
        c3_report_path=Path("c3.json"),
        artifact_dir=Path("artifact"),
    )

    assert payload["status"] == "FAIL"
    assert "C5.1 reviewed diagnostic must be PASS or PASS_WITH_WARNINGS; got FAIL" in payload["blockers"]
    assert "source C5 eval report must be PASS or PASS_WITH_WARNINGS; got FAIL" in payload["blockers"]


def after_policy() -> dict:
    return {
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "true_retrieval_ranking_failure_count": 2,
        "rows": [
            {
                "query_id": "q-file",
                "query": "missing file query",
                "bucket": "pdf_section_question",
                "true_retrieval_ranking_failure": True,
            },
            {
                "query_id": "q-page",
                "query": "wrong page query",
                "bucket": "pdf_page_lookup",
                "true_retrieval_ranking_failure": True,
            },
            {
                "query_id": "q-table",
                "query": "table query",
                "bucket": "pdf_table_lookup",
                "true_retrieval_ranking_failure": False,
            },
        ],
    }


def reviewed_diagnostic() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
    }


def source_eval_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_backend": "vector",
        "index_version": "rag-ingestion-v2-pdf-candidate-v1",
        "query_results": [
            result("q-file", [hit(1, "other.pdf", "doc-other", 7)]),
            result("q-page", [hit(1, "sample.pdf", "docv", 9)]),
        ],
    }


def manifest_rows() -> list[dict[str, str]]:
    return [
        manifest("q-file", "sample.pdf", "docv", "3"),
        manifest("q-page", "sample.pdf", "docv", "3"),
    ]


def c3_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "summary": {
            "missing_page_surface_in_embedding_text_count": 0,
            "missing_section_surface_for_sectioned_rows": 0,
        },
        "embedding_text_contract": {"page_surface_present_count": 10},
    }


def artifact_manifest() -> dict:
    return {
        "embedding_text_variant": "retrieval_title_section",
        "embedding_text_builder_version": "v4-1",
        "embed_text_samples": [{"preview": "Source: sample.pdf Citation: sample.pdf > p.3 Page: 3 Content: text"}],
    }


def result(query_id: str, hits: list[dict]) -> dict:
    return {"query_id": query_id, "top_k_results": hits}


def manifest(query_id: str, file_name: str, docv: str, page_no: str) -> dict[str, str]:
    return {
        "query_id": query_id,
        "query": "sample overlap",
        "bucket": "pdf_page_lookup",
        "expected_file_name": file_name,
        "expected_document_version_id": docv,
        "expected_page_no": page_no,
        "expected_physical_page_index": str(int(page_no) - 1),
        "expected_bbox": "[1, 2, 3, 4]",
        "expected_answer_text": "sample overlap",
        "must_contain_terms": "sample",
        "positive_metric_eligible": "true",
    }


def hit(rank: int, file_name: str, docv: str, page_no: int) -> dict:
    return {
        "rank": rank,
        "score": 0.7,
        "source_file_name": file_name,
        "chunk_type": "paragraph",
        "citation_text": f"{file_name} > p.{page_no}",
        "location_json": {
            "type": "pdf",
            "document_version_id": docv,
            "page_no": page_no,
            "physical_page_index": page_no - 1,
            "page_label": str(page_no),
            "bbox": [1, 2, 3, 4],
        },
        "match_breakdown": {
            "file_match": file_name == "sample.pdf",
            "document_version_match": docv == "docv",
            "chunk_type_match": True,
            "pdf_page_match": page_no == 3,
            "pdf_bbox_overlap": page_no == 3,
            "pdf_exact_bbox": page_no == 3,
            "location_match": page_no == 3,
        },
    }
