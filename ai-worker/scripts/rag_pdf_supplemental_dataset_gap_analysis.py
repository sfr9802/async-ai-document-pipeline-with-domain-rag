"""Compare elec/lh supplemental PDF evidence gaps.

This script is diagnostic-only. It reads existing evidence, draft, quality, and
query-leakage outputs to explain LH evidence-ready failures without mutating
PageIndex, parser, retrieval, DB/SearchUnit, candidates, baselines, gold, or
denominators.
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


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_dataset_gap_analysis.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_dataset_gap_analysis.csv"
DEFAULT_QUALITY_CSV = REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.csv"
DEFAULT_LEAKAGE_CSV = REPORT_DIR / "rag_pdf_supplemental_anchor_query_leakage_audit.csv"

REQUIRED_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "local_llm_run": False,
    "pageindex_rerun": False,
    "pageindex_improvement_claimed": False,
}

CSV_FIELDS = [
    "priority_rank",
    "query_id",
    "dataset_source",
    "file_name",
    "page_no",
    "anchor_type",
    "priority_score",
    "primary_failure_class",
    "failure_dimensions",
    "draft_abstain_reason",
    "quality_reason",
    "keyword_only_risk",
    "table_like_context_candidate",
    "paragraph_context_present",
    "nearby_context_present",
    "query_too_keyword_like",
    "evidence_text_chars",
    "evidence_context_chars",
    "query",
    "evidence_text_excerpt",
    "recommended_next_action",
]

BROAD_QUERY_RE = re.compile(r"(관련 기준|표로 정리된 부분|조건이나 금액|부분 찾아줘|부분 확인해줘)")
VALUE_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
ROW_LABEL_RE = re.compile(r"[가-힣A-Za-z][^\n:：]{0,24}[:：]|\b[1-9]\s*단계\b")
COLUMN_LABEL_RE = re.compile(
    r"(구분|항목|사용량|기본|전력량|요금|금액|단가|임대료|보증금|면적|세대|소득|기간|월|하계|동계|기타|전용|공급)"
)


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

    payload = build_gap_analysis(
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


def build_gap_analysis(
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
    if not quality_csv_path.exists():
        blockers.append(f"quality audit CSV missing: {display_path(quality_csv_path)}")
        quality_rows: list[dict[str, str]] = []
    else:
        quality_rows = read_csv(quality_csv_path)
    leakage_by_id = read_csv_by_id(leakage_csv_path, "leakage audit CSV", warnings)
    evidence_by_id = {str(row.get("query_id") or ""): row for row in evidence_rows}
    draft_by_id = {str(row.get("query_id") or ""): row for row in draft_rows}

    dataset_comparison = build_dataset_comparison(quality_rows, draft_by_id)
    lh_rows = [
        build_lh_failure_row(row, evidence_by_id.get(str(row.get("query_id") or ""), {}), draft_by_id.get(str(row.get("query_id") or ""), {}), leakage_by_id.get(str(row.get("query_id") or ""), {}))
        for row in quality_rows
        if str(row.get("dataset_source") or "") == "lh" and not truthy(row.get("evidence_ready"))
    ]
    lh_rows.sort(key=lambda row: (-int(row["priority_score"]), int_from(row.get("evidence_text_chars"), 0), str(row.get("query_id") or "")))
    for index, row in enumerate(lh_rows, start=1):
        row["priority_rank"] = index

    counts = build_counts(quality_rows, lh_rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and lh_rows:
        status = "PASS_WITH_LH_GAP_ANALYSIS"
    report = {
        "schema_version": "pdf_supplemental_dataset_gap_analysis_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "diagnostic_dataset_gap_analysis_only",
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
        "dataset_comparison": dataset_comparison,
        "lh_failure_priority_rows": lh_rows,
        "interpretation": {
            "lh_ready_rate_drop": "LH has a lower ready rate because its not-ready rows concentrate in table-like blocks with short keyword/label-like text.",
            "query_surface": "Broad synthetic query surfaces are counted as diagnostic dimensions, not gold-policy decisions.",
            "parser_block": "Short parser block text and missing paragraph context are treated as evidence-serializer/parser-context limits.",
            "table_like_semantics": "Table-like candidates are not row/column/value semantics success and should stay separate from answer-quality claims.",
        },
        "blockers": blockers,
        "warnings": warnings,
    }
    return {"report": report, "rows": lh_rows}


def build_dataset_comparison(
    quality_rows: list[Mapping[str, str]],
    draft_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for dataset in sorted({str(row.get("dataset_source") or "unknown") for row in quality_rows}):
        rows = [row for row in quality_rows if str(row.get("dataset_source") or "unknown") == dataset]
        ready = sum(1 for row in rows if truthy(row.get("evidence_ready")))
        abstain = sum(1 for row in rows if draft_by_id.get(str(row.get("query_id") or ""), {}).get("abstain_reason") or not truthy(row.get("evidence_ready")))
        keyword_only = sum(1 for row in rows if truthy(row.get("keyword_only_risk")))
        table_like = sum(1 for row in rows if truthy(row.get("table_like_context_candidate")))
        paragraph = sum(1 for row in rows if truthy(row.get("paragraph_context_present")))
        result[dataset] = {
            "row_count": len(rows),
            "evidence_ready_count": ready,
            "abstain_count": abstain,
            "evidence_ready_rate": rate(ready, len(rows)),
            "keyword_only_risk_count": keyword_only,
            "keyword_only_risk_rate": rate(keyword_only, len(rows)),
            "table_like_context_candidate_count": table_like,
            "table_like_context_candidate_rate": rate(table_like, len(rows)),
            "paragraph_context_present_count": paragraph,
            "paragraph_context_present_rate": rate(paragraph, len(rows)),
            "anchor_type_counts": sorted_counter(Counter(str(row.get("anchor_type") or "unknown") for row in rows)),
            "readiness_reason_counts": sorted_counter(Counter(str(row.get("reason") or "") for row in rows)),
        }
    if "elec" in result and "lh" in result:
        result["lh_minus_elec_delta"] = {
            "evidence_ready_rate": round((result["lh"]["evidence_ready_rate"] or 0.0) - (result["elec"]["evidence_ready_rate"] or 0.0), 6),
            "keyword_only_risk_rate": round((result["lh"]["keyword_only_risk_rate"] or 0.0) - (result["elec"]["keyword_only_risk_rate"] or 0.0), 6),
            "table_like_context_candidate_rate": round((result["lh"]["table_like_context_candidate_rate"] or 0.0) - (result["elec"]["table_like_context_candidate_rate"] or 0.0), 6),
            "paragraph_context_present_rate": round((result["lh"]["paragraph_context_present_rate"] or 0.0) - (result["elec"]["paragraph_context_present_rate"] or 0.0), 6),
        }
    return result


def build_lh_failure_row(
    quality: Mapping[str, str],
    evidence: Mapping[str, Any],
    draft: Mapping[str, Any],
    leakage: Mapping[str, str],
) -> dict[str, Any]:
    evidence_text = compact_text(evidence.get("evidence_text") or evidence.get("evidence_text_excerpt") or "")
    nearby_context = compact_text(evidence.get("nearby_context") or "")
    citation = evidence.get("citation") if isinstance(evidence.get("citation"), Mapping) else {}
    failure_dimensions = classify_failure_dimensions(quality, evidence, leakage, evidence_text, nearby_context)
    primary_class = primary_failure_class(failure_dimensions)
    priority_score = score_failure(failure_dimensions, quality)
    return {
        "priority_rank": 0,
        "query_id": quality.get("query_id") or evidence.get("query_id"),
        "dataset_source": "lh",
        "file_name": quality.get("file_name") or evidence.get("file_name"),
        "page_no": citation.get("page_no"),
        "anchor_type": quality.get("anchor_type") or evidence.get("anchor_type"),
        "priority_score": priority_score,
        "primary_failure_class": primary_class,
        "failure_dimensions": failure_dimensions,
        "draft_abstain_reason": draft.get("abstain_reason"),
        "quality_reason": quality.get("reason"),
        "keyword_only_risk": truthy(quality.get("keyword_only_risk")),
        "table_like_context_candidate": truthy(quality.get("table_like_context_candidate")),
        "paragraph_context_present": truthy(quality.get("paragraph_context_present")),
        "nearby_context_present": truthy(quality.get("nearby_context_present")),
        "query_too_keyword_like": query_too_keyword_like(quality, evidence, leakage),
        "evidence_text_chars": int_from(quality.get("evidence_text_chars"), len(evidence_text)),
        "evidence_context_chars": int_from(quality.get("evidence_context_chars"), len(nearby_context)),
        "query": quality.get("query") or evidence.get("query"),
        "evidence_text_excerpt": short_text(evidence_text, 220),
        "recommended_next_action": recommended_next_action(primary_class, failure_dimensions),
    }


def classify_failure_dimensions(
    quality: Mapping[str, str],
    evidence: Mapping[str, Any],
    leakage: Mapping[str, str],
    evidence_text: str,
    nearby_context: str,
) -> list[str]:
    dimensions: list[str] = []
    table_like = truthy(quality.get("table_like_context_candidate")) or truthy(evidence.get("table_like_context_candidate"))
    parser_thin = (
        int_from(quality.get("evidence_text_chars"), len(evidence_text)) < 40
        or not truthy(quality.get("paragraph_context_present"))
        or (truthy(quality.get("keyword_only_risk")) and len(nearby_context) < 80)
    )
    text_for_table = " ".join(part for part in [evidence_text, nearby_context] if part)
    if query_too_keyword_like(quality, evidence, leakage):
        dimensions.append("query_surface")
    if parser_thin:
        dimensions.append("parser_block")
    if table_like and not all_table_signals_present(text_for_table):
        dimensions.append("table_like_semantics")
    if not dimensions:
        dimensions.append("unknown")
    return dimensions


def query_too_keyword_like(quality: Mapping[str, str], evidence: Mapping[str, Any], leakage: Mapping[str, str]) -> bool:
    query = str(quality.get("query") or evidence.get("query") or leakage.get("query") or "")
    return truthy(leakage.get("query_too_keyword_like")) or bool(BROAD_QUERY_RE.search(query))


def all_table_signals_present(text: str) -> bool:
    return bool(ROW_LABEL_RE.search(text or "") and COLUMN_LABEL_RE.search(text or "") and VALUE_RE.search(text or ""))


def primary_failure_class(dimensions: list[str]) -> str:
    values = set(dimensions)
    if {"query_surface", "parser_block", "table_like_semantics"}.issubset(values):
        return "MIXED_TABLE_QUERY_AND_PARSER"
    if {"parser_block", "table_like_semantics"}.issubset(values):
        return "MIXED_TABLE_AND_PARSER"
    if {"query_surface", "parser_block"}.issubset(values):
        return "MIXED_QUERY_AND_PARSER"
    if "table_like_semantics" in values:
        return "TABLE_LIKE_SEMANTICS_PROBLEM"
    if "parser_block" in values:
        return "PARSER_BLOCK_PROBLEM"
    if "query_surface" in values:
        return "QUERY_SURFACE_PROBLEM"
    return "UNKNOWN"


def score_failure(dimensions: list[str], quality: Mapping[str, str]) -> int:
    score = 0
    if "table_like_semantics" in dimensions:
        score += 40
    if "parser_block" in dimensions:
        score += 30
    if "query_surface" in dimensions:
        score += 20
    if truthy(quality.get("keyword_only_risk")):
        score += 10
    if int_from(quality.get("evidence_text_chars"), 0) < 40:
        score += 5
    return score


def recommended_next_action(primary_class: str, dimensions: list[str]) -> str:
    if "table_like_semantics" in dimensions:
        return "TABLE_PARSER_OR_EVIDENCE_CONTRACT_REVIEW"
    if "parser_block" in dimensions:
        return "EVIDENCE_SERIALIZER_CONTEXT_REVIEW"
    if "query_surface" in dimensions:
        return "QUERY_SURFACE_REWRITE_REVIEW"
    if primary_class == "UNKNOWN":
        return "MANUAL_REVIEW"
    return "KEEP_DIAGNOSTIC_ONLY"


def build_counts(quality_rows: list[Mapping[str, str]], lh_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    dimension_counts: Counter[str] = Counter()
    for row in lh_rows:
        for dimension in row.get("failure_dimensions") or []:
            dimension_counts[str(dimension)] += 1
    return {
        "evidence_object_count": len(quality_rows),
        "dataset_source_counts": sorted_counter(Counter(str(row.get("dataset_source") or "unknown") for row in quality_rows)),
        "lh_not_ready_count": len(lh_rows),
        "lh_primary_failure_class_counts": sorted_counter(Counter(str(row.get("primary_failure_class") or "UNKNOWN") for row in lh_rows)),
        "lh_failure_dimension_counts": sorted_counter(dimension_counts),
        "lh_table_like_not_ready_count": sum(1 for row in lh_rows if row.get("table_like_context_candidate") is True),
        "lh_keyword_only_not_ready_count": sum(1 for row in lh_rows if row.get("keyword_only_risk") is True),
        "lh_query_surface_not_ready_count": sum(1 for row in lh_rows if row.get("query_too_keyword_like") is True),
    }


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


def rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def int_from(value: Any, default: int) -> int:
    parsed = to_int(value)
    return default if parsed is None else parsed


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
