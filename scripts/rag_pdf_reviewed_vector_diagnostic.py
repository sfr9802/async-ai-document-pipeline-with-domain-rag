"""Build the Track C C5.1 reviewed PDF vector diagnostic report.

The default path is deterministic and diagnostic-only: it replays the existing
C5 query-level top-k evidence through the reviewed PDF manifest and policy
overlay. It does not mutate gold v0, run promotion, update baselines, tune
retrieval, reindex, or regenerate candidate artifacts.
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
    EVIDENCE_ROLE,
    PDF_ARTIFACT_DIR,
    PDF_CANDIDATE_NAMESPACE,
    artifact_identity,
    bool_cell,
    clean,
    dedupe,
    expected_docv,
    expected_file,
    file_sha256,
    hit_at,
    hit_docv_match,
    hit_file_match,
    hit_page_match,
    hit_rank,
    location,
    match_breakdown,
    mean_bool,
    mrr_at,
    print_json,
    read_csv_rows,
    read_json,
    report_ref,
    summarize_top_hit,
    utc_run_id,
    utc_timestamp,
    write_json,
)


DEFAULT_REVIEWED_MANIFEST = Path("eval/gold_queries_pdf_v1_reviewed.csv")
DEFAULT_POLICY_OVERLAY = Path("reports/rag_pdf_gold_policy_decision_overlay.json")
DEFAULT_SOURCE_EVAL_REPORT = Path("reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json")
DEFAULT_OUTPUT = Path("reports/rag_retrieval_eval_pdf_v1_reviewed_vector_diagnostic_report.json")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_path = Path(args.reviewed_manifest)
    overlay_path = Path(args.policy_overlay)
    source_path = Path(args.source_eval_report)
    if not source_path.exists():
        payload = blocked_report(
            reviewed_manifest_path=manifest_path,
            policy_overlay_path=overlay_path,
            source_eval_report_path=source_path,
            reason=f"source C5 eval report is missing: {source_path}",
        )
    else:
        payload = build_reviewed_diagnostic(
            reviewed_manifest_rows=read_csv_rows(manifest_path),
            policy_overlay=read_json(overlay_path),
            source_eval_report=read_json(source_path),
            reviewed_manifest_path=manifest_path,
            policy_overlay_path=overlay_path,
            source_eval_report_path=source_path,
            artifact_dir=Path(args.artifact_dir),
            index_version=args.index_version,
        )
    write_json(Path(args.output), payload)
    print_json(payload)
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def blocked_report(
    *,
    reviewed_manifest_path: Path,
    policy_overlay_path: Path,
    source_eval_report_path: Path,
    reason: str,
) -> dict[str, Any]:
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": "BLOCKED_WITH_REASON",
        "track": "C",
        "phase": "C5.1",
        "report_role": "pdf_v1_reviewed_vector_diagnostic",
        "promotion_evidence": False,
        "evidence_role": EVIDENCE_ROLE,
        "pdf_candidate_namespace": PDF_CANDIDATE_NAMESPACE,
        "pdf_artifact_dir": PDF_ARTIFACT_DIR,
        "retrieval_execution": "blocked_before_search",
        "blocked_reason": reason,
        "input_reports": {
            "reviewed_manifest": artifact_identity(reviewed_manifest_path),
            "policy_overlay": artifact_identity(policy_overlay_path),
            "source_eval_report": artifact_identity(source_eval_report_path),
        },
        "blockers": [reason],
        "warnings": [],
    }


def build_reviewed_diagnostic(
    *,
    reviewed_manifest_rows: list[dict[str, str]],
    policy_overlay: Mapping[str, Any],
    source_eval_report: Mapping[str, Any],
    reviewed_manifest_path: Path,
    policy_overlay_path: Path,
    source_eval_report_path: Path,
    artifact_dir: Path = Path(PDF_ARTIFACT_DIR),
    index_version: str = PDF_CANDIDATE_NAMESPACE,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    artifact = artifact_contract(artifact_dir, index_version)
    validate_inputs(
        reviewed_manifest_rows=reviewed_manifest_rows,
        policy_overlay=policy_overlay,
        source_eval_report=source_eval_report,
        artifact=artifact,
        index_version=index_version,
        blockers=blockers,
    )
    source_rows_by_id = {
        clean(row.get("query_id")): row
        for row in source_eval_report.get("query_results") or []
        if isinstance(row, Mapping)
    }
    reviewed_rows = [
        evaluate_reviewed_row(row, source_rows_by_id.get(clean(row.get("query_id"))))
        for row in reviewed_manifest_rows
    ]
    missing_source = [row for row in reviewed_rows if row.get("source_query_result_missing")]
    if missing_source:
        blockers.append("every reviewed manifest row must have a C5 query_result")

    deferred_rows = [row for row in reviewed_rows if row.get("pdf_review_label") == "table_deferred"]
    eligible_rows = [row for row in reviewed_rows if row.get("positive_metric_eligible") is True]
    ranks = [row.get("policy_adjusted_location_rank") for row in eligible_rows]
    file_hits = [bool(row.get("pdf_file_hit_at_10")) for row in eligible_rows]
    page_hits = [bool(row.get("pdf_page_hit_at_10")) for row in eligible_rows]
    bbox_applicable_rows = [row for row in eligible_rows if row.get("expected_bbox_present")]
    bbox_hits = [bool(row.get("pdf_bbox_overlap_at_10")) for row in bbox_applicable_rows]
    exact_bbox_hits = [bool(row.get("pdf_exact_bbox_at_10")) for row in bbox_applicable_rows]
    policy_location_hits = [bool(row.get("policy_adjusted_location_success")) for row in eligible_rows]
    true_failure_rows = [
        row for row in eligible_rows
        if row.get("policy_adjusted_location_success") is False
        and clean(row.get("raw_failure_reason"))
    ]
    metadata_failure_count = int(source_eval_report.get("metadata_projection_failure_count") or 0)
    table_specific_success_count = 0
    if true_failure_rows:
        warnings.append(
            f"true_retrieval_ranking_failure_count={len(true_failure_rows)}; investigate at C8 case level"
        )
    if deferred_rows:
        warnings.append(
            f"table_deferred_count={len(deferred_rows)}; table-specific retrieval remains unproven"
        )

    metrics = {
        "reviewed_query_count": len(reviewed_rows),
        "reviewed_positive_metric_denominator": len(eligible_rows),
        "deferred_table_count": len(deferred_rows),
        "Hit@1": hit_at(ranks, 1),
        "Hit@3": hit_at(ranks, 3),
        "Hit@5": hit_at(ranks, 5),
        "Hit@10": hit_at(ranks, 10),
        "MRR@10": mrr_at(ranks, 10),
        "pdf_file_hit@10": mean_bool(file_hits),
        "pdf_page_hit@10": mean_bool(page_hits),
        "pdf_bbox_overlap@10": mean_bool(bbox_hits),
        "pdf_policy_adjusted_location_accuracy": mean_bool(policy_location_hits),
        "pdf_exact_bbox_location_accuracy": mean_bool(exact_bbox_hits),
        "table_specific_success_count": table_specific_success_count,
        "table_deferred_count": len(deferred_rows),
        "metadata_projection_failure_count": metadata_failure_count,
        "true_retrieval_ranking_failure_count": len(true_failure_rows),
        "pdf_bbox_metric_denominator": len(bbox_applicable_rows),
        "policy_adjusted_location_success_count": sum(1 for value in policy_location_hits if value),
        "exact_bbox_success_count": sum(1 for value in exact_bbox_hits if value),
    }
    status = "FAIL" if blockers else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C5.1",
        "report_role": "pdf_v1_reviewed_vector_diagnostic",
        "promotion_evidence": False,
        "evidence_role": EVIDENCE_ROLE,
        "pdf_candidate_namespace": index_version,
        "pdf_artifact_dir": str(artifact_dir),
        "retrieval_backend": "vector",
        "retrieval_execution": "recomputed_from_existing_c5_query_results",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "baseline_execution": "not_run_by_this_script",
        "gold_mutation_execution": "not_run_by_this_script",
        "immutable_baseline_changed": False,
        "xlsx_candidate_artifact_changed": False,
        "table_specific_retrieval_proven": False,
        "input_reports": {
            "reviewed_manifest": artifact_identity(reviewed_manifest_path),
            "policy_overlay": report_ref(policy_overlay, policy_overlay_path),
            "source_c5_eval_report": report_ref(source_eval_report, source_eval_report_path),
            "pdf_candidate_artifact": artifact,
        },
        "raw_c5_metrics": source_eval_report.get("metrics") or {},
        "metrics": metrics,
        **metrics,
        "deferred_table_query_ids": [row["query_id"] for row in deferred_rows],
        "true_retrieval_ranking_failure_query_ids": [row["query_id"] for row in true_failure_rows],
        "rows": reviewed_rows,
        "blockers": dedupe(blockers),
        "warnings": dedupe(warnings),
        "next_action": (
            "Use C8 case pack for the 7 reviewed non-table failures; do not run broad tuning yet."
            if status in {"PASS", "PASS_WITH_WARNINGS"}
            else "Resolve reviewed diagnostic blockers before C8."
        ),
        "notes": [
            "Reviewed metrics are recomputed from existing C5 query-level top-k evidence; this wrapper does not run a fresh live vector search.",
            "Deferred table rows are excluded from positive Hit/MRR/location denominators.",
            "PAGE_WITH_OPTIONAL_BBOX accepts page success but does not count as bbox success.",
            "PAGE_OR_PARAGRAPH_SAME_PAGE is counted as policy-adjusted same-page evidence, not exact bbox success.",
        ],
    }


def evaluate_reviewed_row(manifest_row: Mapping[str, str], source_row: Mapping[str, Any] | None) -> dict[str, Any]:
    if source_row is None:
        return {
            "query_id": manifest_row.get("query_id"),
            "bucket": manifest_row.get("bucket"),
            "query": manifest_row.get("query"),
            "pdf_review_label": manifest_row.get("pdf_review_label"),
            "positive_metric_eligible": bool_cell(manifest_row.get("positive_metric_eligible")),
            "source_query_result_missing": True,
        }
    hits = list(source_row.get("top_k_results") or [])
    eligible = bool_cell(manifest_row.get("positive_metric_eligible"))
    decision = clean(manifest_row.get("review_decision"))
    policy = clean(manifest_row.get("pdf_match_policy"))
    policy_rank = policy_adjusted_rank(manifest_row, source_row, hits)
    bbox_hits = bbox_overlap_hits(hits, manifest_row)
    exact_hits = exact_bbox_hits(hits, manifest_row)
    return {
        "query_id": manifest_row.get("query_id"),
        "bucket": manifest_row.get("bucket"),
        "query": manifest_row.get("query"),
        "pdf_review_label": manifest_row.get("pdf_review_label"),
        "pdf_match_policy": policy,
        "review_decision": decision,
        "positive_metric_eligible": eligible,
        "expected_file_name": manifest_row.get("expected_file_name"),
        "expected_document_version_id": manifest_row.get("expected_document_version_id"),
        "expected_page_no": manifest_row.get("expected_page_no"),
        "expected_physical_page_index": manifest_row.get("expected_physical_page_index"),
        "expected_bbox_present": bool(clean(manifest_row.get("expected_bbox"))),
        "raw_hit_rank": source_row.get("hit_rank"),
        "raw_location_rank": source_row.get("location_rank"),
        "raw_location_match": bool(source_row.get("location_match")),
        "raw_failure_reason": source_row.get("failure_reason"),
        "policy_adjusted_location_rank": policy_rank if eligible else None,
        "policy_adjusted_location_success": bool(policy_rank) if eligible else False,
        "pdf_file_hit_at_10": any(
            hit_file_match(hit, expected_file(manifest_row)) for hit in hits
        ),
        "pdf_page_hit_at_10": any(
            hit_file_match(hit, expected_file(manifest_row)) and hit_page_match(hit, manifest_row)
            for hit in hits
        ),
        "pdf_bbox_overlap_at_10": bool(bbox_hits),
        "pdf_exact_bbox_at_10": bool(exact_hits),
        "page_with_optional_bbox_success": decision == "ACCEPT_PAGE_WITH_OPTIONAL_BBOX" and bool(policy_rank),
        "same_page_paragraph_success": decision == "ACCEPT_CHUNK_TYPE_POLICY_RELABEL" and bool(policy_rank),
        "top10_hit_summary": [summarize_top_hit(hit) for hit in hits[:10]],
        "source_query_result_missing": False,
    }


def policy_adjusted_rank(
    manifest_row: Mapping[str, str],
    source_row: Mapping[str, Any],
    hits: list[Mapping[str, Any]],
) -> int | None:
    decision = clean(manifest_row.get("review_decision"))
    if decision == "ACCEPT_PAGE_WITH_OPTIONAL_BBOX":
        return first_rank(hits, manifest_row, require_page_chunk=True)
    if decision == "ACCEPT_CHUNK_TYPE_POLICY_RELABEL":
        return first_rank(hits, manifest_row, require_paragraph=True, allow_chunk_mismatch=True)
    if bool(source_row.get("location_match")):
        return int(source_row.get("location_rank") or source_row.get("hit_rank") or 0) or None
    return None


def first_rank(
    hits: list[Mapping[str, Any]],
    manifest_row: Mapping[str, str],
    *,
    require_page_chunk: bool = False,
    require_paragraph: bool = False,
    allow_chunk_mismatch: bool = False,
) -> int | None:
    expected_name = expected_file(manifest_row)
    expected_document_version_id = expected_docv(manifest_row)
    for hit in hits:
        br = match_breakdown(hit)
        chunk_type = clean(hit.get("chunk_type")).lower()
        if require_page_chunk and chunk_type != "page":
            continue
        if require_paragraph and chunk_type != "paragraph":
            continue
        if not hit_file_match(hit, expected_name):
            continue
        if not hit_docv_match(hit, expected_document_version_id):
            continue
        if not hit_page_match(hit, manifest_row):
            continue
        if not allow_chunk_mismatch and br.get("indexing_contract_match") is False:
            continue
        rank = hit_rank(hit)
        if rank is not None:
            return rank
    return None


def bbox_overlap_hits(hits: list[Mapping[str, Any]], manifest_row: Mapping[str, str]) -> list[Mapping[str, Any]]:
    expected_name = expected_file(manifest_row)
    return [
        hit for hit in hits
        if hit_file_match(hit, expected_name)
        and hit_page_match(hit, manifest_row)
        and bool(match_breakdown(hit).get("pdf_bbox_overlap"))
    ]


def exact_bbox_hits(hits: list[Mapping[str, Any]], manifest_row: Mapping[str, str]) -> list[Mapping[str, Any]]:
    expected_name = expected_file(manifest_row)
    return [
        hit for hit in hits
        if hit_file_match(hit, expected_name)
        and hit_page_match(hit, manifest_row)
        and bool(match_breakdown(hit).get("pdf_exact_bbox"))
    ]


def validate_inputs(
    *,
    reviewed_manifest_rows: list[dict[str, str]],
    policy_overlay: Mapping[str, Any],
    source_eval_report: Mapping[str, Any],
    artifact: Mapping[str, Any],
    index_version: str,
    blockers: list[str],
) -> None:
    if source_eval_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"source C5 eval report must be PASS or PASS_WITH_WARNINGS; got {source_eval_report.get('status')}")
    if source_eval_report.get("promotion_evidence") is not False:
        blockers.append("source C5 eval report must keep promotion_evidence=false")
    if source_eval_report.get("evidence_role") != EVIDENCE_ROLE:
        blockers.append("source C5 eval report must keep evidence_role=diagnostic")
    if source_eval_report.get("retrieval_backend") != "vector":
        blockers.append("source C5 eval report must use vector retrieval_backend")
    if source_eval_report.get("index_version") != index_version:
        blockers.append("source C5 index_version must match requested index version")
    if policy_overlay.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"policy overlay must be PASS or PASS_WITH_WARNINGS; got {policy_overlay.get('status')}")
    if policy_overlay.get("promotion_evidence") is not False:
        blockers.append("policy overlay must keep promotion_evidence=false")
    if policy_overlay.get("evidence_role") != EVIDENCE_ROLE:
        blockers.append("policy overlay must keep evidence_role=diagnostic")
    if policy_overlay.get("blockers"):
        blockers.append("policy overlay blockers must be empty")
    if int(policy_overlay.get("unresolved_candidate_count") or 0) != 0:
        blockers.append("policy overlay unresolved_candidate_count must be 0")
    blockers.extend(artifact_blockers(artifact=artifact, index_version=index_version))
    table_rows = [
        row for row in reviewed_manifest_rows
        if clean(row.get("pdf_review_label")) == "table_deferred"
    ]
    if any(bool_cell(row.get("positive_metric_eligible")) for row in table_rows):
        blockers.append("table_deferred rows must be excluded from positive metrics")


def artifact_contract(path: Path, index_version: str) -> dict[str, Any]:
    build_path = path / "build.json"
    manifest_path = path / "ingest_manifest.json"
    faiss_path = path / "faiss.index"
    return {
        "path": str(path),
        "exists": path.exists() and path.is_dir(),
        "expected_index_version": index_version,
        "build_json_exists": build_path.exists(),
        "build_json_sha256": file_sha256(build_path) if build_path.exists() else None,
        "build_json": read_json(build_path) if build_path.exists() else {},
        "ingest_manifest_json_exists": manifest_path.exists(),
        "ingest_manifest_json_sha256": file_sha256(manifest_path) if manifest_path.exists() else None,
        "ingest_manifest_json": read_json(manifest_path) if manifest_path.exists() else {},
        "faiss_index_exists": faiss_path.exists(),
        "faiss_index_sha256": file_sha256(faiss_path) if faiss_path.exists() else None,
    }


def artifact_blockers(*, artifact: Mapping[str, Any], index_version: str) -> list[str]:
    blockers: list[str] = []
    if not artifact.get("exists"):
        return [f"PDF candidate artifact dir is missing: {artifact.get('path')}"]
    if not artifact.get("build_json_exists"):
        blockers.append("PDF candidate artifact build.json is missing")
    if not artifact.get("ingest_manifest_json_exists"):
        blockers.append("PDF candidate artifact ingest_manifest.json is missing")
    if not artifact.get("faiss_index_exists"):
        blockers.append("PDF candidate artifact faiss.index is missing")
    build = artifact.get("build_json") if isinstance(artifact.get("build_json"), Mapping) else {}
    manifest = artifact.get("ingest_manifest_json") if isinstance(artifact.get("ingest_manifest_json"), Mapping) else {}
    if build and build.get("index_version") != index_version:
        blockers.append("PDF candidate artifact build.json index_version must match requested index version")
    if manifest and manifest.get("index_version") != index_version:
        blockers.append("PDF candidate artifact ingest_manifest.json index_version must match requested index version")
    return blockers


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-manifest", default=str(DEFAULT_REVIEWED_MANIFEST))
    parser.add_argument("--policy-overlay", default=str(DEFAULT_POLICY_OVERLAY))
    parser.add_argument("--source-eval-report", default=str(DEFAULT_SOURCE_EVAL_REPORT))
    parser.add_argument("--artifact-dir", default=PDF_ARTIFACT_DIR)
    parser.add_argument("--index-version", default=PDF_CANDIDATE_NAMESPACE)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
