from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "rag_pdf_gold_policy_review.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


c7_module = load_module("rag_pdf_gold_policy_review", MODULE_PATH)


def test_c7_records_relabel_candidates_without_invalid_policy():
    payload = c7_module.build_review(
        breakdown=breakdown([
            candidate("q-table", "pdf_table_lookup", "PDF_TABLE_GOLD_BINDING_MISMATCH"),
            candidate("q-bbox", "pdf_page_lookup", "PDF_BBOX_POLICY_MISMATCH"),
            candidate("q-chunk", "pdf_section_question", "PDF_CHUNK_GRANULARITY_ISSUE"),
        ]),
        gold_rows=[
            gold_row("q-table", "pdf_table_lookup"),
            gold_row("q-bbox", "pdf_page_lookup"),
            gold_row("q-chunk", "pdf_section_question"),
        ],
        c1_report=report("C1"),
        c2_report=report("C2"),
        c3_report=report("C3"),
        breakdown_path=Path("c6.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["invalid_gold_count"] == 0
    assert payload["page_policy_ambiguous_count"] == 0
    assert payload["table_policy_ambiguous_count"] == 0
    assert payload["ocr_policy_ambiguous_count"] == 0
    assert payload["relabel_candidate_count"] == 3
    assert payload["completion_criteria"]["relabel_candidate_rows_recorded_or_zero"] is True
    assert payload["post_c7_decision"]["post_c7_reclassification_required"] is True


def test_c7_fails_when_c6_unknown_remains():
    c6 = breakdown([])
    c6["unknown_failure_count"] = 1

    payload = c7_module.build_review(
        breakdown=c6,
        gold_rows=[],
        c1_report=report("C1"),
        c2_report=report("C2"),
        c3_report=report("C3"),
        breakdown_path=Path("c6.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["status"] == "FAIL"
    assert "C6 unknown_failure_count must be 0 before C7" in payload["blockers"]


def test_c7_invalid_gold_missing_required_page_field():
    bad = candidate("q-bad", "pdf_page_lookup", "PDF_BBOX_POLICY_MISMATCH")
    bad["expected"]["page_no"] = None

    payload = c7_module.build_review(
        breakdown=breakdown([bad]),
        gold_rows=[{"query_id": "q-bad", "expected_file_name": "sample.pdf"}],
        c1_report=report("C1"),
        c2_report=report("C2"),
        c3_report=report("C3"),
        breakdown_path=Path("c6.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["status"] == "FAIL"
    assert payload["invalid_gold_count"] == 1
    assert "expected_page_no" in payload["reviewed_candidate_rows"][0]["required_missing_fields"]


def test_c7_passes_when_no_candidates_remain():
    payload = c7_module.build_review(
        breakdown=breakdown([]),
        gold_rows=[],
        c1_report=report("C1"),
        c2_report=report("C2"),
        c3_report=report("C3"),
        breakdown_path=Path("c6.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["status"] == "PASS"
    assert payload["relabel_candidate_count"] == 0
    assert payload["post_c7_decision"]["retrieval_tuning_candidate_ready"] is True


def breakdown(candidates: list[dict]) -> dict:
    return {
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "unknown_failure_count": 0,
        "metadata_projection_failure_count": 0,
        "true_retrieval_ranking_failure_count": 7,
        "completion_criteria": {
            "unknown_failure_count_zero": True,
            "metadata_vs_ranking_separated": True,
            "gold_policy_candidate_count_recorded": True,
            "chunk_granularity_candidate_count_recorded": True,
            "all_queries_have_next_action": True,
        },
        "gold_policy_candidate_rows": [
            row for row in candidates if row["failure_type"] != "PDF_CHUNK_GRANULARITY_ISSUE"
        ],
        "chunk_granularity_candidate_rows": [
            row for row in candidates if row["failure_type"] == "PDF_CHUNK_GRANULARITY_ISSUE"
        ],
    }


def candidate(query_id: str, bucket: str, failure_type: str) -> dict:
    return {
        "query_id": query_id,
        "bucket": bucket,
        "failure_type": failure_type,
        "c5_failure_reason": "expected_page_not_found",
        "expected": {
            "file_name": "sample.pdf",
            "document_version_id": "docv_pdf",
            "chunk_type": "paragraph",
            "location_type": "pdf",
            "page_no": 1,
            "physical_page_index": 0,
            "page_label": "1",
            "bbox": "[1, 2, 3, 4]",
            "notes": "unit test",
        },
        "supporting_hit_summary": [
            {
                "rank": 1,
                "source_file_name": "sample.pdf",
                "chunk_type": "page",
                "page_no": 1,
                "physical_page_index": 0,
                "bbox_present": False,
                "ocr_used": False,
            }
        ],
    }


def gold_row(query_id: str, bucket: str) -> dict:
    return {
        "query_id": query_id,
        "bucket": bucket,
        "expected_file_name": "sample.pdf",
        "expected_page_no": "1",
        "expected_physical_page_index": "0",
        "label_status": "bound",
    }


def report(phase: str) -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "phase": phase,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
    }
