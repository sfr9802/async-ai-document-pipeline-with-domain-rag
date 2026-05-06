"""Compare v2 seed-query and v3 naturalized XLSX diagnostic metrics."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_V2_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_xlsx_vector_diagnostic_report.json")
DEFAULT_V3_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_xlsx_v3_positive_vector_diagnostic_report.json")
DEFAULT_V3_GOLD = Path("eval/eval_queries/gold_queries_xlsx_v3_positive.csv")
DEFAULT_QUALITY_AUDIT = Path("eval/reports/rag-ingestion/rag_xlsx_natural_query_quality_audit.json")
DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/rag_xlsx_v2_v3_metric_compare.json")

METRIC_KEYS = [
    "Hit@1",
    "Hit@3",
    "Hit@5",
    "Hit@10",
    "MRR@10",
    "xlsx_file_hit@10",
    "xlsx_sheet_hit@10",
    "xlsx_range_overlap@10",
    "xlsx_range_contains@10",
    "xlsx_exact_range@10",
    "xlsx_citation_location_accuracy",
    "result_empty_count",
    "hidden_content_leakage_count",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    v2_report = read_json(Path(args.v2_report))
    v3_report = read_json(Path(args.v3_report))
    v3_gold_rows = read_csv_rows(Path(args.v3_gold))
    quality_audit = read_optional_json(Path(args.quality_audit))
    payload = build_compare(
        v2_report=v2_report,
        v3_report=v3_report,
        v3_gold_rows=v3_gold_rows,
        quality_audit=quality_audit,
        args=args,
    )
    write_json(Path(args.output), payload)
    print_json(payload)
    return 0


def build_compare(
    *,
    v2_report: Mapping[str, Any],
    v3_report: Mapping[str, Any],
    v3_gold_rows: list[dict[str, str]],
    quality_audit: Mapping[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    positive_ids = [row.get("query_id", "") for row in v3_gold_rows]
    gold_by_id = {row.get("query_id", ""): row for row in v3_gold_rows}
    v2_by_id = {row.get("query_id", ""): row for row in query_rows(v2_report)}
    v3_by_id = {row.get("query_id", ""): row for row in query_rows(v3_report)}
    v2_positive_rows = [v2_by_id[query_id] for query_id in positive_ids if query_id in v2_by_id]
    v3_positive_rows = [v3_by_id[query_id] for query_id in positive_ids if query_id in v3_by_id]

    v2_metrics = compute_metrics(v2_positive_rows)
    v3_metrics = metrics_subset(v3_report.get("metrics") or {})
    query_comparison = [
        compare_query(
            query_id=query_id,
            gold=gold_by_id.get(query_id, {}),
            v2_row=v2_by_id.get(query_id, {}),
            v3_row=v3_by_id.get(query_id, {}),
        )
        for query_id in positive_ids
    ]
    degraded = [row["query_id"] for row in query_comparison if row["movement"] == "degraded"]
    improved = [row["query_id"] for row in query_comparison if row["movement"] == "improved"]
    unchanged = [row["query_id"] for row in query_comparison if row["movement"] == "unchanged"]
    anchor_missing_ids = set(quality_audit.get("anchor_term_missing_query_ids") or [])
    naturalization_drift_ids = [
        row["query_id"]
        for row in query_comparison
        if row["movement"] == "degraded" and row["v2_location_match"] and not row["v3_location_match"]
    ]

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED",
        "report_role": "xlsx_v2_v3_metric_compare",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "source_v2_report": args.v2_report,
        "source_v3_report": args.v3_report,
        "source_v3_gold": args.v3_gold,
        "source_quality_audit": args.quality_audit,
        "comparison_scope": {
            "v2_scope": "prior XLSX vector diagnostic restricted to v3 positive query_ids",
            "v3_scope": "eval/eval_queries/gold_queries_xlsx_v3_positive.csv",
            "positive_query_count": len(positive_ids),
            "v2_positive_rows_found": len(v2_positive_rows),
            "v3_positive_rows_found": len(v3_positive_rows),
            "hidden_negative_in_positive_metrics": False,
        },
        "v2_positive_subset_metrics": v2_metrics,
        "v3_positive_metrics": v3_metrics,
        "metric_deltas": compare_metrics(v2_metrics, v3_metrics),
        "degraded_query_ids": degraded,
        "improved_query_ids": improved,
        "unchanged_query_ids": unchanged,
        "naturalization_drift_suspect_count": len(naturalization_drift_ids),
        "naturalization_drift_suspect_query_ids": naturalization_drift_ids,
        "anchor_term_missing_suspect_count": len(anchor_missing_ids.intersection(positive_ids)),
        "anchor_term_missing_suspect_query_ids": sorted(anchor_missing_ids.intersection(positive_ids)),
        "query_level_comparison": query_comparison,
        "notes": [
            "This comparison is diagnostic-only and does not change baselines.",
            "The v2 source report includes non-positive XLSX rows, so v2 metrics are recomputed over the v3 positive IDs.",
        ],
    }


def compare_query(
    *,
    query_id: str,
    gold: Mapping[str, str],
    v2_row: Mapping[str, Any],
    v3_row: Mapping[str, Any],
) -> dict[str, Any]:
    v2_rank = to_int(v2_row.get("hit_rank"))
    v3_rank = to_int(v3_row.get("hit_rank"))
    v2_location = bool(v2_row.get("location_match"))
    v3_location = bool(v3_row.get("location_match"))
    v2_hit = v2_rank is not None and v2_rank <= 10
    v3_hit = v3_rank is not None and v3_rank <= 10
    movement = "unchanged"
    reasons: list[str] = []

    if v2_location and not v3_location:
        movement = "degraded"
        reasons.append("location_match_lost")
    elif not v2_location and v3_location:
        movement = "improved"
        reasons.append("location_match_gained")
    elif v2_hit and not v3_hit:
        movement = "degraded"
        reasons.append("hit_at_10_lost")
    elif not v2_hit and v3_hit:
        movement = "improved"
        reasons.append("hit_at_10_gained")
    elif v2_rank is not None and v3_rank is not None:
        if v3_rank > v2_rank:
            movement = "degraded"
            reasons.append("rank_worse")
        elif v3_rank < v2_rank:
            movement = "improved"
            reasons.append("rank_better")

    return {
        "query_id": query_id,
        "bucket": gold.get("bucket") or v2_row.get("bucket") or v3_row.get("bucket"),
        "v2_query": v2_row.get("query") or gold.get("original_query") or gold.get("query_seed"),
        "v3_query": v3_row.get("query") or gold.get("query"),
        "v2_hit_rank": v2_rank,
        "v3_hit_rank": v3_rank,
        "hit_rank_delta": None if v2_rank is None or v3_rank is None else v3_rank - v2_rank,
        "v2_location_match": v2_location,
        "v3_location_match": v3_location,
        "v2_failure_reason": v2_row.get("failure_reason"),
        "v3_failure_reason": v3_row.get("failure_reason"),
        "movement": movement,
        "movement_reasons": reasons,
        "expected_sheet_name": gold.get("expected_sheet_name") or v3_row.get("expected_sheet_name"),
        "expected_cell_range": gold.get("expected_cell_range") or v3_row.get("expected_cell_range"),
    }


def compute_metrics(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    count = len(rows)
    if count == 0:
        return {key: None for key in METRIC_KEYS}
    ranks = [to_int(row.get("hit_rank")) for row in rows]
    reciprocal_ranks = [0.0 if rank is None or rank > 10 else 1.0 / rank for rank in ranks]
    return {
        "Hit@1": round(sum(1 for rank in ranks if rank is not None and rank <= 1) / count, 4),
        "Hit@3": round(sum(1 for rank in ranks if rank is not None and rank <= 3) / count, 4),
        "Hit@5": round(sum(1 for rank in ranks if rank is not None and rank <= 5) / count, 4),
        "Hit@10": round(sum(1 for rank in ranks if rank is not None and rank <= 10) / count, 4),
        "MRR@10": round(sum(reciprocal_ranks) / count, 4),
        "xlsx_file_hit@10": round(hit_ratio(rows, "file_match") / count, 4),
        "xlsx_sheet_hit@10": round(hit_ratio(rows, "xlsx_sheet_match") / count, 4),
        "xlsx_range_overlap@10": round(hit_ratio(rows, "xlsx_range_overlap") / count, 4),
        "xlsx_range_contains@10": round(hit_ratio(rows, "xlsx_range_contains") / count, 4),
        "xlsx_exact_range@10": round(hit_ratio(rows, "xlsx_range_exact") / count, 4),
        "xlsx_citation_location_accuracy": round(sum(1 for row in rows if row.get("location_match")) / count, 4),
        "result_empty_count": sum(1 for row in rows if not row.get("top_k_results")),
        "hidden_content_leakage_count": sum(1 for row in rows if row.get("hidden_leakage")),
    }


def hit_ratio(rows: list[Mapping[str, Any]], breakdown_key: str) -> int:
    return sum(
        1
        for row in rows
        if any(bool((hit.get("match_breakdown") or {}).get(breakdown_key)) for hit in row.get("top_k_results") or [])
    )


def compare_metrics(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: {
            "v2_positive_subset": before.get(key),
            "v3_positive": after.get(key),
            "delta": metric_delta(before.get(key), after.get(key)),
        }
        for key in METRIC_KEYS
    }


def metric_delta(before: Any, after: Any) -> float | int | None:
    if before is None or after is None:
        return None
    if isinstance(before, int) and isinstance(after, int):
        return after - before
    try:
        return round(float(after) - float(before), 4)
    except (TypeError, ValueError):
        return None


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
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
