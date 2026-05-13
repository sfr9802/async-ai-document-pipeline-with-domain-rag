"""Analyze LH supplemental PDF not-ready rows.

This is a file-based post-analysis over existing supplemental diagnostics. It
does not rerun PageIndex, call an LLM or judge, tune retrieval, rerank, expand
the parser, mutate DB/SearchUnit state, or change candidate, baseline, gold, C7,
or denominator artifacts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from rag_pdf_supplemental_common import (
    COMMON_GUARDRAILS,
    REPORT_DIR,
    artifact_identity,
    bbox_key,
    display_path,
    iter_jsonl,
    read_csv,
    resolve_path,
    short_text,
    sorted_counter,
    supplemental_output_path_blockers,
    to_int,
    truthy,
    utc_timestamp,
    write_csv,
    write_json,
)


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_lh_not_ready_analysis.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_lh_not_ready_analysis.csv"
DEFAULT_QUALITY_CSV = REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.csv"
DEFAULT_LEAKAGE_CSV = REPORT_DIR / "rag_pdf_supplemental_anchor_query_leakage_audit.csv"
DEFAULT_ABSTAIN_BREAKDOWN = REPORT_DIR / "rag_pdf_supplemental_abstain_reason_breakdown.json"
DEFAULT_DATASET_GAP = REPORT_DIR / "rag_pdf_supplemental_dataset_gap_analysis.json"

REQUIRED_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "row_column_value_semantics_claimed": False,
    "local_llm_run": False,
    "pageindex_rerun": False,
    "pageindex_improvement_claimed": False,
    "actual_llm_answer_generation_run": False,
    "actual_generated_answer_output": False,
    "answer_draft_is_actual_generated_llm_answer": False,
    "table_semantics_success_claimed": False,
}

LIKELY_FIX_LANES = [
    "QUERY_REWRITE_ONLY",
    "EVIDENCE_SERIALIZER_FIX",
    "TABLE_EVIDENCE_CONTRACT_REQUIRED",
    "OCR_REFRESH_REQUIRED",
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
    "block_text_excerpt",
    "nearby_context_excerpt",
    "section_context",
    "query_surface_issue",
    "parser_block_issue",
    "table_semantics_issue",
    "likely_fix_lane",
]

BROAD_QUERY_RE = re.compile(r"(관련 기준|표로 정리된 부분|조건이나 금액|부분 찾아줘|부분 확인해줘)")
VALUE_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
ROW_LABEL_RE = re.compile(r"[가-힣A-Za-z][^\n:：]{0,24}[:：]|\b[1-9]\s*단계\b")
COLUMN_LABEL_RE = re.compile(
    r"(구분|항목|사용량|기본|전력량|요금|금액|단가|임대료|보증금|면적|세대|소득|기간|월|하계|동계|기타|전용|공급|조건)"
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = resolve_artifact_dir(args.artifact_dir)
    evidence_path = resolve_path(args.evidence_jsonl) if args.evidence_jsonl else artifact_dir / "answer_evidence_objects.jsonl"
    draft_path = resolve_path(args.draft_jsonl) if args.draft_jsonl else artifact_dir / "deterministic_answer_drafts.jsonl"
    parsed_blocks_path = resolve_path(args.parsed_blocks) if args.parsed_blocks else artifact_dir / "parsed_blocks.jsonl"
    quality_csv_path = resolve_path(args.quality_csv)
    leakage_csv_path = resolve_path(args.leakage_csv)
    abstain_breakdown_path = resolve_path(args.abstain_breakdown)
    dataset_gap_path = resolve_path(args.dataset_gap)
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

    payload = build_analysis(
        artifact_dir=artifact_dir,
        evidence_path=evidence_path,
        draft_path=draft_path,
        parsed_blocks_path=parsed_blocks_path,
        quality_csv_path=quality_csv_path,
        leakage_csv_path=leakage_csv_path,
        abstain_breakdown_path=abstain_breakdown_path,
        dataset_gap_path=dataset_gap_path,
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


def build_analysis(
    *,
    artifact_dir: Path,
    evidence_path: Path,
    draft_path: Path,
    parsed_blocks_path: Path,
    quality_csv_path: Path,
    leakage_csv_path: Path,
    abstain_breakdown_path: Path,
    dataset_gap_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    evidence_rows = read_jsonl_or_block(evidence_path, "answer evidence JSONL", blockers)
    draft_rows = read_jsonl_or_block(draft_path, "deterministic draft JSONL", blockers)
    parsed_blocks = read_jsonl_or_block(parsed_blocks_path, "parsed blocks JSONL", blockers)
    quality_rows = read_csv_or_block(quality_csv_path, "quality audit CSV", blockers)
    leakage_by_id = read_csv_by_id(leakage_csv_path, "leakage audit CSV", warnings)
    evidence_by_id = {str(row.get("query_id") or ""): row for row in evidence_rows}
    draft_by_id = {str(row.get("query_id") or ""): row for row in draft_rows}
    block_index = build_block_index(parsed_blocks)

    rows: list[dict[str, Any]] = []
    for quality in quality_rows:
        if str(quality.get("dataset_source") or "") != "lh":
            continue
        query_id = str(quality.get("query_id") or "")
        draft = draft_by_id.get(query_id, {})
        abstain_reason = str(draft.get("abstain_reason") or "")
        if truthy(quality.get("evidence_ready")) and not abstain_reason:
            continue
        rows.append(analyze_row(
            quality,
            evidence_by_id.get(query_id, {}),
            draft,
            leakage_by_id.get(query_id, {}),
            block_index,
        ))

    counts = build_counts(rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and rows:
        status = "PASS_WITH_LH_NOT_READY_ANALYSIS"
    report = {
        "schema_version": "pdf_supplemental_lh_not_ready_analysis_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "diagnostic_lh_not_ready_row_decomposition_only",
        "likely_fix_lane_enum": LIKELY_FIX_LANES,
        "input_artifacts": [
            artifact_identity(evidence_path),
            artifact_identity(draft_path),
            artifact_identity(parsed_blocks_path),
            artifact_identity(quality_csv_path),
            artifact_identity(leakage_csv_path),
            artifact_identity(abstain_breakdown_path),
            artifact_identity(dataset_gap_path),
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
            "LH not-ready rows are selected from dataset_source=lh with evidence_ready=false or deterministic abstain.",
            "query_surface_issue, parser_block_issue, and table_semantics_issue are diagnostic causes, not parser or answer-quality changes.",
            "TABLE_EVIDENCE_CONTRACT_REQUIRED means row/column/value evidence is missing or ambiguous; it is not table-semantics success.",
        ],
    }
    return {"report": report, "rows": rows}


def analyze_row(
    quality: Mapping[str, str],
    evidence: Mapping[str, Any],
    draft: Mapping[str, Any],
    leakage: Mapping[str, str],
    block_index: Mapping[tuple[str, int, str], Mapping[str, Any]],
) -> dict[str, Any]:
    citation = evidence.get("citation") if isinstance(evidence.get("citation"), Mapping) else {}
    relative_path = str(evidence.get("relative_path") or citation.get("relative_path") or "")
    page_no = to_int(citation.get("page_no")) or to_int(quality.get("page_no")) or 0
    block = block_index.get((relative_path, page_no, bbox_key(citation.get("bbox"))), {})
    evidence_text = compact_text(evidence.get("evidence_text") or evidence.get("evidence_text_excerpt") or "")
    block_text = compact_text(block.get("text") or evidence_text)
    nearby_context = compact_text(evidence.get("nearby_context") or "")
    table_like = truthy(quality.get("table_like_context_candidate")) or truthy(evidence.get("table_like_context_candidate"))
    query_issue = classify_query_surface(quality, evidence, leakage)
    parser_issue = classify_parser_block(quality, evidence_text, nearby_context)
    table_issue = classify_table_semantics(table_like, block_text, nearby_context)
    lane = likely_fix_lane(
        quality=quality,
        evidence=evidence,
        query_issue=query_issue,
        parser_issue=parser_issue,
        table_issue=table_issue,
        abstain_reason=str(draft.get("abstain_reason") or ""),
    )
    return {
        "query_id": quality.get("query_id") or evidence.get("query_id"),
        "dataset_source": "lh",
        "file_name": quality.get("file_name") or evidence.get("file_name"),
        "page_no": page_no,
        "anchor_type": quality.get("anchor_type") or evidence.get("anchor_type"),
        "abstain_reason": draft.get("abstain_reason") or quality.get("reason") or "",
        "table_like_context_candidate": table_like,
        "block_text_excerpt": short_text(block_text, 260),
        "nearby_context_excerpt": short_text(nearby_context, 260),
        "section_context": section_context(evidence),
        "query_surface_issue": query_issue,
        "parser_block_issue": parser_issue,
        "table_semantics_issue": table_issue,
        "likely_fix_lane": lane,
    }


def classify_query_surface(quality: Mapping[str, str], evidence: Mapping[str, Any], leakage: Mapping[str, str]) -> str:
    query = str(quality.get("query") or evidence.get("query") or leakage.get("query") or "")
    if truthy(leakage.get("query_too_keyword_like")) or BROAD_QUERY_RE.search(query):
        return "BROAD_SYNTHETIC_TABLE_OR_SECTION_QUERY"
    return "QUERY_SURFACE_OK"


def classify_parser_block(quality: Mapping[str, str], evidence_text: str, nearby_context: str) -> str:
    issues: list[str] = []
    if int_from(quality.get("evidence_text_chars"), len(evidence_text)) < 40:
        issues.append("SHORT_BLOCK_TEXT")
    if not truthy(quality.get("paragraph_context_present")):
        issues.append("MISSING_PARAGRAPH_CONTEXT")
    if truthy(quality.get("keyword_only_risk")) and len(nearby_context) < 80:
        issues.append("KEYWORD_CONTEXT_BELOW_THRESHOLD")
    return "|".join(issues) if issues else "PARSER_BLOCK_OK"


def classify_table_semantics(table_like: bool, block_text: str, nearby_context: str) -> str:
    if not table_like:
        return "NOT_TABLE_LIKE"
    text = " ".join(part for part in [block_text, nearby_context] if part)
    if ROW_LABEL_RE.search(text or "") and COLUMN_LABEL_RE.search(text or "") and VALUE_RE.search(text or ""):
        return "ROW_COLUMN_VALUE_CANDIDATES_PRESENT"
    return "TABLE_LIKE_WITHOUT_ROW_COLUMN_VALUE"


def likely_fix_lane(
    *,
    quality: Mapping[str, str],
    evidence: Mapping[str, Any],
    query_issue: str,
    parser_issue: str,
    table_issue: str,
    abstain_reason: str,
) -> str:
    if truthy(quality.get("ocr_needed_candidate")) or truthy(evidence.get("ocr_used")) or truthy(evidence.get("lower_trust_ocr")):
        return "OCR_REFRESH_REQUIRED"
    if table_issue == "TABLE_LIKE_WITHOUT_ROW_COLUMN_VALUE":
        return "TABLE_EVIDENCE_CONTRACT_REQUIRED"
    if parser_issue != "PARSER_BLOCK_OK":
        return "EVIDENCE_SERIALIZER_FIX"
    if query_issue != "QUERY_SURFACE_OK":
        return "QUERY_REWRITE_ONLY"
    if abstain_reason:
        return "KEEP_ABSTAIN"
    return "MANUAL_REVIEW_REQUIRED"


def section_context(evidence: Mapping[str, Any]) -> str:
    section_title = compact_text(evidence.get("section_title") or "")
    paragraph = compact_text(evidence.get("paragraph_summary") or "")
    if section_title and paragraph and section_title != paragraph:
        return short_text(f"{section_title} | {paragraph}", 260)
    return short_text(section_title or paragraph, 260)


def build_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "lh_not_ready_row_count": len(rows),
        "table_like_context_candidate_count": sum(1 for row in rows if row.get("table_like_context_candidate") is True),
        "query_surface_issue_count": sum(1 for row in rows if row.get("query_surface_issue") != "QUERY_SURFACE_OK"),
        "parser_block_issue_count": sum(1 for row in rows if row.get("parser_block_issue") != "PARSER_BLOCK_OK"),
        "table_semantics_issue_count": sum(1 for row in rows if row.get("table_semantics_issue") == "TABLE_LIKE_WITHOUT_ROW_COLUMN_VALUE"),
        "likely_fix_lane_counts": sorted_counter(Counter(str(row.get("likely_fix_lane") or "UNKNOWN") for row in rows)),
        "abstain_reason_counts": sorted_counter(Counter(str(row.get("abstain_reason") or "UNKNOWN") for row in rows)),
        "anchor_type_counts": sorted_counter(Counter(str(row.get("anchor_type") or "UNKNOWN") for row in rows)),
        "table_semantics_issue_counts": sorted_counter(Counter(str(row.get("table_semantics_issue") or "UNKNOWN") for row in rows)),
    }


def build_block_index(blocks: list[Mapping[str, Any]]) -> dict[tuple[str, int, str], Mapping[str, Any]]:
    result: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    for block in blocks:
        key = (
            str(block.get("relative_path") or ""),
            to_int(block.get("page_no")) or 0,
            bbox_key(block.get("bbox")),
        )
        result[key] = block
    return result


def read_jsonl_or_block(path: Path, label: str, blockers: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return []
    return [row for row in iter_jsonl(path)]


def read_csv_or_block(path: Path, label: str, blockers: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return []
    return read_csv(path)


def read_csv_by_id(path: Path, label: str, warnings: list[str]) -> dict[str, dict[str, str]]:
    if not path.exists():
        warnings.append(f"{label} missing: {display_path(path)}")
        return {}
    return {str(row.get("query_id") or ""): row for row in read_csv(path)}


def int_from(value: Any, default: int) -> int:
    parsed = to_int(value)
    return default if parsed is None else parsed


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def resolve_artifact_dir(value: str | None) -> Path:
    if value:
        return resolve_path(value)
    raise ValueError("Pass --artifact-dir for deterministic post-analysis; latest-by-mtime artifact selection is disabled.")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--evidence-jsonl", default=None)
    parser.add_argument("--draft-jsonl", default=None)
    parser.add_argument("--parsed-blocks", default=None)
    parser.add_argument("--quality-csv", default=str(DEFAULT_QUALITY_CSV))
    parser.add_argument("--leakage-csv", default=str(DEFAULT_LEAKAGE_CSV))
    parser.add_argument("--abstain-breakdown", default=str(DEFAULT_ABSTAIN_BREAKDOWN))
    parser.add_argument("--dataset-gap", default=str(DEFAULT_DATASET_GAP))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
