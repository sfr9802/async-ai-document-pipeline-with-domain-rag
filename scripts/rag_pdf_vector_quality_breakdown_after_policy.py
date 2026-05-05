"""Reclassify Track C PDF vector failures after the C7.1 policy overlay.

This C6.1 report is diagnostic-only. It preserves the raw C6 breakdown,
applies the reviewed PDF policy manifest, and separates table-pending rows
from reviewed non-table retrieval/ranking failures. It does not rerun
retrieval, indexing, promotion, baseline updates, cleanup, or reset.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from rag_pdf_policy_common import (  # noqa: E402
    EVIDENCE_ROLE,
    PDF_ARTIFACT_DIR,
    PDF_CANDIDATE_NAMESPACE,
    TRUE_RANKING_TYPES,
    artifact_identity,
    bool_cell,
    clean,
    counter_dict,
    dedupe,
    print_json,
    read_csv_rows,
    read_json,
    report_ref,
    utc_run_id,
    utc_timestamp,
    write_json,
)


DEFAULT_RAW_BREAKDOWN = Path("reports/rag_pdf_vector_quality_breakdown.json")
DEFAULT_POLICY_OVERLAY = Path("reports/rag_pdf_gold_policy_decision_overlay.json")
DEFAULT_REVIEWED_MANIFEST = Path("eval/gold_queries_pdf_v1_reviewed.csv")
DEFAULT_OUTPUT = Path("reports/rag_pdf_vector_quality_breakdown_after_policy.json")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    raw_path = Path(args.raw_breakdown)
    overlay_path = Path(args.policy_overlay)
    manifest_path = Path(args.reviewed_manifest)
    payload = build_after_policy_breakdown(
        raw_breakdown=read_json(raw_path),
        policy_overlay=read_json(overlay_path),
        reviewed_manifest_rows=read_csv_rows(manifest_path),
        raw_breakdown_path=raw_path,
        policy_overlay_path=overlay_path,
        reviewed_manifest_path=manifest_path,
        expected_true_failure_count=args.expected_true_failure_count,
    )
    write_json(Path(args.output), payload)
    print_json(payload)
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def build_after_policy_breakdown(
    *,
    raw_breakdown: Mapping[str, Any],
    policy_overlay: Mapping[str, Any],
    reviewed_manifest_rows: list[dict[str, str]],
    raw_breakdown_path: Path,
    policy_overlay_path: Path,
    reviewed_manifest_path: Path,
    expected_true_failure_count: int | None = 7,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    validate_inputs(
        raw_breakdown=raw_breakdown,
        policy_overlay=policy_overlay,
        reviewed_manifest_rows=reviewed_manifest_rows,
        blockers=blockers,
    )
    overlay_by_id = {
        clean(row.get("query_id")): row
        for row in policy_overlay.get("rows") or []
        if isinstance(row, Mapping)
    }
    manifest_by_id = {clean(row.get("query_id")): row for row in reviewed_manifest_rows}
    raw_rows = list(raw_breakdown.get("classified_query_rows") or [])
    missing_manifest_ids = [
        clean(row.get("query_id"))
        for row in raw_rows
        if clean(row.get("query_id")) not in manifest_by_id
    ]
    if missing_manifest_ids:
        blockers.append(
            "reviewed manifest must include every raw C6 query_id: "
            + ", ".join(missing_manifest_ids)
        )
    reclassified_rows = [
        reclassify_row(row, overlay_by_id.get(clean(row.get("query_id"))), manifest_by_id.get(clean(row.get("query_id"))))
        for row in raw_rows
    ]
    unresolved_rows = [row for row in reclassified_rows if row.get("after_policy_classification") == "POLICY_UNRESOLVED"]
    true_failure_rows = [
        row for row in reclassified_rows
        if row.get("true_retrieval_ranking_failure") is True
    ]
    table_pending_rows = [
        row for row in reclassified_rows
        if row.get("after_policy_classification") == "TABLE_PENDING"
    ]
    policy_resolved_rows = [
        row for row in reclassified_rows
        if row.get("policy_resolved") is True
    ]
    eligible_rows = [
        row for row in reclassified_rows
        if row.get("positive_metric_eligible") is True
    ]

    if unresolved_rows:
        blockers.append("policy_unresolved_count must be 0")
    if expected_true_failure_count is not None and len(true_failure_rows) != expected_true_failure_count:
        warnings.append(
            "true_retrieval_ranking_failure_count differs from expected "
            f"{expected_true_failure_count}: actual={len(true_failure_rows)}"
        )
    status = "FAIL" if blockers else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C6.1",
        "report_role": "pdf_vector_quality_breakdown_after_policy",
        "promotion_evidence": False,
        "evidence_role": EVIDENCE_ROLE,
        "pdf_candidate_namespace": PDF_CANDIDATE_NAMESPACE,
        "pdf_artifact_dir": PDF_ARTIFACT_DIR,
        "policy_overlay_applied": True,
        "retrieval_execution": "not_run_by_this_script",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "baseline_execution": "not_run_by_this_script",
        "gold_mutation_execution": "not_run_by_this_script",
        "immutable_baseline_changed": False,
        "xlsx_candidate_artifact_changed": False,
        "input_reports": {
            "raw_c6_breakdown": report_ref(raw_breakdown, raw_breakdown_path),
            "policy_overlay": report_ref(policy_overlay, policy_overlay_path),
            "reviewed_manifest": artifact_identity(reviewed_manifest_path),
        },
        "raw_query_count": len(raw_rows),
        "reviewed_positive_metric_eligible_count": len(eligible_rows),
        "table_deferred_count": len(table_pending_rows),
        "policy_resolved_count": len(policy_resolved_rows),
        "policy_unresolved_count": len(unresolved_rows),
        "true_retrieval_ranking_failure_count": len(true_failure_rows),
        "expected_true_retrieval_ranking_failure_count": expected_true_failure_count,
        "pdf_table_retrieval_ready": False,
        "retrieval_tuning_candidate_ready_for_reviewed_non_table_set": (
            not blockers and len(true_failure_rows) > 0 and len(unresolved_rows) == 0
        ),
        "retrieval_tuning_candidate_ready_for_all_pdf": False,
        "classification_counts": counter_dict(reclassified_rows, "after_policy_classification"),
        "true_retrieval_ranking_failure_query_ids": [row["query_id"] for row in true_failure_rows],
        "table_pending_query_ids": [row["query_id"] for row in table_pending_rows],
        "rows": reclassified_rows,
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "next_action": (
            "Use the 7 reviewed non-table failures for C8 case-level investigation; do not tune broadly yet."
            if status in {"PASS", "PASS_WITH_WARNINGS"}
            else "Resolve C6.1 policy blockers before C8 case packaging."
        ),
        "notes": [
            "Raw C6 remains unchanged; this report is an overlay-applied reclassification.",
            "Table-deferred rows are not counted as retrieval successes or true ranking failures.",
            "Accepted page/chunk policy rows are policy-resolved successes, not exact bbox successes.",
        ],
    }


def reclassify_row(
    row: Mapping[str, Any],
    overlay: Mapping[str, Any] | None,
    manifest: Mapping[str, str] | None,
) -> dict[str, Any]:
    qid = clean(row.get("query_id"))
    raw_type = clean(row.get("failure_type"))
    eligible = bool_cell(manifest.get("positive_metric_eligible")) if manifest else False
    decision = clean(overlay.get("final_decision") if overlay else "")
    policy_resolved = bool(decision)
    if manifest is None:
        classification = "POLICY_UNRESOLVED"
        true_failure = False
        policy_success = False
        ready_action = "REVIEWED_MANIFEST_REPAIR"
    elif decision == "DEFER_TO_TABLE_EXTRACTION":
        classification = "TABLE_PENDING"
        true_failure = False
        policy_success = False
        ready_action = "TABLE_EXTRACTION_DEFERRED"
    elif decision in {"ACCEPT_PAGE_WITH_OPTIONAL_BBOX", "ACCEPT_CHUNK_TYPE_POLICY_RELABEL"}:
        classification = "POLICY_RESOLVED_SUCCESS"
        true_failure = False
        policy_success = True
        ready_action = "POLICY_RESOLVED"
    elif decision in {"KEEP_AS_FAILURE", "REQUIRE_GOLD_BINDING_FIX", "EXCLUDE_FROM_POSITIVE_METRIC"}:
        classification = "POLICY_UNRESOLVED"
        true_failure = False
        policy_success = False
        ready_action = "GOLD_BINDING_REVIEW"
    elif raw_type == "MATCHED":
        classification = "MATCHED"
        true_failure = False
        policy_success = bool(row.get("location_match"))
        ready_action = "NO_ACTION"
    elif raw_type in TRUE_RANKING_TYPES and eligible:
        classification = "TRUE_RETRIEVAL_RANKING_FAILURE"
        true_failure = True
        policy_success = False
        ready_action = "C8_CASE_LEVEL_INVESTIGATION"
    elif not eligible:
        classification = "EXCLUDED_FROM_REVIEWED_POSITIVE_METRIC"
        true_failure = False
        policy_success = False
        ready_action = "EXCLUDED"
    else:
        classification = "POLICY_UNRESOLVED"
        true_failure = False
        policy_success = False
        ready_action = "MANUAL_REVIEW"

    return {
        "query_id": qid,
        "bucket": row.get("bucket"),
        "query": row.get("query"),
        "raw_failure_type": raw_type,
        "raw_c5_failure_reason": row.get("c5_failure_reason"),
        "review_decision": decision or (manifest.get("review_decision") if manifest else ""),
        "pdf_review_label": manifest.get("pdf_review_label") if manifest else "",
        "pdf_match_policy": manifest.get("pdf_match_policy") if manifest else "",
        "positive_metric_eligible": eligible,
        "after_policy_classification": classification,
        "policy_resolved": policy_resolved,
        "policy_adjusted_location_success": policy_success,
        "table_pending": classification == "TABLE_PENDING",
        "true_retrieval_ranking_failure": true_failure,
        "expected": row.get("expected"),
        "evidence": row.get("evidence"),
        "top_hit_summary": row.get("top_hit_summary"),
        "supporting_hit_summary": row.get("supporting_hit_summary"),
        "next_action": ready_action,
    }


def validate_inputs(
    *,
    raw_breakdown: Mapping[str, Any],
    policy_overlay: Mapping[str, Any],
    reviewed_manifest_rows: list[dict[str, str]],
    blockers: list[str],
) -> None:
    if raw_breakdown.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"raw C6 breakdown must be PASS or PASS_WITH_WARNINGS; got {raw_breakdown.get('status')}")
    if raw_breakdown.get("promotion_evidence") is not False:
        blockers.append("raw C6 breakdown must keep promotion_evidence=false")
    if raw_breakdown.get("evidence_role") != EVIDENCE_ROLE:
        blockers.append("raw C6 breakdown must keep evidence_role=diagnostic")
    if int(raw_breakdown.get("unknown_failure_count") or 0) != 0:
        blockers.append("raw C6 unknown_failure_count must be 0")
    if policy_overlay.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"policy overlay must be PASS or PASS_WITH_WARNINGS; got {policy_overlay.get('status')}")
    if policy_overlay.get("promotion_evidence") is not False:
        blockers.append("policy overlay must keep promotion_evidence=false")
    if policy_overlay.get("evidence_role") != EVIDENCE_ROLE:
        blockers.append("policy overlay must keep evidence_role=diagnostic")
    if int(policy_overlay.get("unresolved_candidate_count") or 0) != 0:
        blockers.append("policy overlay unresolved_candidate_count must be 0")
    table_rows = [
        row for row in reviewed_manifest_rows
        if clean(row.get("pdf_review_label")) == "table_deferred"
    ]
    if any(bool_cell(row.get("positive_metric_eligible")) for row in table_rows):
        blockers.append("reviewed manifest table_deferred rows must not be positive_metric_eligible")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-breakdown", default=str(DEFAULT_RAW_BREAKDOWN))
    parser.add_argument("--policy-overlay", default=str(DEFAULT_POLICY_OVERLAY))
    parser.add_argument("--reviewed-manifest", default=str(DEFAULT_REVIEWED_MANIFEST))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--expected-true-failure-count", type=int, default=7)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
