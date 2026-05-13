"""Compare PageIndex PDF navigation output with existing C5/C6 diagnostics.

This is report-only. It does not tune retrieval, expand parsers, mutate gold
policy, or create promotion evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER = SCRIPT_DIR.parent
ROOT = AI_WORKER.parent
DEFAULT_C5_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_pdf_vector_diagnostic_report.json")
DEFAULT_C6_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_vector_quality_breakdown.json")
DEFAULT_C7_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_gold_policy_review.json")
DEFAULT_FIT_AUDIT = Path("eval/reports/pageindex-ab/pdf_xlsx_fit_audit/pageindex_pdf_xlsx_fit_audit_rows.csv")
DEFAULT_JSON_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_pageindex_local_canary_report.json")
DEFAULT_CSV_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_pageindex_local_canary.csv")

GUARDRAILS = {
    "promotion_evidence": False,
    "evidence_role": "diagnostic",
    "xlsx_scope_excluded": True,
    "pdf_scope_only": True,
    "external_cloud_llm_run": False,
    "bbox_contract_success_not_claimed": True,
    "table_semantics_success_not_claimed": True,
    "pdf_c7_policy_decision_applied": False,
    "retrieval_tuning_applied": False,
    "parser_expansion_applied": False,
    "official_denominator_changed": False,
}

COMPARISON_STATUSES = {
    "PAGE_SECTION_NAVIGATION_HELPFUL",
    "VECTOR_ALREADY_SUFFICIENT",
    "NO_IMPROVEMENT_OVER_VECTOR",
    "BBOX_OR_TABLE_STILL_UNSOLVED",
    "GOLD_POLICY_STILL_BLOCKED",
    "PAGEINDEX_RUN_UNAVAILABLE",
    "PAGEINDEX_TREE_BUILD_FAILED",
    "PAGEINDEX_QUERY_NAVIGATION_FAILED",
}
BBOX_TABLE_OR_CHUNK_FAILURE_RE = re.compile(r"BBOX|TABLE|CHUNK|PARSER", re.IGNORECASE)
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
CSV_FIELDS = [
    "query_id",
    "pageindex_canary_candidate",
    "live_tree_usefulness_denominator_included",
    "bucket",
    "query",
    "expected_file",
    "expected_page_no",
    "c6_failure_type",
    "c7_policy_group",
    "pageindex_tree_build_success",
    "pageindex_query_navigation_success",
    "selected_node_id",
    "selected_node_title",
    "selected_page_range",
    "selected_section_title",
    "expected_page_hit",
    "expected_page_range_overlap",
    "expected_section_title_overlap",
    "vector_page_hit",
    "pageindex_improves_over_vector",
    "pageindex_regresses_from_vector",
    "bbox_contract_solved",
    "table_semantics_solved",
    "c7_policy_pending",
    "c7_policy_pending_preserved",
    "comparison_status",
    "vector_expected_page_hit_rank",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_manifest_path = resolve_manifest(Path(args.input_manifest)) if args.input_manifest else latest_input_manifest()
    input_manifest = read_json(input_manifest_path)
    run_manifest_path = resolve_run_manifest(Path(args.run_manifest), input_manifest_path) if args.run_manifest else default_run_manifest(input_manifest_path)
    run_manifest = read_json(run_manifest_path) if run_manifest_path and run_manifest_path.exists() else {}
    c5_path = resolve_existing_path(Path(args.c5_report))
    c6_path = resolve_existing_path(Path(args.c6_report))
    c7_path = resolve_existing_path(Path(args.c7_report))
    fit_audit_path = resolve_existing_path(Path(args.fit_audit))
    c5_report = read_json(c5_path)
    c6_report = read_json(c6_path)
    c7_report = read_json(c7_path)
    fit_audit_rows = read_csv(fit_audit_path) if fit_audit_path.exists() else []
    json_report_path = resolve_output_path(Path(args.report))
    csv_report_path = resolve_output_path(Path(args.csv))

    payload = build_report(
        input_manifest=input_manifest,
        input_manifest_path=input_manifest_path,
        run_manifest=run_manifest,
        run_manifest_path=run_manifest_path,
        c5_report=c5_report,
        c5_path=c5_path,
        c6_report=c6_report,
        c6_path=c6_path,
        c7_report=c7_report,
        c7_path=c7_path,
        fit_audit_rows=fit_audit_rows,
        fit_audit_path=fit_audit_path,
        json_report_path=json_report_path,
        csv_report_path=csv_report_path,
    )
    write_json(json_report_path, payload)
    write_csv(csv_report_path, list(payload.get("query_results") or []))
    print_json(summary_for_stdout(payload, json_report_path, csv_report_path))
    return 0 if str(payload.get("status") or "").startswith("DIAGNOSTIC_COMPLETED") else 2


def build_report(
    *,
    input_manifest: Mapping[str, Any],
    input_manifest_path: Path,
    run_manifest: Mapping[str, Any],
    run_manifest_path: Path | None,
    c5_report: Mapping[str, Any],
    c5_path: Path,
    c6_report: Mapping[str, Any],
    c6_path: Path,
    c7_report: Mapping[str, Any],
    c7_path: Path,
    fit_audit_rows: list[dict[str, str]],
    fit_audit_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    validate_guardrails("input_manifest", input_manifest, blockers)
    validate_guardrails("run_manifest", run_manifest, blockers, allow_missing=True)
    validate_guardrails("c5_report", c5_report, blockers)
    validate_guardrails("c6_report", c6_report, blockers)
    validate_guardrails("c7_report", c7_report, blockers)

    c5_by_id = rows_by_query_id(c5_report.get("query_results") or [])
    c6_by_id = rows_by_query_id(c6_report.get("query_breakdown") or [])
    c7_by_id = rows_by_query_id(c7_report.get("c7_review_rows") or [])
    tree_by_file = load_trees_by_file(run_manifest)
    live_pageindex_run = bool(run_manifest.get("live_pageindex_run"))
    local_pageindex_run = bool(run_manifest.get("local_pageindex_run"))
    canary_query_ids = canary_ids_for_run(run_manifest, fit_audit_rows)
    query_results: list[dict[str, Any]] = []

    for row in list(input_manifest.get("queries") or []):
        if not isinstance(row, Mapping):
            continue
        query_id = str(row.get("query_id") or "")
        c5 = c5_by_id.get(query_id, {})
        c6 = c6_by_id.get(query_id, {})
        c7 = c7_by_id.get(query_id, {})
        query_results.append(compare_query(
            manifest_row=row,
            c5=c5,
            c6=c6,
            c7=c7,
            tree_doc=tree_by_file.get(str(row.get("expected_file") or "")),
            live_pageindex_run=live_pageindex_run,
            pageindex_canary_candidate=query_id in canary_query_ids,
        ))

    comparison_status_counts = Counter(row["comparison_status"] for row in query_results)
    denominator_rows = [row for row in query_results if row["live_tree_usefulness_denominator_included"]]
    bucket_comparison_status_counts: dict[str, dict[str, int]] = {}
    for row in query_results:
        bucket = str(row.get("bucket") or "unknown")
        bucket_comparison_status_counts.setdefault(bucket, {})
        cls = str(row.get("comparison_status") or "UNKNOWN")
        bucket_comparison_status_counts[bucket][cls] = bucket_comparison_status_counts[bucket].get(cls, 0) + 1
    status = "DIAGNOSTIC_COMPLETED"
    if not live_pageindex_run:
        status = "DIAGNOSTIC_COMPLETED_WITH_PAGEINDEX_UNAVAILABLE"
        warnings.append("PageIndex live run unavailable; comparison preserves all rows with PAGEINDEX_RUN_UNAVAILABLE.")
    elif any(row["comparison_status"] == "PAGEINDEX_TREE_BUILD_FAILED" for row in denominator_rows):
        status = "DIAGNOSTIC_COMPLETED_WITH_TREE_BUILD_FAILURES"
    elif any(row["comparison_status"] == "PAGEINDEX_QUERY_NAVIGATION_FAILED" for row in denominator_rows):
        status = "DIAGNOSTIC_COMPLETED_WITH_QUERY_NAVIGATION_FAILURES"
    if blockers:
        status = "FAIL_CLOSED_GUARDRAIL_OR_INPUT_ERROR"

    return {
        "schema_version": "pdf_pageindex_local_canary_report_v1",
        "run_id": str(input_manifest.get("run_id") or ""),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "PageIndex PDF comparison",
        "source_file_type": "PDF",
        **GUARDRAILS,
        "live_pageindex_run": live_pageindex_run,
        "local_pageindex_run": local_pageindex_run,
        "pageindex_role": "pdf_page_section_navigator_candidate_only",
        "pageindex_selection_source": "section_title_token_overlap_tree_scan",
        "live_tree_usefulness_denominator": "partial_pdf_tree_candidate_only",
        "live_tree_usefulness_denominator_query_ids": [row["query_id"] for row in denominator_rows],
        "promotion_execution": "not_run_by_this_script",
        "retrieval_execution": "not_run_by_this_script",
        "indexing_execution": "not_run_by_this_script",
        "parser_execution": "not_run_by_this_script",
        "input_artifacts": [
            artifact_identity(input_manifest_path),
            artifact_identity(run_manifest_path) if run_manifest_path else missing_artifact("pageindex_run_manifest.json"),
            artifact_identity(c5_path),
            artifact_identity(c6_path),
            artifact_identity(c7_path),
            artifact_identity(fit_audit_path),
        ],
        "output_artifacts": {
            "json_report": display_path(json_report_path),
            "csv_report": display_path(csv_report_path),
        },
        "counts": {
            "query_count": len(query_results),
            "live_pageindex_run": live_pageindex_run,
            "local_pageindex_run": local_pageindex_run,
            "external_cloud_llm_run": False,
            "canary_candidate_count": len(denominator_rows),
            "tree_build_success_count": sum(1 for row in denominator_rows if row["pageindex_tree_build_success"]),
            "tree_build_failure_count": sum(
                1 for row in denominator_rows if row["comparison_status"] == "PAGEINDEX_TREE_BUILD_FAILED"
            ),
            "query_navigation_success_count": sum(1 for row in denominator_rows if row["pageindex_query_navigation_success"]),
            "selected_page_range_extractable_count": sum(1 for row in denominator_rows if row["selected_page_range"]),
            "expected_page_range_overlap_count": sum(1 for row in denominator_rows if row["expected_page_range_overlap"]),
            "vector_page_hit_count": sum(1 for row in query_results if row["vector_page_hit"]),
            "pageindex_improves_over_vector_count": sum(1 for row in denominator_rows if row["pageindex_improves_over_vector"]),
            "pageindex_regresses_from_vector_count": sum(1 for row in denominator_rows if row["pageindex_regresses_from_vector"]),
            "vector_already_sufficient_count": sum(
                1 for row in denominator_rows if row["comparison_status"] == "VECTOR_ALREADY_SUFFICIENT"
            ),
            "c7_policy_pending_preserved_count": sum(1 for row in query_results if row["c7_policy_pending_preserved"]),
            "bbox_or_table_still_unsolved_count": sum(1 for row in query_results if row_has_bbox_table_failure(row)),
            "gold_policy_still_blocked_count": sum(1 for row in query_results if row["c7_policy_pending_preserved"]),
            "pageindex_run_unavailable_count": comparison_status_counts.get("PAGEINDEX_RUN_UNAVAILABLE", 0),
            "comparison_status_counts": dict(sorted(comparison_status_counts.items())),
            "bucket_comparison_status_counts": {
                bucket: dict(sorted(counts.items()))
                for bucket, counts in sorted(bucket_comparison_status_counts.items())
            },
        },
        "pageindex_helpful_query_ids": [
            row["query_id"] for row in query_results if row["comparison_status"] == "PAGE_SECTION_NAVIGATION_HELPFUL"
        ],
        "pageindex_no_improvement_query_ids": [
            row["query_id"] for row in query_results if row["comparison_status"] == "NO_IMPROVEMENT_OVER_VECTOR"
        ],
        "pageindex_run_unavailable_query_ids": [
            row["query_id"] for row in query_results if row["comparison_status"] == "PAGEINDEX_RUN_UNAVAILABLE"
        ],
        "query_results": query_results,
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "notes": [
            "PageIndex is compared only as a PDF page/section navigator candidate.",
            "bbox and table semantics are explicitly not claimed as solved.",
            "C7 policy-pending rows remain policy-pending; Codex applied no policy decision.",
            "XLSX is excluded from this comparison and remains on Track A.",
        ],
    }


def compare_query(
    *,
    manifest_row: Mapping[str, Any],
    c5: Mapping[str, Any],
    c6: Mapping[str, Any],
    c7: Mapping[str, Any],
    tree_doc: Mapping[str, Any] | None,
    live_pageindex_run: bool,
    pageindex_canary_candidate: bool,
) -> dict[str, Any]:
    expected_page = to_int(manifest_row.get("expected_page_no"))
    vector_hit = vector_page_hit(c5, c6)
    selected_nodes: list[dict[str, Any]] = []
    pageindex_tree_status = "PAGEINDEX_RUN_UNAVAILABLE"
    pageindex_tree_build_success = False
    if live_pageindex_run and tree_doc:
        pageindex_tree_status = str(tree_doc.get("status"))
        pageindex_tree_build_success = pageindex_tree_status == "TREE_AVAILABLE"
    if pageindex_tree_build_success and pageindex_canary_candidate:
        selected_nodes = select_nodes(tree_doc.get("nodes") or [], manifest_row) if tree_doc else []
    selected_node = selected_nodes[0] if selected_nodes else {}
    selected_page_range = page_range_for_node(selected_node)
    pageindex_query_navigation_success = bool(selected_node)
    pageindex_page_hit = expected_page is not None and any(page_in_range(expected_page, node) for node in selected_nodes)
    title_overlap = any(bool(node.get("title_token_overlap")) and page_in_range(expected_page, node) for node in selected_nodes)
    c7_policy_pending = bool(manifest_row.get("c7_policy_pending"))
    c6_failure_type = str(manifest_row.get("c6_failure_type") or c6.get("failure_type") or "")
    c6_failure_types = list(manifest_row.get("c6_failure_types") or c6.get("failure_types") or [])
    comparison_status = classify_help(
        live_pageindex_run=live_pageindex_run,
        tree_doc=tree_doc,
        pageindex_canary_candidate=pageindex_canary_candidate,
        pageindex_tree_build_success=pageindex_tree_build_success,
        pageindex_query_navigation_success=pageindex_query_navigation_success,
        c7_policy_pending=c7_policy_pending,
        c6_failure_type=c6_failure_type,
        c6_failure_types=c6_failure_types,
        vector_page_hit=vector_hit["vector_page_hit"],
        pageindex_page_hit=pageindex_page_hit,
    )
    validate_comparison_status(comparison_status)
    return {
        "query_id": manifest_row.get("query_id"),
        "pageindex_canary_candidate": pageindex_canary_candidate,
        "live_tree_usefulness_denominator_included": pageindex_canary_candidate,
        "bucket": manifest_row.get("bucket"),
        "query": manifest_row.get("query"),
        "expected_file": manifest_row.get("expected_file"),
        "expected_page_no": expected_page,
        "expected_bbox": manifest_row.get("expected_bbox"),
        "pageindex_tree_build_success": pageindex_tree_build_success,
        "pageindex_query_navigation_success": pageindex_query_navigation_success,
        "selected_node_id": selected_node.get("node_id"),
        "selected_node_title": selected_node.get("title"),
        "selected_page_range": selected_page_range,
        "selected_section_title": selected_node.get("title"),
        "expected_page_hit": pageindex_page_hit,
        "expected_page_range_overlap": pageindex_page_hit,
        "expected_section_title_overlap": title_overlap,
        "vector_page_hit": vector_hit["vector_page_hit"],
        "pageindex_improves_over_vector": bool(pageindex_canary_candidate and pageindex_page_hit and not vector_hit["vector_page_hit"]),
        "pageindex_regresses_from_vector": bool(
            pageindex_canary_candidate
            and live_pageindex_run
            and pageindex_query_navigation_success
            and vector_hit["vector_page_hit"]
            and not pageindex_page_hit
        ),
        "bbox_contract_solved": "not_claimed",
        "table_semantics_solved": "not_claimed",
        "c7_policy_pending": c7_policy_pending,
        "c7_policy_pending_preserved": c7_policy_pending and not bool(manifest_row.get("codex_policy_decision_applied")),
        "c7_policy_group": manifest_row.get("c7_policy_group") or c7.get("primary_c7_classification") or "not_in_c7_review",
        "pdf_c7_policy_decision_applied": False,
        "c6_failure_type": c6_failure_type,
        "c6_failure_types": c6_failure_types,
        "comparison_status": comparison_status,
        "pageindex_tree_status": pageindex_tree_status,
        "pageindex_selected_node_count": len(selected_nodes),
        "pageindex_selected_nodes": selected_node_summaries(selected_nodes),
        "vector_expected_page_hit_rank": vector_hit["vector_expected_page_hit_rank"],
        "vector_expected_page_hit_ranks": vector_hit["vector_expected_page_hit_ranks"],
        "vector_file_hit_rank": vector_hit["vector_file_hit_rank"],
        "c5_final_match_outcome": c5.get("final_match_outcome") or (manifest_row.get("c5") or {}).get("final_match_outcome"),
        "c5_failure_reason": c5.get("failure_reason") or (manifest_row.get("c5") or {}).get("failure_reason"),
        "comparison_notes": comparison_notes(
            comparison_status=comparison_status,
            c7_policy_pending=c7_policy_pending,
            c6_failure_type=c6_failure_type,
            live_pageindex_run=live_pageindex_run,
            pageindex_canary_candidate=pageindex_canary_candidate,
        ),
    }


def vector_page_hit(c5: Mapping[str, Any], c6: Mapping[str, Any]) -> dict[str, Any]:
    evidence = c6.get("evidence") if isinstance(c6.get("evidence"), Mapping) else {}
    first_expected_page_rank = to_int(evidence.get("first_expected_page_rank"))
    expected_page_hit_count = to_int(evidence.get("expected_page_hit_count")) or 0
    file_hit_rank = to_int(evidence.get("first_expected_file_rank"))
    ranks: list[int] = []
    for hit in list(c5.get("top_k_results") or []):
        br = hit.get("match_breakdown") or {}
        if br.get("file_match") and br.get("document_version_match") and br.get("pdf_page_match"):
            rank = to_int(hit.get("rank"))
            if rank is not None:
                ranks.append(rank)
    if ranks and first_expected_page_rank is None:
        first_expected_page_rank = min(ranks)
    return {
        "vector_page_hit": expected_page_hit_count > 0 or bool(ranks),
        "vector_expected_page_hit_rank": first_expected_page_rank,
        "vector_expected_page_hit_ranks": sorted(set(ranks)),
        "vector_file_hit_rank": file_hit_rank,
    }


def select_nodes(nodes: list[Mapping[str, Any]], manifest_row: Mapping[str, Any]) -> list[dict[str, Any]]:
    query_tokens = query_token_set(manifest_row)
    selected: list[dict[str, Any]] = []
    for node in nodes:
        title = str(node.get("title") or "")
        title_tokens = tokens(title)
        overlap = sorted(query_tokens & title_tokens)
        if not overlap:
            continue
        selected.append({
            "node_id": node.get("node_id"),
            "title": title,
            "start_index": to_int(node.get("start_index")),
            "end_index": to_int(node.get("end_index")),
            "depth": to_int(node.get("depth")) or 0,
            "title_token_overlap": overlap,
        })
    selected.sort(key=lambda node: (-len(node["title_token_overlap"]), node.get("depth") or 0, node.get("start_index") or 10**9))
    return selected[:10]


def query_token_set(manifest_row: Mapping[str, Any]) -> set[str]:
    text_parts = [
        str(manifest_row.get("query") or ""),
        str(manifest_row.get("expected_answer_text") or ""),
        " ".join(str(item) for item in (manifest_row.get("must_contain_terms") or [])),
    ]
    return tokens(" ".join(text_parts))


def tokens(text: str) -> set[str]:
    result = {item.lower() for item in TOKEN_RE.findall(text or "") if len(item) >= 2}
    stop = {"pdf", "page", "p", "표", "확인", "위치", "항목", "최근", "경제", "동향"}
    return result - stop


def page_in_range(page: int | None, node: Mapping[str, Any]) -> bool:
    if page is None:
        return False
    start = to_int(node.get("start_index"))
    end = to_int(node.get("end_index"))
    if start is None or end is None:
        return False
    return start <= page <= end


def page_range_for_node(node: Mapping[str, Any]) -> list[int] | None:
    start = to_int(node.get("start_index"))
    end = to_int(node.get("end_index"))
    if start is None or end is None:
        return None
    return [start, end]


def classify_help(
    *,
    live_pageindex_run: bool,
    tree_doc: Mapping[str, Any] | None,
    pageindex_canary_candidate: bool,
    pageindex_tree_build_success: bool,
    pageindex_query_navigation_success: bool,
    c7_policy_pending: bool,
    c6_failure_type: str,
    c6_failure_types: list[Any],
    vector_page_hit: bool,
    pageindex_page_hit: bool,
) -> str:
    if not live_pageindex_run or not tree_doc:
        return "PAGEINDEX_RUN_UNAVAILABLE"
    if not pageindex_tree_build_success:
        return "PAGEINDEX_TREE_BUILD_FAILED"
    if c7_policy_pending:
        return "GOLD_POLICY_STILL_BLOCKED"
    failure_text = " ".join([c6_failure_type] + [str(item) for item in c6_failure_types])
    if BBOX_TABLE_OR_CHUNK_FAILURE_RE.search(failure_text):
        return "BBOX_OR_TABLE_STILL_UNSOLVED"
    if not pageindex_canary_candidate:
        return "PAGEINDEX_RUN_UNAVAILABLE"
    if not pageindex_query_navigation_success:
        return "PAGEINDEX_QUERY_NAVIGATION_FAILED"
    if vector_page_hit and pageindex_page_hit:
        return "VECTOR_ALREADY_SUFFICIENT"
    if pageindex_page_hit and not vector_page_hit:
        return "PAGE_SECTION_NAVIGATION_HELPFUL"
    return "NO_IMPROVEMENT_OVER_VECTOR"


def comparison_notes(
    *,
    comparison_status: str,
    c7_policy_pending: bool,
    c6_failure_type: str,
    live_pageindex_run: bool,
    pageindex_canary_candidate: bool,
) -> list[str]:
    notes: list[str] = []
    if comparison_status not in COMPARISON_STATUSES:
        notes.append("Unknown PageIndex comparison status; inspect comparator rules.")
    if not live_pageindex_run:
        notes.append("PageIndex tree unavailable, so no navigation improvement is claimed.")
    if not pageindex_canary_candidate:
        notes.append("Row remains in comparator output but is excluded from the live tree usefulness denominator.")
    if c7_policy_pending:
        notes.append("C7 policy-pending status is preserved; no Codex policy decision was applied.")
    if BBOX_TABLE_OR_CHUNK_FAILURE_RE.search(c6_failure_type):
        notes.append("bbox/table/chunk issue remains unsolved by page/section navigation.")
    return notes


def row_has_bbox_table_failure(row: Mapping[str, Any]) -> bool:
    failure_text = " ".join(
        [str(row.get("c6_failure_type") or "")]
        + [str(item) for item in list(row.get("c6_failure_types") or [])]
    )
    return bool(BBOX_TABLE_OR_CHUNK_FAILURE_RE.search(failure_text))


def validate_comparison_status(status: str) -> None:
    if status not in COMPARISON_STATUSES:
        raise ValueError(f"Invalid comparison_status: {status}")


def load_trees_by_file(run_manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for doc in list(run_manifest.get("documents") or []):
        if not isinstance(doc, Mapping):
            continue
        expected_file = str(doc.get("expected_file") or "")
        if not expected_file:
            continue
        tree_path_text = doc.get("tree_json_path")
        if doc.get("status") != "TREE_GENERATED" or not tree_path_text:
            result[expected_file] = {
                "status": str(doc.get("status") or "TREE_UNAVAILABLE"),
                "nodes": [],
                "tree_json_path": tree_path_text,
            }
            continue
        tree_path = resolve_repo_path(str(tree_path_text))
        if not tree_path.exists():
            result[expected_file] = {
                "status": "TREE_JSON_PATH_MISSING",
                "nodes": [],
                "tree_json_path": tree_path_text,
            }
            continue
        tree = read_json(tree_path)
        result[expected_file] = {
            "status": "TREE_AVAILABLE",
            "nodes": flatten_nodes(tree.get("structure") or []),
            "tree_json_path": display_path(tree_path),
        }
    return result


def canary_ids_for_run(run_manifest: Mapping[str, Any], fit_audit_rows: list[dict[str, str]]) -> set[str]:
    explicit = {
        str(item).strip()
        for item in list(run_manifest.get("canary_query_ids") or [])
        if str(item).strip()
    }
    if explicit:
        return explicit
    return {
        str(row.get("query_id") or "").strip()
        for row in fit_audit_rows
        if str(row.get("track") or "").strip().upper() == "PDF"
        and str(row.get("pageindex_fit") or "").strip() == "partial_pdf_tree_candidate"
        and str(row.get("query_id") or "").strip()
    }


def flatten_nodes(nodes: list[Any], depth: int = 0, parent_id: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            continue
        node_id = str(node.get("node_id") or f"{parent_id or 'root'}-{index}")
        rows.append({
            "node_id": node_id,
            "parent_id": parent_id,
            "depth": depth,
            "title": str(node.get("title") or ""),
            "start_index": to_int(node.get("start_index")),
            "end_index": to_int(node.get("end_index")),
        })
        rows.extend(flatten_nodes(list(node.get("nodes") or []), depth + 1, node_id))
    return rows


def selected_node_summaries(nodes: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "node_id": node.get("node_id"),
            "title": node.get("title"),
            "start_index": node.get("start_index"),
            "end_index": node.get("end_index"),
            "depth": node.get("depth"),
            "title_token_overlap": node.get("title_token_overlap"),
        }
        for node in nodes[:5]
    ]


def validate_guardrails(label: str, payload: Mapping[str, Any], blockers: list[str], allow_missing: bool = False) -> None:
    if not payload:
        if not allow_missing:
            blockers.append(f"{label} missing or empty")
        return
    if payload.get("promotion_evidence") is not False:
        blockers.append(f"{label} must keep promotion_evidence=false")
    if payload.get("evidence_role") not in {None, "diagnostic"}:
        blockers.append(f"{label} must keep evidence_role=diagnostic when present")
    for key, expected in (
        ("xlsx_scope_excluded", True),
        ("pdf_scope_only", True),
        ("external_cloud_llm_run", False),
        ("bbox_contract_success_not_claimed", True),
        ("table_semantics_success_not_claimed", True),
        ("pdf_c7_policy_decision_applied", False),
        ("retrieval_tuning_applied", False),
        ("parser_expansion_applied", False),
        ("official_denominator_changed", False),
    ):
        if key in payload and payload.get(key) is not expected:
            blockers.append(f"{label}.{key} must be {expected!r}")


def rows_by_query_id(rows: Any) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if isinstance(row, Mapping):
            query_id = str(row.get("query_id") or "").strip()
            if query_id:
                result[query_id] = row
    return result


def write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: csv_value(row.get(key))
                for key in CSV_FIELDS
            })


def csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {display_path(path)}")
    return payload


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def artifact_identity(path: Path | None) -> dict[str, Any]:
    if path is None:
        return missing_artifact("")
    return {
        "path": display_path(path),
        "exists": path.exists(),
    }


def missing_artifact(path: str) -> dict[str, Any]:
    return {
        "path": path,
        "exists": False,
    }


def latest_input_manifest() -> Path:
    candidates = sorted(
        (AI_WORKER / "eval" / "artifacts" / "eval_runs").glob(
            "pdf_pageindex_comparison_*/pageindex_pdf_input_manifest.json"
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No pdf_pageindex_comparison input manifest found")
    return candidates[0].resolve()


def default_run_manifest(input_manifest_path: Path) -> Path | None:
    candidate = input_manifest_path.parent / "pageindex_run_manifest.json"
    return candidate.resolve() if candidate.exists() else None


def resolve_run_manifest(path: Path, input_manifest_path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    for candidate in (input_manifest_path.parent / path, Path.cwd() / path, AI_WORKER / path, ROOT / path):
        if candidate.exists():
            return candidate.resolve()
    return (Path.cwd() / path).resolve()


def resolve_manifest(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    for candidate in (Path.cwd() / path, AI_WORKER / path, ROOT / path):
        if candidate.exists():
            return candidate.resolve()
    return (Path.cwd() / path).resolve()


def resolve_existing_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    candidates: list[Path] = []
    parts = path.parts
    if parts and parts[0] == "eval":
        candidates.append(AI_WORKER / path)
    if parts and parts[0] == "ai":
        candidates.append(ROOT / path)
    candidates.extend([Path.cwd() / path, AI_WORKER / path, ROOT / path])
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def resolve_output_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    parts = path.parts
    if parts and parts[0] == "eval":
        return (AI_WORKER / path).resolve()
    if parts and parts[0] == "ai":
        return (ROOT / path).resolve()
    return (Path.cwd() / path).resolve()


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def display_path(path: Path | None) -> str:
    if path is None:
        return ""
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def summary_for_stdout(payload: Mapping[str, Any], json_report_path: Path, csv_report_path: Path) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "json_report": display_path(json_report_path),
        "csv_report": display_path(csv_report_path),
        "live_pageindex_run": payload.get("live_pageindex_run"),
        "promotion_evidence": payload.get("promotion_evidence"),
        "counts": payload.get("counts"),
        "blockers": payload.get("blockers"),
        "warnings": payload.get("warnings"),
    }


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-manifest", default=None, help="PageIndex PDF input manifest. Defaults to latest.")
    parser.add_argument("--run-manifest", default=None, help="PageIndex run manifest. Defaults to same artifact dir.")
    parser.add_argument("--c5-report", default=str(DEFAULT_C5_REPORT))
    parser.add_argument("--c6-report", default=str(DEFAULT_C6_REPORT))
    parser.add_argument("--c7-report", default=str(DEFAULT_C7_REPORT))
    parser.add_argument("--fit-audit", default=str(DEFAULT_FIT_AUDIT))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
