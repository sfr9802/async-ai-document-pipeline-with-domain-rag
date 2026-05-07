from __future__ import annotations

import importlib.util
import csv
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
llm_probe = load_module(
    AI_WORKER_ROOT / "scripts" / "rag_pdf_xlsx_llm_answer_probe.py",
    "rag_pdf_xlsx_llm_answer_probe_for_repair_tests",
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
    assert evidence_row["fail_closed_reason"] in {
        "XLSX_NO_TABLE_CONTEXT",
        "XLSX_NO_CONTENT_WINDOW",
        "XLSX_CONTENT_PRESENT_BUT_UNSUPPORTED_SHAPE",
    }
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


def test_llm_answer_probe_prompt_excludes_gold_fields():
    source_row = xlsx_probe_source_row()
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    compiled_row["compiled_answer"]["expected_answer_text"] = "GoldOnlyValue"
    compiled_row["compiled_answer"]["must_contain_terms"] = ["GoldOnlyMust"]
    compiled_row["compiled_answer"]["label_status"] = "gold-only"
    compiled_row["compiled_answer"]["citations"][0]["locator"]["gold_label"] = "gold-only"

    probe_row = llm_probe.build_llm_answer_probe_input_row(
        evidence_row=evidence_row,
        compiled_row=compiled_row,
        run_id="probe",
    )
    prompt_blob = json.dumps(
        {
            "prompt": probe_row["answer_prompt"],
            "payload": probe_row["answer_prompt_payload"],
        },
        ensure_ascii=False,
    )

    assert probe_row["answer_allowed"] is True
    assert "expected_answer_text" not in prompt_blob
    assert "must_contain_terms" not in prompt_blob
    assert "expected_evidence_location" not in prompt_blob
    assert "label_status" not in prompt_blob
    assert "gold_label" not in prompt_blob
    assert "GoldOnlyValue" not in prompt_blob
    assert "GoldOnlyMust" not in prompt_blob


def test_llm_answer_probe_evidence_only_answer_passes_checks():
    source_row = xlsx_probe_source_row(expected_answer_text="GoldOnlyValue", must_terms=["GoldOnlyMust"])
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    probe_row = llm_probe.build_llm_answer_probe_input_row(
        evidence_row=evidence_row,
        compiled_row=compiled_row,
        run_id="probe",
    )
    parsed = {
        "query_id": "q_probe",
        "answer": "Station A row / Total column value is 123.",
        "answer_type": "CELL_VALUE",
        "citations": [{"file": "sample.xlsx", "sheet": "Sheet1", "range": "A1:B2", "source": "selected_searchunit_payload"}],
        "used_evidence_fields": ["evidence.row_values"],
        "unsupported_claims": [],
        "abstain_reason": "",
        "confidence": "high",
    }

    checks = llm_probe.answer_checks(probe_input=probe_row, parsed_answer=parsed, source_row=source_row)

    assert checks["llm_unsupported_claim_count"] == 0
    assert checks["llm_gold_leakage_suspected"] is False
    assert checks["llm_citation_missing"] is False
    assert checks["llm_citation_not_in_context"] is False
    assert checks["llm_citation_support_status"] == "PASS"


def test_llm_response_rejects_hallucinated_locator():
    source_row = xlsx_probe_source_row(expected_answer_text="GoldOnlyValue", must_terms=["GoldOnlyMust"])
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    probe_row = llm_probe.build_llm_answer_probe_input_row(
        evidence_row=evidence_row,
        compiled_row=compiled_row,
        run_id="probe",
    )
    parsed = {
        "query_id": "q_probe",
        "answer": "Station A row / Total column value is 123.",
        "answer_type": "CELL_VALUE",
        "citations": [{"sheet": "OtherSheet", "range": "Z9:Z9", "source": "selected_searchunit_payload"}],
        "used_evidence_fields": ["evidence.row_values"],
        "unsupported_claims": [],
        "abstain_reason": "",
        "confidence": "high",
    }

    checks = llm_probe.answer_checks(probe_input=probe_row, parsed_answer=parsed, source_row=source_row)

    assert checks["llm_citation_missing"] is False
    assert checks["llm_citation_not_in_context"] is True
    assert checks["llm_citation_support_status"] == "citation_not_in_retrieved_context"
    assert checks["llm_citation_failure_reasons"] == ["wrong_sheet_citation"]


def test_llm_response_citations_must_come_from_retrieved_context():
    result = llm_probe.validate_probe_citations(
        [{"file": "sample.xlsx", "sheet": "Sheet1", "range": "Z9:Z9", "source": "selected_searchunit_payload"}],
        {"citation_locator": {"file": "sample.xlsx", "sheet": "Sheet1", "range": "A1:B2"}},
    )

    assert result["status"] == "citation_not_in_retrieved_context"
    assert result["failure_reasons"] == ["wrong_range_citation"]


def test_llm_response_citation_missing_source_is_not_invented():
    source_row = xlsx_probe_source_row(expected_answer_text="GoldOnlyValue", must_terms=["GoldOnlyMust"])
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    probe_row = llm_probe.build_llm_answer_probe_input_row(
        evidence_row=evidence_row,
        compiled_row=compiled_row,
        run_id="probe",
    )
    parsed = llm_probe.normalize_probe_answer(
        {
            "query_id": "q_probe",
            "answer": "Station A row / Total column value is 123.",
            "answer_type": "CELL_VALUE",
            "citations": [{"sheet": "Sheet1", "range": "A1:B2"}],
            "used_evidence_fields": ["evidence.row_values"],
            "unsupported_claims": [],
            "abstain_reason": "",
            "confidence": "high",
        },
        fallback_query_id="q_probe",
    )

    assert parsed["citations"][0]["source"] == ""

    checks = llm_probe.answer_checks(probe_input=probe_row, parsed_answer=parsed, source_row=source_row)

    assert checks["llm_citation_missing"] is True
    assert checks["llm_citation_not_in_context"] is True
    assert checks["llm_citation_failure_reasons"] == ["citation_missing_required_fields"]


def test_llm_response_parser_does_not_invent_locator():
    parsed = llm_probe.normalize_probe_answer(
        {
            "query_id": "q_probe",
            "answer": "Station A row / Total column value is 123.",
            "answer_type": "CELL_VALUE",
            "citations": [{"sheet": "Sheet1", "range": "A1:B2"}],
            "used_evidence_fields": ["evidence.row_values"],
            "unsupported_claims": [],
            "abstain_reason": "",
            "confidence": "high",
        },
        fallback_query_id="q_probe",
    )

    assert parsed["citations"][0]["file"] == ""
    assert parsed["citations"][0]["search_unit_id"] == ""
    assert parsed["citations"][0]["document_version_id"] == ""


def test_llm_response_rejects_partial_overlap_locator():
    source_row = xlsx_probe_source_row(expected_answer_text="GoldOnlyValue", must_terms=["GoldOnlyMust"])
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    probe_row = llm_probe.build_llm_answer_probe_input_row(
        evidence_row=evidence_row,
        compiled_row=compiled_row,
        run_id="probe",
    )
    parsed = {
        "query_id": "q_probe",
        "answer": "Station A row / Total column value is 123.",
        "answer_type": "CELL_VALUE",
        "citations": [{"file": "sample.xlsx", "sheet": "Sheet1", "range": "B2:B2", "source": "selected_searchunit_payload"}],
        "used_evidence_fields": ["evidence.row_values"],
        "unsupported_claims": [],
        "abstain_reason": "",
        "confidence": "high",
    }

    checks = llm_probe.answer_checks(probe_input=probe_row, parsed_answer=parsed, source_row=source_row)

    assert checks["llm_citation_missing"] is False
    assert checks["llm_citation_not_in_context"] is True
    assert checks["llm_citation_failure_reasons"] == ["partial_range_overlap"]


def test_llm_response_rejects_wrong_locator_identity_fields():
    prompt_payload = {
        "citation_locator": {
            "file": "sample.xlsx",
            "sheet": "Sheet1",
            "range": "A1:B2",
            "document_version_id": "docv-1",
            "search_unit_id": "unit-1",
        }
    }

    wrong_file = llm_probe.validate_probe_citations(
        [
            {
                "file": "other.xlsx",
                "sheet": "Sheet1",
                "range": "A1:B2",
                "source": "selected_searchunit_payload",
                "document_version_id": "docv-1",
                "search_unit_id": "unit-1",
            }
        ],
        prompt_payload,
    )
    wrong_docv = llm_probe.validate_probe_citations(
        [
            {
                "file": "sample.xlsx",
                "sheet": "Sheet1",
                "range": "A1:B2",
                "source": "selected_searchunit_payload",
                "document_version_id": "docv-other",
                "search_unit_id": "unit-1",
            }
        ],
        prompt_payload,
    )
    wrong_unit = llm_probe.validate_probe_citations(
        [
            {
                "file": "sample.xlsx",
                "sheet": "Sheet1",
                "range": "A1:B2",
                "source": "selected_searchunit_payload",
                "document_version_id": "docv-1",
                "search_unit_id": "unit-other",
            }
        ],
        prompt_payload,
    )

    assert wrong_file["failure_reasons"] == ["wrong_file_citation"]
    assert wrong_docv["failure_reasons"] == ["wrong_document_version_citation"]
    assert wrong_unit["failure_reasons"] == ["wrong_search_unit_citation"]


def test_validate_probe_citations_rejects_same_sheet_nonoverlap():
    result = llm_probe.validate_probe_citations(
        [{"sheet": "Sheet1", "range": "Z9:Z9", "source": "selected_searchunit_payload"}],
        {"citation_locator": {"sheet": "Sheet1", "range": "A1:B2"}},
    )

    assert result["status"] == "citation_not_in_retrieved_context"
    assert result["failure_reasons"] == ["wrong_range_citation"]


def test_normalized_probe_citation_preserves_nested_locator_identity():
    normalized = llm_probe.normalize_probe_citation(
        {
            "source": "selected_searchunit_payload",
            "locator": {
                "file": "sample.xlsx",
                "sheet": "Sheet1",
                "range": "A1:B2",
                "document_version_id": "docv-1",
                "search_unit_id": "unit-1",
            },
        }
    )

    assert normalized["file"] == "sample.xlsx"
    assert normalized["document_version_id"] == "docv-1"
    assert normalized["search_unit_id"] == "unit-1"


def test_gold_intent_role_probe_sees_gold_fields_but_does_not_write_answer_evidence():
    source_row = xlsx_probe_source_row(expected_answer_text="123", must_terms=["Station A", "Total", "123"])
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    probe_row = llm_probe.build_llm_answer_probe_input_row(
        evidence_row=evidence_row,
        compiled_row=compiled_row,
        run_id="probe",
    )
    answer_output = {
        "query_id": "q_probe",
        "answer": "Station A row / Total column value is 123.",
    }

    role_row = llm_probe.build_gold_intent_role_row(
        source_row=source_row,
        probe_input=probe_row,
        answer_output=answer_output,
    )

    assert role_row["expected_answer_text_role"] == "EXACT_ANSWER_VALUE"
    assert role_row["gold_intent_probe_used_for_scoring"] is False
    assert role_row["answer_evidence_updated"] is False
    assert "evidence_object" not in role_row


def test_gold_only_must_term_in_llm_answer_is_flagged_as_leakage():
    source_row = xlsx_probe_source_row(expected_answer_text="GoldOnlyValue", must_terms=["GoldOnlyMust"])
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    probe_row = llm_probe.build_llm_answer_probe_input_row(
        evidence_row=evidence_row,
        compiled_row=compiled_row,
        run_id="probe",
    )
    parsed = {
        "query_id": "q_probe",
        "answer": "GoldOnlyMust",
        "answer_type": "ROW_SUMMARY",
        "citations": [{"file": "sample.xlsx", "sheet": "Sheet1", "range": "A1:B2", "source": "selected_searchunit_payload"}],
        "used_evidence_fields": [],
        "unsupported_claims": [],
        "abstain_reason": "",
        "confidence": "low",
    }

    checks = llm_probe.answer_checks(probe_input=probe_row, parsed_answer=parsed, source_row=source_row)

    assert checks["llm_gold_leakage_suspected"] is True
    assert "GoldOnlyMust" in checks["gold_leakage_terms"]


def test_policy_pending_rows_are_not_sent_to_answer_generation_llm(tmp_path):
    source_row = xlsx_probe_source_row()
    source_row["policy"] = {
        "diagnostic_only": True,
        "promotion_evidence": False,
        "hidden_policy_blocked": True,
    }
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    inputs = tmp_path / "answer_generation_inputs.jsonl"
    evidence = tmp_path / "evidence_objects.jsonl"
    compiled = tmp_path / "compiled_answers.jsonl"
    write_jsonl(inputs, [source_row])
    write_jsonl(evidence, [evidence_row])
    write_jsonl(compiled, [compiled_row])
    calls = []

    report = llm_probe.run_probe(
        source_artifact_dir=tmp_path,
        inputs_path=inputs,
        evidence_objects_path=evidence,
        compiled_answers_path=compiled,
        output_root=tmp_path,
        run_id="probe",
        run_prefix="probe",
        backend="llamacpp",
        base_url="http://localhost:8081/v1",
        model="fake-local",
        temperature=0.0,
        timeout_seconds=1,
        max_tokens=50,
        llm_client=lambda prompt: calls.append(prompt) or "{}",
    )

    assert calls == []
    assert report["llm_answer_probe_row_count"] == 1
    assert report["llm_abstain_count"] == 1


def test_policy_pending_flag_overrides_inconsistent_allowed_flags():
    source_row = xlsx_probe_source_row()
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    evidence_row["policy_pending"] = True
    evidence_row["answer_allowed"] = True
    evidence_row["answer_generation_allowed"] = True
    evidence_row["fail_closed_reason"] = ""

    probe_row = llm_probe.build_llm_answer_probe_input_row(
        evidence_row=evidence_row,
        compiled_row=compiled_row,
        run_id="probe",
    )

    assert probe_row["answer_allowed"] is False
    assert probe_row["llm_requested"] is False
    assert probe_row["answer_prompt"] == ""
    assert probe_row["fail_closed_reason"] == "XLSX_POLICY_PENDING"


def test_llm_probe_report_keeps_official_denominator_and_promotion_false(tmp_path):
    source_row = xlsx_probe_source_row()
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    inputs = tmp_path / "answer_generation_inputs.jsonl"
    evidence = tmp_path / "evidence_objects.jsonl"
    compiled = tmp_path / "compiled_answers.jsonl"
    write_jsonl(inputs, [source_row])
    write_jsonl(evidence, [evidence_row])
    write_jsonl(compiled, [compiled_row])

    report = llm_probe.run_probe(
        source_artifact_dir=tmp_path,
        inputs_path=inputs,
        evidence_objects_path=evidence,
        compiled_answers_path=compiled,
        output_root=tmp_path,
        run_id="probe2",
        run_prefix="probe",
        backend="llamacpp",
        base_url="http://localhost:8081/v1",
        model="fake-local",
        temperature=0.0,
        timeout_seconds=1,
        max_tokens=50,
        llm_client=lambda prompt: json.dumps(
            {
                "query_id": "q_probe",
                "answer": "Station A row / Total column value is 123.",
                "answer_type": "CELL_VALUE",
                "citations": [
                    {"file": "sample.xlsx", "sheet": "Sheet1", "range": "A1:B2", "source": "selected_searchunit_payload"}
                ],
                "used_evidence_fields": ["evidence.row_values"],
                "unsupported_claims": [],
                "abstain_reason": "",
                "confidence": "high",
            }
        ),
    )

    assert report["official_xlsx_answer_eval_denominator"] == 0
    assert report["promotion_evidence"] is False
    assert report["expected_answer_text_used_in_answer_prompt"] is False
    assert report["must_contain_terms_used_in_answer_prompt"] is False


def test_llm_probe_report_marks_grounding_failure_diagnostic(tmp_path):
    source_row = xlsx_probe_source_row()
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    inputs = tmp_path / "answer_generation_inputs.jsonl"
    evidence = tmp_path / "evidence_objects.jsonl"
    compiled = tmp_path / "compiled_answers.jsonl"
    write_jsonl(inputs, [source_row])
    write_jsonl(evidence, [evidence_row])
    write_jsonl(compiled, [compiled_row])

    report = llm_probe.run_probe(
        source_artifact_dir=tmp_path,
        inputs_path=inputs,
        evidence_objects_path=evidence,
        compiled_answers_path=compiled,
        output_root=tmp_path,
        run_id="probe_grounding_failure",
        run_prefix="probe",
        backend="llamacpp",
        base_url="http://localhost:8081/v1",
        model="fake-local",
        temperature=0.0,
        timeout_seconds=1,
        max_tokens=50,
        llm_client=lambda prompt: json.dumps(
            {
                "query_id": "q_probe",
                "answer": "Station A row / Total column value is 123.",
                "answer_type": "CELL_VALUE",
                "citations": [
                    {"sheet": "OtherSheet", "range": "A1:B2", "source": "selected_searchunit_payload"}
                ],
                "used_evidence_fields": ["evidence.row_values"],
                "unsupported_claims": [],
                "abstain_reason": "",
                "confidence": "high",
            }
        ),
    )

    assert report["status"] == "PASS_WITH_WARNINGS"
    assert report["grounding_validation_status"] == "DIAGNOSTIC_FAILURE"
    assert report["diagnostic_grounding_failure_count"] > 0
    rows = read_csv(tmp_path / "probe_probe_grounding_failure" / "llm_answer_probe_report.csv")
    assert rows[0]["citation_not_in_context"] == "True"
    assert report["official_xlsx_answer_eval_denominator"] == 0


def test_llm_smoke_final_record_schema_valid_on_invalid_json(tmp_path):
    source_row = xlsx_probe_source_row()
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    inputs = tmp_path / "answer_generation_inputs.jsonl"
    evidence = tmp_path / "evidence_objects.jsonl"
    compiled = tmp_path / "compiled_answers.jsonl"
    write_jsonl(inputs, [source_row])
    write_jsonl(evidence, [evidence_row])
    write_jsonl(compiled, [compiled_row])

    report = llm_probe.run_probe(
        source_artifact_dir=tmp_path,
        inputs_path=inputs,
        evidence_objects_path=evidence,
        compiled_answers_path=compiled,
        output_root=tmp_path,
        run_id="invalid_json",
        run_prefix="probe",
        backend="llamacpp",
        base_url="http://localhost:8081/v1",
        model="fake-local",
        temperature=0.0,
        timeout_seconds=1,
        max_tokens=50,
        llm_client=lambda prompt: "keyword answer without json",
    )

    row = read_jsonl(tmp_path / "probe_invalid_json" / "llm_answer_probe_outputs.jsonl")[0]
    required = {
        "query_id",
        "track",
        "eval_mode",
        "llm_smoke_status",
        "raw_output_status",
        "parser_status",
        "content_shape_status",
        "citation_validation_status",
        "official_metric_included",
        "answer_generation_denominator_included",
        "failure_reason",
        "trace_id",
        "prompt_hash",
        "context_hash",
    }

    assert required.issubset(row)
    assert row["raw_output_status"] == "MODEL_OUTPUT_INVALID_JSON"
    assert row["parser_status"] == "JSON_REPAIR_FAILED"
    assert row["llm_smoke_status"] == "DIAGNOSTIC_FAILURE"
    assert row["official_metric_included"] is False
    assert row["answer_generation_denominator_included"] is False
    assert report["official_xlsx_answer_eval_denominator"] == 0


def test_llm_smoke_keyword_only_answer_rejected(tmp_path):
    source_row = xlsx_probe_source_row(expected_answer_text="station total", must_terms=["station total"])
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    inputs = tmp_path / "answer_generation_inputs.jsonl"
    evidence = tmp_path / "evidence_objects.jsonl"
    compiled = tmp_path / "compiled_answers.jsonl"
    write_jsonl(inputs, [source_row])
    write_jsonl(evidence, [evidence_row])
    write_jsonl(compiled, [compiled_row])

    llm_json = json.dumps(
        {
            "query_id": "q_probe",
            "answer": "station total",
            "answer_type": "ROW_SUMMARY",
            "citations": [
                {"file": "sample.xlsx", "sheet": "Sheet1", "range": "A1:B2", "source": "selected_searchunit_payload"}
            ],
            "used_evidence_fields": ["evidence.row_values"],
            "unsupported_claims": [],
            "abstain_reason": "",
            "confidence": "low",
        }
    )
    report = llm_probe.run_probe(
        source_artifact_dir=tmp_path,
        inputs_path=inputs,
        evidence_objects_path=evidence,
        compiled_answers_path=compiled,
        output_root=tmp_path,
        run_id="keyword_only",
        run_prefix="probe",
        backend="llamacpp",
        base_url="http://localhost:8081/v1",
        model="fake-local",
        temperature=0.0,
        timeout_seconds=1,
        max_tokens=50,
        llm_client=lambda prompt: llm_json,
    )

    row = read_jsonl(tmp_path / "probe_keyword_only" / "llm_answer_probe_outputs.jsonl")[0]

    assert row["content_shape_status"] == "KEYWORD_ONLY_REJECTED"
    assert row["failure_reason"] == "KEYWORD_ONLY_REJECTED"
    assert row["llm_smoke_status"] == "DIAGNOSTIC_FAILURE"
    assert row["official_metric_included"] is False
    assert row["answer_generation_denominator_included"] is False
    assert report["official_xlsx_answer_eval_denominator"] == 0


def test_llm_smoke_diagnostic_failure_not_official_metric(tmp_path):
    source_row = xlsx_probe_source_row()
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    inputs = tmp_path / "answer_generation_inputs.jsonl"
    evidence = tmp_path / "evidence_objects.jsonl"
    compiled = tmp_path / "compiled_answers.jsonl"
    write_jsonl(inputs, [source_row])
    write_jsonl(evidence, [evidence_row])
    write_jsonl(compiled, [compiled_row])

    report = llm_probe.run_probe(
        source_artifact_dir=tmp_path,
        inputs_path=inputs,
        evidence_objects_path=evidence,
        compiled_answers_path=compiled,
        output_root=tmp_path,
        run_id="not_official",
        run_prefix="probe",
        backend="llamacpp",
        base_url="http://localhost:8081/v1",
        model="fake-local",
        temperature=0.0,
        timeout_seconds=1,
        max_tokens=50,
        llm_client=lambda prompt: "not json",
    )
    row = read_jsonl(tmp_path / "probe_not_official" / "llm_answer_probe_outputs.jsonl")[0]

    assert report["grounding_validation_status"] == "DIAGNOSTIC_FAILURE"
    assert report["promotion_evidence"] is False
    assert report["official_xlsx_answer_eval_denominator"] == 0
    assert row["official_metric_included"] is False
    assert row["answer_generation_denominator_included"] is False


def test_llm_e2e_metrics_are_diagnostic_only(tmp_path):
    source_row = xlsx_probe_source_row()
    evidence_row = serializer.serialize_input_rows([source_row], run_id="probe")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="probe")[0]
    inputs = tmp_path / "answer_generation_inputs.jsonl"
    evidence = tmp_path / "evidence_objects.jsonl"
    compiled = tmp_path / "compiled_answers.jsonl"
    write_jsonl(inputs, [source_row])
    write_jsonl(evidence, [evidence_row])
    write_jsonl(compiled, [compiled_row])

    report = llm_probe.run_probe(
        source_artifact_dir=tmp_path,
        inputs_path=inputs,
        evidence_objects_path=evidence,
        compiled_answers_path=compiled,
        output_root=tmp_path,
        run_id="diagnostic_only",
        run_prefix="probe",
        backend="llamacpp",
        base_url="http://localhost:8081/v1",
        model="fake-local",
        temperature=0.0,
        timeout_seconds=1,
        max_tokens=50,
        llm_client=lambda prompt: "not json",
    )

    assert report["promotion_evidence"] is False
    assert report["official_answer_denominator"] == 0
    assert report["promotion_denominator"] == 0
    assert report["official_xlsx_answer_eval_denominator"] == 0


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


def xlsx_probe_source_row(expected_answer_text="GoldOnlyValue", must_terms=None):
    return {
        "run_id": "source",
        "row_index": 21,
        "track": "XLSX",
        "query_id": "q_probe",
        "query": "station total",
        "expected_answer_shape": "TABLE_ROW_VALUE",
        "expected_answer_text": expected_answer_text,
        "must_contain_terms": must_terms if must_terms is not None else ["GoldOnlyMust"],
        "expected_evidence_location": "Sheet1!A1:B2",
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


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
