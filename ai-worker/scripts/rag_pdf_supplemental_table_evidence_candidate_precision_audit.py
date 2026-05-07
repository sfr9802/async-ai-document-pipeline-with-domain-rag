"""Audit precision of table evidence object candidates.

This diagnostic-only audit reviews existing `CAN_BUILD_TABLE_EVIDENCE_OBJECT`
rows from the supplemental table semantics probe. It applies the false-positive
classification layer and keeps all success claims false.
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
    truthy,
    utc_timestamp,
    write_csv,
    write_json,
)


DEFAULT_PROBE_JSON = REPORT_DIR / "rag_pdf_supplemental_table_semantics_probe.json"
DEFAULT_FALSE_POSITIVE_JSON = REPORT_DIR / "rag_pdf_supplemental_table_like_false_positive_classification.json"
DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_table_evidence_candidate_precision_audit.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_table_evidence_candidate_precision_audit.csv"

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

CANDIDATE_QUALITY_ENUM = [
    "HIGH_CONFIDENCE_TABLE_EVIDENCE_OBJECT_CANDIDATE",
    "EXTRACTIVE_CONTEXT_ONLY",
    "FALSE_POSITIVE_OR_NOISE",
    "NEEDS_MANUAL_REVIEW",
    "NEEDS_LAYOUT_TABLE_PARSER",
]

CSV_FIELDS = [
    "query_id",
    "dataset_source",
    "file_name",
    "page_no",
    "prior_recommended_next_action",
    "false_positive_classification",
    "candidate_quality",
    "candidate_quality_reason",
    "row_label_candidate_present",
    "column_label_candidate_present",
    "value_candidate_present",
    "unit_or_header_context_present",
    "table_semantics_candidate_ready",
    "table_semantics_success_claimed",
    "table_text_excerpt",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    probe_json_path = resolve_path(args.table_semantics_probe)
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

    payload = build_audit(
        probe_json_path=probe_json_path,
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


def build_audit(
    *,
    probe_json_path: Path,
    false_positive_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    probe_payload = read_json_or_block(probe_json_path, "table semantics probe JSON", blockers)
    false_positive_payload = read_json_or_block(false_positive_path, "false-positive classification JSON", blockers)
    validate_guardrails("table_semantics_probe", probe_payload, blockers)
    validate_guardrails("false_positive_classification", false_positive_payload, blockers)
    false_positive_by_id = {
        str(row.get("query_id") or ""): row
        for row in false_positive_payload.get("rows", [])
        if isinstance(row, Mapping)
    }
    rows = []
    for row in probe_payload.get("rows", []):
        if not isinstance(row, Mapping):
            continue
        if row.get("recommended_next_action") != "CAN_BUILD_TABLE_EVIDENCE_OBJECT":
            continue
        rows.append(audit_candidate(row, false_positive_by_id.get(str(row.get("query_id") or ""), {})))
    counts = build_counts(rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and rows:
        status = "PASS_WITH_TABLE_EVIDENCE_CANDIDATE_PRECISION_AUDIT"
    report = {
        "schema_version": "pdf_supplemental_table_evidence_candidate_precision_audit_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "diagnostic_table_evidence_candidate_precision_audit_only",
        "candidate_quality_enum": CANDIDATE_QUALITY_ENUM,
        "prior_can_build_count_preserved": len(rows),
        "success_claims_remain_false": True,
        "input_artifacts": [
            artifact_identity(probe_json_path),
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
            "HIGH_CONFIDENCE_TABLE_EVIDENCE_OBJECT_CANDIDATE remains diagnostic candidate status only.",
            "Footer/print artifacts are forced to FALSE_POSITIVE_OR_NOISE.",
            "Numeric grids without row labels are routed to NEEDS_LAYOUT_TABLE_PARSER.",
        ],
    }
    return {"report": report, "rows": rows}


def audit_candidate(row: Mapping[str, Any], false_positive: Mapping[str, Any]) -> dict[str, Any]:
    classification = str(false_positive.get("classification") or "AMBIGUOUS_TABLE_LIKE_CONTEXT")
    row_present = bool(row.get("row_label_candidates"))
    column_present = bool(row.get("column_label_candidates"))
    value_present = bool(row.get("value_candidates"))
    unit_or_header = truthy(row.get("unit_or_header_context_present"))
    quality, reason = candidate_quality_for(
        classification=classification,
        row_present=row_present,
        column_present=column_present,
        value_present=value_present,
        unit_or_header=unit_or_header,
    )
    return {
        "query_id": row.get("query_id"),
        "dataset_source": row.get("dataset_source"),
        "file_name": row.get("file_name"),
        "page_no": row.get("page_no"),
        "prior_recommended_next_action": row.get("recommended_next_action"),
        "false_positive_classification": classification,
        "candidate_quality": quality,
        "candidate_quality_reason": reason,
        "row_label_candidate_present": row_present,
        "column_label_candidate_present": column_present,
        "value_candidate_present": value_present,
        "unit_or_header_context_present": unit_or_header,
        "table_semantics_candidate_ready": truthy(row.get("table_semantics_candidate_ready")),
        "table_semantics_success_claimed": False,
        "table_text_excerpt": row.get("table_text_excerpt"),
    }


def candidate_quality_for(
    *,
    classification: str,
    row_present: bool,
    column_present: bool,
    value_present: bool,
    unit_or_header: bool,
) -> tuple[str, str]:
    if classification == "FOOTER_OR_PRINT_ARTIFACT":
        return "FALSE_POSITIVE_OR_NOISE", "footer/print artifact must not become a table evidence object"
    if classification == "REFERENCE_CODE_FRAGMENT":
        return "EXTRACTIVE_CONTEXT_ONLY", "reference-code fragment may be cited as context only, not row/column/value evidence"
    if classification == "REAL_NUMERIC_GRID_TABLE":
        if not row_present:
            return "NEEDS_LAYOUT_TABLE_PARSER", "numeric grid has values but no reliable row label candidate"
        if row_present and column_present and value_present and unit_or_header:
            return "HIGH_CONFIDENCE_TABLE_EVIDENCE_OBJECT_CANDIDATE", "row/header/value/unit-or-header candidates are present and no false-positive class was found"
        return "NEEDS_LAYOUT_TABLE_PARSER", "numeric grid needs layout-aware table parser before evidence object creation"
    if classification == "BULLET_OR_FORMULA_CONTEXT":
        return "EXTRACTIVE_CONTEXT_ONLY", "formula or bullet context can support extractive wording but not table-value evidence"
    if classification == "TABLE_TITLE_OR_HEADER_ONLY":
        return "EXTRACTIVE_CONTEXT_ONLY", "title/header-only context is not a table evidence object"
    if classification in {"SECTION_OR_LIST_FRAGMENT", "NOT_TABLE_LIKE_AFTER_REVIEW"}:
        return "FALSE_POSITIVE_OR_NOISE", "section/list or not-table context is false positive for table evidence object"
    return "NEEDS_MANUAL_REVIEW", "ambiguous candidate after false-positive review"


def build_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "prior_can_build_table_evidence_object_count": len(rows),
        "candidate_quality_counts": sorted_counter(Counter(str(row.get("candidate_quality") or "UNKNOWN") for row in rows)),
        "false_positive_classification_counts": sorted_counter(Counter(str(row.get("false_positive_classification") or "UNKNOWN") for row in rows)),
        "high_confidence_table_evidence_object_candidate_count": sum(1 for row in rows if row.get("candidate_quality") == "HIGH_CONFIDENCE_TABLE_EVIDENCE_OBJECT_CANDIDATE"),
        "false_positive_or_noise_count": sum(1 for row in rows if row.get("candidate_quality") == "FALSE_POSITIVE_OR_NOISE"),
        "layout_table_parser_required_count": sum(1 for row in rows if row.get("candidate_quality") == "NEEDS_LAYOUT_TABLE_PARSER"),
        "extractive_context_only_count": sum(1 for row in rows if row.get("candidate_quality") == "EXTRACTIVE_CONTEXT_ONLY"),
        "manual_review_required_count": sum(1 for row in rows if row.get("candidate_quality") == "NEEDS_MANUAL_REVIEW"),
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
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
    parser.add_argument("--table-semantics-probe", default=str(DEFAULT_PROBE_JSON))
    parser.add_argument("--false-positive-classification", default=str(DEFAULT_FALSE_POSITIVE_JSON))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
