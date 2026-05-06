from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-worker" / "eval" / "harness" / "rag_ingestion_retrieval_eval.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_ingestion_retrieval_eval", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


eval_module = load_module()


def test_gold_query_csv_has_required_schema_and_live_bound_rows():
    rows = eval_module.load_gold_csv(
        ROOT / "ai-worker" / "eval" / "eval_queries" / "gold_queries_xlsx_v3_positive_reviewed.csv"
    )

    result = eval_module.validate_gold_rows(rows, require_live_bound=True)

    assert result.ok, result.errors
    assert result.row_count == 35
    assert result.bucket_counts["xlsx_lookup"] >= 5


def test_pdf_denominator_csv_has_required_schema_and_live_bound_rows():
    rows = eval_module.load_gold_csv(ROOT / "ai-worker" / "eval" / "eval_queries" / "gold_queries_pdf_v0.csv")

    result = eval_module.validate_gold_rows(rows, require_live_bound=True)

    assert result.ok, result.errors
    assert result.row_count == 22
    assert result.bucket_counts["pdf_page_lookup"] >= 1


def test_gold_query_validator_rejects_missing_required_columns():
    rows = [{"query_id": "q1", "bucket": "xlsx_lookup"}]

    result = eval_module.validate_gold_rows(rows)

    assert not result.ok
    assert any("missing required columns" in error for error in result.errors)


def test_gold_query_validator_rejects_invalid_policy_values():
    row = _valid_xlsx_row()
    row["hidden_policy"] = "show_hidden"
    row["requires_formula_value"] = "yes"

    result = eval_module.validate_gold_rows([row])

    assert not result.ok
    assert any("unsupported hidden_policy" in error for error in result.errors)
    assert any("requires_formula_value must be true or false" in error for error in result.errors)


def test_range_match_policies_support_contains_and_overlap():
    assert eval_module._range_matches("B2:C3", "B2:C3", "exact_match")
    assert eval_module._range_matches("B2:C3", "A1:D10", "contains_expected")
    assert eval_module._range_matches("B2:C3", "C3:D4", "overlaps_expected")
    assert not eval_module._range_matches("B2:C3", "D4:E5", "overlaps_expected")
    assert not eval_module._range_matches("B2:C3", "A1:D10", "exact_match")


def test_gold_query_validator_requires_xlsx_sheet_and_range_for_positive_rows():
    row = _valid_xlsx_row()
    row["expected_sheet_name"] = ""
    row["expected_cell_range"] = ""

    result = eval_module.validate_gold_rows([row])

    assert not result.ok
    assert result.row_errors["q-validator"] == [
        "expected_sheet_name is required for XLSX range policy",
        "expected_cell_range is required for XLSX range policy",
    ]


def test_gold_query_validator_allows_negative_hidden_row_without_location_binding():
    row = _valid_xlsx_row()
    row["hidden_policy"] = "negative"
    row["expected_file_name"] = ""
    row["expected_location_type"] = ""
    row["expected_sheet_name"] = ""
    row["expected_cell_range"] = ""

    result = eval_module.validate_gold_rows([row])

    assert result.ok, result.errors


def test_gold_query_validator_requires_pdf_page_binding():
    row = _valid_xlsx_row() | {
        "bucket": "pdf_page_lookup",
        "expected_file_name": "contract.pdf",
        "expected_location_type": "pdf",
        "expected_sheet_name": "",
        "expected_cell_range": "",
        "range_match_policy": "none",
    }

    result = eval_module.validate_gold_rows([row])

    assert not result.ok
    assert result.row_errors["q-validator"] == ["PDF rows require expected page fields"]


def _valid_xlsx_row() -> dict[str, str]:
    return {
        column: ""
        for column in eval_module.REQUIRED_COLUMNS
    } | {
        "query_id": "q-validator",
        "bucket": "xlsx_lookup",
        "query": "1호선",
        "expected_file_name": "sales.xlsx",
        "expected_chunk_type": "row_group",
        "expected_location_type": "xlsx",
        "expected_sheet_name": "철도",
        "expected_cell_range": "B2:C3",
        "range_match_policy": "contains_expected",
        "hidden_policy": "exclude_hidden",
        "requires_formula_value": "false",
        "requires_formatted_value": "true",
        "requires_aggregation": "false",
        "label_status": "bound",
    }
