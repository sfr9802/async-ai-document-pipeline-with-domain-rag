"""Run Track B R8 B5-namu deterministic citation support diagnostics.

This phase consumes R7 deterministic answer-eval rows and R6 assembled
``contexts[].text`` rows. It does not call live answer generation or an optional
judge. Retrieval/context misses stay outside the citation denominator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent

DEFAULT_GOLD = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_text_namu_v4_v0.csv"
DEFAULT_ANSWER_REPORT = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_answer_eval_report.json"
)
DEFAULT_ANSWER_JSONL = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_answer_eval.jsonl"
)
DEFAULT_CONTEXT_REPORT = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_context_assembly_report.json"
)
DEFAULT_CONTEXT_JSONL = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_context_assembly.jsonl"
)
DEFAULT_RETRIEVAL_REPORT = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_retrieval_diagnostic_report.json"
)
DEFAULT_REPORT = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_citation_support_report.json"
)
DEFAULT_JSONL = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_citation_support.jsonl"
)

PHASE = "R8_B5_NAMU_CITATION_SUPPORT"
EXPECTED_QUERY_COUNT = 50
EXPECTED_POSITIVE_DENOMINATOR = 47
EXPECTED_NEEDS_REVIEW_EXCLUDED = 3
EXPECTED_CITATION_SUPPORT_DENOMINATOR = 29
EXPECTED_RETRIEVAL_CONTEXT_MISS_EXCLUDED = 18
CONTEXT_FIELD = "chunk_text"
DISALLOWED_CONTEXT_FIELDS = ["embedding_text", "text_for_embedding", "debug_text"]
POSITIVE_LABEL_STATUSES = {"bound"}
NEEDS_REVIEW_LABEL_STATUSES = {"needs_review"}
SUMMARY_SUPPORT_THRESHOLD = 0.25

SUPPORTED_BY_EXPECTED_CONTEXT = "SUPPORTED_BY_EXPECTED_CONTEXT"
SUPPORTED_BY_CONTEXT_BUT_EXPECTED_CHUNK_NOT_TOP_CITATION = (
    "SUPPORTED_BY_CONTEXT_BUT_EXPECTED_CHUNK_NOT_TOP_CITATION"
)
PARTIAL_SUPPORT = "PARTIAL_SUPPORT"
UNSUPPORTED_BY_CONTEXT = "UNSUPPORTED_BY_CONTEXT"
EXCLUDED_RETRIEVAL_CONTEXT_MISS = "EXCLUDED_RETRIEVAL_CONTEXT_MISS"
EXCLUDED_NEEDS_REVIEW = "EXCLUDED_NEEDS_REVIEW"

RETRIEVAL_CONTEXT_MISS_EXCLUSION_BUCKET = (
    "excluded_from_citation_denominator_due_to_retrieval_context_miss"
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_citation_support(
        gold=Path(args.gold),
        answer_report=Path(args.answer_report),
        answer_jsonl=Path(args.answer_jsonl),
        context_report=Path(args.context_report),
        context_jsonl=Path(args.context_jsonl),
        retrieval_report=Path(args.retrieval_report),
        report_path=Path(args.report),
        jsonl_path=Path(args.jsonl),
    )
    print_json(
        {
            "status": report["status"],
            "report": repo_relative(Path(args.report)),
            "jsonl": repo_relative(Path(args.jsonl)),
            "citation_support_denominator_count": report["citation_support_denominator_count"],
            "supported_count": report["supported_count"],
            "partial_support_count": report["partial_support_count"],
            "unsupported_count": report["unsupported_count"],
            "retrieval_context_miss_excluded_count": report[
                "retrieval_context_miss_excluded_count"
            ],
            "needs_review_excluded_count": report["needs_review_excluded_count"],
        }
    )
    return 0 if report["status"] in {"PASS", "PASS_WITH_WARNINGS"} else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--answer-report", default=str(DEFAULT_ANSWER_REPORT))
    parser.add_argument("--answer-jsonl", default=str(DEFAULT_ANSWER_JSONL))
    parser.add_argument("--context-report", default=str(DEFAULT_CONTEXT_REPORT))
    parser.add_argument("--context-jsonl", default=str(DEFAULT_CONTEXT_JSONL))
    parser.add_argument("--retrieval-report", default=str(DEFAULT_RETRIEVAL_REPORT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--jsonl", default=str(DEFAULT_JSONL))
    return parser.parse_args(argv)


def run_citation_support(
    *,
    gold: Path,
    answer_report: Path,
    answer_jsonl: Path,
    context_report: Path,
    context_jsonl: Path,
    retrieval_report: Path,
    report_path: Path,
    jsonl_path: Path,
) -> dict[str, Any]:
    run_id = utc_run_id()
    generated_at = utc_timestamp()
    gold_rows, gold_columns = read_csv_if_exists(gold)
    answer_rows = read_jsonl_if_exists(answer_jsonl)
    context_rows = read_jsonl_if_exists(context_jsonl)
    answer_payload = read_optional_json(answer_report)
    context_payload = read_optional_json(context_report)
    retrieval_payload = read_optional_json(retrieval_report)
    blockers = entry_gate_blockers(
        gold=gold,
        answer_report=answer_report,
        answer_jsonl=answer_jsonl,
        context_report=context_report,
        context_jsonl=context_jsonl,
        retrieval_report=retrieval_report,
        gold_rows=gold_rows,
        answer_rows=answer_rows,
        context_rows=context_rows,
        answer_payload=answer_payload,
        context_payload=context_payload,
        retrieval_payload=retrieval_payload,
    )

    citation_rows: list[dict[str, Any]] = []
    jsonl_sha: str | None = None
    if not blockers:
        gold_by_id = {clean(row.get("query_id")): row for row in gold_rows}
        answer_by_id = {clean(row.get("query_id")): row for row in answer_rows}
        context_by_id = {clean(row.get("query_id")): row for row in context_rows}
        for gold_row in gold_rows:
            query_id = clean(gold_row.get("query_id"))
            citation_rows.append(
                evaluate_citation_row(
                    gold=gold_by_id.get(query_id, {}),
                    answer_row=answer_by_id.get(query_id, {}),
                    context_row=context_by_id.get(query_id, {}),
                )
            )
        write_jsonl(jsonl_path, citation_rows)
        jsonl_sha = sha256_file(jsonl_path)

    metrics = metrics_from_rows(citation_rows, answer_payload)
    status = status_from(blockers, metrics)
    report = build_report(
        run_id=run_id,
        generated_at=generated_at,
        status=status,
        gold=gold,
        answer_report=answer_report,
        answer_jsonl=answer_jsonl,
        context_report=context_report,
        context_jsonl=context_jsonl,
        retrieval_report=retrieval_report,
        report_path=report_path,
        jsonl_path=jsonl_path,
        jsonl_sha256=jsonl_sha,
        gold_rows=gold_rows,
        gold_columns=gold_columns,
        answer_rows=answer_rows,
        context_rows=context_rows,
        citation_rows=citation_rows,
        metrics=metrics,
        blockers=blockers,
        warnings=warnings_from_metrics(metrics, blockers),
        answer_payload=answer_payload,
        context_payload=context_payload,
        retrieval_payload=retrieval_payload,
    )
    write_json(report_path, report)
    return report


def entry_gate_blockers(
    *,
    gold: Path,
    answer_report: Path,
    answer_jsonl: Path,
    context_report: Path,
    context_jsonl: Path,
    retrieval_report: Path,
    gold_rows: list[dict[str, str]],
    answer_rows: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
    answer_payload: Mapping[str, Any] | None,
    context_payload: Mapping[str, Any] | None,
    retrieval_payload: Mapping[str, Any] | None,
) -> list[str]:
    blockers: list[str] = []
    blockers.extend(required_input_blockers(gold, answer_report, answer_jsonl, context_report, context_jsonl, retrieval_report))
    if answer_report.exists() and answer_payload is None:
        blockers.append(f"{repo_relative(answer_report)} is not a JSON object")
    if context_report.exists() and context_payload is None:
        blockers.append(f"{repo_relative(context_report)} is not a JSON object")
    if retrieval_report.exists() and retrieval_payload is None:
        blockers.append(f"{repo_relative(retrieval_report)} is not a JSON object")
    if blockers:
        return blockers

    blockers.extend(
        expected_report_count_blockers(
            label="R7 answer eval report",
            payload=answer_payload,
            expected={
                "positive_denominator_count": EXPECTED_POSITIVE_DENOMINATOR,
                "needs_review_excluded_count": EXPECTED_NEEDS_REVIEW_EXCLUDED,
                "answerable_from_context_count": EXPECTED_CITATION_SUPPORT_DENOMINATOR,
                "retrieval_context_miss_count": EXPECTED_RETRIEVAL_CONTEXT_MISS_EXCLUDED,
                "answer_generation_failure_count": 0,
            },
        )
    )
    blockers.extend(
        expected_report_count_blockers(
            label="R6 context assembly report",
            payload=context_payload,
            expected={
                "positive_denominator_count": EXPECTED_POSITIVE_DENOMINATOR,
                "needs_review_excluded_count": EXPECTED_NEEDS_REVIEW_EXCLUDED,
                "expected_context_present_count": EXPECTED_CITATION_SUPPORT_DENOMINATOR,
                "missing_expected_source_count": 10,
                "missing_expected_chunk_count": 8,
            },
        )
    )
    blockers.extend(
        expected_report_count_blockers(
            label="R5 retrieval diagnostic report",
            payload=retrieval_payload,
            expected={
                "positive_denominator_count": EXPECTED_POSITIVE_DENOMINATOR,
                "needs_review_excluded_count": EXPECTED_NEEDS_REVIEW_EXCLUDED,
            },
        )
    )

    blockers.extend(query_id_consistency_blockers(gold_rows, answer_rows, context_rows))
    blockers.extend(answer_row_count_blockers(answer_rows))
    blockers.extend(context_field_blockers(context_rows))
    blockers.extend(source_policy_blockers(answer_payload, context_payload, retrieval_payload))
    blockers.extend(source_sha_blockers(answer_payload, answer_jsonl, context_payload, context_jsonl))
    return blockers


def required_input_blockers(*paths: Path) -> list[str]:
    return [f"missing required input: {repo_relative(path)}" for path in paths if not path.exists()]


def expected_report_count_blockers(
    *, label: str, payload: Mapping[str, Any] | None, expected: Mapping[str, int]
) -> list[str]:
    if payload is None:
        return [f"{label} is missing or invalid"]
    blockers: list[str] = []
    for field, expected_value in expected.items():
        actual = payload.get(field)
        if actual != expected_value:
            blockers.append(f"{label} {field} must be {expected_value}, got {actual}")
    return blockers


def query_id_consistency_blockers(
    gold_rows: list[dict[str, str]],
    answer_rows: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
) -> list[str]:
    blockers: list[str] = []
    gold_ids = [clean(row.get("query_id")) for row in gold_rows]
    answer_ids = [clean(row.get("query_id")) for row in answer_rows]
    context_ids = [clean(row.get("query_id")) for row in context_rows]
    if len(gold_ids) != EXPECTED_QUERY_COUNT:
        blockers.append(f"gold query count must be {EXPECTED_QUERY_COUNT}, got {len(gold_ids)}")
    if len(answer_ids) != EXPECTED_QUERY_COUNT:
        blockers.append(f"R7 answer JSONL row count must be {EXPECTED_QUERY_COUNT}, got {len(answer_ids)}")
    if len(context_ids) != EXPECTED_QUERY_COUNT:
        blockers.append(f"R6 context JSONL row count must be {EXPECTED_QUERY_COUNT}, got {len(context_ids)}")
    if len(set(gold_ids)) != len(gold_ids):
        blockers.append("gold query ids must be unique")
    if set(answer_ids) != set(gold_ids):
        blockers.append("R7 answer JSONL query ids must match gold query ids")
    if set(context_ids) != set(gold_ids):
        blockers.append("R6 context JSONL query ids must match gold query ids")
    return blockers


def answer_row_count_blockers(answer_rows: list[Mapping[str, Any]]) -> list[str]:
    answerable = [row for row in answer_rows if row.get("answerable_from_context") is True]
    needs_review = [row for row in answer_rows if not bool(row.get("denominator_included"))]
    retrieval_miss = [row for row in answer_rows if is_retrieval_context_miss(row)]
    blockers: list[str] = []
    if len(answerable) != EXPECTED_CITATION_SUPPORT_DENOMINATOR:
        blockers.append(
            "R7 answerable_from_context rows must be "
            f"{EXPECTED_CITATION_SUPPORT_DENOMINATOR}, got {len(answerable)}"
        )
    if len(retrieval_miss) != EXPECTED_RETRIEVAL_CONTEXT_MISS_EXCLUDED:
        blockers.append(
            "R7 retrieval/context miss rows must be "
            f"{EXPECTED_RETRIEVAL_CONTEXT_MISS_EXCLUDED}, got {len(retrieval_miss)}"
        )
    if len(needs_review) != EXPECTED_NEEDS_REVIEW_EXCLUDED:
        blockers.append(
            f"R7 needs_review excluded rows must be {EXPECTED_NEEDS_REVIEW_EXCLUDED}, got {len(needs_review)}"
        )
    partition_errors = answer_row_partition_errors(answer_rows)
    blockers.extend(partition_errors[:10])
    if len(partition_errors) > 10:
        blockers.append(f"R7 row partition has {len(partition_errors) - 10} additional errors")
    return blockers


def answer_row_partition_errors(answer_rows: list[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    for row in answer_rows:
        query_id = clean(row.get("query_id"))
        denominator = bool(row.get("denominator_included"))
        answerable = row.get("answerable_from_context") is True
        retrieval_miss = is_retrieval_context_miss(row)
        if not denominator:
            if answerable or retrieval_miss:
                errors.append(
                    f"{query_id}: needs_review/excluded R7 row must not also be answerable or retrieval miss"
                )
            continue
        if answerable and retrieval_miss:
            errors.append(f"{query_id}: R7 answerable row must not also be retrieval/context miss")
        if not answerable and not retrieval_miss:
            errors.append(
                f"{query_id}: positive R7 row must be either answerable_from_context or retrieval/context miss"
            )
    partition_total = sum(
        1
        for row in answer_rows
        if (
            not bool(row.get("denominator_included"))
            or row.get("answerable_from_context") is True
            or is_retrieval_context_miss(row)
        )
    )
    if partition_total != len(answer_rows):
        errors.append(
            f"R7 row partition must cover every row, covered {partition_total} of {len(answer_rows)}"
        )
    return errors


def context_field_blockers(context_rows: list[Mapping[str, Any]]) -> list[str]:
    blockers: list[str] = []
    disallowed = set(DISALLOWED_CONTEXT_FIELDS)
    for row in context_rows:
        query_id = clean(row.get("query_id"))
        if clean(row.get("context_field")) != CONTEXT_FIELD:
            blockers.append(f"{query_id}: row context_field must be chunk_text")
        contexts = row.get("contexts")
        if not isinstance(contexts, list):
            blockers.append(f"{query_id}: contexts must be a list")
            continue
        for index, context in enumerate(contexts):
            if not isinstance(context, Mapping):
                blockers.append(f"{query_id}: context[{index}] must be an object")
                continue
            if clean(context.get("context_field")) != CONTEXT_FIELD:
                blockers.append(f"{query_id}: context[{index}].context_field must be chunk_text")
            leaked_fields = sorted(disallowed.intersection(context.keys()))
            if leaked_fields:
                blockers.append(f"{query_id}: context[{index}] contains disallowed fields {leaked_fields}")
    return blockers


def source_policy_blockers(
    answer_payload: Mapping[str, Any] | None,
    context_payload: Mapping[str, Any] | None,
    retrieval_payload: Mapping[str, Any] | None,
) -> list[str]:
    blockers: list[str] = []
    if answer_payload:
        if answer_payload.get("promotion_evidence") is not False:
            blockers.append("R7 answer report promotion_evidence must be false")
        if answer_payload.get("live_llm_run") is not False:
            blockers.append("R7 answer report live_llm_run must be false")
        if answer_payload.get("optional_judge_run") is not False:
            blockers.append("R7 answer report optional_judge_run must be false")
        if answer_payload.get("answer_generation_failure_count") != 0:
            blockers.append("R7 answer_generation_failure_count must be 0")
    if context_payload:
        if context_payload.get("promotion_evidence") is not False:
            blockers.append("R6 context report promotion_evidence must be false")
        if context_payload.get("context_field") != CONTEXT_FIELD:
            blockers.append("R6 context report context_field must be chunk_text")
    if retrieval_payload:
        if retrieval_payload.get("promotion_evidence") is not False:
            blockers.append("R5 retrieval report promotion_evidence must be false")
        if retrieval_payload.get("llm_answer_eval_run") is True:
            blockers.append("R5 retrieval report must not include an LLM answer eval run")
        if retrieval_payload.get("citation_eval_run") is True:
            blockers.append("R5 retrieval report must not include a citation eval run")
    return blockers


def source_sha_blockers(
    answer_payload: Mapping[str, Any] | None,
    answer_jsonl: Path,
    context_payload: Mapping[str, Any] | None,
    context_jsonl: Path,
) -> list[str]:
    blockers: list[str] = []
    if answer_payload and answer_payload.get("answer_eval_jsonl_sha256"):
        actual = sha256_file(answer_jsonl)
        expected = clean(answer_payload.get("answer_eval_jsonl_sha256"))
        if actual != expected:
            blockers.append(f"R7 answer_eval_jsonl_sha256 mismatch: expected {expected}, got {actual}")
    if context_payload and context_payload.get("context_emit_sha256"):
        actual = sha256_file(context_jsonl)
        expected = clean(context_payload.get("context_emit_sha256"))
        if actual != expected:
            blockers.append(f"R6 context_emit_sha256 mismatch: expected {expected}, got {actual}")
    return blockers


def evaluate_citation_row(
    *,
    gold: Mapping[str, str],
    answer_row: Mapping[str, Any],
    context_row: Mapping[str, Any],
) -> dict[str, Any]:
    contexts = [item for item in list(context_row.get("contexts") or []) if isinstance(item, Mapping)]
    query_id = clean(gold.get("query_id") or answer_row.get("query_id") or context_row.get("query_id"))
    expected_page_ids = split_ids(gold.get("expected_page_ids")) or clean_list(context_row.get("expected_page_ids"))
    expected_section_ids = split_ids(gold.get("expected_section_ids")) or clean_list(
        context_row.get("expected_section_ids")
    )
    expected_chunk_ids = split_ids(gold.get("expected_chunk_ids")) or clean_list(
        context_row.get("expected_chunk_ids")
    )
    expected_section_path = expected_section_path_from_notes(gold.get("notes"))
    context_chunk_ids = [clean(item.get("chunk_id")) for item in contexts if clean(item.get("chunk_id"))]
    context_section_ids = [clean(item.get("section_id")) for item in contexts if clean(item.get("section_id"))]
    expected_evidence_chunk_present = bool(set(expected_chunk_ids).intersection(context_chunk_ids))
    expected_section_surface_present = bool(set(expected_section_ids).intersection(context_section_ids)) or bool(
        context_row.get("expected_section_present")
    )
    expected_section_path_surface_present = section_path_surface_present(
        expected_section_path=expected_section_path,
        contexts=contexts,
        fallback=expected_section_surface_present,
    )
    base = {
        "schema_version": "rag_text_namu_v4_citation_support_row_v1",
        "phase": PHASE,
        "query_id": query_id,
        "query": clean(gold.get("query") or answer_row.get("query") or context_row.get("query")),
        "bucket": clean(gold.get("bucket") or answer_row.get("bucket") or context_row.get("bucket")),
        "label_status": clean(gold.get("label_status") or answer_row.get("label_status") or context_row.get("label_status")),
        "context_field": CONTEXT_FIELD,
        "r7_primary_stage": clean(answer_row.get("primary_stage")),
        "r7_stages": list(answer_row.get("stages") or []),
        "r7_answerable_from_context": bool(answer_row.get("answerable_from_context")),
        "r7_answer_generation_failure": bool(answer_row.get("answer_generation_failure")),
        "deterministic_answer_coverage_status_from_r7": {
            "primary_stage": clean(answer_row.get("primary_stage")),
            "answerable_from_context": bool(answer_row.get("answerable_from_context")),
            "expected_context_missing_due_to_wrong_source": bool(
                answer_row.get("expected_context_missing_due_to_wrong_source")
            ),
            "expected_chunk_missing": bool(answer_row.get("expected_chunk_missing")),
            "answer_eval_pending_live_llm": bool(answer_row.get("answer_eval_pending_live_llm")),
            "live_llm_run": bool(answer_row.get("live_llm_run")),
        },
        "expected_evidence": {
            "expected_page_ids": expected_page_ids,
            "expected_section_ids": expected_section_ids,
            "expected_chunk_ids": expected_chunk_ids,
            "expected_section_path": expected_section_path,
        },
        "context_chunks_used": [context_item_summary(item) for item in contexts],
        "expected_evidence_chunk_present": expected_evidence_chunk_present,
        "expected_section_surface_present": expected_section_surface_present,
        "expected_section_path_surface_present": expected_section_path_surface_present,
        "diagnostic_only": True,
        "official_metric_input": False,
        "official_denominator_mutation": False,
    }

    if is_needs_review(gold) or not bool(answer_row.get("denominator_included")):
        return {
            **base,
            "citation_denominator_included": False,
            "citation_denominator_exclusion_bucket": "excluded_needs_review",
            "cited_supporting_chunk_ids": [],
            "supporting_chunk_evidence": [],
            "answer_summary_support": False,
            "unsupported_claim_candidate": False,
            "citation_support_status": EXCLUDED_NEEDS_REVIEW,
            "notes": "needs_review is excluded from the R8 citation support denominator.",
        }

    if is_retrieval_context_miss(answer_row):
        return {
            **base,
            "citation_denominator_included": False,
            "citation_denominator_exclusion_bucket": RETRIEVAL_CONTEXT_MISS_EXCLUSION_BUCKET,
            "cited_supporting_chunk_ids": [],
            "supporting_chunk_evidence": [],
            "answer_summary_support": False,
            "unsupported_claim_candidate": False,
            "citation_support_status": EXCLUDED_RETRIEVAL_CONTEXT_MISS,
            "notes": "retrieval/context miss is excluded from citation support failure counts.",
        }

    if answer_row.get("answerable_from_context") is not True:
        return {
            **base,
            "citation_denominator_included": False,
            "citation_denominator_exclusion_bucket": "unexpected_non_answerable_positive_row",
            "cited_supporting_chunk_ids": [],
            "supporting_chunk_evidence": [],
            "answer_summary_support": False,
            "unsupported_claim_candidate": False,
            "citation_support_status": UNSUPPORTED_BY_CONTEXT,
            "notes": "unexpected positive non-answerable row; entry gate should fail closed before writing rows.",
        }

    support = score_citation_support(
        contexts=contexts,
        expected_chunk_ids=expected_chunk_ids,
        expected_summary=clean(gold.get("expected_answer_summary")),
        must_contain_terms=split_terms(gold.get("must_contain_terms")),
    )
    return {
        **base,
        "citation_denominator_included": True,
        "citation_denominator_exclusion_bucket": None,
        "cited_supporting_chunk_ids": support["supporting_chunk_ids"],
        "supporting_chunk_evidence": support["supporting_chunk_evidence"],
        "top_supporting_chunk_id": support["top_supporting_chunk_id"],
        "expected_chunk_is_top_supporting_citation": support["expected_chunk_is_top_supporting_citation"],
        "expected_chunk_has_supporting_text": support["expected_chunk_has_supporting_text"],
        "answer_summary_support": support["answer_summary_support"],
        "answer_summary_support_threshold": SUMMARY_SUPPORT_THRESHOLD,
        "best_summary_coverage_ratio": support["best_summary_coverage_ratio"],
        "best_expected_chunk_summary_coverage_ratio": support[
            "best_expected_chunk_summary_coverage_ratio"
        ],
        "unsupported_claim_candidate": support["citation_support_status"]
        in {PARTIAL_SUPPORT, UNSUPPORTED_BY_CONTEXT},
        "citation_support_status": support["citation_support_status"],
        "notes": "Deterministic citation support used R6 contexts[].text only.",
    }


def score_citation_support(
    *,
    contexts: list[Mapping[str, Any]],
    expected_chunk_ids: list[str],
    expected_summary: str,
    must_contain_terms: list[str],
) -> dict[str, Any]:
    expected_chunks = set(expected_chunk_ids)
    summary_tokens = expected_summary_tokens(expected_summary)
    scored = [
        score_context_item(
            item=item,
            expected_chunks=expected_chunks,
            summary_tokens=summary_tokens,
            must_contain_terms=must_contain_terms,
        )
        for item in contexts
    ]
    scored.sort(key=lambda item: (-float(item["support_score"]), int(item["rank"] or 999999)))
    supporting = [item for item in scored if item["supporting"]]
    partial = [item for item in scored if item["partial_support_candidate"]]
    expected_scored = [item for item in scored if item["expected_chunk"]]
    top_supporting = supporting[0] if supporting else None
    expected_chunk_has_supporting_text = any(item["supporting"] for item in expected_scored)
    expected_chunk_is_top = bool(top_supporting and top_supporting["expected_chunk"])
    status = citation_status_for(
        supporting=bool(supporting),
        partial=bool(partial),
        expected_chunk_has_supporting_text=expected_chunk_has_supporting_text,
        expected_chunk_is_top=expected_chunk_is_top,
        expected_chunk_present=bool(expected_scored),
    )
    return {
        "citation_support_status": status,
        "answer_summary_support": bool(supporting),
        "supporting_chunk_ids": [clean(item["chunk_id"]) for item in supporting],
        "top_supporting_chunk_id": clean(top_supporting["chunk_id"]) if top_supporting else None,
        "expected_chunk_is_top_supporting_citation": expected_chunk_is_top,
        "expected_chunk_has_supporting_text": expected_chunk_has_supporting_text,
        "best_summary_coverage_ratio": float(scored[0]["summary_coverage_ratio"]) if scored else 0.0,
        "best_expected_chunk_summary_coverage_ratio": max(
            [float(item["summary_coverage_ratio"]) for item in expected_scored] or [0.0]
        ),
        "supporting_chunk_evidence": [
            evidence_item(item) for item in supporting[:5]
        ] or [evidence_item(item) for item in partial[:3]],
    }


def score_context_item(
    *,
    item: Mapping[str, Any],
    expected_chunks: set[str],
    summary_tokens: list[str],
    must_contain_terms: list[str],
) -> dict[str, Any]:
    text = clean(item.get("text"))
    matched_summary_tokens = [token for token in summary_tokens if contains_text(text, token)]
    matched_must_terms = [term for term in must_contain_terms if contains_text(text, term)]
    summary_coverage = safe_ratio(len(matched_summary_tokens), len(summary_tokens))
    support_score = summary_coverage + (0.25 if matched_must_terms else 0.0)
    supporting = summary_coverage >= SUMMARY_SUPPORT_THRESHOLD or bool(matched_must_terms)
    partial_support_candidate = not supporting and (bool(matched_summary_tokens) or bool(matched_must_terms))
    return {
        "rank": item.get("rank"),
        "chunk_id": clean(item.get("chunk_id")),
        "page_id": clean(item.get("page_id") or item.get("doc_id")),
        "section_id": clean(item.get("section_id")),
        "section_path": item.get("section_path") if isinstance(item.get("section_path"), list) else [],
        "title": clean(item.get("title")),
        "expected_chunk": clean(item.get("chunk_id")) in expected_chunks,
        "summary_coverage_ratio": summary_coverage,
        "matched_summary_tokens": matched_summary_tokens,
        "matched_must_contain_terms": matched_must_terms,
        "support_score": round(support_score, 6),
        "supporting": supporting,
        "partial_support_candidate": partial_support_candidate,
        "text_excerpt": text[:300],
    }


def citation_status_for(
    *,
    supporting: bool,
    partial: bool,
    expected_chunk_has_supporting_text: bool,
    expected_chunk_is_top: bool,
    expected_chunk_present: bool,
) -> str:
    if supporting and expected_chunk_has_supporting_text and expected_chunk_is_top:
        return SUPPORTED_BY_EXPECTED_CONTEXT
    if supporting and expected_chunk_present:
        return SUPPORTED_BY_CONTEXT_BUT_EXPECTED_CHUNK_NOT_TOP_CITATION
    if supporting:
        return SUPPORTED_BY_CONTEXT_BUT_EXPECTED_CHUNK_NOT_TOP_CITATION
    if partial:
        return PARTIAL_SUPPORT
    return UNSUPPORTED_BY_CONTEXT


def metrics_from_rows(
    rows: list[Mapping[str, Any]], answer_payload: Mapping[str, Any] | None
) -> dict[str, Any]:
    status_counts = Counter(clean(row.get("citation_support_status")) for row in rows)
    denominator_rows = [row for row in rows if row.get("citation_denominator_included")]
    official_metric_rows = [row for row in rows if row.get("official_metric_input") is True]
    # TEXT citation-support policy is still closed. Rows that accidentally set
    # official_metric_input=True are surfaced as leakage, not converted into an
    # official denominator by this diagnostic runner.
    official_denominator_rows: list[Mapping[str, Any]] = []
    supported_statuses = {
        SUPPORTED_BY_EXPECTED_CONTEXT,
        SUPPORTED_BY_CONTEXT_BUT_EXPECTED_CHUNK_NOT_TOP_CITATION,
    }
    supported_count = sum(1 for row in denominator_rows if row.get("citation_support_status") in supported_statuses)
    partial_count = sum(1 for row in denominator_rows if row.get("citation_support_status") == PARTIAL_SUPPORT)
    unsupported_count = sum(
        1 for row in denominator_rows if row.get("citation_support_status") == UNSUPPORTED_BY_CONTEXT
    )
    fallback = answer_payload or {}
    denominator_count = len(denominator_rows) or int(
        fallback.get("answerable_from_context_count") or 0
    )
    retrieval_excluded = status_counts[EXCLUDED_RETRIEVAL_CONTEXT_MISS] or int(
        fallback.get("retrieval_context_miss_count") or 0
    )
    needs_review_excluded = status_counts[EXCLUDED_NEEDS_REVIEW] or int(
        fallback.get("needs_review_excluded_count") or 0
    )
    return {
        "row_count": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "positive_denominator_count": int(fallback.get("positive_denominator_count") or EXPECTED_POSITIVE_DENOMINATOR),
        "needs_review_excluded_count": needs_review_excluded,
        "citation_support_denominator_count": denominator_count,
        "official_metric_input_rows": len(official_metric_rows),
        "official_citation_support_denominator_count": len(official_denominator_rows),
        "official_citation_support_metric_status": (
            "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY"
            if not official_metric_rows
            else "FAIL_CLOSED_OFFICIAL_POLICY_NOT_OPEN"
        ),
        "official_citation_support_rate": None,
        "retrieval_context_miss_excluded_count": retrieval_excluded,
        "supported_count": supported_count,
        "supported_by_expected_context_count": status_counts[SUPPORTED_BY_EXPECTED_CONTEXT],
        "supported_by_context_but_expected_chunk_not_top_citation_count": status_counts[
            SUPPORTED_BY_CONTEXT_BUT_EXPECTED_CHUNK_NOT_TOP_CITATION
        ],
        "partial_support_count": partial_count,
        "unsupported_count": unsupported_count,
        "citation_support_rate": safe_ratio(supported_count, denominator_count),
        "claim_support_rate": safe_ratio(supported_count, denominator_count),
        "unsupported_claim_count": sum(
            1 for row in denominator_rows if row.get("unsupported_claim_candidate")
        ),
        "missing_citation_count": sum(
            1 for row in denominator_rows if not row.get("cited_supporting_chunk_ids")
        ),
        "citation_not_in_retrieved_context_count": 0,
        "abstain_citation_violation_count": 0,
        "supported_query_ids": [
            clean(row.get("query_id")) for row in denominator_rows if row.get("citation_support_status") in supported_statuses
        ],
        "partial_support_query_ids": [
            clean(row.get("query_id")) for row in denominator_rows if row.get("citation_support_status") == PARTIAL_SUPPORT
        ],
        "unsupported_query_ids": [
            clean(row.get("query_id")) for row in denominator_rows if row.get("citation_support_status") == UNSUPPORTED_BY_CONTEXT
        ],
        "excluded_retrieval_context_miss_query_ids": [
            clean(row.get("query_id")) for row in rows if row.get("citation_support_status") == EXCLUDED_RETRIEVAL_CONTEXT_MISS
        ],
        "excluded_needs_review_query_ids": [
            clean(row.get("query_id")) for row in rows if row.get("citation_support_status") == EXCLUDED_NEEDS_REVIEW
        ],
    }


def status_from(blockers: list[str], metrics: Mapping[str, Any]) -> str:
    if blockers:
        return "FAIL"
    if int(metrics.get("official_metric_input_rows") or 0) != 0:
        return "FAIL"
    if (
        metrics.get("retrieval_context_miss_excluded_count")
        or metrics.get("needs_review_excluded_count")
        or metrics.get("partial_support_count")
        or metrics.get("unsupported_count")
    ):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def warnings_from_metrics(metrics: Mapping[str, Any], blockers: list[str]) -> list[str]:
    if blockers:
        return []
    warnings: list[str] = []
    if metrics.get("retrieval_context_miss_excluded_count"):
        warnings.append("R7 retrieval/context misses are excluded from the R8 citation denominator.")
    if metrics.get("needs_review_excluded_count"):
        warnings.append("needs_review rows remain excluded from the citation denominator.")
    if metrics.get("partial_support_count"):
        warnings.append("Some answerable rows have only partial deterministic citation support.")
    if metrics.get("unsupported_count"):
        warnings.append("Some answerable rows are unsupported by R6 contexts[].text.")
    warnings.append("Live LLM answer generation and optional judge were not run.")
    return warnings


def build_report(
    *,
    run_id: str,
    generated_at: str,
    status: str,
    gold: Path,
    answer_report: Path,
    answer_jsonl: Path,
    context_report: Path,
    context_jsonl: Path,
    retrieval_report: Path,
    report_path: Path,
    jsonl_path: Path,
    jsonl_sha256: str | None,
    gold_rows: list[dict[str, str]],
    gold_columns: list[str],
    answer_rows: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
    citation_rows: list[dict[str, Any]],
    metrics: Mapping[str, Any],
    blockers: list[str],
    warnings: list[str],
    answer_payload: Mapping[str, Any] | None,
    context_payload: Mapping[str, Any] | None,
    retrieval_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    answer_generation_failure_count = int((answer_payload or {}).get("answer_generation_failure_count") or 0)
    return {
        "run_id": run_id,
        "generated_at": generated_at,
        "schema_version": "rag_text_namu_v4_citation_support_report_v1",
        "status": status,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "phase": PHASE,
        "promotion_ready": False,
        "diagnostic_only": True,
        "citation_metric_role": "diagnostic_only",
        "live_llm_run": False,
        "optional_judge_run": False,
        "deterministic_citation_support_run": not blockers,
        "llm_answer_generation_run": False,
        "db_mutation_run": False,
        "indexing_run": False,
        "retrieval_tuning_run": False,
        "reranking_run": False,
        "corpus_mutation_run": False,
        "context_field": CONTEXT_FIELD,
        "used_context_json_path": "contexts[].text",
        "disallowed_context_fields": DISALLOWED_CONTEXT_FIELDS,
        "retrieval_context_misses_counted_as_citation_failures": False,
        "answer_generation_failure_count": answer_generation_failure_count,
        "answer_generation_failure_count_source": "R7 answer eval report",
        "gold_path": repo_relative(gold),
        "gold_csv_sha256": sha256_if_exists(gold),
        "gold_columns": gold_columns,
        "answer_eval_report_path": repo_relative(answer_report),
        "answer_eval_report_sha256": sha256_if_exists(answer_report),
        "answer_eval_jsonl_path": repo_relative(answer_jsonl),
        "answer_eval_jsonl_sha256": sha256_if_exists(answer_jsonl),
        "context_assembly_report_path": repo_relative(context_report),
        "context_assembly_report_sha256": sha256_if_exists(context_report),
        "context_assembly_jsonl_path": repo_relative(context_jsonl),
        "context_assembly_jsonl_sha256": sha256_if_exists(context_jsonl),
        "retrieval_diagnostic_report_path": repo_relative(retrieval_report),
        "retrieval_diagnostic_report_sha256": sha256_if_exists(retrieval_report),
        "citation_support_report_path": repo_relative(report_path),
        "citation_support_jsonl_path": repo_relative(jsonl_path),
        "citation_support_jsonl_sha256": jsonl_sha256,
        "query_count": len(gold_rows),
        "answer_eval_row_count": len(answer_rows),
        "context_assembly_row_count": len(context_rows),
        "citation_support_row_count": metrics.get("row_count", len(citation_rows)),
        "positive_denominator_count": metrics.get("positive_denominator_count", EXPECTED_POSITIVE_DENOMINATOR),
        "needs_review_excluded_count": metrics.get("needs_review_excluded_count", 0),
        "citation_support_denominator_count": metrics.get("citation_support_denominator_count", 0),
        "official_metric_input_rows": metrics.get("official_metric_input_rows", 0),
        "official_citation_support_denominator_count": metrics.get(
            "official_citation_support_denominator_count", 0
        ),
        "official_citation_support_metric_status": metrics.get(
            "official_citation_support_metric_status",
            "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY",
        ),
        "official_citation_support_rate": metrics.get("official_citation_support_rate"),
        "official_citation_support_metric_computed": False,
        "official_text_citation_denominator_opened": False,
        "official_text_citation_metric_input_required": True,
        "retrieval_context_miss_excluded_count": metrics.get(
            "retrieval_context_miss_excluded_count", 0
        ),
        "supported_count": metrics.get("supported_count", 0),
        "supported_by_expected_context_count": metrics.get("supported_by_expected_context_count", 0),
        "supported_by_context_but_expected_chunk_not_top_citation_count": metrics.get(
            "supported_by_context_but_expected_chunk_not_top_citation_count", 0
        ),
        "partial_support_count": metrics.get("partial_support_count", 0),
        "unsupported_count": metrics.get("unsupported_count", 0),
        "citation_support_rate": metrics.get("citation_support_rate"),
        "claim_support_rate": metrics.get("claim_support_rate"),
        "unsupported_claim_count": metrics.get("unsupported_claim_count", 0),
        "missing_citation_count": metrics.get("missing_citation_count", 0),
        "citation_not_in_retrieved_context_count": metrics.get(
            "citation_not_in_retrieved_context_count", 0
        ),
        "abstain_citation_violation_count": metrics.get("abstain_citation_violation_count", 0),
        "status_counts": metrics.get("status_counts", {}),
        "query_id_groups": {
            "supported": metrics.get("supported_query_ids", []),
            "partial_support": metrics.get("partial_support_query_ids", []),
            "unsupported": metrics.get("unsupported_query_ids", []),
            "excluded_retrieval_context_miss": metrics.get(
                "excluded_retrieval_context_miss_query_ids", []
            ),
            "excluded_needs_review": metrics.get("excluded_needs_review_query_ids", []),
        },
        "r7_denominator_lock": {
            "positive_denominator_count": (answer_payload or {}).get("positive_denominator_count"),
            "needs_review_excluded_count": (answer_payload or {}).get("needs_review_excluded_count"),
            "answerable_from_context_count": (answer_payload or {}).get("answerable_from_context_count"),
            "retrieval_context_miss_count": (answer_payload or {}).get("retrieval_context_miss_count"),
            "answer_generation_failure_count": answer_generation_failure_count,
        },
        "r6_handoff": {
            "status": (context_payload or {}).get("status"),
            "expected_context_present_count": (context_payload or {}).get("expected_context_present_count"),
            "missing_expected_source_count": (context_payload or {}).get("missing_expected_source_count"),
            "missing_expected_chunk_count": (context_payload or {}).get("missing_expected_chunk_count"),
            "context_field": (context_payload or {}).get("context_field"),
        },
        "r5_handoff": {
            "status": (retrieval_payload or {}).get("status"),
            "positive_denominator_count": (retrieval_payload or {}).get("positive_denominator_count"),
            "needs_review_excluded_count": (retrieval_payload or {}).get("needs_review_excluded_count"),
        },
        "context_source_policy": {
            "allowed_source_field": CONTEXT_FIELD,
            "used_context_json_path": "contexts[].text",
            "disallowed_context_fields": DISALLOWED_CONTEXT_FIELDS,
            "embedding_text_used": False,
            "text_for_embedding_used": False,
            "debug_text_used": False,
        },
        "done_criteria": {
            "source_reports_parsed": bool(answer_payload and context_payload and retrieval_payload),
            "r8_jsonl_row_count_matches_gold": len(citation_rows) == len(gold_rows) if citation_rows else False,
            "query_ids_consistent": bool(citation_rows)
            and {row["query_id"] for row in citation_rows}
            == {clean(row.get("query_id")) for row in gold_rows},
            "support_denominator_is_29": metrics.get("citation_support_denominator_count")
            == EXPECTED_CITATION_SUPPORT_DENOMINATOR,
            "retrieval_context_miss_exclusion_is_18": metrics.get(
                "retrieval_context_miss_excluded_count"
            )
            == EXPECTED_RETRIEVAL_CONTEXT_MISS_EXCLUDED,
            "needs_review_exclusion_is_3": metrics.get("needs_review_excluded_count")
            == EXPECTED_NEEDS_REVIEW_EXCLUDED,
            "chunk_text_only": True,
            "disallowed_context_fields_not_used": not blockers,
            "retrieval_context_misses_not_counted_as_citation_failures": True,
            "answer_generation_failure_count_quoted_from_r7": answer_generation_failure_count == 0,
            "official_metric_input_rows_zero_fails_closed": metrics.get("official_metric_input_rows") == 0,
            "diagnostic_citation_support_is_not_official_metric": True,
            "promotion_not_run": True,
            "live_llm_not_run": True,
            "optional_judge_not_run": True,
            "retrieval_tuning_not_run": True,
            "reranking_not_run": True,
            "corpus_mutation_not_run": True,
            "indexing_not_run": True,
            "db_mutation_not_run": True,
        },
        "blockers": blockers,
        "warnings": warnings,
        "next_phase_recommendation": (
            "Keep R8 diagnostic-only; do not treat citation support as promotion evidence."
            if status in {"PASS", "PASS_WITH_WARNINGS"}
            else "Keep R8 blocked until source artifact contract issues are resolved."
        ),
    }


def context_item_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    text = clean(item.get("text"))
    return {
        "rank": item.get("rank"),
        "chunk_id": clean(item.get("chunk_id")),
        "doc_id": clean(item.get("doc_id")),
        "page_id": clean(item.get("page_id") or item.get("doc_id")),
        "section_id": clean(item.get("section_id")),
        "section_path": item.get("section_path") if isinstance(item.get("section_path"), list) else [],
        "title": clean(item.get("title")),
        "score": item.get("score"),
        "context_field": CONTEXT_FIELD,
        "text_excerpt": text[:300],
    }


def evidence_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rank": item.get("rank"),
        "chunk_id": clean(item.get("chunk_id")),
        "page_id": clean(item.get("page_id")),
        "section_id": clean(item.get("section_id")),
        "expected_chunk": bool(item.get("expected_chunk")),
        "summary_coverage_ratio": item.get("summary_coverage_ratio"),
        "matched_summary_tokens": item.get("matched_summary_tokens", []),
        "matched_must_contain_terms": item.get("matched_must_contain_terms", []),
        "text_excerpt": clean(item.get("text_excerpt")),
    }


def is_retrieval_context_miss(row: Mapping[str, Any]) -> bool:
    primary_stage = clean(row.get("primary_stage"))
    return bool(
        row.get("expected_context_missing_due_to_wrong_source")
        or row.get("expected_chunk_missing")
        or primary_stage in {"expected_context_missing_due_to_wrong_source", "expected_chunk_missing"}
    )


def expected_summary_tokens(summary: str) -> list[str]:
    tokens = re.findall(r"[0-9A-Za-z가-힣]+", summary.lower())
    stopwords = {"으로", "하는", "있다", "이다", "한다", "대한", "중", "및"}
    unique: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if len(token) < 2 or token in stopwords:
            continue
        if token not in seen:
            seen.add(token)
            unique.append(token)
    return unique


def split_terms(value: object) -> list[str]:
    text = clean(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[;|]", text) if part.strip()]


def split_ids(value: object) -> list[str]:
    text = clean(value)
    if not text:
        return []
    normalized = text.replace("|", ";").replace(",", ";")
    return [part.strip() for part in normalized.split(";") if part.strip()]


def clean_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    return split_ids(value)


def expected_section_path_from_notes(value: object) -> str:
    text = clean(value)
    match = re.search(r"(?:^|;\s*)expected_section_path=([^;]+)", text)
    return clean(match.group(1)) if match else ""


def section_path_surface_present(
    *, expected_section_path: str, contexts: list[Mapping[str, Any]], fallback: bool
) -> bool:
    if not expected_section_path:
        return fallback
    for item in contexts:
        path = item.get("section_path")
        if isinstance(path, list) and contains_text(" > ".join(clean(part) for part in path), expected_section_path):
            return True
    return False


def contains_text(haystack: str, needle: str) -> bool:
    text = normalize_text(haystack)
    term = normalize_text(needle)
    if not term:
        return True
    return term in text or term.replace(" ", "") in text.replace(" ", "")


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", clean(value).lower())


def safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 6)


def read_csv_if_exists(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def read_jsonl_if_exists(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def print_json(payload: Mapping[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def denominator_included(row: Mapping[str, str]) -> bool:
    return clean(row.get("label_status")).lower() in POSITIVE_LABEL_STATUSES and not parse_bool(row.get("allowed_abstain"))


def is_needs_review(row: Mapping[str, str]) -> bool:
    return clean(row.get("label_status")).lower() in NEEDS_REVIEW_LABEL_STATUSES


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def parse_bool(value: object) -> bool:
    return clean(value).lower() == "true"


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_if_exists(path: Path) -> str | None:
    return sha256_file(path) if path.exists() else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
