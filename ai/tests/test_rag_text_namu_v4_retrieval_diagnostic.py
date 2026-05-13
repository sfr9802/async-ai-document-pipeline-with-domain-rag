from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai" / "scripts" / "rag_text_namu_v4_retrieval_diagnostic.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


diagnostic = load_module(SCRIPT_PATH, "rag_text_namu_v4_retrieval_diagnostic_for_tests")


def test_run_diagnostic_writes_fresh_emit_and_scores_positive_denominator(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = diagnostic.run_diagnostic(**paths, top_k=10)

    assert report["status"] == "PASS"
    assert report["promotion_evidence"] is False
    assert report["evidence_role"] == "diagnostic"
    assert report["query_count"] == 50
    assert report["positive_denominator_count"] == 47
    assert report["needs_review_excluded_count"] == 3
    assert report["Hit@1"] == 1.0
    assert report["Hit@10"] == 1.0
    assert report["MRR@10"] == 1.0
    assert report["reused_emit"] is False
    assert report["existing_emit_reused"] is False
    assert report["retrieval_metrics_computed"] is True
    assert report["llm_answer_eval_run"] is False
    assert report["citation_eval_run"] is False
    assert report["promotion_run"] is False
    assert paths["fresh_emit"].exists()
    emit_rows = [json.loads(line) for line in paths["fresh_emit"].read_text(encoding="utf-8").splitlines()]
    assert len(emit_rows) == 50
    assert emit_rows[0]["denominator_included"] is True
    assert emit_rows[-1]["denominator_included"] is False
    assert emit_rows[-1]["denominator_exclusion_reason"] == "label_status=needs_review"


def test_run_diagnostic_blocks_without_passed_r3(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path, r3_status="FAILED")

    report = diagnostic.run_diagnostic(**paths, top_k=10)

    assert report["status"] == "FAIL"
    assert "R3 validator status is FAILED, not PASSED" in report["blockers"]
    assert report["retrieval_metrics_computed"] is False
    assert not paths["fresh_emit"].exists()


def test_run_diagnostic_warns_when_expected_chunk_is_not_retrieved(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path, positive_query="beta")

    report = diagnostic.run_diagnostic(**paths, top_k=10)

    assert report["status"] == "PASS_WITH_WARNINGS"
    assert report["Hit@10"] == 0.0
    assert report["wrong_source_count"] == 47
    assert report["missing_expected_chunk_count"] == 47
    assert report["retrieval_error_count"] == 0
    assert report["retrieval_metrics_computed"] is True


def write_fixture_bundle(
    tmp_path: Path,
    *,
    r3_status: str = "PASSED",
    positive_query: str = "alpha",
) -> dict[str, Path]:
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    write_jsonl(
        corpus_dir / "rag_chunks.jsonl",
        [
            {
                "chunk_id": "chunk-alpha",
                "doc_id": "page-alpha",
                "title": "Alpha",
                "retrieval_title": "Alpha",
                "section_id": "section-alpha",
                "section_path": ["Overview"],
                "chunk_text": "alpha evidence text",
            },
            {
                "chunk_id": "chunk-beta",
                "doc_id": "page-beta",
                "title": "Beta",
                "retrieval_title": "Beta",
                "section_id": "section-beta",
                "section_path": ["Overview"],
                "chunk_text": "beta evidence text",
            },
        ],
    )
    gold = tmp_path / "gold_queries_text_namu_v4_v0.csv"
    write_gold(gold, positive_query=positive_query)
    corpus_report = tmp_path / "rag_text_namu_v4_corpus_inventory_report.json"
    r3_report = tmp_path / "rag_text_namu_v4_gold_validate_report.json"
    r4_report = tmp_path / "rag_text_namu_v4_retrieval_emit_inventory_report.json"
    write_json(corpus_report, {"status": "PASS"})
    write_json(r3_report, {"status": r3_status})
    write_json(
        r4_report,
        {
            "status": "NO_REUSABLE_EXISTING_EMIT",
            "decision": "RUN_FRESH_DIAGNOSTIC_RETRIEVAL",
            "retrieval_metrics_computed": False,
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
        },
    )
    return {
        "gold": gold,
        "corpus_dir": corpus_dir,
        "corpus_inventory_report": corpus_report,
        "r3_validator_report": r3_report,
        "r4_inventory_report": r4_report,
        "fresh_emit": tmp_path / "rag_text_namu_v4_retrieval_emit.jsonl",
        "report_path": tmp_path / "rag_text_namu_v4_retrieval_diagnostic_report.json",
    }


def write_gold(path: Path, *, positive_query: str) -> None:
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
            writer.writerow(
                {
                    "query_id": f"gold_seed_{index:04d}",
                    "bucket": "text_fact_lookup",
                    "query": positive_query,
                    "expected_page_ids": "page-alpha",
                    "expected_section_ids": "section-alpha",
                    "expected_chunk_ids": "chunk-alpha",
                    "expected_answer_summary": "alpha evidence",
                    "must_contain_terms": "",
                    "must_not_contain_terms": "",
                    "allowed_abstain": "false",
                    "answer_type": "short_fact",
                    "label_status": "bound",
                    "source_dataset": "fixture",
                    "notes": "",
                }
            )
        for index in range(48, 51):
            writer.writerow(
                {
                    "query_id": f"gold_seed_{index:04d}",
                    "bucket": "text_policy_question",
                    "query": "alpha",
                    "expected_page_ids": "page-alpha",
                    "expected_section_ids": "section-alpha",
                    "expected_chunk_ids": "chunk-alpha",
                    "expected_answer_summary": "alpha evidence",
                    "must_contain_terms": "",
                    "must_not_contain_terms": "",
                    "allowed_abstain": "false",
                    "answer_type": "claim_check",
                    "label_status": "needs_review",
                    "source_dataset": "fixture",
                    "notes": "",
                }
            )


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
