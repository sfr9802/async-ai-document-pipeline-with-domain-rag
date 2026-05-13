"""Run Track B R5 fresh namu-v4 retrieval-only diagnostics.

The R5 contract is intentionally narrow:

* generate a fresh diagnostic retrieval emit for the R3 namu-v4 gold CSV;
* compute retrieval-only metrics over the positive denominator;
* do not reuse existing emits, run LLM answer evaluation, run citation
  evaluation, promote evidence, tune, or index.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent

DEFAULT_GOLD = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_text_namu_v4_v0.csv"
DEFAULT_CORPUS_DIR = AI_WORKER_ROOT / "eval" / "corpora" / "namu-v4-structured-combined"
DEFAULT_CORPUS_INVENTORY_REPORT = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_text_namu_v4_corpus_inventory_report.json"
)
DEFAULT_R3_VALIDATOR_REPORT = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_text_namu_v4_gold_validate_report.json"
)
DEFAULT_R4_INVENTORY_REPORT = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_text_namu_v4_retrieval_emit_inventory_report.json"
)
DEFAULT_FRESH_EMIT = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_text_namu_v4_retrieval_emit.jsonl"
)
DEFAULT_REPORT = (
    AI_WORKER_ROOT / "eval" / "reports" / "rag-ingestion" / "rag_text_namu_v4_retrieval_diagnostic_report.json"
)

EXPECTED_QUERY_COUNT = 50
EXPECTED_POSITIVE_DENOMINATOR = 47
EXPECTED_NEEDS_REVIEW_EXCLUDED = 3
POSITIVE_LABEL_STATUSES = {"bound"}
NEEDS_REVIEW_LABEL_STATUSES = {"needs_review"}
RETRIEVER_NAME = "fresh_diagnostic_lexical_bm25_title_section_v1"


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    doc_id: str
    page_id: str
    section_id: str
    section_path: list[str]
    title: str
    chunk_text: str
    search_text: str


@dataclass(frozen=True)
class LexicalIndex:
    chunks: list[ChunkRecord]
    postings: dict[str, list[tuple[int, int]]]
    doc_lengths: list[int]
    avg_doc_length: float

    @property
    def n_docs(self) -> int:
        return len(self.chunks)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_diagnostic(
        gold=Path(args.gold),
        corpus_dir=Path(args.corpus_dir),
        corpus_inventory_report=Path(args.corpus_inventory_report),
        r3_validator_report=Path(args.r3_validator_report),
        r4_inventory_report=Path(args.r4_inventory_report),
        fresh_emit=Path(args.fresh_emit),
        report_path=Path(args.report),
        top_k=args.top_k,
    )
    print_json(
        {
            "status": report["status"],
            "query_count": report["query_count"],
            "positive_denominator_count": report["positive_denominator_count"],
            "needs_review_excluded_count": report["needs_review_excluded_count"],
            "fresh_emit_path": report["fresh_emit_path"],
            "report": report["report_path"],
        }
    )
    return 0 if report["status"] in {"PASS", "PASS_WITH_WARNINGS"} else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--corpus-dir", default=str(DEFAULT_CORPUS_DIR))
    parser.add_argument("--corpus-inventory-report", default=str(DEFAULT_CORPUS_INVENTORY_REPORT))
    parser.add_argument("--r3-validator-report", default=str(DEFAULT_R3_VALIDATOR_REPORT))
    parser.add_argument("--r4-inventory-report", default=str(DEFAULT_R4_INVENTORY_REPORT))
    parser.add_argument("--fresh-emit", default=str(DEFAULT_FRESH_EMIT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--top-k", type=int, default=10)
    return parser.parse_args(argv)


def run_diagnostic(
    *,
    gold: Path,
    corpus_dir: Path,
    corpus_inventory_report: Path,
    r3_validator_report: Path,
    r4_inventory_report: Path,
    fresh_emit: Path,
    report_path: Path,
    top_k: int,
) -> dict[str, Any]:
    run_id = utc_run_id()
    generated_at = utc_timestamp()
    rows, columns = read_csv(gold)
    corpus_report = read_optional_json(corpus_inventory_report)
    r3_report = read_optional_json(r3_validator_report)
    r4_report = read_optional_json(r4_inventory_report)
    prerequisite_blockers = prerequisite_blockers_for(
        rows=rows,
        corpus_report=corpus_report,
        r3_report=r3_report,
        r4_report=r4_report,
        top_k=top_k,
    )

    if prerequisite_blockers:
        report = build_report(
            run_id=run_id,
            generated_at=generated_at,
            status="FAIL",
            gold=gold,
            corpus_dir=corpus_dir,
            corpus_inventory_report=corpus_inventory_report,
            r3_validator_report=r3_validator_report,
            r4_inventory_report=r4_inventory_report,
            fresh_emit=fresh_emit,
            report_path=report_path,
            rows=rows,
            columns=columns,
            top_k=top_k,
            metrics=empty_metrics(rows),
            query_results=[],
            needs_review_rows=needs_review_rows(rows),
            blockers=prerequisite_blockers,
            warnings=[],
            fresh_emit_written=False,
        )
        write_json(report_path, report)
        return report

    index = build_lexical_index(corpus_dir / "rag_chunks.jsonl")
    emit_rows, query_results, metrics = evaluate_rows(rows, index=index, top_k=top_k, run_id=run_id)
    write_jsonl(fresh_emit, emit_rows)
    fresh_emit_sha256 = sha256_file(fresh_emit)

    blockers: list[str] = []
    warnings: list[str] = []
    if metrics["retrieval_error_count"]:
        blockers.append(f"retrieval errors observed: {metrics['retrieval_error_count']}")
    if metrics["expected_not_in_corpus_count"]:
        blockers.append(f"expected evidence missing from corpus: {metrics['expected_not_in_corpus_count']}")
    if metrics["positive_denominator_count"] != EXPECTED_POSITIVE_DENOMINATOR:
        blockers.append(
            "positive denominator count mismatch: "
            f"{metrics['positive_denominator_count']} != {EXPECTED_POSITIVE_DENOMINATOR}"
        )
    if metrics["needs_review_excluded_count"] != EXPECTED_NEEDS_REVIEW_EXCLUDED:
        blockers.append(
            "needs_review excluded count mismatch: "
            f"{metrics['needs_review_excluded_count']} != {EXPECTED_NEEDS_REVIEW_EXCLUDED}"
        )
    if metrics["missing_expected_chunk_count"]:
        warnings.append(
            "Some positive rows did not retrieve an expected chunk within top_k; metric remains diagnostic-only."
        )
    if metrics["wrong_source_count"]:
        warnings.append(
            "Some positive rows returned top_k results but no expected page/source within top_k."
        )
    if metrics["empty_result_count"]:
        warnings.append("Some positive rows returned an empty result list.")

    status = "FAIL" if blockers else "PASS_WITH_WARNINGS" if warnings else "PASS"
    report = build_report(
        run_id=run_id,
        generated_at=generated_at,
        status=status,
        gold=gold,
        corpus_dir=corpus_dir,
        corpus_inventory_report=corpus_inventory_report,
        r3_validator_report=r3_validator_report,
        r4_inventory_report=r4_inventory_report,
        fresh_emit=fresh_emit,
        report_path=report_path,
        rows=rows,
        columns=columns,
        top_k=top_k,
        metrics={**metrics, "fresh_emit_sha256": fresh_emit_sha256},
        query_results=query_results,
        needs_review_rows=needs_review_rows(rows),
        blockers=blockers,
        warnings=warnings,
        fresh_emit_written=True,
    )
    write_json(report_path, report)
    return report


def prerequisite_blockers_for(
    *,
    rows: list[dict[str, str]],
    corpus_report: Mapping[str, Any],
    r3_report: Mapping[str, Any],
    r4_report: Mapping[str, Any],
    top_k: int,
) -> list[str]:
    blockers: list[str] = []
    if top_k < 10:
        blockers.append("top_k must be >= 10 so Hit@10 and MRR@10 are meaningful")
    if len(rows) != EXPECTED_QUERY_COUNT:
        blockers.append(f"gold query count mismatch: {len(rows)} != {EXPECTED_QUERY_COUNT}")
    if clean(corpus_report.get("status")) != "PASS":
        blockers.append(f"R2 corpus inventory status is {clean(corpus_report.get('status')) or 'MISSING'}, not PASS")
    if clean(r3_report.get("status")) != "PASSED":
        blockers.append(f"R3 validator status is {clean(r3_report.get('status')) or 'MISSING'}, not PASSED")
    if clean(r4_report.get("status")) != "NO_REUSABLE_EXISTING_EMIT":
        blockers.append(
            "R4 inventory status is "
            f"{clean(r4_report.get('status')) or 'MISSING'}, not NO_REUSABLE_EXISTING_EMIT"
        )
    if clean(r4_report.get("decision")) != "RUN_FRESH_DIAGNOSTIC_RETRIEVAL":
        blockers.append(
            "R4 inventory decision is "
            f"{clean(r4_report.get('decision')) or 'MISSING'}, not RUN_FRESH_DIAGNOSTIC_RETRIEVAL"
        )
    if r4_report.get("retrieval_metrics_computed") is not False:
        blockers.append("R4 inventory retrieval_metrics_computed must be false")
    if r4_report.get("promotion_evidence") is not False:
        blockers.append("R4 inventory promotion_evidence must be false")
    if clean(r4_report.get("evidence_role")) != "diagnostic":
        blockers.append("R4 inventory evidence_role must be diagnostic")
    return blockers


def evaluate_rows(
    rows: list[dict[str, str]],
    *,
    index: LexicalIndex,
    top_k: int,
    run_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    emit_rows: list[dict[str, Any]] = []
    query_results: list[dict[str, Any]] = []
    positive_results: list[dict[str, Any]] = []
    retrieval_error_count = 0

    chunk_ids_in_corpus = {chunk.chunk_id for chunk in index.chunks}
    doc_ids_in_corpus = {chunk.doc_id for chunk in index.chunks if chunk.doc_id}
    section_ids_in_corpus = {chunk.section_id for chunk in index.chunks if chunk.section_id}

    for row in rows:
        query_id = clean(row.get("query_id"))
        label_status = clean(row.get("label_status")).lower()
        allowed_abstain = clean(row.get("allowed_abstain")).lower() == "true"
        denominator_included = label_status in POSITIVE_LABEL_STATUSES and not allowed_abstain
        excluded_reason = denominator_exclusion_reason(label_status, allowed_abstain)
        expected_page_ids = split_semicolon(row.get("expected_page_ids"))
        expected_section_ids = split_semicolon(row.get("expected_section_ids"))
        expected_chunk_ids = split_semicolon(row.get("expected_chunk_ids"))
        retrieval_error: str | None = None

        try:
            hits = retrieve(index, clean(row.get("query")), top_k)
        except Exception as exc:  # pragma: no cover - defensive diagnostic isolation
            retrieval_error = f"{type(exc).__name__}: {exc}"
            retrieval_error_count += 1
            hits = []

        docs = [hit_to_emit_doc(hit, rank=rank) for rank, hit in enumerate(hits, start=1)]
        result = evaluate_query_result(
            row=row,
            docs=docs,
            expected_page_ids=expected_page_ids,
            expected_section_ids=expected_section_ids,
            expected_chunk_ids=expected_chunk_ids,
            denominator_included=denominator_included,
            excluded_reason=excluded_reason,
            retrieval_error=retrieval_error,
            chunk_ids_in_corpus=chunk_ids_in_corpus,
            doc_ids_in_corpus=doc_ids_in_corpus,
            section_ids_in_corpus=section_ids_in_corpus,
            top_k=top_k,
        )
        query_results.append(result)
        if denominator_included:
            positive_results.append(result)

        emit_rows.append(
            {
                "schema_version": "rag_text_namu_v4_retrieval_emit_v1",
                "run_id": run_id,
                "variant": RETRIEVER_NAME,
                "retrieval_backend": "fresh_diagnostic_lexical_bm25",
                "query_id": query_id,
                "query": clean(row.get("query")),
                "bucket": clean(row.get("bucket")),
                "label_status": label_status,
                "allowed_abstain": allowed_abstain,
                "denominator_included": denominator_included,
                "denominator_exclusion_reason": excluded_reason,
                "top_k": top_k,
                "docs": docs,
                "retrieval_error": retrieval_error,
            }
        )

    metrics = aggregate_metrics(rows, positive_results)
    metrics["retrieval_error_count"] = retrieval_error_count
    return emit_rows, query_results, metrics


def evaluate_query_result(
    *,
    row: Mapping[str, str],
    docs: list[dict[str, Any]],
    expected_page_ids: list[str],
    expected_section_ids: list[str],
    expected_chunk_ids: list[str],
    denominator_included: bool,
    excluded_reason: str | None,
    retrieval_error: str | None,
    chunk_ids_in_corpus: set[str],
    doc_ids_in_corpus: set[str],
    section_ids_in_corpus: set[str],
    top_k: int,
) -> dict[str, Any]:
    retrieved_doc_ids = [clean(doc.get("doc_id")) for doc in docs if clean(doc.get("doc_id"))]
    retrieved_section_ids = [clean(doc.get("section_id")) for doc in docs if clean(doc.get("section_id"))]
    retrieved_chunk_ids = [clean(doc.get("chunk_id")) for doc in docs if clean(doc.get("chunk_id"))]
    page_hit_rank = first_rank_for(expected_page_ids, docs, "doc_id")
    section_hit_rank = first_rank_for(expected_section_ids, docs, "section_id")
    chunk_hit_rank = first_rank_for(expected_chunk_ids, docs, "chunk_id")
    hit_rank = min_rank(page_hit_rank, chunk_hit_rank)
    expected_page_missing = sorted(page_id for page_id in expected_page_ids if page_id not in doc_ids_in_corpus)
    expected_section_missing = sorted(
        section_id for section_id in expected_section_ids if section_id not in section_ids_in_corpus
    )
    expected_chunk_missing = sorted(chunk_id for chunk_id in expected_chunk_ids if chunk_id not in chunk_ids_in_corpus)
    missing_expected_chunk = bool(expected_chunk_ids and chunk_hit_rank is None)
    wrong_source = bool(docs and expected_page_ids and page_hit_rank is None)
    empty_result = not docs and retrieval_error is None
    failure_reason = classify_failure_reason(
        retrieval_error=retrieval_error,
        empty_result=empty_result,
        hit_rank=hit_rank,
        page_hit_rank=page_hit_rank,
        chunk_hit_rank=chunk_hit_rank,
        expected_page_ids=expected_page_ids,
        expected_chunk_ids=expected_chunk_ids,
        expected_page_missing=expected_page_missing,
        expected_chunk_missing=expected_chunk_missing,
    )
    return {
        "query_id": clean(row.get("query_id")),
        "bucket": clean(row.get("bucket")),
        "query": clean(row.get("query")),
        "label_status": clean(row.get("label_status")).lower(),
        "allowed_abstain": clean(row.get("allowed_abstain")).lower() == "true",
        "denominator_included": denominator_included,
        "denominator_exclusion_reason": excluded_reason,
        "expected_page_ids": expected_page_ids,
        "expected_section_ids": expected_section_ids,
        "expected_chunk_ids": expected_chunk_ids,
        "expected_missing_from_corpus": {
            "page_ids": expected_page_missing,
            "section_ids": expected_section_missing,
            "chunk_ids": expected_chunk_missing,
        },
        "result_count": len(docs),
        "retrieved_doc_ids": retrieved_doc_ids[:top_k],
        "retrieved_section_ids": retrieved_section_ids[:top_k],
        "retrieved_chunk_ids": retrieved_chunk_ids[:top_k],
        "hit_rank": hit_rank,
        "source_hit_rank": page_hit_rank,
        "page_hit_rank": page_hit_rank,
        "section_hit_rank": section_hit_rank,
        "chunk_hit_rank": chunk_hit_rank,
        "source_recall@10": recall_at_k(expected_page_ids, retrieved_doc_ids[:10]),
        "page_recall@10": recall_at_k(expected_page_ids, retrieved_doc_ids[:10]),
        "section_recall@10": recall_at_k(expected_section_ids, retrieved_section_ids[:10]),
        "chunk_recall@10": recall_at_k(expected_chunk_ids, retrieved_chunk_ids[:10]),
        "empty_result": empty_result,
        "wrong_source": wrong_source,
        "missing_expected_chunk": missing_expected_chunk,
        "retrieval_error": retrieval_error,
        "final_match_outcome": final_match_outcome(hit_rank, retrieval_error),
        "failure_reason": failure_reason,
    }


def aggregate_metrics(rows: list[dict[str, str]], positive_results: list[dict[str, Any]]) -> dict[str, Any]:
    ranks = [optional_int(result.get("hit_rank")) for result in positive_results]
    page_ranks = [optional_int(result.get("page_hit_rank")) for result in positive_results]
    section_ranks = [optional_int(result.get("section_hit_rank")) for result in positive_results]
    chunk_ranks = [optional_int(result.get("chunk_hit_rank")) for result in positive_results]
    positive_denominator_count = len(positive_results)
    needs_review_excluded_count = sum(
        1
        for row in rows
        if clean(row.get("label_status")).lower() in NEEDS_REVIEW_LABEL_STATUSES
        or clean(row.get("allowed_abstain")).lower() == "true"
    )
    bucket_ranks: dict[str, list[int | None]] = defaultdict(list)
    for result in positive_results:
        bucket_ranks[clean(result.get("bucket"))].append(optional_int(result.get("hit_rank")))
    expected_not_in_corpus_count = sum(
        1
        for result in positive_results
        if result["expected_missing_from_corpus"]["page_ids"]
        or result["expected_missing_from_corpus"]["section_ids"]
        or result["expected_missing_from_corpus"]["chunk_ids"]
    )
    metrics = {
        "query_count": len(rows),
        "positive_denominator_count": positive_denominator_count,
        "needs_review_excluded_count": needs_review_excluded_count,
        "Hit@1": hit_at(ranks, 1),
        "Hit@3": hit_at(ranks, 3),
        "Hit@5": hit_at(ranks, 5),
        "Hit@10": hit_at(ranks, 10),
        "MRR@10": mrr_at(ranks, 10),
        "source_Hit@1": hit_at(page_ranks, 1),
        "source_Hit@3": hit_at(page_ranks, 3),
        "source_Hit@5": hit_at(page_ranks, 5),
        "source_Hit@10": hit_at(page_ranks, 10),
        "page_Hit@1": hit_at(page_ranks, 1),
        "page_Hit@3": hit_at(page_ranks, 3),
        "page_Hit@5": hit_at(page_ranks, 5),
        "page_Hit@10": hit_at(page_ranks, 10),
        "section_Hit@1": hit_at(section_ranks, 1),
        "section_Hit@3": hit_at(section_ranks, 3),
        "section_Hit@5": hit_at(section_ranks, 5),
        "section_Hit@10": hit_at(section_ranks, 10),
        "chunk_Hit@1": hit_at(chunk_ranks, 1),
        "chunk_Hit@3": hit_at(chunk_ranks, 3),
        "chunk_Hit@5": hit_at(chunk_ranks, 5),
        "chunk_Hit@10": hit_at(chunk_ranks, 10),
        "source_recall@10": mean(result["source_recall@10"] for result in positive_results),
        "page_recall@10": mean(result["page_recall@10"] for result in positive_results),
        "section_recall@10": mean(result["section_recall@10"] for result in positive_results),
        "chunk_recall@10": mean(result["chunk_recall@10"] for result in positive_results),
        "empty_result_count": sum(1 for result in positive_results if result["empty_result"]),
        "wrong_source_count": sum(1 for result in positive_results if result["wrong_source"]),
        "wrong_source_top1_count": sum(
            1
            for result in positive_results
            if result["result_count"] and result["page_hit_rank"] != 1
        ),
        "missing_expected_chunk_count": sum(
            1 for result in positive_results if result["missing_expected_chunk"]
        ),
        "expected_not_in_corpus_count": expected_not_in_corpus_count,
        "missing_chunk_resolution_count": 0,
        "retrieval_error_count": 0,
        "overall_hit_policy": "expected page/source OR expected chunk",
        "bucket_metrics": {
            bucket: {
                "positive_denominator_count": len(bucket_rank_list),
                "Hit@1": hit_at(bucket_rank_list, 1),
                "Hit@3": hit_at(bucket_rank_list, 3),
                "Hit@5": hit_at(bucket_rank_list, 5),
                "Hit@10": hit_at(bucket_rank_list, 10),
                "MRR@10": mrr_at(bucket_rank_list, 10),
            }
            for bucket, bucket_rank_list in sorted(bucket_ranks.items())
        },
    }
    return metrics


def empty_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    positive_count = sum(
        1
        for row in rows
        if clean(row.get("label_status")).lower() in POSITIVE_LABEL_STATUSES
        and clean(row.get("allowed_abstain")).lower() != "true"
    )
    needs_review_count = sum(
        1
        for row in rows
        if clean(row.get("label_status")).lower() in NEEDS_REVIEW_LABEL_STATUSES
        or clean(row.get("allowed_abstain")).lower() == "true"
    )
    return {
        "query_count": len(rows),
        "positive_denominator_count": positive_count,
        "needs_review_excluded_count": needs_review_count,
        "Hit@1": 0.0,
        "Hit@3": 0.0,
        "Hit@5": 0.0,
        "Hit@10": 0.0,
        "MRR@10": 0.0,
        "source_recall@10": 0.0,
        "page_recall@10": 0.0,
        "section_recall@10": 0.0,
        "chunk_recall@10": 0.0,
        "empty_result_count": 0,
        "wrong_source_count": 0,
        "missing_expected_chunk_count": 0,
        "expected_not_in_corpus_count": 0,
        "missing_chunk_resolution_count": 0,
        "retrieval_error_count": 0,
        "bucket_metrics": {},
    }


def build_report(
    *,
    run_id: str,
    generated_at: str,
    status: str,
    gold: Path,
    corpus_dir: Path,
    corpus_inventory_report: Path,
    r3_validator_report: Path,
    r4_inventory_report: Path,
    fresh_emit: Path,
    report_path: Path,
    rows: list[dict[str, str]],
    columns: list[str],
    top_k: int,
    metrics: Mapping[str, Any],
    query_results: list[dict[str, Any]],
    needs_review_rows: list[dict[str, Any]],
    blockers: list[str],
    warnings: list[str],
    fresh_emit_written: bool,
) -> dict[str, Any]:
    fresh_emit_sha256 = metrics.get("fresh_emit_sha256")
    report = {
        "run_id": run_id,
        "generated_at": generated_at,
        "schema_version": "rag_text_namu_v4_retrieval_diagnostic_v1",
        "status": status,
        "report_role": "rag_text_namu_v4_retrieval_diagnostic",
        "scope": "track_b_text_retrieval_e2e",
        "phase": "R5",
        "lane": "B_NAMU_TEXT_CONTENT",
        "retrieval_backend": "fresh_diagnostic_lexical_bm25",
        "retrieval_backend_identity": {
            "name": RETRIEVER_NAME,
            "fresh_emit_generated": fresh_emit_written,
            "corpus_source": "namu-v4-structured-combined/rag_chunks.jsonl",
            "search_fields": [
                "retrieval_title",
                "display_title",
                "title",
                "aliases",
                "section_path",
                "chunk_text",
            ],
            "context_source_field": "chunk_text",
            "implementation": "stdlib lexical BM25 diagnostic retriever",
        },
        "corpus": "namu-v4-structured-combined",
        "corpus_dir": repo_relative(corpus_dir),
        "context_source_field": "chunk_text",
        "gold_path": repo_relative(gold),
        "gold_csv": repo_relative(gold),
        "gold_sha256": sha256_if_exists(gold),
        "gold_columns": columns,
        "corpus_inventory_report_path": repo_relative(corpus_inventory_report),
        "corpus_inventory_report_sha256": sha256_if_exists(corpus_inventory_report),
        "r3_validator_report_path": repo_relative(r3_validator_report),
        "r3_validator_report_sha256": sha256_if_exists(r3_validator_report),
        "r4_inventory_report_path": repo_relative(r4_inventory_report),
        "r4_inventory_report_sha256": sha256_if_exists(r4_inventory_report),
        "fresh_emit_path": repo_relative(fresh_emit),
        "fresh_emit_sha256": fresh_emit_sha256,
        "report_path": repo_relative(report_path),
        "query_count": metrics["query_count"],
        "positive_denominator_count": metrics["positive_denominator_count"],
        "needs_review_excluded_count": metrics["needs_review_excluded_count"],
        "top_k": top_k,
        "Hit@1": metrics["Hit@1"],
        "Hit@3": metrics["Hit@3"],
        "Hit@5": metrics["Hit@5"],
        "Hit@10": metrics["Hit@10"],
        "MRR@10": metrics["MRR@10"],
        "source_recall@10": metrics["source_recall@10"],
        "page_recall@10": metrics["page_recall@10"],
        "section_recall@10": metrics["section_recall@10"],
        "chunk_recall@10": metrics["chunk_recall@10"],
        "empty_result_count": metrics["empty_result_count"],
        "wrong_source_count": metrics["wrong_source_count"],
        "missing_expected_chunk_count": metrics["missing_expected_chunk_count"],
        "retrieval_error_count": metrics["retrieval_error_count"],
        "reused_emit": False,
        "existing_emit_reused": False,
        "retrieval_metrics_computed": status != "FAIL" or bool(query_results),
        "llm_answer_eval_run": False,
        "citation_eval_run": False,
        "promotion_run": False,
        "indexing_run": False,
        "tuning_run": False,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "diagnostic_only": True,
        "denominator_policy": {
            "include_label_status": ["bound"],
            "exclude_label_status": ["needs_review"],
            "exclude_allowed_abstain_true": True,
            "positive_denominator_count": metrics["positive_denominator_count"],
            "needs_review_excluded_count": metrics["needs_review_excluded_count"],
            "policy_note": "needs_review rows remain excluded unless a later gold policy task changes them.",
        },
        "metrics": dict(metrics),
        "needs_review_rows": needs_review_rows,
        "query_results": query_results,
        "blockers": blockers,
        "warnings": warnings,
        "done_criteria": {
            "r3_validator_passed": not any("R3 validator status" in blocker for blocker in blockers),
            "r4_inventory_requires_fresh_diagnostic": not any("R4 inventory" in blocker for blocker in blockers),
            "fresh_emit_written": fresh_emit_written,
            "existing_emit_reused_false": True,
            "retrieval_metrics_computed": status != "FAIL" or bool(query_results),
            "positive_denominator_is_47": metrics["positive_denominator_count"] == EXPECTED_POSITIVE_DENOMINATOR,
            "needs_review_excluded_is_3": metrics["needs_review_excluded_count"] == EXPECTED_NEEDS_REVIEW_EXCLUDED,
            "promotion_evidence_false": True,
            "llm_answer_eval_not_run": True,
            "citation_eval_not_run": True,
            "promotion_not_run": True,
        },
        "next_phase_recommendation": (
            "Proceed to R6 context assembly using the fresh emit."
            if status in {"PASS", "PASS_WITH_WARNINGS"}
            else "Keep R6/R7/R8 blocked until R5 blockers are resolved."
        ),
    }
    return report


def build_lexical_index(path: Path) -> LexicalIndex:
    chunks: list[ChunkRecord] = []
    postings_by_token: dict[str, dict[int, int]] = defaultdict(dict)
    doc_lengths: list[int] = []
    for record in iter_jsonl_objects(path):
        chunk = chunk_record_from_json(record)
        index = len(chunks)
        chunks.append(chunk)
        token_counts = Counter(tokenize(chunk.search_text))
        doc_lengths.append(sum(token_counts.values()))
        for token, count in token_counts.items():
            postings_by_token[token][index] = count
    postings = {
        token: sorted(entries.items())
        for token, entries in postings_by_token.items()
    }
    avg_doc_length = mean(length for length in doc_lengths if length) or 1.0
    return LexicalIndex(chunks=chunks, postings=postings, doc_lengths=doc_lengths, avg_doc_length=avg_doc_length)


def chunk_record_from_json(record: Mapping[str, Any]) -> ChunkRecord:
    title = first_non_empty(
        record.get("retrieval_title"),
        record.get("display_title"),
        record.get("title"),
    )
    aliases = record.get("aliases") if isinstance(record.get("aliases"), list) else []
    section_path = [clean(part) for part in record.get("section_path") or [] if clean(part)]
    chunk_text = clean(record.get("chunk_text"))
    title_block = " ".join([title] * 4)
    alias_block = " ".join(clean(alias) for alias in aliases for _ in range(2) if clean(alias))
    section_block = " ".join(" ".join(section_path) for _ in range(2))
    search_text = " ".join(part for part in (title_block, alias_block, section_block, chunk_text) if part)
    doc_id = clean(record.get("doc_id") or record.get("page_id"))
    return ChunkRecord(
        chunk_id=clean(record.get("chunk_id")),
        doc_id=doc_id,
        page_id=doc_id,
        section_id=clean(record.get("section_id")),
        section_path=section_path,
        title=title,
        chunk_text=chunk_text,
        search_text=search_text,
    )


def retrieve(index: LexicalIndex, query: str, top_k: int) -> list[tuple[ChunkRecord, float]]:
    query_terms = Counter(tokenize(query))
    if not query_terms:
        return []
    scores: dict[int, float] = defaultdict(float)
    k1 = 1.5
    b = 0.75
    for token, query_tf in query_terms.items():
        postings = index.postings.get(token)
        if not postings:
            continue
        df = len(postings)
        idf = math.log(1.0 + (index.n_docs - df + 0.5) / (df + 0.5))
        query_boost = 1.0 + min(query_tf - 1, 3) * 0.15
        for doc_index, term_frequency in postings:
            doc_length = max(index.doc_lengths[doc_index], 1)
            denominator = term_frequency + k1 * (1 - b + b * doc_length / index.avg_doc_length)
            scores[doc_index] += idf * ((term_frequency * (k1 + 1)) / denominator) * query_boost
    if not scores:
        return []
    ranked = sorted(
        ((index.chunks[doc_index], score) for doc_index, score in scores.items()),
        key=lambda item: (-item[1], item[0].title, item[0].chunk_id),
    )
    return ranked[:top_k]


def hit_to_emit_doc(hit: tuple[ChunkRecord, float], *, rank: int) -> dict[str, Any]:
    chunk, score = hit
    return {
        "rank": rank,
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "page_id": chunk.page_id,
        "section_id": chunk.section_id,
        "section_path": chunk.section_path,
        "title": chunk.title,
        "score": round(float(score), 6),
        "context": chunk.chunk_text,
        "chunk_text": chunk.chunk_text,
    }


def denominator_exclusion_reason(label_status: str, allowed_abstain: bool) -> str | None:
    if allowed_abstain:
        return "allowed_abstain=true"
    if label_status in NEEDS_REVIEW_LABEL_STATUSES:
        return "label_status=needs_review"
    if label_status not in POSITIVE_LABEL_STATUSES:
        return f"label_status={label_status or 'missing'}"
    return None


def needs_review_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        label_status = clean(row.get("label_status")).lower()
        allowed_abstain = clean(row.get("allowed_abstain")).lower() == "true"
        if label_status in NEEDS_REVIEW_LABEL_STATUSES or allowed_abstain:
            out.append(
                {
                    "query_id": clean(row.get("query_id")),
                    "query": clean(row.get("query")),
                    "bucket": clean(row.get("bucket")),
                    "label_status": label_status,
                    "allowed_abstain": allowed_abstain,
                    "excluded_from_positive_denominator": True,
                }
            )
    return out


def classify_failure_reason(
    *,
    retrieval_error: str | None,
    empty_result: bool,
    hit_rank: int | None,
    page_hit_rank: int | None,
    chunk_hit_rank: int | None,
    expected_page_ids: list[str],
    expected_chunk_ids: list[str],
    expected_page_missing: list[str],
    expected_chunk_missing: list[str],
) -> str | None:
    if retrieval_error:
        return "retrieval_error"
    if expected_page_missing or expected_chunk_missing:
        return "expected_not_in_corpus"
    if hit_rank is not None:
        return None
    if empty_result:
        return "empty_result"
    if expected_chunk_ids and page_hit_rank is not None and chunk_hit_rank is None:
        return "expected_page_found_but_expected_chunk_missing"
    if expected_page_ids and page_hit_rank is None:
        return "expected_source_missing"
    if expected_chunk_ids and chunk_hit_rank is None:
        return "expected_chunk_missing"
    return "expected_evidence_missing"


def final_match_outcome(hit_rank: int | None, retrieval_error: str | None) -> str:
    if retrieval_error:
        return "retrieval_error"
    if hit_rank is not None:
        return "matched"
    return "not_matched"


def first_rank_for(expected_ids: list[str], docs: list[Mapping[str, Any]], field: str) -> int | None:
    if not expected_ids:
        return None
    expected = set(expected_ids)
    for doc in docs:
        if clean(doc.get(field)) in expected:
            return int(doc["rank"])
    return None


def min_rank(*ranks: int | None) -> int | None:
    values = [rank for rank in ranks if rank is not None]
    return min(values) if values else None


def hit_at(ranks: Iterable[int | None], k: int) -> float:
    values = list(ranks)
    return mean(rank is not None and rank <= k for rank in values)


def mrr_at(ranks: Iterable[int | None], k: int) -> float:
    return mean(1.0 / rank if rank is not None and rank <= k else 0.0 for rank in ranks)


def recall_at_k(expected_ids: list[str], observed_ids: list[str]) -> float:
    if not expected_ids:
        return 0.0
    return len(set(expected_ids) & set(observed_ids)) / len(set(expected_ids))


def mean(values: Iterable[float | bool | int]) -> float:
    items = [float(value) for value in values]
    return sum(items) / len(items) if items else 0.0


def optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for char in text.lower():
        if char.isalnum():
            current.append(char)
        else:
            if current:
                tokens.append("".join(current))
                current = []
    if current:
        tokens.append("".join(current))
    return tokens


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
                raise ValueError(f"{path}: line {line_no} must be a JSON object")
            yield record


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader], list(reader.fieldnames or [])


def read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def split_semicolon(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def clean(value: Any) -> str:
    return str(value or "").strip()


def first_non_empty(*values: Any) -> str:
    for value in values:
        if clean(value):
            return clean(value)
    return ""


def repo_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def sha256_if_exists(path: Path) -> str | None:
    return sha256_file(path) if path.exists() else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    sys.exit(main())
