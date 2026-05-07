"""Reclassify LH supplemental PDF not-ready rows.

This diagnostic-only post-analysis preserves the original LH not-ready
`likely_fix_lane` while adding a revised lane that separates true table evidence
contract needs from LHCS/KCS reference-code, section/list, and serializer
fragments.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
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


DEFAULT_LH_ANALYSIS_JSON = REPORT_DIR / "rag_pdf_supplemental_lh_not_ready_analysis.json"
DEFAULT_FALSE_POSITIVE_JSON = REPORT_DIR / "rag_pdf_supplemental_table_like_false_positive_classification.json"
DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_lh_not_ready_reclassification.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_lh_not_ready_reclassification.csv"

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

REVISED_FIX_LANES = [
    "TABLE_EVIDENCE_CONTRACT_REQUIRED",
    "SECTION_EXPANSION_OR_SERIALIZER_FIX",
    "REFERENCE_CODE_FRAGMENT_FILTER_REQUIRED",
    "QUERY_REWRITE_ONLY",
    "KEEP_ABSTAIN",
    "MANUAL_REVIEW_REQUIRED",
]

CSV_FIELDS = [
    "query_id",
    "dataset_source",
    "file_name",
    "page_no",
    "anchor_type",
    "abstain_reason",
    "table_like_context_candidate",
    "likely_fix_lane",
    "false_positive_classification",
    "classification_reason",
    "revised_fix_lane",
    "revised_fix_reason",
    "block_text_excerpt",
    "nearby_context_excerpt",
    "section_context",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    lh_analysis_path = resolve_path(args.lh_not_ready_analysis)
    false_positive_path = resolve_path(args.false_positive_classification)
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

    payload = build_reclassification(
        lh_analysis_path=lh_analysis_path,
        false_positive_path=false_positive_path,
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


def build_reclassification(
    *,
    lh_analysis_path: Path,
    false_positive_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    lh_payload = read_json_or_block(lh_analysis_path, "LH not-ready analysis JSON", blockers)
    false_positive_payload = read_json_or_block(false_positive_path, "table-like false-positive classification JSON", blockers)
    validate_guardrails("lh_not_ready_analysis", lh_payload, blockers)
    validate_guardrails("false_positive_classification", false_positive_payload, blockers)
    false_positive_by_id = {
        str(row.get("query_id") or ""): row
        for row in false_positive_payload.get("rows", [])
        if isinstance(row, Mapping)
    }
    rows = [
        reclassify_lh_row(row, false_positive_by_id.get(str(row.get("query_id") or ""), {}))
        for row in lh_payload.get("rows", [])
        if isinstance(row, Mapping)
    ]
    counts = build_counts(rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and rows:
        status = "PASS_WITH_LH_NOT_READY_RECLASSIFICATION"
    report = {
        "schema_version": "pdf_supplemental_lh_not_ready_reclassification_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "diagnostic_lh_not_ready_reclassification_only",
        "likely_fix_lane_preserved": True,
        "revised_fix_lane_enum": REVISED_FIX_LANES,
        "input_artifacts": [
            artifact_identity(lh_analysis_path),
            artifact_identity(false_positive_path),
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
            "LHCS/KCS reference-code fragments are separated from true table evidence contract needs.",
            "Rows moved to SECTION_EXPANSION_OR_SERIALIZER_FIX may still need better evidence context, not table semantics success.",
        ],
    }
    return {"report": report, "rows": rows}


def reclassify_lh_row(row: Mapping[str, Any], false_positive: Mapping[str, Any]) -> dict[str, Any]:
    classification = str(false_positive.get("classification") or ("NOT_TABLE_LIKE_AFTER_REVIEW" if not row.get("table_like_context_candidate") else "AMBIGUOUS_TABLE_LIKE_CONTEXT"))
    revised_lane, reason = revised_lane_for(row, classification)
    return {
        "query_id": row.get("query_id"),
        "dataset_source": row.get("dataset_source"),
        "file_name": row.get("file_name"),
        "page_no": row.get("page_no"),
        "anchor_type": row.get("anchor_type"),
        "abstain_reason": row.get("abstain_reason"),
        "table_like_context_candidate": row.get("table_like_context_candidate"),
        "likely_fix_lane": row.get("likely_fix_lane"),
        "false_positive_classification": classification,
        "classification_reason": false_positive.get("classification_reason") or "",
        "revised_fix_lane": revised_lane,
        "revised_fix_reason": reason,
        "block_text_excerpt": row.get("block_text_excerpt"),
        "nearby_context_excerpt": row.get("nearby_context_excerpt"),
        "section_context": row.get("section_context"),
    }


def revised_lane_for(row: Mapping[str, Any], classification: str) -> tuple[str, str]:
    if classification == "REAL_NUMERIC_GRID_TABLE":
        return "TABLE_EVIDENCE_CONTRACT_REQUIRED", "numeric table-like grid still needs a row/column/value evidence contract"
    if classification == "REFERENCE_CODE_FRAGMENT":
        return "REFERENCE_CODE_FRAGMENT_FILTER_REQUIRED", "LHCS/KCS reference-code fragment should be filtered or serialized as reference context"
    if classification == "FOOTER_OR_PRINT_ARTIFACT":
        return "KEEP_ABSTAIN", "footer/print artifact should not become evidence object input"
    if classification in {"SECTION_OR_LIST_FRAGMENT", "TABLE_TITLE_OR_HEADER_ONLY", "BULLET_OR_FORMULA_CONTEXT", "NOT_TABLE_LIKE_AFTER_REVIEW"}:
        return "SECTION_EXPANSION_OR_SERIALIZER_FIX", "not a row/column/value table contract problem; expand or serialize surrounding section/list context"
    if row.get("parser_block_issue") == "PARSER_BLOCK_OK" and row.get("query_surface_issue") != "QUERY_SURFACE_OK":
        return "QUERY_REWRITE_ONLY", "query surface is the only remaining diagnostic issue"
    if classification == "AMBIGUOUS_TABLE_LIKE_CONTEXT":
        return "MANUAL_REVIEW_REQUIRED", "ambiguous table-like context after false-positive review"
    return "MANUAL_REVIEW_REQUIRED", "unclassified diagnostic case"


def build_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_class: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_class[str(row.get("false_positive_classification") or "UNKNOWN")][str(row.get("revised_fix_lane") or "UNKNOWN")] += 1
    return {
        "lh_not_ready_row_count": len(rows),
        "original_likely_fix_lane_counts": sorted_counter(Counter(str(row.get("likely_fix_lane") or "UNKNOWN") for row in rows)),
        "false_positive_classification_counts": sorted_counter(Counter(str(row.get("false_positive_classification") or "UNKNOWN") for row in rows)),
        "revised_fix_lane_counts": sorted_counter(Counter(str(row.get("revised_fix_lane") or "UNKNOWN") for row in rows)),
        "revised_fix_lane_by_false_positive_classification": {
            key: sorted_counter(counter)
            for key, counter in sorted(by_class.items())
        },
        "table_evidence_contract_required_count": sum(1 for row in rows if row.get("revised_fix_lane") == "TABLE_EVIDENCE_CONTRACT_REQUIRED"),
        "reference_code_fragment_filter_required_count": sum(1 for row in rows if row.get("revised_fix_lane") == "REFERENCE_CODE_FRAGMENT_FILTER_REQUIRED"),
        "section_expansion_or_serializer_fix_count": sum(1 for row in rows if row.get("revised_fix_lane") == "SECTION_EXPANSION_OR_SERIALIZER_FIX"),
    }


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
    parser.add_argument("--lh-not-ready-analysis", default=str(DEFAULT_LH_ANALYSIS_JSON))
    parser.add_argument("--false-positive-classification", default=str(DEFAULT_FALSE_POSITIVE_JSON))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
