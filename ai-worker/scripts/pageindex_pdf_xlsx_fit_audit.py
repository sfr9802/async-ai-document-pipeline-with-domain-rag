"""Audit whether PageIndex addresses XLSX/PDF anchor-to-evidence gaps.

The goal is not to run another retriever. This script reads existing XLSX/PDF
diagnostic artifacts and the locally cloned PageIndex source to classify where
PageIndex can help:

* PDF page/section navigation: possible partial fit.
* PDF bbox/table policy or exact block identity: not solved by PageIndex alone.
* XLSX row/cell/header context: not natively supported by the open-source
  PageIndex repo; requires a workbook-to-Markdown/tree adapter first.

All outputs are diagnostic-only and written under eval/reports/pageindex-ab.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent

DEFAULT_PAGEINDEX_ROOT = REPO_ROOT / ".tmp" / "PageIndex"
DEFAULT_XLSX_REPORT = (
    AI_WORKER_ROOT
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json"
)
DEFAULT_PDF_REPORT = (
    AI_WORKER_ROOT
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "rag_retrieval_eval_pdf_vector_diagnostic_report.json"
)
DEFAULT_PDF_BREAKDOWN = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_pdf_vector_quality_breakdown.json"
)
DEFAULT_KEYWORD_RISK = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_pdf_xlsx_keyword_echo_risk_review.csv"
)
DEFAULT_ANSWER_SHAPE = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_pdf_xlsx_answer_shape_local_llm_report.json"
)
DEFAULT_ANSWER_SHAPE_ROWS = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_pdf_xlsx_answer_shape_local_llm.csv"
)
DEFAULT_REPAIR_PLAN = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_pdf_xlsx_answer_prompt_repair_plan.json"
)
DEFAULT_OUTPUT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "pageindex-ab" / "pdf_xlsx_fit_audit"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pageindex = inspect_pageindex(Path(args.pageindex_root))
    xlsx_report = read_json(Path(args.xlsx_report))
    pdf_report = read_json(Path(args.pdf_report))
    pdf_breakdown = read_json(Path(args.pdf_breakdown))
    keyword_rows = read_csv_rows(Path(args.keyword_risk))
    answer_shape = read_json(Path(args.answer_shape))
    answer_rows = read_csv_rows(Path(args.answer_shape_rows))
    repair_plan = read_json(Path(args.repair_plan))

    xlsx_rows = classify_xlsx_rows(
        list(xlsx_report.get("query_results") or []),
        keyword_rows=keyword_rows,
        answer_rows=answer_rows,
    )
    pdf_rows = classify_pdf_rows(
        list(pdf_breakdown.get("query_breakdown") or []),
        keyword_rows=keyword_rows,
        answer_rows=answer_rows,
    )
    report = build_report(
        pageindex=pageindex,
        xlsx_report=xlsx_report,
        pdf_report=pdf_report,
        pdf_breakdown=pdf_breakdown,
        keyword_rows=keyword_rows,
        answer_shape=answer_shape,
        repair_plan=repair_plan,
        xlsx_rows=xlsx_rows,
        pdf_rows=pdf_rows,
        args=args,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "pageindex_pdf_xlsx_fit_audit_report.json"
    row_path = output_dir / "pageindex_pdf_xlsx_fit_audit_rows.csv"
    md_path = output_dir / "pageindex_pdf_xlsx_fit_audit_report.md"
    write_json(report_path, report)
    write_csv(row_path, [*xlsx_rows, *pdf_rows])
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps({
        "status": report["status"],
        "output_dir": repo_relative(output_dir),
        "xlsx_rows": len(xlsx_rows),
        "pdf_rows": len(pdf_rows),
        "xlsx_repo_alone_resolution": report["xlsx_assessment"]["repo_alone_resolution"],
        "pdf_repo_alone_resolution": report["pdf_assessment"]["repo_alone_resolution"],
        "report": repo_relative(report_path),
        "rows": repo_relative(row_path),
        "markdown": repo_relative(md_path),
    }, ensure_ascii=False, indent=2))
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pageindex-root", default=str(DEFAULT_PAGEINDEX_ROOT))
    parser.add_argument("--xlsx-report", default=str(DEFAULT_XLSX_REPORT))
    parser.add_argument("--pdf-report", default=str(DEFAULT_PDF_REPORT))
    parser.add_argument("--pdf-breakdown", default=str(DEFAULT_PDF_BREAKDOWN))
    parser.add_argument("--keyword-risk", default=str(DEFAULT_KEYWORD_RISK))
    parser.add_argument("--answer-shape", default=str(DEFAULT_ANSWER_SHAPE))
    parser.add_argument("--answer-shape-rows", default=str(DEFAULT_ANSWER_SHAPE_ROWS))
    parser.add_argument("--repair-plan", default=str(DEFAULT_REPAIR_PLAN))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args(argv)


def inspect_pageindex(root: Path) -> dict[str, Any]:
    run_pageindex = read_text(root / "run_pageindex.py")
    package_sources = "\n".join(read_text(path) for path in sorted((root / "pageindex").glob("*.py")))
    return {
        "root": repo_relative(root),
        "open_source_pdf_cli_supported": "--pdf_path" in run_pageindex,
        "open_source_markdown_cli_supported": "--md_path" in run_pageindex,
        "open_source_xlsx_native_supported": any(
            token in package_sources.lower()
            for token in ("openpyxl", "xlsx", "spreadsheet", "excel")
        ),
        "pdf_bbox_contract_supported": "bbox" in package_sources.lower(),
        "pdf_page_range_tree_supported": all(
            token in package_sources for token in ("start_index", "end_index", "physical_index")
        ),
        "local_pdf_parser_markers": sorted(
            token for token in ("PyPDF2", "pymupdf", "PyMuPDF") if token.lower() in package_sources.lower()
        ),
        "observed_cli_modes": [
            mode
            for mode, supported in {
                "pdf": "--pdf_path" in run_pageindex,
                "markdown": "--md_path" in run_pageindex,
            }.items()
            if supported
        ],
    }


def classify_xlsx_rows(
    rows: list[Mapping[str, Any]],
    *,
    keyword_rows: list[Mapping[str, str]],
    answer_rows: list[Mapping[str, str]],
) -> list[dict[str, Any]]:
    keyword_by_id = by_query_id(keyword_rows)
    answer_by_id = by_query_id(answer_rows)
    out: list[dict[str, Any]] = []
    for row in rows:
        query_id = clean(row.get("query_id"))
        hits = list(row.get("top_k_results") or [])
        expected_file = clean(row.get("expected_file_name"))
        expected_sheet = clean(row.get("expected_sheet_name"))
        expected_range = clean(row.get("expected_cell_range"))
        exact_hits = [hit for hit in hits if xlsx_hit_flag(hit, "xlsx_range_exact")]
        containing_hits = [
            hit for hit in hits
            if xlsx_hit_flag(hit, "xlsx_range_contains") and not xlsx_hit_flag(hit, "xlsx_range_exact")
        ]
        overlap_hits = [
            hit for hit in hits
            if xlsx_hit_flag(hit, "xlsx_range_overlap") and not xlsx_hit_flag(hit, "xlsx_range_exact")
        ]
        sheet_summary_anchors = [
            hit for hit in hits
            if clean(hit.get("chunk_type")) == "sheet_summary"
            and xlsx_same_file_sheet(hit, expected_file=expected_file, expected_sheet=expected_sheet)
        ]
        keyword = keyword_by_id.get(query_id, {})
        answer = answer_by_id.get(query_id, {})
        context_missing = clean(answer.get("table_or_cell_context_missing")).lower() == "true"
        prompt_or_serializer_fit = (
            context_missing
            or clean(keyword.get("expected_answer_shape")) in {
                "TABLE_COLUMN_OR_RANGE_WITH_CONTEXT",
                "TABLE_ROW_VALUE",
            }
        )
        if prompt_or_serializer_fit:
            fit = "requires_xlsx_markdown_adapter"
            reason = (
                "The open-source PageIndex repo has no native XLSX parser; this row needs "
                "sheet/table/header/cell-range serialization before PageIndex-style reasoning can help."
            )
        elif not exact_hits:
            fit = "not_solved_without_retrieval_or_range_contract_change"
            reason = "No exact expected range hit is visible in top-k."
        else:
            fit = "not_needed_for_retrieval_currently_matched"
            reason = "Current XLSX diagnostic already matched the expected location; answer shaping remains separate."
        out.append({
            "track": "XLSX",
            "query_id": query_id,
            "bucket": clean(row.get("bucket")),
            "query": clean(row.get("query")),
            "expected_location": f"{expected_file} > {expected_sheet} > {expected_range}",
            "current_hit_rank": row.get("hit_rank"),
            "current_location_rank": row.get("location_rank"),
            "current_failure_reason": clean(row.get("failure_reason")),
            "expected_answer_shape": clean(keyword.get("expected_answer_shape")),
            "keyword_echo_risk": clean(keyword.get("keyword_echo_risk")),
            "answer_eval_allowed": clean(keyword.get("answer_eval_allowed")),
            "context_gap_observed": context_missing,
            "pageindex_fit": fit,
            "fit_reason": reason,
            "top1_chunk_type": clean(hits[0].get("chunk_type")) if hits else "",
            "top1_location": citation_or_location(hits[0]) if hits else "",
            "exact_range_hit_count": len(exact_hits),
            "contains_non_exact_hit_count": len(containing_hits),
            "overlap_non_exact_hit_count": len(overlap_hits),
            "sheet_summary_anchor_count": len(sheet_summary_anchors),
        })
    return out


def classify_pdf_rows(
    rows: list[Mapping[str, Any]],
    *,
    keyword_rows: list[Mapping[str, str]],
    answer_rows: list[Mapping[str, str]],
) -> list[dict[str, Any]]:
    keyword_by_id = by_query_id(keyword_rows)
    answer_by_id = by_query_id(answer_rows)
    out: list[dict[str, Any]] = []
    for row in rows:
        query_id = clean(row.get("query_id"))
        expected = row.get("expected") if isinstance(row.get("expected"), Mapping) else {}
        evidence = row.get("evidence") if isinstance(row.get("evidence"), Mapping) else {}
        keyword = keyword_by_id.get(query_id, {})
        answer = answer_by_id.get(query_id, {})
        shape = clean(keyword.get("expected_answer_shape"))
        failure_type = clean(row.get("failure_type"))
        primary = clean(row.get("primary_group"))
        page_hit_count = int(evidence.get("expected_page_hit_count") or 0)
        bbox_hit_count = int(evidence.get("bbox_overlap_hit_count") or 0)
        if shape in {"LOCATION_PLUS_CONTENT", "PDF_SECTION_WITH_SUMMARY"} and primary in {"matched", "ranking"}:
            fit = "partial_pdf_tree_candidate"
            reason = (
                "PageIndex page/section tree may help select compact page ranges or section summaries, "
                "but it still needs this repo's citation metadata for exact evidence."
            )
        elif shape == "PDF_TABLE_VALUE_WITH_CONTEXT":
            fit = "not_solved_for_table_semantics_by_repo_alone"
            reason = "Open-source PageIndex exposes page text/ranges, not table cell/row semantics or bbox policy."
        elif "BBOX" in failure_type or bbox_hit_count == 0 and page_hit_count:
            fit = "not_solved_for_bbox_policy_by_repo_alone"
            reason = "The blocker is bbox/page-vs-paragraph evidence policy; PageIndex tree does not carry bbox identity."
        elif shape == "NOT_ANSWERABLE_OR_POLICY_PENDING" or clean(answer.get("policy_not_answerable_or_pending")).lower() == "true":
            fit = "blocked_by_gold_or_answerability_policy"
            reason = "PDF C7/user policy is pending, so PageIndex should not be treated as solving answerability."
        else:
            fit = "limited_pdf_navigation_only"
            reason = "Potentially useful for file/page navigation, but not enough to prove answerable evidence."
        out.append({
            "track": "PDF",
            "query_id": query_id,
            "bucket": clean(row.get("bucket")),
            "query": clean(row.get("query")),
            "expected_location": (
                f"{clean(expected.get('file_name'))} > p.{clean(expected.get('page_no'))} "
                f"> bbox {clean(expected.get('bbox'))}"
            ),
            "current_hit_rank": row.get("hit_rank"),
            "current_location_rank": row.get("location_rank"),
            "current_failure_reason": clean(row.get("failure_reason")),
            "expected_answer_shape": shape,
            "keyword_echo_risk": clean(keyword.get("keyword_echo_risk")),
            "answer_eval_allowed": clean(keyword.get("answer_eval_allowed")),
            "context_gap_observed": clean(answer.get("pdf_section_summary_missing")).lower() == "true",
            "pageindex_fit": fit,
            "fit_reason": reason,
            "top1_chunk_type": first_top_hit_value(row, "chunk_type"),
            "top1_location": first_top_hit_value(row, "citation_text"),
            "exact_range_hit_count": "",
            "contains_non_exact_hit_count": "",
            "overlap_non_exact_hit_count": "",
            "sheet_summary_anchor_count": "",
            "expected_page_hit_count": page_hit_count,
            "bbox_overlap_hit_count": bbox_hit_count,
        })
    return out


def build_report(
    *,
    pageindex: Mapping[str, Any],
    xlsx_report: Mapping[str, Any],
    pdf_report: Mapping[str, Any],
    pdf_breakdown: Mapping[str, Any],
    keyword_rows: list[Mapping[str, str]],
    answer_shape: Mapping[str, Any],
    repair_plan: Mapping[str, Any],
    xlsx_rows: list[Mapping[str, Any]],
    pdf_rows: list[Mapping[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    xlsx_fit_counts = Counter(row["pageindex_fit"] for row in xlsx_rows)
    pdf_fit_counts = Counter(row["pageindex_fit"] for row in pdf_rows)
    keyword_counts = {
        track: dict(Counter(row.get("keyword_echo_risk") for row in keyword_rows if row.get("track") == track))
        for track in ("XLSX", "PDF")
    }
    answer_shape_counts = {
        track: dict(Counter(row.get("expected_answer_shape") for row in keyword_rows if row.get("track") == track))
        for track in ("XLSX", "PDF")
    }
    return {
        "schema_version": "pageindex_pdf_xlsx_fit_audit_v1",
        "run_id": utc_run_id(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "COMPLETED_DIAGNOSTIC_ONLY",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "live_pageindex_run": False,
        "llm_call_run": False,
        "db_mutation_run": False,
        "indexing_run": False,
        "pageindex_repo_capabilities": dict(pageindex),
        "source_inputs": {
            "pageindex_root": repo_relative(Path(args.pageindex_root)),
            "xlsx_report": repo_relative(Path(args.xlsx_report)),
            "pdf_report": repo_relative(Path(args.pdf_report)),
            "pdf_breakdown": repo_relative(Path(args.pdf_breakdown)),
            "keyword_risk": repo_relative(Path(args.keyword_risk)),
            "answer_shape": repo_relative(Path(args.answer_shape)),
            "answer_shape_rows": repo_relative(Path(args.answer_shape_rows)),
            "repair_plan": repo_relative(Path(args.repair_plan)),
        },
        "xlsx_assessment": {
            "query_count": len(xlsx_rows),
            "current_retrieval_status": xlsx_report.get("status"),
            "current_matched_count": sum(1 for row in xlsx_rows if not row.get("current_failure_reason")),
            "answer_shape_counts": answer_shape_counts["XLSX"],
            "keyword_echo_risk_counts": keyword_counts["XLSX"],
            "context_gap_rows": sum(1 for row in xlsx_rows if row.get("context_gap_observed")),
            "fit_counts": dict(sorted(xlsx_fit_counts.items())),
            "repo_alone_resolution": "NO",
            "reason": (
                "The open-source PageIndex repo supports PDF and Markdown CLI modes, but no native XLSX parser. "
                "XLSX needs a workbook-to-Markdown adapter that preserves sheet, range, headers, row labels, "
                "formatted values, and hidden/formula policy before PageIndex can be fairly tested."
            ),
        },
        "pdf_assessment": {
            "query_count": len(pdf_rows),
            "current_retrieval_status": pdf_report.get("status"),
            "breakdown_status": pdf_breakdown.get("status"),
            "answer_shape_counts": answer_shape_counts["PDF"],
            "keyword_echo_risk_counts": keyword_counts["PDF"],
            "fit_counts": dict(sorted(pdf_fit_counts.items())),
            "repo_alone_resolution": "PARTIAL_ONLY",
            "reason": (
                "PageIndex can help with page/section range navigation, but the current PDF blockers are mostly "
                "C7 policy, bbox overlap, page-vs-paragraph chunk semantics, and table-value context. The local "
                "repo does not preserve this repo's bbox/citation contract by itself."
            ),
        },
        "cross_track_answer_shape_evidence": {
            "answer_shape_report_status": answer_shape.get("status"),
            "answer_shape_metrics": answer_shape.get("metrics"),
            "repair_plan_counts": repair_plan.get("counts"),
        },
        "next_experiment": {
            "xlsx": (
                "Build a workbook-to-Markdown PageIndex scaffold from existing SearchUnit/XLSX metadata, with "
                "one node per sheet/table/range and explicit headers/row labels/cell ranges. Then run anchor "
                "expansion against that generated Markdown tree."
            ),
            "pdf": (
                "Use PageIndex only as a page/section navigator first. Compare selected PageIndex page ranges "
                "against existing PDF C5/C6 expected page/bbox metadata, without claiming bbox-level success."
            ),
        },
    }


def xlsx_hit_flag(hit: Mapping[str, Any], key: str) -> bool:
    breakdown = hit.get("match_breakdown")
    return bool(isinstance(breakdown, Mapping) and breakdown.get(key))


def xlsx_same_file_sheet(hit: Mapping[str, Any], *, expected_file: str, expected_sheet: str) -> bool:
    location = hit.get("location_json") if isinstance(hit.get("location_json"), Mapping) else {}
    return clean(hit.get("source_file_name")) == expected_file and clean(location.get("sheet_name")) == expected_sheet


def by_query_id(rows: Iterable[Mapping[str, str]]) -> dict[str, Mapping[str, str]]:
    return {clean(row.get("query_id")): row for row in rows if clean(row.get("query_id"))}


def citation_or_location(hit: Mapping[str, Any]) -> str:
    if hit.get("citation_text"):
        return clean(hit.get("citation_text"))
    location = hit.get("location_json")
    return json.dumps(location, ensure_ascii=False, sort_keys=True) if isinstance(location, Mapping) else ""


def first_top_hit_value(row: Mapping[str, Any], key: str) -> str:
    hits = row.get("top_hits")
    if not isinstance(hits, list) or not hits:
        hits = row.get("supporting_hits")
    if isinstance(hits, list) and hits:
        return clean(hits[0].get(key))
    return ""


def render_markdown(report: Mapping[str, Any]) -> str:
    xlsx = report["xlsx_assessment"]
    pdf = report["pdf_assessment"]
    return "\n".join([
        "# PageIndex PDF/XLSX Fit Audit",
        "",
        f"- status: `{report['status']}`",
        f"- live_pageindex_run: `{report['live_pageindex_run']}`",
        f"- promotion_evidence: `{report['promotion_evidence']}`",
        "",
        "## PageIndex Repo Capability",
        "",
        f"- PDF CLI: `{report['pageindex_repo_capabilities']['open_source_pdf_cli_supported']}`",
        f"- Markdown CLI: `{report['pageindex_repo_capabilities']['open_source_markdown_cli_supported']}`",
        f"- Native XLSX support observed: `{report['pageindex_repo_capabilities']['open_source_xlsx_native_supported']}`",
        f"- PDF bbox contract observed: `{report['pageindex_repo_capabilities']['pdf_bbox_contract_supported']}`",
        "",
        "## XLSX",
        "",
        f"- repo_alone_resolution: **{xlsx['repo_alone_resolution']}**",
        f"- query_count: **{xlsx['query_count']}**",
        f"- current_matched_count: **{xlsx['current_matched_count']}**",
        f"- context_gap_rows: **{xlsx['context_gap_rows']}**",
        f"- fit_counts: `{json.dumps(xlsx['fit_counts'], ensure_ascii=False)}`",
        "",
        "## PDF",
        "",
        f"- repo_alone_resolution: **{pdf['repo_alone_resolution']}**",
        f"- query_count: **{pdf['query_count']}**",
        f"- fit_counts: `{json.dumps(pdf['fit_counts'], ensure_ascii=False)}`",
        "",
        "## Next Experiment",
        "",
        f"- XLSX: {report['next_experiment']['xlsx']}",
        f"- PDF: {report['next_experiment']['pdf']}",
        "",
    ])


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def repo_relative(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
