"""Inventory reusable Track B R4 namu-v4 retrieval emit artifacts.

This script does not run retrieval and does not compute retrieval metrics. It
only checks whether an already-written emit can be safely reused for the R3
gold CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent

DEFAULT_GOLD = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_text_namu_v4_v0.csv"
DEFAULT_CORPUS_DIR = AI_WORKER_ROOT / "eval" / "corpora" / "namu-v4-structured-combined"
DEFAULT_R3_VALIDATION_REPORT = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_text_namu_v4_gold_validate_report.json"
)
DEFAULT_REPORT = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_text_namu_v4_retrieval_emit_inventory_report.json"
)
DEFAULT_CANDIDATE_ROOTS = [
    AI_WORKER_ROOT / "eval" / "reports" / "phase7",
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion",
]
EXCLUDED_CURRENT_PHASE_OUTPUT_NAMES = {
    "rag_text_namu_v4_retrieval_emit_inventory_report.json",
    "rag_text_namu_v4_retrieval_emit.jsonl",
    "rag_text_namu_v4_retrieval_diagnostic_report.json",
}

RESULT_LIST_FIELDS = ("top_k_results", "results", "docs", "hits")
CHUNK_ID_FIELDS = ("chunk_id", "retrieved_chunk_id", "search_unit_id", "id")
PAGE_ID_FIELDS = ("doc_id", "page_id", "retrieved_page_id", "source_page_id")
CONTEXT_FIELDS = ("chunk_text", "context", "text", "content", "raw_text", "text_preview")
SCORE_FIELDS = ("score", "similarity", "bm25_score", "vector_score", "rerank_score")
EXCLUDED_ARTIFACT_MARKERS = (
    "xlsx",
    "pdf",
    "full72",
    "file_lookup",
    "rag_text_retrieval_diagnostic_report.json",
    "gold_queries_text_e2e_v0.csv",
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidate_paths = [Path(path) for path in args.emit_path]
    if not candidate_paths:
        candidate_paths = discover_candidate_paths(
            [Path(root) for root in args.candidate_root],
            output_report=Path(args.report),
        )

    report = build_inventory(
        gold=Path(args.gold),
        corpus_dir=Path(args.corpus_dir),
        r3_validation_report=Path(args.r3_validation_report),
        candidate_paths=candidate_paths,
    )
    write_json(Path(args.report), report)
    print_json({
        "status": report["status"],
        "decision": report["decision"],
        "candidate_emit_count": report["candidate_emit_count"],
        "reusable_emit_count": report["reusable_emit_count"],
        "report": str(Path(args.report)),
    })
    return 0 if not report["status"].startswith("BLOCKED") else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--corpus-dir", default=str(DEFAULT_CORPUS_DIR))
    parser.add_argument("--r3-validation-report", default=str(DEFAULT_R3_VALIDATION_REPORT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--candidate-root", action="append", default=[str(root) for root in DEFAULT_CANDIDATE_ROOTS])
    parser.add_argument("--emit-path", action="append", default=[])
    return parser.parse_args(argv)


def build_inventory(
    *,
    gold: Path,
    corpus_dir: Path,
    r3_validation_report: Path,
    candidate_paths: Iterable[Path],
) -> dict[str, Any]:
    gold_rows, gold_columns = read_csv(gold)
    gold_query_ids = [clean(row.get("query_id")) for row in gold_rows if clean(row.get("query_id"))]
    gold_query_id_set = set(gold_query_ids)
    pages = load_pages(corpus_dir / "pages_v4.jsonl")
    chunks = load_rag_chunks(corpus_dir / "rag_chunks.jsonl")
    r3_validation = read_optional_json(r3_validation_report)
    r3_status = clean(r3_validation.get("status")) if isinstance(r3_validation, dict) else "MISSING"

    candidates = [
        inspect_emit_candidate(
            path=path,
            gold_query_ids=gold_query_id_set,
            pages=pages,
            chunks=chunks,
        )
        for path in candidate_paths
    ]
    candidates = [candidate for candidate in candidates if candidate["candidate_detected"]]
    reusable = [candidate for candidate in candidates if candidate["reusable"]]

    if r3_status != "PASSED":
        status = "BLOCKED_R3_NOT_PASSED"
        decision = "KEEP_R5_BLOCKED"
        r5_entry = {
            "allowed": False,
            "status": "BLOCKED",
            "blockers": [f"R3 validation status is {r3_status or 'MISSING'}, not PASSED"],
        }
    elif reusable:
        status = "REUSABLE_EXISTING_EMIT"
        decision = "USE_EXISTING_EMIT"
        r5_entry = {
            "allowed": True,
            "status": "READY_WITH_REUSABLE_EXISTING_EMIT",
            "blockers": [],
        }
    elif candidates:
        status = "NO_REUSABLE_EXISTING_EMIT"
        decision = "RUN_FRESH_DIAGNOSTIC_RETRIEVAL"
        r5_entry = {
            "allowed": True,
            "status": "READY_REQUIRES_FRESH_DIAGNOSTIC_RETRIEVAL",
            "blockers": [],
            "requirements": [
                "Do not reuse the inventoried artifacts for R5 metrics.",
                "R5 must generate a fresh diagnostic retrieval emit for gold_seed query ids.",
            ],
        }
    else:
        status = "NO_EXISTING_EMIT"
        decision = "RUN_FRESH_DIAGNOSTIC_RETRIEVAL"
        r5_entry = {
            "allowed": True,
            "status": "READY_REQUIRES_FRESH_DIAGNOSTIC_RETRIEVAL",
            "blockers": [],
            "requirements": [
                "No existing emit was found.",
                "R5 must generate a fresh diagnostic retrieval emit for gold_seed query ids.",
            ],
        }

    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "schema_version": "rag_text_namu_v4_retrieval_emit_inventory_v1",
        "status": status,
        "decision": decision,
        "report_role": "rag_text_namu_v4_retrieval_emit_inventory",
        "scope": "track_b_text_retrieval_e2e",
        "phase": "R4",
        "gold_csv": normalise_path(gold),
        "gold_row_count": len(gold_rows),
        "gold_query_id_count": len(gold_query_id_set),
        "gold_columns": gold_columns,
        "corpus_dir": normalise_path(corpus_dir),
        "r3_validation_report": normalise_path(r3_validation_report),
        "r3_validation_status": r3_status,
        "candidate_emit_count": len(candidates),
        "reusable_emit_count": len(reusable),
        "existing_emit_paths": [candidate["path"] for candidate in candidates],
        "reusable_emit_paths": [candidate["path"] for candidate in reusable],
        "fresh_retrieval_required": decision == "RUN_FRESH_DIAGNOSTIC_RETRIEVAL",
        "retrieval_metrics_computed": False,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "inventory_checks": {
            "query_id_must_match_gold_csv": True,
            "retrieved_chunk_ids_must_resolve_in_rag_chunks": True,
            "retrieved_chunk_doc_id_must_join_pages_v4_page_id": True,
            "context_must_trace_to_rag_chunks_chunk_text": True,
            "exclude_b_app_xlsx_pdf_file_lookup_artifacts": True,
            "retrieval_metric_execution_allowed_in_r4": False,
        },
        "candidate_summaries": candidates,
        "non_reusable_reason_counts": dict(
            sorted(
                Counter(
                    reason
                    for candidate in candidates
                    for reason in candidate["non_reusable_reasons"]
                ).items()
            )
        ),
        "r5_entry": r5_entry,
        "blockers": r5_entry.get("blockers", []),
        "warnings": [
            "R4 inventory is diagnostic-only and does not run retrieval, indexing, tuning, or promotion.",
            "Phase 7 tuning/sanity emits may have clean chunk joins but are not reusable unless query_id matches the R3 gold CSV.",
        ],
        "next_phase_recommendation": (
            "Proceed to R5 with a fresh diagnostic retrieval run."
            if decision == "RUN_FRESH_DIAGNOSTIC_RETRIEVAL" and r3_status == "PASSED"
            else "Proceed to R5 using the reusable emit."
            if decision == "USE_EXISTING_EMIT"
            else "Keep R5 blocked until R3 validation passes."
        ),
    }


def inspect_emit_candidate(
    *,
    path: Path,
    gold_query_ids: set[str],
    pages: Mapping[str, Mapping[str, Any]],
    chunks: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    payload, rows, load_error = load_candidate_rows(path)
    if load_error:
        return {
            "path": normalise_path(path),
            "candidate_detected": False,
            "reusable": False,
            "load_error": load_error,
            "non_reusable_reasons": [load_error],
        }
    if not rows:
        return {
            "path": normalise_path(path),
            "candidate_detected": False,
            "reusable": False,
            "non_reusable_reasons": ["no query-level retrieval rows detected"],
        }

    query_ids = [clean(row.get("query_id")) for row in rows if clean(row.get("query_id"))]
    query_id_set = set(query_ids)
    result_lists = [result_list_for_row(row) for row in rows]
    all_hits = [hit for result_list in result_lists for hit in result_list if isinstance(hit, Mapping)]
    resolved_chunk_count = 0
    missing_chunk_ids: set[str] = set()
    page_join_missing_chunk_ids: set[str] = set()
    context_traceable_count = 0
    context_field_hit_count = 0
    score_field_count = 0
    non_numeric_score_count = 0
    max_rank = 0
    chunk_id_fields_observed: set[str] = set()

    for hit in all_hits:
        rank = int_or_none(hit.get("rank"))
        if rank is not None:
            max_rank = max(max_rank, rank)
        if any(clean(hit.get(field)) for field in CONTEXT_FIELDS):
            context_field_hit_count += 1
        for field in SCORE_FIELDS:
            if field in hit:
                score_field_count += 1
                if not is_number(hit.get(field)):
                    non_numeric_score_count += 1
        for chunk_id, field in chunk_ids_for_hit(hit):
            chunk_id_fields_observed.add(field)
            chunk = chunks.get(chunk_id)
            if chunk is None:
                missing_chunk_ids.add(chunk_id)
                continue
            resolved_chunk_count += 1
            doc_id = clean(chunk.get("doc_id") or chunk.get("page_id"))
            if doc_id not in pages:
                page_join_missing_chunk_ids.add(chunk_id)
            if clean(chunk.get("chunk_text")):
                context_traceable_count += 1

    excluded_reasons = excluded_artifact_reasons(path, payload, rows)
    query_id_matches = query_id_set == gold_query_ids and len(query_ids) == len(gold_query_ids)
    top_k_recorded = top_k_for_payload(payload, rows, result_lists, max_rank) is not None
    retriever_identity_recorded = bool(retriever_identity(payload, rows))
    has_hits = bool(all_hits)
    non_reusable_reasons: list[str] = []
    if not query_id_matches:
        non_reusable_reasons.append("query_id_mismatch")
    if not has_hits:
        non_reusable_reasons.append("no_retrieved_hits")
    if missing_chunk_ids:
        non_reusable_reasons.append("missing_chunk_resolution")
    if page_join_missing_chunk_ids:
        non_reusable_reasons.append("chunk_doc_id_page_join_missing")
    if resolved_chunk_count and context_traceable_count != resolved_chunk_count:
        non_reusable_reasons.append("context_not_traceable_to_rag_chunks_chunk_text")
    if not top_k_recorded:
        non_reusable_reasons.append("top_k_not_recorded")
    if not retriever_identity_recorded:
        non_reusable_reasons.append("retriever_identity_not_recorded")
    if non_numeric_score_count:
        non_reusable_reasons.append("non_numeric_score_field")
    non_reusable_reasons.extend(excluded_reasons)

    sample_query_ids = sorted(query_id_set)[:5]
    missing_gold_query_ids = sorted(gold_query_ids - query_id_set)[:10]
    extra_query_ids = sorted(query_id_set - gold_query_ids)[:10]
    return {
        "path": normalise_path(path),
        "candidate_detected": True,
        "reusable": not non_reusable_reasons,
        "row_count": len(rows),
        "query_id_count": len(query_id_set),
        "sample_query_ids": sample_query_ids,
        "query_id_match_gold_csv": query_id_matches,
        "missing_gold_query_id_count": len(gold_query_ids - query_id_set),
        "extra_query_id_count": len(query_id_set - gold_query_ids),
        "missing_gold_query_ids_sample": missing_gold_query_ids,
        "extra_query_ids_sample": extra_query_ids,
        "hit_count": len(all_hits),
        "resolved_chunk_id_count": resolved_chunk_count,
        "missing_chunk_resolution_count": len(missing_chunk_ids),
        "missing_chunk_ids_sample": sorted(missing_chunk_ids)[:10],
        "chunk_doc_id_page_join_missing_count": len(page_join_missing_chunk_ids),
        "page_join_missing_chunk_ids_sample": sorted(page_join_missing_chunk_ids)[:10],
        "context_field_hit_count": context_field_hit_count,
        "context_traceable_to_chunk_text_count": context_traceable_count,
        "score_field_count": score_field_count,
        "non_numeric_score_count": non_numeric_score_count,
        "top_k_recorded": top_k_recorded,
        "observed_top_k": top_k_for_payload(payload, rows, result_lists, max_rank),
        "retriever_identity_recorded": retriever_identity_recorded,
        "retriever_identity": retriever_identity(payload, rows),
        "chunk_id_fields_observed": sorted(chunk_id_fields_observed),
        "artifact_exclusion_reasons": excluded_reasons,
        "non_reusable_reasons": non_reusable_reasons,
    }


def discover_candidate_paths(roots: Iterable[Path], *, output_report: Path) -> list[Path]:
    paths: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.resolve() == output_report.resolve():
                continue
            if path.name in EXCLUDED_CURRENT_PHASE_OUTPUT_NAMES:
                continue
            if path.suffix.lower() not in {".json", ".jsonl"}:
                continue
            lowered = path.name.lower()
            if lowered.startswith("rag_chunks_"):
                continue
            if not any(marker in lowered for marker in ("retrieval", "emit", "candidate_pool")):
                continue
            paths.append(path)
    return sorted(set(paths), key=lambda item: normalise_path(item))


def load_candidate_rows(path: Path) -> tuple[Any, list[dict[str, Any]], str | None]:
    try:
        if path.suffix.lower() == ".jsonl":
            rows = [dict(record) for record in iter_jsonl_objects(path)]
            query_rows = [row for row in rows if clean(row.get("query_id")) and result_list_for_row(row)]
            return {"format": "jsonl"}, query_rows, None
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - defensive inventory path
        return {}, [], f"load_error:{type(exc).__name__}:{exc}"

    rows: list[Any] = []
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        for field in ("query_results", "per_query", "records", "rows"):
            value = payload.get(field)
            if isinstance(value, list):
                rows = value
                break
    query_rows = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping) and clean(row.get("query_id")) and result_list_for_row(row)
    ]
    return payload, query_rows, None


def result_list_for_row(row: Mapping[str, Any]) -> list[Any]:
    for field in RESULT_LIST_FIELDS:
        value = row.get(field)
        if isinstance(value, list):
            return value
    return []


def chunk_ids_for_hit(hit: Mapping[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for field in CHUNK_ID_FIELDS:
        value = clean(hit.get(field))
        if value:
            out.append((value, field))
    return out


def excluded_artifact_reasons(path: Path, payload: Any, rows: list[dict[str, Any]]) -> list[str]:
    text_parts = [normalise_path(path).lower()]
    if isinstance(payload, dict):
        for field in ("gold_csv", "report_role", "scope", "phase", "retrieval_backend"):
            text_parts.append(clean(payload.get(field)).lower())
        validation = payload.get("validation")
        if isinstance(validation, Mapping):
            bucket_counts = validation.get("bucket_counts")
            if isinstance(bucket_counts, Mapping):
                text_parts.extend(str(key).lower() for key in bucket_counts)
    for row in rows[:20]:
        text_parts.append(clean(row.get("bucket")).lower())
        text_parts.append(clean(row.get("variant")).lower())
    combined = " ".join(part for part in text_parts if part)
    reasons: list[str] = []
    if "rag_text_retrieval_diagnostic_report.json" in combined or "gold_queries_text_e2e_v0.csv" in combined:
        reasons.append("b_app_smoke_artifact")
    if "xlsx" in combined:
        reasons.append("xlsx_artifact")
    if "pdf" in combined:
        reasons.append("pdf_artifact")
    if "file_lookup" in combined:
        reasons.append("file_lookup_artifact")
    if "full72" in combined:
        reasons.append("mixed_full72_artifact")
    if "human_gold_seed_50_tuning" in combined or "confirm_sweep" in combined or "7.8_retrieval_sanity" in combined:
        reasons.append("phase7_tuning_or_sanity_artifact")
    return sorted(set(reasons))


def top_k_for_payload(
    payload: Any,
    rows: list[dict[str, Any]],
    result_lists: list[list[Any]],
    max_rank: int,
) -> int | None:
    if isinstance(payload, dict):
        top_k = int_or_none(payload.get("top_k") or payload.get("k"))
        if top_k is not None:
            return top_k
    for row in rows:
        top_k = int_or_none(row.get("top_k") or row.get("k"))
        if top_k is not None:
            return top_k
    if max_rank:
        return max_rank
    lengths = {len(result_list) for result_list in result_lists if result_list}
    if len(lengths) == 1:
        return next(iter(lengths))
    return None


def retriever_identity(payload: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(payload, dict):
        for field in ("retrieval_backend_identity", "retriever_identity", "retriever_config"):
            value = payload.get(field)
            if isinstance(value, Mapping) and value:
                return dict(value)
        identity = {
            key: payload.get(key)
            for key in ("retrieval_backend", "retriever", "backend", "variant")
            if clean(payload.get(key))
        }
        if identity:
            return identity
    variants = sorted({clean(row.get("variant")) for row in rows if clean(row.get("variant"))})
    if variants:
        return {"variant": variants[0], "variant_count": len(variants)}
    return {}


def load_pages(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for record in iter_jsonl_objects(path):
        page_id = clean(record.get("page_id"))
        if page_id:
            out[page_id] = dict(record)
    return out


def load_rag_chunks(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for record in iter_jsonl_objects(path):
        chunk_id = clean(record.get("chunk_id"))
        if chunk_id:
            out[chunk_id] = dict(record)
    return out


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def read_optional_json(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def iter_jsonl_objects(path: Path) -> Iterable[Mapping[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: invalid JSON on line {line_no}: {exc}") from exc
            if not isinstance(record, Mapping):
                raise ValueError(f"{path}: line {line_no} must be an object")
            yield record


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clean(value: Any) -> str:
    return str(value or "").strip()


def normalise_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    sys.exit(main())
