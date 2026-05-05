from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-worker" / "scripts" / "rag_text_retrieval_diagnostic.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_text_retrieval_diagnostic_for_tests", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


diag = load_module()


def test_evaluate_rows_calculates_hits_mrr_recall_and_counts():
    rows = [
        _row("q1", "text_fact_lookup", source="source-a", chunk="chunk-a"),
        _row("q2", "text_fact_lookup", source="source-b", chunk="chunk-b"),
        _row("q3", "text_fact_lookup", source="source-c", chunk="chunk-c"),
        _row("q4", "text_fact_lookup", source="source-d", chunk="chunk-d"),
        _row("q5", "text_abstain_required", allowed_abstain="true", source="", chunk=""),
    ]

    report = diag.evaluate_rows(rows, search_fn=_fake_search, top_k=10)

    assert report["metrics"]["query_count"] == 5
    assert report["metrics"]["evidence_query_count"] == 4
    assert report["metrics"]["Hit@1"] == 1 / 4
    assert report["metrics"]["Hit@3"] == 2 / 4
    assert report["metrics"]["Hit@5"] == 2 / 4
    assert report["metrics"]["Hit@10"] == 2 / 4
    assert report["metrics"]["MRR@10"] == (1 + 1 / 2) / 4
    assert report["metrics"]["source_recall@10"] == 2 / 4
    assert report["metrics"]["chunk_recall@10"] == 2 / 4
    assert report["metrics"]["result_empty_count"] == 2
    assert report["metrics"]["wrong_source_top1_count"] == 2
    assert report["metrics"]["path_mixing_count"] == 1
    assert report["metrics"]["path_mixing_result_count"] == 1
    assert report["metrics"]["overall_failure_reason_counts"] == {
        "expected_source_not_found": 1,
        "search_result_empty": 1,
    }
    assert report["query_results"][0]["hit_rank"] == 1
    assert report["query_results"][1]["hit_rank"] == 2
    assert report["query_results"][2]["failure_reason"] == "expected_source_not_found"
    assert report["query_results"][3]["failure_reason"] == "search_result_empty"
    assert report["query_results"][4]["final_match_outcome"] == "not_evaluable_no_expected_evidence"
    assert report["query_results"][4]["failure_reason"] is None


def test_evaluate_rows_classifies_chunk_miss_under_matching_source():
    rows = [_row("q1", "text_fact_lookup", source="source-a", chunk="chunk-expected")]

    report = diag.evaluate_rows(rows, search_fn=lambda _query, _top_k: [_hit("source-a", "chunk-wrong")], top_k=10)

    assert report["metrics"]["overall_hit_policy"] == "expected source OR expected chunk"
    assert report["metrics"]["Hit@10"] == 1.0
    assert report["metrics"]["source_Hit@10"] == 1.0
    assert report["metrics"]["chunk_Hit@10"] == 0.0
    assert report["metrics"]["source_recall@10"] == 1.0
    assert report["metrics"]["chunk_recall@10"] == 0.0
    assert report["query_results"][0]["source_hit_rank"] == 1
    assert report["query_results"][0]["chunk_hit_rank"] is None
    assert report["query_results"][0]["failure_reason"] is None


def test_evaluate_rows_records_search_errors_as_blocking_failures():
    rows = [_row("q1", "text_fact_lookup", source="source-a", chunk="chunk-a")]

    def fail_search(_query: str, _top_k: int):
        raise RuntimeError("api down")

    report = diag.evaluate_rows(rows, search_fn=fail_search, top_k=10)

    assert report["metrics"]["search_error_count"] == 1
    assert report["metrics"]["result_empty_count"] == 0
    assert report["query_results"][0]["final_match_outcome"] == "search_error"
    assert report["query_results"][0]["failure_reason"] == "search_error"


def test_build_report_keeps_diagnostic_flags_and_done_criteria():
    rows = [_row("q1", "text_fact_lookup", source="source-a", chunk="chunk-a")]
    evaluation = diag.evaluate_rows(rows, search_fn=lambda _query, _top_k: [_hit("source-a", "chunk-a")], top_k=10)

    report = diag.build_report(
        gold=ROOT / "ai-worker" / "eval" / "eval_queries" / "gold_queries_text_e2e_v0.csv",
        rows=rows,
        columns=diag.REQUIRED_COLUMNS,
        validation={
            "ok": True,
            "row_count": 1,
            "missing_required_columns": [],
            "duplicate_query_ids": [],
            "row_errors": {},
            "bucket_counts": {"text_fact_lookup": 1},
        },
        evaluation=evaluation,
        backend="library_search",
        backend_identity_report={
            "status": "DIAGNOSTIC_COMPLETED",
            "retrieval_backend_identity": {"backend": "library_search"},
            "blockers": [],
        },
        backend_identity_report_path=ROOT / "ai-worker" / "eval" / "reports" / "rag-ingestion" / "rag_text_backend_identity_report.json",
        source_file_types=["MARKDOWN", "MD", "TEXT", "TXT"],
        top_k=10,
        api_url="http://localhost:8080/api/v1/library/search",
    )

    assert report["status"] == "COMPLETED"
    assert report["promotion_evidence"] is False
    assert report["evidence_role"] == "diagnostic"
    assert report["retrieval_backend_identity"] == {"backend": "library_search"}
    assert report["metrics"]["Hit@10"] == 1.0
    assert report["done_criteria"]["failure_reason_exists_for_miss_cases"] is True
    assert report["next_phase_recommendation"].startswith("Proceed to B3")


def test_build_report_does_not_recommend_b3_when_path_mixing_blocks_text_only_run():
    rows = [_row("q1", "text_fact_lookup", source="source-a", chunk="chunk-a")]
    evaluation = diag.evaluate_rows(
        rows,
        search_fn=lambda _query, _top_k: [_hit("source-a", "chunk-a", source_type="PDF")],
        top_k=10,
    )

    report = diag.build_report(
        gold=ROOT / "ai-worker" / "eval" / "eval_queries" / "gold_queries_text_e2e_v0.csv",
        rows=rows,
        columns=diag.REQUIRED_COLUMNS,
        validation={
            "ok": True,
            "row_count": 1,
            "missing_required_columns": [],
            "duplicate_query_ids": [],
            "row_errors": {},
            "bucket_counts": {"text_fact_lookup": 1},
        },
        evaluation=evaluation,
        backend="library_search",
        backend_identity_report={
            "status": "DIAGNOSTIC_COMPLETED",
            "retrieval_backend_identity": {"backend": "library_search"},
            "blockers": [],
        },
        backend_identity_report_path=ROOT / "ai-worker" / "eval" / "reports" / "rag-ingestion" / "rag_text_backend_identity_report.json",
        source_file_types=["MARKDOWN", "MD", "TEXT", "TXT"],
        top_k=10,
        api_url="http://localhost:8080/api/v1/library/search",
    )

    assert report["status"] == "COMPLETED_WITH_BLOCKERS"
    assert "TEXT-only search returned mixed source types: 1 queries" in report["blockers"]
    assert report["next_phase_recommendation"].startswith("Keep B3 blocked")


def test_normalize_source_file_types_expands_text_aliases_and_url_repeats_params():
    source_types = diag.normalize_source_file_types(["TEXT", "txt"])
    url = diag.library_search_url(
        "http://localhost:8080/api/v1/library/search",
        "test query",
        10,
        source_file_types=source_types,
    )

    assert source_types == ["MARKDOWN", "MD", "TEXT", "TXT"]
    assert url == (
        "http://localhost:8080/api/v1/library/search?"
        "query=test+query&limit=10&sourceFileTypes=MARKDOWN&sourceFileTypes=MD"
        "&sourceFileTypes=TEXT&sourceFileTypes=TXT"
    )


def test_normalize_source_file_types_rejects_non_text_filters():
    try:
        diag.normalize_source_file_types(["TEXT", "PDF"])
    except ValueError as exc:
        assert "accepts only TEXT/TXT/MARKDOWN/MD" in str(exc)
    else:
        raise AssertionError("PDF must not be accepted for Track B TEXT diagnostics")


def _fake_search(query: str, _top_k: int):
    if query == "q1 question":
        return [_hit("source-a", "chunk-a")]
    if query == "q2 question":
        return [_hit("source-x", "chunk-x"), _hit("source-b", "chunk-b")]
    if query == "q3 question":
        return [_hit("source-y", "chunk-y", source_type="PDF")]
    return []


def _hit(source_id: str, chunk_id: str, *, source_type: str = "TEXT") -> dict[str, object]:
    return {
        "sourceFile": {
            "sourceFileId": source_id,
            "originalFileName": f"{source_id}.txt",
            "fileType": source_type,
        },
        "searchUnit": {
            "searchUnitId": chunk_id,
            "sourceFileId": source_id,
            "sourceFileType": source_type,
            "unitType": "CHUNK",
            "unitKey": "chunk:1",
            "chunkType": "paragraph",
            "locationType": "text",
            "citationText": f"{source_id}.txt > chunk 1",
            "textPreview": "diagnostic text",
        },
    }


def _row(
    query_id: str,
    bucket: str,
    *,
    allowed_abstain: str = "false",
    source: str = "source-1",
    chunk: str = "chunk-1",
) -> dict[str, str]:
    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": f"{query_id} question",
        "expected_source_ids": source,
        "expected_chunk_ids": chunk,
        "allowed_abstain": allowed_abstain,
        "label_status": "bound" if allowed_abstain == "false" else "draft",
    }
