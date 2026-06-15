"""Create Track A A5 XLSX candidate v2 decision report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_QUERY_SURFACE_PLAN = Path("reports/rag_eval/rag-ingestion/rag_xlsx_query_surface_patch_plan.json")
DEFAULT_RANGE_POLICY_REVIEW = Path("reports/rag_eval/rag-ingestion/rag_xlsx_range_policy_review.json")
DEFAULT_FORMULA_DATE_REVIEW = Path("reports/rag_eval/rag-ingestion/rag_xlsx_formula_date_contract_review.json")
DEFAULT_OUTPUT = Path("reports/rag_eval/rag-ingestion/xlsx_candidate_v2_decision.json")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    query_surface = read_json(Path(args.query_surface_plan))
    range_policy = read_json(Path(args.range_policy_review))
    formula_date = read_json(Path(args.formula_date_review))
    payload = build_decision(args=args, query_surface=query_surface, range_policy=range_policy, formula_date=formula_date)
    write_json(Path(args.output), payload)
    print_json({"status": payload["status"], "output": args.output, "decision": payload["decision"], "reason": payload["reason"]})
    return 0 if payload["status"] == "COMPLETED" else 1


def build_decision(
    *,
    args: argparse.Namespace,
    query_surface: Mapping[str, Any],
    range_policy: Mapping[str, Any],
    formula_date: Mapping[str, Any],
) -> dict[str, Any]:
    reasons = []
    blockers = []
    if query_surface.get("status") != "COMPLETED":
        blockers.append("a2_query_surface_not_completed")
    if range_policy.get("status") != "COMPLETED":
        blockers.append("a3_range_policy_not_completed")
    if formula_date.get("status") != "COMPLETED":
        blockers.append("a4_formula_date_not_completed")
    if (query_surface.get("query_quality_audit") or {}).get("pass") is not True:
        blockers.append("a2_query_quality_audit_failed")
    if range_policy.get("policy_decision") != "KEEP":
        blockers.append("a3_range_policy_not_keep")

    if query_surface.get("reviewed_query_count"):
        reasons.append("QUERY_ONLY")
    if range_policy.get("policy_decision") == "KEEP":
        reasons.append("RANGE_POLICY_ONLY")
    if formula_date.get("next_action") == "QUERY_REWRITE":
        reasons.append("QUERY_ONLY")
    create_v2_conditions = {
        "embedding_text_missing_required_surface": formula_date.get("embedding_contract_change_proven") is True,
        "chunk_granularity_structure_change_needed": range_policy.get("candidate_v2_required_now") is True,
        "ranking_feature_or_text_contract_change_needed": formula_date.get("candidate_v2_required_now") is True,
        "separate_comparable_artifact_needed": False,
    }
    create_v2_required = any(create_v2_conditions.values())
    unique_reasons = sorted(set(reasons))
    if create_v2_required:
        decision = "CREATE_V2_REQUIRED"
        status = "NEEDS_REVIEW"
    elif blockers:
        decision = "NEEDS_REVIEW"
        status = "NEEDS_REVIEW"
    else:
        decision = "SKIP"
        status = "COMPLETED"
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "xlsx_candidate_v2_decision",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "source_query_surface_plan": args.query_surface_plan,
        "source_range_policy_review": args.range_policy_review,
        "source_formula_date_review": args.formula_date_review,
        "decision": decision,
        "reason": unique_reasons,
        "candidate_v1_mutated": False,
        "candidate_v2_created": False,
        "create_v2_conditions": create_v2_conditions,
        "decision_inputs": {
            "a2": {
                "reviewed_query_count": query_surface.get("reviewed_query_count"),
                "query_quality_audit_pass": (query_surface.get("query_quality_audit") or {}).get("pass"),
            },
            "a3": {
                "policy_decision": range_policy.get("policy_decision"),
                "metric_inflation_risk": range_policy.get("metric_inflation_risk"),
            },
            "a4": {
                "next_action": formula_date.get("next_action"),
                "expected_surface": formula_date.get("expected_surface"),
                "candidate_v2_required_now": formula_date.get("candidate_v2_required_now"),
            },
        },
        "completion_criteria": {
            "inputs_completed": not [
                blocker for blocker in blockers if blocker.endswith("_not_completed")
            ],
            "query_quality_audit_pass": "a2_query_quality_audit_failed" not in blockers,
            "range_policy_keep": "a3_range_policy_not_keep" not in blockers,
            "candidate_v2_required_now": create_v2_required,
            "decision_is_skip": decision == "SKIP",
            "reason_allowed": bool(set(unique_reasons).intersection({"QUERY_ONLY", "RANGE_POLICY_ONLY", "GOLD_REVIEW_ONLY"})),
            "candidate_v1_mutated": False,
        },
        "blockers": blockers,
        "guardrails": {
            "allow_unscoped_used": False,
            "candidate_v1_overwritten": False,
            "hidden_safe_stale_rows_used_for_v2": False,
        },
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
    parser.add_argument("--query-surface-plan", default=str(DEFAULT_QUERY_SURFACE_PLAN))
    parser.add_argument("--range-policy-review", default=str(DEFAULT_RANGE_POLICY_REVIEW))
    parser.add_argument("--formula-date-review", default=str(DEFAULT_FORMULA_DATE_REVIEW))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
