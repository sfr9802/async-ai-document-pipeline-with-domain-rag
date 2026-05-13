"""Analyze PageIndex PDF tree oracle coverage for the local canary.

This is report-only. It reads the local PageIndex canary comparator output and
tree artifacts, then classifies whether the current bottleneck is tree coverage,
query navigation, or downstream bbox/table/gold-policy scope. It does not run
PageIndex, retrieval, reranking, parser expansion, indexing, DB writes, or
promotion.
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
from statistics import median
from typing import Any, Iterable, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER = SCRIPT_DIR.parent
ROOT = AI_WORKER.parent

DEFAULT_LOCAL_CANARY_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_pageindex_local_canary_report.json")
DEFAULT_LOCAL_CANARY_CSV = Path("eval/reports/rag-ingestion/rag_pdf_pageindex_local_canary.csv")
DEFAULT_C5_REPORT = Path("eval/reports/rag-ingestion/rag_retrieval_eval_pdf_vector_diagnostic_report.json")
DEFAULT_C6_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_vector_quality_breakdown.json")
DEFAULT_C7_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_gold_policy_review.json")
DEFAULT_JSON_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_pageindex_oracle_coverage_report.json")
DEFAULT_CSV_REPORT = Path("eval/reports/rag-ingestion/rag_pdf_pageindex_oracle_coverage.csv")

GUARDRAILS = {
    "promotion_evidence": False,
    "evidence_role": "diagnostic",
    "xlsx_scope_excluded": True,
    "pdf_scope_only": True,
    "external_cloud_llm_run": False,
    "bbox_contract_success_not_claimed": True,
    "table_semantics_success_not_claimed": True,
    "pdf_c7_policy_decision_applied": False,
    "official_denominator_changed": False,
    "retrieval_tuning_applied": False,
    "parser_expansion_applied": False,
}

LIKELY_BOTTLENECKS = {
    "TREE_RANGE_INVALID",
    "TREE_GRANULARITY_TOO_COARSE",
    "TREE_MISSING_EXPECTED_PAGE",
    "NAVIGATION_MISSED_EXISTING_ORACLE_NODE",
    "PAGE_SECTION_NAVIGATION_OK_BBOX_OR_TABLE_STILL_UNSOLVED",
    "GOLD_POLICY_STILL_BLOCKED",
    "PAGEINDEX_RUN_UNAVAILABLE",
}

BBOX_TABLE_OR_CHUNK_FAILURE_RE = re.compile(r"BBOX|TABLE|CHUNK|PARSER", re.IGNORECASE)
CSV_FIELDS = [
    "query_id",
    "expected_page_no",
    "tree_build_success",
    "invalid_range_count",
    "invalid_range_examples",
    "expected_page_present_in_tree",
    "oracle_node_id",
    "oracle_node_title",
    "oracle_node_page_range",
    "oracle_node_page_width",
    "selected_node_id",
    "selected_node_title",
    "selected_page_range",
    "selected_page_width",
    "selected_contains_expected_page",
    "oracle_exists_but_navigation_missed",
    "likely_bottleneck",
]

RANGE_FIELD_PAIRS = (
    ("start_index", "end_index"),
    ("start_page", "end_page"),
    ("start_page_no", "end_page_no"),
    ("page_start", "page_end"),
    ("from_page", "to_page"),
    ("start", "end"),
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_manifest_path = resolve_manifest(Path(args.input_manifest)) if args.input_manifest else latest_input_manifest()
    run_manifest_path = resolve_run_manifest(Path(args.run_manifest), input_manifest_path) if args.run_manifest else default_run_manifest(input_manifest_path)
    local_canary_report_path = resolve_existing_path(Path(args.local_canary_report))
    local_canary_csv_path = resolve_existing_path(Path(args.local_canary_csv))
    c5_path = resolve_existing_path(Path(args.c5_report))
    c6_path = resolve_existing_path(Path(args.c6_report))
    c7_path = resolve_existing_path(Path(args.c7_report))
    json_report_path = resolve_output_path(Path(args.report))
    csv_report_path = resolve_output_path(Path(args.csv))

    input_manifest = read_json(input_manifest_path)
    run_manifest = read_json(run_manifest_path) if run_manifest_path and run_manifest_path.exists() else {}
    local_canary_report = read_json(local_canary_report_path)
    local_canary_csv_rows = read_csv(local_canary_csv_path) if local_canary_csv_path.exists() else []
    c5_report = read_json(c5_path)
    c6_report = read_json(c6_path)
    c7_report = read_json(c7_path)

    payload = build_report(
        input_manifest=input_manifest,
        input_manifest_path=input_manifest_path,
        run_manifest=run_manifest,
        run_manifest_path=run_manifest_path,
        local_canary_report=local_canary_report,
        local_canary_report_path=local_canary_report_path,
        local_canary_csv_rows=local_canary_csv_rows,
        local_canary_csv_path=local_canary_csv_path,
        c5_report=c5_report,
        c5_path=c5_path,
        c6_report=c6_report,
        c6_path=c6_path,
        c7_report=c7_report,
        c7_path=c7_path,
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
    local_canary_report: Mapping[str, Any],
    local_canary_report_path: Path,
    local_canary_csv_rows: list[dict[str, str]],
    local_canary_csv_path: Path,
    c5_report: Mapping[str, Any],
    c5_path: Path,
    c6_report: Mapping[str, Any],
    c6_path: Path,
    c7_report: Mapping[str, Any],
    c7_path: Path,
    json_report_path: Path,
    csv_report_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    validate_guardrails("input_manifest", input_manifest, blockers)
    validate_guardrails("run_manifest", run_manifest, blockers, allow_missing=True)
    validate_guardrails("local_canary_report", local_canary_report, blockers)
    validate_guardrails("c5_report", c5_report, blockers)
    validate_guardrails("c6_report", c6_report, blockers)
    validate_guardrails("c7_report", c7_report, blockers)

    local_rows_by_id = rows_by_query_id(local_canary_report.get("query_results") or [])
    local_csv_by_id = rows_by_query_id(local_canary_csv_rows)
    manifest_rows_by_id = rows_by_query_id(input_manifest.get("queries") or [])
    canary_query_ids = ordered_canary_ids(input_manifest, run_manifest, local_canary_report)
    tree_by_file = load_tree_docs(run_manifest, input_manifest, warnings)
    live_pageindex_run = bool(run_manifest.get("live_pageindex_run") or local_canary_report.get("live_pageindex_run"))
    local_pageindex_run = bool(run_manifest.get("local_pageindex_run") or local_canary_report.get("local_pageindex_run"))

    query_results: list[dict[str, Any]] = []
    for query_id in canary_query_ids:
        manifest_row = manifest_rows_by_id.get(query_id, {})
        local_row = local_rows_by_id.get(query_id, {})
        csv_row = local_csv_by_id.get(query_id, {})
        query_results.append(analyze_query(
            query_id=query_id,
            manifest_row=manifest_row,
            local_row=local_row,
            csv_row=csv_row,
            tree_doc=tree_by_file.get(str((manifest_row or local_row).get("expected_file") or "")),
            live_pageindex_run=live_pageindex_run,
        ))

    csv_only_ids = sorted(set(local_csv_by_id) - set(local_rows_by_id))
    if csv_only_ids:
        warnings.append(f"Local canary CSV has {len(csv_only_ids)} query_id values absent from JSON query_results.")
    missing_local_rows = [query_id for query_id in canary_query_ids if query_id not in local_rows_by_id]
    if missing_local_rows:
        warnings.append(f"Missing local canary JSON rows for canary query ids: {', '.join(missing_local_rows)}")

    count_payload = build_counts(query_results, tree_by_file)
    status = report_status(query_results, blockers)
    return {
        "schema_version": "pdf_pageindex_oracle_coverage_report_v1",
        "run_id": str(input_manifest.get("run_id") or run_manifest.get("run_id") or local_canary_report.get("run_id") or ""),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "PageIndex PDF oracle coverage diagnostic",
        "source_file_type": "PDF",
        **GUARDRAILS,
        "live_pageindex_run": live_pageindex_run,
        "local_pageindex_run": local_pageindex_run,
        "pageindex_role": "pdf_page_section_navigator_candidate_only",
        "oracle_selection_rule": "smallest_1_based_inclusive_page_width_node_containing_expected_page",
        "likely_bottleneck_values": sorted(LIKELY_BOTTLENECKS),
        "promotion_execution": "not_run_by_this_script",
        "retrieval_execution": "not_run_by_this_script",
        "indexing_execution": "not_run_by_this_script",
        "parser_execution": "not_run_by_this_script",
        "input_artifacts": [
            artifact_identity(input_manifest_path),
            artifact_identity(run_manifest_path) if run_manifest_path else missing_artifact("pageindex_run_manifest.json"),
            artifact_identity(local_canary_report_path),
            artifact_identity(local_canary_csv_path),
            artifact_identity(c5_path),
            artifact_identity(c6_path),
            artifact_identity(c7_path),
        ],
        "output_artifacts": {
            "json_report": display_path(json_report_path),
            "csv_report": display_path(csv_report_path),
        },
        "source_local_canary_counts": local_canary_report.get("counts") or {},
        "counts": count_payload,
        "query_results": query_results,
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "notes": [
            "This report decomposes the local PageIndex canary into tree oracle coverage, query navigation, and downstream bbox/table/C7 scope.",
            "PageIndex output is not claimed as bbox overlap success or table/value semantics success.",
            "C7 policy decisions remain user-owned and were not applied by this script.",
            "XLSX remains excluded; no XLSX PageIndex adapter was implemented.",
        ],
    }


def analyze_query(
    *,
    query_id: str,
    manifest_row: Mapping[str, Any],
    local_row: Mapping[str, Any],
    csv_row: Mapping[str, Any],
    tree_doc: Mapping[str, Any] | None,
    live_pageindex_run: bool,
) -> dict[str, Any]:
    expected_page = first_int(manifest_row.get("expected_page_no"), local_row.get("expected_page_no"), csv_row.get("expected_page_no"))
    tree_build_success = bool(live_pageindex_run and tree_doc and tree_doc.get("status") == "TREE_AVAILABLE")
    nodes = list((tree_doc or {}).get("nodes") or [])
    invalid_ranges = list((tree_doc or {}).get("invalid_ranges") or [])
    expected_page_nodes = [
        node for node in nodes
        if range_contains(node.get("page_range"), expected_page)
    ] if tree_build_success else []
    expected_page_nodes.sort(key=oracle_sort_key)
    oracle_node = expected_page_nodes[0] if expected_page_nodes else {}
    selected_node = selected_node_for_query(local_row, csv_row, nodes)
    selected_range = selected_page_range_for_query(local_row, csv_row, selected_node)
    selected_contains_expected = bool(range_contains(selected_range, expected_page))
    oracle_exists = bool(oracle_node)
    oracle_exists_but_navigation_missed = bool(oracle_exists and not selected_contains_expected)
    c7_policy_pending = truthy(local_row.get("c7_policy_pending")) or truthy(local_row.get("c7_policy_pending_preserved"))
    bbox_table_still_unsolved = row_has_bbox_table_failure(local_row, manifest_row)
    invalid_expected_page_ranges = [
        invalid for invalid in invalid_ranges
        if range_contains(invalid.get("page_range"), expected_page)
    ]
    invalid_range_examples = prioritized_invalid_examples(invalid_expected_page_ranges, invalid_ranges)
    likely_bottleneck = classify_bottleneck(
        tree_build_success=tree_build_success,
        expected_page_present=bool(expected_page_nodes),
        invalid_expected_page_ranges=invalid_expected_page_ranges,
        oracle_node=oracle_node,
        selected_contains_expected=selected_contains_expected,
        oracle_exists_but_navigation_missed=oracle_exists_but_navigation_missed,
        c7_policy_pending=c7_policy_pending,
        bbox_table_still_unsolved=bbox_table_still_unsolved,
    )
    validate_bottleneck(likely_bottleneck)
    return {
        "query_id": query_id,
        "expected_page_no": expected_page,
        "tree_build_success": tree_build_success,
        "invalid_range_count": len(invalid_ranges),
        "invalid_range_examples": invalid_range_examples,
        "expected_page_present_in_tree": bool(expected_page_nodes),
        "oracle_node_id": oracle_node.get("node_id"),
        "oracle_node_title": oracle_node.get("title"),
        "oracle_node_page_range": oracle_node.get("page_range"),
        "oracle_node_page_width": range_width(oracle_node.get("page_range")),
        "selected_node_id": selected_node.get("node_id") or empty_to_none(local_row.get("selected_node_id")) or empty_to_none(csv_row.get("selected_node_id")),
        "selected_node_title": selected_node.get("title") or empty_to_none(local_row.get("selected_node_title")) or empty_to_none(csv_row.get("selected_node_title")),
        "selected_page_range": selected_range,
        "selected_page_width": range_width(selected_range),
        "selected_contains_expected_page": selected_contains_expected,
        "oracle_exists_but_navigation_missed": oracle_exists_but_navigation_missed,
        "likely_bottleneck": likely_bottleneck,
    }


def prioritized_invalid_examples(
    relevant_ranges: list[Mapping[str, Any]],
    all_ranges: list[Mapping[str, Any]],
    *,
    limit: int = 5,
) -> list[Mapping[str, Any]]:
    examples: list[Mapping[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in [*relevant_ranges, *all_ranges]:
        key = (
            str(item.get("node_id") or ""),
            json.dumps(item.get("reasons") or [], ensure_ascii=False, sort_keys=True),
        )
        if key in seen:
            continue
        seen.add(key)
        examples.append(item)
        if len(examples) >= limit:
            break
    return examples


def build_counts(query_results: list[Mapping[str, Any]], tree_by_file: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    oracle_widths = [
        int(width) for width in (row.get("oracle_node_page_width") for row in query_results)
        if isinstance(width, int)
    ]
    selected_widths = [
        int(width) for width in (row.get("selected_page_width") for row in query_results)
        if isinstance(width, int)
    ]
    canary_tree_files = {
        str(row.get("expected_file") or "")
        for row in query_results
        if row.get("expected_file")
    }
    invalid_range_generated_count = 0
    for expected_file, tree_doc in tree_by_file.items():
        if canary_tree_files and expected_file not in canary_tree_files:
            continue
        invalid_range_generated_count += len(list(tree_doc.get("invalid_ranges") or []))
    bottleneck_counts = Counter(str(row.get("likely_bottleneck") or "UNKNOWN") for row in query_results)
    return {
        "canary_candidate_count": len(query_results),
        "tree_build_success_count": sum(1 for row in query_results if row.get("tree_build_success") is True),
        "invalid_range_generated_count": invalid_range_generated_count,
        "expected_page_present_in_tree_count": sum(1 for row in query_results if row.get("expected_page_present_in_tree") is True),
        "oracle_node_found_count": sum(1 for row in query_results if row.get("oracle_node_id")),
        "oracle_node_width_median": median(oracle_widths) if oracle_widths else None,
        "selected_node_width_median": median(selected_widths) if selected_widths else None,
        "selected_contains_expected_page_count": sum(1 for row in query_results if row.get("selected_contains_expected_page") is True),
        "oracle_exists_but_navigation_missed_count": sum(1 for row in query_results if row.get("oracle_exists_but_navigation_missed") is True),
        "expected_page_not_present_in_tree_count": sum(1 for row in query_results if row.get("expected_page_present_in_tree") is False),
        "page_section_ok_but_bbox_or_table_unsolved_count": bottleneck_counts.get(
            "PAGE_SECTION_NAVIGATION_OK_BBOX_OR_TABLE_STILL_UNSOLVED", 0
        ),
        "gold_policy_still_blocked_count": bottleneck_counts.get("GOLD_POLICY_STILL_BLOCKED", 0),
        "likely_bottleneck_counts": dict(sorted(bottleneck_counts.items())),
    }


def report_status(query_results: list[Mapping[str, Any]], blockers: list[str]) -> str:
    if blockers:
        return "FAIL_CLOSED_GUARDRAIL_OR_INPUT_ERROR"
    bottlenecks = {str(row.get("likely_bottleneck") or "") for row in query_results}
    if "PAGEINDEX_RUN_UNAVAILABLE" in bottlenecks:
        return "DIAGNOSTIC_COMPLETED_WITH_PAGEINDEX_UNAVAILABLE"
    if "TREE_RANGE_INVALID" in bottlenecks:
        return "DIAGNOSTIC_COMPLETED_WITH_TREE_RANGE_INVALID"
    if "TREE_MISSING_EXPECTED_PAGE" in bottlenecks:
        return "DIAGNOSTIC_COMPLETED_WITH_TREE_ORACLE_GAPS"
    if "NAVIGATION_MISSED_EXISTING_ORACLE_NODE" in bottlenecks:
        return "DIAGNOSTIC_COMPLETED_WITH_QUERY_NAVIGATION_MISSES"
    if "PAGE_SECTION_NAVIGATION_OK_BBOX_OR_TABLE_STILL_UNSOLVED" in bottlenecks:
        return "DIAGNOSTIC_COMPLETED_WITH_BBOX_OR_TABLE_OUT_OF_SCOPE"
    if "GOLD_POLICY_STILL_BLOCKED" in bottlenecks:
        return "DIAGNOSTIC_COMPLETED_WITH_GOLD_POLICY_BLOCKERS"
    return "DIAGNOSTIC_COMPLETED"


def classify_bottleneck(
    *,
    tree_build_success: bool,
    expected_page_present: bool,
    invalid_expected_page_ranges: list[Mapping[str, Any]],
    oracle_node: Mapping[str, Any],
    selected_contains_expected: bool,
    oracle_exists_but_navigation_missed: bool,
    c7_policy_pending: bool,
    bbox_table_still_unsolved: bool,
) -> str:
    if not tree_build_success:
        return "PAGEINDEX_RUN_UNAVAILABLE"
    if invalid_expected_page_ranges:
        return "TREE_RANGE_INVALID"
    if not expected_page_present:
        return "TREE_MISSING_EXPECTED_PAGE"
    if oracle_exists_but_navigation_missed:
        return "NAVIGATION_MISSED_EXISTING_ORACLE_NODE"
    if c7_policy_pending:
        return "GOLD_POLICY_STILL_BLOCKED"
    if selected_contains_expected and bbox_table_still_unsolved:
        return "PAGE_SECTION_NAVIGATION_OK_BBOX_OR_TABLE_STILL_UNSOLVED"
    if range_width(oracle_node.get("page_range")) and int(range_width(oracle_node.get("page_range")) or 0) > 1:
        return "TREE_GRANULARITY_TOO_COARSE"
    return "TREE_GRANULARITY_TOO_COARSE"


def load_tree_docs(
    run_manifest: Mapping[str, Any],
    input_manifest: Mapping[str, Any],
    warnings: list[str],
) -> dict[str, dict[str, Any]]:
    input_docs_by_file = {
        str(doc.get("expected_file") or ""): doc
        for doc in list(input_manifest.get("documents") or [])
        if isinstance(doc, Mapping) and str(doc.get("expected_file") or "")
    }
    result: dict[str, dict[str, Any]] = {}
    for doc in list(run_manifest.get("documents") or []):
        if not isinstance(doc, Mapping):
            continue
        expected_file = str(doc.get("expected_file") or "")
        if not expected_file:
            continue
        tree_path_text = str(doc.get("tree_json_path") or "")
        input_doc = input_docs_by_file.get(expected_file, {})
        page_count, page_count_source = document_page_count(doc, input_doc)
        if doc.get("status") != "TREE_GENERATED" or not tree_path_text:
            result[expected_file] = {
                "status": str(doc.get("status") or "TREE_UNAVAILABLE"),
                "nodes": [],
                "invalid_ranges": [],
                "tree_json_path": tree_path_text or None,
                "page_count": page_count,
                "page_count_source": page_count_source,
            }
            continue
        tree_path = resolve_repo_path(tree_path_text)
        if not tree_path.exists():
            result[expected_file] = {
                "status": "TREE_JSON_PATH_MISSING",
                "nodes": [],
                "invalid_ranges": [],
                "tree_json_path": tree_path_text,
                "page_count": page_count,
                "page_count_source": page_count_source,
            }
            continue
        tree = read_json(tree_path)
        nodes, invalid_ranges = flatten_nodes_with_ranges(
            list(tree.get("structure") or []),
            page_count=page_count,
        )
        if page_count is None:
            warnings.append(f"Document page count unavailable for {expected_file}; page-count overflow validation skipped.")
        result[expected_file] = {
            "status": "TREE_AVAILABLE",
            "nodes": nodes,
            "invalid_ranges": invalid_ranges,
            "tree_json_path": display_path(tree_path),
            "page_count": page_count,
            "page_count_source": page_count_source,
        }
    return result


def flatten_nodes_with_ranges(
    nodes: list[Any],
    *,
    page_count: int | None,
    depth: int = 0,
    parent_id: str | None = None,
    parent_range: list[int] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    invalid_ranges: list[dict[str, Any]] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            continue
        node_id = str(node.get("node_id") or f"{parent_id or 'root'}-{index}")
        page_range, range_source, range_errors = extract_page_range(node)
        invalid_reasons = list(range_errors)
        if page_range is not None:
            start, end = page_range
            if start < 1 or end < 1:
                invalid_reasons.append("NON_POSITIVE_PAGE_RANGE")
            if start > end:
                invalid_reasons.append("START_AFTER_END")
            if page_count is not None and end > page_count:
                invalid_reasons.append("RANGE_EXCEEDS_DOCUMENT_PAGE_COUNT")
            if (
                parent_range is not None
                and parent_range[0] <= parent_range[1]
                and (start < parent_range[0] or end > parent_range[1])
            ):
                invalid_reasons.append("CHILD_RANGE_OUTSIDE_PARENT")
        row = {
            "node_id": node_id,
            "parent_id": parent_id,
            "depth": depth,
            "title": str(node.get("title") or ""),
            "page_range": page_range,
            "page_width": range_width(page_range),
            "range_source": range_source,
            "invalid_reasons": dedupe(invalid_reasons),
        }
        rows.append(row)
        if invalid_reasons:
            invalid_ranges.append({
                "node_id": node_id,
                "title": row["title"],
                "page_range": page_range,
                "range_source": range_source,
                "parent_node_id": parent_id,
                "parent_page_range": parent_range,
                "reasons": dedupe(invalid_reasons),
            })
        child_rows, child_invalid = flatten_nodes_with_ranges(
            list(node.get("nodes") or []),
            page_count=page_count,
            depth=depth + 1,
            parent_id=node_id,
            parent_range=page_range,
        )
        rows.extend(child_rows)
        invalid_ranges.extend(child_invalid)
    return rows, invalid_ranges


def extract_page_range(node: Mapping[str, Any]) -> tuple[list[int] | None, str | None, list[str]]:
    selected_range = node.get("selected_page_range")
    if selected_range not in (None, ""):
        parsed = parse_page_range(selected_range)
        if parsed is not None:
            return parsed, "selected_page_range", []
        return None, "selected_page_range", ["NON_INTEGER_PAGE_RANGE"]
    for start_key, end_key in RANGE_FIELD_PAIRS:
        if start_key in node or end_key in node:
            start = to_int(node.get(start_key))
            end = to_int(node.get(end_key))
            source = f"{start_key}/{end_key}"
            if start is None or end is None:
                return None, source, ["MISSING_OR_NON_INTEGER_PAGE_RANGE"]
            return [start, end], source, []
    return None, None, ["MISSING_PAGE_RANGE"]


def document_page_count(doc: Mapping[str, Any], input_doc: Mapping[str, Any]) -> tuple[int | None, str]:
    manifest_count = to_int(doc.get("page_count")) or to_int(input_doc.get("page_count"))
    if manifest_count is not None:
        return manifest_count, "manifest"
    pdf_path_text = str(doc.get("pdf_path") or input_doc.get("pdf_path") or "")
    if not pdf_path_text:
        return None, "unavailable"
    pdf_path = resolve_repo_path(pdf_path_text)
    count = pdf_page_count(pdf_path)
    if count is not None:
        return count, "pdf_reader"
    return None, "unavailable"


def pdf_page_count(path: Path) -> int | None:
    try:
        from PyPDF2 import PdfReader  # type: ignore

        return len(PdfReader(str(path)).pages)
    except Exception:
        try:
            from pypdf import PdfReader  # type: ignore

            return len(PdfReader(str(path)).pages)
        except Exception:
            try:
                import fitz  # type: ignore

                document = fitz.open(str(path))
                try:
                    return int(document.page_count)
                finally:
                    document.close()
            except Exception:
                return None


def selected_node_for_query(
    local_row: Mapping[str, Any],
    csv_row: Mapping[str, Any],
    nodes: list[Mapping[str, Any]],
) -> dict[str, Any]:
    selected_id = str(local_row.get("selected_node_id") or csv_row.get("selected_node_id") or "").strip()
    if not selected_id:
        selected_nodes = local_row.get("pageindex_selected_nodes")
        if isinstance(selected_nodes, list) and selected_nodes and isinstance(selected_nodes[0], Mapping):
            selected_id = str(selected_nodes[0].get("node_id") or "").strip()
    for node in nodes:
        if str(node.get("node_id") or "") == selected_id:
            return dict(node)
    if selected_id:
        return {
            "node_id": selected_id,
            "title": empty_to_none(local_row.get("selected_node_title")) or empty_to_none(csv_row.get("selected_node_title")),
            "page_range": parse_page_range(local_row.get("selected_page_range")) or parse_page_range(csv_row.get("selected_page_range")),
        }
    return {}


def selected_page_range_for_query(
    local_row: Mapping[str, Any],
    csv_row: Mapping[str, Any],
    selected_node: Mapping[str, Any],
) -> list[int] | None:
    for value in (local_row.get("selected_page_range"), csv_row.get("selected_page_range"), selected_node.get("page_range")):
        parsed = parse_page_range(value)
        if parsed is not None:
            return parsed
    return None


def parse_page_range(value: Any) -> list[int] | None:
    if value in (None, ""):
        return None
    if isinstance(value, Mapping):
        start = first_int(value.get("start_page"), value.get("start"), value.get("start_index"))
        end = first_int(value.get("end_page"), value.get("end"), value.get("end_index"))
        return [start, end] if start is not None and end is not None else None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        start = to_int(value[0])
        end = to_int(value[1])
        return [start, end] if start is not None and end is not None else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            decoded = None
        if decoded is not None:
            parsed = parse_page_range(decoded)
            if parsed is not None:
                return parsed
        numbers = [to_int(item) for item in re.findall(r"-?\d+", text)]
        numbers = [item for item in numbers if item is not None]
        if len(numbers) >= 2:
            return [int(numbers[0]), int(numbers[1])]
    return None


def range_contains(page_range: Any, page: int | None) -> bool:
    parsed = parse_page_range(page_range)
    if parsed is None or page is None:
        return False
    start, end = parsed
    return start <= end and start >= 1 and start <= page <= end


def range_width(page_range: Any) -> int | None:
    parsed = parse_page_range(page_range)
    if parsed is None:
        return None
    start, end = parsed
    if start < 1 or end < start:
        return None
    return end - start + 1


def oracle_sort_key(node: Mapping[str, Any]) -> tuple[int, int, int, str]:
    page_range = parse_page_range(node.get("page_range")) or [10**9, 10**9]
    width = range_width(page_range) or 10**9
    depth = to_int(node.get("depth")) or 0
    start = page_range[0]
    return (width, -depth, start, str(node.get("node_id") or ""))


def ordered_canary_ids(
    input_manifest: Mapping[str, Any],
    run_manifest: Mapping[str, Any],
    local_canary_report: Mapping[str, Any],
) -> list[str]:
    explicit = [
        str(item).strip()
        for item in list(run_manifest.get("canary_query_ids") or [])
        if str(item).strip()
    ]
    if not explicit:
        explicit = [
            str(item).strip()
            for item in list(local_canary_report.get("live_tree_usefulness_denominator_query_ids") or [])
            if str(item).strip()
        ]
    explicit_set = set(explicit)
    ordered = [
        str(row.get("query_id") or "").strip()
        for row in list(input_manifest.get("queries") or [])
        if isinstance(row, Mapping) and str(row.get("query_id") or "").strip() in explicit_set
    ]
    ordered.extend(query_id for query_id in explicit if query_id not in ordered)
    return ordered


def row_has_bbox_table_failure(*rows: Mapping[str, Any]) -> bool:
    parts: list[str] = []
    for row in rows:
        parts.append(str(row.get("c6_failure_type") or ""))
        parts.extend(str(item) for item in list(row.get("c6_failure_types") or []))
    return bool(BBOX_TABLE_OR_CHUNK_FAILURE_RE.search(" ".join(parts)))


def validate_bottleneck(value: str) -> None:
    if value not in LIKELY_BOTTLENECKS:
        raise ValueError(f"Invalid likely_bottleneck: {value}")


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
            writer.writerow({key: csv_value(row.get(key)) for key in CSV_FIELDS})


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


def display_path(path: Path | None) -> str:
    if path is None:
        return ""
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def first_int(*values: Any) -> int | None:
    for value in values:
        parsed = to_int(value)
        if parsed is not None:
            return parsed
    return None


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def empty_to_none(value: Any) -> Any:
    if value in (None, ""):
        return None
    return value


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def dedupe(values: Iterable[str]) -> list[str]:
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
        "promotion_evidence": payload.get("promotion_evidence"),
        "evidence_role": payload.get("evidence_role"),
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
    parser.add_argument("--local-canary-report", default=str(DEFAULT_LOCAL_CANARY_REPORT))
    parser.add_argument("--local-canary-csv", default=str(DEFAULT_LOCAL_CANARY_CSV))
    parser.add_argument("--c5-report", default=str(DEFAULT_C5_REPORT))
    parser.add_argument("--c6-report", default=str(DEFAULT_C6_REPORT))
    parser.add_argument("--c7-report", default=str(DEFAULT_C7_REPORT))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
