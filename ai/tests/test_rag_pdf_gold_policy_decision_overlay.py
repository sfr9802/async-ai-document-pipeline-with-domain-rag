from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "scripts" / "rag_pdf_gold_policy_decision_overlay.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


overlay_module = load_module("rag_pdf_gold_policy_decision_overlay", MODULE_PATH)


def test_overlay_resolves_all_c7_candidates_and_excludes_table_denominator():
    c7 = c7_report(policy_rows())
    payload = overlay_module.build_overlay_report(
        c7_report=c7,
        c6_breakdown=c6_breakdown(),
        c7_report_path=Path("c7.json"),
        c6_breakdown_path=Path("c6.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["resolved_candidate_count"] == 8
    assert payload["unresolved_candidate_count"] == 0
    assert payload["decision_counts"] == {
        "ACCEPT_CHUNK_TYPE_POLICY_RELABEL": 1,
        "ACCEPT_PAGE_WITH_OPTIONAL_BBOX": 1,
        "DEFER_TO_TABLE_EXTRACTION": 6,
    }
    assert payload["table_specific_retrieval_proven"] is False
    assert payload["reviewed_positive_denominator_excludes_table_deferred"] is True
    assert all(
        row["positive_metric_eligible"] is False
        for row in payload["rows"]
        if row["final_decision"] == "DEFER_TO_TABLE_EXTRACTION"
    )


def test_overlay_builds_reviewed_manifest_without_mutating_v0_shape():
    overlay = overlay_module.build_overlay_report(
        c7_report=c7_report(policy_rows()),
        c6_breakdown=c6_breakdown(),
        c7_report_path=Path("c7.json"),
        c6_breakdown_path=Path("c6.json"),
        gold_path=Path("gold.csv"),
    )
    rows, report = overlay_module.build_reviewed_manifest(
        gold_rows=[gold_row(f"q-table-{idx}", "pdf_table_lookup") for idx in range(6)]
        + [gold_row("q-bbox", "pdf_page_lookup"), gold_row("q-chunk", "pdf_section_question")],
        overlay_report=overlay,
        gold_path=Path("gold.csv"),
        reviewed_manifest_path=Path("reviewed.csv"),
        manifest_report_path=Path("manifest.json"),
    )

    assert report["status"] == "PASS"
    assert report["total_pdf_rows"] == 8
    assert report["table_deferred_count"] == 6
    assert report["reviewed_positive_metric_eligible_count"] == 2
    assert report["promotion_evidence"] is False
    assert report["evidence_role"] == "diagnostic"
    assert {row["pdf_review_label"] for row in rows} == {"positive_reviewed", "table_deferred"}


def test_overlay_fails_closed_when_c6_unknown_remains():
    c6 = c6_breakdown()
    c6["unknown_failure_count"] = 1

    payload = overlay_module.build_overlay_report(
        c7_report=c7_report(policy_rows()),
        c6_breakdown=c6,
        c7_report_path=Path("c7.json"),
        c6_breakdown_path=Path("c6.json"),
        gold_path=Path("gold.csv"),
    )

    assert payload["status"] == "FAIL"
    assert "C6 unknown_failure_count must be 0 before C7.1" in payload["blockers"]


def policy_rows() -> list[dict]:
    rows = [
        candidate("q-bbox", "pdf_page_lookup", "RELABEL_BBOX_OR_PAGE_FALLBACK", support_page()),
        candidate("q-chunk", "pdf_section_question", "RELABEL_CHUNK_TYPE_POLICY", support_paragraph()),
    ]
    rows.extend(
        candidate(f"q-table-{idx}", "pdf_table_lookup", "RELABEL_TABLE_PAGE_BINDING", [])
        for idx in range(6)
    )
    return rows


def c7_report(rows: list[dict]) -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "relabel_candidate_count": len(rows),
        "relabel_candidate_rows": rows,
    }


def c6_breakdown() -> dict:
    return {
        "status": "PASS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "unknown_failure_count": 0,
    }


def candidate(query_id: str, bucket: str, category: str, support: list[dict]) -> dict:
    return {
        "query_id": query_id,
        "bucket": bucket,
        "c6_failure_type": "PDF_TABLE_GOLD_BINDING_MISMATCH",
        "decision_category": category,
        "expected": {"file_name": "sample.pdf", "page_no": 1, "physical_page_index": 0},
        "supporting_hit_summary": support,
    }


def support_page() -> list[dict]:
    return [{
        "file_match": True,
        "document_version_match": True,
        "pdf_page_match": True,
        "chunk_type": "page",
        "bbox_present": False,
    }]


def support_paragraph() -> list[dict]:
    return [{
        "file_match": True,
        "document_version_match": True,
        "pdf_page_match": True,
        "location_match": True,
        "chunk_type": "paragraph",
        "bbox_present": True,
    }]


def gold_row(query_id: str, bucket: str) -> dict[str, str]:
    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": "query",
        "expected_file_name": "sample.pdf",
        "expected_document_version_id": "docv",
        "expected_chunk_type": "paragraph",
        "expected_location_type": "pdf",
        "expected_physical_page_index": "0",
        "expected_page_no": "1",
        "expected_page_label": "1",
        "expected_bbox": "[1, 2, 3, 4]",
        "expected_answer_text": "answer",
        "must_contain_terms": "answer",
        "source_sample_id": "sample",
        "label_status": "bound",
        "notes": "",
    }
