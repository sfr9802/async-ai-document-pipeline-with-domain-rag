"""Audit deterministic supplemental PDF answer-draft shape.

The audit is deterministic and lexical. It does not call an LLM, does not treat
drafts as actual generated answers, and does not change retrieval, candidates,
baselines, gold, denominators, DB/SearchUnit state, or parser behavior.
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
    display_path,
    iter_jsonl,
    latest_supplemental_artifact_dir,
    read_csv,
    resolve_path,
    short_text,
    sorted_counter,
    supplemental_output_path_blockers,
    truthy,
    utc_timestamp,
    write_csv,
    write_json,
)


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_draft_shape_audit.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_draft_shape_audit.csv"
DEFAULT_QUALITY_CSV = REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.csv"

REQUIRED_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "local_llm_run": False,
    "pageindex_rerun": False,
    "pageindex_improvement_claimed": False,
}

CSV_FIELDS = [
    "query_id",
    "dataset_source",
    "file_name",
    "answer_shape",
    "has_draft",
    "content_first_answer",
    "citation_present",
    "locator_leak_into_answer_text",
    "keyword_echo_prevented",
    "keyword_echo_residual",
    "source_evidence_text_missing",
    "support_overlap_ratio",
    "weak_support_overlap",
    "draft_shape_status",
    "warnings",
    "answer_draft_excerpt",
]

LOCATOR_LEAK_RE = re.compile(
    r"(bbox|page_no|physical_page|ai/|eval/datasets|\.pdf\b|페이지\s*\d+|page\s*\d+)",
    re.IGNORECASE,
)
LOCATOR_FIRST_RE = re.compile(r"^\s*(페이지|page|bbox|파일|문서\s*위치|citation|출처)", re.IGNORECASE)
STOPWORDS = {
    "이",
    "그",
    "저",
    "문서",
    "문서에서",
    "부분",
    "관련",
    "기준",
    "찾아줘",
    "확인해줘",
    "알려줘",
    "표",
    "후보",
    "영역에는",
    "내용이",
    "포함되어",
    "있습니다",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = resolve_artifact_dir(args.artifact_dir)
    draft_path = resolve_path(args.draft_jsonl) if args.draft_jsonl else artifact_dir / "deterministic_answer_drafts.jsonl"
    evidence_path = resolve_path(args.evidence_jsonl) if args.evidence_jsonl else artifact_dir / "answer_evidence_objects.jsonl"
    quality_csv_path = resolve_path(args.quality_csv)
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

    payload = build_shape_audit(
        artifact_dir=artifact_dir,
        draft_path=draft_path,
        evidence_path=evidence_path,
        quality_csv_path=quality_csv_path,
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


def build_shape_audit(
    *,
    artifact_dir: Path,
    draft_path: Path,
    evidence_path: Path,
    quality_csv_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    draft_rows = read_jsonl_or_block(draft_path, "deterministic draft JSONL", blockers)
    evidence_rows = read_jsonl_or_block(evidence_path, "answer evidence JSONL", blockers)
    quality_by_id = read_csv_by_id(quality_csv_path, "quality audit CSV", warnings)
    evidence_by_id = {str(row.get("query_id") or ""): row for row in evidence_rows}
    rows = [
        audit_draft_row(row, evidence_by_id.get(str(row.get("query_id") or ""), {}), quality_by_id.get(str(row.get("query_id") or ""), {}))
        for row in draft_rows
    ]
    counts = build_counts(rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and counts["draft_shape_fail_count"]:
        status = "PASS_WITH_DRAFT_SHAPE_FAILURES"
    elif not blockers and counts["draft_shape_warning_count"]:
        status = "PASS_WITH_DRAFT_SHAPE_WARNINGS"
    report = {
        "schema_version": "pdf_supplemental_draft_shape_audit_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "deterministic_draft_shape_audit_only",
        "answer_draft_is_actual_generated_llm_answer": False,
        "actual_generated_answer_output": False,
        "actual_llm_answer_generation_run": False,
        "deterministic_answer_draft_only": True,
        "input_artifacts": [
            artifact_identity(draft_path),
            artifact_identity(evidence_path),
            artifact_identity(quality_csv_path),
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
            "draft_count counts non-empty deterministic drafts; abstain rows are retained in CSV but excluded from shape pass/fail denominators.",
            "Support overlap is lexical and approximate; it is not an LLM/judge result.",
            "Keyword echo prevented means the deterministic draft changed a keyword-risk row into content-bearing text, not that answer quality is accepted.",
        ],
    }
    return {"report": report, "rows": rows}


def audit_draft_row(
    draft: Mapping[str, Any],
    evidence: Mapping[str, Any],
    quality: Mapping[str, str],
) -> dict[str, Any]:
    answer_draft = compact_text(draft.get("answer_draft") or "")
    source_text = compact_text(draft.get("source_evidence_text") or evidence.get("evidence_text") or "")
    has_draft = bool(answer_draft)
    citation = draft.get("citation") if isinstance(draft.get("citation"), Mapping) else {}
    citation_present = bool(citation.get("relative_path") and (citation.get("page_no") or citation.get("bbox")))
    locator_leak = bool(has_draft and LOCATOR_LEAK_RE.search(answer_draft))
    content_first = bool(has_draft and not locator_leak and not LOCATOR_FIRST_RE.search(answer_draft) and len(tokens(answer_draft)) >= 3)
    source_missing = bool(has_draft and not source_text)
    overlap = support_overlap(answer_draft, source_text) if has_draft and source_text else None
    weak_overlap = bool(has_draft and overlap is not None and overlap < 0.45)
    keyword_echo_prevented = truthy(draft.get("keyword_echo_prevented"))
    keyword_echo_residual = bool(has_draft and keyword_echo_like(answer_draft, evidence.get("query") or quality.get("query") or "", keyword_echo_prevented))
    row_warnings: list[str] = []
    if not content_first and has_draft:
        row_warnings.append("answer_not_content_first")
    if not citation_present and has_draft:
        row_warnings.append("citation_missing")
    if locator_leak:
        row_warnings.append("locator_leak_into_answer_text")
    if source_missing:
        row_warnings.append("source_evidence_text_missing")
    if weak_overlap:
        row_warnings.append("weak_source_overlap")
    if keyword_echo_residual:
        row_warnings.append("keyword_echo_residual")
    status = draft_shape_status(has_draft, row_warnings)
    return {
        "query_id": draft.get("query_id"),
        "dataset_source": evidence.get("dataset_source") or quality.get("dataset_source"),
        "file_name": evidence.get("file_name") or quality.get("file_name"),
        "answer_shape": draft.get("answer_shape"),
        "has_draft": has_draft,
        "content_first_answer": content_first,
        "citation_present": citation_present,
        "locator_leak_into_answer_text": locator_leak,
        "keyword_echo_prevented": keyword_echo_prevented,
        "keyword_echo_residual": keyword_echo_residual,
        "source_evidence_text_missing": source_missing,
        "support_overlap_ratio": overlap,
        "weak_support_overlap": weak_overlap,
        "draft_shape_status": status,
        "warnings": row_warnings,
        "answer_draft_excerpt": short_text(answer_draft, 260),
    }


def draft_shape_status(has_draft: bool, warnings: list[str]) -> str:
    if not has_draft:
        return "ABSTAIN_NOT_A_DRAFT"
    hard_failures = {
        "citation_missing",
        "locator_leak_into_answer_text",
        "source_evidence_text_missing",
        "keyword_echo_residual",
    }
    if hard_failures.intersection(warnings):
        return "FAIL"
    if warnings:
        return "WARNING"
    return "PASS"


def build_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    draft_rows = [row for row in rows if row.get("has_draft") is True]
    keyword_prevented_rows = [row for row in draft_rows if row.get("keyword_echo_prevented") is True]
    return {
        "draft_object_count": len(rows),
        "draft_count": len(draft_rows),
        "abstain_row_count": len(rows) - len(draft_rows),
        "content_first_answer_count": sum(1 for row in draft_rows if row.get("content_first_answer") is True),
        "citation_present_count": sum(1 for row in draft_rows if row.get("citation_present") is True),
        "locator_leak_into_answer_text_count": sum(1 for row in draft_rows if row.get("locator_leak_into_answer_text") is True),
        "keyword_echo_residual_count": sum(1 for row in draft_rows if row.get("keyword_echo_residual") is True),
        "keyword_echo_prevented_count": len(keyword_prevented_rows),
        "keyword_echo_prevented_content_bearing_count": sum(
            1
            for row in keyword_prevented_rows
            if row.get("content_first_answer") is True and row.get("keyword_echo_residual") is False
        ),
        "source_evidence_text_missing_count": sum(1 for row in draft_rows if row.get("source_evidence_text_missing") is True),
        "weak_support_overlap_count": sum(1 for row in draft_rows if row.get("weak_support_overlap") is True),
        "draft_shape_pass_count": sum(1 for row in draft_rows if row.get("draft_shape_status") == "PASS"),
        "draft_shape_warning_count": sum(1 for row in draft_rows if row.get("draft_shape_status") == "WARNING"),
        "draft_shape_fail_count": sum(1 for row in draft_rows if row.get("draft_shape_status") == "FAIL"),
        "draft_shape_status_counts": sorted_counter(Counter(str(row.get("draft_shape_status") or "UNKNOWN") for row in rows)),
        "answer_shape_counts": sorted_counter(Counter(str(row.get("answer_shape") or "ABSTAIN") for row in rows)),
    }


def support_overlap(answer: str, source: str) -> float:
    answer_tokens = set(tokens(answer))
    source_tokens = set(tokens(source))
    if not answer_tokens:
        return 0.0
    if not source_tokens:
        return 0.0
    return round(len(answer_tokens & source_tokens) / len(answer_tokens), 6)


def keyword_echo_like(answer: str, query: str, keyword_echo_prevented: bool) -> bool:
    answer_tokens = set(tokens(answer))
    query_tokens = set(tokens(query))
    if not answer_tokens or not query_tokens:
        return False
    overlap = len(answer_tokens & query_tokens) / len(answer_tokens)
    if normalized(answer) == normalized(query):
        return True
    if keyword_echo_prevented and len(answer_tokens) <= 6 and overlap >= 0.7:
        return True
    return False


def tokens(text: str) -> list[str]:
    result = []
    for token in re.findall(r"[0-9A-Za-z가-힣]+", text or ""):
        normalized_token = token.lower()
        if len(normalized_token) <= 1 or normalized_token in STOPWORDS:
            continue
        result.append(normalized_token)
    return result


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def read_jsonl_or_block(path: Path, label: str, blockers: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return []
    return [row for row in iter_jsonl(path)]


def read_csv_by_id(path: Path, label: str, warnings: list[str]) -> dict[str, dict[str, str]]:
    if not path.exists():
        warnings.append(f"{label} missing: {display_path(path)}")
        return {}
    return {str(row.get("query_id") or ""): row for row in read_csv(path)}


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def resolve_artifact_dir(value: str | None) -> Path:
    if value:
        return resolve_path(value)
    return latest_supplemental_artifact_dir()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--draft-jsonl", default=None)
    parser.add_argument("--evidence-jsonl", default=None)
    parser.add_argument("--quality-csv", default=str(DEFAULT_QUALITY_CSV))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
