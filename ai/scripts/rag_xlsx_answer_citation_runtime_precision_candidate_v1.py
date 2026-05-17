"""Generate a report-only XLSX runtime answer/citation precision candidate.

This candidate models the generation path: it produces concise XLSX answers
and single-row citation locators from question text, citation text, and locator
metadata. Gold expected answers and supporting evidence are used only later for
scorer validation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"

DEFAULT_BASELINE_REPORT = REPORT_DIR / "official_answer_citation_metric_first_run_v1.json"
DEFAULT_SCORER_RESULTS = REPORT_DIR / "official_answer_citation_scorer_results_v1.jsonl"
DEFAULT_XLSX_GOLD = EVAL_QUERY_DIR / "gold_queries_xlsx_question_gold_v2.csv"
DEFAULT_OUTPUT_JSONL = REPORT_DIR / "xlsx_answer_citation_runtime_precision_candidate_results_v1.jsonl"
DEFAULT_STATUS_MD = REPORT_DIR / "rag_current_eval_status.md"

SCHEMA_VERSION = "xlsx_answer_citation_runtime_precision_candidate_v1"
PASS_CATEGORY = "PASS"
PROHIBITED_GENERATION_KEYS = {"expected_answer", "supporting_evidence"}
TARGET_COLUMN_ALIASES = {
    "승차총승객수": ("승차총승객수", "승객수"),
    "우편번호": ("우편번호",),
    "시도 시군구 법정동명": ("시도 시군구 법정동명", "법정동명"),
    "기관별 상세주소": ("기관별 상세주소", "상세주소"),
    "지정일자": ("지정일자",),
    "설치신고일자": ("설치신고일자",),
}
ENTITY_CONDITION_KEYS = ("노선명", "장기요양기관이름")
PDF_FAILURE_HINTS = {
    "gq_auto_010": {
        "likely_failure_type": "paragraph selected but numeric value missing",
        "candidate_repair_approach": "nearby table or paragraph numeric value selection with deterministic verification",
    },
    "gq_auto_030": {
        "likely_failure_type": "section/title-only answer",
        "candidate_repair_approach": "deterministic table row extraction or local LLM-assisted table row reading with deterministic verification",
    },
    "gq_pdf_section_question_001": {
        "likely_failure_type": "section/title-only answer",
        "candidate_repair_approach": "nearby table row value selection with deterministic verification",
    },
}


def _load_official_module():
    path = AI_WORKER_ROOT / "scripts" / "rag_official_answer_citation_metric_first_run_v1.py"
    spec = importlib.util.spec_from_file_location("official_answer_citation_metric_first_run_v1_for_runtime_candidate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load official scorer helpers from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


OFFICIAL = _load_official_module()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_candidate(
        baseline_report_path=Path(args.baseline_report),
        report_only_repair_candidate_path=Path(args.report_only_repair_candidate)
        if args.report_only_repair_candidate
        else None,
        scorer_results_path=Path(args.scorer_results_jsonl),
        xlsx_gold_csv_path=Path(args.xlsx_gold_csv),
        output_report=Path(args.output_report) if args.output_report else None,
        output_md=Path(args.output_md) if args.output_md else None,
        output_results_jsonl=Path(args.output_results_jsonl),
        runtime_environment_report_path=Path(args.runtime_environment_report)
        if args.runtime_environment_report
        else None,
        status_md=Path(args.status_md) if args.status_md else None,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "status_md": report["artifact_paths"]["status_md"],
                "results_jsonl": report["artifact_paths"]["results_jsonl"],
                "runtime_candidate_counts": report["runtime_candidate_failure_category_counts"],
                "promotion_evidence": report["guardrails"]["promotion_evidence"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-report", default=str(DEFAULT_BASELINE_REPORT))
    parser.add_argument("--report-only-repair-candidate", default="")
    parser.add_argument("--scorer-results-jsonl", default=str(DEFAULT_SCORER_RESULTS))
    parser.add_argument("--xlsx-gold-csv", default=str(DEFAULT_XLSX_GOLD))
    parser.add_argument("--runtime-environment-report", default="")
    parser.add_argument("--output-report", default="")
    parser.add_argument("--output-md", default="")
    parser.add_argument("--output-results-jsonl", default=str(DEFAULT_OUTPUT_JSONL))
    parser.add_argument("--status-md", default=str(DEFAULT_STATUS_MD))
    return parser.parse_args(argv)


def run_candidate(
    *,
    baseline_report_path: Path,
    report_only_repair_candidate_path: Path | None,
    scorer_results_path: Path,
    xlsx_gold_csv_path: Path,
    output_report: Path | None,
    output_md: Path | None,
    output_results_jsonl: Path,
    runtime_environment_report_path: Path | None,
    status_md: Path | None = None,
) -> dict[str, Any]:
    baseline = read_json(baseline_report_path)
    scorer_rows = read_jsonl(scorer_results_path)
    gold_rows = read_csv_by_query_id(xlsx_gold_csv_path)
    baseline_by_id = {row["query_id"]: row for row in baseline.get("row_results", [])}
    result_rows: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []

    for scorer_row in scorer_rows:
        baseline_row = baseline_by_id.get(clean(scorer_row.get("query_id")), {})
        if scorer_row.get("track") == "xlsx_business_structured":
            runtime_candidate = generate_xlsx_runtime_candidate(runtime_generation_input(scorer_row))
            traces.append(runtime_trace(scorer_row, runtime_candidate))
            result_rows.append(
                score_runtime_row(
                    scorer_row=scorer_row,
                    baseline_row=baseline_row,
                    gold_row=gold_rows.get(clean(scorer_row.get("query_id")), {}),
                    runtime_candidate=runtime_candidate,
                )
            )
        else:
            result_rows.append(carry_forward_row(scorer_row, baseline_row))

    baseline_counts = dict(sorted(Counter(row.get("failure_category") for row in baseline.get("row_results", [])).items()))
    repair_counts = read_json(report_only_repair_candidate_path).get("candidate_failure_category_counts", {}) if (
        report_only_repair_candidate_path and report_only_repair_candidate_path.exists()
    ) else {}
    runtime_counts = dict(sorted(Counter(row.get("failure_category") for row in result_rows).items()))
    remaining_by_track = defaultdict(list)
    for row in result_rows:
        if row.get("failure_category") != PASS_CATEGORY:
            remaining_by_track[clean(row.get("track"))].append(clean(row.get("query_id")))

    trace_basis_counts = dict(sorted(Counter(trace.get("row_selection_basis") for trace in traces).items()))
    runtime_failure_reason_counts = dict(
        sorted(Counter(clean(trace.get("failure_reason")) for trace in traces if clean(trace.get("failure_reason"))).items())
    )
    selected_segment_index_histogram = dict(
        sorted(
            Counter(segment_index_bucket(trace.get("selected_citation_segment_index")) for trace in traces).items()
        )
    )
    row_selection_condition_counts = dict(
        sorted(
            Counter(
                clean(condition)
                for trace in traces
                for condition in list_value(trace.get("row_selection_conditions"))
                if clean(condition)
            ).items()
        )
    )
    ambiguous_selection_query_ids = [
        clean(trace.get("query_id")) for trace in traces if trace.get("failure_reason") == "ambiguous_row_selection"
    ]
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": "REPORT_ONLY_XLSX_RUNTIME_PRECISION_CANDIDATE_COMPLETE",
        "report_only": True,
        "official_metric": False,
        "baseline_counts": baseline_counts,
        "report_only_repair_candidate_counts": repair_counts,
        "runtime_candidate_failure_category_counts": runtime_counts,
        "delta_baseline_to_report_only_repair_candidate": delta_counts(baseline_counts, repair_counts),
        "delta_report_only_repair_candidate_to_runtime_candidate": delta_counts(repair_counts, runtime_counts),
        "candidate_result_row_count": len(result_rows),
        "candidate_query_id_unique_count": len({row.get("query_id") for row in result_rows}),
        "xlsx_summary": {
            "baseline_xlsx_pass": "1/19",
            "runtime_candidate_pass_count": sum(
                1
                for row in result_rows
                if row.get("track") == "xlsx_business_structured" and row.get("failure_category") == PASS_CATEGORY
            ),
            "runtime_candidate_total": sum(1 for row in result_rows if row.get("track") == "xlsx_business_structured"),
            "remaining_xlsx_failures": [
                row.get("query_id")
                for row in result_rows
                if row.get("track") == "xlsx_business_structured" and row.get("failure_category") != PASS_CATEGORY
            ],
        },
        "all_track_carry_forward_observation": {
            "text_rows_carried_forward": sum(1 for row in result_rows if row.get("track") == "text_namu_v2_1"),
            "pdf_rows_carried_forward": sum(1 for row in result_rows if row.get("track") == "pdf_business_ocr_mm"),
            "xlsx_runtime_candidate_rows": sum(1 for row in result_rows if row.get("track") == "xlsx_business_structured"),
            "cross_track_average": None,
        },
        "remaining_failures_by_track": dict(sorted(remaining_by_track.items())),
        "runtime_generation_trace_counts": trace_basis_counts,
        "runtime_failure_reason_counts": runtime_failure_reason_counts,
        "selected_segment_index_histogram": selected_segment_index_histogram,
        "row_selection_condition_counts": row_selection_condition_counts,
        "ambiguous_selection_query_ids": ambiguous_selection_query_ids,
        "first_row_heuristic_applied_count": sum(
            1
            for trace in traces
            if clean(trace.get("row_selection_basis")) in {"first_row_from_citation_text", "first_target_row_fallback"}
        ),
        "xlsx_runtime_generation_traces": traces,
        "xlsx_before_after_rows": [
            before_after_row(row)
            for row in result_rows
            if row.get("candidate_scope") == "xlsx_runtime_precision_candidate"
        ],
        "pdf_remaining_failure_analysis": pdf_failure_analysis(result_rows),
        "source_artifacts": {
            "baseline_report": file_identity(baseline_report_path),
            "report_only_repair_candidate": file_identity(report_only_repair_candidate_path),
            "scorer_results_jsonl": file_identity(scorer_results_path),
            "xlsx_gold_csv_for_scoring_validation_only": file_identity(xlsx_gold_csv_path),
            "runtime_environment_report": file_identity(runtime_environment_report_path)
            if runtime_environment_report_path
            else {"path": None, "exists": False, "sha256": None},
        },
        "artifact_paths": {
            "report_json": repo_relative(output_report) if output_report else None,
            "report_md": repo_relative(output_md) if output_md else None,
            "results_jsonl": repo_relative(output_results_jsonl),
            "status_md": repo_relative(status_md) if status_md else None,
        },
        "local_llm_gpu_usage": {
            "used": False,
            "reason": "deterministic XLSX key-value generation path",
        },
        "guardrails": {
            "tuning_run_started": False,
            "promotion_evidence": False,
            "threshold_tuning": False,
            "winner_selection": False,
            "production_mutation": False,
            "denominator_mutation": False,
            "gold_mutation": False,
            "cross_track_averages_computed": False,
            "expected_answer_used_for_generation": False,
            "supporting_evidence_used_for_generation": False,
            "gold_fields_used_for_generation": False,
            "hidden_excluded_leakage_guardrail": "fail_closed",
        },
    }
    write_jsonl(output_results_jsonl, result_rows)
    if output_report is not None:
        write_json(output_report, report)
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown(report), encoding="utf-8")
    if status_md is not None:
        append_status_event(
            status_md,
            {
                "event_type": "xlsx_runtime_candidate",
                "generated_at": report["generated_at"],
                "status": report["status"],
                "counts": {
                    "PASS": runtime_counts.get("PASS", 0),
                    "PARTIAL_OR_UNSUPPORTED": runtime_counts.get("PARTIAL_OR_UNSUPPORTED", 0),
                    "rows": len(result_rows),
                    "unique_query_ids": len({row.get("query_id") for row in result_rows}),
                    "xlsx_pass": report["xlsx_summary"]["runtime_candidate_pass_count"],
                    "xlsx_total": report["xlsx_summary"]["runtime_candidate_total"],
                },
                "active_artifact_paths": {"results_jsonl": repo_relative(output_results_jsonl)},
                "sha256": {"results_jsonl": sha256_file(output_results_jsonl)},
                "guardrails": report["guardrails"],
                "current_profile_result": None,
            },
        )
    return report


def generate_xlsx_runtime_candidate(generation_input: Mapping[str, Any]) -> dict[str, Any]:
    base = {
        "schema_version": SCHEMA_VERSION,
        "query_id": clean(generation_input.get("query_id")),
        "generation_applied": False,
        "repair_confidence": "failed",
        "failure_reason": "",
        "gold_fields_used_for_generation": False,
        "expected_answer_seen_by_generation": False,
        "supporting_evidence_seen_by_generation": False,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "production_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
    }
    hidden_count = int_value(generation_input.get("hidden_excluded_leakage_count"))
    if hidden_count > 0:
        return {**base, "failure_reason": "hidden_excluded_leakage", "hidden_excluded_leakage_count": hidden_count}

    citation = as_mapping(generation_input.get("generated_citation"))
    locator = as_mapping(citation.get("locator"))
    citation_text = clean(citation.get("citation_text"))
    target = infer_target_column(clean(generation_input.get("question")))
    if not target:
        return {**base, "failure_reason": "target_column_ambiguous_or_missing", "hidden_excluded_leakage_count": hidden_count}
    segments = parse_citation_segments(citation_text)
    if not segments:
        return {**base, "failure_reason": "citation_text_missing", "hidden_excluded_leakage_count": hidden_count}
    selected = select_segment(segments, clean(generation_input.get("question")), target)
    if selected["index"] is None:
        return {**base, "failure_reason": selected["failure_reason"], "hidden_excluded_leakage_count": hidden_count}
    selected_segment = segments[int(selected["index"])]
    if target not in selected_segment["values"] or not clean(selected_segment["values"][target]):
        return {**base, "failure_reason": "target_column_missing_from_selected_row", "hidden_excluded_leakage_count": hidden_count}
    locator_result = single_row_locator(locator, int(selected["index"]))
    if not locator_result.get("range"):
        return {**base, "failure_reason": locator_result["failure_reason"], "hidden_excluded_leakage_count": hidden_count}

    repaired_locator = {
        **dict(locator),
        "original_range": clean(locator.get("range")),
        "range": locator_result["range"],
        "repaired_range": locator_result["range"],
        "row_selection_basis": selected["basis"],
        "target_columns": list_value(locator.get("target_columns")),
        "target_rows": list_value(locator.get("target_rows")),
        "matched_cells": list_value(locator.get("matched_cells")),
        "gold_fields_used_for_generation": False,
        "hidden_excluded_leakage_count": hidden_count,
    }
    return {
        **base,
        "generation_applied": True,
        "repair_confidence": "deterministic",
        "failure_reason": "",
        "generated_answer": answer_sentence(selected_segment["values"][target]),
        "generated_citation": {
            "citation_text": selected_segment["text"],
            "locator": repaired_locator,
        },
        "original_range": clean(locator.get("range")),
        "repaired_range": locator_result["range"],
        "selected_target_row": locator_result["row"],
        "selected_citation_segment_index": int(selected["index"]),
        "row_selection_basis": selected["basis"],
        "row_selection_conditions": selected["conditions"],
        "target_column": target,
        "target_column_selection_basis": "question_target_column_dictionary_normalized_match",
        "hidden_excluded_leakage_count": hidden_count,
    }


def runtime_generation_input(scorer_row: Mapping[str, Any]) -> dict[str, Any]:
    citation = first_generated_citation(scorer_row)
    return {
        "query_id": clean(scorer_row.get("query_id")),
        "question": clean(scorer_row.get("question")),
        "generated_answer": clean(scorer_row.get("generated_answer")),
        "generated_citation": {
            "citation_text": clean(citation.get("citation_text")),
            "locator": dict(as_mapping(citation.get("locator"))),
        },
        "hidden_excluded_leakage_count": int_value(
            as_mapping(scorer_row.get("score_details")).get("xlsx_hidden_excluded_surface_leakage_count")
        ),
    }


def infer_target_column(question: str) -> str:
    normalized_question = normalize_text(question)
    matches = [
        column
        for column, aliases in TARGET_COLUMN_ALIASES.items()
        if any(normalize_text(alias) in normalized_question for alias in aliases)
    ]
    return matches[0] if len(matches) == 1 else ""


def parse_citation_segments(citation_text: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for raw_segment in [part.strip() for part in clean(citation_text).split(";") if part.strip()]:
        values: dict[str, str] = {}
        for raw_pair in raw_segment.split("|"):
            if ":" not in raw_pair:
                continue
            key, value = raw_pair.split(":", 1)
            values[clean(key)] = clean(value)
        if values:
            segments.append({"text": raw_segment, "values": values})
    return segments


def select_segment(segments: list[dict[str, Any]], question: str, target_column: str) -> dict[str, Any]:
    question_norm = normalize_text(question)
    conditions = question_conditions(question, target_column)
    scored: list[tuple[int, int, list[str]]] = []
    for index, segment in enumerate(segments):
        values = as_mapping(segment.get("values"))
        matched: list[str] = []
        for key in ENTITY_CONDITION_KEYS:
            value = clean(values.get(key))
            if value and normalize_text(value) in question_norm:
                matched.append(f"{key}=question_value")
        ym = conditions.get("year_month_compact")
        date_prefix = conditions.get("year_month_dash")
        if ym and clean(values.get("년월")) == ym:
            matched.append("년월=question_year_month")
        if date_prefix:
            for date_key in ("지정일자", "설치신고일자"):
                value = clean(values.get(date_key))
                if value.startswith(date_prefix):
                    matched.append(f"{date_key}=question_year_month")
        scored.append((len(matched), index, matched))
    max_score = max((score for score, _index, _matched in scored), default=0)
    if max_score > 0:
        winners = [(index, matched) for score, index, matched in scored if score == max_score]
        if len(winners) == 1:
            return {
                "index": winners[0][0],
                "basis": "question_condition_match_citation_segment",
                "conditions": winners[0][1],
                "failure_reason": "",
            }
        return {"index": None, "basis": "", "conditions": [], "failure_reason": "ambiguous_row_selection"}
    if len(segments) == 1:
        return {
            "index": 0,
            "basis": "first_row_from_citation_text",
            "conditions": ["single_citation_segment"],
            "failure_reason": "",
        }
    return {"index": None, "basis": "", "conditions": [], "failure_reason": "ambiguous_row_selection"}


def question_conditions(question: str, _target_column: str) -> dict[str, str]:
    match = re.search(r"(\d{4})\s*년\s*(\d{1,2})\s*월", question)
    if not match:
        return {}
    year = match.group(1)
    month = int(match.group(2))
    return {
        "year_month_compact": f"{year}{month:02d}",
        "year_month_dash": f"{year}-{month:02d}",
    }


def single_row_locator(locator: Mapping[str, Any], segment_index: int) -> dict[str, Any]:
    required = ("sheet", "range", "search_unit_id", "document_version_id")
    if any(not clean(locator.get(field)) for field in required):
        return {"failure_reason": "locator_identity_incomplete"}
    target_rows = [int_value(row) for row in list_value(locator.get("target_rows")) if int_value(row)]
    target_columns = [clean(column).upper() for column in list_value(locator.get("target_columns")) if clean(column)]
    if not target_rows:
        return {"failure_reason": "target_rows_missing"}
    if not target_columns:
        return {"failure_reason": "target_columns_missing"}
    if segment_index >= len(target_rows):
        return {"failure_reason": "selected_segment_has_no_target_row"}
    row = target_rows[segment_index]
    return {"range": f"{target_columns[0]}{row}:{target_columns[-1]}{row}", "row": row}


def score_runtime_row(
    *,
    scorer_row: Mapping[str, Any],
    baseline_row: Mapping[str, Any],
    gold_row: Mapping[str, Any],
    runtime_candidate: Mapping[str, Any],
) -> dict[str, Any]:
    if runtime_candidate.get("generation_applied") is not True:
        row = carry_forward_row(scorer_row, baseline_row)
        row["candidate_scope"] = "xlsx_runtime_generation_failed"
        row["runtime_failure_reason"] = runtime_candidate.get("failure_reason")
        return row
    generated_answer = clean(runtime_candidate.get("generated_answer"))
    runtime_range = clean(runtime_candidate.get("repaired_range"))
    expected_answer = clean(gold_row.get("expected_answer"))
    support_cell = OFFICIAL.first_cell_ref(gold_row.get("supporting_evidence"))
    answer_score = 1.0 if OFFICIAL.expected_answer_supported_by_text(expected_answer, generated_answer) else 0.0
    citation_score = 1.0 if support_cell and single_row_range_contains_cell(runtime_range, support_cell) else 0.0
    if answer_score == 1.0 and citation_score == 1.0:
        failure_category = PASS_CATEGORY
    elif answer_score == 1.0:
        failure_category = "CITATION_UNSUPPORTED"
    else:
        failure_category = "PARTIAL_OR_UNSUPPORTED"
    original_citation = first_generated_citation(scorer_row)
    return {
        "schema_version": SCHEMA_VERSION,
        "query_id": scorer_row.get("query_id"),
        "track": scorer_row.get("track"),
        "candidate_scope": "xlsx_runtime_precision_candidate",
        "scoring_attempted": True,
        "answer_score": answer_score,
        "citation_support_score": citation_score,
        "failure_category": failure_category,
        "failure_detail": "" if failure_category == PASS_CATEGORY else "runtime candidate did not satisfy scoring reference",
        "baseline_failure_category": baseline_row.get("failure_category"),
        "baseline_answer_score": baseline_row.get("answer_score"),
        "baseline_citation_support_score": baseline_row.get("citation_support_score"),
        "original_generated_answer": scorer_row.get("generated_answer"),
        "runtime_candidate_generated_answer": generated_answer,
        "original_citation_range": clean(as_mapping(original_citation.get("locator")).get("range")),
        "runtime_candidate_citation_range": runtime_range,
        "original_citation": original_citation,
        "runtime_candidate_citation": runtime_candidate.get("generated_citation"),
        "generated_answer": generated_answer,
        "generated_citations": [runtime_candidate.get("generated_citation")],
        "row_selection_basis": runtime_candidate.get("row_selection_basis"),
        "row_selection_conditions": runtime_candidate.get("row_selection_conditions"),
        "selected_citation_segment_index": runtime_candidate.get("selected_citation_segment_index"),
        "target_column_selection_basis": runtime_candidate.get("target_column_selection_basis"),
        "gold_fields_used_for_generation": False,
        "expected_answer_used_for_generation": False,
        "supporting_evidence_used_for_generation": False,
        "gold_fields_used_for_scoring_validation": True,
        "hidden_excluded_leakage_count": runtime_candidate.get("hidden_excluded_leakage_count", 0),
        "repair_confidence": runtime_candidate.get("repair_confidence"),
        "promotion_evidence": False,
        "threshold_tuning": False,
        "production_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
    }


def carry_forward_row(scorer_row: Mapping[str, Any], baseline_row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "query_id": scorer_row.get("query_id"),
        "track": scorer_row.get("track"),
        "candidate_scope": "carry_forward",
        "scoring_attempted": scorer_row.get("scoring_attempted", True),
        "answer_score": scorer_row.get("answer_score"),
        "citation_support_score": scorer_row.get("citation_support_score"),
        "failure_category": scorer_row.get("failure_category"),
        "failure_detail": scorer_row.get("failure_detail", ""),
        "baseline_failure_category": baseline_row.get("failure_category", scorer_row.get("failure_category")),
        "gold_fields_used_for_generation": False,
        "expected_answer_used_for_generation": False,
        "supporting_evidence_used_for_generation": False,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "production_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "generated_answer": scorer_row.get("generated_answer"),
        "generated_citations": scorer_row.get("generated_citations"),
        "score_details": scorer_row.get("score_details"),
    }


def runtime_trace(scorer_row: Mapping[str, Any], runtime_candidate: Mapping[str, Any]) -> dict[str, Any]:
    original_citation = first_generated_citation(scorer_row)
    return {
        "query_id": clean(scorer_row.get("query_id")),
        "original_answer": clean(scorer_row.get("generated_answer")),
        "repaired_answer": clean(runtime_candidate.get("generated_answer")),
        "original_range": clean(as_mapping(original_citation.get("locator")).get("range")),
        "repaired_range": clean(runtime_candidate.get("repaired_range")),
        "row_selection_basis": clean(runtime_candidate.get("row_selection_basis")),
        "target_column_selection_basis": clean(runtime_candidate.get("target_column_selection_basis")),
        "selected_citation_segment_index": runtime_candidate.get("selected_citation_segment_index"),
        "row_selection_conditions": list_value(runtime_candidate.get("row_selection_conditions")),
        "failure_reason": clean(runtime_candidate.get("failure_reason")),
        "gold_fields_used_for_generation": False,
        "expected_answer_seen_by_generation": False,
        "supporting_evidence_seen_by_generation": False,
        "hidden_excluded_leakage_count": runtime_candidate.get("hidden_excluded_leakage_count", 0),
        "repair_confidence": clean(runtime_candidate.get("repair_confidence")),
    }


def before_after_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "query_id": clean(row.get("query_id")),
        "original_generated_answer": clean(row.get("original_generated_answer")),
        "runtime_candidate_generated_answer": clean(row.get("runtime_candidate_generated_answer")),
        "original_citation_range": clean(row.get("original_citation_range")),
        "runtime_candidate_citation_range": clean(row.get("runtime_candidate_citation_range")),
        "scorer_result_before": clean(row.get("baseline_failure_category")),
        "scorer_result_after": clean(row.get("failure_category")),
    }


def pdf_failure_analysis(result_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in result_rows:
        if row.get("track") != "pdf_business_ocr_mm" or row.get("failure_category") == PASS_CATEGORY:
            continue
        query_id = clean(row.get("query_id"))
        score_details = as_mapping(row.get("score_details"))
        citation = first_generated_citation(row)
        out.append(
            {
                "query_id": query_id,
                "question": clean(row.get("question") or score_details.get("question")),
                "current_generated_answer": clean(row.get("generated_answer")),
                "expected_answer_for_scorer_analysis_only": clean(score_details.get("expected_answer")),
                "current_citation_locator": as_mapping(citation.get("locator")),
                **PDF_FAILURE_HINTS.get(
                    query_id,
                    {
                        "likely_failure_type": "unknown_pdf_answer_citation_failure",
                        "candidate_repair_approach": "prepare deterministic PDF evidence inspection",
                    },
                ),
            }
        )
    return out


def delta_counts(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, int]:
    return {
        category: int(after.get(category, 0) or 0) - int(before.get(category, 0) or 0)
        for category in sorted(set(before) | set(after))
    }


def first_generated_citation(row: Mapping[str, Any]) -> Mapping[str, Any]:
    citations = row.get("generated_citations")
    if isinstance(citations, list) and citations and isinstance(citations[0], Mapping):
        return citations[0]
    citation = row.get("runtime_candidate_citation") or row.get("generated_citation")
    return citation if isinstance(citation, Mapping) else {}


def single_row_range_contains_cell(range_ref: str, cell_ref: str) -> bool:
    parsed = OFFICIAL.parse_range_ref(range_ref)
    if not parsed:
        return False
    _start_col, start_row, _end_col, end_row = parsed
    return start_row == end_row and OFFICIAL.cell_in_any_range(cell_ref, [range_ref])


def answer_sentence(value: str) -> str:
    value = clean(value).rstrip(".")
    if value.endswith("입니다"):
        return f"{value}."
    return f"{value}입니다."


def segment_index_bucket(value: Any) -> str:
    try:
        index = int(value)
    except (TypeError, ValueError):
        return "not_selected"
    if index <= 0:
        return "0"
    if index == 1:
        return "1"
    return "2+"


def normalize_text(value: str) -> str:
    return re.sub(r"[\s,._()/-]+", "", clean(value)).lower()


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# XLSX Answer/Citation Runtime Precision Candidate v1",
        "",
        f"- Status: `{report['status']}`",
        f"- Report-only: `{str(report['report_only']).lower()}`",
        f"- Baseline counts: `{json.dumps(report['baseline_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Report-only repair candidate counts: `{json.dumps(report['report_only_repair_candidate_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Runtime candidate counts: `{json.dumps(report['runtime_candidate_failure_category_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- XLSX runtime pass: `{report['xlsx_summary']['runtime_candidate_pass_count']}/{report['xlsx_summary']['runtime_candidate_total']}`",
        "- Local LLM/GPU used: `false`",
        "",
        "## XLSX Runtime Before/After",
        "",
        "| query_id | scorer before -> after | answer before -> after | range before -> after |",
        "|---|---|---|---|",
    ]
    for row in report.get("xlsx_before_after_rows", []):
        lines.append(
            "| {query_id} | {before} -> {after} | {before_answer} -> {after_answer} | {before_range} -> {after_range} |".format(
                query_id=clean(row.get("query_id")),
                before=clean(row.get("scorer_result_before")),
                after=clean(row.get("scorer_result_after")),
                before_answer=md_cell(row.get("original_generated_answer")),
                after_answer=md_cell(row.get("runtime_candidate_generated_answer")),
                before_range=clean(row.get("original_citation_range")),
                after_range=clean(row.get("runtime_candidate_citation_range")),
            )
        )
    lines.extend(
        [
            "",
            "## Remaining PDF Failure Analysis",
            "",
        ]
    )
    for row in report.get("pdf_remaining_failure_analysis", []):
        lines.append(
            "- `{query_id}`: {failure_type}; next candidate approach: {approach}.".format(
                query_id=row.get("query_id"),
                failure_type=row.get("likely_failure_type"),
                approach=row.get("candidate_repair_approach"),
            )
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- tuning_run_started=false",
            "- promotion_evidence=false",
            "- threshold_tuning=false",
            "- winner_selection=false",
            "- production_mutation=false",
            "- denominator_mutation=false",
            "- gold_mutation=false",
            "- expected_answer/supporting_evidence not used for generation",
            "",
        ]
    )
    return "\n".join(lines)


def md_cell(value: Any) -> str:
    return clean(value).replace("|", "\\|").replace("\n", " ")


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_csv_by_query_id(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["query_id"]: dict(row) for row in csv.DictReader(handle)}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def append_status_event(path: Path, event: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        if is_new:
            handle.write("# RAG Current Eval Status\n\n")
        handle.write(render_status_event_markdown(event))


def render_status_event_markdown(event: Mapping[str, Any]) -> str:
    counts = as_mapping(event.get("counts"))
    guardrails = as_mapping(event.get("guardrails"))
    paths = as_mapping(event.get("active_artifact_paths"))
    lines = [
        f"## {clean(event.get('event_type'))}",
        "",
        f"- Generated at: `{clean(event.get('generated_at'))}`",
        f"- Status: `{clean(event.get('status'))}`",
    ]
    if counts:
        lines.append(
            "- Counts: "
            + ", ".join(f"`{key}={value}`" for key, value in sorted(counts.items()))
        )
    if paths:
        lines.append(
            "- Active artifacts: "
            + ", ".join(f"`{value}`" for _, value in sorted(paths.items()))
        )
    if guardrails:
        lines.append(
            "- Guardrails: "
            + ", ".join(f"`{key}={str(value).lower()}`" for key, value in sorted(guardrails.items()))
        )
    lines.extend(["", ""])
    return "\n".join(lines)


def file_identity(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": None, "exists": False, "sha256": None}
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_value(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
