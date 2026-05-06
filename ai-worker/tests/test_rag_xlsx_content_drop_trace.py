from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from openpyxl import Workbook


ROOT = Path(__file__).resolve().parents[2]
AI_WORKER_ROOT = ROOT / "ai-worker"
if str(AI_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_WORKER_ROOT))


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


trace = load_module(
    AI_WORKER_ROOT / "scripts" / "rag_xlsx_content_drop_trace.py",
    "rag_xlsx_content_drop_trace_for_tests",
)
serializer = load_module(
    AI_WORKER_ROOT / "eval" / "harness" / "pdf_xlsx_answer_evidence_serializer.py",
    "pdf_xlsx_answer_evidence_serializer_for_trace_tests",
)
compiler = load_module(
    AI_WORKER_ROOT / "eval" / "harness" / "pdf_xlsx_deterministic_answer_compiler.py",
    "pdf_xlsx_deterministic_answer_compiler_for_trace_tests",
)


def test_source_workbook_probe_is_diagnostic_only_not_answer_evidence(tmp_path: Path):
    workbook = _xlsx(tmp_path / "source.xlsx", "TRACE_ONLY_VALUE_DO_NOT_ANSWER")
    row = _row(source_path=workbook, context_values=False)

    trace_row = _trace_one(row, dataset_index={"source.xlsx": [workbook]})
    evidence_row = serializer.serialize_input_rows([row], run_id="repair")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="repair")[0]
    payload = json.dumps([trace_row, evidence_row, compiled_row], ensure_ascii=False)

    assert trace_row["source_workbook_stage"]["has_values"] is True
    assert trace_row["answer_generation_input_stage"]["has_values"] is False
    assert trace_row["answer_input_drops_content"] is True
    assert trace_row["denominator_impact"] == "none"
    assert evidence_row["answer_allowed"] is False
    assert compiled_row["compiled_answer"]["answer"] == ""
    assert "TRACE_ONLY_VALUE_DO_NOT_ANSWER" not in payload


def test_policy_pending_row_skips_source_probe_and_answer_evidence(tmp_path: Path):
    workbook = _xlsx(tmp_path / "policy.xlsx", "SHOULD_NOT_BE_PROBED")
    row = _row(
        source_path=workbook,
        context_values=True,
        policy={"diagnostic_only": True, "hidden_policy_blocked": True},
    )

    trace_row = _trace_one(row, dataset_index={"policy.xlsx": [workbook]})
    evidence_row = serializer.serialize_input_rows([row], run_id="repair")[0]
    payload = json.dumps([trace_row, evidence_row], ensure_ascii=False)

    assert trace_row["source_workbook_stage"]["status"] == "SKIPPED_POLICY_PENDING"
    assert trace_row["source_workbook_stage"]["opened"] is False
    assert "workbook_path" not in trace_row["source_workbook_stage"]
    assert trace_row["policy_pending"] is True
    assert "XLSX_POLICY_PENDING" in trace_row["diagnostic_reason_codes"]
    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] == "XLSX_POLICY_PENDING"
    assert "SHOULD_NOT_BE_PROBED" not in payload


def test_source_workbook_failure_classes_are_separate(tmp_path: Path):
    valid = _xlsx(tmp_path / "valid.xlsx", "VISIBLE")
    bad_zip = tmp_path / "bad.xlsx"
    bad_zip.write_text("not a zip file", encoding="utf-8")
    missing = tmp_path / "missing.xlsx"

    missing_row = _row(file_name="missing.xlsx", source_path=missing, context_values=False)
    bad_zip_row = _row(file_name="bad.xlsx", source_path=bad_zip, context_values=False)
    readonly_row = _row(
        file_name="valid.xlsx",
        source_path=valid,
        context_values=False,
        context_errors=["xlsx extraction failed: AttributeError: 'ReadOnlyWorksheet' object has no attribute 'row_dimensions'"],
    )

    rows = trace.build_trace_rows(
        [missing_row, bad_zip_row, readonly_row],
        run_id="test",
        dataset_index={},
        retrieval_maps={"query_results": {}, "classified_rows": {}},
        parser_artifacts_by_docv={},
        index_units_by_docv={},
    )

    assert rows[0]["source_workbook_stage"]["diagnostic_reason_code"] == "XLSX_SOURCE_WORKBOOK_MISSING"
    assert rows[1]["source_workbook_stage"]["diagnostic_reason_code"] == "XLSX_SOURCE_BAD_ZIP"
    assert "XLSX_SOURCE_READONLY_EXTRACTION_ERROR" in rows[2]["diagnostic_reason_codes"]
    assert rows[2]["source_workbook_stage"]["opened"] is True
    assert rows[2]["source_workbook_stage"]["has_values"] is True


def test_content_present_upstream_but_dropped_is_classified_and_denominator_stays_zero(tmp_path: Path):
    row = _row(file_name="source.xlsx", source_path=None, context_values=False)
    parser_artifact = {
        "artifact_json": {
            "workbook": {
                "sheets": [
                    {
                        "name": "Sheet1",
                        "cells": [
                            {"row": 1, "column": 1, "cell": "A1", "value": "Header"},
                            {"row": 2, "column": 2, "cell": "B2", "value": "123"},
                        ],
                        "chunks": [{"cellRange": "A1:B2", "text": "Header: Item | Value: 123"}],
                    }
                ]
            }
        }
    }
    index_unit = {
        "location_json": {"sheet_name": "Sheet1", "cell_range": "A1:B2"},
        "text_content": "Item: Alpha | Value: 123",
        "embedding_text": "Source: source.xlsx\nContent:\nItem: Alpha | Value: 123",
        "display_text": "Item: Alpha | Value: 123",
        "bm25_text": "Alpha 123",
        "chunk_type": "row_group",
    }

    rows = trace.build_trace_rows(
        [row],
        run_id="test",
        dataset_index={},
        retrieval_maps={"query_results": {}, "classified_rows": {}},
        parser_artifacts_by_docv={"docv_test": [parser_artifact]},
        index_units_by_docv={"docv_test": [index_unit]},
    )
    report = trace.build_report(
        run_id="test",
        generated_at="2026-05-06T00:00:00+00:00",
        artifact_dir=tmp_path / "artifact",
        trace_jsonl=tmp_path / "artifact" / "xlsx_content_drop_trace.jsonl",
        trace_csv=tmp_path / "artifact" / "xlsx_content_drop_trace.csv",
        report_json=tmp_path / "report.json",
        report_csv=tmp_path / "report.csv",
        answer_generation_inputs=tmp_path / "inputs.jsonl",
        retrieval_report=tmp_path / "retrieval.json",
        failure_breakdown=tmp_path / "breakdown.json",
        db_snapshot=trace.DbSnapshot(True, "", {"docv_test": [parser_artifact]}, {"docv_test": [index_unit]}),
        source_input_rows=[row],
        rows=rows,
    )

    trace_row = rows[0]
    assert trace_row["parser_artifact_stage"]["has_values"] is True
    assert trace_row["index_payload_stage"]["has_values"] is True
    assert trace_row["retrieval_result_stage"]["has_values"] is False
    assert trace_row["answer_generation_input_stage"]["has_values"] is False
    assert trace_row["answer_input_drops_content"] is True
    assert "XLSX_ANSWER_INPUT_DROPS_CONTENT" in trace_row["diagnostic_reason_codes"]
    assert report["answer_allowed_count"] == 0
    assert report["xlsx_answer_eval_denominator"] == 0
    assert report["content_exists_upstream_but_dropped_before_answer_inputs_count"] == 1


def test_source_answer_allowed_or_denominator_flags_fail_report_guardrail(tmp_path: Path):
    row = _row(file_name="promoted.xlsx", source_path=None, context_values=False)
    promoted_row = dict(row)
    promoted_row["answer_allowed"] = True
    promoted_row["answer_eval_allowed"] = True

    report = trace.build_report(
        run_id="test",
        generated_at="2026-05-06T00:00:00+00:00",
        artifact_dir=tmp_path / "artifact",
        trace_jsonl=tmp_path / "artifact" / "xlsx_content_drop_trace.jsonl",
        trace_csv=tmp_path / "artifact" / "xlsx_content_drop_trace.csv",
        report_json=tmp_path / "report.json",
        report_csv=tmp_path / "report.csv",
        answer_generation_inputs=tmp_path / "inputs.jsonl",
        retrieval_report=tmp_path / "retrieval.json",
        failure_breakdown=tmp_path / "breakdown.json",
        db_snapshot=trace.DbSnapshot(True, "", {}, {}),
        source_input_rows=[promoted_row],
        rows=[],
    )

    assert report["status"] == "FAIL"
    assert report["answer_allowed_count"] == 1
    assert report["xlsx_answer_eval_denominator"] == 1
    assert report["denominator_remains_zero"] is False
    assert report["source_input_guardrails"]["source_input_any_answer_allowed_or_denominator_flag_count"] == 2


def test_broad_parser_and_index_content_does_not_count_as_exact_upstream_content():
    row = _row(file_name="source.xlsx", source_path=None, context_values=False)
    parser_artifact = {
        "artifact_json": {
            "workbook": {
                "sheets": [
                    {
                        "name": "Sheet1",
                        "compactText": "This sheet has broad content outside the requested locator.",
                        "chunks": [{"cellRange": "C10:D11", "text": "Out of range: 456"}],
                    }
                ]
            }
        }
    }
    index_unit = {
        "location_json": {},
        "text_content": "Workbook summary with broad content only",
        "embedding_text": "Workbook summary with broad content only",
        "chunk_type": "workbook_summary",
    }

    rows = trace.build_trace_rows(
        [row],
        run_id="test",
        dataset_index={},
        retrieval_maps={"query_results": {}, "classified_rows": {}},
        parser_artifacts_by_docv={"docv_test": [parser_artifact]},
        index_units_by_docv={"docv_test": [index_unit]},
    )

    trace_row = rows[0]
    assert trace_row["parser_artifact_stage"]["has_values"] is False
    assert trace_row["parser_artifact_stage"]["broad_sheet_or_workbook_has_values"] is True
    assert trace_row["index_payload_stage"]["has_values"] is False
    assert trace_row["index_payload_stage"]["broad_sheet_or_workbook_has_values"] is True
    assert trace_row["upstream_content_available"] is False
    assert trace_row["answer_input_drops_content"] is False
    assert trace_row["content_never_exists_upstream"] is True


def _trace_one(row: dict, *, dataset_index: dict[str, list[Path]]) -> dict:
    parser_artifact = {
        "artifact_json": {
            "workbook": {
                "sheets": [
                    {
                        "name": "Sheet1",
                        "cells": [{"row": 2, "column": 2, "cell": "B2", "value": "123"}],
                    }
                ]
            }
        }
    }
    index_unit = {
        "location_json": {"sheet_name": "Sheet1", "cell_range": "A1:B2"},
        "text_content": "Item: Alpha | Value: 123",
        "chunk_type": "row_group",
    }
    return trace.build_trace_rows(
        [row],
        run_id="test",
        dataset_index=dataset_index,
        retrieval_maps={"query_results": {}, "classified_rows": {}},
        parser_artifacts_by_docv={"docv_test": [parser_artifact]},
        index_units_by_docv={"docv_test": [index_unit]},
    )[0]


def _row(
    *,
    file_name: str = "source.xlsx",
    source_path: Path | None,
    context_values: bool,
    policy: dict | None = None,
    context_errors: list[str] | None = None,
) -> dict:
    context = {
        "context_type": "xlsx",
        "file_name": file_name,
        "sheet_name": "Sheet1",
        "cell_range": "A1:B2",
        "locator": {"file": file_name, "sheet": "Sheet1", "range": "A1:B2", "document_version_id": "docv_test"},
        "context_available": context_values,
        "context_errors": context_errors or [],
    }
    if source_path is not None:
        context["source_path"] = str(source_path)
    if context_values:
        context["value_context"] = [
            {"cell": "B2", "row_label": "Alpha", "column_label": "Value", "value": "SHOULD_NOT_BE_PROBED"}
        ]
    return {
        "run_id": "source",
        "row_index": 1,
        "track": "XLSX",
        "query_id": f"q_{file_name}",
        "bucket": "xlsx_lookup",
        "query": "find value",
        "expected_answer_shape": "TABLE_ROW_VALUE",
        "expected_answer_text": "expected",
        "must_contain_terms": ["expected"],
        "expected_evidence_location": {
            "docv": "docv_test",
            "file": file_name,
            "sheet": "Sheet1",
            "range": "A1:B2",
        },
        "policy": policy or {"diagnostic_only": True, "promotion_evidence": False},
        "context": context,
    }


def _xlsx(path: Path, value: str) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Item", "Value"])
    ws.append(["Alpha", value])
    wb.save(path)
    return path
