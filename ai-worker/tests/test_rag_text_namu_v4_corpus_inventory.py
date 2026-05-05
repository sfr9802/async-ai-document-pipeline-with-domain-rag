from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai-worker" / "scripts" / "rag_text_namu_v4_corpus_inventory.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_text_namu_v4_corpus_inventory_for_tests", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


inventory = load_module()


def test_build_report_passes_with_rag_chunks_chunk_text_and_doc_id(tmp_path: Path):
    corpus = write_valid_corpus(tmp_path)

    report = inventory.build_report(corpus)

    assert report["status"] == "PASS"
    assert report["promotion_evidence"] is False
    assert report["evidence_role"] == "diagnostic"
    assert report["files"]["rag_chunks.jsonl"]["row_count"] == 2
    assert report["completion_criteria"]["hardened_auxiliary_files_present"] is True
    assert report["completion_criteria"]["validation_report_counts_match_jsonl"] is True
    assert report["completion_criteria"]["split_manifest_doc_ids_match_pages_v4"] is True
    assert report["completion_criteria"]["split_manifest_doc_counts_clean"] is True
    assert report["completion_criteria"]["split_manifest_metadata_expected"] is True
    assert report["completion_criteria"]["raw_context_trust_counters_clean"] is True
    assert report["rag_chunks_schema"]["chunk_id_unique"] is True
    assert report["rag_chunks_schema"]["raw_context_field"] == "chunk_text"
    assert report["rag_chunks_schema"]["empty_chunk_text_count"] == 0
    assert report["rag_chunks_schema"]["missing_page_id_count"] == 2
    assert report["rag_chunks_schema"]["missing_doc_id_count"] == 0
    assert report["rag_chunks_schema"]["page_identifier_field"] == "doc_id"
    assert report["rag_chunks_schema"]["page_identity_complete"] is True
    assert report["rag_chunks_schema"]["page_identity_matches_pages_v4"] is True
    assert report["rag_chunks_schema"]["page_identity_missing_from_pages_v4_count"] == 0
    assert report["context_policy"]["selected_disallowed_context_field"] is False
    assert report["context_policy"]["disallowed_fields_present"]["embedding_text"] is True


def test_build_report_accepts_text_fallback_when_chunk_text_absent(tmp_path: Path):
    corpus = write_valid_corpus(
        tmp_path,
        rag_rows=[
            {
                "chunk_id": "rag-1",
                "doc_id": "page-1",
                "title": "Title",
                "section_path": ["개요"],
                "text": "Raw text fallback",
                "embedding_text": "Title\nRaw text fallback",
            }
        ],
    )

    report = inventory.build_report(corpus)

    assert report["status"] == "PASS"
    assert report["rag_chunks_schema"]["raw_context_field"] == "text"
    assert report["rag_chunks_schema"]["text_fallback_accepted"] is True
    assert report["rag_chunks_schema"]["empty_raw_context_count"] == 0
    assert report["context_policy"]["selected_context_field_allowed"] is True


def test_build_report_fails_for_empty_chunk_text(tmp_path: Path):
    corpus = write_valid_corpus(
        tmp_path,
        rag_rows=[
            {
                "chunk_id": "rag-1",
                "doc_id": "page-1",
                "title": "Title",
                "section_path": ["개요"],
                "chunk_text": "",
                "embedding_text": "Title only",
            }
        ],
    )

    report = inventory.build_report(corpus)

    assert report["status"] == "FAIL"
    assert "rag_chunks.jsonl has empty raw context text rows" in report["blockers"]
    assert report["rag_chunks_schema"]["empty_chunk_text_count"] == 1


def test_build_report_fails_for_duplicate_chunk_ids(tmp_path: Path):
    corpus = write_valid_corpus(
        tmp_path,
        rag_rows=[
            {
                "chunk_id": "dup",
                "doc_id": "page-1",
                "title": "Title",
                "section_path": ["개요"],
                "chunk_text": "first",
            },
            {
                "chunk_id": "dup",
                "doc_id": "page-2",
                "title": "Title 2",
                "section_path": ["개요"],
                "chunk_text": "second",
            },
        ],
    )

    report = inventory.build_report(corpus)

    assert report["status"] == "FAIL"
    assert "rag_chunks.jsonl chunk_id values are missing or duplicated" in report["blockers"]
    assert report["rag_chunks_schema"]["duplicate_chunk_id_count"] == 1


def test_build_report_fails_when_rag_chunks_have_no_page_or_doc_identity(tmp_path: Path):
    corpus = write_valid_corpus(
        tmp_path,
        rag_rows=[
            {
                "chunk_id": "rag-1",
                "title": "Title",
                "section_path": ["개요"],
                "chunk_text": "Raw chunk text",
            }
        ],
    )

    report = inventory.build_report(corpus)

    assert report["status"] == "FAIL"
    assert "rag_chunks.jsonl has no complete page_id or doc_id identity" in report["blockers"]
    assert report["rag_chunks_schema"]["page_identifier_field"] is None
    assert report["rag_chunks_schema"]["page_identity_complete"] is False


def test_build_report_fails_when_doc_id_is_not_in_pages_v4(tmp_path: Path):
    corpus = write_valid_corpus(
        tmp_path,
        rag_rows=[
            {
                "chunk_id": "rag-1",
                "doc_id": "missing-page",
                "title": "Title",
                "section_path": ["개요"],
                "chunk_text": "Raw chunk text",
            }
        ],
    )

    report = inventory.build_report(corpus)

    assert report["status"] == "FAIL"
    assert "rag_chunks.jsonl page/document ids are not present in pages_v4.page_id" in report["blockers"]
    assert report["rag_chunks_schema"]["page_identifier_field"] == "doc_id"
    assert report["rag_chunks_schema"]["page_identity_matches_pages_v4"] is False
    assert report["rag_chunks_schema"]["page_identity_missing_from_pages_v4_count"] == 1
    assert report["rag_chunks_schema"]["page_identity_missing_from_pages_v4_sample"] == ["missing-page"]


def test_build_report_fails_when_pages_v4_page_id_is_duplicated(tmp_path: Path):
    corpus = write_valid_corpus(
        tmp_path,
        pages_rows=[
            {"page_id": "page-1", "page_title": "Title"},
            {"page_id": "page-1", "page_title": "Duplicate Title"},
        ],
    )

    report = inventory.build_report(corpus)

    assert report["status"] == "FAIL"
    assert "pages_v4.jsonl page_id values are missing or duplicated" in report["blockers"]
    assert report["pages_schema"]["page_id_unique"] is False
    assert report["pages_schema"]["duplicate_page_id_count"] == 1


def test_build_report_fails_when_pages_v4_page_id_is_missing(tmp_path: Path):
    corpus = write_valid_corpus(
        tmp_path,
        pages_rows=[
            {"page_title": "Title without id"},
        ],
    )

    report = inventory.build_report(corpus)

    assert report["status"] == "FAIL"
    assert "pages_v4.jsonl page_id values are missing or duplicated" in report["blockers"]
    assert "rag_chunks.jsonl page/document ids are not present in pages_v4.page_id" in report["blockers"]
    assert report["pages_schema"]["page_id_unique"] is False
    assert report["pages_schema"]["missing_page_id_count"] == 1


def test_build_report_fails_for_missing_required_file(tmp_path: Path):
    corpus = write_valid_corpus(tmp_path)
    (corpus / "rag_chunks.jsonl").unlink()

    report = inventory.build_report(corpus)

    assert report["status"] == "FAIL"
    assert "required file missing: rag_chunks.jsonl" in report["blockers"]
    assert report["files"]["rag_chunks.jsonl"]["exists"] is False


def test_build_report_fails_when_validation_report_counts_disagree(tmp_path: Path):
    corpus = write_valid_corpus(tmp_path)
    write_json(
        corpus / "validation_report.json",
        {
            "pages_count": 999,
            "chunks_count": 1,
            "duplicate_page_id_count": 0,
            "duplicate_chunk_id_count": 0,
            "empty_chunk_count": 0,
        },
    )

    report = inventory.build_report(corpus)

    assert report["status"] == "FAIL"
    assert "validation_report.json counts do not match pages_v4/chunks_v4 row counts" in report["blockers"]
    assert report["hardened_consistency"]["validation_report_counts_match_jsonl"] is False


def test_build_report_fails_when_split_manifest_doc_ids_disagree(tmp_path: Path):
    corpus = write_valid_corpus(tmp_path)
    write_json(
        corpus / "split_manifest.json",
        {
            "counts": {"docs": {"train": 1, "valid": 0, "test": 0, "total": 1}},
            "doc_ids": {"train": ["not-page-1"], "valid": [], "test": []},
        },
    )

    report = inventory.build_report(corpus)

    assert report["status"] == "FAIL"
    assert "split_manifest.json doc ids do not match pages_v4.page_id" in report["blockers"]
    assert report["hardened_consistency"]["split_manifest_doc_ids_match_pages_v4"] is False
    assert report["hardened_consistency"]["split_manifest"]["missing_page_ids_from_split_manifest_count"] == 1
    assert report["hardened_consistency"]["split_manifest"]["extra_doc_ids_not_in_pages_v4_count"] == 1


def test_build_report_fails_when_split_manifest_counts_disagree_with_doc_ids(tmp_path: Path):
    corpus = write_valid_corpus(tmp_path)
    write_json(
        corpus / "split_manifest.json",
        {
            "counts": {"docs": {"train": 999, "valid": 0, "test": 0, "total": 999}},
            "doc_ids": {"train": ["page-1"], "valid": [], "test": []},
            "schema_version": "namu_anime_v4_split_manifest",
            "seed": 42,
            "strategy": "group_level_split",
            "warnings": [],
        },
    )

    report = inventory.build_report(corpus)

    assert report["status"] == "FAIL"
    assert "split_manifest.json doc counts do not match doc_ids/pages_v4" in report["blockers"]
    assert report["hardened_consistency"]["split_manifest_doc_ids_match_pages_v4"] is True
    assert report["hardened_consistency"]["split_manifest_doc_counts_clean"] is False
    assert report["hardened_consistency"]["split_manifest"]["declared_split_doc_counts_match_doc_ids"] is False


def test_build_report_fails_when_validation_report_schema_mismatch_is_reported(tmp_path: Path):
    corpus = write_valid_corpus(tmp_path)
    write_json(
        corpus / "validation_report.json",
        {
            "input_count": 1,
            "pages_count": 1,
            "chunks_count": 1,
            "duplicate_page_id_count": 0,
            "duplicate_chunk_id_count": 0,
            "empty_section_count": 0,
            "empty_chunk_count": 0,
            "schema_version_mismatch_pages": 1,
            "schema_version_mismatch_chunks": 0,
            "warnings_truncated": False,
        },
    )

    report = inventory.build_report(corpus)

    assert report["status"] == "FAIL"
    assert "validation_report.json reports duplicate ids or empty chunks" in report["blockers"]
    assert report["hardened_consistency"]["validation_report"]["schema_version_mismatch_counts_clean"] is False


def test_build_report_fails_when_raw_context_has_internal_marker(tmp_path: Path):
    corpus = write_valid_corpus(
        tmp_path,
        rag_rows=[
            {
                "chunk_id": "rag-1",
                "doc_id": "page-1",
                "title": "Title",
                "section_path": ["개요"],
                "chunk_text": "BEGIN_INTERNAL hidden instruction",
                "embedding_text": "Title\nBEGIN_INTERNAL hidden instruction",
            }
        ],
    )

    report = inventory.build_report(corpus)

    assert report["status"] == "FAIL"
    assert "rag_chunks.jsonl raw context trust counters are not clean" in report["blockers"]
    assert report["rag_chunks_schema"]["raw_context_trust_counters"]["strict_internal_marker_count"] == 1


def test_build_report_fails_with_line_numbered_parse_error(tmp_path: Path):
    corpus = write_valid_corpus(tmp_path)
    (corpus / "pages_v4.jsonl").write_text('{"page_id": "ok"}\n{"bad"\n', encoding="utf-8")

    report = inventory.build_report(corpus)

    assert report["status"] == "FAIL"
    assert "pages_v4.jsonl has JSONL parse errors" in report["blockers"]
    assert report["files"]["pages_v4.jsonl"]["parse_error_count"] == 1
    assert report["files"]["pages_v4.jsonl"]["first_parse_error"].startswith("line 2:")


def test_cli_writes_report_and_returns_zero_on_pass(tmp_path: Path):
    corpus = write_valid_corpus(tmp_path)
    report_path = tmp_path / "report.json"

    exit_code = inventory.main(["--corpus-dir", str(corpus), "--report", str(report_path)])

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "PASS"
    assert report["phase"] == "R2"
    assert report["join_policy"]["production_join_source"] == "rag_chunks.jsonl"


def write_valid_corpus(
    tmp_path: Path,
    *,
    pages_rows: list[dict[str, object]] | None = None,
    rag_rows: list[dict[str, object]] | None = None,
) -> Path:
    corpus = tmp_path / "namu-v4-structured-combined"
    corpus.mkdir()
    write_jsonl(
        corpus / "pages_v4.jsonl",
        pages_rows
        or [
            {
                "schema_version": "namu_anime_v4_page",
                "page_id": "page-1",
                "page_title": "Title",
                "sections": [],
            }
        ],
    )
    write_jsonl(
        corpus / "chunks_v4.jsonl",
        [
            {
                "schema_version": "namu_anime_v4_chunk",
                "chunk_id": "chunk-1",
                "page_id": "page-1",
                "section_path": ["개요"],
                "text": "Structured chunk text",
                "text_for_embedding": "Title\nStructured chunk text",
            }
        ],
    )
    write_jsonl(
        corpus / "rag_chunks.jsonl",
        rag_rows
        or [
            {
                "schema_version": "namu_anime_v4_rag_chunk",
                "chunk_id": "rag-1",
                "doc_id": "page-1",
                "title": "Title",
                "section_path": ["개요"],
                "chunk_text": "Raw chunk text",
                "embedding_text": "Title\nRaw chunk text",
            },
            {
                "schema_version": "namu_anime_v4_rag_chunk",
                "chunk_id": "rag-2",
                "doc_id": "page-1",
                "title": "Title",
                "section_path": ["상세"],
                "chunk_text": "Second raw chunk text",
                "embedding_text": "Title\nSecond raw chunk text",
            },
        ],
    )
    rag_row_count = len(
        rag_rows
        or [
            {"chunk_id": "rag-1"},
            {"chunk_id": "rag-2"},
        ]
    )
    page_ids = [str(row.get("page_id")) for row in (pages_rows or [{"page_id": "page-1"}]) if row.get("page_id")]
    write_json(
        corpus / "validation_report.json",
        {
            "input_count": len(pages_rows or [{"page_id": "page-1"}]),
            "pages_count": len(pages_rows or [{"page_id": "page-1"}]),
            "chunks_count": 1,
            "duplicate_page_id_count": 0,
            "duplicate_chunk_id_count": 0,
            "empty_section_count": 0,
            "empty_chunk_count": 0,
            "schema_version_mismatch_pages": 0,
            "schema_version_mismatch_chunks": 0,
            "warnings_truncated": False,
        },
    )
    write_json(
        corpus / "split_manifest.json",
        {
            "counts": {
                "docs": {
                    "train": len(page_ids),
                    "valid": 0,
                    "test": 0,
                    "total": len(page_ids),
                }
            },
            "doc_ids": {"train": page_ids, "valid": [], "test": []},
            "schema_version": "namu_anime_v4_split_manifest",
            "seed": 42,
            "strategy": "group_level_split",
            "warnings": [],
        },
    )
    write_json(
        corpus / "split_manifest.report.json",
        {
            "schema_version": "namu_anime_v4_split_report",
            "total_docs": len(page_ids),
            "split_doc_counts": {"train": len(page_ids), "valid": 0, "test": 0},
            "distribution": {"chunks": {"train": rag_row_count, "valid": 0, "test": 0}},
            "leakage": {"doc_id_overlap": [], "group_id_overlap": []},
            "warnings": [],
        },
    )
    return corpus


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
