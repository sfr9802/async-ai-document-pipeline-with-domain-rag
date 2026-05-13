"""Normalize reviewed TEXT/XLSX/PDF gold policy packs without running retrieval.

This script ingests human-reviewed CSV packs that already live under
``ai/eval/review`` and turns their review labels into conservative
policy buckets. It writes a canonical report only; it does not update the
official denominator registry, create namespaces, index data, or run recall
variants.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"
TEXT_REVIEW_CSV = (
    AI_WORKER_ROOT
    / "eval"
    / "review"
    / "text_namu_v2_gold_review"
    / "text_namu_v2_gold_review_pack - text_namu_v2_gold_review_pack.csv"
)
PDF_REVIEW_CSV = (
    AI_WORKER_ROOT
    / "eval"
    / "review"
    / "pdf_supplemental_gold_review"
    / "pdf_gold_review_pack_manual_v1_file_lookup_companion - "
    "pdf_gold_review_pack_manual_v1_file_lookup_companion.csv"
)
XLSX_REVIEW_CSV = (
    AI_WORKER_ROOT
    / "eval"
    / "review"
    / "xlsx"
    / "제목 없는 스프레드시트 - xlsx_gold_human_review_pack (1).csv"
)
OFFICIAL_DENOMINATOR_REGISTRY = AI_WORKER_ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"
DEFAULT_JSON_REPORT = REPORT_DIR / "rag_reviewed_gold_policy_normalization_report.json"
DEFAULT_MD_REPORT = REPORT_DIR / "rag_reviewed_gold_policy_normalization_report.md"

SCHEMA_VERSION = "reviewed_gold_policy_normalization_v1"

TEXT_REQUIRED_COLUMNS = [
    "query_id",
    "track",
    "bucket",
    "query",
    "expected_answer_text",
    "source_label_status",
    "candidate_default_policy",
    "user_final_gold_policy",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_answer_override",
    "user_expected_evidence_override",
    "user_review_notes",
]
XLSX_REQUIRED_COLUMNS = [
    "query_id",
    "query",
    "track",
    "sheet",
    "range",
    "citation_locator",
    "user_answerability_label",
    "user_relevance_label",
    "user_gold_answer_shape",
    "user_required_citation_policy",
    "user_gold_policy_decision",
    "user_include_in_official_denominator",
    "user_review_notes",
]
PDF_REQUIRED_COLUMNS = [
    "track",
    "query_id",
    "retrieval_lane",
    "review_lane",
    "risk_tags",
    "user_gold_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_evidence_policy",
    "user_denominator_policy",
    "user_issue_tags",
    "user_notes",
]

TEXT_EXPECTED_ROWS = 100
XLSX_EXPECTED_ROWS = 50
PDF_EXPECTED_ROWS = 28

PROPOSED_OFFICIAL = "PROPOSED_OFFICIAL_CANDIDATE"
DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
SOURCE_VERIFICATION_REQUIRED = "SOURCE_VERIFICATION_REQUIRED"
SOURCE_BINDING_REVIEW_REQUIRED = "SOURCE_BINDING_REVIEW_REQUIRED"
POLICY_EXCLUDED = "POLICY_EXCLUDED"
EVIDENCE_MISMATCH = "EVIDENCE_MISMATCH"
EXPECTED_ANSWER_REVISION = "EXPECTED_ANSWER_REVISION"
EXPECTED_ANSWER_AND_EVIDENCE_REVISION = "EXPECTED_ANSWER_AND_EVIDENCE_REVISION"
EXPECTED_EVIDENCE_REVISION = "EXPECTED_EVIDENCE_REVISION"
NEEDS_SECOND_REVIEW = "NEEDS_SECOND_REVIEW"
AMBIGUOUS_QUERY = "AMBIGUOUS_QUERY"
INVALID_QUERY = "INVALID_QUERY"
EVIDENCE_TOO_BROAD = "EVIDENCE_TOO_BROAD"
CONTENT_EVIDENCE_POSITIVE = "CONTENT_EVIDENCE_POSITIVE"
FILE_LOOKUP_IDENTITY_CANDIDATE = "FILE_LOOKUP_IDENTITY_CANDIDATE"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        text_path=Path(args.text_review_csv),
        xlsx_path=Path(args.xlsx_review_csv),
        pdf_path=Path(args.pdf_review_csv),
        registry_path=Path(args.official_denominator_registry),
    )
    write_json(Path(args.report_json), report)
    Path(args.report_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_md).write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "report_json": repo_relative(Path(args.report_json)),
                "report_md": repo_relative(Path(args.report_md)),
                "text_proposed_official_candidates": report["tracks"]["text_namu_v2"][
                    "proposed_official_candidate_count"
                ],
                "xlsx_proposed_official_candidates": report["tracks"]["xlsx_human_review"][
                    "proposed_official_candidate_count"
                ],
                "xlsx_official_denominator_frozen": report["tracks"]["xlsx_human_review"][
                    "official_denominator_frozen_count"
                ],
                "pdf_content_evidence_positive": report["tracks"]["pdf_file_lookup_companion"][
                    "content_evidence_positive_count"
                ],
                "pdf_file_lookup_identity_candidates": report["tracks"]["pdf_file_lookup_companion"][
                    "file_lookup_identity_candidate_count"
                ],
                "official_denominator_registry_changed": report["guardrails"][
                    "official_denominator_registry_changed"
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-review-csv", default=str(TEXT_REVIEW_CSV))
    parser.add_argument("--xlsx-review-csv", default=str(XLSX_REVIEW_CSV))
    parser.add_argument("--pdf-review-csv", default=str(PDF_REVIEW_CSV))
    parser.add_argument("--official-denominator-registry", default=str(OFFICIAL_DENOMINATOR_REGISTRY))
    parser.add_argument("--report-json", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--report-md", default=str(DEFAULT_MD_REPORT))
    return parser.parse_args(argv)


def build_report(*, text_path: Path, xlsx_path: Path, pdf_path: Path, registry_path: Path) -> dict[str, Any]:
    registry_sha_before = sha256_file(registry_path) if registry_path.exists() else ""
    text_rows = read_csv_rows(text_path)
    xlsx_rows = read_csv_rows(xlsx_path)
    pdf_rows = read_csv_rows(pdf_path)

    validation = {
        "text_namu_v2": validate_pack(
            rows=text_rows,
            columns=TEXT_REQUIRED_COLUMNS,
            expected_row_count=TEXT_EXPECTED_ROWS,
            query_id_column="query_id",
        ),
        "xlsx_human_review": validate_pack(
            rows=xlsx_rows,
            columns=XLSX_REQUIRED_COLUMNS,
            expected_row_count=XLSX_EXPECTED_ROWS,
            query_id_column="query_id",
        ),
        "pdf_file_lookup_companion": validate_pack(
            rows=pdf_rows,
            columns=PDF_REQUIRED_COLUMNS,
            expected_row_count=PDF_EXPECTED_ROWS,
            query_id_column="query_id",
        ),
    }

    text = normalize_text(text_rows)
    xlsx = normalize_xlsx(xlsx_rows)
    pdf = normalize_pdf(pdf_rows)
    cross_track_errors = validate_cross_track_guardrails(text=text, xlsx=xlsx, pdf=pdf)
    registry_sha_after = sha256_file(registry_path) if registry_path.exists() else ""

    status = "PASS"
    if any(item["errors"] for item in validation.values()) or cross_track_errors:
        status = "FAIL"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": utc_timestamp(),
        "source_resolution": {
            "note": (
                "The /mnt/data source paths were not mounted in this Windows workspace; "
                "canonical repo review-pack paths were used. The XLSX repo copy matches "
                "the accessible D:/다운 export by sha256. Raw review packs stay local/ignored; "
                "the committed report records paths, hashes, counts, and normalized policy buckets."
            ),
            "production_namespace_mutated": False,
            "retrieval_variants_run": False,
        },
        "imported_files": {
            "text_namu_v2": input_ref(text_path, TEXT_EXPECTED_ROWS),
            "xlsx_human_review": input_ref(xlsx_path, XLSX_EXPECTED_ROWS),
            "pdf_file_lookup_companion": input_ref(pdf_path, PDF_EXPECTED_ROWS),
        },
        "validation": validation,
        "normalized_label_mapping": normalized_label_mapping(),
        "tracks": {
            "text_namu_v2": text,
            "xlsx_human_review": xlsx,
            "pdf_file_lookup_companion": pdf,
        },
        "guardrails": {
            "official_denominator_registry_path": repo_relative(registry_path),
            "official_denominator_registry_sha256_before": registry_sha_before,
            "official_denominator_registry_sha256_after": registry_sha_after,
            "official_denominator_registry_changed": registry_sha_before != registry_sha_after,
            "official_denominator_opened": False,
            "production_namespace_mutated": False,
            "retrieval_variants_run": False,
            "diagnostic_only_row_promoted": False,
            "not_answerable_or_irrelevant_in_normal_positive_denominator": False,
            "policy_blocked_rows_treated_as_retrieval_failures": False,
            "index_scope_missing_rows_treated_as_ranking_failures": False,
        },
        "cross_track_validation_errors": cross_track_errors,
        "unresolved_user_review_rows": {
            "text_namu_v2": text["unresolved_user_review_rows"],
            "xlsx_human_review": xlsx["unresolved_user_review_rows"],
            "pdf_file_lookup_companion": pdf["unresolved_user_review_rows"],
        },
        "rationale": [
            "Official denominator registry was read for policy context but not mutated.",
            "Rows with diagnostic-only defaults are kept out of proposed official candidates.",
            "TEXT rows with ambiguous, invalid, second-review, or revision markers stay out of proposed official candidates.",
            "XLSX empty user denominator decisions are preserved; proposed candidates are not frozen official denominator rows.",
            "PDF content evidence and file identity lookup are separate lanes and have no aggregate official candidate count.",
            "NOT_ANSWERABLE, IRRELEVANT, POLICY_EXCLUDED, and EVIDENCE_MISMATCH rows are not normal positive denominator rows.",
        ],
    }


def normalize_text(rows: list[dict[str, str]]) -> dict[str, Any]:
    normalized_rows = []
    for row in rows:
        issue_tags = text_issue_tags(row)
        bucket, reason = text_bucket(row, issue_tags)
        normalized_rows.append(row_summary(row, bucket=bucket, issue_tags=issue_tags, reason=reason))

    bucket_counts = Counter(row["normalized_policy_bucket"] for row in normalized_rows)
    issue_buckets = {
        "needs_second_review": ids_matching(rows, lambda row: "NEEDS_SECOND_REVIEW" in split_values(row.get("user_final_gold_policy"))),
        "expected_answer_revision": ids_matching(
            rows, lambda row: clean(row.get("user_final_gold_policy")) == "REVISE_EXPECTED_ANSWER"
        ),
        "expected_answer_and_evidence_revision": ids_matching(
            rows, lambda row: clean(row.get("user_final_gold_policy")) == "REVISE_EXPECTED_ANSWER_AND_EVIDENCE"
        ),
        "ambiguous_query": ids_matching(rows, lambda row: "AMBIGUOUS_QUERY" in split_values(row.get("user_review_notes"))),
        "invalid_query": ids_matching(rows, lambda row: "INVALID_QUERY" in split_values(row.get("user_answerability_label"))),
        "evidence_too_broad": ids_matching(rows, lambda row: "EVIDENCE_TOO_BROAD" in split_values(row.get("user_review_notes"))),
        "diagnostic_only_default": ids_matching(
            rows, lambda row: clean(row.get("candidate_default_policy")) == "DIAGNOSTIC_ONLY_DEFAULT"
        ),
        "source_binding_review_required": [
            row["query_id"]
            for row in rows
            if text_clean_positive(row) and clean(row.get("source_label_status")) == "needs_review"
        ],
    }
    unresolved = [
        row["query_id"]
        for row in normalized_rows
        if row["normalized_policy_bucket"]
        in {
            NEEDS_SECOND_REVIEW,
            EXPECTED_ANSWER_REVISION,
            EXPECTED_ANSWER_AND_EVIDENCE_REVISION,
            AMBIGUOUS_QUERY,
            INVALID_QUERY,
            EVIDENCE_TOO_BROAD,
            SOURCE_BINDING_REVIEW_REQUIRED,
        }
    ]

    return {
        "track": "text_namuwiki_animation",
        "row_count": len(rows),
        "proposed_official_candidate_count": bucket_counts[PROPOSED_OFFICIAL],
        "proposed_official_candidate_query_ids": ids_for_bucket(normalized_rows, PROPOSED_OFFICIAL),
        "diagnostic_only_count": bucket_counts[DIAGNOSTIC_ONLY],
        "diagnostic_only_query_ids": ids_for_bucket(normalized_rows, DIAGNOSTIC_ONLY),
        "policy_excluded_count": bucket_counts[POLICY_EXCLUDED] + bucket_counts[INVALID_QUERY],
        "policy_excluded_query_ids": ids_for_bucket(normalized_rows, POLICY_EXCLUDED)
        + ids_for_bucket(normalized_rows, INVALID_QUERY),
        "source_verification_required_count": bucket_counts[SOURCE_BINDING_REVIEW_REQUIRED],
        "source_verification_required_query_ids": ids_for_bucket(normalized_rows, SOURCE_BINDING_REVIEW_REQUIRED),
        "expected_answer_or_evidence_revision_count": bucket_counts[EXPECTED_ANSWER_REVISION]
        + bucket_counts[EXPECTED_ANSWER_AND_EVIDENCE_REVISION],
        "expected_answer_or_evidence_revision_query_ids": ids_for_bucket(normalized_rows, EXPECTED_ANSWER_REVISION)
        + ids_for_bucket(normalized_rows, EXPECTED_ANSWER_AND_EVIDENCE_REVISION),
        "review_marker_buckets": issue_buckets,
        "normalized_bucket_counts": dict(sorted(bucket_counts.items())),
        "unresolved_user_review_count": len(unresolved),
        "unresolved_user_review_rows": unresolved,
        "rows": normalized_rows,
    }


def text_bucket(row: Mapping[str, str], issue_tags: list[str]) -> tuple[str, str]:
    if clean(row.get("candidate_default_policy")) == "DIAGNOSTIC_ONLY_DEFAULT":
        return DIAGNOSTIC_ONLY, "candidate_default_policy=DIAGNOSTIC_ONLY_DEFAULT"
    if "NEEDS_SECOND_REVIEW" in issue_tags:
        return NEEDS_SECOND_REVIEW, "user_final_gold_policy=NEEDS_SECOND_REVIEW"
    if "REVISE_EXPECTED_ANSWER_AND_EVIDENCE" in issue_tags:
        return EXPECTED_ANSWER_AND_EVIDENCE_REVISION, "expected answer and evidence need revision"
    if "REVISE_EXPECTED_ANSWER" in issue_tags:
        return EXPECTED_ANSWER_REVISION, "expected answer needs revision"
    if "INVALID_QUERY" in issue_tags:
        return INVALID_QUERY, "user label contains INVALID_QUERY"
    if "EVIDENCE_TOO_BROAD" in issue_tags:
        return EVIDENCE_TOO_BROAD, "user review notes mark evidence too broad"
    if "AMBIGUOUS_QUERY" in issue_tags:
        return AMBIGUOUS_QUERY, "user review notes mark ambiguous query"
    if text_clean_positive(row):
        if clean(row.get("source_label_status")) == "needs_review":
            return SOURCE_BINDING_REVIEW_REQUIRED, "clean user policy but source_label_status=needs_review"
        return PROPOSED_OFFICIAL, "clean official-review candidate under TEXT policy"
    return POLICY_EXCLUDED, "not clean positive under conservative TEXT policy"


def text_clean_positive(row: Mapping[str, str]) -> bool:
    return (
        clean(row.get("candidate_default_policy")) == "OFFICIAL_REVIEW_CANDIDATE"
        and clean(row.get("user_final_gold_policy")) == "KEEP_POSITIVE"
        and clean(row.get("user_answerability_label")) == "ANSWERABLE"
        and clean(row.get("user_relevance_label")) == "RELEVANT"
        and not clean(row.get("user_review_notes"))
    )


def text_issue_tags(row: Mapping[str, str]) -> list[str]:
    tags: list[str] = []
    final_policy_values = split_values(row.get("user_final_gold_policy"))
    answerability_values = split_values(row.get("user_answerability_label"))
    review_note_values = split_values(row.get("user_review_notes"))
    for tag in [
        "NEEDS_SECOND_REVIEW",
        "REVISE_EXPECTED_ANSWER_AND_EVIDENCE",
        "REVISE_EXPECTED_ANSWER",
    ]:
        if tag in final_policy_values:
            tags.append(tag)
    for tag in ["INVALID_QUERY", "AMBIGUOUS_QUERY", "EVIDENCE_TOO_BROAD"]:
        if tag in answerability_values or tag in review_note_values or tag in final_policy_values:
            tags.append(tag)
    if clean(row.get("candidate_default_policy")) == "DIAGNOSTIC_ONLY_DEFAULT":
        tags.append("DIAGNOSTIC_ONLY_DEFAULT")
    if clean(row.get("source_label_status")) == "needs_review":
        tags.append("SOURCE_LABEL_STATUS_NEEDS_REVIEW")
    return dedupe(tags)


def normalize_xlsx(rows: list[dict[str, str]]) -> dict[str, Any]:
    normalized_rows = []
    user_decision_nonblank = []
    user_denominator_nonblank = []
    for row in rows:
        if clean(row.get("user_gold_policy_decision")):
            user_decision_nonblank.append(clean(row.get("query_id")))
        if clean(row.get("user_include_in_official_denominator")):
            user_denominator_nonblank.append(clean(row.get("query_id")))
        bucket, reason = xlsx_bucket(row)
        normalized_rows.append(row_summary(row, bucket=bucket, issue_tags=xlsx_issue_tags(row), reason=reason))

    bucket_counts = Counter(row["normalized_policy_bucket"] for row in normalized_rows)
    denominator_confirmation = ids_for_bucket(normalized_rows, PROPOSED_OFFICIAL)
    source_verification = ids_for_bucket(normalized_rows, SOURCE_VERIFICATION_REQUIRED)
    unresolved = [*denominator_confirmation, *source_verification]
    return {
        "track": "xlsx_business_structured",
        "row_count": len(rows),
        "proposed_official_candidate_count": bucket_counts[PROPOSED_OFFICIAL],
        "proposed_official_candidate_query_ids": ids_for_bucket(normalized_rows, PROPOSED_OFFICIAL),
        "official_denominator_frozen_count": 0,
        "official_denominator_frozen_query_ids": [],
        "denominator_confirmation_required_count": len(denominator_confirmation),
        "denominator_confirmation_required_query_ids": denominator_confirmation,
        "source_verification_required_count": bucket_counts[SOURCE_VERIFICATION_REQUIRED],
        "source_verification_required_query_ids": source_verification,
        "evidence_mismatch_count": bucket_counts[EVIDENCE_MISMATCH],
        "evidence_mismatch_query_ids": ids_for_bucket(normalized_rows, EVIDENCE_MISMATCH),
        "policy_excluded_count": bucket_counts[POLICY_EXCLUDED],
        "policy_excluded_query_ids": ids_for_bucket(normalized_rows, POLICY_EXCLUDED),
        "diagnostic_only_count": bucket_counts[DIAGNOSTIC_ONLY],
        "diagnostic_only_query_ids": ids_for_bucket(normalized_rows, DIAGNOSTIC_ONLY),
        "expected_answer_or_evidence_revision_count": 0,
        "expected_answer_or_evidence_revision_query_ids": [],
        "user_gold_answer_shape_distribution": dict(Counter(clean(row.get("user_gold_answer_shape")) for row in rows)),
        "user_required_citation_policy_distribution": dict(
            Counter(clean(row.get("user_required_citation_policy")) for row in rows)
        ),
        "empty_user_gold_policy_decision_count": len(rows) - len(user_decision_nonblank),
        "empty_user_include_in_official_denominator_count": len(rows) - len(user_denominator_nonblank),
        "nonblank_user_gold_policy_decision_query_ids": user_decision_nonblank,
        "nonblank_user_include_in_official_denominator_query_ids": user_denominator_nonblank,
        "normalized_bucket_counts": dict(sorted(bucket_counts.items())),
        "unresolved_user_review_count": len(unresolved),
        "unresolved_user_review_rows": unresolved,
        "rows": normalized_rows,
    }


def xlsx_bucket(row: Mapping[str, str]) -> tuple[str, str]:
    answerability = clean(row.get("user_answerability_label"))
    relevance = clean(row.get("user_relevance_label"))
    if answerability == "ANSWERABLE_CONFIRMED" and relevance == "EVIDENCE_RELEVANT":
        return PROPOSED_OFFICIAL, "ANSWERABLE_CONFIRMED + EVIDENCE_RELEVANT"
    if answerability == "ANSWERABLE_NEEDS_SOURCE_VERIFICATION" and relevance in {
        "EVIDENCE_PARTIAL",
        "EVIDENCE_RELEVANT",
    }:
        return SOURCE_VERIFICATION_REQUIRED, "answerable but source verification is still required"
    if relevance == "EVIDENCE_MISMATCH":
        return EVIDENCE_MISMATCH, "human label marks evidence mismatch"
    if relevance == "POLICY_EXCLUDED" or answerability == "NOT_ANSWERABLE":
        return POLICY_EXCLUDED, "human label marks policy excluded or not answerable"
    return DIAGNOSTIC_ONLY, "no relaxed XLSX policy for this label combination"


def xlsx_issue_tags(row: Mapping[str, str]) -> list[str]:
    tags: list[str] = []
    for key in ["user_answerability_label", "user_relevance_label"]:
        value = clean(row.get(key))
        if value:
            tags.append(value)
    return tags


def normalize_pdf(rows: list[dict[str, str]]) -> dict[str, Any]:
    normalized_rows = []
    for row in rows:
        bucket, reason = pdf_bucket(row)
        normalized_rows.append(row_summary(row, bucket=bucket, issue_tags=pdf_issue_tags(row), reason=reason))
    bucket_counts = Counter(row["normalized_policy_bucket"] for row in normalized_rows)
    issue_buckets = {
        "not_answerable": ids_matching(rows, lambda row: clean(row.get("user_answerability_label")) == "NOT_ANSWERABLE"),
        "irrelevant": ids_matching(rows, lambda row: clean(row.get("user_relevance_label")) == "IRRELEVANT"),
        "evidence_revision": ids_matching(rows, pdf_requires_evidence_revision),
        "generic_filename_identity_risk": ids_matching(
            rows, lambda row: "GENERIC_FILENAME" in split_values(row.get("risk_tags"))
        ),
    }
    unresolved = ids_for_bucket(normalized_rows, EXPECTED_EVIDENCE_REVISION)
    return {
        "track": "pdf_business_ocr_mm",
        "row_count": len(rows),
        "content_evidence_positive_count": bucket_counts[CONTENT_EVIDENCE_POSITIVE],
        "content_evidence_positive_query_ids": ids_for_bucket(normalized_rows, CONTENT_EVIDENCE_POSITIVE),
        "file_lookup_identity_candidate_count": bucket_counts[FILE_LOOKUP_IDENTITY_CANDIDATE],
        "file_lookup_identity_candidate_query_ids": ids_for_bucket(normalized_rows, FILE_LOOKUP_IDENTITY_CANDIDATE),
        "proposed_content_evidence_candidate_count": bucket_counts[CONTENT_EVIDENCE_POSITIVE],
        "proposed_content_evidence_candidate_query_ids": ids_for_bucket(normalized_rows, CONTENT_EVIDENCE_POSITIVE),
        "proposed_file_lookup_identity_candidate_count": bucket_counts[FILE_LOOKUP_IDENTITY_CANDIDATE],
        "proposed_file_lookup_identity_candidate_query_ids": ids_for_bucket(
            normalized_rows, FILE_LOOKUP_IDENTITY_CANDIDATE
        ),
        "proposed_official_candidate_count": None,
        "proposed_official_candidate_query_ids": [],
        "official_denominator_frozen_count": 0,
        "official_denominator_frozen_query_ids": [],
        "expected_answer_or_evidence_revision_count": bucket_counts[EXPECTED_EVIDENCE_REVISION],
        "expected_answer_or_evidence_revision_query_ids": unresolved,
        "policy_excluded_count": len(set(issue_buckets["not_answerable"]) | set(issue_buckets["irrelevant"])),
        "policy_excluded_query_ids": sorted(set(issue_buckets["not_answerable"]) | set(issue_buckets["irrelevant"])),
        "diagnostic_only_count": bucket_counts[DIAGNOSTIC_ONLY],
        "diagnostic_only_query_ids": ids_for_bucket(normalized_rows, DIAGNOSTIC_ONLY),
        "evidence_mismatch_count": 0,
        "evidence_mismatch_query_ids": [],
        "review_marker_buckets": issue_buckets,
        "normalized_bucket_counts": dict(sorted(bucket_counts.items())),
        "unresolved_user_review_count": len(unresolved),
        "unresolved_user_review_rows": unresolved,
        "rows": normalized_rows,
    }


def pdf_bucket(row: Mapping[str, str]) -> tuple[str, str]:
    if pdf_requires_evidence_revision(row):
        return EXPECTED_EVIDENCE_REVISION, "user decision marks expected evidence revision"
    if (
        clean(row.get("user_gold_decision")) == "KEEP_POSITIVE"
        and clean(row.get("user_answerability_label")) == "ANSWERABLE"
        and clean(row.get("user_relevance_label")) == "RELEVANT"
        and clean(row.get("user_expected_evidence_policy")) == "KEEP_CURRENT_EVIDENCE"
        and clean(row.get("user_denominator_policy")) == "INCLUDE_POSITIVE_DENOMINATOR_AFTER_USER_REVIEW"
    ):
        return CONTENT_EVIDENCE_POSITIVE, "content evidence positive lane"
    if (
        clean(row.get("user_gold_decision")) == "KEEP_POSITIVE"
        and clean(row.get("user_denominator_policy")) == "INCLUDE_FILE_LOOKUP_DENOMINATOR_CANDIDATE"
        and clean(row.get("user_answerability_label")) in {"ANSWERABLE", "ANSWERABLE_AS_FILE_LOOKUP"}
        and clean(row.get("user_relevance_label")) in {"RELEVANT", "PARTIAL"}
    ):
        return FILE_LOOKUP_IDENTITY_CANDIDATE, "file/document identity lookup lane"
    return DIAGNOSTIC_ONLY, "not a content positive or file identity candidate under conservative PDF policy"


def pdf_requires_evidence_revision(row: Mapping[str, str]) -> bool:
    return "REVISE_EXPECTED_EVIDENCE" in split_values(row.get("user_gold_decision")) or clean(
        row.get("user_expected_evidence_policy")
    ) == "REVISE_EXPECTED_EVIDENCE"


def pdf_issue_tags(row: Mapping[str, str]) -> list[str]:
    tags: list[str] = []
    for key in [
        "user_gold_decision",
        "user_answerability_label",
        "user_relevance_label",
        "user_expected_evidence_policy",
        "user_denominator_policy",
    ]:
        tags.extend(split_values(row.get(key)))
    if "GENERIC_FILENAME" in split_values(row.get("risk_tags")):
        tags.append("GENERIC_FILENAME")
    return dedupe(tags)


def validate_pack(
    *,
    rows: list[dict[str, str]],
    columns: list[str],
    expected_row_count: int,
    query_id_column: str,
) -> dict[str, Any]:
    errors: list[str] = []
    actual_columns = list(rows[0].keys()) if rows else []
    missing = [column for column in columns if column not in actual_columns]
    if missing:
        errors.append("missing required columns: " + ", ".join(missing))
    if len(rows) != expected_row_count:
        errors.append(f"row count {len(rows)} != expected {expected_row_count}")
    ids = [clean(row.get(query_id_column)) for row in rows]
    duplicate_ids = sorted(query_id for query_id, count in Counter(ids).items() if query_id and count > 1)
    blank_ids = sum(1 for query_id in ids if not query_id)
    if duplicate_ids:
        errors.append("duplicate query_id values: " + ", ".join(duplicate_ids))
    if blank_ids:
        errors.append(f"blank query_id count: {blank_ids}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "expected_row_count": expected_row_count,
        "actual_row_count": len(rows),
        "required_columns_present": not missing,
        "missing_columns": missing,
        "unique_query_ids": not duplicate_ids and blank_ids == 0,
        "duplicate_query_ids": duplicate_ids,
        "blank_query_id_count": blank_ids,
        "errors": errors,
    }


def validate_cross_track_guardrails(*, text: Mapping[str, Any], xlsx: Mapping[str, Any], pdf: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    text_rows = text["rows"]
    for row in text_rows:
        if row["normalized_policy_bucket"] == PROPOSED_OFFICIAL:
            tags = set(row["issue_tags"])
            if "DIAGNOSTIC_ONLY_DEFAULT" in tags:
                errors.append(f"{row['query_id']}: diagnostic-only TEXT row promoted")
            if tags & {"INVALID_QUERY", "AMBIGUOUS_QUERY", "EVIDENCE_TOO_BROAD", "NEEDS_SECOND_REVIEW"}:
                errors.append(f"{row['query_id']}: review-marked TEXT row promoted")
    for row in xlsx["rows"]:
        if row["normalized_policy_bucket"] == PROPOSED_OFFICIAL:
            tags = set(row["issue_tags"])
            if "NOT_ANSWERABLE" in tags or "POLICY_EXCLUDED" in tags or "EVIDENCE_MISMATCH" in tags:
                errors.append(f"{row['query_id']}: excluded XLSX row promoted")
    for row in pdf["rows"]:
        if row["normalized_policy_bucket"] == CONTENT_EVIDENCE_POSITIVE:
            tags = set(row["issue_tags"])
            if "NOT_ANSWERABLE" in tags or "IRRELEVANT" in tags or "REVISE_EXPECTED_EVIDENCE" in tags:
                errors.append(f"{row['query_id']}: invalid PDF content-positive lane")
    return errors


def normalized_label_mapping() -> dict[str, Any]:
    return {
        "text_namu_v2": {
            "proposed_official_candidate": (
                "OFFICIAL_REVIEW_CANDIDATE + KEEP_POSITIVE + ANSWERABLE + RELEVANT + empty user_review_notes "
                "+ source_label_status not needs_review"
            ),
            "diagnostic_only": "DIAGNOSTIC_ONLY_DEFAULT stays diagnostic-only.",
            "separate_review_markers": [
                "NEEDS_SECOND_REVIEW",
                "REVISE_EXPECTED_ANSWER",
                "REVISE_EXPECTED_ANSWER_AND_EVIDENCE",
                "AMBIGUOUS_QUERY",
                "INVALID_QUERY",
                "EVIDENCE_TOO_BROAD",
            ],
        },
        "xlsx_human_review": {
            "proposed_official_candidate": "ANSWERABLE_CONFIRMED + EVIDENCE_RELEVANT.",
            "official_denominator_frozen": (
                "0 rows because user_gold_policy_decision and user_include_in_official_denominator are blank."
            ),
            "source_verification_required": (
                "ANSWERABLE_NEEDS_SOURCE_VERIFICATION + EVIDENCE_PARTIAL/RELEVANT; not official positive yet."
            ),
            "evidence_mismatch": "EVIDENCE_MISMATCH is not an official positive.",
            "policy_excluded": "POLICY_EXCLUDED or NOT_ANSWERABLE stays outside positive denominators.",
            "preserved_policy_inputs": ["user_gold_answer_shape", "user_required_citation_policy"],
        },
        "pdf_file_lookup_companion": {
            "content_evidence_positive": (
                "KEEP_POSITIVE + ANSWERABLE + RELEVANT + KEEP_CURRENT_EVIDENCE + "
                "INCLUDE_POSITIVE_DENOMINATOR_AFTER_USER_REVIEW."
            ),
            "file_lookup_identity_candidate": (
                "KEEP_POSITIVE + INCLUDE_FILE_LOOKUP_DENOMINATOR_CANDIDATE + answerable/file-lookup answerable "
                "+ relevant/partial; this lane is scored separately from content evidence."
            ),
            "evidence_revision": "Any REVISE_EXPECTED_EVIDENCE marker goes to the evidence revision bucket.",
            "policy_excluded": "NOT_ANSWERABLE or IRRELEVANT rows are not content-positive denominator rows.",
            "aggregate_policy": "No aggregate official candidate count is emitted for PDF content and file identity lanes.",
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    text = report["tracks"]["text_namu_v2"]
    xlsx = report["tracks"]["xlsx_human_review"]
    pdf = report["tracks"]["pdf_file_lookup_companion"]
    lines = [
        "# Reviewed Gold Policy Normalization Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated at: `{report['generated_at']}`",
        "- Scope: CSV schema/count validation and conservative policy normalization only.",
        "- Guardrail: no production namespace, retrieval variant, or official denominator mutation.",
        "",
        "## Imported Files",
    ]
    for key, ref in report["imported_files"].items():
        lines.append(f"- `{key}`: `{ref['path']}` (`{ref['row_count']}` rows, sha256 `{ref['sha256']}`)")
    lines.extend(
        [
            "",
            "## Normalized Counts",
            "",
            "| Track | Proposed content/evidence candidates | File identity candidates | Frozen official denominator | Diagnostic-only | Source verification / binding | Evidence mismatch | Policy excluded | Revision / second review |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            (
                f"| TEXT/Namu | `{text['proposed_official_candidate_count']}` | `0` | `0` | "
                f"`{text['diagnostic_only_count']}` | `{text['source_verification_required_count']}` | `0` | "
                f"`{text['policy_excluded_count']}` | `{text['expected_answer_or_evidence_revision_count'] + len(text['review_marker_buckets']['needs_second_review'])}` |"
            ),
            (
                f"| XLSX | `{xlsx['proposed_official_candidate_count']}` | `0` | `{xlsx['official_denominator_frozen_count']}` | "
                f"`{xlsx['diagnostic_only_count']}` | `{xlsx['source_verification_required_count']}` | "
                f"`{xlsx['evidence_mismatch_count']}` | "
                f"`{xlsx['policy_excluded_count']}` | `0` |"
            ),
            (
                f"| PDF content/file lanes | `{pdf['content_evidence_positive_count']}` | "
                f"`{pdf['file_lookup_identity_candidate_count']}` | `{pdf['official_denominator_frozen_count']}` | "
                f"`{pdf['diagnostic_only_count']}` | `0` | `{pdf['evidence_mismatch_count']}` | `{pdf['policy_excluded_count']}` | "
                f"`{pdf['expected_answer_or_evidence_revision_count']}` |"
            ),
            "",
            "## PDF Lane Split",
            "",
            f"- Content evidence positives: `{pdf['content_evidence_positive_count']}`",
            f"- File lookup / document identity candidates: `{pdf['file_lookup_identity_candidate_count']}`",
            "- These lanes are not mixed for scoring.",
            "",
            "## Rows Still Requiring User Gold-Policy Judgment",
            "",
            f"- TEXT/Namu: `{text['unresolved_user_review_count']}`",
            (
                f"- XLSX: `{xlsx['unresolved_user_review_count']}` "
                f"(`{xlsx['denominator_confirmation_required_count']}` candidate-inclusion confirmations, "
                f"`{xlsx['source_verification_required_count']}` source-verification rows)"
            ),
            f"- PDF: `{pdf['unresolved_user_review_count']}`",
            "",
            "## Guardrails",
            "",
            f"- Official denominator registry changed: `{report['guardrails']['official_denominator_registry_changed']}`",
            f"- Official denominator opened: `{report['guardrails']['official_denominator_opened']}`",
            f"- Diagnostic-only row promoted: `{report['guardrails']['diagnostic_only_row_promoted']}`",
            f"- Retrieval variants run: `{report['guardrails']['retrieval_variants_run']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def row_summary(row: Mapping[str, str], *, bucket: str, issue_tags: Iterable[str], reason: str) -> dict[str, Any]:
    return {
        "query_id": clean(row.get("query_id")),
        "normalized_policy_bucket": bucket,
        "issue_tags": list(issue_tags),
        "normalization_reason": reason,
    }


def ids_for_bucket(rows: Iterable[Mapping[str, Any]], bucket: str) -> list[str]:
    return [str(row["query_id"]) for row in rows if row.get("normalized_policy_bucket") == bucket]


def ids_matching(rows: Iterable[Mapping[str, str]], predicate: Callable[[Mapping[str, str]], bool]) -> list[str]:
    return [clean(row.get("query_id")) for row in rows if predicate(row)]


def input_ref(path: Path, expected_row_count: int) -> dict[str, Any]:
    rows = read_csv_rows(path) if path.exists() else []
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "expected_row_count": expected_row_count,
        "sha256": sha256_file(path) if path.exists() else "",
        "bytes": path.stat().st_size if path.exists() else 0,
    }


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: value for key, value in row.items()} for row in csv.DictReader(handle)]


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def clean(value: Any) -> str:
    return str(value or "").strip()


def split_values(value: Any) -> list[str]:
    text = clean(value)
    if not text:
        return []
    parts = [part.strip() for chunk in text.split(";") for part in chunk.split(",")]
    return [part for part in parts if part]


def dedupe(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
