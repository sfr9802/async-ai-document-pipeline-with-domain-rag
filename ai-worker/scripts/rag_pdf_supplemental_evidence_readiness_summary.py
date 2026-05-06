"""Write supplemental PDF evidence-readiness summary reports.

This is a diagnostic-only summary. It composes existing inventory, parse,
anchor, PageIndex, evidence, quality, leakage, and draft reports without
mutating gold, denominators, DB, SearchUnit, candidate artifacts, or baselines.
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


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_elec_lh_evidence_readiness_summary.json"
DEFAULT_MD_REPORT = REPORT_DIR / "rag_pdf_supplemental_elec_lh_evidence_readiness_summary.md"

REQUIRED_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "local_llm_run": False,
    "pageindex_improvement_claimed": False,
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = {
        "inventory": resolve_path(args.inventory_report),
        "parse": resolve_path(args.parse_report),
        "anchor": resolve_path(args.anchor_report),
        "pageindex": resolve_path(args.pageindex_report),
        "answer_evidence": resolve_path(args.answer_evidence_report),
        "quality_audit": resolve_path(args.quality_audit_report),
        "leakage_audit": resolve_path(args.leakage_audit_report),
        "draft": resolve_path(args.draft_report),
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
    reports: dict[str, dict[str, Any]] = {}
    for label, path in paths.items():
        if not path.exists():
            blockers.append(f"{label} report missing: {display_path(path)}")
            reports[label] = {}
            continue
        reports[label] = read_json(path)
        validate_guardrails(label, reports[label], blockers)
        source_status = str(reports[label].get("status") or "")
        if source_status.startswith("FAIL") or "ERROR" in source_status:
            blockers.append(f"{label}.status is fail-closed: {source_status}")
        source_blockers = reports[label].get("blockers")
        if isinstance(source_blockers, list) and source_blockers:
            blockers.append(f"{label}.blockers must be empty: {source_blockers}")
    counts = {label: (reports.get(label) or {}).get("counts") or {} for label in paths}
    quality_counts = counts.get("quality_audit") or {}
    draft_counts = counts.get("draft") or {}
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and quality_counts.get("keyword_only_risk_count"):
        status = "PASS_WITH_DIAGNOSTIC_RISKS"
    return {
        "schema_version": "pdf_supplemental_elec_lh_evidence_readiness_summary_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "supplemental_dataset_role": "answer_evidence_readiness_diagnostic_only",
        "actual_generated_answer_output": False,
        "actual_llm_answer_generation_run": False,
        "deterministic_answer_draft_only": True,
        "answer_draft_is_actual_generated_llm_answer": False,
        "official_denominator_relationship": "unchanged_and_separate",
        "promotion_relationship": "not_promotion_evidence",
        "pdf_c7_relationship": "policy_decision_not_applied",
        "source_reports": {label: artifact_identity(path) for label, path in paths.items()},
        "output_artifacts": {
            "json_report": display_path(json_report_path),
            "markdown_report": display_path(md_report_path),
        },
        "counts": counts,
        "readiness_highlights": {
            "answer_allowed_count": quality_counts.get("answer_allowed_count"),
            "evidence_ready_count": quality_counts.get("evidence_ready_count"),
            "answer_evidence_ready_rate": quality_counts.get("answer_evidence_ready_rate"),
            "native_text_object_count": quality_counts.get("native_text_object_count"),
            "native_text_ready_rate": quality_counts.get("native_text_ready_rate"),
            "ocr_needed_object_count": quality_counts.get("ocr_needed_object_count"),
            "ocr_needed_ready_rate": quality_counts.get("ocr_needed_ready_rate"),
            "elec_ready_rate": quality_counts.get("elec_ready_rate"),
            "lh_ready_rate": quality_counts.get("lh_ready_rate"),
            "keyword_only_risk_count": quality_counts.get("keyword_only_risk_count"),
            "locator_only_object_count": quality_counts.get("locator_only_object_count"),
            "table_like_context_candidate_count": quality_counts.get("table_like_context_candidate_count"),
            "draft_created_count": draft_counts.get("draft_created_count"),
            "abstained_count": draft_counts.get("abstained_count"),
        },
        "interpretation": {
            "native_vs_ocr": (
                "Readiness is separated by source PDF profile. OCR-needed rows are lower-trust diagnostics; "
                "a null OCR-needed ready rate means no OCR-needed answer-evidence object was present in this object set."
            ),
            "table_like_limit": "table_like_context_candidate is not row/column/value extraction success.",
            "keyword_location_only_risk": "keyword-only and locator-only risks block or qualify readiness before draft creation.",
            "llm_answer_generation": "No live/cloud/local LLM answer generation or optional judge run was executed.",
            "denominator_and_c7": "Official denominators, promotion gates, and PDF C7 policy decisions remain separate and unchanged.",
        },
        "recommendations": [
            "Manually review synthetic anchor surfaces before any gold or denominator decision.",
            "Use the quality audit rows to prioritize keyword-only cases where nearby context is still thin.",
            "Treat table-like candidates as parser/context work items, not as proven table semantics.",
            "If OCR-needed PDFs need coverage, create a separate scoped pass that regenerates evidence objects from the OCR-fallback parse output.",
            "Keep any future LLM answer-generation diagnostic separate from this deterministic draft report.",
        ],
        "blockers": blockers,
        "warnings": warnings,
    }


def validate_guardrails(label: str, payload: Mapping[str, Any], blockers: list[str]) -> None:
    for key, expected in COMMON_GUARDRAILS.items():
        if key not in payload:
            blockers.append(f"{label}.{key} is missing")
        elif payload.get(key) != expected:
            blockers.append(f"{label}.{key} expected {expected!r}, got {payload.get(key)!r}")
    extra_required_by_label = {
        "answer_evidence": ["local_llm_run"],
        "quality_audit": ["local_llm_run", "pageindex_improvement_claimed"],
        "leakage_audit": ["local_llm_run", "pageindex_improvement_claimed"],
        "draft": ["local_llm_run", "pageindex_improvement_claimed"],
        "pageindex": ["pageindex_improvement_claimed"],
    }
    for key in extra_required_by_label.get(label, []):
        expected = REQUIRED_GUARDRAILS[key]
        if key not in payload:
            blockers.append(f"{label}.{key} is missing")
        elif payload.get(key) != expected:
            blockers.append(f"{label}.{key} expected {expected!r}, got {payload.get(key)!r}")


def write_markdown(path: Path, payload: Mapping[str, Any]) -> None:
    counts = payload.get("counts") or {}
    inventory = counts.get("inventory") or {}
    parse = counts.get("parse") or {}
    anchor = counts.get("anchor") or {}
    pageindex = counts.get("pageindex") or {}
    evidence = counts.get("answer_evidence") or {}
    quality = counts.get("quality_audit") or {}
    leakage = counts.get("leakage_audit") or {}
    draft = counts.get("draft") or {}
    highlights = payload.get("readiness_highlights") or {}
    lines = [
        "# Supplemental elec/lh PDF Evidence Readiness Summary",
        "",
        "This summary is diagnostic-only. It does not change official denominators, apply PDF C7 policy decisions, create promotion evidence, run PageIndex again, or run live/cloud/local LLM answer generation.",
        "",
        "## Inputs And Coverage",
        "",
        f"- Supplemental PDFs: `{inventory.get('pdf_count')}` (`elec/lh={json.dumps(inventory.get('dataset_source_pdf_counts') or {}, ensure_ascii=False, sort_keys=True)}`)",
        f"- Parse success: `{parse.get('parse_success_count')}` / `{parse.get('pdf_count')}`",
        f"- Parsed pages / blocks: `{parse.get('page_count_total')}` / `{parse.get('block_count_total')}`",
        f"- Synthetic diagnostic anchors: `{anchor.get('synthetic_anchor_count')}`",
        f"- Existing answer-evidence objects: `{evidence.get('evidence_object_count')}`",
        f"- PageIndex live/local run: `{pageindex.get('live_pageindex_run')}` / `{pageindex.get('local_pageindex_run')}`",
        "",
        "## Evidence Readiness",
        "",
        f"- Answer allowed objects: `{highlights.get('answer_allowed_count')}`",
        f"- Evidence-ready objects: `{highlights.get('evidence_ready_count')}`",
        f"- Evidence readiness rate: `{highlights.get('answer_evidence_ready_rate')}`",
        f"- Native-text objects / ready rate: `{highlights.get('native_text_object_count')}` / `{highlights.get('native_text_ready_rate')}`",
        f"- OCR-needed objects / ready rate: `{fmt_value(highlights.get('ocr_needed_object_count'))}` / `{fmt_value(highlights.get('ocr_needed_ready_rate'))}`",
        f"- elec / lh ready rate: `{highlights.get('elec_ready_rate')}` / `{highlights.get('lh_ready_rate')}`",
        "",
        "## Keyword And Location Risks",
        "",
        f"- Keyword-only risk count: `{quality.get('keyword_only_risk_count')}`",
        f"- Locator-only object count: `{quality.get('locator_only_object_count')}`",
        f"- Page-only / bbox-only risk count: `{quality.get('page_only_risk_count')}` / `{quality.get('bbox_only_risk_count')}`",
        f"- Paragraph / section / nearby context count: `{quality.get('paragraph_context_present_count')}` / `{quality.get('section_context_present_count')}` / `{quality.get('nearby_context_present_count')}`",
        "",
        "## Query Surface Leakage",
        "",
        f"- Exact anchor in query: `{leakage.get('exact_anchor_in_query_count')}`",
        f"- High anchor overlap: `{leakage.get('high_anchor_overlap_count')}`",
        f"- Query same as block excerpt: `{leakage.get('query_same_as_block_excerpt_count')}`",
        f"- Difficulty counts: `{json.dumps(leakage.get('difficulty_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Deterministic Drafts",
        "",
        f"- Drafts created: `{draft.get('draft_created_count')}`",
        f"- Abstained: `{draft.get('abstained_count')}`",
        f"- Keyword echo prevented: `{draft.get('keyword_echo_prevented_count')}`",
        "- Drafts are extractive deterministic previews, not actual generated LLM answers.",
        "- Page and bbox stay in citation fields; answer text starts from content.",
        "",
        "## Limits",
        "",
        "- Table-like contexts are candidates only; row, column, value, and table semantics success are not claimed.",
        "- OCR-needed evidence is lower-trust diagnostic context and remains separate from native text.",
        "- PageIndex improvement is not claimed because this task did not rerun PageIndex.",
        "- Official denominator, promotion, and PDF C7 policy decisions are unchanged and separate.",
        "",
        "## Recommended Next Steps",
        "",
        "- Review high keyword-only risk rows and decide whether query surfaces need manual rewriting before any gold discussion.",
        "- Run a separate OCR-focused evidence-object refresh only if OCR-needed PDFs need answer evidence coverage.",
        "- Keep table-context extraction as a separate parser/evidence contract task before claiming table semantics.",
        "- Treat any future LLM answer-generation run as a new diagnostic lane with its own report flags.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-report", default=str(REPORT_DIR / "rag_pdf_supplemental_elec_lh_inventory.json"))
    parser.add_argument("--parse-report", default=str(REPORT_DIR / "rag_pdf_supplemental_parse_canary_report.json"))
    parser.add_argument("--anchor-report", default=str(REPORT_DIR / "rag_pdf_supplemental_anchor_query_build_report.json"))
    parser.add_argument("--pageindex-report", default=str(REPORT_DIR / "rag_pdf_supplemental_pageindex_diagnostic_report.json"))
    parser.add_argument("--answer-evidence-report", default=str(REPORT_DIR / "rag_pdf_supplemental_answer_evidence_diagnostic_report.json"))
    parser.add_argument("--quality-audit-report", default=str(REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.json"))
    parser.add_argument("--leakage-audit-report", default=str(REPORT_DIR / "rag_pdf_supplemental_anchor_query_leakage_audit.json"))
    parser.add_argument("--draft-report", default=str(REPORT_DIR / "rag_pdf_supplemental_deterministic_answer_draft_report.json"))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--markdown", default=str(DEFAULT_MD_REPORT))
    return parser.parse_args(argv)


def fmt_value(value: Any) -> str:
    if value is None:
        return "null"
    return str(value)


if __name__ == "__main__":
    sys.exit(main())
