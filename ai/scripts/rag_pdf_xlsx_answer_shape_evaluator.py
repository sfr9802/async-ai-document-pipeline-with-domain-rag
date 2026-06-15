"""Evaluate local PDF/XLSX answer-shape diagnostic outputs.

The official PDF/XLSX answer denominators stay zero. This script computes only
diagnostic shape metrics from local-LLM answers when they exist, keeps dry-run
previews out of actual answer output, and emits a prompt repair plan separated
from promotion evidence.
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
REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"

DEFAULT_REPORT = REPORT_DIR / "rag_pdf_xlsx_answer_shape_local_llm_report.json"
DEFAULT_CSV = REPORT_DIR / "rag_pdf_xlsx_answer_shape_local_llm.csv"
DEFAULT_REPAIR_PLAN = REPORT_DIR / "rag_pdf_xlsx_answer_prompt_repair_plan.json"
DEFAULT_OFFICIAL_DENOMINATOR_REGISTRY = (
    AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"
)
DEFAULT_PREVIOUS_EVIDENCE_OBJECTS = (
    AI_WORKER_ROOT
    / "eval"
    / "artifacts"
    / "eval_runs"
    / "pdf_xlsx_answer_shape_repair_20260506T031633Z"
    / "evidence_objects.jsonl"
)

SCHEMA_VERSION = "rag_pdf_xlsx_answer_shape_local_llm_eval_v1"
REPAIR_PLAN_SCHEMA_VERSION = "rag_pdf_xlsx_answer_prompt_repair_plan_v1"
POLICY_SHAPE = "NOT_ANSWERABLE_OR_POLICY_PENDING"
FAILURE_REASONS = {
    "PROMPT_FAILURE",
    "CONTEXT_ASSEMBLY_FAILURE",
    "PARSER_OR_CHUNK_CONTRACT_FAILURE",
    "GOLD_OR_POLICY_BLOCKED",
    "LOCAL_LLM_OUTPUT_INVALID",
    "LLM_HALLUCINATED_UNSUPPORTED_CLAIM",
    "NOT_ANSWERABLE_OR_POLICY_PENDING",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_evaluator(
        inputs_path=Path(args.inputs),
        answers_path=Path(args.answers),
        report_path=Path(args.report),
        csv_path=Path(args.csv),
        repair_plan_path=Path(args.repair_plan),
        official_denominator_registry=Path(args.official_denominator_registry),
        evidence_objects_path=Path(args.evidence_objects) if args.evidence_objects else None,
        previous_evidence_objects_path=Path(args.previous_evidence_objects) if args.previous_evidence_objects else None,
    )
    print_json(
        {
            "status": report["status"],
            "report": repo_relative(Path(args.report)),
            "csv": repo_relative(Path(args.csv)),
            "repair_plan": repo_relative(Path(args.repair_plan)),
            "diagnostic_shape_eval_count": report["diagnostic_shape_eval_count"],
            "actual_answer_output_missing": report["actual_answer_output_missing"],
            "promotion_evidence": report["promotion_evidence"],
            "xlsx_answer_eval_denominator": report["xlsx_answer_eval_denominator"],
            "pdf_answer_eval_denominator": report["pdf_answer_eval_denominator"],
        }
    )
    ok_statuses = {
        "DIAGNOSTIC_COMPLETED",
        "DIAGNOSTIC_COMPLETED_FAIL_CLOSED",
        "DIAGNOSTIC_COMPLETED_WITH_SHAPE_FAILURES",
        "BLOCKED_ACTUAL_ANSWER_OUTPUT_MISSING",
    }
    return 0 if report["status"] in ok_statuses else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, help="answer_generation_inputs.jsonl")
    parser.add_argument("--answers", required=True, help="local_llm_answers.jsonl")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--repair-plan", default=str(DEFAULT_REPAIR_PLAN))
    parser.add_argument("--official-denominator-registry", default=str(DEFAULT_OFFICIAL_DENOMINATOR_REGISTRY))
    parser.add_argument("--evidence-objects", default="", help="Current evidence_objects.jsonl; defaults to answers sibling")
    parser.add_argument(
        "--previous-evidence-objects",
        default=str(DEFAULT_PREVIOUS_EVIDENCE_OBJECTS),
        help="Previous evidence_objects.jsonl for allowed-count comparison",
    )
    return parser.parse_args(argv)


def run_evaluator(
    *,
    inputs_path: Path,
    answers_path: Path,
    report_path: Path,
    csv_path: Path,
    repair_plan_path: Path,
    official_denominator_registry: Path,
    evidence_objects_path: Path | None = None,
    previous_evidence_objects_path: Path | None = None,
) -> dict[str, Any]:
    run_id = utc_run_id()
    generated_at = utc_timestamp()
    input_rows = read_jsonl(inputs_path)
    answer_rows = read_jsonl(answers_path)
    evidence_objects_path = evidence_objects_path or answers_path.parent / "evidence_objects.jsonl"
    evidence_rows = read_jsonl(evidence_objects_path)
    previous_evidence_objects_path = previous_evidence_objects_path or DEFAULT_PREVIOUS_EVIDENCE_OBJECTS
    previous_evidence_rows = read_jsonl(previous_evidence_objects_path)
    answer_by_id = {clean(row.get("query_id")): row for row in answer_rows if clean(row.get("query_id"))}
    coverage_errors = answer_coverage_errors(input_rows, answer_rows)
    parsed_answer_count = sum(1 for row in answer_rows if parse_bool(row.get("parse_ok")))
    actual_answer_output_missing = not (answers_path.exists() and parsed_answer_count > 0)
    answer_output_complete = not coverage_errors
    local_llm_run = any(parse_bool(row.get("local_llm_run")) for row in answer_rows)
    official_denominator_snapshot = inspect_official_answer_denominators(official_denominator_registry)
    denominator_errors = list(official_denominator_snapshot.get("errors", []))

    eval_rows = [evaluate_row(input_row, answer_by_id.get(clean(input_row.get("query_id")))) for input_row in input_rows]
    metrics = metrics_from_rows(eval_rows, actual_answer_output_missing)
    evidence_metrics = evidence_metrics_from_rows(
        evidence_rows=evidence_rows,
        previous_evidence_rows=previous_evidence_rows,
        answer_rows=answer_rows,
    )
    metrics.update(evidence_metrics)
    assembly_metrics = xlsx_context_assembly_metrics(
        input_rows=input_rows,
        evidence_rows=evidence_rows,
        previous_evidence_rows=previous_evidence_rows,
    )
    metrics.update(assembly_metrics)
    status = status_from(metrics, actual_answer_output_missing, coverage_errors, denominator_errors)
    write_csv(csv_path, eval_rows)
    repair_plan = build_repair_plan(
        run_id=run_id,
        generated_at=generated_at,
        eval_rows=eval_rows,
        inputs_path=inputs_path,
        answers_path=answers_path,
        actual_answer_output_missing=actual_answer_output_missing,
        local_llm_run=local_llm_run,
    )
    write_json(repair_plan_path, repair_plan)

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "status": status,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "local_llm_run": local_llm_run,
        "external_live_llm_run": False,
        "optional_judge_run": False,
        "actual_answer_output_missing": actual_answer_output_missing,
        "answer_output_complete": answer_output_complete,
        "answer_output_coverage_errors": coverage_errors,
        "dry_run_preview_used_as_actual_answer": False,
        "xlsx_answer_eval_denominator": 0,
        "official_xlsx_answer_eval_denominator": 0,
        "promotion_denominator": 0,
        "pdf_answer_eval_denominator": evidence_metrics["answer_allowed_count_by_track"].get("PDF", 0),
        "official_answer_denominator": 0,
        "official_answer_denominator_registry": official_denominator_snapshot,
        "diagnostic_shape_eval_count": metrics["diagnostic_shape_eval_count"],
        "diagnostic_shape_rate_denominator": metrics["diagnostic_shape_rate_denominator"],
        "xlsx_retrieval_diagnostic_preserved": True,
        "pdf_policy_pending": True,
        "keyword_echo_only_is_failure": True,
        "location_only_answer_is_failure": True,
        "r8_or_citation_support_blocked_until_answer_shape_alignment": True,
        "no_r8_or_citation_denominator_promoted_automatically": True,
        "source_inputs": {
            "answer_generation_inputs": artifact_entry(inputs_path),
            "local_llm_answers": artifact_entry(answers_path),
            "evidence_objects": artifact_entry(evidence_objects_path),
            "previous_evidence_objects_for_comparison": artifact_entry(previous_evidence_objects_path),
            "official_denominator_registry": artifact_entry(official_denominator_registry),
        },
        "previous_run_artifact_path": repo_relative(previous_evidence_objects_path.parent),
        "new_run_artifact_path": repo_relative(answers_path.parent),
        "output_csv": artifact_entry(csv_path),
        "repair_plan": artifact_entry(repair_plan_path),
        "metrics": metrics,
        **metrics,
        "row_count_by_track": dict(Counter(clean(row.get("track")) for row in eval_rows)),
        "failure_reason_counts": dict(Counter(clean(row.get("failure_reason")) for row in eval_rows)),
        "fail_closed_reason_counts": evidence_metrics["fail_closed_reason_counts"],
        "xlsx_fail_closed_reason_counts": evidence_metrics["xlsx_fail_closed_reason_counts"],
        "compiler_status_counts": evidence_metrics["compiler_status_counts"],
        "content_source_field_counts": evidence_metrics["content_source_field_counts"],
        "denominator_policy_explanation": (
            "Rows with answer_allowed=true form only the query-bound diagnostic answer candidate count. "
            "Official promotion denominators remain governed by official_denominator_registry; "
            "official_xlsx_answer_eval_denominator and promotion_denominator stay 0."
        ),
        "conservative_decisions": [
            "No retrieval, parser, chunking, gold labels, expected answers, relevance labels, or answerability policy were changed.",
            "XLSX answers are allowed only when answer-generation input already contains concrete row, cell, column, nearby-row, or table values.",
            "Locator-only, keyword-only, header-only, and expected-answer-derived summaries remain fail-closed.",
            "XLSX SearchUnit answer content, when present, is joined read-only from retrieval-selected hits by exact search_unit_id or safe sheet/range overlap.",
            "Source workbook probing, expected answers, must-contain terms, gold evidence, and broad sheet/workbook fallbacks are not promoted into answer evidence.",
        ],
        "assertions": {
            "official_pdf_xlsx_answer_denominator_registry_has_no_nonzero": not official_denominator_snapshot[
                "pdf_xlsx_answer_denominator_nonzero"
            ],
            "official_answer_denominator_registry_checked": official_denominator_snapshot["checked"],
            "official_answer_denominator_registry_has_no_pdf_xlsx_answer_denominator": not official_denominator_snapshot[
                "pdf_xlsx_answer_denominator_nonzero"
            ],
            "promotion_evidence_false": True,
            "external_live_llm_run_false": True,
            "optional_judge_run_false": True,
            "no_r8_or_citation_denominator_promoted_automatically": True,
            "dry_run_preview_not_actual_answer": True,
            "answer_rows_cover_input_rows": answer_output_complete,
        },
        "guardrails": {
            "retrieval_tuning_run": False,
            "reranking_run": False,
            "parser_expansion_run": False,
            "threshold_relaxation_run": False,
            "broad_indexing_run": False,
            "db_mutation_run": False,
            "searchunit_mutation_run": False,
            "immutable_baseline_changed": False,
            "candidate_artifact_changed": False,
            "existing_gold_csv_overwritten": False,
        },
    }
    write_json(report_path, report)
    return report


def evaluate_row(input_row: Mapping[str, Any], answer_row: Mapping[str, Any] | None) -> dict[str, Any]:
    answer_row = answer_row or {}
    parsed_answer = answer_row.get("parsed_answer") if isinstance(answer_row.get("parsed_answer"), Mapping) else {}
    evidence_object = answer_row.get("evidence_object") if isinstance(answer_row.get("evidence_object"), Mapping) else {}
    compiled_answer = answer_row.get("compiled_answer") if isinstance(answer_row.get("compiled_answer"), Mapping) else {}
    answer_text = clean(parsed_answer.get("answer"))
    citations = parsed_answer.get("citations") if isinstance(parsed_answer.get("citations"), list) else []
    abstain_reason = clean(parsed_answer.get("abstain_reason"))
    failure_mode = clean(parsed_answer.get("failure_mode_if_any")).upper()
    parsed_answer_shape = clean(parsed_answer.get("answer_shape"))
    parse_ok = parse_bool(answer_row.get("parse_ok"))
    raw_parse_ok = parse_bool(answer_row.get("raw_parse_ok")) if "raw_parse_ok" in answer_row else parse_ok
    repair_parse_ok = parse_bool(answer_row.get("repair_parse_ok"))
    unsupported_claim_added = (
        parse_bool(answer_row.get("unsupported_claim_added"))
        or failure_mode in {"UNSUPPORTED_CLAIM_ADDED", "LLM_HALLUCINATED_UNSUPPORTED_CLAIM"}
        or clean(answer_row.get("failure_reason")) == "LLM_HALLUCINATED_UNSUPPORTED_CLAIM"
    )
    has_answer_output = bool(answer_row)
    policy = input_row.get("policy") if isinstance(input_row.get("policy"), Mapping) else {}
    expected_shape = clean(input_row.get("expected_answer_shape"))
    track = clean(input_row.get("track")).upper()
    context = input_row.get("context") if isinstance(input_row.get("context"), Mapping) else {}

    expected_answer_text = clean(input_row.get("expected_answer_text"))
    must_terms = [clean(term) for term in list(input_row.get("must_contain_terms") or []) if clean(term)]
    locator_text = json.dumps(input_row.get("expected_evidence_location", {}), ensure_ascii=False)
    answer_has_content_target = has_any_term(answer_text, [expected_answer_text, *must_terms])
    answer_has_content_claim = content_claim_present(
        answer_text=answer_text,
        input_row=input_row,
        evidence_object=evidence_object,
        compiled_answer=compiled_answer,
    )
    answer_has_locator = looks_like_locator(answer_text) or has_any_term(answer_text, locator_terms(locator_text))
    is_keyword_echo_only = bool(answer_text) and keyword_echo_only(answer_text, input_row) and not answer_has_content_claim
    is_location_only = bool(answer_text) and not answer_has_content_claim and (
        location_only_answer(answer_text, input_row) or answer_has_locator
    )
    citation_missing = bool(answer_text and not citations)
    claim_without_citation = citation_missing and not abstain_reason
    citation_keyword_only = citation_attached_to_keyword_not_claim(
        citations,
        is_keyword_echo_only,
        is_location_only,
        answer_has_content_claim=answer_has_content_claim,
    )
    context_available = parse_bool(context.get("context_available"))
    context_has_expected_terms = parse_bool(context.get("context_has_expected_terms"))
    table_context_missing = (
        track == "XLSX"
        and expected_shape in {"TABLE_ROW_VALUE", "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT", "LOCATION_PLUS_CONTENT"}
        and has_answer_output
        and parse_ok
        and not abstain_reason
        and not answer_has_content_claim
    )
    pdf_summary_missing = (
        track == "PDF"
        and expected_shape in {"PDF_SECTION_WITH_SUMMARY", "LOCATION_PLUS_CONTENT", "EVIDENCE_LOCATOR_WITH_CONTENT"}
        and has_answer_output
        and parse_ok
        and not abstain_reason
        and not answer_has_content_claim
    )
    context_supported_but_underanswered = (
        context_has_expected_terms
        and has_answer_output
        and parse_ok
        and not abstain_reason
        and (is_keyword_echo_only or is_location_only or not answer_has_content_claim)
    )
    answer_shape_match = (
        has_answer_output
        and parse_ok
        and not abstain_reason
        and expected_shape != POLICY_SHAPE
        and parsed_answer_shape == expected_shape
        and answer_has_content_claim
        and not is_keyword_echo_only
        and not is_location_only
        and not unsupported_claim_added
    )
    context_missing_abstain = (
        has_answer_output
        and parse_ok
        and bool(abstain_reason)
        and expected_shape != POLICY_SHAPE
        and not context_has_expected_terms
    )
    content_target_match = (
        has_answer_output
        and parse_ok
        and not abstain_reason
        and expected_shape != POLICY_SHAPE
        and answer_has_content_claim
        and not is_keyword_echo_only
        and not is_location_only
        and not unsupported_claim_added
    )
    failure_reason = classify_failure_reason(
        input_row=input_row,
        has_answer_output=has_answer_output,
        parse_ok=parse_ok,
        abstain_reason=abstain_reason,
        keyword_echo_only=is_keyword_echo_only or failure_mode == "KEYWORD_ECHO_ONLY",
        location_only=is_location_only or failure_mode == "LOCATION_ONLY_ANSWER",
        content_target_match=content_target_match,
        context_available=context_available,
        context_has_expected_terms=context_has_expected_terms,
        unsupported_claim_added=unsupported_claim_added,
    )
    evidence_quality = answer_row.get("evidence_quality") if isinstance(answer_row.get("evidence_quality"), Mapping) else {}

    return {
        "track": track,
        "query_id": clean(input_row.get("query_id")),
        "query": clean(input_row.get("query")),
        "expected_answer_shape": expected_shape,
        "expected_answer_text": expected_answer_text,
        "must_contain_terms": ";".join(must_terms),
        "has_answer_output": has_answer_output,
        "parse_ok": parse_ok,
        "raw_parse_ok": raw_parse_ok,
        "repair_parse_ok": repair_parse_ok,
        "local_llm_run": parse_bool(answer_row.get("local_llm_run")),
        "llm_polish_run": parse_bool(answer_row.get("llm_polish_run")),
        "deterministic_compiler_run": parse_bool(answer_row.get("deterministic_compiler_run")),
        "deterministic_compiled_answer_used": parse_bool(answer_row.get("deterministic_compiled_answer_used")),
        "answer_allowed": parse_bool(answer_row.get("answer_allowed")) or parse_bool(answer_row.get("answer_generation_allowed")),
        "answer_generation_allowed": parse_bool(answer_row.get("answer_allowed")) or parse_bool(answer_row.get("answer_generation_allowed")),
        "answer_generation_blocker": clean(answer_row.get("answer_generation_blocker")),
        "answer_disallowed_reason": clean(answer_row.get("answer_disallowed_reason")),
        "fail_closed_reason": clean(answer_row.get("fail_closed_reason")),
        "content_source_fields": ";".join(string_items(answer_row.get("content_source_fields"))),
        "content_window_available": parse_bool(evidence_quality.get("has_concrete_content")),
        "compiler_status": clean(answer_row.get("compiler_status")),
        "answer": answer_text,
        "parsed_answer_shape": parsed_answer_shape,
        "abstain_reason": abstain_reason,
        "citation_count": len(citations),
        "keyword_echo_only": is_keyword_echo_only or (bool(answer_text) and failure_mode == "KEYWORD_ECHO_ONLY"),
        "location_only_without_content": is_location_only or (bool(answer_text) and failure_mode == "LOCATION_ONLY_ANSWER"),
        "content_target_match": content_target_match,
        "answer_shape_match": answer_shape_match,
        "context_missing_abstain": context_missing_abstain,
        "table_or_cell_context_missing": table_context_missing,
        "pdf_section_summary_missing": pdf_summary_missing,
        "context_supported_but_underanswered": context_supported_but_underanswered,
        "citation_attached_to_keyword_not_claim": citation_keyword_only,
        "citation_missing": citation_missing,
        "claim_without_citation": claim_without_citation,
        "answer_contains_locator_but_no_claim": answer_has_locator and not answer_has_content_claim and bool(answer_text),
        "answer_has_content_claim": answer_has_content_claim,
        "unsupported_claim_added": unsupported_claim_added,
        "context_available": context_available,
        "context_has_expected_terms": context_has_expected_terms,
        "policy_pdf_c7_pending": parse_bool(policy.get("pdf_c7_policy_pending")),
        "policy_hidden_blocked": parse_bool(policy.get("hidden_policy_blocked")),
        "policy_formula_date_blocked": parse_bool(policy.get("formula_date_policy_blocked")),
        "policy_xlsx_answer_quality_blocked": parse_bool(policy.get("xlsx_answer_quality_blocked")),
        "policy_not_answerable_or_pending": parse_bool(policy.get("not_answerable_or_policy_pending")),
        "exclusion_blocker_reason": clean(input_row.get("exclusion_blocker_reason")),
        "failure_reason": failure_reason,
        "secondary_failure_reasons": secondary_reasons(
            keyword_echo_only=is_keyword_echo_only,
            location_only=is_location_only,
            citation_missing=citation_missing,
            claim_without_citation=claim_without_citation,
            citation_keyword_only=citation_keyword_only,
            table_context_missing=table_context_missing,
            pdf_summary_missing=pdf_summary_missing,
            context_supported_but_underanswered=context_supported_but_underanswered,
            unsupported_claim_added=unsupported_claim_added,
        ),
        "retrieval_failure_reason": retrieval_failure_reason(input_row),
        "policy_blocker_reason": policy_blocker_reason(input_row),
    }


def classify_failure_reason(
    *,
    input_row: Mapping[str, Any],
    has_answer_output: bool,
    parse_ok: bool,
    abstain_reason: str,
    keyword_echo_only: bool,
    location_only: bool,
    content_target_match: bool,
    context_available: bool,
    context_has_expected_terms: bool,
    unsupported_claim_added: bool,
) -> str:
    policy = input_row.get("policy") if isinstance(input_row.get("policy"), Mapping) else {}
    blocker = clean(input_row.get("exclusion_blocker_reason")).upper()
    expected_shape = clean(input_row.get("expected_answer_shape"))
    if has_answer_output and not parse_ok:
        return "LOCAL_LLM_OUTPUT_INVALID"
    if unsupported_claim_added:
        return "LLM_HALLUCINATED_UNSUPPORTED_CLAIM"
    if expected_shape == POLICY_SHAPE or parse_bool(policy.get("not_answerable_or_policy_pending")):
        return "NOT_ANSWERABLE_OR_POLICY_PENDING"
    if any(
        parse_bool(policy.get(key))
        for key in ("pdf_c7_policy_pending", "hidden_policy_blocked", "formula_date_policy_blocked")
    ):
        return "GOLD_OR_POLICY_BLOCKED"
    if "REQUIRE_PARSER_OR_CHUNK_FIX" in blocker or "PARSER_OR_CHUNK" in blocker or "TABLE_GOLD_POLICY" in blocker:
        return "PARSER_OR_CHUNK_CONTRACT_FAILURE"
    if not has_answer_output:
        return "GOLD_OR_POLICY_BLOCKED"
    if not parse_ok:
        return "LOCAL_LLM_OUTPUT_INVALID"
    if not context_available or not context_has_expected_terms:
        return "CONTEXT_ASSEMBLY_FAILURE"
    if abstain_reason and context_has_expected_terms:
        return "PROMPT_FAILURE"
    if keyword_echo_only or location_only or not content_target_match:
        return "PROMPT_FAILURE"
    return "PROMPT_FAILURE" if not content_target_match else ""


def metrics_from_rows(rows: list[Mapping[str, Any]], actual_answer_output_missing: bool) -> dict[str, Any]:
    diagnostic_rows = [row for row in rows if parse_bool(row.get("has_answer_output"))]
    parsed_rows = [row for row in diagnostic_rows if parse_bool(row.get("parse_ok"))]
    non_policy_rows = [
        row
        for row in parsed_rows
        if clean(row.get("expected_answer_shape")) != POLICY_SHAPE
        and not parse_bool(row.get("policy_not_answerable_or_pending"))
    ]
    denominator = len(non_policy_rows)
    allowed_non_policy_rows = [row for row in non_policy_rows if parse_bool(row.get("answer_allowed"))]
    allowed_denominator = len(allowed_non_policy_rows)
    content_target_match_count = sum(1 for row in non_policy_rows if parse_bool(row.get("content_target_match")))
    answer_shape_match_count = sum(1 for row in non_policy_rows if parse_bool(row.get("answer_shape_match")))
    allowed_content_match_count = sum(1 for row in allowed_non_policy_rows if parse_bool(row.get("content_target_match")))
    allowed_shape_match_count = sum(1 for row in allowed_non_policy_rows if parse_bool(row.get("answer_shape_match")))
    location_only_without_content_count = count_bool(parsed_rows, "location_only_without_content")
    answer_contains_locator_but_no_claim_count = count_bool(
        parsed_rows, "answer_contains_locator_but_no_claim"
    )
    return {
        "keyword_echo_only_count": count_bool(parsed_rows, "keyword_echo_only"),
        "location_only_without_content_count": location_only_without_content_count,
        "locator_only_answer_count": location_only_without_content_count
        + answer_contains_locator_but_no_claim_count,
        "content_target_match_rate": rate(content_target_match_count, denominator),
        "answer_shape_match_rate": rate(answer_shape_match_count, denominator),
        "allowed_answer_denominator": allowed_denominator,
        "allowed_content_target_match_rate": rate(allowed_content_match_count, allowed_denominator),
        "allowed_answer_shape_match_rate": rate(allowed_shape_match_count, allowed_denominator),
        "true_shape_failure_count": sum(
            1
            for row in allowed_non_policy_rows
            if not parse_bool(row.get("answer_shape_match"))
            or parse_bool(row.get("keyword_echo_only"))
            or parse_bool(row.get("location_only_without_content"))
            or parse_bool(row.get("unsupported_claim_added"))
        ),
        "fail_closed_insufficient_evidence_abstain_count": sum(
            1
            for row in non_policy_rows
            if clean(row.get("abstain_reason")) and not parse_bool(row.get("answer_allowed"))
        ),
        "empty_abstain_content_match_success_count": sum(
            1
            for row in parsed_rows
            if clean(row.get("abstain_reason")) and parse_bool(row.get("content_target_match"))
        ),
        "table_or_cell_context_missing_count": count_bool(parsed_rows, "table_or_cell_context_missing"),
        "pdf_section_summary_missing_count": count_bool(parsed_rows, "pdf_section_summary_missing"),
        "context_supported_but_underanswered_count": count_bool(parsed_rows, "context_supported_but_underanswered"),
        "citation_attached_to_keyword_not_claim_count": count_bool(
            parsed_rows, "citation_attached_to_keyword_not_claim"
        ),
        "abstain_count": sum(1 for row in parsed_rows if clean(row.get("abstain_reason"))),
        "invalid_json_answer_count": sum(1 for row in diagnostic_rows if not parse_bool(row.get("parse_ok"))),
        "raw_invalid_json_answer_count": sum(1 for row in diagnostic_rows if not parse_bool(row.get("raw_parse_ok"))),
        "repair_parse_ok_count": count_bool(diagnostic_rows, "repair_parse_ok"),
        "unsupported_claim_added_count": count_bool(parsed_rows, "unsupported_claim_added"),
        "context_missing_abstain_count": count_bool(parsed_rows, "context_missing_abstain"),
        "citation_missing_count": count_bool(parsed_rows, "citation_missing"),
        "claim_without_citation_count": count_bool(parsed_rows, "claim_without_citation"),
        "answer_contains_locator_but_no_claim_count": answer_contains_locator_but_no_claim_count,
        "diagnostic_shape_eval_count": len(parsed_rows),
        "diagnostic_shape_rate_denominator": denominator,
        "actual_answer_output_missing": actual_answer_output_missing,
    }


def evidence_metrics_from_rows(
    *,
    evidence_rows: list[Mapping[str, Any]],
    previous_evidence_rows: list[Mapping[str, Any]],
    answer_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    answer_allowed_by_track = Counter(
        clean(row.get("track")).upper()
        for row in evidence_rows
        if parse_bool(row.get("answer_allowed")) or parse_bool(row.get("answer_generation_allowed"))
    )
    fail_closed_rows = [
        row
        for row in evidence_rows
        if not (parse_bool(row.get("answer_allowed")) or parse_bool(row.get("answer_generation_allowed")))
    ]
    previous_by_id = {
        clean(row.get("query_id")): row
        for row in previous_evidence_rows
        if clean(row.get("query_id"))
    }
    changed_to_allowed = 0
    for row in evidence_rows:
        query_id = clean(row.get("query_id"))
        previous = previous_by_id.get(query_id, {})
        previous_allowed = parse_bool(previous.get("answer_allowed")) or parse_bool(
            previous.get("answer_generation_allowed")
        )
        current_allowed = parse_bool(row.get("answer_allowed")) or parse_bool(row.get("answer_generation_allowed"))
        if current_allowed and not previous_allowed:
            changed_to_allowed += 1
    fail_counts = Counter(clean(row.get("fail_closed_reason") or row.get("answer_disallowed_reason") or row.get("answer_generation_blocker")) for row in fail_closed_rows)
    xlsx_fail_counts = Counter(
        clean(row.get("fail_closed_reason") or row.get("answer_disallowed_reason") or row.get("answer_generation_blocker"))
        for row in fail_closed_rows
        if clean(row.get("track")).upper() == "XLSX"
    )
    compiler_counts = Counter(clean(row.get("compiler_status")) for row in answer_rows)
    source_counts: Counter[str] = Counter()
    for row in evidence_rows:
        for source in string_items(row.get("content_source_fields")):
            source_counts[source] += 1
    allowed_answer_rows = [
        row
        for row in answer_rows
        if parse_bool(row.get("answer_allowed")) or parse_bool(row.get("answer_generation_allowed"))
    ]
    allowed_abstain_rows = [
        row
        for row in allowed_answer_rows
        if clean(nested_mapping(row, "parsed_answer").get("abstain_reason"))
    ]
    compiled_failure_modes = [
        clean(
            nested_mapping(row, "parsed_answer").get("failure_mode_if_any")
            or nested_mapping(row, "compiled_answer").get("failure_mode_if_any")
        )
        for row in answer_rows
    ]
    return {
        "answer_allowed_count": sum(answer_allowed_by_track.values()),
        "answer_allowed_count_by_track": dict(answer_allowed_by_track),
        "fail_closed_abstain_count": len(fail_closed_rows),
        "gold_policy_pending_denominator_exclusion_count": sum(
            1
            for row in evidence_rows
            if parse_bool(row.get("policy_pending"))
            or clean(row.get("fail_closed_reason")) in {"XLSX_POLICY_PENDING", "PDF_POLICY_PENDING"}
        ),
        "diagnostic_only_exclusion_count": sum(1 for row in evidence_rows if parse_bool(row.get("diagnostic_only"))),
        "content_present_but_not_compiled_failure_count": len(allowed_abstain_rows),
        "empty_abstain_content_match_success_count": 0,
        "changed_from_disallowed_to_allowed_count": changed_to_allowed,
        "still_disallowed_keyword_or_locator_only_count": sum(
            1
            for row in fail_closed_rows
            if clean(row.get("fail_closed_reason") or row.get("answer_generation_blocker"))
            in {"XLSX_KEYWORD_ONLY", "XLSX_LOCATOR_ONLY", "PDF_KEYWORD_ONLY", "PDF_LOCATOR_ONLY"}
        ),
        "fail_closed_reason_counts": dict(fail_counts),
        "xlsx_fail_closed_reason_counts": dict(xlsx_fail_counts),
        "compiler_status_counts": dict(compiler_counts),
        "content_source_field_counts": dict(source_counts),
        "compiled_answer_drops_bound_entity_count": count_failure_mode(
            compiled_failure_modes, "XLSX_COMPILED_ANSWER_DROPS_BOUND_ENTITY"
        ),
        "compiled_answer_drops_bound_header_count": count_failure_mode(
            compiled_failure_modes, "XLSX_COMPILED_ANSWER_DROPS_BOUND_HEADER"
        ),
        "compiled_answer_drops_bound_value_count": count_failure_mode(
            compiled_failure_modes, "XLSX_COMPILED_ANSWER_DROPS_BOUND_VALUE"
        ),
    }


def xlsx_context_assembly_metrics(
    *,
    input_rows: list[Mapping[str, Any]],
    evidence_rows: list[Mapping[str, Any]],
    previous_evidence_rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    xlsx_rows = [row for row in input_rows if clean(row.get("track")).upper() == "XLSX"]
    policy_pending_rows = [row for row in xlsx_rows if xlsx_policy_pending(row)]
    joined_rows = []
    exact_join_count = 0
    overlap_join_count = 0
    failed_join_count = 0
    answer_input_has_values_after = 0
    source_promoted = 0
    gold_leakage = 0
    broad_promoted = 0
    for row in xlsx_rows:
        context = row.get("context") if isinstance(row.get("context"), Mapping) else {}
        if xlsx_context_has_content_values(context):
            answer_input_has_values_after += 1
        join = context.get("xlsx_searchunit_content_join") if isinstance(context.get("xlsx_searchunit_content_join"), Mapping) else {}
        if parse_bool(join.get("answer_evidence_used")):
            joined_rows.append(row)
            join_type = clean(join.get("join_type"))
            if join_type == "exact_locator":
                exact_join_count += 1
            elif join_type == "safe_range_overlap":
                overlap_join_count += 1
        elif not xlsx_policy_pending(row) and nested_top_k_count(context) > 0:
            failed_join_count += 1
        if parse_bool(join.get("source_workbook_promoted_evidence")):
            source_promoted += 1
        if parse_bool(join.get("gold_leakage")):
            gold_leakage += 1
        if parse_bool(join.get("broad_fallback_promoted")):
            broad_promoted += 1

    previous_xlsx_allowed = sum(
        1
        for row in previous_evidence_rows
        if clean(row.get("track")).upper() == "XLSX"
        and (parse_bool(row.get("answer_allowed")) or parse_bool(row.get("answer_generation_allowed")))
    )
    previous_xlsx_has_values = sum(
        1
        for row in previous_evidence_rows
        if clean(row.get("track")).upper() == "XLSX"
        and (
            parse_bool(nested_mapping(row, "evidence_quality").get("has_concrete_content"))
            or bool(string_items(row.get("content_source_fields")))
        )
    )
    current_xlsx_allowed = sum(
        1
        for row in evidence_rows
        if clean(row.get("track")).upper() == "XLSX"
        and (parse_bool(row.get("answer_allowed")) or parse_bool(row.get("answer_generation_allowed")))
    )
    current_content_shape_candidate = sum(
        1
        for row in evidence_rows
        if clean(row.get("track")).upper() == "XLSX"
        and parse_bool(nested_mapping(row, "evidence_quality").get("content_shape_candidate"))
    )
    previous_content_shape_candidate = sum(
        1
        for row in previous_evidence_rows
        if clean(row.get("track")).upper() == "XLSX"
        and (
            parse_bool(nested_mapping(row, "evidence_quality").get("content_shape_candidate"))
            or parse_bool(nested_mapping(row, "evidence_quality").get("has_concrete_content"))
            or bool(string_items(row.get("content_source_fields")))
        )
    )
    failure_code_counts: Counter[str] = Counter()
    for row in evidence_rows:
        if clean(row.get("track")).upper() != "XLSX":
            continue
        for code in string_items(nested_mapping(row, "evidence_quality").get("failure_codes")):
            failure_code_counts[code] += 1
    return {
        "xlsx_rows": len(xlsx_rows),
        "xlsx_policy_pending_rows": len(policy_pending_rows),
        "retrieval_selected_rows_joined_to_searchunit_content": len(joined_rows),
        "xlsx_exact_locator_join_count": exact_join_count,
        "xlsx_safe_range_overlap_join_count": overlap_join_count,
        "xlsx_failed_join_count": failed_join_count,
        "content_joined_count_before": previous_xlsx_has_values,
        "content_joined_count_after": len(joined_rows),
        "content_joined_count": len(joined_rows),
        "content_shape_candidate_count_before": previous_content_shape_candidate,
        "content_shape_candidate_count_after": current_content_shape_candidate,
        "content_shape_candidate_count": current_content_shape_candidate,
        "query_bound_answer_allowed_count_before": previous_xlsx_allowed,
        "query_bound_answer_allowed_count_after": current_xlsx_allowed,
        "query_bound_answer_allowed_count": current_xlsx_allowed,
        "official_xlsx_answer_eval_denominator_before": 0,
        "official_xlsx_answer_eval_denominator_after": 0,
        "official_xlsx_answer_eval_denominator": 0,
        "promotion_denominator": 0,
        "xlsx_answer_input_has_values_count_before": previous_xlsx_has_values,
        "xlsx_answer_input_has_values_count_after": answer_input_has_values_after,
        "answer_input_has_values_count_before": previous_xlsx_has_values,
        "answer_input_has_values_count_after": answer_input_has_values_after,
        "answer_allowed_count_before": previous_xlsx_allowed,
        "answer_allowed_count_after": current_xlsx_allowed,
        "xlsx_answer_eval_denominator_before": 0,
        "xlsx_answer_eval_denominator_after": 0,
        "rows_still_fail_closed_count": len(xlsx_rows) - current_xlsx_allowed,
        "rows_still_fail_closed_reason_counts": dict(
            Counter(
                clean(row.get("fail_closed_reason") or row.get("answer_disallowed_reason") or row.get("answer_generation_blocker"))
                for row in evidence_rows
                if clean(row.get("track")).upper() == "XLSX"
                and not (parse_bool(row.get("answer_allowed")) or parse_bool(row.get("answer_generation_allowed")))
            )
        ),
        "xlsx_failure_code_counts": dict(failure_code_counts),
        "xlsx_query_anchor_mismatch_count": failure_code_counts.get("XLSX_QUERY_ANCHOR_MISMATCH", 0),
        "xlsx_context_citation_locator_mismatch_count": failure_code_counts.get(
            "XLSX_CONTEXT_CITATION_LOCATOR_MISMATCH", 0
        ),
        "xlsx_expected_locator_promoted_count": failure_code_counts.get("XLSX_EXPECTED_LOCATOR_PROMOTED", 0),
        "xlsx_target_column_not_bound_count": failure_code_counts.get("XLSX_TARGET_COLUMN_NOT_BOUND", 0),
        "xlsx_multirow_first_value_fallback_count": failure_code_counts.get(
            "XLSX_MULTIROW_FIRST_VALUE_FALLBACK", 0
        ),
        "source_workbook_promoted_evidence_count": source_promoted,
        "gold_leakage_count": gold_leakage,
        "expected_locator_promoted_count": failure_code_counts.get("XLSX_EXPECTED_LOCATOR_PROMOTED", 0),
        "broad_fallback_promoted_evidence_count": broad_promoted,
    }


def xlsx_policy_pending(row: Mapping[str, Any]) -> bool:
    policy = row.get("policy") if isinstance(row.get("policy"), Mapping) else {}
    return bool(
        clean(row.get("expected_answer_shape")) == POLICY_SHAPE
        or parse_bool(policy.get("not_answerable_or_policy_pending"))
        or parse_bool(policy.get("hidden_policy_blocked"))
        or parse_bool(policy.get("formula_date_policy_blocked"))
    )


def nested_top_k_count(context: Mapping[str, Any]) -> int:
    retrieval = context.get("retrieval_context") if isinstance(context.get("retrieval_context"), Mapping) else {}
    top_k = retrieval.get("top_k_results") if isinstance(retrieval.get("top_k_results"), list) else []
    return len(top_k)


def xlsx_context_has_content_values(context: Mapping[str, Any]) -> bool:
    for key in (
        "retrieval_text",
        "table_context",
        "nearby_rows",
        "nearby_table_context",
        "row_values",
        "cell_values",
        "column_values",
        "value_context",
        "content_summary",
    ):
        if xlsx_context_value_has_content(context.get(key)):
            return True
    return False


def xlsx_context_value_has_content(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if clean(key).lower() in {"locator", "location_json", "match_breakdown"}:
                continue
            if xlsx_context_value_has_content(item):
                return True
        return False
    if isinstance(value, list):
        return any(xlsx_context_value_has_content(item) for item in value)
    text = clean(value)
    if len(text) < 2:
        return False
    folded = re.sub(r"\s+", "", text).lower()
    locator_patterns = (
        r"^[a-z]{1,3}\d+(:[a-z]{1,3}\d+)?$",
        r"^.+\.xlsx$",
        r"^docv_[0-9a-f]+$",
    )
    return not any(re.match(pattern, folded) for pattern in locator_patterns)


def build_repair_plan(
    *,
    run_id: str,
    generated_at: str,
    eval_rows: list[Mapping[str, Any]],
    inputs_path: Path,
    answers_path: Path,
    actual_answer_output_missing: bool,
    local_llm_run: bool,
) -> dict[str, Any]:
    prompt_rows = [
        row_summary(row)
        for row in eval_rows
        if clean(row.get("failure_reason")) in {"PROMPT_FAILURE", "LOCAL_LLM_OUTPUT_INVALID"}
        or parse_bool(row.get("keyword_echo_only"))
        or parse_bool(row.get("location_only_without_content"))
        or parse_bool(row.get("context_supported_but_underanswered"))
    ]
    context_rows = [
        row_summary(row)
        for row in eval_rows
        if clean(row.get("failure_reason")) == "CONTEXT_ASSEMBLY_FAILURE"
    ]
    parser_rows = [
        row_summary(row)
        for row in eval_rows
        if clean(row.get("failure_reason")) == "PARSER_OR_CHUNK_CONTRACT_FAILURE"
    ]
    pdf_policy_rows = [
        row_summary(row)
        for row in eval_rows
        if clean(row.get("track")) == "PDF"
        and (
            parse_bool(row.get("policy_pdf_c7_pending"))
            or clean(row.get("failure_reason")) == "NOT_ANSWERABLE_OR_POLICY_PENDING"
        )
    ]
    xlsx_policy_rows = [
        row_summary(row)
        for row in eval_rows
        if clean(row.get("track")) == "XLSX"
        and (
            parse_bool(row.get("policy_hidden_blocked"))
            or parse_bool(row.get("policy_formula_date_blocked"))
            or clean(row.get("failure_reason")) == "NOT_ANSWERABLE_OR_POLICY_PENDING"
        )
    ]
    shape_failure_rows = [
        row_summary(row)
        for row in eval_rows
        if parse_bool(row.get("has_answer_output"))
        and parse_bool(row.get("parse_ok"))
        and parse_bool(row.get("answer_allowed"))
        and clean(row.get("expected_answer_shape")) != POLICY_SHAPE
        and not parse_bool(row.get("answer_shape_match"))
    ]
    fail_closed_rows = [
        row_summary(row)
        for row in eval_rows
        if parse_bool(row.get("has_answer_output"))
        and parse_bool(row.get("parse_ok"))
        and clean(row.get("abstain_reason"))
        and not parse_bool(row.get("answer_allowed"))
    ]
    status = "BLOCKED_ACTUAL_ANSWER_OUTPUT_MISSING"
    if not actual_answer_output_missing:
        status = (
            "COMPLETED_DIAGNOSTIC_ONLY_WITH_SHAPE_FAILURES"
            if shape_failure_rows
            else "COMPLETED_DIAGNOSTIC_ONLY_FAIL_CLOSED"
            if fail_closed_rows
            else "COMPLETED_DIAGNOSTIC_ONLY"
        )
    return {
        "schema_version": REPAIR_PLAN_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "status": status,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "local_llm_run": local_llm_run,
        "external_live_llm_run": False,
        "optional_judge_run": False,
        "actual_answer_output_missing": actual_answer_output_missing,
        "dry_run_preview_used_as_actual_answer": False,
        "source_inputs": {
            "answer_generation_inputs": artifact_entry(inputs_path),
            "local_llm_answers": artifact_entry(answers_path),
        },
        "prompt_only_rows": prompt_rows,
        "context_serializer_rows": context_rows,
        "parser_or_chunking_issue_rows": parser_rows,
        "pdf_c7_user_policy_blocked_rows": pdf_policy_rows,
        "xlsx_hidden_formula_date_policy_blocked_rows": xlsx_policy_rows,
        "diagnostic_shape_failure_rows": shape_failure_rows,
        "fail_closed_abstain_rows": fail_closed_rows,
        "counts": {
            "prompt_only_rows": len(prompt_rows),
            "context_serializer_rows": len(context_rows),
            "parser_or_chunking_issue_rows": len(parser_rows),
            "pdf_c7_user_policy_blocked_rows": len(pdf_policy_rows),
            "xlsx_hidden_formula_date_policy_blocked_rows": len(xlsx_policy_rows),
            "diagnostic_shape_failure_rows": len(shape_failure_rows),
            "fail_closed_abstain_rows": len(fail_closed_rows),
        },
        "notes": [
            "Rows are diagnostic-only and do not change official answer denominators.",
            "Prompt-only rows require actual local LLM output; when output is missing this list remains empty.",
            "Context serializer rows mean the assembled input lacked content evidence, not that retrieval tuning is needed.",
            "PDF C7 and XLSX hidden/formula/date blocked rows require policy/parser review before any answer denominator use.",
        ],
    }


def status_from(
    metrics: Mapping[str, Any],
    actual_answer_output_missing: bool,
    coverage_errors: list[str],
    denominator_errors: list[str],
) -> str:
    if denominator_errors:
        return "FAIL_OFFICIAL_ANSWER_DENOMINATOR_NONZERO"
    if coverage_errors:
        return "FAIL_PARTIAL_ANSWER_OUTPUT"
    if actual_answer_output_missing:
        return "BLOCKED_ACTUAL_ANSWER_OUTPUT_MISSING"
    if metrics.get("invalid_json_answer_count"):
        return "DIAGNOSTIC_COMPLETED_WITH_SHAPE_FAILURES"
    if metrics.get("keyword_echo_only_count") or metrics.get("location_only_without_content_count"):
        return "DIAGNOSTIC_COMPLETED_WITH_SHAPE_FAILURES"
    if metrics.get("true_shape_failure_count"):
        return "DIAGNOSTIC_COMPLETED_WITH_SHAPE_FAILURES"
    if metrics.get("fail_closed_insufficient_evidence_abstain_count"):
        return "DIAGNOSTIC_COMPLETED_FAIL_CLOSED"
    return "DIAGNOSTIC_COMPLETED"


def inspect_official_answer_denominators(path: Path) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "path": repo_relative(path),
        "exists": path.exists(),
        "checked": False,
        "observed_answer_denominator_fields": [],
        "pdf_xlsx_answer_denominator_nonzero": False,
        "errors": [],
    }
    if not path.exists():
        snapshot["errors"].append("official denominator registry missing")
        return snapshot
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        snapshot["errors"].append(f"official denominator registry invalid JSON: {exc}")
        return snapshot
    snapshot["checked"] = True
    observed: list[dict[str, Any]] = []
    for key_path, value in walk_json_scalars(payload):
        key_text = ".".join(key_path).lower()
        if "answer" not in key_text or "denominator" not in key_text:
            continue
        if not any(track in key_text for track in ("pdf", "xlsx", "official")):
            continue
        numeric_value = numeric_or_none(value)
        entry = {
            "key_path": ".".join(key_path),
            "value": value,
            "numeric_value": numeric_value,
        }
        observed.append(entry)
        if numeric_value not in (None, 0):
            snapshot["pdf_xlsx_answer_denominator_nonzero"] = True
            snapshot["errors"].append(
                f"nonzero official answer denominator in registry at {entry['key_path']}={numeric_value}"
            )
    snapshot["observed_answer_denominator_fields"] = observed
    return snapshot


def answer_coverage_errors(
    input_rows: list[Mapping[str, Any]],
    answer_rows: list[Mapping[str, Any]],
) -> list[str]:
    errors: list[str] = []
    input_ids = [clean(row.get("query_id")) for row in input_rows if clean(row.get("query_id"))]
    answer_ids = [clean(row.get("query_id")) for row in answer_rows if clean(row.get("query_id"))]
    if len(answer_rows) != len(input_rows):
        errors.append(f"answer row count {len(answer_rows)} != input row count {len(input_rows)}")
    duplicate_input_ids = sorted(query_id for query_id, count in Counter(input_ids).items() if count > 1)
    duplicate_answer_ids = sorted(query_id for query_id, count in Counter(answer_ids).items() if count > 1)
    if duplicate_input_ids:
        errors.append(f"duplicate input query ids: {duplicate_input_ids}")
    if duplicate_answer_ids:
        errors.append(f"duplicate answer query ids: {duplicate_answer_ids}")
    missing_answer_ids = sorted(set(input_ids) - set(answer_ids))
    unexpected_answer_ids = sorted(set(answer_ids) - set(input_ids))
    if missing_answer_ids:
        errors.append(f"missing answer query ids: {missing_answer_ids}")
    if unexpected_answer_ids:
        errors.append(f"unexpected answer query ids: {unexpected_answer_ids}")
    return errors


def secondary_reasons(**flags: bool) -> str:
    return ";".join(name.upper() for name, enabled in flags.items() if enabled)


def retrieval_failure_reason(input_row: Mapping[str, Any]) -> str:
    context = input_row.get("context") if isinstance(input_row.get("context"), Mapping) else {}
    retrieval_context = context.get("retrieval_context") if isinstance(context.get("retrieval_context"), Mapping) else {}
    return clean(
        retrieval_context.get("failure_or_quality_classification")
        or retrieval_context.get("retrieval_query_status")
        or ""
    )


def policy_blocker_reason(input_row: Mapping[str, Any]) -> str:
    policy = input_row.get("policy") if isinstance(input_row.get("policy"), Mapping) else {}
    reasons = [key for key, value in policy.items() if parse_bool(value) and key != "diagnostic_only"]
    return ";".join(reasons)


def row_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "track": clean(row.get("track")),
        "query_id": clean(row.get("query_id")),
        "query": clean(row.get("query")),
        "expected_answer_shape": clean(row.get("expected_answer_shape")),
        "failure_reason": clean(row.get("failure_reason")),
        "fail_closed_reason": clean(row.get("fail_closed_reason")),
        "secondary_failure_reasons": clean(row.get("secondary_failure_reasons")),
        "policy_blocker_reason": clean(row.get("policy_blocker_reason")),
        "retrieval_failure_reason": clean(row.get("retrieval_failure_reason")),
    }


def keyword_echo_only(answer_text: str, input_row: Mapping[str, Any]) -> bool:
    answer = normalize(answer_text)
    if not answer:
        return False
    terms = [clean(input_row.get("expected_answer_text"))]
    terms.extend(clean(term) for term in input_row.get("must_contain_terms") or [])
    terms.extend(extract_keywords(clean(input_row.get("query"))))
    normalized_terms = [normalize(term) for term in terms if normalize(term)]
    if not normalized_terms:
        return False
    if answer in normalized_terms:
        return True
    return len(answer) <= 30 and any(answer == term or term == answer for term in normalized_terms)


def location_only_answer(answer_text: str, input_row: Mapping[str, Any]) -> bool:
    answer = clean(answer_text)
    if not answer:
        return False
    if not looks_like_locator(answer):
        return False
    expected_terms = [clean(input_row.get("expected_answer_text"))]
    expected_terms.extend(clean(term) for term in input_row.get("must_contain_terms") or [])
    return not has_any_term(answer, expected_terms)


def looks_like_locator(value: str) -> bool:
    text = clean(value)
    if not text:
        return False
    locator_patterns = [
        r"\bbbox\b",
        r"\bp(?:age)?\.?\s*\d+\b",
        r"\bpage\s*\d+\b",
        r"\bsheet\b",
        r"\brange\b",
        r"\bcell\b",
        r"[A-Z]{1,3}\d+\s*:\s*[A-Z]{1,3}\d+",
        r"[A-Z]{1,3}\d+",
        r"\.pdf\b",
        r"\.xlsx?\b",
        r"페이지\s*\d+",
        r"시트",
        r"범위",
    ]
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in locator_patterns)


def citation_attached_to_keyword_not_claim(
    citations: list[Any],
    keyword_echo: bool,
    location_only: bool,
    *,
    answer_has_content_claim: bool,
) -> bool:
    if not citations:
        return False
    if keyword_echo or location_only:
        return True
    citation_objects = [citation for citation in citations if isinstance(citation, Mapping)]
    if not citation_objects:
        return True
    if not answer_has_content_claim:
        return True
    return all(not parse_bool(citation.get("supports_claim")) or not clean(citation.get("claim")) for citation in citation_objects)


def content_claim_present(
    *,
    answer_text: str,
    input_row: Mapping[str, Any],
    evidence_object: Mapping[str, Any],
    compiled_answer: Mapping[str, Any],
) -> bool:
    answer = clean(answer_text)
    if not answer:
        return False
    if keyword_echo_only(answer, input_row) and len(normalize(answer)) <= 40:
        return False

    content_terms = evidence_content_terms(evidence_object)
    if not content_terms and isinstance(compiled_answer, Mapping):
        content_terms = evidence_content_terms(compiled_answer)
    shape = clean(input_row.get("expected_answer_shape"))
    if shape == "TABLE_ROW_VALUE":
        required = [
            clean(evidence_object.get("row_label")),
            clean(evidence_object.get("column_label")),
            clean(evidence_object.get("value")),
        ]
        required = [term for term in required if term]
        return bool(required) and all(has_any_term(answer, [term]) for term in required)
    if shape == "PDF_TABLE_VALUE_WITH_CONTEXT":
        required = [
            clean(evidence_object.get("row_label")),
            clean(evidence_object.get("value")),
        ]
        required = [term for term in required if term]
        return bool(required) and all(has_any_term(answer, [term]) for term in required)
    if shape == "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT":
        header_terms = string_items(evidence_object.get("header_context"))
        return bool(content_terms) and has_any_term(answer, content_terms) and (
            bool(header_terms)
            or bool(mapping_items(evidence_object.get("row_values")))
            or bool(mapping_items(evidence_object.get("column_values")))
            or bool(mapping_items(evidence_object.get("cell_values")))
            or bool(string_items(evidence_object.get("nearby_rows")))
            or bool(string_items(evidence_object.get("table_context")))
        )
    if shape in {"PDF_SECTION_WITH_SUMMARY", "LOCATION_PLUS_CONTENT", "EVIDENCE_LOCATOR_WITH_CONTENT", "YES_NO_WITH_EVIDENCE"}:
        return bool(content_terms) and has_any_term(answer, content_terms)
    return bool(content_terms) and has_any_term(answer, content_terms)


def evidence_content_terms(evidence_object: Mapping[str, Any]) -> list[str]:
    terms = [
        clean(evidence_object.get("row_label")),
        clean(evidence_object.get("column_label")),
        clean(evidence_object.get("value")),
        clean(evidence_object.get("content_summary")),
        clean(evidence_object.get("paragraph_or_table_text")),
    ]
    terms.extend(string_items(evidence_object.get("header_context")))
    terms.extend(string_items(evidence_object.get("nearby_row_context")))
    terms.extend(string_items(evidence_object.get("nearby_rows")))
    terms.extend(string_items(evidence_object.get("table_context")))
    for item in [
        *mapping_items(evidence_object.get("row_values")),
        *mapping_items(evidence_object.get("column_values")),
        *mapping_items(evidence_object.get("cell_values")),
    ]:
        terms.extend(
            [
                clean(item.get("row_label")),
                clean(item.get("column_label")),
                clean(item.get("value")),
                clean(item.get("row_text")),
                clean(item.get("column_text")),
            ]
        )
    compact_terms: list[str] = []
    for term in terms:
        term = clean(term)
        if not term:
            continue
        compact_terms.append(term)
        compact_terms.extend(
            item for item in re.split(r"[\s,.;:|/]+", term) if len(clean(item)) >= 3
        )
    return compact_terms[:30]


def mapping_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def string_items(value: object) -> list[str]:
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    if clean(value):
        return [clean(value)]
    return []


def nested_mapping(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    nested = value.get(key)
    return nested if isinstance(nested, Mapping) else {}


def locator_terms(locator_text: str) -> list[str]:
    return [term for term in re.split(r"[\s;,\[\]{}:\"]+", locator_text) if term and len(term) > 1]


def extract_keywords(query: str) -> list[str]:
    return [item for item in re.split(r"[\s,.;!?]+", query) if len(item) >= 2]


def has_any_term(text: str, terms: Iterable[str]) -> bool:
    folded = normalize(text)
    return any(normalize(term) and normalize(term) in folded for term in terms)


def normalize(value: object) -> str:
    return re.sub(r"\s+", "", clean(value)).lower()


def count_bool(rows: Iterable[Mapping[str, Any]], field: str) -> int:
    return sum(1 for row in rows if parse_bool(row.get(field)))


def count_failure_mode(values: Iterable[str], code: str) -> int:
    return sum(1 for value in values if code in clean(value))


def rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                rows.append(
                    {
                        "query_id": f"__invalid_json_line_{line_no}",
                        "parse_ok": False,
                        "parsed_answer": {},
                        "answer_json_raw": line.strip(),
                        "jsonl_parse_error": str(exc),
                    }
                )
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


CSV_FIELDS = [
    "track",
    "query_id",
    "query",
    "expected_answer_shape",
    "expected_answer_text",
    "must_contain_terms",
    "has_answer_output",
    "parse_ok",
    "raw_parse_ok",
    "repair_parse_ok",
    "local_llm_run",
    "llm_polish_run",
    "deterministic_compiler_run",
    "deterministic_compiled_answer_used",
    "answer_allowed",
    "answer_generation_allowed",
    "answer_generation_blocker",
    "answer_disallowed_reason",
    "fail_closed_reason",
    "content_window_available",
    "content_source_fields",
    "compiler_status",
    "answer",
    "parsed_answer_shape",
    "abstain_reason",
    "citation_count",
    "keyword_echo_only",
    "location_only_without_content",
        "content_target_match",
        "answer_shape_match",
        "context_missing_abstain",
        "table_or_cell_context_missing",
    "pdf_section_summary_missing",
    "context_supported_but_underanswered",
    "citation_attached_to_keyword_not_claim",
    "citation_missing",
    "claim_without_citation",
    "answer_contains_locator_but_no_claim",
    "answer_has_content_claim",
    "unsupported_claim_added",
    "context_available",
    "context_has_expected_terms",
    "policy_pdf_c7_pending",
    "policy_hidden_blocked",
    "policy_formula_date_blocked",
    "policy_xlsx_answer_quality_blocked",
    "policy_not_answerable_or_pending",
    "exclusion_blocker_reason",
    "failure_reason",
    "secondary_failure_reasons",
    "retrieval_failure_reason",
    "policy_blocker_reason",
]


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def artifact_entry(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return clean(value).lower() in {"1", "true", "yes", "y"}


def walk_json_scalars(value: Any, prefix: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from walk_json_scalars(item, (*prefix, clean(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_json_scalars(item, (*prefix, str(index)))
    else:
        yield prefix, value


def numeric_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def print_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
