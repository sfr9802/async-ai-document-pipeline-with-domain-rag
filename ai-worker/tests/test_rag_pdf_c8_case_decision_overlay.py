from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "rag_pdf_c8_case_decision_overlay.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


overlay_module = load_module("rag_pdf_c8_case_decision_overlay", MODULE_PATH)


def test_case_decision_overlay_applies_rewrites_and_pending_rows():
    reviewed = reviewed_manifest_rows()
    overlay = overlay_module.build_case_decision_overlay(
        c8_3_report=c8_3_report(),
        reviewed_manifest_rows=reviewed,
        c8_3_report_path=Path("c8_3.json"),
        reviewed_manifest_path=Path("reviewed.csv"),
        output_path=Path("overlay.json"),
    )

    assert overlay["status"] == "PASS_WITH_WARNINGS"
    assert overlay["promotion_evidence"] is False
    assert overlay["evidence_role"] == "diagnostic"
    assert overlay["reviewed_manifest_mutated"] is False
    assert overlay["candidate_manifest_written"] is False
    assert overlay["gold_v0_mutated"] is False
    assert overlay["reviewed_manifest_denominator"] == {
        "total_pdf_rows": 22,
        "positive_metric_eligible_count": 16,
        "table_deferred_count": 6,
        "excluded_count": 0,
    }
    assert overlay["query_surface_rewrite_overlay_count"] == 5
    assert overlay["case_review_pending_count"] == 2
    assert overlay["manifest_action_counts"] == {
        "MARK_CASE_REVIEW_PENDING": 2,
        "QUERY_SURFACE_REWRITE_OVERLAY": 5,
    }

    rewritten = row_by_id(overlay["rows"], "gq_auto_014")
    assert rewritten["proposed_query_surface"] == "달러 기준 1인당 국내총생산 표를 찾아줘"
    assert rewritten["source_review_decision"] == "KEEP_REVIEWED_POSITIVE"
    assert rewritten["overlay_positive_metric_eligible"] is True
    assert rewritten["query_surface_leakage"]["pass"] is True

    pending = row_by_id(overlay["rows"], "gq_pdf_section_question_002")
    assert pending["overlay_pdf_review_label"] == "case_review_pending"
    assert pending["overlay_review_decision"] == "REQUIRE_FILE_DISAMBIGUATION_POLICY"
    assert pending["overlay_positive_metric_eligible"] is False


def test_case_decision_overlay_blocks_promoted_c8_3():
    promoted = c8_3_report()
    promoted["promotion_evidence"] = True

    overlay = overlay_module.build_case_decision_overlay(
        c8_3_report=promoted,
        reviewed_manifest_rows=reviewed_manifest_rows(),
        c8_3_report_path=Path("c8_3.json"),
        reviewed_manifest_path=Path("reviewed.csv"),
        output_path=Path("overlay.json"),
    )

    assert overlay["status"] == "BLOCKED_WITH_REASON"
    assert "C8.3 report must keep promotion_evidence=false" in overlay["blockers"]


def test_case_decision_overlay_blocks_failed_query_surface_audit():
    report = c8_3_report()
    bad_row = next(row for row in report["rows"] if row["query_id"] == "gq_auto_014")
    bad_row["query_surface_audit"]["contains_latin_letters"] = True

    overlay = overlay_module.build_case_decision_overlay(
        c8_3_report=report,
        reviewed_manifest_rows=reviewed_manifest_rows(),
        c8_3_report_path=Path("c8_3.json"),
        reviewed_manifest_path=Path("reviewed.csv"),
        output_path=Path("overlay.json"),
    )

    assert overlay["status"] == "BLOCKED_WITH_REASON"
    assert "gq_auto_014 proposed query surface failed C8.3 audit" in overlay["blockers"]


def test_case_decision_overlay_main_does_not_mutate_reviewed_manifest(tmp_path: Path):
    c8_path = tmp_path / "c8_3.json"
    reviewed_path = tmp_path / "reviewed.csv"
    output_path = tmp_path / "overlay.json"
    c8_path.write_text(json.dumps(c8_3_report(), ensure_ascii=False), encoding="utf-8")
    write_reviewed_csv(reviewed_path, reviewed_manifest_rows())
    before = sha256(reviewed_path)

    exit_code = overlay_module.main([
        "--c8-3-report",
        str(c8_path),
        "--reviewed-manifest",
        str(reviewed_path),
        "--output",
        str(output_path),
    ])

    assert exit_code == 0
    assert sha256(reviewed_path) == before
    assert output_path.exists()
    assert not (tmp_path / "candidate.csv").exists()


def row_by_id(rows: list[dict], query_id: str) -> dict:
    return next(row for row in rows if row["query_id"] == query_id)


def c8_3_report() -> dict:
    rows = [
        case_row("gq_pdf_page_lookup_003", "목 차", "REWRITE_QUERY_SURFACE", "목차 위치를 찾아줘"),
        case_row("gq_pdf_section_question_002", "수입(CIF)", "REQUIRE_FILE_DISAMBIGUATION_POLICY", None),
        case_row("gq_pdf_section_question_003", "2024 6,836.1", "REQUIRE_EMBEDDING_SURFACE_REVIEW", None),
        case_row("gq_auto_009", "기간중", "REWRITE_QUERY_SURFACE", "주요 국가 국내총생산 규모 표의 기간 항목을 찾아줘"),
        case_row("gq_auto_014", "달러", "REWRITE_QUERY_SURFACE", "달러 기준 1인당 국내총생산 표를 찾아줘"),
        case_row("gq_auto_019", "기간중", "REWRITE_QUERY_SURFACE", "1인당 국내총생산 표의 기간 항목을 찾아줘"),
        case_row("gq_auto_025", "목 차", "REWRITE_QUERY_SURFACE", "목차에서 부문별 동향 위치를 찾아줘"),
    ]
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "pdf_candidate_namespace": "rag-ingestion-v2-pdf-candidate-v1",
        "pdf_artifact_dir": "rag-data-pdf-candidate-v1",
        "retrieval_tuning_executed": False,
        "broad_tuning_recommended": False,
        "case_count": 7,
        "decision_counts": {
            "REQUIRE_EMBEDDING_SURFACE_REVIEW": 1,
            "REQUIRE_FILE_DISAMBIGUATION_POLICY": 1,
            "REWRITE_QUERY_SURFACE": 5,
        },
        "blockers": [],
        "rows": rows,
    }


def case_row(query_id: str, query: str, decision: str, proposed: str | None) -> dict:
    return {
        "query_id": query_id,
        "bucket": "pdf_page_lookup",
        "query": query,
        "source_next_action": "QUERY_SURFACE_REVIEW" if decision == "REWRITE_QUERY_SURFACE" else "CASE_REVIEW",
        "case_decision": decision,
        "proposed_query_surface": proposed,
        "query_surface_audit": {
            "has_proposed_query_surface": proposed is not None,
            "changed_from_original": proposed is not None and proposed != query,
            "leaks_expected_file_name": False,
            "contains_latin_letters": False,
            "contains_pdf_extension": False,
        },
        "expected_file_name": f"{query_id}.pdf",
        "expected_page_no": "3",
        "expected_physical_page_index": "2",
        "expected_bbox": "[1,2,3,4]",
        "why_not_broad_tuning": "case-level decision required before tuning",
    }


def reviewed_manifest_rows() -> list[dict[str, str]]:
    rows = [
        reviewed_row("gq_pdf_page_lookup_003", "목 차"),
        reviewed_row("gq_pdf_section_question_002", "수입(CIF)"),
        reviewed_row("gq_pdf_section_question_003", "2024 6,836.1"),
        reviewed_row("gq_auto_009", "기간중"),
        reviewed_row("gq_auto_014", "달러"),
        reviewed_row("gq_auto_019", "기간중"),
        reviewed_row("gq_auto_025", "목 차"),
    ]
    for idx in range(9):
        rows.append(reviewed_row(f"q-extra-{idx}", f"추가 {idx}"))
    for idx in range(6):
        table = reviewed_row(f"q-table-{idx}", "표")
        table["pdf_review_label"] = "table_deferred"
        table["review_decision"] = "DEFER_TO_TABLE_EXTRACTION"
        table["positive_metric_eligible"] = "false"
        rows.append(table)
    return rows


def reviewed_row(query_id: str, query: str) -> dict[str, str]:
    return {
        "query_id": query_id,
        "bucket": "pdf_page_lookup",
        "query": query,
        "expected_file_name": f"{query_id}.pdf",
        "expected_document_version_id": "docv",
        "expected_chunk_type": "paragraph",
        "expected_location_type": "pdf",
        "expected_physical_page_index": "2",
        "expected_page_no": "3",
        "expected_page_label": "3",
        "expected_bbox": "[1,2,3,4]",
        "expected_answer_text": "answer",
        "must_contain_terms": query,
        "source_sample_id": "sample",
        "label_status": "bound",
        "pdf_review_label": "positive_reviewed",
        "pdf_match_policy": "EXACT_PAGE_AND_BBOX",
        "pdf_table_policy": "NOT_TABLE_QUERY",
        "pdf_bbox_policy": "REQUIRED",
        "review_decision": "KEEP_REVIEWED_POSITIVE",
        "positive_metric_eligible": "true",
        "notes": "",
    }


def write_reviewed_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
