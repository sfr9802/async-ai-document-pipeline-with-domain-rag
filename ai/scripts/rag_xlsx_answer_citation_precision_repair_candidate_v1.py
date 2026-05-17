"""Generate a report-only XLSX answer/citation precision repair candidate.

The candidate consumes the scored official first-run baseline and writes a
separate observation artifact. It does not mutate official baseline artifacts,
gold CSVs, denominator registry, production namespaces, thresholds, or
promotion state.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
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
DEFAULT_OUTPUT_JSON = REPORT_DIR / "xlsx_answer_citation_precision_repair_candidate_v1.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "xlsx_answer_citation_precision_repair_candidate_v1.md"
DEFAULT_OUTPUT_JSONL = REPORT_DIR / "xlsx_answer_citation_precision_repair_candidate_results_v1.jsonl"

SCHEMA_VERSION = "xlsx_answer_citation_precision_repair_candidate_v1"
PASS_CATEGORY = "PASS"
TARGET_SUBTYPES = {
    "support_cell_inside_locator_range_but_locator_too_broad",
    "answer_target_column_missing",
}
PROHIBITED_GENERATION_KEYS = {"expected_answer", "supporting_evidence"}
TARGET_COLUMN_ALIASES = (
    ("시도 시군구 법정동명", ("시도 시군구 법정동명", "법정동명")),
    ("기관별 상세주소", ("기관별 상세주소", "상세주소", "주소")),
    ("설치신고일자", ("설치신고일자",)),
    ("지정일자", ("지정일자",)),
    ("승차총승객수", ("승차총승객수", "승객수")),
    ("우편번호", ("우편번호",)),
)


def _load_official_module():
    path = AI_WORKER_ROOT / "scripts" / "rag_official_answer_citation_metric_first_run_v1.py"
    spec = importlib.util.spec_from_file_location("official_answer_citation_metric_first_run_v1_for_candidate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load official metric helpers from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


OFFICIAL = _load_official_module()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_candidate(
        baseline_report_path=Path(args.baseline_report),
        scorer_results_path=Path(args.scorer_results_jsonl),
        xlsx_gold_csv_path=Path(args.xlsx_gold_csv),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
        output_results_jsonl=Path(args.output_results_jsonl),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "results_jsonl": report["artifact_paths"]["results_jsonl"],
                "xlsx_repair_attempted_count": report["xlsx_repair_attempted_count"],
                "xlsx_repair_applied_count": report["xlsx_repair_applied_count"],
                "promotion_evidence": report["promotion_evidence"],
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
    parser.add_argument("--scorer-results-jsonl", default=str(DEFAULT_SCORER_RESULTS))
    parser.add_argument("--xlsx-gold-csv", default=str(DEFAULT_XLSX_GOLD))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--output-results-jsonl", default=str(DEFAULT_OUTPUT_JSONL))
    return parser.parse_args(argv)


def run_candidate(
    *,
    baseline_report_path: Path,
    scorer_results_path: Path,
    xlsx_gold_csv_path: Path,
    output_report: Path,
    output_md: Path,
    output_results_jsonl: Path,
) -> dict[str, Any]:
    baseline = read_json(baseline_report_path)
    scorer_rows = read_jsonl(scorer_results_path)
    gold_rows = read_csv_by_query_id(xlsx_gold_csv_path)
    baseline_by_id = {row["query_id"]: row for row in baseline.get("row_results", [])}
    result_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    for scorer_row in scorer_rows:
        baseline_row = baseline_by_id.get(clean(scorer_row.get("query_id")), {})
        subtype = clean(baseline_row.get("diagnostic_xlsx_citation_failure_subtype"))
        if scorer_row.get("track") == "xlsx_business_structured" and subtype in TARGET_SUBTYPES:
            candidate = build_repair_candidate(candidate_generation_input(scorer_row, baseline_row))
            candidate_rows.append(candidate)
            result_rows.append(score_candidate_row(scorer_row, baseline_row, gold_rows.get(scorer_row["query_id"], {}), candidate))
        else:
            result_rows.append(carry_forward_row(scorer_row, baseline_row))

    baseline_counts = dict(sorted(Counter(row.get("failure_category") for row in baseline.get("row_results", [])).items()))
    candidate_counts = dict(sorted(Counter(row.get("failure_category") for row in result_rows).items()))
    baseline_subtypes = baseline.get("diagnostic_xlsx_citation_failure_subtype_counts") or {}
    candidate_subtypes = dict(
        sorted(
            Counter(
                row.get("diagnostic_xlsx_citation_failure_subtype")
                for row in result_rows
                if row.get("diagnostic_xlsx_citation_failure_subtype") and row.get("failure_category") != PASS_CATEGORY
            ).items()
        )
    )
    deltas = {
        category: candidate_counts.get(category, 0) - baseline_counts.get(category, 0)
        for category in sorted(set(baseline_counts) | set(candidate_counts))
    }
    applied = sum(1 for row in candidate_rows if row["repair_applied"] is True)
    failed = sum(1 for row in candidate_rows if row["repair_applied"] is not True)
    xlsx_candidate_result_rows = [
        xlsx_candidate_result_summary(row)
        for row in result_rows
        if row.get("candidate_scope") in {"xlsx_precision_repair_candidate", "xlsx_repair_failed"}
    ]

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": "REPORT_ONLY_XLSX_PRECISION_REPAIR_CANDIDATE_COMPLETE",
        "report_only": True,
        "official_metric": False,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "tuning_run_started": False,
        "production_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
        "cross_track_averages_computed": False,
        "winner_selection": False,
        "gold_fields_used_for_generation": False,
        "expected_answer_supporting_evidence_policy": "not_used_for_generation_repair; scorer_validation_only",
        "baseline_counts": {
            "official_scoring_attempt_count": baseline.get("official_scoring_attempt_count"),
            "scored_count": baseline.get("scored_count"),
            "skipped_count": baseline.get("skipped_count"),
            "error_count": baseline.get("error_count"),
        },
        "baseline_failure_category_counts": baseline_counts,
        "candidate_failure_category_counts": candidate_counts,
        "delta_failure_category_counts": deltas,
        "baseline_xlsx_diagnostic_subtype_counts": baseline_subtypes,
        "candidate_xlsx_diagnostic_subtype_counts": candidate_subtypes,
        "candidate_denominator_rows": len(result_rows),
        "candidate_result_row_count": len(result_rows),
        "xlsx_repair_attempted_count": len(candidate_rows),
        "xlsx_repair_applied_count": applied,
        "xlsx_repair_failed_count": failed,
        "xlsx_candidate_rows": candidate_rows,
        "xlsx_candidate_result_rows": xlsx_candidate_result_rows,
        "all_track_carry_forward_observation": {
            "pdf_text_rows_carried_forward": sum(
                1 for row in result_rows if row.get("track") in {"pdf_business_ocr_mm", "text_namu_v2_1"}
            ),
            "xlsx_pass_rows_carried_forward": sum(
                1
                for row in result_rows
                if row.get("track") == "xlsx_business_structured" and row.get("candidate_scope") == "carry_forward"
            ),
            "cross_track_average": None,
            "note": "report-only candidate observation, not optimization target",
        },
        "source_artifacts": {
            "baseline_report": file_identity(baseline_report_path),
            "scorer_results_jsonl": file_identity(scorer_results_path),
            "xlsx_gold_csv_for_scoring_reference_only": file_identity(xlsx_gold_csv_path),
        },
        "artifact_paths": {
            "report_json": repo_relative(output_report),
            "report_md": repo_relative(output_md),
            "results_jsonl": repo_relative(output_results_jsonl),
        },
        "guardrails": {
            "tuning_run_started": False,
            "promotion_evidence": False,
            "threshold_tuning": False,
            "production_mutation": False,
            "production_namespace_vector_index_mutation": False,
            "denominator_mutation": False,
            "gold_mutation": False,
            "expected_answer_supporting_evidence_not_used_for_generation_repair": True,
            "hidden_excluded_leakage_guardrail": "fail_closed",
        },
    }
    write_json(output_report, report)
    write_jsonl(output_results_jsonl, result_rows)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def build_repair_candidate(generation_input: Mapping[str, Any]) -> dict[str, Any]:
    query_id = clean(generation_input.get("query_id"))
    base = {
        "schema_version": SCHEMA_VERSION,
        "query_id": query_id,
        "failure_subtype": clean(generation_input.get("diagnostic_xlsx_citation_failure_subtype")),
        "repair_applied": False,
        "repair_confidence": "failed",
        "repair_failure_reason": "",
        "gold_fields_used_for_generation": False,
        "promotion_evidence": False,
        "threshold_tuning": False,
        "production_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
    }
    prohibited = sorted(key for key in PROHIBITED_GENERATION_KEYS if key in generation_input)
    if prohibited:
        return {**base, "repair_failure_reason": f"prohibited_gold_generation_fields:{','.join(prohibited)}"}

    hidden_count = int_value(generation_input.get("hidden_excluded_leakage_count"))
    if hidden_count > 0:
        return {
            **base,
            "repair_failure_reason": "hidden_excluded_leakage",
            "hidden_excluded_leakage_count": hidden_count,
        }

    citation = as_mapping(generation_input.get("generated_citation"))
    locator = as_mapping(citation.get("locator"))
    citation_text = clean(citation.get("citation_text"))
    question = clean(generation_input.get("question"))
    answer = extract_candidate_answer(question, citation_text)
    if not answer.get("candidate_answer"):
        return {
            **base,
            "repair_failure_reason": clean(answer.get("failure_reason")) or "target_column_ambiguous_or_missing",
            "hidden_excluded_leakage_count": hidden_count,
        }

    locator_repair = repair_locator_to_first_target_row(locator, citation_text, answer["target_column"])
    if not locator_repair.get("repaired_range"):
        return {
            **base,
            "repair_failure_reason": clean(locator_repair.get("failure_reason")) or "locator_repair_failed",
            "hidden_excluded_leakage_count": hidden_count,
        }

    return {
        **base,
        "repair_applied": True,
        "repair_confidence": "deterministic",
        "repair_failure_reason": "",
        "candidate_answer": answer["candidate_answer"],
        "target_column": answer["target_column"],
        "candidate_answer_basis": answer["basis"],
        "citation_first_segment": first_row_segment(citation_text),
        "original_answer": clean(generation_input.get("generated_answer")),
        "original_locator": dict(locator),
        "repaired_locator": {
            **dict(locator),
            "original_range": clean(locator.get("range")),
            "repaired_range": locator_repair["repaired_range"],
            "range": locator_repair["repaired_range"],
            "repair_basis": locator_repair["repair_basis"],
            "repair_confidence": "deterministic",
            "gold_fields_used_for_generation": False,
            "hidden_excluded_leakage_count": hidden_count,
        },
        "repaired_citation": {
            "citation_text": first_row_segment(citation_text),
            "locator": {
                **dict(locator),
                "original_range": clean(locator.get("range")),
                "range": locator_repair["repaired_range"],
                "repaired_range": locator_repair["repaired_range"],
                "repair_basis": locator_repair["repair_basis"],
                "repair_confidence": "deterministic",
            },
        },
        "hidden_excluded_leakage_count": hidden_count,
    }


def candidate_generation_input(scorer_row: Mapping[str, Any], baseline_row: Mapping[str, Any]) -> dict[str, Any]:
    citation = first_generated_citation(scorer_row)
    return {
        "query_id": clean(scorer_row.get("query_id")),
        "question": clean(scorer_row.get("question")),
        "diagnostic_xlsx_citation_failure_subtype": clean(baseline_row.get("diagnostic_xlsx_citation_failure_subtype")),
        "generated_answer": clean(scorer_row.get("generated_answer")),
        "generated_citation": {
            "citation_text": clean(citation.get("citation_text")),
            "locator": dict(as_mapping(citation.get("locator"))),
        },
        "hidden_excluded_leakage_count": int_value(
            as_mapping(scorer_row.get("score_details")).get("xlsx_hidden_excluded_surface_leakage_count")
        ),
    }


def extract_candidate_answer(question: str, citation_text: str) -> dict[str, str]:
    target = infer_target_column(question)
    if not target:
        return {"candidate_answer": "", "target_column": "", "failure_reason": "target_column_ambiguous_or_missing"}
    values = key_values_from_segment(first_row_segment(citation_text))
    if target not in values or not clean(values[target]):
        return {"candidate_answer": "", "target_column": target, "failure_reason": "target_column_missing_from_citation_text"}
    return {
        "candidate_answer": answer_sentence(values[target]),
        "target_column": target,
        "basis": "question_target_column_and_citation_text_key_value",
        "failure_reason": "",
    }


def infer_target_column(question: str) -> str:
    matches = [column for column, aliases in TARGET_COLUMN_ALIASES if any(alias in question for alias in aliases)]
    return matches[0] if len(matches) == 1 else ""


def key_values_from_segment(segment: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for part in segment.split("|"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        values[clean(key)] = clean(value)
    return values


def repair_locator_to_first_target_row(locator: Mapping[str, Any], citation_text: str, target_column: str) -> dict[str, str]:
    required = ("sheet", "range", "search_unit_id", "document_version_id")
    if any(not clean(locator.get(field)) for field in required):
        return {"failure_reason": "locator_identity_incomplete"}
    target_rows = [int_value(row) for row in list_value(locator.get("target_rows")) if int_value(row)]
    target_columns = [clean(column).upper() for column in list_value(locator.get("target_columns")) if clean(column)]
    if not target_rows:
        return {"failure_reason": "target_rows_missing"}
    if not target_columns:
        return {"failure_reason": "target_columns_missing"}
    first_segment = first_row_segment(citation_text)
    if target_column and target_column not in key_values_from_segment(first_segment):
        return {"failure_reason": "first_segment_target_column_missing"}
    first_row = target_rows[0]
    return {
        "repaired_range": f"{target_columns[0]}{first_row}:{target_columns[-1]}{first_row}",
        "repair_basis": "citation_text_first_segment_and_locator_target_rows_0",
    }


def score_candidate_row(
    scorer_row: Mapping[str, Any],
    baseline_row: Mapping[str, Any],
    gold_row: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    if candidate.get("repair_applied") is not True:
        row = carry_forward_row(scorer_row, baseline_row)
        row["candidate_scope"] = "xlsx_repair_failed"
        row["repair_failure_reason"] = candidate.get("repair_failure_reason")
        return row
    candidate_answer = clean(candidate.get("candidate_answer"))
    repaired_range = clean(as_mapping(candidate.get("repaired_locator")).get("repaired_range"))
    expected_answer = clean(gold_row.get("expected_answer"))
    support_cell = OFFICIAL.first_cell_ref(gold_row.get("supporting_evidence"))
    answer_score = 1.0 if OFFICIAL.expected_answer_supported_by_text(expected_answer, candidate_answer) else 0.0
    citation_score = 1.0 if support_cell and single_row_range_contains_cell(repaired_range, support_cell) else 0.0
    if answer_score == 1.0 and citation_score == 1.0:
        failure_category = PASS_CATEGORY
    elif answer_score == 1.0:
        failure_category = "CITATION_UNSUPPORTED"
    else:
        failure_category = "PARTIAL_OR_UNSUPPORTED"
    return {
        "schema_version": SCHEMA_VERSION,
        "query_id": scorer_row.get("query_id"),
        "track": scorer_row.get("track"),
        "candidate_scope": "xlsx_precision_repair_candidate",
        "scoring_attempted": True,
        "answer_score": answer_score,
        "citation_support_score": citation_score,
        "failure_category": failure_category,
        "failure_detail": "" if failure_category == PASS_CATEGORY else "candidate repair did not satisfy scoring reference",
        "baseline_failure_category": baseline_row.get("failure_category"),
        "baseline_answer_score": baseline_row.get("answer_score"),
        "baseline_citation_support_score": baseline_row.get("citation_support_score"),
        "original_answer": scorer_row.get("generated_answer"),
        "repaired_answer": candidate_answer,
        "original_citation": first_generated_citation(scorer_row),
        "repaired_citation": candidate.get("repaired_citation"),
        "diagnostic_xlsx_citation_failure_subtype": ""
        if failure_category == PASS_CATEGORY
        else baseline_row.get("diagnostic_xlsx_citation_failure_subtype"),
        "gold_fields_used_for_generation": False,
        "gold_fields_used_for_scoring_validation": True,
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
        "promotion_evidence": False,
        "threshold_tuning": False,
        "production_mutation": False,
        "denominator_mutation": False,
        "gold_mutation": False,
    }


def xlsx_candidate_result_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    original_citation = as_mapping(row.get("original_citation"))
    repaired_citation = as_mapping(row.get("repaired_citation"))
    original_locator = as_mapping(original_citation.get("locator"))
    repaired_locator = as_mapping(repaired_citation.get("locator"))
    return {
        "query_id": clean(row.get("query_id")),
        "original_failure_category": clean(row.get("baseline_failure_category")),
        "repaired_failure_category": clean(row.get("failure_category")),
        "original_answer": clean(row.get("original_answer")),
        "repaired_answer": clean(row.get("repaired_answer")),
        "original_citation_range": clean(original_locator.get("range")),
        "repaired_citation_range": clean(
            repaired_locator.get("repaired_range") or repaired_locator.get("range")
        ),
        "answer_score": row.get("answer_score"),
        "citation_support_score": row.get("citation_support_score"),
        "gold_fields_used_for_generation": False,
    }


def single_row_range_contains_cell(range_ref: str, cell_ref: str) -> bool:
    parsed = OFFICIAL.parse_range_ref(range_ref)
    if not parsed:
        return False
    _start_col, start_row, _end_col, end_row = parsed
    return start_row == end_row and OFFICIAL.cell_in_any_range(cell_ref, [range_ref])


def first_generated_citation(row: Mapping[str, Any]) -> Mapping[str, Any]:
    citations = row.get("generated_citations")
    if isinstance(citations, list) and citations and isinstance(citations[0], Mapping):
        return citations[0]
    return {}


def first_row_segment(citation_text: str) -> str:
    return clean(citation_text).split(";", 1)[0].strip()


def answer_sentence(value: str) -> str:
    value = clean(value).rstrip(".")
    if value.endswith("입니다"):
        return f"{value}."
    return f"{value}입니다."


def md_cell(value: str) -> str:
    return clean(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# XLSX Answer/Citation Precision Repair Candidate v1",
        "",
        f"- Status: `{report['status']}`",
        f"- Report-only: `{str(report['report_only']).lower()}`",
        f"- Candidate denominator rows: `{report['candidate_denominator_rows']}`",
        f"- XLSX repair attempted: `{report['xlsx_repair_attempted_count']}`",
        f"- XLSX repair applied: `{report['xlsx_repair_applied_count']}`",
        f"- XLSX repair failed: `{report['xlsx_repair_failed_count']}`",
        f"- Baseline counts: `{json.dumps(report['baseline_failure_category_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Candidate counts: `{json.dumps(report['candidate_failure_category_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Delta counts: `{json.dumps(report['delta_failure_category_counts'], ensure_ascii=False, sort_keys=True)}`",
        "- Observation: report-only candidate observation, not optimization target.",
        "",
        "## XLSX Before/After Rows",
        "",
        "| query_id | failure before -> after | answer before -> after | citation range before -> after |",
        "|---|---|---|---|",
    ]
    for row in report.get("xlsx_candidate_result_rows", []):
        lines.append(
            "| {query_id} | {before} -> {after} | {original_answer} -> {repaired_answer} | {original_range} -> {repaired_range} |".format(
                query_id=clean(row.get("query_id")),
                before=clean(row.get("original_failure_category")),
                after=clean(row.get("repaired_failure_category")),
                original_answer=md_cell(clean(row.get("original_answer"))),
                repaired_answer=md_cell(clean(row.get("repaired_answer"))),
                original_range=clean(row.get("original_citation_range")),
                repaired_range=clean(row.get("repaired_citation_range")),
            )
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- tuning_run_started: `false`",
            "- promotion_evidence: `false`",
            "- threshold_tuning: `false`",
            "- production_mutation: `false`",
            "- production_namespace_vector_index_mutation: `false`",
            "- denominator_mutation: `false`",
            "- gold_mutation: `false`",
            "- expected_answer/supporting_evidence not used for generation repair: `true`",
            "- gold_fields_used_for_generation=false for every repaired row",
            "",
        ]
    )
    return "\n".join(lines)


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


def file_identity(path: Path) -> dict[str, Any]:
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
