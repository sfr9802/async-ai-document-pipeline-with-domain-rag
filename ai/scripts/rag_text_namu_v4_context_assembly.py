"""Assemble Track B R6 B3-namu diagnostic contexts from the R5 fresh emit.

This phase is file-based only. It joins R5 top-k chunk ids back to the R2
namu-v4 ``rag_chunks.jsonl`` fixture and writes answer-context candidates from
``chunk_text`` only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent

DEFAULT_GOLD = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_text_namu_v4_v0.csv"
DEFAULT_CORPUS_INVENTORY_REPORT = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_corpus_inventory_report.json"
)
DEFAULT_GOLD_VALIDATOR_REPORT = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_gold_validate_report.json"
)
DEFAULT_R5_FRESH_EMIT = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_retrieval_emit.jsonl"
)
DEFAULT_R5_REPORT = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_retrieval_diagnostic_report.json"
)
DEFAULT_CONTEXT_EMIT = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_context_assembly.jsonl"
)
DEFAULT_REPORT = (
    AI_WORKER_ROOT.parent / "reports" / "rag_eval" / "rag-ingestion" / "rag_text_namu_v4_context_assembly_report.json"
)

PHASE = "R6_B3_NAMU_CONTEXT_ASSEMBLY"
EXPECTED_QUERY_COUNT = 50
EXPECTED_POSITIVE_DENOMINATOR = 47
EXPECTED_NEEDS_REVIEW_EXCLUDED = 3
EXPECTED_NEEDS_REVIEW_QUERY_IDS = ["gold_seed_0048", "gold_seed_0049", "gold_seed_0050"]
EXPECTED_R5_WARNING_CARRYOVER = {
    "wrong_source_count": 10,
    "missing_expected_chunk_count": 18,
    "empty_result_count": 0,
    "retrieval_error_count": 0,
}
CONTEXT_FIELD = "chunk_text"
DISALLOWED_CONTEXT_FIELDS = ["embedding_text", "text_for_embedding", "debug_text"]
POSITIVE_LABEL_STATUSES = {"bound"}
NEEDS_REVIEW_LABEL_STATUSES = {"needs_review"}

C4_FORBIDDEN_PATHS = [
    "ai/scripts/pdf_candidate_",
    "ai/scripts/rag_scoped_candidate_indexing.py",
    "ai/scripts/search_unit_indexing.py",
    "ai/tests/test_pdf_candidate_",
    "ai/tests/test_search_unit_indexing_loop.py",
    "ai/eval/indexes/rag-data-pdf-candidate-v1",
    "reports/rag_eval/rag-ingestion/pdf_candidate_embedding_consistency.json",
    "reports/rag_eval/rag-ingestion/pdf_vector_metadata_projection_readiness.json",
    "reports/rag_eval/rag-ingestion/rag_pdf_embedding_text_contract_audit.json",
    "reports/rag_eval/rag-ingestion/rag_pdf_search_unit_surface_repair_report.json",
    "docs/track-c-pdf-embedding-preparation/",
]


@dataclass(frozen=True)
class ChunkContext:
    chunk_id: str
    doc_id: str
    section_id: str
    section_path: list[str]
    title: str
    chunk_text: str


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_context_assembly(
        gold=Path(args.gold),
        corpus_inventory_report=Path(args.corpus_inventory_report),
        gold_validator_report=Path(args.gold_validator_report),
        r5_fresh_emit=Path(args.r5_fresh_emit),
        r5_report=Path(args.r5_report),
        context_emit=Path(args.context_emit),
        report_path=Path(args.report),
        context_field=args.context_field,
        max_context_chars=args.max_context_chars,
    )
    print_json(
        {
            "status": report["status"],
            "context_emit_path": report["context_emit_path"],
            "report": repo_relative(Path(args.report)),
            "positive_denominator_count": report["positive_denominator_count"],
            "needs_review_excluded_count": report["needs_review_excluded_count"],
            "r7_ready": report["r7_ready"],
        }
    )
    return 0 if report["status"] in {"PASS", "PASS_WITH_WARNINGS"} else 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--corpus-inventory-report", default=str(DEFAULT_CORPUS_INVENTORY_REPORT))
    parser.add_argument("--gold-validator-report", default=str(DEFAULT_GOLD_VALIDATOR_REPORT))
    parser.add_argument("--r5-fresh-emit", default=str(DEFAULT_R5_FRESH_EMIT))
    parser.add_argument("--r5-report", default=str(DEFAULT_R5_REPORT))
    parser.add_argument("--context-emit", default=str(DEFAULT_CONTEXT_EMIT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--context-field", default=CONTEXT_FIELD)
    parser.add_argument(
        "--max-context-chars",
        type=int,
        default=0,
        help="0 disables truncation; positive values cap assembled text chars per query.",
    )
    return parser.parse_args(argv)


def run_context_assembly(
    *,
    gold: Path,
    corpus_inventory_report: Path,
    gold_validator_report: Path,
    r5_fresh_emit: Path,
    r5_report: Path,
    context_emit: Path,
    report_path: Path,
    context_field: str = CONTEXT_FIELD,
    max_context_chars: int = 0,
) -> dict[str, Any]:
    run_id = utc_run_id()
    generated_at = utc_timestamp()
    rows, columns = read_csv_if_exists(gold)
    corpus_report = read_optional_json(corpus_inventory_report)
    validator_report = read_optional_json(gold_validator_report)
    r5_payload = read_optional_json(r5_report)
    emit_rows = read_jsonl_if_exists(r5_fresh_emit)

    blockers: list[str] = []
    warnings: list[str] = []
    if context_field != CONTEXT_FIELD:
        blockers.append(f"context_field must be chunk_text, got {context_field}")
    blockers.extend(entry_gate_blockers(rows, corpus_report, validator_report, r5_payload, r5_fresh_emit, emit_rows))

    corpus_path = resolve_corpus_rag_chunks_path(corpus_report)
    if corpus_path is None:
        blockers.append("R2 corpus inventory report does not identify rag_chunks.jsonl")
    elif not corpus_path.exists():
        blockers.append(f"rag_chunks.jsonl does not exist: {repo_relative(corpus_path)}")

    if blockers:
        status = "FAIL" if context_field != CONTEXT_FIELD else "BLOCKED"
        report = build_report(
            run_id=run_id,
            generated_at=generated_at,
            status=status,
            gold=gold,
            corpus_inventory_report=corpus_inventory_report,
            gold_validator_report=gold_validator_report,
            r5_fresh_emit=r5_fresh_emit,
            r5_report=r5_report,
            context_emit=context_emit,
            context_field=context_field,
            max_context_chars=max_context_chars,
            rows=rows,
            context_rows=[],
            metrics=empty_metrics(rows),
            needs_review_rows=needs_review_rows(rows),
            blockers=blockers,
            warnings=warnings,
            r5_payload=r5_payload,
        )
        write_json(report_path, report)
        return report

    assert corpus_path is not None
    chunks = load_rag_chunks(corpus_path, context_field=context_field)
    context_rows, metrics = assemble_rows(
        gold_rows=rows,
        emit_rows=emit_rows,
        chunks=chunks,
        max_context_chars=max_context_chars,
        context_field=context_field,
    )

    if metrics["missing_corpus_chunk_join_count"]:
        blockers.append("R6 corpus chunk join failed for one or more positive rows")
    if metrics["empty_chunk_text_count"]:
        blockers.append("R6 found empty chunk_text for one or more positive rows")
    if metrics["missing_expected_source_count"]:
        warnings.append("R5 retrieval miss carried into R6: expected source missing for some positive rows.")
    if metrics["missing_expected_chunk_count"]:
        warnings.append("R5 retrieval miss carried into R6: expected chunk missing for some positive rows.")
    if metrics["context_truncated_count"]:
        warnings.append("R6 context truncation was applied.")
    if metrics["duplicate_chunk_dedup_count"]:
        warnings.append("R6 removed duplicate chunk ids deterministically by first rank.")

    status = "FAIL" if blockers else "PASS_WITH_WARNINGS" if warnings else "PASS"
    write_jsonl(context_emit, context_rows)
    metrics = {**metrics, "context_emit_sha256": sha256_file(context_emit)}

    report = build_report(
        run_id=run_id,
        generated_at=generated_at,
        status=status,
        gold=gold,
        corpus_inventory_report=corpus_inventory_report,
        gold_validator_report=gold_validator_report,
        r5_fresh_emit=r5_fresh_emit,
        r5_report=r5_report,
        context_emit=context_emit,
        context_field=context_field,
        max_context_chars=max_context_chars,
        rows=rows,
        context_rows=context_rows,
        metrics=metrics,
        needs_review_rows=needs_review_rows(rows),
        blockers=blockers,
        warnings=warnings,
        r5_payload=r5_payload,
    )
    write_json(report_path, report)
    return report


def entry_gate_blockers(
    rows: list[dict[str, str]],
    corpus_report: Mapping[str, Any] | None,
    validator_report: Mapping[str, Any] | None,
    r5_report: Mapping[str, Any] | None,
    r5_fresh_emit: Path,
    emit_rows: list[dict[str, Any]],
) -> list[str]:
    blockers: list[str] = []
    if not rows:
        blockers.append("gold CSV is missing or empty")
    if len(rows) != EXPECTED_QUERY_COUNT:
        blockers.append(f"gold query_count mismatch: {len(rows)} != {EXPECTED_QUERY_COUNT}")
    positive_count = sum(1 for row in rows if denominator_included(row))
    needs_review_count = sum(1 for row in rows if is_needs_review(row))
    if positive_count != EXPECTED_POSITIVE_DENOMINATOR:
        blockers.append(f"positive denominator mismatch: {positive_count} != {EXPECTED_POSITIVE_DENOMINATOR}")
    if needs_review_count != EXPECTED_NEEDS_REVIEW_EXCLUDED:
        blockers.append(f"needs_review count mismatch: {needs_review_count} != {EXPECTED_NEEDS_REVIEW_EXCLUDED}")

    if corpus_report is None:
        blockers.append("R2 corpus inventory report is missing or invalid JSON")
    elif corpus_report.get("status") != "PASS":
        blockers.append(f"R2 corpus inventory status is {corpus_report.get('status')}, not PASS")

    if validator_report is None:
        blockers.append("R3 gold validator report is missing or invalid JSON")
    elif validator_report.get("status") != "PASSED":
        blockers.append(f"R3 gold validator status is {validator_report.get('status')}, not PASSED")

    if r5_report is None:
        blockers.append("R5 diagnostic report is missing or invalid JSON")
    else:
        expected = {
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "reused_emit": False,
            "existing_emit_reused": False,
            "positive_denominator_count": EXPECTED_POSITIVE_DENOMINATOR,
            "needs_review_excluded_count": EXPECTED_NEEDS_REVIEW_EXCLUDED,
            "retrieval_metrics_computed": True,
            "llm_answer_eval_run": False,
            "citation_eval_run": False,
            "promotion_run": False,
        }
        if r5_report.get("status") not in {"PASS", "PASS_WITH_WARNINGS"}:
            blockers.append(f"R5 status is {r5_report.get('status')}, not PASS/PASS_WITH_WARNINGS")
        for field, value in expected.items():
            if r5_report.get(field) != value:
                blockers.append(f"R5 contract mismatch: {field}={r5_report.get(field)!r}, expected {value!r}")
        for field, value in EXPECTED_R5_WARNING_CARRYOVER.items():
            if r5_report.get(field) != value:
                blockers.append(f"R5 warning carry-over mismatch: {field}={r5_report.get(field)!r}, expected {value!r}")
        report_emit_path = clean(r5_report.get("fresh_emit_path"))
        if report_emit_path and not same_path_or_string(report_emit_path, r5_fresh_emit):
            blockers.append(
                f"R5 fresh_emit_path mismatch: report has {report_emit_path}, script uses {repo_relative(r5_fresh_emit)}"
            )
        report_emit_sha256 = clean(r5_report.get("fresh_emit_sha256"))
        if not report_emit_sha256:
            blockers.append("R5 contract mismatch: fresh_emit_sha256 is missing")
        elif r5_fresh_emit.exists():
            actual_emit_sha256 = sha256_file(r5_fresh_emit)
            if report_emit_sha256 != actual_emit_sha256:
                blockers.append(
                    "R5 fresh_emit_sha256 mismatch: "
                    f"report has {report_emit_sha256}, actual is {actual_emit_sha256}"
                )

    if not r5_fresh_emit.exists():
        blockers.append(f"R5 fresh emit missing: {repo_relative(r5_fresh_emit)}")
    elif not emit_rows:
        blockers.append("R5 fresh emit is empty or invalid JSONL")
    return blockers


def assemble_rows(
    *,
    gold_rows: list[dict[str, str]],
    emit_rows: list[dict[str, Any]],
    chunks: Mapping[str, ChunkContext],
    max_context_chars: int,
    context_field: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    emit_by_query_id = {clean(row.get("query_id")): row for row in emit_rows if clean(row.get("query_id"))}
    context_rows: list[dict[str, Any]] = []
    taxonomy_counter: Counter[str] = Counter()
    duplicate_chunk_dedup_count = 0
    context_truncated_count = 0
    missing_corpus_join_positive_count = 0
    empty_chunk_text_positive_count = 0
    missing_retrieval_result_count = 0
    total_context_char_count = 0
    context_chunk_counts: list[int] = []

    for gold_row in gold_rows:
        query_id = clean(gold_row.get("query_id"))
        emit_row = emit_by_query_id.get(query_id)
        raw_docs = docs_from_emit(emit_row)
        deduped_docs, dedup_count = dedup_docs_by_chunk_id(raw_docs)
        duplicate_chunk_dedup_count += dedup_count

        context_items: list[dict[str, Any]] = []
        missing_corpus_chunk_ids: list[str] = []
        empty_chunk_text_ids: list[str] = []
        char_budget = max_context_chars
        row_truncated = False
        for doc in deduped_docs:
            chunk_id = clean(doc.get("chunk_id"))
            chunk = chunks.get(chunk_id)
            if chunk is None:
                missing_corpus_chunk_ids.append(chunk_id or "<missing_chunk_id>")
                continue
            text = select_context_text(chunk, context_field)
            if not text:
                empty_chunk_text_ids.append(chunk_id)
                continue
            if max_context_chars > 0:
                if char_budget <= 0:
                    row_truncated = True
                    continue
                if len(text) > char_budget:
                    text = text[:char_budget]
                    row_truncated = True
                char_budget -= len(text)
            context_items.append(context_item_from(doc, chunk, text=text, context_field=context_field))

        if row_truncated:
            context_truncated_count += 1

        expected_page_ids = split_ids(gold_row.get("expected_page_ids"))
        expected_section_ids = split_ids(gold_row.get("expected_section_ids"))
        expected_chunk_ids = split_ids(gold_row.get("expected_chunk_ids"))
        retrieved_source_ids = source_ids_from_docs(deduped_docs)
        retrieved_section_ids = {clean(doc.get("section_id")) for doc in deduped_docs if clean(doc.get("section_id"))}
        retrieved_chunk_ids = {clean(doc.get("chunk_id")) for doc in deduped_docs if clean(doc.get("chunk_id"))}

        included = denominator_included(gold_row)
        taxonomy = "excluded_needs_review" if not included else "expected_context_present"
        failure_reasons: list[str] = []
        if included:
            if emit_row is None or emit_row.get("retrieval_error") or not raw_docs:
                taxonomy = "context_empty"
                failure_reasons.append("missing_retrieval_result")
                missing_retrieval_result_count += 1
            elif missing_corpus_chunk_ids:
                taxonomy = "missing_corpus_chunk_join"
                failure_reasons.append("missing_corpus_chunk_join")
                missing_corpus_join_positive_count += 1
            elif empty_chunk_text_ids:
                taxonomy = "empty_chunk_text"
                failure_reasons.append("empty_chunk_text")
                empty_chunk_text_positive_count += 1
            elif expected_page_ids and retrieved_source_ids.isdisjoint(expected_page_ids):
                taxonomy = "missing_expected_source"
                failure_reasons.append("missing_expected_source")
            elif expected_chunk_ids and retrieved_chunk_ids.isdisjoint(expected_chunk_ids):
                taxonomy = "missing_expected_chunk"
                failure_reasons.append("missing_expected_chunk")
            else:
                taxonomy = "expected_context_present"
            taxonomy_counter[taxonomy] += 1

        context_char_count = sum(len(item["text"]) for item in context_items)
        total_context_char_count += context_char_count
        context_chunk_counts.append(len(context_items))
        context_rows.append(
            {
                "schema_version": "rag_text_namu_v4_context_assembly_v1",
                "phase": PHASE,
                "query_id": query_id,
                "query": clean(gold_row.get("query")),
                "bucket": clean(gold_row.get("bucket")),
                "label_status": clean(gold_row.get("label_status")),
                "allowed_abstain": parse_bool(gold_row.get("allowed_abstain")),
                "denominator_included": included,
                "denominator_exclusion_reason": None if included else "label_status=needs_review",
                "taxonomy": taxonomy,
                "failure_reasons": failure_reasons,
                "expected_page_ids": expected_page_ids,
                "expected_section_ids": expected_section_ids,
                "expected_chunk_ids": expected_chunk_ids,
                "expected_source_present": not retrieved_source_ids.isdisjoint(expected_page_ids),
                "expected_section_present": not retrieved_section_ids.isdisjoint(expected_section_ids),
                "expected_chunk_present": not retrieved_chunk_ids.isdisjoint(expected_chunk_ids),
                "retrieval_result_count": len(raw_docs),
                "deduped_retrieval_result_count": len(deduped_docs),
                "duplicate_chunk_dedup_count": dedup_count,
                "missing_corpus_chunk_ids": missing_corpus_chunk_ids,
                "empty_chunk_text_ids": empty_chunk_text_ids,
                "context_field": context_field,
                "contexts": context_items,
                "context_count": len(context_items),
                "context_char_count": context_char_count,
                "truncated": row_truncated,
            }
        )

    positive_denominator_count = sum(1 for row in gold_rows if denominator_included(row))
    needs_review_query_ids = [clean(row.get("query_id")) for row in gold_rows if is_needs_review(row)]
    metrics = {
        "query_count": len(gold_rows),
        "positive_denominator_count": positive_denominator_count,
        "needs_review_excluded_count": len(needs_review_query_ids),
        "needs_review_query_ids": needs_review_query_ids,
        "context_rows_written": len(context_rows),
        "expected_context_present_count": taxonomy_counter["expected_context_present"],
        "context_empty_count": taxonomy_counter["context_empty"],
        "missing_retrieval_result_count": missing_retrieval_result_count,
        "missing_expected_source_count": taxonomy_counter["missing_expected_source"],
        "missing_expected_chunk_count": taxonomy_counter["missing_expected_chunk"],
        "missing_corpus_chunk_join_count": missing_corpus_join_positive_count,
        "empty_chunk_text_count": empty_chunk_text_positive_count,
        "context_truncated_count": context_truncated_count,
        "duplicate_chunk_dedup_count": duplicate_chunk_dedup_count,
        "total_context_char_count": total_context_char_count,
        "context_chunk_count_p50": percentile(context_chunk_counts, 50),
        "context_chunk_count_p95": percentile(context_chunk_counts, 95),
        "taxonomy_counts": dict(taxonomy_counter),
    }
    return context_rows, metrics


def build_report(
    *,
    run_id: str,
    generated_at: str,
    status: str,
    gold: Path,
    corpus_inventory_report: Path,
    gold_validator_report: Path,
    r5_fresh_emit: Path,
    r5_report: Path,
    context_emit: Path,
    context_field: str,
    max_context_chars: int,
    rows: list[dict[str, str]],
    context_rows: list[dict[str, Any]],
    metrics: Mapping[str, Any],
    needs_review_rows: list[dict[str, Any]],
    blockers: list[str],
    warnings: list[str],
    r5_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    top_k_used = int(r5_payload.get("top_k", 0)) if r5_payload else 0
    report = {
        "run_id": run_id,
        "generated_at": generated_at,
        "schema_version": "rag_text_namu_v4_context_assembly_report_v1",
        "status": status,
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "phase": PHASE,
        "parallel_with_track_c_c4": True,
        "c4_files_touched": False,
        "db_mutation_run": False,
        "indexing_run": False,
        "worker_claim_run": False,
        "promotion_run": False,
        "llm_answer_eval_run": False,
        "citation_eval_run": False,
        "gold_path": repo_relative(gold),
        "gold_sha256": sha256_if_exists(gold),
        "corpus_inventory_report_path": repo_relative(corpus_inventory_report),
        "corpus_inventory_report_sha256": sha256_if_exists(corpus_inventory_report),
        "gold_validator_report_path": repo_relative(gold_validator_report),
        "gold_validator_report_sha256": sha256_if_exists(gold_validator_report),
        "r5_fresh_emit_path": repo_relative(r5_fresh_emit),
        "r5_fresh_emit_sha256": sha256_if_exists(r5_fresh_emit),
        "r5_report_path": repo_relative(r5_report),
        "r5_report_sha256": sha256_if_exists(r5_report),
        "context_emit_path": repo_relative(context_emit),
        "context_emit_sha256": metrics.get("context_emit_sha256"),
        "context_field": context_field,
        "disallowed_context_fields": DISALLOWED_CONTEXT_FIELDS,
        "query_count": metrics.get("query_count", len(rows)),
        "positive_denominator_count": metrics.get("positive_denominator_count", 0),
        "needs_review_excluded_count": metrics.get("needs_review_excluded_count", 0),
        "needs_review_query_ids": metrics.get("needs_review_query_ids", []),
        "needs_review_rows": needs_review_rows,
        "top_k_used": top_k_used,
        "max_context_chars": max_context_chars,
        "context_rows_written": metrics.get("context_rows_written", len(context_rows)),
        "expected_context_present_count": metrics.get("expected_context_present_count", 0),
        "context_empty_count": metrics.get("context_empty_count", 0),
        "missing_retrieval_result_count": metrics.get("missing_retrieval_result_count", 0),
        "missing_expected_source_count": metrics.get("missing_expected_source_count", 0),
        "missing_expected_chunk_count": metrics.get("missing_expected_chunk_count", 0),
        "missing_corpus_chunk_join_count": metrics.get("missing_corpus_chunk_join_count", 0),
        "empty_chunk_text_count": metrics.get("empty_chunk_text_count", 0),
        "context_truncated_count": metrics.get("context_truncated_count", 0),
        "duplicate_chunk_dedup_count": metrics.get("duplicate_chunk_dedup_count", 0),
        "wrong_source_count_carryover_from_R5": r5_payload.get("wrong_source_count", 0) if r5_payload else 0,
        "missing_expected_chunk_count_carryover_from_R5": (
            r5_payload.get("missing_expected_chunk_count", 0) if r5_payload else 0
        ),
        "empty_result_count_carryover_from_R5": r5_payload.get("empty_result_count", 0) if r5_payload else 0,
        "retrieval_error_count_carryover_from_R5": r5_payload.get("retrieval_error_count", 0) if r5_payload else 0,
        "r5_warning_carryover": {
            "wrong_source_count": r5_payload.get("wrong_source_count", 0) if r5_payload else 0,
            "missing_expected_chunk_count": r5_payload.get("missing_expected_chunk_count", 0) if r5_payload else 0,
            "empty_result_count": r5_payload.get("empty_result_count", 0) if r5_payload else 0,
            "retrieval_error_count": r5_payload.get("retrieval_error_count", 0) if r5_payload else 0,
        },
        "retrieval_emit_reuse": {
            "r5_fresh_emit_only": True,
            "existing_emit_reused": False,
            "reused_emit": False,
        },
        "context_ordering_policy": {
            "rank_order_preserved": True,
            "duplicate_chunk_policy": "first rank wins",
            "source_grouping_applied": False,
            "reranking_applied": False,
        },
        "taxonomy_counts": metrics.get("taxonomy_counts", {}),
        "r7_ready": status in {"PASS", "PASS_WITH_WARNINGS"} and not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "c4_isolation": {
            "c4_files_touched": False,
            "db_mutation_run": False,
            "indexing_run": False,
            "namespace_mutation_run": False,
            "worker_claim_run": False,
            "forbidden_path_patterns": C4_FORBIDDEN_PATHS,
        },
        "done_criteria": {
            "r5_contract_valid": not any(blocker.startswith("R5 ") for blocker in blockers),
            "context_emit_written": status in {"PASS", "PASS_WITH_WARNINGS"},
            "chunk_text_only": context_field == CONTEXT_FIELD,
            "disallowed_context_fields_not_used": context_field not in DISALLOWED_CONTEXT_FIELDS,
            "positive_denominator_is_47": metrics.get("positive_denominator_count", 0)
            == EXPECTED_POSITIVE_DENOMINATOR,
            "needs_review_excluded_is_3": metrics.get("needs_review_excluded_count", 0)
            == EXPECTED_NEEDS_REVIEW_EXCLUDED,
            "c4_files_touched_false": True,
            "indexing_not_run": True,
            "llm_answer_eval_not_run": True,
            "citation_eval_not_run": True,
            "promotion_not_run": True,
        },
        "next_phase_recommendation": (
            "Proceed to R7 answer eval planning only; R7 answer eval was not run."
            if status in {"PASS", "PASS_WITH_WARNINGS"}
            else "Keep R7 blocked until R6 blockers are resolved."
        ),
    }
    return report


def empty_metrics(rows: list[dict[str, str]]) -> dict[str, Any]:
    needs_review_query_ids = [clean(row.get("query_id")) for row in rows if is_needs_review(row)]
    return {
        "query_count": len(rows),
        "positive_denominator_count": sum(1 for row in rows if denominator_included(row)),
        "needs_review_excluded_count": len(needs_review_query_ids),
        "needs_review_query_ids": needs_review_query_ids,
        "context_rows_written": 0,
        "expected_context_present_count": 0,
        "context_empty_count": 0,
        "missing_retrieval_result_count": 0,
        "missing_expected_source_count": 0,
        "missing_expected_chunk_count": 0,
        "missing_corpus_chunk_join_count": 0,
        "empty_chunk_text_count": 0,
        "context_truncated_count": 0,
        "duplicate_chunk_dedup_count": 0,
        "taxonomy_counts": {},
    }


def load_rag_chunks(path: Path, *, context_field: str) -> dict[str, ChunkContext]:
    chunks: dict[str, ChunkContext] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            chunk_id = clean(row.get("chunk_id"))
            if not chunk_id:
                continue
            text = clean(row.get(context_field))
            chunks[chunk_id] = ChunkContext(
                chunk_id=chunk_id,
                doc_id=clean(row.get("doc_id") or row.get("page_id")),
                section_id=clean(row.get("section_id")),
                section_path=normalize_section_path(row.get("section_path")),
                title=clean(row.get("display_title") or row.get("retrieval_title") or row.get("title")),
                chunk_text=text,
            )
    return chunks


def select_context_text(chunk: ChunkContext | Mapping[str, Any], context_field: str = CONTEXT_FIELD) -> str:
    if context_field in DISALLOWED_CONTEXT_FIELDS or context_field != CONTEXT_FIELD:
        raise ValueError(f"disallowed context field: {context_field}")
    if isinstance(chunk, ChunkContext):
        return chunk.chunk_text
    return clean(chunk.get(CONTEXT_FIELD))


def context_item_from(
    doc: Mapping[str, Any],
    chunk: ChunkContext,
    *,
    text: str,
    context_field: str,
) -> dict[str, Any]:
    return {
        "rank": int_or_none(doc.get("rank")),
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "page_id": chunk.doc_id,
        "section_id": chunk.section_id,
        "section_path": chunk.section_path,
        "title": chunk.title,
        "score": float_or_none(doc.get("score")),
        "context_field": context_field,
        "text": text,
    }


def dedup_docs_by_chunk_id(docs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    ordered = sorted(enumerate(docs), key=lambda item: (rank_sort_key(item[1].get("rank")), item[0]))
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    duplicate_count = 0
    for _, doc in ordered:
        chunk_id = clean(doc.get("chunk_id"))
        if not chunk_id:
            deduped.append(doc)
            continue
        if chunk_id in seen:
            duplicate_count += 1
            continue
        seen.add(chunk_id)
        deduped.append(doc)
    return deduped, duplicate_count


def docs_from_emit(emit_row: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if emit_row is None:
        return []
    docs = emit_row.get("docs")
    if not isinstance(docs, list):
        return []
    return [doc for doc in docs if isinstance(doc, dict)]


def source_ids_from_docs(docs: Iterable[Mapping[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for doc in docs:
        for field in ("page_id", "doc_id"):
            value = clean(doc.get(field))
            if value:
                ids.add(value)
    return ids


def resolve_corpus_rag_chunks_path(corpus_report: Mapping[str, Any] | None) -> Path | None:
    if not corpus_report:
        return None
    files = corpus_report.get("files")
    if not isinstance(files, dict):
        return None
    rag_chunks = files.get("rag_chunks.jsonl")
    if not isinstance(rag_chunks, dict):
        return None
    path_value = clean(rag_chunks.get("path"))
    if not path_value:
        return None
    return resolve_repo_path(path_value)


def needs_review_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if is_needs_review(row):
            result.append(
                {
                    "query_id": clean(row.get("query_id")),
                    "query": clean(row.get("query")),
                    "bucket": clean(row.get("bucket")),
                    "label_status": clean(row.get("label_status")),
                    "allowed_abstain": parse_bool(row.get("allowed_abstain")),
                    "excluded_from_positive_denominator": True,
                }
            )
    return result


def read_csv_if_exists(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def read_jsonl_if_exists(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def print_json(payload: Mapping[str, Any]) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def denominator_included(row: Mapping[str, str]) -> bool:
    return clean(row.get("label_status")).lower() in POSITIVE_LABEL_STATUSES and not parse_bool(row.get("allowed_abstain"))


def is_needs_review(row: Mapping[str, str]) -> bool:
    return clean(row.get("label_status")).lower() in NEEDS_REVIEW_LABEL_STATUSES


def split_ids(value: object) -> list[str]:
    text = clean(value)
    if not text:
        return []
    normalized = text.replace("|", ";").replace(",", ";")
    return [part.strip() for part in normalized.split(";") if part.strip()]


def normalize_section_path(value: object) -> list[str]:
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    text = clean(value)
    if not text:
        return []
    return [part.strip() for part in text.replace(">", "/").split("/") if part.strip()]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def parse_bool(value: object) -> bool:
    return clean(value).lower() == "true"


def int_or_none(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def float_or_none(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def rank_sort_key(value: object) -> int:
    rank = int_or_none(value)
    return rank if rank is not None else 1_000_000


def percentile(values: list[int], percent: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((percent / 100) * (len(ordered) - 1)))
    return float(ordered[index])


def resolve_repo_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else REPO_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def same_path_or_string(reported: str, actual: Path) -> bool:
    normalized_reported = reported.replace("\\", "/")
    normalized_actual = repo_relative(actual).replace("\\", "/")
    if normalized_reported == normalized_actual:
        return True
    try:
        return Path(reported).resolve() == actual.resolve()
    except OSError:
        return False


def sha256_if_exists(path: Path) -> str | None:
    return sha256_file(path) if path.exists() else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
