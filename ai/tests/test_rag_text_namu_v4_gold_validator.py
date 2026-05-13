from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER_PATH = ROOT / "ai" / "scripts" / "rag_text_namu_v4_gold_builder.py"
VALIDATOR_PATH = ROOT / "ai" / "scripts" / "rag_text_namu_v4_gold_validator.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


builder = load_module(BUILDER_PATH, "rag_text_namu_v4_gold_builder_for_tests")
validator = load_module(VALIDATOR_PATH, "rag_text_namu_v4_gold_validator_for_tests")


def test_builder_binds_curated_seed_rows_to_pages_and_rag_chunks(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    source = write_source(tmp_path)
    output = tmp_path / "gold.csv"

    build = builder.build_gold(source_path=source, corpus_dir=corpus, output_csv=output)

    assert build["report"]["status"] == "COMPLETED"
    assert build["report"]["promotion_evidence"] is False
    assert build["report"]["evidence_role"] == "diagnostic"
    assert build["report"]["row_count"] == 2
    assert build["report"]["positive_row_count"] == 1
    assert build["report"]["needs_review_row_count"] == 1
    assert build["report"]["abstain_or_review_row_count"] == 1
    first = build["rows"][0]
    assert first["query_id"] == "gold_seed_0001"
    assert first["expected_page_ids"] == "page-1"
    assert first["expected_chunk_ids"] == "chunk-1"
    assert first["expected_section_ids"] == "section-1"
    assert first["label_status"] == "bound"
    second = build["rows"][1]
    assert second["label_status"] == "needs_review"
    assert second["allowed_abstain"] == "false"
    assert second["bucket"] == "text_policy_question"
    assert second["answer_type"] == "claim_check"


def test_builder_fails_when_expected_chunk_is_missing(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    source = write_source(tmp_path, first_chunk_id="missing-chunk")

    build = builder.build_gold(source_path=source, corpus_dir=corpus, output_csv=tmp_path / "gold.csv")

    assert build["report"]["status"] == "FAILED"
    assert "expected_chunk_id not found in rag_chunks: missing-chunk" in build["report"]["row_errors"]["gold_seed_0001"]


def test_builder_rejects_expected_section_path_mismatch(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    source = write_source(tmp_path, first_section_path=["설정"])

    build = builder.build_gold(source_path=source, corpus_dir=corpus, output_csv=tmp_path / "gold.csv")

    assert build["report"]["status"] == "FAILED"
    assert (
        "chunk chunk-1 section_path=['개요'] does not match expected_section_path=['설정']"
        in build["report"]["row_errors"]["gold_seed_0001"]
    )


def test_validator_passes_bound_and_needs_review_rows(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    rows = [
        valid_gold_row("gold_seed_0001", label_status="bound", allowed_abstain="false"),
        valid_gold_row("gold_seed_0002", label_status="needs_review", allowed_abstain="false"),
    ]

    result = validator.validate_rows(
        rows,
        columns=validator.REQUIRED_COLUMNS,
        pages=validator.load_pages(corpus / "pages_v4.jsonl"),
        chunks=validator.load_rag_chunks(corpus / "rag_chunks.jsonl"),
        min_rows=2,
    )

    assert result.ok, result.row_errors
    assert result.positive_row_count == 1
    assert result.needs_review_row_count == 1
    assert result.abstain_or_review_row_count == 1


def test_validator_allows_abstain_review_rows_without_bindings(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    rows = [
        valid_gold_row("gold_seed_0001", label_status="bound", allowed_abstain="false"),
        valid_gold_row(
            "gold_seed_0002",
            page_ids="",
            section_ids="",
            chunk_ids="",
            label_status="needs_review",
            allowed_abstain="true",
        ),
    ]

    result = validator.validate_rows(
        rows,
        columns=validator.REQUIRED_COLUMNS,
        pages=validator.load_pages(corpus / "pages_v4.jsonl"),
        chunks=validator.load_rag_chunks(corpus / "rag_chunks.jsonl"),
        min_rows=2,
    )

    assert result.ok, result.row_errors
    assert result.positive_row_count == 1
    assert result.needs_review_row_count == 1
    assert result.abstain_or_review_row_count == 1


def test_validator_rejects_missing_chunk_and_doc_mismatch(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    rows = [
        valid_gold_row("missing", chunk_ids="missing-chunk"),
        valid_gold_row("mismatch", page_ids="page-2", chunk_ids="chunk-1"),
    ]

    result = validator.validate_rows(
        rows,
        columns=validator.REQUIRED_COLUMNS,
        pages=validator.load_pages(corpus / "pages_v4.jsonl"),
        chunks=validator.load_rag_chunks(corpus / "rag_chunks.jsonl"),
        min_rows=2,
    )

    assert not result.ok
    assert result.missing_chunk_ids == ["missing-chunk"]
    assert "chunk chunk-1 doc_id=page-1 outside expected_page_ids=['page-2']" in result.row_errors["mismatch"]


def test_validator_rejects_missing_columns_and_duplicate_query_ids(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    rows = [valid_gold_row("dup"), valid_gold_row("dup")]

    result = validator.validate_rows(
        rows,
        columns=["query_id", "query"],
        pages=validator.load_pages(corpus / "pages_v4.jsonl"),
        chunks=validator.load_rag_chunks(corpus / "rag_chunks.jsonl"),
        min_rows=2,
    )

    assert not result.ok
    assert "bucket" in result.missing_required_columns
    assert result.duplicate_query_ids == ["dup"]


def test_validator_rejects_section_ids_missing_from_pages(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    rows = [valid_gold_row("bad-section", section_ids="missing-section")]

    result = validator.validate_rows(
        rows,
        columns=validator.REQUIRED_COLUMNS,
        pages=validator.load_pages(corpus / "pages_v4.jsonl"),
        chunks=validator.load_rag_chunks(corpus / "rag_chunks.jsonl"),
        min_rows=1,
    )

    assert not result.ok
    assert result.missing_section_ids == ["missing-section"]
    assert "expected_section_id not found on expected chunks: missing-section" in result.row_errors["bad-section"]
    assert "expected_section_id not found under expected pages: missing-section" in result.row_errors["bad-section"]


def test_validator_rejects_section_path_mismatch_from_notes(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    rows = [valid_gold_row("bad-path", notes="expected_section_path=설정")]

    result = validator.validate_rows(
        rows,
        columns=validator.REQUIRED_COLUMNS,
        pages=validator.load_pages(corpus / "pages_v4.jsonl"),
        chunks=validator.load_rag_chunks(corpus / "rag_chunks.jsonl"),
        min_rows=1,
    )

    assert not result.ok
    assert result.section_path_mismatch_count == 1
    assert (
        "chunk chunk-1 section_path=['개요'] does not match expected_section_path=['설정']"
        in result.row_errors["bad-path"]
    )


def test_validator_report_enforces_current_seed_no_abstain_policy(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    rows = [
        valid_gold_row("gold_seed_0001", label_status="bound", allowed_abstain="false"),
        valid_gold_row(
            "gold_seed_0002",
            page_ids="",
            section_ids="",
            chunk_ids="",
            label_status="needs_review",
            allowed_abstain="true",
            notes="",
        ),
    ]
    result = validator.validate_rows(
        rows,
        columns=validator.REQUIRED_COLUMNS,
        pages=validator.load_pages(corpus / "pages_v4.jsonl"),
        chunks=validator.load_rag_chunks(corpus / "rag_chunks.jsonl"),
        min_rows=2,
    )

    report = validator.build_report(
        gold=tmp_path / "gold.csv",
        corpus_dir=corpus,
        validation=result,
        min_rows=2,
        expected_row_count=2,
        expected_positive_row_count=1,
        expected_needs_review_row_count=1,
    )

    assert report["status"] == "FAILED"
    assert report["done_criteria"]["all_allowed_abstain_false"] is False
    assert "all_allowed_abstain_false" in report["failed_done_criteria"]
    assert "done_criteria failed: all_allowed_abstain_false" in report["blockers"]
    assert report["current_seed_policy"]["fabricated_abstain_row_count"] == 1


def test_validator_cli_writes_passed_report(tmp_path: Path):
    corpus = write_corpus(tmp_path)
    gold = tmp_path / "gold.csv"
    report_path = tmp_path / "report.json"
    write_gold_csv(gold, [
        valid_gold_row("gold_seed_0001", label_status="bound", allowed_abstain="false"),
        valid_gold_row("gold_seed_0002", label_status="needs_review", allowed_abstain="false"),
    ])

    exit_code = validator.main([
        "--gold",
        str(gold),
        "--corpus-dir",
        str(corpus),
        "--report",
        str(report_path),
        "--min-rows",
        "2",
        "--expected-row-count",
        "2",
        "--expected-positive-row-count",
        "1",
        "--expected-needs-review-row-count",
        "1",
    ])

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "PASSED"
    assert report["phase"] == "R3"
    assert report["promotion_evidence"] is False
    assert report["evidence_role"] == "diagnostic"
    assert report["positive_denominator_policy"]["positive_row_count"] == 1


def write_corpus(tmp_path: Path) -> Path:
    corpus = tmp_path / "namu-v4-structured-combined"
    corpus.mkdir()
    write_jsonl(
        corpus / "pages_v4.jsonl",
        [
            {
                "page_id": "page-1",
                "page_title": "Page One",
                "sections": [{"section_id": "section-1", "heading_path": ["개요"]}],
            },
            {
                "page_id": "page-2",
                "page_title": "Page Two",
                "sections": [{"section_id": "section-2", "heading_path": ["설정"]}],
            },
        ],
    )
    write_jsonl(
        corpus / "rag_chunks.jsonl",
        [
            {
                "chunk_id": "chunk-1",
                "doc_id": "page-1",
                "title": "Page One",
                "section_id": "section-1",
                "section_path": ["개요"],
                "chunk_text": "Raw chunk one",
            },
            {
                "chunk_id": "chunk-2",
                "doc_id": "page-2",
                "title": "Page Two",
                "section_id": "section-2",
                "section_path": ["설정"],
                "chunk_text": "Raw chunk two",
            },
        ],
    )
    return corpus


def write_source(
    tmp_path: Path,
    *,
    first_chunk_id: str = "chunk-1",
    first_section_path: list[str] | None = None,
) -> Path:
    source = tmp_path / "gold_seed_50_candidates.jsonl"
    write_jsonl(
        source,
        [
            {
                "seed_id": "gold_seed_0001",
                "source_query_id": "v4-silver-natural-0001",
                "query": "첫 번째 문서 개요 찾아줘",
                "expected_doc_ids": ["page-1"],
                "expected_title": "Page One",
                "expected_section_path": first_section_path or ["개요"],
                "expected_chunk_ids": [first_chunk_id],
                "query_type": "title_direct",
                "difficulty": "medium",
                "answerability": "answerable",
                "source_evidence": "Raw chunk one",
            },
            {
                "seed_id": "gold_seed_0002",
                "source_query_id": "v4-silver-natural-0002",
                "query": "틀린 전제를 확인해줘",
                "expected_doc_ids": ["page-2"],
                "expected_title": "Page Two",
                "expected_section_path": ["설정"],
                "expected_chunk_ids": ["chunk-2"],
                "query_type": "wrong_assumption",
                "difficulty": "hard",
                "answerability": "partially_answerable",
                "source_evidence": "Raw chunk two",
            },
        ],
    )
    return source


def valid_gold_row(
    query_id: str,
    *,
    page_ids: str = "page-1",
    chunk_ids: str = "chunk-1",
    section_ids: str = "section-1",
    label_status: str = "bound",
    allowed_abstain: str = "false",
    notes: str = "expected_section_path=개요",
) -> dict[str, str]:
    return {
        "query_id": query_id,
        "bucket": "text_fact_lookup",
        "query": "첫 번째 문서 개요 찾아줘",
        "expected_page_ids": page_ids,
        "expected_section_ids": section_ids,
        "expected_chunk_ids": chunk_ids,
        "expected_answer_summary": "Raw chunk one",
        "must_contain_terms": "Page One;개요",
        "must_not_contain_terms": "",
        "allowed_abstain": allowed_abstain,
        "answer_type": "short_fact",
        "label_status": label_status,
        "source_dataset": validator.EXPECTED_SOURCE_DATASET,
        "notes": notes,
    }


def write_gold_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=validator.REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
