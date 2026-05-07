"""Write supplemental PDF table-evidence next-step summary.

This composes existing diagnostic outputs plus the new LH/table/polishing
post-analysis reports. It is not promotion evidence and does not mutate any
runtime, parser, candidate, baseline, gold, denominator, DB, or SearchUnit
artifact.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
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
    write_json,
)


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_table_evidence_next_step_summary.json"
DEFAULT_MD_REPORT = REPORT_DIR / "rag_pdf_supplemental_table_evidence_next_step_summary.md"

REQUIRED_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "row_column_value_semantics_claimed": False,
    "local_llm_run": False,
    "pageindex_rerun": False,
    "pageindex_improvement_claimed": False,
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = {
        "failure_summary": resolve_path(args.failure_summary),
        "abstain_breakdown": resolve_path(args.abstain_breakdown),
        "quality_audit": resolve_path(args.quality_audit),
        "dataset_gap": resolve_path(args.dataset_gap),
        "table_like_audit": resolve_path(args.table_like_audit),
        "draft_shape_audit": resolve_path(args.draft_shape_audit),
        "lh_not_ready_analysis": resolve_path(args.lh_not_ready_analysis),
        "table_semantics_probe": resolve_path(args.table_semantics_probe),
        "polishing_split": resolve_path(args.polishing_split),
        "table_like_audit_csv": resolve_path(args.table_like_audit_csv),
    }
    json_report_path = resolve_path(args.report)
    md_report_path = resolve_path(args.markdown)
    output_path_blockers = supplemental_output_path_blockers({
        "json_report": json_report_path,
        "markdown_report": md_report_path,
    })
    if output_path_blockers:
        print(json.dumps({
            "status": "FAIL_CLOSED_UNSAFE_OUTPUT_PATH",
            "json_report": display_path(json_report_path),
            "markdown_report": display_path(md_report_path),
            "blockers": output_path_blockers,
        }, ensure_ascii=False, indent=2))
        return 2

    payload = build_summary(paths, json_report_path, md_report_path)
    write_json(json_report_path, payload)
    write_markdown(md_report_path, payload)
    print(json.dumps({
        "status": payload["status"],
        "json_report": display_path(json_report_path),
        "markdown_report": display_path(md_report_path),
        "counts": payload["counts"],
        "blockers": payload["blockers"],
    }, ensure_ascii=False, indent=2))
    return 0 if not payload["blockers"] else 2


def build_summary(paths: Mapping[str, Path], json_report_path: Path, md_report_path: Path) -> dict[str, Any]:
    blockers: list[str] = []
    reports = read_reports(paths, blockers)
    for label, report in reports.items():
        validate_report_guardrails(label, report, blockers)
    table_audit_rows = read_csv_or_block(paths["table_like_audit_csv"], "table-like audit CSV", blockers)

    failure_summary = reports.get("failure_summary") or {}
    quality_audit = reports.get("quality_audit") or {}
    abstain_breakdown = reports.get("abstain_breakdown") or {}
    dataset_gap = reports.get("dataset_gap") or {}
    table_like_audit = reports.get("table_like_audit") or {}
    lh_analysis = reports.get("lh_not_ready_analysis") or {}
    table_probe = reports.get("table_semantics_probe") or {}
    polishing_split = reports.get("polishing_split") or {}

    failure_counts = failure_summary.get("counts") or {}
    quality_counts = quality_audit.get("counts") or {}
    abstain_counts = abstain_breakdown.get("counts") or {}
    dataset_counts = dataset_gap.get("counts") or {}
    table_audit_counts = table_like_audit.get("counts") or {}
    lh_counts = lh_analysis.get("counts") or {}
    table_probe_counts = table_probe.get("counts") or {}
    polishing_counts = polishing_split.get("counts") or {}

    prior_needs_parser_ids = {
        row.get("query_id")
        for row in table_audit_rows
        if row.get("recommended_next_action") == "NEEDS_TABLE_PARSER"
    }
    probe_ready_ids = {
        str(row.get("query_id") or "")
        for row in (table_probe.get("rows") or [])
        if row.get("table_semantics_candidate_ready") is True
        or row.get("recommended_next_action") == "CAN_BUILD_TABLE_EVIDENCE_OBJECT"
    }
    needs_parser_candidate_ready_ids = sorted(query_id for query_id in prior_needs_parser_ids if query_id in probe_ready_ids)

    evidence_ready_count = quality_counts.get("evidence_ready_count") or failure_counts.get("evidence_ready_count")
    abstain_count = failure_counts.get("abstain_count") or abstain_counts.get("abstain_count")
    evidence_object_count = quality_counts.get("evidence_object_count") or failure_counts.get("evidence_object_count")
    counts = {
        "evidence_object_count": evidence_object_count,
        "evidence_ready_count": evidence_ready_count,
        "abstain_count": abstain_count,
        "ready_abstain_status_maintained": evidence_ready_count == 115 and abstain_count == 35,
        "keyword_only_risk_count": quality_counts.get("keyword_only_risk_count") or failure_counts.get("keyword_only_risk_count"),
        "keyword_risk_content_draft_count": failure_counts.get("keyword_risk_content_draft_count"),
        "keyword_risk_abstain_count": failure_counts.get("keyword_risk_abstain_count"),
        "abstain_table_like_without_row_column_value_count": (abstain_counts.get("primary_abstain_reason_counts") or {}).get("TABLE_LIKE_WITHOUT_ROW_COLUMN_VALUE"),
        "lh_not_ready_count": lh_counts.get("lh_not_ready_row_count") or dataset_counts.get("lh_not_ready_count"),
        "lh_table_like_semantics_problem_count": lh_counts.get("table_semantics_issue_count") or dataset_counts.get("lh_table_like_not_ready_count"),
        "lh_likely_fix_lane_counts": lh_counts.get("likely_fix_lane_counts") or {},
        "table_like_candidate_count": table_probe_counts.get("table_like_context_candidate_count") or table_audit_counts.get("table_like_context_candidate_count"),
        "table_probe_recommended_next_action_counts": table_probe_counts.get("recommended_next_action_counts") or {},
        "table_semantics_candidate_ready_count": table_probe_counts.get("table_semantics_candidate_ready_count"),
        "table_like_audit_needs_table_parser_count": (table_audit_counts.get("recommended_next_action_counts") or {}).get("NEEDS_TABLE_PARSER", 0),
        "needs_table_parser_table_evidence_object_candidate_ready_count": len(needs_parser_candidate_ready_ids),
        "needs_table_parser_table_evidence_object_candidate_ready_sample_query_ids": needs_parser_candidate_ready_ids[:12],
        "keep_abstain_row_count": polishing_counts.get("abstain_no_polishing_count"),
        "llm_polishing_safe_candidate_count": polishing_counts.get("safe_section_summary_polishing_count"),
        "llm_polishing_restricted_candidate_count": polishing_counts.get("restricted_table_context_polishing_count"),
        "llm_polishing_table_contract_required_count": polishing_counts.get("table_evidence_contract_required_before_polishing_count"),
        "ocr_needed_evidence_object_count": quality_counts.get("ocr_needed_object_count") or failure_counts.get("ocr_needed_evidence_object_count"),
    }
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers:
        status = "PASS_WITH_DIAGNOSTIC_TABLE_EVIDENCE_NEXT_STEPS"
    return {
        "schema_version": "pdf_supplemental_table_evidence_next_step_summary_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "diagnostic_table_evidence_next_step_summary_only",
        "actual_llm_answer_generation_run": False,
        "actual_generated_answer_output": False,
        "answer_draft_is_actual_generated_llm_answer": False,
        "deterministic_answer_draft_only": True,
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
        "promotion_relationship": "not_promotion_evidence",
        "official_denominator_relationship": "unchanged_and_separate",
        "gold_relationship": "no_gold_or_synthetic_anchor_promotion",
        "pdf_c7_relationship": "policy_decision_not_applied",
        "input_artifacts": {label: artifact_identity(path) for label, path in paths.items()},
        "output_artifacts": {
            "json_report": display_path(json_report_path),
            "markdown_report": display_path(md_report_path),
        },
        "counts": counts,
        "lh_not_ready_summary": {
            "cause_counts": {
                "query_surface_issue_count": lh_counts.get("query_surface_issue_count"),
                "parser_block_issue_count": lh_counts.get("parser_block_issue_count"),
                "table_semantics_issue_count": lh_counts.get("table_semantics_issue_count"),
            },
            "likely_fix_lane_counts": lh_counts.get("likely_fix_lane_counts"),
            "table_semantics_issue_counts": lh_counts.get("table_semantics_issue_counts"),
        },
        "table_like_probe_summary": {
            "counts": table_probe_counts,
            "needs_table_parser_is_contract_signal": True,
            "table_semantics_success_claimed": False,
        },
        "llm_polishing_summary": {
            "counts": polishing_counts,
            "external_cloud_llm_run": False,
            "local_llm_run": False,
            "live_llm_answer_generation_run": False,
        },
        "separation_rationale": {
            "promotion_gold_denominator": "The outputs decompose diagnostic evidence gaps only; no gold CSV, official denominator, candidate artifact, or immutable baseline is modified.",
            "pdf_c7": "PDF C7 policy remains a user-governed decision and is not applied by this post-analysis.",
            "parser_and_bbox": "Existing PyMuPDF parsed block text and bbox metadata are read as evidence; parser expansion and bbox-contract success are not claimed.",
            "llm": "Deterministic drafts are dry-run previews; actual LLM answer generation, polishing, and judge scoring were not run.",
            "ocr": "OCR-needed evidence object coverage remains zero and should stay in a separate lane.",
        },
        "blockers": blockers,
        "warnings": [],
    }


def read_reports(paths: Mapping[str, Path], blockers: list[str]) -> dict[str, Mapping[str, Any]]:
    reports: dict[str, Mapping[str, Any]] = {}
    json_labels = [label for label in paths if label != "table_like_audit_csv"]
    for label in json_labels:
        path = paths[label]
        if not path.exists():
            blockers.append(f"{label} missing: {display_path(path)}")
            reports[label] = {}
            continue
        reports[label] = read_json(path)
    return reports


def validate_report_guardrails(label: str, report: Mapping[str, Any], blockers: list[str]) -> None:
    if not report:
        return
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
        "actual_llm_answer_generation_run": False,
        "actual_generated_answer_output": False,
        "answer_draft_is_actual_generated_llm_answer": False,
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
    }
    required_true = {
        "synthetic_diagnostic_only": True,
        "pdf_scope_only": True,
        "xlsx_scope_excluded": True,
        "bbox_contract_success_not_claimed": True,
        "table_semantics_success_not_claimed": True,
    }
    if report.get("evidence_role") != "diagnostic":
        blockers.append(f"{label}.evidence_role expected diagnostic, got {report.get('evidence_role')!r}")
    for key, expected in required_false.items():
        if key in report and report.get(key) is not expected:
            blockers.append(f"{label}.{key} expected {expected!r}, got {report.get(key)!r}")
    for key, expected in required_true.items():
        if key in report and report.get(key) is not expected:
            blockers.append(f"{label}.{key} expected {expected!r}, got {report.get(key)!r}")
    if report.get("blockers"):
        blockers.append(f"{label} has blockers: {report.get('blockers')!r}")
    new_post_analysis_labels = {"lh_not_ready_analysis", "table_semantics_probe", "polishing_split"}
    if label in new_post_analysis_labels:
        required_keys = set(required_false) | set(required_true) | {"evidence_role"}
        missing = sorted(key for key in required_keys if key not in report)
        if missing:
            blockers.append(f"{label} missing required guardrail keys: {missing}")


def read_csv_or_block(path: Path, label: str, blockers: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_markdown(path: Path, payload: Mapping[str, Any]) -> None:
    counts = payload.get("counts") or {}
    lh = payload.get("lh_not_ready_summary") or {}
    probe = (payload.get("table_like_probe_summary") or {}).get("counts") or {}
    polishing = (payload.get("llm_polishing_summary") or {}).get("counts") or {}
    lines = [
        "# Supplemental PDF Table Evidence Next-Step Summary",
        "",
        "This summary is diagnostic-only. It does not rerun PageIndex, call any live/cloud/local LLM or optional judge, run promotion, change official denominators or gold, apply PDF C7 policy, tune retrieval, rerank, expand parsers, mutate DB/SearchUnit, change candidate artifacts, or change immutable baselines.",
        "",
        "## Ready And Abstain",
        "",
        f"- Evidence-ready rows remain `{counts.get('evidence_ready_count')}`.",
        f"- Abstain rows remain `{counts.get('abstain_count')}`.",
        f"- Ready/abstain invariant maintained: `{counts.get('ready_abstain_status_maintained')}`.",
        f"- Keyword-only risk remains `{counts.get('keyword_only_risk_count')}`: `{counts.get('keyword_risk_content_draft_count')}` deterministic draft mitigations plus `{counts.get('keyword_risk_abstain_count')}` abstains.",
        "",
        "## LH Not-Ready",
        "",
        f"- LH not-ready rows: `{counts.get('lh_not_ready_count')}`.",
        f"- LH table-semantics problem rows: `{counts.get('lh_table_like_semantics_problem_count')}`.",
        f"- LH likely fix lanes: `{json.dumps(counts.get('lh_likely_fix_lane_counts') or {}, ensure_ascii=False, sort_keys=True)}`.",
        f"- Cause counts: `{json.dumps(lh.get('cause_counts') or {}, ensure_ascii=False, sort_keys=True)}`.",
        "",
        "## Table-Like Probe",
        "",
        f"- Table-like candidates probed: `{counts.get('table_like_candidate_count')}`.",
        f"- Probe recommended actions: `{json.dumps(counts.get('table_probe_recommended_next_action_counts') or {}, ensure_ascii=False, sort_keys=True)}`.",
        f"- Candidate-ready rows under row/column/value plus unit/header rule: `{counts.get('table_semantics_candidate_ready_count')}`.",
        f"- Existing NEEDS_TABLE_PARSER rows: `{counts.get('table_like_audit_needs_table_parser_count')}`.",
        f"- NEEDS_TABLE_PARSER rows that look table-evidence-object candidate-ready after probe: `{counts.get('needs_table_parser_table_evidence_object_candidate_ready_count')}`.",
        "- Table semantics success and bbox contract success are not claimed.",
        "",
        "## LLM Polishing Split",
        "",
        f"- Safe section-summary polishing candidates: `{counts.get('llm_polishing_safe_candidate_count')}`.",
        f"- Restricted table-context polishing candidates: `{counts.get('llm_polishing_restricted_candidate_count')}`.",
        f"- Table evidence contract required before polishing: `{counts.get('llm_polishing_table_contract_required_count')}`.",
        f"- Rows kept as abstain/no-polishing: `{counts.get('keep_abstain_row_count')}`.",
        f"- Lane counts: `{json.dumps(polishing.get('polishing_lane_counts') or {}, ensure_ascii=False, sort_keys=True)}`.",
        "",
        "## OCR And Execution",
        "",
        f"- OCR-needed evidence object coverage remains `{counts.get('ocr_needed_evidence_object_count')}`.",
        "- Actual LLM answer generation was not run.",
        "- Deterministic draft pass count is not an actual LLM answer pass.",
        "",
        "## Separation From Promotion",
        "",
        "- `promotion_evidence=false`; `evidence_role=diagnostic`.",
        "- `official_denominator_changed=false`; `codex_gold_policy_decision_applied=false`; `pdf_c7_policy_decision_applied=false`.",
        "- `synthetic_diagnostic_only=true`; `pdf_scope_only=true`; `xlsx_scope_excluded=true`.",
        "- `external_cloud_llm_run=false`; `local_llm_run=false`; `live_llm_answer_generation_run=false`; `optional_judge_run=false`.",
        "- `pageindex_rerun=false`; `pageindex_improvement_claimed=false`.",
        "- `bbox_contract_success_not_claimed=true`; `table_semantics_success_not_claimed=true`; `row_column_value_semantics_claimed=false`.",
        "- `retrieval_tuning_applied=false`; `reranking_applied=false`; `parser_expansion_applied=false`.",
        "- `db_mutation_applied=false`; `searchunit_mutation_applied=false`; `candidate_artifact_changed=false`; `immutable_baseline_changed=false`.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failure-summary", default=str(REPORT_DIR / "rag_pdf_supplemental_evidence_failure_analysis_summary.json"))
    parser.add_argument("--abstain-breakdown", default=str(REPORT_DIR / "rag_pdf_supplemental_abstain_reason_breakdown.json"))
    parser.add_argument("--quality-audit", default=str(REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.json"))
    parser.add_argument("--dataset-gap", default=str(REPORT_DIR / "rag_pdf_supplemental_dataset_gap_analysis.json"))
    parser.add_argument("--table-like-audit", default=str(REPORT_DIR / "rag_pdf_supplemental_table_like_context_audit.json"))
    parser.add_argument("--draft-shape-audit", default=str(REPORT_DIR / "rag_pdf_supplemental_draft_shape_audit.json"))
    parser.add_argument("--lh-not-ready-analysis", default=str(REPORT_DIR / "rag_pdf_supplemental_lh_not_ready_analysis.json"))
    parser.add_argument("--table-semantics-probe", default=str(REPORT_DIR / "rag_pdf_supplemental_table_semantics_probe.json"))
    parser.add_argument("--polishing-split", default=str(REPORT_DIR / "rag_pdf_supplemental_llm_polishing_candidate_split.json"))
    parser.add_argument("--table-like-audit-csv", default=str(REPORT_DIR / "rag_pdf_supplemental_table_like_context_audit.csv"))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--markdown", default=str(DEFAULT_MD_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
