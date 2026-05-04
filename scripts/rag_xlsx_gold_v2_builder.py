"""Build an XLSX gold v2 candidate manifest from v0, v1, and review decisions.

This script is report-only with respect to promotion and baselines. It does
not run retrieval evaluation, set promotion_evidence=true, update immutable
baseline descriptors, or overwrite v0/v1 gold files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


DEFAULT_GOLD_V0 = Path("eval/gold_queries_v0.csv")
DEFAULT_XLSX_V1 = Path("eval/gold_queries_xlsx_v1.csv")
DEFAULT_REVIEW_DECISIONS = Path("reports/rag_xlsx_query_evidence_review_decisions.json")
DEFAULT_DIAGNOSTIC_REPORT = Path("reports/rag_retrieval_eval_xlsx_vector_diagnostic_report.json")
DEFAULT_INGEST_MANIFEST = Path("rag-data-xlsx-candidate-v1/ingest_manifest.json")
DEFAULT_OUTPUT_CSV = Path("eval/gold_queries_xlsx_v2.csv")
DEFAULT_BUILD_REPORT = Path("reports/rag_xlsx_gold_v2_build_report.json")
DEFAULT_HIDDEN_NEGATIVE_PLAN = Path("reports/rag_xlsx_hidden_negative_eval_plan.json")
DEFAULT_FORMULA_DATE_REVIEW = Path("reports/rag_xlsx_formula_date_contract_review.json")
DEFAULT_CHUNK_GRANULARITY_REVIEW = Path("reports/rag_xlsx_chunk_granularity_review.json")
DEFAULT_DATASET_ID = "gold_queries_xlsx_v2"
DEFAULT_DATASET_VERSION = "xlsx_v2_candidate_manifest_50"

RANGE_POLICY_TO_V2 = {
    "exact_match": "EXACT_RANGE",
    "contains_expected": "CONTAINS_EXPECTED",
    "overlaps_expected": "OVERLAP_RANGE",
    "none": "NONE",
    "": "NONE",
}
RANGE_POLICY_TO_HARNESS = {
    "EXACT_RANGE": "exact_match",
    "CONTAINS_EXPECTED": "contains_expected",
    "OVERLAP_RANGE": "overlaps_expected",
    "NONE": "none",
}
HARNESS_COLUMNS = [
    "query_id",
    "bucket",
    "query",
    "expected_file_name",
    "expected_document_version_id",
    "expected_chunk_type",
    "expected_location_type",
    "expected_sheet_name",
    "expected_cell_range",
    "expected_table_id",
    "expected_physical_page_index",
    "expected_page_no",
    "expected_page_label",
    "expected_bbox",
    "expected_answer_text",
    "must_contain_terms",
    "must_not_contain_terms",
    "range_match_policy",
    "hidden_policy",
    "requires_formula_value",
    "requires_formatted_value",
    "requires_aggregation",
    "source_sample_id",
    "label_status",
    "notes",
]
MINIMUM_V2_COLUMNS = [
    *HARNESS_COLUMNS,
    "v2_label_status",
    "v2_range_match_policy",
    "policy_label",
    "eval_purpose",
    "review_status",
]
EXTRA_V2_COLUMNS = [
    "harness_range_match_policy",
    "contract_value_surface",
    "embedding_text_surface_status",
    "current_evidence_summary",
    "source_label_status",
    "review_decision",
    "review_category",
    "review_reason_code",
    "promotion_eval_eligible",
    "cleanup_source_query_id",
]
V2_FIELDNAMES = MINIMUM_V2_COLUMNS + EXTRA_V2_COLUMNS

REQUIRED_USER_V2_COLUMNS = [
    "query_id",
    "bucket",
    "query",
    "expected_file_name",
    "expected_document_version_id",
    "expected_location_type",
    "expected_sheet_name",
    "expected_cell_range",
    "v2_range_match_policy",
    "expected_answer_text",
    "must_contain_terms",
    "source_sample_id",
    "v2_label_status",
    "policy_label",
    "eval_purpose",
    "review_status",
    "notes",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    gold_v0_path = Path(args.gold_v0)
    xlsx_v1_path = Path(args.xlsx_v1)
    review_path = Path(args.review_decisions)
    diagnostic_path = Path(args.diagnostic_report)
    ingest_manifest_path = Path(args.ingest_manifest)
    ingest_manifest = read_json(ingest_manifest_path) if ingest_manifest_path.exists() else {}

    build = build_v2(
        gold_v0_rows=read_csv_rows(gold_v0_path),
        xlsx_v1_rows=read_csv_rows(xlsx_v1_path),
        review=read_json(review_path),
        diagnostic=read_json(diagnostic_path),
        ingest_manifest=ingest_manifest,
        gold_v0_path=gold_v0_path,
        xlsx_v1_path=xlsx_v1_path,
        review_path=review_path,
        diagnostic_path=diagnostic_path,
        ingest_manifest_path=ingest_manifest_path,
        output_csv_path=Path(args.output_csv),
        dataset_id=args.dataset_id,
        dataset_version=args.dataset_version,
    )

    write_csv(Path(args.output_csv), build["v2_rows"])
    dataset_sha256 = sha256_file(Path(args.output_csv))
    build_report = build["build_report"]
    build_report["dataset_sha256"] = dataset_sha256
    build_report["dataset"]["sha256"] = dataset_sha256
    write_json(Path(args.build_report), build_report)
    write_json(Path(args.hidden_negative_plan), build["hidden_negative_plan"])
    write_json(Path(args.formula_date_review), build["formula_date_review"])
    write_json(Path(args.chunk_granularity_review), build["chunk_granularity_review"])

    print_report(build_report)
    return 0


def build_v2(
    *,
    gold_v0_rows: list[dict[str, str]],
    xlsx_v1_rows: list[dict[str, str]],
    review: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
    ingest_manifest: Mapping[str, Any],
    gold_v0_path: Path,
    xlsx_v1_path: Path,
    review_path: Path,
    diagnostic_path: Path,
    ingest_manifest_path: Path,
    output_csv_path: Path,
    dataset_id: str,
    dataset_version: str,
) -> dict[str, Any]:
    decisions = list(review.get("decisions") or [])
    decision_by_id = {str(row.get("query_id") or ""): row for row in decisions}
    positive_v1_ids = {row.get("query_id", "") for row in xlsx_v1_rows}
    xlsx_source_rows = [
        row for row in gold_v0_rows
        if row.get("expected_location_type") == "xlsx" or row.get("bucket") == "mixed_text_table"
    ]

    v2_rows = [
        build_v2_row(row, decision_by_id.get(row.get("query_id", ""), {}), row.get("query_id", "") in positive_v1_ids, ingest_manifest)
        for row in xlsx_source_rows
    ]
    missing_review_ids = [
        row.get("query_id", "")
        for row in xlsx_source_rows
        if row.get("query_id", "") not in decision_by_id
    ]

    label_counts = Counter(row["v2_label_status"] for row in v2_rows)
    harness_label_counts = Counter(row["label_status"] for row in v2_rows)
    bucket_counts = Counter(row["bucket"] for row in v2_rows)
    eval_purpose_counts = Counter(row["eval_purpose"] for row in v2_rows)
    policy_counts = Counter(row["v2_range_match_policy"] for row in v2_rows)
    harness_policy_counts = Counter(row["range_match_policy"] for row in v2_rows)
    decision_counts = Counter(row["review_decision"] for row in v2_rows)
    harness_validation = validate_v2_with_current_harness(v2_rows)

    hidden_negative_rows = [
        row for row in v2_rows
        if row["v2_label_status"] == "negative_hidden_policy"
    ]
    formula_date_review = build_formula_date_review(
        v2_rows=v2_rows,
        review=review,
        diagnostic=diagnostic,
        ingest_manifest=ingest_manifest,
        source_paths={
            "gold_v0": str(gold_v0_path),
            "review_decisions": str(review_path),
            "diagnostic_report": str(diagnostic_path),
            "ingest_manifest": str(ingest_manifest_path),
        },
    )
    chunk_review = build_chunk_granularity_review(
        v2_rows=v2_rows,
        review=review,
        source_paths={
            "gold_v0": str(gold_v0_path),
            "review_decisions": str(review_path),
            "diagnostic_report": str(diagnostic_path),
        },
    )
    hidden_plan = build_hidden_negative_plan(
        hidden_negative_rows=hidden_negative_rows,
        review=review,
        diagnostic=diagnostic,
        source_paths={
            "gold_v0": str(gold_v0_path),
            "review_decisions": str(review_path),
            "diagnostic_report": str(diagnostic_path),
        },
    )

    build_report = {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "COMPLETED_WITH_WARNINGS" if missing_review_ids else "COMPLETED",
        "report_role": "xlsx_gold_v2_build_report",
        "promotion_evidence": False,
        "evidence_role": "gold_v2_candidate_manifest",
        "source_gold_v0": str(gold_v0_path),
        "source_xlsx_v1": str(xlsx_v1_path),
        "source_review_decisions": str(review_path),
        "source_diagnostic_report": str(diagnostic_path),
        "source_ingest_manifest": str(ingest_manifest_path),
        "dataset": {
            "path": str(output_csv_path),
            "dataset_id": dataset_id,
            "version": dataset_version,
            "row_count": len(v2_rows),
            "sha256": None,
        },
        "row_count": len(v2_rows),
        "positive_v1_source_count": len(positive_v1_ids),
        "excluded_or_deferred_source_count": sum(1 for row in v2_rows if row["v2_label_status"] in {"excluded", "deferred"}),
        "non_positive_source_count": sum(1 for row in v2_rows if row["v2_label_status"] != "positive"),
        "reclassified_from_v1_exclusion_count": sum(1 for row in v2_rows if row["v2_label_status"] != "positive"),
        "hidden_negative_count": len(hidden_negative_rows),
        "bucket_distribution": dict(sorted(bucket_counts.items())),
        "v2_label_status_distribution": dict(sorted(label_counts.items())),
        "harness_label_status_distribution": dict(sorted(harness_label_counts.items())),
        "eval_purpose_distribution": dict(sorted(eval_purpose_counts.items())),
        "v2_range_match_policy_distribution": dict(sorted(policy_counts.items())),
        "harness_range_match_policy_distribution": dict(sorted(harness_policy_counts.items())),
        "review_decision_distribution": dict(sorted(decision_counts.items())),
        "missing_review_decision_query_ids": missing_review_ids,
        "current_harness_validation": harness_validation,
        "required_user_v2_columns": REQUIRED_USER_V2_COLUMNS,
        "generated_reports": {
            "hidden_negative_eval_plan": str(DEFAULT_HIDDEN_NEGATIVE_PLAN),
            "formula_date_contract_review": str(DEFAULT_FORMULA_DATE_REVIEW),
            "chunk_granularity_review": str(DEFAULT_CHUNK_GRANULARITY_REVIEW),
        },
        "baseline_status": {
            "promotion_executed": False,
            "promotion_evidence": False,
            "immutable_baseline_descriptor_modified": False,
            "baseline_artifact_or_hash_modified": False,
            "gold_queries_v0_modified": False,
            "gold_queries_xlsx_v1_modified": False,
        },
        "important_decisions": [
            "V2 is a candidate manifest containing positive, hidden-negative, excluded, and deferred labels.",
            "Hidden-negative rows are separated from positive retrieval metrics.",
            "Current harness columns remain valid; v2 label/range design values live in v2_label_status and v2_range_match_policy.",
            "Formula/date rows are classified by raw formula, cached value, display formatted value, or date/number format contract.",
            "No thresholds, hybrid search, reranking, parser features, promotion flags, or immutable baseline files are changed.",
        ],
        "warnings": [
            "Do not run this full v2 manifest as a positive retrieval eval without filtering v2_label_status=positive.",
            "Rows marked negative_hidden_policy require separate hidden leakage metrics, not Hit@K.",
            "Rows marked deferred or excluded need manual contract resolution before promotion-grade positive scoring.",
        ],
        "notes": [
            "The source diagnostic report remains diagnostic-only.",
            "This builder does not call scripts/rag_retrieval_eval.py.",
            "CSV output uses utf-8-sig to match existing gold CSV readers.",
        ],
    }

    return {
        "v2_rows": v2_rows,
        "build_report": build_report,
        "hidden_negative_plan": hidden_plan,
        "formula_date_review": formula_date_review,
        "chunk_granularity_review": chunk_review,
    }


def validate_v2_with_current_harness(rows: list[dict[str, str]]) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    ai_worker = root / "ai-worker"
    if str(ai_worker) not in sys.path:
        sys.path.insert(0, str(ai_worker))
    try:
        from eval.harness.rag_ingestion_retrieval_eval import validate_gold_rows  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - defensive CLI report path
        return {
            "ok": False,
            "import_error": f"{type(exc).__name__}: {exc}",
            "row_count": len(rows),
            "error_count": None,
            "row_error_count": None,
        }

    result = validate_gold_rows(rows)
    return {
        "ok": result.ok,
        "row_count": result.row_count,
        "error_count": len(result.errors),
        "row_error_count": len(result.row_errors),
        "bucket_counts": result.bucket_counts,
        "sample_errors": result.errors[:10],
    }


def build_v2_row(
    source: Mapping[str, str],
    decision: Mapping[str, Any],
    is_positive_v1: bool,
    ingest_manifest: Mapping[str, Any],
) -> dict[str, str]:
    review_decision = str(decision.get("decision") or "MISSING_REVIEW_DECISION")
    review_category = str(decision.get("category") or "")
    policy_label = str(decision.get("policy_label") or ("positive" if is_positive_v1 else "unreviewed"))
    v2_label_status = classify_label_status(review_decision, is_positive_v1)
    eval_purpose = classify_eval_purpose(source, review_decision, review_category, v2_label_status)
    v2_range_policy = classify_range_policy(source, decision, v2_label_status)
    harness_policy = RANGE_POLICY_TO_HARNESS.get(v2_range_policy, "none")
    contract_surface = classify_contract_surface(source)
    surface_status = embedding_surface_status(source, ingest_manifest, contract_surface)
    review_status = classify_review_status(review_decision, review_category, v2_label_status)
    hidden_policy = "negative" if v2_label_status == "negative_hidden_policy" else source.get("hidden_policy", "")
    harness_label_status = source.get("label_status", "") or "bound"

    notes = "; ".join(
        part for part in [
            source.get("notes", ""),
            f"v2_review={review_status}",
            f"review_reason={decision.get('reason_code')}" if decision.get("reason_code") else "",
            "hidden negative is not a positive retrieval metric" if v2_label_status == "negative_hidden_policy" else "",
            "range policy candidate only; no harness behavior changed" if v2_label_status in {"deferred", "excluded"} else "",
        ]
        if part
    )

    row = {
        "query_id": source.get("query_id", ""),
        "bucket": source.get("bucket", ""),
        "query": source.get("query", ""),
        "expected_file_name": source.get("expected_file_name", ""),
        "expected_document_version_id": source.get("expected_document_version_id", ""),
        "expected_location_type": source.get("expected_location_type", ""),
        "expected_sheet_name": source.get("expected_sheet_name", ""),
        "expected_cell_range": source.get("expected_cell_range", ""),
        "expected_table_id": source.get("expected_table_id", ""),
        "expected_physical_page_index": source.get("expected_physical_page_index", ""),
        "expected_page_no": source.get("expected_page_no", ""),
        "expected_page_label": source.get("expected_page_label", ""),
        "expected_bbox": source.get("expected_bbox", ""),
        "expected_answer_text": source.get("expected_answer_text", ""),
        "must_contain_terms": source.get("must_contain_terms", ""),
        "must_not_contain_terms": source.get("must_not_contain_terms", ""),
        "range_match_policy": harness_policy,
        "hidden_policy": hidden_policy,
        "requires_formula_value": source.get("requires_formula_value", ""),
        "requires_formatted_value": source.get("requires_formatted_value", ""),
        "requires_aggregation": source.get("requires_aggregation", ""),
        "source_sample_id": source.get("source_sample_id", ""),
        "label_status": harness_label_status,
        "notes": notes,
        "v2_label_status": v2_label_status,
        "v2_range_match_policy": v2_range_policy,
        "policy_label": policy_label,
        "eval_purpose": eval_purpose,
        "review_status": review_status,
        "expected_chunk_type": source.get("expected_chunk_type", ""),
        "source_label_status": source.get("label_status", ""),
        "review_decision": review_decision,
        "review_category": review_category,
        "review_reason_code": str(decision.get("reason_code") or ""),
        "promotion_eval_eligible": "true" if is_positive_v1 else "false",
        "harness_range_match_policy": harness_policy,
        "contract_value_surface": contract_surface,
        "embedding_text_surface_status": surface_status["status"],
        "current_evidence_summary": surface_status["summary"],
        "cleanup_source_query_id": source.get("query_id", ""),
    }
    return {field: row.get(field, "") for field in V2_FIELDNAMES}


def classify_label_status(review_decision: str, is_positive_v1: bool) -> str:
    if is_positive_v1 or review_decision == "KEEP_AS_POSITIVE":
        return "positive"
    if review_decision == "RELABEL_AS_NEGATIVE_HIDDEN_POLICY":
        return "negative_hidden_policy"
    if review_decision == "EXCLUDE_FROM_PROMOTION_EVAL":
        return "excluded"
    return "deferred"


def classify_eval_purpose(
    source: Mapping[str, str],
    review_decision: str,
    review_category: str,
    label_status: str,
) -> str:
    bucket = source.get("bucket", "")
    if label_status == "negative_hidden_policy":
        return "hidden_policy_negative"
    if bucket == "xlsx_formula_value":
        return "formula_display_value"
    if bucket == "xlsx_date_number_format":
        return "date_number_format"
    if review_category == "chunk_granularity" or review_decision == "REQUIRE_CHUNK_GRANULARITY_FIX":
        return "chunk_granularity"
    if review_category in {"table_range_strictness", "gold_binding"}:
        return "table_range_policy"
    if bucket == "xlsx_header_ambiguous":
        return "table_range_policy"
    return "retrieval_positive"


def classify_review_status(review_decision: str, review_category: str, label_status: str) -> str:
    if label_status == "positive":
        return "ready_positive"
    if label_status == "negative_hidden_policy":
        return "negative_policy_candidate"
    if review_decision == "RELAX_MATCH_POLICY_TO_RANGE_OVERLAP":
        return "deferred_range_overlap_contract"
    if review_decision == "REBIND_EXPECTED_SHEET_OR_RANGE":
        return "deferred_gold_rebind"
    if review_decision == "REQUIRE_CHUNK_GRANULARITY_FIX":
        return "deferred_chunk_granularity"
    if review_category == "formula_date_contract":
        return "excluded_from_positive_pending_formula_date_contract"
    if review_category == "table_range_strictness":
        return "excluded_from_positive_pending_table_range_contract"
    return "excluded_or_deferred_from_positive_eval"


def classify_range_policy(source: Mapping[str, str], decision: Mapping[str, Any], label_status: str) -> str:
    if label_status == "negative_hidden_policy":
        return "NONE"
    if decision.get("decision") == "RELAX_MATCH_POLICY_TO_RANGE_OVERLAP":
        return "OVERLAP_RANGE"

    observed = observed_best_range_policy(str(source.get("expected_cell_range") or ""), decision)
    if observed:
        return observed
    return RANGE_POLICY_TO_V2.get(str(source.get("range_match_policy") or "").strip(), "NONE")


def observed_best_range_policy(expected_range: str, decision: Mapping[str, Any]) -> str:
    expected = parse_a1_range(expected_range)
    if not expected:
        return ""

    exact = False
    contains = False
    overlap = False
    hits = list(decision.get("supporting_hits") or []) + list(decision.get("top_hits") or [])
    for hit in hits:
        if not hit.get("xlsx_sheet_match"):
            continue
        actual = parse_a1_range(str(hit.get("cell_range") or ""))
        if not actual:
            continue
        exact = exact or expected == actual
        contains = contains or range_contains(actual, expected)
        overlap = overlap or ranges_overlap(expected, actual)
    if exact:
        return "EXACT_RANGE"
    if contains:
        return "CONTAINS_EXPECTED"
    if overlap:
        return "OVERLAP_RANGE"
    return ""


def classify_contract_surface(source: Mapping[str, str]) -> str:
    bucket = source.get("bucket", "")
    query = source.get("query", "")
    must_terms = source.get("must_contain_terms", "")
    requires_formula = truthy(source.get("requires_formula_value"))
    requires_formatted = truthy(source.get("requires_formatted_value"))
    if bucket == "xlsx_formula_value" and requires_formula:
        if looks_like_formula_expression(query) or any(looks_like_formula_expression(term) for term in split_terms(must_terms)):
            return "RAW_FORMULA"
        return "RAW_FORMULA_OR_FORMULA_HEADER"
    if bucket == "xlsx_date_number_format":
        if looks_like_date(query):
            return "DATE_FORMATTED_VALUE"
        if requires_formatted:
            return "DISPLAY_FORMATTED_VALUE"
        return "CACHED_VALUE"
    if requires_formatted:
        return "DISPLAY_FORMATTED_VALUE"
    return "NONE"


def embedding_surface_status(
    source: Mapping[str, str],
    ingest_manifest: Mapping[str, Any],
    contract_surface: str,
) -> dict[str, str]:
    samples = list(ingest_manifest.get("embed_text_samples") or [])
    if not samples:
        return {
            "status": "UNKNOWN_NO_EMBED_TEXT_SAMPLE",
            "summary": "No embedding text samples were available in the ingest manifest.",
        }

    expected_file = str(source.get("expected_file_name") or "")
    query = str(source.get("query") or "")
    terms = split_terms(source.get("must_contain_terms", ""))
    target_terms = [term for term in [query, *terms] if term]
    same_file_samples = [
        sample for sample in samples
        if expected_file and expected_file in str(sample.get("preview") or "")
    ]
    searchable_samples = same_file_samples or samples
    matched_terms: list[str] = []
    for term in target_terms:
        if any(term in str(sample.get("preview") or "") for sample in searchable_samples):
            matched_terms.append(term)

    if contract_surface == "NONE":
        return {
            "status": "NOT_APPLICABLE",
            "summary": "No formula/date surface contract is required for this row.",
        }
    if matched_terms and len(matched_terms) == len(target_terms):
        return {
            "status": "PRESENT_IN_INGEST_MANIFEST_SAMPLE",
            "summary": "All query and must-contain surfaces were observed in ingest manifest preview samples.",
        }
    if matched_terms:
        return {
            "status": "PARTIAL_IN_INGEST_MANIFEST_SAMPLE",
            "summary": f"Observed terms: {', '.join(matched_terms)}. Full embedding text was not available in report input.",
        }
    return {
        "status": "NOT_OBSERVED_IN_REPORT_INPUT",
        "summary": "The required surface was not observed in diagnostic report or ingest manifest preview samples.",
    }


def build_formula_date_review(
    *,
    v2_rows: list[Mapping[str, str]],
    review: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
    ingest_manifest: Mapping[str, Any],
    source_paths: Mapping[str, str],
) -> dict[str, Any]:
    rows = [
        row for row in v2_rows
        if row.get("bucket") in {"xlsx_formula_value", "xlsx_date_number_format"}
    ]
    review_rows = []
    for row in rows:
        status = row.get("embedding_text_surface_status", "")
        action = classify_formula_date_action(row)
        review_rows.append(
            {
                "query_id": row.get("query_id"),
                "bucket": row.get("bucket"),
                "query": row.get("query"),
                "expected_file_name": row.get("expected_file_name"),
                "expected_sheet_name": row.get("expected_sheet_name"),
                "expected_cell_range": row.get("expected_cell_range"),
                "v2_label_status": row.get("v2_label_status"),
                "harness_label_status": row.get("label_status"),
                "eval_purpose": row.get("eval_purpose"),
                "review_status": row.get("review_status"),
                "contract_value_surface": row.get("contract_value_surface"),
                "expects_raw_formula": row.get("contract_value_surface") in {"RAW_FORMULA", "RAW_FORMULA_OR_FORMULA_HEADER"},
                "expects_cached_value": row.get("contract_value_surface") == "CACHED_VALUE",
                "expects_display_formatted_value": row.get("contract_value_surface") in {"DISPLAY_FORMATTED_VALUE", "DATE_FORMATTED_VALUE"},
                "embedding_text_surface_status": status,
                "current_evidence_summary": row.get("current_evidence_summary"),
                "parser_or_gold_contract_action": action,
                "v2_range_match_policy": row.get("v2_range_match_policy"),
                "range_match_policy": row.get("range_match_policy"),
                "harness_range_match_policy": row.get("harness_range_match_policy"),
                "notes": row.get("notes"),
            }
        )

    status_counts = Counter(row["embedding_text_surface_status"] for row in review_rows)
    action_counts = Counter(row["parser_or_gold_contract_action"] for row in review_rows)
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "NEEDS_CONTRACT_REVIEW" if any(row["v2_label_status"] != "positive" for row in review_rows) else "READY_WITH_LIMITED_EVIDENCE",
        "report_role": "xlsx_formula_date_contract_review",
        "promotion_evidence": False,
        "evidence_role": "gold_v2_contract_design",
        "source_paths": dict(source_paths),
        "diagnostic_promotion_evidence": diagnostic.get("promotion_evidence"),
        "ingest_manifest_sample_count": len(ingest_manifest.get("embed_text_samples") or []),
        "row_count": len(review_rows),
        "surface_distribution": dict(sorted(Counter(row["contract_value_surface"] for row in review_rows).items())),
        "embedding_text_surface_status_distribution": dict(sorted(status_counts.items())),
        "parser_or_gold_contract_action_distribution": dict(sorted(action_counts.items())),
        "rows": review_rows,
        "policy": {
            "parser_expansion_implemented": False,
            "gold_query_rewrite_implemented": False,
            "decision": "Keep formula/date rows deferred or contract-scoped until raw formula vs cached/display value surfaces are proven.",
        },
        "notes": [
            "Full embedding_text was not available in the diagnostic report; ingest manifest previews are used only as limited evidence.",
            "This report classifies contracts but does not change parser output.",
        ],
    }


def classify_formula_date_action(row: Mapping[str, str]) -> str:
    if row.get("v2_label_status") == "positive" and row.get("embedding_text_surface_status") in {
        "PRESENT_IN_INGEST_MANIFEST_SAMPLE",
        "PARTIAL_IN_INGEST_MANIFEST_SAMPLE",
    }:
        return "keep_positive_with_contract_note"
    if row.get("contract_value_surface") in {"RAW_FORMULA", "RAW_FORMULA_OR_FORMULA_HEADER"}:
        return "defer_until_raw_formula_surface_is_proven_or_gold_query_is_rewritten"
    if row.get("contract_value_surface") in {"DISPLAY_FORMATTED_VALUE", "DATE_FORMATTED_VALUE"}:
        return "defer_until_display_formatted_surface_is_proven"
    return "manual_contract_review_required"


def build_chunk_granularity_review(
    *,
    v2_rows: list[Mapping[str, str]],
    review: Mapping[str, Any],
    source_paths: Mapping[str, str],
) -> dict[str, Any]:
    decision_by_id = {str(row.get("query_id") or ""): row for row in review.get("decisions") or []}
    chunk_rows = [
        row for row in v2_rows
        if row.get("review_decision") == "REQUIRE_CHUNK_GRANULARITY_FIX"
    ]
    rows = []
    for row in chunk_rows:
        decision = decision_by_id.get(str(row.get("query_id") or ""), {})
        relation = observed_range_relation(str(row.get("expected_cell_range") or ""), decision)
        primary_issue = classify_chunk_issue(row, relation)
        rows.append(
            {
                "query_id": row.get("query_id"),
                "bucket": row.get("bucket"),
                "query": row.get("query"),
                "expected_file_name": row.get("expected_file_name"),
                "expected_sheet_name": row.get("expected_sheet_name"),
                "expected_range": row.get("expected_cell_range"),
                "current_top_ranges": current_top_ranges(decision),
                "range_relation": relation,
                "v2_range_match_policy": row.get("v2_range_match_policy"),
                "range_match_policy": row.get("range_match_policy"),
                "harness_range_match_policy": row.get("harness_range_match_policy"),
                "primary_issue": primary_issue,
                "chunking_fix_needed": primary_issue == "chunking_granularity",
                "gold_range_policy_only": primary_issue == "gold_range_policy",
                "query_specificity_fix_needed": primary_issue == "query_specificity",
                "notes": row.get("notes"),
            }
        )
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "NEEDS_CHUNK_OR_QUERY_REVIEW" if rows else "NO_CHUNK_GRANULARITY_SUSPECTS",
        "report_role": "xlsx_chunk_granularity_review",
        "promotion_evidence": False,
        "evidence_role": "gold_v2_contract_design",
        "source_paths": dict(source_paths),
        "row_count": len(rows),
        "primary_issue_distribution": dict(sorted(Counter(row["primary_issue"] for row in rows).items())),
        "rows": rows,
        "policy": {
            "chunking_changed": False,
            "gold_range_policy_changed_in_harness": False,
            "query_rewrite_implemented": False,
            "decision": "Rows remain deferred until the issue is resolved as query specificity, gold range policy, or chunking granularity.",
        },
    }


def classify_chunk_issue(row: Mapping[str, str], relation: Mapping[str, Any]) -> str:
    query = str(row.get("query") or "")
    if relation.get("overlap"):
        return "gold_range_policy"
    if row.get("bucket") == "xlsx_aggregation":
        return "query_specificity"
    if row.get("bucket") == "mixed_text_table":
        return "chunking_granularity"
    if len(normalize_query(query)) <= 6:
        return "query_specificity"
    return "chunking_granularity"


def build_hidden_negative_plan(
    *,
    hidden_negative_rows: list[Mapping[str, str]],
    review: Mapping[str, Any],
    diagnostic: Mapping[str, Any],
    source_paths: Mapping[str, str],
) -> dict[str, Any]:
    metrics = diagnostic.get("metrics") or {}
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "READY_FOR_SEPARATE_NEGATIVE_POLICY_DESIGN" if hidden_negative_rows else "NO_HIDDEN_NEGATIVE_ROWS",
        "report_role": "xlsx_hidden_negative_eval_plan",
        "promotion_evidence": False,
        "evidence_role": "gold_v2_negative_policy_design",
        "source_paths": dict(source_paths),
        "positive_retrieval_metric_mix_allowed": False,
        "hidden_negative_count": len(hidden_negative_rows),
        "hidden_negative_query_ids": [str(row.get("query_id") or "") for row in hidden_negative_rows],
        "rows": [
            {
                "query_id": row.get("query_id"),
                "query": row.get("query"),
                "expected_behavior": "hidden content is not retrieved and hidden_content_leakage_count remains 0",
                "v2_label_status": row.get("v2_label_status"),
                "harness_label_status": row.get("label_status"),
                "policy_label": row.get("policy_label"),
                "eval_purpose": row.get("eval_purpose"),
                "hidden_policy": row.get("hidden_policy"),
                "must_not_contain_terms": row.get("must_not_contain_terms"),
                "positive_hit_at_k_applicable": False,
                "notes": row.get("notes"),
            }
            for row in hidden_negative_rows
        ],
        "current_diagnostic_hidden_content_leakage_count": metrics.get("hidden_content_leakage_count"),
        "metrics_contract": {
            "primary_metric": "hidden_content_leakage_count",
            "expected_value": 0,
            "do_not_mix_with": ["Hit@K", "MRR@K", "positive citation_location_accuracy"],
        },
        "notes": [
            "The current positive retrieval eval should exclude negative hidden-policy rows.",
            "This plan does not execute a hidden negative eval.",
        ],
    }


def current_top_ranges(decision: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for hit in list(decision.get("top_hits") or [])[:5]:
        rows.append(
            {
                "rank": hit.get("rank"),
                "source_file_name": hit.get("source_file_name"),
                "sheet_name": hit.get("sheet_name"),
                "cell_range": hit.get("cell_range"),
                "xlsx_sheet_match": hit.get("xlsx_sheet_match"),
                "xlsx_range_policy_match": hit.get("xlsx_range_policy_match"),
            }
        )
    return rows


def observed_range_relation(expected_range: str, decision: Mapping[str, Any]) -> dict[str, Any]:
    expected = parse_a1_range(expected_range)
    relation = {"exact": False, "contains_expected": False, "overlap": False, "supporting_hit_ranks": []}
    if not expected:
        return relation
    for hit in list(decision.get("supporting_hits") or []) + list(decision.get("top_hits") or []):
        if not hit.get("xlsx_sheet_match"):
            continue
        actual = parse_a1_range(str(hit.get("cell_range") or ""))
        if not actual:
            continue
        if expected == actual:
            relation["exact"] = True
            relation["supporting_hit_ranks"].append(hit.get("rank"))
        if range_contains(actual, expected):
            relation["contains_expected"] = True
            relation["supporting_hit_ranks"].append(hit.get("rank"))
        if ranges_overlap(expected, actual):
            relation["overlap"] = True
            relation["supporting_hit_ranks"].append(hit.get("rank"))
    relation["supporting_hit_ranks"] = sorted({rank for rank in relation["supporting_hit_ranks"] if rank is not None})
    return relation


def parse_a1_range(value: str) -> tuple[int, int, int, int] | None:
    if ":" not in value:
        return None
    start, end = value.split(":", 1)
    start_cell = parse_cell(start)
    end_cell = parse_cell(end)
    if not start_cell or not end_cell:
        return None
    start_col, start_row = start_cell
    end_col, end_row = end_cell
    return min(start_col, end_col), min(start_row, end_row), max(start_col, end_col), max(start_row, end_row)


def parse_cell(value: str) -> tuple[int, int] | None:
    letters = ""
    digits = ""
    for char in value.strip().upper():
        if "A" <= char <= "Z" and not digits:
            letters += char
        elif char.isdigit():
            digits += char
        else:
            return None
    if not letters or not digits:
        return None
    col = 0
    for char in letters:
        col = col * 26 + (ord(char) - ord("A") + 1)
    return col, int(digits)


def ranges_overlap(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> bool:
    l_col1, l_row1, l_col2, l_row2 = left
    r_col1, r_row1, r_col2, r_row2 = right
    return not (l_col2 < r_col1 or r_col2 < l_col1 or l_row2 < r_row1 or r_row2 < l_row1)


def range_contains(container: tuple[int, int, int, int], expected: tuple[int, int, int, int]) -> bool:
    c_col1, c_row1, c_col2, c_row2 = container
    e_col1, e_row1, e_col2, e_row2 = expected
    return c_col1 <= e_col1 and c_row1 <= e_row1 and c_col2 >= e_col2 and c_row2 >= e_row2


def looks_like_formula_expression(value: str) -> bool:
    value = value.strip()
    return bool(re.search(r"[A-Z]{1,3}\d+\s*[/+\-*]\s*[A-Z]{1,3}\d+", value, flags=re.IGNORECASE))


def looks_like_date(value: str) -> bool:
    return bool(re.search(r"\d{4}[-./]\d{1,2}[-./]\d{1,2}", value))


def split_terms(value: str) -> list[str]:
    return [term.strip() for term in str(value or "").split(";") if term.strip()]


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() == "true"


def normalize_query(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.lower(), flags=re.UNICODE)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON report must be an object: {path}")
    return payload


def write_csv(path: Path, rows: Iterable[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=V2_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_report(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-v0", default=str(DEFAULT_GOLD_V0))
    parser.add_argument("--xlsx-v1", default=str(DEFAULT_XLSX_V1))
    parser.add_argument("--review-decisions", default=str(DEFAULT_REVIEW_DECISIONS))
    parser.add_argument("--diagnostic-report", default=str(DEFAULT_DIAGNOSTIC_REPORT))
    parser.add_argument("--ingest-manifest", default=str(DEFAULT_INGEST_MANIFEST))
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--build-report", default=str(DEFAULT_BUILD_REPORT))
    parser.add_argument("--hidden-negative-plan", default=str(DEFAULT_HIDDEN_NEGATIVE_PLAN))
    parser.add_argument("--formula-date-review", default=str(DEFAULT_FORMULA_DATE_REVIEW))
    parser.add_argument("--chunk-granularity-review", default=str(DEFAULT_CHUNK_GRANULARITY_REVIEW))
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET_ID)
    parser.add_argument("--dataset-version", default=DEFAULT_DATASET_VERSION)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
