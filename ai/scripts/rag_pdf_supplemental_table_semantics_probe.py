"""Probe supplemental PDF table-like row/column/value candidates.

This script is diagnostic-only. It reads existing PyMuPDF parsed blocks and
answer-evidence objects, then records candidate row/column/value signals. It
does not change production parser artifacts and does not claim table-semantics
success.
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
    bbox_to_list,
    display_path,
    iter_jsonl,
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


DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_table_semantics_probe.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_table_semantics_probe.csv"
DEFAULT_QUALITY_CSV = REPORT_DIR / "rag_pdf_supplemental_answer_evidence_quality_audit.csv"

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

RECOMMENDED_NEXT_ACTIONS = [
    "KEEP_AS_EXTRACTIVE_CONTEXT",
    "CAN_BUILD_TABLE_EVIDENCE_OBJECT",
    "NEEDS_TABLE_PARSER",
    "NEEDS_MANUAL_REVIEW",
    "NOT_TABLE_AFTER_PROBE",
]

CSV_FIELDS = [
    "query_id",
    "dataset_source",
    "file_name",
    "page_no",
    "block_id",
    "bbox",
    "table_like_context_candidate",
    "table_text_excerpt",
    "numeric_density",
    "aligned_text_signal",
    "row_label_candidates",
    "column_label_candidates",
    "value_candidates",
    "unit_candidates",
    "unit_or_header_context_present",
    "row_column_value_alignment_confidence",
    "table_semantics_candidate_ready",
    "table_semantics_success_claimed",
    "recommended_next_action",
]

VALUE_RE = re.compile(
    r"\d[\d,]*(?:\.\d+)?(?:\s*(?:원/kWh|kWh|kW|kw|원|만원|천원|%|㎡|m2|개월|년|월|일|세대|호|단계|배))?",
    re.IGNORECASE,
)
UNIT_RE = re.compile(r"(원/kWh|kWh|kW|kw|원|만원|천원|%|㎡|m2|개월|년|월|일|세대|호|단계|배)", re.IGNORECASE)
ROW_COLON_RE = re.compile(r"^\s*(?P<label>[^:：]{1,36})[:：]")
ROW_STEP_RE = re.compile(r"\b(?P<label>[1-9]\s*단계)\b")
ROW_RANGE_RE = re.compile(
    r"(?P<label>\d[\d,]*(?:\.\d+)?\s*(?:kWh|kw|kW|㎡|m2)?\s*(?:초과|이하|까지|~|-)\s*\d?[\d,]*(?:\.\d+)?\s*(?:kWh|kw|kW|㎡|m2)?(?:\s*사용)?)",
    re.IGNORECASE,
)
ROW_KNOWN_RE = re.compile(r"(?P<label>기타계절|하계|동계|경부하|중간부하|최대부하|전체시간|고\s*압\s*[A-C]?|저\s*압)", re.IGNORECASE)
COLUMN_TERMS = [
    "구분",
    "항목",
    "사용량",
    "기본",
    "전력량",
    "요금",
    "금액",
    "단가",
    "임대료",
    "보증금",
    "면적",
    "세대",
    "소득",
    "기간",
    "하계",
    "동계",
    "기타",
    "전용",
    "공급",
    "조건",
]
COLUMN_RE = re.compile("|".join(re.escape(term) for term in COLUMN_TERMS), re.IGNORECASE)


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

    payload = build_probe(
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


def build_probe(
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
    quality_rows = read_csv_or_block(quality_csv_path, "quality audit CSV", blockers)
    quality_by_id = {str(row.get("query_id") or ""): row for row in quality_rows}
    block_index = build_block_index(parsed_blocks)
    page_index = build_page_index(parsed_blocks)

    rows: list[dict[str, Any]] = []
    for evidence in evidence_rows:
        query_id = str(evidence.get("query_id") or "")
        quality = quality_by_id.get(query_id, {})
        if not (truthy(evidence.get("table_like_context_candidate")) or truthy(quality.get("table_like_context_candidate"))):
            continue
        rows.append(probe_row(evidence, quality, block_index, page_index))

    counts = build_counts(rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and rows:
        status = "PASS_WITH_TABLE_SEMANTICS_CANDIDATE_PROBE"
    report = {
        "schema_version": "pdf_supplemental_table_semantics_probe_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "diagnostic_table_row_column_value_candidate_probe_only",
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
        "table_semantics_success_claimed_default": False,
        "table_semantics_candidate_ready_rule": [
            "row_label_candidate_present",
            "column_label_candidate_present",
            "value_candidate_present",
            "unit_or_header_context_present",
        ],
        "recommended_next_action_enum": RECOMMENDED_NEXT_ACTIONS,
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
        "rows": rows,
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "Candidates are extracted from existing PyMuPDF parsed block text plus page-neighbor bbox heuristics.",
            "table_semantics_candidate_ready is a candidate-readiness signal only; it is not table parser success.",
            "NEEDS_TABLE_PARSER remains an evidence-contract signal before any factual table-value answer lane.",
        ],
    }
    return {"report": report, "rows": rows}


def probe_row(
    evidence: Mapping[str, Any],
    quality: Mapping[str, str],
    block_index: Mapping[tuple[str, int, str], Mapping[str, Any]],
    page_index: Mapping[tuple[str, int], list[Mapping[str, Any]]],
) -> dict[str, Any]:
    citation = evidence.get("citation") if isinstance(evidence.get("citation"), Mapping) else {}
    relative_path = str(evidence.get("relative_path") or citation.get("relative_path") or "")
    page_no = to_int(citation.get("page_no")) or 0
    citation_bbox = bbox_to_list(citation.get("bbox"))
    block = block_index.get((relative_path, page_no, bbox_key(citation.get("bbox"))), {})
    if not block:
        block = nearest_block(relative_path, page_no, citation_bbox, page_index) or {}
    block_bbox = bbox_to_list(block.get("bbox")) or citation_bbox
    block_text = str(block.get("text") or evidence.get("evidence_text") or "")
    neighbor_text = nearby_header_text(relative_path, page_no, block_bbox, page_index)
    combined_header_text = "\n".join(part for part in [neighbor_text, block_text] if part)
    row_candidates = row_label_candidates(block_text)
    column_candidates = column_label_candidates(combined_header_text)
    value_candidates = value_candidates_for(block_text)
    unit_candidates = unit_candidates_for(combined_header_text)
    numeric_density = numeric_density_for(block_text)
    aligned = aligned_text_signal(block_text, block, block_bbox)
    unit_or_header_context_present = bool(strong_unit_candidates(unit_candidates) or column_candidates)
    ready = bool(row_candidates and column_candidates and value_candidates and unit_or_header_context_present)
    confidence = alignment_confidence(
        row_present=bool(row_candidates),
        column_present=bool(column_candidates),
        value_present=bool(value_candidates),
        unit_or_header_context_present=unit_or_header_context_present,
        aligned_text_signal=aligned,
        numeric_density=numeric_density,
    )
    action = recommended_next_action(
        text=block_text,
        numeric_density=numeric_density,
        aligned_text_signal=aligned,
        value_present=bool(value_candidates),
        candidate_ready=ready,
        confidence=confidence,
    )
    return {
        "query_id": evidence.get("query_id") or quality.get("query_id"),
        "dataset_source": evidence.get("dataset_source") or quality.get("dataset_source"),
        "file_name": evidence.get("file_name") or quality.get("file_name"),
        "page_no": page_no,
        "block_id": block_id(relative_path, page_no, block),
        "bbox": block_bbox or citation.get("bbox"),
        "table_like_context_candidate": True,
        "table_text_excerpt": short_text(compact_text(block_text), 260),
        "numeric_density": numeric_density,
        "aligned_text_signal": aligned,
        "row_label_candidates": row_candidates,
        "column_label_candidates": column_candidates,
        "value_candidates": value_candidates,
        "unit_candidates": unit_candidates,
        "unit_or_header_context_present": unit_or_header_context_present,
        "row_column_value_alignment_confidence": confidence,
        "table_semantics_candidate_ready": ready,
        "table_semantics_success_claimed": False,
        "recommended_next_action": action,
    }


def row_label_candidates(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for line_index, line in enumerate(nonempty_lines(text)):
        if len(candidates) >= 6:
            break
        match = row_label_match(line)
        if not match:
            continue
        label = match
        cleaned = compact_text(label).strip(" :-:：")
        if not cleaned or cleaned in {item["text"] for item in candidates}:
            continue
        candidates.append({
            "text": short_text(cleaned, 80),
            "line_index": line_index,
            "source": "pymupdf_block_text",
            "confidence": 0.55 if VALUE_RE.search(line) else 0.4,
        })
    return candidates


def row_label_match(line: str) -> str | None:
    compact = compact_text(line)
    if not compact:
        return None
    if re.fullmatch(r"(?:LHCS|KCS)\s*(?:\d+\s*){2,}", compact):
        return None
    colon = ROW_COLON_RE.search(compact)
    if colon and has_hangul_or_alpha(colon.group("label")):
        return colon.group("label")
    step = ROW_STEP_RE.search(compact)
    if step:
        return step.group("label")
    ranged = ROW_RANGE_RE.search(compact)
    if ranged:
        return ranged.group("label")
    known = ROW_KNOWN_RE.search(compact)
    if known and VALUE_RE.search(compact):
        return known.group("label")
    return None


def column_label_candidates(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in COLUMN_RE.finditer(text or ""):
        term = match.group(0)
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append({
            "text": term,
            "source": "pymupdf_block_or_bbox_neighbor_header",
            "confidence": 0.55,
        })
        if len(candidates) >= 8:
            break
    return candidates


def value_candidates_for(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_index, line in enumerate(nonempty_lines(text)):
        for match in VALUE_RE.finditer(line):
            value = compact_text(match.group(0))
            if value in seen:
                continue
            seen.add(value)
            candidates.append({
                "text": value,
                "line_index": line_index,
                "source": "pymupdf_block_text",
                "confidence": 0.65 if UNIT_RE.search(value) or UNIT_RE.search(line) else 0.45,
            })
            if len(candidates) >= 10:
                return candidates
    return candidates


def unit_candidates_for(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in UNIT_RE.finditer(text or ""):
        unit = match.group(0)
        key = unit.lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append({
            "text": unit,
            "source": "pymupdf_block_or_bbox_neighbor_header",
            "confidence": 0.6,
        })
        if len(candidates) >= 6:
            break
    return candidates


def strong_unit_candidates(candidates: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    weak_date_units = {"년", "월", "일", "단계"}
    return [candidate for candidate in candidates if str(candidate.get("text") or "").lower() not in weak_date_units]


def numeric_density_for(text: str) -> float:
    tokens = re.findall(r"[0-9A-Za-z가-힣.,%()/-]+", text or "")
    if not tokens:
        return 0.0
    numeric = [token for token in tokens if re.search(r"\d", token)]
    return round(len(numeric) / len(tokens), 4)


def aligned_text_signal(text: str, block: Mapping[str, Any], bbox: list[float] | None) -> bool:
    reasons = block.get("table_like_reasons") if isinstance(block.get("table_like_reasons"), list) else []
    if {"aligned_numeric_lines", "short_token_grid", "repeated_separators"}.intersection(reasons):
        return True
    lines = nonempty_lines(text)
    if len(lines) < 2:
        return False
    numeric_lines = sum(1 for line in lines if VALUE_RE.search(line))
    short_lines = sum(1 for line in lines if 1 <= len(re.findall(r"\S+", line)) <= 10)
    wide_bbox = bool(bbox and len(bbox) == 4 and (bbox[2] - bbox[0]) >= 180)
    return numeric_lines / len(lines) >= 0.5 and (short_lines / len(lines) >= 0.5 or wide_bbox)


def alignment_confidence(
    *,
    row_present: bool,
    column_present: bool,
    value_present: bool,
    unit_or_header_context_present: bool,
    aligned_text_signal: bool,
    numeric_density: float,
) -> float:
    score = 0.0
    if row_present:
        score += 0.25
    if column_present:
        score += 0.25
    if value_present:
        score += 0.25
    if unit_or_header_context_present:
        score += 0.15
    if aligned_text_signal:
        score += 0.08
    if numeric_density >= 0.25:
        score += 0.02
    return round(min(score, 1.0), 4)


def recommended_next_action(
    *,
    text: str,
    numeric_density: float,
    aligned_text_signal: bool,
    value_present: bool,
    candidate_ready: bool,
    confidence: float,
) -> str:
    if not compact_text(text):
        return "NEEDS_MANUAL_REVIEW"
    if candidate_ready and confidence >= 0.75:
        return "CAN_BUILD_TABLE_EVIDENCE_OBJECT"
    if not value_present and numeric_density < 0.15 and not aligned_text_signal:
        return "NOT_TABLE_AFTER_PROBE"
    if value_present and (numeric_density >= 0.25 or aligned_text_signal):
        return "NEEDS_TABLE_PARSER"
    if aligned_text_signal or len(compact_text(text)) >= 40:
        return "KEEP_AS_EXTRACTIVE_CONTEXT"
    return "NEEDS_MANUAL_REVIEW"


def build_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    action_counts = Counter(str(row.get("recommended_next_action") or "UNKNOWN") for row in rows)
    return {
        "table_like_context_candidate_count": len(rows),
        "table_semantics_candidate_ready_count": sum(1 for row in rows if row.get("table_semantics_candidate_ready") is True),
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
        "row_label_candidate_present_count": sum(1 for row in rows if row.get("row_label_candidates")),
        "column_label_candidate_present_count": sum(1 for row in rows if row.get("column_label_candidates")),
        "value_candidate_present_count": sum(1 for row in rows if row.get("value_candidates")),
        "unit_or_header_context_present_count": sum(1 for row in rows if row.get("unit_or_header_context_present") is True),
        "aligned_text_signal_count": sum(1 for row in rows if row.get("aligned_text_signal") is True),
        "recommended_next_action_counts": sorted_counter(action_counts),
        "dataset_source_counts": sorted_counter(Counter(str(row.get("dataset_source") or "unknown") for row in rows)),
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


def build_page_index(blocks: list[Mapping[str, Any]]) -> dict[tuple[str, int], list[Mapping[str, Any]]]:
    result: dict[tuple[str, int], list[Mapping[str, Any]]] = defaultdict(list)
    for block in blocks:
        result[(str(block.get("relative_path") or ""), to_int(block.get("page_no")) or 0)].append(block)
    for key in list(result):
        result[key].sort(key=lambda row: (bbox_y0(row.get("bbox")), to_int(row.get("block_index")) or 0))
    return dict(result)


def nearest_block(
    relative_path: str,
    page_no: int,
    bbox: list[float] | None,
    page_index: Mapping[tuple[str, int], list[Mapping[str, Any]]],
) -> Mapping[str, Any] | None:
    if not bbox:
        return None
    blocks = page_index.get((relative_path, page_no), [])
    best: tuple[float, Mapping[str, Any]] | None = None
    for block in blocks:
        block_bbox = bbox_to_list(block.get("bbox"))
        if not block_bbox:
            continue
        distance = bbox_center_distance(bbox, block_bbox)
        if best is None or distance < best[0]:
            best = (distance, block)
    return best[1] if best and best[0] <= 12.0 else None


def nearby_header_text(
    relative_path: str,
    page_no: int,
    bbox: list[float] | None,
    page_index: Mapping[tuple[str, int], list[Mapping[str, Any]]],
) -> str:
    if not bbox:
        return ""
    nearby: list[str] = []
    for block in page_index.get((relative_path, page_no), []):
        block_bbox = bbox_to_list(block.get("bbox"))
        if not block_bbox:
            continue
        vertical_gap = bbox[1] - block_bbox[3]
        horizontal_overlap = overlap_width(bbox, block_bbox) > 0
        if 0 <= vertical_gap <= 90 and horizontal_overlap:
            nearby.append(str(block.get("text") or ""))
        if len(nearby) >= 4:
            break
    return "\n".join(nearby)


def block_id(relative_path: str, page_no: int, block: Mapping[str, Any]) -> str:
    explicit = block.get("block_id")
    if explicit:
        return str(explicit)
    index = block.get("block_index")
    if index is None:
        return f"{relative_path}#p{page_no}:b?"
    return f"{relative_path}#p{page_no}:b{index}"


def bbox_center_distance(a: list[float], b: list[float]) -> float:
    ax = (a[0] + a[2]) / 2
    ay = (a[1] + a[3]) / 2
    bx = (b[0] + b[2]) / 2
    by = (b[1] + b[3]) / 2
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def overlap_width(a: list[float], b: list[float]) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0]))


def bbox_y0(value: Any) -> float:
    bbox = bbox_to_list(value)
    if not bbox:
        return 0.0
    return to_float(bbox[1]) or 0.0


def nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def first_present(values: Any) -> str | None:
    for value in values:
        if value:
            return str(value)
    return None


def has_hangul_or_alpha(value: str) -> bool:
    return bool(re.search(r"[가-힣A-Za-z]", value or ""))


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
    parser.add_argument("--parsed-blocks", default=None)
    parser.add_argument("--quality-csv", default=str(DEFAULT_QUALITY_CSV))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
