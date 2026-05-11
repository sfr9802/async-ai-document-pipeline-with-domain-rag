"""Run diagnostic-only XLSX human-review vector retrieval evaluation.

This script intentionally does not run promotion and never marks the report as
promotion evidence. It keeps hidden-negative probes in a separate leakage
diagnostic so positive Hit@K/MRR metrics stay positive-only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


AI_WORKER = Path(__file__).resolve().parents[1]
ROOT = AI_WORKER.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(AI_WORKER) not in sys.path:
    sys.path.insert(0, str(AI_WORKER))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from eval.harness.rag_ingestion_retrieval_eval import (  # noqa: E402
    evaluate_gold_rows,
    load_gold_csv,
    search_vector,
    validate_gold_rows,
)
from rag_xlsx_pre_silver_risk_closure import (  # noqa: E402
    XlsxPreSilverRiskError,
    resolve_current_xlsx_human_review_artifacts,
    validate_diagnostic_agentic_xlsx_config,
    validate_official_xlsx_eval_route,
)


XLSX_CANDIDATE_INDEX_VERSION = "rag-ingestion-v2-xlsx-candidate-v1"
XLSX_CANDIDATE_NAMESPACE = "rag-ingestion-v2-xlsx-candidate-v1"
XLSX_CANDIDATE_ARTIFACT_DIR = Path("eval/indexes/rag-data-xlsx-candidate-v1")
LEGACY_CSV_ARCHIVE = ROOT / "archive" / "results" / "2026-05-05-eval-query-lineage-cleanup" / "csv"

DEFAULT_HUMAN_REVIEW_OFFICIAL_RETRIEVAL_GOLD = Path(
    "eval/eval_queries/gold_queries_xlsx_human_review_official_positive_v0_retrieval.csv"
)
LEGACY_V3_POSITIVE_GOLD = Path("eval/eval_queries/gold_queries_xlsx_v3_positive_reviewed.csv")
DEFAULT_V3_POSITIVE_GOLD = DEFAULT_HUMAN_REVIEW_OFFICIAL_RETRIEVAL_GOLD
DEFAULT_V3_NATURALIZED_GOLD = LEGACY_CSV_ARCHIVE / "gold_queries_xlsx_v3_naturalized.csv"
DEFAULT_V2_GOLD = LEGACY_CSV_ARCHIVE / "gold_queries_xlsx_v2.csv"
DEFAULT_REPORT = Path(
    "eval/reports/rag-ingestion/"
    "rag_retrieval_eval_xlsx_human_review_official_positive_v0_vector_diagnostic_report.json"
)
DEFAULT_SUMMARY = Path(
    "eval/reports/rag-ingestion/"
    "rag_xlsx_human_review_official_positive_v0_retrieval_performance_summary.json"
)
DEFAULT_HIDDEN_REPORT = Path(
    "eval/reports/rag-ingestion/"
    "rag_xlsx_human_review_official_positive_v0_hidden_negative_leakage_diagnostic.json"
)

METRIC_KEYS = [
    "Hit@1",
    "Hit@3",
    "Hit@5",
    "Hit@10",
    "MRR@10",
    "xlsx_file_hit@10",
    "xlsx_sheet_hit@10",
    "xlsx_range_overlap@10",
    "xlsx_range_contains@10",
    "xlsx_exact_range@10",
    "target_cell_hit",
    "target_row_hit",
    "header_included",
    "target_column_included",
    "surrounding_context_included",
    "sheet_resolution_accuracy",
    "xlsx_citation_location_accuracy",
    "result_empty_count",
    "hidden_content_leakage_count",
]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validate_official_xlsx_eval_route(
            eval_mode=args.eval_mode,
            track="XLSX",
            agent_orchestrator_enabled=args.agent_orchestrator_enabled,
            retrieval_backend=args.retrieval_backend,
            namespace=XLSX_CANDIDATE_NAMESPACE,
            vector_index_dir=args.vector_index_dir,
            positive_gold=args.positive_gold,
            candidate_index_version=args.candidate_index_version,
            required_index_version=args.required_index_version,
            combined_retrieval_enabled=args.combined_retrieval_enabled,
        )
        validate_diagnostic_agentic_xlsx_config(
            eval_mode=args.eval_mode,
            track="XLSX",
            namespace=XLSX_CANDIDATE_NAMESPACE,
            agent_orchestrator_enabled=args.agent_orchestrator_enabled,
            diagnostic_agentic_allow=args.diagnostic_agentic_allow,
            retriever_names=args.diagnostic_agentic_retriever_name,
            global_fallback_enabled=args.global_fallback_enabled,
            external_search_enabled=args.external_search_enabled,
            max_iterations=args.diagnostic_agentic_max_iterations,
        )
        if args.diagnostic_agentic_allow:
            raise XlsxPreSilverRiskError(
                "diagnostic XLSX agentic E2E runner is not implemented in this wrapper; "
                "the explicit allow flag is accepted only after a runner records validated iterations"
            )
        if Path(args.positive_gold).name == DEFAULT_HUMAN_REVIEW_OFFICIAL_RETRIEVAL_GOLD.name:
            resolve_current_xlsx_human_review_artifacts(
                registry_path=Path(args.official_registry),
                require_source_snapshot=False,
            )
    except XlsxPreSilverRiskError as exc:
        payload = {
            "run_id": utc_run_id(),
            "generated_at": utc_timestamp(),
            "status": "ROUTE_GUARD_FAILED",
            "track": "XLSX",
            "eval_mode": args.eval_mode,
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "error": str(exc),
            "official_xlsx_answer_generation_denominator": 0,
        }
        write_json(Path(args.report), payload)
        print_json(payload)
        return 2
    candidate_index_version = args.candidate_index_version
    required_index_version = args.required_index_version or candidate_index_version
    positive_gold_path, positive_rows, positive_source = resolve_positive_rows(args)
    hidden_source_path, hidden_rows = resolve_hidden_rows(args)

    validation = validate_gold_rows(positive_rows, require_live_bound=False)
    validation_payload = validation_summary(validation)
    if not validation.ok:
        payload = base_report_payload(args, positive_gold_path, positive_source, validation_payload) | {
            "status": "VALIDATION_FAILED",
            "query_results": [],
            "per_query": [],
            "metrics": {},
            "bucket_metrics": {},
        }
        write_json(Path(args.report), payload)
        write_summary(
            args=args,
            status="VALIDATION_FAILED",
            positive_gold_path=positive_gold_path,
            positive_source=positive_source,
            positive_report=payload,
            hidden_report=None,
            hidden_source_path=hidden_source_path,
            hidden_rows=hidden_rows,
            validation_payload=validation_payload,
        )
        print_json(payload)
        return 1

    search_fn = search_vector(
        index_dir=args.vector_index_dir,
        db_dsn=args.vector_db_dsn,
        embedding_model=args.vector_embedding_model,
        query_prefix=args.vector_query_prefix,
        passage_prefix=args.vector_passage_prefix,
        max_seq_length=args.vector_max_seq_length,
        batch_size=args.vector_batch_size,
        expected_index_version=required_index_version,
    )

    positive_report = evaluate_gold_rows(
        positive_rows,
        search_fn=search_fn,
        top_k=args.top_k,
        candidate_index_version=candidate_index_version,
        required_embedding_status=args.required_embedding_status or None,
        required_index_version=required_index_version,
    )
    positive_report.update(base_report_payload(args, positive_gold_path, positive_source, validation_payload))
    positive_report["status"] = "COMPLETED" if validation.ok else positive_report.get("status")
    write_json(Path(args.report), positive_report)

    hidden_report = build_hidden_leakage_report(
        args=args,
        search_fn=search_fn,
        hidden_source_path=hidden_source_path,
        hidden_rows=hidden_rows,
        candidate_index_version=candidate_index_version,
        required_index_version=required_index_version,
    )
    write_json(Path(args.hidden_report), hidden_report)

    summary = write_summary(
        args=args,
        status="COMPLETED",
        positive_gold_path=positive_gold_path,
        positive_source=positive_source,
        positive_report=positive_report,
        hidden_report=hidden_report,
        hidden_source_path=hidden_source_path,
        hidden_rows=hidden_rows,
        validation_payload=validation_payload,
    )
    print_json(summary)
    return 0


def resolve_positive_rows(args: argparse.Namespace) -> tuple[Path, list[dict[str, str]], dict[str, Any]]:
    positive_path = Path(args.positive_gold)
    if positive_path.exists():
        rows = [row for row in load_gold_csv(positive_path) if not is_hidden_negative(row)]
        if positive_path.name == DEFAULT_HUMAN_REVIEW_OFFICIAL_RETRIEVAL_GOLD.name:
            return positive_path, rows, {
                "mode": "human_review_official_positive_retrieval_projection",
                "source_path": str(positive_path),
                "fallback_generated": False,
                "selection_rule": (
                    "use the projected XLSX human-review official positive retrieval/evidence denominator; "
                    "answer-generation denominator remains zero"
                ),
                "denominator_kind": "xlsx_retrieval_evidence_diagnostic",
                "official_xlsx_answer_generation_denominator": 0,
                "legacy_default_positive_gold": str(LEGACY_V3_POSITIVE_GOLD),
            }
        return positive_path, rows, {
            "mode": "reviewed_positive_file",
            "source_path": str(positive_path),
            "fallback_generated": False,
            "selection_rule": "use caller-supplied reviewed positive retrieval CSV when present",
            "denominator_kind": "caller_supplied_retrieval_evidence_diagnostic",
            "official_xlsx_answer_generation_denominator": 0,
        }

    raise FileNotFoundError(
        "official XLSX reviewed positive gold is required; refusing to regenerate "
        f"an active positive CSV from archived v2/v3 manifests: {positive_path}"
    )


def resolve_hidden_rows(args: argparse.Namespace) -> tuple[Path, list[dict[str, str]]]:
    for path in [Path(args.naturalized_gold), Path(args.v2_gold)]:
        if path.exists():
            rows = [row for row in load_gold_csv(path) if is_hidden_negative(row)]
            if rows:
                return path, rows
    return Path(args.naturalized_gold), []


def build_hidden_leakage_report(
    *,
    args: argparse.Namespace,
    search_fn: Any,
    hidden_source_path: Path,
    hidden_rows: list[dict[str, str]],
    candidate_index_version: str,
    required_index_version: str,
) -> dict[str, Any]:
    if not hidden_rows:
        return {
            "run_id": utc_run_id(),
            "generated_at": utc_timestamp(),
            "status": "NO_HIDDEN_NEGATIVE_ROWS",
            "report_role": "xlsx_hidden_negative_leakage_diagnostic",
            "promotion_evidence": False,
            "evidence_role": "diagnostic",
            "retrieval_backend": "vector",
            "positive_metric_mix_allowed": False,
            "excluded_from_positive_metrics": True,
            "source_hidden_gold": str(hidden_source_path),
            "hidden_negative_row_count": 0,
            "metrics": {
                "hidden_content_leakage_count": 0,
                "hidden_negative_pass_count": 0,
                "search_error_count": 0,
            },
            "query_results": [],
            "notes": ["No hidden-negative rows were found in the configured v3/v2 manifests."],
        }

    hidden_eval = evaluate_gold_rows(
        hidden_rows,
        search_fn=search_fn,
        top_k=args.top_k,
        candidate_index_version=candidate_index_version,
        required_embedding_status=args.required_embedding_status or None,
        required_index_version=required_index_version,
    )
    metrics = hidden_eval.get("metrics") or {}
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": hidden_eval.get("status", "COMPLETED"),
        "report_role": "xlsx_hidden_negative_leakage_diagnostic",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_backend": "vector",
        "backend_identity": backend_identity(args, required_index_version),
        "candidate_index_version": candidate_index_version,
        "namespace": XLSX_CANDIDATE_NAMESPACE,
        "required_index_version": required_index_version,
        "required_embedding_status": args.required_embedding_status or None,
        "top_k": args.top_k,
        "positive_metric_mix_allowed": False,
        "excluded_from_positive_metrics": True,
        "source_hidden_gold": str(hidden_source_path),
        "hidden_negative_row_count": len(hidden_rows),
        "hidden_negative_query_ids": [row.get("query_id", "") for row in hidden_rows],
        "validation": hidden_eval.get("validation") or {},
        "metrics": {
            "hidden_content_leakage_count": metrics.get("hidden_content_leakage_count", 0),
            "hidden_negative_pass_count": metrics.get("hidden_negative_pass_count", 0),
            "search_error_count": metrics.get("search_error_count", 0),
            "result_empty_count": metrics.get("result_empty_count", 0),
        },
        "query_results": hidden_eval.get("query_results") or [],
        "notes": [
            "Hidden-negative probes are evaluated only for leakage.",
            "These rows are excluded from positive Hit@K and MRR metrics.",
        ],
    }


def base_report_payload(
    args: argparse.Namespace,
    positive_gold_path: Path,
    positive_source: Mapping[str, Any],
    validation_payload: Mapping[str, Any],
) -> dict[str, Any]:
    required_index_version = args.required_index_version or args.candidate_index_version
    return {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "gold": str(positive_gold_path),
        "top_k": args.top_k,
        "retrieval_backend": "vector",
        "backend_identity": backend_identity(args, required_index_version),
        "eval_mode": args.eval_mode,
        "official_route_guard": {
            "generic_agent_orchestrator_allowed": False,
            "agent_orchestrator_enabled": args.agent_orchestrator_enabled,
            "combined_retrieval_enabled": args.combined_retrieval_enabled,
            "diagnostic_agentic_allow": args.diagnostic_agentic_allow,
            "diagnostic_agentic_runner_available": False,
            "message": "official XLSX eval uses the XLSX wrapper/retrieval-evidence path only",
        },
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "row_filter": {
            "source": positive_source,
            "positive_only": True,
            "hidden_negative_excluded": True,
            "expected_location_types": ["xlsx"],
        },
        "candidate_index_version": args.candidate_index_version,
        "namespace": XLSX_CANDIDATE_NAMESPACE,
        "required_embedding_status": args.required_embedding_status or None,
        "required_index_version": required_index_version,
        "diagnostic_policy": diagnostic_policy_payload(),
        "validation": validation_payload,
    }


def write_summary(
    *,
    args: argparse.Namespace,
    status: str,
    positive_gold_path: Path,
    positive_source: Mapping[str, Any],
    positive_report: Mapping[str, Any],
    hidden_report: Mapping[str, Any] | None,
    hidden_source_path: Path,
    hidden_rows: list[dict[str, str]],
    validation_payload: Mapping[str, Any],
) -> dict[str, Any]:
    metrics = positive_report.get("metrics") or {}
    hidden_metrics = (hidden_report or {}).get("metrics") or {}
    summary = {
        "run_id": utc_run_id(),
        "generated_at": utc_timestamp(),
        "status": status,
        "report_role": "xlsx_human_review_official_positive_v0_retrieval_performance_summary",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "eval_mode": args.eval_mode,
        "retrieval_backend": "vector",
        "official_route_guard": {
            "generic_agent_orchestrator_allowed": False,
            "agent_orchestrator_enabled": args.agent_orchestrator_enabled,
            "combined_retrieval_enabled": args.combined_retrieval_enabled,
            "diagnostic_agentic_allow": args.diagnostic_agentic_allow,
            "diagnostic_agentic_runner_available": False,
        },
        "candidate_index_version": args.candidate_index_version,
        "namespace": XLSX_CANDIDATE_NAMESPACE,
        "artifact_dir": str(Path(args.vector_index_dir)),
        "positive_gold": str(positive_gold_path),
        "positive_source": positive_source,
        "positive_diagnostic_report": str(Path(args.report)),
        "hidden_negative_source": str(hidden_source_path),
        "hidden_negative_row_count": len(hidden_rows),
        "hidden_negative_leakage_report": str(Path(args.hidden_report)),
        "gold_validation": validation_payload,
        "metrics": metrics_subset(metrics),
        "hidden_negative_metrics": {
            "hidden_content_leakage_count": hidden_metrics.get("hidden_content_leakage_count", 0),
            "hidden_negative_pass_count": hidden_metrics.get("hidden_negative_pass_count", 0),
            "positive_metric_mix_allowed": False,
        },
        "diagnostic_policy": diagnostic_policy_payload(),
    }
    write_json(Path(args.summary), summary)
    return summary


def backend_identity(args: argparse.Namespace, required_index_version: str) -> dict[str, Any]:
    return {
        "backend": "faiss",
        "index_dir": str(Path(args.vector_index_dir)),
        "index_namespace_filter": required_index_version,
        "db_dsn": redact_dsn(args.vector_db_dsn),
        "filtering_mode": "vector_namespace_then_contract_filter",
    }


def diagnostic_policy_payload() -> dict[str, Any]:
    return {
        "promotion_executed": False,
        "promotion_evidence_true_set": False,
        "baseline_descriptor_artifact_hash_modified": False,
        "hybrid_search_introduced": False,
        "reranking_introduced": False,
        "parser_expansion_introduced": False,
        "threshold_relaxed": False,
        "positive_metrics_exclude_hidden_negative_rows": True,
    }


def metrics_subset(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {key: metrics.get(key) for key in METRIC_KEYS}


def validation_summary(validation: Any) -> dict[str, Any]:
    return {
        "ok": validation.ok,
        "error_count": len(validation.errors),
        "row_error_count": len(validation.row_errors),
        "errors": validation.errors,
        "row_errors": validation.row_errors,
        "row_count": validation.row_count,
        "bucket_counts": validation.bucket_counts,
    }


def is_positive_row(row: Mapping[str, str]) -> bool:
    return (
        (row.get("v2_label_status") or "").strip() == "positive"
        and not is_hidden_negative(row)
        and (row.get("expected_location_type") or "").strip().lower() == "xlsx"
    )


def is_hidden_negative(row: Mapping[str, str]) -> bool:
    return (
        (row.get("hidden_policy") or "").strip() == "negative"
        or (row.get("v2_label_status") or "").strip() == "negative_hidden_policy"
        or (row.get("eval_purpose") or "").strip() == "hidden_policy_negative"
    )


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def print_json(payload: Mapping[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def redact_dsn(dsn: str) -> str:
    parts = []
    for token in dsn.split():
        if token.lower().startswith("password="):
            parts.append("password=<redacted>")
        else:
            parts.append(token)
    return " ".join(parts)


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-mode", choices=["official", "diagnostic"], default="official")
    parser.add_argument("--retrieval-backend", default="vector")
    parser.add_argument("--agent-orchestrator-enabled", action="store_true")
    parser.add_argument("--diagnostic-agentic-allow", action="store_true")
    parser.add_argument("--diagnostic-agentic-retriever-name", action="append", default=[])
    parser.add_argument("--diagnostic-agentic-max-iterations", type=int, default=1)
    parser.add_argument("--global-fallback-enabled", action="store_true")
    parser.add_argument("--external-search-enabled", action="store_true")
    parser.add_argument("--combined-retrieval-enabled", action="store_true")
    parser.add_argument(
        "--official-registry",
        default="ai-worker/eval/eval_queries/official_denominator_registry.json",
    )
    parser.add_argument("--positive-gold", default=str(DEFAULT_V3_POSITIVE_GOLD))
    parser.add_argument("--naturalized-gold", default=str(DEFAULT_V3_NATURALIZED_GOLD))
    parser.add_argument("--v2-gold", default=str(DEFAULT_V2_GOLD))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--summary", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--hidden-report", default=str(DEFAULT_HIDDEN_REPORT))
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--vector-index-dir", default=str(XLSX_CANDIDATE_ARTIFACT_DIR))
    parser.add_argument(
        "--vector-db-dsn",
        default="host=localhost port=5433 dbname=aipipeline user=aipipeline password=aipipeline_pw",
    )
    parser.add_argument("--vector-embedding-model", default="BAAI/bge-m3")
    parser.add_argument("--vector-query-prefix", default="")
    parser.add_argument("--vector-passage-prefix", default="")
    parser.add_argument("--vector-max-seq-length", type=int, default=1024)
    parser.add_argument("--vector-batch-size", type=int, default=32)
    parser.add_argument("--candidate-index-version", default=XLSX_CANDIDATE_INDEX_VERSION)
    parser.add_argument("--required-index-version", default=XLSX_CANDIDATE_NAMESPACE)
    parser.add_argument("--required-embedding-status", default="EMBEDDED")
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
