"""Run a diagnostic-only C8.2 rank probe for reviewed PDF failures.

This script reruns vector search at a deeper top-k, then joins read-only DB
SearchUnit text to answer two narrow questions:

1. Does the expected page/block appear beyond top-10?
2. Would page grouping or exact lexical evidence explain the remaining cases?

It does not tune retrieval, change parser behavior, reindex, promote, mutate
gold, or write candidate artifacts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
AI_WORKER = ROOT / "ai-worker"
for path in (SCRIPT_DIR, AI_WORKER):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rag_pdf_policy_common import (  # noqa: E402
    EVIDENCE_ROLE,
    PDF_ARTIFACT_DIR,
    PDF_CANDIDATE_NAMESPACE,
    artifact_identity,
    clean,
    dedupe,
    expected_docv,
    expected_page,
    file_sha256,
    print_json,
    read_json,
    report_ref,
    to_int,
    utc_run_id,
    utc_timestamp,
    write_json,
)


DEFAULT_CASE_INVESTIGATION = Path("reports/rag_pdf_c8_case_investigation_report.json")
DEFAULT_C4_CONSISTENCY_REPORT = Path("reports/pdf_candidate_embedding_consistency_report.json")
DEFAULT_OUTPUT = Path("reports/rag_pdf_c8_rank_probe_report.json")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"
DEFAULT_ARTIFACT_DIR = Path(PDF_ARTIFACT_DIR)
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_TOP_K = 100


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    case_path = Path(args.case_investigation)
    c4_path = Path(args.c4_consistency_report)
    case_investigation = read_json(case_path)
    c4_report = read_json(c4_path)
    warnings: list[str] = []
    blockers: list[str] = []
    units = load_units(db_dsn=args.db_dsn, warnings=warnings, blockers=blockers)
    vector_results: dict[str, list[dict[str, Any]]] = {}
    if not blockers and not args.no_vector:
        vector_results = run_vector_probe(
            cases=list(case_investigation.get("rows") or []),
            top_k=args.top_k,
            artifact_dir=Path(args.artifact_dir),
            db_dsn=args.db_dsn,
            embedding_model=args.embedding_model,
            warnings=warnings,
            blockers=blockers,
        )
    elif args.no_vector:
        blockers.append("vector probe was explicitly disabled with --no-vector")

    payload = build_rank_probe_report(
        case_investigation=case_investigation,
        units=units,
        vector_results_by_query_id=vector_results,
        case_investigation_path=case_path,
        c4_report=c4_report,
        c4_report_path=c4_path,
        top_k=args.top_k,
        blockers=blockers,
        warnings=warnings,
        artifact_dir=Path(args.artifact_dir),
        expected_embedding_model=args.embedding_model,
    )
    write_json(Path(args.output), payload)
    print_json(payload)
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def build_rank_probe_report(
    *,
    case_investigation: Mapping[str, Any],
    units: list[Mapping[str, Any]],
    vector_results_by_query_id: Mapping[str, list[Mapping[str, Any]]],
    case_investigation_path: Path,
    c4_report: Mapping[str, Any],
    c4_report_path: Path,
    top_k: int,
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    expected_embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> dict[str, Any]:
    blocker_list = list(blockers or [])
    warning_list = list(warnings or [])
    validate_case_investigation(case_investigation, blocker_list)
    artifact_contract = validate_c4_and_artifact(
        c4_report=c4_report,
        c4_report_path=c4_report_path,
        artifact_dir=artifact_dir,
        expected_embedding_model=expected_embedding_model,
        blockers=blocker_list,
    )
    rows = [
        probe_case(
            case=case,
            units=units,
            vector_hits=vector_results_by_query_id.get(clean(case.get("query_id")), []),
            top_k=top_k,
        )
        for case in list(case_investigation.get("rows") or [])
        if isinstance(case, Mapping)
    ]
    if len(rows) != int(case_investigation.get("case_count") or 0):
        blocker_list.append("C8.2 row count must match C8.1 case_count")
    if rows and any(row.get("vector_probe_blocked") for row in rows):
        blocker_list.append("vector top-k probe must be available for every C8.2 row")
    gate_counters = gate_counter_summary(rows)
    if gate_counters["wrong_index_version_hit_count"] or gate_counters["non_embedded_hit_count"]:
        blocker_list.append("C8.2 vector hits must all use the PDF candidate index namespace and EMBEDDED status")

    status = "BLOCKED_WITH_REASON" if blocker_list else ("PASS_WITH_WARNINGS" if warning_list else "PASS")
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C8.2",
        "report_role": "pdf_c8_rank_probe",
        "promotion_evidence": False,
        "evidence_role": EVIDENCE_ROLE,
        "pdf_candidate_namespace": PDF_CANDIDATE_NAMESPACE,
        "pdf_artifact_dir": str(artifact_dir),
        "retrieval_tuning_executed": False,
        "retrieval_execution": "top_k_vector_probe_only",
        "indexing_execution": "not_run_by_this_script",
        "promotion_execution": "not_run_by_this_script",
        "baseline_execution": "not_run_by_this_script",
        "gold_mutation_execution": "not_run_by_this_script",
        "immutable_baseline_changed": False,
        "xlsx_candidate_artifact_changed": False,
        "table_specific_retrieval_proven": False,
        "top_k": int(top_k),
        "db_candidate_unit_count": len(units),
        "artifact_contract": artifact_contract,
        "input_reports": {
            "case_investigation": report_ref(case_investigation, case_investigation_path),
            "c4_embedding_consistency": report_ref(c4_report, c4_report_path),
        },
        "gate_counters": gate_counters,
        "case_count": len(rows),
        "target_rank_summary": target_rank_summary(rows),
        "lexical_probe_summary": lexical_probe_summary(rows),
        "page_aggregation_summary": page_aggregation_summary(rows),
        "refined_next_action_counts": count(rows, "rank_probe_next_action"),
        "broad_tuning_recommended": False,
        "rows": rows,
        "blockers": dedupe(blocker_list),
        "warnings": dedupe(warning_list),
        "next_action": (
            "Review query-surface and exact-rank findings before any narrow retrieval experiment."
            if not blocker_list
            else "Resolve C8.2 blockers before using rank-probe results."
        ),
        "notes": [
            "C8.2 is diagnostic-only; top-k depth is used to inspect ranks, not to change retrieval behavior.",
            "Page aggregation is a simulation over existing vector scores; it does not alter serving code or index artifacts.",
            "Lexical evidence is computed from existing SearchUnit text and is not a BM25 index or hybrid retrieval run.",
        ],
    }


def probe_case(
    *,
    case: Mapping[str, Any],
    units: list[Mapping[str, Any]],
    vector_hits: list[Mapping[str, Any]],
    top_k: int,
) -> dict[str, Any]:
    query_id = clean(case.get("query_id"))
    expected_units = [unit for unit in units if unit_matches_expected_page(unit, case)]
    expected_file_name = first_nonempty(
        case.get("expected_file_name"),
        *(unit.get("source_file_name") for unit in expected_units),
    )
    lexical = lexical_probe(case=case, units=units, expected_units=expected_units)
    vector = vector_probe(case=case, hits=vector_hits, top_k=top_k, expected_file_name=expected_file_name)
    page_groups = page_aggregation_probe(case=case, hits=vector_hits)
    next_action = choose_next_action(case, lexical, vector, page_groups)
    return {
        "query_id": query_id,
        "bucket": case.get("bucket"),
        "query": case.get("query"),
        "source_root_cause": case.get("root_cause"),
        "source_refined_next_action": case.get("refined_next_action"),
        "expected_document_version_id": case.get("expected_document_version_id"),
        "expected_file_name": expected_file_name,
        "expected_page_no": case.get("expected_page_no"),
        "expected_physical_page_index": case.get("expected_physical_page_index"),
        "expected_bbox": case.get("expected_bbox"),
        "vector_probe_blocked": not bool(vector_hits),
        "vector_probe": vector,
        "page_aggregation_probe": page_groups,
        "lexical_probe": lexical,
        "rank_probe_next_action": next_action,
        "broad_tuning_recommended": False,
    }


def vector_probe(
    *,
    case: Mapping[str, Any],
    hits: list[Mapping[str, Any]],
    top_k: int,
    expected_file_name: str,
) -> dict[str, Any]:
    expected_bbox = parse_bbox(case.get("expected_bbox"))
    file_ranks: list[int] = []
    docv_ranks: list[int] = []
    page_ranks: list[int] = []
    page_chunk_ranks: list[int] = []
    bbox_overlap_ranks: list[int] = []
    exact_bbox_ranks: list[int] = []
    wrong_index_version_hit_count = 0
    non_embedded_hit_count = 0
    for hit in hits:
        rank = to_int(hit.get("rank"))
        if rank is None:
            continue
        index_version = clean(hit.get("index_version"))
        if index_version and index_version != PDF_CANDIDATE_NAMESPACE:
            wrong_index_version_hit_count += 1
        embedding_status = clean(hit.get("embedding_status")).upper()
        if embedding_status and embedding_status != "EMBEDDED":
            non_embedded_hit_count += 1
        if expected_file_name and clean(hit.get("source_file_name")) == expected_file_name:
            file_ranks.append(rank)
        if hit_docv(hit) == expected_docv(case):
            docv_ranks.append(rank)
        if hit_matches_expected_page(hit, case):
            page_ranks.append(rank)
            if clean(hit_chunk_type(hit)) == "page":
                page_chunk_ranks.append(rank)
            hit_bbox = parse_bbox(hit_location(hit).get("bbox"))
            if expected_bbox and hit_bbox and bbox_overlap(expected_bbox, hit_bbox):
                bbox_overlap_ranks.append(rank)
            if expected_bbox and hit_bbox and bbox_exact(expected_bbox, hit_bbox):
                exact_bbox_ranks.append(rank)
    return {
        "top_k": int(top_k),
        "returned_hit_count": len(hits),
        "wrong_index_version_hit_count": wrong_index_version_hit_count,
        "non_embedded_hit_count": non_embedded_hit_count,
        "expected_file_hit_ranks": file_ranks,
        "expected_file_first_rank": min(file_ranks) if file_ranks else None,
        "expected_file_found": bool(file_ranks),
        "expected_file_found_at": found_at(file_ranks),
        "expected_docv_hit_ranks": docv_ranks,
        "expected_docv_first_rank": min(docv_ranks) if docv_ranks else None,
        "expected_docv_found": bool(docv_ranks),
        "expected_docv_found_at": found_at(docv_ranks),
        "expected_page_hit_ranks": page_ranks,
        "expected_page_first_rank": min(page_ranks) if page_ranks else None,
        "expected_page_found": bool(page_ranks),
        "expected_page_found_at": found_at(page_ranks),
        "expected_page_chunk_hit_ranks": page_chunk_ranks,
        "expected_page_chunk_first_rank": min(page_chunk_ranks) if page_chunk_ranks else None,
        "expected_page_chunk_found_at": found_at(page_chunk_ranks),
        "expected_bbox_overlap_hit_ranks": bbox_overlap_ranks,
        "expected_bbox_overlap_first_rank": min(bbox_overlap_ranks) if bbox_overlap_ranks else None,
        "expected_bbox_overlap_found_at": found_at(bbox_overlap_ranks),
        "expected_exact_bbox_hit_ranks": exact_bbox_ranks,
        "expected_exact_bbox_first_rank": min(exact_bbox_ranks) if exact_bbox_ranks else None,
        "expected_exact_bbox_found_at": found_at(exact_bbox_ranks),
        "top20_summary": [summarize_hit(hit) for hit in hits[:20]],
    }


def page_aggregation_probe(*, case: Mapping[str, Any], hits: list[Mapping[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, int | None, int | None], dict[str, Any]] = {}
    for hit in hits:
        docv = hit_docv(hit)
        loc = hit_location(hit)
        page = to_int(loc.get("page_no"))
        physical_page_index = to_int(loc.get("physical_page_index"))
        key = (docv, page, physical_page_index)
        group = groups.setdefault(
            key,
            {
                "document_version_id": docv,
                "page_no": page,
                "physical_page_index": physical_page_index,
                "best_score": None,
                "best_rank": None,
                "hit_count": 0,
                "sample_search_unit_ids": [],
            },
        )
        score = float(hit.get("score") or 0.0)
        rank = to_int(hit.get("rank"))
        group["hit_count"] += 1
        if len(group["sample_search_unit_ids"]) < 5:
            group["sample_search_unit_ids"].append(hit_search_unit_id(hit))
        if group["best_score"] is None or score > float(group["best_score"]):
            group["best_score"] = score
            group["best_rank"] = rank
        elif score == group["best_score"] and rank is not None:
            if group["best_rank"] is None or rank < int(group["best_rank"]):
                group["best_rank"] = rank
    ordered = sorted(
        groups.values(),
        key=lambda group: (-(float(group.get("best_score") or 0.0)), int(group.get("best_rank") or 999999)),
    )
    expected_rank = None
    expected_page_no = expected_page(case)
    expected_physical = expected_physical_page_index(case)
    expected_document_version_id = expected_docv(case)
    for index, group in enumerate(ordered, start=1):
        if (
            group.get("document_version_id") == expected_document_version_id
            and group.get("page_no") == expected_page_no
            and physical_page_matches(to_int(group.get("physical_page_index")), expected_physical)
        ):
            expected_rank = index
            break
    return {
        "group_count": len(ordered),
        "expected_page_group_rank": expected_rank,
        "expected_page_group_in_top10": expected_rank is not None and expected_rank <= 10,
        "top10_groups": ordered[:10],
    }


def lexical_probe(
    *,
    case: Mapping[str, Any],
    units: list[Mapping[str, Any]],
    expected_units: list[Mapping[str, Any]],
) -> dict[str, Any]:
    query = clean(case.get("query"))
    query_tokens = tokens(query)
    exact_units: list[Mapping[str, Any]] = []
    token_units: list[tuple[Mapping[str, Any], set[str]]] = []
    for unit in units:
        text = unit_surface(unit)
        overlap = query_tokens & tokens(text)
        if exact_phrase_present(query, text):
            exact_units.append(unit)
        if overlap:
            token_units.append((unit, overlap))
    expected_exact = [unit for unit in expected_units if exact_phrase_present(query, unit_surface(unit))]
    expected_token = [
        (unit, query_tokens & tokens(unit_surface(unit)))
        for unit in expected_units
        if query_tokens & tokens(unit_surface(unit))
    ]
    return {
        "query_tokens": sorted(query_tokens),
        "query_surface_class": "SHORT_OR_GENERIC" if len(query_tokens) <= 2 else "SPECIFIC",
        "corpus_exact_phrase_unit_count": len(exact_units),
        "expected_page_exact_phrase_unit_count": len(expected_exact),
        "expected_page_exact_phrase_present": bool(expected_exact),
        "corpus_token_overlap_unit_count": len(token_units),
        "expected_page_token_overlap_unit_count": len(expected_token),
        "expected_page_token_overlap_terms": sorted(set().union(*(overlap for _, overlap in expected_token))) if expected_token else [],
        "competing_exact_phrase_page_count": competing_page_count(exact_units, case),
        "exact_phrase_page_samples": page_samples(exact_units, limit=8),
        "expected_page_sample_units": [
            {
                "search_unit_id": unit.get("id"),
                "chunk_type": unit.get("chunk_type"),
                "citation_text": unit.get("citation_text"),
                "text_preview": preview(unit.get("text_content")),
            }
            for unit in expected_units[:5]
        ],
    }


def choose_next_action(
    case: Mapping[str, Any],
    lexical: Mapping[str, Any],
    vector: Mapping[str, Any],
    page_groups: Mapping[str, Any],
) -> str:
    if bool(case.get("expected_file_absent")):
        return "FILE_DISAMBIGUATION_REVIEW"
    if lexical.get("query_surface_class") == "SHORT_OR_GENERIC":
        return "QUERY_SURFACE_REVIEW"
    if vector.get("expected_page_found"):
        return "PAGE_AGGREGATION_SIMULATION_REVIEW" if page_groups.get("expected_page_group_in_top10") else "RANK_DEPTH_REVIEW"
    if lexical.get("expected_page_exact_phrase_present"):
        return "LEXICAL_EXACT_PHRASE_PROBE_REVIEW"
    return "EMBEDDING_SURFACE_REVIEW"


def validate_case_investigation(case_investigation: Mapping[str, Any], blockers: list[str]) -> None:
    if case_investigation.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C8.1 case investigation must be PASS or PASS_WITH_WARNINGS; got {case_investigation.get('status')}")
    if case_investigation.get("promotion_evidence") is not False:
        blockers.append("C8.1 must keep promotion_evidence=false")
    if case_investigation.get("evidence_role") != EVIDENCE_ROLE:
        blockers.append("C8.1 must keep evidence_role=diagnostic")
    if case_investigation.get("retrieval_tuning_executed") is not False:
        blockers.append("C8.1 must keep retrieval_tuning_executed=false")
    if case_investigation.get("table_specific_retrieval_proven") is not False:
        blockers.append("C8.1 must keep table_specific_retrieval_proven=false")


def validate_c4_and_artifact(
    *,
    c4_report: Mapping[str, Any],
    c4_report_path: Path,
    artifact_dir: Path,
    expected_embedding_model: str,
    blockers: list[str],
) -> dict[str, Any]:
    if c4_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C4 consistency report must be PASS or PASS_WITH_WARNINGS; got {c4_report.get('status')}")
    if c4_report.get("promotion_evidence") is not False:
        blockers.append("C4 consistency report must keep promotion_evidence=false")
    if c4_report.get("evidence_role") != EVIDENCE_ROLE:
        blockers.append("C4 consistency report must keep evidence_role=diagnostic")
    if c4_report.get("index_version") != PDF_CANDIDATE_NAMESPACE:
        blockers.append("C4 consistency report index_version must match the PDF candidate namespace")
    if c4_report.get("expected_index_version") != PDF_CANDIDATE_NAMESPACE:
        blockers.append("C4 consistency report expected_index_version must match the PDF candidate namespace")
    if clean(c4_report.get("artifact_dir")) != str(artifact_dir):
        blockers.append("C4 consistency report artifact_dir must match the rank probe artifact_dir")

    build_path = artifact_dir / "build.json"
    manifest_path = artifact_dir / "ingest_manifest.json"
    build = read_optional_json_object(build_path)
    manifest = read_optional_json_object(manifest_path)
    if not build:
        blockers.append("PDF candidate artifact build.json must exist and be parseable")
    if not manifest:
        blockers.append("PDF candidate artifact ingest_manifest.json must exist and be parseable")
    if build and build.get("index_version") != PDF_CANDIDATE_NAMESPACE:
        blockers.append("PDF candidate artifact build.json index_version must match the candidate namespace")
    if manifest and manifest.get("index_version") != PDF_CANDIDATE_NAMESPACE:
        blockers.append("PDF candidate artifact ingest_manifest.json index_version must match the candidate namespace")
    if build and clean(build.get("embedding_model")) != expected_embedding_model:
        blockers.append("PDF candidate artifact build.json embedding_model must match the rank probe model")
    if manifest and clean(manifest.get("embedding_model")) != expected_embedding_model:
        blockers.append("PDF candidate artifact ingest_manifest.json embedding_model must match the rank probe model")
    if build and manifest and to_int(build.get("chunk_count")) != to_int(manifest.get("chunk_count")):
        blockers.append("PDF candidate artifact build and ingest manifest chunk_count must match")

    return {
        "c4_report": {
            "path": str(c4_report_path),
            "exists": c4_report_path.exists(),
            "sha256": file_sha256(c4_report_path) if c4_report_path.exists() and c4_report_path.is_file() else None,
            "status": c4_report.get("status"),
            "index_version": c4_report.get("index_version"),
            "artifact_dir": c4_report.get("artifact_dir"),
        },
        "artifact_dir": {
            "path": str(artifact_dir),
            "exists": artifact_dir.exists(),
        },
        "build_json": artifact_identity(build_path),
        "ingest_manifest_json": artifact_identity(manifest_path),
        "build_index_version": build.get("index_version"),
        "manifest_index_version": manifest.get("index_version"),
        "build_embedding_model": build.get("embedding_model"),
        "manifest_embedding_model": manifest.get("embedding_model"),
        "build_chunk_count": build.get("chunk_count"),
        "manifest_chunk_count": manifest.get("chunk_count"),
    }


def load_units(*, db_dsn: str, warnings: list[str], blockers: list[str]) -> list[dict[str, Any]]:
    try:
        import psycopg2  # type: ignore
        import psycopg2.extras  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local env
        blockers.append(f"DB lexical probe requires psycopg2: {exc}")
        return []
    try:
        conn = psycopg2.connect(db_dsn)
        conn.set_session(readonly=True, autocommit=True)
    except Exception as exc:  # pragma: no cover - depends on local env
        blockers.append(f"DB lexical probe connection failed: {exc}")
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                select id, source_file_name, document_version_id, chunk_type,
                       page_start, page_end, citation_text, text_content,
                       embedding_text, location_json
                from public.search_unit
                where index_version = %s
                """,
                (PDF_CANDIDATE_NAMESPACE,),
            )
            rows = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
    if not rows:
        blockers.append("DB lexical probe found no candidate SearchUnits")
    return rows


def run_vector_probe(
    *,
    cases: list[Mapping[str, Any]],
    top_k: int,
    artifact_dir: Path,
    db_dsn: str,
    embedding_model: str,
    warnings: list[str],
    blockers: list[str],
) -> dict[str, list[dict[str, Any]]]:
    try:
        from eval.harness.rag_ingestion_retrieval_eval import search_vector
    except Exception as exc:
        blockers.append(f"vector probe could not import search_vector: {exc}")
        return {}
    try:
        search_fn = search_vector(
            index_dir=str(artifact_dir),
            db_dsn=db_dsn,
            embedding_model=embedding_model,
            expected_index_version=PDF_CANDIDATE_NAMESPACE,
        )
        results: dict[str, list[dict[str, Any]]] = {}
        for case in cases:
            query_id = clean(case.get("query_id"))
            results[query_id] = [normalize_vector_hit(hit) for hit in search_fn(clean(case.get("query")), top_k)]
        return results
    except Exception as exc:
        blockers.append(f"vector top-k probe failed: {exc}")
        return {}


def normalize_vector_hit(hit: Mapping[str, Any]) -> dict[str, Any]:
    unit = hit.get("searchUnit") if isinstance(hit.get("searchUnit"), Mapping) else {}
    return {
        "rank": hit.get("rank"),
        "score": hit.get("score"),
        "index_version": hit.get("indexVersion") or unit.get("indexVersion"),
        "embedding_status": hit.get("embeddingStatus") or unit.get("embeddingStatus"),
        "source_file_name": hit.get("sourceFileName") or ((hit.get("sourceFile") or {}).get("originalFileName") if isinstance(hit.get("sourceFile"), Mapping) else None),
        "document_version_id": hit.get("documentVersionId") or unit.get("documentVersionId"),
        "search_unit_id": unit.get("id") or unit.get("searchUnitId"),
        "chunk_type": unit.get("chunkType"),
        "location_json": parse_json(unit.get("locationJson")),
        "citation_text": unit.get("citationText"),
        "vector_chunk_id": (hit.get("vector") or {}).get("chunkId") if isinstance(hit.get("vector"), Mapping) else None,
    }


def summarize_hit(hit: Mapping[str, Any]) -> dict[str, Any]:
    loc = hit_location(hit)
    return {
        "rank": hit.get("rank"),
        "score": hit.get("score"),
        "search_unit_id": hit_search_unit_id(hit),
        "vector_chunk_id": hit.get("vector_chunk_id"),
        "index_version": hit.get("index_version"),
        "embedding_status": hit.get("embedding_status"),
        "source_file_name": hit.get("source_file_name"),
        "document_version_id": hit_docv(hit),
        "page_no": loc.get("page_no"),
        "physical_page_index": loc.get("physical_page_index"),
        "chunk_type": hit_chunk_type(hit),
        "citation_text": hit.get("citation_text"),
    }


def target_rank_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    probes = [row["vector_probe"] for row in rows]
    return {
        "expected_file_found_top_k_count": sum(1 for probe in probes if probe.get("expected_file_found")),
        "expected_docv_found_top_k_count": sum(1 for probe in probes if probe.get("expected_docv_found")),
        "expected_page_found_top_k_count": sum(1 for probe in probes if probe.get("expected_page_found")),
        "expected_page_missing_top_k_count": sum(1 for probe in probes if not probe.get("expected_page_found")),
        "expected_exact_bbox_found_top_k_count": sum(1 for probe in probes if probe.get("expected_exact_bbox_hit_ranks")),
        "expected_page_chunk_found_top_k_count": sum(1 for probe in probes if probe.get("expected_page_chunk_hit_ranks")),
        "found_at_counts": {
            "expected_file": found_at_counts(rows, "expected_file_first_rank"),
            "expected_docv": found_at_counts(rows, "expected_docv_first_rank"),
            "expected_page": found_at_counts(rows, "expected_page_first_rank"),
            "expected_page_chunk": found_at_counts(rows, "expected_page_chunk_first_rank"),
            "bbox_overlap": found_at_counts(rows, "expected_bbox_overlap_first_rank"),
            "exact_bbox": found_at_counts(rows, "expected_exact_bbox_first_rank"),
        },
        "expected_file_first_ranks": {
            row["query_id"]: row["vector_probe"].get("expected_file_first_rank")
            for row in rows
        },
        "expected_docv_first_ranks": {
            row["query_id"]: row["vector_probe"].get("expected_docv_first_rank")
            for row in rows
        },
        "expected_page_first_ranks": {
            row["query_id"]: row["vector_probe"].get("expected_page_first_rank")
            for row in rows
        },
        "expected_exact_bbox_first_ranks": {
            row["query_id"]: row["vector_probe"].get("expected_exact_bbox_first_rank")
            for row in rows
        },
    }


def lexical_probe_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "expected_page_exact_phrase_present_count": sum(1 for row in rows if row["lexical_probe"].get("expected_page_exact_phrase_present")),
        "short_or_generic_query_count": sum(1 for row in rows if row["lexical_probe"].get("query_surface_class") == "SHORT_OR_GENERIC"),
        "corpus_exact_phrase_unit_counts": {
            row["query_id"]: row["lexical_probe"].get("corpus_exact_phrase_unit_count")
            for row in rows
        },
    }


def page_aggregation_summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "expected_page_group_top10_count": sum(1 for row in rows if row["page_aggregation_probe"].get("expected_page_group_in_top10")),
        "expected_page_group_ranks": {
            row["query_id"]: row["page_aggregation_probe"].get("expected_page_group_rank")
            for row in rows
        },
    }


def gate_counter_summary(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "wrong_index_version_hit_count": sum(
            int(row["vector_probe"].get("wrong_index_version_hit_count") or 0)
            for row in rows
        ),
        "non_embedded_hit_count": sum(
            int(row["vector_probe"].get("non_embedded_hit_count") or 0)
            for row in rows
        ),
    }


def found_at(ranks: list[int]) -> dict[str, bool]:
    first = min(ranks) if ranks else None
    return {
        "at_10": first is not None and first <= 10,
        "at_50": first is not None and first <= 50,
        "at_100": first is not None and first <= 100,
    }


def found_at_counts(rows: list[Mapping[str, Any]], rank_key: str) -> dict[str, int]:
    ranks = [to_int(row["vector_probe"].get(rank_key)) for row in rows]
    return {
        "found_at_10": sum(1 for rank in ranks if rank is not None and rank <= 10),
        "found_at_50": sum(1 for rank in ranks if rank is not None and rank <= 50),
        "found_at_100": sum(1 for rank in ranks if rank is not None and rank <= 100),
    }


def unit_matches_expected_page(unit: Mapping[str, Any], case: Mapping[str, Any]) -> bool:
    if clean(unit.get("document_version_id")) != expected_docv(case):
        return False
    page = expected_page(case)
    if page is None:
        return False
    loc = unit_location(unit)
    loc_page = to_int(loc.get("page_no"))
    if loc_page is not None:
        return loc_page == page
    start = to_int(unit.get("page_start"))
    end = to_int(unit.get("page_end"))
    return start is not None and end is not None and start <= page <= end


def hit_matches_expected_page(hit: Mapping[str, Any], case: Mapping[str, Any]) -> bool:
    if hit_docv(hit) != expected_docv(case):
        return False
    loc = hit_location(hit)
    if to_int(loc.get("page_no")) != expected_page(case):
        return False
    expected_physical = expected_physical_page_index(case)
    if expected_physical is None:
        return True
    return to_int(loc.get("physical_page_index")) == expected_physical


def hit_docv(hit: Mapping[str, Any]) -> str:
    return clean(hit.get("document_version_id") or hit.get("documentVersionId"))


def hit_chunk_type(hit: Mapping[str, Any]) -> str:
    return clean(hit.get("chunk_type") or hit.get("chunkType"))


def hit_search_unit_id(hit: Mapping[str, Any]) -> str:
    return clean(hit.get("search_unit_id") or hit.get("searchUnitId"))


def hit_location(hit: Mapping[str, Any]) -> Mapping[str, Any]:
    value = hit.get("location_json") or hit.get("locationJson")
    parsed = parse_json(value)
    return parsed if isinstance(parsed, Mapping) else {}


def unit_location(unit: Mapping[str, Any]) -> Mapping[str, Any]:
    parsed = parse_json(unit.get("location_json"))
    return parsed if isinstance(parsed, Mapping) else {}


def unit_surface(unit: Mapping[str, Any]) -> str:
    return " ".join([
        clean(unit.get("source_file_name")),
        clean(unit.get("citation_text")),
        clean(unit.get("text_content")),
        clean(unit.get("embedding_text")),
    ])


def expected_physical_page_index(case: Mapping[str, Any]) -> int | None:
    return to_int(case.get("expected_physical_page_index"))


def physical_page_matches(actual: int | None, expected: int | None) -> bool:
    return expected is None or actual == expected


def first_nonempty(*values: Any) -> str:
    for value in values:
        text = clean(value)
        if text:
            return text
    return ""


def exact_phrase_present(query: str, text: str) -> bool:
    needle = normalized_phrase(query)
    return bool(needle and needle in normalized_phrase(text))


def competing_page_count(exact_units: list[Mapping[str, Any]], case: Mapping[str, Any]) -> int:
    expected_key = (expected_docv(case), expected_page(case))
    keys = {
        (clean(unit.get("document_version_id")), to_int(unit_location(unit).get("page_no")) or to_int(unit.get("page_start")))
        for unit in exact_units
    }
    return len({key for key in keys if key != expected_key})


def page_samples(units: list[Mapping[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()
    for unit in units:
        key = (clean(unit.get("document_version_id")), to_int(unit_location(unit).get("page_no")) or to_int(unit.get("page_start")))
        if key in seen:
            continue
        seen.add(key)
        samples.append({
            "document_version_id": key[0],
            "source_file_name": unit.get("source_file_name"),
            "page_no": key[1],
            "sample_search_unit_id": unit.get("id"),
            "sample_text": preview(unit.get("text_content")),
        })
        if len(samples) >= limit:
            break
    return samples


def read_optional_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    parsed = parse_json(path.read_text(encoding="utf-8"))
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def parse_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not clean(value):
        return {}
    try:
        return json.loads(clean(value))
    except json.JSONDecodeError:
        return {}


def parse_bbox(value: Any) -> list[float] | None:
    if isinstance(value, list) and len(value) == 4:
        try:
            return [float(item) for item in value]
        except (TypeError, ValueError):
            return None
    numbers = re.findall(r"-?\d+(?:\.\d+)?", clean(value))
    if len(numbers) != 4:
        return None
    return [float(number) for number in numbers]


def bbox_exact(left: list[float], right: list[float], *, tolerance: float = 0.05) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(left, right))


def bbox_overlap(left: list[float], right: list[float]) -> bool:
    left_x1, left_y1, left_x2, left_y2 = left
    right_x1, right_y1, right_x2, right_y2 = right
    return min(left_x2, right_x2) > max(left_x1, right_x1) and min(left_y2, right_y2) > max(left_y1, right_y1)


def tokens(value: Any) -> set[str]:
    return {token for token in re.findall(r"[0-9a-zA-Z가-힣]+", clean(value).lower()) if token}


def normalized_phrase(value: Any) -> str:
    return re.sub(r"\s+", "", clean(value).lower())


def preview(value: Any, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", clean(value))
    return text if len(text) <= limit else text[: limit - 3] + "..."


def count(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean(row.get(key)) or "UNKNOWN"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-investigation", default=str(DEFAULT_CASE_INVESTIGATION))
    parser.add_argument("--c4-consistency-report", default=str(DEFAULT_C4_CONSISTENCY_REPORT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--db-dsn", default=DEFAULT_DB_DSN)
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--no-vector", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
