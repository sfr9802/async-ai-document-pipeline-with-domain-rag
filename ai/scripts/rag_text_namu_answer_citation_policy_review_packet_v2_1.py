"""Build the TEXT/Namu V2.1 diagnostic policy review packet.

This packet is a compact user-facing review surface for diagnostic-only
answer/citation rows. It intentionally does not read or open official metrics,
official denominators, gold registries, candidate artifacts, immutable
baselines, or production indexes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"
REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"

DEFAULT_GENERATED_ANSWER_JSONL = (
    REVIEW_DIR / "rag_text_namu_generated_answer_review_input_local_llm_v2_1.jsonl"
)
DEFAULT_REVIEW_DRAFT_JSONL = (
    REVIEW_DIR / "rag_text_namu_answer_citation_review_draft_local_llm_v2_1.jsonl"
)
DEFAULT_APPLIED_DIAGNOSTIC_JSON = (
    REVIEW_DIR / "rag_text_namu_answer_citation_review_applied_diagnostic_v2_1.json"
)
DEFAULT_IMPROVEMENT_REPORT_JSON = (
    REPORT_DIR / "rag_text_namu_answer_citation_local_llm_improvement_report_v2_1.json"
)
DEFAULT_OUTPUT_JSON = REVIEW_DIR / "rag_text_namu_answer_citation_policy_review_packet_v2_1.json"
DEFAULT_OUTPUT_MD = REVIEW_DIR / "rag_text_namu_answer_citation_policy_review_packet_v2_1.md"

SCHEMA_VERSION = "rag_text_namu_answer_citation_policy_review_packet_v2_1"
OFFICIAL_METRIC_STATUS = "FAIL_CLOSED_OFFICIAL_METRIC_INPUT_EMPTY"
KEEP_DIAGNOSTIC_CANDIDATE = "KEEP_DIAGNOSTIC_CANDIDATE"
KEEP_WITH_CLEANUP = "KEEP_WITH_CLEANUP"
FULLY_SUPPORTED = "fully_supported"
PASS_STATUS = "POLICY_REVIEW_PACKET_READY"
FAIL_STATUS = "FAIL_CLOSED"


@dataclass(frozen=True)
class ExpectedCounts:
    total_rows: int = 66
    clean_pass: int = 60
    cleanup: int = 5
    unresolved: int = 1
    citation_supported: int = 65


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    expected_counts = ExpectedCounts(
        total_rows=args.expected_total_rows,
        clean_pass=args.expected_clean_pass,
        cleanup=args.expected_cleanup,
        unresolved=args.expected_unresolved,
        citation_supported=args.expected_citation_supported,
    )
    packet = build_policy_review_packet(
        generated_answer_jsonl=Path(args.generated_answer_jsonl),
        review_draft_jsonl=Path(args.review_draft_jsonl),
        applied_diagnostic_json=Path(args.applied_diagnostic_json),
        improvement_report_json=Path(args.improvement_report_json),
        expected_counts=expected_counts,
    )
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    write_json(output_json, packet)
    write_text(output_md, render_markdown(packet))
    print_json(
        {
            "status": packet["status"],
            "output_json": repo_relative(output_json),
            "output_md": repo_relative(output_md),
            "row_count": packet["row_count"],
            "strict_clean_answer_preview": packet["diagnostic_metric_preview"][
                "strict_clean_answer_preview"
            ],
            "cleanup_inclusive_answer_preview": packet["diagnostic_metric_preview"][
                "cleanup_inclusive_answer_preview"
            ],
            "citation_supported_preview": packet["diagnostic_metric_preview"][
                "citation_supported_preview"
            ],
            "official_metric_input_rows": packet["diagnostic_metric_preview"][
                "official_metric_input_rows"
            ],
            "official_metric_status": packet["diagnostic_metric_preview"][
                "official_metric_status"
            ],
        }
    )
    return 0 if packet["status"] == PASS_STATUS else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated-answer-jsonl", default=str(DEFAULT_GENERATED_ANSWER_JSONL))
    parser.add_argument("--review-draft-jsonl", default=str(DEFAULT_REVIEW_DRAFT_JSONL))
    parser.add_argument("--applied-diagnostic-json", default=str(DEFAULT_APPLIED_DIAGNOSTIC_JSON))
    parser.add_argument("--improvement-report-json", default=str(DEFAULT_IMPROVEMENT_REPORT_JSON))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--expected-total-rows", type=int, default=66)
    parser.add_argument("--expected-clean-pass", type=int, default=60)
    parser.add_argument("--expected-cleanup", type=int, default=5)
    parser.add_argument("--expected-unresolved", type=int, default=1)
    parser.add_argument("--expected-citation-supported", type=int, default=65)
    return parser.parse_args(argv)


def build_policy_review_packet(
    *,
    generated_answer_jsonl: Path,
    review_draft_jsonl: Path,
    applied_diagnostic_json: Path,
    improvement_report_json: Path,
    expected_counts: ExpectedCounts = ExpectedCounts(),
) -> dict[str, Any]:
    generated_rows, generated_errors = read_jsonl_with_errors(generated_answer_jsonl)
    draft_rows, draft_errors = read_jsonl_with_errors(review_draft_jsonl)
    applied = read_json(applied_diagnostic_json)
    improvement = read_json(improvement_report_json)
    applied_rows = ensure_list_of_dicts(applied.get("applied_rows"))

    generated_by_id = rows_by_query_id(generated_rows)
    draft_by_id = rows_by_query_id(draft_rows)
    applied_by_id = rows_by_query_id(applied_rows)
    all_ids = sorted(set(generated_by_id) | set(draft_by_id) | set(applied_by_id))
    action_counts = Counter(clean(row.get("assistant_review_action")) for row in applied_rows)
    citation_counts = Counter(
        clean(row.get("assistant_citation_support_judgment")) for row in applied_rows
    )

    clean_ids = sorted(
        query_id
        for query_id, row in applied_by_id.items()
        if clean(row.get("assistant_review_action")) == KEEP_DIAGNOSTIC_CANDIDATE
    )
    cleanup_ids = sorted(
        query_id
        for query_id, row in applied_by_id.items()
        if clean(row.get("assistant_review_action")) == KEEP_WITH_CLEANUP
    )
    unresolved_ids = sorted(
        query_id
        for query_id, row in applied_by_id.items()
        if clean(row.get("assistant_review_action"))
        not in {KEEP_DIAGNOSTIC_CANDIDATE, KEEP_WITH_CLEANUP}
    )
    model_assisted_ids = sorted(
        query_id
        for query_id in all_ids
        if any(
            row.get("model_assisted") is True
            for row in (
                generated_by_id.get(query_id, {}),
                draft_by_id.get(query_id, {}),
                applied_by_id.get(query_id, {}),
            )
        )
    )
    deterministic_verifier_only_ids = sorted(
        query_id
        for query_id in all_ids
        if query_id not in model_assisted_ids
        and generated_by_id.get(query_id, {}).get("official_metric_input") is False
    )
    deterministic_claim_repair_ids = sorted(
        query_id
        for query_id, row in generated_by_id.items()
        if row.get("deterministic_claim_repair") is True
    )
    official_metric_blocked_ids = sorted(
        query_id
        for query_id in all_ids
        if all(
            row.get("official_metric_input") is False
            for row in (
                generated_by_id.get(query_id, {}),
                draft_by_id.get(query_id, {}),
                applied_by_id.get(query_id, {}),
            )
            if row
        )
    )
    audit_sample_ids = stratified_clean_audit_sample(
        clean_ids=clean_ids,
        generated_by_id=generated_by_id,
        model_assisted_ids=set(model_assisted_ids),
        deterministic_verifier_only_ids=set(deterministic_verifier_only_ids),
        improved_ids=set(improvement_ids(improvement)),
        target_size=12,
    )

    metrics = diagnostic_metric_preview(
        row_count=len(applied_rows),
        clean_count=len(clean_ids),
        cleanup_count=len(cleanup_ids),
        unresolved_count=len(unresolved_ids),
        citation_supported_count=citation_counts.get(FULLY_SUPPORTED, 0),
        improvement=improvement,
    )
    validation_errors = validate_packet_inputs(
        generated_rows=generated_rows,
        draft_rows=draft_rows,
        applied_rows=applied_rows,
        generated_errors=generated_errors,
        draft_errors=draft_errors,
        generated_by_id=generated_by_id,
        draft_by_id=draft_by_id,
        applied_by_id=applied_by_id,
        action_counts=action_counts,
        citation_counts=citation_counts,
        applied=applied,
        improvement=improvement,
        metrics=metrics,
        expected_counts=expected_counts,
    )
    status = PASS_STATUS if not validation_errors else FAIL_STATUS
    user_rows = (
        review_rows(cleanup_ids, applied_by_id, generated_by_id, "cleanup", True, False)
        + review_rows(unresolved_ids, applied_by_id, generated_by_id, "unresolved", True, False)
        + review_rows(
            audit_sample_ids,
            applied_by_id,
            generated_by_id,
            "clean_pass_audit_sample",
            False,
            True,
        )
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "scope": "text_namu_v2_1_answer_citation_policy_review_packet_diagnostic_only",
        "diagnostic_only": True,
        "not_official_metric": True,
        "model_assisted_output_not_human_approved_gold": True,
        "row_count": len(applied_rows),
        "source_artifacts": {
            "generated_answer_review_input_local_llm_v2_1_jsonl": artifact_info(
                generated_answer_jsonl
            ),
            "answer_citation_review_draft_local_llm_v2_1_jsonl": artifact_info(
                review_draft_jsonl
            ),
            "applied_diagnostic_v2_1_json": artifact_info(applied_diagnostic_json),
            "improvement_report_v2_1_json": artifact_info(improvement_report_json),
        },
        "diagnostic_metric_preview": metrics,
        "row_groups": {
            "clean_pass_rows": row_group(clean_ids),
            "cleanup_rows": row_group(cleanup_ids),
            "unresolved_rows": row_group(unresolved_ids),
            "model_assisted_rows": row_group(model_assisted_ids),
            "deterministic_verifier_only_rows": row_group(deterministic_verifier_only_ids),
            "deterministic_claim_repair_rows": row_group(deterministic_claim_repair_ids),
            "official_metric_blocked_rows": row_group(official_metric_blocked_ids),
        },
        "user_review": {
            "included_row_count": len(user_rows),
            "cleanup_row_count": len(cleanup_ids),
            "unresolved_row_count": len(unresolved_ids),
            "clean_pass_audit_sample_count": len(audit_sample_ids),
            "clean_pass_audit_sample_strategy": (
                "deterministic stratified sample across model-assisted, "
                "deterministic verifier-only, improved, and sorted clean-pass rows"
            ),
            "rows_requiring_human_decision": user_rows,
        },
        "policy_options": policy_options(),
        "selected_policy_option": None,
        "guardrails": guardrails(metrics),
        "validation": {
            "ok": not validation_errors,
            "errors": validation_errors,
            "expected_counts": {
                "total_rows": expected_counts.total_rows,
                "clean_pass": expected_counts.clean_pass,
                "cleanup": expected_counts.cleanup,
                "unresolved": expected_counts.unresolved,
                "citation_supported": expected_counts.citation_supported,
            },
            "actual_counts": {
                "total_rows": len(applied_rows),
                "clean_pass": len(clean_ids),
                "cleanup": len(cleanup_ids),
                "unresolved": len(unresolved_ids),
                "citation_supported": citation_counts.get(FULLY_SUPPORTED, 0),
                "generated_rows": len(generated_rows),
                "draft_rows": len(draft_rows),
            },
        },
        "remaining_blockers": [
            "Human policy decision is required before any official metric lane can open.",
            "Model-assisted rows are diagnostic output, not human-approved official labels.",
            "The unresolved row is excluded from all diagnostic pass previews.",
        ],
    }


def diagnostic_metric_preview(
    *,
    row_count: int,
    clean_count: int,
    cleanup_count: int,
    unresolved_count: int,
    citation_supported_count: int,
    improvement: Mapping[str, Any],
) -> dict[str, Any]:
    target_status = (
        ensure_mapping(improvement.get("v2_vs_v2_1")).get("diagnostic_quality_target_status", {})
    )
    target_status = ensure_mapping(target_status)
    return {
        "strict_clean_answer_preview": {
            "numerator": clean_count,
            "denominator": row_count,
        },
        "cleanup_inclusive_answer_preview": {
            "numerator": clean_count + cleanup_count,
            "denominator": row_count,
        },
        "citation_supported_preview": {
            "numerator": citation_supported_count,
            "denominator": row_count,
        },
        "unresolved_count": unresolved_count,
        "official_metric_input_rows": 0,
        "official_metric_status": OFFICIAL_METRIC_STATUS,
        "metric_preview_candidate": target_status.get("metric_preview_candidate") is True,
        "metric_pass_candidate": target_status.get("metric_pass_candidate") is True,
        "official_metric_opened": False,
        "diagnostic_preview_not_official_metric": True,
    }


def validate_packet_inputs(
    *,
    generated_rows: list[dict[str, Any]],
    draft_rows: list[dict[str, Any]],
    applied_rows: list[dict[str, Any]],
    generated_errors: list[str],
    draft_errors: list[str],
    generated_by_id: Mapping[str, Mapping[str, Any]],
    draft_by_id: Mapping[str, Mapping[str, Any]],
    applied_by_id: Mapping[str, Mapping[str, Any]],
    action_counts: Counter[str],
    citation_counts: Counter[str],
    applied: Mapping[str, Any],
    improvement: Mapping[str, Any],
    metrics: Mapping[str, Any],
    expected_counts: ExpectedCounts,
) -> list[str]:
    errors: list[str] = []
    errors.extend(f"generated-answer JSONL parse error: {error}" for error in generated_errors)
    errors.extend(f"review draft JSONL parse error: {error}" for error in draft_errors)
    if len(generated_rows) != expected_counts.total_rows:
        errors.append(f"generated-answer row count must be {expected_counts.total_rows}")
    if len(draft_rows) != expected_counts.total_rows:
        errors.append(f"review draft row count must be {expected_counts.total_rows}")
    if len(applied_rows) != expected_counts.total_rows:
        errors.append(f"applied row count must be {expected_counts.total_rows}")
    generated_ids = set(generated_by_id)
    draft_ids = set(draft_by_id)
    applied_ids = set(applied_by_id)
    if generated_ids != draft_ids or generated_ids != applied_ids:
        errors.append("generated, draft, and applied query_id sets must match")
    for label, rows in (
        ("generated-answer", generated_rows),
        ("review draft", draft_rows),
        ("applied", applied_rows),
    ):
        duplicate_ids = duplicate_query_ids(rows)
        blank_rows = blank_query_id_row_numbers(rows)
        if duplicate_ids:
            errors.append(
                f"{label} rows must have unique query_id values: {', '.join(duplicate_ids)}"
            )
        if blank_rows:
            errors.append(
                f"{label} rows must have non-empty query_id values: "
                + ", ".join(str(row_number) for row_number in blank_rows)
            )
    if action_counts.get(KEEP_DIAGNOSTIC_CANDIDATE, 0) != expected_counts.clean_pass:
        errors.append(f"clean pass count must be {expected_counts.clean_pass}")
    if action_counts.get(KEEP_WITH_CLEANUP, 0) != expected_counts.cleanup:
        errors.append(f"cleanup count must be {expected_counts.cleanup}")
    unresolved = len(applied_rows) - action_counts.get(KEEP_DIAGNOSTIC_CANDIDATE, 0) - action_counts.get(
        KEEP_WITH_CLEANUP, 0
    )
    if unresolved != expected_counts.unresolved:
        errors.append(f"unresolved count must be {expected_counts.unresolved}")
    if citation_counts.get(FULLY_SUPPORTED, 0) != expected_counts.citation_supported:
        errors.append(f"citation fully supported count must be {expected_counts.citation_supported}")
    applied_metrics = ensure_mapping(applied.get("diagnostic_metric_preview"))
    if applied_metrics.get("official_metric_input_rows") != 0:
        errors.append("applied diagnostic official_metric_input_rows must be 0")
    if applied_metrics.get("official_metric_status") != OFFICIAL_METRIC_STATUS:
        errors.append("applied diagnostic official_metric_status must remain fail-closed")
    if applied_metrics.get("answer_pass_preview_count") != expected_counts.clean_pass:
        errors.append("applied diagnostic clean preview count mismatch")
    if applied_metrics.get("cleanup_pass_preview_count") != expected_counts.cleanup:
        errors.append("applied diagnostic cleanup preview count mismatch")
    if applied_metrics.get("unresolved_diagnostic_count") != expected_counts.unresolved:
        errors.append("applied diagnostic unresolved count mismatch")
    if (
        applied_metrics.get("citation_fully_supported_generated_answer_count")
        != expected_counts.citation_supported
    ):
        errors.append("applied diagnostic citation-supported count mismatch")
    v2_vs_v2_1 = ensure_mapping(improvement.get("v2_vs_v2_1"))
    if v2_vs_v2_1.get("official_metric_input_rows") != 0:
        errors.append("improvement report official_metric_input_rows must be 0")
    if v2_vs_v2_1.get("official_metric_status") != OFFICIAL_METRIC_STATUS:
        errors.append("improvement report official_metric_status must remain fail-closed")
    if ensure_mapping(applied.get("validation")).get("ok") is not True:
        errors.append("applied diagnostic validation must be ok")
    for label, rows in (
        ("generated-answer", generated_rows),
        ("review draft", draft_rows),
        ("applied", applied_rows),
    ):
        if any(row.get("official_metric_input") is not False for row in rows):
            errors.append(f"{label} rows must keep official_metric_input=false")
        if any(row.get("promotion_evidence") is not False for row in rows):
            errors.append(f"{label} rows must keep promotion_evidence=false")
        if any(row.get("diagnostic_only") is not True for row in rows):
            errors.append(f"{label} rows must keep diagnostic_only=true")
    if metrics.get("official_metric_input_rows") != 0:
        errors.append("packet official_metric_input_rows must be 0")
    if metrics.get("official_metric_status") != OFFICIAL_METRIC_STATUS:
        errors.append("packet official metric status must remain fail-closed")
    return errors


def review_rows(
    query_ids: list[str],
    applied_by_id: Mapping[str, Mapping[str, Any]],
    generated_by_id: Mapping[str, Mapping[str, Any]],
    review_bucket: str,
    human_decision_needed: bool,
    included_for_audit: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query_id in query_ids:
        applied_row = applied_by_id[query_id]
        generated_row = generated_by_id.get(query_id, {})
        rows.append(
            {
                "query_id": query_id,
                "review_bucket": review_bucket,
                "query": clean(applied_row.get("query") or generated_row.get("safe_query_text")),
                "assistant_review_action": clean(applied_row.get("assistant_review_action")),
                "assistant_answer_judgment": clean(applied_row.get("assistant_answer_judgment")),
                "assistant_citation_support_judgment": clean(
                    applied_row.get("assistant_citation_support_judgment")
                ),
                "suggested_extractive_answer_not_gold": clean(
                    applied_row.get("suggested_extractive_answer_not_gold")
                    or generated_row.get("rewritten_answer")
                ),
                "generated_short_answer": clean(
                    applied_row.get("generated_short_answer") or generated_row.get("rewritten_answer")
                ),
                "evidence_spans": clean_string_list(
                    applied_row.get("evidence_spans") or generated_row.get("evidence_spans")
                ),
                "cited_chunk_ids": clean_string_list(
                    applied_row.get("cited_chunk_ids") or generated_row.get("cited_chunk_ids")
                ),
                "failure_causes": clean_string_list(applied_row.get("failure_causes")),
                "model_assisted": any(
                    row.get("model_assisted") is True for row in (applied_row, generated_row)
                ),
                "deterministic_verifier_only": not any(
                    row.get("model_assisted") is True for row in (applied_row, generated_row)
                ),
                "deterministic_claim_repair": generated_row.get("deterministic_claim_repair") is True,
                "not_human_approved": True,
                "human_decision_needed": human_decision_needed,
                "included_for_audit": included_for_audit,
                "official_metric_input": False,
                "promotion_evidence": False,
                "decision_options": decision_options_for_bucket(review_bucket),
            }
        )
    return rows


def stratified_clean_audit_sample(
    *,
    clean_ids: list[str],
    generated_by_id: Mapping[str, Mapping[str, Any]],
    model_assisted_ids: set[str],
    deterministic_verifier_only_ids: set[str],
    improved_ids: set[str],
    target_size: int,
) -> list[str]:
    sample: list[str] = []

    def add(ids: Iterable[str], limit: int) -> None:
        for query_id in evenly_spaced(sorted(set(ids)), limit):
            if query_id in clean_ids and query_id not in sample:
                sample.append(query_id)

    add((query_id for query_id in clean_ids if query_id in improved_ids), 4)
    add((query_id for query_id in clean_ids if query_id in model_assisted_ids), 4)
    add((query_id for query_id in clean_ids if query_id in deterministic_verifier_only_ids), 4)
    add(
        (
            query_id
            for query_id in clean_ids
            if generated_by_id.get(query_id, {}).get("deterministic_claim_repair") is True
        ),
        2,
    )
    add(clean_ids, target_size)
    return sample[:target_size]


def evenly_spaced(ids: list[str], limit: int) -> list[str]:
    if limit <= 0 or not ids:
        return []
    if len(ids) <= limit:
        return ids
    if limit == 1:
        return [ids[0]]
    step = (len(ids) - 1) / (limit - 1)
    indexes = sorted({round(index * step) for index in range(limit)})
    return [ids[index] for index in indexes]


def policy_options() -> list[dict[str, str]]:
    return [
        {
            "option_id": "keep_diagnostic_only",
            "label": "Keep diagnostic-only",
            "meaning": "Use the packet only for review discussion; do not treat previews as official.",
        },
        {
            "option_id": "allow_diagnostic_metric_preview_only",
            "label": "Allow diagnostic metric preview only",
            "meaning": "Share the preview counts while official metric inputs remain closed.",
        },
        {
            "option_id": "open_official_metric_candidate_after_human_audit",
            "label": "Open official metric candidate after human audit",
            "meaning": "Consider opening the official lane only after the listed human-review rows are audited.",
        },
        {
            "option_id": "require_full_66_row_human_review_before_official_metric",
            "label": "Require full 66-row human review before official metric",
            "meaning": "Require every row to be manually reviewed before any official metric candidate is prepared.",
        },
    ]


def decision_options_for_bucket(review_bucket: str) -> list[str]:
    if review_bucket == "cleanup":
        return [
            "accept_as_cleanup_only_diagnostic",
            "request_answer_cleanup_before_human_approval",
            "mark_unresolved",
        ]
    if review_bucket == "unresolved":
        return [
            "keep_unresolved",
            "request_new_source_bound_rewrite",
            "mark_not_answerable_from_cited_context",
        ]
    return [
        "accept_clean_pass_sample",
        "request_manual_review",
        "move_to_cleanup_or_unresolved",
    ]


def guardrails(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "official_metric_input_rows": metrics["official_metric_input_rows"],
        "promotion_evidence_rows": 0,
        "official_metrics_opened": False,
        "official_metric_candidate_opened": False,
        "official_denominator_registry_opened": False,
        "official_denominator_registry_mutation": False,
        "gold_registry_opened": False,
        "gold_registry_mutation": False,
        "candidate_artifact_mutation": False,
        "immutable_baseline_mutation": False,
        "production_namespace_vector_index_mutation": False,
        "production_vector_index_mutation": False,
        "promotion_evidence_mutation": False,
        "route_fallback_labels_diagnostic_only": True,
        "model_assisted_output_not_human_approved_gold": True,
    }


def render_markdown(packet: Mapping[str, Any]) -> str:
    metrics = packet["diagnostic_metric_preview"]
    row_groups = packet["row_groups"]
    user_review = packet["user_review"]
    validation = packet["validation"]
    lines = [
        "# TEXT/Namu V2.1 Answer/Citation Policy Review Packet",
        "",
        f"- status: `{packet['status']}`",
        f"- row_count: `{packet['row_count']}`",
        f"- diagnostic_only: `{packet['diagnostic_only']}`",
        f"- official_metric_status: `{metrics['official_metric_status']}`",
        f"- selected_policy_option: `{packet['selected_policy_option']}`",
        "",
        "## Diagnostic Metric Preview",
        "",
        "| preview | count |",
        "| --- | ---: |",
        format_metric_row("strict_clean_answer_preview", metrics["strict_clean_answer_preview"]),
        format_metric_row(
            "cleanup_inclusive_answer_preview",
            metrics["cleanup_inclusive_answer_preview"],
        ),
        format_metric_row("citation_supported_preview", metrics["citation_supported_preview"]),
        f"| unresolved_count | {metrics['unresolved_count']} |",
        f"| official_metric_input_rows | {metrics['official_metric_input_rows']} |",
        "",
        "## Row Separation",
        "",
        "| group | rows |",
        "| --- | ---: |",
        f"| clean pass | {row_groups['clean_pass_rows']['row_count']} |",
        f"| cleanup | {row_groups['cleanup_rows']['row_count']} |",
        f"| unresolved | {row_groups['unresolved_rows']['row_count']} |",
        f"| model-assisted | {row_groups['model_assisted_rows']['row_count']} |",
        f"| deterministic verifier-only | {row_groups['deterministic_verifier_only_rows']['row_count']} |",
        f"| official metric blocked | {row_groups['official_metric_blocked_rows']['row_count']} |",
        "",
        "## User Decision Surface",
        "",
        f"- cleanup rows: `{user_review['cleanup_row_count']}`",
        f"- unresolved rows: `{user_review['unresolved_row_count']}`",
        f"- clean pass audit sample: `{user_review['clean_pass_audit_sample_count']}`",
        "",
        "| bucket | query_id | action | citation |",
        "| --- | --- | --- | --- |",
    ]
    for row in user_review["rows_requiring_human_decision"]:
        lines.append(
            "| {bucket} | `{query_id}` | `{action}` | `{citation}` |".format(
                bucket=row["review_bucket"],
                query_id=row["query_id"],
                action=row["assistant_review_action"],
                citation=row["assistant_citation_support_judgment"],
            )
        )
    lines.extend(
        [
            "",
            "## Policy Options",
            "",
        ]
    )
    for option in packet["policy_options"]:
        lines.append(f"- `{option['option_id']}`: {option['meaning']}")
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            f"- official metrics opened: `{packet['guardrails']['official_metrics_opened']}`",
            f"- official denominator registry opened: `{packet['guardrails']['official_denominator_registry_opened']}`",
            f"- official metric input rows: `{packet['guardrails']['official_metric_input_rows']}`",
            f"- promotion evidence rows: `{packet['guardrails']['promotion_evidence_rows']}`",
            "- model-assisted output is not human-approved gold: "
            f"`{packet['guardrails']['model_assisted_output_not_human_approved_gold']}`",
            f"- validation ok: `{validation['ok']}`",
            "",
            "## Remaining Blockers",
            "",
        ]
    )
    lines.extend(f"- {blocker}" for blocker in packet.get("remaining_blockers", []))
    lines.extend(
        [
            "",
        ]
    )
    if validation["errors"]:
        lines.append("## Validation Errors")
        lines.append("")
        lines.extend(f"- {error}" for error in validation["errors"])
        lines.append("")
    return "\n".join(lines)


def format_metric_row(label: str, metric: Mapping[str, int]) -> str:
    return f"| {label} | {metric['numerator']} / {metric['denominator']} |"


def row_group(query_ids: list[str]) -> dict[str, Any]:
    return {"row_count": len(query_ids), "query_ids": query_ids}


def improvement_ids(improvement: Mapping[str, Any]) -> list[str]:
    return clean_string_list(ensure_mapping(improvement.get("v2_vs_v2_1")).get("rows_improved"))


def rows_by_query_id(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {clean(row.get("query_id")): row for row in rows if clean(row.get("query_id"))}


def duplicate_query_ids(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    counts = Counter(clean(row.get("query_id")) for row in rows if clean(row.get("query_id")))
    return sorted(query_id for query_id, count in counts.items() if count > 1)


def blank_query_id_row_numbers(rows: Iterable[Mapping[str, Any]]) -> list[int]:
    return [row_number for row_number, row in enumerate(rows, start=1) if not clean(row.get("query_id"))]


def ensure_list_of_dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def ensure_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_jsonl_with_errors(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    if not path.exists():
        return rows, [f"{repo_relative(path)}: missing"]
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{repo_relative(path)}:{line_number}: {exc.msg}")
                continue
            if not isinstance(payload, dict):
                errors.append(f"{repo_relative(path)}:{line_number}: row must be a JSON object")
                continue
            rows.append(payload)
    return rows, errors


def clean_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace("|", ";").replace(",", ";").split(";") if part.strip()]
    if isinstance(value, Iterable):
        return [clean(item) for item in value if clean(item)]
    return []


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def artifact_info(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_if_exists(path),
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


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


if __name__ == "__main__":
    raise SystemExit(main())
