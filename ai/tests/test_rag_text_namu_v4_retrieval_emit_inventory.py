from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_text_namu_v4_retrieval_emit_inventory.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


inventory = load_module(SCRIPT_PATH, "rag_text_namu_v4_retrieval_emit_inventory_for_tests")


def test_inventory_accepts_reusable_gold_seed_emit(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    gold = write_gold(tmp_path)
    r3_report = write_r3_report(tmp_path, status="PASSED")
    emit = tmp_path / "namu_v4_r4_emit.jsonl"
    write_jsonl(
        emit,
        [
            emit_row("gold_seed_0001", "chunk-1", score=0.9),
            emit_row("gold_seed_0002", "chunk-2", score=0.8),
        ],
    )

    report = inventory.build_inventory(
        gold=gold,
        corpus_dir=corpus,
        r3_validation_report=r3_report,
        candidate_paths=[emit],
    )

    assert report["status"] == "REUSABLE_EXISTING_EMIT"
    assert report["decision"] == "USE_EXISTING_EMIT"
    assert report["retrieval_metrics_computed"] is False
    assert report["promotion_evidence"] is False
    assert report["candidate_summaries"][0]["query_id_match_gold_csv"] is True
    assert report["candidate_summaries"][0]["missing_chunk_resolution_count"] == 0
    assert report["candidate_summaries"][0]["chunk_doc_id_page_join_missing_count"] == 0
    assert report["candidate_summaries"][0]["context_traceable_to_chunk_text_count"] == 2


def test_inventory_rejects_phase7_query_id_mismatch_emit(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    gold = write_gold(tmp_path)
    r3_report = write_r3_report(tmp_path, status="PASSED")
    emit_dir = tmp_path / "human_gold_seed_50_tuning"
    emit_dir.mkdir()
    emit = emit_dir / "retrieval_cand_title_section_top10_gold.jsonl"
    write_jsonl(
        emit,
        [
            emit_row("v4-llm-silver-010", "chunk-1", score=0.9),
            emit_row("v4-llm-silver-013", "chunk-2", score=0.8),
        ],
    )

    report = inventory.build_inventory(
        gold=gold,
        corpus_dir=corpus,
        r3_validation_report=r3_report,
        candidate_paths=[emit],
    )

    assert report["status"] == "NO_REUSABLE_EXISTING_EMIT"
    assert report["decision"] == "RUN_FRESH_DIAGNOSTIC_RETRIEVAL"
    assert report["r5_entry"]["status"] == "READY_REQUIRES_FRESH_DIAGNOSTIC_RETRIEVAL"
    reasons = report["candidate_summaries"][0]["non_reusable_reasons"]
    assert "query_id_mismatch" in reasons
    assert "phase7_tuning_or_sanity_artifact" in reasons


def test_inventory_rejects_broken_chunk_page_and_context_gates(tmp_path: Path):
    corpus = tmp_path / "namu-v4-structured-combined"
    corpus.mkdir()
    write_jsonl(
        corpus / "pages_v4.jsonl",
        [
            {"page_id": "page-1", "page_title": "Page One"},
            {"page_id": "page-2", "page_title": "Page Two"},
        ],
    )
    write_jsonl(
        corpus / "rag_chunks.jsonl",
        [
            {"chunk_id": "empty-text", "doc_id": "page-1", "chunk_text": ""},
            {"chunk_id": "orphan-page", "doc_id": "missing-page", "chunk_text": "raw"},
        ],
    )
    gold = write_gold(tmp_path)
    r3_report = write_r3_report(tmp_path, status="PASSED")
    emit = tmp_path / "namu_v4_r4_broken_emit.jsonl"
    write_jsonl(
        emit,
        [
            {
                "variant": "r4_test_retriever",
                "query_id": "gold_seed_0001",
                "docs": [
                    {"rank": 1, "chunk_id": "missing-chunk", "score": 0.9},
                    {"rank": 2, "chunk_id": "empty-text", "score": 0.8},
                ],
            },
            emit_row("gold_seed_0002", "orphan-page", score=0.7),
        ],
    )

    report = inventory.build_inventory(
        gold=gold,
        corpus_dir=corpus,
        r3_validation_report=r3_report,
        candidate_paths=[emit],
    )

    assert report["status"] == "NO_REUSABLE_EXISTING_EMIT"
    summary = report["candidate_summaries"][0]
    assert summary["query_id_match_gold_csv"] is True
    assert summary["missing_chunk_resolution_count"] == 1
    assert summary["chunk_doc_id_page_join_missing_count"] == 1
    assert summary["context_traceable_to_chunk_text_count"] == 1
    assert "missing_chunk_resolution" in summary["non_reusable_reasons"]
    assert "chunk_doc_id_page_join_missing" in summary["non_reusable_reasons"]
    assert "context_not_traceable_to_rag_chunks_chunk_text" in summary["non_reusable_reasons"]


def test_inventory_reports_no_existing_emit_as_fresh_run_required(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    gold = write_gold(tmp_path)
    r3_report = write_r3_report(tmp_path, status="PASSED")

    report = inventory.build_inventory(
        gold=gold,
        corpus_dir=corpus,
        r3_validation_report=r3_report,
        candidate_paths=[],
    )

    assert report["status"] == "NO_EXISTING_EMIT"
    assert report["decision"] == "RUN_FRESH_DIAGNOSTIC_RETRIEVAL"
    assert report["fresh_retrieval_required"] is True
    assert report["retrieval_metrics_computed"] is False


def test_inventory_blocks_when_r3_is_not_passed(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    gold = write_gold(tmp_path)
    r3_report = write_r3_report(tmp_path, status="FAILED")

    report = inventory.build_inventory(
        gold=gold,
        corpus_dir=corpus,
        r3_validation_report=r3_report,
        candidate_paths=[],
    )

    assert report["status"] == "BLOCKED_R3_NOT_PASSED"
    assert report["decision"] == "KEEP_R5_BLOCKED"
    assert report["r5_entry"]["allowed"] is False


def test_discovery_includes_rag_ingestion_diagnostics_but_excludes_r5_outputs(tmp_path: Path):
    phase7 = tmp_path / "phase7"
    rag_ingestion = tmp_path / "rag-ingestion"
    phase7.mkdir()
    rag_ingestion.mkdir()
    phase7_emit = phase7 / "retrieval_cand_title_section_top10_gold.jsonl"
    b_app_report = rag_ingestion / "rag_text_retrieval_diagnostic_report.json"
    xlsx_report = rag_ingestion / "rag_retrieval_eval_xlsx_vector_diagnostic_report.json"
    r4_report = rag_ingestion / "rag_text_namu_v4_retrieval_emit_inventory_report.json"
    r5_emit = rag_ingestion / "rag_text_namu_v4_retrieval_emit.jsonl"
    r5_report = rag_ingestion / "rag_text_namu_v4_retrieval_diagnostic_report.json"
    for path in [phase7_emit, b_app_report, xlsx_report, r4_report, r5_emit, r5_report]:
        path.write_text("{}\n", encoding="utf-8")

    discovered = inventory.discover_candidate_paths(
        [phase7, rag_ingestion],
        output_report=r4_report,
    )

    names = {path.name for path in discovered}
    assert phase7_emit.name in names
    assert b_app_report.name in names
    assert xlsx_report.name in names
    assert r4_report.name not in names
    assert r5_emit.name not in names
    assert r5_report.name not in names


def write_corpus(tmp_path: Path) -> Path:
    corpus = tmp_path / "namu-v4-structured-combined"
    corpus.mkdir()
    write_jsonl(
        corpus / "pages_v4.jsonl",
        [
            {"page_id": "page-1", "page_title": "Page One"},
            {"page_id": "page-2", "page_title": "Page Two"},
        ],
    )
    write_jsonl(
        corpus / "rag_chunks.jsonl",
        [
            {"chunk_id": "chunk-1", "doc_id": "page-1", "chunk_text": "raw one"},
            {"chunk_id": "chunk-2", "doc_id": "page-2", "chunk_text": "raw two"},
        ],
    )
    return corpus


def write_gold(tmp_path: Path) -> Path:
    path = tmp_path / "gold.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["query_id", "query"])
        writer.writeheader()
        writer.writerow({"query_id": "gold_seed_0001", "query": "q1"})
        writer.writerow({"query_id": "gold_seed_0002", "query": "q2"})
    return path


def write_r3_report(tmp_path: Path, *, status: str) -> Path:
    path = tmp_path / "r3.json"
    path.write_text(json.dumps({"status": status}), encoding="utf-8")
    return path


def emit_row(query_id: str, chunk_id: str, *, score: float) -> dict[str, object]:
    return {
        "variant": "r4_test_retriever",
        "query_id": query_id,
        "query": "query",
        "docs": [
            {
                "rank": 1,
                "chunk_id": chunk_id,
                "score": score,
                "context": "raw text from emit",
            }
        ],
    }


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
