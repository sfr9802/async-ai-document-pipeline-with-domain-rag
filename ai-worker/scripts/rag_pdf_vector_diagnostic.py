"""Run Track C C5 PDF-only vector diagnostic.

This script is diagnostic-only. It reads the C1/C2/C3/C4 Track C reports,
filters the bound PDF gold rows, and runs vector retrieval only against the
PDF candidate namespace/artifact. It does not index, promote, or mutate any
baseline artifact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER = SCRIPT_DIR.parent
ROOT = AI_WORKER.parent
for path in (SCRIPT_DIR, AI_WORKER):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from eval.harness.rag_ingestion_retrieval_eval import (  # noqa: E402
    evaluate_gold_rows,
    search_vector,
    validate_gold_rows,
)
from rag_pdf_current_diagnostic_snapshot import (  # noqa: E402
    build_pdf_counters,
    pick_pdf_metrics,
)


PDF_INDEX_VERSION = "rag-ingestion-v2-pdf-candidate-v1"
PDF_ARTIFACT_DIR = Path("eval/indexes/rag-data-pdf-candidate-v1")
DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_v0.csv")
DEFAULT_C1_REPORT = Path("eval/reports/rag-ingestion/pdf_candidate_scope_report.json")
DEFAULT_C2_REPORT = Path("eval/reports/rag-ingestion/pdf_vector_metadata_projection_readiness.json")
DEFAULT_C3_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_embedding_text_contract_audit.json")
DEFAULT_C4_REPORT = Path("eval/reports/rag-ingestion/pdf_candidate_embedding_consistency_report.json")
DEFAULT_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_pdf_vector_diagnostic_report.json")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"

PDF_ONLY_WARNING_KEYS = (
    "OCR confidence missing rows are policy-excluded before C4: 6",
    "document summaries are policy-excluded before C4: 3",
    "skipped searchable rows remain visible for C4 exclusion: 9",
    "current PDF table gold rows have no table-like SearchUnits: 6",
)
INDEX_CONTRACT_METRIC_KEYS = (
    "candidate_index_mismatch_count",
    "embedding_status_mismatch_count",
    "required_index_version_mismatch_count",
    "indexing_filtered_hit_count",
    "wrong_index_version_hit_count",
    "unembedded_hit_count",
    "hidden_content_leakage_count",
)
RETRIEVAL_FAILURE_REASONS = {
    "search_result_empty",
    "expected_file_not_found",
    "expected_page_not_found",
    "bbox_mismatch",
    "unknown",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_report(args)
    output_path = resolve_output_path(Path(args.report))
    write_json(output_path, payload)
    print_json(summary_for_stdout(payload, output_path))
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def build_report(
    args: argparse.Namespace,
    *,
    search_fn_override: Callable[[str, int], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []

    gold_path = resolve_existing_path(Path(args.gold))
    c1_path = resolve_existing_path(Path(args.c1_report))
    c2_path = resolve_existing_path(Path(args.c2_report))
    c3_path = resolve_existing_path(Path(args.c3_report))
    c4_path = resolve_existing_path(Path(args.c4_report))
    artifact_dir = resolve_existing_path(Path(args.artifact_dir))
    db_dsn = args.vector_db_dsn or os.environ.get("RAG_DB_DSN") or DEFAULT_DB_DSN
    index_version = args.index_version
    required_index_version = args.required_index_version or index_version

    c1_report = read_json(c1_path, blockers, "c1_scope_report")
    c2_report = read_json(c2_path, blockers, "c2_report")
    c3_report = read_json(c3_path, blockers, "c3_report")
    c4_report = read_json(c4_path, blockers, "c4_report")
    gold_rows = read_gold_rows(gold_path, blockers)
    artifact_build = read_artifact_build(artifact_dir)

    expected_location_types = [item.lower() for item in (args.expected_location_type or ["pdf"])]
    selected_rows = filter_pdf_positive_rows(
        gold_rows,
        expected_location_types=expected_location_types,
        label_status=args.label_status,
    )
    excluded_gold_counts = excluded_gold_row_counts(gold_rows, selected_rows)
    validation = validate_gold_rows(selected_rows, require_live_bound=False)
    validation_payload = validation_summary(validation)

    validate_static_contract(
        args=args,
        c1_report=c1_report,
        c2_report=c2_report,
        c3_report=c3_report,
        c4_report=c4_report,
        artifact_build=artifact_build,
        artifact_dir=artifact_dir,
        index_version=index_version,
        required_index_version=required_index_version,
        expected_location_types=expected_location_types,
        selected_rows=selected_rows,
        validation_payload=validation_payload,
        blockers=blockers,
    )
    warnings.extend(carry_forward_warnings(c2_report, c3_report, c4_report))

    eval_report: dict[str, Any] = {
        "status": "NOT_RUN",
        "validation": validation_payload,
        "metrics": {},
        "bucket_metrics": {},
        "query_results": [],
        "per_query": [],
    }
    retrieval_error: str | None = None
    if not blockers:
        try:
            search_fn = search_fn_override or search_vector(
                index_dir=str(artifact_dir),
                db_dsn=db_dsn,
                embedding_model=args.vector_embedding_model,
                query_prefix=args.vector_query_prefix,
                passage_prefix=args.vector_passage_prefix,
                max_seq_length=args.vector_max_seq_length,
                batch_size=args.vector_batch_size,
                expected_index_version=required_index_version,
            )
            eval_report = evaluate_gold_rows(
                selected_rows,
                search_fn=search_fn,
                top_k=args.top_k,
                candidate_index_version=index_version,
                required_embedding_status=args.required_embedding_status or None,
                required_index_version=required_index_version,
            )
        except Exception as exc:  # pragma: no cover - live dependency failure path
            retrieval_error = f"{type(exc).__name__}: {exc}"
            blockers.append(f"C5 vector diagnostic execution failed: {retrieval_error}")

    metrics = dict(eval_report.get("metrics") or {})
    query_results = normalize_query_results(list(eval_report.get("query_results") or []))
    pdf_counters = build_pdf_counters(selected_rows, query_results)
    pdf_metrics = pick_pdf_metrics(metrics)
    vector_contract = vector_contract_counters(metrics, query_results)
    failure_classification = classify_failures(
        c4_report=c4_report,
        metrics=metrics,
        pdf_counters=pdf_counters,
        selected_rows=selected_rows,
        query_results=query_results,
    )

    validate_runtime_contract(
        vector_contract=vector_contract,
        failure_classification=failure_classification,
        query_results=query_results,
        blockers=blockers,
    )
    if query_results and any(value for value in failure_classification["failure_reason_counts"].values()):
        warnings.append("C5 observed PDF retrieval/location misses; C6 should classify them by query.")
    if int(failure_classification.get("metadata_projection_failure_count") or 0) != 0:
        warnings.append("C5 separated metadata projection failures for C6; not a C5 blocker.")
    if c4_report.get("warnings_carried_forward") or c3_report.get("table_contract"):
        warnings.append("PDF table gold policy remains a C7/C6 warning, not a C5 blocker.")

    status = "PASS"
    if blockers:
        status = "FAIL"
    elif dedupe(warnings):
        status = "PASS_WITH_WARNINGS"

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C5",
        "report_role": "pdf_only_vector_diagnostic",
        "source_file_type": "PDF",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_backend": "vector",
        "namespace": index_version,
        "index_version": index_version,
        "candidate_index_version": index_version,
        "required_index_version": required_index_version,
        "required_embedding_status": args.required_embedding_status or None,
        "artifact_dir": display_path(artifact_dir),
        "allowUnscoped": False,
        "top_k": args.top_k,
        "backend_identity": backend_identity(
            artifact_dir=artifact_dir,
            db_dsn=db_dsn,
            required_index_version=required_index_version,
            embedding_model=args.vector_embedding_model,
        ),
        "retrieval_execution": "run_by_this_script" if eval_report.get("status") != "NOT_RUN" else "not_run",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "broad_indexing_execution": "not_run_by_this_script",
        "input_artifacts": [
            artifact_identity(c1_path),
            artifact_identity(c2_path),
            artifact_identity(c3_path),
            artifact_identity(c4_path),
            artifact_identity(gold_path),
        ],
        "prerequisite_reports": {
            "c1_scope_report": report_ref(c1_path, c1_report),
            "c2_report": report_ref(c2_path, c2_report),
            "c3_report": report_ref(c3_path, c3_report),
            "c4_report": report_ref(c4_path, c4_report),
        },
        "scope": {
            "source_file_type": "PDF",
            "expected_location_type": "pdf",
            "label_status": args.label_status,
            "positive_only": True,
            "hidden_policy_negative_excluded": True,
            "allowUnscoped": False,
            "document_version_ids": list((c4_report.get("scope") or {}).get("document_version_ids") or []),
            "source_file_ids": list((c4_report.get("scope") or {}).get("source_file_ids") or []),
            "parser_versions": list((c4_report.get("scope") or {}).get("parser_versions") or []),
        },
        "gold_filter": {
            "gold_path": display_path(gold_path),
            "gold_row_count": len(gold_rows),
            "selected_pdf_positive_row_count": len(selected_rows),
            "excluded_counts": excluded_gold_counts,
            "bucket_counts": dict(sorted(Counter(row.get("bucket") or "unknown" for row in selected_rows).items())),
            "query_ids": [row.get("query_id", "") for row in selected_rows],
        },
        "validation": validation_payload,
        "candidate_namespace_chunk_count": int(c4_report.get("candidate_namespace_chunk_count") or 0),
        "unexpected_sourceFileId_count": int(c4_report.get("unexpected_sourceFileId_count") or 0),
        "unexpected_documentVersionId_count": int(c4_report.get("unexpected_documentVersionId_count") or 0),
        "non_pdf_row_count": int(c4_report.get("non_pdf_row_count") or 0),
        "policy_excluded_leakage_count": int(c4_report.get("policy_excluded_leakage_count") or 0),
        "scope_leakage_detected": any(
            int(c4_report.get(key) or 0) != 0
            for key in (
                "unexpected_sourceFileId_count",
                "unexpected_documentVersionId_count",
                "non_pdf_row_count",
                "policy_excluded_leakage_count",
            )
        ),
        "metadata_projection_consistency": c4_report.get("metadata_projection_consistency") or {},
        "embedding_text_contract_consistency": c4_report.get("embedding_text_contract_consistency") or {},
        "immutable_baseline_changed": bool(c4_report.get("immutable_baseline_changed")),
        "xlsx_candidate_artifact_changed": bool(c4_report.get("xlsx_candidate_artifact_changed")),
        "candidate_indexing_consistency": {
            "scoped_search_unit_count": int(c4_report.get("scoped_search_unit_count") or 0),
            "indexable_search_unit_count": int(c4_report.get("indexable_search_unit_count") or 0),
            "policy_excluded_search_unit_count": int(c4_report.get("policy_excluded_search_unit_count") or 0),
            "candidate_namespace_chunk_count": int(c4_report.get("candidate_namespace_chunk_count") or 0),
            "candidate_chunk_count_matches_indexable_rows": bool(
                c4_report.get("candidate_chunk_count_matches_indexable_rows")
            ),
            "unexpected_sourceFileId_count": int(c4_report.get("unexpected_sourceFileId_count") or 0),
            "unexpected_documentVersionId_count": int(c4_report.get("unexpected_documentVersionId_count") or 0),
            "non_pdf_row_count": int(c4_report.get("non_pdf_row_count") or 0),
            "policy_excluded_leakage_count": int(c4_report.get("policy_excluded_leakage_count") or 0),
            "metadata_projection_consistency": c4_report.get("metadata_projection_consistency") or {},
            "embedding_text_contract_consistency": c4_report.get("embedding_text_contract_consistency") or {},
        },
        "artifact_build": artifact_build,
        "metrics": metrics,
        "pdf_metrics": pdf_metrics,
        "pdf_failure_counters": pdf_counters,
        "vector_contract_counters": vector_contract,
        "diagnostic_failure_classification": failure_classification,
        "metadata_projection_failure_count": failure_classification["metadata_projection_failure_count"],
        "true_retrieval_ranking_failure_count": failure_classification["true_retrieval_ranking_failure_count"],
        "result_empty_count": int(metrics.get("result_empty_count") or 0),
        "query_level_results_available": bool(query_results),
        "query_result_count": len(query_results),
        "query_results": query_results,
        "per_query": list(eval_report.get("per_query") or []),
        "bucket_metrics": eval_report.get("bucket_metrics") or {},
        "retrieval_error": retrieval_error,
        "warnings_carried_forward": dedupe(carry_forward_warnings(c2_report, c3_report, c4_report)),
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "c6_ready": status in {"PASS", "PASS_WITH_WARNINGS"} and bool(query_results),
        "c7_policy_review_required_now": False,
        "next_action": (
            "Proceed to C6 PDF vector failure breakdown."
            if status in {"PASS", "PASS_WITH_WARNINGS"} and bool(query_results)
            else "Resolve C5 blockers before C6."
        ),
        "notes": [
            "C5 measures PDF-only vector retrieval quality; it is not promotion evidence.",
            "C5 does not perform indexing, cleanup, baseline mutation, or promotion.",
            "PDF table/page/OCR/bbox gold policy remains deferred to C6/C7 if failure taxonomy requires it.",
        ],
    }


def filter_pdf_positive_rows(
    rows: list[dict[str, str]],
    *,
    expected_location_types: list[str],
    label_status: str,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for row in rows:
        expected_type = str(row.get("expected_location_type") or "").strip().lower()
        bucket = str(row.get("bucket") or "")
        hidden_policy = str(row.get("hidden_policy") or "").strip().lower()
        current_label = str(row.get("label_status") or "").strip().lower()
        if expected_type not in expected_location_types and not bucket.startswith("pdf"):
            continue
        if expected_type != "pdf":
            continue
        if current_label != label_status.lower():
            continue
        if hidden_policy == "negative":
            continue
        selected.append(row)
    return selected


def excluded_gold_row_counts(
    rows: list[dict[str, str]],
    selected_rows: list[dict[str, str]],
) -> dict[str, int]:
    selected_ids = {id(row) for row in selected_rows}
    counts: Counter[str] = Counter()
    for row in rows:
        if id(row) in selected_ids:
            continue
        expected_type = str(row.get("expected_location_type") or "").strip().lower()
        hidden_policy = str(row.get("hidden_policy") or "").strip().lower()
        label_status = str(row.get("label_status") or "").strip().lower()
        if hidden_policy == "negative":
            counts["hidden_policy_negative"] += 1
        elif expected_type != "pdf":
            counts["non_pdf"] += 1
        elif label_status != "bound":
            counts[f"label_status_{label_status or 'missing'}"] += 1
        else:
            counts["other"] += 1
    return dict(sorted(counts.items()))


def validate_static_contract(
    *,
    args: argparse.Namespace,
    c1_report: Mapping[str, Any],
    c2_report: Mapping[str, Any],
    c3_report: Mapping[str, Any],
    c4_report: Mapping[str, Any],
    artifact_build: Mapping[str, Any],
    artifact_dir: Path,
    index_version: str,
    required_index_version: str,
    expected_location_types: list[str],
    selected_rows: list[dict[str, str]],
    validation_payload: Mapping[str, Any],
    blockers: list[str],
) -> None:
    if truthy(args.promotion_evidence):
        blockers.append("C5 must keep promotion_evidence=false")
    if args.evidence_role != "diagnostic":
        blockers.append("C5 must keep evidence_role=diagnostic")
    if index_version != PDF_INDEX_VERSION:
        blockers.append(f"C5 index_version must be {PDF_INDEX_VERSION}")
    if required_index_version != PDF_INDEX_VERSION:
        blockers.append(f"C5 required_index_version must be {PDF_INDEX_VERSION}")
    if expected_location_types != ["pdf"]:
        blockers.append("C5 expected_location_type filter must be exactly pdf")
    if c1_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C1 must pass before C5; got {c1_report.get('status')}")
    if c2_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C2 must pass before C5; got {c2_report.get('status')}")
    if c3_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C3 must pass before C5; got {c3_report.get('status')}")
    if c4_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C4 must pass before C5; got {c4_report.get('status')}")
    if c4_report.get("c5_ready") is not True:
        blockers.append("C4 report must mark c5_ready=true before C5")
    for label, report in (
        ("C1", c1_report),
        ("C2", c2_report),
        ("C3", c3_report),
        ("C4", c4_report),
    ):
        if report and report.get("promotion_evidence") is not False:
            blockers.append(f"{label} report must keep promotion_evidence=false")
        if report and report.get("evidence_role") != "diagnostic":
            blockers.append(f"{label} report must keep evidence_role=diagnostic")
    if c1_report.get("allowUnscoped") is not False:
        blockers.append("C1 allowUnscoped must remain false")
    if c4_report.get("allowUnscoped") is not False:
        blockers.append("C4 allowUnscoped must remain false")
    if c4_report.get("namespace") != PDF_INDEX_VERSION:
        blockers.append("C4 namespace must match PDF candidate namespace")
    if display_path(artifact_dir) != "ai-worker/eval/indexes/rag-data-pdf-candidate-v1":
        blockers.append("C5 artifact_dir must be ai-worker/eval/indexes/rag-data-pdf-candidate-v1")
    if not artifact_build.get("exists"):
        blockers.append("PDF candidate artifact_dir must exist before C5")
    if artifact_build.get("index_version") != PDF_INDEX_VERSION:
        blockers.append("PDF artifact build index_version must match C5 namespace")
    if int(artifact_build.get("chunk_count") or 0) != 8194:
        blockers.append("PDF artifact build chunk_count must remain 8194")
    if int(c4_report.get("scoped_search_unit_count") or 0) != 8203:
        blockers.append("C4 scoped_search_unit_count must remain 8203")
    if int(c4_report.get("indexable_search_unit_count") or 0) != 8194:
        blockers.append("C4 indexable_search_unit_count must remain 8194")
    if int(c4_report.get("policy_excluded_search_unit_count") or 0) != 9:
        blockers.append("C4 policy_excluded_search_unit_count must remain 9")
    if int(c4_report.get("candidate_namespace_chunk_count") or 0) != 8194:
        blockers.append("C4 candidate_namespace_chunk_count must remain 8194")
    if c4_report.get("candidate_chunk_count_matches_indexable_rows") is not True:
        blockers.append("C4 chunk count must match indexable rows")
    for key in (
        "unexpected_sourceFileId_count",
        "unexpected_documentVersionId_count",
        "non_pdf_row_count",
        "policy_excluded_leakage_count",
        "missing_location_json_locationJson_count",
        "jackson_jsonnode_shape_location_count",
        "unusable_location_count",
        "missing_physical_page_index_count",
        "missing_page_no_count",
        "missing_bbox_count",
        "missing_citation_text_count",
        "missing_embedding_text_count",
        "missing_source_page_citation_block_surface_count",
        "ocr_trust_marker_missing_count",
    ):
        if int(c4_report.get(key) or 0) != 0:
            blockers.append(f"C4 {key} must be 0 before C5")
    if c4_report.get("immutable_baseline_changed") is not False:
        blockers.append("immutable baseline must remain unchanged before C5")
    if c4_report.get("xlsx_candidate_artifact_changed") is not False:
        blockers.append("XLSX candidate artifact must remain unchanged before C5")
    if not selected_rows:
        blockers.append("C5 PDF positive gold subset must not be empty")
    if validation_payload.get("ok") is not True:
        blockers.append("C5 selected PDF gold rows must pass harness validation")


def validate_runtime_contract(
    *,
    vector_contract: Mapping[str, int],
    failure_classification: Mapping[str, Any],
    query_results: list[Mapping[str, Any]],
    blockers: list[str],
) -> None:
    for key in INDEX_CONTRACT_METRIC_KEYS:
        if int(vector_contract.get(key) or 0) != 0:
            blockers.append(f"{key} must be 0")
    for key in (
        "top_k_non_pdf_hit_count",
        "top_k_wrong_index_version_hit_count",
        "top_k_unembedded_hit_count",
        "top_k_missing_location_json_count",
        "top_k_missing_source_file_type_count",
    ):
        if int(vector_contract.get(key) or 0) != 0:
            blockers.append(f"{key} must be 0")
    if int(failure_classification.get("search_error_count") or 0) != 0:
        blockers.append("search_error_count must be 0")
    if not query_results:
        blockers.append("C5 query_level_results_available must be true")


def vector_contract_counters(
    metrics: Mapping[str, Any],
    query_results: list[Mapping[str, Any]],
) -> dict[str, int]:
    counters: Counter[str] = Counter()
    for key in INDEX_CONTRACT_METRIC_KEYS:
        counters[key] = int(metrics.get(key) or 0)
    for key in (
        "top_k_non_pdf_hit_count",
        "top_k_wrong_index_version_hit_count",
        "top_k_unembedded_hit_count",
        "top_k_missing_location_json_count",
        "top_k_raw_source_file_type_missing_count",
        "top_k_source_file_type_inferred_count",
        "top_k_missing_source_file_type_count",
    ):
        counters[key] = 0
    for row in query_results:
        for hit in list(row.get("top_k_results") or []):
            source_type = str(hit.get("effective_source_file_type") or hit.get("source_file_type") or "").upper()
            if not hit.get("raw_source_file_type_present"):
                counters["top_k_raw_source_file_type_missing_count"] += 1
            if hit.get("source_file_type_inferred"):
                counters["top_k_source_file_type_inferred_count"] += 1
            if not source_type:
                counters["top_k_missing_source_file_type_count"] += 1
            if source_type and source_type != "PDF":
                counters["top_k_non_pdf_hit_count"] += 1
            if hit.get("index_version") != PDF_INDEX_VERSION:
                counters["top_k_wrong_index_version_hit_count"] += 1
            if str(hit.get("embedding_status") or "").upper() != "EMBEDDED":
                counters["top_k_unembedded_hit_count"] += 1
            if not hit.get("location_json_present"):
                counters["top_k_missing_location_json_count"] += 1
    return dict(sorted((key, int(value)) for key, value in counters.items()))


def classify_failures(
    *,
    c4_report: Mapping[str, Any],
    metrics: Mapping[str, Any],
    pdf_counters: Mapping[str, Any],
    selected_rows: list[Mapping[str, str]],
    query_results: list[Mapping[str, Any]],
) -> dict[str, Any]:
    failure_counts = dict(metrics.get("overall_failure_reason_counts") or {})
    metadata_projection_failure_count = int(
        c4_report.get("missing_location_json_locationJson_count") or 0
    ) + int(c4_report.get("unusable_location_count") or 0) + int(
        c4_report.get("missing_physical_page_index_count") or 0
    ) + int(
        c4_report.get("missing_page_no_count") or 0
    ) + int(
        c4_report.get("missing_bbox_count") or 0
    ) + int(
        pdf_counters.get("correct_page_no_hit_but_missing_physical_page_index_count") or 0
    ) + int(
        pdf_counters.get("correct_page_no_hit_but_missing_bbox_count") or 0
    )
    retrieval_failure_count = sum(int(failure_counts.get(reason) or 0) for reason in RETRIEVAL_FAILURE_REASONS)
    table_gold_query_count = sum(1 for row in selected_rows if str(row.get("bucket") or "") == "pdf_table_lookup")
    failed_query_ids = [
        str(row.get("query_id") or "")
        for row in query_results
        if row.get("failure_reason") not in (None, "", "matched")
    ]
    return {
        "failure_reason_counts": dict(sorted((str(key), int(value)) for key, value in failure_counts.items())),
        "metadata_projection_failure_count": metadata_projection_failure_count,
        "true_retrieval_ranking_failure_count": retrieval_failure_count,
        "result_empty_count": int(metrics.get("result_empty_count") or 0),
        "search_error_count": int(metrics.get("search_error_count") or 0),
        "gold_label_invalid_count": int(metrics.get("gold_label_invalid_count") or 0),
        "table_gold_query_count": table_gold_query_count,
        "gold_policy_candidate_warning_count": table_gold_query_count,
        "unclassified_failure_count": int(failure_counts.get("unknown") or 0),
        "failed_query_ids": failed_query_ids,
    }


def normalize_query_results(query_results: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized_rows: list[dict[str, Any]] = []
    for row in query_results:
        next_row = dict(row)
        next_hits: list[dict[str, Any]] = []
        for hit in list(row.get("top_k_results") or []):
            next_hit = dict(hit)
            raw_source_type = str(next_hit.get("source_file_type") or "").strip()
            inferred_type = infer_source_file_type(next_hit)
            effective_type = raw_source_type.upper() if raw_source_type else inferred_type
            next_hit["raw_source_file_type_present"] = bool(raw_source_type)
            next_hit["source_file_type_inferred"] = bool(not raw_source_type and inferred_type)
            if not raw_source_type and inferred_type:
                next_hit["source_file_type"] = inferred_type
                next_hit["source_file_type_inferred_from"] = "location_json.type"
            next_hit["effective_source_file_type"] = effective_type
            next_hits.append(next_hit)
        next_row["top_k_results"] = next_hits
        normalized_rows.append(next_row)
    return normalized_rows


def infer_source_file_type(hit: Mapping[str, Any]) -> str:
    location = hit.get("location_json")
    location = location if isinstance(location, Mapping) else {}
    location_type = str(location.get("type") or "").strip().lower()
    if location_type in {"pdf", "ocr"}:
        return "PDF"
    if location_type == "xlsx":
        return "XLSX"
    return ""


def carry_forward_warnings(
    c2_report: Mapping[str, Any],
    c3_report: Mapping[str, Any],
    c4_report: Mapping[str, Any],
) -> list[str]:
    warnings: list[str] = []
    c4_warnings = c4_report.get("warnings_carried_forward")
    if isinstance(c4_warnings, list):
        warnings.extend(str(item) for item in c4_warnings)
    c2_summary = c2_report.get("summary") if isinstance(c2_report.get("summary"), Mapping) else {}
    c3_summary = c3_report.get("summary") if isinstance(c3_report.get("summary"), Mapping) else {}
    table_contract = c3_report.get("table_contract") if isinstance(c3_report.get("table_contract"), Mapping) else {}
    derived = [
        f"OCR confidence missing rows are policy-excluded before C4: {int(c2_summary.get('policy_excluded_ocr_confidence_missing_count') or 0)}",
        f"document summaries are policy-excluded before C4: {int(c2_summary.get('policy_excluded_document_summary_count') or 0)}",
        f"skipped searchable rows remain visible for C4 exclusion: {int(c3_summary.get('skipped_searchable_row_count') or 0)}",
        "current PDF table gold rows have no table-like SearchUnits: "
        f"{int(table_contract.get('pdf_table_gold_count') or 0)}",
    ]
    warnings.extend(item for item in derived if item in PDF_ONLY_WARNING_KEYS)
    return dedupe(warnings)


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


def read_artifact_build(path: Path) -> dict[str, Any]:
    build_path = path / "build.json"
    manifest_path = path / "ingest_manifest.json"
    build: dict[str, Any] = {}
    if build_path.exists():
        parsed = json.loads(build_path.read_text(encoding="utf-8"))
        build = parsed if isinstance(parsed, dict) else {}
    return {
        "artifact_dir": display_path(path),
        "exists": path.exists(),
        "build_json_path": display_path(build_path),
        "build_json_sha256": file_sha256(build_path) if build_path.exists() else None,
        "manifest_path": display_path(manifest_path),
        "manifest_sha256": file_sha256(manifest_path) if manifest_path.exists() else None,
        "index_version": build.get("index_version"),
        "embedding_model": build.get("embedding_model"),
        "dimension": build.get("dimension"),
        "chunk_count": build.get("chunk_count"),
    }


def backend_identity(
    *,
    artifact_dir: Path,
    db_dsn: str,
    required_index_version: str,
    embedding_model: str,
) -> dict[str, Any]:
    return {
        "backend": "faiss",
        "index_dir": display_path(artifact_dir),
        "index_namespace_filter": required_index_version,
        "embedding_model": embedding_model,
        "db_dsn": redact_dsn(db_dsn),
        "filtering_mode": "pdf_candidate_namespace_then_contract_filter",
    }


def validation_summary(validation: Any) -> dict[str, Any]:
    return {
        "ok": validation.ok,
        "error_count": len(validation.errors),
        "row_error_count": len(validation.row_errors),
        "errors": validation.errors,
        "row_errors": validation.row_errors,
        "row_count": validation.row_count,
        "bucket_counts": validation.bucket_counts,
    }


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


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def summary_for_stdout(payload: Mapping[str, Any], output_path: Path) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "report": display_path(output_path),
        "promotion_evidence": payload.get("promotion_evidence"),
        "evidence_role": payload.get("evidence_role"),
        "namespace": payload.get("namespace"),
        "query_result_count": payload.get("query_result_count"),
        "pdf_metrics": payload.get("pdf_metrics"),
        "metadata_projection_failure_count": payload.get("metadata_projection_failure_count"),
        "true_retrieval_ranking_failure_count": payload.get("true_retrieval_ranking_failure_count"),
        "blockers": payload.get("blockers"),
        "warnings": payload.get("warnings"),
        "c6_ready": payload.get("c6_ready"),
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


def redact_dsn(dsn: str) -> str:
    parts = []
    for token in dsn.split():
        if token.lower().startswith("password="):
            parts.append("password=<redacted>")
        else:
            parts.append(token)
    return " ".join(parts)


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


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
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--c1-report", default=str(DEFAULT_C1_REPORT))
    parser.add_argument("--c2-report", default=str(DEFAULT_C2_REPORT))
    parser.add_argument("--c3-report", default=str(DEFAULT_C3_REPORT))
    parser.add_argument("--c4-report", default=str(DEFAULT_C4_REPORT))
    parser.add_argument("--report", "--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--artifact-dir", "--vector-index-dir", default=str(PDF_ARTIFACT_DIR))
    parser.add_argument("--expected-location-type", action="append", default=None)
    parser.add_argument("--label-status", default="bound")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--index-version", "--candidate-index-version", default=PDF_INDEX_VERSION)
    parser.add_argument("--required-index-version", default=PDF_INDEX_VERSION)
    parser.add_argument("--required-embedding-status", default="EMBEDDED")
    parser.add_argument("--promotion-evidence", default="false")
    parser.add_argument("--evidence-role", default="diagnostic")
    parser.add_argument("--vector-db-dsn", default=None)
    parser.add_argument("--vector-embedding-model", default="BAAI/bge-m3")
    parser.add_argument("--vector-query-prefix", default="")
    parser.add_argument("--vector-passage-prefix", default="")
    parser.add_argument("--vector-max-seq-length", type=int, default=1024)
    parser.add_argument("--vector-batch-size", type=int, default=32)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
