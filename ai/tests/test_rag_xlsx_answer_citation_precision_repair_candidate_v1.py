from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_xlsx_answer_citation_precision_repair_candidate_v1.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "rag_xlsx_answer_citation_precision_repair_candidate_v1_for_tests",
        SCRIPT_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_broad_transport_range_repairs_to_single_target_row_without_gold_fields():
    module = load_module()
    candidate = module.build_repair_candidate(
        repair_input(
            query_id="gq_auto_012",
            question="2019년 2월 5호선의 승차총승객수는 몇 명입니까?",
            citation_text=(
                "대중교통구분: 지하철 | 노선명: 5호선 | 년월: 201902 | 승차총승객수: 15,446,522; "
                "대중교통구분: 지하철 | 노선명: 5호선 | 년월: 201903 | 승차총승객수: 18,834,177"
            ),
            locator={
                "sheet": "철도",
                "range": "A352:D401",
                "target_rows": [352, 353],
                "target_columns": ["A", "B", "C", "D"],
                "search_unit_id": "su-1",
                "document_version_id": "docv-1",
            },
        )
    )

    assert candidate["repair_applied"] is True
    assert candidate["repaired_locator"]["original_range"] == "A352:D401"
    assert candidate["repaired_locator"]["repaired_range"] == "A352:D352"
    assert candidate["repaired_locator"]["repair_basis"] == "citation_text_first_segment_and_locator_target_rows_0"
    assert candidate["repaired_locator"]["repair_confidence"] == "deterministic"
    assert candidate["candidate_answer"] == "15,446,522입니다."
    assert candidate["gold_fields_used_for_generation"] is False


def test_broad_care_facility_range_repairs_to_single_target_row():
    module = load_module()
    candidate = module.build_repair_candidate(
        repair_input(
            query_id="gq_auto_018",
            question="하얀민들레노인요양원의 우편번호는 무엇입니까?",
            citation_text=(
                "장기요양기관코드: 12,717,000,382 | 장기요양기관이름: 하얀민들레노인요양원 | "
                "우편번호: 41786 | 시도코드: 27 | 시군구코드: 170"
            ),
            locator={
                "sheet": "일반현황",
                "range": "A702:J751",
                "target_rows": [702, 703],
                "target_columns": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
                "search_unit_id": "su-2",
                "document_version_id": "docv-2",
            },
        )
    )

    assert candidate["repair_applied"] is True
    assert candidate["repaired_locator"]["repaired_range"] == "A702:J702"
    assert candidate["candidate_answer"] == "41786입니다."


def test_target_column_extraction_for_address_install_date_and_legal_dong_name():
    module = load_module()
    citation_text = (
        "장기요양기관이름: 신논현요양원 | 우편번호: 21666 | 시도 시군구 법정동명: 인천광역시 남동구 논현동 | "
        "지정일자: 2019-03-15 | 설치신고일자: 2019-03-15 | 기관별 상세주소: 인천광역시 남동구 논고개로 120 6층"
    )

    assert module.extract_candidate_answer("신논현요양원의 기관별 상세주소는 무엇입니까?", citation_text)[
        "candidate_answer"
    ] == "인천광역시 남동구 논고개로 120 6층입니다."
    assert module.extract_candidate_answer("신논현요양원의 설치신고일자는 언제입니까?", citation_text)[
        "candidate_answer"
    ] == "2019-03-15입니다."
    assert module.extract_candidate_answer("신논현요양원의 시도 시군구 법정동명은 무엇입니까?", citation_text)[
        "candidate_answer"
    ] == "인천광역시 남동구 논현동입니다."


def test_generation_repair_api_does_not_accept_gold_reference_fields():
    module = load_module()
    signature = inspect.signature(module.build_repair_candidate)

    assert "expected_answer" not in signature.parameters
    assert "supporting_evidence" not in signature.parameters
    assert module.build_repair_candidate(
        {
            **repair_input(
                query_id="bad",
                question="우편번호는?",
                citation_text="우편번호: 41786",
                locator={
                    "sheet": "일반현황",
                    "range": "A702:J751",
                    "target_rows": [702],
                    "target_columns": ["A", "B", "C"],
                    "search_unit_id": "su",
                    "document_version_id": "docv",
                },
            ),
            "expected_answer": "41786입니다.",
        }
    )["repair_confidence"] == "failed"


def test_hidden_excluded_leakage_guardrail_blocks_repair():
    module = load_module()
    candidate = module.build_repair_candidate(
        repair_input(
            query_id="leak",
            question="우편번호는?",
            citation_text="우편번호: 41786",
            locator={
                "sheet": "일반현황",
                "range": "A702:J751",
                "target_rows": [702],
                "target_columns": ["A", "B", "C"],
                "search_unit_id": "su",
                "document_version_id": "docv",
            },
            hidden_excluded_leakage_count=1,
        )
    )

    assert candidate["repair_applied"] is False
    assert candidate["repair_confidence"] == "failed"
    assert candidate["repair_failure_reason"] == "hidden_excluded_leakage"
    assert candidate["production_mutation"] is False
    assert candidate["promotion_evidence"] is False


def test_ambiguous_multi_row_citation_fails_closed():
    module = load_module()
    candidate = module.build_repair_candidate(
        repair_input(
            query_id="ambiguous",
            question="값은 무엇입니까?",
            citation_text="A열: 첫값 | B열: 둘째값; A열: 다른값 | B열: 또다른값",
            locator={
                "sheet": "Sheet1",
                "range": "A1:B50",
                "target_rows": [1, 2],
                "target_columns": ["A", "B"],
                "search_unit_id": "su",
                "document_version_id": "docv",
            },
        )
    )

    assert candidate["repair_applied"] is False
    assert candidate["repair_confidence"] == "failed"
    assert candidate["repair_failure_reason"] == "target_column_ambiguous_or_missing"


def test_candidate_run_emits_report_only_artifacts_for_actual_baseline(tmp_path: Path):
    module = load_module()
    report_path = tmp_path / "candidate.json"
    md_path = tmp_path / "candidate.md"
    results_path = tmp_path / "candidate.jsonl"

    report = module.run_candidate(
        baseline_report_path=ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "official_answer_citation_metric_first_run_v1.json",
        scorer_results_path=ROOT / "ai" / "eval" / "reports" / "rag-ingestion" / "official_answer_citation_scorer_results_v1.jsonl",
        xlsx_gold_csv_path=ROOT / "ai" / "eval" / "eval_queries" / "gold_queries_xlsx_question_gold_v2.csv",
        output_report=report_path,
        output_md=md_path,
        output_results_jsonl=results_path,
    )

    assert report["report_only"] is True
    assert report["promotion_evidence"] is False
    assert report["threshold_tuning"] is False
    assert report["production_mutation"] is False
    assert report["gold_mutation"] is False
    assert report["denominator_mutation"] is False
    assert report["xlsx_repair_attempted_count"] == 18
    assert report["xlsx_repair_applied_count"] == 18
    assert report["xlsx_repair_failed_count"] == 0
    assert report["candidate_failure_category_counts"]["PASS"] > report["baseline_failure_category_counts"]["PASS"]
    assert all(row["gold_fields_used_for_generation"] is False for row in report["xlsx_candidate_rows"])
    assert len(report["xlsx_candidate_result_rows"]) == 18
    assert {
        "query_id",
        "original_failure_category",
        "repaired_failure_category",
        "original_answer",
        "repaired_answer",
        "original_citation_range",
        "repaired_citation_range",
        "gold_fields_used_for_generation",
    } <= set(report["xlsx_candidate_result_rows"][0])
    assert all(row["gold_fields_used_for_generation"] is False for row in report["xlsx_candidate_result_rows"])
    md_text = md_path.read_text(encoding="utf-8")
    assert "## XLSX Before/After Rows" in md_text
    assert "A352:D401 -> A352:D352" in md_text
    assert "A702:J751 -> A702:J702" in md_text
    assert len([json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line]) == 29


def repair_input(
    *,
    query_id: str,
    question: str,
    citation_text: str,
    locator: dict,
    hidden_excluded_leakage_count: int = 0,
) -> dict:
    return {
        "query_id": query_id,
        "question": question,
        "diagnostic_xlsx_citation_failure_subtype": "support_cell_inside_locator_range_but_locator_too_broad",
        "generated_answer": "",
        "generated_citation": {"citation_text": citation_text, "locator": locator},
        "hidden_excluded_leakage_count": hidden_excluded_leakage_count,
    }
