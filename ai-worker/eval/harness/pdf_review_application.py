"""Diagnostic-only PDF review-pack application harness.

This module consumes prepared PDF manual/supplemental review packs and turns
reviewed rows into retrieval/evidence validation diagnostics. It never runs
answer generation, broad indexing, or denominator mutation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from eval.harness.xlsx_pdf_route_trace import (
    FAIL_FILE_CONTENT_MISMATCH,
    FAIL_INVALID_LOCATION,
    FAIL_MISSING_CITATION,
    FAIL_MISSING_LOCATION,
    FAIL_NO_EVIDENCE,
    FAIL_ROUTE_MISMATCH,
    OFFICIAL_REGISTRY,
    REPORT_DIR,
    RETRY_FAILURES,
    ROUTE_PDF_CONTENT,
    ROUTE_PDF_FILE,
    STATUS_DIAGNOSTIC_ONLY,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_REVIEW_REQUIRED,
    UNKNOWN,
    RouteRetryController,
    ScopedRetriever,
    dedupe,
    display_path,
    failure_category_counts,
    protected_artifact_diff,
    retry_summary,
    sha256_file,
    status_counts,
)


AI_WORKER = Path(__file__).resolve().parents[2]
ROOT = AI_WORKER.parent
REVIEW_DIR = AI_WORKER / "eval" / "review" / "pdf_supplemental_gold_review"

APPLICATION_STATUS_OFFICIAL = "OFFICIAL_RETRIEVAL_EVIDENCE_CANDIDATE"
APPLICATION_STATUS_REVIEW_REQUIRED = "REVIEW_REQUIRED"
APPLICATION_STATUS_EXCLUDED_INCOMPLETE = "EXCLUDED_INCOMPLETE_REVIEW"
APPLICATION_STATUS_EXCLUDED_POLICY_REJECTED = "EXCLUDED_POLICY_REJECTED"
APPLICATION_STATUS_DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"

FAIL_ROUTE_POLICY_MISSING = "ROUTE_POLICY_MISSING"
FAIL_ROUTE_POLICY_AMBIGUOUS = "ROUTE_POLICY_AMBIGUOUS"
FAIL_FILE_EXPECTED_CONTENT_ACTUAL = "FILE_EXPECTED_CONTENT_ACTUAL"
FAIL_CONTENT_EXPECTED_FILE_ACTUAL = "CONTENT_EXPECTED_FILE_ACTUAL"
FAIL_TABLE_POLICY_MISSING = "TABLE_POLICY_MISSING"
FAIL_PAGE_POLICY_MISSING = "PAGE_POLICY_MISSING"
FAIL_BBOX_POLICY_MISSING = "BBOX_POLICY_MISSING"
FAIL_TABLE_POLICY_REJECTED = "TABLE_POLICY_REJECTED"
FAIL_PAGE_POLICY_REJECTED = "PAGE_POLICY_REJECTED"
FAIL_BBOX_POLICY_REJECTED = "BBOX_POLICY_REJECTED"
FAIL_REVIEW_LABEL_MISSING = "REVIEW_LABEL_MISSING"
FAIL_GOLD_DECISION_NOT_POSITIVE = "GOLD_DECISION_NOT_POSITIVE"
FAIL_ANSWERABILITY_NOT_POSITIVE = "ANSWERABILITY_NOT_POSITIVE"
FAIL_RELEVANCE_NOT_RELEVANT = "RELEVANCE_NOT_RELEVANT"
FAIL_REVIEW_LABEL_MALFORMED = "REVIEW_LABEL_MALFORMED"
FAIL_NO_SCOPED_INDEX = "MISSING_SCOPED_INDEX"
FAIL_BBOX_MISSING_EVIDENCE = "bbox_missing_evidence"
FAIL_OCR_WHEN_NATIVE_EXISTS = "ocr_fallback_candidate_when_native_exists"

USER_COLUMNS = [
    "user_gold_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_evidence_policy",
    "user_denominator_policy",
    "user_issue_tags",
    "user_notes",
]

REQUIRED_REVIEW_COLUMNS = [
    "user_gold_decision",
    "user_answerability_label",
    "user_relevance_label",
    "user_expected_evidence_policy",
    "user_denominator_policy",
]

REQUIRED_PACK_COLUMNS = [
    "query_id",
    "query",
    "expected_evidence_excerpt",
    "expected_file_name",
    "retrieval_lane",
    "review_lane",
    "suggested_answerability_label",
    "suggested_relevance_label",
    "suggested_expected_evidence_policy",
    "suggested_denominator_policy",
]

ROUTE_POLICY_FILE_VALUES = {
    "FILE",
    "PDF_FILE",
    "PDF_FILE_LOOKUP",
    "PDF_FILE_LOOKUP_BY_METADATA",
    "PDF_FILE_LOOKUP_BY_CONTENT_ANCHOR",
    "EXPECTED_FILE_NAME_OR_DOCUMENT_IDENTITY",
    "ANSWERABLE_AS_FILE_LOOKUP",
    "INCLUDE_FILE_LOOKUP_DENOMINATOR_CANDIDATE",
}
ROUTE_POLICY_CONTENT_VALUES = {
    "CONTENT",
    "PDF_CONTENT",
    "PDF_CONTENT_LOOKUP",
    "PDF_CONTENT_RETRIEVAL_REVIEW",
    "KEEP_CURRENT_EVIDENCE",
    "REVISE_EXPECTED_EVIDENCE",
    "INCLUDE_POSITIVE_DENOMINATOR_AFTER_USER_REVIEW",
}
POLICY_ALLOW_VALUES = {"ALLOW", "ALLOWED", "ACCEPT", "ACCEPTED", "KEEP", "REQUIRE", "REQUIRED", "YES"}
POLICY_REJECT_VALUES = {"REJECT", "REJECTED", "EXCLUDE", "EXCLUDED", "NO", "DENY", "DENIED"}
DENOMINATOR_INCLUDE_VALUES = {
    "INCLUDE",
    "INCLUDE_POSITIVE_DENOMINATOR_AFTER_USER_REVIEW",
    "INCLUDE_FILE_LOOKUP_DENOMINATOR_CANDIDATE",
    "OFFICIAL_RETRIEVAL_EVIDENCE_CANDIDATE",
}
DENOMINATOR_REJECT_VALUES = {"EXCLUDE", "EXCLUDE_POSITIVE_DENOMINATOR", "REJECT", "REJECTED"}
GOLD_POSITIVE_VALUES = {"KEEP_POSITIVE"}
GOLD_REJECT_VALUES = {"RELABEL_NEGATIVE", "REJECT", "REJECTED", "EXCLUDE", "EXCLUDED"}
ANSWERABILITY_POSITIVE_VALUES = {"ANSWERABLE", "ANSWERABLE_AS_FILE_LOOKUP"}
ANSWERABILITY_REJECT_VALUES = {"NOT_ANSWERABLE", "UNANSWERABLE"}
RELEVANCE_POSITIVE_VALUES = {"RELEVANT"}
RELEVANCE_REJECT_VALUES = {"IRRELEVANT"}


@dataclass(frozen=True)
class ReviewApplicationConfig:
    date: str = "20260507"
    review_dir: Path = REVIEW_DIR
    report_dir: Path = REPORT_DIR
    official_registry: Path = OFFICIAL_REGISTRY
    max_retries: int = 2
    live_scoped_check: bool = True
    selected_review_pack: Path | None = None
    manifest_path: Path | None = None


def build_review_application_reports(config: ReviewApplicationConfig) -> dict[str, Any]:
    selected_pack = config.selected_review_pack or select_review_pack(config.review_dir)["path"]
    pack_info = review_pack_metadata(selected_pack)
    rows = read_csv_rows(selected_pack)
    validation = validate_review_pack(selected_pack, rows=rows, config=config, selected_metadata=pack_info)
    normalized_rows = normalize_review_rows(rows, source_path=selected_pack)
    application = build_application_report(config, validation, normalized_rows)
    route_trace = build_reviewed_route_trace_report(config, validation, normalized_rows)
    agentic = build_reviewed_agentic_report(config, route_trace["route_trace_rows"])
    xlsx_silver = build_xlsx_strict_silver_report(config)
    reports = {
        "validation": validation,
        "application": application,
        "route_trace": route_trace,
        "agentic_loop": agentic,
        "xlsx_strict_silver": xlsx_silver,
    }
    return reports


def write_review_application_reports(config: ReviewApplicationConfig) -> dict[str, Any]:
    reports = build_review_application_reports(config)
    report_paths = default_report_paths(config)

    write_json(report_paths["validation_json"], reports["validation"])
    write_markdown(report_paths["validation_md"], render_validation_markdown(reports["validation"]))
    write_json(report_paths["application_json"], reports["application"])
    write_markdown(report_paths["application_md"], render_application_markdown(reports["application"]))
    write_jsonl(report_paths["normalized_jsonl"], reports["application"].get("normalized_rows", []))
    write_json(report_paths["route_json"], reports["route_trace"])
    write_markdown(report_paths["route_md"], render_route_markdown(reports["route_trace"]))
    write_json(report_paths["agentic_json"], reports["agentic_loop"])
    write_markdown(report_paths["agentic_md"], render_agentic_markdown(reports["agentic_loop"]))
    write_json(report_paths["xlsx_json"], reports["xlsx_strict_silver"])
    write_markdown(report_paths["xlsx_md"], render_xlsx_markdown(reports["xlsx_strict_silver"]))

    manifest = build_manifest(config, reports, report_paths)
    write_toml(report_paths["manifest_toml"], manifest)
    reports["manifest"] = manifest
    reports["manifest_path"] = display_path(report_paths["manifest_toml"])
    return reports


def default_report_paths(config: ReviewApplicationConfig) -> dict[str, Path]:
    report_dir = config.report_dir
    date = config.date
    return {
        "validation_json": report_dir / f"pdf_review_pack_validation_{date}.json",
        "validation_md": report_dir / f"pdf_review_pack_validation_{date}.md",
        "application_json": report_dir / f"pdf_reviewed_retrieval_evidence_application_{date}.json",
        "application_md": report_dir / f"pdf_reviewed_retrieval_evidence_application_{date}.md",
        "normalized_jsonl": report_dir / f"pdf_reviewed_retrieval_evidence_normalized_{date}.jsonl",
        "route_json": report_dir / f"pdf_reviewed_route_trace_diagnostic_{date}.json",
        "route_md": report_dir / f"pdf_reviewed_route_trace_diagnostic_{date}.md",
        "agentic_json": report_dir / f"pdf_reviewed_agentic_route_loop_diagnostic_{date}.json",
        "agentic_md": report_dir / f"pdf_reviewed_agentic_route_loop_diagnostic_{date}.md",
        "xlsx_json": report_dir / f"xlsx_strict_silver_generation_{date}.json",
        "xlsx_md": report_dir / f"xlsx_strict_silver_generation_{date}.md",
        "manifest_toml": config.manifest_path or report_dir / f"pdf_xlsx_review_application_manifest_{date}.toml",
    }


def discover_review_packs(review_dir: Path = REVIEW_DIR) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if not review_dir.exists():
        return candidates
    for path in sorted(review_dir.glob("*.csv")):
        if "pdf" not in path.name.lower() or "review" not in path.name.lower():
            continue
        try:
            metadata = review_pack_metadata(path)
        except Exception as exc:
            candidates.append(
                {
                    "path": path,
                    "path_display": display_path(path),
                    "exists": path.exists(),
                    "read_error": f"{type(exc).__name__}: {exc}",
                    "row_count": 0,
                    "complete_reviewed_row_count": 0,
                    "rows_with_any_user_review_count": 0,
                    "selection_score": [-1],
                }
            )
            continue
        candidates.append(metadata)
    return sorted(candidates, key=lambda item: item["selection_score"], reverse=True)


def select_review_pack(review_dir: Path = REVIEW_DIR) -> dict[str, Any]:
    candidates = discover_review_packs(review_dir)
    if not candidates:
        raise FileNotFoundError(f"no PDF review CSV found under {review_dir}")
    selected = candidates[0]
    selected["selection_rationale"] = (
        "Selected by complete reviewed-row count, merged FILE companion coverage, row count, "
        "and newest mtime. If all user-reviewed columns are blank, the latest merged pack is "
        "still consumed but official candidates remain zero."
    )
    return selected


def review_pack_metadata(path: Path) -> dict[str, Any]:
    rows = read_csv_rows(path)
    fieldnames = list(rows[0].keys()) if rows else csv_fieldnames(path)
    any_user = sum(1 for row in rows if any(clean(row.get(column)) for column in USER_COLUMNS if column in row))
    complete = sum(1 for row in rows if complete_review_labels(row))
    lanes = Counter(clean(row.get("retrieval_lane") or row.get("review_lane") or row.get("query_surface_type")) for row in rows)
    file_lookup_count = sum(1 for row in rows if is_file_lookup_row(row))
    content_count = sum(1 for row in rows if not is_file_lookup_row(row))
    table_count = sum(1 for row in rows if is_table_lane(row))
    stat = path.stat()
    has_file_lookup = int(file_lookup_count > 0 and "with_file_lookup" in path.name)
    selection_score = [complete, has_file_lookup, any_user, len(rows), int(stat.st_mtime)]
    return {
        "path": path,
        "path_display": display_path(path),
        "exists": path.exists(),
        "sha256": sha256_file(path),
        "bytes": stat.st_size,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "row_count": len(rows),
        "fieldnames": fieldnames,
        "user_columns_present": [column for column in USER_COLUMNS if column in fieldnames],
        "user_columns_blank": any_user == 0,
        "rows_with_any_user_review_count": any_user,
        "complete_reviewed_row_count": complete,
        "retrieval_lane_counts": dict(sorted(lanes.items())),
        "file_lookup_row_count": file_lookup_count,
        "content_lookup_row_count": content_count,
        "table_lane_row_count": table_count,
        "has_file_lookup_companion": file_lookup_count > 0,
        "selection_score": selection_score,
    }


def validate_review_pack(
    path: Path,
    *,
    rows: Sequence[Mapping[str, str]],
    config: ReviewApplicationConfig,
    selected_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    fieldnames = list(rows[0].keys()) if rows else csv_fieldnames(path)
    missing_required_columns = [column for column in REQUIRED_PACK_COLUMNS if column not in fieldnames]
    missing_user_columns = [column for column in USER_COLUMNS if column not in fieldnames]
    query_ids = [clean(row.get("query_id")) for row in rows]
    blank_query_ids = [idx + 1 for idx, query_id in enumerate(query_ids) if not query_id]
    duplicate_ids = sorted([query_id for query_id, count in Counter(query_ids).items() if query_id and count > 1])
    complete_rows = [row for row in rows if complete_review_labels(row)]
    incomplete_rows = [row for row in rows if not complete_review_labels(row)]
    file_rows = [row for row in rows if is_file_lookup_row(row)]
    content_rows = [row for row in rows if not is_file_lookup_row(row)]
    expected_evidence_missing = [
        clean(row.get("query_id"))
        for row in rows
        if not clean(row.get("expected_evidence_excerpt") or row.get("expected_answer_text"))
    ]
    route_policy_missing = [
        clean(row.get("query_id"))
        for row in complete_rows
        if classify_reviewed_route_policy(row) in {"MISSING", "AMBIGUOUS"}
    ]
    policy_missing = {
        "table_policy_missing": [clean(row.get("query_id")) for row in complete_rows if is_table_lane(row) and policy_state(row, "table") == "MISSING"],
        "page_policy_missing": [clean(row.get("query_id")) for row in complete_rows if is_page_lane(row) and policy_state(row, "page") == "MISSING"],
        "bbox_policy_missing": [clean(row.get("query_id")) for row in complete_rows if bbox_reference_present(row) and policy_state(row, "bbox") == "MISSING"],
    }
    errors = []
    if missing_required_columns:
        errors.append("missing_required_pack_columns")
    if missing_user_columns:
        errors.append("missing_user_review_columns")
    if blank_query_ids:
        errors.append("blank_query_id")
    if duplicate_ids:
        errors.append("duplicate_query_id")
    if not file_rows:
        errors.append("missing_file_lookup_lane")
    if not content_rows:
        errors.append("missing_content_lookup_lane")
    warnings = []
    if incomplete_rows:
        warnings.append("incomplete_user_review_rows_excluded_from_official_candidates")
    if expected_evidence_missing:
        warnings.append("expected_evidence_missing_for_some_rows")

    denominator_diff = denominator_registry_git_diff(config.official_registry)
    payload = base_report(
        config,
        report_role="pdf_review_pack_validation",
        status=STATUS_FAIL if errors else STATUS_DIAGNOSTIC_ONLY,
        source_review_pack=path,
        extra={
            "selected_review_pack": artifact_identity(path),
            "selection_rationale": selected_metadata.get("selection_rationale")
            or (
                "Selected by complete reviewed-row count, merged FILE companion coverage, row count, "
                "and newest mtime."
            ),
            "candidate_review_packs": [
                strip_path_object(candidate) for candidate in discover_review_packs(config.review_dir)
            ],
            "fieldnames": fieldnames,
            "missing_required_columns": missing_required_columns,
            "missing_user_columns": missing_user_columns,
            "row_count": len(rows),
            "stable_query_ids": not blank_query_ids,
            "blank_query_id_rows": blank_query_ids,
            "duplicate_active_query_ids": duplicate_ids,
            "rows_with_any_user_review_count": selected_metadata.get("rows_with_any_user_review_count", 0),
            "complete_reviewed_row_count": len(complete_rows),
            "incomplete_review_row_count": len(incomplete_rows),
            "user_columns_blank": selected_metadata.get("user_columns_blank"),
            "file_lookup_rows_distinguishable": bool(file_rows),
            "content_lookup_rows_distinguishable": bool(content_rows),
            "file_lookup_row_count": len(file_rows),
            "content_lookup_row_count": len(content_rows),
            "table_lane_row_count": sum(1 for row in rows if is_table_lane(row)),
            "page_lane_row_count": sum(1 for row in rows if is_page_lane(row)),
            "bbox_reference_row_count": sum(1 for row in rows if bbox_reference_present(row)),
            "expected_evidence_missing_query_ids": expected_evidence_missing[:100],
            "route_policy_missing_or_ambiguous_query_ids": route_policy_missing[:100],
            "policy_missing": policy_missing,
            "validation_errors": errors,
            "validation_warnings": warnings,
            "review_pack_validation_status": "VALID_FOR_DIAGNOSTIC_CONSUMPTION" if not errors else "FAIL_CLOSED",
            "official_candidate_readiness": "NO_COMPLETE_REVIEWED_ROWS" if not complete_rows else "HAS_COMPLETE_REVIEWED_ROWS",
            "denominator_registry_diff": denominator_diff,
        },
    )
    return payload


def normalize_review_rows(rows: Sequence[Mapping[str, str]], *, source_path: Path) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for ordinal, row in enumerate(rows, start=1):
        query_id = clean(row.get("query_id")) or f"__blank_query_id_row_{ordinal}"
        route_policy = classify_reviewed_route_policy(row)
        actual_route = actual_route_from_row(row)
        policy_status = reviewed_policy_status(row)
        failure_categories = row_failure_categories(row, route_policy=route_policy, actual_route=actual_route)
        application_status = application_status_for_row(row, failure_categories=failure_categories)
        normalized.append(
            {
                "source_review_pack": display_path(source_path),
                "source_row_number": ordinal,
                "query_id": query_id,
                "query_text": query_text(row),
                "source_file_id": clean(row.get("source_file_id")) or UNKNOWN,
                "source_file_name": clean(row.get("source_file_name") or row.get("expected_file_name")),
                "expected_file_name": clean(row.get("expected_file_name")),
                "expected_document_version_id": clean(row.get("expected_document_version_id")),
                "expected_page_no": clean(row.get("expected_page_no")),
                "expected_page_label": clean(row.get("expected_page_label")),
                "expected_bbox": clean(row.get("expected_bbox")),
                "expected_evidence": clean(row.get("expected_evidence_excerpt") or row.get("expected_answer_text")),
                "retrieval_lane": clean(row.get("retrieval_lane") or row.get("review_lane") or row.get("query_surface_type")),
                "review_group": clean(row.get("review_group")),
                "review_lane": clean(row.get("review_lane")),
                "risk_tags": clean(row.get("risk_tags")),
                "suggested_gold_decision": clean(row.get("suggested_gold_decision")),
                "suggested_answerability_label": clean(row.get("suggested_answerability_label")),
                "suggested_relevance_label": clean(row.get("suggested_relevance_label")),
                "suggested_expected_evidence_policy": clean(row.get("suggested_expected_evidence_policy")),
                "suggested_denominator_policy": clean(row.get("suggested_denominator_policy")),
                "user_gold_decision": clean(row.get("user_gold_decision")),
                "user_answerability_label": clean(row.get("user_answerability_label")),
                "user_relevance_label": clean(row.get("user_relevance_label")),
                "user_expected_evidence_policy": clean(row.get("user_expected_evidence_policy")),
                "user_denominator_policy": clean(row.get("user_denominator_policy")),
                "user_issue_tags": clean(row.get("user_issue_tags")),
                "user_notes": clean(row.get("user_notes")),
                "reviewer_notes": clean(row.get("user_notes")),
                "review_complete": complete_review_labels(row),
                "review_missing_columns": [column for column in REQUIRED_REVIEW_COLUMNS if not clean(row.get(column))],
                "expected_route_policy": route_policy,
                "actual_route": actual_route,
                "route_mismatch_category": route_mismatch_category(route_policy, actual_route),
                "table_policy_status": policy_status["table"],
                "page_policy_status": policy_status["page"],
                "bbox_policy_status": policy_status["bbox"],
                "native_ocr_policy_status": policy_status["native_ocr"],
                "file_lookup_reference_only": is_file_lookup_row(row),
                "requires_page_success": policy_status["page"] == "ALLOW",
                "requires_bbox_success": policy_status["bbox"] == "ALLOW",
                "requires_table_value_success": policy_status["table"] == "ALLOW",
                "application_status": application_status,
                "official_retrieval_evidence_candidate": application_status == APPLICATION_STATUS_OFFICIAL,
                "exclusion_reason": exclusion_reason(application_status, failure_categories),
                "failure_categories": failure_categories,
                "promotion_evidence": False,
                "official_denominator_changed": False,
                "pdf_answer_denominator_included": False,
                "answer_generation_execution": "not_run_by_this_harness",
            }
        )
    return normalized


def build_application_report(
    config: ReviewApplicationConfig,
    validation: Mapping[str, Any],
    normalized_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    included = [row for row in normalized_rows if row.get("application_status") == APPLICATION_STATUS_OFFICIAL]
    excluded = [row for row in normalized_rows if str(row.get("application_status", "")).startswith("EXCLUDED")]
    review_required = [row for row in normalized_rows if row.get("application_status") == APPLICATION_STATUS_REVIEW_REQUIRED]
    by_reason = Counter(clean(row.get("exclusion_reason")) for row in excluded)
    before_after = registry_denominator_snapshot(config.official_registry)
    payload = base_report(
        config,
        report_role="pdf_reviewed_retrieval_evidence_application",
        status=STATUS_DIAGNOSTIC_ONLY,
        source_review_pack=resolve_report_path(validation["selected_review_pack"]["path"]),
        extra={
            "normalized_dataset_role": "pdf_reviewed_retrieval_evidence_dataset",
            "normalized_rows": list(normalized_rows),
            "source_row_count": len(normalized_rows),
            "reviewed_included_row_count": len(included),
            "excluded_row_count": len(excluded),
            "review_required_row_count": len(review_required),
            "excluded_by_reason": dict(sorted(by_reason.items())),
            "official_retrieval_evidence_candidate_ids": [row["query_id"] for row in included],
            "review_required_query_ids": [row["query_id"] for row in review_required],
            "denominator_registry_update_performed": False,
            "denominator_proposal_only": True,
            "denominator_registry_mutation_supported": False,
            "denominator_registry_decision": "proposal_only_no_mutation",
            "denominator_registry_decision_reason": denominator_decision_reason(included, validation),
            "official_denominator_change_reason": None,
            "before_after_denominator_values": before_after,
            "proposed_pdf_retrieval_evidence_denominator": len(included),
            "proposed_row_ids": [row["query_id"] for row in included],
            "row_ids_added": [],
            "row_ids_removed": [],
            "source_review_pack_sha256": validation["selected_review_pack"]["sha256"],
            "pdf_answer_denominator": 0,
            "xlsx_answer_denominator": 0,
        },
    )
    return payload


def build_reviewed_route_trace_report(
    config: ReviewApplicationConfig,
    validation: Mapping[str, Any],
    normalized_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    route_rows = [route_trace_row(row) for row in normalized_rows]
    summary = route_trace_summary(route_rows)
    included_count = sum(1 for row in normalized_rows if row.get("application_status") == APPLICATION_STATUS_OFFICIAL)
    live_scoped = live_scoped_index_status(included_count=included_count)
    payload = base_report(
        config,
        report_role="pdf_reviewed_route_trace_diagnostic",
        status=STATUS_DIAGNOSTIC_ONLY,
        source_review_pack=resolve_report_path(validation["selected_review_pack"]["path"]),
        extra={
            "retrieval_execution": "review_pack_replay_no_live_index_mutation",
            "review_pack_row_count": len(normalized_rows),
            "route_trace_rows": route_rows,
            "route_counts": status_counts(route_rows),
            "failure_category_counts": failure_category_counts(route_rows),
            "pdf_reviewed_route_summary": summary,
            "pdf_source_row_count": len(normalized_rows),
            "reviewed_included_row_count": included_count,
            "excluded_row_count": sum(1 for row in normalized_rows if str(row.get("application_status", "")).startswith("EXCLUDED")),
            "excluded_by_reason": dict(sorted(Counter(clean(row.get("exclusion_reason")) for row in normalized_rows if str(row.get("application_status", "")).startswith("EXCLUDED")).items())),
            "optional_live_scoped_retrieval_check": live_scoped,
            "table_lane_included_in_diagnostic": summary["table_lane_count"] > 0,
            "allowUnscoped": False,
        },
    )
    return payload


def route_trace_row(row: Mapping[str, Any]) -> dict[str, Any]:
    failures = list(row.get("failure_categories") or [])
    application_status = clean(row.get("application_status"))
    if application_status in {APPLICATION_STATUS_EXCLUDED_INCOMPLETE, APPLICATION_STATUS_REVIEW_REQUIRED}:
        route_status = STATUS_REVIEW_REQUIRED
    elif application_status == APPLICATION_STATUS_EXCLUDED_POLICY_REJECTED:
        route_status = STATUS_DIAGNOSTIC_ONLY
    elif failures:
        route_status = STATUS_FAIL
    elif application_status == APPLICATION_STATUS_OFFICIAL:
        route_status = STATUS_PASS
    else:
        route_status = STATUS_DIAGNOSTIC_ONLY

    evidence_source = "file_lookup" if row.get("actual_route") == ROUTE_PDF_FILE else "content_lookup"
    if route_status != STATUS_PASS:
        evidence_source = "review_pack_metadata_only"
    return {
        "query_id": row.get("query_id"),
        "query_text": row.get("query_text"),
        "source_review_pack": row.get("source_review_pack"),
        "expected_route_hint": row.get("expected_route_policy"),
        "actual_route": row.get("actual_route"),
        "route_reason": route_reason(row),
        "file_type": "PDF",
        "source_file_id": row.get("source_file_id") or UNKNOWN,
        "source_file_name": row.get("source_file_name") or UNKNOWN,
        "document_version_id": row.get("expected_document_version_id") or UNKNOWN,
        "extracted_artifact_id": UNKNOWN,
        "search_unit_id": UNKNOWN,
        "parser_version": UNKNOWN,
        "location_json_present": False,
        "location_json_valid": False,
        "citation_text_present": False,
        "display_text_present": bool(row.get("expected_evidence")),
        "bm25_text_present": UNKNOWN,
        "embedding_text_present": UNKNOWN,
        "evidence_source": evidence_source,
        "allowUnscoped": False,
        "index_scope": "review_pack_replay_scoped_identity_only",
        "hidden_excluded_leakage": "NOT_APPLICABLE",
        "route_status": route_status,
        "failure_category": failures[0] if failures else None,
        "failure_categories": failures,
        "diagnostic_only_reason": "pdf_review_pack_application_no_answer_denominator",
        "application_status": row.get("application_status"),
        "exclusion_reason": row.get("exclusion_reason"),
        "expected_file_name": row.get("expected_file_name"),
        "expected_evidence": row.get("expected_evidence"),
        "review_group": row.get("review_group"),
        "review_lane": row.get("review_lane"),
        "retrieval_lane": row.get("retrieval_lane"),
        "route_mismatch_category": row.get("route_mismatch_category"),
        "page_only_evidence": is_page_lane(row),
        "table_like_evidence": is_table_lane(row),
        "bbox_present": bbox_reference_present(row),
        "bbox_missing": not bbox_reference_present(row),
        "expected_page_no": row.get("expected_page_no") or UNKNOWN,
        "expected_bbox": row.get("expected_bbox") or UNKNOWN,
        "table_policy_status": row.get("table_policy_status"),
        "page_policy_status": row.get("page_policy_status"),
        "bbox_policy_status": row.get("bbox_policy_status"),
        "native_ocr_policy_status": row.get("native_ocr_policy_status"),
        "native_pdf_text_used": False,
        "ocr_fallback_used": False,
        "file_lookup_route": row.get("actual_route") == ROUTE_PDF_FILE,
        "content_lookup_route": row.get("actual_route") == ROUTE_PDF_CONTENT,
        "official_retrieval_evidence_candidate": row.get("official_retrieval_evidence_candidate"),
    }


def build_reviewed_agentic_report(config: ReviewApplicationConfig, route_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    diagnostic_rows = list(route_rows)
    diagnostic_rows.extend(agentic_retry_fixture_rows())
    controller = RouteRetryController(max_retries=config.max_retries)
    loop_rows = [controller.run_case(row, ScopedRetriever(diagnostic_rows)) for row in diagnostic_rows]
    summary = retry_summary(loop_rows)
    summary["diagnostic_fixture_case_count"] = sum(1 for row in diagnostic_rows if row.get("diagnostic_fixture"))
    summary["retry_path_exercised"] = summary["max_attempt_count"] > 1
    payload = base_report(
        config,
        report_role="pdf_reviewed_agentic_route_loop_diagnostic",
        status=STATUS_DIAGNOSTIC_ONLY,
        source_review_pack=resolve_report_path(route_rows[0]["source_review_pack"]) if route_rows and route_rows[0].get("source_review_pack") else None,
        extra={
            "retrieval_execution": "agentic_review_pack_replay_only",
            "agentic_loop_execution": "bounded_retrieval_route_verification_only",
            "answer_generation_execution": "not_run_by_this_harness",
            "max_retries": config.max_retries,
            "route_trace_rows": diagnostic_rows,
            "agentic_route_loop_rows": loop_rows,
            "agentic_retry_summary": summary,
            "retry_fixture_reason": (
                "Reviewed user labels are incomplete in the selected pack, so retry paths are exercised "
                "with diagnostic-only fixtures and never counted as official denominator evidence."
            ),
            "retry_paths_requested": [
                FAIL_ROUTE_MISMATCH,
                FAIL_NO_EVIDENCE,
                FAIL_MISSING_CITATION,
                FAIL_INVALID_LOCATION,
                FAIL_MISSING_LOCATION,
                FAIL_BBOX_MISSING_EVIDENCE,
                "table_like_evidence",
                FAIL_FILE_CONTENT_MISMATCH,
                FAIL_OCR_WHEN_NATIVE_EXISTS,
            ],
            "allowUnscoped": False,
            "route_counts": status_counts(diagnostic_rows),
            "failure_category_counts": failure_category_counts(diagnostic_rows),
        },
    )
    return payload


def agentic_retry_fixture_rows() -> list[dict[str, Any]]:
    base = {
        "file_type": "PDF",
        "source_review_pack": "diagnostic_fixture",
        "query_text": "diagnostic route retry fixture",
        "source_file_id": UNKNOWN,
        "source_file_name": UNKNOWN,
        "document_version_id": UNKNOWN,
        "extracted_artifact_id": UNKNOWN,
        "search_unit_id": UNKNOWN,
        "parser_version": UNKNOWN,
        "location_json_present": False,
        "location_json_valid": False,
        "citation_text_present": False,
        "display_text_present": False,
        "bm25_text_present": UNKNOWN,
        "embedding_text_present": UNKNOWN,
        "allowUnscoped": False,
        "index_scope": "diagnostic_fixture_no_index",
        "hidden_excluded_leakage": "NOT_APPLICABLE",
        "application_status": APPLICATION_STATUS_DIAGNOSTIC_ONLY,
        "diagnostic_only_reason": "agentic_retry_path_fixture_not_review_pack_gold",
        "official_retrieval_evidence_candidate": False,
        "promotion_evidence": False,
        "diagnostic_fixture": True,
    }
    specs = [
        ("pdf_fixture_route_mismatch", ROUTE_PDF_FILE, [FAIL_FILE_CONTENT_MISMATCH], True, False, False),
        ("pdf_fixture_no_evidence", ROUTE_PDF_CONTENT, [FAIL_NO_EVIDENCE], False, False, False),
        ("pdf_fixture_missing_citation", ROUTE_PDF_CONTENT, [FAIL_MISSING_CITATION], False, False, False),
        ("pdf_fixture_invalid_location", ROUTE_PDF_CONTENT, [FAIL_INVALID_LOCATION], False, False, False),
        ("pdf_fixture_missing_location", ROUTE_PDF_CONTENT, [FAIL_MISSING_LOCATION], False, False, False),
        ("pdf_fixture_bbox_missing", ROUTE_PDF_CONTENT, [FAIL_BBOX_MISSING_EVIDENCE, FAIL_MISSING_LOCATION], False, False, True),
        ("pdf_fixture_table_like", ROUTE_PDF_CONTENT, [FAIL_TABLE_POLICY_MISSING, FAIL_MISSING_CITATION], False, True, False),
        ("pdf_fixture_ocr_when_native_exists", ROUTE_PDF_CONTENT, [FAIL_OCR_WHEN_NATIVE_EXISTS], False, False, False),
    ]
    rows: list[dict[str, Any]] = []
    for query_id, route, failures, file_route, table_like, bbox_missing in specs:
        row = dict(base)
        row.update(
            {
                "query_id": query_id,
                "actual_route": route,
                "expected_route_hint": route,
                "route_reason": "Diagnostic-only retry fixture.",
                "route_status": STATUS_FAIL if any(failure in RETRY_FAILURES for failure in failures) else STATUS_DIAGNOSTIC_ONLY,
                "failure_category": failures[0],
                "failure_categories": failures,
                "file_lookup_route": file_route,
                "content_lookup_route": not file_route,
                "table_like_evidence": table_like,
                "page_only_evidence": False,
                "bbox_present": not bbox_missing,
                "bbox_missing": bbox_missing,
                "evidence_source": "diagnostic_fixture",
                "route_mismatch_category": failures[0] if failures[0] in {FAIL_FILE_CONTENT_MISMATCH, FAIL_ROUTE_MISMATCH} else None,
            }
        )
        rows.append(row)
    return rows


def build_xlsx_strict_silver_report(config: ReviewApplicationConfig) -> dict[str, Any]:
    strict_report_path = config.report_dir / "xlsx_pre_silver_risk_closure_20260507.json"
    hidden_report_path = config.report_dir / "rag_xlsx_human_review_official_positive_v0_hidden_negative_leakage_diagnostic.json"
    strict_payload = read_json_if_exists(strict_report_path)
    hidden_payload = read_json_if_exists(hidden_report_path)
    hidden_status = xlsx_hidden_leakage_state(hidden_payload)
    strict_intact = strict_payload.get("final_recommendation", "").lower().find("strict") >= 0 or bool(
        strict_payload.get("artifact_resolution_summary", {}).get("registry_hashes_match_current_files")
    )
    generation_status = (
        "NOT_RUN_NO_EXPLICIT_STRICT_SILVER_GENERATOR_FOUND"
        if strict_intact and hidden_status["status"] == STATUS_PASS
        else "FAIL_CLOSED_HIDDEN_LEAKAGE_OR_STRICT_PATH_NOT_INTACT"
    )
    payload = base_report(
        config,
        report_role="xlsx_strict_silver_generation",
        status=STATUS_DIAGNOSTIC_ONLY if generation_status.startswith("NOT_RUN") else STATUS_FAIL,
        source_review_pack=None,
        extra={
            "xlsx_strict_wrapper_path_intact": strict_intact,
            "xlsx_hidden_leakage_pre_probe": hidden_status,
            "xlsx_hidden_leakage_post_probe": {
                "status": "NOT_RUN",
                "reason": "silver_generation_not_run_by_this_harness",
            },
            "silver_generation_execution": "not_run_by_this_harness",
            "silver_generation_status": generation_status,
            "strict_pre_silver_report": artifact_identity(strict_report_path),
            "hidden_leakage_report": artifact_identity(hidden_report_path),
            "promotion_evidence": False,
            "official_denominator_changed": False,
            "xlsx_answer_denominator": 0,
            "answer_generation_execution": "not_run_by_this_harness",
            "conservative_assumption": (
                "No separate strict silver-generation entrypoint was invoked here; this report only records "
                "that the approved strict wrapper closure artifact and pre-generation hidden leakage probe are present."
            ),
        },
    )
    return payload


def build_manifest(
    config: ReviewApplicationConfig,
    reports: Mapping[str, Mapping[str, Any]],
    report_paths: Mapping[str, Path],
) -> dict[str, Any]:
    validation = reports["validation"]
    application = reports["application"]
    report_entries = {}
    for key, path in report_paths.items():
        if key == "manifest_toml":
            continue
        exists = path.exists()
        report_entries[key] = {
            "path": display_path(path),
            "exists": exists,
            "sha256": sha256_file(path) if exists else None,
        }
    return {
        "schema_version": "pdf_xlsx_review_application_manifest_v1",
        "generated_at": utc_timestamp(),
        "date": config.date,
        "promotion_evidence": False,
        "official_denominator_changed": False,
        "official_denominator_change_reason": "",
        "source_review_pack_path": validation["selected_review_pack"]["path"],
        "source_review_pack_sha256": validation["selected_review_pack"]["sha256"],
        "included_row_count": application["reviewed_included_row_count"],
        "excluded_row_count": application["excluded_row_count"],
        "review_required_row_count": application["review_required_row_count"],
        "denominator_registry_diff_status": application["denominator_registry_decision"],
        "denominator_registry_update_performed": False,
        "pdf_answer_denominator": 0,
        "xlsx_answer_denominator": 0,
        "reports": report_entries,
        "commands": {
            "review_application": f"python scripts\\rag_pdf_review_application.py --date {config.date}",
            "py_compile": (
                "python -m py_compile scripts\\rag_pdf_review_application.py "
                "eval\\harness\\pdf_review_application.py"
            ),
            "pytest": "python -m pytest tests\\test_pdf_review_application.py -q",
        },
    }


def base_report(
    config: ReviewApplicationConfig,
    *,
    report_role: str,
    status: str,
    source_review_pack: Path | None,
    extra: Mapping[str, Any],
) -> dict[str, Any]:
    registry_diff = denominator_registry_git_diff(config.official_registry)
    protected_diff = protected_artifact_diff()
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": report_role,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "official_denominator_changed": False,
        "official_denominator_changed_by_harness": False,
        "official_denominator_change_reason": None,
        "official_denominator_registry_diff": registry_diff,
        "answer_generation_execution": "not_run_by_this_harness",
        "xlsx_answer_denominator": 0,
        "pdf_answer_denominator": 0,
        "answer_denominators_collapsed": False,
        "retrieval_backend": "review_pack_replay",
        "allowUnscoped": False,
        "broad_candidate_indexing_execution": "not_run_by_this_harness",
        "search_unit_indexing_cli_execution": "not_run_by_this_harness",
        "baseline_mutation_execution": "not_run_by_this_harness",
        "candidate_artifact_mutation_execution": "not_run_by_this_harness",
        "protected_artifact_diff": protected_diff,
        "source_review_pack": artifact_identity(source_review_pack) if source_review_pack else None,
        "commands": {
            "review_application": f"python scripts\\rag_pdf_review_application.py --date {config.date}",
        },
        "conservative_assumptions": [
            "Suggested labels in review packs are diagnostic provenance, not reviewed gold.",
            "Blank or malformed user review labels are excluded from official denominator candidates.",
            "FILE lookup rows are evaluated by file/document identity only unless reviewed policy says otherwise.",
            "PDF native text remains authoritative and OCR fallback is lower-trust metadata.",
            "Denominator registry mutation is proposal-only unless an explicit project convention supports it.",
        ],
        **dict(extra),
    }


def route_trace_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "pdf_source_row_count": len(rows),
        "page_lane_count": sum(1 for row in rows if row.get("page_only_evidence")),
        "content_or_section_lane_count": sum(1 for row in rows if row.get("content_lookup_route")),
        "table_lane_count": sum(1 for row in rows if row.get("table_like_evidence")),
        "file_lookup_count": sum(1 for row in rows if row.get("file_lookup_route")),
        "content_lookup_count": sum(1 for row in rows if row.get("content_lookup_route")),
        "bbox_present_count": sum(1 for row in rows if row.get("bbox_present")),
        "bbox_missing_count": sum(1 for row in rows if row.get("bbox_missing")),
        "native_pdf_evidence_count": sum(1 for row in rows if row.get("native_pdf_text_used")),
        "ocr_fallback_evidence_count": sum(1 for row in rows if row.get("ocr_fallback_used")),
        "route_mismatch_count": sum(1 for row in rows if row.get("route_mismatch_category") not in (None, "", "MATCH")),
        "review_required_count": sum(1 for row in rows if row.get("route_status") == STATUS_REVIEW_REQUIRED),
        "fail_count": sum(1 for row in rows if row.get("route_status") == STATUS_FAIL),
        "route_policy_missing_count": sum(1 for row in rows if row.get("route_mismatch_category") == FAIL_ROUTE_POLICY_MISSING),
        "route_policy_ambiguous_count": sum(1 for row in rows if row.get("route_mismatch_category") == FAIL_ROUTE_POLICY_AMBIGUOUS),
    }


def live_scoped_index_status(*, included_count: int = 0) -> dict[str, Any]:
    index_path = AI_WORKER / "eval" / "indexes" / "rag-data-pdf-candidate-v1"
    exists = index_path.exists()
    if exists and included_count == 0:
        status = "NO_REVIEWED_ROWS_ELIGIBLE_FOR_LIVE_SCOPED_RETRIEVAL"
        reason = "Scoped PDF index exists, but the selected review pack has zero complete reviewed rows eligible for live retrieval."
    elif exists:
        status = "SCOPED_INDEX_PRESENT_LIVE_CHECK_NOT_RUN_BY_THIS_HARNESS"
        reason = (
            "Scoped PDF index exists, but this harness does not mutate or build indexes; "
            "live retrieval should be wired through an explicit reviewed-row gold projection."
        )
    else:
        status = FAIL_NO_SCOPED_INDEX
        reason = "No scoped PDF index was available; no broad index was created."
    return {
        "status": status,
        "index_path": display_path(index_path),
        "exists": exists,
        "eligible_reviewed_row_count": included_count,
        "live_scoped_retrieval_executed": False,
        "allowUnscoped": False,
        "broad_indexing_executed": False,
        "diagnostic_reason": reason,
    }


def registry_denominator_snapshot(path: Path) -> dict[str, Any]:
    payload = read_json_if_exists(path)
    denominators = payload.get("official_diagnostic_denominators", {}) if isinstance(payload, Mapping) else {}
    pdf = denominators.get("track_c_pdf_c7_conservative", {}) if isinstance(denominators, Mapping) else {}
    return {
        "registry_path": display_path(path),
        "before_pdf_retrieval_positive_denominator": pdf.get("official_positive_denominator"),
        "after_pdf_retrieval_positive_denominator": pdf.get("official_positive_denominator"),
        "before_pdf_answer_denominator": pdf.get("official_pdf_answer_generation_denominator", 0),
        "after_pdf_answer_denominator": 0,
        "xlsx_answer_denominator": 0,
        "registry_mutated": False,
    }


def denominator_decision_reason(included: Sequence[Mapping[str, Any]], validation: Mapping[str, Any]) -> str:
    if not included:
        return "no_complete_reviewed_pdf_rows"
    return (
        "complete_reviewed_rows_exist_but_registry_mutation_convention_unclear_for_new_pdf_review_pack; "
        "proposal_only_report_generated"
    )


def xlsx_hidden_leakage_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), Mapping) else {}
    validation = payload.get("validation") if isinstance(payload.get("validation"), Mapping) else {}
    hidden_count = int_value(metrics.get("hidden_content_leakage_count"))
    search_errors = int_value(metrics.get("search_error_count"))
    negative_rows = int_value(payload.get("hidden_negative_row_count"))
    pass_count = int_value(metrics.get("hidden_negative_pass_count"))
    ok = bool(validation.get("ok", True)) and hidden_count == 0 and search_errors == 0 and (negative_rows == 0 or pass_count == negative_rows)
    return {
        "status": STATUS_PASS if ok else STATUS_FAIL,
        "hidden_content_leakage_count": hidden_count,
        "search_error_count": search_errors,
        "hidden_negative_row_count": negative_rows,
        "hidden_negative_pass_count": pass_count,
        "promotion_evidence": False,
    }


def application_status_for_row(row: Mapping[str, Any], *, failure_categories: Sequence[str]) -> str:
    if not complete_review_labels(row):
        return APPLICATION_STATUS_EXCLUDED_INCOMPLETE
    denominator = upper_tokens(row.get("user_denominator_policy"))
    gold = upper_tokens(row.get("user_gold_decision"))
    if denominator & DENOMINATOR_REJECT_VALUES or explicit_review_reject(row):
        return APPLICATION_STATUS_EXCLUDED_POLICY_REJECTED
    if failure_categories:
        return APPLICATION_STATUS_REVIEW_REQUIRED
    if denominator & DENOMINATOR_INCLUDE_VALUES and labels_are_official_positive(row):
        return APPLICATION_STATUS_OFFICIAL
    return APPLICATION_STATUS_DIAGNOSTIC_ONLY


def row_failure_categories(row: Mapping[str, Any], *, route_policy: str, actual_route: str) -> list[str]:
    failures: list[str] = []
    if not complete_review_labels(row):
        failures.append(FAIL_REVIEW_LABEL_MISSING)
    else:
        failures.extend(review_label_failures(row))
    mismatch = route_mismatch_category(route_policy, actual_route)
    if mismatch not in (None, "", "MATCH"):
        failures.append(mismatch)
    if complete_review_labels(row):
        table = policy_state(row, "table")
        page = policy_state(row, "page")
        bbox = policy_state(row, "bbox")
        if is_table_lane(row) and table == "MISSING":
            failures.append(FAIL_TABLE_POLICY_MISSING)
        if is_page_lane(row) and page == "MISSING":
            failures.append(FAIL_PAGE_POLICY_MISSING)
        if bbox_reference_present(row) and bbox == "MISSING":
            failures.append(FAIL_BBOX_POLICY_MISSING)
        if table == "REJECT":
            failures.append(FAIL_TABLE_POLICY_REJECTED)
        if page == "REJECT":
            failures.append(FAIL_PAGE_POLICY_REJECTED)
        if bbox == "REJECT":
            failures.append(FAIL_BBOX_POLICY_REJECTED)
    return dedupe(failures)


def reviewed_policy_status(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        "table": policy_state(row, "table"),
        "page": policy_state(row, "page"),
        "bbox": policy_state(row, "bbox"),
        "native_ocr": policy_state(row, "ocr"),
    }


def policy_state(row: Mapping[str, Any], policy: str) -> str:
    if not complete_review_labels(row):
        return "MISSING"
    haystack = " ".join(
        [
            clean(row.get("user_expected_evidence_policy")),
            clean(row.get("user_issue_tags")),
            clean(row.get("user_notes")),
        ]
    )
    tokens = upper_tokens(haystack)
    policy_name = policy.upper()
    if any(is_scoped_policy_token(token, policy_name, POLICY_REJECT_VALUES) for token in tokens):
        return "REJECT"
    if any(is_scoped_policy_token(token, policy_name, POLICY_ALLOW_VALUES) for token in tokens):
        return "ALLOW"
    return "MISSING"


def is_scoped_policy_token(token: str, policy_name: str, values: set[str]) -> bool:
    if token in {f"{policy_name}_{value}" for value in values}:
        return True
    if token in {f"{value}_{policy_name}" for value in values}:
        return True
    if any(token.startswith(f"{policy_name}_{value}") for value in values):
        return True
    if any(token.startswith(f"{value}_{policy_name}") for value in values):
        return True
    return False


def review_label_failures(row: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    gold = exact_upper(row.get("user_gold_decision"))
    answerability = exact_upper(row.get("user_answerability_label"))
    relevance = exact_upper(row.get("user_relevance_label"))

    if gold not in GOLD_POSITIVE_VALUES:
        failures.append(FAIL_GOLD_DECISION_NOT_POSITIVE if gold in GOLD_REJECT_VALUES else FAIL_REVIEW_LABEL_MALFORMED)
    if answerability not in ANSWERABILITY_POSITIVE_VALUES:
        failures.append(
            FAIL_ANSWERABILITY_NOT_POSITIVE
            if answerability in ANSWERABILITY_REJECT_VALUES
            else FAIL_REVIEW_LABEL_MALFORMED
        )
    if relevance not in RELEVANCE_POSITIVE_VALUES:
        failures.append(FAIL_RELEVANCE_NOT_RELEVANT if relevance in RELEVANCE_REJECT_VALUES else FAIL_REVIEW_LABEL_MALFORMED)
    return dedupe(failures)


def labels_are_official_positive(row: Mapping[str, Any]) -> bool:
    return not review_label_failures(row)


def explicit_review_reject(row: Mapping[str, Any]) -> bool:
    gold = exact_upper(row.get("user_gold_decision"))
    answerability = exact_upper(row.get("user_answerability_label"))
    relevance = exact_upper(row.get("user_relevance_label"))
    return bool(
        gold in GOLD_REJECT_VALUES
        or answerability in ANSWERABILITY_REJECT_VALUES
        or relevance in RELEVANCE_REJECT_VALUES
    )


def classify_reviewed_route_policy(row: Mapping[str, Any]) -> str:
    if not complete_review_labels(row):
        return "MISSING"
    values = " ".join(
        [
            clean(row.get("user_expected_evidence_policy")),
            clean(row.get("user_denominator_policy")),
            clean(row.get("user_issue_tags")),
        ]
    )
    tokens = upper_tokens(values)
    file_hit = bool(
        tokens & ROUTE_POLICY_FILE_VALUES
        or any("FILE_LOOKUP" in token or "EXPECTED_FILE_NAME" in token or "DOCUMENT_IDENTITY" in token for token in tokens)
    )
    content_hit = bool(tokens & ROUTE_POLICY_CONTENT_VALUES or any("CONTENT_LOOKUP" in token for token in tokens))
    if file_hit and content_hit:
        return "AMBIGUOUS"
    if file_hit:
        return ROUTE_PDF_FILE
    if content_hit:
        return ROUTE_PDF_CONTENT
    return "MISSING"


def actual_route_from_row(row: Mapping[str, Any]) -> str:
    return ROUTE_PDF_FILE if is_file_lookup_row(row) else ROUTE_PDF_CONTENT


def route_mismatch_category(route_policy: str, actual_route: str) -> str | None:
    if route_policy == "MISSING":
        return FAIL_ROUTE_POLICY_MISSING
    if route_policy == "AMBIGUOUS":
        return FAIL_ROUTE_POLICY_AMBIGUOUS
    if route_policy == ROUTE_PDF_FILE and actual_route == ROUTE_PDF_CONTENT:
        return FAIL_FILE_EXPECTED_CONTENT_ACTUAL
    if route_policy == ROUTE_PDF_CONTENT and actual_route == ROUTE_PDF_FILE:
        return FAIL_CONTENT_EXPECTED_FILE_ACTUAL
    return "MATCH"


def exclusion_reason(application_status: str, failure_categories: Sequence[str]) -> str:
    if application_status == APPLICATION_STATUS_EXCLUDED_INCOMPLETE:
        return "missing_required_user_review_labels"
    if application_status == APPLICATION_STATUS_EXCLUDED_POLICY_REJECTED:
        return "review_policy_rejected"
    if application_status == APPLICATION_STATUS_REVIEW_REQUIRED:
        return first_or_default(failure_categories, "review_required_policy_or_route_issue")
    if application_status == APPLICATION_STATUS_DIAGNOSTIC_ONLY:
        return "diagnostic_only_not_denominator_candidate"
    return ""


def route_reason(row: Mapping[str, Any]) -> str:
    if row.get("actual_route") == ROUTE_PDF_FILE:
        return "Review-pack row is a PDF FILE lookup lane; page/bbox/table fields are references unless reviewed policy allows them."
    return "Review-pack row is a PDF CONTENT lookup lane; expected evidence and policy labels are required for official eligibility."


def is_file_lookup_row(row: Mapping[str, Any]) -> bool:
    lane = clean(row.get("retrieval_lane") or row.get("review_lane") or row.get("query_surface_type")).upper()
    track = clean(row.get("track")).upper()
    tags = clean(row.get("risk_tags")).upper()
    return "FILE_LOOKUP" in lane or "FILE_LOOKUP" in track or "PDF_FILE_LOOKUP" in tags


def is_table_lane(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        clean(row.get(key))
        for key in ("retrieval_lane", "review_group", "review_lane", "risk_tags", "query_surface_type")
    ).upper()
    return "TABLE" in text


def is_page_lane(row: Mapping[str, Any]) -> bool:
    lane = clean(row.get("retrieval_lane") or row.get("review_lane")).upper()
    if is_file_lookup_row(row):
        return False
    return "PAGE" in lane or bool(clean(row.get("expected_page_no") or row.get("expected_page_label")))


def bbox_reference_present(row: Mapping[str, Any]) -> bool:
    return bool(clean(row.get("expected_bbox")))


def complete_review_labels(row: Mapping[str, Any]) -> bool:
    return all(clean(row.get(column)) for column in REQUIRED_REVIEW_COLUMNS)


def query_text(row: Mapping[str, Any]) -> str:
    return clean(row.get("query_text") or row.get("query") or row.get("new_query") or row.get("old_query"))


def csv_fieldnames(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or [])


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_toml(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Auto-generated diagnostic manifest. Reports are diagnostic-only.", ""]
    simple_keys = [
        "schema_version",
        "generated_at",
        "date",
        "promotion_evidence",
        "official_denominator_changed",
        "official_denominator_change_reason",
        "source_review_pack_path",
        "source_review_pack_sha256",
        "included_row_count",
        "excluded_row_count",
        "review_required_row_count",
        "denominator_registry_diff_status",
        "denominator_registry_update_performed",
        "pdf_answer_denominator",
        "xlsx_answer_denominator",
    ]
    for key in simple_keys:
        lines.append(f"{key} = {toml_value(payload.get(key))}")
    lines.append("")
    lines.append("[reports]")
    for key, value in (payload.get("reports") or {}).items():
        if isinstance(value, Mapping):
            lines.append(f'{key}_path = {toml_value(value.get("path"))}')
            lines.append(f'{key}_sha256 = {toml_value(value.get("sha256"))}')
            lines.append(f'{key}_exists = {toml_value(value.get("exists"))}')
    lines.append("")
    lines.append("[commands]")
    for key, value in (payload.get("commands") or {}).items():
        lines.append(f"{key} = {toml_value(value)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_validation_markdown(payload: Mapping[str, Any]) -> str:
    return simple_markdown(
        "PDF Review Pack Validation",
        payload,
        [
            ("Selected pack", payload.get("selected_review_pack", {}).get("path")),
            ("Rows", payload.get("row_count")),
            ("Complete reviewed rows", payload.get("complete_reviewed_row_count")),
            ("Incomplete rows", payload.get("incomplete_review_row_count")),
            ("FILE rows", payload.get("file_lookup_row_count")),
            ("CONTENT rows", payload.get("content_lookup_row_count")),
            ("Table rows", payload.get("table_lane_row_count")),
            ("User columns blank", payload.get("user_columns_blank")),
        ],
    )


def render_application_markdown(payload: Mapping[str, Any]) -> str:
    return simple_markdown(
        "PDF Reviewed Retrieval Evidence Application",
        payload,
        [
            ("Source rows", payload.get("source_row_count")),
            ("Included official candidates", payload.get("reviewed_included_row_count")),
            ("Excluded", payload.get("excluded_row_count")),
            ("Review required", payload.get("review_required_row_count")),
            ("Proposal-only denominator", payload.get("proposed_pdf_retrieval_evidence_denominator")),
            ("Registry update performed", payload.get("denominator_registry_update_performed")),
        ],
    )


def render_route_markdown(payload: Mapping[str, Any]) -> str:
    summary = payload.get("pdf_reviewed_route_summary") or {}
    return simple_markdown(
        "PDF Reviewed Route Trace Diagnostic",
        payload,
        [
            ("PDF source rows", summary.get("pdf_source_row_count")),
            ("Page lane", summary.get("page_lane_count")),
            ("Content/section lane", summary.get("content_or_section_lane_count")),
            ("Table lane", summary.get("table_lane_count")),
            ("FILE lookup", summary.get("file_lookup_count")),
            ("CONTENT lookup", summary.get("content_lookup_count")),
            ("BBox present", summary.get("bbox_present_count")),
            ("BBox missing", summary.get("bbox_missing_count")),
            ("Route mismatch", summary.get("route_mismatch_count")),
            ("REVIEW_REQUIRED", summary.get("review_required_count")),
            ("FAIL", summary.get("fail_count")),
        ],
    )


def render_agentic_markdown(payload: Mapping[str, Any]) -> str:
    summary = payload.get("agentic_retry_summary") or {}
    return simple_markdown(
        "PDF Reviewed Agentic Route Loop Diagnostic",
        payload,
        [
            ("Cases", summary.get("case_count")),
            ("Diagnostic fixtures", summary.get("diagnostic_fixture_case_count")),
            ("Retry exhausted", summary.get("retry_exhausted_count")),
            ("Max attempt count", summary.get("max_attempt_count")),
            ("allowUnscoped true count", summary.get("allow_unscoped_true_count")),
            ("Retry path exercised", summary.get("retry_path_exercised")),
        ],
    )


def render_xlsx_markdown(payload: Mapping[str, Any]) -> str:
    hidden = payload.get("xlsx_hidden_leakage_pre_probe") or {}
    return simple_markdown(
        "XLSX Strict Silver Generation Diagnostic",
        payload,
        [
            ("Strict wrapper intact", payload.get("xlsx_strict_wrapper_path_intact")),
            ("Generation status", payload.get("silver_generation_status")),
            ("Hidden leakage status", hidden.get("status")),
            ("Hidden leakage count", hidden.get("hidden_content_leakage_count")),
            ("Answer generation", payload.get("answer_generation_execution")),
        ],
    )


def simple_markdown(title: str, payload: Mapping[str, Any], rows: Sequence[tuple[str, Any]]) -> str:
    lines = [
        f"# {title}",
        "",
        f"- Status: `{payload.get('status')}`",
        "- Promotion evidence: `false`",
        f"- Official denominator changed: `{str(payload.get('official_denominator_changed')).lower()}`",
        "- PDF answer denominator: `0`",
        "- XLSX answer denominator: `0`",
        "- Broad candidate indexing: `not_run_by_this_harness`",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in rows:
        lines.append(f"| {key} | {markdown_value(value)} |")
    lines.extend(["", "## Guardrails", "", "```json"])
    guardrails = {
        "promotion_evidence": payload.get("promotion_evidence"),
        "official_denominator_changed": payload.get("official_denominator_changed"),
        "answer_generation_execution": payload.get("answer_generation_execution"),
        "allowUnscoped": payload.get("allowUnscoped"),
        "broad_candidate_indexing_execution": payload.get("broad_candidate_indexing_execution"),
        "candidate_artifact_mutation_execution": payload.get("candidate_artifact_mutation_execution"),
    }
    lines.append(json.dumps(guardrails, ensure_ascii=False, indent=2))
    lines.extend(["```", "", "## Commands", ""])
    for key, value in (payload.get("commands") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    if payload.get("conservative_assumptions"):
        lines.extend(["", "## Conservative Assumptions", ""])
        for item in payload.get("conservative_assumptions") or []:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def denominator_registry_git_diff(path: Path) -> dict[str, Any]:
    result = git_capture(["git", "diff", "--", display_path(path)])
    return {
        "path": display_path(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() else None,
        "git_diff_empty": result["ok"] and not result["stdout"].strip(),
        "official_denominator_changed": result["ok"] and bool(result["stdout"].strip()),
        "git_diff_error": None if result["ok"] else result["stderr"],
    }


def git_capture(args: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc)}
    return {"ok": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr}


def artifact_identity(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"path": None, "exists": False, "sha256": None}
    return {
        "path": display_path(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() and path.is_file() else None,
    }


def resolve_report_path(value: Any) -> Path:
    path = Path(clean(value))
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "ai-worker":
        return ROOT / path
    if path.parts and path.parts[0] == "eval":
        return AI_WORKER / path
    return path


def strip_path_object(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {key: (display_path(value) if isinstance(value, Path) else value) for key, value in metadata.items() if key != "path"}


def upper_tokens(value: Any) -> set[str]:
    text = clean(value).upper().replace(";", " ").replace(",", " ").replace("|", " ").replace("/", " ")
    return {token for token in text.split() if token}


def exact_upper(value: Any) -> str:
    return clean(value).upper()


def int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def first_or_default(values: Sequence[str], default: str) -> str:
    return clean(values[0]) if values else default


def clean(value: Any) -> str:
    return str(value or "").strip()


def markdown_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return ""
    return str(value)


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return '""'
    return json.dumps(str(value), ensure_ascii=False)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
