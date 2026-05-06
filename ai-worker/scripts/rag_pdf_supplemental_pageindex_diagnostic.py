"""Diagnostic-only PageIndex pass for supplemental elec/lh synthetic anchors."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from rag_pdf_supplemental_common import (
    COMMON_GUARDRAILS,
    REPORT_DIR,
    SCRIPT_DIR,
    artifact_identity,
    bbox_to_list,
    display_path,
    latest_supplemental_artifact_dir,
    local_pageindex_preflight,
    read_csv,
    read_json,
    resolve_path,
    sha256_file,
    sorted_counter,
    to_int,
    utc_timestamp,
    write_csv,
    write_json,
)


DEFAULT_ANCHOR_CSV = Path("eval/eval_queries/gold_queries_pdf_supplemental_elec_lh_synthetic_diagnostic.csv")
DEFAULT_JSON_REPORT = REPORT_DIR / "rag_pdf_supplemental_pageindex_diagnostic_report.json"
DEFAULT_CSV_REPORT = REPORT_DIR / "rag_pdf_supplemental_pageindex_diagnostic.csv"

CSV_FIELDS = [
    "query_id",
    "dataset_source",
    "file_name",
    "relative_path",
    "parser_derived_expected_page_no",
    "tree_build_success",
    "query_navigation_success",
    "selected_node_id",
    "selected_node_title",
    "selected_page_range",
    "selected_page_width",
    "parser_derived_expected_page_overlap",
    "expected_page_present_in_any_tree",
    "expected_page_present_in_valid_tree",
    "oracle_node_id",
    "oracle_node_title",
    "oracle_node_page_range",
    "selected_contains_expected_page",
    "oracle_exists_but_navigation_missed",
    "invalid_range_count",
    "invalid_child_outside_parent_count",
    "tree_integrity_status",
    "bbox_contract_solved",
    "table_semantics_solved",
    "comparison_status",
]

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = resolve_artifact_dir(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    anchor_csv_path = resolve_path(args.anchor_csv)
    input_manifest_path = artifact_dir / "pageindex_supplemental_input_manifest.json"
    run_manifest_path = artifact_dir / "pageindex_run_manifest.json"
    tree_dir = artifact_dir / "pageindex_trees"
    report_path = resolve_path(args.report)
    csv_path = resolve_path(args.csv)
    anchors = read_csv(anchor_csv_path) if anchor_csv_path.exists() else []

    payload = build_pageindex_diagnostic(
        anchors=anchors,
        anchor_csv_path=anchor_csv_path,
        artifact_dir=artifact_dir,
        input_manifest_path=input_manifest_path,
        run_manifest_path=run_manifest_path,
        tree_dir=tree_dir,
        report_path=report_path,
        csv_path=csv_path,
        allow_local_run=bool(args.allow_local_run),
        model=args.model,
        base_url=args.base_url,
        pageindex_root=args.pageindex_root,
        pageindex_python=args.python,
        timeout_seconds=args.timeout_seconds,
    )
    write_json(input_manifest_path, payload["input_manifest"])
    write_json(run_manifest_path, payload["run_manifest"])
    write_json(report_path, payload["report"])
    write_csv(csv_path, payload["rows"], CSV_FIELDS)
    print(json.dumps({
        "status": payload["report"]["status"],
        "json_report": display_path(report_path),
        "csv_report": display_path(csv_path),
        "run_manifest": display_path(run_manifest_path),
        "counts": payload["report"]["counts"],
        "blockers": payload["report"]["blockers"],
    }, ensure_ascii=False, indent=2))
    return 0 if not payload["report"]["blockers"] else 2


def build_pageindex_diagnostic(
    *,
    anchors: list[dict[str, str]],
    anchor_csv_path: Path,
    artifact_dir: Path,
    input_manifest_path: Path,
    run_manifest_path: Path,
    tree_dir: Path,
    report_path: Path,
    csv_path: Path,
    allow_local_run: bool,
    model: str | None,
    base_url: str | None,
    pageindex_root: str,
    pageindex_python: str | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    tree_dir.mkdir(parents=True, exist_ok=True)
    if not anchors:
        blockers.append("No supplemental synthetic anchor rows available.")
    input_manifest = supplemental_pageindex_input_manifest(anchors, artifact_dir)
    write_json(input_manifest_path, input_manifest)
    input_manifest_sha256 = sha256_file(input_manifest_path)
    preflight_ready, preflight_blockers = local_pageindex_preflight(
        allow_local_run=allow_local_run,
        model=model,
        base_url=base_url,
    )
    live_pageindex_run = False
    local_pageindex_run = False
    runner_returncode: int | None = None
    runner_stdout = ""
    runner_stderr = ""
    run_manifest: dict[str, Any] | None = None

    if anchors and preflight_ready:
        if run_manifest_path.exists():
            run_manifest_path.unlink()
        command = [
            sys.executable,
            str(SCRIPT_DIR / "rag_pdf_pageindex_runner.py"),
            "--manifest",
            str(input_manifest_path),
            "--allow-local-run",
            "--model",
            str(model),
            "--base-url",
            str(base_url),
            "--pageindex-root",
            pageindex_root,
            "--timeout-seconds",
            str(timeout_seconds),
        ]
        if pageindex_python:
            command.extend(["--python", pageindex_python])
        completed = subprocess.run(command, cwd=str(SCRIPT_DIR.parent.parent), text=True, capture_output=True, check=False)
        runner_returncode = completed.returncode
        runner_stdout = completed.stdout[-4000:]
        runner_stderr = completed.stderr[-4000:]
        if run_manifest_path.exists():
            candidate_manifest = read_json(run_manifest_path)
            identity_blockers = pageindex_manifest_identity_blockers(
                candidate_manifest,
                input_manifest=input_manifest,
                input_manifest_path=input_manifest_path,
                input_manifest_sha256=input_manifest_sha256,
                runner_returncode=runner_returncode,
            )
            if identity_blockers:
                blockers.extend(identity_blockers)
            else:
                run_manifest = candidate_manifest
        else:
            blockers.append("PageIndex runner did not produce pageindex_run_manifest.json.")
    if run_manifest is None:
        run_manifest = fail_closed_run_manifest(
            input_manifest=input_manifest,
            input_manifest_path=input_manifest_path,
            input_manifest_sha256=input_manifest_sha256,
            artifact_dir=artifact_dir,
            tree_dir=tree_dir,
            allow_local_run=allow_local_run,
            model=model,
            base_url=base_url,
            preflight_blockers=preflight_blockers,
        )
    live_pageindex_run = bool(run_manifest.get("live_pageindex_run"))
    local_pageindex_run = bool(run_manifest.get("local_pageindex_run"))

    tree_by_file = load_tree_docs(run_manifest)
    rows = [analyze_anchor(row, tree_by_file, live_pageindex_run) for row in anchors]
    counts = build_counts(rows, run_manifest, live_pageindex_run, local_pageindex_run)
    status = "DIAGNOSTIC_COMPLETED"
    if blockers:
        status = "FAIL_CLOSED_INPUT_ERROR"
    elif not live_pageindex_run:
        status = "DIAGNOSTIC_COMPLETED_WITH_PAGEINDEX_UNAVAILABLE"
    elif counts["tree_build_failure_count"]:
        status = "DIAGNOSTIC_COMPLETED_WITH_TREE_BUILD_FAILURES"
    elif counts["oracle_exists_but_navigation_missed_count"]:
        status = "DIAGNOSTIC_COMPLETED_WITH_NAVIGATION_MISSES"
    report = {
        "schema_version": "pdf_supplemental_pageindex_diagnostic_report_v1",
        "run_id": str(input_manifest["run_id"]),
        "generated_at": utc_timestamp(),
        "status": status,
        **COMMON_GUARDRAILS,
        "live_pageindex_run": live_pageindex_run,
        "local_pageindex_run": local_pageindex_run,
        "external_cloud_llm_run": False,
        "pageindex_improvement_claimed": False,
        "pageindex_role": "pdf_page_section_navigator_candidate_only",
        "input_artifacts": [artifact_identity(anchor_csv_path), artifact_identity(input_manifest_path)],
        "output_artifacts": {
            "pageindex_trees": display_path(tree_dir),
            "pageindex_run_manifest": display_path(run_manifest_path),
            "json_report": display_path(report_path),
            "csv_report": display_path(csv_path),
        },
        "pageindex_runner": {
            "requested": bool(allow_local_run),
            "preflight_ready": preflight_ready,
            "preflight_blockers": preflight_blockers,
            "returncode": runner_returncode,
            "stdout_tail": runner_stdout,
            "stderr_tail": runner_stderr,
        },
        "counts": counts,
        "blockers": blockers,
        "warnings": warnings,
        "notes": [
            "Supplemental synthetic anchors are diagnostic_only and not Track C official gold.",
            "PageIndex is evaluated only as a page/section navigator candidate.",
            "bbox/table/value semantics success is not claimed.",
        ],
        "query_results": rows,
    }
    return {"input_manifest": input_manifest, "run_manifest": run_manifest, "report": report, "rows": rows}


def supplemental_pageindex_input_manifest(anchors: list[Mapping[str, str]], artifact_dir: Path) -> dict[str, Any]:
    run_id_value = artifact_dir.name.replace("pdf_supplemental_elec_lh_", "")
    by_file: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in anchors:
        by_file[str(row.get("relative_path") or "")].append(row)
    documents: list[dict[str, Any]] = []
    for relative_path, rows in sorted(by_file.items()):
        pdf_path = resolve_path(relative_path)
        documents.append({
            "expected_file": str(rows[0].get("file_name") or Path(relative_path).name),
            "expected_document_version_ids": [],
            "pdf_path_found": pdf_path.exists(),
            "pdf_path": display_path(pdf_path),
            "query_ids": [row["query_id"] for row in rows],
            "query_count": len(rows),
            "expected_pages": sorted({to_int(row.get("parser_derived_page_no")) for row in rows if to_int(row.get("parser_derived_page_no")) is not None}),
        })
    queries = [
        {
            "query_id": row.get("query_id"),
            "query": row.get("query"),
            "expected_file": row.get("file_name"),
            "expected_page_no": to_int(row.get("parser_derived_page_no")),
            "expected_bbox": bbox_to_list(row.get("parser_derived_bbox")),
            "label_status": "diagnostic_only",
            "synthetic_diagnostic": True,
            "promotion_evidence": False,
        }
        for row in anchors
    ]
    return {
        "schema_version": "pdf_supplemental_pageindex_input_manifest_v1",
        "run_id": run_id_value,
        "generated_at": utc_timestamp(),
        **COMMON_GUARDRAILS,
        "artifact_dir": display_path(artifact_dir),
        "documents": documents,
        "queries": queries,
        "counts": {"query_count": len(queries), "document_count": len(documents)},
    }


def fail_closed_run_manifest(
    *,
    input_manifest: Mapping[str, Any],
    input_manifest_path: Path,
    input_manifest_sha256: str,
    artifact_dir: Path,
    tree_dir: Path,
    allow_local_run: bool,
    model: str | None,
    base_url: str | None,
    preflight_blockers: list[str],
) -> dict[str, Any]:
    status = "SKIPPED_PAGEINDEX_RUN_NOT_REQUESTED" if not allow_local_run else "FAIL_CLOSED_PAGEINDEX_UNAVAILABLE"
    docs = []
    for doc in list(input_manifest.get("documents") or []):
        docs.append({
            **doc,
            "artifact_dir": None,
            "status": status,
            "tree_json_path": None,
            "tree_text_path": None,
            "page_count": None,
            "node_count": 0,
            "returncode": None,
            "blockers": preflight_blockers,
        })
    return {
        "schema_version": "pdf_supplemental_pageindex_run_manifest_v1",
        "run_id": str(input_manifest.get("run_id") or ""),
        "generated_at": utc_timestamp(),
        "status": status,
        **COMMON_GUARDRAILS,
        "live_pageindex_run": False,
        "local_pageindex_run": False,
        "local_open_source_run_requested": allow_local_run,
        "local_model": model,
        "local_base_url": base_url,
        "artifact_dir": display_path(artifact_dir),
        "input_manifest": display_path(input_manifest_path),
        "input_manifest_sha256": input_manifest_sha256,
        "tree_dir": display_path(tree_dir),
        "documents": docs,
        "counts": {
            "document_count": len(docs),
            "tree_generated_count": 0,
            "failed_or_skipped_count": len(docs),
        },
        "blockers": preflight_blockers,
        "warnings": [],
    }


def pageindex_manifest_identity_blockers(
    run_manifest: Mapping[str, Any],
    *,
    input_manifest: Mapping[str, Any],
    input_manifest_path: Path,
    input_manifest_sha256: str,
    runner_returncode: int | None,
) -> list[str]:
    blockers: list[str] = []
    expected_run_id = str(input_manifest.get("run_id") or "")
    if str(run_manifest.get("run_id") or "") != expected_run_id:
        blockers.append("PageIndex runner manifest run_id does not match supplemental input manifest.")
    expected_input_path = display_path(input_manifest_path)
    if str(run_manifest.get("input_manifest") or "") != expected_input_path:
        blockers.append("PageIndex runner manifest input_manifest path does not match supplemental input manifest.")
    actual_input_sha256 = str(run_manifest.get("input_manifest_sha256") or "")
    if actual_input_sha256 != input_manifest_sha256:
        blockers.append("PageIndex runner manifest input_manifest_sha256 does not match supplemental input manifest.")
    manifest_status = str(run_manifest.get("status") or "")
    explicit_failure_manifest = manifest_status.startswith("FAIL_CLOSED") or manifest_status.startswith("SKIPPED")
    if runner_returncode not in (0, None) and not explicit_failure_manifest:
        blockers.append(f"PageIndex runner returned non-zero ({runner_returncode}) without an explicit fail-closed manifest.")
    return blockers


def load_tree_docs(run_manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for doc in list(run_manifest.get("documents") or []):
        if not isinstance(doc, Mapping):
            continue
        expected_file = str(doc.get("expected_file") or "")
        tree_path_text = str(doc.get("tree_json_path") or "")
        if doc.get("status") != "TREE_GENERATED" or not tree_path_text:
            result[expected_file] = {"status": str(doc.get("status") or "TREE_UNAVAILABLE"), "nodes": [], "invalid_ranges": []}
            continue
        tree_path = resolve_path(tree_path_text)
        if not tree_path.exists():
            result[expected_file] = {"status": "TREE_JSON_PATH_MISSING", "nodes": [], "invalid_ranges": []}
            continue
        tree = read_json(tree_path)
        nodes, invalid = flatten_nodes(list(tree.get("structure") or []))
        result[expected_file] = {"status": "TREE_AVAILABLE", "nodes": nodes, "invalid_ranges": invalid}
    return result


def flatten_nodes(nodes: list[Any], depth: int = 0, parent_id: str | None = None, parent_range: list[int] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            continue
        node_id = str(node.get("node_id") or f"{parent_id or 'root'}-{index}")
        page_range = page_range_for_node(node)
        reasons: list[str] = []
        if page_range is None:
            reasons.append("MISSING_PAGE_RANGE")
        else:
            start, end = page_range
            if start < 1 or end < 1:
                reasons.append("NON_POSITIVE_PAGE_RANGE")
            if start > end:
                reasons.append("START_AFTER_END")
            if parent_range and parent_range[0] <= parent_range[1] and (start < parent_range[0] or end > parent_range[1]):
                reasons.append("CHILD_RANGE_OUTSIDE_PARENT")
        row = {
            "node_id": node_id,
            "parent_id": parent_id,
            "depth": depth,
            "title": str(node.get("title") or ""),
            "page_range": page_range,
            "invalid_reasons": reasons,
        }
        rows.append(row)
        if reasons:
            invalid.append(row)
        child_rows, child_invalid = flatten_nodes(list(node.get("nodes") or []), depth + 1, node_id, page_range)
        rows.extend(child_rows)
        invalid.extend(child_invalid)
    return rows, invalid


def page_range_for_node(node: Mapping[str, Any]) -> list[int] | None:
    start = to_int(node.get("start_index") or node.get("start_page") or node.get("start"))
    end = to_int(node.get("end_index") or node.get("end_page") or node.get("end"))
    if start is None or end is None:
        return None
    return [start, end]


def analyze_anchor(anchor: Mapping[str, str], tree_by_file: Mapping[str, Mapping[str, Any]], live_pageindex_run: bool) -> dict[str, Any]:
    expected_file = str(anchor.get("file_name") or "")
    expected_page = to_int(anchor.get("parser_derived_page_no"))
    tree_doc = tree_by_file.get(expected_file, {"status": "PAGEINDEX_RUN_UNAVAILABLE", "nodes": [], "invalid_ranges": []})
    nodes = list(tree_doc.get("nodes") or [])
    invalid = list(tree_doc.get("invalid_ranges") or [])
    tree_success = bool(live_pageindex_run and tree_doc.get("status") == "TREE_AVAILABLE")
    valid_nodes = [node for node in nodes if not node.get("invalid_reasons")]
    expected_any = any(range_contains(node.get("page_range"), expected_page) for node in nodes)
    expected_valid = any(range_contains(node.get("page_range"), expected_page) for node in valid_nodes)
    oracle_nodes = [node for node in valid_nodes if range_contains(node.get("page_range"), expected_page)]
    if not oracle_nodes:
        oracle_nodes = [node for node in nodes if range_contains(node.get("page_range"), expected_page)]
    oracle_nodes.sort(key=lambda node: (range_width(node.get("page_range")) or 10**9, -(to_int(node.get("depth")) or 0)))
    oracle = oracle_nodes[0] if oracle_nodes else {}
    selected = select_node(anchor, valid_nodes or nodes)
    selected_range = selected.get("page_range")
    selected_contains = range_contains(selected_range, expected_page)
    selected_extractable = bool(selected_range)
    query_navigation_success = bool(selected)
    overlap = selected_contains
    status = "PAGEINDEX_RUN_UNAVAILABLE"
    if tree_success and not expected_any:
        status = "TREE_MISSING_EXPECTED_PAGE"
    elif tree_success and selected_contains:
        status = "PAGE_SECTION_NAVIGATION_HIT"
    elif tree_success and oracle:
        status = "NAVIGATION_MISSED_EXISTING_ORACLE_NODE"
    elif tree_success:
        status = "PAGEINDEX_QUERY_NAVIGATION_FAILED"
    child_invalid_count = sum(1 for node in invalid if "CHILD_RANGE_OUTSIDE_PARENT" in list(node.get("invalid_reasons") or []))
    tree_integrity = "VALID" if not invalid else "INVALID_RANGE_PRESENT"
    return {
        "query_id": anchor.get("query_id"),
        "dataset_source": anchor.get("dataset_source"),
        "file_name": expected_file,
        "relative_path": anchor.get("relative_path"),
        "parser_derived_expected_page_no": expected_page,
        "tree_build_success": tree_success,
        "query_navigation_success": query_navigation_success,
        "selected_node_id": selected.get("node_id"),
        "selected_node_title": selected.get("title"),
        "selected_page_range": selected_range,
        "selected_page_width": range_width(selected_range),
        "parser_derived_expected_page_overlap": overlap,
        "expected_page_present_in_any_tree": expected_any,
        "expected_page_present_in_valid_tree": expected_valid,
        "oracle_node_id": oracle.get("node_id"),
        "oracle_node_title": oracle.get("title"),
        "oracle_node_page_range": oracle.get("page_range"),
        "selected_contains_expected_page": selected_contains,
        "oracle_exists_but_navigation_missed": bool(oracle and not selected_contains),
        "invalid_range_count": len(invalid),
        "invalid_child_outside_parent_count": child_invalid_count,
        "tree_integrity_status": tree_integrity,
        "bbox_contract_solved": "not_claimed",
        "table_semantics_solved": "not_claimed",
        "comparison_status": status,
    }


def select_node(anchor: Mapping[str, str], nodes: list[Mapping[str, Any]]) -> dict[str, Any]:
    query_tokens = tokens(" ".join([str(anchor.get("query") or ""), str(anchor.get("anchor_text") or "")]))
    scored = []
    for node in nodes:
        title_tokens = tokens(str(node.get("title") or ""))
        overlap = query_tokens & title_tokens
        if not overlap:
            continue
        scored.append((len(overlap), -(to_int(node.get("depth")) or 0), node))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return dict(scored[0][2]) if scored else {}


def tokens(text: str) -> set[str]:
    stop = {"pdf", "page", "확인", "부분", "문서", "찾아줘", "알려줘", "관련", "설명"}
    return {token.lower() for token in TOKEN_RE.findall(text or "") if len(token) >= 2} - stop


def range_contains(page_range: Any, page: int | None) -> bool:
    if not isinstance(page_range, list) or len(page_range) < 2 or page is None:
        return False
    start = to_int(page_range[0])
    end = to_int(page_range[1])
    return start is not None and end is not None and start <= end and start <= page <= end


def range_width(page_range: Any) -> int | None:
    if not isinstance(page_range, list) or len(page_range) < 2:
        return None
    start = to_int(page_range[0])
    end = to_int(page_range[1])
    if start is None or end is None or start > end:
        return None
    return end - start + 1


def build_counts(rows: list[Mapping[str, Any]], run_manifest: Mapping[str, Any], live_pageindex_run: bool, local_pageindex_run: bool) -> dict[str, Any]:
    invalid_range_generated_count = sum(int(row.get("invalid_range_count") or 0) for row in rows)
    child_invalid_count = sum(int(row.get("invalid_child_outside_parent_count") or 0) for row in rows)
    # The row sums intentionally count query exposure to invalid ranges. Unique
    # node-level counts remain visible in pageindex_run_manifest/tree artifacts.
    return {
        "supplemental_query_count": len(rows),
        "live_pageindex_run": live_pageindex_run,
        "local_pageindex_run": local_pageindex_run,
        "external_cloud_llm_run": False,
        "tree_build_success_count": sum(1 for row in rows if row.get("tree_build_success") is True),
        "tree_build_failure_count": sum(1 for row in rows if live_pageindex_run and row.get("tree_build_success") is not True),
        "query_navigation_success_count": sum(1 for row in rows if row.get("query_navigation_success") is True),
        "selected_page_range_extractable_count": sum(1 for row in rows if row.get("selected_page_range")),
        "parser_derived_expected_page_overlap_count": sum(1 for row in rows if row.get("parser_derived_expected_page_overlap") is True),
        "expected_page_present_in_any_tree_count": sum(1 for row in rows if row.get("expected_page_present_in_any_tree") is True),
        "expected_page_present_in_valid_tree_count": sum(1 for row in rows if row.get("expected_page_present_in_valid_tree") is True),
        "oracle_node_found_any_count": sum(1 for row in rows if row.get("oracle_node_id")),
        "oracle_node_found_valid_count": sum(1 for row in rows if row.get("oracle_node_id") and row.get("expected_page_present_in_valid_tree")),
        "selected_contains_expected_page_count": sum(1 for row in rows if row.get("selected_contains_expected_page") is True),
        "oracle_exists_but_navigation_missed_count": sum(1 for row in rows if row.get("oracle_exists_but_navigation_missed") is True),
        "invalid_range_generated_count": invalid_range_generated_count,
        "invalid_child_outside_parent_count": child_invalid_count,
        "pageindex_improvement_claimed": False,
        "bbox_contract_success_not_claimed": True,
        "table_semantics_success_not_claimed": True,
        "comparison_status_counts": sorted_counter(Counter(str(row.get("comparison_status") or "UNKNOWN") for row in rows)),
        "run_manifest_status": run_manifest.get("status"),
    }


def resolve_artifact_dir(value: str | None) -> Path:
    if value:
        return resolve_path(value)
    return latest_supplemental_artifact_dir()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", default=None)
    parser.add_argument("--anchor-csv", default=str(DEFAULT_ANCHOR_CSV))
    parser.add_argument("--report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV_REPORT))
    parser.add_argument("--allow-local-run", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--pageindex-root", default=str(Path(".tmp") / "PageIndex"))
    parser.add_argument("--python", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
