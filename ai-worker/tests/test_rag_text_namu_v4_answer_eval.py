from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_text_namu_v4_answer_eval.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


answer_eval = load_module(SCRIPT_PATH, "rag_text_namu_v4_answer_eval_for_tests")


def test_r7_deterministic_answer_eval_separates_retrieval_misses(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = answer_eval.run_answer_eval(**paths)
    rows = read_jsonl(paths["jsonl_path"])

    assert report["status"] == "PASS_WITH_WARNINGS"
    assert report["promotion_evidence"] is False
    assert report["promotion_ready"] is False
    assert report["evidence_role"] == "diagnostic"
    assert report["answer_metric_role"] == "diagnostic_only"
    assert report["context_field"] == "chunk_text"
    assert report["used_context_json_path"] == "contexts[].text"
    assert report["positive_denominator_count"] == 47
    assert report["needs_review_excluded_count"] == 3
    assert report["retrieval_context_available_count"] == 47
    assert report["expected_context_missing_due_to_wrong_source_count"] == 1
    assert report["expected_chunk_missing_count"] == 1
    assert report["retrieval_context_miss_count"] == 2
    assert report["answerable_from_context_count"] == 45
    assert report["answer_generation_failure_count"] == 0
    assert report["actual_generated_answer_output_count"] == 0
    assert report["generated_answer_missing_count"] == 45
    assert report["official_metric_input_rows"] == 0
    assert report["official_answer_denominator"] == 0
    assert report["official_answer_metric_computed"] is False
    assert report["official_text_answer_metric_status"] == "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY"
    assert report["live_llm_run"] is False
    assert report["llm_model"] == "none_deterministic_dry_run"
    assert report["context_source_policy"]["embedding_text_used"] is False
    assert all(row["diagnostic_only"] is True for row in rows)
    assert all(row["official_metric_input"] is False for row in rows)
    assert all(row["official_denominator_mutation"] is False for row in rows)
    assert all(row["actual_generated_answer_output"] is False for row in rows)
    assert rows[0]["primary_stage"] == "answerable_from_context"
    assert rows[0]["diagnostic_only"] is True
    assert rows[0]["official_metric_input"] is False
    assert rows[0]["actual_generated_answer_output"] is False
    assert rows[0]["generated_answer_missing"] is True
    assert "answer_eval_pending_live_llm" in rows[0]["stages"]
    assert rows[1]["primary_stage"] == "expected_context_missing_due_to_wrong_source"
    assert rows[2]["primary_stage"] == "expected_chunk_missing"
    assert rows[47]["primary_stage"] == "denominator_excluded_needs_review"


def test_r7_fails_if_context_contains_disallowed_fields(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path, leak_disallowed_field=True)

    report = answer_eval.run_answer_eval(**paths)

    assert report["status"] == "FAIL"
    assert any("contains disallowed fields" in blocker for blocker in report["blockers"])
    assert not paths["jsonl_path"].exists()


def test_r7_live_llm_flag_is_blocked_until_explicit_implementation(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = answer_eval.run_answer_eval(**paths, enable_live_llm=True)

    assert report["status"] == "FAIL"
    assert "live LLM judge is intentionally not implemented in R7 deterministic mode" in report["blockers"]
    assert report["live_llm_requested"] is True
    assert report["live_llm_run"] is False


def test_r7_checks_context_report_sha(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    payload = json.loads(paths["context_report"].read_text(encoding="utf-8"))
    payload["context_emit_sha256"] = "wrong-sha"
    paths["context_report"].write_text(json.dumps(payload), encoding="utf-8")

    report = answer_eval.run_answer_eval(**paths)

    assert report["status"] == "FAIL"
    assert any("context_emit_sha256 mismatch" in blocker for blocker in report["blockers"])


def write_fixture_bundle(tmp_path: Path, *, leak_disallowed_field: bool = False) -> dict[str, Path]:
    gold = tmp_path / "gold_queries_text_namu_v4_v0.csv"
    context_jsonl = tmp_path / "rag_text_namu_v4_context_assembly.jsonl"
    context_report = tmp_path / "rag_text_namu_v4_context_assembly_report.json"
    report_path = tmp_path / "rag_text_namu_v4_answer_eval_report.json"
    jsonl_path = tmp_path / "rag_text_namu_v4_answer_eval.jsonl"

    write_gold(gold)
    context_rows = [context_row(index, leak_disallowed_field=leak_disallowed_field) for index in range(1, 51)]
    write_jsonl(context_jsonl, context_rows)
    context_sha = answer_eval.sha256_file(context_jsonl)
    write_json(
        context_report,
        {
            "status": "PASS_WITH_WARNINGS",
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "context_emit_path": str(context_jsonl.resolve()),
            "context_emit_sha256": context_sha,
            "context_field": "chunk_text",
            "positive_denominator_count": 47,
            "needs_review_excluded_count": 3,
            "r7_ready": True,
            "llm_answer_eval_run": False,
            "citation_eval_run": False,
            "promotion_run": False,
            "indexing_run": False,
            "expected_context_present_count": 45,
            "missing_expected_source_count": 1,
            "missing_expected_chunk_count": 1,
            "taxonomy_counts": {
                "expected_context_present": 45,
                "missing_expected_source": 1,
                "missing_expected_chunk": 1,
            },
        },
    )
    return {
        "gold": gold,
        "context_jsonl": context_jsonl,
        "context_report": context_report,
        "report_path": report_path,
        "jsonl_path": jsonl_path,
    }


def write_gold(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(1, 51):
            needs_review = index >= 48
            writer.writerow(
                {
                    "query_id": f"gold_seed_{index:04d}",
                    "bucket": "text_policy_question" if needs_review else "text_fact_lookup",
                    "query": f"query {index}",
                    "expected_page_ids": f"page-{index}",
                    "expected_section_ids": f"section-{index}",
                    "expected_chunk_ids": f"chunk-{index}",
                    "expected_answer_summary": f"alpha evidence {index}",
                    "must_contain_terms": f"alpha;{index}",
                    "must_not_contain_terms": "forbidden" if index == 1 else "",
                    "allowed_abstain": "false",
                    "answer_type": "short_fact",
                    "label_status": "needs_review" if needs_review else "bound",
                    "source_dataset": "fixture",
                    "notes": "",
                }
            )


def context_row(index: int, *, leak_disallowed_field: bool) -> dict[str, object]:
    denominator = index < 48
    taxonomy = "expected_context_present"
    expected_source_present = True
    expected_chunk_present = True
    page_id = f"page-{index}"
    chunk_id = f"chunk-{index}"
    if index == 2:
        taxonomy = "missing_expected_source"
        expected_source_present = False
        expected_chunk_present = False
        page_id = "wrong-page"
        chunk_id = "wrong-chunk"
    elif index == 3:
        taxonomy = "missing_expected_chunk"
        expected_chunk_present = False
        chunk_id = "wrong-chunk"
    elif not denominator:
        taxonomy = "excluded_needs_review"

    context = {
        "rank": 1,
        "chunk_id": chunk_id,
        "doc_id": page_id,
        "page_id": page_id,
        "section_id": f"section-{index}",
        "section_path": ["Overview"],
        "title": f"Title {index}",
        "score": 1.0,
        "context_field": "chunk_text",
        "text": f"alpha evidence {index}",
    }
    if leak_disallowed_field and index == 1:
        context["embedding_text"] = "must not be used"

    return {
        "schema_version": "rag_text_namu_v4_context_assembly_v1",
        "phase": "R6_B3_NAMU_CONTEXT_ASSEMBLY",
        "query_id": f"gold_seed_{index:04d}",
        "query": f"query {index}",
        "bucket": "text_policy_question" if not denominator else "text_fact_lookup",
        "label_status": "needs_review" if not denominator else "bound",
        "allowed_abstain": False,
        "denominator_included": denominator,
        "denominator_exclusion_reason": None if denominator else "label_status=needs_review",
        "taxonomy": taxonomy,
        "failure_reasons": [] if taxonomy == "expected_context_present" else [taxonomy],
        "expected_page_ids": [f"page-{index}"],
        "expected_section_ids": [f"section-{index}"],
        "expected_chunk_ids": [f"chunk-{index}"],
        "expected_source_present": expected_source_present,
        "expected_section_present": expected_source_present,
        "expected_chunk_present": expected_chunk_present,
        "retrieval_result_count": 1,
        "deduped_retrieval_result_count": 1,
        "duplicate_chunk_dedup_count": 0,
        "missing_corpus_chunk_ids": [],
        "empty_chunk_text_ids": [],
        "context_field": "chunk_text",
        "contexts": [context],
        "context_count": 1,
        "context_char_count": len(context["text"]),
        "truncated": False,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
