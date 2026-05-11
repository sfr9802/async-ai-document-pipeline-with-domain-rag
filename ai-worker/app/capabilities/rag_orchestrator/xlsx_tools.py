"""Fixture-only XLSX materialization and deterministic aggregation helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from app.capabilities.rag_orchestrator.evidence import (
    SOURCE_FILE_TYPE_SPREADSHEET,
    Evidence,
)

EXPECTED_HIDDEN_POLICY_VERSION = "exclude-hidden-v1"
FORMULA_POLICY_CACHED_VALUES_ONLY = "cached_values_only"

WARNING_HIDDEN_POLICY_MISSING = "hidden_policy_version_missing"
WARNING_HIDDEN_POLICY_MISMATCH = "hidden_policy_version_mismatch"
WARNING_TABLE_TRUNCATED = "table_truncated"
WARNING_FORMULA_CACHED_VALUE_USED = "formula_cached_value_used"
WARNING_AMBIGUOUS_NUMERIC_VALUE = "ambiguous_numeric_value"

REJECT_UNSUPPORTED_OPERATION = "unsupported_operation"
REJECT_UNSUPPORTED_FILTER = "unsupported_filter"
REJECT_UNKNOWN_COLUMN = "unknown_column"
REJECT_AMBIGUOUS_NUMERIC_VALUE = "ambiguous_numeric_value"

SUPPORTED_OPERATIONS = {"sum", "avg", "min", "max", "count"}
_NUMERIC_RE = re.compile(r"^[+-]?(?:\d+|\d+\.\d+|\.\d+)$")
_CELL_REF_RE = re.compile(r"^\$?([A-Z]+)\$?(\d+)$", re.IGNORECASE)

VECTOR_WRAPPER_TODOS = (
    "Replace fixture lookup with a bounded table_metadata/materialized-table read API.",
    "Keep hidden row, column, and cell exclusion policy attached to every table.",
    "Continue using cached formula values only; never execute macros or formulas.",
    "Validate aggregation specs from any future LLM node before calculation.",
)

XLSX_CONTEXT_CONTRACT_VERSION = "xlsx-business-structured-context-v1"
XLSX_CONTEXT_DIAGNOSTIC_WARNING = "xlsx_context_diagnostic_only_missing_structure"
XLSX_CONTEXT_ASSEMBLY_POLICY = (
    "same_row",
    "header_row",
    "target_column_header",
    "nearby_rows",
    "merged_parent_cells",
    "sheet_name",
    "table_title_candidate",
)


@dataclass(frozen=True)
class XlsxEvidenceContext:
    """Structure-aware answer context assembled from one XLSX candidate."""

    file: str
    sheet: str | None
    table_id: str | None
    table_range: str | None
    matched_cells: tuple[str, ...]
    header_rows: tuple[Any, ...]
    target_rows: tuple[int, ...]
    target_columns: tuple[str, ...]
    row_values: Mapping[str, Any]
    column_headers: tuple[str, ...]
    nearby_rows: tuple[Mapping[str, Any], ...]
    merged_cell_context: tuple[Any, ...]
    table_title_candidate: str | None
    score: float | None
    diagnostic_only: bool
    missing_context_fields: tuple[str, ...]
    context_assembly_policy: tuple[str, ...] = XLSX_CONTEXT_ASSEMBLY_POLICY
    contract_version: str = XLSX_CONTEXT_CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "file": self.file,
            "sheet": self.sheet,
            "table_id": self.table_id,
            "table_range": self.table_range,
            "matched_cells": list(self.matched_cells),
            "header_rows": list(self.header_rows),
            "target_rows": list(self.target_rows),
            "target_columns": list(self.target_columns),
            "row_values": dict(self.row_values),
            "column_headers": list(self.column_headers),
            "nearby_rows": [dict(row) for row in self.nearby_rows],
            "merged_cell_context": list(self.merged_cell_context),
            "table_title_candidate": self.table_title_candidate,
            "score": self.score,
            "diagnostic_only": self.diagnostic_only,
            "missing_context_fields": list(self.missing_context_fields),
            "context_assembly_policy": list(self.context_assembly_policy),
        }


def assemble_xlsx_evidence_context(evidence: Evidence) -> XlsxEvidenceContext:
    """Assemble structure-aware context from a retrieved XLSX candidate.

    This function deliberately accepts only the retrieved Evidence payload. It
    does not reopen source workbooks or probe hidden workbook state.
    """

    if evidence.source_file_type != SOURCE_FILE_TYPE_SPREADSHEET:
        raise ValueError("assemble_xlsx_evidence_context requires SPREADSHEET evidence")

    location = dict(evidence.location_json) if isinstance(evidence.location_json, Mapping) else {}
    metadata = _evidence_metadata(evidence)
    table_range = _str_or_none(
        _first_present(
            location,
            metadata,
            "cellRange",
            "cell_range",
            "range",
            "usedRange",
            "tableRange",
            "table_range",
        )
    )
    row_start = _int_or_none(_first_present(location, metadata, "rowStart", "row_start"))
    row_end = _int_or_none(_first_present(location, metadata, "rowEnd", "row_end"))
    column_start = _first_present(location, metadata, "columnStart", "column_start")
    column_end = _first_present(location, metadata, "columnEnd", "column_end")
    parsed_rows, parsed_columns = _rows_columns_from_range(table_range)
    target_rows = _int_range(row_start, row_end) or parsed_rows
    target_columns = _column_range(column_start, column_end) or parsed_columns

    row_values = _mapping_from_value(
        _first_present(metadata, location, "rowValues", "row_values")
    )
    column_headers = _tuple_strings(
        _first_present(metadata, location, "columnHeaders", "column_headers", "headers")
    )
    header_rows = _tuple_any(
        _first_present(metadata, location, "headerRows", "header_rows", "headers")
    )
    nearby_rows = _tuple_mappings(
        _first_present(metadata, location, "nearbyRows", "nearby_rows")
    )
    merged_cell_context = _tuple_any(
        _first_present(
            metadata,
            location,
            "mergedCellContext",
            "merged_cell_context",
            "mergedParentCells",
            "mergedCells",
            "merged_cells",
        )
    )
    matched_cells = _tuple_strings(
        _first_present(metadata, location, "matchedCells", "matched_cells", "cell")
    )
    if not matched_cells and table_range:
        matched_cells = (table_range,)

    missing = []
    if not row_values:
        missing.append("row_values")
    if not column_headers:
        missing.append("column_headers")
    if not header_rows:
        missing.append("header_rows")
    if not target_rows:
        missing.append("target_rows")
    if not target_columns:
        missing.append("target_columns")
    diagnostic_only = bool(missing)

    return XlsxEvidenceContext(
        file=evidence.source_file_name or evidence.source_file_id,
        sheet=_str_or_none(
            _first_present(location, metadata, "sheetName", "sheet_name")
        ),
        table_id=_str_or_none(
            _first_present(location, metadata, "tableId", "table_id", "tableName")
        ),
        table_range=table_range,
        matched_cells=matched_cells,
        header_rows=header_rows,
        target_rows=target_rows,
        target_columns=target_columns,
        row_values=row_values,
        column_headers=column_headers,
        nearby_rows=nearby_rows,
        merged_cell_context=merged_cell_context,
        table_title_candidate=_str_or_none(
            _first_present(
                metadata,
                location,
                "tableTitle",
                "table_title",
                "tableName",
                "title",
            )
        ),
        score=_score(evidence),
        diagnostic_only=diagnostic_only,
        missing_context_fields=tuple(missing),
    )


def evidence_with_xlsx_context(evidence: Evidence) -> Evidence:
    """Attach XLSX context assembly output to an Evidence item."""

    context = assemble_xlsx_evidence_context(evidence)
    warnings = tuple(evidence.verification_warnings)
    if context.diagnostic_only and XLSX_CONTEXT_DIAGNOSTIC_WARNING not in warnings:
        warnings = (*warnings, XLSX_CONTEXT_DIAGNOSTIC_WARNING)
    extra = dict(evidence.extra)
    extra["track_evidence_contract"] = XLSX_CONTEXT_CONTRACT_VERSION
    extra["xlsx_evidence_context"] = context.to_dict()
    return replace(
        evidence,
        diagnostic_only=evidence.diagnostic_only or context.diagnostic_only,
        verification_warnings=warnings,
        extra=extra,
    )


@dataclass(frozen=True)
class TableLimits:
    max_rows: int = 200
    max_columns: int = 50
    max_cells: int = 5000

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> "TableLimits":
        if not values:
            return cls()
        limits = cls(
            max_rows=int(values.get("max_rows", values.get("maxRows", cls.max_rows))),
            max_columns=int(
                values.get("max_columns", values.get("maxColumns", cls.max_columns))
            ),
            max_cells=int(values.get("max_cells", values.get("maxCells", cls.max_cells))),
        )
        if limits.max_rows < 1 or limits.max_columns < 1 or limits.max_cells < 1:
            raise ValueError("XLSX materialization limits must be positive")
        return limits


@dataclass(frozen=True)
class MaterializedTable:
    table_ref: Mapping[str, Any]
    headers: tuple[str, ...]
    rows: tuple[Mapping[str, Any], ...]
    truncated: bool
    hidden_policy_version: str | None
    warnings: tuple[str, ...]
    formula_policy: str = FORMULA_POLICY_CACHED_VALUES_ONLY
    macros_executed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "table_ref": dict(self.table_ref),
            "headers": list(self.headers),
            "rows": [dict(row) for row in self.rows],
            "truncated": self.truncated,
            "hidden_policy_version": self.hidden_policy_version,
            "warnings": list(self.warnings),
            "formula_policy": self.formula_policy,
            "macros_executed": self.macros_executed,
        }


@dataclass(frozen=True)
class XlsxAggregationResult:
    status: str
    operation: str
    metric_column: str
    group_by: tuple[str, ...]
    result: Any
    deterministic: bool
    used_table_ref: Mapping[str, Any]
    warnings: tuple[str, ...]
    reject_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "operation": self.operation,
            "metric_column": self.metric_column,
            "group_by": list(self.group_by),
            "result": self.result,
            "deterministic": self.deterministic,
            "used_table_ref": dict(self.used_table_ref),
            "warnings": list(self.warnings),
            "reject_reason": self.reject_reason,
        }


def xlsx_table_materialize_fixture_tool(
    table_ref: Mapping[str, Any],
    limits: Mapping[str, Any] | TableLimits | None = None,
) -> MaterializedTable:
    """Materialize a bounded table from local fixtures only."""

    resolved_limits = (
        limits if isinstance(limits, TableLimits) else TableLimits.from_mapping(limits)
    )
    fixture = _fixture_for(table_ref)
    hidden_policy_version = fixture["hidden_policy_version"]
    headers = tuple(fixture["headers"])
    rows = tuple(dict(row) for row in fixture["rows"])
    warnings = list(_hidden_policy_warnings(hidden_policy_version))

    limited_headers = headers[: resolved_limits.max_columns]
    truncated = len(limited_headers) < len(headers) or len(rows) > resolved_limits.max_rows
    limited_rows = rows[: resolved_limits.max_rows]

    if limited_headers:
        max_rows_by_cells = resolved_limits.max_cells // len(limited_headers)
        if max_rows_by_cells < len(limited_rows):
            truncated = True
            limited_rows = limited_rows[:max_rows_by_cells]

    if truncated:
        warnings.append(WARNING_TABLE_TRUNCATED)

    projected_rows = tuple(
        {header: row.get(header) for header in limited_headers} for row in limited_rows
    )
    materialized_ref = dict(fixture["table_ref"])
    materialized_ref.update(dict(table_ref))

    return MaterializedTable(
        table_ref=materialized_ref,
        headers=limited_headers,
        rows=projected_rows,
        truncated=truncated,
        hidden_policy_version=hidden_policy_version,
        warnings=_dedupe(warnings),
    )


def xlsx_aggregation_tool(
    table: MaterializedTable,
    *,
    operation: str,
    metric_column: str,
    group_by: Sequence[str] | None = None,
    filters: Sequence[Mapping[str, Any]] | None = None,
) -> XlsxAggregationResult:
    """Run deterministic aggregation over a materialized fixture table."""

    normalized_operation = operation.strip().lower()
    group_columns = tuple(group_by or ())
    warnings = list(table.warnings)

    if normalized_operation not in SUPPORTED_OPERATIONS:
        return _rejected_result(
            table,
            operation=normalized_operation,
            metric_column=metric_column,
            group_by=group_columns,
            warnings=warnings,
            reason=REJECT_UNSUPPORTED_OPERATION,
        )

    if filters:
        return _rejected_result(
            table,
            operation=normalized_operation,
            metric_column=metric_column,
            group_by=group_columns,
            warnings=warnings,
            reason=REJECT_UNSUPPORTED_FILTER,
        )

    missing_columns = [
        column for column in (metric_column, *group_columns) if column not in table.headers
    ]
    if missing_columns:
        return _rejected_result(
            table,
            operation=normalized_operation,
            metric_column=metric_column,
            group_by=group_columns,
            warnings=warnings,
            reason=REJECT_UNKNOWN_COLUMN,
        )

    rows = tuple(table.rows)
    if group_columns:
        result, group_warnings, reject_reason = _grouped_aggregate(
            rows,
            operation=normalized_operation,
            metric_column=metric_column,
            group_by=group_columns,
        )
    else:
        result, group_warnings, reject_reason = _scalar_aggregate(
            rows,
            operation=normalized_operation,
            metric_column=metric_column,
        )

    warnings.extend(group_warnings)
    if reject_reason:
        return _rejected_result(
            table,
            operation=normalized_operation,
            metric_column=metric_column,
            group_by=group_columns,
            warnings=warnings,
            reason=reject_reason,
        )

    return XlsxAggregationResult(
        status="ok",
        operation=normalized_operation,
        metric_column=metric_column,
        group_by=group_columns,
        result=result,
        deterministic=True,
        used_table_ref=table.table_ref,
        warnings=_dedupe(warnings),
    )


def _scalar_aggregate(
    rows: Sequence[Mapping[str, Any]],
    *,
    operation: str,
    metric_column: str,
) -> tuple[dict[str, Any], tuple[str, ...], str | None]:
    values, warnings, reject_reason = _values_for(rows, metric_column, operation)
    if reject_reason:
        return {}, warnings, reject_reason
    value = _aggregate_values(values, operation)
    return {"value": value, "row_count": len(rows)}, warnings, None


def _grouped_aggregate(
    rows: Sequence[Mapping[str, Any]],
    *,
    operation: str,
    metric_column: str,
    group_by: tuple[str, ...],
) -> tuple[list[dict[str, Any]], tuple[str, ...], str | None]:
    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for row in rows:
        key = tuple(row.get(column) for column in group_by)
        grouped.setdefault(key, []).append(row)

    warnings: list[str] = []
    output: list[dict[str, Any]] = []
    for key in sorted(grouped, key=lambda item: tuple(str(part) for part in item)):
        values, current_warnings, reject_reason = _values_for(
            grouped[key],
            metric_column,
            operation,
        )
        warnings.extend(current_warnings)
        if reject_reason:
            return [], _dedupe(warnings), reject_reason
        output.append(
            {
                "group": dict(zip(group_by, key, strict=True)),
                "value": _aggregate_values(values, operation),
                "row_count": len(grouped[key]),
            }
        )
    return output, _dedupe(warnings), None


def _values_for(
    rows: Sequence[Mapping[str, Any]],
    metric_column: str,
    operation: str,
) -> tuple[tuple[float, ...], tuple[str, ...], str | None]:
    warnings: list[str] = []
    if operation == "count":
        return (
            tuple(1.0 for row in rows if row.get(metric_column) not in (None, "")),
            (),
            None,
        )

    values: list[float] = []
    for row in rows:
        value, value_warnings, reject_reason = _to_number(row.get(metric_column))
        warnings.extend(value_warnings)
        if reject_reason:
            return (), _dedupe(warnings), reject_reason
        values.append(value)
    return tuple(values), _dedupe(warnings), None


def _aggregate_values(values: Sequence[float], operation: str) -> float | int:
    if operation == "count":
        return len(values)
    if not values:
        return 0
    if operation == "sum":
        return sum(values)
    if operation == "avg":
        return sum(values) / len(values)
    if operation == "min":
        return min(values)
    if operation == "max":
        return max(values)
    raise ValueError(f"unsupported operation: {operation}")


def _to_number(value: Any) -> tuple[float, tuple[str, ...], str | None]:
    warnings: list[str] = []
    raw_value = value
    if isinstance(value, Mapping):
        if "cached_value" in value:
            raw_value = value["cached_value"]
        elif "cachedValue" in value:
            raw_value = value["cachedValue"]
        else:
            return 0.0, (), REJECT_AMBIGUOUS_NUMERIC_VALUE
        warnings.append(WARNING_FORMULA_CACHED_VALUE_USED)

    if isinstance(raw_value, bool):
        return 0.0, tuple(warnings), REJECT_AMBIGUOUS_NUMERIC_VALUE
    if isinstance(raw_value, (int, float)):
        return float(raw_value), tuple(warnings), None
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if _NUMERIC_RE.fullmatch(stripped):
            return float(stripped), tuple(warnings), None
        warnings.append(WARNING_AMBIGUOUS_NUMERIC_VALUE)
        return 0.0, tuple(warnings), REJECT_AMBIGUOUS_NUMERIC_VALUE
    return 0.0, tuple(warnings), REJECT_AMBIGUOUS_NUMERIC_VALUE


def _rejected_result(
    table: MaterializedTable,
    *,
    operation: str,
    metric_column: str,
    group_by: tuple[str, ...],
    warnings: Sequence[str],
    reason: str,
) -> XlsxAggregationResult:
    return XlsxAggregationResult(
        status="rejected",
        operation=operation,
        metric_column=metric_column,
        group_by=group_by,
        result=[],
        deterministic=True,
        used_table_ref=table.table_ref,
        warnings=_dedupe(warnings),
        reject_reason=reason,
    )


def _fixture_for(table_ref: Mapping[str, Any]) -> dict[str, Any]:
    fixture_id = (
        table_ref.get("fixture")
        or table_ref.get("table_id")
        or table_ref.get("tableId")
        or "sales-table"
    )
    if fixture_id not in _FIXTURES:
        raise ValueError(f"unknown XLSX fixture table: {fixture_id}")
    return _FIXTURES[fixture_id]


def _hidden_policy_warnings(hidden_policy_version: str | None) -> tuple[str, ...]:
    if not hidden_policy_version:
        return (WARNING_HIDDEN_POLICY_MISSING,)
    if hidden_policy_version != EXPECTED_HIDDEN_POLICY_VERSION:
        return (WARNING_HIDDEN_POLICY_MISMATCH,)
    return ()


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return tuple(deduped)


def _evidence_metadata(evidence: Evidence) -> dict[str, Any]:
    metadata = dict(evidence.extra.get("retriever_metadata") or {})
    metadata.update(
        {
            key: value
            for key, value in evidence.extra.items()
            if key not in {"retriever_metadata", "xlsx_evidence_context"}
        }
    )
    return metadata


def _first_present(
    primary: Mapping[str, Any],
    secondary: Mapping[str, Any],
    *keys: str,
) -> Any:
    for source in (primary, secondary):
        for key in keys:
            value = source.get(key)
            if value not in (None, ""):
                return value
    return None


def _mapping_from_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _tuple_strings(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, Mapping):
        return tuple(str(key).strip() for key in value.keys() if str(key).strip())
    if isinstance(value, Iterable):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value).strip(),) if str(value).strip() else ()


def _tuple_any(value: Any) -> tuple[Any, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, Mapping):
        return (dict(value),)
    if isinstance(value, Iterable):
        return tuple(value)
    return (value,)


def _tuple_mappings(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not value:
        return ()
    if isinstance(value, Mapping):
        return (dict(value),)
    if isinstance(value, Iterable) and not isinstance(value, str):
        return tuple(dict(item) for item in value if isinstance(item, Mapping))
    return ()


def _int_range(start: int | None, end: int | None) -> tuple[int, ...]:
    if start is None:
        return ()
    stop = start if end is None else end
    low = min(start, stop)
    high = max(start, stop)
    return tuple(range(low, high + 1))


def _column_range(start: Any, end: Any) -> tuple[str, ...]:
    start_text = _column_label(start)
    if not start_text:
        return ()
    end_text = _column_label(end) or start_text
    start_idx = _column_index(start_text)
    end_idx = _column_index(end_text)
    if start_idx is None or end_idx is None:
        return (start_text,) if start_text == end_text else (start_text, end_text)
    low = min(start_idx, end_idx)
    high = max(start_idx, end_idx)
    return tuple(_index_to_column(idx) for idx in range(low, high + 1))


def _rows_columns_from_range(cell_range: str | None) -> tuple[tuple[int, ...], tuple[str, ...]]:
    if not cell_range:
        return (), ()
    parts = str(cell_range).replace("$", "").split(":", 1)
    start = _parse_cell_ref(parts[0])
    end = _parse_cell_ref(parts[1] if len(parts) == 2 else parts[0])
    if start is None or end is None:
        return (), ()
    row_start, col_start = start
    row_end, col_end = end
    return _int_range(row_start, row_end), _column_range(col_start, col_end)


def _parse_cell_ref(value: str) -> tuple[int, str] | None:
    match = _CELL_REF_RE.match(str(value or "").strip())
    if not match:
        return None
    return int(match.group(2)), match.group(1).upper()


def _column_label(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip().upper()
    if text.isdigit():
        return _index_to_column(int(text))
    return "".join(ch for ch in text if ch.isalpha()) or None


def _column_index(label: str) -> int | None:
    if not label:
        return None
    value = 0
    for char in label.upper():
        if not ("A" <= char <= "Z"):
            return None
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value


def _index_to_column(index: int) -> str:
    value = max(1, int(index))
    chars: list[str] = []
    while value:
        value, rem = divmod(value - 1, 26)
        chars.append(chr(ord("A") + rem))
    return "".join(reversed(chars))


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _score(evidence: Evidence) -> float | None:
    for key in ("final", "rerank", "dense"):
        value = evidence.scores.get(key) if evidence.scores else None
        if isinstance(value, (int, float)):
            return float(value)
    return None


_FIXTURES: dict[str, dict[str, Any]] = {
    "sales-table": {
        "table_ref": {
            "source_file_id": "source-sales",
            "sheet_name": "Sales",
            "cell_range": "A1:D5",
            "table_id": "sales-table",
        },
        "headers": ("Region", "Quarter", "Revenue", "Units"),
        "rows": (
            {"Region": "KR", "Quarter": "Q1", "Revenue": 100, "Units": 10},
            {"Region": "KR", "Quarter": "Q2", "Revenue": 150, "Units": 12},
            {"Region": "US", "Quarter": "Q1", "Revenue": 200, "Units": 20},
            {"Region": "US", "Quarter": "Q2", "Revenue": 250, "Units": 30},
        ),
        "hidden_policy_version": EXPECTED_HIDDEN_POLICY_VERSION,
    },
    "formula-sales-table": {
        "table_ref": {
            "source_file_id": "source-formula-sales",
            "sheet_name": "FormulaSales",
            "cell_range": "A1:B3",
            "table_id": "formula-sales-table",
        },
        "headers": ("Region", "Revenue"),
        "rows": (
            {
                "Region": "KR",
                "Revenue": {"formula": "=SUM(B4:B5)", "cached_value": 300},
            },
            {
                "Region": "US",
                "Revenue": {"formula": "=SUM(B6:B7)", "cached_value": 450},
            },
        ),
        "hidden_policy_version": EXPECTED_HIDDEN_POLICY_VERSION,
    },
    "ambiguous-number-table": {
        "table_ref": {
            "source_file_id": "source-ambiguous",
            "sheet_name": "Ambiguous",
            "cell_range": "A1:B2",
            "table_id": "ambiguous-number-table",
        },
        "headers": ("Region", "Revenue"),
        "rows": ({"Region": "KR", "Revenue": "1,234"},),
        "hidden_policy_version": EXPECTED_HIDDEN_POLICY_VERSION,
    },
    "legacy-hidden-policy-table": {
        "table_ref": {
            "source_file_id": "source-legacy-hidden",
            "sheet_name": "LegacyHidden",
            "cell_range": "A1:B2",
            "table_id": "legacy-hidden-policy-table",
        },
        "headers": ("Region", "Revenue"),
        "rows": ({"Region": "KR", "Revenue": 100},),
        "hidden_policy_version": "legacy-hidden-policy",
    },
}
