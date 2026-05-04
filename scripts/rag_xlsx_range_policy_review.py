"""Review Track A A3 range policy decision for XLSX v3."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_A1_REVIEW = Path("reports/rag_xlsx_v3_failure_case_review.json")
DEFAULT_SNAPSHOT = Path("reports/rag_xlsx_v3_current_diagnostic_snapshot.json")
DEFAULT_REVIEW_OUTPUT = Path("reports/rag_xlsx_range_policy_review.json")
DEFAULT_IMPACT_OUTPUT = Path("reports/rag_xlsx_range_policy_dry_run_impact.json")
TARGET_QUERY_ID = "gq_auto_041"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    a1_review = read_json(Path(args.a1_review))
    snapshot = read_json(Path(args.snapshot))
    target = next(row for row in a1_review.get("rows") or [] if row.get("query_id") == args.query_id)
    impact = build_impact(args=args, target=target, snapshot=snapshot)
    review = build_review(args=args, target=target, impact=impact)
    write_json(Path(args.review_output), review)
    write_json(Path(args.impact_output), impact)
    print_json(
        {
            "status": review["status"],
            "review_output": args.review_output,
            "impact_output": args.impact_output,
            "policy_decision": review["policy_decision"],
            "metric_inflation_risk": review["metric_inflation_risk"],
        }
    )
    return 0


def build_review(*, args: argparse.Namespace, target: Mapping[str, Any], impact: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED",
        "report_role": "xlsx_range_policy_review",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "source_a1_review": args.a1_review,
        "source_dry_run_impact": args.impact_output,
        "reviewed_query_id": args.query_id,
        "current_policy": target.get("range_match_policy"),
        "policy_decision": "KEEP",
        "policy_reason": (
            "The only top-k contains/overlap evidence is a sheet_summary range that is too broad for a row-level query; "
            "accepting it would inflate location accuracy without row-group evidence."
        ),
        "human_citation_acceptability": "LOW_FOR_ROW_LEVEL_QUERY",
        "metric_inflation_risk": "HIGH_IF_SHEET_SUMMARY_COUNTS_AS_ROW_MATCH",
        "top_k_evidence": target.get("top_k_hits") or [],
        "dry_run_summary": impact.get("policy_impacts"),
        "completion_criteria": {
            "reviewed_query_id": args.query_id,
            "policy_decision_valid": True,
            "policy_reason_present": True,
            "metric_inflation_risk_reviewed": True,
        },
        "guardrails": guardrails_payload(),
    }


def build_impact(*, args: argparse.Namespace, target: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    metrics = snapshot.get("metrics") or {}
    positive_count = int(snapshot.get("positive_row_count") or 0)
    before_accuracy = to_float(metrics.get("xlsx_citation_location_accuracy"))
    before_matched = round(before_accuracy * positive_count) if before_accuracy is not None and positive_count else None
    policies = []
    for name, key in [("EXACT_RANGE", "xlsx_range_exact"), ("CONTAINS_EXPECTED", "xlsx_range_contains"), ("OVERLAP_RANGE", "xlsx_range_overlap")]:
        match = first_hit_with(target.get("top_k_hits") or [], key)
        range_only_pass = match is not None
        chunk_aware_pass = bool(range_only_pass and ((match.get("match_breakdown") or {}).get("chunk_type_match")))
        policies.append(
            {
                "policy": name,
                "range_only_pass": range_only_pass,
                "chunk_aware_pass": chunk_aware_pass,
                "first_matching_rank": match.get("rank") if match else None,
                "first_matching_chunk_type": match.get("chunk_type") if match else None,
                "first_matching_cell_range": match.get("cell_range") if match else None,
            }
        )
    contains_or_overlap_range_only = any(
        row["policy"] in {"CONTAINS_EXPECTED", "OVERLAP_RANGE"} and row["range_only_pass"] for row in policies
    )
    contains_or_overlap_chunk_aware = any(
        row["policy"] in {"CONTAINS_EXPECTED", "OVERLAP_RANGE"} and row["chunk_aware_pass"] for row in policies
    )
    inflated_accuracy = accuracy_after(before_matched, positive_count, add_one=contains_or_overlap_range_only)
    chunk_aware_accuracy = accuracy_after(before_matched, positive_count, add_one=contains_or_overlap_chunk_aware)
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED",
        "report_role": "xlsx_range_policy_dry_run_impact",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "source_a1_review": args.a1_review,
        "source_snapshot": args.snapshot,
        "reviewed_query_id": args.query_id,
        "positive_row_count": positive_count,
        "before_xlsx_citation_location_accuracy": before_accuracy,
        "before_location_match_count_estimate": before_matched,
        "policy_impacts": policies,
        "range_only_acceptance": {
            "would_recover_target": contains_or_overlap_range_only,
            "after_location_match_count_estimate": (before_matched + 1) if before_matched is not None and contains_or_overlap_range_only else before_matched,
            "after_xlsx_citation_location_accuracy_estimate": inflated_accuracy,
            "risk": "inflates metric by accepting sheet_summary evidence for a row-level query",
        },
        "chunk_aware_acceptance": {
            "would_recover_target": contains_or_overlap_chunk_aware,
            "after_location_match_count_estimate": (before_matched + 1) if before_matched is not None and contains_or_overlap_chunk_aware else before_matched,
            "after_xlsx_citation_location_accuracy_estimate": chunk_aware_accuracy,
            "risk": "low, but no chunk-aware alternate policy pass was observed",
        },
        "guardrails": guardrails_payload(),
    }


def first_hit_with(hits: list[Mapping[str, Any]], key: str) -> Mapping[str, Any] | None:
    for hit in hits:
        if (hit.get("match_breakdown") or {}).get(key):
            return hit
    return None


def accuracy_after(before_matched: int | None, positive_count: int, *, add_one: bool) -> float | None:
    if before_matched is None or not positive_count:
        return None
    return round((before_matched + (1 if add_one else 0)) / positive_count, 4)


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def guardrails_payload() -> dict[str, Any]:
    return {
        "promotion_evidence_true_set": False,
        "global_policy_relaxed": False,
        "gold_v0_changed": False,
        "immutable_baseline_changed": False,
        "candidate_v1_mutated": False,
    }


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
    parser.add_argument("--a1-review", default=str(DEFAULT_A1_REVIEW))
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--review-output", default=str(DEFAULT_REVIEW_OUTPUT))
    parser.add_argument("--impact-output", default=str(DEFAULT_IMPACT_OUTPUT))
    parser.add_argument("--query-id", default=TARGET_QUERY_ID)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
