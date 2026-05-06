"""Compare XLSX v3 positive vector diagnostics with the prior v2 diagnostic."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_V3_RETRIEVAL_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_xlsx_v3_positive_vector_diagnostic_report.json")
DEFAULT_V2_RETRIEVAL_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_xlsx_vector_diagnostic_report.json")
DEFAULT_V3_GOLD = Path("eval/eval_queries/gold_queries_xlsx_v3_positive.csv")
DEFAULT_QUALITY_AUDIT = Path("eval/reports/rag-ingestion/rag_xlsx_natural_query_quality_audit.json")
DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/rag_xlsx_v3_vector_quality_breakdown.json")

METRIC_KEYS = [
    "Hit@10",
    "MRR@10",
    "xlsx_file_hit@10",
    "xlsx_sheet_hit@10",
    "xlsx_range_overlap@10",
    "xlsx_range_contains@10",
    "xlsx_exact_range@10",
    "xlsx_citation_location_accuracy",
    "hidden_content_leakage_count",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    v3_retrieval = read_json(Path(args.v3_retrieval_report))
    v2_retrieval = read_json(Path(args.v2_retrieval_report))
    v3_gold_rows = read_csv_rows(Path(args.v3_gold))
    quality_audit = read_optional_json(Path(args.quality_audit))
    payload = build_breakdown(
        v3_retrieval=v3_retrieval,
        v2_retrieval=v2_retrieval,
        v3_gold_rows=v3_gold_rows,
        quality_audit=quality_audit,
        v3_retrieval_path=Path(args.v3_retrieval_report),
        v2_retrieval_path=Path(args.v2_retrieval_report),
        v3_gold_path=Path(args.v3_gold),
        quality_audit_path=Path(args.quality_audit),
    )
    write_json(Path(args.output), payload)
    print_report(payload)
    return 0


def build_breakdown(
    *,
    v3_retrieval: Mapping[str, Any],
    v2_retrieval: Mapping[str, Any],
    v3_gold_rows: list[dict[str, str]],
    quality_audit: Mapping[str, Any],
    v3_retrieval_path: Path,
    v2_retrieval_path: Path,
    v3_gold_path: Path,
    quality_audit_path: Path,
) -> dict[str, Any]:
    positive_ids = [row.get("query_id", "") for row in v3_gold_rows]
    gold_by_id = {row.get("query_id", ""): row for row in v3_gold_rows}
    v2_rows_by_id = {row.get("query_id", ""): row for row in query_rows(v2_retrieval)}
    v3_rows_by_id = {row.get("query_id", ""): row for row in query_rows(v3_retrieval)}

    v2_positive_rows = [v2_rows_by_id[query_id] for query_id in positive_ids if query_id in v2_rows_by_id]
    v3_positive_rows = [v3_rows_by_id[query_id] for query_id in positive_ids if query_id in v3_rows_by_id]
    v2_positive_metrics = compute_metrics(v2_positive_rows)
    v3_positive_metrics = metrics_subset(v3_retrieval.get("metrics") or {})
    comparison = compare_metrics(v2_positive_metrics, v3_positive_metrics)

    query_comparison = [
        compare_query(
            query_id=query_id,
            gold=gold_by_id.get(query_id, {}),
            v2_row=v2_rows_by_id.get(query_id, {}),
            v3_row=v3_rows_by_id.get(query_id, {}),
        )
        for query_id in positive_ids
    ]
    anchor_missing_ids = set(quality_audit.get("anchor_term_missing_query_ids") or [])
    drift_or_anchor_suspect_rows = [
        row
        for row in query_comparison
        if row.get("query_id") in anchor_missing_ids
        or row.get("outcome_change") == "location_match_lost_after_naturalization"
        or row.get("v3_failure_reason")
    ]

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED",
        "report_role": "xlsx_v3_vector_quality_breakdown",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "source_v3_retrieval_report": str(v3_retrieval_path),
        "source_v2_retrieval_report": str(v2_retrieval_path),
        "source_v3_gold": str(v3_gold_path),
        "source_quality_audit": str(quality_audit_path),
        "retrieval_backend": v3_retrieval.get("retrieval_backend"),
        "backend_identity": v3_retrieval.get("backend_identity") or {},
        "top_k": v3_retrieval.get("top_k"),
        "query_count": len(v3_positive_rows),
        "v3_positive_metrics": v3_positive_metrics,
        "v2_report_all_xlsx_metrics": metrics_subset(v2_retrieval.get("metrics") or {}),
        "v2_positive_subset_metrics": v2_positive_metrics,
        "comparison_to_v2_positive_subset": comparison,
        "comparison_scope_note": (
            "The prior v2 report covered 50 XLSX rows, including deferred, excluded, and hidden-negative rows. "
            "This report recomputes a v2 positive-only subset for the same 35 query_ids used by v3_positive."
        ),
        "quality_audit_summary": {
            "quality_status": quality_audit.get("quality_status"),
            "anchor_term_missing_count": quality_audit.get("anchor_term_missing_count"),
            "hidden_value_in_positive_query_count": quality_audit.get("hidden_value_in_positive_query_count"),
            "formula_contract_violation_count": quality_audit.get("formula_contract_violation_count"),
            "date_format_contract_violation_count": quality_audit.get("date_format_contract_violation_count"),
            "expected_binding_changed_count": quality_audit.get("expected_binding_changed_count"),
        },
        "bucket_metrics": v3_retrieval.get("bucket_metrics") or {},
        "v3_failure_rows": [row for row in query_comparison if row.get("v3_failure_reason")],
        "query_drift_or_anchor_suspect_rows": drift_or_anchor_suspect_rows,
        "query_level_comparison": query_comparison,
        "notes": [
            "This is diagnostic-only vector evidence and does not set promotion_evidence=true.",
            "Metric movement after naturalization is treated as a more honest query-surface measurement, not as a promotion failure by itself.",
            "No hybrid search, reranking, parser expansion, or threshold changes are introduced by this report.",
        ],
    }


def compare_query(
    *,
    query_id: str,
    gold: Mapping[str, str],
    v2_row: Mapping[str, Any],
    v3_row: Mapping[str, Any],
) -> dict[str, Any]:
    v2_location = bool(v2_row.get("location_match"))
    v3_location = bool(v3_row.get("location_match"))
    if v2_location and not v3_location:
        outcome_change = "location_match_lost_after_naturalization"
    elif not v2_location and v3_location:
        outcome_change = "location_match_gained_after_naturalization"
    elif v2_location and v3_location:
        outcome_change = "location_match_preserved"
    else:
        outcome_change = "location_miss_preserved"

    v2_rank = to_int(v2_row.get("hit_rank"))
    v3_rank = to_int(v3_row.get("hit_rank"))
    return {
        "query_id": query_id,
        "bucket": gold.get("bucket") or v3_row.get("bucket") or v2_row.get("bucket"),
        "original_query": gold.get("original_query") or gold.get("query_seed") or v2_row.get("query"),
        "v3_query": gold.get("query") or v3_row.get("query"),
        "v2_hit_rank": v2_rank,
        "v3_hit_rank": v3_rank,
        "hit_rank_delta": None if v2_rank is None or v3_rank is None else v3_rank - v2_rank,
        "v2_location_match": v2_location,
        "v3_location_match": v3_location,
        "outcome_change": outcome_change,
        "v2_failure_reason": v2_row.get("failure_reason"),
        "v3_failure_reason": v3_row.get("failure_reason"),
        "expected_sheet_name": gold.get("expected_sheet_name") or v3_row.get("expected_sheet_name"),
        "expected_cell_range": gold.get("expected_cell_range") or v3_row.get("expected_cell_range"),
    }


def compute_metrics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    if count == 0:
        return {key: None for key in METRIC_KEYS}
    hit_at_10 = sum(1 for row in rows if bool(row.get("hit_at_10"))) / count
    reciprocal_ranks = []
    for row in rows:
        rank = to_int(row.get("hit_rank"))
        reciprocal_ranks.append(0.0 if rank is None or rank > 10 else 1.0 / rank)
    return {
        "Hit@10": round(hit_at_10, 4),
        "MRR@10": round(sum(reciprocal_ranks) / count, 4),
        "xlsx_file_hit@10": round(hit_ratio(rows, "file_match"), 4),
        "xlsx_sheet_hit@10": round(hit_ratio(rows, "xlsx_sheet_match"), 4),
        "xlsx_range_overlap@10": round(hit_ratio(rows, "xlsx_range_overlap"), 4),
        "xlsx_range_contains@10": round(hit_ratio(rows, "xlsx_range_contains"), 4),
        "xlsx_exact_range@10": round(hit_ratio(rows, "xlsx_range_exact"), 4),
        "xlsx_citation_location_accuracy": round(sum(1 for row in rows if row.get("location_match")) / count, 4),
        "hidden_content_leakage_count": sum(1 for row in rows if row.get("hidden_leakage")),
    }


def hit_ratio(rows: list[Mapping[str, Any]], breakdown_key: str) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if any_breakdown(row, breakdown_key)) / len(rows)


def any_breakdown(row: Mapping[str, Any], key: str) -> bool:
    return any(bool((hit.get("match_breakdown") or {}).get(key)) for hit in list(row.get("top_k_results") or []))


def compare_metrics(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    comparison: dict[str, Any] = {}
    for key in METRIC_KEYS:
        before_value = before.get(key)
        after_value = after.get(key)
        comparison[key] = {
            "v2_positive_subset": before_value,
            "v3_positive": after_value,
            "delta": None if before_value is None or after_value is None else round(float(after_value) - float(before_value), 4),
        }
    return comparison


def metrics_subset(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {key: metrics.get(key) for key in METRIC_KEYS}


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
    parser.add_argument("--v3-retrieval-report", default=str(DEFAULT_V3_RETRIEVAL_REPORT))
    parser.add_argument("--v2-retrieval-report", default=str(DEFAULT_V2_RETRIEVAL_REPORT))
    parser.add_argument("--v3-gold", default=str(DEFAULT_V3_GOLD))
    parser.add_argument("--quality-audit", default=str(DEFAULT_QUALITY_AUDIT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
