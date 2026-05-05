"""Apply C8.3 case decisions to a report-only reviewed-PDF overlay.

This is a report-only follow-up to C8.3. It reads the reviewed PDF manifest and
the C8.3 case-level review report, records the case decisions as overlay fields,
and leaves every CSV manifest untouched. It does not mutate eval/gold_queries_v0.csv,
overwrite eval/gold_queries_pdf_v1_reviewed.csv, write a candidate CSV, run retrieval,
tune, reindex, promote, or regenerate PDF candidate artifacts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from rag_pdf_policy_common import (  # noqa: E402
    EVIDENCE_ROLE,
    PDF_ARTIFACT_DIR,
    PDF_CANDIDATE_NAMESPACE,
    artifact_identity,
    bool_cell,
    clean,
    dedupe,
    print_json,
    read_csv_rows,
    read_json,
    report_ref,
    utc_run_id,
    utc_timestamp,
    write_json,
)


DEFAULT_C8_3_REPORT = Path("reports/rag_pdf_c8_case_level_review_report.json")
DEFAULT_REVIEWED_MANIFEST = Path("eval/gold_queries_pdf_v1_reviewed.csv")
DEFAULT_OUTPUT = Path("reports/rag_pdf_c8_case_decision_overlay.json")

EXPECTED_CASE_COUNT = 7
EXPECTED_DECISION_COUNTS = {
    "REQUIRE_EMBEDDING_SURFACE_REVIEW": 1,
    "REQUIRE_FILE_DISAMBIGUATION_POLICY": 1,
    "REWRITE_QUERY_SURFACE": 5,
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    c8_3_path = Path(args.c8_3_report)
    reviewed_manifest_path = Path(args.reviewed_manifest)

    c8_3_report = read_json(c8_3_path)
    reviewed_rows = read_csv_rows(reviewed_manifest_path)
    overlay = build_case_decision_overlay(
        c8_3_report=c8_3_report,
        reviewed_manifest_rows=reviewed_rows,
        c8_3_report_path=c8_3_path,
        reviewed_manifest_path=reviewed_manifest_path,
        output_path=Path(args.output),
    )
    write_json(Path(args.output), overlay)
    print_json(overlay)
    return 0 if overlay.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c8-3-report", default=str(DEFAULT_C8_3_REPORT))
    parser.add_argument("--reviewed-manifest", default=str(DEFAULT_REVIEWED_MANIFEST))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


def build_case_decision_overlay(
    *,
    c8_3_report: Mapping[str, Any],
    reviewed_manifest_rows: list[Mapping[str, Any]],
    c8_3_report_path: Path,
    reviewed_manifest_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = [
        "C8.4 creates a report-only case-decision overlay; source reviewed manifest remains unchanged.",
    ]
    validate_inputs(
        c8_3_report=c8_3_report,
        reviewed_manifest_rows=reviewed_manifest_rows,
        reviewed_manifest_path=reviewed_manifest_path,
        blockers=blockers,
    )
    manifest_by_id = by_query_id(reviewed_manifest_rows)
    overlay_rows = [
        decide_case(row, manifest_by_id.get(clean(row.get("query_id"))), blockers)
        for row in c8_3_report.get("rows") or []
        if isinstance(row, Mapping)
    ]
    action_counts = count(overlay_rows, "manifest_action")
    denominator = reviewed_manifest_denominator(reviewed_manifest_rows)
    expected_denominator = {
        "total_pdf_rows": 22,
        "positive_metric_eligible_count": 16,
        "table_deferred_count": 6,
        "excluded_count": 0,
    }
    if len(overlay_rows) != EXPECTED_CASE_COUNT:
        blockers.append(f"C8.4 must apply exactly {EXPECTED_CASE_COUNT} case decisions")
    if denominator != expected_denominator:
        blockers.append(f"reviewed manifest denominator must remain {expected_denominator}; got {denominator}")
    if any(row.get("overlay_positive_metric_eligible") is True for row in overlay_rows if row.get("case_review_pending")):
        blockers.append("case_review_pending overlay rows must be marked ineligible until manually resolved")

    status = "BLOCKED_WITH_REASON" if blockers else "PASS_WITH_WARNINGS"
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C8.4",
        "report_role": "pdf_c8_case_decision_overlay",
        "promotion_evidence": False,
        "evidence_role": EVIDENCE_ROLE,
        "pdf_candidate_namespace": PDF_CANDIDATE_NAMESPACE,
        "pdf_artifact_dir": PDF_ARTIFACT_DIR,
        "retrieval_tuning_executed": False,
        "retrieval_execution": "not_run_by_this_script",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "baseline_execution": "not_run_by_this_script",
        "gold_mutation_execution": "not_run_by_this_script",
        "gold_v0_mutated": False,
        "reviewed_manifest_mutated": False,
        "candidate_manifest_written": False,
        "immutable_baseline_changed": False,
        "xlsx_candidate_artifact_changed": False,
        "table_specific_retrieval_proven": False,
        "broad_tuning_recommended": False,
        "input_reports": {
            "c8_3_case_level_review": report_ref(c8_3_report, c8_3_report_path),
            "reviewed_manifest": artifact_identity(reviewed_manifest_path),
        },
        "outputs": {
            "overlay_report": str(output_path),
        },
        "case_count": len(overlay_rows),
        "reviewed_manifest_denominator": denominator,
        "source_decision_counts": count(overlay_rows, "case_decision"),
        "manifest_action_counts": action_counts,
        "query_surface_rewrite_overlay_count": action_counts.get("QUERY_SURFACE_REWRITE_OVERLAY", 0),
        "case_review_pending_count": action_counts.get("MARK_CASE_REVIEW_PENDING", 0),
        "query_surface_leakage_counts": count_leakage(overlay_rows),
        "rows": overlay_rows,
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "next_action": (
            "Use this overlay to decide manual label/query/page/file changes; create or rerun diagnostics separately only after acceptance."
            if not blockers
            else "Resolve C8.4 blockers before using the overlay."
        ),
        "notes": [
            "Query rewrites are overlay proposals only; no CSV is written.",
            "File disambiguation and page/embedding unresolved rows are marked case_review_pending in overlay only.",
            "No promotion, broad tuning, reindexing, parser expansion, baseline update, or gold v0 mutation is performed.",
        ],
    }


def decide_case(
    row: Mapping[str, Any],
    manifest_row: Mapping[str, Any] | None,
    blockers: list[str],
) -> dict[str, Any]:
    query_id = clean(row.get("query_id"))
    case_decision = clean(row.get("case_decision"))
    if manifest_row is None:
        blockers.append(f"{query_id} is missing from reviewed manifest")
        manifest_row = {}
    base = {
        "query_id": query_id,
        "bucket": first_nonempty(row.get("bucket"), manifest_row.get("bucket")),
        "case_decision": case_decision,
        "source_next_action": row.get("source_next_action"),
        "original_query": manifest_row.get("query") or row.get("query"),
        "proposed_query_surface": None,
        "expected_file_name": first_nonempty(row.get("expected_file_name"), manifest_row.get("expected_file_name")),
        "expected_page_no": first_nonempty(row.get("expected_page_no"), manifest_row.get("expected_page_no")),
        "expected_physical_page_index": first_nonempty(row.get("expected_physical_page_index"), manifest_row.get("expected_physical_page_index")),
        "expected_bbox": first_nonempty(row.get("expected_bbox"), manifest_row.get("expected_bbox")),
        "source_positive_metric_eligible": bool_cell(manifest_row.get("positive_metric_eligible")),
        "overlay_positive_metric_eligible": bool_cell(manifest_row.get("positive_metric_eligible")),
        "case_review_pending": False,
        "mutation_required": False,
        "rationale": row.get("why_not_broad_tuning"),
    }
    if case_decision == "REWRITE_QUERY_SURFACE":
        proposed_query = clean(row.get("proposed_query_surface"))
        audit = row.get("query_surface_audit") if isinstance(row.get("query_surface_audit"), Mapping) else {}
        if not proposed_query:
            blockers.append(f"{query_id} rewrite decision lacks proposed_query_surface")
        leakage = query_surface_leakage(
            proposed_query=proposed_query,
            manifest_row=manifest_row,
            c8_3_row=row,
        )
        if (
            audit.get("leaks_expected_file_name")
            or audit.get("contains_latin_letters")
            or audit.get("contains_pdf_extension")
            or not leakage["pass"]
        ):
            blockers.append(f"{query_id} proposed query surface failed C8.3 audit")
        return base | {
            "manifest_action": "QUERY_SURFACE_REWRITE_OVERLAY",
            "proposed_query_surface": proposed_query,
            "source_pdf_review_label": manifest_row.get("pdf_review_label"),
            "source_pdf_match_policy": manifest_row.get("pdf_match_policy"),
            "source_pdf_bbox_policy": manifest_row.get("pdf_bbox_policy"),
            "source_review_decision": manifest_row.get("review_decision"),
            "overlay_positive_metric_eligible": bool_cell(manifest_row.get("positive_metric_eligible")),
            "case_review_pending": False,
            "query_surface_leakage": leakage,
        }
    if case_decision == "REQUIRE_FILE_DISAMBIGUATION_POLICY":
        return pending_case(base, manifest_row, "file disambiguation policy is required before metric use")
    if case_decision == "REQUIRE_EMBEDDING_SURFACE_REVIEW":
        return pending_case(base, manifest_row, "expected page and embedding surface review is required before metric use")
    blockers.append(f"{query_id} has unsupported C8.4 case_decision {case_decision!r}")
    return pending_case(base, manifest_row, "unsupported case decision requires manual review")


def pending_case(base: Mapping[str, Any], manifest_row: Mapping[str, Any], note: str) -> dict[str, Any]:
    return dict(base) | {
        "manifest_action": "MARK_CASE_REVIEW_PENDING",
        "proposed_query_surface": None,
        "overlay_pdf_review_label": "case_review_pending",
        "overlay_pdf_match_policy": "CASE_REVIEW_REQUIRED",
        "overlay_pdf_bbox_policy": "REVIEW_REQUIRED",
        "overlay_review_decision": base.get("case_decision"),
        "overlay_positive_metric_eligible": False,
        "case_review_pending": True,
        "pending_reason": note,
        "source_pdf_review_label": manifest_row.get("pdf_review_label"),
        "source_review_decision": manifest_row.get("review_decision"),
    }


def validate_inputs(
    *,
    c8_3_report: Mapping[str, Any],
    reviewed_manifest_rows: list[Mapping[str, Any]],
    reviewed_manifest_path: Path,
    blockers: list[str],
) -> None:
    if c8_3_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C8.3 report must be PASS or PASS_WITH_WARNINGS; got {c8_3_report.get('status')}")
    if c8_3_report.get("promotion_evidence") is not False:
        blockers.append("C8.3 report must keep promotion_evidence=false")
    if c8_3_report.get("evidence_role") != EVIDENCE_ROLE:
        blockers.append("C8.3 report must keep evidence_role=diagnostic")
    if c8_3_report.get("retrieval_tuning_executed") is not False:
        blockers.append("C8.3 report must keep retrieval_tuning_executed=false")
    if c8_3_report.get("broad_tuning_recommended") is not False:
        blockers.append("C8.3 report must keep broad_tuning_recommended=false")
    if c8_3_report.get("blockers"):
        blockers.append("C8.3 blockers must be empty before C8.4")
    if c8_3_report.get("case_count") != EXPECTED_CASE_COUNT:
        blockers.append(f"C8.3 report must have case_count={EXPECTED_CASE_COUNT}")
    if c8_3_report.get("decision_counts") != EXPECTED_DECISION_COUNTS:
        blockers.append(f"C8.3 decision_counts must be {EXPECTED_DECISION_COUNTS}")
    if not reviewed_manifest_rows:
        blockers.append("reviewed PDF manifest must be readable and non-empty")
    current_manifest = artifact_identity(reviewed_manifest_path)
    c8_3_manifest = (
        c8_3_report.get("input_reports", {}).get("reviewed_manifest")
        if isinstance(c8_3_report.get("input_reports"), Mapping)
        else {}
    )
    if (
        isinstance(c8_3_manifest, Mapping)
        and c8_3_manifest.get("sha256")
        and c8_3_manifest.get("sha256") != current_manifest.get("sha256")
    ):
        blockers.append("current reviewed manifest sha256 must match the C8.3 input reviewed manifest sha256")


def by_query_id(rows: Iterable[Any]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        query_id = clean(row.get("query_id"))
        if query_id:
            out[query_id] = row
    return out


def count(rows: Iterable[Any], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        value = clean(row.get(key)) or "UNKNOWN"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def first_nonempty(*values: Any) -> Any:
    for value in values:
        if value is not None and clean(value):
            return value
    return None


def reviewed_manifest_denominator(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    rows_list = list(rows)
    table_rows = [row for row in rows_list if clean(row.get("pdf_review_label")) == "table_deferred"]
    excluded_rows = [row for row in rows_list if clean(row.get("pdf_review_label")) == "excluded"]
    return {
        "total_pdf_rows": len(rows_list),
        "positive_metric_eligible_count": sum(1 for row in rows_list if bool_cell(row.get("positive_metric_eligible"))),
        "table_deferred_count": len(table_rows),
        "excluded_count": len(excluded_rows),
    }


def query_surface_leakage(
    *,
    proposed_query: str,
    manifest_row: Mapping[str, Any],
    c8_3_row: Mapping[str, Any],
) -> dict[str, Any]:
    query = normalize_for_leak_scan(proposed_query)
    forbidden_terms = forbidden_surface_terms(manifest_row, c8_3_row)
    hits = [term for term in forbidden_terms if term and term in query]
    return {
        "pass": not hits,
        "matched_forbidden_terms": hits,
        "forbidden_term_count": len(forbidden_terms),
    }


def forbidden_surface_terms(manifest_row: Mapping[str, Any], c8_3_row: Mapping[str, Any]) -> list[str]:
    terms: set[str] = set()
    file_name = clean(first_nonempty(c8_3_row.get("expected_file_name"), manifest_row.get("expected_file_name")))
    docv = clean(first_nonempty(c8_3_row.get("expected_document_version_id"), manifest_row.get("expected_document_version_id")))
    source_sample_id = clean(manifest_row.get("source_sample_id"))
    for raw in [file_name, Path(file_name).stem if file_name else "", docv, source_sample_id, ".pdf"]:
        normalized = normalize_for_leak_scan(raw)
        if normalized:
            terms.add(normalized)
    if file_name:
        for token in Path(file_name).stem.replace("-", "_").split("_"):
            normalized = normalize_for_leak_scan(token)
            if len(normalized) >= 3:
                terms.add(normalized)
    if "recent_economic_trends" in file_name:
        terms.update({
            normalize_for_leak_scan("최근 경제 동향"),
            normalize_for_leak_scan("최근경제동향"),
            normalize_for_leak_scan("recent economic trends"),
        })
    return sorted(terms)


def normalize_for_leak_scan(value: Any) -> str:
    return "".join(ch for ch in clean(value).lower() if ch.isalnum() or "\uac00" <= ch <= "\ud7a3")


def count_leakage(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    total = 0
    failed = 0
    for row in rows:
        leakage = row.get("query_surface_leakage") if isinstance(row.get("query_surface_leakage"), Mapping) else {}
        if leakage:
            total += 1
            if leakage.get("pass") is not True:
                failed += 1
    return {
        "query_surface_checked_count": total,
        "query_surface_leak_count": failed,
    }


if __name__ == "__main__":
    raise SystemExit(main())
