"""Create Track A A6 after-cleanup metric comparison report."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_BEFORE_REPORT = Path("reports/rag_retrieval_eval_xlsx_v3_positive_vector_diagnostic_report.json")
DEFAULT_AFTER_REPORT = Path("reports/rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json")
DEFAULT_BEFORE_GOLD = Path("eval/gold_queries_xlsx_v3_positive.csv")
DEFAULT_AFTER_GOLD = Path("eval/gold_queries_xlsx_v3_positive_reviewed.csv")
DEFAULT_HIDDEN_REPORT = Path("reports/rag_xlsx_v3_positive_reviewed_hidden_negative_leakage_diagnostic.json")
DEFAULT_CANDIDATE_DECISION = Path("reports/xlsx_candidate_v2_decision.json")
DEFAULT_OUTPUT = Path("reports/rag_xlsx_v3_after_cleanup_metric_compare.json")

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
    before = read_json(Path(args.before_report))
    after = read_json(Path(args.after_report))
    before_gold_rows = read_csv_rows(Path(args.before_gold))
    after_gold_rows = read_csv_rows(Path(args.after_gold))
    hidden = read_json(Path(args.hidden_report))
    candidate_decision = read_json(Path(args.candidate_decision))
    payload = build_compare(
        args=args,
        before=before,
        after=after,
        before_gold_rows=before_gold_rows,
        after_gold_rows=after_gold_rows,
        hidden=hidden,
        candidate_decision=candidate_decision,
    )
    write_json(Path(args.output), payload)
    print_json(
        {
            "status": payload["status"],
            "output": args.output,
            "xlsx_citation_location_accuracy_before": payload["metrics"]["before"]["xlsx_citation_location_accuracy"],
            "xlsx_citation_location_accuracy_after": payload["metrics"]["after"]["xlsx_citation_location_accuracy"],
            "hidden_content_leakage_count": payload["hidden_negative_metrics"]["hidden_content_leakage_count"],
        }
    )
    return 0 if payload["status"] == "COMPLETED" else 1


def build_compare(
    *,
    args: argparse.Namespace,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    before_gold_rows: list[dict[str, str]],
    after_gold_rows: list[dict[str, str]],
    hidden: Mapping[str, Any],
    candidate_decision: Mapping[str, Any],
) -> dict[str, Any]:
    before_metrics = before.get("metrics") or {}
    after_metrics = after.get("metrics") or {}
    hidden_metrics = hidden.get("metrics") or {}
    rows = []
    before_report_inventory = report_query_inventory(before)
    after_report_inventory = report_query_inventory(after)
    before_by_id = rows_by_query_id(before)
    after_by_id = rows_by_query_id(after)
    before_gold_inventory = query_id_inventory(before_gold_rows)
    after_gold_inventory = query_id_inventory(after_gold_rows)
    before_report_ids = set(before_report_inventory["ids"])
    after_report_ids = set(after_report_inventory["ids"])
    before_gold_ids = set(before_gold_inventory["ids"])
    after_gold_ids = set(after_gold_inventory["ids"])
    for query_id in sorted(set(before_by_id) | set(after_by_id)):
        before_row = before_by_id.get(query_id, {})
        after_row = after_by_id.get(query_id, {})
        if before_row.get("query") == after_row.get("query") and before_row.get("location_match") == after_row.get("location_match"):
            continue
        rows.append(
            {
                "query_id": query_id,
                "before_query": before_row.get("query"),
                "after_query": after_row.get("query"),
                "before_location_match": before_row.get("location_match"),
                "after_location_match": after_row.get("location_match"),
                "before_failure_reason": before_row.get("failure_reason"),
                "after_failure_reason": after_row.get("failure_reason"),
                "before_hit_rank": before_row.get("hit_rank"),
                "after_hit_rank": after_row.get("hit_rank"),
                "before_location_rank": before_row.get("location_rank"),
                "after_location_rank": after_row.get("location_rank"),
            }
        )
    location_rank_metrics = {
        "before": location_metrics(before),
        "after": location_metrics(after),
        "delta": location_metric_delta(location_metrics(before), location_metrics(after)),
    }
    completion_criteria = {
        "before_positive_diagnostic_completed": before.get("status") == "COMPLETED",
        "positive_diagnostic_completed": after.get("status") == "COMPLETED",
        "reviewed_gold_validation_pass": bool((after.get("validation") or {}).get("ok")),
        "hidden_negative_diagnostic_completed": hidden.get("status") == "COMPLETED",
        "hidden_content_leakage_count_is_0": hidden_metrics.get("hidden_content_leakage_count") == 0,
        "promotion_evidence_is_false": after.get("promotion_evidence") is False
        and hidden.get("promotion_evidence") is False
        and candidate_decision.get("promotion_evidence") is False,
        "evidence_role_is_diagnostic": after.get("evidence_role") == "diagnostic"
        and hidden.get("evidence_role") == "diagnostic"
        and candidate_decision.get("evidence_role") == "diagnostic",
        "candidate_decision_completed": candidate_decision.get("status") == "COMPLETED",
        "candidate_decision_is_skip": candidate_decision.get("decision") == "SKIP",
        "candidate_v1_not_mutated": candidate_decision.get("candidate_v1_mutated") is False,
        "before_after_gold_query_ids_match": before_gold_ids == after_gold_ids,
        "before_gold_has_no_duplicate_query_ids": not before_gold_inventory["duplicate_ids"],
        "after_gold_has_no_duplicate_query_ids": not after_gold_inventory["duplicate_ids"],
        "before_report_query_ids_match_gold": before_report_ids == before_gold_ids,
        "after_report_query_ids_match_gold": after_report_ids == after_gold_ids,
        "before_report_has_no_duplicate_query_ids": not before_report_inventory["duplicate_ids"],
        "after_report_has_no_duplicate_query_ids": not after_report_inventory["duplicate_ids"],
        "before_report_has_no_blank_query_ids": not before_report_inventory["blank_row_indexes"],
        "after_report_has_no_blank_query_ids": not after_report_inventory["blank_row_indexes"],
        "before_report_row_count_matches_gold": before_report_inventory["row_count"] == before_gold_inventory["row_count"],
        "after_report_row_count_matches_gold": after_report_inventory["row_count"] == after_gold_inventory["row_count"],
        "metrics_are_finite": finite_metric_values(before_metrics, after_metrics),
    }
    blockers = blockers_for_completion(completion_criteria)
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED" if not blockers else "NEEDS_REVIEW",
        "report_role": "xlsx_v3_after_cleanup_metric_compare",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "source_before_report": args.before_report,
        "source_after_report": args.after_report,
        "source_before_gold": args.before_gold,
        "source_after_gold": args.after_gold,
        "source_hidden_report": args.hidden_report,
        "source_candidate_decision": args.candidate_decision,
        "candidate_v2_decision": candidate_decision.get("decision"),
        "candidate_v1_mutated": False,
        "metrics": {
            "before": metric_subset(before_metrics),
            "after": metric_subset(after_metrics),
            "delta": metric_delta(before_metrics, after_metrics),
        },
        "location_rank_metrics": location_rank_metrics,
        "hidden_negative_metrics": {
            "hidden_content_leakage_count": hidden_metrics.get("hidden_content_leakage_count"),
            "hidden_negative_pass_count": hidden_metrics.get("hidden_negative_pass_count"),
            "positive_metric_mix_allowed": False,
        },
        "gold_query_id_contract": {
            "before_gold": before_gold_inventory,
            "after_gold": after_gold_inventory,
            "before_missing_report_query_ids": sorted(before_gold_ids - before_report_ids),
            "before_extra_report_query_ids": sorted(before_report_ids - before_gold_ids),
            "after_missing_report_query_ids": sorted(after_gold_ids - after_report_ids),
            "after_extra_report_query_ids": sorted(after_report_ids - after_gold_ids),
            "before_report": before_report_inventory,
            "after_report": after_report_inventory,
        },
        "changed_or_recovered_rows": rows,
        "completion_criteria": completion_criteria,
        "blockers": blockers,
        "location_quality_observations": location_quality_observations(location_rank_metrics["after"]),
        "guardrails": {
            "promotion_evidence_true_set": False,
            "candidate_v1_mutated": False,
            "immutable_baseline_changed": False,
            "rag_data_canary_changed": False,
            "hidden_negative_in_positive_metrics": False,
        },
    }


def rows_by_query_id(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row.get("query_id") or ""): row
        for row in report.get("query_results") or report.get("per_query") or []
        if isinstance(row, Mapping)
    }


def report_query_inventory(report: Mapping[str, Any]) -> dict[str, Any]:
    rows = [
        row
        for row in report.get("query_results") or report.get("per_query") or []
        if isinstance(row, Mapping)
    ]
    ids = []
    blank_row_indexes = []
    counts: dict[str, int] = {}
    for index, row in enumerate(rows):
        query_id = str(row.get("query_id") or "")
        if not query_id:
            blank_row_indexes.append(index)
            continue
        ids.append(query_id)
        counts[query_id] = counts.get(query_id, 0) + 1
    return {
        "row_count": len(rows),
        "ids": sorted(ids),
        "duplicate_ids": sorted(query_id for query_id, count in counts.items() if count > 1),
        "blank_row_indexes": blank_row_indexes,
    }


def query_id_inventory(rows: list[dict[str, str]]) -> dict[str, Any]:
    ids = [str(row.get("query_id") or "") for row in rows if row.get("query_id")]
    counts: dict[str, int] = {}
    for query_id in ids:
        counts[query_id] = counts.get(query_id, 0) + 1
    return {
        "row_count": len(rows),
        "ids": sorted(ids),
        "duplicate_ids": sorted(query_id for query_id, count in counts.items() if count > 1),
    }


def location_metrics(report: Mapping[str, Any]) -> dict[str, Any]:
    rows = [
        row
        for row in report.get("query_results") or report.get("per_query") or []
        if isinstance(row, Mapping)
    ]
    total = len(rows)
    location_ranks = [safe_int(row.get("location_rank")) for row in rows]
    location_hit_rates = {}
    for cutoff in (1, 3, 5, 10):
        location_hit_rates[f"location_hit@{cutoff}"] = ratio(
            sum(1 for rank in location_ranks if rank is not None and rank <= cutoff),
            total,
        )
    location_mrr = ratio(
        sum((1.0 / rank) for rank in location_ranks if rank is not None and rank <= 10),
        total,
    )
    identity_without_top_location = [
        str(row.get("query_id") or "")
        for row in rows
        if row.get("hit_rank") is not None and row.get("location_rank") is not None and row.get("hit_rank") != row.get("location_rank")
    ]
    top5_location_miss_ids = [
        str(row.get("query_id") or "")
        for row, rank in zip(rows, location_ranks)
        if rank is None or rank > 5
    ]
    sheet_summary_only_ids = []
    wrong_docv_duplicate_ids = []
    wrong_docv_duplicate_hit_count = 0
    for row in rows:
        location_hit = hit_at_rank(row, safe_int(row.get("location_rank")))
        if is_sheet_summary_relation(location_hit):
            sheet_summary_only_ids.append(str(row.get("query_id") or ""))
        wrong_docv_hits = [
            hit for hit in row.get("top_k_results") or [] if is_wrong_docv_duplicate_hit(hit)
        ]
        if wrong_docv_hits:
            wrong_docv_duplicate_ids.append(str(row.get("query_id") or ""))
            wrong_docv_duplicate_hit_count += len(wrong_docv_hits)
    return {
        "query_count": total,
        **location_hit_rates,
        "location_mrr@10": round(location_mrr, 4),
        "top1_location_match_rate": location_hit_rates["location_hit@1"],
        "identity_hit_without_top_location_count": len(identity_without_top_location),
        "identity_hit_without_top_location_query_ids": identity_without_top_location,
        "location_top5_miss_count": len(top5_location_miss_ids),
        "location_top5_miss_query_ids": top5_location_miss_ids,
        "sheet_summary_only_relation_count": len(sheet_summary_only_ids),
        "sheet_summary_only_relation_query_ids": sheet_summary_only_ids,
        "wrong_docv_duplicate_hit_count": wrong_docv_duplicate_hit_count,
        "wrong_docv_duplicate_query_ids": sorted(set(wrong_docv_duplicate_ids)),
    }


def location_metric_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    delta = {}
    for key, after_value in after.items():
        before_value = before.get(key)
        if is_number(before_value) and is_number(after_value):
            delta[key] = round(float(after_value) - float(before_value), 4)
    return delta


def location_quality_observations(metrics: Mapping[str, Any]) -> list[str]:
    observations = []
    if metrics.get("location_top5_miss_count"):
        observations.append("Some positive rows only recover the exact location after rank 5; keep this diagnostic-only.")
    if metrics.get("identity_hit_without_top_location_count"):
        observations.append("Identity hits and exact location hits are not always at the same rank.")
    if metrics.get("wrong_docv_duplicate_hit_count"):
        observations.append("Wrong-document-version duplicates appear in top-k and can suppress exact location rank.")
    return observations


def hit_at_rank(row: Mapping[str, Any], rank: int | None) -> Mapping[str, Any]:
    if rank is None:
        return {}
    for hit in row.get("top_k_results") or []:
        if safe_int(hit.get("rank")) == rank:
            return hit
    return {}


def is_sheet_summary_relation(hit: Mapping[str, Any]) -> bool:
    breakdown = hit.get("match_breakdown") or {}
    return (
        hit.get("chunk_type") == "sheet_summary"
        and breakdown.get("xlsx_range_exact") is not True
        and (breakdown.get("xlsx_range_contains") is True or breakdown.get("xlsx_range_overlap") is True)
    )


def is_wrong_docv_duplicate_hit(hit: Mapping[str, Any]) -> bool:
    breakdown = hit.get("match_breakdown") or {}
    return (
        breakdown.get("file_match") is True
        and breakdown.get("xlsx_sheet_match") is True
        and breakdown.get("xlsx_range_exact") is True
        and breakdown.get("document_version_match") is False
    )


def safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def ratio(numerator: float, denominator: int) -> float:
    return round(float(numerator) / denominator, 4) if denominator else 0.0


def metric_subset(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {key: metrics.get(key) for key in METRIC_KEYS}


def metric_delta(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    delta = {}
    for key in METRIC_KEYS:
        before_value = before.get(key)
        after_value = after.get(key)
        delta[key] = round(float(after_value) - float(before_value), 4) if is_number(before_value) and is_number(after_value) else None
    return delta


def is_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def finite_metric_values(before: Mapping[str, Any], after: Mapping[str, Any]) -> bool:
    for metrics in (before, after):
        for key in METRIC_KEYS:
            value = metrics.get(key)
            if value is None or not is_number(value):
                return False
    return True


def blockers_for_completion(criteria: Mapping[str, Any]) -> list[str]:
    return [key for key, value in criteria.items() if value is not True]


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
    parser.add_argument("--before-report", default=str(DEFAULT_BEFORE_REPORT))
    parser.add_argument("--after-report", default=str(DEFAULT_AFTER_REPORT))
    parser.add_argument("--before-gold", default=str(DEFAULT_BEFORE_GOLD))
    parser.add_argument("--after-gold", default=str(DEFAULT_AFTER_GOLD))
    parser.add_argument("--hidden-report", default=str(DEFAULT_HIDDEN_REPORT))
    parser.add_argument("--candidate-decision", default=str(DEFAULT_CANDIDATE_DECISION))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
