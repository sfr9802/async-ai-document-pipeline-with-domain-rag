"""Audit the reviewed XLSX-only gold v1 set without running promotion.

The audit is intentionally report-only. It records why
eval/gold_queries_xlsx_v1.csv is a useful positive subset but not a final
promotion-grade XLSX gold baseline.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_XLSX_V1 = Path("eval/eval_queries/gold_queries_xlsx_v1.csv")
DEFAULT_REVIEW_DECISIONS = Path("eval/reports/rag-ingestion/rag_xlsx_query_evidence_review_decisions.json")
DEFAULT_DIAGNOSTIC_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_xlsx_vector_diagnostic_report.json")
DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/rag_xlsx_gold_quality_audit.json")

GENERIC_QUERY_TERMS = {
    "구분",
    "기간",
    "날짜",
    "합계",
    "총계",
    "비고",
    "내용",
    "표",
    "데이터",
    "현황",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    xlsx_v1_path = Path(args.xlsx_v1)
    review_path = Path(args.review_decisions)
    diagnostic_path = Path(args.diagnostic_report)
    payload = build_audit(
        xlsx_v1_rows=read_csv_rows(xlsx_v1_path),
        review=read_json(review_path),
        diagnostic=read_json(diagnostic_path),
        xlsx_v1_path=xlsx_v1_path,
        review_path=review_path,
        diagnostic_path=diagnostic_path,
    )
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0


def build_audit(
    *,
    xlsx_v1_rows: list[dict[str, str]],
    review: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
    xlsx_v1_path: Path,
    review_path: Path,
    diagnostic_path: Path,
) -> dict[str, Any]:
    decisions = list(review.get("decisions") or [])
    positive_ids = {row.get("query_id", "") for row in xlsx_v1_rows}
    deferred_decisions = [row for row in decisions if not bool(row.get("promotion_eval_eligible"))]
    v1_bucket_counts = Counter(row.get("bucket") or "unknown" for row in xlsx_v1_rows)
    deferred_bucket_counts = Counter(row.get("bucket") or "unknown" for row in deferred_decisions)
    deferred_category_counts = Counter(row.get("category") or "unknown" for row in deferred_decisions)
    deferred_decision_counts = Counter(row.get("decision") or "unknown" for row in deferred_decisions)

    duplicate_groups, near_duplicate_pairs = duplicate_query_groups(xlsx_v1_rows)
    too_generic = too_generic_queries(xlsx_v1_rows)
    missing_range_policy_ids = [
        row.get("query_id", "")
        for row in xlsx_v1_rows
        if not normalized_policy(row.get("range_match_policy"))
    ]
    source_file_distribution = Counter(row.get("expected_file_name") or "unknown" for row in xlsx_v1_rows)
    overrepresented_files = overrepresented_file_rows(source_file_distribution, len(xlsx_v1_rows))

    hidden_negative_ids = [
        str(row.get("query_id") or "")
        for row in deferred_decisions
        if row.get("policy_label") == "negative_hidden_policy"
    ]
    formula_date_ids = [
        str(row.get("query_id") or "")
        for row in deferred_decisions
        if row.get("category") == "formula_date_contract"
    ]
    chunk_granularity_ids = [
        str(row.get("query_id") or "")
        for row in deferred_decisions
        if row.get("category") == "chunk_granularity"
    ]
    table_range_ids = [
        str(row.get("query_id") or "")
        for row in deferred_decisions
        if row.get("category") in {"table_range_strictness", "gold_binding"}
    ]
    excluded_bucket_coverage_gap = {
        "missing_from_positive_v1_count": len(deferred_decisions),
        "missing_from_positive_v1_query_ids": [str(row.get("query_id") or "") for row in deferred_decisions],
        "missing_from_positive_v1_bucket_distribution": dict(sorted(deferred_bucket_counts.items())),
        "buckets_absent_from_positive_v1": sorted(
            bucket for bucket in deferred_bucket_counts if bucket not in v1_bucket_counts
        ),
    }

    blockers: list[str] = []
    warnings: list[str] = []
    if deferred_decisions:
        blockers.append(f"{len(deferred_decisions)} reviewed XLSX rows are excluded or deferred from positive v1.")
    if hidden_negative_ids:
        blockers.append("Hidden-policy negative rows are absent from positive v1 and need a separate negative eval bucket.")
    if formula_date_ids:
        blockers.append("Formula/date rows still need an explicit raw/cached/display value contract.")
    if chunk_granularity_ids:
        blockers.append("Chunk granularity suspects are not represented as resolved positive evidence.")
    if table_range_ids:
        blockers.append("Table/range rows still need explicit v2 range policy or rebinding decisions.")
    if overrepresented_files:
        warnings.append("One or more source files exceed the audit overrepresentation threshold.")
    if duplicate_groups or near_duplicate_pairs:
        warnings.append("Duplicate or near-duplicate query surfaces should be reviewed before final gold promotion.")
    if too_generic:
        warnings.append("Some query surfaces are generic by heuristic and should be manually reviewed.")

    quality_status = "FAIL" if blockers else ("PASS_WITH_WARNINGS" if warnings else "PASS")

    diagnostic_metrics = diagnostic.get("metrics") or {}
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED",
        "report_role": "xlsx_gold_quality_audit",
        "promotion_evidence": False,
        "evidence_role": "gold_quality_design_audit",
        "source_xlsx_v1": str(xlsx_v1_path),
        "source_review_decisions": str(review_path),
        "source_diagnostic_report": str(diagnostic_path),
        "quality_status": quality_status,
        "row_count": len(xlsx_v1_rows),
        "bucket_distribution": dict(sorted(v1_bucket_counts.items())),
        "source_file_distribution": dict(sorted(source_file_distribution.items())),
        "sheet_distribution": dict(sorted(Counter(row.get("expected_sheet_name") or "unknown" for row in xlsx_v1_rows).items())),
        "duplicate_or_near_duplicate_query_count": len(duplicate_groups) + len(near_duplicate_pairs),
        "duplicate_query_groups": duplicate_groups,
        "near_duplicate_query_pairs": near_duplicate_pairs,
        "too_generic_query_count": len(too_generic),
        "too_generic_query_ids": [row["query_id"] for row in too_generic],
        "missing_expected_answer_text_count": count_missing(xlsx_v1_rows, "expected_answer_text"),
        "missing_expected_answer_text_query_ids": ids_missing(xlsx_v1_rows, "expected_answer_text"),
        "missing_must_contain_terms_count": count_missing(xlsx_v1_rows, "must_contain_terms"),
        "missing_must_contain_terms_query_ids": ids_missing(xlsx_v1_rows, "must_contain_terms"),
        "missing_range_match_policy_count": len(missing_range_policy_ids),
        "missing_range_match_policy_query_ids": missing_range_policy_ids,
        "overrepresented_file_count": len(overrepresented_files),
        "overrepresented_files": overrepresented_files,
        "excluded_bucket_coverage_gap": excluded_bucket_coverage_gap,
        "hidden_negative_missing_count": len(hidden_negative_ids),
        "hidden_negative_missing_query_ids": hidden_negative_ids,
        "formula_date_missing_count": len(formula_date_ids),
        "formula_date_missing_query_ids": formula_date_ids,
        "chunk_granularity_missing_count": len(chunk_granularity_ids),
        "chunk_granularity_missing_query_ids": chunk_granularity_ids,
        "table_range_policy_missing_count": len(table_range_ids),
        "table_range_policy_missing_query_ids": table_range_ids,
        "review_decision_counts": dict(sorted(Counter(row.get("decision") or "unknown" for row in decisions).items())),
        "deferred_decision_counts": dict(sorted(deferred_decision_counts.items())),
        "deferred_category_counts": dict(sorted(deferred_category_counts.items())),
        "source_diagnostic_metrics": {
            "Hit@10": diagnostic_metrics.get("Hit@10"),
            "MRR@10": diagnostic_metrics.get("MRR@10"),
            "xlsx_file_hit@10": diagnostic_metrics.get("xlsx_file_hit@10"),
            "xlsx_sheet_hit@10": diagnostic_metrics.get("xlsx_sheet_hit@10"),
            "xlsx_range_overlap@10": diagnostic_metrics.get("xlsx_range_overlap@10"),
            "xlsx_range_contains@10": diagnostic_metrics.get("xlsx_range_contains@10"),
            "xlsx_exact_range@10": diagnostic_metrics.get("xlsx_exact_range@10"),
            "xlsx_citation_location_accuracy": diagnostic_metrics.get("xlsx_citation_location_accuracy"),
            "hidden_content_leakage_count": diagnostic_metrics.get("hidden_content_leakage_count"),
        },
        "quality_limitations": [
            "gold_queries_xlsx_v1 is a reviewed positive subset, not a final XLSX baseline.",
            "The v1 set drops formula/date, hidden-negative, table/range, and chunk-granularity candidates from positive scoring.",
            "The source diagnostic remains promotion_evidence=false and evidence_role=diagnostic.",
            "This audit did not run promotion, reranking, hybrid retrieval, parser expansion, or threshold changes.",
        ],
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "eval/eval_queries/gold_queries_v0.csv is not modified.",
            "eval/eval_queries/gold_queries_xlsx_v1.csv is not modified.",
            "Existing baseline descriptors and artifact hashes are not read-write outputs of this audit.",
        ],
    }


def duplicate_query_groups(rows: list[Mapping[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_normalized: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        by_normalized[normalize_query(row.get("query", ""))].append(row)
    duplicate_groups = [
        {
            "normalized_query": key,
            "query_ids": [str(row.get("query_id") or "") for row in grouped],
            "queries": sorted({str(row.get("query") or "") for row in grouped}),
        }
        for key, grouped in sorted(by_normalized.items())
        if key and len(grouped) > 1
    ]

    near_duplicate_pairs: list[dict[str, Any]] = []
    for left_index, left in enumerate(rows):
        for right in rows[left_index + 1:]:
            left_query = normalize_query(left.get("query", ""))
            right_query = normalize_query(right.get("query", ""))
            if not left_query or not right_query or left_query == right_query:
                continue
            if len(left_query) < 4 or len(right_query) < 4:
                continue
            if left_query in right_query or right_query in left_query:
                near_duplicate_pairs.append(
                    {
                        "query_ids": [left.get("query_id", ""), right.get("query_id", "")],
                        "queries": [left.get("query", ""), right.get("query", "")],
                        "reason": "one_normalized_query_contains_the_other",
                    }
                )
    return duplicate_groups, near_duplicate_pairs


def too_generic_queries(rows: Iterable[Mapping[str, str]]) -> list[dict[str, str]]:
    generic_rows: list[dict[str, str]] = []
    for row in rows:
        query = str(row.get("query") or "").strip()
        normalized = normalize_query(query)
        if not normalized:
            generic_rows.append({"query_id": str(row.get("query_id") or ""), "query": query, "reason": "empty_query"})
        elif normalized in GENERIC_QUERY_TERMS:
            generic_rows.append({"query_id": str(row.get("query_id") or ""), "query": query, "reason": "generic_header_term"})
        elif len(normalized) <= 2:
            generic_rows.append({"query_id": str(row.get("query_id") or ""), "query": query, "reason": "very_short_query"})
    return generic_rows


def normalize_query(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.lower(), flags=re.UNICODE)


def normalized_policy(value: str | None) -> str:
    value = str(value or "").strip()
    return "" if value in {"", "none", "NONE"} else value


def overrepresented_file_rows(counts: Counter[str], total: int) -> list[dict[str, Any]]:
    if total <= 0:
        return []
    rows: list[dict[str, Any]] = []
    for file_name, count in sorted(counts.items()):
        ratio = count / total
        if ratio >= 0.50:
            rows.append({"expected_file_name": file_name, "row_count": count, "share": round(ratio, 4)})
    return rows


def count_missing(rows: Iterable[Mapping[str, str]], column: str) -> int:
    return len(ids_missing(rows, column))


def ids_missing(rows: Iterable[Mapping[str, str]], column: str) -> list[str]:
    return [str(row.get("query_id") or "") for row in rows if not str(row.get(column) or "").strip()]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON report must be an object: {path}")
    return payload


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_report(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx-v1", default=str(DEFAULT_XLSX_V1))
    parser.add_argument("--review-decisions", default=str(DEFAULT_REVIEW_DECISIONS))
    parser.add_argument("--diagnostic-report", default=str(DEFAULT_DIAGNOSTIC_REPORT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
