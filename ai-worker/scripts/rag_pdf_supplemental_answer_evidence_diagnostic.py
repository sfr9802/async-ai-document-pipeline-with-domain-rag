"""Build diagnostic answer-evidence objects for supplemental PDF anchors."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from rag_pdf_supplemental_common import (
    COMMON_GUARDRAILS,
    REPORT_DIR,
    artifact_identity,
    bbox_key,
    display_path,
    iter_jsonl,
    latest_supplemental_artifact_dir,
    read_csv,
    read_json,
    resolve_path,
    short_text,
    sorted_counter,
    to_int,
    truthy,
    utc_timestamp,
    write_csv,
    write_json,
    write_jsonl,
)


DEFAULT_ANCHOR_CSV = Path("eval/eval_queries/gold_queries_pdf_supplemental_elec_lh_synthetic_diagnostic.csv")
DEFAULT_PAGEINDEX_CSV = REPORT_DIR / "rag_pdf_supplemental_pageindex_diagnostic.csv"
DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_answer_evidence_diagnostic_report.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_answer_evidence_diagnostic.csv"

CSV_FIELDS = [
    "query_id",
    "dataset_source",
    "file_name",
    "relative_path",
    "answer_allowed",
    "fail_closed_reason",
    "locator_only_object",
    "paragraph_context_present",
    "section_context_present",
    "nearby_context_present",
    "table_like_context_candidate",
    "keyword_only_risk",
    "page_only_risk",
    "bbox_only_risk",
    "evidence_navigation_signal_present",
    "evidence_text_excerpt",
    "citation",
    "promotion_evidence",
    "label_status",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = resolve_artifact_dir(args.artifact_dir)
    anchors_path = resolve_path(args.anchor_csv)
    parsed_blocks_path = resolve_path(args.parsed_blocks) if args.parsed_blocks else artifact_dir / "parsed_blocks.jsonl"
    pageindex_csv_path = resolve_path(args.pageindex_csv)
    evidence_jsonl_path = resolve_path(args.evidence_jsonl) if args.evidence_jsonl else artifact_dir / "answer_evidence_objects.jsonl"
    report_path = resolve_path(args.report)
    csv_path = resolve_path(args.csv)

    anchors = read_csv(anchors_path) if anchors_path.exists() else []
    blocks = [row for row in iter_jsonl(parsed_blocks_path)] if parsed_blocks_path.exists() else []
    pageindex_rows = read_csv(pageindex_csv_path) if pageindex_csv_path.exists() else []
    payload = build_answer_evidence(
        anchors=anchors,
        blocks=blocks,
        pageindex_rows=pageindex_rows,
        anchors_path=anchors_path,
        parsed_blocks_path=parsed_blocks_path,
        pageindex_csv_path=pageindex_csv_path,
        evidence_jsonl_path=evidence_jsonl_path,
        report_path=report_path,
        csv_path=csv_path,
    )
    write_jsonl(evidence_jsonl_path, payload["evidence_rows"])
    write_json(report_path, payload["report"])
    write_csv(csv_path, payload["csv_rows"], CSV_FIELDS)
    print(json.dumps({
        "status": payload["report"]["status"],
        "json_report": display_path(report_path),
        "csv_report": display_path(csv_path),
        "evidence_jsonl": display_path(evidence_jsonl_path),
        "counts": payload["report"]["counts"],
        "blockers": payload["report"]["blockers"],
    }, ensure_ascii=False, indent=2))
    return 0 if not payload["report"]["blockers"] else 2


def build_answer_evidence(
    *,
    anchors: list[dict[str, str]],
    blocks: list[dict[str, Any]],
    pageindex_rows: list[dict[str, str]],
    anchors_path: Path,
    parsed_blocks_path: Path,
    pageindex_csv_path: Path,
    evidence_jsonl_path: Path,
    report_path: Path,
    csv_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not anchors:
        blockers.append("No synthetic anchor rows available.")
    if not blocks:
        warnings.append("Parsed block JSONL is missing or empty; evidence objects will fail closed.")
    block_index = build_block_index(blocks)
    nearby_index = build_nearby_index(blocks)
    pageindex_by_id = {str(row.get("query_id") or ""): row for row in pageindex_rows}
    evidence_rows: list[dict[str, Any]] = []
    csv_rows: list[dict[str, Any]] = []
    for anchor in anchors:
        evidence = build_evidence_row(anchor, block_index, nearby_index, pageindex_by_id)
        evidence_rows.append(evidence)
        csv_rows.append({key: evidence.get(key) for key in CSV_FIELDS})
    counts = build_counts(evidence_rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and counts["locator_only_object_count"]:
        status = "PASS_WITH_LOCATOR_ONLY_RISKS"
    report = {
        "schema_version": "pdf_supplemental_answer_evidence_diagnostic_report_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **COMMON_GUARDRAILS,
        "answer_generation_execution": "not_run_by_this_script",
        "local_llm_run": False,
        "actual_generated_answer_output": False,
        "answer_evidence_object_is_actual_answer": False,
        "input_artifacts": [
            artifact_identity(anchors_path),
            artifact_identity(parsed_blocks_path),
            artifact_identity(pageindex_csv_path),
        ],
        "output_artifacts": {
            "answer_evidence_objects_jsonl": display_path(evidence_jsonl_path),
            "json_report": display_path(report_path),
            "csv_report": display_path(csv_path),
        },
        "counts": counts,
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "Evidence objects diagnose whether content around parser anchors can support answer generation.",
            "No final answer, local LLM call, cloud LLM call, or judge run is performed.",
            "Table-like contexts remain heuristic candidates only.",
        ],
    }
    return {"report": report, "evidence_rows": evidence_rows, "csv_rows": csv_rows}


def build_block_index(blocks: list[Mapping[str, Any]]) -> dict[tuple[str, int, str], Mapping[str, Any]]:
    result: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    for block in blocks:
        key = (
            str(block.get("relative_path") or ""),
            int(block.get("page_no") or 0),
            bbox_key(block.get("bbox")),
        )
        result[key] = block
    return result


def build_nearby_index(blocks: list[Mapping[str, Any]]) -> dict[tuple[str, int], list[Mapping[str, Any]]]:
    result: dict[tuple[str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for block in blocks:
        result[(str(block.get("relative_path") or ""), int(block.get("page_no") or 0))].append(block)
    for rows in result.values():
        rows.sort(key=lambda row: int(row.get("block_index") or 0))
    return result


def build_evidence_row(
    anchor: Mapping[str, str],
    block_index: Mapping[tuple[str, int, str], Mapping[str, Any]],
    nearby_index: Mapping[tuple[str, int], list[Mapping[str, Any]]],
    pageindex_by_id: Mapping[str, Mapping[str, str]],
) -> dict[str, Any]:
    relative_path = str(anchor.get("relative_path") or "")
    page_no = to_int(anchor.get("parser_derived_page_no")) or 0
    bbox = anchor.get("parser_derived_bbox")
    block = block_index.get((relative_path, page_no, bbox_key(bbox)), {})
    block_text = str(block.get("text") or anchor.get("parser_derived_block_text_excerpt") or "").strip()
    section_title = str(anchor.get("parser_derived_section_title") or "").strip()
    nearby_context = nearby_context_for_anchor(anchor, block, nearby_index)
    paragraph_context_present = bool(block_text and len(block_text) >= 40)
    section_context_present = bool(section_title)
    nearby_context_present = bool(nearby_context)
    table_like = truthy(block.get("table_like_block_candidate")) or anchor.get("anchor_type") == "table_like_block"
    content_available = paragraph_context_present or section_context_present or nearby_context_present
    locator_available = bool(page_no or bbox)
    locator_only = bool(locator_available and not content_available)
    keyword_only_risk = bool(block_text and normalized(anchor.get("anchor_text")) == normalized(block_text) and len(block_text) < 80)
    page_only_risk = bool(page_no and not block_text and not nearby_context)
    bbox_only_risk = bool(bbox and not block_text)
    answer_allowed = bool(content_available and not locator_only)
    fail_closed_reason = "" if answer_allowed else "LOCATOR_ONLY_OR_CONTENT_CONTEXT_MISSING"
    pageindex_row = pageindex_by_id.get(str(anchor.get("query_id") or ""), {})
    navigation_signal = pageindex_signal(pageindex_row)
    evidence_text = block_text or nearby_context or section_title
    citation = {
        "source": "parser_derived_pdf_locator",
        "page_no": page_no,
        "physical_page_index": to_int(anchor.get("parser_derived_physical_page_index")),
        "bbox": anchor.get("parser_derived_bbox"),
        "relative_path": relative_path,
    }
    return {
        "schema_version": "pdf_supplemental_answer_evidence_object_v1",
        "query_id": anchor.get("query_id"),
        "dataset_source": anchor.get("dataset_source"),
        "file_name": anchor.get("file_name"),
        "relative_path": relative_path,
        "query": anchor.get("query"),
        "anchor_type": anchor.get("anchor_type"),
        "answer_allowed": answer_allowed,
        "fail_closed_reason": fail_closed_reason,
        "locator_only_object": locator_only,
        "paragraph_context_present": paragraph_context_present,
        "section_context_present": section_context_present,
        "nearby_context_present": nearby_context_present,
        "table_like_context_candidate": table_like,
        "keyword_only_risk": keyword_only_risk,
        "page_only_risk": page_only_risk,
        "bbox_only_risk": bbox_only_risk,
        "evidence_navigation_signal_present": bool(navigation_signal),
        "evidence_navigation_signal": navigation_signal,
        "evidence_text": evidence_text,
        "evidence_text_excerpt": short_text(evidence_text, 420),
        "paragraph_summary": short_text(block_text, 260) if block_text else "",
        "section_title": section_title,
        "nearby_context": nearby_context,
        "table_like_context": {
            "candidate": table_like,
            "heuristic_only": True,
            "row_column_value_semantics_claimed": False,
        },
        "citation": citation,
        "promotion_evidence": False,
        "label_status": "diagnostic_only",
        "denominator_included": False,
        **COMMON_GUARDRAILS,
    }


def nearby_context_for_anchor(
    anchor: Mapping[str, str],
    block: Mapping[str, Any],
    nearby_index: Mapping[tuple[str, int], list[Mapping[str, Any]]],
) -> str:
    relative_path = str(anchor.get("relative_path") or "")
    page_no = to_int(anchor.get("parser_derived_page_no")) or 0
    rows = list(nearby_index.get((relative_path, page_no), []))
    if not rows:
        return ""
    block_index = to_int(block.get("block_index")) if block else None
    if block_index is None:
        selected = rows[:3]
    else:
        selected = [row for row in rows if abs(int(row.get("block_index") or 0) - block_index) <= 1]
    text = " ".join(str(row.get("text") or "").strip() for row in selected if str(row.get("text") or "").strip())
    return short_text(text, 800)


def pageindex_signal(row: Mapping[str, str]) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "selected_node_id": row.get("selected_node_id"),
        "selected_node_title": row.get("selected_node_title"),
        "selected_page_range": row.get("selected_page_range"),
        "selected_contains_expected_page": truthy(row.get("selected_contains_expected_page")),
        "oracle_exists_but_navigation_missed": truthy(row.get("oracle_exists_but_navigation_missed")),
        "source": "supplemental_pageindex_diagnostic",
    }


def normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def build_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    evidence_object_count = len(rows)
    answer_allowed_count = sum(1 for row in rows if row.get("answer_allowed") is True)
    return {
        "evidence_object_count": evidence_object_count,
        "answer_allowed_count": answer_allowed_count,
        "locator_only_object_count": sum(1 for row in rows if row.get("locator_only_object") is True),
        "paragraph_context_present_count": sum(1 for row in rows if row.get("paragraph_context_present") is True),
        "section_context_present_count": sum(1 for row in rows if row.get("section_context_present") is True),
        "nearby_context_present_count": sum(1 for row in rows if row.get("nearby_context_present") is True),
        "table_like_context_candidate_count": sum(1 for row in rows if row.get("table_like_context_candidate") is True),
        "keyword_only_risk_count": sum(1 for row in rows if row.get("keyword_only_risk") is True),
        "page_only_risk_count": sum(1 for row in rows if row.get("page_only_risk") is True),
        "bbox_only_risk_count": sum(1 for row in rows if row.get("bbox_only_risk") is True),
        "answer_evidence_ready_rate": (answer_allowed_count / evidence_object_count) if evidence_object_count else 0.0,
        "answer_generation_run": False,
        "local_llm_run": False,
        "optional_judge_run": False,
        "dataset_source_counts": sorted_counter(Counter(str(row.get("dataset_source") or "unknown") for row in rows)),
    }


def resolve_artifact_dir(value: str | None) -> Path:
    if value:
        return resolve_path(value)
    return latest_supplemental_artifact_dir()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--anchor-csv", default=str(DEFAULT_ANCHOR_CSV))
    parser.add_argument("--parsed-blocks", default=None)
    parser.add_argument("--pageindex-csv", default=str(DEFAULT_PAGEINDEX_CSV))
    parser.add_argument("--evidence-jsonl", default=None)
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
