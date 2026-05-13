"""Summarize supplemental PDF table-like reclassification.

This summary composes the false-positive classifier, LH reclassification,
precision audit, and canary readiness reports. It remains diagnostic-only and
separate from promotion, gold, denominators, PDF C7, parser expansion, and any
runtime mutation.
"""

from __future__ import annotations

import argparse
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
    supplemental_output_path_blockers,
    utc_timestamp,
    write_json,
)


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_table_like_reclassification_summary.json"
DEFAULT_MD_REPORT = REPORT_DIR / "rag_pdf_supplemental_table_like_reclassification_summary.md"

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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = {
        "table_evidence_next_step_summary": resolve_path(args.table_evidence_next_step_summary),
        "false_positive_classification": resolve_path(args.false_positive_classification),
        "lh_not_ready_reclassification": resolve_path(args.lh_not_ready_reclassification),
        "precision_audit": resolve_path(args.precision_audit),
        "canary_readiness": resolve_path(args.canary_readiness),
        "evidence_failure_summary": resolve_path(args.evidence_failure_summary),
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
    for label, payload in reports.items():
        validate_guardrails(label, payload, blockers)

    next_step_counts = (reports.get("table_evidence_next_step_summary") or {}).get("counts") or {}
    false_counts = (reports.get("false_positive_classification") or {}).get("counts") or {}
    lh_counts = (reports.get("lh_not_ready_reclassification") or {}).get("counts") or {}
    precision_counts = (reports.get("precision_audit") or {}).get("counts") or {}
    canary_counts = (reports.get("canary_readiness") or {}).get("counts") or {}
    failure_counts = (reports.get("evidence_failure_summary") or {}).get("counts") or {}

    false_by_prior = false_counts.get("classification_by_prior_recommended_next_action") or {}
    broader_layout_required = (false_by_prior.get("NEEDS_TABLE_PARSER") or {}).get("REAL_NUMERIC_GRID_TABLE", 0)
    counts = {
        "evidence_object_count": next_step_counts.get("evidence_object_count") or failure_counts.get("evidence_object_count"),
        "evidence_ready_count": next_step_counts.get("evidence_ready_count") or failure_counts.get("evidence_ready_count"),
        "abstain_count": next_step_counts.get("abstain_count") or failure_counts.get("abstain_count"),
        "ready_abstain_status_maintained": next_step_counts.get("ready_abstain_status_maintained") is True,
        "ocr_needed_evidence_object_count": next_step_counts.get("ocr_needed_evidence_object_count") or failure_counts.get("ocr_needed_evidence_object_count"),
        "table_like_context_candidate_count": false_counts.get("table_like_context_candidate_count"),
        "table_like_false_positive_classification_counts": false_counts.get("classification_counts") or {},
        "lh_not_ready_row_count": lh_counts.get("lh_not_ready_row_count"),
        "lh_revised_fix_lane_counts": lh_counts.get("revised_fix_lane_counts") or {},
        "prior_can_build_table_evidence_object_count": precision_counts.get("prior_can_build_table_evidence_object_count"),
        "high_confidence_table_evidence_object_candidate_count": precision_counts.get("high_confidence_table_evidence_object_candidate_count"),
        "can_build_false_positive_or_noise_count": precision_counts.get("false_positive_or_noise_count"),
        "can_build_layout_table_parser_required_count": precision_counts.get("layout_table_parser_required_count"),
        "broader_numeric_grid_layout_table_parser_required_count": broader_layout_required,
        "can_build_extractive_context_only_count": precision_counts.get("extractive_context_only_count"),
        "llm_canary_total_ready_count": canary_counts.get("total_canary_ready_count"),
        "llm_canary_safe_section_summary_count": canary_counts.get("safe_section_summary_canary_ready_count"),
        "llm_canary_restricted_table_context_count": canary_counts.get("restricted_table_context_canary_ready_count"),
        "llm_canary_exclude_false_positive_or_noise_count": canary_counts.get("exclude_false_positive_or_noise_count"),
        "llm_canary_exclude_until_table_evidence_contract_count": canary_counts.get("exclude_until_table_evidence_contract_count"),
        "prior_polishing_split_40_29_46_35_preserved": canary_counts.get("prior_split_40_29_46_35_preserved") is True,
    }
    blockers.extend(invariant_blockers(counts))
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers:
        status = "PASS_WITH_DIAGNOSTIC_TABLE_LIKE_RECLASSIFICATION"
    return {
        "schema_version": "pdf_supplemental_table_like_reclassification_summary_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "diagnostic_table_like_reclassification_summary_only",
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
        "table_like_reclassification": {
            "classification_counts": false_counts.get("classification_counts"),
            "classification_by_prior_recommended_next_action": false_counts.get("classification_by_prior_recommended_next_action"),
            "interpretation": "False-positive classes are diagnostic filters over table-like context, not table extraction success.",
        },
        "lh_reclassification": {
            "revised_fix_lane_counts": lh_counts.get("revised_fix_lane_counts"),
            "revised_fix_lane_by_false_positive_classification": lh_counts.get("revised_fix_lane_by_false_positive_classification"),
        },
        "precision_audit": {
            "candidate_quality_counts": precision_counts.get("candidate_quality_counts"),
            "false_positive_classification_counts": precision_counts.get("false_positive_classification_counts"),
        },
        "canary_readiness": {
            "canary_lane_counts": canary_counts.get("canary_lane_counts"),
            "prior_polishing_split_40_29_46_35_preserved": canary_counts.get("prior_split_40_29_46_35_preserved"),
        },
        "separation_rationale": {
            "promotion_gold_denominator": "This run classifies existing diagnostic evidence only; no gold CSV, official denominator, candidate artifact, or immutable baseline was modified.",
            "pdf_c7": "PDF C7 policy remains unresolved and was not decided by Codex.",
            "parser": "Rows needing layout/table parser support are identified as future contract/parser work; parser expansion was not applied.",
            "llm": "Canary readiness is a file-based selection only; no local/cloud LLM or judge was called.",
        },
        "blockers": blockers,
        "warnings": [],
    }


def invariant_blockers(counts: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = {
        "evidence_ready_count": 115,
        "abstain_count": 35,
        "ocr_needed_evidence_object_count": 0,
        "table_like_context_candidate_count": 102,
        "prior_can_build_table_evidence_object_count": 31,
    }
    for key, value in expected.items():
        if counts.get(key) != value:
            blockers.append(f"{key} expected {value!r}, got {counts.get(key)!r}")
    if counts.get("ready_abstain_status_maintained") is not True:
        blockers.append("ready_abstain_status_maintained expected true")
    if counts.get("prior_polishing_split_40_29_46_35_preserved") is not True:
        blockers.append("prior polishing split 40/29/46/35 was not preserved")
    return blockers


def read_reports(paths: Mapping[str, Path], blockers: list[str]) -> dict[str, Mapping[str, Any]]:
    reports: dict[str, Mapping[str, Any]] = {}
    for label, path in paths.items():
        if not path.exists():
            blockers.append(f"{label} missing: {display_path(path)}")
            reports[label] = {}
            continue
        reports[label] = read_json(path)
    return reports


def validate_guardrails(label: str, payload: Mapping[str, Any], blockers: list[str]) -> None:
    if not payload:
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


def write_markdown(path: Path, payload: Mapping[str, Any]) -> None:
    counts = payload.get("counts") or {}
    lines = [
        "# Supplemental PDF Table-Like Reclassification Summary",
        "",
        "This summary is diagnostic-only. It does not rerun PageIndex, call an LLM or judge, run promotion, change official denominators or gold, apply PDF C7 policy, tune retrieval, rerank, expand parsers, relax thresholds, mutate DB/SearchUnit, change candidate artifacts, or change immutable baselines.",
        "",
        "## Preserved State",
        "",
        f"- Evidence-ready / abstain remains `{counts.get('evidence_ready_count')}` / `{counts.get('abstain_count')}`.",
        f"- OCR-needed evidence object coverage remains `{counts.get('ocr_needed_evidence_object_count')}`.",
        f"- Prior LLM polishing split `40/29/46/35` preserved: `{counts.get('prior_polishing_split_40_29_46_35_preserved')}`.",
        "",
        "## Table-Like False Positives",
        "",
        f"- Table-like rows reclassified: `{counts.get('table_like_context_candidate_count')}`.",
        f"- Classification counts: `{json.dumps(counts.get('table_like_false_positive_classification_counts') or {}, ensure_ascii=False, sort_keys=True)}`.",
        "- `CAN_BUILD_TABLE_EVIDENCE_OBJECT` remains candidate-only and is not table-semantics success.",
        "",
        "## LH Not-Ready Reclassification",
        "",
        f"- LH not-ready rows: `{counts.get('lh_not_ready_row_count')}`.",
        f"- Revised fix lanes: `{json.dumps(counts.get('lh_revised_fix_lane_counts') or {}, ensure_ascii=False, sort_keys=True)}`.",
        "",
        "## Candidate Precision",
        "",
        f"- Prior CAN_BUILD candidates: `{counts.get('prior_can_build_table_evidence_object_count')}`.",
        f"- High-confidence diagnostic table evidence object candidates: `{counts.get('high_confidence_table_evidence_object_candidate_count')}`.",
        f"- CAN_BUILD false-positive/noise rows: `{counts.get('can_build_false_positive_or_noise_count')}`.",
        f"- CAN_BUILD layout table parser required rows: `{counts.get('can_build_layout_table_parser_required_count')}`.",
        f"- Broader numeric-grid layout/parser contract rows outside high-confidence candidates: `{counts.get('broader_numeric_grid_layout_table_parser_required_count')}`.",
        f"- CAN_BUILD extractive-context-only rows: `{counts.get('can_build_extractive_context_only_count')}`.",
        "",
        "## LLM Canary Readiness",
        "",
        f"- Total diagnostic canary-ready rows: `{counts.get('llm_canary_total_ready_count')}`.",
        f"- Safe section-summary canary rows: `{counts.get('llm_canary_safe_section_summary_count')}`.",
        f"- Restricted table-context canary rows: `{counts.get('llm_canary_restricted_table_context_count')}`.",
        f"- Excluded as false-positive/noise: `{counts.get('llm_canary_exclude_false_positive_or_noise_count')}`.",
        f"- Excluded until table evidence contract: `{counts.get('llm_canary_exclude_until_table_evidence_contract_count')}`.",
        "",
        "## Guardrails",
        "",
        "- `promotion_evidence=false`; `evidence_role=diagnostic`.",
        "- `official_denominator_changed=false`; `codex_gold_policy_decision_applied=false`; `pdf_c7_policy_decision_applied=false`.",
        "- `external_cloud_llm_run=false`; `local_llm_run=false`; `live_llm_answer_generation_run=false`; `optional_judge_run=false`.",
        "- `pageindex_rerun=false`; `pageindex_improvement_claimed=false`.",
        "- `bbox_contract_success_not_claimed=true`; `table_semantics_success_not_claimed=true`; `row_column_value_semantics_claimed=false`; `table_semantics_success_claimed=false`.",
        "- `retrieval_tuning_applied=false`; `reranking_applied=false`; `parser_expansion_applied=false`.",
        "- `db_mutation_applied=false`; `searchunit_mutation_applied=false`; `candidate_artifact_changed=false`; `immutable_baseline_changed=false`.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table-evidence-next-step-summary", default=str(REPORT_DIR / "rag_pdf_supplemental_table_evidence_next_step_summary.json"))
    parser.add_argument("--false-positive-classification", default=str(REPORT_DIR / "rag_pdf_supplemental_table_like_false_positive_classification.json"))
    parser.add_argument("--lh-not-ready-reclassification", default=str(REPORT_DIR / "rag_pdf_supplemental_lh_not_ready_reclassification.json"))
    parser.add_argument("--precision-audit", default=str(REPORT_DIR / "rag_pdf_supplemental_table_evidence_candidate_precision_audit.json"))
    parser.add_argument("--canary-readiness", default=str(REPORT_DIR / "rag_pdf_supplemental_llm_polishing_canary_readiness.json"))
    parser.add_argument("--evidence-failure-summary", default=str(REPORT_DIR / "rag_pdf_supplemental_evidence_failure_analysis_summary.json"))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--markdown", default=str(DEFAULT_MD_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
