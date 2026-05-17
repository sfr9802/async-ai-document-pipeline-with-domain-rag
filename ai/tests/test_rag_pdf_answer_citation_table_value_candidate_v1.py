from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_pdf_answer_citation_table_value_candidate_v1.py"
REPAIRED_PDF_QUERY_IDS = ("gq_auto_010", "gq_auto_030", "gq_pdf_section_question_001")
REPORT_ONLY_GUARDRAILS = {
    "tuning_run_started": False,
    "promotion_evidence": False,
    "threshold_tuning": False,
    "winner_selection": False,
    "production_mutation": False,
    "denominator_mutation": False,
    "gold_mutation": False,
    "expected_answer_used_for_generation": False,
    "supporting_evidence_used_for_generation": False,
    "gold_fields_used_for_generation": False,
}


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_answer_citation_table_value_candidate_v1_for_tests", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pdf_candidate_generates_table_value_answers_without_gold_generation_inputs() -> None:
    module = load_module()

    currency = module.generate_pdf_candidate_for_query(
        query_id="gq_auto_030",
        question="2020년 한국 원달러 기말 환율은 얼마인가요?",
        source_page_text=currency_page_text(),
        source_page_locator=source_locator(
            file="2021_03_recent_economic_trends.pdf",
            page=65,
            search_unit_id="su-currency",
            document_version_id="docv-currency",
        ),
    )
    trade = module.generate_pdf_candidate_for_query(
        query_id="gq_pdf_section_question_001",
        question="2024년 수출입차 금액은 얼마인가요?",
        source_page_text=trade_page_text(),
        source_page_locator=source_locator(
            file="2025_12_recent_economic_trends.pdf",
            page=61,
            search_unit_id="su-trade",
            document_version_id="docv-trade",
        ),
    )
    unemployment = module.generate_pdf_candidate_for_query(
        query_id="gq_auto_010",
        question="2월 실업률은 전년 같은 달보다 어떻게 변했나요?",
        source_page_text=unemployment_page_text(),
        source_page_locator=source_locator(
            file="2021_03_recent_economic_trends.pdf",
            page=8,
            search_unit_id="su-unemployment",
            document_version_id="docv-unemployment",
        ),
    )

    assert currency["candidate_generated_answer"] == "2020년 한국 원/달러 기말 환율은 1,088.0원입니다."
    assert currency["row_table_extraction_basis"] == "native_pdf_currency_comparison_table"
    assert trade["candidate_generated_answer"] == "2024년 수출입차 금액은 518.4억 불입니다."
    assert trade["row_table_extraction_basis"] == "native_pdf_export_import_table"
    assert unemployment["candidate_generated_answer"] == "실업률은 4.9%로 전년동월대비 0.8%p 상승"
    assert unemployment["row_table_extraction_basis"] == "native_pdf_nearby_paragraph_value"
    for candidate in (currency, trade, unemployment):
        assert candidate["expected_answer_used_for_generation"] is False
        assert candidate["supporting_evidence_used_for_generation"] is False
        assert candidate["local_llm_used"] is False
        assert candidate["gold_fields_used_for_generation"] is False
        assert candidate["source_text_contains_answer_value"] is True
        assert candidate["source_row_contains_target_value"] is True
        assert candidate["source_bound_identity_verified"] is True
        assert module.classify_pdf_locator_compatibility(candidate["candidate_citation_locator"]) == [
            "OFFICIAL_COMPATIBLE_LOCATOR"
        ]

    assert currency["candidate_citation_locator"]["region_type"] == "table_body"
    assert currency["candidate_citation_locator"]["bbox_granularity"] == "row_only"
    assert trade["candidate_citation_locator"]["region_type"] == "table_body"
    assert trade["candidate_citation_locator"]["bbox_granularity"] == "row_only"
    assert unemployment["candidate_citation_locator"]["region_type"] == "paragraph"
    assert "bbox_granularity" not in unemployment["candidate_citation_locator"]


def test_pdf_candidate_run_carries_forward_xlsx_runtime_and_scores_three_pdf_rows(tmp_path: Path) -> None:
    module = load_module()
    baseline = tmp_path / "baseline.json"
    xlsx_report = tmp_path / "xlsx_runtime.json"
    runtime_results = tmp_path / "xlsx_runtime.jsonl"
    scorer_results = tmp_path / "scorer.jsonl"
    out_jsonl = tmp_path / "pdf_candidate.jsonl"
    status_path = tmp_path / "status.jsonl"
    write_json(baseline, baseline_report())
    write_json(xlsx_report, xlsx_runtime_report())
    write_jsonl(runtime_results, runtime_candidate_rows())
    write_jsonl(scorer_results, scorer_rows_for_pdf_failures())

    report = module.run_candidate(
        baseline_report_path=baseline,
        xlsx_runtime_candidate_report_path=xlsx_report,
        xlsx_runtime_candidate_results_path=runtime_results,
        official_scorer_results_path=scorer_results,
        output_report=None,
        output_md=None,
        output_results_jsonl=out_jsonl,
        status_jsonl=status_path,
        source_page_text_by_query_id={
            "gq_auto_010": unemployment_page_text(),
            "gq_auto_030": currency_page_text(),
            "gq_pdf_section_question_001": trade_page_text(),
        },
    )

    rows = [json.loads(line) for line in out_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    status_events = [
        json.loads(line) for line in status_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    by_id = {row["query_id"]: row for row in rows}
    assert len(rows) == 29
    assert len(by_id) == 29
    assert sum(1 for row in rows if row["failure_category"] == "PASS") == 29
    assert all(sum(1 for row in rows if row["query_id"] == query_id) == 1 for query_id in REPAIRED_PDF_QUERY_IDS)
    assert status_events[-1]["event_type"] == "pdf_candidate_locator_hardening"
    assert status_events[-1]["pdf_repaired_rows"] == 3
    assert status_events[-1]["current_focused_result"] is None
    assert status_events[-1]["pdf_candidate_result_count"] == {
        "failure_category_counts": {"PASS": 29},
        "rows": 29,
        "unique_query_ids": 29,
    }
    assert status_events[-1]["guardrails"] == REPORT_ONLY_GUARDRAILS
    assert report["status"] == "PASS"
    assert report["report_only"] is True
    assert report["pdf_candidate_result_counts"] == {"PASS": 29}
    assert set(report["pdf_candidate_before_after"]) == set(REPAIRED_PDF_QUERY_IDS)
    assert report["remaining_failures"] == []
    assert report["pdf_candidate_before_after"]["gq_auto_010"]["after_failure_category"] == "PASS"
    assert report["all_track_candidate_observation"]["pdf_candidate_pass"] == "29/29"
    assert report["pdf_candidate_cases"]["gq_auto_030"]["deterministic_verification_passed"] is True
    assert by_id["gq_auto_030"]["failure_category"] == "PASS"
    assert by_id["gq_auto_030"]["score_details"]["expected_answer_used_for_generation"] is False
    assert by_id["gq_auto_030"]["score_details"]["supporting_evidence_used_for_generation"] is False
    assert by_id["gq_auto_030"]["score_details"]["gold_fields_used_for_generation"] is False
    assert by_id["gq_auto_030"]["score_details"]["source_row_contains_target_value"] is True
    assert by_id["gq_auto_030"]["score_details"]["target_column_selection_basis"] == "question_phrase"
    assert by_id["gq_auto_030"]["score_details"]["row_selection_basis"] == "question_period_native_pdf_row"
    assert by_id["gq_auto_030"]["generated_citations"][0]["citation_locator"]["region_type"] == "table_body"
    assert by_id["gq_auto_030"]["generated_citations"][0]["citation_locator"]["bbox_granularity"] == "row_only"
    assert by_id["gq_auto_030"]["generated_citations"][0]["citation_locator"]["search_unit_id"] == "su-gq_auto_030"
    assert by_id["gq_auto_030"]["generated_citations"][0]["citation_locator"]["document_version_id"] == "docv-gq_auto_030"
    assert status_events[-1]["locator_compatibility_before"]["gq_auto_030"] == [
        "LOCATOR_METADATA_INCOMPLETE",
        "REGION_TYPE_NOT_ALLOWED",
        "SEARCH_UNIT_ID_MISSING",
        "DOCUMENT_VERSION_ID_MISSING",
        "SOURCE_BOUNDING_UNVERIFIED",
    ]
    assert status_events[-1]["locator_compatibility_after"]["gq_auto_030"] == ["OFFICIAL_COMPATIBLE_LOCATOR"]
    assert report["guardrails"] == REPORT_ONLY_GUARDRAILS
    for query_id in REPAIRED_PDF_QUERY_IDS:
        row = by_id[query_id]
        locator = row["generated_citations"][0]["citation_locator"]
        assert row["score_details"]["locator_compatibility"] == ["OFFICIAL_COMPATIBLE_LOCATOR"]
        assert locator["file"]
        assert locator["page"]
        assert locator["physical_page_index"] >= 0
        assert numeric_bbox(locator["bbox"])
        assert locator["search_unit_id"]
        assert locator["document_version_id"]
        assert locator["source_basis"]
        assert locator["source_pdf_path"]
        assert locator["row_label"]
        assert locator["target_column"]
        if query_id == "gq_auto_010":
            assert locator["region_type"] == "paragraph"
            assert "bbox_granularity" not in locator
        else:
            assert locator["region_type"] == "table_body"
            assert locator["bbox_granularity"] == "row_only"


def test_pdf_candidate_fails_closed_when_source_identity_is_missing() -> None:
    module = load_module()
    candidate = module.generate_pdf_candidate_for_query(
        query_id="gq_auto_030",
        question="2020년 한국 원달러 기말 환율은 얼마인가요?",
        source_page_text=currency_page_text(),
        source_page_locator=source_locator(
            file="2021_03_recent_economic_trends.pdf",
            page=65,
            search_unit_id="",
            document_version_id="docv-currency",
        ),
    )
    scored = module.score_candidate_row(
        original_runtime_row={"query_id": "gq_auto_030", "failure_category": "PARTIAL_OR_UNSUPPORTED"},
        official_scorer_row=scorer_rows_for_pdf_failures()[1],
        candidate=candidate,
    )

    assert candidate["source_bound_identity_verified"] is False
    assert "SEARCH_UNIT_ID_MISSING" in module.classify_pdf_locator_compatibility(
        candidate["candidate_citation_locator"]
    )
    assert scored["failure_category"] == "PARTIAL_OR_UNSUPPORTED"
    assert scored["score_details"]["deterministic_verification_passed"] is False


def test_pdf_candidate_generation_and_locator_hardening_ignore_gold_poison_sentinel() -> None:
    module = load_module()
    candidate = module.generate_pdf_candidate_for_query(
        query_id="gq_auto_030",
        question="2020년 한국 원달러 기말 환율은 얼마인가요?",
        source_page_text=currency_page_text(),
        source_page_locator=source_locator(
            file="2021_03_recent_economic_trends.pdf",
            page=65,
            search_unit_id="su-currency",
            document_version_id="docv-currency",
        ),
    )
    poison_row = scorer_row(
        "gq_auto_030",
        "2020년 한국 원달러 기말 환율은 얼마인가요?",
        "POISON_EXPECTED_ANSWER_SHOULD_NOT_APPEAR",
        "POISON_SUPPORTING_EVIDENCE_SHOULD_NOT_APPEAR",
    )
    scored = module.score_candidate_row(
        original_runtime_row={"query_id": "gq_auto_030", "failure_category": "PARTIAL_OR_UNSUPPORTED"},
        official_scorer_row=poison_row,
        candidate=candidate,
    )

    serialized_candidate = json.dumps(candidate, ensure_ascii=False)
    assert "POISON_EXPECTED_ANSWER_SHOULD_NOT_APPEAR" not in serialized_candidate
    assert "POISON_SUPPORTING_EVIDENCE_SHOULD_NOT_APPEAR" not in serialized_candidate
    assert candidate["candidate_generated_answer"] == "2020년 한국 원/달러 기말 환율은 1,088.0원입니다."
    assert candidate["candidate_citation_locator"]["target_column"] == "한국(원/달러) 기말"
    assert scored["failure_category"] == "PARTIAL_OR_UNSUPPORTED"
    assert scored["score_details"]["expected_answer_used_for_generation"] is False
    assert scored["score_details"]["supporting_evidence_used_for_generation"] is False


def test_pdf_candidate_does_not_pass_when_source_row_lacks_target_value() -> None:
    module = load_module()
    missing_target_text = currency_page_text().replace("1,088.0", "1,999.9")

    candidate = module.generate_pdf_candidate_for_query(
        query_id="gq_auto_030",
        question="2020년 한국 원달러 기말 환율은 얼마인가요?",
        source_page_text=missing_target_text,
        source_page_locator=source_locator(
            file="2021_03_recent_economic_trends.pdf",
            page=65,
            search_unit_id="su-currency",
            document_version_id="docv-currency",
        ),
    )
    scored = module.score_candidate_row(
        original_runtime_row={"query_id": "gq_auto_030", "failure_category": "PARTIAL_OR_UNSUPPORTED"},
        official_scorer_row=scorer_rows_for_pdf_failures()[1],
        candidate=candidate,
    )

    assert candidate["source_row_contains_target_value"] is True
    assert candidate["target_value"] == "1,999.9"
    assert scored["failure_category"] == "PARTIAL_OR_UNSUPPORTED"
    assert scored["score_details"]["deterministic_verification_passed"] is False


def test_pdf_candidate_has_no_query_id_specific_answer_or_evidence_map() -> None:
    module = load_module()
    source_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert not hasattr(module, "PDF_CASES")
    assert 'if query_id == "' not in source_text
    assert '"gq_auto_030": {' not in source_text
    generation_source = inspect.getsource(module.generate_pdf_candidate_for_query)
    assert "score_details" not in generation_source
    assert ".get(\"expected_answer\"" not in generation_source
    assert ".get(\"supporting_evidence\"" not in generation_source


def baseline_report() -> dict:
    return {
        "failure_category_counts": {"PASS": 8, "CITATION_UNSUPPORTED": 11, "PARTIAL_OR_UNSUPPORTED": 10},
        "official_scoring_attempt_count": 29,
        "scored_count": 29,
        "baseline_metrics": {"per_track": {"pdf_business_ocr_mm": {"pass_count": 1, "row_count": 4}}},
    }


def xlsx_runtime_report() -> dict:
    return {
        "runtime_candidate_failure_category_counts": {"PASS": 26, "PARTIAL_OR_UNSUPPORTED": 3},
        "xlsx_summary": {"runtime_candidate_pass_count": 19, "runtime_candidate_total": 19},
        "remaining_failures_by_track": {
            "pdf_business_ocr_mm": ["gq_auto_010", "gq_auto_030", "gq_pdf_section_question_001"]
        },
    }


def runtime_candidate_rows() -> list[dict]:
    pass_rows = [
        {
            "query_id": f"pass_{index:02d}",
            "track": "text_namu_v2_1",
            "failure_category": "PASS",
            "answer_score": 1.0,
            "citation_support_score": 1.0,
        }
        for index in range(26)
    ]
    pdf_rows = [
        {
            "query_id": query_id,
            "track": "pdf_business_ocr_mm",
            "failure_category": "PARTIAL_OR_UNSUPPORTED",
            "answer_score": 0.0,
            "citation_support_score": 0.0,
            "generated_answer": "old answer",
            "generated_citations": [
                {
                    "citation_text": "old",
                    "citation_locator": {"page": 1, "bbox": [], "region_type": "table_row"},
                }
            ],
        }
        for query_id in ("gq_auto_010", "gq_auto_030", "gq_pdf_section_question_001")
    ]
    return [*pass_rows, *pdf_rows]


def scorer_rows_for_pdf_failures() -> list[dict]:
    return [
        scorer_row(
            "gq_auto_010",
            "2월 실업률은 전년 같은 달보다 어떻게 변했나요?",
            "실업률은 4.9%로 전년동월대비 0.8%p 상승",
            "실업률은 4.9%로 전년동월대비 0.8%p 상승",
        ),
        scorer_row(
            "gq_auto_030",
            "2020년 한국 원달러 기말 환율은 얼마인가요?",
            "2020년 한국 원/달러 기말 환율은 1,088.0원입니다.",
            "2020 / 1,088.0 / 6.42 / 1,180.1 / 103.20 / 5.49 / 28.13 / 6.97 / 1.2300 / 9.76",
        ),
        scorer_row(
            "gq_pdf_section_question_001",
            "2024년 수출입차 금액은 얼마인가요?",
            "2024년 수출입차 금액은 518.4억 불입니다.",
            "2024 / 6,836.1 / 8.1 / 6,317.7 / △1.7 / 518.4",
        ),
    ]


def scorer_row(query_id: str, question: str, expected_answer: str, supporting_evidence: str) -> dict:
    return {
        "query_id": query_id,
        "track": "pdf_business_ocr_mm",
        "question": question,
        "generated_answer": "old answer",
        "generated_citations": [
            {
                "citation_text": "old",
                "citation_locator": {
                    "file": "sample.pdf",
                    "page": 1,
                    "physical_page_index": 0,
                    "bbox": [1, 2, 3, 4],
                    "region_type": "paragraph",
                    "search_unit_id": f"su-{query_id}",
                    "document_version_id": f"docv-{query_id}",
                    "source_pdf_path": "local-storage/sample.pdf",
                },
            }
        ],
        "score_details": {
            "expected_answer": expected_answer,
            "supporting_evidence": supporting_evidence,
        },
    }


def source_locator(*, file: str, page: int, search_unit_id: str, document_version_id: str) -> dict:
    return {
        "file": file,
        "page": page,
        "physical_page_index": page - 1,
        "bbox": [1, 2, 3, 4],
        "region_type": "paragraph",
        "search_unit_id": search_unit_id,
        "document_version_id": document_version_id,
        "source_pdf_path": f"local-storage/{file}",
    }


def unemployment_page_text() -> str:
    return "2월중 실업자는 증가하였으며,\n실업률은 4.9%로 전년동월대비 0.8%p 상승\n▪ 실업률은 모든 연령계층에서 상승"


def currency_page_text() -> str:
    return (
        "마. 주요국가의 환율변동 비교\n한국(원/달러)\n절상률\n기간평균\n"
        "2019\n1,157.8\n△3.43\n1,165.65\n108.87\n1.36\n30.09\n1.59\n1.1206\n△2.05\n"
        "2020\n1,088.0\n6.42\n1,180.1\n103.20\n5.49\n28.13\n6.97\n1.2300\n9.76"
    )


def trade_page_text() -> str:
    return (
        "나. 수출입(통관)\n수 출(FOB)\n수 입(CIF)\n수출입차\n금 액\n증가율\n금 액\n증가율\n금 액\n"
        "2023\n6,322.3\n△7.5\n6,425.7\n△12.1\n△103.5\n"
        "2024\n6,836.1\n8.1\n6,317.7\n△1.7\n518.4"
    )


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def numeric_bbox(value: object) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    try:
        return all(isinstance(float(item), float) for item in value)
    except (TypeError, ValueError):
        return False
