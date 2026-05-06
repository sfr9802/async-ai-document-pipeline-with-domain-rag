"""Summarize supplemental elec/lh PDF diagnostics separately from Track C gold."""

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
    protected_source_status,
    read_json,
    resolve_path,
    utc_timestamp,
    write_json,
)


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_elec_lh_summary.json"
DEFAULT_MD_REPORT = REPORT_DIR / "rag_pdf_supplemental_elec_lh_summary.md"

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = {
        "inventory": resolve_path(args.inventory_report),
        "parse": resolve_path(args.parse_report),
        "anchor": resolve_path(args.anchor_report),
        "pageindex": resolve_path(args.pageindex_report),
        "answer_evidence": resolve_path(args.answer_evidence_report),
    }
    json_report_path = resolve_path(args.report)
    md_report_path = resolve_path(args.markdown)
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
            if label == "pageindex":
                warnings.append(f"optional pageindex report missing: {display_path(path)}")
                reports[label] = {}
                continue
            blockers.append(f"{label} report missing: {display_path(path)}")
            reports[label] = {}
            continue
        reports[label] = read_json(path)
        validate_stage_guardrails(label, reports[label], blockers)
    protected = protected_hashes()
    for item in protected.values():
        if not item["exists"]:
            blockers.append(f"protected source missing: {item['path']}")
        elif not item["matches_expected"]:
            blockers.append(f"protected source hash drift: {item['path']}")
    c7 = read_optional_report(resolve_path("ai-worker/eval/reports/rag-ingestion/rag_pdf_gold_policy_review.json"))
    c7_summary = {
        "status": c7.get("status"),
        "human_decision_required_count": (c7.get("review_scope") or {}).get("failed_query_count")
        or c7.get("human_decision_required_count"),
        "policy_pending_preserved": True,
    }
    counts = {
        "inventory": (reports.get("inventory") or {}).get("counts") or {},
        "parse": (reports.get("parse") or {}).get("counts") or {},
        "anchor": (reports.get("anchor") or {}).get("counts") or {},
        "pageindex": (reports.get("pageindex") or {}).get("counts") or {},
        "answer_evidence": (reports.get("answer_evidence") or {}).get("counts") or {},
    }
    status = "PASS" if not blockers else "FAIL_CLOSED_GUARDRAIL_OR_HASH_ERROR"
    return {
        "schema_version": "pdf_supplemental_elec_lh_summary_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **COMMON_GUARDRAILS,
        "supplemental_dataset_role": "parser_pageindex_answer_evidence_diagnostic_only",
        "track_c_official_gold_expanded": False,
        "track_c_c7_policy_pending_preserved": True,
        "synthetic_anchor_rows_are_gold": False,
        "actual_generated_answer_output": False,
        "source_reports": {label: artifact_identity(path) for label, path in paths.items()},
        "output_artifacts": {
            "json_report": display_path(json_report_path),
            "markdown_report": display_path(md_report_path),
        },
        "protected_input_hashes": protected,
        "track_c_c7_relationship": c7_summary,
        "counts": counts,
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "why_not_official_denominator": [
                "elec/lh PDFs are not human-reviewed gold.",
                "Synthetic anchors are parser-derived diagnostic surfaces only.",
                "User-owned gold inclusion, answerability, relevance, and expected-evidence policy decisions remain blank.",
            ],
            "next_steps": [
                "Review synthetic anchor rows manually before any future gold inclusion decision.",
                "Use parse canary and answer-evidence readiness to decide where parser/OCR/table-context work is needed.",
                "Run supplemental PageIndex locally only with explicit local model and localhost base URL when navigation diagnostics are needed.",
            ],
        },
    }


def validate_stage_guardrails(label: str, payload: Mapping[str, Any], blockers: list[str]) -> None:
    for key, expected in COMMON_GUARDRAILS.items():
        if key in payload and payload.get(key) != expected:
            blockers.append(f"{label}.{key} expected {expected!r}, got {payload.get(key)!r}")
    if payload.get("promotion_evidence") is not False:
        blockers.append(f"{label}.promotion_evidence must be false")
    if payload.get("evidence_role") != "diagnostic":
        blockers.append(f"{label}.evidence_role must be diagnostic")


def protected_hashes() -> dict[str, dict[str, Any]]:
    return protected_source_status()


def read_optional_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return read_json(path)


def write_markdown(path: Path, payload: Mapping[str, Any]) -> None:
    counts = payload.get("counts") or {}
    inventory = counts.get("inventory") or {}
    parse = counts.get("parse") or {}
    anchor = counts.get("anchor") or {}
    pageindex = counts.get("pageindex") or {}
    evidence = counts.get("answer_evidence") or {}
    lines = [
        "# Supplemental elec/lh PDF Diagnostic Summary",
        "",
        "This report is diagnostic-only. It does not expand Track C official gold, change the denominator, apply C7 policy decisions, create promotion evidence, or run answer generation.",
        "",
        "## Dataset",
        "",
        f"- PDF count: `{inventory.get('pdf_count')}`",
        f"- elec/lh source counts: `{json.dumps(inventory.get('dataset_source_pdf_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
        f"- OCR-needed candidates: `{inventory.get('ocr_needed_candidate_count')}`",
        f"- Table-centered candidates: `{inventory.get('table_centered_pdf_count')}`",
        "",
        "## Parser Coverage",
        "",
        f"- Parse success: `{parse.get('parse_success_count')}`",
        f"- Parse failure: `{parse.get('parse_failure_count')}`",
        f"- Total pages: `{parse.get('page_count_total')}`",
        f"- Total blocks: `{parse.get('block_count_total')}`",
        f"- Table-like block candidates: `{parse.get('table_like_block_candidate_count')}`",
        "",
        "## Synthetic Anchors",
        "",
        f"- Synthetic diagnostic anchors: `{anchor.get('synthetic_anchor_count')}`",
        f"- Anchor type counts: `{json.dumps(anchor.get('anchor_type_counts') or {}, ensure_ascii=False, sort_keys=True)}`",
        "",
        "## PageIndex",
        "",
        f"- Live PageIndex run: `{pageindex.get('live_pageindex_run')}`",
        f"- Tree build success count: `{pageindex.get('tree_build_success_count')}`",
        f"- Navigation success count: `{pageindex.get('query_navigation_success_count')}`",
        f"- Oracle navigation missed count: `{pageindex.get('oracle_exists_but_navigation_missed_count')}`",
        f"- Invalid range generated count: `{pageindex.get('invalid_range_generated_count')}`",
        "",
        "## Answer Evidence",
        "",
        f"- Evidence objects: `{evidence.get('evidence_object_count')}`",
        f"- Answer allowed count: `{evidence.get('answer_allowed_count')}`",
        f"- Locator-only object count: `{evidence.get('locator_only_object_count')}`",
        f"- Answer evidence ready rate: `{evidence.get('answer_evidence_ready_rate')}`",
        "",
        "## Track C Relationship",
        "",
        "- Existing Track C PDF C7 policy-pending rows remain unresolved and user-owned.",
        "- elec/lh synthetic anchors are not official Track C denominator rows.",
        "- PageIndex remains a PDF page/section navigator candidate only.",
        "- bbox, table, value semantics, C7 resolution, promotion readiness, and actual answer quality are not claimed.",
        "",
        "## Next Steps",
        "",
        "- Manually review anchor rows before any future gold inclusion/exclusion decision.",
        "- Use parser and answer-evidence gaps to decide whether OCR fallback or table-context extraction deserves a separate scoped task.",
        "- Run local PageIndex only with explicit local model and localhost base URL when navigation evidence is needed.",
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
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--markdown", default=str(DEFAULT_MD_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
