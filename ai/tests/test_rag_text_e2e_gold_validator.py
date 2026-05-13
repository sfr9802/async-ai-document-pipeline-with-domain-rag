from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "scripts" / "rag_text_e2e_gold_validator.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_text_e2e_gold_validator_for_tests", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = load_module()


def test_validate_rows_accepts_minimal_b1_seed_contract():
    rows = [_row(f"q{i}", "text_fact_lookup") for i in range(1, 10)]
    rows.append(_row("q10", "text_abstain_required", allowed_abstain="true", source="", chunk=""))

    result = validator.validate_rows(rows, columns=validator.REQUIRED_COLUMNS, min_rows=10)

    assert result.ok, result.row_errors
    assert result.row_count == 10
    assert result.bucket_counts["text_abstain_required"] == 1
    assert result.abstain_true_count == 1


def test_validate_rows_rejects_missing_columns_duplicate_ids_and_missing_non_abstain_source():
    rows = [
        _row("dup", "text_fact_lookup", source=""),
        _row("dup", "text_fact_lookup"),
    ]

    result = validator.validate_rows(rows, columns=["query_id", "bucket"], min_rows=10)

    assert not result.ok
    assert "query" in result.missing_required_columns
    assert result.duplicate_query_ids == ["dup"]
    assert "dup" in result.non_abstain_missing_source_ids
    assert "__dataset__" in result.row_errors


def test_build_report_keeps_diagnostic_flags_and_blocks_failed_db_check():
    validation = validator.validate_rows(
        [_row(f"q{i}", "text_fact_lookup") for i in range(1, 10)]
        + [_row("q10", "text_abstain_required", allowed_abstain="true", source="", chunk="")],
        columns=validator.REQUIRED_COLUMNS,
        min_rows=10,
    )

    report = validator.build_report(
        gold=Path("eval/eval_queries/gold_queries_text_e2e_v0.csv"),
        validation=validation,
        db_check={"status": "FAILED", "blockers": ["missing chunk id: c1"]},
        min_rows=10,
    )

    assert report["status"] == "FAILED"
    assert report["promotion_evidence"] is False
    assert report["evidence_role"] == "diagnostic"
    assert "missing chunk id: c1" in report["blockers"]


def test_row_level_chunk_source_mismatches_rejects_cross_source_binding():
    rows = [
        _row("q1", "text_fact_lookup", source="source-a", chunk="chunk-from-b"),
    ]
    chunk_by_id = {
        "chunk-from-b": {
            "id": "chunk-from-b",
            "source_file_id": "source-b",
            "source_file_type": "TEXT",
            "source_status": "READY",
        },
    }

    mismatches = validator.row_level_chunk_source_mismatches(rows, chunk_by_id)

    assert mismatches == [{
        "query_id": "q1",
        "chunk_id": "chunk-from-b",
        "actual_source_file_id": "source-b",
        "expected_source_ids": ["source-a"],
    }]


def test_build_report_marks_skip_db_as_schema_only_not_passed():
    validation = validator.validate_rows(
        [_row(f"q{i}", "text_fact_lookup") for i in range(1, 10)]
        + [_row("q10", "text_abstain_required", allowed_abstain="true", source="", chunk="")],
        columns=validator.REQUIRED_COLUMNS,
        min_rows=10,
    )

    report = validator.build_report(
        gold=Path("eval/eval_queries/gold_queries_text_e2e_v0.csv"),
        validation=validation,
        db_check={"status": "SCHEMA_ONLY", "reason": "skip_db requested; live binding was not verified"},
        min_rows=10,
    )

    assert report["status"] == "SCHEMA_ONLY"
    assert report["validation"]["schema_ok"] is True
    assert report["validation"]["ok"] is False
    assert report["done_criteria"]["live_binding_check_passed"] is False
    assert "skip_db requested; live binding was not verified" in report["blockers"]


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
        "query": "What does the text say?",
        "expected_answer_summary": "The text gives a diagnostic answer.",
        "expected_source_ids": source,
        "expected_chunk_ids": chunk,
        "expected_citation_texts": "source.txt > chunk 1",
        "must_contain_terms": "diagnostic",
        "must_not_contain_terms": "",
        "allowed_abstain": allowed_abstain,
        "answer_type": "short_fact",
        "difficulty": "easy",
        "label_status": "bound" if allowed_abstain == "false" else "draft",
        "notes": "unit test row",
    }
