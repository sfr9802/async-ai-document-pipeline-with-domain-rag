"""Split supplemental deterministic drafts into LLM-polishing lanes.

This script does not call an LLM. It classifies deterministic drafts and
abstains into diagnostic polishing lanes while keeping table-like rows from
being treated as factual row/column/value answers.
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
    iter_jsonl,
    read_csv,
    resolve_path,
    sorted_counter,
    supplemental_output_path_blockers,
    truthy,
    utc_timestamp,
    write_csv,
    write_json,
)


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_llm_polishing_candidate_split.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_llm_polishing_candidate_split.csv"
DEFAULT_QUALITY_CSV = REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.csv"
DEFAULT_DRAFT_SHAPE_CSV = REPORT_DIR / "rag_pdf_supplemental_draft_shape_audit.csv"
DEFAULT_TABLE_AUDIT_CSV = REPORT_DIR / "rag_pdf_supplemental_table_like_context_audit.csv"

REQUIRED_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "row_column_value_semantics_claimed": False,
    "local_llm_run": False,
    "pageindex_rerun": False,
    "pageindex_improvement_claimed": False,
}

POLISHING_LANES = [
    "SAFE_SECTION_SUMMARY_POLISHING",
    "RESTRICTED_TABLE_CONTEXT_POLISHING",
    "TABLE_EVIDENCE_CONTRACT_REQUIRED_BEFORE_POLISHING",
    "ABSTAIN_NO_POLISHING",
]

CSV_FIELDS = [
    "query_id",
    "answer_shape",
    "draft_shape_status",
    "table_like_context_candidate",
    "needs_table_parser",
    "polishing_lane",
    "forbidden_claims",
    "allowed_claims",
    "citation_policy",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = resolve_artifact_dir(args.artifact_dir)
    draft_path = resolve_path(args.draft_jsonl) if args.draft_jsonl else artifact_dir / "deterministic_answer_drafts.jsonl"
    quality_csv_path = resolve_path(args.quality_csv)
    draft_shape_csv_path = resolve_path(args.draft_shape_csv)
    table_audit_csv_path = resolve_path(args.table_audit_csv)
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

    payload = build_split(
        artifact_dir=artifact_dir,
        draft_path=draft_path,
        quality_csv_path=quality_csv_path,
        draft_shape_csv_path=draft_shape_csv_path,
        table_audit_csv_path=table_audit_csv_path,
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


def build_split(
    *,
    artifact_dir: Path,
    draft_path: Path,
    quality_csv_path: Path,
    draft_shape_csv_path: Path,
    table_audit_csv_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    draft_rows = read_jsonl_or_block(draft_path, "deterministic draft JSONL", blockers)
    quality_by_id = read_csv_by_id(quality_csv_path, "quality audit CSV", blockers)
    shape_by_id = read_csv_by_id(draft_shape_csv_path, "draft shape audit CSV", blockers)
    table_by_id = read_csv_by_id(table_audit_csv_path, "table-like audit CSV", blockers)

    rows = [
        split_row(row, quality_by_id.get(str(row.get("query_id") or ""), {}), shape_by_id.get(str(row.get("query_id") or ""), {}), table_by_id.get(str(row.get("query_id") or ""), {}))
        for row in draft_rows
    ]
    counts = build_counts(rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and rows:
        status = "PASS_WITH_LLM_POLISHING_CANDIDATE_SPLIT"
    report = {
        "schema_version": "pdf_supplemental_llm_polishing_candidate_split_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "diagnostic_llm_polishing_candidate_split_only",
        "external_cloud_llm_run": False,
        "local_llm_run": False,
        "live_llm_answer_generation_run": False,
        "actual_llm_answer_generation_run": False,
        "actual_generated_answer_output": False,
        "answer_draft_is_actual_generated_llm_answer": False,
        "deterministic_answer_draft_only": True,
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
        "polishing_lane_enum": POLISHING_LANES,
        "input_artifacts": [
            artifact_identity(draft_path),
            artifact_identity(quality_csv_path),
            artifact_identity(draft_shape_csv_path),
            artifact_identity(table_audit_csv_path),
        ],
        "output_artifacts": {
            "json_report": display_path(json_report_path),
            "csv_report": display_path(csv_report_path),
        },
        "artifact_dir": display_path(artifact_dir),
        "counts": counts,
        "rows": rows,
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "SAFE_SECTION_SUMMARY_POLISHING is a future diagnostic polishing candidate lane, not an LLM run.",
            "RESTRICTED_TABLE_CONTEXT_POLISHING may polish table-context wording but must not finalize row/column/value semantics.",
            "NEEDS_TABLE_PARSER rows are not factual table-value answer candidates until a table evidence contract exists.",
        ],
    }
    return {"report": report, "rows": rows}


def split_row(
    draft: Mapping[str, Any],
    quality: Mapping[str, str],
    shape: Mapping[str, str],
    table_audit: Mapping[str, str],
) -> dict[str, Any]:
    answer_shape = str(draft.get("answer_shape") or shape.get("answer_shape") or "")
    draft_shape_status = str(shape.get("draft_shape_status") or ("PASS" if draft.get("answer_draft") else "ABSTAIN_NOT_A_DRAFT"))
    has_draft = bool(draft.get("answer_draft")) and draft_shape_status != "ABSTAIN_NOT_A_DRAFT"
    table_like = (
        truthy(quality.get("table_like_context_candidate"))
        or truthy(table_audit.get("table_like_context_candidate"))
        or answer_shape == "PDF_TABLE_LIKE_CANDIDATE_WITH_CONTEXT"
    )
    needs_table_parser = table_audit.get("recommended_next_action") == "NEEDS_TABLE_PARSER"
    lane = polishing_lane(
        has_draft=has_draft,
        answer_shape=answer_shape,
        table_like=table_like,
        needs_table_parser=needs_table_parser,
    )
    policy = claims_policy(lane=lane, needs_table_parser=needs_table_parser)
    return {
        "query_id": draft.get("query_id") or shape.get("query_id") or quality.get("query_id"),
        "answer_shape": answer_shape,
        "draft_shape_status": draft_shape_status,
        "table_like_context_candidate": table_like,
        "needs_table_parser": needs_table_parser,
        "polishing_lane": lane,
        "forbidden_claims": policy["forbidden_claims"],
        "allowed_claims": policy["allowed_claims"],
        "citation_policy": policy["citation_policy"],
    }


def polishing_lane(*, has_draft: bool, answer_shape: str, table_like: bool, needs_table_parser: bool) -> str:
    if not has_draft:
        return "ABSTAIN_NO_POLISHING"
    if needs_table_parser:
        return "TABLE_EVIDENCE_CONTRACT_REQUIRED_BEFORE_POLISHING"
    if table_like or answer_shape == "PDF_TABLE_LIKE_CANDIDATE_WITH_CONTEXT":
        return "RESTRICTED_TABLE_CONTEXT_POLISHING"
    if answer_shape == "PDF_SECTION_WITH_SUMMARY":
        return "SAFE_SECTION_SUMMARY_POLISHING"
    return "SAFE_SECTION_SUMMARY_POLISHING"


def claims_policy(*, lane: str, needs_table_parser: bool) -> dict[str, Any]:
    common_forbidden = [
        "promotion_or_denominator_claim",
        "pdf_c7_policy_decision",
        "actual_llm_answer_generation_claim",
        "new_fact_not_present_in_deterministic_source",
    ]
    if lane == "SAFE_SECTION_SUMMARY_POLISHING":
        return {
            "forbidden_claims": common_forbidden + ["citation_without_content_support"],
            "allowed_claims": [
                "polish_section_summary_wording",
                "preserve_source_claim_and_locator",
                "keep_diagnostic_role",
            ],
            "citation_policy": "Citation may attach to the same section/paragraph claim already present in the deterministic draft.",
        }
    if lane == "RESTRICTED_TABLE_CONTEXT_POLISHING":
        return {
            "forbidden_claims": common_forbidden + [
                "row_column_value_finalization",
                "factual_table_value_answer",
                "table_semantics_success_claim",
            ],
            "allowed_claims": [
                "polish_table_context_excerpt_wording",
                "state_that_the_cited_area_is_table_like_context",
                "preserve_uncertainty_about_row_column_value_semantics",
            ],
            "citation_policy": "Citation may support table-like context presence only; it must not support a finalized row/column/value answer.",
        }
    if lane == "TABLE_EVIDENCE_CONTRACT_REQUIRED_BEFORE_POLISHING":
        forbidden = common_forbidden + [
            "row_column_value_finalization",
            "factual_table_value_answer",
            "table_semantics_success_claim",
            "needs_table_parser_as_success",
        ]
        if needs_table_parser:
            forbidden.append("treat_needs_table_parser_row_as_polishable_value_answer")
        return {
            "forbidden_claims": forbidden,
            "allowed_claims": [
                "retain_as_diagnostic_table_context",
                "route_to_table_evidence_contract_work",
            ],
            "citation_policy": "No factual table-value polishing before a row/column/value evidence contract exists.",
        }
    return {
        "forbidden_claims": common_forbidden + ["polish_empty_or_abstained_answer"],
        "allowed_claims": ["retain_abstain_status"],
        "citation_policy": "No polishing; row remains abstained.",
    }


def build_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    lane_counts = Counter(str(row.get("polishing_lane") or "UNKNOWN") for row in rows)
    draft_rows = [row for row in rows if row.get("draft_shape_status") != "ABSTAIN_NOT_A_DRAFT"]
    table_rows = [row for row in draft_rows if row.get("table_like_context_candidate") is True]
    return {
        "row_count": len(rows),
        "deterministic_draft_count": len(draft_rows),
        "abstain_no_polishing_count": lane_counts.get("ABSTAIN_NO_POLISHING", 0),
        "safe_section_summary_polishing_count": lane_counts.get("SAFE_SECTION_SUMMARY_POLISHING", 0),
        "restricted_table_context_polishing_count": lane_counts.get("RESTRICTED_TABLE_CONTEXT_POLISHING", 0),
        "table_evidence_contract_required_before_polishing_count": lane_counts.get("TABLE_EVIDENCE_CONTRACT_REQUIRED_BEFORE_POLISHING", 0),
        "table_like_draft_count": len(table_rows),
        "needs_table_parser_draft_count": sum(1 for row in draft_rows if row.get("needs_table_parser") is True),
        "needs_table_parser_not_factual_table_value_answer_candidate": True,
        "polishing_lane_counts": sorted_counter(lane_counts),
        "answer_shape_counts": sorted_counter(Counter(str(row.get("answer_shape") or "ABSTAIN") for row in rows)),
    }


def read_jsonl_or_block(path: Path, label: str, blockers: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return []
    return [row for row in iter_jsonl(path)]


def read_csv_by_id(path: Path, label: str, blockers: list[str]) -> dict[str, dict[str, str]]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return {}
    return {str(row.get("query_id") or ""): row for row in read_csv(path)}


def resolve_artifact_dir(value: str | None) -> Path:
    if value:
        return resolve_path(value)
    raise ValueError("Pass --artifact-dir for deterministic post-analysis; latest-by-mtime artifact selection is disabled.")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--draft-jsonl", default=None)
    parser.add_argument("--quality-csv", default=str(DEFAULT_QUALITY_CSV))
    parser.add_argument("--draft-shape-csv", default=str(DEFAULT_DRAFT_SHAPE_CSV))
    parser.add_argument("--table-audit-csv", default=str(DEFAULT_TABLE_AUDIT_CSV))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
