"""Investigate Track C C8 reviewed PDF failures at case level.

This diagnostic report enriches the C8 case pack with read-only SearchUnit
surface evidence from the local database when available. It does not tune
retrieval, run promotion, mutate gold files, reindex, or change artifacts.
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


DEFAULT_CASE_PACK = Path("reports/rag_pdf_retrieval_tuning_case_pack.json")
DEFAULT_OUTPUT = Path("reports/rag_pdf_c8_case_investigation_report.json")
DEFAULT_DB_DSN = "host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw"

GENERIC_QUERY_TERMS = {
    "목",
    "차",
    "목차",
    "기간중",
    "달러",
    "수입",
    "cif",
}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    case_pack_path = Path(args.case_pack)
    case_pack = read_json(case_pack_path)
    warnings: list[str] = []
    db_context = {"available": False, "expected_units": {}, "top_hit_units": {}}
    if not args.no_db:
        db_context = load_db_context(
            cases=list(case_pack.get("cases") or []),
            db_dsn=args.db_dsn,
            warnings=warnings,
        )
    payload = build_investigation_report(
        case_pack=case_pack,
        db_context=db_context,
        case_pack_path=case_pack_path,
        warnings=warnings,
    )
    write_json(Path(args.output), payload)
    print_json(payload)
    return 0 if payload.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 2


def build_investigation_report(
    *,
    case_pack: Mapping[str, Any],
    db_context: Mapping[str, Any],
    case_pack_path: Path,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warning_list = list(warnings or [])
    validate_case_pack(case_pack, blockers)
    cases = list(case_pack.get("cases") or [])
    expected_units = db_context.get("expected_units") if isinstance(db_context.get("expected_units"), Mapping) else {}
    top_hit_units = db_context.get("top_hit_units") if isinstance(db_context.get("top_hit_units"), Mapping) else {}
    rows = [
        investigate_case(
            case=case,
            expected_units=list(expected_units.get(clean(case.get("query_id")), [])),
            top_hit_units=top_hit_units,
        )
        for case in cases
        if isinstance(case, Mapping)
    ]
    if len(rows) != int(case_pack.get("case_count") or 0):
        blockers.append("investigated row count must match C8 case_count")
    if any(row.get("table_deferred") for row in rows):
        blockers.append("C8.1 should only inspect reviewed non-table failures")

    root_cause_counts = count(rows, "root_cause")
    refined_action_counts = count(rows, "refined_next_action")
    status = "FAIL" if blockers else ("PASS_WITH_WARNINGS" if warning_list else "PASS")
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "track": "C",
        "phase": "C8.1",
        "report_role": "pdf_c8_case_level_investigation",
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
        "immutable_baseline_changed": False,
        "xlsx_candidate_artifact_changed": False,
        "table_specific_retrieval_proven": False,
        "db_inspection_used": bool(db_context.get("available")),
        "input_reports": {
            "case_pack": report_ref(case_pack, case_pack_path),
        },
        "case_count": len(rows),
        "source_case_pack_next_action_counts": case_pack.get("next_action_counts") or {},
        "root_cause_counts": root_cause_counts,
        "refined_next_action_counts": refined_action_counts,
        "broad_tuning_recommended": False,
        "case_level_investigation_required": True,
        "rows": rows,
        "blockers": dedupe(blockers),
        "warnings": dedupe(warning_list),
        "next_action": "Review the refined case buckets before any narrow retrieval change; broad tuning remains blocked.",
        "notes": [
            "C8.1 is diagnostic-only and reads SearchUnit surfaces when the local DB is available.",
            "Repeated short table/header query surfaces dominate the remaining reviewed PDF failures.",
            "No hybrid search, reranker, parser expansion, reindexing, promotion, or baseline update is run.",
        ],
    }


def investigate_case(
    *,
    case: Mapping[str, Any],
    expected_units: list[Mapping[str, Any]],
    top_hit_units: Mapping[str, Any],
) -> dict[str, Any]:
    query = clean(case.get("query"))
    query_tokens = tokens(query)
    top_hits = list(case.get("top10_hit_summary") or [])
    expected_surface = summarize_expected_surface(
        query=query,
        expected_units=expected_units,
        expected_bbox=case.get("expected_bbox"),
    )
    top_surface = summarize_top_surface(query=query, top_hits=top_hits, top_hit_units=top_hit_units)
    root_cause = choose_root_cause(case, query_tokens, expected_surface, top_surface)
    refined_action = choose_refined_action(root_cause)
    return {
        "query_id": case.get("query_id"),
        "bucket": case.get("bucket"),
        "query": query,
        "query_tokens": sorted(query_tokens),
        "query_surface_class": query_surface_class(query_tokens),
        "expected_document_version_id": case.get("expected_document_version_id"),
        "expected_page_no": case.get("expected_page_no"),
        "expected_physical_page_index": case.get("expected_physical_page_index"),
        "expected_bbox": case.get("expected_bbox"),
        "source_next_action": case.get("next_action"),
        "same_file_hit_ranks": case.get("same_file_hit_ranks") or [],
        "same_page_hit_ranks": case.get("same_page_hit_ranks") or [],
        "expected_file_absent": bool(case.get("expected_file_absent")),
        "expected_page_absent": bool(case.get("expected_page_absent")),
        "expected_page_surface": expected_surface,
        "top_hit_surface": top_surface,
        "root_cause": root_cause,
        "refined_next_action": refined_action,
        "broad_tuning_recommended": False,
        "table_deferred": False,
        "evidence_summary": evidence_summary(case, expected_surface, top_surface, root_cause),
    }


def summarize_expected_surface(
    *,
    query: str,
    expected_units: list[Mapping[str, Any]],
    expected_bbox: Any,
) -> dict[str, Any]:
    query_tokens = tokens(query)
    parsed_expected_bbox = parse_bbox(expected_bbox)
    unit_summaries: list[dict[str, Any]] = []
    phrase_hits = 0
    token_hits = 0
    page_unit_count = 0
    embedding_record_count = 0
    ragmeta_chunk_count = 0
    exact_bbox_count = 0
    bbox_overlap_count = 0
    for unit in expected_units:
        text = clean(unit.get("text_content"))
        embedding_text = clean(unit.get("embedding_text"))
        location_json = unit.get("location_json") if isinstance(unit.get("location_json"), Mapping) else {}
        unit_bbox = parse_bbox(location_json.get("bbox"))
        overlap = sorted(query_tokens & tokens(f"{text} {embedding_text}"))
        phrase_hit = normalized_phrase(query) in normalized_phrase(f"{text} {embedding_text}") if query else False
        if phrase_hit:
            phrase_hits += 1
        if overlap:
            token_hits += 1
        if clean(unit.get("chunk_type")) == "page":
            page_unit_count += 1
        if clean(unit.get("embedding_record_id")):
            embedding_record_count += 1
        if clean(unit.get("ragmeta_chunk_id")):
            ragmeta_chunk_count += 1
        if parsed_expected_bbox and unit_bbox:
            if bbox_exact(parsed_expected_bbox, unit_bbox):
                exact_bbox_count += 1
            if bbox_overlap(parsed_expected_bbox, unit_bbox):
                bbox_overlap_count += 1
        unit_summaries.append({
            "search_unit_id": unit.get("id"),
            "index_id": unit.get("index_id"),
            "chunk_type": unit.get("chunk_type"),
            "embedding_status": unit.get("embedding_status"),
            "embedding_record_present": bool(clean(unit.get("embedding_record_id"))),
            "ragmeta_chunk_present": bool(clean(unit.get("ragmeta_chunk_id"))),
            "citation_text": unit.get("citation_text"),
            "query_overlap_terms": overlap,
            "exact_query_phrase_present": phrase_hit,
            "expected_bbox_exact_match": bool(parsed_expected_bbox and unit_bbox and bbox_exact(parsed_expected_bbox, unit_bbox)),
            "expected_bbox_overlap": bool(parsed_expected_bbox and unit_bbox and bbox_overlap(parsed_expected_bbox, unit_bbox)),
            "text_preview": preview(text),
            "embedding_preview": preview(embedding_text),
        })
    return {
        "search_unit_count": len(expected_units),
        "page_unit_count": page_unit_count,
        "embedding_status_counts": count_values(unit.get("embedding_status") for unit in expected_units),
        "embedding_record_count": embedding_record_count,
        "ragmeta_chunk_count": ragmeta_chunk_count,
        "target_exists_in_index": bool(expected_units),
        "target_embedding_records_complete": bool(expected_units) and embedding_record_count == len(expected_units),
        "target_ragmeta_chunks_complete": bool(expected_units) and ragmeta_chunk_count == len(expected_units),
        "expected_bbox_present": bool(parsed_expected_bbox),
        "target_exact_bbox_exists": (exact_bbox_count > 0) if parsed_expected_bbox else None,
        "target_bbox_overlap_exists": (bbox_overlap_count > 0) if parsed_expected_bbox else None,
        "exact_bbox_unit_count": exact_bbox_count,
        "bbox_overlap_unit_count": bbox_overlap_count,
        "query_token_hit_unit_count": token_hits,
        "exact_query_phrase_hit_unit_count": phrase_hits,
        "expected_page_has_query_surface": bool(token_hits or phrase_hits),
        "sample_units": unit_summaries[:8],
    }


def summarize_top_surface(
    *,
    query: str,
    top_hits: list[Mapping[str, Any]],
    top_hit_units: Mapping[str, Any],
) -> dict[str, Any]:
    query_tokens = tokens(query)
    summaries: list[dict[str, Any]] = []
    overlap_hit_count = 0
    exact_phrase_count = 0
    for hit in top_hits[:10]:
        unit = top_hit_units.get(clean(hit.get("search_unit_id")), {}) if isinstance(top_hit_units, Mapping) else {}
        text = clean(unit.get("text_content")) or clean(hit.get("citation_text"))
        embedding_text = clean(unit.get("embedding_text"))
        overlap = sorted(query_tokens & tokens(f"{text} {embedding_text}"))
        phrase_hit = normalized_phrase(query) in normalized_phrase(f"{text} {embedding_text}") if query else False
        if overlap:
            overlap_hit_count += 1
        if phrase_hit:
            exact_phrase_count += 1
        summaries.append({
            "rank": hit.get("rank"),
            "score": hit.get("score"),
            "search_unit_id": hit.get("search_unit_id"),
            "source_file_name": hit.get("source_file_name"),
            "page_no": hit.get("page_no"),
            "chunk_type": hit.get("chunk_type"),
            "file_match": hit.get("file_match"),
            "pdf_page_match": hit.get("pdf_page_match"),
            "query_overlap_terms": overlap,
            "exact_query_phrase_present": phrase_hit,
            "text_preview": preview(text),
            "embedding_preview": preview(embedding_text),
        })
    return {
        "top10_query_token_overlap_hit_count": overlap_hit_count,
        "top10_exact_query_phrase_hit_count": exact_phrase_count,
        "top_hit": summaries[0] if summaries else {},
        "sample_hits": summaries[:5],
    }


def choose_root_cause(
    case: Mapping[str, Any],
    query_tokens: set[str],
    expected_surface: Mapping[str, Any],
    top_surface: Mapping[str, Any],
) -> str:
    if bool(case.get("expected_file_absent")):
        return "CROSS_DOCUMENT_REPEATED_TABLE_LABEL_FILE_RECALL"
    if query_surface_class(query_tokens) == "SHORT_OR_GENERIC":
        return "SHORT_OR_GENERIC_QUERY_SURFACE_TOO_WEAK"
    if expected_surface.get("expected_page_has_query_surface") and top_surface.get("top10_query_token_overlap_hit_count"):
        return "EXPECTED_PAGE_PRESENT_BUT_DENSE_RANKING_MISS"
    if expected_surface.get("expected_page_has_query_surface"):
        return "EXPECTED_PAGE_PRESENT_BUT_NOT_RECALLED_IN_TOP10"
    return "EXPECTED_PAGE_SURFACE_WEAK_OR_GOLD_BINDING_REVIEW"


def choose_refined_action(root_cause: str) -> str:
    if root_cause == "CROSS_DOCUMENT_REPEATED_TABLE_LABEL_FILE_RECALL":
        return "FILE_RECALL_INVESTIGATION"
    if root_cause == "SHORT_OR_GENERIC_QUERY_SURFACE_TOO_WEAK":
        return "QUERY_SURFACE_REVIEW"
    if root_cause == "EXPECTED_PAGE_PRESENT_BUT_DENSE_RANKING_MISS":
        return "EMBEDDING_SURFACE_REVIEW"
    if root_cause == "EXPECTED_PAGE_SURFACE_WEAK_OR_GOLD_BINDING_REVIEW":
        return "GOLD_BINDING_REVIEW"
    return "PAGE_RANKING_INVESTIGATION"


def evidence_summary(
    case: Mapping[str, Any],
    expected_surface: Mapping[str, Any],
    top_surface: Mapping[str, Any],
    root_cause: str,
) -> str:
    same_file = case.get("same_file_hit_ranks") or []
    same_page = case.get("same_page_hit_ranks") or []
    expected_count = expected_surface.get("search_unit_count")
    expected_hits = expected_surface.get("query_token_hit_unit_count")
    top_overlap = top_surface.get("top10_query_token_overlap_hit_count")
    return (
        f"{root_cause}; expected_page_units={expected_count}, "
        f"expected_query_surface_units={expected_hits}, "
        f"top10_query_surface_hits={top_overlap}, "
        f"same_file_ranks={same_file}, same_page_ranks={same_page}."
    )


def validate_case_pack(case_pack: Mapping[str, Any], blockers: list[str]) -> None:
    if case_pack.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
        blockers.append(f"C8 case pack must be PASS or PASS_WITH_WARNINGS; got {case_pack.get('status')}")
    if case_pack.get("promotion_evidence") is not False:
        blockers.append("C8 case pack must keep promotion_evidence=false")
    if case_pack.get("evidence_role") != EVIDENCE_ROLE:
        blockers.append("C8 case pack must keep evidence_role=diagnostic")
    if case_pack.get("retrieval_tuning_executed") is not False:
        blockers.append("C8 case pack must keep retrieval_tuning_executed=false")
    if case_pack.get("table_specific_retrieval_proven") is not False:
        blockers.append("C8 case pack must keep table_specific_retrieval_proven=false")
    if case_pack.get("pdf_candidate_namespace") != PDF_CANDIDATE_NAMESPACE:
        blockers.append("C8 case pack namespace must match PDF candidate namespace")


def load_db_context(*, cases: list[Mapping[str, Any]], db_dsn: str, warnings: list[str]) -> dict[str, Any]:
    try:
        import psycopg2  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local env
        warnings.append(f"DB inspection skipped because psycopg2 is unavailable: {exc}")
        return {"available": False, "expected_units": {}, "top_hit_units": {}}

    try:
        conn = psycopg2.connect(db_dsn)
    except Exception as exc:  # pragma: no cover - depends on local env
        warnings.append(f"DB inspection skipped because connection failed: {exc}")
        return {"available": False, "expected_units": {}, "top_hit_units": {}}

    expected_units: dict[str, list[dict[str, Any]]] = {}
    top_hit_units: dict[str, dict[str, Any]] = {}
    try:
        with conn:
            with conn.cursor() as cur:
                for case in cases:
                    query_id = clean(case.get("query_id"))
                    docv = expected_docv(case)
                    page = expected_page(case)
                    if not docv or page is None:
                        expected_units[query_id] = []
                        continue
                    cur.execute(
                        """
                        select id, source_file_name, document_version_id, chunk_type,
                               page_start, page_end, citation_text, text_content,
                               embedding_text, location_json, index_id,
                               embedding_status, embedding_record_id, ragmeta_chunk_id
                        from (
                            select su.id, su.source_file_name, su.document_version_id,
                                   su.chunk_type, su.page_start, su.page_end,
                                   su.citation_text, su.text_content, su.embedding_text,
                                   su.location_json, su.index_id, su.embedding_status,
                                   er.id as embedding_record_id,
                                   ch.chunk_id as ragmeta_chunk_id
                            from public.search_unit su
                            left join public.embedding_record er
                              on er.search_unit_id = su.id
                             and er.index_version = su.index_version
                            left join ragmeta.chunks ch
                              on ch.chunk_id = su.index_id
                             and ch.index_version = su.index_version
                            where su.document_version_id = %s
                              and su.page_start <= %s
                              and su.page_end >= %s
                              and su.index_version = %s
                        ) unit
                        order by case when chunk_type = 'page' then 0 else 1 end,
                                 page_start, id
                        limit 80
                        """,
                        (docv, page, page, PDF_CANDIDATE_NAMESPACE),
                    )
                    expected_units[query_id] = [unit_from_row(row) for row in cur.fetchall()]

                top_ids = sorted({
                    clean(hit.get("search_unit_id"))
                    for case in cases
                    for hit in list(case.get("top10_hit_summary") or [])
                    if clean(hit.get("search_unit_id"))
                })
                if top_ids:
                    cur.execute(
                        """
                        select id, source_file_name, document_version_id, chunk_type,
                               page_start, page_end, citation_text, text_content,
                               embedding_text, location_json, index_id,
                               embedding_status, embedding_record_id, ragmeta_chunk_id
                        from (
                            select su.id, su.source_file_name, su.document_version_id,
                                   su.chunk_type, su.page_start, su.page_end,
                                   su.citation_text, su.text_content, su.embedding_text,
                                   su.location_json, su.index_id, su.embedding_status,
                                   er.id as embedding_record_id,
                                   ch.chunk_id as ragmeta_chunk_id
                            from public.search_unit su
                            left join public.embedding_record er
                              on er.search_unit_id = su.id
                             and er.index_version = su.index_version
                            left join ragmeta.chunks ch
                              on ch.chunk_id = su.index_id
                             and ch.index_version = su.index_version
                            where su.id = any(%s)
                        ) unit
                        """,
                        (top_ids,),
                    )
                    top_hit_units = {clean(row[0]): unit_from_row(row) for row in cur.fetchall()}
    finally:
        conn.close()

    return {
        "available": True,
        "expected_units": expected_units,
        "top_hit_units": top_hit_units,
    }


def unit_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "source_file_name": row[1],
        "document_version_id": row[2],
        "chunk_type": row[3],
        "page_start": row[4],
        "page_end": row[5],
        "citation_text": row[6],
        "text_content": row[7],
        "embedding_text": row[8],
        "location_json": row[9],
        "index_id": row[10],
        "embedding_status": row[11],
        "embedding_record_id": row[12],
        "ragmeta_chunk_id": row[13],
    }


def tokens(value: Any) -> set[str]:
    text = clean(value).lower()
    return {
        token for token in re.findall(r"[0-9a-zA-Z가-힣]+", text)
        if token
    }


def normalized_phrase(value: Any) -> str:
    return re.sub(r"\s+", "", clean(value).lower())


def query_surface_class(query_tokens: set[str]) -> str:
    if len(query_tokens) <= 2:
        return "SHORT_OR_GENERIC"
    if query_tokens and query_tokens <= GENERIC_QUERY_TERMS:
        return "SHORT_OR_GENERIC"
    return "SPECIFIC"


def preview(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", clean(value))
    return text if len(text) <= limit else text[: limit - 3] + "..."


def parse_bbox(value: Any) -> list[float] | None:
    if isinstance(value, list) and len(value) == 4:
        try:
            return [float(item) for item in value]
        except (TypeError, ValueError):
            return None
    text = clean(value)
    if not text:
        return None
    numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
    if len(numbers) != 4:
        return None
    return [float(number) for number in numbers]


def bbox_exact(left: list[float], right: list[float], *, tolerance: float = 0.05) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(left, right))


def bbox_overlap(left: list[float], right: list[float]) -> bool:
    left_x1, left_y1, left_x2, left_y2 = left
    right_x1, right_y1, right_x2, right_y2 = right
    width = min(left_x2, right_x2) - max(left_x1, right_x1)
    height = min(left_y2, right_y2) - max(left_y1, right_y1)
    return width > 0 and height > 0


def count(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = clean(row.get(key)) or "UNKNOWN"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = clean(value) or "UNKNOWN"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-pack", default=str(DEFAULT_CASE_PACK))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--db-dsn", default=DEFAULT_DB_DSN)
    parser.add_argument("--no-db", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
