"""Audit supplemental PDF table-like context candidates.

This is a row-level diagnostic over existing parsed/evidence artifacts. It
checks whether table-like candidates contain row/column/value signals, but it
does not claim table-semantics success or change parsers, DB/SearchUnit,
candidates, baselines, gold, denominators, or answer outputs.
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
    bbox_key,
    display_path,
    iter_jsonl,
    latest_supplemental_artifact_dir,
    read_csv,
    resolve_path,
    short_text,
    sorted_counter,
    supplemental_output_path_blockers,
    to_float,
    to_int,
    truthy,
    utc_timestamp,
    write_csv,
    write_json,
)


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_table_like_context_audit.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_table_like_context_audit.csv"
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
    "page_no",
    "block_id",
    "table_like_context_candidate",
    "numeric_density",
    "aligned_text_signal",
    "row_label_candidate_present",
    "column_label_candidate_present",
    "value_candidate_present",
    "unit_candidate_present",
    "table_semantics_ready",
    "recommended_next_action",
    "anchor_type",
    "table_like_score",
    "table_like_reasons",
    "source_text_chars",
    "source_text_excerpt",
]

RECOMMENDED_ACTIONS = [
    "KEEP_AS_CONTEXT_ONLY",
    "NEEDS_TABLE_PARSER",
    "NEEDS_MANUAL_REVIEW",
    "NOT_TABLE_LIKE_AFTER_AUDIT",
    "SUFFICIENT_FOR_EXTRACTIVE_CONTEXT_ONLY",
]

UNIT_RE = re.compile(r"(원|kWh|kw|%|㎡|m2|개월|년|월|일|만원|천원|세대|호|단계|배)", re.IGNORECASE)
VALUE_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
ROW_LABEL_RE = re.compile(
    r"[가-힣A-Za-z][^\n:：]{0,24}[:：]|\b[1-9]\s*단계\b|기타계절|하계|동계|가구별|입주자|공급대상|임대조건"
)
COLUMN_LABEL_RE = re.compile(
    r"(구분|항목|사용량|기본|전력량|요금|금액|단가|임대료|보증금|면적|세대|소득|기간|월|하계|동계|기타|전용|공급|조건)"
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = resolve_artifact_dir(args.artifact_dir)
    evidence_path = resolve_path(args.evidence_jsonl) if args.evidence_jsonl else artifact_dir / "answer_evidence_objects.jsonl"
    parsed_blocks_path = resolve_path(args.parsed_blocks) if args.parsed_blocks else artifact_dir / "parsed_blocks.jsonl"
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

    payload = build_table_audit(
        artifact_dir=artifact_dir,
        evidence_path=evidence_path,
        parsed_blocks_path=parsed_blocks_path,
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


def build_table_audit(
    *,
    artifact_dir: Path,
    evidence_path: Path,
    parsed_blocks_path: Path,
    quality_csv_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    evidence_rows = read_jsonl_or_block(evidence_path, "answer evidence JSONL", blockers)
    parsed_blocks = read_jsonl_or_block(parsed_blocks_path, "parsed blocks JSONL", blockers)
    if not quality_csv_path.exists():
        blockers.append(f"quality audit CSV missing: {display_path(quality_csv_path)}")
        quality_by_id: dict[str, dict[str, str]] = {}
    else:
        quality_by_id = {str(row.get("query_id") or ""): row for row in read_csv(quality_csv_path)}
    block_index = build_block_index(parsed_blocks)

    rows: list[dict[str, Any]] = []
    for evidence in evidence_rows:
        query_id = str(evidence.get("query_id") or "")
        quality = quality_by_id.get(query_id, {})
        if not (truthy(evidence.get("table_like_context_candidate")) or truthy(quality.get("table_like_context_candidate"))):
            continue
        rows.append(audit_table_candidate(evidence, quality, block_index))

    counts = build_counts(rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and rows:
        status = "PASS_WITH_TABLE_LIKE_CONTEXT_AUDIT"
    report = {
        "schema_version": "pdf_supplemental_table_like_context_audit_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "diagnostic_table_like_context_candidate_audit_only",
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
        "table_like_context_is_candidate_only": True,
        "recommended_next_action_enum": RECOMMENDED_ACTIONS,
        "input_artifacts": [
            artifact_identity(evidence_path),
            artifact_identity(parsed_blocks_path),
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
            "table_semantics_ready is a heuristic context-readiness signal, not a parser/table-semantics success claim.",
            "Rows missing clear row, column, and value support are kept diagnostic-only.",
            "NEEDS_TABLE_PARSER rows should move to a separate parser/evidence-contract task before any answer-quality claim.",
        ],
    }
    return {"report": report, "rows": rows}


def audit_table_candidate(
    evidence: Mapping[str, Any],
    quality: Mapping[str, str],
    block_index: Mapping[tuple[str, int, str], Mapping[str, Any]],
) -> dict[str, Any]:
    citation = evidence.get("citation") if isinstance(evidence.get("citation"), Mapping) else {}
    relative_path = str(evidence.get("relative_path") or citation.get("relative_path") or "")
    page_no = to_int(citation.get("page_no")) or 0
    block = block_index.get((relative_path, page_no, bbox_key(citation.get("bbox"))), {})
    source_text = compact_text(
        evidence.get("evidence_text")
        or evidence.get("evidence_text_excerpt")
        or block.get("text")
        or evidence.get("nearby_context")
        or ""
    )
    profile = table_signal_profile(source_text, block)
    table_semantics_ready = bool(
        profile["row_label_candidate_present"]
        and profile["column_label_candidate_present"]
        and profile["value_candidate_present"]
        and profile["aligned_text_signal"]
    )
    action = recommended_next_action(profile, table_semantics_ready, source_text, block)
    return {
        "query_id": evidence.get("query_id") or quality.get("query_id"),
        "dataset_source": evidence.get("dataset_source") or quality.get("dataset_source"),
        "file_name": evidence.get("file_name") or quality.get("file_name"),
        "page_no": page_no,
        "block_id": block_id(relative_path, page_no, block),
        "table_like_context_candidate": True,
        "numeric_density": profile["numeric_density"],
        "aligned_text_signal": profile["aligned_text_signal"],
        "row_label_candidate_present": profile["row_label_candidate_present"],
        "column_label_candidate_present": profile["column_label_candidate_present"],
        "value_candidate_present": profile["value_candidate_present"],
        "unit_candidate_present": profile["unit_candidate_present"],
        "table_semantics_ready": table_semantics_ready,
        "recommended_next_action": action,
        "anchor_type": evidence.get("anchor_type") or quality.get("anchor_type"),
        "table_like_score": block.get("table_like_score"),
        "table_like_reasons": block.get("table_like_reasons") or [],
        "source_text_chars": len(source_text),
        "source_text_excerpt": short_text(source_text, 240),
    }


def table_signal_profile(text: str, block: Mapping[str, Any]) -> dict[str, Any]:
    numeric_density = numeric_density_for(text, block)
    reasons = block.get("table_like_reasons") if isinstance(block.get("table_like_reasons"), list) else []
    aligned_text_signal = bool(
        "aligned_numeric_lines" in reasons
        or "short_token_grid" in reasons
        or "repeated_separators" in reasons
        or (to_float(block.get("table_like_line_numeric_ratio")) or 0.0) >= 0.5
        or aligned_line_signal(text)
    )
    return {
        "numeric_density": numeric_density,
        "aligned_text_signal": aligned_text_signal,
        "row_label_candidate_present": bool(ROW_LABEL_RE.search(text or "")),
        "column_label_candidate_present": bool(COLUMN_LABEL_RE.search(text or "")),
        "value_candidate_present": bool(VALUE_RE.search(text or "")),
        "unit_candidate_present": bool(UNIT_RE.search(text or "")),
    }


def numeric_density_for(text: str, block: Mapping[str, Any]) -> float:
    existing = to_float(block.get("table_like_numeric_token_ratio"))
    if existing is not None:
        return round(existing, 4)
    tokens = re.findall(r"[0-9A-Za-z가-힣.,%()/-]+", text or "")
    if not tokens:
        return 0.0
    numeric = [token for token in tokens if re.search(r"\d", token)]
    return round(len(numeric) / len(tokens), 4)


def aligned_line_signal(text: str) -> bool:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    numeric_lines = sum(1 for line in lines if VALUE_RE.search(line))
    short_lines = sum(1 for line in lines if 1 <= len(re.findall(r"\S+", line)) <= 8)
    return numeric_lines / len(lines) >= 0.5 and short_lines / len(lines) >= 0.5


def recommended_next_action(
    profile: Mapping[str, Any],
    table_semantics_ready: bool,
    source_text: str,
    block: Mapping[str, Any],
) -> str:
    if not source_text.strip():
        return "NEEDS_MANUAL_REVIEW"
    if table_semantics_ready:
        return "SUFFICIENT_FOR_EXTRACTIVE_CONTEXT_ONLY"
    if not profile["aligned_text_signal"] and profile["numeric_density"] < 0.15:
        return "NOT_TABLE_LIKE_AFTER_AUDIT"
    if profile["value_candidate_present"] and profile["numeric_density"] >= 0.25:
        return "NEEDS_TABLE_PARSER"
    if truthy(block.get("ocr_used")) or truthy(block.get("lower_trust_ocr")):
        return "NEEDS_MANUAL_REVIEW"
    return "KEEP_AS_CONTEXT_ONLY"


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


def block_id(relative_path: str, page_no: int, block: Mapping[str, Any]) -> str:
    explicit = block.get("block_id")
    if explicit:
        return str(explicit)
    block_index = block.get("block_index")
    if block_index is None:
        return f"{relative_path}#p{page_no}:b?"
    return f"{relative_path}#p{page_no}:b{block_index}"


def build_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    dataset_action: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        dataset_action[str(row.get("dataset_source") or "unknown")][str(row.get("recommended_next_action") or "unknown")] += 1
    return {
        "table_like_context_candidate_count": len(rows),
        "table_semantics_ready_count": sum(1 for row in rows if row.get("table_semantics_ready") is True),
        "table_semantics_success_claimed": False,
        "numeric_density_median": median([float(row.get("numeric_density") or 0.0) for row in rows]),
        "aligned_text_signal_count": sum(1 for row in rows if row.get("aligned_text_signal") is True),
        "row_label_candidate_present_count": sum(1 for row in rows if row.get("row_label_candidate_present") is True),
        "column_label_candidate_present_count": sum(1 for row in rows if row.get("column_label_candidate_present") is True),
        "value_candidate_present_count": sum(1 for row in rows if row.get("value_candidate_present") is True),
        "unit_candidate_present_count": sum(1 for row in rows if row.get("unit_candidate_present") is True),
        "recommended_next_action_counts": sorted_counter(Counter(str(row.get("recommended_next_action") or "unknown") for row in rows)),
        "dataset_source_counts": sorted_counter(Counter(str(row.get("dataset_source") or "unknown") for row in rows)),
        "dataset_source_action_counts": {key: sorted_counter(counter) for key, counter in sorted(dataset_action.items())},
    }


def median(values: list[float]) -> float | None:
    if not values:
        return None
    values = sorted(values)
    midpoint = len(values) // 2
    if len(values) % 2:
        return round(values[midpoint], 4)
    return round((values[midpoint - 1] + values[midpoint]) / 2, 4)


def read_jsonl_or_block(path: Path, label: str, blockers: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return []
    return [row for row in iter_jsonl(path)]


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
    parser.add_argument("--parsed-blocks", default=None)
    parser.add_argument("--quality-csv", default=str(DEFAULT_QUALITY_CSV))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
