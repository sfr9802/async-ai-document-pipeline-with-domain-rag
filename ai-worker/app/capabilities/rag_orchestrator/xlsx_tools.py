"""Fixture-only XLSX materialization and deterministic aggregation helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

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

VECTOR_WRAPPER_TODOS = (
    "Replace fixture lookup with a bounded table_metadata/materialized-table read API.",
    "Keep hidden row, column, and cell exclusion policy attached to every table.",
    "Continue using cached formula values only; never execute macros or formulas.",
    "Validate aggregation specs from any future LLM node before calculation.",
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
