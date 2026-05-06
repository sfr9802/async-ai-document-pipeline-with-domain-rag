"""Create A/B/C pre-tuning baseline snapshots with E2E LLM I/O artifacts.

Defaults follow the worker-owned eval layout:

* ``ai-worker/eval/artifacts/eval_runs/{run_id}/``
* ``ai-worker/eval/reports/eval/``

The command is safe by default: it reads existing retrieval/context reports,
does not mutate indexes or DB state, and uses dry-run output unless
``E2E_BASELINE_LIVE_LLM=1`` is set with an Ollama endpoint.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


AI_WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AI_WORKER_ROOT.parent
if str(AI_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_WORKER_ROOT))

from eval.harness.e2e_baseline_reporting import (  # noqa: E402
    DRY_RUN_MODEL,
    LIVE_ENV_FLAG,
    PROMPT_VERSION,
    aggregate_summary,
    build_io_record,
    build_judgement_record,
    build_retrieval_record,
    capture_mode_note,
    clean,
    denominator_policy_summary,
    dry_run_answer,
    judge_dry_run_case,
    make_messages,
    read_json,
    redaction_marker,
    render_overview_report,
    render_track_report,
    representative_examples,
    sha256_if_exists,
    utc_run_id,
    utc_timestamp,
    validate_jsonl_records,
    write_json,
    write_jsonl,
)


DEFAULT_ARTIFACT_ROOT = AI_WORKER_ROOT / "eval" / "artifacts" / "eval_runs"
DEFAULT_REPORT_DIR = AI_WORKER_ROOT / "eval" / "reports" / "eval"

DEFAULT_A_GOLD = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_xlsx_v3_positive_reviewed.csv"
DEFAULT_A_RETRIEVAL = (
    AI_WORKER_ROOT
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "rag_retrieval_eval_xlsx_v3_positive_reviewed_vector_diagnostic_report.json"
)
DEFAULT_A_PROGRESS = REPO_ROOT / "docs" / "rag-ingestion" / "xlsx-retrieval" / "phase-progress.md"

DEFAULT_B_GOLD = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_text_namu_v4_v0.csv"
DEFAULT_B_RETRIEVAL = (
    AI_WORKER_ROOT
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "rag_text_namu_v4_retrieval_diagnostic_report.json"
)
DEFAULT_B_CONTEXT = (
    AI_WORKER_ROOT
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "rag_text_namu_v4_context_assembly.jsonl"
)
DEFAULT_B_CONTEXT_REPORT = (
    AI_WORKER_ROOT
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "rag_text_namu_v4_context_assembly_report.json"
)
DEFAULT_B_ANSWER_REPORT = (
    AI_WORKER_ROOT
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "rag_text_namu_v4_answer_eval_report.json"
)
DEFAULT_B_ANSWER_EVAL = (
    AI_WORKER_ROOT
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "rag_text_namu_v4_answer_eval.jsonl"
)
DEFAULT_B_PROGRESS = REPO_ROOT / "docs" / "track_b_text_retrieval_e2e" / "rag_text_retrieval_e2e_progress.md"

DEFAULT_C_GOLD = AI_WORKER_ROOT / "eval" / "eval_queries" / "gold_queries_pdf_v0.csv"
DEFAULT_C_RETRIEVAL = (
    AI_WORKER_ROOT
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "rag_retrieval_eval_pdf_vector_diagnostic_report.json"
)
DEFAULT_C_CONSISTENCY = (
    AI_WORKER_ROOT
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "pdf_candidate_embedding_consistency_report.json"
)
DEFAULT_C_POLICY = (
    AI_WORKER_ROOT
    / "eval"
    / "reports"
    / "rag-ingestion"
    / "rag_pdf_gold_policy_review.json"
)
DEFAULT_C_PROGRESS = REPO_ROOT / "docs" / "track-c-pdf-embedding-preparation" / "progress.md"
DEFAULT_PREVIOUS_RUN_ID = "base_before_tuning_20260505"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = args.run_id or f"base_before_tuning_{utc_run_id()}"
    generated_at = utc_timestamp()
    artifact_dir = Path(args.artifact_root) / run_id
    report_dir = Path(args.report_dir)
    live_call_enabled = os.getenv(LIVE_ENV_FLAG, "").strip() == "1"

    cases, source_metrics, source_paths = collect_cases(args, run_id=run_id)
    previous_run_dir = Path(args.artifact_root) / args.previous_run_id
    freshness_comparison = build_freshness_comparison(previous_run_dir, source_paths)
    io_records = materialize_io_records(
        cases,
        run_id=run_id,
        live_call_enabled=live_call_enabled,
        temperature=args.temperature,
    )
    validation_errors = validate_jsonl_records(io_records)
    if validation_errors:
        raise ValueError("E2E LLM I/O schema validation failed: " + "; ".join(validation_errors[:5]))

    retrieval_rows = [build_retrieval_record(record) for record in io_records]
    judgement_rows = [build_judgement_record(record) for record in io_records]
    summary = aggregate_summary(
        run_id=run_id,
        generated_at=generated_at,
        io_records=io_records,
        source_metrics=source_metrics,
        live_call_executed=live_call_enabled,
    )
    summary["freshness_comparison"] = freshness_comparison
    summary["denominator_policy_summary"] = build_denominator_policy_snapshot(
        summary=summary,
        source_metrics=source_metrics,
        live_call_enabled=live_call_enabled,
    )

    artifact_paths = {
        "manifest": artifact_dir / "manifest.json",
        "retrieval_results": artifact_dir / "retrieval_results.jsonl",
        "e2e_llm_io": artifact_dir / "e2e_llm_io.jsonl",
        "e2e_judgements": artifact_dir / "e2e_judgements.jsonl",
        "summary": artifact_dir / "summary.json",
    }
    write_jsonl(artifact_paths["retrieval_results"], retrieval_rows)
    write_jsonl(artifact_paths["e2e_llm_io"], io_records)
    write_jsonl(artifact_paths["e2e_judgements"], judgement_rows)
    write_json(artifact_paths["summary"], summary)

    manifest = build_manifest(
        run_id=run_id,
        generated_at=generated_at,
        live_call_enabled=live_call_enabled,
        source_paths=source_paths,
        artifact_paths=artifact_paths,
        report_dir=report_dir,
        args=args,
        freshness_comparison=freshness_comparison,
        denominator_policy=summary["denominator_policy_summary"],
    )
    write_json(artifact_paths["manifest"], manifest)

    report_paths = write_reports(
        report_dir=report_dir,
        summary=summary,
        io_records=io_records,
        source_paths=source_paths,
        artifact_paths=artifact_paths,
        live_call_enabled=live_call_enabled,
    )

    print(
        json.dumps(
            {
                "run_id": run_id,
                "artifact_dir": repo_relative(artifact_dir),
                "report_dir": repo_relative(report_dir),
                "live_call_executed": live_call_enabled,
                "capture_mode_note": capture_mode_note(live_call_enabled),
                "reports": {key: repo_relative(path) for key, path in report_paths.items()},
                "artifacts": {key: repo_relative(path) for key, path in artifact_paths.items()},
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--artifact-root", default=str(DEFAULT_ARTIFACT_ROOT))
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--a-gold", default=str(DEFAULT_A_GOLD))
    parser.add_argument("--a-retrieval-report", default=str(DEFAULT_A_RETRIEVAL))
    parser.add_argument("--b-gold", default=str(DEFAULT_B_GOLD))
    parser.add_argument("--b-retrieval-report", default=str(DEFAULT_B_RETRIEVAL))
    parser.add_argument("--b-context-emit", default=str(DEFAULT_B_CONTEXT))
    parser.add_argument("--b-context-report", default=str(DEFAULT_B_CONTEXT_REPORT))
    parser.add_argument("--b-answer-report", default=str(DEFAULT_B_ANSWER_REPORT))
    parser.add_argument("--b-answer-eval", default=str(DEFAULT_B_ANSWER_EVAL))
    parser.add_argument("--c-gold", default=str(DEFAULT_C_GOLD))
    parser.add_argument("--c-retrieval-report", default=str(DEFAULT_C_RETRIEVAL))
    parser.add_argument("--c-consistency-report", default=str(DEFAULT_C_CONSISTENCY))
    parser.add_argument("--c-policy-report", default=str(DEFAULT_C_POLICY))
    parser.add_argument("--previous-run-id", default=DEFAULT_PREVIOUS_RUN_ID)
    return parser.parse_args(argv)


def collect_cases(args: argparse.Namespace, *, run_id: str) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]]:
    del run_id
    a_cases, a_metrics, a_sources = load_track_a(
        gold=Path(args.a_gold),
        retrieval_report=Path(args.a_retrieval_report),
    )
    b_cases, b_metrics, b_sources = load_track_b(
        gold=Path(args.b_gold),
        retrieval_report=Path(args.b_retrieval_report),
        context_emit=Path(args.b_context_emit),
        context_report=Path(args.b_context_report),
        answer_report=Path(args.b_answer_report),
        answer_eval=Path(args.b_answer_eval),
    )
    c_cases, c_metrics, c_sources = load_track_c(
        gold=Path(args.c_gold),
        retrieval_report=Path(args.c_retrieval_report),
        consistency_report=Path(args.c_consistency_report),
        policy_report=Path(args.c_policy_report),
    )
    source_paths = {
        **{f"A:{key}": value for key, value in a_sources.items()},
        **{f"B:{key}": value for key, value in b_sources.items()},
        **{f"C:{key}": value for key, value in c_sources.items()},
    }
    return (
        [*a_cases, *b_cases, *c_cases],
        {"A": a_metrics, "B": b_metrics, "C": c_metrics},
        source_paths,
    )


def load_track_a(*, gold: Path, retrieval_report: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    rows = csv_by_id(gold)
    report = read_json(retrieval_report)
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    namespace = clean(metrics.get("required_index_version")) or "rag-ingestion-v2-xlsx-candidate-v1"
    cases: list[dict[str, Any]] = []
    for item in report.get("per_query", []) or []:
        if not isinstance(item, dict):
            continue
        case_id = clean(item.get("query_id"))
        gold_row = rows.get(case_id, {})
        top_hit = item.get("top_hit") if isinstance(item.get("top_hit"), dict) else {}
        expected = compact_list(
            [
                gold_row.get("expected_document_version_id"),
                gold_row.get("expected_sheet_name"),
                gold_row.get("expected_cell_range"),
                gold_row.get("expected_table_id"),
            ]
        )
        retrieved_context = [
            {
                "rank": 1,
                "search_unit_id": top_hit.get("search_unit_id"),
                "source_file_name": top_hit.get("source_file_name"),
                "chunk_id": top_hit.get("search_unit_id"),
                "doc_id": top_hit.get("source_file_name"),
                "citation_text": top_hit.get("citation_text"),
                "text": top_hit.get("citation_text") or "",
            }
        ]
        cases.append(
            {
                "track": "A",
                "case_id": case_id,
                "gold_status": xlsx_gold_status(gold_row),
                "label_status": clean(gold_row.get("label_status")).lower(),
                "query": clean(item.get("query") or gold_row.get("query")),
                "retrieval": {
                    "namespace": namespace,
                    "index_version": clean(top_hit.get("index_version")) or namespace,
                    "top_k": 10,
                    "retrieved_doc_ids": compact_list(
                        [top_hit.get("source_file_name"), top_hit.get("search_unit_id")]
                    ),
                    "retrieved_doc_ids_source": "top_hit only; full top_k context was not emitted by source report",
                    "retrieved_context": retrieved_context,
                    "expected_evidence_ids": expected,
                    "evidence_hit": bool(item.get("hit_at_10")),
                },
                "notes": "Track A reviewed XLSX positive diagnostic baseline.",
            }
        )
    source_metrics = pick_metrics(
        metrics,
        [
            "Hit@1",
            "Hit@3",
            "Hit@5",
            "Hit@10",
            "MRR@10",
            "xlsx_citation_location_accuracy",
            "hidden_content_leakage_count",
            "required_index_version",
        ],
    )
    source_metrics["reviewed_positive_count"] = sum(1 for row in rows.values() if xlsx_gold_status(row) == "gold")
    return cases, source_metrics, {"gold": repo_relative(gold), "retrieval_report": repo_relative(retrieval_report)}


def load_track_b(
    *,
    gold: Path,
    retrieval_report: Path,
    context_emit: Path,
    context_report: Path,
    answer_report: Path,
    answer_eval: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    rows = csv_by_id(gold)
    report = read_json(retrieval_report)
    answer_payload = read_json(answer_report)
    answer_rows = {clean(row.get("query_id")): row for row in read_jsonl(answer_eval)}
    context_rows = read_jsonl(context_emit)
    namespace = clean(_nested(report, "retrieval_backend_identity.name")) or clean(report.get("retrieval_backend"))
    index_identifier = clean(_nested(report, "retrieval_backend_identity.corpus_source")) or "namu-v4-rag_chunks"
    cases: list[dict[str, Any]] = []
    for row in context_rows:
        case_id = clean(row.get("query_id"))
        gold_row = rows.get(case_id, {})
        answer_row = answer_rows.get(case_id, {})
        contexts = row.get("contexts") if isinstance(row.get("contexts"), list) else []
        expected = compact_list(
            [
                *as_list(row.get("expected_page_ids")),
                *as_list(row.get("expected_section_ids")),
                *as_list(row.get("expected_chunk_ids")),
            ]
        )
        evidence_hit = bool(answer_row.get("answerable_from_context") or row.get("expected_chunk_present"))
        cases.append(
            {
                "track": "B",
                "case_id": case_id,
                "gold_status": text_gold_status(gold_row),
                "label_status": clean(row.get("label_status") or gold_row.get("label_status")).lower(),
                "query": clean(row.get("query") or gold_row.get("query")),
                "retrieval": {
                    "namespace": namespace,
                    "index_identifier": index_identifier,
                    "top_k": int(report.get("top_k") or row.get("retrieval_result_count") or 10),
                    "retrieved_doc_ids": compact_list(context.get("doc_id") for context in contexts),
                    "retrieved_context": contexts,
                    "expected_evidence_ids": expected,
                    "evidence_hit": evidence_hit,
                    "answer_eval": {
                        "artifact_included": bool(answer_rows),
                        "primary_stage": answer_row.get("primary_stage"),
                        "stages": answer_row.get("stages") or [],
                        "answerable_from_context": bool(answer_row.get("answerable_from_context")),
                        "answer_eval_pending_live_llm": bool(answer_row.get("answer_eval_pending_live_llm")),
                        "retrieval_context_miss_stage": answer_row.get("primary_stage")
                        in {
                            "expected_context_missing_due_to_wrong_source",
                            "expected_chunk_missing",
                        },
                    },
                },
                "notes": "Track B R6 context assembly plus R7 deterministic answer eval baseline.",
            }
        )
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else report
    source_metrics = pick_metrics(
        metrics,
        [
            "Hit@1",
            "Hit@3",
            "Hit@5",
            "Hit@10",
            "MRR@10",
            "source_recall@10",
            "chunk_recall@10",
            "wrong_source_count",
            "missing_expected_chunk_count",
            "positive_denominator_count",
            "needs_review_excluded_count",
        ],
    )
    if answer_payload:
        source_metrics.update(
            {
                "R7_status": answer_payload.get("status"),
                "R7_answerable_from_context_count": answer_payload.get("answerable_from_context_count"),
                "R7_retrieval_context_miss_count": answer_payload.get("retrieval_context_miss_count"),
                "R7_answer_generation_failure_count": answer_payload.get("answer_generation_failure_count"),
                "R7_live_llm_run": answer_payload.get("live_llm_run"),
                "R7_context_field": answer_payload.get("context_field"),
            }
        )
    return (
        cases,
        source_metrics,
        {
            "gold": repo_relative(gold),
            "retrieval_report": repo_relative(retrieval_report),
            "context_emit": repo_relative(context_emit),
            "context_report": repo_relative(context_report),
            "answer_report": repo_relative(answer_report),
            "answer_eval": repo_relative(answer_eval),
        },
    )


def load_track_c(
    *,
    gold: Path,
    retrieval_report: Path,
    consistency_report: Path,
    policy_report: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    rows = csv_by_id(gold)
    report = read_json(retrieval_report)
    consistency = read_json(consistency_report)
    policy = read_required_json(policy_report, "Track C C7 policy report")
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    namespace = clean(report.get("namespace")) or clean(metrics.get("required_index_version")) or "rag-ingestion-v2-pdf-candidate-v1"
    c7_review_rows = {
        clean(row.get("query_id")): row
        for row in policy.get("c7_review_rows", []) or []
        if isinstance(row, dict)
    }
    c7_controls = {
        clean(row.get("query_id")): row
        for row in policy.get("current_policy_positive_control_rows", []) or []
        if isinstance(row, dict)
    }
    query_results_by_id = {
        clean(row.get("query_id")): row
        for row in report.get("query_results", []) or []
        if isinstance(row, dict)
    }
    cases: list[dict[str, Any]] = []
    for item in report.get("per_query", []) or []:
        if not isinstance(item, dict):
            continue
        if not clean(item.get("bucket")).startswith("pdf_"):
            continue
        case_id = clean(item.get("query_id"))
        gold_row = rows.get(case_id, {})
        c7_row = c7_review_rows.get(case_id) or c7_controls.get(case_id) or {}
        top_hit = item.get("top_hit") if isinstance(item.get("top_hit"), dict) else {}
        query_result = query_results_by_id.get(case_id, {})
        top_k_results = query_result.get("top_k_results") if isinstance(query_result.get("top_k_results"), list) else []
        expected = compact_list(
            [
                gold_row.get("expected_document_version_id"),
                gold_row.get("expected_page_no"),
                gold_row.get("expected_bbox"),
            ]
        )
        retrieved_context = pdf_context_rows(top_k_results) or [
            {
                "rank": 1,
                "search_unit_id": top_hit.get("search_unit_id"),
                "source_file_name": top_hit.get("source_file_name"),
                "chunk_id": top_hit.get("search_unit_id"),
                "doc_id": top_hit.get("source_file_name"),
                "citation_text": top_hit.get("citation_text"),
                "text": top_hit.get("citation_text") or "",
            }
        ]
        cases.append(
            {
                "track": "C",
                "case_id": case_id,
                "gold_status": pdf_gold_status_from_c7(case_id, c7_row, control_ids=set(c7_controls)),
                "label_status": clean(gold_row.get("label_status")).lower(),
                "query": clean(item.get("query") or gold_row.get("query")),
                "retrieval": {
                    "namespace": namespace,
                    "index_version": clean(top_hit.get("index_version")) or namespace,
                    "top_k": 10,
                    "retrieved_doc_ids": compact_list(
                        [top_hit.get("source_file_name"), top_hit.get("search_unit_id")]
                    ),
                    "retrieved_doc_ids_source": "C5 PDF-only diagnostic top_k_results when available; top_hit fallback otherwise",
                    "retrieved_context": retrieved_context,
                    "expected_evidence_ids": expected,
                    "evidence_hit": bool(item.get("hit_at_10")),
                    "c7_policy": {
                        "status": policy.get("status"),
                        "primary_classification": c7_row.get("primary_c7_classification"),
                        "secondary_classifications": c7_row.get("secondary_c7_classifications") or [],
                        "human_decision_required": bool(c7_row.get("human_decision_required")),
                        "human_decision_topic": c7_row.get("human_decision_topic"),
                        "gold_policy_change_candidate": bool(c7_row.get("gold_policy_change_candidate")),
                        "recommended_current_action": c7_row.get("recommended_current_action"),
                    },
                },
                "notes": "Track C PDF row classified conservatively from C7 policy review.",
            }
        )
    source_metrics = pick_metrics(
        metrics,
        [
            "Hit@1",
            "Hit@3",
            "Hit@5",
            "Hit@10",
            "MRR@10",
            "pdf_file_hit@10",
            "pdf_page_hit@10",
            "pdf_bbox_overlap@10",
            "pdf_citation_location_accuracy",
            "required_index_version",
        ],
    )
    source_metrics.update(
        pick_metrics(
            consistency,
            [
                "status",
                "c5_ready",
                "candidate_namespace_chunk_count",
                "indexable_search_unit_count",
                "policy_excluded_search_unit_count",
            ],
        )
    )
    source_metrics.update(
        {
            "C7_status": policy.get("status"),
            "C7_current_policy_positive_control_count": len(c7_controls),
            "C7_human_decision_required_count": policy.get("human_decision_required_count"),
            "C7_gold_policy_change_candidate_count": policy.get("gold_policy_change_candidate_count"),
            "C7_diagnostic_only_exclude_candidate_count": policy.get("diagnostic_only_exclude_candidate_count"),
            "C7_namespace": policy.get("namespace"),
        }
    )
    return (
        cases,
        source_metrics,
        {
            "gold": repo_relative(gold),
            "retrieval_report": repo_relative(retrieval_report),
            "consistency_report": repo_relative(consistency_report),
            "policy_report": repo_relative(policy_report),
        },
    )


def materialize_io_records(
    cases: Sequence[Mapping[str, Any]],
    *,
    run_id: str,
    live_call_enabled: bool,
    temperature: float,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for case in cases:
        retrieval = dict(case["retrieval"])
        contexts = retrieval.get("retrieved_context") if isinstance(retrieval.get("retrieved_context"), list) else []
        messages = make_messages(
            track=clean(case["track"]),
            query=clean(case["query"]),
            contexts=contexts,
            expected_evidence_ids=as_list(retrieval.get("expected_evidence_ids")),
        )
        content, finish_reason, model, latency_ms, live_note = call_or_dry_run(
            messages,
            live_call_enabled=live_call_enabled,
            temperature=temperature,
        )
        answerability, verdict, grounded, failure_type, notes = judge_dry_run_case(
            gold_status=clean(case["gold_status"]),
            evidence_hit=retrieval.get("evidence_hit"),
            has_context_text=has_context_text(contexts),
            label_status=clean(case.get("label_status")).lower(),
        )
        if live_note:
            notes = f"{notes} {live_note}"
        records.append(
            build_io_record(
                run_id=run_id,
                track=clean(case["track"]),
                case_id=clean(case["case_id"]),
                gold_status=clean(case["gold_status"]),
                query=clean(case["query"]),
                retrieval=retrieval,
                messages=messages,
                output_content=content,
                finish_reason=finish_reason,
                model=model,
                temperature=temperature,
                latency_ms=latency_ms,
                answerability=answerability,
                verdict=verdict,
                grounded=grounded,
                failure_type=failure_type,
                notes=notes,
                prompt_version=PROMPT_VERSION,
            )
        )
    return records


def call_or_dry_run(
    messages: Sequence[Mapping[str, str]],
    *,
    live_call_enabled: bool,
    temperature: float,
) -> tuple[str, str, str, float, str]:
    if live_call_enabled:
        try:
            return call_ollama(messages, temperature=temperature)
        except Exception as exc:  # pragma: no cover - environment-specific
            content, finish_reason = dry_run_answer(messages)
            note = f"Live LLM call failed and dry-run fallback was used: {type(exc).__name__}."
            return content, finish_reason, DRY_RUN_MODEL, 0.0, note
    content, finish_reason = dry_run_answer(messages)
    return content, finish_reason, DRY_RUN_MODEL, 0.0, ""


def call_ollama(
    messages: Sequence[Mapping[str, str]],
    *,
    temperature: float,
) -> tuple[str, str, str, float, str]:
    import httpx

    base_url = os.getenv("E2E_BASELINE_OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("E2E_BASELINE_OLLAMA_MODEL", "gemma4:e2b")
    payload = {
        "model": model,
        "messages": list(messages),
        "stream": False,
        "options": {"temperature": float(temperature)},
    }
    started_at = time.perf_counter()
    with httpx.Client(timeout=float(os.getenv("E2E_BASELINE_LLM_TIMEOUT_S", "60"))) as client:
        response = client.post(f"{base_url}/api/chat", json=payload)
        response.raise_for_status()
        body = response.json()
    latency_ms = (time.perf_counter() - started_at) * 1000.0
    content = clean((body.get("message") or {}).get("content"))
    finish_reason = clean(body.get("done_reason")) or "stop"
    return content, finish_reason, f"ollama-{model}", latency_ms, "Live Ollama output captured; judgement still requires human review."


def write_reports(
    *,
    report_dir: Path,
    summary: Mapping[str, Any],
    io_records: Sequence[Mapping[str, Any]],
    source_paths: Mapping[str, str],
    artifact_paths: Mapping[str, Path],
    live_call_enabled: bool,
) -> dict[str, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    common_artifacts = {key: repo_relative(path) for key, path in artifact_paths.items()}
    paths = {
        "A": report_dir / "base_before_tuning_A.md",
        "B": report_dir / "base_before_tuning_B.md",
        "C": report_dir / "base_before_tuning_C.md",
        "overview": report_dir / "base_before_tuning_overview.md",
        "denominator_policy": report_dir / "base_before_tuning_denominator_policy.md",
    }
    track_titles = {
        "A": "Base Before Tuning A - XLSX Retrieval",
        "B": "Base Before Tuning B - Text Retrieval E2E",
        "C": "Base Before Tuning C - PDF Embedding",
    }
    limitations = {
        "A": [
            "Source retrieval report emits top_hit only, so full retrieved context is stored as unavailable.",
            "Evidence remains diagnostic baseline evidence, not promotion evidence.",
        ],
        "B": [
            "R7 live answer evaluation was not executed in dry-run mode.",
            "R7 deterministic answer eval is included, but answer generation/judgement remains pending live LLM.",
            "The three Track B needs_review rows remain diagnostic_only and out of denominators.",
        ],
        "C": [
            "C7 status is NEEDS_POLICY_DECISION; policy-change candidates stay out of official denominators.",
            "Only C7 current-policy positive controls enter the Track C gold denominator.",
        ],
    }
    next_candidates = {
        "A": [
            "Investigate location-rank quality watch item(s) without mutating XLSX candidate namespace.",
            "Keep hidden-negative leakage checks separate from positive Hit/MRR denominators.",
        ],
        "B": [
            "Run a later explicit live or approved local LLM pass for R7 answer_eval_pending_live_llm rows.",
            "Add citation-support checks after answer output is captured.",
        ],
        "C": [
            "Collect user decisions for C7 gold policy, expected evidence semantics, and answerability labels.",
            "Add follow-up C6 reclassification entries if user policy decisions change C7 classifications.",
        ],
    }
    for track in ("A", "B", "C"):
        md = render_track_report(
            track=track,
            title=track_titles[track],
            summary=summary,
            artifact_paths=common_artifacts,
            source_paths={key: value for key, value in source_paths.items() if key.startswith(f"{track}:")},
            representative_examples=representative_examples(io_records, track=track),
            known_limitations=limitations[track],
            next_tuning_candidates=next_candidates[track],
            live_call_executed=live_call_enabled,
        )
        paths[track].write_text(md, encoding="utf-8")
    overview = render_overview_report(
        summary=summary,
        report_paths={key: repo_relative(path) for key, path in paths.items() if key != "overview"},
        live_call_executed=live_call_enabled,
    )
    overview += "\n## Freshness comparison\n\n" + _freshness_markdown(summary.get("freshness_comparison", {})) + "\n"
    paths["overview"].write_text(overview, encoding="utf-8")
    denominator = render_denominator_policy_report(summary)
    paths["denominator_policy"].write_text(denominator, encoding="utf-8")
    return paths


def build_freshness_comparison(previous_run_dir: Path, source_paths: Mapping[str, str]) -> dict[str, Any]:
    previous_manifest_path = previous_run_dir / "manifest.json"
    previous_manifest = read_json(previous_manifest_path)
    previous_sha = previous_manifest.get("source_sha256") if isinstance(previous_manifest.get("source_sha256"), dict) else {}
    previous_paths = previous_manifest.get("source_paths") if isinstance(previous_manifest.get("source_paths"), dict) else {}
    sources: dict[str, dict[str, Any]] = {}
    counts = Counter()
    for key, current_path in sorted(source_paths.items()):
        current_abs = resolve_repo_path(current_path)
        current_sha = sha256_if_exists(current_abs)
        old_sha = previous_sha.get(key)
        old_path = previous_paths.get(key)
        if current_sha is None:
            status = "missing_current_source"
        elif old_sha is None:
            status = "new_source"
        elif old_path != current_path:
            status = "path_changed"
        elif old_sha != current_sha:
            status = "sha_changed"
        else:
            status = "unchanged"
        counts[status] += 1
        sources[key] = {
            "path": current_path,
            "previous_path": old_path,
            "current_sha256": current_sha,
            "previous_sha256": old_sha,
            "status": status,
        }
    return {
        "previous_run_id": previous_manifest.get("run_id") or previous_run_dir.name,
        "previous_manifest_path": repo_relative(previous_manifest_path),
        "previous_generated_at": previous_manifest.get("generated_at"),
        "compared_source_count": len(source_paths),
        "status_counts": dict(sorted(counts.items())),
        "changed_or_new_source_count": sum(
            count for status, count in counts.items() if status not in {"unchanged"}
        ),
        "sources": sources,
    }


def build_denominator_policy_snapshot(
    *,
    summary: Mapping[str, Any],
    source_metrics: Mapping[str, Mapping[str, Any]],
    live_call_enabled: bool,
) -> dict[str, Any]:
    track_summaries = summary.get("track_summaries") if isinstance(summary.get("track_summaries"), dict) else {}
    return {
        "official_metric_gold_status": "gold",
        "excluded_statuses": ["candidate", "diagnostic_only"],
        "ambiguous_non_gold_default": "diagnostic_only",
        "live_llm_call_executed": live_call_enabled,
        "raw_prompt_context_output_policy": "JSONL only; Markdown reports contain summaries and paths only.",
        "tracks": {
            "A": {
                "policy": "reviewed XLSX positives remain gold only when label_status=bound and review_decision=KEEP_AS_POSITIVE",
                "official_denominator_count": _track_denominator(track_summaries, "A"),
                "case_counts_by_gold_status": _track_counts(track_summaries, "A"),
                "source_positive_reviewed_count": source_metrics.get("A", {}).get("reviewed_positive_count"),
            },
            "B": {
                "policy": "R3 bound namu-v4 rows are gold; three needs_review rows are diagnostic_only; R7 answer eval is diagnostic only",
                "official_denominator_count": _track_denominator(track_summaries, "B"),
                "case_counts_by_gold_status": _track_counts(track_summaries, "B"),
                "positive_denominator_count": source_metrics.get("B", {}).get("positive_denominator_count"),
                "needs_review_excluded_count": source_metrics.get("B", {}).get("needs_review_excluded_count"),
                "r7_answerable_from_context_count": source_metrics.get("B", {}).get("R7_answerable_from_context_count"),
                "r7_live_llm_run": source_metrics.get("B", {}).get("R7_live_llm_run"),
            },
            "C": {
                "policy": "C7 conservative PDF policy: current-policy positive controls are gold; policy-change candidates are candidate; remaining review rows are diagnostic_only",
                "official_denominator_count": _track_denominator(track_summaries, "C"),
                "case_counts_by_gold_status": _track_counts(track_summaries, "C"),
                "c7_status": source_metrics.get("C", {}).get("C7_status"),
                "c7_current_policy_positive_control_count": source_metrics.get("C", {}).get("C7_current_policy_positive_control_count"),
                "c7_human_decision_required_count": source_metrics.get("C", {}).get("C7_human_decision_required_count"),
                "c7_gold_policy_change_candidate_count": source_metrics.get("C", {}).get("C7_gold_policy_change_candidate_count"),
                "c7_diagnostic_only_exclude_candidate_count": source_metrics.get("C", {}).get("C7_diagnostic_only_exclude_candidate_count"),
            },
        },
    }


def _track_denominator(track_summaries: Mapping[str, Any], track: str) -> Any:
    payload = track_summaries.get(track) if isinstance(track_summaries.get(track), Mapping) else {}
    return payload.get("official_denominator_count")


def _track_counts(track_summaries: Mapping[str, Any], track: str) -> Mapping[str, Any]:
    payload = track_summaries.get(track) if isinstance(track_summaries.get(track), Mapping) else {}
    return payload.get("case_counts_by_gold_status", {})


def render_denominator_policy_report(summary: Mapping[str, Any]) -> str:
    policy = summary.get("denominator_policy_summary") if isinstance(summary.get("denominator_policy_summary"), Mapping) else {}
    tracks = policy.get("tracks") if isinstance(policy.get("tracks"), Mapping) else {}
    rows = []
    for track, payload in sorted(tracks.items()):
        if not isinstance(payload, Mapping):
            continue
        rows.append(
            [
                track,
                _format_value(payload.get("official_denominator_count")),
                json.dumps(payload.get("case_counts_by_gold_status", {}), ensure_ascii=False),
                clean(payload.get("policy")),
            ]
        )
    lines = [
        "# Baseline Denominator Policy Summary",
        "",
        "## Run metadata",
        "",
        f"- Run id: `{summary['run_id']}`",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Live LLM call executed: `{str(summary.get('live_call_executed')).lower()}`",
        "",
        "## Official policy",
        "",
        "- Only `gold` rows enter official retrieval and E2E denominators.",
        "- `candidate` and `diagnostic_only` rows are preserved in JSONL artifacts but excluded from official denominators.",
        "- Raw prompt, context, and output are stored in JSONL only; Markdown reports contain summaries only.",
        "",
        "## Track policies",
        "",
        _markdown_table(["track", "official denominator", "gold_status counts", "policy"], rows),
        "",
        "## Freshness summary",
        "",
        _freshness_markdown(summary.get("freshness_comparison", {})),
        "",
    ]
    return "\n".join(lines)


def _freshness_markdown(freshness: Any) -> str:
    if not isinstance(freshness, Mapping):
        return "_No freshness comparison was recorded._"
    status_counts = freshness.get("status_counts") if isinstance(freshness.get("status_counts"), Mapping) else {}
    sources = freshness.get("sources") if isinstance(freshness.get("sources"), Mapping) else {}
    lines = [
        f"- Previous run id: `{freshness.get('previous_run_id')}`",
        f"- Previous generated at: `{freshness.get('previous_generated_at')}`",
        f"- Compared source count: `{freshness.get('compared_source_count')}`",
        f"- Status counts: `{json.dumps(status_counts, ensure_ascii=False, sort_keys=True)}`",
        "",
        _markdown_table(
            ["source", "status", "path"],
            [
                [key, clean(value.get("status")), f"`{value.get('path')}`"]
                for key, value in sorted(sources.items())
                if isinstance(value, Mapping) and clean(value.get("status")) != "unchanged"
            ]
            or [["all", "unchanged", "n/a"]],
        ),
    ]
    return "\n".join(lines)


def _markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_escape_cell(cell) for cell in row) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def _escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_manifest(
    *,
    run_id: str,
    generated_at: str,
    live_call_enabled: bool,
    source_paths: Mapping[str, str],
    artifact_paths: Mapping[str, Path],
    report_dir: Path,
    args: argparse.Namespace,
    freshness_comparison: Mapping[str, Any],
    denominator_policy: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "e2e_baseline_manifest_v1",
        "run_id": run_id,
        "generated_at": generated_at,
        "capture_mode_note": capture_mode_note(live_call_enabled),
        "live_call_executed": live_call_enabled,
        "previous_run_id": args.previous_run_id,
        "freshness_comparison": dict(freshness_comparison),
        "llm_config": {
            "env_flag": LIVE_ENV_FLAG,
            "model_default": DRY_RUN_MODEL,
            "prompt_version": PROMPT_VERSION,
            "temperature_default": 0.0,
            "secrets_recorded": False,
            "redaction_marker": redaction_marker(),
        },
        "denominator_policy": denominator_policy_summary(),
        "denominator_policy_summary": dict(denominator_policy),
        "source_paths": dict(source_paths),
        "source_sha256": {
            key: sha256_if_exists(REPO_ROOT / value)
            for key, value in source_paths.items()
            if not Path(value).is_absolute()
        },
        "artifact_paths": {key: repo_relative(path) for key, path in artifact_paths.items()},
        "report_dir": repo_relative(report_dir),
        "track_notes": {
            "A": "Track A XLSX reviewed positives are gold for denominator purposes, while report evidence stays diagnostic.",
            "B": "Track B bound rows are gold; needs_review rows are diagnostic_only; R7 answer eval artifacts are included when present.",
            "C": "Track C PDF rows are classified conservatively from C7: current-policy controls are gold, policy-change candidates are candidate, and the rest are diagnostic_only.",
        },
    }


def csv_by_id(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {clean(row.get("query_id")): dict(row) for row in rows if clean(row.get("query_id"))}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}: line {line_number} must be object")
            rows.append(payload)
    return rows


def read_required_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} missing: {repo_relative(path)}")
    payload = read_json(path)
    if not payload:
        raise ValueError(f"{label} is empty or invalid JSON: {repo_relative(path)}")
    return payload


def pdf_context_rows(top_k_results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in top_k_results[:10]:
        if not isinstance(item, Mapping):
            continue
        location = item.get("location_json") if isinstance(item.get("location_json"), Mapping) else {}
        rows.append(
            {
                "rank": item.get("rank"),
                "search_unit_id": item.get("search_unit_id"),
                "source_file_name": item.get("source_file_name"),
                "chunk_id": item.get("search_unit_id"),
                "doc_id": item.get("source_file_name"),
                "page_no": location.get("page_no"),
                "physical_page_index": location.get("physical_page_index"),
                "chunk_type": item.get("chunk_type"),
                "citation_text": item.get("citation_text"),
                "text": item.get("citation_text") or "",
            }
        )
    return rows


def pdf_gold_status_from_c7(
    query_id: str,
    c7_row: Mapping[str, Any],
    *,
    control_ids: set[str],
) -> str:
    if query_id in control_ids or clean(c7_row.get("primary_c7_classification")) == "keep_as_positive_current_policy":
        return "gold"
    if not c7_row:
        return "diagnostic_only"
    if bool(c7_row.get("gold_policy_change_candidate")):
        return "candidate"
    if clean(c7_row.get("primary_c7_classification")) in {
        "table_gold_policy_review_required",
        "page_only_evidence_policy_review_required",
        "bbox_policy_review_required",
    }:
        return "candidate"
    return "diagnostic_only"


def xlsx_gold_status(row: Mapping[str, Any]) -> str:
    label = clean(row.get("label_status")).lower()
    review = clean(row.get("review_decision")).upper()
    if label == "bound" and review in {"", "KEEP_AS_POSITIVE"} and row.get("expected_document_version_id"):
        return "gold"
    if label in {"candidate", "pending"}:
        return "candidate"
    return "diagnostic_only"


def text_gold_status(row: Mapping[str, Any]) -> str:
    label = clean(row.get("label_status")).lower()
    has_expected = bool(
        clean(row.get("expected_answer_summary"))
        and clean(row.get("expected_page_ids"))
        and clean(row.get("expected_chunk_ids"))
    )
    if label == "bound" and has_expected:
        return "gold"
    if label in {"candidate", "pending"}:
        return "candidate"
    return "diagnostic_only"


def has_context_text(contexts: Sequence[Mapping[str, Any]]) -> bool:
    return any(clean(context.get("text")) for context in contexts)


def pick_metrics(metrics: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return {key: metrics[key] for key in keys if key in metrics}


def compact_list(values: Any) -> list[str]:
    if isinstance(values, str):
        return [values] if values.strip() else []
    out: list[str] = []
    for value in values or []:
        text = clean(value)
        if text and text not in out:
            out.append(text)
    return out


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    if isinstance(value, tuple):
        return [clean(item) for item in value if clean(item)]
    text = clean(value)
    if not text:
        return []
    if ";" in text:
        return [part.strip() for part in text.split(";") if part.strip()]
    return [text]


def _nested(payload: Mapping[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_repo_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
