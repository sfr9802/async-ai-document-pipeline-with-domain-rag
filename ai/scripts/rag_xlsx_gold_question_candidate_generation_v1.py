"""Generate diagnostic XLSX question/expected-answer candidates with a local LLM."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from rag_local_llm_expected_answer_generation_v1 import (  # noqa: E402
    DEFAULT_BACKEND,
    DEFAULT_MODEL,
    call_local_llm_strict_json,
    clean,
    local_llm_entry_blockers,
    read_jsonl,
    repo_relative,
    resolve_base_url,
    utc_timestamp,
    write_json,
)
from rag_question_quality_gate_v1 import classify_question  # noqa: E402


REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_INPUT_JSONL = REPORT_DIR / "xlsx_answer_citation_diagnostic_review_input.jsonl"
DEFAULT_OUTPUT_JSON = REVIEW_DIR / "rag_xlsx_gold_question_candidate_generation_v1.json"
DEFAULT_OUTPUT_MD = REVIEW_DIR / "rag_xlsx_gold_question_candidate_generation_v1.md"

METRIC_HINTS = ("승차", "매출", "금액", "수량", "건수", "비율", "율", "가격", "점수", "투자", "생산", "수출", "수입")
PERIOD_HINTS = ("년월", "기간", "일자", "날짜", "월", "연도", "date", "period")
FILTER_BLOCKLIST = ("코드", "우편번호", "주소")

# These queries are hand-written gold-candidate drafts. The script may package
# them into the diagnostic report, but it must not invent the query text.
MANUAL_XLSX_CANDIDATES: dict[str, dict[str, Any]] = {
    "gq_xlsx_lookup_001": {
        "rewritten_question_ko": "2017년 11월 1호선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "8,633,618명입니다.",
        "metric": "승차총승객수",
        "period": "201711",
        "aggregation": "cell_value",
        "filters": ["노선명=1호선"],
        "deterministic_value": "8,633,618",
        "deterministic_value_cell": "D2",
        "supporting_evidence_cells": ["D2"],
    },
    "gq_xlsx_lookup_004": {
        "rewritten_question_ko": "2019년 5월 우이신설선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "1,469,681명입니다.",
        "metric": "승차총승객수",
        "period": "201905",
        "aggregation": "cell_value",
        "filters": ["노선명=우이신설선"],
        "deterministic_value": "1,469,681",
        "deterministic_value_cell": "D602",
        "supporting_evidence_cells": ["D602"],
    },
    "gq_xlsx_lookup_005": {
        "rewritten_question_ko": "2018년 4월 경인선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "10,356,250명입니다.",
        "metric": "승차총승객수",
        "period": "201804",
        "aggregation": "cell_value",
        "filters": ["노선명=경인선"],
        "deterministic_value": "10,356,250",
        "deterministic_value_cell": "D102",
        "supporting_evidence_cells": ["D102"],
    },
    "gq_xlsx_lookup_006": {
        "rewritten_question_ko": "2019년 2월 수인선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "1,124,736명입니다.",
        "metric": "승차총승객수",
        "period": "201902",
        "aggregation": "cell_value",
        "filters": ["노선명=수인선"],
        "deterministic_value": "1,124,736",
        "deterministic_value_cell": "D302",
        "supporting_evidence_cells": ["D302"],
    },
    "gq_xlsx_lookup_007": {
        "rewritten_question_ko": "2008년 6월에 지정된 청운노인요양원의 기관별 상세주소는 무엇입니까?",
        "expected_answer_ko": "서울특별시 종로구 비봉길 76 (구기동)입니다.",
        "metric": "기관별 상세주소",
        "period": "2008-06-25",
        "aggregation": "cell_value",
        "filters": ["장기요양기관이름=청운노인요양원"],
        "deterministic_value": "서울특별시 종로구 비봉길 76 (구기동)",
        "deterministic_value_cell": "J2",
        "supporting_evidence_cells": ["J2"],
    },
    "gq_xlsx_lookup_008": {
        "rewritten_question_ko": "2015년 6월에 지정된 부여효요양원의 기관별 상세주소는 무엇입니까?",
        "expected_answer_ko": "충청남도 부여군 석성면 왕릉로 773 (석성면)입니다.",
        "metric": "기관별 상세주소",
        "period": "2015-06-02",
        "aggregation": "cell_value",
        "filters": ["장기요양기관이름=부여효요양원"],
        "deterministic_value": "충청남도 부여군 석성면 왕릉로 773 (석성면)",
        "deterministic_value_cell": "J5002",
        "supporting_evidence_cells": ["J5002"],
    },
    "gq_xlsx_date_number_format_001": {
        "rewritten_question_ko": "2008년 6월에 지정된 청운노인요양원의 지정일자는 정확히 언제입니까?",
        "expected_answer_ko": "2008-06-25입니다.",
        "metric": "지정일자",
        "period": "2008-06-25",
        "aggregation": "cell_value",
        "filters": ["장기요양기관이름=청운노인요양원"],
        "deterministic_value": "2008-06-25",
        "deterministic_value_cell": "H2",
        "supporting_evidence_cells": ["H2"],
    },
    "gq_xlsx_aggregation_002": {
        "rewritten_question_ko": "2017년 11월 1호선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "8,633,618명입니다.",
        "metric": "승차총승객수",
        "period": "201711",
        "aggregation": "cell_value",
        "filters": ["노선명=1호선"],
        "deterministic_value": "8,633,618",
        "deterministic_value_cell": "D2",
        "supporting_evidence_cells": ["D2"],
    },
    "gq_auto_012": {
        "rewritten_question_ko": "2019년 2월 5호선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "15,446,522명입니다.",
        "metric": "승차총승객수",
        "period": "201902",
        "aggregation": "cell_value",
        "filters": ["노선명=5호선"],
        "deterministic_value": "15,446,522",
        "deterministic_value_cell": "D352",
        "supporting_evidence_cells": ["D352"],
    },
    "gq_auto_017": {
        "rewritten_question_ko": "2019년 5월 우이신설선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "1,469,681명입니다.",
        "metric": "승차총승객수",
        "period": "201905",
        "aggregation": "cell_value",
        "filters": ["노선명=우이신설선"],
        "deterministic_value": "1,469,681",
        "deterministic_value_cell": "D602",
        "supporting_evidence_cells": ["D602"],
    },
    "gq_auto_018": {
        "rewritten_question_ko": "2020년 11월에 지정된 하얀민들레노인요양원의 우편번호는 무엇입니까?",
        "expected_answer_ko": "41786입니다.",
        "metric": "우편번호",
        "period": "2020-11-26",
        "aggregation": "cell_value",
        "filters": ["장기요양기관이름=하얀민들레노인요양원"],
        "deterministic_value": "41786",
        "deterministic_value_cell": "C702",
        "supporting_evidence_cells": ["C702"],
    },
    "gq_auto_022": {
        "rewritten_question_ko": "2017년 12월 9호선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "8,048,476명입니다.",
        "metric": "승차총승객수",
        "period": "201712",
        "aggregation": "cell_value",
        "filters": ["노선명=9호선"],
        "deterministic_value": "8,048,476",
        "deterministic_value_cell": "D452",
        "supporting_evidence_cells": ["D452"],
    },
    "gq_auto_023": {
        "rewritten_question_ko": "2014년 12월에 지정된 해뜨는요양원2의 시도 시군구 법정동명은 무엇입니까?",
        "expected_answer_ko": "대구광역시 북구 복현동입니다.",
        "metric": "시도 시군구 법정동명",
        "period": "2014-12-31",
        "aggregation": "cell_value",
        "filters": ["장기요양기관이름=해뜨는요양원2"],
        "deterministic_value": "대구광역시 북구 복현동",
        "deterministic_value_cell": "G752",
        "supporting_evidence_cells": ["G752"],
    },
    "gq_auto_028": {
        "rewritten_question_ko": "2012년 3월에 지정된 해오름요양원의 기관별 상세주소는 무엇입니까?",
        "expected_answer_ko": "대구광역시 수성구 파동로51길 96 (파동)입니다.",
        "metric": "기관별 상세주소",
        "period": "2012-03-06",
        "aggregation": "cell_value",
        "filters": ["장기요양기관이름=해오름요양원"],
        "deterministic_value": "대구광역시 수성구 파동로51길 96 (파동)",
        "deterministic_value_cell": "J802",
        "supporting_evidence_cells": ["J802"],
    },
    "gq_auto_031": {
        "rewritten_question_ko": "2018년 7월 8호선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "5,630,084명입니다.",
        "metric": "승차총승객수",
        "period": "201807",
        "aggregation": "cell_value",
        "filters": ["노선명=8호선"],
        "deterministic_value": "5,630,084",
        "deterministic_value_cell": "D402",
        "supporting_evidence_cells": ["D402"],
    },
    "gq_auto_034": {
        "rewritten_question_ko": "2018년 5월 의정부경전철의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "1,095,397명입니다.",
        "metric": "승차총승객수",
        "period": "201805",
        "aggregation": "cell_value",
        "filters": ["노선명=의정부경전철"],
        "deterministic_value": "1,095,397",
        "deterministic_value_cell": "D552",
        "supporting_evidence_cells": ["D552"],
    },
    "gq_auto_035": {
        "rewritten_question_ko": "2018년 11월 3호선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "17,956,555명입니다.",
        "metric": "승차총승객수",
        "period": "201811",
        "aggregation": "cell_value",
        "filters": ["노선명=3호선"],
        "deterministic_value": "17,956,555",
        "deterministic_value_cell": "D52",
        "supporting_evidence_cells": ["D52"],
    },
    "gq_auto_036": {
        "rewritten_question_ko": "2018년 4월 경인선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "10,356,250명입니다.",
        "metric": "승차총승객수",
        "period": "201804",
        "aggregation": "cell_value",
        "filters": ["노선명=경인선"],
        "deterministic_value": "10,356,250",
        "deterministic_value_cell": "D102",
        "supporting_evidence_cells": ["D102"],
    },
    "gq_auto_037": {
        "rewritten_question_ko": "2019년 4월 안산선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "4,230,809명입니다.",
        "metric": "승차총승객수",
        "period": "201904",
        "aggregation": "cell_value",
        "filters": ["노선명=안산선"],
        "deterministic_value": "4,230,809",
        "deterministic_value_cell": "D152",
        "supporting_evidence_cells": ["D152"],
    },
    "gq_auto_038": {
        "rewritten_question_ko": "2018년 9월 일산선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "3,258,215명입니다.",
        "metric": "승차총승객수",
        "period": "201809",
        "aggregation": "cell_value",
        "filters": ["노선명=일산선"],
        "deterministic_value": "3,258,215",
        "deterministic_value_cell": "D202",
        "supporting_evidence_cells": ["D202"],
    },
    "gq_auto_040": {
        "rewritten_question_ko": "2019년 2월 수인선의 승차총승객수는 몇 명입니까?",
        "expected_answer_ko": "1,124,736명입니다.",
        "metric": "승차총승객수",
        "period": "201902",
        "aggregation": "cell_value",
        "filters": ["노선명=수인선"],
        "deterministic_value": "1,124,736",
        "deterministic_value_cell": "D302",
        "supporting_evidence_cells": ["D302"],
    },
    "gq_auto_043": {
        "rewritten_question_ko": "2019년 3월에 지정된 신논현요양원의 설치신고일자는 언제입니까?",
        "expected_answer_ko": "2019-03-15입니다.",
        "metric": "설치신고일자",
        "period": "2019-03-15",
        "aggregation": "cell_value",
        "filters": ["장기요양기관이름=신논현요양원"],
        "deterministic_value": "2019-03-15",
        "deterministic_value_cell": "I1052",
        "supporting_evidence_cells": ["I1052"],
    },
    "gq_auto_044": {
        "rewritten_question_ko": "2022년 5월에 지정된 인천은빛요양원의 기관별 상세주소는 무엇입니까?",
        "expected_answer_ko": "인천광역시 남동구 하촌로 26 7층701 702호 (만수동 거신빌딩)입니다.",
        "metric": "기관별 상세주소",
        "period": "2022-05-01",
        "aggregation": "cell_value",
        "filters": ["장기요양기관이름=인천은빛요양원"],
        "deterministic_value": "인천광역시 남동구 하촌로 26 7층701 702호 (만수동 거신빌딩)",
        "deterministic_value_cell": "J1102",
        "supporting_evidence_cells": ["J1102"],
    },
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_generation(
        input_jsonl=Path(args.input_jsonl),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
        backend=args.backend,
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
        max_tokens=args.max_tokens,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "generated_candidates": report["summary"]["generated_candidates"],
                "rejected_candidates": report["summary"]["rejected_candidates"],
                "official_metric_input_rows": report["official_metric_input_rows"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] != "FAILED_GUARDRAIL" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", default=str(DEFAULT_INPUT_JSONL))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--backend", default=DEFAULT_BACKEND, choices=["llamacpp", "openai-compatible", "ollama"])
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--max-tokens", type=int, default=900)
    return parser.parse_args(argv)


def run_generation(
    *,
    input_jsonl: Path,
    output_report: Path,
    output_md: Path,
    backend: str = DEFAULT_BACKEND,
    base_url: str = "",
    model: str = DEFAULT_MODEL,
    timeout_seconds: int = 120,
    max_tokens: int = 900,
    llm_client: Any | None = None,
    skip_probe: bool = False,
) -> dict[str, Any]:
    resolved = resolve_base_url(backend, base_url)
    rows = read_jsonl(input_jsonl)
    blockers: list[str] = []
    needs_llm = any(clean(row.get("query_id")) not in MANUAL_XLSX_CANDIDATES for row in rows)
    if needs_llm and not skip_probe:
        blockers = local_llm_entry_blockers(
            backend=backend,
            base_url=resolved,
            model=model,
            check_endpoint=True,
            timeout_seconds=min(timeout_seconds, 5),
        )
    if blockers:
        report = base_report(
            status="LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED",
            input_jsonl=input_jsonl,
            output_report=output_report,
            output_md=output_md,
            backend=backend,
            base_url=resolved,
            model=model,
            rows=rows,
        )
        report["blockers"] = blockers
        write_outputs(report, output_report, output_md)
        return report

    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in rows:
        constraints = deterministic_constraints(row)
        manual_payload = manual_candidate_payload(row)
        if manual_payload:
            constraints = apply_manual_constraints(constraints, manual_payload)
        reasons = eligibility_rejection_reasons(row, constraints)
        if reasons:
            rejected.append(rejected_row(row, reasons, constraints=constraints))
            continue
        if manual_payload:
            candidate = candidate_from_payload(row, manual_payload, constraints, manual_meta())
            post_reasons = candidate_rejection_reasons(candidate)
            if post_reasons:
                rejected.append(rejected_row(row, post_reasons, constraints=constraints, candidate=candidate))
            else:
                candidates.append(candidate)
            continue
        prompt = build_prompt(row, constraints)
        try:
            parsed, meta = call_local_llm_strict_json(
                backend=backend,
                base_url=resolved,
                model=model,
                prompt=prompt,
                temperature=0.0,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
                llm_client=llm_client,
            )
            candidate = candidate_from_payload(row, parsed, constraints, meta)
            post_reasons = candidate_rejection_reasons(candidate)
            if post_reasons:
                rejected.append(rejected_row(row, post_reasons, constraints=constraints, candidate=candidate))
            else:
                candidates.append(candidate)
        except Exception as exc:
            rejected.append(rejected_row(row, [f"LOCAL_LLM_OUTPUT_INVALID:{type(exc).__name__}: {exc}"], constraints=constraints))

    report = base_report(
        status="XLSX_LOCAL_LLM_CANDIDATE_GENERATION_COMPLETE",
        input_jsonl=input_jsonl,
        output_report=output_report,
        output_md=output_md,
        backend=backend,
        base_url=resolved,
        model=model,
        rows=rows,
    )
    report["candidates"] = candidates
    report["rejected_rows"] = rejected
    report["model_assisted_diagnostic_only"] = needs_llm
    report["summary"].update({"generated_candidates": len(candidates), "rejected_candidates": len(rejected)})
    report["summary"]["manual_query_candidates"] = sum(
        1 for candidate in candidates if candidate.get("local_llm_meta", {}).get("manual_curation") is True
    )
    write_outputs(report, output_report, output_md)
    return report


def base_report(
    *,
    status: str,
    input_jsonl: Path,
    output_report: Path,
    output_md: Path,
    backend: str,
    base_url: str,
    model: str,
    rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "rag_xlsx_gold_question_candidate_generation_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "xlsx_business_structured",
        "diagnostic_only": True,
        "model_assisted_diagnostic_only": True,
        "human_review_required": True,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "external_api_used": False,
        "local_llm": {"backend": backend, "base_url": base_url, "model": clean(model), "temperature": 0},
        "summary": {"input_rows": len(rows), "generated_candidates": 0, "rejected_candidates": 0},
        "candidates": [],
        "rejected_rows": [],
        "blockers": [],
        "source_artifacts": {"input_jsonl": repo_relative(input_jsonl)},
        "artifact_paths": {"report_json": repo_relative(output_report), "report_md": repo_relative(output_md)},
        "validation": {"ok": True, "errors": []},
    }


def deterministic_constraints(row: Mapping[str, Any]) -> dict[str, Any]:
    formatter = row.get("formatter_input") if isinstance(row.get("formatter_input"), Mapping) else {}
    row_values = [item for item in formatter.get("row_values") or [] if isinstance(item, Mapping)]
    metric = first_metric(row_values)
    period = first_period(row_values)
    filters = first_filters(row_values, metric, period)
    raw_locator = first_locator(row)
    deterministic_value_cell = clean(metric.get("cell")) or infer_value_cell(formatter, raw_locator, metric)
    source_cells = list_value(formatter.get("matched_cells")) or list_value(raw_locator.get("matched_cells"))
    evidence_cells = [deterministic_value_cell] if is_single_cell_ref(deterministic_value_cell) else source_cells
    locator = refined_locator(raw_locator, deterministic_value_cell)
    return {
        "workbook": clean(formatter.get("file") or locator.get("file")),
        "sheet": clean(formatter.get("sheet") or locator.get("sheet")),
        "table_range": clean(formatter.get("table_range") or locator.get("range")),
        "cells": evidence_cells,
        "source_cells": source_cells,
        "row_headers": list_value(formatter.get("target_rows")),
        "column_headers": list_value(formatter.get("column_headers")),
        "metric": clean(metric.get("column_label")),
        "period": clean(period.get("value")),
        "period_column": clean(period.get("column_label")),
        "aggregation": "cell_value" if metric else "",
        "filters": filters,
        "deterministic_value": clean(metric.get("value")),
        "deterministic_value_cell": deterministic_value_cell,
        "citation_locator": locator,
        "source_row_values": row_values[:12],
    }


def eligibility_rejection_reasons(row: Mapping[str, Any], constraints: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if row.get("hidden") is True or row.get("excluded") is True or row.get("pending") is True:
        reasons.append("XLSX_HIDDEN_EXCLUDED_OR_PENDING_ROW_BLOCKED")
    if clean(row.get("label_status")).lower() in {"pending", "excluded", "hidden"}:
        reasons.append("XLSX_HIDDEN_EXCLUDED_OR_PENDING_ROW_BLOCKED")
    if not clean(constraints.get("metric")):
        reasons.append("XLSX_MISSING_METRIC")
    if not clean(constraints.get("period")):
        reasons.append("XLSX_MISSING_PERIOD")
    if not clean(constraints.get("aggregation")) or not list_value(constraints.get("filters")):
        reasons.append("XLSX_MISSING_AGGREGATION_OR_FILTER")
    if not clean(constraints.get("deterministic_value")):
        reasons.append("XLSX_MISSING_DETERMINISTIC_VALUE")
    if not clean(constraints.get("sheet")) or not clean(constraints.get("table_range")) or not list_value(constraints.get("cells")):
        reasons.append("XLSX_CITATION_LOCATOR_INCOMPLETE")
    return sorted(set(reasons))


def candidate_rejection_reasons(candidate: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    question = clean(candidate.get("rewritten_question_ko"))
    answer = clean(candidate.get("expected_answer_ko"))
    deterministic_value = clean(candidate.get("deterministic_value"))
    quality = classify_question(question, query_id=clean(candidate.get("query_id")), track="xlsx_business_structured")
    if quality["primary_classification"] != "NATURAL_LANGUAGE_QUESTION":
        reasons.extend(quality["classifications"])
    if not answer:
        reasons.append("EMPTY_PROPOSED_ANSWER")
    if answer and answer == question:
        reasons.append("ANSWER_EQUALS_QUESTION")
    if deterministic_value and normalize_number(deterministic_value) not in normalize_number(answer):
        reasons.append("XLSX_NUMERIC_VALUE_CHANGED")
    for key in ("metric", "period", "aggregation"):
        if clean(candidate.get(key)) != clean(candidate.get(f"deterministic_{key}") or candidate.get(key)):
            reasons.append(f"XLSX_{key.upper()}_CHANGED")
    if clean(candidate.get("answerability_label_proposed")) != "ANSWERABLE":
        reasons.append("XLSX_NOT_ANSWERABLE")
    return sorted(set(reasons))


def candidate_from_payload(
    row: Mapping[str, Any],
    payload: Mapping[str, Any],
    constraints: Mapping[str, Any],
    meta: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "rag_xlsx_gold_question_candidate_generation_row_v1",
        "track": "xlsx_business_structured",
        "query_id": clean(row.get("query_id")),
        "original_question": clean(row.get("question") or row.get("query_id")),
        "rewritten_question_ko": clean(payload.get("rewritten_question_ko")),
        "expected_answer_ko": clean(payload.get("expected_answer_ko")),
        "supporting_evidence_cells": deterministic_supporting_evidence_cells(constraints, payload),
        "llm_supporting_evidence_cells": list_value(payload.get("supporting_evidence_cells")),
        "metric": clean(payload.get("metric") or constraints.get("metric")),
        "period": clean(payload.get("period") or constraints.get("period")),
        "aggregation": clean(payload.get("aggregation") or constraints.get("aggregation")),
        "filters": list_value(payload.get("filters")) or list_value(constraints.get("filters")),
        "deterministic_metric": clean(constraints.get("metric")),
        "deterministic_period": clean(constraints.get("period")),
        "deterministic_aggregation": clean(constraints.get("aggregation")),
        "deterministic_filters": list_value(constraints.get("filters")),
        "deterministic_value": clean(constraints.get("deterministic_value")),
        "deterministic_value_cell": clean(constraints.get("deterministic_value_cell")),
        "answerability_label_proposed": normalize_answerability(payload.get("answerability_label_proposed")),
        "relevance_label_proposed": normalize_relevance(payload.get("relevance_label_proposed")),
        "confidence": normalize_confidence(payload.get("confidence")),
        "reason": clean(payload.get("reason")),
        "workbook": clean(constraints.get("workbook")),
        "sheet": clean(constraints.get("sheet")),
        "table_range": clean(constraints.get("table_range")),
        "citation_locator": constraints.get("citation_locator") if isinstance(constraints.get("citation_locator"), Mapping) else {},
        "source_bound_table_metadata": dict(constraints),
        "human_review_required": True,
        "model_assisted_diagnostic_only": not bool(meta.get("manual_curation")),
        "official_metric_input": False,
        "promotion_evidence": False,
        "official_denominator_current": False,
        "local_llm_meta": dict(meta),
    }


def manual_candidate_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    query_id = clean(row.get("query_id"))
    spec = MANUAL_XLSX_CANDIDATES.get(query_id)
    if not spec:
        return {}
    payload = dict(spec)
    payload.setdefault("answerability_label_proposed", "ANSWERABLE")
    payload.setdefault("relevance_label_proposed", "RELEVANT")
    payload.setdefault("confidence", "HIGH")
    payload.setdefault("reason", "수동으로 작성한 XLSX gold 후보 질문입니다.")
    return payload


def apply_manual_constraints(
    constraints: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    patched = dict(constraints)
    for key in (
        "metric",
        "period",
        "aggregation",
        "filters",
        "deterministic_value",
        "deterministic_value_cell",
    ):
        if key in payload:
            patched[key] = payload[key]
    cells = list_value(payload.get("supporting_evidence_cells"))
    if cells:
        patched["cells"] = cells
        locator = dict(patched.get("citation_locator") if isinstance(patched.get("citation_locator"), Mapping) else {})
        locator["matched_cells"] = cells
        patched["citation_locator"] = locator
    return patched


def manual_meta() -> dict[str, Any]:
    return {"manual_curation": True, "strict_json": True}


def build_prompt(row: Mapping[str, Any], constraints: Mapping[str, Any]) -> str:
    payload = {
        "workbook": constraints.get("workbook"),
        "sheet": constraints.get("sheet"),
        "table_range": constraints.get("table_range"),
        "cells": constraints.get("cells"),
        "row_headers": constraints.get("row_headers"),
        "column_headers": constraints.get("column_headers"),
        "metric": constraints.get("metric"),
        "period": constraints.get("period"),
        "aggregation": constraints.get("aggregation"),
        "filters": constraints.get("filters"),
        "expected_deterministic_value": constraints.get("deterministic_value"),
        "citation_locator": constraints.get("citation_locator"),
        "source_row_values": constraints.get("source_row_values"),
    }
    return (
        "XLSX source-bound table evidence only. Do not calculate numeric answers; the deterministic code already "
        "computed/extracted expected_deterministic_value. Phrase a natural Korean question and answer around that "
        "exact value only. Return exactly one JSON object with keys: rewritten_question_ko, expected_answer_ko, "
        "supporting_evidence_cells, metric, period, aggregation, filters, answerability_label_proposed, "
        "relevance_label_proposed, confidence, reason.\n\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def first_metric(row_values: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    for item in row_values:
        label = clean(item.get("column_label"))
        value = clean(item.get("value"))
        if not value or not has_number(value):
            continue
        if any(block in label for block in FILTER_BLOCKLIST):
            continue
        if any(hint in label for hint in METRIC_HINTS):
            return item
    return {}


def first_period(row_values: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    for item in row_values:
        label = clean(item.get("column_label")).lower()
        value = clean(item.get("value"))
        if any(hint in label for hint in PERIOD_HINTS):
            return item
        if re.fullmatch(r"\d{6}|\d{4}[-./]\d{1,2}|\d{4}년\s*\d{1,2}월", value):
            return item
    return {}


def first_filters(
    row_values: list[Mapping[str, Any]],
    metric: Mapping[str, Any],
    period: Mapping[str, Any],
) -> list[str]:
    filters: list[str] = []
    metric_label = clean(metric.get("column_label"))
    period_label = clean(period.get("column_label"))
    for item in row_values:
        label = clean(item.get("column_label"))
        value = clean(item.get("value"))
        if not label or not value or label in {metric_label, period_label}:
            continue
        if any(block in label for block in FILTER_BLOCKLIST):
            continue
        filters.append(f"{label}={value}")
        break
    return filters


def first_locator(row: Mapping[str, Any]) -> dict[str, Any]:
    for item in list_value(row.get("citation_items")):
        if isinstance(item, Mapping):
            locator = item.get("locator") if isinstance(item.get("locator"), Mapping) else item.get("citation_locator")
            if isinstance(locator, Mapping):
                return dict(locator)
    locator = row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {}
    return dict(locator)


def first_cell(formatter: Mapping[str, Any], locator: Mapping[str, Any]) -> str:
    for value in list_value(formatter.get("matched_cells")) + list_value(locator.get("matched_cells")):
        return clean(value)
    return clean(locator.get("range") or formatter.get("table_range"))


def deterministic_supporting_evidence_cells(
    constraints: Mapping[str, Any],
    payload: Mapping[str, Any],
) -> list[str]:
    value_cell = clean(constraints.get("deterministic_value_cell"))
    if is_single_cell_ref(value_cell):
        return [value_cell]
    return list_value(payload.get("supporting_evidence_cells")) or list_value(constraints.get("cells"))


def refined_locator(locator: Mapping[str, Any], value_cell: str) -> dict[str, Any]:
    refined = dict(locator)
    if is_single_cell_ref(value_cell):
        refined["matched_cells"] = [value_cell]
    return refined


def infer_value_cell(formatter: Mapping[str, Any], locator: Mapping[str, Any], metric: Mapping[str, Any]) -> str:
    column = metric_column_letter(formatter, metric)
    row = first_target_row(formatter, locator)
    if column and row:
        return f"{column}{row}"
    for value in list_value(formatter.get("matched_cells")) + list_value(locator.get("matched_cells")):
        cell = clean(value)
        if is_single_cell_ref(cell):
            return cell
    return first_cell(formatter, locator)


def metric_column_letter(formatter: Mapping[str, Any], metric: Mapping[str, Any]) -> str:
    metric_label = clean(metric.get("column_label"))
    if not metric_label:
        return ""
    headers = [clean(header) for header in list_value(formatter.get("column_headers"))]
    target_columns = [clean(column).upper() for column in list_value(formatter.get("target_columns"))]
    try:
        index = headers.index(metric_label)
    except ValueError:
        return ""
    if index < len(target_columns) and target_columns[index]:
        return re.sub(r"[^A-Z]", "", target_columns[index].upper())
    return excel_column_name(index + 1)


def first_target_row(formatter: Mapping[str, Any], locator: Mapping[str, Any]) -> str:
    for source in (formatter, locator):
        for value in list_value(source.get("target_rows")):
            text = clean(value)
            if text.isdigit():
                return text
    range_text = clean(formatter.get("table_range") or locator.get("range"))
    match = re.match(r"^[A-Z]+(\d+)(?::[A-Z]+\d+)?$", range_text.upper())
    return match.group(1) if match else ""


def excel_column_name(index: int) -> str:
    name = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def is_single_cell_ref(value: Any) -> bool:
    return bool(re.fullmatch(r"[A-Z]{1,3}\d{1,7}", clean(value).upper()))


def rejected_row(
    row: Mapping[str, Any],
    reasons: list[str],
    *,
    constraints: Mapping[str, Any],
    candidate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "query_id": clean(row.get("query_id")),
        "track": "xlsx_business_structured",
        "rejection_reasons": sorted(set(reasons)),
        "constraints": dict(constraints),
        "candidate": dict(candidate or {}),
        "official_metric_input": False,
        "promotion_evidence": False,
    }


def write_outputs(report: Mapping[str, Any], output_report: Path, output_md: Path) -> None:
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    return "\n".join(
        [
            "# XLSX Gold Question Candidate Generation v1",
            "",
            f"- Status: `{report.get('status')}`",
            f"- Generated candidates: `{summary.get('generated_candidates')}`",
            f"- Rejected candidates: `{summary.get('rejected_candidates')}`",
            f"- Official metric input rows: `{report.get('official_metric_input_rows')}`",
            f"- Promotion evidence: `{str(report.get('promotion_evidence')).lower()}`",
        ]
    ) + "\n"


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def has_number(value: str) -> bool:
    return bool(re.search(r"\d", clean(value)))


def normalize_number(value: str) -> str:
    return re.sub(r"[^0-9.-]", "", clean(value))


def normalize_answerability(value: Any) -> str:
    text = clean(value).upper()
    if text in {
        "YES",
        "Y",
        "TRUE",
        "ANSWERABLE",
        "HIGH",
        "EXACT",
        "EXACTVALUE",
        "EXACT_MATCH",
        "EXACT_VALUE_EXTRACTION",
        "SUPPORTED",
    }:
        return "ANSWERABLE"
    if text in {"NO", "N", "FALSE", "NOT_ANSWERABLE"}:
        return "NOT_ANSWERABLE"
    return text or "UNCLEAR"


def normalize_relevance(value: Any) -> str:
    text = clean(value).upper()
    if text in {"YES", "Y", "TRUE", "RELEVANT", "HIGH", "EXACT", "EXACT_MATCH", "EXACT_VALUE_EXTRACTION"}:
        return "RELEVANT"
    if text in {"NO", "N", "FALSE", "IRRELEVANT"}:
        return "IRRELEVANT"
    return text or "UNCLEAR"


def normalize_confidence(value: Any) -> str:
    text = clean(value).upper()
    if text in {"HIGH", "MEDIUM", "LOW"}:
        return text
    return "LOW"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
