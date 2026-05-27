from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import rag_v3_21_agent_runtime_llm_io_observability_packet_nonprod as v321
from rag_local_llm_expected_answer_generation_v1 import (  # noqa: E402
    DEFAULT_BACKEND,
    DEFAULT_MODEL,
    call_local_llm,
    local_llm_entry_blockers,
    resolve_base_url,
)


ROOT = v321.ROOT
REPORT_DIR = v321.REPORT_DIR
STATUS_JSONL = v321.STATUS_JSONL
PROGRESS_DOC = v321.PROGRESS_DOC
MEASUREMENTS_DOC = v321.MEASUREMENTS_DOC
TRIAGE_DOC = v321.TRIAGE_DOC

if str(ROOT / "ai") not in sys.path:
    sys.path.insert(0, str(ROOT / "ai"))

from eval.harness import rag_diagnostic_common as diagnostic_common  # noqa: E402

from app.capabilities.rag_orchestrator.agent_runtime import (  # noqa: E402
    AgentRuntime,
    AgentRuntimeRequest,
    RUNTIME_CONTRACT_GUARDS,
)
from app.capabilities.rag_orchestrator.phase1_diagnostic_runtime import (  # noqa: E402
    BOUNDED_SUMMARY_MAX_CELLS as SHARED_BOUNDED_SUMMARY_MAX_CELLS,
    PHASE1_V3_22_RUN_ID,
    RANGE_MODES as SHARED_RANGE_MODES,
    SMALL_RANGE_MAX_CELLS as SHARED_SMALL_RANGE_MAX_CELLS,
    cell_ref_to_row_col as shared_cell_ref_to_row_col,
    explicit_query_range_area as shared_explicit_query_range_area,
    range_shape as shared_range_shape,
)
from app.capabilities.rag_orchestrator.runtime_adapters import (  # noqa: E402
    InMemoryRuntimeCacheAdapter,
    InMemorySearchIndexAdapter,
    InMemorySourceAtomStoreAdapter,
    cache_key_for_query,
)
from app.capabilities.rag_orchestrator.tool_registry import (  # noqa: E402
    LAYER_NAMES,
    build_default_tool_registry,
)


RUN_ID = PHASE1_V3_22_RUN_ID
EVENT_TYPE = "diagnostic_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod"
STATUS = "DIAGNOSTIC_V3_22_XLSX_VALUE_FORMATTING_AND_CELL_RANGE_ANSWER_RENDERING_NONPROD_READY"
OUTPUT_DIR = REPORT_DIR / "quality" / RUN_ID
REPORT_JSON = OUTPUT_DIR / "report.json"
REVIEW_CSV = OUTPUT_DIR / "review_packet.csv"
ADAPTER_NAMESPACE = "rag-data-v3-22-xlsx-display-rendering-nonprod"
CACHE_NAMESPACE = "rag-v3-22-xlsx-display-cache"
DIAGNOSTIC_TENANT_ID = v321.DIAGNOSTIC_TENANT_ID
PROMPT_TEMPLATE_VERSION = "rag_agent_runtime_xlsx_display_value_prompt_v1"
PROMPT_TEMPLATE = """You are a non-production diagnostic RAG answer generator.
Answer in Korean using only the provided SourceAtom/EvidenceBundle evidence and bounded XLSX display metadata.
Prefer xlsx_display_value when xlsx_format_confidence is high.
Return exactly one JSON object with keys:
- final_answer: concise user-visible answer
- citation_or_provenance_summary: short provenance summary using only provided SourceAtom/EvidenceBundle ids

Do not use hidden target, gold, expected answer, supporting evidence, vector payload, raw files, formula text, or local file paths.

User query:
{query}

Answer-ready context:
{answer_ready_context}

Evidence:
{evidence}
"""

RANGE_MODES = SHARED_RANGE_MODES
SMALL_RANGE_MAX_CELLS = SHARED_SMALL_RANGE_MAX_CELLS
BOUNDED_SUMMARY_MAX_CELLS = SHARED_BOUNDED_SUMMARY_MAX_CELLS
FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES = (
    "summary.json",
    "metrics.json",
    "per_query.jsonl",
    "route_policy_audit.jsonl",
    "runtime_contract_audit.jsonl",
    "user_response_policy_audit.jsonl",
    "db_contract_audit.jsonl",
    "index_contract_audit.jsonl",
    "cache_contract_audit.jsonl",
    "llm_io_packet.jsonl",
    "guardrail_audit.json",
    "leakage_audit.jsonl",
    "prompt_manifest.json",
)

USER_OWNED_REVIEW_REASONS = {
    "expected_answer_judgment",
    "supporting_evidence_judgment",
    "relevance_label",
    "answerability_label",
    "pass_fail_label",
    "denominator_eligibility",
    "query_approval",
    "gold_policy",
    "formatting_policy_user_decision_required",
}

LOCAL_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"']+|\\\\[^\\\s]+\\[^\s\"']+")


def clean(value: Any) -> str:
    return diagnostic_common.clean(value)


def repo_relative(path: Path) -> str:
    return diagnostic_common.repo_relative(path, root=ROOT)


def artifact_path_text(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def utc_now() -> str:
    return diagnostic_common.utc_now()


def sha256_file(path: Path) -> str:
    return diagnostic_common.sha256_file(path)


def sha256_text(value: str) -> str:
    return diagnostic_common.sha256_text(value)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return diagnostic_common.read_jsonl(path)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    diagnostic_common.write_json(path, payload)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    diagnostic_common.write_jsonl(path, rows)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns or (rows[0].keys() if rows else ()))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def csv_value(value: Any) -> str:
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return clean(value)


def guardrail_flags() -> dict[str, Any]:
    flags = dict(v321.guardrail_flags())
    flags.update(
        {
            "xlsx_display_value_contract": True,
            "single_report_artifact_contract": True,
            "raw_xlsx_query_time_parsing_forbidden": True,
            "full_workbook_sheet_scan_forbidden": True,
            "formula_evaluation_at_query_time": False,
            "formula_text_visible_to_user_default": False,
            "display_metadata_materialized_only": True,
            "bounded_range_rendering_only": True,
            "review_csv_optional_only_for_user_owned_decision": True,
        }
    )
    return flags


def display_contract(
    *,
    raw_value: Any,
    normalized_value: Any,
    display_value: Any | None,
    number_format: str = "",
    value_type: str,
    provenance: str,
    formula_cached_value: Any = "",
    merged_cell: bool = False,
    merged_range: str = "",
    merged_owner_cell: str = "",
    format_confidence: str = "high",
    format_drop_reason: str = "",
) -> dict[str, Any]:
    raw = clean(raw_value)
    normalized = clean(normalized_value)
    supplied_display = None if display_value is None else clean(display_value)
    if supplied_display is None:
        return {
            "raw_value": raw,
            "normalized_value": normalized,
            "display_value": raw,
            "number_format": clean(number_format),
            "value_type": clean(value_type) or "unknown",
            "formula_cached_value": clean(formula_cached_value),
            "formula_text_visible_to_user": False,
            "format_confidence": "low",
            "format_provenance": clean(provenance),
            "format_drop_reason": "FORMAT_METADATA_UNAVAILABLE",
            "merged_cell": bool(merged_cell),
            "merged_range": clean(merged_range),
            "merged_owner_cell": clean(merged_owner_cell),
        }
    return {
        "raw_value": raw,
        "normalized_value": normalized,
        "display_value": supplied_display,
        "number_format": clean(number_format),
        "value_type": clean(value_type),
        "formula_cached_value": clean(formula_cached_value),
        "formula_text_visible_to_user": False,
        "format_confidence": clean(format_confidence) or "high",
        "format_provenance": clean(provenance),
        "format_drop_reason": clean(format_drop_reason),
        "merged_cell": bool(merged_cell),
        "merged_range": clean(merged_range),
        "merged_owner_cell": clean(merged_owner_cell),
    }


def make_atom(
    atom_id: str,
    *,
    cell: str,
    cell_range: str,
    contract: Mapping[str, Any],
    row_label: str = "",
    target_column: str = "",
    table_id: str = "table:Book.xlsx:Sheet1:A1:E20",
) -> dict[str, Any]:
    locator = {
        "workbook": "Book.xlsx",
        "sheet": "Sheet1",
        "cell": cell,
        "range": cell_range,
        "row_label": row_label,
        "target_column": target_column,
        "normalized_value": clean(contract.get("normalized_value")),
        "display_value": clean(contract.get("display_value")),
        "raw_value": clean(contract.get("raw_value")),
        "number_format": clean(contract.get("number_format")),
        "value_type": clean(contract.get("value_type")),
        "table_id": table_id,
    }
    if contract.get("merged_cell"):
        locator["merged_range"] = clean(contract.get("merged_range"))
        locator["merged_owner_cell"] = clean(contract.get("merged_owner_cell"))
    snapshot = (
        f"Book.xlsx Sheet1 {cell} "
        f"xlsx_display_value={clean(contract.get('display_value'))} "
        f"xlsx_raw_value={clean(contract.get('raw_value'))} "
        f"xlsx_normalized_value={clean(contract.get('normalized_value'))} "
        f"xlsx_value_type={clean(contract.get('value_type'))}"
    )
    return {
        "source_atom_id": atom_id,
        "mock_source_atom": True,
        "tenant_id": DIAGNOSTIC_TENANT_ID,
        "source_family": "XLSX",
        "source_identity": f"XLSX:Book.xlsx:Sheet1:{cell_range}:{cell}",
        "raw_locator": dict(locator),
        "canonical_citation_payload": dict(locator),
        "normalized_text_or_value_snapshot": snapshot,
        "xlsx_display_contract": dict(contract),
    }


def source_atoms() -> dict[str, dict[str, Any]]:
    high = "source_atom_materialized_xlsx_display_metadata_v1"
    atoms = {
        "atom-xlsx-a1-int": make_atom(
            "atom-xlsx-a1-int",
            cell="A1",
            cell_range="A1:B2",
            row_label="Units",
            target_column="Integer",
            contract=display_contract(
                raw_value=42,
                normalized_value=42,
                display_value="42",
                number_format="0",
                value_type="integer",
                provenance=high,
            ),
        ),
        "atom-xlsx-b1-percent": make_atom(
            "atom-xlsx-b1-percent",
            cell="B1",
            cell_range="A1:B2",
            row_label="Rate",
            target_column="Percentage",
            contract=display_contract(
                raw_value="0.125",
                normalized_value="0.125",
                display_value="12.5%",
                number_format="0.0%",
                value_type="percentage",
                provenance=high,
            ),
        ),
        "atom-xlsx-a2-text": make_atom(
            "atom-xlsx-a2-text",
            cell="A2",
            cell_range="A1:B2",
            row_label="Description",
            target_column="Text",
            contract=display_contract(
                raw_value="서울",
                normalized_value="서울",
                display_value="서울",
                number_format="@",
                value_type="text",
                provenance=high,
            ),
        ),
        "atom-xlsx-b2-merged": make_atom(
            "atom-xlsx-b2-merged",
            cell="B2",
            cell_range="A1:B2",
            row_label="Merged owner",
            target_column="Merged display",
            contract=display_contract(
                raw_value="Header total",
                normalized_value="Header total",
                display_value="Header total",
                number_format="@",
                value_type="text",
                provenance=high,
                merged_cell=True,
                merged_range="B2:C2",
                merged_owner_cell="B2",
            ),
        ),
        "atom-xlsx-c1-currency": make_atom(
            "atom-xlsx-c1-currency",
            cell="C1",
            cell_range="C1:C1",
            row_label="Amount",
            target_column="Currency",
            contract=display_contract(
                raw_value="1234.5",
                normalized_value="1234.5",
                display_value="$1,234.50",
                number_format="$#,##0.00",
                value_type="currency",
                provenance=high,
            ),
        ),
        "atom-xlsx-d1-date": make_atom(
            "atom-xlsx-d1-date",
            cell="D1",
            cell_range="D1:D1",
            row_label="Date",
            target_column="Date",
            contract=display_contract(
                raw_value="45123",
                normalized_value="2023-07-17",
                display_value="2023-07-17",
                number_format="yyyy-mm-dd",
                value_type="date",
                provenance=high,
            ),
        ),
        "atom-xlsx-d2-datetime": make_atom(
            "atom-xlsx-d2-datetime",
            cell="D2",
            cell_range="D2:D2",
            row_label="DateTime",
            target_column="DateTime",
            contract=display_contract(
                raw_value="45123.3958333333",
                normalized_value="2023-07-17T09:30:00",
                display_value="2023-07-17 09:30",
                number_format="yyyy-mm-dd hh:mm",
                value_type="datetime",
                provenance=high,
            ),
        ),
        "atom-xlsx-e1-blank": make_atom(
            "atom-xlsx-e1-blank",
            cell="E1",
            cell_range="E1:E1",
            row_label="Blank",
            target_column="Blank",
            contract=display_contract(
                raw_value="",
                normalized_value="",
                display_value="",
                number_format="General",
                value_type="blank",
                provenance=high,
            ),
        ),
        "atom-xlsx-f1-formula-cached": make_atom(
            "atom-xlsx-f1-formula-cached",
            cell="F1",
            cell_range="F1:F1",
            row_label="Formula",
            target_column="Cached value",
            contract=display_contract(
                raw_value="168",
                normalized_value="168",
                display_value="168",
                number_format="0",
                value_type="formula_cached_value",
                formula_cached_value="168",
                provenance=high,
            ),
        ),
        "atom-xlsx-g1-missing-format": make_atom(
            "atom-xlsx-g1-missing-format",
            cell="G1",
            cell_range="G1:G1",
            row_label="Missing format",
            target_column="Raw fallback",
            contract=display_contract(
                raw_value="9999.5",
                normalized_value="9999.5",
                display_value=None,
                value_type="numeric",
                provenance="source_atom_materialized_raw_value_only_v1",
            ),
        ),
    }
    for idx, cell in enumerate(("A1", "B1", "C1", "D1", "E1"), start=1):
        base_contract = dict(atoms[{
            "A1": "atom-xlsx-a1-int",
            "B1": "atom-xlsx-b1-percent",
            "C1": "atom-xlsx-c1-currency",
            "D1": "atom-xlsx-d1-date",
            "E1": "atom-xlsx-e1-blank",
        }[cell]]["xlsx_display_contract"])
        atoms[f"atom-xlsx-summary-{idx}"] = make_atom(
            f"atom-xlsx-summary-{idx}",
            cell=cell,
            cell_range="A1:E20",
            row_label=f"Summary row {idx}",
            target_column=f"Summary col {idx}",
            contract=base_contract,
            table_id="table:Book.xlsx:Sheet1:A1:E20",
        )
    atoms["atom-xlsx-large-range"] = make_atom(
        "atom-xlsx-large-range",
        cell="A1",
        cell_range="A1:Z1000",
        row_label="Large range",
        target_column="Large range",
        contract=display_contract(
            raw_value="too-large",
            normalized_value="too-large",
            display_value="too-large",
            number_format="@",
            value_type="text",
            provenance=high,
        ),
        table_id="table:Book.xlsx:Sheet1:A1:Z1000",
    )
    other = make_atom(
        "atom-xlsx-other-workbook-a1",
        cell="A1",
        cell_range="A1:A1",
        row_label="Other workbook",
        target_column="Integer",
        contract=display_contract(
            raw_value=42,
            normalized_value=42,
            display_value="42",
            number_format="0",
            value_type="integer",
            provenance=high,
        ),
        table_id="table:Other.xlsx:Sheet1:A1:A1",
    )
    other["source_identity"] = "XLSX:Other.xlsx:Sheet1:A1:A1"
    other["raw_locator"]["workbook"] = "Other.xlsx"
    other["canonical_citation_payload"]["workbook"] = "Other.xlsx"
    atoms["atom-xlsx-other-workbook-a1"] = other
    return atoms


def search_views() -> dict[str, dict[str, Any]]:
    views: dict[str, dict[str, Any]] = {}
    for atom_id, atom in source_atoms().items():
        views[f"sv-{atom_id}"] = {
            "search_view_id": f"sv-{atom_id}",
            "source_atom_ids": [atom_id],
            "source_family": "XLSX",
            "vector_payload_text": f"POISONED_VECTOR_PAYLOAD_{atom_id}",
            "canonical_citation_payload": {
                "workbook": "Poison.xlsx",
                "sheet": "Wrong",
                "cell": "Z99",
                "display_value": "DO_NOT_USE_VECTOR_PAYLOAD",
            },
        }
    return views


def atom_ids(*ids: str) -> tuple[str, ...]:
    return tuple(ids)


def build_cases(*, include_user_review_required_case: bool = False) -> list[dict[str, Any]]:
    cases = [
        {
            "review_id": "v3_22_001",
            "query_id": "v3_22_xlsx_integer_a1",
            "diagnostic_case_id": "v3_22_xlsx_integer_a1",
            "bucket": "xlsx_single_cell_integer_display",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            "candidate_source_atom_ids": atom_ids("atom-xlsx-a1-int"),
            "rendering_mode_hint": "SINGLE_CELL_VALUE",
        },
        {
            "review_id": "v3_22_002",
            "query_id": "v3_22_xlsx_percentage_b1",
            "diagnostic_case_id": "v3_22_xlsx_percentage_b1",
            "bucket": "xlsx_single_cell_percentage_display",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 B1 퍼센트 표시값 알려줘",
            "candidate_source_atom_ids": atom_ids("atom-xlsx-b1-percent"),
            "rendering_mode_hint": "SINGLE_CELL_VALUE",
        },
        {
            "review_id": "v3_22_003",
            "query_id": "v3_22_xlsx_currency_c1",
            "diagnostic_case_id": "v3_22_xlsx_currency_c1",
            "bucket": "xlsx_single_cell_currency_display",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 C1 통화 표시값 알려줘",
            "candidate_source_atom_ids": atom_ids("atom-xlsx-c1-currency"),
            "rendering_mode_hint": "SINGLE_CELL_VALUE",
        },
        {
            "review_id": "v3_22_004",
            "query_id": "v3_22_xlsx_date_d1",
            "diagnostic_case_id": "v3_22_xlsx_date_d1",
            "bucket": "xlsx_single_cell_date_display",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 D1 날짜 표시값 알려줘",
            "candidate_source_atom_ids": atom_ids("atom-xlsx-d1-date"),
            "rendering_mode_hint": "SINGLE_CELL_VALUE",
        },
        {
            "review_id": "v3_22_005",
            "query_id": "v3_22_xlsx_datetime_d2",
            "diagnostic_case_id": "v3_22_xlsx_datetime_d2",
            "bucket": "xlsx_single_cell_datetime_display",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 D2 일시 표시값 알려줘",
            "candidate_source_atom_ids": atom_ids("atom-xlsx-d2-datetime"),
            "rendering_mode_hint": "SINGLE_CELL_VALUE",
        },
        {
            "review_id": "v3_22_006",
            "query_id": "v3_22_xlsx_blank_e1",
            "diagnostic_case_id": "v3_22_xlsx_blank_e1",
            "bucket": "xlsx_single_cell_blank_display",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 E1 빈 셀인지 알려줘",
            "candidate_source_atom_ids": atom_ids("atom-xlsx-e1-blank"),
            "rendering_mode_hint": "SINGLE_CELL_VALUE",
        },
        {
            "review_id": "v3_22_007",
            "query_id": "v3_22_xlsx_formula_cached_f1",
            "diagnostic_case_id": "v3_22_xlsx_formula_cached_f1",
            "bucket": "xlsx_formula_cached_value_display",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 F1 수식 캐시 표시값 알려줘",
            "candidate_source_atom_ids": atom_ids("atom-xlsx-f1-formula-cached"),
            "rendering_mode_hint": "SINGLE_CELL_VALUE",
        },
        {
            "review_id": "v3_22_008",
            "query_id": "v3_22_xlsx_small_range_a1_b2",
            "diagnostic_case_id": "v3_22_xlsx_small_range_a1_b2",
            "bucket": "xlsx_small_bounded_range_table",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 범위 A1:B2 값을 표로 알려줘",
            "candidate_source_atom_ids": atom_ids(
                "atom-xlsx-a1-int",
                "atom-xlsx-b1-percent",
                "atom-xlsx-a2-text",
                "atom-xlsx-b2-merged",
            ),
            "rendering_mode_hint": "SMALL_RANGE_TABLE",
        },
        {
            "review_id": "v3_22_009",
            "query_id": "v3_22_xlsx_broad_bounded_summary",
            "diagnostic_case_id": "v3_22_xlsx_broad_bounded_summary",
            "bucket": "xlsx_broad_bounded_range_summary",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 범위 A1:E20 값을 요약해줘",
            "candidate_source_atom_ids": atom_ids(
                "atom-xlsx-summary-1",
                "atom-xlsx-summary-2",
                "atom-xlsx-summary-3",
                "atom-xlsx-summary-4",
                "atom-xlsx-summary-5",
            ),
            "rendering_mode_hint": "BOUNDED_RANGE_SUMMARY",
        },
        {
            "review_id": "v3_22_010",
            "query_id": "v3_22_xlsx_missing_format_metadata_fallback",
            "diagnostic_case_id": "v3_22_xlsx_missing_format_metadata_fallback",
            "bucket": "xlsx_missing_format_metadata_raw_fallback",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 G1 값 알려줘",
            "candidate_source_atom_ids": atom_ids("atom-xlsx-g1-missing-format"),
            "rendering_mode_hint": "FORMAT_METADATA_UNAVAILABLE",
        },
        {
            "review_id": "v3_22_011",
            "query_id": "v3_22_xlsx_deictic_context_missing",
            "diagnostic_case_id": "v3_22_xlsx_deictic_context_missing",
            "bucket": "xlsx_deictic_context_missing_fail_closed",
            "source_family": "XLSX",
            "query": "이 표에서 선택한 범위 값을 알려줘",
            "candidate_source_atom_ids": atom_ids("atom-xlsx-a1-int"),
            "rough_query_hint": True,
            "rendering_mode_hint": "AMBIGUOUS_RANGE_CONTEXT_REQUIRED",
        },
        {
            "review_id": "v3_22_012",
            "query_id": "v3_22_xlsx_unsupported_large_range",
            "diagnostic_case_id": "v3_22_xlsx_unsupported_large_range",
            "bucket": "xlsx_unsupported_large_range_fail_closed",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 범위 A1:Z1000 값을 전부 알려줘",
            "candidate_source_atom_ids": atom_ids("atom-xlsx-large-range"),
            "rendering_mode_hint": "UNSUPPORTED_RANGE_TOO_LARGE",
        },
        {
            "review_id": "v3_22_013",
            "query_id": "v3_22_xlsx_ambiguous_range_context_required",
            "diagnostic_case_id": "v3_22_xlsx_ambiguous_range_context_required",
            "bucket": "xlsx_ambiguous_workbook_context_required",
            "source_family": "XLSX",
            "query": "Sheet1 시트 셀 A1 값 알려줘",
            "candidate_source_atom_ids": atom_ids("atom-xlsx-a1-int", "atom-xlsx-other-workbook-a1"),
            "rendering_mode_hint": "AMBIGUOUS_RANGE_CONTEXT_REQUIRED",
        },
        {
            "review_id": "v3_22_014",
            "query_id": "v3_22_xlsx_index_unavailable",
            "diagnostic_case_id": "v3_22_xlsx_index_unavailable",
            "bucket": "xlsx_index_unavailable_fail_closed",
            "source_family": "XLSX",
            "query": "Book.xlsx 시트 Sheet1 셀 A1 값 알려줘",
            "candidate_source_atom_ids": atom_ids("atom-xlsx-a1-int"),
            "index_available": False,
            "rendering_mode_hint": "AMBIGUOUS_RANGE_CONTEXT_REQUIRED",
        },
    ]
    if include_user_review_required_case:
        review_case = dict(cases[9])
        review_case.update(
            {
                "review_id": "v3_22_review_001",
                "query_id": "v3_22_xlsx_formatting_policy_review_required",
                "diagnostic_case_id": "v3_22_xlsx_formatting_policy_review_required",
                "bucket": "xlsx_formatting_policy_user_decision_required",
                "user_owned_review_required": True,
                "user_owned_review_reason": "formatting_policy_user_decision_required",
            }
        )
        cases.append(review_case)
    return cases


def cache_items_for_cases(cases: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not case.get("cache_hit"):
            continue
        namespace = clean(case.get("cache_namespace")) or CACHE_NAMESPACE
        key = cache_key_for_query(run_id=RUN_ID, query_id=clean(case.get("query_id")), namespace=namespace)
        items[key] = {"source_atom_ids": list(case.get("candidate_source_atom_ids") or ()), "evidence_bundle_ids": []}
    return items


def build_runtime_for_case(case: Mapping[str, Any], cache_items: Mapping[str, Mapping[str, Any]]) -> AgentRuntime:
    return AgentRuntime(
        registry=build_default_tool_registry(),
        search_index=InMemorySearchIndexAdapter(
            search_views=search_views(),
            namespace=ADAPTER_NAMESPACE,
            available=case.get("index_available", True) is not False,
            max_candidates=16,
        ),
        source_atom_store=InMemorySourceAtomStoreAdapter(
            source_atoms=source_atoms(),
            namespace=ADAPTER_NAMESPACE,
            available=case.get("db_available", True) is not False,
            max_hydration_ids=16,
        ),
        runtime_cache=InMemoryRuntimeCacheAdapter(
            namespace=clean(case.get("cache_namespace")) or CACHE_NAMESPACE,
            cache_items=cache_items,
            available=case.get("cache_available", True) is not False,
        ),
    )


def base_request_context(case: Mapping[str, Any]) -> dict[str, Any]:
    context = {
        "diagnostic_tenant_id": DIAGNOSTIC_TENANT_ID,
        "namespace": ADAPTER_NAMESPACE,
        "cache_namespace": clean(case.get("cache_namespace")) or CACHE_NAMESPACE,
        "expected_cache_namespace": clean(case.get("expected_cache_namespace")) or clean(case.get("cache_namespace")) or CACHE_NAMESPACE,
        "tenant_id": DIAGNOSTIC_TENANT_ID,
        "authorized_source_atom_ids": tuple(case.get("candidate_source_atom_ids") or ()),
    }
    context.update(v321.v320.v319.v317.as_mapping(case.get("request_context")))
    return context


def source_atom_contract(atom_id: str) -> dict[str, Any]:
    atom = source_atoms().get(clean(atom_id), {})
    contract = atom.get("xlsx_display_contract") if isinstance(atom.get("xlsx_display_contract"), Mapping) else {}
    return dict(contract)


def sort_cell_key(atom_id: str) -> tuple[int, int, str]:
    atom = source_atoms().get(clean(atom_id), {})
    locator = atom.get("raw_locator") if isinstance(atom.get("raw_locator"), Mapping) else {}
    cell = clean(locator.get("cell")).upper()
    parsed = cell_ref_to_row_col(cell)
    if parsed is None:
        return (9999, 9999, atom_id)
    row, col = parsed
    return (row, col, atom_id)


def cell_ref_to_row_col(cell: str) -> tuple[int, int] | None:
    return shared_cell_ref_to_row_col(cell)


def range_shape(range_text: str) -> tuple[int, int, int]:
    return shared_range_shape(range_text)


def explicit_query_range_area(query: str) -> int | None:
    return shared_explicit_query_range_area(query)


def selected_cell_span_area(selected_ids: Sequence[str]) -> int:
    points: list[tuple[int, int]] = []
    atoms = source_atoms()
    for atom_id in selected_ids:
        atom = atoms.get(clean(atom_id), {})
        locator = atom.get("raw_locator") if isinstance(atom.get("raw_locator"), Mapping) else {}
        parsed = cell_ref_to_row_col(clean(locator.get("cell")))
        if parsed is not None:
            points.append(parsed)
    if not points:
        return 1
    rows = [row for row, _col in points]
    cols = [col for _row, col in points]
    return (max(rows) - min(rows) + 1) * (max(cols) - min(cols) + 1)


def selected_locator_range_max_area(selected_ids: Sequence[str]) -> int:
    atoms = source_atoms()
    areas: list[int] = []
    for atom_id in selected_ids:
        atom = atoms.get(clean(atom_id), {})
        locator = atom.get("raw_locator") if isinstance(atom.get("raw_locator"), Mapping) else {}
        locator_range = clean(locator.get("range")) or clean(locator.get("cell"))
        _rows, _cols, area = range_shape(locator_range)
        areas.append(area)
    return max(areas or [1])


def selected_locator_scope_is_ambiguous(selected_ids: Sequence[str]) -> bool:
    atoms = source_atoms()
    workbooks: set[str] = set()
    sheets: set[str] = set()
    for atom_id in selected_ids:
        atom = atoms.get(clean(atom_id), {})
        locator = atom.get("raw_locator") if isinstance(atom.get("raw_locator"), Mapping) else {}
        workbook = clean(locator.get("workbook")).casefold()
        sheet = clean(locator.get("sheet")).casefold()
        if workbook:
            workbooks.add(workbook)
        if sheet:
            sheets.add(sheet)
    return len(workbooks) > 1 or len(sheets) > 1


def runtime_result_requires_context(result: Any) -> bool:
    text_fields = " ".join(
        clean(value)
        for value in (
            getattr(result, "response_policy_bucket", ""),
            getattr(result, "fail_closed_reason", ""),
            getattr(result, "blocked_reason", ""),
        )
    ).upper()
    return bool(getattr(result, "active_context_required", False)) or "CONTEXT_REQUIRED" in text_fields or "AMBIGUOUS" in text_fields


def determine_range_mode(case: Mapping[str, Any], selected_ids: Sequence[str], result: Any) -> str:
    # rendering_mode_hint stays fixture metadata only; runtime policy is derived
    # from the active-context result, actual user locator text, and SourceAtom locators.
    if runtime_result_requires_context(result):
        return "AMBIGUOUS_RANGE_CONTEXT_REQUIRED"
    if not selected_ids:
        return "AMBIGUOUS_RANGE_CONTEXT_REQUIRED" if getattr(result, "active_context_required", False) else "FORMAT_METADATA_UNAVAILABLE"
    if selected_locator_scope_is_ambiguous(selected_ids):
        return "AMBIGUOUS_RANGE_CONTEXT_REQUIRED"
    contracts = [source_atom_contract(atom_id) for atom_id in selected_ids]
    if any(clean(contract.get("format_confidence")) == "low" for contract in contracts):
        return "FORMAT_METADATA_UNAVAILABLE"

    query_range_area = explicit_query_range_area(clean(case.get("query")))
    if query_range_area is not None:
        if query_range_area > BOUNDED_SUMMARY_MAX_CELLS:
            return "UNSUPPORTED_RANGE_TOO_LARGE"
        if query_range_area <= SMALL_RANGE_MAX_CELLS:
            return "SINGLE_CELL_VALUE" if len(selected_ids) == 1 and query_range_area == 1 else "SMALL_RANGE_TABLE"
        return "BOUNDED_RANGE_SUMMARY"

    materialized_range_area = selected_locator_range_max_area(selected_ids)
    if len(selected_ids) == 1:
        if materialized_range_area > BOUNDED_SUMMARY_MAX_CELLS:
            return "UNSUPPORTED_RANGE_TOO_LARGE"
        return "SINGLE_CELL_VALUE"
    cell_span_area = selected_cell_span_area(selected_ids)
    area = max(cell_span_area, materialized_range_area)
    if cell_span_area <= SMALL_RANGE_MAX_CELLS and materialized_range_area <= SMALL_RANGE_MAX_CELLS:
        return "SMALL_RANGE_TABLE"
    if area <= BOUNDED_SUMMARY_MAX_CELLS:
        return "BOUNDED_RANGE_SUMMARY"
    return "UNSUPPORTED_RANGE_TOO_LARGE"


def rendered_xlsx_value(selected_ids: Sequence[str], mode: str) -> tuple[str, dict[str, Any]]:
    atoms = source_atoms()
    contracts = [source_atom_contract(atom_id) for atom_id in selected_ids]
    if not contracts:
        return "", empty_display_contract()
    first = dict(contracts[0])
    if mode == "SMALL_RANGE_TABLE":
        lines = ["| Cell | Display value | Raw value | Type | Format confidence |", "| --- | --- | --- | --- | --- |"]
        for atom_id in sorted(selected_ids, key=sort_cell_key):
            atom = atoms[clean(atom_id)]
            locator = atom["raw_locator"]
            contract = source_atom_contract(atom_id)
            owner = clean(contract.get("merged_owner_cell"))
            display = clean(contract.get("display_value"))
            if owner:
                display = f"{display} (merged owner {owner})"
            lines.append(
                "| "
                + " | ".join(
                    [
                        clean(locator.get("cell")),
                        display,
                        clean(contract.get("raw_value")),
                        clean(contract.get("value_type")),
                        clean(contract.get("format_confidence")),
                    ]
                )
                + " |"
            )
        first["display_value"] = "\n".join(lines)
        first["value_type"] = "small_range_table"
        first["format_provenance"] = "source_atom_materialized_xlsx_display_metadata_v1:small_range_table"
        return first["display_value"], first
    if mode == "BOUNDED_RANGE_SUMMARY":
        range_text = clean(atoms[clean(selected_ids[0])]["raw_locator"].get("range"))
        examples = []
        for atom_id in sorted(selected_ids, key=sort_cell_key):
            locator = atoms[clean(atom_id)]["raw_locator"]
            contract = source_atom_contract(atom_id)
            examples.append(f"{clean(locator.get('cell'))}={clean(contract.get('display_value'))}")
        first["display_value"] = (
            f"bounded_range={range_text}; materialized_cell_count={len(selected_ids)}; "
            f"shown_examples={', '.join(examples)}"
        )
        first["value_type"] = "bounded_range_summary"
        first["format_provenance"] = "source_atom_materialized_xlsx_display_metadata_v1:bounded_range_summary"
        return first["display_value"], first
    return clean(first.get("display_value")), first


def empty_display_contract() -> dict[str, Any]:
    return {
        "raw_value": "",
        "normalized_value": "",
        "display_value": "",
        "number_format": "",
        "value_type": "",
        "formula_cached_value": "",
        "formula_text_visible_to_user": False,
        "format_confidence": "low",
        "format_provenance": "",
        "format_drop_reason": "NO_SELECTED_XLSX_SOURCEATOM",
        "merged_cell": False,
        "merged_range": "",
        "merged_owner_cell": "",
    }


def sanitize_preview(value: Any, *, max_chars: int = 900) -> str:
    text = clean(value)
    if not text:
        return ""
    text = text.replace(str(ROOT), "[REPO_ROOT]").replace(ROOT.as_posix(), "[REPO_ROOT]")
    text = LOCAL_PATH_RE.sub("[LOCAL_PATH]", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text).strip()
    return text[:max_chars]


def selected_evidence_preview(source_atom_ids: Sequence[str], *, max_chars: int = 1200) -> str:
    atoms = source_atoms()
    snippets: list[str] = []
    for atom_id in source_atom_ids:
        atom = atoms.get(clean(atom_id), {})
        if not atom:
            continue
        locator = atom.get("canonical_citation_payload") if isinstance(atom.get("canonical_citation_payload"), Mapping) else {}
        contract = atom.get("xlsx_display_contract") if isinstance(atom.get("xlsx_display_contract"), Mapping) else {}
        snippets.append(
            "SourceAtom "
            f"{clean(atom_id)} workbook={clean(locator.get('workbook'))} sheet={clean(locator.get('sheet'))} "
            f"cell={clean(locator.get('cell'))} range={clean(locator.get('range'))} "
            f"xlsx_display_value={clean(contract.get('display_value'))} "
            f"xlsx_raw_value={clean(contract.get('raw_value'))} "
            f"xlsx_format_confidence={clean(contract.get('format_confidence'))}"
        )
    return sanitize_preview("\n".join(snippets), max_chars=max_chars)


def answer_ready_context(
    *,
    query: str,
    selected_ids: Sequence[str],
    mode: str,
    rendered_value: str,
    contract: Mapping[str, Any],
) -> str:
    fields = {
        "query": clean(query),
        "xlsx_display_value": clean(rendered_value),
        "xlsx_raw_value": clean(contract.get("raw_value")),
        "xlsx_normalized_value": clean(contract.get("normalized_value")),
        "xlsx_format_confidence": clean(contract.get("format_confidence")),
        "xlsx_format_provenance": clean(contract.get("format_provenance")),
        "xlsx_range_rendering_mode": clean(mode),
        "source_atom_ids": "|".join(clean(value) for value in selected_ids),
    }
    return sanitize_preview("\n".join(f"{key}={value}" for key, value in fields.items()), max_chars=1400)


def build_prompt(*, query: str, answer_ready: str, evidence_preview: str) -> str:
    return PROMPT_TEMPLATE.format(
        query=clean(query),
        answer_ready_context=clean(answer_ready),
        evidence=clean(evidence_preview),
    )


def parse_llm_json(raw: str) -> tuple[str, str, str]:
    return v321.parse_llm_json(raw)


def leakage_flags(row: Mapping[str, Any]) -> dict[str, bool]:
    packet_text = json.dumps(row, ensure_ascii=False)
    prompt_text = clean(row.get("sanitized_prompt_preview"))
    response_text = clean(row.get("raw_llm_response")) + " " + clean(row.get("parsed_final_answer"))
    path_text = "\n".join(
        clean(row.get(key))
        for key in (
            "sanitized_prompt_preview",
            "sanitized_evidence_preview",
            "raw_llm_response",
            "parsed_final_answer",
            "final_user_visible_answer",
            "answer_ready_context",
        )
    )
    forbidden_terms = ("expected_answer", "supporting_evidence", "target_locator", "gold_locator")
    return {
        "prompt_leakage": any(term in prompt_text for term in forbidden_terms),
        "response_leakage": any(term in response_text for term in forbidden_terms),
        "path_leakage": bool(LOCAL_PATH_RE.search(path_text)) or str(ROOT) in path_text or ROOT.as_posix() in path_text,
        "evidence_truth_violation": clean(row.get("evidence_truth_source")) not in {"source_atom_evidence_bundle", "none"},
        "vector_payload_evidence_truth_violation": clean(row.get("evidence_truth_source")).lower().startswith("vector")
        or "POISONED_VECTOR_PAYLOAD" in packet_text,
    }


def build_readiness(
    *,
    backend: str,
    base_url: str,
    model: str,
    blockers: Sequence[str],
    llm_client_provided: bool,
) -> dict[str, Any]:
    available = llm_client_provided or not blockers
    return {
        "schema_version": f"{RUN_ID}_local_llm_readiness_v1",
        "run_id": RUN_ID,
        "status": "LOCAL_LLM_AVAILABLE_DIAGNOSTIC_ONLY" if available else "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED",
        "generated_at": utc_now(),
        "local_llm_available": available,
        "backend": clean(backend),
        "base_url": sanitize_preview(base_url, max_chars=200),
        "model": clean(model),
        "blockers": list(blockers),
        "llm_client_provided_for_test": bool(llm_client_provided),
        "localhost_only": True,
        "noop_or_extractive_generator_used": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }


def build_prompt_manifest(*, backend: str, base_url: str, model: str) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_prompt_manifest_v1",
        "run_id": RUN_ID,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "prompt_sha256": sha256_text(PROMPT_TEMPLATE),
        "backend": clean(backend),
        "base_url": sanitize_preview(base_url, max_chars=200),
        "model": clean(model),
        "requires_korean_answer": True,
        "requires_supplied_evidence_only": True,
        "requires_strict_json_object": True,
        "prefers_display_value_when_format_confidence_high": True,
        "uses_expected_or_supporting_gold_text": False,
        "uses_raw_file_query_time_access": False,
        "uses_target_or_gold_locator_text": False,
        "uses_vector_payload_as_evidence": False,
        "source_atom_evidence_bundle_truth_only": True,
        "formula_text_visible_to_user": False,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
    }


def build_live_audit_row(result: Any) -> dict[str, Any]:
    row = v321.build_live_audit_row(result)
    row["schema_version"] = f"{RUN_ID}_runtime_adapter_audit_v1"
    row["input_schema_version"] = "rag_v3_22_xlsx_display_runtime_input_v1"
    row["output_schema_version"] = "rag_v3_22_xlsx_display_runtime_output_v1"
    row["diagnostic_tenant_id"] = DIAGNOSTIC_TENANT_ID
    row["tenant_id"] = DIAGNOSTIC_TENANT_ID
    row["namespace"] = ADAPTER_NAMESPACE
    return row


def invoke_llm(
    *,
    prompt: str,
    query_id: str,
    backend: str,
    base_url: str,
    model: str,
    max_tokens: int,
    timeout_seconds: int,
    llm_client: Callable[..., str] | None,
) -> tuple[str, int, float, str]:
    request_id = f"{RUN_ID}:{query_id}"
    start = time.perf_counter()
    if llm_client is not None:
        raw = llm_client(
            prompt,
            query_id=query_id,
            backend=backend,
            base_url=base_url,
            model=model,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )
    else:
        raw = call_local_llm(
            backend=backend,
            base_url=base_url,
            model=model,
            prompt=prompt,
            temperature=0.0,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
        )
    elapsed_ms = round((time.perf_counter() - start) * 1000.0, 3)
    return clean(raw), len(clean(raw)), elapsed_ms, request_id


def build_rows(
    *,
    backend: str,
    base_url: str,
    model: str,
    readiness: Mapping[str, Any],
    max_tokens: int,
    timeout_seconds: int,
    llm_client: Callable[..., str] | None,
    include_user_review_required_case: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    cases = build_cases(include_user_review_required_case=include_user_review_required_case)
    cache_items = cache_items_for_cases(cases)
    per_query: list[dict[str, Any]] = []
    route_policy: list[dict[str, Any]] = []
    runtime_contract: list[dict[str, Any]] = []
    user_response_policy: list[dict[str, Any]] = []
    runtime_adapter: list[dict[str, Any]] = []
    llm_observability: list[dict[str, Any]] = []
    formatting_audit: list[dict[str, Any]] = []
    leakage_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    local_llm_available = bool(readiness.get("local_llm_available"))
    unavailable_reason = "; ".join(clean(value) for value in readiness.get("blockers", []) if clean(value))
    for case in cases:
        runtime = build_runtime_for_case(case, cache_items)
        context = base_request_context(case)
        result = runtime.invoke(
            AgentRuntimeRequest(
                run_id=RUN_ID,
                query_id=clean(case.get("query_id")),
                diagnostic_case_id=clean(case.get("diagnostic_case_id")),
                query_text=clean(case.get("query")),
                source_family=clean(case.get("source_family")),
                source_registry={},
                candidate_source_atom_ids=tuple(case.get("candidate_source_atom_ids") or ()),
                rough_query_hint=bool(case.get("rough_query_hint")),
                request_context=context,
                runtime_flags=v321.v320.v319.v317.as_mapping(case.get("runtime_flags")),
                internal_replay_adapter=True,
            )
        )
        trace_rows.extend(result.trace_rows)
        runtime_adapter.extend(row for row in (build_live_audit_row(result), *list(result.runtime_adapter_trace_rows)))
        selected_ids = list(result.selected_source_atom_ids)
        mode = determine_range_mode(case, selected_ids, result)
        rendered_value, display = rendered_xlsx_value(selected_ids, mode)
        if mode in {"UNSUPPORTED_RANGE_TOO_LARGE", "AMBIGUOUS_RANGE_CONTEXT_REQUIRED"}:
            answer_allowed = False
        else:
            answer_allowed = bool(result.answer_allowed_by_policy)
        evidence_preview = selected_evidence_preview(selected_ids)
        answer_ready = (
            answer_ready_context(
                query=clean(case.get("query")),
                selected_ids=selected_ids,
                mode=mode,
                rendered_value=rendered_value,
                contract=display,
            )
            if answer_allowed
            else ""
        )
        prompt = build_prompt(query=clean(case.get("query")), answer_ready=answer_ready, evidence_preview=evidence_preview) if answer_allowed else ""
        prompt_sha = sha256_text(prompt) if prompt else ""
        llm_invoked = False
        raw_response = ""
        raw_response_sha = ""
        parsed_answer = ""
        provenance = v321.citation_summary(selected_ids, list(result.evidence_bundle_ids))
        blocked_reason = clean(result.fail_closed_reason or result.blocked_reason)
        llm_latency_ms = 0.0
        llm_request_id = ""
        llm_unavailable_reason = ""
        llm_parse_error = ""
        if answer_allowed:
            if not local_llm_available:
                blocked_reason = "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
                llm_unavailable_reason = unavailable_reason or "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"
            else:
                llm_invoked = True
                try:
                    raw_response, _raw_len, llm_latency_ms, llm_request_id = invoke_llm(
                        prompt=prompt,
                        query_id=result.query_id,
                        backend=backend,
                        base_url=base_url,
                        model=model,
                        max_tokens=max_tokens,
                        timeout_seconds=timeout_seconds,
                        llm_client=llm_client,
                    )
                except Exception as exc:
                    raw_response = ""
                    blocked_reason = "LOCAL_LLM_INVOCATION_FAILED_FAIL_CLOSED"
                    llm_unavailable_reason = f"{type(exc).__name__}: {exc}"
                if raw_response:
                    raw_response_sha = sha256_text(raw_response)
                    parsed_answer, parsed_provenance, llm_parse_error = parse_llm_json(raw_response)
                    provenance = parsed_provenance or provenance
                    if llm_parse_error:
                        blocked_reason = llm_parse_error
                elif llm_invoked and not llm_unavailable_reason:
                    blocked_reason = "LOCAL_LLM_EMPTY_RESPONSE_FAIL_CLOSED"
                    llm_parse_error = blocked_reason
        else:
            if mode == "UNSUPPORTED_RANGE_TOO_LARGE":
                blocked_reason = "UNSUPPORTED_RANGE_TOO_LARGE"
            elif mode == "AMBIGUOUS_RANGE_CONTEXT_REQUIRED" and not blocked_reason:
                blocked_reason = "AMBIGUOUS_RANGE_CONTEXT_REQUIRED"
            elif not blocked_reason:
                blocked_reason = "ANSWER_NOT_ALLOWED_BY_POLICY"
        final_user_visible_answer = parsed_answer
        if answer_allowed and not parsed_answer:
            final_user_visible_answer = blocked_reason or "LOCAL_LLM_RESPONSE_FAIL_CLOSED"
        elif not answer_allowed:
            final_user_visible_answer = blocked_reason if mode == "UNSUPPORTED_RANGE_TOO_LARGE" else (result.final_answer or blocked_reason)
        response_bucket = result.response_policy_bucket
        if mode == "UNSUPPORTED_RANGE_TOO_LARGE":
            response_bucket = "UNSUPPORTED_RANGE_TOO_LARGE"
        elif mode == "AMBIGUOUS_RANGE_CONTEXT_REQUIRED" and response_bucket == "ANSWER_ALLOWED":
            response_bucket = "CONTEXT_REQUIRED"
        row = {
            "schema_version": f"{RUN_ID}_per_query_v1",
            "run_id": RUN_ID,
            "review_id": clean(case.get("review_id")),
            "query_id": result.query_id,
            "diagnostic_case_id": result.diagnostic_case_id,
            "bucket": clean(case.get("bucket")),
            "source_family": clean(case.get("source_family")),
            "actual_input_query": clean(case.get("query")),
            "actual_input_query_sha256": sha256_text(clean(case.get("query"))),
            "route_lane": result.route_lane,
            "agent_route": result.agent_route,
            "response_policy_bucket": response_bucket,
            "answer_allowed_by_policy": answer_allowed,
            "abstained": not answer_allowed or bool(blocked_reason and not parsed_answer),
            "llm_invoked": llm_invoked,
            "llm_backend": clean(backend),
            "llm_model_label": clean(model),
            "llm_request_id": llm_request_id,
            "llm_latency_ms": llm_latency_ms,
            "raw_llm_response": raw_response,
            "raw_llm_response_sha256": raw_response_sha,
            "parsed_final_answer": parsed_answer,
            "final_user_visible_answer": final_user_visible_answer,
            "citation_or_provenance_summary": provenance,
            "blocked_reason": blocked_reason,
            "llm_unavailable_reason": llm_unavailable_reason,
            "llm_parse_error": llm_parse_error,
            "prompt_template_version": PROMPT_TEMPLATE_VERSION if prompt else "",
            "prompt_sha256": prompt_sha,
            "sanitized_prompt_preview": sanitize_preview(prompt),
            "answer_ready_context": answer_ready,
            "evidence_truth_source": result.evidence_truth_source,
            "selected_source_atom_ids": selected_ids,
            "selected_source_atom_count": len(selected_ids),
            "evidence_bundle_ids": list(result.evidence_bundle_ids),
            "sanitized_evidence_preview": evidence_preview,
            "xlsx_range_rendering_mode": mode,
            "xlsx_raw_value": clean(display.get("raw_value")),
            "xlsx_normalized_value": clean(display.get("normalized_value")),
            "xlsx_display_value": clean(rendered_value),
            "xlsx_number_format": clean(display.get("number_format")),
            "xlsx_value_type": clean(display.get("value_type")),
            "xlsx_formula_cached_value": clean(display.get("formula_cached_value")),
            "xlsx_formula_text_visible_to_user": bool(display.get("formula_text_visible_to_user")),
            "formula_evaluated_at_query_time": False,
            "xlsx_format_confidence": clean(display.get("format_confidence")),
            "xlsx_format_provenance": clean(display.get("format_provenance")),
            "xlsx_format_drop_reason": clean(display.get("format_drop_reason")),
            "xlsx_merged_cell": bool(display.get("merged_cell")),
            "xlsx_merged_range": clean(display.get("merged_range")),
            "xlsx_merged_owner_cell": clean(display.get("merged_owner_cell")),
            "runtime_contract_violation": result.runtime_contract_violation,
            "fail_closed_reason": blocked_reason if not answer_allowed else result.fail_closed_reason,
            "adapter_fail_closed_reason": result.adapter_fail_closed_reason,
            "db_contract_status": result.db_contract_status,
            "index_contract_status": result.index_contract_status,
            "cache_contract_status": result.cache_contract_status,
            "cache_hit": result.cache_hit,
            "cache_key_namespace": result.cache_key_namespace,
            "vector_payload_candidate_only": True,
            "production_write_attempted": False,
            "broad_scan_attempted": False,
            "raw_file_query_time_accessed": False,
            "official_metric_candidate": False,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "human_review_required": bool(case.get("user_owned_review_required")),
            "user_owned_review_reason": clean(case.get("user_owned_review_reason")),
            **guardrail_flags(),
        }
        leaks = leakage_flags(row)
        row.update(leaks)
        per_query.append(row)
        llm_observability.append(
            {
                "schema_version": f"{RUN_ID}_llm_io_observability_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "answer_allowed_by_policy": answer_allowed,
                "llm_invoked": llm_invoked,
                "raw_llm_response_present": bool(raw_response),
                "parsed_final_answer_present": bool(parsed_answer),
                "prompt_template_version": PROMPT_TEMPLATE_VERSION if prompt else "",
                "prompt_sha256": prompt_sha,
                "raw_llm_response_sha256": raw_response_sha,
                "llm_unavailable_reason": llm_unavailable_reason,
                "llm_parse_error": llm_parse_error,
                "selected_source_atom_ids": selected_ids,
                "evidence_bundle_ids": list(result.evidence_bundle_ids),
                "evidence_truth_source": result.evidence_truth_source,
                "official_metric_input_rows": 0,
                "promotion_evidence": False,
            }
        )
        route_policy.append(
            {
                "schema_version": f"{RUN_ID}_route_policy_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "route_lane": result.route_lane,
                "response_policy_bucket": response_bucket,
                "selected_tool_ids": result.tool_call_sequence,
                "range_rendering_mode": mode,
                "fail_closed_reason": row["fail_closed_reason"],
                "llm_invoked": llm_invoked,
                "diagnostic_only": True,
            }
        )
        runtime_contract.append(
            {
                "schema_version": f"{RUN_ID}_runtime_contract_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "runtime_contract_violation": result.runtime_contract_violation,
                "runtime_contract_guards": list(RUNTIME_CONTRACT_GUARDS),
                "raw_file_query_time_accessed": False,
                "raw_xlsx_query_time_parsing": False,
                "full_workbook_sheet_scan": False,
                "broad_source_atom_scan": False,
                "vector_payload_used_as_evidence_truth": False,
                "target_locator_used": False,
                "gold_locator_used": False,
                "expected_supporting_text_used": False,
                "direct_normalized_value_query_matching_used": False,
                "formula_evaluated_at_query_time": False,
                "unbounded_fallback": False,
                "production_write_allowed": False,
                "official_metric_input_rows": 0,
            }
        )
        user_response_policy.append(
            {
                "schema_version": f"{RUN_ID}_user_response_policy_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "response_policy_bucket": response_bucket,
                "answer_allowed_by_policy": answer_allowed,
                "abstained": row["abstained"],
                "blocked_reason": blocked_reason,
                "llm_invoked": llm_invoked,
                "evidence_truth_source": result.evidence_truth_source,
                "xlsx_range_rendering_mode": mode,
                "diagnostic_only": True,
            }
        )
        formatting_audit.append(
            {
                "schema_version": f"{RUN_ID}_formatting_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "xlsx_range_rendering_mode": mode,
                "xlsx_raw_value": row["xlsx_raw_value"],
                "xlsx_normalized_value": row["xlsx_normalized_value"],
                "xlsx_display_value": row["xlsx_display_value"],
                "xlsx_number_format": row["xlsx_number_format"],
                "xlsx_value_type": row["xlsx_value_type"],
                "xlsx_formula_cached_value": row["xlsx_formula_cached_value"],
                "xlsx_formula_text_visible_to_user": row["xlsx_formula_text_visible_to_user"],
                "formula_evaluated_at_query_time": False,
                "xlsx_format_confidence": row["xlsx_format_confidence"],
                "xlsx_format_provenance": row["xlsx_format_provenance"],
                "xlsx_format_drop_reason": row["xlsx_format_drop_reason"],
                "selected_source_atom_ids": selected_ids,
                "source_atom_evidence_bundle_truth_only": True,
                "raw_xlsx_query_time_parsing": False,
            }
        )
        leakage_rows.append(
            {
                "schema_version": f"{RUN_ID}_leakage_audit_v1",
                "run_id": RUN_ID,
                "query_id": result.query_id,
                "diagnostic_case_id": result.diagnostic_case_id,
                "leakage_detected": any(leaks.values()),
                "leakage_fields": [key for key, value in leaks.items() if value],
                "prompt_leakage": leaks["prompt_leakage"],
                "response_leakage": leaks["response_leakage"],
                "path_leakage": leaks["path_leakage"],
                "evidence_truth_violation": leaks["evidence_truth_violation"],
                "vector_payload_evidence_truth_violation": leaks["vector_payload_evidence_truth_violation"],
                "target_locator_used": False,
                "gold_locator_used": False,
                "expected_supporting_text_used": False,
                "diagnostic_only": True,
            }
        )
        if row["human_review_required"]:
            review_rows.append(row)
    return {
        "per_query": per_query,
        "route_policy_audit": route_policy,
        "runtime_contract_audit": runtime_contract,
        "user_response_policy_audit": user_response_policy,
        "runtime_adapter_audit": runtime_adapter,
        "llm_io_observability": llm_observability,
        "formatting_audit": formatting_audit,
        "leakage_audit": leakage_rows,
        "trace_rows": trace_rows,
        "review_rows": review_rows,
    }


def build_metrics(rows: Mapping[str, Sequence[Mapping[str, Any]]], readiness: Mapping[str, Any]) -> dict[str, Any]:
    per_query = list(rows["per_query"])
    route_counts = Counter(clean(row.get("route_lane")) for row in per_query)
    response_counts = Counter(clean(row.get("response_policy_bucket")) for row in per_query)
    mode_counts = Counter(clean(row.get("xlsx_range_rendering_mode")) for row in per_query)

    def display_value_used(row: Mapping[str, Any]) -> bool:
        return (
            bool(row.get("answer_allowed_by_policy"))
            and clean(row.get("xlsx_format_confidence")) == "high"
            and clean(row.get("xlsx_display_value")) != ""
            and clean(row.get("xlsx_format_drop_reason")) == ""
            and clean(row.get("xlsx_range_rendering_mode")) != "FORMAT_METADATA_UNAVAILABLE"
        )

    return {
        "schema_version": f"{RUN_ID}_metrics_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "report_row_count": len(per_query),
        "xlsx_case_count": sum(1 for row in per_query if row["source_family"] == "XLSX"),
        "xlsx_answer_allowed_count": sum(1 for row in per_query if row["source_family"] == "XLSX" and row["answer_allowed_by_policy"]),
        "llm_invoked_count": sum(1 for row in per_query if row["llm_invoked"]),
        "raw_llm_response_present_count": sum(1 for row in per_query if clean(row.get("raw_llm_response"))),
        "parsed_final_answer_present_count": sum(1 for row in per_query if clean(row.get("parsed_final_answer"))),
        "single_cell_value_count": mode_counts["SINGLE_CELL_VALUE"],
        "small_range_table_count": mode_counts["SMALL_RANGE_TABLE"],
        "bounded_range_summary_count": mode_counts["BOUNDED_RANGE_SUMMARY"],
        "display_value_used_count": sum(1 for row in per_query if display_value_used(row)),
        "raw_value_fallback_count": sum(1 for row in per_query if row["xlsx_format_drop_reason"] == "FORMAT_METADATA_UNAVAILABLE"),
        "format_confidence_high_count": sum(1 for row in per_query if row["xlsx_format_confidence"] == "high"),
        "format_confidence_low_count": sum(1 for row in per_query if row["xlsx_format_confidence"] == "low"),
        "format_metadata_unavailable_count": sum(1 for row in per_query if row["xlsx_format_drop_reason"] == "FORMAT_METADATA_UNAVAILABLE"),
        "formula_cached_value_used_count": sum(1 for row in per_query if clean(row.get("xlsx_formula_cached_value"))),
        "blank_cell_answer_count": sum(1 for row in per_query if row["xlsx_value_type"] == "blank"),
        "unsupported_range_too_large_count": mode_counts["UNSUPPORTED_RANGE_TOO_LARGE"],
        "ambiguous_range_context_required_count": mode_counts["AMBIGUOUS_RANGE_CONTEXT_REQUIRED"],
        "runtime_contract_violation_count": sum(1 for row in per_query if row["runtime_contract_violation"]),
        "vector_payload_evidence_truth_violation_count": sum(
            1 for row in per_query if row["vector_payload_evidence_truth_violation"]
        ),
        "raw_file_query_time_accessed": False,
        "fail_closed_no_llm_invocation_count": sum(1 for row in per_query if not row["answer_allowed_by_policy"] and not row["llm_invoked"]),
        "local_llm_unavailable_fail_closed_count": sum(1 for row in per_query if row["blocked_reason"] == "LOCAL_LLM_UNAVAILABLE_FAIL_CLOSED"),
        "prompt_leakage_count": sum(1 for row in per_query if row["prompt_leakage"]),
        "response_leakage_count": sum(1 for row in per_query if row["response_leakage"]),
        "path_leakage_count": sum(1 for row in per_query if row["path_leakage"]),
        "evidence_truth_violation_count": sum(1 for row in per_query if row["evidence_truth_violation"]),
        "production_write_attempt_count": sum(1 for row in per_query if row["production_write_attempted"]),
        "broad_source_atom_scan_attempt_count": sum(1 for row in per_query if row["broad_scan_attempted"]),
        "route_lane_counts": dict(sorted(route_counts.items())),
        "response_policy_bucket_counts": dict(sorted(response_counts.items())),
        "range_rendering_mode_counts": dict(sorted(mode_counts.items())),
        "local_llm_available": bool(readiness.get("local_llm_available")),
        "human_review_required": bool(rows["review_rows"]),
        "review_csv_created": bool(rows["review_rows"]),
        "official_metric_input_rows": 0,
        "official_metric": False,
        "promotion_evidence": False,
        "diagnostic_only": True,
        **guardrail_flags(),
    }


def build_guardrail_audit(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_guardrail_audit_v1",
        "run_id": RUN_ID,
        "status": STATUS,
        "runtime_contract_violation_count": metrics["runtime_contract_violation_count"],
        "prompt_leakage_count": metrics["prompt_leakage_count"],
        "response_leakage_count": metrics["response_leakage_count"],
        "path_leakage_count": metrics["path_leakage_count"],
        "evidence_truth_violation_count": metrics["evidence_truth_violation_count"],
        "production_write_attempt_count": metrics["production_write_attempt_count"],
        "broad_source_atom_scan_attempt_count": metrics["broad_source_atom_scan_attempt_count"],
        "vector_payload_evidence_truth_violation_count": metrics["vector_payload_evidence_truth_violation_count"],
        **guardrail_flags(),
    }


def build_leakage_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_leakage_summary_v1",
        "run_id": RUN_ID,
        "prompt_leakage_count": sum(1 for row in rows if row.get("prompt_leakage")),
        "response_leakage_count": sum(1 for row in rows if row.get("response_leakage")),
        "path_leakage_count": sum(1 for row in rows if row.get("path_leakage")),
        "evidence_truth_violation_count": sum(1 for row in rows if row.get("evidence_truth_violation")),
        "vector_payload_evidence_truth_violation_count": sum(1 for row in rows if row.get("vector_payload_evidence_truth_violation")),
        "leakage_detected": any(row.get("prompt_leakage") or row.get("response_leakage") or row.get("path_leakage") for row in rows),
        "target_locator_used": False,
        "gold_locator_used": False,
        "expected_supporting_text_used": False,
        "diagnostic_only": True,
    }


def build_input_paths() -> dict[str, Path]:
    return {
        "v3_21_summary_json": v321.OUTPUT_DIR / "summary.json",
        "v3_21_metrics_json": v321.OUTPUT_DIR / "metrics.json",
        "v3_21_per_query_jsonl": v321.OUTPUT_DIR / "per_query.jsonl",
        "v3_21_llm_io_packet_jsonl": v321.OUTPUT_DIR / "llm_io_packet.jsonl",
        "v3_21_guardrail_audit_json": v321.OUTPUT_DIR / "guardrail_audit.json",
    }


def require_input_artifacts(paths: Mapping[str, Path]) -> None:
    missing = [repo_relative(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required v3_21 input artifacts: " + ", ".join(missing))


def build_input_lineage(paths: Mapping[str, Path]) -> dict[str, Any]:
    return {
        key: {"exists": path.exists(), "path": repo_relative(path), "sha256": sha256_file(path) if path.exists() else ""}
        for key, path in paths.items()
    }


def build_summary(
    *,
    metrics: Mapping[str, Any],
    input_lineage: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
    readiness: Mapping[str, Any],
) -> dict[str, Any]:
    summary = dict(metrics)
    summary.update(
        {
            "schema_version": f"{RUN_ID}_summary_v1",
            "run_id": RUN_ID,
            "status": STATUS,
            "event_type": EVENT_TYPE,
            "run_class": "diagnostic_only_xlsx_display_value_and_range_rendering_nonprod",
            "generated_at": utc_now(),
            "review_packet_dir": repo_relative(OUTPUT_DIR),
            "artifact_paths": dict(artifact_paths),
            "input_lineage": dict(input_lineage),
            "tool_registry_version": "rag_tool_registry_l0_l8_v1",
            "runtime_layer_names": list(LAYER_NAMES),
            "local_llm_readiness": dict(readiness),
            "human_review_required": bool(metrics["human_review_required"]),
            "review_csv_created": bool(metrics["review_csv_created"]),
            "single_report_artifact_contract": True,
            "sidecar_primary_artifacts_suppressed": True,
            "review_csv_optional_only": True,
            "diagnostic_only": True,
            "official_metric": False,
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "agent_runtime_nonprod": True,
            "agent_runtime_product_ready": False,
            "live_db_index_cache_readiness": False,
        }
    )
    return summary


def build_verification_section() -> dict[str, Any]:
    return {
        "schema_version": f"{RUN_ID}_verification_v1",
        "run_id": RUN_ID,
        "commands_required_by_goal": [
            "python -X utf8 -m py_compile ai\\scripts\\rag_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod.py",
            "python -X utf8 ai\\scripts\\rag_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod.py --check",
            "targeted v3_22 formatting/report-contract tests",
            "targeted artifact/status/guardrail tests",
            "python -X utf8 -m pytest ai/tests --rag-current -q",
            "git diff --check",
            "git diff --cached --check",
            "protected-surface unstaged/cached diff checks",
            "git check-ignore -v for report.json, optional review_packet.csv if emitted, and status.jsonl",
        ],
        "results_recorded_in_final_response": True,
    }


def build_report(
    *,
    rows: Mapping[str, Sequence[Mapping[str, Any]]],
    metrics: Mapping[str, Any],
    prompt_manifest: Mapping[str, Any],
    guardrail: Mapping[str, Any],
    leakage: Mapping[str, Any],
    readiness: Mapping[str, Any],
    input_lineage: Mapping[str, Any],
    artifact_paths: Mapping[str, str],
) -> dict[str, Any]:
    summary = build_summary(metrics=metrics, input_lineage=input_lineage, artifact_paths=artifact_paths, readiness=readiness)
    audits = {
        "route_policy_audit": list(rows["route_policy_audit"]),
        "runtime_contract_audit": list(rows["runtime_contract_audit"]),
        "user_response_policy_audit": list(rows["user_response_policy_audit"]),
        "runtime_adapter_audit": list(rows["runtime_adapter_audit"]),
        "llm_io_observability": list(rows["llm_io_observability"]),
        "formatting_audit": list(rows["formatting_audit"]),
    }
    return {
        "schema_version": "rag_v3_22_single_report_v1",
        "run_id": RUN_ID,
        "generated_at": utc_now(),
        "diagnostic_only": True,
        "official_metric_input_rows": 0,
        "promotion_evidence": False,
        "human_review_required": bool(metrics["human_review_required"]),
        "review_csv_created": bool(metrics["review_csv_created"]),
        "summary": summary,
        "metrics": dict(metrics),
        "per_query": list(rows["per_query"]),
        "audits": audits,
        "route_policy_audit": audits["route_policy_audit"],
        "runtime_contract_audit": audits["runtime_contract_audit"],
        "user_response_policy_audit": audits["user_response_policy_audit"],
        "runtime_adapter_audit": audits["runtime_adapter_audit"],
        "llm_io_observability": audits["llm_io_observability"],
        "formatting_audit": audits["formatting_audit"],
        "prompt_manifest": dict(prompt_manifest),
        "guardrails": dict(guardrail),
        "guardrail_audit": dict(guardrail),
        "leakage": dict(leakage),
        "leakage_audit": list(rows["leakage_audit"]),
        "verification": build_verification_section(),
        "changed_files": [
            "ai/scripts/rag_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod.py",
            "ai/tests/test_rag_answer_citation_silver_manifest_v1.py",
            "ai/tests/test_rag_official_metric_artifact_source_of_truth_audit_v1.py",
            "ai/tests/test_rag_diagnostic_guardrail_git_diff.py",
            "ai/tests/test_rag_diagnostic_status_sync.py",
            "ai/tests/test_rag_current_focused_test_profile_v1.py",
            "docs/rag-ingestion-progress.md",
            "docs/rag-ingestion-measurements.md",
            "docs/rag-ingestion-triage.md",
            "ai/eval/reports/rag-ingestion/status.jsonl",
        ],
        "residual_risks": [
            "Diagnostic-only in-memory SourceAtom display metadata exercises the runtime contract but is not production routing.",
            "No official metric input rows are emitted; answer/citation quality and promotion remain blocked.",
            "Live DB/index/cache readiness is not claimed by v3_22.",
        ],
        "next_recommendation": (
            "If this diagnostic remains stable, wire the same display-value contract into persisted XLSX SourceAtom materialization "
            "behind a non-production gate before any product or promotion discussion."
        ),
    }


def build_artifacts(
    *,
    backend: str = DEFAULT_BACKEND,
    base_url: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 420,
    timeout_seconds: int = 90,
    llm_client: Callable[..., str] | None = None,
    include_user_review_required_case: bool = False,
    output_dir: Path | None = None,
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
    readiness = build_readiness(
        backend=backend,
        base_url=resolved_base_url,
        model=model,
        blockers=blockers,
        llm_client_provided=llm_client is not None,
    )
    rows = build_rows(
        backend=backend,
        base_url=resolved_base_url,
        model=model,
        readiness=readiness,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        llm_client=llm_client,
        include_user_review_required_case=include_user_review_required_case,
    )
    metrics = build_metrics(rows, readiness)
    target_dir = output_dir or OUTPUT_DIR
    artifact_paths = {"report_json": artifact_path_text(target_dir / "report.json")}
    if metrics["review_csv_created"]:
        artifact_paths["review_packet_csv"] = artifact_path_text(target_dir / "review_packet.csv")
    prompt_manifest = build_prompt_manifest(backend=backend, base_url=resolved_base_url, model=model)
    guardrail = build_guardrail_audit(metrics)
    leakage = build_leakage_summary(rows["per_query"])
    report = build_report(
        rows=rows,
        metrics=metrics,
        prompt_manifest=prompt_manifest,
        guardrail=guardrail,
        leakage=leakage,
        readiness=readiness,
        input_lineage=input_lineage,
        artifact_paths=artifact_paths,
    )
    return {
        "report": report,
        "metrics": metrics,
        "rows": rows,
        "prompt_manifest": prompt_manifest,
        "guardrail_audit": guardrail,
        "leakage": leakage,
        "local_llm_readiness": readiness,
        "review_rows": list(rows["review_rows"]),
    }


def remove_stale_sidecar_artifacts(target_dir: Path, *, keep_review_csv: bool) -> None:
    for artifact_name in FORBIDDEN_PRIMARY_SIDECAR_ARTIFACT_NAMES:
        stale_path = target_dir / artifact_name
        if stale_path.is_file():
            stale_path.unlink()
    review_path = target_dir / "review_packet.csv"
    if not keep_review_csv and review_path.is_file():
        review_path.unlink()


def write_artifacts(artifacts: Mapping[str, Any], *, output_dir: Path | None = None) -> dict[str, Any]:
    target_dir = output_dir or OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    report_path = target_dir / "report.json"
    report = dict(artifacts["report"])
    report["artifact_paths"] = {"report_json": artifact_path_text(report_path)}
    report["summary"] = dict(report["summary"])
    report["summary"]["artifact_paths"] = dict(report["artifact_paths"])
    review_rows = list(artifacts.get("review_rows") or [])
    remove_stale_sidecar_artifacts(target_dir, keep_review_csv=bool(review_rows))
    if review_rows:
        review_path = target_dir / "review_packet.csv"
        write_csv(
            review_path,
            review_rows,
            columns=[
                "review_id",
                "query_id",
                "diagnostic_case_id",
                "actual_input_query",
                "user_owned_review_reason",
                "xlsx_raw_value",
                "xlsx_display_value",
                "xlsx_format_confidence",
                "xlsx_format_drop_reason",
                "final_user_visible_answer",
            ],
        )
        report["artifact_paths"]["review_packet_csv"] = artifact_path_text(review_path)
        report["summary"]["artifact_paths"] = dict(report["artifact_paths"])
        report["review_csv_created"] = True
        report["human_review_required"] = True
        report["summary"]["review_csv_created"] = True
        report["summary"]["human_review_required"] = True
        report["metrics"]["review_csv_created"] = True
        report["metrics"]["human_review_required"] = True
    write_json(report_path, report)
    return report


def replace_marked_entry(path: Path, marker: str, entry: str) -> None:
    diagnostic_common.replace_marked_entry(path, marker, entry)


def update_docs(report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v321.v320.v319.refresh_last_updated(doc_path)
    report_path = report["artifact_paths"]["report_json"]
    progress_entry = (
        f"- v3_22 XLSX display-value and cell/range rendering (`{RUN_ID}`) is "
        "diagnostic_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod_ready. It keeps the "
        "v3_19-v3_21 fail-closed runtime policy, adds materialized SourceAtom-owned XLSX display metadata "
        "(raw_value, normalized_value, display_value, number_format, value_type, formula cached value, confidence, "
        "provenance, and drop reason), and renders SINGLE_CELL_VALUE, SMALL_RANGE_TABLE, BOUNDED_RANGE_SUMMARY, "
        "FORMAT_METADATA_UNAVAILABLE, UNSUPPORTED_RANGE_TOO_LARGE, and AMBIGUOUS_RANGE_CONTEXT_REQUIRED rows. "
        f"v3_22 uses the new single-report artifact policy: `{report_path}` is the only primary report artifact; "
        "review_packet.csv is omitted unless user-owned review is required. SourceAtom/EvidenceBundle remains canonical "
        "evidence truth; SearchView/vector payload remains candidate-only. This is not production routing, not product "
        "success, not promotion evidence, not official metric lift, and not live DB/index/cache readiness."
    )
    measurements_entry = f"""### v3_22 XLSX Display-Value And Cell/Range Rendering

- Run: `{RUN_ID}`
- Policy: diagnostic-only, non-production, SourceAtom/EvidenceBundle-owned XLSX display metadata; no raw XLSX query-time parsing, no sidecar primary artifacts, no review CSV unless user-owned review is required.
- Primary artifact: `{report_path}`

| Diagnostic count | Value |
| --- | ---: |
| report_row_count | {metrics["report_row_count"]} |
| xlsx_case_count | {metrics["xlsx_case_count"]} |
| xlsx_answer_allowed_count | {metrics["xlsx_answer_allowed_count"]} |
| llm_invoked_count | {metrics["llm_invoked_count"]} |
| raw_llm_response_present_count | {metrics["raw_llm_response_present_count"]} |
| parsed_final_answer_present_count | {metrics["parsed_final_answer_present_count"]} |
| single_cell_value_count | {metrics["single_cell_value_count"]} |
| small_range_table_count | {metrics["small_range_table_count"]} |
| bounded_range_summary_count | {metrics["bounded_range_summary_count"]} |
| display_value_used_count | {metrics["display_value_used_count"]} |
| raw_value_fallback_count | {metrics["raw_value_fallback_count"]} |
| format_metadata_unavailable_count | {metrics["format_metadata_unavailable_count"]} |
| formula_cached_value_used_count | {metrics["formula_cached_value_used_count"]} |
| blank_cell_answer_count | {metrics["blank_cell_answer_count"]} |
| unsupported_range_too_large_count | {metrics["unsupported_range_too_large_count"]} |
| ambiguous_range_context_required_count | {metrics["ambiguous_range_context_required_count"]} |
| runtime_contract_violation_count | {metrics["runtime_contract_violation_count"]} |
| vector_payload_evidence_truth_violation_count | {metrics["vector_payload_evidence_truth_violation_count"]} |
| raw_file_query_time_accessed | {str(metrics["raw_file_query_time_accessed"]).lower()} |
| official_metric_input_rows | 0 |
| review_csv_created | {str(metrics["review_csv_created"]).lower()} |

Counter source-of-truth: `report.json` embeds summary, metrics, per_query, route/user/runtime/adapter/LLM/formatting audits, guardrails, leakage, prompt_manifest, verification, changed_files, residual_risks, and next_recommendation. The run directory intentionally does not write summary.json, metrics.json, per_query.jsonl, audit JSONL files, llm_io_packet.jsonl, guardrail_audit.json, leakage_audit.jsonl, or prompt_manifest.json.
"""
    triage_entry = (
        "### v3_22 XLSX Display-Value And Cell/Range Rendering Triage\n\n"
        f"- Run: `{RUN_ID}`\n"
        f"- Primary artifact: `{report_path}`; single-report contract is active.\n"
        "- Formatting uses bounded materialized SourceAtom/runtime metadata only; missing or ambiguous display metadata falls back to raw_value with low confidence and FORMAT_METADATA_UNAVAILABLE.\n"
        "- Formula cells use cached values only; formula text is not exposed and formulas are not evaluated at query time.\n"
        "- Small ranges render as bounded tables, broad bounded ranges render compact summaries, unsupported large ranges and ambiguous/deictic context-missing rows fail closed without LLM invocation.\n"
        "- SourceAtom/EvidenceBundle remains evidence truth; SearchView/vector payload remains candidate-only; official_metric_input_rows stays 0.\n"
        "- This is not production routing, not product success, not promotion evidence, not official metric lift, and not live DB/index/cache readiness.\n"
    )
    replace_marked_entry(PROGRESS_DOC, f"{RUN_ID}:progress-entry", progress_entry)
    progress_text = PROGRESS_DOC.read_text(encoding="utf-8")
    progress_text = re.sub(
        r"Overall status: `[^`]+`;",
        "Overall status: `diagnostic_v3_22_xlsx_value_formatting_and_cell_range_answer_rendering_nonprod_ready`;",
        progress_text,
        count=1,
    )
    progress_text = re.sub(
        r"current diagnostic (?:LLM I/O observability|answer-quality|response-policy|live-runtime-like smoke) loop:\n`[^`]+`;",
        f"current diagnostic XLSX display/range rendering loop:\n`{RUN_ID}`;",
        progress_text,
        count=1,
    )
    PROGRESS_DOC.write_text(progress_text, encoding="utf-8")
    replace_marked_entry(MEASUREMENTS_DOC, f"{RUN_ID}:measurements-entry", measurements_entry)
    replace_marked_entry(TRIAGE_DOC, f"{RUN_ID}:triage-entry", triage_entry)
    for doc_path in (PROGRESS_DOC, MEASUREMENTS_DOC, TRIAGE_DOC):
        v321.v320.v319.refresh_last_updated(doc_path)


def artifact_sha256_from_report_paths(artifact_paths: Mapping[str, str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path_text in artifact_paths.items():
        path = Path(path_text)
        if not path.is_absolute():
            path = ROOT / path_text
        if path.exists():
            hashes[f"{key}_sha256"] = sha256_file(path)
    return hashes


def append_status_event(report: Mapping[str, Any]) -> None:
    event = {
        "schema_version": f"{RUN_ID}_status_event_v1",
        "run_id": RUN_ID,
        "event_type": EVENT_TYPE,
        "status": STATUS,
        "generated_at": utc_now(),
        "review_packet_dir": repo_relative(OUTPUT_DIR),
        "artifact_paths": dict(report["artifact_paths"]),
        "artifact_sha256": artifact_sha256_from_report_paths(report["artifact_paths"]),
        "tool_registry_version": "rag_tool_registry_l0_l8_v1",
        "single_report_artifact_contract": True,
        "human_review_required": bool(report["human_review_required"]),
        "review_csv_created": bool(report["review_csv_created"]),
        **dict(report["metrics"]),
    }
    event.pop("schema_version", None)
    event["schema_version"] = f"{RUN_ID}_status_event_v1"
    existing = read_jsonl(STATUS_JSONL) if STATUS_JSONL.exists() else []
    filtered = [row for row in existing if not (row.get("run_id") == RUN_ID and row.get("event_type") == EVENT_TYPE)]
    filtered.append(event)
    write_jsonl(STATUS_JSONL, filtered)


def run_write(*, backend: str, base_url: str, model: str, max_tokens: int, timeout_seconds: int) -> dict[str, Any]:
    artifacts = build_artifacts(
        backend=backend,
        base_url=base_url,
        model=model,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )
    report = write_artifacts(artifacts)
    update_docs(report)
    append_status_event(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--backend", default=DEFAULT_BACKEND, choices=["llamacpp", "openai-compatible", "ollama"])
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=420)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    args = parser.parse_args(argv)
    if args.check:
        artifacts = build_artifacts(
            backend=args.backend,
            base_url=args.base_url,
            model=args.model,
            max_tokens=args.max_tokens,
            timeout_seconds=args.timeout_seconds,
        )
        metrics = artifacts["metrics"]
        payload = {
            "run_id": RUN_ID,
            "status": artifacts["report"]["summary"]["status"],
            "report_row_count": metrics["report_row_count"],
            "xlsx_case_count": metrics["xlsx_case_count"],
            "llm_invoked_count": metrics["llm_invoked_count"],
            "raw_llm_response_present_count": metrics["raw_llm_response_present_count"],
            "runtime_contract_violation_count": metrics["runtime_contract_violation_count"],
            "official_metric_input_rows": metrics["official_metric_input_rows"],
            "human_review_required": artifacts["report"]["human_review_required"],
            "review_csv_created": artifacts["report"]["review_csv_created"],
            "local_llm_readiness_status": artifacts["local_llm_readiness"]["status"],
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    report = run_write(
        backend=args.backend,
        base_url=args.base_url,
        model=args.model,
        max_tokens=args.max_tokens,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps({"run_id": RUN_ID, "report": report["artifact_paths"]["report_json"], "status": report["summary"]["status"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
