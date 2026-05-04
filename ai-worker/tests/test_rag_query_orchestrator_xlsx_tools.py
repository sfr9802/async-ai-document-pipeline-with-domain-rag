from __future__ import annotations

from app.capabilities.rag_orchestrator.xlsx_tools import (
    EXPECTED_HIDDEN_POLICY_VERSION,
    FORMULA_POLICY_CACHED_VALUES_ONLY,
    REJECT_AMBIGUOUS_NUMERIC_VALUE,
    REJECT_UNSUPPORTED_FILTER,
    REJECT_UNSUPPORTED_OPERATION,
    WARNING_AMBIGUOUS_NUMERIC_VALUE,
    WARNING_FORMULA_CACHED_VALUE_USED,
    WARNING_HIDDEN_POLICY_MISMATCH,
    WARNING_TABLE_TRUNCATED,
    xlsx_aggregation_tool,
    xlsx_table_materialize_fixture_tool,
)


def _sales_table():
    return xlsx_table_materialize_fixture_tool(
        {"table_id": "sales-table"},
        {"max_rows": 10, "max_columns": 10, "max_cells": 100},
    )


def test_sum_calculation_is_deterministic():
    table = _sales_table()

    result = xlsx_aggregation_tool(
        table,
        operation="sum",
        metric_column="Revenue",
    )

    assert result.status == "ok"
    assert result.result == {"value": 700, "row_count": 4}
    assert result.deterministic is True


def test_avg_calculation_is_deterministic():
    result = xlsx_aggregation_tool(
        _sales_table(),
        operation="avg",
        metric_column="Revenue",
    )

    assert result.status == "ok"
    assert result.result["value"] == 175


def test_count_calculation_is_deterministic():
    result = xlsx_aggregation_tool(
        _sales_table(),
        operation="count",
        metric_column="Revenue",
    )

    assert result.status == "ok"
    assert result.result == {"value": 4, "row_count": 4}


def test_group_by_sum_calculation_is_deterministic():
    result = xlsx_aggregation_tool(
        _sales_table(),
        operation="sum",
        metric_column="Revenue",
        group_by=["Region"],
    )

    assert result.status == "ok"
    assert result.result == [
        {"group": {"Region": "KR"}, "value": 250, "row_count": 2},
        {"group": {"Region": "US"}, "value": 450, "row_count": 2},
    ]


def test_max_cells_limit_truncates_materialized_table():
    table = xlsx_table_materialize_fixture_tool(
        {"table_id": "sales-table"},
        {"max_rows": 10, "max_columns": 4, "max_cells": 4},
    )

    assert table.truncated is True
    assert len(table.rows) == 1
    assert WARNING_TABLE_TRUNCATED in table.warnings


def test_unsupported_operation_is_rejected():
    result = xlsx_aggregation_tool(
        _sales_table(),
        operation="median",
        metric_column="Revenue",
    )

    assert result.status == "rejected"
    assert result.reject_reason == REJECT_UNSUPPORTED_OPERATION
    assert result.deterministic is True


def test_unsupported_filter_is_rejected():
    result = xlsx_aggregation_tool(
        _sales_table(),
        operation="sum",
        metric_column="Revenue",
        filters=[{"column": "Region", "op": "eq", "value": "KR"}],
    )

    assert result.status == "rejected"
    assert result.reject_reason == REJECT_UNSUPPORTED_FILTER


def test_ambiguous_numeric_value_is_rejected_with_warning():
    table = xlsx_table_materialize_fixture_tool(
        {"table_id": "ambiguous-number-table"},
        {"max_rows": 10, "max_columns": 10, "max_cells": 100},
    )

    result = xlsx_aggregation_tool(
        table,
        operation="sum",
        metric_column="Revenue",
    )

    assert result.status == "rejected"
    assert result.reject_reason == REJECT_AMBIGUOUS_NUMERIC_VALUE
    assert WARNING_AMBIGUOUS_NUMERIC_VALUE in result.warnings


def test_hidden_policy_version_is_preserved_and_mismatch_warns():
    table = xlsx_table_materialize_fixture_tool(
        {"table_id": "legacy-hidden-policy-table"},
        {"max_rows": 10, "max_columns": 10, "max_cells": 100},
    )

    assert table.hidden_policy_version == "legacy-hidden-policy"
    assert WARNING_HIDDEN_POLICY_MISMATCH in table.warnings
    assert table.to_dict()["hidden_policy_version"] == "legacy-hidden-policy"


def test_expected_hidden_policy_and_formula_contract_are_preserved():
    table = _sales_table()

    assert table.hidden_policy_version == EXPECTED_HIDDEN_POLICY_VERSION
    assert table.formula_policy == FORMULA_POLICY_CACHED_VALUES_ONLY
    assert table.macros_executed is False


def test_formula_cached_values_are_used_without_formula_execution():
    table = xlsx_table_materialize_fixture_tool(
        {"table_id": "formula-sales-table"},
        {"max_rows": 10, "max_columns": 10, "max_cells": 100},
    )

    result = xlsx_aggregation_tool(
        table,
        operation="sum",
        metric_column="Revenue",
    )

    assert result.status == "ok"
    assert result.result == {"value": 750, "row_count": 2}
    assert WARNING_FORMULA_CACHED_VALUE_USED in result.warnings
    assert table.macros_executed is False
