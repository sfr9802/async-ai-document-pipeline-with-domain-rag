from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


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


serializer = load_module(
    AI_WORKER_ROOT / "eval" / "harness" / "pdf_xlsx_answer_evidence_serializer.py",
    "pdf_xlsx_answer_evidence_serializer_for_tests",
)
compiler = load_module(
    AI_WORKER_ROOT / "eval" / "harness" / "pdf_xlsx_deterministic_answer_compiler.py",
    "pdf_xlsx_deterministic_answer_compiler_for_tests",
)
evaluator = load_module(
    AI_WORKER_ROOT / "scripts" / "rag_pdf_xlsx_answer_shape_evaluator.py",
    "rag_pdf_xlsx_answer_shape_evaluator_for_repair_tests",
)


def test_missing_content_summary_abstains_without_counting_content_match():
    input_row = {
        "run_id": "source",
        "row_index": 1,
        "track": "XLSX",
        "query_id": "q_missing",
        "query": "find ridership value",
        "expected_answer_shape": "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT",
        "expected_answer_text": "ridership",
        "must_contain_terms": ["ridership"],
        "policy": {"diagnostic_only": True, "promotion_evidence": False},
        "context": {
            "context_type": "xlsx",
            "file_name": "sample.xlsx",
            "sheet_name": "Sheet1",
            "cell_range": "A1:B2",
            "locator": {"file": "sample.xlsx", "sheet": "Sheet1", "range": "A1:B2"},
            "context_available": False,
            "context_has_expected_terms": False,
            "context_errors": ["source workbook missing"],
        },
    }

    evidence_row = serializer.serialize_input_rows([input_row], run_id="repair")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="repair")[0]
    eval_row = evaluator.evaluate_row(input_row, answer_row_from_compiled(compiled_row))

    assert evidence_row["answer_generation_allowed"] is False
    assert evidence_row["answer_allowed"] is False
    assert evidence_row["answer_generation_blocker"] == "XLSX_LOCATOR_ONLY"
    assert evidence_row["fail_closed_reason"] == "XLSX_LOCATOR_ONLY"
    assert evidence_row["content_window_available"] is False
    assert compiled_row["compiled_answer"]["answer"] == ""
    assert compiled_row["compiled_answer_draft"]["answer"] == ""
    assert compiled_row["compiled_answer"]["failure_mode_if_any"] == "XLSX_LOCATOR_ONLY"
    assert eval_row["content_target_match"] is False
    assert eval_row["answer_shape_match"] is False
    assert eval_row["context_missing_abstain"] is True
    assert eval_row["table_or_cell_context_missing"] is False


def test_table_row_value_compiles_required_row_column_value_claim():
    input_row = {
        "run_id": "source",
        "row_index": 2,
        "track": "XLSX",
        "query_id": "q_value",
        "query": "station total",
        "expected_answer_shape": "TABLE_ROW_VALUE",
        "expected_answer_text": "Station A",
        "must_contain_terms": ["Station A", "Total"],
        "policy": {"diagnostic_only": True, "promotion_evidence": False},
        "context": {
            "context_type": "xlsx",
            "file_name": "sample.xlsx",
            "sheet_name": "Sheet1",
            "cell_range": "A1:B2",
            "locator": {"file": "sample.xlsx", "sheet": "Sheet1", "range": "A1:B2"},
            "row_label": "Station A",
            "column_label": "Total",
            "header_context": ["Station", "Total"],
            "value_context": [
                {
                    "cell": "B2",
                    "row_label": "Station A",
                    "column_label": "Total",
                    "value": "123",
                }
            ],
            "nearby_table_context": ["Station: Station A | Total: 123"],
            "context_available": True,
            "context_has_expected_terms": True,
            "context_errors": [],
        },
    }

    evidence_row = serializer.serialize_input_rows([input_row], run_id="repair")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="repair")[0]
    eval_row = evaluator.evaluate_row(input_row, answer_row_from_compiled(compiled_row))

    assert evidence_row["answer_generation_allowed"] is True
    assert evidence_row["answer_allowed"] is True
    assert "matched_keyword" not in evidence_row["evidence_object"]
    assert evidence_row["evidence_object"]["column_labels"] == ["Total"]
    assert evidence_row["evidence_object"]["row_values"][0]["value"] == "123"
    assert evidence_row["evidence_object"]["content_source_fields"]
    assert "Station A" in compiled_row["compiled_answer"]["answer"]
    assert "Total" in compiled_row["compiled_answer"]["answer"]
    assert "123" in compiled_row["compiled_answer"]["answer"]
    assert eval_row["content_target_match"] is True
    assert eval_row["answer_shape_match"] is True
    assert eval_row["location_only_without_content"] is False
    assert eval_row["citation_attached_to_keyword_not_claim"] is False


def test_evaluator_records_llm_hallucinated_unsupported_claim_failure():
    input_row = {
        "run_id": "source",
        "row_index": 3,
        "track": "XLSX",
        "query_id": "q_hallucinated",
        "query": "station total",
        "expected_answer_shape": "TABLE_ROW_VALUE",
        "expected_answer_text": "Station A",
        "must_contain_terms": ["Station A", "Total"],
        "policy": {"diagnostic_only": True, "promotion_evidence": False},
        "context": {
            "context_type": "xlsx",
            "context_available": True,
            "context_has_expected_terms": True,
        },
    }
    answer_row = {
        "track": "XLSX",
        "query_id": "q_hallucinated",
        "query": "station total",
        "expected_answer_shape": "TABLE_ROW_VALUE",
        "parsed_answer": {
            "answer": "Station A / Total value is 999.",
            "answer_shape": "TABLE_ROW_VALUE",
            "citations": [{"locator": {"sheet": "Sheet1"}, "supports_claim": True, "claim": "Station A / Total value is 999."}],
            "abstain_reason": "",
            "used_content_terms": ["Station A", "Total"],
            "failure_mode_if_any": "LLM_HALLUCINATED_UNSUPPORTED_CLAIM",
        },
        "parse_ok": True,
        "raw_parse_ok": True,
        "repair_parse_ok": False,
        "unsupported_claim_added": True,
        "failure_reason": "LLM_HALLUCINATED_UNSUPPORTED_CLAIM",
        "compiled_answer": {"answer": "Station A / Total value is 123."},
        "evidence_object": {
            "row_label": "Station A",
            "column_label": "Total",
            "value": "123",
            "content_summary": "Station A / Total value is 123.",
        },
    }

    eval_row = evaluator.evaluate_row(input_row, answer_row)

    assert eval_row["failure_reason"] == "LLM_HALLUCINATED_UNSUPPORTED_CLAIM"
    assert eval_row["unsupported_claim_added"] is True
    assert eval_row["content_target_match"] is False


def test_xlsx_keyword_only_input_abstains():
    input_row = {
        "run_id": "source",
        "row_index": 4,
        "track": "XLSX",
        "query_id": "q_keyword",
        "query": "find ridership",
        "expected_answer_shape": "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT",
        "expected_answer_text": "ridership",
        "must_contain_terms": ["ridership"],
        "policy": {"diagnostic_only": True, "promotion_evidence": False},
        "context": {
            "context_type": "xlsx",
            "matched_keyword": "ridership",
            "context_available": False,
            "context_has_expected_terms": False,
        },
    }

    evidence_row = serializer.serialize_input_rows([input_row], run_id="repair")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="repair")[0]

    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] == "XLSX_KEYWORD_ONLY"
    assert compiled_row["compiled_answer"]["answer"] == ""
    assert compiled_row["compiled_answer"]["abstain_reason"]


def test_xlsx_sheet_range_only_input_abstains_without_content_answer():
    input_row = {
        "run_id": "source",
        "row_index": 5,
        "track": "XLSX",
        "query_id": "q_locator",
        "query": "sheet range",
        "expected_answer_shape": "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT",
        "expected_answer_text": "Total",
        "must_contain_terms": ["Total"],
        "policy": {"diagnostic_only": True, "promotion_evidence": False},
        "context": {
            "context_type": "xlsx",
            "file_name": "sample.xlsx",
            "sheet_name": "Sheet1",
            "cell_range": "A1:B4",
            "locator": {"file": "sample.xlsx", "sheet": "Sheet1", "range": "A1:B4"},
            "context_available": False,
            "context_has_expected_terms": False,
        },
    }

    evidence_row = serializer.serialize_input_rows([input_row], run_id="repair")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="repair")[0]

    assert evidence_row["answer_allowed"] is False
    assert evidence_row["locator_only_evidence"] is True
    assert evidence_row["fail_closed_reason"] == "XLSX_LOCATOR_ONLY"
    assert compiled_row["compiled_answer"]["answer"] == ""


def test_xlsx_header_and_nearby_rows_with_values_allows_range_answer():
    input_row = {
        "run_id": "source",
        "row_index": 6,
        "track": "XLSX",
        "query_id": "q_nearby",
        "query": "station totals",
        "expected_answer_shape": "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT",
        "expected_answer_text": "Station A Total",
        "must_contain_terms": ["Station A", "Total", "123"],
        "policy": {"diagnostic_only": True, "promotion_evidence": False},
        "context": {
            "context_type": "xlsx",
            "file_name": "sample.xlsx",
            "sheet_name": "Sheet1",
            "cell_range": "A1:B2",
            "locator": {"file": "sample.xlsx", "sheet": "Sheet1", "range": "A1:B2"},
            "header_context": ["Station", "Total"],
            "nearby_table_context": ["Station: Station A | Total: 123"],
            "context_available": True,
            "context_has_expected_terms": True,
        },
    }

    evidence_row = serializer.serialize_input_rows([input_row], run_id="repair")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="repair")[0]
    eval_row = evaluator.evaluate_row(input_row, answer_row_from_compiled(compiled_row))

    assert evidence_row["answer_allowed"] is True
    assert evidence_row["content_window_available"] is True
    assert "nearby_table_context" in ";".join(evidence_row["content_source_fields"])
    assert compiled_row["compiler_status"] == "COMPILED"
    assert "Station A" in compiled_row["compiled_answer"]["answer"]
    assert "123" in compiled_row["compiled_answer"]["answer"]
    assert compiled_row["compiled_answer"]["citations"]
    assert eval_row["answer_has_content_claim"] is True
    assert eval_row["content_target_match"] is True
    assert eval_row["answer_shape_match"] is True


def test_xlsx_table_row_value_does_not_invent_from_nearby_text():
    input_row = {
        "run_id": "source",
        "row_index": 7,
        "track": "XLSX",
        "query_id": "q_no_invent",
        "query": "station total",
        "expected_answer_shape": "TABLE_ROW_VALUE",
        "expected_answer_text": "Station A",
        "must_contain_terms": ["Station A", "Total"],
        "policy": {"diagnostic_only": True, "promotion_evidence": False},
        "context": {
            "context_type": "xlsx",
            "file_name": "sample.xlsx",
            "sheet_name": "Sheet1",
            "cell_range": "A1:B2",
            "locator": {"file": "sample.xlsx", "sheet": "Sheet1", "range": "A1:B2"},
            "row_label": "Station A",
            "column_label": "Total",
            "nearby_table_context": ["Station A appears near the Total column"],
            "context_available": True,
            "context_has_expected_terms": True,
        },
    }

    evidence_row = serializer.serialize_input_rows([input_row], run_id="repair")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="repair")[0]
    eval_row = evaluator.evaluate_row(input_row, answer_row_from_compiled(compiled_row))

    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] == "XLSX_LOCATOR_ONLY"
    assert compiled_row["compiled_answer"]["answer"] == ""
    assert compiled_row["compiled_answer"]["abstain_reason"]
    assert compiled_row["compiled_answer"]["failure_mode_if_any"] == "XLSX_LOCATOR_ONLY"
    assert eval_row["content_target_match"] is False
    assert eval_row["answer_shape_match"] is False


def test_xlsx_expected_only_content_summary_is_not_allowed():
    input_row = {
        "run_id": "source",
        "row_index": 8,
        "track": "XLSX",
        "query_id": "q_leakage",
        "query": "station total",
        "expected_answer_shape": "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT",
        "expected_answer_text": "Station A Total",
        "must_contain_terms": ["Station A Total"],
        "policy": {"diagnostic_only": True, "promotion_evidence": False},
        "context": {
            "context_type": "xlsx",
            "content_summary": "Station A Total",
            "context_available": True,
            "context_has_expected_terms": True,
        },
    }

    evidence_row = serializer.serialize_input_rows([input_row], run_id="repair")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="repair")[0]

    assert evidence_row["answer_allowed"] is False
    assert evidence_row["content_summary"] == ""
    assert evidence_row["fail_closed_reason"] in {"XLSX_NO_TABLE_CONTEXT", "XLSX_NO_CONTENT_WINDOW"}
    assert compiled_row["compiled_answer"]["answer"] == ""


def test_pdf_locator_only_context_stays_fail_closed():
    input_row = {
        "run_id": "source",
        "row_index": 9,
        "track": "PDF",
        "query_id": "q_pdf_locator",
        "query": "section summary",
        "expected_answer_shape": "PDF_SECTION_WITH_SUMMARY",
        "expected_answer_text": "economic trend",
        "must_contain_terms": ["economic"],
        "policy": {"diagnostic_only": True, "promotion_evidence": False},
        "context": {
            "context_type": "pdf",
            "file_name": "sample.pdf",
            "page_no": "1",
            "section_id": "1.1",
            "bbox": [1, 2, 3, 4],
            "locator": {"file": "sample.pdf", "page": "1", "bbox": [1, 2, 3, 4]},
            "context_available": False,
            "context_has_expected_terms": False,
        },
    }

    evidence_row = serializer.serialize_input_rows([input_row], run_id="repair")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="repair")[0]
    eval_row = evaluator.evaluate_row(input_row, answer_row_from_compiled(compiled_row))

    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] == "PDF_LOCATOR_ONLY"
    evidence_json = json.dumps(evidence_row["evidence_object"], ensure_ascii=False)
    assert "economic trend" not in evidence_json
    assert "economic" not in evidence_json
    assert compiled_row["compiler_status"] == "LOCATOR_ONLY_ABSTAIN"
    assert compiled_row["compiled_answer"]["answer"] == ""
    assert eval_row["content_target_match"] is False
    assert eval_row["answer_shape_match"] is False


def test_xlsx_policy_pending_does_not_serialize_hidden_values():
    input_row = {
        "run_id": "source",
        "row_index": 10,
        "track": "XLSX",
        "query_id": "q_hidden",
        "query": "hidden value",
        "expected_answer_shape": "TABLE_ROW_VALUE",
        "expected_answer_text": "Visible target",
        "must_contain_terms": ["Visible target"],
        "policy": {
            "diagnostic_only": True,
            "promotion_evidence": False,
            "hidden_policy_blocked": True,
        },
        "context": {
            "context_type": "xlsx",
            "file_name": "sample.xlsx",
            "sheet_name": "Hidden",
            "cell_range": "A1:B2",
            "locator": {"file": "sample.xlsx", "sheet": "Hidden", "range": "A1:B2"},
            "value_context": [
                {"cell": "B2", "row_label": "Secret Row", "column_label": "Secret", "value": "DO_NOT_LEAK"}
            ],
            "nearby_table_context": ["Secret: DO_NOT_LEAK | Total: 123"],
            "context_available": True,
            "context_has_expected_terms": True,
        },
    }

    evidence_row = serializer.serialize_input_rows([input_row], run_id="repair")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="repair")[0]
    payload = json.dumps([evidence_row, compiled_row], ensure_ascii=False)

    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] == "XLSX_POLICY_PENDING"
    assert evidence_row["content_window_available"] is False
    assert "DO_NOT_LEAK" not in payload
    assert "Secret Row" not in payload
    assert compiled_row["compiled_answer"]["answer"] == ""


def test_evaluator_expected_answer_echo_is_not_content_success():
    input_row = {
        "run_id": "source",
        "row_index": 11,
        "track": "XLSX",
        "query_id": "q_echo",
        "query": "station total",
        "expected_answer_shape": "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT",
        "expected_answer_text": "Station A Total",
        "must_contain_terms": ["Station A", "Total"],
        "policy": {"diagnostic_only": True, "promotion_evidence": False},
        "context": {"context_type": "xlsx", "context_available": True, "context_has_expected_terms": True},
    }
    answer_row = {
        "track": "XLSX",
        "query_id": "q_echo",
        "query": "station total",
        "expected_answer_shape": "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT",
        "parsed_answer": {
            "answer": "Station A Total",
            "answer_shape": "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT",
            "citations": [{"locator": {"sheet": "Sheet1"}, "supports_claim": True, "claim": "Station A Total"}],
            "abstain_reason": "",
            "used_content_terms": ["Station A", "Total"],
            "failure_mode_if_any": "",
        },
        "parse_ok": True,
        "raw_parse_ok": True,
        "repair_parse_ok": False,
        "compiled_answer": {"answer": "Station A Total"},
        "evidence_object": {},
        "answer_allowed": True,
        "answer_generation_allowed": True,
        "compiler_status": "COMPILED",
    }

    eval_row = evaluator.evaluate_row(input_row, answer_row)

    assert eval_row["answer_has_content_claim"] is False
    assert eval_row["content_target_match"] is False
    assert eval_row["answer_shape_match"] is False


def test_serialized_rows_are_jsonl_roundtrip_safe():
    input_row = {
        "run_id": "source",
        "row_index": 10,
        "track": "XLSX",
        "query_id": "q_schema",
        "query": "station total",
        "expected_answer_shape": "TABLE_ROW_VALUE",
        "expected_answer_text": "Station A",
        "must_contain_terms": ["Station A", "Total"],
        "policy": {"diagnostic_only": True, "promotion_evidence": False},
        "context": {
            "context_type": "xlsx",
            "value_context": [{"cell": "B2", "row_label": "Station A", "column_label": "Total", "value": "123"}],
        },
    }

    evidence_row = serializer.serialize_input_rows([input_row], run_id="repair")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="repair")[0]
    loaded_evidence = json.loads(json.dumps(evidence_row, ensure_ascii=False))
    loaded_compiled = json.loads(json.dumps(compiled_row, ensure_ascii=False))

    assert loaded_evidence["schema_version"] == "rag_pdf_xlsx_answer_evidence_objects_v1"
    assert loaded_compiled["schema_version"] == "rag_pdf_xlsx_deterministic_compiled_answers_v1"
    assert loaded_compiled["compiled_answer"]["citations"]


def answer_row_from_compiled(compiled_row: dict) -> dict:
    return {
        "track": compiled_row["track"],
        "query_id": compiled_row["query_id"],
        "query": compiled_row["query"],
        "expected_answer_shape": compiled_row["expected_answer_shape"],
        "answer_json_raw": compiled_row["compiled_answer_json"],
        "parsed_answer": compiled_row["compiled_answer"],
        "parse_ok": True,
        "raw_parse_ok": True,
        "repair_parse_ok": False,
        "local_llm_run": False,
        "llm_polish_run": False,
        "deterministic_compiler_run": True,
        "deterministic_compiled_answer_used": True,
        "unsupported_claim_added": False,
        "failure_reason": "",
        "compiled_answer_draft": compiled_row["compiled_answer_draft"],
        "compiled_answer": compiled_row["compiled_answer"],
        "evidence_object": compiled_row["evidence_object"],
        "answer_allowed": compiled_row["answer_allowed"],
        "answer_generation_allowed": compiled_row["answer_generation_allowed"],
        "compiler_status": compiled_row["compiler_status"],
        "external_live_llm_run": False,
        "optional_judge_run": False,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
    }
