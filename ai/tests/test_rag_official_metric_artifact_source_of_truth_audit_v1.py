from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "ai" / "eval" / "reports" / "rag-ingestion"
README = ROOT / "README.md"
PROGRESS_DOC = ROOT / "docs" / "rag-ingestion-progress.md"
REPAIRED_PDF_QUERY_IDS = ("gq_auto_010", "gq_auto_030", "gq_pdf_section_question_001")
AGENTIC_RUN_ID = "official_answer_citation_agentic_loop_run_v1"
AGENTIC_RESULTS = REPORT_DIR / f"{AGENTIC_RUN_ID}_results.jsonl"
AGENTIC_SUMMARY_JSON = REPORT_DIR / f"{AGENTIC_RUN_ID}_summary.json"
AGENTIC_SUMMARY_MD = REPORT_DIR / f"{AGENTIC_RUN_ID}_summary.md"
AGENTIC_INDEX_DIR = ROOT / "ai" / "eval" / "indexes" / "rag-data"
CURRENT_REPORT_FILENAMES = {
    "official_answer_citation_metric_first_run_v1.json",
    "official_answer_citation_metric_first_run_v1.md",
    "official_answer_citation_scorer_results_v1.jsonl",
    "official_metric_input_config_v1.json",
    "official_metric_pre_execution_smoke_report_v1.json",
    "xlsx_answer_citation_runtime_precision_candidate_results_v1.jsonl",
    "pdf_answer_citation_table_value_candidate_results_v1.jsonl",
    "rag_current_eval_status.jsonl",
    f"{AGENTIC_RUN_ID}_results.jsonl",
    f"{AGENTIC_RUN_ID}_summary.json",
    f"{AGENTIC_RUN_ID}_summary.md",
}


def test_source_of_truth_audit_reports_current_scored_baseline() -> None:
    first_run = read_json(REPORT_DIR / "official_answer_citation_metric_first_run_v1.json")
    first_run_md = (REPORT_DIR / "official_answer_citation_metric_first_run_v1.md").read_text(encoding="utf-8")
    scorer_rows = read_jsonl(REPORT_DIR / "official_answer_citation_scorer_results_v1.jsonl")
    xlsx_rows = read_jsonl(REPORT_DIR / "xlsx_answer_citation_runtime_precision_candidate_results_v1.jsonl")
    pdf_rows = read_jsonl(REPORT_DIR / "pdf_answer_citation_table_value_candidate_results_v1.jsonl")
    smoke = read_json(REPORT_DIR / "official_metric_pre_execution_smoke_report_v1.json")

    assert first_run["official_scoring_attempt_count"] == 29
    assert first_run["scored_count"] == 29
    assert first_run["official_metric_execution_started"] is True
    assert first_run["execution_blocker_category"] is None
    assert first_run["primary_failure_category"] == "CITATION_UNSUPPORTED"
    assert first_run["status_detail"] == "SCORED_BASELINE_PARTIAL"
    assert first_run["failure_category_counts"] == {
        "CITATION_UNSUPPORTED": 11,
        "PARTIAL_OR_UNSUPPORTED": 10,
        "PASS": 8,
    }
    assert "SCORER_BACKEND_UNAVAILABLE" not in json.dumps(first_run, ensure_ascii=False)
    assert "SCORER_BACKEND_UNAVAILABLE" not in first_run_md

    assert len(scorer_rows) == 29
    assert len({row["query_id"] for row in scorer_rows}) == 29
    first_run_rows_by_id = {row["query_id"]: row for row in first_run["row_results"]}
    mismatches = [
        row["query_id"]
        for row in scorer_rows
        if first_run_rows_by_id[row["query_id"]]["failure_category"] != row["failure_category"]
    ]
    assert mismatches == []

    assert len(xlsx_rows) == 29
    assert len({row["query_id"] for row in xlsx_rows}) == 29
    assert Counter(row["failure_category"] for row in xlsx_rows) == Counter({"PASS": 26, "PARTIAL_OR_UNSUPPORTED": 3})
    assert sum(
        1
        for row in xlsx_rows
        if row["track"] == "xlsx_business_structured" and row["failure_category"] == "PASS"
    ) == 19
    assert [
        row["query_id"]
        for row in xlsx_rows
        if row["track"] == "pdf_business_ocr_mm" and row["failure_category"] != "PASS"
    ] == ["gq_auto_010", "gq_auto_030", "gq_pdf_section_question_001"]

    assert len(pdf_rows) == 29
    assert len({row["query_id"] for row in pdf_rows}) == 29
    assert Counter(row["failure_category"] for row in pdf_rows) == Counter({"PASS": 29})
    for query_id in REPAIRED_PDF_QUERY_IDS:
        row = next(row for row in pdf_rows if row["query_id"] == query_id)
        score_details = row.get("score_details", {})
        locator = row["generated_citations"][0]["citation_locator"]
        assert score_details["deterministic_verification_passed"] is True
        assert score_details["expected_answer_used_for_generation"] is False
        assert score_details["supporting_evidence_used_for_generation"] is False
        assert score_details["gold_fields_used_for_generation"] is False
        assert score_details["source_text_contains_answer_value"] is True
        assert score_details["source_row_contains_target_value"] is True
        assert score_details["source_bound_identity_verified"] is True
        assert score_details["locator_compatibility"] == ["OFFICIAL_COMPATIBLE_LOCATOR"]
        assert locator["file"]
        assert locator["page"]
        assert locator["physical_page_index"] >= 0
        assert locator["bbox"] and len(locator["bbox"]) == 4
        assert locator["search_unit_id"]
        assert locator["document_version_id"]
        assert locator["source_basis"]
        assert locator["source_pdf_path"]
        assert locator["row_label"]
        assert locator["target_column"]
        assert locator["region_type"] in {"paragraph", "table_body"}
        assert locator["region_type"] != "table_row"
        if locator["region_type"] == "table_body":
            assert locator["bbox_granularity"] == "row_only"

    assert smoke["official_metric_execution_started"] is False
    assert smoke["status"] == "OFFICIAL_METRIC_PRE_EXECUTION_SMOKE_PASS_WITH_DIAGNOSTIC_WARNINGS"

    progress = PROGRESS_DOC.read_text(encoding="utf-8")
    current_progress = progress.split("## Short History", 1)[0]
    assert "SCORER_BACKEND_UNAVAILABLE" not in current_progress
    assert "official_answer_citation_agentic_loop_measurement_partial_gpu_index_live_generation" in current_progress
    assert "PDF candidate now has official-compatible source-bound locators" in current_progress
    assert "official_answer_citation_agentic_loop_run_v1" in current_progress
    assert "promotion_evidence=false" in current_progress
    assert "faiss_gpu_used=true" in current_progress


def test_pdf_candidate_locator_repair_artifacts_are_locked_to_current_report_only_state() -> None:
    first_run = read_json(REPORT_DIR / "official_answer_citation_metric_first_run_v1.json")
    input_config = read_json(REPORT_DIR / "official_metric_input_config_v1.json")
    xlsx_rows = read_jsonl(REPORT_DIR / "xlsx_answer_citation_runtime_precision_candidate_results_v1.jsonl")
    pdf_rows = read_jsonl(REPORT_DIR / "pdf_answer_citation_table_value_candidate_results_v1.jsonl")
    status_events = read_jsonl(REPORT_DIR / "rag_current_eval_status.jsonl")
    smoke = read_json(REPORT_DIR / "official_metric_pre_execution_smoke_report_v1.json")

    assert {path.name for path in REPORT_DIR.iterdir() if path.is_file()} == CURRENT_REPORT_FILENAMES
    assert not (REPORT_DIR / "rag_current_eval_status.md").exists()

    assert first_run["scored_count"] == 29
    assert first_run["failure_category_counts"] == {
        "CITATION_UNSUPPORTED": 11,
        "PARTIAL_OR_UNSUPPORTED": 10,
        "PASS": 8,
    }
    assert Counter(row["failure_category"] for row in first_run["row_results"]) == Counter(
        {"CITATION_UNSUPPORTED": 11, "PARTIAL_OR_UNSUPPORTED": 10, "PASS": 8}
    )
    first_run_by_id = {row["query_id"]: row for row in first_run["row_results"]}
    scorer_by_id = {
        row["query_id"]: row
        for row in read_jsonl(REPORT_DIR / "official_answer_citation_scorer_results_v1.jsonl")
    }
    config_query_ids = {row["query_id"] for row in input_config["candidate_manifest"]}
    assert set(first_run_by_id) == set(scorer_by_id) == config_query_ids
    assert {
        query_id: row["failure_category"]
        for query_id, row in first_run_by_id.items()
    } == {
        query_id: row["failure_category"]
        for query_id, row in scorer_by_id.items()
    }
    assert [first_run_by_id[query_id]["failure_category"] for query_id in REPAIRED_PDF_QUERY_IDS] == [
        "PARTIAL_OR_UNSUPPORTED",
        "PARTIAL_OR_UNSUPPORTED",
        "PARTIAL_OR_UNSUPPORTED",
    ]

    assert len(xlsx_rows) == 29
    assert len({row["query_id"] for row in xlsx_rows}) == 29
    assert Counter(row["failure_category"] for row in xlsx_rows) == Counter({"PASS": 26, "PARTIAL_OR_UNSUPPORTED": 3})
    assert all(row.get("promotion_evidence") is False for row in xlsx_rows)
    xlsx_by_id = {row["query_id"]: row for row in xlsx_rows}
    for query_id in REPAIRED_PDF_QUERY_IDS:
        row = xlsx_by_id[query_id]
        assert row["failure_category"] == "PARTIAL_OR_UNSUPPORTED"
        serialized_row = json.dumps(row, ensure_ascii=False)
        assert "table_value_candidate" not in serialized_row
        assert "OFFICIAL_COMPATIBLE_LOCATOR" not in serialized_row

    assert len(pdf_rows) == 29
    assert len({row["query_id"] for row in pdf_rows}) == 29
    assert Counter(row["failure_category"] for row in pdf_rows) == Counter({"PASS": 29})
    assert all(row.get("promotion_evidence") is False for row in pdf_rows)

    pdf_by_id = {row["query_id"]: row for row in pdf_rows}
    assert all(sum(1 for row in pdf_rows if row["query_id"] == query_id) == 1 for query_id in REPAIRED_PDF_QUERY_IDS)
    for query_id in REPAIRED_PDF_QUERY_IDS:
        row = pdf_by_id[query_id]
        score_details = row["score_details"]
        locator = row["generated_citations"][0]["citation_locator"]
        assert score_details["locator_compatibility"] == ["OFFICIAL_COMPATIBLE_LOCATOR"]
        assert score_details["expected_answer_used_for_generation"] is False
        assert score_details["supporting_evidence_used_for_generation"] is False
        assert score_details["gold_fields_used_for_generation"] is False
        assert locator["search_unit_id"].strip()
        assert locator["document_version_id"].strip()
        assert locator["source_pdf_path"].strip()
        assert locator["row_label"].strip()
        assert locator["target_column"].strip()
        assert locator["source_basis"].strip()
        assert numeric_bbox(locator["bbox"])
        if query_id == "gq_auto_010":
            assert locator["region_type"] == "paragraph"
            assert "bbox_granularity" not in locator
        else:
            assert locator["region_type"] == "table_body"
            assert locator["bbox_granularity"] == "row_only"

    status = next(event for event in reversed(status_events) if event.get("event_type") == "pdf_candidate_locator_hardening")
    assert status["event_type"] == "pdf_candidate_locator_hardening"
    assert status["current_focused_result"] == "68 passed, 0 skipped, 0 failed"
    assert status["pdf_candidate_result_count"] == {
        "failure_category_counts": {"PASS": 29},
        "rows": 29,
        "unique_query_ids": 29,
    }
    assert status["pdf_repaired_rows"] == 3
    assert set(status["locator_compatibility_after"]) == set(REPAIRED_PDF_QUERY_IDS)
    assert all(value == ["OFFICIAL_COMPATIBLE_LOCATOR"] for value in status["locator_compatibility_after"].values())
    assert status["guardrails"]["promotion_evidence"] is False
    assert status["guardrails"]["denominator_mutation"] is False
    assert status["guardrails"]["production_mutation"] is False

    assert smoke["official_metric_execution_started"] is False
    assert first_run["official_metric_execution_started"] is True


def test_readme_baseline_section_matches_immutable_first_run_and_separates_candidates() -> None:
    first_run = read_json(REPORT_DIR / "official_answer_citation_metric_first_run_v1.json")
    readme = README.read_text(encoding="utf-8")

    assert "## RAG Answer/Citation Metric Baseline" in readme
    assert "official_answer_citation_metric_first_run_v1" in readme
    assert "`SCORED_BASELINE_PARTIAL`" in readme
    assert f"`scored_count={first_run['scored_count']}`" in readme
    assert "`PASS=8`" in readme
    assert "`CITATION_UNSUPPORTED=11`" in readme
    assert "`PARTIAL_OR_UNSUPPORTED=10`" in readme
    assert "immutable baseline" in readme
    assert "XLSX runtime candidate" in readme
    assert "PASS=26/29" in readme
    assert "XLSX=19/19" in readme
    assert "PDF table/value candidate" in readme
    assert "PASS=29/29" in readme
    assert "must not be presented as the official first-run baseline" in readme
    assert "expected answers/supporting evidence are for scoring/audit only" in readme
    assert AGENTIC_RUN_ID in readme
    assert str(AGENTIC_RESULTS.relative_to(ROOT)).replace("\\", "/") in readme


def test_agentic_loop_measurement_artifacts_are_separate_fail_closed_current_run() -> None:
    first_run = read_json(REPORT_DIR / "official_answer_citation_metric_first_run_v1.json")
    input_config = read_json(REPORT_DIR / "official_metric_input_config_v1.json")
    summary = read_json(AGENTIC_SUMMARY_JSON)
    results = read_jsonl(AGENTIC_RESULTS)
    summary_md = AGENTIC_SUMMARY_MD.read_text(encoding="utf-8")
    status_events = read_jsonl(REPORT_DIR / "rag_current_eval_status.jsonl")

    assert summary["run_id"] == AGENTIC_RUN_ID
    assert summary["baseline_reference"]["run_id"] == "official_answer_citation_metric_first_run_v1"
    assert summary["baseline_reference"]["status_detail"] == "SCORED_BASELINE_PARTIAL"
    assert summary["artifact_provenance"]["immutable_first_run_baseline_overwritten"] is False
    assert summary["artifact_provenance"]["report_only_candidates_promoted"] is False
    assert summary["denominator_count"] == 29
    assert summary["result_count"] == 29
    assert summary["unique_query_id_count"] == 29
    assert summary["validation"]["ok"] is True
    assert summary["pipeline_decision"]["registry_application_report_required"] is False
    assert summary["pipeline_decision"]["registry_application_fallback_used"] is True
    assert summary["agentic_loop"]["implemented"] is True
    assert summary["agentic_loop"]["enabled"] is True
    assert summary["agentic_loop"]["backend"] in {"legacy", "graph"}
    assert summary["non_production_rag_index_dependency"]["canonical_path"] == "ai/eval/indexes/rag-data"
    assert summary["non_production_rag_index_dependency"]["worker_relative_path"] == "eval/indexes/rag-data"
    assert summary["non_production_rag_index_dependency"]["production_index_path_used"] is False
    assert summary["non_production_rag_index_dependency"]["build_command"] == (
        "cd ai && AIPIPELINE_WORKER_RAG_FAISS_BUILD_DEVICE=cuda "
        "python -m scripts.build_rag_index --fixture all "
        "--index-version official-answer-citation-agentic-loop-v1-nonprod-fixture-all"
    )
    assert summary["non_production_rag_index_dependency"]["build_metadata"] == {
        "faiss_build_device_requested": "cuda",
        "faiss_gpu_count": 1,
        "faiss_gpu_device": 0,
        "faiss_gpu_used": True,
    }
    assert summary["infrastructure_blocker"]["model_quality_regression"] is False
    if summary["failure_counts"] == {"GENERATION_PIPELINE_UNAVAILABLE": 29}:
        assert summary["status"] == "BLOCKED_ACTUAL_GENERATION_PIPELINE_UNAVAILABLE"
        assert summary["measurement_classification"] == "diagnostic_actual_generation_blocked_pipeline_unavailable"
        assert summary["scored_count"] == 0
        assert summary["pass_count"] == 0
        assert summary["agentic_loop"]["executed"] is False
        assert summary["infrastructure_blocker"]["category"] == "NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING"
    else:
        assert summary["status"] in {"PASS", "BLOCKED_OR_PARTIAL"}
        assert summary["measurement_classification"] == "official_next_run_measurement"
        assert summary["agentic_loop"]["actual_generation_pipeline_available"] is True
        assert summary["agentic_loop"]["executed"] is True
        assert "GENERATION_PIPELINE_UNAVAILABLE" not in summary["failure_counts"]
        assert all(
            row["generated_answer"] or row["generated_citations"] or row["failure_category"] != "GENERATION_PIPELINE_UNAVAILABLE"
            for row in results
        )
    assert summary["local_llm_used"] is False
    assert summary["local_gpu_used"] is True
    assert summary["guardrails"]["promotion_evidence"] is False
    assert summary["guardrails"]["generation_used_expected_answer"] is False
    assert summary["guardrails"]["generation_used_supporting_evidence"] is False
    assert summary["guardrails"]["denominator_mutation"] is False
    assert summary["guardrails"]["gold_mutation"] is False
    assert summary["guardrails"]["production_mutation"] is False
    assert summary["comparison_to_baseline"]["pass_delta"] == -7
    assert summary["comparison_to_baseline"]["per_track_pass_delta"] == {
        "pdf_business_ocr_mm": 0,
        "text_namu_v2_1": -6,
        "xlsx_business_structured": -1,
    }

    official_query_ids = {row["query_id"] for row in input_config["candidate_manifest"]}
    assert len(results) == 29
    assert {row["query_id"] for row in results} == official_query_ids
    assert all(row["run_id"] == AGENTIC_RUN_ID for row in results)
    assert all(row["promotion_evidence"] is False for row in results)
    assert all(row["generation_used_expected_answer"] is False for row in results)
    assert all(row["generation_used_supporting_evidence"] is False for row in results)
    assert all(row["generation_used_gold_fields"] is False for row in results)
    assert all(row["agentic_loop_enabled"] is True for row in results)
    assert all(row["local_llm_used"] is False for row in results)
    assert all(row["local_gpu_used"] is True for row in results)
    assert all("expected_answer" not in row for row in results)
    assert all("supporting_evidence" not in row for row in results)
    if summary["failure_counts"] == {"GENERATION_PIPELINE_UNAVAILABLE": 29}:
        assert all(row["agentic_loop_executed"] is False for row in results)
        assert all(row["failure_category"] == "GENERATION_PIPELINE_UNAVAILABLE" for row in results)
        assert all(row["infrastructure_blocker_category"] == "NON_PRODUCTION_RAG_INDEX_ARTIFACT_MISSING" for row in results)
    else:
        assert any(row["agentic_loop_executed"] is True for row in results)
        assert all(row["failure_category"] != "GENERATION_PIPELINE_UNAVAILABLE" for row in results)

    assert "official_answer_citation_agentic_loop_run_v1" in summary_md
    assert "model quality regression: `false`" in summary_md
    assert "FAISS GPU used for build: `true`" in summary_md
    assert "official first-run baseline was not overwritten" in summary_md
    latest = next(
        event
        for event in reversed(status_events)
        if event.get("event_type") == "official_answer_citation_agentic_loop_measurement"
    )
    assert latest["event_type"] == "official_answer_citation_agentic_loop_measurement"
    assert latest["run_id"] == AGENTIC_RUN_ID
    assert latest["result_count"] == 29
    assert latest["unique_query_id_count"] == 29
    assert latest["pass_count"] == summary["pass_count"]
    assert latest["non_production_rag_index_dependency"]["build_metadata"]["faiss_gpu_used"] is True
    assert latest["promotion_evidence"] is False
    assert first_run["failure_category_counts"] == {
        "CITATION_UNSUPPORTED": 11,
        "PARTIAL_OR_UNSUPPORTED": 10,
        "PASS": 8,
    }


def test_agentic_available_pipeline_row_exception_is_specific_not_pipeline_unavailable() -> None:
    sys.path.insert(0, str(ROOT / "ai" / "scripts"))
    import rag_official_answer_citation_agentic_loop_run_v1 as runner

    class BoomRetriever:
        def retrieve(self, _query: str) -> object:
            raise RuntimeError("synthetic retriever failure after index availability")

    args = SimpleNamespace(
        agent_loop_backend="legacy",
        agent_max_iter=1,
        agent_max_total_ms=1000,
        agent_max_llm_tokens=1000,
        agent_min_stop_confidence=0.0,
    )
    rows = [
        {
            "query_id": "q-row-failure",
            "track": "text_namu_v2_1",
            "question": "실패 분기 확인용 질문",
            "expected_answer": "sentinel answer",
            "supporting_evidence": "sentinel evidence",
        }
    ]

    out = runner.execute_agentic_generation_rows(rows, args, {"_retriever": BoomRetriever()})

    assert len(out) == 1
    row = out[0]
    assert row["failure_category"] == runner.AGENTIC_GENERATION_ROW_FAILED
    assert row["failure_category"] != runner.GENERATION_PIPELINE_UNAVAILABLE
    assert row["agentic_loop_enabled"] is True
    assert row["agentic_loop_executed"] is True
    assert row["scoring_attempted"] is False
    assert row["generated_answer"] == ""
    assert row["generated_citations"] == []
    assert row["retrieved_evidence"] == []
    assert row["infrastructure_blocker_category"] is None


def test_faiss_cuda_build_fails_closed_when_gpu_api_unavailable(
    tmp_path, monkeypatch
) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from app.capabilities.rag import faiss_index as faiss_index_module
    from app.capabilities.rag.faiss_index import FaissIndex

    monkeypatch.setattr(faiss_index_module, "_faiss_gpu_ready", lambda: False)
    monkeypatch.setattr(faiss_index_module, "_faiss_gpu_count", lambda: 0)
    index = FaissIndex(tmp_path / "idx", build_device="cuda")

    with pytest.raises(RuntimeError, match="FAISS GPU build requested"):
        index.build(
            np.ones((2, 4), dtype=np.float32),
            index_version="gpu-required",
            embedding_model="hashing",
        )


def test_faiss_cuda_build_records_gpu_metadata(tmp_path, monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from app.capabilities.rag import faiss_index as faiss_index_module
    from app.capabilities.rag.faiss_index import FaissIndex

    calls: list[tuple[str, int | None]] = []

    class _FakeGpuIndex:
        def __init__(self, cpu_index):
            self.cpu_index = cpu_index

        def add(self, vectors):
            calls.append(("add", int(vectors.shape[0])))
            self.cpu_index.add(vectors)

    def _to_gpu(_resources, device, cpu_index):
        calls.append(("to_gpu", int(device)))
        return _FakeGpuIndex(cpu_index)

    def _to_cpu(gpu_index):
        calls.append(("to_cpu", None))
        return gpu_index.cpu_index

    monkeypatch.setattr(faiss_index_module, "_faiss_gpu_ready", lambda: True)
    monkeypatch.setattr(faiss_index_module, "_faiss_gpu_count", lambda: 1)
    monkeypatch.setattr(
        faiss_index_module.faiss,
        "StandardGpuResources",
        lambda: object(),
        raising=False,
    )
    monkeypatch.setattr(
        faiss_index_module.faiss,
        "index_cpu_to_gpu",
        _to_gpu,
        raising=False,
    )
    monkeypatch.setattr(
        faiss_index_module.faiss,
        "index_gpu_to_cpu",
        _to_cpu,
        raising=False,
    )

    index = FaissIndex(tmp_path / "idx", build_device="cuda")
    index.build(
        np.ones((2, 4), dtype=np.float32),
        index_version="gpu-used",
        embedding_model="hashing",
    )

    payload = json.loads((tmp_path / "idx" / "build.json").read_text())
    assert payload["faiss_build_device_requested"] == "cuda"
    assert payload["faiss_gpu_used"] is True
    assert payload["faiss_gpu_count"] == 1
    assert payload["faiss_gpu_device"] == 0
    assert calls == [("to_gpu", 0), ("add", 2), ("to_cpu", None)]


def test_sentence_transformer_embedder_exposes_configured_max_seq_length_for_ingest_manifest() -> None:
    sys.path.insert(0, str(ROOT / "ai"))
    from app.capabilities.rag.embeddings import SentenceTransformerEmbedder

    embedder = SentenceTransformerEmbedder("BAAI/bge-m3", max_seq_length=1024)

    assert embedder.max_seq_length == 1024


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def numeric_bbox(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    try:
        return all(isinstance(float(item), float) for item in value)
    except (TypeError, ValueError):
        return False
