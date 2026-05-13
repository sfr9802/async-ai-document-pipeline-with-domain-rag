from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_WORKER_ROOT = ROOT / "ai"
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


builder = load_module(
    AI_WORKER_ROOT / "scripts" / "rag_pdf_xlsx_answer_generation_input_builder.py",
    "rag_pdf_xlsx_answer_generation_input_builder_for_context_tests",
)
serializer = load_module(
    AI_WORKER_ROOT / "eval" / "harness" / "pdf_xlsx_answer_evidence_serializer.py",
    "pdf_xlsx_answer_evidence_serializer_for_context_tests",
)
compiler = load_module(
    AI_WORKER_ROOT / "eval" / "harness" / "pdf_xlsx_deterministic_answer_compiler.py",
    "pdf_xlsx_deterministic_answer_compiler_for_context_tests",
)


def test_locator_only_retrieval_hit_joins_searchunit_content_into_answer_input():
    context = _joined_context()
    input_row = _input_row(context=context)

    evidence_row = serializer.serialize_input_rows([input_row], run_id="context")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="context")[0]

    assert context["context_available"] is True
    assert context["xlsx_searchunit_content_join"]["join_type"] == "exact_locator"
    assert context["xlsx_searchunit_content_join"]["content_source_field"] == "search_unit.display_text"
    assert evidence_row["answer_allowed"] is True
    assert "context.row_values" in ";".join(evidence_row["content_source_fields"])
    assert compiled_row["compiler_status"] == "COMPILED"
    assert "Alpha" in compiled_row["compiled_answer"]["answer"]
    assert "123" in compiled_row["compiled_answer"]["answer"]
    assert compiled_row["compiled_answer"]["citations"]


def test_safe_range_overlap_join_is_allowed_without_broad_fallback():
    hit = _hit(search_unit_id="", cell_range="A1:B3")
    unit = _unit(cell_range="A2:B2")
    context = builder.xlsx_searchunit_answer_context(
        retrieval_context={"top_k_results": [hit]},
        searchunit_index=_index(unit),
    )

    assert context["context_available"] is True
    assert context["xlsx_searchunit_content_join"]["join_type"] == "safe_range_overlap"
    assert context["xlsx_searchunit_content_join"]["broad_fallback_promoted"] is False


def test_node_id_alias_can_join_loaded_searchunit_content():
    hit = _hit(search_unit_id="")
    hit["node_id"] = "idx1"
    context = builder.xlsx_searchunit_answer_context(
        retrieval_context={"top_k_results": [hit]},
        searchunit_index=_index(_unit()),
    )

    assert context["context_available"] is True
    assert context["xlsx_searchunit_content_join"]["join_type"] == "exact_locator"
    assert context["xlsx_searchunit_content_join"]["search_unit_id"] == "su1"


def test_unjoinable_retrieval_hit_remains_fail_closed():
    context = builder.xlsx_searchunit_answer_context(
        retrieval_context={"top_k_results": [_hit(search_unit_id="missing")]},
        searchunit_index=_index(_unit()),
    )
    input_row = _input_row(context={**_locator_context(), **context})

    evidence_row = serializer.serialize_input_rows([input_row], run_id="context")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="context")[0]

    assert context["context_available"] is False
    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] == "XLSX_LOCATOR_ONLY"
    assert compiled_row["compiled_answer"]["answer"] == ""


def test_lookup_002_like_query_anchor_mismatch_fails_closed():
    _assert_query_anchor_mismatch(
        query="신분당선 2019년 5월 승차총승객수 알려줘.",
        content="노선명: 일산선 | 년월: 201904 | 승차총승객수: 3,608,124",
    )


def test_auto_039_like_query_anchor_mismatch_fails_closed():
    _assert_query_anchor_mismatch(
        query="경의선 승차 쪽 찾아줘.",
        content="노선명: 경인선 | 년월: 201904 | 승차총승객수: 10,409,566",
    )


def test_auto_042_like_query_anchor_mismatch_fails_closed():
    _assert_query_anchor_mismatch(
        query="축복전문요양원 장기요양기관 정보 찾아줘.",
        content="장기요양기관코드: 12,823,700,748 | 장기요양기관이름: 팔복요양원 | 기관별 상세주소: 인천광역시 부평구",
    )


def test_date_number_format_like_query_anchor_mismatch_fails_closed():
    _assert_query_anchor_mismatch(
        query="163,443,126 승객수 찾아줘.",
        content="대중교통구분: 지하철 | 노선명: 9호선 | 년월: 201712 | 승차총승객수: 8,048,476",
    )


def test_expected_locator_promoted_or_context_citation_mismatch_fails_closed():
    context = _joined_context()
    context["sheet_name"] = "ExpectedSheet"
    context["cell_range"] = "Z1:Z9"
    context["expected_evidence_locator_diagnostic_only"] = {
        "file": "sample.xlsx",
        "sheet": "ExpectedSheet",
        "range": "Z1:Z9",
        "document_version_id": "docv1",
    }
    input_row = _input_row(context=context, query="Alpha Value 찾아줘")

    evidence_row = serializer.serialize_input_rows([input_row], run_id="context")[0]
    failure_codes = evidence_row["evidence_quality"]["failure_codes"]

    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] in {
        "XLSX_CONTEXT_CITATION_LOCATOR_MISMATCH",
        "XLSX_EXPECTED_LOCATOR_PROMOTED",
    }
    assert "XLSX_CONTEXT_CITATION_LOCATOR_MISMATCH" in failure_codes
    assert "XLSX_EXPECTED_LOCATOR_PROMOTED" in failure_codes


def test_same_sheet_range_but_different_docv_fails_citation_locator_match():
    context = _joined_context()
    context["citation_locator"] = {
        **context["citation_locator"],
        "document_version_id": "docv-other",
    }
    input_row = _input_row(context=context, query="Alpha Value 찾아줘")

    evidence_row = serializer.serialize_input_rows([input_row], run_id="context")[0]

    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] == "XLSX_CONTEXT_CITATION_LOCATOR_MISMATCH"
    assert "XLSX_CONTEXT_CITATION_LOCATOR_MISMATCH" in evidence_row["evidence_quality"]["failure_codes"]


def test_prompt_context_excludes_gold_answer_fields_and_locators():
    context = _joined_context()
    prompt_context = builder.build_prompt_context(
        row={
            "query": "Alpha Value 찾아줘",
            "expected_answer_shape": "TABLE_ROW_VALUE",
            "expected_answer_text": "GOLD_SECRET",
            "must_contain_terms": "GOLD_SECRET",
            "content_target_needed": "GOLD_SECRET",
            "citation_target_policy": "GOLD_SECRET",
        },
        locator={"file": "gold.xlsx", "sheet": "GoldSheet", "range": "Z1:Z9"},
        context=context,
        policy={"diagnostic_only": True, "promotion_evidence": False},
        max_context_chars=6000,
    )
    payload = json.loads(prompt_context)

    assert "GOLD_SECRET" not in prompt_context
    assert "expected_answer_text" not in payload
    assert "must_contain_terms" not in payload
    assert "expected_evidence_location" not in payload
    assert "content_target_needed" not in payload
    assert payload["citation_policy"] == "cite_only_bound_context_locator"


def test_valid_query_bound_row_uses_target_column_value_with_matching_citation():
    context = builder.xlsx_searchunit_answer_context(
        retrieval_context={"top_k_results": [_hit()]},
        searchunit_index=_index(
            _unit(display_text="노선명: 5호선 | 년월: 201905 | 승차총승객수: 123")
        ),
    )
    input_row = _input_row(context=context, query="5호선 승차총승객수 찾아줘")

    evidence_row = serializer.serialize_input_rows([input_row], run_id="context")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="context")[0]
    citation_locator = compiled_row["compiled_answer"]["citations"][0]["locator"]

    assert evidence_row["answer_allowed"] is True
    assert evidence_row["evidence_object"]["query_binding"]["query_bound_values"][0]["column_label"] == "승차총승객수"
    assert "승차총승객수" in compiled_row["compiled_answer"]["answer"]
    assert "123" in compiled_row["compiled_answer"]["answer"]
    assert "노선명 column value is 5호선" not in compiled_row["compiled_answer"]["answer"]
    assert citation_locator == evidence_row["content_source_locator"]


def test_synthetic_non_gold_workbook_terms_compile_generically():
    context = builder.xlsx_searchunit_answer_context(
        retrieval_context={"top_k_results": [_hit()]},
        searchunit_index=_index(
            _unit(display_text="장비명: 테스트장비A | 측정월: 202602 | 처리량: 42")
        ),
    )
    input_row = _input_row(context=context, query="테스트장비A 처리량 찾아줘")

    evidence_row = serializer.serialize_input_rows([input_row], run_id="context")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="context")[0]
    binding = evidence_row["evidence_object"]["query_binding"]

    assert evidence_row["answer_allowed"] is True
    assert binding["workbook_vocabulary_source"] == "retrieved_searchunit_payload"
    assert binding["stopword_source"] == "language_intent"
    assert binding["matched_header_labels"] == ["처리량"]
    assert "테스트장비A" in compiled_row["compiled_answer"]["answer"]
    assert "처리량" in compiled_row["compiled_answer"]["answer"]
    assert "42" in compiled_row["compiled_answer"]["answer"]


def test_bound_entity_is_preserved_when_row_label_is_a_code():
    context = builder.xlsx_searchunit_answer_context(
        retrieval_context={"top_k_results": [_hit()]},
        searchunit_index=_index(
            _unit(display_text="기관코드: A-001 | 기관명: 해오름센터 | 지정일자: 2024-02-03")
        ),
    )
    input_row = _input_row(context=context, query="해오름센터 지정일자 찾아줘")

    evidence_row = serializer.serialize_input_rows([input_row], run_id="context")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="context")[0]

    assert evidence_row["answer_allowed"] is True
    assert compiled_row["compiler_status"] == "COMPILED"
    assert "해오름센터" in compiled_row["compiled_answer"]["answer"]
    assert "지정일자" in compiled_row["compiled_answer"]["answer"]
    assert "2024-02-03" in compiled_row["compiled_answer"]["answer"]


def test_different_header_names_are_not_forced_to_gold_header_aliases():
    valid_context = builder.xlsx_searchunit_answer_context(
        retrieval_context={"top_k_results": [_hit()]},
        searchunit_index=_index(
            _unit(display_text="역명: 파랑역 | 기준월: 202601 | 탑승인원: 77")
        ),
    )
    valid_row = _input_row(context=valid_context, query="파랑역 탑승인원 찾아줘")
    valid_evidence = serializer.serialize_input_rows([valid_row], run_id="context")[0]
    valid_compiled = compiler.compile_evidence_rows([valid_evidence], run_id="context")[0]

    assert valid_evidence["answer_allowed"] is True
    assert valid_evidence["evidence_object"]["query_binding"]["matched_header_labels"] == ["탑승인원"]
    assert "탑승인원" in valid_compiled["compiled_answer"]["answer"]
    assert "77" in valid_compiled["compiled_answer"]["answer"]

    invalid_row = _input_row(context=valid_context, query="파랑역 승차총승객수 찾아줘")
    invalid_evidence = serializer.serialize_input_rows([invalid_row], run_id="context")[0]
    invalid_compiled = compiler.compile_evidence_rows([invalid_evidence], run_id="context")[0]

    assert invalid_evidence["answer_allowed"] is False
    assert invalid_evidence["fail_closed_reason"] == "XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY"
    assert "승차총승객수" in invalid_evidence["evidence_object"]["query_binding"]["unbound_query_terms"]
    assert invalid_compiled["compiled_answer"]["answer"] == ""


def test_language_stopwords_do_not_become_entity_anchors():
    context = builder.xlsx_searchunit_answer_context(
        retrieval_context={"top_k_results": [_hit()]},
        searchunit_index=_index(
            _unit(display_text="항목: Alpha | 값열: 123")
        ),
    )
    input_row = _input_row(context=context, query="자료 정보 쪽 찾아줘")

    evidence_row = serializer.serialize_input_rows([input_row], run_id="context")[0]
    binding = evidence_row["evidence_object"]["query_binding"]

    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] == "XLSX_QUERY_ANCHOR_MISSING"
    assert binding["query_anchors"]["entity_anchors"] == []
    assert set(binding["ignored_stopwords"]) == {"자료", "정보", "쪽", "찾아줘"}
    assert binding["stopword_source"] == "language_intent"


def test_gold_fields_do_not_bind_otherwise_unanchored_query():
    context = builder.xlsx_searchunit_answer_context(
        retrieval_context={"top_k_results": [_hit()]},
        searchunit_index=_index(_unit(display_text="Item: Alpha | Value: 123")),
    )
    input_row = _input_row(
        context=context,
        query="찾아줘",
        expected_answer_text="Alpha Value 123",
        must_contain_terms=["Alpha", "Value", "123"],
    )

    evidence_row = serializer.serialize_input_rows([input_row], run_id="context")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="context")[0]

    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] == "XLSX_QUERY_ANCHOR_MISSING"
    assert evidence_row["evidence_object"]["query_binding"]["query_bound_values"] == []
    assert compiled_row["compiled_answer"]["answer"] == ""


def test_content_row_without_bound_query_anchor_remains_fail_closed():
    context = builder.xlsx_searchunit_answer_context(
        retrieval_context={"top_k_results": [_hit()]},
        searchunit_index=_index(_unit(display_text="Item: Alpha | Value: 123")),
    )
    input_row = _input_row(context=context, query="요약해줘")

    evidence_row = serializer.serialize_input_rows([input_row], run_id="context")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="context")[0]

    assert evidence_row["content_window_available"] is True
    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] in {
        "XLSX_QUERY_ANCHOR_MISSING",
        "XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY",
    }
    assert compiled_row["compiled_answer"]["answer"] == ""


def test_policy_pending_row_skips_searchunit_answer_content_join():
    row = {
        "query_id": "q_context",
        "expected_answer_shape": builder.ANSWER_SHAPE_POLICY_PENDING,
        "expected_file_name": "sample.xlsx",
        "expected_sheet_name": "Sheet1",
        "expected_cell_range": "A1:B2",
    }
    context = builder.build_xlsx_context(
        row=row,
        locator={"file": "sample.xlsx", "sheet": "Sheet1", "range": "A1:B2", "docv": "docv1"},
        dataset_index={},
        cache={},
        retrieval_maps={
            "xlsx": {
                "query_results": {"q_context": {"top_k_results": [_hit()]}},
                "classified_rows": {},
            }
        },
        xlsx_searchunit_index=_index(_unit()),
        policy={"not_answerable_or_policy_pending": True},
    )
    evidence_row = serializer.serialize_input_rows([_input_row(context=context, shape=builder.ANSWER_SHAPE_POLICY_PENDING)], run_id="context")[0]

    assert context["context_available"] is False
    assert context["xlsx_searchunit_content_join"]["status"] == "SKIPPED_POLICY_PENDING"
    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] == "XLSX_POLICY_PENDING"


def test_source_workbook_diagnostic_values_are_not_promoted_when_join_fails(tmp_path: Path):
    workbook = tmp_path / "sample.xlsx"
    workbook.write_text("SOURCE_WORKBOOK_SECRET", encoding="utf-8")
    context = builder.build_xlsx_context(
        row={
            "query_id": "q_context",
            "expected_file_name": "sample.xlsx",
            "expected_sheet_name": "Sheet1",
            "expected_cell_range": "A1:B2",
        },
        locator={"file": "sample.xlsx", "sheet": "Sheet1", "range": "A1:B2", "docv": "docv1"},
        dataset_index={"sample.xlsx": [workbook]},
        cache={},
        retrieval_maps={"xlsx": {"query_results": {}, "classified_rows": {}}},
        xlsx_searchunit_index=builder.empty_xlsx_searchunit_content_index("test"),
        policy={"diagnostic_only": True},
    )
    evidence_row = serializer.serialize_input_rows([_input_row(context=context)], run_id="context")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="context")[0]
    payload = json.dumps([evidence_row["evidence_object"], compiled_row["compiled_answer"]], ensure_ascii=False)

    assert context["context_available"] is False
    assert "SOURCE_WORKBOOK_SECRET" not in payload
    assert evidence_row["answer_allowed"] is False
    assert compiled_row["compiled_answer"]["answer"] == ""


def test_expected_answer_and_must_contain_are_not_evidence_terms():
    context = _joined_context()
    input_row = _input_row(
        context=context,
        expected_answer_text="GOLD_SECRET",
        must_contain_terms=["GOLD_SECRET"],
    )

    evidence_row = serializer.serialize_input_rows([input_row], run_id="context")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="context")[0]

    assert "GOLD_SECRET" not in json.dumps(evidence_row["evidence_object"], ensure_ascii=False)
    assert "GOLD_SECRET" not in json.dumps(compiled_row["compiled_answer"], ensure_ascii=False)
    assert "GOLD_SECRET" not in compiled_row["compiled_answer"]["used_content_terms"]


def test_broad_sheet_or_workbook_content_is_not_promoted():
    unit = _unit(chunk_type="workbook_summary", cell_range="")
    context = builder.xlsx_searchunit_answer_context(
        retrieval_context={"top_k_results": [_hit()]},
        searchunit_index=_index(unit),
    )
    input_row = _input_row(context={**_locator_context(), **context})

    evidence_row = serializer.serialize_input_rows([input_row], run_id="context")[0]

    assert context["context_available"] is False
    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] == "XLSX_LOCATOR_ONLY"


def test_retrieval_context_preserves_selected_searchunit_id_for_later_join():
    context = builder.retrieval_context_for(
        "q_context",
        {
            "xlsx": {
                "query_results": {"q_context": {"top_k_results": [_hit(search_unit_id="su-preserved")]}},
                "classified_rows": {},
            }
        },
        "xlsx",
    )

    assert context["top_k_results"][0]["search_unit_id"] == "su-preserved"


def _joined_context() -> dict:
    return builder.xlsx_searchunit_answer_context(
        retrieval_context={"top_k_results": [_hit()]},
        searchunit_index=_index(_unit()),
    )


def _input_row(
    *,
    context: dict,
    shape: str = "TABLE_ROW_VALUE",
    query: str = "find value",
    expected_answer_text: str = "Alpha 123",
    must_contain_terms: list[str] | None = None,
) -> dict:
    return {
        "run_id": "source",
        "row_index": 1,
        "track": "XLSX",
        "query_id": "q_context",
        "query": query,
        "expected_answer_shape": shape,
        "expected_answer_text": expected_answer_text,
        "must_contain_terms": must_contain_terms or ["Alpha", "123"],
        "policy": {"diagnostic_only": True, "promotion_evidence": False},
        "context": {"context_type": "xlsx", **_locator_context(), **context},
    }


def _locator_context() -> dict:
    return {
        "file_name": "sample.xlsx",
        "sheet_name": "Sheet1",
        "cell_range": "A1:B2",
        "locator": {
            "file": "sample.xlsx",
            "sheet": "Sheet1",
            "range": "A1:B2",
            "document_version_id": "docv1",
        },
        "context_available": False,
        "context_has_expected_terms": False,
    }


def _hit(*, search_unit_id: str = "su1", cell_range: str = "A1:B2") -> dict:
    return {
        "rank": 1,
        "score": 0.9,
        "search_unit_id": search_unit_id,
        "source_file_name": "sample.xlsx",
        "chunk_type": "row_group",
        "citation_text": f"sample.xlsx > Sheet1 > {cell_range}",
        "location_json": {
            "document_version_id": "docv1",
            "sheet_name": "Sheet1",
            "cell_range": cell_range,
            "type": "xlsx",
        },
    }


def _unit(
    *,
    chunk_type: str = "row_group",
    cell_range: str = "A1:B2",
    display_text: str = "Item: Alpha | Value: 123",
) -> dict:
    return {
        "id": "su1",
        "index_id": "idx1",
        "document_version_id": "docv1",
        "source_file_name": "sample.xlsx",
        "chunk_type": chunk_type,
        "location_json": {
            "document_version_id": "docv1",
            "sheet_name": "Sheet1",
            "cell_range": cell_range,
            "type": "xlsx",
        },
        "display_text": display_text,
        "text_content": display_text,
        "parser_version": "xlsx-extract-v2-hidden-safe",
        "index_version": "rag-ingestion-v2-xlsx-candidate-v1",
        "embedding_status": "EMBEDDED",
    }


def _index(unit: dict) -> dict:
    return {
        "enabled": True,
        "status": "LOADED",
        "error": "",
        "by_id": {unit["id"]: unit, unit["index_id"]: unit},
        "by_docv": {"docv1": [unit]},
        "selected_search_unit_id_count": 1,
        "loaded_search_unit_count": 1,
    }


def _assert_query_anchor_mismatch(*, query: str, content: str) -> None:
    context = builder.xlsx_searchunit_answer_context(
        retrieval_context={"top_k_results": [_hit()]},
        searchunit_index=_index(_unit(display_text=content)),
    )
    input_row = _input_row(context=context, query=query)

    evidence_row = serializer.serialize_input_rows([input_row], run_id="context")[0]
    compiled_row = compiler.compile_evidence_rows([evidence_row], run_id="context")[0]

    assert evidence_row["answer_allowed"] is False
    assert evidence_row["fail_closed_reason"] in {
        "XLSX_QUERY_ANCHOR_MISMATCH",
        "XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY",
    }
    assert set(evidence_row["evidence_quality"]["failure_codes"]) & {
        "XLSX_QUERY_ANCHOR_MISMATCH",
        "XLSX_QUERY_TERM_NOT_IN_WORKBOOK_VOCABULARY",
    }
    assert compiled_row["compiled_answer"]["answer"] == ""
