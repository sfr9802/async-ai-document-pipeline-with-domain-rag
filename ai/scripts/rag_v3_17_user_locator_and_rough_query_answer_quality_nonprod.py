from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import rag_v3_16_pdf_xlsx_final_llm_answer_quality_review_nonprod as v316
from rag_local_llm_expected_answer_generation_v1 import (
    DEFAULT_BACKEND,
    DEFAULT_MODEL,
    local_llm_entry_blockers,
    resolve_base_url,
)


ROOT = v316.ROOT
if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))
if str(ROOT / "ai" / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))

from app.capabilities.rag.source_registry import assemble_evidence_bundle, render_citation
from app.capabilities.rag_orchestrator.tool_registry import (
    ROUTE_LANES,
    ToolRegistry,
    build_default_tool_registry,
)


RUN_ID = "official_answer_citation_agentic_loop_run_v3_17_user_locator_and_rough_query_answer_quality_nonprod"
REPORT_DIR = v316.REPORT_DIR
STATUS_JSONL = v316.STATUS_JSONL
PROGRESS_DOC = v316.PROGRESS_DOC
MEASUREMENTS_DOC = v316.MEASUREMENTS_DOC
TRIAGE_DOC = v316.TRIAGE_DOC
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID

STATUS = "DIAGNOSTIC_V3_17_USER_LOCATOR_ROUGH_QUERY_ANSWER_QUALITY_NONPROD_READY"
FAIL_CLOSED_STATUS = "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
EVENT_TYPE = "diagnostic_v3_17_user_locator_rough_query_answer_quality_nonprod"
PROMPT_VERSION = "v3_17_user_locator_rough_query_answer_quality_prompt_v1"

SAMPLE_LIMITS = {
    "xlsx_user_provided_file_sheet_cell": 8,
    "xlsx_user_provided_range_or_table": 8,
    "xlsx_rough_query_answerable": 8,
    "xlsx_rough_query_unanswerable_or_ambiguous": 6,
    "pdf_user_provided_page_or_section_control": 4,
    "pdf_rough_query_control": 4,
}
MAX_EVIDENCE_BUNDLES = 3
MAX_RESOLVED_SOURCE_ATOMS = 3
LEAKAGE_SCAN_FIELDS = (
    "final_answer",
    "abstain_reason",
    "selected_evidence_excerpt",
    "locator_bounds_answerability_reason",
    "locator_summary",
    "rendered_citations",
)
LEAKAGE_PATTERNS = {
    "local_storage_path": re.compile(r"local-storage[\\/]|input_file[\\/]", flags=re.IGNORECASE),
    "windows_absolute_path": re.compile(r"\b[A-Za-z]:\\"),
    "posix_runtime_path": re.compile(r"(?<![A-Za-z0-9_])/(?:tmp|var|home|mnt|Users|local-storage)/"),
    "internal_search_view_name": re.compile(r"\bSearchView\b"),
    "internal_source_atom_name": re.compile(r"\bSourceAtom\b"),
    "internal_layer_name": re.compile(r"\bL[0-8]_[A-Z0-9_]+\b"),
}

OUTPUTS = {
    "summary_json": OUTPUT_DIR / "summary.json",
    "metrics_json": OUTPUT_DIR / "metrics.json",
    "per_family_json": OUTPUT_DIR / "per_family.json",
    "per_query_jsonl": OUTPUT_DIR / "per_query.jsonl",
    "responses_jsonl": OUTPUT_DIR / "responses.jsonl",
    "review_packet_csv": OUTPUT_DIR / "review_packet.csv",
    "review_packet_jsonl": OUTPUT_DIR / "review_packet.jsonl",
    "guardrail_audit_json": OUTPUT_DIR / "guardrail_audit.json",
    "leakage_audit_jsonl": OUTPUT_DIR / "leakage_audit.jsonl",
    "prompt_manifest_json": OUTPUT_DIR / "prompt_manifest.json",
    "user_locator_parse_audit_jsonl": OUTPUT_DIR / "user_locator_parse_audit.jsonl",
    "user_locator_resolution_audit_jsonl": OUTPUT_DIR / "user_locator_resolution_audit.jsonl",
    "rough_query_bucket_audit_jsonl": OUTPUT_DIR / "rough_query_bucket_audit.jsonl",
    "tool_registry_json": OUTPUT_DIR / "tool_registry.json",
    "route_policy_audit_jsonl": OUTPUT_DIR / "route_policy_audit.jsonl",
    "runtime_materialization_plan_json": OUTPUT_DIR / "runtime_materialization_plan.json",
    "latency_budget_contract_json": OUTPUT_DIR / "latency_budget_contract.json",
}

USER_REVIEW_FIELDS = (
    "user_review_like",
    "user_review_note",
    "user_expected_answer_decision",
    "user_supporting_evidence_decision",
    "user_relevance_decision",
    "user_answerability_decision",
)

REVIEW_COLUMNS = (
    "review_id",
    "query_id",
    "diagnostic_case_id",
    "bucket",
    "source_family",
    "query",
    "final_answer",
    "rendered_citations",
    "query_user_provided_locator",
    "user_locator_type",
    "user_locator_text",
    "user_locator_resolution_status",
    "route_lane",
    "route_policy_reason",
    "allow_unbounded_fallback",
    "locator_bounds_answerability",
    "locator_bounds_answerability_reason",
    "selected_source_atom_ids",
    "locator_summary",
    "selected_evidence_excerpt",
    "diagnostic_flags",
    "abstain_reason",
    "over_abstain_review_candidate",
    "xlsx_value_formatting_risk",
    "unsupported_claim_risk",
    *USER_REVIEW_FIELDS,
    "official_metric_candidate",
    "promotion_evidence",
)

MATERIALIZATION_CLASSES = v316.MATERIALIZATION_CLASSES
RUNTIME_LAYER_NAMES = v316.RUNTIME_LAYER_NAMES
LAYER_MATERIALIZATION_CLASSIFICATION = v316.LAYER_MATERIALIZATION_CLASSIFICATION


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="microseconds") + "Z"


def clean(value: Any) -> str:
    return v316.clean(value)


def sanitize_internal_references(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    text = re.sub(
        r"(?i)(?:[A-Za-z]:\\|/)?(?:[^\\/\s]+[\\/])*local-storage[\\/][^\\/\s]+[\\/]input_file[\\/]",
        "",
        text,
    )
    return re.sub(r"(?i)\binput_file[\\/]", "", text)


def sanitize_json_strings(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_internal_references(value)
    if isinstance(value, Mapping):
        return {key: sanitize_json_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json_strings(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_json_strings(item) for item in value)
    return value


def leakage_hits(row: Mapping[str, Any]) -> list[str]:
    hits: list[str] = []
    for field in LEAKAGE_SCAN_FIELDS:
        text = clean(row.get(field))
        for name, pattern in LEAKAGE_PATTERNS.items():
            if pattern.search(text):
                hits.append(f"{field}:{name}")
    return hits


def as_mapping(value: Any) -> Mapping[str, Any]:
    return v316.as_mapping(value)


def read_json(path: Path) -> dict[str, Any]:
    return v316.read_json(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v316.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    v316.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    v316.write_jsonl(path, rows)


def sha256_file(path: Path) -> str:
    return v316.sha256_file(path)


def sha256_text(value: str) -> str:
    return v316.sha256_text(value)


def repo_relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return v316.ratio(numerator, denominator)


def source_atom_ids_from_row(row: Mapping[str, Any]) -> list[str]:
    return v316.source_atom_ids_from_row(row)


def row_diagnostic_flags(row: Mapping[str, Any]) -> dict[str, Any]:
    flags = row.get("diagnostic_flags")
    if isinstance(flags, str):
        try:
            return as_mapping(json.loads(flags))
        except json.JSONDecodeError:
            return {}
    return as_mapping(flags)


def normalize_locator_text(value: str) -> str:
    return re.sub(r"[\s_./\\(){}\[\]:'\"`!?,;|-]+", "", clean(value).casefold())


def a1_to_tuple(cell: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,6})", clean(cell).upper())
    if not match:
        return None
    column = 0
    for char in match.group(1):
        column = column * 26 + (ord(char) - ord("A") + 1)
    return int(match.group(2)), column


def range_contains_cell(range_text: str, cell_text: str) -> bool:
    parts = clean(range_text).upper().split(":", 1)
    if len(parts) != 2:
        return False
    start = a1_to_tuple(parts[0])
    end = a1_to_tuple(parts[1])
    cell = a1_to_tuple(cell_text)
    if not start or not end or not cell:
        return False
    row_min, row_max = sorted((start[0], end[0]))
    col_min, col_max = sorted((start[1], end[1]))
    return row_min <= cell[0] <= row_max and col_min <= cell[1] <= col_max


def unique_preserve(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = clean(value).strip(" .,!?:;\"'")
        if not item:
            continue
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def parse_user_locator_text(
    query: str,
    *,
    artifact_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    del artifact_context
    query_text = clean(query)
    ranges = unique_preserve(re.findall(r"\b[A-Z]{1,3}[1-9][0-9]{0,6}:[A-Z]{1,3}[1-9][0-9]{0,6}\b", query_text.upper()))
    query_without_ranges = query_text
    for range_text in ranges:
        query_without_ranges = re.sub(re.escape(range_text), " ", query_without_ranges, flags=re.IGNORECASE)
    cells = unique_preserve(re.findall(r"\b[A-Z]{1,3}[1-9][0-9]{0,6}\b", query_without_ranges.upper()))
    r1c1 = unique_preserve(re.findall(r"\bR[1-9][0-9]{0,6}C[1-9][0-9]{0,6}\b", query_text.upper()))
    files = unique_preserve(
        match.strip()
        for match in re.findall(r"([A-Za-z0-9가-힣_(). \-]+?\.xlsx)", query_text, flags=re.IGNORECASE)
    )
    sheet_terms: list[str] = []
    sheet_after = re.findall(
        r"(?:시트|sheet)\s*[:=]?\s*['\"]?([^'\"!,;]+?)(?=\s*(?:셀|cell|범위|range|값|의|에서|$))",
        query_text,
        flags=re.IGNORECASE,
    )
    sheet_before = re.findall(r"([A-Za-z0-9가-힣_ \-]{1,40})\s*(?:시트|sheet)", query_text, flags=re.IGNORECASE)
    sheet_terms.extend(sheet_after)
    sheet_terms.extend(sheet_before)
    sheets = unique_preserve(sheet_terms)
    table_terms = unique_preserve(
        re.findall(
            r"(?:표|테이블|table)\s*[:=]\s*([A-Za-z0-9가-힣_ \-]{1,40}?)(?=\s*(?:셀|cell|범위|range|값|의|에서|$))",
            query_text,
            flags=re.IGNORECASE,
        )
    )
    section_terms = unique_preserve(
        re.findall(r"(?:절|섹션|section)\s*[:=]?\s*([A-Za-z0-9가-힣_ \-]{1,50})", query_text, flags=re.IGNORECASE)
    )
    page_matches = re.findall(
        r"(?:page|p\.?|쪽|페이지)\s*([0-9]{1,4})|([0-9]{1,4})\s*(?:쪽|페이지)",
        query_text,
        flags=re.IGNORECASE,
    )
    flat_pages = unique_preserve([item for pair in page_matches for item in pair if item])

    locator_types: list[str] = []
    if files:
        locator_types.append("file")
    if sheets:
        locator_types.append("sheet")
    if cells or r1c1:
        locator_types.append("cell")
    if ranges:
        locator_types.append("range")
    if table_terms:
        locator_types.append("table")
    if flat_pages:
        locator_types.append("page")
    if section_terms:
        locator_types.append("section")
    locator_types = unique_preserve(locator_types)
    if not locator_types:
        locator_type = "none"
    elif len(locator_types) == 1:
        locator_type = locator_types[0]
    else:
        locator_type = "mixed"
    locator_text_parts = [*files, *sheets, *cells, *ranges, *r1c1, *table_terms, *flat_pages, *section_terms]
    locator_text = " | ".join(unique_preserve(locator_text_parts))
    confidence = 0.0
    if locator_types:
        confidence = min(0.95, 0.55 + 0.1 * len(locator_types) + (0.1 if any((cells, ranges, flat_pages)) else 0.0))
    return {
        "query_user_provided_locator": bool(locator_types),
        "user_locator_type": locator_type,
        "user_locator_text": locator_text,
        "user_locator_parse_confidence": round(confidence, 3),
        "locator_terms": {
            "file": files,
            "sheet": sheets,
            "cell": cells + r1c1,
            "range": ranges,
            "table": table_terms,
            "page": flat_pages,
            "section": section_terms,
        },
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_text_used": False,
    }


def atom_locator(atom: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = as_mapping(atom.get("raw_locator"))
    payload = as_mapping(atom.get("canonical_citation_payload"))
    merged: dict[str, Any] = dict(payload)
    merged.update({key: value for key, value in raw.items() if clean(value)})
    return merged


def locator_field_values(atom: Mapping[str, Any], *fields: str) -> list[str]:
    locator = atom_locator(atom)
    values: list[str] = []
    for field in fields:
        value = locator.get(field)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            values.extend(clean(item) for item in value)
        else:
            values.append(clean(value))
    values.extend([clean(atom.get("source_identity")), clean(atom.get("workbook_id")), clean(atom.get("workbook_version_id"))])
    return [value for value in values if value]


def text_matches_any(term: str, values: Sequence[str]) -> bool:
    needle = normalize_locator_text(term)
    if not needle:
        return False
    return any(needle in normalize_locator_text(value) or normalize_locator_text(value) in needle for value in values if value)


def resolve_user_locator_to_source_atoms(
    parsed_locator: Mapping[str, Any],
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
    source_family: str,
    top_k: int = MAX_RESOLVED_SOURCE_ATOMS,
) -> dict[str, Any]:
    if not parsed_locator.get("query_user_provided_locator"):
        return {
            "user_locator_resolved_to_sourceatom": False,
            "user_locator_resolution_status": "NO_USER_LOCATOR",
            "selected_source_atom_ids": [],
            "selected_candidate_count": 0,
            "resolution_notes": "query did not contain user-provided locator text",
            "vector_payload_used_as_evidence_truth": False,
        }

    terms = as_mapping(parsed_locator.get("locator_terms"))
    scored: list[tuple[int, str, str]] = []
    for source_atom_id, atom in source_registry.items():
        if source_family and clean(atom.get("source_family")).upper() != clean(source_family).upper():
            continue
        locator = atom_locator(atom)
        score = 0
        notes: list[str] = []
        for term in terms.get("file", []) or []:
            if text_matches_any(clean(term), locator_field_values(atom, "workbook", "source_path", "file_name")):
                score += 4
                notes.append("file")
        for term in terms.get("sheet", []) or []:
            if text_matches_any(clean(term), locator_field_values(atom, "sheet", "sheet_name")):
                score += 3
                notes.append("sheet")
        for term in terms.get("cell", []) or []:
            cell = clean(locator.get("cell"))
            range_text = clean(locator.get("range"))
            if cell and normalize_locator_text(term) == normalize_locator_text(cell):
                score += 5
                notes.append("cell")
            elif range_text and range_contains_cell(range_text, clean(term).upper()):
                score += 2
                notes.append("cell_in_range")
        for term in terms.get("range", []) or []:
            if text_matches_any(clean(term), locator_field_values(atom, "range", "table_range")):
                score += 5
                notes.append("range")
        for term in terms.get("table", []) or []:
            if text_matches_any(clean(term), locator_field_values(atom, "table", "table_name", "range_name")):
                score += 4
                notes.append("table")
        for term in terms.get("page", []) or []:
            page_value = clean(locator.get("page"))
            sheet_value = clean(locator.get("sheet"))
            if page_value and clean(term) == page_value:
                score += 4
                notes.append("page")
            elif sheet_value and text_matches_any(clean(term), [sheet_value]):
                score += 3
                notes.append("page_sheet")
        for term in terms.get("section", []) or []:
            if text_matches_any(clean(term), locator_field_values(atom, "section", "section_title", "row_label")):
                score += 2
                notes.append("section")
        if score > 0:
            scored.append((score, source_atom_id, ",".join(unique_preserve(notes))))
    scored.sort(key=lambda item: (-item[0], item[1]))
    if scored:
        top_score = scored[0][0]
        top_tied = [item for item in scored if item[0] == top_score]
        selected_source = top_tied if len(top_tied) > 1 else scored[:1]
    else:
        selected_source = []
    selected = [source_atom_id for _, source_atom_id, _ in selected_source[:top_k]]
    if not selected:
        status = "UNRESOLVED"
    elif len(selected_source) > 1:
        status = "AMBIGUOUS_MULTIPLE_SOURCEATOMS"
    else:
        status = "RESOLVED"
    return {
        "user_locator_resolved_to_sourceatom": bool(selected),
        "user_locator_resolution_status": status,
        "selected_source_atom_ids": selected,
        "selected_candidate_count": len(scored),
        "resolution_notes": "; ".join(
            f"{source_atom_id}:{notes}:score={score}" for score, source_atom_id, notes in selected_source[:top_k]
        ),
        "vector_payload_used_as_evidence_truth": False,
    }


def route_policy_for_case(
    *,
    parsed_locator: Mapping[str, Any],
    bucket: str,
    source_family: str,
    registry: ToolRegistry,
) -> dict[str, Any]:
    route_decision = registry.route_policy(
        user_locator_present=bool(parsed_locator.get("query_user_provided_locator")),
        rough_query_present="rough_query" in clean(bucket),
        supported_source_family=clean(source_family).upper() in {"PDF", "XLSX"},
    )
    return route_decision.to_dict()


def locator_bounds_answerability(
    *,
    parsed_locator: Mapping[str, Any],
    resolution: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, str]:
    if not parsed_locator.get("query_user_provided_locator"):
        return {
            "locator_bounds_answerability": "NOT_USER_LOCATOR",
            "locator_bounds_answerability_reason": "query has no query-owned locator bounds",
        }
    status = clean(resolution.get("user_locator_resolution_status"))
    if status == "UNRESOLVED":
        return {
            "locator_bounds_answerability": "UNANSWERABLE_FROM_LOCATOR_BOUNDS",
            "locator_bounds_answerability_reason": "query-owned locator could not be resolved to bounded evidence ids",
        }
    if status == "AMBIGUOUS_MULTIPLE_SOURCEATOMS":
        return {
            "locator_bounds_answerability": "AMBIGUOUS_FROM_LOCATOR_BOUNDS",
            "locator_bounds_answerability_reason": "query-owned locator resolves to multiple tied bounded evidence candidates",
        }
    if status == "RESOLVED" and clean(evidence.get("selected_evidence_excerpt")):
        return {
            "locator_bounds_answerability": "ANSWERABLE_FROM_LOCATOR_BOUNDS",
            "locator_bounds_answerability_reason": "bounded registry evidence is available for the query-owned locator",
        }
    return {
        "locator_bounds_answerability": "UNANSWERABLE_FROM_LOCATOR_BOUNDS",
        "locator_bounds_answerability_reason": "resolved locator did not produce answer-ready bounded evidence",
    }


def build_input_paths() -> dict[str, Path]:
    return {
        "v3_16_summary_json": v316.OUTPUTS["summary_json"],
        "v3_16_review_packet_jsonl": v316.OUTPUTS["review_packet_jsonl"],
        "v3_16_responses_jsonl": v316.OUTPUTS["responses_jsonl"],
        "v3_16_per_query_jsonl": v316.OUTPUTS["per_query_jsonl"],
        "v3_15_per_query_jsonl": v316.v315.OUTPUTS["per_query_jsonl"],
        "v3_14_per_query_jsonl": v316.v314.OUTPUTS["per_query_jsonl"],
        "source_registry_jsonl": v316.v314.v392.SOURCE_REGISTRY_JSONL,
    }


def lineage_entry(path: Path) -> dict[str, Any]:
    return {"exists": path.exists(), "path": repo_relative(path), "sha256": sha256_file(path) if path.exists() else ""}


def build_input_lineage(input_paths: Mapping[str, Path]) -> dict[str, Any]:
    return {key: lineage_entry(path) for key, path in input_paths.items()}


def require_input_artifacts(input_paths: Mapping[str, Path]) -> None:
    missing = [repo_relative(path) for path in input_paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required v3_17 input artifacts: " + ", ".join(missing))


def choose_cases(cases: Sequence[Mapping[str, Any]], *, bucket: str, limit: int) -> list[Mapping[str, Any]]:
    filtered = [case for case in cases if clean(case.get("sample_bucket")) == bucket]
    return filtered[:limit]


def first_atom(case: Mapping[str, Any], source_registry: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any]:
    for source_atom_id in source_atom_ids_from_row(case):
        atom = as_mapping(source_registry.get(source_atom_id))
        if atom:
            return atom
    return {}


def xlsx_locator_query(atom: Mapping[str, Any], *, mode: str) -> str:
    locator = atom_locator(atom)
    workbook = clean(locator.get("workbook")) or "workbook.xlsx"
    sheet = clean(locator.get("sheet")) or "Sheet1"
    cell = clean(locator.get("cell"))
    range_text = clean(locator.get("range"))
    row_label = clean(locator.get("row_label"))
    column = clean(locator.get("target_column") or locator.get("column_label"))
    if mode == "file_sheet_cell" and cell:
        return f"{workbook} 시트 {sheet} 셀 {cell} 값 알려줘"
    if range_text:
        return f"{workbook} {sheet} 시트 범위 {range_text}에서 뭐 확인돼?"
    if row_label and column:
        return f"{workbook} {sheet} 시트 표 {row_label} {column} 좀 봐줘"
    return f"{workbook} {sheet} 시트 표에서 확인 가능한 값 알려줘"


def xlsx_rough_query(atom: Mapping[str, Any]) -> str:
    locator = atom_locator(atom)
    row_label = clean(locator.get("row_label"))
    column = clean(locator.get("target_column") or locator.get("column_label"))
    if row_label and column:
        return f"{row_label} {column} 뭐야"
    if column:
        return f"{column} 값 좀"
    return "이 표에서 뭐라고 돼 있어?"


def pdf_locator_query(atom: Mapping[str, Any]) -> str:
    locator = atom_locator(atom)
    page = clean(locator.get("page")) or "1"
    row_label = clean(locator.get("row_label") or locator.get("section_title"))
    if row_label:
        return f"{page}페이지 {row_label} 부분만 보고 답해줘"
    return f"{page}페이지에서 확인되는 내용 알려줘"


def pdf_rough_query(atom: Mapping[str, Any]) -> str:
    locator = atom_locator(atom)
    row_label = clean(locator.get("row_label") or locator.get("section_title"))
    if row_label:
        return f"{row_label} 그거 뭐야"
    return "그 페이지 내용 짧게 알려줘"


def build_diagnostic_cases() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    upstream_cases, _sample_reasons = v316.build_sample_cases()
    source_registry = v316.load_source_registry_for_cases(upstream_cases)
    cases: list[dict[str, Any]] = []

    def add_case(base: Mapping[str, Any], *, bucket: str, query: str, selected_source_atom_ids: Sequence[str]) -> None:
        cases.append(
            {
                "review_id": f"v3_17_{len(cases) + 1:03d}",
                "diagnostic_case_id": f"{bucket}:{clean(base.get('query_id')) or len(cases) + 1}",
                "query_id": clean(base.get("query_id")),
                "bucket": bucket,
                "source_family": clean(base.get("source_family")).upper(),
                "query": query,
                "source_row": dict(as_mapping(base.get("source_row"))),
                "selected_source_atom_ids": list(selected_source_atom_ids),
                "artifact_context": {},
            }
        )

    xlsx_answer_ready = choose_cases(
        upstream_cases,
        bucket="xlsx_answer_ready",
        limit=SAMPLE_LIMITS["xlsx_user_provided_file_sheet_cell"]
        + SAMPLE_LIMITS["xlsx_user_provided_range_or_table"]
        + SAMPLE_LIMITS["xlsx_rough_query_answerable"],
    )
    no_candidate = choose_cases(
        upstream_cases,
        bucket="xlsx_no_candidate_abstain",
        limit=SAMPLE_LIMITS["xlsx_rough_query_unanswerable_or_ambiguous"],
    )
    pdf_answer_ready = choose_cases(
        upstream_cases,
        bucket="pdf_answer_ready_control",
        limit=SAMPLE_LIMITS["pdf_user_provided_page_or_section_control"],
    )
    pdf_residual = choose_cases(
        upstream_cases,
        bucket="pdf_residual_control",
        limit=SAMPLE_LIMITS["pdf_rough_query_control"],
    )

    for base in xlsx_answer_ready[: SAMPLE_LIMITS["xlsx_user_provided_file_sheet_cell"]]:
        atom = first_atom(base, source_registry)
        add_case(
            base,
            bucket="xlsx_user_provided_file_sheet_cell",
            query=xlsx_locator_query(atom, mode="file_sheet_cell"),
            selected_source_atom_ids=[],
        )
    offset = SAMPLE_LIMITS["xlsx_user_provided_file_sheet_cell"]
    for base in xlsx_answer_ready[offset : offset + SAMPLE_LIMITS["xlsx_user_provided_range_or_table"]]:
        atom = first_atom(base, source_registry)
        add_case(
            base,
            bucket="xlsx_user_provided_range_or_table",
            query=xlsx_locator_query(atom, mode="range_or_table"),
            selected_source_atom_ids=[],
        )
    offset += SAMPLE_LIMITS["xlsx_user_provided_range_or_table"]
    for base in xlsx_answer_ready[offset : offset + SAMPLE_LIMITS["xlsx_rough_query_answerable"]]:
        atom = first_atom(base, source_registry)
        add_case(
            base,
            bucket="xlsx_rough_query_answerable",
            query=xlsx_rough_query(atom),
            selected_source_atom_ids=source_atom_ids_from_row(base),
        )
    for base in no_candidate:
        add_case(
            base,
            bucket="xlsx_rough_query_unanswerable_or_ambiguous",
            query="이거 값 좀 봐줘",
            selected_source_atom_ids=[],
        )
    cases.append(
        {
            "review_id": f"v3_17_{len(cases) + 1:03d}",
            "diagnostic_case_id": "xlsx_user_provided_file_sheet_cell:synthetic_unresolved_user_locator",
            "query_id": "v3_17_synthetic_unresolved_user_locator",
            "bucket": "xlsx_user_provided_file_sheet_cell",
            "source_family": "XLSX",
            "query": "missing_locator_workbook.xlsx 시트 MissingSheet 셀 Z999 값 알려줘",
            "source_row": {},
            "selected_source_atom_ids": [],
            "artifact_context": {},
        }
    )
    for base in pdf_answer_ready:
        atom = first_atom(base, source_registry)
        add_case(
            base,
            bucket="pdf_user_provided_page_or_section_control",
            query=pdf_locator_query(atom),
            selected_source_atom_ids=[],
        )
    for base in pdf_residual:
        atom = first_atom(base, source_registry)
        add_case(
            base,
            bucket="pdf_rough_query_control",
            query=pdf_rough_query(atom),
            selected_source_atom_ids=source_atom_ids_from_row(base),
        )

    reasons: dict[str, Any] = {}
    for bucket in SAMPLE_LIMITS:
        selected = [case for case in cases if case["bucket"] == bucket]
        reasons[bucket] = {
            "requested": SAMPLE_LIMITS[bucket],
            "selected": len(selected),
            "shortfall_reason": "" if len(selected) >= SAMPLE_LIMITS[bucket] else "fewer_safe_rows_available",
            "sample_selection_strategy": "v3_16_sourceatom_backed_cases_with_query_owned_locator_and_rough_query_variants",
        }
    return cases, reasons


def source_atom_ids_for_cases(cases: Sequence[Mapping[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for case in cases:
        ids.update(source_atom_ids_from_row(case))
        source_row = as_mapping(case.get("source_row"))
        ids.update(source_atom_ids_from_row(source_row))
    return {source_atom_id for source_atom_id in ids if source_atom_id}


def load_source_registry_for_cases(cases: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return v316.v314.load_source_registry_subset(source_atom_ids_for_cases(cases))


def citation_to_text(index: int, rendered: Mapping[str, Any]) -> str:
    return v316.citation_to_text(index, rendered)


def evidence_for_source_atom_ids(
    source_atom_ids: Sequence[str],
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
    max_evidence_chars: int,
) -> dict[str, Any]:
    selected_ids = list(source_atom_ids[:MAX_EVIDENCE_BUNDLES])
    evidence_blocks: list[str] = []
    citation_texts: list[str] = []
    locator_summaries: list[str] = []
    rendered_payloads: list[dict[str, Any]] = []
    for index, source_atom_id in enumerate(selected_ids, start=1):
        atom = as_mapping(source_registry.get(source_atom_id))
        if not atom:
            continue
        bundle_result = assemble_evidence_bundle(
            source_atom_id,
            source_registry=source_registry,
            mode="runtime_answer",
        )
        if not bundle_result.get("valid"):
            continue
        bundle = as_mapping(bundle_result.get("evidence_bundle"))
        rendered = render_citation(source_atom_id, source_registry=source_registry)
        rendered_payloads.append(dict(rendered))
        citation_text = citation_to_text(index, rendered)
        citation_texts.append(citation_text)
        locator_summaries.append(citation_text)
        matched = sanitize_internal_references(
            bundle.get("matched_text_or_value") or atom.get("normalized_text_or_value_snapshot")
        )
        if matched:
            evidence_blocks.append(f"[S{index}] {matched[:max_evidence_chars]}")
    return {
        "selected_source_atom_ids": selected_ids,
        "selected_evidence_excerpt": "\n".join(evidence_blocks)[:max_evidence_chars],
        "rendered_citations": " | ".join(citation_texts),
        "locator_summary": " | ".join(locator_summaries),
        "rendered_payloads": rendered_payloads,
        "bundle_truncated_count": max(0, len(source_atom_ids) - len(selected_ids)),
    }


def build_generation_prompt(
    *,
    query: str,
    source_family: str,
    bucket: str,
    evidence_excerpt: str,
    locator_summary: str,
    user_locator_text: str,
    resolution_status: str,
) -> tuple[str, str]:
    system_prompt = (
        "You are a local diagnostic RAG answer generator. Return exactly one JSON object. "
        "The answer must be Korean, concise, and grounded only in the supplied evidence. "
        "Never invent values or expose internal implementation names."
    )
    status_text = {
        "RESOLVED": "위치가 근거 후보로 확인됨",
        "AMBIGUOUS_MULTIPLE_SOURCEATOMS": "여러 후보 위치가 있어 모호함",
        "UNRESOLVED": "위치를 찾지 못함",
        "NO_USER_LOCATOR": "사용자가 위치를 따로 언급하지 않음",
    }.get(clean(resolution_status), clean(resolution_status) or "확인 안 됨")
    user_prompt = f"""질문:
{query}

문서 유형: {source_family}
리뷰 버킷: {bucket}
사용자가 언급한 위치: {clean(user_locator_text) or "없음"}
위치 해석 상태: {status_text}

제공 근거:
{clean(evidence_excerpt) or "제공된 근거가 없습니다."}

인용 위치:
{clean(locator_summary) or "인용 가능한 위치 정보가 없습니다."}

작성 규칙:
- 한국어로 간결하게 답하세요.
- 제공 근거만 사용하고 값을 새로 만들지 마세요.
- XLSX는 필요할 때 시트, 범위, 셀을 사용자가 읽기 쉬운 표현으로 언급하세요.
- 근거가 부족하면 "제공된 근거만으로는 답변하기 어렵습니다"라고 말하세요.
- 질문이 모호하면 부족한 조건을 한 문장으로 짚어 주세요.
- 반환 형식은 JSON 한 개이며 키는 answer, citations, abstain_reason 입니다.
- citations는 citation_id와 locator를 가진 객체 배열이며 가능한 경우 S1, S2 형식을 쓰세요.
"""
    return system_prompt, user_prompt


def parse_answer(raw_response: str) -> tuple[str, list[Mapping[str, Any]], str, bool, bool, str]:
    return v316.parse_answer(raw_response)


def call_llm(
    *,
    llm_client: Callable[[str, str], str] | None,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    timeout_seconds: int,
) -> str:
    return v316.call_llm(
        llm_client=llm_client,
        base_url=base_url,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )


def deterministic_abstain_answer(*, reason: str) -> tuple[str, list[Mapping[str, Any]], str]:
    if reason == "user_locator_unresolved":
        return (
            "질문에 언급된 위치를 현재 제공된 근거에서 찾을 수 없습니다. 파일, 시트, 셀 또는 범위를 확인한 뒤 다시 요청해 주세요.",
            [],
            "user_locator_unresolved",
        )
    return (
        "제공된 근거만으로는 답변하기 어렵습니다. 필요한 파일, 시트, 셀/범위 또는 항목 조건이 부족합니다.",
        [],
        "insufficient_or_ambiguous_evidence",
    )


def build_row_flags(
    *,
    source_family: str,
    bucket: str,
    final_answer: str,
    citations: Sequence[Mapping[str, Any]],
    evidence_excerpt: str,
    resolution_status: str,
) -> dict[str, Any]:
    no_evidence = not clean(evidence_excerpt)
    abstain = "제공된 근거만으로는" in final_answer or "찾을 수 없습니다" in final_answer or bool(no_evidence)
    unsupported = bool(final_answer) and no_evidence and not abstain
    xlsx_value_formatting_risk = (
        clean(source_family).upper() == "XLSX"
        and bool(clean(evidence_excerpt))
        and not abstain
        and any(char.isdigit() for char in final_answer)
    )
    over_abstain = bool(clean(evidence_excerpt)) and abstain and resolution_status not in {"UNRESOLVED", "NO_USER_LOCATOR"}
    return {
        "abstain_quality_flag": bool(abstain),
        "unsupported_claim_risk": bool(unsupported),
        "unsupported_claim_risk_counted": bool(unsupported),
        "hallucination_risk_flag": bool(unsupported),
        "citation_missing_flag": bool(not citations and bool(clean(evidence_excerpt)) and not abstain),
        "xlsx_value_formatting_risk": bool(xlsx_value_formatting_risk),
        "over_abstain_review_candidate": bool(over_abstain),
        "rough_query": "rough_query" in bucket,
        "user_locator_bucket": "user_provided" in bucket,
    }


def generate_rows(
    cases: Sequence[Mapping[str, Any]],
    *,
    source_registry: Mapping[str, Mapping[str, Any]],
    tool_registry: ToolRegistry,
    model: str,
    base_url: str,
    max_tokens: int,
    timeout_seconds: int,
    llm_client: Callable[[str, str], str] | None,
    max_evidence_chars: int,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    per_query_rows: list[dict[str, Any]] = []
    response_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    parse_audit_rows: list[dict[str, Any]] = []
    resolution_audit_rows: list[dict[str, Any]] = []
    rough_audit_rows: list[dict[str, Any]] = []
    route_policy_audit_rows: list[dict[str, Any]] = []

    for case in cases:
        query = clean(case.get("query"))
        bucket = clean(case.get("bucket"))
        family = clean(case.get("source_family")).upper()
        parsed = parse_user_locator_text(query, artifact_context=as_mapping(case.get("artifact_context")))
        resolution = resolve_user_locator_to_source_atoms(
            parsed,
            source_registry=source_registry,
            source_family=family,
            top_k=MAX_RESOLVED_SOURCE_ATOMS,
        )
        if parsed["query_user_provided_locator"]:
            selected_ids = list(resolution["selected_source_atom_ids"])
        else:
            selected_ids = source_atom_ids_from_row(case)
        evidence = evidence_for_source_atom_ids(
            selected_ids,
            source_registry=source_registry,
            max_evidence_chars=max_evidence_chars,
        )
        route_policy = route_policy_for_case(
            parsed_locator=parsed,
            bucket=bucket,
            source_family=family,
            registry=tool_registry,
        )
        locator_answerability = locator_bounds_answerability(
            parsed_locator=parsed,
            resolution=resolution,
            evidence=evidence,
        )
        resolution_status = clean(resolution["user_locator_resolution_status"])
        should_abstain_without_llm = (
            resolution_status == "UNRESOLVED"
            or (not parsed["query_user_provided_locator"] and not clean(evidence["selected_evidence_excerpt"]))
        )
        if should_abstain_without_llm:
            final_answer, citations, abstain_reason = deterministic_abstain_answer(
                reason="user_locator_unresolved" if resolution_status == "UNRESOLVED" else "insufficient"
            )
            raw_response = json.dumps(
                {"answer": final_answer, "citations": citations, "abstain_reason": abstain_reason},
                ensure_ascii=False,
            )
            parse_ok = True
            malformed_response = False
            parse_error_reason = ""
            elapsed_ms = 0.0
            prompt_sha = ""
            llm_executed = False
        else:
            system_prompt, user_prompt = build_generation_prompt(
                query=query,
                source_family=family,
                bucket=bucket,
                evidence_excerpt=evidence["selected_evidence_excerpt"],
                locator_summary=evidence["locator_summary"],
                user_locator_text=clean(parsed["user_locator_text"]),
                resolution_status=resolution_status,
            )
            started = time.perf_counter()
            raw_response = call_llm(
                llm_client=llm_client,
                base_url=base_url,
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
            final_answer, citations, abstain_reason, parse_ok, malformed_response, parse_error_reason = parse_answer(
                raw_response
            )
            final_answer = sanitize_internal_references(final_answer)
            abstain_reason = sanitize_internal_references(abstain_reason)
            citations = sanitize_json_strings(citations)
            prompt_sha = sha256_text(system_prompt + "\n" + user_prompt)
            llm_executed = True
        flags = build_row_flags(
            source_family=family,
            bucket=bucket,
            final_answer=final_answer,
            citations=citations,
            evidence_excerpt=evidence["selected_evidence_excerpt"],
            resolution_status=resolution_status,
        )
        diagnostic_flags = {
            **flags,
            "parse_ok": parse_ok,
            "malformed_response_flag": malformed_response,
            "parse_error_reason": parse_error_reason,
            "abstain_reason_present": bool(abstain_reason),
            "diagnostic_only": True,
            "official_metric_candidate": False,
            "promotion_evidence": False,
            "query_user_provided_locator": bool(parsed["query_user_provided_locator"]),
            "user_locator_resolution_status": resolution_status,
            "llm_executed": llm_executed,
        }
        selected_output_ids = list(evidence["selected_source_atom_ids"])
        source_row = as_mapping(case.get("source_row"))
        retrieval_latency_ms = round(float(source_row.get("total_retrieval_latency_ms") or 0.0), 3)
        common = {
            "run_id": RUN_ID,
            "review_id": clean(case.get("review_id")),
            "diagnostic_case_id": clean(case.get("diagnostic_case_id")),
            "query_id": clean(case.get("query_id")),
            "bucket": bucket,
            "source_family": family,
            "query_text_sha256": sha256_text(query),
            "selected_source_atom_ids": selected_output_ids,
            "selected_source_atom_count": len(selected_output_ids),
            "query_user_provided_locator": bool(parsed["query_user_provided_locator"]),
            "user_locator_type": clean(parsed["user_locator_type"]),
            "user_locator_text": clean(parsed["user_locator_text"]),
            "user_locator_parse_confidence": parsed["user_locator_parse_confidence"],
            "user_locator_resolved_to_sourceatom": bool(resolution["user_locator_resolved_to_sourceatom"]),
            "user_locator_resolution_status": resolution_status,
            "target_locator_used": False,
            "gold_locator_used": False,
            "expected_supporting_text_used": False,
            "official_metric_input_rows": 0,
            "official_metric_candidate": False,
            "promotion_evidence": False,
            "raw_file_query_time_accessed": False,
            "source_atom_registry_canonical_truth": True,
            "vector_payload_used_as_evidence_truth": False,
            "direct_normalized_value_query_matching_used": False,
            "expected_supporting_gold_text_used_for_retrieval_or_generation": False,
            "deterministic_official_execution": False,
            "deterministic_answer_execution_executed": False,
            "L8_generation_executed": llm_executed,
            "answer_generation_executed": True,
            "retrieval_latency_ms": retrieval_latency_ms,
            "l8_generation_latency_ms": elapsed_ms,
            "retrieval_latency_includes_l8_generation": False,
            "latency_scope": "l0_l7_retrieval_from_upstream_trace_or_user_locator_resolution_l8_generation_separate",
            **route_policy,
            **locator_answerability,
        }
        per_query = {
            "schema_version": f"{RUN_ID}_per_query_v1",
            **common,
            "answer_length_chars": len(final_answer),
            "generation_model": model,
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": prompt_sha,
            "diagnostic_flags": diagnostic_flags,
        }
        response = {
            **per_query,
            "query": query,
            "raw_response": raw_response,
            "final_answer": final_answer,
            "citations": [dict(item) for item in citations],
            "abstain_reason": abstain_reason,
            "parse_ok": parse_ok,
            "malformed_response_flag": malformed_response,
            "parse_error_reason": parse_error_reason,
            "rendered_citations": evidence["rendered_citations"],
            "locator_summary": evidence["locator_summary"],
        }
        review = {
            "review_id": clean(case.get("review_id")),
            "query_id": clean(case.get("query_id")),
            "diagnostic_case_id": clean(case.get("diagnostic_case_id")),
            "bucket": bucket,
            "source_family": family,
            "query": query,
            "final_answer": final_answer,
            "rendered_citations": evidence["rendered_citations"],
            "query_user_provided_locator": bool(parsed["query_user_provided_locator"]),
            "user_locator_type": clean(parsed["user_locator_type"]),
            "user_locator_text": clean(parsed["user_locator_text"]),
            "user_locator_resolution_status": resolution_status,
            "route_lane": route_policy["route_lane"],
            "route_policy_reason": route_policy["route_policy_reason"],
            "allow_unbounded_fallback": route_policy["allow_unbounded_fallback"],
            "locator_bounds_answerability": locator_answerability["locator_bounds_answerability"],
            "locator_bounds_answerability_reason": locator_answerability["locator_bounds_answerability_reason"],
            "selected_source_atom_ids": "|".join(selected_output_ids),
            "locator_summary": evidence["locator_summary"],
            "selected_evidence_excerpt": evidence["selected_evidence_excerpt"],
            "diagnostic_flags": json.dumps(diagnostic_flags, ensure_ascii=False, sort_keys=True),
            "abstain_reason": abstain_reason,
            "over_abstain_review_candidate": flags["over_abstain_review_candidate"],
            "xlsx_value_formatting_risk": flags["xlsx_value_formatting_risk"],
            "unsupported_claim_risk": flags["unsupported_claim_risk"],
            **{field: "" for field in USER_REVIEW_FIELDS},
            "official_metric_candidate": False,
            "promotion_evidence": False,
        }
        parse_audit = {
            "schema_version": f"{RUN_ID}_user_locator_parse_audit_v1",
            **common,
            "locator_terms": parsed["locator_terms"],
            "target_locator_used": False,
            "gold_locator_used": False,
            "expected_supporting_text_used": False,
        }
        resolution_audit = {
            "schema_version": f"{RUN_ID}_user_locator_resolution_audit_v1",
            **common,
            "selected_candidate_count": resolution["selected_candidate_count"],
            "resolution_notes": resolution["resolution_notes"],
            "source_atom_registry_canonical_truth": True,
            "vector_payload_used_as_evidence_truth": False,
        }
        if "rough_query" in bucket:
            rough_audit_rows.append(
                {
                    "schema_version": f"{RUN_ID}_rough_query_bucket_audit_v1",
                    **common,
                    "rough_query_answerable_candidate": bool(clean(evidence["selected_evidence_excerpt"])),
                    "rough_query_abstained": bool(flags["abstain_quality_flag"]),
                    "official_metric_input_rows": 0,
                }
            )
        route_policy_audit_rows.append(
            {
                "schema_version": f"{RUN_ID}_route_policy_audit_v1",
                **common,
                "bounded_tool_registry_version": tool_registry.registry_version,
                "selected_tool_count": len(route_policy["selected_tool_ids"]),
                "selected_tool_ids": route_policy["selected_tool_ids"],
            }
        )
        per_query_rows.append(per_query)
        response_rows.append(response)
        review_rows.append(review)
        parse_audit_rows.append(parse_audit)
        resolution_audit_rows.append(resolution_audit)
    return (
        per_query_rows,
        response_rows,
        review_rows,
        parse_audit_rows,
        resolution_audit_rows,
        rough_audit_rows,
        route_policy_audit_rows,
    )


def guardrail_flags(*, l8_generation_executed: bool, fail_closed: bool = False) -> dict[str, Any]:
    return {
        **v316.guardrail_flags(l8_generation_executed=l8_generation_executed, fail_closed=fail_closed),
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_text_used": False,
        "user_locator_candidate_only": True,
        "rough_query_review_only": True,
    }


def review_packet_user_fields_blank(review_rows: Sequence[Mapping[str, Any]]) -> bool:
    return all(row.get(field, "") == "" for row in review_rows for field in USER_REVIEW_FIELDS)


def query_duplicate_metrics(review_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    hashes = [sha256_text(clean(row.get("query"))) for row in review_rows]
    hash_counts = Counter(hashes)
    bucket_hashes: dict[str, set[str]] = defaultdict(set)
    bucket_locator_status_l8: Counter[tuple[str, str, bool]] = Counter()
    for row, query_hash in zip(review_rows, hashes):
        bucket = clean(row.get("bucket"))
        bucket_hashes[bucket].add(query_hash)
        flags = row_diagnostic_flags(row)
        bucket_locator_status_l8[
            (
                bucket,
                clean(row.get("user_locator_resolution_status")),
                bool(flags.get("llm_executed")),
            )
        ] += 1
    return {
        "unique_query_hash_count": len(hash_counts),
        "duplicate_query_hash_groups": [
            {"query_text_sha256": query_hash, "row_count": count}
            for query_hash, count in sorted(hash_counts.items())
            if count > 1
        ],
        "per_bucket_unique_query_count": {
            bucket: len(values) for bucket, values in sorted(bucket_hashes.items())
        },
        "per_bucket_locator_status_l8_generation": {
            f"{bucket}|{status or 'NONE'}|L8_generation_executed={str(l8).lower()}": count
            for (bucket, status, l8), count in sorted(bucket_locator_status_l8.items())
        },
    }


def build_metrics(review_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    bucket_counts = Counter(clean(row.get("bucket")) for row in review_rows)
    family_counts = Counter(clean(row.get("source_family")) for row in review_rows)
    parse_ok_count = sum(bool(row_diagnostic_flags(row).get("parse_ok")) for row in review_rows)
    locator_rows = [row for row in review_rows if bool(row.get("query_user_provided_locator"))]
    rough_rows = [row for row in review_rows if "rough_query" in clean(row.get("bucket"))]
    duplicate_metrics = query_duplicate_metrics(review_rows)
    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "generated_response_count": len(review_rows),
        "review_packet_row_count": len(review_rows),
        "parse_ok_count": parse_ok_count,
        "invalid_json_count": len(review_rows) - parse_ok_count,
        "citation_rendered_count": sum(1 for row in review_rows if clean(row.get("rendered_citations"))),
        "abstain_count": sum(bool(row_diagnostic_flags(row).get("abstain_quality_flag")) for row in review_rows),
        "user_locator_query_count": len(locator_rows),
        "user_locator_resolved_count": sum(
            clean(row.get("user_locator_resolution_status")) in {"RESOLVED", "AMBIGUOUS_MULTIPLE_SOURCEATOMS"}
            for row in locator_rows
        ),
        "user_locator_unresolved_count": sum(clean(row.get("user_locator_resolution_status")) == "UNRESOLVED" for row in locator_rows),
        "rough_query_count": len(rough_rows),
        "rough_query_abstain_count": sum(bool(row_diagnostic_flags(row).get("abstain_quality_flag")) for row in rough_rows),
        "hallucination_risk_flag_count": sum(bool(row_diagnostic_flags(row).get("hallucination_risk_flag")) for row in review_rows),
        "unsupported_claim_risk_count": sum(bool(row.get("unsupported_claim_risk")) for row in review_rows),
        "xlsx_value_formatting_risk_count": sum(bool(row.get("xlsx_value_formatting_risk")) for row in review_rows),
        "over_abstain_review_candidate_count": sum(bool(row.get("over_abstain_review_candidate")) for row in review_rows),
        "review_packet_user_fields_blank": review_packet_user_fields_blank(review_rows),
        "family_counts": dict(sorted(family_counts.items())),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        **duplicate_metrics,
        "pdf_xlsx_collapsed_headline_score_reported": False,
        "headline_score": None,
        **guardrail_flags(l8_generation_executed=any(bool(row_diagnostic_flags(row).get("llm_executed")) for row in review_rows)),
    }


def build_per_family(review_rows: Sequence[Mapping[str, Any]], sample_reasons: Mapping[str, Any]) -> dict[str, Any]:
    by_family: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in review_rows:
        by_family[clean(row.get("source_family"))].append(row)
    return {
        "schema_version": f"{RUN_ID}_per_family_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "families_reported_separately": sorted(by_family),
        "no_collapsed_cross_family_score": True,
        "per_source_family": {
            family: {
                "row_count": len(rows),
                "generated_response_count": len(rows),
                "user_locator_query_count": sum(bool(row.get("query_user_provided_locator")) for row in rows),
                "rough_query_count": sum("rough_query" in clean(row.get("bucket")) for row in rows),
                "abstain_count": sum(bool(row_diagnostic_flags(row).get("abstain_quality_flag")) for row in rows),
                "unique_query_hash_count": query_duplicate_metrics(rows)["unique_query_hash_count"],
                "per_bucket_unique_query_count": query_duplicate_metrics(rows)["per_bucket_unique_query_count"],
            }
            for family, rows in sorted(by_family.items())
        },
        "sample_buckets": dict(sample_reasons),
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "pdf_xlsx_collapsed_headline_score_reported": False,
    }


def build_guardrail_audit(generated_response_count: int) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "generated_at": utc_now(),
        "generated_response_count": generated_response_count,
        "protected_namespaces_touched": [],
        "db_or_production_namespace_written": False,
        "source_atom_registry_canonical_truth": True,
        "source_atom_registry_mutated": False,
        "vector_payload_used_as_evidence_truth": False,
        "raw_file_query_time_accessed": False,
        "direct_normalized_value_query_matching_used": False,
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_text_used": False,
        **guardrail_flags(l8_generation_executed=generated_response_count > 0),
    }


def build_leakage_audit(review_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in review_rows:
        flags = row_diagnostic_flags(row)
        hits = leakage_hits(row)
        rows.append(
            {
                "schema_version": f"{RUN_ID}_leakage_audit_v1",
                "run_id": RUN_ID,
                "review_id": clean(row.get("review_id")),
                "bucket": clean(row.get("bucket")),
                "query_user_provided_locator": bool(row.get("query_user_provided_locator")),
                "target_locator_used": False,
                "gold_locator_used": False,
                "expected_supporting_text_used": False,
                "raw_file_query_time_accessed": False,
                "source_atom_registry_canonical_truth": True,
                "vector_payload_used_as_evidence_truth": False,
                "direct_normalized_value_query_matching_used": False,
                "unsupported_claim_risk": bool(flags.get("unsupported_claim_risk")),
                "leakage_detected": bool(hits),
                "leakage_fields": hits,
                "leakage_scan_fields": list(LEAKAGE_SCAN_FIELDS),
                "official_metric_input_rows": 0,
            }
        )
    return rows


def build_prompt_manifest(*, model: str, base_url: str, backend: str) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_prompt_manifest_v1",
        "run_id": RUN_ID,
        "prompt_version": PROMPT_VERSION,
        "backend": backend,
        "base_url": base_url,
        "model": model,
        "requires_korean_answer": True,
        "uses_only_supplied_evidence": True,
        "requires_concise_answer": True,
        "requires_insufficient_evidence_abstain": True,
        "requires_ambiguity_disclosure": True,
        "uses_user_provided_locator_text_from_query": True,
        "uses_artifact_target_or_gold_locator_text": False,
        "uses_expected_or_supporting_gold_text": False,
        "exposes_internal_layer_names": False,
        "route_policy_lanes": list(ROUTE_LANES),
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }


def build_runtime_materialization_plan() -> dict[str, Any]:
    registry = build_default_tool_registry()
    return {
        "schema_version": f"{RUN_ID}_runtime_materialization_plan_v1",
        "run_id": RUN_ID,
        "generated_at": utc_now(),
        "reused_or_linked_from_run_id": v316.RUN_ID,
        "materialization_contract_unchanged_from_v3_16": True,
        "all_l0_l8_components_classified_once": set(LAYER_MATERIALIZATION_CLASSIFICATION) == set(RUNTIME_LAYER_NAMES),
        "per_layer_classification": dict(LAYER_MATERIALIZATION_CLASSIFICATION),
        "tool_registry_version": registry.registry_version,
        "bounded_tool_registry": {
            "registered_layer_names": list(registry.layer_names()),
            "route_lanes": list(ROUTE_LANES),
            "unbounded_fallback_allowed": False,
            "official_metric_input_rows": 0,
            "diagnostic_only": True,
        },
        "db_contract": {
            "adapter_classification": "replay_or_mock_live_runtime_like",
            "production_write_allowed": False,
            "required_policy_fields": [
                "request_id",
                "required_index_version",
                "allowed_source_file_types",
                "allowed_parser_versions",
                "tenant_id",
                "acl_tags",
            ],
            "current_enforcement_status": "diagnostic_post_filter_or_replay_until_preranking_scope_enforcement_exists",
        },
        "index_contract": {
            "adapter_classification": "replay_or_mock_live_runtime_like",
            "retrieval_scope_required_before_ranking": True,
            "current_vector_adapter_production_filter_enforcement": False,
            "protected_namespaces_touched": [],
        },
        "cache_contract": {
            "adapter_classification": "replay_or_mock_live_runtime_like",
            "cache_material_is_source_truth": False,
            "source_atom_registry_remains_canonical_truth": True,
            "policy_snapshot_required_in_cache_key": True,
        },
        "raw_pdf_xlsx_query_time_accessed": False,
        "raw_pdf_xlsx_query_time_parsing_forbidden": True,
        "broad_source_atom_registry_scan_query_time_forbidden": True,
        "user_locator_resolution_surface": "bounded_review_candidate_sourceatom_subset",
        "source_atom_registry_canonical_truth": True,
        "vector_payload_used_as_evidence_truth": False,
        "searchview_vector_payload_candidate_only": True,
        "direct_normalized_value_query_matching_used": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }


def percentile(values: Sequence[float], pct: float) -> float:
    return v316.percentile(values, pct)


def latency_stats(values: Sequence[float]) -> dict[str, Any]:
    return v316.latency_stats(values)


def build_latency_budget_contract(per_query_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    retrieval_values = [float(row.get("retrieval_latency_ms") or 0.0) for row in per_query_rows]
    l8_values = [float(row.get("l8_generation_latency_ms") or 0.0) for row in per_query_rows]
    return {
        "schema_version": f"{RUN_ID}_latency_budget_contract_v1",
        "run_id": RUN_ID,
        "generated_at": utc_now(),
        "reused_or_linked_from_run_id": v316.RUN_ID,
        "budget_role": "diagnostic_only",
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "retrieval_latency_excludes_l8_generation": True,
        "l8_generation_latency_reported_separately": True,
        "actual_retrieval_latency_ms": latency_stats(retrieval_values),
        "actual_l8_generation_latency_ms": latency_stats(l8_values),
        "review_packet_row_count": len(per_query_rows),
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    per_family: Mapping[str, Any],
    input_lineage: Mapping[str, Any],
    artifact_sha256: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_summary_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "event_type": EVENT_TYPE,
        "run_class": "diagnostic_only_user_locator_and_rough_query_answer_quality_nonprod",
        "generated_at": utc_now(),
        "review_packet_dir": repo_relative(OUTPUT_DIR),
        "generated_response_count": metrics["generated_response_count"],
        "review_packet_row_count": metrics["review_packet_row_count"],
        "parse_ok_count": metrics["parse_ok_count"],
        "invalid_json_count": metrics["invalid_json_count"],
        "citation_rendered_count": metrics["citation_rendered_count"],
        "abstain_count": metrics["abstain_count"],
        "user_locator_query_count": metrics["user_locator_query_count"],
        "user_locator_resolved_count": metrics["user_locator_resolved_count"],
        "user_locator_unresolved_count": metrics["user_locator_unresolved_count"],
        "rough_query_count": metrics["rough_query_count"],
        "rough_query_abstain_count": metrics["rough_query_abstain_count"],
        "unique_query_hash_count": metrics["unique_query_hash_count"],
        "duplicate_query_hash_groups": metrics["duplicate_query_hash_groups"],
        "per_bucket_unique_query_count": metrics["per_bucket_unique_query_count"],
        "per_bucket_locator_status_l8_generation": metrics["per_bucket_locator_status_l8_generation"],
        "hallucination_risk_flag_count": metrics["hallucination_risk_flag_count"],
        "unsupported_claim_risk_count": metrics["unsupported_claim_risk_count"],
        "xlsx_value_formatting_risk_count": metrics["xlsx_value_formatting_risk_count"],
        "over_abstain_review_candidate_count": metrics["over_abstain_review_candidate_count"],
        "families_reported_separately": per_family["families_reported_separately"],
        "route_policy_lanes": list(ROUTE_LANES),
        "tool_registry_version": build_default_tool_registry().registry_version,
        "runtime_materialization": dict(LAYER_MATERIALIZATION_CLASSIFICATION),
        "review_packet_user_fields_blank": bool(metrics["review_packet_user_fields_blank"]),
        "input_lineage": dict(input_lineage),
        "artifact_paths": {key: repo_relative(path) for key, path in OUTPUTS.items()},
        "artifact_sha256": dict(artifact_sha256),
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "pdf_xlsx_collapsed_headline_score_reported": False,
        "headline_score": None,
        **guardrail_flags(l8_generation_executed=metrics["generated_response_count"] > 0),
    }


def fail_closed_artifacts(
    *,
    blockers: Sequence[str],
    backend: str,
    base_url: str,
    model: str,
    input_lineage: Mapping[str, Any],
) -> dict[str, Any]:
    del backend, base_url, model
    empty_metrics = {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": FAIL_CLOSED_STATUS,
        "diagnostic_only": True,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "generated_response_count": 0,
        "review_packet_row_count": 0,
        "parse_ok_count": 0,
        "invalid_json_count": 0,
        "citation_rendered_count": 0,
        "abstain_count": 0,
        "user_locator_query_count": 0,
        "user_locator_resolved_count": 0,
        "user_locator_unresolved_count": 0,
        "rough_query_count": 0,
        "rough_query_abstain_count": 0,
        "unique_query_hash_count": 0,
        "duplicate_query_hash_groups": [],
        "per_bucket_unique_query_count": {},
        "per_bucket_locator_status_l8_generation": {},
        "hallucination_risk_flag_count": 0,
        "unsupported_claim_risk_count": 0,
        "xlsx_value_formatting_risk_count": 0,
        "over_abstain_review_candidate_count": 0,
        "review_packet_user_fields_blank": True,
        "pdf_xlsx_collapsed_headline_score_reported": False,
        "headline_score": None,
        **guardrail_flags(l8_generation_executed=False, fail_closed=True),
    }
    per_family = {
        "schema_version": f"{RUN_ID}_per_family_v1",
        "run_id": RUN_ID,
        "diagnostic_only": True,
        "families_reported_separately": [],
        "no_collapsed_cross_family_score": True,
        "per_source_family": {},
        "sample_buckets": {},
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }
    summary = {
        "schema_version": f"{RUN_ID}_summary_v1",
        "run_id": RUN_ID,
        "status": FAIL_CLOSED_STATUS,
        "event_type": EVENT_TYPE,
        "run_class": "diagnostic_only_user_locator_and_rough_query_answer_quality_nonprod",
        "generated_at": utc_now(),
        "review_packet_dir": repo_relative(OUTPUT_DIR),
        "local_llm_unavailable_fail_closed": True,
        "local_llm_blockers": list(blockers),
        "input_lineage": dict(input_lineage),
        "artifact_paths": {key: repo_relative(path) for key, path in OUTPUTS.items()},
        "artifact_sha256": {},
        **empty_metrics,
    }
    return {
        "summary": summary,
        "metrics": empty_metrics,
        "per_family": per_family,
        "per_query_rows": [],
        "response_rows": [],
        "review_rows": [],
        "guardrail_audit": build_guardrail_audit(0),
        "leakage_audit_rows": [],
        "prompt_manifest": build_prompt_manifest(model="", base_url="", backend=""),
        "user_locator_parse_audit_rows": [],
        "user_locator_resolution_audit_rows": [],
        "rough_query_bucket_audit_rows": [],
        "tool_registry": build_default_tool_registry().to_dict(),
        "route_policy_audit_rows": [],
        "runtime_materialization_plan": build_runtime_materialization_plan(),
        "latency_budget_contract": build_latency_budget_contract([]),
        "input_lineage": input_lineage,
    }


def build_artifacts(
    *,
    backend: str = DEFAULT_BACKEND,
    base_url: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 420,
    timeout_seconds: int = 90,
    max_evidence_chars: int = 900,
    llm_client: Callable[[str, str], str] | None = None,
) -> dict[str, Any]:
    input_paths = build_input_paths()
    require_input_artifacts(input_paths)
    input_lineage = build_input_lineage(input_paths)
    resolved_base_url = resolve_base_url(backend, base_url)
    blockers: list[str] = []
    if llm_client is None:
        blockers = local_llm_entry_blockers(
            backend=backend,
            base_url=resolved_base_url,
            model=model,
            check_endpoint=True,
            timeout_seconds=min(timeout_seconds, 10),
        )
    if blockers:
        return fail_closed_artifacts(
            blockers=blockers,
            backend=backend,
            base_url=resolved_base_url,
            model=model,
            input_lineage=input_lineage,
        )

    cases, sample_reasons = build_diagnostic_cases()
    source_registry = load_source_registry_for_cases(cases)
    tool_registry = build_default_tool_registry()
    (
        per_query_rows,
        response_rows,
        review_rows,
        parse_rows,
        resolution_rows,
        rough_rows,
        route_policy_rows,
    ) = generate_rows(
        cases,
        source_registry=source_registry,
        tool_registry=tool_registry,
        model=model,
        base_url=resolved_base_url,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        llm_client=llm_client,
        max_evidence_chars=max_evidence_chars,
    )
    metrics = build_metrics(review_rows)
    per_family = build_per_family(review_rows, sample_reasons)
    prompt_manifest = build_prompt_manifest(model=model, base_url=resolved_base_url, backend=backend)
    guardrail = build_guardrail_audit(len(review_rows))
    leakage = build_leakage_audit(review_rows)
    runtime_plan = build_runtime_materialization_plan()
    latency_contract = build_latency_budget_contract(per_query_rows)
    metrics["latency_budget"] = {
        "budget_role": "diagnostic_only",
        "retrieval_latency_excludes_l8_generation": True,
        "l8_generation_latency_reported_separately": True,
        "promotion_evidence": False,
    }
    metrics["llm_latency_summary"] = latency_contract["actual_l8_generation_latency_ms"]
    metrics["retrieval_latency_summary"] = latency_contract["actual_retrieval_latency_ms"]
    summary = build_summary(
        metrics=metrics,
        per_family=per_family,
        input_lineage=input_lineage,
        artifact_sha256={},
    )
    return {
        "summary": summary,
        "metrics": metrics,
        "per_family": per_family,
        "per_query_rows": per_query_rows,
        "response_rows": response_rows,
        "review_rows": review_rows,
        "guardrail_audit": guardrail,
        "leakage_audit_rows": leakage,
        "prompt_manifest": prompt_manifest,
        "user_locator_parse_audit_rows": parse_rows,
        "user_locator_resolution_audit_rows": resolution_rows,
        "rough_query_bucket_audit_rows": rough_rows,
        "tool_registry": tool_registry.to_dict(),
        "route_policy_audit_rows": route_policy_rows,
        "runtime_materialization_plan": runtime_plan,
        "latency_budget_contract": latency_contract,
        "input_lineage": input_lineage,
    }


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REVIEW_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    v316.replace_marked_entry(path, marker, entry)


def update_docs(summary: Mapping[str, Any], metrics: Mapping[str, Any]) -> None:
    progress_entry = (
        f"- v3_17 user-locator and rough-query answer-quality packet (`{RUN_ID}`) is "
        "diagnostic_v3_17_user_locator_rough_query_answer_quality_nonprod_ready. It creates a compact "
        "PDF/XLSX review packet for rough, terse, incomplete user queries and query-owned locator text. "
        "The user-provided locator text is query-owned only: target_locator_used=false, gold_locator_used=false, "
        "expected_supporting_text_used=false, official_metric=false, official_metric_input_rows=0, "
        "promotion_evidence=false, raw_file_query_time_accessed=false. SourceAtom registry remains canonical truth, "
        "SearchView/vector payload remains candidate-only, and the bounded ToolRegistry declares the diagnostic L0-L8 "
        "tool specs plus user_locator, rough_query, hybrid, and unsupported route lanes with unbounded fallback disabled."
    )
    measurements_entry = f"""### v3_17 User-Locator And Rough-Query Review Packet

- Run: `{RUN_ID}`
- Policy: diagnostic-only answer-quality review; no official metric, score lift, promotion, threshold tuning, winner selection, production DB write, raw PDF/XLSX query-time parsing, target/gold locator use, expected/supporting text use, or direct normalized answer-value query matching.
- User locator policy: locator text is allowed only when it appears in the user query. Artifact target/gold/supporting/expected locator text is forbidden.
- Runtime evidence policy: resolved user locators hydrate through SourceAtom registry; SearchView/vector payload remains candidate-only.

| Diagnostic count | Value |
| --- | ---: |
| generated_response_count | {metrics["generated_response_count"]} |
| review_packet_row_count | {metrics["review_packet_row_count"]} |
| parse_ok_count | {metrics["parse_ok_count"]} |
| invalid_json_count | {metrics["invalid_json_count"]} |
| citation_rendered_count | {metrics["citation_rendered_count"]} |
| abstain_count | {metrics["abstain_count"]} |
| user_locator_query_count | {metrics["user_locator_query_count"]} |
| user_locator_resolved_count | {metrics["user_locator_resolved_count"]} |
| user_locator_unresolved_count | {metrics["user_locator_unresolved_count"]} |
| rough_query_count | {metrics["rough_query_count"]} |
| rough_query_abstain_count | {metrics["rough_query_abstain_count"]} |
| unique_query_hash_count | {metrics["unique_query_hash_count"]} |
| hallucination_risk_flag_count | {metrics["hallucination_risk_flag_count"]} |
| unsupported_claim_risk_count | {metrics["unsupported_claim_risk_count"]} |
| xlsx_value_formatting_risk_count | {metrics["xlsx_value_formatting_risk_count"]} |
| over_abstain_review_candidate_count | {metrics["over_abstain_review_candidate_count"]} |
| official_metric_input_rows | 0 |

Artifacts: `{summary["review_packet_dir"]}/summary.json`, `metrics.json`, `per_family.json`, `per_query.jsonl`, `responses.jsonl`, `review_packet.csv`, `review_packet.jsonl`, `guardrail_audit.json`, `leakage_audit.jsonl`, `prompt_manifest.json`, `user_locator_parse_audit.jsonl`, `user_locator_resolution_audit.jsonl`, `rough_query_bucket_audit.jsonl`, `tool_registry.json`, `route_policy_audit.jsonl`, `runtime_materialization_plan.json`, and `latency_budget_contract.json`.
"""
    triage_entry = (
        "### v3_17 User-Locator And Rough-Query Review Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        "- Scope: diagnostic-only PDF/XLSX answer-quality review for rough, terse, incomplete user queries and user-provided file/sheet/cell/range/page locator text; XLSX is primary and PDF is control only.\n"
        "- This is not official scoring, not promotion evidence, not product success evidence, and not a winner-selection or threshold-tuning run.\n"
        "- User-owned review fields remain blank for satisfaction, relevance, answerability, expected-answer decision, and supporting-evidence decision.\n"
        "- locator-bounds answerability is machine-stated for user locator rows only and remains a review aid, not a human answerability label or official metric.\n"
        "- If query-owned locator text cannot be resolved to bounded SourceAtom ids, the row abstains with a location-not-found answer rather than inventing values.\n"
        "- SourceAtom registry is the canonical evidence truth; SearchView/vector payload stays candidate-only.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        "Overall status: `diagnostic_v3_17_user_locator_rough_query_answer_quality_nonprod_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"current diagnostic answer-quality loop:\n`[^`]+`;",
        f"current diagnostic answer-quality loop:\n`{RUN_ID}`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)


def artifact_sha256_without_summary() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path in OUTPUTS.items():
        if key == "summary_json":
            continue
        hashes[f"{key}_sha256"] = sha256_file(path)
    return hashes


def append_status_event(summary: Mapping[str, Any]) -> None:
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": summary["status"],
        "generated_at": utc_now(),
        "review_packet_dir": summary["review_packet_dir"],
        "generated_response_count": summary["generated_response_count"],
        "review_packet_row_count": summary["review_packet_row_count"],
        "parse_ok_count": summary["parse_ok_count"],
        "invalid_json_count": summary["invalid_json_count"],
        "citation_rendered_count": summary["citation_rendered_count"],
        "abstain_count": summary["abstain_count"],
        "user_locator_query_count": summary["user_locator_query_count"],
        "user_locator_resolved_count": summary["user_locator_resolved_count"],
        "user_locator_unresolved_count": summary["user_locator_unresolved_count"],
        "rough_query_count": summary["rough_query_count"],
        "rough_query_abstain_count": summary["rough_query_abstain_count"],
        "unique_query_hash_count": summary.get("unique_query_hash_count", 0),
        "duplicate_query_hash_groups": summary.get("duplicate_query_hash_groups", []),
        "per_bucket_unique_query_count": summary.get("per_bucket_unique_query_count", {}),
        "per_bucket_locator_status_l8_generation": summary.get("per_bucket_locator_status_l8_generation", {}),
        "route_policy_lanes": summary.get("route_policy_lanes", list(ROUTE_LANES)),
        "tool_registry_version": summary.get("tool_registry_version", build_default_tool_registry().registry_version),
        "runtime_materialization": summary.get("runtime_materialization", dict(LAYER_MATERIALIZATION_CLASSIFICATION)),
        "future_scored_adapter_status": "DISABLED_PENDING_USER_APPROVAL",
        "artifact_paths": summary["artifact_paths"],
        "artifact_sha256": {**summary["artifact_sha256"], "summary_json_sha256": sha256_file(OUTPUTS["summary_json"])},
        **guardrail_flags(l8_generation_executed=summary["status"] == STATUS),
    }
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def write_artifacts(artifacts: Mapping[str, Any]) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUTS["metrics_json"], artifacts["metrics"])
    write_json(OUTPUTS["per_family_json"], artifacts["per_family"])
    write_jsonl(OUTPUTS["per_query_jsonl"], artifacts["per_query_rows"])
    write_jsonl(OUTPUTS["responses_jsonl"], artifacts["response_rows"])
    write_csv(OUTPUTS["review_packet_csv"], artifacts["review_rows"])
    write_jsonl(OUTPUTS["review_packet_jsonl"], artifacts["review_rows"])
    write_json(OUTPUTS["guardrail_audit_json"], artifacts["guardrail_audit"])
    write_jsonl(OUTPUTS["leakage_audit_jsonl"], artifacts["leakage_audit_rows"])
    write_json(OUTPUTS["prompt_manifest_json"], artifacts["prompt_manifest"])
    write_jsonl(OUTPUTS["user_locator_parse_audit_jsonl"], artifacts["user_locator_parse_audit_rows"])
    write_jsonl(OUTPUTS["user_locator_resolution_audit_jsonl"], artifacts["user_locator_resolution_audit_rows"])
    write_jsonl(OUTPUTS["rough_query_bucket_audit_jsonl"], artifacts["rough_query_bucket_audit_rows"])
    write_json(OUTPUTS["tool_registry_json"], artifacts["tool_registry"])
    write_jsonl(OUTPUTS["route_policy_audit_jsonl"], artifacts["route_policy_audit_rows"])
    write_json(OUTPUTS["runtime_materialization_plan_json"], artifacts["runtime_materialization_plan"])
    write_json(OUTPUTS["latency_budget_contract_json"], artifacts["latency_budget_contract"])
    artifact_sha = artifact_sha256_without_summary()
    if artifacts["summary"]["status"] == STATUS:
        summary = build_summary(
            metrics=artifacts["metrics"],
            per_family=artifacts["per_family"],
            input_lineage=artifacts["input_lineage"],
            artifact_sha256=artifact_sha,
        )
    else:
        summary = dict(artifacts["summary"])
        summary["artifact_sha256"] = artifact_sha
    write_json(OUTPUTS["summary_json"], summary)
    append_status_event(summary)
    if summary["status"] == STATUS:
        update_docs(summary, artifacts["metrics"])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build v3_17 diagnostic-only user-locator and rough-query review packet.")
    parser.add_argument("--check", action="store_true", help="Build in memory only.")
    parser.add_argument("--backend", default=DEFAULT_BACKEND, choices=["llamacpp", "openai-compatible", "ollama"])
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=420)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--max-evidence-chars", type=int, default=900)
    args = parser.parse_args(argv)
    artifacts = build_artifacts(
        backend=args.backend,
        base_url=args.base_url,
        model=args.model,
        max_tokens=args.max_tokens,
        timeout_seconds=args.timeout_seconds,
        max_evidence_chars=args.max_evidence_chars,
    )
    payload = {
        "run_id": RUN_ID,
        "status": artifacts["summary"]["status"],
        "generated_response_count": artifacts["metrics"]["generated_response_count"],
        "review_packet_row_count": artifacts["metrics"]["review_packet_row_count"],
        "official_metric": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }
    if args.check:
        print(json.dumps({**payload, "check": True}, ensure_ascii=False, sort_keys=True))
        return 0 if artifacts["summary"]["status"] == STATUS else 2
    summary = write_artifacts(artifacts)
    print(json.dumps({**payload, "summary": repo_relative(OUTPUTS["summary_json"])}, ensure_ascii=False, sort_keys=True))
    return 0 if summary["status"] == STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
