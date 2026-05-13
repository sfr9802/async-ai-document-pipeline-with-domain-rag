"""Audit supplemental synthetic anchor query leakage.

The audit evaluates parser-derived synthetic query surfaces only. It does not
promote anchors to gold, change denominators, or run retrieval/LLM evaluation.
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
    EVAL_QUERIES_DIR,
    REPORT_DIR,
    artifact_identity,
    display_path,
    iter_jsonl,
    latest_supplemental_artifact_dir,
    read_csv,
    resolve_path,
    sorted_counter,
    supplemental_output_path_blockers,
    utc_timestamp,
    write_csv,
    write_json,
)


DEFAULT_ANCHOR_CSV = EVAL_QUERIES_DIR / "gold_queries_pdf_supplemental_elec_lh_synthetic_diagnostic.csv"
DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_anchor_query_leakage_audit.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_anchor_query_leakage_audit.csv"

REQUIRED_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "local_llm_run": False,
    "pageindex_improvement_claimed": False,
}

CSV_FIELDS = [
    "query_id",
    "dataset_source",
    "file_name",
    "anchor_type",
    "query",
    "exact_anchor_in_query",
    "query_same_as_block_excerpt",
    "high_anchor_overlap",
    "anchor_overlap_ratio",
    "block_excerpt_overlap_ratio",
    "query_too_keyword_like",
    "difficulty",
    "reason",
]

STOPWORDS = {
    "이",
    "그",
    "저",
    "문서",
    "문서에서",
    "pdf",
    "부분",
    "찾아줘",
    "확인해줘",
    "알려줘",
    "나오는",
    "설명된",
    "정리된",
    "관련",
    "주요",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = resolve_artifact_dir(args.artifact_dir)
    anchor_csv_path = resolve_path(args.anchor_csv)
    parsed_blocks_path = resolve_path(args.parsed_blocks) if args.parsed_blocks else artifact_dir / "parsed_blocks.jsonl"
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

    payload = build_leakage_audit(
        artifact_dir=artifact_dir,
        anchor_csv_path=anchor_csv_path,
        parsed_blocks_path=parsed_blocks_path,
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


def build_leakage_audit(
    *,
    artifact_dir: Path,
    anchor_csv_path: Path,
    parsed_blocks_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not anchor_csv_path.exists():
        blockers.append(f"synthetic anchor CSV missing: {display_path(anchor_csv_path)}")
        anchors: list[dict[str, str]] = []
    else:
        anchors = read_csv(anchor_csv_path)
    block_index = build_block_text_index(parsed_blocks_path, warnings) if parsed_blocks_path.exists() else {}
    if not parsed_blocks_path.exists():
        warnings.append(f"parsed blocks JSONL missing: {display_path(parsed_blocks_path)}")

    rows = [audit_anchor(row, block_index) for row in anchors]
    counts = build_counts(rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and (
        counts["exact_anchor_in_query_count"]
        or counts["high_anchor_overlap_count"]
        or counts["query_same_as_block_excerpt_count"]
    ):
        status = "PASS_WITH_QUERY_SURFACE_LEAKAGE_RISKS"
    report = {
        "schema_version": "pdf_supplemental_anchor_query_leakage_audit_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "query_gold_status": "diagnostic_only",
        "synthetic_rows_are_gold": False,
        "diagnostic_query_surface_quality_only": True,
        "input_artifacts": [
            artifact_identity(anchor_csv_path),
            artifact_identity(parsed_blocks_path),
        ],
        "output_artifacts": {
            "json_report": display_path(json_report_path),
            "csv_report": display_path(csv_report_path),
        },
        "artifact_dir": display_path(artifact_dir),
        "counts": counts,
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "Exact anchor copy and high token overlap are query-surface leakage risks, not gold decisions.",
            "Difficulty is a synthetic diagnostic heuristic only.",
            "No PageIndex, retrieval, LLM, optional judge, denominator, C7, or promotion path is executed.",
        ],
    }
    return {"report": report, "rows": rows}


def build_block_text_index(path: Path, warnings: list[str]) -> dict[tuple[str, str, str], str]:
    result: dict[tuple[str, str, str], str] = {}
    try:
        for block in iter_jsonl(path):
            key = (
                str(block.get("relative_path") or ""),
                str(block.get("page_no") or ""),
                compact(str(block.get("bbox") or "")),
            )
            result[key] = str(block.get("text") or "")
    except json.JSONDecodeError as exc:
        warnings.append(f"parsed block JSONL decode warning: {exc}")
    return result


def audit_anchor(row: Mapping[str, str], block_index: Mapping[tuple[str, str, str], str]) -> dict[str, Any]:
    query = str(row.get("query") or "")
    anchor_text = str(row.get("anchor_text") or "")
    block_excerpt = str(row.get("parser_derived_block_text_excerpt") or "")
    key = (
        str(row.get("relative_path") or ""),
        str(row.get("parser_derived_page_no") or ""),
        compact(str(row.get("parser_derived_bbox") or "")),
    )
    block_text = block_index.get(key) or block_excerpt
    exact_anchor_in_query = exact_substring(anchor_text, query)
    query_same_as_block_excerpt = normalized(query) in {normalized(anchor_text), normalized(block_excerpt), normalized(block_text)}
    anchor_overlap_ratio = overlap_ratio(query, anchor_text)
    block_excerpt_overlap_ratio = overlap_ratio(query, block_text)
    high_anchor_overlap = max(anchor_overlap_ratio, block_excerpt_overlap_ratio) >= 0.65
    query_too_keyword_like = keyword_like_query(query)
    difficulty = classify_difficulty(
        row=row,
        exact_anchor_in_query=exact_anchor_in_query,
        query_same_as_block_excerpt=query_same_as_block_excerpt,
        high_anchor_overlap=high_anchor_overlap,
        query_too_keyword_like=query_too_keyword_like,
        overlap=max(anchor_overlap_ratio, block_excerpt_overlap_ratio),
    )
    return {
        "query_id": row.get("query_id"),
        "dataset_source": row.get("dataset_source"),
        "file_name": row.get("file_name"),
        "anchor_type": row.get("anchor_type"),
        "query": query,
        "exact_anchor_in_query": exact_anchor_in_query,
        "query_same_as_block_excerpt": query_same_as_block_excerpt,
        "high_anchor_overlap": high_anchor_overlap,
        "anchor_overlap_ratio": anchor_overlap_ratio,
        "block_excerpt_overlap_ratio": block_excerpt_overlap_ratio,
        "query_too_keyword_like": query_too_keyword_like,
        "difficulty": difficulty,
        "reason": leakage_reason(
            exact_anchor_in_query,
            query_same_as_block_excerpt,
            high_anchor_overlap,
            query_too_keyword_like,
            difficulty,
        ),
    }


def exact_substring(anchor_text: str, query: str) -> bool:
    anchor = normalized(anchor_text)
    if len(anchor) < 12:
        return False
    return anchor in normalized(query)


def overlap_ratio(query: str, evidence_text: str) -> float:
    query_tokens = meaningful_tokens(query)
    evidence_tokens = set(meaningful_tokens(evidence_text))
    if not query_tokens:
        return 0.0
    overlap = sum(1 for token in query_tokens if token in evidence_tokens)
    return round(overlap / len(query_tokens), 6)


def meaningful_tokens(text: str) -> list[str]:
    raw_tokens = [token.lower() for token in re.findall(r"[0-9A-Za-z가-힣]+", text or "")]
    return [token for token in raw_tokens if token and token not in STOPWORDS and len(token) > 1]


def keyword_like_query(query: str) -> bool:
    tokens = meaningful_tokens(query)
    if len(tokens) <= 2:
        return True
    has_content_target = any(
        term in query
        for term in ("조건", "금액", "자격", "요금", "공고", "신청", "안내", "기준", "표", "공급", "임대")
    )
    return not has_content_target and len(tokens) <= 4


def classify_difficulty(
    *,
    row: Mapping[str, str],
    exact_anchor_in_query: bool,
    query_same_as_block_excerpt: bool,
    high_anchor_overlap: bool,
    query_too_keyword_like: bool,
    overlap: float,
) -> str:
    if exact_anchor_in_query or query_same_as_block_excerpt or high_anchor_overlap or query_too_keyword_like:
        return "easy"
    query = str(row.get("query") or "")
    source = str(row.get("dataset_source") or "")
    source_hint = (
        (source == "elec" and any(term in query for term in ("전기", "요금", "주택용")))
        or (source == "lh" and any(term in query for term in ("LH", "입주", "공급", "신청", "임대", "금액", "조건")))
    )
    if overlap < 0.15 and not source_hint:
        return "hard"
    return "medium"


def leakage_reason(
    exact_anchor_in_query: bool,
    query_same_as_block_excerpt: bool,
    high_anchor_overlap: bool,
    query_too_keyword_like: bool,
    difficulty: str,
) -> str:
    reasons: list[str] = []
    if exact_anchor_in_query:
        reasons.append("exact_anchor_in_query")
    if query_same_as_block_excerpt:
        reasons.append("query_same_as_block_excerpt")
    if high_anchor_overlap:
        reasons.append("high_anchor_overlap")
    if query_too_keyword_like:
        reasons.append("query_too_keyword_like")
    if not reasons:
        reasons.append("no_direct_anchor_copy_detected")
    reasons.append(f"difficulty={difficulty}")
    return "|".join(reasons)


def build_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "synthetic_anchor_count": len(rows),
        "exact_anchor_in_query_count": sum(1 for row in rows if row.get("exact_anchor_in_query") is True),
        "high_anchor_overlap_count": sum(1 for row in rows if row.get("high_anchor_overlap") is True),
        "query_too_keyword_like_count": sum(1 for row in rows if row.get("query_too_keyword_like") is True),
        "query_same_as_block_excerpt_count": sum(1 for row in rows if row.get("query_same_as_block_excerpt") is True),
        "easy_count": sum(1 for row in rows if row.get("difficulty") == "easy"),
        "medium_count": sum(1 for row in rows if row.get("difficulty") == "medium"),
        "hard_count": sum(1 for row in rows if row.get("difficulty") == "hard"),
        "dataset_source_counts": sorted_counter(Counter(str(row.get("dataset_source") or "unknown") for row in rows)),
        "difficulty_counts": sorted_counter(Counter(str(row.get("difficulty") or "unknown") for row in rows)),
    }


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def resolve_artifact_dir(value: str | None) -> Path:
    if value:
        return resolve_path(value)
    return latest_supplemental_artifact_dir()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--anchor-csv", default=str(DEFAULT_ANCHOR_CSV))
    parser.add_argument("--parsed-blocks", default=None)
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
