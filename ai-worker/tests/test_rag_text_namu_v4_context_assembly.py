from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_text_namu_v4_context_assembly.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


assembly = load_module(SCRIPT_PATH, "rag_text_namu_v4_context_assembly_for_tests")


def test_entry_gate_passes_with_r5_fresh_emit_and_positive_denominator(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = assembly.run_context_assembly(**paths)

    assert report["status"] == "PASS"
    assert report["promotion_evidence"] is False
    assert report["evidence_role"] == "diagnostic"
    assert report["positive_denominator_count"] == 47
    assert report["needs_review_excluded_count"] == 3
    assert report["r5_fresh_emit_path"].endswith("rag_text_namu_v4_retrieval_emit.jsonl")
    assert report["retrieval_emit_reuse"]["r5_fresh_emit_only"] is True
    assert report["retrieval_emit_reuse"]["existing_emit_reused"] is False
    assert report["r7_ready"] is True
    assert paths["context_emit"].exists()


def test_needs_review_rows_are_excluded_from_positive_denominator(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = assembly.run_context_assembly(**paths)
    rows = read_jsonl(paths["context_emit"])
    excluded = [row for row in rows if not row["denominator_included"]]

    assert report["needs_review_query_ids"] == ["gold_seed_0048", "gold_seed_0049", "gold_seed_0050"]
    assert len(excluded) == 3
    assert {row["taxonomy"] for row in excluded} == {"excluded_needs_review"}


def test_context_uses_corpus_chunk_text_only(tmp_path: Path):
    paths = write_fixture_bundle(
        tmp_path,
        corpus_chunk_text="CORPUS RAW TEXT",
        emit_chunk_text="EMIT TEXT MUST NOT BE USED",
    )

    report = assembly.run_context_assembly(**paths)
    rows = read_jsonl(paths["context_emit"])

    assert report["context_field"] == "chunk_text"
    assert rows[0]["contexts"][0]["text"] == "CORPUS RAW TEXT"
    assert "EMIT TEXT MUST NOT BE USED" not in json.dumps(rows[0], ensure_ascii=False)
    assert "embedding_text" not in rows[0]["contexts"][0]
    assert "text_for_embedding" not in rows[0]["contexts"][0]
    assert "debug_text" not in rows[0]["contexts"][0]


def test_disallowed_context_field_fails(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = assembly.run_context_assembly(**paths, context_field="embedding_text")

    assert report["status"] == "FAIL"
    assert "context_field must be chunk_text, got embedding_text" in report["blockers"]
    with pytest.raises(ValueError):
        assembly.select_context_text({"chunk_text": "ok", "embedding_text": "bad"}, "embedding_text")


def test_top_k_result_joins_to_corpus_chunk_id(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    assembly.run_context_assembly(**paths)
    rows = read_jsonl(paths["context_emit"])

    assert rows[0]["contexts"][0]["chunk_id"] == "chunk-alpha"
    assert rows[0]["contexts"][0]["doc_id"] == "page-alpha"
    assert rows[0]["contexts"][0]["text"] == "alpha corpus evidence"
    assert rows[0]["taxonomy"] == "expected_context_present"


def test_missing_corpus_chunk_id_is_reported_in_taxonomy(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path, emit_doc_builder=lambda index: emit_doc("missing-chunk", "page-alpha"))

    report = assembly.run_context_assembly(**paths)
    rows = read_jsonl(paths["context_emit"])

    assert report["status"] == "FAIL"
    assert report["missing_corpus_chunk_join_count"] == 47
    assert rows[0]["taxonomy"] == "missing_corpus_chunk_join"
    assert rows[0]["missing_corpus_chunk_ids"] == ["missing-chunk"]


def test_missing_expected_source_and_chunk_are_separated(tmp_path: Path):
    def builder(index: int) -> dict[str, object]:
        if index == 1:
            return emit_doc("chunk-beta", "page-beta")
        if index == 2:
            return emit_doc("chunk-alpha-other", "page-alpha")
        return emit_doc("chunk-alpha", "page-alpha")

    paths = write_fixture_bundle(tmp_path, emit_doc_builder=builder, include_alpha_other=True)

    report = assembly.run_context_assembly(**paths)
    rows = read_jsonl(paths["context_emit"])

    assert report["status"] == "PASS_WITH_WARNINGS"
    assert report["missing_expected_source_count"] == 1
    assert report["missing_expected_chunk_count"] == 1
    assert rows[0]["taxonomy"] == "missing_expected_source"
    assert rows[1]["taxonomy"] == "missing_expected_chunk"


def test_duplicate_chunk_id_is_deduped_by_first_rank(tmp_path: Path):
    def builder(index: int) -> list[dict[str, object]]:
        return [
            emit_doc("chunk-alpha", "page-alpha", rank=1, score=0.9),
            emit_doc("chunk-alpha", "page-alpha", rank=2, score=0.8),
        ]

    paths = write_fixture_bundle(tmp_path, emit_doc_builder=builder)

    report = assembly.run_context_assembly(**paths)
    rows = read_jsonl(paths["context_emit"])

    assert report["status"] == "PASS_WITH_WARNINGS"
    assert report["duplicate_chunk_dedup_count"] == 50
    assert rows[0]["context_count"] == 1
    assert rows[0]["contexts"][0]["rank"] == 1


def test_c4_related_paths_are_not_touched_or_required(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = assembly.run_context_assembly(**paths)

    assert report["parallel_with_track_c_c4"] is True
    assert report["c4_files_touched"] is False
    assert report["db_mutation_run"] is False
    assert report["indexing_run"] is False
    assert report["worker_claim_run"] is False
    forbidden_blob = json.dumps(report["c4_isolation"]["forbidden_path_patterns"])
    assert "pdf_candidate_" in forbidden_blob
    assert "track-c-pdf-embedding-preparation" in forbidden_blob
    assert "pdf_candidate_" not in report["context_emit_path"]
    assert "track-c-pdf-embedding-preparation" not in report["context_emit_path"]


def write_fixture_bundle(
    tmp_path: Path,
    *,
    corpus_chunk_text: str = "alpha corpus evidence",
    emit_chunk_text: str = "alpha emit text",
    emit_doc_builder=None,
    include_alpha_other: bool = False,
) -> dict[str, Path]:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    chunks = [
        {
            "chunk_id": "chunk-alpha",
            "doc_id": "page-alpha",
            "display_title": "Alpha",
            "section_id": "section-alpha",
            "section_path": ["Overview"],
            "chunk_text": corpus_chunk_text,
            "embedding_text": "EMBEDDING MUST NOT LEAK",
            "text_for_embedding": "TEXT FOR EMBEDDING MUST NOT LEAK",
            "debug_text": "DEBUG MUST NOT LEAK",
        },
        {
            "chunk_id": "chunk-beta",
            "doc_id": "page-beta",
            "display_title": "Beta",
            "section_id": "section-beta",
            "section_path": ["Overview"],
            "chunk_text": "beta corpus evidence",
            "embedding_text": "beta embedding",
        },
    ]
    if include_alpha_other:
        chunks.append(
            {
                "chunk_id": "chunk-alpha-other",
                "doc_id": "page-alpha",
                "display_title": "Alpha",
                "section_id": "section-other",
                "section_path": ["Other"],
                "chunk_text": "same source but not expected chunk",
            }
        )
    write_jsonl(corpus_dir / "rag_chunks.jsonl", chunks)

    gold = tmp_path / "gold_queries_text_namu_v4_v0.csv"
    write_gold(gold)
    corpus_report = tmp_path / "rag_text_namu_v4_corpus_inventory_report.json"
    gold_validator_report = tmp_path / "rag_text_namu_v4_gold_validate_report.json"
    r5_emit = tmp_path / "rag_text_namu_v4_retrieval_emit.jsonl"
    r5_report = tmp_path / "rag_text_namu_v4_retrieval_diagnostic_report.json"
    context_emit = tmp_path / "rag_text_namu_v4_context_assembly.jsonl"
    report = tmp_path / "rag_text_namu_v4_context_assembly_report.json"

    write_json(
        corpus_report,
        {
            "status": "PASS",
            "files": {
                "rag_chunks.jsonl": {
                    "path": str((corpus_dir / "rag_chunks.jsonl").resolve()),
                    "exists": True,
                }
            },
        },
    )
    write_json(gold_validator_report, {"status": "PASSED"})
    emit_rows = [
        retrieval_emit_row(
            index,
            emit_docs_for(index, emit_doc_builder, emit_chunk_text=emit_chunk_text),
            label_status="needs_review" if index >= 48 else "bound",
            denominator_included=index < 48,
        )
        for index in range(1, 51)
    ]
    write_jsonl(r5_emit, emit_rows)
    write_json(
        r5_report,
        {
            "status": "PASS_WITH_WARNINGS",
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "fresh_emit_path": str(r5_emit.resolve()),
            "fresh_emit_sha256": assembly.sha256_file(r5_emit),
            "reused_emit": False,
            "existing_emit_reused": False,
            "positive_denominator_count": 47,
            "needs_review_excluded_count": 3,
            "retrieval_metrics_computed": True,
            "llm_answer_eval_run": False,
            "citation_eval_run": False,
            "promotion_run": False,
            "top_k": 10,
            "wrong_source_count": 10,
            "missing_expected_chunk_count": 18,
            "empty_result_count": 0,
            "retrieval_error_count": 0,
        },
    )
    return {
        "gold": gold,
        "corpus_inventory_report": corpus_report,
        "gold_validator_report": gold_validator_report,
        "r5_fresh_emit": r5_emit,
        "r5_report": r5_report,
        "context_emit": context_emit,
        "report_path": report,
    }


def emit_docs_for(index: int, builder, *, emit_chunk_text: str) -> list[dict[str, object]]:
    if builder is None:
        return [emit_doc("chunk-alpha", "page-alpha", chunk_text=emit_chunk_text)]
    built = builder(index)
    if isinstance(built, list):
        return built
    return [built]


def retrieval_emit_row(
    index: int,
    docs: list[dict[str, object]],
    *,
    label_status: str,
    denominator_included: bool,
) -> dict[str, object]:
    return {
        "schema_version": "rag_text_namu_v4_retrieval_emit_v1",
        "query_id": f"gold_seed_{index:04d}",
        "query": "alpha query",
        "bucket": "text_policy_question" if label_status == "needs_review" else "text_fact_lookup",
        "label_status": label_status,
        "allowed_abstain": False,
        "denominator_included": denominator_included,
        "denominator_exclusion_reason": None if denominator_included else "label_status=needs_review",
        "top_k": 10,
        "docs": docs,
        "retrieval_error": None,
    }


def emit_doc(
    chunk_id: str,
    page_id: str,
    *,
    rank: int = 1,
    score: float = 1.0,
    chunk_text: str = "emit text",
) -> dict[str, object]:
    return {
        "rank": rank,
        "chunk_id": chunk_id,
        "doc_id": page_id,
        "page_id": page_id,
        "section_id": "section-alpha" if page_id == "page-alpha" else "section-beta",
        "section_path": ["Overview"],
        "title": "Title",
        "score": score,
        "context": "emit context must not be used",
        "chunk_text": chunk_text,
    }


def write_gold(path: Path) -> None:
    fieldnames = [
        "query_id",
        "bucket",
        "query",
        "expected_page_ids",
        "expected_section_ids",
        "expected_chunk_ids",
        "expected_answer_summary",
        "must_contain_terms",
        "must_not_contain_terms",
        "allowed_abstain",
        "answer_type",
        "label_status",
        "source_dataset",
        "notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(1, 48):
            writer.writerow(gold_row(index, label_status="bound"))
        for index in range(48, 51):
            writer.writerow(gold_row(index, label_status="needs_review"))


def gold_row(index: int, *, label_status: str) -> dict[str, object]:
    return {
        "query_id": f"gold_seed_{index:04d}",
        "bucket": "text_policy_question" if label_status == "needs_review" else "text_fact_lookup",
        "query": "alpha query",
        "expected_page_ids": "page-alpha",
        "expected_section_ids": "section-alpha",
        "expected_chunk_ids": "chunk-alpha",
        "expected_answer_summary": "alpha answer",
        "must_contain_terms": "",
        "must_not_contain_terms": "",
        "allowed_abstain": "false",
        "answer_type": "short_fact",
        "label_status": label_status,
        "source_dataset": "fixture",
        "notes": "",
    }


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
