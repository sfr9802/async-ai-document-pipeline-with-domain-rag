"""Build synthetic diagnostic anchor queries from supplemental parsed PDF blocks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from rag_pdf_supplemental_common import (
    COMMON_GUARDRAILS,
    EVAL_QUERIES_DIR,
    REPORT_DIR,
    REVIEW_DIR,
    artifact_identity,
    bbox_key,
    display_path,
    iter_jsonl,
    latest_supplemental_artifact_dir,
    protected_source_blockers,
    protected_source_status,
    read_json,
    resolve_path,
    short_text,
    sorted_counter,
    supplemental_output_path_blockers,
    supplemental_output_path_findings,
    utc_timestamp,
    write_csv,
    write_json,
)


DEFAULT_QUERY_CSV = EVAL_QUERIES_DIR / "gold_queries_pdf_supplemental_elec_lh_synthetic_diagnostic.csv"
DEFAULT_REVIEW_CSV = REVIEW_DIR / "pdf_supplemental_anchor_review_pack.csv"
DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_anchor_query_build_report.json"

CSV_FIELDS = [
    "query_id",
    "dataset_source",
    "file_name",
    "relative_path",
    "query",
    "anchor_text",
    "anchor_type",
    "expected_location_type",
    "parser_derived_page_no",
    "parser_derived_physical_page_index",
    "parser_derived_bbox",
    "parser_derived_section_title",
    "parser_derived_block_text_excerpt",
    "synthetic_diagnostic",
    "label_status",
    "promotion_evidence",
    "user_gold_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_evidence_policy",
    "user_denominator_policy",
    "user_issue_tags",
    "user_notes",
]

ANCHOR_PRIORITY = {
    "table_like_block": 0,
    "section_title_candidate": 1,
    "paragraph_candidate": 2,
    "semantic_anchor_candidate": 3,
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = resolve_artifact_dir(args.artifact_dir)
    parsed_blocks_path = resolve_path(args.parsed_blocks) if args.parsed_blocks else artifact_dir / "parsed_blocks.jsonl"
    parse_report_path = resolve_path(args.parse_report) if args.parse_report else REPORT_DIR / "rag_pdf_supplemental_parse_canary_report.json"
    query_csv_path = resolve_path(args.query_csv)
    review_csv_path = resolve_path(args.review_csv)
    report_path = resolve_path(args.report)
    parse_report = read_json(parse_report_path) if parse_report_path.exists() else {}
    output_path_findings = supplemental_output_path_findings({
        "query_csv": query_csv_path,
        "review_csv": review_csv_path,
        "json_report": report_path,
    })

    payload = build_anchor_queries(
        parsed_blocks_path=parsed_blocks_path,
        parse_report=parse_report,
        parse_report_path=parse_report_path,
        query_csv_path=query_csv_path,
        review_csv_path=review_csv_path,
        report_path=report_path,
        output_path_blockers=supplemental_output_path_blockers({
            "query_csv": query_csv_path,
            "review_csv": review_csv_path,
            "json_report": report_path,
        }),
        output_path_findings=output_path_findings,
        max_anchors_per_pdf=args.max_anchors_per_pdf,
        max_total_anchors=args.max_total_anchors,
    )
    unsafe_outputs = set(output_path_findings)
    if "query_csv" not in unsafe_outputs:
        write_csv(query_csv_path, payload["rows"], CSV_FIELDS)
    if "review_csv" not in unsafe_outputs:
        write_csv(review_csv_path, payload["rows"], CSV_FIELDS)
    if "json_report" not in unsafe_outputs:
        write_json(report_path, payload["report"])
    print(json.dumps({
        "status": payload["report"]["status"],
        "query_csv": display_path(query_csv_path),
        "review_csv": display_path(review_csv_path),
        "report": display_path(report_path),
        "counts": payload["report"]["counts"],
        "blockers": payload["report"]["blockers"],
    }, ensure_ascii=False, indent=2))
    return 0 if not payload["report"]["blockers"] else 2


def build_anchor_queries(
    *,
    parsed_blocks_path: Path,
    parse_report: Mapping[str, Any],
    parse_report_path: Path,
    query_csv_path: Path,
    review_csv_path: Path,
    report_path: Path,
    output_path_blockers: list[str],
    output_path_findings: Mapping[str, list[str]],
    max_anchors_per_pdf: int,
    max_total_anchors: int,
) -> dict[str, Any]:
    blockers: list[str] = list(output_path_blockers)
    warnings: list[str] = []
    blockers.extend(protected_source_blockers())
    if parse_report and parse_report.get("promotion_evidence") is not False:
        blockers.append("parse report must keep promotion_evidence=false")
    if not parsed_blocks_path.exists():
        blockers.append(f"parsed blocks JSONL missing: {display_path(parsed_blocks_path)}")
        blocks: list[dict[str, Any]] = []
    else:
        blocks = [row for row in iter_jsonl(parsed_blocks_path) if str(row.get("text") or "").strip()]
    if not blocks:
        blockers.append("No parsed text blocks available for synthetic anchors.")

    section_titles = build_section_title_index(blocks)
    by_pdf: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for block in blocks:
        by_pdf[str(block.get("sha256") or block.get("relative_path") or "")].append(block)

    rows: list[dict[str, Any]] = []
    for group_blocks in by_pdf.values():
        candidates = sorted(
            [candidate for block in group_blocks if (candidate := classify_anchor(block))],
            key=lambda item: (
                ANCHOR_PRIORITY.get(str(item["anchor_type"]), 99),
                -int(item.get("score") or 0),
                int(item["block"].get("page_no") or 10**9),
                int(item["block"].get("block_index") or 10**9),
            ),
        )
        selected = diversify_candidates(candidates, max_anchors_per_pdf)
        for item in selected:
            if len(rows) >= max_total_anchors:
                break
            rows.append(anchor_row(item["block"], item["anchor_type"], section_titles, len(rows) + 1))
        if len(rows) >= max_total_anchors:
            break

    anchor_counts = Counter(row["anchor_type"] for row in rows)
    source_counts = Counter(row["dataset_source"] for row in rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    report = {
        "schema_version": "pdf_supplemental_anchor_query_build_report_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **COMMON_GUARDRAILS,
        "anchor_generation_mode": "deterministic_parser_derived_synthetic",
        "query_gold_status": "diagnostic_only",
        "synthetic_rows_are_gold": False,
        "existing_gold_csv_overwritten": False,
        "protected_gold_sources_mutated": False,
        "protected_source_hashes": protected_source_status(),
        "output_path_findings": dict(output_path_findings),
        "input_artifacts": [artifact_identity(parsed_blocks_path), artifact_identity(parse_report_path)],
        "output_artifacts": {
            "query_csv": display_path(query_csv_path),
            "review_pack_csv": display_path(review_csv_path),
            "json_report": display_path(report_path),
        },
        "counts": {
            "parsed_block_count": len(blocks),
            "synthetic_anchor_count": len(rows),
            "max_anchors_per_pdf": max_anchors_per_pdf,
            "max_total_anchors": max_total_anchors,
            "anchor_type_counts": sorted_counter(anchor_counts),
            "dataset_source_counts": sorted_counter(source_counts),
            "diagnostic_only_count": sum(1 for row in rows if row["label_status"] == "diagnostic_only"),
            "promotion_evidence_true_count": sum(1 for row in rows if row["promotion_evidence"] is not False),
            "blank_user_decision_field_count": sum(
                1 for row in rows
                if all(not row[field] for field in USER_DECISION_FIELDS)
            ),
        },
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "Synthetic anchor rows are diagnostic_only and parser-derived.",
            "Expected page and bbox are parser locators, not user-reviewed expected evidence.",
            "User decision columns are intentionally blank.",
        ],
    }
    return {"report": report, "rows": rows}


USER_DECISION_FIELDS = [
    "user_gold_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_evidence_policy",
    "user_denominator_policy",
    "user_issue_tags",
    "user_notes",
]


def classify_anchor(block: Mapping[str, Any]) -> dict[str, Any] | None:
    text = re.sub(r"\s+", " ", str(block.get("text") or "")).strip()
    if len(text) < 8:
        return None
    score = 0
    anchor_type = "semantic_anchor_candidate"
    if block.get("table_like_block_candidate"):
        anchor_type = "table_like_block"
        score += 8
    elif is_section_title_candidate(text, block):
        anchor_type = "section_title_candidate"
        score += 6
    elif len(text) >= 180:
        anchor_type = "paragraph_candidate"
        score += 5
    if re.search(r"\d", text):
        score += 2
    if re.search(r"(전기|요금|기준|계약|주택|입주|자격|공고|임대|공급|LH|한국토지)", text, re.IGNORECASE):
        score += 3
    if len(text) > 1200:
        score -= 1
    if score < 4:
        return None
    return {"block": block, "anchor_type": anchor_type, "score": score}


def is_section_title_candidate(text: str, block: Mapping[str, Any]) -> bool:
    if len(text) > 120:
        return False
    line_count = len([line for line in str(block.get("text") or "").splitlines() if line.strip()])
    if line_count > 3:
        return False
    bbox = block.get("bbox")
    y0 = bbox[1] if isinstance(bbox, list) and len(bbox) >= 2 else 999
    return bool(re.search(r"(^[0-9IVX]+[.)]|제\s*\d+\s*장|목차|요금|자격|공급|공고|기준)", text)) or y0 < 140


def diversify_candidates(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used_types: set[str] = set()
    used_pages: set[int] = set()
    for candidate in candidates:
        anchor_type = str(candidate["anchor_type"])
        page_no = int(candidate["block"].get("page_no") or -1)
        if anchor_type in used_types and page_no in used_pages:
            continue
        selected.append(candidate)
        used_types.add(anchor_type)
        used_pages.add(page_no)
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        for candidate in candidates:
            if candidate in selected:
                continue
            selected.append(candidate)
            if len(selected) >= limit:
                break
    return selected


def build_section_title_index(blocks: list[Mapping[str, Any]]) -> dict[tuple[str, int], str]:
    result: dict[tuple[str, int], str] = {}
    for block in blocks:
        text = short_text(str(block.get("text") or ""), 120)
        if not text or not is_section_title_candidate(text, block):
            continue
        key = (str(block.get("sha256") or block.get("relative_path") or ""), int(block.get("page_no") or 0))
        result.setdefault(key, text)
    return result


def anchor_row(
    block: Mapping[str, Any],
    anchor_type: str,
    section_titles: Mapping[tuple[str, int], str],
    sequence: int,
) -> dict[str, Any]:
    source = str(block.get("dataset_source") or "unknown")
    sha = str(block.get("sha256") or "")[:10]
    page_no = int(block.get("page_no") or 0)
    query_id = f"supp_{source}_{sha}_p{page_no}_{sequence:04d}"
    block_text = re.sub(r"\s+", " ", str(block.get("text") or "")).strip()
    return {
        "query_id": query_id,
        "dataset_source": source,
        "file_name": block.get("file_name"),
        "relative_path": block.get("relative_path"),
        "query": synthetic_query(source, anchor_type, block_text),
        "anchor_text": short_text(block_text, 160),
        "anchor_type": anchor_type,
        "expected_location_type": "pdf",
        "parser_derived_page_no": page_no,
        "parser_derived_physical_page_index": block.get("physical_page_index"),
        "parser_derived_bbox": block.get("bbox"),
        "parser_derived_section_title": section_titles.get((str(block.get("sha256") or block.get("relative_path") or ""), page_no), ""),
        "parser_derived_block_text_excerpt": short_text(block_text, 360),
        "synthetic_diagnostic": True,
        "label_status": "diagnostic_only",
        "promotion_evidence": False,
        "user_gold_decision": "",
        "user_answerability_label": "",
        "user_relevance_label": "",
        "user_expected_evidence_policy": "",
        "user_denominator_policy": "",
        "user_issue_tags": "",
        "user_notes": "",
    }


def synthetic_query(source: str, anchor_type: str, text: str) -> str:
    if source == "elec":
        if anchor_type == "table_like_block":
            return "이 문서에서 전기요금 기준이 표로 정리된 부분 확인해줘."
        if "주택" in text:
            return "이 문서에서 주택용 전기요금 기준이 설명된 부분 찾아줘."
        return "이 문서에서 전기요금 관련 기준이 설명된 부분 확인해줘."
    if source == "lh":
        if anchor_type == "table_like_block":
            return "LH 문서에서 조건이나 금액이 표로 정리된 부분 찾아줘."
        if re.search(r"입주|자격", text):
            return "LH 문서에서 입주자격 조건이 나오는 부분 찾아줘."
        if re.search(r"공급|공고", text):
            return "LH 문서에서 공급 공고의 주요 조건이 설명된 부분 확인해줘."
        return "LH 문서에서 신청 조건이나 안내가 설명된 부분 찾아줘."
    return "이 PDF 문서에서 주요 조건이 설명된 부분 확인해줘."


def resolve_artifact_dir(value: str | None) -> Path:
    if value:
        return resolve_path(value)
    return latest_supplemental_artifact_dir()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--parsed-blocks", default=None)
    parser.add_argument("--parse-report", default=None)
    parser.add_argument("--query-csv", default=str(DEFAULT_QUERY_CSV))
    parser.add_argument("--review-csv", default=str(DEFAULT_REVIEW_CSV))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--max-anchors-per-pdf", type=int, default=5)
    parser.add_argument("--max-total-anchors", type=int, default=220)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
