"""Generate the human audit packet before official metric transition.

The packet contains only user-owned decisions: expected answer/evidence
semantics, answerability, relevance, final gold policy, denominator inclusion,
and CONTENT-vs-FILE lane policy where needed. Diagnostic-only and already
policy-blocked rows are summarized but are not promoted.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
REVIEW_DIR = AI_WORKER_ROOT / "eval" / "review"

DEFAULT_TEXT_PACKET = REVIEW_DIR / "rag_text_namu_answer_citation_policy_review_packet_v2_1.json"
DEFAULT_XLSX_PACKET = REPORT_DIR / "rag_xlsx_answer_citation_policy_review_packet_v1.json"
DEFAULT_PDF_ANSWER_PACKET = REPORT_DIR / "rag_pdf_answer_citation_policy_review_packet_v1.json"
DEFAULT_PDF_REVIEW_INPUT = REPORT_DIR / "pdf_answer_citation_diagnostic_review_input.jsonl"
DEFAULT_PDF_QUERY_REPORT = REPO_ROOT / "reports" / "rag_retrieval_eval_pdf_vector_diagnostic_report.json"
DEFAULT_ROUTE_APPLIED = REVIEW_DIR / "route_gold_label_review_applied_v1.json"
DEFAULT_FALLBACK_APPLIED = REVIEW_DIR / "fallback_outcome_label_review_applied_v1.json"
DEFAULT_ANSWER_RECOVERY_REPORT = REPORT_DIR / "answer_recovery_tuning_report.md"
DEFAULT_OUTPUT_JSON = REVIEW_DIR / "rag_human_audit_packet_v1.json"
DEFAULT_OUTPUT_MD = REVIEW_DIR / "rag_human_audit_packet_v1.md"

SCHEMA_VERSION = "rag_human_audit_packet_v1"

DECISION_VALUES = [
    "INCLUDE_AS_OFFICIAL_GOLD_CANDIDATE",
    "EXCLUDE_FROM_OFFICIAL_GOLD",
    "KEEP_PENDING_EVIDENCE",
    "KEEP_PENDING_ANSWERABILITY",
    "KEEP_PENDING_RELEVANCE",
    "KEEP_PENDING_FILE_IDENTITY",
    "CONTENT_LANE_ONLY",
    "FILE_IDENTITY_LANE_ONLY",
    "DO_NOT_INCLUDE_IN_OFFICIAL_DENOMINATOR",
    "NEEDS_USER_REWRITE_OF_EXPECTED_ANSWER",
    "NEEDS_USER_REWRITE_OF_EXPECTED_EVIDENCE",
]

DECISION_TYPES = [
    "expected_answer_evidence_semantics",
    "answerability_label",
    "relevance_label",
    "final_gold_policy",
    "official_denominator_inclusion",
]

PROTECTED_SOURCE_GUARDRAILS = (
    "official_denominator_registry_mutation",
    "official_denominator_registry_changed",
    "official_denominator_registry_opened",
    "gold_registry_mutation",
    "official_denominator_opened",
    "official_denominator_opened_or_frozen",
    "promotion_evidence_created",
    "production_namespace_mutated",
    "production_vector_index_mutated",
    "production_vector_written",
    "candidate_artifact_mutated",
    "immutable_baseline_mutated",
    "model_assisted_outputs_promoted_to_gold",
    "answer_generation_run",
    "pdf_answer_generation_denominator_opened",
    "pdf_answer_generation_opened",
    "pdf_content_file_lanes_aggregated",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = run_packet(
        text_packet_path=Path(args.text_packet),
        xlsx_packet_path=Path(args.xlsx_packet),
        pdf_answer_packet_path=Path(args.pdf_answer_packet),
        pdf_review_input_path=Path(args.pdf_review_input),
        pdf_query_report_path=Path(args.pdf_query_report),
        route_applied_path=Path(args.route_applied),
        fallback_applied_path=Path(args.fallback_applied),
        answer_recovery_report_path=Path(args.answer_recovery_report),
        output_report=Path(args.output_report),
        output_md=Path(args.output_md),
    )
    print(
        json.dumps(
            {
                "status": packet["status"],
                "report": packet["artifact_paths"]["report_json"],
                "total_user_action_rows": packet["summary"]["total_user_action_rows"],
                "official_metric_input_rows": packet["official_metric_input_rows"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if packet["validation"]["ok"] else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-packet", default=str(DEFAULT_TEXT_PACKET))
    parser.add_argument("--xlsx-packet", default=str(DEFAULT_XLSX_PACKET))
    parser.add_argument("--pdf-answer-packet", default=str(DEFAULT_PDF_ANSWER_PACKET))
    parser.add_argument("--pdf-review-input", default=str(DEFAULT_PDF_REVIEW_INPUT))
    parser.add_argument("--pdf-query-report", default=str(DEFAULT_PDF_QUERY_REPORT))
    parser.add_argument("--route-applied", default=str(DEFAULT_ROUTE_APPLIED))
    parser.add_argument("--fallback-applied", default=str(DEFAULT_FALLBACK_APPLIED))
    parser.add_argument("--answer-recovery-report", default=str(DEFAULT_ANSWER_RECOVERY_REPORT))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args(argv)


def run_packet(
    *,
    text_packet_path: Path,
    xlsx_packet_path: Path,
    pdf_answer_packet_path: Path,
    pdf_review_input_path: Path,
    pdf_query_report_path: Path,
    route_applied_path: Path,
    fallback_applied_path: Path,
    answer_recovery_report_path: Path,
    output_report: Path,
    output_md: Path,
) -> dict[str, Any]:
    text = read_json(text_packet_path)
    xlsx = read_json(xlsx_packet_path)
    pdf_answer = read_json(pdf_answer_packet_path)
    pdf_rows = read_jsonl(pdf_review_input_path)
    pdf_query_lookup = load_pdf_query_lookup(pdf_query_report_path)
    route = read_json(route_applied_path)
    fallback = read_json(fallback_applied_path)
    answer_recovery = parse_answer_recovery_markdown(answer_recovery_report_path)

    packet = build_packet(
        text=text,
        xlsx=xlsx,
        pdf_answer=pdf_answer,
        pdf_rows=pdf_rows,
        pdf_query_lookup=pdf_query_lookup,
        route=route,
        fallback=fallback,
        answer_recovery=answer_recovery,
        source_paths={
            "text_packet": text_packet_path,
            "xlsx_packet": xlsx_packet_path,
            "pdf_answer_packet": pdf_answer_packet_path,
            "pdf_review_input": pdf_review_input_path,
            "pdf_query_report": pdf_query_report_path,
            "route_applied": route_applied_path,
            "fallback_applied": fallback_applied_path,
            "answer_recovery_report": answer_recovery_report_path,
        },
    )
    packet["artifact_paths"]["report_json"] = repo_relative(output_report)
    packet["artifact_paths"]["report_md"] = repo_relative(output_md)
    write_json(output_report, packet)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(packet), encoding="utf-8")
    return packet


def build_packet(
    *,
    text: Mapping[str, Any],
    xlsx: Mapping[str, Any],
    pdf_answer: Mapping[str, Any],
    pdf_rows: Sequence[Mapping[str, Any]],
    pdf_query_lookup: Mapping[str, str],
    route: Mapping[str, Any],
    fallback: Mapping[str, Any],
    answer_recovery: Mapping[str, Any],
    source_paths: Mapping[str, Path],
) -> dict[str, Any]:
    actionable: list[dict[str, Any]] = []
    sections: dict[str, Any] = {}

    text_rows, text_non_action = text_action_rows(text)
    actionable.extend(text_rows)
    sections["text_namu_v2_1"] = {
        "actionable_rows": [row["row_id"] for row in text_rows],
        "cleanup_rows_requiring_action": sum(1 for row in text_rows if row["issue_type"] == "TEXT_CLEANUP_EXPECTED_ANSWER_EVIDENCE"),
        "unresolved_rows_requiring_action": sum(1 for row in text_rows if row["issue_type"] == "TEXT_UNRESOLVED_ANSWERABILITY"),
        "non_action_summary": text_non_action,
        "official_metric_input_rows": source_official_metric_input_rows(text),
        **source_contract("text_namu_v2_1", text),
    }

    xlsx_rows, xlsx_section = xlsx_action_rows_and_section(xlsx)
    actionable.extend(xlsx_rows)
    sections["xlsx_business_structured"] = xlsx_section

    answer_recovery_rows, answer_recovery_section = answer_recovery_action_rows(answer_recovery)
    answer_recovery_ids = {row["row_id"] for row in answer_recovery_rows}
    pdf_direct_rows, pdf_section = pdf_action_rows_and_section(
        pdf_answer=pdf_answer,
        pdf_rows=pdf_rows,
        pdf_query_lookup=pdf_query_lookup,
        answer_recovery_action_ids=answer_recovery_ids,
    )
    actionable.extend(pdf_direct_rows)
    actionable.extend(answer_recovery_rows)
    sections["pdf_business_ocr_mm"] = pdf_section
    sections["route_fallback"] = route_fallback_section(route, fallback)
    sections["answer_recovery"] = answer_recovery_section
    sections["source_artifact_checks"] = {
        name: {"exists": path.exists(), "bytes": path.stat().st_size if path.exists() else 0}
        for name, path in source_paths.items()
    }

    summary = packet_summary(actionable, sections)
    validation_errors = validation_errors_for(actionable, sections)
    packet = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": "HUMAN_AUDIT_PACKET_READY" if not validation_errors else "FAILED_GUARDRAIL",
        "report_role": "human_audit_packet_before_official_metric_transition",
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric": False,
        "official_metric_input_rows": 0,
        "summary": summary,
        "sections": sections,
        "actionable_rows": sorted(actionable, key=lambda row: (row["track"], row["row_id"])),
        "decision_schema": {
            "required_fields": [
                "row_id",
                "query_id",
                "track",
                "question",
                "current_diagnostic_status",
                "proposed_evidence",
                "proposed_answer",
                "citation_locator",
                "issue_type",
                "required_user_decision",
                "allowed_decision_values",
                "codex_recommendation",
                "why_codex_cannot_finalize_this_as_non_gold",
                "official_denominator_current",
                "promotion_evidence",
            ],
            "allowed_decision_values": DECISION_VALUES,
        },
        "source_artifacts": {name: file_identity(path) for name, path in source_paths.items()},
        "artifact_paths": {"report_json": "", "report_md": ""},
        "validation": {"ok": not validation_errors, "errors": validation_errors},
    }
    return packet


def text_action_rows(text: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = nested_sequence(text, "user_review", "rows_requiring_human_decision")
    actionable: list[dict[str, Any]] = []
    non_action_count = 0
    for row in rows:
        bucket = clean(row.get("review_bucket"))
        human_needed = row.get("human_decision_needed") is True
        if not human_needed and bucket not in {"cleanup", "unresolved"}:
            non_action_count += 1
            continue
        issue_type = "TEXT_UNRESOLVED_ANSWERABILITY" if bucket == "unresolved" else "TEXT_CLEANUP_EXPECTED_ANSWER_EVIDENCE"
        actionable.append(
            base_action_row(
                row_id=clean(row.get("query_id")),
                track="text_namu_v2_1",
                question=clean(row.get("query")),
                status=bucket or "human_decision_required",
                proposed_evidence=first_text(row.get("evidence_spans")),
                proposed_answer=clean(row.get("generated_short_answer") or row.get("suggested_extractive_answer_not_gold")),
                citation_locator={"cited_chunk_ids": list(row.get("cited_chunk_ids") or [])},
                issue_type=issue_type,
                required_user_decision=(
                    "Confirm expected answer/evidence semantics plus answerability/relevance before any official denominator inclusion."
                ),
                codex_recommendation=(
                    "non_binding_keep_pending_answerability"
                    if bucket == "unresolved"
                    else "non_binding_needs_user_cleanup_or_expected_answer_rewrite"
                ),
                why="The row is diagnostic/model-assisted or cleanup carry-forward and is not human-approved gold.",
            )
        )
    return actionable, {
        "clean_pass_audit_sample_rows_not_actionable": non_action_count,
        "model_assisted_rows_not_human_approved": int_value(nested_mapping(text, "user_review").get("included_row_count")) - len(actionable)
        if nested_mapping(text, "user_review")
        else 0,
    }


def xlsx_action_rows_and_section(xlsx: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pending_rows = [
        row
        for row in nested_sequence(xlsx, "pending_evidence_rows")
        if isinstance(row, Mapping)
    ]
    hidden_or_excluded_pending = [row for row in pending_rows if row_is_hidden_or_excluded(row)]
    eligible_pending_rows = [row for row in pending_rows if not row_is_hidden_or_excluded(row)]
    actionable = [
        base_action_row(
            row_id=clean(row.get("query_id")),
            track="xlsx_business_structured",
            question=clean(row.get("question") or row.get("query") or row.get("query_id")),
            status=clean(row.get("status") or "pending_evidence"),
            proposed_evidence=clean(row.get("proposed_evidence") or row.get("evidence_snippet")),
            proposed_answer=clean(row.get("proposed_answer") or row.get("generated_answer")),
            citation_locator=row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {},
            issue_type="XLSX_PENDING_EVIDENCE_OR_CONSTRAINT",
            required_user_decision="Confirm metric/period/constraint semantics before official denominator inclusion.",
            codex_recommendation="non_binding_keep_pending_evidence",
            why="The row needs user metric or period semantics; strict wrapper expansion must not guess.",
        )
        for row in eligible_pending_rows
    ]
    hidden_excluded = (
        int_value(xlsx.get("hidden_negative_rows"))
        + int_value(xlsx.get("normalized_excluded_rows"))
        + int_value(xlsx.get("pending_excluded_rows"))
        + len(hidden_or_excluded_pending)
    )
    preview = nested_mapping(xlsx, "diagnostic_metric_preview")
    return actionable, {
        "actionable_rows": [row["row_id"] for row in actionable],
        "pending_evidence_rows": len(actionable),
        "strict_silver_clean_rows_summarized_not_action": int_value(preview.get("clean_pass_rows")),
        "hidden_excluded_rows_summarized_not_action": hidden_excluded,
        "hidden_excluded_rows_candidate_count": len(hidden_or_excluded_pending),
        "hidden_excluded_rows_candidate_ids": [clean(row.get("query_id") or row.get("row_id")) for row in hidden_or_excluded_pending],
        "pending_official_metric_rows": sum(1 for row in pending_rows if row_has_official_metric(row)),
        "pending_promotion_evidence_rows": sum(1 for row in pending_rows if row_has_promotion_evidence(row)),
        "official_metric_input_rows": source_official_metric_input_rows(xlsx),
        **source_contract("xlsx_business_structured", xlsx),
    }


def pdf_action_rows_and_section(
    *,
    pdf_answer: Mapping[str, Any],
    pdf_rows: Sequence[Mapping[str, Any]],
    pdf_query_lookup: Mapping[str, str],
    answer_recovery_action_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    actionable: list[dict[str, Any]] = []
    filename_only_accepted = False
    content_file_merge = bool_value(pdf_answer.get("content_file_identity_lane_merge"))
    file_identity_review_rows = 0
    filename_only_rows_accepted = 0
    for row in pdf_rows:
        query_id = clean(row.get("query_id"))
        file_lane = row.get("file_identity_lane") if isinstance(row.get("file_identity_lane"), Mapping) else {}
        filename_only = file_lane.get("filename_only_identity_accepted") is True or row.get("no_filename_only_identity_acceptance") is False
        filename_only_accepted = filename_only_accepted or filename_only
        if filename_only:
            filename_only_rows_accepted += 1
        lane = clean(row.get("content_evidence_lane"))
        if query_id in answer_recovery_action_ids:
            file_identity_review_rows += 1
            continue
        if lane != "pdf_content_evidence":
            continue
        actionable.append(
            base_action_row(
                row_id=query_id,
                track="pdf_business_ocr_mm",
                question=pdf_query_lookup.get(query_id, query_id),
                status=clean(row.get("bucket") or "pdf_answer_citation_diagnostic"),
                proposed_evidence=clean(row.get("matched_text") or row.get("citation_text")),
                proposed_answer=clean(row.get("diagnostic_answer") or row.get("generated_answer")),
                citation_locator=row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {},
                issue_type="PDF_CONTENT_EXPECTED_EVIDENCE_LANE_REVIEW",
                required_user_decision=(
                    "Confirm CONTENT evidence semantics and denominator inclusion while keeping FILE identity separate."
                ),
                codex_recommendation="non_binding_content_lane_only_pending_human_gold_policy",
                why="The row is diagnostic strict-ready evidence, not human-approved official gold.",
                lane_decision_scope="CONTENT_LANE_ONLY",
                content_file_identity_lane_merge=False,
                filename_only_identity_accepted=False,
            )
        )
    return actionable, {
        "actionable_rows": [row["row_id"] for row in actionable],
        "content_rows_actionable": len(actionable),
        "file_identity_rows_actionable": file_identity_review_rows,
        "content_file_identity_lane_merge_detected": content_file_merge,
        "filename_only_identity_accepted": filename_only_accepted,
        "filename_only_identity_rows_accepted": filename_only_rows_accepted,
        "diagnostic_answer_clean_rows": int_value(pdf_answer.get("clean_pass_rows")),
        "official_metric_input_rows": source_official_metric_input_rows(pdf_answer),
        "review_input_official_metric_rows": sum(1 for row in pdf_rows if row_has_official_metric(row)),
        "review_input_promotion_evidence_rows": sum(1 for row in pdf_rows if row_has_promotion_evidence(row)),
        **source_contract("pdf_business_ocr_mm", pdf_answer),
    }


def answer_recovery_action_rows(answer_recovery: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    review_rows = [
        row
        for row in answer_recovery.get("gold_policy_required_user_review", [])
        if isinstance(row, Mapping)
    ]
    actionable: list[dict[str, Any]] = []
    for row in review_rows:
        lane = clean(row.get("lane"))
        track = track_for_answer_recovery_lane(lane)
        lane_scope = "FILE_IDENTITY_LANE_ONLY" if lane == "PDF_FILE_LOOKUP" else ""
        actionable.append(
            base_action_row(
                row_id=clean(row.get("row_id")),
                track=track,
                question=clean(row.get("question") or row.get("row_id")),
                status="GOLD_POLICY_REQUIRED",
                proposed_evidence=clean(row.get("reason")),
                proposed_answer="",
                citation_locator={"lane": lane, "case_type": clean(row.get("case_type"))},
                issue_type="ANSWER_RECOVERY_GOLD_POLICY_REQUIRED",
                required_user_decision=clean(row.get("judgment_needed"))
                or "User gold-policy judgment is required before recovery can be considered.",
                codex_recommendation="non_binding_keep_pending_gold_policy",
                why="The row requires user-owned gold policy and denominator inclusion semantics.",
                lane_decision_scope=lane_scope,
                content_file_identity_lane_merge=False,
                filename_only_identity_accepted=False,
            )
        )
    non_action = answer_recovery.get("row_group_counts", {})
    row_group_ids = answer_recovery.get("row_group_ids") if isinstance(answer_recovery.get("row_group_ids"), Mapping) else {}
    category_counts = answer_recovery.get("category_counts") if isinstance(answer_recovery.get("category_counts"), Mapping) else {}
    expected_from_category = int_value(category_counts.get("GOLD_POLICY_REQUIRED"))
    expected_from_groups = int_value(non_action.get("gold_policy_required"))
    expected_ids = {clean(value) for value in row_group_ids.get("gold_policy_required", [])}
    actual_ids = {row["row_id"] for row in actionable}
    return actionable, {
        "gold_policy_required_rows": len(actionable),
        "expected_gold_policy_required_rows": expected_from_category,
        "row_group_gold_policy_required_rows": expected_from_groups,
        "gold_policy_required_count_matches_report": (
            expected_from_category == len(actionable) and expected_from_groups == len(actionable)
        ),
        "gold_policy_required_ids_match_report": expected_ids == actual_ids,
        "expected_gold_policy_required_ids": sorted(expected_ids),
        "actual_gold_policy_required_ids": sorted(actual_ids),
        "report_exists": answer_recovery.get("report_exists") is True,
        "parse_errors": list(answer_recovery.get("parse_errors") or []),
        "actionable_rows": [row["row_id"] for row in actionable],
        "non_action_summary": {
            "promotion_candidate": int_value(non_action.get("promotion_candidate")),
            "safe_recoverable_report_only": int_value(non_action.get("safe_recoverable_report_only")),
            "index_scope_missing": int_value(non_action.get("index_scope_missing")),
            "policy_blocked_correctly": int_value(non_action.get("policy_blocked_correctly")),
            "diagnostic_only_do_not_promote": int_value(non_action.get("diagnostic_only")),
            "unknown_needs_manual_review": int_value(non_action.get("unknown_needs_manual_review")),
        },
    }


def route_fallback_section(route: Mapping[str, Any], fallback: Mapping[str, Any]) -> dict[str, Any]:
    route_rows = unresolved_route_rows(route)
    fallback_rows = unresolved_route_rows(fallback)
    return {
        "actionable_rows": route_rows + fallback_rows,
        "route_diagnostic_only": route.get("diagnostic_only") is True,
        "fallback_diagnostic_only": fallback.get("diagnostic_only") is True,
        "route_source_official_metric": route.get("official_metric") is True,
        "fallback_source_official_metric": fallback.get("official_metric") is True,
        "route_source_promotion_evidence": route.get("promotion_evidence") is True,
        "fallback_source_promotion_evidence": fallback.get("promotion_evidence") is True,
        "route_source_validation_ok": source_validation_ok(route),
        "fallback_source_validation_ok": source_validation_ok(fallback),
        "route_source_protected_guardrail_violations": protected_source_guardrail_violations(route),
        "fallback_source_protected_guardrail_violations": protected_source_guardrail_violations(fallback),
        "route_metrics_official": route.get("route_metrics_official") is True,
        "fallback_metrics_official": fallback.get("fallback_metrics_official") is True,
        "route_official_metric_input_rows": source_official_metric_input_rows(route),
        "fallback_official_metric_input_rows": source_official_metric_input_rows(fallback),
        "diagnostic_only_rows_summarized_not_action": int_value(nested_mapping(route, "counts").get("codex_diagnostic_only_rows_unchanged"))
        + int_value(nested_mapping(fallback, "counts").get("codex_diagnostic_only_rows_unchanged")),
        "applied_human_review_rows_summarized": len(nested_sequence(route, "applied_human_review_rows"))
        + len(nested_sequence(fallback, "applied_human_review_rows")),
    }


def unresolved_route_rows(payload: Mapping[str, Any]) -> list[str]:
    rows: list[str] = []
    for row in nested_sequence(payload, "applied_human_review_rows"):
        status = clean(row.get("label_status")).lower()
        if status and status not in {"applied", "applied_user_review", "resolved", "complete"}:
            rows.append(clean(row.get("query_id")))
    return rows


def packet_summary(actionable: Sequence[Mapping[str, Any]], sections: Mapping[str, Any]) -> dict[str, Any]:
    by_track = Counter(row["track"] for row in actionable)
    decision_counts = {decision_type: len(actionable) for decision_type in DECISION_TYPES}
    rows_not_action = 0
    rows_not_action += int_value(nested_mapping(sections, "text_namu_v2_1", "non_action_summary").get("clean_pass_audit_sample_rows_not_actionable"))
    rows_not_action += int_value(nested_mapping(sections, "xlsx_business_structured").get("strict_silver_clean_rows_summarized_not_action"))
    rows_not_action += int_value(nested_mapping(sections, "xlsx_business_structured").get("hidden_excluded_rows_summarized_not_action"))
    rows_not_action += int_value(nested_mapping(sections, "route_fallback").get("diagnostic_only_rows_summarized_not_action"))
    rows_not_action += sum(
        int_value(value)
        for value in nested_mapping(sections, "answer_recovery", "non_action_summary").values()
    )
    return {
        "total_user_action_rows": len(actionable),
        "rows_by_track": {track: by_track[track] for track in sorted(by_track)},
        "decision_type_counts": decision_counts,
        "rows_not_requiring_user_action": rows_not_action,
        "official_rows_still_0": True,
    }


def validation_errors_for(actionable: Sequence[Mapping[str, Any]], sections: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if any(row.get("official_denominator_current") is not False for row in actionable):
        errors.append("actionable rows must keep official_denominator_current=false")
    if any(row.get("promotion_evidence") is not False for row in actionable):
        errors.append("actionable rows must keep promotion_evidence=false")
    if any(row_has_official_metric(row) for row in actionable):
        errors.append("actionable rows must not carry official metric flags")
    if any(row_has_promotion_evidence(row) for row in actionable):
        errors.append("actionable rows must not carry promotion evidence flags")
    if any("hidden_blocked" in clean(row.get("row_id")) for row in actionable):
        errors.append("hidden/excluded XLSX rows must not be human audit candidates")
    xlsx_section = nested_mapping(sections, "xlsx_business_structured")
    if xlsx_section.get("hidden_excluded_rows_candidate_count") not in {0, None}:
        errors.append("hidden/excluded XLSX candidate count must be 0")
    if int_value(xlsx_section.get("pending_official_metric_rows")) != 0:
        errors.append("XLSX pending evidence rows must not carry official metric flags")
    if int_value(xlsx_section.get("pending_promotion_evidence_rows")) != 0:
        errors.append("XLSX pending evidence rows must not carry promotion evidence flags")
    for track in ("text_namu_v2_1", "xlsx_business_structured", "pdf_business_ocr_mm"):
        source_section = nested_mapping(sections, track)
        if int_value(source_section.get("official_metric_input_rows")) != 0:
            errors.append(f"{track} official_metric_input_rows must remain 0")
        if source_section.get("source_diagnostic_only") is not True:
            errors.append(f"{track} source artifact must be diagnostic-only")
        if source_section.get("source_official_metric") is True:
            errors.append(f"{track} source artifact must keep official_metric=false")
        if source_section.get("source_promotion_evidence") is True:
            errors.append(f"{track} source artifact must keep promotion_evidence=false")
        if source_section.get("source_validation_ok") is not True:
            errors.append(f"{track} source validation.ok must be true")
        if source_section.get("source_protected_guardrail_violations"):
            errors.append(
                f"{track} source protected guardrail violation: "
                + ", ".join(source_section.get("source_protected_guardrail_violations", []))
            )
    pdf_section = nested_mapping(sections, "pdf_business_ocr_mm")
    if int_value(pdf_section.get("review_input_official_metric_rows")) != 0:
        errors.append("PDF review input rows must not carry official metric flags")
    if int_value(pdf_section.get("review_input_promotion_evidence_rows")) != 0:
        errors.append("PDF review input rows must not carry promotion evidence flags")
    if pdf_section.get("content_file_identity_lane_merge_detected") is True:
        errors.append("PDF content and file identity lanes must not merge")
    if pdf_section.get("filename_only_identity_accepted") is True:
        errors.append("filename-only PDF identity must remain blocked")
    route_section = nested_mapping(sections, "route_fallback")
    if route_section.get("route_diagnostic_only") is not True:
        errors.append("route review rows must remain diagnostic-only")
    if route_section.get("fallback_diagnostic_only") is not True:
        errors.append("fallback review rows must remain diagnostic-only")
    if route_section.get("route_source_official_metric") is True:
        errors.append("route source artifact must keep official_metric=false")
    if route_section.get("fallback_source_official_metric") is True:
        errors.append("fallback source artifact must keep official_metric=false")
    if route_section.get("route_source_promotion_evidence") is True:
        errors.append("route source artifact must keep promotion_evidence=false")
    if route_section.get("fallback_source_promotion_evidence") is True:
        errors.append("fallback source artifact must keep promotion_evidence=false")
    if route_section.get("route_source_validation_ok") is not True:
        errors.append("route source validation.ok must be true")
    if route_section.get("fallback_source_validation_ok") is not True:
        errors.append("fallback source validation.ok must be true")
    if route_section.get("route_source_protected_guardrail_violations"):
        errors.append(
            "route source protected guardrail violation: "
            + ", ".join(route_section.get("route_source_protected_guardrail_violations", []))
        )
    if route_section.get("fallback_source_protected_guardrail_violations"):
        errors.append(
            "fallback source protected guardrail violation: "
            + ", ".join(route_section.get("fallback_source_protected_guardrail_violations", []))
        )
    if route_section.get("route_metrics_official") is True:
        errors.append("route metrics must remain diagnostic-only")
    if route_section.get("fallback_metrics_official") is True:
        errors.append("fallback metrics must remain diagnostic-only")
    if int_value(route_section.get("route_official_metric_input_rows")) != 0:
        errors.append("route official_metric_input_rows must remain 0")
    if int_value(route_section.get("fallback_official_metric_input_rows")) != 0:
        errors.append("fallback official_metric_input_rows must remain 0")
    answer_recovery = nested_mapping(sections, "answer_recovery")
    if answer_recovery.get("report_exists") is not True:
        errors.append("answer recovery report must exist for GOLD_POLICY_REQUIRED audit rows")
    if answer_recovery.get("parse_errors"):
        errors.extend(f"answer recovery parse error: {error}" for error in answer_recovery.get("parse_errors", []))
    if answer_recovery.get("gold_policy_required_count_matches_report") is not True:
        errors.append("answer recovery GOLD_POLICY_REQUIRED rows must match category_counts and row_groups")
    if answer_recovery.get("gold_policy_required_ids_match_report") is not True:
        errors.append("answer recovery GOLD_POLICY_REQUIRED row ids must match row_groups")
    missing_sources = [
        name
        for name, artifact in nested_mapping(sections, "source_artifact_checks").items()
        if not isinstance(artifact, Mapping) or artifact.get("exists") is not True or int_value(artifact.get("bytes")) <= 0
    ]
    if missing_sources:
        errors.append("required source artifacts missing or empty: " + ", ".join(sorted(missing_sources)))
    return errors


def base_action_row(
    *,
    row_id: str,
    track: str,
    question: str,
    status: str,
    proposed_evidence: str,
    proposed_answer: str,
    citation_locator: Mapping[str, Any],
    issue_type: str,
    required_user_decision: str,
    codex_recommendation: str,
    why: str,
    lane_decision_scope: str = "",
    content_file_identity_lane_merge: bool = False,
    filename_only_identity_accepted: bool = False,
) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "query_id": row_id,
        "track": track,
        "question": question,
        "current_diagnostic_status": status,
        "proposed_evidence": proposed_evidence,
        "proposed_answer": proposed_answer,
        "citation_locator": dict(citation_locator),
        "issue_type": issue_type,
        "required_user_decision": required_user_decision,
        "decision_types": list(DECISION_TYPES),
        "allowed_decision_values": list(DECISION_VALUES),
        "codex_recommendation": codex_recommendation,
        "codex_recommendation_binding": False,
        "why_codex_cannot_finalize_this_as_non_gold": why,
        "official_denominator_current": False,
        "promotion_evidence": False,
        "human_label": None,
        "human_notes": None,
        "lane_decision_scope": lane_decision_scope,
        "content_file_identity_lane_merge": content_file_identity_lane_merge,
        "filename_only_identity_accepted": filename_only_identity_accepted,
    }


def parse_answer_recovery_markdown(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "gold_policy_required_user_review": [],
            "row_group_counts": {},
            "category_counts": {},
            "report_exists": False,
            "parse_errors": ["answer_recovery_report_missing"],
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []
    try:
        review_rows = parse_backticked_json(text, "gold_policy_required_user_review")
    except json.JSONDecodeError as exc:
        review_rows = []
        errors.append(f"gold_policy_required_user_review_json_invalid:{exc.msg}")
    if "gold_policy_required_user_review:" not in text:
        errors.append("gold_policy_required_user_review_missing")
    row_groups = parse_row_group_counts(text)
    row_group_ids = parse_row_group_ids(text)
    category_counts = parse_category_counts(text)
    if "gold_policy_required" not in row_groups:
        errors.append("row_groups_gold_policy_required_missing")
    if "GOLD_POLICY_REQUIRED" not in category_counts:
        errors.append("category_counts_GOLD_POLICY_REQUIRED_missing")
    return {
        "gold_policy_required_user_review": review_rows if isinstance(review_rows, list) else [],
        "row_group_counts": row_groups,
        "row_group_ids": row_group_ids,
        "category_counts": category_counts,
        "report_exists": True,
        "parse_errors": errors,
    }


def parse_backticked_json(text: str, label: str) -> Any:
    match = re.search(rf"{re.escape(label)}:\s*`(.+?)`", text, flags=re.DOTALL)
    if not match:
        return []
    return json.loads(match.group(1))


def parse_row_group_counts(text: str) -> dict[str, int]:
    match = re.search(r"row_groups:\s*`(.+?)`", text, flags=re.DOTALL)
    if not match:
        return {}
    raw = match.group(1)
    counts: dict[str, int] = {}
    for group_match in re.finditer(r"([a-zA-Z_]+)=\[(.*?)\](?:,|$)", raw):
        key = group_match.group(1)
        body = group_match.group(2).strip()
        if not body:
            counts[key] = 0
            continue
        try:
            values = ast.literal_eval("[" + body + "]")
        except (SyntaxError, ValueError):
            values = []
        counts[key] = len(values)
    return counts


def parse_row_group_ids(text: str) -> dict[str, list[str]]:
    match = re.search(r"row_groups:\s*`(.+?)`", text, flags=re.DOTALL)
    if not match:
        return {}
    raw = match.group(1)
    groups: dict[str, list[str]] = {}
    for group_match in re.finditer(r"([a-zA-Z_]+)=\[(.*?)\](?:,|$)", raw):
        key = group_match.group(1)
        body = group_match.group(2).strip()
        if not body:
            groups[key] = []
            continue
        try:
            values = ast.literal_eval("[" + body + "]")
        except (SyntaxError, ValueError):
            values = []
        groups[key] = [clean(value) for value in values]
    return groups


def parse_category_counts(text: str) -> dict[str, int]:
    match = re.search(r"category_counts:\s*`(.+?)`", text, flags=re.DOTALL)
    if not match:
        return {}
    counts: dict[str, int] = {}
    for part in match.group(1).split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        counts[key.strip()] = int_value(value.strip())
    return counts


def load_pdf_query_lookup(path: Path) -> dict[str, str]:
    payload = read_json(path)
    lookup: dict[str, str] = {}
    for key in ("per_query", "query_results"):
        for row in payload.get(key, []) if isinstance(payload.get(key), list) else []:
            if isinstance(row, Mapping) and row.get("query_id"):
                lookup[clean(row.get("query_id"))] = clean(row.get("query") or row.get("question"))
    return lookup


def track_for_answer_recovery_lane(lane: str) -> str:
    if lane in {"PDF_FILE_LOOKUP", "PDF_CONTENT"}:
        return "pdf_business_ocr_mm"
    if lane == "XLSX":
        return "xlsx_business_structured"
    if lane == "TEXT":
        return "text_namu_v2_1"
    return "answer_recovery"


def render_markdown(packet: Mapping[str, Any]) -> str:
    summary = packet["summary"]
    lines = [
        "# Human Audit Packet v1",
        "",
        f"- Status: `{packet['status']}`",
        f"- Total user-action rows: `{summary['total_user_action_rows']}`",
        f"- Official metric input rows: `{packet['official_metric_input_rows']}`",
        "- Scope: user decisions only; diagnostic-only rows are summarized, not promoted.",
        "",
        "## Rows By Track",
        "",
    ]
    for track, count in summary["rows_by_track"].items():
        lines.append(f"- `{track}`: `{count}`")
    lines.extend(["", "## Action Rows", ""])
    for row in packet["actionable_rows"]:
        lines.append(
            f"- `{row['row_id']}` `{row['track']}` `{row['issue_type']}` "
            f"decision=`{row['required_user_decision']}`"
        )
    return "\n".join(lines) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
    }


def nested_mapping(payload: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return current if isinstance(current, Mapping) else {}


def nested_sequence(payload: Mapping[str, Any], *keys: str) -> list[Mapping[str, Any]]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return []
        current = current.get(key)
    if not isinstance(current, Sequence) or isinstance(current, (str, bytes)):
        return []
    return [row for row in current if isinstance(row, Mapping)]


def first_text(value: Any) -> str:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return clean(value[0]) if value else ""
    return clean(value)


def int_value(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def source_official_metric_input_rows(payload: Mapping[str, Any]) -> int:
    values = [
        int_value(payload.get("official_metric_input_rows")),
        int_value(nested_mapping(payload, "diagnostic_metric_preview").get("official_metric_input_rows")),
        int_value(nested_mapping(payload, "counts").get("official_metric_input_rows")),
    ]
    return max(values)


def source_contract(name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_name": name,
        "source_diagnostic_only": payload.get("diagnostic_only") is True,
        "source_official_metric": payload.get("official_metric") is True,
        "source_promotion_evidence": payload.get("promotion_evidence") is True,
        "source_validation_ok": source_validation_ok(payload),
        "source_protected_guardrail_violations": protected_source_guardrail_violations(payload),
    }


def source_validation_ok(payload: Mapping[str, Any]) -> bool:
    validation = payload.get("validation") if isinstance(payload.get("validation"), Mapping) else {}
    return validation.get("ok") is True


def protected_source_guardrail_violations(payload: Mapping[str, Any]) -> list[str]:
    guardrails = payload.get("guardrails") if isinstance(payload.get("guardrails"), Mapping) else {}
    source_guardrails = payload.get("source_guardrails") if isinstance(payload.get("source_guardrails"), Mapping) else {}
    return [
        key
        for key in PROTECTED_SOURCE_GUARDRAILS
        if payload.get(key) is True or guardrails.get(key) is True or source_guardrails.get(key) is True
    ]


def row_has_official_metric(row: Mapping[str, Any]) -> bool:
    return (
        row.get("official_metric") is True
        or row.get("official_metric_input") is True
        or row.get("official_denominator_current") is True
        or int_value(row.get("official_metric_input_rows")) > 0
    )


def row_has_promotion_evidence(row: Mapping[str, Any]) -> bool:
    return row.get("promotion_evidence") is True


def row_is_hidden_or_excluded(row: Mapping[str, Any]) -> bool:
    boolean_markers = (
        "hidden",
        "hidden_row",
        "hidden_negative",
        "hidden_content",
        "hidden_or_excluded",
        "excluded",
        "policy_excluded",
        "normalized_excluded",
        "pending_excluded",
    )
    if any(row.get(key) is True for key in boolean_markers):
        return True
    if row.get("no_policy_excluded_row_used") is False:
        return True
    text_markers = " ".join(
        clean(row.get(key)).lower()
        for key in ("status", "bucket", "label_status", "review_bucket", "exclusion_reason", "policy_status")
    )
    return any(marker in text_markers for marker in ("hidden", "excluded", "policy_blocked", "do_not_promote"))


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def clean(value: Any) -> str:
    return str(value or "").strip()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
