"""Break down supplemental PDF deterministic-draft abstain reasons.

This diagnostic joins existing deterministic drafts and answer-evidence
objects. It does not run PageIndex, retrieval, reranking, parser expansion,
DB/SearchUnit mutation, LLM answer generation, or judge calls.
"""

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
    to_int,
    truthy,
    utc_timestamp,
    write_csv,
    write_json,
)


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_abstain_reason_breakdown.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_abstain_reason_breakdown.csv"
DEFAULT_QUALITY_CSV = REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.csv"
DEFAULT_LEAKAGE_CSV = REPORT_DIR / "rag_pdf_supplemental_anchor_query_leakage_audit.csv"

REQUIRED_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "local_llm_run": False,
    "pageindex_rerun": False,
    "pageindex_improvement_claimed": False,
}

ABSTAIN_REASON_ENUM = [
    "CONTEXT_TEXT_TOO_SHORT",
    "ONLY_KEYWORD_OR_LABEL_PRESENT",
    "ONLY_LOCATOR_PRESENT",
    "TABLE_LIKE_WITHOUT_ROW_COLUMN_VALUE",
    "OCR_OR_TEXT_LAYER_UNAVAILABLE",
    "SECTION_CONTEXT_TOO_GENERIC",
    "NEARBY_CONTEXT_NOT_ANSWER_SUPPORTING",
    "SYNTHETIC_QUERY_TOO_BROAD",
    "UNKNOWN",
]

CSV_FIELDS = [
    "query_id",
    "dataset_source",
    "anchor_type",
    "file_name",
    "page_no",
    "primary_abstain_reason",
    "draft_abstain_reason",
    "quality_reason",
    "secondary_signals",
    "keyword_only_risk",
    "table_like_context_candidate",
    "synthetic_query_too_broad",
    "evidence_text_chars",
    "nearby_context_chars",
    "section_title_chars",
    "row_label_candidate_present",
    "column_label_candidate_present",
    "value_candidate_present",
    "unit_candidate_present",
    "query",
    "evidence_text_excerpt",
    "nearby_context_excerpt",
]

UNIT_RE = re.compile(r"(원|kWh|kw|%|㎡|m2|개월|년|월|일|만원|천원|세대|호|단계|배)", re.IGNORECASE)
VALUE_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
ROW_LABEL_RE = re.compile(r"[가-힣A-Za-z][^\n:：]{0,24}[:：]")
COLUMN_LABEL_RE = re.compile(
    r"(구분|항목|사용량|기본|전력량|요금|금액|단가|임대료|보증금|면적|세대|소득|기간|월|하계|동계|기타|전용|공급)"
)
GENERIC_SECTION_RE = re.compile(r"(요금표|표|기준|안내|목차|개요|조건|금액|관련|사항)")
BROAD_QUERY_RE = re.compile(r"(관련 기준|표로 정리된 부분|조건이나 금액|부분 찾아줘|부분 확인해줘)")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = resolve_artifact_dir(args.artifact_dir)
    evidence_path = resolve_path(args.evidence_jsonl) if args.evidence_jsonl else artifact_dir / "answer_evidence_objects.jsonl"
    draft_path = resolve_path(args.draft_jsonl) if args.draft_jsonl else artifact_dir / "deterministic_answer_drafts.jsonl"
    quality_csv_path = resolve_path(args.quality_csv)
    leakage_csv_path = resolve_path(args.leakage_csv)
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

    payload = build_breakdown(
        artifact_dir=artifact_dir,
        evidence_path=evidence_path,
        draft_path=draft_path,
        quality_csv_path=quality_csv_path,
        leakage_csv_path=leakage_csv_path,
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


def build_breakdown(
    *,
    artifact_dir: Path,
    evidence_path: Path,
    draft_path: Path,
    quality_csv_path: Path,
    leakage_csv_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    evidence_rows = read_jsonl_or_block(evidence_path, "answer evidence JSONL", blockers)
    draft_rows = read_jsonl_or_block(draft_path, "deterministic draft JSONL", blockers)
    quality_by_id = read_csv_by_id(quality_csv_path, "quality audit CSV", blockers)
    leakage_by_id = read_csv_by_id(leakage_csv_path, "leakage audit CSV", warnings)
    evidence_by_id = {str(row.get("query_id") or ""): row for row in evidence_rows}

    abstain_drafts = [row for row in draft_rows if is_abstain_draft(row)]
    rows: list[dict[str, Any]] = []
    for draft in abstain_drafts:
        query_id = str(draft.get("query_id") or "")
        evidence = evidence_by_id.get(query_id, {})
        quality = quality_by_id.get(query_id, {})
        leakage = leakage_by_id.get(query_id, {})
        rows.append(audit_abstain_row(draft, evidence, quality, leakage))

    counts = build_counts(draft_rows, rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and rows:
        status = "PASS_WITH_ABSTAIN_BREAKDOWN"
    report = {
        "schema_version": "pdf_supplemental_abstain_reason_breakdown_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "diagnostic_abstain_reason_breakdown_only",
        "actual_llm_answer_generation_run": False,
        "answer_draft_is_actual_generated_llm_answer": False,
        "actual_generated_answer_output": False,
        "deterministic_answer_draft_only": True,
        "abstain_reason_enum": ABSTAIN_REASON_ENUM,
        "input_artifacts": [
            artifact_identity(evidence_path),
            artifact_identity(draft_path),
            artifact_identity(quality_csv_path),
            artifact_identity(leakage_csv_path),
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
            "Primary abstain reasons are deterministic heuristics over existing evidence/draft rows.",
            "Keyword-only and table-like labels are diagnostic risk labels, not final answer-quality judgments.",
            "Table-like abstains do not claim row, column, value, bbox, or table-semantics success.",
        ],
    }
    return {"report": report, "rows": rows}


def read_jsonl_or_block(path: Path, label: str, blockers: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return []
    return [row for row in iter_jsonl(path)]


def read_csv_by_id(path: Path, label: str, findings: list[str]) -> dict[str, dict[str, str]]:
    if not path.exists():
        findings.append(f"{label} missing: {display_path(path)}")
        return {}
    return {str(row.get("query_id") or ""): row for row in read_csv(path)}


def is_abstain_draft(row: Mapping[str, Any]) -> bool:
    return bool(str(row.get("abstain_reason") or "").strip() or not str(row.get("answer_draft") or "").strip())


def audit_abstain_row(
    draft: Mapping[str, Any],
    evidence: Mapping[str, Any],
    quality: Mapping[str, str],
    leakage: Mapping[str, str],
) -> dict[str, Any]:
    citation = evidence.get("citation") if isinstance(evidence.get("citation"), Mapping) else draft.get("citation")
    citation = citation if isinstance(citation, Mapping) else {}
    evidence_text = compact_text(
        evidence.get("evidence_text")
        or evidence.get("evidence_text_excerpt")
        or evidence.get("paragraph_summary")
        or quality.get("evidence_text_excerpt")
        or ""
    )
    nearby_context = compact_text(evidence.get("nearby_context") or "")
    section_title = compact_text(evidence.get("section_title") or "")
    table_profile = table_signal_profile(" ".join(part for part in [evidence_text, nearby_context] if part))
    primary_reason, secondary_signals = classify_abstain(
        evidence=evidence,
        quality=quality,
        leakage=leakage,
        evidence_text=evidence_text,
        nearby_context=nearby_context,
        section_title=section_title,
        table_profile=table_profile,
    )
    return {
        "query_id": draft.get("query_id") or evidence.get("query_id") or quality.get("query_id"),
        "dataset_source": evidence.get("dataset_source") or quality.get("dataset_source"),
        "anchor_type": evidence.get("anchor_type") or quality.get("anchor_type"),
        "file_name": evidence.get("file_name") or quality.get("file_name"),
        "page_no": citation.get("page_no"),
        "primary_abstain_reason": primary_reason,
        "draft_abstain_reason": draft.get("abstain_reason"),
        "quality_reason": quality.get("reason"),
        "secondary_signals": secondary_signals,
        "keyword_only_risk": is_true(quality.get("keyword_only_risk")) or truthy(evidence.get("keyword_only_risk")),
        "table_like_context_candidate": is_true(quality.get("table_like_context_candidate"))
        or truthy(evidence.get("table_like_context_candidate")),
        "synthetic_query_too_broad": synthetic_query_too_broad(evidence, leakage),
        "evidence_text_chars": int_from_quality(quality.get("evidence_text_chars"), len(evidence_text)),
        "nearby_context_chars": len(nearby_context),
        "section_title_chars": len(section_title),
        "row_label_candidate_present": table_profile["row_label_candidate_present"],
        "column_label_candidate_present": table_profile["column_label_candidate_present"],
        "value_candidate_present": table_profile["value_candidate_present"],
        "unit_candidate_present": table_profile["unit_candidate_present"],
        "query": evidence.get("query") or quality.get("query"),
        "evidence_text_excerpt": short_text(evidence_text, 220),
        "nearby_context_excerpt": short_text(nearby_context, 220),
    }


def classify_abstain(
    *,
    evidence: Mapping[str, Any],
    quality: Mapping[str, str],
    leakage: Mapping[str, str],
    evidence_text: str,
    nearby_context: str,
    section_title: str,
    table_profile: Mapping[str, bool],
) -> tuple[str, list[str]]:
    evidence_text_chars = int_from_quality(quality.get("evidence_text_chars"), len(evidence_text))
    context_chars = int_from_quality(quality.get("evidence_context_chars"), len(nearby_context) + len(section_title))
    keyword_only = is_true(quality.get("keyword_only_risk")) or truthy(evidence.get("keyword_only_risk"))
    table_like = is_true(quality.get("table_like_context_candidate")) or truthy(evidence.get("table_like_context_candidate"))
    locator_only = (
        is_true(quality.get("locator_only_risk"))
        or is_true(quality.get("page_only_risk"))
        or is_true(quality.get("bbox_only_risk"))
        or truthy(evidence.get("locator_only_object"))
        or truthy(evidence.get("page_only_risk"))
        or truthy(evidence.get("bbox_only_risk"))
    )
    ocr_unavailable = (
        is_true(quality.get("ocr_needed_candidate"))
        or truthy(evidence.get("ocr_evidence_used"))
        or truthy(evidence.get("lower_trust_ocr"))
    ) and not evidence_text
    all_table_semantics_present = all(
        table_profile[key]
        for key in ("row_label_candidate_present", "column_label_candidate_present", "value_candidate_present")
    )
    secondary: list[str] = []
    if keyword_only:
        secondary.append("keyword_only_risk")
    if table_like:
        secondary.append("table_like_context_candidate")
    if synthetic_query_too_broad(evidence, leakage):
        secondary.append("synthetic_query_too_broad")
    if evidence_text_chars < 40:
        secondary.append("evidence_text_below_40_chars")
    if len(nearby_context) < 80:
        secondary.append("nearby_context_below_80_chars")
    if section_title and GENERIC_SECTION_RE.search(section_title) and evidence_text_chars < 40:
        secondary.append("section_context_generic")
    if table_like and not all_table_semantics_present:
        secondary.append("row_column_value_not_all_present")

    if locator_only:
        return "ONLY_LOCATOR_PRESENT", secondary
    if ocr_unavailable:
        return "OCR_OR_TEXT_LAYER_UNAVAILABLE", secondary
    if table_like and not all_table_semantics_present:
        return "TABLE_LIKE_WITHOUT_ROW_COLUMN_VALUE", secondary
    if section_title and GENERIC_SECTION_RE.search(section_title) and evidence_text_chars < 40:
        return "SECTION_CONTEXT_TOO_GENERIC", secondary
    if keyword_only:
        return "ONLY_KEYWORD_OR_LABEL_PRESENT", secondary
    if evidence_text_chars < 40 and context_chars < 80:
        return "CONTEXT_TEXT_TOO_SHORT", secondary
    if nearby_context and lexical_overlap(evidence_text, nearby_context) < 0.2:
        return "NEARBY_CONTEXT_NOT_ANSWER_SUPPORTING", secondary
    if synthetic_query_too_broad(evidence, leakage):
        return "SYNTHETIC_QUERY_TOO_BROAD", secondary
    return "UNKNOWN", secondary


def table_signal_profile(text: str) -> dict[str, bool]:
    numeric_tokens = VALUE_RE.findall(text or "")
    return {
        "row_label_candidate_present": bool(ROW_LABEL_RE.search(text or "")) or bool(re.search(r"\b[1-9]\s*단계\b", text or "")),
        "column_label_candidate_present": bool(COLUMN_LABEL_RE.search(text or "")),
        "value_candidate_present": len(numeric_tokens) >= 1,
        "unit_candidate_present": bool(UNIT_RE.search(text or "")),
    }


def synthetic_query_too_broad(evidence: Mapping[str, Any], leakage: Mapping[str, str]) -> bool:
    query = str(evidence.get("query") or leakage.get("query") or "")
    return is_true(leakage.get("query_too_keyword_like")) or bool(BROAD_QUERY_RE.search(query))


def lexical_overlap(left: str, right: str) -> float:
    left_tokens = set(tokens(left))
    right_tokens = set(tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens)


def tokens(text: str) -> list[str]:
    return [token.lower() for token in re.findall(r"[0-9A-Za-z가-힣]+", text or "") if len(token) > 1]


def int_from_quality(value: Any, default: int) -> int:
    parsed = to_int(value)
    return default if parsed is None else parsed


def is_true(value: Any) -> bool:
    return truthy(value)


def build_counts(draft_rows: list[Mapping[str, Any]], rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    dataset_reason: dict[str, Counter[str]] = defaultdict(Counter)
    anchor_reason: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        reason = str(row.get("primary_abstain_reason") or "UNKNOWN")
        dataset_reason[str(row.get("dataset_source") or "unknown")][reason] += 1
        anchor_reason[str(row.get("anchor_type") or "unknown")][reason] += 1
    return {
        "draft_object_count": len(draft_rows),
        "draft_created_count": sum(1 for row in draft_rows if str(row.get("answer_draft") or "").strip()),
        "abstain_count": len(rows),
        "primary_abstain_reason_counts": sorted_counter(Counter(str(row.get("primary_abstain_reason") or "UNKNOWN") for row in rows)),
        "dataset_source_counts": sorted_counter(Counter(str(row.get("dataset_source") or "unknown") for row in rows)),
        "anchor_type_counts": sorted_counter(Counter(str(row.get("anchor_type") or "unknown") for row in rows)),
        "dataset_source_reason_counts": nested_counter(dataset_reason),
        "anchor_type_reason_counts": nested_counter(anchor_reason),
        "keyword_only_risk_abstain_count": sum(1 for row in rows if row.get("keyword_only_risk") is True),
        "table_like_abstain_count": sum(1 for row in rows if row.get("table_like_context_candidate") is True),
        "synthetic_query_too_broad_abstain_count": sum(1 for row in rows if row.get("synthetic_query_too_broad") is True),
    }


def nested_counter(value: Mapping[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {key: sorted_counter(counter) for key, counter in sorted(value.items())}


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def resolve_artifact_dir(value: str | None) -> Path:
    if value:
        return resolve_path(value)
    return latest_supplemental_artifact_dir()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--evidence-jsonl", default=None)
    parser.add_argument("--draft-jsonl", default=None)
    parser.add_argument("--quality-csv", default=str(DEFAULT_QUALITY_CSV))
    parser.add_argument("--leakage-csv", default=str(DEFAULT_LEAKAGE_CSV))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
