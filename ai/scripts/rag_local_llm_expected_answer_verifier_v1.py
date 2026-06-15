"""Verify diagnostic local-LLM PDF/XLSX question/expected-answer drafts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from rag_local_llm_expected_answer_generation_v1 import clean, read_json, repo_relative, utc_timestamp, write_json  # noqa: E402
from rag_question_quality_gate_v1 import classify_question  # noqa: E402


REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"
DEFAULT_PDF_CANDIDATES = REVIEW_DIR / "rag_pdf_gold_question_candidate_generation_v1.json"
DEFAULT_XLSX_CANDIDATES = REVIEW_DIR / "rag_xlsx_gold_question_candidate_generation_v1.json"
DEFAULT_OUTPUT_JSON = REVIEW_DIR / "rag_local_llm_expected_answer_verifier_v1.json"
DEFAULT_OUTPUT_MD = REVIEW_DIR / "rag_local_llm_expected_answer_verifier_v1.md"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_verifier(
        pdf_candidate_report=Path(args.pdf_candidate_report),
        xlsx_candidate_report=Path(args.xlsx_candidate_report),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "clean_candidates": report["bucket_counts"].get("clean_candidate_for_human_audit", 0),
                "official_metric_input_rows": report["summary"]["official_metric_input_rows"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["validation"]["ok"] else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-candidate-report", default=str(DEFAULT_PDF_CANDIDATES))
    parser.add_argument("--xlsx-candidate-report", default=str(DEFAULT_XLSX_CANDIDATES))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_verifier(
    *,
    pdf_candidate_report: Path,
    xlsx_candidate_report: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    source_reports = []
    if pdf_candidate_report.exists():
        source_reports.append(read_json(pdf_candidate_report))
    if xlsx_candidate_report.exists():
        source_reports.append(read_json(xlsx_candidate_report))
    candidates = [
        candidate
        for report in source_reports
        for candidate in report.get("candidates", [])
        if isinstance(candidate, Mapping)
    ]
    verified = verify_candidates(candidates)
    bucket_counts = Counter(row["bucket"] for row in verified)
    report = {
        "schema_version": "rag_local_llm_expected_answer_verifier_v1",
        "generated_at": utc_timestamp(),
        "status": "LOCAL_LLM_EXPECTED_ANSWER_VERIFIER_COMPLETE",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric_input_rows": 0,
        "verified_candidates": verified,
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "summary": {
            "input_candidates": len(candidates),
            "clean_candidates": bucket_counts.get("clean_candidate_for_human_audit", 0),
            "rejected_candidates": len(candidates) - bucket_counts.get("clean_candidate_for_human_audit", 0),
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "xlsx_dataset_diversity": xlsx_dataset_diversity(verified),
        },
        "source_artifacts": {
            "pdf_candidate_report": repo_relative(pdf_candidate_report),
            "xlsx_candidate_report": repo_relative(xlsx_candidate_report),
        },
        "artifact_paths": {"report_json": repo_relative(output_report), "report_md": repo_relative(output_md)},
        "validation": {"ok": True, "errors": []},
    }
    write_json(output_report, report)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")
    return report


def verify_candidates(candidates: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    verified = [verify_candidate(candidate) for candidate in candidates]
    seen_xlsx_keys: set[tuple[str, ...]] = set()
    for row in verified:
        if (
            clean(row.get("track")) == "xlsx_business_structured"
            and clean(row.get("bucket")) == "clean_candidate_for_human_audit"
        ):
            key = xlsx_duplicate_key(row)
            if key and key in seen_xlsx_keys:
                reasons = sorted(set(list_value(row.get("rejection_reasons")) + ["XLSX_DUPLICATE_CANDIDATE"]))
                row["rejection_reasons"] = reasons
                row["bucket"] = bucket_for(reasons)
                row["clean_candidate_for_human_audit"] = False
            elif key:
                seen_xlsx_keys.add(key)
    return verified


def verify_candidate(candidate: Mapping[str, Any], *, extra_reasons: list[str] | None = None) -> dict[str, Any]:
    track = clean(candidate.get("track"))
    reasons: list[str] = []
    question = clean(candidate.get("rewritten_question_ko"))
    answer = clean(candidate.get("expected_answer_ko"))
    query_id = clean(candidate.get("query_id"))
    quality = classify_question(question, query_id=query_id, track=track)
    if quality["primary_classification"] != "NATURAL_LANGUAGE_QUESTION":
        reasons.extend(quality["classifications"])
    if not answer:
        reasons.append("EMPTY_PROPOSED_ANSWER")
    if question == answer:
        reasons.append("ANSWER_EQUALS_QUESTION")
    if question == query_id:
        reasons.append("QUESTION_EQUALS_QUERY_ID")
    if candidate.get("official_metric_input") is not False:
        reasons.append("OFFICIAL_METRIC_INPUT_NOT_FALSE")
    if candidate.get("promotion_evidence") is not False:
        reasons.append("PROMOTION_EVIDENCE_NOT_FALSE")

    if track == "pdf_business_ocr_mm":
        reasons.extend(pdf_rejection_reasons(candidate))
    elif track == "xlsx_business_structured":
        reasons.extend(xlsx_rejection_reasons(candidate))
    else:
        reasons.append("UNKNOWN_TRACK")
    if extra_reasons:
        reasons.extend(extra_reasons)

    reasons = sorted(set(reasons))
    bucket = bucket_for(reasons)
    verified = dict(candidate)
    verified.update(
        {
            "bucket": bucket,
            "question_quality": quality["primary_classification"],
            "rejection_reasons": reasons,
            "clean_candidate_for_human_audit": bucket == "clean_candidate_for_human_audit",
            "human_review_required": True,
            "model_assisted_diagnostic_only": True,
            "official_metric_input": False,
            "promotion_evidence": False,
            "official_denominator_current": False,
        }
    )
    return verified


def pdf_rejection_reasons(candidate: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    evidence = clean(candidate.get("source_bound_evidence_text"))
    quote = clean(candidate.get("supporting_evidence_quote"))
    answer = clean(candidate.get("expected_answer_ko"))
    if clean(candidate.get("content_evidence_lane")) == "pdf_file_identity":
        reasons.append("PDF_FILE_IDENTITY_LANE_BLOCKED")
    if not quote or normalize(quote) not in normalize(evidence):
        reasons.append("PDF_SUPPORTING_EVIDENCE_QUOTE_NOT_IN_SOURCE")
    if answer and normalize(answer) not in normalize(evidence) and not pdf_table_answer_supported(candidate, answer):
        reasons.append("PDF_EXPECTED_ANSWER_UNSUPPORTED")
    locator = candidate.get("citation_locator") if isinstance(candidate.get("citation_locator"), Mapping) else {}
    if locator.get("page") is None:
        reasons.append("PDF_CITATION_LOCATOR_MISSING_PAGE")
    if not locator.get("bbox"):
        reasons.append("PDF_CITATION_LOCATOR_MISSING_BBOX")
    if not clean(locator.get("region_type") or candidate.get("region_type")):
        reasons.append("PDF_CITATION_LOCATOR_MISSING_REGION")
    if not clean(locator.get("search_unit_id") or candidate.get("search_unit_id")):
        reasons.append("PDF_CITATION_LOCATOR_MISSING_SEARCH_UNIT")
    return reasons


def pdf_table_answer_supported(candidate: Mapping[str, Any], answer: str) -> bool:
    values = pdf_table_values(candidate)
    if not values:
        return False
    normalized_answer = normalize(answer)
    for value in values:
        row_label = clean(value.get("period") or value.get("row_label_normalized") or value.get("row_label_raw"))
        column = clean(value.get("column") or value.get("column_path"))
        raw_value = clean(value.get("value") or value.get("value_raw"))
        if not raw_value:
            continue
        if normalize(raw_value) not in normalized_answer:
            continue
        if row_label and normalize(row_label) not in normalized_answer:
            continue
        column_terms = [term for term in re.split(r"[()/\s]+", column) if term]
        semantic_terms = [term for term in column_terms if not re.fullmatch(r"[A-Za-z$]+", term)]
        if semantic_terms and not any(normalize(term) in normalized_answer for term in semantic_terms):
            continue
        return True
    return False


def pdf_table_values(candidate: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = []
    for key in ("deterministic_table_values", "table_values"):
        for item in list_value(candidate.get(key)):
            if isinstance(item, Mapping):
                values.append(item)
    table_context = candidate.get("table_context") if isinstance(candidate.get("table_context"), Mapping) else {}
    for item in list_value(table_context.get("cell_values")):
        if isinstance(item, Mapping):
            values.append(item)
    for row in list_value(table_context.get("row_values")):
        if not isinstance(row, Mapping):
            continue
        period = clean(row.get("period"))
        for column, value in row.items():
            if column == "period":
                continue
            values.append({"period": period, "column": column, "value": value})
    return values


def xlsx_rejection_reasons(candidate: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    for key in ("metric", "period", "aggregation"):
        if not clean(candidate.get(key)):
            reasons.append(f"XLSX_MISSING_{key.upper()}")
    if not list_value(candidate.get("filters")):
        reasons.append("XLSX_MISSING_FILTERS")
    deterministic_value = clean(candidate.get("deterministic_value"))
    answer = clean(candidate.get("expected_answer_ko"))
    if deterministic_value and normalize_number(deterministic_value) not in normalize_number(answer):
        reasons.append("XLSX_NUMERIC_VALUE_CHANGED")
    locator = candidate.get("citation_locator") if isinstance(candidate.get("citation_locator"), Mapping) else {}
    if not clean(candidate.get("workbook") or locator.get("file") or locator.get("workbook")):
        reasons.append("XLSX_CITATION_LOCATOR_MISSING_WORKBOOK")
    if not clean(candidate.get("sheet") or locator.get("sheet")):
        reasons.append("XLSX_CITATION_LOCATOR_MISSING_SHEET")
    if not clean(candidate.get("table_range") or locator.get("range")):
        reasons.append("XLSX_CITATION_LOCATOR_MISSING_RANGE")
    if not list_value(candidate.get("supporting_evidence_cells")) and not list_value(locator.get("matched_cells")):
        reasons.append("XLSX_CITATION_LOCATOR_MISSING_CELLS")
    period = clean(candidate.get("deterministic_period") or candidate.get("period"))
    question = clean(candidate.get("rewritten_question_ko"))
    if period and question and not period_present_in_question(period, question):
        reasons.append("XLSX_QUESTION_MISSING_PERIOD")
    deterministic_value_cell = clean(candidate.get("deterministic_value_cell")).upper()
    supporting_cells = [clean(cell).upper() for cell in list_value(candidate.get("supporting_evidence_cells"))]
    locator_cells = [clean(cell).upper() for cell in list_value(locator.get("matched_cells"))]
    if not supporting_cells:
        supporting_cells = locator_cells
    if deterministic_value_cell and not is_single_cell_ref(deterministic_value_cell):
        reasons.append("XLSX_VALUE_CELL_NOT_PRECISE")
    if any(is_range_ref(cell) for cell in supporting_cells):
        reasons.append("XLSX_SUPPORTING_EVIDENCE_RANGE_TOO_WIDE")
    elif deterministic_value_cell and supporting_cells and deterministic_value_cell not in supporting_cells:
        reasons.append("XLSX_SUPPORTING_EVIDENCE_CELL_MISMATCH")
    if any(is_range_ref(cell) for cell in locator_cells):
        reasons.append("XLSX_LOCATOR_MATCHED_CELLS_RANGE_TOO_WIDE")
    elif deterministic_value_cell and locator_cells and deterministic_value_cell not in locator_cells:
        reasons.append("XLSX_LOCATOR_MATCHED_CELL_MISMATCH")
    return reasons


def xlsx_dataset_diversity(verified: list[Mapping[str, Any]]) -> dict[str, Any]:
    clean_xlsx = [
        row
        for row in verified
        if clean(row.get("track")) == "xlsx_business_structured"
        and clean(row.get("bucket")) == "clean_candidate_for_human_audit"
    ]
    workbook_counts = Counter(
        clean(row.get("workbook") or nested_locator(row).get("file") or nested_locator(row).get("workbook"))
        for row in clean_xlsx
    )
    workbook_counts.pop("", None)
    total = sum(workbook_counts.values())
    top_workbook, top_count = ("", 0)
    if workbook_counts:
        top_workbook, top_count = workbook_counts.most_common(1)[0]
    top_share = round(top_count / total, 4) if total else 0.0
    review_required = total >= 3 and top_share > 0.8
    return {
        "clean_xlsx_candidate_rows": total,
        "workbook_distribution": dict(sorted(workbook_counts.items())),
        "top_workbook": top_workbook,
        "top_workbook_share": top_share,
        "status": "REVIEW_REQUIRED" if review_required else "PASS",
        "reason": (
            "clean XLSX candidates are concentrated in one workbook; broaden workbook/domain sampling before official use"
            if review_required
            else ""
        ),
    }


def nested_locator(row: Mapping[str, Any]) -> Mapping[str, Any]:
    locator = row.get("citation_locator")
    return locator if isinstance(locator, Mapping) else {}


def xlsx_duplicate_key(candidate: Mapping[str, Any]) -> tuple[str, ...]:
    locator = candidate.get("citation_locator") if isinstance(candidate.get("citation_locator"), Mapping) else {}
    filters = [normalize(clean(item)) for item in list_value(candidate.get("deterministic_filters") or candidate.get("filters"))]
    values = [
        clean(candidate.get("workbook") or locator.get("file") or locator.get("workbook")),
        clean(candidate.get("sheet") or locator.get("sheet")),
        clean(candidate.get("deterministic_metric") or candidate.get("metric")),
        clean(candidate.get("deterministic_period") or candidate.get("period")),
        clean(candidate.get("deterministic_value")),
        clean(candidate.get("deterministic_value_cell")),
        *sorted(filters),
    ]
    normalized = tuple(normalize(value) for value in values if value)
    return normalized if len(normalized) >= 5 else ()


def period_present_in_question(period: str, question: str) -> bool:
    aliases = period_aliases(period)
    normalized_question = normalize(question)
    return any(normalize(alias) in normalized_question for alias in aliases if alias)


def period_aliases(period: str) -> set[str]:
    text = clean(period)
    aliases = {text}
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 6:
        year = digits[:4]
        month = int(digits[4:6])
        aliases.update(year_month_aliases(year, month))
    for match in re.finditer(r"(\d{4})\s*년\s*(\d{1,2})\s*월", text):
        aliases.update(year_month_aliases(match.group(1), int(match.group(2))))
    for match in re.finditer(r"(\d{4})[-./](\d{1,2})(?!\d)", text):
        aliases.update(year_month_aliases(match.group(1), int(match.group(2))))
    return aliases


def year_month_aliases(year: str, month: int) -> set[str]:
    return {
        f"{year}{month:02d}",
        f"{year}-{month}",
        f"{year}-{month:02d}",
        f"{year}.{month}",
        f"{year}.{month:02d}",
        f"{year}/{month}",
        f"{year}/{month:02d}",
        f"{year}년 {month}월",
        f"{year}년 {month:02d}월",
    }


def is_single_cell_ref(value: Any) -> bool:
    return bool(re.fullmatch(r"[A-Z]{1,3}\d{1,7}", clean(value).upper()))


def is_range_ref(value: Any) -> bool:
    text = clean(value).upper()
    return ":" in text or (bool(text) and not is_single_cell_ref(text))


def bucket_for(reasons: list[str]) -> str:
    if not reasons:
        return "clean_candidate_for_human_audit"
    if any("FILE_IDENTITY" in reason or "LANE" in reason for reason in reasons):
        return "lane_policy_blocked"
    if any(
        reason.startswith("XLSX_DUPLICATE")
        or reason.startswith("XLSX_QUESTION")
        or reason.startswith("XLSX_SUPPORTING_EVIDENCE")
        or reason.startswith("XLSX_LOCATOR_MATCHED")
        or reason.startswith("XLSX_VALUE_CELL")
        for reason in reasons
    ):
        return "exclude_from_official_gold_candidate"
    if any("MISSING" in reason and ("XLSX" in reason or "CONSTRAINT" in reason) for reason in reasons):
        return "missing_constraint"
    if any("UNSUPPORTED" in reason or "NUMERIC_VALUE_CHANGED" in reason for reason in reasons):
        return "expected_answer_unsupported"
    if any("QUESTION" in reason or "PLACEHOLDER" in reason or reason.startswith("PDF_") for reason in reasons):
        return "local_llm_output_invalid"
    return "exclude_from_official_gold_candidate"


def protected_path_diff_check(changed_paths: list[str]) -> dict[str, bool]:
    normalized = [path.replace("\\", "/") for path in changed_paths]
    return {
        "official_denominator_registry_changed": any(
            path == "ai/eval/eval_queries/official_denominator_registry.json" for path in normalized
        ),
        "candidate_artifact_changed": any("candidate" in path and "rag_human_audit_packet_v2" not in path for path in normalized),
        "gold_registry_changed": any("gold" in path and "gold_question_candidate_generation_v1" not in path for path in normalized),
        "production_vector_or_index_changed": any(
            ("production" in path or "vector" in path or "index" in path)
            and not path.startswith("ai/reports/rag_eval/")
            for path in normalized
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    diversity = summary.get("xlsx_dataset_diversity") if isinstance(summary.get("xlsx_dataset_diversity"), Mapping) else {}
    return "\n".join(
        [
            "# Local LLM Expected Answer Verifier v1",
            "",
            f"- Status: `{report.get('status')}`",
            f"- Input candidates: `{summary.get('input_candidates')}`",
            f"- Clean candidates: `{summary.get('clean_candidates')}`",
            f"- Rejected candidates: `{summary.get('rejected_candidates')}`",
            f"- XLSX dataset diversity: `{diversity.get('status', 'N/A')}`",
            f"- XLSX top workbook share: `{diversity.get('top_workbook_share', 0)}`",
            f"- Official metric input rows: `{summary.get('official_metric_input_rows')}`",
            f"- Promotion evidence: `{str(summary.get('promotion_evidence')).lower()}`",
        ]
    ) + "\n"


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", clean(value).lower())


def normalize_number(value: str) -> str:
    return re.sub(r"[^0-9.-]", "", clean(value))


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
