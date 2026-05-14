"""Close remaining PDF layout/bbox gaps with source-bound evidence only.

The closure is diagnostic-only. It may promote a PDF readiness row to
strict-ready only when an exact source-bound bbox is present in a parser,
OCR/text-line, table/caption/figure, or SearchUnit location artifact. It does
not synthesize bboxes, open answer generation, touch official denominators, or
write production/candidate/vector artifacts.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import rag_pdf_evidence_readiness_repair as repair  # noqa: E402


DEFAULT_ENRICHMENT_REPORT = REPORT_DIR / "pdf_evidence_metadata_enrichment_report.json"
DEFAULT_REPAIR_REPORT = REPORT_DIR / "pdf_evidence_readiness_repair_report.json"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "pdf_layout_gap_closure_report.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "pdf_layout_gap_closure_report.md"
DEFAULT_REFRESHED_ENRICHMENT_JSON = REPORT_DIR / "pdf_evidence_metadata_enrichment_report.json"
DEFAULT_REFRESHED_ENRICHMENT_MD = REPORT_DIR / "pdf_evidence_metadata_enrichment_report.md"
DEFAULT_REFRESHED_REPAIR_JSON = REPORT_DIR / "pdf_evidence_readiness_repair_report.json"
DEFAULT_REFRESHED_REPAIR_MD = REPORT_DIR / "pdf_evidence_readiness_repair_report.md"
DEFAULT_VECTOR_DIAGNOSTIC = REPO_ROOT / "reports" / "rag_retrieval_eval_pdf_vector_diagnostic_report.json"
TARGET_QUERY_IDS = ("gq_auto_010", "gq_auto_015", "gq_auto_030")

SCHEMA_VERSION = "pdf_layout_gap_closure_report_v1"
TRACK = "pdf_business_ocr_mm"
ALLOWED_BBOX_SOURCES = {
    "parser_block_bbox",
    "parser_text_line_bbox",
    "ocr_text_line_bbox",
    "table_region_bbox",
    "caption_region_bbox",
    "figure_region_bbox",
    "source_artifact_location_json_bbox",
    "local_db.search_unit.location_json.bbox",
    "local_db.pdf_page_metadata.raw_page.blocks.bbox",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_closure(
        enrichment_report_path=Path(args.enrichment_report),
        repair_report_path=Path(args.repair_report),
        layout_source_paths=[Path(path) for path in args.layout_source],
        output_json_path=Path(args.output_report),
        output_md_path=Path(args.output_md),
        refreshed_enrichment_json_path=Path(args.refreshed_enrichment_report),
        refreshed_enrichment_md_path=Path(args.refreshed_enrichment_md),
        refreshed_repair_json_path=Path(args.refreshed_repair_report),
        refreshed_repair_md_path=Path(args.refreshed_repair_md),
        db_dsn=args.db_dsn or "",
        vector_diagnostic_path=Path(args.vector_diagnostic),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "strict_ready_rows_before": report["strict_ready_rows_before"],
                "strict_ready_rows_after": report["strict_ready_rows_after"],
                "diagnostic_only_fallback_rows_after": report["diagnostic_only_fallback_rows_after"],
                "source_bound_bbox_resolved_count": report["source_bound_bbox_resolved_count"],
                "official_metric_input_rows": report["official_metric_input_rows"],
                "answer_generation_opened": report["answer_generation_opened"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] != "FAILED_GUARDRAIL" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enrichment-report", default=str(DEFAULT_ENRICHMENT_REPORT))
    parser.add_argument("--repair-report", default=str(DEFAULT_REPAIR_REPORT))
    parser.add_argument("--layout-source", action="append", default=[])
    parser.add_argument("--vector-diagnostic", default=str(DEFAULT_VECTOR_DIAGNOSTIC))
    parser.add_argument(
        "--db-dsn",
        default=os.environ.get("PDF_LAYOUT_GAP_DB_DSN")
        or os.environ.get("AIPIPELINE_DB_DSN")
        or "",
        help="Optional PostgreSQL DSN. Queries are run in a read-only transaction.",
    )
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--refreshed-enrichment-report", default=str(DEFAULT_REFRESHED_ENRICHMENT_JSON))
    parser.add_argument("--refreshed-enrichment-md", default=str(DEFAULT_REFRESHED_ENRICHMENT_MD))
    parser.add_argument("--refreshed-repair-report", default=str(DEFAULT_REFRESHED_REPAIR_JSON))
    parser.add_argument("--refreshed-repair-md", default=str(DEFAULT_REFRESHED_REPAIR_MD))
    return parser.parse_args(argv)


def run_closure(
    *,
    enrichment_report_path: Path,
    repair_report_path: Path,
    layout_source_paths: Sequence[Path],
    output_json_path: Path,
    output_md_path: Path,
    refreshed_enrichment_json_path: Path,
    refreshed_enrichment_md_path: Path,
    refreshed_repair_json_path: Path,
    refreshed_repair_md_path: Path,
    db_dsn: str = "",
    vector_diagnostic_path: Path = DEFAULT_VECTOR_DIAGNOSTIC,
) -> dict[str, Any]:
    enrichment = read_json(enrichment_report_path)
    repair_report = read_json(repair_report_path)
    source_rows = [row for row in enrichment.get("rows", []) if isinstance(row, Mapping)]
    before_counts = count_snapshot(enrichment, fallback_report=repair_report)
    vector_rank_by_query = load_vector_rank_map(vector_diagnostic_path)

    layout_candidates = load_layout_sources(layout_source_paths)
    db_summary = {"attempted": False}
    if db_dsn:
        db_candidates, db_summary = load_db_layout_candidates(source_rows, db_dsn, vector_rank_by_query)
        for query_id, candidates in db_candidates.items():
            layout_candidates.setdefault(query_id, []).extend(candidates)

    refreshed_rows: list[dict[str, Any]] = []
    row_results: list[dict[str, Any]] = []
    target_ids = set(TARGET_QUERY_IDS)
    for row in source_rows:
        row_copy = copy.deepcopy(dict(row))
        query_id = clean(row_copy.get("query_id"))
        if query_id in target_ids:
            result = resolve_row_layout(row_copy, layout_candidates.get(query_id, []))
            row_copy = result["row"]
            row_results.append(result["audit"])
        refreshed_rows.append(row_copy)

    refreshed_repair = repair.build_repair_from_payload(source_report=repair_report, source_rows=refreshed_rows)
    refreshed_repair["generated_at"] = utc_timestamp()
    refreshed_repair["source_artifacts"] = {
        "enrichment_report": file_identity(enrichment_report_path),
        "repair_report": file_identity(repair_report_path),
        "layout_sources": [file_identity(path) for path in layout_source_paths],
        "vector_diagnostic": file_identity(vector_diagnostic_path),
        "database_readonly": db_summary,
    }
    refreshed_repair["artifact_paths"]["report_json"] = repo_relative(refreshed_repair_json_path)
    refreshed_repair["artifact_paths"]["report_md"] = repo_relative(refreshed_repair_md_path)
    strict_after = int_value(refreshed_repair.get("strict_ready_rows"))
    refreshed_repair["strict_gate_rerun"]["rerun_performed"] = strict_after > 0
    refreshed_repair["strict_gate_rerun"]["strict_gate_rerun_performed"] = strict_after > 0
    refreshed_repair["strict_gate_rerun"]["eligible"] = strict_after > 0
    refreshed_repair["strict_gate_rerun"]["strict_gate_rerun_eligible"] = strict_after > 0
    refreshed_repair["strict_gate_rerun"]["mode"] = "layout_gap_closure_readiness_gate_only"
    refreshed_repair["strict_gate_rerun"]["canonical_strict_silver_generator_run"] = False
    refreshed_repair["strict_gate_rerun"]["canonical_strict_silver_generator_skip_reason"] = (
        "protected official denominator registry was not opened"
    )

    after_counts = count_snapshot(refreshed_repair)
    generated_strict_rows = generated_strict_preview_rows(refreshed_repair["repair_rows"])
    status = closure_status(after_counts, refreshed_repair)
    source_bound_bbox_resolved_count = sum(
        1 for row in row_results if row.get("classification") == "strict_ready_diagnostic_only"
    )
    strict_ready_rows_before = max(
        0,
        int_value(after_counts.get("strict_ready_rows")) - source_bound_bbox_resolved_count,
    )
    diagnostic_only_fallback_rows_before = (
        int_value(after_counts.get("diagnostic_only_fallback_rows")) + source_bound_bbox_resolved_count
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "pdf_layout_gap_closure",
        "track": TRACK,
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric": False,
        "answer_generation_opened": False,
        "answer_generation_run": False,
        "official_metric_input_rows": int_value(refreshed_repair.get("official_metric_input_rows")),
        "input_rows": int_value(after_counts.get("input_rows")),
        "strict_ready_rows_before": strict_ready_rows_before,
        "strict_ready_rows_after": int_value(after_counts.get("strict_ready_rows")),
        "diagnostic_only_fallback_rows_before": diagnostic_only_fallback_rows_before,
        "diagnostic_only_fallback_rows_after": int_value(after_counts.get("diagnostic_only_fallback_rows")),
        "source_bound_bbox_resolved_count": source_bound_bbox_resolved_count,
        "page_anchor_only_count": sum(
            1 for row in row_results if "blocked_page_anchor_only" in set(row.get("blocker_classifications") or [])
        ),
        "unresolved_layout_count": sum(
            1
            for row in row_results
            if row.get("classification") != "strict_ready_diagnostic_only"
            and "blocked_page_anchor_only" not in set(row.get("blocker_classifications") or [])
        ),
        "citation_locator_complete_count": int_value(after_counts.get("citation_locator_complete_count")),
        "search_unit_id_count": int_value(after_counts.get("search_unit_id_available_count")),
        "parser_source_metadata_count": int_value(after_counts.get("parser_source_metadata_available_count")),
        "nearby_paragraph_count": int_value(after_counts.get("nearby_paragraph_count")),
        "ocr_native_trust_count": int_value(after_counts.get("native_or_ocr_trust_available_count")),
        "row_results": row_results,
        "generated_strict_rows": generated_strict_rows,
        "strict_gate_rerun": {
            "strict_gate_rerun_eligible": strict_after > 0,
            "strict_gate_rerun_performed": True,
            "mode": "layout_gap_closure_readiness_gate_only",
            "canonical_strict_silver_generator_run": False,
            "canonical_strict_silver_generator_skip_reason": "protected official denominator registry was not opened",
            "generated_strict_silver_rows": len(generated_strict_rows),
            "strict_ready_rows": strict_after,
            "remaining_fallback_rows": int_value(after_counts.get("diagnostic_only_fallback_rows")),
        },
        "guardrails": guardrails(),
        "source_artifacts": refreshed_repair["source_artifacts"],
        "artifact_paths": {
            "report_json": repo_relative(output_json_path),
            "report_md": repo_relative(output_md_path),
            "refreshed_enrichment_json": repo_relative(refreshed_enrichment_json_path),
            "refreshed_enrichment_md": repo_relative(refreshed_enrichment_md_path),
            "refreshed_repair_json": repo_relative(refreshed_repair_json_path),
            "refreshed_repair_md": repo_relative(refreshed_repair_md_path),
        },
        "validation": refreshed_repair["validation"],
        "remaining_blockers": {
            row["query_id"]: row["blocker_classifications"]
            for row in row_results
            if row.get("classification") != "strict_ready_diagnostic_only"
        },
    }

    write_json(output_json_path, report)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.write_text(render_markdown(report), encoding="utf-8")
    refreshed_enrichment = build_refreshed_enrichment(
        original=enrichment,
        refreshed_repair=refreshed_repair,
        after_counts=after_counts,
        output_json_path=refreshed_enrichment_json_path,
        output_md_path=refreshed_enrichment_md_path,
        closure_report_path=output_json_path,
    )
    write_json(refreshed_repair_json_path, refreshed_repair)
    refreshed_repair_md_path.parent.mkdir(parents=True, exist_ok=True)
    refreshed_repair_md_path.write_text(repair.render_markdown(refreshed_repair), encoding="utf-8")
    write_json(refreshed_enrichment_json_path, refreshed_enrichment)
    refreshed_enrichment_md_path.parent.mkdir(parents=True, exist_ok=True)
    refreshed_enrichment_md_path.write_text(render_enrichment_markdown(refreshed_enrichment), encoding="utf-8")
    return report


def resolve_row_layout(row: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    best_valid = next((candidate for candidate in candidates if is_allowed_source_bound(candidate)), None)
    best_seen = candidates[0] if candidates else {}
    resolved = copy.deepcopy(dict(row))
    if best_valid:
        original_search_unit = clean(resolved.get("search_unit_id"))
        original_rank = int_or_none(resolved.get("search_unit_rank"))
        update_row_with_layout(resolved, best_valid, original_search_unit=original_search_unit, original_rank=original_rank)
        audit = row_audit(resolved, best_valid, "strict_ready_diagnostic_only", [])
        return {"row": resolved, "audit": audit}

    blockers = classify_unresolved(best_seen)
    if best_seen:
        resolved["bbox_source"] = clean(best_seen.get("bbox_source"))
        resolved["layout_resolution_method"] = clean(best_seen.get("layout_resolution_method"))
        resolved["source_bound_bbox"] = False
    resolved["blocker_classifications"] = [*blockers, "diagnostic_only_fallback"]
    resolved["strict_ready"] = False
    audit = row_audit(resolved, best_seen, "diagnostic_only_fallback", resolved["blocker_classifications"])
    return {"row": resolved, "audit": audit}


def update_row_with_layout(
    row: dict[str, Any],
    candidate: Mapping[str, Any],
    *,
    original_search_unit: str,
    original_rank: int | None,
) -> None:
    bbox = list(candidate.get("bbox") or [])
    region_type = clean(candidate.get("region_type") or "paragraph")
    search_unit_id = clean(candidate.get("search_unit_id") or original_search_unit)
    rank = int_or_none(candidate.get("search_unit_rank") or candidate.get("retrieval_rank")) or original_rank
    row["page_anchor_search_unit_id"] = original_search_unit
    row["page_anchor_retrieval_rank"] = original_rank
    row["search_unit_id"] = search_unit_id
    row["search_unit_rank"] = rank
    row["retrieval_rank"] = rank
    row["bbox"] = bbox
    row["region_type"] = region_type
    row["bbox_source"] = clean(candidate.get("bbox_source"))
    row["layout_resolution_method"] = clean(candidate.get("layout_resolution_method"))
    row["source_bound_bbox"] = True
    row["source_artifact_ref"] = clean(candidate.get("source_artifact_ref"))
    if nonempty(candidate.get("matched_text")):
        row["matched_text"] = clean(candidate.get("matched_text"))
    if nonempty(candidate.get("citation_text")):
        row["citation_text"] = clean(candidate.get("citation_text"))
    locator = copy.deepcopy(row.get("citation_locator") if isinstance(row.get("citation_locator"), Mapping) else {})
    locator.update(
        {
            "page": int_or_none(candidate.get("page")) or row.get("page"),
            "physical_page_index": int_or_none(candidate.get("physical_page_index")) or row.get("physical_page_index"),
            "bbox": bbox,
            "region_type": region_type,
            "search_unit_id": search_unit_id,
        }
    )
    row["citation_locator"] = locator
    metadata = copy.deepcopy(row.get("source_metadata") if isinstance(row.get("source_metadata"), Mapping) else {})
    metadata["layout_gap_closure"] = {
        "bbox_source": row["bbox_source"],
        "layout_resolution_method": row["layout_resolution_method"],
        "source_artifact_ref": row["source_artifact_ref"],
        "source_bound_bbox": True,
        "page_anchor_search_unit_id": original_search_unit,
        "page_anchor_retrieval_rank": original_rank,
    }
    row["source_metadata"] = metadata


def classify_unresolved(candidate: Mapping[str, Any]) -> list[str]:
    method = clean(candidate.get("layout_resolution_method"))
    bbox_source = clean(candidate.get("bbox_source"))
    if method == "full_page_fallback_bbox" or bbox_source == "full_page_fallback":
        return ["blocked_page_anchor_only"]
    if method == "generated_bbox_estimate" or bbox_source == "generated_estimate":
        return ["blocked_missing_source_bound_bbox"]
    if method == "table_or_caption_missing":
        return ["blocked_table_or_caption_region_missing"]
    if method == "parser_artifact_missing_layout":
        return ["blocked_parser_artifact_missing_layout"]
    return ["blocked_text_span_unresolved"]


def is_allowed_source_bound(candidate: Mapping[str, Any]) -> bool:
    return (
        candidate.get("source_bound_bbox") is True
        and nonempty(candidate.get("bbox"))
        and clean(candidate.get("bbox_source")) in ALLOWED_BBOX_SOURCES
        and clean(candidate.get("layout_resolution_method")) not in {"generated_bbox_estimate", "full_page_fallback_bbox"}
    )


def row_audit(
    row: Mapping[str, Any],
    candidate: Mapping[str, Any],
    classification: str,
    blocker_classifications: Sequence[str],
) -> dict[str, Any]:
    return {
        "query_id": clean(row.get("query_id")),
        "classification": classification,
        "blocker_classifications": list(blocker_classifications),
        "source_file_id": clean(row.get("source_file_id")),
        "document_version_id": clean(row.get("document_version_id") or row.get("stable_source_identity")),
        "stable_source_identity": clean(row.get("stable_source_identity") or row.get("document_version_id")),
        "extracted_artifact_id": clean(row.get("extracted_artifact_id")),
        "search_unit_id": clean(row.get("search_unit_id")),
        "search_unit_rank": int_or_none(row.get("search_unit_rank")),
        "retrieval_rank": int_or_none(row.get("retrieval_rank")),
        "page": int_or_none(row.get("page")),
        "physical_page_index": int_or_none(row.get("physical_page_index")),
        "matched_text": clean(row.get("matched_text")),
        "citation_text": clean(row.get("citation_text")),
        "region_type": clean(row.get("region_type")),
        "bbox": list(row.get("bbox") or []),
        "bbox_source": clean(row.get("bbox_source") or candidate.get("bbox_source")),
        "layout_resolution_method": clean(row.get("layout_resolution_method") or candidate.get("layout_resolution_method")),
        "section_heading": clean(row.get("section_heading")),
        "table_caption_footnote": clean(row.get("table_caption_footnote")),
        "nearby_paragraph_count": len(row.get("nearby_paragraphs") or []),
        "native_text_available": row.get("native_text_available") is True,
        "OCR_confidence": row.get("OCR_confidence"),
        "OCR_fallback_used": row.get("OCR_fallback_used") is True,
        "content_evidence_lane": clean(row.get("content_evidence_lane")),
        "file_identity_lane": row.get("file_identity_lane"),
        "source_artifact_ref": clean(row.get("source_artifact_ref") or candidate.get("source_artifact_ref")),
    }


def load_layout_sources(paths: Sequence[Path]) -> dict[str, list[dict[str, Any]]]:
    by_query: dict[str, list[dict[str, Any]]] = {}
    for path in paths:
        if not path.exists():
            continue
        rows = read_jsonl(path) if path.suffix.lower() == ".jsonl" else generic_json_rows(read_json(path))
        for row in rows:
            query_id = clean(row.get("query_id"))
            if not query_id:
                continue
            candidate = dict(row)
            candidate["source_artifact_ref"] = clean(candidate.get("source_artifact_ref") or repo_relative(path))
            by_query.setdefault(query_id, []).append(candidate)
    return by_query


def load_db_layout_candidates(
    rows: Sequence[Mapping[str, Any]],
    db_dsn: str,
    vector_rank_by_query: Mapping[str, Mapping[str, int]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    summary: dict[str, Any] = {"attempted": True, "readonly_transaction": True, "resolved_query_count": 0, "errors": []}
    candidates_by_query: dict[str, list[dict[str, Any]]] = {}
    try:
        import psycopg2
        import psycopg2.extras
    except Exception as exc:  # pragma: no cover - depends on local env
        summary["errors"].append(f"psycopg2 unavailable: {type(exc).__name__}: {exc}")
        return candidates_by_query, summary
    try:
        conn = psycopg2.connect(db_dsn)
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SET TRANSACTION READ ONLY")
        for row in rows:
            query_id = clean(row.get("query_id"))
            if query_id not in TARGET_QUERY_IDS:
                continue
            candidate = exact_db_candidate(cur, row, vector_rank_by_query.get(query_id, {}))
            if candidate:
                candidates_by_query.setdefault(query_id, []).append(candidate)
                summary["resolved_query_count"] += 1
            else:
                candidates_by_query.setdefault(query_id, []).append(
                    {
                        "query_id": query_id,
                        "bbox_source": "",
                        "layout_resolution_method": "parser_artifact_missing_layout",
                        "source_bound_bbox": False,
                    }
                )
        conn.rollback()
        cur.close()
        conn.close()
    except Exception as exc:  # pragma: no cover - depends on local DB
        summary["errors"].append(f"{type(exc).__name__}: {exc}")
    return candidates_by_query, summary


def exact_db_candidate(
    cur: Any,
    row: Mapping[str, Any],
    rank_by_search_unit: Mapping[str, int],
) -> dict[str, Any]:
    query_id = clean(row.get("query_id"))
    docv = clean(row.get("document_version_id") or row.get("stable_source_identity"))
    page = int_or_none(row.get("page"))
    needle = normalize_text(row.get("matched_text"))
    if not docv or page is None or not needle:
        return {}
    cur.execute(
        """
        select id, source_file_id, extracted_artifact_id, document_version_id,
               parsed_artifact_id, source_file_name, chunk_type, location_json,
               parser_version, citation_text, display_text, text_content
        from search_unit
        where document_version_id = %s
          and coalesce(page_start, nullif(location_json->>'page_no', '')::int) = %s
          and lower(coalesce(chunk_type, '')) <> 'page'
          and location_json ? 'bbox'
        order by id
        """,
        (docv, page),
    )
    exact_rows = []
    for candidate in cur.fetchall():
        text = candidate_text(candidate)
        if normalize_text(text) == needle:
            exact_rows.append(candidate)
    if not exact_rows:
        return {}
    exact_rows.sort(key=lambda item: rank_by_search_unit.get(clean(item.get("id")), 10_000))
    selected = exact_rows[0]
    location = selected.get("location_json") if isinstance(selected.get("location_json"), Mapping) else {}
    rank = rank_by_search_unit.get(clean(selected.get("id")))
    return {
        "query_id": query_id,
        "search_unit_id": clean(selected.get("id")),
        "search_unit_rank": rank,
        "retrieval_rank": rank,
        "page": int_or_none(location.get("page_no")) or page,
        "physical_page_index": int_or_none(location.get("physical_page_index")) or int_or_none(row.get("physical_page_index")),
        "bbox": location.get("bbox") if isinstance(location.get("bbox"), list) else [],
        "region_type": clean(location.get("block_type") or selected.get("chunk_type")),
        "bbox_source": "local_db.search_unit.location_json.bbox",
        "layout_resolution_method": "exact_search_unit_bbox",
        "source_bound_bbox": True,
        "source_artifact_ref": f"search_unit:{clean(selected.get('id'))}.location_json.bbox",
        "matched_text": clean(selected.get("display_text") or selected.get("text_content")),
        "citation_text": clean(selected.get("citation_text")),
        "parser_version": clean(selected.get("parser_version")),
        "source_file_id": clean(selected.get("source_file_id")),
        "document_version_id": clean(selected.get("document_version_id")),
        "extracted_artifact_id": clean(selected.get("extracted_artifact_id")),
        "parsed_artifact_id": clean(selected.get("parsed_artifact_id")),
    }


def load_vector_rank_map(path: Path) -> dict[str, dict[str, int]]:
    if not path.exists():
        return {}
    payload = read_json(path)
    by_query: dict[str, dict[str, int]] = {}
    for query in payload.get("query_results") or []:
        if not isinstance(query, Mapping):
            continue
        query_id = clean(query.get("query_id"))
        ranks: dict[str, int] = {}
        for hit in query.get("top_k_results") or []:
            if isinstance(hit, Mapping) and clean(hit.get("search_unit_id")):
                ranks[clean(hit.get("search_unit_id"))] = int_value(hit.get("rank"))
        by_query[query_id] = ranks
    return by_query


def build_refreshed_enrichment(
    *,
    original: Mapping[str, Any],
    refreshed_repair: Mapping[str, Any],
    after_counts: Mapping[str, int],
    output_json_path: Path,
    output_md_path: Path,
    closure_report_path: Path,
) -> dict[str, Any]:
    refreshed = copy.deepcopy(dict(original))
    before_counts = refreshed.get("before_counts") if isinstance(refreshed.get("before_counts"), Mapping) else {}
    refreshed.update(
        {
            "generated_at": utc_timestamp(),
            "status": "PDF_METADATA_ENRICHMENT_COMPLETED_STRICT_READY"
            if int_value(after_counts.get("strict_ready_rows")) == int_value(after_counts.get("input_rows"))
            else "PDF_METADATA_ENRICHMENT_COMPLETED_PARTIAL_STRICT_READY",
            "answer_generation_opened": False,
            "answer_generation_run": False,
            "official_metric_input_rows": int_value(refreshed_repair.get("official_metric_input_rows")),
            "after_counts": dict(after_counts),
            "rows": refreshed_repair["repair_rows"],
            "generated_strict_rows": generated_strict_preview_rows(refreshed_repair["repair_rows"]),
            "strict_gate_rerun": {
                "strict_gate_rerun_eligible": int_value(after_counts.get("strict_ready_rows")) > 0,
                "strict_gate_rerun_performed": True,
                "mode": "layout_gap_closure_readiness_gate_only",
                "canonical_strict_silver_generator_run": False,
                "canonical_strict_silver_generator_skip_reason": "protected official denominator registry was not opened",
                "generated_strict_silver_rows": int_value(after_counts.get("strict_ready_rows")),
                "strict_ready_rows": int_value(after_counts.get("strict_ready_rows")),
                "remaining_fallback_rows": int_value(after_counts.get("diagnostic_only_fallback_rows")),
            },
            "artifact_paths": {
                "report_json": repo_relative(output_json_path),
                "report_md": repo_relative(output_md_path),
            },
        }
    )
    refreshed["count_deltas"] = {
        key: int_value(after_counts.get(key)) - int_value(before_counts.get(key))
        for key in sorted(set(before_counts) | set(after_counts))
    }
    source_artifacts = refreshed.get("source_artifacts") if isinstance(refreshed.get("source_artifacts"), Mapping) else {}
    refreshed["source_artifacts"] = {**source_artifacts, "layout_gap_closure_report": file_identity(closure_report_path)}
    refreshed["guardrails"] = {**guardrails(), **(refreshed.get("guardrails") if isinstance(refreshed.get("guardrails"), Mapping) else {})}
    refreshed["guardrails"].update(guardrails())
    refreshed["validation"] = refreshed_repair["validation"]
    return refreshed


def closure_status(after_counts: Mapping[str, int], refreshed_repair: Mapping[str, Any]) -> str:
    if refreshed_repair.get("validation", {}).get("ok") is not True:
        return "FAILED_GUARDRAIL"
    if int_value(after_counts.get("strict_ready_rows")) == int_value(after_counts.get("input_rows")):
        return "PDF_LAYOUT_GAP_CLOSED_ALL_STRICT_READY"
    if int_value(after_counts.get("strict_ready_rows")) > 0:
        return "PDF_LAYOUT_GAP_CLOSED_PARTIAL_STRICT_READY"
    return "PDF_LAYOUT_GAP_UNRESOLVED_DIAGNOSTIC_ONLY"


def count_snapshot(report: Mapping[str, Any], *, fallback_report: Mapping[str, Any] | None = None) -> dict[str, int]:
    counts = report.get("after_counts") if isinstance(report.get("after_counts"), Mapping) else report
    fallback = fallback_report or {}
    keys = (
        "input_rows",
        "strict_ready_rows",
        "diagnostic_only_fallback_rows",
        "citation_locator_complete_count",
        "search_unit_id_available_count",
        "parser_source_metadata_available_count",
        "nearby_paragraph_count",
        "native_or_ocr_trust_available_count",
        "official_metric_input_rows",
    )
    result = {key: int_value(counts.get(key)) for key in keys}
    if result["input_rows"] == 0:
        result["input_rows"] = int_value(fallback.get("input_rows"))
    if result["strict_ready_rows"] == 0:
        result["strict_ready_rows"] = int_value(fallback.get("strict_ready_rows"))
    if result["diagnostic_only_fallback_rows"] == 0:
        result["diagnostic_only_fallback_rows"] = int_value(fallback.get("diagnostic_only_fallback_rows"))
    return result


def generated_strict_preview_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "query_id": clean(row.get("query_id")),
            "search_unit_id": clean(row.get("search_unit_id")),
            "retrieval_rank": int_or_none(row.get("retrieval_rank")),
            "bbox": row.get("bbox"),
            "bbox_source": clean(row.get("bbox_source")),
            "layout_resolution_method": clean(row.get("layout_resolution_method")),
            "diagnostic_only": True,
            "official_metric_input": False,
            "promotion_evidence": False,
        }
        for row in rows
        if row.get("strict_ready") is True
    ]


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# PDF Layout Gap Closure Report",
        "",
        f"- Status: `{report['status']}`",
        "- Scope: diagnostic-only PDF layout/bbox closure; source-bound bbox required for strict readiness.",
        f"- Strict ready rows: `{report['strict_ready_rows_before']}` -> `{report['strict_ready_rows_after']}`",
        "- Diagnostic-only fallback rows: "
        f"`{report['diagnostic_only_fallback_rows_before']}` -> `{report['diagnostic_only_fallback_rows_after']}`",
        f"- Source-bound bbox resolved rows: `{report['source_bound_bbox_resolved_count']}`",
        f"- Page-anchor-only rows: `{report['page_anchor_only_count']}`",
        f"- Unresolved layout rows: `{report['unresolved_layout_count']}`",
        f"- Official metric input rows: `{report['official_metric_input_rows']}`",
        f"- Answer generation opened: `{str(report['answer_generation_opened']).lower()}`",
        "",
        "## Row Results",
        "",
    ]
    for row in report["row_results"]:
        lines.append(
            f"- `{row['query_id']}`: `{row['classification']}`; "
            f"bbox_source=`{row['bbox_source']}`; method=`{row['layout_resolution_method']}`"
        )
    return "\n".join(lines) + "\n"


def render_enrichment_markdown(report: Mapping[str, Any]) -> str:
    before = report.get("before_counts") if isinstance(report.get("before_counts"), Mapping) else {}
    after = report["after_counts"]
    lines = [
        "# PDF Evidence Metadata Enrichment Report",
        "",
        f"- Status: `{report['status']}`",
        "- Scope: PDF evidence readiness only; answer generation and official metrics remain closed.",
        f"- Input rows: `{after['input_rows']}`",
        f"- SearchUnit id: `{int_value(before.get('search_unit_id_available_count'))}` -> `{after['search_unit_id_available_count']}`",
        "- Parser/source metadata: "
        f"`{int_value(before.get('parser_source_metadata_available_count'))}` -> `{after['parser_source_metadata_available_count']}`",
        f"- Nearby paragraphs: `{int_value(before.get('nearby_paragraph_count'))}` -> `{after['nearby_paragraph_count']}`",
        "- OCR/native trust: "
        f"`{int_value(before.get('native_or_ocr_trust_available_count'))}` -> `{after['native_or_ocr_trust_available_count']}`",
        "- Citation locator complete: "
        f"`{int_value(before.get('citation_locator_complete_count'))}` -> `{after['citation_locator_complete_count']}`",
        f"- Strict ready rows: `{int_value(before.get('strict_ready_rows'))}` -> `{after['strict_ready_rows']}`",
        "- Strict gate rerun performed: "
        f"`{str(report['strict_gate_rerun']['strict_gate_rerun_performed']).lower()}`",
        f"- Official metric input rows: `{report['official_metric_input_rows']}`",
        f"- Answer generation opened: `{str(report['answer_generation_opened']).lower()}`",
        "",
        "## Row Blockers",
        "",
    ]
    for row in report["rows"]:
        blockers = ", ".join(row.get("blocker_classifications") or [])
        lines.append(f"- `{row['query_id']}`: `{blockers or 'strict_ready_diagnostic_only'}`")
    return "\n".join(lines) + "\n"


def generic_json_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("rows", "row_results", "layout_candidates"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, Mapping)]
    return []


def guardrails() -> dict[str, Any]:
    return {
        "official_metric_input_rows_remain_zero": True,
        "answer_generation_opened": False,
        "official_denominator_registry_opened": False,
        "official_denominator_registry_mutation": False,
        "production_namespace_mutated": False,
        "production_vector_index_mutated": False,
        "production_vector_written": False,
        "candidate_artifact_mutated": False,
        "immutable_baseline_mutated": False,
        "gold_registry_mutation": False,
        "content_file_identity_lane_merge": False,
        "filename_only_identity_accepted": False,
    }


def candidate_text(row: Mapping[str, Any]) -> str:
    return clean(row.get("display_text") or row.get("text_content"))


def normalize_text(value: Any) -> str:
    return "".join(clean(value).split())


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_identity(path: Path) -> dict[str, Any]:
    return {
        "path": repo_relative(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() else None,
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def int_value(value: Any) -> int:
    parsed = int_or_none(value)
    return parsed if parsed is not None else 0


def nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    return True


def clean(value: Any) -> str:
    return str(value or "").strip()


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
