from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "ai-worker" / "scripts" / "rag_text_namu_v4_citation_support.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


citation_support = load_module(SCRIPT_PATH, "rag_text_namu_v4_citation_support_for_tests")


def test_r8_citation_support_locks_denominator_and_excludes_misses(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)

    report = citation_support.run_citation_support(**paths)
    rows = read_jsonl(paths["jsonl_path"])

    assert report["status"] == "PASS_WITH_WARNINGS"
    assert report["promotion_evidence"] is False
    assert report["evidence_role"] == "diagnostic"
    assert report["promotion_ready"] is False
    assert report["live_llm_run"] is False
    assert report["optional_judge_run"] is False
    assert report["context_field"] == "chunk_text"
    assert report["disallowed_context_fields"] == ["embedding_text", "text_for_embedding", "debug_text"]
    assert report["positive_denominator_count"] == 47
    assert report["needs_review_excluded_count"] == 3
    assert report["citation_support_denominator_count"] == 29
    assert report["retrieval_context_miss_excluded_count"] == 18
    assert report["answer_generation_failure_count"] == 0
    assert report["retrieval_context_misses_counted_as_citation_failures"] is False
    assert report["supported_count"] == 28
    assert report["supported_by_expected_context_count"] == 27
    assert report["supported_by_context_but_expected_chunk_not_top_citation_count"] == 1
    assert report["partial_support_count"] == 1
    assert report["unsupported_count"] == 0
    assert report["unsupported_claim_count"] == 1
    assert report["missing_citation_count"] == 1
    assert report["done_criteria"]["support_denominator_is_29"] is True
    assert report["done_criteria"]["retrieval_context_miss_exclusion_is_18"] is True
    assert report["done_criteria"]["needs_review_exclusion_is_3"] is True
    assert len(rows) == 50

    by_id = {row["query_id"]: row for row in rows}
    assert by_id["gold_seed_0001"]["citation_support_status"] == "SUPPORTED_BY_EXPECTED_CONTEXT"
    assert by_id["gold_seed_0028"]["citation_support_status"] == (
        "SUPPORTED_BY_CONTEXT_BUT_EXPECTED_CHUNK_NOT_TOP_CITATION"
    )
    assert by_id["gold_seed_0029"]["citation_support_status"] == "PARTIAL_SUPPORT"
    assert by_id["gold_seed_0030"]["citation_support_status"] == "EXCLUDED_RETRIEVAL_CONTEXT_MISS"
    assert by_id["gold_seed_0030"]["citation_denominator_exclusion_bucket"] == (
        "excluded_from_citation_denominator_due_to_retrieval_context_miss"
    )
    assert by_id["gold_seed_0030"]["unsupported_claim_candidate"] is False
    assert by_id["gold_seed_0048"]["citation_support_status"] == "EXCLUDED_NEEDS_REVIEW"


def test_r8_fails_if_context_contains_disallowed_fields(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path, leak_disallowed_field=True)

    report = citation_support.run_citation_support(**paths)

    assert report["status"] == "FAIL"
    assert any("contains disallowed fields" in blocker for blocker in report["blockers"])
    assert not paths["jsonl_path"].exists()


def test_r8_checks_source_report_sha_contracts(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    payload = json.loads(paths["answer_report"].read_text(encoding="utf-8"))
    payload["answer_eval_jsonl_sha256"] = "wrong-sha"
    write_json(paths["answer_report"], payload)

    report = citation_support.run_citation_support(**paths)

    assert report["status"] == "FAIL"
    assert any("answer_eval_jsonl_sha256 mismatch" in blocker for blocker in report["blockers"])


def test_r8_fails_if_r7_answerable_partition_is_count_preserving_but_swapped(tmp_path: Path):
    paths = write_fixture_bundle(tmp_path)
    rows = read_jsonl(paths["answer_jsonl"])
    rows[0]["answerable_from_context"] = False
    rows[0]["answer_eval_pending_live_llm"] = False
    rows[0]["primary_stage"] = "not_answerable_from_context"
    rows[0]["stages"] = ["retrieval_context_available", "not_answerable_from_context"]
    rows[29]["answerable_from_context"] = True
    rows[29]["answer_eval_pending_live_llm"] = True
    write_jsonl(paths["answer_jsonl"], rows)
    payload = json.loads(paths["answer_report"].read_text(encoding="utf-8"))
    payload["answer_eval_jsonl_sha256"] = citation_support.sha256_file(paths["answer_jsonl"])
    write_json(paths["answer_report"], payload)

    report = citation_support.run_citation_support(**paths)

    assert report["status"] == "FAIL"
    assert any("positive R7 row must be either answerable_from_context" in blocker for blocker in report["blockers"])
    assert any("must not also be retrieval/context miss" in blocker for blocker in report["blockers"])
    assert not paths["jsonl_path"].exists()


def write_fixture_bundle(tmp_path: Path, *, leak_disallowed_field: bool = False) -> dict[str, Path]:
    gold = tmp_path / "gold_queries_text_namu_v4_v0.csv"
    answer_report = tmp_path / "rag_text_namu_v4_answer_eval_report.json"
    answer_jsonl = tmp_path / "rag_text_namu_v4_answer_eval.jsonl"
    context_report = tmp_path / "rag_text_namu_v4_context_assembly_report.json"
    context_jsonl = tmp_path / "rag_text_namu_v4_context_assembly.jsonl"
    retrieval_report = tmp_path / "rag_text_namu_v4_retrieval_diagnostic_report.json"
    report_path = tmp_path / "rag_text_namu_v4_citation_support_report.json"
    jsonl_path = tmp_path / "rag_text_namu_v4_citation_support.jsonl"

    write_gold(gold)
    answer_rows = [answer_row(index) for index in range(1, 51)]
    context_rows = [
        context_row(index, leak_disallowed_field=leak_disallowed_field) for index in range(1, 51)
    ]
    write_jsonl(answer_jsonl, answer_rows)
    write_jsonl(context_jsonl, context_rows)
    answer_sha = citation_support.sha256_file(answer_jsonl)
    context_sha = citation_support.sha256_file(context_jsonl)
    write_json(
        answer_report,
        {
            "status": "PASS_WITH_WARNINGS",
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "positive_denominator_count": 47,
            "needs_review_excluded_count": 3,
            "answerable_from_context_count": 29,
            "retrieval_context_miss_count": 18,
            "answer_generation_failure_count": 0,
            "live_llm_run": False,
            "optional_judge_run": False,
            "answer_eval_jsonl_sha256": answer_sha,
        },
    )
    write_json(
        context_report,
        {
            "status": "PASS_WITH_WARNINGS",
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "context_field": "chunk_text",
            "positive_denominator_count": 47,
            "needs_review_excluded_count": 3,
            "expected_context_present_count": 29,
            "missing_expected_source_count": 10,
            "missing_expected_chunk_count": 8,
            "context_emit_sha256": context_sha,
        },
    )
    write_json(
        retrieval_report,
        {
            "status": "PASS_WITH_WARNINGS",
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "positive_denominator_count": 47,
            "needs_review_excluded_count": 3,
            "llm_answer_eval_run": False,
            "citation_eval_run": False,
        },
    )
    return {
        "gold": gold,
        "answer_report": answer_report,
        "answer_jsonl": answer_jsonl,
        "context_report": context_report,
        "context_jsonl": context_jsonl,
        "retrieval_report": retrieval_report,
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
                    "expected_answer_summary": f"alpha beta gamma delta epsilon {index}",
                    "must_contain_terms": "",
                    "must_not_contain_terms": "",
                    "allowed_abstain": "false",
                    "answer_type": "short_fact",
                    "label_status": "needs_review" if needs_review else "bound",
                    "source_dataset": "fixture",
                    "notes": "expected_section_path=Overview",
                }
            )


def answer_row(index: int) -> dict[str, object]:
    denominator = index < 48
    answerable = index <= 29
    wrong_source = 30 <= index <= 39
    missing_chunk = 40 <= index <= 47
    if not denominator:
        primary_stage = "denominator_excluded_needs_review"
        stages = ["denominator_excluded_needs_review"]
    elif wrong_source:
        primary_stage = "expected_context_missing_due_to_wrong_source"
        stages = ["retrieval_context_available", "expected_context_missing_due_to_wrong_source"]
    elif missing_chunk:
        primary_stage = "expected_chunk_missing"
        stages = ["retrieval_context_available", "expected_chunk_missing"]
    else:
        primary_stage = "answerable_from_context"
        stages = ["retrieval_context_available", "answerable_from_context", "answer_eval_pending_live_llm"]
    return {
        "schema_version": "rag_text_namu_v4_answer_eval_row_v1",
        "phase": "R7_B4_NAMU_ANSWER_EVAL",
        "query_id": f"gold_seed_{index:04d}",
        "query": f"query {index}",
        "bucket": "text_policy_question" if not denominator else "text_fact_lookup",
        "label_status": "needs_review" if not denominator else "bound",
        "denominator_included": denominator,
        "primary_stage": primary_stage,
        "stages": stages,
        "expected_context_missing_due_to_wrong_source": wrong_source,
        "expected_chunk_missing": missing_chunk,
        "answerable_from_context": answerable,
        "answer_eval_pending_live_llm": answerable,
        "answer_generation_failure": False,
        "live_llm_run": False,
    }


def context_row(index: int, *, leak_disallowed_field: bool) -> dict[str, object]:
    denominator = index < 48
    if 30 <= index <= 39:
        taxonomy = "missing_expected_source"
    elif 40 <= index <= 47:
        taxonomy = "missing_expected_chunk"
    elif not denominator:
        taxonomy = "excluded_needs_review"
    else:
        taxonomy = "expected_context_present"
    expected_present = taxonomy == "expected_context_present"
    contexts = context_items(index)
    if leak_disallowed_field and index == 1:
        contexts[0]["embedding_text"] = "must not be used"
    return {
        "schema_version": "rag_text_namu_v4_context_assembly_v1",
        "phase": "R6_B3_NAMU_CONTEXT_ASSEMBLY",
        "query_id": f"gold_seed_{index:04d}",
        "query": f"query {index}",
        "bucket": "text_policy_question" if not denominator else "text_fact_lookup",
        "label_status": "needs_review" if not denominator else "bound",
        "denominator_included": denominator,
        "taxonomy": taxonomy,
        "failure_reasons": [] if expected_present else [taxonomy],
        "expected_page_ids": [f"page-{index}"],
        "expected_section_ids": [f"section-{index}"],
        "expected_chunk_ids": [f"chunk-{index}"],
        "expected_source_present": expected_present,
        "expected_section_present": expected_present,
        "expected_chunk_present": expected_present,
        "retrieval_result_count": len(contexts),
        "context_field": "chunk_text",
        "contexts": contexts,
        "context_count": len(contexts),
        "context_char_count": sum(len(item["text"]) for item in contexts),
        "truncated": False,
    }


def context_items(index: int) -> list[dict[str, object]]:
    expected_text = f"alpha beta gamma delta epsilon {index}"
    if index == 28:
        return [
            context_item(index, "other-28", 1, expected_text, expected=False),
            context_item(index, f"chunk-{index}", 2, "alpha", expected=True),
        ]
    if index == 29:
        return [context_item(index, f"chunk-{index}", 1, "alpha", expected=True)]
    if index <= 29:
        return [context_item(index, f"chunk-{index}", 1, expected_text, expected=True)]
    return [context_item(index, f"other-{index}", 1, "unrelated context", expected=False)]


def context_item(
    index: int, chunk_id: str, rank: int, text: str, *, expected: bool
) -> dict[str, object]:
    page_id = f"page-{index}" if expected else f"other-page-{index}"
    section_id = f"section-{index}" if expected else f"other-section-{index}"
    return {
        "rank": rank,
        "chunk_id": chunk_id,
        "doc_id": page_id,
        "page_id": page_id,
        "section_id": section_id,
        "section_path": ["Overview"],
        "title": f"Title {index}",
        "score": 1.0,
        "context_field": "chunk_text",
        "text": text,
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
