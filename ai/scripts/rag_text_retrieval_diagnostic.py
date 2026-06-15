"""Run Track B B2 retrieval-only diagnostics for TEXT library search.

This script intentionally stops at retrieval. It calls the catalog
`/api/v1/library/search` endpoint with TEXT-only source type filters, compares
top-k results with the B1 gold source/chunk ids, and writes a diagnostic-only
report for later Track B phases.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


DEFAULT_GOLD = Path("eval/eval_queries/gold_queries_text_e2e_v0.csv")
DEFAULT_REPORT = Path("reports/rag_eval/rag-ingestion/rag_text_retrieval_diagnostic_report.json")
DEFAULT_BACKEND_IDENTITY_REPORT = Path("reports/rag_eval/rag-ingestion/rag_text_backend_identity_report.json")
DEFAULT_API_URL = "http://localhost:8080/api/v1/library/search"

REQUIRED_COLUMNS = [
    "query_id",
    "bucket",
    "query",
    "expected_source_ids",
    "expected_chunk_ids",
    "allowed_abstain",
    "label_status",
]

TEXT_TYPES = {"TEXT", "TXT", "MARKDOWN", "MD"}
TEXT_TYPE_ALIASES = ["MARKDOWN", "MD", "TEXT", "TXT"]
PDF_TYPES = {"PDF", "OCR"}
XLSX_TYPES = {"SPREADSHEET", "XLSX", "XLSM"}


SearchFn = Callable[[str, int], list[dict[str, Any]]]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    gold_path = Path(args.gold)
    rows, columns = read_csv(gold_path)
    validation = validate_gold_rows(rows, columns)
    backend_identity_report = read_json(Path(args.backend_identity_report))
    source_file_types = normalize_source_file_types(args.source_file_type)

    if validation["ok"]:
        search_fn = search_library(
            args.api_url,
            source_file_types=source_file_types,
            timeout_seconds=args.timeout_seconds,
        )
        evaluation = evaluate_rows(rows, search_fn=search_fn, top_k=args.top_k)
    else:
        evaluation = empty_evaluation(rows)

    payload = build_report(
        gold=gold_path,
        rows=rows,
        columns=columns,
        validation=validation,
        evaluation=evaluation,
        backend=args.backend,
        backend_identity_report=backend_identity_report,
        backend_identity_report_path=Path(args.backend_identity_report),
        source_file_types=source_file_types,
        top_k=args.top_k,
        api_url=args.api_url,
    )
    write_json(Path(args.report), payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "COMPLETED" else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--backend", default="library_search")
    parser.add_argument("--backend-identity-report", default=str(DEFAULT_BACKEND_IDENTITY_REPORT))
    parser.add_argument("--source-file-type", action="append", default=["TEXT"])
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    return parser.parse_args(argv)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def validate_gold_rows(rows: list[dict[str, str]], columns: list[str]) -> dict[str, Any]:
    missing_required_columns = [column for column in REQUIRED_COLUMNS if column not in columns]
    row_errors: dict[str, list[str]] = defaultdict(list)
    query_ids: list[str] = []
    for index, row in enumerate(rows, start=2):
        query_id = clean(row.get("query_id")) or f"<row:{index}>"
        query_ids.append(query_id)
        if not clean(row.get("query_id")):
            row_errors[query_id].append("query_id is required")
        if not clean(row.get("bucket")):
            row_errors[query_id].append("bucket is required")
        if not clean(row.get("query")):
            row_errors[query_id].append("query is required")
        if clean(row.get("allowed_abstain")).lower() not in {"true", "false"}:
            row_errors[query_id].append("allowed_abstain must be true or false")
    duplicate_query_ids = sorted(
        query_id for query_id, count in Counter(query_ids).items() if query_id and count > 1
    )
    for query_id in duplicate_query_ids:
        row_errors[query_id].append("duplicate query_id")
    if missing_required_columns:
        row_errors["__dataset__"].append(
            "missing required columns: " + ", ".join(missing_required_columns)
        )
    return {
        "ok": not row_errors,
        "row_count": len(rows),
        "missing_required_columns": missing_required_columns,
        "duplicate_query_ids": duplicate_query_ids,
        "row_errors": dict(row_errors),
        "bucket_counts": dict(sorted(Counter(clean(row.get("bucket")) or "unknown" for row in rows).items())),
    }


def evaluate_rows(rows: list[dict[str, str]], *, search_fn: SearchFn, top_k: int) -> dict[str, Any]:
    query_results: list[dict[str, Any]] = []
    ranks: list[int | None] = []
    source_ranks: list[int | None] = []
    chunk_ranks: list[int | None] = []
    source_recalls: list[float] = []
    chunk_recalls: list[float] = []
    bucket_ranks: dict[str, list[int | None]] = defaultdict(list)
    bucket_source_ranks: dict[str, list[int | None]] = defaultdict(list)
    bucket_chunk_ranks: dict[str, list[int | None]] = defaultdict(list)
    bucket_source_recalls: dict[str, list[float]] = defaultdict(list)
    bucket_chunk_recalls: dict[str, list[float]] = defaultdict(list)
    failure_reason_counts: Counter[str] = Counter()
    bucket_failure_reason_counts: dict[str, Counter[str]] = defaultdict(Counter)

    result_empty_count = 0
    wrong_source_top1_count = 0
    path_mixing_count = 0
    path_mixing_result_count = 0
    search_error_count = 0
    evidence_query_count = 0
    abstain_query_count = 0

    for row in rows:
        bucket = clean(row.get("bucket"))
        expected_source_ids = split_semicolon(row.get("expected_source_ids"))
        expected_chunk_ids = split_semicolon(row.get("expected_chunk_ids"))
        has_expected_evidence = bool(expected_source_ids or expected_chunk_ids)
        if has_expected_evidence:
            evidence_query_count += 1
        if clean(row.get("allowed_abstain")).lower() == "true":
            abstain_query_count += 1

        search_error = None
        try:
            hits = search_fn(row.get("query", ""), top_k)
        except Exception as exc:  # pragma: no cover - live service resilience
            search_error = f"{type(exc).__name__}: {exc}"
            hits = []
            search_error_count += 1

        top_k_hits = hits[:top_k]
        hit_details = [
            summarize_hit(
                hit,
                rank=rank,
                expected_source_ids=expected_source_ids,
                expected_chunk_ids=expected_chunk_ids,
            )
            for rank, hit in enumerate(top_k_hits, start=1)
        ]
        mixed_hits = [hit for hit in hit_details if not hit["match_breakdown"]["text_type_ok"]]
        if mixed_hits:
            path_mixing_count += 1
            path_mixing_result_count += len(mixed_hits)
        if not top_k_hits and search_error is None:
            result_empty_count += 1

        source_hit_rank = first_rank(hit_details, "source_id_match")
        chunk_hit_rank = first_rank(hit_details, "chunk_id_match")
        hit_rank = min_rank(source_hit_rank, chunk_hit_rank)
        source_recall = recall_at_k(expected_source_ids, [hit["source_file_id"] for hit in hit_details])
        chunk_recall = recall_at_k(expected_chunk_ids, [hit["search_unit_id"] for hit in hit_details])
        top1_source_id = hit_details[0]["source_file_id"] if hit_details else None
        wrong_source_top1 = bool(
            expected_source_ids
            and top1_source_id
            and top1_source_id not in expected_source_ids
        )
        if wrong_source_top1:
            wrong_source_top1_count += 1

        failure_reason = classify_failure_reason(
            has_expected_evidence=has_expected_evidence,
            search_error=search_error,
            hit_rank=hit_rank,
            hit_details=hit_details,
            expected_source_ids=expected_source_ids,
            expected_chunk_ids=expected_chunk_ids,
        )
        if failure_reason:
            failure_reason_counts[failure_reason] += 1
            bucket_failure_reason_counts[bucket][failure_reason] += 1

        if has_expected_evidence:
            ranks.append(hit_rank)
            bucket_ranks[bucket].append(hit_rank)
            if expected_source_ids:
                source_ranks.append(source_hit_rank)
                bucket_source_ranks[bucket].append(source_hit_rank)
                source_recalls.append(source_recall)
                bucket_source_recalls[bucket].append(source_recall)
            if expected_chunk_ids:
                chunk_ranks.append(chunk_hit_rank)
                bucket_chunk_ranks[bucket].append(chunk_hit_rank)
                chunk_recalls.append(chunk_recall)
                bucket_chunk_recalls[bucket].append(chunk_recall)

        query_results.append({
            "query_id": clean(row.get("query_id")),
            "bucket": bucket,
            "query": clean(row.get("query")),
            "allowed_abstain": clean(row.get("allowed_abstain")).lower() == "true",
            "label_status": clean(row.get("label_status")),
            "expected_source_ids": expected_source_ids,
            "expected_chunk_ids": expected_chunk_ids,
            "has_expected_evidence": has_expected_evidence,
            "result_count": len(top_k_hits),
            "top_k_results": hit_details,
            "hit_rank": hit_rank,
            "source_hit_rank": source_hit_rank,
            "chunk_hit_rank": chunk_hit_rank,
            "source_recall@10": source_recall if expected_source_ids else None,
            "chunk_recall@10": chunk_recall if expected_chunk_ids else None,
            "wrong_source_top1": wrong_source_top1,
            "path_mixing": bool(mixed_hits),
            "path_mixing_result_count": len(mixed_hits),
            "final_match_outcome": final_match_outcome(has_expected_evidence, hit_rank, search_error),
            "failure_reason": failure_reason,
            "search_error": search_error,
        })

    metrics = {
        "query_count": len(rows),
        "evidence_query_count": evidence_query_count,
        "abstain_query_count": abstain_query_count,
        "Hit@1": hit_at(ranks, 1),
        "Hit@3": hit_at(ranks, 3),
        "Hit@5": hit_at(ranks, 5),
        "Hit@10": hit_at(ranks, 10),
        "MRR@10": mrr_at(ranks, 10),
        "overall_hit_policy": "expected source OR expected chunk",
        "source_Hit@1": hit_at(source_ranks, 1),
        "source_Hit@3": hit_at(source_ranks, 3),
        "source_Hit@5": hit_at(source_ranks, 5),
        "source_Hit@10": hit_at(source_ranks, 10),
        "source_MRR@10": mrr_at(source_ranks, 10),
        "chunk_Hit@1": hit_at(chunk_ranks, 1),
        "chunk_Hit@3": hit_at(chunk_ranks, 3),
        "chunk_Hit@5": hit_at(chunk_ranks, 5),
        "chunk_Hit@10": hit_at(chunk_ranks, 10),
        "chunk_MRR@10": mrr_at(chunk_ranks, 10),
        "source_recall@10": mean(source_recalls),
        "chunk_recall@10": mean(chunk_recalls),
        "result_empty_count": result_empty_count,
        "wrong_source_top1_count": wrong_source_top1_count,
        "path_mixing_count": path_mixing_count,
        "path_mixing_result_count": path_mixing_result_count,
        "search_error_count": search_error_count,
        "overall_failure_reason_counts": dict(sorted(failure_reason_counts.items())),
        "bucket_failure_reason_counts": {
            bucket_name: dict(sorted(counter.items()))
            for bucket_name, counter in sorted(bucket_failure_reason_counts.items())
        },
    }
    bucket_metrics = {
        bucket: {
            "count": len(bucket_rank_list),
            "Hit@1": hit_at(bucket_rank_list, 1),
            "Hit@3": hit_at(bucket_rank_list, 3),
            "Hit@5": hit_at(bucket_rank_list, 5),
            "Hit@10": hit_at(bucket_rank_list, 10),
            "MRR@10": mrr_at(bucket_rank_list, 10),
            "overall_hit_policy": "expected source OR expected chunk",
            "source_Hit@10": hit_at(bucket_source_ranks.get(bucket, []), 10),
            "source_MRR@10": mrr_at(bucket_source_ranks.get(bucket, []), 10),
            "chunk_Hit@10": hit_at(bucket_chunk_ranks.get(bucket, []), 10),
            "chunk_MRR@10": mrr_at(bucket_chunk_ranks.get(bucket, []), 10),
            "source_recall@10": mean(bucket_source_recalls.get(bucket, [])),
            "chunk_recall@10": mean(bucket_chunk_recalls.get(bucket, [])),
            **(
                {"bucket_failure_reason_counts": dict(sorted(bucket_failure_reason_counts[bucket].items()))}
                if bucket_failure_reason_counts.get(bucket)
                else {}
            ),
        }
        for bucket, bucket_rank_list in sorted(bucket_ranks.items())
    }
    return {
        "metrics": metrics,
        "bucket_metrics": bucket_metrics,
        "query_results": query_results,
    }


def empty_evaluation(rows: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "metrics": {
            "query_count": len(rows),
            "evidence_query_count": 0,
            "abstain_query_count": 0,
            "Hit@1": 0.0,
            "Hit@3": 0.0,
            "Hit@5": 0.0,
            "Hit@10": 0.0,
            "MRR@10": 0.0,
            "overall_hit_policy": "expected source OR expected chunk",
            "source_Hit@1": 0.0,
            "source_Hit@3": 0.0,
            "source_Hit@5": 0.0,
            "source_Hit@10": 0.0,
            "source_MRR@10": 0.0,
            "chunk_Hit@1": 0.0,
            "chunk_Hit@3": 0.0,
            "chunk_Hit@5": 0.0,
            "chunk_Hit@10": 0.0,
            "chunk_MRR@10": 0.0,
            "source_recall@10": 0.0,
            "chunk_recall@10": 0.0,
            "result_empty_count": 0,
            "wrong_source_top1_count": 0,
            "path_mixing_count": 0,
            "path_mixing_result_count": 0,
            "search_error_count": 0,
            "overall_failure_reason_counts": {},
            "bucket_failure_reason_counts": {},
        },
        "bucket_metrics": {},
        "query_results": [],
    }


def build_report(
    *,
    gold: Path,
    rows: list[dict[str, str]],
    columns: list[str],
    validation: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    backend: str,
    backend_identity_report: Mapping[str, Any],
    backend_identity_report_path: Path,
    source_file_types: list[str],
    top_k: int,
    api_url: str,
) -> dict[str, Any]:
    metrics = dict(evaluation.get("metrics") or {})
    backend_identity = backend_identity_report.get("retrieval_backend_identity") or backend_identity_report.get(
        "backend_identity",
        {},
    )
    backend_blockers = list(backend_identity_report.get("blockers") or [])
    validation_errors = [
        error
        for errors in (validation.get("row_errors") or {}).values()
        for error in errors
    ]
    blockers = [*validation_errors]
    if backend_blockers:
        blockers.extend(f"backend identity blocker: {blocker}" for blocker in backend_blockers)
    if metrics.get("search_error_count", 0) > 0:
        blockers.append(f"search errors observed: {metrics['search_error_count']}")
    if metrics.get("path_mixing_count", 0) > 0:
        blockers.append(f"TEXT-only search returned mixed source types: {metrics['path_mixing_count']} queries")
    status = "COMPLETED"
    if not validation.get("ok"):
        status = "VALIDATION_FAILED"
    elif metrics.get("search_error_count", 0) > 0:
        status = "COMPLETED_WITH_SEARCH_ERRORS"
    elif blockers:
        status = "COMPLETED_WITH_BLOCKERS"
    next_phase_recommendation = next_phase_recommendation_for_status(status, metrics)
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "schema_version": "rag_text_retrieval_diagnostic_v1",
        "status": status,
        "report_role": "rag_text_retrieval_diagnostic",
        "scope": "track_b_text_retrieval_e2e",
        "phase": "B2",
        "retrieval_backend": backend,
        "retrieval_backend_identity": backend_identity,
        "backend_identity_report": str(backend_identity_report_path).replace("\\", "/"),
        "backend_identity_status": backend_identity_report.get("status"),
        "gold_csv": str(gold).replace("\\", "/"),
        "gold_csv_sha256": sha256_file(gold),
        "gold_columns": columns,
        "top_k": top_k,
        "source_file_types": source_file_types,
        "api_url": api_url,
        "smoke_only": smoke_only_backend(backend, backend_identity_report),
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "validation": validation,
        "metrics": metrics,
        "bucket_metrics": evaluation.get("bucket_metrics") or {},
        "query_results": evaluation.get("query_results") or [],
        "blockers": blockers,
        "warnings": [
            "library_search is lexical diagnostic evidence and not vector promotion evidence.",
            "B2 measures retrieval only; answer correctness and citation support are out of scope.",
            "B1 gold ids are local live-catalog bindings and may need rebind on a clean DB.",
            "Overall Hit@K/MRR use expected source OR expected chunk; source_* and chunk_* metrics keep those dimensions separate.",
        ],
        "done_criteria": {
            "query_results_exist": bool(evaluation.get("query_results")),
            "hit_at_k_and_mrr_calculated": all(
                key in metrics for key in ("Hit@1", "Hit@3", "Hit@5", "Hit@10", "MRR@10")
            ),
            "source_chunk_hit_separated": bool(evaluation.get("query_results")),
            "failure_reason_exists_for_miss_cases": failure_reason_exists_for_miss_cases(
                evaluation.get("query_results") or []
            ),
            "retrieval_backend_identity_included": bool(backend_identity),
            "promotion_evidence_false": True,
        },
        "next_phase_recommendation": next_phase_recommendation,
    }


def search_library(
    api_url: str,
    *,
    source_file_types: list[str],
    timeout_seconds: float,
) -> SearchFn:
    def _search(query: str, top_k: int) -> list[dict[str, Any]]:
        url = library_search_url(
            api_url,
            query,
            top_k,
            source_file_types=source_file_types,
        )
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:  # noqa: S310 - local diagnostic URL
            payload = json.loads(response.read().decode("utf-8"))
        return list(payload.get("results") or [])

    return _search


def library_search_url(
    api_url: str,
    query: str,
    limit: int,
    *,
    source_file_types: Iterable[str],
) -> str:
    params: list[tuple[str, str]] = [("query", query), ("limit", str(limit))]
    params.extend(("sourceFileTypes", item) for item in source_file_types)
    return api_url + "?" + urllib.parse.urlencode(params)


def summarize_hit(
    hit: Mapping[str, Any],
    *,
    rank: int,
    expected_source_ids: list[str],
    expected_chunk_ids: list[str],
) -> dict[str, Any]:
    source = hit.get("sourceFile") or {}
    unit = hit.get("searchUnit") or {}
    citation = unit.get("citation") or {}
    source_file_id = clean_any(unit.get("sourceFileId") or source.get("sourceFileId") or source.get("id"))
    search_unit_id = clean_any(
        unit.get("searchUnitId")
        or unit.get("unitId")
        or unit.get("id")
        or citation.get("searchUnitId")
        or citation.get("unitId")
    )
    source_type = source_type_from_hit(hit)
    source_match = source_file_id in expected_source_ids if expected_source_ids else False
    chunk_match = search_unit_id in expected_chunk_ids if expected_chunk_ids else False
    return {
        "rank": rank,
        "source_file_id": source_file_id,
        "source_file_name": source.get("originalFileName"),
        "search_unit_id": search_unit_id,
        "source_file_type": source_type,
        "unit_type": unit.get("unitType"),
        "unit_key": unit.get("unitKey"),
        "chunk_type": unit.get("chunkType"),
        "location_type": unit.get("locationType"),
        "citation_text": unit.get("citationText") or citation.get("citationText"),
        "text_preview": unit.get("textPreview"),
        "match_breakdown": {
            "source_id_match": source_match,
            "chunk_id_match": chunk_match,
            "expected_evidence_match": source_match or chunk_match,
            "text_type_ok": normalize_source_type(source_type) in TEXT_TYPES,
        },
    }


def classify_failure_reason(
    *,
    has_expected_evidence: bool,
    search_error: str | None,
    hit_rank: int | None,
    hit_details: list[dict[str, Any]],
    expected_source_ids: list[str],
    expected_chunk_ids: list[str],
) -> str | None:
    if search_error:
        return "search_error"
    if not has_expected_evidence:
        return None
    if hit_rank is not None:
        return None
    if not hit_details:
        return "search_result_empty"
    any_source_hit = any(hit["match_breakdown"]["source_id_match"] for hit in hit_details)
    any_chunk_hit = any(hit["match_breakdown"]["chunk_id_match"] for hit in hit_details)
    if expected_chunk_ids and any_source_hit and not any_chunk_hit:
        return "expected_chunk_not_found"
    if expected_source_ids and not any_source_hit:
        return "expected_source_not_found"
    return "expected_evidence_not_found"


def final_match_outcome(
    has_expected_evidence: bool,
    hit_rank: int | None,
    search_error: str | None,
) -> str:
    if search_error:
        return "search_error"
    if not has_expected_evidence:
        return "not_evaluable_no_expected_evidence"
    if hit_rank is not None:
        return "matched"
    return "not_matched"


def first_rank(hit_details: list[dict[str, Any]], key: str) -> int | None:
    for hit in hit_details:
        if hit["match_breakdown"].get(key):
            return int(hit["rank"])
    return None


def min_rank(*ranks: int | None) -> int | None:
    values = [rank for rank in ranks if rank is not None]
    return min(values) if values else None


def hit_at(ranks: list[int | None], k: int) -> float:
    return mean([rank is not None and rank <= k for rank in ranks])


def mrr_at(ranks: list[int | None], k: int) -> float:
    return mean([1.0 / rank if rank is not None and rank <= k else 0.0 for rank in ranks])


def recall_at_k(expected_ids: list[str], observed_ids: list[str]) -> float:
    if not expected_ids:
        return 0.0
    observed = set(item for item in observed_ids if item)
    return len(set(expected_ids) & observed) / len(set(expected_ids))


def mean(values: Iterable[float | bool]) -> float:
    items = [float(item) for item in values]
    return sum(items) / len(items) if items else 0.0


def source_type_from_hit(hit: Mapping[str, Any]) -> str:
    source = hit.get("sourceFile") or {}
    unit = hit.get("searchUnit") or {}
    return normalize_source_type(unit.get("sourceFileType") or source.get("fileType") or hit.get("sourceFileType"))


def normalize_source_file_types(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        source_type = normalize_source_type(value)
        if source_type not in TEXT_TYPES:
            raise ValueError(
                "Track B TEXT retrieval diagnostic accepts only TEXT/TXT/MARKDOWN/MD source types; "
                f"got {source_type}"
            )
        aliases = TEXT_TYPE_ALIASES if source_type in TEXT_TYPES else [source_type]
        for alias in aliases:
            if alias not in normalized:
                normalized.append(alias)
    return normalized


def next_phase_recommendation_for_status(status: str, metrics: Mapping[str, Any]) -> str:
    if status == "COMPLETED":
        if int(metrics.get("evidence_query_count") or 0) > 0 and float(metrics.get("Hit@10") or 0.0) == 0.0:
            return (
                "B2 completed, but no expected evidence was retrieved; review lexical query matching before B3."
            )
        return "Proceed to B3 context assembly with this diagnostic retrieval report."
    if status == "COMPLETED_WITH_BLOCKERS":
        return "Keep B3 blocked until B2 blockers, especially path mixing/backend identity blockers, are resolved."
    return "Keep B3 blocked until B2 completes without validation or search errors."


def normalize_source_type(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    normalized = str(value).strip().upper()
    return normalized or "UNKNOWN"


def split_semicolon(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def clean(value: str | None) -> str:
    return (value or "").strip()


def clean_any(value: Any) -> str:
    return "" if value is None else str(value).strip()


def smoke_only_backend(backend: str, backend_identity_report: Mapping[str, Any]) -> bool:
    candidate_backends = backend_identity_report.get("candidate_backends") or {}
    candidate = candidate_backends.get(backend) or {}
    return candidate.get("operational_role") == "smoke_only"


def failure_reason_exists_for_miss_cases(query_results: list[Mapping[str, Any]]) -> bool:
    for result in query_results:
        if result.get("final_match_outcome") == "not_matched" and not result.get("failure_reason"):
            return False
    return True


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    sys.exit(main())
