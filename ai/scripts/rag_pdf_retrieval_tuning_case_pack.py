"""Create a diagnostic-only C8 case pack for reviewed PDF ranking failures.

This script packages remaining true retrieval/ranking failures for manual
case-level investigation. It does not tune retrieval, alter parser behavior,
run hybrid search/rerank, reindex, promote, or mutate baselines.
"""

from __future__ import annotations

import argparse
import re
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
    expected_docv,
    expected_file,
    hit_docv_match,
    hit_file_match,
    hit_page_match,
    location,
    match_breakdown,
    print_json,
    read_csv_rows,
    read_json,
    report_ref,
    summarize_top_hit,
    to_int,
    utc_run_id,
    utc_timestamp,
    write_json,
)


DEFAULT_AFTER_POLICY = Path("reports/rag_pdf_vector_quality_breakdown_after_policy.json")
DEFAULT_REVIEWED_DIAGNOSTIC = Path("reports/rag_retrieval_eval_pdf_v1_reviewed_vector_diagnostic_report.json")
DEFAULT_SOURCE_EVAL_REPORT = Path("reports/rag_retrieval_eval_pdf_vector_diagnostic_report.json")
DEFAULT_REVIEWED_MANIFEST = Path("eval/gold_queries_pdf_v1_reviewed.csv")
DEFAULT_C3_REPORT = Path("reports/rag_pdf_embedding_text_contract_audit.json")
DEFAULT_ARTIFACT_DIR = Path(PDF_ARTIFACT_DIR)
DEFAULT_OUTPUT = Path("reports/rag_pdf_retrieval_tuning_case_pack.json")

NEXT_ACTIONS = {
    "QUERY_SURFACE_REVIEW",
    "EMBEDDING_SURFACE_REVIEW",
    "PAGE_RANKING_INVESTIGATION",
    "FILE_RECALL_INVESTIGATION",
    "TABLE_EXTRACTION_DEFERRED",
    "GOLD_BINDING_REVIEW",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    after_path = Path(args.after_policy_breakdown)
    reviewed_path = Path(args.reviewed_diagnostic)
    source_path = Path(args.source_eval_report)
    manifest_path = Path(args.reviewed_manifest)
    c3_path = Path(args.c3_report)
    artifact_dir = Path(args.artifact_dir)
    payload = build_case_pack(
        after_policy_breakdown=read_json(after_path),
        reviewed_diagnostic=read_json(reviewed_path),
        source_eval_report=read_json(source_path),
        reviewed_manifest_rows=read_csv_rows(manifest_path),
        c3_report=read_json(c3_path),
        artifact_manifest=read_json(artifact_dir / "ingest_manifest.json") if (artifact_dir / "ingest_manifest.json").exists() else {},
        after_policy_path=after_path,
        reviewed_diagnostic_path=reviewed_path,
        source_eval_report_path=source_path,
        reviewed_manifest_path=manifest_path,
        c3_report_path=c3_path,
        artifact_dir=artifact_dir,
    )
    write_json(Path(args.output), payload)
    print_json(payload)
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def build_case_pack(
    *,
    after_policy_breakdown: Mapping[str, Any],
    reviewed_diagnostic: Mapping[str, Any],
    source_eval_report: Mapping[str, Any],
    reviewed_manifest_rows: list[dict[str, str]],
    c3_report: Mapping[str, Any],
    artifact_manifest: Mapping[str, Any],
    after_policy_path: Path,
    reviewed_diagnostic_path: Path,
    source_eval_report_path: Path,
    reviewed_manifest_path: Path,
    c3_report_path: Path,
    artifact_dir: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    validate_inputs(after_policy_breakdown, reviewed_diagnostic, source_eval_report, blockers)
    source_by_id = {
        clean(row.get("query_id")): row
        for row in source_eval_report.get("query_results") or []
        if isinstance(row, Mapping)
    }
    manifest_by_id = {clean(row.get("query_id")): row for row in reviewed_manifest_rows}
    failure_rows = [
        row for row in after_policy_breakdown.get("rows") or []
        if isinstance(row, Mapping) and row.get("true_retrieval_ranking_failure") is True
    ]
    cases = [
        build_case(
            after_row=row,
            source_row=source_by_id.get(clean(row.get("query_id")), {}),
            manifest_row=manifest_by_id.get(clean(row.get("query_id")), {}),
            c3_report=c3_report,
            artifact_manifest=artifact_manifest,
        )
        for row in failure_rows
    ]
    invalid_actions = [case for case in cases if case.get("next_action") not in NEXT_ACTIONS]
    if invalid_actions:
        blockers.append("all C8 cases must have a known next_action")
    if len(cases) != int(after_policy_breakdown.get("true_retrieval_ranking_failure_count") or 0):
        blockers.append("case count must match C6.1 true_retrieval_ranking_failure_count")
    status = "FAIL" if blockers else "PASS"
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C8",
        "report_role": "pdf_retrieval_tuning_case_pack",
        "promotion_evidence": False,
        "evidence_role": EVIDENCE_ROLE,
        "pdf_candidate_namespace": PDF_CANDIDATE_NAMESPACE,
        "pdf_artifact_dir": str(artifact_dir),
        "retrieval_tuning_executed": False,
        "retrieval_execution": "not_run_by_this_script",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "baseline_execution": "not_run_by_this_script",
        "gold_mutation_execution": "not_run_by_this_script",
        "immutable_baseline_changed": False,
        "xlsx_candidate_artifact_changed": False,
        "table_specific_retrieval_proven": False,
        "input_reports": {
            "after_policy_breakdown": report_ref(after_policy_breakdown, after_policy_path),
            "reviewed_diagnostic": report_ref(reviewed_diagnostic, reviewed_diagnostic_path),
            "source_c5_eval_report": report_ref(source_eval_report, source_eval_report_path),
            "reviewed_manifest": artifact_identity(reviewed_manifest_path),
            "c3_embedding_text_contract": report_ref(c3_report, c3_report_path),
            "artifact_manifest": artifact_identity(artifact_dir / "ingest_manifest.json"),
        },
        "case_count": len(cases),
        "true_retrieval_ranking_failure_count": len(cases),
        "next_action_counts": count_cases(cases, "next_action"),
        "cases": cases,
        "blockers": blockers,
        "warnings": warnings,
        "next_action": "Investigate these 7 cases individually before any broad retrieval tuning.",
        "notes": [
            "C8 case pack is diagnostic-only; retrieval tuning remains unexecuted.",
            "The case pack records evidence and next actions only.",
            "No hybrid search, reranker, parser expansion, reindexing, or promotion is run.",
        ],
    }


def build_case(
    *,
    after_row: Mapping[str, Any],
    source_row: Mapping[str, Any],
    manifest_row: Mapping[str, str],
    c3_report: Mapping[str, Any],
    artifact_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    hits = list(source_row.get("top_k_results") or [])
    expected_name = expected_file(manifest_row or after_row)
    expected_document_version_id = expected_docv(manifest_row or after_row)
    same_file_ranks = [
        hit.get("rank") for hit in hits
        if hit_file_match(hit, expected_name)
    ]
    same_page_ranks = [
        hit.get("rank") for hit in hits
        if hit_file_match(hit, expected_name)
        and hit_docv_match(hit, expected_document_version_id)
        and hit_page_match(hit, manifest_row or after_row)
    ]
    expected_file_absent = not same_file_ranks
    expected_page_absent = not same_page_ranks
    lexical = lexical_overlap(manifest_row)
    surface = embedding_surface_evidence(c3_report, artifact_manifest)
    top_hit = hits[0] if hits else {}
    next_action = choose_next_action(
        expected_file_absent=expected_file_absent,
        expected_page_absent=expected_page_absent,
        lexical_overlap_possible=bool(lexical["overlap_terms"]),
    )
    return {
        "query_id": after_row.get("query_id"),
        "query": after_row.get("query") or manifest_row.get("query"),
        "bucket": after_row.get("bucket") or manifest_row.get("bucket"),
        "expected_document_version_id": manifest_row.get("expected_document_version_id") or expected_document_version_id,
        "expected_page_no": manifest_row.get("expected_page_no"),
        "expected_physical_page_index": manifest_row.get("expected_physical_page_index"),
        "expected_bbox": manifest_row.get("expected_bbox"),
        "top10_hit_summary": [summarize_top_hit(hit) for hit in hits[:10]],
        "same_file_hit_ranks": same_file_ranks,
        "same_page_hit_ranks": same_page_ranks,
        "expected_file_absent": expected_file_absent,
        "expected_page_absent": expected_page_absent,
        "query_expected_page_text_lexical_overlap": lexical,
        "embedding_text_surface_evidence": surface,
        "top_ranked_wrong_page_evidence": wrong_page_evidence(top_hit, manifest_row),
        "next_action": next_action,
    }


def lexical_overlap(manifest_row: Mapping[str, str]) -> dict[str, Any]:
    query_terms = tokens(manifest_row.get("query"))
    expected_terms = tokens(
        " ".join([
            clean(manifest_row.get("expected_answer_text")),
            clean(manifest_row.get("must_contain_terms")).replace(";", " "),
        ])
    )
    overlap = sorted(query_terms & expected_terms)
    return {
        "expected_page_text_available": False,
        "expected_page_text_source": "not_available_in_c5_report_or_reviewed_manifest",
        "query_term_count": len(query_terms),
        "expected_term_count": len(expected_terms),
        "overlap_terms": overlap,
        "overlap_possible": bool(overlap),
        "note": "Uses query, expected_answer_text, and must_contain_terms as a proxy; full expected page text is not present.",
    }


def tokens(value: Any) -> set[str]:
    text = clean(value).lower()
    return {
        token for token in re.findall(r"[0-9a-zA-Z가-힣]+", text)
        if len(token) >= 2
    }


def embedding_surface_evidence(c3_report: Mapping[str, Any], artifact_manifest: Mapping[str, Any]) -> dict[str, Any]:
    summary = c3_report.get("summary") or {}
    contract = c3_report.get("embedding_text_contract") or {}
    samples = list(artifact_manifest.get("embed_text_samples") or [])
    sample_previews = [clean(sample.get("preview")) for sample in samples if isinstance(sample, Mapping)]
    return {
        "embedding_text_variant": artifact_manifest.get("embedding_text_variant"),
        "embedding_text_builder_version": artifact_manifest.get("embedding_text_builder_version"),
        "page_surface_present_count": contract.get("page_surface_present_count"),
        "missing_page_surface_in_embedding_text_count": summary.get("missing_page_surface_in_embedding_text_count"),
        "missing_section_surface_for_sectioned_rows": summary.get("missing_section_surface_for_sectioned_rows"),
        "artifact_samples_include_page_surface": any("Page:" in preview for preview in sample_previews),
        "artifact_samples_include_citation_surface": any("Citation:" in preview for preview in sample_previews),
        "per_failure_page_text_available": False,
        "note": "C3/manifest support page/citation surface globally; C5 top-k report does not include per-page embedding text.",
    }


def wrong_page_evidence(top_hit: Mapping[str, Any], manifest_row: Mapping[str, str]) -> dict[str, Any]:
    if not top_hit:
        return {"summary": "No top hit was returned."}
    loc = location(top_hit)
    expected_name = expected_file(manifest_row)
    expected_page_no = to_int(manifest_row.get("expected_page_no"))
    br = match_breakdown(top_hit)
    if not hit_file_match(top_hit, expected_name):
        summary = "Top hit is from a different PDF, so file recall/ranking is stronger than the expected file."
    elif expected_page_no is not None and to_int(loc.get("page_no")) != expected_page_no:
        summary = "Top hit is the expected file but a different page, so page ranking is the immediate issue."
    else:
        summary = "Top hit shares file/page evidence but still failed the reviewed location policy."
    return {
        "summary": summary,
        "rank": top_hit.get("rank"),
        "score": top_hit.get("score"),
        "source_file_name": top_hit.get("source_file_name"),
        "page_no": loc.get("page_no"),
        "page_label": loc.get("page_label"),
        "chunk_type": top_hit.get("chunk_type"),
        "file_match": br.get("file_match"),
        "document_version_match": br.get("document_version_match"),
        "pdf_page_match": br.get("pdf_page_match"),
        "citation_text": top_hit.get("citation_text"),
    }


def choose_next_action(
    *,
    expected_file_absent: bool,
    expected_page_absent: bool,
    lexical_overlap_possible: bool,
) -> str:
    if expected_file_absent:
        return "FILE_RECALL_INVESTIGATION"
    if expected_page_absent:
        return "PAGE_RANKING_INVESTIGATION"
    if not lexical_overlap_possible:
        return "QUERY_SURFACE_REVIEW"
    return "EMBEDDING_SURFACE_REVIEW"


def validate_inputs(
    after_policy_breakdown: Mapping[str, Any],
    reviewed_diagnostic: Mapping[str, Any],
    source_eval_report: Mapping[str, Any],
    blockers: list[str],
) -> None:
    if after_policy_breakdown.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append("C6.1 after-policy breakdown must pass before C8")
    if after_policy_breakdown.get("promotion_evidence") is not False:
        blockers.append("C6.1 after-policy breakdown must keep promotion_evidence=false")
    if reviewed_diagnostic.get("promotion_evidence") is not False:
        blockers.append("C5.1 reviewed diagnostic must keep promotion_evidence=false")
    if reviewed_diagnostic.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(
            f"C5.1 reviewed diagnostic must be PASS or PASS_WITH_WARNINGS; got {reviewed_diagnostic.get('status')}"
        )
    if reviewed_diagnostic.get("evidence_role") != EVIDENCE_ROLE:
        blockers.append("C5.1 reviewed diagnostic must keep evidence_role=diagnostic")
    if source_eval_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(
            f"source C5 eval report must be PASS or PASS_WITH_WARNINGS; got {source_eval_report.get('status')}"
        )
    if source_eval_report.get("promotion_evidence") is not False:
        blockers.append("source C5 eval report must keep promotion_evidence=false")
    if source_eval_report.get("evidence_role") != EVIDENCE_ROLE:
        blockers.append("source C5 eval report must keep evidence_role=diagnostic")
    if source_eval_report.get("retrieval_backend") != "vector":
        blockers.append("source C5 eval report must use vector retrieval_backend")
    if source_eval_report.get("index_version") != PDF_CANDIDATE_NAMESPACE:
        blockers.append("source C5 eval report index_version must match PDF candidate namespace")


def count_cases(cases: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        value = clean(case.get(key)) or "UNKNOWN"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after-policy-breakdown", default=str(DEFAULT_AFTER_POLICY))
    parser.add_argument("--reviewed-diagnostic", default=str(DEFAULT_REVIEWED_DIAGNOSTIC))
    parser.add_argument("--source-eval-report", default=str(DEFAULT_SOURCE_EVAL_REPORT))
    parser.add_argument("--reviewed-manifest", default=str(DEFAULT_REVIEWED_MANIFEST))
    parser.add_argument("--c3-report", default=str(DEFAULT_C3_REPORT))
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
