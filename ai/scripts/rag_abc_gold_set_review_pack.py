"""Create the A/B/C gold-set user review pack.

The pack is diagnostic-only. It reads current gold/report artifacts, preserves
existing gold CSVs and historical reports, and emits only review artifacts under
``ai/eval/review/gold_set_review``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent

REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
EVAL_QUERY_DIR = AI_WORKER_ROOT / "eval" / "eval_queries"
LEGACY_LINEAGE_ARCHIVE_DIR = (
    REPO_ROOT / "archive" / "results" / "2026-05-05-eval-query-lineage-cleanup" / "csv"
)
EXTERNAL_LEGACY_LINEAGE_ARCHIVE_DIR = Path(
    "D:/_external_workspace_archive/async-ocr-rag-multimodal-pipeline/"
    "20260519-repo-wide-cleanup/files/archive/results/2026-05-05-eval-query-lineage-cleanup/csv"
)
ARCHIVE_XLSX_CSV_DIR = (
    LEGACY_LINEAGE_ARCHIVE_DIR
    if LEGACY_LINEAGE_ARCHIVE_DIR.exists()
    else EXTERNAL_LEGACY_LINEAGE_ARCHIVE_DIR
)
REMOVED_ACTIVE_LEGACY_DATASET_PATHS = [
    EVAL_QUERY_DIR / "gold_queries_v0.csv",
    EVAL_QUERY_DIR / "gold_queries_xlsx_v1.csv",
    EVAL_QUERY_DIR / "gold_queries_xlsx_v2.csv",
    EVAL_QUERY_DIR / "gold_queries_xlsx_v3_naturalized.csv",
    EVAL_QUERY_DIR / "gold_queries_xlsx_v3_positive.csv",
]

DEFAULT_OUTPUT_DIR = AI_WORKER_ROOT / "eval" / "review" / "gold_set_review"

DEFAULT_INPUTS = {
    "xlsx_positive_reviewed": EVAL_QUERY_DIR / "gold_queries_xlsx_v3_positive_reviewed.csv",
    "xlsx_naturalized_archive": ARCHIVE_XLSX_CSV_DIR / "gold_queries_xlsx_v3_naturalized.csv",
    "xlsx_v2_archive": ARCHIVE_XLSX_CSV_DIR / "gold_queries_xlsx_v2.csv",
    "xlsx_metric_compare": REPORT_DIR / "rag_xlsx_v3_after_cleanup_metric_compare.json",
    "xlsx_failure_breakdown": REPORT_DIR / "rag_xlsx_v3_after_cleanup_failure_breakdown.json",
    "xlsx_hidden_negative_leakage": REPORT_DIR
    / "rag_xlsx_v3_positive_reviewed_hidden_negative_leakage_diagnostic.json",
    "xlsx_review_decisions": REPORT_DIR / "rag_xlsx_query_evidence_review_decisions.json",
    "xlsx_natural_query_quality": REPORT_DIR / "rag_xlsx_natural_query_quality_audit.json",
    "text_gold": EVAL_QUERY_DIR / "gold_queries_text_namu_v4_v0.csv",
    "text_gold_validate": REPORT_DIR / "rag_text_namu_v4_gold_validate_report.json",
    "text_retrieval_report": REPORT_DIR / "rag_text_namu_v4_retrieval_diagnostic_report.json",
    "text_context_report": REPORT_DIR / "rag_text_namu_v4_context_assembly_report.json",
    "text_context_jsonl": REPORT_DIR / "rag_text_namu_v4_context_assembly.jsonl",
    "text_answer_report": REPORT_DIR / "rag_text_namu_v4_answer_eval_report.json",
    "text_answer_jsonl": REPORT_DIR / "rag_text_namu_v4_answer_eval.jsonl",
    "text_citation_report": REPORT_DIR / "rag_text_namu_v4_citation_support_report.json",
    "text_citation_jsonl": REPORT_DIR / "rag_text_namu_v4_citation_support.jsonl",
    "pdf_gold": EVAL_QUERY_DIR / "gold_queries_pdf_v1_review_draft.csv",
    "pdf_gold_v0_reference": EVAL_QUERY_DIR / "gold_queries_pdf_v0.csv",
    "pdf_vector_diagnostic": REPORT_DIR / "rag_retrieval_eval_pdf_vector_diagnostic_report.json",
    "pdf_vector_quality": REPORT_DIR / "rag_pdf_vector_quality_breakdown.json",
    "pdf_policy_review": REPORT_DIR / "rag_pdf_gold_policy_review.json",
    "pdf_policy_decisions_template": REPORT_DIR
    / "rag_pdf_gold_policy_review_decisions_template.csv",
    "pdf_c7_decision_pack": REPORT_DIR / "rag_pdf_c7_decision_pack.csv",
    "pdf_c7_decision_pack_summary": REPORT_DIR / "rag_pdf_c7_decision_pack_summary.json",
    "r9_lane_readiness": REPORT_DIR / "rag_file_content_lane_readiness_report.json",
}

DECISION_COLUMNS = [
    "user_gold_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_evidence_policy",
    "user_denominator_policy",
    "user_issue_tags",
    "user_notes",
]
SUGGESTED_COLUMNS = [
    "suggested_gold_decision",
    "suggested_answerability_label",
    "suggested_relevance_label",
    "suggested_expected_evidence_policy",
    "suggested_denominator_policy",
    "suggested_issue_tags",
    "suggested_notes",
]
USER_GOLD_DECISION_OPTIONS = [
    "KEEP_POSITIVE",
    "REVISE_QUERY",
    "REVISE_EXPECTED_EVIDENCE",
    "RELABEL_NEEDS_REVIEW",
    "RELABEL_NEGATIVE",
    "DEFER",
    "DIAGNOSTIC_ONLY_EXCLUDE",
    "REQUIRE_PARSER_OR_CHUNK_FIX",
]
USER_ANSWERABILITY_OPTIONS = [
    "ANSWERABLE",
    "PARTIALLY_ANSWERABLE",
    "NOT_ANSWERABLE",
    "UNCLEAR",
]
USER_RELEVANCE_OPTIONS = ["RELEVANT", "PARTIAL", "IRRELEVANT", "UNCLEAR"]
USER_EXPECTED_EVIDENCE_POLICY_OPTIONS = [
    "KEEP_CURRENT_EVIDENCE",
    "REVISE_EXPECTED_EVIDENCE",
    "ALLOW_PAGE_ONLY_EVIDENCE",
    "REQUIRE_BBOX_OVERLAP",
    "REQUIRE_TABLE_LIKE_EVIDENCE",
    "ALLOW_PARAGRAPH_BACKED_TABLE_EVIDENCE",
    "DEFER",
    "UNCLEAR",
]
USER_DENOMINATOR_POLICY_OPTIONS = [
    "INCLUDE_POSITIVE_DENOMINATOR",
    "INCLUDE_POSITIVE_EXCLUDE_CITATION_DENOMINATOR",
    "EXCLUDE_POSITIVE_DENOMINATOR",
    "DIAGNOSTIC_ONLY",
    "BLOCKED_GOLD_POLICY",
    "DEFER",
]
USER_ISSUE_TAG_OPTIONS = [
    "ANSWERABILITY",
    "BBOX_POLICY",
    "CITATION_DENOMINATOR_EXCLUDED",
    "DENOMINATOR_POLICY",
    "EXPECTED_EVIDENCE",
    "FORMULA_DATE_CONTRACT",
    "HIDDEN_NEGATIVE_POLICY",
    "LOCATION_RANK_WATCH",
    "MUST_CONTAIN_STRICTNESS",
    "NEEDS_REVIEW",
    "PAGE_ONLY_POLICY",
    "PARSER_CHUNK_CONTRACT",
    "PDF_C7_POLICY_PENDING",
    "QUERY_SURFACE",
    "RANGE_POLICY",
    "RELEVANCE",
    "RETRIEVAL_CONTEXT_MISS",
    "TABLE_POLICY",
]

REVIEW_FIELDNAMES = [
    "track",
    "query_id",
    "review_group",
    "bucket",
    "query",
    "expected_answer_text",
    "must_contain_terms",
    "expected_document_version_id",
    "expected_file_name",
    "expected_page_no",
    "expected_physical_page_index",
    "expected_page_label",
    "expected_section_id",
    "expected_chunk_id",
    "expected_sheet_name",
    "expected_cell_range",
    "expected_table_id",
    "expected_bbox",
    *SUGGESTED_COLUMNS,
    *DECISION_COLUMNS,
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run_review_pack(output_dir=Path(args.output_dir))
    print(
        json.dumps(
            {
                "status": summary["status"],
                "output_dir": repo_relative(Path(args.output_dir)),
                "xlsx_review_row_count": summary["xlsx_review_row_count"],
                "text_review_row_count": summary["text_review_row_count"],
                "pdf_review_row_count": summary["pdf_review_row_count"],
                "promotion_evidence": summary["promotion_evidence"],
                "evidence_role": summary["evidence_role"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args(argv)


def run_review_pack(
    *,
    output_dir: Path,
    inputs: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    input_paths = dict(DEFAULT_INPUTS)
    if inputs:
        input_paths.update(inputs)

    generated_at = utc_timestamp()
    source_inventory = build_source_inventory(input_paths)

    xlsx_records = build_xlsx_records(input_paths)
    text_records = build_text_records(input_paths)
    pdf_records = build_pdf_records(input_paths)
    all_records = xlsx_records + text_records + pdf_records

    output_dir.mkdir(parents=True, exist_ok=True)
    xlsx_csv = output_dir / "xlsx_gold_review_pack.csv"
    text_csv = output_dir / "text_gold_review_pack.csv"
    pdf_csv = output_dir / "pdf_gold_review_pack.csv"
    inventory_json = output_dir / "a_b_c_gold_review_inventory.json"
    summary_json = output_dir / "a_b_c_gold_review_summary.json"
    guide_md = output_dir / "a_b_c_gold_review_pack.md"

    write_review_csv(xlsx_csv, xlsx_records)
    write_review_csv(text_csv, text_records)
    write_review_csv(pdf_csv, pdf_records)

    track_counts = dict(Counter(record["track"] for record in all_records))
    review_group_counts = count_review_group_tags(all_records)
    user_decision_required_count = sum(
        1 for record in all_records if record["user_decision_required"] == "true"
    )

    inventory = {
        "status": "NEEDS_USER_REVIEW",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "generated_at": generated_at,
        "codex_gold_decision_applied": False,
        "gold_csv_modified": False,
        "historical_reports_modified": False,
        "official_denominator_changed": False,
        "source_inventory": source_inventory,
        "candidate_inventory": build_candidate_inventory(
            xlsx_records=xlsx_records,
            text_records=text_records,
            pdf_records=pdf_records,
            inputs=input_paths,
        ),
        "records_by_track": {
            "XLSX": xlsx_records,
            "TEXT": text_records,
            "PDF": pdf_records,
        },
        "review_pack_paths": {
            "xlsx": repo_relative(xlsx_csv),
            "text": repo_relative(text_csv),
            "pdf": repo_relative(pdf_csv),
            "summary": repo_relative(summary_json),
            "guide": repo_relative(guide_md),
        },
    }

    summary = {
        "status": "NEEDS_USER_REVIEW",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "generated_at": generated_at,
        "codex_gold_decision_applied": False,
        "historical_reports_modified": False,
        "gold_csv_modified": False,
        "official_denominator_changed": False,
        "xlsx_review_row_count": len(xlsx_records),
        "text_review_row_count": len(text_records),
        "pdf_review_row_count": len(pdf_records),
        "user_decision_required_count": user_decision_required_count,
        "track_counts": track_counts,
        "review_group_counts": review_group_counts,
        "blocked_next_steps_until_user_review": [
            "pdf_c7_user_decision_apply",
            "pdf_c6_followup_reclassification",
            "text_r8_citation_support",
            "abc_baseline_snapshot_refresh",
        ],
        "decision_columns": DECISION_COLUMNS,
        "suggested_columns": SUGGESTED_COLUMNS,
        "labeling_csv_columns": REVIEW_FIELDNAMES,
        "labeling_csv_role": "minimal_user_labeling_sheet",
        "blank_user_decision_policy": "FAIL_CLOSED",
        "user_gold_decision_cardinality": "single_enum",
        "user_issue_tags_cardinality": "semicolon_multi_enum",
        "user_gold_decision_options": USER_GOLD_DECISION_OPTIONS,
        "user_answerability_label_options": USER_ANSWERABILITY_OPTIONS,
        "user_relevance_label_options": USER_RELEVANCE_OPTIONS,
        "user_expected_evidence_policy_options": USER_EXPECTED_EVIDENCE_POLICY_OPTIONS,
        "user_denominator_policy_options": USER_DENOMINATOR_POLICY_OPTIONS,
        "user_issue_tag_options": USER_ISSUE_TAG_OPTIONS,
        "guardrails": {
            "promotion_execution": False,
            "promotion_evidence_true_generated": False,
            "live_llm_call": False,
            "optional_judge_call": False,
            "retrieval_tuning": False,
            "reranking": False,
            "parser_expansion": False,
            "threshold_relaxation": False,
            "broad_indexing": False,
            "db_mutation": False,
            "searchunit_mutation": False,
            "immutable_baseline_changed": False,
            "candidate_artifact_changed": False,
            "rag_data_canary_changed": False,
        },
        "source_integrity": source_inventory,
        "output_paths": {
            "inventory": repo_relative(inventory_json),
            "summary": repo_relative(summary_json),
            "xlsx_csv": repo_relative(xlsx_csv),
            "text_csv": repo_relative(text_csv),
            "pdf_csv": repo_relative(pdf_csv),
            "guide": repo_relative(guide_md),
        },
    }

    write_json(inventory_json, inventory)
    write_json(summary_json, summary)
    write_guide(guide_md, summary, inventory)
    return summary


def build_xlsx_records(inputs: Mapping[str, Path]) -> list[dict[str, str]]:
    reviewed_path = inputs["xlsx_positive_reviewed"]
    active_rows = read_csv_if_exists(reviewed_path)
    decision_rows = read_decision_rows(inputs["xlsx_review_decisions"])
    decision_by_id = {row.get("query_id", ""): row for row in decision_rows}
    unresolved_decisions = [
        row for row in decision_rows if row.get("decision") != "KEEP_AS_POSITIVE"
    ]
    unresolved_source_path = first_existing(
        inputs["xlsx_naturalized_archive"],
        inputs["xlsx_v2_archive"],
    )
    unresolved_rows_by_id = {
        row.get("query_id", ""): row for row in read_csv_if_exists(unresolved_source_path)
    }
    hidden_diag_by_id = {
        row.get("query_id", ""): row
        for row in (read_json_if_exists(inputs["xlsx_hidden_negative_leakage"]).get("query_results") or [])
    }

    records: list[dict[str, str]] = []
    for row in active_rows:
        query_id = row.get("query_id", "")
        decision = decision_by_id.get(query_id, {})
        records.append(
            xlsx_record(
                row=row,
                source_path=reviewed_path,
                source_origin="active_reviewed_positive_gold",
                decision=decision,
                hidden_diag=hidden_diag_by_id.get(query_id, {}),
            )
        )

    active_ids = {row.get("query_id", "") for row in active_rows}
    for decision in unresolved_decisions:
        query_id = decision.get("query_id", "")
        if query_id in active_ids:
            continue
        row = unresolved_rows_by_id.get(query_id) or flatten_decision_gold_fields(decision)
        records.append(
            xlsx_record(
                row=row,
                source_path=unresolved_source_path,
                source_origin="archive_lineage_or_current_unresolved_candidate",
                decision=decision,
                hidden_diag=hidden_diag_by_id.get(query_id, {}),
            )
        )

    return records


def xlsx_record(
    *,
    row: Mapping[str, Any],
    source_path: Path,
    source_origin: str,
    decision: Mapping[str, Any],
    hidden_diag: Mapping[str, Any],
) -> dict[str, str]:
    decision_name = text_cell(decision.get("decision") or row.get("review_decision"))
    category = text_cell(decision.get("category") or row.get("review_category"))
    primary_group = xlsx_primary_group(decision_name, category)
    tags = xlsx_group_tags(row=row, decision=decision, primary_group=primary_group)
    promotion_eligible = bool_text(row.get("promotion_eval_eligible") or decision.get("promotion_eval_eligible"))
    eval_status = decision_name or row.get("review_decision") or "reviewed_positive"
    failure_type = first_non_empty(
        decision.get("reason_code"),
        decision.get("failure_reason"),
        row.get("review_reason_code"),
        category,
    )
    if hidden_diag:
        failure_type = first_non_empty(failure_type, hidden_diag.get("failure_reason"), "hidden_negative_policy_watch")

    if decision_name == "KEEP_AS_POSITIVE":
        gold_status = "reviewed_positive_current"
        denominator_policy = (
            "diagnostic reviewed positive; XLSX positive denominator remains 35; "
            "promotion-grade baseline compatibility is still a separate blocker"
        )
    else:
        gold_status = "archived_or_review_overlay_unresolved_candidate"
        denominator_policy = (
            "excluded from positive retrieval denominator until the user decides "
            "gold inclusion, evidence policy, or hidden-negative handling"
        )

    return base_record(
        track="XLSX",
        query_id=row.get("query_id"),
        source_gold_file=source_path,
        source_record_origin=source_origin,
        bucket=row.get("bucket") or decision.get("bucket"),
        query=row.get("query") or decision.get("query"),
        label_status=row.get("label_status") or (decision.get("gold_fields") or {}).get("label_status"),
        current_gold_status=gold_status,
        expected_answer_text=row.get("expected_answer_text"),
        must_contain_terms=row.get("must_contain_terms"),
        expected_document_version_id=row.get("expected_document_version_id"),
        expected_file_name=row.get("expected_file_name"),
        expected_range=row.get("expected_cell_range"),
        expected_sheet_name=row.get("expected_sheet_name"),
        expected_cell_range=row.get("expected_cell_range"),
        expected_table_id=row.get("expected_table_id"),
        expected_page_no=row.get("expected_page_no"),
        expected_physical_page_index=row.get("expected_physical_page_index"),
        expected_page_label=row.get("expected_page_label"),
        expected_bbox=row.get("expected_bbox"),
        current_eval_status=eval_status,
        current_failure_or_warning_type=failure_type,
        current_denominator_policy=denominator_policy,
        current_recommended_codex_bucket=primary_group,
        review_group=primary_group,
        review_group_tags=tags,
        notes_for_reviewer=xlsx_notes(
            row=row,
            decision=decision,
            promotion_eligible=promotion_eligible,
            hidden_diag=hidden_diag,
        ),
    )


def build_text_records(inputs: Mapping[str, Path]) -> list[dict[str, str]]:
    gold_path = inputs["text_gold"]
    gold_rows = read_csv_if_exists(gold_path)
    answer_by_id = index_jsonl(inputs["text_answer_jsonl"])
    context_by_id = index_jsonl(inputs["text_context_jsonl"])
    citation_by_id = index_jsonl(inputs["text_citation_jsonl"])

    records = []
    for row in gold_rows:
        query_id = row.get("query_id", "")
        answer = answer_by_id.get(query_id, {})
        context = context_by_id.get(query_id, {})
        citation = citation_by_id.get(query_id, {})
        primary_stage = text_cell(answer.get("primary_stage"))
        label_status = text_cell(row.get("label_status"))
        if label_status == "needs_review":
            primary_group = "needs_review_3"
            denominator_policy = "excluded from TEXT positive denominator until user review"
            current_gold_status = "needs_review_current"
        elif answer.get("answerable_from_context") is True or primary_stage == "answerable_from_context":
            primary_group = "positive_answerable_from_context_29"
            denominator_policy = (
                "included in R7 answerable-from-context denominator and R8 citation "
                "support denominator; diagnostic-only until user review"
            )
            current_gold_status = "positive_bound_answerable_from_context"
        else:
            primary_group = "retrieval_context_miss_18"
            denominator_policy = (
                "excluded from R8 citation support denominator because R7 classified "
                "retrieval/context miss; do not count as citation failure"
            )
            current_gold_status = "positive_bound_retrieval_context_miss"

        tags = [primary_group, "expected_answer_or_evidence_review"]
        if row.get("must_contain_terms"):
            tags.append("must_contain_terms_strictness_review")

        expected_surface = answer.get("expected_evidence_surface") or {}
        failure_type = first_non_empty(
            primary_stage,
            ";".join(text_cell(item) for item in answer.get("r6_failure_reasons") or []),
            citation.get("citation_support_status"),
        )
        current_eval_status = first_non_empty(
            citation.get("citation_support_status"),
            primary_stage,
            context.get("taxonomy"),
        )
        notes = [
            "R7/R8 deterministic artifacts only; no live LLM answer or optional judge decision is applied.",
            f"R7 primary_stage={primary_stage or 'missing'}",
        ]
        if citation:
            notes.append(
                "R8 citation_support_status="
                + text_cell(citation.get("citation_support_status") or "missing")
            )
        if context.get("failure_reasons"):
            notes.append("R6 failure_reasons=" + text_cell(context.get("failure_reasons")))

        records.append(
            base_record(
                track="TEXT",
                query_id=query_id,
                source_gold_file=gold_path,
                source_record_origin="active_text_namu_v4_gold",
                bucket=row.get("bucket"),
                query=row.get("query"),
                label_status=label_status,
                current_gold_status=current_gold_status,
                expected_answer_text=row.get("expected_answer_summary"),
                must_contain_terms=row.get("must_contain_terms"),
                expected_source=row.get("source_dataset"),
                expected_document=cell_first(expected_surface.get("expected_page_ids"), row.get("expected_page_ids")),
                expected_page=cell_first(expected_surface.get("expected_page_ids"), row.get("expected_page_ids")),
                expected_section=cell_first(
                    expected_surface.get("expected_section_ids"), row.get("expected_section_ids")
                ),
                expected_section_id=cell_first(
                    expected_surface.get("expected_section_ids"), row.get("expected_section_ids")
                ),
                expected_chunk=cell_first(
                    expected_surface.get("expected_chunk_ids"), row.get("expected_chunk_ids")
                ),
                expected_chunk_id=cell_first(
                    expected_surface.get("expected_chunk_ids"), row.get("expected_chunk_ids")
                ),
                current_eval_status=current_eval_status,
                current_failure_or_warning_type=failure_type,
                current_denominator_policy=denominator_policy,
                current_recommended_codex_bucket=primary_group,
                review_group=primary_group,
                review_group_tags=tags,
                notes_for_reviewer=" ".join(notes),
            )
        )

    return records


def build_pdf_records(inputs: Mapping[str, Path]) -> list[dict[str, str]]:
    gold_path = inputs["pdf_gold"]
    gold_rows = read_csv_if_exists(gold_path)
    c7_rows = read_csv_if_exists(inputs["pdf_c7_decision_pack"])
    c7_by_id = {row.get("query_id", ""): row for row in c7_rows}

    records = []
    for row in gold_rows:
        query_id = row.get("query_id", "")
        c7 = c7_by_id.get(query_id)
        if c7:
            primary_group = c7.get("decision_group") or c7.get("c7_primary_classification")
            current_status = "c7_policy_pending_human_decision_required"
            current_eval_status = c7.get("c7_primary_classification") or primary_group
            failure_type = first_non_empty(
                c7.get("c6_failure_type"),
                c7.get("c6_failure_types"),
                c7.get("c5_failure_reason"),
                c7.get("gold_policy_implication"),
            )
            recommended = primary_group
            notes = first_non_empty(
                c7.get("user_decision_needed_items"),
                c7.get("gold_policy_implication"),
                "C7 requires user decision before PDF denominator promotion.",
            )
        else:
            primary_group = "matched_positive_control_7"
            current_status = "matched_positive_control_policy_pending"
            current_eval_status = "matched_positive_control"
            failure_type = "none_observed_in_c7_failed_set"
            recommended = primary_group
            notes = (
                "Matched positive control from PDF gold; still diagnostic-only until "
                "C7 policy decisions settle the PDF denominator."
            )

        tags = [primary_group]
        if primary_group in {
            "table_gold_policy_review_required",
            "query_surface_or_answerability_review_required",
            "page_only_evidence_policy_review_required",
            "bbox_policy_review_required",
        }:
            tags.append("c7_human_decision_required_15")

        records.append(
            base_record(
                track="PDF",
                query_id=query_id,
                source_gold_file=gold_path,
                source_record_origin="pdf_v1_review_draft_query_surface_with_c7_v0_policy_overlay",
                bucket=row.get("bucket"),
                query=row.get("query"),
                label_status=row.get("label_status"),
                current_gold_status=current_status,
                expected_answer_text=row.get("expected_answer_text"),
                must_contain_terms=row.get("must_contain_terms"),
                expected_document_version_id=row.get("expected_document_version_id"),
                expected_file_name=row.get("expected_file_name"),
                expected_page=row.get("expected_page_no"),
                expected_page_no=row.get("expected_page_no"),
                expected_physical_page_index=row.get("expected_physical_page_index"),
                expected_page_label=row.get("expected_page_label"),
                expected_range=row.get("expected_cell_range"),
                expected_bbox=row.get("expected_bbox"),
                expected_table_id=row.get("expected_table_id"),
                current_eval_status=current_eval_status,
                current_failure_or_warning_type=failure_type,
                current_denominator_policy=(
                    "PDF C7 policy pending; official denominator remains unchanged "
                    "and all rows stay diagnostic-only until user decision"
                ),
                current_recommended_codex_bucket=recommended,
                review_group=primary_group,
                review_group_tags=tags,
                notes_for_reviewer=notes,
            )
        )

    return records


def base_record(
    *,
    track: str,
    query_id: Any,
    source_gold_file: Path,
    source_record_origin: str,
    bucket: Any,
    query: Any,
    label_status: Any,
    current_gold_status: str,
    expected_answer_text: Any = "",
    must_contain_terms: Any = "",
    expected_source: Any = "",
    expected_document: Any = "",
    expected_document_version_id: Any = "",
    expected_file_name: Any = "",
    expected_page: Any = "",
    expected_page_no: Any = "",
    expected_physical_page_index: Any = "",
    expected_page_label: Any = "",
    expected_section: Any = "",
    expected_section_id: Any = "",
    expected_chunk: Any = "",
    expected_chunk_id: Any = "",
    expected_range: Any = "",
    expected_bbox: Any = "",
    expected_sheet_name: Any = "",
    expected_cell_range: Any = "",
    expected_table_id: Any = "",
    current_eval_status: Any = "",
    current_failure_or_warning_type: Any = "",
    current_denominator_policy: Any = "",
    current_recommended_codex_bucket: Any = "",
    review_group: Any = "",
    review_group_tags: list[str] | str | None = None,
    notes_for_reviewer: Any = "",
    suggested_gold_decision: Any = "",
    suggested_answerability_label: Any = "",
    suggested_relevance_label: Any = "",
    suggested_expected_evidence_policy: Any = "",
    suggested_denominator_policy: Any = "",
    suggested_issue_tags: list[str] | str | None = None,
    suggested_notes: Any = "",
) -> dict[str, str]:
    group = text_cell(review_group)
    group_tags = text_cell(review_group_tags or review_group)
    suggestions = default_suggestions(
        track=track,
        review_group=group,
        review_group_tags=group_tags,
        current_gold_status=current_gold_status,
    )
    record = {
        "track": track,
        "query_id": text_cell(query_id),
        "source_gold_file": repo_relative(source_gold_file),
        "source_record_origin": source_record_origin,
        "bucket": text_cell(bucket),
        "query": text_cell(query),
        "label_status": text_cell(label_status),
        "current_gold_status": current_gold_status,
        "expected_answer_text": text_cell(expected_answer_text),
        "must_contain_terms": text_cell(must_contain_terms),
        "expected_source": text_cell(expected_source),
        "expected_document": text_cell(expected_document),
        "expected_document_version_id": text_cell(expected_document_version_id),
        "expected_file_name": text_cell(expected_file_name),
        "expected_page": text_cell(expected_page),
        "expected_page_no": text_cell(expected_page_no),
        "expected_physical_page_index": text_cell(expected_physical_page_index),
        "expected_page_label": text_cell(expected_page_label),
        "expected_section": text_cell(expected_section),
        "expected_section_id": text_cell(expected_section_id),
        "expected_chunk": text_cell(expected_chunk),
        "expected_chunk_id": text_cell(expected_chunk_id),
        "expected_range": text_cell(expected_range),
        "expected_bbox": text_cell(expected_bbox),
        "expected_sheet_name": text_cell(expected_sheet_name),
        "expected_cell_range": text_cell(expected_cell_range),
        "expected_table_id": text_cell(expected_table_id),
        "current_eval_status": text_cell(current_eval_status),
        "current_failure_or_warning_type": text_cell(current_failure_or_warning_type),
        "current_denominator_policy": text_cell(current_denominator_policy),
        "current_recommended_codex_bucket": text_cell(current_recommended_codex_bucket),
        "review_group": group,
        "review_group_tags": group_tags,
        "user_decision_required": "true",
        "notes_for_reviewer": text_cell(notes_for_reviewer),
        "suggested_gold_decision": text_cell(suggested_gold_decision)
        or suggestions["suggested_gold_decision"],
        "suggested_answerability_label": text_cell(suggested_answerability_label)
        or suggestions["suggested_answerability_label"],
        "suggested_relevance_label": text_cell(suggested_relevance_label)
        or suggestions["suggested_relevance_label"],
        "suggested_expected_evidence_policy": text_cell(suggested_expected_evidence_policy)
        or suggestions["suggested_expected_evidence_policy"],
        "suggested_denominator_policy": text_cell(suggested_denominator_policy)
        or suggestions["suggested_denominator_policy"],
        "suggested_issue_tags": text_cell(suggested_issue_tags)
        or suggestions["suggested_issue_tags"],
        "suggested_notes": text_cell(suggested_notes) or text_cell(notes_for_reviewer),
    }
    for column in DECISION_COLUMNS:
        record[column] = ""
    return record


def default_suggestions(
    *,
    track: str,
    review_group: str,
    review_group_tags: str,
    current_gold_status: str,
) -> dict[str, str]:
    issue_tags = issue_tags_from_review_group(track, review_group, review_group_tags)
    if track == "XLSX":
        if review_group == "positive_retrieval_review":
            return suggestion(
                "KEEP_POSITIVE",
                "ANSWERABLE",
                "RELEVANT",
                "KEEP_CURRENT_EVIDENCE",
                "INCLUDE_POSITIVE_DENOMINATOR",
                issue_tags,
            )
        if review_group == "hidden_negative_policy_review":
            return suggestion(
                "RELABEL_NEGATIVE",
                "NOT_ANSWERABLE",
                "IRRELEVANT",
                "DEFER",
                "EXCLUDE_POSITIVE_DENOMINATOR",
                issue_tags,
            )
        if review_group in {"formula_date_contract_review", "range_policy_review"}:
            return suggestion(
                "REVISE_EXPECTED_EVIDENCE",
                "UNCLEAR",
                "PARTIAL",
                "REVISE_EXPECTED_EVIDENCE",
                "DEFER",
                issue_tags,
            )
        return suggestion(
            "REQUIRE_PARSER_OR_CHUNK_FIX",
            "UNCLEAR",
            "UNCLEAR",
            "DEFER",
            "DIAGNOSTIC_ONLY",
            issue_tags,
        )
    if track == "TEXT":
        if review_group == "positive_answerable_from_context_29":
            return suggestion(
                "KEEP_POSITIVE",
                "ANSWERABLE",
                "RELEVANT",
                "KEEP_CURRENT_EVIDENCE",
                "INCLUDE_POSITIVE_DENOMINATOR",
                issue_tags,
            )
        if review_group == "retrieval_context_miss_18":
            return suggestion(
                "KEEP_POSITIVE",
                "UNCLEAR",
                "RELEVANT",
                "KEEP_CURRENT_EVIDENCE",
                "INCLUDE_POSITIVE_EXCLUDE_CITATION_DENOMINATOR",
                issue_tags,
            )
        return suggestion(
            "RELABEL_NEEDS_REVIEW",
            "UNCLEAR",
            "UNCLEAR",
            "UNCLEAR",
            "EXCLUDE_POSITIVE_DENOMINATOR",
            issue_tags,
        )
    if track == "PDF":
        if review_group == "matched_positive_control_7":
            return suggestion(
                "KEEP_POSITIVE",
                "ANSWERABLE",
                "RELEVANT",
                "KEEP_CURRENT_EVIDENCE",
                "DIAGNOSTIC_ONLY",
                issue_tags,
            )
        evidence_policy = "DEFER"
        gold_decision = "DEFER"
        if review_group == "table_gold_policy_review_required":
            evidence_policy = "REQUIRE_TABLE_LIKE_EVIDENCE"
            gold_decision = "REQUIRE_PARSER_OR_CHUNK_FIX"
        elif review_group == "page_only_evidence_policy_review_required":
            evidence_policy = "ALLOW_PAGE_ONLY_EVIDENCE"
            gold_decision = "REVISE_EXPECTED_EVIDENCE"
        elif review_group == "bbox_policy_review_required":
            evidence_policy = "REQUIRE_BBOX_OVERLAP"
            gold_decision = "REVISE_EXPECTED_EVIDENCE"
        elif review_group == "query_surface_or_answerability_review_required":
            gold_decision = "REVISE_QUERY"
            evidence_policy = "UNCLEAR"
        return suggestion(
            gold_decision,
            "UNCLEAR",
            "UNCLEAR",
            evidence_policy,
            "BLOCKED_GOLD_POLICY",
            issue_tags,
        )
    return suggestion("DEFER", "UNCLEAR", "UNCLEAR", "UNCLEAR", "DEFER", issue_tags)


def suggestion(
    gold_decision: str,
    answerability_label: str,
    relevance_label: str,
    expected_evidence_policy: str,
    denominator_policy: str,
    issue_tags: list[str],
) -> dict[str, str]:
    return {
        "suggested_gold_decision": gold_decision,
        "suggested_answerability_label": answerability_label,
        "suggested_relevance_label": relevance_label,
        "suggested_expected_evidence_policy": expected_evidence_policy,
        "suggested_denominator_policy": denominator_policy,
        "suggested_issue_tags": ";".join(stable_unique(issue_tags)),
    }


def issue_tags_from_review_group(track: str, review_group: str, review_group_tags: str) -> list[str]:
    raw_tags = {tag for tag in review_group_tags.split("|") if tag}
    mapped: list[str] = []
    if "needs_review_3" in raw_tags:
        mapped.append("NEEDS_REVIEW")
    if "must_contain_terms_strictness_review" in raw_tags:
        mapped.append("MUST_CONTAIN_STRICTNESS")
    if "expected_answer_or_evidence_review" in raw_tags:
        mapped.append("EXPECTED_EVIDENCE")
    if "retrieval_context_miss_18" in raw_tags:
        mapped.extend(["RETRIEVAL_CONTEXT_MISS", "CITATION_DENOMINATOR_EXCLUDED"])
    if "hidden_negative_policy_review" in raw_tags:
        mapped.append("HIDDEN_NEGATIVE_POLICY")
    if "formula_date_contract_review" in raw_tags:
        mapped.append("FORMULA_DATE_CONTRACT")
    if "range_policy_review" in raw_tags:
        mapped.append("RANGE_POLICY")
    if "location_rank_watch_items" in raw_tags:
        mapped.append("LOCATION_RANK_WATCH")
    if "table_gold_policy_review_required" in raw_tags:
        mapped.extend(["PDF_C7_POLICY_PENDING", "TABLE_POLICY", "PARSER_CHUNK_CONTRACT"])
    if "query_surface_or_answerability_review_required" in raw_tags:
        mapped.extend(["PDF_C7_POLICY_PENDING", "QUERY_SURFACE", "ANSWERABILITY", "RELEVANCE"])
    if "page_only_evidence_policy_review_required" in raw_tags:
        mapped.extend(["PDF_C7_POLICY_PENDING", "PAGE_ONLY_POLICY", "EXPECTED_EVIDENCE"])
    if "bbox_policy_review_required" in raw_tags:
        mapped.extend(["PDF_C7_POLICY_PENDING", "BBOX_POLICY", "EXPECTED_EVIDENCE"])
    if track == "PDF" and review_group != "matched_positive_control_7":
        mapped.append("DENOMINATOR_POLICY")
    return stable_unique([tag for tag in mapped if tag in USER_ISSUE_TAG_OPTIONS])


def xlsx_primary_group(decision: str, category: str) -> str:
    if decision == "KEEP_AS_POSITIVE":
        return "positive_retrieval_review"
    if decision == "RELABEL_AS_NEGATIVE_HIDDEN_POLICY" or category == "hidden_policy_contract":
        return "hidden_negative_policy_review"
    if category == "formula_date_contract":
        return "formula_date_contract_review"
    if category in {"table_range_strictness", "gold_binding"}:
        return "range_policy_review"
    return "deferred_or_excluded_review"


def xlsx_group_tags(
    *,
    row: Mapping[str, Any],
    decision: Mapping[str, Any],
    primary_group: str,
) -> list[str]:
    tags = [primary_group]
    decision_name = text_cell(decision.get("decision") or row.get("review_decision"))
    category = text_cell(decision.get("category") or row.get("review_category"))
    bucket = text_cell(row.get("bucket") or decision.get("bucket"))
    if decision_name == "KEEP_AS_POSITIVE":
        tags.append("positive_retrieval_review")
    if category == "hidden_policy_contract" or bucket == "xlsx_hidden_policy":
        tags.append("hidden_negative_policy_review")
    if category == "formula_date_contract" or bucket == "xlsx_date_number_format":
        tags.append("formula_date_contract_review")
    if category in {"table_range_strictness", "gold_binding"}:
        tags.append("range_policy_review")
    location_rank = decision.get("location_rank")
    if location_rank not in (None, "", 0, 1, "0", "1"):
        tags.append("location_rank_watch_items")
    if decision_name and decision_name != "KEEP_AS_POSITIVE":
        tags.append("deferred_or_excluded_review")
    return stable_unique(tags)


def xlsx_notes(
    *,
    row: Mapping[str, Any],
    decision: Mapping[str, Any],
    promotion_eligible: str,
    hidden_diag: Mapping[str, Any],
) -> str:
    notes = [
        "Codex did not decide XLSX gold inclusion, hidden-negative policy, or evidence semantics.",
        f"review_decision={text_cell(decision.get('decision') or row.get('review_decision') or 'missing')}",
        f"review_category={text_cell(decision.get('category') or row.get('review_category') or 'missing')}",
        f"promotion_eval_eligible={promotion_eligible or 'missing'}",
    ]
    if decision.get("location_rank") not in (None, ""):
        notes.append(f"location_rank={text_cell(decision.get('location_rank'))}")
    if hidden_diag:
        notes.append("hidden_negative_diagnostic_row=true")
    if row.get("current_evidence_summary"):
        notes.append("current_evidence_summary=" + text_cell(row.get("current_evidence_summary")))
    return " ".join(notes)


def build_candidate_inventory(
    *,
    xlsx_records: list[dict[str, str]],
    text_records: list[dict[str, str]],
    pdf_records: list[dict[str, str]],
    inputs: Mapping[str, Path],
) -> list[dict[str, Any]]:
    pdf_c7_summary = read_json_if_exists(inputs["pdf_c7_decision_pack_summary"])
    text_answer_report = read_json_if_exists(inputs["text_answer_report"])
    xlsx_decisions = read_json_if_exists(inputs["xlsx_review_decisions"])
    return [
        {
            "track": "XLSX",
            "candidate_group": "xlsx_positive_reviewed",
            "observed_row_count": count_group(xlsx_records, "positive_retrieval_review"),
            "expected_or_policy_count": 35,
            "source": repo_relative(inputs["xlsx_positive_reviewed"]),
            "denominator_policy": "reviewed positive denominator remains 35; diagnostic-only review pack",
        },
        {
            "track": "XLSX",
            "candidate_group": "xlsx_unresolved_hidden_deferred_excluded",
            "observed_row_count": len(
                [record for record in xlsx_records if record["review_group"] != "positive_retrieval_review"]
            ),
            "expected_or_policy_count": xlsx_decisions.get("excluded_or_deferred_count"),
            "source": repo_relative(
                first_existing(
                    inputs["xlsx_naturalized_archive"],
                    inputs["xlsx_v2_archive"],
                )
            ),
            "denominator_policy": "not mixed into the positive retrieval denominator",
            "active_legacy_eval_paths_removed": [
                repo_relative(path) for path in REMOVED_ACTIVE_LEGACY_DATASET_PATHS
            ],
        },
        {
            "track": "TEXT",
            "candidate_group": "text_namu_v4_all",
            "observed_row_count": len(text_records),
            "expected_or_policy_count": 50,
            "source": repo_relative(inputs["text_gold"]),
            "denominator_policy": "47 positive plus 3 needs_review; R7/R8 diagnostic-only",
            "r7_counts": {
                "positive_denominator_count": text_answer_report.get("positive_denominator_count"),
                "needs_review_excluded_count": text_answer_report.get("needs_review_excluded_count"),
                "answerable_from_context_count": text_answer_report.get("answerable_from_context_count"),
                "retrieval_context_miss_count": text_answer_report.get("retrieval_context_miss_count"),
            },
        },
        {
            "track": "PDF",
            "candidate_group": "pdf_gold_c7_policy_pending",
            "observed_row_count": len(pdf_records),
            "expected_or_policy_count": 22,
            "source": repo_relative(inputs["pdf_gold"]),
            "source_v0_reference": repo_relative(inputs["pdf_gold_v0_reference"]),
            "denominator_policy": (
                "PDF review rows use v1 review-draft query surfaces, while C7 policy "
                "remains over the same query_id/evidence bindings; all PDF rows remain "
                "diagnostic-only until C7 user decisions"
            ),
            "c7_counts": {
                "human_decision_required_count": pdf_c7_summary.get("human_decision_required_count"),
                "matched_positive_control_count": pdf_c7_summary.get("matched_positive_control_count"),
                "classification_counts": pdf_c7_summary.get("classification_counts"),
            },
        },
    ]


def build_source_inventory(inputs: Mapping[str, Path]) -> dict[str, Any]:
    gold_keys = [
        "xlsx_positive_reviewed",
        "xlsx_naturalized_archive",
        "xlsx_v2_archive",
        "text_gold",
        "pdf_gold",
        "pdf_gold_v0_reference",
    ]
    report_keys = [key for key in inputs if key not in gold_keys]
    return {
        "gold_csv_inputs": {key: describe_source(path) for key, path in inputs.items() if key in gold_keys},
        "removed_active_legacy_csvs": [
            {
                "path": repo_relative(path),
                "exists": path.exists(),
                "removal_policy": "removed_from_active_eval_queries_to_prevent_default_denominator_reuse",
            }
            for path in REMOVED_ACTIVE_LEGACY_DATASET_PATHS
        ],
        "historical_report_inputs": {
            key: describe_source(path) for key, path in inputs.items() if key in report_keys
        },
    }


def describe_source(path: Path) -> dict[str, Any]:
    descriptor: dict[str, Any] = {
        "path": repo_relative(path),
        "exists": path.exists(),
        "sha256": sha256(path) if path.exists() else None,
    }
    if not path.exists():
        return descriptor
    if path.suffix.lower() == ".csv":
        rows = read_csv_if_exists(path)
        descriptor["row_count"] = len(rows)
        descriptor["columns"] = list(rows[0].keys()) if rows else read_csv_header(path)
    elif path.suffix.lower() == ".json":
        data = read_json_if_exists(path)
        descriptor["status"] = data.get("status")
        descriptor["promotion_evidence"] = data.get("promotion_evidence")
        descriptor["evidence_role"] = data.get("evidence_role")
        for key in [
            "row_count",
            "query_count",
            "positive_denominator_count",
            "needs_review_excluded_count",
            "answerable_from_context_count",
            "retrieval_context_miss_count",
            "human_decision_required_count",
            "matched_positive_control_count",
        ]:
            if key in data:
                descriptor[key] = data[key]
    elif path.suffix.lower() == ".jsonl":
        descriptor["row_count"] = count_jsonl_rows(path)
    return descriptor


def write_review_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_guide(path: Path, summary: Mapping[str, Any], inventory: Mapping[str, Any]) -> None:
    lines = [
        "# A/B/C Gold Set Review Pack",
        "",
        "This pack is diagnostic-only. The CSV files are intentionally narrow labeling sheets; detailed diagnostic context stays in the inventory/source reports and can be joined later by `track` plus `query_id`.",
        "",
        "## Reviewer Columns",
        "",
        "Fill only these `user_*` columns in the CSV packs:",
        "",
        "- `user_gold_decision`",
        "- `user_answerability_label`",
        "- `user_relevance_label`",
        "- `user_expected_evidence_policy`",
        "- `user_denominator_policy`",
        "- `user_issue_tags`",
        "- `user_notes`",
        "",
        "`user_gold_decision` accepts a single enum. `user_issue_tags` accepts multiple enum values separated by semicolons. Blank user decisions are fail-closed and must not be treated as approval.",
        "",
        "Codex filled `suggested_*` columns from the current diagnostic state, but did not apply any user-owned gold decision.",
        "",
        "## User Enums",
        "",
        "- `user_gold_decision`: "
        + ", ".join(f"`{option}`" for option in USER_GOLD_DECISION_OPTIONS),
        "- `user_answerability_label`: "
        + ", ".join(f"`{option}`" for option in USER_ANSWERABILITY_OPTIONS),
        "- `user_relevance_label`: "
        + ", ".join(f"`{option}`" for option in USER_RELEVANCE_OPTIONS),
        "- `user_expected_evidence_policy`: "
        + ", ".join(f"`{option}`" for option in USER_EXPECTED_EVIDENCE_POLICY_OPTIONS),
        "- `user_denominator_policy`: "
        + ", ".join(f"`{option}`" for option in USER_DENOMINATOR_POLICY_OPTIONS),
        "- `user_issue_tags`: "
        + ", ".join(f"`{option}`" for option in USER_ISSUE_TAG_OPTIONS),
        "",
        "## Counts",
        "",
        f"- XLSX review rows: `{summary['xlsx_review_row_count']}`",
        f"- TEXT review rows: `{summary['text_review_row_count']}`",
        f"- PDF review rows: `{summary['pdf_review_row_count']}`",
        f"- User-decision-required rows: `{summary['user_decision_required_count']}`",
        "",
        "## Track Notes",
        "",
        "### XLSX",
        "",
        "The reviewed positive set remains separate from hidden-negative, deferred, excluded, formula/date, range, and location-rank watch rows. If these are not reviewed, the next baseline refresh can mix hidden-negative or unresolved evidence semantics into a positive retrieval denominator.",
        "",
        "### TEXT",
        "",
        "The Namu v4 set keeps 29 answerable-from-context rows, 18 retrieval/context misses, and 3 needs-review rows separate. If these are not reviewed, R8 citation support and future answerability metrics can inherit uncertain must-contain-term or expected-evidence semantics.",
        "",
        "### PDF",
        "",
        "The PDF set keeps 7 matched positive controls separate from 15 C7 human-decision rows. If table/page/bbox/query-surface policy is not reviewed, C6 follow-up reclassification and any official PDF denominator would be policy-contaminated.",
        "",
        "The PDF labeling rows use `gold_queries_pdf_v1_review_draft.csv` query surfaces while preserving the C7 policy-pending split by `query_id`.",
        "",
        "## Blocked Next Steps",
        "",
    ]
    for step in summary["blocked_next_steps_until_user_review"]:
        lines.append(f"- `{step}`")
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- Inventory: `{inventory['review_pack_paths']['summary'].replace('summary.json', 'inventory.json')}`",
            f"- Summary: `{inventory['review_pack_paths']['summary']}`",
            f"- XLSX CSV: `{inventory['review_pack_paths']['xlsx']}`",
            f"- TEXT CSV: `{inventory['review_pack_paths']['text']}`",
            f"- PDF CSV: `{inventory['review_pack_paths']['pdf']}`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def read_csv_if_exists(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl_if_exists(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def read_decision_rows(path: Path) -> list[dict[str, Any]]:
    data = read_json_if_exists(path)
    rows = data.get("decisions")
    return rows if isinstance(rows, list) else []


def index_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    return {row.get("query_id", ""): row for row in read_jsonl_if_exists(path)}


def flatten_decision_gold_fields(decision: Mapping[str, Any]) -> dict[str, Any]:
    fields = dict(decision.get("gold_fields") or {})
    fields.update(
        {
            "query_id": decision.get("query_id"),
            "bucket": decision.get("bucket"),
            "query": decision.get("query"),
            "review_decision": decision.get("decision"),
            "review_category": decision.get("category"),
            "review_reason_code": decision.get("reason_code"),
            "promotion_eval_eligible": decision.get("promotion_eval_eligible"),
        }
    )
    return fields


def first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = text_cell(value)
        if text:
            return text
    return ""


def cell_first(*values: Any) -> str:
    for value in values:
        text = text_cell(value)
        if text:
            return text
    return ""


def text_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        return "|".join(text_cell(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def bool_text(value: Any) -> str:
    text = text_cell(value).lower()
    if text in {"true", "1", "yes"}:
        return "true"
    if text in {"false", "0", "no"}:
        return "false"
    return text


def stable_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def count_review_group_tags(records: list[Mapping[str, str]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for record in records:
        tags = [tag for tag in record.get("review_group_tags", "").split("|") if tag]
        if not tags and record.get("review_group"):
            tags = [record["review_group"]]
        counter.update(tags)
    return dict(sorted(counter.items()))


def count_group(records: list[Mapping[str, str]], group: str) -> int:
    return sum(1 for record in records if group in record.get("review_group_tags", "").split("|"))


def count_jsonl_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
