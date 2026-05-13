"""Clean reviewed TEXT/PDF gold signals and create tuning-only silver sets.

This is a source-input normalization bridge for reviewed spreadsheet exports.
It does not update the official denominator registry, does not decide human
gold semantics, and does not claim PDF page/bbox/table/row/column/value
success. Outputs are candidate manifests and tuning-only rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
OUTPUT_DIR = AI_WORKER_ROOT / "eval" / "review" / "gold_silver_tuning"
TEXT_REVIEW_CSV = (
    AI_WORKER_ROOT
    / "eval"
    / "review"
    / "text_namu_v2_gold_review"
    / "text_namu_v2_gold_review_pack - text_namu_v2_gold_review_pack.csv"
)
PDF_FILE_LOOKUP_REVIEW_CSV = (
    AI_WORKER_ROOT
    / "eval"
    / "review"
    / "pdf_supplemental_gold_review"
    / "pdf_gold_review_pack_manual_v1_file_lookup_companion - "
    "pdf_gold_review_pack_manual_v1_file_lookup_companion.csv"
)
TEXT_CANDIDATE_CSV = (
    AI_WORKER_ROOT
    / "eval"
    / "review"
    / "text_namu_v2_gold_review"
    / "text_namu_v2_gold_candidates.csv"
)
NEMU_CHUNKS_JSONL = AI_WORKER_ROOT / "eval" / "corpora" / "namu-v4-structured-combined" / "rag_chunks.jsonl"
PHASE7_SILVER_JSONL = (
    AI_WORKER_ROOT
    / "eval"
    / "reports"
    / "phase7"
    / "7.12_silver_manual_curated"
    / "queries_v4_silver_manual_curated_500.jsonl"
)
PDF_MERGED_WITH_FILE_LOOKUP_CSV = (
    AI_WORKER_ROOT
    / "eval"
    / "review"
    / "pdf_supplemental_gold_review"
    / "pdf_gold_review_pack_manual_v1_with_file_lookup.csv"
)
OFFICIAL_DENOMINATOR_REGISTRY = AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"
PROGRESS_LOG = REPO_ROOT / "docs" / "rag-ingestion-progress.md"
TRACK_B_PROGRESS_LOG = REPO_ROOT / "docs" / "track_b_text_retrieval_e2e" / "rag_text_retrieval_e2e_progress.md"

TEXT_MAIN_POSITIVE = "text_gold_main_positive_clean.csv"
TEXT_ABSTAIN_DIAGNOSTIC = "text_gold_abstain_diagnostic_clean.csv"
TEXT_DEFERRED_OR_EXCLUDED = "text_gold_deferred_or_excluded_clean.csv"
PDF_POSITIVE = "pdf_file_lookup_gold_positive_clean.csv"
PDF_DIAGNOSTIC = "pdf_file_lookup_diagnostic_clean.csv"
PDF_DEFERRED_OR_EXCLUDED = "pdf_file_lookup_deferred_or_excluded_clean.csv"
SILVER_TEXT_POSITIVE = "silver_text_positive_train.csv"
SILVER_TEXT_HARD_NEGATIVE = "silver_text_hard_negative_train.csv"
SILVER_TEXT_ABSTAIN = "silver_text_abstain_diagnostic.csv"
SILVER_PDF_POSITIVE = "silver_pdf_file_lookup_positive_train.csv"
SILVER_PDF_HARD_NEGATIVE = "silver_pdf_file_lookup_hard_negative_train.csv"
SILVER_MANIFEST = "silver_manifest.csv"

REPORT_FILES = {
    "gold_cleanup_report": "gold_cleanup_report.md",
    "silver_generation_report": "silver_generation_report.md",
    "denominator_manifest": "denominator_manifest.json",
    "tuning_readiness_report": "tuning_readiness_report.md",
}

TEXT_PROVENANCE_COLUMNS = {
    "query_id",
    "query",
    "expected_answer_text",
    "source_evidence_quote",
    "expected_document_ids",
    "expected_page_ids",
    "expected_section_ids",
    "expected_chunk_ids",
    "source_locator",
    "candidate_default_policy",
}
TEXT_ALLOWED_ANSWERABILITY = {"ANSWERABLE", "NOT_ANSWERABLE", "UNCLEAR", "INVALID_QUERY"}
TEXT_MAIN_ALLOWED_POLICY = "KEEP_POSITIVE"
PDF_FILE_LOOKUP_ANSWERABILITY = {"ANSWERABLE", "ANSWERABLE_AS_FILE_LOOKUP"}
TEXT_ID_COLUMNS = ["expected_document_ids", "expected_page_ids", "expected_section_ids", "expected_chunk_ids"]
PDF_SEMANTIC_GUARDRAILS = [
    "page",
    "bbox",
    "table",
    "row",
    "column",
    "value",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)
    report_dir = Path(args.report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    text_review_path = Path(args.text_review_csv)
    pdf_review_path = Path(args.pdf_review_csv)
    text_rows, text_columns = read_csv(text_review_path)
    pdf_rows, pdf_columns = read_csv(pdf_review_path)

    chunks_by_id = load_chunks_by_id(Path(args.namu_chunks_jsonl))
    text_cleanup = clean_text_gold(text_rows, text_columns, chunks_by_id)
    pdf_cleanup = clean_pdf_file_lookup(pdf_rows, pdf_columns)
    gold_frozen = freeze_gold_denominator_candidates(
        text_main=text_cleanup["main_positive"],
        text_abstain=text_cleanup["abstain_diagnostic"],
        text_deferred=text_cleanup["deferred_or_excluded"],
        pdf_positive=pdf_cleanup["positive"],
        pdf_diagnostic=pdf_cleanup["diagnostic"],
        pdf_deferred=pdf_cleanup["deferred_or_excluded"],
    )

    write_gold_outputs(output_dir, text_cleanup, pdf_cleanup)

    silver = generate_silver_sets(
        text_rows=text_rows,
        text_cleanup=text_cleanup,
        chunks_by_id=chunks_by_id,
        phase7_silver_path=Path(args.phase7_silver_jsonl),
        pdf_rows=pdf_rows,
        pdf_cleanup=pdf_cleanup,
        pdf_merged_path=Path(args.pdf_merged_csv),
    )
    write_silver_outputs(output_dir, silver)

    context = build_report_context(
        text_review_path=text_review_path,
        pdf_review_path=pdf_review_path,
        text_columns=text_columns,
        pdf_columns=pdf_columns,
        text_cleanup=text_cleanup,
        pdf_cleanup=pdf_cleanup,
        gold_frozen=gold_frozen,
        silver=silver,
        output_dir=output_dir,
        report_dir=report_dir,
    )
    write_reports(report_dir, context)
    if args.update_progress:
        append_progress_logs(context)

    print(
        json.dumps(
            {
                "status": "COMPLETED",
                "output_dir": rel(output_dir),
                "report_dir": rel(report_dir),
                "text_main_positive": len(text_cleanup["main_positive"]),
                "text_abstain_diagnostic": len(text_cleanup["abstain_diagnostic"]),
                "text_deferred_or_excluded": len(text_cleanup["deferred_or_excluded"]),
                "pdf_file_lookup_positive": len(pdf_cleanup["positive"]),
                "pdf_file_lookup_diagnostic": len(pdf_cleanup["diagnostic"]),
                "pdf_deferred_or_excluded": len(pdf_cleanup["deferred_or_excluded"]),
                "silver_manifest_rows": len(silver["manifest"]),
                "official_denominator_registry_changed": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-review-csv", default=str(TEXT_REVIEW_CSV))
    parser.add_argument("--pdf-review-csv", default=str(PDF_FILE_LOOKUP_REVIEW_CSV))
    parser.add_argument("--text-candidate-csv", default=str(TEXT_CANDIDATE_CSV))
    parser.add_argument("--namu-chunks-jsonl", default=str(NEMU_CHUNKS_JSONL))
    parser.add_argument("--phase7-silver-jsonl", default=str(PHASE7_SILVER_JSONL))
    parser.add_argument("--pdf-merged-csv", default=str(PDF_MERGED_WITH_FILE_LOOKUP_CSV))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--report-dir", default=str(REPORT_DIR))
    parser.add_argument(
        "--update-progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="append compact progress-log entries",
    )
    return parser.parse_args(argv)


def clean_text_gold(
    rows: list[dict[str, str]],
    columns: Sequence[str],
    chunks_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    missing = [column for column in required_text_columns() if column not in columns]
    if missing:
        raise ValueError("TEXT review CSV missing required columns: " + ", ".join(missing))

    main_positive: list[dict[str, str]] = []
    abstain_diagnostic: list[dict[str, str]] = []
    deferred_or_excluded: list[dict[str, str]] = []
    decisions: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    conflict_rows: list[str] = []
    missing_override_rows: list[str] = []
    needs_second_review_rows: list[str] = []
    provenance_changes = detect_provenance_changes(rows)

    for row in rows:
        normalized = normalize_row_values(row)
        query_id = normalized["query_id"]
        answerability_values = split_multi_value(normalized.get("user_answerability_label"))
        label_conflict = has_answerability_conflict(answerability_values)
        normalized["user_answerability_label_clean"] = (
            answerability_values[0] if len(answerability_values) == 1 else ""
        )

        status = "CLEANED"
        role = "DEFERRED"
        issue_tags: list[str] = []

        if label_conflict:
            status = "DEFERRED_LABEL_CONFLICT"
            issue_tags.append("ANSWERABILITY_LABEL_CONFLICT")
            conflict_rows.append(query_id)
        elif not answerability_values and normalized.get("user_final_gold_policy") == TEXT_MAIN_ALLOWED_POLICY:
            status = "DEFERRED_MISSING_ANSWERABILITY"
            issue_tags.append("MISSING_ANSWERABILITY")

        final_policy_values = split_multi_value(normalized.get("user_final_gold_policy"))
        requires_answer_override = any("REVISE_EXPECTED_ANSWER" in value for value in final_policy_values)
        requires_evidence_override = any("REVISE_EXPECTED_EVIDENCE" in value for value in final_policy_values)
        if requires_answer_override and not normalized.get("user_expected_answer_override"):
            status = "MISSING_REQUIRED_OVERRIDE"
            issue_tags.append("MISSING_EXPECTED_ANSWER_OVERRIDE")
            missing_override_rows.append(query_id)
        if requires_evidence_override and not normalized.get("user_expected_evidence_override"):
            status = "MISSING_REQUIRED_OVERRIDE"
            issue_tags.append("MISSING_EXPECTED_EVIDENCE_OVERRIDE")
            missing_override_rows.append(query_id)

        final_policy = normalized.get("user_final_gold_policy") or ""
        if "NEEDS_SECOND_REVIEW" in final_policy_values or final_policy == "NEEDS_SECOND_REVIEW":
            status = "DEFERRED_NEEDS_SECOND_REVIEW"
            issue_tags.append("NEEDS_SECOND_REVIEW")
            needs_second_review_rows.append(query_id)

        if normalized.get("user_answerability_label_clean") not in TEXT_ALLOWED_ANSWERABILITY and normalized.get(
            "user_answerability_label_clean"
        ):
            status = "DEFERRED_INVALID_ANSWERABILITY_ENUM"
            issue_tags.append("INVALID_ANSWERABILITY_ENUM")

        source_label_status = normalized.get("source_label_status")
        if source_label_status == "needs_review":
            issue_tags.append("SOURCE_LABEL_STATUS_NEEDS_REVIEW")

        if is_hard_text_defer_status(status):
            role = "DEFERRED"
        elif is_text_abstain_diagnostic(normalized):
            role = "TEXT_ABSTAIN_DIAGNOSTIC"
            if status == "CLEANED":
                status = "DIAGNOSTIC_ONLY"
        elif is_text_main_positive_candidate(normalized, status):
            role = "TEXT_MAIN_POSITIVE_GOLD_CANDIDATE"
            status = "CLEANED_POSITIVE"
        else:
            role = "DEFERRED"
            if status == "CLEANED":
                status = "EXCLUDED_BY_CONSERVATIVE_POLICY"

        normalized["cleanup_status"] = status
        normalized["denominator_role"] = role
        normalized["official_gold"] = "false"
        normalized["cleanup_issue_tags"] = join_tags(issue_tags)
        normalized["non_obvious_decision"] = explain_text_decision(normalized, issue_tags)
        normalized["source_evidence_quote_verified_in_expected_chunk"] = str(
            text_quote_verified(normalized, chunks_by_id)
        ).lower()

        if role == "TEXT_MAIN_POSITIVE_GOLD_CANDIDATE":
            main_positive.append(normalized)
        elif role == "TEXT_ABSTAIN_DIAGNOSTIC":
            abstain_diagnostic.append(normalized)
        else:
            deferred_or_excluded.append(normalized)

        status_counts[status] += 1
        role_counts[role] += 1
        decisions.append(
            {
                "query_id": query_id,
                "cleanup_status": status,
                "denominator_role": role,
                "issue_tags": issue_tags,
            }
        )

    return {
        "rows": rows,
        "main_positive": main_positive,
        "abstain_diagnostic": abstain_diagnostic,
        "deferred_or_excluded": deferred_or_excluded,
        "decisions": decisions,
        "row_counts_by_cleanup_status": dict(sorted(status_counts.items())),
        "row_counts_by_denominator_role": dict(sorted(role_counts.items())),
        "conflict_rows": sorted(conflict_rows),
        "missing_override_rows": sorted(set(missing_override_rows)),
        "needs_second_review_rows": sorted(set(needs_second_review_rows)),
        "provenance_changes": provenance_changes,
        "normalization_rules": [
            "trimmed whitespace on all fields",
            "treated empty strings as null for validation decisions",
            "split comma/semicolon/pipe user decision cells only to detect conflicts",
            "did not choose a gold label for conflicting answerability cells",
            "did not modify provenance columns",
        ],
    }


def is_text_main_positive_candidate(row: Mapping[str, str], status: str) -> bool:
    if status not in {"CLEANED"}:
        return False
    return (
        row.get("user_final_gold_policy") == "KEEP_POSITIVE"
        and row.get("user_answerability_label_clean") == "ANSWERABLE"
        and row.get("user_relevance_label") == "RELEVANT"
        and row.get("candidate_default_policy") != "DIAGNOSTIC_ONLY_DEFAULT"
        and row.get("bucket") != "abstain_not_answerable_diagnostic"
        and row.get("source_label_status") != "needs_review"
    )


def is_text_abstain_diagnostic(row: Mapping[str, str]) -> bool:
    return (
        row.get("candidate_default_policy") == "DIAGNOSTIC_ONLY_DEFAULT"
        or row.get("bucket") == "abstain_not_answerable_diagnostic"
    )


def is_hard_text_defer_status(status: str) -> bool:
    return status in {
        "DEFERRED_LABEL_CONFLICT",
        "DEFERRED_NEEDS_SECOND_REVIEW",
        "DEFERRED_INVALID_ANSWERABILITY_ENUM",
        "MISSING_REQUIRED_OVERRIDE",
    }


def clean_pdf_file_lookup(rows: list[dict[str, str]], columns: Sequence[str]) -> dict[str, Any]:
    missing = [column for column in required_pdf_columns() if column not in columns]
    if missing:
        raise ValueError("PDF FILE lookup review CSV missing required columns: " + ", ".join(missing))

    positive: list[dict[str, str]] = []
    diagnostic: list[dict[str, str]] = []
    deferred_or_excluded: list[dict[str, str]] = []
    status_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    generic_filename_rows: list[str] = []
    mixed_decision_rows: list[str] = []
    normalized_positive_rows: list[str] = []

    for row in rows:
        normalized = normalize_row_values(row)
        query_id = normalized["query_id"]
        gold_decision_values = split_multi_value(normalized.get("user_gold_decision"))
        risk_tags = set(split_tags(normalized.get("risk_tags")))
        user_issue_tags = set(split_tags(normalized.get("user_issue_tags")))
        issue_tags: list[str] = []
        status = "CLEANED"
        role = "PDF_FILE_LOOKUP_DIAGNOSTIC"

        if "GENERIC_FILENAME" in risk_tags:
            issue_tags.append("GENERIC_FILENAME_IDENTITY_RISK")
            generic_filename_rows.append(query_id)

        if len(gold_decision_values) > 1:
            status = "DEFERRED_MIXED_GOLD_DECISION"
            issue_tags.append("MIXED_USER_GOLD_DECISION")
            mixed_decision_rows.append(query_id)

        positive_allowed = (
            status == "CLEANED"
            and normalized.get("user_gold_decision") == "KEEP_POSITIVE"
            and normalized.get("user_answerability_label") in PDF_FILE_LOOKUP_ANSWERABILITY
            and normalized.get("user_relevance_label") == "RELEVANT"
            and "PDF_FILE_LOOKUP" in risk_tags
            and normalized.get("user_expected_evidence_policy") != "REVISE_EXPECTED_EVIDENCE"
        )
        if positive_allowed:
            role = "PDF_FILE_LOOKUP_GOLD_CANDIDATE"
            status = "CLEANED_FILE_LOOKUP_POSITIVE"
            normalized["user_answerability_label_clean"] = "ANSWERABLE_AS_FILE_LOOKUP"
            normalized["user_expected_evidence_policy_clean"] = "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY"
            normalized["user_denominator_policy_clean"] = "INCLUDE_FILE_LOOKUP_DENOMINATOR_CANDIDATE"
            normalized_positive_rows.append(query_id)
        else:
            normalized["user_answerability_label_clean"] = normalized.get("user_answerability_label", "")
            normalized["user_expected_evidence_policy_clean"] = normalized.get("user_expected_evidence_policy", "")
            normalized["user_denominator_policy_clean"] = normalized.get("user_denominator_policy", "")
            if status == "CLEANED":
                status = "DIAGNOSTIC_OR_EXCLUDED_BY_FILE_LOOKUP_POLICY"
            if is_pdf_deferred(normalized, gold_decision_values):
                role = "DEFERRED"
            else:
                role = "PDF_FILE_LOOKUP_DIAGNOSTIC"

        issue_tags.extend(sorted(user_issue_tags - {""}))
        normalized["diagnostic_page_no"] = normalized.get("expected_page_no", "")
        normalized["diagnostic_page_label"] = normalized.get("expected_page_label", "")
        normalized["diagnostic_bbox"] = normalized.get("expected_bbox", "")
        normalized["diagnostic_evidence_excerpt"] = normalized.get("expected_evidence_excerpt", "")
        normalized["cleanup_status"] = status
        normalized["denominator_role"] = role
        normalized["retrieval_lane_clean"] = "pdf_file_lookup"
        normalized["official_gold"] = "false"
        normalized["cleanup_issue_tags"] = join_tags(issue_tags)
        normalized["non_obvious_decision"] = explain_pdf_decision(normalized, issue_tags)

        if role == "PDF_FILE_LOOKUP_GOLD_CANDIDATE":
            positive.append(normalized)
        elif role == "PDF_FILE_LOOKUP_DIAGNOSTIC":
            diagnostic.append(normalized)
        else:
            deferred_or_excluded.append(normalized)

        status_counts[status] += 1
        role_counts[role] += 1

    return {
        "rows": rows,
        "positive": positive,
        "diagnostic": diagnostic,
        "deferred_or_excluded": deferred_or_excluded,
        "row_counts_by_cleanup_status": dict(sorted(status_counts.items())),
        "row_counts_by_denominator_role": dict(sorted(role_counts.items())),
        "generic_filename_rows": sorted(set(generic_filename_rows)),
        "mixed_decision_rows": sorted(set(mixed_decision_rows)),
        "normalized_positive_rows": sorted(set(normalized_positive_rows)),
        "normalization_rules": [
            "trimmed whitespace on all fields",
            "treated empty strings as null for validation decisions",
            "normalized clear FILE lookup positives to ANSWERABLE_AS_FILE_LOOKUP",
            "normalized clear FILE lookup evidence policy to EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY",
            "kept NOT_ANSWERABLE, IRRELEVANT, PARTIAL, REVISE_EXPECTED_EVIDENCE, mixed decisions, and weak generic filenames out of official positives",
        ],
    }


def is_pdf_deferred(row: Mapping[str, str], gold_decision_values: Sequence[str]) -> bool:
    if len(gold_decision_values) > 1:
        return True
    if row.get("user_gold_decision") == "REVISE_EXPECTED_EVIDENCE":
        return True
    if row.get("user_answerability_label") == "NOT_ANSWERABLE":
        return True
    if row.get("user_relevance_label") == "IRRELEVANT":
        return True
    return False


def freeze_gold_denominator_candidates(
    *,
    text_main: list[dict[str, str]],
    text_abstain: list[dict[str, str]],
    text_deferred: list[dict[str, str]],
    pdf_positive: list[dict[str, str]],
    pdf_diagnostic: list[dict[str, str]],
    pdf_deferred: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "schema_version": "reviewed_gold_denominator_candidate_manifest_v1",
        "generated_at": utc_timestamp(),
        "official_denominator_registry_changed": False,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "denominator_candidates": {
            "text_main_positive_candidate_count": len(text_main),
            "text_abstain_diagnostic_count": len(text_abstain),
            "text_deferred_or_excluded_count": len(text_deferred),
            "pdf_file_lookup_candidate_count": len(pdf_positive),
            "pdf_file_lookup_diagnostic_count": len(pdf_diagnostic),
            "pdf_file_lookup_deferred_or_excluded_count": len(pdf_deferred),
        },
        "policies": {
            "text_main_positive_rule": (
                "KEEP_POSITIVE + ANSWERABLE + RELEVANT + non-diagnostic default + "
                "not source_label_status=needs_review + no conflict + no missing override + no NEEDS_SECOND_REVIEW"
            ),
            "text_abstain_rule": "DIAGNOSTIC_ONLY_DEFAULT or abstain_not_answerable_diagnostic stays diagnostic",
            "pdf_file_lookup_rule": (
                "KEEP_POSITIVE + ANSWERABLE/ANSWERABLE_AS_FILE_LOOKUP + RELEVANT + PDF_FILE_LOOKUP risk tag; "
                "file identity only"
            ),
            "pdf_content_denominator_count": 0,
            "pdf_page_bbox_table_row_column_value_success_claimed": False,
            "official_gold": False,
        },
    }


def generate_silver_sets(
    *,
    text_rows: list[dict[str, str]],
    text_cleanup: Mapping[str, Any],
    chunks_by_id: Mapping[str, Mapping[str, Any]],
    phase7_silver_path: Path,
    pdf_rows: list[dict[str, str]],
    pdf_cleanup: Mapping[str, Any],
    pdf_merged_path: Path,
) -> dict[str, Any]:
    frozen = build_frozen_gold_keys(text_cleanup, pdf_cleanup)
    phase7_rows = read_jsonl(phase7_silver_path)
    silver_text_positive = build_text_silver_positive(phase7_rows, frozen, chunks_by_id)
    silver_text_hard_negative = build_text_silver_hard_negative(silver_text_positive, phase7_rows, frozen)
    silver_text_abstain = build_text_silver_abstain(text_cleanup["abstain_diagnostic"], frozen)

    pdf_candidate_pool = build_pdf_candidate_pool(pdf_rows, pdf_merged_path)
    silver_pdf_positive = build_pdf_silver_identity_from_pool(pdf_candidate_pool, frozen)
    silver_pdf_hard_negative = build_pdf_silver_hard_negative(silver_pdf_positive, pdf_candidate_pool, frozen)

    all_silver = [
        *silver_text_positive,
        *silver_text_hard_negative,
        *silver_text_abstain,
        *silver_pdf_positive,
        *silver_pdf_hard_negative,
    ]
    leakage = run_silver_leakage_checks(all_silver, frozen)
    manifest = build_silver_manifest(
        silver_text_positive=silver_text_positive,
        silver_text_hard_negative=silver_text_hard_negative,
        silver_text_abstain=silver_text_abstain,
        silver_pdf_positive=silver_pdf_positive,
        silver_pdf_hard_negative=silver_pdf_hard_negative,
        leakage=leakage,
    )
    return {
        "text_positive": silver_text_positive,
        "text_hard_negative": silver_text_hard_negative,
        "text_abstain": silver_text_abstain,
        "pdf_positive": silver_pdf_positive,
        "pdf_hard_negative": silver_pdf_hard_negative,
        "manifest": manifest,
        "leakage": leakage,
        "sources": {
            "phase7_silver_jsonl": rel(phase7_silver_path),
            "pdf_merged_csv": rel(pdf_merged_path),
        },
    }


def build_text_silver_positive(
    phase7_rows: list[dict[str, Any]],
    frozen: Mapping[str, set[str]],
    chunks_by_id: Mapping[str, Mapping[str, Any]],
    *,
    limit: int = 120,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_queries: set[str] = set()
    frozen_source_ids = frozen["query_ids"] | frozen["source_query_ids"]
    for row in phase7_rows:
        query_id = clean(row.get("query_id"))
        query = clean(row.get("query"))
        expected_doc_id = clean(row.get("expected_doc_id"))
        expected_chunk_ids = [clean(value) for value in row.get("expected_chunk_ids", []) if clean(value)]
        evidence = clean(row.get("source_evidence"))
        if not query_id or not query or not expected_doc_id or not expected_chunk_ids or not evidence:
            continue
        if query in frozen["queries"] or query_id in frozen_source_ids:
            continue
        if query in seen_queries:
            continue
        if expected_doc_id in frozen["expected_ids"]:
            continue
        if any(chunk_id in frozen["expected_ids"] for chunk_id in expected_chunk_ids):
            continue
        if not phase7_evidence_verified(row, chunks_by_id):
            continue
        rows.append(
            {
                "query_id": f"silver_text_pos_{len(rows) + 1:04d}",
                "source_query_id": query_id,
                "query": query,
                "expected_document_ids": expected_doc_id,
                "expected_page_ids": expected_doc_id,
                "expected_section_path": join_path(row.get("expected_section_path")),
                "expected_chunk_ids": join_ids(expected_chunk_ids),
                "source_evidence_quote": evidence,
                "silver_label": "SILVER_POSITIVE_HIGH_CONFIDENCE",
                "silver_confidence": "HIGH",
                "denominator_role": "TUNING_ONLY",
                "official_gold": "false",
                "leakage_exclusion_reason": "",
                "generation_reason": "deterministic Phase 7 source locator with verified chunk evidence",
            }
        )
        seen_queries.add(query)
        if len(rows) >= limit:
            break
    return rows


def build_text_silver_hard_negative(
    positives: list[dict[str, str]],
    phase7_rows: list[dict[str, Any]],
    frozen: Mapping[str, set[str]],
    *,
    limit: int = 120,
) -> list[dict[str, str]]:
    source_by_doc = defaultdict(list)
    for row in phase7_rows:
        source_by_doc[clean(row.get("expected_doc_id"))].append(row)

    rows: list[dict[str, str]] = []
    for positive in positives:
        if len(rows) >= limit:
            break
        source_query_id = positive["source_query_id"]
        source_row = next((r for r in phase7_rows if clean(r.get("query_id")) == source_query_id), None)
        if not source_row:
            continue
        wrong = choose_wrong_text_anchor(source_row, phase7_rows, source_by_doc, frozen)
        if not wrong:
            continue
        rows.append(
            {
                "query_id": f"silver_text_hneg_{len(rows) + 1:04d}",
                "source_query_id": source_query_id,
                "query": positive["query"],
                "expected_document_ids": clean(wrong.get("expected_doc_id")),
                "expected_page_ids": clean(wrong.get("expected_doc_id")),
                "expected_section_path": join_path(wrong.get("expected_section_path")),
                "expected_chunk_ids": join_ids(wrong.get("expected_chunk_ids", [])),
                "positive_expected_document_ids": positive["expected_document_ids"],
                "negative_strategy": negative_strategy(source_row, wrong),
                "silver_label": "SILVER_HARD_NEGATIVE",
                "silver_confidence": "MEDIUM",
                "denominator_role": "TUNING_ONLY",
                "official_gold": "false",
                "generation_reason": "same/similar corpus surface paired with wrong expected ids",
            }
        )
    return rows


def build_text_silver_abstain(abstain_gold: list[dict[str, str]], frozen: Mapping[str, set[str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in abstain_gold:
        query = clean(row.get("query"))
        if not query or query in frozen["queries"]:
            continue
        rows.append(
            {
                "query_id": f"silver_text_abstain_{len(rows) + 1:04d}",
                "source_query_id": clean(row.get("query_id")),
                "query": query,
                "expected_document_ids": "",
                "expected_page_ids": "",
                "expected_section_ids": "",
                "expected_chunk_ids": "",
                "silver_label": "SILVER_ABSTAIN_DIAGNOSTIC",
                "silver_confidence": "MEDIUM",
                "denominator_role": "TUNING_ONLY",
                "official_gold": "false",
                "generation_reason": "reviewed TEXT abstain diagnostic row; excluded from gold denominator",
            }
        )
    return rows


def build_pdf_silver_positive(pdf_positive: list[dict[str, str]], frozen: Mapping[str, set[str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in pdf_positive:
        query = clean(row.get("query"))
        source_query_id = clean(row.get("query_id"))
        expected_file = clean(row.get("expected_file_name") or row.get("source_file_name"))
        document_version = clean(row.get("expected_document_version_id"))
        if source_query_id in frozen["query_ids"] or query in frozen["queries"]:
            # Gold eval rows must not become silver training rows.
            continue
        if not expected_file:
            continue
        rows.append(
            {
                "query_id": f"silver_pdf_file_pos_{len(rows) + 1:04d}",
                "source_query_id": source_query_id,
                "query": derive_pdf_file_lookup_silver_query(row, len(rows) + 1),
                "retrieval_lane": "pdf_file_lookup",
                "expected_file_name": expected_file,
                "source_file_name": clean(row.get("source_file_name")),
                "expected_document_version_id": document_version,
                "expected_evidence_policy": "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY",
                "silver_label": "SILVER_FILE_LOOKUP_POSITIVE",
                "silver_confidence": "HIGH" if "GENERIC_FILENAME" not in split_tags(row.get("risk_tags")) else "MEDIUM",
                "denominator_role": "TUNING_ONLY",
                "official_gold": "false",
                "generation_reason": "PDF FILE lookup semantics only; no page/bbox/table/value claim",
            }
        )
    return rows


def build_pdf_silver_identity_from_pool(
    pdf_candidate_pool: list[dict[str, str]],
    frozen: Mapping[str, set[str]],
    *,
    limit: int = 30,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_files: set[str] = set()
    frozen_source_ids = frozen["query_ids"] | frozen["source_query_ids"]
    for row in sorted(
        pdf_candidate_pool,
        key=lambda item: (
            generic_filename_family(clean(item.get("expected_file_name") or item.get("source_file_name"))) != "",
            clean(item.get("expected_file_name") or item.get("source_file_name")),
        ),
    ):
        expected_file = clean(row.get("expected_file_name") or row.get("source_file_name"))
        source_query_id = clean(row.get("query_id"))
        query = clean(row.get("query"))
        if not expected_file or expected_file in seen_files:
            continue
        if source_query_id in frozen_source_ids or query in frozen["queries"] or expected_file in frozen["expected_ids"]:
            continue
        if generic_filename_family(expected_file):
            continue
        rows.append(
            {
                "query_id": f"silver_pdf_file_pos_{len(rows) + 1:04d}",
                "source_query_id": source_query_id,
                "query": f"{pdf_file_query_hint(expected_file)} 자료를 파일 목록에서 찾아줘",
                "retrieval_lane": "pdf_file_lookup",
                "expected_file_name": expected_file,
                "source_file_name": clean(row.get("source_file_name")),
                "expected_document_version_id": clean(row.get("expected_document_version_id")),
                "expected_evidence_policy": "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY",
                "silver_label": "SILVER_FILE_LOOKUP_POSITIVE",
                "silver_confidence": "HIGH",
                "denominator_role": "TUNING_ONLY",
                "official_gold": "false",
                "generation_reason": "non-gold PDF file identity row from companion/content pool; no page/bbox/table/value claim",
            }
        )
        seen_files.add(expected_file)
        if len(rows) >= limit:
            break
    return rows


def build_pdf_silver_hard_negative(
    pdf_positive: list[dict[str, str]],
    pdf_candidate_pool: list[dict[str, str]],
    frozen: Mapping[str, set[str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for positive in pdf_positive:
        wrong = choose_wrong_pdf_file(positive, pdf_candidate_pool, frozen)
        if not wrong:
            continue
        rows.append(
            {
                "query_id": f"silver_pdf_file_hneg_{len(rows) + 1:04d}",
                "source_query_id": positive["source_query_id"],
                "query": positive["query"],
                "retrieval_lane": "pdf_file_lookup",
                "expected_file_name": clean(wrong.get("expected_file_name") or wrong.get("source_file_name")),
                "source_file_name": clean(wrong.get("source_file_name")),
                "expected_document_version_id": clean(wrong.get("expected_document_version_id")),
                "positive_expected_file_name": positive["expected_file_name"],
                "expected_evidence_policy": "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY",
                "negative_strategy": pdf_negative_strategy(positive, wrong),
                "silver_label": "SILVER_FILE_LOOKUP_HARD_NEGATIVE",
                "silver_confidence": "MEDIUM",
                "denominator_role": "TUNING_ONLY",
                "official_gold": "false",
                "generation_reason": "similar/wrong PDF file identity; no content semantics claimed",
            }
        )
    return rows


def write_gold_outputs(output_dir: Path, text_cleanup: Mapping[str, Any], pdf_cleanup: Mapping[str, Any]) -> None:
    write_csv(output_dir / TEXT_MAIN_POSITIVE, text_cleanup["main_positive"], fieldnames=clean_text_fieldnames())
    write_csv(output_dir / TEXT_ABSTAIN_DIAGNOSTIC, text_cleanup["abstain_diagnostic"], fieldnames=clean_text_fieldnames())
    write_csv(
        output_dir / TEXT_DEFERRED_OR_EXCLUDED,
        text_cleanup["deferred_or_excluded"],
        fieldnames=clean_text_fieldnames(),
    )
    write_csv(output_dir / PDF_POSITIVE, pdf_cleanup["positive"], fieldnames=clean_pdf_fieldnames())
    write_csv(output_dir / PDF_DIAGNOSTIC, pdf_cleanup["diagnostic"], fieldnames=clean_pdf_fieldnames())
    write_csv(
        output_dir / PDF_DEFERRED_OR_EXCLUDED,
        pdf_cleanup["deferred_or_excluded"],
        fieldnames=clean_pdf_fieldnames(),
    )


def write_silver_outputs(output_dir: Path, silver: Mapping[str, Any]) -> None:
    write_csv(output_dir / SILVER_TEXT_POSITIVE, silver["text_positive"], fieldnames=silver_text_positive_fieldnames())
    write_csv(
        output_dir / SILVER_TEXT_HARD_NEGATIVE,
        silver["text_hard_negative"],
        fieldnames=silver_text_hard_negative_fieldnames(),
    )
    write_csv(output_dir / SILVER_TEXT_ABSTAIN, silver["text_abstain"], fieldnames=silver_text_abstain_fieldnames())
    write_csv(output_dir / SILVER_PDF_POSITIVE, silver["pdf_positive"], fieldnames=silver_pdf_positive_fieldnames())
    write_csv(
        output_dir / SILVER_PDF_HARD_NEGATIVE,
        silver["pdf_hard_negative"],
        fieldnames=silver_pdf_hard_negative_fieldnames(),
    )
    write_csv(output_dir / SILVER_MANIFEST, silver["manifest"], fieldnames=silver_manifest_fieldnames())


def build_report_context(
    *,
    text_review_path: Path,
    pdf_review_path: Path,
    text_columns: Sequence[str],
    pdf_columns: Sequence[str],
    text_cleanup: Mapping[str, Any],
    pdf_cleanup: Mapping[str, Any],
    gold_frozen: Mapping[str, Any],
    silver: Mapping[str, Any],
    output_dir: Path,
    report_dir: Path,
) -> dict[str, Any]:
    output_files = {
        name: rel(output_dir / name)
        for name in [
            TEXT_MAIN_POSITIVE,
            TEXT_ABSTAIN_DIAGNOSTIC,
            TEXT_DEFERRED_OR_EXCLUDED,
            PDF_POSITIVE,
            PDF_DIAGNOSTIC,
            PDF_DEFERRED_OR_EXCLUDED,
            SILVER_TEXT_POSITIVE,
            SILVER_TEXT_HARD_NEGATIVE,
            SILVER_TEXT_ABSTAIN,
            SILVER_PDF_POSITIVE,
            SILVER_PDF_HARD_NEGATIVE,
            SILVER_MANIFEST,
        ]
    }
    report_files = {key: rel(report_dir / name) for key, name in REPORT_FILES.items()}
    context = {
        "schema_version": "reviewed_gold_cleanup_and_silver_generation_v1",
        "generated_at": utc_timestamp(),
        "inputs": {
            "text_review_csv": file_descriptor(text_review_path),
            "pdf_file_lookup_review_csv": file_descriptor(pdf_review_path),
            "official_denominator_registry": file_descriptor(OFFICIAL_DENOMINATOR_REGISTRY)
            if OFFICIAL_DENOMINATOR_REGISTRY.exists()
            else None,
        },
        "input_columns": {
            "text": list(text_columns),
            "pdf": list(pdf_columns),
        },
        "output_files": output_files,
        "report_files": report_files,
        "text_cleanup": reportable_cleanup(text_cleanup),
        "pdf_cleanup": reportable_cleanup(pdf_cleanup),
        "gold_frozen": gold_frozen,
        "silver": {
            "row_counts": {
                "silver_text_positive_train": len(silver["text_positive"]),
                "silver_text_hard_negative_train": len(silver["text_hard_negative"]),
                "silver_text_abstain_diagnostic": len(silver["text_abstain"]),
                "silver_pdf_file_lookup_positive_train": len(silver["pdf_positive"]),
                "silver_pdf_file_lookup_hard_negative_train": len(silver["pdf_hard_negative"]),
                "silver_manifest": len(silver["manifest"]),
            },
            "leakage": silver["leakage"],
            "sources": silver["sources"],
        },
        "tuning_readiness": tuning_readiness_summary(),
    }
    return context


def write_reports(report_dir: Path, context: Mapping[str, Any]) -> None:
    write_text(report_dir / REPORT_FILES["gold_cleanup_report"], render_gold_cleanup_report(context))
    write_text(report_dir / REPORT_FILES["silver_generation_report"], render_silver_generation_report(context))
    write_json(report_dir / REPORT_FILES["denominator_manifest"], context)
    write_text(report_dir / REPORT_FILES["tuning_readiness_report"], render_tuning_readiness_report(context))


def append_progress_logs(context: Mapping[str, Any]) -> None:
    today = datetime.now(timezone.utc).date().isoformat()
    heading = f"## {today} - Reviewed TEXT/PDF gold cleanup and silver generation"
    entry = [
        "",
        heading,
        "",
        "- Status: `completed_diagnostic_candidate_freeze`.",
        "- Scope: cleaned human-reviewed TEXT v2 labels, cleaned PDF FILE lookup companion labels, froze denominator candidates, generated tuning-only silver sets.",
        "- Evidence: "
        f"`{context['report_files']['gold_cleanup_report']}`, "
        f"`{context['report_files']['silver_generation_report']}`, "
        f"`{context['report_files']['denominator_manifest']}`.",
        "- Counts: "
        f"TEXT main candidates `{context['gold_frozen']['denominator_candidates']['text_main_positive_candidate_count']}`, "
        f"TEXT abstain diagnostics `{context['gold_frozen']['denominator_candidates']['text_abstain_diagnostic_count']}`, "
        f"PDF FILE lookup candidates `{context['gold_frozen']['denominator_candidates']['pdf_file_lookup_candidate_count']}`, "
        f"silver manifest rows `{context['silver']['row_counts']['silver_manifest']}`.",
        "- Policies: official denominator registry unchanged; PDF FILE lookup is file identity only; no page/bbox/table/row/column/value success claimed.",
        "- Known exclusions: label conflicts, missing required overrides, `NEEDS_SECOND_REVIEW`, source `needs_review`, TEXT abstain diagnostics, and weak/mixed PDF FILE lookup rows stay out of main positive denominators.",
        f"- Verification: silver leakage status `{context['silver']['leakage']['status']}` with exact gold query/id/source/expected-id overlaps all zero.",
        f"- Next: {context['tuning_readiness']['recommended_next_step']}",
        "",
    ]
    upsert_markdown_section(PROGRESS_LOG, heading, "\n".join(entry))
    upsert_markdown_section(TRACK_B_PROGRESS_LOG, heading, "\n".join(entry))


def render_gold_cleanup_report(context: Mapping[str, Any]) -> str:
    text = context["text_cleanup"]
    pdf = context["pdf_cleanup"]
    lines = [
        "# Reviewed Gold Cleanup Report",
        "",
        "## Status",
        "",
        "- Status: `completed_diagnostic_candidate_freeze`.",
        "- Official denominator registry changed: `false`.",
        "- Promotion evidence: `false`.",
        "- The reviewed input rows were normalized as source-review signals only; Codex did not decide true gold labels.",
        "",
        "## Inputs",
        "",
    ]
    lines.extend(describe_inputs(context))
    lines.extend(
        [
            "",
            "## Outputs",
            "",
        ]
    )
    for key, path in context["output_files"].items():
        if key.startswith("text_gold") or key.startswith("pdf_file_lookup_gold") or "deferred" in key or "diagnostic_clean" in key:
            lines.append(f"- `{key}`: `{path}`")
    lines.extend(
        [
            "",
            "## TEXT Cleanup Counts",
            "",
            f"- Main positive candidates: `{context['gold_frozen']['denominator_candidates']['text_main_positive_candidate_count']}`.",
            f"- Abstain diagnostic rows: `{context['gold_frozen']['denominator_candidates']['text_abstain_diagnostic_count']}`.",
            f"- Deferred or excluded rows: `{context['gold_frozen']['denominator_candidates']['text_deferred_or_excluded_count']}`.",
            f"- Counts by cleanup status: `{text['row_counts_by_cleanup_status']}`.",
            f"- Counts by denominator role: `{text['row_counts_by_denominator_role']}`.",
            f"- Conflicts found: `{len(text['conflict_rows'])}` rows.",
            f"- Missing required overrides: `{len(text['missing_override_rows'])}` rows.",
            f"- Rows deferred for NEEDS_SECOND_REVIEW: `{len(text['needs_second_review_rows'])}` rows.",
            "",
            "## PDF FILE Lookup Cleanup Counts",
            "",
            f"- FILE lookup candidates: `{context['gold_frozen']['denominator_candidates']['pdf_file_lookup_candidate_count']}`.",
            f"- Diagnostic rows: `{context['gold_frozen']['denominator_candidates']['pdf_file_lookup_diagnostic_count']}`.",
            f"- Deferred or excluded rows: `{context['gold_frozen']['denominator_candidates']['pdf_file_lookup_deferred_or_excluded_count']}`.",
            f"- Counts by cleanup status: `{pdf['row_counts_by_cleanup_status']}`.",
            f"- Counts by denominator role: `{pdf['row_counts_by_denominator_role']}`.",
            f"- Generic filename identity-risk rows: `{len(pdf['generic_filename_rows'])}`.",
            f"- Mixed user-decision rows: `{len(pdf['mixed_decision_rows'])}`.",
            "",
            "## Normalization Rules",
            "",
        ]
    )
    for rule in text["normalization_rules"]:
        lines.append(f"- TEXT: {rule}.")
    for rule in pdf["normalization_rules"]:
        lines.append(f"- PDF FILE lookup: {rule}.")
    lines.extend(
        [
            "",
            "## Deferred Rows",
            "",
            f"- TEXT label conflicts: `{', '.join(text['conflict_rows']) or 'none'}`.",
            f"- TEXT missing overrides: `{', '.join(text['missing_override_rows']) or 'none'}`.",
            f"- TEXT NEEDS_SECOND_REVIEW: `{', '.join(text['needs_second_review_rows']) or 'none'}`.",
            f"- PDF mixed decisions: `{', '.join(pdf['mixed_decision_rows']) or 'none'}`.",
            f"- PDF generic filename risk rows: `{', '.join(pdf['generic_filename_rows']) or 'none'}`.",
            "",
            "## PDF FILE Lookup Guardrails",
            "",
            "- Companion rows are FILE lookup only.",
            "- They are not part of the PDF content retrieval denominator.",
            "- Evaluation target is expected file identity only.",
            "- No success is claimed for page, bbox, table, row, column, or value semantics.",
            "- `GENERIC_FILENAME_IDENTITY_RISK` was added for generic filename rows and weak identity rows were kept diagnostic or deferred.",
            "",
            "## Recommended Next Command",
            "",
            "```powershell",
            "python ai/scripts/rag_reviewed_gold_cleanup_and_silver_generation.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def render_silver_generation_report(context: Mapping[str, Any]) -> str:
    silver = context["silver"]
    lines = [
        "# Silver Generation Report",
        "",
        "## Status",
        "",
        "- Status: `silver_generated_tuning_only`.",
        "- Gold eval rows were excluded from silver training by query id, query text, source query id, and expected id checks.",
        "- Official gold: `false` for every silver row.",
        "",
        "## Outputs",
        "",
    ]
    for key, path in context["output_files"].items():
        if key.startswith("silver_"):
            lines.append(f"- `{key}`: `{path}`")
    lines.extend(
        [
            "",
            "## Row Counts",
            "",
        ]
    )
    for key, value in silver["row_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Silver Leakage Checks",
            "",
            f"- Status: `{silver['leakage']['status']}`.",
            f"- Exact query-id overlaps: `{silver['leakage']['query_id_overlap_count']}`.",
            f"- Exact query text overlaps: `{silver['leakage']['query_text_overlap_count']}`.",
            f"- Source query-id overlaps: `{silver['leakage']['source_query_id_overlap_count']}`.",
            f"- Expected-id overlaps: `{silver['leakage']['expected_id_overlap_count']}`.",
            f"- Duplicate silver queries: `{silver['leakage']['duplicate_silver_query_count']}`.",
            "",
            "## Gold/Silver Separation Proof",
            "",
            "- The frozen gold candidate keys were collected from cleaned TEXT main positive rows and PDF FILE lookup positive rows.",
            "- TEXT silver positives come from Phase 7 manual-curated silver rows only when expected document/chunk ids do not overlap frozen gold ids and evidence is found in the referenced chunk.",
            "- TEXT hard negatives reuse query surfaces only against wrong ids and remain `TUNING_ONLY`.",
            "- PDF FILE lookup silver rows use expected file identity only and exclude frozen gold source query ids and query text.",
            "",
            "## PDF FILE Lookup Guardrails",
            "",
            "- `retrieval_lane=pdf_file_lookup` on PDF silver rows.",
            "- `expected_evidence_policy=EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY`.",
            "- No page, bbox, table, row, column, or value semantics are used or claimed.",
            "",
            "## Recommended Next Command",
            "",
            "```powershell",
            "python ai/scripts/rag_reviewed_gold_cleanup_and_silver_generation.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def render_tuning_readiness_report(context: Mapping[str, Any]) -> str:
    readiness = context["tuning_readiness"]
    lines = [
        "# Tuning Readiness Report",
        "",
        "## Status",
        "",
        f"- Status: `{readiness['status']}`.",
        f"- Expensive tuning run: `{str(readiness['expensive_tuning_run']).lower()}`.",
        f"- Standard command found: `{str(readiness['standard_command_found']).lower()}`.",
        f"- Active tuning sweep allowed: `{str(readiness['active_tuning_sweep_allowed']).lower()}`.",
        f"- Recommended next step: {readiness['recommended_next_step']}",
        "",
        "## Inputs",
        "",
    ]
    lines.extend(describe_inputs(context))
    lines.extend(
        [
            "",
            "## Output Files",
            "",
        ]
    )
    for key, path in context["output_files"].items():
        lines.append(f"- `{key}`: `{path}`")
    lines.extend(
        [
            "",
            "## Denominator Policies",
            "",
            "- Official denominator registry was not updated.",
            "- Cleaned TEXT/PDF outputs are candidate or diagnostic artifacts, not automatic official gold.",
            "- Silver rows are tuning-only and `official_gold=false`.",
            "- PDF FILE lookup remains separate from PDF content retrieval.",
            "",
            "## Next Tuning Entry Point",
            "",
        ]
    )
    if readiness["standard_command_found"]:
        lines.extend(
            [
                "A standard tuning command exists, but the active config blocks tuning sweeps by default.",
                "",
                "```powershell",
                readiness["standard_command"],
                "```",
            ]
        )
    else:
        lines.append("No standard strict silver tuning command for this mixed reviewed TEXT/PDF FILE lookup set was found.")
    lines.append("")
    return "\n".join(lines)


def describe_inputs(context: Mapping[str, Any]) -> list[str]:
    lines = []
    for name, descriptor in context["inputs"].items():
        if descriptor is None:
            lines.append(f"- `{name}`: `missing`")
            continue
        lines.append(
            f"- `{name}`: `{descriptor['path']}` (`sha256={descriptor['sha256']}`, `bytes={descriptor['bytes']}`)."
        )
    return lines


def tuning_readiness_summary() -> dict[str, Any]:
    active_yaml = AI_WORKER_ROOT / "eval" / "experiments" / "active.yaml"
    phase7_tune = AI_WORKER_ROOT / "scripts" / "phase7_human_gold_tune.py"
    standard_command_found = phase7_tune.exists()
    active_tuning_sweep_allowed = False
    disabled_reason = "no active.yaml found"
    if active_yaml.exists():
        text = active_yaml.read_text(encoding="utf-8")
        if re.search(r"allow_tuning_sweep:\s*false", text):
            disabled_reason = "_meta.execution_policy.allow_tuning_sweep=false"
        else:
            active_tuning_sweep_allowed = True
            disabled_reason = ""
    return {
        "status": "READY_FOR_DOCUMENTED_SILVER_ONLY_TUNING_STEP" if standard_command_found else "NO_STANDARD_COMMAND_FOUND",
        "expensive_tuning_run": False,
        "standard_command_found": standard_command_found,
        "standard_command": "python scripts\\phase7_human_gold_tune.py --help" if standard_command_found else "",
        "active_tuning_sweep_allowed": active_tuning_sweep_allowed,
        "disabled_reason": disabled_reason,
        "recommended_next_step": (
            "review the generated silver manifest, then create an explicit silver-only tuning config before running "
            "`python scripts\\phase7_human_gold_tune.py`; evaluate only on frozen cleaned gold candidates after that."
        ),
    }


def build_frozen_gold_keys(text_cleanup: Mapping[str, Any], pdf_cleanup: Mapping[str, Any]) -> dict[str, set[str]]:
    rows: list[Mapping[str, str]] = []
    rows.extend(text_cleanup["main_positive"])
    rows.extend(pdf_cleanup["positive"])
    query_ids = {clean(row.get("query_id")) for row in rows if clean(row.get("query_id"))}
    queries = {clean(row.get("query")) for row in rows if clean(row.get("query"))}
    source_query_ids = {clean(row.get("source_query_id")) for row in rows if clean(row.get("source_query_id"))}
    expected_ids: set[str] = set()
    for row in rows:
        for column in [*TEXT_ID_COLUMNS, "expected_file_name", "source_file_name", "expected_document_version_id"]:
            expected_ids.update(split_ids(row.get(column)))
    return {
        "query_ids": query_ids,
        "queries": queries,
        "source_query_ids": source_query_ids,
        "expected_ids": {value for value in expected_ids if value},
    }


def run_silver_leakage_checks(rows: list[dict[str, str]], frozen: Mapping[str, set[str]]) -> dict[str, Any]:
    frozen_source_ids = frozen["query_ids"] | frozen["source_query_ids"]
    query_id_overlaps = sorted({row["query_id"] for row in rows if row.get("query_id") in frozen["query_ids"]})
    query_overlaps = sorted({row["query"] for row in rows if row.get("query") in frozen["queries"]})
    source_query_overlaps = sorted(
        {row["source_query_id"] for row in rows if clean(row.get("source_query_id")) in frozen_source_ids}
    )
    expected_id_overlaps = sorted(
        {
            expected_id
            for row in rows
            for column in leakage_expected_identity_columns(row)
            for expected_id in split_ids(row.get(column))
            if expected_id in frozen["expected_ids"]
        }
    )
    duplicate_queries = [
        query for query, count in Counter(clean(row.get("query")) for row in rows if clean(row.get("query"))).items() if count > 1
    ]
    status = (
        "PASS"
        if not query_id_overlaps and not query_overlaps and not source_query_overlaps and not expected_id_overlaps
        else "FAIL"
    )
    return {
        "status": status,
        "query_id_overlap_count": len(query_id_overlaps),
        "query_id_overlaps": query_id_overlaps[:50],
        "query_text_overlap_count": len(query_overlaps),
        "query_text_overlaps": query_overlaps[:50],
        "source_query_id_overlap_count": len(source_query_overlaps),
        "source_query_id_overlaps": source_query_overlaps[:50],
        "expected_id_overlap_count": len(expected_id_overlaps),
        "expected_id_overlaps": expected_id_overlaps[:50],
        "duplicate_silver_query_count": len(duplicate_queries),
        "duplicate_silver_queries": duplicate_queries[:50],
        "duplicate_silver_query_policy": "allowed for deliberate positive/hard-negative training pairs",
    }


def leakage_expected_identity_columns(row: Mapping[str, str]) -> list[str]:
    columns = []
    for column in row:
        if column in {"expected_evidence_policy", "generation_reason", "negative_strategy"}:
            continue
        if column == "source_file_name":
            columns.append(column)
            continue
        if "expected_" in column and (
            column.endswith("_ids")
            or column.endswith("_id")
            or column.endswith("_name")
            or column.endswith("_version_id")
            or column in {"expected_file_name"}
        ):
            columns.append(column)
    return columns


def build_silver_manifest(
    *,
    silver_text_positive: list[dict[str, str]],
    silver_text_hard_negative: list[dict[str, str]],
    silver_text_abstain: list[dict[str, str]],
    silver_pdf_positive: list[dict[str, str]],
    silver_pdf_hard_negative: list[dict[str, str]],
    leakage: Mapping[str, Any],
) -> list[dict[str, str]]:
    manifest_specs = [
        (SILVER_TEXT_POSITIVE, silver_text_positive, "text_positive"),
        (SILVER_TEXT_HARD_NEGATIVE, silver_text_hard_negative, "text_hard_negative"),
        (SILVER_TEXT_ABSTAIN, silver_text_abstain, "text_abstain_diagnostic"),
        (SILVER_PDF_POSITIVE, silver_pdf_positive, "pdf_file_lookup_positive"),
        (SILVER_PDF_HARD_NEGATIVE, silver_pdf_hard_negative, "pdf_file_lookup_hard_negative"),
    ]
    return [
        {
            "file_name": file_name,
            "row_count": str(len(rows)),
            "lane": lane,
            "official_gold": "false",
            "denominator_role": "TUNING_ONLY",
            "leakage_check_status": leakage["status"],
            "notes": "generated after gold cleanup; excludes frozen gold query ids, text, source ids, and expected ids",
        }
        for file_name, rows, lane in manifest_specs
    ]


def build_pdf_candidate_pool(pdf_rows: list[dict[str, str]], pdf_merged_path: Path) -> list[dict[str, str]]:
    pool = [normalize_row_values(row) for row in pdf_rows]
    if pdf_merged_path.exists():
        merged, _ = read_csv(pdf_merged_path)
        for row in merged:
            norm = normalize_row_values(row)
            if norm.get("expected_file_name") or norm.get("source_file_name"):
                pool.append(norm)
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for row in pool:
        key = (clean(row.get("expected_file_name") or row.get("source_file_name")), clean(row.get("expected_document_version_id")))
        if key[0]:
            unique.setdefault(key, row)
    return list(unique.values())


def choose_wrong_pdf_file(
    positive: Mapping[str, str],
    pool: list[dict[str, str]],
    frozen: Mapping[str, set[str]],
) -> dict[str, str] | None:
    expected_file = clean(positive.get("expected_file_name"))
    generic = generic_filename_family(expected_file)
    candidates = []
    for row in pool:
        wrong_file = clean(row.get("expected_file_name") or row.get("source_file_name"))
        if not wrong_file or wrong_file == expected_file or wrong_file in frozen["expected_ids"]:
            continue
        score = 0
        if generic and generic == generic_filename_family(wrong_file):
            score += 3
        if shared_file_tokens(expected_file, wrong_file):
            score += 2
        if same_year_token(expected_file, wrong_file):
            score += 1
        candidates.append((score, wrong_file, row))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2] if candidates else None


def choose_wrong_text_anchor(
    source_row: Mapping[str, Any],
    phase7_rows: list[dict[str, Any]],
    source_by_doc: Mapping[str, list[dict[str, Any]]],
    frozen: Mapping[str, set[str]],
) -> dict[str, Any] | None:
    doc_id = clean(source_row.get("expected_doc_id"))
    source_sections = set(path_values(source_row.get("expected_section_path")))
    same_doc = [
        row
        for row in source_by_doc.get(doc_id, [])
        if clean(row.get("query_id")) != clean(source_row.get("query_id"))
        and set(path_values(row.get("expected_section_path"))) != source_sections
    ]
    for row in same_doc:
        if text_row_eligible_as_wrong(row, frozen):
            return row
    candidates = [
        row
        for row in phase7_rows
        if row is not source_row
        and clean(row.get("expected_doc_id")) != doc_id
        and title_similarity(clean(source_row.get("expected_title")), clean(row.get("expected_title"))) > 0
        and text_row_eligible_as_wrong(row, frozen)
    ]
    candidates.sort(
        key=lambda row: (
            -title_similarity(clean(source_row.get("expected_title")), clean(row.get("expected_title"))),
            clean(row.get("query_id")),
        )
    )
    return candidates[0] if candidates else None


def text_row_eligible_as_wrong(row: Mapping[str, Any], frozen: Mapping[str, set[str]]) -> bool:
    doc_id = clean(row.get("expected_doc_id"))
    if not doc_id or doc_id in frozen["expected_ids"]:
        return False
    for chunk_id in row.get("expected_chunk_ids", []):
        if clean(chunk_id) in frozen["expected_ids"]:
            return False
    return True


def negative_strategy(source_row: Mapping[str, Any], wrong: Mapping[str, Any]) -> str:
    if clean(source_row.get("expected_doc_id")) == clean(wrong.get("expected_doc_id")):
        return "same_entity_or_page_title_different_section"
    if title_similarity(clean(source_row.get("expected_title")), clean(wrong.get("expected_title"))) > 0:
        return "similar_title_wrong_document_id"
    return "high_lexical_overlap_wrong_expected_ids"


def pdf_negative_strategy(positive: Mapping[str, str], wrong: Mapping[str, str]) -> str:
    expected_file = clean(positive.get("expected_file_name"))
    wrong_file = clean(wrong.get("expected_file_name") or wrong.get("source_file_name"))
    if generic_filename_family(expected_file) and generic_filename_family(expected_file) == generic_filename_family(wrong_file):
        return "same_generic_filename_pattern_wrong_identity"
    if same_year_token(expected_file, wrong_file):
        return "same_metadata_family_wrong_file_identity"
    return "similar_file_name_wrong_identity"


def phase7_evidence_verified(row: Mapping[str, Any], chunks_by_id: Mapping[str, Mapping[str, Any]]) -> bool:
    evidence = clean(row.get("source_evidence"))
    if not evidence:
        return False
    snippet = normalize_whitespace(evidence[:80])
    if not snippet:
        return False
    for chunk_id in row.get("expected_chunk_ids", []):
        chunk = chunks_by_id.get(clean(chunk_id))
        if not chunk:
            continue
        if snippet in normalize_whitespace(clean(chunk.get("chunk_text"))):
            return True
    return False


def text_quote_verified(row: Mapping[str, str], chunks_by_id: Mapping[str, Mapping[str, Any]]) -> bool:
    quote = normalize_whitespace(clean(row.get("source_evidence_quote")))
    if not quote:
        return False
    for chunk_id in split_ids(row.get("expected_chunk_ids")):
        chunk = chunks_by_id.get(chunk_id)
        if chunk and quote in normalize_whitespace(clean(chunk.get("chunk_text"))):
            return True
    return False


def load_chunks_by_id(path: Path) -> dict[str, dict[str, Any]]:
    chunks: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            chunk_id = clean(row.get("chunk_id"))
            if chunk_id:
                chunks[chunk_id] = row
    return chunks


def detect_provenance_changes(rows: list[dict[str, str]]) -> dict[str, Any]:
    changed_rows: list[str] = []
    for row in rows:
        original = row
        normalized = normalize_row_values(row)
        for column in row:
            if column in TEXT_PROVENANCE_COLUMNS or column.startswith("source_"):
                if clean(original.get(column)) != normalized.get(column, ""):
                    changed_rows.append(clean(row.get("query_id")) or "<unknown>")
                    break
    return {
        "status": "PASSED",
        "changed_provenance_row_count": len(set(changed_rows)),
        "changed_provenance_rows": sorted(set(changed_rows)),
        "note": "normalization used in-memory views only; provenance output values are copied from source after trimming",
    }


def explain_text_decision(row: Mapping[str, str], issue_tags: Sequence[str]) -> str:
    if row["denominator_role"] == "TEXT_MAIN_POSITIVE_GOLD_CANDIDATE":
        return "Strict reviewed positive candidate; official registry still unchanged."
    if row["denominator_role"] == "TEXT_ABSTAIN_DIAGNOSTIC":
        return "Abstain/diagnostic default kept out of main positive denominator."
    if issue_tags:
        return "Deferred or excluded because " + ", ".join(issue_tags) + "."
    return "Excluded by conservative non-gold policy."


def explain_pdf_decision(row: Mapping[str, str], issue_tags: Sequence[str]) -> str:
    if row["denominator_role"] == "PDF_FILE_LOOKUP_GOLD_CANDIDATE":
        return "Clear reviewed FILE lookup candidate; file identity only, registry unchanged."
    if "GENERIC_FILENAME_IDENTITY_RISK" in issue_tags:
        return "Generic filename identity risk kept out of high-confidence positive unless strict positive criteria also hold."
    if issue_tags:
        return "Diagnostic/deferred because " + ", ".join(issue_tags) + "."
    return "Diagnostic FILE lookup row; no content/page/table semantics claimed."


def normalize_row_values(row: Mapping[str, Any]) -> dict[str, str]:
    return {str(key): clean(value) for key, value in row.items()}


def has_answerability_conflict(values: Sequence[str]) -> bool:
    labels = [value for value in values if value in TEXT_ALLOWED_ANSWERABILITY]
    non_labels = [value for value in values if value and value not in TEXT_ALLOWED_ANSWERABILITY]
    if len(set(labels)) > 1:
        return True
    if labels and non_labels:
        return True
    return False


def split_multi_value(value: Any) -> list[str]:
    text = clean(value)
    if not text:
        return []
    parts = [clean(part) for part in re.split(r"[,;|]", text) if clean(part)]
    return parts or [text]


def split_tags(value: Any) -> list[str]:
    return [clean(part) for part in re.split(r"[,;|]", clean(value)) if clean(part)]


def split_ids(value: Any) -> list[str]:
    text = clean(value)
    if not text:
        return []
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    return [clean(part) for part in re.split(r"[|;]", text) if clean(part)]


def join_tags(values: Iterable[str]) -> str:
    return ";".join(sorted({clean(value) for value in values if clean(value)}))


def join_ids(values: Iterable[Any]) -> str:
    return "|".join(clean(value) for value in values if clean(value))


def join_path(value: Any) -> str:
    if isinstance(value, list):
        return " > ".join(clean(item) for item in value if clean(item))
    return clean(value)


def path_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    return [clean(part) for part in re.split(r">\s*|[|;]", clean(value)) if clean(part)]


def title_similarity(left: str, right: str) -> int:
    left_tokens = set(re.findall(r"[\w가-힣]+", left.lower()))
    right_tokens = set(re.findall(r"[\w가-힣]+", right.lower()))
    return len(left_tokens & right_tokens)


def generic_filename_family(file_name: str) -> str:
    text = clean(file_name).lower()
    if re.fullmatch(r"file(?: \(\d+\))?\.pdf", text):
        return "generic_file_pdf"
    return ""


def shared_file_tokens(left: str, right: str) -> bool:
    left_tokens = set(re.findall(r"\d{4}|\d{8}|[가-힣]+|[a-z]+", left.lower()))
    right_tokens = set(re.findall(r"\d{4}|\d{8}|[가-힣]+|[a-z]+", right.lower()))
    return bool(left_tokens & right_tokens)


def same_year_token(left: str, right: str) -> bool:
    return bool(set(re.findall(r"20\d{2}", left)) & set(re.findall(r"20\d{2}", right)))


def derive_pdf_file_lookup_silver_query(row: Mapping[str, str], index: int) -> str:
    source_query = clean(row.get("query"))
    if source_query and clean(row.get("query_id")) not in source_query:
        return f"파일 목록 확인용 자료 {index:03d} 찾아줘"
    return f"파일 식별 후보 자료 {index:03d} 찾아줘"


def pdf_file_query_hint(file_name: str) -> str:
    text = clean(file_name)
    year = re.search(r"20\d{2}", text)
    month = re.search(r"(?:20\d{2})(?:년도)?[+_-]?(\d{1,2})", text)
    if "주택용고압" in text or "high" in text.lower():
        family = "주택용 고압 전기요금표"
    elif "주택용저압" in text or "low" in text.lower() or "law" in text.lower():
        family = "주택용 저압 전기요금표"
    elif "종합" in text or "total" in text.lower():
        family = "전기요금 종합표"
    else:
        family = "PDF"
    prefix = year.group(0) if year else "해당"
    if month:
        prefix = f"{prefix}년 {month.group(1)}월"
    return f"{prefix} {family}"


def required_text_columns() -> list[str]:
    return [
        "query_id",
        "bucket",
        "query",
        "expected_answer_text",
        "source_evidence_quote",
        "expected_document_ids",
        "expected_page_ids",
        "expected_section_ids",
        "expected_chunk_ids",
        "source_locator",
        "candidate_default_policy",
        "source_query_id",
        "source_label_status",
        "user_final_gold_policy",
        "user_answerability_label",
        "user_relevance_label",
        "user_expected_answer_override",
        "user_expected_evidence_override",
        "user_review_notes",
    ]


def required_pdf_columns() -> list[str]:
    return [
        "query_id",
        "retrieval_lane",
        "source_file_name",
        "expected_file_name",
        "expected_document_version_id",
        "query",
        "risk_tags",
        "user_gold_decision",
        "user_answerability_label",
        "user_relevance_label",
        "user_expected_evidence_policy",
        "user_denominator_policy",
        "user_issue_tags",
    ]


def clean_text_fieldnames() -> list[str]:
    return [
        *required_text_columns()[:13],
        "track",
        "expected_page_title",
        "expected_section_path",
        "source_url",
        "chunk_text_sha256",
        "answer_type",
        "allowed_abstain",
        "source_dataset",
        "source_original_gold",
        "generation_notes",
        "user_final_gold_policy",
        "user_answerability_label",
        "user_answerability_label_clean",
        "user_relevance_label",
        "user_expected_answer_override",
        "user_expected_evidence_override",
        "user_review_notes",
        "cleanup_status",
        "denominator_role",
        "official_gold",
        "cleanup_issue_tags",
        "source_evidence_quote_verified_in_expected_chunk",
        "non_obvious_decision",
    ]


def clean_pdf_fieldnames() -> list[str]:
    return [
        "track",
        "query_id",
        "retrieval_lane",
        "retrieval_lane_clean",
        "review_group",
        "source_file_name",
        "expected_file_name",
        "expected_document_version_id",
        "diagnostic_page_no",
        "diagnostic_page_label",
        "diagnostic_bbox",
        "query",
        "diagnostic_evidence_excerpt",
        "review_lane",
        "risk_tags",
        "diagnostic_reason",
        "user_gold_decision",
        "user_answerability_label",
        "user_answerability_label_clean",
        "user_relevance_label",
        "user_expected_evidence_policy",
        "user_expected_evidence_policy_clean",
        "user_denominator_policy",
        "user_denominator_policy_clean",
        "user_issue_tags",
        "user_notes",
        "cleanup_status",
        "denominator_role",
        "official_gold",
        "cleanup_issue_tags",
        "non_obvious_decision",
    ]


def silver_text_positive_fieldnames() -> list[str]:
    return [
        "query_id",
        "source_query_id",
        "query",
        "expected_document_ids",
        "expected_page_ids",
        "expected_section_path",
        "expected_chunk_ids",
        "source_evidence_quote",
        "silver_label",
        "silver_confidence",
        "denominator_role",
        "official_gold",
        "leakage_exclusion_reason",
        "generation_reason",
    ]


def silver_text_hard_negative_fieldnames() -> list[str]:
    return [
        "query_id",
        "source_query_id",
        "query",
        "expected_document_ids",
        "expected_page_ids",
        "expected_section_path",
        "expected_chunk_ids",
        "positive_expected_document_ids",
        "negative_strategy",
        "silver_label",
        "silver_confidence",
        "denominator_role",
        "official_gold",
        "generation_reason",
    ]


def silver_text_abstain_fieldnames() -> list[str]:
    return [
        "query_id",
        "source_query_id",
        "query",
        "expected_document_ids",
        "expected_page_ids",
        "expected_section_ids",
        "expected_chunk_ids",
        "silver_label",
        "silver_confidence",
        "denominator_role",
        "official_gold",
        "generation_reason",
    ]


def silver_pdf_positive_fieldnames() -> list[str]:
    return [
        "query_id",
        "source_query_id",
        "query",
        "retrieval_lane",
        "expected_file_name",
        "source_file_name",
        "expected_document_version_id",
        "expected_evidence_policy",
        "silver_label",
        "silver_confidence",
        "denominator_role",
        "official_gold",
        "generation_reason",
    ]


def silver_pdf_hard_negative_fieldnames() -> list[str]:
    return [
        "query_id",
        "source_query_id",
        "query",
        "retrieval_lane",
        "expected_file_name",
        "source_file_name",
        "expected_document_version_id",
        "positive_expected_file_name",
        "expected_evidence_policy",
        "negative_strategy",
        "silver_label",
        "silver_confidence",
        "denominator_role",
        "official_gold",
        "generation_reason",
    ]


def silver_manifest_fieldnames() -> list[str]:
    return [
        "file_name",
        "row_count",
        "lane",
        "official_gold",
        "denominator_role",
        "leakage_check_status",
        "notes",
    ]


def reportable_cleanup(cleanup: Mapping[str, Any]) -> dict[str, Any]:
    result = {}
    for key, value in cleanup.items():
        if key == "rows":
            result["input_row_count"] = len(value)
        elif key in {"main_positive", "abstain_diagnostic", "deferred_or_excluded", "positive", "diagnostic"}:
            result[f"{key}_count"] = len(value)
        elif key == "decisions":
            continue
        else:
            result[key] = value
    return result


def file_descriptor(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": rel(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
        return rows, list(reader.fieldnames or [])


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_csv(path: Path, rows: list[dict[str, str]], *, fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_markdown_section(path: Path, heading: str, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    pattern = re.compile(rf"\n?{re.escape(heading)}\n.*?(?=\n## |\Z)", re.DOTALL)
    replacement = "\n\n" + text.strip() + "\n"
    if pattern.search(existing):
        updated = pattern.sub(lambda _match: replacement.rstrip(), existing).rstrip() + "\n"
    else:
        updated = existing.rstrip() + replacement
    path.write_text(updated, encoding="utf-8")


def clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "|".join(clean(item) for item in value if clean(item))
    return str(value).strip()


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", clean(value))


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
