"""Create Track C C7 PDF gold-policy review artifacts.

This script is report-only. It consumes the C6 PDF vector failure breakdown,
cross-checks the C5 PDF-only diagnostic and gold CSV, and writes a query-level
gold-policy review report. It does not run retrieval, indexing, parser
expansion, threshold changes, or promotion.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER = SCRIPT_DIR.parent
ROOT = AI_WORKER.parent

PDF_INDEX_VERSION = "rag-ingestion-v2-pdf-candidate-v1"
PDF_ARTIFACT_DIR = "ai/eval/indexes/rag-data-pdf-candidate-v1"
DEFAULT_C6_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_vector_quality_breakdown.json")
DEFAULT_C5_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_pdf_vector_diagnostic_report.json")
DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_pdf_v0.csv")
DEFAULT_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_gold_policy_review.json")
DEFAULT_DECISIONS_TEMPLATE = Path(
    "eval/reports/rag-ingestion/rag_pdf_gold_policy_review_decisions_template.csv"
)

CLASSIFICATIONS = (
    "keep_as_positive_current_policy",
    "table_gold_policy_review_required",
    "page_only_evidence_policy_review_required",
    "bbox_policy_review_required",
    "parser_chunk_contract_fix_required",
    "query_surface_or_answerability_review_required",
    "diagnostic_only_exclude_candidate",
)
HUMAN_DECISION_CLASSIFICATIONS = {
    "table_gold_policy_review_required",
    "page_only_evidence_policy_review_required",
    "bbox_policy_review_required",
    "query_surface_or_answerability_review_required",
}
POLICY_CHANGE_CLASSIFICATIONS = {
    "table_gold_policy_review_required",
    "page_only_evidence_policy_review_required",
    "bbox_policy_review_required",
}
CODEX_DIAGNOSTIC_CLASSIFICATIONS = {
    "parser_chunk_contract_fix_required",
    "diagnostic_only_exclude_candidate",
}
GENERIC_QUERY_SURFACES = {
    "기간중",
    "목 차",
    "달러",
    "수입(CIF)",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    blockers: list[str] = []
    c6_path = resolve_existing_path(Path(args.c6_report))
    c5_path = resolve_existing_path(Path(args.c5_report))
    gold_path = resolve_existing_path(Path(args.gold))
    report_path = resolve_output_path(Path(args.report))
    decisions_template_path = (
        None if args.no_decisions_template else resolve_output_path(Path(args.decisions_template))
    )

    c6_report = read_json(c6_path, blockers, "c6_report")
    c5_report = read_json(c5_path, blockers, "c5_report")
    gold_rows = read_gold_rows(gold_path, blockers)
    payload, template_rows = build_review(
        c6_report=c6_report,
        c5_report=c5_report,
        gold_rows=gold_rows,
        c6_path=c6_path,
        c5_path=c5_path,
        gold_path=gold_path,
        decisions_template_path=decisions_template_path,
        blockers=blockers,
    )
    if decisions_template_path and template_rows:
        write_csv(decisions_template_path, template_rows)
        payload["decisions_template"].update({
            "written": True,
            "sha256": file_sha256(decisions_template_path),
        })
    write_json(report_path, payload)
    print_json(summary_for_stdout(payload, report_path))
    return 0 if payload.get("status") != "FAIL" else 2


def build_review(
    *,
    c6_report: Mapping[str, Any],
    c5_report: Mapping[str, Any],
    gold_rows: list[dict[str, str]],
    c6_path: Path,
    c5_path: Path,
    gold_path: Path,
    decisions_template_path: Path | None,
    blockers: list[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    blocker_list = list(blockers or [])
    warnings: list[str] = []
    validate_inputs(c6_report=c6_report, c5_report=c5_report, blocker_list=blocker_list)

    gold_by_id = {row.get("query_id", ""): row for row in gold_rows}
    c5_by_id = {str(row.get("query_id") or ""): row for row in c5_report.get("query_results") or []}
    all_c6_rows = list(c6_report.get("query_breakdown") or [])
    failed_rows = list(c6_report.get("classified_failed_query_rows") or [])
    if not failed_rows:
        failed_rows = [row for row in all_c6_rows if row.get("failure_type") != "MATCHED"]
    matched_rows = [row for row in all_c6_rows if row.get("failure_type") == "MATCHED"]

    review_rows = [
        review_failed_query(row, gold_by_id.get(str(row.get("query_id") or ""), {}), c5_by_id)
        for row in failed_rows
    ]
    positive_control_rows = [
        current_policy_positive_row(row, gold_by_id.get(str(row.get("query_id") or ""), {}))
        for row in matched_rows
    ]
    template_rows = [decision_template_row(row) for row in review_rows if row["human_decision_required"]]

    primary_counts = Counter(row["primary_c7_classification"] for row in review_rows)
    all_counts: Counter[str] = Counter()
    bucket_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in review_rows:
        classifications = [row["primary_c7_classification"]] + list(row["secondary_c7_classifications"])
        all_counts.update(classifications)
        bucket_counts[str(row.get("bucket") or "unknown")][row["primary_c7_classification"]] += 1
    for classification in CLASSIFICATIONS:
        primary_counts.setdefault(classification, 0)
        all_counts.setdefault(classification, 0)

    human_rows = [row for row in review_rows if row["human_decision_required"]]
    policy_rows = [row for row in review_rows if row["gold_policy_change_candidate"]]
    codex_rows = [row for row in review_rows if row["codex_diagnostic_only_candidate"]]
    parser_rows = [
        row
        for row in review_rows
        if "parser_chunk_contract_fix_required" in row["all_c7_classifications"]
    ]
    diagnostic_exclude_rows = [
        row
        for row in review_rows
        if "diagnostic_only_exclude_candidate" in row["all_c7_classifications"]
    ]

    if human_rows:
        warnings.append("C7 found rows that need human gold-policy, evidence-semantics, or answerability decisions.")
    if parser_rows:
        warnings.append("C7 found parser/chunk contract follow-up candidates; no parser expansion was performed.")
    if diagnostic_exclude_rows:
        warnings.append("C7 recommends keeping ambiguous failed rows diagnostic-only until reviewed.")

    status = "FAIL" if blocker_list else ("NEEDS_POLICY_DECISION" if human_rows else "PASS")
    decisions_template = {
        "path": display_path(decisions_template_path) if decisions_template_path else None,
        "written": False,
        "row_count": len(template_rows),
        "sha256": None,
        "purpose": (
            "Blank user-decision worksheet limited to gold policy, expected evidence semantics, "
            "and answerability/relevance labels."
        ),
    }
    immutable_baseline_changed = bool(c5_report.get("immutable_baseline_changed"))
    xlsx_candidate_artifact_changed = bool(c5_report.get("xlsx_candidate_artifact_changed"))

    return (
        {
            "run_id": utc_run_id(),
            "generated_at": utc_timestamp(),
            "status": status,
            "track": "C",
            "phase": "C7",
            "report_role": "pdf_gold_policy_review",
            "source_file_type": "PDF",
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "retrieval_backend": c6_report.get("retrieval_backend"),
            "namespace": c6_report.get("namespace"),
            "index_version": c6_report.get("index_version"),
            "artifact_dir": c6_report.get("artifact_dir") or PDF_ARTIFACT_DIR,
            "allowUnscoped": c5_report.get("allowUnscoped"),
            "retrieval_execution": "not_run_by_this_script",
            "indexing_execution": "not_run_by_this_script",
            "promotion_execution": "not_run_by_this_script",
            "promotion_evidence_created": False,
            "input_artifacts": [
                artifact_identity(c6_path),
                artifact_identity(c5_path),
                artifact_identity(gold_path),
            ],
            "c6_report": report_ref(c6_path, c6_report),
            "c5_report": report_ref(c5_path, c5_report),
            "gold": {
                "path": display_path(gold_path),
                "row_count": len(gold_rows),
            },
            "review_scope": {
                "source_c6_failed_query_count": c6_report.get("failed_query_count"),
                "failed_query_count": len(review_rows),
                "failed_query_ids": [row["query_id"] for row in review_rows],
                "matched_control_count": len(positive_control_rows),
                "matched_control_query_ids": [row["query_id"] for row in positive_control_rows],
                "gold_policy_candidate_query_ids_from_c6": list(
                    c6_report.get("gold_policy_candidate_query_ids") or []
                ),
                "parser_chunk_candidate_query_ids_from_c6": list(
                    c6_report.get("parser_chunk_contract_candidate_query_ids") or []
                ),
            },
            "classification_counts": dict(sorted(primary_counts.items())),
            "all_classification_counts": dict(sorted(all_counts.items())),
            "classification_query_ids": ids_by_primary_classification(review_rows),
            "all_classification_query_ids": ids_by_any_classification(review_rows),
            "bucket_classification_counts": {
                bucket: dict(sorted(counts.items()))
                for bucket, counts in sorted(bucket_counts.items())
            },
            "human_decision_required_count": len(human_rows),
            "human_decision_required_query_ids": [row["query_id"] for row in human_rows],
            "human_decision_scope": {
                "allowed_decision_topics": [
                    "gold_policy",
                    "expected_evidence_semantics",
                    "answerability_or_relevance_label",
                ],
                "excluded_topics": [
                    "retrieval_tuning",
                    "threshold_relaxation",
                    "broad_reindexing",
                    "parser_expansion",
                    "promotion_evidence",
                ],
            },
            "gold_policy_change_candidate_count": len(policy_rows),
            "gold_policy_change_candidate_query_ids": [row["query_id"] for row in policy_rows],
            "codex_diagnostic_only_candidate_count": len(codex_rows),
            "codex_diagnostic_only_candidate_query_ids": [row["query_id"] for row in codex_rows],
            "parser_chunk_contract_candidate_count": len(parser_rows),
            "parser_chunk_contract_candidate_query_ids": [row["query_id"] for row in parser_rows],
            "diagnostic_only_exclude_candidate_count": len(diagnostic_exclude_rows),
            "diagnostic_only_exclude_candidate_query_ids": [
                row["query_id"] for row in diagnostic_exclude_rows
            ],
            "invalid_gold_count": 0,
            "page_policy_ambiguous_count": all_counts["page_only_evidence_policy_review_required"],
            "table_policy_ambiguous_count": all_counts["table_gold_policy_review_required"],
            "bbox_policy_ambiguous_count": all_counts["bbox_policy_review_required"],
            "ocr_policy_ambiguous_count": 0,
            "relabel_candidate_count": len(human_rows),
            "relabel_candidate_rows_recorded": bool(template_rows),
            "decisions_template": decisions_template,
            "follow_up_c6_reclassification_plan": {
                "required": bool(policy_rows or human_rows),
                "old_c6_mutated": False,
                "action": (
                    "If the user approves policy, evidence-semantics, or answerability changes, "
                    "append a follow-up C6 reclassification entry and generate a new derivative "
                    "report. Do not edit the historical C6 report."
                ),
                "trigger_query_ids": [row["query_id"] for row in human_rows],
            },
            "gate_and_baseline_status": {
                "promotion_was_run": False,
                "retrieval_was_run_by_c7": False,
                "indexing_was_run_by_c7": False,
                "promotion_evidence": False,
                "evidence_role": "diagnostic",
                "namespace": c6_report.get("namespace"),
                "index_version": c6_report.get("index_version"),
                "immutable_baseline_changed": immutable_baseline_changed,
                "xlsx_candidate_artifact_changed": xlsx_candidate_artifact_changed,
                "rag_data_canary_changed": False,
            },
            "c7_review_rows": review_rows,
            "current_policy_positive_control_rows": positive_control_rows,
            "blockers": dedupe(blocker_list),
            "warnings": dedupe(warnings),
            "next_action": (
                "Collect user decisions from the C7 template before any gold policy change or "
                "follow-up C6 reclassification."
                if human_rows
                else "No C7 policy changes are required before the next diagnostic step."
            ),
            "notes": [
                "C7 is diagnostic-only and report-only.",
                "The source C6 report is immutable for this review; follow-up reclassification must be append-only.",
                "Rows marked diagnostic_only_exclude_candidate are not promotion evidence and do not change gold policy.",
            ],
        },
        template_rows,
    )


def review_failed_query(
    row: Mapping[str, Any],
    gold: Mapping[str, str],
    c5_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    query_id = str(row.get("query_id") or "")
    bucket = str(row.get("bucket") or "")
    query = str(row.get("query") or gold.get("query") or "")
    failure_type = str(row.get("failure_type") or "")
    expected = dict(row.get("expected") or {})
    expected_chunk_type = str(expected.get("chunk_type") or gold.get("expected_chunk_type") or "")
    c6_secondary = list(row.get("secondary_dispositions") or [])
    primary, secondary, reason_code = classify_c7(row, gold)
    all_classifications = dedupe([primary] + secondary)
    human_required = any(item in HUMAN_DECISION_CLASSIFICATIONS for item in all_classifications)
    policy_candidate = any(item in POLICY_CHANGE_CLASSIFICATIONS for item in all_classifications)
    diagnostic_only = (
        "diagnostic_only_exclude_candidate" in all_classifications
        or primary in CODEX_DIAGNOSTIC_CLASSIFICATIONS
        or human_required
    )
    c5_row = c5_by_id.get(query_id, {})
    supporting_hits = list(row.get("supporting_hits") or [])
    top_hits = list(row.get("top_hits") or [])
    top_supporting_hit = supporting_hits[0] if supporting_hits else (top_hits[0] if top_hits else {})

    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": query,
        "label_status": row.get("label_status") or gold.get("label_status"),
        "primary_c7_classification": primary,
        "secondary_c7_classifications": secondary,
        "all_c7_classifications": all_classifications,
        "reason_code": reason_code,
        "human_decision_required": human_required,
        "human_decision_topic": human_decision_topic(all_classifications),
        "gold_policy_change_candidate": policy_candidate,
        "codex_diagnostic_only_candidate": diagnostic_only,
        "recommended_current_action": (
            "keep_diagnostic_only_excluded_from_promotion_until_user_review"
            if diagnostic_only
            else "keep_current_positive_policy"
        ),
        "follow_up_c6_reclassification_needed_if_policy_changes": human_required,
        "c6_failure_type": failure_type,
        "c6_failure_types": list(row.get("failure_types") or []),
        "c6_primary_disposition": row.get("primary_disposition"),
        "c6_secondary_dispositions": c6_secondary,
        "c5_failure_reason": row.get("failure_reason") or c5_row.get("failure_reason"),
        "hit_rank": row.get("hit_rank"),
        "location_rank": row.get("location_rank"),
        "expected_evidence": expected_evidence(expected, gold, bucket),
        "observed_evidence": {
            "top_k_count": (row.get("evidence") or {}).get("top_k_count"),
            "file_hit_count": (row.get("evidence") or {}).get("file_hit_count"),
            "document_version_hit_count": (row.get("evidence") or {}).get("document_version_hit_count"),
            "expected_page_hit_count": (row.get("evidence") or {}).get("expected_page_hit_count"),
            "bbox_overlap_hit_count": (row.get("evidence") or {}).get("bbox_overlap_hit_count"),
            "first_expected_file_rank": (row.get("evidence") or {}).get("first_expected_file_rank"),
            "first_expected_docv_rank": (row.get("evidence") or {}).get("first_expected_docv_rank"),
            "first_expected_page_rank": (row.get("evidence") or {}).get("first_expected_page_rank"),
            "first_bbox_overlap_rank": (row.get("evidence") or {}).get("first_bbox_overlap_rank"),
            "page_hit_missing_bbox_ranks": (row.get("evidence") or {}).get("page_hit_missing_bbox_ranks") or [],
            "chunk_type_mismatch_ranks": (row.get("evidence") or {}).get("chunk_type_mismatch_ranks") or [],
            "location_match_without_identity_ranks": (
                (row.get("evidence") or {}).get("location_match_without_identity_ranks") or []
            ),
            "correct_page_wrong_chunk_type_count": (
                (row.get("evidence") or {}).get("correct_page_wrong_chunk_type_count") or 0
            ),
            "supporting_hit_ranks": (row.get("evidence") or {}).get("supporting_hit_ranks") or [],
        },
        "top_k_supporting_hit": summarize_supporting_hit(top_supporting_hit),
        "top_k_supporting_hits": [summarize_supporting_hit(hit) for hit in supporting_hits[:5]],
        "top_hits": [summarize_supporting_hit(hit) for hit in top_hits[:5]],
        "mismatch_reason": mismatch_reason(row, gold, expected_chunk_type),
        "c7_rationale": c7_rationale(primary, reason_code),
        "c6_rationale": row.get("rationale"),
        "c6_next_action": row.get("next_action"),
    }


def classify_c7(row: Mapping[str, Any], gold: Mapping[str, str]) -> tuple[str, list[str], str]:
    bucket = str(row.get("bucket") or "")
    query = str(row.get("query") or gold.get("query") or "").strip()
    failure_type = str(row.get("failure_type") or "")
    expected = row.get("expected") or {}
    expected_chunk_type = str(expected.get("chunk_type") or gold.get("expected_chunk_type") or "")
    c6_primary = str(row.get("primary_disposition") or "")
    c6_secondary = list(row.get("secondary_dispositions") or [])
    evidence = row.get("evidence") or {}
    secondary: list[str] = []
    low_signal = is_low_signal_query(query, gold)

    if bucket == "pdf_table_lookup":
        primary = "table_gold_policy_review_required"
        reason = "pdf_table_row_has_no_table_id_or_table_like_hit_contract"
        if c6_primary == "parser_chunk_contract":
            secondary.append("parser_chunk_contract_fix_required")
        if low_signal:
            secondary.append("query_surface_or_answerability_review_required")
    elif failure_type == "PDF_BBOX_POLICY_MISMATCH":
        primary = "bbox_policy_review_required"
        reason = "expected_page_hit_exists_without_bbox_overlap_or_paragraph_identity"
        if evidence.get("page_hit_missing_bbox_ranks") or evidence.get("chunk_type_mismatch_ranks"):
            secondary.extend([
                "page_only_evidence_policy_review_required",
                "parser_chunk_contract_fix_required",
            ])
    elif expected_chunk_type == "page" and failure_type == "PDF_CHUNK_GRANULARITY_ISSUE":
        primary = "page_only_evidence_policy_review_required"
        reason = "page_level_gold_matches_only_paragraph_chunks_in_top_k"
        secondary.append("parser_chunk_contract_fix_required")
    elif low_signal:
        primary = "query_surface_or_answerability_review_required"
        reason = "query_surface_too_generic_or_auto_bound_for_strict_pdf_location_gold"
        if expected_chunk_type == "page":
            secondary.append("page_only_evidence_policy_review_required")
    elif c6_primary == "parser_chunk_contract" or "parser_chunk_contract" in c6_secondary:
        primary = "parser_chunk_contract_fix_required"
        reason = "parser_chunk_contract_follow_up_without_user_policy_change"
    else:
        primary = "diagnostic_only_exclude_candidate"
        reason = "not_safe_for_gold_denominator_from_current_diagnostic_evidence"

    if primary != "keep_as_positive_current_policy":
        secondary.append("diagnostic_only_exclude_candidate")
    return primary, [item for item in dedupe(secondary) if item != primary], reason


def is_low_signal_query(query: str, gold: Mapping[str, str]) -> bool:
    normalized = " ".join(query.split())
    if normalized in GENERIC_QUERY_SURFACES:
        return True
    if any(char.isdigit() for char in normalized) and all(
        char.isdigit() or char in " .,%-" for char in normalized
    ):
        return True
    notes = str(gold.get("notes") or "").lower()
    return "auto-bound seed" in notes


def expected_evidence(expected: Mapping[str, Any], gold: Mapping[str, str], bucket: str) -> dict[str, Any]:
    return {
        "file_name": expected.get("file_name") or gold.get("expected_file_name"),
        "document_version_id": expected.get("document_version_id") or gold.get("expected_document_version_id"),
        "chunk_type": expected.get("chunk_type") or gold.get("expected_chunk_type"),
        "location_type": expected.get("location_type") or gold.get("expected_location_type"),
        "physical_page_index": expected.get("physical_page_index") or gold.get("expected_physical_page_index"),
        "page_no": expected.get("page_no") or gold.get("expected_page_no"),
        "page_label": expected.get("page_label") or gold.get("expected_page_label"),
        "bbox": expected.get("bbox") or gold.get("expected_bbox"),
        "expected_answer_text": gold.get("expected_answer_text"),
        "must_contain_terms": gold.get("must_contain_terms"),
        "table": {
            "bucket_is_pdf_table_lookup": bucket == "pdf_table_lookup",
            "expected_table_id": gold.get("expected_table_id"),
            "current_pdf_table_binding": (
                "PDF table-like rows currently bind to PDF page/bbox evidence; expected_table_id is empty."
                if bucket == "pdf_table_lookup" and not gold.get("expected_table_id")
                else None
            ),
        },
    }


def summarize_supporting_hit(hit: Mapping[str, Any]) -> dict[str, Any]:
    br = hit.get("match_breakdown") if isinstance(hit.get("match_breakdown"), Mapping) else {}
    return {
        "rank": hit.get("rank"),
        "search_unit_id": hit.get("search_unit_id"),
        "score": hit.get("score"),
        "source_file_name": hit.get("source_file_name"),
        "source_file_type": hit.get("source_file_type"),
        "chunk_type": hit.get("chunk_type"),
        "page_no": hit.get("page_no"),
        "physical_page_index": hit.get("physical_page_index"),
        "bbox_present": hit.get("bbox_present"),
        "citation_text": hit.get("citation_text"),
        "match_breakdown": {
            key: br.get(key)
            for key in (
                "identity_match",
                "location_match",
                "file_match",
                "document_version_match",
                "chunk_type_match",
                "location_type_match",
                "pdf_page_match",
                "pdf_bbox_overlap",
                "pdf_exact_bbox",
                "indexing_contract_match",
                "required_index_version_match",
                "embedding_status_match",
            )
        },
    }


def mismatch_reason(row: Mapping[str, Any], gold: Mapping[str, str], expected_chunk_type: str) -> str:
    evidence = row.get("evidence") or {}
    parts = [
        f"c6_failure_type={row.get('failure_type')}",
        f"c5_failure_reason={row.get('failure_reason')}",
        f"expected_file_rank={evidence.get('first_expected_file_rank')}",
        f"expected_page_rank={evidence.get('first_expected_page_rank')}",
        f"bbox_overlap_rank={evidence.get('first_bbox_overlap_rank')}",
    ]
    if expected_chunk_type:
        parts.append(f"expected_chunk_type={expected_chunk_type}")
    if gold.get("expected_table_id") is not None:
        parts.append(f"expected_table_id={gold.get('expected_table_id') or '<empty>'}")
    if row.get("rationale"):
        parts.append(str(row.get("rationale")))
    return "; ".join(parts)


def c7_rationale(primary: str, reason_code: str) -> str:
    if primary == "table_gold_policy_review_required":
        return "A table-like PDF query is bound to page/bbox evidence, but the current candidate index has no table-like PDF SearchUnit contract for it."
    if primary == "bbox_policy_review_required":
        return "The expected PDF page appears only without the required paragraph/bbox match, so bbox acceptance semantics must be settled first."
    if primary == "page_only_evidence_policy_review_required":
        return "The expected evidence is page-level, while top-k evidence is paragraph-level on the page; this is an expected-evidence semantics question before it is a ranking issue."
    if primary == "query_surface_or_answerability_review_required":
        return "The query surface is too broad, duplicated, numeric-only, or auto-bound for strict page/bbox gold interpretation without human answerability review."
    if primary == "parser_chunk_contract_fix_required":
        return "The row can stay diagnostic-only while Codex records a parser/chunk contract follow-up; no gold policy mutation is implied."
    if primary == "diagnostic_only_exclude_candidate":
        return "The row is not safe for official denominator use from current diagnostic evidence."
    return reason_code


def human_decision_topic(classifications: list[str]) -> str | None:
    topics: list[str] = []
    if "table_gold_policy_review_required" in classifications:
        topics.append("gold_policy")
    if "bbox_policy_review_required" in classifications or "page_only_evidence_policy_review_required" in classifications:
        topics.append("expected_evidence_semantics")
    if "query_surface_or_answerability_review_required" in classifications:
        topics.append("answerability_or_relevance_label")
    return "|".join(dedupe(topics)) if topics else None


def current_policy_positive_row(row: Mapping[str, Any], gold: Mapping[str, str]) -> dict[str, Any]:
    return {
        "query_id": row.get("query_id"),
        "bucket": row.get("bucket"),
        "query": row.get("query") or gold.get("query"),
        "primary_c7_classification": "keep_as_positive_current_policy",
        "human_decision_required": False,
        "expected_evidence": expected_evidence(row.get("expected") or {}, gold, str(row.get("bucket") or "")),
        "supporting_hit_ranks": (row.get("evidence") or {}).get("supporting_hit_ranks") or [],
        "rationale": "C6 already classified this query as MATCHED under the current diagnostic policy.",
    }


def decision_template_row(row: Mapping[str, Any]) -> dict[str, Any]:
    hit = row.get("top_k_supporting_hit") or {}
    expected = row.get("expected_evidence") or {}
    table = expected.get("table") or {}
    return {
        "query_id": row.get("query_id"),
        "bucket": row.get("bucket"),
        "query": row.get("query"),
        "current_c7_classification": row.get("primary_c7_classification"),
        "secondary_c7_classifications": "|".join(row.get("secondary_c7_classifications") or []),
        "human_decision_topic": row.get("human_decision_topic"),
        "allowed_user_decision_scope": "gold_policy|expected_evidence_semantics|answerability_or_relevance_label",
        "user_gold_policy_decision": "",
        "user_expected_evidence_semantics_decision": "",
        "user_answerability_relevance_decision": "",
        "user_notes": "",
        "expected_file_name": expected.get("file_name"),
        "expected_document_version_id": expected.get("document_version_id"),
        "expected_page_no": expected.get("page_no"),
        "expected_physical_page_index": expected.get("physical_page_index"),
        "expected_page_label": expected.get("page_label"),
        "expected_bbox": expected.get("bbox"),
        "expected_table_id": table.get("expected_table_id"),
        "expected_answer_text": expected.get("expected_answer_text"),
        "must_contain_terms": expected.get("must_contain_terms"),
        "top_supporting_hit_rank": hit.get("rank"),
        "top_supporting_hit_file": hit.get("source_file_name"),
        "top_supporting_hit_page_no": hit.get("page_no"),
        "top_supporting_hit_chunk_type": hit.get("chunk_type"),
        "top_supporting_hit_citation": hit.get("citation_text"),
        "mismatch_reason": row.get("mismatch_reason"),
        "follow_up_c6_reclassification_needed_if_policy_changes": (
            "true" if row.get("follow_up_c6_reclassification_needed_if_policy_changes") else "false"
        ),
    }


def validate_inputs(
    *,
    c6_report: Mapping[str, Any],
    c5_report: Mapping[str, Any],
    blocker_list: list[str],
) -> None:
    if c6_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blocker_list.append(f"C6 report must pass before C7; got {c6_report.get('status')}")
    if c6_report.get("phase") != "C6":
        blocker_list.append("C7 input must be the C6 failure breakdown")
    if c6_report.get("promotion_evidence") is not False:
        blocker_list.append("C6 report must keep promotion_evidence=false")
    if c6_report.get("evidence_role") != "diagnostic":
        blocker_list.append("C6 report must keep evidence_role=diagnostic")
    if c6_report.get("namespace") != PDF_INDEX_VERSION:
        blocker_list.append("C6 namespace must remain the PDF candidate namespace")
    if c6_report.get("index_version") != PDF_INDEX_VERSION:
        blocker_list.append("C6 index_version must remain the PDF candidate namespace")
    if c6_report.get("c7_ready") is not True:
        blocker_list.append("C6 report must mark c7_ready=true before C7")
    if int(c6_report.get("unknown_failure_count") or 0) != 0:
        blocker_list.append("C6 unknown_failure_count must be 0 before C7")
    if c5_report.get("promotion_evidence") is not False:
        blocker_list.append("C5 report must keep promotion_evidence=false")
    if c5_report.get("evidence_role") != "diagnostic":
        blocker_list.append("C5 report must keep evidence_role=diagnostic")
    if c5_report.get("namespace") != PDF_INDEX_VERSION:
        blocker_list.append("C5 namespace must remain the PDF candidate namespace")
    if c5_report.get("allowUnscoped") is not False:
        blocker_list.append("C5 allowUnscoped must be false for Track C C7")
    if bool(c5_report.get("immutable_baseline_changed")):
        blocker_list.append("immutable baseline must not change before C7")
    if bool(c5_report.get("xlsx_candidate_artifact_changed")):
        blocker_list.append("XLSX candidate artifact must not change before C7")


def ids_by_primary_classification(rows: list[Mapping[str, Any]]) -> dict[str, list[str]]:
    result = {classification: [] for classification in CLASSIFICATIONS}
    for row in rows:
        result.setdefault(str(row.get("primary_c7_classification") or ""), []).append(str(row.get("query_id") or ""))
    return {key: value for key, value in result.items()}


def ids_by_any_classification(rows: list[Mapping[str, Any]]) -> dict[str, list[str]]:
    result = {classification: [] for classification in CLASSIFICATIONS}
    for row in rows:
        for classification in row.get("all_c7_classifications") or []:
            result.setdefault(str(classification), []).append(str(row.get("query_id") or ""))
    return {key: dedupe(value) for key, value in result.items()}


def read_json(path: Path, blockers: list[str], label: str) -> dict[str, Any]:
    if not path.exists():
        blockers.append(f"{label} missing: {display_path(path)}")
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        blockers.append(f"{label} must be a JSON object: {display_path(path)}")
        return {}
    return payload


def read_gold_rows(path: Path, blockers: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        blockers.append(f"gold CSV missing: {display_path(path)}")
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def summary_for_stdout(payload: Mapping[str, Any], output_path: Path) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "report": display_path(output_path),
        "failed_query_count": (payload.get("review_scope") or {}).get("failed_query_count"),
        "classification_counts": payload.get("classification_counts"),
        "human_decision_required_count": payload.get("human_decision_required_count"),
        "gold_policy_change_candidate_count": payload.get("gold_policy_change_candidate_count"),
        "codex_diagnostic_only_candidate_count": payload.get("codex_diagnostic_only_candidate_count"),
        "decisions_template": payload.get("decisions_template"),
        "blockers": payload.get("blockers"),
    }


def report_ref(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": display_path(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() and path.is_file() else None,
        "status": payload.get("status"),
        "promotion_evidence": payload.get("promotion_evidence"),
        "evidence_role": payload.get("evidence_role"),
    }


def artifact_identity(path: Path) -> dict[str, Any]:
    return {
        "path": display_path(path),
        "exists": path.exists(),
        "sha256": file_sha256(path) if path.exists() and path.is_file() else None,
    }


def resolve_existing_path(path: Path) -> Path:
    candidates = candidate_paths(path)
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def resolve_output_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0] == "eval":
        return (AI_WORKER / path).resolve()
    if parts and parts[0] == "ai":
        return (ROOT / path).resolve()
    return (Path.cwd() / path).resolve()


def candidate_paths(path: Path) -> list[Path]:
    if path.is_absolute():
        return [path]
    paths: list[Path] = []
    parts = path.parts
    if parts and parts[0] == "eval":
        paths.append(AI_WORKER / path)
    if parts and parts[0] == "ai":
        paths.append(ROOT / path)
    paths.extend([Path.cwd() / path, AI_WORKER / path, ROOT / path])
    result: list[Path] = []
    for candidate in paths:
        if candidate not in result:
            result.append(candidate)
    return result


def display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c6-report", default=str(DEFAULT_C6_REPORT))
    parser.add_argument("--c5-report", default=str(DEFAULT_C5_REPORT))
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--report", "--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--decisions-template", default=str(DEFAULT_DECISIONS_TEMPLATE))
    parser.add_argument("--no-decisions-template", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
