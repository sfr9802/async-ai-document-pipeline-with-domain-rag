"""Run Track B R7 B4-namu deterministic answerability diagnostics.

This phase consumes R6 context assembly output and R3 gold rows. By default it
does not call a live LLM or judge. It keeps retrieval/context misses separate
from answer coverage so R5/R6 retrieval misses are not counted as answer
generation failures.
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
DEFAULT_CONTEXT_JSONL = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_text_namu_v4_context_assembly.jsonl"
)
DEFAULT_CONTEXT_REPORT = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_text_namu_v4_context_assembly_report.json"
)
DEFAULT_REPORT = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_text_namu_v4_answer_eval_report.json"
)
DEFAULT_JSONL = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_text_namu_v4_answer_eval.jsonl"
)

PHASE = "R7_B4_NAMU_ANSWER_EVAL"
EXPECTED_QUERY_COUNT = 50
EXPECTED_POSITIVE_DENOMINATOR = 47
EXPECTED_NEEDS_REVIEW_EXCLUDED = 3
EXPECTED_NEEDS_REVIEW_QUERY_IDS = ["gold_seed_0048", "gold_seed_0049", "gold_seed_0050"]
CONTEXT_FIELD = "chunk_text"
DISALLOWED_CONTEXT_FIELDS = {"embedding_text", "text_for_embedding", "debug_text"}
POSITIVE_LABEL_STATUSES = {"bound"}
NEEDS_REVIEW_LABEL_STATUSES = {"needs_review"}
SUMMARY_COVERAGE_THRESHOLD = 0.25

PROMPT_TEMPLATE = """Use only the provided chunk_text context to answer the user query.
If the context is insufficient, abstain. Return a short Korean answer with
supporting chunk ids."""


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_answer_eval(
        gold=Path(args.gold),
        context_jsonl=Path(args.context_jsonl),
        context_report=Path(args.context_report),
        report_path=Path(args.report),
        jsonl_path=Path(args.jsonl),
        enable_live_llm=args.enable_live_llm,
    )
    print_json(
        {
            "status": report["status"],
            "report": repo_relative(Path(args.report)),
            "jsonl": repo_relative(Path(args.jsonl)),
            "positive_denominator_count": report["positive_denominator_count"],
            "needs_review_excluded_count": report["needs_review_excluded_count"],
            "answerable_from_context_count": report["answerable_from_context_count"],
            "retrieval_context_miss_count": report["retrieval_context_miss_count"],
            "live_llm_run": report["live_llm_run"],
        }
    )
    return 0 if report["status"] in {"PASS", "PASS_WITH_WARNINGS"} else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--context-jsonl", default=str(DEFAULT_CONTEXT_JSONL))
    parser.add_argument("--context-report", default=str(DEFAULT_CONTEXT_REPORT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--jsonl", default=str(DEFAULT_JSONL))
    parser.add_argument(
        "--enable-live-llm",
        action="store_true",
        help="Reserved for a future live judge. The current implementation records this as a blocker.",
    )
    return parser.parse_args(argv)


def run_answer_eval(
    *,
    gold: Path,
    context_jsonl: Path,
    context_report: Path,
    report_path: Path,
    jsonl_path: Path,
    enable_live_llm: bool = False,
) -> dict[str, Any]:
    run_id = utc_run_id()
    generated_at = utc_timestamp()
    gold_rows, gold_columns = read_csv_if_exists(gold)
    context_rows = read_jsonl_if_exists(context_jsonl)
    context_payload = read_optional_json(context_report)
    blockers = entry_gate_blockers(
        gold_rows=gold_rows,
        context_rows=context_rows,
        context_report=context_payload,
        context_jsonl=context_jsonl,
        enable_live_llm=enable_live_llm,
    )

    answer_rows: list[dict[str, Any]] = []
    if not blockers:
        gold_by_id = {clean(row.get("query_id")): row for row in gold_rows}
        for context_row in context_rows:
            query_id = clean(context_row.get("query_id"))
            answer_rows.append(evaluate_row(gold_by_id.get(query_id, {}), context_row))

    metrics = metrics_from_rows(gold_rows, answer_rows)
    status = "FAIL" if blockers else "PASS_WITH_WARNINGS" if warning_needed(metrics) else "PASS"
    if not blockers:
        write_jsonl(jsonl_path, answer_rows)
        jsonl_sha = sha256_file(jsonl_path)
    else:
        jsonl_sha = None

    report = build_report(
        run_id=run_id,
        generated_at=generated_at,
        status=status,
        gold=gold,
        context_jsonl=context_jsonl,
        context_report=context_report,
        jsonl_path=jsonl_path,
        jsonl_sha256=jsonl_sha,
        gold_rows=gold_rows,
        gold_columns=gold_columns,
        context_rows=context_rows,
        metrics=metrics,
        blockers=blockers,
        warnings=warnings_from_metrics(metrics, blockers),
        context_payload=context_payload,
        enable_live_llm=enable_live_llm,
    )
    write_json(report_path, report)
    return report


def entry_gate_blockers(
    *,
    gold_rows: list[dict[str, str]],
    context_rows: list[dict[str, Any]],
    context_report: Mapping[str, Any] | None,
    context_jsonl: Path,
    enable_live_llm: bool,
) -> list[str]:
    blockers: list[str] = []
    if enable_live_llm:
        blockers.append("live LLM judge is intentionally not implemented in R7 deterministic mode")
    if not gold_rows:
        blockers.append("R3 gold CSV is missing or empty")
    if len(gold_rows) != EXPECTED_QUERY_COUNT:
        blockers.append(f"gold query_count mismatch: {len(gold_rows)} != {EXPECTED_QUERY_COUNT}")
    positive_count = sum(1 for row in gold_rows if denominator_included(row))
    needs_review_count = sum(1 for row in gold_rows if is_needs_review(row))
    needs_review_ids = [clean(row.get("query_id")) for row in gold_rows if is_needs_review(row)]
    if positive_count != EXPECTED_POSITIVE_DENOMINATOR:
        blockers.append(f"positive denominator mismatch: {positive_count} != {EXPECTED_POSITIVE_DENOMINATOR}")
    if needs_review_count != EXPECTED_NEEDS_REVIEW_EXCLUDED:
        blockers.append(f"needs_review count mismatch: {needs_review_count} != {EXPECTED_NEEDS_REVIEW_EXCLUDED}")
    if needs_review_ids != EXPECTED_NEEDS_REVIEW_QUERY_IDS:
        blockers.append(f"needs_review query ids mismatch: {needs_review_ids} != {EXPECTED_NEEDS_REVIEW_QUERY_IDS}")

    if context_report is None:
        blockers.append("R6 context assembly report is missing or invalid JSON")
    else:
        expected = {
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "context_field": CONTEXT_FIELD,
            "positive_denominator_count": EXPECTED_POSITIVE_DENOMINATOR,
            "needs_review_excluded_count": EXPECTED_NEEDS_REVIEW_EXCLUDED,
            "r7_ready": True,
            "llm_answer_eval_run": False,
            "citation_eval_run": False,
            "promotion_run": False,
            "indexing_run": False,
        }
        if context_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
            blockers.append(f"R6 status is {context_report.get('status')}, not PASS/PASS_WITH_WARNINGS")
        for field, value in expected.items():
            if context_report.get(field) != value:
                blockers.append(f"R6 contract mismatch: {field}={context_report.get(field)!r}, expected {value!r}")
        report_context_path = clean(context_report.get("context_emit_path"))
        if report_context_path and not same_path_or_string(report_context_path, context_jsonl):
            blockers.append(
                "R6 context_emit_path mismatch: "
                f"report has {report_context_path}, script uses {repo_relative(context_jsonl)}"
            )
        report_context_sha = clean(context_report.get("context_emit_sha256"))
        if not report_context_sha:
            blockers.append("R6 contract mismatch: context_emit_sha256 is missing")
        elif context_jsonl.exists():
            actual_sha = sha256_file(context_jsonl)
            if report_context_sha != actual_sha:
                blockers.append(
                    f"R6 context_emit_sha256 mismatch: report has {report_context_sha}, actual is {actual_sha}"
                )

    if not context_jsonl.exists():
        blockers.append(f"R6 context JSONL missing: {repo_relative(context_jsonl)}")
    elif len(context_rows) != EXPECTED_QUERY_COUNT:
        blockers.append(f"R6 context row count mismatch: {len(context_rows)} != {EXPECTED_QUERY_COUNT}")
    blockers.extend(context_field_blockers(context_rows))
    return blockers


def context_field_blockers(context_rows: list[Mapping[str, Any]]) -> list[str]:
    blockers: list[str] = []
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
            leaked_fields = sorted(DISALLOWED_CONTEXT_FIELDS.intersection(context.keys()))
            if leaked_fields:
                blockers.append(f"{query_id}: context[{index}] contains disallowed fields {leaked_fields}")
    return blockers


def evaluate_row(gold: Mapping[str, str], context_row: Mapping[str, Any]) -> dict[str, Any]:
    contexts = [item for item in list(context_row.get("contexts") or []) if isinstance(item, Mapping)]
    context_text = "\n".join(clean(item.get("text")) for item in contexts)
    must_terms = split_terms(gold.get("must_contain_terms"))
    must_not_terms = split_terms(gold.get("must_not_contain_terms"))
    expected_summary = clean(gold.get("expected_answer_summary"))
    summary_tokens = expected_summary_tokens(expected_summary)
    matched_summary_tokens = [token for token in summary_tokens if contains_text(context_text, token)]
    missing_summary_tokens = [token for token in summary_tokens if token not in matched_summary_tokens]
    matched_must_terms = [term for term in must_terms if contains_text(context_text, term)]
    missing_must_terms = [term for term in must_terms if term not in matched_must_terms]
    must_not_violations = [term for term in must_not_terms if contains_text(context_text, term)]
    expected_chunk_ids = split_ids(gold.get("expected_chunk_ids")) or list(context_row.get("expected_chunk_ids") or [])
    context_chunk_ids = [clean(item.get("chunk_id")) for item in contexts if clean(item.get("chunk_id"))]
    denominator = bool(context_row.get("denominator_included"))
    retrieval_context_available = denominator and int(context_row.get("context_count") or 0) > 0
    wrong_source = denominator and clean(context_row.get("taxonomy")) == "missing_expected_source"
    missing_chunk = denominator and clean(context_row.get("taxonomy")) == "missing_expected_chunk"
    expected_chunk_present = bool(context_row.get("expected_chunk_present"))
    must_contain_pass = not must_terms or not missing_must_terms
    must_not_pass = not must_not_violations
    summary_coverage = safe_ratio(len(matched_summary_tokens), len(summary_tokens))
    support_possible = (
        retrieval_context_available
        and expected_chunk_present
        and must_not_pass
        and (must_contain_pass or summary_coverage >= SUMMARY_COVERAGE_THRESHOLD)
    )
    primary_stage = primary_stage_for(
        denominator=denominator,
        wrong_source=wrong_source,
        missing_chunk=missing_chunk,
        support_possible=support_possible,
        retrieval_context_available=retrieval_context_available,
    )
    stages = stage_flags_for(
        denominator=denominator,
        retrieval_context_available=retrieval_context_available,
        wrong_source=wrong_source,
        missing_chunk=missing_chunk,
        support_possible=support_possible,
    )
    answer_eval_pending_live_llm = support_possible

    return {
        "schema_version": "rag_text_namu_v4_answer_eval_row_v1",
        "phase": PHASE,
        "query_id": clean(context_row.get("query_id") or gold.get("query_id")),
        "query": clean(context_row.get("query") or gold.get("query")),
        "bucket": clean(context_row.get("bucket") or gold.get("bucket")),
        "label_status": clean(context_row.get("label_status") or gold.get("label_status")),
        "allowed_abstain": parse_bool(gold.get("allowed_abstain")) or bool(context_row.get("allowed_abstain")),
        "denominator_included": denominator,
        "denominator_exclusion_reason": context_row.get("denominator_exclusion_reason"),
        "primary_stage": primary_stage,
        "stages": stages,
        "retrieval_context_available": retrieval_context_available,
        "expected_context_missing_due_to_wrong_source": wrong_source,
        "expected_chunk_missing": missing_chunk,
        "answerable_from_context": support_possible,
        "not_answerable_from_context": denominator and retrieval_context_available and not support_possible and not wrong_source and not missing_chunk,
        "answer_eval_pending_live_llm": answer_eval_pending_live_llm,
        "answer_generation_failure": False,
        "live_llm_run": False,
        "deterministic_judge_run": True,
        "r6_taxonomy": context_row.get("taxonomy"),
        "r6_failure_reasons": list(context_row.get("failure_reasons") or []),
        "context_field": CONTEXT_FIELD,
        "context_count": context_row.get("context_count"),
        "context_char_count": context_row.get("context_char_count"),
        "retrieval_result_count": context_row.get("retrieval_result_count"),
        "expected_evidence_surface": {
            "expected_page_ids": split_ids(gold.get("expected_page_ids")) or list(context_row.get("expected_page_ids") or []),
            "expected_section_ids": split_ids(gold.get("expected_section_ids")) or list(context_row.get("expected_section_ids") or []),
            "expected_chunk_ids": expected_chunk_ids,
            "expected_source_present": bool(context_row.get("expected_source_present")),
            "expected_section_present": bool(context_row.get("expected_section_present")),
            "expected_chunk_present": expected_chunk_present,
            "context_chunk_ids": context_chunk_ids,
        },
        "deterministic_checks": {
            "must_contain_terms": {
                "expected": must_terms,
                "matched": matched_must_terms,
                "missing": missing_must_terms,
                "pass": must_contain_pass,
            },
            "must_not_contain_terms": {
                "expected_absent": must_not_terms,
                "violations": must_not_violations,
                "pass": must_not_pass,
            },
            "expected_answer_summary_surface": {
                "summary": expected_summary,
                "token_count": len(summary_tokens),
                "matched_token_count": len(matched_summary_tokens),
                "coverage_ratio": summary_coverage,
                "matched_tokens": matched_summary_tokens,
                "missing_tokens": missing_summary_tokens,
            },
            "context_support_possible": support_possible,
        },
        "context_supporting_items": [context_item_summary(item) for item in contexts[:5]],
        "notes": (
            "Retrieval/context miss is preserved from R6 and is not counted as answer generation failure."
            if wrong_source or missing_chunk
            else "Deterministic answerability check used chunk_text context only."
        ),
    }


def primary_stage_for(
    *,
    denominator: bool,
    wrong_source: bool,
    missing_chunk: bool,
    support_possible: bool,
    retrieval_context_available: bool,
) -> str:
    if not denominator:
        return "denominator_excluded_needs_review"
    if wrong_source:
        return "expected_context_missing_due_to_wrong_source"
    if missing_chunk:
        return "expected_chunk_missing"
    if support_possible:
        return "answerable_from_context"
    if retrieval_context_available:
        return "not_answerable_from_context"
    return "not_answerable_from_context"


def stage_flags_for(
    *,
    denominator: bool,
    retrieval_context_available: bool,
    wrong_source: bool,
    missing_chunk: bool,
    support_possible: bool,
) -> list[str]:
    if not denominator:
        return ["denominator_excluded_needs_review"]
    stages: list[str] = []
    if retrieval_context_available:
        stages.append("retrieval_context_available")
    if wrong_source:
        stages.append("expected_context_missing_due_to_wrong_source")
    if missing_chunk:
        stages.append("expected_chunk_missing")
    if support_possible:
        stages.append("answerable_from_context")
        stages.append("answer_eval_pending_live_llm")
    elif retrieval_context_available and not wrong_source and not missing_chunk:
        stages.append("not_answerable_from_context")
    return stages


def context_item_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    text = clean(item.get("text"))
    return {
        "rank": item.get("rank"),
        "chunk_id": clean(item.get("chunk_id")),
        "doc_id": clean(item.get("doc_id")),
        "page_id": clean(item.get("page_id")),
        "section_id": clean(item.get("section_id")),
        "section_path": item.get("section_path") if isinstance(item.get("section_path"), list) else [],
        "title": clean(item.get("title")),
        "score": item.get("score"),
        "context_field": CONTEXT_FIELD,
        "text_excerpt": text[:300],
    }


def metrics_from_rows(gold_rows: list[dict[str, str]], answer_rows: list[dict[str, Any]]) -> dict[str, Any]:
    primary_counts = Counter(row.get("primary_stage") for row in answer_rows)
    stage_counts: Counter[str] = Counter()
    bucket_stage_counts: dict[str, Counter[str]] = {}
    for row in answer_rows:
        stage_counts.update(row.get("stages") or [])
        bucket = clean(row.get("bucket")) or "unknown"
        bucket_stage_counts.setdefault(bucket, Counter()).update([clean(row.get("primary_stage"))])

    positive_rows = [row for row in answer_rows if row.get("denominator_included")]
    needs_review_ids = [clean(row.get("query_id")) for row in answer_rows if not row.get("denominator_included")]
    answerable_rows = [row for row in positive_rows if row.get("answerable_from_context")]
    not_answerable_rows = [row for row in positive_rows if row.get("not_answerable_from_context")]
    wrong_source_rows = [
        row for row in positive_rows if row.get("expected_context_missing_due_to_wrong_source")
    ]
    missing_chunk_rows = [row for row in positive_rows if row.get("expected_chunk_missing")]

    must_rows = [
        row for row in positive_rows
        if (row.get("deterministic_checks") or {}).get("must_contain_terms", {}).get("expected")
    ]
    must_pass_rows = [
        row for row in must_rows
        if (row.get("deterministic_checks") or {}).get("must_contain_terms", {}).get("pass")
    ]
    must_not_rows = [
        row for row in positive_rows
        if (row.get("deterministic_checks") or {}).get("must_not_contain_terms", {}).get("expected_absent")
    ]
    must_not_pass_rows = [
        row for row in must_not_rows
        if (row.get("deterministic_checks") or {}).get("must_not_contain_terms", {}).get("pass")
    ]
    coverage_values = [
        float((row.get("deterministic_checks") or {}).get("expected_answer_summary_surface", {}).get("coverage_ratio") or 0.0)
        for row in positive_rows
    ]

    return {
        "query_count": len(gold_rows) if gold_rows else len(answer_rows),
        "context_row_count": len(answer_rows),
        "positive_denominator_count": sum(1 for row in gold_rows if denominator_included(row)),
        "needs_review_excluded_count": sum(1 for row in gold_rows if is_needs_review(row)),
        "needs_review_query_ids": [clean(row.get("query_id")) for row in gold_rows if is_needs_review(row)]
        or needs_review_ids,
        "primary_stage_counts": dict(sorted(primary_counts.items())),
        "stage_counts": dict(sorted(stage_counts.items())),
        "bucket_primary_stage_counts": {
            bucket: dict(sorted(counts.items())) for bucket, counts in sorted(bucket_stage_counts.items())
        },
        "retrieval_context_available_count": stage_counts["retrieval_context_available"],
        "expected_context_missing_due_to_wrong_source_count": len(wrong_source_rows),
        "expected_chunk_missing_count": len(missing_chunk_rows),
        "retrieval_context_miss_count": len(wrong_source_rows) + len(missing_chunk_rows),
        "answerable_from_context_count": len(answerable_rows),
        "not_answerable_from_context_count": len(not_answerable_rows),
        "answer_eval_pending_live_llm_count": stage_counts["answer_eval_pending_live_llm"],
        "answer_generation_failure_count": 0,
        "must_contain_evaluated_count": len(must_rows),
        "must_contain_pass_count": len(must_pass_rows),
        "must_contain_pass_rate": safe_ratio(len(must_pass_rows), len(must_rows)),
        "must_not_contain_evaluated_count": len(must_not_rows),
        "must_not_contain_pass_count": len(must_not_pass_rows),
        "must_not_contain_pass_rate": safe_ratio(len(must_not_pass_rows), len(must_not_rows)),
        "expected_answer_summary_coverage_avg": round(sum(coverage_values) / len(coverage_values), 6)
        if coverage_values
        else None,
        "answerable_query_ids": [row["query_id"] for row in answerable_rows],
        "not_answerable_query_ids": [row["query_id"] for row in not_answerable_rows],
        "wrong_source_query_ids": [row["query_id"] for row in wrong_source_rows],
        "missing_expected_chunk_query_ids": [row["query_id"] for row in missing_chunk_rows],
    }


def warning_needed(metrics: Mapping[str, Any]) -> bool:
    return bool(
        metrics.get("retrieval_context_miss_count")
        or metrics.get("not_answerable_from_context_count")
        or metrics.get("needs_review_excluded_count")
    )


def warnings_from_metrics(metrics: Mapping[str, Any], blockers: list[str]) -> list[str]:
    if blockers:
        return []
    warnings: list[str] = []
    if metrics.get("retrieval_context_miss_count"):
        warnings.append("R5/R6 retrieval/context misses are preserved separately from answer failures.")
    if metrics.get("not_answerable_from_context_count"):
        warnings.append("Some expected-context-present rows are not deterministically answerable from chunk_text.")
    if metrics.get("answer_eval_pending_live_llm_count"):
        warnings.append("Live LLM answer generation/judging was not run; deterministic coverage only.")
    return warnings


def build_report(
    *,
    run_id: str,
    generated_at: str,
    status: str,
    gold: Path,
    context_jsonl: Path,
    context_report: Path,
    jsonl_path: Path,
    jsonl_sha256: str | None,
    gold_rows: list[dict[str, str]],
    gold_columns: list[str],
    context_rows: list[dict[str, Any]],
    metrics: Mapping[str, Any],
    blockers: list[str],
    warnings: list[str],
    context_payload: Mapping[str, Any] | None,
    enable_live_llm: bool,
) -> dict[str, Any]:
    prompt_sha = hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()
    return {
        "run_id": run_id,
        "generated_at": generated_at,
        "schema_version": "rag_text_namu_v4_answer_eval_report_v1",
        "status": status,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "context_field": CONTEXT_FIELD,
        "used_context_json_path": "contexts[].text",
        "phase": PHASE,
        "gold_path": repo_relative(gold),
        "gold_csv_sha256": sha256_if_exists(gold),
        "gold_columns": gold_columns,
        "context_jsonl_path": repo_relative(context_jsonl),
        "context_jsonl_sha256": sha256_if_exists(context_jsonl),
        "context_report_path": repo_relative(context_report),
        "context_report_sha256": sha256_if_exists(context_report),
        "answer_eval_jsonl_path": repo_relative(jsonl_path),
        "answer_eval_jsonl_sha256": jsonl_sha256,
        "llm_model": "none_deterministic_dry_run",
        "temperature": 0,
        "prompt_template_sha256": prompt_sha,
        "prompt_template_role": "recorded_for_future_live_llm_only",
        "live_llm_requested": enable_live_llm,
        "live_llm_run": False,
        "optional_judge_run": False,
        "deterministic_judge_run": not blockers,
        "llm_answer_eval_run": False,
        "citation_eval_run": False,
        "db_mutation_run": False,
        "indexing_run": False,
        "retrieval_tuning_run": False,
        "reranking_run": False,
        "corpus_mutation_run": False,
        "context_source_policy": {
            "context_field": CONTEXT_FIELD,
            "used_context_json_path": "contexts[].text",
            "allowed_source_field": "chunk_text",
            "disallowed_context_fields": sorted(DISALLOWED_CONTEXT_FIELDS),
            "embedding_text_used": False,
            "debug_text_used": False,
            "text_for_embedding_used": False,
        },
        "query_count": metrics.get("query_count", len(gold_rows)),
        "context_row_count": metrics.get("context_row_count", len(context_rows)),
        "positive_denominator_count": metrics.get("positive_denominator_count", 0),
        "needs_review_excluded_count": metrics.get("needs_review_excluded_count", 0),
        "needs_review_query_ids": metrics.get("needs_review_query_ids", []),
        "primary_stage_counts": metrics.get("primary_stage_counts", {}),
        "stage_counts": metrics.get("stage_counts", {}),
        "bucket_primary_stage_counts": metrics.get("bucket_primary_stage_counts", {}),
        "retrieval_context_available_count": metrics.get("retrieval_context_available_count", 0),
        "expected_context_missing_due_to_wrong_source_count": metrics.get(
            "expected_context_missing_due_to_wrong_source_count", 0
        ),
        "expected_chunk_missing_count": metrics.get("expected_chunk_missing_count", 0),
        "retrieval_context_miss_count": metrics.get("retrieval_context_miss_count", 0),
        "answerable_from_context_count": metrics.get("answerable_from_context_count", 0),
        "not_answerable_from_context_count": metrics.get("not_answerable_from_context_count", 0),
        "answer_eval_pending_live_llm_count": metrics.get("answer_eval_pending_live_llm_count", 0),
        "answer_generation_failure_count": metrics.get("answer_generation_failure_count", 0),
        "must_contain_evaluated_count": metrics.get("must_contain_evaluated_count", 0),
        "must_contain_pass_count": metrics.get("must_contain_pass_count", 0),
        "must_contain_pass_rate": metrics.get("must_contain_pass_rate"),
        "must_not_contain_evaluated_count": metrics.get("must_not_contain_evaluated_count", 0),
        "must_not_contain_pass_count": metrics.get("must_not_contain_pass_count", 0),
        "must_not_contain_pass_rate": metrics.get("must_not_contain_pass_rate"),
        "expected_answer_summary_coverage_avg": metrics.get("expected_answer_summary_coverage_avg"),
        "separation_policy": {
            "retrieval_miss_not_answer_generation_failure": True,
            "retrieval_context_miss_count": metrics.get("retrieval_context_miss_count", 0),
            "answer_generation_failure_count": metrics.get("answer_generation_failure_count", 0),
            "source_context_taxonomy": context_payload.get("taxonomy_counts", {}) if context_payload else {},
        },
        "query_id_groups": {
            "answerable_from_context": metrics.get("answerable_query_ids", []),
            "not_answerable_from_context": metrics.get("not_answerable_query_ids", []),
            "expected_context_missing_due_to_wrong_source": metrics.get("wrong_source_query_ids", []),
            "expected_chunk_missing": metrics.get("missing_expected_chunk_query_ids", []),
            "answer_eval_pending_live_llm": metrics.get("answerable_query_ids", []),
        },
        "r6_handoff": {
            "status": context_payload.get("status") if context_payload else None,
            "r7_ready": context_payload.get("r7_ready") if context_payload else None,
            "expected_context_present_count": context_payload.get("expected_context_present_count") if context_payload else None,
            "missing_expected_source_count": context_payload.get("missing_expected_source_count") if context_payload else None,
            "missing_expected_chunk_count": context_payload.get("missing_expected_chunk_count") if context_payload else None,
        },
        "done_criteria": {
            "r6_context_report_exists": context_report.exists(),
            "r6_context_jsonl_exists": context_jsonl.exists(),
            "context_field_is_chunk_text": True,
            "chunk_text_only": True,
            "disallowed_context_fields_not_used": not blockers,
            "positive_denominator_is_47": metrics.get("positive_denominator_count") == EXPECTED_POSITIVE_DENOMINATOR,
            "needs_review_excluded_is_3": metrics.get("needs_review_excluded_count") == EXPECTED_NEEDS_REVIEW_EXCLUDED,
            "live_llm_not_run_by_default": not enable_live_llm,
            "retrieval_miss_and_answer_failure_separated": metrics.get("answer_generation_failure_count") == 0,
            "promotion_not_run": True,
            "retrieval_tuning_not_run": True,
            "reranking_not_run": True,
            "corpus_mutation_not_run": True,
        },
        "blockers": blockers,
        "warnings": warnings,
        "next_phase_recommendation": (
            "Proceed to R8 citation support only for answerable_from_context rows, or run live LLM under an explicit flag later."
            if status in {"PASS", "PASS_WITH_WARNINGS"}
            else "Keep R7 blocked until deterministic answer-eval blockers are resolved."
        ),
    }


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


def same_path_or_string(reported: str, actual: Path) -> bool:
    normalized_reported = reported.replace("\\", "/")
    normalized_actual = repo_relative(actual).replace("\\", "/")
    if normalized_reported == normalized_actual:
        return True
    try:
        return Path(reported).resolve() == actual.resolve()
    except OSError:
        return False


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
    return datetime.now(timezone.utc).isoformat()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
