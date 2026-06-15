"""Enrich PDF evidence readiness rows with diagnostic provenance metadata.

This script is PDF-only and diagnostic-only. It reads active readiness rows,
repo-local diagnostic artifacts, and optionally the local database in a
read-only transaction. It does not open official metrics, official
denominators, answer generation, production indexes, candidate artifacts, or
gold registries.
"""

from __future__ import annotations

import argparse
import copy
import csv
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
REPORT_DIR = AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import rag_pdf_evidence_readiness_repair as repair  # noqa: E402


DEFAULT_READINESS_REPORT = REPORT_DIR / "pdf_evidence_readiness_report.json"
DEFAULT_READINESS_ROWS = REPORT_DIR / "pdf_evidence_readiness_rows.jsonl"
DEFAULT_OUTPUT_JSON = REPORT_DIR / "pdf_evidence_metadata_enrichment_report.json"
DEFAULT_OUTPUT_MD = REPORT_DIR / "pdf_evidence_metadata_enrichment_report.md"
DEFAULT_REPAIR_OUTPUT_JSON = REPORT_DIR / "pdf_evidence_readiness_repair_report.json"
DEFAULT_REPAIR_OUTPUT_MD = REPORT_DIR / "pdf_evidence_readiness_repair_report.md"
DEFAULT_METADATA_SOURCES = (
    REPO_ROOT / "reports" / "rag_retrieval_eval_pdf_vector_diagnostic_report.json",
    REPO_ROOT / "reports" / "pdf_candidate_embedding_consistency_report.json",
    REPO_ROOT / "reports" / "rag_pdf_vector_quality_breakdown_after_policy.json",
    REPO_ROOT / "rag-data-pdf-candidate-v1" / "ingest_manifest.json",
)

SCHEMA_VERSION = "pdf_evidence_metadata_enrichment_report_v1"
TRACK = "pdf_business_ocr_mm"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_enrichment(
        readiness_report_path=Path(args.readiness_report),
        readiness_rows_path=Path(args.readiness_rows),
        metadata_source_paths=[Path(path) for path in args.metadata_source],
        db_dsn=args.db_dsn or "",
        output_json_path=Path(args.output_report),
        output_md_path=Path(args.output_md),
        repair_output_json_path=Path(args.repair_output_report),
        repair_output_md_path=Path(args.repair_output_md),
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "report": report["artifact_paths"]["report_json"],
                "input_rows": report["after_counts"]["input_rows"],
                "search_unit_id_available_count": report["after_counts"]["search_unit_id_available_count"],
                "parser_source_metadata_available_count": report["after_counts"][
                    "parser_source_metadata_available_count"
                ],
                "strict_ready_rows": report["after_counts"]["strict_ready_rows"],
                "strict_gate_rerun_performed": report["strict_gate_rerun"]["strict_gate_rerun_performed"],
                "official_metric_input_rows": report["official_metric_input_rows"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] != "FAILED_GUARDRAIL" else 2


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness-report", default=str(DEFAULT_READINESS_REPORT))
    parser.add_argument("--readiness-rows", default=str(DEFAULT_READINESS_ROWS))
    parser.add_argument("--metadata-source", action="append", default=[str(path) for path in DEFAULT_METADATA_SOURCES])
    parser.add_argument(
        "--db-dsn",
        default=os.environ.get("PDF_METADATA_ENRICHMENT_DB_DSN")
        or os.environ.get("AIPIPELINE_DB_DSN")
        or "",
        help="Optional PostgreSQL DSN. Queries are run in a read-only transaction.",
    )
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--repair-output-report", default=str(DEFAULT_REPAIR_OUTPUT_JSON))
    parser.add_argument("--repair-output-md", default=str(DEFAULT_REPAIR_OUTPUT_MD))
    return parser.parse_args(argv)


def run_enrichment(
    *,
    readiness_report_path: Path,
    readiness_rows_path: Path,
    metadata_source_paths: Sequence[Path],
    output_json_path: Path,
    output_md_path: Path,
    repair_output_json_path: Path,
    repair_output_md_path: Path,
    db_dsn: str = "",
) -> dict[str, Any]:
    source_report = read_json(readiness_report_path)
    source_rows = read_jsonl(readiness_rows_path) if readiness_rows_path.exists() else []
    before_repair = repair.build_repair_from_payload(source_report=source_report, source_rows=source_rows)
    before_counts = count_snapshot(before_repair)

    target_query_ids = {clean(row.get("query_id")) for row in source_rows if clean(row.get("query_id"))}
    metadata_by_query, metadata_source_summaries = load_metadata_sources(metadata_source_paths)
    metadata_by_query = {
        query_id: metadata
        for query_id, metadata in metadata_by_query.items()
        if query_id in target_query_ids
    }
    db_summary = enrich_from_db(metadata_by_query, db_dsn) if db_dsn else {"attempted": False}
    enriched_rows = [merge_metadata(row, metadata_by_query.get(clean(row.get("query_id")), {})) for row in source_rows]
    repaired = repair.build_repair_from_payload(source_report=source_report, source_rows=enriched_rows)

    strict_ready_rows = int(repaired.get("strict_ready_rows") or 0)
    strict_gate_performed = strict_ready_rows > 0
    repaired["strict_gate_rerun"]["rerun_performed"] = strict_gate_performed
    repaired["strict_gate_rerun"]["strict_gate_rerun_performed"] = strict_gate_performed
    repaired["strict_gate_rerun"]["strict_gate_rerun_eligible"] = strict_ready_rows > 0
    repaired["strict_gate_rerun"]["eligible"] = strict_ready_rows > 0
    repaired["strict_gate_rerun"]["mode"] = "metadata_enrichment_readiness_gate_only"
    repaired["strict_gate_rerun"]["canonical_strict_silver_generator_run"] = False
    repaired["strict_gate_rerun"]["canonical_strict_silver_generator_skip_reason"] = (
        "canonical generator requires official_denominator_registry.json, which is protected for this task"
    )
    repaired["source_artifacts"] = {
        "readiness_report": file_identity(readiness_report_path),
        "readiness_rows": file_identity(readiness_rows_path),
        "metadata_sources": metadata_source_summaries,
        "database_readonly": db_summary,
    }
    repaired["artifact_paths"]["report_json"] = repo_relative(repair_output_json_path)
    repaired["artifact_paths"]["report_md"] = repo_relative(repair_output_md_path)

    generated_strict_rows = generated_strict_preview_rows(repaired["repair_rows"])
    after_counts = count_snapshot(repaired)
    status = "PDF_METADATA_ENRICHMENT_COMPLETED"
    if repaired["validation"]["ok"] is not True:
        status = "FAILED_GUARDRAIL"
    elif strict_ready_rows == 0:
        status = "PDF_METADATA_ENRICHMENT_COMPLETED_STRICT_GATE_NOT_ELIGIBLE"
    elif strict_ready_rows < int(after_counts.get("input_rows") or 0):
        status = "PDF_METADATA_ENRICHMENT_COMPLETED_PARTIAL_STRICT_READY"

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "pdf_evidence_metadata_enrichment",
        "track": TRACK,
        "diagnostic_only": True,
        "promotion_evidence": False,
        "official_metric": False,
        "answer_generation_opened": False,
        "answer_generation_run": False,
        "official_metric_input_rows": int(repaired.get("official_metric_input_rows") or 0),
        "before_counts": before_counts,
        "after_counts": after_counts,
        "count_deltas": {
            key: int(after_counts.get(key) or 0) - int(before_counts.get(key) or 0)
            for key in sorted(set(before_counts) | set(after_counts))
        },
        "rows": repaired["repair_rows"],
        "generated_strict_rows": generated_strict_rows,
        "strict_gate_rerun": {
            "strict_gate_rerun_eligible": strict_ready_rows > 0,
            "strict_gate_rerun_performed": strict_gate_performed,
            "mode": "metadata_enrichment_readiness_gate_only",
            "canonical_strict_silver_generator_run": False,
            "canonical_strict_silver_generator_skip_reason": (
                "protected official denominator registry was not opened"
            ),
            "generated_strict_silver_rows": len(generated_strict_rows),
            "strict_ready_rows": strict_ready_rows,
            "remaining_fallback_rows": int(repaired.get("diagnostic_only_fallback_rows") or 0),
            "blocker_reasons_by_row": {
                str(row.get("query_id")): list(row.get("blocker_classifications") or [])
                for row in repaired["repair_rows"]
                if row.get("strict_ready") is not True
            },
        },
        "guardrails": {
            "official_metric_input_rows_remain_zero": int(repaired.get("official_metric_input_rows") or 0) == 0,
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
        },
        "source_artifacts": repaired["source_artifacts"],
        "artifact_paths": {
            "report_json": repo_relative(output_json_path),
            "report_md": repo_relative(output_md_path),
            "repair_report_json": repo_relative(repair_output_json_path),
            "repair_report_md": repo_relative(repair_output_md_path),
        },
        "validation": repaired["validation"],
        "remaining_blockers": remaining_blockers(repaired["repair_rows"]),
    }

    write_json(repair_output_json_path, repaired)
    repair_output_md_path.parent.mkdir(parents=True, exist_ok=True)
    repair_output_md_path.write_text(repair.render_markdown(repaired), encoding="utf-8")
    write_json(output_json_path, report)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.write_text(render_markdown(report), encoding="utf-8")
    return report


def load_metadata_sources(paths: Sequence[Path]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    metadata_by_query: dict[str, dict[str, Any]] = {}
    docv_source_file: dict[str, str] = {}
    summaries: list[dict[str, Any]] = []
    for path in paths:
        summary = file_identity(path)
        summary["source_role"] = "metadata_source"
        if not path.exists():
            summary["resolved_row_count"] = 0
            summaries.append(summary)
            continue
        resolved = 0
        if path.suffix.lower() == ".jsonl":
            for row in read_jsonl(path):
                resolved += merge_query_metadata(metadata_by_query, normalise_generic_metadata(row, path))
        elif path.suffix.lower() == ".csv":
            for row in read_csv(path):
                resolved += merge_query_metadata(metadata_by_query, normalise_generic_metadata(row, path))
        elif path.suffix.lower() == ".json":
            payload = read_json(path)
            if isinstance(payload.get("query_results"), list):
                for row in vector_diagnostic_metadata(payload, path):
                    resolved += merge_query_metadata(metadata_by_query, row)
            if isinstance(payload.get("document_scope_details"), list):
                for item in payload["document_scope_details"]:
                    if not isinstance(item, Mapping):
                        continue
                    docv = clean(item.get("document_version_id"))
                    source_file_ids = item.get("source_file_ids") if isinstance(item.get("source_file_ids"), list) else []
                    if docv and source_file_ids:
                        docv_source_file[docv] = clean(source_file_ids[0])
            for row in generic_json_rows(payload):
                resolved += merge_query_metadata(metadata_by_query, normalise_generic_metadata(row, path))
        summary["resolved_row_count"] = resolved
        summaries.append(summary)

    for meta in metadata_by_query.values():
        docv = clean(meta.get("document_version_id"))
        if docv and not clean(meta.get("source_file_id")) and docv in docv_source_file:
            meta["source_file_id"] = docv_source_file[docv]
            add_field_source(meta, "source_file_id", "pdf_candidate_embedding_consistency_report")
    return metadata_by_query, summaries


def vector_diagnostic_metadata(payload: Mapping[str, Any], path: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for query_result in payload.get("query_results") or []:
        if not isinstance(query_result, Mapping):
            continue
        hit = select_vector_hit(query_result)
        if not hit:
            continue
        location = hit.get("location_json") if isinstance(hit.get("location_json"), Mapping) else {}
        match = hit.get("match_breakdown") if isinstance(hit.get("match_breakdown"), Mapping) else {}
        rank = int_value(hit.get("rank"))
        parser_version = clean(hit.get("parser_version"))
        source_metadata = {
            "metadata_source": repo_relative(path),
            "source_role": "vector_diagnostic_top_k_hit",
            "candidate_index_version": clean(query_result.get("candidate_index_version")),
            "hit_rank": int_value(query_result.get("hit_rank")),
            "location_rank": int_value(query_result.get("location_rank")),
            "retrieval_rank": rank,
            "match_breakdown": match,
            "parser_name": clean(hit.get("parser_name")),
            "parser_version": parser_version,
            "chunk_type": clean(hit.get("chunk_type")),
            "index_version": clean(hit.get("index_version")),
            "embedding_status": clean(hit.get("embedding_status")),
            "location_json": location,
        }
        results.append(
            with_field_sources(
                {
                    "query_id": clean(query_result.get("query_id")),
                    "search_unit_id": clean(hit.get("search_unit_id")),
                    "source_searchunit_id": clean(hit.get("search_unit_id")),
                    "search_unit_rank": rank,
                    "source_searchunit_rank": rank,
                    "retrieval_rank": rank,
                    "parser_version": parser_version,
                    "source_metadata": source_metadata,
                    "parser_source_metadata": source_metadata,
                    "document_version_id": clean(location.get("document_version_id")),
                    "page": int_or_none(location.get("page_no")),
                    "physical_page_index": int_or_none(location.get("physical_page_index")),
                    "bbox": location.get("bbox") if isinstance(location.get("bbox"), list) else [],
                    "region_type": clean(location.get("block_type") or hit.get("chunk_type") or location.get("type")),
                    "citation_text": clean(hit.get("citation_text")),
                    "OCR_confidence": location.get("ocr_confidence"),
                    "native_text_available": location.get("ocr_used") is False,
                    "OCR_fallback_used": location.get("ocr_used") is True,
                },
                repo_relative(path),
            )
        )
    return results


def select_vector_hit(query_result: Mapping[str, Any]) -> Mapping[str, Any]:
    hits = [hit for hit in query_result.get("top_k_results") or [] if isinstance(hit, Mapping)]
    if not hits:
        return {}
    hit_rank = int_value(query_result.get("hit_rank")) or int_value(query_result.get("location_rank"))
    if hit_rank:
        for hit in hits:
            if int_value(hit.get("rank")) == hit_rank:
                return hit
    for hit in hits:
        match = hit.get("match_breakdown") if isinstance(hit.get("match_breakdown"), Mapping) else {}
        if match.get("identity_match") is True:
            return hit
    for hit in hits:
        match = hit.get("match_breakdown") if isinstance(hit.get("match_breakdown"), Mapping) else {}
        if match.get("document_version_match") is True and match.get("pdf_page_match") is True:
            return hit
    return hits[0]


def normalise_generic_metadata(row: Mapping[str, Any], path: Path) -> dict[str, Any]:
    query_id = clean(row.get("query_id"))
    if not query_id:
        return {}
    source_metadata = row.get("source_metadata") if isinstance(row.get("source_metadata"), Mapping) else {}
    parser_metadata = (
        row.get("parser_source_metadata")
        if isinstance(row.get("parser_source_metadata"), Mapping)
        else source_metadata
    )
    return with_field_sources(
        {
            "query_id": query_id,
            "source_file_id": clean(row.get("source_file_id") or row.get("sourceFileId")),
            "extracted_artifact_id": clean(row.get("extracted_artifact_id") or row.get("extractedArtifactId")),
            "document_version_id": clean(row.get("document_version_id") or row.get("stable_source_identity")),
            "search_unit_id": clean(row.get("search_unit_id") or row.get("searchUnitId")),
            "source_searchunit_id": clean(
                row.get("source_searchunit_id") or row.get("source_search_unit_id") or row.get("search_unit_id")
            ),
            "search_unit_rank": int_or_none(row.get("search_unit_rank") or row.get("source_searchunit_rank")),
            "source_searchunit_rank": int_or_none(row.get("source_searchunit_rank") or row.get("search_unit_rank")),
            "retrieval_rank": int_or_none(row.get("retrieval_rank") or row.get("rank")),
            "parser_version": clean(row.get("parser_version")),
            "parser_source_metadata": parser_metadata,
            "source_metadata": source_metadata or parser_metadata,
            "page": int_or_none(row.get("page")),
            "physical_page_index": int_or_none(row.get("physical_page_index")),
            "bbox": row.get("bbox") if isinstance(row.get("bbox"), list) else [],
            "bbox_source": clean(row.get("bbox_source")),
            "layout_resolution_method": clean(row.get("layout_resolution_method")),
            "source_bound_bbox": row.get("source_bound_bbox") is True,
            "region_type": clean(row.get("region_type")),
            "matched_text": clean(row.get("matched_text")),
            "citation_text": clean(row.get("citation_text")),
            "section_heading": clean(row.get("section_heading")),
            "table_caption_footnote": clean(row.get("table_caption_footnote")),
            "nearby_paragraphs": list_value(row.get("nearby_paragraphs")),
            "native_text_available": row.get("native_text_available") is True,
            "OCR_confidence": row.get("OCR_confidence"),
            "OCR_fallback_used": row.get("OCR_fallback_used") is True,
        },
        repo_relative(path),
    )


def enrich_from_db(metadata_by_query: dict[str, dict[str, Any]], db_dsn: str) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "attempted": True,
        "readonly_transaction": True,
        "resolved_query_count": 0,
        "errors": [],
    }
    try:
        import psycopg2
        import psycopg2.extras
    except Exception as exc:  # pragma: no cover - depends on local env
        summary["errors"].append(f"psycopg2 unavailable: {type(exc).__name__}: {exc}")
        return summary
    try:
        conn = psycopg2.connect(db_dsn)
        conn.set_session(readonly=True, autocommit=False)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SET TRANSACTION READ ONLY")
        for query_id, meta in metadata_by_query.items():
            search_unit_id = clean(meta.get("search_unit_id") or meta.get("source_searchunit_id"))
            if not search_unit_id:
                continue
            row = fetch_search_unit(cur, search_unit_id)
            if not row:
                continue
            db_meta = metadata_from_db_row(cur, row, search_unit_id)
            db_meta["query_id"] = query_id
            merge_query_metadata(metadata_by_query, db_meta)
            summary["resolved_query_count"] += 1
        conn.rollback()
        cur.close()
        conn.close()
    except Exception as exc:  # pragma: no cover - depends on local DB shape
        summary["errors"].append(f"{type(exc).__name__}: {exc}")
    return summary


def fetch_search_unit(cur: Any, search_unit_id: str) -> Mapping[str, Any]:
    cur.execute(
        """
        select
            su.id,
            su.source_file_id,
            su.extracted_artifact_id,
            su.document_id,
            su.document_version_id,
            su.parsed_artifact_id,
            su.source_file_name,
            su.source_file_type,
            su.chunk_type,
            su.location_type,
            su.location_json,
            su.parser_name,
            su.parser_version,
            su.index_version,
            su.embedding_status,
            su.citation_text,
            su.display_text,
            su.text_content,
            su.section_path,
            su.page_start,
            su.page_end,
            su.metadata_json,
            su.confidence_score,
            su.quality_score,
            pa.artifact_type as parsed_artifact_type,
            pa.storage_uri as parsed_artifact_storage_uri,
            pa.parser_name as parsed_parser_name,
            pa.parser_version as parsed_parser_version,
            ea.pipeline_version as extracted_pipeline_version,
            pp.text_layer_present,
            pp.ocr_used as page_ocr_used,
            pp.ocr_confidence as page_ocr_confidence,
            pp.ocr_confidence_avg,
            pp.block_count,
            pp.table_count
        from search_unit su
        left join parsed_artifact pa on pa.id = su.parsed_artifact_id
        left join extracted_artifact ea on ea.artifact_id = su.extracted_artifact_id
        left join pdf_page_metadata pp
            on pp.document_version_id = su.document_version_id
           and pp.page_no = coalesce(su.page_start, nullif(su.location_json->>'page_no', '')::int)
        where su.id = %s
        """,
        (search_unit_id,),
    )
    row = cur.fetchone()
    return row if isinstance(row, Mapping) else {}


def metadata_from_db_row(cur: Any, row: Mapping[str, Any], search_unit_id: str) -> dict[str, Any]:
    location = row.get("location_json") if isinstance(row.get("location_json"), Mapping) else {}
    page = int_or_none(location.get("page_no") or row.get("page_start"))
    nearby = fetch_nearby_paragraphs(
        cur,
        document_version_id=clean(row.get("document_version_id")),
        search_unit_id=search_unit_id,
        page=page,
    )
    ocr_confidence = first_nonempty(location.get("ocr_confidence"), row.get("page_ocr_confidence"), row.get("ocr_confidence_avg"))
    native_text = location.get("ocr_used") is False or (
        row.get("text_layer_present") is True and row.get("page_ocr_used") is not True
    )
    ocr_fallback = location.get("ocr_used") is True or row.get("page_ocr_used") is True
    parser_version = clean(row.get("parser_version") or row.get("parsed_parser_version"))
    source_metadata = {
        "metadata_source": "local_db_readonly",
        "search_unit": {
            "id": clean(row.get("id")),
            "chunk_type": clean(row.get("chunk_type")),
            "location_type": clean(row.get("location_type")),
            "index_version": clean(row.get("index_version")),
            "embedding_status": clean(row.get("embedding_status")),
            "quality_score": row.get("quality_score"),
            "confidence_score": row.get("confidence_score"),
        },
        "parser": {
            "parser_name": clean(row.get("parser_name") or row.get("parsed_parser_name")),
            "parser_version": parser_version,
        },
        "parsed_artifact": {
            "id": clean(row.get("parsed_artifact_id")),
            "artifact_type": clean(row.get("parsed_artifact_type")),
            "storage_uri": clean(row.get("parsed_artifact_storage_uri")),
        },
        "extracted_artifact": {
            "id": clean(row.get("extracted_artifact_id")),
            "pipeline_version": clean(row.get("extracted_pipeline_version")),
        },
        "page_metadata": {
            "text_layer_present": row.get("text_layer_present"),
            "ocr_used": row.get("page_ocr_used"),
            "ocr_confidence": row.get("page_ocr_confidence"),
            "ocr_confidence_avg": row.get("ocr_confidence_avg"),
            "block_count": row.get("block_count"),
            "table_count": row.get("table_count"),
        },
        "location_json": location,
    }
    return with_field_sources(
        {
            "source_file_id": clean(row.get("source_file_id")),
            "extracted_artifact_id": clean(row.get("extracted_artifact_id")),
            "document_version_id": clean(row.get("document_version_id")),
            "parser_version": parser_version,
            "parser_source_metadata": source_metadata,
            "source_metadata": source_metadata,
            "page": page,
            "physical_page_index": int_or_none(location.get("physical_page_index")),
            "bbox": location.get("bbox") if isinstance(location.get("bbox"), list) else [],
            "region_type": clean(location.get("block_type") or row.get("chunk_type") or row.get("location_type")),
            "citation_text": clean(row.get("citation_text") or row.get("display_text")),
            "section_heading": clean(row.get("section_path")),
            "nearby_paragraphs": nearby,
            "native_text_available": native_text,
            "OCR_confidence": ocr_confidence,
            "OCR_fallback_used": ocr_fallback,
        },
        "local_db_readonly",
    )


def fetch_nearby_paragraphs(
    cur: Any,
    *,
    document_version_id: str,
    search_unit_id: str,
    page: int | None,
) -> list[str]:
    if not document_version_id or page is None:
        return []
    cur.execute(
        """
        select citation_text, display_text, text_content
        from search_unit
        where document_version_id = %s
          and id <> %s
          and lower(coalesce(chunk_type, '')) = 'paragraph'
          and coalesce(page_start, nullif(location_json->>'page_no', '')::int) between %s and %s
        order by
          abs(coalesce(page_start, nullif(location_json->>'page_no', '')::int) - %s),
          coalesce(page_start, nullif(location_json->>'page_no', '')::int),
          id
        limit 4
        """,
        (document_version_id, search_unit_id, max(page - 1, 1), page + 1, page),
    )
    paragraphs: list[str] = []
    for row in cur.fetchall():
        text = clean(row.get("citation_text") or row.get("display_text") or row.get("text_content"))
        if text:
            paragraphs.append(text[:600])
    return paragraphs


def merge_metadata(row: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any]:
    enriched = copy.deepcopy(dict(row))
    citation_metadata = enriched.get("citation_metadata") if isinstance(enriched.get("citation_metadata"), dict) else {}
    citation_locator = enriched.get("citation_locator") if isinstance(enriched.get("citation_locator"), dict) else {}
    if not citation_locator and isinstance(citation_metadata.get("citation_locator"), dict):
        citation_locator = citation_metadata["citation_locator"]

    simple_fields = (
        "source_file_id",
        "extracted_artifact_id",
        "document_version_id",
        "page",
        "physical_page_index",
        "bbox",
        "region_type",
        "matched_text",
        "citation_text",
        "section_heading",
        "table_caption_footnote",
        "nearby_paragraphs",
        "native_text_available",
        "OCR_confidence",
        "OCR_fallback_used",
        "parser_version",
        "bbox_source",
        "layout_resolution_method",
        "source_bound_bbox",
    )
    for key in simple_fields:
        if key in metadata and nonempty(metadata.get(key)) and not nonempty(citation_metadata.get(key)):
            citation_metadata[key] = copy.deepcopy(metadata[key])
    if nonempty(metadata.get("search_unit_id")):
        citation_metadata["source_searchunit_id"] = metadata["search_unit_id"]
        citation_locator["search_unit_id"] = metadata["search_unit_id"]
    if nonempty(metadata.get("source_searchunit_id")) and not nonempty(citation_metadata.get("source_searchunit_id")):
        citation_metadata["source_searchunit_id"] = metadata["source_searchunit_id"]
        citation_locator["search_unit_id"] = metadata["source_searchunit_id"]
    if nonempty(metadata.get("search_unit_rank")) and not nonempty(citation_metadata.get("source_searchunit_rank")):
        citation_metadata["source_searchunit_rank"] = metadata["search_unit_rank"]
    if nonempty(metadata.get("source_searchunit_rank")) and not nonempty(citation_metadata.get("source_searchunit_rank")):
        citation_metadata["source_searchunit_rank"] = metadata["source_searchunit_rank"]
    if nonempty(metadata.get("retrieval_rank")) and not nonempty(citation_metadata.get("retrieval_rank")):
        citation_metadata["retrieval_rank"] = metadata["retrieval_rank"]
    parser_metadata = (
        metadata.get("parser_source_metadata")
        if isinstance(metadata.get("parser_source_metadata"), Mapping)
        else metadata.get("source_metadata")
        if isinstance(metadata.get("source_metadata"), Mapping)
        else {}
    )
    if parser_metadata and not nonempty(citation_metadata.get("parser_source_metadata")):
        citation_metadata["parser_source_metadata"] = copy.deepcopy(parser_metadata)
    citation_metadata["metadata_resolution_sources"] = sorted(
        set(list_value(citation_metadata.get("metadata_resolution_sources")) + list_value(metadata.get("metadata_sources")))
    )
    for key in ("page", "physical_page_index", "bbox", "region_type", "document_version_id"):
        if key in citation_metadata and nonempty(citation_metadata.get(key)) and not nonempty(citation_locator.get(key)):
            citation_locator[key] = copy.deepcopy(citation_metadata[key])
    if not nonempty(citation_locator.get("file")):
        file_name = citation_metadata.get("file") or metadata.get("file") or metadata.get("source_file_name") or row.get("document_id")
        if nonempty(file_name):
            citation_locator["file"] = clean(file_name)
            if not nonempty(citation_metadata.get("file")):
                citation_metadata["file"] = clean(file_name)
    if not nonempty(citation_locator.get("document_version_id")):
        docv = citation_metadata.get("document_version_id") or row.get("document_version_id") or row.get(
            "stable_source_identity"
        )
        if nonempty(docv):
            citation_locator["document_version_id"] = clean(docv)
            if not nonempty(citation_metadata.get("document_version_id")):
                citation_metadata["document_version_id"] = clean(docv)
    if nonempty(citation_metadata.get("source_file_id")):
        enriched["source_file_id"] = citation_metadata["source_file_id"]
    if nonempty(citation_metadata.get("extracted_artifact_id")):
        enriched["extracted_artifact_id"] = citation_metadata["extracted_artifact_id"]
    enriched["citation_metadata"] = citation_metadata
    enriched["citation_locator"] = citation_locator
    return enriched


def merge_query_metadata(metadata_by_query: dict[str, dict[str, Any]], metadata: Mapping[str, Any]) -> int:
    query_id = clean(metadata.get("query_id"))
    if not query_id:
        return 0
    current = metadata_by_query.setdefault(query_id, {"query_id": query_id})
    for key, value in metadata.items():
        if key in {"query_id", "_field_sources"}:
            continue
        if key == "source_metadata" and isinstance(value, Mapping):
            merged = dict(current.get("source_metadata") or {})
            merged.update(value)
            current["source_metadata"] = merged
        elif key == "parser_source_metadata" and isinstance(value, Mapping):
            merged = dict(current.get("parser_source_metadata") or {})
            merged.update(value)
            current["parser_source_metadata"] = merged
        elif nonempty(value) and not nonempty(current.get(key)):
            current[key] = copy.deepcopy(value)
    for field, source in (metadata.get("_field_sources") or {}).items():
        add_field_source(current, str(field), str(source))
    return 1


def generated_strict_preview_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for row in rows:
        if row.get("strict_ready") is not True:
            continue
        previews.append(
            {
                "query_id": clean(row.get("query_id")),
                "search_unit_id": clean(row.get("search_unit_id")),
                "retrieval_rank": row.get("retrieval_rank"),
                "parser_version": clean(row.get("parser_version")),
                "citation_locator": row.get("citation_locator"),
                "diagnostic_only": True,
                "official_metric_input": False,
                "promotion_evidence": False,
            }
        )
    return previews


def count_snapshot(report: Mapping[str, Any]) -> dict[str, int]:
    keys = (
        "input_rows",
        "complete_page_bbox_region_count",
        "matched_text_count",
        "citation_locator_complete_count",
        "search_unit_id_available_count",
        "parser_source_metadata_available_count",
        "nearby_paragraph_count",
        "OCR_confidence_available_count",
        "native_text_available_count",
        "native_or_ocr_trust_available_count",
        "strict_ready_rows",
        "diagnostic_only_fallback_rows",
        "file_identity_ambiguous_count",
        "official_metric_input_rows",
    )
    return {key: int_value(report.get(key)) for key in keys}


def remaining_blockers(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    return {
        clean(row.get("query_id")): list(row.get("blocker_classifications") or [])
        for row in rows
        if row.get("strict_ready") is not True
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    before = report["before_counts"]
    after = report["after_counts"]
    lines = [
        "# PDF Evidence Metadata Enrichment Report",
        "",
        f"- Status: `{report['status']}`",
        "- Scope: PDF evidence readiness only; answer generation and official metrics remain closed.",
        f"- Input rows: `{after['input_rows']}`",
        f"- SearchUnit id: `{before['search_unit_id_available_count']}` -> `{after['search_unit_id_available_count']}`",
        "- Parser/source metadata: "
        f"`{before['parser_source_metadata_available_count']}` -> `{after['parser_source_metadata_available_count']}`",
        f"- Nearby paragraphs: `{before['nearby_paragraph_count']}` -> `{after['nearby_paragraph_count']}`",
        "- OCR/native trust: "
        f"`{before['native_or_ocr_trust_available_count']}` -> `{after['native_or_ocr_trust_available_count']}`",
        "- Citation locator complete: "
        f"`{before['citation_locator_complete_count']}` -> `{after['citation_locator_complete_count']}`",
        f"- Strict ready rows: `{before['strict_ready_rows']}` -> `{after['strict_ready_rows']}`",
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


def generic_json_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in ("rows", "repair_rows", "readiness_rows", "row_audit"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, Mapping)]
    return []


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


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def with_field_sources(metadata: dict[str, Any], source: str) -> dict[str, Any]:
    metadata["_field_sources"] = {key: source for key, value in metadata.items() if key != "query_id" and nonempty(value)}
    metadata["metadata_sources"] = [source]
    return metadata


def add_field_source(metadata: dict[str, Any], field: str, source: str) -> None:
    field_sources = metadata.setdefault("_field_sources", {})
    if isinstance(field_sources, dict):
        field_sources[field] = source
    sources = set(list_value(metadata.get("metadata_sources")))
    if source:
        sources.add(source)
    metadata["metadata_sources"] = sorted(sources)


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else ([] if value in (None, "") else [value])


def first_nonempty(*values: Any) -> Any:
    for value in values:
        if nonempty(value):
            return value
    return None


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
