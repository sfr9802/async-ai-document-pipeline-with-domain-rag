"""Classify XLSX v3 naturalized positive retrieval failures and degradations."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_V2_REPORT = Path("reports/rag_eval/rag-ingestion/rag_retrieval_eval_xlsx_vector_diagnostic_report.json")
DEFAULT_V3_REPORT = Path("reports/rag_eval/rag-ingestion/rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json")
DEFAULT_V3_GOLD = Path("eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv")
DEFAULT_QUALITY_AUDIT = Path("reports/rag_eval/rag-ingestion/rag_xlsx_natural_query_quality_audit.json")
DEFAULT_FORMULA_DATE_REVIEW = Path("reports/rag_eval/rag-ingestion/rag_xlsx_formula_date_contract_review.json")
DEFAULT_CHUNK_REVIEW = Path("reports/rag_eval/rag-ingestion/rag_xlsx_chunk_granularity_review.json")
DEFAULT_OUTPUT = Path("reports/rag_eval/rag-ingestion/rag_xlsx_v3_after_cleanup_failure_breakdown.json")

CATEGORIES = {
    "MATCHED",
    "EMPTY_RESULT",
    "FILE_MISS",
    "SHEET_MISS",
    "RANGE_MISS",
    "RANGE_POLICY_MISMATCH",
    "CHUNK_GRANULARITY_ISSUE",
    "QUERY_NATURALIZATION_DRIFT",
    "ANCHOR_TERM_MISSING",
    "FORMULA_DATE_CONTRACT_MISMATCH",
    "TRUE_RETRIEVAL_RANKING_FAILURE",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    v2_report = read_json(Path(args.v2_report))
    v3_report = read_json(Path(args.v3_report))
    v3_gold_rows = read_csv_rows(Path(args.v3_gold))
    quality_audit = read_optional_json(Path(args.quality_audit))
    formula_review = read_optional_json(Path(args.formula_date_review))
    chunk_review = read_optional_json(Path(args.chunk_review))
    payload = build_breakdown(
        v2_report=v2_report,
        v3_report=v3_report,
        v3_gold_rows=v3_gold_rows,
        quality_audit=quality_audit,
        formula_review=formula_review,
        chunk_review=chunk_review,
        args=args,
    )
    write_json(Path(args.output), payload)
    print_json(payload)
    return 0


def build_breakdown(
    *,
    v2_report: Mapping[str, Any],
    v3_report: Mapping[str, Any],
    v3_gold_rows: list[dict[str, str]],
    quality_audit: Mapping[str, Any],
    formula_review: Mapping[str, Any],
    chunk_review: Mapping[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    v2_by_id = {row.get("query_id", ""): row for row in query_rows(v2_report)}
    v3_by_id = {row.get("query_id", ""): row for row in query_rows(v3_report)}
    anchor_missing_ids = set(quality_audit.get("anchor_term_missing_query_ids") or [])
    formula_contract_ids = {row.get("query_id", "") for row in formula_review.get("rows") or []}
    chunk_issue_ids = {
        row.get("query_id", "")
        for row in chunk_review.get("rows") or []
        if row.get("chunking_fix_needed") or row.get("primary_issue") == "chunking_granularity"
    }
    classified = [
        classify_query(
            gold=gold,
            v2_row=v2_by_id.get(gold.get("query_id", ""), {}),
            v3_row=v3_by_id.get(gold.get("query_id", ""), {}),
            anchor_missing_ids=anchor_missing_ids,
            formula_contract_ids=formula_contract_ids,
            chunk_issue_ids=chunk_issue_ids,
        )
        for gold in v3_gold_rows
    ]
    category_counts = Counter(row["category"] for row in classified)
    degraded_rows = [row for row in classified if row["degraded_after_naturalization"]]
    failed_rows = [row for row in classified if row["category"] != "MATCHED"]

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED",
        "report_role": "xlsx_v3_failure_breakdown",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "source_v2_report": args.v2_report,
        "source_v3_report": args.v3_report,
        "source_v3_gold": args.v3_gold,
        "source_quality_audit": args.quality_audit,
        "source_formula_date_review": args.formula_date_review,
        "source_chunk_review": args.chunk_review,
        "allowed_categories": sorted(CATEGORIES),
        "query_count": len(classified),
        "failed_or_degraded_count": len({row["query_id"] for row in failed_rows + degraded_rows}),
        "category_counts": dict(sorted(category_counts.items())),
        "degradation_axis_counts": degradation_axis_counts(classified),
        "failed_or_degraded_query_ids": sorted({row["query_id"] for row in failed_rows + degraded_rows}),
        "classified_query_rows": classified,
        "failed_or_degraded_rows": [row for row in classified if row["category"] != "MATCHED" or row["degraded_after_naturalization"]],
        "interpretation": {
            "naturalization_drift_query_ids": [
                row["query_id"] for row in classified if row["category"] == "QUERY_NATURALIZATION_DRIFT"
            ],
            "anchor_term_missing_query_ids": [
                row["query_id"] for row in classified if row["category"] == "ANCHOR_TERM_MISSING"
            ],
            "retrieval_or_ranking_query_ids": [
                row["query_id"] for row in classified if row["category"] == "TRUE_RETRIEVAL_RANKING_FAILURE"
            ],
            "range_policy_or_granularity_query_ids": [
                row["query_id"]
                for row in classified
                if row["category"] in {"RANGE_POLICY_MISMATCH", "CHUNK_GRANULARITY_ISSUE", "RANGE_MISS"}
            ],
        },
        "notes": [
            "Classification is diagnostic; it does not change thresholds, parser behavior, ranking, or baselines.",
            "Hidden-negative rows are absent from this positive failure breakdown.",
        ],
    }


def classify_query(
    *,
    gold: Mapping[str, str],
    v2_row: Mapping[str, Any],
    v3_row: Mapping[str, Any],
    anchor_missing_ids: set[str],
    formula_contract_ids: set[str],
    chunk_issue_ids: set[str],
) -> dict[str, Any]:
    query_id = gold.get("query_id", "")
    v2_location = bool(v2_row.get("location_match"))
    v3_location = bool(v3_row.get("location_match"))
    v2_rank = to_int(v2_row.get("hit_rank"))
    v3_rank = to_int(v3_row.get("hit_rank"))
    degraded_after_naturalization = v2_location and not v3_location
    failure_reason = v3_row.get("failure_reason")
    top_hits = list(v3_row.get("top_k_results") or [])
    relation = range_relation(top_hits)
    file_seen = any_breakdown(top_hits, "file_match")
    sheet_seen = any_breakdown(top_hits, "xlsx_sheet_match")
    category = "MATCHED"
    rationale = "v3 positive row matched expected location"

    if not top_hits:
        category = "EMPTY_RESULT"
        rationale = "vector retrieval returned no hits"
    elif v3_location and not degraded_after_naturalization:
        category = "MATCHED"
    elif query_id in anchor_missing_ids:
        category = "ANCHOR_TERM_MISSING"
        rationale = "naturalized query failed anchor-term audit"
    elif query_id in formula_contract_ids and failure_reason:
        category = "FORMULA_DATE_CONTRACT_MISMATCH"
        rationale = "formula/date contract review already marks this row as contract-sensitive"
    elif failure_reason == "expected_file_not_found":
        category = "FILE_MISS"
        rationale = "expected workbook is absent from top-k results"
    elif failure_reason == "expected_sheet_not_found":
        category = "SHEET_MISS"
        rationale = "expected workbook appears, but expected sheet is absent from top-k results"
    elif failure_reason == "expected_table_not_found":
        category = "RANGE_POLICY_MISMATCH"
        rationale = "expected sheet/range may appear, but table policy did not match"
    elif failure_reason == "expected_range_not_found":
        if degraded_after_naturalization and file_seen and sheet_seen and not relation["any_relation"]:
            category = "QUERY_NATURALIZATION_DRIFT"
            rationale = "v2 matched the location, while v3 naturalized wording kept file/sheet but shifted range retrieval"
        elif query_id in chunk_issue_ids:
            category = "CHUNK_GRANULARITY_ISSUE"
            rationale = "chunk review already marks this query as requiring chunk granularity review"
        elif relation["has_non_policy_relation"]:
            category = "RANGE_POLICY_MISMATCH"
            rationale = "a range relation exists in top-k, but the configured range policy did not match"
        elif file_seen and sheet_seen:
            category = "RANGE_MISS"
            rationale = "expected workbook and sheet appear, but expected range is absent from top-k"
        elif file_seen:
            category = "SHEET_MISS"
            rationale = "expected workbook appears, but expected sheet is absent from top-k results"
        else:
            category = "FILE_MISS"
            rationale = "expected workbook is absent from top-k results"
    elif degraded_after_naturalization:
        category = "QUERY_NATURALIZATION_DRIFT"
        rationale = "v2 matched but v3 did not, without another more specific failure category"
    elif failure_reason:
        category = "TRUE_RETRIEVAL_RANKING_FAILURE"
        rationale = "failure does not match a known gold policy, contract, or chunking category"
    elif v2_rank is not None and v3_rank is not None and v3_rank > v2_rank:
        category = "TRUE_RETRIEVAL_RANKING_FAILURE"
        rationale = "v3 still matched but ranked below the v2 seed query"

    return {
        "query_id": query_id,
        "bucket": gold.get("bucket") or v3_row.get("bucket") or v2_row.get("bucket"),
        "v2_query": v2_row.get("query") or gold.get("original_query") or gold.get("query_seed"),
        "v3_query": v3_row.get("query") or gold.get("query"),
        "expected_file_name": gold.get("expected_file_name") or v3_row.get("expected_file_name"),
        "expected_sheet_name": gold.get("expected_sheet_name") or v3_row.get("expected_sheet_name"),
        "expected_cell_range": gold.get("expected_cell_range") or v3_row.get("expected_cell_range"),
        "range_match_policy": gold.get("range_match_policy"),
        "v2_hit_rank": v2_rank,
        "v3_hit_rank": v3_rank,
        "v2_location_match": v2_location,
        "v3_location_match": v3_location,
        "degraded_after_naturalization": degraded_after_naturalization,
        "v3_failure_reason": failure_reason,
        "category": category,
        "rationale": rationale,
        "range_relation_in_top_k": relation,
        "top_k_summary": summarize_hits(top_hits),
    }


def degradation_axis_counts(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "query_drift": sum(1 for row in rows if row.get("category") == "QUERY_NATURALIZATION_DRIFT"),
        "anchor_term_missing": sum(1 for row in rows if row.get("category") == "ANCHOR_TERM_MISSING"),
        "retrieval_ranking": sum(1 for row in rows if row.get("category") == "TRUE_RETRIEVAL_RANKING_FAILURE"),
        "range_policy": sum(1 for row in rows if row.get("category") == "RANGE_POLICY_MISMATCH"),
        "chunk_granularity": sum(1 for row in rows if row.get("category") == "CHUNK_GRANULARITY_ISSUE"),
        "range_miss": sum(1 for row in rows if row.get("category") == "RANGE_MISS"),
        "formula_date_contract": sum(1 for row in rows if row.get("category") == "FORMULA_DATE_CONTRACT_MISMATCH"),
    }


def range_relation(hits: list[Mapping[str, Any]]) -> dict[str, bool]:
    has_exact = any_breakdown(hits, "xlsx_range_exact")
    has_contains = any_breakdown(hits, "xlsx_range_contains")
    has_overlap = any_breakdown(hits, "xlsx_range_overlap")
    has_policy = any_breakdown(hits, "xlsx_range_policy_match")
    return {
        "exact": has_exact,
        "contains": has_contains,
        "overlap": has_overlap,
        "policy_match": has_policy,
        "any_relation": has_exact or has_contains or has_overlap,
        "has_non_policy_relation": (has_exact or has_contains or has_overlap) and not has_policy,
    }


def any_breakdown(hits: list[Mapping[str, Any]], key: str) -> bool:
    return any(bool((hit.get("match_breakdown") or {}).get(key)) for hit in hits)


def summarize_hits(hits: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    summary = []
    for hit in hits[:5]:
        location = hit.get("location_json") if isinstance(hit.get("location_json"), Mapping) else {}
        breakdown = hit.get("match_breakdown") or {}
        summary.append(
            {
                "rank": hit.get("rank"),
                "source_file_name": hit.get("source_file_name"),
                "sheet_name": location.get("sheetName") or location.get("sheet_name"),
                "cell_range": location.get("cellRange") or location.get("cell_range"),
                "file_match": breakdown.get("file_match"),
                "sheet_match": breakdown.get("xlsx_sheet_match"),
                "range_policy_match": breakdown.get("xlsx_range_policy_match"),
                "range_exact": breakdown.get("xlsx_range_exact"),
                "range_contains": breakdown.get("xlsx_range_contains"),
                "range_overlap": breakdown.get("xlsx_range_overlap"),
            }
        )
    return summary


def query_rows(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = report.get("query_results") or report.get("per_query") or []
    return [row for row in rows if isinstance(row, Mapping)]


def to_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON report must be an object: {path}")
    return payload


def read_optional_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.exists() else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
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
    parser.add_argument("--v2-report", default=str(DEFAULT_V2_REPORT))
    parser.add_argument("--v3-report", default=str(DEFAULT_V3_REPORT))
    parser.add_argument("--v3-gold", default=str(DEFAULT_V3_GOLD))
    parser.add_argument("--quality-audit", default=str(DEFAULT_QUALITY_AUDIT))
    parser.add_argument("--formula-date-review", default=str(DEFAULT_FORMULA_DATE_REVIEW))
    parser.add_argument("--chunk-review", default=str(DEFAULT_CHUNK_REVIEW))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
