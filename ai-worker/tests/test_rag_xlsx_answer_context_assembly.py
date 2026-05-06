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
    expected_answer_text: str = "Alpha 123",
    must_contain_terms: list[str] | None = None,
) -> dict:
    return {
        "run_id": "source",
        "row_index": 1,
        "track": "XLSX",
        "query_id": "q_context",
        "query": "find value",
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


def _unit(*, chunk_type: str = "row_group", cell_range: str = "A1:B2") -> dict:
    return {
        "id": "su1",
        "document_version_id": "docv1",
        "source_file_name": "sample.xlsx",
        "chunk_type": chunk_type,
        "location_json": {
            "document_version_id": "docv1",
            "sheet_name": "Sheet1",
            "cell_range": cell_range,
            "type": "xlsx",
        },
        "display_text": "Item: Alpha | Value: 123",
        "text_content": "Item: Alpha | Value: 123",
        "parser_version": "xlsx-extract-v2-hidden-safe",
        "index_version": "rag-ingestion-v2-xlsx-candidate-v1",
        "embedding_status": "EMBEDDED",
    }


def _index(unit: dict) -> dict:
    return {
        "enabled": True,
        "status": "LOADED",
        "error": "",
        "by_id": {unit["id"]: unit},
        "by_docv": {"docv1": [unit]},
        "selected_search_unit_id_count": 1,
        "loaded_search_unit_count": 1,
    }
