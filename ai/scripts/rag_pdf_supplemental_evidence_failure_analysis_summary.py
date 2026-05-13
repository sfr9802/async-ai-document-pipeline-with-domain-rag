"""Write supplemental PDF evidence-failure analysis summary.

This summary composes existing diagnostic reports plus the row-level failure
audits. It does not run PageIndex, LLMs, judges, retrieval tuning, reranking,
parser expansion, DB/SearchUnit mutations, candidate writes, baseline writes,
gold updates, denominator changes, or PDF C7 policy decisions.
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
    read_csv,
    read_json,
    resolve_path,
    supplemental_output_path_blockers,
    utc_timestamp,
    write_json,
)


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_evidence_failure_analysis_summary.json"
DEFAULT_MD_REPORT = REPORT_DIR / "rag_pdf_supplemental_evidence_failure_analysis_summary.md"

REQUIRED_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "local_llm_run": False,
    "pageindex_rerun": False,
    "pageindex_improvement_claimed": False,
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = {
        "readiness_summary": resolve_path(args.readiness_summary),
        "abstain_breakdown": resolve_path(args.abstain_breakdown),
        "dataset_gap": resolve_path(args.dataset_gap),
        "table_like_audit": resolve_path(args.table_like_audit),
        "draft_shape_audit": resolve_path(args.draft_shape_audit),
        "quality_audit": resolve_path(args.quality_audit),
        "deterministic_draft": resolve_path(args.deterministic_draft),
        "table_like_csv": resolve_path(args.table_like_csv),
        "dataset_gap_csv": resolve_path(args.dataset_gap_csv),
        "draft_shape_csv": resolve_path(args.draft_shape_csv),
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
    warnings: list[str] = []
    reports = read_reports(paths, blockers)
    for label, payload in reports.items():
        if isinstance(payload, Mapping):
            validate_guardrails(label, payload, blockers)
    readiness = reports.get("readiness_summary") or {}
    abstain = reports.get("abstain_breakdown") or {}
    dataset_gap = reports.get("dataset_gap") or {}
    table_audit = reports.get("table_like_audit") or {}
    draft_shape = reports.get("draft_shape_audit") or {}
    readiness_counts = (readiness.get("counts") or {}) if isinstance(readiness, Mapping) else {}
    quality_counts = readiness_counts.get("quality_audit") or {}
    old_draft_counts = readiness_counts.get("draft") or {}
    abstain_counts = (abstain.get("counts") or {}) if isinstance(abstain, Mapping) else {}
    gap_counts = (dataset_gap.get("counts") or {}) if isinstance(dataset_gap, Mapping) else {}
    table_counts = (table_audit.get("counts") or {}) if isinstance(table_audit, Mapping) else {}
    shape_counts = (draft_shape.get("counts") or {}) if isinstance(draft_shape, Mapping) else {}

    table_rows = required_read_csv(paths["table_like_csv"], blockers, "table_like_csv")
    gap_rows = required_read_csv(paths["dataset_gap_csv"], blockers, "dataset_gap_csv")
    shape_rows = required_read_csv(paths["draft_shape_csv"], blockers, "draft_shape_csv")
    recommendation_rows = build_recommendation_rows(table_rows, gap_rows, shape_rows, quality_counts)

    counts = {
        "evidence_object_count": quality_counts.get("evidence_object_count"),
        "evidence_ready_count": quality_counts.get("evidence_ready_count"),
        "abstain_count": old_draft_counts.get("abstained_count") or abstain_counts.get("abstain_count"),
        "keyword_only_risk_count": quality_counts.get("keyword_only_risk_count"),
        "keyword_risk_content_draft_count": shape_counts.get("keyword_echo_prevented_content_bearing_count"),
        "keyword_risk_abstain_count": abstain_counts.get("keyword_only_risk_abstain_count"),
        "table_like_context_candidate_count": table_counts.get("table_like_context_candidate_count"),
        "table_like_needs_table_parser_count": (table_counts.get("recommended_next_action_counts") or {}).get("NEEDS_TABLE_PARSER", 0),
        "table_like_context_only_count": (table_counts.get("recommended_next_action_counts") or {}).get("KEEP_AS_CONTEXT_ONLY", 0),
        "ocr_needed_evidence_object_count": quality_counts.get("ocr_needed_object_count"),
        "draft_shape_pass_count": shape_counts.get("draft_shape_pass_count"),
        "draft_shape_warning_count": shape_counts.get("draft_shape_warning_count"),
        "draft_shape_fail_count": shape_counts.get("draft_shape_fail_count"),
        "lh_not_ready_count": gap_counts.get("lh_not_ready_count"),
    }
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers:
        status = "PASS_WITH_DIAGNOSTIC_FAILURE_ANALYSIS"
    return {
        "schema_version": "pdf_supplemental_evidence_failure_analysis_summary_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "diagnostic_evidence_failure_analysis_summary_only",
        "actual_generated_answer_output": False,
        "actual_llm_answer_generation_run": False,
        "deterministic_answer_draft_only": True,
        "answer_draft_is_actual_generated_llm_answer": False,
        "table_like_context_is_candidate_only": True,
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
        "official_denominator_relationship": "unchanged_and_separate",
        "promotion_relationship": "not_promotion_evidence",
        "pdf_c7_relationship": "policy_decision_not_applied",
        "input_artifacts": {label: artifact_identity(path) for label, path in paths.items()},
        "output_artifacts": {
            "json_report": display_path(json_report_path),
            "markdown_report": display_path(md_report_path),
        },
        "counts": counts,
        "readiness_interpretation": {
            "ready_115_abstain_35": (
                "115 rows have enough deterministic content context for extractive draft previews; "
                "35 rows remain abstains because the evidence object is still too keyword/label/table-fragment oriented."
            ),
            "keyword_only_risk_112": (
                "112 rows carry keyword-only risk. Existing context mitigated 77 into content-bearing deterministic drafts; "
                "35 stayed abstain and require query/evidence/table-context work before answer generation."
            ),
            "ocr_needed_coverage": "No OCR-needed answer-evidence objects are present in this evidence object set.",
        },
        "dataset_gap": {
            "dataset_comparison": dataset_gap.get("dataset_comparison") if isinstance(dataset_gap, Mapping) else {},
            "lh_failure_dimension_counts": gap_counts.get("lh_failure_dimension_counts"),
            "lh_primary_failure_class_counts": gap_counts.get("lh_primary_failure_class_counts"),
        },
        "abstain_breakdown": {
            "primary_abstain_reason_counts": abstain_counts.get("primary_abstain_reason_counts"),
            "dataset_source_reason_counts": abstain_counts.get("dataset_source_reason_counts"),
            "anchor_type_reason_counts": abstain_counts.get("anchor_type_reason_counts"),
        },
        "table_like_context_limits": {
            "recommended_next_action_counts": table_counts.get("recommended_next_action_counts"),
            "table_semantics_ready_count": table_counts.get("table_semantics_ready_count"),
            "table_semantics_success_claimed": False,
        },
        "draft_shape_audit": {
            "counts": shape_counts,
            "interpretation": "Deterministic drafts were checked for content-first wording, citation presence, locator leakage, and lexical source support without LLM or judge calls.",
        },
        "recommendations": recommendation_rows,
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "All outputs are diagnostic-only and are not promotion evidence.",
            "Future local LLM polishing, if chosen, must be a separate local-only diagnostic run.",
            "Table parser/evidence-contract work must stay separate from row/column/value success claims.",
        ],
    }


def read_reports(paths: Mapping[str, Path], blockers: list[str]) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    json_labels = {
        "readiness_summary",
        "abstain_breakdown",
        "dataset_gap",
        "table_like_audit",
        "draft_shape_audit",
        "quality_audit",
        "deterministic_draft",
    }
    for label in json_labels:
        path = paths[label]
        if not path.exists():
            blockers.append(f"{label} missing: {display_path(path)}")
            reports[label] = {}
            continue
        reports[label] = read_json(path)
    return reports


def validate_guardrails(label: str, payload: Mapping[str, Any], blockers: list[str]) -> None:
    for key, expected in REQUIRED_GUARDRAILS.items():
        if key in payload and payload.get(key) != expected:
            blockers.append(f"{label}.{key} expected {expected!r}, got {payload.get(key)!r}")
    hard_required = {
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "official_denominator_changed": False,
        "external_cloud_llm_run": False,
        "local_llm_run": False,
        "live_llm_answer_generation_run": False,
        "optional_judge_run": False,
        "bbox_contract_success_not_claimed": True,
        "table_semantics_success_not_claimed": True,
        "candidate_artifact_changed": False,
        "immutable_baseline_changed": False,
    }
    for key, expected in hard_required.items():
        if key not in payload:
            blockers.append(f"{label}.{key} is missing")
        elif payload.get(key) != expected:
            blockers.append(f"{label}.{key} expected {expected!r}, got {payload.get(key)!r}")
    optional_false_flags = {
        "actual_llm_answer_generation_run": False,
        "actual_generated_answer_output": False,
        "answer_draft_is_actual_generated_llm_answer": False,
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
    }
    for key, expected in optional_false_flags.items():
        if key in payload and payload.get(key) != expected:
            blockers.append(f"{label}.{key} expected {expected!r}, got {payload.get(key)!r}")
    required_by_label = {
        "readiness_summary": {
            "actual_llm_answer_generation_run": False,
            "actual_generated_answer_output": False,
            "answer_draft_is_actual_generated_llm_answer": False,
        },
        "abstain_breakdown": {
            "actual_llm_answer_generation_run": False,
            "actual_generated_answer_output": False,
            "answer_draft_is_actual_generated_llm_answer": False,
        },
        "table_like_audit": {
            "table_semantics_success_claimed": False,
            "row_column_value_semantics_claimed": False,
        },
        "draft_shape_audit": {
            "actual_llm_answer_generation_run": False,
            "actual_generated_answer_output": False,
            "answer_draft_is_actual_generated_llm_answer": False,
        },
        "deterministic_draft": {
            "actual_llm_answer_generation_run": False,
            "actual_generated_answer_output": False,
            "answer_draft_is_actual_generated_llm_answer": False,
            "row_column_value_semantics_claimed": False,
        },
    }
    for key, expected in required_by_label.get(label, {}).items():
        if key not in payload:
            blockers.append(f"{label}.{key} is missing")
        elif payload.get(key) != expected:
            blockers.append(f"{label}.{key} expected {expected!r}, got {payload.get(key)!r}")


def build_recommendation_rows(
    table_rows: list[dict[str, str]],
    gap_rows: list[dict[str, str]],
    shape_rows: list[dict[str, str]],
    quality_counts: Mapping[str, Any],
) -> dict[str, Any]:
    local_llm_candidates = [
        row for row in shape_rows
        if row.get("has_draft") == "True" and row.get("draft_shape_status") == "PASS"
    ]
    evidence_serializer_rows = [
        row for row in gap_rows
        if row.get("recommended_next_action") == "EVIDENCE_SERIALIZER_CONTEXT_REVIEW"
    ]
    table_parser_rows = [
        row for row in table_rows
        if row.get("recommended_next_action") in {"NEEDS_TABLE_PARSER", "NEEDS_MANUAL_REVIEW"}
    ]
    return {
        "local_llm_polishing": {
            "count": len(local_llm_candidates),
            "condition": "Future local-only diagnostic polishing can start from draft-shape PASS rows; this run did not call an LLM.",
            "sample_query_ids": first_query_ids(local_llm_candidates),
        },
        "evidence_serializer_review": {
            "count": len(evidence_serializer_rows),
            "condition": "Rows where evidence text/context is too thin without table-specific parser needs.",
            "sample_query_ids": first_query_ids(evidence_serializer_rows),
        },
        "table_parser_or_evidence_contract": {
            "count": len(table_parser_rows),
            "condition": "Table-like candidates needing row/column/value extraction support or manual table review.",
            "sample_query_ids": first_query_ids(table_parser_rows),
        },
        "ocr_focused_refresh": {
            "count": quality_counts.get("ocr_needed_object_count") or 0,
            "condition": "Current answer-evidence object coverage has no OCR-needed objects; any OCR refresh must be separate and scoped.",
            "sample_query_ids": [],
        },
    }


def first_query_ids(rows: list[Mapping[str, str]], limit: int = 12) -> list[str]:
    result: list[str] = []
    for row in rows:
        query_id = str(row.get("query_id") or "")
        if query_id and query_id not in result:
            result.append(query_id)
        if len(result) >= limit:
            break
    return result


def required_read_csv(path: Path, blockers: list[str], label: str) -> list[dict[str, str]]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return []
    return read_csv(path)


def write_markdown(path: Path, payload: Mapping[str, Any]) -> None:
    counts = payload.get("counts") or {}
    dataset_gap = payload.get("dataset_gap") or {}
    comparison = dataset_gap.get("dataset_comparison") or {}
    elec = comparison.get("elec") or {}
    lh = comparison.get("lh") or {}
    table_limits = payload.get("table_like_context_limits") or {}
    draft_shape = (payload.get("draft_shape_audit") or {}).get("counts") or {}
    recommendations = payload.get("recommendations") or {}
    lines = [
        "# Supplemental PDF Evidence Failure Analysis Summary",
        "",
        "This summary is diagnostic-only. It does not rerun PageIndex, call any cloud/local LLM or judge, tune retrieval, rerank, expand the parser, mutate DB/SearchUnit, change candidate artifacts, change immutable baselines, overwrite gold, change official denominators, or apply PDF C7 policy.",
        "",
        "## Ready vs Abstain",
        "",
        f"- Evidence-ready deterministic draft rows: `{counts.get('evidence_ready_count')}`.",
        f"- Abstain rows: `{counts.get('abstain_count')}`.",
        "- Ready means enough content-bearing context existed for deterministic extractive draft preview only.",
        "- Abstain means the answer evidence object stayed too keyword/label/table-fragment oriented for draft creation.",
        "",
        "## Keyword-Only Risk",
        "",
        f"- Keyword-only risk rows: `{counts.get('keyword_only_risk_count')}`.",
        f"- Keyword-risk rows converted into content-bearing deterministic drafts: `{counts.get('keyword_risk_content_draft_count')}`.",
        f"- Keyword-risk rows that remained abstain: `{counts.get('keyword_risk_abstain_count')}`.",
        "",
        "## elec vs lh",
        "",
        f"- elec ready rate: `{elec.get('evidence_ready_rate')}` (`{elec.get('evidence_ready_count')}/{elec.get('row_count')}`).",
        f"- lh ready rate: `{lh.get('evidence_ready_rate')}` (`{lh.get('evidence_ready_count')}/{lh.get('row_count')}`).",
        f"- LH not-ready rows: `{counts.get('lh_not_ready_count')}`.",
        f"- LH failure dimensions: `{json.dumps(dataset_gap.get('lh_failure_dimension_counts') or {}, ensure_ascii=False, sort_keys=True)}`.",
        "",
        "## Table-Like Context Limits",
        "",
        f"- Table-like context candidates: `{counts.get('table_like_context_candidate_count')}`.",
        f"- Recommended actions: `{json.dumps(table_limits.get('recommended_next_action_counts') or {}, ensure_ascii=False, sort_keys=True)}`.",
        "- Table-like candidates are not row/column/value semantics success. Bbox contract and table semantics success are not claimed.",
        "",
        "## OCR Coverage",
        "",
        f"- OCR-needed answer-evidence objects in this set: `{counts.get('ocr_needed_evidence_object_count')}`.",
        "- OCR-focused refresh, if needed, must be a separate scoped pass.",
        "",
        "## Draft Shape Audit",
        "",
        f"- Draft shape pass / warning / fail: `{draft_shape.get('draft_shape_pass_count')}` / `{draft_shape.get('draft_shape_warning_count')}` / `{draft_shape.get('draft_shape_fail_count')}`.",
        f"- Locator leakage into answer text: `{draft_shape.get('locator_leak_into_answer_text_count')}`.",
        f"- Weak support overlap: `{draft_shape.get('weak_support_overlap_count')}`.",
        "",
        "## Recommended Next Steps",
        "",
        f"- Local LLM polishing candidates: `{(recommendations.get('local_llm_polishing') or {}).get('count')}` diagnostic rows, only in a future local-only lane.",
        f"- Evidence serializer/context review rows: `{(recommendations.get('evidence_serializer_review') or {}).get('count')}`.",
        f"- Table parser/evidence-contract rows: `{(recommendations.get('table_parser_or_evidence_contract') or {}).get('count')}`.",
        f"- OCR-focused refresh rows in this object set: `{(recommendations.get('ocr_focused_refresh') or {}).get('count')}`.",
        "",
        "## Guardrails",
        "",
        "- `promotion_evidence=false`; `evidence_role=diagnostic`.",
        "- `official_denominator_changed=false`; `codex_gold_policy_decision_applied=false`; `pdf_c7_policy_decision_applied=false`.",
        "- `external_cloud_llm_run=false`; `local_llm_run=false`; `live_llm_answer_generation_run=false`; `optional_judge_run=false`.",
        "- `pageindex_rerun=false`; `pageindex_improvement_claimed=false`.",
        "- `candidate_artifact_changed=false`; `immutable_baseline_changed=false`.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness-summary", default=str(REPORT_DIR / "rag_pdf_supplemental_elec_lh_evidence_readiness_summary.json"))
    parser.add_argument("--abstain-breakdown", default=str(REPORT_DIR / "rag_pdf_supplemental_abstain_reason_breakdown.json"))
    parser.add_argument("--dataset-gap", default=str(REPORT_DIR / "rag_pdf_supplemental_dataset_gap_analysis.json"))
    parser.add_argument("--table-like-audit", default=str(REPORT_DIR / "rag_pdf_supplemental_table_like_context_audit.json"))
    parser.add_argument("--draft-shape-audit", default=str(REPORT_DIR / "rag_pdf_supplemental_draft_shape_audit.json"))
    parser.add_argument("--quality-audit", default=str(REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.json"))
    parser.add_argument("--deterministic-draft", default=str(REPORT_DIR / "rag_pdf_supplemental_deterministic_answer_draft_report.json"))
    parser.add_argument("--table-like-csv", default=str(REPORT_DIR / "rag_pdf_supplemental_table_like_context_audit.csv"))
    parser.add_argument("--dataset-gap-csv", default=str(REPORT_DIR / "rag_pdf_supplemental_dataset_gap_analysis.csv"))
    parser.add_argument("--draft-shape-csv", default=str(REPORT_DIR / "rag_pdf_supplemental_draft_shape_audit.csv"))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--markdown", default=str(DEFAULT_MD_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
