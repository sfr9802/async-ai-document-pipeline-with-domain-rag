from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-worker" / "scripts" / "rag_query_intent_routing_matrix.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_query_intent_routing_matrix_for_tests", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


routing = load_module()


def test_classify_row_separates_xlsx_content_from_file_lookup_wording():
    row = {
        "query_id": "xlsx-1",
        "query": "신분당선 2019년 5월 승차총승객수 찾아줘.",
        "expected_location_type": "xlsx",
        "expected_sheet_name": "철도",
        "expected_cell_range": "A502:D551",
        "expected_answer_text": "신분당선 승차총승객수",
        "must_contain_terms": "신분당선;승차총승객수",
    }

    result = routing.classify_row(row, "gold_queries_xlsx_v3_positive_reviewed")

    assert result["resource_type"] == "XLSX"
    assert result["target_type"] == "CONTENT"
    assert result["retrieval_lane"] == "XLSX_CONTENT"
    assert result["readiness"] == "DIAGNOSTIC_READY"
    assert result["requires_clarification"] == "false"


def test_classify_row_routes_file_lookup_to_file_lane():
    row = {
        "query_id": "xlsx-file",
        "query": "수술 통계 엑셀 파일 찾아줘",
        "expected_file_name": "surgery.xlsx",
    }

    result = routing.classify_row(row, "manual_xlsx_file_rows")

    assert result["resource_type"] == "XLSX"
    assert result["target_type"] == "FILE"
    assert result["retrieval_lane"] == "XLSX_FILE"
    assert result["requires_clarification"] == "false"


def test_classify_row_separates_pdf_content_and_mixed_rows():
    pdf_row = {
        "query_id": "pdf-1",
        "query": "PDF 3페이지 해지 조건 알려줘",
        "expected_location_type": "pdf",
        "expected_page_no": "3",
        "expected_bbox": "[0,0,1,1]",
        "expected_answer_text": "해지 조건",
    }
    mixed_row = {
        "query_id": "mixed-1",
        "query": "경제 보고서 PDF 파일에서 3페이지 조건 알려줘",
        "expected_location_type": "pdf",
        "expected_page_no": "3",
        "expected_answer_text": "조건",
    }

    pdf_result = routing.classify_row(pdf_row, "gold_queries_v0")
    mixed_result = routing.classify_row(mixed_row, "gold_queries_v0")

    assert pdf_result["resource_type"] == "PDF"
    assert pdf_result["target_type"] == "CONTENT"
    assert pdf_result["retrieval_lane"] == "PDF_CONTENT"
    assert pdf_result["readiness"] == "BLOCKED"
    assert mixed_result["target_type"] == "MIXED"
    assert mixed_result["retrieval_lane"] == "UNKNOWN"
    assert mixed_result["requires_clarification"] == "true"


def test_classify_text_e2e_as_app_text_smoke_not_b_namu():
    row = {
        "query_id": "text-1",
        "query": "When do visitor badges expire?",
        "expected_source_ids": "source-1",
        "expected_chunk_ids": "chunk-1",
        "expected_citation_texts": "source.txt > chunk 1",
        "expected_answer_summary": "Visitor badges expire at 18:00.",
    }

    result = routing.classify_row(row, "gold_queries_text_e2e_v0")

    assert result["resource_type"] == "TEXT"
    assert result["retrieval_lane"] == "APP_TEXT_SMOKE"
    assert result["readiness"] == "SMOKE_ONLY"
    assert "not B-namu" in result["notes"]


def test_build_report_records_missing_future_input_without_failing_current_rows():
    current = routing.LoadedInput(
        path=Path("eval/current.csv"),
        source_manifest="gold_queries_v0",
        role="current_candidate",
        exists=True,
        rows=[{
            "query_id": "pdf-1",
            "query": "PDF 3페이지 조건 알려줘",
            "expected_location_type": "pdf",
            "expected_page_no": "3",
            "expected_answer_text": "조건",
        }],
        columns=["query_id", "query", "expected_location_type", "expected_page_no", "expected_answer_text"],
    )
    future = routing.LoadedInput(
        path=Path("eval/eval_queries/gold_queries_text_namu_v4_v0.csv"),
        source_manifest="gold_queries_text_namu_v4_v0",
        role="future_namu_candidate",
        exists=False,
        rows=[],
        columns=[],
        error="missing input; skipped by R1 policy",
    )
    matrix_rows = routing.build_matrix_rows([current])

    report = routing.build_report(
        loaded=[current],
        future_loaded=[future],
        matrix_rows=matrix_rows,
        output_csv=Path("eval/eval_queries/query_intent_routing_matrix_v0.csv"),
    )

    assert report["status"] == "NEEDS_REVIEW"
    assert report["blockers"] == []
    assert report["promotion_evidence"] is False
    assert report["evidence_role"] == "diagnostic"
    assert report["missing_future_inputs"] == ["eval/eval_queries/gold_queries_text_namu_v4_v0.csv"]
    assert report["lane_counts"]["PDF_CONTENT"] == 1
    assert report["lane_counts"]["B_NAMU_TEXT_CONTENT"] == 0
    assert report["observed_required_lane_coverage"]["PDF_CONTENT"] is True
    assert report["observed_required_lane_coverage"]["B_NAMU_TEXT_CONTENT"] is False


def test_build_report_needs_review_when_all_inputs_missing():
    report = routing.build_report(
        loaded=[
            routing.LoadedInput(
                path=Path("missing.csv"),
                source_manifest="missing",
                role="current_candidate",
                exists=False,
                rows=[],
                columns=[],
                error="missing input; skipped by R1 policy",
            )
        ],
        future_loaded=[],
        matrix_rows=[],
        output_csv=Path("eval/eval_queries/query_intent_routing_matrix_v0.csv"),
    )

    assert report["status"] == "NEEDS_REVIEW"
    assert "no usable input rows were available" in report["blockers"]


def test_cli_writes_csv_and_report(tmp_path: Path):
    source = tmp_path / "gold_queries_v0.csv"
    write_csv(
        source,
        [
            {
                "query_id": "q1",
                "query": "PDF 3페이지 조건 알려줘",
                "expected_location_type": "pdf",
                "expected_page_no": "3",
                "expected_answer_text": "조건",
            }
        ],
    )
    output_csv = tmp_path / "matrix.csv"
    report_path = tmp_path / "report.json"

    exit_code = routing.main([
        "--inputs",
        str(source),
        "--future-inputs",
        str(tmp_path / "missing_namu.csv"),
        "--output-csv",
        str(output_csv),
        "--report",
        str(report_path),
    ])

    assert exit_code == 0
    with output_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert reader.fieldnames == routing.CSV_FIELDNAMES
    assert rows[0]["retrieval_lane"] == "PDF_CONTENT"
    assert report["status"] == "NEEDS_REVIEW"


def test_denominator_policy_groups_by_lane_and_excludes_blocked_pdf():
    xlsx = routing.classify_row(
        {
            "query_id": "xlsx-1",
            "query": "신분당선 승차총승객수 알려줘",
            "expected_location_type": "xlsx",
            "expected_cell_range": "A1:B2",
            "expected_answer_text": "10",
            "policy_label": "positive",
            "review_decision": "KEEP_AS_POSITIVE",
            "promotion_eval_eligible": "true",
            "review_status": "ready_positive",
        },
        "gold_queries_xlsx_v3_positive_reviewed",
    )
    pdf = routing.classify_row(
        {
            "query_id": "pdf-1",
            "query": "PDF 3페이지 조건 알려줘",
            "expected_location_type": "pdf",
            "expected_page_no": "3",
            "expected_answer_text": "조건",
        },
        "gold_queries_v0",
    )
    namu = routing.classify_row(
            {
                "query_id": "namu-1",
                "query": "갱신 조건은 뭐야?",
                "expected_answer_summary": "갱신 조건",
                "expected_chunk_ids": "chunk-1",
            },
        "gold_queries_text_namu_v4_v0",
    )

    report = routing.build_report(
        loaded=[],
        future_loaded=[],
        matrix_rows=[xlsx, pdf, namu],
        output_csv=Path("eval/eval_queries/query_intent_routing_matrix_v0.csv"),
    )

    policy = report["positive_denominator_policy"]
    assert policy["must_group_by"] == ["retrieval_lane"]
    assert "PDF_CONTENT" in policy["exclude_retrieval_lanes"]
    assert "BLOCKED" in policy["exclude_readiness"]
    assert list(policy["eligible_denominator_groups_by_lane"]) == ["XLSX_CONTENT"]
    assert policy["eligible_denominator_groups_by_lane"]["XLSX_CONTENT"]["row_count"] == 1
    assert report["lane_counts"]["PDF_CONTENT"] == 1
    assert report["lane_counts"]["B_NAMU_TEXT_CONTENT"] == 1
    assert report["completion_criteria"]["observed_required_lane_coverage_complete"] is False


def test_denominator_eligibility_excludes_deferred_and_hidden_negative_rows():
    reviewed_positive = routing.classify_row(
        {
            "query_id": "q-positive",
            "query": "신분당선 승차총승객수 알려줘",
            "expected_location_type": "xlsx",
            "expected_cell_range": "A1:B2",
            "expected_answer_text": "10",
            "policy_label": "positive",
            "review_decision": "KEEP_AS_POSITIVE",
            "promotion_eval_eligible": "true",
            "review_status": "ready_positive",
        },
        "gold_queries_xlsx_v3_positive_reviewed",
    )
    deferred = routing.classify_row(
        {
            "query_id": "q-deferred",
            "query": "표 범위 알려줘",
            "expected_location_type": "xlsx",
            "expected_cell_range": "A1:Z99",
            "expected_answer_text": "table",
            "policy_label": "defer_table_contract",
            "review_decision": "EXCLUDE_FROM_POSITIVE",
            "promotion_eval_eligible": "false",
            "review_status": "excluded_from_positive_pending_table_range_contract",
        },
        "gold_queries_xlsx_v3_naturalized",
    )
    hidden_negative = routing.classify_row(
        {
            "query_id": "q-hidden",
            "query": "숨김 행 알려줘",
            "expected_location_type": "xlsx",
            "expected_cell_range": "A1:B2",
            "expected_answer_text": "hidden",
            "policy_label": "negative_hidden_policy",
            "review_decision": "RELABEL_AS_NEGATIVE_HIDDEN_POLICY",
            "promotion_eval_eligible": "false",
            "review_status": "negative_policy_candidate",
        },
        "gold_queries_xlsx_v3_naturalized",
    )

    report = routing.build_report(
        loaded=[],
        future_loaded=[],
        matrix_rows=[reviewed_positive, deferred, hidden_negative],
        output_csv=Path("eval/eval_queries/query_intent_routing_matrix_v0.csv"),
    )

    group = report["positive_denominator_policy"]["eligible_denominator_groups_by_lane"]["XLSX_CONTENT"]
    assert group["row_count"] == 1
    assert group["query_ids"] == ["q-positive"]
    assert report["denominator_exclusion_counts"][
        "source manifest is not the current XLSX official or legacy reviewed positive set"
    ] == 2


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
