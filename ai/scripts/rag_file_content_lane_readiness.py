"""Build Track B R9 FILE vs CONTENT lane readiness diagnostics.

This report preserves the R1 routing-matrix status and creates a separate
diagnostic-only readiness matrix. It never promotes missing lanes, FILE lanes,
APP smoke rows, or policy-pending PDF rows into a shared denominator.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent

DEFAULT_R1_CSV = AI_WORKER_ROOT / "eval" / "eval_queries" / "query_intent_routing_matrix_v0.csv"
DEFAULT_R1_REPORT = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_query_intent_routing_matrix_report.json"
)
DEFAULT_NAMU_GOLD = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_text_namu_v4_v0.csv"
DEFAULT_XLSX_GOLD = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_xlsx_v3_positive_reviewed.csv"
DEFAULT_PDF_GOLD = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_pdf_v0.csv"
DEFAULT_REPORT = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_file_content_lane_readiness_report.json"
)
DEFAULT_CSV = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_file_content_lane_readiness.csv"
)

NAMU_ARTIFACTS = {
    "gold_validate": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "rag_text_namu_v4_gold_validate_report.json",
    "retrieval_diagnostic": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "rag_text_namu_v4_retrieval_diagnostic_report.json",
    "context_assembly": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "rag_text_namu_v4_context_assembly_report.json",
    "answer_eval": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "rag_text_namu_v4_answer_eval_report.json",
    "citation_support": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "rag_text_namu_v4_citation_support_report.json",
}
XLSX_ARTIFACTS = {
    "retrieval_diagnostic": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json",
    "performance_summary": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "rag_xlsx_v3_positive_reviewed_retrieval_performance_summary.json",
    "promotion_readiness": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "rag_xlsx_promotion_grade_eval_readiness.json",
}
PDF_ARTIFACTS = {
    "gold_policy_review": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "rag_pdf_gold_policy_review.json",
    "c7_decision_pack": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "rag_pdf_c7_decision_pack_summary.json",
    "vector_diagnostic": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "rag_retrieval_eval_pdf_vector_diagnostic_report.json",
}
BASELINE_ARTIFACTS = {
    "initial_immutable_vector_baseline_descriptor": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "initial_immutable_vector_baseline_descriptor.json",
    "initial_baseline_bootstrap_readiness": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "initial_baseline_bootstrap_readiness.json",
    "a5_c3_immutable_baseline_readiness": AI_WORKER_ROOT.parent
    / "reports"
    / "rag_eval"
    / "rag-ingestion"
    / "a5_c3_immutable_baseline_readiness.json",
}

LANES = [
    "APP_TEXT_SMOKE",
    "B_NAMU_TEXT_CONTENT",
    "TEXT_FILE_LOOKUP",
    "XLSX_CONTENT",
    "XLSX_FILE",
    "PDF_CONTENT",
    "PDF_FILE",
    "UNKNOWN",
    "MIXED_FILE_CONTENT",
]
REPORT_FIELDNAMES = [
    "retrieval_lane",
    "observed_row_count",
    "r1_observed_row_count",
    "eligible_positive_denominator_count",
    "excluded_count",
    "exclusion_reason",
    "current_artifact_source",
    "readiness_status",
    "next_action",
]
POSITIVE_LABEL_STATUSES = {"bound"}
NEEDS_REVIEW_LABEL_STATUSES = {"needs_review"}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_lane_readiness(
        r1_csv=Path(args.r1_csv),
        r1_report=Path(args.r1_report),
        namu_gold=Path(args.namu_gold),
        xlsx_gold=Path(args.xlsx_gold),
        pdf_gold=Path(args.pdf_gold),
        report_path=Path(args.report),
        csv_path=Path(args.csv),
    )
    print_json(
        {
            "status": report["status"],
            "report": repo_relative(Path(args.report)),
            "csv": repo_relative(Path(args.csv)),
            "r1_status_preserved": report["r1_status_preserved"],
            "forced_lane_coverage": report["forced_lane_coverage"],
            "file_lane_official_denominator_ready": report[
                "file_lane_official_denominator_ready"
            ],
        }
    )
    return 1 if report.get("blockers") else 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r1-csv", default=str(DEFAULT_R1_CSV))
    parser.add_argument("--r1-report", default=str(DEFAULT_R1_REPORT))
    parser.add_argument("--namu-gold", default=str(DEFAULT_NAMU_GOLD))
    parser.add_argument("--xlsx-gold", default=str(DEFAULT_XLSX_GOLD))
    parser.add_argument("--pdf-gold", default=str(DEFAULT_PDF_GOLD))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    return parser.parse_args(argv)


def run_lane_readiness(
    *,
    r1_csv: Path,
    r1_report: Path,
    namu_gold: Path,
    xlsx_gold: Path,
    pdf_gold: Path,
    report_path: Path,
    csv_path: Path,
) -> dict[str, Any]:
    run_id = utc_run_id()
    generated_at = utc_timestamp()
    r1_pre_hashes = protected_input_hashes(r1_csv, r1_report)
    r1_rows, r1_columns = read_csv_if_exists(r1_csv)
    namu_rows, namu_columns = read_csv_if_exists(namu_gold)
    xlsx_rows, xlsx_columns = read_csv_if_exists(xlsx_gold)
    pdf_rows, pdf_columns = read_csv_if_exists(pdf_gold)
    r1_payload = read_optional_json(r1_report)
    artifact_payloads = {
        "namu": read_artifact_group(NAMU_ARTIFACTS),
        "xlsx": read_artifact_group(XLSX_ARTIFACTS),
        "pdf": read_artifact_group(PDF_ARTIFACTS),
        "baseline": read_artifact_group(BASELINE_ARTIFACTS),
    }
    blockers = entry_gate_blockers(
        r1_csv=r1_csv,
        r1_report=r1_report,
        r1_rows=r1_rows,
        r1_payload=r1_payload,
        report_path=report_path,
        csv_path=csv_path,
    )
    lane_table = build_lane_table(
        r1_rows=r1_rows,
        namu_rows=namu_rows,
        xlsx_rows=xlsx_rows,
        pdf_rows=pdf_rows,
        artifacts=artifact_payloads,
    )
    output_path_blocked = any("must not overwrite R1" in blocker for blocker in blockers)
    if not output_path_blocked:
        write_csv(csv_path, lane_table)
        csv_sha = sha256_file(csv_path)
    else:
        csv_sha = None
    csv_written = not output_path_blocked
    report_written = not output_path_blocked
    r1_post_hashes = protected_input_hashes(r1_csv, r1_report)
    metrics = metrics_from_lane_table(lane_table, r1_rows, r1_payload)
    status = "NEEDS_REVIEW" if blockers else "PASS_WITH_WARNINGS"
    report = build_report(
        run_id=run_id,
        generated_at=generated_at,
        status=status,
        r1_csv=r1_csv,
        r1_report=r1_report,
        namu_gold=namu_gold,
        xlsx_gold=xlsx_gold,
        pdf_gold=pdf_gold,
        report_path=report_path,
        csv_path=csv_path,
        csv_sha256=csv_sha,
        csv_written=csv_written,
        report_written=report_written,
        r1_rows=r1_rows,
        r1_columns=r1_columns,
        namu_rows=namu_rows,
        namu_columns=namu_columns,
        xlsx_rows=xlsx_rows,
        xlsx_columns=xlsx_columns,
        pdf_rows=pdf_rows,
        pdf_columns=pdf_columns,
        r1_payload=r1_payload,
        r1_pre_hashes=r1_pre_hashes,
        r1_post_hashes=r1_post_hashes,
        artifacts=artifact_payloads,
        lane_table=lane_table,
        metrics=metrics,
        blockers=blockers,
    )
    if not output_path_blocked:
        write_json(report_path, report)
    return report


def entry_gate_blockers(
    *,
    r1_csv: Path,
    r1_report: Path,
    r1_rows: list[dict[str, str]],
    r1_payload: Mapping[str, Any] | None,
    report_path: Path,
    csv_path: Path,
) -> list[str]:
    blockers: list[str] = []
    if not r1_csv.exists():
        blockers.append(f"missing R1 CSV: {repo_relative(r1_csv)}")
    if not r1_report.exists():
        blockers.append(f"missing R1 report: {repo_relative(r1_report)}")
    if r1_report.exists() and r1_payload is None:
        blockers.append(f"R1 report is not a JSON object: {repo_relative(r1_report)}")
    if r1_csv.exists() and not r1_rows:
        blockers.append("R1 CSV has no rows")
    blockers.extend(output_path_blockers(r1_csv, r1_report, report_path, csv_path))
    return blockers


def output_path_blockers(r1_csv: Path, r1_report: Path, report_path: Path, csv_path: Path) -> list[str]:
    blockers: list[str] = []
    protected = {
        "R1 CSV": resolve_for_compare(r1_csv),
        "R1 report": resolve_for_compare(r1_report),
    }
    outputs = {
        "R9 CSV": resolve_for_compare(csv_path),
        "R9 report": resolve_for_compare(report_path),
    }
    for output_label, output_path in outputs.items():
        for protected_label, protected_path in protected.items():
            if output_path == protected_path:
                blockers.append(f"{output_label} must not overwrite R1 input path ({protected_label})")
    return blockers


def resolve_for_compare(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def build_lane_table(
    *,
    r1_rows: list[dict[str, str]],
    namu_rows: list[dict[str, str]],
    xlsx_rows: list[dict[str, str]],
    pdf_rows: list[dict[str, str]],
    artifacts: Mapping[str, Mapping[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    r1_lane_counts = Counter(clean(row.get("retrieval_lane")) for row in r1_rows)
    mixed_count = int(r1_lane_counts.get("MIXED_FILE_CONTENT", 0))
    lane_rows = {
        "APP_TEXT_SMOKE": app_text_smoke_lane(r1_lane_counts),
        "B_NAMU_TEXT_CONTENT": namu_text_lane(namu_rows, artifacts["namu"]),
        "TEXT_FILE_LOOKUP": missing_file_lane(
            "TEXT_FILE_LOOKUP",
            r1_lane_counts.get("TEXT_FILE_LOOKUP", 0),
            "text file lookup fixtures/gold are not observed",
        ),
        "XLSX_CONTENT": xlsx_content_lane(r1_lane_counts, xlsx_rows, artifacts["xlsx"]),
        "XLSX_FILE": missing_file_lane(
            "XLSX_FILE",
            r1_lane_counts.get("XLSX_FILE", 0),
            "xlsx file lookup fixtures/gold are not observed",
        ),
        "PDF_CONTENT": pdf_content_lane(r1_lane_counts, pdf_rows, artifacts["pdf"]),
        "PDF_FILE": missing_file_lane(
            "PDF_FILE",
            r1_lane_counts.get("PDF_FILE", 0),
            "pdf file lookup fixtures/gold are not observed",
        ),
        "UNKNOWN": unknown_lane(r1_lane_counts),
        "MIXED_FILE_CONTENT": mixed_lane(mixed_count),
    }
    return [lane_rows[lane] for lane in LANES]


def app_text_smoke_lane(r1_lane_counts: Mapping[str, int]) -> dict[str, Any]:
    observed = int(r1_lane_counts.get("APP_TEXT_SMOKE", 0))
    return lane_record(
        lane="APP_TEXT_SMOKE",
        observed=observed,
        r1_observed=observed,
        eligible=0,
        excluded=observed,
        exclusion_reason="smoke_only_not_b_namu_mainline",
        sources=["R1 matrix APP_TEXT_SMOKE rows"],
        readiness_status="SMOKE_ONLY",
        next_action="Keep B-app smoke separate from B-namu TEXT content and promotion denominators.",
    )


def namu_text_lane(
    namu_rows: list[dict[str, str]], artifacts: Mapping[str, dict[str, Any]]
) -> dict[str, Any]:
    observed = len(namu_rows)
    positive = sum(1 for row in namu_rows if denominator_included(row))
    excluded = observed - positive
    r8 = artifacts.get("citation_support", {})
    answerable = int(r8.get("citation_support_denominator_count") or 0)
    sources = artifact_sources(artifacts, [DEFAULT_NAMU_GOLD])
    return lane_record(
        lane="B_NAMU_TEXT_CONTENT",
        observed=observed,
        r1_observed=0,
        eligible=positive,
        excluded=excluded,
        exclusion_reason="needs_review_excluded; citation support sub-denominator remains diagnostic",
        sources=sources,
        readiness_status="DIAGNOSTIC_READY",
        next_action=(
            "Use R3/R5/R6/R7/R8 as B-namu diagnostic evidence; keep promotion_ready=false "
            f"and treat R8 citation support denominator {answerable} as diagnostic-only."
        ),
        extra={
            "citation_support_denominator_count": answerable,
            "retrieval_context_miss_excluded_count": int(
                r8.get("retrieval_context_miss_excluded_count") or 0
            ),
        },
    )


def xlsx_content_lane(
    r1_lane_counts: Mapping[str, int],
    xlsx_rows: list[dict[str, str]],
    artifacts: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    observed = len(xlsx_rows) or int(r1_lane_counts.get("XLSX_CONTENT", 0))
    eligible = sum(1 for row in xlsx_rows if xlsx_positive_eligible(row))
    excluded = max(observed - eligible, 0)
    promotion_readiness = artifacts.get("promotion_readiness", {})
    baseline_compatible = bool(
        (promotion_readiness.get("readiness_summary") or {}).get(
            "baseline_dataset_compatible_with_cleaned_xlsx_v1"
        )
    )
    readiness_status = (
        "DIAGNOSTIC_READY"
        if baseline_compatible
        else "DIAGNOSTIC_READY_PROMOTION_BASELINE_BLOCKED"
    )
    return lane_record(
        lane="XLSX_CONTENT",
        observed=observed,
        r1_observed=int(r1_lane_counts.get("XLSX_CONTENT", 0)),
        eligible=eligible,
        excluded=excluded,
        exclusion_reason=(
            "non_positive_or_not_promotion_eval_eligible"
            if excluded
            else "none; promotion-grade baseline compatibility is tracked separately"
        ),
        sources=artifact_sources(artifacts, [DEFAULT_XLSX_GOLD]),
        readiness_status=readiness_status,
        next_action=(
            "Keep the reviewed positive 35 as XLSX content diagnostic denominator; resolve baseline "
            "dataset compatibility before any promotion-grade claim."
        ),
        extra={
            "promotion_grade_baseline_compatible": baseline_compatible,
            "promotion_readiness_status": promotion_readiness.get("status"),
        },
    )


def pdf_content_lane(
    r1_lane_counts: Mapping[str, int],
    pdf_rows: list[dict[str, str]],
    artifacts: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    observed = len(pdf_rows) or int(r1_lane_counts.get("PDF_CONTENT", 0))
    c7 = artifacts.get("c7_decision_pack", {})
    policy_review = artifacts.get("gold_policy_review", {})
    return lane_record(
        lane="PDF_CONTENT",
        observed=observed,
        r1_observed=int(r1_lane_counts.get("PDF_CONTENT", 0)),
        eligible=0,
        excluded=observed,
        exclusion_reason="pdf_c7_policy_pending_not_official_denominator",
        sources=artifact_sources(artifacts, [DEFAULT_PDF_GOLD]),
        readiness_status="POLICY_PENDING_DIAGNOSTIC_ONLY",
        next_action=(
            "Keep PDF rows diagnostic-only until C7 policy/user decisions resolve official denominator use."
        ),
        extra={
            "pdf_policy_review_status": policy_review.get("status"),
            "c7_decision_pack_status": c7.get("status"),
            "human_decision_required_count": int(
                c7.get("human_decision_required_count")
                or policy_review.get("human_decision_required_count")
                or 0
            ),
        },
    )


def missing_file_lane(lane: str, r1_observed: int, reason: str) -> dict[str, Any]:
    status = "NEEDS_FIXTURE_OR_GOLD_DESIGN" if r1_observed else "NOT_OBSERVED"
    return lane_record(
        lane=lane,
        observed=r1_observed,
        r1_observed=r1_observed,
        eligible=0,
        excluded=r1_observed,
        exclusion_reason=reason if r1_observed else "not_observed",
        sources=[],
        readiness_status=status,
        next_action="Design explicit diagnostic fixtures/gold before counting this FILE lane.",
    )


def unknown_lane(r1_lane_counts: Mapping[str, int]) -> dict[str, Any]:
    observed = int(r1_lane_counts.get("UNKNOWN", 0))
    return lane_record(
        lane="UNKNOWN",
        observed=observed,
        r1_observed=observed,
        eligible=0,
        excluded=observed,
        exclusion_reason="not_observed" if not observed else "requires_clarification",
        sources=[],
        readiness_status="NOT_OBSERVED" if not observed else "NEEDS_CLARIFICATION",
        next_action="Leave absent UNKNOWN lane absent; clarify any future UNKNOWN rows before metric use.",
    )


def mixed_lane(observed: int) -> dict[str, Any]:
    return lane_record(
        lane="MIXED_FILE_CONTENT",
        observed=observed,
        r1_observed=observed,
        eligible=0,
        excluded=observed,
        exclusion_reason="not_observed" if not observed else "requires_file_content_split",
        sources=[],
        readiness_status="NOT_OBSERVED" if not observed else "NEEDS_SPLIT_OR_CLARIFICATION",
        next_action=(
            "Leave absent MIXED lane absent; split future mixed rows into explicit FILE and CONTENT tasks."
        ),
    )


def lane_record(
    *,
    lane: str,
    observed: int,
    r1_observed: int,
    eligible: int,
    excluded: int,
    exclusion_reason: str,
    sources: list[str],
    readiness_status: str,
    next_action: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "retrieval_lane": lane,
        "observed_row_count": observed,
        "r1_observed_row_count": r1_observed,
        "eligible_positive_denominator_count": eligible,
        "excluded_count": excluded,
        "exclusion_reason": exclusion_reason,
        "current_artifact_source": sources,
        "readiness_status": readiness_status,
        "next_action": next_action,
    }
    if extra:
        record.update(extra)
    return record


def metrics_from_lane_table(
    lane_table: list[Mapping[str, Any]],
    r1_rows: list[dict[str, str]],
    r1_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "r1_row_count": len(r1_rows),
        "r1_status": (r1_payload or {}).get("status"),
        "lane_counts": {
            clean(row["retrieval_lane"]): int(row["observed_row_count"]) for row in lane_table
        },
        "eligible_positive_denominator_counts": {
            clean(row["retrieval_lane"]): int(row["eligible_positive_denominator_count"])
            for row in lane_table
        },
        "excluded_counts": {
            clean(row["retrieval_lane"]): int(row["excluded_count"]) for row in lane_table
        },
        "missing_or_not_observed_lanes": [
            clean(row["retrieval_lane"])
            for row in lane_table
            if int(row["observed_row_count"]) == 0
        ],
        "file_lane_observed_count": sum(
            int(row["observed_row_count"])
            for row in lane_table
            if clean(row["retrieval_lane"]) in {"TEXT_FILE_LOOKUP", "XLSX_FILE", "PDF_FILE"}
        ),
    }


def build_report(
    *,
    run_id: str,
    generated_at: str,
    status: str,
    r1_csv: Path,
    r1_report: Path,
    namu_gold: Path,
    xlsx_gold: Path,
    pdf_gold: Path,
    report_path: Path,
    csv_path: Path,
    csv_sha256: str | None,
    csv_written: bool,
    report_written: bool,
    r1_rows: list[dict[str, str]],
    r1_columns: list[str],
    namu_rows: list[dict[str, str]],
    namu_columns: list[str],
    xlsx_rows: list[dict[str, str]],
    xlsx_columns: list[str],
    pdf_rows: list[dict[str, str]],
    pdf_columns: list[str],
    r1_payload: Mapping[str, Any] | None,
    r1_pre_hashes: Mapping[str, str | None],
    r1_post_hashes: Mapping[str, str | None],
    artifacts: Mapping[str, Mapping[str, dict[str, Any]]],
    lane_table: list[dict[str, Any]],
    metrics: Mapping[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    r1_status = (r1_payload or {}).get("status")
    r1_inputs_unchanged = dict(r1_pre_hashes) == dict(r1_post_hashes)
    baseline_refs = baseline_references(artifacts.get("baseline", {}), artifacts)
    warnings = warnings_from(lane_table, r1_status, baseline_refs)
    return {
        "run_id": run_id,
        "generated_at": generated_at,
        "schema_version": "rag_file_content_lane_readiness_report_v1",
        "status": status,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "phase": "R9_FILE_CONTENT_LANE_READINESS",
        "r1_status": r1_status,
        "r1_status_preserved": bool(r1_inputs_unchanged),
        "forced_lane_coverage": False,
        "must_group_by": "retrieval_lane",
        "app_text_smoke_separate": True,
        "pdf_policy_pending": True,
        "file_lane_official_denominator_ready": metrics.get("file_lane_observed_count") > 0
        and any(
            row["eligible_positive_denominator_count"] > 0
            for row in lane_table
            if row["retrieval_lane"] in {"TEXT_FILE_LOOKUP", "XLSX_FILE", "PDF_FILE"}
        ),
        "live_llm_run": False,
        "optional_judge_run": False,
        "promotion_run": False,
        "retrieval_tuning_run": False,
        "reranking_run": False,
        "indexing_run": False,
        "db_mutation_run": False,
        "corpus_mutation_run": False,
        "r1_csv_path": repo_relative(r1_csv),
        "r1_csv_sha256": sha256_if_exists(r1_csv),
        "r1_report_path": repo_relative(r1_report),
        "r1_report_sha256": sha256_if_exists(r1_report),
        "r1_input_hashes_before": dict(r1_pre_hashes),
        "r1_input_hashes_after": dict(r1_post_hashes),
        "r9_report_path": repo_relative(report_path),
        "r9_csv_path": repo_relative(csv_path),
        "r9_csv_sha256": csv_sha256,
        "r9_csv_written": csv_written,
        "r9_report_json_written": report_written,
        "input_records": {
            "r1_csv": input_record(r1_csv, r1_rows, r1_columns),
            "namu_gold": input_record(namu_gold, namu_rows, namu_columns),
            "xlsx_gold": input_record(xlsx_gold, xlsx_rows, xlsx_columns),
            "pdf_gold_diagnostic_only": input_record(pdf_gold, pdf_rows, pdf_columns),
        },
        "lane_counts": metrics.get("lane_counts", {}),
        "eligible_positive_denominator_counts": metrics.get(
            "eligible_positive_denominator_counts", {}
        ),
        "excluded_counts": metrics.get("excluded_counts", {}),
        "lane_readiness_table": lane_table,
        "artifact_sources": {
            group: artifact_records(payloads) for group, payloads in artifacts.items()
        },
        "baseline_references": baseline_refs,
        "done_criteria": {
            "r1_csv_parsed": bool(r1_rows),
            "r1_report_json_parsed": bool(r1_payload),
            "r1_status_preserved": bool(r1_inputs_unchanged),
            "r1_report_not_overwritten": r1_pre_hashes.get("r1_report_sha256")
            == r1_post_hashes.get("r1_report_sha256"),
            "r1_csv_not_overwritten": r1_pre_hashes.get("r1_csv_sha256")
            == r1_post_hashes.get("r1_csv_sha256"),
            "r9_report_json_written": report_written,
            "r9_csv_written": csv_written,
            "forced_lane_coverage_false": True,
            "must_group_by_retrieval_lane": True,
            "app_text_smoke_separate": True,
            "b_namu_text_content_separate": True,
            "xlsx_content_separate": True,
            "pdf_policy_pending": True,
            "file_lanes_not_promoted_without_fixture_or_gold": True,
            "unknown_and_mixed_not_forced_pass": True,
            "promotion_evidence_false": True,
        },
        "blockers": blockers,
        "warnings": warnings,
        "next_phase_recommendation": (
            "Keep R1 NEEDS_REVIEW intact; use R9 as lane-separated diagnostic readiness only."
        ),
    }


def warnings_from(
    lane_table: list[Mapping[str, Any]],
    r1_status: object,
    baseline_refs: list[Mapping[str, Any]],
) -> list[str]:
    warnings = []
    if r1_status == "NEEDS_REVIEW":
        warnings.append("R1 routing matrix remains NEEDS_REVIEW and was not forced to PASS.")
    for row in lane_table:
        if row["retrieval_lane"] == "APP_TEXT_SMOKE" and row["observed_row_count"]:
            warnings.append("APP_TEXT_SMOKE remains smoke-only and separate from B-namu.")
        if row["retrieval_lane"] == "PDF_CONTENT" and row["observed_row_count"]:
            warnings.append("PDF_CONTENT remains diagnostic-only while C7 policy is pending.")
        if row["retrieval_lane"].endswith("_FILE") and row["observed_row_count"] == 0:
            warnings.append(f"{row['retrieval_lane']} is not observed and was not promoted.")
    if any(ref.get("stale_for_r9_lane_readiness") for ref in baseline_refs):
        warnings.append("Existing baseline references predate R7/C7 and are marked stale for R9.")
    return sorted(set(warnings))


def baseline_references(
    baseline_artifacts: Mapping[str, dict[str, Any]],
    all_artifacts: Mapping[str, Mapping[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    freshness_paths = [
        NAMU_ARTIFACTS["answer_eval"],
        NAMU_ARTIFACTS["citation_support"],
        PDF_ARTIFACTS["c7_decision_pack"],
    ]
    freshness_mtime = max((path.stat().st_mtime for path in freshness_paths if path.exists()), default=0)
    refs = []
    for name, payload in baseline_artifacts.items():
        path = BASELINE_ARTIFACTS[name]
        exists = path.exists()
        mtime = path.stat().st_mtime if exists else 0
        refs.append(
            {
                "name": name,
                "path": repo_relative(path),
                "exists": exists,
                "status": payload.get("status"),
                "baseline_type": payload.get("baseline_type"),
                "baseline_index_version": payload.get("baseline_index_version"),
                "usable_as_baseline_for_future_candidates": payload.get(
                    "usable_as_baseline_for_future_candidates"
                ),
                "stale_for_r9_lane_readiness": bool(exists and freshness_mtime and mtime < freshness_mtime),
                "stale_reason": (
                    "artifact predates R7/R8 B-namu or C7 PDF policy artifacts"
                    if exists and freshness_mtime and mtime < freshness_mtime
                    else None
                ),
            }
        )
    for path in latest_e2e_baseline_manifests():
        payload = read_optional_json(path) or {}
        exists = path.exists()
        mtime = path.stat().st_mtime if path.exists() else 0
        stale = bool(exists and freshness_mtime and mtime < freshness_mtime)
        refs.append(
            {
                "name": f"e2e_baseline_manifest:{payload.get('run_id') or path.parent.name}",
                "path": repo_relative(path),
                "exists": exists,
                "status": payload.get("status"),
                "baseline_type": payload.get("schema_version"),
                "baseline_index_version": payload.get("run_id"),
                "usable_as_baseline_for_future_candidates": None,
                "live_call_executed": payload.get("live_call_executed"),
                "stale_for_r9_lane_readiness": stale,
                "stale_reason": (
                    "manifest predates R7/R8 B-namu or C7 PDF policy artifacts"
                    if stale
                    else None
                ),
                "historical_stale_not_r9_effective": stale,
                "historical_summary_omitted": (
                    "stale denominator policy summary omitted so historical official counts are not scraped as R9 readiness"
                    if stale and payload.get("denominator_policy_summary")
                    else None
                ),
            }
        )
    return refs


def latest_e2e_baseline_manifests(limit: int = 1) -> list[Path]:
    root = AI_WORKER_ROOT / "eval" / "artifacts" / "eval_runs"
    if not root.exists():
        return []
    manifests = [path for path in root.glob("*/manifest.json") if path.is_file()]
    manifests.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return manifests[:limit]


def artifact_sources(artifacts: Mapping[str, dict[str, Any]], extra_paths: list[Path]) -> list[str]:
    sources = [repo_relative(path) for path in extra_paths if path.exists()]
    for name, payload in artifacts.items():
        path = payload.get("_path")
        if payload.get("_exists") and path:
            sources.append(repo_relative(Path(path)))
    return sources


def artifact_records(artifacts: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for name, payload in artifacts.items():
        path = Path(clean(payload.get("_path")))
        records.append(
            {
                "name": name,
                "path": repo_relative(path),
                "exists": bool(payload.get("_exists")),
                "status": payload.get("status"),
                "promotion_evidence": payload.get("promotion_evidence"),
                "evidence_role": payload.get("evidence_role"),
                "sha256": sha256_if_exists(path),
            }
        )
    return records


def read_artifact_group(paths: Mapping[str, Path]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        payload = read_optional_json(path) or {}
        payload["_path"] = str(path)
        payload["_exists"] = path.exists()
        result[name] = payload
    return result


def input_record(path: Path, rows: list[dict[str, str]], columns: list[str]) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "row_count": len(rows),
        "columns": columns,
        "sha256": sha256_if_exists(path),
    }


def protected_input_hashes(r1_csv: Path, r1_report: Path) -> dict[str, str | None]:
    return {
        "r1_csv_sha256": sha256_if_exists(r1_csv),
        "r1_report_sha256": sha256_if_exists(r1_report),
    }


def xlsx_positive_eligible(row: Mapping[str, str]) -> bool:
    return (
        clean(row.get("policy_label")).lower() == "positive"
        and clean(row.get("review_decision")).upper() == "KEEP_AS_POSITIVE"
        and clean(row.get("promotion_eval_eligible")).lower() == "true"
        and clean(row.get("review_status")).lower() == "ready_positive"
        and denominator_included(row)
    )


def denominator_included(row: Mapping[str, str]) -> bool:
    return clean(row.get("label_status")).lower() in POSITIVE_LABEL_STATUSES and clean(
        row.get("allowed_abstain")
    ).lower() != "true"


def is_needs_review(row: Mapping[str, str]) -> bool:
    return clean(row.get("label_status")).lower() in NEEDS_REVIEW_LABEL_STATUSES


def read_csv_if_exists(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            serialized["current_artifact_source"] = ";".join(row.get("current_artifact_source") or [])
            writer.writerow({field: serialized.get(field, "") for field in REPORT_FIELDNAMES})


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_if_exists(path: Path) -> str | None:
    return sha256_file(path) if path.exists() else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
