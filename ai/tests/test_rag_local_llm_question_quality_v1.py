from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ai" / "scripts"


def load_script(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_for_tests", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_local_llm_probe_rejects_external_endpoint_without_fallback(tmp_path: Path) -> None:
    module = load_script("rag_local_llm_expected_answer_generation_v1")

    report = module.run_probe(
        backend="llamacpp",
        base_url="https://api.example.com/v1",
        model="gemma4-e2b-local",
        output_report=tmp_path / "probe.json",
        output_md=tmp_path / "probe.md",
        check_endpoint=False,
    )

    assert report["status"] == "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
    assert report["local_llm_available"] is False
    assert report["external_api_used"] is False
    assert report["gold_candidates_created"] is False
    assert "external/cloud LLM endpoints are forbidden; use localhost only" in report["blockers"]


def test_local_llm_malformed_json_fails_closed() -> None:
    module = load_script("rag_local_llm_expected_answer_generation_v1")

    try:
        module.parse_strict_json_object("```json\n{\"rewritten_question_ko\":\"질문\"}\n```")
    except ValueError as exc:
        assert "strict JSON object" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("malformed JSON must fail closed")


def test_question_quality_gate_rejects_placeholders_titles_fragments_and_missing_constraints() -> None:
    module = load_script("rag_question_quality_gate_v1")

    assert module.classify_question("expanded_pdf_file_lookup_017", query_id="expanded_pdf_file_lookup_017")[
        "primary_classification"
    ] == "PLACEHOLDER_QUERY_ID"
    assert module.classify_question("경상수지 추이", track="pdf_business_ocr_mm", region_type="heading")[
        "primary_classification"
    ] == "PDF_HEADING_OR_TITLE_AS_QUERY"
    assert module.classify_question("보인 가운데 환율은 글로벌 달러강세 영향으로 상승 약세 , 국고채 금리는")[
        "primary_classification"
    ] == "PDF_OCR_FRAGMENT_AS_QUERY"

    xlsx = module.evaluate_row(
        {
            "query_id": "expanded_xlsx_constraint_013",
            "question": "expanded_xlsx_constraint_013",
            "track": "xlsx_business_structured",
            "proposed_answer": "",
            "proposed_evidence": "",
            "metric": "",
            "period": "",
            "aggregation": "",
            "filters": [],
        }
    )

    assert xlsx["official_candidate_eligible"] is False
    assert "XLSX_PLACEHOLDER_CONSTRAINT" in xlsx["classifications"]
    assert "XLSX_MISSING_METRIC" in xlsx["classifications"]
    assert "XLSX_MISSING_PERIOD" in xlsx["classifications"]
    assert "XLSX_MISSING_AGGREGATION_OR_FILTER" in xlsx["classifications"]


def test_pdf_generation_blocks_file_identity_and_heading_only_rows(tmp_path: Path) -> None:
    module = load_script("rag_pdf_gold_question_candidate_generation_v1")
    rows_path = tmp_path / "pdf_input.jsonl"
    write_jsonl(
        rows_path,
        [
            pdf_row(
                "pdf_content_001",
                matched_text="2024년 수출은 전년 대비 7.0% 증가했다.",
                nearby_paragraphs=["2024년 수출은 전년 대비 7.0% 증가했다."],
            ),
            pdf_row(
                "pdf_file_001",
                matched_text="파일명.pdf",
                nearby_paragraphs=["파일명.pdf"],
                content_evidence_lane="pdf_file_identity",
            ),
            pdf_row(
                "pdf_heading_001",
                matched_text="경상수지 추이",
                nearby_paragraphs=[],
                region_type="heading",
            ),
        ],
    )

    report = module.run_generation(
        input_jsonl=rows_path,
        output_report=tmp_path / "pdf_candidates.json",
        output_md=tmp_path / "pdf_candidates.md",
        llm_client=lambda _prompt: json.dumps(
            {
                "rewritten_question_ko": "2024년 수출은 전년 대비 어떻게 변했나요?",
                "expected_answer_ko": "2024년 수출은 전년 대비 7.0% 증가했다.",
                "supporting_evidence_quote": "2024년 수출은 전년 대비 7.0% 증가했다.",
                "answerability_label_proposed": "ANSWERABLE",
                "relevance_label_proposed": "RELEVANT",
                "confidence": "HIGH",
                "reason": "source-bound",
            },
            ensure_ascii=False,
        ),
        skip_probe=True,
    )

    assert report["status"] == "PDF_LOCAL_LLM_CANDIDATE_GENERATION_COMPLETE"
    assert report["summary"]["generated_candidates"] == 1
    assert report["summary"]["rejected_candidates"] == 2
    assert {row["query_id"] for row in report["candidates"]} == {"pdf_content_001"}
    rejected = {row["query_id"]: row["rejection_reasons"] for row in report["rejected_rows"]}
    assert "PDF_FILE_IDENTITY_LANE_BLOCKED" in rejected["pdf_file_001"]
    assert "PDF_HEADING_OR_TITLE_AS_QUERY" in rejected["pdf_heading_001"]


def test_pdf_generation_fails_closed_when_llm_unavailable(tmp_path: Path) -> None:
    module = load_script("rag_pdf_gold_question_candidate_generation_v1")
    rows_path = tmp_path / "pdf_input.jsonl"
    write_jsonl(rows_path, [pdf_row("pdf_content_001")])

    report = module.run_generation(
        input_jsonl=rows_path,
        output_report=tmp_path / "pdf_candidates.json",
        output_md=tmp_path / "pdf_candidates.md",
        backend="llamacpp",
        base_url="http://127.0.0.1:1/v1",
        model="gemma4-e2b-local",
        timeout_seconds=1,
        skip_probe=False,
    )

    assert report["status"] == "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
    assert report["summary"]["generated_candidates"] == 0
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False


def test_xlsx_generation_requires_constraints_and_preserves_deterministic_numeric_value(tmp_path: Path) -> None:
    module = load_script("rag_xlsx_gold_question_candidate_generation_v1")
    rows_path = tmp_path / "xlsx_input.jsonl"
    write_jsonl(
        rows_path,
        [
            xlsx_row("xlsx_ok_001"),
            xlsx_row("xlsx_hidden_001", hidden=True),
            xlsx_row("xlsx_missing_period_001", row_values=[{"column_label": "매출", "value": "123"}]),
        ],
    )

    report = module.run_generation(
        input_jsonl=rows_path,
        output_report=tmp_path / "xlsx_candidates.json",
        output_md=tmp_path / "xlsx_candidates.md",
        llm_client=lambda _prompt: json.dumps(
            {
                "rewritten_question_ko": "2024년 1월 서울 지점의 매출은 얼마인가요?",
                "expected_answer_ko": "2024년 1월 서울 지점의 매출은 1,234입니다.",
                "supporting_evidence_cells": ["D5"],
                "metric": "매출",
                "period": "2024년 1월",
                "aggregation": "cell_value",
                "filters": ["지점=서울"],
                "answerability_label_proposed": "ANSWERABLE",
                "relevance_label_proposed": "RELEVANT",
                "confidence": "HIGH",
                "reason": "source-bound",
            },
            ensure_ascii=False,
        ),
        skip_probe=True,
    )

    assert report["status"] == "XLSX_LOCAL_LLM_CANDIDATE_GENERATION_COMPLETE"
    assert report["summary"]["generated_candidates"] == 1
    assert report["summary"]["rejected_candidates"] == 2
    assert report["candidates"][0]["deterministic_value"] == "1,234"
    rejected = {row["query_id"]: row["rejection_reasons"] for row in report["rejected_rows"]}
    assert "XLSX_HIDDEN_EXCLUDED_OR_PENDING_ROW_BLOCKED" in rejected["xlsx_hidden_001"]
    assert "XLSX_MISSING_PERIOD" in rejected["xlsx_missing_period_001"]

    tampered = dict(report["candidates"][0])
    tampered["expected_answer_ko"] = "2024년 1월 서울 지점의 매출은 9,999입니다."
    verifier = load_script("rag_local_llm_expected_answer_verifier_v1")
    result = verifier.verify_candidate(tampered)

    assert result["bucket"] == "expected_answer_unsupported"
    assert "XLSX_NUMERIC_VALUE_CHANGED" in result["rejection_reasons"]


def test_pdf_verifier_accepts_source_bound_deterministic_table_value_answer() -> None:
    verifier = load_script("rag_local_llm_expected_answer_verifier_v1")

    result = verifier.verify_candidate(
        {
            "query_id": "gq_pdf_section_question_001",
            "track": "pdf_business_ocr_mm",
            "rewritten_question_ko": "2024년 수출입차 금액은 얼마인가요?",
            "expected_answer_ko": "2024년 수출입차 금액은 518.4억 불입니다.",
            "supporting_evidence_quote": "2024 / 6,836.1 / 8.1 / 6,317.7 / △1.7 / 518.4",
            "source_bound_evidence_text": (
                "수 출(FOB) / 수 입(CIF) / 수출입차 / 금 액 / 증가율 / 금 액 / 증가율 / 금 액 / "
                "2024 / 6,836.1 / 8.1 / 6,317.7 / △1.7 / 518.4"
            ),
            "deterministic_table_values": [
                {"period": "2024", "column": "수출입차 금액", "value": "518.4"}
            ],
            "citation_locator": {
                "page": 61,
                "bbox": [76.68, 103.92, 483.52, 672.6],
                "region_type": "table_body",
                "search_unit_id": "su-table",
            },
            "content_evidence_lane": "pdf_content_evidence",
            "official_metric_input": False,
            "promotion_evidence": False,
        }
    )

    assert result["bucket"] == "clean_candidate_for_human_audit"
    assert result["rejection_reasons"] == []


def test_xlsx_generation_recovers_exact_value_labels_and_derives_precise_value_cell(tmp_path: Path) -> None:
    module = load_script("rag_xlsx_gold_question_candidate_generation_v1")
    rows_path = tmp_path / "xlsx_input.jsonl"
    write_jsonl(
        rows_path,
        [
            xlsx_row(
                "gq_xlsx_lookup_004",
                table_range="A602:D602",
                matched_cells=["A602:D602"],
                target_rows=[602],
                target_columns=["A", "B", "C", "D"],
                column_headers=["대중교통구분", "노선명", "년월", "승차총승객수"],
                row_values=[
                    {"column_label": "노선명", "value": "우이신설선"},
                    {"column_label": "년월", "value": "201905"},
                    {"column_label": "승차총승객수", "value": "1,469,681"},
                ],
            )
        ],
    )

    report = module.run_generation(
        input_jsonl=rows_path,
        output_report=tmp_path / "xlsx_candidates.json",
        output_md=tmp_path / "xlsx_candidates.md",
        llm_client=lambda _prompt: json.dumps(
            {
                "rewritten_question_ko": "2019년 5월 우이신설선의 승차총승객수는 얼마입니까?",
                "expected_answer_ko": "1,469,681명입니다.",
                "supporting_evidence_cells": ["C602"],
                "metric": "승차총승객수",
                "period": "201905",
                "aggregation": "cell_value",
                "filters": ["노선명=우이신설선"],
                "answerability_label_proposed": "EXACT_VALUE_EXTRACTION",
                "relevance_label_proposed": "EXACT_MATCH",
                "confidence": "HIGH",
                "reason": "source-bound",
            },
            ensure_ascii=False,
        ),
        skip_probe=True,
    )

    assert report["summary"]["generated_candidates"] == 1
    assert report["summary"]["rejected_candidates"] == 0
    candidate = report["candidates"][0]
    assert candidate["answerability_label_proposed"] == "ANSWERABLE"
    assert candidate["relevance_label_proposed"] == "RELEVANT"
    assert candidate["deterministic_value_cell"] == "D602"
    assert candidate["supporting_evidence_cells"] == ["D602"]
    assert candidate["citation_locator"]["matched_cells"] == ["D602"]


def test_xlsx_generation_prefers_metric_column_value_cell_over_anchor_matched_cell(tmp_path: Path) -> None:
    module = load_script("rag_xlsx_gold_question_candidate_generation_v1")
    rows_path = tmp_path / "xlsx_input.jsonl"
    write_jsonl(
        rows_path,
        [
            xlsx_row(
                "gq_xlsx_anchor_cell_001",
                table_range="A602:D602",
                matched_cells=["C602"],
                target_rows=[602],
                target_columns=["A", "B", "C", "D"],
                column_headers=["대중교통구분", "노선명", "년월", "승차총승객수"],
                row_values=[
                    {"column_label": "노선명", "value": "우이신설선"},
                    {"column_label": "년월", "value": "201905"},
                    {"column_label": "승차총승객수", "value": "1,469,681"},
                ],
            )
        ],
    )

    report = module.run_generation(
        input_jsonl=rows_path,
        output_report=tmp_path / "xlsx_candidates.json",
        output_md=tmp_path / "xlsx_candidates.md",
        llm_client=lambda _prompt: json.dumps(
            {
                "rewritten_question_ko": "2019년 5월 우이신설선의 승차총승객수는 얼마입니까?",
                "expected_answer_ko": "1,469,681명입니다.",
                "supporting_evidence_cells": ["C602"],
                "metric": "승차총승객수",
                "period": "201905",
                "aggregation": "cell_value",
                "filters": ["노선명=우이신설선"],
                "answerability_label_proposed": "ANSWERABLE",
                "relevance_label_proposed": "RELEVANT",
                "confidence": "HIGH",
                "reason": "source-bound",
            },
            ensure_ascii=False,
        ),
        skip_probe=True,
    )

    candidate = report["candidates"][0]
    assert candidate["deterministic_value_cell"] == "D602"
    assert candidate["supporting_evidence_cells"] == ["D602"]
    assert candidate["citation_locator"]["matched_cells"] == ["D602"]


def test_xlsx_generation_uses_manual_query_for_non_subway_candidate_without_llm(tmp_path: Path) -> None:
    module = load_script("rag_xlsx_gold_question_candidate_generation_v1")
    verifier = load_script("rag_local_llm_expected_answer_verifier_v1")
    rows_path = tmp_path / "xlsx_input.jsonl"
    row = xlsx_row(
        "gq_xlsx_lookup_007",
        table_range="A2:J51",
        matched_cells=["A2:J51"],
        target_rows=[2],
        target_columns=["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
        column_headers=[
            "장기요양기관코드",
            "장기요양기관이름",
            "우편번호",
            "시도코드",
            "시군구코드",
            "법정동코드",
            "시도 시군구 법정동명",
            "지정일자",
            "설치신고일자",
            "기관별 상세주소",
        ],
        row_values=[
            {"column_label": "장기요양기관이름", "value": "청운노인요양원"},
            {"column_label": "지정일자", "value": "2008-06-25"},
            {"column_label": "기관별 상세주소", "value": "서울특별시 종로구 비봉길 76 (구기동)"},
        ],
    )
    row["formatter_input"]["file"] = "국민건강보험공단_장기요양기관 시설별 현황_20240716.xlsx"
    row["formatter_input"]["sheet"] = "일반현황"
    row["citation_items"][0]["locator"]["file"] = row["formatter_input"]["file"]
    row["citation_items"][0]["locator"]["sheet"] = "일반현황"
    write_jsonl(rows_path, [row])

    def fail_if_called(_prompt: str) -> str:
        raise AssertionError("manual XLSX query candidates must not call the LLM")

    report = module.run_generation(
        input_jsonl=rows_path,
        output_report=tmp_path / "xlsx_candidates.json",
        output_md=tmp_path / "xlsx_candidates.md",
        llm_client=fail_if_called,
    )

    assert report["summary"]["generated_candidates"] == 1
    assert report["summary"]["rejected_candidates"] == 0
    assert report["summary"]["manual_query_candidates"] == 1
    candidate = report["candidates"][0]
    assert candidate["rewritten_question_ko"] == "2008년 6월에 지정된 청운노인요양원의 기관별 상세주소는 무엇입니까?"
    assert candidate["deterministic_value_cell"] == "J2"
    assert candidate["supporting_evidence_cells"] == ["J2"]
    assert candidate["citation_locator"]["matched_cells"] == ["J2"]
    assert candidate["model_assisted_diagnostic_only"] is False
    assert candidate["local_llm_meta"]["manual_curation"] is True
    assert verifier.verify_candidate(candidate)["bucket"] == "clean_candidate_for_human_audit"


def test_xlsx_verifier_rejects_duplicates_missing_periods_and_wide_evidence_cells(tmp_path: Path) -> None:
    verifier = load_script("rag_local_llm_expected_answer_verifier_v1")
    xlsx_report = tmp_path / "xlsx_candidates.json"
    write_json(
        xlsx_report,
        {
            "candidates": [
                xlsx_candidate(
                    "gq_xlsx_lookup_001",
                    question="2017년 11월 지하철 1호선의 승차총승객수는 얼마입니까?",
                    period="201711",
                    value="8,633,618",
                    value_cell="D2",
                    filters=["노선명=1호선"],
                ),
                xlsx_candidate(
                    "gq_xlsx_aggregation_002",
                    question="2017년 11월 지하철 1호선의 승차총승객수는 얼마입니까?",
                    period="201711",
                    value="8,633,618",
                    value_cell="D2",
                    filters=["노선명=1호선"],
                ),
                xlsx_candidate(
                    "gq_auto_036",
                    question="경인선 지하철의 승차총승객수는 얼마입니까?",
                    period="201804",
                    value="10,356,250",
                    value_cell="D102",
                    filters=["노선명=경인선"],
                ),
                xlsx_candidate(
                    "gq_auto_040",
                    question="2019년 2월 수인선 지하철의 승차총승객수는 얼마입니까?",
                    period="201902",
                    value="1,124,736",
                    value_cell="D302",
                    filters=["노선명=수인선"],
                    supporting_cells=["A302:D351"],
                ),
            ]
        },
    )

    report = verifier.run_verifier(
        pdf_candidate_report=tmp_path / "missing_pdf.json",
        xlsx_candidate_report=xlsx_report,
        output_report=tmp_path / "verified.json",
        output_md=tmp_path / "verified.md",
    )

    by_id = {row["query_id"]: row for row in report["verified_candidates"]}
    assert by_id["gq_xlsx_lookup_001"]["bucket"] == "clean_candidate_for_human_audit"
    assert "XLSX_DUPLICATE_CANDIDATE" in by_id["gq_xlsx_aggregation_002"]["rejection_reasons"]
    assert "XLSX_QUESTION_MISSING_PERIOD" in by_id["gq_auto_036"]["rejection_reasons"]
    assert "XLSX_SUPPORTING_EVIDENCE_RANGE_TOO_WIDE" in by_id["gq_auto_040"]["rejection_reasons"]
    assert report["summary"]["clean_candidates"] == 1
    assert report["summary"]["rejected_candidates"] == 3
    assert report["bucket_counts"]["exclude_from_official_gold_candidate"] == 3


def test_xlsx_verifier_checks_locator_cells_and_dedupes_only_clean_candidates(tmp_path: Path) -> None:
    verifier = load_script("rag_local_llm_expected_answer_verifier_v1")
    invalid_first = xlsx_candidate(
        "gq_invalid_first",
        question="경인선 지하철의 승차총승객수는 얼마입니까?",
        period="201804",
        value="10,356,250",
        value_cell="D102",
        filters=["노선명=경인선"],
    )
    valid_second = xlsx_candidate(
        "gq_valid_second",
        question="2018년 4월 경인선 지하철의 승차총승객수는 얼마입니까?",
        period="201804",
        value="10,356,250",
        value_cell="D102",
        filters=["노선명=경인선"],
    )
    wide_locator = xlsx_candidate(
        "gq_wide_locator",
        question="2019년 5월 우이신설선의 승차총승객수는 얼마입니까?",
        period="201905",
        value="1,469,681",
        value_cell="D602",
        filters=["노선명=우이신설선"],
        supporting_cells=["D602"],
    )
    wide_locator["citation_locator"]["matched_cells"] = ["A602:D602"]

    results = verifier.verify_candidates([invalid_first, valid_second, wide_locator])
    by_id = {row["query_id"]: row for row in results}

    assert "XLSX_QUESTION_MISSING_PERIOD" in by_id["gq_invalid_first"]["rejection_reasons"]
    assert "XLSX_DUPLICATE_CANDIDATE" not in by_id["gq_valid_second"]["rejection_reasons"]
    assert by_id["gq_valid_second"]["bucket"] == "clean_candidate_for_human_audit"
    assert "XLSX_LOCATOR_MATCHED_CELLS_RANGE_TOO_WIDE" in by_id["gq_wide_locator"]["rejection_reasons"]


def test_xlsx_verifier_accepts_unpadded_period_aliases() -> None:
    verifier = load_script("rag_local_llm_expected_answer_verifier_v1")
    candidate = xlsx_candidate(
        "gq_period_alias",
        question="2019년 5월 우이신설선의 승차총승객수는 얼마입니까?",
        period="2019.05",
        value="1,469,681",
        value_cell="D602",
        filters=["노선명=우이신설선"],
    )

    result = verifier.verify_candidate(candidate)

    assert result["bucket"] == "clean_candidate_for_human_audit"
    assert "XLSX_QUESTION_MISSING_PERIOD" not in result["rejection_reasons"]


def test_verifier_accepts_source_bound_pdf_candidate_and_rejects_query_echo() -> None:
    verifier = load_script("rag_local_llm_expected_answer_verifier_v1")
    candidate = {
        "track": "pdf_business_ocr_mm",
        "query_id": "pdf_content_001",
        "rewritten_question_ko": "2024년 수출은 전년 대비 어떻게 변했나요?",
        "expected_answer_ko": "2024년 수출은 전년 대비 7.0% 증가했다.",
        "supporting_evidence_quote": "2024년 수출은 전년 대비 7.0% 증가했다.",
        "source_bound_evidence_text": "2024년 수출은 전년 대비 7.0% 증가했다.",
        "content_evidence_lane": "pdf_content_evidence",
        "citation_locator": {"page": 1, "bbox": [1, 2, 3, 4], "region_type": "paragraph"},
        "search_unit_id": "su-1",
        "official_metric_input": False,
        "promotion_evidence": False,
    }

    assert verifier.verify_candidate(candidate)["bucket"] == "clean_candidate_for_human_audit"

    bad = dict(candidate)
    bad["rewritten_question_ko"] = "pdf_content_001"
    assert verifier.verify_candidate(bad)["bucket"] == "local_llm_output_invalid"


def test_human_audit_packet_v2_keeps_generated_rows_diagnostic_only_and_official_rows_zero(tmp_path: Path) -> None:
    module = load_script("rag_human_audit_packet_v2_question_quality_local_llm")
    text_v1 = [
        {
            "row_id": "text_namu_v2_0017",
            "query_id": "text_namu_v2_0017",
            "track": "text_namu_v2_1",
            "question": "실바니안 실크 고양이 가족 설명은 어떤 성격과 역할을 말해",
            "proposed_answer": "실크고양이 소년은 상냥하며 배려심이 넘친다.",
            "proposed_evidence": "실크고양이 소년은 상냥하며 배려심이 넘친다.",
            "citation_locator": {"cited_chunk_ids": ["chunk-1"]},
            "official_denominator_current": False,
            "promotion_evidence": False,
        },
        {
            "row_id": "expanded_pdf_file_lookup_017",
            "query_id": "expanded_pdf_file_lookup_017",
            "track": "pdf_business_ocr_mm",
            "question": "expanded_pdf_file_lookup_017",
            "proposed_answer": "",
            "proposed_evidence": "Exact or canonical file identity is missing or ambiguous.",
            "citation_locator": {},
            "official_denominator_current": False,
            "promotion_evidence": False,
        },
    ]
    v1_path = tmp_path / "v1.json"
    write_json(v1_path, {"actionable_rows": text_v1, "summary": {"total_user_action_rows": 19}})

    verifier_path = tmp_path / "verified.json"
    write_json(
        verifier_path,
        {
            "verified_candidates": [
                {
                    "bucket": "clean_candidate_for_human_audit",
                    "track": "pdf_business_ocr_mm",
                    "query_id": "pdf_content_001",
                    "rewritten_question_ko": "2024년 수출은 전년 대비 어떻게 변했나요?",
                    "expected_answer_ko": "2024년 수출은 전년 대비 7.0% 증가했다.",
                    "supporting_evidence_quote": "2024년 수출은 전년 대비 7.0% 증가했다.",
                    "citation_locator": {"page": 1, "bbox": [1, 2, 3, 4], "region_type": "paragraph"},
                    "source_packet_role": "manual_source_bound_pdf_context_v2",
                    "model_assisted_diagnostic_only": True,
                    "official_metric_input": False,
                    "promotion_evidence": False,
                }
            ],
            "bucket_counts": {"clean_candidate_for_human_audit": 1, "exclude_from_official_gold_candidate": 1},
            "summary": {"official_metric_input_rows": 0, "promotion_evidence": False},
        },
    )

    packet = module.run_packet(
        human_audit_v1_path=v1_path,
        verifier_report_path=verifier_path,
        output_report=tmp_path / "v2.json",
        output_md=tmp_path / "v2.md",
    )

    rows = packet["actionable_rows"]
    assert packet["status"] == "HUMAN_AUDIT_PACKET_V2_READY"
    assert packet["summary"]["original_action_rows"] == 19
    assert packet["summary"]["official_metric_input_rows"] == 0
    assert packet["summary"]["pdf_manual_candidates"] == 1
    assert packet["summary"]["pdf_local_llm_candidates"] == 0
    assert packet["promotion_evidence"] is False
    assert packet["summary"]["final_user_action_rows_by_track"] == {"pdf_business_ocr_mm": 1, "text_namu_v2_1": 1}
    assert all(row["human_review_required"] is True for row in rows)
    assert all(row["official_metric_input"] is False for row in rows)
    assert all(row["promotion_evidence"] is False for row in rows)
    assert all(row["official_denominator_current"] is False for row in rows)
    generated = [row for row in rows if row["track"] == "pdf_business_ocr_mm"][0]
    assert generated["model_assisted_diagnostic_only"] is True
    assert generated["issue_type"] == "MANUAL_SOURCE_BOUND_PDF_QUESTION_EXPECTED_ANSWER_DRAFT"
    assert generated["source_packet_role"] == "manual_source_bound_pdf_context_v2"
    assert generated["gold_promoted"] is False
    assert "expanded_pdf_file_lookup_017" not in {row["query_id"] for row in rows}

    labeled_packet = module.run_packet(
        human_audit_v1_path=v1_path,
        verifier_report_path=verifier_path,
        output_report=tmp_path / "v2_labeled.json",
        output_md=tmp_path / "v2_labeled.md",
        apply_all_human_label="INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE",
        human_notes="User reviewed all rows and approved them as candidates.",
    )

    assert labeled_packet["human_audit_completed"] is True
    assert labeled_packet["summary"]["human_labeled_rows"] == 2
    assert labeled_packet["summary"]["human_unlabeled_rows"] == 0
    assert labeled_packet["human_audit_label_counts"] == {"INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE": 2}
    assert all(row["human_label"] == "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE" for row in labeled_packet["actionable_rows"])
    assert all(row["official_metric_input"] is False for row in labeled_packet["actionable_rows"])
    assert all(row["promotion_evidence"] is False for row in labeled_packet["actionable_rows"])
    assert labeled_packet["guardrails"]["official_denominator_registry_mutation"] is False


def test_protected_path_diff_check_reports_registry_unchanged() -> None:
    verifier = load_script("rag_local_llm_expected_answer_verifier_v1")
    protected = verifier.protected_path_diff_check(
        changed_paths=[
            "ai/eval/review/rag_human_audit_packet_v2_question_quality_local_llm.json",
            "ai/eval/reports/rag-ingestion/question_quality_gate_report_v1.json",
        ]
    )

    assert protected["official_denominator_registry_changed"] is False
    assert protected["candidate_artifact_changed"] is False
    assert protected["gold_registry_changed"] is False
    assert protected["production_vector_or_index_changed"] is False


def pdf_row(
    query_id: str,
    *,
    matched_text: str = "2024년 수출은 전년 대비 7.0% 증가했다.",
    nearby_paragraphs: list[str] | None = None,
    content_evidence_lane: str = "pdf_content_evidence",
    region_type: str = "paragraph",
) -> dict:
    return {
        "query_id": query_id,
        "track": "pdf_business_ocr_mm",
        "content_evidence_lane": content_evidence_lane,
        "matched_text": matched_text,
        "nearby_paragraphs": nearby_paragraphs
        if nearby_paragraphs is not None
        else ["2024년 수출은 전년 대비 7.0% 증가했다."],
        "page": 1,
        "bbox": [1, 2, 3, 4],
        "region_type": region_type,
        "search_unit_id": "su-1",
        "document_version_id": "docv-1",
        "file": "경제.pdf",
        "citation_locator": {"page": 1, "bbox": [1, 2, 3, 4], "region_type": region_type},
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def xlsx_row(
    query_id: str,
    *,
    hidden: bool = False,
    row_values: list[dict] | None = None,
    table_range: str = "A1:D10",
    matched_cells: list[str] | None = None,
    target_rows: list[int] | None = None,
    target_columns: list[str] | None = None,
    column_headers: list[str] | None = None,
) -> dict:
    values = row_values or [
        {"column_label": "지점", "value": "서울", "cell": "A5"},
        {"column_label": "년월", "value": "2024년 1월", "cell": "B5"},
        {"column_label": "매출", "value": "1,234", "cell": "D5"},
    ]
    return {
        "query_id": query_id,
        "track": "xlsx_business_structured",
        "hidden": hidden,
        "excluded": False,
        "pending": False,
        "formatter_input": {
            "file": "매출.xlsx",
            "sheet": "Sheet1",
            "table_range": table_range,
            "matched_cells": matched_cells or ["D5"],
            "target_rows": target_rows or [5],
            "target_columns": target_columns or ["A", "B", "C", "D"],
            "column_headers": column_headers or ["지점", "년월", "매출"],
            "row_values": values,
            "nearby_rows": [{"row_text": "지점: 서울 | 년월: 2024년 1월 | 매출: 1,234"}],
        },
        "citation_items": [
            {
                "locator": {
                    "file": "매출.xlsx",
                    "sheet": "Sheet1",
                    "range": table_range,
                    "matched_cells": matched_cells or ["D5"],
                }
            }
        ],
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def xlsx_candidate(
    query_id: str,
    *,
    question: str,
    period: str,
    value: str,
    value_cell: str,
    filters: list[str],
    supporting_cells: list[str] | None = None,
) -> dict:
    return {
        "track": "xlsx_business_structured",
        "query_id": query_id,
        "rewritten_question_ko": question,
        "expected_answer_ko": f"{value}명입니다.",
        "metric": "승차총승객수",
        "period": period,
        "aggregation": "cell_value",
        "filters": filters,
        "deterministic_metric": "승차총승객수",
        "deterministic_period": period,
        "deterministic_aggregation": "cell_value",
        "deterministic_filters": filters,
        "deterministic_value": value,
        "deterministic_value_cell": value_cell,
        "supporting_evidence_cells": supporting_cells or [value_cell],
        "workbook": "서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx",
        "sheet": "철도",
        "table_range": "A1:D999",
        "citation_locator": {
            "file": "서울시 대중교통 수단별 이용 현황(2017.11~2019.5).xlsx",
            "sheet": "철도",
            "range": "A1:D999",
            "matched_cells": supporting_cells or [value_cell],
        },
        "official_metric_input": False,
        "promotion_evidence": False,
    }
