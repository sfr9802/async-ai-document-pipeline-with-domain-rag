"""Apply C7.1 explicit policy decisions to Track C PDF relabel candidates.

This script is diagnostic-only. It reads the C7 gold policy review report,
assigns a final policy decision to every relabel candidate, and writes a
separate reviewed PDF manifest. It does not mutate eval/gold_queries_v0.csv,
run retrieval, run indexing, promote, update baselines, or regenerate PDF
candidate artifacts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from rag_pdf_policy_common import (  # noqa: E402
    DECISIONS,
    EVIDENCE_ROLE,
    PDF_ARTIFACT_DIR,
    PDF_CANDIDATE_NAMESPACE,
    REVIEWED_MANIFEST_COLUMNS,
    artifact_identity,
    bool_cell,
    clean,
    counter_dict,
    dedupe,
    parse_bool,
    print_json,
    read_csv_rows,
    read_json,
    report_ref,
    utc_run_id,
    utc_timestamp,
    write_csv_rows,
    write_json,
)


DEFAULT_C7_REPORT = Path("reports/rag_pdf_gold_policy_review.json")
DEFAULT_C6_BREAKDOWN = Path("reports/rag_pdf_vector_quality_breakdown.json")
DEFAULT_GOLD = Path("eval/gold_queries_v0.csv")
DEFAULT_OUTPUT = Path("reports/rag_pdf_gold_policy_decision_overlay.json")
DEFAULT_REVIEWED_MANIFEST = Path("eval/gold_queries_pdf_v1_reviewed.csv")
DEFAULT_MANIFEST_REPORT = Path("reports/rag_pdf_v1_reviewed_manifest_report.json")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    promotion_evidence = parse_bool(args.promotion_evidence)
    evidence_role = clean(args.evidence_role) or EVIDENCE_ROLE
    c7_path = Path(args.c7_report)
    c6_path = Path(args.c6_breakdown)
    gold_path = Path(args.gold)
    overlay = build_overlay_report(
        c7_report=read_json(c7_path),
        c6_breakdown=read_json(c6_path),
        c7_report_path=c7_path,
        c6_breakdown_path=c6_path,
        gold_path=gold_path,
        promotion_evidence=promotion_evidence,
        evidence_role=evidence_role,
        pdf_candidate_namespace=args.pdf_candidate_namespace,
        pdf_artifact_dir=args.pdf_artifact_dir,
    )
    reviewed_rows, manifest_report = build_reviewed_manifest(
        gold_rows=read_csv_rows(gold_path),
        overlay_report=overlay,
        gold_path=gold_path,
        reviewed_manifest_path=Path(args.reviewed_manifest),
        manifest_report_path=Path(args.manifest_report),
        promotion_evidence=promotion_evidence,
        evidence_role=evidence_role,
        pdf_candidate_namespace=args.pdf_candidate_namespace,
        pdf_artifact_dir=args.pdf_artifact_dir,
    )
    write_json(Path(args.output), overlay)
    write_csv_rows(Path(args.reviewed_manifest), reviewed_rows, fieldnames=REVIEWED_MANIFEST_COLUMNS)
    write_json(Path(args.manifest_report), manifest_report)
    print_json(overlay)
    return 0 if overlay.get("status") in {"PASS", "PASS_WITH_WARNINGS"} and manifest_report.get("status") == "PASS" else 2


def build_overlay_report(
    *,
    c7_report: Mapping[str, Any],
    c6_breakdown: Mapping[str, Any],
    c7_report_path: Path,
    c6_breakdown_path: Path,
    gold_path: Path = DEFAULT_GOLD,
    promotion_evidence: bool = False,
    evidence_role: str = EVIDENCE_ROLE,
    pdf_candidate_namespace: str = PDF_CANDIDATE_NAMESPACE,
    pdf_artifact_dir: str = PDF_ARTIFACT_DIR,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    validate_inputs(
        c7_report=c7_report,
        c6_breakdown=c6_breakdown,
        promotion_evidence=promotion_evidence,
        evidence_role=evidence_role,
        blockers=blockers,
    )

    relabel_rows = list(c7_report.get("relabel_candidate_rows") or [])
    overlay_rows = [decide_row(row, blockers) for row in relabel_rows]
    unresolved = [row for row in overlay_rows if not row.get("final_decision")]
    unknown_decisions = [
        row for row in overlay_rows if row.get("final_decision") and row.get("final_decision") not in DECISIONS
    ]
    table_rows = [
        row for row in overlay_rows
        if row.get("c7_decision_category") == "RELABEL_TABLE_PAGE_BINDING"
    ]
    table_denominator_rows = [
        row for row in table_rows
        if row.get("positive_metric_eligible") is True
    ]
    c7_count = int(c7_report.get("relabel_candidate_count") or 0)
    if c7_count != len(overlay_rows):
        blockers.append(
            f"C7 relabel_candidate_count {c7_count} must match overlay row count {len(overlay_rows)}"
        )
    if unresolved:
        blockers.append("every overlay row must have final_decision")
    if unknown_decisions:
        blockers.append("unknown final_decision enum found")
    if table_denominator_rows:
        blockers.append("table relabel rows must not enter reviewed positive denominator")
    if table_rows:
        warnings.append(
            f"table_pending_count={len(table_rows)}; table-specific retrieval is not proven"
        )

    status = "FAIL" if blockers else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C7.1",
        "report_role": "pdf_gold_policy_decision_overlay",
        "promotion_evidence": promotion_evidence,
        "evidence_role": evidence_role,
        "pdf_candidate_namespace": pdf_candidate_namespace,
        "pdf_artifact_dir": pdf_artifact_dir,
        "retrieval_execution": "not_run_by_this_script",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "baseline_execution": "not_run_by_this_script",
        "gold_mutation_execution": "not_run_by_this_script",
        "immutable_baseline_changed": False,
        "xlsx_candidate_artifact_changed": False,
        "gold_v0_mutated": False,
        "input_reports": {
            "c7_gold_policy_review": report_ref(c7_report, c7_report_path),
            "c6_vector_quality_breakdown": report_ref(c6_breakdown, c6_breakdown_path),
            "gold_v0": artifact_identity(gold_path),
        },
        "relabel_candidate_count": c7_count,
        "resolved_candidate_count": len([row for row in overlay_rows if row.get("final_decision")]),
        "unresolved_candidate_count": len(unresolved),
        "decision_counts": counter_dict(overlay_rows, "final_decision"),
        "table_specific_retrieval_proven": False,
        "reviewed_positive_denominator_excludes_table_deferred": not table_denominator_rows,
        "table_deferred_count": len(table_rows),
        "policy_resolved_count": len(overlay_rows),
        "allowed_decisions": sorted(DECISIONS),
        "rows": overlay_rows,
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "next_action": (
            "Use eval/gold_queries_pdf_v1_reviewed.csv for C6.1 and reviewed C5.1 diagnostics; do not run promotion."
            if not blockers
            else "Resolve C7.1 blockers before using reviewed PDF policy evidence."
        ),
        "notes": [
            "Table relabel rows are preserved as table_pending and excluded from reviewed positive metrics.",
            "Page-with-optional-bbox and same-page paragraph policy rows are accepted only as diagnostic policy decisions.",
            "This overlay does not prove table-specific retrieval.",
        ],
    }


def decide_row(row: Mapping[str, Any], blockers: list[str]) -> dict[str, Any]:
    category = clean(row.get("decision_category"))
    query_id = clean(row.get("query_id"))
    base = {
        "query_id": query_id,
        "bucket": row.get("bucket"),
        "c6_failure_type": row.get("c6_failure_type"),
        "c5_failure_reason": row.get("c5_failure_reason"),
        "c7_decision_category": category,
        "expected": row.get("expected") or {},
        "supporting_hit_summary": row.get("supporting_hit_summary") or [],
        "table_specific_retrieval_proven": False,
    }
    if category == "RELABEL_TABLE_PAGE_BINDING":
        return base | {
            "final_decision": "DEFER_TO_TABLE_EXTRACTION",
            "pdf_review_label": "table_deferred",
            "pdf_match_policy": "TABLE_EXTRACTION_REQUIRED",
            "pdf_table_policy": "DEFER_TO_TABLE_EXTRACTION",
            "pdf_bbox_policy": "NOT_APPLICABLE",
            "positive_metric_eligible": False,
            "denominator_bucket": "table_pending",
            "rationale": (
                "Current PDF table gold rows have no table-like SearchUnits; "
                "table-specific retrieval remains unproven."
            ),
            "next_action": "Keep as table_pending until table extraction creates table-like SearchUnits.",
        }
    if category == "RELABEL_BBOX_OR_PAGE_FALLBACK":
        if not has_page_level_support(row):
            blockers.append(f"{query_id} lacks correct-page page-level support for PAGE_WITH_OPTIONAL_BBOX")
        return base | {
            "final_decision": "ACCEPT_PAGE_WITH_OPTIONAL_BBOX",
            "pdf_review_label": "positive_reviewed",
            "pdf_match_policy": "PAGE_WITH_OPTIONAL_BBOX",
            "pdf_table_policy": "NOT_TABLE_QUERY",
            "pdf_bbox_policy": "OPTIONAL_FOR_PAGE_LEVEL",
            "positive_metric_eligible": True,
            "denominator_bucket": "reviewed_positive",
            "rationale": (
                "Correct-page supporting hit is page-level; bbox absence is allowed "
                "only for this reviewed page-level policy."
            ),
            "next_action": "Count page-level success separately from exact bbox success.",
        }
    if category == "RELABEL_CHUNK_TYPE_POLICY":
        if not has_same_page_paragraph_support(row):
            blockers.append(f"{query_id} lacks same-page paragraph support for chunk-type policy relabel")
        return base | {
            "final_decision": "ACCEPT_CHUNK_TYPE_POLICY_RELABEL",
            "pdf_review_label": "positive_reviewed",
            "pdf_match_policy": "PAGE_OR_PARAGRAPH_SAME_PAGE",
            "pdf_table_policy": "NOT_TABLE_QUERY",
            "pdf_bbox_policy": "NOT_APPLICABLE",
            "positive_metric_eligible": True,
            "denominator_bucket": "reviewed_positive",
            "rationale": (
                "Same-page paragraph evidence exists; the conflict is expected "
                "page/chunk policy rather than a retrieval miss."
            ),
            "next_action": "Count same-page paragraph evidence separately from exact bbox success.",
        }
    blockers.append(f"{query_id} has unsupported C7 decision_category {category!r}")
    return base | {
        "final_decision": "KEEP_AS_FAILURE",
        "pdf_review_label": "excluded",
        "pdf_match_policy": "EXACT_PAGE_AND_BBOX",
        "pdf_table_policy": "NOT_TABLE_QUERY",
        "pdf_bbox_policy": "REQUIRED",
        "positive_metric_eligible": False,
        "denominator_bucket": "policy_unresolved",
        "rationale": "Unsupported C7 category could not be policy-resolved.",
        "next_action": "Review the gold binding before metric use.",
    }


def has_page_level_support(row: Mapping[str, Any]) -> bool:
    for hit in row.get("supporting_hit_summary") or []:
        if not isinstance(hit, Mapping):
            continue
        if (
            hit.get("file_match") is True
            and hit.get("document_version_match") is True
            and hit.get("pdf_page_match") is True
            and clean(hit.get("chunk_type")).lower() == "page"
            and hit.get("bbox_present") is False
        ):
            return True
    return False


def has_same_page_paragraph_support(row: Mapping[str, Any]) -> bool:
    for hit in row.get("supporting_hit_summary") or []:
        if not isinstance(hit, Mapping):
            continue
        if (
            hit.get("file_match") is True
            and hit.get("document_version_match") is True
            and hit.get("pdf_page_match") is True
            and hit.get("location_match") is True
            and clean(hit.get("chunk_type")).lower() == "paragraph"
        ):
            return True
    return False


def validate_inputs(
    *,
    c7_report: Mapping[str, Any],
    c6_breakdown: Mapping[str, Any],
    promotion_evidence: bool,
    evidence_role: str,
    blockers: list[str],
) -> None:
    if c7_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C7 report must be PASS or PASS_WITH_WARNINGS; got {c7_report.get('status')}")
    if c7_report.get("promotion_evidence") is not False:
        blockers.append("C7 report must keep promotion_evidence=false")
    if c7_report.get("evidence_role") != EVIDENCE_ROLE:
        blockers.append("C7 report must keep evidence_role=diagnostic")
    if c6_breakdown.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C6 breakdown must be PASS or PASS_WITH_WARNINGS; got {c6_breakdown.get('status')}")
    if c6_breakdown.get("promotion_evidence") is not False:
        blockers.append("C6 breakdown must keep promotion_evidence=false")
    if c6_breakdown.get("evidence_role") != EVIDENCE_ROLE:
        blockers.append("C6 breakdown must keep evidence_role=diagnostic")
    if int(c6_breakdown.get("unknown_failure_count") or 0) != 0:
        blockers.append("C6 unknown_failure_count must be 0 before C7.1")
    if promotion_evidence is not False:
        blockers.append("C7.1 must keep promotion_evidence=false")
    if evidence_role != EVIDENCE_ROLE:
        blockers.append("C7.1 must keep evidence_role=diagnostic")


def build_reviewed_manifest(
    *,
    gold_rows: list[dict[str, str]],
    overlay_report: Mapping[str, Any],
    gold_path: Path,
    reviewed_manifest_path: Path,
    manifest_report_path: Path,
    promotion_evidence: bool = False,
    evidence_role: str = EVIDENCE_ROLE,
    pdf_candidate_namespace: str = PDF_CANDIDATE_NAMESPACE,
    pdf_artifact_dir: str = PDF_ARTIFACT_DIR,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    blockers: list[str] = []
    if promotion_evidence is not False:
        blockers.append("reviewed manifest must keep promotion_evidence=false")
    if evidence_role != EVIDENCE_ROLE:
        blockers.append("reviewed manifest must keep evidence_role=diagnostic")
    overlay_by_id = {
        clean(row.get("query_id")): row
        for row in overlay_report.get("rows") or []
        if isinstance(row, Mapping)
    }
    pdf_rows = [
        row for row in gold_rows
        if clean(row.get("expected_location_type")).lower() == "pdf"
    ]
    reviewed_rows: list[dict[str, Any]] = []
    for gold in pdf_rows:
        reviewed_rows.append(reviewed_row(gold, overlay_by_id.get(clean(gold.get("query_id")))))

    table_deferred = [row for row in reviewed_rows if row["pdf_review_label"] == "table_deferred"]
    eligible = [row for row in reviewed_rows if bool_cell(row["positive_metric_eligible"])]
    if any(bool_cell(row["positive_metric_eligible"]) for row in table_deferred):
        blockers.append("table_deferred rows must be excluded from the positive denominator")
    if int(overlay_report.get("unresolved_candidate_count") or 0) != 0:
        blockers.append("policy overlay must have unresolved_candidate_count=0 before manifest use")
    status = "PASS" if not blockers else "FAIL"
    report = {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C7.1",
        "report_role": "pdf_v1_reviewed_manifest",
        "promotion_evidence": promotion_evidence,
        "evidence_role": evidence_role,
        "pdf_candidate_namespace": pdf_candidate_namespace,
        "pdf_artifact_dir": pdf_artifact_dir,
        "source_gold": artifact_identity(gold_path),
        "output_manifest": str(reviewed_manifest_path),
        "output_report": str(manifest_report_path),
        "gold_v0_mutated": False,
        "total_pdf_rows": len(pdf_rows),
        "table_deferred_count": len(table_deferred),
        "reviewed_positive_metric_eligible_count": len(eligible),
        "excluded_count": len([row for row in reviewed_rows if row["pdf_review_label"] == "excluded"]),
        "pdf_review_label_counts": counter_dict(reviewed_rows, "pdf_review_label"),
        "review_decision_counts": counter_dict(reviewed_rows, "review_decision"),
        "positive_metric_eligible_query_ids": [row["query_id"] for row in eligible],
        "table_deferred_query_ids": [row["query_id"] for row in table_deferred],
        "blockers": dedupe(blockers),
        "warnings": [],
        "notes": [
            "This manifest is separate from eval/gold_queries_v0.csv.",
            "Table-deferred rows are preserved for investigation but excluded from reviewed positive metrics.",
        ],
    }
    return reviewed_rows, report


def reviewed_row(gold: Mapping[str, str], overlay: Mapping[str, Any] | None) -> dict[str, Any]:
    if overlay is None:
        bbox_policy = "REQUIRED" if clean(gold.get("expected_bbox")) else "NOT_APPLICABLE"
        match_policy = "EXACT_PAGE_AND_BBOX" if clean(gold.get("expected_bbox")) else "PAGE_WITH_OPTIONAL_BBOX"
        policy = {
            "pdf_review_label": "positive_reviewed",
            "pdf_match_policy": match_policy,
            "pdf_table_policy": "NOT_TABLE_QUERY",
            "pdf_bbox_policy": bbox_policy,
            "review_decision": "KEEP_REVIEWED_POSITIVE",
            "positive_metric_eligible": True,
            "policy_note": "Reviewed positive row inherited from v0 without C7 relabel decision.",
        }
    else:
        policy = {
            "pdf_review_label": overlay.get("pdf_review_label"),
            "pdf_match_policy": overlay.get("pdf_match_policy"),
            "pdf_table_policy": overlay.get("pdf_table_policy"),
            "pdf_bbox_policy": overlay.get("pdf_bbox_policy"),
            "review_decision": overlay.get("final_decision"),
            "positive_metric_eligible": bool(overlay.get("positive_metric_eligible")),
            "policy_note": overlay.get("rationale"),
        }
    notes = clean(gold.get("notes"))
    policy_note = clean(policy.get("policy_note"))
    return {
        "query_id": gold.get("query_id"),
        "bucket": gold.get("bucket"),
        "query": gold.get("query"),
        "expected_file_name": gold.get("expected_file_name"),
        "expected_document_version_id": gold.get("expected_document_version_id"),
        "expected_chunk_type": gold.get("expected_chunk_type"),
        "expected_location_type": gold.get("expected_location_type"),
        "expected_physical_page_index": gold.get("expected_physical_page_index"),
        "expected_page_no": gold.get("expected_page_no"),
        "expected_page_label": gold.get("expected_page_label"),
        "expected_bbox": gold.get("expected_bbox"),
        "expected_answer_text": gold.get("expected_answer_text"),
        "must_contain_terms": gold.get("must_contain_terms"),
        "source_sample_id": gold.get("source_sample_id"),
        "label_status": gold.get("label_status"),
        "pdf_review_label": policy.get("pdf_review_label"),
        "pdf_match_policy": policy.get("pdf_match_policy"),
        "pdf_table_policy": policy.get("pdf_table_policy"),
        "pdf_bbox_policy": policy.get("pdf_bbox_policy"),
        "review_decision": policy.get("review_decision"),
        "positive_metric_eligible": bool(policy.get("positive_metric_eligible")),
        "notes": f"{notes} | {policy_note}" if notes and policy_note else notes or policy_note,
    }


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c7-report", default=str(DEFAULT_C7_REPORT))
    parser.add_argument("--c6-breakdown", default=str(DEFAULT_C6_BREAKDOWN))
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--reviewed-manifest", default=str(DEFAULT_REVIEWED_MANIFEST))
    parser.add_argument("--manifest-report", default=str(DEFAULT_MANIFEST_REPORT))
    parser.add_argument("--pdf-candidate-namespace", default=PDF_CANDIDATE_NAMESPACE)
    parser.add_argument("--pdf-artifact-dir", default=PDF_ARTIFACT_DIR)
    parser.add_argument("--promotion-evidence", default="false")
    parser.add_argument("--evidence-role", default=EVIDENCE_ROLE)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
