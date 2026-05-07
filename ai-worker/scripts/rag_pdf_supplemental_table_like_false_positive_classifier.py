"""Classify supplemental PDF table-like false-positive risks.

This diagnostic-only post-analysis reads existing supplemental table probe
outputs and parsed PyMuPDF blocks. It preserves prior recommended actions while
adding a separate false-positive classification. It does not claim table
semantics success or mutate PageIndex, parsers, DB/SearchUnit, candidates,
baselines, gold, denominators, or policy state.
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
    ARTIFACT_ROOT,
    COMMON_GUARDRAILS,
    REPORT_DIR,
    artifact_identity,
    display_path,
    iter_jsonl,
    read_json,
    resolve_path,
    short_text,
    sorted_counter,
    supplemental_output_path_blockers,
    truthy,
    utc_timestamp,
    write_csv,
    write_json,
)


DEFAULT_ARTIFACT_DIR = ARTIFACT_ROOT / "pdf_supplemental_elec_lh_20260506T_supplemental_diag"
DEFAULT_PROBE_JSON = REPORT_DIR / "rag_pdf_supplemental_table_semantics_probe.json"
DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_table_like_false_positive_classification.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_table_like_false_positive_classification.csv"

REQUIRED_GUARDRAILS: dict[str, Any] = {
    **COMMON_GUARDRAILS,
    "local_llm_run": False,
    "pageindex_rerun": False,
    "pageindex_improvement_claimed": False,
    "actual_llm_answer_generation_run": False,
    "actual_generated_answer_output": False,
    "answer_draft_is_actual_generated_llm_answer": False,
    "table_semantics_success_claimed": False,
    "row_column_value_semantics_claimed": False,
}

CLASSIFICATION_ENUM = [
    "REAL_NUMERIC_GRID_TABLE",
    "BULLET_OR_FORMULA_CONTEXT",
    "REFERENCE_CODE_FRAGMENT",
    "FOOTER_OR_PRINT_ARTIFACT",
    "SECTION_OR_LIST_FRAGMENT",
    "TABLE_TITLE_OR_HEADER_ONLY",
    "AMBIGUOUS_TABLE_LIKE_CONTEXT",
    "NOT_TABLE_LIKE_AFTER_REVIEW",
]

CSV_FIELDS = [
    "query_id",
    "dataset_source",
    "file_name",
    "page_no",
    "block_id",
    "prior_recommended_next_action",
    "table_semantics_candidate_ready",
    "classification",
    "classification_reason",
    "noise_flags",
    "numeric_density",
    "row_label_candidate_present",
    "column_label_candidate_present",
    "value_candidate_present",
    "unit_or_header_context_present",
    "table_text_excerpt",
]

FOOTER_RE = re.compile(
    r"(\.indd\b|시안\.?indd|출력\s*일시|인쇄\s*일시|\bpage\s*\d+\b|\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*(오전|오후)\s*\d{1,2}:\d{2})",
    re.IGNORECASE,
)
REFERENCE_RE = re.compile(r"\b(?:LHCS|KCS)\s*(?:\d+\s*){2,}", re.IGNORECASE)
SECTION_RE = re.compile(r"^\s*(?:\(?\d+(?:\.\d+){0,4}\)?|[①-⑳]|\(\d+\)|·|-)\s*")
FORMULA_RE = re.compile(r"(×|=|\{|\}|산식|부과방식|적용전력량|요금단가|단가\s*[×x]|비율|초과\s*전력량요금)")
TABLE_HEADER_RE = re.compile(r"(구분|항목|사용량|기본요금|전력량요금|요금|금액|단가|임대료|보증금|면적|세대|조건)")
VALUE_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = resolve_path(args.artifact_dir)
    probe_json_path = resolve_path(args.table_semantics_probe)
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

    payload = build_classification(
        artifact_dir=artifact_dir,
        probe_json_path=probe_json_path,
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


def build_classification(
    *,
    artifact_dir: Path,
    probe_json_path: Path,
    parsed_blocks_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    probe_payload = read_json_or_block(probe_json_path, "table semantics probe JSON", blockers)
    validate_guardrails("table_semantics_probe", probe_payload, blockers)
    parsed_block_text_by_id = parsed_block_text_index(parsed_blocks_path, blockers)
    probe_rows = probe_payload.get("rows") if isinstance(probe_payload.get("rows"), list) else []
    rows = [
        classify_probe_row(row, parsed_block_text_by_id)
        for row in probe_rows
        if isinstance(row, Mapping)
    ]
    counts = build_counts(rows)
    status = "PASS" if not blockers else "FAIL_CLOSED_INPUT_ERROR"
    if not blockers and rows:
        status = "PASS_WITH_TABLE_LIKE_FALSE_POSITIVE_CLASSIFICATION"
    report = {
        "schema_version": "pdf_supplemental_table_like_false_positive_classification_v1",
        "generated_at": utc_timestamp(),
        "status": status,
        **REQUIRED_GUARDRAILS,
        "analysis_role": "diagnostic_table_like_false_positive_classification_only",
        "classification_enum": CLASSIFICATION_ENUM,
        "prior_recommended_next_action_preserved": True,
        "table_like_context_is_candidate_only": True,
        "input_artifacts": [
            artifact_identity(probe_json_path),
            artifact_identity(parsed_blocks_path),
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
            "CAN_BUILD_TABLE_EVIDENCE_OBJECT is preserved as a prior candidate action, not table semantics success.",
            "False-positive classes isolate footer/print artifacts, reference-code fragments, and section/list fragments before any table evidence object work.",
        ],
    }
    return {"report": report, "rows": rows}


def classify_probe_row(row: Mapping[str, Any], parsed_block_text_by_id: Mapping[str, str]) -> dict[str, Any]:
    block_id = str(row.get("block_id") or "")
    full_text = parsed_block_text_by_id.get(block_id) or str(row.get("table_text_excerpt") or "")
    text = compact_text(full_text)
    row_present = bool(row.get("row_label_candidates"))
    column_present = bool(row.get("column_label_candidates"))
    value_present = bool(row.get("value_candidates"))
    unit_or_header = truthy(row.get("unit_or_header_context_present"))
    numeric_density = to_float(row.get("numeric_density")) or 0.0
    classification, reason, flags = classify_table_like_context(
        text=text,
        dataset_source=str(row.get("dataset_source") or ""),
        numeric_density=numeric_density,
        aligned_text_signal=truthy(row.get("aligned_text_signal")),
        row_label_candidate_present=row_present,
        column_label_candidate_present=column_present,
        value_candidate_present=value_present,
        unit_or_header_context_present=unit_or_header,
    )
    return {
        "query_id": row.get("query_id"),
        "dataset_source": row.get("dataset_source"),
        "file_name": row.get("file_name"),
        "page_no": row.get("page_no"),
        "block_id": block_id,
        "prior_recommended_next_action": row.get("recommended_next_action"),
        "table_semantics_candidate_ready": truthy(row.get("table_semantics_candidate_ready")),
        "classification": classification,
        "classification_reason": reason,
        "noise_flags": flags,
        "numeric_density": numeric_density,
        "row_label_candidate_present": row_present,
        "column_label_candidate_present": column_present,
        "value_candidate_present": value_present,
        "unit_or_header_context_present": unit_or_header,
        "table_text_excerpt": short_text(text, 260),
    }


def classify_table_like_context(
    *,
    text: str,
    dataset_source: str,
    numeric_density: float,
    aligned_text_signal: bool,
    row_label_candidate_present: bool,
    column_label_candidate_present: bool,
    value_candidate_present: bool,
    unit_or_header_context_present: bool,
) -> tuple[str, str, list[str]]:
    flags: list[str] = []
    if is_footer_or_print_artifact(text):
        flags.append("footer_or_print_artifact_signal")
        return "FOOTER_OR_PRINT_ARTIFACT", "print/footer metadata rather than table evidence", flags
    if is_reference_code_fragment(text):
        flags.append("lhcs_or_kcs_reference_code_signal")
        if is_short_fragment(text) or "따른다" in text or dataset_source == "lh":
            return "REFERENCE_CODE_FRAGMENT", "LHCS/KCS reference-code or follows-clause fragment", flags
    if is_formula_context(text):
        flags.append("formula_or_bullet_signal")
        return "BULLET_OR_FORMULA_CONTEXT", "formula, fee calculation, or bullet context rather than row/column/value table semantics", flags
    if is_header_only(text, column_label_candidate_present, value_candidate_present, numeric_density):
        flags.append("header_or_title_only_signal")
        return "TABLE_TITLE_OR_HEADER_ONLY", "title/header/unit context without enough row/value evidence", flags
    if is_section_or_list_fragment(text, dataset_source, numeric_density, row_label_candidate_present, column_label_candidate_present):
        flags.append("section_or_list_fragment_signal")
        return "SECTION_OR_LIST_FRAGMENT", "short section/list fragment over-detected as table-like", flags
    if is_real_numeric_grid(
        text=text,
        numeric_density=numeric_density,
        aligned_text_signal=aligned_text_signal,
        value_candidate_present=value_candidate_present,
    ):
        flags.append("numeric_grid_signal")
        if not row_label_candidate_present:
            flags.append("row_label_missing_requires_layout_parser")
        return "REAL_NUMERIC_GRID_TABLE", "numeric grid/table-like value block; still candidate-only", flags
    if not value_candidate_present and numeric_density < 0.12:
        flags.append("weak_value_signal")
        return "NOT_TABLE_LIKE_AFTER_REVIEW", "weak value/table signal after review", flags
    if row_label_candidate_present and column_label_candidate_present and value_candidate_present and unit_or_header_context_present:
        flags.append("candidate_signals_present_but_not_success")
    return "AMBIGUOUS_TABLE_LIKE_CONTEXT", "table-like context remains ambiguous after false-positive review", flags


def is_footer_or_print_artifact(text: str) -> bool:
    return bool(FOOTER_RE.search(text or ""))


def is_reference_code_fragment(text: str) -> bool:
    if not REFERENCE_RE.search(text or ""):
        return False
    tokens = re.findall(r"[A-Za-z가-힣0-9.()]+", text or "")
    code_tokens = re.findall(r"\b(?:LHCS|KCS)\b|\b\d{2}\b", text or "", flags=re.IGNORECASE)
    return len(code_tokens) >= 3 or len(tokens) <= 24


def is_formula_context(text: str) -> bool:
    if FORMULA_RE.search(text or ""):
        return True
    lines = nonempty_lines(text)
    numbered = sum(1 for line in lines if re.match(r"^\s*\d+[.)]?\s*", line))
    return numbered >= 2 and any(":" in line or "：" in line for line in lines)


def is_header_only(text: str, column_present: bool, value_present: bool, numeric_density: float) -> bool:
    if not column_present and not TABLE_HEADER_RE.search(text or ""):
        return False
    if not value_present:
        return True
    values = VALUE_RE.findall(text or "")
    return len(values) <= 2 and numeric_density < 0.35 and len(compact_text(text)) <= 80


def is_section_or_list_fragment(
    text: str,
    dataset_source: str,
    numeric_density: float,
    row_present: bool,
    column_present: bool,
) -> bool:
    lines = nonempty_lines(text)
    if dataset_source == "lh" and (is_short_fragment(text) or "제출물" in text or "참고 기준" in text):
        return True
    if len(lines) <= 3 and SECTION_RE.search(text or "") and numeric_density < 0.45 and not (row_present and column_present):
        return True
    return False


def is_real_numeric_grid(*, text: str, numeric_density: float, aligned_text_signal: bool, value_candidate_present: bool) -> bool:
    values = VALUE_RE.findall(text or "")
    if numeric_density >= 0.55 and len(values) >= 4:
        return True
    return aligned_text_signal and value_candidate_present and len(values) >= 6


def parsed_block_text_index(path: Path, blockers: list[str]) -> dict[str, str]:
    if not path.exists():
        blockers.append(f"parsed blocks JSONL missing: {display_path(path)}")
        return {}
    result: dict[str, str] = {}
    for block in iter_jsonl(path):
        relative_path = str(block.get("relative_path") or "")
        page_no = block.get("page_no")
        block_index = block.get("block_index")
        block_id = f"{relative_path}#p{page_no}:b{block_index}" if relative_path and block_index is not None else ""
        if block_id:
            result[block_id] = str(block.get("text") or "")
    return result


def build_counts(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_prior: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_prior[str(row.get("prior_recommended_next_action") or "UNKNOWN")][str(row.get("classification") or "UNKNOWN")] += 1
    return {
        "table_like_context_candidate_count": len(rows),
        "classification_counts": sorted_counter(Counter(str(row.get("classification") or "UNKNOWN") for row in rows)),
        "prior_recommended_next_action_counts": sorted_counter(Counter(str(row.get("prior_recommended_next_action") or "UNKNOWN") for row in rows)),
        "classification_by_prior_recommended_next_action": {
            key: sorted_counter(counter)
            for key, counter in sorted(by_prior.items())
        },
        "footer_or_print_artifact_count": sum(1 for row in rows if row.get("classification") == "FOOTER_OR_PRINT_ARTIFACT"),
        "reference_code_fragment_count": sum(1 for row in rows if row.get("classification") == "REFERENCE_CODE_FRAGMENT"),
        "section_or_list_fragment_count": sum(1 for row in rows if row.get("classification") == "SECTION_OR_LIST_FRAGMENT"),
        "real_numeric_grid_table_count": sum(1 for row in rows if row.get("classification") == "REAL_NUMERIC_GRID_TABLE"),
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
    }


def validate_guardrails(label: str, payload: Mapping[str, Any], blockers: list[str]) -> None:
    required_false = {
        "promotion_evidence": False,
        "official_denominator_changed": False,
        "codex_gold_policy_decision_applied": False,
        "pdf_c7_policy_decision_applied": False,
        "external_cloud_llm_run": False,
        "local_llm_run": False,
        "live_llm_answer_generation_run": False,
        "optional_judge_run": False,
        "pageindex_rerun": False,
        "pageindex_improvement_claimed": False,
        "retrieval_tuning_applied": False,
        "reranking_applied": False,
        "parser_expansion_applied": False,
        "db_mutation_applied": False,
        "searchunit_mutation_applied": False,
        "candidate_artifact_changed": False,
        "immutable_baseline_changed": False,
        "table_semantics_success_claimed": False,
        "row_column_value_semantics_claimed": False,
    }
    for key, expected in required_false.items():
        if key not in payload:
            blockers.append(f"{label}.{key} is missing")
        elif payload.get(key) is not expected:
            blockers.append(f"{label}.{key} expected {expected!r}, got {payload.get(key)!r}")
    if payload.get("evidence_role") != "diagnostic":
        blockers.append(f"{label}.evidence_role expected diagnostic, got {payload.get('evidence_role')!r}")
    if payload.get("blockers"):
        blockers.append(f"{label} has blockers: {payload.get('blockers')!r}")


def read_json_or_block(path: Path, label: str, blockers: list[str]) -> dict[str, Any]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return {}
    return read_json(path)


def nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def is_short_fragment(text: str) -> bool:
    return len(compact_text(text)) <= 90


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def to_float(value: Any) -> float | None:
    try:
        if value in ("", None):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--table-semantics-probe", default=str(DEFAULT_PROBE_JSON))
    parser.add_argument("--parsed-blocks", default=None)
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
