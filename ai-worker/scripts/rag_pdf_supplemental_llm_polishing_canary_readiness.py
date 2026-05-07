"""Compute supplemental LLM polishing canary readiness without calling an LLM.

The existing polishing split is preserved. This script only applies the
false-positive and precision-audit layers to decide which rows are safe
diagnostic canary inputs.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from rag_pdf_supplemental_common import (
    COMMON_GUARDRAILS,
    REPORT_DIR,
    artifact_identity,
    display_path,
    read_json,
    resolve_path,
    sorted_counter,
    supplemental_output_path_blockers,
    utc_timestamp,
    write_csv,
    write_json,
)


DEFAULT_POLISHING_SPLIT_JSON = REPORT_DIR / "rag_pdf_supplemental_llm_polishing_candidate_split.json"
DEFAULT_FALSE_POSITIVE_JSON = REPORT_DIR / "rag_pdf_supplemental_table_like_false_positive_classification.json"
DEFAULT_PRECISION_AUDIT_JSON = REPORT_DIR / "rag_pdf_supplemental_table_evidence_candidate_precision_audit.json"
DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_llm_polishing_canary_readiness.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_llm_polishing_canary_readiness.csv"

REQUIRED_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "local_llm_run": False,
    "pageindex_rerun": False,
    "pageindex_improvement_claimed": False,
    "actual_llm_answer_generation_run": False,
    "actual_generated_answer_output": False,
    "answer_draft_is_actual_generated_llm_answer": False,
    "table_semantics_success_claimed": False,
    "row_column_value_semantics_claimed": False,
}

CANARY_LANES = [
    "SAFE_SECTION_SUMMARY_CANARY_READY",
    "RESTRICTED_TABLE_CONTEXT_CANARY_READY",
    "EXCLUDE_UNTIL_TABLE_EVIDENCE_CONTRACT",
    "EXCLUDE_FALSE_POSITIVE_OR_NOISE",
    "ABSTAIN_NO_CANARY",
]

CSV_FIELDS = [
    "query_id",
    "answer_shape",
    "prior_polishing_lane",
    "false_positive_classification",
    "candidate_quality",
    "canary_lane",
    "canary_reason",
    "forbidden_claims",
    "allowed_claims",
    "citation_policy",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    polishing_split_path = resolve_path(args.polishing_split)
    false_positive_path = resolve_path(args.false_positive_classification)
    precision_audit_path = resolve_path(args.precision_audit)
    json_report_path = resolve_path(args.report)
    csv_report_path = resolve_path(args.csv)
    output_path_blockers = supplemental_output_path_blockers({
        "json_report": json_report_path,
        "csv_report": csv_report_path,
    })
    if output_path_blockers:
        print(json.dumps({
            "status": "FAIL_CLOSED_UNSAFE_OUTPUT_PATH",
            "json_report": display_path(json_report_path),
            "csv_report": display_path(csv_report_path),
            "blockers": output_path_blockers,
        }, ensure_ascii=False, indent=2))
        return 2

    payload = build_readiness(
        polishing_split_path=polishing_split_path,
        false_positive_path=false_positive_path,
        precision_audit_path=precision_audit_path,
        json_report_path=json_report_path,
        csv_report_path=csv_report_path,
    )
    write_json(json_report_path, payload["report"])
    write_csv(csv_report_path, payload["rows"], CSV_FIELDS)
    print(json.dumps({
        "status": payload["report"]["status"],
        "json_report": display_path(json_report_path),
        "csv_report": display_path(csv_report_path),
        "counts": payload["report"]["counts"],
        "blockers": payload["report"]["blockers"],
    }, ensure_ascii=False, indent=2))
    return 0 if not payload["report"]["blockers"] else 2


def build_readiness(
    *,
    polishing_split_path: Path,
    false_positive_path: Path,
    precision_audit_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    split_payload = read_json_or_block(polishing_split_path, "polishing split JSON", blockers)
    false_positive_payload = read_json_or_block(false_positive_path, "false-positive classification JSON", blockers)
    precision_payload = read_json_or_block(precision_audit_path, "precision audit JSON", blockers)
    validate_guardrails("polishing_split", split_payload, blockers)
    validate_guardrails("false_positive_classification", false_positive_payload, blockers)
    validate_guardrails("precision_audit", precision_payload, blockers)
    false_positive_by_id = {
        str(row.get("query_id") or ""): row
        for row in false_positive_payload.get("rows", [])
        if isinstance(row, Mapping)
    }
    precision_by_id = {
        str(row.get("query_id") or ""): row
        for row in precision_payload.get("rows", [])
        if isinstance(row, Mapping)
    }
    rows = [
        canary_row(row, false_positive_by_id.get(str(row.get("query_id") or ""), {}), precision_by_id.get(str(row.get("query_id") or ""), {}))
        for row in split_payload.get("rows", [])
        if isinstance(row, Mapping)
    ]
    counts = build_counts(rows, split_payload.get("counts") or {})
    blockers.extend(split_invariant_blockers(counts))
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and rows:
        status = "PASS_WITH_LLM_POLISHING_CANARY_READINESS"
    report = {
        "schema_version": "pdf_supplemental_llm_polishing_canary_readiness_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "diagnostic_llm_polishing_canary_readiness_only",
        "external_cloud_llm_run": False,
        "local_llm_run": False,
        "live_llm_answer_generation_run": False,
        "actual_llm_answer_generation_run": False,
        "actual_generated_answer_output": False,
        "answer_draft_is_actual_generated_llm_answer": False,
        "prior_polishing_split_preserved": True,
        "canary_lane_enum": CANARY_LANES,
        "input_artifacts": [
            artifact_identity(polishing_split_path),
            artifact_identity(false_positive_path),
            artifact_identity(precision_audit_path),
        ],
        "output_artifacts": {
            "json_report": display_path(json_report_path),
            "csv_report": display_path(csv_report_path),
        },
        "counts": counts,
        "rows": rows,
        "blockers": blockers,
        "warnings": [],
        "notes": [
            "Canary-ready means safe diagnostic prompt-polishing input only; no LLM call occurred.",
            "False positives and rows needing table evidence contracts are excluded from canary input.",
        ],
    }
    return {"report": report, "rows": rows}


def canary_row(row: Mapping[str, Any], false_positive: Mapping[str, Any], precision: Mapping[str, Any]) -> dict[str, Any]:
    prior_lane = str(row.get("polishing_lane") or "")
    classification = str(false_positive.get("classification") or "")
    quality = str(precision.get("candidate_quality") or "")
    lane, reason = canary_lane_for(prior_lane, classification, quality)
    return {
        "query_id": row.get("query_id"),
        "answer_shape": row.get("answer_shape"),
        "prior_polishing_lane": prior_lane,
        "false_positive_classification": classification,
        "candidate_quality": quality,
        "canary_lane": lane,
        "canary_reason": reason,
        "forbidden_claims": row.get("forbidden_claims") or [],
        "allowed_claims": row.get("allowed_claims") or [],
        "citation_policy": row.get("citation_policy") or "",
    }


def canary_lane_for(prior_lane: str, classification: str, quality: str) -> tuple[str, str]:
    if prior_lane == "ABSTAIN_NO_POLISHING":
        return "ABSTAIN_NO_CANARY", "abstained row remains out of canary"
    if prior_lane == "SAFE_SECTION_SUMMARY_POLISHING":
        return "SAFE_SECTION_SUMMARY_CANARY_READY", "section-summary deterministic draft can be polished in a future diagnostic canary"
    if classification in {"FOOTER_OR_PRINT_ARTIFACT", "REFERENCE_CODE_FRAGMENT", "SECTION_OR_LIST_FRAGMENT", "NOT_TABLE_LIKE_AFTER_REVIEW"}:
        return "EXCLUDE_FALSE_POSITIVE_OR_NOISE", "false-positive classification excludes row from canary"
    if quality == "FALSE_POSITIVE_OR_NOISE":
        return "EXCLUDE_FALSE_POSITIVE_OR_NOISE", "precision audit marked row as noise"
    if prior_lane == "TABLE_EVIDENCE_CONTRACT_REQUIRED_BEFORE_POLISHING":
        return "EXCLUDE_UNTIL_TABLE_EVIDENCE_CONTRACT", "existing split requires table evidence contract before polishing"
    if prior_lane == "RESTRICTED_TABLE_CONTEXT_POLISHING":
        if classification in {"BULLET_OR_FORMULA_CONTEXT", "REAL_NUMERIC_GRID_TABLE"} or quality in {
            "HIGH_CONFIDENCE_TABLE_EVIDENCE_OBJECT_CANDIDATE",
            "EXTRACTIVE_CONTEXT_ONLY",
        }:
            return "RESTRICTED_TABLE_CONTEXT_CANARY_READY", "restricted table-context wording can be canaried without row/column/value success claims"
        return "EXCLUDE_UNTIL_TABLE_EVIDENCE_CONTRACT", "table-like row lacks safe canary classification"
    return "EXCLUDE_UNTIL_TABLE_EVIDENCE_CONTRACT", "unknown polishing lane kept out of canary"


def build_counts(rows: list[Mapping[str, Any]], split_counts: Mapping[str, Any]) -> dict[str, Any]:
    lane_counts = Counter(str(row.get("canary_lane") or "UNKNOWN") for row in rows)
    prior_counts = Counter(str(row.get("prior_polishing_lane") or "UNKNOWN") for row in rows)
    return {
        "row_count": len(rows),
        "prior_polishing_lane_counts": sorted_counter(prior_counts),
        "prior_split_safe_section_summary_count": split_counts.get("safe_section_summary_polishing_count"),
        "prior_split_restricted_table_context_count": split_counts.get("restricted_table_context_polishing_count"),
        "prior_split_table_contract_required_count": split_counts.get("table_evidence_contract_required_before_polishing_count"),
        "prior_split_abstain_no_polishing_count": split_counts.get("abstain_no_polishing_count"),
        "prior_split_40_29_46_35_preserved": (
            split_counts.get("safe_section_summary_polishing_count") == 40
            and split_counts.get("restricted_table_context_polishing_count") == 29
            and split_counts.get("table_evidence_contract_required_before_polishing_count") == 46
            and split_counts.get("abstain_no_polishing_count") == 35
        ),
        "canary_lane_counts": sorted_counter(lane_counts),
        "safe_section_summary_canary_ready_count": lane_counts.get("SAFE_SECTION_SUMMARY_CANARY_READY", 0),
        "restricted_table_context_canary_ready_count": lane_counts.get("RESTRICTED_TABLE_CONTEXT_CANARY_READY", 0),
        "exclude_until_table_evidence_contract_count": lane_counts.get("EXCLUDE_UNTIL_TABLE_EVIDENCE_CONTRACT", 0),
        "exclude_false_positive_or_noise_count": lane_counts.get("EXCLUDE_FALSE_POSITIVE_OR_NOISE", 0),
        "abstain_no_canary_count": lane_counts.get("ABSTAIN_NO_CANARY", 0),
        "total_canary_ready_count": lane_counts.get("SAFE_SECTION_SUMMARY_CANARY_READY", 0) + lane_counts.get("RESTRICTED_TABLE_CONTEXT_CANARY_READY", 0),
    }


def split_invariant_blockers(counts: Mapping[str, Any]) -> list[str]:
    if counts.get("prior_split_40_29_46_35_preserved") is not True:
        return ["prior polishing split expected 40/29/46/35"]
    return []


def validate_guardrails(label: str, payload: Mapping[str, Any], blockers: list[str]) -> None:
    required_false = {
        "promotion_evidence": False,
        "official_denominator_changed": False,
        "codex_gold_policy_decision_applied": False,
        "pdf_c7_policy_decision_applied": False,
        "external_cloud_llm_run": False,
        "local_llm_run": False,
        "live_llm_answer_generation_run": False,
        "optional_judge_run": False,
        "pageindex_rerun": False,
        "pageindex_improvement_claimed": False,
        "retrieval_tuning_applied": False,
        "reranking_applied": False,
        "parser_expansion_applied": False,
        "db_mutation_applied": False,
        "searchunit_mutation_applied": False,
        "candidate_artifact_changed": False,
        "immutable_baseline_changed": False,
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
    }
    if payload.get("evidence_role") != "diagnostic":
        blockers.append(f"{label}.evidence_role expected diagnostic, got {payload.get('evidence_role')!r}")
    for key, expected in required_false.items():
        if key not in payload:
            blockers.append(f"{label}.{key} is missing")
        elif payload.get(key) is not expected:
            blockers.append(f"{label}.{key} expected {expected!r}, got {payload.get(key)!r}")
    if payload.get("blockers"):
        blockers.append(f"{label} has blockers: {payload.get('blockers')!r}")


def read_json_or_block(path: Path, label: str, blockers: list[str]) -> dict[str, Any]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return {}
    return read_json(path)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--polishing-split", default=str(DEFAULT_POLISHING_SPLIT_JSON))
    parser.add_argument("--false-positive-classification", default=str(DEFAULT_FALSE_POSITIVE_JSON))
    parser.add_argument("--precision-audit", default=str(DEFAULT_PRECISION_AUDIT_JSON))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
