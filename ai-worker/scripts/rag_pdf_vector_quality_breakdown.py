"""Break down Track C C6 PDF vector diagnostic failures.

This report consumes the C5 PDF-only vector diagnostic and classifies each
query into metadata, ranking, parser/chunk, bbox policy, or gold-policy review
candidates. It is diagnostic-only and never runs retrieval, indexing, or
promotion.
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
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER = SCRIPT_DIR.parent
ROOT = AI_WORKER.parent

PDF_INDEX_VERSION = "rag-ingestion-v2-pdf-candidate-v1"
DEFAULT_EVAL_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_pdf_vector_diagnostic_report.json")
DEFAULT_C2_REPORT = Path("eval/reports/rag-ingestion/pdf_vector_metadata_projection_readiness.json")
DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_v0.csv")
DEFAULT_OUTPUT = Path("eval/reports/rag-ingestion/rag_pdf_vector_quality_breakdown.json")

FAILURE_TYPES = {
    "MATCHED",
    "PDF_METADATA_PROJECTION_MISSING_PHYSICAL_PAGE",
    "PDF_METADATA_PROJECTION_MISSING_BBOX",
    "PDF_EXPECTED_FILE_ABSENT_IN_TOP10",
    "PDF_EXPECTED_PAGE_ABSENT_IN_TOP10",
    "PDF_BBOX_POLICY_MISMATCH",
    "PDF_TABLE_GOLD_BINDING_MISMATCH",
    "PDF_CHUNK_GRANULARITY_ISSUE",
    "PDF_OCR_TRUST_CONTRACT_MISMATCH",
    "PDF_TRUE_RETRIEVAL_RANKING_FAILURE",
    "PDF_INDEX_CONTRACT_MISMATCH",
    "PDF_RUNTIME_SEARCH_ERROR",
    "UNKNOWN",
}
BLOCKING_C5_COUNTERS = (
    "candidate_index_mismatch_count",
    "embedding_status_mismatch_count",
    "required_index_version_mismatch_count",
    "indexing_filtered_hit_count",
    "top_k_non_pdf_hit_count",
    "top_k_wrong_index_version_hit_count",
    "top_k_unembedded_hit_count",
    "top_k_missing_location_json_count",
    "top_k_missing_source_file_type_count",
    "hidden_content_leakage_count",
)
METADATA_FAILURE_TYPES = {
    "PDF_METADATA_PROJECTION_MISSING_PHYSICAL_PAGE",
    "PDF_METADATA_PROJECTION_MISSING_BBOX",
}
RETRIEVAL_RANKING_TYPES = {
    "PDF_EXPECTED_FILE_ABSENT_IN_TOP10",
    "PDF_EXPECTED_PAGE_ABSENT_IN_TOP10",
    "PDF_TRUE_RETRIEVAL_RANKING_FAILURE",
}
GOLD_POLICY_TYPES = {
    "PDF_TABLE_GOLD_BINDING_MISMATCH",
    "PDF_BBOX_POLICY_MISMATCH",
}
CHUNK_GRANULARITY_TYPES = {
    "PDF_CHUNK_GRANULARITY_ISSUE",
}
GENERIC_GOLD_LABELS = {
    "기간중",
    "목 차",
    "달러",
    "수입(CIF)",
}
GENERIC_NUMERIC_RE = re.compile(r"^\d{4}(?:\.\s*\d+)?$|^\d+(?:\.\d+)?$")
TABLE_NUMERIC_TEXT_RE = re.compile(r"^[\d\s,.\-]+$")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    eval_path = resolve_existing_path(Path(args.eval_report))
    c2_path = resolve_existing_path(Path(args.c2_report))
    gold_path = resolve_existing_path(Path(args.gold))
    output_path = resolve_output_path(Path(args.report))
    blockers: list[str] = []

    c5_report = read_json(eval_path, blockers, "c5_eval_report")
    c2_report = read_json(c2_path, blockers, "c2_report")
    gold_rows = read_gold_rows(gold_path, blockers)
    payload = build_breakdown(
        c5_report=c5_report,
        c2_report=c2_report,
        gold_rows=gold_rows,
        eval_path=eval_path,
        c2_path=c2_path,
        gold_path=gold_path,
        blockers=blockers,
    )
    write_json(output_path, payload)
    print_json(summary_for_stdout(payload, output_path))
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def build_breakdown(
    *,
    c5_report: Mapping[str, Any],
    c2_report: Mapping[str, Any],
    gold_rows: list[dict[str, str]],
    eval_path: Path,
    c2_path: Path,
    gold_path: Path,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    blocker_list = list(blockers or [])
    warning_list: list[str] = []
    validate_inputs(
        c5_report=c5_report,
        c2_report=c2_report,
        blocker_list=blocker_list,
    )

    gold_by_id = {row.get("query_id", ""): row for row in gold_rows}
    query_results = [row for row in list(c5_report.get("query_results") or []) if is_pdf_query(row, gold_by_id)]
    classified_rows: list[dict[str, Any]] = []
    for row in query_results:
        gold = gold_by_id.get(str(row.get("query_id") or ""), {})
        classified_rows.append(classify_query(row, gold))

    failure_type_counts = Counter(row["failure_type"] for row in classified_rows)
    primary_group_counts = Counter(row["primary_group"] for row in classified_rows)
    bucket_failure_type_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in classified_rows:
        bucket_failure_type_counts[str(row.get("bucket") or "unknown")][row["failure_type"]] += 1

    metadata_observations = metadata_projection_observations(classified_rows)
    failed_rows = [row for row in classified_rows if row["failure_type"] != "MATCHED"]
    unknown_count = int(failure_type_counts.get("UNKNOWN") or 0)
    missing_next_action = [row["query_id"] for row in classified_rows if not row.get("next_action")]
    if unknown_count:
        blocker_list.append("UNKNOWN failure count must be 0")
    if missing_next_action:
        blocker_list.append(f"query rows missing next_action: {missing_next_action}")
    if c5_report.get("query_result_count") is not None and len(query_results) != int(c5_report.get("query_result_count") or 0):
        blocker_list.append("C6 query_result_count must match C5 query_result_count")

    gold_policy_candidate_rows = [
        row for row in classified_rows if row["failure_type"] in GOLD_POLICY_TYPES or row.get("c7_gold_policy_candidate")
    ]
    chunk_granularity_rows = [
        row for row in classified_rows if row["failure_type"] in CHUNK_GRANULARITY_TYPES
    ]
    parser_chunk_rows = [
        row for row in classified_rows if row.get("primary_group") == "parser_chunk_contract"
    ]
    metadata_primary_count = sum(
        1 for row in classified_rows if row["failure_type"] in METADATA_FAILURE_TYPES
    )
    retrieval_ranking_candidates_present = retrieval_ranking_count(classified_rows) > 0
    retrieval_tuning_ready = (
        status_ready(blocker_list)
        and retrieval_ranking_candidates_present
        and len(gold_policy_candidate_rows) == 0
        and len(parser_chunk_rows) == 0
        and len(chunk_granularity_rows) == 0
        and metadata_primary_count == 0
    )
    if gold_policy_candidate_rows:
        warning_list.append("C6 found C7 gold-policy candidate rows.")
    if chunk_granularity_rows:
        warning_list.append("C6 found chunk granularity or parser/chunk contract candidate rows.")
    if metadata_observations["observation_count"]:
        warning_list.append("C6 separated metadata projection observations from primary ranking failures.")
    if retrieval_ranking_count(classified_rows):
        warning_list.append("C6 found true retrieval/ranking candidate failures.")

    status = "PASS"
    if blocker_list:
        status = "FAIL"
    elif warning_list or list(c5_report.get("warnings") or []):
        status = "PASS_WITH_WARNINGS"

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C6",
        "report_role": "pdf_vector_failure_breakdown",
        "source_file_type": "PDF",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_backend": c5_report.get("retrieval_backend"),
        "namespace": c5_report.get("namespace"),
        "index_version": c5_report.get("index_version"),
        "artifact_dir": c5_report.get("artifact_dir"),
        "retrieval_execution": "not_run_by_this_script",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "input_artifacts": [
            artifact_identity(eval_path),
            artifact_identity(c2_path),
            artifact_identity(gold_path),
        ],
        "c5_report": report_ref(eval_path, c5_report),
        "c2_report": report_ref(c2_path, c2_report),
        "gold": {
            "path": display_path(gold_path),
            "row_count": len(gold_rows),
        },
        "query_count": len(query_results),
        "failed_query_count": len(failed_rows),
        "failed_query_ids": [row["query_id"] for row in failed_rows],
        "matched_query_count": int(failure_type_counts.get("MATCHED") or 0),
        "unknown_failure_count": unknown_count,
        "failure_type_counts": dict(sorted(failure_type_counts.items())),
        "primary_group_counts": dict(sorted(primary_group_counts.items())),
        "primary_disposition_counts": dict(sorted(primary_group_counts.items())),
        "bucket_failure_type_counts": {
            bucket: dict(sorted(counts.items()))
            for bucket, counts in sorted(bucket_failure_type_counts.items())
        },
        "metadata_projection": metadata_observations,
        "c5_reported_metadata_projection_failure_count": int(
            c5_report.get("metadata_projection_failure_count") or 0
        ),
        "metadata_projection_primary_failure_count": metadata_primary_count,
        "parser_chunk_contract_candidate_count": len(parser_chunk_rows),
        "parser_chunk_contract_candidate_query_ids": [
            row["query_id"] for row in parser_chunk_rows
        ],
        "retrieval_ranking_failure_count": retrieval_ranking_count(classified_rows),
        "retrieval_ranking_candidates_present": retrieval_ranking_candidates_present,
        "gold_policy_candidate_count": len(gold_policy_candidate_rows),
        "gold_policy_candidate_query_ids": [row["query_id"] for row in gold_policy_candidate_rows],
        "chunk_granularity_candidate_count": len(chunk_granularity_rows),
        "chunk_granularity_candidate_query_ids": [row["query_id"] for row in chunk_granularity_rows],
        "ocr_trust_contract_mismatch_count": int(failure_type_counts.get("PDF_OCR_TRUST_CONTRACT_MISMATCH") or 0),
        "c7_review_candidates": {
            "query_count": len(gold_policy_candidate_rows),
            "query_ids": [row["query_id"] for row in gold_policy_candidate_rows],
            "reason": "Gold/page/table/bbox policy candidates should be reviewed in C7 if still relevant after C6.",
            "user_gold_policy_decision_required_now": False,
        },
        "c5_failure_classification": c5_report.get("diagnostic_failure_classification") or {},
        "c5_pdf_metrics": c5_report.get("pdf_metrics") or {},
        "c5_vector_contract_counters": c5_report.get("vector_contract_counters") or {},
        "source_file_type_inferred_count": int(
            (c5_report.get("vector_contract_counters") or {}).get("top_k_source_file_type_inferred_count") or 0
        ),
        "hidden_policy_negative_excluded_count": int(
            ((c5_report.get("gold_filter") or {}).get("excluded_counts") or {}).get("hidden_policy_negative") or 0
        ),
        "c5_warnings_carried_forward": list(c5_report.get("warnings_carried_forward") or []),
        "query_breakdown": classified_rows,
        "classified_failed_query_rows": [row for row in classified_rows if row["failure_type"] != "MATCHED"],
        "blockers": dedupe(blocker_list),
        "warnings": dedupe(warning_list + list(c5_report.get("warnings") or [])),
        "c7_ready": status in {"PASS", "PASS_WITH_WARNINGS"} and len(gold_policy_candidate_rows) > 0,
        "retrieval_tuning_ready": retrieval_tuning_ready,
        "next_action": (
            "Proceed to C7 gold policy review for the recorded candidates."
            if gold_policy_candidate_rows
            else "Use retrieval/ranking candidates for tuning discussion only after C7/C6 policy candidates are cleared."
        ),
        "notes": [
            "C6 classifies C5 query-level results only; it does not run retrieval, indexing, or promotion.",
            "Metadata projection observations can be secondary warnings even when the query ultimately matched.",
            "PDF table gold policy candidates are recorded for C7 and are not resolved by this script.",
        ],
    }


def classify_query(row: Mapping[str, Any], gold: Mapping[str, str]) -> dict[str, Any]:
    top_hits = list(row.get("top_k_results") or [])
    query_id = str(row.get("query_id") or gold.get("query_id") or "")
    bucket = str(row.get("bucket") or gold.get("bucket") or "")
    expected_chunk_type = str(gold.get("expected_chunk_type") or "").strip()
    expected_page_no = to_int(gold.get("expected_page_no") or row.get("expected_page_no"))
    expected_bbox = str(gold.get("expected_bbox") or row.get("expected_bbox") or "").strip()
    query_text = str(row.get("query") or gold.get("query") or "").strip()
    is_ocr = str(gold.get("expected_location_type") or row.get("expected_location_type") or "").lower() == "ocr"
    file_hits = [hit for hit in top_hits if match(hit, "file_match")]
    docv_hits = [hit for hit in file_hits if match(hit, "document_version_match")]
    page_hits = [hit for hit in docv_hits if expected_page_no is not None and location(hit).get("page_no") == expected_page_no]
    bbox_hits = [hit for hit in page_hits if match(hit, "pdf_bbox_overlap")]
    page_hits_missing_physical = [hit for hit in page_hits if location(hit).get("physical_page_index") is None]
    page_hits_missing_bbox = [hit for hit in page_hits if expected_bbox and not location(hit).get("bbox")]
    page_hits_missing_bbox_from_page_chunk = [
        hit for hit in page_hits_missing_bbox
        if str(hit.get("chunk_type") or "").lower() == "page" or not match(hit, "chunk_type_match")
    ]
    chunk_type_hits = [hit for hit in docv_hits if match(hit, "chunk_type_match")]
    correct_page_wrong_chunk_hits = [hit for hit in page_hits if not match(hit, "chunk_type_match")]
    location_match_hits = [hit for hit in top_hits if match(hit, "location_match")]
    generic_label = is_generic_gold_label(query_text)
    secondary_types = metadata_secondary_types(
        page_hits_missing_physical=page_hits_missing_physical,
        page_hits_missing_bbox=[] if page_hits_missing_bbox_from_page_chunk else page_hits_missing_bbox,
    )
    if page_hits_missing_bbox_from_page_chunk:
        secondary_types.append("PDF_BBOX_POLICY_MISMATCH")

    failure_reason = row.get("failure_reason")
    if row.get("location_match") is True:
        failure_type = "MATCHED"
        primary_group = "matched"
        rationale = "C5 matched the expected PDF location."
        supporting_hits = location_match_hits[:3]
        next_action = "No C6 action for the primary result; keep secondary metadata observations visible if present."
    elif int(row.get("search_error_count") or 0) or row.get("search_error"):
        failure_type = "PDF_RUNTIME_SEARCH_ERROR"
        primary_group = "runtime"
        rationale = "C5 reported a vector search runtime error."
        supporting_hits = top_hits[:3]
        next_action = "Fix C5 runtime dependency and rerun C5 before C6."
    elif has_index_contract_mismatch(top_hits):
        failure_type = "PDF_INDEX_CONTRACT_MISMATCH"
        primary_group = "index_contract"
        rationale = "At least one top-k hit violates the candidate index/version/embedding contract."
        supporting_hits = top_hits[:3]
        next_action = "Return to C4/C5 contract readiness before interpreting ranking quality."
    elif is_ocr and any_ocr_trust_mismatch(top_hits):
        failure_type = "PDF_OCR_TRUST_CONTRACT_MISMATCH"
        primary_group = "metadata_projection"
        rationale = "OCR row lacks the trust markers required for lower-trust OCR evidence."
        supporting_hits = top_hits[:3]
        next_action = "Route to OCR trust readiness before ranking or gold-policy decisions."
    elif bucket == "pdf_table_lookup":
        failure_type = "PDF_TABLE_GOLD_BINDING_MISMATCH"
        primary_group = "parser_chunk_contract"
        rationale = "PDF table gold row did not resolve to table-like evidence in the candidate index."
        supporting_hits = docv_hits[:3] or file_hits[:3] or top_hits[:3]
        next_action = "C7 should decide whether this table gold row requires table-like SearchUnits or paragraph/page-backed evidence is acceptable."
    elif generic_label and failure_reason in {"expected_file_not_found", "expected_page_not_found"}:
        failure_type = (
            "PDF_EXPECTED_FILE_ABSENT_IN_TOP10"
            if failure_reason == "expected_file_not_found"
            else "PDF_EXPECTED_PAGE_ABSENT_IN_TOP10"
        )
        primary_group = "gold_policy"
        rationale = "The failed query surface is generic or duplicated enough that gold/policy review should precede ranking interpretation."
        supporting_hits = docv_hits[:3] or file_hits[:3] or top_hits[:3]
        next_action = "C7 should review whether this query/evidence binding is specific enough for PDF ranking evaluation."
    elif expected_chunk_type == "page" and (correct_page_wrong_chunk_hits or (docv_hits and not chunk_type_hits)):
        failure_type = "PDF_CHUNK_GRANULARITY_ISSUE"
        primary_group = "parser_chunk_contract"
        rationale = "Gold expects page-level evidence but top-k candidate hits are not page chunks."
        supporting_hits = correct_page_wrong_chunk_hits[:3] or docv_hits[:3]
        next_action = "Review parser/chunk granularity before treating this as pure retrieval ranking."
    elif page_hits_missing_physical:
        failure_type = "PDF_METADATA_PROJECTION_MISSING_PHYSICAL_PAGE"
        primary_group = "metadata_projection"
        rationale = "Expected page number appears in top-k, but physical_page_index is missing."
        supporting_hits = page_hits_missing_physical[:3]
        next_action = "Repair metadata projection for physical_page_index and rerun C5."
    elif page_hits_missing_bbox:
        if page_hits_missing_bbox_from_page_chunk:
            failure_type = "PDF_BBOX_POLICY_MISMATCH"
            primary_group = "parser_chunk_contract"
            rationale = "Expected page appears through a page-level or chunk-type-mismatched hit without bbox, so bbox/page-chunk policy must be resolved before ranking interpretation."
            supporting_hits = page_hits_missing_bbox_from_page_chunk[:3]
            next_action = "C7/C6 should review bbox policy and page-vs-paragraph chunk behavior before retrieval tuning."
        else:
            failure_type = "PDF_METADATA_PROJECTION_MISSING_BBOX"
            primary_group = "metadata_projection"
            rationale = "Expected page appears in top-k, but the relevant hit has no bbox."
            supporting_hits = page_hits_missing_bbox[:3]
            next_action = "Review bbox projection or page-vs-paragraph chunk policy before ranking changes."
    elif not file_hits:
        failure_type = "PDF_EXPECTED_FILE_ABSENT_IN_TOP10"
        primary_group = "retrieval_ranking"
        rationale = "Expected PDF file is absent from top10."
        supporting_hits = top_hits[:3]
        next_action = "Treat as retrieval/ranking candidate after gold-policy candidates are cleared."
    elif expected_page_no is not None and not page_hits:
        failure_type = "PDF_EXPECTED_PAGE_ABSENT_IN_TOP10"
        primary_group = "retrieval_ranking"
        rationale = "Expected PDF file/document appears, but expected page is absent from top10."
        supporting_hits = docv_hits[:3] or file_hits[:3]
        next_action = "Treat as retrieval/ranking candidate after C7 policy candidates are cleared."
    elif expected_bbox and not bbox_hits:
        failure_type = "PDF_BBOX_POLICY_MISMATCH"
        primary_group = "gold_policy"
        rationale = "Expected page appears, but bbox overlap policy does not match."
        supporting_hits = page_hits[:3]
        next_action = "C7 should review bbox overlap/expected evidence policy for this row."
    elif failure_reason:
        failure_type = "PDF_TRUE_RETRIEVAL_RANKING_FAILURE"
        primary_group = "retrieval_ranking"
        rationale = f"C5 failure_reason={failure_reason!r} did not map to metadata, chunk, or gold-policy categories."
        supporting_hits = docv_hits[:3] or file_hits[:3] or top_hits[:3]
        next_action = "Treat as retrieval/ranking candidate after policy and chunk candidates are cleared."
    else:
        failure_type = "UNKNOWN"
        primary_group = "unknown"
        rationale = "C6 could not classify this query deterministically."
        supporting_hits = top_hits[:3]
        next_action = "Inspect this query manually and update the C6 classifier."

    c7_candidate = failure_type in GOLD_POLICY_TYPES or primary_group == "gold_policy" or bucket == "pdf_table_lookup"
    secondary_dispositions = secondary_disposition_list(
        failure_type=failure_type,
        primary_group=primary_group,
        secondary_types=secondary_types,
        c7_candidate=c7_candidate,
    )
    return {
        "query_id": query_id,
        "bucket": bucket,
        "query": row.get("query") or gold.get("query"),
        "label_status": row.get("label_status") or gold.get("label_status"),
        "failure_reason": failure_reason,
        "failure_type": failure_type,
        "failure_types": dedupe([failure_type] + secondary_types),
        "primary_group": primary_group,
        "primary_disposition": primary_group,
        "secondary_dispositions": secondary_dispositions,
        "secondary_failure_types": secondary_types,
        "c7_gold_policy_candidate": c7_candidate,
        "hit_rank": row.get("hit_rank"),
        "location_rank": row.get("location_rank"),
        "expected": {
            "file_name": row.get("expected_file_name") or gold.get("expected_file_name"),
            "document_version_id": gold.get("expected_document_version_id"),
            "chunk_type": expected_chunk_type,
            "location_type": gold.get("expected_location_type"),
            "physical_page_index": row.get("expected_physical_page_index") or gold.get("expected_physical_page_index"),
            "page_no": row.get("expected_page_no") or gold.get("expected_page_no"),
            "page_label": row.get("expected_page_label") or gold.get("expected_page_label"),
            "bbox": row.get("expected_bbox") or gold.get("expected_bbox"),
        },
        "evidence": {
            "top_k_count": len(top_hits),
            "file_hit_count": len(file_hits),
            "document_version_hit_count": len(docv_hits),
            "expected_page_hit_count": len(page_hits),
            "bbox_overlap_hit_count": len(bbox_hits),
            "first_expected_file_rank": first_rank(file_hits),
            "first_expected_docv_rank": first_rank(docv_hits),
            "first_expected_page_rank": first_rank(page_hits),
            "first_bbox_overlap_rank": first_rank(bbox_hits),
            "page_hit_missing_bbox_ranks": [hit.get("rank") for hit in page_hits_missing_bbox],
            "chunk_type_mismatch_ranks": [hit.get("rank") for hit in top_hits if not match(hit, "chunk_type_match")],
            "location_match_without_identity_ranks": [
                hit.get("rank") for hit in top_hits if match(hit, "location_match") and not match(hit, "identity_match")
            ],
            "match_breakdown_counts": match_breakdown_counts(top_hits),
            "page_hit_missing_physical_page_index_count": len(page_hits_missing_physical),
            "page_hit_missing_bbox_count": len(page_hits_missing_bbox),
            "correct_page_wrong_chunk_type_count": len(correct_page_wrong_chunk_hits),
            "supporting_hit_ranks": [hit.get("rank") for hit in supporting_hits],
        },
        "rationale": rationale,
        "next_action": next_action,
        "top_hits": summarize_hits(top_hits[:5]),
        "supporting_hits": summarize_hits(supporting_hits),
    }


def metadata_secondary_types(
    *,
    page_hits_missing_physical: list[Mapping[str, Any]],
    page_hits_missing_bbox: list[Mapping[str, Any]],
) -> list[str]:
    result: list[str] = []
    if page_hits_missing_physical:
        result.append("PDF_METADATA_PROJECTION_MISSING_PHYSICAL_PAGE")
    if page_hits_missing_bbox:
        result.append("PDF_METADATA_PROJECTION_MISSING_BBOX")
    return result


def metadata_projection_observations(classified_rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [
        row for row in classified_rows
        if any(item in METADATA_FAILURE_TYPES for item in list(row.get("secondary_failure_types") or []))
    ]
    primary_rows = [row for row in classified_rows if row.get("failure_type") in METADATA_FAILURE_TYPES]
    warning_rows = [row for row in rows if row.get("failure_type") not in METADATA_FAILURE_TYPES]
    type_counts = Counter()
    for row in rows:
        type_counts.update(list(row.get("secondary_failure_types") or []))
    return {
        "observation_count": len(rows),
        "primary_failure_count": len(primary_rows),
        "secondary_warning_count": len(warning_rows),
        "type_counts": dict(sorted(type_counts.items())),
        "query_ids": [row.get("query_id") for row in rows],
        "primary_failure_query_ids": [row.get("query_id") for row in primary_rows],
        "secondary_warning_query_ids": [row.get("query_id") for row in warning_rows],
    }


def retrieval_ranking_count(classified_rows: list[Mapping[str, Any]]) -> int:
    return sum(
        1
        for row in classified_rows
        if row.get("failure_type") in RETRIEVAL_RANKING_TYPES and row.get("primary_group") == "retrieval_ranking"
    )


def status_ready(blocker_list: list[str]) -> bool:
    return not blocker_list


def secondary_disposition_list(
    *,
    failure_type: str,
    primary_group: str,
    secondary_types: list[str],
    c7_candidate: bool,
) -> list[str]:
    dispositions: list[str] = []
    if c7_candidate and primary_group != "gold_policy":
        dispositions.append("gold_policy")
    if failure_type in CHUNK_GRANULARITY_TYPES and primary_group != "parser_chunk_contract":
        dispositions.append("parser_chunk_contract")
    if any(item in METADATA_FAILURE_TYPES for item in secondary_types) and primary_group != "metadata_projection":
        dispositions.append("metadata_projection")
    if "PDF_BBOX_POLICY_MISMATCH" in secondary_types and primary_group != "parser_chunk_contract":
        dispositions.append("parser_chunk_contract")
    return dedupe(dispositions)


def is_generic_gold_label(query_text: str) -> bool:
    normalized = " ".join(query_text.split())
    if normalized in GENERIC_GOLD_LABELS:
        return True
    if GENERIC_NUMERIC_RE.match(normalized):
        return True
    return bool(any(char.isdigit() for char in normalized) and TABLE_NUMERIC_TEXT_RE.match(normalized))


def first_rank(hits: list[Mapping[str, Any]]) -> int | None:
    if not hits:
        return None
    return to_int(hits[0].get("rank"))


def match_breakdown_counts(hits: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for hit in hits:
        br = breakdown(hit)
        for key, value in br.items():
            if value is True:
                counts[f"{key}_true"] += 1
            elif value is False:
                counts[f"{key}_false"] += 1
    return dict(sorted(counts.items()))


def validate_inputs(
    *,
    c5_report: Mapping[str, Any],
    c2_report: Mapping[str, Any],
    blocker_list: list[str],
) -> None:
    if c5_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blocker_list.append(f"C5 report must pass before C6; got {c5_report.get('status')}")
    if c5_report.get("promotion_evidence") is not False:
        blocker_list.append("C5 report must keep promotion_evidence=false")
    if c5_report.get("evidence_role") != "diagnostic":
        blocker_list.append("C5 report must keep evidence_role=diagnostic")
    if c5_report.get("retrieval_backend") != "vector":
        blocker_list.append("C5 report must be vector-backed")
    if c5_report.get("namespace") != PDF_INDEX_VERSION:
        blocker_list.append("C5 namespace must be the PDF candidate namespace")
    if c5_report.get("c6_ready") is not True:
        blocker_list.append("C5 report must mark c6_ready=true before C6")
    if not c5_report.get("query_level_results_available"):
        blocker_list.append("C5 query_level_results_available must be true")
    if int((c5_report.get("pdf_metrics") or {}).get("search_error_count") or 0) != 0:
        blocker_list.append("C5 search_error_count must be 0 before C6")
    if int((c5_report.get("pdf_metrics") or {}).get("hidden_content_leakage_count") or 0) != 0:
        blocker_list.append("C5 pdf_metrics.hidden_content_leakage_count must be 0 before C6")
    for key, value in (c5_report.get("vector_contract_counters") or {}).items():
        if key in BLOCKING_C5_COUNTERS and int(value or 0) != 0:
            blocker_list.append(f"C5 {key} must be 0 before C6")
    if c2_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blocker_list.append(f"C2 report must pass before C6; got {c2_report.get('status')}")
    if c2_report.get("promotion_evidence") is not False:
        blocker_list.append("C2 report must keep promotion_evidence=false")
    if c2_report.get("evidence_role") != "diagnostic":
        blocker_list.append("C2 report must keep evidence_role=diagnostic")


def summarize_hits(hits: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for hit in hits:
        loc = location(hit)
        br = breakdown(hit)
        summaries.append({
            "rank": hit.get("rank"),
            "search_unit_id": hit.get("search_unit_id"),
            "score": hit.get("score"),
            "source_file_name": hit.get("source_file_name"),
            "source_file_type": hit.get("effective_source_file_type") or hit.get("source_file_type"),
            "chunk_type": hit.get("chunk_type"),
            "page_no": loc.get("page_no"),
            "physical_page_index": loc.get("physical_page_index"),
            "bbox_present": bool(loc.get("bbox")),
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
        })
    return summaries


def has_index_contract_mismatch(hits: list[Mapping[str, Any]]) -> bool:
    for hit in hits:
        br = breakdown(hit)
        if br.get("indexing_contract_match") is False:
            return True
        if br.get("required_index_version_match") is False:
            return True
        if br.get("embedding_status_match") is False:
            return True
    return False


def any_ocr_trust_mismatch(hits: list[Mapping[str, Any]]) -> bool:
    for hit in hits:
        loc = location(hit)
        if str(loc.get("type") or "").lower() == "ocr" and not loc.get("ocr_confidence"):
            return True
    return False


def is_pdf_query(row: Mapping[str, Any], gold_by_id: Mapping[str, Mapping[str, str]]) -> bool:
    query_id = str(row.get("query_id") or "")
    gold = gold_by_id.get(query_id, {})
    bucket = str(row.get("bucket") or gold.get("bucket") or "")
    expected_type = str(gold.get("expected_location_type") or row.get("expected_location_type") or "").lower()
    return expected_type == "pdf" or bucket.startswith("pdf")


def match(hit: Mapping[str, Any], key: str) -> bool:
    return bool(breakdown(hit).get(key))


def breakdown(hit: Mapping[str, Any]) -> Mapping[str, Any]:
    value = hit.get("match_breakdown")
    return value if isinstance(value, Mapping) else {}


def location(hit: Mapping[str, Any]) -> Mapping[str, Any]:
    value = hit.get("location_json")
    return value if isinstance(value, Mapping) else {}


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def summary_for_stdout(payload: Mapping[str, Any], output_path: Path) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "report": display_path(output_path),
        "query_count": payload.get("query_count"),
        "failed_query_count": payload.get("failed_query_count"),
        "unknown_failure_count": payload.get("unknown_failure_count"),
        "failure_type_counts": payload.get("failure_type_counts"),
        "metadata_projection": payload.get("metadata_projection"),
        "gold_policy_candidate_count": payload.get("gold_policy_candidate_count"),
        "chunk_granularity_candidate_count": payload.get("chunk_granularity_candidate_count"),
        "retrieval_ranking_failure_count": payload.get("retrieval_ranking_failure_count"),
        "blockers": payload.get("blockers"),
        "c7_ready": payload.get("c7_ready"),
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
    if parts and parts[0] == "ai-worker":
        return (ROOT / path).resolve()
    return (Path.cwd() / path).resolve()


def candidate_paths(path: Path) -> list[Path]:
    if path.is_absolute():
        return [path]
    paths: list[Path] = []
    parts = path.parts
    if parts and parts[0] == "eval":
        paths.append(AI_WORKER / path)
    if parts and parts[0] == "ai-worker":
        paths.append(ROOT / path)
    paths.extend([Path.cwd() / path, AI_WORKER / path, ROOT / path])
    result: list[Path] = []
    for candidate in paths:
        if candidate not in result:
            result.append(candidate)
    return result


def display_path(path: Path) -> str:
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
    parser.add_argument("--eval-report", default=str(DEFAULT_EVAL_REPORT))
    parser.add_argument("--c2-report", default=str(DEFAULT_C2_REPORT))
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--report", "--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
